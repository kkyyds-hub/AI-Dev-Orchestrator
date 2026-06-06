# BCG-09A Provider Run Deliverable & Approval Live Evidence

> Document date: 2026-05-24
> Repository path: `docs/product/ai-project-director/verification-project-director-provider-run-deliverable-approval-20260524.md`
> Phase: BCG-09A — Provider Run → Auto Deliverable → Auto Approval Evidence

---

## 1. Summary

BCG-09A live evidence confirms that after a real `provider_reported` Worker run succeeds, the system automatically generates a deliverable snapshot AND automatically creates a pending approval request. Both are readable through existing API paths with full traceability to task_id, run_id, and project_id.

**Reused BCG-05B run: YES**

The BCG-05B provider-reported run (run_id `834b38aa-3669-4121-9424-3aa4999cad2e`) already had an auto-generated deliverable and auto-generated approval from the original Worker execution. No forging, no manual creation was needed.

---

## 2. Evidence IDs

| Field | Value |
|---|---|
| project_id | `423367da-966b-4c2e-b8c8-a4ff5f7f2377` |
| task_id | `db204e31-f244-4f9b-a469-abcc5e0b873f` |
| run_id | `834b38aa-3669-4121-9424-3aa4999cad2e` |
| provider_key | `deepseek` |
| model_name | `deepseek-v4-pro` |
| token_accounting_mode | `provider_reported` |
| run_provider_receipt_id | `3d8bf6e7-fdfd-43db-bd9a-3abee685521d` |
| deliverable_id | `3ae2a721-4396-453e-8d1b-529a50efb29c` |
| deliverable_version_number | `1` |
| version_id (latest) | From v1 deliverable record |
| source_task_id | `db204e31-f244-4f9b-a469-abcc5e0b873f` |
| source_run_id | `834b38aa-3669-4121-9424-3aa4999cad2e` |
| approval_id | `90714664-41d5-41fb-8156-59fc9a784a22` |
| approval_status | `pending_approval` |
| approval_deliverable_version_number | `1` |
| request_note | `[自动生成] Worker 成功运行后自动创建的交付件审批。\nTask ID: db204e31-f244-4f9b-a469-abcc5e0b873f\nRun ID: 834b38aa-3669-4121-9424-3aa4999cad2e` |

---

## 3. Run Verification

| Check | Result |
|---|---|
| run exists | Pass |
| run.task_id = db204e31-f244-4f9b-a469-abcc5e0b873f | Pass (verified via task-scoped API) |
| run.provider_key = deepseek | Pass |
| run.model_name = deepseek-v4-pro | Pass |
| run.token_accounting_mode = provider_reported | Pass |
| run.provider_receipt_id = 3d8bf6e7-fdfd-43db-bd9a-3abee685521d | Pass |
| run.status = succeeded | Pass |
| run.quality_gate_passed = true | Pass |
| fallback_applied != true | Pass |
| execution_mode != provider_mock | Pass |

---

## 4. Deliverable Verification

| Check | Result |
|---|---|
| deliverable found by `find_by_source_run_id(TARGET_RUN_ID)` | Pass |
| deliverable.project_id = run.task.project_id | Pass |
| latest_version.source_task_id = TARGET_TASK_ID | Pass |
| latest_version.source_run_id = TARGET_RUN_ID | Pass |
| title non-empty | Pass |
| content non-empty | Pass |
| summary non-empty | Pass |
| content contains Task ID | Pass |
| content contains Run ID | Pass |
| content contains execution mode evidence | Pass |
| content contains run status evidence | Pass |
| content contains verification evidence | Pass |
| content contains Token/Cost evidence | Pass |
| GET /deliverables/projects/{project_id} returns deliverable | Pass |
| GET /deliverables/tasks/{task_id} returns deliverable | Pass |

---

## 5. Approval Verification

| Check | Result |
|---|---|
| approval found for deliverable | Pass |
| approval.project_id = project_id | Pass |
| approval.deliverable_id = deliverable_id | Pass |
| approval.deliverable_version_number present | Pass |
| request_note contains [自动生成] marker | Pass |
| request_note contains Task ID | Pass |
| request_note contains Run ID | Pass |
| GET /approvals/projects/{project_id} returns approval | Pass |
| GET /approvals/{approval_id} detail returns approval with correct fields | Pass |
| GET /approvals/{approval_id}/history returns approval history with steps | Pass |
| auto-created, not manually forged | Pass |

---

## 6. APIs Used

| Method | Path | Purpose |
|---|---|---|
| GET | `/tasks/{task_id}/runs` | Read run detail |
| GET | `/runs/{run_id}/logs?limit=200` | Read run logs for fallback/mock check |
| GET | `/deliverables/projects/{project_id}` | Read project deliverables |
| GET | `/deliverables/tasks/{task_id}` | Read task-associated deliverables |
| GET | `/approvals/projects/{project_id}` | Read project approvals |
| GET | `/approvals/{approval_id}` | Read approval detail |
| GET | `/approvals/{approval_id}/history` | Read approval history with steps |

---

## 7. Live Evidence JSON Summary

```json
{
  "phase": "BCG-09A Provider Run Deliverable Approval Evidence",
  "reused_bcg05b_run": true,
  "auto_created": true,
  "not_forged": true,
  "target_run": {
    "run_id": "834b38aa-3669-4121-9424-3aa4999cad2e",
    "task_id": "db204e31-f244-4f9b-a469-abcc5e0b873f",
    "project_id": "423367da-966b-4c2e-b8c8-a4ff5f7f2377",
    "provider_key": "deepseek",
    "model_name": "deepseek-v4-pro",
    "token_accounting_mode": "provider_reported",
    "run_provider_receipt_id": "3d8bf6e7-fdfd-43db-bd9a-3abee685521d",
    "fallback_applied": false,
    "actual_execution_mode": "provider_openai"
  },
  "deliverable": {
    "deliverable_id": "3ae2a721-4396-453e-8d1b-529a50efb29c",
    "project_id": "423367da-966b-4c2e-b8c8-a4ff5f7f2377",
    "current_version_number": 1,
    "source_task_id": "db204e31-f244-4f9b-a469-abcc5e0b873f",
    "source_run_id": "834b38aa-3669-4121-9424-3aa4999cad2e"
  },
  "approval": {
    "approval_id": "90714664-41d5-41fb-8156-59fc9a784a22",
    "status": "pending_approval",
    "deliverable_version_number": 1,
    "request_note_has_auto_generation_marker": true,
    "request_note_has_task_id": true,
    "request_note_has_run_id": true
  },
  "api_read_back": {
    "deliverable_via_project_api": true,
    "deliverable_via_task_api": true,
    "approval_via_project_api": true,
    "approval_detail_read_back": true,
    "approval_history_read_back": true
  },
  "result": {
    "passed": 46,
    "failed": 0
  }
}
```

---

## 8. Is This a Real Provider Run?

**Yes.** The BCG-05B run (834b38aa-3669-4121-9424-3aa4999cad2e) was a real provider run:

- `execution_mode` = `provider_openai`
- `token_accounting_mode` = `provider_reported`
- `provider_key` = `deepseek`
- `model_name` = `deepseek-v4-pro`
- `provider_receipt_id` = `3d8bf6e7-fdfd-43db-bd9a-3abee685521d`
- `fallback_applied` = `false`
- No mock/simulate/provider_mock substitution

---

## 9. Auto-Created, Not Manually Forged

- The deliverable was created by `_auto_create_run_deliverable()` in the Worker pipeline (`task_worker.py` lines 798-813).
- The approval was created by `_auto_create_run_approval()` immediately after the deliverable.
- Both were created during the original BCG-05B Worker execution.
- No manual `POST /deliverables` or `POST /approvals` was used to forge them.
- The request_note contains `[自动生成]` confirming auto-generation semantics.

---

## 10. Uncovered Scope

| Item | Status | Reason |
|---|---|---|
| BCG-10 (approval rework → task queue) | Not covered | Out of BCG-09A scope |
| BCG-11+ (repository binding, snapshots) | Not covered | Out of BCG-09A scope |
| Release Gate (BCG-18) | Not covered | Out of BCG-09A scope |
| Governance (BCG-19~22) | Not covered | Out of BCG-09A scope |
| Cost telemetry (BCG-23) | Not covered | Out of BCG-09A scope |
| Total AI Project Director closure | Not covered | BCG-09 is P1 evidence; total closure requires BCG-10~30 |
| Frontend verification | Not covered | No frontend changes in this phase |
| End-to-end with new run | Not needed | BCG-05B run already had deliverable + approval |

---

## 11. Gate Conclusion

**BCG-09A Runtime Evidence: Pass**

- 46/46 live evidence checks passed.
- Auto-generated deliverable confirmed via repository read path.
- Auto-generated approval confirmed via repository read path.
- Both deliverable and approval readable through existing project/task-scoped APIs.
- Full traceability: project_id → task_id → run_id → deliverable_id → approval_id.
- Real provider_reported run; no mock/simulate/forged evidence.
- BCG-09 can now be written as Runtime Evidence Pass for provider-run deliverable/approval evidence.

**AI Project Director total closure: remains Partial.** Do not write total closure Pass.

---

## 12. Live Evidence Command

```bash
cd runtime/orchestrator
.\\.venv\\Scripts\\python.exe scripts\\bcg09a_provider_run_deliverable_approval_live.py
```

Result: 46 passed, 0 failed. Reused BCG-05B run: True.

## 13. Regression Test Command

```bash
cd runtime/orchestrator
.\\.venv\\Scripts\\python.exe -m pytest tests/test_project_director_sessions.py tests/test_project_director_plan_versions.py tests/test_project_director_confirmations.py tests/test_project_director_task_creation.py tests/test_project_director_worker_run_evidence.py tests/test_project_director_run_evidence_replay.py tests/test_run_ai_summaries.py -q
```

Result: 132 passed, 3 warnings in 40.57s.
