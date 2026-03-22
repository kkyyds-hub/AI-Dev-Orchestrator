# Day15 策略引擎与模型角色路由 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V3/04-模块D-Skill配置、项目记忆与策略引擎/01-计划文档/Day15-策略引擎与模型角色路由.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 策略引擎能结合项目阶段、角色、预算压力和 Skill 绑定做路由
2. 每次策略决策都能输出可解释理由
3. 角色化策略与现有 `TaskRouterService`、预算守卫兼容
4. 用户能在 UI 里看到本次为什么选这个角色/模型/Skill
5. 策略规则支持最小配置化而不是硬编码散落

---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
   - `runtime/orchestrator/app/services/strategy_engine_service.py`
   - `runtime/orchestrator/app/services/task_router_service.py`
   - `runtime/orchestrator/app/services/budget_guard_service.py`
   - `runtime/orchestrator/app/domain/run.py`
   - `runtime/orchestrator/app/repositories/run_repository.py`
   - `runtime/orchestrator/app/api/routes/strategy.py`
   - `runtime/orchestrator/app/workers/task_worker.py`
   - `runtime/orchestrator/scripts/v3d_day15_strategy_engine_smoke.py`
   - `apps/web/src/features/strategy/StrategyDecisionPanel.tsx`
   - `apps/web/src/features/strategy/StrategyRuleEditor.tsx`
2. 检查后端路由、服务和 Worker 链路是否已接通。
3. 检查前端项目页是否能展示策略预览、策略规则和最新 Worker 的策略结果。
4. 补一次最小烟测，验证规则覆盖、预算降级、Skill 绑定选择和运行持久化。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：Day15 需要的统一策略引擎、模型角色路由、Skill 绑定选择、预算压降级、可解释预览与最小规则编辑均已接通，且未扩展到 Day16 端到端收口或更重长期记忆体系。
- 证据：
  1. `D:/AI-Dev-Orchestrator/runtime/orchestrator/.venv/Scripts/python.exe -X utf8 -m compileall app`
     - 结果：通过。
     - 说明：确认 `strategy_engine_service.py`、`task_router_service.py`、`budget_guard_service.py`、`strategy.py` 与 `task_worker.py` 等 Day15 改动未引入 Python 语法错误。
  2. `D:/AI-Dev-Orchestrator/runtime/orchestrator/.venv/Scripts/python.exe -X utf8 scripts/v3d_day15_strategy_engine_smoke.py`
     - 结果：通过。
     - 覆盖点：
       - `/strategy/projects/{project_id}/preview` 默认会优先选中规划阶段的产品任务，并继承 Day13 的规划类 Skill；
       - `/strategy/rules` 支持运行时覆盖规则，规划阶段产品经理任务可在正常预算下被提升到 `premium / gpt-5`；
       - 注入历史成本样本后，预算压力会进入 `critical`，策略动作降为 `degraded`，模型层级被重新封顶到 `economy / gpt-4.1-mini`；
       - `/workers/run-once` 返回 `model_name`、`model_tier`、`strategy_code`、`selected_skill_names`，且持久化的 `Run.strategy_decision` 会保留本次策略快照。
  3. `D:/AI-Dev-Orchestrator/apps/web> npm.cmd run build`
     - 结果：通过。
     - 说明：确认 `StrategyDecisionPanel`、`StrategyRuleEditor`、`ProjectOverviewPage` 与 `App` 中的 Day15 UI 改造未引入 TypeScript / Vite 构建错误。

---

## 后续补测建议

1. Day16 启动时，可在真实项目数据下补一轮“项目记忆 -> 策略预览 -> Worker 执行 -> 交付 / 审批”跨模块回归，但不要回写到 Day15 验收范围里。
2. 若后续继续扩展策略规则，可补更多边界样本，例如多角色同分、无 Skill 绑定、预算 blocked 等情况。
3. Day15 已收口，本次不建议在同一任务中继续引入长期记忆增强、向量检索或更复杂策略调参后台。
