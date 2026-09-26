# DayFlow Personal Roadmap

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

## Next

### V0.3 — Calendar and Time Blocking

Status: Architecture frozen; implementation not started.

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

Implementation must first validate `0003_add_task_schedule` on a temporary copy
of the real v0.2.1 database. No real-data migration is implied by this design
entry.

## Later

- V0.4: Projects and Project progress.
- V0.5: Reminders, Deadlines, and Repeat Tasks.
- V0.6: AI Provider abstraction and Mock Provider.
- V0.7: Natural-language Task creation.
- V0.8: AI Task decomposition.
- V0.9: AI Scheduling and Schedule Sandbox.
- V1.0: PWA, Backup/Restore, Statistics, and stability work.

## Candidate / Backlog

Ideas remain backlog items until a real need and version scope are approved.
