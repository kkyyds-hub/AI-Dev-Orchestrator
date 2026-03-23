# Day09 仓库验证模板与项目命令基线

- 版本：`V4`
- 模块 / 提案：`模块C：验证基线与证据沉淀`
- 原始日期：`2026-04-30`
- 原始来源：`V4 正式版总纲 / 模块C：验证基线与证据沉淀 / Day09`
- 当前回填状态：**已完成**
- 回填口径：已严格按 Day09 范围完成仓库级 `build / test / lint / typecheck` 模板、项目命令基线、ChangePlan / ChangeBatch 模板引用、仓库页展示与最小烟测；未提前跨入 Day10+ 的验证运行记录、失败归因、差异证据包、回退重做、提交候选，也未在产品链路里执行任何真实 Git 写操作。

---

## 今日目标

为仓库建立可复用的 `build / test / lint / typecheck` 命令模板，让每个变更计划都能引用稳定的验证基线，而不是临时拼接命令。

---

## 当日交付

1. `runtime/orchestrator/app/domain/repository_verification.py`
2. `runtime/orchestrator/app/repositories/repository_verification_repository.py`
3. `runtime/orchestrator/app/services/repository_verification_service.py`
4. `runtime/orchestrator/app/api/routes/repositories.py`
5. `apps/web/src/features/repositories/RepositoryVerificationPanel.tsx`
6. `runtime/orchestrator/scripts/v4c_day09_repository_verification_smoke.py`

### 关联支撑改动

1. `runtime/orchestrator/app/core/db.py`
2. `runtime/orchestrator/app/core/db_tables.py`
3. `runtime/orchestrator/app/domain/change_plan.py`
4. `runtime/orchestrator/app/domain/change_batch.py`
5. `runtime/orchestrator/app/repositories/change_plan_repository.py`
6. `runtime/orchestrator/app/services/change_plan_service.py`
7. `runtime/orchestrator/app/services/change_batch_service.py`
8. `runtime/orchestrator/app/api/routes/planning.py`
9. `apps/web/src/features/repositories/api.ts`
10. `apps/web/src/features/repositories/hooks.ts`
11. `apps/web/src/features/repositories/types.ts`
12. `apps/web/src/features/repositories/RepositoryOverviewPage.tsx`
13. `apps/web/src/features/repositories/ChangeBatchBoard.tsx`
14. `apps/web/src/features/projects/ChangePlanDrawer.tsx`
15. `apps/web/src/features/projects/types.ts`

---

## 验收点

1. 仓库可以配置最小验证命令模板，并区分 `build / test / lint / typecheck` 类别
2. 变更计划或变更批次可以引用其中一个或多个命令模板
3. 命令模板至少记录命令文本、工作目录、超时、是否默认启用等字段
4. 项目或仓库页面可以查看当前验证基线和最后更新时间
5. Day09 只冻结验证模板，不提前记录验证运行结果或差异证据

---

## 边界澄清

1. Day09 只冻结仓库验证模板与项目命令基线，不提前实现 Day10 的验证运行记录、失败归因扩展。
2. Day09 只让 ChangePlan / ChangeBatch 引用模板并沉淀命令文本，不在产品内执行真实验证命令，也不生成 Day11 差异证据包。
3. Day09 不进入 Day12 的回退重做与仓库复盘，也不进入 Day13+ 的提交候选、审批放行或任何真实 Git 写操作。
4. 本次开发过程中的本地 Git commit 仅用于仓库实现收口，不代表产品内新增任何真实 Git 写能力；`.gitignore` 已复核，无需为 Day09 额外扩张忽略规则。

---

## 回填记录

- 当前结论：**已完成**
- 回填说明：已新增 Day09 仓库验证模板领域模型、持久化仓储、服务与仓库路由，为每个绑定仓库建立固定的 `build / test / lint / typecheck` 基线；仓库页新增 `RepositoryVerificationPanel` 可查看与编辑当前命令模板、最后更新时间；Day06 ChangePlan 可直接引用一个或多个 Day09 模板，Day07 ChangeBatch 会保留模板引用并展开出 Day08 预检可复用的命令基线；整条实现严格停留在模板与引用层，不进入 Day10+ 的运行记录、失败归因、证据包、回退重做、提交候选，也未在产品链路内加入任何真实 Git 写操作。
- 回填证据：
1. `runtime/orchestrator/app/domain/repository_verification.py`、`runtime/orchestrator/app/repositories/repository_verification_repository.py`、`runtime/orchestrator/app/services/repository_verification_service.py` 已建立 Day09 的模板分类、命令字段、默认基线、持久化与模板引用解析能力。
2. `runtime/orchestrator/app/core/db_tables.py` 与 `runtime/orchestrator/app/core/db.py` 已补齐 `repository_verification_templates` 表和 `change_plan_versions.verification_templates_json` 的 SQLite 升级入口。
3. `runtime/orchestrator/app/api/routes/repositories.py` 已新增 Day09 基线查询 / 覆盖接口；仓库页加载时可自动初始化默认基线，并返回最后更新时间。
4. `runtime/orchestrator/app/domain/change_plan.py`、`runtime/orchestrator/app/repositories/change_plan_repository.py`、`runtime/orchestrator/app/services/change_plan_service.py`、`runtime/orchestrator/app/api/routes/planning.py` 已让 ChangePlan 持久化 Day09 模板引用，同时保留手动命令补充。
5. `runtime/orchestrator/app/domain/change_batch.py`、`runtime/orchestrator/app/services/change_batch_service.py`、`apps/web/src/features/repositories/ChangeBatchBoard.tsx` 已让 ChangeBatch 继承模板引用，并把模板命令与手动命令合并成统一验证命令基线供 Day08 预检复用。
6. `apps/web/src/features/repositories/RepositoryVerificationPanel.tsx`、`apps/web/src/features/repositories/api.ts`、`apps/web/src/features/repositories/hooks.ts`、`apps/web/src/features/repositories/types.ts`、`apps/web/src/features/repositories/RepositoryOverviewPage.tsx` 已把 Day09 基线接入仓库页，展示当前模板、工作目录、超时、默认启用状态和最后更新时间。
7. `apps/web/src/features/projects/ChangePlanDrawer.tsx` 与 `apps/web/src/features/projects/types.ts` 已在 Day06 草案抽屉中接入 Day09 模板选择、命令预览与版本时间线展示。
8. `runtime/orchestrator/scripts/v4c_day09_repository_verification_smoke.py` 已覆盖“仓库绑定 → Day09 基线初始化 / 更新 → ChangePlan 引用模板 → ChangeBatch 继承并展开命令基线”的最小链路。

---

## 关键产物路径

1. `runtime/orchestrator/app/domain/repository_verification.py`
2. `runtime/orchestrator/app/repositories/repository_verification_repository.py`
3. `runtime/orchestrator/app/services/repository_verification_service.py`
4. `runtime/orchestrator/app/api/routes/repositories.py`
5. `runtime/orchestrator/app/api/routes/planning.py`
6. `runtime/orchestrator/app/core/db.py`
7. `runtime/orchestrator/app/core/db_tables.py`
8. `runtime/orchestrator/app/domain/change_plan.py`
9. `runtime/orchestrator/app/domain/change_batch.py`
10. `runtime/orchestrator/app/repositories/change_plan_repository.py`
11. `runtime/orchestrator/app/services/change_plan_service.py`
12. `runtime/orchestrator/app/services/change_batch_service.py`
13. `apps/web/src/features/repositories/RepositoryVerificationPanel.tsx`
14. `apps/web/src/features/repositories/RepositoryOverviewPage.tsx`
15. `apps/web/src/features/repositories/ChangeBatchBoard.tsx`
16. `apps/web/src/features/repositories/api.ts`
17. `apps/web/src/features/repositories/hooks.ts`
18. `apps/web/src/features/repositories/types.ts`
19. `apps/web/src/features/projects/ChangePlanDrawer.tsx`
20. `apps/web/src/features/projects/types.ts`
21. `runtime/orchestrator/scripts/v4c_day09_repository_verification_smoke.py`

---

## 上下游衔接

- 前一日：Day08 执行前风险守卫与人工确认
- 后一日：Day10 验证运行记录与失败归因扩展
- 对应测试文档：`docs/01-版本冻结计划/V4/03-模块C-验证基线与证据沉淀/02-测试验证/Day09-仓库验证模板与项目命令基线-测试.md`

---

## 顺延与备注

### 顺延项
1. Day10 的验证运行记录与失败归因扩展仍保持未开始。
2. Day11 的代码差异视图与验收证据包仍保持未开始。
3. Day12 的回退重做、仓库复盘与后续 Day13+ 提交候选仍保持未开始。

### 备注
1. 当前仓库尚未引入专用 lint 工具，因此 Day09 的 `lint` 类模板先以 Python 源码编译检查承接，属于“命令基线冻结”而非运行结果沉淀。
2. Day09 的核心价值是把“改完怎么验”从草案文本提升为仓库级、可引用、可复用的模板基线，为 Day10+ 后续运行记录提供稳定入口，但本次不提前实现这些后续能力。
