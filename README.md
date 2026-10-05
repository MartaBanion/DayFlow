# DayFlow Personal

本地优先的单用户个人任务与日程管理工具。

A local-first, single-user personal task and schedule manager.

**稳定版本 / Stable Release:** [`v1.0.0`](https://github.com/MartaBanion/DayFlow/releases/tag/v1.0.0)<br>
**应用版本 / Application Version:** `1.0.0`

DayFlow Personal 的数据默认保存在本机，不依赖云端账户，适合个人长期管理任务、计划、时间安排与复盘。

DayFlow Personal keeps data local by default and does not require a cloud account. It is designed for long-term personal task planning, scheduling, and review.

## 目录 / Contents

- [项目简介 / Overview](#项目简介--overview)
- [核心功能 / Core Features](#核心功能--core-features)
- [界面与工作流 / Workflow](#界面与工作流--workflow)
- [技术栈 / Tech Stack](#技术栈--tech-stack)
- [快速开始 / Quick Start](#快速开始--quick-start)
- [项目结构 / Project Structure](#项目结构--project-structure)
- [数据与隐私 / Data & Privacy](#数据与隐私--data--privacy)
- [备份与恢复 / Backup & Restore](#备份与恢复--backup--restore)
- [测试 / Testing](#测试--testing)
- [当前版本 / Release Status](#当前版本--release-status)

## 项目简介 / Overview

DayFlow Personal 是一个 Local First、Single User 的个人任务与日程管理应用。它把收集、规划、执行和复盘放在一套轻量的本地工作流中，数据持久化在本机 SQLite 数据库。

DayFlow Personal is a local-first, single-user personal productivity application. It keeps capture, planning, execution, and review in one lightweight local workflow, with persistence provided by SQLite on the local machine.

应用不要求云端账户或多人协作服务；本地数据库、备份和维护边界会在下文明确说明。

The application does not require a cloud account or a multi-user service. The local database, backup, and maintenance boundaries are documented below.

## 核心功能 / Core Features

| 功能 | Feature | 说明 / Description |
| --- | --- | --- |
| 收件箱 | Inbox | 管理未安排的待办任务。<br>Manage pending tasks that do not have a planned date. |
| 今天 | Today | 查看当天计划，完成、恢复、删除、撤销删除或调整日期。<br>Work through today’s plan with complete, restore, delete, undo, and reschedule actions. |
| 任务管理 | Task CRUD | 创建、查看、编辑和删除任务，并使用 optimistic version 防止静默覆盖。<br>Create, view, edit, and delete tasks with optimistic version checks. |
| 优先级、分类、标签 | Priority, Category, Tags | 使用结构化元数据组织任务。<br>Organize tasks with structured metadata. |
| 项目 | Projects | 管理项目、项目任务和项目进度。<br>Manage projects, project tasks, and project progress. |
| 搜索、筛选、排序 | Search, Filter, Sort | 支持文本、状态、Overdue、计划日期区间、优先级、分类、标签、项目和稳定排序；筛选使用 AND 语义。<br>Search and organize tasks by text, status, overdue state, planned-date bucket, priority, category, tag, project, and stable sort; filters use AND semantics. |
| 日 / 周 / 月日历 | Day / Week / Month Calendar | 查看计划任务、Time Block 和 Deadline；月视图日期可进入现有 Day View。<br>View planned tasks, Time Blocks, and Deadlines; Month dates can open the existing Day View. |
| 时间块 | Time Block | 为任务设置本地开始/结束时间和时区。<br>Schedule a task with local start/end times and a timezone. |
| 截止日期 | Deadline | 支持日期型和定时 Deadline，并保留时区与 DST 语义。<br>Support date-only and timed Deadlines with timezone and DST-aware semantics. |
| 提醒 | Reminder | 支持指定时间提醒、pending、acknowledged 和 dismissed 状态。<br>Support specified-time reminders with pending, acknowledged, and dismissed states. |
| 重复任务 | Recurrence / Repeat | 支持 Daily、选定星期和 Monthly 规则，并按现有规则处理 occurrence。<br>Support daily, selected-weekday, and monthly recurrence rules with explicit occurrence handling. |
| 每日 / 每周复盘 | Daily / Weekly Review | 以只读方式查看完成、Overdue、Carryover 和项目当前快照。<br>Review completed, overdue, carryover, and current project facts in a read-only view. |
| 快速调整日期 | Quick Reschedule | Pending Task 可调整到 Today、Tomorrow、Next Monday、Inbox 或自选日期。<br>Reschedule pending Tasks to Today, Tomorrow, Next Monday, Inbox, or a chosen date. |
| 软删除与撤销 | Soft Delete / Undo | 删除任务时保留可恢复的软删除状态和 Undo 路径。<br>Use recoverable soft deletion with an Undo path. |
| 本地 SQLite 持久化 | Local SQLite Persistence | 任务和项目数据默认持久化在本机。<br>Tasks and projects persist locally by default. |

## 界面与工作流 / Workflow

DayFlow Personal 的日常工作流保持简单：先记录，再安排，再执行，最后复盘。

DayFlow Personal follows a simple daily loop: capture first, plan next, execute, and review.

```text
记录 Capture
   ↓
收件箱 Inbox
   ↓
规划 Plan
   ↓
Today / Calendar
   ↓
完成或调整 Complete / Reschedule
   ↓
复盘 Review
```

- **收集 / Capture:** 快速创建任务，随后决定是否安排日期、时间块、项目或其他元数据。<br>
  Create a task quickly, then decide whether to add a planned date, Time Block, project, or other metadata.
- **规划 / Plan:** Inbox 用于未安排任务；Today、Calendar 和 Task Editor 用于更具体的计划。<br>
  Inbox is for unscheduled work; Today, Calendar, and Task Editor support more specific planning.
- **执行 / Execute:** Today 聚焦当前计划，Calendar 提供 Day、Week、Month 视角。<br>
  Today focuses on the current plan, while Calendar provides Day, Week, and Month views.
- **复盘 / Review:** `#review` 保持只读，帮助查看完成、Overdue、Carryover 和项目当前状态。<br>
  `#review` is read-only and helps inspect completed work, Overdue tasks, Carryover, and current project state.

### 快速调整日期 / Quick Reschedule

Quick Reschedule 只面向 Pending Task，动作包括：Today、Tomorrow、Next Monday、移回收件箱和选择日期。普通动作只修改 `planned_date`；移回收件箱会同时清除 `schedule`。Deadline、Reminder 和 Recurrence 不会被隐式修改。

Quick Reschedule is available for pending Tasks with Today, Tomorrow, Next Monday, Move to Inbox, and Choose Date actions. Normal actions change only `planned_date`; moving a task to Inbox also clears `schedule`. Deadline, Reminder, and Recurrence are not changed implicitly.

Today、Tomorrow 和 Next Monday 以 DayFlow runtime 的 `local_date` 为日期基准，而不是浏览器时区或 UTC 日期。带 Time Block 的任务跨日期移动时，Backend 保留本地时钟和时区并重新计算 UTC；冲突继续使用现有确认流程。

Today, Tomorrow, and Next Monday use the DayFlow runtime `local_date`, not the browser timezone or a UTC date. When a scheduled task moves across dates, the Backend preserves its local clock and timezone while recalculating UTC instants; conflicts use the existing confirmation flow.

## 技术栈 / Tech Stack

- Vue 3 + TypeScript + Vite + Element Plus
- Python 3.12 + FastAPI + Pydantic
- Synchronous SQLAlchemy 2.x
- SQLite + Alembic

## 快速开始 / Quick Start

### 环境要求 / Prerequisites

- Python 3.12
- Node.js 24 LTS
- [`uv`](https://docs.astral.sh/uv/)

### 初始化开发环境 / Set Up a Development Environment

以下示例使用临时数据库。不要把真实个人数据库用于测试或首次初始化。

The following setup uses a temporary database. Do not use the real personal database for tests or first-time setup.

```bash
uv sync --directory backend
npm ci --prefix frontend
DAYFLOW_DATABASE_PATH=/tmp/dayflow-development.sqlite3 \
  uv run --directory backend alembic upgrade head
```

### 启动 Backend / Run the Backend

```bash
DAYFLOW_DATABASE_PATH=/tmp/dayflow-development.sqlite3 \
  uv run --directory backend uvicorn app.main:app \
  --reload --host 127.0.0.1 --port 8000
```

### 启动 Frontend / Run the Frontend

在另一个终端执行：

Run this in a second terminal:

```bash
npm run dev --prefix frontend
```

### WSL 日常启动 / Daily WSL Launch

在项目根目录执行：

From the project root, run:

```bash
./scripts/dayflow-start.sh
```

启动脚本会检查运行环境、端口、Backend 健康状态、应用版本和真实数据库 Schema，不会自动执行 Migration，也不会创建测试数据。停止由脚本创建的服务：

The launcher checks the runtime environment, ports, Backend health, application version, and database schema. It does not run migrations or create test data. Stop services created by the launcher with:

```bash
./scripts/dayflow-stop.sh
```

## 项目结构 / Project Structure

```text
backend/     FastAPI API, services, models, migrations, and Backend tests
frontend/    Vue application, unit tests, and Playwright E2E tests
docs/        API, architecture, and database documentation
scripts/     Local WSL start/stop scripts
data/        Ignored local runtime data; never commit personal data
```

```text
backend/     FastAPI API、服务、模型、迁移和 Backend 测试
frontend/    Vue 应用、单元测试和 Playwright E2E 测试
docs/        API、架构和数据库文档
scripts/     本地 WSL 启停脚本
data/        被 Git 忽略的本地运行数据；不要提交个人数据
```

## 数据与隐私 / Data & Privacy

真实 SQLite 数据库默认位于 `data/dayflow.sqlite3`，属于个人运行数据，已被 Git 忽略，不会包含在 GitHub 仓库或 Release 中。应用以本地运行和本地持久化为核心，不要求云端账户。

The real SQLite database normally lives at `data/dayflow.sqlite3`. It is personal runtime data, ignored by Git, and not included in the GitHub repository or Release. The application is built around local execution and local persistence and does not require a cloud account.

测试、浏览器 E2E 和迁移演练必须使用隔离临时数据库。不要把 `.env`、真实数据库、备份、虚拟环境、`node_modules` 或测试产物复制到 Git。

Tests, browser E2E runs, and migration rehearsals must use isolated temporary databases. Do not copy `.env`, the real database, backups, virtual environments, `node_modules`, or test artifacts into Git.

## 备份与恢复 / Backup & Restore

DayFlow 提供维护界面的 Backup Create、List 和 Verify。备份使用 SQLite Online Backup API，以处理活动数据库的 WAL 数据；不要直接复制正在运行的数据库主文件。

DayFlow provides Backup Create, List, and Verify through the maintenance view. Backups use SQLite’s Online Backup API so committed WAL data is handled safely; do not directly copy the main file of an active database.

当前边界如下：

The current boundary is:

- **Backup / 备份:** available
- **Real Restore / 真实数据库恢复:** prohibited
- **Storage Qualification / 存储资格:** `NOT QUALIFIED`
- 目前只验证了独立系统临时数据库上的隔离 Restore 流程。<br>
  Restore execution has only been verified for independent system-temporary databases.

真实个人数据库、备份和维护状态属于本地数据，必须在删除 WSL 或迁移环境前单独备份；它们不是 GitHub Repository 或 Release 的内容。

The real personal database, backups, and maintenance state are local-only data. Back them up separately before retiring or migrating the WSL environment; they are not part of the GitHub repository or Release.

## 测试 / Testing

Backend 和 Frontend 测试使用隔离临时数据库，不得访问 `data/dayflow.sqlite3`。

Backend and Frontend tests use isolated temporary databases and must never access `data/dayflow.sqlite3`.

```bash
uv run --directory backend pytest
npm run test --prefix frontend
```

浏览器 E2E 使用一次性的临时 SQLite 数据库、headless Chromium、Backend `18000` 和 Frontend `15173`：

Browser E2E uses a fresh temporary SQLite database, headless Chromium, Backend port `18000`, and Frontend port `15173`:

```bash
npm run test:e2e --prefix frontend
npm run test:e2e:ui --prefix frontend
```

首次运行前只需安装 Playwright Chromium：

Install the Playwright Chromium browser once before the first run:

```bash
npm exec --prefix frontend playwright install chromium
```

## 当前版本 / Release Status

- **Stable Release / 稳定版本:** `v1.0.0`
- **Application Version / 应用版本:** `1.0.0`
- **Release Commit / 发布 Commit:** `8a941b5a15ef9eaeb18b9a415710f9d7deb7133e`
- **Database Schema / 数据库 Schema:** `0005_add_deadlines_recurrence_reminders`
- **Migration / 数据库迁移:** NO；`0006` 不存在 / `0006` does not exist
- **V1.0 Product Maturity Audit:** PASS
- **V1.0 Final Product Acceptance:** PASS

当前正式验收基线：Backend 414 passed、Frontend 127 passed、Playwright 52 passed、Type-check PASS、Build PASS。

The accepted release baseline is: Backend 414 passed, Frontend 127 passed, Playwright 52 passed, Type-check PASS, and Build PASS.

低风险 UX 改进仍延后至 1.x；V1.0 的重点是稳定、可理解、可恢复的个人任务管理闭环，而不是继续扩大功能范围。

Additional low-risk UX improvements remain deferred to 1.x. V1.0 focuses on a stable, understandable, and recoverable personal task workflow rather than continued feature expansion.

完整历史请参阅 [`CHANGELOG.md`](CHANGELOG.md) 与 [`ROADMAP.md`](ROADMAP.md)。

See [`CHANGELOG.md`](CHANGELOG.md) and [`ROADMAP.md`](ROADMAP.md) for the full release history.
