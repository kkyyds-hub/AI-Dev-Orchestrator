# BCG-10A Approval Request Changes → Rework Live Evidence

> Document date: 2026-05-24
> Repository path: `docs/product/ai-project-director/verification-project-director-approval-request-changes-rework-20260524.md`
> Phase: BCG-10A — Approval Request Changes → Rework Evidence Chain

---

## 1. Summary

BCG-10A live evidence confirms that applying a `request_changes` approval decision produces a complete rework evidence chain: approval status changes → decision persisted → history readable → change-rework snapshot visible. The rework evidence is fully traceable through existing APIs.

The system produces visible rework evidence (approval history + change-rework snapshot) but does NOT automatically create executable rework tasks. This is a known gap.

---

## 2. Evidence IDs

| Field | Value |
|---|---|
| project_id | `423367da-966b-4c2e-b8c8-a4ff5f7f2377` |
| task_id | `db204e31-f244-4f9b-a469-abcc5e0b873f` |
| run_id | `834b38aa-3669-4121-9424-3aa4999cad2e` |
| deliverable_id | `3ae2a721-4396-453e-8d1b-529a50efb29c` |
| approval_id | `90714664-41d5-41fb-8156-59fc9a784a22` |
| decision_id | `6c1e2340-762f-4e19-a5c0-2ac6a5176c55` |

---

## 3. Status Change

| Field | Before | After |
|---|---|---|
| approval.status | `pending_approval` | `changes_requested` |
| approval.decided_at | `null` | `2026-05-24T02:38:42.016801Z` |

---

## 4. Action API

| Field | Value |
|---|---|
| API | `POST /approvals/{approval_id}/actions` |
| action | `request_changes` |
| actor_name | `老板` |
| summary | `BCG-10A requests changes for rework evidence` |
| comment | `要求根据 BCG-10A 验收补充返工说明` |
| requested_changes | `[补充 BCG-10A 返工说明章节, 在交付件中增加可验证的回归测试结果]` |
| highlighted_risks | `[当前交付件缺少端到端验收截图，可能遗漏运行时错误]` |

---

## 5. Decision Evidence

| Check | Result |
|---|---|
| decision_id persisted | Pass (`6c1e2340-762f-4e19-a5c0-2ac6a5176c55`) |
| decision.action = request_changes | Pass |
| decision.summary preserved | Pass |
| decision.comment preserved | Pass |
| decision.requested_changes preserved (2 items) | Pass |
| decision.highlighted_risks preserved (1 item) | Pass |
| decided_at non-null | Pass |

---

## 6. Approval Detail Read-Back

| Check | Result |
|---|---|
| GET /approvals/{approval_id} returns status=changes_requested | Pass |
| decided_at non-null on re-read | Pass |
| latest_decision.action = request_changes | Pass |
| requested_changes not lost | Pass |
| highlighted_risks not lost | Pass |

---

## 7. Approval History Read-Back

| Check | Result |
|---|---|
| GET /approvals/{approval_id}/history returns data | Pass |
| history.deliverable_id matches | Pass |
| history.latest_approval_status = changes_requested | Pass |
| history.negative_decision_count >= 1 | Pass (1) |
| history.rework_status = rework_required | Pass |
| history.current_version_number = 1 | Pass |
| steps: approval_requested present | Pass |
| steps: approval_decided present | Pass |
| decided step: decision_action = request_changes | Pass |
| decided step: requested_changes present | Pass |
| decided step: highlighted_risks present | Pass |
| decided step: is_rework = false (first decision, no prior negative) | Pass |
| no rework_version_submitted step (no new version created) | Pass |

---

## 8. Project Approval Inbox Read-Back

| Check | Result |
|---|---|
| GET /approvals/projects/{project_id} returns data | Pass |
| target approval found in inbox | Pass |
| approval.status = changes_requested | Pass |
| approval.deliverable_id matches | Pass |
| latest_decision.action = request_changes | Pass |

---

## 9. Change-Rework Snapshot Read-Back

| Check | Result |
|---|---|
| GET /approvals/projects/{project_id}/change-rework returns data | Pass |
| item found with approval_id match | Pass |
| item.deliverable_id matches | Pass |
| item.decision_action = request_changes | Pass |
| item.chain_source = approval_rework | Pass |
| item.closed = false | Pass |
| item.status non-empty | Pass |
| item.recommendation non-empty | Pass |
| item.reason_summary non-empty | Pass |
| item.requested_changes contains submitted items | Pass |
| item.highlighted_risks contains submitted items | Pass |
| item.steps include decision + rework stages | Pass |
| summary.approval_rework_items >= 1 | Pass |
| summary.open_items >= 1 | Pass |
| **item.approval_status** | **None (by design — see gap below)** |

### Representation Gap: approval_status = null

The change-rework item's `approval_status` field is `None` because the underlying code uses `cycle.latest_approval_status`, which reflects the *resubmitted version's* approval status. Since no higher version has been submitted yet, it is `None` by design. The rework evidence is still correctly conveyed through:
- `decision_action=request_changes` (what triggered rework)
- `status=rework_required` (current cycle state)
- `deliverable_id` and other trace fields

This is a structural representation gap in `ChangeReworkService`, not a functional failure.

---

## 10. Executable Rework Task

| Check | Result |
|---|---|
| Auto-created executable rework task | **NOT FOUND** |
| Rework visibility in snapshot | Yes |
| Rework visibility in history | Yes |

**Gap: `visible_rework_no_executable_task`**

The system correctly produces:
- Approval history showing `rework_required`
- Change-rework snapshot showing the rework cycle

But does NOT automatically create an executable task for the rework. This is expected for the current implementation stage.

---

## 11. APIs Used

| Method | Path | Purpose |
|---|---|---|
| GET | `/approvals/{approval_id}` | Read initial state + re-read after action |
| POST | `/approvals/{approval_id}/actions` | Apply request_changes decision |
| GET | `/deliverables/tasks/{task_id}` | Verify deliverable traceability |
| GET | `/approvals/{approval_id}/history` | Read approval redo history |
| GET | `/approvals/projects/{project_id}` | Read project approval inbox |
| GET | `/approvals/projects/{project_id}/change-rework` | Read project rework snapshot |
| GET | `/tasks` | Check for auto-created rework tasks |

---

## 12. Live Evidence Command

```bash
cd runtime/orchestrator
.\.venv\Scripts\python.exe scripts\bcg10a_approval_request_changes_rework_live.py
```

**Result: 61 passed, 0 failed.**

First run: applied request_changes action (status: pending_approval → changes_requested).
Second run (idempotent): skipped action, re-verified all read paths.

---

## 13. Regression Test Command

```bash
cd runtime/orchestrator
.\.venv\Scripts\python.exe -m pytest tests/test_project_director_sessions.py tests/test_project_director_plan_versions.py tests/test_project_director_confirmations.py tests/test_project_director_task_creation.py tests/test_project_director_worker_run_evidence.py tests/test_project_director_run_evidence_replay.py tests/test_run_ai_summaries.py -q
```

**Result: 132 passed, 3 warnings in 32.57s.**

---

## 14. Uncovered Scope

| Item | Status | Reason |
|---|---|---|
| Executable rework task creation | Missing | System has rework visibility but no auto task creation |
| Rework task → Worker execution | Not covered | No executable rework task exists |
| BCG-11 (repository binding) | Not covered | Out of BCG-10 scope |
| Release Gate (BCG-18) | Not covered | Out of BCG-10 scope |
| AI Project Director total closure | Not covered | BCG-10A is P1 evidence; total closure requires BCG-11+ |

---

## 15. Gate Conclusion

**BCG-10A Approval Rework Evidence: Pass (61/61)**

- Approval request_changes decision applied and persisted via real API.
- Approval status correctly transitions: pending_approval → changes_requested.
- Decision with requested_changes/highlighted_risks fully preserved.
- Approval history shows rework_required with complete step trace.
- Change-rework snapshot includes the rework cycle with full data.
- **Gap: Executable rework task NOT auto-created.** Rework evidence is visible (history + snapshot) but not actionable (no rework task in queue).
- BCG-10 overall: **Partial** — approval rework evidence Pass; executable rework task creation Missing.

**AI Project Director total closure: remains Partial.** Do not write total closure Pass.
