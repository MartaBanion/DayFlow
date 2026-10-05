# DayFlow Personal Roadmap

Stable release: **v0.7.0 — Daily & Weekly Review**. Current DayFlow
application version: **0.8.0**, in Release Preparation. The
annotated `v0.7.0` tag is the published stable release and points to Commit
`b632f10dbc9cde7da04083a60ef758dea648b594`. V0.7 Phases 0–3 are complete.
Current development is V0.8 Task Organization at Scale. Phases 0–3 are
complete, including Full Acceptance; current status is V0.8.0 Release
Preparation. V0.8.0 is not released. Phase 1 is committed as
`82691ac61bbce3cf745de2cfd5904f7619c1a642`, following the Phase 0 freeze
commit `97e118a0d546f57fcee7a9dd6ae53f6f0010db80`; Phase 2 is committed as
`60a1dacbf1d044054a26da1e4556e6c2270de9cf`. Phase 3 acceptance adds no code
commit. The real database schema remains
`0005_add_deadlines_recurrence_reminders`.

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

## Released

### V0.6 — Data Safety & Recovery

Status: Completed and formally released as `v0.6.0`. Product scope and
architecture are frozen. Phase 1 Backup Core,
Create/List/Verify API and Manifest V1 are committed. Phase 2 Maintenance UI
is committed and has passed rough manual visual acceptance. Phase 3A state-only
maintenance lock, state tracking and Launcher/Backend startup blocking prototypes
are committed. Phase 3B read-only Restore Dry Run and RestorePlan generation are
committed. Phase 3C Restore Execution protocol is frozen and an isolated-only
execution prototype is committed. Phase 3D recovery coordination, storage
capability probes and explicit completed acknowledgement are implemented,
reviewed, and committed. The acknowledge fail-open review finding is closed by
a durable two-phase startup-clearance receipt. Phase 4 Reminder Poll Failure
Visibility, Retry, and automatic recovery are implemented, reviewed, and
committed. Phase 5 Full Acceptance passed the Functional, Regression, Data
Safety, Migration, Launcher, Restore Boundary, and Repository Hygiene gates;
the Documentation Gate is synchronized. V0.6.0 Full Acceptance is PASS. The
release Commit is `fc8311b3f97536907158f940d2f414e30c98a301`, and the annotated
`v0.6.0` tag points to that Commit. Isolated Restore
execution is implemented and verified; real project-database Restore remains
prohibited. Real Restore Storage Qualification is currently `NOT QUALIFIED`
because the real data mount differs from the system-temporary qualification
mount. Process-abort tests are not power-loss durability acceptance.
At the time of the V0.6 release, the published stable release was `v0.6.0`.
NO DATABASE MIGRATION REQUIRED:
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
   DB/WAL/SHM switching/crash-safety finalization. Completed and reviewed; no
   real Restore is authorized.
9. Phase 4: Reminder Poll Failure Visibility, Retry, and automatic recovery;
   completed and reviewed.
10. Phase 5: Full Acceptance with isolated Backup/Restore tests, normal Launcher
    smoke, and release-gate verification. Completed.
11. Release Preparation: version/documentation sync and release verification.

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

## Current Development

### V0.7 — Daily & Weekly Review (Released)

Status: Completed and formally released as `v0.7.0`. Phase 0 Product /
Architecture Freeze and Phase 1
Review Core are complete and committed. Phase 2 `#review` UI and Frontend
integration are complete and committed. Phase 3 Full Acceptance is PASS. V0.7
is a read-only, list-first Review flow, not a Dashboard or Statistics system.

Must Have:

- Hash view and main navigation entry: `#review` / 回顾.
- Scope selector: Today / This Week, with Monday-based weeks in the configured
  DayFlow IANA timezone.
- Completed Review containing only non-deleted Tasks that are still completed
  and whose retained `completed_at_utc` falls in the selected UTC half-open
  range.
- Current Overdue based on the existing date-only/timed Deadline semantics.
- Carryover defined only as non-deleted pending Tasks whose `planned_date` is
  earlier than the current DayFlow local date.
- Current Project snapshots: non-deleted Task totals, completed/pending/overdue
  counts, completion percentage, and latest retained Task completion.
- Navigation from Review to the existing Task Editor and Project Detail.
- A pure read-only Review API with isolated Backend, Frontend, and E2E tests.

Historical limits are explicit: `completed_at_utc` is the latest retained Task
completion state, not immutable history; Reopen/Restore-to-pending removes a
Task from Completed Review; `updated_at_utc` is never a completion proxy. Each
recurrence occurrence participates as its own Task. Skip, Delete, and Stop are
not completion events. Project Review is a current snapshot and never claims
stagnation or last activity.

NO DATABASE MIGRATION REQUIRED. Keep
`0005_add_deadlines_recurrence_reminders`; do not create `0006`. If immutable
event history becomes necessary, implementation must stop for a new product
decision.

Explicitly excluded: Dashboard/charts/trends/productivity scores, streaks,
time tracking, Activity/Event History, Saved Views, Kanban, Subtasks, Project
Tree, Manual Ordering, Drag & Drop, Batch Edit, advanced Search, bulk Inbox
triage, quick defer, Calendar or TaskEditor redesign, AI/auto-scheduling,
background notifications, and all Backup/Restore/Recovery work.

Implementation phases:

1. Phase 0: Product / Architecture Freeze — complete and committed.
2. Phase 1: read-only Review API and Backend tests — complete and committed.
3. Phase 2: `#review`, navigation, Frontend tests, and isolated E2E — complete
   and committed.
4. Phase 3: full acceptance, real-database read-only validation, documentation,
   and release gate — complete.

Definition of Done: `#review` reliably answers what was completed today and
this week, what is currently overdue, what planned work is carried over, and
the current basic state of each Project, with navigation to the existing Task
and Project flows.

### V0.8 — Task Organization at Scale

Status: Phase 0 Product / Architecture Freeze, Phase 1 Task Query Core, Phase 2
Search / Project UI Integration, and Phase 3 Full Acceptance complete. V0.8.0
Release Preparation is in progress; v0.8.0 is not released.
The single theme is Search / Filter / Sort with Project reuse. V0.8 extends the
existing `GET /api/v1/tasks` endpoint and keeps the existing `TaskRead[]`
response shape.

Must Have:

- Current status filter: `pending`, `completed`, or `all`.
- Canonical `overdue=true` filter using the existing Deadline evaluator.
- Planned-date buckets: `unscheduled`, `today`, `past`, and `future`, using
  the configured DayFlow IANA timezone.
- Limited fixed sorts: `default`, `planned`, `deadline`, and `completed`, each
  with documented null placement and stable tie-breakers.
- Project Detail reuse of the same filters and sorts with a fixed
  `project_id`, plus clear Search mode, AND semantics, Reset, and isolated
  regression coverage.

The default query behavior remains backward compatible, Inbox keeps its strict
pending/unplanned meaning, and contradictory combinations return the natural
empty intersection rather than silently ignoring a parameter. Each Task-list
request captures one `generated_at_utc`; Overdue and planned buckets use that
same instant, and TaskRead deadline status must use the same boundary.

Should Have: optional Quick Project and Quick Priority Inbox actions after the
core query scope is complete. URL/hash filter state is optional only if it is
nearly free and does not introduce a global store.

Explicitly out of scope: a new Search API, query language, Saved Views,
grouping engine, Kanban, Subtasks, Manual Ordering, Drag & Drop, Batch Edit,
Activity History, pagination without measured evidence, Quick Postpone, Move
Tomorrow/Next Week, Calendar/Review redesign, AI, and Backup/Restore/Recovery.

NO DATABASE MIGRATION REQUIRED. Keep
`0005_add_deadlines_recurrence_reminders`; do not create `0006`, new columns,
tables, or indexes during Phase 0.

Implementation phases:

1. Phase 0: Product / Architecture Freeze — frozen.
2. Phase 1: Task Query Core — complete. This adds
   filters, fixed sorts, request clock, canonical Deadline reuse, and Backend
   tests.
3. Phase 2: Search / Project UI Integration — controls, reuse, Frontend tests,
   and isolated E2E — complete. Inbox Quick Project/Priority remains separately
   optional and is not implemented.
4. Phase 3: Full Acceptance — complete. Release Preparation is in progress.

Definition of Done: the user can quickly find all pending Tasks, current
completed Tasks, current Overdue Tasks, planned-date buckets, and use a small
set of stable sorts; Project Detail offers the same organization capability.

## Later Candidates

- V0.9 Planning Flow refinement remains separate from V0.8 organization.
- V1.0 Product Maturity follows the focused V0.8 and V0.9 milestones.
- AI assistance remains a future candidate after the core product workflow is
  mature; it is not on the active V0.8 path.

## Candidate / Backlog

Ideas remain backlog items until a real need and version scope are approved.
