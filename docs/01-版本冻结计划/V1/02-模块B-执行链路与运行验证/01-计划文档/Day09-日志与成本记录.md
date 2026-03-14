
# Day09 日志与成本记录

- 版本：`V1`
- 模块 / 提案：`模块B：执行链路与运行验证`
- 原始日期：`2026-03-17`
- 原始来源：`历史标签/每日计划/2026-03-17-V1日志与成本记录/01-今日计划.md`
- 当前回填状态：**已完成**
- 回填口径：原日计划已完成并已回填。

---

## 今日目标

完成 Day 9 的最小日志落盘与成本记录闭环，让执行结果除了状态之外还能留下过程痕迹和成本数据。

---

## 当日交付

1. `prompt_tokens`
2. `completion_tokens`
3. `estimated_cost`
4. `log_path`
5. `runtime/orchestrator/app/services/run_logging_service.py`
6. `runtime/orchestrator/app/services/cost_estimator_service.py`
7. `runtime/orchestrator/app/workers/task_worker.py`
8. `runtime/orchestrator/app/api/routes/workers.py`
---

## 验收点

1. 新老数据库都能持久化 Day 9 字段
2. `RunRepository` 可以回写并读出这些字段
3. 每次运行都会落一份 `jsonl` 日志
4. Worker 成功和失败路径都会产生最终成本记录
5. 接口调用方可以直接看到 `log_path` 和成本字段
6. README 能说明 Day 9 新增能力
7. 每日计划文档能作为后续 Day 10 交接依据
---

## 回填记录

- 当前结论：**已完成**
- 回填说明：原日计划已完成并已回填。
- 回填证据：
1. 已更新 `runtime/orchestrator/app/domain/run.py`
2. 已更新 `runtime/orchestrator/app/core/db_tables.py`
3. 已更新 `runtime/orchestrator/app/core/db.py`
4. 已在 `TaskWorker` 串上日志初始化、执行记录、验证记录、成本记录和最终回写
5. 已在 `WorkerRunOnceResponse` 暴露 `log_path`、`prompt_tokens`、`completion_tokens`、`estimated_cost`
6. 已通过本地烟测验证日志文件实际落盘
7. 已更新 `runtime/orchestrator/README.md`
8. 已新增本文件记录 Day 9 范围与完成结果
---

## 关键产物路径

1. `runtime/orchestrator/app/services/run_logging_service.py`
2. `runtime/orchestrator/app/services/cost_estimator_service.py`
3. `runtime/orchestrator/app/workers/task_worker.py`
4. `runtime/orchestrator/app/api/routes/workers.py`
5. `runtime/orchestrator/README.md`
6. `历史标签/每日计划/2026-03-17-V1日志与成本记录/01-今日计划.md`
7. `runtime/orchestrator/app/domain/run.py`
8. `runtime/orchestrator/app/core/db_tables.py`
---

## 上下游衔接

- 前一日：Day08 Verifier基础能力
- 后一日：Day10 最小控制台首页
- 对应测试文档：`docs/01-版本冻结计划/V1/02-模块B-执行链路与运行验证/02-测试验证/Day09-日志与成本记录-测试.md`

---

## 顺延与备注

### 顺延项
1. Day 10 继续把成本展示接到最小控制台首页
2. 后续再补日志查询接口或 SSE 日志流
### 备注
1. Day 9 的价值不是做完整观测平台，而是先把“执行过什么、花了多少”沉淀下来
2. 只要 Day 9 完成，Day 10 就可以直接消费 `Run` 上的日志路径和成本字段
