# Day11 代码差异视图与验收证据包

- 版本：`V4`
- 模块 / 提案：`模块C：验证基线与证据沉淀`
- 原始日期：`2026-05-02`
- 原始来源：`V4 正式版总纲 / 模块C：验证基线与证据沉淀 / Day11`
- 当前回填状态：**未开始**
- 回填口径：当前文档为 V4 冻结版计划，尚未开始实现；后续只按 Day11 范围回填，不提前跨 Day 扩 scope。

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

- 当前结论：**未开始**
- 回填说明：当前仅完成 Day11 冻结版计划建档，尚未进入实现；开始开发时需严格以今日目标、当日交付和验收点为回填边界。
- 回填证据：
1. 已建立本文档，冻结 Day11 的目标、交付和验收范围
2. 已建立对应测试验证骨架文件，待后续按真实实现回填
3. 后续启动开发后，再以实际代码、页面、脚本和烟测结果替换当前占位说明

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
