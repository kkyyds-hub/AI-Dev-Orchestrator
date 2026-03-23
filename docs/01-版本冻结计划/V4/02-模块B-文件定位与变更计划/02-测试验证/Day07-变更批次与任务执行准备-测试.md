# Day07 变更批次与任务执行准备 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V4/02-模块B-文件定位与变更计划/01-计划文档/Day07-变更批次与任务执行准备.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 项目可以基于多个变更计划创建一个变更批次并查看其状态
2. 同一批次内的任务顺序、依赖关系和文件重叠风险有明确展示
3. 系统能限制同一项目同一时刻只有一个活跃变更批次，避免范围混乱
4. 批次摘要可以回写到项目视图与时间线
5. Day07 只建立执行准备模型，不提前触发审批守卫或真实仓库动作

---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/domain/change_batch.py`
3.    - `runtime/orchestrator/app/repositories/change_batch_repository.py`
4.    - `runtime/orchestrator/app/services/change_batch_service.py`
5.    - `runtime/orchestrator/app/api/routes/repositories.py`
6.    - `apps/web/src/features/repositories/ChangeBatchBoard.tsx`
7.    - `runtime/orchestrator/scripts/v4b_day07_change_batch_smoke.py`

8. 检查后端路由、服务或项目流程是否已按计划接通。
9. 检查前端页面、卡片、抽屉或时间线是否能展示对应信息。
10. 若当日涉及扫描、差异、审批、验证命令或回退链路，补一次最小烟测验证关键路径。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：Day07 已完成 ChangeBatch 建模、聚合持久化、任务顺序/依赖/文件重叠展示、仓库页看板接入与最小烟测；实现边界严格停留在执行准备层，没有提前进入 Day08 风险预检、审批放行、验证证据包，也没有在产品内新增真实 Git 写操作。
- 证据：
1. 已执行 `runtime/orchestrator/.venv/Scripts/python.exe -m py_compile runtime/orchestrator/app/domain/change_batch.py runtime/orchestrator/app/repositories/change_batch_repository.py runtime/orchestrator/app/services/change_batch_service.py runtime/orchestrator/app/api/routes/repositories.py runtime/orchestrator/app/core/db_tables.py runtime/orchestrator/scripts/v4b_day07_change_batch_smoke.py`，确认 Day07 后端与烟测脚本编译通过。
2. 已执行 `runtime/orchestrator/.venv/Scripts/python.exe runtime/orchestrator/scripts/v4b_day07_change_batch_smoke.py`，验证“多 ChangePlan 创建 Day07 ChangeBatch → 顺序/依赖/重叠详情 → 活跃批次冲突阻断”链路通过。
3. 已执行 `runtime/orchestrator/.venv/Scripts/python.exe runtime/orchestrator/scripts/v4b_day06_change_plan_smoke.py`，确认 Day07 接入后 Day06 ChangePlan 草案能力未回归。
4. 已执行 `cmd /c npm run build`，确认前端类型、Day07 看板与仓库页集成通过 TypeScript 与 Vite 构建。
5. `apps/web/src/features/repositories/ChangeBatchBoard.tsx` 已在仓库页展示批次摘要、任务顺序、依赖关系、目标文件、文件重叠提醒与本地时间线，满足 Day07 验收要求。

---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做最小烟测。
2. 若当前状态为“未开始”，先按计划文档完成关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在实现变化时补回归验证。
