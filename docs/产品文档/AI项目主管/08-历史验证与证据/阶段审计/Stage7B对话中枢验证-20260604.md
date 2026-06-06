# Stage 7-B Conversational Brain — Evidence & Regression Verification

> **日期**: 2026-06-04  
> **基于 Commit**: `676d875` (Bridge Project Director suggested actions)  
> **仓库**: https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git  
> **验证范围**: Stage 7-B1 ~ 7-B5 实现级证据复核  
> **主产品基线**: `docs/product/ai-project-director/page-information-architecture-20260518.md`  
> **设计基线**: `docs/product/ai-project-director/conversational-brain-design-20260603.md`  
> **审计基线**: `docs/product/ai-project-director/conversational-brain-audit-20260603.md`

---

## 1. Stage 7-B1 ~ 7-B5 完成摘要

| Stage | Commit | 内容 | 状态 |
|-------|--------|------|------|
| 7-B1 | `87c4062` `7372b44` `d826a01` | Message 持久化层：domain model、DB table、repository、GET/POST messages API、API contract tests、safety tests | ✅ |
| 7-B2 | `766521d` `7bfae19` | Context Builder + Provider chat response + rule fallback | ✅ |
| 7-B3 | `ef71dda` | 前端消息列表 + 输入框语义切换 | ✅ |
| 7-B4 | `bc95032` | suggested_actions 只读展示、read-only action display | ✅ |
| 7-B5 | `676d875` | suggested_actions → 确认 ←→ 现有端点（request_changes / create_formal_project）确认桥接 | ✅ |

**总提交数**: 8 commits (87c4062 → 676d875)

---

## 2. 后端 API 与数据模型证据

### 2.1 数据模型

**文件**: `runtime/orchestrator/app/domain/project_director_message.py`

```python
class ProjectDirectorMessage(DomainModel):
    id: UUID
    session_id: UUID
    role: ProjectDirectorMessageRole          # USER | ASSISTANT | SYSTEM
    content: str
    sequence_no: int
    source: ProjectDirectorMessageSource      # AI | RULE_FALLBACK | SYSTEM
    source_detail: str | None
    suggested_actions: list[dict] | None
    requires_confirmation: bool
    risk_level: str | None
    forbidden_actions_detected: list[str] | None
    created_at: datetime
```

**文件**: `runtime/orchestrator/app/core/db_tables.py:1701`
- 表名: `project_director_messages`
- 列: id, session_id, role, content, sequence_no, source, source_detail, suggested_actions_json, requires_confirmation, risk_level, forbidden_actions_detected_json, created_at
- 索引: (session_id, created_at)

### 2.2 Message API

**GET /project-director/sessions/{session_id}/messages** (`project_director.py:588`)
- Response: `ProjectDirectorMessageListResponse` { session_id, messages[], has_more }
- 支持游标分页 (before 参数)
- 最近 50 条，按 created_at 降序

**POST /project-director/sessions/{session_id}/messages** (`project_director.py:629`)
- Request: { content: str }
- Response: `PostProjectDirectorMessageResponse` { user_message, assistant_message, source }
- 处理流程: persist user msg → context builder → provider call → guardrail → persist AI reply
- 文档字符串明确声明: "不创建运行、调度 Worker、执行 planning/apply、执行 apply-local、执行 suggested_actions 或写入仓库"

### 2.3 WorkbenchResumeResponse 更新

**文件**: `project_director.py:2210-2216`

```python
class WorkbenchResumeResponse(BaseModel):
    session: SessionResponse | None = None
    plan_version: PlanVersionResponse | None = None
    task_creation: TaskCreationResponse | None = None
    recent_messages: list[ProjectDirectorMessageResponse] = Field(default_factory=list)  # NEW
    source: str = Field(default="none")
    next_action: str = Field(default="暂无可恢复的 Project Director 流程。")
```

`recent_messages` 由 `_recent_message_responses()` 从 `ProjectDirectorMessageRepository.list_by_session_id()` 填充（最近 20 条）。

---

## 3. Context Builder / Provider Chat / Fallback 证据

### 3.1 Context Builder

**文件**: `runtime/orchestrator/app/services/project_director_context_builder_service.py`

`ProjectDirectorConversationContext` 包含:
- session (goal_text, constraints, status, goal_summary)
- clarifying_questions / clarifying_answers
- recent_messages (最近 20 条)
- latest_plan_version (phases, proposed_tasks, risks, acceptance_criteria, complexity)
- task_creation (project_name, task_count)
- project_snapshot, task_snapshot
- safety_boundary (不启动 Worker、不创建 Run、不执行 planning/apply…)

数据来源: 6 个 repository（session, message, plan_version, task_creation, project, task）— 全部后端 readback。

### 3.2 Provider Chat

**文件**: `runtime/orchestrator/app/services/project_director_message_service.py`

- `_build_assistant_reply()` 优先调用 Provider（`_call_provider_text` 或注入的 `provider_text_generator`）
- 成功后设置 `source=AI`, `source_detail="provider=...; model=...; receipt=..."`

### 3.3 Rule Fallback

5 个 fallback 路径均设置 `source=RULE_FALLBACK`, `source_detail="stage_7_b2_rule_fallback; reason=..."`:

| Fallback 场景 | 触发条件 |
|--------------|---------|
| `provider_config_unavailable` | ProviderConfigService 异常 |
| `provider_not_configured` | 无 API key |
| `provider_generation_failed` | Provider 调用异常 |
| `provider_empty_output` | Provider 返回空 |
| `provider_contract_invalid` | Provider 输出非 JSON 或不在 allowlist |

### 3.4 防御性检测

`_detect_forbidden_execution_claims()` 检测 Provider 输出中是否包含:
- "已启动 Worker" / "已创建 Run" / "已执行 planning/apply" / "已执行 apply-local"
- 如检测到，标记在 `forbidden_actions_detected` 中

Rule fallback 回复内容明确声明:
> "本回复不会启动 Worker、创建 Run、执行 planning/apply、执行 apply-local、写仓库或执行 suggested_actions。"

---

## 4. 前端输入语义切换证据

**文件**: `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx`

### 4.1 handleSubmit 路由逻辑 (line 389-416)

```typescript
// 有 session → 发送消息
if (session) {
    const result = await postMessageMutation.mutateAsync({
        sessionId: session.id,
        content: trimmedDraft,
    });
}
// 无 session → 创建新 session
else {
    const createdSession = await createSessionMutation.mutateAsync({
        goal_text: trimmedDraft,
        project_id: scopedProjectId,
        constraints: "",
    });
}
```

### 4.2 消息历史恢复 (line 326)

```typescript
setMessageTimeline(resume.recent_messages ?? []);
```

### 4.3 验证点

| 场景 | 行为 | 状态 |
|------|------|------|
| session === null 时输入 | POST /sessions 创建新 session | ✅ |
| session 存在时输入 | POST /sessions/{id}/messages 发消息 | ✅ |
| 用户说"总结草案" | 走 message 路径，不重新澄清 | ✅ |
| 页面刷新恢复 | resume.recent_messages → 恢复历史 | ✅ |

---

## 5. Suggested Actions 只读展示与确认桥接证据

**文件**: `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx`

### 5.1 SuggestedActions 组件 (line 1380-1487)

- 每条 AI reply 的 `suggested_actions` 被渲染为按钮列表
- `data-testid="project-director-suggested-actions-readonly"`
- 显示 "confirmation bridge" 模式标签

### 5.2 确认桥接

| 动作 | 确认方式 | 状态 |
|------|---------|------|
| `request_changes` | `window.prompt` 输入反馈 + `window.confirm` 二次确认 | ✅ |
| `create_formal_project` | `window.confirm` 确认 | ✅ |
| `run_worker_once` | **被禁用** — 标签 "不可从建议启动"，说明 "本阶段禁止从 suggested_actions 触发" | ✅ 禁止 |
| `navigate` / other actions | 只读展示或禁用提示，不桥接后端动作 | ✅ 只读 |

### 5.3 独立 Worker 入口

`handleRunWorkerOnce` (line 601-619) 是正式项目卡片中的独立按钮，需要 `window.confirm` — **不在 suggested_actions 中自动触发**。

---

## 6. 禁止动作核查

| 禁止动作 | 后端证据 | 前端证据 | 状态 |
|---------|---------|---------|------|
| 未启动 Worker | `_FORBIDDEN_MESSAGE_ACTIONS` + 文档字符串 | `run_worker_once` 在 suggested_actions 中被禁用 | ✅ |
| 未创建 Run | 同上；`_detect_forbidden_execution_claims()` 检测 | 无 run 创建代码路径 | ✅ |
| 未执行 planning/apply | 同上 | 无 planning/apply 调用 | ✅ |
| 未执行 apply-local | 同上 | 无 apply-local 调用 | ✅ |
| 未写仓库业务动作 | 同上 | 无 repository write 调用 | ✅ |
| 未从 suggested_actions 调用 runWorkerOnce | `run_worker_once` 不在确认桥接中 | `resolveSuggestedActionBridge` 跳过 `run_worker_once` | ✅ |
| source/source_detail 可追溯 | AI=provider+model+receipt; fallback=reason | MessageBubble 渲染 source badge | ✅ |
| rule_fallback 不冒充 AI | source=RULE_FALLBACK 显式标注 | source badge 区分 "AI 生成" / "规则生成" | ✅ |
| 未新增 Gate Pass / CL-16 Pass | 所有 Gate 结论仍为 Partial / Not Pass | — | ✅ |

---

## 7. 测试命令与结果

### 7.1 Message tests

```bash
$ cd runtime/orchestrator
$ python3 -m pytest tests/test_project_director_messages.py -q

20 passed in 1.40s
```

覆盖: message CRUD、空白拒绝、API contract、Provider chat response 只读上下文、
rule fallback 使用 plan risk/task context、context builder 读取消息/项目/任务

### 7.2 前端构建

```bash
$ npm --prefix apps/web run build

✓ built in 1.13s
```

---

## 8. Gate 结论

| Gate | 结论 | 说明 |
|------|------|------|
| **Stage 7-B conversational brain implementation-level** | **Pass** | 7-B1~7-B5 全部 8 个 commits 在库；数据模型、API、context builder、provider chat、fallback、前端输入语义、suggested_actions 展示与确认桥接全部有代码证据、测试和 build 验证 |
| **Runtime evidence-level** | **Partial** | 本轮未执行 Live HTTP 端到端验证（Provider chat 涉及外部调用，需用户在真实环境下手动验收） |
| **AI Project Director total closure** | **Partial** | S8 P2（多未完成会话指示器）+ CL-16 成本闭环仍待解决 |
| **CL-16** | **Not Pass / Deferred** | 对话 cost 已记录 token_count/estimated_cost，但真实 provider-reported cost 闭环待后续 |

---

## 9. 下一步建议

1. **用户真实手工测试**: 启动前后端，在有 Provider 配置的环境下验证完整对话链路：
   - 创建 session → 回答澄清 → 确认目标 → 生成草案
   - 发送 "总结这个草案" → 验证 AI 基于 plan 回答，不重新澄清
   - 发送 "有什么风险" → 验证 AI 引用 plan.risks
   - 点击 suggested_actions 中的 "创建正式项目" → 验证确认弹窗 → 确认后真实创建
   - 刷新页面 → 验证对话历史恢复
2. **如果真实测试通过**: 进入后续整体 evidence gate；回填 WB-09 closure checklist
3. **不建议继续加功能**: 7-B5 确认桥接完成后，Conversational Brain 核心链路已实现

---

## 10. 边界合规声明

| 约束 | 状态 |
|------|------|
| 本轮是否改业务代码 | 否 |
| 是否启动 Worker | 否 |
| 是否创建 Run | 否 |
| 是否调用真实 Provider | 否（本轮仅静态复核 + 测试套件） |
| 是否执行 planning/apply | 否 |
| 是否执行 apply-local | 否 |
| 是否写仓库业务动作 | 否 |
| 是否写 Gate Pass | 否（total closure 仍为 Partial） |
| CL-16 Pass | 否（Deferred） |
| Runtime evidence-level Pass | 否（Partial，待用户真实验收） |
| Implementation-level Pass | 是（7-B1~7-B5 代码级链路闭环） |
