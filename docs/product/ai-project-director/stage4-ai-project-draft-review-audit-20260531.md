# Stage 4-A AI 项目主管草案生成与审核弹窗闭环现状审计

> 文档类型：Stage 4 审计文档
> 审计日期：2026-05-31
> 审计人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commit（审计时）：`d7c8092a07dfd6708791117b8dbfd9e45db30cf9`
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`
> UX 路线图：`docs/product/AI-Dev-Orchestrator-AI-assisted-UX-roadmap-20260517.md`
> 前置阶段：Stage 3 Pass（项目页 AI 总结）
>
> 审计范围：Stage 4-A AI 项目主管草案生成与审核弹窗闭环现状，不做代码修改。

---

## 1. 当前最新 commit

```
d7c8092a07dfd6708791117b8dbfd9e45db30cf9
```

确认方式：`git fetch origin && git checkout main && git pull --ff-only origin main && git rev-parse HEAD`，与用户报告的 `origin/main` 一致。

---

## 2. 审计范围

本次审计覆盖 Stage 4（项目创建 AI 对话 / AI 项目主管草案生成与审核弹窗闭环）的六个维度：

1. 当前工作台 / AI 主管入口现状
2. 当前项目草案生成能力
3. 当前草案审核 / 确认 / 拒绝 / 整改能力
4. 当前动态思考状态能力
5. 当前后端 API / service / repository / domain 对应关系
6. 当前前端组件 / 页面 / hooks / api 对应关系

输出缺口清单（P0/P1/P2）、Stage 4 第一版推荐交互流程、最小可落地代码补丁建议、模型分配建议、Gate 结论。

---

## 3. 当前工作台 AI 主管入口现状

### 3.1 工作台页面组件路径

| 组件 | 路径 | 状态 |
|---|---|---|
| WorkbenchPage | `apps/web/src/pages/workbench/WorkbenchPage.tsx` | 存在，完整 |
| DirectorChatEntry | `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx` | 存在，801 行，功能完整 |
| WorkbenchHeader | `apps/web/src/pages/workbench/components/WorkbenchHeader.tsx` | 存在 |
| WorkbenchRightRail | `apps/web/src/pages/workbench/components/WorkbenchRightRail.tsx` | 存在 |
| SituationPanel | `apps/web/src/pages/workbench/components/SituationPanel.tsx` | 存在，未被直接使用（被 RightRail 替代） |
| DetailModal | `apps/web/src/pages/workbench/components/DetailModal.tsx` | 存在，可复用 Modal |
| QuickEntryCards | `apps/web/src/pages/workbench/components/QuickEntryCards.tsx` | 存在，含 BattlePlanContent、AgentMovementContent、ProjectFlowContent、PendingConfirmationsContent + EntryModals 容器 |

### 3.2 AI Project Director 对话组件现状

**是。** `DirectorChatEntry` 已是完整的 AI 项目主管对话组件，包含：

1. **用户输入目标** → 调用 `POST /project-director/sessions` 创建 session
2. **AI 主管响应澄清问题** → session 返回 `clarifying_questions`（确定性问题，非真 AI）
3. **用户回答澄清问题** → `POST /project-director/sessions/{id}/answers`
4. **目标确认** → `POST /project-director/sessions/{id}/confirm`
5. **生成作战计划** → `POST /project-director/sessions/{id}/plan-versions`
6. **确认作战计划** → `POST /project-director/plan-versions/{id}/confirm`
7. **创建真实任务队列** → `POST /project-director/plan-versions/{id}/create-tasks`
8. **手动启动一次执行** → `useRunWorkerOnce`

### 3.3 会话状态链路

会话状态完整流转：
```
用户输入目标 → clarifying → 提交答案 → ready_to_confirm → 确认目标 → confirmed → 生成计划 → pending_confirmation → 确认计划 → confirmed → 创建任务队列
```

每个状态在前端 `DirectorChatEntry` 中都有对应的 UI 渲染和按钮控制。状态由 `_compute_contract_fields()` 后端生成。

### 3.4 状态驱动方式

**真实后端驱动。** 所有状态通过 `ProjectDirectorSession.status` 字段从后端返回，前端不做假状态。

Session status 枚举：`draft / clarifying / ready_to_confirm / confirmed`

Plan version status 枚举：`draft / pending_confirmation / confirmed / superseded / rejected`

### 3.5 AI 主管"正在思考 / 正在生成"的 loading 状态

**极其有限。** 当前只有 mutation pending 状态的按钮文案变化：

| 状态 | 显示 |
|---|---|
| `createSessionMutation.isPending` | "发送中..." |
| `submitAnswersMutation.isPending` | "提交回答中..." |
| `confirmGoalMutation.isPending` | "确认中..." |
| `createPlanVersionMutation.isPending` | "生成计划中..." |
| `confirmPlanVersionMutation.isPending` | "确认计划中..." |
| `createTaskQueueMutation.isPending` | "创建任务队列中..." |
| `runWorkerOnceMutation.isPending` | "启动中..." |

无 loading dots、streaming message、skeleton、thinking indicator、step progress（如"正在分析需求 / 正在拆解任务 / 正在生成草案 / 正在重新规划"）。

---

## 4. 当前项目草案生成能力

### 4.1 草案实体

| 实体 | Domain 路径 | DB Table | Repository 路径 |
|---|---|---|---|
| ProjectDirectorSession | `runtime/orchestrator/app/domain/project_director_session.py` | `project_director_sessions` | `project_director_session_repository.py` |
| ProjectDirectorPlanVersion | `runtime/orchestrator/app/domain/project_director_plan_version.py` | `project_director_plan_versions` | `project_director_plan_version_repository.py` |
| ProjectDirectorTaskCreationRecord | `runtime/orchestrator/app/domain/project_director_task_creation.py` | `project_director_task_creation_records` | `project_director_task_creation_repository.py` |

### 4.2 草案生成方式

**确定性规则引擎，不调用真实 AI Provider。**

代码位置：`runtime/orchestrator/app/services/project_director_plan_service.py` 中的 `_generate_plan_from_session()`

生成内容完全基于 session 的 `goal_text` + `constraints` + `clarifying_answers` 的关键词匹配：
- 根据 goal 长度确定 phase 数量（2/3/4）
- 根据 tech/frontend 关键词决定 proposed_tasks
- 根据"验收"/"风险"关键词提取 acceptance_criteria 和 risks

### 4.3 草案内容字段对照

| 计划项（UX 路线图要求） | 当前 PlanVersion 字段 | 存在？ | 真实落库？ | 备注 |
|---|---|---|---|---|
| 项目目标 | `plan_summary` + session `goal_text` | ✓ | ✓ | plan_summary 为 Markdown，含目标和决策依据 |
| 项目范围 | 无独立字段 | ✗ | ✗ | 范围信息混在 `constraints` 和 `clarifying_answers` 中 |
| 不做范围 | 无独立字段 | ✗ | ✗ | 缺失 |
| 任务拆解 | `proposed_tasks[]` | ✓ | ✓ | JSON 列，含 title/description/suggested_role_code/priority_hint |
| Agent 编队 | 无独立字段 | ✗ | ✗ | `proposed_tasks` 中有 `suggested_role_code`，但无 Agent 名称/职责/协作关系 |
| Skill 绑定 | 无独立字段 | ✗ | ✗ | 缺失 |
| 验证方式 | 无独立字段 | ✗ | ✗ | 缺失 |
| 仓库建议 | 无独立字段 | ✗ | ✗ | 缺失 |
| 风险 | `risks[]` | ✓ | ✓ | JSON 列，string list |
| 验收标准 | `acceptance_criteria[]` | ✓ | ✓ | JSON 列，string list |
| 阶段拆解 | `phases[]` | ✓ | ✓ | JSON 列，含 title/goal/task_count_hint |
| 禁止行为 | `forbidden_actions[]` | ✓ | ✓ | JSON 列，安全边界 |

### 4.4 缺失字段汇总

按 UX 路线图 7.5.1 节要求，当前草案明显缺失：
1. **项目范围边界**（scope / out_of_scope）— 无独立字段
2. **Agent 编队**（Agent 名称、职责描述、上下游协作）— 仅有 `suggested_role_code`
3. **Skill 绑定方案**（每个 Agent 绑定哪些 Skill，为什么）— 完全缺失
4. **验证机制建议**（验证命令、模板建议）— 完全缺失
5. **仓库绑定建议**（仓库 URL、主分支、关注目录）— 完全缺失
6. **交付件边界**（每个任务预期产出什么）— 缺失
7. **复杂度评估**（简单/中等/复杂/大型多 Agent 协作）— 缺失

---

## 5. 当前草案审核 / 确认 / 拒绝 / 整改能力

### 5.1 "查看草案"入口

**不存在独立的"查看项目草案"入口。** 当前草案（PlanVersion）内容直接内联展开在 `DirectorChatEntry` 对话区中（第 430-703 行），通过 `planVersion` state 渲染。无"查看项目草案"卡片或按钮模式。

### 5.2 草案审核页面 / 弹窗 / 卡片

**不存在独立草案审核弹窗。** 草案审核功能通过内联对话区的按钮完成：

| 操作 | 当前状态 | 按钮位置 |
|---|---|---|
| 确认创建（确认作战计划） | **存在** | 对话区内联按钮 `handleConfirmPlanVersion` |
| 拒绝 / 放弃 | **不存在** | 无 reject plan version 端点 |
| 要求整改 | **不存在** | 无 rectification/rework flow |
| 编辑草案 | **不存在** | 草案内容不可编辑 |

### 5.3 确认创建后的实际创建内容

`POST /plan-versions/{id}/create-tasks` 调用 `ProjectDirectorTaskCreationService.create_tasks_from_plan_version()`：

| 创建实体 | 是否创建 | 代码路径 |
|---|---|---|
| Project (项目) | **否** | 依赖已存在的 project_id，不新建项目 |
| Tasks (任务) | **是** | `task_repo.add_no_commit()` → 真实落库 |
| Agent Sessions | **否** | 仅设 `owner_role_code` 在 Task 上，不创建 AgentSession |
| Roles | **否** | 仅使用已有 `ProjectRoleCode` 枚举值 |
| Skill Bindings | **否** | 不绑定 Skill |
| Validation Config | **否** | 不创建 |
| Repository Binding | **否** | 不创建 |

**关键发现：当前"确认创建"只创建 Task 实体，不创建 Project（必须预先存在）。这与 UX 路线图目标"用户通过对话创建完整项目"有本质差距。**

### 5.4 确认前提前落库问题

**不存在提前落库问题。** 当前流程严格执行"确认后才创建任务"：
- 创建 session → 只存 session 记录
- 生成 plan version → 只存 plan version 记录（`proposed_tasks` 不是真实 Task）
- 确认 plan version → 只改 plan version 状态
- 创建任务队列 → 才真正创建 Task 实体

### 5.5 按钮闭环状态

| 按钮 | 闭环状态 |
|---|---|
| "发送" | → POST /sessions 真实 API |
| "提交澄清回答" | → POST /sessions/{id}/answers |
| "确认目标" | → POST /sessions/{id}/confirm |
| "生成作战计划" | → POST /sessions/{id}/plan-versions |
| "确认作战计划" | → POST /plan-versions/{id}/confirm |
| "创建真实任务队列" | → POST /plan-versions/{id}/create-tasks |
| "启动一次执行" | → useRunWorkerOnce mutation |

**无假按钮、无 alert-only、无 console-only。**

### 5.6 Plan Version 拒绝能力

PlanVersionStatus 枚举包含 `REJECTED = "rejected"`，但：
- **无 POST /plan-versions/{id}/reject 路由**
- **无前端"拒绝计划"按钮**
- `rejected` 状态仅作为枚举定义存在，无任何代码路径可达

---

## 6. 整改链路

### 6.1 用户整改意见

**不支持。** 无整改意见输入、无整改 API、无整改记录存储。

### 6.2 整改意见保存

**不存在。**

### 6.3 AI 主管根据整改意见生成新版本草案

**不存在。** Plan version 的 supersede 机制仅在确认新版本时触发，没有"根据整改意见生成新版本"的流程。

### 6.4 Draft Version / Revision 机制

**部分存在。** `version_no` 字段和 `SUPERSEDED` 状态支持多版本：
- `list_plan_versions(session_id)` 返回所有版本，按 version_no 倒序
- `confirm_plan_version()` 会将旧 confirmed 版本标记为 superseded
- 但**没有任何机制触发新版本生成**（无 rework request → regenerate 链路）

### 6.5 旧版与新版差异

**不支持。** 前端不展示多版本列表，无 diff 对比能力。

`GET /sessions/{session_id}/plan-versions` 路由存在但前端 `DirectorChatEntry` 不使用（仅通过 `list_plan_versions` API，但前端 `api.ts` 中没有对应的前端 API 函数）。

### 6.6 对话区"AI 正在重新规划"状态

**不存在。**

---

## 7. 弹窗交互可落地性

### 7.1 最适合承接"项目草案审核弹窗"的位置

| 候选位置 | 路径 | 适用性 |
|---|---|---|
| DirectorChatEntry 内新增弹窗 | `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx` | **最佳**：草案生成后弹出审核弹窗 |
| DetailModal 复用 | `apps/web/src/pages/workbench/components/DetailModal.tsx` | **可复用**：已有 Modal 骨架 |
| EntryModals 容器 | `apps/web/src/pages/workbench/components/QuickEntryCards.tsx` | 可扩展：已有弹窗管理机制 |

### 7.2 可复用组件

| 组件 | 路径 | 用途 |
|---|---|---|
| DetailModal | `apps/web/src/pages/workbench/components/DetailModal.tsx` | 通用 Modal：header + body + close 按钮 |
| StatusBadge | `apps/web/src/components/StatusBadge.tsx` | 状态展示 |
| RunAiSummaryMarkdown | 已有（Stage 3） | Markdown 渲染（可复用于草案正文） |

### 7.3 可拆用的项目创建表单组件

**无独立可拆用的项目创建表单组件。** 当前项目创建走的是手动表单流程，不在工作台路径内。

### 7.4 类似组件

- **DirectorChatEntry** — 已有完整对话 UI，草案内联展示
- **QuickEntryCards.BattlePlanContent** — 已有作战计划弹窗内容（当前仅展示基础统计，标注"待接入 AI 项目主管后端能力"）
- 无 ProjectDraftReviewCard / DraftPreview 等专用组件

### 7.5 第一版最小改动建议插入点

**在 `DirectorChatEntry` 中**：当 `planVersion.status === 'pending_confirmation'` 时，将当前内联展开的草案内容替换为"查看项目草案"按钮，点击打开 `DetailModal` 承载的草案审核弹窗。这是改动最小的路径。

---

## 8. 动态思考状态能力

### 8.1 当前状态

| 状态类型 | 是否存在 | 实现方式 |
|---|---|---|
| loading dots | ✗ | 无 |
| streaming message | ✗ | 无，所有响应是一次性 JSON |
| skeleton | ✗ | 无 |
| thinking indicator | ✗ | 无 |
| step progress | ✗ | 无 |
| "正在分析需求 / 正在拆解任务 / 正在生成草案 / 正在重新规划" | ✗ | 无 |

仅有的状态指示：mutation pending 时按钮文案变化（如"发送中..."、"生成计划中..."）。

### 8.2 最小 UI 方案建议（仅描述，不写代码）

**不写代码，仅给方案描述：**

1. **加载脉冲点**：在 AI 主管回复区域底部加 3 个缩放脉冲点（`animate-pulse`），表示"AI 主管正在思考"
2. **步骤指示条**：在草案生成过程中显示步骤条（分析需求 → 拆解任务 → 分配 Agent → 生成草案→ 完成），每个步骤有一个轻微的过渡动画
3. **进度文案**：在加载区显示当前步骤的中文描述（如"AI 主管正在拆解任务结构…"）
4. **骨架卡片**：草案生成完成后但在用户审核前，可以先展示一个轻量骨架卡片表示"草案已就绪，请审核"

---

## 9. 当前后端 API / service / repository 对应关系

### 9.1 API 路由

| 方法 | 路由 | 文件 | 行号 |
|---|---|---|---|
| POST | `/project-director/sessions` | `project_director.py` | 274-308 |
| GET | `/project-director/sessions/{id}` | `project_director.py` | 311-329 |
| POST | `/project-director/sessions/{id}/answers` | `project_director.py` | 332-370 |
| POST | `/project-director/sessions/{id}/confirm` | `project_director.py` | 373-414 |
| POST | `/project-director/sessions/{id}/plan-versions` | `project_director.py` | 558-593 |
| GET | `/project-director/sessions/{id}/plan-versions` | `project_director.py` | 596-624 |
| GET | `/project-director/plan-versions/{id}` | `project_director.py` | 627-645 |
| POST | `/project-director/plan-versions/{id}/confirm` | `project_director.py` | 648-686 |
| GET | `/project-director/confirmations` | `project_director.py` | 734-757 |
| GET | `/project-director/projects/{id}/confirmations` | `project_director.py` | 760-777 |
| GET | `/project-director/sessions/{id}/confirmations` | `project_director.py` | 780-797 |
| POST | `/project-director/plan-versions/{id}/create-tasks` | `project_director.py` | 818-873 |
| GET | `/project-director/plan-versions/{id}/created-tasks` | `project_director.py` | 876-911 |

**已实现 13 个端点。**

### 9.2 缺失端点

| 端点 | 用途 | 严重度 |
|---|---|---|
| POST `/plan-versions/{id}/reject` | 拒绝草案 | P0 |
| POST `/plan-versions/{id}/request-rework` | 提交整改意见，触发重新规划 | P0 |
| POST `/sessions/{id}/regenerate-plan` | 根据整改意见生成新版本草案 | P0 |
| POST `/sessions/{id}/create-project` | 从草案创建完整项目（含 Agent/Skill/验证/仓库） | P0 |
| GET `/plan-versions/{id}/diff?base={base_id}` | 查看版本差异 | P2 |

### 9.3 Service 层

| Service | 路径 | 职责 |
|---|---|---|
| ProjectDirectorService | `project_director_service.py` | Session CRUD、澄清、目标确认 |
| ProjectDirectorPlanService | `project_director_plan_service.py` | Plan 生成（确定性规则）、确认、列表 |
| ProjectDirectorConfirmationService | `project_director_confirmation_service.py` | 确认事项聚合查询 |
| ProjectDirectorTaskCreationService | `project_director_task_creation_service.py` | 从 Plan 创建真实 Task |

**缺失 Service：**
- 无 `ProjectDirectorReworkService`（整改）
- 无 `ProjectDirectorProjectCreationService`（从草案创建完整项目）
- 无 real AI provider 集成（当前全部确定性规则）

### 9.4 Repository 层

| Repository | 路径 |
|---|---|
| ProjectDirectorSessionRepository | `project_director_session_repository.py` |
| ProjectDirectorPlanVersionRepository | `project_director_plan_version_repository.py` |
| ProjectDirectorTaskCreationRecordRepository | `project_director_task_creation_repository.py` |

### 9.5 测试覆盖

| 测试文件 | 测试内容 |
|---|---|
| `test_project_director_sessions.py` | Session CRUD + 状态转换 |
| `test_project_director_plan_versions.py` | Plan 生成、确认、supersede |
| `test_project_director_confirmations.py` | 确认收件箱聚合 |
| `test_project_director_task_creation.py` | 任务创建、幂等性、原子性 |
| `test_project_director_worker_run_evidence.py` | Worker Run 证据 |
| `test_project_director_run_evidence_replay.py` | 运行证据回放 |

---

## 10. 当前前端组件 / 页面 / hooks / api 对应关系

### 10.1 页面组件

| 组件 | 路径 |
|---|---|
| WorkbenchPage | `apps/web/src/pages/workbench/WorkbenchPage.tsx` |
| DirectorChatEntry | `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx` |
| WorkbenchHeader | `apps/web/src/pages/workbench/components/WorkbenchHeader.tsx` |
| WorkbenchRightRail | `apps/web/src/pages/workbench/components/WorkbenchRightRail.tsx` |
| SituationPanel | `apps/web/src/pages/workbench/components/SituationPanel.tsx` |
| DetailModal | `apps/web/src/pages/workbench/components/DetailModal.tsx` |
| QuickEntryCards | `apps/web/src/pages/workbench/components/QuickEntryCards.tsx` |

### 10.2 Feature hooks

| Hook | 路径 |
|---|---|
| useCreateProjectDirectorSession | `apps/web/src/features/project-director/hooks.ts` |
| useSubmitProjectDirectorAnswers | 同上 |
| useConfirmProjectDirectorGoal | 同上 |
| useCreateProjectDirectorPlanVersion | 同上 |
| useConfirmProjectDirectorPlanVersion | 同上 |
| useCreateProjectDirectorTaskQueue | 同上（含 queryClient invalidation） |

### 10.3 Feature API

| API 函数 | 路径 |
|---|---|
| createProjectDirectorSession | `apps/web/src/features/project-director/api.ts` |
| submitProjectDirectorAnswers | 同上 |
| confirmProjectDirectorGoal | 同上 |
| createProjectDirectorPlanVersion | 同上 |
| confirmProjectDirectorPlanVersion | 同上 |
| createProjectDirectorTaskQueue | 同上 |

**缺失前端 API：**
- 无 `listPlanVersions` 前端 API（后端路由存在，前端不调用）
- 无 `rejectPlanVersion` 前端 API
- 无 `requestRework` 前端 API
- 无 `createProjectFromDraft` 前端 API

### 10.4 Feature Types

完整类型定义位于 `apps/web/src/features/project-director/types.ts`，覆盖：
- ProjectDirectorSession（含 status、clarifying_questions、answers、goal_summary）
- ProjectDirectorPlanVersion（含 phases、proposed_tasks、acceptance_criteria、risks）
- ProjectDirectorTaskCreationResponse

---

## 11. 缺口清单

### P0 必须补（Stage 4 第一版）

| # | 缺口 | 说明 |
|---|---|---|
| P0-1 | **草案审核弹窗** | 无独立草案审核 Modal/Drawer。当前草案内联在对话区展示，无"查看项目草案"入口模式 |
| P0-2 | **拒绝草案能力** | PlanVersionStatus 有 REJECTED 但无路由、无按钮。用户无法拒绝不满意的草案 |
| P0-3 | **整改意见输入与提交** | 无整改输入框、无 rework request API。用户无法对草案提出修改要求 |
| P0-4 | **根据整改意见生成新版本** | 无 regenerate/rework API。Plan version 多版本机制存在但无法触发新版本生成 |
| P0-5 | **草案中缺少 Agent 编队** | proposed_tasks 只有 suggested_role_code，无 Agent 名称/职责/协作关系 |
| P0-6 | **草案中缺少 Skill 绑定** | 完全无 Skill 绑定方案信息 |
| P0-7 | **草案中缺少项目范围/不做范围** | 无 scope/out_of_scope 字段 |
| P0-8 | **草案中缺少验证机制建议** | 无验证命令/模板建议 |
| P0-9 | **草案中缺少仓库绑定建议** | 无仓库 URL/主分支/关注目录建议 |
| P0-10 | **草案创建不包含 Project 创建** | 草案依赖已有 project_id，不能从零创建项目 |

### P1 应该补

| # | 缺口 | 说明 |
|---|---|---|
| P1-1 | **无 AI 思考状态动态展示** | 无 loading dots/streaming/skeleton/step progress |
| P1-2 | **无 draft version 列表对比** | 前端不展示多版本、不支持版本 diff |
| P1-3 | **整改意见不持久化** | 整改流程缺失导致整改意见无存储结构 |
| P1-4 | **Agent/Skill 绑定不落库** | "确认创建"只创建 Task，不创建 Agent Session / Skill 绑定 |
| P1-5 | **草案中缺少复杂度评估** | 无 simple/medium/complex/large 分级 |
| P1-6 | **草案中缺少交付件边界** | 无每个任务预期产出的描述 |

### P2 后续补

| # | 缺口 | 说明 |
|---|---|---|
| P2-1 | **版本 diff 展示** | 新旧草案版本差异可视化 |
| P2-2 | **真实 AI 生成草案** | 当前为确定性规则生成，非真实 AI |
| P2-3 | **整改历史时间线** | 草案版本演变时间线 |
| P2-4 | **并行草案比较** | 同时比较多个草案版本 |
| P2-5 | **草案导出/分享** | Markdown/PDF 导出 |

---

## 12. Stage 4 第一版推荐交互流程

```
1. 用户在工作台 AI 主管对话框输入项目目标
2. AI 主管追问澄清问题
3. 用户回答所有问题
4. AI 主管显示目标摘要，用户确认
5. AI 主管生成项目草案（含 Agent 编队、Skill 绑定、验证建议等）
6. 对话区出现"查看项目草案"卡片/按钮
7. 用户点击 → 打开草案审核弹窗（DetailModal）
8. 弹窗展示完整草案（目标、范围、任务、Agent、Skill、验证、风险）
9. 用户选择：
   a. [确认创建] → 创建 Project + Tasks + Agent Sessions + Skill Bindings → 跳转项目页
   b. [要求整改] → 展示整改意见输入框 → 提交整改意见 → 弹窗关闭 → 对话区显示"AI 主管正在重新规划" → 生成新版本草案 → 再次出现"查看项目草案"
   c. [放弃草案] → 关闭弹窗 → 对话区回到空闲状态
10. 确认创建前不静默创建任何实体
```

### 第一版草案审核弹窗内容布局建议

弹窗使用已有的 `DetailModal` 组件骨架，内容分 7 个区域（Tab 或分节）：

| 区域 | 内容 |
|---|---|
| 项目目标与范围 | 目标摘要、范围边界、不做范围 |
| 任务拆解 | 任务列表（标题、描述、优先级、建议角色） |
| Agent 编队 | Agent 名称、职责、协作关系 |
| Skill 绑定 | 每个 Agent 的 Skill 绑定方案 |
| 验证与仓库 | 验证命令建议、仓库绑定建议 |
| 风险与验收 | 风险列表、验收标准 |
| 操作区 | [确认创建] [要求整改] [放弃草案] |

---

## 13. Stage 4 第一版最小可落地代码补丁建议

### 后端（Codex）

1. **新增 PlanVersion 字段**：`scope`、`out_of_scope`、`agent_deployment`、`skill_bindings`、`verification_suggestions`、`repository_suggestions`、`complexity_assessment`
2. **新增路由**：
   - `POST /plan-versions/{id}/reject` — 拒绝草案
   - `POST /plan-versions/{id}/request-rework` — 提交整改意见
   - `POST /sessions/{id}/create-project-from-plan/{plan_version_id}` — 从草案创建完整项目（含 Agent/Skill）
3. **新增 Service**：`ProjectDirectorProjectCreationService`（原子性创建 Project + Tasks + Agent Sessions + Skill Bindings）
4. **扩展 `_generate_plan_from_session()`**：生成 Agent 编队方案、Skill 绑定建议、验证建议、仓库建议（仍为确定性规则）
5. **新增 `ProjectDirectorReworkService`**：接收整改意见 → 生成新版本草案（supersede 机制已存在）

### 前端（Codex）

1. **新增 `DraftReviewModal.tsx`**：复用 `DetailModal`，展示草案 7 区域 + 操作按钮
2. **修改 `DirectorChatEntry.tsx`**：当 `planVersion.status === 'pending_confirmation'` 时显示"查看项目草案"按钮（替代当前内联展开）
3. **新增前端 API**：`rejectPlanVersion`、`requestRework`、`createProjectFromPlan`
4. **新增 loading 状态**：在等待后端草案生成时显示步骤指示
5. **新增整改流程 UI**：弹窗内整改意见输入 + 提交后对话区显示"AI 主管正在重新规划"

### 不改的范围
- 不重构 WorkbenchPage
- 不修改侧边栏导航
- 不修改现有手动创建流程
- 不修改运行页 / 项目页 / 执行中心
- 不修改后端 API 协议（仅新增路由）

---

## 14. 判断下一步应该交给 Codex 还是 DeepSeek

**本次审计任务：DeepSeek**（已完成）

**下一步实现：Codex**

原因：
1. P0 缺口全部是业务代码缺失（新增路由、新增 Service、新增字段、新增前端组件）
2. 涉及后端 API 新增和前端组件新增
3. 根据 Skill 规则（.kkr/skills/ai-project-director-command-governance/SKILL.md），Codex 负责最小业务代码修补
4. 代码修补完成后，需要 DeepSeek 进行 evidence 验证

---

## 15. 明确不做事项（本阶段）

1. 不新建复杂项目创建表单（在弹窗中完成审核）
2. 不替代现有手动创建流程
3. 不绕过用户确认直接创建正式项目
4. 不自动绑定仓库
5. 不自动配置高风险验证命令
6. 不调用 apply-local / git-commit
7. 不把草案生成伪装成项目已创建
8. 不把 AI 主管做成普通问答机器人
9. 不把审核分散到多个页面作为第一版主方案
10. 第一版优先在工作台 AI 主管旁边或弹窗完成草案审核
11. 不修改主产品基线
12. 不修改 Stage 3 evidence
13. 不修改 checklist / ledger / total gate
14. 不把 AI Project Director total closure 写成 Pass
15. 不把 CL-16 写成 Pass
16. 不新增代码（本次审计）
17. 不删除代码（本次审计）
18. 不做 UI 实现（本次审计）

---

## 16. Gate 结论

### 16.1 Stage 4-A Gate

**Partial**

判定依据：
1. AI 主管对话入口已存在（DirectorChatEntry + WorkbenchPage）
2. Session 创建 → 澄清 → 确认 → 计划生成 → 计划确认 → 任务创建链路已真实存在
3. 后端 13 个端点全部可用，测试覆盖完整
4. 草案审核弹窗**不存在**（P0）
5. 拒绝草案能力**不存在**（P0）
6. 整改 / rework 链路**不存在**（P0）
7. Agent 编队、Skill 绑定、验证建议、仓库建议在草案中**缺失**（P0）
8. 项目创建（从草案）**不存在**（P0）
9. 动态思考状态**不存在**（P1）
10. 草案生成仍为确定性规则，非真 AI（P2）

### 16.2 AI Project Director Total Closure

**不涉及本次判定。** Total closure 仍为 Partial（CL-16 Evidence Partial）。Stage 4-A 不应被标记为 Pass。

### 16.3 下一步建议

**交给 Codex**，实现 P0 缺口的后端路由 + Service + 前端弹窗。完成后交给 DeepSeek 做 evidence 验证。

---

## 17. 附录：关键代码位置速查

### 前端
| 文件 | 路径 |
|---|---|
| WorkbenchPage | `apps/web/src/pages/workbench/WorkbenchPage.tsx:14-117` |
| DirectorChatEntry | `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx:38-800` |
| DetailModal | `apps/web/src/pages/workbench/components/DetailModal.tsx:10-36` |
| QuickEntryCards | `apps/web/src/pages/workbench/components/QuickEntryCards.tsx:1-276` |
| WorkbenchRightRail | `apps/web/src/pages/workbench/components/WorkbenchRightRail.tsx:22-265` |
| project-director/types | `apps/web/src/features/project-director/types.ts:1-117` |
| project-director/api | `apps/web/src/features/project-director/api.ts:1-78` |
| project-director/hooks | `apps/web/src/features/project-director/hooks.ts:1-57` |

### 后端
| 文件 | 路径 |
|---|---|
| Routes | `runtime/orchestrator/app/api/routes/project_director.py:1-911` |
| Session Service | `runtime/orchestrator/app/services/project_director_service.py:1-339` |
| Plan Service | `runtime/orchestrator/app/services/project_director_plan_service.py:1-324` |
| Task Creation Service | `runtime/orchestrator/app/services/project_director_task_creation_service.py:1-298` |
| Confirmation Service | `runtime/orchestrator/app/services/project_director_confirmation_service.py` |
| Session Domain | `runtime/orchestrator/app/domain/project_director_session.py:1-56` |
| Plan Version Domain | `runtime/orchestrator/app/domain/project_director_plan_version.py:1-65` |
| Task Creation Domain | `runtime/orchestrator/app/domain/project_director_task_creation.py` |
| DB Tables | `runtime/orchestrator/app/core/db_tables.py:1639-1772` |
| Session Repository | `runtime/orchestrator/app/repositories/project_director_session_repository.py` |
| Plan Version Repository | `runtime/orchestrator/app/repositories/project_director_plan_version_repository.py` |
| Task Creation Repository | `runtime/orchestrator/app/repositories/project_director_task_creation_repository.py` |

### 测试
| 文件 | 路径 |
|---|---|
| Session Tests | `runtime/orchestrator/tests/test_project_director_sessions.py` |
| Plan Version Tests | `runtime/orchestrator/tests/test_project_director_plan_versions.py` |
| Confirmation Tests | `runtime/orchestrator/tests/test_project_director_confirmations.py` |
| Task Creation Tests | `runtime/orchestrator/tests/test_project_director_task_creation.py` |
| Worker Run Evidence | `runtime/orchestrator/tests/test_project_director_worker_run_evidence.py` |
| Run Evidence Replay | `runtime/orchestrator/tests/test_project_director_run_evidence_replay.py` |
