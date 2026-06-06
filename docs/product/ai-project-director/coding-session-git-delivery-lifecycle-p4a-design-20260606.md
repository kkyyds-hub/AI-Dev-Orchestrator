# Coding Session Git Delivery Lifecycle P4-A 设计

> **文档类型**: P4-A 设计文档（R1 修订，只做设计收口，不改业务代码）
> **生成日期**: 2026-06-06
> **R1 修订日期**: 2026-06-06
> **基准 commit**: `ed7e41b963640bcc52c439786c0c70904196daa4`
> **参考项目**: ComposioHQ Agent Orchestrator (`c3eeecb`)
> **前置文档**:
> - `.kkr/skills/ai-project-director-command-governance/SKILL.md`
> - `docs/product/ai-project-director/coding-session-lifecycle-design-20260604.md`
> - `docs/product/ai-project-director/page-information-architecture-20260518.md`
> - `docs/product/ai-project-director/closure-flow-20260518.md`
> - `docs/product/ai-project-director/closure-checklist-20260518.md`
> - `docs/product/ai-project-director/gap-analysis/ai-project-director-ideal-gap-after-p1-20260605.md`
> - `docs/product/ai-project-director/coding-session-worktree-p1-lifecycle-closure-20260605.md`
> - `docs/product/ai-project-director/coding-session-worktree-p2-worker-context-closure-20260605.md`
> - `docs/product/ai-project-director/coding-session-runtime-lifecycle-p3a-design-20260605.md`
> - `docs/product/ai-project-director/coding-session-runtime-lifecycle-p3-closure-20260606.md`
> - `docs/product/ai-project-director/coding-session-runtime-lifecycle-p3d-event-audit-design-20260606.md`
> - `docs/product/ai-project-director/coding-session-runtime-lifecycle-p3d-closure-20260606.md`
> **边界**: 纯设计文档，不改 Python 代码、不改前端、不启动服务、不执行任何 Git 写操作（只允许受控 allowlist 的只读 Git 检查命令）
> **安全边界 (R1 修订)**: 只读 Git 命令（如 `git diff` / `git status` / `git log`）在 allowlist 内可以执行，`runs_git = true` 是预期行为；安全的核心是 `runs_write_git = false`
> **状态**: P4-A Design Complete (R1)；Git add / commit / push / PR: Not started；AI Project Director 总闭环 Partial

---

## 0. 核对过的文件清单

### AI-Dev-Orchestrator 设计文档

| 文件 | 用途 |
|------|------|
| `coding-session-lifecycle-design-20260604.md` | 四轴模型基线 — DeliveryAxis 最初版本定义 (`none → merged`) |
| `page-information-architecture-20260518.md` | 主产品基线 — 成果中心（交付物/审批）、仓库工作区、执行中心 |
| `closure-flow-20260518.md` | 闭环流程 — 交付审批 → 阶段放行 → 项目推进 |
| `closure-checklist-20260518.md` | 闭环验收清单 — DEL/REPO/APV 相关条目 |
| `gap-analysis/ai-project-director-ideal-gap-after-p1-20260605.md` | 真实差距报告 — P4/P5/P6 建议阶段 + Conversation Hub |
| `coding-session-worktree-p1-lifecycle-closure-20260605.md` | P1 收口 — WorktreeAxis create/cleanup Pass |
| `coding-session-worktree-p2-worker-context-closure-20260605.md` | P2 收口 — Worker Context / Runtime Dry-run / Safe Command Proof Pass |
| `coding-session-runtime-lifecycle-p3a-design-20260605.md` | P3-A 设计 — RuntimeAxis 状态机 + gate chain |
| `coding-session-runtime-lifecycle-p3-closure-20260606.md` | P3 收口 — Runtime Lifecycle Evidence Pass |
| `coding-session-runtime-lifecycle-p3d-event-audit-design-20260606.md` | P3-D 设计 — Event/Audit 14 种事件 + JSON 合同 |
| `coding-session-runtime-lifecycle-p3d-closure-20260606.md` | P3-D 收口 — Event/Audit Pass |

### AI-Dev-Orchestrator 后端已有代码

| 文件 | 用途 |
|------|------|
| `runtime/orchestrator/app/domain/agent_session.py` | AgentSession — `DeliveryStatus` 枚举 (P0 预留), `branch_name`, `workspace_path` |
| `runtime/orchestrator/app/domain/agent_message.py` | AgentMessage — `event_type`, `content_summary`, `content_detail` |
| `runtime/orchestrator/app/domain/runtime_event.py` | RuntimeEventSchema + Builder — gate-only event 模式（P4-A 参考） |
| `runtime/orchestrator/app/domain/runtime_lifecycle.py` | RuntimeLifecycleSnapshot — 双轴派生模式（P4-A 参考） |
| `runtime/orchestrator/app/workers/task_worker.py` | WorkerRunResult — P2/P3 evidence 字段（P4-A 参考字段模式） |
| `runtime/orchestrator/app/workers/worktree_safe_command.py` | P2-D pwd proof — deny-by-default allowlist 模式（P4-A 参考） |
| `runtime/orchestrator/app/workers/runtime_adapter.py` | RuntimeAdapter contract + FakeRuntimeAdapter — fake adapter 模式（P4-A 参考） |
| `runtime/orchestrator/app/api/routes/workers.py` | WorkerRunOnceResponse — evidence 透传 API 模式 |
| `runtime/orchestrator/app/api/routes/agent_threads.py` | AgentSessionResponse + RuntimeLifecycleSnapshotResponse |
| `runtime/orchestrator/app/services/runtime_event_audit_service.py` | RuntimeEventAuditService — 事件写入 AgentMessage 模式（P4-A 参考） |
| `runtime/orchestrator/app/repositories/agent_session_repository.py` | AgentSessionRepository — `update_status()`, `mark_workspace_cleaned()` |
| `runtime/orchestrator/app/repositories/agent_message_repository.py` | AgentMessageRepository — `create()`, `get_next_sequence_no()` |

### Agent Orchestrator 参考

| 文件 | 参考要点 |
|------|---------|
| `README.md` | spawn → workspace.create → runtime.create → agent → PR → cleanup 完整生命周期 |
| `packages/core/src/types.ts` | `CanonicalPRState/Reason` — PR 作为独立维度；`SCM` interface: `detectPR()`, `getCIChecks()`, `getReviewThreads()` |
| `packages/core/src/session-manager.ts` | CleanupStack LIFO undo；spawn 失败时的回滚策略 |
| `packages/core/src/lifecycle-manager.ts` | 轮询循环 + PR/CI/review batch enrichment + reaction engine |
| `packages/core/src/lifecycle-state.ts` | `CanonicalSessionLifecycle` 三元组 (session/pr/runtime) 联合推导 |
| `packages/core/src/cleanup-stack.ts` | LIFO undo — 成功时 dismiss，失败时 runAll |
| `packages/plugins/workspace-worktree/src/index.ts` | workspacePath seam；`destroy()` 不删 branch |

---

## A. P4-A 目标

P4-A 是 **Git Delivery Lifecycle 的完整设计收口**。P1 完成了 Workspace Axis（worktree 创建/清理），P2 完成了 Worker Context + Safe Command Proof（"证明可以，但不执行"），P3 完成了 Runtime Axis 的合同和证据链（"门禁通过，但 runtime 尚未启动"）。P4-A 设计的是 Delivery Axis 的状态机、dry-run 合同、diff evidence、审批门禁、事件审计和前端展示字段。

P4-A 的具体目标：

1. **精化 Delivery Axis 状态机** — 基于原始四轴模型中 `DeliveryAxis` 的 11 个状态，增加 dry-run 前置阶段
2. **定义 Git operation dry-run API 合同** — 在 "不执行真实 Git 写" 的前提下，定义 dry-run 的输入/输出/安全标志
3. **定义 diff evidence 字段** — 从 Agent 编码可能产生的 changed files 出发，定义只读 diff/status/summary evidence
4. **设计 delivery gate chain** — 参考 P3 的 runtime launch gate chain，定义 delivery gate（diff gate → human approval gate → feature flag）
5. **设计 human approval gate** — 从 closure-flow 和 closure-checklist 的审批原则出发，定义 git add/commit/push/PR 每一步都需要 explicit user confirmation
6. **定义 delivery event/audit 事件类型** — 参考 P3-D 的 runtime event 14 种模式，定义 delivery event 类型
7. **定义前端只读展示字段** — 定义 delivery dry-run evidence 的前端展示方式
8. **明确 Not started 边界** — 所有真实 Git 写操作（add/commit/push/PR/merge）全部 Not started

---

## B. 当前状态说明

以下基于当前代码事实，不接受假设或夸大：

| 已有项 | 说明 |
|--------|------|
| `AgentSession.branch_name` | P1 create 时写入（`session/proj-<hex8>-<hex8>`），cleanup 时不删除 |
| `AgentSession.workspace_path` | P1 create 时写入 worktree 绝对路径 |
| `AgentSession.workspace_clean` | P1 create 后置为 True；P3 阶段不做 git status |
| `AgentSession.DeliveryStatus` 枚举 | P0 已定义（none/branch_created/pr_opened/ci_pending/…merged/closed），但从未使用 |
| `AgentSession.commit_sha` 字段 | P1 设计中未落地到当前 AgentSession 模型 |
| P1 `WorktreeWriteCommandRunner` | 唯一 allowlisted 写命令: `git worktree add -b` |
| P1 `WorktreeCleanupWriteCommandRunner` | 唯一 allowlisted 写命令: `git worktree remove <path>` |
| P2 `WorkerPwdCommandRunner` | 唯一 allowlisted 只读命令: `pwd`（deny-by-default） |
| `WorkerRunResult` | 已有 ~200 evidence 字段（P2/P3 阶段），P4 新增字段复用相同模式 |

所有以下能力当前严格 **Not started**：
- git add
- git commit
- git push
- PR 创建
- PR 状态检测（open/merged/closed）
- CI check 查询
- code review thread 读取
- merge

---

## C. Delivery Axis 状态机

### C.1 原始设计回顾

`coding-session-lifecycle-design-20260604.md` 定义的 DeliveryAxis：

```
none → branch_created → pr_opened → ci_pending → ci_passing → review_pending → review_approved → merged
                                       ↘ ci_failed → (fix) → pr_opened
                                       ↘ changes_requested → (rework) → pr_opened
                                       ↘ closed
```

P4-A 在此基础上增加三个前置阶段（dry-run / diff evidence / approval gate），并将 P1 的 `branch_created` 状态重新定位。

### C.2 精化后的 Delivery Axis 状态机

```
none (当前)
  │
  ├─ Git diff dry-run (P4-B 计划) ← P4-A 设计阶段
  │   │
  │   ├─ diff_clean (没有改动)
  │   │    └─ delivery skipped (合理终态)
  │   │
  │   └─ diff_dirty (有改动)
  │        │
  │        ├─ File list evidence
  │        ├─ Diff summary evidence
  │        └─ Changed files evidence
  │             │
  │             ├─ Delivery gate (P4-B 计划)
  │             │   ├─ G1: worktree clean check
  │             │   ├─ G2: diff evidence ready
  │             │   ├─ G3: branch name valid
  │             │   ├─ G4: workspace_path valid
  │             │   └─ G5: feature flag gate
  │             │
  │             └─ Human approval (P4-C 计划)
  │                  ├─ approved → git add + commit (P4-D)
  │                  │   └─ branch_created (branch already exists from P1) → pr_opened (P4-E)
  │                  └─ rejected → delivery blocked (终态)
  │
  └─ pr_opened (P4-E 计划, SCM integration)
       ├─ ci_pending → ci_passing → review_pending → review_approved → merged
       ├─ ci_pending → ci_failed → (fix) → pr_opened
       ├─ review_pending → changes_requested → (rework) → pr_opened
       └─ closed
```

### C.3 每个状态的定义

| 状态 | 含义 | 触发条件 | P4-A 实现的阶段 |
|------|------|---------|---------------|
| `none` | 无交付 | Agent 尚未产生代码改动 | **当前状态** |
| `diff_dry_run` | 正在做 diff 预览 | git diff/status --dry-run | P4-B |
| `diff_clean` | 没有改动 | git diff 返回空 | P4-B |
| `diff_dirty` | 有改动 | git diff 返回非空 | P4-B |
| `delivery_gate_evaluated` | 交付门禁已评估 | 五道 delivery gate 全部完成 | P4-B |
| `delivery_gate_blocked` | 交付门禁已阻断 | 至少一道 gate 失败 | P4-B |
| `human_approval_pending` | 等待用户审批 | delivery gate 通过后进入用户确认 | P4-C |
| `human_approval_rejected` | 用户已驳回 | 用户选择不提交 | P4-C |
| `branch_created` | 分支已存在 | P1 create 时已创建（重新定位为 P1 已有状态） | P1 ✅ |
| `git_add_completed` | git add 已完成 | 用户审批通过后执行 git add | P4-D |
| `git_commit_completed` | git commit 已完成 | git add 后执行 git commit | P4-D |
| `pr_opened` | PR 已创建 | git push + gh pr create | P4-E |
| `ci_pending` | CI 运行中 | PR 创建后 CI 自动触发 | P4-E |
| `ci_passing` | CI 检查通过 | 所有 CI checks 通过 | P4-E |
| `ci_failed` | CI 检查失败 | CI checks 失败 | P4-E |
| `review_pending` | 等待代码审查 | PR 等待 review | P4-E |
| `review_approved` | 审查通过 | Review approved | P4-E |
| `changes_requested` | 要求修改 | Review changes requested | P4-E |
| `merged` | 已合并 | PR merged | P4-E |
| `closed` | 已关闭 | PR closed without merge | P4-E |

### C.4 与工作区 / 会话 / 运行时轴的关系

四轴联合推导状态表（只列出 P4 相关的新行）：

| session | workspace | runtime | delivery | → 推导整体状态 |
|---------|-----------|---------|----------|---------------|
| working | ready | alive | none | **working** (当前) |
| working | dirty | alive | diff_dry_run | **working** (diff 预览中) |
| working | dirty | alive | delivery_gate_evaluated | **delivery_ready** |
| working | dirty | alive | delivery_gate_blocked | **delivery_blocked** |
| needs_input | dirty | alive | human_approval_pending | **awaiting_approval** |
| working | committed | alive | git_add_completed | **delivery_in_progress** |
| idle | committed | alive | pr_opened | **pr_open** (AO 等价) |
| idle | committed | alive | ci_failed | **ci_failed** (AO 等价) |
| completed | cleaned | exited | merged | **done** |

---

## D. Git Diff / Status Evidence 字段设计

### D.1 核心原则

PP4-A 参考 P2-C（Runtime Launch Dry-run）的思路：定义 Git diff/status 的 evidence 字段。P4-B 阶段会执行受控 allowlist 的只读 Git 命令（`git diff`、`git status`、`git log`），但**不执行任何 Git 写操作**（`git add`、`git commit`、`git push` 等）。字段的目的是向用户展示 "这次 Agent run 产生了哪些代码改动" 的只读信息。安全的核心是 `runs_write_git = false`，不表示 `runs_git = false`。

### D.2 Diff Evidence 字段定义

遵循 P2/P3 的 evidence 字段命名模式（`<layer>_<name>`），定义一组 **git_diff_dry_run_*** 字段：

| 字段 | 类型 | 含义 |
|------|------|------|
| `git_diff_dry_run_ready` | `bool \| None` | diff dry-run 是否成功执行 |
| `git_diff_dry_run_source` | `str \| None` | 来源标识 (如 `agent_session_worktree_diff`) |
| `git_diff_dry_run_reason_code` | `str \| None` | 未就绪原因码 |
| `git_diff_dry_run_worktree_path` | `str \| None` | 检查的 worktree 路径 |
| `git_diff_dry_run_has_changes` | `bool \| None` | 是否有改动 |
| `git_diff_dry_run_changed_files_count` | `int \| None` | 改动文件数量 |
| `git_diff_dry_run_changed_files` | `list[str]` | 改动文件路径列表 |
| `git_diff_dry_run_added_files` | `list[str]` | 新增文件列表 |
| `git_diff_dry_run_modified_files` | `list[str]` | 修改文件列表 |
| `git_diff_dry_run_deleted_files` | `list[str]` | 删除文件列表 |
| `git_diff_dry_run_renamed_files` | `list[str]` | 重命名文件列表 |
| `git_diff_dry_run_status_summary` | `str \| None` | 中文改动摘要 (如 "2 个文件修改，1 个文件新增") |
| `git_diff_dry_run_diff_stat` | `str \| None` | `git diff --stat` 输出（截断） |
| `git_diff_dry_run_diff_shortstat` | `str \| None` | `git diff --shortstat` 输出 |
| `git_diff_dry_run_branch_name` | `str \| None` | 当前分支名 |
| `git_diff_dry_run_compare_branch` | `str \| None` | 对比分支名（基线分支） |
| `git_diff_dry_run_command` | `str \| None` | 项目录中哪个命令产出了 diff |
| `git_diff_dry_run_peek_command` | `str \| None` | 项目录中哪个命令产生了可审查的差异 |
| `git_diff_dry_run_danger_commands_applied` | `bool \| None` | 项目录中是否有风险命令被执行 |

### D.3 安全标志（R1 修订）

与 P3 runtime evidence 保持相同的模式。**P4-B 阶段执行 allowlisted 的只读 Git 命令时 `runs_git = true` 是预期行为，不代表有风险**。安全的核心是所有 Git 写操作标志保持 `false`：

| 安全开关 | P4-B 预期值 | 含义 |
|---------|--------|------|
| `git_diff_dry_run_runs_git` | **true** | `git diff` / `git status` 等只读命令会实际执行 git，`true` 是安全的（只读） |
| `git_diff_dry_run_runs_write_git` | **false** | **不执行** git add/commit/push 等写操作——这是安全核心 |
| `git_diff_dry_run_git_add_triggered` | **false** | git add 未触发 |
| `git_diff_dry_run_git_commit_triggered` | **false** | git commit 未触发 |
| `git_diff_dry_run_git_push_triggered` | **false** | git push 未触发 |
| `git_diff_dry_run_pr_opened` | **false** | PR 未创建 |
| `git_diff_dry_run_ci_triggered` | **false** | CI 未触发 |
| `git_diff_dry_run_execution_enabled` | **false** | 真实 Git 写入执行未开启 |

**关键声明**: 不要用 `runs_git = false` 来表示安全。安全由 `runs_write_git = false` + 其余写标志全部 `false` 来保证。把只读 git 命令误标为 `runs_git = false` 会让字段失去可信度——因为 `git diff` 确实在执行 git。

### D.4 与 P2 safe command proof 的 deny-by-default 一致

当前允许的只读 Git 命令（继承 P1 的 5 条 preflight 命令）：
- `git rev-parse`
- `git status`
- `git worktree list`
- `git branch --list`
- `git diff --stat / --shortstat`（P4-B 新增）

**任何写操作**（`git add`、`git commit`、`git push`、`git branch -d`、`git worktree remove`）必须经过 delivery gate + human approval gate 双门禁，并写入 delivery event audit。

---

## E. Git Operation Dry-run API 合同

### E.1 参考模式

P4-A 的 Git dry-run 合同参考以下已完成的设计模式：

| 参考 | 来源 | 对应关系 |
|------|------|---------|
| `WorkerRuntimeLaunchDryRun` | P2-C (task_worker.py L224-252) | dry-run 输出包含 ready/source/reason_code + 执行标志全部 false |
| `WorkerPwdCommandSpec` | P2-D (worktree_safe_command.py) | deny-by-default，单一 allowlisted 命令形状 |
| `WorkerWorktreeSafeCommandProof` | P2-D | proof 结果包含 ready + observed 值 + 安全标志 |
| `RuntimeLaunchGateResult` | P3-B (runtime_adapter.py) | gate chain 聚合，任一门失败即 blocked |
| `RuntimeEventSchema` | P3-D (runtime_event.py) | content_detail JSON 合同，safety_flags 9 字段 |

### E.2 Git diff dry-run 数据结构建议

```python
@dataclass(slots=True, frozen=True)
class GitDiffDryRunResult:
    """Evidence-only git diff preview — no git write commands are executed."""

    ready: bool
    source: str                     # "agent_session_worktree" | "agent_session_no_worktree"
    reason_code: str | None         # 未就绪原因
    worktree_path: str | None       # 检查的工作区路径
    has_changes: bool | None        # 是否有改动
    changed_files_count: int | None
    changed_files: list[str]        # 路径列表
    added_files: list[str]
    modified_files: list[str]
    deleted_files: list[str]
    renamed_files: list[str]
    status_summary_cn: str | None   # 中文摘要
    diff_stat: str | None           # git diff --stat (截断)
    diff_shortstat: str | None      # git diff --shortstat
    branch_name: str | None         # 当前 branch
    compare_branch: str | None      # 对比 branch
    command: str | None             # 项目录中哪个命令产出了这次 diff 信息
    peek_command: str | None        # 项目录中哪个命令产生了可审查的差异
    danger_commands_applied: bool | None  # 项目录中是否有风险命令被执行

    # Safety (R1 修订)
    # runs_git=True is EXPECTED in P4-B: git diff/status ARE git commands (read-only).
    # Safety is guaranteed by runs_write_git=False plus all other write flags below.
    runs_git: bool = True            # 只读 git 命令会实际执行 git（安全）
    runs_write_git: bool = False     # **不执行** git add/commit/push（安全核心）
    git_add_triggered: bool = False
    git_commit_triggered: bool = False
    git_push_triggered: bool = False
    pr_opened: bool = False
    ci_triggered: bool = False
    execution_enabled: bool = False
```

### E.3 Command allowlist 合同

与 `worktree_safe_command.py` 保持一致的模式：deny-by-default，每个允许的命令必须显式 allowlist。

P4-B 阶段可以新增的只读命令：

| 命令 | 参数 | 分类 | 说明 |
|------|------|------|------|
| `git diff --stat` | `[-- <paths>]` | `git_diff_stat` | 改动统计 |
| `git diff --shortstat` | 无 | `git_diff_shortstat` | 简短统计 |
| `git diff --name-only` | `[--cached] [-- <paths>]` | `git_diff_name_only` | 只列出文件名 |
| `git diff --name-status` | `[--cached] [-- <paths>]` | `git_diff_name_status` | 文件名 + 状态 (A/M/D/R) |
| `git status --porcelain` | 无 | `git_status_porcelain` | 机器可读状态 |
| `git log --oneline -n <N>` | `-n <N>` | `git_log_oneline` | 最近提交摘要 |

任何 write 命令 (`add`, `commit`, `push`, `merge`, `rebase`, `reset`, `checkout`, `switch`, `stash`, `tag`, `branch -d`, `branch -D`) 始终拒绝执行。

---

## F. Delivery Gate 设计

### F.1 Gate chain

参考 P3-B 的 Runtime Launch Gate Chain (G1–G5)，P4-A 定义 Delivery Gate Chain (D1–D5)：

| Gate | 名称 | 检查内容 | 依赖阶段 |
|------|------|---------|---------|
| D1 | 工作区清洁检查 | `workspace_clean == True` | P1 |
| D2 | diff 证据就绪 | `diff_dry_run.ready` + `has_changes` 已知 | P4-B |
| D3 | 分支名有效 | `branch_name` 非 None，格式符合 `BranchNamePolicy` | P1 |
| D4 | 工作区路径有效 | `workspace_path` 存在且为绝对路径 | P1/P2 |
| D5 | feature flag | `delivery_execution_enabled == True`（用户显式确认后翻转） | P4-C |

### F.2 Gate 聚合结构

```python
@dataclass(slots=True, frozen=True)
class DeliveryGateResult:
    """Aggregate result of the D1–D5 delivery gate chain."""

    ready: bool
    gates_passed: list[str]       # ["G1", "G2", ...]
    gates_failed: list[str]
    blocking_reason_code: str | None
    blocking_summary: str | None

    # Safety — all False in P4-A
    runs_write_git: bool = False
    git_add_triggered: bool = False
    git_commit_triggered: bool = False
    git_push_triggered: bool = False
    pr_opened: bool = False
    execution_enabled: bool = False
```

---

## G. Human Approval Gate 设计

### G.1 为什么需要 Human Approval

P4-A 遵循 closure-flow 的原则：**高风险动作必须用户确认**：

> AI 项目主管拥有调度权和建议权，但高风险动作必须用户确认：
> - 真实写入仓库
> - git commit / push / PR
> - 发布、删除项目、删除交付物、覆盖敏感配置

Git 写操作（add/commit/push/PR）属于高风险动作，必须经过 human approval gate。与 P1 worktree create/cleanup 的 `requires_user_confirmation` 模式保持一致。

### G.2 审批流程（R1 修订：分步双审批）

P4-A-R1 明确：**human approval 必须分步执行，一次审批不能覆盖全部 Git 写动作**。

```
delivery gate passed (D1–D5)
    │
    ▼
human_approval_pending（第一步）
    │
    ├─ user approves add+commit → git add (P4-D)
    │   └─ git commit (P4-D)
    │       │
    │       ├─ 第二步审批: user approves push+PR → git push + PR (P4-E)
    │       │
    │       └─ user does NOT approve push → 代码保留在本地（合法终态）
    │
    └─ user rejects add+commit → human_approval_rejected
        └─ delivery blocked (终态，可重新评估)
```

**关键规则**：
- "同意生成本地提交" 只能覆盖 `git add` + `git commit`
- "同意推送并创建代码合并请求" 必须是另一个独立审批或明确的二次确认
- **不允许**一次模糊的 "同意提交" 自动覆盖 add、commit、push、PR 全部动作
- 用户可以在提交后选择不推送——代码保留在本地是合法终态

### G.3 Approval request 结构建议

```python
@dataclass(slots=True, frozen=True)
class DeliveryApprovalRequest:
    """Request for user confirmation before executing git write operations."""

    session_id: str
    project_id: str
    task_id: str
    run_id: str
    branch_name: str
    workspace_path: str
    changed_files_summary: str
    diff_stat_preview: str | None
    proposed_commit_message: str | None
    proposed_action: str         # "git_add_commit" | "git_push_pr" | "git_push_only"
    risk_level: str              # "low" | "medium" | "high"
    requires_confirmation: bool = True
```

### G.4 与现有 Approval 和 Deliverable 模型的关系

当前项目已经有 `Approval`、`Deliverable`、`ApprovalRequest` 等领域模型在 `runtime/orchestrator/app/domain/` 下。P4-A 建议的 `DeliveryApprovalRequest` 可以作为 `ApprovalRequest` 的一个子类型，但 P4-A 设计阶段不耦合到具体实现。

---

## H. Delivery Handle / Event / Audit 设计

### H.1 Delivery Handle 绑定建议

与 Runtime Handle 类似的模式（`RuntimeHandle` 不表示进程存活），Delivery Handle 也不表示 PR 已创建或代码已推送：

```python
@dataclass(slots=True, frozen=True)
class DeliveryHandle:
    """Opaque identifier for a git delivery. Does NOT imply git write was performed."""

    handle_kind: str              # "branch" | "commit" | "pr"
    handle_value: str             # branch name, commit SHA, or PR number
    workspace_path: str | None
    created_by: str               # "TaskWorker" | "UserConfirmation"
```

### H.2 Delivery event 类型定义

参考 P3-D 的 `RuntimeEventType` 14 种事件设计，P4-A 定义以下 delivery event 类型：

| # | event_type | 含义 | 预计实现阶段 |
|---|-----------|------|------------|
| 1 | `delivery_diff_dry_run_executed` | Git diff 预览已执行 | P4-B |
| 2 | `delivery_diff_dry_run_no_changes` | Git diff 无改动 | P4-B |
| 3 | `delivery_diff_evidence_ready` | diff evidence 字段已生成 | P4-B |
| 4 | `delivery_gate_evaluated` | 交付门禁已评估（D1–D5 全部通过） | P4-B |
| 5 | `delivery_gate_blocked` | 交付门禁已阻断 | P4-B |
| 6 | `delivery_human_approval_requested` | 已发起用户审批 | P4-C |
| 7 | `delivery_human_approval_granted` | 用户已同意 | P4-C |
| 8 | `delivery_human_approval_rejected` | 用户已驳回 | P4-C |
| 9 | `delivery_git_add_completed` | git add 已完成 | P4-D |
| 10 | `delivery_git_commit_completed` | git commit 已完成 | P4-D |
| 11 | `delivery_git_push_completed` | git push 已完成 | P4-E |
| 12 | `delivery_pr_created` | PR 已创建 | P4-E |
| 13 | `delivery_pr_status_updated` | PR 状态已更新 (open/merged/closed) | P4-E |
| 14 | `delivery_ci_status_updated` | CI 状态已更新 | P4-E |
| 15 | `delivery_review_updated` | Review 状态已更新 | P4-E |

### H.3 Delivery event 的 AgentMessage 写入

与 P3-D3 中的 `RuntimeEventAuditService` 保持一致模式：

- role = `SYSTEM`
- message_type = `TIMELINE`
- event_type = `delivery_*`
- state_from / state_to = DeliveryAxis 状态
- content_summary = 中文摘要
- content_detail = content_detail JSON（复用 P3-D 的 JSON 合同模式）

### H.4 Delivery event 的 content_detail JSON 合同

扩展 P3-D 的 JSON 合同，新增 delivery 特定字段：

```json
{
  "schema_version": "1.0",
  "event_id": "<uuid>",
  "event_type": "delivery_gate_blocked",
  "session_id": "<uuid>",
  "project_id": "<uuid>",
  "task_id": "<uuid>",
  "run_id": "<uuid>",
  "delivery_handle_id": null,
  "previous_delivery_state": "none",
  "next_delivery_state": "delivery_gate_blocked",
  "reason_code": "diff_evidence_missing",
  "summary_cn": "交付门禁已阻断：diff 证据未就绪。",
  "safety_flags": {
    "execution_enabled": false,
    "runs_write_git": false,
    "git_add_triggered": false,
    "git_commit_triggered": false,
    "git_push_triggered": false,
    "pr_opened": false,
    "ci_triggered": false
  },
  "evidence": {
    "gates_passed": ["worktree_clean", "branch_name_valid", "workspace_path_valid"],
    "gates_failed": ["diff_evidence_ready"],
    "blocking_reason_code": "diff_evidence_missing",
    "changed_files_count": 0,
    "changed_files": []
  },
  "created_by": "TaskWorker.run_once"
}
```

---

## I. 前端只读展示字段设计

### I.1 对应页面信息架构

根据 `page-information-architecture-20260518.md`，Git delivery 相关展示属于：

- **执行中心 / 仓库工作区** — diff evidence、变更方案、提交草案
- **成果中心 / 交付物** — 交付状态、版本、关联变更
- **成果中心 / 审批** — 用户审批决策面板

### I.2 建议的前端展示组件

#### Git diff 证据面板（执行中心仓库工作区）

参考 `WorkerRuntimeLaunchGateEvidenceCard.tsx`（P3-B3）的模式：

展示字段：
- 改动文件数量 + 中文摘要（"本次执行产生了 3 个文件变更" / "本次执行未产生文件变更"）
- 改动文件列表（added/modified/deleted/renamed 分组）
- diff stat 预览
- 安全标志面板：git add committed / git commit committed / git push committed / PR opened — **全部显示 "否"**
- 底部免责声明："这是 diff 预览证据，不表示代码已被提交、推送或创建 PR。"

#### Delivery gate 证据面板

参考 P3-B3 的门禁链展示：

- 已通过的门禁列表（中文化）
- 失败的门禁列表（中文化）
- 阻断原因和摘要（中文）
- "交付门禁通过只表示前置条件满足，不表示代码已被提交。"

#### Human approval 面板（成果中心审批页）

- 改动文件摘要
- diff 预览
- 建议的 commit message（可编辑）
- 风险等级
- [同意提交] / [驳回] 按钮（均调用真实后端 API）

### I.3 用户可见中文文案规范（R1 补强）

**核心原则**：所有展示给用户看的主文案必须是简单易懂的中文。技术词（如 git add / commit / PR / delivery gate / diff dry-run）不能直接作为主文案，只能放在括号里作为辅助说明。

#### 技术词 → 用户可见中文映射

| 技术词 | 中文主文案 | 辅助说明（可选） |
|--------|-----------|----------------|
| git diff dry-run | 代码改动预览 | （基于 git diff 只读检查） |
| delivery gate | 交付前检查 | （共 5 项前置条件） |
| human approval | 用户确认 | （需要你来审批） |
| git add | 加入待提交区 | （git add 操作） |
| git commit | 生成本地提交 | （git commit 操作） |
| git push | 推送到远程仓库 | （git push 操作） |
| PR（Pull Request） | 代码合并请求 | （Pull Request） |
| CI（Continuous Integration） | 自动检查 | （CI 流水线） |
| code review | 代码审查 | （人工审查） |
| merge | 合并代码 | （merge 操作） |
| diff_dirty | 存在代码改动 | — |
| diff_clean | 没有代码改动 | — |
| branch_created | 分支已存在 | — |
| true / false | 是 / 否 | — |

#### 按钮中文规范

所有按钮必须是用户能理解的中文：

| 按钮功能 | 中文文案 | 禁止使用的文案 |
|---------|---------|--------------|
| 查看 diff | 查看代码改动 | Diff / Show Diff |
| 发起交付前检查 | 检查是否可以提交 | 运行 Delivery Gate |
| 请求用户审批 | 发起提交确认 | Request Human Approval |
| 同意提交（只到 add+commit） | 同意生成本地提交 | Approve / OK |
| 同意推送并创建合并请求 | 同意推送并创建代码合并请求 | Approve Push+PR |
| 驳回本次提交 | 驳回本次提交 | Reject / Deny |
| 查看交付前检查结果 | 查看交付前检查结果 | View Delivery Gate Result |
| 查看提交历史 | 查看提交历史 | View Commit Log |

#### 审批分步说明（R1 新增）

一次审批只能绑定一个具体动作范围：

| 审批步骤 | 审批覆盖的动作 | 按钮中文 |
|---------|-------------|---------|
| 第一步审批 | `git add` + `git commit` | **同意生成本地提交** / **驳回本次提交** |
| 第二步审批 | `git push` + PR 创建 | **同意推送并创建代码合并请求** / **驳回本次推送** |

**不允许**：
- 一次模糊的 "同意提交" 自动覆盖 add、commit、push、PR 全部动作
- "同意推送" 必须是一个独立的审批或明确的二次确认

#### 禁止在功能未实现时使用的误导文案

以下文案在对应能力未实现前**严禁**出现在任何前端页面：

| 禁止文案 | 原因 |
|---------|------|
| 代码已提交 | git commit 尚未实现 |
| 代码已推送 | git push 尚未实现 |
| 合并请求已创建 | PR 尚未实现 |
| 自动提交成功 | git commit 不是自动的，且尚未实现 |
| AI 已完成交付 | Delivery Axis 未闭环 |
| 交付完成 | 同上 |
| PR 已准备 | PR 尚未实现 |
| 提交成功 | 无 git commit 能力 |
| 推送成功 | 无 git push 能力 |
| CI 检查通过 | CI 集成尚未实现 |
| 代码审查已通过 | Code review 尚未实现 |

#### 正确的状态展示文案

在能力未实现时，前端应展示如实的中文状态：

| 场景 | 正确中文 |
|------|---------|
| 代码改动预览已完成 | 检测到 3 个文件变更。注意：改动只是预览结果，尚未被提交或推送。 |
| 代码改动预览无改动 | 本次执行未产生代码改动。 |
| 交付前检查通过 | 交付前检查已全部通过（共 5 项）。这仅表示前置条件满足，代码尚未被提交。 |
| 交付前检查阻断 | 交付前检查已阻断：代码改动预览未就绪。阻断是受控安全行为。 |
| 等待用户确认 | 等待你确认是否生成本地提交。提交后可在下一步选择是否推送到远程仓库。 |
| 用户已驳回 | 你已选择不提交本次改动。可随时重新发起提交确认。 |
| 安全标志面板（通用） | 是否已推送到远程仓库：否；是否已创建代码合并请求：否

---

## J. Feature Flag 翻转条件

### J.1 分层 feature flag

参考 closure-flow 的高风险动作管控原则，P4-A 定义三个级别的 feature flag：

| Flag | 默认值 | 翻转条件 | 预期阶段 |
|------|--------|---------|---------|
| `delivery_diff_dry_run_enabled` | **false** | 用户显式在设置页或审批面板中开启 | P4-B |
| `delivery_git_write_enabled` | **false** | delivery gate D1–D5 全部通过 + human approval granted | P4-C/P4-D |
| `delivery_scm_integration_enabled` | **false** | git push/PR capability implemented + user confirmed | P4-E |

### J.2 Feature flag 审计

每次 feature flag 翻转必须：
1. 写入 delivery event audit（`AgentMessage` timeline）
2. 记录操作者和时间
3. 前端展示明确的 feature flag 状态（"Git 写操作已关闭" / "Git 写操作已开启，需审批"）

---

## K. 与 Agent Orchestrator 的对比参考

### K.1 参考了的机制

| AO 机制 | 学习要点 | P4-A 对应设计 |
|---------|---------|-------------|
| **PR 作为独立维度** | `CanonicalPRState/Reason` 将 PR 状态独立于 session/runtime | DeliveryAxis 作为四轴模型的独立轴 |
| **SCM 接口抽象** | `detectPR()`, `getCIChecks()`, `getReviewThreads()` — SCM 操作与生命周期推导分离 | delivery event 记录 SCM 状态变化，不直接绑定具体 SCM API |
| **human approval gate** | AO 的 orchestrator session 在 PR 合并前等待用户介入 | delivery_gate → human_approval 双门禁 |
| **CleanupStack rollback** | LIFO undo — spawn 失败时反向清理 workspace/runtime | git write 失败时需要 rollback（但不在此设计实现） |
| **workspace path 作为 delivery seam** | `workspacePath` 既是 runtime cwd 也是 delivery 操作的工作目录 | `workspace_path` 贯穿 P1 create → P2 context → P3 dry-run → P4 delivery |

### K.2 不照搬的内容

| AO 内容 | 为什么不照搬 |
|---------|------------|
| SCM 插件 (`detectPR`, `createPR`, `getCIChecks`, `getReviewThreads`) | AI-Dev 的 DeliveryAxis 通过 AgentMessage event 记录 SCM 状态，不绑定特定 SCM provider |
| tmux 作为默认 runtime | AI-Dev 用 subprocess |
| Next.js dashboard | AI-Dev 有自己的 React 前端 |
| `gh` CLI 直接调用 | AI-Dev 通过 allowlisted command runner 间接调用 git |
| 自动 PR 创建 | AI-Dev 的 PR 创建必须经过 human approval gate |
| 文件系统 metadata | AI-Dev 用 SQLite |

---

## L. Not Started 清单

| # | 能力 | 说明 |
|---|------|------|
| 1 | Git diff dry-run | 只读 diff 命令尚未实现 |
| 2 | Diff evidence 字段写入 WorkerRunResult | 未实现 |
| 3 | Delivery gate chain (D1–D5) | 未实现 |
| 4 | delivery_gate_evaluated / blocked event 写入 AgentMessage | 未实现 |
| 5 | Human approval request/response API | 未实现 |
| 6 | delivery_human_approval_* event 写入 AgentMessage | 未实现 |
| 7 | git add | 未实现 |
| 8 | git commit | 未实现 |
| 9 | git push | 未实现 |
| 10 | PR 创建 (gh pr create / GitHub API) | 未实现 |
| 11 | PR 状态轮询 (open/merged/closed) | 未实现 |
| 12 | CI check 查询 | 未实现 |
| 13 | Code review thread 读取 | 未实现 |
| 14 | merge | 未实现 |
| 15 | delivery_* 事件 AgentMessage 写入（除 gate 外的所有事件） | 未实现 |
| 16 | 前端 diff evidence 面板 | 未实现 |
| 17 | 前端 delivery gate 面板 | 未实现 |
| 18 | 前端 human approval 面板 | 未实现 |
| 19 | feature flag 实现 | 未实现 |
| 20 | CleanupStack rollback on git write failure | 未实现 |

---

## M. 后续阶段拆分建议

| 阶段 | 目标 | 说明 |
|------|------|------|
| **P4-B** | Git diff dry-run 实现 | allowlisted 只读 git diff/status 命令 + evidence 字段写入 WorkerRunResult + AgentMessage event |
| **P4-C** | Delivery gate + human approval | D1–D5 gate chain 实现 + human approval API + feature flag |
| **P4-D** | git add + git commit | allowlisted 写命令 (git add + git commit) + delivery event audit |
| **P4-E** | git push + PR 创建 | allowlisted git push + gh pr create + PR 状态轮询 |
| **P4-F** | CI/review integration | SCM API 抽象 + CI/review 状态更新 event |
| **P4-G** | 前端只读展示 | diff evidence 面板 + delivery gate 面板 + human approval 面板 |
| **P4-H** | 端到端 UAT | git diff → delivery gate → human approval → git add/commit/push/PR 完整流程验证 |

---

## Gate 结论

| Gate | 结论 |
|------|------|
| P4-A Git Delivery Lifecycle Design (R1) | **Design Complete (R1)** |
| P4-A 代码实现 | **Not started** |
| Git diff dry-run（只读 diff） | **Not started** |
| Delivery gate（交付前检查） | **Not started** |
| Human approval（分步双审批） | **Not started** |
| git add / git commit | **Not started** |
| git push / PR 创建 | **Not started** |
| CI / review / merge | **Not started** |
| 前端只读展示 | **Not started** |
| AI 自动编码 | **Not started** |
| **AI Project Director 总闭环** | **Partial** |

P4-A-R1 完成了 Git Delivery Lifecycle 的完整设计收口，并修正了两个关键设计问题：
- **安全标志修正**: `runs_git = true`（只读 Git 命令会实际执行 git，这是安全的），`runs_write_git = false`（所有 Git 写操作保持关闭）
- **用户可见中文规范补强**: 所有技术词必须映射为简单中文，按钮必须用户可理解，禁止在功能未实现时使用误导文案

但所有真实 Git 写操作（git add / commit / push / PR / merge）仍然是 **Not started**。P4-A-R1 只是设计的里程碑，不代表代码已开始推进、不代表任何 Git 写操作已执行、不代表 AI 自动编码已启动。AI Project Director 总闭环仍为 **Partial**。
