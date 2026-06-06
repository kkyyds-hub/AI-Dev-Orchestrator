# BCG-18 Release Gate Runtime Evidence

> 文档日期: 2026-05-25
> 模型: DeepSeek
> 证据类型: Live Evidence Script
> 脚本: runtime/orchestrator/scripts/bcg18_release_gate_live.py

---

## 1. Evidence Summary

| Field | Value |
|---|---|
| Model | DeepSeek |
| Script | `runtime/orchestrator/scripts/bcg18_release_gate_live.py` |
| Live Result | 137 passed, 0 failed, 0 gaps |
| Isolated workspace base | `E:\bcg18-workspaces\` (outside main repo) |

---

## 2. APIs Used

| Method | Path | Purpose |
|---|---|---|
| POST | /projects | Create isolated projects |
| PUT | /repositories/projects/{id} | Bind workspace |
| POST | /repositories/projects/{id}/snapshot/refresh | Snapshot |
| POST | /project-director/sessions | Task creation chain |
| POST | /deliverables | Create deliverable |
| POST | /planning/projects/{id}/change-plans | Change plans |
| POST | /repositories/projects/{id}/change-batches | Change batch |
| POST | /repositories/change-batches/{id}/preflight | Preflight |
| POST | /runs/verification | Verification run |
| POST | /repositories/change-batches/{id}/commit-candidate | Commit candidate |
| GET | /approvals/repository-release-gate/{id} | Gate detail |
| POST | /approvals/repository-release-gate/{id}/actions | Gate decision |
| GET | /approvals/projects/{id}/repository-release-gate | Gate inbox |
| GET | /approvals/projects/{id}/day15-release-judgement | Day15 judgement |

---

## 3. Scenarios

### 3.1 Blocked Gate → Approve Rejected (409)

- No commit candidate → `commit_draft` checklist item missing → gate blocked
- POST approve → **409** "Release gate is blocked by missing required checklist items"
- Inbox shows `blocked_batches=1`

### 3.2 Approve → release_qualification_established=true

- Full chain (preflight ready, verification passed, commit candidate exists)
- Gate status: `pending_approval`, blocked=false
- POST approve → `approved`, `release_qualification_established=true`, decision_count=1
- Read-back consistent
- Inbox: `approved_batches=1`
- Day15 judgement: `release_qualification_established=true`, `git_write_actions_triggered=false`, `selected_decision_count=1`

### 3.3 Reject → release_qualification_established=false

- Full chain, gate pending_approval
- POST reject → `rejected`, `release_qualification_established=false`, decision persisted
- Read-back consistent
- Inbox: `rejected_batches=1`
- Day15 judgement: `release_qualification_established=false`, `git_write_actions_triggered=false`

### 3.4 Changes Requested → release_qualification_established=false

- Full chain, gate pending_approval
- POST request_changes → `changes_requested`, `release_qualification_established=false`, decision persisted
- Read-back consistent
- Inbox: `changes_requested_batches=1`
- Day15 judgement: `release_qualification_established=false`, `git_write_actions_triggered=false`

---

## 4. Boundaries

- `git_write_actions_triggered=false` in all Day15 judgements
- No apply-local called
- No git-commit called
- No git-push called
- No PR created
- No remote write
- All repos under `E:\bcg18-workspaces\` (outside main repo)
- BCG-17 remote push / PR / merge remains Deferred

---

## 5. Runtime Evidence Gap Assessment

None.

---

## 6. Uncovered Scope

- Multi-batch inbox aggregation (multiple batches for same project)
- Decision history across multiple decisions on same batch
- Non-existent batch → 404
- Duplicate action protection (re-approve after approve)

---

## 7. Gate Conclusion

```text
BCG-18 Runtime Evidence: Pass
  - Blocked gate → approve 409: Pass
  - Approve → rqe=true: Pass
  - Reject → rqe=false: Pass
  - Changes requested → rqe=false: Pass
  - Day15 judgement read-back: Pass
  - git_write_actions_triggered=false: Pass
  - No apply-local / git-commit / push: Pass

AI Project Director total closure remains Partial. Do not mark total closure Pass.
```

---

## 8. Live Evidence Command

```bash
cd runtime/orchestrator
python scripts/bcg18_release_gate_live.py
```

Result: **137 passed, 0 failed, 0 Runtime Evidence Gaps**
