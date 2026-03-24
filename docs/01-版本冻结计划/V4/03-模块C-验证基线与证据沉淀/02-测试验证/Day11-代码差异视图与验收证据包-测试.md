# Day11 代码差异视图与验收证据包 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V4/03-模块C-验证基线与证据沉淀/01-计划文档/Day11-代码差异视图与验收证据包.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 系统可以输出按文件维度聚合的差异摘要，包括增删改统计和关键文件列表
2. 证据包至少包含变更计划、验证结果、交付件引用和审批上下文摘要
3. 同一批次的证据包支持版本快照，便于审批前后对比
4. 项目、交付件或审批页面都能反查对应证据包
5. Day11 只冻结差异与证据汇总，不提前进入回退重做链路

---

## 实际验证动作

1. 核对关键产物均已落地并已接线：
   - `runtime/orchestrator/app/domain/change_evidence.py`
   - `runtime/orchestrator/app/services/diff_summary_service.py`
   - `runtime/orchestrator/app/api/routes/deliverables.py`
   - `apps/web/src/features/deliverables/ChangeEvidencePanel.tsx`
   - `apps/web/src/features/repositories/DiffSummaryPage.tsx`
   - `runtime/orchestrator/scripts/v4c_day11_change_evidence_smoke.py`
2. 语法检查：
   - `python -m py_compile runtime/orchestrator/app/domain/change_evidence.py runtime/orchestrator/app/services/diff_summary_service.py runtime/orchestrator/app/api/routes/deliverables.py runtime/orchestrator/scripts/v4c_day11_change_evidence_smoke.py`
   - 结果：通过。
3. 前端构建验证：
   - `cmd /c npm run build`（工作目录：`apps/web`）
   - 结果：通过（Vite 构建完成，仅保留 chunk size warning，不影响 Day11 功能验收）。
4. Day11 烟测脚本：
   - `.\\.venv\\Scripts\\python scripts/v4c_day11_change_evidence_smoke.py`（工作目录：`runtime/orchestrator`）
   - 结果：通过；成功返回 `project_package_key / deliverable_package_key / approval_package_key`，并断言 `changed_file_count=3`、`key_file_count=3`、`verification_total_runs=3`、`snapshot_count=5`。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：Day11 范围内产物与验证已闭环；仅覆盖差异视图与证据包汇总，不包含 Day12+ 的回退重做、提交候选或审批放行。
- 证据：
1. 差异摘要可按文件维度输出，包含增删改统计、关键文件列表、工作区脏状态与目标文件反查关系。
2. 证据包已包含 ChangePlan 快照、VerificationRun 汇总、交付件引用、审批上下文与版本快照。
3. 项目页（`DiffSummaryPage`）、交付件页（`ChangeEvidencePanel`）与审批抽屉（`ChangeEvidencePanel`）均可反查同一证据包。
4. 烟测覆盖项目/交付件/审批三个接口并完成关键字段断言，验证结果通过。

---

## 后续补测建议

1. 若后续调整 `DiffSummaryService` 的聚合规则（关键文件筛选、统计口径、快照拼装），优先回归 Day11 烟测脚本。
2. 若后续调整前端面板结构或接口字段映射，至少补跑 `cmd /c npm run build` 并做一次项目/交付件/审批页面手工联调。
3. Day12+ 开发阶段继续保持范围隔离：回归仅验证 Day11 能力，不提前并入回退重做、提交候选或审批放行自动化。
