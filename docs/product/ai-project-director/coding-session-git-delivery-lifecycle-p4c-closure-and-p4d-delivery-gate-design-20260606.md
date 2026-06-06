# Coding Session Git Delivery Lifecycle P4-C 收口 + P4-D Delivery Gate Evidence 设计

> **文档类型**: P4-C 阶段收口审计 + P4-D Delivery Gate Evidence 设计
> **生成日期**: 2026-06-06
> **基准 commit**: `d3a4ee7947db5d77ceadc3dfd409ebb27b51212a`
> **参考项目**: ComposioHQ Agent Orchestrator (`c3eeecb`)
> **前置文档**:
> - `.kkr/skills/ai-project-director-command-governance/SKILL.md`
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4a-design-20260606.md`
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4b2-closure-and-p4b3-event-audit-design-20260606.md`
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4b3-closure-and-p4e-frontend-design-20260606.md`
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4e-closure-and-p4c-operation-dry-run-design-20260606.md`
> **边界**: P4-C 收口审计 + P4-D 纯合同设计，不改 Python 代码、不改 TypeScript 组件、不改 API schema、不改数据库 migration、不运行全量测试、不启动服务
> **状态**: P4-C Closure: Pass；P4-D Design: Design only；AI Project Director 总闭环 Partial

---

## 0. 核对过的文件清单

### AI-Dev-Orchestrator 后端

| 文件 | 用途 |
|------|------|
| `runtime/orchestrator/app/domain/git_operation_dry_run.py` | P4-C1 GitOperationDryRunBuilder + GitOperationDryRunSafetyFlags + GitOperationDryRunResult（388 行） |
| `runtime/orchestrator/app/services/git_diff_dry_run_runner.py` | P4-B1 GitDiffDryRunRunner — deny-by-default 只读 diff/status runner（593 行） |
| `runtime/orchestrator/app/domain/delivery_event.py` | P4-B3 DeliveryEventSchema + DeliveryEventBuilder（402 行） |
| `runtime/orchestrator/app/services/delivery_event_audit_service.py` | P4-B3 DeliveryEventAuditService — AgentMessage 写入（77 行） |
| `runtime/orchestrator/app/workers/task_worker.py` | WorkerRunResult — P4-B2 28 字段 + P4-C2 32 字段 + P4-B3/P4-C 审计调用 |
| `runtime/orchestrator/app/api/routes/workers.py` | WorkerRunOnceResponse — P4-B2 + P4-C2 evidence 透传 |
| `runtime/orchestrator/tests/test_git_operation_dry_run.py` | P4-C1 builder targeted tests（257 行，8 个测试用例） |
| `runtime/orchestrator/tests/test_worker_workspace_readonly_validation.py` | P4-C2 集成测试 — success path render、no-changes blocked、blocked/failed path 不调用 builder |

### Agent Orchestrator 参考

| 文件 | 参考要点 |
|------|---------|
| `README.md` | spawn → workspace.create → runtime.create → agent → PR → cleanup 完整生命周期 |
| `packages/core/src/types.ts` | session/runtime/PR 分轴建模；`CanonicalPRState/Reason`；SCM 接口抽象 |
| `packages/core/src/session-manager.ts` | CleanupStack LIFO undo；recordActivityEvent() 审计模式 |
| `packages/core/src/lifecycle-state.ts` | CanonicalSessionLifecycle 三元组联合推导 |
| `packages/core/src/lifecycle-manager.ts` | 状态探测与事件分离；reaction engine |
| `packages/core/src/cleanup-stack.ts` | LIFO undo — 成功时 dismiss，失败时 runAll |
| `packages/plugins/workspace-worktree/src/index.ts` | workspacePath seam；`destroy()` 不删 branch |

---

## 1. P4-C 真实状态收口

### 1.1 P4-C1 GitOperationDryRunBuilder — PASS

文件：`runtime/orchestrator/app/domain/git_operation_dry_run.py`（388 行）

核心实现：

| 组件 | 说明 |
|------|------|
| `GitOperationDryRunOperation` | 枚举：`GIT_ADD_COMMIT`、`NONE`（不含 `git_push_pr`——R1 修正） |
| `GitOperationDryRunSafetyFlags` | 10 个安全标志 + `validate_p4c_no_execution_boundary()` 强制拒绝任何 forbidden flag 为 True |
| `GitOperationDryRunResult` | Pydantic 域模型，30+ 字段 + `validate_contract()` 确保 ready/reason_code/proposed_operation 一致性 |
| `GitOperationDryRunBuilder.build_from_diff_evidence()` | 从 `GitDiffDryRunResult` + `AgentSession` 构建提案 |
| `P4C_FORBIDDEN_TRUE_SAFETY_FLAGS` | 10 个禁止为 True 的标志：`runs_git`、`runs_write_git`、`git_add_triggered`、`git_commit_triggered`、`git_push_triggered`、`pr_opened`、`ci_triggered`、`execution_enabled`、`operation_applied`、`approval_granted` |

builder 的条件检查顺序（严格执行，按优先级）：

```
1. agent_session is None          → session_missing
2. worktree 不可用                  → worktree_unavailable
3. delivery_operation_dry_run_enabled=False → feature_flag_disabled
4. delivery_git_write_enabled=True  → feature_flag_enabled
5. human_approval_status 非 none/pending → write_already_triggered
6. diff_evidence is None 或 not ready → diff_evidence_not_ready
7. diff_evidence 中有任何写标志为 True → write_already_triggered
8. has_changes=False 或 changed_files_count≤0 → no_changes
9. 全部通过 → ready=True, proposed_operation=GIT_ADD_COMMIT
```

### 1.2 P4-C1-R1 合同修正 — PASS

| 修正项 | 状态 | 证据 |
|--------|------|------|
| `git_push_pr` 已删除 | **Pass** | `GitOperationDryRunOperation` 枚举只有 `git_add_commit` 和 `none`（L39） |
| `test_git_operation_dry_run_operation_does_not_include_push_or_pr_preview` 确认 | **Pass** | L226–L229：`assert "git_" + "push_pr" not in operation_values` |
| `summary_cn` 包含"尚未加入待提交区、尚未生成本地提交、尚未推送" | **Pass** | L273：`"尚未加入待提交区、尚未生成本地提交、尚未推送。"` |
| `session_missing` 拒绝 agent_session=None | **Pass** | L186–L191：`if agent_session is None → session_missing` |
| `feature_flag_enabled`（真实写入开关已开启时拒绝） | **Pass** | L212–L223：`delivery_git_write_enabled=True → feature_flag_enabled` |
| `write_already_triggered` 检查 diff evidence 写标志 | **Pass** | L244–L251：`_has_any_write_flag(diff_evidence)` |
| 10 个 forbidden flags 完整覆盖 | **Pass** | L22–L33：`P4C_FORBIDDEN_TRUE_SAFETY_FLAGS` |

### 1.3 P4-C2 WorkerRunResult / WorkerRunOnceResponse 透传 — PASS

文件：`runtime/orchestrator/app/workers/task_worker.py`（L247–L280 + L387–L439）

`WorkerRunResult` 新增 32 个 `git_operation_dry_run_*` evidence 字段：

| 字段组 | 字段数 | 内容 |
|--------|--------|------|
| 基础状态 | 4 | `ready`、`source`、`reason_code`、`summary_cn` |
| 关联标识 | 4 | `session_id`、`project_id`、`task_id`、`run_id` |
| 工作区信息 | 2 | `worktree_path`、`branch_name` |
| 改动信息 | 7 | `changed_files_count`、`changed_files`、`added_files`、`modified_files`、`deleted_files`、`renamed_files` |
| 提案操作 | 5 | `proposed_operation`、`proposed_steps`、`proposed_commit_message`、`proposed_pr_title`、`proposed_pr_body` |
| 审批要求 | 3 | `user_confirmation_required`、`human_approval_required`、`feature_flag_required` |
| 安全标志 | 10 | `runs_git`、`runs_write_git`、`git_add_triggered`、`git_commit_triggered`、`git_push_triggered`、`pr_opened`、`ci_triggered`、`execution_enabled`、`operation_applied`、`approval_granted` |

文件：`runtime/orchestrator/app/api/routes/workers.py` → `WorkerRunOnceResponse` 完整透传所有 32 个字段。

关键设计：`_git_operation_dry_run_result_kwargs()` 函数（L387–L439）：
- `result is None` → 返回空 dict（blocked/failed path 不写 operation fields）
- `result is not None` → 完整映射所有字段
- `safety_flags` 从 `result.safety_flags` 直接读取，不硬编码

### 1.4 P4-C2-R1 no-changes 与 blocked path 测试补强 — PASS

| 测试用例 | 文件名 | 行号 | 状态 |
|---------|--------|------|------|
| success path 有改动 → operation ready | `test_worker_workspace_readonly_validation.py` | L971 | **Pass** |
| success path 无改动 → operation blocked (no_changes) | `test_worker_workspace_readonly_validation.py` | L1168 | **Pass** |
| execution failed → git_operation_dry_run_ready=None | `test_worker_workspace_readonly_validation.py` | L1442–L1443 | **Pass** |
| pwd mismatch blocked → git_operation_dry_run_ready=None | `test_worker_workspace_readonly_validation.py` | L965–L966 | **Pass** |
| builder test: ready from dirty diff | `test_git_operation_dry_run.py` | L65 | **Pass** |
| builder test: 5 blocked reason_code | `test_git_operation_dry_run.py` | L114 | **Pass** |
| builder test: feature_flag_disabled | `test_git_operation_dry_run.py` | L182 | **Pass** |
| builder test: session_missing | `test_git_operation_dry_run.py` | L195 | **Pass** |
| builder test: feature_flag_enabled (write flag on) | `test_git_operation_dry_run.py` | L212 | **Pass** |
| builder test: no push_pr in operation enum | `test_git_operation_dry_run.py` | L226 | **Pass** |
| safety flags: each forbidden flag rejected | `test_git_operation_dry_run.py` | L233 | **Pass** |
| contract: ready + reason_code rejected | `test_git_operation_dry_run.py` | L242 | **Pass** |

### 1.5 P4-C Gate

| Gate | 结论 |
|------|------|
| P4-C1 GitOperationDryRunBuilder | **Pass** |
| P4-C1-R1 git_push_pr / summary_cn / session_missing / feature_flag_enabled 修正 | **Pass** |
| P4-C2 WorkerRunResult / WorkerRunOnceResponse 透传（32 字段） | **Pass** |
| P4-C2-R1 no-changes Worker 路径测试 | **Pass** |
| P4-C2-R1 blocked / failed path 不调用 builder 测试 | **Pass** |
| P4-C1 builder targeted tests（8 用例） | **Pass** |
| git add / commit / push / PR | **Not started（正确）** |
| **P4-C Closure** | **Pass** |
| **AI Project Director 总闭环** | **Partial** |

---

## 2. 当前已完成 Delivery evidence 链路

从 P4-B1 到 P4-C 的完整只读证据链路（比 P4-E 收口时新增 P4-C 两层）：

```
1. GitDiffDryRunRunner.collect()            — 只读 git diff/status 采集 (P4-B1)
      │   7 种 allowlisted 命令形状
      │   runs_git=True（只读），runs_write_git=False
      ▼
2. WorkerRunResult git_diff_dry_run_* 字段  — 28 个 evidence 字段 (P4-B2)
      ▼
3. WorkerRunOnceResponse API 透传          — 前端可读取 (P4-B2)
      ▼
4. DeliveryEventBuilder                     — 规范化事件 + SafetyFlags 强制校验 (P4-B3)
      │   3 种事件：collected / skipped / failed
      ▼
5. DeliveryEventAuditService                — 写入 AgentMessage timeline (P4-B3)
      │   role=SYSTEM, message_type=TIMELINE
      ▼
6. AgentMessage 持久化                      — 永久审计记录 (P4-B3)
      ▼
7. 前端 Worker evidence 只读展示            — WorkerGitDiffDryRunEvidenceCard (P4-E)
      │   ManualRunResultSection + WorkerPoolResultSection
      ▼
8. 前端 Agent timeline delivery event 展示  — AgentDeliveryDiffEventPanel (P4-E)
      │
      ▼  ← ← ← P4-C 新增从以下开始 ← ← ←
      │
9. GitOperationDryRunBuilder                — 从 diff evidence 构建提交提案 (P4-C1)
      │   6 种阻断条件 + 10 forbidden safety flags
      │   runs_git=False（纯计算，不执行 Git）
      ▼
10. WorkerRunResult git_operation_dry_run_* — 32 个 evidence 字段 (P4-C2)
      │   _git_operation_dry_run_result_kwargs() 映射
      ▼
11. WorkerRunOnceResponse API 透传         — 前端可读取 (P4-C2)
```

**关键安全边界（全链路强制执行）**：

| 安全标志 | P4-B 值 | P4-C 值 | 说明 |
|---------|---------|---------|------|
| `runs_git` | **True**（执行了 git diff/status） | **False**（纯提案计算） | P4-C 不调 git |
| `runs_write_git` | **False** | **False** | 两阶段都不写 |
| `git_add_triggered` | **False** | **False** | 不触发 add |
| `git_commit_triggered` | **False** | **False** | 不触发 commit |
| `git_push_triggered` | **False** | **False** | 不触发 push |
| `pr_opened` | **False** | **False** | 不创建 PR |
| `ci_triggered` | **False** | **False** | 不触发 CI |
| `execution_enabled` | **False** | **False** | 不开启真实执行 |
| `operation_applied` | N/A | **False** | 提案未应用 |
| `approval_granted` | N/A | **False** | 审批未授予 |

---

## 3. 当前仍 Not started 清单

| # | 能力 | 说明 |
|---|------|------|
| 1 | Delivery gate evidence | 无交付门禁证据——无法判断"是否允许进入用户确认提交预览阶段" |
| 2 | Human approval API | 无审批 API |
| 3 | Delivery snapshot 派生 | 无 delivery lifecycle 状态快照 |
| 4 | Git operation dry-run 前端展示 | 无提交预览前端面板 |
| 5 | git add | 未实现 |
| 6 | git commit | 未实现 |
| 7 | git push | 未实现 |
| 8 | PR 创建 | 未实现 |
| 9 | CI / review / merge | 未实现 |
| 10 | CleanupStack rollback | 未实现 |
| 11 | AI Project Director 总闭环 Pass | 仍为 Partial |

---

## 4. P4-D Delivery Gate Evidence 设计目标

### 4.1 P4-D 定位

P4-D 是 P4-C（Git Operation Dry-run 实现收口）和 P4-F（Human Approval Gate）之间的**纯合同设计阶段**。

P4-D 的目标是设计 **DeliveryGateEvidenceResult**——一个 gate evidence 结构，用来判断"是否允许进入用户确认提交预览阶段"。P4-D 会消费 P4-B（diff evidence）和 P4-C（operation dry-run）的输出，执行交叉验证，得出统一的 gate 结论。

P4-D **不执行**：
- git add
- git commit
- git push
- PR 创建
- merge
- branch delete
- reset / checkout / switch / stash / rebase / tag
- human approval 写入

### 4.2 P4-D 与 P4-C 的关键区别

| 维度 | P4-C（Operation Dry-run） | P4-D（Delivery Gate Evidence） |
|------|--------------------------|------------------------------|
| 消费了什么 | P4-B diff evidence + AgentSession | P4-B diff evidence + P4-C operation dry-run + workspace context + runtime gate + delivery event audit |
| 做了什么 | 构建提交提案（如果执行，会做什么） | 交叉验证所有前置条件是否满足，得出 gate 结论 |
| 产出了什么 | `GitOperationDryRunResult` | `DeliveryGateEvidenceResult` |
| 回答了什么问题 | "如果确认，将提交什么？" | "现在可以进入用户确认界面吗？" |
| 安全标志 | runs_git=False（纯计算） | gate_allows_write=False（绝不输出写权限） |

---

## 5. Delivery Gate 输入证据

### 5.1 必须消费的证据源

P4-D 的 `DeliveryGateEvidenceResult` 必须综合以下所有证据源得出 gate 结论：

| # | 证据源 | 来源 | 检查内容 |
|---|--------|------|---------|
| E1 | AgentSession workspace / branch / worktree | P1 | `workspace_type` 为 worktree，`workspace_path` 非空，`branch_name` 非空 |
| E2 | Worker workspace context evidence | P2 | `WorkerWorkspaceValidationResult.ready=True`，`workspace_clean=True` |
| E3 | Runtime launch gate evidence | P3 | `RuntimeLaunchGateResult.ready=True` |
| E4 | Git diff dry-run evidence | P4-B | `GitDiffDryRunResult.ready=True`，`has_changes=True`，`changed_files_count>0` |
| E5 | Git operation dry-run evidence | P4-C | `GitOperationDryRunResult.ready=True`，`proposed_operation=git_add_commit` |
| E6 | Delivery event audit evidence | P4-B3 | 存在有效的 `delivery_diff_dry_run_collected` event，无 `delivery_diff_dry_run_failed` event |
| E7 | Safety flags 全线一致 | P4-B/P4-C | 所有写操作 flags 为 False，`runs_write_git=False`，`operation_applied=False`，`approval_granted=False` |
| E8 | Feature flag 状态 | 未来 | `delivery_git_write_enabled=False` |

### 5.2 输入证据的消费方式

`DeliveryGateEvidenceBuilder` 应接收以下输入参数：

```python
@staticmethod
def evaluate(
    *,
    agent_session: Any,                          # E1
    diff_evidence: GitDiffDryRunResult | None,    # E4
    operation_dry_run: GitOperationDryRunResult | None,  # E5
    delivery_git_write_enabled: bool = False,     # E8
) -> DeliveryGateEvidenceResult:
```

P4-D builder 内部应自行验证 workspace context（从 agent_session 派生）和 safety flags 一致性（从 diff_evidence + operation_dry_run 派生），不接受外部注入的伪造 gate 状态。

---

## 6. Delivery Gate ready=True 条件

### 6.1 全部必须满足的条件

P4-D 的 `DeliveryGateEvidenceResult.ready=True` 必须在以下条件**全部**满足时才能产生：

| # | 条件 | 依赖 | 说明 |
|---|------|------|------|
| G1 | AgentSession 存在 | E1 | 会话信息完整可用 |
| G2 | workspace_type=worktree | E1 | 会话绑定的是 worktree 类型的工作区 |
| G3 | workspace_path 非空 | E1 | worktree 路径有效 |
| G4 | branch_name 非空 | E1 | 分支名已分配 |
| G5 | workspace_clean=True | E1/E2 | 工作区清洁 |
| G6 | diff_evidence 存在 | E4 | GitDiffDryRunResult 存在 |
| G7 | diff_evidence.ready=True | E4 | diff 预览成功执行 |
| G8 | diff_evidence.has_changes=True | E4 | 有改动 |
| G9 | diff_evidence.changed_files_count>0 | E4 | 改动文件数 >0 |
| G10 | diff_evidence.runs_write_git=False | E4/E7 | diff 阶段未执行写操作 |
| G11 | operation_dry_run 存在 | E5 | GitOperationDryRunResult 存在 |
| G12 | operation_dry_run.ready=True | E5 | 操作预览已生成 |
| G13 | operation_dry_run.proposed_operation=git_add_commit | E5 | 提案操作为 add+commit |
| G14 | operation_dry_run.user_confirmation_required=True | E5 | 需要用户确认 |
| G15 | operation_dry_run.human_approval_required=True | E5 | 需要人工审批 |
| G16 | operation_dry_run.safety_flags 全部为 False | E5/E7 | 操作预览未执行任何动作 |
| G17 | operation_dry_run.operation_applied=False | E5/E7 | 操作未应用 |
| G18 | operation_dry_run.approval_granted=False | E5/E7 | 审批未授予 |
| G19 | delivery_git_write_enabled=False | E8 | 写操作 feature flag 未开启 |
| G20 | diff 与 operation 的 changed_files 一致 | E4/E5 | 两个证据源描述的改动文件数量一致 |

### 6.2 条件满足时的行为

`ready=True` 的含义**严格限定为**：

- ✅ 允许进入用户确认提交预览阶段
- ❌ 不表示 git add 已执行
- ❌ 不表示 git commit 已执行
- ❌ 不表示 approval 已通过
- ❌ 不表示 PR 已创建
- ❌ 不表示代码已交付

`ready=True` 时 `next_required_action` 必须设为 `"await_user_confirmation"`。

---

## 7. Delivery Gate Blocked reason_code

### 7.1 完整阻断原因码

| reason_code | 对应不满足条件 | summary_cn |
|-------------|-------------|-----------|
| `agent_session_missing` | G1 | 会话信息缺失，无法进行交付前检查。 |
| `worktree_unavailable` | G2/G3 | 当前工作区不可用，无法进行交付前检查。 |
| `branch_missing` | G4 | 当前工作区未绑定分支，无法进行交付前检查。 |
| `workspace_not_clean` | G5 | 工作区状态不一致，无法进行交付前检查。 |
| `diff_evidence_not_ready` | G6/G7 | 代码改动预览未就绪，无法进行交付前检查。 |
| `no_changes` | G8/G9 | 当前没有可提交的代码改动。 |
| `diff_write_flag_triggered` | G10 | 检测到 diff 阶段写操作标志异常，无法进行交付前检查。 |
| `operation_dry_run_not_ready` | G11/G12 | 提交预览未就绪，无法进行交付前检查。 |
| `unsupported_operation` | G13 | 当前操作类型不支持交付。 |
| `operation_write_flag_triggered` | G16 | 检测到操作预览阶段写操作标志异常，无法进行交付前检查。 |
| `operation_already_applied` | G17 | 操作已应用，无法重复进行交付前检查。 |
| `approval_already_granted` | G18 | 审批已授予，无法重新进行交付前检查。 |
| `feature_flag_enabled` | G19 | 真实写入开关已开启，不支持预览模式下的交付前检查。 |
| `evidence_mismatch` | G20 | 代码改动预览与提交预览不一致，无法进行交付前检查。 |
| `audit_evidence_missing` | E6 | 缺少交付审计记录，无法进行交付前检查。 |

### 7.2 阻断时的行为

`ready=False` 时：
- `next_required_action` 设为 `"resolve_blocking_conditions"`
- `blocking_reasons` 列出所有不满足的条件
- `satisfied_conditions` 列出所有已满足的条件（用于诊断）
- 不输出任何"可以提交"的暗示

---

## 8. Delivery Gate 输出字段

### 8.1 DeliveryGateEvidenceResult 数据结构

```python
@dataclass(slots=True, frozen=True)
class DeliveryGateEvidenceResult:
    """Aggregated delivery gate evidence — does NOT execute any Git write."""

    # --- 基础状态 ---
    ready: bool
    source: str                     # "delivery_gate_evidence"
    reason_code: str | None         # 阻断原因码（ready=False 时非空）

    # --- 关联标识 ---
    session_id: str
    project_id: str
    task_id: str
    run_id: str

    # --- 工作区信息 ---
    worktree_path: str | None
    branch_name: str | None

    # --- 提案信息（透传自 operation dry-run，用于前端展示）---
    proposed_operation: str         # "git_add_commit" | "none"
    changed_files_count: int
    changed_files: list[str]

    # --- 下一步动作 ---
    next_required_action: str       # "await_user_confirmation" | "resolve_blocking_conditions" | "none"
    user_confirmation_required: bool
    human_approval_required: bool

    # --- 中文摘要 ---
    summary_cn: str

    # --- gate 明细 ---
    satisfied_conditions: list[str]    # 已满足的条件代号列表
    blocking_reasons: list[str]        # 不满足的条件代号 + reason_code 列表

    # --- 安全标志 ---
    runs_git: bool = False
    runs_write_git: bool = False
    git_add_triggered: bool = False
    git_commit_triggered: bool = False
    git_push_triggered: bool = False
    pr_opened: bool = False
    ci_triggered: bool = False
    execution_enabled: bool = False
    operation_applied: bool = False
    approval_granted: bool = False
    gate_allows_write: bool = False          # **始终为 False**
    gate_allows_user_confirmation: bool = False  # ready=True 时为 True
```

### 8.2 next_required_action 枚举

| 值 | 含义 | 对应 ready |
|----|------|-----------|
| `"await_user_confirmation"` | 允许进入用户确认提交预览界面 | ready=True |
| `"resolve_blocking_conditions"` | 需要解决阻断条件后重新评估 | ready=False |
| `"none"` | 无下一步动作 | 异常状态 |

### 8.3 关键声明

- `gate_allows_write` **始终为 False**：P4-D 只做 gate evidence，不授权任何写操作
- `gate_allows_user_confirmation` 为 True 时**只表示**用户可以进入确认界面看到提交预览——**不表示** git add/commit 已执行、approval 已通过、PR 已创建

---

## 9. Delivery Gate Safety Flags

### 9.1 安全标志定义

P4-D 的 safety flags 比 P4-C 多两个专用标志：

| 安全标志 | P4-D 预期值 | 含义 |
|---------|-----------|------|
| `runs_git` | **False** | P4-D gate 评估不执行任何 Git 命令 |
| `runs_write_git` | **False** | 不执行写操作——安全核心 |
| `git_add_triggered` | **False** | git add 未触发 |
| `git_commit_triggered` | **False** | git commit 未触发 |
| `git_push_triggered` | **False** | git push 未触发 |
| `pr_opened` | **False** | PR 未创建 |
| `ci_triggered` | **False** | CI 未触发 |
| `execution_enabled` | **False** | 真实 Git 写入执行未开启 |
| `operation_applied` | **False** | 操作未应用 |
| `approval_granted` | **False** | 审批未授予 |
| `gate_allows_write` | **False** | **始终为 False——gate 不授权写操作** |
| `gate_allows_user_confirmation` | **True/False** | ready=True 时为 True；只表示允许进入确认界面 |

### 9.2 强制校验规则

P4-D 的 `DeliveryGateEvidenceSafetyFlags` 构造时必须强制执行：

```python
P4D_FORBIDDEN_TRUE_SAFETY_FLAGS: tuple[str, ...] = (
    "runs_git",
    "runs_write_git",
    "git_add_triggered",
    "git_commit_triggered",
    "git_push_triggered",
    "pr_opened",
    "ci_triggered",
    "execution_enabled",
    "operation_applied",
    "approval_granted",
    "gate_allows_write",            # P4-D 永远不授权写操作
)
```

注意：`gate_allows_user_confirmation` **不在** forbidden 列表中——它在 `ready=True` 时应为 True。

### 9.3 P4-D 与 P4-B/P4-C safety flags 的关键区别

| 标志 | P4-B | P4-C | P4-D | 说明 |
|------|------|------|------|------|
| `runs_git` | True | False | False | P4-D 也不执行 Git 命令 |
| `gate_allows_write` | N/A | N/A | **False** | P4-D 特有——绝不授权写操作 |
| `gate_allows_user_confirmation` | N/A | N/A | **ready** | P4-D 特有——可以允许进入确认界面 |
| 其他写标志 | 全部 False | 全部 False | 全部 False | 三个阶段都不做写操作 |

---

## 10. 用户可见中文规范

### 10.1 允许文案（P4-D 推荐使用）

| 场景 | 推荐中文文案 |
|------|------------|
| gate 通过 | 交付前检查已通过，可以进入用户确认。仍未执行提交或推送。 |
| gate 未通过 | 交付前检查未通过。 |
| 无改动 | 当前没有可提交的代码改动。 |
| 工作区不可用 | 当前工作区不可用，无法进行交付前检查。 |
| diff evidence 未就绪 | 代码改动预览未就绪，无法进行交付前检查。 |
| operation dry-run 未就绪 | 提交预览未就绪，无法进行交付前检查。 |
| feature flag 已开启 | 真实写入开关已开启，不支持预览模式下的交付前检查。 |
| 证据不一致 | 代码改动预览与提交预览不一致，请联系管理员。 |
| gate 面板标题 | 交付前检查 |
| gate 结果描述 | 这是交付前检查结果，不表示代码已被提交、推送或创建合并请求。需要用户确认后才能进入下一步。 |
| satisfied_conditions 标题 | 已满足条件 |
| blocking_reasons 标题 | 未满足条件 |
| next_required_action: await_user_confirmation | 等待用户确认 |
| next_required_action: resolve_blocking_conditions | 需要解决阻断条件 |
| safety flag 面板标题 | 操作安全标记 |
| gate_allows_write=false | 未授权写操作 |
| gate_allows_user_confirmation=true | 可以进入用户确认界面 |
| gate_allows_user_confirmation=false | 不允许进入用户确认界面 |

### 10.2 禁止文案（P4-D 及所有后续阶段严禁使用）

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
| 可合并 | merge 尚未实现 |

---

## 11. P4-D Event / Audit 设计边界

### 11.1 可以设计但不实现的 event 类型

P4-D 可以在文档中定义以下 event 类型作为未来实现参考，但**本轮不实现**：

| # | event_type | 含义 | 触发时机 | 实现阶段 |
|---|-----------|------|---------|---------|
| 1 | `delivery_gate_evaluated` | 交付前检查已通过 | DeliveryGateEvidenceBuilder.evaluate() 返回 ready=True | 未来 P4-D 实现 |
| 2 | `delivery_gate_blocked` | 交付前检查已阻断 | DeliveryGateEvidenceBuilder.evaluate() 返回 ready=False | 未来 P4-D 实现 |

### 11.2 delivery_gate_evaluated 的精确语义

`delivery_gate_evaluated`（ready=True）的语义**严格限定为**：

- ✅ 所有前置条件已满足，可以进入用户确认界面
- ❌ 不表示 git add / commit 已执行
- ❌ 不表示 approval 已通过
- ❌ 不表示 PR 已创建
- ❌ 不表示代码已交付

任何将 `delivery_gate_evaluated` 误解为"代码已交付"的实现都是**错误的**。

### 11.3 Event/Audit 实现边界

P4-D 设计阶段只定义 event 类型名称和 JSON 合同形状。以下行为**不在** P4-D 范围内：

- 不实现 DeliveryEventBuilder 对 gate event 的支持
- 不实现 DeliveryEventAuditService 对 gate event 的写入
- 不修改 `P4B3_BUILDABLE_DELIVERY_EVENT_TYPES` 元组
- 不修改 `DeliveryEventType` 枚举
- 不修改 `DeliveryEventState` 枚举

### 11.4 禁止设计为已完成事件

以下事件对应真实 Git 写操作，在 P4-D 及所有当前阶段**严禁**设计为已完成：

| # | event_type | 为什么禁止 |
|---|-----------|----------|
| 1 | `delivery_git_add_completed` | git add 尚未实现 |
| 2 | `delivery_git_commit_completed` | git commit 尚未实现 |
| 3 | `delivery_git_push_completed` | git push 尚未实现 |
| 4 | `delivery_pr_created` | PR 创建尚未实现 |
| 5 | `delivery_pr_merged` | merge 尚未实现 |
| 6 | `delivery_branch_deleted` | branch delete 尚未实现 |

---

## 12. 参考机制总结

从 Agent Orchestrator 参考项目中提取的机制，及其在 P4-D 设计中的应用：

| # | AO 机制 | 学习要点 | P4-D 对应设计 |
|---|---------|---------|-------------|
| 1 | session / runtime / PR 分轴建模 | `CanonicalSessionLifecycle` 三元组 — 各维度独立推导 | P4-D gate evidence 作为独立 contract，消费多轴证据但不修改各轴状态 |
| 2 | workspace/worktree 作为隔离边界 | `workspacePath` 贯穿全生命周期 | P4-D 必须验证 worktree_path 有效性 |
| 3 | evidence / event / snapshot 分离 | evidence 瞬态、event 历史、snapshot 派生 — 三者不混用 | P4-D gate evidence 是 evidence 层聚合，不是 event 层写入 |
| 4 | operation preview 与真实执行分离 | `detectPR()` 只读，`createPR()` 写操作 | P4-D gate 只评估条件，不授权写操作（`gate_allows_write=False`） |
| 5 | gate / lifecycle state 只表达真实状态 | AO 的 lifecycle manager 只从已完成事件推导当前状态 | P4-D gate ready=True 只表示"可以进入确认界面"，不表示"已交付" |
| 6 | cleanup / rollback 作为未来阶段参考 | CleanupStack LIFO undo | P4-D 不实现 rollback，`operation_applied=False` 预留 |

---

## 13. 下一步 Codex 最小实现建议

### 13.1 实现范围

下一条 Codex 指令应严格限定在以下范围：

| # | 做什么 | 说明 |
|---|--------|------|
| 1 | 新增 `DeliveryGateEvidenceBuilder` | 位置：`runtime/orchestrator/app/domain/delivery_gate_evidence.py`（新文件） |
| 2 | 实现 `evaluate()` | 接收 AgentSession + GitDiffDryRunResult + GitOperationDryRunResult → 交叉验证 20 个条件 |
| 3 | 包含 `DeliveryGateEvidenceSafetyFlags` 域模型 | 12 个 safety flags + validator 拒绝 11 个 forbidden flag 为 True |
| 4 | `DeliveryGateEvidenceResult` 域模型 | 20+ 字段 + `validate_contract()` |
| 5 | 窄范围单元测试 | 只测试 gate evaluate 逻辑（全部通过/部分阻断/全部阻断） |

### 13.2 不做什么

| # | 不做什么 | 说明 |
|---|---------|------|
| 1 | 不接前端 | 不新增组件、不修改现有组件 |
| 2 | 不接 Worker | 不在 `TaskWorker.run_once()` 中调用 `DeliveryGateEvidenceBuilder` |
| 3 | 不写 AgentMessage | 不实现 `delivery_gate_evaluated` / `delivery_gate_blocked` event 写入 |
| 4 | 不执行 Git 写操作 | 不调 git add/commit/push |
| 5 | 不写 approval | 不实现 human approval API |
| 6 | 不创建 PR | 不调 gh pr create 或 GitHub API |
| 7 | 不修改 DeliveryEventBuilder | 不扩展 `P4B3_BUILDABLE_DELIVERY_EVENT_TYPES` |
| 8 | 不跑全量 pytest | 只跑新增的 targeted tests |
| 9 | 不跑全量 build | 不触发 `apps/web build` |

### 13.3 测试范围

```bash
# 只允许运行：
cd runtime/orchestrator
python -m pytest tests/test_delivery_gate_evidence.py -v

# 禁止运行：
pytest  # 全量
cd apps/web && npm run build  # 前端 build
```

### 13.4 文件清单

| 文件 | 操作 | 内容 |
|------|------|------|
| `runtime/orchestrator/app/domain/delivery_gate_evidence.py` | 新建 | `DeliveryGateEvidenceSafetyFlags` + `DeliveryGateEvidenceResult` + `DeliveryGateEvidenceBuilder` |
| `runtime/orchestrator/tests/test_delivery_gate_evidence.py` | 新建 | 窄范围 targeted tests（≤12 个测试用例） |

---

## Gate 结论

| Gate | 结论 |
|------|------|
| P4-C1 GitOperationDryRunBuilder | **Pass** |
| P4-C1-R1 git_push_pr / summary_cn / session_missing / feature_flag_enabled 修正 | **Pass** |
| P4-C2 WorkerRunResult / WorkerRunOnceResponse 透传（32 字段） | **Pass** |
| P4-C2-R1 no-changes Worker 路径测试 | **Pass** |
| P4-C2-R1 blocked / failed path 不调用 builder 测试 | **Pass** |
| P4-C1 builder targeted tests（8 用例） | **Pass** |
| git add / commit / push / PR | **Not started（正确）** |
| **P4-C Closure** | **Pass** |
| P4-D Delivery Gate Evidence 设计 | **Design only** |
| P4-D DeliveryGateEvidenceBuilder 实现 | **Not started** |
| P4-D delivery gate evidence API | **Not started** |
| P4-D gate event AgentMessage 写入 | **Not started** |
| Delivery snapshot 派生 | **Not started** |
| Git operation dry-run 前端展示 | **Not started** |
| Human approval API | **Not started** |
| git add / commit | **Not started** |
| git push / PR 创建 | **Not started** |
| CI / review / merge | **Not started** |
| CleanupStack rollback | **Not started** |
| **AI Project Director 总闭环** | **Partial** |

P4-C 完成了 Git Operation Dry-run 从 Builder 域模型到 WorkerRunResult/WorkerRunOnceResponse 透传的完整闭环——`GitOperationDryRunBuilder` 6 种阻断条件 + 10 forbidden safety flags、`GitOperationDryRunResult` 30+ 字段、WorkerRunResult 32 字段、WorkerRunOnceResponse API 透传、no-changes Worker 路径测试、blocked/failed path 不调用 builder 测试、P4-C1-R1 合同修正（`git_push_pr` 删除、`summary_cn` 声明"尚未加入待提交区、尚未生成本地提交、尚未推送"、`session_missing` / `feature_flag_enabled` 完善）。

P4-D 定义了 Delivery Gate Evidence 合同——综合 8 类证据源（AgentSession、workspace context、runtime gate、diff evidence、operation dry-run、delivery audit、safety flags、feature flag）、20 个 ready 条件、15 个阻断 reason_code、12 个 safety flags（含 `gate_allows_write=False` 和 `gate_allows_user_confirmation` 两个专属标志）、2 种 event 类型（`delivery_gate_evaluated` / `delivery_gate_blocked`，可设计不实现）。

P4-D 明确：gate ready=True 只表示"可以进入用户确认界面"，不表示 git add/commit 已执行、不表示 approval 已通过、不表示 PR 已创建、不表示代码已交付。`gate_allows_write` 始终为 False。AI Project Director 总闭环仍为 **Partial**——在所有 Git 写操作实现并通过证据验证之前，不能标记为 Pass。
