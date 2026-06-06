# AI Project Director Worker Dispatch Readiness Audit R1-F

> 文档类型：只读现状审计
> 审计日期：2026-05-29
> 审计人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commit：`7fe5cfd82047b38cc52d8c21bd6dcfd6d952e46a`
> 前置阶段：R1-A (session) → R1-B (clarify) → R1-C (plan) → R1-D (confirm) → R1-E (tasks)
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`

---

## 1. 审计目的

R1-E 已完成 confirmed plan → create-tasks → pending task queue 的 Runtime Pass。下一步（R1-F）需要验证 Worker/Agent 调度 → Run 生成链路。

本次审计只读，不改代码。目标：
- 识别当前已有的 Worker/Run/Log/Summary/Rework 能力
- 区分已有后端 / 已有前端 / 已有测试 / 已有 evidence
- 判断下一步交给 DeepSeek (evidence) 还是 Codex (最小前端接入)
- 识别高风险动作

---

## 2. 已检查文件

| 类别 | 文件 | 状态 |
|---|---|---|
| Governance | `.kkr/skills/ai-project-director-command-governance/SKILL.md` | 已读 |
| Product | `docs/product/ai-project-director/page-information-architecture-20260518.md` | 已读 |
| Product | `docs/product/ai-project-director/closure-flow-20260518.md` | 已读 |
| Product | `docs/product/ai-project-director/closure-checklist-20260518.md` | 已读 |
| Product | `docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md` | 已读 |
| Evidence | `verification-project-director-workbench-task-creation-r1e-20260528.md` | 已读 |
| Evidence | `verification-project-director-created-task-worker-run-phase1-20260524.md` | 已读 |
| Backend | `runtime/orchestrator/app/api/routes/workers.py` | 已读 |
| Backend | `runtime/orchestrator/app/workers/task_worker.py` | 已读 |
| Backend | `runtime/orchestrator/app/core/db_tables.py` (TaskTable/RunTable) | 已读 |
| Backend | `runtime/orchestrator/app/api/routes/project_director.py` | 已读 |
| Test | `tests/test_project_director_worker_run_evidence.py` | 存在 |
| Test | `tests/test_project_director_run_evidence_replay.py` | 存在 |
| Test | `tests/test_run_ai_summaries.py` | 存在 |
| Test | `tests/test_approval_rework_task_creation.py` | 存在 |
| Frontend | `apps/web/src/features/task-actions/api.ts` (runWorkerOnce) | 存在 |
| Frontend | `apps/web/src/pages/workbench/components/WorkbenchRightRail.tsx` (Worker按钮) | 存在 |
| Frontend | `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx` (R1-A~E) | 存在 |

---

## 3. Worker / Agent 调度相关 API 清单

### 3.1 后端

| API | Method | 位置 | 用途 | 状态 |
|---|---|---|---|---|
| `/workers/run-once` | POST | `routes/workers.py:325` | 单次 Worker 循环（支持 project_id scope） | **已有** |
| `/workers/run-pool-once` | POST | `routes/workers.py:343` | Worker Pool 批量调度 | **已有** |

### 3.2 Worker Pipeline（task_worker.py）

`TaskWorker.run_once()` 完整链路：

```
pending task → TaskRouterService (路由评分 + role_code/strategy)
  → TaskStateMachineService (状态转换 pending→in_progress)
  → RunRepository (创建 Run, status=queued→running)
  → ContextBuilderService (构建上下文包)
  → ExecutorService (执行, support simulate/provide)
  → VerifierService (质量闸门)
  → RunLoggingService (日志写盘)
  → TaskStateMachineService (completed/failed)
  → BudgetGuardService (成本闸门)
  → event_stream_service (事件发布)
```

### 3.3 Worker 响应内容（WorkerRunOnceResponse）

单次 Worker 响应包含以下域：
- **调度决策**: claimed, route_reason, routing_score, routing_score_breakdown, dispatch_status
- **角色信息**: owner_role_code, upstream_role_code, downstream_role_code, handoff_reason
- **Skill 绑定**: selected_skill_codes, selected_skill_names
- **模型信息**: model_name, model_tier, strategy_code
- **Run 信息**: task_id, run_id, run_status, run_created_at, run_finished_at
- **Token/Cost**: total_tokens, prompt_tokens, completion_tokens, estimated_cost, provider_key
- **失败分类**: failure_category
- **质量闸门**: quality_gate_passed, verification_summary
- **Budget**: budget_pressure_level, budget_action
- **Memory**: project_memory_enabled, memory_governance_*
- **Agent**: agent_session_id, agent_session_status

### 3.4 前端

| 入口 | 位置 | 用途 | 状态 |
|---|---|---|---|
| WorkbenchRightRail "触发 Worker 单次调度" | `WorkbenchRightRail.tsx:158` | POST /workers/run-once with selectedProjectId | **已有** |
| HomeHeader "触发 Worker" | `HomeHeaderSection.tsx:52` | POST /workers/run-once | **已有** |
| MemoryGovernance "触发 Worker" | `MemoryGovernanceSection.tsx:453` | POST /workers/run-once with project_id | **已有** |
| **DirectorChatEntry 内无 Worker 按钮** | N/A | R1-A~E 链路不包含 Worker 调度 | **缺失 — R1-F 需要** |
| task-actions/api.ts | `features/task-actions/api.ts:10` | `runWorkerOnce()`, `runWorkerPoolOnce()` | **已有** |

---

## 4. Run 生成相关 API / Service / DB 表清单

### 4.1 Run DB 表（RunTable）

关键字段：
- `id` (UUID PK), `task_id` (FK→tasks)
- `status` (RunStatus: queued/running/succeeded/failed/blocked)
- `model_name`, `route_reason`, `routing_score`, `routing_score_breakdown`
- `owner_role_code`, `upstream_role_code`, `downstream_role_code`
- `total_tokens`, `prompt_tokens`, `completion_tokens`, `estimated_cost`
- `provider_key`, `provider_receipt_id`, `token_accounting_mode`
- `execution_mode` (simulate / provider), `verification_mode`
- `failure_category`, `quality_gate_passed`
- `log_path` (文件系统日志路径)
- `created_at`, `finished_at`, `updated_at`

### 4.2 Run Logging Service

`app/services/run_logging_service.py` — 日志写盘服务。

### 4.3 Run Summary

- `L1` 短摘要 (run.summary): Worker 执行后自动生成
- `L2` 结构化判断
- `L3` 高价值决策
- `source=ai / rule_fallback / reused`
- GET /runs/{run_id} 返回 run summary + decision trace

### 4.4 Run Read API

| API | Method | 用途 | 状态 |
|---|---|---|---|
| `/runs/{run_id}` | GET | Run 详情含 summary/log/decision-trace | **已有** |
| `/tasks/{task_id}/runs` | GET | Task 的 Run 列表 | **已有** |

---

## 5. 失败/阻塞/返工机制

### 5.1 后端

| 能力 | 位置 | 证据 |
|---|---|---|
| failure_category | RunTable | RunDomain failure_category 枚举 |
| retry/rework/human/replan | TaskStateMachine | 状态机支持 reroute/retry |
| approval rework | `test_approval_rework_task_creation.py` | 审批要求修改→生成返工任务 (BCG-10) |
| human review | `POST /tasks/{id}/request-human` | 请求人工介入 |
| blocking reason | TaskBlockingReasonCode | 阻塞原因编码 |

### 5.2 已有 Evidence

- `test_project_director_worker_run_evidence.py` — simulate mode created-task → Worker → Run
- `test_project_director_run_evidence_replay.py` — provider_reported run evidence replay
- `test_approval_rework_task_creation.py` — approval rework → task creation

---

## 6. 角色/Skill 消费证据与成本台账

### 6.1 角色/Skill

| 数据 | 位置 | 状态 |
|---|---|---|
| owner_role_code | RunTable, WorkerRunOnceResponse | Worker 执行后记录 |
| selected_skill_codes/names | WorkerRunOnceResponse | Worker 执行后记录 |
| role_model_policy_* | WorkerRunOnceResponse | 模型策略决策记录 |
| 治理中心角色/Skill 展示 | GovernancePage | Partial（前端已展示，消费证据待后端接入） |

### 6.2 成本台账

| 数据 | 位置 | 状态 |
|---|---|---|
| total_tokens, estimated_cost | RunTable, WorkerRunOnceResponse | Worker 执行后记录 |
| provider_receipt_id | RunTable | Provider 回执 ID |
| token_accounting_mode | RunTable | provider_reported / heuristic |
| 治理中心成本展示 | GovernancePage | Partial（前端已展示，数据源静态） |

---

## 7. CL-08 ~ CL-17 当前状态判断

| ID | 当前状态 | 判断依据 |
|---|---|---|
| **CL-08** | **Evidence Partial** | 后端调度 API 完整 (`POST /workers/run-once`)；前端 WorkbenchRightRail 已有 Worker 按钮；**缺失**：DirectorChatEntry 主链路内无 Worker 按钮；**缺失**：R1-E created tasks 经过 Worker 的 live evidence |
| **CL-09** | **Evidence Partial** | 后端 RunTable + RunRepository 完整；simulate Worker 可生成 Run；**缺失**：R1-E tasks → Worker → Run live evidence |
| **CL-10** | **Evidence Partial** | Worker 执行后自动生成 run.summary (L1)；run_ai_summaries 测试存在；**缺失**：R1-E tasks 跑完 Worker 后的 summary live evidence |
| **CL-11** | **Evidence Partial** | 后端 failure_category + retry/rework/human 路径完整；approval rework 已测试；**缺失**：R1-E 链路中失败/阻塞 real evidence |
| **CL-15** | **Partial** | 后端 Worker 已记录 owner_role_code + skill_codes；治理中心前端已展示但消费证据数据待后端接入 |
| **CL-16** | **Partial** | 后端 RunTable 已记录 tokens/cost；治理中心前端展示但数据源静态；provider_reported evidence 存在 |
| **CL-17** | **Runtime Pass (工作台)** | 工作台 6 按钮全真实闭环；WorkbenchRightRail Worker 按钮真实调用 /workers/run-once |

---

## 8. 可安全验证的本地/测试链路

### 8.1 可直接运行的窄范围测试（无风险）

```bash
cd runtime/orchestrator
python -m pytest tests/test_project_director_worker_run_evidence.py
python -m pytest tests/test_project_director_run_evidence_replay.py
python -m pytest tests/test_run_ai_summaries.py
python -m pytest tests/test_approval_rework_task_creation.py
```

这些测试使用临时 SQLite DB + simulate executor，不产生外部副作用。

### 8.2 Live HTTP evidence（需要临时后端 + DB）

与 R1-A~E 相同方式：临时 uvicorn + 临时 SQLite + simulate executor → 验证 Worker 从 R1-E created tasks 中 claim task → 生成 Run → readback Run/summary。

**这是安全的**：simulate executor 不调用外部 API，不修改仓库，不产生外部副作用。

### 8.3 如果是 provider_reported（真模型执行）

- CLI tool 已有 `v5_day07_minimal_continuous_regression_pack.py` showing provider execution
- Provider execution 会产生真实 API 调用和 token 消耗
- 属于 **低度风险**（token 消耗但无副作用），但需要用户确认

---

## 9. 高风险动作清单

以下动作属于高风险，需要用户显式确认后才能执行：

| # | 动作 | 风险 |
|---|---|---|
| **H1** | 调用 provider_reported Worker（真模型执行） | token 消耗；可能产生意外输出 |
| **H2** | 调用 planning/apply | 可能修改计划或变更仓库 |
| **H3** | 调用 apply-local / git-commit | 写入仓库 |
| **H4** | 写入主仓库 data/ 目录 | 污染数据 |

以下动作 **不** 属于高风险，可在审计范围内执行：

| 动作 | 风险级别 |
|---|---|
| 运行窄范围 pytest（simulate 模式） | 无 |
| Live HTTP + simulate executor Worker | 无 |
| 读取 API 响应验证 Worker dispatch/Run 链路 | 无 |
| GET readback Run/summary/log | 无 |

---

## 10. 下一步建议

### 10.1 R1-F 分两个子阶段

**R1-Fa（前端最小接入）→ 交给 Codex**

范围：
- DirectorChatEntry 中 confirmed plan + created tasks 后展示"调度 Worker 执行任务"按钮
- 按钮调用 `POST /workers/run-once?project_id={project_id}`
- 展示 Worker 返回的关键字段：claimed, task_id, run_id, run_status, model_name, failure_category, tokens, cost
- 不调用 Worker Pool（复用现有单次 Worker）
- 不调用 planning/apply
- 不调用 apply-local/git-commit
- task ID chips 也展示在 Worker response 中（复用 R1-E UI guard）

最小文件范围：
- `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx` (+~60 lines)
- 复用已有 `useRunWorkerOnce()` from `features/task-actions/hooks.ts`

**R1-Fb（live evidence）→ 交给 DeepSeek**

范围：
- Local HTTP: R1-E created tasks → POST /workers/run-once → verify claimed/run_id/run_status/tokens/cost
- GET /runs/{run_id} → verify run summary + decision trace
- GET /tasks/{task_id}/runs → verify run history
- Error path: no pending tasks → Worker returns claimed=false
- 回填 CL-08/CL-09/CL-10 为 Runtime Pass 或 Evidence Partial
- 更新 ledger/checklist

### 10.2 缺口评估

| 缺口 | 严重程度 | 需要 | 交给 |
|---|---|---|---|
| DirectorChatEntry 缺少 Worker 触发按钮 | **关键** | 前端最小接入 | Codex |
| R1-E tasks → Worker → Run live evidence | **关键** | live HTTP evidence | DeepSeek |
| Run summary live evidence | **重要** | GET /runs/{id} readback | DeepSeek |
| 失败/阻塞路径 evidence | **非阻塞** | 可选，已有 simulate 测试 | DeepSeek (后续) |
| 自动 Worker 调度 | **不在 scope** | 当前只做 manual Worker | N/A |
| Worker Pool | **不在 scope** | 复用单次 Worker | N/A |

---

## 11. Gate 结论

### 11.1 R1-F Readiness

**R1-F Readiness: Partial（前端入口缺失，后端能力完备）**

- 后端 Worker API 完整 ✓
- Run 生成/持久化/日志完整 ✓
- Run summary/log/decision-trace read API 完整 ✓
- 失败/阻塞/返工后端机制完整 ✓
- Cost token 记录完整 ✓
- 前端 WorkbenchRightRail Worker 按钮已存在 ✓
- **缺失：DirectorChatEntry 主链路内无 Worker 按钮 ✗**
- **缺失：R1-E tasks → Worker → Run live evidence ✗**

### 11.2 AI Project Director Total Closure

**仍为 Partial**

R1-F（Worker/Run）尚未完成；CL-12~CL-18 尚未完成；交付物、审批、仓库闭环、治理沉淀仍缺失。

---

## 12. 建议执行顺序

```text
1. [Codex] R1-Fa: DirectorChatEntry 加 "调度 Worker" 按钮
2. [DeepSeek] R1-Fb: live evidence + 台账回填
3. [评估] 如果 simulate evidence 足够 → 进 R1-G (Run log/summary 展示)
4. [评估] 如果需要 provider_reported evidence → 用户确认后再执行
```
