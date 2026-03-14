
# Day11 任务详情与运行历史 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V1/03-模块C-控制台与操作闭环/01-计划文档/Day11-任务详情与运行历史.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 单任务可以查到历史运行记录
2. 结果里保留状态、成本、摘要、时间、日志路径
3. 一个接口足以支撑最小详情视图
4. 前端不需要再自行拼接多个后端响应
5. 首页可以打开单任务详情
6. 用户可以在不离开首页的情况下看见运行历史
---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/repositories/run_repository.py`
3.    - `runtime/orchestrator/app/api/routes/runs.py`
4.    - `runtime/orchestrator/app/services/console_service.py`
5.    - `runtime/orchestrator/app/api/routes/tasks.py`
6.    - `apps/web/src/app/App.tsx`
7. 检查前端视图是否能看到对应面板、交互或状态提示。
8. 检查后端路由、服务或 Worker 链路是否已接通。
---

## 当前回填结果

- 结果：**通过**
- 状态口径：原日计划已完成并已回填。
- 证据：
1. 已在 `runtime/orchestrator/app/repositories/run_repository.py` 增加 `list_by_task_id()`
2. 已在 `runtime/orchestrator/app/api/routes/tasks.py` 新增 `GET /tasks/{task_id}/runs`
3. 历史运行结果已统一按“最新在前”返回，并保留状态、成本、摘要、时间和日志路径
4. 已在 `runtime/orchestrator/app/services/console_service.py` 增加 Day 11 详情聚合能力
5. 已在 `runtime/orchestrator/app/api/routes/tasks.py` 新增 `GET /tasks/{task_id}/detail`
6. 详情接口已一次返回任务基本信息、最新运行摘要和历史运行列表
7. 已在 `apps/web/src/app/App.tsx` 为任务行接入点击交互和选中态
8. 已新增 `apps/web/src/features/task-detail/TaskDetailPanel.tsx` 详情侧板
---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做完整烟测。
2. 若当前状态为“未开始”，先创建关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在实现变化时补回归验证。
