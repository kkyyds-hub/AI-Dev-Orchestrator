
# Day15 预算守卫与失败重试 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V1/04-模块D-质量闸门与预算守卫/01-计划文档/Day15-预算守卫与失败重试.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 预算配置边界清晰
2. 超限后的行为可预测
3. 超预算任务不会继续执行
4. 超重试任务不会无限循环
5. 控制台可以看见被阻止原因
6. 首页可以看见预算剩余与风险提示
7. 被预算阻止的任务不会变成“神秘失败”
---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/core/config.py`
3.    - `runtime/orchestrator/app/services/budget_guard_service.py`
4.    - `runtime/orchestrator/app/domain/*`
5.    - `runtime/orchestrator/app/workers/task_worker.py`
6.    - `runtime/orchestrator/app/repositories/task_repository.py`
7. 检查前端视图是否能看到对应面板、交互或状态提示。
8. 检查后端路由、服务或 Worker 链路是否已接通。
---

## 当前回填结果

- 结果：**通过**
- 状态口径：原日计划已完成并已回填。
- 证据：
1. `runtime/orchestrator/app/core/config.py` 已支持 `DAILY_BUDGET_USD`、`SESSION_BUDGET_USD`、`MAX_TASK_RETRIES` 配置读取
2. `runtime/orchestrator/app/services/budget_guard_service.py` 已定义预算快照、重试状态和阻塞决策，并冻结日预算 / 会话预算 / 单任务重试上限三类守卫
3. `runtime/orchestrator/app/workers/task_worker.py` 已在执行前接入预算与重试判断，超限时把任务置为 `blocked`、把运行置为 `cancelled` 并写入结构化日志
4. `runtime/orchestrator/app/services/task_service.py` 已在手动重试入口阻止超出重试上限的任务继续进入下一次尝试
5. `apps/web/src/features/budget/BudgetOverviewPanel.tsx` 已展示日预算 / 会话预算使用、剩余额度和重试上限
6. `apps/web/src/features/task-detail/TaskDetailPanel.tsx` 已展示执行次数、已用重试、剩余重试和预算健康状态，并在超上限时禁用重试按钮
---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做完整烟测。
2. 若当前状态为“未开始”，先创建关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在实现变化时补回归验证。
