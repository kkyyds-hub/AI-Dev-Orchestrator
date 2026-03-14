
# Day03 依赖就绪判断与阻塞原因归一

- 版本：`V2`
- 模块 / 提案：`模块A：状态机与调度强化`
- 原始日期：`2026-03-26`
- 原始来源：`历史标签/每日计划/2026-03-26-V2A依赖就绪判断与阻塞原因归一/01-今日计划.md`
- 当前回填状态：**已完成**
- 回填口径：原日计划已完成并已回填。

---

## 今日目标

把任务是否“可执行”的判断逻辑统一，并把阻塞原因标准化成系统可见信息。

---

## 当日交付

1. `runtime/orchestrator/app/services/task_readiness_service.py`
2. `runtime/orchestrator/app/services/task_router_service.py`
3. `runtime/orchestrator/app/repositories/task_repository.py`
4. `runtime/orchestrator/app/domain/task.py`
5. `runtime/orchestrator/app/services/context_builder_service.py`
6. `runtime/orchestrator/app/services/run_logging_service.py`
7. `apps/web/src/features/task-detail/TaskDetailPanel.tsx`
8. `apps/web/src/features/console/types.ts`
---

## 验收点

1. 路由前判断不再复制粘贴
2. 就绪结果可被其他服务复用
3. 阻塞原因可以被归类
4. 控制台不再显示大量相似但不统一的说明
5. 同一阻塞原因在多个视图中用词一致
6. 用户能区分“不能执行”和“还没被执行”
---

## 回填记录

- 当前结论：**已完成**
- 回填说明：原日计划已完成并已回填。
- 回填证据：
1. 已新增 `runtime/orchestrator/app/services/task_readiness_service.py`
2. 已更新 `runtime/orchestrator/app/services/task_router_service.py`
3. 已更新 `runtime/orchestrator/app/services/context_builder_service.py`
4. 已更新 `runtime/orchestrator/app/repositories/task_repository.py`
5. 已在 `runtime/orchestrator/app/domain/task.py` 冻结阻塞原因分类与编码
6. 已在 `runtime/orchestrator/app/api/routes/tasks.py` 暴露 `blocking_signals`
7. 已在 `runtime/orchestrator/app/services/run_logging_service.py` 统一日志数据结构化输出
8. 已在 `runtime/orchestrator/app/workers/task_worker.py` 为 `guard_blocked` 路径补充结构化阻塞原因
---

## 关键产物路径

1. `runtime/orchestrator/app/services/task_readiness_service.py`
2. `runtime/orchestrator/app/services/task_router_service.py`
3. `runtime/orchestrator/app/repositories/task_repository.py`
4. `runtime/orchestrator/app/domain/task.py`
5. `runtime/orchestrator/app/services/context_builder_service.py`
6. `runtime/orchestrator/app/services/run_logging_service.py`
7. `apps/web/src/features/task-detail/TaskDetailPanel.tsx`
8. `apps/web/src/features/console/types.ts`
---

## 上下游衔接

- 前一日：Day02 状态守卫与统一入口
- 后一日：Day04 人工介入恢复流与重试分流
- 对应测试文档：`docs/01-版本冻结计划/V2/01-模块A-状态机与调度强化/02-测试验证/Day03-依赖就绪判断与阻塞原因归一-测试.md`

---

## 顺延与备注

### 顺延项
1. 无
### 备注
1. 本轮按排期中的 `Day 3` 范围提前执行，实际完成日期为 `2026-03-10`
2. 目录日期 `2026-03-26` 保持不变，用于对齐 `V2` 排期目录结构
3. Day 4 可以直接进入人工介入恢复流与重试分流
