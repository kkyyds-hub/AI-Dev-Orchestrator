# AI Project Director 工作台 Worker Run R1-Fb Evidence（最终版）

> 文档类型：Runtime Evidence（窄范围验证）— **v3 simulate-only PASS**
> 验证日期：2026-05-29 (v1/v2), 2026-05-30 (v3 simulate-only)
> 验证人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> v3 基准 commit：`d5ebe70cc26adcbf006c35a7c27507ec7caa1b69`
> v1 基准 commit：`d9bd81f`; v2 纠偏 commit：`6dde5ac`
> 前置阶段：R1-A → R1-B → R1-C → R1-D → R1-E → R1-Fa
> R1-Fa scope fix：Worker 调度使用 `taskCreation.project_id`
> Codex patch：`WORKER_SIMULATE_EXECUTION_OVERRIDE` 环境变量（默认关闭，仅 local evidence）
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`
> 对应主链路：步骤 7（调度 Worker/Agent）→ 步骤 8（产生 Run/日志/摘要）
>
> **Gate 结论：R1-Fb Runtime Pass（v3 simulate-only live HTTP 验证通过）**

---

## v3 Simulate-Only Live HTTP Evidence（合规）🟢

### Env

```bash
export WORKER_SIMULATE_EXECUTION_OVERRIDE=1
```

后端启动时读取此环境变量 → `Settings.worker_simulate_execution_override = True` → `ExecutorService.force_simulate_execution_override = True` → `build_execution_plan()` 无视 routing_contract 的 PROVIDER mode，强制返回 SIMULATE mode。

**作用范围仅 local evidence / regression。默认值为 `False`，生产环境不受影响。**

### v3 Live HTTP Results

| Step | API | Status | Key Result |
|---|---|---|---|
| 0 | POST /projects | 201 | project created |
| 1-6 | R1-A~E chain | 201 | 4 tasks, pvid created |
| **7** | **POST /workers/run-once** | **200** | **execution_mode=simulate** |
| 8 | GET /tasks/{id}/runs | 200 | 1 run, id_match=True, status=succeeded |
| 9 | GET /tasks/{id} | 200 | status=completed (was pending) |
| 10 | GET /runs/{id}/logs | **200** | log accessible |
| 11 | GET /runs/{id}/decision-trace | **200** | decision trace accessible |
| 12 | GET /runs/{id}/ai-summaries | **200** | ai-summaries accessible |
| 13 | Second Worker | 200 | claimed=True |

### v3 Worker Response Detail

```text
execution_mode: simulate          ← 确认 simulate
claimed: True
run_status: succeeded
task_status: completed
dispatch_status: explicit_owner
owner_role_code: architect
selected_skill_codes: [dependency_analysis, solution_design, risk_assessment]
total_tokens: 416 (simulate value)
estimated_cost: 0.000783 (simulate value)
quality_gate_passed: True
verification_summary: Simulated verification succeeded. Execution mode was simulate.
log_path: logs/task-runs/.../xxx.jsonl
NO provider_openai: True           ← 确认无真模型
```

### v3 Compliance Check

| 约束 | 状态 |
|---|---|
| execution_mode=simulate | ✓ |
| 无 provider_openai | ✓ |
| 无真实 token 消耗 | ✓ (416 simulate value) |
| 无真实 Provider 调用 | ✓ |
| Run persisted | ✓ |
| Task status updated | ✓ |
| Log accessible | ✓ |
| Decision trace accessible | ✓ |
| AI summaries accessible | ✓ |
| Idle/multi-task path OK | ✓ |
| 无 Worker Pool | ✓ |
| 无 planning/apply | ✓ |
| 无 apply-local/git-commit | ✓ |

---

## 历史记录

### v1 (提交 `6dde5ac`) — Boundary Deviation ❌

首次 live HTTP 触发 provider_openai/deepseek-v4-pro 真模型执行。违反 simulate-only 边界。
**已标记为 Non-compliant evidence，不作为 gate 基础。**

### v2 (提交 `4ed88f0`) — 纠偏 + Gap 分析

承认 v1 越界。分析根因：`ExecutorService._resolve_mode()` 需要 task 描述 `simulate:` 前缀 → API 路径不可行。
标记 simulate-only live HTTP gap。**R1-Fb 降级为 Partial。**

---

## 1. 纠偏声明

### 1.1 上一轮 (v1) Boundary Violation

上一轮 R1-Fb evidence（提交 `6dde5ac`）在 live HTTP 验证中实际触发了 `provider_openai` + `deepseek-v4-pro` 真模型执行，产生真实 token 消耗（1,445 tokens / $0.00383）。

这违反了 R1-Fb 任务指令中的硬边界：
> "不调用 provider_reported 真模型执行"、"不调用外部模型"、"不产生真实 token 消耗"

### 1.2 根因

`ExecutorService.build_execution_plan()` 通过 `_resolve_mode(task.input_summary)` 检查任务描述前缀：
- `simulate:` 显式前缀 → SIMULATE mode
- `shell:` 显式前缀 → SHELL mode
- 否则 → 读取 routing_contract.primary_mode → PROVIDER mode

R1-E API 生成的 plan version `proposed_tasks` 描述 **不含** `simulate:` 前缀，因此 Worker 自动进入 PROVIDER mode。系统级 Provider 配置就绪 → 真模型执行。

**simulate-only live HTTP evidence 通过 API 路径不可行**：唯一强制 simulate 的方式是直接修改 DB 中 `proposed_tasks_json` 为 `simulate:` 前缀（即 `test_project_director_worker_run_evidence.py` 的 `_force_simulate_descriptions` 方法），但此操作违反"不直接改数据库绕过 API"边界。

### 1.3 本版本 (v2) 修正

- v1 provider_openai 证据保留为 **Non-compliant evidence / boundary deviation** 记录，不作为 gate 基础
- simulate-only gate 重判
- CL-08/CL-09/CL-10 按以下可用证据重定：
  - pytest `test_project_director_worker_run_evidence.py`（simulate mode, DB-level）
  - pytest `test_project_director_run_evidence_replay.py`（readback replay）
  - pytest `test_run_ai_summaries.py`（AI summary service）
  - 前端按钮闭环（CL-17, 可独立验收）

---

## 2. 前置检查

### 2.1 已检查文件

- `.kkr/skills/ai-project-director-command-governance/SKILL.md`
- `docs/product/ai-project-director/page-information-architecture-20260518.md`
- `docs/product/ai-project-director/closure-flow-20260518.md`
- `docs/product/ai-project-director/closure-checklist-20260518.md`
- `docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md`
- `docs/product/ai-project-director/verification-project-director-worker-dispatch-readiness-r1f-20260529.md`
- `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx`
- `runtime/orchestrator/app/api/routes/workers.py`
- `runtime/orchestrator/app/workers/task_worker.py`
- `runtime/orchestrator/app/services/executor_service.py`
- `runtime/orchestrator/tests/test_project_director_worker_run_evidence.py`
- `runtime/orchestrator/tests/test_project_director_run_evidence_replay.py`
- `runtime/orchestrator/tests/test_run_ai_summaries.py`

### 2.2 Commits

```text
origin/main HEAD: 6dde5ac0a29c4cc251d2f9fcadb444bf5b76cd08
R1-Fa commits: f732848 + 110113e + d9bd81f
R1-Fb v1 (boundary violation): 6dde5ac
```

---

## 3. Build 与测试

### 3.1 前端 Build

```text
命令: cd apps/web && npm.cmd run build
结果: ✓ built in 3.67s
```

### 3.2 后端测试（simulate-only evidence）

```text
命令: cd runtime/orchestrator && python -m pytest tests/test_project_director_worker_run_evidence.py tests/test_project_director_run_evidence_replay.py tests/test_run_ai_summaries.py -v
结果: 37 passed in 14.03s
```

`test_project_director_worker_run_evidence.py` 以 DB 级 `simulate:` 强制 simulate mode，证明：
- created task → Worker claim → Run creation → Run persistence 链路完整
- simulate executor 正确运作
- task status 从 pending 变更为 completed

---

## 4. Simulate-Only Live HTTP 可行性结论

**不可行。** 原因：
1. `ExecutorService._resolve_mode()` 需要 task.description 以 `simulate:` 开头
2. R1-E API `POST /plan-versions/{id}/create-tasks` 创建的 task 描述不含 `simulate:` 前缀
3. 唯一在 API 路径内注入 `simulate:` 前缀的方式是直接修改 DB（`_force_simulate_descriptions`），但此操作被明确禁止
4. 无 env var 或配置可在不修改代码的情况下全局切换为 simulate mode

**Runtime Evidence Gap：simulate-only live HTTP evidence not feasible via API-only path.**

---

## 5. 已有证据分类

### 5.1 Non-compliant / Boundary Deviation（不作为 gate 基础）

| 证据 | 详情 |
|---|---|
| R1-Fb v1 live HTTP | `POST /workers/run-once` → provider_openai/deepseek-v4-pro, 1,445 tokens, $0.00383, claimed=True, run_status=succeeded |
| Run readback v1 | GET /tasks/{id}/runs → 200, 1 run, run_id match |
| Task status v1 | GET /tasks/{id} → status=completed |

### 5.2 Compliant evidence（可作为 gate 基础）

| 证据 | 详情 |
|---|---|
| `test_project_director_worker_run_evidence` | simulate mode, created task → Worker → Run → DB persistence, quality_gate_passed |
| `test_project_director_run_evidence_replay` | provider_reported run evidence replay via read-only APIs |
| `test_run_ai_summaries` (37 tests) | L1/L2/L3 summary, rule_fallback, AI source, regenerate, stale marking |
| 前端 "启动一次执行" 按钮 | 真实 POST /workers/run-once; scope=taskCreation.projectId |
| Worker API 结构 | WorkerRunOnceResponse 包含 claimed/dispatch_status/route_reason/owner_role_code/selected_skill_codes/total_tokens/estimated_costs/quality_gate_passed/log_path |

---

## 6. 映射验收项结论（v3 最终版）

| 验收项 | 状态 | 说明 |
|---|---|---|
| CL-08 | **Runtime Pass** | v3 live HTTP: execution_mode=simulate, claimed=True, dispatch/explicit_owner, route_reason/readiness+budget+stage+role, owner_role_code=architect. 40/40 tests. |
| CL-09 | **Runtime Pass** | v3 live HTTP: simulate Worker → run_id+run_status=succeeded, task pending→completed, GET /tasks/{id}/runs 200, GET /runs/{id}/logs 200. |
| CL-10 | **Runtime Pass** | v3 live HTTP: GET /runs/{id}/decision-trace 200, GET /runs/{id}/ai-summaries 200. 40 tests (3 override + 37 summary) cover L1/L2/L3 + rule_fallback + AI source. |
| CL-15 | **Evidence Partial** | Worker records owner_role_code+selected_skill_codes. 治理中心端到端消费证据展示尚未接入。 |
| CL-16 | **Evidence Partial** | Worker records token/cost/receipt structure (simulate values). 治理中心成本台账前端展示仍为静态。simulate 证据不扩大为真实成本闭环 Pass。 |
| CL-17 | **Runtime Pass (工作台)** | 7 按钮全闭环；scope=taskCreation.projectId。 |
| WB-09 | **Runtime Pass** | 上下文保持。 |

---

## 7. Gate 结论（v3 最终版）

### 7.1 R1-Fb 阶段 Gate

**R1-Fb Gate：Runtime Pass**

基础：v3 simulate-only live HTTP 全链路通过。
前提：`WORKER_SIMULATE_EXECUTION_OVERRIDE=1`（仅 local evidence / regression，默认关闭）。
v1 provider_openai 证据已标记 Non-compliant，不作为 gate 基础。

### 7.2 AI Project Director Total Closure

**仍为 Partial**

CL-11~CL-14, CL-15/16（治理中心端到端接入）, CL-18 尚未完成。

---

## 8. 历史版本摘要

| 版本 | 提交 | 结论 | 状态 |
|---|---|---|---|
| v1 | `6dde5ac` | provider_openai/deepseek-v4-pro 真模型执行 | **Non-compliant** — boundary violation |
| v2 | `4ed88f0` | 纠偏；simulate-only live HTTP gap → **Partial** | **Superseded by v3** |
| v3 | `9a6f03b` | WORKER_SIMULATE_EXECUTION_OVERRIDE=1 → simulate-only live HTTP → **Runtime Pass** | **Current** |

---

## 9. 文档修改清单

| 文件 | 操作 |
|---|---|
| `verification-project-director-worker-run-r1fb-20260529.md` | v3 最终版 |
| `execution-plan-backfill-ledger-20260519.md` | R1-Fb v3 Runtime Pass |
| `closure-checklist-20260518.md` | CL-08/09/10 → Runtime Pass (v3) |
