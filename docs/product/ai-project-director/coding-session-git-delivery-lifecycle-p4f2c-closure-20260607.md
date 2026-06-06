# Coding Session Git Delivery Lifecycle P4-F2-C Delivery Human Approval API 收口

> **文档类型**: P4-F2-C 阶段收口审计 + Gate 证据  
> **生成日期**: 2026-06-07  
> **远端基准**: `origin/main` = `4dabb0c279a5f8161143556debd83cbc7aa1dd57`  
> **P4-F2-C 实现 commits**:  
> - `e9a6275` feat: add P4-F2C delivery human approval API  
> - `0d1f1fd` fix: harden P4-F2C delivery approval API  
> - `4dabb0c` fix: align P4-F2C approval actor seam  
> **路线文档**: `docs/product/ai-project-director/p1-p7参考规划复用说明书.md`  
> **前置 closure 文档**:  
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4f2b-human-approval-api-design-20260606.md`  
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4f2c0-closure-20260607.md`  
> **边界**: 本轮只做 P4-F2-C 收口复核与文档回填；不改 Python 代码、不改前端、不改数据库 / migration、不写 AgentMessage、不实现确认按钮、不实现产品运行时 Git 写操作。  
> **状态**: P4-F2-C Closure: Pass；P4-F2-D: Not started；P4-F3: Not started；AI Project Director 总闭环: Partial

---

## 0. 阶段定位

P4-F2-C 实现最小 approval API。该 API 接收用户显式确认事实，从 P4-F2-C0 run log snapshot 读取 P4-C/P4-D evidence，调用 `HumanApprovalGateBuilder.evaluate()`，返回 `DeliveryHumanApprovalResult`。API 不执行任何 Git 写操作、不写 AgentMessage、不改前端。

### 0.1 本阶段范围

| 项目 | 状态 |
|------|------|
| `POST /approvals/delivery-human-approval` endpoint | Pass |
| `DeliveryHumanApprovalRequest` schema | Pass |
| `DeliveryHumanApprovalResponse` schema | Pass |
| snapshot 读取 + 校验 | Pass |
| `HumanApprovalGateBuilder.evaluate()` 调用 | Pass |
| Actor seam（临时本地用户） | Pass |
| Targeted tests | Pass |

### 0.2 本阶段明确不做

| 项目 | 状态 |
|------|------|
| 前端确认按钮 | 不做（P4-F3） |
| AgentMessage 写入 | 不做（P4-F2-D） |
| 数据库持久化 | 不做 |
| 产品运行时 Git 写操作 | 不做 |
| 真实 auth seam | P4-F2-C 使用临时本地用户占位 |

---

## 1. 基准提交

| 项目 | 值 |
|------|-----|
| 当前 `origin/main` hash | `4dabb0c279a5f8161143556debd83cbc7aa1dd57` |
| 当前 `origin/main` commit message | `fix: align P4-F2C approval actor seam` |
| P4-F2-C feat commit | `e9a6275` feat: add P4-F2C delivery human approval API |
| P4-F2-C harden commit | `0d1f1fd` fix: harden P4-F2C delivery approval API |
| P4-F2-C actor seam commit | `4dabb0c` fix: align P4-F2C approval actor seam |

---

## 2. API Endpoint

### 2.1 路由

```text
POST /approvals/delivery-human-approval
```

文件：`runtime/orchestrator/app/api/routes/approvals.py`（第 1807–1810 行）

```python
@router.post(
    "/delivery-human-approval",
    response_model=DeliveryHumanApprovalResponse,
    summary="Evaluate the P4-F2-C delivery human approval gate",
)
```

### 2.2 路径选择

放在 `/approvals` 路由前缀下，因为 human approval 在语义上属于审批域。区别于 `/approvals/{approval_id}/actions`（boss approval decision），`/approvals/delivery-human-approval` 是独立的 human approval gate 评估端点。

---

## 3. Request Schema

### 3.1 `DeliveryHumanApprovalRequest`

文件：`runtime/orchestrator/app/api/routes/approvals.py`（第 985–1007 行）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `run_id` | `UUID` | 是 | 关联的 Worker run ID |
| `approval_requested_action` | `str` | 是（默认 `approve_git_add_commit_preview`） | P4-F 仅允许此值 |
| `approval_scope` | `str` | 是（默认 `git_add_commit_preview`） | P4-F 仅允许此值 |
| `approval_confirmation_text` | `str` | 是（max 2000） | 用户显式确认文案 |
| `approval_client_request_id` | `str` | 是（max 200） | 前端生成，幂等去重键 |
| `approval_expires_at` | `datetime` | 是 | 确认过期时间（UTC） |
| `expected_changed_files` | `list[str]` | 是（max 500 items） | 用户确认的文件列表 |
| `expected_proposed_commit_message` | `str` | 是（max 200） | 用户确认的提交说明 |

### 3.2 关键设计决策

| 决策 | 说明 |
|------|------|
| **不包含 `approval_actor_id`** | 前端不能伪造确认人身份 |
| **不包含 `approval_actor_display_name`** | 展示名由后端决定 |
| **`approval_confirmation_text` 不保存、不回显** | 只用于生成 `approval_confirmation_fingerprint`（SHA-256），response 中不返回原文 |

---

## 4. Response Schema

### 4.1 `DeliveryHumanApprovalResponse`

文件：`runtime/orchestrator/app/api/routes/approvals.py`（第 1010–1114 行）

| 字段分组 | 字段 | 类型 |
|---------|------|------|
| Gate 状态 | `ready` | `bool` |
| Gate 状态 | `reason_code` | `str \| None` |
| Gate 状态 | `summary_cn` | `str` |
| Gate 状态 | `source` | `str`（固定 `delivery_human_approval`） |
| 会话标识 | `run_id` | `UUID` |
| 会话标识 | `task_id` | `str` |
| 会话标识 | `project_id` | `str` |
| 会话标识 | `session_id` | `str` |
| 审批状态 | `approval_required` | `bool` |
| 审批状态 | `approval_granted` | `bool` |
| 审批状态 | `approval_id` | `str \| None` |
| 审批状态 | `approved_by` | `str \| None` |
| 审批状态 | `approved_by_display_name` | `str \| None` |
| 审批状态 | `approval_scope` | `str \| None` |
| 审批状态 | `approval_requested_action` | `str \| None` |
| 审批状态 | `approval_client_request_id` | `str \| None` |
| 审批状态 | `approval_created_at` | `datetime \| None` |
| 审批状态 | `approval_expires_at` | `datetime \| None` |
| 审批状态 | `approval_applied` | `bool` |
| 审批状态 | `approval_revoked` | `bool` |
| 审批状态 | `approval_confirmation_fingerprint` | `str \| None` |
| Evidence 对齐 | `operation_dry_run_ready` 等 4 字段 | `bool \| None` |
| 操作预览 | `proposed_operation`, `proposed_commit_message`, `changed_files_count`, `changed_files` | — |
| 条件与阻塞 | `satisfied_conditions`, `blocking_reasons` | `list[str]` |
| 安全标志 | `safety_flags` | `dict[str, Any]`（`HumanApprovalGateSafetyFlags.model_dump(mode="json")`） |
| Evidence 溯源 | `evidence_snapshot_event` | `str`（固定 `delivery_evidence_snapshot`） |
| Evidence 溯源 | `evidence_snapshot_log_path` | `str` |
| Evidence 溯源 | `evidence_snapshot_schema_version` | `str \| None` |
| Evidence 溯源 | `evidence_snapshot_source` | `str \| None` |

### 4.2 关键响应语义

| ready 值 | 语义 |
|----------|------|
| `True` | 用户确认记录已生成，可进入下一阶段写入前安全检查。当前仍未写入仓库。 |
| `False` | 当前不满足用户确认条件。`reason_code` 指明具体阻断原因。 |
| 所有情况 | `gate_allows_write=False`, `approval_applied=False`, 所有 Git write flag=False |

---

## 5. Actor Seam

### 5.1 当前实现

文件：`runtime/orchestrator/app/api/routes/approvals.py`（第 109–110 行）

```python
DELIVERY_HUMAN_APPROVAL_API_ACTOR_ID = "local_user"
DELIVERY_HUMAN_APPROVAL_API_ACTOR_DISPLAY_NAME = "本地用户"
```

| 字段 | 值 | 说明 |
|------|-----|------|
| `approved_by` | `"local_user"` | 临时后端占位值 |
| `approved_by_display_name` | `"本地用户"` | 临时后端占位值 |

### 5.2 安全设计

| 规则 | 实现 |
|------|------|
| Request body 不包含 `approval_actor_id` | ✅ `DeliveryHumanApprovalRequest` 无此字段 |
| Request body 不包含 `approval_actor_display_name` | ✅ `DeliveryHumanApprovalRequest` 无此字段 |
| Actor 由后端决定，不信任前端 | ✅ API handler 直接使用常量 |
| 测试验证 request 中注入的 actor 被忽略 | ✅ test 传入 `approval_actor_id="untrusted-request-actor"` 在 response 中未出现 |

### 5.3 后续演进

当系统引入真实 auth seam 后，替换这两行常量即可，无需修改 API 合约。

---

## 6. Evidence 来源

### 6.1 数据流

```text
1. API handler 接收 run_id
2. RunRepository.get_by_id(run_id) → 获取 run.log_path
3. RunLoggingService.read_latest_delivery_evidence_snapshot(log_path=run.log_path)
   → snapshot (RunLogEvent)
4. _delivery_human_approval_snapshot_invalid_reason(snapshot.data)
   → 6 项 contract 校验
5. snapshot.data["operation_dry_run"] → P4-C evidence
6. snapshot.data["delivery_gate_evidence"] → P4-D evidence
7. AgentSessionRepository.get_by_run_id(run_id) → agent_session
8. HumanApprovalGateBuilder.evaluate(...) → DeliveryHumanApprovalResult
9. DeliveryHumanApprovalResponse.from_gate_result(...) → API response
```

### 6.2 不做什么

| 禁止 | 代码证据 |
|------|---------|
| 不重扫 Git | API 只从 snapshot 读取 |
| 不信任前端 evidence | `expected_changed_files` 和 `expected_proposed_commit_message` 与 snapshot evidence 对比校验 |
| 不重新生成 P4-C/P4-D evidence | `operation_dry_run` 和 `delivery_gate_evidence` 直接从 snapshot 反序列化 |

---

## 7. 安全校验

### 7.1 前置校验（返回 HTTP 错误）

| # | 校验 | 失败响应 |
|---|------|---------|
| 1 | `run` 存在 | HTTP 404 |
| 2 | `run.log_path` 存在 | HTTP 409 |
| 3 | snapshot 存在（`read_latest_delivery_evidence_snapshot` 非 None） | HTTP 409 |
| 4 | snapshot contract 有效（6 项校验全通过） | HTTP 409 |

### 7.2 Snapshot Contract 校验

文件：`runtime/orchestrator/app/api/routes/approvals.py`（第 1888–1908 行）

```python
def _delivery_human_approval_snapshot_invalid_reason(snapshot_data) -> str | None:
```

| # | 校验项 | 失败 reason |
|---|--------|------------|
| 1 | `schema_version == "p4f2c0.v1"` | `schema_version_mismatch` |
| 2 | `snapshot_source == "run_log_jsonl"` | `snapshot_source_mismatch` |
| 3 | `operation_dry_run_available is True` | `operation_dry_run_unavailable` |
| 4 | `delivery_gate_evidence_available is True` | `delivery_gate_evidence_unavailable` |
| 5 | `operation_dry_run` is `dict` | `operation_dry_run_payload_invalid` |
| 6 | `delivery_gate_evidence` is `dict` | `delivery_gate_evidence_payload_invalid` |

### 7.3 Gate 级校验（返回 ready=False，HTTP 200）

由 `HumanApprovalGateBuilder.evaluate()` 内部执行（22 项 H1–H22 校验，详见 P4-F1 closure 文档）。

关键校验结果：

| 校验 | ready=True 时 | ready=False 时 |
|------|-------------|---------------|
| `gate_allows_write` | `False` | `False` |
| `approval_applied` | `False` | — |
| `approval_granted` | `True` | `False` |
| `gate_allows_next_guardrail` | `True` | `False` |
| 所有 Git write flag | `False` | — |

---

## 8. 测试证据

### 8.1 测试文件

`runtime/orchestrator/tests/test_delivery_human_approval_api.py`

### 8.2 测试命令与结果

```bash
cd runtime/orchestrator
python -m pytest tests/test_delivery_human_approval_api.py -q
```

结果（P4-F2-C 实现阶段记录）：

```text
7 passed in <1s
```

### 8.3 相邻 targeted regression

```bash
cd runtime/orchestrator
python -m pytest tests/test_delivery_human_approval_api.py \
  tests/test_run_logging_service_delivery_evidence_snapshot.py \
  tests/test_worker_workspace_readonly_validation.py \
  tests/test_human_approval_gate.py \
  tests/test_git_operation_dry_run.py \
  tests/test_delivery_gate_evidence.py -q
```

结果：

```text
85 passed, 4 warnings in <2s
```

### 8.4 测试覆盖清单

| # | 测试 | 覆盖 | 状态 |
|---|------|------|------|
| 1 | `test_delivery_human_approval_api_actor_seam_constants_are_local_user` | Actor 常量值验证 | Pass |
| 2 | `test_delivery_human_approval_api_evaluates_snapshot_without_persisting_confirmation` | Happy path: ready=True、actor seam、confirmation_text 不回显、request actor 被忽略、ApprovalRequestTable/ApprovalDecisionTable/AgentMessageTable 为 0 | Pass |
| 3 | `test_delivery_human_approval_api_blocks_when_snapshot_missing` | Snapshot 缺失 → HTTP 409 | Pass |
| 4 | `test_delivery_human_approval_api_rejects_invalid_snapshot_contract` | Schema version 不匹配 → HTTP 409 | Pass |
| 5 | `test_delivery_human_approval_api_returns_blocked_when_agent_session_missing` | AgentSession 缺失 → ready=False, reason_code=agent_session_missing | Pass |
| 6 | `test_delivery_human_approval_api_returns_blocked_on_changed_files_mismatch` | changed_files 不一致 → ready=False | Pass |
| 7 | `test_delivery_human_approval_api_returns_blocked_on_commit_message_mismatch` | commit_message 不一致 → ready=False | Pass |

### 8.5 关键断言覆盖

| 断言 | 测试覆盖 |
|------|---------|
| Actor seam `approved_by="local_user"` | ✅ #1, #2, #5, #6, #7 |
| Actor seam `approved_by_display_name="本地用户"` | ✅ #1, #2 |
| 前端注入的 actor 被忽略 | ✅ #2（`untrusted-request-actor` 不在 response 中） |
| `confirmation_text` 不保存不回显 | ✅ #2（原文不在 response text 中） |
| `gate_allows_write=False` | ✅ #2 |
| `gate_allows_next_guardrail=True` (ready=True) | ✅ #2 |
| `gate_allows_next_guardrail=False` (ready=False) | ✅ #5, #6, #7 |
| 所有 Git write flag=False | ✅ #2 |
| `approval_applied=False` | ✅ #2 |
| `approval_granted=True` (ready=True) | ✅ #2 |
| `approval_granted=False` (ready=False) | ✅ #5, #6, #7 |
| `ApprovalRequestTable` 为 0 | ✅ #2, #3, #4, #5 |
| `ApprovalDecisionTable` 为 0 | ✅ #2, #3, #4, #5 |
| `AgentMessageTable` 为 0 | ✅ #2, #3, #4, #5 |
| Snapshot 缺失 → 409 | ✅ #3 |
| Snapshot 无效 → 409 | ✅ #4 |
| Snapshot 溯源字段在 response 中 | ✅ #2 |
| `satisfied_conditions` / `blocking_reasons` 正确 | ✅ #5, #6, #7 |

---

## 9. 测试复用策略

为避免每轮都跑全量测试（增加模型 token 成本与执行时间），后续阶段建议采用以下最小测试策略：

| 改动范围 | 最小测试命令 |
|---------|------------|
| 只改 approval API（routes/approvals.py 的 delivery-human-approval 部分） | `pytest tests/test_delivery_human_approval_api.py -q` |
| 改 snapshot source（run_logging_service.py 的 snapshot 相关） | `pytest tests/test_delivery_human_approval_api.py tests/test_run_logging_service_delivery_evidence_snapshot.py -q` |
| 改 Worker（task_worker.py） | `pytest tests/test_worker_workspace_readonly_validation.py tests/test_delivery_human_approval_api.py tests/test_run_logging_service_delivery_evidence_snapshot.py -q` |
| 改 P4-C/P4-D builder | `pytest tests/test_git_operation_dry_run.py tests/test_delivery_gate_evidence.py tests/test_human_approval_gate.py -q` |
| **全量 targeted regression**（closure 阶段） | `pytest tests/test_delivery_human_approval_api.py tests/test_run_logging_service_delivery_evidence_snapshot.py tests/test_worker_workspace_readonly_validation.py tests/test_human_approval_gate.py tests/test_git_operation_dry_run.py tests/test_delivery_gate_evidence.py -q` |

**不要求每轮都跑全量测试。**

---

## 10. 当前 Not started 清单

| # | 能力 | 状态 | 计划阶段 |
|---|------|------|---------|
| 1 | P4-F2-D Approval Audit / AgentMessage | Not started | P4-F2-D |
| 2 | P4-F3 前端确认入口 | Not started | P4-F3 |
| 3 | P4-F4 Human Approval E2E Closure | Not started | P4-F4 |
| 4 | P5 Failure Recovery / 失败回流 | Not started | P5 |
| 5 | P6 Agent Orchestration / AI 主管调度 | Not started | P6 |
| 6 | P7 Project Director Conversation Hub + Governance | Not started | P7 |
| 7 | 产品运行时 `git add` | Not started | 后续真实写入阶段 |
| 8 | 产品运行时 `git commit` | Not started | 后续真实写入阶段 |
| 9 | 产品运行时 `git push` | Not started | 后续真实写入阶段 |
| 10 | PR 创建 / merge / CI | Not started | 后续真实写入阶段 |
| 11 | AI Project Director 总闭环 Pass | Not started | P7 完成后 |

---

## 11. Gate 结论

| Gate | 结论 | 证据 |
|------|------|------|
| `origin/main` HEAD 为 P4-F2-C actor seam commit | Pass | `4dabb0c279a5f8161143556debd83cbc7aa1dd57` |
| API endpoint 存在 | Pass | `POST /approvals/delivery-human-approval` |
| Request schema 不含 actor 字段 | Pass | `DeliveryHumanApprovalRequest` 无 `approval_actor_id` / `approval_actor_display_name` |
| Actor seam 为临时本地用户 | Pass | `approved_by="local_user"`, `approved_by_display_name="本地用户"` |
| Evidence 来源为 P4-F2-C0 snapshot | Pass | `read_latest_delivery_evidence_snapshot()` → 6 项 contract 校验 |
| Snapshot 缺失 → HTTP 409 | Pass | 测试覆盖 |
| Snapshot 无效 → HTTP 409 | Pass | 测试覆盖 |
| `confirmation_text` 不保存不回显 | Pass | 测试断言原文不在 response text 中 |
| 前端 actor 注入被忽略 | Pass | 测试断言 `untrusted-request-actor` 不在 response text 中 |
| `gate_allows_write=False` | Pass | 全测试覆盖 |
| `approval_applied=False` | Pass | 全测试覆盖 |
| 所有 Git write flag=False | Pass | 全测试覆盖 |
| ApprovalRequestTable / ApprovalDecisionTable / AgentMessageTable 为 0 | Pass | 全测试覆盖 |
| Targeted tests 通过 | Pass | 7 passed（单文件）；85 passed（全 targeted regression） |
| 未改前端 | Pass | 无前端文件变更 |
| 未写 AgentMessage | Pass | 无 AgentMessage 写入 |
| 未改数据库 | Pass | 无 migration |
| 未实现产品运行时 Git 写操作 | Pass | 所有 write flag=False |
| **P4-F2-C Closure** | **Pass** | — |
| P4-F2-D Approval Audit / AgentMessage | Not started | — |
| P4-F3 前端确认入口 | Not started | — |
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
| 是否只新增 P4-F2-C closure 文档 | 是 |

开发流程中的文档提交不代表 AI-Dev-Orchestrator 产品运行时具备 Git 写操作能力。
