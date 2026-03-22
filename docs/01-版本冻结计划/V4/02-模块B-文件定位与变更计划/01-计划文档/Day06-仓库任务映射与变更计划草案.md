# Day06 仓库任务映射与变更计划草案

- 版本：`V4`
- 模块 / 提案：`模块B：文件定位与变更计划`
- 原始日期：`2026-04-27`
- 原始来源：`V4 正式版总纲 / 模块B：文件定位与变更计划 / Day06`
- 当前回填状态：**已完成**
- 回填口径：已严格按 Day06 范围完成 ChangePlan 草案映射、版本化持久化、项目详情反查映射与最小前端抽屉接入；未提前跨入 Day07 变更批次、Day08 风险预检、真实代码改动执行或任何产品内真实 Git 写操作。

---

## 今日目标

把项目任务、交付件和候选文件集合映射成结构化 `ChangePlan`，让“要改什么、为什么改、改完怎么验”第一次有统一记录。

---

## 当日交付

1. `runtime/orchestrator/app/domain/change_plan.py`
2. `runtime/orchestrator/app/repositories/change_plan_repository.py`
3. `runtime/orchestrator/app/services/change_plan_service.py`
4. `runtime/orchestrator/app/api/routes/planning.py`
5. `apps/web/src/features/projects/ChangePlanDrawer.tsx`
6. `runtime/orchestrator/scripts/v4b_day06_change_plan_smoke.py`

---

## 验收点

1. 任务可以创建、查看和更新一份变更计划草案
2. 变更计划至少包含目标文件、预期动作、风险说明、验证命令引用和关联交付件
3. 同一个交付件可以记录多版变更计划草案，保留版本时间线
4. 项目详情能反查任务与变更计划的映射关系
5. Day06 只冻结计划草案，不提前进入批次调度和风险预检

---

## 边界澄清

1. Day06 只建立任务 → 交付件 → 候选文件集合 → `ChangePlan` 的结构化草案映射，不做真实代码执行。
2. Day06 只补 `ChangePlan` 头记录、版本快照、列表/详情/追加版本接口以及项目页抽屉，不进入 Day07 变更批次拆分。
3. Day06 不做 Day08 风险守卫、审批放行、验证证据包，也不扩展到真实 Git 提交、push、PR 或 merge。
4. 本次提交中的 Git commit 仅用于仓库开发过程收口，不代表产品内新增任何真实 Git 写操作能力。

---

## 回填记录

- 当前结论：**已完成**
- 回填说明：已新增 Day06 的 `ChangePlan` 领域模型、SQLite 持久化表与仓储、服务层版本化逻辑、`/planning` 下的创建/列表/详情/追加版本接口；前端在项目仓库页接入 `ChangePlanDrawer`、任务映射卡片与 Day05 `CodeContextPack` 透传，形成“任务 + 交付件 + 候选文件集合”的统一草案入口；整条实现严格停留在草案层，不进入 Day07/Day08，也未在产品链路内加入任何真实 Git 写操作。
- 回填证据：
1. `runtime/orchestrator/app/domain/change_plan.py` 已定义 `ChangePlan`、`ChangePlanVersion`、`ChangePlanTargetFile` 等 Day06 结构化对象。
2. `runtime/orchestrator/app/core/db_tables.py` 与 `runtime/orchestrator/app/repositories/change_plan_repository.py` 已补齐 `change_plans` / `change_plan_versions` 表和版本化读写逻辑。
3. `runtime/orchestrator/app/services/change_plan_service.py` 已把项目、任务、交付件与版本时间线校验封装为 Day06 服务。
4. `runtime/orchestrator/app/api/routes/planning.py` 已新增项目级 ChangePlan 创建、列表、详情与追加版本接口。
5. `apps/web/src/features/projects/ChangePlanDrawer.tsx`、`apps/web/src/features/repositories/RepositoryOverviewPage.tsx`、`apps/web/src/features/repositories/components/FileLocatorPanel.tsx` 已把 Day05 `CodeContextPack` 与 Day06 草案抽屉接通，并在项目详情页提供任务反查映射入口。
6. `apps/web/src/features/projects/api.ts`、`apps/web/src/features/projects/hooks.ts`、`apps/web/src/features/projects/types.ts` 已补齐前端请求、缓存刷新与类型定义。
7. `runtime/orchestrator/scripts/v4b_day06_change_plan_smoke.py` 已验证“Day05 文件定位/上下文包 → Day06 变更计划草案 → 版本追加”的最小链路。

---

## 关键产物路径

1. `runtime/orchestrator/app/domain/change_plan.py`
2. `runtime/orchestrator/app/repositories/change_plan_repository.py`
3. `runtime/orchestrator/app/services/change_plan_service.py`
4. `runtime/orchestrator/app/api/routes/planning.py`
5. `runtime/orchestrator/app/core/db_tables.py`
6. `apps/web/src/features/projects/ChangePlanDrawer.tsx`
7. `apps/web/src/features/projects/api.ts`
8. `apps/web/src/features/projects/hooks.ts`
9. `apps/web/src/features/projects/types.ts`
10. `apps/web/src/features/repositories/RepositoryOverviewPage.tsx`
11. `apps/web/src/features/repositories/components/FileLocatorPanel.tsx`
12. `runtime/orchestrator/scripts/v4b_day06_change_plan_smoke.py`

---

## 上下游衔接

- 前一日：Day05 文件定位索引与代码上下文包
- 后一日：Day07 变更批次与任务执行准备
- 对应测试文档：`docs/01-版本冻结计划/V4/02-模块B-文件定位与变更计划/02-测试验证/Day06-仓库任务映射与变更计划草案-测试.md`

---

## 顺延与备注

### 顺延项
1. Day07 变更批次拆分、执行准备、变更分组与批次调度仍保持未开始。
2. Day08 风险守卫、人工确认、审批放行与验证证据包仍保持未开始。

### 备注
1. Day06 的核心价值是把 Day05 的候选文件集合沉淀成可版本化、可回看、可反查的 ChangePlan 草案。
2. 本次实现只形成草案与映射关系，不做真实代码变更执行，也不在产品内提供任何真实 Git 写操作能力。
