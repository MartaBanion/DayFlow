# Database

## Runtime Database

```text
data/dayflow.sqlite3
```

The file is personal runtime data and must never be committed. Backend writes
must occur through services and transactions.

## Current Schema: V0.4.0

The real database is currently at:

```text
0004_add_projects
```

Current application version: `v0.4.0`. V0.4 Projects functionality is
complete, the Project Backend and Frontend are implemented, and final acceptance
and database verification passed. V0.5 is the next planned development version.

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

Stop the Backend before copying `data/dayflow.sqlite3`. Verified maintenance
backups can use SQLite's Online Backup API; DayFlow still does not provide an
automatic Backup Service or Restore UI.

## Test Isolation

Tests create isolated temporary SQLite files, run Alembic against those files,
and override the FastAPI database dependency. Browser E2E uses a unique
`/tmp/dayflow-e2e-*` directory, upgrades it to head, and refuses to fall back
to the real database or any backup.
