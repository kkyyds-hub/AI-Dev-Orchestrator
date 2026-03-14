
# Day08 Verifier基础能力

- 版本：`V1`
- 模块 / 提案：`模块B：执行链路与运行验证`
- 原始日期：`2026-03-16`
- 原始来源：`历史标签/每日计划/2026-03-16-V1Verifier基础能力/01-今日计划.md`
- 当前回填状态：**已完成**
- 回填口径：原日计划已完成并已回填。

---

## 今日目标

完成 `Verifier` 最小接入，让任务在执行后具备最小验证动作，并把验证结果回写到 `Task / Run`

---

## 当日交付

1. Day 8 验证模式约定
2. `runtime/orchestrator/app/services/verifier_service.py`
3. `Executor -> Verifier -> 状态回写` 调用边界
4. `runtime/orchestrator/app/services/task_instruction_parser.py`
5. `runtime/orchestrator/app/workers/task_worker.py`
6. `runtime/orchestrator/app/api/routes/workers.py`
7. Day 8 验证闭环结果
8. `runtime/orchestrator/README.md`
---

## 验收点

1. 验证模式边界清晰，不和 `Worker`、`Executor`、仓储层混淆
2. Day 9 可以在此基础上继续接日志与成本记录，不需要返工 Day 8 主结构
3. 验证成功时，任务保持 `completed`，运行记录保持 `succeeded`
4. 验证失败时，任务回写为 `failed`，运行记录回写为 `failed`
5. `result_summary` 中能看到执行与验证的最小结果摘要
6. `Worker` 单轮触发后可以得到执行 + 验证的最终结果
7. 成功与失败路径都能正确回写 `Task / Run` 状态
8. Day 9 可以在此基础上继续记录日志和成本
---

## 回填记录

- 当前结论：**已完成**
- 回填说明：原日计划已完成并已回填。
- 回填证据：
1. 已新增 `runtime/orchestrator/app/services/verifier_service.py`
2. 已新增 `runtime/orchestrator/app/services/task_instruction_parser.py`
3. 已明确 `verify:` / `check:` 作为 Day 8 的最小验证指令
4. 已在 `runtime/orchestrator/app/services/verifier_service.py` 实现本地命令验证与模拟验证
5. 已在 `runtime/orchestrator/app/workers/task_worker.py` 补充执行后验证与结果汇总
6. 已复用 Day 7 的本地命令执行基础能力，没有重复引入新的执行基础设施
7. 已在 `runtime/orchestrator/app/api/routes/workers.py` 返回验证模式和验证摘要
8. 已更新 `runtime/orchestrator/README.md` 的 Day 8 运行说明
---

## 关键产物路径

1. `runtime/orchestrator/app/services/verifier_service.py`
2. `runtime/orchestrator/app/services/task_instruction_parser.py`
3. `runtime/orchestrator/app/workers/task_worker.py`
4. `runtime/orchestrator/app/api/routes/workers.py`
5. `runtime/orchestrator/README.md`
---

## 上下游衔接

- 前一日：Day07 Executor基础能力
- 后一日：Day09 日志与成本记录
- 对应测试文档：`docs/01-版本冻结计划/V1/02-模块B-执行链路与运行验证/02-测试验证/Day08-Verifier基础能力-测试.md`

---

## 顺延与备注

### 顺延项
1. 日志与成本记录顺延到 Day 9
2. 覆盖率、工件归档和复杂验证流水线顺延到后续工作日
### 备注
1. Day 8 的价值不是做复杂测试平台，而是让任务第一次具备“执行后验证”的最小能力
2. 只要今天完成“Verifier + 状态回写 + Worker 验证闭环”，`V1` 的最小执行与验证链路就真正成立
