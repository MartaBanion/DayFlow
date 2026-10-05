# DayFlow Personal — Long-Term Development Rules

## Project Identity

DayFlow Personal is a local-first, single-user productivity application for reliable Task management and future time planning.

## Current Version

Published stable release: `v0.7.0` — Daily & Weekly Review; its annotated tag
points to release Commit
`b632f10dbc9cde7da04083a60ef758dea648b594`. Current development is V0.8 Task
Organization at Scale. Phase 0 Product / Architecture Freeze, Phase 1 Task
Query Core, Phase 2 Search / Project UI Integration, and Phase 3 Full
Acceptance are complete. Phase 1 is committed as
`82691ac61bbce3cf745de2cfd5904f7619c1a642`, following the Phase 0 freeze
commit `97e118a0d546f57fcee7a9dd6ae53f6f0010db80`; Phase 2 is committed as
`60a1dacbf1d044054a26da1e4556e6c2270de9cf`. Phase 3 acceptance adds no code
commit. Application Version is `0.8.0`; current status is V0.8.0 Release
Preparation, and v0.8.0 is not released. The real database schema remains
`0005_add_deadlines_recurrence_reminders`.

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
- Do not introduce future-version fields or abstractions without a current approved-version
  need.
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
- The real database must remain at its currently approved migration until a
  verified temporary-copy migration and explicit approval are complete. The
  currently approved real-data migration is `0005_add_deadlines_recurrence_reminders`.
- Database writes go through services and transactions.
- Do not use `Base.metadata.create_all()` in application runtime.

## V0.6 Data Safety Boundary

- V0.6.0 Data Safety & Recovery implementation Phases 1–5 are complete,
  accepted, committed, tagged, and formally released.
- NO DATABASE MIGRATION REQUIRED: keep schema `0005_add_deadlines_recurrence_reminders`;
  do not create `0006` or change Task/Project/Deadline/Recurrence/Reminder semantics.
- Use SQLite Online Backup API, including committed WAL data; never assume copying
  an active database's main file produces a consistent backup.
- Restore is offline Maintenance CLI only. The running Backend must not replace
  its active database through an HTTP endpoint.
- Isolated Restore execution is implemented and tested only for independent
  system-temporary databases. Real project-database Restore remains prohibited;
  the current real-data storage qualification is `NOT QUALIFIED`.
- Destructive tests and all development Restore operations use isolated temporary
  databases. Real Restore requires separate explicit approval. Compare the real
  database SHA-256 before and after automated tests.
- Maintenance CLI, start script, and Backend startup must coordinate database
  usage/maintenance locks and refuse startup after an incomplete Restore.
- Restore failures must preserve original DB/WAL/SHM material, safety and target
  backups, candidate, and operation log. No automatic rollback or downgrade.
- Keep Backup Metadata, Restore logs, and maintenance state in controlled,
  Git-ignored filesystem locations. Never log personal Task contents or secrets.
- V0.6 ancillary work was limited to Reminder poll failure visibility/Retry.
  The released data-safety behavior must not be expanded during V0.7.

## V0.7 Development Safety

- V0.7 has one theme: Daily & Weekly Review. Do not expand it into a Dashboard,
  Statistics system, Task Organization project, or unrelated UI redesign.
- Review is a read-only current-state view. It must never materialize recurrence,
  mutate Tasks/Projects/Reminders, write snapshots or caches, or update a
  last-viewed timestamp.
- `completed_at_utc` is the latest retained completion timestamp for a Task,
  not immutable event history. Never use `updated_at_utc` as a completion time.
- Daily and Monday-based weekly boundaries use the configured DayFlow IANA
  timezone and are converted independently to UTC half-open ranges.
- NO DATABASE MIGRATION REQUIRED: retain
  `0005_add_deadlines_recurrence_reminders`; do not create `0006`. If immutable
  history becomes necessary, stop and request a new product decision.
- V0.8 Task Organization, advanced Search, bulk Inbox work, quick defer,
  Backup/Restore/Recovery changes, and real Restore remain outside V0.7.

## V0.8 Development Safety

- V0.8 has one theme: Task Organization at Scale — Search / Filter / Sort with
  Project reuse. Do not expand it into a Dashboard, Statistics system,
  Activity History, Kanban, Subtasks, Saved Views, Batch Edit, AI, or unrelated
  UI redesign.
- Extend the existing `GET /api/v1/tasks` contract rather than creating a
  second Search API. Preserve `TaskRead[]`, backward-compatible defaults,
  soft-delete exclusion, and AND semantics across filters.
- The frozen query inputs are `status`, `overdue`, `planned_bucket`, and
  `sort`, alongside the existing text, Priority, Category, Tag, Project, and
  Inbox filters. Project Detail reuses the same query with a fixed
  `project_id`.
- Every Task-list request uses one explicit `generated_at_utc` for Overdue and
  DayFlow-timezone planned buckets. Overdue must reuse the canonical Deadline
  evaluator; the response must not disagree with the filter at a boundary.
- NO DATABASE MIGRATION REQUIRED: retain
  `0005_add_deadlines_recurrence_reminders`; do not create `0006`, new tables,
  columns, or indexes without a new product decision. V0.8 has no pagination
  until measured data justifies revisiting that decision.
- Inbox Quick Project and Quick Priority are optional Should Have work, not a
  release gate. Quick Postpone and Move Tomorrow/Next Week remain V0.9 scope.
  Review, Calendar, Backup, Restore, Recovery, and Storage Qualification stay
  on their existing boundaries.

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

- No Drag & Drop, Resize, AI, external Calendar, PWA,
  Authentication, Docker, CI/CD, or remote Git work during V0.8 development.
- No modification of protected workspace mounts to bypass a safety boundary.

## Definition of Done

A V0.7 implementation is complete when `#review` reliably answers what was
completed today and this week, what is currently overdue, what planned work is
carried over, and the current Project snapshot; Task and Project navigation
works; Review remains read-only; isolated tests and full regression pass; no
Migration is added; documentation is synchronized; and the approved real
database is read-only verified at `0005_add_deadlines_recurrence_reminders`.
