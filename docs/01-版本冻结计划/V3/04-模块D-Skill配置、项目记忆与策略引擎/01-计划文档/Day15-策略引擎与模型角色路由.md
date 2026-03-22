# Day15 策略引擎与模型角色路由

- 版本：`V3`
- 模块 / 提案：`模块D：Skill配置、项目记忆与策略引擎`
- 原始日期：`2026-04-20`
- 原始来源：`V3 正式版总纲 / 模块D：Skill配置、项目记忆与策略引擎 / Day15`
- 当前回填状态：**已完成**
- 回填口径：已完成 Day15 范围内的策略引擎、模型角色路由、Skill 绑定路由与可解释策略预览；未扩展到 Day16 端到端收口，也未引入更重长期记忆体系。

---

## 今日目标

让模型选择、角色选择、Skill 选择和预算策略形成统一的策略引擎，而不是散落在多个服务里的局部判断。

---

## 当日交付

1. `runtime/orchestrator/app/services/strategy_engine_service.py`
2. `runtime/orchestrator/app/services/task_router_service.py`
3. `runtime/orchestrator/app/services/budget_guard_service.py`
4. `runtime/orchestrator/app/domain/run.py`
5. `runtime/orchestrator/app/repositories/run_repository.py`
6. `runtime/orchestrator/app/api/routes/strategy.py`
7. `runtime/orchestrator/app/api/routes/workers.py`
8. `runtime/orchestrator/app/workers/task_worker.py`
9. `runtime/orchestrator/scripts/v3d_day15_strategy_engine_smoke.py`
10. `apps/web/src/features/strategy/StrategyDecisionPanel.tsx`
11. `apps/web/src/features/strategy/StrategyRuleEditor.tsx`
12. `apps/web/src/features/projects/ProjectOverviewPage.tsx`
13. `apps/web/src/app/App.tsx`

---

## 验收点

1. 策略引擎能结合项目阶段、角色、预算压力和 Skill 绑定做路由
2. 每次策略决策都能输出可解释理由
3. 角色化策略与现有 `TaskRouterService`、预算守卫兼容
4. 用户能在 UI 里看到本次为什么选这个角色/模型/Skill
5. 策略规则支持最小配置化而不是硬编码散落

---

## 回填记录

- 当前结论：**已完成**
- 回填说明：
  1. 新增 `StrategyEngineService`，把项目阶段、角色职责、Day13 Skill 绑定、预算压力和模型层级选择统一收敛到一份可配置规则集里，支持默认规则与运行时 JSON 覆盖。
  2. 重写 `TaskRouterService` 的候选评估链路，统一输出任务候选、角色接力、模型层级、Skill 选择、解释性理由和打分明细，不再把这些判断散落在多个局部服务中。
  3. 扩展 `BudgetGuardService`、`Run` / `RunRepository` 与 `TaskWorker`，把预算压力映射为可消费的 `preferred_model_tier` 与路由指令，并把 `strategy_decision`、角色接力信息、模型名、Skill 选择持久化到运行记录和日志事件里。
  4. 新增 `/strategy/rules` 与 `/strategy/projects/{project_id}/preview`，并在老板项目页接入“策略决策预览”和“策略规则编辑器”，允许直接查看“为什么选这个角色 / 模型 / Skill”以及最小规则调参结果。
  5. 增加 `v3d_day15_strategy_engine_smoke.py`，覆盖默认路由、规则覆盖、预算临界降级、Worker 执行回写与策略快照持久化；严格收口在 Day15，不扩展到 Day16 端到端总验收。
- 回填证据：
1. `D:/AI-Dev-Orchestrator/runtime/orchestrator/.venv/Scripts/python.exe -X utf8 -m compileall app`
2. `D:/AI-Dev-Orchestrator/runtime/orchestrator/.venv/Scripts/python.exe -X utf8 scripts/v3d_day15_strategy_engine_smoke.py`
3. `D:/AI-Dev-Orchestrator/apps/web> npm.cmd run build`

---

## 关键产物路径

1. `runtime/orchestrator/app/services/strategy_engine_service.py`
2. `runtime/orchestrator/app/services/task_router_service.py`
3. `runtime/orchestrator/app/services/budget_guard_service.py`
4. `runtime/orchestrator/app/domain/run.py`
5. `runtime/orchestrator/app/repositories/run_repository.py`
6. `runtime/orchestrator/app/api/routes/strategy.py`
7. `runtime/orchestrator/app/api/routes/workers.py`
8. `runtime/orchestrator/app/workers/task_worker.py`
9. `runtime/orchestrator/scripts/v3d_day15_strategy_engine_smoke.py`
10. `apps/web/src/features/strategy/StrategyDecisionPanel.tsx`
11. `apps/web/src/features/strategy/StrategyRuleEditor.tsx`
12. `apps/web/src/features/projects/ProjectOverviewPage.tsx`
13. `apps/web/src/app/App.tsx`

---

## 上下游衔接

- 前一日：Day14 项目记忆与可检索经验沉淀
- 后一日：Day16 V3端到端验收与文档收口
- 对应测试文档：`docs/01-版本冻结计划/V3/04-模块D-Skill配置、项目记忆与策略引擎/02-测试验证/Day15-策略引擎与模型角色路由-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无。

### 备注
1. Day15 把 V2 的路由透明度升级到项目级、角色级和 Skill 绑定级。
2. 本次不做 Day16 端到端总收口，也不引入向量数据库、复杂 RAG 或更重长期记忆体系。
