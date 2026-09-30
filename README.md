# DayFlow Personal

DayFlow Personal is a local-first, single-user productivity application.

## Current Version

**Current application version: v0.5.0.** Deadlines, Repeat Tasks, and Reminders
are implemented in both Backend and Frontend. Final acceptance and database
verification passed; the real database schema is
`0005_add_deadlines_recurrence_reminders`. Release status is confirmed by Git
tags. V0.6 is the next planned development version.

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

It is excluded from Git. V0.1 does not provide an automated Backup Service or Restore UI.

For a manual backup, stop the Backend first, then create a timestamped backup
with SQLite's Online Backup API or copy `data/dayflow.sqlite3` to a location
outside the repository. Do not copy the database while the Backend is writing
to it. DayFlow still has no automatic Backup Service or Restore UI.

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
