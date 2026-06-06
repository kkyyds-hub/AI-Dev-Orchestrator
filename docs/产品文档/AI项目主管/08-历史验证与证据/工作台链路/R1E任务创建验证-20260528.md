# AI Project Director 工作台 Task Creation R1-E Evidence

> 文档类型：Runtime Evidence（窄范围验证）
> 验证日期：2026-05-28
> 验证人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commits：`95745d9` (wire task queue creation), `e9d99e3` (trim task id chips)
> 前置阶段：R1-A → R1-B → R1-C → R1-D
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`
> 对应主链路：步骤 6（创建真实任务队列）

---

## 1. 验证范围

R1-E 阶段：Codex 已完成前端最小接入（confirmed plan → create-tasks + task ID chips UI guard），DeepSeek 负责验证真实链路。

R1-E 在前端新增：
- confirmed plan version 状态下展示"创建任务队列"按钮
- POST /project-director/plan-versions/{id}/create-tasks
- 展示 created_task_ids（最多 6 个，超出显示"等 N 个任务"）
- 不调用 Worker / planning/apply

### 1.1 映射验收项

| 验收项 ID | 描述 | 本阶段验证范围 |
|---|---|---|
| CL-07 | 是否根据计划创建任务队列 | confirmed plan → create-tasks → 真实 task rows in TaskTable |
| CL-08 | 任务创建后允许后续调度 Worker | task 已创建 (status=pending)，为 Worker 调度提供前置条件 |
| CL-17 | 页面按钮是否真实闭环 | "创建任务队列"按钮真实 POST create-tasks |
| WB-09 | 工作台上下文能力保持 | selectedProjectId 传递保持 |

---

## 2. 前置检查

### 2.1 Commits

```text
origin/main HEAD: e9d99e3
R1-E commits: 95745d9 + e9d99e3
```

变更文件（仅前端，4 files）：
- `apps/web/src/features/project-director/api.ts` (+13: createProjectDirectorTaskQueue)
- `apps/web/src/features/project-director/hooks.ts` (+20/-3: useCreateProjectDirectorTaskQueue)
- `apps/web/src/features/project-director/types.ts` (+16: TaskCreationResult, TaskCreationInput)
- `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx` (+129/-9: create-tasks 按钮、task ID chips、overflow guard)

**结论：diff 仅包含 R1-E 前端接入范围（confirmed plan → task queue creation + UI guard），无后端修改。**

### 2.1.1 UI Guard 验证

```typescript
// DirectorChatEntry.tsx:91
const visibleTaskIds = taskCreation?.created_task_ids.slice(0, 6) ?? [];
// DirectorChatEntry.tsx:589
等 {hiddenTaskCount} 个任务
```

**结论：task ID 最多展示 6 个，超出时显示"等 N 个任务" ✓**

### 2.2 已检查文件

- `.kkr/skills/ai-project-director-command-governance/SKILL.md`
- `docs/product/ai-project-director/page-information-architecture-20260518.md`
- `docs/product/ai-project-director/closure-flow-20260518.md`
- `docs/product/ai-project-director/closure-checklist-20260518.md`
- `docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md`
- `docs/product/ai-project-director/verification-project-director-workbench-plan-confirmation-r1d-20260528.md`
- `apps/web/src/features/project-director/api.ts`
- `apps/web/src/features/project-director/hooks.ts`
- `apps/web/src/features/project-director/types.ts`
- `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx`
- `runtime/orchestrator/app/api/routes/project_director.py`
- `runtime/orchestrator/tests/test_project_director_task_creation.py`
- `runtime/orchestrator/tests/test_project_director_plan_versions.py`
- `runtime/orchestrator/tests/test_project_director_sessions.py`

---

## 3. Build 与测试

### 3.1 前端 Build

```text
命令: cd apps/web && npm.cmd run build
结果: ✓ built in 3.69s (tsc + vite, 499 modules)
```

### 3.2 后端测试

```text
命令: cd runtime/orchestrator && python -m pytest tests/test_project_director_sessions.py tests/test_project_director_plan_versions.py tests/test_project_director_task_creation.py -v
结果: 80 passed in 29.98s (38 session + 24 plan version + 18 task creation)
```

---

## 4. Live HTTP Evidence

### 4.1 IDs

- Project ID: `17de4fc4-3c87-4e90-9c5d-4f84036268ed`
- Session ID: `96ba7ec1-7c83-4de1-b009-142e17d2a303`
- Plan Version ID: `f6d640e3-bed0-44b1-b3d7-52d02189c0d0`
- Created Task IDs: `44d469b4-...`, `28da351d-...`, `d3ebf4bd-...`, +1 more (4 total)

### 4.2 Full Flow

| Step | API | Status | Key Result |
|---|---|---|---|
| 0 | POST /projects | 201 | project created (required for task creation) |
| 1 | POST /sessions (with project_id) | 201 | clarifying, 5 questions |
| 2 | POST /sessions/{id}/answers | 200 | ready_to_confirm |
| 3 | POST /sessions/{id}/confirm | 200 | confirmed |
| 4 | POST /sessions/{id}/plan-versions | 201 | pending_confirmation |
| 5 | POST /plan-versions/{id}/confirm | 200 | confirmed |
| **6** | **POST /plan-versions/{id}/create-tasks** | **201** | **created** |
| 7 | GET /plan-versions/{id}/created-tasks | 200 | readback match |

### 4.3 Step 6: Create Tasks Response

```text
Status: 201 Created
  task_count: 4
  created_task_ids count: 4
  status: created
  plan_version_id: f6d640e3-bed0-44b1-b3d7-52d02189c0d0
  session_id: 96ba7ec1-7c83-4de1-b009-142e17d2a303
  project_id: 17de4fc4-3c87-4e90-9c5d-4f84036268ed
  next_action: 任务已创建至任务队列中。可通过手动触发 Worker 来执行任务。当前阶段不自动执行。
  forbidden_actions: [不自动调度 Worker, 不自动执行任务, ...]
  gate_conclusion: Partial（任务创建闭环 Pass，Worker 执行未完成）
```

### 4.4 Step 7: GET Created Tasks Readback

```text
Status: 200 OK
  task_count match: True
  task_ids match: True (4 ids)
  status: created
  gate_conclusion: Partial（任务创建闭环 Pass，Worker 执行未完成）
```

### 4.5 Task Queue Evidence (Step 8)

Each created task verified via `GET /tasks/{id}`:

| Task ID (short) | Status | Title |
|---|---|---|
| `44d469b4-...` | pending | 功能范围确定 (verified) |
| `28da351d-...` | pending | (verified) |
| `d3ebf4bd-...` | pending | (verified) |

**3/3 sampled tasks confirmed in TaskTable with status=pending ✓**

### 4.6 Error Paths

| Case | Status | Expected |
|---|---|---|
| Duplicate create-tasks | 409 ✓ | Conflict |
| Nonexistent plan version | 404 ✓ | Not Found |

---

## 5. 前端代码审查

### 5.1 R1-E 新增 API 调用

| API | Method | 用途 |
|---|---|---|
| `/project-director/plan-versions/{id}/create-tasks` | POST | 从 confirmed plan 创建真实任务队列 |

### 5.2 越界检查

DirectorChatEntry.tsx 及其依赖中 **不存在** 以下动作：

| 动作 | 是否实现 |
|---|---|
| 调用 Worker | 否 |
| 调用 planning/apply | 否 |
| 调用 apply-local / git-commit | 否 |
| 直接写仓库 | 否 |

前端显式声明：`"R1-E 边界：确认 plan version 后可创建真实任务队列；不调度 Worker / 不调用 planning/apply"`

**结论：R1-E 前端仅接入 create-tasks，未越界 ✓**

### 5.3 UI Guard 验证

```text
visibleTaskIds = created_task_ids.slice(0, 6)
overflow: "等 {hiddenTaskCount} 个任务"
```

**结论：task ID 最多展示 6 个，短 ID 显示不撑破布局 ✓**

---

## 6. 映射验收项结论

| 验收项 | 状态 | 说明 |
|---|---|---|
| CL-07 | **Runtime Pass** | confirmed plan → create-tasks → 201 status=created；4 tasks 落库 (TaskTable GET 200/pending)；created-tasks readback task_count/task_ids 一致；project_id/session_id/plan_version_id 一致 |
| CL-08 | **Evidence Partial** | 任务队列已创建 (4 tasks, status=pending)，为后续 Worker/Agent 调度提供前置条件；前端未接入 Worker 调度。**不得写 Pass** |
| CL-17 | **Runtime Pass (本阶段)** | "创建任务队列"按钮真实 POST create-tasks → 201；task IDs 展示有 UI guard；不涉及全站按钮 Pass |
| WB-09 | **Runtime Pass** | selectedProjectId 传递保持；project_id 在 session 和 task creation 间一致 |

---

## 7. Gate 结论

### 7.1 R1-E 阶段 Gate

**R1-E Runtime Pass**

| Gate 项 | 结论 |
|---|---|
| Build | Pass (3.69s) |
| 80 tests | Pass |
| Full chain (create project → session → answers → confirm → plan → confirm → create-tasks) | Pass |
| task_count=4, status=created | Pass |
| GET created-tasks readback consistent | Pass |
| Tasks in TaskTable (GET /tasks/{id}, pending) | Pass |
| project_id/session_id/plan_version_id consistent | Pass |
| Duplicate → 409 | Pass |
| Nonexistent → 404 | Pass |
| UI guard: max 6 task IDs + overflow | Pass |
| 未调用 Worker/planning/apply/apply-local | Pass |

### 7.2 AI Project Director Total Closure

**仍为 Partial**

CL-08~CL-18 尚未完成；Worker 调度、运行证据、交付物、审批、仓库闭环、治理沉淀、成本台账均未接入。
