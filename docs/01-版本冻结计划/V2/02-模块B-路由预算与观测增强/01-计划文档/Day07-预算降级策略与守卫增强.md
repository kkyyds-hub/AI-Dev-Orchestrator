# Day07 预算降级策略与守卫增强

- 版本：`V2`
- 模块 / 提案：`模块B：路由预算与观测增强`
- 原始日期：`2026-03-30`
- 原始来源：`历史标签/每日计划/2026-03-30-V2B预算降级策略与守卫增强/01-今日计划.md`
- 当前回填状态：**已完成**
- 回填口径：已结合现有仓库实现回填为完成，预算压力等级、守卫联动和路由影响规则已经落地。

---

## 今日目标

把预算控制从“超限阻断”升级为“可降级、可解释、可回退”的策略体系。

---

## 当日交付

1. `历史标签/V2阶段文档/23-V2-路由预算与观测策略.md`
2. 预算层级表
3. 降级行为说明
4. `runtime/orchestrator/app/services/budget_guard_service.py`
5. `runtime/orchestrator/app/domain/run.py`
6. `runtime/orchestrator/app/repositories/run_repository.py`
7. `runtime/orchestrator/app/services/task_router_service.py`
8. `runtime/orchestrator/app/workers/task_worker.py`

---

## 验收点

1. 临界预算时的行为可预测。
2. 用户能理解系统为什么变保守。
3. 守卫结果不只包含 `allow / deny`。
4. 降级建议可被后续逻辑消费。
5. 路由会感知预算压力。
6. 用户能看到预算为何影响行为。

---

## 回填记录

- 当前结论：**已完成**
- 回填说明：已结合现有仓库实现回填为完成，预算压力等级、守卫联动和路由影响规则已经落地。
- 回填证据：
1. `runtime/orchestrator/app/services/budget_guard_service.py` 已落地预算压力等级与策略决策结构。
2. `runtime/orchestrator/app/services/task_router_service.py` 已接入预算压力对路由评分的影响。
3. `runtime/orchestrator/app/workers/task_worker.py` 已在执行前消费预算守卫结果并写回明确状态。
4. `runtime/orchestrator/app/domain/run.py` 与 `runtime/orchestrator/app/repositories/run_repository.py` 已补齐预算相关记录字段。

---

## 关键产物路径

1. `runtime/orchestrator/app/services/budget_guard_service.py`
2. `runtime/orchestrator/app/domain/run.py`
3. `runtime/orchestrator/app/repositories/run_repository.py`
4. `runtime/orchestrator/app/services/task_router_service.py`
5. `runtime/orchestrator/app/workers/task_worker.py`
6. `apps/web/src/features/budget/BudgetOverviewPanel.tsx`

---

## 上下游衔接

- 前一日：Day06 模型路由策略与打分口径
- 后一日：Day08 成本指标与失败分布接口
- 对应测试文档：`docs/01-版本冻结计划/V2/02-模块B-路由预算与观测增强/02-测试验证/Day07-预算降级策略与守卫增强-测试.md`

---

## 顺延与备注

### 顺延项
1. 控制台预算层级的可视化细节可顺延到 Day09，不影响本日完成判定。

### 备注
1. 这一天的价值是让预算控制从纯拦截升级为可管理策略。
