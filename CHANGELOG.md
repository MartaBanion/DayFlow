# Changelog

## [Unreleased] — V0.9 Planning Flow Refinement

V0.9 Phases 0–2 are complete. Full Acceptance is PASS, including the Month
empty-date blocker fix and its existing Day View regression. Application
Version is `0.9.0`; Release Preparation is current, Stable Release remains
`v0.8.0`, and V0.9.0 is not released.

### Frozen Scope

- Quick Reschedule for pending Tasks: Today, Tomorrow, Next Monday, Move to
  Inbox, and Choose Date.
- The same versioned Task PATCH and conflict confirmation from Today and
  Calendar.
- Month date click, including “还有 N 项”, switches to the existing Day View.
- Presets use DayFlow `/runtime` `local_date` and pure date arithmetic.
- Moving a scheduled Task preserves its local clock and timezone; Deadline,
  Reminder, and Recurrence remain unchanged.
- Request-race protection covers Today and Calendar refreshes; optimistic
  version semantics and existing schedule-conflict handling are reused.
- DST-aware Time Block movement preserves local clock/timezone semantics.
- Empty Month dates render the existing Day View, including keyboard activation.
- No new API, dependency, migration, or `0006`; Inbox Quick Project and Quick
  Priority remain DEFERRED.

## [v0.8.0] — Task Organization at Scale

V0.8.0 is formally released. The annotated `v0.8.0` tag points to release
Commit `6bbd452dcee8fbc793e1c66deba2b986eac3197c`.

### Completed

Backend:

- Current status, canonical Overdue, planned-date bucket, and stable sort
  filters on `GET /api/v1/tasks`.
- Request-scoped clock and Project query reuse.

Frontend:

- Search organization controls with clear Search / Inbox semantics.
- Project Detail filter/sort reuse, Reset, Loading/Error/Empty states, request
  race protection, and Task edit refresh.

Quality:

- Backend: 405 passed.
- Frontend: 99 passed; type-check and build passed.
- Playwright Chromium: 40 passed.
- Performance sanity: PASS.
- NO DATABASE MIGRATION REQUIRED.

Inbox Quick Project and Quick Priority remain DEFERRED and are not release
gates.

### Frozen Scope

- Status filters: pending, completed, and all.
- Canonical Overdue filter and DayFlow-timezone planned-date buckets.
- Limited stable sorting for default, planned, deadline, and completed views.
- Reuse of the same Task query contract in Project Detail.
- Existing `TaskRead[]` response shape, AND semantics, Reset, and no pagination.

NO DATABASE MIGRATION REQUIRED. No `0006` exists. Inbox Quick Project and Quick
Priority remain DEFERRED. V0.9 Planning Flow Refinement is a separate scope.

## [v0.7.0] — Daily & Weekly Review

V0.7.0 is formally released. The annotated `v0.7.0` tag points to release
Commit `b632f10dbc9cde7da04083a60ef758dea648b594`.

### Added

- Daily and weekly current-state Review using retained `completed_at_utc`.
- Current Completed, Overdue, and Carryover lists with Task navigation.
- Current Project progress, pending/overdue counts, and latest retained Task
  completion.
- Read-only Review API and `#review` UI with Today/This Week scopes.
- Project navigation, Loading/Error/Retry, responsive behavior, and accessible
  controls.

### Compatibility

- `completed_at_utc` is not immutable activity history; Reopen removes a Task
  from Completed Review and `updated_at_utc` is never a completion proxy.
- NO DATABASE MIGRATION REQUIRED; the schema remains
  `0005_add_deadlines_recurrence_reminders` and no `0006` exists.
- Review GET operations are read-only and do not materialize recurrence or
  mutate business data.

## V0.7.0 Release Preparation History

Historical record: V0.7.0 Release Preparation, before the annotated release
tag was created. Daily & Weekly Review implementation and Full Acceptance were
complete at that point.

### Completed in Preparation

- Daily and weekly current-state Review using retained `completed_at_utc`.
- Current Completed, Overdue, and Carryover lists with Task navigation.
- Current Project progress, pending/overdue counts, and latest retained Task
  completion.
- Read-only Review API and `#review` UI with Today/This Week scopes.
- Project navigation, Loading/Error/Retry, responsive behavior, and accessible
  controls.
- No Dashboard, charts, immutable history, Task Organization expansion, or
  Backup/Restore work.

### Compatibility

- NO DATABASE MIGRATION REQUIRED; the schema remains
  `0005_add_deadlines_recurrence_reminders` and no `0006` exists.
- Review GET operations are read-only and do not materialize recurrence or
  mutate business data.

## [v0.6.0] — Data Safety & Recovery

V0.6.0 was the published stable release before v0.7.0. Full Acceptance passed
and the annotated `v0.6.0` tag points to its release Commit. Real project-database
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
