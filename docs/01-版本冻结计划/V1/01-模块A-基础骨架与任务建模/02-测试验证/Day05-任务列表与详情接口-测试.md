
# Day05 任务列表与详情接口 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V1/01-模块A-基础骨架与任务建模/01-计划文档/Day05-任务列表与详情接口.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 列表接口和详情接口的字段口径与 Day 4 创建响应保持一致
2. 代码落位不引入新的职责混乱
3. 查询逻辑不直接散落在路由层
4. 任务列表和单条详情都能返回领域对象
5. Day 6 之后如果继续扩展状态流转，查询能力不需要返工
6. `GET /tasks` 可以返回已创建任务集合
7. `GET /tasks/{task_id}` 可以返回指定任务详情
8. 未命中的 `task_id` 能返回明确错误结果
---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/repositories/task_repository.py`
3.    - `runtime/orchestrator/app/services/task_service.py`
4.    - `runtime/orchestrator/app/api/routes/tasks.py`
5.    - `runtime/orchestrator/README.md`
6. 检查后端路由、服务或 Worker 链路是否已接通。
---

## 当前回填结果

- 结果：**通过**
- 状态口径：原日计划已完成并已回填。
- 证据：
1. 已在 `runtime/orchestrator/app/api/routes/tasks.py` 增加 `GET /tasks` 与 `GET /tasks/{task_id}` 的响应契约
2. 已继续沿用 `runtime/orchestrator/app/repositories/task_repository.py` 与 `runtime/orchestrator/app/services/task_service.py` 的既有落位
3. 已在 `runtime/orchestrator/app/repositories/task_repository.py` 补充 `list_all()` 与 `get_by_id()`
4. 已在 `runtime/orchestrator/app/services/task_service.py` 补充 `list_tasks()` 与 `get_task()`
5. 已形成从路由 -> 服务 -> 仓储 -> 数据库的任务查询最小调用链
6. 已在 `runtime/orchestrator/app/api/routes/tasks.py` 接入任务列表与详情接口
7. 已更新 `runtime/orchestrator/README.md` 的任务列表与任务详情调用说明
8. 已通过临时数据库验证 `POST /tasks`、`GET /tasks`、`GET /tasks/{task_id}` 和缺失任务 `404` 返回
---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做完整烟测。
2. 若当前状态为“未开始”，先创建关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在实现变化时补回归验证。
