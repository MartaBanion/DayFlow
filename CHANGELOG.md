# Changelog

## [0.1.0] - 2026-09-26

### Added

- Task CRUD with optimistic version checks, complete/restore, and soft delete with
  a user-facing Undo action.
- Today query and desktop-first Today UI with loading, loaded, error, retry, and
  empty states.
- SQLite persistence with Alembic migration `0001_create_tasks`.
- Isolated backend and frontend tests covering the V0.1 task and Today flows.

### Notes

- Automated Backup/Restore remains out of scope for V0.1.
- V0.1 passed automated tests and manual acceptance.
