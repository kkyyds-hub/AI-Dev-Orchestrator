# AI Project Director 工作台 Plan Generation R1-C Evidence

> 文档类型：Runtime Evidence（窄范围验证）
> 验证日期：2026-05-28
> 验证人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commit：`6cdad0c6dc0d5fde667ff8b4790aa20b1a191319`
> 前置阶段 commit：`5d959f0` (R1-A), `1729033` (R1-B), `0036cdc` (R1-A evidence), `2f9e72f` (R1-B evidence)
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`
> 对应主链路：步骤 4（AI 主管生成计划）

---

## 1. 验证范围

本 evidence 文档覆盖 R1-C 阶段：Codex 已提交前端最小接入代码（commit `6cdad0c`），DeepSeek 负责验证真实链路。

R1-C 在前端新增以下能力：
- confirmed session 状态下展示"生成作战计划"按钮
- 调用 POST /project-director/sessions/{id}/plan-versions 创建 plan version
- 展示 plan_summary、phases、proposed_tasks、acceptance_criteria、risks、next_action、forbidden_actions、gate_conclusion
- 不调用 plan version confirm、不调用 create-tasks、不调用 planning/apply、不调度 Worker

### 1.1 映射验收项

| 验收项 ID | 描述 | 本阶段验证范围 |
|---|---|---|
| CL-03 | 是否生成 AI 作战计划 | POST /project-director/sessions/{id}/plan-versions 创建 plan version；展示 plan_summary/phases/proposed_tasks 等 |
| CL-04 | 计划是否经用户确认（前置条件） | plan version 生成后 status=pending_confirmation；前端未接入 confirm；为后续计划确认提供前置条件 |
| WB-09 | 聊天框是否能访问项目上下文 | selectedProjectId 传递保持；上下文 badge 保持 |

---

## 2. 前置检查

### 2.1 Commit 验证

```text
origin/main HEAD: 6cdad0c6dc0d5fde667ff8b4790aa20b1a191319
```

变更文件（仅前端，4 files）：
- `apps/web/src/features/project-director/api.ts` (+13: createProjectDirectorPlanVersion)
- `apps/web/src/features/project-director/hooks.ts` (+7: useCreateProjectDirectorPlanVersion)
- `apps/web/src/features/project-director/types.ts` (+45: PlanVersionStatus, PlanPhase, ProposedTask, PlanVersion, CreatePlanVersionInput)
- `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx` (+198/-19: plan version 生成按钮、渲染 phases/proposed_tasks/acceptance_criteria/risks、边界声明)

**结论：diff 仅包含 R1-C 前端接入范围（confirmed session → plan version 生成与展示），无后端修改。**

### 2.2 已检查文件

- `.kkr/skills/ai-project-director-command-governance/SKILL.md`
- `docs/product/ai-project-director/page-information-architecture-20260518.md`
- `docs/product/ai-project-director/closure-flow-20260518.md`
- `docs/product/ai-project-director/closure-checklist-20260518.md`
- `docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md`
- `docs/product/ai-project-director/verification-project-director-workbench-session-entry-r1a-20260528.md`
- `docs/product/ai-project-director/verification-project-director-workbench-goal-confirmation-r1b-20260528.md`
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
结果: ✓ built in 3.43s
      499 modules transformed.
      TypeScript tsc -b: 通过
```

### 3.2 后端测试

```text
命令: cd runtime/orchestrator && python -m pytest tests/test_project_director_sessions.py tests/test_project_director_plan_versions.py -v
结果: 62 passed in 15.05s
      覆盖: Session(38) + PlanVersion(24)
      PlanVersion 覆盖: CreatePlanVersion(7) / ListPlanVersions(3) / GetPlanVersion(2) / ConfirmPlanVersion(6) / PlanService(4)
```

---

## 4. Live HTTP Evidence

### 4.1 测试方法

临时启动 uvicorn（端口 9880，临时 SQLite 数据库），通过 `http.client` 直接调用 API。

### 4.2 Session & Plan Version IDs

- Session ID: `cd252776-0b3d-4ff1-ae8b-6b71b2373654`
- Plan Version ID: `d287585a-d215-422f-a569-3c790c7f36c8`

### 4.3 Full Flow Results

| Step | API | Status | Key Result |
|---|---|---|---|
| 1 | POST /sessions | 201 | status=clarifying, 5 questions |
| 2 | POST /sessions/{id}/answers | 200 | status=ready_to_confirm |
| 3 | POST /sessions/{id}/confirm | 200 | status=confirmed |
| 4 | POST /sessions/{unconfirmed_id}/plan-versions | 409 | Error: only confirmed ✓ |
| 5 | POST /sessions/{nonexistent_id}/plan-versions | 404 | Error: not found ✓ |
| 6 | POST /sessions/{id}/plan-versions | 201 | status=pending_confirmation |

### 4.4 Step 6: POST plan-versions Response Detail

```text
Status: 201 Created
  plan_version_id: d287585a-d215-422f-a569-3c790c7f36c8
  session_id: cd252776-0b3d-4ff1-ae8b-6b71b2373654
  version_no: 1
  status: pending_confirmation
  plan_summary: 492 chars (non-empty)
  phases: 2 items
  proposed_tasks: 4 items
  acceptance_criteria: 1 item
  risks: 1 item
  next_action: present
  gate_conclusion: Partial
```

### 4.5 Step 7: GET Plan Versions List

```text
Status: 200 OK
  plan_versions count: 1
  first id match: True
```

### 4.6 Step 8: GET Single Plan Version Readback

```text
Status: 200 OK
  plan_summary match: True
  phases count match: True (2)
  proposed_tasks count match: True (4)
  acceptance_criteria count match: True (1)
  risks count match: True (1)
  status: pending_confirmation
  gate_conclusion: Partial
```

### 4.7 Step 9: Version Increment

```text
Status: 201 Created
  version_no: 2 (incremented from 1)
```

---

## 5. 前端代码审查

### 5.1 R1-C 新增 API 调用

| API | Method | 用途 |
|---|---|---|
| `/project-director/sessions/{id}/plan-versions` | POST | 从 confirmed session 生成 plan version |

### 5.2 越界检查

DirectorChatEntry.tsx 及其依赖的 api.ts 中 **不存在** 以下动作的调用：

| 动作 | 是否实现 | 证据 |
|---|---|---|
| 调用 /plan-versions/{id}/confirm | 否 | 无 confirmPlanVersion API 调用；无 confirm 按钮 |
| 调用 /create-tasks | 否 | 无 task creation API 调用 |
| 调用 planning/apply | 否 | 无 planning route 调用 |
| 调度 Worker | 否 | 无 worker dispatch API 调用 |
| apply-local / git-commit | 否 | 无仓库写入链路 |

前端代码显式声明边界：
- `"R1-C 仅在目标确认后允许生成作战计划；不会确认计划、创建任务或调度 Worker"`
- `"R1-C 边界：不确认 plan version / 不创建任务 / 不调用 planning/apply / 不调度 Worker"`

**结论：R1-C 前端仅接入 plan version 生成（POST），未越界 ✓**

### 5.3 前端按钮禁用逻辑

| 条件 | "生成作战计划"按钮 |
|---|---|
| status !== "confirmed" | 不显示 |
| status === "confirmed" AND !planVersion AND !isPending | 启用 |
| planVersion 已存在 | 不显示（展示已有计划） |

---

## 6. 映射验收项结论

| 验收项 | 状态 | 说明 |
|---|---|---|
| CL-03 | **Runtime Pass** | confirmed session → POST plan-versions → 201 status=pending_confirmation；plan_summary/phases/proposed_tasks/acceptance_criteria/risks 全部有内容；GET list + detail readback 一致；version_no 递增正确；前端渲染所有字段 |
| CL-04 | **Evidence Partial** | plan version 已生成（pending_confirmation），为后续 confirm plan version 提供前置条件；但前端尚未接入 confirm plan version。**不得写 Pass** |
| WB-09 | **Runtime Pass** | selectedProjectId 传递保持；上下文 badge 保持；无退化 |

---

## 7. Gate 结论

### 7.1 R1-C 阶段 Gate

| Gate 项 | 结论 |
|---|---|
| 前端 Build 通过 | Pass |
| 后端 62 tests 通过 | Pass |
| Live HTTP create→answer→confirm→plan-version 全链路 | Pass |
| Plan version fields (all 10) present | Pass |
| GET list readback | Pass |
| GET detail readback (all 5 content matches) | Pass |
| Version increment | Pass |
| Error: unconfirmed → 409 | Pass |
| Error: nonexistent → 404 | Pass |
| 未调用 confirm plan version | Pass |
| 未调用 create-tasks | Pass |
| 未调用 planning/apply | Pass |
| 未调用 Worker | Pass |
| 未调用 apply-local/git-commit | Pass |

**R1-C Gate：Runtime Pass**

### 7.2 AI Project Director Total Closure

**仍为 Partial**

原因：
- CL-04 仅满足前置条件（plan version 已生成），plan version 确认前端尚未接入
- CL-05~CL-18 尚未完成
- 计划确认、任务创建、Worker 调度、运行证据、交付物、审批、仓库闭环、治理沉淀、成本台账均未接入

---

## 8. 文档修改清单

| 文件 | 操作 | 说明 |
|---|---|---|
| `verification-project-director-workbench-plan-generation-r1c-20260528.md` | 新增 | 本 evidence 文档 |
| `execution-plan-backfill-ledger-20260519.md` | 追加 | 工作台 R1-C 记录（4.1.3） |
| `closure-checklist-20260518.md` | 更新 | CL-03 / CL-04 状态 |
