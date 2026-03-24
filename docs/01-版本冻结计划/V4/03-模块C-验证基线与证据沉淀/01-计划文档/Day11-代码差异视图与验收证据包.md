# Day11 代码差异视图与验收证据包

- 版本：`V4`
- 模块 / 提案：`模块C：验证基线与证据沉淀`
- 原始日期：`2026-05-02`
- 原始来源：`V4 正式版总纲 / 模块C：验证基线与证据沉淀 / Day11`
- 当前回填状态：**已完成**
- 回填口径：Day11 已按冻结边界完成代码差异视图与验收证据包落地；仅覆盖差异汇总、验证结果汇总、交付件/审批反查与快照对比，不提前进入 Day12+。

---

## 今日目标

把仓库变更的文件差异、验证结果、交付件引用和审批上下文汇总成一份可以直接用于老板验收的证据包。

---

## 当日交付

1. `runtime/orchestrator/app/domain/change_evidence.py`
2. `runtime/orchestrator/app/services/diff_summary_service.py`
3. `runtime/orchestrator/app/api/routes/deliverables.py`
4. `apps/web/src/features/deliverables/ChangeEvidencePanel.tsx`
5. `apps/web/src/features/repositories/DiffSummaryPage.tsx`
6. `runtime/orchestrator/scripts/v4c_day11_change_evidence_smoke.py`

---

## 验收点

1. 系统可以输出按文件维度聚合的差异摘要，包括增删改统计和关键文件列表
2. 证据包至少包含变更计划、验证结果、交付件引用和审批上下文摘要
3. 同一批次的证据包支持版本快照，便于审批前后对比
4. 项目、交付件或审批页面都能反查对应证据包
5. Day11 只冻结差异与证据汇总，不提前进入回退重做链路

---

## 回填记录

- 当前结论：**已完成**
- 回填说明：已完成后端 DiffSummaryService 与证据包接口、前端差异视图与证据面板，并在项目页、交付件页、审批抽屉三处接通反查入口，范围严格收口在 Day11。
- 回填证据：
1. 新增 `runtime/orchestrator/app/domain/change_evidence.py`，定义 Day11 证据包领域模型，覆盖差异摘要、计划快照、验证汇总、交付件引用、审批上下文、版本快照与反查索引。
2. 新增 `runtime/orchestrator/app/services/diff_summary_service.py`，按文件维度聚合 Git 差异（增删改统计、关键文件、脏工作区）并整合 ChangeBatch / VerificationRun / Deliverable / Approval 生成证据包。
3. 扩展 `runtime/orchestrator/app/api/routes/deliverables.py`，新增项目、交付件、审批三个维度的 `change-evidence` 查询接口，并补充 404 错误映射。
4. 新增 `apps/web/src/features/repositories/DiffSummaryPage.tsx` 与 `apps/web/src/features/deliverables/ChangeEvidencePanel.tsx`，并在 `RepositoryOverviewPage`、`DeliverableVersionList`、`ApprovalActionDrawer` 完成展示接入。
5. 新增 `runtime/orchestrator/scripts/v4c_day11_change_evidence_smoke.py`，覆盖差异聚合、证据包结构完整性、项目/交付件/审批反查和版本快照断言。
6. 已执行并通过：
   - `python -m py_compile runtime/orchestrator/app/domain/change_evidence.py runtime/orchestrator/app/services/diff_summary_service.py runtime/orchestrator/app/api/routes/deliverables.py runtime/orchestrator/scripts/v4c_day11_change_evidence_smoke.py`
   - `cmd /c npm run build`（`apps/web`）
   - `.\\.venv\\Scripts\\python scripts/v4c_day11_change_evidence_smoke.py`（`runtime/orchestrator`）

---

## 关键产物路径

1. `runtime/orchestrator/app/domain/change_evidence.py`
2. `runtime/orchestrator/app/services/diff_summary_service.py`
3. `runtime/orchestrator/app/api/routes/deliverables.py`
4. `apps/web/src/features/deliverables/ChangeEvidencePanel.tsx`
5. `apps/web/src/features/repositories/DiffSummaryPage.tsx`
6. `runtime/orchestrator/scripts/v4c_day11_change_evidence_smoke.py`

---

## 上下游衔接

- 前一日：Day10 验证运行记录与失败归因扩展
- 后一日：Day12 回退重做与仓库复盘收口
- 对应测试文档：`docs/01-版本冻结计划/V4/03-模块C-验证基线与证据沉淀/02-测试验证/Day11-代码差异视图与验收证据包-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无；如 Day11 启动时发现上游能力未就绪，只在本 Day 文档内记录缺口，不提前并入下一天范围。

### 备注
1. Day11 只做差异和证据汇总，不提前实现驳回后的回退重做。
