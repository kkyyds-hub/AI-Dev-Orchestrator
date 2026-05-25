# BCG-10-R3 Approval Request Changes → Executable Rework Task Runtime Evidence

> Document date: 2026-05-25
> Repository path: `docs/product/ai-project-director/verification-project-director-approval-request-changes-rework-20260525.md`
> Phase: BCG-10-R3 — Approval Request Changes / Reject → Executable Rework Task Runtime Evidence

---

## 1. Summary

BCG-10-R3 live evidence confirms that when the boss applies a negative approval decision (request_changes or reject) through `POST /approvals/{id}/actions`, the system automatically creates one executable pending rework task. The rework task is readable via `GET /tasks`, traceable to the approval/decision/deliverable/project, and consumable by the downstream worker queue.

Previous BCG-10A (2026-05-24) proved rework visibility (history + change-rework snapshot) but the executable rework task was missing. BCG-10-R3 closes that gap.

---

## 2. Evidence Scenarios

### 2.1 request_changes → Executable Rework Task

| Field | Value |
|---|---|
| project_id | `971314f1-39e5-4dff-836d-e147e46e4719` |
| approval_id | `c6bbfee0-047a-47bb-ab15-8d26ce8bf099` |
| decision_id | `025f5425-b993-4ba4-b0a2-e63e2f12dcea` |
| rework_task_id | `029d165c-a3b3-40ee-994f-5b0df19f7674` |
| source_draft_id | `arw:c6bbfee0047a47bb:025f5425b9934ba4` |

Assertions (all Pass):
- `POST /approvals/{id}/actions` action=request_changes returns 200, status=changes_requested
- `GET /approvals/{id}` re-read confirms status=changes_requested, decided_at non-null, latest_decision.action=request_changes, decisions[-1].requested_changes has 2 items
- `GET /approvals/{id}/history` returns rework_status=rework_required, negative_decision_count>=1, steps include approval_requested + approval_decided
- `GET /approvals/projects/{id}/change-rework` shows approval_rework_items>=1, matching approval found
- `GET /tasks` returns 1 pending rework task with source_draft_id starting with "arw:", input_summary contains approval_id + "request_changes" + requested_changes item
- acceptance_criteria >= 2 items, references approval/decision/review
- owner_role_code = engineer
- priority = high
- task_created event published exactly once

### 2.2 reject → Executable Rework Task

| Field | Value |
|---|---|
| project_id | `5052e9db-b188-4e5a-8251-aed6289c69d6` |
| approval_id | `e853fd59-1b94-4078-8233-5123240b9ea4` |
| decision_id | `a019ca33-4e85-4bce-a6e4-c71e51f05052` |
| rework_task_id | `fa4efa4c-5c95-4918-978c-cd891c62cb08` |
| source_draft_id | `arw:e853fd591b944078:a019ca334e854bce` |

Assertions (all Pass):
- `POST /approvals/{id}/actions` action=reject returns 200, status=rejected
- rework task found via GET /tasks: status=pending, priority=high, risk_level=high, owner_role_code=engineer
- source_draft_id starts with "arw:"
- input_summary contains approval_id + "reject"

### 2.3 approve → No Rework Task

| Field | Value |
|---|---|
| project_id | `61e2de27-c670-46a2-a8b4-4e00feb29b1a` |
| approval_id | `193d848a-a4de-49e3-97f0-bb98d8271809` |

Assertions (all Pass):
- `POST /approvals/{id}/actions` action=approve returns 200, status=approved
- No arw: rework task found via GET /tasks for this approval

### 2.4 Idempotency / Closed Approval

| Field | Value |
|---|---|
| project_id | `965ea536-044f-4fd9-a92b-6e909745dbc3` |
| approval_id | `5a4f76ff-e687-46a7-b50a-bae2191de4d1` |
| rework_task_id | `41b489be-16fa-4213-95f4-ed11dfac8876` |

Assertions (all Pass):
- First reject → 200, 1 rework task created
- Second reject on closed approval → 422
- Original rework task still exists, unchanged
- No new rework task created

### 2.5 Transaction Rollback

| Field | Value |
|---|---|
| project_id | `a2720d15-f493-4bab-bafe-9ab0e874395f` |
| approval_id | `4b623f74-354a-49b9-864f-5a1f9b507d5f` |

Assertions (all Pass):
- request_changes with simulated task creation failure → 422
- Approval status still pending_approval
- decided_at = null, decisions = [], latest_decision = null
- No rework task created

### 2.6 Event Boundary

| Field | Value |
|---|---|
| project_id | `ff4a9580-2ac6-46ab-89cd-36de47f157eb` |
| approval_id | `ecf55e7b-f898-41f9-bb4f-c82b780504fb` |

Assertions (all Pass):
- request_changes with simulated task creation failure → 422
- Zero task_created events published (rollback prevents event publishing)

---

## 3. Live Evidence Command

```bash
cd runtime/orchestrator
python scripts/bcg10_rework_task_live.py
```

**Result: 89 passed, 0 failed.**

---

## 4. Unit Test Command

```bash
cd runtime/orchestrator
python -m pytest tests/test_approval_rework_task_creation.py -q
```

**Result: 6 passed.**

---

## 5. Smoke Regression

```bash
cd runtime/orchestrator
python scripts/v3c_day10_approval_gate_smoke.py
python scripts/v3c_day12_approval_rework_retrospective_smoke.py
```

**Both passed.**

---

## 6. APIs Exercised

| Method | Path | Purpose |
|---|---|---|
| POST | `/projects` | Create project |
| POST | `/tasks` | Create source task |
| POST | `/deliverables` | Create deliverable |
| POST | `/approvals` | Create approval request |
| POST | `/approvals/{id}/actions` | Apply request_changes / reject / approve |
| GET | `/approvals/{id}` | Read approval detail + decisions |
| GET | `/approvals/{id}/history` | Read approval redo history |
| GET | `/approvals/projects/{id}/change-rework` | Read change-rework snapshot |
| GET | `/tasks` | Read all tasks, find rework task |

---

## 7. Business Code Path Verified

- `approval_service.apply_approval_decision` — transaction orchestration
- `approval_service._ensure_rework_task_for_negative_decision` — rework task creation
- `approval_service._build_rework_task_source_id` — idempotency key (`arw:{approval_hex16}:{decision_hex16}`)
- `approval_repository.add_decision_no_commit` — flush without commit
- `task_service.create_task(commit=False)` — add_no_commit for single transaction
- `task_repository.publish_created` — event publishing after commit
- `approval_repository.session.commit()` / `rollback()` — transaction boundary

---

## 8. Boundaries Enforced

- No apply-local triggered
- No product git-commit triggered
- No git push / PR / merge
- No worker execution (rework task stays pending)
- No frontend changes
- No business code changes
- BCG-17 remains Deferred

---

## 9. Gate Conclusion

**BCG-10 Approval Rework Task Creation: Runtime Evidence Pass (89/89)**

- request_changes → executable pending rework task: Pass
- reject → executable pending rework task with high risk: Pass
- approve → no rework task: Pass
- closed approval idempotency (422, no duplicate): Pass
- transaction rollback (approval preserved, no ghost data): Pass
- event boundary (rollback publishes zero, normal path publishes exactly once): Pass

**BCG-10 overall: Runtime Evidence Pass** — both rework visibility (BCG-10A) and executable rework task creation (BCG-10-R3) are now proven.

**AI Project Director total closure: remains Partial.** Do not write total closure Pass.
