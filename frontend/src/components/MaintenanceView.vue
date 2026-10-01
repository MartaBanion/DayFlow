<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ApiRequestError, backupApi, taskApi } from '../api'
import type { Backup, BackupVerification, RuntimeInfo } from '../types'

const backups = ref<Backup[]>([])
const runtime = ref<RuntimeInfo | null>(null)
const loading = ref(false)
const listLoaded = ref(false)
const listError = ref('')
const runtimeError = ref('')
const creating = ref(false)
const createError = ref('')
const created = ref<Backup | null>(null)
const verifying = reactive<Record<string, boolean>>({})
const results = reactive<Record<string, BackupVerification>>({})
const verifyErrors = reactive<Record<string, string>>({})
const copyMessage = ref('')

function errorText(error: unknown, action: string): string {
  if (!(error instanceof ApiRequestError)) return `${action}失败，请确认后端服务正在运行后重试。`
  const codes: Record<string, string> = {
    backup_registration_failed: '备份数据文件可能已保存，但登记失败。请检查后端日志后再重试。',
    backup_timeout: '数据库繁忙或操作超时，请稍后重试。',
    backup_permission_denied: '没有读取或保存备份的权限，请检查备份目录权限。',
    backup_path_unsafe: '备份路径不安全，操作已拒绝。请检查备份目录。',
    backup_manifest_invalid: '备份元数据异常，请检查备份登记信息。',
    backup_not_found: '备份登记不存在，请刷新列表。',
    backup_origin_rejected: '当前页面来源不受信任，请从 DayFlow 本地地址访问。',
    backup_schema_incompatible: '数据库版本不兼容，无法创建备份。',
    backup_platform_unsupported: '当前环境缺少 Linux / WSL 备份能力，操作已拒绝。',
    backup_file_conflict: '备份文件名冲突，未覆盖已有文件。请重试。',
  }
  return codes[error.code ?? ''] ?? `${action}失败，请稍后重试。（HTTP ${error.status}）`
}

async function loadList(): Promise<void> {
  if (loading.value) return
  loading.value = true
  listError.value = ''
  try {
    backups.value = await backupApi.list()
    listLoaded.value = true
  } catch (error) { listError.value = errorText(error, '备份列表加载') }
  finally { loading.value = false }
}

async function loadRuntime(): Promise<void> {
  runtimeError.value = ''
  try { runtime.value = await taskApi.getRuntime() }
  catch (error) { runtimeError.value = errorText(error, '数据库状态读取') }
}

async function createBackup(): Promise<void> {
  if (creating.value) return
  creating.value = true
  createError.value = ''
  created.value = null
  try {
    created.value = await backupApi.create()
    await loadList()
  } catch (error) { createError.value = errorText(error, '创建备份') }
  finally { creating.value = false }
}

async function verifyBackup(backup: Backup): Promise<void> {
  const id = backup.backup_id
  if (verifying[id]) return
  verifying[id] = true
  delete verifyErrors[id]
  try { results[id] = await backupApi.verify(id) }
  catch (error) { verifyErrors[id] = errorText(error, '验证备份') }
  finally { verifying[id] = false }
}

function status(backup: Backup): string {
  if (verifyErrors[backup.backup_id]) return '验证请求失败'
  const result = results[backup.backup_id]
  if (!result) return backup.compatible_for_restore ? '需要验证' : '不兼容 · 不可恢复'
  if (result.status === 'manifest_mismatch') return '元数据不匹配 · 不可恢复'
  if (result.status === 'corrupted') return '验证失败 · 备份损坏或结构异常'
  if (result.status === 'unreadable') return '验证失败 · 文件缺失、不可读或不安全'
  if (result.status === 'incompatible' || !result.compatible_for_restore) return '不兼容 · 不可恢复'
  return '可用于当前版本恢复'
}

function time(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}
function size(value: number): string {
  return value < 1024 ? `${value} B` : `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 }).format(value / 1024)} KiB`
}
async function copySha(value: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(value)
    copyMessage.value = '完整 SHA-256 已复制'
  } catch { copyMessage.value = '无法复制，请展开并手动选择完整 SHA-256。' }
}

onMounted(() => { void loadRuntime(); void loadList() })
</script>

<template>
  <div class="maintenance-view">
    <header class="page-header">
      <div><h2>数据与备份</h2><p class="muted">保留一致性快照，先验证，再准备恢复。</p></div>
      <el-button :loading="loading" @click="loadList">刷新备份列表</el-button>
    </header>

    <section class="maintenance-panel" aria-labelledby="database-title">
      <h3 id="database-title">当前数据库</h3>
      <p v-if="runtimeError" role="alert">{{ runtimeError }} <el-button text @click="loadRuntime">重试数据库状态</el-button></p>
      <p v-else-if="!runtime" role="status">正在读取数据库状态…</p>
      <dl class="maintenance-metadata">
        <div><dt>应用版本</dt><dd>{{ runtime?.app_version ?? '未获取' }}</dd></div>
        <div><dt>数据库 Schema</dt><dd>{{ runtime?.database_schema ?? '未获取' }}</dd></div>
        <div><dt>备份位置</dt><dd>数据库同级 backups/（默认 data/backups/）</dd></div>
        <div><dt>已登记备份</dt><dd>{{ listLoaded && !listError ? `${backups.length} 份` : '未获取' }}</dd></div>
      </dl>
    </section>

    <section class="maintenance-panel" aria-labelledby="create-title">
      <div class="maintenance-heading"><div><h3 id="create-title">创建备份</h3><p class="muted">创建当前数据库的一致性快照，不暂停日常任务操作。</p></div>
        <el-button type="primary" :loading="creating" :disabled="loading" @click="createBackup">创建备份</el-button>
      </div>
      <p v-if="createError" class="form-error" role="alert">{{ createError }}</p>
      <div v-if="created" class="maintenance-success" role="status">
        <strong>备份已创建</strong>
        <p class="maintenance-filename">{{ created.filename }}</p>
        <p>{{ time(created.created_at_utc) }} · {{ size(created.file_size) }} · {{ created.alembic_version }}</p>
        <p>SHA-256：{{ created.database_sha256.slice(0, 12) }}…</p>
      </div>
    </section>

    <section class="maintenance-panel" aria-labelledby="backups-title" :aria-busy="loading">
      <h3 id="backups-title">备份列表</h3>
      <p class="muted">列表展示登记时的验证记录；点击“验证”检查文件当前状态。验证不会修改备份文件。</p>
      <p v-if="loading" role="status">正在加载备份列表…</p>
      <div v-if="listError" role="alert"><p class="form-error">{{ listError }}</p><el-button @click="loadList">重试备份列表</el-button></div>
      <div v-if="listLoaded && !loading && !listError && !backups.length" class="maintenance-empty">
        <h4>还没有备份</h4><p class="muted">创建第一份快照，为本地数据保留一个检查点。</p>
        <el-button :loading="creating" :disabled="loading" @click="createBackup">创建第一份备份</el-button>
      </div>
      <div class="maintenance-list">
        <article v-for="backup in backups" :key="backup.backup_id" class="backup-card" :aria-label="`备份 ${backup.filename}`">
          <div class="maintenance-heading">
            <div><h4 class="maintenance-filename" :title="backup.filename">{{ backup.filename }}</h4><p class="muted">{{ time(backup.created_at_utc) }}</p></div>
            <el-button :aria-label="`验证备份 ${backup.filename}`" :loading="verifying[backup.backup_id]" @click="verifyBackup(backup)">验证</el-button>
          </div>
          <p role="status" class="backup-status">{{ verifying[backup.backup_id] ? '验证中…' : status(backup) }}</p>
          <p v-if="verifyErrors[backup.backup_id]" class="form-error" role="alert">{{ verifyErrors[backup.backup_id] }}</p>
          <dl class="maintenance-metadata">
            <div><dt>大小</dt><dd>{{ results[backup.backup_id] ? (results[backup.backup_id]!.file_size === null ? '无法读取' : size(results[backup.backup_id]!.file_size!)) : size(backup.file_size) }}</dd></div>
            <div><dt>Schema</dt><dd>{{ results[backup.backup_id] ? (results[backup.backup_id]!.alembic_version ?? '无法读取') : backup.alembic_version }}</dd></div>
            <div><dt>完整性</dt><dd>{{ (results[backup.backup_id] ? results[backup.backup_id]!.integrity_check : backup.integrity_check) === 'ok' ? '通过' : '未通过或无法读取' }}</dd></div>
            <div><dt>外键错误</dt><dd>{{ results[backup.backup_id] ? (results[backup.backup_id]!.foreign_key_errors ?? '无法读取') : backup.foreign_key_errors }}</dd></div>
            <div><dt>{{ results[backup.backup_id] ? '本次验证时间' : '登记验证时间' }}</dt><dd>{{ time(results[backup.backup_id]?.verified_at_utc ?? backup.verified_at_utc) }}</dd></div>
          </dl>
          <details class="backup-hash"><summary>SHA-256：{{ (results[backup.backup_id] ? results[backup.backup_id]!.database_sha256 ?? '无法读取' : backup.database_sha256).slice(0, 12) }}… · 查看完整值</summary>
            <code>{{ results[backup.backup_id] ? results[backup.backup_id]!.database_sha256 ?? '无法读取' : backup.database_sha256 }}</code>
          </details>
          <el-button text :disabled="Boolean(verifying[backup.backup_id]) || Boolean(results[backup.backup_id] && !results[backup.backup_id]!.database_sha256)" @click="copySha(results[backup.backup_id]?.database_sha256 ?? backup.database_sha256)">复制完整 SHA</el-button>
          <p v-if="results[backup.backup_id]?.status === 'manifest_mismatch'" class="form-error">实际文件与登记的 SHA、大小或 Schema 不一致。请保留文件并检查，不能用于恢复。</p>
          <p v-if="results[backup.backup_id]?.status === 'corrupted'" class="form-error">完整性、外键或关键结构检查未通过。不能用于恢复。</p>
          <p v-if="!backup.compatible_for_restore || results[backup.backup_id]?.status === 'incompatible'" class="muted">仅支持 Schema 0005_add_deadlines_recurrence_reminders，不会自动迁移备份。</p>
        </article>
      </div>
      <p v-if="copyMessage" role="status">{{ copyMessage }}</p>
    </section>

    <section class="maintenance-panel restore-guidance" aria-labelledby="restore-title">
      <h3 id="restore-title">恢复准备说明</h3>
      <p>恢复会覆盖当前数据库，必须停止 DayFlow，通过离线 Maintenance CLI 执行，并先创建恢复前安全备份。</p>
      <p class="muted">恢复功能将在 V0.6 Phase 3 提供，当前版本仅支持创建和验证备份。页面不会执行恢复，也不会自动启动服务。</p>
    </section>
  </div>
</template>

<style scoped>
.maintenance-view { display: grid; gap: var(--space-4); min-width: 0; }
.maintenance-view .page-header { margin-bottom: 0; }
.maintenance-panel { padding: var(--space-5); border: 1px solid var(--color-border); border-radius: var(--radius-card); background: var(--color-surface); min-width: 0; }
.maintenance-panel h3 { font-size: var(--font-size-section-title); margin: 0 0 var(--space-2); }
.maintenance-panel p { margin: var(--space-2) 0; overflow-wrap: anywhere; }
.maintenance-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); }
.maintenance-heading > div { min-width: 0; }
.maintenance-heading > .el-button { flex-shrink: 0; }
.maintenance-metadata { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-3); margin: var(--space-4) 0; }
.maintenance-metadata dt { color: var(--color-muted); font-size: var(--font-size-caption); }
.maintenance-metadata dd { margin: var(--space-1) 0 0; overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }
.maintenance-list { display: grid; gap: var(--space-3); }
.backup-card { padding: var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-control); min-width: 0; }
.maintenance-filename { overflow-wrap: anywhere; font-size: var(--font-size-body); margin: 0; }
.backup-status { font-weight: 600; }
.backup-hash { color: var(--color-text-secondary); font-size: var(--font-size-caption); }
.backup-hash summary { cursor: pointer; overflow-wrap: anywhere; }
.backup-hash code { display: block; overflow-wrap: anywhere; margin-top: var(--space-2); user-select: all; }
.maintenance-success { border-left: 3px solid var(--color-success); padding-left: var(--space-3); }
.maintenance-empty { text-align: center; padding: var(--space-5); }
.restore-guidance { border-left: 3px solid var(--color-warning); }
@media (max-width: 1200px) { .maintenance-panel { padding: var(--space-4); } }
@media (max-width: 960px) { .maintenance-metadata { grid-template-columns: 1fr; } .maintenance-heading { flex-wrap: wrap; } }
</style>
