
# Day12 日志查看与任务操作

- 版本：`V1`
- 模块 / 提案：`模块C：控制台与操作闭环`
- 原始日期：`2026-03-20`
- 原始来源：`历史标签/每日计划/2026-03-20-V1日志查看与任务操作/01-今日计划.md`
- 当前回填状态：**已完成**
- 回填口径：原日计划已完成并已回填。

---

## 今日目标

让用户不仅能看任务，还能看日志、手动触发执行并对失败任务做最小操作。

---

## 当日交付

1. `runtime/orchestrator/app/services/run_logging_service.py`
2. `runtime/orchestrator/app/api/routes/runs.py` 或等价文件
3. `runtime/orchestrator/app/api/routes/tasks.py`
4. `runtime/orchestrator/app/services/task_service.py`
5. `runtime/orchestrator/app/workers/task_worker.py`（如有必要）
6. `apps/web/src/app/App.tsx`
7. `apps/web/src/features/task-detail/*`
8. `apps/web/src/features/run-log/*`
---

## 验收点

1. 可以按 `run_id` 获取日志事件
2. 结果中包含 `timestamp / level / event / message / data`
3. 控制台可以手动触发单轮执行
4. 失败任务可以被重新推进到下一次尝试
5. 用户可以在首页完成最小操作闭环
6. 日志不再只是一个文件路径，而是可阅读内容
---

## 回填记录

- 当前结论：**已完成**
- 回填说明：原日计划已完成并已回填。
- 回填证据：
1. 已在 `runtime/orchestrator/app/services/run_logging_service.py` 增加结构化日志读取能力
2. 已新增 `runtime/orchestrator/app/api/routes/runs.py` 并暴露 `GET /runs/{run_id}/logs`
3. 日志接口已限制单次读取上限，并返回 `timestamp / level / event / message / data`
4. 已复用现有 `POST /workers/run-once` 作为 Day 12 手动执行入口
5. 已在 `runtime/orchestrator/app/services/task_service.py` 冻结失败 / 阻塞任务重试语义
6. 已在 `runtime/orchestrator/app/api/routes/tasks.py` 新增 `POST /tasks/{task_id}/retry`
7. 已在 `apps/web/src/app/App.tsx` 增加“执行 Worker 一次”按钮和执行反馈面板
8. 已在 `apps/web/src/features/task-detail/TaskDetailPanel.tsx` 增加“重试任务”按钮
---

## 关键产物路径

1. `runtime/orchestrator/app/services/run_logging_service.py`
2. `runtime/orchestrator/app/api/routes/runs.py`
3. `runtime/orchestrator/app/api/routes/tasks.py`
4. `runtime/orchestrator/app/services/task_service.py`
5. `runtime/orchestrator/app/workers/task_worker.py`
6. `apps/web/src/app/App.tsx`
7. `apps/web/src/features/task-detail/*`
8. `apps/web/src/features/run-log/*`
---

## 上下游衔接

- 前一日：Day11 任务详情与运行历史
- 后一日：Day13 SSE状态流与实时刷新
- 对应测试文档：`docs/01-版本冻结计划/V1/03-模块C-控制台与操作闭环/02-测试验证/Day12-日志查看与任务操作-测试.md`

---

## 顺延与备注

### 顺延项
1. 实时日志流顺延到 Day 13
2. 更复杂的人工介入动作顺延到后续阶段
### 备注
1. 今天的重点是“让控制台可以推动事情继续发生”，不是把后台做成完整运维面板
