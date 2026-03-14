# Day07 预算降级策略与守卫增强 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V2/02-模块B-路由预算与观测增强/01-计划文档/Day07-预算降级策略与守卫增强.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 临界预算时的行为可预测。
2. 用户能理解系统为什么变保守。
3. 守卫结果不只包含 `allow / deny`。
4. 降级建议可被后续逻辑消费。
5. 路由会感知预算压力。
6. 用户能看到预算为何影响行为。

---

## 建议验证动作

1. 检查 `runtime/orchestrator/app/services/budget_guard_service.py` 是否输出稳定的预算压力等级与策略说明。
2. 检查 `runtime/orchestrator/app/services/task_router_service.py` 与 `runtime/orchestrator/app/workers/task_worker.py` 是否正确消费预算策略。
3. 检查 `apps/web/src/features/budget/BudgetOverviewPanel.tsx` 是否能展示预算健康和风险提示。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：已结合现有仓库实现回填为完成，预算压力等级、守卫联动和路由影响规则已经落地。
- 证据：
1. `runtime/orchestrator/app/services/budget_guard_service.py` 已落地预算压力等级与策略决策结构。
2. `runtime/orchestrator/app/services/task_router_service.py` 已接入预算压力对路由评分的影响。
3. `runtime/orchestrator/app/workers/task_worker.py` 已消费预算守卫结果并写回状态。
4. `apps/web/src/features/budget/BudgetOverviewPanel.tsx` 已承担预算可视化展示。

---

## 后续补测建议

1. 后续若增加新预算层级，只需补充回归验证即可。
2. 若路由打分口径变化，需要同步补预算联动回归测试。
