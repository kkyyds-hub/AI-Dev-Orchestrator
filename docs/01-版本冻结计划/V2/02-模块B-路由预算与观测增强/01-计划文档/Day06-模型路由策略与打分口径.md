
# Day06 模型路由策略与打分口径

- 版本：`V2`
- 模块 / 提案：`模块B：路由预算与观测增强`
- 原始日期：`2026-03-29`
- 原始来源：`历史标签/每日计划/2026-03-29-V2B模型路由策略与打分口径/01-今日计划.md`
- 当前回填状态：**已完成**
- 回填口径：原日计划已完成并已回填。

---

## 今日目标

把任务路由为什么这样选，变成可解释、可记录、可展示的统一策略。

---

## 当日交付

1. `历史标签/V2阶段文档/23-V2-路由预算与观测策略.md`
2. 路由打分表
3. 路由原因命名规范
4. `runtime/orchestrator/app/services/task_router_service.py`
5. `runtime/orchestrator/app/domain/run.py`
6. `runtime/orchestrator/app/repositories/run_repository.py`
7. `runtime/orchestrator/app/workers/task_worker.py`
8. `runtime/orchestrator/app/services/run_logging_service.py`
---

## 验收点

1. 路由策略可解释
2. 打分口径可被记录
3. 路由原因不再只有一句自由文本
4. 分项得分可被读取
5. 用户能解释主要路由原因
6. 日志和 UI 使用同一套字段
---

## 回填记录

- 当前结论：**已完成**
- 回填说明：原日计划已完成并已回填。
- 回填证据：
1. `历史标签/V2阶段文档/23-V2-路由预算与观测策略.md` 已补齐 Day 6 路由维度表、权重口径和原因命名规范
2. `runtime/orchestrator/app/services/task_router_service.py` 已按固定维度生成结构化分项得分并统一汇总为稳定路由说明
3. `runtime/orchestrator/app/domain/run.py` 已新增 `RunRoutingScoreItem` 与 `routing_score_breakdown` 字段
4. `runtime/orchestrator/app/repositories/run_repository.py` 与 `runtime/orchestrator/app/repositories/task_repository.py` 已支持 `routing_score_breakdown` 的 JSON 持久化和读取
5. `runtime/orchestrator/app/core/db.py`、`runtime/orchestrator/app/core/db_tables.py` 已完成 `runs.routing_score_breakdown` 增量字段升级
6. `runtime/orchestrator/app/workers/task_worker.py` 已把路由分项写入 `task_routed` 与 `run_finalized` 结构化日志事件
7. `runtime/orchestrator/app/services/run_logging_service.py` 已支持对结构化对象做统一 JSON 归一化，避免日志字段失真
8. `apps/web/src/features/task-detail/TaskDetailPanel.tsx` 已展示路由总分与分项说明，前后端字段口径一致
---

## 关键产物路径

1. `历史标签/V2阶段文档/23-V2-路由预算与观测策略.md`
2. `runtime/orchestrator/app/services/task_router_service.py`
3. `runtime/orchestrator/app/domain/run.py`
4. `runtime/orchestrator/app/repositories/run_repository.py`
5. `runtime/orchestrator/app/workers/task_worker.py`
6. `runtime/orchestrator/app/services/run_logging_service.py`
7. `apps/web/src/features/task-detail/TaskDetailPanel.tsx`
8. `runtime/orchestrator/app/repositories/task_repository.py`
---

## 上下游衔接

- 前一日：Day05 状态机验证与文档收口
- 后一日：Day07 预算降级策略与守卫增强
- 对应测试文档：`docs/01-版本冻结计划/V2/02-模块B-路由预算与观测增强/02-测试验证/Day06-模型路由策略与打分口径-测试.md`

---

## 顺延与备注

### 顺延项
1. 无
### 备注
1. Day 6 已完成“路由可解释、可记录、可回放”的最小闭环，后续 Day 7/Day 8 可直接在该结构上叠加预算降级与指标聚合
