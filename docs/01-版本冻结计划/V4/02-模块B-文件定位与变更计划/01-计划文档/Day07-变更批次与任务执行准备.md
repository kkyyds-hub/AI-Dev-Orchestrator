# Day07 变更批次与任务执行准备

- 版本：`V4`
- 模块 / 提案：`模块B：文件定位与变更计划`
- 原始日期：`2026-04-28`
- 原始来源：`V4 正式版总纲 / 模块B：文件定位与变更计划 / Day07`
- 当前回填状态：**已完成**
- 回填口径：已严格按 Day07 范围完成 ChangeBatch 建模、聚合创建、任务顺序/依赖/文件重叠展示、仓库页接入与最小烟测；未提前跨入 Day08 风险预检、审批放行、验证证据包或任何产品内真实 Git 写操作。

---

## 今日目标

把多个已确认的变更计划合并成可推进的 `ChangeBatch`，明确本轮开发准备改哪些文件、按什么顺序推进、是否存在文件重叠风险。

---

## 当日交付

1. `runtime/orchestrator/app/domain/change_batch.py`
2. `runtime/orchestrator/app/repositories/change_batch_repository.py`
3. `runtime/orchestrator/app/services/change_batch_service.py`
4. `runtime/orchestrator/app/api/routes/repositories.py`
5. `apps/web/src/features/repositories/ChangeBatchBoard.tsx`
6. `runtime/orchestrator/scripts/v4b_day07_change_batch_smoke.py`

---

## 验收点

1. 项目可以基于多个变更计划创建一个变更批次并查看其状态
2. 同一批次内的任务顺序、依赖关系和文件重叠风险有明确展示
3. 系统能限制同一项目同一时刻只有一个活跃变更批次，避免范围混乱
4. 批次摘要可以回写到项目视图与时间线
5. Day07 只建立执行准备模型，不提前触发审批守卫或真实仓库动作

---

## 边界澄清

1. Day07 只建立 `ChangePlan` → `ChangeBatch` 的执行准备层，不做 Day08 风险预检、人工确认或审批放行。
2. Day07 只补批次聚合、顺序整理、重叠提醒、列表/详情/创建接口以及仓库页看板，不进入真实代码修改、验证运行、差异证据包或回退链路。
3. Day07 不做真实 `checkout` / `commit` / `push` / `PR` / `merge`，也不把任何真实 Git 写操作暴露到产品链路中。
4. 本次开发过程中的本地 Git commit 仅用于仓库实现收口，不代表产品内新增任何真实 Git 写操作能力。

---

## 回填记录

- 当前结论：**已完成**
- 回填说明：已新增 Day07 的 `ChangeBatch` 领域模型、SQLite 持久化表与仓储、服务层聚合与依赖排序逻辑，并在 `/repositories` 下补齐批次创建/列表/详情接口；前端在项目仓库页接入 `ChangeBatchBoard`，可基于多个最新 `ChangePlan` 创建批次、查看活跃批次摘要、展示任务执行顺序、依赖关系、目标文件清单、文件重叠提醒与本地时间线；整条实现严格停留在执行准备层，不进入 Day08 风险守卫、审批放行、验证证据包，也未在产品链路内加入任何真实 Git 写操作。
- 回填证据：
1. `runtime/orchestrator/app/domain/change_batch.py` 已定义 `ChangeBatch`、`ChangeBatchPlanSnapshot`、`ChangeBatchLinkedDeliverable` 等 Day07 聚合对象。
2. `runtime/orchestrator/app/core/db_tables.py` 与 `runtime/orchestrator/app/repositories/change_batch_repository.py` 已补齐 `change_batches` 表和批次持久化读写逻辑。
3. `runtime/orchestrator/app/services/change_batch_service.py` 已把多 ChangePlan 聚合、任务依赖排序、目标文件汇总、重叠识别和批次时间线整理封装为 Day07 服务。
4. `runtime/orchestrator/app/api/routes/repositories.py` 已新增项目级 ChangeBatch 创建、列表、详情接口，并限制同项目只有一个活跃批次。
5. `apps/web/src/features/repositories/ChangeBatchBoard.tsx`、`apps/web/src/features/repositories/RepositoryOverviewPage.tsx`、`apps/web/src/features/repositories/api.ts`、`apps/web/src/features/repositories/hooks.ts`、`apps/web/src/features/repositories/types.ts` 已把 Day07 看板接入仓库页，展示批次摘要、任务顺序、依赖、目标文件与重叠提醒。
6. `runtime/orchestrator/scripts/v4b_day07_change_batch_smoke.py` 已验证“Day06 ChangePlan → Day07 ChangeBatch 创建 → 列表/详情 → 活跃批次冲突阻断”的最小链路。

---

## 关键产物路径

1. `runtime/orchestrator/app/domain/change_batch.py`
2. `runtime/orchestrator/app/repositories/change_batch_repository.py`
3. `runtime/orchestrator/app/services/change_batch_service.py`
4. `runtime/orchestrator/app/api/routes/repositories.py`
5. `runtime/orchestrator/app/core/db_tables.py`
6. `apps/web/src/features/repositories/ChangeBatchBoard.tsx`
7. `apps/web/src/features/repositories/RepositoryOverviewPage.tsx`
8. `apps/web/src/features/repositories/api.ts`
9. `apps/web/src/features/repositories/hooks.ts`
10. `apps/web/src/features/repositories/types.ts`
11. `runtime/orchestrator/scripts/v4b_day07_change_batch_smoke.py`

---

## 上下游衔接

- 前一日：Day06 仓库任务映射与变更计划草案
- 后一日：Day08 执行前风险守卫与人工确认
- 对应测试文档：`docs/01-版本冻结计划/V4/02-模块B-文件定位与变更计划/02-测试验证/Day07-变更批次与任务执行准备-测试.md`

---

## 顺延与备注

### 顺延项
1. Day08 风险守卫、人工确认、审批放行与验证证据包仍保持未开始。

### 备注
1. Day07 的核心价值是把多个已确认的 `ChangePlan` 收敛成一个可执行准备的 `ChangeBatch`，让“准备改哪些文件、先后顺序是什么、哪些文件互相重叠”第一次有统一视图。
2. 本次实现只形成批次与执行准备，不做真实代码执行，也不在产品内提供任何真实 Git 写操作能力。
