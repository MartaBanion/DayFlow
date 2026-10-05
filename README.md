# DayFlow Personal

DayFlow Personal is a local-first, single-user productivity application.

## Current Version

**Stable release: v0.8.0 — Task Organization at Scale.** The current DayFlow
application version is `0.8.0`. The annotated `v0.8.0` tag points to release
Commit `6bbd452dcee8fbc793e1c66deba2b986eac3197c`. V0.8 Phases 0–3 are
complete and released. Phase 0 is committed as
`97e118a0d546f57fcee7a9dd6ae53f6f0010db80`, Phase 1 as
`82691ac61bbce3cf745de2cfd5904f7619c1a642`, and Phase 2 as
`60a1dacbf1d044054a26da1e4556e6c2270de9cf`; Phase 3 Full Acceptance added no
code commit. Current development is V0.9 Planning Flow Refinement; Phases 0–2
and Full Acceptance are complete, the Month empty-date blocker is fixed, and
the release status is Ready for V0.9.0 Release Preparation. V0.9.0 is not
released. The real database schema remains
`0005_add_deadlines_recurrence_reminders`, with no new migration.

V0.6 adds the 数据与备份 maintenance view, consistent Backup Create/List/Verify,
Restore Dry Run, isolated Restore safety and recovery coordination, and visible
Reminder polling failure with Retry and automatic recovery. Real DayFlow
database Restore remains disabled; only isolated temporary-database Restore has
been verified.

## V0.6 Data Safety & Recovery

- Maintenance view for Backup status, Create, List, and Verify.
- Read-only Restore planning and isolated Restore safety workflows.
- Reminder poll failure visibility, Retry, and automatic recovery.
- No real project-database Restore authorization; storage qualification remains
  `NOT QUALIFIED`.

## V0.7 Daily & Weekly Review

V0.7 has one product theme: Daily & Weekly Review. The released `#review`
view presents current-state completed Tasks, current overdue and carryover work,
and Project snapshots for Today and This Week. It is a read-only, list-first
review flow rather than a Statistics Dashboard. Phases 0–3 are complete and
V0.7 requires no database Migration. `completed_at_utc` remains the latest
retained completion state, not immutable activity history.

## V0.8 Task Organization at Scale

V0.8.0 is released. The theme is Search / Filter / Sort with Project reuse. The
release scope is intentionally small: extend the existing
`/api/v1/tasks` query with
current-status, Overdue, planned-date bucket, and limited stable-sort controls;
reuse those controls in Project Detail with a fixed `project_id`; and make
Search mode visibly distinct from Inbox mode. All filters use AND semantics,
soft-deleted Tasks remain excluded, and the response remains the existing
`TaskRead[]` list with no pagination.

V0.8 requires no database migration and does not create `0006`. It does not
include a query language, Saved Views, grouping, Kanban, Batch Edit, Activity
History, Dashboard/Charts, or Backup/Restore/Recovery work. Inbox Quick Project
and Quick Priority remain DEFERRED. V0.9 planning work is frozen separately.

## V0.9 Planning Flow Refinement

V0.9 is frozen around Quick Reschedule + Lightweight Month Drill-down. The
core scope is:

- Quick Reschedule for pending Tasks: Today, Tomorrow, Next Monday, Move to
  Inbox, and Choose Date.
- The same action from Today and Calendar, using the existing versioned Task
  PATCH and conflict confirmation.
- Month date click, including the “还有 N 项” overflow action, switches to the
  existing Day View.

Quick Reschedule changes `planned_date` only. Move to Inbox also clears the
Time Block with `schedule: null`. Deadline, Reminder, recurrence rule,
occurrence date, and future occurrences remain unchanged. DayFlow runtime
`local_date` is the only preset basis; no new API, dependency, migration, or
`0006` is required. Inbox Quick Project and Quick Priority remain DEFERRED.
V0.9 Full Acceptance is PASS, including the Month empty-date → existing Day
View regression; the next step is Release Preparation.

## V0.1 Features

- Create, read, and edit Tasks.
- Complete and restore Tasks.
- Soft-delete Tasks with an Undo restore action.
- View Tasks planned for Today.
- Show explicit Today loading, loaded, and error states with Retry.
- Persist data in SQLite across Backend restarts.

The V0.1 UI is Today-first and desktop-first. The backend exposes the complete
minimal Task lifecycle under `/api/v1` and uses optimistic `version` checks for
mutations.

## V0.2 Features

- Inbox represented by active Tasks with `planned_date = null`.
- Low/normal/high Priority with a normal default.
- User-defined Categories and normalized many-to-many Tags.
- Create, rename, and delete Category and Tag metadata from the Today or Inbox UI.
- Title/description Search with structured Priority, Category, and Tag filters.
- SQLite Foreign Key enforcement on every SQLAlchemy connection.

V0.2 keeps the V0.1 API paths and behavior compatible. The `v0.2.0` and
`v0.2.1` release tags are local stable checkpoints. V0.3 adds the Hash-based
Calendar frontend, Day/Week/Month views, Task Editor Time Blocking, Calendar
range API, Runtime API, timezone/DST validation, and conflict detection. The
real database was later upgraded to `0004_add_projects` for V0.4.

V0.1 deliberately excluded Projects, Priority, Category, Tags, Reminders,
Recurrence, Calendar, AI, and ScheduleBlock.

V0.3 adds Calendar, Day/Week/Month views, date-only Tasks, and one optional
Time Block per Task. V0.3 does not include Drag & Drop, Resize, cross-day Time
Blocks, Repeat, Projects, Reminders, AI Scheduling, or external Calendar
integration.

## V0.4 Features

- Project CRUD with Hash-based Project list and detail views.
- Project assignment and clearing from Task Editor and existing Task views.
- Project progress, complete/reopen, soft delete, and restore.
- Project-aware Search filtering with existing Today, Inbox, and Calendar flows.
- Migration `0004_add_projects`, temporary-database validation, and real-data
  migration acceptance.

## V0.5 Features

- Date-only and timed Deadlines with saved timezone and DST validation.
- Daily, selected-weekday, and monthly (1–28) Repeat rules with explicit
  materialization, skip, stop, and preserved occurrence history.
- Specified-time Reminders with pending, acknowledged, and dismissed states.
- Read-only due polling and browser-session dialog deduplication.
- No real-time Reminder guarantee while the Backend is stopped.

## Technology

- Vue 3 + TypeScript + Vite + Element Plus
- Python 3.12 + FastAPI + Pydantic
- Synchronous SQLAlchemy 2.x
- SQLite + Alembic

## Runtime Data

The real database is stored at:

```text
data/dayflow.sqlite3
```

It is excluded from Git. The V0.1 implementation did not provide an automated
Backup Service or Restore UI; V0.6 provides the controlled maintenance view.
Use 数据与备份 for Backup Create/List/Verify. Backup creation uses SQLite's
Online Backup API and handles committed WAL data; do not directly copy an
active database file. Real project-database Restore remains disabled.

## Development Setup

Use Python 3.12 and Node.js 24 LTS. Install `uv`, then run:

```bash
uv sync --directory backend
npm ci --prefix frontend
# Only point this at a new or temporary database, never the real personal DB.
DAYFLOW_DATABASE_PATH=/tmp/dayflow-development.sqlite3 uv run --directory backend alembic upgrade head
```

The real SQLite file is managed by Alembic and is currently at
`0005_add_deadlines_recurrence_reminders`. Runtime code does not call `Base.metadata.create_all()`.
Before applying any future migration to real data, stop the Backend, create a
verified backup, and validate the migration on a copy of the current database
first.

## Run

Backend:

```bash
DAYFLOW_DATABASE_PATH=/tmp/dayflow-development.sqlite3 uv run --directory backend uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The development command above uses the temporary database initialized by the
setup command. Use isolated temporary databases for tests and migration
rehearsals; reserve `data/dayflow.sqlite3` for normal personal use.

Frontend:

```bash
npm run dev --prefix frontend
```

### WSL 日常启动与停止

在 WSL 项目根目录执行：

```bash
./scripts/dayflow-start.sh
```

启动脚本会检查 Node.js 24 LTS、Backend 虚拟环境、Frontend 依赖、端口和
真实数据库版本（`0005_add_deadlines_recurrence_reminders`），并从项目元数据
读取应用版本、验证 Backend 健康接口版本一致。不会自动执行 Migration，也不会创建
测试数据。启动成功后，在浏览器访问 `http://127.0.0.1:5173`；Backend 地址为
`http://127.0.0.1:8000`。

停止由启动脚本创建的服务：

```bash
./scripts/dayflow-stop.sh
```

停止脚本只会终止已记录且身份校验通过的 DayFlow Backend/Frontend 进程；遇到
PID 复用或未知进程时会拒绝操作。

Node.js 由 WSL 用户级 nvm 管理，启动脚本会从 nvm 默认版本加载 Node.js，
不会依赖临时目录中的 Node 安装，也不会修改系统 Node.js。

## Test

```bash
uv run --directory backend pytest
npm run test --prefix frontend
```

Tests use isolated temporary databases and must never access `data/dayflow.sqlite3`.
When running inside a restricted Codex sandbox, backend tests that exercise
synchronous FastAPI routes may need one-time elevated execution because the
sandbox can block cross-thread asyncio wakeups. This is an execution-environment
limitation, not a dependency downgrade requirement.

Browser E2E acceptance tests use a fresh temporary SQLite database for each
run. The runner refuses the real database and runs Alembic before starting a
test-only Backend on `127.0.0.1:18000` and Vite on `127.0.0.1:15173`:

```bash
npm run test:e2e --prefix frontend
npm run test:e2e:ui --prefix frontend
```

Install only the Playwright Chromium browser before the first run:

```bash
npm exec --prefix frontend playwright install chromium
```

The UI mode is optional and is not a release gate in headless-only
environments. Browser reports and test results are ignored by Git.

## Troubleshooting

- `database is locked`: stop the Backend before manually copying or inspecting
  the real database, and avoid running two writers against it.
- Frontend shows an API error: start the Backend on `127.0.0.1:8000` before the
  Vite development server.
- Do not copy `.env`, `data/dayflow.sqlite3`, backups, `.venv`, or
  `frontend/node_modules` into Git.
