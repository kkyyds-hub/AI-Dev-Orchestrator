# P16 Programmer No-Write Plan Ledger - 2026-06-23

## Gate

- P16-Codex programmer no-write planning implementation: Pass with note
- P16-Mimocode contract tests: Pass
- P16-Mimocode API tests: Pass after R1
- P16-Mimocode smoke tests: Pass
- P16-R1 source binding fix: Pass
- P16 overall: Pass with note
- AI Project Director total loop: Partial

## Implemented Surface

- Endpoint: `POST /project-director/sessions/{session_id}/programmer-no-write-plan`
- Domain: `runtime/orchestrator/app/domain/project_director_programmer_no_write_plan.py`
- Service: `runtime/orchestrator/app/services/project_director_programmer_no_write_plan_service.py`
- Smoke: `runtime/orchestrator/scripts/p16_project_director_programmer_no_write_plan_smoke.py`
- Tests:
  - `runtime/orchestrator/tests/test_project_director_programmer_no_write_plan_contract.py`
  - `runtime/orchestrator/tests/test_project_director_programmer_no_write_plan_api.py`
  - `runtime/orchestrator/tests/test_project_director_programmer_no_write_plan_smoke.py`

No frontend entrypoint was added. P16 does not modify `apps/web/**`.

## Evidence Chain

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

## P16-Codex Implementation Evidence

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

## P16-Mimocode Test Evidence

- Commit: `c9c5c50a89cafef8a6a8dd00f51193ca1040d655`
- Contract tests: 16 passed
- API tests: 8 passed, 1 failed before R1
- Smoke tests: 8 passed
- Targeted total before R1: 32 passed, 1 failed
- Discovered implementation bug: P16 accepted `source_task_id=task_A` with `source_message_id=P15_review_message_from_task_B` (HTTP 200 instead of 409)
- Conclusion: source binding safety was Blocked before R1

## P16-R1 Fix Evidence

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

## Boundary Record

- `apps/web/**` unchanged
- `docs/superpowers/**` untouched; existing untracked plan preserved
- `external_executors` unchanged
- `task_worker.py` unchanged
- Product runtime Git write remains forbidden
- Worktree write remains forbidden
- `file_write_allowed=false`
- Default path starts neither Codex nor Claude
- P16 does not create Task
- P16 does not create Run
- P16 does not call Worker
- P16 does not modify real code through product path
- P16 does not perform product runtime Git write
- `controlled_no_write` remains blocked at API/smoke layer
- AI Project Director total loop remains `Partial`

## Current Capability After P16

P16 completes the following chain:

```text
Project Director session
-> evidence-to-agent dry-run
-> safe dry-run Task
-> Worker simulate / Run
-> controlled executor lifecycle evidence
-> readonly reviewer review
-> programmer no-write implementation plan
-> Project Director message readback
```

Not yet available:

- Programmer controlled no-write execution
- Actual file modification
- Sandbox/worktree write
- Targeted tests against changed code
- Reviewer reviews real diff
- Git add / commit / push / PR / merge by product runtime

## Next Step

P17 should be controlled programmer no-write execution.
Do not open file write or product runtime Git write yet.

P17 scope:

- Programmer executor consumes P16 plan
- Produces execution intent / patch preview / bounded handoff
- No file write
- No Task/Run creation by product path unless explicitly designed
- No Git write
- Result written back to Project Director session
