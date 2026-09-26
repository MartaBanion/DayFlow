import { createHash } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import { mkdtemp, rm } from 'node:fs/promises'
import { spawn, spawnSync } from 'node:child_process'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import { dirname, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const projectRoot = resolve(frontendRoot, '..')
const backendRoot = join(projectRoot, 'backend')
const realDatabasePath = resolve(projectRoot, 'data', 'dayflow.sqlite3')
const backendPort = 18000
const frontendPort = 15173
const expectedMigration = '0002_add_priority_categories_tags'

const processes = new Set()
let activePlaywright
let stopping = false

const sqliteProbe = String.raw`
import json
import sqlite3
import sys
from pathlib import Path

database_path = Path(sys.argv[1]).resolve()
uri = f"file:{database_path}?mode=ro"
connection = sqlite3.connect(uri, uri=True)
try:
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
    migration = connection.execute(
        "SELECT version_num FROM alembic_version"
    ).fetchone()[0]
    task_count = connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    active_count = connection.execute(
        "SELECT COUNT(*) FROM tasks WHERE deleted_at_utc IS NULL"
    ).fetchone()[0]
    deleted_count = connection.execute(
        "SELECT COUNT(*) FROM tasks WHERE deleted_at_utc IS NOT NULL"
    ).fetchone()[0]
finally:
    connection.close()

print(json.dumps({
    "path": str(database_path),
    "integrity_check": integrity,
    "foreign_key_errors": len(foreign_keys),
    "alembic_version": migration,
    "task_count": task_count,
    "active_count": active_count,
    "deleted_count": deleted_count,
}))
`

function fail(message) {
  throw new Error(`[e2e safety] ${message}`)
}

function ensureNotStopping() {
  if (stopping) fail('收到终止信号，停止 E2E 运行。')
}

function isPathInside(child, parent) {
  const childRelative = relative(parent, child)
  return childRelative === '' || (childRelative !== '..' && !childRelative.startsWith(`..${sep}`))
}

function commandAvailable(command) {
  const result = spawnSync(command, ['--version'], { stdio: 'ignore' })
  return !result.error && result.status === 0
}

function ensurePortAvailable(port, label) {
  return new Promise((resolvePort, rejectPort) => {
    const server = createServer()
    server.once('error', () => {
      rejectPort(new Error(`[e2e safety] ${label} 测试端口 127.0.0.1:${port} 已被占用；不会终止未知进程。`))
    })
    server.listen(port, '127.0.0.1', () => {
      server.close((closeError) => {
        if (closeError) rejectPort(closeError)
        else resolvePort()
      })
    })
  })
}

function resolveBackendRuntime() {
  const virtualenvPython = join(backendRoot, '.venv', 'bin', 'python')
  if (existsSync(virtualenvPython)) {
    return {
      command: virtualenvPython,
      python: virtualenvPython,
      migrationArgs: ['-m', 'alembic', '-c', 'alembic.ini', 'upgrade', 'head'],
      settingsArgs: [],
      serverArgs: ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(backendPort)],
    }
  }

  if (commandAvailable('uv')) {
    return {
      command: 'uv',
      python: commandAvailable('python3') ? 'python3' : 'python',
      migrationArgs: ['run', 'alembic', 'upgrade', 'head'],
      settingsArgs: ['run', 'python'],
      serverArgs: ['run', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(backendPort)],
    }
  }

  const systemPython = commandAvailable('python3') ? 'python3' : commandAvailable('python') ? 'python' : null
  if (systemPython) {
    return {
      command: systemPython,
      python: systemPython,
      migrationArgs: ['-m', 'alembic', '-c', 'alembic.ini', 'upgrade', 'head'],
      settingsArgs: [],
      serverArgs: ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(backendPort)],
    }
  }

  fail('无法找到 Backend Python/uv 运行时。请先准备 backend/.venv 或 uv。')
}

function sha256(filePath) {
  return createHash('sha256').update(readFileSync(filePath)).digest('hex')
}

function inspectDatabase(python, filePath) {
  const result = spawnSync(python, ['-c', sqliteProbe, filePath], {
    cwd: projectRoot,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  if (result.error || result.status !== 0) {
    fail(`只读检查数据库失败：${result.stderr || result.error?.message || 'unknown error'}`)
  }
  return JSON.parse(result.stdout)
}

const settingsProbe = String.raw`
from pathlib import Path
from app.core.config import get_settings

print(Path(get_settings().database_path).resolve())
`

function resolveBackendDatabase(runtime, runtimeEnv) {
  const result = spawnSync(
    runtime.command,
    [...runtime.settingsArgs, '-c', settingsProbe],
    {
      cwd: backendRoot,
      env: runtimeEnv,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  )
  if (result.error || result.status !== 0) {
    fail(`无法验证 Backend 实际数据库路径：${result.stderr || result.error?.message || 'unknown error'}`)
  }
  return resolve(result.stdout.trim())
}

function spawnManaged(command, args, options, label) {
  const child = spawn(command, args, { ...options, stdio: 'inherit' })
  child.__dayflowLabel = label
  processes.add(child)
  child.once('close', () => processes.delete(child))
  child.once('error', (error) => {
    console.error(`[e2e] ${label} process error: ${error.message}`)
  })
  return child
}

function waitForExit(child) {
  if (child.exitCode !== null || child.signalCode !== null) return Promise.resolve()
  return new Promise((resolveExit) => child.once('close', resolveExit))
}

async function stopProcess(child) {
  if (child.exitCode !== null || child.signalCode !== null) return
  child.kill('SIGTERM')
  await Promise.race([
    waitForExit(child),
    new Promise((resolveTimeout) => setTimeout(resolveTimeout, 5_000)),
  ])
  if (child.exitCode === null && child.signalCode === null) child.kill('SIGKILL')
}

async function stopAllProcesses() {
  const running = [...processes]
  await Promise.all(running.map((child) => stopProcess(child)))
}

async function waitForHttp(url, label, child) {
  const deadline = Date.now() + 30_000
  let lastError = 'no response'
  while (Date.now() < deadline) {
    if (child.exitCode !== null || child.signalCode !== null) {
      fail(`${label} 在启动期间退出，exit=${child.exitCode} signal=${child.signalCode}`)
    }
    try {
      const response = await fetch(url)
      if (response.ok) return
      lastError = `HTTP ${response.status}`
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error)
    }
    await new Promise((resolveRetry) => setTimeout(resolveRetry, 250))
  }
  fail(`${label} 未能在 30 秒内就绪：${url}（${lastError}）`)
}

async function runPlaywright(runtimeEnv) {
  const cli = join(frontendRoot, 'node_modules', '@playwright', 'test', 'cli.js')
  if (!existsSync(cli)) fail('未找到 @playwright/test，请先运行 npm ci 或 npm install。')

  activePlaywright = spawnManaged(
    process.execPath,
    [cli, 'test', ...process.argv.slice(2)],
    { cwd: frontendRoot, env: runtimeEnv },
    'Playwright',
  )
  const result = await new Promise((resolveResult) => {
    activePlaywright.once('close', (code, signal) => resolveResult({ code: code ?? 1, signal }))
  })
  activePlaywright = undefined
  return result
}

async function main() {
  if (!existsSync(realDatabasePath)) fail(`真实数据库不存在：${realDatabasePath}`)

  const runtime = resolveBackendRuntime()
  const beforeHash = sha256(realDatabasePath)
  const beforeProbe = inspectDatabase(runtime.python, realDatabasePath)
  console.log(`[e2e] real DB before sha256=${beforeHash}`)
  console.log(`[e2e] real DB before ${JSON.stringify(beforeProbe)}`)

  let tempRoot
  let temporaryDatabasePath
  let runtimeEnv
  let exitCode = 1
  try {
    tempRoot = await mkdtemp(join(tmpdir(), 'dayflow-e2e-'))
    temporaryDatabasePath = resolve(tempRoot, 'dayflow.sqlite3')
    const temporaryDatabaseDirectory = resolve(tempRoot)
    if (!tempRoot.startsWith(resolve(tmpdir()) + sep)) fail('临时目录不在系统临时目录内。')
    if (!tempRoot.split(sep).at(-1)?.startsWith('dayflow-e2e-')) fail('临时目录缺少 DayFlow E2E 前缀。')
    if (!isPathInside(temporaryDatabasePath, temporaryDatabaseDirectory)) fail('临时数据库路径越界。')
    if (temporaryDatabasePath === realDatabasePath || isPathInside(temporaryDatabasePath, resolve(projectRoot, 'data', 'backups'))) {
      fail('临时数据库路径命中了真实数据库或备份目录。')
    }

    runtimeEnv = {
      ...process.env,
      DAYFLOW_DATABASE_PATH: temporaryDatabasePath,
      DAYFLOW_BACKEND_ORIGIN: `http://127.0.0.1:${backendPort}`,
      DAYFLOW_FRONTEND_ORIGIN: `http://127.0.0.1:${frontendPort}`,
    }
    if (!runtimeEnv.DAYFLOW_DATABASE_PATH) fail('DAYFLOW_DATABASE_PATH 未显式设置。')
    if (resolve(runtimeEnv.DAYFLOW_DATABASE_PATH) !== temporaryDatabasePath) fail('DAYFLOW_DATABASE_PATH 解析结果不安全。')
    const resolvedBackendPath = resolveBackendDatabase(runtime, runtimeEnv)
    if (resolvedBackendPath !== temporaryDatabasePath) {
      fail(`Backend 实际解析到非临时数据库：${resolvedBackendPath}`)
    }
    ensureNotStopping()
    console.log(`[e2e] isolated DB=${temporaryDatabasePath}`)
    await ensurePortAvailable(backendPort, 'Backend')
    await ensurePortAvailable(frontendPort, 'Vite')
    const migration = spawnSync(runtime.command, runtime.migrationArgs, {
      cwd: backendRoot,
      env: runtimeEnv,
      stdio: 'inherit',
    })
    if (migration.status !== 0) fail(`临时数据库 Alembic upgrade 失败，exit=${migration.status}`)
    ensureNotStopping()
    const migratedProbe = inspectDatabase(runtime.python, temporaryDatabasePath)
    if (migratedProbe.alembic_version !== expectedMigration) {
      fail(`临时数据库 Migration 版本错误：${migratedProbe.alembic_version}`)
    }
    if (migratedProbe.integrity_check !== 'ok' || migratedProbe.foreign_key_errors !== 0) {
      fail(`临时数据库完整性检查失败：${JSON.stringify(migratedProbe)}`)
    }
    console.log(`[e2e] isolated DB after migration ${JSON.stringify(migratedProbe)}`)

    const backend = spawnManaged(runtime.command, runtime.serverArgs, {
      cwd: backendRoot,
      env: runtimeEnv,
    }, 'Backend')
    await waitForHttp(`http://127.0.0.1:${backendPort}/healthz`, 'Backend', backend)
    ensureNotStopping()

    const vite = spawnManaged(process.execPath, [
      join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'),
      '--host',
      '127.0.0.1',
      '--port',
      String(frontendPort),
    ], {
      cwd: frontendRoot,
      env: runtimeEnv,
    }, 'Vite')
    await waitForHttp(`http://127.0.0.1:${frontendPort}/`, 'Vite', vite)
    ensureNotStopping()
    const proxyHealth = await fetch(`http://127.0.0.1:${frontendPort}/healthz`)
    if (!proxyHealth.ok) fail(`Vite Proxy /healthz 失败：HTTP ${proxyHealth.status}`)
    ensureNotStopping()
    console.log('[e2e] Backend、Vite 和 Proxy 已在同一运行器中就绪。')

    const result = await runPlaywright(runtimeEnv)
    exitCode = result.code
    if (result.signal) console.error(`[e2e] Playwright signal=${result.signal}`)
  } finally {
    await stopAllProcesses()
    try {
      const afterHash = sha256(realDatabasePath)
      const afterProbe = inspectDatabase(runtime.python, realDatabasePath)
      console.log(`[e2e] real DB after sha256=${afterHash}`)
      console.log(`[e2e] real DB after ${JSON.stringify(afterProbe)}`)
      if (beforeHash !== afterHash) {
        console.error('[e2e safety] 真实数据库 SHA-256 发生变化，E2E 运行失败。')
        exitCode = 1
      }
      if (beforeProbe.integrity_check !== afterProbe.integrity_check || afterProbe.integrity_check !== 'ok') {
        console.error('[e2e safety] 真实数据库 integrity_check 异常。')
        exitCode = 1
      }
    } finally {
      if (tempRoot) {
        await rm(tempRoot, { recursive: true, force: true })
        console.log(`[e2e] removed isolated DB directory ${tempRoot}`)
      }
    }
  }
  return exitCode
}

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    if (stopping) return
    stopping = true
    activePlaywright?.kill(signal)
    void stopAllProcesses()
  })
}

main()
  .then((exitCode) => {
    process.exitCode = exitCode
  })
  .catch(async (error) => {
    console.error(error instanceof Error ? error.stack : error)
    await stopAllProcesses()
    process.exitCode = 1
  })
