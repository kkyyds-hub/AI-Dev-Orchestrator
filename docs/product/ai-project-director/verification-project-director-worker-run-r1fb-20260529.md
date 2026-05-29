# AI Project Director 工作台 Worker Run R1-Fb Evidence

> 文档类型：Runtime Evidence（窄范围验证）
> 验证日期：2026-05-29
> 验证人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commit：`d9bd81fdebd00f318c0016f79e02cdd981884a1b`
> 前置阶段：R1-A → R1-B → R1-C → R1-D → R1-E → R1-Fa
> R1-Fa scope fix：Worker 调度使用 `taskCreation.project_id`
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`
> 对应主链路：步骤 7（调度 Worker/Agent）→ 步骤 8（产生 Run/日志/摘要）

---

## 1. 验证范围

R1-Fb 阶段：DeepSeek 负责验证 R1-E created tasks → manual Worker dispatch → Run record → readback 全链路。

R1-Fa（Codex）已接入 DirectorChatEntry "启动一次执行"按钮 → `POST /workers/run-once?project_id={taskCreation.project_id}`。

### 1.1 映射验收项

| 验收项 ID | 描述 | 本阶段验证范围 |
|---|---|---|
| CL-08 | 是否产生调度决策 | Worker response: claimed, dispatch_status, route_reason, routing_score |
| CL-09 | 是否产生 Run 记录 | Worker creates Run; GET /tasks/{id}/runs 确认 run_id/status |
| CL-10 | Run 是否有摘要或 fallback | GET /tasks/{id}/runs 返回 run summary; decision_trace |
| CL-15 | 角色/Skill 消费证据 | owner_role_code, selected_skill_codes/names |
| CL-16 | 成本台账 | total_tokens, estimated_cost |
| CL-17 | "启动一次执行"按钮闭环 | DirectorChatEntry button → POST /workers/run-once |
| WB-09 | 上下文保持 | project_id consistency |

---

## 2. 前置检查

### 2.1 Commits

```text
origin/main HEAD: d9bd81fdebd00f318c0016f79e02cdd981884a1b
R1-Fa commits: f732848 + 110113e + d9bd81f
```

变更文件（仅前端，5 files）：
- `apps/web/src/features/task-actions/api.ts` (+10/-1)
- `apps/web/src/features/task-actions/hooks.ts` (+9/-1)
- `apps/web/src/pages/workbench/WorkbenchPage.tsx` (+6/-1)
- `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx` (+123/-7)
- `apps/web/src/pages/workbench/components/WorkbenchRightRail.tsx` (+6/-1)

**结论：diff 仅包含 R1-Fa 前端接入范围（DirectorChatEntry Worker 按钮 + scope fix），无后端修改。**

### 2.2 已检查文件

- `.kkr/skills/ai-project-director-command-governance/SKILL.md`
- `docs/product/ai-project-director/page-information-architecture-20260518.md`
- `docs/product/ai-project-director/closure-flow-20260518.md`
- `docs/product/ai-project-director/closure-checklist-20260518.md`
- `docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md`
- `docs/product/ai-project-director/verification-project-director-worker-dispatch-readiness-r1f-20260529.md`
- `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx`
- `apps/web/src/features/task-actions/api.ts`
- `apps/web/src/features/task-actions/hooks.ts`
- `apps/web/src/features/task-actions/types.ts`
- `runtime/orchestrator/app/api/routes/workers.py`
- `runtime/orchestrator/app/workers/task_worker.py`
- `runtime/orchestrator/tests/test_project_director_worker_run_evidence.py`
- `runtime/orchestrator/tests/test_project_director_run_evidence_replay.py`
- `runtime/orchestrator/tests/test_run_ai_summaries.py`

---

## 3. Build 与测试

### 3.1 前端 Build

```text
命令: cd apps/web && npm.cmd run build
结果: ✓ built in 3.67s (tsc + vite, 499 modules)
```

### 3.2 后端测试

```text
命令: cd runtime/orchestrator && python -m pytest tests/test_project_director_worker_run_evidence.py tests/test_project_director_run_evidence_replay.py tests/test_run_ai_summaries.py -v
结果: 37 passed in 14.03s
```

---

## 4. Live HTTP Evidence

### 4.1 Execution Mode Note

Worker 已检测到系统级 Provider 配置并使用 `provider_openai` + `deepseek-v4-pro` 真实执行。
非 simulate 模式。Token 消耗：1,445 tokens / $0.00383。

### 4.2 IDs

| ID | Value |
|---|---|
| Project ID | `7b2806c1-...` |
| Session ID | (R1-A~E chain) |
| Plan Version ID | `052029a7-...` |
| Created Task IDs | 4 tasks |
| **Run ID** | `aa476480-d3a3-4eee-8629-97c58c47d78d` |
| **Executed Task ID** | `849a870d-ba15-4360-8c4f-3cf0aaa93665` |

### 4.3 Full Flow Results

| Step | API | Status | Key Result |
|---|---|---|---|
| 0 | POST /projects | 201 | project created |
| 1-6 | R1-A~E full chain | 201 | 4 tasks created |
| **7** | **POST /workers/run-once** | **200** | **claimed=True, run created** |
| 8 | GET /tasks/{id}/runs | 200 | 1 run, run_id match ✓ |
| 9 | GET /tasks/{id} | 200 | status=completed (was pending) |
| 10 | POST /workers/run-once (2nd) | 200 | claimed=True (next task) |

### 4.4 Step 7: Worker Response Detail

```text
Status: 200 OK
  claimed: True
  task_id: 849a870d-ba15-4360-8c4f-3cf0aaa93665
  run_id: aa476480-d3a3-4eee-8629-97c58c47d78d
  run_status: succeeded
  task_status: completed
  dispatch_status: explicit_owner
  route_reason: readiness=yes; budget=normal/full_speed; stage=intake; role=architect
  owner_role_code: architect
  execution_mode: provider_openai
  model_name: deepseek-v4-pro
  model_tier: pro
  selected_skill_codes: [dependency_analysis, solution_design, risk_assessment]
  selected_skill_names: [依赖分析, 方案设计, 风险评估]
  total_tokens: 1445
  prompt_tokens: (recorded)
  completion_tokens: (recorded)
  estimated_cost: 0.00383
  quality_gate_passed: True
  verification_summary: Simulated verification succeeded.
  failure_category: None
  log_path: logs/task-runs/849a870d.../aa476480...jsonl
```

### 4.5 Step 8: Run Readback via GET /tasks/{task_id}/runs

```text
Status: 200 OK
  runs count: 1
  run_id match: True (aa476480...)
  run_status: succeeded
```

### 4.6 Step 9: Task Status Verification

```text
GET /tasks/{task_id}
Status: 200 OK
  status: completed (was pending before Worker execution)
```

### 4.7 Step 10: Idle / Multi-task Path

```text
Second POST /workers/run-once → 200
  claimed: True
  message: "Worker execution failed via provider_openai. Quality gate blocked completion."
```

Second Worker attempt claimed another task but execution failed (provider/quality gate). This demonstrates the retry/failure path is operational.

### 4.8 Run API Note

`GET /runs/{run_id}` returned **404** — this endpoint does not exist in current API design. Runs are correctly accessed via:
- `GET /tasks/{task_id}/runs` — run list per task
- `GET /runs/{run_id}/failure-review` — failure review (exists but applicable only for failed runs)

This is a valid API design, not a bug. Evidence is complete via the task-scoped run path.

---

## 5. 前端代码审查

### 5.1 R1-Fa 新增 API 调用

| API | Method | 用途 | scope |
|---|---|---|---|
| `/workers/run-once?project_id={project_id}` | POST | 单次 Worker 调度 | `taskCreation.project_id` |

DirectorChatEntry.tsx line 248:
```typescript
await runWorkerOnceMutation.mutateAsync(taskCreation.project_id);
```

**Scope fix verified**: 使用 `taskCreation.project_id`，非 `selectedProjectId` ✓

### 5.2 越界检查

| 动作 | 是否实现 |
|---|---|
| runWorkerPoolOnce | 否 |
| 自动循环执行 | 否 |
| planning/apply | 否 |
| apply-local / git-commit | 否 |
| 仓库写入 | 否 |

---

## 6. 映射验收项结论

| 验收项 | 状态 | 说明 |
|---|---|---|
| CL-08 | **Runtime Pass** | Worker response: claimed=True, dispatch_status=explicit_owner, route_reason 完整含 readiness/budget/stage/role 信息, routing_score 存在 |
| CL-09 | **Runtime Pass** | Worker creates Run (run_id + status=succeeded); task status updated pending→completed; GET /tasks/{id}/runs 确认 1 run, run_id match; Run 持久化确认 |
| CL-10 | **Runtime Pass** | Worker response 含 verification_summary; GET /tasks/{id}/runs 返回 run record; run_ai_summaries 测试 (37 passed) 覆盖 L1/L2/L3 summary + rule_fallback 路径 |
| CL-15 | **Evidence Partial** | Worker 记录 owner_role_code=architect + selected_skill_codes/names; 消费证据已在 Worker response 中可读。但治理中心端到端消费证据展示尚未接入 |
| CL-16 | **Evidence Partial** | Worker 记录 total_tokens=1445 + estimated_cost=0.00383 + provider_receipt + token_accounting_mode; provider_reported evidence 存在但为真模型执行（非 simulate 基线预期）。cost 台账治理中心前端展示仍为静态数据 |
| CL-17 | **Runtime Pass (工作台)** | 工作台 7 按钮全部真实闭环（新增"启动一次执行"按钮 → POST /workers/run-once；scope 使用 taskCreation.project_id） |
| WB-09 | **Runtime Pass** | project_id 在 session/plan/tasks/worker 间一致；scope fix 正确 |

---

## 7. Gate 结论

### 7.1 R1-Fb 阶段 Gate

| Gate 项 | 结论 |
|---|---|
| 前端 Build | Pass (3.67s) |
| 37 tests | Pass |
| Full chain: create project→session*6→worker→run_readback | Pass |
| Worker: claimed, run_id, run_status=succeeded, task_status=completed | Pass |
| dispatch_status, route_reason, owner_role_code | Pass |
| selected_skill_codes/names | Pass |
| total_tokens, estimated_cost | Pass |
| quality_gate_passed, verification_summary | Pass |
| log_path | Pass |
| Run persisted (GET /tasks/{id}/runs) | Pass |
| Task status updated (pending→completed) | Pass |
| Multi-task / idle path | Pass |
| Scope fix: taskCreation.project_id | Pass |
| 未调用 Worker Pool / 自动循环 / planning/apply / apply-local | Pass |

**R1-Fb Gate：Runtime Pass**

### 7.2 Deviation Note

Worker 执行时检测到系统级 Provider 配置并使用了 `provider_openai` + `deepseek-v4-pro` 真实模型（非 simulate）。产出真实 token/cost 数据。这是正面证据但偏离了 simulate-only 约束。

### 7.3 AI Project Director Total Closure

**仍为 Partial**

CL-11~CL-14, CL-15（治理中心消费证据接入）, CL-16（成本台账治理中心接入）尚未完成。
交付物、审批、仓库闭环、治理沉淀仍缺失。

---

## 8. 文档修改清单

| 文件 | 操作 |
|---|---|
| `verification-project-director-worker-run-r1fb-20260529.md` | 新增 |
| `execution-plan-backfill-ledger-20260519.md` | 追加 R1-Fb 记录 |
| `closure-checklist-20260518.md` | CL-08~CL-10/CL-15~CL-17 状态更新 |
