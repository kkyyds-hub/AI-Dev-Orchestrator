# Day04 人工介入恢复流与重试分流

- 版本：`V2`
- 模块 / 提案：`模块A：状态机与调度强化`
- 原始日期：`2026-03-27`
- 原始来源：`历史标签/每日计划/2026-03-27-V2A人工介入恢复流与重试分流/01-今日计划.md`
- 当前回填状态：**已完成**
- 回填口径：已结合现有仓库实现回填为完成，人工介入、恢复流和重试分流链路已经落地。

---

## 今日目标

把人工介入、恢复、重试和失败分流规则统一成一套可持续扩展的流程。

---

## 当日交付

1. `历史标签/V2阶段文档/22-V2-状态机与调度规则.md`
2. `runtime/orchestrator/app/services/task_service.py`
3. `runtime/orchestrator/app/api/routes/tasks.py`
4. `runtime/orchestrator/app/services/budget_guard_service.py`
5. `runtime/orchestrator/app/workers/task_worker.py`
6. `runtime/orchestrator/app/domain/run.py`
7. `apps/web/src/features/task-detail/TaskDetailPanel.tsx`
8. `apps/web/src/features/task-actions/api.ts`

---

## 验收点

1. 人工介入规则可解释。
2. 人工恢复后不会回到不一致状态。
3. 重试资格不再只靠当前状态判断。
4. 失败分流可被日志和 UI 解释。
5. 用户能理解自己现在可以点什么。
6. 按钮语义和服务端规则不冲突。

---

## 回填记录

- 当前结论：**已完成**
- 回填说明：已结合现有仓库实现回填为完成，人工介入、恢复流和重试分流链路已经落地。
- 回填证据：
1. `runtime/orchestrator/app/services/task_service.py` 已具备 `request-human / resolve-human / retry` 等统一动作链路。
2. `runtime/orchestrator/app/api/routes/tasks.py` 已暴露显式人工介入与恢复接口。
3. `runtime/orchestrator/app/workers/task_worker.py` 与 `runtime/orchestrator/app/domain/run.py` 已统一失败分流与运行状态回写口径。
4. `apps/web/src/features/task-detail/TaskDetailPanel.tsx` 已提供与人工介入/重试相关的界面展示与操作反馈。

---

## 关键产物路径

1. `runtime/orchestrator/app/services/task_service.py`
2. `runtime/orchestrator/app/api/routes/tasks.py`
3. `runtime/orchestrator/app/services/budget_guard_service.py`
4. `runtime/orchestrator/app/workers/task_worker.py`
5. `runtime/orchestrator/app/domain/run.py`
6. `apps/web/src/features/task-detail/TaskDetailPanel.tsx`
7. `apps/web/src/features/task-actions/api.ts`

---

## 上下游衔接

- 前一日：Day03 依赖就绪判断与阻塞原因归一
- 后一日：Day05 状态机验证与文档收口
- 对应测试文档：`docs/01-版本冻结计划/V2/01-模块A-状态机与调度强化/02-测试验证/Day04-人工介入恢复流与重试分流-测试.md`

---

## 顺延与备注

### 顺延项
1. 如提示文案和按钮条件仍需细抠，只作为后续体验优化，不影响本日闭环完成。

### 备注
1. 这一天的核心价值是把“失败后怎么办”从散点操作变成统一流程。
