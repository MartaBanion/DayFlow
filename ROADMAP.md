# DayFlow Personal Roadmap

Current application version: **v0.5.1 — UI/UX refinement**.
V0.5 Backend and Frontend are complete, and the V0.5.1 presentation-only patch
is integrated into `main` and released as the current stable version `v0.5.1`. The real database schema
remains `0005_add_deadlines_recurrence_reminders`; V0.6 remains the next
planned feature-development version.

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
Phase 3 acceptance, and real-data migration are complete. Its migration is
`0004_add_projects`; the real database later advanced to `0005` for V0.5.

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
acceptance, and approved real-data migration.

Optional future tooling: Windows one-click WSL start/stop entrypoints. The
currently supported workflow uses the WSL start and stop scripts directly.

## Completed Functionality

### V0.5 — Deadlines, Repeat Tasks, and Reminders

Status: Backend and Frontend complete. Automated and manual visual acceptance,
approved real-data migration to `0005`, and final read-only acceptance passed.
Release status is confirmed by Git tags.

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

The independent V0.4 version-display maintenance fix is complete: `App.vue`
reads the application version from Frontend package metadata.

## Current UI/UX Patch

### V0.5.1 — UI/UX Consistency

Status: UI/UX implementation complete, integrated into `main`, and released as
`v0.5.1`. This is a presentation and interaction patch, not
a new business-feature release. Release status is confirmed by Git tags. The
real database remains `0005_add_deadlines_recurrence_reminders`.

Scope: CSS/Element Plus design tokens, App layout and Sidebar, Today, Inbox,
Search, TaskCard, grouped TaskEditor, Projects, Calendar Day/Week/Month, and
accessibility and responsive desktop polish. Business semantics and Backend
API contracts stay unchanged. No schema change or migration is needed. The
implementation passed Backend, Frontend, type-check, build, and Browser E2E
regression gates; manual desktop visual acceptance also passed. The detailed
contracts are in `docs/ARCHITECTURE.md`.

The completed implementation followed these reviewed phases:

1. Phase 0: design documentation freeze.
2. Phase 1: Design System, App Layout, and Sidebar.
3. Phase 2: Today, Inbox, Search, TaskCard, and TaskEditor.
4. Phase 3: Projects and Calendar.
5. Phase 4: Reminder UX.
6. Phase 5: full automated regression and manual visual acceptance at
   1440×900, 1024×768, and 900×700.

Preserve Backend regression, Frontend Vitest, and all 21 existing Browser E2E
scenarios. Add focused coverage for editor sections and draft preservation,
omitted/null payloads, Calendar overlap and short blocks, responsive layout,
and Reminder interaction. Existing assertions cannot simply be removed to
make the refactor pass; presentation-specific updates must preserve the
original behavioral checks. E2E continues to use isolated temporary `0005`
databases and the existing fail-closed runner, never real personal data.

Explicitly excluded: new business features, Router, Pinia, a new UI/state
framework, new dependencies, Kanban, Drag & Drop, Resize, a full global Reminder
history, background notification services, and V0.6 feature work. Week View
may scroll horizontally inside the Calendar; unintended whole-page overflow
is not accepted. Mobile is not an acceptance target for this patch.

### Future UI/UX Refinement Backlog

The current UI is acceptable for this stage but is not treated as the final
visual language. Future refinement remains a separate backlog and is not tied
to V0.6 by default:

- Theme and color refinement
- Typography refinement
- Further TaskCard and TaskEditor polish
- Calendar density and interaction polish
- Responsive desktop refinement
- Broader design-language consistency
- Dark Mode as a future candidate only

## Later

### V0.6 — Data Safety & Recovery

Status: Product scope and architecture frozen. Phase 1 Backup Core,
Create/List/Verify API and Manifest V1 are committed. Phase 2 Maintenance UI
is committed and has passed rough manual visual acceptance. Phase 3A state-only
maintenance lock, state tracking and Launcher/Backend startup blocking prototypes
are committed. Phase 3B read-only Restore Dry Run and RestorePlan generation are
committed. Phase 3C Restore Execution protocol is frozen and an isolated-only
execution prototype is committed. Phase 3D recovery coordination, storage
capability probes and explicit completed acknowledgement are implemented in the
working tree and committed. The acknowledge fail-open review finding is closed
by a durable two-phase startup-clearance receipt. Phase 4 Reminder Poll Failure
Visibility, Retry, and automatic recovery are implemented in the working tree
pending Review. Real Restore remains unimplemented. Process-abort tests are not
power-loss durability acceptance.
The current stable release remains `v0.5.1`. NO DATABASE MIGRATION REQUIRED:
the real schema stays `0005_add_deadlines_recurrence_reminders`; no `0006`.

MVP: consistent Create Backup, List Backups, Verify Backup, Restore Dry Run,
Pre-Restore Safety Backup, offline Restore CLI, post-Restore verification,
and a lightweight `#maintenance` (数据与备份) view. Backup metadata, logs,
and maintenance state live in controlled, Git-ignored filesystem locations.
Restore never runs as an active-database replacement HTTP request. The only
ancillary maintenance is visible Reminder polling failure, Retry, and recovery
feedback, preserving the 45-second polling and ack/dismiss semantics.

Implementation sequence (each phase has independent Review, Tests, and Commit):

1. Pre-Development Maintenance: V0.5.1 documentation release-status sync.
2. Phase 0: Architecture Freeze.
3. Phase 1: Backup Core and Create/List/Verify API.
4. Phase 2: Maintenance UI and CLI Restore guidance.
5. Phase 3A: state-only safety prototypes and startup blocking.
6. Phase 3B: read-only Restore Dry Run and RestorePlan generation.
7. Phase 3C: frozen execution design, then isolated Restore Execution Prototype:
   lifetime exclusive cooperative lock, external-use refusal, verified Safety
   Backup, independent candidate, no-overwrite switch and crash evidence.
8. Phase 3D: Launcher/Backend lease handoff and connection shutdown coordination,
   DB/WAL/SHM switching/crash-safety finalization. No real Restore is authorized.
9. Phase 4: Reminder Poll Failure Visibility, Retry, and automatic recovery;
   remove it from V0.6 if scope expands.
10. Phase 5: Full Acceptance, approved real Backup smoke, Restore on disposable
   copies only.
11. Release Gate: version/documentation sync and release verification.

Execution protocol is specified in `docs/ARCHITECTURE.md`; artifact/identity rules
are in `docs/DATABASE.md`. Operator stops DayFlow before execution admission;
running Backend/unknown users fail closed. `coordination.lock` uses lifetime
shared Backend/exclusive Restore leases. Operation workspaces live in controlled
`backups/restore-operations/<UUID4>/`, preserving target, Safety Backup,
candidate and original DB/WAL/SHM. Current evidence is not a Backup substitute.
Only tested local Linux/WSL ext4, no-replace rename and file/directory fsync are
supported. All C0-C8 crashes block startup; completed also keeps the marker until
explicit verified acknowledgement. No auto-rollback, cleanup, restart, force
flag or Migration is authorized. The execution prototype rejects real/project
data and permits only independent databases in the system temporary directory.

Phase 3 must validate isolated prototypes for SQLite connection/process usage
and maintenance-lock coordination, and DB/WAL/SHM switching at different crash
points with artifact preservation, startup blocking, and recovery inspection.
These are not Phase 1 blockers; real Restore is prohibited until they pass and
separate explicit approval is given. No real Restore during development.

Test gates include WAL/concurrent committed writes, Metadata, path boundaries,
read-only verification, safety-backup failure, isolated Restore, interrupted
switching, startup blocking, precise stop, and full Backend/Vitest/Playwright/
type-check/build regression. Detailed contracts are in the core docs.

Excluded: Review/Statistics, Saved Views, Manual Ordering, Kanban, AI, Cloud
Sync, Multi User, Mobile App, External Calendar, Project Hierarchy, Reminder
Background Service, Repeat Time Block, unrelated bundle/Starlette warnings,
large TaskEditor extraction, global CSS or API Client refactoring.

### Later Candidates

AI Provider abstraction and Mock Provider are deferred candidates, not V0.6 scope.
- V0.7: Natural-language Task creation.
- V0.8: AI Task decomposition.
- V0.9: AI Scheduling and Schedule Sandbox.
- V1.0: PWA, Backup/Restore, Statistics, and stability work.

## Candidate / Backlog

Ideas remain backlog items until a real need and version scope are approved.
