# Programmer No-Write Loop Ledger - 2026-06-23

> This ledger is the single backfill ledger for the programmer no-write loop.
> It records P16 and P17 evidence in one place to avoid one-ledger-per-stage documentation sprawl.
>
> 本文件是 programmer no-write loop 的统一总账，用于回填 P16/P17/P18 后续证据，避免每个小阶段新增单独 ledger。

---

## P16 Programmer No-Write Plan

### Gate

- P16-Codex programmer no-write planning implementation: Pass with note
- P16-Mimocode contract tests: Pass
- P16-Mimocode API tests: Pass after R1
- P16-Mimocode smoke tests: Pass
- P16-R1 source binding fix: Pass
- P16 overall: Pass with note
- AI Project Director total loop: Partial

### Implemented Surface

- Endpoint: `POST /project-director/sessions/{session_id}/programmer-no-write-plan`
- Domain: `runtime/orchestrator/app/domain/project_director_programmer_no_write_plan.py`
- Service: `runtime/orchestrator/app/services/project_director_programmer_no_write_plan_service.py`
- Smoke: `runtime/orchestrator/scripts/p16_project_director_programmer_no_write_plan_smoke.py`
- Tests:
  - `runtime/orchestrator/tests/test_project_director_programmer_no_write_plan_contract.py`
  - `runtime/orchestrator/tests/test_project_director_programmer_no_write_plan_api.py`
  - `runtime/orchestrator/tests/test_project_director_programmer_no_write_plan_smoke.py`

No frontend entrypoint was added. P16 does not modify `apps/web/**`.

### Evidence Chain

```text
Project Director session
-> P11 evidence-to-agent dry-run
-> P12 safe dry-run Task
-> P12 Worker simulate
-> P13 controlled executor dispatch intent
-> P14 controlled subprocess lifecycle result
-> P15 readonly reviewer review
-> P16 programmer no-write implementation plan
-> Project Director session message readback
```

### P16-Codex Implementation Evidence

- Commit: `35c728eaece47819b3f0502f9c387db786231843`
- Implemented domain contract, service, and API endpoint
- Did not write tests, smoke, ledger, or README
- Does not create Task
- Does not create Run
- Does not call Worker
- Does not start Codex or Claude
- Does not perform Git write
- `product_runtime_git_write_allowed=false`
- `worktree_write_allowed=false`
- `file_write_allowed=false`
- `real_code_modified=false`
- `git_write_performed=false`
- AI Project Director total loop: `Partial`

### P16-Mimocode Test Evidence

- Commit: `c9c5c50a89cafef8a6a8dd00f51193ca1040d655`
- Contract tests: 16 passed
- API tests: 8 passed, 1 failed before R1
- Smoke tests: 8 passed
- Targeted total before R1: 32 passed, 1 failed
- Discovered implementation bug: P16 accepted `source_task_id=task_A` with `source_message_id=P15_review_message_from_task_B` (HTTP 200 instead of 409)
- Conclusion: source binding safety was Blocked before R1

### P16-R1 Fix Evidence

- Commit: `faf4d17327e8166541423bbea68183eda08eabcc`
- Modified files:
  - `runtime/orchestrator/app/services/project_director_programmer_no_write_plan_service.py`
  - `runtime/orchestrator/app/api/routes/project_director.py`
- Fix: P16 service now requires P15 review message to bind the requested source task by:
  - `related_task_id == source_task.id`, or
  - `p15_readonly_reviewer_review_record.source_task_id == str(source_task.id)` in `suggested_actions`
- Route maps `source_task_not_bound_to_p15_review` to HTTP 409
- Failing test rerun: 1 passed
- P16 targeted tests after R1: 33 passed
- Dry-run smoke: `passed_dry_run`
- Fake-plan smoke: `passed_fake_plan`
- Controlled no-write smoke: blocked with `controlled_no_write_not_enabled_in_api`

---

## P17 Programmer No-Write Execution

### Gate

- P17-Codex programmer no-write execution implementation: Pass with note
- P17-Mimocode contract tests: Pass
- P17-Mimocode API tests: Pass
- P17-Mimocode smoke tests: Pass
- P17 source binding safety: Pass
- P17 patch preview safety: Pass
- P17 overall: Pass with note
- AI Project Director total loop: Partial

### Implemented Surface

- Endpoint: `POST /project-director/sessions/{session_id}/programmer-no-write-execution`
- Domain: `runtime/orchestrator/app/domain/project_director_programmer_no_write_execution.py`
- Service: `runtime/orchestrator/app/services/project_director_programmer_no_write_execution_service.py`
- Smoke: `runtime/orchestrator/scripts/p17_project_director_programmer_no_write_execution_smoke.py`
- Tests:
  - `runtime/orchestrator/tests/test_project_director_programmer_no_write_execution_contract.py`
  - `runtime/orchestrator/tests/test_project_director_programmer_no_write_execution_api.py`
  - `runtime/orchestrator/tests/test_project_director_programmer_no_write_execution_smoke.py`

No frontend entrypoint was added. P17 does not modify `apps/web/**`.

### Evidence

- P17-Codex commit: `e795fcf4f274e55becfe5f1219e709ab1fc3228e`
- P17-Mimocode commit: `9c17dac8138eb0e81887a14d3e996ecbf6f89b56`
- Targeted tests: 43 passed
- Contract tests: 19 passed
- API tests: 24 passed
- Smoke tests: 12 passed
- P16 compatibility smoke: `passed_fake_plan`
- P17 dry_run smoke: `passed_dry_run`
- P17 fake_execution smoke: `passed_fake_execution`
- Controlled no-write: blocked with `controlled_no_write_not_enabled_in_api`
- Source task/message mismatch: blocked with 409
- Patch preview: preview-only, no applyable diff returned

### Boundary Record

- `apps/web/**` unchanged
- `docs/superpowers/**` untouched; existing untracked plan preserved
- `external_executors` unchanged
- `task_worker.py` unchanged
- Product runtime Git write remains forbidden
- Worktree write remains forbidden
- `file_write_allowed=false`
- `actual_patch_applied=false`
- Default path starts neither Codex nor Claude
- P17 does not create Task
- P17 does not create Run
- P17 does not call Worker
- P17 does not modify real code through product path
- P17 does not perform product runtime Git write
- `controlled_no_write` remains blocked at API/smoke layer
- AI Project Director total loop remains `Partial`

### Patch Preview Safety Note

- P17 service-generated `patch_preview` is preview-only.
- It must not be treated as an applyable patch.
- Tests verify that API output does not expose applyable diff markers such as:
  - `diff --git`
  - `--- a/`
  - `+++ b/`
  - `@@`
- Current domain field is `list[str]`; future P18/P19 should consider adding sanitizer/validator before accepting real model-generated patch previews.

---

## Current Capability After P17

P17 completes the following chain:

```text
Project Director session
-> evidence-to-agent dry-run
-> safe dry-run Task
-> Worker simulate / Run
-> controlled executor lifecycle evidence
-> readonly reviewer review
-> programmer no-write implementation plan
-> programmer no-write execution result
-> Project Director message readback
```

Not yet available:

- Actual file modification
- Sandbox/worktree write
- Real diff
- Targeted tests against changed code
- Reviewer reviews real diff
- Git add / commit / push / PR / merge by product runtime

## Next Step

P18 should not open product runtime Git write yet.

Preferred P18: Patch preview sanitizer / diff safety hardening before any sandbox file-write.

Reason: Before accepting real model-generated patch previews, the system should block applyable diff markers from preview-only channels.
