
# Day05 任务列表与详情接口

- 版本：`V1`
- 模块 / 提案：`模块A：基础骨架与任务建模`
- 原始日期：`2026-03-13`
- 原始来源：`历史标签/每日计划/2026-03-13-V1任务列表与详情接口/01-今日计划.md`
- 当前回填状态：**已完成**
- 回填口径：原日计划已完成并已回填。

---

## 今日目标

完成 `Task` 最小列表与详情接口接入，让后端具备查看任务状态的基础能力

---

## 当日交付

1. 任务列表接口契约
2. 任务详情接口契约
3. Day 5 文件落位约定
4. `runtime/orchestrator/app/repositories/task_repository.py`
5. `runtime/orchestrator/app/services/task_service.py`
6. 任务查询最小调用链
7. `runtime/orchestrator/app/api/routes/tasks.py`
8. 任务列表接口
---

## 验收点

1. 列表接口和详情接口的字段口径与 Day 4 创建响应保持一致
2. 代码落位不引入新的职责混乱
3. 查询逻辑不直接散落在路由层
4. 任务列表和单条详情都能返回领域对象
5. Day 6 之后如果继续扩展状态流转，查询能力不需要返工
6. `GET /tasks` 可以返回已创建任务集合
7. `GET /tasks/{task_id}` 可以返回指定任务详情
8. 未命中的 `task_id` 能返回明确错误结果
---

## 回填记录

- 当前结论：**已完成**
- 回填说明：原日计划已完成并已回填。
- 回填证据：
1. 已在 `runtime/orchestrator/app/api/routes/tasks.py` 增加 `GET /tasks` 与 `GET /tasks/{task_id}` 的响应契约
2. 已继续沿用 `runtime/orchestrator/app/repositories/task_repository.py` 与 `runtime/orchestrator/app/services/task_service.py` 的既有落位
3. 已在 `runtime/orchestrator/app/repositories/task_repository.py` 补充 `list_all()` 与 `get_by_id()`
4. 已在 `runtime/orchestrator/app/services/task_service.py` 补充 `list_tasks()` 与 `get_task()`
5. 已形成从路由 -> 服务 -> 仓储 -> 数据库的任务查询最小调用链
6. 已在 `runtime/orchestrator/app/api/routes/tasks.py` 接入任务列表与详情接口
7. 已更新 `runtime/orchestrator/README.md` 的任务列表与任务详情调用说明
8. 已通过临时数据库验证 `POST /tasks`、`GET /tasks`、`GET /tasks/{task_id}` 和缺失任务 `404` 返回
---

## 关键产物路径

1. `runtime/orchestrator/app/repositories/task_repository.py`
2. `runtime/orchestrator/app/services/task_service.py`
3. `runtime/orchestrator/app/api/routes/tasks.py`
4. `runtime/orchestrator/README.md`
---

## 上下游衔接

- 前一日：Day04 任务创建接口
- 后一日：Day06 Worker最小循环
- 对应测试文档：`docs/01-版本冻结计划/V1/01-模块A-基础骨架与任务建模/02-测试验证/Day05-任务列表与详情接口-测试.md`

---

## 顺延与备注

### 顺延项
1. 分页、筛选和排序增强顺延到后续工作日
2. `Run` 列表与详情接口顺延到后续工作日
### 备注
1. Day 5 的价值不是做复杂查询，而是让任务从“可创建”推进到“可查看”
2. 只要今天完成“查询契约 + 仓储/服务查询 + 接口验证”，`V1` 就继续保持最小闭环推进节奏
