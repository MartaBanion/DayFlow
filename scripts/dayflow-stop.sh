#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd -- "$script_dir/.." && pwd)"
backend_root="$project_root/backend"
frontend_root="$project_root/frontend"
backend_port="${DAYFLOW_BACKEND_PORT:-8000}"
frontend_port="${DAYFLOW_FRONTEND_PORT:-5173}"
state_root="${DAYFLOW_STATE_DIR:-${XDG_STATE_HOME:-${HOME}/.local/state}/dayflow}"
lock_path="$state_root/lock"
backend_meta="$state_root/backend.meta"
frontend_meta="$state_root/frontend.meta"

die() {
  printf 'DayFlow 停止失败：%s\n' "$1" >&2
  exit 1
}

command -v flock >/dev/null 2>&1 || die '缺少命令：flock'
command -v ps >/dev/null 2>&1 || die '缺少命令：ps'
command -v readlink >/dev/null 2>&1 || die '缺少命令：readlink'
mkdir -p "$state_root"
exec 9>"$lock_path"
flock -n 9 || die '已有另一个 DayFlow 启停操作正在进行。'

meta_value() {
  local path="$1"
  local key="$2"
  awk -F= -v wanted="$key" '$1 == wanted {print substr($0, index($0, "=") + 1); exit}' "$path"
}

proc_start_ticks() {
  local pid="$1"
  [[ -r "/proc/$pid/stat" ]] || return 1
  awk '{sub(/^.*\) /, ""); print $20}' "/proc/$pid/stat"
}

metadata_matches_process() {
  local meta_path="$1"
  local kind="$2"
  [[ -f "$meta_path" ]] || return 1
  local pid pgid start_ticks current_pgid current_ticks own_pgid cwd command_line expected_root expected_port
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
  cwd="$(readlink "/proc/$pid/cwd" 2>/dev/null || true)"
  command_line="$(tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null || true)"
  if [[ "$kind" == backend ]]; then
    expected_root="$backend_root"
    expected_port="$backend_port"
    [[ "$cwd" == "$expected_root" ]] || return 1
    [[ "$command_line" == *"$expected_root/.venv/bin/uvicorn"* ]] || return 1
    [[ "$command_line" == *'app.main:app'* && "$command_line" == *"--port $expected_port"* ]] || return 1
  else
    expected_root="$frontend_root"
    expected_port="$frontend_port"
    [[ "$cwd" == "$expected_root" ]] || return 1
    [[ "$command_line" == *'npm'* && "$command_line" == *'run dev'* && "$command_line" == *"--port $expected_port"* ]] || return 1
  fi
}

validate_all_records() {
  local invalid=0
  if [[ -f "$backend_meta" ]] && ! metadata_matches_process "$backend_meta" backend; then
    printf '拒绝停止：Backend PID 记录身份不一致或已失效：%s\n' "$backend_meta" >&2
    invalid=1
  fi
  if [[ -f "$frontend_meta" ]] && ! metadata_matches_process "$frontend_meta" frontend; then
    printf '拒绝停止：Frontend PID 记录身份不一致或已失效：%s\n' "$frontend_meta" >&2
    invalid=1
  fi
  (( invalid == 0 )) || exit 1
}

stop_record() {
  local meta_path="$1"
  local kind="$2"
  [[ -f "$meta_path" ]] || return 0
  local pid pgid
  pid="$(meta_value "$meta_path" pid)"
  pgid="$(meta_value "$meta_path" pgid)"
  [[ "$pid" =~ ^[0-9]+$ && "$pgid" =~ ^[0-9]+$ ]] || die "无效的 $kind PID 记录。"
  kill -TERM -- "-$pgid" 2>/dev/null || true
  for _ in $(seq 1 40); do
    if ! kill -0 "$pid" 2>/dev/null; then
      rm -f -- "$meta_path"
      printf '%s 已停止。\n' "$kind"
      return 0
    fi
    sleep 0.05
  done
  if metadata_matches_process "$meta_path" "$kind"; then
    kill -KILL -- "-$pgid" 2>/dev/null || true
  fi
  rm -f -- "$meta_path"
  printf '%s 已停止。\n' "$kind"
}

validate_all_records
stop_record "$frontend_meta" Frontend
stop_record "$backend_meta" Backend
if [[ ! -f "$frontend_meta" && ! -f "$backend_meta" ]]; then
  printf '%s\n' 'DayFlow 已停止，未扫描或终止其他进程。'
fi
