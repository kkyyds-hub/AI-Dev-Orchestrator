
# Day12 有限多执行单元方案设计

- 版本：`V2`
- 模块 / 提案：`模块C：复盘与有限并行`
- 原始日期：`2026-04-04`
- 原始来源：`历史标签/每日计划/2026-04-04-V2C有限多执行单元方案设计/01-今日计划.md`
- 当前回填状态：**已完成**
- 回填口径：已补齐有限并行方案设计文档，槽位模型、配置字段、安全边界、并发风险和回退路径均已冻结，并与现有实现保持一致。

---

## 今日目标

在不破坏状态一致性和预算控制的前提下，设计单机有限多执行单元方案。

---

## 当日交付

1. `历史标签/V2阶段文档/24-V2-复盘与有限并行方案.md`
2. 槽位模型图
3. 配置字段说明
4. 安全边界表
5. 并发风险说明
6. 计划新增 `runtime/orchestrator/app/services/worker_slot_service.py`
7. 计划新增 `runtime/orchestrator/app/workers/worker_pool.py`
8. 计划新增配置 `MAX_CONCURRENT_WORKERS`
---

## 验收点

1. 并行槽位模型简单清晰
2. 用户能理解系统为何只并行固定数量任务
3. 多执行单元不会打破状态一致性
4. 预算守卫不会被并行绕过
5. 实现骨架命名清晰
6. 后续不会因为命名模糊而返工
---

## 回填记录

- 当前结论：**已完成**
- 回填说明：有限并行方案已完成设计冻结，关键配置、槽位模型、安全边界与并发风险说明已落入设计文档，并能对应到当前代码实现。
- 回填证据：
1. ✅ 已发现产物：`docs/01-版本冻结计划/V2/03-模块C-复盘与有限并行/03-设计文档/复盘与有限并行方案.md` - 已补齐 Day12 / Day13 的有限并行补充设计
2. ✅ 已发现产物：`runtime/orchestrator/app/services/worker_slot_service.py`
3. ✅ 已发现产物：`runtime/orchestrator/app/workers/worker_pool.py`
4. ✅ 已发现产物：`runtime/orchestrator/app/core/config.py` - 包含配置 `MAX_CONCURRENT_WORKERS`
5. ✅ 已发现产物：`runtime/orchestrator/app/api/routes/workers.py` - 暴露 `/workers/run-pool-once` 单机固定槽位入口
6. ✅ 已发现产物：`runtime/orchestrator/app/workers/task_worker.py` - claim 竞争时支持自动重路由重试，不因并发竞争直接丢吞吐
---

## 关键产物路径

1. `docs/01-版本冻结计划/V2/03-模块C-复盘与有限并行/03-设计文档/复盘与有限并行方案.md`
2. `runtime/orchestrator/app/services/worker_slot_service.py`
3. `runtime/orchestrator/app/workers/worker_pool.py`
4. `runtime/orchestrator/app/core/config.py`
5. `runtime/orchestrator/app/api/routes/workers.py`
---

## 上下游衔接

- 前一日：Day11 历史决策回放与问题聚类
- 后一日：Day13 单机有限并行验证
- 对应测试文档：`docs/01-版本冻结计划/V2/03-模块C-复盘与有限并行/02-测试验证/Day12-有限多执行单元方案设计-测试.md`

---

## 顺延与备注

### 顺延项
1. 无
### 备注
1. 今天的价值是先把并行方案定稳，再做最小实现
