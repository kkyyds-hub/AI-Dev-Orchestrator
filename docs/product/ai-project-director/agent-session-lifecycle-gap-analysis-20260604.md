# AI 主管 Agent Session 闭环设计审计

> **文档类型**: 架构审计 / gap analysis / 设计建议
> **生成日期**: 2026-06-04
> **基准 commit**: `c6bef1d` (Align project director execution claim terminology)
> **参考项目**: agent-orchestrator (https://github.com/anthropics/agent-orchestrator)
> **边界**: 只分析和设计，不改代码，不改数据库，不启动服务
> **状态**: 完成

---

## 目录

1. [当前真实链路](#1-当前真实链路-project--task--run--approval--repository-draft)
2. [AgentSession / CodingSession 中间层缺口](#2-agentsession--codingsession-中间层缺口)
3. [Worker 执行表达能力审计](#3-worker-执行表达能力审计)
4. [为何停留在 commit candidate draft](#4-为何停留在-commit-candidate-draft)
5. [AgentSession 数据模型设计](#5-agentsession-数据模型设计)
6. [四轴生命周期设计](#6-四轴生命周期设计)
7. [与现有状态机的推导关系](#7-与现有状态机的推导关系)
8. [P0 / P1 / P2 实施路线](#8-p0--p1--p2-实施路线)
9. [第一阶段最小可落地改造范围](#9-第一阶段最小可落地改造范围)
10. [附录：agent-orchestrator 参考机制摘要](#10-附录agent-orchestrator-参考机制摘要)

---

## 1. 当前真实链路: Project → Task → Run → Approval → Repository draft

### 1.1 链路全景

当前 AI-Dev-Orchestrator 的完整数据流如下（以一次 AI Project Director 驱动的执行链路为例）：

```
ProjectDirectorSession (目标澄清)
    → ProjectDirectorPlanVersion (计划草案)
    → ProjectDirectorTaskCreationRecord (任务创建记录)
    → Project (正式项目, stage=intake→planning→execution→verification→delivery)
        → Task (任务队列, status=pending→running→completed/failed)
            → Run (执行记录, status=queued→running→succeeded/failed)
                → AgentSession (Day11 agent-thread, 1 per Run)
                → Deliverable + DeliverableVersion (自动生成交付物快照)
                    → ApprovalRequest + ApprovalDecision (审批)
        → RepositoryWorkspace (仓库绑定, access_mode=read_only)
            → RepositorySnapshot (仓库快照扫描)
            → ChangeSession (分支/工作区状态)
                → ChangePlan (变更方案)
                → ChangeBatch (变更批次, status=preparing→preflighting→...)
                    → CommitCandidate (提交草案, status=draft only)
                    → VerificationRun (验证执行)
        → ProjectAISummary (项目级 AI 摘要)
```

### 1.2 关键模块关系

| 模块 | 表 | 核心状态 | 与上层的 FK |
|------|-----|---------|------------|
| ProjectDirectorSession | `project_director_sessions` | draft→confirmed | project_id (nullable) |
| ProjectDirectorPlanVersion | `project_director_plan_versions` | draft→approved/rejected | session_id, project_id |
| Project | `projects` | active/on_hold/completed/archived + stage (intake→...→delivery) | — |
| Task | `tasks` | pending→running→paused→waiting_human→completed/failed/blocked | project_id |
| Run | `runs` | queued→running→succeeded/failed/cancelled | task_id |
| AgentSession | `agent_sessions` | running→review_rework→completed/failed/blocked | project_id, task_id, run_id |
| ApprovalRequest | `approval_requests` | pending_approval→approved/rejected/changes_requested | project_id, deliverable_id, deliverable_version_id |
| RepositoryWorkspace | `repository_workspaces` | read_only | project_id (unique) |
| ChangeSession | `change_sessions` | clean/dirty + ready/blocked | project_id, repository_workspace_id |
| ChangeBatch | `change_batches` | preparing→... | project_id, repository_workspace_id |
| CommitCandidate | `commit_candidates` | **draft only** | project_id, change_batch_id |

### 1.3 ProjectStage 状态机

```
intake → planning → execution → verification → delivery
```

每次阶段推进由 `ProjectStageGuard` 守卫评估。

### 1.4 TaskStatus 状态机

```
pending → running → completed
                  → failed
                  → paused → running
                  → waiting_human → running
                  → blocked
```

### 1.5 RunStatus 状态机

```
queued → running → succeeded
                 → failed
                 → cancelled
```

### 1.6 关键观察

1. **TaskWorker 是单体同步执行器**: `TaskWorker.run_once()` 在一个 DB session 中完成 "claim → execute → verify → finalize → auto-deliverable → auto-approval" 的全流程
2. **Execution 是同步调用**: `ExecutorService.execute_task()` 在当前进程中调用 `subprocess` 或 `OpenAIProviderExecutorService`，不是异步 dispatch
3. **AgentSession 是事后记录**: 在 `TaskWorker` 的第 648-666 行创建，只在 run 开始前创建一条记录，结束时更新状态。不承载真实 agent 交互
4. **Repository 链路是旁路**: RepositoryWorkspace → ChangeSession → ChangePlan → ChangeBatch → CommitCandidate 独立于 Task/Run/Approval 主链路运行，仅通过 project_id 关联

---

## 2. AgentSession / CodingSession 中间层缺口

### 2.1 当前已有

| 概念 | 表 | 职责 | 缺口 |
|------|-----|------|------|
| **AgentSession** | `agent_sessions` | Day11 agent-thread 会话记录 | 仅记录生命周期状态 (running/review_rework/completed/failed)，**不承载真实 agent 进程交互** |
| **AgentMessage** | `agent_messages` | Day11 agent-thread 时间线 | 仅记录事件摘要 (event_type, content_summary)，**不是真实 agent 对话 transcript** |
| **ChangeSession** | `change_sessions` | Day03 分支/工作区状态快照 | 记录 git branch/commit/dirty files，**不关联到执行会话** |
| **ProjectDirectorSession** | `project_director_sessions` | 目标澄清会话 | 仅用于 intake→planning 阶段的目标输入与澄清，**不扩展到 execution 阶段** |

### 2.2 缺失的概念: CodingSession

**agent-orchestrator** 的核心抽象是一个 **CodingSession**——它同时描述了：

1. **谁在执行**: agent_type (claude-code, codex, opencode, etc.)
2. **在哪执行**: workspace_type (worktree, clone) + worktree_path
3. **怎么运行**: runtime_type (tmux, docker, process) + runtime_handle
4. **产出什么**: branch_name + pr_url + pr_number
5. **质量如何**: ci_status + review_status
6. **当前活动**: activity_state (active, idle, waiting_input, blocked, exited)

当前 AI-Dev-Orchestrator 中，这些信息**分散在至少 5 个不同的表中**：

| 信息 | 当前存储位置 | 问题 |
|------|-------------|------|
| agent_type | 无。`Run.provider_key` 记录了 provider (openai)，但不记录 agent 类型 | 无法区分 claude-code vs codex vs opencode |
| runtime_type | 无 | 无法区分 tmux vs subprocess vs docker |
| workspace_type | `RepositoryWorkspace.access_mode` 永远是 read_only | 不区分 worktree vs clone vs in-place |
| worktree_path | `RepositoryWorkspace.root_path` | 这是项目级绑定路径，不是 per-run workspace |
| branch_name | `ChangeSession.current_branch` | 是项目级状态快照，不绑定到 Run |
| pr_url | 无此字段 | 完全没有 PR 概念 |
| ci_status | 无此字段 | 完全没有 CI 概念 |
| review_status | `AgentSession.review_status` (Day11) | 仅指内部 review/rework 流程，不是 GitHub PR review |

### 2.3 根因

**AI-Dev-Orchestrator 当前是一个"任务调度器 + 同步执行器"，不是"agent session 编排器"**。

- `TaskWorker` 调用 `ExecutorService.execute_task()` 在一个 DB session 内同步完成执行
- 没有"启动 agent 进程 → 轮询状态 → 检测完成 → 收尾"的异步生命周期
- 没有 workspace 隔离机制（每个 Run 不在独立 worktree/分支中执行）
- 没有 SCM 集成（PR/CI/review 完全不存在）

**核心缺口**: 缺少一个位于 `Run` 之下、`AgentSession` 之上的 **CodingSession** 抽象——它封装了一次真实的 agent 编码会话的完整生命周期。

---

## 3. Worker 执行表达能力审计

### 3.1 当前 `Run` 模型已记录的字段

参考 `Run` 领域模型 (`app/domain/run.py`) 和 `RunTable` (`app/core/db_tables.py`):

| 字段 | 当前支持 | 说明 |
|------|---------|------|
| `provider_key` | ✅ | 记录 AI provider (如 "openai") |
| `model_name` | ✅ | 记录模型名称 |
| `dispatch_status` | ✅ | string(100)，当前用途不明确 |
| `owner_role_code` | ✅ | 执行此 Run 的角色 |
| `verification_mode` | ✅ | 验证模式 |
| `log_path` | ✅ | 日志文件路径 |
| `total_tokens / prompt_tokens / completion_tokens` | ✅ | Token 统计 |
| `estimated_cost` | ✅ | 成本估算 |
| `cache_read_tokens / cache_write_tokens / cache_hit` | ✅ | 缓存指标 |

### 3.2 当前 `Run` 模型明确缺失的字段

| 缺失字段 | 推荐字段名 | 类型 | P |
|---------|-----------|------|---|
| **agent_type** | `agent_type` | string(40) | P0 |
| **runtime_type** | `runtime_type` | string(40) | P0 |
| **workspace_type** | `workspace_type` | string(40) | P1 |
| **worktree_path** | `worktree_path` | text | P1 |
| **branch_name** | `branch_name` | string(200) | P0 |
| **pr_url** | `pr_url` | text | P1 |
| **pr_number** | `pr_number` | integer | P1 |
| **ci_status** | `ci_status` | string(40) | P2 |
| **review_status** | `review_status` | string(40) | P2 |
| **commit_sha** | `commit_sha` | string(64) | P1 |
| **runtime_handle_id** | `runtime_handle_id` | string(200) | P0 |

### 3.3 为什么 `AgentSession` 不能填补这个缺口

`AgentSession` (Day11) 的定位是"review/rework 生命周期管理"：

```python
class AgentSessionStatus(StrEnum):
    RUNNING = "running"
    REVIEW_REWORK = "review_rework"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
```

它关注的是**内部审查流程**（谁 review、是否需要 rework），不关注**外部执行环境**（在哪台机器上运行、用什么 runtime、在哪个 worktree 里编码）。

**结论**: `AgentSession` 的位置在 `Run` 之下是正确的，但它目前过于"轻量"——它缺少编码会话的关键上下文。

---

## 4. 为何停留在 commit candidate draft

### 4.1 CommitCandidate 模型只有 DRAFT 状态

参考 `CommitCandidateStatus` (`app/domain/commit_candidate.py`):

```python
class CommitCandidateStatus(StrEnum):
    DRAFT = "draft"  # 只有一个状态
```

`CommitCandidate` 的设计文档明确标注为 **"review-only drafts"**——它不触发真实 git 提交、不创建 branch、不创建 PR。

### 4.2 根因分析

整个 repository 链路 (`RepositoryWorkspace → ChangeSession → ChangePlan → ChangeBatch → CommitCandidate`) 停留在 draft 阶段的原因有三：

#### 原因 1: 设计哲学 — "AI 建议，人类决策"

从 `ProjectDirectorPlanVersion` 到 `AgentTeamConfig` 到 `SkillBindingConfig` 到 `RepositoryBindingConfig` 到 `CommitCandidate`，整个 AI Project Director 的设计哲学是 **"AI 起草，老板审核，确认后才执行"**。

- `PlanVersionStatus`: draft → approved/rejected
- `AgentTeamConfigStatus`: pending_confirmation → confirmed/rejected
- `SkillBindingConfigStatus`: pending_confirmation → confirmed/rejected
- `RepositoryBindingConfigStatus`: pending_confirmation → confirmed/rejected
- `CommitCandidateStatus`: **draft only** ← 缺失 "confirmed" 和 "applied" 状态

#### 原因 2: RepositoryWorkspace.access_mode 永远是 read_only

```python
class RepositoryAccessMode(StrEnum):
    READ_ONLY = "read_only"  # 只有一个值
```

系统**从未设计过 write 模式**。`LocalGitWriteService` 存在但需要显式调用且受多层 guard 保护（workspace binding → change batch → preflight → release gate → commit candidate）。

#### 原因 3: 没有 SCM 集成层

对比 agent-orchestrator 的 `SCM` 插件接口：

```typescript
interface SCM {
    detectPR(session, project): Promise<PRInfo | null>;
    getPRState(pr): Promise<PRState>;
    getCIChecks(pr): Promise<CICheck[]>;
    getReviews(pr): Promise<Review[]>;
    mergePR(pr, method?): Promise<void>;
    closePR(pr): Promise<void>;
    // ...
}
```

AI-Dev-Orchestrator **完全没有 SCM 集成层**。没有 `detectPR`、`getCIStatus`、`getReviewStatus` 等能力，因此 `CommitCandidate` 自然无法从 draft 推进到 "branch created → PR opened → CI running → review → merge" 这一完整流程。

### 4.3 与 agent-orchestrator 的对比

| 维度 | agent-orchestrator | AI-Dev-Orchestrator |
|------|-------------------|---------------------|
| PR 创建 | `SCM.detectPR()` 自动检测 / agent 通过 git/gh 创建 | 无 |
| CI 监控 | `SCM.getCIChecks()` + `CIFailureSummary` | 无 |
| Review 监控 | `SCM.getReviews()` + `ReviewDecision` | `AgentSessionReviewStatus` (内部 review，不是 PR review) |
| 合并 | `SCM.mergePR()` + auto-merge reaction | 无 |
| 分支管理 | `Workspace.create()` per session + branch name | `ChangeSession.current_branch` (项目级，不是 per-run) |
| 代码产出 | 真实的 branch + PR + merge | CommitCandidate draft (JSON 草案) |

---

## 5. AgentSession 数据模型设计

### 5.1 设计原则

1. **不推翻现有模型**: 在现有 `Task`/`Run`/`AgentSession` 之上增加，不是替换
2. **参考 agent-orchestrator 的三元组抽象**: Session / Runtime / PR 三元组是 agent-orchestrator 最成功的设计
3. **适合本项目**: 保留 Project → Task → Run 调度层，在 Run 之下增加真正承载 agent 执行的会话层
4. **渐进增强**: 新字段为可选 (nullable)，不破坏现有数据库

### 5.2 建议的 AgentSession 扩展模型

当前 `AgentSession` (Day11) 已经是 Run 之下的子记录。建议将其扩展为完整的 **CodingSession**:

```python
# ---- 新增枚举 ----

class AgentType(StrEnum):
    """可插拔的 AI coding agent 类型"""
    CLAUDE_CODE = "claude_code"       # Claude Code CLI
    CODEX = "codex"                   # OpenAI Codex CLI
    OPENCODE = "opencode"             # OpenCode
    OPENAI_PROVIDER = "openai_provider"  # 当前已有的 OpenAI API 直接调用
    SHELL = "shell"                   # 当前已有的 shell 执行
    SIMULATE = "simulate"             # 当前已有的模拟模式


class RuntimeType(StrEnum):
    """Agent 运行环境类型"""
    TMUX = "tmux"                     # tmux session
    SUBPROCESS = "subprocess"         # 当前已有的 subprocess
    DOCKER = "docker"
    PROCESS = "process"


class WorkspaceType(StrEnum):
    """代码隔离策略"""
    WORKTREE = "worktree"             # git worktree (per session)
    CLONE = "clone"                   # 独立 clone
    IN_PLACE = "in_place"             # 当前已有的项目路径直接操作
    READ_ONLY = "read_only"           # 只读引用


class CodingSessionStatus(StrEnum):
    """编码会话生命周期状态 (agent-orchestrator 风格)"""
    SPAWNING = "spawning"             # 正在创建
    WORKING = "working"               # agent 活跃工作中
    IDLE = "idle"                     # agent 空闲 (等待下一个任务)
    NEEDS_INPUT = "needs_input"       # agent 需要人工输入 (权限/澄清)
    STUCK = "stuck"                   # agent 卡住了
    COMPLETED = "completed"           # 正常完成
    FAILED = "failed"                 # 执行失败
    TERMINATED = "terminated"         # 被终止


class CodingSessionActivityState(StrEnum):
    """Agent 活动检测状态 (agent-orchestrator 风格)"""
    ACTIVE = "active"                 # 正在思考/编码
    READY = "ready"                   # 完成任务，等待下一个输入
    IDLE = "idle"                     # 长时间未活动
    WAITING_INPUT = "waiting_input"   # 等待权限/澄清
    BLOCKED = "blocked"               # 遇到错误
    EXITED = "exited"                 # 进程已退出


class DeliveryStatus(StrEnum):
    """代码交付状态"""
    NONE = "none"                     # 无交付
    BRANCH_CREATED = "branch_created" # 分支已创建
    PR_OPENED = "pr_opened"          # PR 已开启
    CI_PASSING = "ci_passing"        # CI 通过
    CI_FAILED = "ci_failed"          # CI 失败
    REVIEW_APPROVED = "review_approved" # Review 通过
    CHANGES_REQUESTED = "changes_requested" # Review 要求修改
    MERGED = "merged"                 # 已合并
    CLOSED = "closed"                 # PR 已关闭 (未合并)
```

### 5.3 建议的 AgentSession 扩展字段 (加在现有 `AgentSession` 模型上)

```python
class AgentSession(DomainModel):
    """扩展后的 Agent 编码会话 — 在现有 Day11 AgentSession 基础上增强"""

    # === 现有字段 (保持不变) ===
    id: UUID
    project_id: UUID
    task_id: UUID
    run_id: UUID
    status: AgentSessionStatus          # running/review_rework/completed/failed/blocked
    review_status: AgentSessionReviewStatus
    current_phase: AgentSessionPhase
    owner_role_code: ProjectRoleCode | None
    context_checkpoint_id: str | None
    context_rehydrated: bool
    latest_intervention_type: str | None
    latest_note_event_type: str | None
    summary: str | None
    started_at: datetime
    updated_at: datetime
    finished_at: datetime | None

    # === P0 新增: 执行环境标识 ===
    agent_type: AgentType | None = None          # claude_code / openai_provider / shell / simulate
    runtime_type: RuntimeType | None = None       # tmux / subprocess / docker / process
    runtime_handle_id: str | None = None          # tmux session name / container ID / PID
    coding_status: CodingSessionStatus | None = None  # spawning → working → idle → completed/failed
    activity_state: CodingSessionActivityState | None = None  # agent 活动检测

    # === P1 新增: Worktree / Branch / PR ===
    workspace_type: WorkspaceType | None = None   # worktree / clone / in_place / read_only
    worktree_path: str | None = None              # 隔离工作区路径
    branch_name: str | None = None                # git 分支名
    commit_sha: str | None = None                 # 最后提交 SHA

    # === P2 新增: Delivery 状态 ===
    delivery_status: DeliveryStatus | None = None # none → branch_created → pr_opened → merged
    pr_url: str | None = None                     # PR URL
    pr_number: int | None = None                  # PR 编号
    ci_status: str | None = None                  # CI 状态: pending/passing/failing/none
    review_decision: str | None = None            # Review: approved/changes_requested/pending/none
```

### 5.4 为什么不新建独立表

1. `AgentSession` 已经建立了 `project_id → task_id → run_id` 的 FK 链
2. 现有 `agent_sessions` 表已经承载了 Day11 的 review/rework 流程
3. 新增一个 `CodingSession` 表会造成概念重复（两个表都表达 "一次 Run 下的 agent 会话"）
4. 扩展字段全部为 `nullable`，不影响现有逻辑

### 5.5 与 agent-orchestrator Session 模型的映射

| agent-orchestrator | AI-Dev-Orchestrator (建议) |
|-------------------|---------------------------|
| `Session.id` | `AgentSession.id` |
| `Session.projectId` | `AgentSession.project_id` |
| `Session.status` | `AgentSession.coding_status` |
| `Session.activity` | `AgentSession.activity_state` |
| `Session.branch` | `AgentSession.branch_name` |
| `Session.workspacePath` | `AgentSession.worktree_path` |
| `Session.runtimeHandle` | `AgentSession.runtime_handle_id` |
| `Session.pr.url` | `AgentSession.pr_url` |
| `Session.pr.number` | `AgentSession.pr_number` |
| `Session.lifecycle` | `AgentSession` 自身状态机 (coding_status + delivery_status) |
| `CanonicalSessionLifecycle.runtime` | `AgentSession.runtime_type + runtime_handle_id + coding_status` |
| `CanonicalSessionLifecycle.pr` | `AgentSession.delivery_status + pr_url + pr_number + ci_status + review_decision` |

---

## 6. 四轴生命周期设计

参考 agent-orchestrator 的 `CanonicalSessionLifecycle` (version 2) 三元组 (session / pr / runtime)，设计适合本项目的四轴生命周期：

```
CanonicalSessionLifecycle {
    session:   SessionAxis     — agent 本身的运行状态
    workspace: WorkspaceAxis   — 代码隔离环境
    runtime:   RuntimeAxis     — 进程/容器运行环境
    delivery:  DeliveryAxis    — 代码产出与审批状态
}
```

### 6.1 Axis 1: Session (会话轴)

agent 自身的运行生命周期。

```
                ┌──────────┐
                │ spawning │  ← 创建中 (分配 workspace、启动 runtime)
                └────┬─────┘
                     │
                ┌────▼─────┐
         ┌──────│ working  │──────┐
         │      └────┬─────┘      │
         │           │             │
    ┌────▼───┐  ┌───▼────┐   ┌───▼──────────┐
    │  idle  │  │ stuck  │   │ needs_input   │
    └────────┘  └───┬────┘   └───┬───────────┘
                    │             │
                    └──────┬──────┘
                           │ (recovery / intervention)
                           ▼
                    ┌──────────┐
                    │ working  │ ← 恢复工作
                    └────┬─────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
         ┌────▼───┐ ┌───▼────┐ ┌──▼─────────┐
         │completed│ │ failed │ │ terminated │
         └─────────┘ └────────┘ └────────────┘
```

**状态与现有 `AgentSessionStatus` 的映射**:
- `spawning` → 新增
- `working` → `RUNNING`
- `idle` → 新增
- `stuck` → 新增
- `needs_input` → 新增
- `completed` → `COMPLETED`
- `failed` → `FAILED`
- `terminated` → 新增 (区别于 failed——terminated 是外部终止，failed 是内部失败)

### 6.2 Axis 2: Workspace (工作区轴)

代码隔离环境的生命周期。

```
    ┌──────────────┐
    │ not_created  │  ← 未创建隔离工作区
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │  creating    │  ← git worktree add / git clone
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │    ready     │  ← 工作区就绪，agent 可开始编码
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │    dirty     │  ← 有未提交更改
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │  committed   │  ← 更改已提交 (可在此创建 PR)
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │   cleaned    │  ← 工作区已清理 (合并后删除 worktree)
    └──────────────┘
```

**状态与现有 `ChangeSessionWorkspaceStatus` 的映射**:
- `not_created` → 新增
- `creating` → 新增
- `ready` → `CLEAN`
- `dirty` → `DIRTY`
- `committed` → 新增
- `cleaned` → 新增

### 6.3 Axis 3: Runtime (运行时轴)

agent 进程/容器的运行状态。

```
    ┌──────────────┐
    │   unknown    │  ← 尚未探测
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │   spawning   │  ← tmux new / docker run / Popen
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │    alive     │  ← 进程运行中
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │    exited    │  ← 进程已退出
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │   missing    │  ← runtime 环境丢失 (tmux session 被 kill)
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │ probe_failed │  ← 探活失败 (网络/权限问题)
    └──────────────┘
```

**状态与现有模型的关系**:
- 这是**全新的轴**。当前 AI-Dev-Orchestrator 没有进程级探活机制
- `RunStatus.RUNNING` 只表达 "数据库记录标记为运行中"，不表达 "agent 进程仍在运行"
- 对 `subprocess` 模式，runtime 生命周期与 Run 同步
- 对 `tmux` 模式，runtime 生命周期独立于 Run（一个 tmux session 可以服务多个 Run）

### 6.4 Axis 4: Delivery (交付轴)

代码产出从分支到 PR 到合并的完整生命周期。

```
    ┌──────────────┐
    │     none     │  ← 无代码产出
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │branch_created│  ← git branch + push
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │   pr_opened  │  ← PR 已创建
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │  ci_pending  │  ← CI 运行中
    └──┬───┬───┬───┘
       │   │   │
  ┌────▼┐ ┌▼───┐ ┌▼──────────────┐
  │ci_  │ │ci_ │ │review_pending │
  │pass │ │fail│ └───────┬───────┘
  └──┬──┘ └┬───┘         │
     │     │       ┌──────┼──────┐
     │     │  ┌────▼──┐ ┌▼──────────────┐
     │     │  │review │ │changes_requested│
     │     │  │approved│ └───────┬───────┘
     │     │  └───┬───┘         │
     │     │      │             │ (rework → pr_opened)
     │     │      │      ┌──────▼──────┐
     │     │      │      │   rework    │
     │     │      │      └──────┬──────┘
     │     │      │             │
     └─────┴──────┴─────────────┘
                    │
             ┌──────▼──────┐
             │   merged    │
             └──────┬──────┘
                    │
             ┌──────▼──────┐
             │   closed    │  ← PR 关闭未合并 (alternative ending)
             └─────────────┘
```

**状态与现有模型的映射**:
- 这是**全新的轴**。当前 AI-Dev-Orchestrator 没有任何 delivery 状态追踪
- `none` → 当前默认状态
- `branch_created` → 在 `LocalGitWriteService` 执行 apply-local + git-commit 后可达 (当前需要显式触发)
- `pr_opened` → 需要 SCM 集成
- `ci_*` / `review_*` / `merged` → 需要 SCM 集成

### 6.5 四轴联合状态表

借鉴 agent-orchestrator `deriveLegacyStatus()` 的设计，从四轴的联合状态推导整体状态：

| session | workspace | runtime | delivery | → 整体状态 |
|---------|-----------|---------|----------|-----------|
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

## 7. 与现有状态机的推导关系

### 7.1 关键设计原则

**不推翻现有状态机，而是在现有状态机之上增加推导层**。

现有状态机:
- `TaskStatus`: pending/running/paused/waiting_human/completed/failed/blocked
- `RunStatus`: queued/running/succeeded/failed/cancelled
- `ProjectStage`: intake/planning/execution/verification/delivery
- `ApprovalStatus`: pending_approval/approved/rejected/changes_requested

新增的四轴状态**推导自**但不**替代**这些现有状态。

### 7.2 推导规则

#### TaskStatus → SessionAxis

```
TaskStatus.RUNNING + AgentSession.agent_type IS NOT NULL
    → SessionAxis.working

TaskStatus.RUNNING + AgentSession IS NULL
    → SessionAxis 未激活 (CodingSession 尚未创建)

TaskStatus.COMPLETED + AgentSession.status = COMPLETED
    → SessionAxis.completed

TaskStatus.FAILED + AgentSession.status = FAILED
    → SessionAxis.failed

TaskStatus.WAITING_HUMAN
    → SessionAxis.needs_input

TaskStatus.BLOCKED
    → SessionAxis.stuck
```

#### RunStatus → RuntimeAxis

```
RunStatus.QUEUED
    → RuntimeAxis.unknown

RunStatus.RUNNING + AgentSession.runtime_handle_id IS NOT NULL
    → RuntimeAxis.alive (需探活确认)

RunStatus.SUCCEEDED + AgentSession.runtime_handle_id IS NULL
    → RuntimeAxis.exited

RunStatus.CANCELLED
    → RuntimeAxis.missing (如果是 tmux 被 kill)
```

#### ProjectStage → DeliveryAxis

```
ProjectStage.EXECUTION + CommitCandidate.status = DRAFT
    → DeliveryAxis.none

ProjectStage.EXECUTION + ChangeSession.workspace_status = DIRTY
    → DeliveryAxis.none (有更改但未提交)

ProjectStage.VERIFICATION + ChangeBatch.preflight = READY
    → DeliveryAxis 可能推进到 branch_created

ProjectStage.DELIVERY + ApprovalStatus.APPROVED
    → DeliveryAxis 可能推进到 pr_opened / merged
```

#### ApprovalStatus → DeliveryAxis

```
ApprovalStatus.PENDING_APPROVAL
    → DeliveryAxis 保持在当前状态 (不推进)

ApprovalStatus.APPROVED + CommitCandidate 已 confirmed
    → DeliveryAxis 可以从 draft → branch_created

ApprovalStatus.CHANGES_REQUESTED
    → DeliveryAxis.changes_requested

ApprovalStatus.REJECTED
    → DeliveryAxis 保持在当前状态 (不合并)
```

### 7.3 为什么是推导而不是替代

1. **Task/Run/Approval 是"发生了什么"**: 业务事实记录 (task 被执行了，run 成功了，approval 通过了)
2. **四轴生命周期是"现在处于什么状态"**: 实时状态快照 (agent 正在 working，runtime 还活着，PR 已 open)

这种分层设计允许:
- 在不改动现有 DB schema 的前提下，通过查询推导（或缓存）四轴状态
- 当 agent 进程崩溃时，RuntimeAxis 可以标记为 `exited`，但 `Run` 的状态保持 `RUNNING`（可恢复）
- 当 delivery 完成后，`Run.status = SUCCEEDED` 不变，但 `DeliveryAxis` 推进到 `merged`

### 7.4 查询视图 (不建表，用 SQL VIEW 或代码层推导)

```sql
-- 伪代码: 从现有表推导四轴状态
CREATE VIEW coding_session_lifecycle AS
SELECT
    ag.id AS agent_session_id,
    ag.run_id,
    r.task_id,
    t.project_id,

    -- SessionAxis
    CASE
        WHEN ag.status = 'running' THEN 'working'
        WHEN ag.status = 'completed' THEN 'completed'
        WHEN ag.status = 'failed' THEN 'failed'
        WHEN ag.status = 'blocked' THEN 'stuck'
        WHEN ag.status = 'review_rework' THEN 'working'
        ELSE 'spawning'
    END AS session_state,

    -- RuntimeAxis (从 AgentSession 扩展字段获取，当前全部为 'unknown')
    COALESCE(ag.runtime_type_derived, 'unknown') AS runtime_type,
    COALESCE(ag.runtime_state_derived, 'unknown') AS runtime_state,

    -- WorkspaceAxis (从 ChangeSession 获取)
    CASE
        WHEN cs.workspace_status = 'clean' THEN 'ready'
        WHEN cs.workspace_status = 'dirty' THEN 'dirty'
        ELSE 'not_created'
    END AS workspace_state,

    -- DeliveryAxis
    CASE
        WHEN cc.status = 'draft' THEN 'none'
        -- 未来扩展:
        -- WHEN pr.status = 'open' THEN 'pr_opened'
        -- WHEN pr.merged THEN 'merged'
        ELSE 'none'
    END AS delivery_state

FROM agent_sessions ag
JOIN runs r ON ag.run_id = r.id
JOIN tasks t ON r.task_id = t.id
LEFT JOIN change_sessions cs ON cs.project_id = t.project_id
LEFT JOIN change_batches cb ON cb.project_id = t.project_id
LEFT JOIN commit_candidates cc ON cc.change_batch_id = cb.id;
```

---

## 8. P0 / P1 / P2 实施路线

### 8.1 P0: 让 AgentSession 承载真实编码会话身份

**目标**: `AgentSession` 不再只是一个 review/rework 状态记录，而是携带真实的 agent/runtime 环境信息。

**范围**:
1. 在 `AgentSession` 领域模型中新增 6 个可选字段:
   - `agent_type: AgentType | None`
   - `runtime_type: RuntimeType | None`
   - `runtime_handle_id: str | None`
   - `coding_status: CodingSessionStatus | None`
   - `activity_state: CodingSessionActivityState | None`
   - `branch_name: str | None`

2. 在 `AgentSessionTable` (SQLAlchemy) 中新增对应列 (全部 nullable)

3. **不修改 `TaskWorker` 的执行逻辑** — 当前 `TaskWorker` 在创建 `AgentSession` 时填充这些新字段:
   - `agent_type = AgentType.OPENAI_PROVIDER` (当前 provider) 或 `AgentType.SHELL` (当前 shell)
   - `runtime_type = RuntimeType.SUBPROCESS` (当前执行模型)
   - `coding_status = CodingSessionStatus.WORKING` (创建时) → `COMPLETED` 或 `FAILED` (结束时)
   - `branch_name = None` (当前没有 per-run 分支)

4. 在 `WorkerRunResult` 中透传 `agent_type` 和 `runtime_type`

**不变**:
- 不改 `TaskWorker.run_once()` 的同步执行模型
- 不引入真实的 tmux/docker/worktree
- 不创建分支

**价值**:
- 建立编码会话身份的概念基础
- API 可以区分 "这是哪种 agent 执行的"
- 为 P1/P2 的异步执行模型做好数据基础

### 8.2 P1: 引入 Workspace 隔离 + 真实分支

**目标**: 每个 `AgentSession` 可以在独立的 git worktree + 分支中执行。

**范围**:
1. 新增 `WorkspaceType` 列到 `AgentSession`:
   - `workspace_type: WorkspaceType | None`
   - `worktree_path: str | None`

2. 新增 `CommitCandidateStatus.CONFIRMED` 和 `CommitCandidateStatus.APPLIED`:
   - `CONFIRMED`: 老板审批通过，等待执行
   - `APPLIED`: 已执行完成（分支已创建，代码已提交）

3. 新增 `RepositoryAccessMode.READ_WRITE`:
   - 允许在 approved 的 `CommitCandidate` 上执行真实的 git 操作

4. 在 `LocalGitWriteService` 中新增 `create_branch_from_candidate`:
   - 确认 → 创建分支 → apply-local → git-commit → 更新 `AgentSession.branch_name + commit_sha`

5. 前端: 在 `ExecutionRepositoryTab` 中显示真实的 branch 状态

**不变**:
- 不引入 SCM 集成 (不创建 PR)
- 不改 `TaskWorker` 的同步模型
- `RepositoryWorkspace` 的 root_path 仍然是项目级绑定

**价值**:
- `CommitCandidate` 从 draft 走到 confirmed → applied
- 每个 coding session 有独立的 git worktree
- 代码更改从 "JSON 草案" 变成 "真实 git branch + commit"

### 8.3 P2: SCM 集成 + Delivery 闭环

**目标**: 从 branch 到 PR 到 merge 的完整交付闭环。

**范围**:
1. 新增 SCM 抽象层 (参考 agent-orchestrator 的 `SCM` 接口):
   - `SCMService`: 封装 GitHub/GitLab API 调用
   - `detect_pr(session) -> PRInfo`
   - `get_pr_state(pr) -> PRState`
   - `get_ci_checks(pr) -> CICheck[]`
   - `get_reviews(pr) -> Review[]`
   - `create_pr(branch, base, title, body) -> PRInfo`

2. 扩展 `AgentSession` 的 Delivery 字段:
   - `delivery_status: DeliveryStatus | None`
   - `pr_url: str | None`
   - `pr_number: int | None`
   - `ci_status: str | None`
   - `review_decision: str | None`

3. 新增 `SessionPoller` (参考 agent-orchestrator 的 `LifecycleManager`):
   - 定期轮询 agent 进程状态
   - 检测 git 分支创建/PR 创建
   - 轮询 CI/review 状态

4. 前端: Delivery 进度条 (branch → PR → CI → review → merged)

**不变**:
- 不改 `TaskWorker` 的核心调度逻辑
- `ApprovalStatus` 仍然是人工审批门控

**价值**:
- `CommitCandidate` 推进到真实 PR + merge
- 完整的 "AI 编码 → 人工审批 → 自动交付" 闭环
- 对标 agent-orchestrator 的 session 生命周期可视化

---

## 9. 第一阶段最小可落地改造范围

### 9.1 范围定义

**Phase 1 = P0 的子集**，只做数据模型扩展 + API 透传，不动执行逻辑。

### 9.2 具体改造项

#### 9.2.1 领域模型: `app/domain/agent_session.py`

新增 5 个枚举类 + 扩展 `AgentSession` 类:

```python
# 新增枚举 (在文件顶部)
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

# 扩展 AgentSession 类 (在现有字段后追加)
class AgentSession(DomainModel):
    # ... 现有字段 ...

    # Phase 1 新增
    agent_type: AgentType | None = None
    runtime_type: RuntimeType | None = None
    runtime_handle_id: str | None = Field(default=None, max_length=200)
    coding_status: CodingSessionStatus | None = None
    activity_state: CodingSessionActivityState | None = None
    branch_name: str | None = Field(default=None, max_length=200)
```

#### 9.2.2 数据库表: `app/core/db_tables.py`

在 `AgentSessionTable` 中新增 6 列 (全部 nullable):

```python
class AgentSessionTable(ORMBase):
    # ... 现有列 ...

    # Phase 1 新增 (全部 nullable, 不设 default)
    agent_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    runtime_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    runtime_handle_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    coding_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    activity_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    branch_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
```

#### 9.2.3 TaskWorker 填充逻辑: `app/workers/task_worker.py`

在 `TaskWorker.run_once()` 的 `start_session` 调用处 (约第 653 行) 和 `finalize_session` 调用处 (约第 766 行) 填充新字段:

```python
# start_session 时
agent_session = self.agent_conversation_service.start_session(
    project_id=task.project_id,
    task_id=task.id,
    run_id=run.id,
    owner_role_code=run.owner_role_code,
    context_seed=context_seed,
    # Phase 1 新增参数:
    agent_type=AgentType.OPENAI_PROVIDER,  # 当前默认
    runtime_type=RuntimeType.SUBPROCESS,    # 当前默认
    coding_status=CodingSessionStatus.WORKING,
)

# finalize_session 时
agent_session = self.agent_conversation_service.finalize_session(
    session_id=agent_session.id,
    run_status=run.status,
    run_failure_category=run.failure_category,
    final_summary=final_summary,
    # Phase 1 新增参数:
    coding_status=(
        CodingSessionStatus.COMPLETED
        if run.status == RunStatus.SUCCEEDED
        else CodingSessionStatus.FAILED
    ),
    activity_state=CodingSessionActivityState.EXITED,
)
```

#### 9.2.4 API 响应透传

在 `WorkerRunResult` 中新增字段 (已有 `agent_session_*` 字段，追加):

```python
@dataclass(slots=True)
class WorkerRunResult:
    # ... 现有字段 ...
    agent_type: str | None = None
    runtime_type: str | None = None
    coding_status: str | None = None
    activity_state: str | None = None
    branch_name: str | None = None
```

#### 9.2.5 不需要改的文件清单 (明确边界)

以下文件**不在此次改造范围内**:
- `ExecutorService` / `ExecutorService.execute_task()` — 不改执行逻辑
- `TaskWorker.run_once()` 的控制流 — 不改同步执行模型
- `RepositoryWorkspace` / `ChangeSession` / `ChangeBatch` / `CommitCandidate` — 不改 repository 链路
- `ApprovalService` / `ApprovalRepository` — 不改审批流程
- 前端任何文件 — Phase 1 只做后端数据模型
- 任何 smoke test — 推迟到 Phase 1.5
- `agent-orchestrator` 项目 — 不引入其代码，仅参考其设计模式

### 9.3 验收标准

1. `AgentSession` 创建时自动填充 `agent_type = "openai_provider"`, `runtime_type = "subprocess"`, `coding_status = "working"`
2. `AgentSession` 完成时自动更新 `coding_status = "completed"` 或 `"failed"`, `activity_state = "exited"`
3. 新的枚举字段序列化正常，API 响应中包含这些字段
4. 现有 48 个后端测试继续通过（新字段为 nullable，不影响现有逻辑）
5. 现有 smoke test 不受影响

---

## 10. 附录: agent-orchestrator 参考机制摘要

本节提取 agent-orchestrator 中最值得借鉴的设计模式，注明哪些适合 AI-Dev-Orchestrator，哪些不适合。

### 10.1 可借鉴的设计

| agent-orchestrator 设计 | 借鉴价值 | 适配方式 |
|-------------------------|---------|---------|
| **CanonicalSessionLifecycle** (三元组 session/pr/runtime) | ⭐⭐⭐⭐⭐ | 扩展为四轴 (session/workspace/runtime/delivery)，已在 §6 详细设计 |
| **LifecycleManager 轮询循环** | ⭐⭐⭐⭐ | P2 阶段引入 `SessionPoller`，定期探测 agent 进程 + PR 状态 |
| **8 插件槽架构** (Runtime/Agent/Workspace/Tracker/SCM/Notifier/Terminal) | ⭐⭐⭐ | 当前不需要完整插件系统，但 SCM 抽象层可用于 P2 |
| **ActivitySignal** (活动检测置信度) | ⭐⭐⭐⭐ | P1 阶段引入，区分 agent 是否真的在工作还是卡住了 |
| **Metadata 持久化** (JSON 文件) | ⭐⭐ | 当前有 SQLite，不需要。但 agent-orchestrator 的 lifecycle 字段以 JSON 存储的方式值得参考 |
| **Session.reactions** (自动响应) | ⭐⭐⭐ | CI 失败自动通知 agent 修复、PR review 自动回复等。P2+ 考虑 |
| **Session.restore** (会话恢复) | ⭐⭐⭐ | `context_checkpoint_id` 已有基础。P1 支持 coding session 中断恢复 |

### 10.2 不适合直接借鉴的设计

| agent-orchestrator 设计 | 不适合原因 |
|-------------------------|-----------|
| **以 Session 为顶层调度单元** | AI-Dev-Orchestrator 以 Project → Task 为顶层，Session 是 Run 的子级 |
| **基于文件系统的 metadata** | AI-Dev-Orchestrator 使用 SQLite，有完整的关系模型和 FK 约束 |
| **tmux 作为默认 runtime** | 当前依赖 subprocess 直接执行，不需要 tmux session 管理 |
| **独立的 CLI (ao spawn/status/kill)** | AI-Dev-Orchestrator 是 web-first 应用，通过 API + Worker 调度 |
| **Tracker 插件 (Linear/Jira)** | 当前 role/skill 体系已覆盖任务分发 |
| **Notifier 插件** | 当前通过 event stream + console 展示，不需要 push notification |
| **PR 为中心的交付状态机** | 当前以 CommitCandidate draft + Approval 为交付单位，PR 只是可选的交付通道之一 |

### 10.3 agent-orchestrator 最重要的设计教训

1. **三元组 (session/pr/runtime) 是正确的最小粒度**: agent-orchestrator 的 `CanonicalSessionLifecycle` 将 session 状态、PR 状态、runtime 状态分离但联动，这是它最成功的设计。本项目的四轴扩展直接受此启发。

2. **状态推导优于状态存储**: agent-orchestrator 的 `deriveLegacyStatus()` 表明，多个底层状态可以推导出一个高层次状态。不要在每个表里存冗余的"整体状态"字段。

3. **探活是区分"挂了"和"在思考"的基础**: agent-orchestrator 的 `isAlive()` + `detectActivity()` 是两个独立维度。没有探活，编码会话状态机只是摆设。

4. **不可恢复状态机需要明确的 terminal marker**: agent-orchestrator 的 `TERMINAL_STATUSES` 集合清晰地标记了哪些状态是终态。本项目的 `AgentSession.status` 目前没有明确的终态区分。

---

## 总结

本审计的核心发现:

1. **AI-Dev-Orchestrator 当前的执行模型是 "同步任务调度器"，不是 "agent session 编排器"**
2. **AgentSession (Day11) 是一个轻量的 review/rework 记录，缺少承载真实 agent 编码会话的能力**
3. **CommitCandidate 停留在 draft 是因为系统从未设计过 "confirmed → applied → branch → PR → merge" 的交付流程**
4. **四轴生命周期 (Session / Workspace / Runtime / Delivery) 可以从现有 TaskStatus / RunStatus / ProjectStage / ApprovalStatus 推导，不需要推翻现有状态机**
5. **Phase 1 最小可落地改造 = AgentSession 扩展 6 个字段 + TaskWorker 填充逻辑，不动任何执行模型**
