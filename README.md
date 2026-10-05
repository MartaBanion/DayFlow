<a id="top"></a>

# DayFlow Personal

[English](#english) | [简体中文](#zh-cn)

<a id="english"></a>

## Overview

DayFlow Personal is a local-first, single-user personal task and schedule manager.

**Stable Release:** [`v1.0.0`](https://github.com/MartaBanion/DayFlow/releases/tag/v1.0.0)<br>
**Application Version:** `1.0.0`

DayFlow keeps capture, planning, execution, and review in one lightweight local workflow. Data is stored locally by default, and the application does not require a cloud account or a multi-user service.

## Core Features

| Feature | Description |
| --- | --- |
| Inbox | Manage pending tasks that do not have a planned date. |
| Today | Work through today’s plan with complete, restore, delete, undo, and reschedule actions. |
| Task CRUD | Create, view, edit, and delete tasks with optimistic version checks. |
| Priority, Category, Tags | Organize tasks with structured metadata. |
| Projects | Manage projects, project tasks, and project progress. |
| Search, Filter, Sort | Search and organize tasks by text, status, overdue state, planned-date bucket, priority, category, tag, project, and stable sort; filters use AND semantics. |
| Day / Week / Month Calendar | View planned tasks, Time Blocks, and Deadlines; Month dates can open the existing Day View. |
| Time Block | Schedule a task with local start/end times and a timezone. |
| Deadline | Support date-only and timed Deadlines with timezone and DST-aware semantics. |
| Reminder | Support specified-time reminders with pending, acknowledged, and dismissed states. |
| Recurrence / Repeat | Support daily, selected-weekday, and monthly recurrence rules with explicit occurrence handling. |
| Daily / Weekly Review | Review completed, overdue, carryover, and current project facts in a read-only view. |
| Quick Reschedule | Reschedule pending Tasks to Today, Tomorrow, Next Monday, Inbox, or a chosen date. |
| Soft Delete / Undo | Use recoverable soft deletion with an Undo path. |
| Local SQLite Persistence | Tasks and projects persist locally by default. |

## Daily Workflow

DayFlow follows a simple daily loop: capture first, plan next, execute, and review.

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

- **Capture:** Create a task quickly, then decide whether to add a planned date, Time Block, project, or other metadata.
- **Plan:** Inbox is for unscheduled work; Today, Calendar, and Task Editor support more specific planning.
- **Execute:** Today focuses on the current plan, while Calendar provides Day, Week, and Month views.
- **Review:** `#review` is read-only and helps inspect completed work, overdue tasks, carryover, and current project state.

### Quick Reschedule

Quick Reschedule is available for pending Tasks with Today, Tomorrow, Next Monday, Move to Inbox, and Choose Date actions. Normal actions change only `planned_date`; moving a task to Inbox also clears `schedule`. Deadline, Reminder, and Recurrence are not changed implicitly.

Today, Tomorrow, and Next Monday use the DayFlow runtime `local_date`, not the browser timezone or a UTC date. When a scheduled task moves across dates, the Backend preserves its local clock and timezone while recalculating UTC instants; conflicts use the existing confirmation flow.

## Tech Stack

- Vue 3 + TypeScript + Vite + Element Plus
- Python 3.12 + FastAPI + Pydantic
- Synchronous SQLAlchemy 2.x
- SQLite + Alembic

## Quick Start

### Prerequisites

- Python 3.12
- Node.js 24 LTS
- [`uv`](https://docs.astral.sh/uv/)

### Set Up a Development Environment

The following setup uses a temporary database. Do not use the real personal database for tests or first-time setup.

```bash
uv sync --directory backend
npm ci --prefix frontend
DAYFLOW_DATABASE_PATH=/tmp/dayflow-development.sqlite3 \
  uv run --directory backend alembic upgrade head
```

### Run the Backend

```bash
DAYFLOW_DATABASE_PATH=/tmp/dayflow-development.sqlite3 \
  uv run --directory backend uvicorn app.main:app \
  --reload --host 127.0.0.1 --port 8000
```

### Run the Frontend

Run this in a second terminal:

```bash
npm run dev --prefix frontend
```

### Daily WSL Launch

From the project root, run:

```bash
./scripts/dayflow-start.sh
```

The launcher checks the runtime environment, ports, Backend health, application version, and database schema. It does not run migrations or create test data. Stop services created by the launcher with:

```bash
./scripts/dayflow-stop.sh
```

## Project Structure

```text
backend/     FastAPI API, services, models, migrations, and Backend tests
frontend/    Vue application, unit tests, and Playwright E2E tests
docs/        API, architecture, and database documentation
scripts/     Local WSL start/stop scripts
data/        Ignored local runtime data; never commit personal data
```

## Data & Privacy

The real SQLite database normally lives at `data/dayflow.sqlite3`. It is personal runtime data, ignored by Git, and not included in the GitHub repository or Release. The application is built around local execution and local persistence and does not require a cloud account.

Tests, browser E2E runs, and migration rehearsals must use isolated temporary databases. Do not copy `.env`, the real database, backups, virtual environments, `node_modules`, or test artifacts into Git.

## Backup / Restore

DayFlow provides Backup Create, List, and Verify through the maintenance view. Backups use SQLite’s Online Backup API so committed WAL data is handled safely; do not directly copy the main file of an active database.

The current boundary is:

- **Backup:** available
- **Real Restore:** PROHIBITED
- **Storage Qualification:** `NOT QUALIFIED`
- Restore execution has only been verified for independent system-temporary databases.

The real personal database, backups, and maintenance state are local-only data. Back them up separately before retiring or migrating the WSL environment; they are not part of the GitHub repository or Release.

## Testing & Quality

Backend and Frontend tests use isolated temporary databases and must never access `data/dayflow.sqlite3`.

```bash
uv run --directory backend pytest
npm run test --prefix frontend
```

Browser E2E uses a fresh temporary SQLite database, headless Chromium, Backend port `18000`, and Frontend port `15173`:

```bash
npm run test:e2e --prefix frontend
npm run test:e2e:ui --prefix frontend
```

Install the Playwright Chromium browser once before the first run:

```bash
npm exec --prefix frontend playwright install chromium
```

The accepted release baseline is:

- Backend: 414 passed
- Frontend: 127 passed
- Playwright: 52 passed
- Type-check: PASS
- Build: PASS

## Release Status

- **Stable Release:** `v1.0.0`
- **Application Version:** `1.0.0`
- **Release Commit:** `8a941b5a15ef9eaeb18b9a415710f9d7deb7133e`
- **Database Schema:** `0005_add_deadlines_recurrence_reminders`
- **Migration:** NO; `0006` does not exist
- **V1.0 Product Maturity Audit:** PASS
- **V1.0 Final Product Acceptance:** PASS

Additional low-risk UX improvements remain deferred to 1.x. V1.0 focuses on a stable, understandable, and recoverable personal task workflow rather than continued feature expansion.

See [`CHANGELOG.md`](CHANGELOG.md) and [`ROADMAP.md`](ROADMAP.md) for the full release history.

---

<a id="zh-cn"></a>

# 简体中文

[English](#english) | [简体中文](#zh-cn)

## 项目简介

DayFlow Personal 是一个本地优先、单用户的个人任务与日程管理工具。

**稳定版本：** [`v1.0.0`](https://github.com/MartaBanion/DayFlow/releases/tag/v1.0.0)<br>
**应用版本：** `1.0.0`

DayFlow 将记录、规划、执行和复盘放在一套轻量的本地工作流中。数据默认保存在本机，不依赖云端账户或多人协作服务。

## 核心功能

| 功能 | 说明 |
| --- | --- |
| 收件箱 Inbox | 管理没有计划日期的待处理任务。 |
| 今天 Today | 查看当天计划，并完成、恢复、删除、撤销删除或调整日期。 |
| 任务管理 | 创建、查看、编辑和删除任务，并使用版本检查避免静默覆盖。 |
| 优先级、分类、标签 | 使用结构化元数据组织任务。 |
| 项目 Projects | 管理项目、项目任务和项目进度。 |
| 搜索、筛选、排序 | 按文本、状态、逾期状态、计划日期区间、优先级、分类、标签、项目和稳定排序查找任务；筛选使用 AND 语义。 |
| 日 / 周 / 月日历 Calendar | 查看计划任务、Time Block 和 Deadline；月视图日期可以进入现有 Day View。 |
| 时间块 Time Block | 为任务设置本地开始时间、结束时间和时区。 |
| 截止日期 Deadline | 支持日期型和定时 Deadline，并保留时区与 DST 语义。 |
| 提醒 Reminder | 支持指定时间提醒，以及 pending、acknowledged 和 dismissed 状态。 |
| 重复任务 Recurrence | 支持每日、指定星期和每月规则，并按现有规则处理 occurrence。 |
| 每日 / 每周复盘 | 以只读方式查看完成、逾期、Carryover 和项目当前状态。 |
| 快速调整日期 Quick Reschedule | Pending Task 可以调整到 Today、Tomorrow、Next Monday、Inbox 或自选日期。 |
| 软删除与撤销 | 使用可恢复的软删除状态和 Undo 路径。 |
| 本地 SQLite 持久化 | 任务和项目默认持久化在本机。 |

## 日常工作流

DayFlow 的日常流程保持简单：先记录，再规划，然后执行，最后复盘。

```text
记录
   ↓
收件箱 Inbox
   ↓
规划
   ↓
Today / Calendar
   ↓
完成 / 调整日期
   ↓
复盘 Review
```

- **记录：** 快速创建任务，再决定是否添加计划日期、Time Block、项目或其他元数据。
- **规划：** Inbox 用于未安排任务；Today、Calendar 和 Task Editor 用于更具体的计划。
- **执行：** Today 聚焦当前计划，Calendar 提供 Day、Week 和 Month 视角。
- **复盘：** `#review` 为只读视图，用于查看已完成任务、逾期任务、Carryover 和项目当前状态。

### 快速调整日期

快速调整日期只面向 Pending Task，动作包括 Today、Tomorrow、Next Monday、移回 Inbox 和选择日期。普通动作只修改 `planned_date`；移回 Inbox 会同时清除 `schedule`。Deadline、Reminder 和 Recurrence 不会被隐式修改。

Today、Tomorrow 和 Next Monday 以 DayFlow runtime 的 `local_date` 为日期基准，不使用浏览器时区或 UTC 日期。带 Time Block 的任务跨日期移动时，Backend 保留本地时钟和时区并重新计算 UTC；冲突继续使用现有确认流程。

## 技术栈

- Vue 3 + TypeScript + Vite + Element Plus
- Python 3.12 + FastAPI + Pydantic
- 同步 SQLAlchemy 2.x
- SQLite + Alembic

## 快速开始

### 环境要求

- Python 3.12
- Node.js 24 LTS
- [`uv`](https://docs.astral.sh/uv/)

### 初始化开发环境

以下示例使用临时数据库。不要把真实个人数据库用于测试或首次初始化。

```bash
uv sync --directory backend
npm ci --prefix frontend
DAYFLOW_DATABASE_PATH=/tmp/dayflow-development.sqlite3 \
  uv run --directory backend alembic upgrade head
```

### 启动 Backend

```bash
DAYFLOW_DATABASE_PATH=/tmp/dayflow-development.sqlite3 \
  uv run --directory backend uvicorn app.main:app \
  --reload --host 127.0.0.1 --port 8000
```

### 启动 Frontend

在另一个终端执行：

```bash
npm run dev --prefix frontend
```

### WSL 日常启动

在项目根目录执行：

```bash
./scripts/dayflow-start.sh
```

启动脚本会检查运行环境、端口、Backend 健康状态、应用版本和数据库 Schema。不会自动执行 Migration，也不会创建测试数据。停止由启动脚本创建的服务：

```bash
./scripts/dayflow-stop.sh
```

## 项目结构

```text
backend/     FastAPI API、服务、模型、迁移和 Backend 测试
frontend/    Vue 应用、单元测试和 Playwright E2E 测试
docs/        API、架构和数据库文档
scripts/     本地 WSL 启停脚本
data/        被 Git 忽略的本地运行数据；不要提交个人数据
```

## 数据与隐私

真实 SQLite 数据库默认位于 `data/dayflow.sqlite3`，属于个人运行数据，已被 Git 忽略，不会包含在 GitHub 仓库或 Release 中。应用以本地运行和本地持久化为核心，不要求云端账户。

测试、浏览器 E2E 和迁移演练必须使用隔离临时数据库。不要把 `.env`、真实数据库、备份、虚拟环境、`node_modules` 或测试产物复制到 Git。

## Backup / Restore

DayFlow 通过维护界面提供 Backup Create、List 和 Verify。备份使用 SQLite Online Backup API，以安全处理已提交的 WAL 数据；不要直接复制正在运行的数据库主文件。

当前边界如下：

- **Backup：** `available`
- **Real Restore：** `PROHIBITED`
- **Storage Qualification：** `NOT QUALIFIED`
- 目前只验证了独立系统临时数据库上的隔离 Restore 流程。

真实个人数据库、备份和维护状态属于本地数据。在删除 WSL 或迁移环境前必须单独备份；它们不是 GitHub 仓库或 Release 的内容。

## 测试与质量

Backend 和 Frontend 测试使用隔离临时数据库，不得访问 `data/dayflow.sqlite3`。

```bash
uv run --directory backend pytest
npm run test --prefix frontend
```

浏览器 E2E 使用一次性的临时 SQLite 数据库、headless Chromium、Backend `18000` 和 Frontend `15173`：

```bash
npm run test:e2e --prefix frontend
npm run test:e2e:ui --prefix frontend
```

首次运行前只需安装 Playwright Chromium：

```bash
npm exec --prefix frontend playwright install chromium
```

正式验收基线如下：

- Backend：414 passed
- Frontend：127 passed
- Playwright：52 passed
- Type-check：PASS
- Build：PASS

## 发布状态

- **稳定版本：** `v1.0.0`
- **应用版本：** `1.0.0`
- **发布 Commit：** `8a941b5a15ef9eaeb18b9a415710f9d7deb7133e`
- **数据库 Schema：** `0005_add_deadlines_recurrence_reminders`
- **Migration：** NO；`0006` 不存在
- **V1.0 Product Maturity Audit：** PASS
- **V1.0 Final Product Acceptance：** PASS

低风险用户体验改进继续延后到 1.x。V1.0 的重点是稳定、易理解、可恢复的个人任务工作流，而不是继续扩大功能范围。

完整发布历史请参阅 [`CHANGELOG.md`](CHANGELOG.md) 与 [`ROADMAP.md`](ROADMAP.md)。
