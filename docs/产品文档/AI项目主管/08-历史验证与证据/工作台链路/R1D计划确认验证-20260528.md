# AI Project Director 工作台 Plan Confirmation R1-D Evidence

> 文档类型：Runtime Evidence（窄范围验证）
> 验证日期：2026-05-28
> 验证人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commit：`f684e863ebe68aff6f84dfeb43b628a4c530cf2e`
> 前置阶段：R1-A (`5d959f0`) → R1-B (`1729033`) → R1-C (`6cdad0c`)
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`
> 对应主链路：步骤 5（用户确认计划）

---

## 1. 验证范围

本 evidence 文档覆盖 R1-D 阶段：Codex 已提交前端最小接入代码（commit `f684e86`），DeepSeek 负责验证真实链路。

R1-D 在前端新增：
- pending_confirmation plan version 状态下展示"确认计划"按钮
- 调用 POST /project-director/plan-versions/{id}/confirm
- 展示 confirmed 状态、confirmed_at、next_action、gate_conclusion、forbidden_actions

### 1.1 映射验收项

| 验收项 ID | 描述 | 本阶段验证范围 |
|---|---|---|
| CL-04 | 计划是否经用户确认 | POST /project-director/plan-versions/{id}/confirm → status=confirmed, confirmed_at 非空 |
| CL-07 | 计划确认后允许后续创建任务队列（前置条件） | plan version confirmed 为 task creation 提供前置条件；frontend 未调用 create-tasks |
| WB-09 | 工作台上下文能力保持 | selectedProjectId 传递保持；上下文 badge 保持 |

---

## 2. 前置检查

### 2.1 Commit 验证

```text
origin/main HEAD: f684e863ebe68aff6f84dfeb43b628a4c530cf2e
```

变更文件（仅前端，4 files）：
- `apps/web/src/features/project-director/api.ts` (+12: confirmProjectDirectorPlanVersion)
- `apps/web/src/features/project-director/hooks.ts` (+7: useConfirmProjectDirectorPlanVersion)
- `apps/web/src/features/project-director/types.ts` (+4: ConfirmPlanVersionInput)
- `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx` (+66/-8: "确认计划"按钮、confirmed 展示)

**结论：diff 仅包含 R1-D 前端接入范围（pending_confirmation → confirmed），无后端修改。**

### 2.2 已检查文件

- `.kkr/skills/ai-project-director-command-governance/SKILL.md`
- `docs/product/ai-project-director/page-information-architecture-20260518.md`
- `docs/product/ai-project-director/closure-flow-20260518.md`
- `docs/product/ai-project-director/closure-checklist-20260518.md`
- `docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md`
- `docs/product/ai-project-director/verification-project-director-workbench-plan-generation-r1c-20260528.md`
- `apps/web/src/features/project-director/api.ts`
- `apps/web/src/features/project-director/hooks.ts`
- `apps/web/src/features/project-director/types.ts`
- `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx`
- `runtime/orchestrator/app/api/routes/project_director.py`
- `runtime/orchestrator/tests/test_project_director_plan_versions.py`
- `runtime/orchestrator/tests/test_project_director_sessions.py`

---

## 3. Build 与测试

### 3.1 前端 Build

```text
命令: cd apps/web && npm.cmd run build
结果: ✓ built in 3.59s (tsc + vite, 499 modules)
```

### 3.2 后端测试

```text
命令: cd runtime/orchestrator && python -m pytest tests/test_project_director_sessions.py tests/test_project_director_plan_versions.py -v
结果: 62 passed in 20.87s (38 session + 24 plan version)
```

---

## 4. Live HTTP Evidence

### 4.1 测试方法

临时启动 uvicorn（端口 9881，临时 SQLite 数据库）。

### 4.2 Session & Plan Version IDs

- Plan Version ID: `78fcc51c-5447-4b05-8c47-ac50525c3b3a`

### 4.3 Full Flow

| Step | API | Status | Key Result |
|---|---|---|---|
| 1 | POST /sessions | 201 | clarifying |
| 2 | POST /sessions/{id}/answers | 200 | ready_to_confirm |
| 3 | POST /sessions/{id}/confirm | 200 | confirmed |
| 4 | POST /sessions/{id}/plan-versions | 201 | pending_confirmation |
| **5** | **POST /plan-versions/{id}/confirm** | **200** | **confirmed** |
| 6 | GET /plan-versions/{id} (detail readback) | 200 | all_content_match True |
| 7 | GET /sessions/{id}/plan-versions (list readback) | 200 | 1 plan, confirmed |
| 8 | Confirm nonexistent (error) | 404 | ✓ |
| 9 | Re-confirm (idempotent) | 200 | ✓ |

### 4.4 Step 5: Confirm Plan Version Response Detail

```text
Status: 200 OK
  status: confirmed
  confirmed_at: 2026-05-29T06:51:10.233420+00:00
  next_action: 计划版本已确认。后续可进入任务创建阶段，但需单独触发
  gate_conclusion: Partial（计划闭环 Pass，总闭环未完成）
  plan_summary: 323 chars
  phases: 2 items
  proposed_tasks: 4 items
  acceptance_criteria: 3 items
  risks: 1 item
  forbidden_actions: [不自动创建任务, 不自动调度 Worker, 不写仓库]
```

### 4.5 Step 6: GET Detail Readback

```text
Status: 200 OK
  plan_summary match: True
  status match (confirmed): True
  confirmed_at match: True
  phases count match: True
  proposed_tasks count match: True
```

### 4.6 Step 7: GET List Readback

```text
Status: 200 OK
  plan_versions count: 1
  confirmed versions: 1
```

---

## 5. 前端代码审查

### 5.1 R1-D 新增 API 调用

| API | Method | 用途 |
|---|---|---|
| `/project-director/plan-versions/{id}/confirm` | POST | 确认 plan version |

### 5.2 越界检查

DirectorChatEntry.tsx 及其依赖的 api.ts 中 **不存在** 以下动作的调用：

| 动作 | 是否实现 | 证据 |
|---|---|---|
| 调用 create-tasks | 否 | 无 POST .../create-tasks 调用 |
| 调用 planning/apply | 否 | 无 planning route 调用 |
| 调度 Worker | 否 | 无 worker dispatch API 调用 |
| apply-local / git-commit | 否 | 无仓库写入链路 |

**结论：R1-D 前端仅接入 plan version confirm，未越界 ✓**

### 5.3 前端按钮逻辑

| 条件 | "确认计划"按钮 |
|---|---|
| plan.version.status === "pending_confirmation" | 显示且启用 |
| plan.version.status === "confirmed" | 不显示"确认计划"，展示"计划已确认" |
| plan.version 不存在 | 不显示 |

---

## 6. 映射验收项结论

| 验收项 | 状态 | 说明 |
|---|---|---|
| CL-04 | **Runtime Pass** | POST /plan-versions/{id}/confirm → 200 status=confirmed, confirmed_at 非空；GET detail readback 确认 plan_summary/phases/proposed_tasks 未丢失；GET list readback 确认 confirmed 状态持久化；idempotent re-confirm 正常 |
| CL-07 | **Evidence Partial** | plan version 已 confirmed，为后续 task creation 提供前置条件（only confirmed plan versions can create tasks）；前端未调用 create-tasks。**不得写 Pass** |
| WB-09 | **Runtime Pass** | 上下文传递保持，无退化 |

---

## 7. Gate 结论

### 7.1 R1-D 阶段 Gate

| Gate 项 | 结论 |
|---|---|
| 前端 Build 通过 | Pass |
| 后端 62 tests 通过 | Pass |
| Full chain: create→answer→confirm→plan→confirm_plan | Pass |
| confirmed_at non-null | Pass |
| plan_summary/phases/proposed_tasks 未丢失 | Pass |
| Detail readback all match | Pass |
| List readback confirmed | Pass |
| Error: nonexistent → 404 | Pass |
| Idempotent re-confirm → 200 | Pass |
| 未调用 create-tasks | Pass |
| 未调用 planning/apply | Pass |
| 未调用 Worker | Pass |
| 未调用 apply-local/git-commit | Pass |

**R1-D Gate：Runtime Pass**

### 7.2 AI Project Director Total Closure

**仍为 Partial**

原因：
- CL-07 仅满足前置条件（plan version confirmed），task creation 前端尚未接入
- CL-05, CL-06, CL-08~CL-18 尚未完成
- 任务创建、Worker 调度、运行证据、交付物、审批、仓库闭环、治理沉淀、成本台账均未接入

---

## 8. 文档修改清单

| 文件 | 操作 |
|---|---|
| `verification-project-director-workbench-plan-confirmation-r1d-20260528.md` | 新增 |
| `execution-plan-backfill-ledger-20260519.md` | 追加 4.1.4 R1-D 记录 |
| `closure-checklist-20260518.md` | 更新 CL-04 / CL-07 状态 |
