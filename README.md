# DayFlow Personal

DayFlow Personal is a local-first, single-user productivity application.

## Current Version

V0.2 — Inbox, Task organization, and Search development on the stable V0.1.0 foundation.

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

V0.2 keeps the V0.1 API paths and behavior compatible. The `v0.2.0` release tag
waits for human acceptance.

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

The real SQLite file is created and upgraded by Alembic. Runtime code does not
call `Base.metadata.create_all()`. Before applying the V0.2 migration to real
data, stop the Backend, create a verified backup, and validate the migration on
a copy of the V0.1 database first.

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
