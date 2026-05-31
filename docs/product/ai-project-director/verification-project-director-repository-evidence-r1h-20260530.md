# AI Project Director Repository Evidence Chain R1-H Audit

> 文档类型：Repository evidence chain audit + live HTTP + smoke + tests
> 审计日期：2026-05-30（Phase 1 Evidence Partial）/ 2026-05-31（Phase 2 Runtime Pass）
> 审计人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commit：`6b1095b`（Codex: draft-chain-readback API + git_write_state_tracker）
> 前置阶段：R1-G Runtime Pass (CL-11)
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`
> 对应验收项：CL-12（代码相关任务是否有仓库证据链）
> Phase 1 结论：Evidence Partial（只读仓库链 live HTTP 通过；draft chain 后端完备但端到端需 deliverables 前置）
> **Phase 2 结论：Runtime Pass（draft-chain-readback 端到端 smoke + tests 全通过）**

---

## 1. 审计范围

重新验证 CL-12：Codex 已完成 `GET /repositories/projects/{project_id}/draft-chain-readback` 聚合 API + `git_write_state_tracker` 安全边界。

### 1.1 Phase 2 新增文件

- `runtime/orchestrator/app/api/routes/repositories.py` (+draft-chain-readback endpoint)
- `runtime/orchestrator/app/services/git_write_state_tracker.py` (new, git-write state tracker)
- `runtime/orchestrator/tests/test_repository_draft_chain_readback.py` (new, 1 test)
- `runtime/orchestrator/tests/test_apply_local_git_commit_guard.py` (6 tests)
- `runtime/orchestrator/scripts/v4d_day15_repository_flow_smoke.py` (end-to-end smoke)

---

## 2. Draft Chain Readback API

`GET /repositories/projects/{project_id}/draft-chain-readback` — 只读聚合快照：

```json
{
  "project_id": "...",
  "review_only": true,
  "safe_runtime_path": true,
  "change_plan_count": 7,
  "change_batch_count": 1,
  "selected_change_batch_id": "...",
  "selected_change_batch_title": "...",
  "preflight_status": "ready_for_execution",
  "commit_candidate_present": true,
  "commit_candidate_status": "draft",
  "commit_candidate_review_only": true,
  "commit_candidate_evidence_package_key": "...",
  "commit_candidate_related_file_count": 3,
  "release_status": "approved",
  "release_qualification_established": true,
  "day15_flow": { ... },
  "day15_status": "ready_for_review",
  "apply_local_triggered": false,
  "git_commit_triggered": false,
  "git_write_actions_triggered": false,
  "forbidden_actions": ["apply-local", "git-commit", "push", "planning/apply"]
}
```

### 2.1 Git Write State Tracker

`git_write_state_tracker.py` 在每次 apply-local / git-commit 调用时记录状态，draft-chain-readback 读取该 tracker 确认是否触发过写操作。

---

## 3. Smoke Script Results

```
v4d_day15_repository_flow_smoke.py

project_id: 291519c3-c1fe-4cb1-9102-7a87b6f84929
change_batch_id: 1e577d1b-0715-4cd2-8cad-a8d7aee7d4ec

draft_chain_readback:
  review_only: true ✓
  safe_runtime_path: true ✓
  preflight_status: ready_for_execution ✓
  commit_candidate_present: true ✓
  commit_candidate_review_only: true ✓
  release_status: approved ✓
  apply_local_triggered: false ✓
  git_commit_triggered: false ✓
  git_write_actions_triggered: false ✓

repository_day15_status: ready_for_review
project_day15_status: ready_for_review
approvals_day15_selected_status: approved
release_qualification_established: true ✓
head_unchanged: true ✓
git_write_actions_triggered: false ✓
```

---

## 4. Tests

```bash
python -m pytest tests/test_repository_draft_chain_readback.py -q
→ 1 passed in 2.03s

python -m pytest tests/test_apply_local_git_commit_guard.py -q
→ 6 passed in 4.02s

python -m pytest tests/test_project_director_worker_run_evidence.py tests/test_project_director_run_evidence_replay.py -q
→ 2 passed in 2.52s

Total: 9 passed
```

---

## 5. Draft vs Real Commit Boundary (Re-confirmed)

| Component | Nature | Real Git Commit? |
|---|---|---|
| ChangePlan | Structured draft | No |
| ChangeBatch | Multi-plan preparation | No |
| Preflight | Command classification (no execution) | No |
| CommitCandidate | **Review-only draft** | No |
| ReleaseGate | Checklist-based judgement | No |
| DraftChainReadback | **Read-only aggregation** | No |
| apply-local (BCL-03) | **Guarded write** | Yes (requires full chain) |
| git-commit (BCL-03) | **Guarded write** | Yes (requires prior apply-local) |

The draft-chain-readback explicitly confirms: `review_only=true`, `apply_local_triggered=false`, `git_commit_triggered=false`, `git_write_actions_triggered=false`.

---

## 6. CL-12 Status

**Runtime Pass** (upgraded from Phase 1 Evidence Partial)

- Full deliverable → change plan → change batch → preflight → commit candidate → release gate chain verified via smoke script
- GET /repositories/projects/{pid}/draft-chain-readback confirms review_only=true, safe_runtime_path=true
- All git-write flags false: apply_local_triggered=false, git_commit_triggered=false, git_write_actions_triggered=false
- 9 tests pass (1 draft chain + 6 guard + 2 worker evidence)
- No apply-local, no git-commit, no real repository write

---

## 7. Gate Conclusion

### 7.1 R1-H Gate

**Runtime Pass** (upgraded from Phase 1 Evidence Partial)

### 7.2 AI Project Director Total Closure

**仍为 Partial**

CL-16 Evidence Partial 尚未消除。
