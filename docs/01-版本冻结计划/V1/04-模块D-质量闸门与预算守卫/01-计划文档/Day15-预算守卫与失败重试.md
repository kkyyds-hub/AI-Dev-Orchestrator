
# Day15 预算守卫与失败重试

- 版本：`V1`
- 模块 / 提案：`模块D：质量闸门与预算守卫`
- 原始日期：`2026-03-23`
- 原始来源：`历史标签/每日计划/2026-03-23-V1预算守卫与失败重试/01-今日计划.md`
- 当前回填状态：**已完成**
- 回填口径：原日计划已完成并已回填。

---

## 今日目标

让自动执行在成本和失败重试上更安全、更可控，避免系统“能自动跑但不好放心用”。

---

## 当日交付

1. `runtime/orchestrator/app/core/config.py`
2. `runtime/orchestrator/app/services/budget_guard_service.py`（新文件）
3. `runtime/orchestrator/app/domain/*`（如需补字段）
4. `runtime/orchestrator/app/workers/task_worker.py`
5. `runtime/orchestrator/app/repositories/task_repository.py`
6. `runtime/orchestrator/app/repositories/run_repository.py`
7. `apps/web/src/app/App.tsx`
8. `apps/web/src/features/budget/*`
---

## 验收点

1. 预算配置边界清晰
2. 超限后的行为可预测
3. 超预算任务不会继续执行
4. 超重试任务不会无限循环
5. 控制台可以看见被阻止原因
6. 首页可以看见预算剩余与风险提示
7. 被预算阻止的任务不会变成“神秘失败”
---

## 回填记录

- 当前结论：**已完成**
- 回填说明：原日计划已完成并已回填。
- 回填证据：
1. `runtime/orchestrator/app/core/config.py` 已支持 `DAILY_BUDGET_USD`、`SESSION_BUDGET_USD`、`MAX_TASK_RETRIES` 配置读取
2. `runtime/orchestrator/app/services/budget_guard_service.py` 已定义预算快照、重试状态和阻塞决策，并冻结日预算 / 会话预算 / 单任务重试上限三类守卫
3. `runtime/orchestrator/app/workers/task_worker.py` 已在执行前接入预算与重试判断，超限时把任务置为 `blocked`、把运行置为 `cancelled` 并写入结构化日志
4. `runtime/orchestrator/app/services/task_service.py` 已在手动重试入口阻止超出重试上限的任务继续进入下一次尝试
5. `apps/web/src/features/budget/BudgetOverviewPanel.tsx` 已展示日预算 / 会话预算使用、剩余额度和重试上限
6. `apps/web/src/features/task-detail/TaskDetailPanel.tsx` 已展示执行次数、已用重试、剩余重试和预算健康状态，并在超上限时禁用重试按钮
---

## 关键产物路径

1. `runtime/orchestrator/app/core/config.py`
2. `runtime/orchestrator/app/services/budget_guard_service.py`
3. `runtime/orchestrator/app/domain/*`
4. `runtime/orchestrator/app/workers/task_worker.py`
5. `runtime/orchestrator/app/repositories/task_repository.py`
6. `runtime/orchestrator/app/repositories/run_repository.py`
7. `apps/web/src/app/App.tsx`
8. `apps/web/src/features/budget/*`
---

## 上下游衔接

- 前一日：Day14 验证模板与质量闸门
- 后一日：无（版本收口）
- 对应测试文档：`docs/01-版本冻结计划/V1/04-模块D-质量闸门与预算守卫/02-测试验证/Day15-预算守卫与失败重试-测试.md`

---

## 顺延与备注

### 顺延项
1. 真实模型厂商账单对齐顺延到更后面阶段
2. 更复杂的降级路由和模型切换顺延到后续成本治理阶段
### 备注
1. 今天的目标不是把成本算得多精，而是让系统第一次具备“知道什么时候该停”的能力
2. 已完成 Day 15 烟测：日预算超限会阻止下一条任务、会话预算超限会阻止下一条任务、单任务超重试上限会阻止再次重试并由 Worker 把任务置为 `blocked`
