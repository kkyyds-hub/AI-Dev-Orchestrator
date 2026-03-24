# Day14 审批闸门与放行检查单 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V4/04-模块D-提交候选、审批放行与验收收口/01-计划文档/Day14-审批闸门与放行检查单.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 放行检查单至少覆盖仓库绑定、快照新鲜度、变更计划、风险预检、验证结果、差异证据和提交草案
2. 任一关键项缺失时，审批闸门会显式阻断并给出缺口说明
3. 审批动作会记录通过、驳回、补证据等决策及其原因
4. 放行闸门仍保持本地优先，不在 Day14 扩展到自动 `push`、自动 PR、自动 `merge`，也不因审批通过而自动执行 `git commit`
5. 审批口径与 V3 的交付件 / 审批链路保持兼容

---

## 实际验证动作

1. 核对关键产物与接线路径已落地：
   - `runtime/orchestrator/app/services/repository_release_gate_service.py`
   - `runtime/orchestrator/app/api/routes/approvals.py`
   - `runtime/orchestrator/app/api/routes/repositories.py`
   - `apps/web/src/features/approvals/RepositoryReleaseChecklist.tsx`
   - `apps/web/src/features/approvals/RepositoryReleaseGatePanel.tsx`
   - `apps/web/src/features/approvals/ApprovalInboxPage.tsx`
   - `apps/web/src/features/approvals/ApprovalGatePage.tsx`
   - `runtime/orchestrator/scripts/v4d_day14_release_gate_smoke.py`
2. 后端语法检查：
   - `python -m py_compile runtime/orchestrator/app/services/repository_release_gate_service.py runtime/orchestrator/app/api/routes/approvals.py runtime/orchestrator/app/api/routes/repositories.py runtime/orchestrator/scripts/v4d_day14_release_gate_smoke.py`
   - 结果：通过。
3. 前端构建验证：
   - `cmd /c npm run build`（工作目录：`apps/web`）
   - 结果：通过（Vite 构建完成，仅保留 chunk size warning，不影响 Day14 功能验收）。
4. Day14 烟测脚本：
   - `runtime/orchestrator/.venv/Scripts/python.exe scripts/v4d_day14_release_gate_smoke.py`（工作目录：`runtime/orchestrator`）
   - 结果：通过；关键输出包含 `blocked_before=true`、`approve_blocked_status_code=409`、`final_status=approved`、`decision_actions=["request_changes","reject","approve"]`、`head_unchanged=true`、`git_write_actions_triggered=false`，验证缺口阻断、审批动作记录与“通过不自动写 Git”口径。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：Day14 范围内后端放行检查单、阻断策略、审批记录与前端展示/动作均已接通；“审批通过”仅表示放行资格成立，不代表真实 Git 动作触发。
- 证据：
1. `GET /approvals/projects/{project_id}/repository-release-gate`、`GET /approvals/repository-release-gate/{change_batch_id}`、`POST /approvals/repository-release-gate/{change_batch_id}/actions` 已接通，支持通过/驳回/补证据动作和原因沉淀
2. `GET /repositories/projects/{project_id}/release-gates`、`GET /repositories/change-batches/{change_batch_id}/release-checklist` 已接通，确保与仓库链路兼容
3. 烟测中先验证阻断（缺失提交草案时 `409`），再验证三类动作记录，最终 `head_unchanged=true` 与 `git_write_actions_triggered=false` 证明未触发真实 Git 写操作
4. 前端构建通过，Day14 面板可展示检查单、缺口与审批记录，并可提交三类审批动作

---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做最小烟测。
2. 若当前状态为“未开始”，先按计划文档完成关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在实现变化时补回归验证。
