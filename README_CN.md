# DayFlow Personal

一个本地优先、面向单用户的个人任务与日程管理工具。

[English](README.md) | [简体中文](README_CN.md)

[发布版本](https://github.com/MartaBanion/DayFlow/releases/tag/v1.0.0) · [更新日志](CHANGELOG.md) · [路线图](ROADMAP.md) · [项目文档](docs/)

**稳定版本：** `v1.0.0`<br>
**应用版本：** `1.0.0`

## 目录

- [DayFlow 是什么？](#dayflow-是什么)
- [为什么做 DayFlow？](#为什么做-dayflow)
- [核心功能](#核心功能)
- [日常工作流](#日常工作流)
- [产品原则](#产品原则)
- [架构](#架构)
- [任务模型概览](#任务模型概览)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [开发与测试](#开发与测试)
- [主要页面](#主要页面)
- [API 概览](#api-概览)
- [数据模型](#数据模型)
- [数据与隐私](#数据与隐私)
- [备份与恢复](#备份与恢复)
- [测试与质量](#测试与质量)
- [版本历史](#版本历史)
- [已知限制](#已知限制)
- [路线图](#路线图)
- [文档](#文档)
- [发布状态](#发布状态)

## DayFlow 是什么？

DayFlow Personal 是一个本地优先、面向单用户的个人任务管理和日程管理工具。它把任务记录、规划、排程、执行、调整和复盘放在一套清晰的工作流中。

DayFlow 不是企业协作平台，不是多用户 SaaS，也不是云端任务服务。它面向希望使用可靠本地工作区进行日常规划的个人用户。

## 为什么做 DayFlow？

许多 Todo List 工具主要解决“记录任务”。DayFlow 进一步关注任务如何贯穿一天：

```text
记录
   ↓
收件箱
   ↓
规划
   ↓
Today / Calendar
   ↓
完成 / 调整日期
   ↓
复盘
```

- 未规划的工作可以先留在 Inbox，准备好后再安排日期。
- Today 聚焦当前这一天的工作。
- Calendar 通过 Day、Week 和 Month 视图支持日期与时间规划。
- Quick Reschedule 用于处理计划变化，不会隐式修改截止日期、提醒或重复规则。
- Review 提供只读的每日和每周当前状态视图。
- 任务数据保存在本地 SQLite 中。

## 核心功能

### 记录与收件箱

- 创建和编辑任务，可填写描述及规划字段。
- 将没有计划日期的待处理任务保存在 Inbox。
- 使用优先级、分类、标签和项目组织任务。
- Inbox 查询不会改变收件箱语义：始终只查询待处理、未安排、未删除的任务。

### Today

- 聚焦 DayFlow 当前日期的任务计划。
- 完成和恢复任务。
- 软删除任务，并在需要时使用撤销。
- 为待处理任务打开现有的 Quick Reschedule 菜单。

### Calendar

- Day View、Week View 和 Month View。
- 展示日期任务和 Time Block。
- 任务移动到其他日期时，保留本地时钟与时区语义。
- 从 Month 日期选择和“还有 N 项”进入现有 Day View。

### 任务组织

- 全局 Search 支持文本、状态、逾期、计划日期区间、优先级、分类、标签、项目、Inbox 和排序。
- 任务查询复用统一语义，多个有效筛选条件使用 AND 关系。
- 项目列表、项目详情、项目任务筛选和计算得到的项目进度。

### 规划

- 计划日期：准备在哪一天处理任务。
- 截止日期：任务应完成的日期或具体时间点。
- 提醒：指定的提醒触发时间。
- 重复规则：每日、指定星期和每月任务规则。
- Time Block：带时区的本地开始和结束时间段。
- Quick Reschedule：Today、Tomorrow、Next Monday、移回 Inbox 和选择日期。

### 复盘

- 每日和每周当前状态 Review。
- 已完成、逾期和 Carryover 任务列表。
- 当前项目事实和进度。
- 只读复盘不会物化重复任务，也不会修改业务数据。

### 本地数据

- 使用 SQLite 持久化本地任务和项目数据。
- 通过软删除和可恢复的任务状态路径保留安全边界。
- 使用乐观版本控制降低并发编辑时的静默覆盖风险。
- 通过维护边界提供备份创建、列表和验证能力。

## 日常工作流

DayFlow 围绕一套简短、可重复的日常循环组织：

```text
记录
   ↓
收件箱
   ↓
规划
   ↓
Today / Calendar
   ↓
完成 / 调整日期
   ↓
复盘
```

1. **记录：** 先创建任务，不要求一次性完成所有规划决定。
2. **收件箱：** 在任务尚未明确时，先让未安排工作保持可见。
3. **规划：** 按需要添加计划日期、项目、优先级、分类、标签、截止日期、提醒、重复规则或 Time Block。
4. **Today / Calendar：** 执行当前计划，并从 Day、Week 或 Month 视角查看工作。
5. **完成 / 调整日期：** 完成任务，或在计划变化时使用 Quick Reschedule。
6. **复盘：** 查看当前已完成、逾期、Carryover 和项目事实。

## 产品原则

### 本地优先

用户任务数据保存在本地 SQLite 中。GitHub 仓库保存源码和文档，不保存个人任务数据。

### 单用户

DayFlow 专门面向个人使用，不提供账户、团队、权限或多人协作模型。

### 工作流优先于功能数量

项目优先保证记录、规划、执行和复盘之间的连贯流程，而不是不断增加互不关联的功能。

### 明确的任务语义

计划日期、截止日期、提醒、重复规则和 Time Block 是不同概念。Quick Reschedule 只调整计划日期；移回 Inbox 时还会清除维持 Inbox 不变量所需的时间安排。

### 数据归属

GitHub 保存源码、文档、Git 历史和发布标签。真实个人数据库和本地备份由用户自行控制，不属于仓库内容。

## 架构

DayFlow 是一个本地优先的模块化单体应用，由 Vue 浏览器客户端、FastAPI 服务和 SQLite 组成。

```text
浏览器
   │
   ▼
Vue 3 + TypeScript + Vite + Element Plus
   │
   │ HTTP / REST
   ▼
FastAPI
   │
   ▼
同步 SQLAlchemy 2.x
   │
   ▼
SQLite
```

- **前端：** Vue 3、TypeScript、Vite 和 Element Plus。
- **后端：** Python 3.12 和 FastAPI。
- **ORM：** 同步 SQLAlchemy 2.x。
- **数据库：** SQLite。
- **迁移：** Alembic。

参见[架构文档](docs/ARCHITECTURE.md)。

## 任务模型概览

| 概念 | 含义 |
| --- | --- |
| 计划日期 | 用户准备处理任务的本地日期。 |
| 截止日期 | 任务应完成的日期，或具体的本地时间点。 |
| 提醒 | 与任务关联的提醒触发条件。 |
| 重复规则 | 描述未来任务实例的规则。 |
| Time Block | 带时区的本地开始和结束时间段。 |

这些概念具有不同语义。使用 Quick Reschedule 移动任务时，不会隐式重写截止日期、提醒或重复规则。

## 技术栈

| 层次 | 技术 |
| --- | --- |
| 前端 | Vue 3、TypeScript、Vite、Element Plus |
| 后端 | Python 3.12、FastAPI |
| ORM | SQLAlchemy 2.x |
| 数据库 | SQLite |
| 迁移 | Alembic |
| 后端测试 | pytest |
| 前端测试 | Vitest |
| 端到端测试 | Playwright |
| 版本控制 | Git |

## 项目结构

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

- `backend/`：API、服务、模型、迁移和后端测试。
- `frontend/`：Vue 应用、单元测试和 Playwright 测试。
- `docs/`：API、架构和数据库核心文档。
- `scripts/`：本地启动和停止辅助脚本。
- `data/`：仅用于被 Git 忽略的本地运行时数据。

## 快速开始

下面的命令使用隔离的临时数据库建立开发环境。首次设置、测试和迁移演练都不要使用真实个人数据库。

### 前置要求

- Python 3.12。
- Node.js 24 或更高版本。
- [`uv`](https://docs.astral.sh/uv/)。
- Git。

### 克隆项目

```bash
git clone https://github.com/MartaBanion/DayFlow.git
cd DayFlow
```

### 配置后端

```bash
uv sync --directory backend
```

### 配置前端

```bash
npm ci --prefix frontend
```

### 初始化数据库

将隔离的开发数据库初始化到 `/tmp/dayflow-development.sqlite3`：

```bash
DAYFLOW_DATABASE_PATH=/tmp/dayflow-development.sqlite3 \
  uv run --directory backend alembic upgrade head
```

### 启动

让后端使用隔离数据库启动：

```bash
DAYFLOW_DATABASE_PATH=/tmp/dayflow-development.sqlite3 \
  uv run --directory backend uvicorn app.main:app \
  --reload --host 127.0.0.1 --port 8000
```

在第二个终端启动前端：

```bash
npm run dev --prefix frontend
```

如果已经有本地 DayFlow 运行时数据库，可以使用项目启动器同时启动两个服务，并执行健康、版本、维护状态和 Schema 检查：

```bash
./scripts/dayflow-start.sh
```

使用下面的命令停止启动器创建的服务：

```bash
./scripts/dayflow-stop.sh
```

启动器不会创建测试数据，也不会运行迁移。默认情况下，它检查 `data/dayflow.sqlite3` 中的真实本地数据库；请将它与隔离的开发数据库和测试数据库分开。

### 打开页面

- 前端：<http://127.0.0.1:5173>
- 后端：<http://127.0.0.1:8000>
- 健康检查：<http://127.0.0.1:8000/healthz>

## 开发与测试

运行后端测试：

```bash
uv run --directory backend pytest
```

运行前端单元测试：

```bash
npm run test --prefix frontend
```

运行类型检查和生产构建：

```bash
npm run type-check --prefix frontend
npm run build --prefix frontend
```

使用项目的隔离测试运行器执行 Chromium 端到端测试：

```bash
npm run test:e2e --prefix frontend
npm run test:e2e:ui --prefix frontend
```

首次运行前按需安装 Playwright 浏览器：

```bash
npm exec --prefix frontend playwright install chromium
```

浏览器端到端测试使用隔离临时数据库、无头 Chromium、专用本地端口 `18000` 和 `15173`，并在测试 SQLite 时保持一个 worker。测试绝不能回退使用 `data/dayflow.sqlite3` 或 `data/backups/`。

## 主要页面

| 页面 | 作用 |
| --- | --- |
| Today | 执行和维护当天的计划。 |
| Inbox | 保存还没有计划日期的待处理任务。 |
| Calendar | 从 Day、Week 和 Month 视图查看并调整工作。 |
| Search | 在未删除任务范围内搜索、筛选、排序和查看任务。 |
| Projects | 管理项目，查看项目任务列表和进度。 |
| Review | 只读查看每日、每周的完成、逾期、Carryover 和项目事实。 |

## API 概览

后端在 `/api/v1` 下提供版本化 API，主要围绕以下领域组织：

- 任务和任务查询筛选。
- 项目、分类和标签。
- Calendar 和运行时日期信息。
- Today 与 This Week 的 Review 范围。
- 重复规则和提醒操作。
- 备份和维护状态。

Quick Reschedule 复用现有的带版本任务更新路径，不会增加独立的规划 API。相关契约是 `PATCH /api/v1/tasks/{id}?version=<version>`；Inbox 搜索仍然使用带 `inbox=true&q=<query>` 的收件箱范围查询。

参见 [API 文档](docs/API.md)。

## 数据模型

主要业务模型包括 Task、Project、Category、Tag、Time Block、Deadline、Recurrence 和 Reminder。Task 可以拥有计划日期、可选 Time Block、可选 Deadline 和 Reminder 数据，以及可选 Recurrence 关系，同时保持明确的状态语义。

当前 Schema 和迁移历史参见[数据库文档](docs/DATABASE.md)。

## 数据与隐私

DayFlow 是本地优先应用。用户任务数据保存在本地 SQLite 中，通常位于 `data/dayflow.sqlite3`，不会包含在 GitHub 仓库或 GitHub Release 中。

GitHub 仓库和全新 clone 可以恢复源码、文档、Git 历史和发布标签，但不能恢复个人任务数据、本地数据库或本地备份数据。

以下内容属于本地数据，不能提交到仓库：

- `data/dayflow.sqlite3`
- `data/backups/`
- `data/maintenance/`
- `.env` 和其他本地配置

测试和浏览器端到端测试使用隔离临时数据库。不要把本地运行时状态、虚拟环境、`node_modules` 或测试产物复制到仓库。

## 备份与恢复

DayFlow 通过维护边界提供备份创建、列表和验证能力。备份使用 SQLite Online Backup API，以安全处理已经提交的 WAL 数据；不支持直接复制运行中数据库的主文件作为备份方式。

当前 v1.0.0 边界如下：

- **Backup：** available。
- **Real Restore：** PROHIBITED。
- **Storage Qualification：** `NOT QUALIFIED`。

Restore 执行只针对独立的系统临时数据库完成隔离验证。真实个人数据库在退出或迁移本地环境前必须单独备份；GitHub 不包含这些数据。

## 测试与质量

以下是 V1.0 正式发布验收基线，并不承诺测试数量永远不变：

| 检查项 | 结果 |
| --- | --- |
| Backend | 414 passed |
| Frontend | 127 passed |
| Playwright | 52 passed |
| Type-check | PASS |
| Build | PASS |

正式发布验收时，测试使用隔离临时数据库，真实个人数据库保持不变。

## 版本历史

| 版本 | 里程碑 |
| --- | --- |
| `v1.0.0` | Product Maturity：稳定的记录、Inbox、Today、Calendar、Search、Projects、Deadline、Reminder、Recurrence、Review 和 Quick Reschedule 工作流。 |
| `v0.9.0` | Quick Reschedule 和轻量 Month 到 Day 下钻。 |
| `v0.8.0` | Search、Filter、Sort 和 Project 查询复用。 |
| `v0.7.0` | 每日与每周 Review。 |
| `v0.6.0` | 数据安全与恢复基础能力。 |
| `v0.5.x` | Deadline、Reminder、Recurrence 和界面优化。 |

详细历史参见 [CHANGELOG.md](CHANGELOG.md)。

## 已知限制

- 由于 Storage Qualification 为 `NOT QUALIFIED`，真实项目数据库的 Real Restore 仍然禁止。
- 较窄桌面布局下，Calendar 可能需要使用内部横向滚动。
- Reminder 的 acknowledge/dismiss 失败反馈仍可改进。
- skip-to-content 仍延期处理。

这些是已知边界或低风险体验改进，不影响 v1.0.0 的正常日常使用。

## 路线图

1.x 继续聚焦渐进式产品成熟度提升：

- 界面体验优化。
- 实用的可访问性改进。
- 更清晰的 Reminder 操作反馈。
- 基于实际证据的小步工作流改进。

当前版本范围有意不继续扩展大型功能。维护中的路线图参见 [ROADMAP.md](ROADMAP.md)。

## 文档

- [架构](docs/ARCHITECTURE.md)
- [API](docs/API.md)
- [数据库](docs/DATABASE.md)
- [路线图](ROADMAP.md)
- [更新日志](CHANGELOG.md)
- [English README](README.md)

## 发布状态

- **稳定版本：** `v1.0.0`
- **应用版本：** `1.0.0`
- **发布 Commit：** `8a941b5a15ef9eaeb18b9a415710f9d7deb7133e`
- **数据库 Schema：** `0005_add_deadlines_recurrence_reminders`
- **Migration：** NO；不存在 `0006`
- **状态：** Released / Stable
- **GitHub Release：** <https://github.com/MartaBanion/DayFlow/releases/tag/v1.0.0>

DayFlow Personal 是一个本地优先的个人生产力项目。
