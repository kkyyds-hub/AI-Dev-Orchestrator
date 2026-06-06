# AI Project Director Cost Ledger Closure R1-L Audit

> 文档类型：Cost ledger closure audit + live HTTP + tests + frontend build
> 审计日期：2026-05-31
> 审计人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commit：`1c9009b`
> 前置阶段：R1-K Runtime Pass (CL-15 role/skill consumption)
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`
> 对应验收项：CL-16（AI 生成是否记录成本台账）

---

## 1. 审计范围

验证 CL-16：AI 生成 / Worker 执行是否记录模型、来源、缓存、token、成本，并能在成本治理中心端到端 readback。

### 1.1 已检查文件

**Backend:**
- `runtime/orchestrator/app/workers/task_worker.py` (token_accounting / cost_estimator → Run persistence)
- `runtime/orchestrator/app/services/token_accounting_service.py`
- `runtime/orchestrator/app/services/cost_estimator_service.py`
- `runtime/orchestrator/app/services/budget_guard_service.py`
- `runtime/orchestrator/app/services/context_budget_service.py`
- `runtime/orchestrator/app/api/routes/workers.py` (WorkerRunOnceResponse cost fields)
- `runtime/orchestrator/app/api/routes/projects.py` (cost-dashboard endpoint)
- `runtime/orchestrator/app/api/routes/runs.py` (run log + ai-summaries)

**Frontend:**
- `apps/web/src/features/costs/api.ts` (fetchProjectCostDashboardSnapshot)
- `apps/web/src/features/costs/hooks.ts` (useProjectCostDashboardSnapshot)
- `apps/web/src/features/costs/types.ts` (ProjectCostDashboardSnapshot + breakdown types)
- `apps/web/src/pages/governance/GovernancePage.tsx` (CostMemoryTab)

---

## 2. Cost Ledger Chain Components

### 2.1 L1: Worker Execution → Token Accounting

Worker 管线 (`task_worker.py`):

```python
# Token accounting from prompt + completion
token_accounting = self.token_accounting_service.build_snapshot(
    prompt_envelope=prompt_envelope,
    completion_text=...,
    execution_mode=execution.mode,
    provider_usage_receipt=execution.provider_usage_receipt,
)
# Cost estimation
cost_estimate = self.cost_estimator_service.estimate_run_cost(
    task=task, execution=execution, ...
)
# Persist to Run
updated_run = self.run_repository.finish_run(
    ..., total_tokens=..., estimated_cost=...,
    token_pricing_source=...,
    provider_receipt_id=...,
    cache_read_tokens=..., cache_write_tokens=..., cache_hit=...,
)
```

### 2.2 L2: Run Persistence Fields

| Field | Source | Description |
|---|---|---|
| model_name | StrategyEngine / Routing | deepseek-v4-pro |
| provider_key | TokenAccountingSnapshot | None (simulate mode) |
| total_tokens | TokenAccountingSnapshot | prompt + completion |
| prompt_tokens | TokenAccountingSnapshot | 683 |
| completion_tokens | TokenAccountingSnapshot | 353 |
| estimated_cost | CostEstimate | $0.002 (heuristic) |
| token_pricing_source | TokenAccountingSnapshot | heuristic.simulate.char_count.v1 |
| token_accounting_mode | TokenAccountingSnapshot | heuristic |
| cache_read_tokens | TokenAccountingSnapshot | 0 |
| cache_write_tokens | TokenAccountingSnapshot | 0 |
| cache_hit | TokenAccountingSnapshot | false |
| provider_receipt_id | TokenAccountingSnapshot | None (simulate) |

### 2.3 L3: Cost Dashboard API

`GET /projects/{project_id}/cost-dashboard` → `ProjectCostDashboardSnapshotResponse`

```json
{
  "project_id": "UUID",
  "run_count": 6,
  "total_estimated_cost_usd": 0.010597,
  "avg_estimated_cost_per_run_usd": 0.001766,
  "prompt_tokens": 3588,
  "completion_tokens": 1738,
  "total_tokens": 5326,
  "mode_breakdown": [
    {"mode": "heuristic", "run_count": 6, "total_estimated_cost_usd": 0.010597, "total_tokens": 5326}
  ],
  "role_breakdown": [
    {"role_code": "engineer", "run_count": 3, "total_estimated_cost_usd": 0.006241},
    ...
  ],
  "thread_breakdown": [...],
  "cache_summary": {"total_memories": 12, ...},
  "fallback_contract": {
    "fallback_active": true,
    "provider_reported_run_count": 0,
    "heuristic_run_count": 6
  },
  "budget_policy_source": "not_configured"
}
```

Key evidence: the cost dashboard reads from real Run history, not static data. The `fallback_contract` honestly reports 0 provider_reported runs.

### 2.4 L4: GovernancePage CostMemoryTab

Frontend `GovernancePage.tsx` CostMemoryTab (lines 633-687):
- Uses `useProjectCostDashboardSnapshot(projectId)` → real API
- Displays: 累计费用 ($0.0106), 运行次数 (6), Token 总数 (5326)
- Source credibility: "成本数据来源可信度：provider_reported / heuristic / missing"
- Shows: "当前读取自成本仪表板 API（真实数据）" when data exists
- Shows: "未接入" when no data
- Memory buttons (Compact/Rehydrate/Reset) correctly disabled with explanation

---

## 3. Live HTTP Evidence

> Backend: `WORKER_SIMULATE_EXECUTION_OVERRIDE=1`; 6 total runs under this project (3 CL-15 + 3 CL-16)

### Worker Response (cost fields per run)

| Run | mode | total_tokens | estimated_cost | model_name |
|---|---|---|---|---|
| 1 | simulate | 1031 | $0.002073 | deepseek-v4-pro |
| 2 | simulate | 1036 | $0.002084 | deepseek-v4-pro |
| 3 | simulate | 1036 | $0.002084 | deepseek-v4-pro |

### Cost Dashboard

```
run_count=6, total_cost=$0.010597, avg_cost=$0.001766
prompt_tokens=3588, completion_tokens=1738, total_tokens=5326
fallback: active=True, provider_reported=0, heuristic=6
mode_breakdown: heuristic ×6
role_breakdown: engineer×3 ($0.006241), architect×2 ($0.002280), reviewer×1 ($0.002076)
token_pricing_source: heuristic.simulate.char_count.v1
```

### Run Readback

```
GET /tasks/{id}/runs → total_tokens=1036, estimated_cost=0.002084
                     → token_accounting_mode=heuristic
                     → token_pricing_source=heuristic.simulate.char_count.v1
```

---

## 4. Tests

```bash
python -m pytest tests/test_project_director_worker_run_evidence.py tests/test_project_director_run_evidence_replay.py tests/test_run_ai_summaries.py -q
→ 37 passed in 8.26s
```

### Frontend Build

```
cd apps/web && npm.cmd run build → built in 3.62s
```

---

## 5. Cost Source Credibility

| Source | Meaning | This Audit |
|---|---|---|
| provider_reported | 真实 provider API 返回的 usage 字段 | 0 runs (simulate mode, no provider call) |
| heuristic | 估算（字符数 / token 比率估算） | 6 runs (simulate mode) |
| missing | 无成本记录 | 0 runs |

**Simulate costs are heuristic estimates ($0.001-0.002/run). These demonstrate the cost ledger STRUCTURE is complete but DO NOT represent real provider costs. Previous provider_openai evidence was already marked Non-compliant.**

---

## 6. CL-16 Status

**Evidence Partial** (unchanged from previous baseline — structure verified, values are heuristic)

| Item | Status | Evidence |
|---|---|---|
| Worker → Run token/cost persistence | **Runtime Pass** | total_tokens, estimated_cost, token_pricing_source, provider_key all in Run |
| Cost Dashboard API | **Runtime Pass** | GET /projects/{pid}/cost-dashboard reads Run history, not static |
| Mode breakdown | **Runtime Pass** | heuristic mode correctly identified |
| Role breakdown | **Runtime Pass** | engineer×3, architect×2, reviewer×1 |
| Fallback contract | **Runtime Pass** | Honest: 0 provider_reported, 6 heuristic |
| Cache summary | **Runtime Pass** | 12 memories reported |
| GovernancePage CostMemoryTab | **Runtime Pass** | Real API, displays cost/run/token; source credibility explained |
| **Provider cost values** | **Evidence Partial** | Simulate costs are heuristic ($0.002/run), not real provider costs |

### Gap

The cost ledger STRUCTURE is complete from Worker→Run→Cost Dashboard→GovernancePage. However, all costs are heuristic (simulate mode). Real provider cost verification requires explicit user permission to call a live provider. CL-16 stays Evidence Partial until real provider costs are verified.

---

## 7. Gate Conclusion

### 7.1 R1-L Gate

**Evidence Partial**

Cost ledger structure (Worker→Run→Cost Dashboard→GovernancePage CostMemoryTab) is complete and verified via live HTTP + frontend build. All 6 runs are heuristic (simulate mode). Real provider cost verification requires live provider execution. Previous provider_openai evidence remains Non-compliant.

### 7.2 AI Project Director Total Closure

**仍为 Partial**

CL-18（文档闭环）尚未完成。
