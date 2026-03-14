
# Day11 历史决策回放与问题聚类 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V2/03-模块C-复盘与有限并行/01-计划文档/Day11-历史决策回放与问题聚类.md`
- 当前回填状态：**已完成**
- 当前测试结论：**已通过**

---

## 核心检查项

1. 回放结构足够表达关键过程
2. 不需要阅读整份原始日志也能理解主线
3. 接口名称能直接说明用途
4. 回放信息可被前端直接消费
5. 同类问题可被汇总
6. 聚类口径和失败分类保持一致
---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/services/decision_replay_service.py`
3.    - `历史标签/V2阶段文档/24-V2-复盘与有限并行方案.md`
4.    - `runtime/orchestrator/app/api/routes/runs.py`
5.    - `apps/web/src/features/run-log/RunLogPanel.tsx`
6. 检查前端视图是否能看到对应面板、交互或状态提示。
7. 检查后端路由、服务或 Worker 链路是否已接通。
---

## 当前回填结果

- 结果：**已通过**
- 状态口径：已补齐前端接线与构建问题，三个接口和前端消费链路均已完成本地验证。
- 证据：
1. 已发现产物：`runtime/orchestrator/app/services/decision_replay_service.py`
2. 已发现产物：`docs/01-版本冻结计划/V2/03-模块C-复盘与有限并行/03-设计文档/复盘与有限并行方案.md`
3. 已发现产物：`runtime/orchestrator/app/api/routes/runs.py`
4. 已发现产物：`apps/web/src/features/run-log/RunLogPanel.tsx`
5. 已发现产物：`apps/web/src/features/console-metrics/DecisionHistoryPanel.tsx`
6. 已发现产物：`apps/web/src/features/console-metrics/ReviewClustersPanel.tsx`
7. 已发现产物：`apps/web/src/features/task-detail/TaskDetailPanel.tsx` - 已接入决策历史面板
8. 已发现产物：`apps/web/src/app/App.tsx` - 已接入失败聚类面板
9. 本地前端构建通过：`cmd /c npm run build`
10. 本地 smoke 通过：`python runtime/orchestrator/scripts/v2c_day11_decision_replay_smoke.py`，验证 `/runs/{run_id}/decision-trace`、`/tasks/{task_id}/decision-history`、`/console/review-clusters` 均返回 `200`，且结果满足 `trace_items=5`、`history_items=1`、`review_clusters_count=1`
---

## 后续补测建议

1. 后续若扩展新的运行事件类型，应同步补充 `DecisionReplayService` 的事件映射与前端阶段标签。
2. 若回放或聚类接口增加分页 / limit 参数，需追加对应的边界烟测。
3. 当前状态为“已完成”，后续仅在实现变化时补回归验证。
