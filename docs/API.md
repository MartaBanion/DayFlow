# API

## Base Path

```text
/api/v1
```

## Current Version

Current stable application version: `v0.6.0`. The annotated `v0.6.0` tag is the
published stable release. Deadline, Recurrence, Reminder, Backup, and Recovery
API contracts use the released V0.6 behavior. V0.7 Phase 0 is frozen and
committed; the Daily & Weekly Review API below is implemented and committed in
Phase 1, with its Frontend integration complete and committed in Phase 2. Phase
3 Full Acceptance is complete and V0.7 is ready for Release Preparation; the
`v0.7.0` release does not yet exist. The real database schema remains
`0005_add_deadlines_recurrence_reminders`, with no new migration.

## V0.7 Review API (Phase 1 and Phase 2 Complete; Phase 3 Acceptance Complete)

V0.7 adds one read-only resource with two fixed scopes:

```text
GET /api/v1/review?scope=today
GET /api/v1/review?scope=week
```

One endpoint with a constrained query parameter matches the existing DayFlow
style (`/tasks`, `/calendar`) and avoids duplicate Today/Week response models.
`scope` is required and is exactly `today` or `week`; other values return the
existing FastAPI 422 validation envelope. V0.7 provides no arbitrary start/end
dates, analytics language, pagination, write endpoint or Review history API.

### Response Contract

The response model is:

```json
{
  "scope": "today",
  "local_timezone": "Asia/Shanghai",
  "local_date": "2026-10-03",
  "range_start_utc": "2026-10-02T16:00:00.000000Z",
  "range_end_utc": "2026-10-03T16:00:00.000000Z",
  "generated_at_utc": "2026-10-03T04:00:00.000000Z",
  "completed": {
    "count": 0,
    "tasks": []
  },
  "overdue": {
    "count": 0,
    "tasks": []
  },
  "carryover": {
    "count": 0,
    "tasks": []
  },
  "projects": []
}
```

Real Task entries use the existing `TaskRead` shape. `count` always equals the
corresponding array length.
V0.7 returns all matches and has no pagination or truncation.

Fields:

| Field | Contract |
| --- | --- |
| `scope` | Echoes `today` or `week` |
| `local_timezone` | Configured DayFlow IANA timezone used for Review boundaries |
| `local_date` | Date in `local_timezone` at `generated_at_utc` |
| `range_start_utc` | Inclusive UTC completion-range boundary |
| `range_end_utc` | Exclusive UTC completion-range boundary |
| `generated_at_utc` | Single clock instant used by the entire response |
| `completed` | Current retained completed Tasks inside `[start, end)` |
| `overdue` | Current non-deleted pending Tasks overdue at `generated_at_utc` |
| `carryover` | Current non-deleted pending Tasks planned before `local_date` |
| `projects` | Current snapshots for all non-deleted Projects |

Today uses local midnight to next local midnight. Week uses Monday local
midnight to the following Monday local midnight. Each boundary is independently
converted through `local_timezone`, so DST may produce a range that is not
exactly 24 or 168 elapsed hours. Switching scope changes the completion range;
Overdue, Carryover and Project snapshots remain current at the common
`generated_at_utc` instant.

Each `projects` entry has this shape:

```json
{
  "id": "canonical-project-uuid",
  "name": "Project name",
  "status": "active",
  "task_count": 4,
  "completed_task_count": 1,
  "pending_task_count": 3,
  "overdue_task_count": 1,
  "progress_percent": 25,
  "latest_completed_at_utc": "2026-10-03T03:00:00.000000Z"
}
```

`latest_completed_at_utc` is nullable and means the maximum retained completion
timestamp among that Project's non-deleted Tasks that are still completed. It
is not Last Activity, Last Progress, or immutable history. Both active and
completed non-deleted Projects are returned; Project status remains independent
from Task status. There is no `stagnant`, `last_activity`, `attention_status` or
attention-score field in V0.7.

### Section Membership

Completed membership requires all of:

```text
deleted_at_utc IS NULL
status = completed
completed_at_utc IS NOT NULL
range_start_utc <= completed_at_utc < range_end_utc
```

Reopen and restore-to-pending clear `completed_at_utc`, soft deletion excludes
the Task, and re-completion uses only the latest timestamp. `updated_at_utc` is
never accepted as a completion fallback.

Current Overdue uses the released Deadline semantics at `generated_at_utc`:

- timed Deadline: `generated_at_utc >= deadline_at_utc`;
- date-only Deadline: the current date in the Task's saved
  `deadline_timezone` is later than `deadline_date`;
- only pending, non-deleted Tasks qualify.

Carryover requires `planned_date < local_date`, pending status and no soft
delete. A Deadline-only Task with no planned date is not Carryover. A Task may
appear in both Overdue and Carryover because they are separate facts.

Each recurrence occurrence is evaluated as its own Task. A completed
occurrence can qualify; its generated pending successor cannot. Skip, Delete,
Stop, and materialization are not completion events. GET Review never invokes
materialization.

### Ordering and Read-Only Contract

- Completed: newest `completed_at_utc`, then Task ID.
- Overdue: earliest `deadline_date`; timed Deadlines before date-only Deadlines
  on the same date; then timed instant, creation time and Task ID.
- Carryover: oldest `planned_date`, then creation time, Task ID.
- Projects: active before completed, then case-insensitive name and Project ID.

Review performs SELECT operations only. It never mutates Task, Project,
Recurrence or Reminder state; updates timestamps or versions; writes a cache,
snapshot or last-viewed value; creates files; performs Backup/Restore; or runs a
Migration. The service captures one request clock, uses bounded eager/grouped
queries, and must not perform a Task-table scan per Project.

### Error and Test Contract

Expected failures use the existing safe error envelope without internal paths
or stack traces. Invalid `scope` is 422. Invalid configured IANA timezone or a
database read failure returns a safe server error and performs no fallback
write or guessed time conversion.

Backend acceptance covers Daily/Week and DST boundaries, exact half-open
limits, Reopen/Delete/Restore/Repeat semantics, date-only and timed Overdue,
Carryover exclusions and overlap, Project aggregates/latest completion,
deterministic ordering, count/list agreement, common request clock, bounded
query shape and before/after proof that GET has no side effects.

## Frozen V0.6 Backup API / CLI Boundary

Status: released in `v0.6.0`. Phase 1 Create/List/Verify and Manifest V1 are committed. Phase 2
Maintenance UI is committed. Phase 3A adds state-only maintenance/startup
safety prototypes, and Phase 3B adds a read-only Restore Dry Run CLI. The Dry
Run creates a RestorePlan only; it does not create a lock, write restore state,
copy or replace SQLite files, migrate, or stop services. Phase 3C implements
TTY-confirmed execution only for independent databases in the system temporary
directory; project real data is rejected. Phase 3D recovery coordination and
explicit completed acknowledgement are implemented and reviewed. Phase 4
Reminder poll failure visibility, Retry, and automatic recovery are implemented
and reviewed. Isolated Restore execution is available only for independent
system-temporary databases; real project-data Restore remains prohibited and
current Real Restore Storage Qualification is `NOT QUALIFIED`. See Architecture
for prototype limits; no real recovery is authorized for the project database.

Phase 3C isolated execution uses `python -m app.maintenance_cli restore <backup_id>`.
Both input/output must be TTY and confirmation must exactly match
`RESTORE <canonical-backup-id>`. Non-TTY, wrong/EOF confirmation, execution JSON
and unsupported force flags refuse. CLI prints operation/backup/safety IDs and
verification result, explicitly leaving DayFlow stopped and maintenance
confirmation required. Success never clears the V2 maintenance marker. Dry Run
`--json` is unchanged. No HTTP Restore endpoint or real Restore permission exists.
The stable application version and tag are `v0.6.0`. Business API and schema
remain unchanged. NO DATABASE MIGRATION
REQUIRED; continue `0005_add_deadlines_recurrence_reminders` with no `0006`.

Phase 3D offline commands (no HTTP contract changes):

```text
python -m app.maintenance_cli status --json
python -m app.maintenance_cli storage-check --json
python -m app.maintenance_cli acknowledge <operation-id>
```

Status is read-only metadata inspection. Storage check creates only disposable
system-temp probes, never database or restore artifacts. Acknowledgement requires
stdin/stdout TTY and exact `ACKNOWLEDGE <canonical-operation-id>`; no force/yes
flags. It takes the exclusive gate, fully re-verifies a matching V2 completed
isolated Restore, commits a durable mirrored startup-clearance receipt before
touching active blockers, then removes only active blocking records as
post-commit housekeeping. All recovery evidence remains. Incomplete/V1/corrupt/
mismatched state refuses. A cleanup failure reports `acknowledge_committed`,
`cleanup_complete`, and `startup_allowed` separately: remaining blockers still
block; blocker absence is usable only when both receipt copies, completed
evidence and the current live DB fully re-verify. Retained Restore workspaces
without a matching durable receipt also block; absence of active markers alone
is never clearance. Neither
acknowledgement nor storage qualification authorizes real Restore or starts
services. Dry Run JSON remains unchanged.

Phase 1 endpoints:

| Method / path | Responsibility |
| --- | --- |
| `GET /api/v1/backups` | Read-only list of registered DayFlow Backups and last known verification Metadata |
| `POST /api/v1/backups` | Create consistent SQLite Online Backup and Manifest V1 |
| `POST /api/v1/backups/{backup_id}/verify` | Explicit read-only Backup verification; no automatic Manifest rebuild |

Accept Backup IDs, not arbitrary source/Restore absolute paths. List includes
time, filename, bytes, schema, integrity, and SHA summary, identifying unknown
creation time and stale verification honestly. Do not enumerate arbitrary
system files as restorable Backups or run full integrity scans implicitly.

Verify checks readability, hash, size, integrity, foreign keys, Alembic,
required tables, and critical structure. Distinguish valid-compatible,
valid-incompatible, corrupted, missing/unreadable, Manifest mismatch. These
are represented in Phase 1 by `status`: `valid`, `incompatible`, `corrupted`,
`unreadable`, `manifest_mismatch`. Exact supported schema
is `0005_add_deadlines_recurrence_reminders`; no automatic migration or Restore
for old, unknown, or newer schemas. Existing business responses do not change.

### Phase 1 Response and Error Contract

Phase 2 adds optional-consumer runtime status: `GET /api/v1/runtime` retains
`timezone` and `local_date`, and additionally returns `app_version` from Backend
metadata and nullable `database_schema` read from the active database's
`alembic_version`. It performs no integrity scan, backup or migration. The
Maintenance view displays a logical database-adjacent `backups/` location,
never a server absolute path. Existing Backup API contracts are unchanged.

Create returns HTTP 201 with Manifest V1 fields plus `compatible_for_restore`.
It accepts no body or query parameters; callers cannot choose source,
destination, filename, or root. Root derives from configured database parent
plus `backups`, so isolated databases use isolated Backup directories.
No real Backup smoke occurs during Phase 1.

List returns an array of the same Metadata shape, newest creation time first,
with descending Backup ID as stable tie-breaker. Compatibility reflects recorded
metadata, not a fresh integrity check. Invalid, oversized, missing, duplicate-ID
or unsafe registrations are skipped with a diagnostic warning. Unknown files,
symlinks, non-regular/hard-linked files, temporary files and orphan DBs are not
listed. Missing root returns `[]` without creating it.

Verify returns HTTP 200 for inspected registered files, including corrupted,
missing/unreadable data files, incompatibility and mismatch:

```json
{
  "backup_id": "canonical-uuid4",
  "verified_at_utc": "2026-10-01T00:00:00.000000Z",
  "status": "valid",
  "compatible_for_restore": true,
  "database_sha256": "64-lowercase-hex-characters",
  "file_size": 123456,
  "alembic_version": "0005_add_deadlines_recurrence_reminders",
  "integrity_check": "ok",
  "foreign_key_errors": 0,
  "structure_valid": true,
  "issues": []
}
```

Unavailable measured fields are `null`; `structure_valid` is false until checked.
Compatibility requires exact schema, required model columns/PKs/FKs/CHECKs/
indexes, clean integrity/FK checks, and matching Manifest SHA/size/schema.
Standalone published files with WAL/SHM/journal sidecars fail validation.
Older/unknown/newer readable schemas return `incompatible`; claimed current
schema with missing structure returns `corrupted`. No migration is attempted.

Manifest `verified_at_utc` is the immutable creation-time validation record.
Each Verify returns a new timestamp without updating either DB or Manifest.
Missing/bad Manifest is not silently registered; an unregistered ID returns 404.
Explicit historical Backup registration is deferred.

Errors use the existing envelope without internal paths or stack traces:

| Code | HTTP | Meaning |
| --- | --- | --- |
| `backup_id_invalid`, `backup_request_invalid` | 422 | Invalid ID or Create input |
| `backup_path_unsafe`, `backup_manifest_invalid` | 422 | Unsafe root/path or ambiguous registration |
| `backup_not_found` | 404 | No valid registration or required file unavailable |
| `backup_origin_rejected`, `backup_permission_denied` | 403 | Origin/file permission rejected |
| `backup_file_conflict` | 409 | Publication would overwrite a file |
| `backup_timeout` | 503 | Source busy or operation timed out |
| `backup_platform_unsupported` | 503 | Required Linux/WSL descriptor or hard-link support unavailable |
| `backup_schema_incompatible` | 422 | Source schema unsupported for Create |
| `backup_creation_failed`, `backup_io_failed` | 500 | Snapshot/SQLite/filesystem failure |
| `backup_registration_failed` | 500 | Data file may exist, but registration failed |

Create/Verify check Origin when present: allow configured Frontend Origin and
HTTP localhost/127.0.0.1 aliases at that configured port only. No-Origin local
tool requests are allowed. Foreign, `null`, or different-port Origins are rejected.
No Authentication system is introduced.

Root is controlled `data/backups/`. Reject traversal, absolute path input,
symlinks, outside-root resolution, non-regular files, and unexpected overwrite.
Manifest filenames are not trusted. Recoverable files require DayFlow naming
and verified registration. Revalidate identity/content before use; validate
browser request origin for filesystem-mutating local API operations.

There is no HTTP Restore-active-database endpoint. Maintenance CLI only:

- `restore --dry-run`: verify target and report plan/preconditions, never switch
  databases or stop services as a side effect.
- `restore`: explicit confirmation, maintenance lock, safe managed-service stop,
  database usage checks, verified Pre-Restore Backup, target revalidation,
  candidate validation, controlled switch, final validation, result log.

Unknown process identity or database usage fails closed. No automatic rollback,
downgrade, migration, or service restart. Preserve original DB/WAL/SHM, Safety
Backup, target, candidate and logs. Incomplete Restore blocks both Launcher
and Backend startup. Lock implementation is validated in Phase 3 prototypes.

Phase 3B Dry Run is invoked with
`python -m app.maintenance_cli restore --dry-run <backup_id>` (add `--json`
for a machine-readable `RestorePlan`). It reads the current database and calls
the existing read-only Backup Verify service for the target. The output
includes current and target metadata, Schema compatibility, future execution
steps, and the exact `No changes performed.` marker. Invalid, missing,
incompatible, corrupted, or mismatched targets return a non-zero result and do
not create maintenance state or modify any database artifact.

Frontend `#maintenance` (数据与备份) provides database status, Create/List/Verify,
destructive Restore summary and prepared CLI guidance. Incompatible entries
show reasons and no executable Restore instruction; no ordinary HTTP button
replaces the live database. No shutdown worker is included.

The only Reminder maintenance is visible polling failure, Retry, and clearing
the error on recovery, retaining 45-second polling and ack/dismiss. No new
Reminder endpoint, history, Snooze, OS notification, daemon, or Schema.

API acceptance covers WAL consistency, missing/corrupt/mismatched Metadata,
path attacks, read-only Verify and List, failed backup publication, stable
ordering, UI Loading/Empty/Error/Retry, and existing business regressions.
Restore tests are isolated; real Restore always needs separate approval.

## Existing System Endpoint

```http
GET /healthz
```

`/healthz` remains a lightweight liveness endpoint. Frontend runtime timezone
information is provided by the separate read-only endpoint below.

## Runtime Endpoint

```http
GET /api/v1/runtime
```

Response:

```json
{
  "timezone": "Asia/Shanghai",
  "local_date": "2026-09-26"
}
```

`timezone` is the configured IANA timezone. `local_date` is calculated by the
Backend in that timezone. Frontend “今天” logic must use this runtime value
instead of the browser's local date.

## V0.1 Endpoints

- `POST /api/v1/tasks`
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{id}`
- `PATCH /api/v1/tasks/{id}`
- `DELETE /api/v1/tasks/{id}` — Soft Delete
- `POST /api/v1/tasks/{id}/complete`
- `POST /api/v1/tasks/{id}/restore`
- `GET /api/v1/today?date=YYYY-MM-DD`

Mutation requests include the current `version` for optimistic concurrency
control. Existing request and response behavior remains compatible.

## V0.2 Endpoints and Filters

The existing Task paths remain unchanged. Task listing accepts:

```text
GET /api/v1/tasks?inbox=true
GET /api/v1/tasks?q=linux
GET /api/v1/tasks?priority=high
GET /api/v1/tasks?category_id=<uuid>&tag_id=<uuid>
```

`inbox=true` returns only pending, active Tasks with `planned_date = null`.
`q` is trimmed, parameterized, and searches title and description. Percent and
underscore are treated as literal characters. Category, Tag, and Priority are
structured filters.

Task Create and Patch accept:

```json
{
  "priority": "normal",
  "category_id": "<uuid-or-null>",
  "tag_ids": ["<uuid>"]
}
```

One Task Patch that changes multiple fields or relationships increments
`version` once. Relationship IDs are validated before any mutation; failures
roll back the entire transaction.

Category resources:

```text
GET    /api/v1/categories
POST   /api/v1/categories
PATCH  /api/v1/categories/{id}
DELETE /api/v1/categories/{id}
```

Tag resources:

```text
GET    /api/v1/tags
POST   /api/v1/tags
PATCH  /api/v1/tags/{id}
DELETE /api/v1/tags/{id}
```

## V0.3 Phase 1 Calendar API

V0.3 Phase 1 adds one read-only Calendar range endpoint:

```http
GET /api/v1/calendar?start=2026-09-21&end=2026-09-27
```

Rules:

- `start` and `end` are inclusive local dates in the configured runtime
  timezone.
- `start > end` returns HTTP 422.
- The initial implementation limits the range to a practical bounded window,
  such as 62 days.
- Soft-deleted Tasks are excluded.
- Completed Tasks remain visible, matching current Today behavior.
- Date-only Tasks and scheduled Tasks are both returned.
- The endpoint reuses the Task service and `TaskRead` representation; it does
  not create a second Task CRUD system.

Day, Week, and Month views calculate their local date range and call this same
endpoint. The frontend uses a Day range for Day View, seven dates for Week
View, and the visible month grid range for Month View; all stay within the
Backend's 62-day limit.

## V0.3 Phase 1 Task Schedule Write API

Task Create and Patch gain one structured `schedule` field:

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

`timezone` is optional. If omitted, the Backend uses `DAYFLOW_TIMEZONE`.
The value must be a valid IANA timezone when supplied.

### Partial Update Semantics

- `schedule` omitted: preserve the existing Time Block.
- `schedule: null`: clear the Time Block and preserve `planned_date` by
  default.
- `planned_date: null` plus `schedule: null`: clear the schedule and return the
  Task to Inbox.
- Changing only `planned_date` for a scheduled Task preserves local start/end
  clock times in the stored `schedule_timezone` and recalculates UTC instants.

The API response adds these nullable fields to `TaskRead`:

```json
{
  "start_at_utc": "2026-09-26T06:00:00.000000Z",
  "end_at_utc": "2026-09-26T07:00:00.000000Z",
  "schedule_timezone": "Asia/Shanghai"
}
```

When no Time Block exists, all three values are `null`.

The Backend must enforce:

- A Time Block requires `planned_date`.
- The start and end values are both present.
- The end is later than the start.
- `planned_date` equals the local date of the start instant in
  `schedule_timezone`.
- V0.3 Time Blocks do not cross a local date.
- DST ambiguous or nonexistent local times return HTTP 422.

## Conflict Handling

The Backend checks a new or changed Time Block against active, pending,
non-deleted Tasks using UTC intervals.

When overlap is found, the default response is:

```http
409 Conflict
```

```json
{
  "error": {
    "code": "schedule_conflict",
    "message": "The requested time overlaps another task",
    "details": {
      "task_ids": ["..."]
    }
  }
}
```

The user may explicitly confirm the overlap by retrying the same mutation with
the one-request query flag:

```text
PATCH /api/v1/tasks/{id}?version=3&allow_schedule_conflict=true
```

The flag is not persisted. The Backend never automatically moves or reschedules
another Task.

Conflict and stale-version failures are atomic: no Task field, relationship,
Time Block, or version may be partially changed.

## Date and Time Serialization

- Date-only values use `YYYY-MM-DD`.
- Stored and returned instants use RFC3339 UTC strings ending in `Z`.
- IANA timezone names use values such as `Asia/Shanghai`.
- The API does not treat `planned_date` as a UTC date.
- Frontend must not parse a date-only value through JavaScript UTC conversion.

## Error Contract

Errors use the existing envelope:

```json
{
  "error": {
    "code": "task_version_conflict",
    "message": "Task changed since it was loaded; refresh before saving",
    "details": {}
  }
}
```

V0.3 Phase 1 adds or uses:

- `schedule_validation_error` — invalid date/time, timezone, or schedule state.
- `calendar_range_invalid` — invalid or oversized Calendar date range.
- `schedule_conflict` — overlapping active pending Task.
- `task_version_conflict` — stale optimistic version.
- `task_not_found` — missing or inaccessible Task.

## Transaction and Version Rules

Task fields, relationships, and schedule changes in one PATCH execute in one
transaction. Any validation, conflict, or stale-version failure rolls back all
changes.

One successful Task PATCH increments `version` at most once, regardless of how
many fields and relationships change.

## V0.4 Project API

V0.4 adds a minimal Project resource. It reuses the existing Task resource for
Project membership and filtering; it does not create a second Project-specific
Task CRUD surface.

### Project Endpoints

```text
GET    /api/v1/projects
POST   /api/v1/projects
GET    /api/v1/projects/{id}
PATCH  /api/v1/projects/{id}
DELETE /api/v1/projects/{id}
POST   /api/v1/projects/{id}/complete
POST   /api/v1/projects/{id}/reopen
POST   /api/v1/projects/{id}/restore
```

Project list/detail responses include dynamically calculated `task_count`,
`completed_task_count`, and `progress_percent`; these values are not stored in
the database. Project list calculation must use grouped aggregates or an
equivalent bounded query plan, not one count query per Project.

A minimal response shape is:

```json
{
  "id": "project-uuid",
  "name": "学习 Linux",
  "description": null,
  "status": "active",
  "created_at_utc": "2026-09-28T00:00:00.000000Z",
  "updated_at_utc": "2026-09-28T00:00:00.000000Z",
  "completed_at_utc": null,
  "deleted_at_utc": null,
  "version": 1,
  "task_count": 3,
  "completed_task_count": 1,
  "progress_percent": 33
}
```

`POST` requires a non-empty trimmed `name`; `description` is optional. `PATCH`
supports `name` and `description` as partial fields and requires the current
Project `version`. `GET /projects` excludes soft-deleted Projects by default;
pass `include_deleted=true` when a management view needs to discover
soft-deleted Projects for restoration. The restore action addresses deleted
records without adding a recycle-bin feature. The existing `status` filter
continues to apply with either list mode.

Lifecycle semantics are explicit:

- `complete` sets Project status to `completed` and `completed_at_utc`; it does
  not complete any Task.
- `reopen` sets status to `active` and clears `completed_at_utc`.
- `DELETE` soft-deletes the Project and clears `project_id` from every related
  Task, including soft-deleted Tasks, in one transaction. Each affected Task
  version and `updated_at_utc` changes once at most.
- `restore` clears only the Project's soft-delete marker and preserves its
  status/completion timestamp. It does not recreate previous Task
  relationships. If an active Project already has the same name, restore
  returns HTTP 409.

Duplicate active names return HTTP 409. Empty/invalid names return HTTP 422.
Missing Projects return HTTP 404, and stale Project versions return HTTP 409.
The existing error envelope is used with resource-specific error codes such as
`project_name_conflict`, `project_version_conflict`, and `project_not_found`.

### Task Project Integration

Task Create and PATCH gain an optional nullable field:

```json
{
  "project_id": "project-uuid-or-null"
}
```

Omitted `project_id` preserves the current relationship; `null` clears it; a
UUID assigns the Task to that Project. A Task may belong to at most one
Project. The existing `version` is incremented only once when a successful
PATCH changes Project membership together with other Task fields. Missing or
deleted Project IDs fail before mutation and roll back the whole request.

`TaskRead` adds nullable `project_id` and a compact nullable Project summary
when the relationship exists. The addition is backward-compatible for clients
that ignore unknown response fields. Project deletion makes both values null
for affected Tasks.

Task listing and Search add the structured filter:

```text
GET /api/v1/tasks?project_id=<uuid>
```

The filter is exact and does not alter the existing Inbox, Today, Calendar,
Priority, Category, Tag, or title/description `q` semantics. Project detail
uses the same query rather than `GET /projects/{id}/tasks`.

### Project Transaction Rules

Every Project mutation validates input and optimistic version before changing
stored state. Project delete performs Project soft delete, relationship
clearing for all associated Tasks, Task timestamp/version updates, and commit
in one transaction. Any validation, name conflict, stale version, foreign-key
failure, or other critical error rolls the transaction back. Project complete,
reopen, and restore change only the Project and increment its version once.

Project restore does not restore historical Task membership. Project status and
Task status are independent: completing a Task changes progress only, while
completing a Project does not complete its Tasks.

## V0.4 Compatibility and Test Contract

The V0.1–V0.3.1 endpoints retain their paths and semantics. Existing Tasks
migrate with `project_id = null`; Inbox remains `planned_date IS NULL` plus its
existing active/pending rules, and Calendar/Today continue to use
`planned_date` and schedule fields as before.

The V0.4 test gate must cover Project CRUD, duplicate/validation errors,
complete/reopen/restore, assignment and clearing, Project deletion preserving
Tasks, detachment of soft-deleted Tasks, one-version-per-affected-Task,
dynamic progress, stale-version rollback, migration compatibility, and Project
filters in Search, Inbox, Today, and Calendar. Frontend and Browser E2E must
cover Hash navigation, Project list/detail, Task Editor assignment/clear,
progress, lifecycle actions, error states, refresh persistence, and continued
V0.3 regression coverage.

## V0.5 API Contract

V0.5 architecture is frozen and the endpoints below are implemented and used by
the Frontend. The approved real database is at `0005`; final acceptance passed.

### Deadline Write and Read Shape

Task Create and Patch accept an optional structured `deadline` value:

```json
{
  "deadline": {
    "date": "2026-10-20",
    "time": "17:00",
    "timezone": "Asia/Shanghai"
  }
}
```

`time` is optional. Omitting it creates a date-only Deadline. `timezone` may be
omitted and then defaults to `DAYFLOW_TIMEZONE`; the resolved IANA timezone is
persisted. The API returns the normalized fields:

```json
{
  "deadline_date": "2026-10-20",
  "deadline_at_utc": "2026-10-20T09:00:00.000000Z",
  "deadline_timezone": "Asia/Shanghai",
  "deadline_status": "upcoming"
}
```

For a date-only Deadline, `deadline_at_utc` is `null`. With no Deadline, all
three stored fields are `null` and the computed status is `none`.

Partial-update semantics are:

- `deadline` omitted: preserve the existing Deadline.
- `deadline: null`: clear all Deadline fields.
- Date-only values use the saved timezone and are overdue only after the
  Backend local date passes the saved `deadline_date`.
- Timed values are converted from local date/time to UTC in the saved timezone.
- Invalid timezone, ambiguous/nonexistent DST time, or inconsistent local date
  returns HTTP 422.

Deadline updates never alter `planned_date`, a Time Block, Project membership,
Category, Tags, or Task status. Completion preserves the stored Deadline;
normal due/overdue queries exclude completed and soft-deleted Tasks.

### Recurrence Endpoints

The minimal recurrence contract is:

```text
POST /api/v1/tasks/{id}/recurrence
GET  /api/v1/recurrence-rules/{id}
PATCH /api/v1/recurrence-rules/{id}
POST /api/v1/recurrence-rules/{id}/stop
POST /api/v1/recurrence-rules/{id}/materialize
POST /api/v1/tasks/{id}/skip
```

Creating a rule requires `daily`, `weekly` with selected weekdays, or
`monthly` with a day from 1 through 28, plus `starts_on` and an IANA timezone.
The attached Task must have a planned date and no Time Block in this first
version. Creating a rule requires the current Task `version` in the JSON body.
Rule mutation requires the current rule `version`; occurrence Task
mutation continues to require the Task `version`.

Successful generation advances the rule version once within the same transaction,
preventing concurrent stop/edit/generation from using an obsolete rule snapshot.
Returning an existing pending occurrence does not change either version.

The lifecycle contract is:

- Completing an occurrence of an active rule completes it and creates the next
  occurrence in the same transaction. A stopped rule creates nothing.
- `POST /api/v1/tasks/{id}/skip` soft-deletes the current occurrence of an
  active rule and creates the next one in the same transaction; a stopped rule
  creates nothing.
- A normal Task `DELETE` soft-deletes only the current occurrence and creates
  nothing.
- The next occurrence date is strictly later than both the current occurrence
  date and today in the rule timezone. Missed occurrences are not backfilled.
- Stopping a rule sets `stopped_at_utc` and preserves historical Tasks.
- Restoring a Task restores only that Task and does not restart its rule.
- `materialize` is explicit, never called by startup or a GET, creates at most
  one occurrence, and returns the existing pending occurrence when one already
  exists. Historical soft-deleted occurrences still reserve their dates.

Rule edits affect future materialization only. Existing generated unfinished
Tasks are snapshots and are not rewritten. Generated occurrences do not copy
absolute Deadlines, Reminders, or Time Blocks; ordinary metadata is copied only
after current validity checks. The pair of recurrence fields is always set or
cleared together.

Successful multi-step occurrence operations are one transaction. Validation,
stale version, date collision, or database failure rolls back both the current
occurrence change and any attempted next-occurrence creation. A stale version
cannot be bypassed by materialization or a skip request.

### Reminder Endpoints

The initial Reminder contract is:

```text
GET    /api/v1/tasks/{id}/reminders
POST   /api/v1/tasks/{id}/reminders
PATCH  /api/v1/reminders/{id}
DELETE /api/v1/reminders/{id}
GET    /api/v1/reminders/due
POST   /api/v1/reminders/{id}/acknowledge
POST   /api/v1/reminders/{id}/dismiss
```

Reminders accept an explicitly specified local trigger time and timezone and
store the normalized UTC instant. They do not inherit or copy a Deadline, and
repeat generation does not copy them. Status is only `pending`,
`acknowledged`, or `dismissed`.

`GET /api/v1/reminders/due` is pure read. It returns pending reminders whose
UTC trigger is due and whose Task is not completed or soft-deleted. It never
changes status or timestamps. Only explicit acknowledge/dismiss requests
change state, using the current Reminder `version` and returning HTTP 409 for
stale updates. Frontend polling may use `sessionStorage` to deduplicate
dialogs; this does not replace server acknowledgement.

Repeated acknowledge/dismiss requests have no additional side effects: an old
version returns `409 reminder_version_conflict`; a current version applied to
an already handled reminder returns `409 reminder_state_conflict`. An explicit
time edit resets the reminder to pending and clears both handled timestamps.

### V0.5 Errors and Test Contract

Expected validation and conflict codes include:

- `deadline_validation_error` — invalid local date/time, timezone, or DST
  state.
- `recurrence_validation_error` — invalid frequency, selector, date, or
  unsupported scheduled Task.
- `recurrence_rule_conflict` — occurrence date or rule state conflict.
- `recurrence_version_conflict` — stale rule version.
- `reminder_validation_error` — invalid trigger or timezone.
- `reminder_version_conflict` — stale Reminder version.

The V0.5 test gate must cover upgrade `0004 → 0005`, preservation of all
existing Task/Project/Category/Tag/Time Block data, Deadline date-only and
timed behavior, UTC and DST validation, recurrence next-date calculation,
missed-date no-backfill, delete/skip/complete/stop/restore semantics,
materialize idempotence, historical soft-delete uniqueness, transaction
rollback, Reminder due/acknowledge/dismiss behavior, read-only due polling,
Frontend error states, and V0.4 regression plus Browser E2E coverage.
