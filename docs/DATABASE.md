# Database

## Runtime Database

```text
data/dayflow.sqlite3
```

The file is personal runtime data and must never be committed. Backend writes
must occur through services and transactions.

## Current Schema: V0.2.1

The real database is currently at:

```text
0002_add_priority_categories_tags
```

V0.1 contains the original `tasks` fields. V0.2 adds organization fields and
the normalized metadata tables.

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

## Planned V0.3 Schema: `0003_add_task_schedule`

This migration is designed but has not been created or executed.

It will add only these nullable columns to `tasks`:

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

All three new columns will be `NULL` for old Tasks.

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

## Migration Procedure

When implementation begins:

1. Keep the Backend stopped.
2. Create and verify a pre-V0.3 backup.
3. Copy the real V0.2.1 database to a temporary test location.
4. Run `0003` only against the copy.
5. Verify `integrity_check` and `foreign_key_check`.
6. Verify Alembic head and all legacy Task fields.
7. Verify all new fields are `NULL` for existing Tasks.
8. Test scheduled Task writes, clear operations, conflict rollback, and restart
   persistence on the copy.
9. Run the complete Backend, Frontend, and Browser regression suites.
10. Request explicit approval before upgrading the real database.

SQLite batch migration must be used where table recreation is required. The
migration must not edit `0001_create_tasks` or
`0002_add_priority_categories_tags`.

## Downgrade

Downgrade of `0003` is potentially destructive because it removes saved Time
Block data. It must fail closed if any row has a non-`NULL` schedule field. A
downgrade is only safe when all three new columns are empty, such as on a clean
test database.

## Backup

Stop the Backend before copying `data/dayflow.sqlite3`. V0.2.1 still uses the
manual backup procedure; V0.3 does not add an automatic backup service.

## Test Isolation

Tests create isolated temporary SQLite files, run Alembic against those files,
and override the FastAPI database dependency. Browser E2E uses a unique
`/tmp/dayflow-e2e-*` directory, upgrades it to head, and refuses to fall back
to the real database or any backup.
