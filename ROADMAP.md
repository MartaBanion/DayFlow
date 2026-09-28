# DayFlow Personal Roadmap

Current application version: **v0.4.0 — V0.4 Projects**. V0.4 Projects
functionality is complete. The Project Backend and Frontend are implemented;
final acceptance and database verification passed. The real database schema is
`0004_add_projects`. V0.5 is the next planned development version.

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
Phase 3 acceptance, and real-data migration are complete. The real database is
at `0004_add_projects`.

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
acceptance, and approved real-data migration. V0.5 is the next planned
development version.

## Later

- V0.5: Reminders, Deadlines, and Repeat Tasks.
- V0.6: AI Provider abstraction and Mock Provider.
- V0.7: Natural-language Task creation.
- V0.8: AI Task decomposition.
- V0.9: AI Scheduling and Schedule Sandbox.
- V1.0: PWA, Backup/Restore, Statistics, and stability work.

## Candidate / Backlog

Ideas remain backlog items until a real need and version scope are approved.
