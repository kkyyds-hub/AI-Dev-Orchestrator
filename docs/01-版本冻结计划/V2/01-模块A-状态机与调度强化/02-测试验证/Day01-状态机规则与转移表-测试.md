
# Day01 状态机规则与转移表 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V2/01-模块A-状态机与调度强化/01-计划文档/Day01-状态机规则与转移表.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 当前状态种类被完整列出
2. 每个状态变化入口都有来源说明
3. 主要路径可被表格表达
4. 失败后的去向有统一规则
5. 文件职责一眼可识别
6. 对外接口语义不含糊
---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `历史标签/V2阶段文档/22-V2-状态机与调度规则.md`
3.    - `runtime/orchestrator/app/domain/task.py`
4.    - `runtime/orchestrator/app/domain/run.py`
5.    - `runtime/orchestrator/app/services/task_state_machine_service.py`
6.    - `runtime/orchestrator/app/services/task_readiness_service.py`
7. 检查后端路由、服务或 Worker 链路是否已接通。
---

## 当前回填结果

- 结果：**通过**
- 状态口径：原日计划已完成并已回填。
- 证据：
1. 已在 `历史标签/V2阶段文档/22-V2-状态机与调度规则.md` 盘点 `Task / Run / Event` 当前真实状态
2. 已核对 `runtime/orchestrator/app/domain/task.py`
3. 已核对 `runtime/orchestrator/app/domain/run.py`
4. 已核对 `runtime/orchestrator/app/services/task_service.py`、`runtime/orchestrator/app/workers/task_worker.py`、`runtime/orchestrator/app/services/event_stream_service.py`
5. 已在 `历史标签/V2阶段文档/22-V2-状态机与调度规则.md` 冻结 `Task` 状态转移矩阵
6. 已在 `历史标签/V2阶段文档/22-V2-状态机与调度规则.md` 冻结 `Run` 状态转移矩阵
7. 已统一“预算守卫阻断 -> task blocked / run cancelled”和“失败 -> task failed / run failed”的主分流口径
8. 已明确 `pending` 任务存在“保持原状态但不可路由”的阻塞规则
---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做完整烟测。
2. 若当前状态为“未开始”，先创建关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在实现变化时补回归验证。
