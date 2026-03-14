
# Day01 状态机规则与转移表

- 版本：`V2`
- 模块 / 提案：`模块A：状态机与调度强化`
- 原始日期：`2026-03-24`
- 原始来源：`历史标签/每日计划/2026-03-24-V2A状态机规则与转移表/01-今日计划.md`
- 当前回填状态：**已完成**
- 回填口径：原日计划已完成并已回填。

---

## 今日目标

把 `Task / Run / Event` 的状态语义和主要转移路径统一冻结成一张可执行的规则表。

---

## 当日交付

1. `历史标签/V2阶段文档/22-V2-状态机与调度规则.md`
2. `runtime/orchestrator/app/domain/task.py`
3. `runtime/orchestrator/app/domain/run.py`
4. 状态转移矩阵表
5. 非法转移处理约定
6. 计划新增 `runtime/orchestrator/app/services/task_state_machine_service.py`
7. 计划新增 `runtime/orchestrator/app/services/task_readiness_service.py`
8. 计划保留 `POST /tasks/{task_id}/pause`、`POST /tasks/{task_id}/resume` 等显式接口
---

## 验收点

1. 当前状态种类被完整列出
2. 每个状态变化入口都有来源说明
3. 主要路径可被表格表达
4. 失败后的去向有统一规则
5. 文件职责一眼可识别
6. 对外接口语义不含糊
---

## 回填记录

- 当前结论：**已完成**
- 回填说明：原日计划已完成并已回填。
- 回填证据：
1. 已在 `历史标签/V2阶段文档/22-V2-状态机与调度规则.md` 盘点 `Task / Run / Event` 当前真实状态
2. 已核对 `runtime/orchestrator/app/domain/task.py`
3. 已核对 `runtime/orchestrator/app/domain/run.py`
4. 已核对 `runtime/orchestrator/app/services/task_service.py`、`runtime/orchestrator/app/workers/task_worker.py`、`runtime/orchestrator/app/services/event_stream_service.py`
5. 已在 `历史标签/V2阶段文档/22-V2-状态机与调度规则.md` 冻结 `Task` 状态转移矩阵
6. 已在 `历史标签/V2阶段文档/22-V2-状态机与调度规则.md` 冻结 `Run` 状态转移矩阵
7. 已统一“预算守卫阻断 -> task blocked / run cancelled”和“失败 -> task failed / run failed”的主分流口径
8. 已明确 `pending` 任务存在“保持原状态但不可路由”的阻塞规则
---

## 关键产物路径

1. `历史标签/V2阶段文档/22-V2-状态机与调度规则.md`
2. `runtime/orchestrator/app/domain/task.py`
3. `runtime/orchestrator/app/domain/run.py`
4. `runtime/orchestrator/app/services/task_state_machine_service.py`
5. `runtime/orchestrator/app/services/task_readiness_service.py`
6. `runtime/orchestrator/app/services/task_service.py`
7. `runtime/orchestrator/app/workers/task_worker.py`
8. `runtime/orchestrator/app/services/event_stream_service.py`
---

## 上下游衔接

- 前一日：无（版本起点）
- 后一日：Day02 状态守卫与统一入口
- 对应测试文档：`docs/01-版本冻结计划/V2/01-模块A-状态机与调度强化/02-测试验证/Day01-状态机规则与转移表-测试.md`

---

## 顺延与备注

### 顺延项
1. 无
### 备注
1. 本轮按排期中的 `Day 1` 范围提前执行，实际完成日期为 `2026-03-10`
2. 目录日期 `2026-03-24` 保持不变，用于对齐 `V2` 排期目录结构
3. Day 2 可以直接进入状态守卫与统一入口收敛
