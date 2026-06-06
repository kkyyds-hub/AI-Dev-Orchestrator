# Coding Session 生命周期设计基线

> **文档类型**: 设计基线 / 一致性审计
> **生成日期**: 2026-06-04
> **基准 commit (AI-Dev-Orchestrator)**: `55d1579` (docs: agent session lifecycle gap analysis and four-axis design audit)
> **参考项目 agent-orchestrator**: `c3eeecb` (merge fork, 25 May - 2 June, #2086)
> **边界**: 只做设计和只读推导，不改代码、不建表、不加 API、不启动服务
> **状态**: 设计基线完成

---

## 目录

1. [AI-Dev 当前链路](#1-ai-dev-当前-project--task--run--agentsession--repository--approval-链路)
2. [当前 AgentSession 为什么不是 CodingSession](#2-当前-agentsession-为什么不是-codingsession)
3. [参考项目 agent-orchestrator 的可复用点](#3-参考项目-agent-orchestrator-的可复用点)
4. [新增 CodingSession 还是改造 AgentSession](#4-新增-codingsession-还是改造现有-agentsession)
5. [四轴生命周期模型](#5-四轴生命周期模型)
6. [每轴状态枚举](#6-每轴状态枚举)
7. [已有字段到四轴映射](#7-当前-ai-dev-已有字段如何映射到四轴)
8. [缺失清单](#8-缺失字段缺失服务缺失-api-清单)
9. [Worktree / Branch / PR 分阶段路线](#9-worktree--branch--pr-的分阶段路线)
10. [失败回流机制设计](#10-失败回流机制设计)
11. [第一阶段最小落地范围](#11-第一阶段最小落地范围)
12. [明确不建议现在做的](#12-明确不建议现在做的)

---

## 0. 核对过的文件清单

### AI-Dev-Orchestrator (已核对)

| 文件 | 用途 |
|------|------|
| `.kkr/skills/ai-project-director-command-governance/SKILL.md` | 指令治理规范 |
| `docs/product/ai-project-director/page-information-architecture-20260518.md` | 主产品基线 |
| `docs/product/ai-project-director/closure-flow-20260518.md` | 闭环流程设计 |
| `docs/product/ai-project-director/closure-checklist-20260518.md` | 闭环验收清单 |
| `runtime/orchestrator/app/domain/task.py` | Task 领域模型 |
| `runtime/orchestrator/app/domain/run.py` | Run 领域模型 |
| `runtime/orchestrator/app/domain/project.py` | Project 领域模型 |
| `runtime/orchestrator/app/domain/agent_session.py` | AgentSession 领域模型 |
| `runtime/orchestrator/app/domain/agent_message.py` | AgentMessage 领域模型 |
| `runtime/orchestrator/app/api/routes/workers.py` | Worker API |
| `runtime/orchestrator/app/api/routes/agent_threads.py` | AgentSession API |
| `runtime/orchestrator/app/api/routes/repositories.py` | Repository API |
| `runtime/orchestrator/app/services/local_git_write_service.py` | 本地 Git 写入 |
| `runtime/orchestrator/app/services/git_write_state_tracker.py` | Git 写入状态追踪 |
| `runtime/orchestrator/app/services/branch_session_service.py` | 分支会话服务 |
| `runtime/orchestrator/app/workers/task_worker.py` | TaskWorker |
| `runtime/orchestrator/app/core/db_tables.py` | 数据库表定义 |

### agent-orchestrator (已核对)

| 文件 | 用途 |
|------|------|
| `README.md` | 项目概览 |
| `CLAUDE.md` | 开发文档 |
| `ARCHITECTURE.md` | 架构设计 |
| `DESIGN.md` | 设计系统 |
| `docs/PLUGIN_SPEC.md` | 插件规范 |
| `packages/core/src/types.ts` | 核心类型定义 (Session, Runtime, Agent, Workspace, SCM, Lifecycle) |
| `packages/core/src/lifecycle-state.ts` | CanonicalSessionLifecycle 解析/推导 |
| `packages/core/src/lifecycle-manager.ts` | 生命周期管理器 (轮询循环 + 状态判定) |
| `packages/core/src/lifecycle-transition.ts` | 生命周期转换服务 |
| `packages/core/src/session-manager.ts` | 会话管理器 (CRUD) |
| `packages/core/src/metadata.ts` | 元数据持久化 |

---

## 1. AI-Dev 当前 Project → Task → Run → AgentSession → Repository → Approval 链路

### 1.1 链路总览

```
ProjectDirectorSession (目标澄清, status=draft→confirmed)
  → ProjectDirectorPlanVersion (计划草案, status=draft→approved/rejected)
    → ProjectDirectorTaskCreationRecord (任务创建记录, immutable)
      → Project (正式项目, stage=intake→planning→execution→verification→delivery)
        → Task (任务, status=pending→running→completed/failed/blocked)
          → Run (执行记录, status=queued→running→succeeded/failed/cancelled)
            → AgentSession (Day11, status=running→review_rework→completed/failed/blocked)
        → RepositoryWorkspace (仓库绑定, access_mode=read_only)
          → RepositorySnapshot (快照)
          → ChangeSession (分支/工作区状态, workspace_status=clean/dirty)
            → ChangePlan → ChangeBatch → CommitCandidate (draft only)
        → Deliverable → DeliverableVersion (交付物)
          → ApprovalRequest → ApprovalDecision (审批)
```

### 1.2 Run 包含的字段 (当前)

| 类别 | 字段 | 是否支持 agent session 维度 |
|------|------|---------------------------|
| Provider | `provider_key`, `model_name` | 部分——记录 AI provider，但不记录 agent 类型 |
| Token/Cost | `total_tokens`, `prompt_tokens`, `completion_tokens`, `estimated_cost`, `cache_*` | 是 |
| Routing | `routing_score`, `route_reason`, `strategy_decision` (JSON) | 部分 |
| Role | `owner_role_code`, `upstream_role_code`, `downstream_role_code` | 部分 |
| Verification | `verification_mode`, `verification_command`, `verification_summary` | 否 |
| **Missing** | **agent_type**, **runtime_type**, **workspace_type**, **worktree_path**, **branch_name**, **pr_url**, **ci_status**, **review_status** | **否——完全缺失** |

### 1.3 AgentSession 包含的字段 (当前)

| 字段 | 值 | 说明 |
|------|-----|------|
| `status` | running / review_rework / completed / failed / blocked | 内部审查生命周期 |
| `review_status` | none / review_required / rework_required / review_passed | 审查状态 |
| `current_phase` | context_ready / executing / reviewing / reworking / finalized | 当前阶段 |
| `owner_role_code` | ProjectRoleCode | 负责角色 |
| `context_checkpoint_id` | string | 上下文检查点 |
| `latest_intervention_type` | string | 最近干预类型 |
| **缺失** | agent_type, runtime_type, workspace_type, worktree_path, branch_name, coding_status, activity_state, delivery_status, pr_url, ci_status, review_decision | 完全缺失编码会话维度 |

### 1.4 ChangeSession 包含的字段

| 字段 | 说明 |
|------|------|
| `current_branch`, `head_commit_sha` | 当前分支和提交 |
| `baseline_branch`, `baseline_commit_sha` | 基线分支 |
| `workspace_status` | clean / dirty |
| `guard_status` | ready / blocked |
| `dirty_files` | 脏文件列表 |

**关键限制**: ChangeSession 是项目级别的（1 project = 1 ChangeSession），不是 per-run 的。它不是 CodingSession 的 workspace 维度——它是仓库快照，不是会话工作区。

---

## 2. 当前 AgentSession 为什么不是 CodingSession

### 2.1 定义差异

| 维度 | CodingSession (需要的能力) | AgentSession (当前的实际) |
|------|--------------------------|-------------------------|
| **执行载体** | 知道 agent 是什么 (claude-code / codex / opencode) | 不知道——AgentSession 创建时不区分 agent 类型 |
| **运行环境** | 知道在哪运行 (tmux / subprocess / docker) | 不知道——`TaskWorker` 用 subprocess，但 AgentSession 不记录 |
| **工作区** | 有独立的 git worktree 和 branch | 没有——ChangeSession 是项目级的，不绑定到 Run |
| **实时状态** | 知道 agent 是否还在运行 (alive / exited / stuck) | 不知道——AgentSession 只记录 "外部审查后我被告知的结果" |
| **代码产出** | 追踪 branch → PR → CI → review → merge | 完全没有——所有字段都是内部审查流程 |
| **角色定位** | "这一次 agent 编码会话" | "这一次 run 的审查记录" |

### 2.2 根因

`AgentSession` 的创建时机是 `TaskWorker.run_once()` 的第 648-666 行:

```python
agent_session = self.agent_conversation_service.start_session(
    project_id=task.project_id,
    task_id=task.id,
    run_id=run.id,
    owner_role_code=run.owner_role_code,
    context_seed=context_seed,
)
```

此时 AgentSession 的作用是:
1. 记录"一个 run 开始了，它属于某个角色"
2. 在 run 结束时更新 `status` 和 `review_status`
3. 为 Day12 的 review/rework 流程提供数据源

它**不负责**:
- 启动 agent 进程
- 创建 git worktree
- 创建 git branch
- 监控 agent 进程状态
- 轮询 CI 状态
- 追踪 PR

### 2.3 与 agent-orchestrator Session 的差距

| 能力 | agent-orchestrator | AI-Dev (当前) |
|------|-------------------|--------------|
| 创建隔离 worktree | `Workspace.create()` per session | 无 |
| 创建 git branch | `session.branch` per session | 无 |
| 启动 agent 进程 | `Runtime.create()` + `Agent.getLaunchCommand()` | TaskWorker 同步调用 `subprocess` |
| 探活 | `Runtime.isAlive()` + `Agent.isProcessRunning()` | 无 |
| 活动检测 | `Agent.getActivityState()` (active/ready/idle/waiting_input/blocked/exited) | 无 |
| PR 检测 | `SCM.detectPR()` | 无 |
| CI 监控 | `SCM.getCIChecks()` + batch enrichment | 无 |
| Review 监控 | `SCM.getReviewThreads()` | 无 |
| 自动响应 | `LifecycleManager` reaction engine | 无 |
| 会话恢复 | `SessionManager.restore()` | 无 |

---

## 3. 参考项目 agent-orchestrator 的可复用点

### 3.1 强烈建议借鉴的设计

#### a. CanonicalSessionLifecycle 三元组

agent-orchestrator 的核心抽象:

```typescript
interface CanonicalSessionLifecycle {
  version: 2;
  session: { kind, state, reason, startedAt, completedAt, terminatedAt, lastTransitionAt };
  pr: { state, reason, number, url, lastObservedAt };
  runtime: { state, reason, lastObservedAt, handle, tmuxName };
}
```

**三元组分离是 agent-orchestrator 最成功的架构决策**——三个维度独立变化，联合推导整体状态。本项目应扩展为四元组 (session / workspace / runtime / delivery)。

#### b. LifecycleManager 轮询循环

```typescript
// 定期轮询所有 session，判定状态转换并触发 reactions
LifecycleManager.start(intervalMs);
// 每轮:
// 1. populatePREnrichmentCache (批量 SCM 查询)
// 2. determineStatus (检查 runtime + agent 活动 + PR 状态)
// 3. commit lifecycle state change
// 4. dispatch reactions (CI failure → send-to-agent, etc.)
```

**适用于本项目的场景**: 当 coding session 以 tmux/process 方式运行后，需要一个后台轮询器来检测 agent 是否还在运行。

#### c. 状态推导优于状态存储

agent-orchestrator 的 `deriveLegacyStatus()` 从三元组推导出一个扁平状态:

```typescript
function deriveLegacyStatus(lifecycle): SessionStatus {
  // session.state + pr.state + runtime.state → 单一 status
  // 不存储冗余的 "整体状态" 字段
}
```

**适用于本项目**: 四轴状态联合推导整体状态，不在多个表中存储冗余字段。

#### d. ActivitySignal — 活动检测置信度

```typescript
type ActivitySignalState = "valid" | "stale" | "null" | "unavailable" | "probe_failure";
```

**适用于本项目**: 当 agent 进程探活失败时，区分 "进程确实死了" 和 "探活机制暂时不可用"。

### 3.2 部分可借鉴的设计

| 设计 | 借鉴程度 | 说明 |
|------|---------|------|
| 8 插件槽 | 部分 | 不需要完整插件系统，但 SCM 抽象层 (detectPR/getCI/getReviews) 建议在 P2 引入 |
| Session metadata 文件系统 | 不借鉴 | AI-Dev 用 SQLite，有完整关系模型 |
| Reaction 引擎 | 部分 | CI 失败自动通知 agent 修复的模式值得参考，但不需要完整的 reaction config |
| PR 为中心的交付状态机 | 部分 | AI-Dev 的交付单位是 CommitCandidate + Approval，PR 只是可选的交付通道 |

### 3.3 不适合借鉴的设计

- **以 Session 为顶层调度单元**: AI-Dev 以 Project → Task 为顶层
- **文件系统 metadata**: AI-Dev 用 SQLite + FK 约束
- **tmux 作为默认 runtime**: 当前以 subprocess 为主
- **独立 CLI (ao spawn/status/kill)**: AI-Dev 是 web-first API 应用

---

## 4. 新增 CodingSession 还是改造现有 AgentSession

### 4.1 明确结论: 改造现有 AgentSession，新增 coding 维度字段，不新建表

**理由**:

1. **FK 链已存在**: `AgentSession` 已经有 `project_id → task_id → run_id` 的 FK 链，这是 CodingSession 和 Run 之间的天然桥接。新建表会重复这些 FK。
2. **概念一致性**: 一次 Run 产生一个 AgentSession，这个 AgentSession 就是 "这一次编码会话"。新建 `CodingSession` 表会造成概念重复 (两个表都表达 "Run 下的 agent 会话")。
3. **现有功能不破坏**: `AgentSession` 的 Day11 review/rework 流程可以继续工作。新增的 coding 维度字段与现有 review 字段是互补的 (正交维度)。
4. **渐进增强**: 新增字段全部 nullable，不影响现有逻辑。`TaskWorker` 逐步填充新字段。
5. **agent-orchestrator 的先例**: agent-orchestrator 也是在同一个 Session 对象上承载 session/runtime/pr 三个维度的信息，没有为每个维度建单独的表。

### 4.2 改造方案

在现有 `AgentSession` 上新增两组字段:

**P0 组 (执行环境标识)**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `agent_type` | string(40), nullable | claude_code / codex / opencode / openai_provider / shell / simulate |
| `runtime_type` | string(40), nullable | tmux / subprocess / docker / process |
| `runtime_handle_id` | string(200), nullable | tmux session name / container ID / PID |
| `coding_status` | string(40), nullable | spawning / working / idle / needs_input / stuck / completed / failed / terminated |
| `activity_state` | string(40), nullable | active / ready / idle / waiting_input / blocked / exited |
| `branch_name` | string(200), nullable | git branch name |

**P1 组 (工作区与交付)**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `workspace_type` | string(40), nullable | worktree / clone / in_place / read_only |
| `worktree_path` | text, nullable | 隔离工作区路径 |
| `commit_sha` | string(64), nullable | 最后提交 SHA |
| `delivery_status` | string(40), nullable | none / branch_created / pr_opened / ci_passing / ci_failed / review_approved / changes_requested / merged / closed |
| `pr_url` | text, nullable | PR URL |
| `pr_number` | integer, nullable | PR 编号 |
| `ci_status` | string(40), nullable | pending / passing / failing / none |
| `review_decision` | string(40), nullable | approved / changes_requested / pending / none |

### 4.3 P0 第一阶段: 为什么只加 P0 组

- `agent_type` + `runtime_type` + `coding_status` + `activity_state`: 当前 `TaskWorker` 可以立即填充 (subprocess + openai_provider + working → completed/failed)
- `branch_name`: 当前是 null，为 P1 的 worktree 隔离做准备
- P1 组在 P0 阶段都留 null，不做任何迁移

---

## 5. 四轴生命周期模型

借鉴 agent-orchestrator 的 `CanonicalSessionLifecycle` (三元组)，设计适合 AI-Dev 的四轴模型:

```
CodingSessionLifecycle {
    session:   SessionAxis     — agent 本身的运行状态
    workspace: WorkspaceAxis   — 代码隔离环境状态
    runtime:   RuntimeAxis     — 进程/容器运行状态
    delivery:  DeliveryAxis    — 代码产出与审批状态
}
```

### 5.1 四轴关系

```
                    ┌─────────────┐
                    │   Session   │ ← agent 是否在运行、是否卡住、是否完成
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
   ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
   │  Workspace  │  │   Runtime   │  │  Delivery   │
   │ 工作区隔离   │  │ 进程/容器    │  │ 代码交付     │
   └─────────────┘  └─────────────┘  └─────────────┘

四轴独立变化，联合推导整体状态:
- runtime 死了 → session 进入 detecting
- workspace 有改动 → 可以推进 delivery
- delivery merged → session 进入 completed
```

### 5.2 四轴联合状态推导 (关键状态组合)

| session | workspace | runtime | delivery | → 推导整体状态 |
|---------|-----------|---------|----------|---------------|
| spawning | not_created | unknown | none | **spawning** |
| working | ready | alive | none | **working** |
| working | dirty | alive | none | **working** |
| working | committed | alive | branch_created | **working** |
| idle | committed | alive | pr_opened | **pr_open** |
| idle | committed | alive | ci_failed | **ci_failed** |
| idle | committed | alive | review_pending | **review_pending** |
| idle | committed | alive | changes_requested | **changes_requested** |
| idle | committed | alive | review_approved | **approved** |
| idle | committed | alive | merged | **merged** |
| stuck | — | alive | — | **stuck** |
| needs_input | — | alive | — | **needs_input** |
| completed | cleaned | exited | merged | **done** |
| failed | — | exited | — | **failed** |
| terminated | — | missing | — | **terminated** |

---

## 6. 每轴状态枚举

### 6.1 SessionAxis

```
not_started → spawning → working ⇄ idle
                          working → needs_input
                          working → stuck → working (recovery)
                          working → completed
                          working → failed
                          working → terminated
```

| 状态 | 含义 | 触发条件 |
|------|------|---------|
| `not_started` | 尚未创建 | AgentSession 创建前的瞬态 |
| `spawning` | 正在创建 | workspace 分配中 / runtime 启动中 |
| `working` | 工作中 | agent 进程运行中，activity = active |
| `idle` | 空闲 | agent 进程存活但长时间无活动 |
| `needs_input` | 需要输入 | agent 等待用户权限/澄清 |
| `stuck` | 卡住 | agent 长时间无响应或报错 |
| `completed` | 完成 | 正常结束 |
| `failed` | 失败 | 执行失败 |
| `terminated` | 已终止 | 外部终止 (kill/cleanup) |

### 6.2 WorkspaceAxis

```
not_created → creating → ready → dirty → committed → cleaned
```

| 状态 | 含义 | 触发条件 |
|------|------|---------|
| `not_created` | 未创建 | 无隔离工作区 |
| `creating` | 创建中 | git worktree add / git clone 进行中 |
| `ready` | 就绪 | 工作区干净，可开始编码 |
| `dirty` | 有改动 | 有未提交更改 |
| `committed` | 已提交 | 更改已提交 |
| `cleaned` | 已清理 | 工作区已删除 |

### 6.3 RuntimeAxis

```
unknown → spawning → alive → exited
                            → missing
                            → probe_failed
```

| 状态 | 含义 | 触发条件 |
|------|------|---------|
| `unknown` | 未知 | 尚未探测 |
| `spawning` | 启动中 | tmux new / docker run / Popen 进行中 |
| `alive` | 存活 | 进程运行中 (ps / isAlive 确认) |
| `exited` | 已退出 | 进程正常/异常退出 |
| `missing` | 丢失 | tmux session 被外部 kill / 容器被删除 |
| `probe_failed` | 探活失败 | 无法确认进程状态 (网络/权限问题) |

### 6.4 DeliveryAxis

```
none → branch_created → pr_opened → ci_pending → ci_passing → review_pending → review_approved → merged
                                       ↘ ci_failed → (fix) → pr_opened
                                       ↘ changes_requested → (rework) → pr_opened
                                       ↘ closed
```

| 状态 | 含义 | 触发条件 |
|------|------|---------|
| `none` | 无交付 | 无代码产出 |
| `branch_created` | 分支已创建 | git branch + push |
| `pr_opened` | PR 已开启 | PR 已创建 |
| `ci_pending` | CI 运行中 | CI checks 运行中 |
| `ci_passing` | CI 通过 | 所有 CI checks 通过 |
| `ci_failed` | CI 失败 | CI checks 失败 |
| `review_pending` | 等待审查 | PR 等待 review |
| `review_approved` | 审查通过 | Review approved |
| `changes_requested` | 要求修改 | Review changes requested |
| `merged` | 已合并 | PR merged |
| `closed` | 已关闭 | PR closed without merge |

---

## 7. 当前 AI-Dev 已有字段如何映射到四轴

### 7.1 SessionAxis 映射

| 来源 | 映射目标 | 推导规则 |
|------|---------|---------|
| `AgentSession.status = running` | `session_state = working` | 直接映射 |
| `AgentSession.status = review_rework` | `session_state = working` | rework 也是 working |
| `AgentSession.status = completed` | `session_state = completed` | 直接映射 |
| `AgentSession.status = failed` | `session_state = failed` | 直接映射 |
| `AgentSession.status = blocked` | `session_state = stuck` | 直接映射 |
| `TaskStatus.waiting_human` | `session_state = needs_input` | Task 需要人工介入 |
| (新字段) `coding_status` | `session_state` | 直接取值 |

### 7.2 WorkspaceAxis 映射

| 来源 | 映射目标 | 推导规则 |
|------|---------|---------|
| `ChangeSession.workspace_status = clean` | `workspace_state = ready` | 项目级映射 |
| `ChangeSession.workspace_status = dirty` | `workspace_state = dirty` | 项目级映射 |
| `RepositoryWorkspace.access_mode = read_only` | `workspace_type = read_only` | 当前永远是 read_only |
| (新字段) `workspace_type` | `workspace_state` 推导 | P1 引入 |

### 7.3 RuntimeAxis 映射

| 来源 | 映射目标 | 推导规则 |
|------|---------|---------|
| `Run.status = queued` | `runtime_state = unknown` | 尚未启动 |
| `Run.status = running` | `runtime_state = alive` | 假设在运行 (当前无探活) |
| `Run.status = succeeded` | `runtime_state = exited` | 进程已退出 |
| `Run.status = failed` | `runtime_state = exited` | 进程已退出 |
| `Run.status = cancelled` | `runtime_state = missing` | 被取消 |

### 7.4 DeliveryAxis 映射

| 来源 | 映射目标 | 推导规则 |
|------|---------|---------|
| `CommitCandidate.status = draft` | `delivery_state = none` | 草案不是真实交付 |
| `ApprovalStatus.approved` + CommitCandidate 已确认 | `delivery_state = branch_created` (潜在) | 审批通过后可推进 |
| `ApprovalStatus.changes_requested` | `delivery_state = changes_requested` | 直接映射 |
| (新字段) `delivery_status` | `delivery_state` | P1 引入 |

**关键限制**: 当前 DeliveryAxis 几乎全部映射到 `none`——因为没有 SCM 集成，没有真实的 branch/PR 创建。

---

## 8. 缺失字段、缺失服务、缺失 API 清单

### 8.1 缺失字段 (AgentSession 表)

| 字段 | P | 当前状态 |
|------|---|---------|
| `agent_type` | P0 | 缺失 |
| `runtime_type` | P0 | 缺失 |
| `runtime_handle_id` | P0 | 缺失 |
| `coding_status` | P0 | 缺失 |
| `activity_state` | P0 | 缺失 |
| `branch_name` | P0 | 缺失 |
| `workspace_type` | P1 | 缺失 |
| `worktree_path` | P1 | 缺失 |
| `commit_sha` | P1 | 缺失 |
| `delivery_status` | P1 | 缺失 |
| `pr_url` | P1 | 缺失 |
| `pr_number` | P1 | 缺失 |
| `ci_status` | P2 | 缺失 |
| `review_decision` | P2 | 缺失 |

### 8.2 缺失服务

| 服务 | P | 职责 | 参考 agent-orchestrator |
|------|---|------|------------------------|
| `AgentTypeResolver` | P0 | 根据 executor mode 推断 agent_type | `Agent.name` / `Agent.getLaunchCommand()` |
| `RuntimeTypeResolver` | P0 | 根据执行环境推断 runtime_type | `Runtime.isAlive()` |
| `SessionActivityPoller` | P1 | 定期轮询 agent 进程状态 | `LifecycleManager.determineStatus()` |
| `WorkspaceIsolationService` | P1 | 创建/销毁 git worktree per session | `Workspace.create()` / `Workspace.destroy()` |
| `SCMIntegrationService` | P2 | GitHub/GitLab API 封装 (PR/CI/review) | `SCM` interface |
| `SessionStateDeriver` | P0 | 从四轴数据推导整体状态 | `deriveLegacyStatus()` |

### 8.3 缺失 API

| API | P | 说明 |
|-----|---|------|
| `GET /agent-sessions/{id}/coding-status` | P0 | 返回 coding_status + activity_state |
| `GET /agent-sessions/{id}/lifecycle` | P0 | 返回四轴状态摘要 |
| `POST /agent-sessions/{id}/activity-probe` | P1 | 手动触发 agent 活动探测 |
| `GET /agent-sessions/{id}/workspace-status` | P1 | 返回 workspace_type + worktree_path + branch |
| `GET /agent-sessions/{id}/delivery-status` | P2 | 返回 delivery_status + pr_url + ci_status + review_decision |

---

## 9. Worktree / Branch / PR 的分阶段路线

### Phase 1 (当前 → P0 完成): 身份识别

```
当前状态: 所有 Run 在项目根目录下 subprocess 执行
         无 branch，无 worktree，无 PR

Phase 1 目标:
  AgentSession.agent_type = "openai_provider" | "shell" | "simulate"
  AgentSession.runtime_type = "subprocess"
  AgentSession.coding_status = working → completed/failed
  AgentSession.branch_name = null (保持)
```

**不改执行模型**。只是给当前的 subprocess 执行加上 "身份标签"。

### Phase 2 (P1): Per-Run 隔离

```
Phase 2 目标:
  CommitCandidate 增加 CONFIRMED 和 APPLIED 状态
  RepositoryAccessMode 增加 READ_WRITE
  用户确认 CommitCandidate → 创建 git worktree + branch
  AgentSession.workspace_type = "worktree"
  AgentSession.worktree_path = /path/to/worktree
  AgentSession.branch_name = session/{project}-{run}
  AgentSession.commit_sha = <git rev-parse HEAD>
```

**不改 TaskWorker 的同步模型**，但是增加了一个 "确认后执行" 的步骤。

### Phase 3 (P2): SCM 集成

```
Phase 3 目标:
  SCMIntegrationService 封装 GitHub/GitLab API
  git push → create PR → AgentSession.delivery_status = "pr_opened"
  轮询 CI → AgentSession.ci_status = pending/passing/failing
  轮询 review → AgentSession.review_decision = approved/changes_requested
  PR merged → AgentSession.delivery_status = "merged"
```

**引入异步轮询**: 需要 `SessionActivityPoller` 定期检查 CI/review 状态。

---

## 10. 失败回流机制设计

### 10.1 失败场景总表

| 失败场景 | 触发条件 | session 状态 | 回流路径 |
|---------|---------|-------------|---------|
| `execution_failed` | `ExecutorService.execute_task()` 返回 success=False | failed | → TaskWorker finalize → Task.status=failed → FailureReview → retry/replan |
| `verification_failed` | `VerifierService.verify_task()` 返回 success=False | failed | → Run.failure_category=verification_failed → quality_gate_passed=false → Task.failed → retry |
| `preflight_blocked` | `ChangeBatch.preflight` 检查未通过 | working (session 继续，但不能推进 delivery) | → 用户补充验收条件 → 重新预检 |
| `approval changes_requested` | `ApprovalDecision.action = request_changes` | working (需要 rework) | → rework task 自动创建 → AgentSession.status=review_rework → 回到任务队列 |
| `runtime_lost` | agent 进程意外退出 | detecting → stuck/terminated | → SessionActivityPoller 检测 → agent 是否可恢复 → 如果不可恢复则标记 terminated，创建 failure review |
| `review_comments` | PR 收到 review comments | working | → lifecyle manager 检测 → 自动或手动发送给 agent → agent 修复 → push → 重新 CI |
| `ci_failed` | CI checks 失败 | working | → lifecyle manager 检测 → 自动通知 agent → agent 修复 → push → 重新 CI |

### 10.2 失败回流流程图

```
                    ┌──────────────┐
                    │   working    │
                    └──────┬───────┘
                           │
         ┌─────────────────┼──────────────────┐
         │                 │                  │
    ┌────▼────┐      ┌─────▼──────┐    ┌──────▼──────┐
    │execute  │      │verification│    │  runtime    │
    │_failed  │      │_failed     │    │  _lost      │
    └────┬────┘      └─────┬──────┘    └──────┬──────┘
         │                 │                  │
    ┌────▼────┐      ┌─────▼──────┐    ┌──────▼──────┐
    │failed   │      │failed      │    │ detecting   │
    └────┬────┘      └─────┬──────┘    └──────┬──────┘
         │                 │                  │
    ┌────▼────┐      ┌─────▼──────┐    ┌──────▼──────┐
    │Failure  │      │Failure     │    │ stuck or    │
    │Review   │      │Review      │    │ terminated  │
    └────┬────┘      └─────┬──────┘    └──────┬──────┘
         │                 │                  │
    ┌────▼─────────────────▼──────────────────▼────┐
    │              retry / rework / replan          │
    │  (Task 重新入队或创建 rework task 或生成      │
    │   replan 建议进入工作台待确认)                │
    └──────────────────────┬───────────────────────┘
                           │
                    ┌──────▼──────┐
                    │   working   │ (重新开始)
                    └─────────────┘

对于 CI/review 失败 (P2):
    working → delivery_status=ci_failed/changes_requested
           → reaction: send-to-agent with failure details
           → agent fix → push → delivery_status=pr_opened (重新 CI)
           → (如果多次失败) → escalation → 人工通知
```

### 10.3 与现有状态机的整合

| 失败类型 | Task 状态 | Run 状态 | AgentSession 状态 | AgentSession coding_status |
|---------|----------|---------|-------------------|--------------------------|
| execution_failed | failed | failed | failed | failed |
| verification_failed | failed | failed | failed | failed |
| preflight_blocked | (不变) | (不变) | (不变) | working |
| changes_requested | pending (rework) | (新 run) | review_rework | working |
| runtime_lost | running | running | (不变) | detecting → stuck/terminated |
| review_comments | (不变) | (不变) | (不变) | working |
| ci_failed | (不变) | (不变) | (不变) | working |

**关键设计原则**: 失败不是 AgentSession 的终态——`failed` 和 `terminated` 是 session 的终态。`detecting` 是临时状态，允许恢复到 `working`。

---

## 11. 第一阶段最小落地范围

### 11.1 范围定义

**只在后端数据模型层做扩展，不动执行逻辑。**

### 11.2 具体改造项

#### A. `app/domain/agent_session.py` — 新增枚举 + 扩展模型

```python
# 新增枚举类 (6个)
class AgentType(StrEnum):
    CLAUDE_CODE = "claude_code"
    CODEX = "codex"
    OPENCODE = "opencode"
    OPENAI_PROVIDER = "openai_provider"
    SHELL = "shell"
    SIMULATE = "simulate"

class RuntimeType(StrEnum):
    TMUX = "tmux"
    SUBPROCESS = "subprocess"
    DOCKER = "docker"
    PROCESS = "process"

class CodingSessionStatus(StrEnum):
    SPAWNING = "spawning"
    WORKING = "working"
    IDLE = "idle"
    NEEDS_INPUT = "needs_input"
    STUCK = "stuck"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"

class CodingSessionActivityState(StrEnum):
    ACTIVE = "active"
    READY = "ready"
    IDLE = "idle"
    WAITING_INPUT = "waiting_input"
    BLOCKED = "blocked"
    EXITED = "exited"

class WorkspaceType(StrEnum):
    WORKTREE = "worktree"
    CLONE = "clone"
    IN_PLACE = "in_place"
    READ_ONLY = "read_only"

class DeliveryStatus(StrEnum):
    NONE = "none"
    BRANCH_CREATED = "branch_created"
    PR_OPENED = "pr_opened"
    CI_PENDING = "ci_pending"
    CI_PASSING = "ci_passing"
    CI_FAILED = "ci_failed"
    REVIEW_PENDING = "review_pending"
    REVIEW_APPROVED = "review_approved"
    CHANGES_REQUESTED = "changes_requested"
    MERGED = "merged"
    CLOSED = "closed"

# 扩展 AgentSession 类 (在现有字段后追加 6 个 P0 字段)
class AgentSession(DomainModel):
    # ... 现有字段保持不变 ...

    # P0 新增 (全部 nullable)
    agent_type: AgentType | None = None
    runtime_type: RuntimeType | None = None
    runtime_handle_id: str | None = Field(default=None, max_length=200)
    coding_status: CodingSessionStatus | None = None
    activity_state: CodingSessionActivityState | None = None
    branch_name: str | None = Field(default=None, max_length=200)
```

#### B. `app/core/db_tables.py` — AgentSessionTable 新增 6 列

```python
class AgentSessionTable(ORMBase):
    # ... 现有列 ...

    agent_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    runtime_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    runtime_handle_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    coding_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    activity_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    branch_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
```

#### C. `app/workers/task_worker.py` — TaskWorker 填充新字段

在 `start_session` 和 `record_execution_outcome` / `finalize_session` 调用处填充:

```python
# start_session 时 (约第 653 行)
agent_session = self.agent_conversation_service.start_session(
    ...
    agent_type="openai_provider",   # 当前默认
    runtime_type="subprocess",       # 当前默认
    coding_status="working",
)

# finalize_session 时 (约第 779 行)
agent_session = self.agent_conversation_service.finalize_session(
    ...
    coding_status="completed" if run.status == RunStatus.SUCCEEDED else "failed",
    activity_state="exited",
)
```

#### D. `WorkerRunResult` 透传新字段 (已部分支持 agent_session_* 字段，追加)

#### E. API 响应更新

`AgentSessionResponse` (在 `agent_threads.py`) 增加新字段:

```python
class AgentSessionResponse(BaseModel):
    # ... 现有字段 ...
    agent_type: str | None = None
    runtime_type: str | None = None
    runtime_handle_id: str | None = None
    coding_status: str | None = None
    activity_state: str | None = None
    branch_name: str | None = None
```

### 11.3 第一阶段不做什么

- 不改 `ExecutorService.execute_task()` — 不改执行逻辑
- 不改 `TaskWorker.run_once()` 的控制流 — 不改同步模型
- 不创建 git worktree — workspace_type 保持 null
- 不创建 git branch — branch_name 保持 null
- 不引入 SCM 集成 — delivery_status 保持 null
- 不改前端任何文件
- 不新增 API endpoint — 只在现有 response 中透传
- 不新增数据库表 — 只扩展现有表加 column
- 不运行 smoke test — 推迟到 Phase 1.5
- 不引入 agent-orchestrator 代码

### 11.4 验收标准

1. `AgentSession` 创建时 `agent_type = "openai_provider"`, `runtime_type = "subprocess"`, `coding_status = "working"`
2. `AgentSession` 完成时 `coding_status = "completed"` 或 `"failed"`, `activity_state = "exited"`
3. 新枚举字段序列化正常
4. 现有 48 个后端测试继续通过 (新字段 nullable)
5. 新字段在 API response 中可见

---

## 12. 明确不建议现在做的

| 不建议做的事 | 原因 |
|-------------|------|
| **插件市场** | 当前不需要完整插件系统。只需在 AgentSession 上增加字段，不需要插件注册/发现/加载机制 |
| **前端设计系统** | 本次只做后端数据模型层。P1/P2 的前端可视化后续再设计 |
| **自动 PR** | `SCM.createPR()` 在没有人工审批前不能自动执行。CommitCandidate 的 confirmed→applied 流程需要用户确认 |
| **自动 merge** | 高风险动作，必须走审批→放行→确认流程 |
| **大规模重构 Task/Run/Worker** | TaskWorker 的同步执行模型在 Phase 1 不变 |
| **新建 CodingSession 表** | 在现有 AgentSession 上扩展字段即可，不建新表 |
| **Real provider 运行** | 当前所有字段基于 simulate 模式填充即可。真实 provider 运行是后续阶段的验收要求，不是本设计基线的前提 |
| **把 AI Project Director 总闭环标记为 Pass** | 本设计基线只建立了 CodingSession 生命周期模型。总闭环的 Pass 需要 real provider evidence + SCM 集成 + 真实 delivery 闭环。当前仍为 Partial |

---

## 总结

### 当前已有能力

| 能力 | 状态 | 证据 |
|------|------|------|
| Project → Task → Run → AgentSession 链路 | ✅ Runtime Pass | CL-07, CL-08, CL-09 |
| TaskWorker 同步执行 (subprocess + simulate) | ✅ Runtime Pass | CL-08, CL-09 |
| Run 日志 + 摘要 + token/cost | ✅ Runtime Pass | CL-09, CL-10 |
| 交付物 + 审批 | ✅ Runtime Pass | CL-13, CL-14 |
| 失败处理 (retry/rework/human) | ✅ Runtime Pass | CL-11 |
| 仓库绑定 + 快照 + 变更链路 | ✅ 后端就绪，前端部分 | CL-12 |
| Agent 角色 + Skill 编队 | ✅ Runtime Pass | CL-05, CL-06 |

### 关键缺口

| 缺口 | 严重程度 | 本设计基线是否覆盖 |
|------|---------|------------------|
| AgentSession 不是 CodingSession | P0 | ✅ 四轴模型设计完成 |
| 无 agent_type / runtime_type / workspace_type | P0 | ✅ P0 字段枚举设计完成 |
| 无 worktree 隔离 | P1 | ✅ 分阶段路线设计完成 |
| 无 git branch per session | P1 | ✅ 分阶段路线设计完成 |
| 无 SCM 集成 (PR/CI/review) | P2 | ✅ DeliveryAxis 设计完成 |
| 无 coding session 状态推导 | P0 | ✅ 四轴联合推导表设计完成 |
| 无失败回流机制 | P1 | ✅ 7 种失败回流路径设计完成 |

### 第一阶段建议交给 Codex 的最小代码任务

**任务: AgentSession 模型扩展 + 字段填充**

```
范围:
  - app/domain/agent_session.py: 新增 6 个枚举 + 扩展 AgentSession 类
  - app/core/db_tables.py: AgentSessionTable 新增 6 列 (nullable)
  - app/workers/task_worker.py: TaskWorker 填充新字段
  - app/api/routes/agent_threads.py: AgentSessionResponse 新增 6 字段
  - tests/: 验证新字段的创建+更新+序列化

边界: 不改执行模型, 不改前端, 不新增 API endpoint, 不新建表
验收: pytest 全部通过
```

### Gate 结论

**设计基线完成，不是运行闭环 Pass。**

本设计基线:
- 完成了 AI-Dev 当前链路的完整审计
- 明确了 "AgentSession 不是 CodingSession" 的根因
- 设计了四轴生命周期模型及其与现有状态机的推导关系
- 定义了 P0/P1/P2 分阶段路线
- 定义了 7 种失败回流机制
- 明确了第一阶段最小可落地范围 (6 个 model 字段 + 填充逻辑)
- 不建表、不加 API、不改执行模型

**AI Project Director 总闭环: 仍为 Partial** — 本设计基线解决了 "CodingSession 概念缺口" 的设计问题，但尚未实现。总闭环的 Pass 需要 P0 代码实现 + 真实 provider evidence + P1/P2 实现。
