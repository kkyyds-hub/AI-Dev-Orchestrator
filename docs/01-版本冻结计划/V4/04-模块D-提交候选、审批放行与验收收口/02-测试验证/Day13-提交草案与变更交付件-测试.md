# Day13 提交草案与变更交付件 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V4/04-模块D-提交候选、审批放行与验收收口/01-计划文档/Day13-提交草案与变更交付件.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 已通过验证的变更批次可以生成一份结构化提交草案
2. 提交草案至少包含提交说明、影响范围、关联文件、验证摘要和关联交付件，并能被 Day14 直接消费
3. 同一批次的提交草案支持修订版本，不覆盖前一版说明
4. 提交草案只作为待放行交付件，不在 Day13 直接执行真实 `git commit`，也不写入 `.git` 或生成 commit hash
5. Day13 只冻结提交候选，不提前扩展到审批放行、远程仓库操作或任何自动提交动作

---

## 实际验证动作

1. 核对关键产物与接线路径已落地：
   - `runtime/orchestrator/app/domain/commit_candidate.py`
   - `runtime/orchestrator/app/repositories/commit_candidate_repository.py`
   - `runtime/orchestrator/app/services/commit_candidate_service.py`
   - `runtime/orchestrator/app/api/routes/repositories.py`
   - `apps/web/src/features/repositories/CommitDraftPanel.tsx`
   - `runtime/orchestrator/scripts/v4d_day13_commit_candidate_smoke.py`
2. 后端语法检查：
   - `python -m py_compile runtime/orchestrator/app/domain/commit_candidate.py runtime/orchestrator/app/repositories/commit_candidate_repository.py runtime/orchestrator/app/services/commit_candidate_service.py runtime/orchestrator/app/api/routes/repositories.py runtime/orchestrator/app/core/db_tables.py runtime/orchestrator/scripts/v4d_day13_commit_candidate_smoke.py`
   - 结果：通过。
3. 前端构建验证：
   - `cmd /c npm run build`（工作目录：`apps/web`）
   - 结果：通过（Vite 构建完成，仅保留 chunk size warning，不影响 Day13 功能验收）。
4. Day13 烟测脚本：
   - `runtime/orchestrator/.venv/Scripts/python.exe scripts/v4d_day13_commit_candidate_smoke.py`（工作目录：`runtime/orchestrator`）
   - 结果：通过；返回 `current_version_number=2`、`revision_count=2`、`verification_total_runs=2`、`deliverable_count=2`、`head_unchanged=true`，验证草案修订历史保留且未触发真实 Git 提交。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：Day13 范围内后端模型/仓储/服务/路由、前端草案面板与烟测链路已闭环；“提交草案”仍是可审阅候选，不代表真实 Git 提交。
- 证据：
1. `GET /repositories/projects/{project_id}/commit-candidates`、`GET /repositories/change-batches/{change_batch_id}/commit-candidate`、`POST /repositories/change-batches/{change_batch_id}/commit-candidate` 已接通并可用
2. 烟测验证“首版草案 + 修订 v2”历史保留，且 `head_unchanged=true` 证明未执行真实 `git commit`
3. 前端构建通过，`CommitDraftPanel` 已在仓库总览页展示提交草案、验证摘要、关联文件与交付件

---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做最小烟测。
2. 若当前状态为“未开始”，先按计划文档完成关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在实现变化时补回归验证。
