# Changelog

## [Unreleased] — V0.7 Daily & Weekly Review

V0.7 Product / Architecture Freeze defines a read-only `#review` experience
for Today and This Week. Product implementation has not started.

### Planned

- Current-state completed Task review using retained `completed_at_utc`.
- Current overdue and carryover lists with Task navigation.
- Current Project progress, pending/overdue counts, and latest retained Task
  completion.
- No Dashboard, charts, immutable history, Task Organization expansion, or
  Backup/Restore work.

### Compatibility

- NO DATABASE MIGRATION REQUIRED; the schema remains
  `0005_add_deadlines_recurrence_reminders` and no `0006` exists.
- Review GET operations are read-only and do not materialize recurrence or
  mutate business data.

## [v0.6.0] — Data Safety & Recovery

V0.6.0 is the current published stable release. Full Acceptance passed and the
annotated `v0.6.0` tag points to its release Commit. Real project-database
Restore remains prohibited; current Real Restore Storage Qualification is
`NOT QUALIFIED`.

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

V0.5.1 is a presentation-only patch and a previous stable release. Its
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
