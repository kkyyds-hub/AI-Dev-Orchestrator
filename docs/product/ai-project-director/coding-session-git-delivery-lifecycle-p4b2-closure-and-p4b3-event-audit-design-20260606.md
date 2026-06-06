# Coding Session Git Delivery Lifecycle P4-B2 收口 + P4-B3 Event/Audit 设计

> **文档类型**: P4-B2 阶段收口审计 + P4-B3 事件审计设计
> **生成日期**: 2026-06-06
> **基准 commit**: `4c4563f1a30bc420cc93b89eabef4ed32d3f63c9`
> **参考项目**: ComposioHQ Agent Orchestrator (`c3eeecb`)
> **前置文档**:
> - `.kkr/skills/ai-project-director-command-governance/SKILL.md`
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4a-design-20260606.md`
> - `docs/product/ai-project-director/coding-session-runtime-lifecycle-p3d-event-audit-design-20260606.md`
> - `docs/product/ai-project-director/coding-session-runtime-lifecycle-p3d-closure-20260606.md`
> **边界**: 收口审计 + 设计确认，不改业务代码、不写 AgentMessage、不实现 git add/commit/push/PR
> **状态**: P4-B2 Closure: Pass；P4-B3 Design: Design only；AI Project Director 总闭环 Partial

---

## 0. 核对过的文件清单

### AI-Dev-Orchestrator 后端

| 文件 | 用途 |
|------|------|
| `runtime/orchestrator/app/services/git_diff_dry_run_runner.py` | P4-B1 GitDiffDryRunRunner — deny-by-default 只读 git diff/status runner |
| `runtime/orchestrator/app/workers/task_worker.py` | WorkerRunResult P4-B2 evidence 字段 + diff collect 调用 |
| `runtime/orchestrator/app/api/routes/workers.py` | WorkerRunOnceResponse P4-B2 evidence 透传 |
| `runtime/orchestrator/app/domain/agent_message.py` | AgentMessage 域模型 — event_type/content_summary/content_detail |
| `runtime/orchestrator/app/domain/runtime_event.py` | RuntimeEventSchema + Builder — P3-D gate-only event 模式（P4-B3 参考） |
| `runtime/orchestrator/app/services/runtime_event_audit_service.py` | RuntimeEventAuditService — AgentMessage 写入模式（P4-B3 参考） |
| `runtime/orchestrator/app/repositories/agent_message_repository.py` | AgentMessageRepository — create() + get_next_sequence_no() |
| `runtime/orchestrator/tests/test_git_diff_dry_run_runner.py` | P4-B1 targeted tests |
| `runtime/orchestrator/tests/test_worker_workspace_readonly_validation.py` | P2/P3 regression baseline |

### Agent Orchestrator 参考

| 文件 | 参考要点 |
|------|---------|
| `README.md` | spawn → workspace.create → runtime.create → agent → PR → cleanup |
| `packages/core/src/types.ts` | session/runtime/PR 分轴；SCM interface；RuntimeHandle |
| `packages/core/src/session-manager.ts` | recordActivityEvent() 审计模式；CleanupStack |
| `packages/core/src/lifecycle-state.ts` | CanonicalSessionLifecycle 三元组推导 |
| `packages/core/src/lifecycle-manager.ts` | 状态探测与事件分离；reaction engine |
| `packages/core/src/cleanup-stack.ts` | LIFO undo；失败保留审计线索 |

---

## 1. P4-B2 真实状态收口

### 1.1 P4-B1: Git diff/status read-only runner — PASS

文件：`runtime/orchestrator/app/services/git_diff_dry_run_runner.py`（593 行）

核心实现：

| 组件 | 说明 |
|------|------|
| `GitDiffDryRunRunner` | deny-by-default runner，只允许 7 种只读 git 命令形状 |
| `_ensure_read_only_allowlisted()` | 拒绝任何 `mutates_repository=True` 的命令；拒绝非 git 命令；拒绝未 allowlist 的 git 命令 |
| `collect()` | 组合 git status porcelain + diff name-status + diff stat + diff shortstat + branch current → 完整 diff evidence |
| 安全边界 | `runs_git=True`（只读 git 命令会实际执行 git），`runs_write_git=False`，`git_add/commit/push_triggered=False` |

7 种 allowlisted 命令：
- `git status --porcelain=v1 --untracked-files=all`
- `git diff --stat [-- <paths>]`
- `git diff --shortstat`
- `git diff [--cached] --name-only [-- <paths>]`
- `git diff [--cached] --name-status [-- <paths>]`
- `git log --oneline -n <N>`（N ≤ 20）
- `git rev-parse --abbrev-ref HEAD`

### 1.2 P4-B1-R1: 测试补强 — PASS

文件：`runtime/orchestrator/tests/test_git_diff_dry_run_runner.py`

测试覆盖：
- allowlist 暴露验证
- 真实 git repository fixture 中的 status/diff/log 命令执行
- 成功路径 `collect()` 返回完整 evidence（changed_files、added/modified/deleted/renamed、status_summary_cn、diff_stat 等）
- blocked path（missing path / not directory / empty path）不调用 git 命令

### 1.3 P4-B2: WorkerRunResult / WorkerRunOnceResponse 透传 — PASS

文件：`runtime/orchestrator/app/workers/task_worker.py`（L215–L241）

`WorkerRunResult` 新增 28 个 `git_diff_dry_run_*` evidence 字段：

| 字段组 | 字段数 | 内容 |
|--------|--------|------|
| 基础状态 | 4 | `ready`、`source`、`reason_code`、`worktree_path` |
| 改动统计 | 7 | `has_changes`、`changed_files_count`、`changed_files`、`added_files`、`modified_files`、`deleted_files`、`renamed_files` |
| 摘要/预览 | 4 | `status_summary_cn`、`diff_stat`、`diff_shortstat`、`branch_name` |
| 命令审计 | 4 | `compare_branch`、`command`、`peek_command`、`danger_commands_applied` |
| 安全标志 | 9 | `runs_git`、`runs_write_git`、`git_add_triggered`、`git_commit_triggered`、`git_push_triggered`、`pr_opened`、`ci_triggered`、`execution_enabled`、加上 runner 自身标志 |

文件：`runtime/orchestrator/app/api/routes/workers.py` → `WorkerRunOnceResponse` 完整透传所有 28 个字段。

### 1.4 P4-B2-R1: 字段合同修正 — PASS

- `runs_git=True` 作为 P4-B 只读阶段的正确默认值
- `runs_write_git=False` 保持安全边界
- 所有 `git_*_triggered=False` 确保写操作未触发
- `status_summary_cn` 使用中文摘要："X 个文件修改，Y 个文件新增，Z 个文件删除，W 个文件重命名"

### 1.5 向 Worker 主链的集成状态

在 `TaskWorker.run_once()` 中，Git diff dry-run evidence 在 executor 成功后、finalize 前收集。当前集成状态：
- 成功路径（executor succeeded + worktree 可用）→ `GitDiffDryRunRunner.collect()` 被调用
- blocked / failed 路径 → 不调用 `collect()`（设计决定：不浪费 git 检查在已知失败的任务上）

### 1.6 Gate

| Gate | 结论 |
|------|------|
| P4-B1 Git diff/status read-only runner | **Pass** |
| P4-B1-R1 测试补强 | **Pass** |
| P4-B2 WorkerRunResult 透传 | **Pass** |
| P4-B2-R1 字段合同修正 | **Pass** |
| **AI Project Director 总闭环** | **Partial** |

---

## 2. 当前已完成能力清单

| # | 能力 | 证据 |
|---|------|------|
| 1 | Git diff/status read-only runner | `git_diff_dry_run_runner.py` 593 行 |
| 2 | deny-by-default allowlist（7 种命令形状） | `_ensure_read_only_allowlisted()` |
| 3 | changed_files / added / modified / deleted / renamed evidence | `collect()` 合并 status porcelain + diff name-status |
| 4 | status_summary_cn 中文摘要 | `_build_status_summary_cn()` — "X 个文件修改，Y 个文件新增" |
| 5 | runs_git=True / runs_write_git=False 安全边界 | `GitDiffDryRunResult` 数据类 |
| 6 | WorkerRunResult 28 字段透传 | `task_worker.py` L215–241 |
| 7 | WorkerRunOnceResponse API DTO 透传 | `workers.py` |
| 8 | 成功路径 `collect()` 测试 | `test_git_diff_dry_run_runner.py` |
| 9 | blocked / failed path 不调用 `collect()` | 设计决定（测试中验证） |

---

## 3. 当前仍 Not started 清单

| # | 能力 | 说明 |
|---|------|------|
| 1 | AgentMessage delivery event 写入 | git diff dry-run 结果未写入 timeline |
| 2 | DeliveryEventBuilder | 无 delivery 事件域模型 |
| 3 | DeliveryEventAuditService | 无 delivery 事件审计服务 |
| 4 | 前端 delivery evidence 展示 | 无 diff evidence 面板 |
| 5 | human approval API | 无审批 API |
| 6 | delivery gate (D1–D5) | 无交付门禁链 |
| 7 | git add | 未实现 |
| 8 | git commit | 未实现 |
| 9 | git push | 未实现 |
| 10 | PR 创建 | 未实现 |
| 11 | CI / review / merge | 未实现 |
| 12 | CleanupStack rollback | 未实现 |
| 13 | AI Project Director 总闭环 Pass | 仍为 Partial |

---

## 4. P4-B3 事件设计边界

### 4.1 核心原则

P4-B3 参考 P3-D 的 Event/Audit 设计模式（`RuntimeEventSchema` + `RuntimeEventBuilder` + `RuntimeEventAuditService`），但独立于 runtime event。Delivery event 使用自己的事件类型前缀（`delivery_*`）和内容合同，不与 runtime event 混用。

### 4.2 P4-B3 允许写入的事件

P4-B3 **只**允许设计并准备实现以下 3 个只读 evidence event：

| # | event_type | 含义 | 写入时机 |
|---|-----------|------|---------|
| 1 | `delivery_diff_dry_run_collected` | 代码改动预览已完成 | `GitDiffDryRunRunner.collect()` 成功返回 `ready=True` |
| 2 | `delivery_diff_dry_run_skipped` | 代码改动预览已跳过 | worktree 不可用或非 worktree 类型，未执行 diff |
| 3 | `delivery_diff_dry_run_failed` | 代码改动预览失败 | `collect()` 返回 `ready=False`（路径问题、git 命令失败） |

### 4.3 P4-B3 禁止写入的事件

以下事件在 P4-B3 **严禁**写入——它们对应真实 Git 写操作，尚未实现：

| # | event_type | 为什么禁止 |
|---|-----------|----------|
| 1 | `delivery_git_add_completed` | git add 尚未实现 |
| 2 | `delivery_git_commit_completed` | git commit 尚未实现 |
| 3 | `delivery_git_push_completed` | git push 尚未实现 |
| 4 | `delivery_pr_created` | PR 创建尚未实现 |
| 5 | `delivery_pr_status_updated` | PR 状态轮询尚未实现 |
| 6 | `delivery_ci_status_updated` | CI 集成尚未实现 |
| 7 | `delivery_review_updated` | Code review 尚未实现 |
| 8 | `delivery_merged` | merge 尚未实现 |
| 9 | `delivery_human_approval_requested` | 用户审批 API 尚未实现 |
| 10 | `delivery_human_approval_granted` | 同上 |
| 11 | `delivery_human_approval_rejected` | 同上 |
| 12 | `delivery_gate_evaluated` | 交付门禁链尚未实现 |
| 13 | `delivery_gate_blocked` | 同上 |

### 4.4 关键声明

P4-B3 delivery event 写入 AgentMessage timeline **不表示代码已交付**。这只是将 P4-B1/B2 的 diff evidence 固化为可回放的历史审计记录。与 P3-D 的 `runtime_launch_gate_*` 事件类似——事件证明 "门禁已通过"，但不证明 "runtime 已启动"。P4-B3 的事件证明 "diff 已执行"，但不证明 "代码已提交/推送"。

---

## 5. Event / Evidence / Snapshot 三者边界

这是 P4 阶段的关键概念边界——与 P3 阶段的同名概念完全一致的区分原则：

| 概念 | 是什么 | 存储位置 | 生命周期 | P4 当前状态 |
|------|--------|---------|---------|----------|
| **Git Diff Dry-run Evidence** (P4-B2) | 单次 Worker 响应中的 diff 证据 | `WorkerRunResult` 字段（内存） | 一次 Worker 周期 | ✅ 已实现（28 字段） |
| **Delivery Lifecycle Event** (P4-B3) | 可回放的历史审计事件 | `AgentMessage` 表（SQLite） | 永久（追加写入） | ⏳ 本设计定义 |
| **Delivery Lifecycle Snapshot** (未来 P4-C+) | 从 AgentSession + latest event 派生的当前交付状态 | 不存储（每次读取时计算） | 每次读取 | ❌ Not started |

**三者不能混用**：
- Evidence 是瞬态的 — Worker 结束后消失
- Event 是历史的 — 一旦写入不可修改
- Snapshot 是派生的 — 从已有数据计算

**P4-B3 只做**：把 P4-B2 的 diff evidence 固化为 delivery event。这个 event 可以被未来的 delivery snapshot 派生逻辑读取（例如 "因为看到了 `delivery_diff_dry_run_collected` event，所以 snapshot 的 delivery state 从 `none` 变为 `diff_dirty`"），但那样的派生逻辑属于未来阶段。

---

## 6. 建议的 Delivery Event JSON 合同

### 6.1 结构定义

遵循 P3-D `RuntimeEventSchema` 的 JSON 合同模式，但使用 delivery 专用字段：

```json
{
  "schema_version": "1.0",
  "event_id": "<uuid>",
  "event_type": "delivery_diff_dry_run_collected",
  "session_id": "<uuid>",
  "project_id": "<uuid>",
  "task_id": "<uuid>",
  "run_id": "<uuid>",
  "previous_delivery_state": "none",
  "next_delivery_state": "diff_dirty",
  "reason_code": null,
  "summary_cn": "已完成代码改动预览：检测到 3 个文件变更。注意：改动只是预览结果，尚未被提交或推送。",
  "technical_detail": null,
  "safety_flags": {
    "runs_git": true,
    "runs_write_git": false,
    "git_add_triggered": false,
    "git_commit_triggered": false,
    "git_push_triggered": false,
    "pr_opened": false,
    "ci_triggered": false,
    "execution_enabled": false
  },
  "evidence": {
    "worktree_path": "/tmp/aido-worktree",
    "has_changes": true,
    "changed_files_count": 3,
    "changed_files": ["src/a.py", "src/b.py", "README.md"],
    "added_files": ["src/b.py"],
    "modified_files": ["src/a.py", "README.md"],
    "deleted_files": [],
    "renamed_files": [],
    "status_summary_cn": "2 个文件修改，1 个文件新增",
    "branch_name": "session/proj-a1b2c3d4-e5f6g7h8",
    "compare_branch": null
  },
  "created_by": "TaskWorker.run_once"
}
```

### 6.2 三种事件的 summary_cn 示例

| event_type | summary_cn |
|-----------|-----------|
| `delivery_diff_dry_run_collected` | 已完成代码改动预览：检测到 X 个文件变更。注意：改动只是预览结果，尚未被提交或推送。 |
| `delivery_diff_dry_run_collected`（无改动） | 本次执行未产生代码改动。 |
| `delivery_diff_dry_run_skipped` | 代码改动预览已跳过：当前没有可检查的工作区。 |
| `delivery_diff_dry_run_failed` | 代码改动预览失败：无法读取工作区改动。原因：<reason_code>。 |

---

## 7. P4-B3 安全标志要求

所有 delivery diff event 的 `safety_flags` 必须明确以下安全边界：

| 安全标志 | P4-B3 值 | 含义 |
|---------|---------|------|
| `runs_git` | **true** | `git diff` / `git status` 等只读命令会实际执行 git——这是安全的 |
| `runs_write_git` | **false** | **不执行** git add/commit/push 等写操作——这是安全核心 |
| `git_add_triggered` | **false** | git add 未触发 |
| `git_commit_triggered` | **false** | git commit 未触发 |
| `git_push_triggered` | **false** | git push 未触发 |
| `pr_opened` | **false** | PR 未创建 |
| `ci_triggered` | **false** | CI 未触发 |
| `execution_enabled` | **false** | 真实 Git 写入执行未开启 |

---

## 8. 用户可见中文要求

### 8.1 summary_cn 文案规范

所有 `summary_cn` 必须是简单中文，禁止使用英文枚举或技术缩写作为主文案：

| 场景 | 正确中文 | 禁止文案 |
|------|---------|---------|
| diff 有改动 | 已完成代码改动预览：检测到 3 个文件变更。注意：改动只是预览结果，尚未被提交或推送。 | diff collected, 3 files changed |
| diff 无改动 | 本次执行未产生代码改动。 | No changes detected |
| diff 跳过 | 代码改动预览已跳过：当前没有可检查的工作区。 | delivery_diff_dry_run_skipped |
| diff 失败 | 代码改动预览失败：无法读取工作区改动。 | diff dry-run failed, reason_code=xxx |

### 8.2 禁止误导文案

在功能未实现前，任何 delivery event 的 `content_summary` 或前端展示**严禁**出现：

- 代码已提交
- 代码已推送
- 合并请求已创建
- 自动提交成功
- AI 已完成交付
- 交付完成
- PR 已准备
- 提交成功
- 推送成功

---

## 9. P4-B3 建议实现范围

下一步建议交给 Codex 做 P4-B3 最小实现——只覆盖 diff dry-run event 的 AgentMessage 写入：

### 需要新增的代码

1. **DeliveryEventBuilder** 或 **GitDeliveryEventBuilder**
   - 位置：`runtime/orchestrator/app/domain/delivery_event.py`（新文件）
   - 范围：定义 `DeliveryEventType` 枚举（3 个值）+ `DeliveryEventSchema`（Pydantic 模型）+ `GitDeliveryEventBuilder`（工厂，只接受 collected/skipped/failed）
   - 参考：`runtime_event.py` 的 `P3D2_BUILDABLE_RUNTIME_EVENT_TYPES` 限制模式

2. **DeliveryEventAuditService** 或 **GitDeliveryEventAuditService**
   - 位置：`runtime/orchestrator/app/services/delivery_event_audit_service.py`（新文件）
   - 范围：`record_diff_dry_run_event()` — 接收 `GitDiffDryRunResult` + `AgentSession` → 写入 AgentMessage
   - 参考：`runtime_event_audit_service.py` 的 `record_launch_gate_event()` 模式

3. **AgentMessage 写入参数**
   - `role = SYSTEM`
   - `message_type = TIMELINE`
   - `event_type = "delivery_diff_dry_run_collected" | "delivery_diff_dry_run_skipped" | "delivery_diff_dry_run_failed"`
   - `phase = AgentSession.current_phase`
   - `state_from / state_to = delivery_state`（如 `"none" → "diff_dirty"`）
   - `intervention_type = None`
   - `note_event_type = None`
   - `content_summary = summary_cn`（中文）
   - `content_detail = JSON`（delivery event 合同）

### 不需要改变的代码

- 不改变 executor 阻断行为
- 不接前端
- 不实现 git add / commit / push / PR
- 不改变 `TaskWorker.run_once()` 中 executor 调用前后逻辑（只追加 event 写入）

---

## 10. P4-B3 不建议做的事情

| # | 不建议 |
|---|--------|
| 1 | 不实现 delivery gate (D1–D5) |
| 2 | 不实现 human approval |
| 3 | 不实现真实 Git 写操作（git add/commit/push） |
| 4 | 不创建 PR |
| 5 | 不接 CI |
| 6 | 不改变 executor 阻断行为 |
| 7 | 不接前端 |
| 8 | 不把总闭环写成 Pass |

---

## Gate 结论

| Gate | 结论 |
|------|------|
| P4-B1 Git diff/status read-only runner | **Pass** |
| P4-B1-R1 测试补强 | **Pass** |
| P4-B2 WorkerRunResult / WorkerRunOnceResponse 透传 | **Pass** |
| P4-B2-R1 字段合同修正 | **Pass** |
| P4-B3 Delivery Event/Audit Design | **Design only** |
| P4-B3 代码实现 | **Not started** |
| AgentMessage delivery event 写入 | **Not started** |
| git add / commit / push | **Not started** |
| PR 创建 | **Not started** |
| CI / review / merge | **Not started** |
| **AI Project Director 总闭环** | **Partial** |

P4-B2 完成了 Git diff dry-run evidence 从 runner 到 WorkerRunResult 到 WorkerRunOnceResponse API 的完整证据链路。P4-B3 定义了 delivery event/audit 的设计边界——3 个允许写入的只读 evidence event、13 个禁止写入的真实 Git 操作 event、完整的 JSON 合同和中文文案规范。

下一步交给 Codex 在 P4-B3 中实现最小 `DeliveryEventBuilder` + `DeliveryEventAuditService`，只覆盖 diff dry-run collected/skipped/failed 三种事件，不改 executor 阻断行为，不接前端。
