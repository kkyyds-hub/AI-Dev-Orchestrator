# AI Project Director Role / Skill Consumption Evidence R1-K Audit

> 文档类型：Role/Skill consumption evidence audit + live HTTP + gap analysis
> 审计日期：2026-05-30
> 审计人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commit：`983be15`
> 前置阶段：R1-J Runtime Pass (CL-14 approval closure)
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`
> 对应验收项：CL-15（角色/Skill 是否记录消费证据）

---

## 1. 审计范围

验证 CL-15：角色/Skill 不是只保存配置，而是真正在 Worker 调度和 Run 证据里被消费，并能被治理中心或证据 API readback。

### 1.1 已检查文件

- `runtime/orchestrator/app/workers/task_worker.py` (WorkerRunResult ~1100 行)
- `runtime/orchestrator/app/api/routes/workers.py` (Worker API response)
- `runtime/orchestrator/app/api/routes/tasks.py` (Task/Run console response)
- `runtime/orchestrator/app/api/routes/runs.py` (Decision-trace response)
- `runtime/orchestrator/app/api/routes/roles.py` (Role catalog + project role configs)
- `runtime/orchestrator/app/api/routes/skills.py` (Skill registry + bindings)
- `runtime/orchestrator/app/services/role_catalog_service.py`
- `runtime/orchestrator/app/services/skill_registry_service.py`
- `runtime/orchestrator/app/services/strategy_engine_service.py`
- `apps/web/src/pages/governance/GovernancePage.tsx` (Frontend governance)

---

## 2. Role / Skill Consumption Evidence: Three-Layer Analysis

### 2.1 L1: Worker Dispatch (Runtime Evidence)

Worker 调度时，`task_worker.py:run_once()` 通过 `TaskRouterService` + `StrategyEngineService` 产生：

| Field | Source | Live HTTP Value |
|---|---|---|
| owner_role_code | StrategyEngine → TaskRouter | **architect** |
| upstream_role_code | Routing decision | **product_manager** |
| downstream_role_code | Routing decision | **engineer** |
| dispatch_status | Routing decision | **explicit_owner** |
| handoff_reason | Routing decision | "任务已显式指定责任角色「架构师」..." |
| selected_skill_codes | StrategyEngine | `["dependency_analysis", "solution_design", "risk_assessment"]` |
| selected_skill_names | StrategyEngine | `["依赖分析", "方案设计", "风险评估"]` |
| strategy_code | StrategyEngine | `se-intake-architect-balanced-normal` |
| strategy_summary | StrategyEngine | "需求 Intake 阶段优先由 架构师 承接..." |
| model_name | StrategyEngine | `deepseek-v4-pro` |
| model_tier | StrategyEngine | `balanced` |
| route_reason | TaskRouter | readiness/budget/stage/roles composite |
| routing_score | TaskRouter | 350.0 |

### 2.2 L2: Run Persistence + Readback

Run 表持久化所有路由和策略数据，并通过三个路径可读回：

**Path 1: Worker Response** (`POST /workers/run-once`)
```
owner_role_code=architect
selected_skill_codes=["dependency_analysis", "solution_design", "risk_assessment"]
strategy_code=se-intake-architect-balanced-normal
```

**Path 2: Decision-Trace** (`GET /runs/{id}/decision-trace`)
```
[routing] task_routed: owner_role_code=architect, selected_skill_codes=[...], model_tier=balanced
[handoff] role_handoff: product_manager -> architect -> engineer
```

**Path 3: Task/Runs Console** (`GET /tasks/{id}/runs`)
```
owner_role_code=architect
strategy_decision.selected_skill_codes=["dependency_analysis", ...]
strategy_decision.role_policy_source=budget_fallback
```

所有三个 readback 路径数据一致。

### 2.3 L3: Governance Center (FRONTEND GAP)

治理中心前端 (`GovernancePage.tsx`):

| Tab | Role/Skill Consumption Display |
|---|---|
| 本项目 AI 团队 (team) | "基于角色目录静态基线，待接入真实运行时消费证据" |
| 角色治理 (roles) | "最近消费证据" → **"暂无消费证据"** |
| Skill 治理 (skills) | "最近消费证据" → **"暂无消费证据"** |

后端 roles 和 skills 路由仅提供 CRUD（角色配置、Skill 定义/绑定），无消费统计聚合 API。

---

## 3. Gap Analysis

| 层级 | 状态 | 说明 |
|---|---|---|
| Worker dispatch (owner_role_code) | **Runtime Pass** | Live HTTP 验证 architect, handoff chain |
| Worker dispatch (selected_skill_codes) | **Runtime Pass** | Live HTTP 验证 3 skills selected |
| Run persistence (all role/skill fields) | **Runtime Pass** | Persisted to Run, read-back via 3 paths |
| Decision-trace (role_handoff + routing) | **Runtime Pass** | role_handoff event, routing event with skills |
| Task/Runs console API | **Runtime Pass** | strategy_decision.selected_skill_codes present |
| **Governance aggregation API** | **Missing** | No API that reads run-history role/skill consumption by project |
| **Governance center frontend** | **Not connected** | Static config display; "暂无消费证据" everywhere |

---

## 4. 最小补丁点 (for Codex)

要将 CL-15 从 Evidence Partial 升为 Runtime Pass，Codex 需要：

1. **最小后端补丁**：在 `/roles` 或 `/skills` 路由加一个聚合端点（例如 `GET /roles/projects/{pid}/consumption`），从项目下所有 Run 的 `owner_role_code` / `selected_skill_codes` 聚合消费统计。

2. **最小前端补丁**：治理中心 "最近消费证据" 改为真实读取上述聚合 API，展示每个角色/Skill 的最近调用次数、最近调用时间。

---

## 5. Tests

```bash
python -m pytest tests/ -q
→ 163 passed in 38.79s (full suite)
```

Role/Skill dispatch 通过 full suite 间接覆盖。

---

## 6. CL-15 Status

**Evidence Partial** (unchanged from previous baseline)

- Worker/Run level: role and skill consumption evidence exists and is read-back-able via 3 paths (worker response, decision-trace, task/runs console)
- Governance center: frontend shows static config only ("暂无消费证据"); no consumption aggregation API exists
- Gap is specifically in governance aggregation API + frontend consumption display
- Backend data chain is complete; frontend display chain is missing

---

## 7. Gate Conclusion

### 7.1 R1-K Gate

**Evidence Partial**

Worker dispatch → Run persistence → multi-path readback chain is complete and verified via live HTTP. Governance center end-to-end consumption display is not yet implemented; requires a governance aggregation API and frontend wiring.

### 7.2 AI Project Director Total Closure

**仍为 Partial**

CL-16（成本闭环端到端接入）、CL-18 尚未完成。
