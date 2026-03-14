
# Day13 单机有限并行验证 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V2/03-模块C-复盘与有限并行/01-计划文档/Day13-单机有限并行验证.md`
- 当前回填状态：**已完成**
- 当前测试结论：**已通过**

---

## 核心检查项

1. 固定槽位可工作且数量可配置
2. 单轮模式保留为明确回退路径
3. 控制台能看见槽位状态和等待压力
4. 并行运行后的日志与回放链路仍可被前端消费
5. 并行能力不会破坏状态机、预算规则和回放链路
6. `V2-C` 与 `V2` 完成与否有明确结论
---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/services/worker_slot_service.py`
3.    - `runtime/orchestrator/app/workers/worker_pool.py`
4.    - `runtime/orchestrator/app/core/config.py`
5.    - `runtime/orchestrator/app/api/routes/console.py`
6.    - `apps/web/src/features/run-log/RunLogPanel.tsx`
7. 检查前端视图是否能看到对应面板、交互或状态提示。
8. 检查后端路由、服务或 Worker 链路是否已接通。
---

## 当前回填结果

- 结果：**已通过**
- 状态口径：单机固定槽位、控制台观测、并行日志与回放链路、单轮回退路径均已通过本地验证，`V2-C` 可以收口。
- 证据：
1. 已发现产物：`runtime/orchestrator/app/services/worker_slot_service.py`
2. 已发现产物：`runtime/orchestrator/app/workers/worker_pool.py`
3. 已发现产物：`runtime/orchestrator/app/core/config.py`
4. 已发现产物：`runtime/orchestrator/app/api/routes/console.py`
5. 已发现产物：`runtime/orchestrator/app/api/routes/workers.py`
6. 已发现产物：`apps/web/src/features/console-metrics/WorkerSlotPanel.tsx`
7. 已发现产物：`runtime/orchestrator/scripts/v2c_day13_worker_pool_smoke.py`
8. 本地 smoke 通过：`python runtime/orchestrator/scripts/v2c_day13_worker_pool_smoke.py`
9. smoke 结果满足：
   - `/workers/run-pool-once` 返回 `launched_workers=2`、`claimed_runs=2`
   - `/console/worker-slots` 在池化执行后显示 `pending_tasks=1`、全部槽位回到 `idle`
   - 两个并行 run 的日志均包含 `worker_slot_assigned` 与 `worker_slot_released`
   - 两个并行 run 的 `decision-trace` 均包含 `parallel` 阶段
   - `/workers/run-once` 成功领取剩余 1 个任务，证明单轮模式仍可作为回退路径
10. 前端构建通过：`cmd /c npm run build`
---

## 后续补测建议

1. 若后续提高槽位上限或引入更重的执行任务，应增加高并发和长耗时场景烟测。
2. 若预算口径改为更严格的预留式控制，需要追加并行预算竞争专项验证。
3. 当前状态为“已完成”，后续仅在并行链路变化时补回归验证。
