# Day06 仓库任务映射与变更计划草案 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V4/02-模块B-文件定位与变更计划/01-计划文档/Day06-仓库任务映射与变更计划草案.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 任务可以创建、查看和更新一份变更计划草案
2. 变更计划至少包含目标文件、预期动作、风险说明、验证命令引用和关联交付件
3. 同一个交付件可以记录多版变更计划草案，保留版本时间线
4. 项目详情能反查任务与变更计划的映射关系
5. Day06 只冻结计划草案，不提前进入批次调度和风险预检

---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/domain/change_plan.py`
3.    - `runtime/orchestrator/app/repositories/change_plan_repository.py`
4.    - `runtime/orchestrator/app/services/change_plan_service.py`
5.    - `runtime/orchestrator/app/api/routes/planning.py`
6.    - `apps/web/src/features/projects/ChangePlanDrawer.tsx`
7.    - `runtime/orchestrator/scripts/v4b_day06_change_plan_smoke.py`
8. 检查后端路由、服务或项目流程是否已按计划接通。
9. 检查前端页面、卡片、抽屉或时间线是否能展示对应信息。
10. 若当日涉及扫描、差异、审批、验证命令或回退链路，补一次最小烟测验证关键路径。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：Day06 已完成 ChangePlan 草案建模、版本化持久化、项目详情反查映射与 Day05 `CodeContextPack` 接入；实现边界严格停留在草案层，没有提前进入 Day07 变更批次、Day08 风险预检、审批放行、验证证据包，也没有在产品内新增真实 Git 写操作。
- 证据：
1. 已执行 `python -X utf8 - <<py_compile>>` 对 `change_plan.py`、`change_plan_repository.py`、`change_plan_service.py`、`planning.py`、`db_tables.py` 与 `v4b_day06_change_plan_smoke.py` 做编译检查并通过。
2. 已执行 `runtime/orchestrator/.venv/Scripts/python.exe runtime/orchestrator/scripts/v4b_day06_change_plan_smoke.py`，验证“Day05 文件定位 / 上下文包 → Day06 变更计划草案创建 → 追加版本 → 列表/详情反查”链路通过。
3. 已执行 `runtime/orchestrator/.venv/Scripts/python.exe runtime/orchestrator/scripts/v4b_day05_code_locator_smoke.py`，确认 Day06 接入后 Day05 文件定位与 `CodeContextPack` 能力未回归。
4. 已执行 `cmd /c npm run build`，确认前端类型、抽屉与项目仓库页集成通过 TypeScript 与 Vite 构建。
5. `apps/web/src/features/repositories/RepositoryOverviewPage.tsx` 已在项目详情页展示任务到 ChangePlan 的映射入口，满足 Day06 反查要求。

---

## 后续补测建议

1. 后续如调整 ChangePlan 字段结构、前端抽屉交互或项目页映射卡片，优先回归 Day06 烟测脚本与前端构建。
2. 进入 Day07 前，仅补与批次拆分直接相关的回归，不在 Day06 文档中提前记录 Day07/Day08 结果。
3. 若后续新增更复杂的交付件关联规则，可追加 API 断言，但仍保持 Day06 不触发真实代码执行与产品内 Git 写操作。
