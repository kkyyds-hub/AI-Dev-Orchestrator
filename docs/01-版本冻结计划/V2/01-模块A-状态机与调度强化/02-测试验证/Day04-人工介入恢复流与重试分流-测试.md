# Day04 人工介入恢复流与重试分流 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V2/01-模块A-状态机与调度强化/01-计划文档/Day04-人工介入恢复流与重试分流.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 人工介入规则可解释。
2. 人工恢复后不会回到不一致状态。
3. 重试资格不再只靠当前状态判断。
4. 失败分流可被日志和 UI 解释。
5. 用户能理解自己现在可以点什么。
6. 按钮语义和服务端规则不冲突。

---

## 建议验证动作

1. 核对 `runtime/orchestrator/app/services/task_service.py`、`runtime/orchestrator/app/api/routes/tasks.py`、`runtime/orchestrator/app/workers/task_worker.py` 是否已联通人工介入与恢复动作。
2. 检查 `apps/web/src/features/task-detail/TaskDetailPanel.tsx` 与 `apps/web/src/features/task-actions/api.ts` 是否能正确展示动作入口和状态反馈。
3. 通过最小接口烟测验证 `request-human / resolve-human / retry` 流程状态回写一致。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：已结合现有仓库实现回填为完成，人工介入、恢复流和重试分流链路已经落地。
- 证据：
1. `runtime/orchestrator/app/services/task_service.py` 已具备统一动作链路。
2. `runtime/orchestrator/app/api/routes/tasks.py` 已暴露显式动作接口。
3. `runtime/orchestrator/app/workers/task_worker.py` 与 `runtime/orchestrator/app/domain/run.py` 已统一失败分流口径。
4. `apps/web/src/features/task-detail/TaskDetailPanel.tsx` 已提供相应 UI 支撑。

---

## 后续补测建议

1. 后续若调整按钮文案或权限边界，只需做回归验证。
2. 若状态机规则再次扩展，优先补动作矩阵测试而不是改口径。
