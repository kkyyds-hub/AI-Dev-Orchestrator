# Coding Session Git Delivery Lifecycle P4-F2-D Approval Audit / AgentMessage 设计

> **文档类型**: P4-F2-D 审计事件设计文档（仅设计，不实现）  
> **生成日期**: 2026-06-07  
> **远端基准**: `origin/main` = `3f1ac55397aa8b9c09f82db4855bb0bf35acbfcb`  
> **主产品基线**: `docs/product/ai-project-director/page-information-architecture-20260518.md`  
> **路线文档**: `docs/product/ai-project-director/p1-p7参考规划复用说明书.md`  
> **前置文档**:  
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4f2c-closure-20260607.md`  
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4f2c0-closure-20260607.md`  
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4f2b-human-approval-api-design-20260606.md`  
> **参考项目**: ComposioHQ Agent Orchestrator — `packages/core/src/activity-events.ts`（结构化 event 类型、best-effort 写入、source 分类）  
> **边界**: 本轮只做审计事件设计；不改 Python 代码、不改测试、不改前端、不改数据库 / migration、不写 AgentMessage、不实现审计事件。  
> **状态**: P4-F2-D Design: Complete；P4-F2-D Implementation: Not started；P4-F3: Not started；AI Project Director 总闭环: Partial

---

## 0. 阶段定位

P4-F2-D 只设计 approval audit / AgentMessage 事件。目标是让 P4-F2-C 产生的"用户确认记录已生成"结果变成可审计、可查询、可展示的持久化事件。

### 0.1 核心语义

```text
P4-F2-D 记录的是"用户确认记录已生成"这一事实。
它不是"审批已通过"，不是"已授权写入"，不是"代码已提交"。
它只是用户确认了提交预览，允许进入下一阶段写入前安全检查。
当前仍未写入仓库。
```

### 0.2 本阶段范围

| 项目 | 状态 |
|------|------|
| event_type 定义 | 本轮完成 |
| AgentMessage payload 字段设计 | 本轮完成 |
| 写入时机设计 | 本轮完成 |
| 幂等策略设计 | 本轮完成 |
| 中文文案设计 | 本轮完成 |
| P4-F2-D 实现任务摘要 | 本轮完成 |

### 0.3 本阶段明确不做

| 项目 | 状态 |
|------|------|
| 写入 AgentMessage | 不做（P4-F2-D Implementation） |
| 修改 approval API | 不做 |
| 修改数据库 / migration | 不做 |
| 前端展示审计事件 | 不做（P4-F3） |
| 产品运行时 Git 写操作 | 不做 |

---

## 1. 输入来源

### 1.1 数据来源

P4-F2-D 审计事件的唯一输入来源是 P4-F2-C `DeliveryHumanApprovalResponse`（`POST /approvals/delivery-human-approval` 的返回值）。

### 1.2 写入条件

只有在以下条件**全部满足**时才写入审计事件：

| # | 条件 | 来源字段 |
|---|------|---------|
| 1 | `ready is True` | `DeliveryHumanApprovalResponse.ready` |
| 2 | `approval_granted is True` | `DeliveryHumanApprovalResponse.approval_granted` |
| 3 | `gate_allows_next_guardrail is True` | `DeliveryHumanApprovalResponse.safety_flags["gate_allows_next_guardrail"]` |
| 4 | `gate_allows_write is False` | `DeliveryHumanApprovalResponse.safety_flags["gate_allows_write"]` |
| 5 | `approval_applied is False` | `DeliveryHumanApprovalResponse.approval_applied` |

### 1.3 不写入的情况

| 场景 | 写入行为 |
|------|---------|
| `ready=False`（任何阻断原因） | **不写** "确认记录已生成"事件 |
| snapshot 缺失 / 无效（HTTP 409） | **不写** |
| run 不存在（HTTP 404） | **不写** |

> 注：blocked audit event（如 `delivery_human_approval_blocked`）可在后续子阶段单独设计，不纳入 P4-F2-D 最小实现范围。

### 1.4 不读取/不保存的数据

| 数据 | 规则 |
|------|------|
| `approval_confirmation_text` 原文 | **不读取、不保存、不回显**。只使用 `approval_confirmation_fingerprint`（SHA-256） |
| 前端传来的 actor | **不信任**。`approved_by` 由后端 actor seam 决定 |
| 完整 diff 内容 | **不保存**。不写入文件变更的具体内容 |

---

## 2. 建议 Event Type

### 2.1 event_type

```text
delivery_human_approval_recorded
```

### 2.2 命名说明

| 要素 | 说明 |
|------|------|
| 前缀 `delivery_human_approval` | 与现有 `delivery_evidence_snapshot` event、`delivery_human_approval` source 保持一致 |
| 后缀 `recorded` | 表达"已记录确认事实"，不表达"已审批/已通过/已授权" |
| 参考 AO 命名风格 | AO 使用 `domain.action` 模式（如 `session.spawned`、`runtime.lost_detected`） |

### 2.3 明确不是以下含义

| 禁止理解 | 正确理解 |
|---------|---------|
| 审批已通过 | 用户确认记录已生成 |
| 已授权写入 | gate_allows_write=False |
| 代码已提交 | git_commit_triggered=False |

---

## 3. AgentMessage Payload 字段设计

### 3.1 域模型字段

`AgentMessage` 域模型（`runtime/orchestrator/app/domain/agent_message.py`）已有以下字段。本设计指定 P4-F2-D 写入时的填充值：

| 域模型字段 | 填充值 | 说明 |
|-----------|--------|------|
| `id` | 自动生成 UUID | — |
| `session_id` | `DeliveryHumanApprovalResponse.session_id` | AgentSession ID |
| `project_id` | `DeliveryHumanApprovalResponse.project_id` | Project ID |
| `task_id` | `DeliveryHumanApprovalResponse.task_id` | Task ID |
| `run_id` | `DeliveryHumanApprovalResponse.run_id` | Run ID |
| `sequence_no` | 通过 `AgentMessageRepository` 自动分配 | 当前仓库实现中 repository 无自动 sequence_no，实现时需处理 |
| `role` | `AgentMessageRole.SYSTEM` | 系统级审计事件 |
| `message_type` | `AgentMessageType.TIMELINE` | 时间线事件 |
| `event_type` | `"delivery_human_approval_recorded"` | 固定 event type |
| `phase` | `None` | 不使用 |
| `state_from` | `None` | 不使用 |
| `state_to` | `None` | 不使用 |
| `intervention_type` | `None` | 不使用 |
| `note_event_type` | `None` | 不使用 |
| `context_checkpoint_id` | `None` | 不使用 |
| `context_rehydrated` | `None` | 不使用 |

### 3.2 `content_summary`（安全中文摘要）

```text
用户确认记录已生成，可进入下一阶段写入前安全检查。当前仍未执行提交或推送。
```

### 3.3 `content_detail`（结构化 JSON）

`content_detail` 用于存储审计所需的结构化字段（JSON 字符串）。以下为建议 payload：

```json
{
  "event_type": "delivery_human_approval_recorded",
  "approval_id": "hap_<uuid5>",
  "approved_by": "local_user",
  "approved_by_display_name": "本地用户",
  "approval_scope": "git_add_commit_preview",
  "approval_requested_action": "approve_git_add_commit_preview",
  "approval_client_request_id": "client-request-1",
  "approval_created_at": "2026-06-07T08:00:00Z",
  "approval_expires_at": "2026-06-07T09:00:00Z",
  "approval_applied": false,
  "approval_revoked": false,
  "approval_confirmation_fingerprint": "<sha256-hex>",
  "proposed_operation": "git_add_commit",
  "proposed_commit_message": "fix: stabilize delivery evidence",
  "changed_files_count": 1,
  "changed_files": ["runtime/orchestrator/app/api/routes/approvals.py"],
  "satisfied_conditions": ["H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9", "H10", "H11", "H12", "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20", "H21", "H22"],
  "evidence_snapshot_event": "delivery_evidence_snapshot",
  "evidence_snapshot_schema_version": "p4f2c0.v1",
  "gate_allows_next_guardrail": true,
  "gate_allows_write": false,
  "git_add_triggered": false,
  "git_commit_triggered": false,
  "git_push_triggered": false,
  "pr_opened": false,
  "ci_triggered": false,
  "runs_write_git": false,
  "execution_enabled": false,
  "operation_applied": false
}
```

### 3.4 必须包含的字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `event_type` | `str` | `"delivery_human_approval_recorded"` |
| `approval_id` | `str` | 确认记录唯一 ID |
| `approved_by` | `str` | 后端决定的确认人 ID |
| `approved_by_display_name` | `str` | 展示用名称 |
| `approval_scope` | `str` | `"git_add_commit_preview"` |
| `approval_requested_action` | `str` | `"approve_git_add_commit_preview"` |
| `approval_client_request_id` | `str` | 前端请求 ID（幂等键） |
| `approval_created_at` | `str` | UTC ISO 8601 |
| `approval_expires_at` | `str` | UTC ISO 8601 |
| `approval_applied` | `bool` | 必须为 `false` |
| `approval_revoked` | `bool` | 必须为 `false` |
| `approval_confirmation_fingerprint` | `str` | SHA-256 hex（不含原文） |
| `proposed_operation` | `str` | `"git_add_commit"` |
| `proposed_commit_message` | `str` | 被确认的提交说明 |
| `changed_files_count` | `int` | 变更文件数量 |
| `changed_files` | `list[str]` | 被确认的文件列表 |
| `evidence_snapshot_event` | `str` | `"delivery_evidence_snapshot"` — 溯源用 |
| `evidence_snapshot_schema_version` | `str` | `"p4f2c0.v1"` — 溯源用 |
| `gate_allows_next_guardrail` | `bool` | 必须为 `true` |
| `gate_allows_write` | `bool` | 必须为 `false` |
| `git_add_triggered` | `bool` | 必须为 `false` |
| `git_commit_triggered` | `bool` | 必须为 `false` |
| `git_push_triggered` | `bool` | 必须为 `false` |
| `pr_opened` | `bool` | 必须为 `false` |
| `ci_triggered` | `bool` | 必须为 `false` |

### 3.5 严禁包含的数据

| 禁止字段 | 原因 |
|---------|------|
| `approval_confirmation_text` 原文 | 敏感用户输入不可落库 |
| token / secret / credential | 安全 |
| 完整 diff 内容 | 可事后从仓库获取 |
| 任何"已提交 / 已推送 / PR 已创建 / 审批已通过 / 已授权写入 / 交付完成" | 不属于 P4-F 阶段事实 |

---

## 4. 用户可见中文文案

### 4.1 允许文案

以下中文文案可以出现在 `content_summary`、response、或前端展示中：

| # | 文案 |
|---|------|
| 1 | 用户确认记录已生成 |
| 2 | 用户已确认进入下一阶段安全检查 |
| 3 | 这只是确认进入下一阶段，尚未执行提交或推送 |
| 4 | 尚未执行提交或推送 |
| 5 | 仍未执行提交或推送 |
| 6 | 当前仍未写入仓库 |
| 7 | 可进入下一阶段写入前安全检查 |

### 4.2 禁止文案

以下中文文案在 P4-F 全阶段绝对不得出现：

```text
代码已提交
代码已推送
合并请求已创建
自动提交成功
AI 已完成交付
交付完成
PR 已准备
提交成功
推送成功
可合并
可以提交代码
审批已通过
已完成审批
已授权写入
已执行提交
已执行推送
```

### 4.3 参考：AO 的 activity event 文案风格

AO 的 `activity-events.ts` 中的 event kind 使用 `domain.action_result` 命名（如 `session.spawned`、`runtime.lost_detected`、`reaction.escalated`），不包含暗示"已完成交付"或"已授权写入"的表达。P4-F2-D 遵循同样原则：event 命名只描述事实，不提前声称未发生的状态。

---

## 5. 写入时机设计

### 5.1 建议实现方式

后续 P4-F2-D Implementation 在 approval API handler（`evaluate_delivery_human_approval`）的成功路径中直接写入 AgentMessage：

```text
POST /approvals/delivery-human-approval
  ↓
1. 前置校验（run/log_path/snapshot/contract）
  ↓ 全部通过
2. HumanApprovalGateBuilder.evaluate(...)
  ↓ 返回 result
3. DeliveryHumanApprovalResponse.from_gate_result(...)
  ↓ 如果 result.ready is True:
4.   AgentMessageRepository.create(
      role=SYSTEM,
      message_type=TIMELINE,
      event_type="delivery_human_approval_recorded",
      content_summary="用户确认记录已生成，可进入下一阶段写入前安全检查。当前仍未执行提交或推送。",
      content_detail=<结构化 JSON>,
      ...
    )
5. 返回 response
```

### 5.2 不写的场景

| 场景 | 行为 |
|------|------|
| `result.ready is False` | 不写 "recorded" 事件 |
| HTTP 404 / 409 | 不写任何事件 |

### 5.3 关于 blocked audit event

`delivery_human_approval_blocked` 事件的设计（记录"用户确认被阻断"的事实）可在后续子阶段（如 P4-F2-D-R1）单独考虑。P4-F2-D 最小实现只覆盖 `ready=True` 的成功审计事件。

参考 AO 的 activity event 设计，AO 同时记录 `session.spawned`（成功）和 `session.spawn_failed`（失败）。本项目的 blocked audit event 可作为后续子阶段做类似扩展。

---

## 6. 幂等设计

### 6.1 幂等键

`approval_client_request_id` 是前端生成的唯一请求 ID。同一个 `run_id` + `approval_client_request_id` 不应重复生成多条确认事件。

### 6.2 当前约束

当前 `AgentMessageTable` (`runtime/orchestrator/app/core/db_tables.py`) 在 `session_id`、`project_id`、`task_id`、`run_id` 上有索引，但没有 `(run_id, event_type, approval_client_request_id)` 唯一约束。

### 6.3 设计建议（不做 DB migration）

P4-F2-D Implementation 阶段建议采用**查询后写入**的低成本幂等策略：

```text
写入前检查：
1. 通过 AgentMessageRepository 查询：
   - session_id = response.session_id
   - event_type = "delivery_human_approval_recorded"
   - content_detail 中包含相同的 approval_client_request_id
2. 如果已存在 → 跳过写入（幂等）
3. 如果不存在 → 写入新事件
```

此策略避免新增 DB migration，且不要求唯一约束。后续如果需要严格幂等，可在独立 migration 阶段添加唯一索引。

### 6.4 幂等规则

| 场景 | 行为 |
|------|------|
| 相同 run_id + 相同 `approval_client_request_id` + 已有 recorded 事件 | 跳过写入，仍返回 200（幂等） |
| 相同 run_id + 不同 `approval_client_request_id` + 此前已有 recorded 事件 | 已有 recorded 事件的 `approval_applied` 是否为 False？如果 False，应考虑是否覆盖或拒绝。最小实现可先允许写入新事件，由 `HumanApprovalGateBuilder` 的 `approval_already_applied` 校验在前置层拦截 |
| 相同 run_id + 相同 `approval_client_request_id` + changed_files 已变化 | `HumanApprovalGateBuilder` 会因 `changed_files_mismatch` 返回 ready=False，不会进入写入路径 |

---

## 7. 与后续阶段的关系

| 后续阶段 | 依赖 P4-F2-D | 说明 |
|---------|-------------|------|
| P4-F3 前端确认入口 | 是 | 前端需要从 AgentMessage / timeline 读取 "delivery_human_approval_recorded" 事件来展示"用户确认记录已生成" |
| P4-F4 Human Approval E2E Closure | 是 | E2E 验证需要 audit event 作为证据链的一环 |
| P5 Failure Recovery | 否 | 不依赖 P4-F2-D |
| P6 Agent Orchestration | 否 | 不直接依赖 |

### 7.1 P4-F3 前端展示约束

当 P4-F3 实现前端确认入口时，必须遵守以下约束：

| 展示内容 | 来源 |
|---------|------|
| 确认状态 | `content_summary`："用户确认记录已生成，可进入下一阶段写入前安全检查。当前仍未执行提交或推送。" |
| 确认编号 | `content_detail.approval_id` |
| 确认人 | `content_detail.approved_by_display_name` |
| 确认范围 | `content_detail.approval_scope` |
| 确认时间 | `content_detail.approval_created_at` |
| 有效期 | `content_detail.approval_expires_at` |
| 不可展示 | "审批通过 / 可以提交代码 / 已授权写入" |

---

## 8. 测试设计

### 8.1 P4-F2-D Implementation 阶段最小测试

建议测试文件：`runtime/orchestrator/tests/test_delivery_human_approval_audit.py`

| # | 测试 | 预期 |
|---|------|------|
| 1 | ready=True 时写入一条 AgentMessage | `event_type == "delivery_human_approval_recorded"`，`role == SYSTEM`，`message_type == TIMELINE` |
| 2 | payload 不含 `confirmation_text` 原文 | `content_detail` 中无确认文本原文 |
| 3 | payload 所有 Git write flag 为 `false` | `git_commit_triggered=False`，`git_push_triggered=False` 等 |
| 4 | `gate_allows_write=False` | payload 中确认 |
| 5 | `approval_applied=False` | payload 中确认 |
| 6 | blocked result 不写 "recorded" 事件 | 查询 AgentMessage 无 `delivery_human_approval_recorded` 事件 |
| 7 | 重复 `approval_client_request_id` 不重复写入 | 查询 AgentMessage 仅有 1 条 |
| 8 | approval API 原有 7 个测试仍通过 | `test_delivery_human_approval_api.py` 全 Pass |

### 8.2 测试复用策略

| 改动范围 | 最小测试命令 |
|---------|------------|
| 只改 approval audit / AgentMessage 写入 | `pytest tests/test_delivery_human_approval_audit.py tests/test_delivery_human_approval_api.py -q` |
| 改 approval API handler + audit | 同上 |
| 改 AgentMessageRepository / 域模型 | `pytest tests/test_delivery_human_approval_audit.py tests/test_delivery_human_approval_api.py -q` |

**不需要跑** Worker、P4-C/P4-D builder、snapshot source 测试，除非改到对应模块。

---

## 9. 参考：AgentMessage 现有写入模式

为保证 P4-F2-D 实现时风格一致，以下列出当前 AgentMessage 的现有写入模式：

### 9.1 现有 SYSTEM + TIMELINE 事件示例

来自 `runtime/orchestrator/app/services/agent_conversation_service.py`（第 94–95 行）：

```python
role=AgentMessageRole.SYSTEM,
message_type=AgentMessageType.TIMELINE,
```

现有 `SYSTEM` + `TIMELINE` 事件包括：`session_started`、`execution_started`、`execution_outcome`、`session_finalized`、`workspace_preflight_failed` 等。

### 9.2 content_summary 长度限制

`AgentMessage.content_summary` 的 `max_length=2_000`，建议 `content_summary` 的中文摘要远小于此限制（当前建议约 40 字）。

### 9.3 content_detail 长度限制

`AgentMessage.content_detail` 的 `max_length=4_000`，建议结构化 JSON 不超过此限制。如果 `satisfied_conditions` 列表过长（22 项全部），JSON 序列化可能接近 4KB 边界。实现时需注意截断策略：

- 如果接近 4KB，可省略 `satisfied_conditions` 细项（H1-H22），只在 `content_detail` 中保留 `satisfied_conditions_count` 和 `blocking_reasons_count`（ready=True 时两者分别为 22 和 0）。

### 9.4 sequence_no 处理

当前 `AgentMessageRepository.create()` 接受 `sequence_no` 作为参数但不自动生成。P4-F2-D 实现时需先查询 `session_id` 下的最大 `sequence_no`，然后 +1。

---

## 10. P4-F2-D Implementation 最小实现任务摘要

以下摘要供下一阶段 Codex 实施。

### 10.1 允许实现

| # | 任务 | 位置 |
|---|------|------|
| 1 | 在 `evaluate_delivery_human_approval` handler 的成功路径（`result.ready is True` 后，return response 前）写入 AgentMessage | `runtime/orchestrator/app/api/routes/approvals.py` |
| 2 | 构造 `content_detail` JSON（包含第 3.4 节所有必须字段） | 同上 |
| 3 | 设置 `content_summary` 为安全中文文案 | 同上 |
| 4 | 实现幂等检查（查询已有 `delivery_human_approval_recorded` 事件） | 同上或独立 helper |
| 5 | 新增 `test_delivery_human_approval_audit.py`（8 个测试，见第 8.1 节） | `runtime/orchestrator/tests/` |

### 10.2 禁止实现

| # | 禁止 | 原因 |
|---|------|------|
| 1 | 写入 `confirmation_text` 原文 | 敏感数据不可落库 |
| 2 | 写入 `gate_allows_write=True` | 永不为 True |
| 3 | DB migration | P4-F2-D 最小实现不需要 |
| 4 | blocked audit event | 不在最小范围 |
| 5 | 前端展示 | 属于 P4-F3 |

---

## 11. Gate 结论

| Gate | 结论 | 证据 |
|------|------|------|
| `origin/main` HEAD 确认 | Pass | `3f1ac55397aa8b9c09f82db4855bb0bf35acbfcb` |
| Event type 设计 | Pass | `delivery_human_approval_recorded` |
| AgentMessage payload 字段设计 | Pass | 25 字段，全部来自 `DeliveryHumanApprovalResponse` |
| 中文文案审计 | Pass | 7 条允许 + 15 条禁止 |
| 幂等策略设计 | Pass | 查询后写入，基于 `approval_client_request_id` |
| 测试设计 | Pass | 8 个测试场景 |
| `confirmation_text` 不落库 | Pass | 仅 `fingerprint` |
| `gate_allows_write=False` 硬性要求 | Pass | 全部字段断言 |
| 是否改代码 | Pass | 否 |
| 是否改测试 | Pass | 否 |
| 是否改前端 | Pass | 否 |
| 是否改数据库 | Pass | 否 |
| 是否写 AgentMessage | Pass | 否 |
| **P4-F2-D Design** | **Complete** | — |
| P4-F2-D Implementation | Not started | — |
| P4-F3 前端确认入口 | Not started | — |
| 产品运行时 git add / commit / push / PR | Not started | — |
| **AI Project Director 总闭环** | **Partial** | P7 完成前不得写 Pass |

---

## 12. 本轮收口声明

| 声明 | 结论 |
|------|------|
| 是否修改 Python 业务代码 | 否 |
| 是否修改测试代码 | 否 |
| 是否修改前端 | 否 |
| 是否修改数据库 / migration | 否 |
| 是否修改 API | 否 |
| 是否写 AgentMessage | 否 |
| 是否实现确认按钮 | 否 |
| 是否实现产品运行时 Git 写操作 | 否 |
| 是否只新增 P4-F2-D design 文档 | 是 |

开发流程中的文档提交不代表 AI-Dev-Orchestrator 产品运行时具备 Git 写操作能力。
