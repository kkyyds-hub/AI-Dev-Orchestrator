
# Day12 日志查看与任务操作 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V1/03-模块C-控制台与操作闭环/01-计划文档/Day12-日志查看与任务操作.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 可以按 `run_id` 获取日志事件
2. 结果中包含 `timestamp / level / event / message / data`
3. 控制台可以手动触发单轮执行
4. 失败任务可以被重新推进到下一次尝试
5. 用户可以在首页完成最小操作闭环
6. 日志不再只是一个文件路径，而是可阅读内容
---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/services/run_logging_service.py`
3.    - `runtime/orchestrator/app/api/routes/runs.py`
4.    - `runtime/orchestrator/app/api/routes/tasks.py`
5.    - `runtime/orchestrator/app/services/task_service.py`
6.    - `runtime/orchestrator/app/workers/task_worker.py`
7. 检查前端视图是否能看到对应面板、交互或状态提示。
8. 检查后端路由、服务或 Worker 链路是否已接通。
---

## 当前回填结果

- 结果：**通过**
- 状态口径：原日计划已完成并已回填。
- 证据：
1. 已在 `runtime/orchestrator/app/services/run_logging_service.py` 增加结构化日志读取能力
2. 已新增 `runtime/orchestrator/app/api/routes/runs.py` 并暴露 `GET /runs/{run_id}/logs`
3. 日志接口已限制单次读取上限，并返回 `timestamp / level / event / message / data`
4. 已复用现有 `POST /workers/run-once` 作为 Day 12 手动执行入口
5. 已在 `runtime/orchestrator/app/services/task_service.py` 冻结失败 / 阻塞任务重试语义
6. 已在 `runtime/orchestrator/app/api/routes/tasks.py` 新增 `POST /tasks/{task_id}/retry`
7. 已在 `apps/web/src/app/App.tsx` 增加“执行 Worker 一次”按钮和执行反馈面板
8. 已在 `apps/web/src/features/task-detail/TaskDetailPanel.tsx` 增加“重试任务”按钮
---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做完整烟测。
2. 若当前状态为“未开始”，先创建关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在实现变化时补回归验证。
