# Changelog

## [Unreleased] — V0.6.0 Data Safety & Recovery

V0.6.0 Release Preparation is complete and Full Acceptance is PASS. The
annotated `v0.6.0` tag and formal release have not been created; the last
published stable tag remains `v0.5.1`. Real project-database Restore remains
prohibited; current Real Restore Storage Qualification is `NOT QUALIFIED`.

### Added

- Backup Core with consistent SQLite backups, Manifest V1, list, verify, and
  controlled path/origin safety.
- Maintenance UI with database status, Backup Create/List/Verify, and Restore
  guidance.
- Restore Dry Run and isolated Restore execution with pre-Restore Safety
  Backup, candidate validation, WAL/SHM/DB archiving, controlled switching,
  final verification, and crash-safety evidence.
- Recovery coordination with Backend usage locks, Launcher handoff, startup
  blocking, completed acknowledgement, durable clearance receipts, and status
  inspection.
- Reminder poll failure visibility with Retry, automatic recovery, and existing
  Reminder data preservation.

### Compatibility

- The database schema remains `0005_add_deadlines_recurrence_reminders`; no
  `0006` migration is included.
- Real Restore is not authorized for the project database. Restore evidence is
  preserved and the isolated execution boundary remains documented.

## [v0.5.1] — UI/UX Refinement

V0.5.1 is a presentation-only patch and the current stable release. Its
release-preparation phase is historical; release status is confirmed by the
annotated Git tag.

### Changed

- Refined the shared Design System, Element Plus theme, App layout, Sidebar,
  focus states, and responsive desktop behavior.
- Improved Today, Inbox, Search, TaskCard, and grouped TaskEditor hierarchy.
- Clarified independent Repeat and Reminder save boundaries without changing
  their API semantics.
- Improved Projects and Calendar readability, overlap presentation, short
  Time Block display, and keyboard-accessible interactions.

### Compatibility

- Backend APIs and business semantics are unchanged.
- The database schema remains `0005_add_deadlines_recurrence_reminders`; no
  migration is included in this patch.

## [Unreleased] — V0.3.1 UI/UX Polish

### Changed

- Refined Inbox wording to distinguish the inbox from tasks waiting for a date.
- Expanded the Calendar workspace and unified Calendar navigation controls.
- Reworked the Week view into a seven-column time-blocking timeline with a
  shared “未安排时间” area.
- Improved Day/Month date hierarchy, today highlighting, and completed Time
  Block styling.
- Kept the default user-facing interface in natural Simplified Chinese.

## [Unreleased] — V0.3 Calendar Frontend

### Added

- Hash-based Calendar navigation with Day, Week, and Month views.
- Date-only Task display as “未安排时间” and single Task Time Blocks.
- Task Editor start/end time editing and explicit Time Block clearing.
- Backend runtime timezone integration, Calendar loading/error/empty states, and
  Chinese schedule conflict confirmation.
- Calendar Vitest and Playwright Browser E2E regression coverage.

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
