# BCG-14A Preflight + Manual Confirmation Live Evidence

> 文档日期: 2026-05-24
> 模型: DeepSeek
> 证据类型: Live Evidence Script
> 脚本: runtime/orchestrator/scripts/bcg14a_preflight_manual_confirmation_live.py

---

## 1. Evidence Summary

| Field | Value |
|---|---|
| project_id | 423367da-966b-4c2e-b8c8-a4ff5f7f2377 |
| workspace_id | e1e32ddb-e858-4224-b301-5362f97c1864 |
| change_batch_id (approved) | 2d07dde6-0216-40ef-ae2b-b4959db58d33 |
| change_batch_id (reject) | None (active batch conflict) |

---

## 2. APIs Used

| Method | Path | Purpose |
|---|---|---|
| GET | /repositories/projects/{project_id} | Workspace verification |
| GET | /repositories/projects/{project_id}/snapshot | Snapshot verification |
| POST | /repositories/change-batches/{id}/preflight | Run preflight (low-risk and high-risk) |
| GET | /repositories/change-batches/{id} | Read-back detail |
| POST | /approvals/repository-preflight/{id}/actions | Manual approve |
| GET | /approvals/repository-preflight/{id} | Approval-side detail |
| GET | /approvals/projects/{project_id}/repository-preflight | Inbox |
| GET | /repositories/projects/{project_id}/day15-flow | Day15 aggregation |
| GET | /repositories/projects/{project_id}/change-batches | List batches |
| GET | /planning/projects/{project_id}/change-plans | List plans |

---

## 3. Preflight Results

### 3.1 Low-risk Preflight

- **API**: `POST /repositories/change-batches/{id}/preflight` with empty candidate_commands
- **Status**: `blocked_requires_confirmation` (correct — batch scope triggers wide_change with 5 target files across 4 directories)
- **Findings**: wide_change_scope (HIGH severity)
- **Note**: This is correct preflight behavior. A batch with 5 files in 4 directories exceeds the HIGH threshold (4 directories). The low-risk path works correctly for smaller batches; this batch's scope naturally requires manual confirmation.

### 3.2 High-risk Preflight

- **API**: `POST /repositories/change-batches/{id}/preflight` with dangerous candidate_commands
- **Commands**: `git push origin main`, `rm -rf /tmp/evidence`, `git reset --hard HEAD~1`
- **Status**: `blocked_requires_confirmation`
- **blocked**: true
- **ready_for_execution**: false
- **manual_confirmation_required**: true
- **manual_confirmation_status**: pending
- **Findings**: 4 findings — `wide_change_scope` (HIGH), `git_push` (HIGH), `shell_force_delete` (CRITICAL), `git_reset_hard` (CRITICAL)
- **inspected_commands**: 4 (3 dangerous + 1 existing verification command)
- **requested_at / evaluated_at**: non-null
- **Read-back**: GET detail matches; GET approvals detail matches

---

## 4. Manual Confirmation Results

### 4.1 Manual Approve

- **API**: `POST /approvals/repository-preflight/{id}/actions` with `action=approve`
- **Pre-approve status**: `blocked_requires_confirmation`
- **Post-approve status**: `manual_confirmed`
- **blocked**: false
- **ready_for_execution**: true
- **manual_confirmation_status**: approved
- **decided_at**: non-null
- **decision_history**: 1 decision (action=approve, actor_name=老板, summary/comment/highlighted_risks all present)
- **Read-back**: GET detail and GET approvals detail both confirm `manual_confirmed`

### 4.2 Manual Reject

- **Status**: **Skipped**
- **Reason**: Active batch conflict (409). The project has one active (preparing) batch. After approve, the batch remains active. Creating a second batch for the reject scenario returns 409.
- **Gap**: Active-batch-per-project constraint prevents testing both approve and reject on a single project. A fresh project without active batches would be needed to test reject. The MANUAL_REJECTED state and decision flow are structurally identical to approve (same service path, same state machine), only the final state and blocked flag differ.

---

## 5. Illegal-Action Protection

| Test | Expected | Actual | Result |
|---|---|---|---|
| Re-approve already-approved batch | 422 | 422 | Pass |
| Reject already-approved batch | 422 | 422 | Pass |
| Action on non-existent batch | 404 | 404 | Pass |

---

## 6. Read-back Aggregations

### 6.1 Approval Repository-Preflight Inbox

- API: `GET /approvals/projects/{project_id}/repository-preflight`
- total_batches: 1
- pending_confirmations: 0
- ready_batches: 1 (approved batch counts as ready)
- rejected_batches: 0
- Approved batch correctly shows `manual_confirmed` status

### 6.2 Day15 Flow

- API: `GET /repositories/projects/{project_id}/day15-flow`
- `risk_preflight` step status: **completed**
- Summary confirms preflight was run and findings recorded

### 6.3 Approvals Detail

- API: `GET /approvals/repository-preflight/{id}`
- Tasks: 2
- Target files: 5
- Timeline: 5 entries
- Preflight status: manual_confirmed

---

## 7. Runtime Evidence Gap Assessment

### Gaps Found

1. **Manual reject not tested** — Active batch conflict (409) prevents creating a second batch. The API allows only one active (preparing) batch per project. A separate project/batch would be needed.

### Not Gaps

- Preflight correctly classifies risks (empty commands: wide_change; dangerous commands: wide_change + dangerous_command findings).
- Preflight only classifies, never executes commands.
- Manual approve transitions correctly: blocked → ready_for_execution, blocked=false.
- Decision history persists and is readable.
- Inbox, detail, and day15-flow all correctly aggregate preflight state.
- Illegal re-approve/reject correctly return 422; non-existent batch returns 404.

---

## 8. Uncovered Scope

- Low-risk preflight on a genuinely small batch (<5 target files, <4 directories) — requires a fresh project without active batches.
- Manual reject end-to-end — requires a second batch or fresh project.
- Preflight on a batch with NOT_STARTED → manual action without preflight (needs fresh batch).
- Frontend integration.

---

## 9. Gate Conclusion

```text
BCG-14 Runtime Evidence: Partial
  - Low-risk preflight (wide_change correctly detected): Pass
  - High-risk preflight (dangerous commands detected): Pass
  - Manual approve: Pass
  - Manual reject: Skipped (active batch constraint — documented gap)
  - Illegal-action protection: Pass
  - Inbox / detail / day15-flow read-back: Pass

BCG-14 overall: Partial (preflight/approve/readback Pass / reject not tested due to active-batch constraint)

AI Project Director total closure remains Partial. Do not mark total closure Pass.
```

---

## 10. Live Evidence Command

```bash
cd runtime/orchestrator
python scripts/bcg14a_preflight_manual_confirmation_live.py
```

Result: **74 passed, 0 failed, 1 Runtime Evidence Gap (manual reject skipped)**

---

## 12. R1 Closeout (2026-05-24)

### R1 Script

`runtime/orchestrator/scripts/bcg14a_r1_preflight_reject_closeout_live.py`

### R1 Strategy

Created a fresh isolated project (`BCG-14A-R1 Preflight Evidence`) to avoid
active-batch conflict with BCG-13A.  Used `POST /projects`,
`POST /project-director/sessions` (goal_text → clarify → confirm →
plan version → create-tasks), `POST /deliverables` (create stage_artifact),
`POST /planning/projects/{id}/change-plans`, and
`POST /repositories/projects/{id}/change-batches` to set up a small-scope
batch (2 target files in 2 directories, well under wide_change thresholds).

### R1 Results

| Scenario | Pre-R1 Status | R1 Status |
|---|---|---|
| NOT_STARTED manual action → 422 | Missing | **Pass** |
| Low-risk ready_for_execution | Partial (wide_change blocked) | **Pass** (0 findings) |
| Manual reject | Skipped (active batch conflict) | **Pass** (manual_rejected, 1 decision) |
| Inbox read-back (rejected) | Not tested | **Pass** |
| day15-flow risk_preflight = blocked | Not tested | **Pass** |

### R1 Evidence IDs

| ID | Value |
|---|---|
| r1_project_id | 7fb17d15-c6d2-4919-95f0-4d39607a11ea |
| r1_batch_id | 59d3c8a5-9e24-46b7-af15-4dd164d91000 |

### R1 Live Evidence Command

```bash
cd runtime/orchestrator
python scripts/bcg14a_r1_preflight_reject_closeout_live.py
```

Result: **59 passed, 0 failed, 0 Runtime Evidence Gaps**

### R1 Gate Conclusion

```text
BCG-14A-R1 closeout: Pass
BCG-14 Runtime Evidence: Pass (all four preflight states + illegal-action protection + read-back verified)
AI Project Director total closure: remains Partial. Do not mark total closure Pass.
```
