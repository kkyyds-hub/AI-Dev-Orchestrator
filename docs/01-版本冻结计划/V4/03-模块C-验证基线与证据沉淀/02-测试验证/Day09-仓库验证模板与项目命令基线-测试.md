# Day09 仓库验证模板与项目命令基线 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V4/03-模块C-验证基线与证据沉淀/01-计划文档/Day09-仓库验证模板与项目命令基线.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 仓库可以配置最小验证命令模板，并区分 `build / test / lint / typecheck` 类别
2. 变更计划或变更批次可以引用其中一个或多个命令模板
3. 命令模板至少记录命令文本、工作目录、超时、是否默认启用等字段
4. 项目或仓库页面可以查看当前验证基线和最后更新时间
5. Day09 只冻结验证模板，不提前记录验证运行结果或差异证据

---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/domain/repository_verification.py`
3.    - `runtime/orchestrator/app/repositories/repository_verification_repository.py`
4.    - `runtime/orchestrator/app/services/repository_verification_service.py`
5.    - `runtime/orchestrator/app/api/routes/repositories.py`
6.    - `apps/web/src/features/repositories/RepositoryVerificationPanel.tsx`
7.    - `runtime/orchestrator/scripts/v4c_day09_repository_verification_smoke.py`
8. 检查 Day09 基线是否可自动初始化 / 覆盖，是否区分 `build / test / lint / typecheck`。
9. 检查 Day06 ChangePlan 与 Day07 ChangeBatch 是否能引用 Day09 模板，并在仓库页展示最后更新时间。
10. 补一次最小烟测，确认 Day09 只冻结模板引用，不提前进入 Day10+ 的运行记录、失败归因或证据包。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：Day09 已完成仓库级验证模板、项目命令基线、ChangePlan / ChangeBatch 模板引用、仓库页展示与烟测验证；实现边界严格停留在“模板与命令基线冻结”层，不提前进入 Day10+ 的验证运行记录、失败归因、差异证据包、回退重做、提交候选或产品内真实 Git 写操作。
- 证据：
1. 已执行 `runtime/orchestrator/.venv/Scripts/python.exe -m py_compile runtime/orchestrator/app/domain/repository_verification.py runtime/orchestrator/app/domain/change_plan.py runtime/orchestrator/app/domain/change_batch.py runtime/orchestrator/app/core/db.py runtime/orchestrator/app/core/db_tables.py runtime/orchestrator/app/repositories/repository_verification_repository.py runtime/orchestrator/app/repositories/change_plan_repository.py runtime/orchestrator/app/services/repository_verification_service.py runtime/orchestrator/app/services/change_plan_service.py runtime/orchestrator/app/services/change_batch_service.py runtime/orchestrator/app/api/routes/planning.py runtime/orchestrator/app/api/routes/repositories.py runtime/orchestrator/scripts/v4c_day09_repository_verification_smoke.py`，确认 Day09 后端与烟测脚本编译通过。
2. 已执行 `runtime/orchestrator/.venv/Scripts/python.exe runtime/orchestrator/scripts/v4c_day09_repository_verification_smoke.py`，验证“仓库绑定 → Day09 基线初始化 / 覆盖 → ChangePlan 引用 Day09 模板 → ChangeBatch 继承并展开命令基线”链路通过。
3. 已执行 `runtime/orchestrator/.venv/Scripts/python.exe runtime/orchestrator/scripts/v4b_day08_preflight_guard_smoke.py`，确认 Day09 接入后 Day08 执行前风险守卫与人工确认链路未回归。
4. 已执行 `runtime/orchestrator/.venv/Scripts/python.exe runtime/orchestrator/scripts/v4b_day07_change_batch_smoke.py`，确认 Day09 接入后 Day07 ChangeBatch 执行准备链路未回归。
5. 已执行 `runtime/orchestrator/.venv/Scripts/python.exe runtime/orchestrator/scripts/v4b_day06_change_plan_smoke.py`，确认 Day09 接入后 Day06 ChangePlan 草案能力未回归。
6. 已执行 `cmd /c npm run build`，确认前端 Day09 仓库验证模板面板、ChangePlan 抽屉模板选择与 ChangeBatch 看板展示通过 TypeScript 与 Vite 构建。
7. 仓库页的 `RepositoryVerificationPanel` 已能展示并编辑当前验证基线、工作目录、超时、默认启用状态和最近更新时间；Day06 / Day07 页面已能显示模板引用和展开后的命令基线，满足 Day09 验收要求。

---

## 后续补测建议

1. 若 Day09 模板结构继续调整，优先回归 `v4c_day09_repository_verification_smoke.py` 与 `cmd /c npm run build`。
2. 若 Day10 开始落地验证运行记录，应补充“模板引用 → 运行记录生成 → 失败归因”的跨 Day 回归验证。
3. 若后续为仓库引入专用 lint 工具，可把 Day09 当前的编译检查基线平滑替换为真实 lint 命令，并回归本文件列出的检查项。
