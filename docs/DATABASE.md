# Database

## Runtime Database

```text
data/dayflow.sqlite3
```

The file is personal runtime data and must never be committed.

## V0.1 Schema

V0.1 contains only the `tasks` table with the fields required for basic Task management and Today queries.

| Column | SQLite type | Nullable | Meaning |
| --- | --- | --- | --- |
| `id` | `VARCHAR(36)` | no | Application-generated UUID string |
| `title` | `VARCHAR(500)` | no | Required user-facing title |
| `description` | `TEXT` | yes | Optional notes |
| `status` | `VARCHAR(20)` | no | `pending` or `completed` |
| `planned_date` | `DATE` | yes | Date-only planning value |
| `created_at_utc` | `VARCHAR(32)` | no | UTC RFC3339 instant ending in `Z` |
| `updated_at_utc` | `VARCHAR(32)` | no | UTC RFC3339 instant ending in `Z` |
| `completed_at_utc` | `VARCHAR(32)` | yes | Set when completed |
| `deleted_at_utc` | `VARCHAR(32)` | yes | Set by soft delete |
| `version` | `INTEGER` | no | Starts at 1 and increments on mutation |

The UTC datetime type intentionally stores normalized RFC3339 text because
SQLite does not preserve timezone metadata for ordinary datetime columns.
Future schema changes must be additive or data-compatible migrations; do not
pre-add Project, Reminder, Recurrence, scheduling, or AI columns.

## V0.2 Schema

Migration `0002_add_priority_categories_tags` adds:

| Object | Purpose |
| --- | --- |
| `tasks.priority` | Non-null `low`, `normal`, or `high`; existing rows use `normal` |
| `tasks.category_id` | Nullable Category foreign key with `ON DELETE SET NULL` |
| `categories` | UUID and case-insensitive unique name |
| `tags` | UUID and case-insensitive unique name |
| `task_tags` | Composite `(task_id, tag_id)` relationship table |

Inbox is not a table or column. It is the query:

```text
planned_date IS NULL AND deleted_at_utc IS NULL AND status = 'pending'
```

Category and Tag names are trimmed, non-empty, length-limited, and checked for
case-insensitive duplicates. SQLite `NOCASE` is intentionally used without an
additional Unicode case-folding dependency; its case-insensitive behavior is
limited compared with full Unicode case folding.

Every SQLAlchemy SQLite connection enables `PRAGMA foreign_keys=ON`. The same
rule applies to the Alembic engine and isolated test engines.

## State Rules

- Completing a pending Task sets `status=completed` and `completed_at_utc`.
- Restoring a completed Task returns it to `pending` and clears
  `completed_at_utc`.
- Soft delete sets `deleted_at_utc` and increments `version` without erasing
  the row.
- Normal list and Today queries exclude soft-deleted rows.
- The restore endpoint can recover a soft-deleted row when the caller supplies
  its current version.

## Manual Backup

Stop the Backend before copying the database. Copy `data/dayflow.sqlite3` to a timestamped location outside the repository. V0.1 does not include an automated backup or restore workflow.

## Migration

Use Alembic. Do not delete and recreate the database to apply schema changes.

```bash
uv run --directory backend alembic upgrade head
uv run --directory backend alembic current
```

The initial migration is `0001_create_tasks`. Downgrade is supported for the
The V0.2 migration is `0002_add_priority_categories_tags`; `0001_create_tasks`
must never be edited. SQLite batch operations are used for the existing Task
table. Downgrade is destructive once V0.2 data exists, so it is intended for
empty/test databases only. Make a manual backup before any risky migration on
personal data.

## Test Isolation

Tests create a temporary SQLite file, run the Alembic upgrade against that file,
and override the FastAPI database dependency. The configured real path
`data/dayflow.sqlite3` is never used by tests.
