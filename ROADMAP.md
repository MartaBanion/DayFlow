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

## Planned

### V0.2 — Inbox and Organization

Status: In development. Release tag waits for human acceptance.

- Inbox based on `planned_date IS NULL`, excluding completed and deleted Tasks
- Priority
- Category
- Tags
- Search over title and description
- Structured Priority, Category, and Tag filters

### Later

- V0.3: Calendar and Time Blocking.
- V0.4: Projects and Project progress.
- V0.5: Reminders, Deadlines, and Repeat Tasks.
- V0.6: AI Provider abstraction and Mock Provider.
- V0.7: Natural-language Task creation.
- V0.8: AI Task decomposition.
- V0.9: AI Scheduling and Schedule Sandbox.
- V1.0: PWA, Backup/Restore, Statistics, and stability work.

## Candidate / Backlog

Ideas remain backlog items until a real need and version scope are approved.
