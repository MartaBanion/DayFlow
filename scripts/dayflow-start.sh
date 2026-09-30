#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd -- "$script_dir/.." && pwd)"
backend_root="$project_root/backend"
frontend_root="$project_root/frontend"
real_database="$project_root/data/dayflow.sqlite3"
database_path="${DAYFLOW_DATABASE_PATH:-$real_database}"
backend_host="127.0.0.1"
frontend_host="127.0.0.1"
backend_port="${DAYFLOW_BACKEND_PORT:-8000}"
frontend_port="${DAYFLOW_FRONTEND_PORT:-5173}"
state_root="${DAYFLOW_STATE_DIR:-${XDG_STATE_HOME:-${HOME}/.local/state}/dayflow}"
lock_path="$state_root/lock"
backend_meta="$state_root/backend.meta"
frontend_meta="$state_root/frontend.meta"
backend_log="$state_root/backend.log"
frontend_log="$state_root/frontend.log"
backend_python="$backend_root/.venv/bin/python"
backend_uvicorn="$backend_root/.venv/bin/uvicorn"
node_bin=""
npm_bin=""

die() {
  printf 'DayFlow 启动失败：%s\n' "$1" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "缺少命令：$1"
}

require_command curl
require_command flock
require_command nohup
require_command ps
require_command readlink
require_command setsid
require_command ss

mkdir -p "$state_root"
exec 9>"$lock_path"
flock -n 9 || die '已有另一个 DayFlow 启停操作正在进行。'

[[ "$backend_port" =~ ^[0-9]+$ ]] || die "Backend 端口无效：$backend_port"
[[ "$frontend_port" =~ ^[0-9]+$ ]] || die "Frontend 端口无效：$frontend_port"
[[ -x "$backend_python" ]] || die "Backend Python 不存在：$backend_python"
[[ -x "$backend_uvicorn" ]] || die "Backend uvicorn 不存在：$backend_uvicorn"
[[ -d "$frontend_root/node_modules" ]] || die 'Frontend 依赖目录不存在，请先完成 npm ci。'
[[ -f "$database_path" ]] || die "数据库文件不存在：$database_path"

database_path="$(readlink -f -- "$database_path")"
real_database="$(readlink -f -- "$real_database")"
if [[ "$database_path" != "$real_database" && "${DAYFLOW_ALLOW_NONREAL_DATABASE:-0}" != '1' ]]; then
  die "默认启动只允许真实数据库；如需隔离测试，请显式设置 DAYFLOW_ALLOW_NONREAL_DATABASE=1。"
fi

application_version="$("$backend_python" - "$backend_root/pyproject.toml" "$frontend_root/package.json" <<'PY'
import json
import sys
import tomllib
from pathlib import Path

version = tomllib.loads(Path(sys.argv[1]).read_text())["project"]["version"]
frontend_version = json.loads(Path(sys.argv[2]).read_text())["version"]
if version != frontend_version:
    raise SystemExit("Backend 与 Frontend 项目版本不一致。")
print(version)
PY
)"
printf 'Application version: %s\n' "$application_version"

"$backend_python" - "$database_path" <<'PY'
import sqlite3
import sys

path = sys.argv[1]
with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
    version = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
if version != "0005_add_deadlines_recurrence_reminders":
    raise SystemExit(f"数据库版本不是 0005_add_deadlines_recurrence_reminders：{version}")
if integrity != "ok":
    raise SystemExit(f"数据库完整性检查失败：{integrity}")
if foreign_keys:
    raise SystemExit(f"数据库存在外键错误：{len(foreign_keys)}")
print(f"Database Alembic: {version}")
PY

load_node24() {
  local nvm_dir="${DAYFLOW_NVM_DIR:-${NVM_DIR:-${HOME}/.nvm}}"
  local default_version=''
  local candidate_dir=''

  if [[ -s "$nvm_dir/nvm.sh" ]]; then
    set +e
    # Existing user npm prefix settings can make nvm return non-zero while
    # still selecting the default Node binary. The resulting binary is checked below.
    . "$nvm_dir/nvm.sh" >/dev/null 2>&1
    set -e
  fi

  if command -v nvm >/dev/null 2>&1; then
    default_version="$(nvm version default 2>/dev/null || true)"
    if [[ "$default_version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
      candidate_dir="$nvm_dir/versions/node/$default_version/bin"
      if [[ -x "$candidate_dir/node" && -x "$candidate_dir/npm" ]]; then
        export PATH="$candidate_dir:$PATH"
      fi
    fi
  fi

  node_bin="$(command -v node || true)"
  npm_bin="$(command -v npm || true)"
  [[ -x "$node_bin" ]] || die '找不到 Node.js。请配置持久的 Node.js 24 LTS。'
  [[ -x "$npm_bin" ]] || die '找不到 npm。请检查 Node.js 24 LTS 安装。'

  local node_version node_major
  node_version="$($node_bin --version)"
  [[ "$node_version" =~ ^v([0-9]+)\.[0-9]+\.[0-9]+$ ]] || die "无法识别 Node.js 版本：$node_version"
  node_major="${BASH_REMATCH[1]}"
  (( node_major >= 24 )) || die "Node.js 版本过低：$node_version；项目要求 >=24.0.0。"
  printf 'Node.js: %s\n' "$node_version"
  printf 'npm: %s\n' "$($npm_bin --version)"
}

load_node24

proc_start_ticks() {
  local pid="$1"
  [[ -r "/proc/$pid/stat" ]] || return 1
  awk '{sub(/^.*\) /, ""); print $20}' "/proc/$pid/stat"
}

meta_value() {
  local path="$1"
  local key="$2"
  awk -F= -v wanted="$key" '$1 == wanted {print substr($0, index($0, "=") + 1); exit}' "$path"
}

service_cwd_matches() {
  local kind="$1"
  local pid="$2"
  local cwd
  cwd="$(readlink "/proc/$pid/cwd" 2>/dev/null || true)"
  if [[ "$kind" == backend ]]; then
    [[ "$cwd" == "$backend_root" ]]
  else
    [[ "$cwd" == "$frontend_root" ]]
  fi
}

service_command_matches() {
  local kind="$1"
  local pid="$2"
  local command_line
  command_line="$(tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null || true)"
  if [[ "$kind" == backend ]]; then
    [[ "$command_line" == *"$backend_uvicorn"* ]] &&
      [[ "$command_line" == *'app.main:app'* ]] &&
      [[ "$command_line" == *"--port $backend_port"* ]]
  else
    [[ "$command_line" == *'npm'* ]] &&
      [[ "$command_line" == *'run dev'* ]] &&
      [[ "$command_line" == *"--port $frontend_port"* ]]
  fi
}

metadata_matches_process() {
  local meta_path="$1"
  local kind="$2"
  [[ -f "$meta_path" ]] || return 1
  local pid pgid start_ticks current_pgid current_ticks own_pgid
  pid="$(meta_value "$meta_path" pid)"
  pgid="$(meta_value "$meta_path" pgid)"
  start_ticks="$(meta_value "$meta_path" start_ticks)"
  [[ "$pid" =~ ^[0-9]+$ && "$pgid" =~ ^[0-9]+$ && "$start_ticks" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  current_pgid="$(ps -o pgid= -p "$pid" | tr -d ' ')"
  current_ticks="$(proc_start_ticks "$pid")"
  own_pgid="$(ps -o pgid= -p $$ | tr -d ' ')"
  [[ "$current_pgid" == "$pgid" && "$pgid" != "$own_pgid" ]] || return 1
  [[ "$current_ticks" == "$start_ticks" ]] || return 1
  service_cwd_matches "$kind" "$pid" || return 1
  service_command_matches "$kind" "$pid" || return 1
}

write_metadata() {
  local path="$1"
  local kind="$2"
  local pid="$3"
  local pgid="$4"
  local start_ticks="$5"
  local temporary="$path.$$"
  {
    printf 'kind=%s\n' "$kind"
    printf 'pid=%s\n' "$pid"
    printf 'pgid=%s\n' "$pgid"
    printf 'start_ticks=%s\n' "$start_ticks"
    printf 'project_root=%s\n' "$project_root"
    printf 'port=%s\n' "$([[ "$kind" == backend ]] && printf '%s' "$backend_port" || printf '%s' "$frontend_port")"
  } >"$temporary"
  mv -f -- "$temporary" "$path"
}

record_process() {
  local path="$1"
  local kind="$2"
  local pid="$3"
  local pgid start_ticks
  for _ in $(seq 1 40); do
    if kill -0 "$pid" 2>/dev/null; then
      pgid="$(ps -o pgid= -p "$pid" | tr -d ' ')"
      start_ticks="$(proc_start_ticks "$pid" || true)"
      if [[ "$pgid" =~ ^[0-9]+$ && "$start_ticks" =~ ^[0-9]+$ ]]; then
        write_metadata "$path" "$kind" "$pid" "$pgid" "$start_ticks"
        return 0
      fi
    fi
    sleep 0.05
  done
  return 1
}

stop_metadata() {
  local meta_path="$1"
  local kind="$2"
  local pid pgid
  pid="$(meta_value "$meta_path" pid)"
  pgid="$(meta_value "$meta_path" pgid)"
  if ! metadata_matches_process "$meta_path" "$kind"; then
    if ! [[ "$pid" =~ ^[0-9]+$ ]] || kill -0 "$pid" 2>/dev/null; then
      return 1
    fi
    rm -f -- "$meta_path"
    return 0
  fi
  kill -TERM -- "-$pgid" 2>/dev/null || true
  for _ in $(seq 1 40); do
    if ! kill -0 "$pid" 2>/dev/null; then
      rm -f -- "$meta_path"
      return 0
    fi
    sleep 0.05
  done
  if metadata_matches_process "$meta_path" "$kind"; then
    kill -KILL -- "-$pgid" 2>/dev/null || true
  fi
  rm -f -- "$meta_path"
}

prepare_record() {
  local meta_path="$1"
  local kind="$2"
  if [[ ! -f "$meta_path" ]]; then
    return 0
  fi
  if metadata_matches_process "$meta_path" "$kind"; then
    return 2
  fi
  local pid
  pid="$(meta_value "$meta_path" pid)"
  if [[ "$pid" =~ ^[0-9]+$ ]] && ! kill -0 "$pid" 2>/dev/null; then
    rm -f -- "$meta_path"
    return 0
  fi
  die "$kind 的 PID 记录与当前进程身份不一致，拒绝接管：$meta_path"
}

port_in_use() {
  local listeners
  listeners="$(ss -H -ltnp "sport = :$1" 2>&1)" || die '无法安全检查本机端口状态。'
  [[ "$listeners" != *'Cannot open netlink socket'* ]] || die '无法安全检查本机端口状态。'
  [[ -n "$listeners" ]]
}

listening_pid() {
  local listeners
  listeners="$(ss -H -ltnp "sport = :$1" 2>&1)" || return 1
  [[ "$listeners" != *'Cannot open netlink socket'* ]] || return 1
  sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' <<<"$listeners" | head -1
}

external_process_matches() {
  local kind="$1"
  local port="$2"
  local pid command_line cwd
  pid="$(listening_pid "$port" || true)"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  cwd="$(readlink "/proc/$pid/cwd" 2>/dev/null || true)"
  command_line="$(tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null || true)"
  if [[ "$kind" == backend ]]; then
    [[ "$cwd" == "$backend_root" ]] &&
      [[ "$command_line" == *"$backend_uvicorn"* ]] &&
      [[ "$command_line" == *'app.main:app'* ]] &&
      [[ "$command_line" == *"--port $backend_port"* ]]
  else
    [[ "$cwd" == "$frontend_root" ]] &&
      [[ "$command_line" == *"$frontend_root/node_modules/.bin/vite"* ]] &&
      [[ "$command_line" == *"--port $frontend_port"* ]]
  fi
}

external_backend_healthy() {
  local body
  body="$(curl --noproxy '*' --fail --silent --show-error "http://$backend_host:$backend_port/healthz" || true)"
  [[ "$body" == *'"status":"ok"'* && "$body" == *"\"version\":\"$application_version\""* ]]
}

external_frontend_healthy() {
  curl --noproxy '*' --fail --silent --show-error "http://$frontend_host:$frontend_port/" >/dev/null 2>&1 &&
    curl --noproxy '*' --fail --silent --show-error "http://$frontend_host:$frontend_port/healthz" >/dev/null 2>&1
}

wait_for_http() {
  local label="$1"
  local url="$2"
  local pid="$3"
  local log_path="$4"
  for _ in $(seq 1 100); do
    if curl --noproxy '*' --fail --silent --show-error "$url" >/dev/null 2>&1; then
      printf '%s 已就绪：%s\n' "$label" "$url"
      return 0
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
      printf '%s 启动日志：\n' "$label" >&2
      tail -40 "$log_path" >&2 || true
      return 1
    fi
    sleep 0.1
  done
  printf '%s 启动超时，日志：\n' "$label" >&2
  tail -40 "$log_path" >&2 || true
  return 1
}

if [[ "${1:-}" == '--check' ]]; then
  printf 'DayFlow 启动前检查通过。\n'
  exit 0
fi
[[ $# -eq 0 ]] || die '用法：dayflow-start.sh [--check]'

backend_state=0
frontend_state=0
prepare_record "$backend_meta" backend || backend_state=$?
prepare_record "$frontend_meta" frontend || frontend_state=$?
if [[ "$backend_state" -eq 2 && "$frontend_state" -eq 2 ]]; then
  printf 'DayFlow 已在运行。\nFrontend: http://%s:%s\nBackend:  http://%s:%s\n' \
    "$frontend_host" "$frontend_port" "$backend_host" "$backend_port"
  exit 0
fi
[[ "$backend_state" -ne 2 ]] || stop_metadata "$backend_meta" backend || die '无法安全停止残留 Backend。'
[[ "$frontend_state" -ne 2 ]] || stop_metadata "$frontend_meta" frontend || die '无法安全停止残留 Frontend。'

external_backend=0
external_frontend=0
if port_in_use "$backend_port"; then
  if external_process_matches backend "$backend_port" && external_backend_healthy; then
    external_backend=1
  else
    die "Backend 端口 $backend_port 已被未知进程占用。"
  fi
fi
if port_in_use "$frontend_port"; then
  if external_process_matches frontend "$frontend_port" && external_frontend_healthy; then
    external_frontend=1
  else
    die "Frontend 端口 $frontend_port 已被未知进程占用。"
  fi
fi
if [[ "$external_backend" -eq 1 || "$external_frontend" -eq 1 ]]; then
  if [[ "$external_backend" -eq 1 && "$external_frontend" -eq 1 ]]; then
    printf 'DayFlow 已在运行（由其他启动方式管理），不会重复启动。\nFrontend: http://%s:%s\nBackend:  http://%s:%s\n' \
      "$frontend_host" "$frontend_port" "$backend_host" "$backend_port"
    exit 0
  fi
  die '检测到部分 DayFlow 服务正在运行；为避免接管未知进程，未启动或停止任何服务。'
fi

DAYFLOW_BACKEND_ROOT="$backend_root" \
DAYFLOW_UVICORN="$backend_uvicorn" \
DAYFLOW_DATABASE_PATH="$database_path" \
DAYFLOW_BACKEND_HOST="$backend_host" \
DAYFLOW_BACKEND_PORT="$backend_port" \
  nohup setsid bash -c 'cd "$DAYFLOW_BACKEND_ROOT"; exec env DAYFLOW_DATABASE_PATH="$DAYFLOW_DATABASE_PATH" "$DAYFLOW_UVICORN" app.main:app --host "$DAYFLOW_BACKEND_HOST" --port "$DAYFLOW_BACKEND_PORT"' \
  >"$backend_log" 2>&1 < /dev/null 9>&- &
backend_pid=$!
record_process "$backend_meta" backend "$backend_pid" || die '无法记录 Backend 进程身份。'

DAYFLOW_FRONTEND_ROOT="$frontend_root" \
DAYFLOW_NPM_BIN="$npm_bin" \
DAYFLOW_BACKEND_ORIGIN="http://$backend_host:$backend_port" \
DAYFLOW_FRONTEND_HOST="$frontend_host" \
DAYFLOW_FRONTEND_PORT="$frontend_port" \
PATH="$PATH" \
  nohup setsid bash -c 'cd "$DAYFLOW_FRONTEND_ROOT"; exec env DAYFLOW_BACKEND_ORIGIN="$DAYFLOW_BACKEND_ORIGIN" "$DAYFLOW_NPM_BIN" run dev -- --host "$DAYFLOW_FRONTEND_HOST" --port "$DAYFLOW_FRONTEND_PORT"' \
  >"$frontend_log" 2>&1 < /dev/null 9>&- &
frontend_pid=$!
record_process "$frontend_meta" frontend "$frontend_pid" || {
  stop_metadata "$backend_meta" backend || true
  die '无法记录 Frontend 进程身份。'
}

if ! wait_for_http Backend "http://$backend_host:$backend_port/healthz" "$backend_pid" "$backend_log"; then
  stop_metadata "$frontend_meta" frontend || true
  stop_metadata "$backend_meta" backend || true
  die 'Backend 未能就绪。'
fi
if ! external_backend_healthy; then
  stop_metadata "$frontend_meta" frontend || true
  stop_metadata "$backend_meta" backend || true
  die 'Backend 健康状态或应用版本与项目元数据不一致。'
fi
if ! wait_for_http Frontend "http://$frontend_host:$frontend_port/" "$frontend_pid" "$frontend_log"; then
  stop_metadata "$frontend_meta" frontend || true
  stop_metadata "$backend_meta" backend || true
  die 'Frontend 未能就绪。'
fi
if ! curl --noproxy '*' --fail --silent --show-error "http://$frontend_host:$frontend_port/healthz" >/dev/null; then
  stop_metadata "$frontend_meta" frontend || true
  stop_metadata "$backend_meta" backend || true
  die 'Vite Proxy /healthz 未能就绪。'
fi

printf 'DayFlow 已启动。\nFrontend: http://%s:%s\nBackend:  http://%s:%s\n' \
  "$frontend_host" "$frontend_port" "$backend_host" "$backend_port"
