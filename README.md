# DayFlow Personal

A local-first, single-user personal task and schedule manager.

[English](README.md) | [简体中文](README_CN.md)

[Release](https://github.com/MartaBanion/DayFlow/releases/tag/v1.0.0) · [Changelog](CHANGELOG.md) · [Roadmap](ROADMAP.md) · [Documentation](docs/)

**Stable Release:** `v1.0.0`<br>
**Application Version:** `1.0.0`

## Contents

- [What is DayFlow?](#what-is-dayflow)
- [Why DayFlow?](#why-dayflow)
- [Core Features](#core-features)
- [Daily Workflow](#daily-workflow)
- [Product Principles](#product-principles)
- [Architecture](#architecture)
- [Task Model at a Glance](#task-model-at-a-glance)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Development](#development)
- [Application Areas](#application-areas)
- [API Overview](#api-overview)
- [Data Model](#data-model)
- [Data & Privacy](#data--privacy)
- [Backup & Recovery](#backup--recovery)
- [Testing & Quality](#testing--quality)
- [Release History](#release-history)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)
- [Documentation](#documentation)
- [Release Status](#release-status)

## What is DayFlow?

DayFlow Personal is a local-first, single-user application for personal task management and schedule management. It brings task capture, planning, scheduling, execution, rescheduling, and review into one focused workflow.

DayFlow is not an enterprise collaboration platform, a multi-user SaaS product, or a cloud task service. The application is designed for a person who wants a dependable local workspace for everyday planning.

## Why DayFlow?

Many Todo List tools are optimized for recording tasks. DayFlow also gives the task a path through the day:

```text
Capture
   ↓
Inbox
   ↓
Plan
   ↓
Today / Calendar
   ↓
Complete / Reschedule
   ↓
Review
```

- Unplanned work can stay in Inbox until it is ready to schedule.
- Today focuses attention on the current day.
- Calendar provides Day, Week, and Month views for date and time planning.
- Quick Reschedule handles ordinary plan changes without silently changing deadlines, reminders, or recurrence rules.
- Review provides read-only daily and weekly current-state views.
- Task data remains in the local SQLite database.

## Core Features

### Capture & Inbox

- Create and edit tasks with optional descriptions and planning fields.
- Keep pending tasks without a planned date in Inbox.
- Organize tasks with Priority, Category, Tags, and Projects.
- Search inside Inbox without changing its meaning: Inbox queries remain scoped to pending, unscheduled, non-deleted tasks.

### Today

- Focus on the tasks planned for the current DayFlow date.
- Complete and restore tasks.
- Soft-delete tasks and use Undo when appropriate.
- Open the existing Quick Reschedule menu for pending tasks.

### Calendar

- Day View, Week View, and Month View.
- Display date-only tasks and scheduled Time Blocks.
- Preserve local clock and timezone semantics when a scheduled task moves to another date.
- Use Month date selection and “more items” links to enter the existing Day View.

### Organization

- Global Search with text, status, overdue, planned-date bucket, Priority, Category, Tag, Project, Inbox, and sort controls.
- Reusable Task query semantics with AND behavior across active filters.
- Project lists, Project Detail, project task filtering, and calculated project progress.

### Planning

- Planned Date for the day a task is intended to be worked on.
- Deadline for a date-only or timed due point.
- Reminder for a specified notification time.
- Recurrence rules for daily, selected-weekday, and monthly work.
- Time Block for a local start/end schedule and timezone.
- Quick Reschedule actions for Today, Tomorrow, Next Monday, Move to Inbox, and Choose Date.

### Review

- Daily and weekly current-state Review.
- Completed, Overdue, and Carryover task lists.
- Current Project facts and progress.
- Read-only review behavior that does not materialize recurrence or mutate business data.

### Local Data

- SQLite persistence for local task and project data.
- Soft Delete with recoverable task Restore paths.
- Optimistic Version Control for safe concurrent edits.
- Backup Create, List, and Verify support through the maintenance boundary.

## Daily Workflow

DayFlow is organized around a short, repeatable loop:

```text
Capture
   ↓
Inbox
   ↓
Plan
   ↓
Today / Calendar
   ↓
Complete / Reschedule
   ↓
Review
```

1. **Capture:** record a task without requiring every planning decision immediately.
2. **Inbox:** keep unplanned work visible while it is still being clarified.
3. **Plan:** assign a Planned Date, Project, Priority, Category, Tags, Deadline, Reminder, Recurrence, or Time Block as needed.
4. **Today / Calendar:** execute the current plan and inspect work across Day, Week, or Month views.
5. **Complete / Reschedule:** finish work or use Quick Reschedule when the plan changes.
6. **Review:** inspect current completed, overdue, carryover, and Project facts.

## Product Principles

### Local First

User task data is stored locally in SQLite. The GitHub repository contains source code and documentation, not personal task data.

### Single User

DayFlow is intentionally designed for personal use rather than accounts, teams, permissions, or multi-user collaboration.

### Workflow Before Feature Count

The project prioritizes a coherent daily workflow over adding isolated features that do not improve capture, planning, execution, or review.

### Explicit Task Semantics

Planned Date, Deadline, Reminder, Recurrence, and Time Block are separate concepts. Quick Reschedule changes only the planning date, except that Move to Inbox also clears the schedule required by the Inbox invariant.

### Data Ownership

GitHub stores the source code, documentation, Git history, and release tags. The real personal database and local backups remain under the user's control outside the repository.

## Architecture

DayFlow is a local-first modular monolith with a Vue browser client and a FastAPI service backed by SQLite.

```text
Browser
   │
   ▼
Vue 3 + TypeScript + Vite + Element Plus
   │
   │ HTTP / REST
   ▼
FastAPI
   │
   ▼
Synchronous SQLAlchemy 2.x
   │
   ▼
SQLite
```

- **Frontend:** Vue 3, TypeScript, Vite, and Element Plus.
- **Backend:** Python 3.12 and FastAPI.
- **ORM:** synchronous SQLAlchemy 2.x.
- **Database:** SQLite.
- **Migration:** Alembic.

See [Architecture Documentation](docs/ARCHITECTURE.md).

## Task Model at a Glance

| Concept | Meaning |
| --- | --- |
| Planned Date | The local date when the user intends to work on the task. |
| Deadline | The date, or specific local-time point, by which the task is due. |
| Reminder | The notification trigger associated with a task. |
| Recurrence | The rule used to describe future occurrences. |
| Time Block | A scheduled local start/end block with a timezone. |

These concepts have different semantics. Moving a task with Quick Reschedule does not implicitly rewrite its Deadline, Reminder, or Recurrence.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | Vue 3, TypeScript, Vite, Element Plus |
| Backend | Python 3.12, FastAPI |
| ORM | SQLAlchemy 2.x |
| Database | SQLite |
| Migration | Alembic |
| Backend Testing | pytest |
| Frontend Testing | Vitest |
| E2E Testing | Playwright |
| Version Control | Git |

## Project Structure

```text
DayFlow/
├── backend/
│   ├── app/
│   ├── migrations/
│   │   └── versions/
│   └── tests/
├── frontend/
│   ├── src/
│   └── e2e/
├── docs/
├── scripts/
├── data/
├── AGENTS.md
├── CHANGELOG.md
├── ROADMAP.md
├── README.md
└── README_CN.md
```

- `backend/` contains the API, services, models, migrations, and Backend tests.
- `frontend/` contains the Vue application, unit tests, and Playwright tests.
- `docs/` contains the core API, architecture, and database documentation.
- `scripts/` contains local start and stop helpers.
- `data/` is for ignored local runtime data only.

## Quick Start

The commands below describe a development setup with an isolated temporary database. Do not use the real personal database for first-time setup, tests, or migration rehearsals.

### Prerequisites

- Python 3.12.
- Node.js 24 or newer.
- [`uv`](https://docs.astral.sh/uv/).
- Git.

### Clone

```bash
git clone https://github.com/MartaBanion/DayFlow.git
cd DayFlow
```

### Backend Setup

```bash
uv sync --directory backend
```

### Frontend Setup

```bash
npm ci --prefix frontend
```

### Database Initialization

Initialize an isolated development database at `/tmp/dayflow-development.sqlite3`:

```bash
DAYFLOW_DATABASE_PATH=/tmp/dayflow-development.sqlite3 \
  uv run --directory backend alembic upgrade head
```

### Start

Start the Backend against the isolated database:

```bash
DAYFLOW_DATABASE_PATH=/tmp/dayflow-development.sqlite3 \
  uv run --directory backend uvicorn app.main:app \
  --reload --host 127.0.0.1 --port 8000
```

In a second terminal, start the Frontend:

```bash
npm run dev --prefix frontend
```

For an existing local DayFlow runtime database, the project launcher can start both services and perform its health, version, maintenance, and schema checks:

```bash
./scripts/dayflow-start.sh
```

Stop services started by the launcher with:

```bash
./scripts/dayflow-stop.sh
```

The launcher does not create test data or run migrations. By default it checks the real local database at `data/dayflow.sqlite3`; keep that boundary separate from isolated development and test databases.

### Open

- Frontend: <http://127.0.0.1:5173>
- Backend: <http://127.0.0.1:8000>
- Health check: <http://127.0.0.1:8000/healthz>

## Development

Run Backend tests:

```bash
uv run --directory backend pytest
```

Run Frontend unit tests:

```bash
npm run test --prefix frontend
```

Run type checking and the production build:

```bash
npm run type-check --prefix frontend
npm run build --prefix frontend
```

Run Chromium E2E tests with the repository's isolated test runner:

```bash
npm run test:e2e --prefix frontend
npm run test:e2e:ui --prefix frontend
```

Install the Playwright browser when needed:

```bash
npm exec --prefix frontend playwright install chromium
```

Browser E2E uses an isolated temporary database, headless Chromium, dedicated local ports `18000` and `15173`, and one worker while SQLite is under test. Tests must never fall back to `data/dayflow.sqlite3` or `data/backups/`.

## Application Areas

| Area | Purpose |
| --- | --- |
| Today | Execute and maintain the current daily plan. |
| Inbox | Hold pending tasks that do not yet have a Planned Date. |
| Calendar | Inspect and adjust work across Day, Week, and Month views. |
| Search | Search, filter, sort, and inspect tasks across the non-deleted task set. |
| Projects | Manage projects and inspect project task lists and progress. |
| Review | Read-only daily and weekly views of current completed, overdue, carryover, and Project facts. |

## API Overview

The Backend exposes the versioned API under `/api/v1`. The existing API is organized around:

- Tasks and task query filters.
- Projects, Categories, and Tags.
- Calendar and runtime date information.
- Review scopes for today and this week.
- Recurrence and Reminder operations.
- Backup and maintenance status.

Quick Reschedule reuses the existing versioned Task update path rather than introducing a separate planning API. The relevant contract is `PATCH /api/v1/tasks/{id}?version=<version>`; Inbox search remains an Inbox-scoped task query using `inbox=true&q=<query>`.

See [API Documentation](docs/API.md).

## Data Model

The main business models are Task, Project, Category, Tag, Time Block, Deadline, Recurrence, and Reminder. A Task can have a Planned Date, an optional Time Block, optional Deadline and Reminder data, and an optional Recurrence relationship while retaining explicit state semantics.

See [Database Documentation](docs/DATABASE.md) for the current schema and migration history.

## Data & Privacy

DayFlow is local-first. User task data is stored locally in SQLite, normally at `data/dayflow.sqlite3`, and is not included in the GitHub repository or GitHub Release.

The GitHub repository and a fresh clone restore source code, documentation, Git history, and release tags. They do not restore personal task data, the local database, or local backup data.

The following are local-only and must not be committed:

- `data/dayflow.sqlite3`
- `data/backups/`
- `data/maintenance/`
- `.env` and other local configuration

Tests and browser E2E use isolated temporary databases. Do not copy local runtime state, virtual environments, `node_modules`, or test artifacts into the repository.

## Backup & Recovery

DayFlow provides Backup Create, List, and Verify through the maintenance boundary. Backups use SQLite's Online Backup API so committed WAL data is handled safely; directly copying the main file of an active database is not the supported backup method.

The current v1.0.0 boundary is:

- **Backup:** available.
- **Real Restore:** PROHIBITED.
- **Storage Qualification:** `NOT QUALIFIED`.

Restore execution has been isolated and verified only for independent system-temporary databases. The real personal database must be backed up separately before retiring or moving the local environment; GitHub does not contain that data.

## Testing & Quality

The following is the V1.0 release acceptance baseline, not a promise that test counts will never change:

| Check | Result |
| --- | --- |
| Backend | 414 passed |
| Frontend | 127 passed |
| Playwright | 52 passed |
| Type-check | PASS |
| Build | PASS |

At release acceptance, tests used isolated temporary databases and the real personal database remained unchanged.

## Release History

| Release | Milestone |
| --- | --- |
| `v1.0.0` | Product Maturity: stable Capture, Inbox, Today, Calendar, Search, Projects, Deadline, Reminder, Recurrence, Review, and Quick Reschedule workflows. |
| `v0.9.0` | Quick Reschedule and lightweight Month-to-Day drill-down. |
| `v0.8.0` | Search, Filter, Sort, and Project query reuse. |
| `v0.7.0` | Daily and Weekly Review. |
| `v0.6.0` | Data Safety and Recovery foundations. |
| `v0.5.x` | Deadline, Reminder, Recurrence, and UI refinement. |

See [CHANGELOG.md](CHANGELOG.md) for the detailed history.

## Known Limitations

- Real Restore for the project database remains prohibited because Storage Qualification is `NOT QUALIFIED`.
- Calendar may use internal horizontal scrolling on narrower desktop layouts.
- Reminder acknowledge/dismiss failure feedback can be improved.
- Skip-to-content remains deferred.

These are known boundaries or low-risk UX improvements and do not block normal v1.0.0 daily usage.

## Roadmap

The 1.x direction remains focused on incremental product maturity:

- UX polish.
- Practical accessibility improvements.
- Better Reminder interaction feedback.
- Small, evidence-driven refinements to the existing personal workflow.

Large feature expansion is intentionally outside the current release scope. See [ROADMAP.md](ROADMAP.md) for the maintained roadmap.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API](docs/API.md)
- [Database](docs/DATABASE.md)
- [Roadmap](ROADMAP.md)
- [Changelog](CHANGELOG.md)
- [Simplified Chinese README](README_CN.md)

## Release Status

- **Stable Release:** `v1.0.0`
- **Application Version:** `1.0.0`
- **Release Commit:** `8a941b5a15ef9eaeb18b9a415710f9d7deb7133e`
- **Database Schema:** `0005_add_deadlines_recurrence_reminders`
- **Migration:** NO; `0006` does not exist
- **Status:** Released / Stable
- **GitHub Release:** <https://github.com/MartaBanion/DayFlow/releases/tag/v1.0.0>

DayFlow Personal is developed as a local-first personal productivity project.
