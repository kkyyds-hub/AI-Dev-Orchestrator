# Coding Session Git Delivery Lifecycle P4-E2 收口 + P4-F Human Approval Gate 设计

> **文档类型**: P4-E2 前端只读展示收口审计 + P4-F Human Approval Gate 设计
> **生成日期**: 2026-06-06
> **基准 commit**: `503b67e85fbe876e812fcf7cd7ccbbda7411c84c`
> **前置文档**:
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4d-closure-and-p4e2-frontend-operation-gate-design-20260606.md`
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4c-closure-and-p4d-delivery-gate-design-20260606.md`
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4b3-closure-and-p4e-frontend-design-20260606.md`
> **边界**: 仅文档收口与设计；不改 Python 代码、不改 TypeScript 代码、不改 API schema、不改数据库 schema、不运行全量测试、不启动服务、不实现产品运行时 `git add` / `git commit` / `git push` / PR
> **状态**: P4-E2 Closure: Pass；P4-F Design: Design only；AI Project Director 总闭环 Partial

---

## 0. 本轮范围

本轮只完成两件事：

1. 收口 P4-E2 前端只读展示现状。
2. 设计 P4-F Human Approval Gate，作为后续真实 Git 写入 guardrail 与 feature flag 之前的人工确认关口。

本轮明确不做：

| 项目 | 状态 |
|------|------|
| 业务代码改动 | 不做 |
| 前端组件改动 | 不做 |
| API schema 改动 | 不做 |
| 数据库 schema / migration 改动 | 不做 |
| TaskWorker 行为改动 | 不做 |
| AgentMessage 写入逻辑改动 | 不做 |
| 产品运行时 Git 写操作 | 不做 |
| 全量测试 / 全量 build | 不做 |

---

## 1. P4-E2 前端只读展示收口

### 1.1 已完成能力

P4-E2 已把 P4-C / P4-D 后端只读 evidence 透传结果接入前端展示：

| 能力 | 文件 | 状态 |
|------|------|------|
| `WorkerRunOnceResponse` 类型补齐 `git_operation_dry_run_*` 字段 | `apps/web/src/features/task-actions/types.ts` | Pass |
| `WorkerRunOnceResponse` 类型补齐 `delivery_gate_evidence_*` 字段 | `apps/web/src/features/task-actions/types.ts` | Pass |
| 提交预览卡片 | `apps/web/src/features/task-actions/WorkerGitOperationDryRunPreviewCard.tsx` | Pass |
| 交付前检查卡片 | `apps/web/src/features/task-actions/WorkerDeliveryGateEvidenceCard.tsx` | Pass |
| 手动执行结果区接入 | `apps/web/src/app/sections/ManualRunResultSection.tsx` | Pass |
| Worker Pool 结果区接入 | `apps/web/src/app/sections/WorkerPoolResultSection.tsx` | Pass |

### 1.2 只读边界

P4-E2 的 UI 只展示后端已有 evidence，不产生新的交付行为：

- 不新增确认按钮。
- 不触发 API 写入。
- 不写 AgentMessage。
- 不执行 `git add`。
- 不执行 `git commit`。
- 不执行 `git push`。
- 不创建 PR。
- 不触发 CI。
- 不改变 TaskWorker executor 阻断行为。

### 1.3 提交预览展示摘要

`WorkerGitOperationDryRunPreviewCard` 展示以下信息：

| 展示组 | 代表字段 |
|--------|----------|
| 就绪状态 | `git_operation_dry_run_ready`、`git_operation_dry_run_reason_code`、`git_operation_dry_run_summary_cn` |
| 工作区信息 | `git_operation_dry_run_worktree_path`、`git_operation_dry_run_branch_name` |
| 变更信息 | `git_operation_dry_run_changed_files_count`、`git_operation_dry_run_changed_files`、`added/modified/deleted/renamed_files` |
| 预览动作 | `git_operation_dry_run_proposed_operation`、`git_operation_dry_run_proposed_steps`、`git_operation_dry_run_proposed_commit_message` |
| 确认要求 | `user_confirmation_required`、`human_approval_required`、`feature_flag_required` |
| 安全标记 | `runs_git`、`runs_write_git`、`git_add_triggered`、`git_commit_triggered`、`git_push_triggered`、`pr_opened`、`ci_triggered`、`execution_enabled`、`operation_applied`、`approval_granted` |

### 1.4 交付前检查展示摘要

`WorkerDeliveryGateEvidenceCard` 展示以下信息：

| 展示组 | 代表字段 |
|--------|----------|
| Gate 状态 | `delivery_gate_evidence_ready`、`reason_code`、`summary_cn`、`next_required_action` |
| 工作区与操作 | `worktree_path`、`branch_name`、`proposed_operation`、`changed_files_count`、`changed_files` |
| 审计证据 | `delivery_audit_event_present`、`delivery_audit_event_type`、`delivery_audit_event_ready` |
| 条件明细 | `satisfied_conditions`、`blocking_reasons` |
| 确认要求 | `user_confirmation_required`、`human_approval_required` |
| 安全标记 | `runs_git`、`runs_write_git`、`git_add_triggered`、`git_commit_triggered`、`git_push_triggered`、`pr_opened`、`ci_triggered`、`execution_enabled`、`operation_applied`、`approval_granted`、`gate_allows_write`、`gate_allows_user_confirmation` |

### 1.5 P4-E2-R1 中文文案收口

P4-E2-R1 已将用户可见中文文案收敛为安全、明确、不会误导用户认为写操作已发生的表达：

| 场景 | 当前规范 |
|------|----------|
| `runs_git=false` | 表达为未执行 Git 检查 |
| `approval_granted=false` | 表达为用户尚未确认 |
| `approval_already_granted` reason | 表达为用户确认状态异常 |
| 真实写入状态 | 使用“未加入待提交区 / 未生成本地提交 / 未推送远程仓库 / 未创建代码合并请求”等否定事实 |
| Gate ready | 表达为可进入用户确认界面，不表达为已授权写仓库 |

### 1.6 P4-E2 Gate

| Gate | 结论 |
|------|------|
| WorkerRunOnceResponse 类型补齐 | Pass |
| 提交预览只读展示 | Pass |
| 交付前检查只读展示 | Pass |
| ManualRunResultSection 接入 | Pass |
| WorkerPoolResultSection 接入 | Pass |
| 中文文案 R1 修正 | Pass |
| 新增按钮 | 未发生 |
| 后端改动 | 未发生 |
| API schema 改动 | 未发生 |
| 数据库 schema 改动 | 未发生 |
| 产品运行时 Git 写操作 | 未发生 |
| **P4-E2 Closure** | **Pass** |

---

## 2. P4-F Human Approval Gate 设计目标

P4-F 的目标不是执行真实 Git 写入，而是建立一个明确、可审计、可测试的人类确认门禁：

> 只有当 Delivery Gate Evidence 已证明“可以进入用户确认界面”，且用户通过明确动作确认后，系统才生成只读 approval evidence，供后续阶段继续检查。P4-F 自身仍不得执行 Git 写入。

P4-F 位于当前链路之后：

```text
P4-B 只读 diff evidence
  → P4-C operation dry-run preview
  → P4-D delivery gate evidence
  → P4-E2 frontend read-only display
  → P4-F human approval gate evidence
  → 后续真实 Git 写入 guardrail + feature flag 阶段
```

---

## 3. P4-F 非目标

P4-F 不包含以下能力：

| 能力 | P4-F 状态 |
|------|-----------|
| 执行 `git add` | 不包含 |
| 执行 `git commit` | 不包含 |
| 执行 `git push` | 不包含 |
| 创建 PR | 不包含 |
| 触发 CI | 不包含 |
| 自动合并 | 不包含 |
| 后台静默审批 | 不允许 |
| 无 evidence 时放行 | 不允许 |
| 前端按钮直接触发 Git 写入 | 不允许 |

---

## 4. Human Approval Gate 输入条件

建议 P4-F 域模型命名：

- `HumanApprovalGateBuilder`
- `HumanApprovalGateResult`
- `HumanApprovalGateSafetyFlags`

`HumanApprovalGateBuilder.evaluate()` 的输入应只来自已存在的只读 evidence 与用户明确确认事实：

| 输入 | 类型 | 说明 |
|------|------|------|
| `agent_session` | `AgentSession | None` | 当前 Agent 会话 |
| `operation_dry_run` | `GitOperationDryRunResult | None` | P4-C 提交预览 evidence |
| `delivery_gate_evidence` | `DeliveryGateEvidenceResult | None` | P4-D 交付前检查 evidence |
| `approval_requested_action` | `str | None` | 用户确认的目标动作，P4-F 仅允许 `approve_git_add_commit_preview` |
| `approval_confirmation_text` | `str | None` | 用户确认文案或确认 token，必须能证明用户是显式确认 |
| `approval_actor_id` | `str | None` | 发起确认的用户 ID |
| `approval_actor_display_name` | `str | None` | 展示用操作者名称 |
| `approval_client_request_id` | `str | None` | 前端确认请求 ID，用于幂等与追踪 |
| `approval_created_at` | `datetime | None` | 用户确认发生时间 |
| `delivery_git_write_enabled` | `bool` | 真实写入 feature flag；P4-F 阶段必须为 False |
| `expected_changed_files` | `list[str] | None` | 前端展示给用户并被确认的文件列表 |
| `expected_proposed_commit_message` | `str | None` | 前端展示给用户并被确认的提交说明 |

### 4.1 输入合同原则

1. `delivery_gate_evidence.ready` 必须为 `True`。
2. `delivery_gate_evidence.gate_allows_user_confirmation` 必须为 `True`。
3. `delivery_gate_evidence.gate_allows_write` 必须为 `False`。
4. `operation_dry_run.ready` 必须为 `True`。
5. `operation_dry_run.proposed_operation` 必须为 `git_add_commit`。
6. `operation_dry_run.operation_applied` 必须为 `False`。
7. `operation_dry_run.approval_granted` 必须为 `False`。
8. `delivery_git_write_enabled` 必须为 `False`。
9. 用户确认必须包含明确 actor、动作、请求 ID、确认时间。
10. 用户确认的文件列表和提交说明必须与 evidence 一致。

---

## 5. Human Approval Gate 输出字段

建议 `HumanApprovalGateResult` 输出以下字段，并在后续接入 Worker / API 时以 `human_approval_gate_*` 前缀透传。

### 5.1 基础字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `ready` | `bool` | 是否已形成有效用户确认 evidence |
| `source` | `str` | 固定为 `human_approval_gate` |
| `reason_code` | `str | None` | 阻断原因；ready=True 时必须为 None |
| `summary_cn` | `str` | 用户可见中文摘要 |
| `session_id` | `str | None` | 会话 ID |
| `project_id` | `str | None` | 项目 ID |
| `task_id` | `str | None` | 任务 ID |
| `run_id` | `str | None` | Worker run ID |

### 5.2 确认字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `approval_required` | `bool` | 是否需要用户确认；P4-F ready 前后均应为 True |
| `approval_granted` | `bool` | 用户是否已明确确认；P4-F ready=True 时为 True |
| `approval_actor_id` | `str | None` | 确认用户 ID |
| `approval_actor_display_name` | `str | None` | 确认用户展示名 |
| `approval_requested_action` | `str | None` | 被确认动作 |
| `approval_client_request_id` | `str | None` | 前端请求 ID |
| `approval_created_at` | `datetime | None` | 确认时间 |
| `approval_confirmation_fingerprint` | `str | None` | 对确认文本、文件列表、提交说明形成的摘要，不保存敏感长文本 |

### 5.3 Evidence 对齐字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `operation_dry_run_ready` | `bool | None` | P4-C ready 状态 |
| `delivery_gate_evidence_ready` | `bool | None` | P4-D ready 状态 |
| `delivery_gate_allows_user_confirmation` | `bool | None` | 是否允许进入确认界面 |
| `delivery_gate_allows_write` | `bool | None` | 必须为 False |
| `proposed_operation` | `str | None` | 预览动作 |
| `proposed_commit_message` | `str | None` | 被确认的提交说明 |
| `changed_files_count` | `int | None` | 被确认的文件数量 |
| `changed_files` | `list[str]` | 被确认的文件列表 |
| `satisfied_conditions` | `list[str]` | 已满足条件 |
| `blocking_reasons` | `list[str]` | 未满足条件 |

---

## 6. Safety Flags 设计

建议 `HumanApprovalGateSafetyFlags` 字段：

| 字段 | P4-F 允许值 | 说明 |
|------|-------------|------|
| `runs_git` | False | P4-F 纯验证，不执行 Git |
| `runs_write_git` | False | 不执行写 Git |
| `git_add_triggered` | False | 不加入待提交区 |
| `git_commit_triggered` | False | 不生成本地提交 |
| `git_push_triggered` | False | 不推送 |
| `pr_opened` | False | 不创建 PR |
| `ci_triggered` | False | 不触发 CI |
| `execution_enabled` | False | 不开启真实执行 |
| `operation_applied` | False | 预览动作未应用 |
| `approval_granted` | True only when ready=True | 仅表示用户已确认，不表示已写仓库 |
| `gate_allows_write` | False | P4-F 不授权写仓库 |
| `gate_allows_next_guardrail` | True only when ready=True | 仅允许进入下一阶段 guardrail |

强制校验：

- 以下字段任意为 True 必须拒绝构造：`runs_git`、`runs_write_git`、`git_add_triggered`、`git_commit_triggered`、`git_push_triggered`、`pr_opened`、`ci_triggered`、`execution_enabled`、`operation_applied`、`gate_allows_write`。
- `approval_granted=True` 仅允许在 `ready=True`、所有输入条件通过时出现。
- `gate_allows_next_guardrail=True` 仅允许在 `ready=True` 时出现。

---

## 7. 建议阻断 reason_code 清单

| reason_code | 中文摘要 | 触发条件 |
|-------------|----------|----------|
| `agent_session_missing` | 会话信息缺失 | `agent_session is None` |
| `operation_dry_run_missing` | 提交预览缺失 | `operation_dry_run is None` |
| `operation_dry_run_not_ready` | 提交预览未就绪 | `operation_dry_run.ready is not True` |
| `delivery_gate_evidence_missing` | 交付前检查缺失 | `delivery_gate_evidence is None` |
| `delivery_gate_not_ready` | 交付前检查未通过 | `delivery_gate_evidence.ready is not True` |
| `user_confirmation_not_allowed` | 当前不能进入用户确认 | `gate_allows_user_confirmation is not True` |
| `write_gate_unexpectedly_enabled` | 检测到写入授权异常 | `gate_allows_write is True` 或 `delivery_git_write_enabled is True` |
| `unsupported_approval_action` | 用户确认动作不受支持 | `approval_requested_action` 不是允许值 |
| `approval_actor_missing` | 缺少确认用户 | `approval_actor_id` 缺失 |
| `approval_request_id_missing` | 缺少确认请求编号 | `approval_client_request_id` 缺失 |
| `approval_timestamp_missing` | 缺少确认时间 | `approval_created_at` 缺失 |
| `approval_confirmation_missing` | 缺少明确确认内容 | `approval_confirmation_text` 缺失或不满足确认规则 |
| `changed_files_mismatch` | 用户确认的文件列表与证据不一致 | `expected_changed_files` 与 evidence 不一致 |
| `commit_message_mismatch` | 用户确认的提交说明与证据不一致 | `expected_proposed_commit_message` 与 evidence 不一致 |
| `write_already_triggered` | 检测到写操作标记异常 | 输入 evidence 或 safety flags 显示已有写操作 |
| `approval_already_recorded` | 已存在同一确认记录 | 幂等请求重复且已有成功记录 |

---

## 8. 用户可见中文规范

P4-F 用户可见文案必须遵守：

1. 明确说明“用户确认”只表示进入下一阶段检查，不表示代码已经写入仓库。
2. 明确说明当前仍未执行 Git 写操作。
3. 避免使用会让用户误解为已经完成提交、推送或 PR 的表达。
4. reason 文案聚焦状态，不责备用户。
5. ready=True 时建议展示：`用户已确认提交预览，可进入下一阶段写入前安全检查。当前仍未写入仓库。`
6. ready=False 时建议展示：`尚不能确认提交预览，请先完成交付前检查。当前未写入仓库。`

建议按钮附近说明：

```text
确认后不会立即提交代码。系统只会记录你的确认，并进入下一阶段写入前安全检查。
```

---

## 9. 前端确认按钮边界

P4-F 后续最小前端实现可以新增一个按钮，但按钮必须满足以下边界：

| 边界 | 规则 |
|------|------|
| 显示条件 | `delivery_gate_evidence_ready=True` 且 `gate_allows_user_confirmation=True` |
| 禁用条件 | evidence 缺失、gate 未通过、文件列表不一致、API 请求进行中 |
| 按钮文案 | 建议为“确认提交预览” |
| 按钮说明 | 明确确认后不会立即执行 Git 写入 |
| 触发 API | 只调用 approval evidence API，不调用 Git 写入 API |
| 成功反馈 | 表达为“已记录用户确认，可进入下一阶段检查” |
| 失败反馈 | 展示 reason_code 的中文摘要 |
| 二次确认 | 建议要求用户确认文件数量、文件列表和提交说明 |

按钮不得：

- 直接执行 Git 命令。
- 直接触发 Worker 真实写入。
- 直接创建 PR。
- 将 `gate_allows_write` 改为 True。
- 在 evidence 缺失时可点击。

---

## 10. Event / Audit 边界

P4-F 建议新增单独的 approval audit event，但 event 仍只记录确认事实，不记录 Git 写入事实。

### 10.1 推荐 event_type

| event_type | 说明 |
|------------|------|
| `human_approval_gate_ready` | 用户确认 evidence 已就绪 |
| `human_approval_gate_blocked` | 用户确认 gate 被阻断 |

### 10.2 AgentMessage 写入边界

后续实现时可选择写 AgentMessage，但必须满足：

- `role=SYSTEM`
- `message_type=TIMELINE`
- `event_type` 仅使用 P4-F approval event 类型
- `content_summary` 使用安全中文摘要
- `content_detail` 只包含 evidence 字段、actor、request_id、fingerprint、reason_code
- 不写入完整敏感确认文本
- 不写入任何声称 Git 已写入的内容

### 10.3 与 Delivery Gate event 的关系

- P4-D 的 delivery gate evidence 表示“前置证据满足，可进入用户确认界面”。
- P4-F 的 approval evidence 表示“用户已确认，可进入下一阶段写入前 guardrail”。
- 二者都不表示真实 Git 写入已经发生。

---

## 11. 下一步 Codex 最小实现建议

建议下一轮拆成 P4-F1 / P4-F2 / P4-F3，避免一次性把按钮、API、审计、真实写入混在一起。

### 11.1 P4-F1：纯域模型 + 窄范围单元测试

只实现：

- `runtime/orchestrator/app/domain/human_approval_gate.py`
- `HumanApprovalGateSafetyFlags`
- `HumanApprovalGateResult`
- `HumanApprovalGateBuilder.evaluate()`
- `runtime/orchestrator/tests/test_human_approval_gate.py`

禁止：

- 接 Worker。
- 接 API。
- 写 AgentMessage。
- 改前端。
- 执行 Git 写操作。

测试覆盖：

- ready=True 条件。
- gate evidence missing。
- gate not ready。
- operation preview missing / not ready。
- unsupported approval action。
- actor missing。
- confirmation missing。
- changed files mismatch。
- commit message mismatch。
- forbidden safety flags 强制校验。
- ready=True 时 `gate_allows_next_guardrail=True` 且 `gate_allows_write=False`。

### 11.2 P4-F2：后端只读透传

只做：

- TaskWorker 成功路径中基于 P4-C/P4-D evidence 与用户确认记录生成 `human_approval_gate_*` 字段。
- WorkerRunResult / WorkerRunOnceResponse 透传。
- blocked / failed path 保持 None。

禁止：

- 改 executor 阻断行为。
- 写 Git。
- 创建 PR。

### 11.3 P4-F3：前端确认入口

只做：

- 在 `WorkerDeliveryGateEvidenceCard` 附近展示“确认提交预览”入口。
- 调用只记录 approval evidence 的 API。
- 成功后展示 approval evidence。

禁止：

- 按钮直接触发 Git 写入。
- 按钮直接触发 PR。
- 文案暗示已经写仓库。

---

## 12. 总 Gate 结论

| Gate | 结论 |
|------|------|
| P4-E2 Closure | Pass |
| P4-F Human Approval Gate Design | Pass |
| 是否改代码 | 否 |
| 是否改前端 | 否 |
| 是否运行全量测试 | 否 |
| 产品运行时是否实现 Git 写操作 | 否 |
| AI Project Director 总闭环 | Partial |
