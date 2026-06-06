# Coding Session Git Delivery Lifecycle P4-F2-B Human Approval API 设计

> **文档类型**: P4-F2-B API 设计文档（仅设计，不实现）  
> **生成日期**: 2026-06-06  
> **远端基准**: `origin/main` = `c093e744471c0eeffc6693ce260b54fba749bb12`  
> **主产品基线**: `docs/product/ai-project-director/page-information-architecture-20260518.md`  
> **前置文档**:  
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4f1-closure-20260606.md`  
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4f2a-closure-20260606.md`  
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4e2-closure-and-p4f-human-approval-gate-design-20260606.md`  
> **边界**: 本轮只做 API 设计方案；不改 Python 代码、不改 API、不改 Worker、不改前端、不改数据库 / migration、不写 AgentMessage、不实现 approval API、不实现产品运行时 Git 写操作。  
> **状态**: P4-F2-B Design: Complete; P4-F2-C Implementation: Not started; P4-F3: Not started; AI Project Director 总闭环: Partial

---

## 0. 阶段定位

P4-F2-B 是 Human Approval API 的**纯设计阶段**。本阶段不实现任何代码，只为下一阶段 P4-F2-C 的 Codex 实现提供精确的 API 合约。

### 0.1 本阶段范围

| 项目 | 状态 |
|------|------|
| API 路由设计 | 本轮完成 |
| Request / Response schema 设计 | 本轮完成 |
| 安全校验清单设计 | 本轮完成 |
| Evidence 来源审计 | 本轮完成 |
| 幂等 / 去重设计 | 本轮完成 |
| P4-F2-C 最小实现任务摘要 | 本轮完成 |

### 0.2 本阶段明确不做

| 项目 | 状态 |
|------|------|
| 实现 API endpoint | 不做 |
| 修改 Worker | 不做 |
| 修改前端 | 不做 |
| 写 AgentMessage | 不做 |
| 数据库 / migration | 不做 |
| 产品运行时 Git 写操作 | 不做 |
| P4-F3 前端确认入口 | 不做 |

### 0.3 语义边界

用户确认只表示"允许进入下一阶段写入前安全检查"，不表示提交、推送、PR、merge 或授权写入。API 返回 `ready=True` 时：
- `gate_allows_write` 必须为 `False`
- `approval_applied` 必须为 `False`
- 所有 Git 写操作安全标志必须为 `False`

---

## 1. API 目标

### 1.1 核心职责

设计一个最小接口，供前端确认按钮调用，职责仅为：

1. 接收显式用户确认事实（谁、确认什么、确认范围、确认内容指纹）。
2. 从持久化或缓存来源获取对应 run / task / agent_session 的 P4-C `operation_dry_run` evidence 与 P4-D `delivery_gate_evidence`。
3. 调用 `HumanApprovalGateBuilder.evaluate()`。
4. 返回 `DeliveryHumanApprovalResult` 或映射到已有 `WorkerRunOnceResponse.delivery_human_approval_*` 字段。
5. 不执行 `git add` / `git commit` / `git push` / PR。
6. 不写仓库。
7. 不创建 PR。
8. 不触发 CI。
9. 不改 Worker 默认路径。

### 1.2 非职责

| 非职责 | 说明 |
|--------|------|
| 执行 Git 写操作 | P4-F 全线禁止 |
| 生成 P4-C/P4-D evidence | evidence 由 Worker 运行产生，API 只读取 |
| 修改 run / task 状态 | API 不改变业务对象状态 |
| 持久化 approval record | P4-F2-C 不负责持久化，后续阶段决定存储方案 |
| 前端按钮实现 | 属于 P4-F3 |

---

## 2. 路由设计

### 2.1 建议路径

```text
POST /runs/{run_id}/delivery-human-approval
```

### 2.2 路径选择理由

| 考量 | 分析 |
|------|------|
| 现有路由风格 | 项目使用 RESTful 资源路由：`/workers`、`/approvals`、`/runs`、`/tasks`、`/projects`。审批相关放在 `/approvals`，但这是 deliverable 级别的 boss approval，和 P4-F 的 human approval gate 是不同的业务概念 |
| 资源归属 | human approval 是一次 run 产出的 evidence 之上的用户确认，自然归属于 run |
| 避免与现有 `/approvals` 混淆 | 现有 `/approvals` 是 boss 审批 deliverable，P4-F human approval 是用户确认提交预览。两者完全不同：前者审批交付物，后者确认进入下一 guardrail |
| 与现有 worker 路由关系 | `/workers/run-once` 返回 `WorkerRunOnceResponse`（含 `delivery_human_approval_*`），`/runs/{run_id}/delivery-human-approval` 返回同构的 human approval 子集，前端可以合并展示 |
| 文件放置 | 建议新建 `runtime/orchestrator/app/api/routes/delivery_human_approval.py`，在 `router.py` 中注册 |

### 2.3 备选路径

| 路径 | 优缺点 |
|------|--------|
| `POST /workers/runs/{run_id}/delivery-human-approval` | 语义上归 worker 域，但路径过深 |
| `POST /delivery-gate/runs/{run_id}/human-approval` | 独立顶级域，和现有风格不一致 |
| `POST /runs/{run_id}/delivery-human-approval` **(推荐)** | 最简洁，run 资源下的子资源 |

---

## 3. Request Schema 设计

### 3.1 请求体

```python
class DeliveryHumanApprovalRequest(BaseModel):
    """Request body for creating a human approval confirmation record."""

    approval_requested_action: str = Field(
        default="approve_git_add_commit_preview",
        min_length=1,
        max_length=120,
        description="被确认的目标动作。P4-F 仅允许 approve_git_add_commit_preview",
    )
    approval_scope: str = Field(
        default="git_add_commit_preview",
        min_length=1,
        max_length=120,
        description="确认范围。P4-F 仅允许 git_add_commit_preview",
    )
    approval_confirmation_text: str = Field(
        min_length=1,
        max_length=500,
        description=(
            "用户显式确认文案。必须包含确认令牌（如 confirm_git_add_commit_preview "
            "或 确认提交预览）。不落完整原文到 AgentMessage，只用于生成 fingerprint。"
        ),
    )
    approval_client_request_id: str = Field(
        min_length=1,
        max_length=200,
        description="前端生成的确认请求 ID，用于幂等与去重。同一 run 的相同 request_id 应返回相同结果。",
    )
    expected_changed_files: list[str] = Field(
        min_length=0,
        max_length=500,
        description="前端展示给用户并被用户确认的文件列表。必须与当前 P4-C evidence 完全一致。",
    )
    expected_proposed_commit_message: str = Field(
        min_length=1,
        max_length=200,
        description="前端展示给用户并被用户确认的提交说明。必须与当前 P4-C evidence 完全一致。",
    )
    approval_expires_at: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "确认过期时间（ISO 8601 UTC）。若未提供，服务端生成默认过期时间 "
            "（建议 created_at + 30 分钟）。过期后不得进入下一 guardrail。"
        ),
    )
```

### 3.2 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `approval_requested_action` | `str` | 是（默认值） | P4-F 仅允许 `approve_git_add_commit_preview` |
| `approval_scope` | `str` | 是（默认值） | P4-F 仅允许 `git_add_commit_preview` |
| `approval_confirmation_text` | `str` | 是 | 必须包含显式确认令牌；不落完整原文到持久化 |
| `approval_client_request_id` | `str` | 是 | 前端生成，幂等去重键 |
| `expected_changed_files` | `list[str]` | 是 | 用户确认的文件列表；必须与 P4-C evidence 完全一致 |
| `expected_proposed_commit_message` | `str` | 是 | 用户确认的提交说明；必须与 P4-C evidence 完全一致 |
| `approval_expires_at` | `str \| None` | 否 | 过期时间；不提供则服务端默认 `created_at + 30min` |

### 3.3 Actor（approved_by）来源

P4-F2-C 阶段暂不引入完整 auth seam。Actor 来源处理：

| 方案 | 说明 | P4-F2-C 建议 |
|------|------|-------------|
| 固定 `approved_by="user"` | 最简单的占位方案 | 采用 |
| 从请求 header 读取 | 如 `X-User-Id` 或 `X-Actor-Id` | 备选，但不强制 |
| 从 session / cookie 读取 | 需要引入 auth 中间件 | P4-F2-C 不引入 |
| **禁止前端传入 `approved_by`** | 前端不可伪造确认人身份 | **强制** |

P4-F2-C 实现时，`approved_by` 必须由后端决定，不允许 request body 中包含此字段。若后续引入 auth seam，替换为真实用户 ID。

### 3.4 approval_confirmation_text 处理规则

| 规则 | 说明 |
|------|------|
| 必须包含显式确认令牌 | `confirm_git_add_commit_preview` / `approve_git_add_commit_preview` / `确认提交预览` / `确认 git add commit 预览` |
| 不落完整原文到 AgentMessage | 只保存 `approval_confirmation_fingerprint`（SHA-256） |
| 不落完整原文到 API response | response 中不返回原文，只返回 fingerprint |
| 用于生成 fingerprint | fingerprint 输入：confirmation_text + approval_scope + expires_at + commit_message + changed_files |

---

## 4. Response Schema 设计

### 4.1 响应体

建议直接复用 `WorkerRunOnceResponse` 中的 `delivery_human_approval_*` 字段，或创建一个精简的专用 response model。

**推荐方案**：创建专用的 `DeliveryHumanApprovalResponse`，包含 `DeliveryHumanApprovalResult` 的核心字段。这样 P4-F2-C 的 API 独立于 Worker response，后续 Worker 可以从 API 返回的结果或持久化记录读取。

```python
class DeliveryHumanApprovalResponse(BaseModel):
    """API response for a human approval gate evaluation."""

    ready: bool = Field(
        description=(
            "是否已形成有效用户确认 evidence。True 只表示可进入下一阶段写入前安全检查，"
            "不表示已提交、已推送或已授权写入。"
        ),
    )
    source: str = Field(
        default="delivery_human_approval",
        description="固定来源标识",
    )
    reason_code: str | None = Field(
        default=None,
        description="阻断原因代码。ready=True 时为 None",
    )
    summary_cn: str = Field(
        description="用户可见中文摘要",
    )

    # Session 标识
    session_id: str | None = None
    project_id: str | None = None
    task_id: str | None = None
    run_id: str | None = None

    # 审批状态
    approval_required: bool = Field(default=True)
    approval_granted: bool = Field(default=False)
    approval_id: str | None = None
    approved_by: str | None = None
    approved_by_display_name: str | None = None
    approval_scope: str | None = None
    approval_requested_action: str | None = None
    approval_client_request_id: str | None = None
    approval_created_at: datetime | None = None
    approval_expires_at: datetime | None = None
    approval_applied: bool = Field(default=False)
    approval_revoked: bool = Field(default=False)
    approval_confirmation_fingerprint: str | None = None

    # Evidence 对齐
    operation_dry_run_ready: bool | None = None
    delivery_gate_evidence_ready: bool | None = None
    delivery_gate_allows_user_confirmation: bool | None = None
    delivery_gate_allows_write: bool | None = None

    # 操作预览
    proposed_operation: str | None = None
    proposed_commit_message: str | None = None
    changed_files_count: int | None = None
    changed_files: list[str] = Field(default_factory=list)

    # 条件与阻塞
    satisfied_conditions: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)

    # 安全标志（全部必须为 False，或 gate_allows_next_guardrail 在 ready=True 时为 True）
    runs_git: bool | None = None
    runs_write_git: bool | None = None
    git_add_triggered: bool | None = None
    git_commit_triggered: bool | None = None
    git_push_triggered: bool | None = None
    pr_opened: bool | None = None
    ci_triggered: bool | None = None
    execution_enabled: bool | None = None
    operation_applied: bool | None = None
    gate_allows_write: bool | None = None
    gate_allows_next_guardrail: bool | None = None

    @classmethod
    def from_result(
        cls,
        result,
        run_id: str,
    ) -> "DeliveryHumanApprovalResponse":
        """Convert DeliveryHumanApprovalResult into API DTO."""
        ...
```

### 4.2 关键响应语义

| ready 值 | 语义 | 禁止表达 |
|----------|------|---------|
| `True` | 用户确认记录已生成，可进入下一阶段写入前安全检查。当前仍未执行提交或推送。 | 审批已通过 / 已授权写入 / 可以提交代码 |
| `False` | 当前不满足用户确认条件。`reason_code` 指明阻断原因。 | 系统错误（过于模糊） |

### 4.3 与 WorkerRunOnceResponse 的关系

| 字段组 | DeliveryHumanApprovalResponse | WorkerRunOnceResponse |
|--------|------------------------------|----------------------|
| 核心 human approval 字段 | 包含 | 包含（`delivery_human_approval_*` 前缀） |
| P4-C / P4-D evidence | 仅引用对齐字段 | 包含完整 P4-C / P4-D 字段 |
| run/task 状态 | 仅 session ID | 包含完整 run/task |

两者字段一致（前缀不同），前端可以复用相同的类型定义。

---

## 5. Evidence 来源设计（关键风险声明）

### 5.1 当前证据来源审计

当前 P4-C (`GitOperationDryRunResult`) 和 P4-D (`DeliveryGateEvidenceResult`) evidence 的生命周期：

| 阶段 | 产生位置 | 持久化 | 查询能力 |
|------|---------|--------|---------|
| P4-C operation dry-run | `task_worker.py` 的 `run_once()` 方法内调用 `GitOperationDryRunBuilder` | **未持久化**。仅存在于 `WorkerRunResult` 内存对象，通过 `POST /workers/run-once` response 返回 | 无独立查询 API |
| P4-D delivery gate evidence | `task_worker.py` 的 `run_once()` 方法内调用 `DeliveryGateEvidenceBuilder` | **未持久化**。同 P4-C | 无独立查询 API |
| AgentSession | `task_worker.py` 创建，持久化到 `agent_sessions` 表 | 已持久化 | 可通过 `agent_session_repository` 查询 |

### 5.2 关键风险

```text
⚠ 当前 P4-C / P4-D evidence 主要存在于 WorkerRunResult / run-once response 内存中。
API 实现 P4-F2-C 前必须明确 evidence persistence / snapshot 来源。

不允许：
- API 自己重新扫描 Git 或重新生成不一致的 evidence
- API 用前端传来的 evidence 当事实来源
- API 在没有 evidence 时返回 ready=True
```

### 5.3 P4-F2-C 的 evidence 获取方案

建议 P4-F2-C 采用以下方案之一（由 Codex 在实现时选择并单独文档化）：

| 方案 | 描述 | 优缺点 |
|------|------|--------|
| **A. Worker 运行后缓存 evidence** | Worker 运行结束后，将 P4-C/P4-D evidence 序列化存入 run 的 log/evidence 字段或独立表。API 从缓存读取。 | 需要最小 schema 变更 |
| **B. API 触发时重新构建 evidence** | API 从 AgentSession + GitDiffDryRun 重新构建 evidence（调用已有 builder）。 | 不需要新存储，但可能和 Worker 运行时的 evidence 不一致 |
| **C. 要求前端传入完整 evidence** | ❌ 禁止。前端不可作为证据来源。 | — |

**推荐方案 A**。P4-F2-C 实现时，从 AgentSession 查找对应 session 后，重新调用 `GitOperationDryRunBuilder` 和 `DeliveryGateEvidenceBuilder` 应该得到与 Worker 运行时一致的结果（因为两者都只做 read-only 计算）。但如果 run 运行时间过长或 Git 状态发生变化，可能出现偏差。

P4-F2-C 必须：
1. 从 AgentSession 获取 session 上下文（session_id / project_id / task_id / run_id）。
2. 重新构建或读取已缓存的 P4-C/P4-D evidence。
3. 使用后端 evidence 调用 `HumanApprovalGateBuilder.evaluate()`。
4. 如果 evidence 不可用，返回 `ready=False`，`reason_code="operation_dry_run_missing"` 或 `"delivery_gate_evidence_missing"`。

---

## 6. 安全校验设计

以下校验是 P4-F2-C 实现时必须全部覆盖的硬性要求。

### 6.1 前置校验（返回 404）

| # | 校验项 | 失败 reason_code |
|---|--------|-----------------|
| 1 | `run` 存在（通过 `run_id` 查询） | HTTP 404 |
| 2 | `task` 存在（通过 run 关联） | HTTP 404 |
| 3 | `agent_session` 存在（通过 run 关联） | `agent_session_missing` |

### 6.2 Evidence 校验（返回 ready=False）

| # | 校验项 | 失败 reason_code |
|---|--------|-----------------|
| 4 | `operation_dry_run` 存在 | `operation_dry_run_missing` |
| 5 | `operation_dry_run.ready is True` | `operation_dry_run_not_ready` |
| 6 | `delivery_gate_evidence` 存在 | `delivery_gate_evidence_missing` |
| 7 | `delivery_gate_evidence.ready is True` | `delivery_gate_not_ready` |
| 8 | `delivery_gate_allows_user_confirmation is True` | `user_confirmation_not_allowed` |
| 9 | `delivery_gate_allows_write is False` | `write_gate_unexpectedly_enabled` |
| 10 | `delivery_git_write_enabled is False` | `write_gate_unexpectedly_enabled` |

### 6.3 用户确认校验（返回 ready=False）

| # | 校验项 | 失败 reason_code |
|---|--------|-----------------|
| 11 | `approval_requested_action == "approve_git_add_commit_preview"` | `unsupported_approval_action` |
| 12 | `approval_scope == "git_add_commit_preview"` | `approval_scope_unsupported` |
| 13 | `approval_scope` 与 `approval_requested_action` 与 `proposed_operation` 一致 | `approval_scope_mismatch` |
| 14 | `expected_changed_files` 与 evidence `changed_files` 完全一致（顺序无关，内容相同） | `changed_files_mismatch` |
| 15 | `expected_proposed_commit_message` 与 evidence `proposed_commit_message` 完全一致 | `commit_message_mismatch` |
| 16 | `approval_confirmation_text` 包含显式确认令牌 | `approval_confirmation_missing` |
| 17 | `approval_client_request_id` 存在且非空 | `approval_request_id_missing` |

### 6.4 生命周期校验（返回 ready=False）

| # | 校验项 | 失败 reason_code |
|---|--------|-----------------|
| 18 | `approval` 未过期（`now < approval_expires_at`） | `approval_expired` |
| 19 | `approval_applied is False`（未被后续 guardrail 消费） | `approval_already_applied` |
| 20 | `approval_revoked is False` | `approval_revoked` |

### 6.5 写操作标记校验（返回 ready=False）

| # | 校验项 | 失败 reason_code |
|---|--------|-----------------|
| 21 | 所有 P4-F forbidden safety flags 均为 False | `write_already_triggered` |

### 6.6 校验顺序

校验按以上顺序执行，第一个失败即返回。不执行后续校验以避免不必要的计算。

---

## 7. 幂等与重复确认设计

### 7.1 approval_client_request_id 的作用

`approval_client_request_id` 是前端生成的唯一请求 ID，用于：

| 用途 | 说明 |
|------|------|
| 请求去重 | 同一个 `run_id` + 同一个 `approval_client_request_id` 的重复请求应返回相同结果 |
| 追踪 | 前端可以将请求 ID 与 UI 状态关联 |
| 审计 | 后续 AgentMessage 记录中使用此 ID 追溯前端请求 |

### 7.2 幂等规则

| 场景 | 行为 |
|------|------|
| 相同 run + 相同 request_id + 相同 changed_files + 相同 commit_message | 返回已有结果（幂等） |
| 相同 run + 相同 request_id + **不同** changed_files / commit_message | 旧确认失效，返回 `changed_files_mismatch` 或 `commit_message_mismatch` |
| 相同 run + 不同 request_id | 新请求，重新评估 |
| 已有 ready=True 的确认且未被消费 | 相同 request_id 返回相同结果；不同 request_id 返回 `approval_already_applied`（需实现层判断） |

### 7.3 过期确认处理

| 场景 | 行为 |
|------|------|
| 已过期的确认 + 新 request_id | 重新评估（可以创建新确认） |
| 已过期的确认 + 相同 request_id | 返回 `approval_expired` |

### 7.4 approval_applied 消费后处理

当后续 guardrail 阶段消费 approval（设置 `approval_applied=True`）后：
- 相同 request_id 返回已有结果（但 `approval_applied=True`）
- 不同 request_id 返回 `approval_already_applied`

---

## 8. 审计 / AgentMessage 设计边界

### 8.1 本阶段只设计，不实现

P4-F2-B **不实现** AgentMessage 写入。P4-F2-D 阶段才考虑。

### 8.2 建议 event_type

| event_type | 触发条件 | 说明 |
|------------|---------|------|
| `human_approval_gate_ready` | API 返回 `ready=True` | 用户确认 evidence 已生成 |
| `human_approval_gate_blocked` | API 返回 `ready=False` | 用户确认 gate 被阻断 |

### 8.3 AgentMessage 记录字段建议

| 字段 | 建议值 | 说明 |
|------|--------|------|
| `role` | `SYSTEM` | 系统级审计事件 |
| `message_type` | `TIMELINE` | 时间线事件 |
| `event_type` | `human_approval_gate_ready` 或 `human_approval_gate_blocked` | — |
| `content_summary` | 安全中文摘要，如"用户已确认提交预览，可进入下一阶段安全检查。当前仍未写入仓库。" | 不包含代码路径或敏感数据 |
| `approval_id` | `hap_<uuid5>` | 确认记录 ID |
| `approved_by` | 后端决定的 actor | 不从前端读取 |
| `approval_scope` | `git_add_commit_preview` | — |
| `approval_client_request_id` | 前端传入值 | 用于追踪 |
| `approval_created_at` | UTC datetime | — |
| `approval_expires_at` | UTC datetime | — |
| `approval_applied` | `False` | P4-F 阶段永不为 True |
| `approval_revoked` | `False` | — |
| `approval_confirmation_fingerprint` | SHA-256 hex | **不**存 confirmation_text 原文 |
| `reason_code` | 字符串或 null | 阻断原因 |

### 8.4 关键禁止

| 禁止 | 原因 |
|------|------|
| 不写入 `confirmation_text` 原文 | 敏感用户输入不可落库 |
| 不写入任何声称 Git 已写入的内容 | P4-F 全线不写 Git |
| 不写入 `gate_allows_write=True` | 永不为 True |

---

## 9. 前端 P4-F3 依赖说明

P4-F3 前端确认按钮依赖 P4-F2-C 实现本 API。以下是 P4-F3 的前置条件：

### 9.1 按钮显示条件

| 条件 | 来源字段 |
|------|---------|
| `delivery_gate_allows_user_confirmation == True` | P4-D evidence |
| `proposed_operation == "git_add_commit"` | P4-C evidence |
| `changed_files` 非空 | P4-C evidence |
| API 已部署且可达 | — |

### 9.2 按钮调用流程

```text
1. 用户在前端看到 P4-C 提交预览（changed_files + proposed_commit_message）
2. 用户看到 P4-D delivery gate 状态（ready + allows_user_confirmation）
3. 用户点击"确认提交预览"按钮
4. 前端弹出二次确认：展示文件数量、文件列表、提交说明
5. 用户输入或确认 approval_confirmation_text
6. 前端 POST /runs/{run_id}/delivery-human-approval
7. 前端展示 response：
   - ready=True → 展示"用户确认记录已生成，可进入下一阶段安全检查。当前仍未写入仓库。"
   - ready=False → 展示 reason_code 对应的中文摘要
```

### 9.3 按钮文案规范

| 允许文案 | 禁止文案 |
|---------|---------|
| 确认提交预览 | 审批通过 |
| 确认进入下一阶段检查 | 提交代码 |
| — | 授权写入 |
| — | 一键提交 |

### 9.4 二次确认弹窗建议文案

```text
确认以下提交预览：

文件数量：3
变更文件：
- apps/web/src/pages/RunsPage.tsx
- apps/web/src/components/RunLogModal.tsx
- apps/web/src/api/run-log.ts

提交说明：
优化运行观测页技术日志弹窗与 AI 摘要展示

确认后不会立即提交代码。系统只会记录你的确认，并进入下一阶段写入前安全检查。

[确认提交预览] [取消]
```

---

## 10. 禁止与允许中文文案

### 10.1 禁止文案（绝对不得出现）

以下文案在任何 API response、AgentMessage、log 中均不得出现：

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

### 10.2 允许文案（ready=True）

```text
用户确认记录已生成
用户已确认进入下一阶段安全检查
这只是确认进入下一阶段，尚未执行提交或推送
尚未执行提交或推送
仍未执行提交或推送
当前仍未写入仓库
可进入下一阶段写入前安全检查
```

### 10.3 允许文案（ready=False）

```text
当前不满足用户确认条件
交付前检查未通过，不能确认
确认内容与当前提交预览不一致
用户确认已过期
用户确认已撤销
用户确认已被后续检查使用
缺少用户确认记录
尚不能确认提交预览，请先完成交付前检查
```

---

## 11. P4-F2-C 最小实现任务摘要

以下摘要供下一阶段 Codex 实施。P4-F2-C 实现者必须遵守此边界。

### 11.1 允许实现

| # | 任务 | 说明 |
|---|------|------|
| 1 | 新建 `runtime/orchestrator/app/api/routes/delivery_human_approval.py` | 或在现有 `workers.py` 中新增路由 |
| 2 | 实现 `POST /runs/{run_id}/delivery-human-approval` | 路由处理函数 |
| 3 | 创建 `DeliveryHumanApprovalRequest` 和 `DeliveryHumanApprovalResponse` schema | 按本设计文档 |
| 4 | 从 AgentSession 获取 session 上下文 | 使用 `AgentSessionRepository` |
| 5 | 重新构建或读取 P4-C / P4-D evidence | 使用已有 builder |
| 6 | 调用 `HumanApprovalGateBuilder.evaluate()` | 传入完整参数 |
| 7 | 返回 `DeliveryHumanApprovalResponse` | 映射 `DeliveryHumanApprovalResult` |
| 8 | 新增 targeted tests | `tests/test_delivery_human_approval_api.py` |
| 9 | 在 `router.py` 中注册路由 | — |

### 11.2 禁止实现

| # | 禁止 | 原因 |
|---|------|------|
| 1 | 前端按钮 | 属于 P4-F3 |
| 2 | AgentMessage 写入 | 属于 P4-F2-D |
| 3 | DB migration | 除非设计证明必须且另开阶段评估 |
| 4 | 产品运行时 Git 写操作 | 全线禁止 |
| 5 | 修改 Worker `run_once()` | 保持 Worker 默认路径不变 |
| 6 | 修改 P4-C / P4-D builder | 只读取，不修改 |
| 7 | 创建 PR / 触发 CI | 全线禁止 |
| 8 | 将 `gate_allows_write` 设为 True | 永不为 True |

### 11.3 测试覆盖要求

P4-F2-C 测试必须覆盖：

| # | 测试场景 | 预期 |
|---|---------|------|
| 1 | 正常确认流程（所有条件满足） | `ready=True`, `approval_granted=True`, `gate_allows_write=False` |
| 2 | run 不存在 | HTTP 404 |
| 3 | evidence 缺失 | `ready=False`, `operation_dry_run_missing` |
| 4 | evidence 未就绪 | `ready=False`, `operation_dry_run_not_ready` |
| 5 | delivery gate 未就绪 | `ready=False`, `delivery_gate_not_ready` |
| 6 | user confirmation 不允许 | `ready=False`, `user_confirmation_not_allowed` |
| 7 | write gate 异常 | `ready=False`, `write_gate_unexpectedly_enabled` |
| 8 | 不支持的 approval action | `ready=False`, `unsupported_approval_action` |
| 9 | changed_files 不一致 | `ready=False`, `changed_files_mismatch` |
| 10 | commit_message 不一致 | `ready=False`, `commit_message_mismatch` |
| 11 | confirmation_text 缺少令牌 | `ready=False`, `approval_confirmation_missing` |
| 12 | 过期确认 | `ready=False`, `approval_expired` |
| 13 | 相同 request_id 幂等 | 返回相同结果 |
| 14 | 所有 Git write flag 为 False | 全部安全字段为 False/None |

---

## 12. Gate 结论

| Gate | 结论 | 证据 |
|------|------|------|
| origin/main HEAD 确认 | Pass | `c093e744471c0eeffc6693ce260b54fba749bb12` |
| P4-F2-B 设计文档完成 | Pass | 本文档 |
| API 路由设计 | Pass | `POST /runs/{run_id}/delivery-human-approval` |
| Request schema 设计 | Pass | 7 字段，含类型、必填性、说明 |
| Response schema 设计 | Pass | 复用 delivery_human_approval_* 字段结构 |
| Evidence 来源审计 | Pass | 明确当前风险：P4-C/P4-D 未持久化 |
| 安全校验清单 | Pass | 21 项校验全部列出 |
| 幂等设计 | Pass | approval_client_request_id |
| 禁止文案清单 | Pass | 15 条禁止 + 12 条允许 |
| 是否改代码 | Pass | 否 |
| 是否改测试 | Pass | 否 |
| 是否改 Worker | Pass | 否 |
| 是否改前端 | Pass | 否 |
| 是否改数据库 | Pass | 否 |
| 是否写 AgentMessage | Pass | 否 |
| **P4-F2-B Design** | **Complete** | — |

| 后续阶段 | 状态 |
|----------|------|
| P4-F2-C API Implementation | Not started |
| P4-F2-D AgentMessage Audit | Not started |
| P4-F3 前端确认入口 | Not started |
| approval API implementation | Not started |
| 产品运行时 Git add / commit / push / PR | Not started |
| **AI Project Director 总闭环** | **Partial** |

---

## 13. 本轮收口声明

| 声明 | 结论 |
|------|------|
| 是否修改 Python 业务代码 | 否 |
| 是否修改测试代码 | 否 |
| 是否修改 API | 否 |
| 是否修改 Worker | 否 |
| 是否修改前端 | 否 |
| 是否修改数据库 / migration | 否 |
| 是否写 AgentMessage | 否 |
| 是否实现 approval API | 否 |
| 是否实现确认按钮 | 否 |
| 是否实现产品运行时 Git 写操作 | 否 |
| 是否只新增 P4-F2-B 设计文档 | 是 |

开发流程中的文档提交不代表 AI-Dev-Orchestrator 产品运行时具备 Git 写操作能力。
