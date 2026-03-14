
# Day06 Worker最小循环 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V1/02-模块B-执行链路与运行验证/01-计划文档/Day06-Worker最小循环.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. `Worker`、仓储层和接口层的职责不混淆
2. Day 7 可以在此基础上继续接入 `Executor`，不需要返工 Day 6 主结构
3. 单轮 `Worker` 可以选到一条待执行任务
4. 被选中的任务会从 `pending` 推进到 `running`
5. 数据库中会生成与该任务关联的一条 `Run` 记录
6. `POST /workers/run-once` 能返回本轮是否取到任务
7. 取到任务时响应中可以看到 `task_id` 和 `run_id`
8. 任务详情接口能看到任务状态已推进到 `running`
---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/workers/task_worker.py`
3.    - `runtime/orchestrator/app/api/routes/workers.py`
4.    - `runtime/orchestrator/app/repositories/task_repository.py`
5.    - `runtime/orchestrator/app/repositories/run_repository.py`
6.    - `runtime/orchestrator/README.md`
7. 检查后端路由、服务或 Worker 链路是否已接通。
---

## 当前回填结果

- 结果：**通过**
- 状态口径：原日计划已完成并已回填。
- 证据：
1. 已新增 `runtime/orchestrator/app/workers/task_worker.py`
2. 已新增 `runtime/orchestrator/app/api/routes/workers.py`
3. 已明确通过 `POST /workers/run-once` 触发 Day 6 最小 `Worker` 循环
4. 已在 `runtime/orchestrator/app/repositories/task_repository.py` 增加 `claim_next_pending()`
5. 已新增 `runtime/orchestrator/app/repositories/run_repository.py`
6. 已在 `runtime/orchestrator/app/workers/task_worker.py` 完成“取任务 -> 推进状态 -> 创建 Run”的最小单轮处理
7. 已在 `runtime/orchestrator/app/api/routes/workers.py` 提供 `POST /workers/run-once`
8. 已在 `runtime/orchestrator/README.md` 补充 Worker 触发说明
---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做完整烟测。
2. 若当前状态为“未开始”，先创建关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在实现变化时补回归验证。
