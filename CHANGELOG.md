# Changelog

## [Unreleased] — V0.2 development

### Added

- Inbox semantics based on active, pending Tasks without a planned date.
- Low/normal/high Priority with a normal default.
- Category CRUD and nullable Task Category relationships.
- Tag CRUD and normalized Task/Tag relationships.
- Parameterized title/description Search with structured filters.
- SQLite Foreign Key enforcement for application, migration, and test connections.
- V0.2 migration compatibility and Frontend Inbox/Search tests.
- Minimal Category and Tag management UI with create, rename, delete, and refresh.

### Changed

- Split the Today-first Frontend shell into Today, Inbox, Task Card, and Task Editor components.
- Extended Task organization updates to increment optimistic version once per Task PATCH.

### Fixed

- Explicit `priority: null` Task PATCH requests now return HTTP 422 without changing
  Task data or optimistic version.

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
