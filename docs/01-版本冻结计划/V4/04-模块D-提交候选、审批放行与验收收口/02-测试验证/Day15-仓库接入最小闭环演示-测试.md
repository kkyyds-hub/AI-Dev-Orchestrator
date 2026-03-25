# Day15 仓库接入最小闭环演示 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V4/04-模块D-提交候选、审批放行与验收收口/01-计划文档/Day15-仓库接入最小闭环演示.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 至少能跑通“绑定仓库 -> 刷新快照 -> 生成变更计划 -> 建立批次 -> 预检 -> 记录验证 -> 生成证据包 -> 形成提交草案 -> 展示放行判断”的最小链路
2. 关键接口、关键页面和关键状态流都有最小烟测证据
3. 如有未完成能力，必须在 Day15 演示中明确标记缺口，不伪造通过
4. 演示链路保持本地优先，不扩展到远程仓库推送、在线协作或真实 Git 写动作自动执行
5. Day15 只做闭环演示，不继续新增 Day16 之外的产品能力，也不把演示通过解释为已经具备真实 Git 自动化

---

## 实际验证动作

1. 核对关键产物与接线路径已落地：
   - `runtime/orchestrator/scripts/v4d_day15_repository_flow_smoke.py`
   - `runtime/orchestrator/app/api/routes/repositories.py`
   - `runtime/orchestrator/app/api/routes/projects.py`
   - `runtime/orchestrator/app/api/routes/approvals.py`
   - `apps/web/src/features/projects/ProjectOverviewPage.tsx`
   - `apps/web/src/features/repositories/DiffSummaryPage.tsx`
   - `apps/web/src/features/repositories/CommitDraftPanel.tsx`
2. 后端语法检查：
   - `python -m py_compile runtime/orchestrator/app/api/routes/repositories.py runtime/orchestrator/app/api/routes/projects.py runtime/orchestrator/app/api/routes/approvals.py runtime/orchestrator/scripts/v4d_day15_repository_flow_smoke.py`
   - 结果：通过。
3. 前端构建验证：
   - `cmd /c npm run build`（工作目录：`apps/web`）
   - 结果：通过（Vite 构建完成，仅保留 chunk size warning，不影响 Day15 功能验收）。
4. Day15 烟测脚本：
   - `.venv/Scripts/python.exe scripts/v4d_day15_repository_flow_smoke.py`（工作目录：`runtime/orchestrator`）
   - 结果：通过；关键输出包含 `repository_day15_status=\"ready_for_review\"`、`project_day15_status=\"ready_for_review\"`、`approvals_day15_selected_status=\"approved\"`、`blocked_before=true`、`approve_blocked_status_code=409`、`head_unchanged=true`、`git_write_actions_triggered=false`，验证闭环链路打通且未触发真实 Git 写动作。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：Day15 范围内后端三条聚合接口、前端三处状态展示和 Day15 烟测脚本均已接通；闭环演示止于“可审阅、可解释、可拒绝”，不代表真实 Git 自动执行能力。
- 证据：
1. `/repositories/projects/{project_id}/day15-flow`、`/projects/{project_id}/day15-repository-flow`、`/approvals/projects/{project_id}/day15-release-judgement` 已接通，能输出 Day15 闭环总览与放行判断
2. Day15 烟测已显式覆盖“证据包 -> 提交草案 -> 放行判断”后段链路，并验证阻断场景（缺失 `commit_draft` 时审批 `409`）
3. 最终输出 `head_unchanged=true` 与 `git_write_actions_triggered=false`，确认演示未触发真实 Git 写动作
4. 前端构建通过，老板总览/差异页/提交草案页均可显示 Day15 闭环状态卡片

---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做最小烟测。
2. 若当前状态为“未开始”，先按计划文档完成关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在实现变化时补回归验证。
