# Coding Session Git Delivery Lifecycle P4-D 收口 + P4-E2 前端提交预览 / 交付前检查只读展示设计

> **文档类型**: P4-D 阶段收口审计 + P4-E2 前端只读展示设计
> **生成日期**: 2026-06-06
> **基准 commit**: `db03b39dac2a7fbe61fbb3b077741e69ac2861c5`
> **参考项目**: ComposioHQ Agent Orchestrator (`c3eeecb`)
> **前置文档**:
> - `.kkr/skills/ai-project-director-command-governance/SKILL.md`
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4a-design-20260606.md`
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4c-closure-and-p4d-delivery-gate-design-20260606.md`
> **边界**: P4-D 收口审计 + P4-E2 前端设计，不改 Python 代码、不改 TypeScript 代码、不改 API schema、不改数据库 migration、不运行全量测试、不启动服务
> **状态**: P4-D Closure: Pass；P4-E2 Design: Design only；AI Project Director 总闭环 Partial

---

## 0. 核对过的文件清单

### AI-Dev-Orchestrator 后端

| 文件 | 用途 |
|------|------|
| `runtime/orchestrator/app/domain/git_operation_dry_run.py` | P4-C1 GitOperationDryRunBuilder + GitOperationDryRunSafetyFlags + GitOperationDryRunResult（388 行） |
| `runtime/orchestrator/app/domain/delivery_gate_evidence.py` | P4-D1 DeliveryGateEvidenceBuilder + DeliveryGateEvidenceSafetyFlags + DeliveryGateEvidenceResult（542 行） |
| `runtime/orchestrator/app/services/git_diff_dry_run_runner.py` | P4-B1 GitDiffDryRunRunner — deny-by-default 只读 diff/status runner（593 行） |
| `runtime/orchestrator/app/domain/delivery_event.py` | P4-B3 DeliveryEventSchema + DeliveryEventBuilder（402 行） |
| `runtime/orchestrator/app/services/delivery_event_audit_service.py` | P4-B3 DeliveryEventAuditService — AgentMessage 写入（77 行） |
| `runtime/orchestrator/app/workers/task_worker.py` | WorkerRunResult — P4-B2 28 + P4-C2 32 + P4-D2 33 字段；`_delivery_gate_evidence_result_kwargs()` 映射（L486+） |
| `runtime/orchestrator/app/api/routes/workers.py` | WorkerRunOnceResponse — P4-B2/P4-C2/P4-D2 evidence 透传 |
| `runtime/orchestrator/tests/test_delivery_gate_evidence.py` | P4-D1 builder targeted tests（387 行，7 个测试用例） |
| `runtime/orchestrator/tests/test_worker_workspace_readonly_validation.py` | P4-D2 集成测试 — success path gate ready、audit wrong type / not ready、blocked/failed path 不调用 gate builder |

### AI-Dev-Orchestrator 前端

| 文件 | 用途 |
|------|------|
| `apps/web/src/features/task-actions/types.ts` | WorkerRunOnceResponse 类型 — 当前只到 `git_diff_dry_run_*`，尚未含 P4-C/P4-D 字段 |
| `apps/web/src/features/task-actions/WorkerGitDiffDryRunEvidenceCard.tsx` | P4-E Worker diff evidence 只读展示卡片（423 行） |
| `apps/web/src/features/agents/components/AgentDeliveryDiffEventPanel.tsx` | P4-E Agent timeline delivery event 面板（390 行） |
| `apps/web/src/app/sections/ManualRunResultSection.tsx` | 手动执行结果区 — 集成 WorkerGitDiffDryRunEvidenceCard |
| `apps/web/src/app/sections/WorkerPoolResultSection.tsx` | 批量 Worker 结果区 — 集成 WorkerGitDiffDryRunEvidenceCard |

### Agent Orchestrator 参考

| 文件 | 参考要点 |
|------|---------|
| `README.md` | spawn → workspace.create → runtime.create → agent → PR → cleanup 完整生命周期 |
| `packages/core/src/types.ts` | session/runtime/PR 分轴建模；evidence/event/snapshot 分离 |
| `packages/core/src/lifecycle-state.ts` | CanonicalSessionLifecycle 三元组联合推导 |
| `packages/core/src/lifecycle-manager.ts` | 前端展示只表达真实状态，不提前显示未实现能力 |

---

## 1. P4-D 真实状态收口

### 1.1 P4-D1 DeliveryGateEvidenceBuilder — PASS

文件：`runtime/orchestrator/app/domain/delivery_gate_evidence.py`（542 行）

核心实现：

| 组件 | 说明 |
|------|------|
| `DeliveryGateEvidenceSafetyFlags` | 12 个安全标志 + `validate_p4d_no_execution_boundary()` 强制拒绝 11 个 forbidden flag 为 True |
| `DeliveryGateEvidenceResult` | Pydantic 域模型，29 个字段 + `validate_contract()` 确保 ready/reason_code/proposed_operation/next_required_action/satisfied_conditions 一致性 |
| `DeliveryGateEvidenceBuilder.evaluate()` | 从 AgentSession + diff_evidence + operation_dry_run + audit evidence 参数 + feature flag → 逐条件验证 G1–G21 |
| `P4D_FORBIDDEN_TRUE_SAFETY_FLAGS` | 11 个禁止为 True 的标志：`runs_git`、`runs_write_git`、`git_add_triggered`、`git_commit_triggered`、`git_push_triggered`、`pr_opened`、`ci_triggered`、`execution_enabled`、`operation_applied`、`approval_granted`、`gate_allows_write` |
| `P4D_READY_CONDITIONS` | G1–G21 完整条件列表 |
| `P4D_REASON_SUMMARIES_CN` | 15 个阻断原因的中文摘要映射 |
| `DELIVERY_AUDIT_COLLECTED_EVENT_TYPE` | 期望的 audit event type：`delivery_diff_dry_run_collected` |

`evaluate()` 的 21 个条件检查顺序：

```
G1:  agent_session is not None
G2:  workspace_type == "worktree"
G3:  workspace_path is not None
G4:  branch_name is not None
G5:  workspace_clean is True
G6:  diff_evidence is not None
G7:  diff_evidence.ready is True
G8:  diff_evidence.has_changes is True
G9:  diff_evidence.changed_files_count > 0
G10: diff_evidence 所有写标志为 False
G11: operation_dry_run is not None
G12: operation_dry_run.ready is True
G13: operation_dry_run.proposed_operation == "git_add_commit"
G14: operation_dry_run.user_confirmation_required is True
G15: operation_dry_run.human_approval_required is True
G16: operation_dry_run safety_flags 全部为 False
G17: operation_dry_run.operation_applied is False
G18: operation_dry_run.approval_granted is False
G19: delivery_git_write_enabled is False
G20: diff 与 operation 的 changed_files 一致
G21: delivery_audit_event_present=True + event_type=delivery_diff_dry_run_collected + event_ready=True
```

### 1.2 P4-D1-R1 Audit Evidence 输出字段补强 — PASS

| 修正项 | 状态 | 证据 |
|--------|------|------|
| `evaluate()` 接收 `delivery_audit_event_present` 参数 | **Pass** | `delivery_gate_evidence.py` L243：参数签名包含三个 audit evidence 参数 |
| `evaluate()` 接收 `delivery_audit_event_type` 参数 | **Pass** | L244 |
| `evaluate()` 接收 `delivery_audit_event_ready` 参数 | **Pass** | L245 |
| `DeliveryGateEvidenceResult` 包含 `delivery_audit_event_present` 字段 | **Pass** | L122：`delivery_audit_event_present: bool \| None` |
| `DeliveryGateEvidenceResult` 包含 `delivery_audit_event_type` 字段 | **Pass** | L123 |
| `DeliveryGateEvidenceResult` 包含 `delivery_audit_event_ready` 字段 | **Pass** | L124 |
| G21 检查 audit evidence 三者同时满足 | **Pass** | L361–L367：`delivery_audit_event_present=True and event_type==collected and event_ready=True` |
| builder 自身不查数据库 | **Pass** | 文件头注释 L4–L7："does not … query audit repositories" |

### 1.3 P4-D2 WorkerRunResult / WorkerRunOnceResponse 透传 — PASS

文件：`runtime/orchestrator/app/workers/task_worker.py`（L286–L318 + L486–L540）

`WorkerRunResult` 新增 33 个 `delivery_gate_evidence_*` evidence 字段：

| 字段组 | 字段数 | 内容 |
|--------|--------|------|
| 基础状态 | 4 | `ready`、`source`、`reason_code`、`summary_cn` |
| 关联标识 | 4 | `session_id`、`project_id`、`task_id`、`run_id` |
| 工作区/操作信息 | 4 | `worktree_path`、`branch_name`、`proposed_operation`、`changed_files_count`、`changed_files` |
| 下一步动作 | 3 | `next_required_action`、`user_confirmation_required`、`human_approval_required` |
| 审计证据 | 3 | `delivery_audit_event_present`、`delivery_audit_event_type`、`delivery_audit_event_ready` |
| Gate 明细 | 2 | `satisfied_conditions`、`blocking_reasons` |
| 安全标志 | 12 | `runs_git`、`runs_write_git`、`git_add_triggered`、`git_commit_triggered`、`git_push_triggered`、`pr_opened`、`ci_triggered`、`execution_enabled`、`operation_applied`、`approval_granted`、`gate_allows_write`、`gate_allows_user_confirmation` |

文件：`runtime/orchestrator/app/api/routes/workers.py` → `WorkerRunOnceResponse` 完整透传所有 33 个 gate evidence 字段 + 32 个 operation dry-run 字段。

关键设计（`_delivery_gate_evidence_result_kwargs()`，L486–L540）：
- `result is None` → 返回空 dict（blocked/failed path 不写 gate fields）
- `result is not None` → 完整映射所有字段
- `safety_flags` 从 `result.safety_flags` 直接读取

### 1.4 P4-D2-R1 Audit Wrong Type / Not Ready Worker 测试补强 — PASS

| 测试用例 | 文件名 | 行号 | 状态 |
|---------|--------|------|------|
| success path gate ready (G1–G21 全部通过) | `test_worker_workspace_readonly_validation.py` | 门禁 ready 路径 | **Pass** |
| audit evidence wrong type → gate blocked | `test_worker_workspace_readonly_validation.py` | L1288 | **Pass** |
| audit evidence not ready → gate blocked | `test_worker_workspace_readonly_validation.py` | L1288（参数化） | **Pass** |
| blocked / failed path 不调用 gate builder | `test_worker_workspace_readonly_validation.py` | `_assert_delivery_gate_evidence_not_built()` L151 | **Pass** |
| builder test: ready (G1–G21) | `test_delivery_gate_evidence.py` | L113 | **Pass** |
| builder test: audit_evidence_missing (None) | `test_delivery_gate_evidence.py` | L152 | **Pass** |
| builder test: audit wrong type (failed event) | `test_delivery_gate_evidence.py` | L175 | **Pass** |
| builder test: audit not ready (ready=False) | `test_delivery_gate_evidence.py` | L193 | **Pass** |
| builder test: 14 blocked reason_code coverage | `test_delivery_gate_evidence.py` | L211 | **Pass** |
| safety flags: each forbidden flag rejected | `test_delivery_gate_evidence.py` | L351 | **Pass** |
| contract: ready + reason_code rejected | `test_delivery_gate_evidence.py` | L364 | **Pass** |
| forbidden copy check (no "代码已提交" etc.) | `test_delivery_gate_evidence.py` | L27–L38 | **Pass** |

### 1.5 P4-D Gate

| Gate | 结论 |
|------|------|
| P4-D1 DeliveryGateEvidenceBuilder | **Pass** |
| P4-D1-R1 audit evidence 输入参数 + 输出字段补强 | **Pass** |
| P4-D2 WorkerRunResult / WorkerRunOnceResponse 透传（33 字段） | **Pass** |
| P4-D2-R1 audit wrong type / not ready Worker 测试 | **Pass** |
| P4-D2-R1 blocked / failed path 不调用 gate builder 测试 | **Pass** |
| P4-D1 builder targeted tests（7 用例） | **Pass** |
| Delivery gate event 写入 | **Not started** |
| 前端 delivery gate evidence 展示 | **Not started** |
| Human approval API | **Not started** |
| git add / commit / push / PR | **Not started（正确）** |
| **P4-D Closure** | **Pass** |
| **AI Project Director 总闭环** | **Partial** |

---

## 2. 当前已完成的 P4 Evidence 链路

从 P4-B1 到 P4-D 的完整只读证据链路：

```
 1. GitDiffDryRunRunner.collect()               — 只读 git diff/status 采集 (P4-B1)
 2. WorkerRunResult git_diff_dry_run_*            — 28 字段 (P4-B2)
 3. WorkerRunOnceResponse API 透传               — (P4-B2)
 4. DeliveryEventBuilder                          — 规范化事件 (P4-B3)
 5. DeliveryEventAuditService                     — 写入 AgentMessage timeline (P4-B3)
 6. AgentMessage 持久化                          — (P4-B3)
 7. 前端 WorkerGitDiffDryRunEvidenceCard 只读展示 — (P4-E)
 8. 前端 AgentDeliveryDiffEventPanel 只读展示     — (P4-E)
 9. GitOperationDryRunBuilder                     — 提交预览构建 (P4-C1)
10. WorkerRunResult git_operation_dry_run_*       — 32 字段 (P4-C2)
11. WorkerRunOnceResponse API 透传               — (P4-C2)
12. DeliveryGateEvidenceBuilder                   — 交叉验证 G1–G21 (P4-D1)
13. WorkerRunResult delivery_gate_evidence_*      — 33 字段 (P4-D2)
14. WorkerRunOnceResponse API 透传               — (P4-D2)
```

**全链路安全边界**：

| 安全标志 | P4-B | P4-C | P4-D |
|---------|------|------|------|
| `runs_git` | True（只读 git diff） | False（纯计算） | False（纯计算） |
| `runs_write_git` | False | False | False |
| `git_add/commit/push_triggered` | False | False | False |
| `pr_opened` | False | False | False |
| `ci_triggered` | False | False | False |
| `execution_enabled` | False | False | False |
| `operation_applied` | N/A | False | False |
| `approval_granted` | N/A | False | False |
| `gate_allows_write` | N/A | N/A | **False** |
| `gate_allows_user_confirmation` | N/A | N/A | ready=True 时为 True |

---

## 3. 当前仍 Not started 清单

| # | 能力 | 说明 |
|---|------|------|
| 1 | 前端提交预览展示 | 无 git_operation_dry_run_* 面板 |
| 2 | 前端交付前检查展示 | 无 delivery_gate_evidence_* 面板 |
| 3 | Delivery gate event AgentMessage 写入 | 无 `delivery_gate_evaluated` / `delivery_gate_blocked` event |
| 4 | 前端 delivery gate event 展示 | AgentDeliveryDiffEventPanel 未扩展到 gate event |
| 5 | Human approval API | 无审批 API |
| 6 | git add | 未实现 |
| 7 | git commit | 未实现 |
| 8 | git push | 未实现 |
| 9 | PR 创建 | 未实现 |
| 10 | CI / review / merge | 未实现 |
| 11 | CleanupStack rollback | 未实现 |
| 12 | AI Project Director 总闭环 Pass | 仍为 Partial |

---

## 4. P4-E2 前端展示目标

### 4.1 展示范围

P4-E2 的目标是让用户在工作台页面**只读查看**本次 Worker 执行产生的两类新 evidence：

| 展示卡片 | 数据来源 | 当前状态 |
|---------|---------|---------|
| 代码改动预览 | `WorkerRunOnceResponse.git_diff_dry_run_*` | ✅ 已实现（P4-E） |
| **提交预览** | `WorkerRunOnceResponse.git_operation_dry_run_*` | ❌ 未实现（P4-E2 设计） |
| **交付前检查** | `WorkerRunOnceResponse.delivery_gate_evidence_*` | ❌ 未实现（P4-E2 设计） |

### 4.2 三段式展示流程

```
ManualRunResultSection / WorkerPoolResultSection
  │
  ├─ WorkerRuntimeLaunchGateEvidenceCard    ← 运行时门禁（P3-D4 已有）
  │
  ├─ WorkerGitDiffDryRunEvidenceCard        ← 代码改动预览（P4-E 已有）
  │    │  "检测到 3 个文件变更"
  │    │  safety_flags: 未执行提交或推送
  │
  ├─ WorkerGitOperationDryRunEvidenceCard   ← 提交预览（P4-E2 新增）
  │    │  "已生成提交预览：如果确认，将把 3 个文件提交到分支 X"
  │    │  "这是提交前预览，尚未加入待提交区、尚未生成本地提交、尚未推送"
  │    │  proposed_steps 展示
  │    │  safety_flags: 全部应为"否"
  │
  └─ WorkerDeliveryGateEvidenceCard         ← 交付前检查（P4-E2 新增）
       │  ready=true:  "交付前检查已通过，可以进入用户确认。仍未执行提交或推送。"
       │  ready=false: "交付前检查未通过" + blocking_reasons 列表
       │  satisfied_conditions / blocking_reasons 明细
       │  safety_flags: gate_allows_write="否", gate_allows_user_confirmation=是/否
```

### 4.3 前端接入策略

| 接入位置 | 当前已有 | P4-E2 新增 |
|---------|---------|-----------|
| `ManualRunResultSection.tsx` | `WorkerGitDiffDryRunEvidenceCard` (L116–L118) | `WorkerGitOperationDryRunEvidenceCard` + `WorkerDeliveryGateEvidenceCard` |
| `WorkerPoolResultSection.tsx` | `WorkerGitDiffDryRunEvidenceCard` (L52) | 同上两卡片 |

P4-E2 **不接 Agent timeline**——当前 delivery event 只有 `delivery_diff_dry_run_*` 三类，`delivery_gate_evaluated` / `delivery_gate_blocked` 尚未实现。P4-E2 重点是 Worker response evidence 的只读展示。

---

## 5. 建议新增组件

### 5.1 WorkerGitOperationDryRunEvidenceCard

- 位置：`apps/web/src/features/task-actions/WorkerGitOperationDryRunEvidenceCard.tsx`
- 参考：`WorkerGitDiffDryRunEvidenceCard.tsx` 的卡片 + safety flags 面板模式
- 数据源：`WorkerRunOnceResponse.git_operation_dry_run_*`
- 守卫：`git_operation_dry_run_ready !== null || git_operation_dry_run_reason_code !== null` 有值时渲染，否则 return null
- 语义分区标题：**提交预览**

### 5.2 WorkerDeliveryGateEvidenceCard

- 位置：`apps/web/src/features/task-actions/WorkerDeliveryGateEvidenceCard.tsx`
- 参考：`WorkerRuntimeLaunchGateEvidenceCard.tsx` 的门禁链展示模式（已通过/已阻断条件列表）
- 数据源：`WorkerRunOnceResponse.delivery_gate_evidence_*`
- 守卫：`delivery_gate_evidence_ready !== null || delivery_gate_evidence_reason_code !== null` 有值时渲染，否则 return null
- 语义分区标题：**交付前检查**

> 也可以建议合并为一个 `WorkerGitDeliveryGatewayCard`，但必须保持两个语义分区（提交预览 + 交付前检查），每个分区有独立标题和独立的免责声明。推荐两个独立组件以匹配 P4-E 已有的 `WorkerGitDiffDryRunEvidenceCard` 粒度。

---

## 6. 字段映射设计：git_operation_dry_run_*

### 6.1 前端应从 WorkerRunOnceResponse 读取的字段

| # | 字段 | 类型 | 中文标签 | 说明 |
|---|------|------|---------|------|
| 1 | `git_operation_dry_run_ready` | `boolean \| null` | 提交预览是否就绪 | true→是，false→否，null→未记录 |
| 2 | `git_operation_dry_run_source` | `string \| null` | 检测来源 | 映射中文 |
| 3 | `git_operation_dry_run_reason_code` | `string \| null` | 未就绪原因 | 映射中文 |
| 4 | `git_operation_dry_run_worktree_path` | `string \| null` | 检查工作区 | — |
| 5 | `git_operation_dry_run_branch_name` | `string \| null` | 目标分支 | — |
| 6 | `git_operation_dry_run_changed_files_count` | `number \| null` | 改动文件数量 | "X 个" |
| 7 | `git_operation_dry_run_changed_files` | `string[]` | 改动文件列表 | — |
| 8 | `git_operation_dry_run_added_files` | `string[]` | 新增文件 | — |
| 9 | `git_operation_dry_run_modified_files` | `string[]` | 修改文件 | — |
| 10 | `git_operation_dry_run_deleted_files` | `string[]` | 删除文件 | — |
| 11 | `git_operation_dry_run_renamed_files` | `string[]` | 重命名文件 | — |
| 12 | `git_operation_dry_run_proposed_operation` | `string \| null` | 提案操作 | "git_add_commit"→生成本地提交，"none"→无操作 |
| 13 | `git_operation_dry_run_proposed_steps` | `string[]` | 提案步骤 | 有序步骤列表 |
| 14 | `git_operation_dry_run_proposed_commit_message` | `string \| null` | 建议提交信息 | — |
| 15 | `git_operation_dry_run_user_confirmation_required` | `boolean \| null` | 需要用户确认 | 始终为"是" |
| 16 | `git_operation_dry_run_human_approval_required` | `boolean \| null` | 需要审批 | 始终为"是" |
| 17 | `git_operation_dry_run_feature_flag_required` | `boolean \| null` | 需要功能开关 | 始终为"是" |
| 18 | `git_operation_dry_run_summary_cn` | `string \| null` | 提交预览摘要 | 可直接展示 |
| 19 | `git_operation_dry_run_runs_git` | `boolean \| null` | 只读代码检查 | false→未执行 Git 检查 |
| 20 | `git_operation_dry_run_runs_write_git` | `boolean \| null` | 提交或推送等写操作 | false→未执行写操作 |
| 21 | `git_operation_dry_run_git_add_triggered` | `boolean \| null` | 加入待提交区 | false→未加入待提交区 |
| 22 | `git_operation_dry_run_git_commit_triggered` | `boolean \| null` | 生成本地提交 | false→未生成本地提交 |
| 23 | `git_operation_dry_run_git_push_triggered` | `boolean \| null` | 推送远程仓库 | false→未推送 |
| 24 | `git_operation_dry_run_pr_opened` | `boolean \| null` | 创建代码合并请求 | false→未创建 |
| 25 | `git_operation_dry_run_ci_triggered` | `boolean \| null` | 触发自动检查 | false→未触发 |
| 26 | `git_operation_dry_run_execution_enabled` | `boolean \| null` | 开启真实提交 | false→未开启 |
| 27 | `git_operation_dry_run_operation_applied` | `boolean \| null` | 已执行预览操作 | false→未执行 |
| 28 | `git_operation_dry_run_approval_granted` | `boolean \| null` | 用户已确认 | false→未确认 |

### 6.2 reason_code 中文化映射

| reason_code | 中文 |
|------------|------|
| `session_missing` | 会话信息缺失 |
| `worktree_unavailable` | 当前工作区不可用 |
| `diff_evidence_not_ready` | 代码改动预览未就绪 |
| `no_changes` | 当前没有可提交的代码改动 |
| `write_already_triggered` | 检测到写操作已触发 |
| `feature_flag_disabled` | 提交功能尚未开启 |
| `feature_flag_enabled` | 真实写入开关已开启，不支持预览模式 |

---

## 7. 字段映射设计：delivery_gate_evidence_*

### 7.1 前端应从 WorkerRunOnceResponse 读取的字段

| # | 字段 | 类型 | 中文标签 | 说明 |
|---|------|------|---------|------|
| 1 | `delivery_gate_evidence_ready` | `boolean \| null` | 交付前检查是否通过 | true→已通过，false→未通过，null→未记录 |
| 2 | `delivery_gate_evidence_source` | `string \| null` | 检测来源 | 映射中文 |
| 3 | `delivery_gate_evidence_reason_code` | `string \| null` | 阻断原因 | 映射中文（15 种） |
| 4 | `delivery_gate_evidence_worktree_path` | `string \| null` | 检查工作区 | — |
| 5 | `delivery_gate_evidence_branch_name` | `string \| null` | 目标分支 | — |
| 6 | `delivery_gate_evidence_proposed_operation` | `string \| null` | 提案操作 | "git_add_commit"→生成本地提交 |
| 7 | `delivery_gate_evidence_changed_files_count` | `number \| null` | 改动文件数量 | — |
| 8 | `delivery_gate_evidence_changed_files` | `string[]` | 改动文件列表 | — |
| 9 | `delivery_gate_evidence_next_required_action` | `string \| null` | 下一步动作 | await_user_confirmation→等待用户确认，resolve_blocking_conditions→需解决阻断条件 |
| 10 | `delivery_gate_evidence_user_confirmation_required` | `boolean \| null` | 需要用户确认 | ready=true 时为"是" |
| 11 | `delivery_gate_evidence_human_approval_required` | `boolean \| null` | 需要审批 | ready=true 时为"是" |
| 12 | `delivery_gate_evidence_delivery_audit_event_present` | `boolean \| null` | 交付审计记录存在 | true→存在 |
| 13 | `delivery_gate_evidence_delivery_audit_event_type` | `string \| null` | 审计事件类型 | delivery_diff_dry_run_collected→代码改动预览已完成 |
| 14 | `delivery_gate_evidence_delivery_audit_event_ready` | `boolean \| null` | 审计事件就绪 | true→是 |
| 15 | `delivery_gate_evidence_summary_cn` | `string \| null` | 交付前检查摘要 | 可直接展示 |
| 16 | `delivery_gate_evidence_satisfied_conditions` | `string[]` | 已满足条件 | G1–G21 子集 |
| 17 | `delivery_gate_evidence_blocking_reasons` | `string[]` | 阻断原因明细 | 格式 "Gx:reason_code" |
| 18 | `delivery_gate_evidence_runs_git` | `boolean \| null` | 只读代码检查 | false→未执行 Git 检查 |
| 19 | `delivery_gate_evidence_runs_write_git` | `boolean \| null` | 提交或推送等写操作 | false→未执行写操作 |
| 20 | `delivery_gate_evidence_git_add_triggered` | `boolean \| null` | 加入待提交区 | false→未加入 |
| 21 | `delivery_gate_evidence_git_commit_triggered` | `boolean \| null` | 生成本地提交 | false→未生成本地提交 |
| 22 | `delivery_gate_evidence_git_push_triggered` | `boolean \| null` | 推送远程仓库 | false→未推送 |
| 23 | `delivery_gate_evidence_pr_opened` | `boolean \| null` | 创建代码合并请求 | false→未创建 |
| 24 | `delivery_gate_evidence_ci_triggered` | `boolean \| null` | 触发自动检查 | false→未触发 |
| 25 | `delivery_gate_evidence_execution_enabled` | `boolean \| null` | 开启真实提交 | false→未开启 |
| 26 | `delivery_gate_evidence_operation_applied` | `boolean \| null` | 已执行预览操作 | false→未执行 |
| 27 | `delivery_gate_evidence_approval_granted` | `boolean \| null` | 用户已确认 | false→未确认 |
| 28 | `delivery_gate_evidence_gate_allows_write` | `boolean \| null` | 允许直接写入 | **始终为"否"** |
| 29 | `delivery_gate_evidence_gate_allows_user_confirmation` | `boolean \| null` | 可以进入用户确认 | ready=true 时为"是" |

### 7.2 delivery_gate_evidence_reason_code 中文化映射

| reason_code | 中文 |
|------------|------|
| `agent_session_missing` | 会话信息缺失 |
| `worktree_unavailable` | 当前工作区不可用 |
| `branch_missing` | 未绑定分支 |
| `workspace_not_clean` | 工作区状态不一致 |
| `diff_evidence_not_ready` | 代码改动预览未就绪 |
| `no_changes` | 当前没有可提交的代码改动 |
| `diff_write_flag_triggered` | diff 阶段写操作标志异常 |
| `operation_dry_run_not_ready` | 提交预览未就绪 |
| `unsupported_operation` | 操作类型不支持 |
| `operation_write_flag_triggered` | 操作预览写操作标志异常 |
| `operation_already_applied` | 操作已应用 |
| `approval_already_granted` | 审批已授予 |
| `feature_flag_enabled` | 真实写入开关已开启 |
| `evidence_mismatch` | 改动预览与提交预览不一致 |
| `audit_evidence_missing` | 缺少交付审计记录 |

---

## 8. Safety Flags 中文映射

所有 safety flags 在前端展示时必须使用以下中文映射：

| 字段 | true 中文 | false 中文 |
|------|----------|----------|
| `runs_git` | 已执行只读 Git 检查 | **未执行 Git 检查** |
| `runs_write_git` | 安全标记异常（红色警告） | **未执行提交或推送等写操作** |
| `git_add_triggered` | 安全标记异常（红色警告） | **未加入待提交区** |
| `git_commit_triggered` | 安全标记异常（红色警告） | **未生成本地提交** |
| `git_push_triggered` | 安全标记异常（红色警告） | **未推送到远程仓库** |
| `pr_opened` | 安全标记异常（红色警告） | **未创建代码合并请求** |
| `ci_triggered` | 安全标记异常（红色警告） | **未触发自动检查** |
| `execution_enabled` | 安全标记异常（红色警告） | **未开启真实提交** |
| `operation_applied` | 安全标记异常（红色警告） | **未执行提交预览中的操作** |
| `approval_granted` | 安全标记异常（红色警告） | **用户尚未确认** |
| `gate_allows_write` | 安全标记异常（红色警告） | **交付前检查不允许直接写入** |
| `gate_allows_user_confirmation` | **可以进入用户确认界面** | 不允许进入用户确认界面 |

**关键规则**：
- P4-E2 阶段所有写操作相关标志的预期值都是 `false`
- 如果任何写操作标志为 `true`，必须用红色 danger tone 展示 "安全标记异常"，而不是展示 true 对应的中文
- `runs_git` 例外——在 P4-C 和 P4-D 中它为 `false`（纯计算），在 P4-B 中为 `true`（已执行只读检查）
- `gate_allows_user_confirmation=true` 是 **唯一** 在 ready=True 时可为 true 的标志——展示为 "可以进入用户确认界面"（safe tone）

---

## 9. 用户可见中文规范

### 9.1 提交预览（git_operation_dry_run_*）推荐文案

| 场景 | 推荐中文文案 |
|------|------------|
| 卡片标题 | 提交预览 |
| 操作预览已生成 | 已生成提交预览：检测到 X 个文件变更。如果确认，将把这些文件提交到分支 Y。 |
| 操作预览无改动 | 当前没有可提交的代码改动。 |
| 工作区不可用 | 当前工作区不可用，无法生成提交预览。 |
| diff evidence 未就绪 | 代码改动预览未就绪，无法生成提交预览。 |
| 提交功能未开启 | 提交功能尚未开启。 |
| 写操作已触发 | 检测到写操作已触发，无法再次生成提交预览。 |
| 免责声明（每张卡片必须显示） | 这是提交前预览，尚未加入待提交区、尚未生成本地提交、尚未推送。需要用户确认后才能进入下一步。 |
| proposed_steps 标题 | 如果确认，将执行以下步骤： |
| proposed_commit_message 标签 | 建议提交信息 |

### 9.2 交付前检查（delivery_gate_evidence_*）推荐文案

| 场景 | 推荐中文文案 |
|------|------------|
| 卡片标题 | 交付前检查 |
| gate 通过 | 交付前检查已通过，可以进入用户确认。仍未执行提交或推送。 |
| gate 未通过 | 交付前检查未通过。 |
| 无改动 | 当前没有可提交的代码改动。 |
| 工作区不可用 | 当前工作区不可用。 |
| diff evidence 未就绪 | 代码改动预览未就绪。 |
| operation dry-run 未就绪 | 提交预览未就绪。 |
| 缺少审计记录 | 缺少交付审计记录。 |
| feature flag 已开启 | 真实写入开关已开启，不支持预览模式。 |
| 证据不一致 | 代码改动预览与提交预览不一致。 |
| 免责声明（每张卡片必须显示） | 这是交付前检查结果，不表示代码已被提交、推送或创建合并请求。需要用户确认后才能进入下一步。 |
| satisfied_conditions 标题 | 已满足条件（X/21） |
| blocking_reasons 标题 | 未满足条件 |
| next_required_action: await_user_confirmation | 等待用户确认 |
| next_required_action: resolve_blocking_conditions | 需要解决阻断条件 |

### 9.3 三段式总免责声明（可选）

如果 P4-E2 前端展示三段 evidence（改动预览 → 提交预览 → 交付前检查），可在交付前检查卡片底部增加总声明：

> 以上三段只读证据（代码改动预览、提交预览、交付前检查）均不表示代码已被提交、推送或创建合并请求。所有 Git 写操作（git add、git commit、git push、PR 创建）尚未执行。最终提交需要用户逐项确认。

---

## 10. 前端禁止文案

在功能未实现前，任何页面**严禁**显示以下文案：

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
| 可以提交代码 | 有误导——应说"可以进入用户确认界面" |
| 已允许提交 | approval 尚未实现 |
| 用户已确认 | approval 尚未实现 |
| 审批已通过 | approval 尚未实现 |

---

## 11. P4-E2 明确不做

| # | 不做 | 说明 |
|---|------|------|
| 1 | 不做确认按钮 | 无 "同意生成本地提交" / "同意推送并创建代码合并请求" / "驳回本次提交" 等按钮 |
| 2 | 不做 approval API | 不实现 human approval API |
| 3 | 不做 git add / commit / push | 不执行任何 Git 写操作 |
| 4 | 不做 PR 创建 | 不调 gh pr create 或 GitHub API |
| 5 | 不做 delivery gate event 写入 | 不实现 `delivery_gate_evaluated` / `delivery_gate_blocked` AgentMessage 写入 |
| 6 | 不接 CI / review / merge | — |
| 7 | 不改后端 API | 不修改 Python 代码 |
| 8 | 不改数据库 | 不新增表或字段 |
| 9 | 不把总闭环写成 Pass | AI Project Director 总闭环仍为 Partial |

---

## 12. 下一步 Codex 最小实现建议

### 12.1 实现范围

| # | 做什么 | 说明 |
|---|--------|------|
| 1 | 补前端类型 | 在 `apps/web/src/features/task-actions/types.ts` 的 `WorkerRunOnceResponse` 中新增 `git_operation_dry_run_*`（28 字段）和 `delivery_gate_evidence_*`（29 字段）的类型定义 |
| 2 | 新增 `WorkerGitOperationDryRunEvidenceCard` | 位置：`apps/web/src/features/task-actions/WorkerGitOperationDryRunEvidenceCard.tsx`；守卫：exists 检查；模式：参考 `WorkerGitDiffDryRunEvidenceCard` |
| 3 | 新增 `WorkerDeliveryGateEvidenceCard` | 位置：`apps/web/src/features/task-actions/WorkerDeliveryGateEvidenceCard.tsx`；守卫：exists 检查；模式：参考 `WorkerRuntimeLaunchGateEvidenceCard` 的门禁链展示 |
| 4 | 接入 `ManualRunResultSection` | 在 `WorkerGitDiffDryRunEvidenceCard` 之后依次渲染 `WorkerGitOperationDryRunEvidenceCard` + `WorkerDeliveryGateEvidenceCard` |
| 5 | 接入 `WorkerPoolResultSection` | 在每条 Worker result 的 `WorkerGitDiffDryRunEvidenceCard` 之后渲染两卡片 |
| 6 | npx tsc 类型检查 | 只跑 `npx tsc -p tsconfig.app.json --noEmit` |

### 12.2 不做什么

| # | 不做什么 | 说明 |
|---|---------|------|
| 1 | 不新增按钮 | 不新增 "同意提交" / "驳回" / "推送" / "创建 PR" 等按钮 |
| 2 | 不接后端 API | 不改 Python 代码 |
| 3 | 不修改 AgentDeliveryDiffEventPanel | 不扩展到 gate event |
| 4 | 不修改 AgentThreadControlGrid | 不在 Agent timeline 面板中新增 gate event 展示 |
| 5 | 不跑全量 pytest | 后端不变 |
| 6 | 不跑全量 build | 只跑 tsc --noEmit |
| 7 | 不跑 npm run build | — |

### 12.3 测试范围

```bash
# 只允许运行：
cd apps/web
npx tsc -p tsconfig.app.json --noEmit

# 禁止运行：
cd runtime/orchestrator && pytest  # 后端全量测试
cd apps/web && npm run build       # 前端全量 build
```

---

## Gate 结论

| Gate | 结论 |
|------|------|
| P4-D1 DeliveryGateEvidenceBuilder | **Pass** |
| P4-D1-R1 audit evidence 输入参数 + 输出字段补强 | **Pass** |
| P4-D2 WorkerRunResult / WorkerRunOnceResponse 透传（33 字段） | **Pass** |
| P4-D2-R1 audit wrong type / not ready Worker 测试 | **Pass** |
| P4-D2-R1 blocked / failed path 不调用 gate builder 测试 | **Pass** |
| P4-D1 builder targeted tests（7 用例） | **Pass** |
| Delivery gate event 写入 | **Not started** |
| git add / commit / push / PR | **Not started（正确）** |
| **P4-D Closure** | **Pass** |
| P4-E2 Frontend Operation/Gate Evidence Design | **Design only** |
| 前端提交预览展示 | **Not started** |
| 前端交付前检查展示 | **Not started** |
| Human approval API | **Not started** |
| git add / commit | **Not started** |
| git push / PR 创建 | **Not started** |
| CI / review / merge | **Not started** |
| CleanupStack rollback | **Not started** |
| **AI Project Director 总闭环** | **Partial** |

P4-D 完成了 Delivery Gate Evidence 从 Builder 域模型到 WorkerRunResult/WorkerRunOnceResponse 透传的完整闭环——`DeliveryGateEvidenceBuilder` G1–G21 条件逐条验证、`DeliveryGateEvidenceResult` 29 字段、WorkerRunResult 33 字段、WorkerRunOnceResponse API 透传、P4-D1-R1 audit evidence 参数合同修正、P4-D2-R1 audit wrong type / not ready Worker 测试、blocked/failed path 不调用 gate builder 测试。

P4-E2 定义了前端两段新 evidence 的只读展示设计——提交预览（28 字段映射 + 7 种 reason_code 中文化 + "这是提交前预览，尚未加入待提交区、尚未生成本地提交、尚未推送" 免责声明）和交付前检查（29 字段映射 + 15 种 reason_code 中文化 + "交付前检查已通过，可以进入用户确认。仍未执行提交或推送。" 免责声明）。前端禁止文案从 10 条扩充到 14 条。下一步 Codex 只补前端类型 + 两个新卡片组件 + 接入 ManualRunResultSection/WorkerPoolResultSection，不新增任何按钮、不执行任何 Git 写操作。

AI Project Director 总闭环仍为 **Partial**——在所有 Git 写操作实现并通过证据验证之前，不能标记为 Pass。
