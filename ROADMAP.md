# DayFlow Personal Roadmap

Current application version: **v0.4.0 — V0.4 Projects**. V0.4 Projects
functionality is complete. The Project Backend and Frontend are implemented;
final acceptance and database verification passed. The real database schema is
`0004_add_projects`. V0.5 Phase 1 Backend implementation is in progress;
V0.5 Frontend work has not started.

## Current

### V0.1 — Task Management

Status: Completed and released as `v0.1.0`.

- Project scaffold
- Git baseline
- Minimal Task model
- Task CRUD
- Complete and restore
- Soft Delete with Undo
- Today page
- Today loading/error/loaded states with Retry
- SQLite persistence
- Alembic migration
- Isolated backend and frontend tests

V0.1 deliberately does not include automated Backup/Restore, Projects, Inbox,
Calendar, Reminders, AI, or scheduling.

## Completed

### V0.2 — Inbox and Organization

Status: Completed and released as `v0.2.0`; patch and Browser E2E acceptance
work released as `v0.2.1`.

- Inbox based on `planned_date IS NULL`, excluding completed and deleted Tasks
- Priority
- Category
- Tags
- Search over title and description
- Structured Priority, Category, and Tag filters

## Completed and Current Development

### V0.3 — Calendar and Time Blocking

Status: Completed and released as `v0.3.0`; UI/UX polish released as
`v0.3.1`. Its schema is `0003_add_task_schedule`; the real database later
advanced to `0004_add_projects` during V0.4 preparation.

Scope:

- Calendar range query
- Day View
- Week View
- Month View
- Date-only Tasks shown as “未安排时间”
- One optional Time Block per Task
- Persisted `start_at_utc`, `end_at_utc`, and `schedule_timezone`
- Timezone-consistent scheduling with Python `zoneinfo`
- Active pending Task conflict detection with explicit overlap override
- Optimistic Version and atomic schedule updates
- Hash-based Calendar navigation with Day/Week/Month views
- Task Editor Time Blocking with explicit clear support
- Runtime timezone integration and Chinese conflict confirmation
- Calendar loading, error, empty, and retry states

Explicitly out of scope:

- Drag & Drop
- Resize
- Cross-day Time Blocks
- Repeat
- Calendar Event
- Project
- Reminder
- AI Scheduling
- External Calendar integration

`0003_add_task_schedule` was validated on a temporary copy and then applied to
the real database after backup and approval. No later migration is implied by
this roadmap entry.

### V0.4 — Projects

Status: Completed. Phase 1 Backend, Migration 0004, Phase 2 Project Frontend,
Phase 3 acceptance, and real-data migration are complete. The real database is
at `0004_add_projects`.

Scope:

- Project CRUD and Hash-based Project list/detail views
- One optional Project per Task via nullable `tasks.project_id`
- Project Task assignment and clearing from Task Editor
- Active/completed Project lifecycle: complete and reopen
- Soft delete and restore for Projects
- Dynamic Project progress from active Tasks, with empty Projects at 0%
- Project-aware Task filtering and compact Project display in existing views
- Optimistic Version, atomic relationship updates, and grouped progress queries
- `0004_add_projects` tested on temporary databases and applied to real data
  after backup and explicit approval

Frozen lifecycle rules:

- Completing a Project never completes its Tasks.
- Completing a Task never changes Project status.
- Deleting a Project clears `project_id` for all related Tasks, including
  soft-deleted Tasks, and increments each affected Task version once.
- Restoring a Project never restores historical Task relationships.
- Active Project names are unique; restoring into a duplicate name returns 409.
- Progress is dynamic and never stored in the database.

Explicitly out of scope:

- Kanban, subprojects, Project hierarchy, teams, assignees, sprints
- Comments, attachments, file upload
- Project colors, icons, deadlines, start dates, sorting, archive, pause
- Project AI, external integrations, reminders, and recurrence

V0.4 implementation completed in this order: Phase 1 temporary `0004`
migration rehearsal and Backend model/service/API, Phase 2 Frontend Hash views
and Task Editor integration, Vitest and Browser E2E regression, Phase 3 full
acceptance, and approved real-data migration. V0.5 Phase 1 Backend work is in
progress; Frontend work has not started.

Optional future tooling: Windows one-click WSL start/stop entrypoints. The
currently supported workflow uses the WSL start and stop scripts directly.

## Next Planned Development

### V0.5 — Deadlines, Repeat Tasks, and Reminders

Status: Architecture frozen; Phase 1 Backend implementation and isolated-database
tests are complete for review. The real database remains at
`0004_add_projects` until a temporary-copy migration, full test gate, backup,
and explicit approval are complete. Frontend work has not started.

#### Frozen Scope

- Deadline values may be date-only or a specific local time.
- Repeat rules support `daily`, `weekly` with selected weekdays, and `monthly`
  on days 1–28.
- Reminders support one or more explicitly specified trigger times per Task;
  relative Deadline reminders are out of scope.
- Existing Task, Project, Category, Tag, Calendar, and Time Block behavior
  remains compatible.

Deadline data is independent from `planned_date` and Time Blocks. Date-only
deadlines use a persisted IANA `deadline_timezone` for overdue evaluation;
timed deadlines are converted to and stored as UTC instants with their source
timezone. Completing a Task does not erase its deadline, but completed Tasks
are not treated as currently overdue.

Repeat rules do not create repeated Time Blocks, copy absolute Deadlines, or
copy Reminders. A generated occurrence may copy ordinary Task metadata when it
is still valid, but its Deadline, Reminder, and Time Block start empty.

#### Repeat Lifecycle Rules

- A normal Task `DELETE` soft-deletes only the current occurrence and does not
  generate another occurrence.
- For an active rule, `Skip` soft-deletes the current occurrence and creates the
  next occurrence in the same transaction; a stopped rule creates nothing.
- For an active rule, `Complete` completes the current occurrence and creates
  the next occurrence in the same transaction; a stopped rule creates nothing.
- The next occurrence is strictly later than both the current occurrence date
  and today in the rule timezone. Missed dates are not backfilled.
- `Stop` sets `stopped_at_utc` on the rule and keeps all historical Tasks.
- `Restore` restores only the selected Task; it never restarts a rule or
  reconstructs historical relationships.
- Explicit `Materialize` is the only operation that may create a next
  occurrence without completing or skipping the current one. It is never
  triggered by frontend startup or a GET request, creates at most one Task,
  does not backfill history, and is idempotent when a pending occurrence
  already exists. Soft-deleted historical occurrences still participate in
  date and uniqueness checks.
- Editing an occurrence edits that snapshot only. Editing a rule affects future
  materialization and does not rewrite already generated unfinished Tasks.

#### Reminder Lifecycle Rules

Reminder status is `pending`, `acknowledged`, or `dismissed`. `due` is a
read-only query condition (`pending` and trigger time reached), not a stored
status. `GET /api/v1/reminders/due` never writes. A user action is required to
acknowledge or dismiss a reminder. Frontend polling uses `sessionStorage` to
avoid duplicate dialogs in one browser session; reopening DayFlow can still
show unprocessed due reminders. No real-time notification is promised while
the Backend is stopped.

#### Migration and Test Gate

The implemented schema is `0005_add_deadlines_recurrence_reminders`; migrations
`0001` through `0004` remain immutable. Phase 1 validates upgrade,
constraints, UTC/timezone and DST behavior, repeat idempotence and rollback,
reminder state transitions, and all V0.4 regression suites on isolated
databases before any real-data migration is considered.

An independent V0.4 maintenance fix is still required for the stale `v0.3.1`
version text currently displayed by `frontend/src/App.vue`; it is not part of
V0.5 Migration 0005 or V0.5 feature implementation.

## Later

- V0.6: AI Provider abstraction and Mock Provider.
- V0.7: Natural-language Task creation.
- V0.8: AI Task decomposition.
- V0.9: AI Scheduling and Schedule Sandbox.
- V1.0: PWA, Backup/Restore, Statistics, and stability work.

## Candidate / Backlog

Ideas remain backlog items until a real need and version scope are approved.
