# Programmer No-Write Loop Ledger - 2026-06-23

> This ledger is the single backfill ledger for the programmer no-write loop.
> It records P16, P17, and P18 evidence in one place to avoid one-ledger-per-stage documentation sprawl.
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
- P18 adds domain-level `patch_preview` validation via `assert_patch_preview_safe`; raw applyable diff markers are now rejected by `ProjectDirectorProgrammerNoWriteExecutionStep` and `ProjectDirectorProgrammerNoWriteExecutionResult` field validators.

---

## P18 Patch Preview Sanitizer / Diff Safety Hardening

### Gate

- P18-Codex patch preview sanitizer implementation: Pass with note
- P18-Mimocode sanitizer contract tests: Pass
- P18-Mimocode P17 domain compatibility tests: Pass
- P18-Mimocode service/API safety tests: Pass
- P18-Mimocode smoke compatibility: Pass
- P18 patch preview safety: Pass
- P18 overall: Pass with note
- AI Project Director total loop: Partial

### Implemented Surface

- Sanitizer domain: `runtime/orchestrator/app/domain/project_director_patch_preview_safety.py`
- Integrated domain: `runtime/orchestrator/app/domain/project_director_programmer_no_write_execution.py`
- Integrated service: `runtime/orchestrator/app/services/project_director_programmer_no_write_execution_service.py`
- Tests:
  - `runtime/orchestrator/tests/test_project_director_patch_preview_safety.py`
  - `runtime/orchestrator/tests/test_project_director_programmer_no_write_execution_contract.py`
  - `runtime/orchestrator/tests/test_project_director_programmer_no_write_execution_api.py`
  - `runtime/orchestrator/tests/test_project_director_programmer_no_write_execution_smoke.py`

### P18-Codex Implementation Evidence

- Commit: `d155acac717234d777ab7b3c6dcdaa07ef389723`
- Implemented reusable patch preview safety module
- Unsafe markers covered:
  - `diff --git`
  - `--- a/`
  - `+++ b/`
  - `@@`
  - `index`
  - `new file mode`
  - `deleted file mode`
  - `rename from`
  - `rename to`
- Sanitizer behavior:
  - Safe preview-only content remains unchanged
  - Unsafe applyable diff markers are detected
  - Unsafe raw preview is replaced with fixed `PREVIEW ONLY` placeholder
  - Raw unsafe patch lines are not returned
  - Domain validator rejects raw unsafe `patch_preview`
- No tests/smoke/ledger were added by Codex
- No `apps/web` changes
- No `external_executors` changes
- No `task_worker` changes
- AI Project Director total loop remains `Partial`

### P18-Mimocode Test Evidence

- Commit: `94833dffc2296291976e21da7c76b67812c312ca`
- Targeted pytest: 78 passed
- Sanitizer contract tests: Pass
- P17 domain compatibility tests: Pass
- Service/API safety tests: Pass
- Smoke compatibility: Pass
- P17 dry_run smoke: `passed_dry_run`
- P17 fake_execution smoke: `passed_fake_execution`
- controlled_no_write: blocked with `controlled_no_write_not_enabled_in_api`
- Sanitizer unsafe marker coverage: all 9 markers tested individually
- Sanitizer removes raw unsafe diff content: yes
- Domain rejects unsafe `patch_preview`: yes
- API response `patch_preview`: preview-only
- Smoke output: no unsafe diff markers

### Boundary Record

- Product runtime Git write remains forbidden
- Worktree write remains forbidden
- `file_write_allowed=false`
- `actual_patch_applied=false`
- Default path starts neither Codex nor Claude
- P17/P18 does not create Task
- P17/P18 does not create Run
- P17/P18 does not call Worker
- No real code modified by product path
- No product runtime Git write performed
- AI Project Director total loop remains `Partial`
- P18 does not open sandbox/worktree file-write
- P18 does not open applyable patch channel
- P18 does not accept raw model-generated diff into preview-only channel

---

## Current Capability After P18

P18 completes the following chain:

```text
Project Director session
-> evidence-to-agent dry-run
-> safe dry-run Task
-> Worker simulate / Run
-> controlled executor lifecycle evidence
-> readonly reviewer review
-> programmer no-write implementation plan
-> programmer no-write execution result
-> patch preview sanitizer / diff safety hardening
-> Project Director message readback
```

Not yet available:

- Actual file modification
- Sandbox/worktree write
- Real diff application
- Targeted tests against changed code
- Reviewer reviews real diff
- Git add / commit / push / PR / merge by product runtime

## Next Step

P19 should still not open product runtime Git write.

Recommended P19 direction: Controlled sandbox/worktree file-write design review, not implementation yet.

P19 should define:

- Sandbox/worktree write boundary
- Allowed file path policy
- Patch application safety policy
- Rollback / cleanup strategy
- Reviewer-before-Git-write rule
- No product runtime Git write
- No automatic commit / push / PR
