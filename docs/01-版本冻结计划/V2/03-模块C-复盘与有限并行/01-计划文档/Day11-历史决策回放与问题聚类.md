
# Day11 历史决策回放与问题聚类

- 版本：`V2`
- 模块 / 提案：`模块C：复盘与有限并行`
- 原始日期：`2026-04-03`
- 原始来源：`历史标签/每日计划/2026-04-03-V2C历史决策回放与问题聚类/01-今日计划.md`
- 当前回填状态：**已完成**
- 回填口径：所有交付物已齐全，三个接口已实现并可用，前端已具备完整消费能力。

---

## 今日目标

让历史路由、失败和人工处置过程具备回放能力，并支持最小问题聚类。

---

## 当日交付

1. `runtime/orchestrator/app/services/decision_replay_service.py`
2. `历史标签/V2阶段文档/24-V2-复盘与有限并行方案.md`
3. 回放模型说明
4. `runtime/orchestrator/app/api/routes/runs.py`
5. `GET /runs/{run_id}/decision-trace`
6. `GET /tasks/{task_id}/decision-history`
7. `GET /console/review-clusters`
8. `apps/web/src/features/run-log/RunLogPanel.tsx`
---

## 验收点

1. 回放结构足够表达关键过程
2. 不需要阅读整份原始日志也能理解主线
3. 接口名称能直接说明用途
4. 回放信息可被前端直接消费
5. 同类问题可被汇总
6. 聚类口径和失败分类保持一致
---

## 回填记录

- 当前结论：**已完成**
- 回填说明：所有交付物已齐全，三个接口已实现并可用，前端已具备完整消费能力。
- 回填证据：
1. ✅ 已发现产物：`runtime/orchestrator/app/services/decision_replay_service.py`
2. ✅ 已发现产物：`docs/01-版本冻结计划/V2/03-模块C-复盘与有限并行/03-设计文档/复盘与有限并行方案.md`
3. ✅ 已发现产物：`runtime/orchestrator/app/api/routes/runs.py` - 包含 `GET /runs/{run_id}/decision-trace` 接口
4. ✅ 已发现产物：`runtime/orchestrator/app/api/routes/tasks.py` - 包含 `GET /tasks/{task_id}/decision-history` 接口
5. ✅ 已发现产物：`runtime/orchestrator/app/api/routes/console.py` - 包含 `GET /console/review-clusters` 接口
6. ✅ 已发现产物：`apps/web/src/features/run-log/RunLogPanel.tsx` - 决策回放展示组件
7. ✅ 已发现产物：`apps/web/src/features/console-metrics/decision-api.ts` - 决策历史和聚类API
8. ✅ 已发现产物：`apps/web/src/features/console-metrics/decision-hooks.ts` - 决策历史和聚类hooks
9. ✅ 已发现产物：`apps/web/src/features/console-metrics/DecisionHistoryPanel.tsx` - 决策历史展示组件
10. ✅ 已发现产物：`apps/web/src/features/console-metrics/ReviewClustersPanel.tsx` - 失败聚类展示组件
11. ✅ 已发现产物：`apps/web/src/features/task-detail/TaskDetailPanel.tsx` - 已接入任务级决策历史面板并支持切换运行记录
12. ✅ 已发现产物：`apps/web/src/app/App.tsx` - 已接入全局失败聚类面板
---

## 关键产物路径

1. `runtime/orchestrator/app/services/decision_replay_service.py`
2. `docs/01-版本冻结计划/V2/03-模块C-复盘与有限并行/03-设计文档/复盘与有限并行方案.md`
3. `runtime/orchestrator/app/api/routes/runs.py`
4. `runtime/orchestrator/app/api/routes/tasks.py`
5. `runtime/orchestrator/app/api/routes/console.py`
6. `apps/web/src/features/run-log/RunLogPanel.tsx`
7. `apps/web/src/features/console-metrics/decision-api.ts`
8. `apps/web/src/features/console-metrics/decision-hooks.ts`
9. `apps/web/src/features/console-metrics/DecisionHistoryPanel.tsx`
10. `apps/web/src/features/console-metrics/ReviewClustersPanel.tsx`
---

## 上下游衔接

- 前一日：Day10 失败复盘结构与记录模板
- 后一日：Day12 有限多执行单元方案设计
- 对应测试文档：`docs/01-版本冻结计划/V2/03-模块C-复盘与有限并行/02-测试验证/Day11-历史决策回放与问题聚类-测试.md`

---

## 顺延与备注

### 顺延项
1. 如聚类视图未完全接通，可先保证回放接口稳定
### 备注
1. 今天的重点是让“结果可看”升级为“过程可回放”
