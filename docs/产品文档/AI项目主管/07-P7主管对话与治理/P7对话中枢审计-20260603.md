# AI Project Director Conversational Brain — 代码审查与产品架构缺口报告

**日期**: 2026-06-03  
**Commit**: `4f6d37f` (fix project director plan provider fallback)  
**仓库**: https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git  
**任务类型**: 代码审查 + 产品架构缺口确认 + 最小实现方案设计  

---

## 1. 当前行为链路图

```
用户输入文本
    │
    ├── session === null ──→ POST /project-director/sessions {goal_text}
    │                          ↓
    │                       后端创建新 session (status=clarifying)
    │                       返回 clarifying_questions (5-6 条)
    │                          ↓
    │                       前端隐藏文本输入框
    │                       为每条问题渲染独立 textarea
    │
    ├── status=clarifying ──→ 每条问题旁边独立 textarea
    │                         用户填写所有答案后点击"提交答案"
    │                         POST /sessions/{id}/answers {answers:[...]}
    │
    ├── status=ready_to_confirm → 显示 goal_summary
    │                            用户点击"确认目标"按钮
    │                            POST /sessions/{id}/confirm
    │
    ├── status=confirmed ──→ 用户点击"生成项目草案"按钮
    │                        POST /sessions/{id}/plan-versions
    │
    ├── plan.status=pending_confirmation → 显示草案预览弹窗
    │                                     用户选择 approve/reject/request_changes
    │                                     POST /plan-versions/{id}/review
    │
    ├── plan.status=confirmed → 用户点击"创建正式项目"
    │                           POST /plan-versions/{id}/create-formal-project
    │
    └── taskCreation done → 显示任务创建结果、Worker 入口
                             用户点击"启动一次执行"
                             POST /workers/run-once

    ❌ 任何阶段，用户输入自由文本（"总结一下"、"为什么这么拆"）
       都会被当成新 goal_text → POST /sessions → 重新创建 session！
```

**关键发现**：`DirectorChatEntry.tsx` 的 `handleSubmit` 函数**永远调用 `createSessionMutation`** — 不管当前处于什么 state，用户输入的任何文本都会被当成新目标来创建 session。

---

## 2. 代码证据（文件路径 + 函数/组件 + 关键行为）

### 2.1 前端：DirectorChatEntry.tsx — 唯一的文本输入处理

**文件**: `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx`

```typescript
// 第 358 行: handleSubmit — 唯一的用户文本输入处理函数
const handleSubmit = async () => {
    const trimmedDraft = draft.trim();
    if (!trimmedDraft) return;
    // ⚠️ 无条件调用 createSessionMutation — 用户文本永远被当成新目标
    await createSessionMutation.mutateAsync({
        goal_text: trimmedDraft,
        project_id: scopedProjectId,
        constraints: "",
    });
    setDraft("");
};
```

**关键行为**:
- `session === null` 时: textarea 可见 → 输入文本 → 创建新 session ✅ 合理
- `session !== null` 时: textarea 变为 `hidden` → 用户**无法在任何已存在 session 下输入自由文本** ❌
- 澄清阶段: 每条问题渲染独立 textarea，但不是"自由对话"，而是结构化表单填写
- 草案审核阶段: 反馈输入框仅用于 `request_changes.feedback`，不是对话

### 2.2 前端：hooks.ts — 无消息/聊天 hook

**文件**: `apps/web/src/features/project-director/hooks.ts`

现有 hooks 清单:
- `useCreateProjectDirectorSession` → POST /sessions
- `useSubmitProjectDirectorAnswers` → POST /sessions/{id}/answers
- `useConfirmProjectDirectorGoal` → POST /sessions/{id}/confirm
- `useCreateProjectDirectorPlanVersion` → POST /sessions/{id}/plan-versions
- `useReviewProjectDirectorPlanVersion` → POST /plan-versions/{id}/review
- `useCreateProjectDirectorTaskQueue` → POST /plan-versions/{id}/create-formal-project
- `useProjectDirectorWorkbenchResume` → GET /workbench/resume

**缺失**: 没有任何 `useSendMessage`、`useConversationHistory`、`useProjectDirectorChat` hook。

### 2.3 后端：project_director.py — 无消息端点

**文件**: `runtime/orchestrator/app/api/routes/project_director.py`

grep `message|chat|conversation` → **零命中**。

路由完整清单不含任何消息相关端点:
```
POST /sessions
GET  /sessions/{session_id}
POST /sessions/{session_id}/answers
POST /sessions/{session_id}/confirm
POST /sessions/{session_id}/plan-versions
GET  /sessions/{session_id}/plan-versions
GET  /plan-versions/{plan_version_id}
POST /plan-versions/{plan_version_id}/confirm
POST /plan-versions/{plan_version_id}/review
POST /plan-versions/{plan_version_id}/create-formal-project
GET  /workbench/resume
GET  /workbench/resumable-sessions
```

### 2.4 后端：领域模型 — 无消息/聊天模型

**文件**: `runtime/orchestrator/app/domain/project_director_session.py`

```python
class ProjectDirectorSession(DomainModel):
    id: UUID
    project_id: UUID | None
    goal_text: str
    constraints: str
    status: ProjectDirectorSessionStatus       # draft|clarifying|ready_to_confirm|confirmed
    clarifying_questions: list[ClarifyingQuestion]
    clarifying_answers: list[ClarifyingAnswer]
    goal_summary: str
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime
```

**缺失字段**: `messages`、`chat_history`、`conversation_turns` — 全不存在。

### 2.5 后端：数据库表 — 无消息表

**文件**: `runtime/orchestrator/app/core/db_tables.py`

`ProjectDirectorSessionTable` 的列:
- `id`, `project_id`, `goal_text`, `constraints`, `status`
- `clarifying_questions_json` (JSON blob)
- `clarifying_answers_json` (JSON blob)
- `goal_summary`, `confirmed_at`, `created_at`, `updated_at`

**无** `project_director_messages` 表或类似结构。

### 2.6 后端：WorkbenchResumeResponse — 无消息历史

**文件**: `runtime/orchestrator/app/api/routes/project_director.py` (最新 `07240b4`)

```python
class WorkbenchResumeResponse(BaseModel):
    session: SessionResponse | None = None
    plan_version: PlanVersionResponse | None = None
    task_creation: TaskCreationResponse | None = None
    source: str = Field(default="none")
    next_action: str = Field(default="暂无可恢复的 Project Director 流程。")
```

**缺失**: `messages`、`conversation_history`、`recent_turns`。

---

## 3. 可复用能力审计

### 3.1 agent_threads/messages — 部分可参考，不能直接复用

**文件**: `runtime/orchestrator/app/api/routes/agent_threads.py`

- 已有 `AgentMessageTable`（`db_tables.py:996`）存储 agent 间的任务执行消息
- 已有 `POST /agent-threads/.../interventions` 记录主管干预
- 但 agent_threads 是**任务执行层**的消息，与 Project Director **规划会话层**完全不同
- **参考价值**: 表结构设计可作为 `project_director_messages` 的模式参考
- **不能复用**: 领域隔离 — agent thread messages 绑定 task/run，Project Director messages 绑定 session/plan

### 3.2 Provider executor / prompt service — 可直接复用

**文件**: `runtime/orchestrator/app/services/project_director_service.py`

- `ProjectDirectorService._generate_initial_clarification()` 已有 Provider 调用模式
- `ProjectDirectorPlanService` 已有 `_generate_plan_draft()` + rule_fallback 模式
- **复用方式**: Conversational Brain 的每条用户消息都应复用相同的 provider config resolve → call → guardrail → fallback 链路

### 3.3 Guardrails — 可直接复用

**文件**: `runtime/orchestrator/app/services/project_director_service.py`

- `validate_clarification_output()` / `ProjectDirectorOutputGuardrailError` 已有
- `forbidden_actions` 合同字段已经在 SessionResponse/PlanVersionResponse/TaskCreationResponse 中使用
- **复用方式**: Conversational Brain 的 AI 回复必须经过相同的 guardrail 验证

### 3.4 审批 / 确认机制 — 可复用

**文件**: `runtime/orchestrator/app/api/routes/project_director.py`

- `create-formal-project` 的 idempotency（already_created）
- `confirm` 的 idempotency（re-confirming is idempotent）
- `review` 的 request_changes → replacement plan 模式
- **复用方式**: Conversational Brain 中 suggested_actions 的高风险动作必须复用此确认链路

### 3.5 Run summary / AI 摘要 — 不直接相关

**文件**: `runtime/orchestrator/app/services/run_ai_summary_service.py`

- Run summary 是**任务执行后**的摘要，不是 Project Director 对话
- **不直接复用**，但 Conversational Brain 的 AI 回复可以引用 run summary 作为上下文

---

## 4. 产品文档对齐

### 4.1 工作台定位（page-information-architecture §3）

> 工作台正式定位为：**AI 项目主管轻量指挥室**。  
> 用户进入系统后，默认面对 AI 项目主管，可以**通过对话**提出目标、询问进度、调整计划、处理阻塞、请求总结、发起重新规划。

**当前实现**: 工作台是一个**固定流程状态机**，不是"对话"入口。  
**与产品文档差距**: 产品定位是"对话式 AI 主管"，但实现是"结构化表单填写 + 按钮点击"。

### 4.2 对话框设计（page-information-architecture §5.2-A）

> 支持用户输入："当前项目进度怎么样？""为什么任务卡住了？""帮我重新评估任务拆解。""把当前计划汇总给我审批。"

**当前实现**: 这些输入**全部无法处理** — 它们会被当成新目标，重新创建 session。

### 4.3 闭环验收（closure-checklist §WB-09）

> WB-09: 聊天框是否能访问项目上下文 — 能读取项目、任务、运行、交付、治理摘要  
> 状态: Runtime Pass (R1-A) — 但标注"更深层上下文需后续阶段补充"

**当前实现**: 聊天框**仅**能访问 `selectedProjectId` 传给 session 创建，**不能**读取任务/运行/交付/治理摘要。

### 4.4 Closure Flow §5

> 工作台闭环动作第 1 条：提出目标 — 必须形成目标记录或**主管会话记录**

**当前实现**: 会话记录仅包含 goal_text + clarifying Q&A + goal_summary。**没有任何"对话记录"或"主管会话消息"**。

---

## 5. 缺口判定

| 维度 | 当前状态 | 缺口等级 |
|------|---------|---------|
| session 内自由对话 | ❌ 完全缺失 | **P0** |
| message/turn 持久化 | ❌ 完全缺失 | **P0** |
| 围绕草案总结/解释 | ❌ 完全缺失 | **P0** |
| 误创建新 session | ❌ **已确认** — 任意文本被当成新 goal | **P0** |
| 多轮上下文对话 | ❌ 完全缺失 | **P0** |
| Intent 识别 | ❌ 完全缺失 | **P0** |
| suggested_actions 回复 | ❌ 完全缺失 | **P0** |
| 对话历史恢复 | ❌ 完全缺失 | **P1** |
| 高风险动作二次确认 | ⚠️ 部分存在（计划确认、任务创建有确认）但不在对话链中 | **P1** |

**总体判定**: **P0 — Blocking**。缺少"AI Project Director Conversational Brain"意味着系统**不符合产品基线中的"AI 项目主管对话入口"定位**。

**对 total closure 影响**: AI Project Director total closure **不能 Pass**，直到工作台具备 session-scoped 自由对话能力。

---

## 6. 最小可行架构方案

### 6.1 后端数据模型

```python
# 新文件: runtime/orchestrator/app/domain/project_director_message.py

class ProjectDirectorMessage(DomainModel):
    id: UUID
    session_id: UUID
    role: str                          # "user" | "assistant" | "system"
    content: str
    
    # Intent & routing
    intent: str | None                 # "general_discussion" | "ask_about_plan" | ...
    related_plan_version_id: UUID | None
    related_project_id: UUID | None
    related_task_id: UUID | None
    
    # AI reply metadata
    source: str                        # "ai" | "rule_fallback" | "system"
    source_detail: str | None
    suggested_actions: list[dict] | None  # [{type, label, requires_confirmation, risk_level}]
    requires_confirmation: bool
    
    # Cost
    token_count: int | None
    estimated_cost: float | None
    
    created_at: datetime
```

**数据库表**: `project_director_messages`
- 列: id, session_id, role, content, intent, related_plan_version_id, related_project_id, related_task_id, source, source_detail, suggested_actions_json, requires_confirmation, token_count, estimated_cost, created_at
- 索引: (session_id, created_at), (related_plan_version_id)

### 6.2 后端 API

```
GET  /project-director/sessions/{session_id}/messages
     → list[MessageResponse] (分页可选, 默认最近 50 条)

POST /project-director/sessions/{session_id}/messages
     body: { content: str }
     → MessageResponse (AI 回复)
     后端执行: context assembly → provider call → guardrail → persist both user msg + AI reply

POST /project-director/sessions/{session_id}/messages/{message_id}/confirm-action
     body: { action_type: str, confirmed: bool }
     → 触发对应的高风险动作（create-formal-project / request_changes / run_worker_once）
```

### 6.3 Context Builder 设计

每次 `POST /sessions/{session_id}/messages` 时，后端组装:

```python
context = {
    "session": {
        "goal_text": ...,
        "constraints": ...,
        "status": ...,
        "clarifying_questions": [...],
        "clarifying_answers": [...],
        "goal_summary": ...,
    },
    "latest_plan_version": {
        "status": ..., "plan_summary": ..., "phases": [...], "risks": [...],
        "proposed_tasks": [...], "complexity_assessment": {...}
    } or None,
    "task_creation": {
        "project_id": ..., "task_count": ..., "created_task_ids": [...]
    } or None,
    "provider_settings_status": "configured" | "not_configured" | "tested",
    "forbidden_actions": [...],
    "recent_messages": [...]   # 最近 20 条
}
```

→ 组装为 system prompt → provider call → guardrail validation → persist + return

### 6.4 Intent 识别（开放式）

不设计"只能问 N 类问题"的固定分类器。以下 intent 作为 provider system prompt 的**软引导**，不是硬路由:

```
- general_discussion        # 任何自然语言都落这里，正常回答
- ask_about_current_context  # 当前项目/会话状态
- ask_about_plan            # 草案相关
- ask_about_risks           # 风险分析
- ask_about_next_step       # 下一步建议
- request_plan_change       # 想改草案
- request_action            # 想执行动作
- navigation_help           # 不知道去哪
- restart_or_new_goal       # 想重新开始
```

**关键设计**: 任何 intent 都可以被 AI 正常回答。**unknown intent → general_discussion → 正常回复**。绝不能因为 intent 不匹配就重新创建 session。

### 6.5 AI 回复合同

```json
{
  "intent": "ask_about_plan",
  "answer": "当前草案包含 2 个阶段、6 个拟议任务。第一阶段是分析与设计，第二阶段是核心实现...",
  "related_plan_version_id": "uuid",
  "suggested_actions": [
    {
      "type": "request_changes",
      "label": "调整草案范围",
      "requires_confirmation": false,
      "risk_level": "low"
    },
    {
      "type": "create_formal_project",
      "label": "创建正式项目与任务队列",
      "requires_confirmation": true,
      "risk_level": "medium"
    }
  ],
  "forbidden_actions_detected": [],
  "risk_level": "low",
  "source": "ai",
  "source_detail": "provider=deepseek; model=deepseek-v4-pro; receipt=xxx"
}
```

### 6.6 前端交互设计

**输入框语义按状态切换**:

| session 状态 | 输入框 placeholder | 行为 |
|---|---|---|
| null | "输入你的项目目标..." | 创建新 session |
| clarifying | "回答澄清问题，或继续描述你的需求..." | 优先填答案，也允许自由补充 |
| ready_to_confirm | "继续和 AI 项目主管讨论..." | 自由对话 |
| confirmed (无 plan) | "讨论目标，或生成项目草案..." | 自由对话 + 快捷按钮 |
| confirmed (有 plan) | "讨论草案、询问细节、或继续下一步..." | 自由对话 + suggested_actions 按钮 |
| taskCreation done | "讨论执行计划、询问进度、或启动执行..." | 自由对话 + 执行入口 |

**核心改动**:
1. **删除"输入框在 session 存在时隐藏"的逻辑** — 输入框应始终可见
2. **输入框不再是"新目标"专属** — 判断 session 是否存在来决定是 create session 还是 send message
3. **AI 回复列表** — 渲染 message 历史（用户 + AI 交替）
4. **suggested_actions 按钮** — 在 AI 回复下方以按钮展示，高风险标注
5. **"新建会话"按钮** — 显式入口，不与输入框混淆

### 6.7 高风险动作治理

必须保留的约束:
- 创建正式项目 → 需确认
- 启动 Worker → 需确认
- 创建 Run → 需确认
- 写仓库 / git commit / git push / apply-local → **禁止**或审批
- AI 回复不能宣称已执行未执行动作
- total closure Pass 必须有证据
- CL-16 Pass 必须有成本证据

### 6.8 分阶段落地建议

```
Stage 7-B0: 审查结论与设计文档（本轮完成）
  → 产出: 本报告
  → Gate: 不进入实现

Stage 7-B1: Message 持久化层
  → 后端: project_director_messages 表 + 领域模型 + repository
  → 后端: GET /sessions/{id}/messages
  → 后端: POST /sessions/{id}/messages（先仅 persist user message, AI reply=rule_fallback placeholder）
  → Tests: 3-5 条 API 测试
  → Gate: messages CRUD readback ok

Stage 7-B2: Context Builder + Provider Chat Response
  → 后端: context assembly 函数
  → 后端: AI reply 生成（复用已有 provider config → call → guardrail → fallback）
  → 后端: intent soft guidance in system prompt
  → 后端: suggested_actions 生成
  → Tests: context assembly 单元测试 + provider chat integration test
  → Gate: user msg → context → AI reply → persist 全链路

Stage 7-B3: 前端消息列表 + 输入框语义切换
  → 前端: message list 组件（用户 + AI 气泡）
  → 前端: 输入框改为 send message（非 create session）
  → 前端: 状态感知 placeholder 文案
  → 前端: "新建会话"按钮
  → 前端: 页面加载时恢复消息历史
  → Tests: frontend build + smoke
  → Gate: 自由对话可用，不误创建新 session

Stage 7-B4: suggested_actions 展示
  → 前端: AI 回复下方渲染 suggested_actions 按钮
  → 高风险标记和 tooltip
  → 不执行 — 纯展示
  → Gate: actions 可见，高风险标记正确

Stage 7-B5: 确认后调用现有动作
  → 前端: 点击 suggested_action → confirm modal → POST confirm-action
  → 后端: confirm-action 端点触发 create-formal-project / request_changes / run_worker_once
  → Tests: 全链路 action 测试
  → Gate: suggested_action → 真实动作 闭环

Stage 7-B6: 运行证据与 Gate 回填
  → 记录对话中的决策证据
  → 回填 closure checklist
  → 确认 total closure 是否接近 Pass
```

---

## 7. 结论

### 当前系统判定

| 问题 | 答案 |
|------|------|
| 当前是否已有 session 内自由对话能力 | **否** — 固定流程状态机 |
| 当前是否已有 message/turn 持久化 | **否** — 无表、无模型、无 API |
| 当前是否能围绕草案总结/解释 | **否** — 任何文本被当成新 goal |
| 当前是否会误创建新 session | **是** — `handleSubmit` 永远调 `createSessionMutation` |
| 缺口等级 | **P0** — 不符合产品基线"AI 项目主管对话入口"定位 |

### 边界合规

| 约束 | 状态 |
|------|------|
| 本轮是否改代码 | 否 |
| 是否启动 Worker | 否 |
| 是否创建 Run | 否 |
| 是否调用真实 Provider | 否 |
| 是否写 Gate | 否 |
| Total closure Pass | 不写 |
| CL-16 Pass | 不写 |

### 建议下一步

1. **本报告作为 Stage 7-B0 设计文档** — 已覆盖审查、证据定位、缺口确认和方案设计
2. **下一条 Codex 任务**: Stage 7-B1 — 创建 `project_director_messages` 表 + 领域模型 + repository + GET/POST messages API（最小骨架，不含 AI 回复）
3. **设计文档建议路径**: `docs/product/ai-project-director/conversational-brain-design-20260603.md`
