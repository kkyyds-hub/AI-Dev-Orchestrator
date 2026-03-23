# Day08 执行前风险守卫与人工确认

- 版本：`V4`
- 模块 / 提案：`模块B：文件定位与变更计划`
- 原始日期：`2026-04-29`
- 原始来源：`V4 正式版总纲 / 模块B：文件定位与变更计划 / Day08`
- 当前回填状态：**已完成**
- 回填口径：已严格按 Day08 范围完成执行前风险守卫、标准化风险分类、人工确认闸门、仓库页 / 审批页展示、项目时间线回写与最小烟测；未提前跨入 Day09 及以后，不在产品能力里执行真实代码修改、验证运行、证据包、回退链路、提交候选或任何真实 Git 写操作。

---

## 今日目标

在任何实际代码改动之前，先把高风险文件、危险命令、大范围变更和敏感目录识别出来，并形成显式人工确认闸门。

---

## 当日交付

1. `runtime/orchestrator/app/services/change_risk_guard_service.py`
2. `runtime/orchestrator/app/api/routes/approvals.py`
3. `runtime/orchestrator/app/api/routes/repositories.py`
4. `apps/web/src/features/approvals/RepositoryPreflightPanel.tsx`
5. `apps/web/src/features/repositories/components/PreflightChecklist.tsx`
6. `runtime/orchestrator/scripts/v4b_day08_preflight_guard_smoke.py`

### 关联支撑改动

1. `runtime/orchestrator/app/domain/change_batch.py`
2. `runtime/orchestrator/app/repositories/change_batch_repository.py`
3. `runtime/orchestrator/app/core/db.py`
4. `runtime/orchestrator/app/core/db_tables.py`
5. `runtime/orchestrator/app/api/routes/projects.py`
6. `apps/web/src/features/repositories/ChangeBatchBoard.tsx`
7. `apps/web/src/features/repositories/RepositoryOverviewPage.tsx`
8. `apps/web/src/features/repositories/api.ts`
9. `apps/web/src/features/repositories/hooks.ts`
10. `apps/web/src/features/repositories/types.ts`
11. `apps/web/src/features/approvals/api.ts`
12. `apps/web/src/features/approvals/hooks.ts`
13. `apps/web/src/features/approvals/types.ts`
14. `apps/web/src/features/projects/types.ts`

---

## 验收点

1. 系统能对危险目录、敏感文件、大范围变更和高风险命令给出标准化风险分类
2. 高风险变更批次会被阻断并显式转入人工确认，不允许默认放行
3. 低风险变更批次可以形成“可进入执行”的预检结果
4. 预检结果能回写到审批、项目时间线和变更批次详情
5. Day08 只建立执行前守卫，不提前执行代码修改、验证命令或提交动作

---

## 边界澄清

1. Day08 只做执行前风险守卫与人工确认，不提前进入 Day09 仓库验证模板、验证命令基线、验证运行记录或证据包。
2. Day08 只识别并分类命令文本，不在产品内执行真实代码修改、验证命令、`checkout` / `commit` / `push` / `merge` 等真实 Git 写操作。
3. “人工确认已放行”只表示“允许人工进入下一步”，不等于系统自动执行，也不代表 Day14 审批或 Day13 提交候选已经开始。
4. 本次开发过程中的本地 Git commit 仅用于仓库实现收口，不代表产品内新增任何真实 Git 写操作能力。

---

## 回填记录

- 当前结论：**已完成**
- 回填说明：已在 `ChangeBatch` 上新增结构化 `preflight` 状态，落地 Day08 的风险守卫服务、预检接口、人工确认接口、审批页人工确认面板、仓库页预检检查单与项目时间线回写；系统会在任何实际执行前，对敏感目录、敏感文件、危险命令和大范围变更形成统一风险分类，并对高风险批次显式阻断、转入人工确认；整条实现严格停留在执行前守卫层，不进入 Day09+ 的验证运行、证据包、回退重做、提交候选，也未在产品链路内加入任何真实 Git 写操作。
- 回填证据：
1. `runtime/orchestrator/app/services/change_risk_guard_service.py` 已实现 Day08 风险分类、低风险放行、高风险阻断、人工确认与项目时间线事件投影。
2. `runtime/orchestrator/app/domain/change_batch.py`、`runtime/orchestrator/app/repositories/change_batch_repository.py`、`runtime/orchestrator/app/core/db.py`、`runtime/orchestrator/app/core/db_tables.py` 已补齐 `ChangeBatchPreflight` 持久化结构与 SQLite 升级入口。
3. `runtime/orchestrator/app/api/routes/repositories.py` 已新增变更批次执行前预检接口；`runtime/orchestrator/app/api/routes/approvals.py` 已新增项目级预检队列、详情与人工确认动作接口；`runtime/orchestrator/app/api/routes/projects.py` 已把 Day08 结果回写到项目时间线。
4. `apps/web/src/features/repositories/components/PreflightChecklist.tsx`、`apps/web/src/features/repositories/ChangeBatchBoard.tsx`、`apps/web/src/features/repositories/RepositoryOverviewPage.tsx` 已把 Day08 预检结果接入仓库页，展示风险分类、命令检查、范围统计与时间线结果。
5. `apps/web/src/features/approvals/RepositoryPreflightPanel.tsx` 以及对应 `api/hooks/types` 已在审批区新增“执行前人工确认”面板，可查看高风险批次并显式给出放行 / 驳回结论。
6. `runtime/orchestrator/scripts/v4b_day08_preflight_guard_smoke.py` 已覆盖“高风险批次阻断并转人工确认 + 低风险批次可进入执行 + 审批页 / 时间线回写”的最小链路。

---

## 关键产物路径

1. `runtime/orchestrator/app/domain/change_batch.py`
2. `runtime/orchestrator/app/repositories/change_batch_repository.py`
3. `runtime/orchestrator/app/services/change_batch_service.py`
4. `runtime/orchestrator/app/services/change_risk_guard_service.py`
5. `runtime/orchestrator/app/api/routes/repositories.py`
6. `runtime/orchestrator/app/api/routes/approvals.py`
7. `runtime/orchestrator/app/api/routes/projects.py`
8. `runtime/orchestrator/app/core/db.py`
9. `runtime/orchestrator/app/core/db_tables.py`
10. `apps/web/src/features/repositories/components/PreflightChecklist.tsx`
11. `apps/web/src/features/repositories/ChangeBatchBoard.tsx`
12. `apps/web/src/features/repositories/RepositoryOverviewPage.tsx`
13. `apps/web/src/features/repositories/api.ts`
14. `apps/web/src/features/repositories/hooks.ts`
15. `apps/web/src/features/repositories/types.ts`
16. `apps/web/src/features/approvals/RepositoryPreflightPanel.tsx`
17. `apps/web/src/features/approvals/api.ts`
18. `apps/web/src/features/approvals/hooks.ts`
19. `apps/web/src/features/approvals/types.ts`
20. `apps/web/src/features/projects/types.ts`
21. `runtime/orchestrator/scripts/v4b_day08_preflight_guard_smoke.py`

---

## 上下游衔接

- 前一日：Day07 变更批次与任务执行准备
- 后一日：Day09 仓库验证模板与项目命令基线
- 对应测试文档：`docs/01-版本冻结计划/V4/02-模块B-文件定位与变更计划/02-测试验证/Day08-执行前风险守卫与人工确认-测试.md`

---

## 顺延与备注

### 顺延项
1. Day09 的验证模板、项目命令基线、验证运行记录与证据包仍保持未开始。

### 备注
1. Day08 的核心价值是把“是否允许进入执行”前置成结构化守卫：先识别高风险，再决定是否必须人工接管，而不是先运行再补救。
2. 本次实现只形成预检结果与人工确认，不做真实代码执行，也不在产品内提供任何真实 Git 写操作能力。
