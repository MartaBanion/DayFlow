# Database

## Runtime Database

```text
data/dayflow.sqlite3
```

The file is personal runtime data and must never be committed. Backend writes
must occur through services and transactions.

## Current Schema: `0005` / V0.6.0 Release Preparation

The real database is currently at:

```text
0005_add_deadlines_recurrence_reminders
```

Current application version: `v0.6.0` (Release Preparation). V0.5.1 is the
last published stable tag. V0.6.0 changes no business schema or migration; the
real schema remains `0005_add_deadlines_recurrence_reminders`. The `v0.6.0` tag
has not been created.

V0.1 contains the original `tasks` fields. V0.2 adds organization fields and
the normalized metadata tables. V0.3 adds the optional single-Task Time Block
columns.

### Tasks

| Column | SQLite type | Nullable | Meaning |
| --- | --- | ---: | --- |
| `id` | `VARCHAR(36)` | no | Application-generated UUID string |
| `title` | `VARCHAR(500)` | no | Required user-facing title |
| `description` | `TEXT` | yes | Optional notes |
| `status` | `VARCHAR(20)` | no | `pending` or `completed` |
| `planned_date` | `DATE` | yes | Local date-only planning value |
| `created_at_utc` | `VARCHAR(32)` | no | UTC RFC3339 instant ending in `Z` |
| `updated_at_utc` | `VARCHAR(32)` | no | UTC RFC3339 instant ending in `Z` |
| `completed_at_utc` | `VARCHAR(32)` | yes | Set when completed |
| `deleted_at_utc` | `VARCHAR(32)` | yes | Soft-delete instant |
| `version` | `INTEGER` | no | Starts at 1 and increments on mutation |
| `priority` | `VARCHAR(20)` | no | `low`, `normal`, or `high` |
| `category_id` | `VARCHAR(36)` | yes | Nullable Category foreign key |
| `start_at_utc` | `VARCHAR(32)` | yes | Optional Time Block start UTC instant |
| `end_at_utc` | `VARCHAR(32)` | yes | Optional Time Block end UTC instant |
| `schedule_timezone` | `VARCHAR(64)` | yes | IANA timezone for the Time Block |
| `project_id` | `VARCHAR(36)` | yes | Nullable Project foreign key |

### Organization Tables

- `categories`: UUID and case-insensitive unique name.
- `tags`: UUID and case-insensitive unique name.
- `task_tags`: normalized composite `(task_id, tag_id)` relationship table.

Category deletion uses `ON DELETE SET NULL`. Tag deletion uses `ON DELETE
CASCADE` for `task_tags`. Deletion of either metadata object never deletes a
Task. Affected Task versions are updated by the service in one transaction.

## V0.2 State Rules

- Inbox is `planned_date IS NULL AND deleted_at_utc IS NULL AND status = 'pending'`.
- Completing a pending Task sets `status=completed` and
  `completed_at_utc`.
- Restoring a Task returns it to `pending` and clears `completed_at_utc`.
- Soft delete sets `deleted_at_utc` and increments `version` without erasing
  the row.
- Normal list, Today, Inbox, and Search queries exclude soft-deleted Tasks.
- The restore endpoint can recover a soft-deleted row using its current version.

## V0.3 Schema: `0003_add_task_schedule`

The migration is implemented, tested, and applied to the real database. It
added only these nullable columns to `tasks`:

| Column | SQLite type | Nullable | Meaning |
| --- | --- | ---: | --- |
| `start_at_utc` | `VARCHAR(32)` | yes | Time Block start UTC instant |
| `end_at_utc` | `VARCHAR(32)` | yes | Time Block end UTC instant |
| `schedule_timezone` | `VARCHAR(64)` | yes | IANA timezone for the Time Block |

No existing Task is assigned a time during migration. Existing rows retain:

- `id`
- `status`
- `planned_date`
- `completed_at_utc`
- `deleted_at_utc`
- `version`

Existing Tasks were migrated with all three new columns `NULL`; no legacy Task
was assigned a schedule by the migration.

### Structural Constraints

The migration should add only database-level structural constraints:

1. `start_at_utc` and `end_at_utc` are both `NULL` or both non-`NULL`.
2. A non-`NULL` Time Block requires a non-`NULL` `planned_date`.
3. A non-`NULL` Time Block requires a non-`NULL` `schedule_timezone`.

The following remain Backend business validation rather than SQLite-only
constraints:

- IANA timezone validity.
- DST ambiguous/nonexistent local times.
- `end_at_utc` later than `start_at_utc`.
- `planned_date` matching the local date of `start_at_utc`.
- V0.3 same-local-date restriction for Time Blocks.

The existing `(planned_date, deleted_at_utc)` index is sufficient for the
initial Calendar range query. No additional index is planned until a real query
plan shows a need.

### Time Block State Semantics

```text
Inbox:       planned_date = NULL, start/end/timezone = NULL
Date-only:   planned_date != NULL, start/end/timezone = NULL
Scheduled:   planned_date != NULL, start/end/timezone != NULL
```

The UI label for the date-only state is “未安排时间”. It must not imply that
the Task has a full-day time block.

One Task has at most one Time Block. A separate `time_blocks` table is deferred
until multiple blocks, split execution, or external Calendar Events become a
real requirement.

## V0.4 Schema: `0004_add_projects`

`0004_add_projects` depends on `0003_add_task_schedule` and does not modify
`0001`, `0002`, or `0003`. It is implemented, tested on temporary and real-data
copies, and applied to the real database after backup and explicit approval.

### Projects

| Column | SQLite type | Nullable | Meaning |
| --- | --- | ---: | --- |
| `id` | `VARCHAR(36)` | no | Application-generated UUID string |
| `name` | `VARCHAR(200)` | no | Trimmed Project name |
| `description` | `TEXT` | yes | Optional Project description |
| `status` | `VARCHAR(20)` | no | `active` or `completed` |
| `created_at_utc` | `VARCHAR(32)` | no | Creation UTC instant |
| `updated_at_utc` | `VARCHAR(32)` | no | Last Project mutation UTC instant |
| `completed_at_utc` | `VARCHAR(32)` | yes | Set only for completed Projects |
| `deleted_at_utc` | `VARCHAR(32)` | yes | Project soft-delete UTC instant |
| `version` | `INTEGER` | no | Starts at 1; increments once per mutation |

`tasks.project_id` will be a nullable foreign key to `projects.id` with
`ON DELETE SET NULL`, plus an index for Project task queries. The service must
clear all associated Task relationships before soft-deleting a Project, so the
logical delete also covers soft-deleted Tasks and updates each affected Task
version once. Physical FK deletion is not the normal Project delete path.

The migration will add a partial unique index for trimmed/case-insensitive
Project names where `deleted_at_utc IS NULL`. SQLite `NOCASE` is sufficient for
the current single-user scope but does not provide full Unicode case folding.
Name validation remains explicit at the API/service boundary.

Status and relationship constraints are structural (`active`/`completed`,
valid nullable FK); lifecycle rules, timestamps, and version transitions remain
service rules. Progress is not a column: it is calculated from active Tasks as
`completed / total`, with soft-deleted Tasks excluded and an empty Project at
0%.

### Migration Safety and Downgrade

The upgrade from the V0.3.1 schema retained all existing Tasks'
IDs, titles, descriptions, statuses, dates, completion/deletion timestamps,
priorities, Categories, Tags, schedule fields, and versions. Their new
`project_id` value must be `NULL`. SQLite batch migration is used where table
recreation is required, with foreign-key enforcement enabled on every
connection. Because recreating `tasks` can cascade-delete rows from
`task_tags`, the migration temporarily backs up and restores the normalized
tag relationships around the batch operation.

Downgrade must fail closed if any Project row exists or any Task has a
non-`NULL` `project_id`; it must never silently discard Project data or
relationships. Downgrade is safe only for a test database whose Project table
is empty and whose Task relationships are all `NULL`.

The real-data migration followed the same procedure: Backend stopped, verified
pre-migration backup created, temporary-copy migration and regression checks
completed, then explicit approval was obtained before applying `0004`.

## V0.5 Schema: `0005_add_deadlines_recurrence_reminders`

The V0.5 Backend and Migration implementation was validated on isolated databases
and real-data copies before backup and explicit approval to migrate the real
database. The approved real schema is now `0005`. Migration `0005` depends on
`0004`; migrations `0001` through `0004` remain unchanged.

### Task Deadline Columns

Migration `0005` adds these nullable columns to `tasks`:

| Column | SQLite type | Nullable | Meaning |
| --- | --- | ---: | --- |
| `deadline_date` | `DATE` | yes | Local date of a date-only or timed Deadline |
| `deadline_at_utc` | `VARCHAR(32)` | yes | UTC instant for a specific-time Deadline |
| `deadline_timezone` | `VARCHAR(64)` | yes | Persisted IANA timezone for Deadline interpretation |
| `recurrence_rule_id` | `VARCHAR(36)` | yes | Nullable FK to `recurrence_rules.id` |
| `recurrence_occurrence_date` | `DATE` | yes | Local occurrence date within the rule timezone |

Database checks must allow only these Deadline states:

```text
all three NULL
or deadline_date and deadline_timezone NOT NULL with deadline_at_utc NULL
or all three NOT NULL
```

The database does not validate IANA names, DST, or the relationship between a
UTC instant and a local date; those remain Backend business validation. For a
timed Deadline, the service must ensure `deadline_date` is the local date of
`deadline_at_utc` in `deadline_timezone`.

The recurrence columns use a paired check: `recurrence_rule_id` and
`recurrence_occurrence_date` are both NULL or both non-NULL. A unique index on
`(recurrence_rule_id, recurrence_occurrence_date)` prevents duplicate
occurrences for one rule. Because soft-deleted rows remain in the table, they
also reserve their historical occurrence dates.

### `recurrence_rules`

The normalized table contains:

| Column | SQLite type | Nullable | Meaning |
| --- | --- | ---: | --- |
| `id` | `VARCHAR(36)` | no | Application-generated UUID |
| `frequency` | `VARCHAR(20)` | no | `daily`, `weekly`, or `monthly` |
| `weekdays_mask` | `INTEGER` | yes | Selected weekdays for weekly rules |
| `month_day` | `INTEGER` | yes | Day 1–28 for monthly rules |
| `starts_on` | `DATE` | no | First local occurrence date |
| `timezone` | `VARCHAR(64)` | no | Persisted IANA rule timezone |
| `stopped_at_utc` | `VARCHAR(32)` | yes | Set when the rule is stopped |
| `created_at_utc` | `VARCHAR(32)` | no | Creation UTC instant |
| `updated_at_utc` | `VARCHAR(32)` | no | Last rule mutation UTC instant |
| `version` | `INTEGER` | no | Optimistic version, starting at 1 |

Structural checks require weekly rules to have a non-empty weekday mask,
monthly rules to have `month_day` between 1 and 28, and daily rules to have
neither weekly nor monthly selector. IANA validity and the exact next-date
algorithm remain service rules. `tasks.recurrence_rule_id` references this
table with `ON DELETE RESTRICT`; a stopped rule is retained rather than
physically deleted.

### `reminders`

Reminders are separate records for explicitly specified trigger times:

| Column | SQLite type | Nullable | Meaning |
| --- | --- | ---: | --- |
| `id` | `VARCHAR(36)` | no | Application-generated UUID |
| `task_id` | `VARCHAR(36)` | no | FK to `tasks.id`, `ON DELETE CASCADE` |
| `trigger_at_utc` | `VARCHAR(32)` | no | UTC trigger instant |
| `reminder_timezone` | `VARCHAR(64)` | no | Persisted source/display timezone |
| `status` | `VARCHAR(20)` | no | `pending`, `acknowledged`, or `dismissed` |
| `acknowledged_at_utc` | `VARCHAR(32)` | yes | Explicit acknowledgement time |
| `dismissed_at_utc` | `VARCHAR(32)` | yes | Explicit dismissal time |
| `created_at_utc` | `VARCHAR(32)` | no | Creation UTC instant |
| `updated_at_utc` | `VARCHAR(32)` | no | Last state mutation UTC instant |
| `version` | `INTEGER` | no | Optimistic version, starting at 1 |

Database checks constrain status and timestamp combinations. `due` is not a
stored status: it is a read-only query condition over `pending` reminders whose
trigger has passed. Completed or soft-deleted Tasks are excluded from due
results without changing Reminder rows. Reminder state changes are explicit
transactions; polling GETs never acknowledge or dismiss implicitly.

### Indexes and Foreign Keys

The migration adds bounded-query indexes for:

- `tasks(deadline_date, deleted_at_utc, status)` for date Deadline queries.
- `tasks(recurrence_rule_id, recurrence_occurrence_date)` for occurrence
  lookup and idempotent generation.
- `recurrence_rules(stopped_at_utc)` for active-rule selection.
- `reminders(status, trigger_at_utc)` for due lookup.
- `reminders(task_id, status)` for Task reminder management.

Foreign-key enforcement remains `PRAGMA foreign_keys=ON` on every SQLAlchemy
connection, test connection, and migration connection. The recurrence FK is
`ON DELETE RESTRICT`; the Reminder-to-Task FK is `ON DELETE CASCADE`. Normal
Task deletion remains soft delete, so it does not silently remove reminders.

### Migration and Downgrade Safety

SQLite batch migration must preserve all existing Task fields, Project
relationships, Category/Tag rows, `task_tags`, and Time Block values. Existing
Tasks receive `NULL` Deadline and recurrence fields. No existing Task receives
a generated occurrence, Reminder, or copied Deadline during upgrade.

Downgrade must fail closed if any Deadline column is populated, any recurrence
rule exists, any Task references a rule, any occurrence row exists, or any
Reminder exists. It is safe only on a test database with all V0.5 data empty.
The downgrade must never silently discard Deadline, recurrence, or Reminder
data.

## Completed V0.4 Migration Procedure

The following procedure was completed before applying `0004_add_projects` to
real data:

1. Keep the Backend stopped.
2. Create and verify a pre-migration backup.
3. Copy the real V0.3.1 database to a temporary test location.
4. Run `0004` only against the copy.
5. Verify `integrity_check` and `foreign_key_check`.
6. Verify Alembic head and all legacy Task fields.
7. Verify `project_id` is `NULL` for existing Tasks and all V0.3 schedule
   fields remain unchanged.
8. Test Project CRUD, assignment/clearing, delete detach semantics, progress,
   lifecycle transitions, rollback, and restart persistence on the copy.
9. Run the complete Backend, Frontend, and Browser regression suites.
10. Receive explicit approval before upgrading the real database.

SQLite batch migration must be used where table recreation is required. The
migration must not edit `0001_create_tasks` or
`0002_add_priority_categories_tags`.

## Downgrade

Downgrade of `0003` is potentially destructive because it removes saved Time
Block data. It must fail closed if any row has a non-`NULL` schedule field. A
downgrade is only safe when all three new columns are empty, such as on a clean
test database.

## Backup

The last stable v0.5.1 release has manual verified maintenance backups. V0.6.0
Release Preparation includes Phase 1 development
implements Backup Core/Create/List/Verify. Phase 2 Maintenance UI and Phase 3B
read-only Dry Run and Phase 3C isolated execution are committed and reviewed.
Phase 3D recovery coordination and Phase 4 Reminder poll failure visibility are
committed and reviewed. Phase 5 Full Acceptance passed all functional,
regression, data-safety, migration, launcher, restore-boundary, and repository
hygiene gates. V0.6.0 Full Acceptance is PASS; the release Commit and Tag have
not been created. Isolated Restore execution is verified only for independent
system-temporary databases. Real project-database Restore remains prohibited,
and Real Restore Storage Qualification is currently `NOT QUALIFIED`.
Use SQLite Online Backup API for consistency,
including committed WAL data; never assume copying an active main file is safe.

### V0.6 Filesystem Model (Backup Implemented; Restore Execution Design Frozen)

NO DATABASE MIGRATION REQUIRED. Keep `0005_add_deadlines_recurrence_reminders`;
do not create `0006`, modify historic migrations, or add Backup business tables.
Default controlled root: `data/backups/`. Backup DBs, JSON Metadata, temporary
Restore candidates, original DB/WAL/SHM material, maintenance state and logs
must be in controlled Git-ignored locations. No automatic retention cleanup.

Use `sqlite3.Connection.backup()`; stage uniquely named files, close the target,
verify integrity/FK/schema/structure, compute hash and size, publish database
without overwrite, then publish Manifest. Unfinished files cannot be Restore
candidates. Published Backup databases must never be modified.

Each Backup has Manifest V1 (`*.json`):

| Field | Meaning |
| --- | --- |
| `backup_version` | Manifest format version `1` |
| `backup_id` | Unique API/CLI file identity |
| `filename` | Backup basename, validated rather than trusted |
| `created_at_utc` | Backup creation UTC time |
| `app_version` | Application version at creation |
| `alembic_version` | Verified database version |
| `database_sha256` | Closed Backup file SHA-256 |
| `file_size` | Bytes |
| `integrity_check` | Recorded verification result |
| `foreign_key_errors` | Recorded error count |
| `verified_at_utc` | Recorded verification UTC time |
| `source_database` | Logical source identity, e.g. `dayflow.sqlite3` |

Manifest is not database truth; no Task contents, Token, Password, or Secret.
Missing Manifest permits read-only verification and explicit registration.
Compute hash/size/schema again, but do not invent unknown creation time or
application version. Filesystem mtime may be shown as auxiliary information.
Verification does not automatically rewrite Metadata or Backup bytes.

Phase 1 Manifest verification time records creation-time validation only.
Explicit Verify returns a new time without editing Manifest. Root is derived
from configured source DB parent / `backups`, not API input. UUID4 IDs are
independent of generated timestamp/random filenames. List ignores malformed
registrations, incomplete artifacts and orphan DBs; no automatic registration.
Source opens with `mode=ro`. Online Backup includes committed WAL transactions
and excludes uncommitted writes. Published snapshots are standalone; Verify
rejects sidecars, checks current columns/PK/FK/CHECK/index structure, and
compares actual SHA/size/schema with Manifest.
On Linux/WSL, hash and SQLite inspection share a held file descriptor;
exclusive temporary targets and no-overwrite publication retain inode identity.
Required PK order and partial-index predicates are checked against current
models, including the `alembic_version.version_num` PK. Unsupported descriptor
or hard-link facilities fail closed rather than using unsafe path fallbacks.

Only exact `0005_add_deadlines_recurrence_reminders` is Restore-compatible.
Validate readability, hash, size, integrity, FK, Alembic, required tables and
critical structure; schema label alone is insufficient. Old/unknown/newer
schemas may be inspected but cannot Restore. Restore never runs migrations.

Offline Restore must first create and verify a Pre-Restore Safety Backup.
Revalidate target, create independent candidate, verify it, close connections,
and perform controlled switching with original DB/WAL/SHM retained. Never mix
old WAL with restored DB. Validate final integrity/FK/schema/structure/data;
record result and leave service stopped. Retain original, Safety Backup,
target, candidate, and operation log until explicit human disposition.

Failures stop; no automatic rollback/downgrade/guessed recovery. Before-switch
failure cannot replace current DB; during/after-switch failure or interruption
leaves startup blocked. Phase 3 must prototype locking and crash-safe DB/WAL/SHM
switching on isolated databases. No real Restore during development; future
real Restore needs separate explicit approval after those prototypes pass.

### Phase 3C Restore Artifact and Identity Contract (Isolated Prototype)

The complete execution/state/crash protocol is frozen in
`docs/ARCHITECTURE.md`, with isolated-only execution now implemented. No real
Restore is authorized or verified. Execution rejects the project data tree and
anything outside the system temporary directory; no real artifacts were created.
NO DATABASE MIGRATION REQUIRED; only exact `0005` remains compatible. Do not
change migrations, business fields, IDs, versions, relationships or time semantics.

Default operation storage:

```text
data/maintenance/coordination.lock          permanent cooperative flock inode
data/maintenance/maintenance.lock          durable operation acquisition marker
data/maintenance/restore-state.json        durable stage, not a business table
data/backups/restore-operations/<UUID4>/
  operation.json / events.jsonl / verification receipts
  current-evidence/                         raw quiescent forensic material
  current-working/                          private SQLite inspection source
  pre-restore-safety/                       Online Backup + Manifest V1
  original/                                original DB / WAL / SHM archive
  candidate.sqlite3                        independent retained target-byte copy
  install.sqlite3.partial                  independently verified installation copy
```

Paths derive from configured database parent, never user input. Existing
`data/backups/` and `data/maintenance/` ignores cover them. Backup List stays
nonrecursive and does not register operation directories, evidence or candidates.
Operations are UUID-owned, no-reuse, no-overwrite, private (0700/0600), no symlinks
or abnormal hard links. Manifest filenames never authorize a path. Safety purpose
is identified by `pre-restore-safety/` and the operation record, preserving the
existing standard Backup filename pattern and Manifest V1 without a new schema.

Require Backend stopped, exclusive lifetime cooperative usage lease, observable
quiescent process environment and no unknown users. Current raw DB/WAL/SHM is
captured as evidence, with source identities/hashes checked before/after; it is
not a consistent Backup product. SQLite logical inspection and Online Backup
run on a private working copy of the captured set so original SHM bookkeeping
is preserved. Never use immutable SQLite reads to ignore current committed WAL.
Only a separately verified Online Backup can be the Pre-Restore Safety Backup.
No checkpoint, journal-mode change, migration or repair of original files.

Target is already verified immutable standalone SQLite without sidecars. Exact
descriptor copying into independent candidate/install inodes is safe only in
that restricted case, not for an active database. Target, Manifest and candidate
master survive installation. Require target SHA/size = candidate SHA/size =
installation SHA/size = final live SHA/size. Final read-only standalone inspection
also verifies integrity/FK/exact schema/critical structure and target core counts.
Counts alone never prove logical identity. Online Backup of a WAL-bearing current
source may change physical layout/SHA; validate its committed logical contents,
not equality with the original main-file SHA.

Persist/fsync switch intent and `switching` before changing any live name.
Same-filesystem no-replace rename archives WAL, then SHM, then main DB; fsync
each source/destination directory and record each action. Require all live names
absent before installing the independent install file. Never attach old WAL/SHM
to the restored DB. Original files remain individually preserved, even if a crash
leaves them split between live/archive directories. No automatic reassembly.
Candidate master and initial evidence remain independent. Unexpected journal,
sidecar or changed identity blocks the operation.

Support only tested Linux/WSL ext4 storage with descriptor/NOFOLLOW, flock,
directory fsync and `renameat2(RENAME_NOREPLACE)` capabilities. Reject cross-mount,
DrvFS/network/unvalidated storage; no overwrite/copy-delete fallback. All readers
are closed before switching. Unknown usage is fail-closed; a best-effort process
scan does not exclude a later noncooperative opener. Require operator-controlled
quiescence, never promise universal exclusivity against arbitrary OS processes.

`completed` means final identity/verification and result receipts are durable,
not merely that installation returned success. Keep maintenance marker until
explicit verified completion acknowledgement; never auto-start services or
clear failed/unknown/partial state. Preserve original DB/WAL/SHM, evidence,
Safety Backup, target, candidate and logs after success or failure. Future manual
cleanup/recovery is separate approval; no automatic rollback or retention policy.

## Test Isolation

Phase 3D completed acknowledgement re-verifies the installed database read-only
under exclusive coordination lock: physical SHA/size, 0005, integrity/FK,
required structure, full logical fingerprint and matching final receipts.
Only V2 completed isolated operations qualify. Before any active blocker is
removed, a no-overwrite `startup-clearance.json` is fsynced in the operation
workspace and as a byte-identical maintenance-directory mirror, then fully
re-validated. It contains the archived active state identities, live DB
SHA/size/schema/logical fingerprint, final-verification and exact-confirmation
identities, and the immutable operation-log digest. That receipt is the durable
acknowledgement commit point. Blocker removal is post-commit housekeeping; a
remaining/reappearing blocker blocks, while blocker absence requires full
receipt/evidence/live-DB validation by Launcher and Backend. Receipt damage or
mismatch blocks. No compensation guard is required after cleanup failure.
All original DB/WAL/SHM, candidate, Target/Safety Backups, receipts and operation
logs remain. No automatic evidence retention cleanup or restart. The permanent
coordination inode and durable clearance receipt are never removed or replaced.

Storage qualification inspects actual mount identity/type, not path prefixes.
Only tested ext4 with same-mount no-replace rename, fsync and flock is qualified.
Probes use disposable system-temp files, not the real data directory. This is
mechanism qualification, not power-loss certification or real Restore approval.
Backend closes/drains tracked Sessions and disposes pooled connections before
releasing its lifespan shared lease. All destructive tests remain temporary;
NO DATABASE MIGRATION REQUIRED; REAL DATABASE RESTORE NOT APPROVED.

Tests create isolated temporary SQLite files, run Alembic against those files,
and override the FastAPI database dependency. Browser E2E uses a unique
`/tmp/dayflow-e2e-*` directory, upgrades it to head, and refuses to fall back
to the real database or any backup.
