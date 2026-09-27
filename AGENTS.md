# DayFlow Personal — Long-Term Development Rules

## Project Identity

DayFlow Personal is a local-first, single-user productivity application for reliable Task management and future time planning.

## Current Version

V0.3 Phase 1: Backend Task scheduling model, Migration 0003, timezone/DST
validation, Calendar range API, conflict detection, and Runtime API. Calendar
Frontend implementation has not started. The real database remains at
`0002_add_priority_categories_tags` until explicit migration approval.

Only the version currently being implemented may be changed. Do not start later roadmap versions early.

## Tech Stack

- Frontend: Vue 3, TypeScript, Vite, Element Plus.
- Backend: Python 3.12, FastAPI, Pydantic, synchronous SQLAlchemy 2.x.
- Database: SQLite.
- Migration: Alembic.
- Python dependencies: `pyproject.toml` and `uv.lock`.
- Frontend dependencies: `package.json` and `package-lock.json`.

## Directory Rules

- `frontend/`: browser application only.
- `backend/`: API, domain services, database layer, migrations, and tests.
- `data/`: local runtime data only; never commit real personal data.
- `docs/`: maintain only core architecture, database, and API documentation.
- Keep modules small and avoid creating directories without a current use.

## Coding Rules

- Prefer the smallest clear change that satisfies the current requirement.
- Keep HTTP routing, business services, and database access separate.
- Use typed Python and TypeScript interfaces for API data.
- Do not silently swallow exceptions.
- Validate input at the API boundary and enforce business rules in services.
- Do not introduce future-version fields or abstractions without a current V0.3
  Phase 1 need.
- DayFlow's default user language is Simplified Chinese. User-visible UI copy should use Simplified Chinese; code, APIs, database schema, and internal enum values remain in English. Do not introduce a full internationalization system at this stage.

## Testing Rules

- Tests must never open, delete, modify, or migrate the real personal database.
- Every test uses an isolated temporary database.
- Test migration setup before testing database behavior.
- Run relevant tests and regression tests after changes.
- Do not ignore newly failing existing tests.
- Browser E2E runs must use the fail-closed temporary database runner and must
  never fall back to `data/dayflow.sqlite3` or any file under `data/backups/`.
- Browser E2E uses the dedicated local ports `18000` and `15173`, headless
  Chromium by default, and keeps workers at one while SQLite is under test.

## Git Rules

- Use the local `main` branch.
- Inspect `git status` and `git diff` before commits.
- Never commit `.env`, secrets, SQLite data, backups, virtual environments, `node_modules`, or test data.
- No remote, GitHub repository, Push, or Tag without explicit instruction.
- Do not use `git reset --hard`, `git clean -fd`, force push, or history rewriting.

## Database Rules

- Real database path: `data/dayflow.sqlite3`.
- SQLite data is not source code and must not enter Git.
- V0.2 Task organization and V0.3 schedule fields must be added only through
  Alembic.
- The real database must remain at its approved migration until a verified
  temporary-copy migration and explicit approval are complete.
- Database writes go through services and transactions.
- Do not use `Base.metadata.create_all()` in application runtime.

## Migration Rules

- Every schema change requires an Alembic migration.
- Never delete and recreate the real database to apply a schema change.
- Review migration SQL and test Upgrade from a clean database.
- Test data compatibility before applying a migration to real data.

## Change Safety Rules

1. Read related code and tests before changing them.
2. Make the smallest necessary change.
3. Do not refactor unrelated modules.
4. Do not silently change stable API behavior.
5. Do not change database schema outside Alembic.
6. Do not upgrade major dependencies as part of ordinary feature work.
7. Use transactions and rollback for multi-step writes.
8. Keep tests completely separate from real personal data.
9. Report architecture problems before making a major redesign.
10. Do not silently swallow errors.
11. Do not expand scope for opportunistic optimization.

## Prohibited Actions

- No Calendar Frontend, Day/Week/Month UI, Drag & Drop, Resize, Project,
  Reminder, Recurrence, AI, external Calendar, PWA, Authentication, Docker,
  CI/CD, or remote Git work during V0.3 Phase 1.
- No modification of protected workspace mounts to bypass a safety boundary.

## Definition of Done

A V0.3 Phase 1 change is complete only when the Backend runs, the temporary
V0.2.1 database copy is migrated and verified, schedule/DST/conflict tests and
V0.1/V0.2 regression tests pass, no secrets or personal data are exposed,
documentation is updated, and the real database remains unchanged until
explicit approval. Calendar Frontend work is a later phase.
