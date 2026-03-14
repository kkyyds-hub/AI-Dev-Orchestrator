
# Day06 模型路由策略与打分口径 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V2/02-模块B-路由预算与观测增强/01-计划文档/Day06-模型路由策略与打分口径.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 路由策略可解释
2. 打分口径可被记录
3. 路由原因不再只有一句自由文本
4. 分项得分可被读取
5. 用户能解释主要路由原因
6. 日志和 UI 使用同一套字段
---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `历史标签/V2阶段文档/23-V2-路由预算与观测策略.md`
3.    - `runtime/orchestrator/app/services/task_router_service.py`
4.    - `runtime/orchestrator/app/domain/run.py`
5.    - `runtime/orchestrator/app/repositories/run_repository.py`
6.    - `runtime/orchestrator/app/workers/task_worker.py`
7. 检查前端视图是否能看到对应面板、交互或状态提示。
8. 检查后端路由、服务或 Worker 链路是否已接通。
---

## 当前回填结果

- 结果：**通过**
- 状态口径：原日计划已完成并已回填。
- 证据：
1. `历史标签/V2阶段文档/23-V2-路由预算与观测策略.md` 已补齐 Day 6 路由维度表、权重口径和原因命名规范
2. `runtime/orchestrator/app/services/task_router_service.py` 已按固定维度生成结构化分项得分并统一汇总为稳定路由说明
3. `runtime/orchestrator/app/domain/run.py` 已新增 `RunRoutingScoreItem` 与 `routing_score_breakdown` 字段
4. `runtime/orchestrator/app/repositories/run_repository.py` 与 `runtime/orchestrator/app/repositories/task_repository.py` 已支持 `routing_score_breakdown` 的 JSON 持久化和读取
5. `runtime/orchestrator/app/core/db.py`、`runtime/orchestrator/app/core/db_tables.py` 已完成 `runs.routing_score_breakdown` 增量字段升级
6. `runtime/orchestrator/app/workers/task_worker.py` 已把路由分项写入 `task_routed` 与 `run_finalized` 结构化日志事件
7. `runtime/orchestrator/app/services/run_logging_service.py` 已支持对结构化对象做统一 JSON 归一化，避免日志字段失真
8. `apps/web/src/features/task-detail/TaskDetailPanel.tsx` 已展示路由总分与分项说明，前后端字段口径一致
---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做完整烟测。
2. 若当前状态为“未开始”，先创建关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在实现变化时补回归验证。
