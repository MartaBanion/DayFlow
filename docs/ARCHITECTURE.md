# Architecture

## Current Version

Current application version: **v0.5.1** — UI/UX refinement.
V0.5 Backend and Frontend are complete; the V0.5.1 presentation-only patch is
implemented, integrated into `main`, and released as the current stable version
`v0.5.1`. The real
database schema remains `0005_add_deadlines_recurrence_reminders`; V0.6
remains the next planned feature-development version. Release status is
confirmed by Git tags.

## Frozen V0.6 — Data Safety & Recovery

Status: Phase 1 Backup Core/Create/List/Verify/Manifest V1 are committed.
Phase 2 Maintenance UI is committed with rough manual visual acceptance.
Phase 3A maintenance lock/state tracking and Launcher/Backend startup blocking
prototypes are committed. Phase 3B read-only Restore Dry Run and RestorePlan
generation are implemented in the development working tree, pending Review.
Actual Restore CLI, database replacement, actual recovery and Reminder poll
visibility are not yet implemented.
Stable release is `v0.5.1`. This version is not Statistics,
Review, AI, Task Organization, or a Notification Service.

### Product and Storage Boundaries

MVP includes Create/List/Verify Backup, Restore Dry Run, Pre-Restore Safety
Backup, offline Restore CLI, automatic post-Restore verification, and a
lightweight Maintenance view. NO DATABASE MIGRATION REQUIRED. Existing
`0005_add_deadlines_recurrence_reminders` and all business semantics stay intact.
Metadata, Restore logs, and maintenance state are controlled filesystem data,
Git ignored, never business tables. No `0006` is created.

### Backup and Verification

Maintenance UI uses the existing Hash navigation (`#maintenance`), with a
secondary 数据与备份 entry. It creates, lists and explicitly verifies registered
backups; no polling, deletion, Restore button or invented CLI command exists.
Current application/schema status comes from the read-only runtime endpoint,
not historical Backup metadata. List verification is labeled as a registration
record; measured verification results remain local to the current view. An
unverified compatible record says 需要验证, not currently safe to Restore.
Restore guidance explains offline overwrite risks and deferred Phase 3 work.

Default root is `data/backups/`. Use Python `sqlite3.Connection.backup()` with
a read-only source connection; include committed WAL data. Copying the active
main file is not a consistent backup mechanism. Backup captures an internally
consistent committed snapshot, not every write made before it finishes.

Publication order: unique temporary file → Online Backup → close target →
integrity check → foreign key check → schema/critical-structure check →
SHA-256 → publish database without overwrite → publish Manifest V1.
Incomplete artifacts are not recoverable entries. Published Backup databases
are immutable. No automatic Backup cleanup is included in V0.6.

Phase 1 uses atomic same-filesystem hard-link publication followed by removal
of the temporary link: existing final files cannot be overwritten. Files and
directory are fsynced before success. Backup ID is independent of filename.
Root derives from configured database parent / `backups`, never API input.
Descriptor walking with NOFOLLOW guards root components and regular-file opens.
Linux/WSL is the supported platform: SQLite inspection and temporary-target
writes use `/proc/self/fd` references to the held file, and publication links
that same inode rather than reopening a replaceable pathname. Unsupported
descriptor/hard-link facilities fail closed; there is no pathname fallback.
Published input files must have one link. Publication briefly adds a second
link only to the verified temporary inode, then removes the temporary name.
Verification rechecks identity, timestamps and SHA after inspection. These
guards do not provide authenticity against a user who controls the same OS
account and can rewrite both Backup and Manifest.
Online Backup is bounded (10-second limit, short SQLite busy timeout), with
no Maintenance lock. Concurrent creators use independent UUIDs and exclusive
temporary files. Manifest publication failure retains the DB as an unlisted
orphan and returns registration failure, never success.

Verify is explicit and read-only; it checks readability, SQLite format, hash,
size, integrity, foreign keys, Alembic version, required DayFlow tables, and
critical structure. Manifest is metadata, not truth. List displays last known
verification and timestamp; it does not silently perform full verification.
Structural checks derive required columns, PKs, FKs, CHECK expressions and
indexes from current models, plus the Alembic version table PK. They are a
compatibility screen, not a second Migration engine or proof of arbitrary SQL
semantic equivalence; no Backup is migrated or repaired during verification.
Recovery of missing Metadata requires separate explicit registration.

Create stores first verification time in Manifest. Subsequent Verify returns
its own timestamp and never edits published artifacts. Phase 1 skips invalid
registrations (logged); registration/rebuilding remains deferred explicit
maintenance. See `docs/API.md` for implemented result/error contracts.

Only exact schema `0005_add_deadlines_recurrence_reminders` is restorable.
Old, unknown, and newer versions may be inspected but cannot be restored.
Restore never migrates. Verification distinguishes valid-compatible,
valid-incompatible, corrupted, missing/unreadable, and Manifest mismatch as
semantic categories; these strings are not frozen API enums.

### Offline Restore Workflow

1. Verify target and show summary (identity, schema, hash, counts, overwrite impact).
2. Obtain explicit confirmation and maintenance lock.
3. Stop only identity-validated, managed DayFlow services.
4. Confirm database usage state; unknown processes or uncertainty fail closed.
5. Create and verify current database Pre-Restore Safety Backup.
6. Verify target again; build an independent Restore candidate and verify it.
7. Close all connections, persist candidate/operation state, perform controlled switch.
8. Verify final integrity, foreign keys, Alembic version, structure, and data.
9. Record result; clear blocking state only on success and leave services stopped.

Running Backend cannot replace its active database. Restore is Maintenance CLI
only; HTTP UI offers summary/explanation and prepared CLI guidance, not an
active-database replacement button or automatic shutdown worker.

Original DB/WAL/SHM material must be preserved in a controlled recovery
location before switching. Old WAL must never attach to the restored database.
Preserve original material, target, Pre-Restore Backup, candidate, and log until
a human decides retention. Source Backup is never consumed or modified.
Any failure stops further steps; never automatically rollback, downgrade, guess
recovery, or start services. No automatic service startup after success either.

### Maintenance and Startup Boundary

#### Phase 3A implemented prototype (not Restore)

`app.core.maintenance` operates only on controlled filesystem state in the
configured database's sibling `maintenance/` directory (default
`data/maintenance/`, Git ignored). It never opens SQLite, creates Backup data,
copies a Restore source, switches DB/WAL/SHM, stops a process or runs migrations.
There is no HTTP maintenance mutation or actual Restore CLI. The read-only
Launcher preflight remains `python -m app.core.maintenance --check`.

Two independent protections are required:

- A persistent `maintenance.lock` acquisition record contains UUID4 `lock_id`,
  UTC `created_at_utc`, `operation=restore-safety-prototype`, acquisition stage
  `prepare`, format version and application version. `restore-state.json`
  carries the matching identity and current stage. PID is not authority.
- A permanent `coordination.lock` inode uses nonblocking Linux/WSL `flock`.
  Backend ASGI lifespan checks state while holding a shared lease, retained
  for its lifetime. Prototype begin/transition/cleanup require an exclusive
  lease. Thus begin refuses while a cooperating Backend is running, without
  trying to stop it; Backend refuses to start after begin. The Launcher checks
  before its first SQLite open or process handling; Backend checks again to
  close the preflight/start race. The stop script is unchanged.

The coordination inode is never removed/replaced. State publication uses an
exclusive temporary file, file fsync, no-overwrite hard-link publication for
the acquisition record, atomic state-file replacement, and directory fsync.
Directory-descriptor walking and NOFOLLOW reject symlinks; nonregular files,
hard-linked records, foreign ownership, unsafe write permissions, unknown
files/partials, unknown formats/stages and parse failures block startup.
No insecure platform fallback is provided. State checks never silently remove
or repair artifacts. Empty/missing state is implicit `idle` (no write).

Normal simulated transitions are:

`idle → prepare → verified → switching → verifying → completed`

Each active stage may instead enter terminal `failed` or `blocked`. Updates
require the matching lock ID and expected previous stage; skipped/backward or
stale transitions fail without mutation. Recording `completed` needs explicit
confirmation; it proves only completion of the state simulation, **not** actual
database verification. Startup remains blocked until a second explicit,
identity-checked cleanup removes the completed acquisition marker. Completed
state and coordination inode remain. Failed/blocked/corrupt/incomplete records
cannot be cleared by this prototype; no reset/unlock/recovery CLI is exposed.
A persisted `idle` record is not an escape hatch and is rejected at startup.

Tests use isolated directories and actual child-process abnormal exits at
prepare/switching/verifying. The next Launcher/Backend check must reject them
without automatic continuation, rollback or record deletion. Tests also cover
concurrent acquisition, cross-process usage leases, corrupt/missing records,
publication/flush failure, explicit cleanup and absence of DB creation.

Limits: this is a cooperative Linux/WSL protocol, not a detector for arbitrary
SQLite connections or pre-existing Backend versions. Bypassing ASGI lifespan
is unsupported. Same-account actors able to rewrite controlled files are not
an authenticity boundary. Databases sharing a parent conservatively share the
maintenance root. Actual DB connection draining, unknown-process inspection,
DB/WAL/SHM preservation and switching/crash durability tests remain future
Phase 3 gates. Phase 3A authorizes no real Restore and no production unlock.

#### Remaining Phase 3 requirements

#### Phase 3B implemented prototype (Dry Run only)

`python -m app.maintenance_cli restore --dry-run <backup_id>` reads the
current database and invokes the existing read-only Backup Verify service. It
returns a `RestorePlan` containing current/target metadata, exact Schema
compatibility, the future Restore steps, and explicit refusal reasons. The
human-readable output includes `No changes performed.`; `--json` returns the
same plan as JSON.

This prototype never acquires `maintenance.lock`, writes `restore-state.json`,
creates a Backup, copies or replaces a database/WAL/SHM file, runs a migration,
stops a service, or changes a Manifest. It fails closed for an unreadable or
incompatible current database or target Backup. A non-zero exit means no
Restore action was performed. Actual Restore integration, candidate switching,
and recovery execution remain out of scope.

Maintenance CLI, start script, and Backend startup must coordinate database
usage locks, maintenance lock, and durable incomplete-Restore marker. Port
checks alone are insufficient. The existing startup operation lock is not a
database lifetime/maintenance protocol; Phase 3A adds cooperative safety state,
while actual database-use verification remains deferred.
Both script-mediated and direct Backend startup must refuse normal operation
while maintenance is active or a Restore is incomplete. Lock design must permit
managed shutdown without deadlocking the stop script.

File switching is not a SQLite transaction: durable phase records, disk flushes,
and startup blocking must cover process interruption and partial switching.
Specific locking/switching mechanics are deferred to isolated Phase 3 prototypes:
(1) SQLite connection/process usage/maintenance coordination; (2) DB/WAL/SHM
crash points, retained artifacts, startup blocking, and recovery inspection.
These do not block Phase 1; they block any real Restore pending tests and
separate explicit user approval. Development Restore is isolated only.

### Maintenance UI and Ancillary Reminder Work

Continue Hash navigation with `#maintenance`, Chinese entry 数据与备份.
Show current database status, Create, List, Verify, Restore summary and CLI
guidance. Restore uses destructive-action styling and explicit confirmation;
incompatible entries show reasons and no executable Restore command.
No Router or unrelated UI redesign.

Reminder maintenance is limited to visible but restrained polling failure,
Retry, and clearing the error after recovery. Preserve 45-second polling,
session deduplication, ack/dismiss, and existing persistence. No Snooze,
History, OS Notification, Background Service, or schema changes. Remove this
item from V0.6 if implementation would expand scope.

### Failures, Paths, and Logging

Fail closed for Backup/Verify/Pre-Restore Backup failure, unknown database
usage, Manifest failure, disk full, permissions, timeout, candidate/final
verification failure, and interrupted Restore. Preconditions failing must
never replace current DB. Failures during/after switching leave a durable
startup-blocking marker. Logs contain stages, file identifiers, hashes,
verification results, and errors, never personal Task contents or secrets.

API accepts Backup IDs, never arbitrary paths. Root is controlled; reject
absolute input paths, `..`, traversal, symlinks, outside-root resolved paths,
non-regular files, and unexpected overwrite. Manifest filename is untrusted.
Only DayFlow-named, verified/registered files become Restore candidates.
Prevent target replacement between validation/use and match candidate content
to verified source. Mutating local API operations validate browser request
origin; Single User does not justify unrestricted filesystem access.

### Implementation and Acceptance Gates

Each phase has independent Review, Tests, Commit: documentation maintenance;
Phase 0 architecture; Phase 1 Backup Core/API; Phase 2 Maintenance UI;
Phase 3 Restore CLI/locks/Launcher/crash safety; Phase 4 small Reminder item;
Phase 5 full acceptance; Release Gate. Planned functionality must remain
distinguished from implemented functionality in release documentation.

All destructive tests use isolated temporary databases. Compare real database
SHA-256 before/after automation; it remains at `0005`. Full matrix:

| Area | Required coverage |
| --- | --- |
| Create | normal, active WAL, committed concurrent writes, timeout, permission failure, simulated disk failure |
| Metadata | SHA, size, Manifest, missing/damaged Manifest, mismatch |
| List | valid, incomplete, unknown files, stable ordering |
| Verify | valid, corrupted, incompatible, missing, unreadable, no Backup mutation |
| Path | traversal, absolute input, symlink, outside root, overwrite conflict |
| Preparation | dry-run, incompatible schema, unknown process, failed Safety Backup |
| Restore | isolated success, WAL isolation, preserve original/target/Safety Backup |
| Failure | before/during/after switch, interrupted process, startup-blocking marker |
| Launcher | normal start, incomplete Restore blocks start, precise stop |
| Reminder | poll failure, Retry, recovery, no implicit Reminder mutation |
| Regression | Backend, Vitest, existing 28 Playwright scenarios, type-check, build |

Acceptance includes approved real Backup smoke (no Restore) and disposable-copy
Restore. Real Restore always requires separate explicit approval.

Excluded: Review/Statistics, Saved Views, Manual Ordering, Kanban, AI, Cloud
Sync, Multi User, Mobile App, External Calendar, Project Hierarchy, Reminder
Background Service, Repeat Time Block, unrelated bundle/Starlette warnings,
large TaskEditor extraction, global CSS/API Client refactoring.

## Existing Application Architecture

DayFlow is a local-first, single-user modular monolith:

```text
Vue 3 Frontend → FastAPI REST API → Service Layer → SQLAlchemy → SQLite
```

The application is intentionally not split into microservices. AI, reminders,
recurrence, external calendar integration, and scheduling automation remain
outside V0.3 and V0.4. Project support is limited to the frozen V0.4 design
below; it must not be implemented as part of unrelated work.

The request path remains:

```text
HTTP route → Pydantic schema → Service Layer → SQLAlchemy Session → SQLite
```

Routes expose HTTP contracts only. Services own validation that depends on
stored data, state transitions, conflict detection, optimistic version checks,
and transaction boundaries.

## Existing Decisions

- SQLite is sufficient for the current single-user local workload.
- Synchronous SQLAlchemy is preferred for simple SQLite transactions.
- API version prefix is `/api/v1`.
- Real data lives under `data/` and is excluded from Git.
- Schema changes use Alembic only.
- Tests use isolated temporary databases.
- Timestamps are UTC instants; date-only planning uses `planned_date`.
- UUIDs are generated by the application and stored as text for SQLite portability.
- V0.1/V0.2 statuses remain `pending` and `completed`.
- Soft deletion is represented by `deleted_at_utc`, not by another status.
- Inbox is `planned_date IS NULL`, `deleted_at_utc IS NULL`, and pending only.
- Priority is a non-null `low`, `normal`, or `high` value with `normal` default.
- A Task has at most one nullable Category.
- Tags use normalized `tags` and `task_tags` tables.
- Search uses parameterized SQLite `LIKE` over title and description.
- Every SQLAlchemy SQLite connection enables `PRAGMA foreign_keys=ON`.
- AI and ScheduleBlock are not current schema dependencies. V0.5 Deadline,
  Recurrence, and Reminder structures are implemented and present in the
  approved real database at `0005`.

## Frozen V0.3 Decisions

V0.3 contains Calendar, Day View, Week View, Month View, date-only Tasks, and
one optional Time Block per Task. It does not contain Drag & Drop, Resize,
cross-day Time Blocks, Repeat, Calendar Event, Project, Reminder, AI Scheduling,
or external Calendar integration.

### Task Time Model

One Task can have at most one Time Block. The existing `tasks` table will gain:

- `start_at_utc`: nullable UTC instant.
- `end_at_utc`: nullable UTC instant.
- `schedule_timezone`: nullable IANA timezone used to interpret the block.

`planned_date` remains a date-only local calendar value. When a Time Block is
present, it must equal the local date of `start_at_utc` in
`schedule_timezone`. A Time Block therefore requires all four values:
`planned_date`, `start_at_utc`, `end_at_utc`, and `schedule_timezone`.

The state meanings are:

```text
Inbox:       planned_date = NULL, no Time Block
Date-only:   planned_date != NULL, no Time Block
Scheduled:   planned_date != NULL, one complete Time Block
```

The UI should call a date-only Task “未安排时间”, not “全天任务”.

No `all_day`, `schedule_mode`, or `time_block_id` field is planned. A separate
TimeBlock table is not needed while a Task has at most one block.

### Schedule Writes

Task Create/Patch uses one structured `schedule` value so that a block cannot
be partially updated:

```json
{
  "planned_date": "2026-09-26",
  "schedule": {
    "start_time": "14:00",
    "end_time": "15:00",
    "timezone": "Asia/Shanghai"
  }
}
```

`timezone` may be omitted and then defaults to `DAYFLOW_TIMEZONE`.

- Omitted `schedule`: keep the existing Time Block unchanged.
- `schedule: null`: clear the Time Block and keep `planned_date` by default.
- `planned_date: null` together with `schedule: null`: return the Task to Inbox.
- Changing only `planned_date` on a scheduled Task preserves local clock times
  and the stored `schedule_timezone`, then recalculates the UTC instants.

### Conflict Policy

The Backend checks real UTC overlap against active, pending, non-deleted Tasks.
It does not automatically move or reschedule Tasks.

By default, a conflict returns HTTP 409 with error code
`schedule_conflict`. The user may explicitly confirm and retry with the
one-request override `allow_schedule_conflict=true`. The override is not
stored as Task data.

Frontend confirmation copy should be concise Chinese, for example:
“该时间段与已有任务冲突，是否仍然保存？”

Conflict failure and stale-version failure are atomic: no partial update and no
version increment may remain.

## Frozen V0.4 Project Decisions

V0.4 is a single-user Project layer over the existing Task model. Its scope is
Project CRUD, assigning Tasks to one Project, Project detail, dynamic progress,
Project lifecycle actions, and Project-aware Task filtering/display. It does not
introduce a second Task CRUD system or a workflow/kanban model.

### Project Model

The planned `projects` table contains only fields required by V0.4:

- `id`: application-generated UUID stored as text.
- `name`: required trimmed name.
- `description`: nullable text.
- `status`: `active` or `completed`.
- `created_at_utc` and `updated_at_utc`: UTC instants.
- `completed_at_utc`: nullable UTC instant.
- `deleted_at_utc`: nullable UTC instant for soft delete.
- `version`: integer optimistic-concurrency version starting at 1.

Color, icon, deadline, start date, sort order, archive state, pause state,
hierarchy, and persisted progress are deliberately deferred. Project names are
unique only among non-deleted Projects. Trimmed, case-insensitive duplicate
validation is a service/API responsibility backed by a partial unique index;
SQLite `NOCASE` limitations for non-ASCII case folding remain documented.

### Task Relationship and Lifecycle

V0.4 adds nullable `tasks.project_id`. A Task belongs to zero or one Project,
and a Project contains zero or more Tasks. Inbox, planned-date, Calendar,
Priority, Category, Tag, schedule, complete, restore, and soft-delete semantics
remain unchanged. An Inbox Task may belong to a Project, and a Project Task may
have no planned date or Time Block.

Project lifecycle rules are fixed:

- `complete` changes only the Project to `completed` and sets
  `completed_at_utc`; it never completes associated Tasks.
- `reopen` changes only a completed Project to `active` and clears
  `completed_at_utc`.
- `DELETE` soft-deletes the Project and, in the same transaction, clears
  `project_id` on every associated Task, including soft-deleted Tasks.
- Every affected Task version increases at most once for that delete operation.
- `restore` clears only the Project's soft-delete marker and preserves its
  status/completion timestamp. It never reconstructs historical Task
  relationships; a name collision with an active Project returns HTTP 409.
- Task completion never changes Project status.

All Project mutations require the current Project `version` and increment it
once on success. Task assignment, clearing, or Project deletion follows the
existing one-PATCH/one-version-increment rule; an affected Task's
`updated_at_utc` is updated with that single version change. Multi-row changes
use one transaction and roll back completely on validation, conflict, or
database failure.

### Progress and Query Boundaries

Progress is computed dynamically and is never stored. For a non-deleted Project:

```text
completed active Tasks / total active Tasks
```

Soft-deleted Tasks are excluded from both numerator and denominator. Completed
Tasks remain in the denominator. An empty Project reports 0% and zero Tasks.
Project list queries must obtain counts and completed counts with grouped
aggregates (or an equivalent bounded query plan), not one query per Project.

Project detail reuses the existing Task list/filter path with
`project_id=<uuid>`. The Task editor gains a Project selector, and Today,
Inbox, Search, and Calendar may display a compact Project name without changing
their existing date, status, or deletion semantics.

### V0.4 Frontend Boundary

The existing Hash navigation remains in use: `#projects` for the Project list
and `#project:<id>` for Project detail. The minimum frontend units are a
Projects view, a Project detail view, and the existing Task Editor extension.
No Vue Router, Pinia, new UI framework, Kanban board, or project-specific drag
interaction is introduced.

## V0.5 Implementation: Deadlines, Repeat, and Reminders

V0.5 architecture is frozen and implemented in Backend and Frontend. Migration
0005 was verified on temporary copies, backed up, and applied to real data after
explicit approval. Automated, manual visual, and final read-only acceptance passed.

### Feature Boundary

V0.5 contains only:

- Date-only and specific-time Deadlines.
- `daily`, `weekly` with selected weekdays, and `monthly` rules for days 1–28.
- Explicitly specified-time Reminders.

V0.5 does not contain repeated Time Blocks, relative Deadline Reminders,
background reminder services, complex recurrence protocols, external calendar
integration, AI scheduling, or other V0.6+ features.

### Deadline Model

Deadline is independent from `planned_date` and from the optional Time Block.
The proposed Task fields are:

- `deadline_date`: nullable local calendar date.
- `deadline_at_utc`: nullable UTC instant for a specific-time Deadline.
- `deadline_timezone`: nullable persisted IANA timezone used for date-only
  overdue evaluation and for interpreting a timed Deadline.

The valid states are:

```text
No Deadline:    deadline_date = NULL, deadline_at_utc = NULL,
                deadline_timezone = NULL
Date-only:      deadline_date != NULL, deadline_at_utc = NULL,
                deadline_timezone != NULL
Timed:          deadline_date != NULL, deadline_at_utc != NULL,
                deadline_timezone != NULL
```

For a timed Deadline, `deadline_date` must equal the local date of
`deadline_at_utc` in `deadline_timezone`. The Backend uses the saved timezone,
not the browser timezone, to determine overdue state. A date-only Deadline is
overdue when the Backend's local date in that saved timezone is later than the
saved date. A timed Deadline is overdue when the current UTC instant reaches
the saved instant. Completed Tasks retain their Deadline data but are not
reported as currently overdue; deleted Tasks are excluded from normal due and
overdue queries.

Deadline conversion uses `zoneinfo` and rejects invalid, ambiguous, or
nonexistent local times with HTTP 422. Deadline changes do not change
`planned_date`, a Time Block, Project membership, Category, Tags, or Task
status.

### Repeat Model and Lifecycle

V0.5 uses a normalized `recurrence_rules` table and adds a nullable paired
`recurrence_rule_id` plus `recurrence_occurrence_date` to `tasks`. A Task is an
occurrence snapshot; it may belong to at most one rule. Repeated Time Blocks
are not supported, so a recurring Task cannot create a repeated schedule.

Rules store frequency, the weekly weekday mask or monthly day when applicable,
the first local occurrence date, the persisted IANA timezone,
`stopped_at_utc`, timestamps, and an optimistic `version`. Daily rules do not
store a weekday mask; weekly rules require at least one selected weekday;
monthly rules accept only days 1–28.

The pair `recurrence_rule_id` and `recurrence_occurrence_date` is either both
NULL or both non-NULL. Occurrence dates are unique per rule, including rows
that are soft-deleted. `tasks.recurrence_rule_id` uses `ON DELETE RESTRICT` so a
referenced rule cannot be physically deleted; normal stopping uses
`stopped_at_utc`.

The lifecycle is deliberately explicit:

- Normal Task `DELETE` soft-deletes only the current occurrence and does not
  generate another one.
- For an active rule, `Skip` soft-deletes the current occurrence and creates
  its next occurrence in one transaction; a stopped rule creates nothing.
- For an active rule, `Complete` completes the current occurrence and creates
  its next occurrence in one transaction; a stopped rule creates nothing.
- The next date must be later than both the current occurrence date and today
  in the rule timezone. Missed dates are never backfilled.
- `Stop` stops the rule without deleting historical Tasks.
- `Restore` restores only the selected Task; it does not restart the rule or
  restore historical relationships.
- Explicit `Materialize` is the only standalone generation operation. It is
  never called from frontend startup or a GET endpoint, creates at most one
  occurrence, does not backfill, and is idempotent when a pending occurrence
  already exists. A candidate date that conflicts with any historical,
  including soft-deleted, occurrence is skipped.

Editing an occurrence changes that Task snapshot only. Editing a recurrence
rule changes future generation; already generated unfinished Tasks are not
rewritten, deleted, or silently rescheduled. Generated occurrences do not copy
absolute Deadlines, Reminders, or Time Blocks. Valid ordinary metadata such as
title, description, priority, Category, Tags, and Project may be copied under
service validation.

### Reminder Model and Runtime Behavior

Reminders are separate records so a Task can have more than one explicitly
specified trigger. Their persisted state is:

```text
pending → acknowledged
pending → dismissed
```

`due` is derived from `pending` plus `trigger_at_utc <= now_utc` and is never
stored. A due query may exclude completed or soft-deleted Tasks without
mutating their Reminder rows. `GET /api/v1/reminders/due` is strictly
read-only. Only explicit user actions call acknowledge or dismiss endpoints.

When the browser and Backend are running, frontend polling can surface due
Reminders. When the browser is closed but the Backend runs, due records remain
available but no reliable browser popup is promised. When the Backend is
stopped, real-time reminders are unavailable. On reopening, pending due
Reminders can be displayed. `sessionStorage` deduplicates dialogs within one
browser session; it is not a server-side acknowledgement.

### V0.5 Maintenance and Test Boundary

The independent V0.4 footer maintenance fix was completed in `b7b5114`;
`App.vue` reads the application version from the Frontend package metadata.
It is separate from Migration 0005 and V0.5 feature work.

V0.5 implementation and real-data acceptance are complete. The V0.5.1 UI/UX
patch is kept separate from the V0.5 Backend and Migration 0005 work; it does
not change API contracts or database schema. Future visual refinement remains
backlog work and is not automatically part of V0.6.

## Frozen V0.5.1 UI/UX Architecture

### Scope and Non-Goals

V0.5.1 refactors presentation and interaction consistency only. It keeps Vue 3,
TypeScript, Vite, Element Plus, and existing Hash navigation. No new business
feature, dependency, Router, Pinia, UI/state framework, or generic CRUD engine
is introduced. Backend APIs and Task/Project/Deadline/Recurrence/Reminder
semantics remain unchanged. Any improvement requiring Backend support must be
reported for separate approval rather than worked around or added silently.
No migration is created; the real schema remains
`0005_add_deadlines_recurrence_reminders`. Product metadata is `0.5.1` for
this released UI/UX patch; formal release status is determined by Git
tags.

### Design Tokens

Use CSS variables, Element Plus theme variables, and local component classes.
Avoid widespread selectors targeting Element Plus internal DOM. The following
values are the frozen and implemented design baseline:

| Token group | Baseline |
| --- | --- |
| Font family | System sans-serif; Chinese fallbacks PingFang SC and Microsoft YaHei; no downloaded fonts |
| Typography | Page title 28px/1.3; section title 18px/1.4; Task title 15px/1.5; body 14px/1.5; supporting copy 12px/1.5 |
| Spacing | 4, 8, 12, 16, 24, 32, 48px |
| Radius | Input/button 8px; cards and Dialogs 12px; badges 6px |
| Border | 1px solid #E6EBF2; stronger control border #CBD5E1 |
| Background | App #F5F7FB; surface #FFFFFF; subtle surface #F8FAFC |
| Text | Primary #152033; secondary #475467; supporting #667085 |
| Semantic colors | Brand #2F7D73; danger #B42318; warning #B54708; success #28705E; neutral #475467 |
| Focus | Visible 2px brand outline with 2px offset; no removal without an equivalent indicator |
| Control size | Default 36px; primary capture input 40px; compact controls no less than 32px |
| Content width | Task pages max 1040px; Projects max 1280px; Calendar fills available width, max 1680px |
| Sidebar | 220px normally; 192px in compact desktop layout |
| Workspace padding | Horizontal 32px normally, 20px in compact desktop; vertical 32px normally, 24px compact |

Normal Priority and organizational badges are neutral. High Priority and
overdue deadlines get emphasis; warning color is reserved for relevant
attention states such as due today. Completed Tasks remain visible with
restrained styling. Meaning cannot rely on color alone. Validate text contrast,
focus, and disabled-state legibility during implementation and visual review.
Use one primary button per action area, clear labels for inputs/selects,
consistent light-bordered cards, and a shared page-title/state design.

### Responsive and Navigation Rules

Acceptance viewports are 1440×900 and 1024×768. Compact desktop rules begin at
approximately 1200px (the initial breakpoint is max-width: 1199px), not only at
Header actions and filters may wrap; task content must shrink safely.
The Sidebar keeps 今天, 收件箱, 日历, 搜索, 项目 and existing Hash destinations.
Remove decorative 01–05 indices; do not invent counts. Keep the brand and
package-derived version. Active navigation has a visual and accessible state.

Week View may use a clearly bounded internal horizontal scroll area. Header,
date-only rows, and timeline columns stay aligned; horizontal overflow must
not propagate to the whole page. No mobile acceptance claim is made.

### TaskCard Contract

1. Primary: completion state, title, and main edit entry.
2. Secondary: Time Block, Deadline, and Project.
3. Supporting: Category, Tags, Repeat, and other low-frequency metadata.

Keep all existing actions accessible, including complete, restore, delete,
Undo, and skip. A More Menu is allowed, but actions cannot depend on hover.
Long titles/notes and many tags use restrained summaries with accessible full
details. Normal Priority is neutral; High/Overdue are prominent. Do not change
task-list membership, ordering, status, or deadline computation. Display-only
summaries must not introduce per-card Rule/Reminder API queries.

### TaskEditor Contract

Keep one TaskEditor, grouped into 基础信息, 日期与时间, 项目与分类, and 重复与提醒.
The Task save action is labelled 保存任务 and lives in the Dialog Footer.
Use a 700px desktop Dialog (within the approved 680–720px range), constrained
by available width. At 1024×768, the body scrolls internally and the Footer
stays accessible; date/select popovers must remain usable.

Repeat and Reminder use independent management areas and save actions marked
立即生效. Never offer 保存全部: Task, Rule, and Reminder have separate API,
version, and transaction boundaries. Before a Task exists, these areas are
non-editable with the explanation 保存任务后可设置重复和提醒.

Expanding/collapsing a section must preserve drafts, original values, touched
flags, and validation. Invalid sections open and expose their errors. An
independent operation must not silently close the editor and discard a Task
draft; either preserve it or require an explicit discard decision. Cancelling
the editor cannot undo already saved independent operations.

Keep omitted/null semantics: untouched Deadline/Schedule fields stay omitted;
explicit clearing sends null; clearing Tags sends []; Category and Project
clear values normalize undefined to null at the API boundary. Deadline remains
independent of planned_date and Time Block. Preserve stored timezones and
Task/Rule/Reminder versions. Keep time conflict confirmation and stale-version
handling distinct. Grouping is not a reason to change write payload semantics.

### Page and Calendar Contracts

Today uses compact statistics, Quick Capture, and Task List. Inbox puts Quick
Capture first. Search separates its copy and presentation responsibility from
Inbox while preserving existing query/filter semantics. Projects improves card
hierarchy and the Detail Header, not workflow; progress remains Backend-owned.

Calendar shares a compact toolbar and consistent Day/Week/Month design.
Date-only Tasks remain 未安排时间. Empty ranges retain Calendar structure;
loading and error are explicit and never presented as empty success. Short
Time Blocks prioritize title and start/end time, with accessible full details.
Overlapping blocks get display-only side-by-side lanes; do not move Tasks,
forbid overlap, or alter conflict override semantics. Keep true time positions
and duration geometry; do not inflate the scheduled interval to fit labels.
Columns and hour scale align across local scrolling. Completed Tasks remain
visible. Time Block formatting uses each Task's schedule_timezone; Today uses
Backend runtime local_date, not browser timezone. Date-only parsing remains
date-only. No Drag & Drop, Resize, Calendar library, or new range API is added.

### Reminder Contract

Add a global entry only for current due/pending Reminders, using existing
GET /api/v1/reminders/due and existing Task/Reminder actions. This is not a
global future/history Reminder Center. Opening, refreshing, polling, or merely
closing its container cannot acknowledge or dismiss a Reminder.

Keep 45-second polling and sessionStorage deduplication for automatic dialogs.
Deduplication must not hide pending items from the visible due list or alter
Backend state. Queue automatic prompts and prevent concurrent duplicate
prompts. Only explicit 确认提醒 or 关闭提醒 performs the corresponding mutation.
Acknowledgement failure never triggers dismissal. Polling/action failures show
an understandable error and Retry rather than a normal empty list. A failed
mutation preserves pending availability. Closing the global panel is not the
same operation as closing a Reminder. No OS/background notification guarantee
is made while the browser or Backend is stopped.

### Component and Test Boundaries

Permitted minimal extractions: PageHeader, PageState, Repeat management area,
Reminder management area, and Calendar Time Block positioning/display helpers.
App owns Hash navigation; TaskEditor owns Task drafts/payload construction;
Repeat and Reminder areas retain their own independent API actions. Avoid
generic CRUD engines, future-use abstractions, and unrelated service rewrites.

Each Phase 0–5 requires independent review and commit; see ROADMAP.md for
ordering. Relevant tests run at each phase, followed by the complete Phase 5
gate: Backend regression, Frontend Vitest, type-check, build, all 21 existing
Browser E2E scenarios plus focused additions, diff/secret checks, and manual
visual review at both desktop sizes. Existing assertions cannot be deleted
merely to turn tests green; copy/locator changes preserve behavioral checks.
Add editor grouping/draft/payload coverage, overlap and short-block coverage,
responsive overflow/Dialog coverage, and Reminder interaction/failure coverage.
Automated success does not imply manual visual acceptance. All write tests use
isolated temporary 0005 databases through the fail-closed E2E runner; never real
Tasks or Projects. Do not start or replace real services for this design phase.

## Timezone Strategy

- Database stores Time Block instants in UTC.
- `schedule_timezone` stores the IANA timezone used for that block.
- A new block defaults to the configured `DAYFLOW_TIMEZONE`.
- Backend uses Python `zoneinfo` for conversion and validation.
- Ambiguous and nonexistent local times caused by DST return HTTP 422; the
  Backend must not silently select an offset.
- Frontend formats a Time Block using the Task's `schedule_timezone`.
- Date-only `planned_date` values are never parsed as JavaScript UTC dates.
- Backend runtime date/timezone information is exposed through
  `GET /api/v1/runtime`, not through `/healthz`.

## Calendar Boundaries

Calendar uses one range query and the existing Task representation. Day, Week,
and Month views calculate an inclusive local-date range and call the same API.

Today remains a separate compatibility view based on `planned_date`; a
scheduled Task still appears in Today for its local planned date. Completed
Tasks remain visible according to the existing Today behavior, while deleted
Tasks remain hidden.

## Frontend Boundaries

The V0.3 frontend adds `CalendarView` and small Day/Week/Month renderers. It
continues to use Hash navigation, Vue 3, TypeScript, Vite, and Element Plus.
TaskEditor is the single schedule write surface and sends the structured
schedule payload, including explicit `schedule: null` when the user clears a
Time Block. Calendar uses Backend runtime `local_date` and
`schedule_timezone`-aware `Intl.DateTimeFormat` output.

V0.3 does not add Vue Router, Pinia, another global state library, a Calendar
library, or a Drag library. Task Editor remains the write surface for schedule
changes. Calendar refreshes after a successful mutation and has explicit
loading, error, empty, and conflict states.

## Error and Safety Boundaries

- API validation returns the stable `{error: {code, message, details}}` envelope.
- A stale Task `version` returns HTTP 409 and never overwrites newer data.
- A schedule conflict returns HTTP 409 and never partially applies the update.
- Every multi-field Task update commits once or rolls back completely.
- Every SQLAlchemy SQLite connection enables `PRAGMA foreign_keys=ON`, including
  migration and test connections.
- Database exceptions are logged, rolled back, and returned as a meaningful
  generic error; internal tracebacks are not sent to the browser.
- Tests configure dependency overrides backed by temporary SQLite files.
- Browser E2E uses a fail-closed `/tmp/dayflow-e2e-*` database and never falls
  back to `data/dayflow.sqlite3` or `data/backups/`.

## Migration Safety

V0.3 schema work is implemented as `0003_add_task_schedule`, based on
`0002_add_priority_categories_tags`; the real database advanced to `0004` after
the V0.4 migration.
`0001` and `0002` remain immutable.

V0.4 schema work is implemented as `0004_add_projects`, based on `0003`, and
has been tested on clean and real-data temporary copies before approval. It is
now applied to the real database. Existing Tasks retained all legacy values
and received `project_id = NULL`.

Before a real-data migration, the Backend must be stopped, a verified backup
must be created, and the migration must pass on a copy of the current database.
A downgrade must fail closed when any Project or Project relationship would be
lost.

## V0.3 Implementation Boundary

The approved order is:

```text
0003 implementation → temporary-copy migration test → Backend/API → Frontend Calendar
→ Vitest → Browser E2E → real-data migration approval → manual acceptance
```

The V0.4 implementation order was:

```text
0004 temporary migration → Project backend/model/API → backend regression
tests → Phase 1 review → Hash-based Project list/detail → Task Editor
integration → Vitest and Browser E2E → real-data backup and migration approval
→ final acceptance and database verification
```

No V0.4 product implementation may enter a release outside its approved
Project scope. V0.5+ features such as reminders, recurrence, AI, and external
integrations remain out of scope.
