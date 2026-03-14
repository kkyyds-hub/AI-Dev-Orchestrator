
# Day06 Worker最小循环

- 版本：`V1`
- 模块 / 提案：`模块B：执行链路与运行验证`
- 原始日期：`2026-03-14`
- 原始来源：`历史标签/每日计划/2026-03-14-V1Worker最小循环/01-今日计划.md`
- 当前回填状态：**已完成**
- 回填口径：原日计划已完成并已回填。

---

## 今日目标

完成单 `Worker` 的最小单轮循环，让系统可以从待执行任务中取出一条任务并推进到执行中状态

---

## 当日交付

1. Day 6 `Worker` 职责边界说明
2. `runtime/orchestrator/app/workers/task_worker.py`
3. `runtime/orchestrator/app/api/routes/workers.py`
4. `runtime/orchestrator/app/repositories/task_repository.py`
5. `runtime/orchestrator/app/repositories/run_repository.py`
6. `POST /workers/run-once` 接口
7. Day 6 单轮执行验证结果
8. `runtime/orchestrator/README.md`
---

## 验收点

1. `Worker`、仓储层和接口层的职责不混淆
2. Day 7 可以在此基础上继续接入 `Executor`，不需要返工 Day 6 主结构
3. 单轮 `Worker` 可以选到一条待执行任务
4. 被选中的任务会从 `pending` 推进到 `running`
5. 数据库中会生成与该任务关联的一条 `Run` 记录
6. `POST /workers/run-once` 能返回本轮是否取到任务
7. 取到任务时响应中可以看到 `task_id` 和 `run_id`
8. 任务详情接口能看到任务状态已推进到 `running`
---

## 回填记录

- 当前结论：**已完成**
- 回填说明：原日计划已完成并已回填。
- 回填证据：
1. 已新增 `runtime/orchestrator/app/workers/task_worker.py`
2. 已新增 `runtime/orchestrator/app/api/routes/workers.py`
3. 已明确通过 `POST /workers/run-once` 触发 Day 6 最小 `Worker` 循环
4. 已在 `runtime/orchestrator/app/repositories/task_repository.py` 增加 `claim_next_pending()`
5. 已新增 `runtime/orchestrator/app/repositories/run_repository.py`
6. 已在 `runtime/orchestrator/app/workers/task_worker.py` 完成“取任务 -> 推进状态 -> 创建 Run”的最小单轮处理
7. 已在 `runtime/orchestrator/app/api/routes/workers.py` 提供 `POST /workers/run-once`
8. 已在 `runtime/orchestrator/README.md` 补充 Worker 触发说明
---

## 关键产物路径

1. `runtime/orchestrator/app/workers/task_worker.py`
2. `runtime/orchestrator/app/api/routes/workers.py`
3. `runtime/orchestrator/app/repositories/task_repository.py`
4. `runtime/orchestrator/app/repositories/run_repository.py`
5. `runtime/orchestrator/README.md`
---

## 上下游衔接

- 前一日：Day05 任务列表与详情接口
- 后一日：Day07 Executor基础能力
- 对应测试文档：`docs/01-版本冻结计划/V1/02-模块B-执行链路与运行验证/02-测试验证/Day06-Worker最小循环-测试.md`

---

## 顺延与备注

### 顺延项
1. 真实 `Executor` 接入顺延到 Day 7
2. `Run` 查询接口、失败处理和重试策略顺延到后续工作日
### 备注
1. Day 6 的价值不是“执行成功”，而是让任务第一次具备被 `Worker` 取走并推进状态的能力
2. 只要今天完成“单轮 Worker + 状态推进 + Run 创建 + 触发验证”，`V1` 的最小调度链路就真正开始成立
