# DayFlow Personal

DayFlow Personal is a local-first, single-user productivity application.

## Current Version

V0.1 — minimal Task management and Today view.

## V0.1 Features

- Create, read, and edit Tasks.
- Complete and restore Tasks.
- Soft-delete Tasks.
- View Tasks planned for Today.
- Persist data in SQLite across Backend restarts.

The V0.1 UI is Today-first and desktop-first. The backend exposes the complete
minimal Task lifecycle under `/api/v1` and uses optimistic `version` checks for
mutations.

V0.1 deliberately excludes Projects, Priority, Category, Tags, Reminders, Recurrence, Calendar, AI, and ScheduleBlock.

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

For a manual backup, stop the Backend first, then copy `data/dayflow.sqlite3` to a location outside the repository with a timestamped name. Do not copy the database while the Backend is writing to it.

## Development Setup

Use Python 3.12 and Node.js 24 LTS. Install `uv`, then run:

```bash
uv sync --directory backend
npm ci --prefix frontend
uv run --directory backend alembic upgrade head
```

The real SQLite file is created by the Alembic command. Runtime code does not
call `Base.metadata.create_all()`.

## Run

Backend:

```bash
uv run --directory backend uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```bash
npm run dev --prefix frontend
```

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

## Troubleshooting

- `database is locked`: stop the Backend before manually copying or inspecting
  the real database, and avoid running two writers against it.
- Frontend shows an API error: start the Backend on `127.0.0.1:8000` before the
  Vite development server.
- Do not copy `.env`, `data/dayflow.sqlite3`, backups, `.venv`, or
  `frontend/node_modules` into Git.
