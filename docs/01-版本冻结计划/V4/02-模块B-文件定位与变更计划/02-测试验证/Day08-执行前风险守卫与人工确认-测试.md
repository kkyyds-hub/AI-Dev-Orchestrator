# Day08 执行前风险守卫与人工确认 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V4/02-模块B-文件定位与变更计划/01-计划文档/Day08-执行前风险守卫与人工确认.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 系统能对危险目录、敏感文件、大范围变更和高风险命令给出标准化风险分类
2. 高风险变更批次会被阻断并显式转入人工确认，不允许默认放行
3. 低风险变更批次可以形成“可进入执行”的预检结果
4. 预检结果能回写到审批、项目时间线和变更批次详情
5. Day08 只建立执行前守卫，不提前执行代码修改、验证命令或提交动作

---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/services/change_risk_guard_service.py`
3.    - `runtime/orchestrator/app/api/routes/approvals.py`
4.    - `runtime/orchestrator/app/api/routes/repositories.py`
5.    - `apps/web/src/features/approvals/RepositoryPreflightPanel.tsx`
6.    - `apps/web/src/features/repositories/components/PreflightChecklist.tsx`
7.    - `runtime/orchestrator/scripts/v4b_day08_preflight_guard_smoke.py`
8. 检查后端路由、服务、审批页、仓库页与项目时间线是否已按计划接通。
9. 检查高风险批次是否会被阻断并转入人工确认，低风险批次是否返回“可进入执行”。
10. 若当日涉及回写审批、时间线或批次详情，补一次最小烟测验证关键路径。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：Day08 已完成执行前风险守卫、人工确认闸门、审批页 / 仓库页展示、批次详情回写与项目时间线回写；实现边界严格停留在执行前守卫层，没有提前进入 Day09+ 的验证模板、验证运行、证据包、回退链路或产品内真实 Git 写操作。
- 证据：
1. 已执行 `runtime/orchestrator/.venv/Scripts/python.exe -m py_compile runtime/orchestrator/app/domain/change_batch.py runtime/orchestrator/app/core/db.py runtime/orchestrator/app/core/db_tables.py runtime/orchestrator/app/repositories/change_batch_repository.py runtime/orchestrator/app/services/change_batch_service.py runtime/orchestrator/app/services/change_risk_guard_service.py runtime/orchestrator/app/api/routes/repositories.py runtime/orchestrator/app/api/routes/approvals.py runtime/orchestrator/app/api/routes/projects.py runtime/orchestrator/scripts/v4b_day08_preflight_guard_smoke.py`，确认 Day08 后端与烟测脚本编译通过。
2. 已执行 `runtime/orchestrator/.venv/Scripts/python.exe runtime/orchestrator/scripts/v4b_day08_preflight_guard_smoke.py`，验证“高风险批次阻断并转人工确认 → 人工放行回写 → 低风险批次返回可进入执行 → 审批页 / 时间线回写”链路通过。
3. 已执行 `runtime/orchestrator/.venv/Scripts/python.exe runtime/orchestrator/scripts/v4b_day07_change_batch_smoke.py`，确认 Day08 接入后 Day07 ChangeBatch 执行准备链路未回归。
4. 已执行 `runtime/orchestrator/.venv/Scripts/python.exe runtime/orchestrator/scripts/v4b_day06_change_plan_smoke.py`，确认 Day08 接入后 Day06 ChangePlan 草案能力未回归。
5. 已执行 `cmd /c npm run build`，确认前端 Day08 仓库页预检检查单、审批页人工确认面板及项目时间线类型变更通过 TypeScript 与 Vite 构建。
6. 仓库页的 `PreflightChecklist` 与审批页的 `RepositoryPreflightPanel` 已能展示标准化风险分类、低风险“可进入执行”结果、高风险阻断与人工确认动作，满足 Day08 验收要求。

---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做最小烟测。
2. 若当前状态为“未开始”，先按计划文档完成关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在 Day08 实现变化时补回归验证。
