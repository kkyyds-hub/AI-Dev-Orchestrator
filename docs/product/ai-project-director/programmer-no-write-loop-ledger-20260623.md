# Programmer No-Write Loop Ledger - 2026-06-23

> This ledger is the single backfill ledger for the programmer no-write loop.
> It records P16, P17, P18, P19, P20, P21-A, P21-B-A, P21-B-B, P21-C, P21-D-A, P21-D-B, P21-D-C1, P21-D-C2, P21-D-C3, P21-D-D1, P21-D-D2, P21-D-D3, P21-D-D4, P21-D-E, P22, and P23 evidence in one place to avoid one-ledger-per-stage documentation sprawl.
>
> 本文件是 programmer no-write loop 的统一总账，用于回填 P16/P17/P18/P19/P20/P21-A/P21-B-A/P21-B-B/P21-C/P21-D-A/P21-D-B/P21-D-C1/P21-D-C2/P21-D-C3/P21-D-D1/P21-D-D2/P21-D-D3/P21-D-D4/P21-D-E/P22/P23 后续证据，避免每个小阶段新增单独 ledger。

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

## P19 Sandbox / Worktree File-Write Design Review

### Gate

- P19 design review: Pass
- P19 implementation: Not started
- Sandbox/worktree file-write: Not enabled
- Product runtime Git write: Forbidden
- AI Project Director total loop: Partial

### Design Decision

P19 does not open file write.

P20 may implement controlled sandbox/worktree file-write only after this design is accepted. Product runtime Git write remains forbidden. The current P18 sanitizer protects the preview-only `patch_preview` channel; it is not a patch application system and must not become a write input by convention or by reuse.

Current code review notes:

- P18 added `runtime/orchestrator/app/domain/project_director_patch_preview_safety.py` and rejects raw applyable diff markers before P17 execution domain objects can carry unsafe `patch_preview`.
- P17 execution service still produces preview-only text and keeps `actual_patch_applied=false`, `file_write_allowed=false`, `worktree_write_allowed=false`, and `product_runtime_git_write_allowed=false`.
- Existing worktree create/cleanup services are for guarded `git worktree add` / `git worktree remove` lifecycle, not file-content modification.
- Existing external executor surfaces continue to preserve `product_runtime_git_write_allowed=false` and do not provide product runtime Git write authorization.

### Proposed Future Chain

Future P20/P21 should follow this chain, without implementing it in P19:

```text
Project Director session
-> P16 programmer no-write plan
-> P17 no-write execution result
-> P18 patch preview sanitizer
-> P20 controlled sandbox/worktree file-write request
-> allowlist path policy check
-> sanitized patch / file operation plan
-> sandbox/worktree write only
-> targeted tests in sandbox/worktree
-> P21 readonly reviewer real diff review
-> user confirmation
-> only then consider Git write design, still not automatic
```

### Write Boundary

Future write capability must obey these boundaries:

- Write only inside an approved sandbox/worktree; never write to the main repository working tree.
- Write only explicitly allowlisted paths.
- Deny by default:
  - `.env`
  - secrets
  - keys
  - credentials
  - `.git/**`
  - `node_modules/**`
  - `dist/**`
  - `build/**`
  - lockfiles, unless a later stage explicitly allows them
  - `docs/superpowers/**`
  - `apps/web/**`, unless a later stage explicitly approves frontend work
- Deny path traversal and escape by default:
  - `../`
  - absolute paths
  - symlink escape
- Deny binary writes by default.
- Deny file deletion by default, unless a later stage explicitly allows deletion.
- Deny `chmod`, `chown`, and shell-command-based writes.

### Patch / File Operation Policy

Future writes may accept only one of these input shapes.

A. Structured file operation plan:

- `path`
- `operation: create/update`
- `before_hash` or `expected_current_hash`
- `content_preview_hash`
- `reason`
- linked P16/P17/P18 evidence refs

B. Sanitized patch plan:

- patch must pass sanitizer
- patch must be parsed into structured operations before write
- raw applyable diff must not bypass sanitizer
- preview-only `patch_preview` must never be applied directly

Required policy statements:

- `patch_preview` is not patch apply input.
- `patch_preview` cannot directly write files.
- raw model-generated diff must not be applied directly.

### Safety Gates Before Write

Future P20 implementation must satisfy all of these gates before any write:

1. session exists
2. source_task exists
3. source_message belongs to session
4. source message is P17 no-write execution or later approved write design source
5. source task is safe dry-run or approved sandbox task
6. `user_confirmed=true`
7. allowlist path policy passes
8. patch/file operation sanitizer passes
9. no product runtime Git write
10. no main worktree write
11. rollback snapshot prepared
12. reviewer checkpoint required after write
13. targeted tests required after write
14. AI Project Director total loop remains Partial until UAT

### Rollback / Cleanup Strategy

Future sandbox/worktree write must provide rollback and cleanup before it can write:

- Record `before_hash` before every sandbox/worktree write.
- Generate one `operation_id` for every write operation.
- Record `affected_files` for every write operation.
- Cleanup must be able to remove temporary sandbox/worktree state.
- Rollback must be able to restore affected files to `before_hash`.
- If cleanup or rollback fails, enter failure recovery and block any Git write path.
- Never automatically delete user-unconfirmed content.

### Reviewer-Before-Git-Write Rule

- After sandbox/worktree write, a readonly reviewer must review the real diff.
- Reviewer result must bind to `source_task_id` and `source_message_id`.
- Reviewer must not write files.
- Reviewer must not execute Git write.
- If reviewer does not pass, the flow cannot enter Git write design.
- User confirmation record is not Git write authorization.
- Git add / commit / push / PR / merge remains a future separate stage and must not open automatically in P19/P20.

### Data Model Suggestions

Future domains may include:

- `ProjectDirectorSandboxWriteRequest`
- `ProjectDirectorSandboxWriteResult`
- `ProjectDirectorFileOperationPlan`
- `ProjectDirectorFileOperationResult`
- `ProjectDirectorWritePolicyCheck`
- `ProjectDirectorRollbackSnapshot`

Suggested fields:

- `session_id`
- `source_task_id`
- `source_message_id`
- `user_confirmed`
- `write_mode: dry_run / fake_write / controlled_sandbox_write`
- `allowed_paths`
- `denied_paths`
- `affected_files`
- `before_hashes`
- `after_hashes`
- `operation_ids`
- `rollback_available`
- `cleanup_required`
- `product_runtime_git_write_allowed=false`
- `main_worktree_write_allowed=false`
- `sandbox_write_allowed=true` only after gate
- `actual_patch_applied=false` until controlled write phase
- `git_write_performed=false`
- `ai_project_director_total_loop=Partial`

### API Suggestions

Future endpoints may be:

- `POST /project-director/sessions/{session_id}/sandbox-write-plan`
- `POST /project-director/sessions/{session_id}/sandbox-write-execution`

P19 adds no endpoint.

### Test Plan Suggestions

Future P20/P21 must test:

- path allowlist accepts allowed paths
- denied paths blocked
- `../` path traversal blocked
- absolute path blocked
- `.git` blocked
- `.env` blocked
- `docs/superpowers` blocked
- `apps/web` blocked unless explicitly allowed
- binary write blocked
- delete blocked by default
- `patch_preview` cannot be used as apply input
- raw diff cannot bypass sanitizer
- rollback snapshot created
- cleanup called
- reviewer required before Git write
- product runtime Git write remains false
- no Task/Run/Worker unless explicitly designed
- total loop remains Partial

### Risks / Open Questions

- How to represent sandbox/worktree identity safely.
- Whether to reuse existing worktree services or create a narrower sandbox abstraction.
- How to handle generated lockfiles.
- How to handle formatters that touch many files.
- How to enforce symlink escape checks.
- How to record file hashes reliably across OS.
- How to present diff to reviewer without exposing raw secrets.
- When, if ever, product runtime Git write can be introduced.

### Recommended P20

P20 should implement policy-only sandbox write preflight, not actual file write yet.

P20 should add:

- path allowlist/denylist checker
- patch/file operation plan validator
- no-write preflight result
- tests/smoke
- no actual file write
- no Git write

---

## P20 Policy-Only Sandbox Write Preflight

### Gate

- P20-Codex policy-only sandbox write preflight implementation: Pass with note
- P20-Mimocode path policy tests: Pass
- P20-Mimocode preflight contract tests: Pass
- P20-Mimocode API tests: Pass
- P20-Mimocode smoke tests: Pass
- P20 policy-only no-write safety: Pass
- P20 overall: Pass with note
- AI Project Director total loop: Partial

### Implemented Surface

- Endpoint: `POST /project-director/sessions/{session_id}/sandbox-write-preflight`
- Policy domain: `runtime/orchestrator/app/domain/project_director_sandbox_write_policy.py`
- Preflight domain: `runtime/orchestrator/app/domain/project_director_sandbox_write_preflight.py`
- Service: `runtime/orchestrator/app/services/project_director_sandbox_write_preflight_service.py`
- Route: `runtime/orchestrator/app/api/routes/project_director.py`
- Smoke: `runtime/orchestrator/scripts/p20_project_director_sandbox_write_preflight_smoke.py`
- Tests:
  - `runtime/orchestrator/tests/test_project_director_sandbox_write_policy.py`
  - `runtime/orchestrator/tests/test_project_director_sandbox_write_preflight_contract.py`
  - `runtime/orchestrator/tests/test_project_director_sandbox_write_preflight_api.py`
  - `runtime/orchestrator/tests/test_project_director_sandbox_write_preflight_smoke.py`

### P20-Codex Implementation Evidence

- Commit: `70b0afe75cddfd38bd754f2af49907c4c2d81283`
- Implemented policy-only sandbox write preflight endpoint
- Implemented path allowlist / denylist checker
- Implemented file operation plan validation
- Integrated `patch_preview` safety validation
- Added Project Director message binding with `source_detail`: `p20_sandbox_write_preflight`
- No tests/smoke/ledger were added by Codex
- No `apps/web` changes
- No `external_executors` changes
- No `task_worker` changes
- No worktree create/cleanup/write runner changes
- No product runtime Git write
- No file write
- No worktree write
- AI Project Director total loop remains `Partial`

### P20-Mimocode Test Evidence

- Commit: `38e9519919582ad31b264a305a7ca558b31b555c`
- Targeted pytest: 132 passed
- Path policy tests: Pass
- Preflight contract tests: Pass
- API tests: Pass
- Smoke tests: Pass
- P20 dry_run smoke: `passed_dry_run`
- P20 fake_preflight smoke: `passed_fake_preflight`
- controlled_sandbox_write: blocked with `controlled_sandbox_write_not_enabled_in_api`
- Path policy allowlist: all 4 default prefixes accepted
- Denylist coverage: `.git`, `node_modules`, `dist`, `build`, `docs/superpowers`, `.env` variants, sensitive substrings, lockfiles, binary suffixes all blocked
- apps/web behavior: blocked unless `allow_frontend=true` and `allowed_path_prefixes` includes `apps/web/`
- unsafe `patch_preview`: blocked
- source_task/message mismatch: blocked with `source_task_not_bound_to_p17_execution`
- message readback: succeeded
- operation=delete: observed as blocked; API may return 409 or 422 depending on validation path; direct policy function reports `unsupported_operation`

### Boundary Record

- P20 is policy-only preflight
- P20 does not write files
- P20 does not create worktree
- P20 does not write worktree
- P20 does not write main worktree
- P20 does not apply patch
- P20 does not perform product runtime Git write
- `product_runtime_git_write_allowed=false`
- `main_worktree_write_allowed=false`
- `worktree_write_allowed=false`
- `file_write_allowed=false`
- `actual_patch_applied=false`
- `real_code_modified=false`
- `git_write_performed=false`
- Default path starts neither Codex nor Claude
- P20 does not create Task
- P20 does not create Run
- P20 does not call Worker
- AI Project Director total loop remains `Partial`

---

## P21-A Sandbox Write Execution dry_run / fake_write

### Gate

- P21-A-Codex sandbox write execution dry-run/fake-write implementation: Pass with note
- P21-A-Mimocode contract tests: Pass
- P21-A-Mimocode API tests: Pass
- P21-A-Mimocode smoke tests: Pass
- P21-A dry_run/fake_write no-write safety: Pass
- P21-A overall: Pass with note
- AI Project Director total loop: Partial

### Implemented Surface

- Endpoint: `POST /project-director/sessions/{session_id}/sandbox-write-execution`
- Domain: `runtime/orchestrator/app/domain/project_director_sandbox_write_execution.py`
- Service: `runtime/orchestrator/app/services/project_director_sandbox_write_execution_service.py`
- Route: `runtime/orchestrator/app/api/routes/project_director.py`
- Smoke: `runtime/orchestrator/scripts/p21_project_director_sandbox_write_execution_smoke.py`
- Tests:
  - `runtime/orchestrator/tests/test_project_director_sandbox_write_execution_contract.py`
  - `runtime/orchestrator/tests/test_project_director_sandbox_write_execution_api.py`
  - `runtime/orchestrator/tests/test_project_director_sandbox_write_execution_smoke.py`

### P21-A-Codex Implementation Evidence

- Commit: `674115dc5c0348ff837e75d7b5920a91d3017c1d`
- Commit message: `backend: add sandbox write execution dry run`
- Implemented sandbox write execution domain/service/API
- Supports only `dry_run` and `fake_write`
- Blocks `controlled_sandbox_write`
- Persists P21 Project Director message with `source_detail=p21_sandbox_write_execution`
- Does not write files
- Does not create worktree
- Does not write worktree
- Does not write main worktree
- Does not apply patch
- Does not perform product runtime Git write
- Does not create Task
- Does not create Run
- Does not call Worker
- Does not start Codex or Claude
- Does not read target file content
- AI Project Director total loop remains `Partial`

### P21-A-Mimocode Test Evidence

- Commit: `8b579b84ee0fb1de271b52a813e91d6958515d50`
- Commit message: `test: add sandbox write execution coverage`
- Contract tests: 32 passed
- API tests: 10 passed
- Smoke tests: 19 passed
- Final targeted regression: 106 passed
- dry_run smoke: `passed_dry_run`, `p21_execution_status=planned`, `p21_dry_run=passed_planned`
- fake_write smoke: `passed_fake_write`, `p21_execution_status=simulated`, `p21_fake_write=passed_simulated`
- `controlled_sandbox_write`: blocked with `controlled_sandbox_write_not_enabled_in_api`
- blocked preflight: blocked via `path_policy_failed`
- source_task/message mismatch: blocked with `source_task_not_bound_to_p20_preflight`
- message readback: passed
- no-write boundary: passed
- misleading output check: passed
- AI Project Director total loop: `Partial`

### Boundary Record

- `product_runtime_git_write_allowed=false`
- `main_worktree_write_allowed=false`
- `worktree_write_allowed=false`
- `file_write_allowed=false`
- `actual_patch_applied=false`
- `real_code_modified=false`
- `git_write_performed=false`
- `native_executor_started=false`
- `codex_started=false`
- `claude_code_started=false`
- `worker_started=false`
- `task_created=false`
- `run_created=false`
- `worktree_created=false`
- `worktree_cleaned_up=false`
- `rollback_snapshot_created=false`
- `cleanup_required=false`
- `file_written=false`
- `target_file_content_read=false`
- `patch_applied=false`
- Product runtime Git write remains forbidden.
- AI Project Director total loop remains `Partial`.

---

## P21-B-A Sandbox Write Operation Intent Preservation

### Gate

- P21-B-A implementation: Pass
- P21-B-A targeted regression: Pass
- P21-B-A no-write boundary: Pass
- P21-B-A process note: Accepted this time only because Codex also changed tests; future stages must split implementation and tests
- P21-B-A overall: Pass with process note
- AI Project Director total loop: Partial

### Process Note

This stage was executed by Codex and included implementation plus targeted test updates. This is accepted for P21-B-A only because the instruction allowed it before the user clarified the rule.

Future stages must follow:

- Codex: implementation only
- Mimocode: tests / smoke / verification only
- DeepSeek: docs / ledger / evidence only

Do not allow Codex to write tests in future task instructions.

### Implementation Evidence

- Commit: `3df0add3e11edfeb91296fcf9e1d4474595c15dd`
- Commit message: `backend: preserve sandbox write operation intent`
- P20 preflight now records structured accepted operation intent: `accepted_operations[{path, operation}]`
- P20 still keeps legacy: `accepted_operation_paths`
- P20 suggested action now includes `accepted_operations`
- P21-A execution now reads original operation intent from P20 action
- P21-A operation result now preserves: `operation=create/update`, `source_preflight_operation_type=p20_preflight_accepted_path`
- Legacy P20 actions with paths only still fallback to: `operation=p20_preflight_accepted_path`
- No real write capability was added.

### Modified Surface

Implementation files:

- `runtime/orchestrator/app/domain/project_director_sandbox_write_preflight.py`
- `runtime/orchestrator/app/domain/project_director_sandbox_write_execution.py`
- `runtime/orchestrator/app/services/project_director_sandbox_write_preflight_service.py`
- `runtime/orchestrator/app/services/project_director_sandbox_write_execution_service.py`
- `runtime/orchestrator/app/api/routes/project_director.py`

Targeted test files modified in this commit:

- `runtime/orchestrator/tests/test_project_director_sandbox_write_preflight_contract.py`
- `runtime/orchestrator/tests/test_project_director_sandbox_write_preflight_api.py`
- `runtime/orchestrator/tests/test_project_director_sandbox_write_execution_contract.py`
- `runtime/orchestrator/tests/test_project_director_sandbox_write_execution_api.py`

### Test Evidence

- Targeted regression: `108 passed`
- P20/P21 contract/API/smoke passed
- Executed through equivalent `uv run ... pytest` because direct `pytest` was not in shell PATH
- Smoke summary:
  - dry_run: `passed_dry_run`
  - fake_write: `passed_fake_write`
  - controlled sandbox write: `blocked`
  - no-write boundary: `passed`

### Boundary Record

- `controlled_sandbox_write` remains blocked
- `product_runtime_git_write_allowed=false`
- `main_worktree_write_allowed=false`
- `worktree_write_allowed=false`
- `file_write_allowed=false`
- `actual_patch_applied=false`
- `real_code_modified=false`
- `git_write_performed=false`
- `native_executor_started=false`
- `codex_started=false`
- `claude_code_started=false`
- `worker_started=false`
- `task_created=false`
- `run_created=false`
- `worktree_created=false`
- `worktree_cleaned_up=false`
- `rollback_snapshot_created=false`
- `cleanup_required=false`
- `file_written=false`
- `patch_applied=false`
- `target_file_content_read=false`
- Product runtime Git write remains forbidden.
- AI Project Director total loop remains `Partial`.

---

## P21-B-B Controlled Sandbox Write Design Lock

### Gate

- P21-B-B implementation: Pass
- P21-B-B-R1 blocked API status fix: Pass
- P21-B-B-Mimocode tests/smoke: Pass with note
- P21-B-B no-write boundary: Pass
- P21-B-B overall: Pass with note
- AI Project Director total loop: Partial

### Implementation Evidence

- Implementation commit: `e2eeddf86028742ed48660c87cd736066e4bec96`
- Commit message: `backend: add sandbox write design lock`
- Added endpoint: `POST /project-director/sessions/{session_id}/sandbox-write-design-lock`
- Added domain: `runtime/orchestrator/app/domain/project_director_sandbox_write_design_lock.py`
- Added service: `runtime/orchestrator/app/services/project_director_sandbox_write_design_lock_service.py`
- Modified route: `runtime/orchestrator/app/api/routes/project_director.py`
- Successful design lock persists: `source_detail=p21_b_sandbox_write_design_lock`
- Source message must be: `source_detail=p21_sandbox_write_execution`
- `controlled_sandbox_write_design_locked=true` only means design locked for review.
- It does not mean controlled sandbox write is enabled.
- It does not mean file write / worktree write / patch apply / Git write is enabled.
- AI Project Director total loop remains Partial.

### R1 Fix Evidence

- R1 commit: `e3cf7791e670db3f3268542ed5d2e2e2df51601d`
- Commit message: `backend: return conflict for blocked design lock`
- R1 changed only: `runtime/orchestrator/app/api/routes/project_director.py`
- R1 fixed:
  - blocked design lock now returns HTTP 409
  - blocked design lock does not return 200 + `design_lock_status=blocked`
  - blocked design lock does not create `ProjectDirectorMessage`
  - locked success path still returns 200
- R1 verification: compileall exit 0; `git diff --check` exit 0
- No tests were changed by Codex in R1.

### Mimocode Test Evidence

- Mimocode commit: `86603142e679e873f03edf912f8783b28e1fd575`
- Commit message: `test: add sandbox write design lock coverage`
- Added files:
  - `runtime/orchestrator/tests/test_project_director_sandbox_write_design_lock_contract.py`
  - `runtime/orchestrator/tests/test_project_director_sandbox_write_design_lock_api.py`
  - `runtime/orchestrator/tests/test_project_director_sandbox_write_design_lock_smoke.py`
  - `runtime/orchestrator/scripts/p21_b_project_director_sandbox_write_design_lock_smoke.py`
- Mimocode did not modify: `runtime/orchestrator/app/**`, `docs/**`, `apps/web/**`, `external_executors/**`, dependency / lockfile files
- Reported targeted test results:
  - contract: `29 passed`
  - API: `10 passed`
  - smoke pytest: `7 passed`
  - smoke script: `passed`
  - adjacent targeted regression: `154 passed`
- Note: 29 + 10 + 7 = 46 new targeted pytest cases for design lock coverage. Do not write "46 contract tests"; contract command reported 29 passed.

### Tested Behavior

- dry_run design lock: HTTP 200, `design_lock_status=locked`
- fake_write design lock: HTTP 200, `design_lock_status=locked`
- user_confirmed=false: HTTP 409
- non-P21 source message: HTTP 409
- source task/message mismatch: HTTP 409
- runtime write flag true: blocked at service level
- operation intent missing: blocked at service level
- blocked design lock: creates no `ProjectDirectorMessage`
- successful design lock: creates exactly one `ProjectDirectorMessage`
- successful design lock: creates no Task, creates no Run
- message readback: includes `source_detail=p21_b_sandbox_write_design_lock`
- misleading output: absent
- smoke: uses isolated runtime data; refuses non-isolated runtime data; clears `OPENAI_API_KEY`; uses simulate override; cleans temporary runtime data

### Boundary Record

- `controlled_sandbox_write_enabled=false`
- `sandbox_write_allowed=false`
- `product_runtime_git_write_allowed=false`
- `main_worktree_write_allowed=false`
- `worktree_write_allowed=false`
- `file_write_allowed=false`
- `actual_patch_applied=false`
- `real_code_modified=false`
- `git_write_performed=false`
- `native_executor_started=false`
- `codex_started=false`
- `claude_code_started=false`
- `worker_started=false`
- `task_created=false`
- `run_created=false`
- `worktree_created=false`
- `worktree_cleaned_up=false`
- `rollback_snapshot_created=false`
- `cleanup_required=false`
- `target_file_content_read=false`
- real diff generation remains unavailable
- product runtime Git write remains forbidden
- AI Project Director total loop remains `Partial`

### Current Capability After P21-B-B

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
-> sandbox/worktree write design review
-> policy-only sandbox write preflight with structured operation intent
-> sandbox write execution dry_run / fake_write result preserving original operation intent
-> controlled sandbox write design lock
-> Project Director message readback
```

### Not Yet Available

- Actual file modification
- Controlled sandbox/worktree write
- Worktree create/write/cleanup for P21 execution
- Real diff generation
- Target file content read
- Targeted tests against actually changed code
- Readonly reviewer real diff review
- Rollback snapshot
- Product runtime Git add / commit / push / PR / merge

### Process Note

- Future Codex tasks must not add, modify, or delete tests.
- Future Mimocode tasks should first inspect existing tests, helpers, fixtures, and smoke scripts.
- If existing helper / fixture / smoke chain can be reused cleanly, reuse it.
- If reuse would make tests unclear, fragile, or unsafe, adding a new focused test file is acceptable.
- Do not create new test files just by habit.
- Do not force reuse if it weakens safety boundary coverage.
- DeepSeek should only update docs / ledger / evidence.

---

## P21-C-H-B2 Readonly Reviewer Production Execution Verification

### Gate

- P21-C-H-B2-A Transport + Adapter: Closed / Pass
- P21-C-H-B2-B Native Reviewer Transport: Closed / Pass
- P21-C-H-B2-C1 Real Codex Production Reviewer: Closed / Pass
- P21-C-H-B2-C2 Real Claude Code Production Reviewer: Closed / Pass
- P21-C-H-B2 overall: Closed / Pass
- P21-C overall: Partial
- AI Project Director total loop: Partial

### Architecture Conclusion: Reviewer Executor Split

Codex reviewer uses a dedicated Codex app-server transport (`CodexAppServerReadonlyReviewerTransport`). It does not use the failed `codex exec` path.

Claude Code reviewer uses native capture transport (`NativeReadonlyReviewerCaptureTransport`). It does not use the Codex app-server architecture.

### Architecture Conclusion: Provider / Executor Separation

Claude Code is the executor. MiMo was the provider/model profile used in the controlled production smoke. The verified model was `mimo-v2.5-pro`.

The transport now has an explicit seam to receive a resolved Claude Code child environment. The system is not locked to MiMo or to any single provider. The same seam supports DeepSeek, MiMo, or any other Anthropic-compatible provider.

### Root Cause and Fix

The original Claude production smoke timed out because the native transport implicitly inherited the caller's parent process environment. Different launch contexts produced different provider profiles, leading to non-deterministic behavior.

This was not:

- Claude Code CLI installation failure
- MiMo incompatibility
- Production prompt complexity
- H-B1 schema issue

The fix was to add `claude_code_child_environment: Mapping[str, str] | None` to `NativeReadonlyReviewerCaptureTransport`. The contract is:

- Constructor materializes an independent snapshot of the caller mapping.
- Explicit environment only reaches Claude Code processes.
- `None` preserves legacy environment inheritance.
- Codex does not receive the Claude environment.
- Each process launch receives an independent env dict copy.
- Transport contains no MiMo / DeepSeek-specific logic.

### R1 Production Fix Evidence

- Commit: `4fb439e7deccec5e0c95baae497ba5fbb8d9062c`
- Commit message: `fix: inject claude reviewer child environment`
- Modified file: `runtime/orchestrator/app/external_executors/readonly_reviewer_native_transport.py`
- Only one production file changed.
- No tests changed by Codex.
- No provider-specific production logic added.
- Claude argv unchanged.
- Codex argv unchanged.
- No profile / shell / credential file reads.
- Product runtime Git write not added.
- Codex reported targeted evidence: native transport contracts 50 passed, adjacent Codex app-server regression 46 passed.
- This is executor-reported test evidence.

### Mimocode Contract Evidence

- Commit: `a7ea4e3452a4502478f1ace6a61ee7d9b5571c94`
- Commit message: `test: lock claude reviewer child environment contracts`
- Modified file: `runtime/orchestrator/tests/test_project_director_sandbox_candidate_diff_readonly_reviewer_native_transport_contract.py`
- New contracts locked:

1. Explicit Claude environment injection
2. Exact environment content
3. Constructor snapshot isolation
4. Claude None / omitted legacy behavior
5. Codex isolation (env key absent)
6. Claude exact argv preservation
7. Codex exact argv preservation
8. Per-execution environment copy isolation

- Test evidence: targeted native transport 59 passed, adjacent Codex app-server regression 46 passed.
- No real profile read. No real credential. No real model/provider call. No production app changes.

### CFG1 Isolated MiMo Connectivity Evidence

No repository commit.

```text
cc-mimo
→ Claude Code 2.1.205
→ Xiaomi MiMo official Anthropic-compatible endpoint
→ mimo-v2.5-pro
→ one real model conversation
→ stdout OK
→ exit code 0
```

Boundary: one real process launch, one real model conversation, no retry, no repository file modification, no Git commit, no lingering Claude process.

### Final Production Smoke Evidence

Stage: P21-C-H-B2-C2-S1-R1-S1-Mimocode

Classification: explicit MiMo child environment production reviewer chain fully verified.

Real chain:

```text
production deterministic review prompt builder
→ production Adapter
→ NativeReadonlyReviewerCaptureTransport
→ explicit resolved MiMo child environment
→ real Claude Code process
→ real MiMo model turn
→ production H-B1 strict validation
```

Input:

- Review scope: `src/smoke_sample.py`
- Synthetic comment-only unified diff
- Source diff SHA256: `f012e6878443e9eac92347d12941308e91c362a0833ee266d7ea1775dd514ba2`
- Review prompt SHA256: `a3b61daa086bcf5c547313623f39b4b09a8875cb8aa8b6e31a1e87cc1110b92f`
- Review prompt bytes: 2174

Smoke results:

- Adapter invocation count: 1
- Transport execute count: 1
- Real Claude process launch count: 1
- Real model conversation count: 1
- Codex launch count: 0
- Direct provider HTTP request count: 0
- Duration: 11.30 seconds
- Timeout: false
- `adapter_status`: `validated_output`
- `review_prompt_verified`: true
- `transport_invoked`: true
- `transport_status`: `completed`
- `transport_error_code`: null
- `execution_mode`: `native_capture_transport`
- `output_validation_status`: `validated`
- `strict_json_valid`: true
- `schema_valid`: true
- `semantics_valid`: true
- `evidence_scope_valid`: true
- `review_status`: `reviewed`
- `verdict`: `no_blocking_findings`
- `risk_level`: `low`
- `findings`: 0
- `recommended_next_step`: No blocking issues. Safe to proceed.
- `real_reviewer_started`: true
- `real_reviewer_executed`: true
- `native_process_started`: true
- `provider_called`: false
- `codex_started`: false
- `claude_code_started`: true

`provider_called=false` is the current transport result schema field value. It does not mean no real model request occurred. The real model conversation happened through the Claude Code CLI.

### Safety Evidence

- New lingering Claude PID count: 0
- Workspace before / after: identical
- Production transport sentinel: identical
- MiMo profile: identical
- Project files modified by smoke: no
- Smoke commit: none
- `runtime/orchestrator/uv.lock`: generated and removed as execution side effect
- Root `uv.lock`: unchanged

### Product Boundary Record

Even though P21-C-H-B2 is Closed / Pass:

- No automatic patch apply.
- No product runtime Git add.
- No product runtime Git commit.
- No product runtime Git push.
- No automatic PR.
- No automatic merge.
- Reviewer verdict is not human approval.
- Product runtime Git write remains forbidden.
- AI Project Director total loop remains Partial.

---

## P21-C-H-C1 Readonly Review Execution Orchestration

### Gate

- P21-C-H-C1-Codex: Closed / Pass
- P21-C-H-C1-Mimocode: Closed / Pass
- P21-C-H-C1 overall: Closed / Pass

### Key Commits

- `685ede7d194a0250a8914e9a8c144de9236addd5` — `backend: add readonly review execution orchestration`
- `f647094938650c12a994fa3ffad1fede3913dc54` — `test: lock readonly review execution orchestration contracts`
- `0adc99fae346abbe0d8408b5080ab1e1ecdcb8b8` — `test: close readonly review orchestration contract gaps`

### Architecture

Core chain:

```text
persisted execution preflight validation
→ source diff evidence validation
→ deterministic review prompt reconstruction
→ review prompt fingerprint validation
→ transport / resolver seam
→ readonly reviewer Adapter
→ persistence
```

### Boundary Record

- Does not accept request-controlled executor override of persisted executor.
- Does not accept request-controlled workspace.
- Does not start transport before evidence validation.
- Does not persist on failure.
- Does not perform Git write.
- `ai_project_director_total_loop` remains `Partial`.

---

## P21-C-H-C2 Deferred Readonly Reviewer Transport Resolution

### Gate

- P21-C-H-C2-Codex: Closed / Pass
- P21-C-H-C2-Mimocode: Closed / Pass
- P21-C-H-C2 overall: Closed / Pass

### Key Commits

- `ed860b09fbcc5781fe6bde66ef044703104a7203` — `backend: defer readonly reviewer transport resolution`
- `479b66803fcfa6c3d41ff568e628b80f217afc21` — `backend: normalize readonly reviewer resolver failures`
- `1b6f080fb7f01752a6e4f9afa42b02503f7b392e` — `test: lock deferred readonly reviewer transport resolution contracts`
- `d7ff75c0e5b804ce23fd27b4af9ed94480867831` — `test: close readonly reviewer resolver contract gaps`

### Architecture

Core ordering:

```text
persisted evidence validation
→ source diff validation
→ prompt reconstruction
→ prompt fingerprint validation
→ resolver(persisted trusted executor)
→ Adapter
→ persistence
```

Legal persisted reviewer executor values: `codex`, `claude-code`.

Resolver contract:

- Called at most once per execution.
- No retry. No fallback. No auto-switch.
- Failure reason: `readonly_reviewer_transport_resolution_failed`.
- On failure: Adapter = 0, message create = 0, commit = 0.

---

## P21-C-H-C3 Concrete Readonly Reviewer Transport Resolver

### Gate

- P21-C-H-C3-Codex: Closed / Pass
- P21-C-H-C3-Mimocode: Closed / Pass
- P21-C-H-C3 overall: Closed / Pass

### Key Commits

- `d412fc3f92479b307b37983c66d17cc4289b2c7e` — `backend: add concrete readonly reviewer transport resolver`
- `8681c73007443514049ee5e1382d66a1afa53738` — `test: lock concrete readonly reviewer transport resolver contracts`

### Resolver Mapping

```text
codex → CodexAppServerReadonlyReviewerTransport
claude-code → NativeReadonlyReviewerCaptureTransport
```

### Boundary Record

- Each legal resolve creates exactly one matching transport.
- Does not pre-create the other transport.
- Does not cache. Does not fallback. Does not retry. Does not auto-switch.
- Resolver is not responsible for: process execution, process start, persistence, settings read, env read, credential read, DB evidence read, workspace inference.

---

## P21-C-H-C4 Trusted Workspace-Bound Production API Composition

### Gate

- P21-C-H-C4-A Evidence Pack: Closed / Pass with note
- P21-C-H-C4-B: Closed / Pass with note
- P21-C-H-C4-C Evidence Pack: Cancelled / unnecessary
- P21-C-H-C4-D: Closed / Pass with note
- P21-C-H-C4 overall: Closed / Pass with note

Note on H-C4-C: Cancelled by AI Project Director. No further architecture investigation needed for ordinary scope; AI Project Director directly inspected latest origin/main and key code.

### H-C4-B Workspace Factory Composition

Production: `6a7848530a4174dfa94f9a7c350c8ff90a7bcb88` — `backend: defer readonly reviewer resolver composition to trusted workspace`

Tests: `1e05e1ec97bc03dd19458feffd59556e6999c4fd` — `test: lock trusted workspace resolver composition contracts`

New class: `ReadonlyReviewerTransportResolverFactory`.

Architecture:

```text
Execution Service
  completes persisted evidence / diff / prompt validation
  ↓
reads persisted source diff action.workspace_path
  ↓
confirms workspace_path_within_root is True
  ↓
calls Factory
  ↓
Factory re-validates current workspace root / workspace state
  ↓
creates Resolver
```

Factory is not responsible for: Popen creation, process start, provider selection, credential read, settings read, transport execution, persistence.

### H-C4-D Production API Composition

Production: `5df01975d29a0a659d9b3c23898f20294a3ecea9` — `backend: wire readonly reviewer execution api`

Initial tests: `3eabf4a00aa4dfd0378b3a222aed33745edde2c7` — `test: lock readonly reviewer execution api composition`

R1 tests: `cc22fb2cb6b83ecbc474149fe878dd7c2c9aea5a` — `test: close readonly reviewer api composition gaps`

Endpoint: `POST /project-director/sessions/{session_id}/sandbox-candidate-diff-review-execution`

Request fields: `source_task_id`, `source_message_id`, `user_confirmed`. Must not contain: `executor`, `workspace`, `provider`, `model`, `token`.

Production lazy composition:

```text
HTTP explicit confirmation
→ Execution Service
→ persisted preflight validation
→ source diff validation
→ prompt reconstruction / fingerprint validation
→ route-local lazy callable
→ per-execution RealExecutorProcessSupervisor
→ ReadonlyReviewerTransportResolverFactory
→ Resolver
→ persisted reviewer executor
→ transport
→ Adapter
→ persistence
```

Workspace root: `settings.runtime_data_dir / "project-director" / "sandbox-workspaces"`.

Config: `readonly_reviewer_timeout_seconds` (default 180, minimum 1), `readonly_reviewer_max_output_bytes` (default 262144, minimum 1).

### H-C4 Test Closure Evidence

R1 confirmed:

- Explicit confirmation failure: Supervisor = 0, Factory constructor = 0, Factory call = 0, Popen = 0.
- Early persisted evidence failure: Supervisor = 0, Factory constructor = 0, Factory call = 0, Popen = 0.
- Success composition: Supervisor constructor = 1, Factory constructor = 1, Factory call = 1, Resolver call = 1, real Popen = 0 in contract test.
- Factory exact workspace = persisted source diff action.workspace_path.
- Request adversarial `workspace_path=/evil/path` cannot override persisted workspace.
- HTTP mapping: `user_confirmed=false` → 409; blocked reasons → 409 with `;`.join; empty reasons → fallback message; `ValueError("not found")` → 404; other `ValueError` → 422.

---

## P21-C-H-C5 Real Readonly Reviewer Production API Runtime Verification

### Gate

- P21-C-H-C5-A: Closed / Pass with note
- P21-C-H-C5-B: Closed / Pass with note
- P21-C-H-C5 overall: Closed / Pass with note

### H-C5-A Real Codex Evidence

No repository commit.

Environment recovery:

```text
legacy /usr/local/bin/codex → broken symlink (old Codex.app binary unavailable)
→ recovered via npm install -g @openai/codex
→ codex-cli 0.144.1
→ supports codex app-server --listen stdio://
```

Real production smoke result:

```text
real reviewer execution = 1
HTTP = 200
adapter_status = validated_output
requested_reviewer_executor = codex
execution_mode = codex_app_server_transport
transport = CodexAppServerReadonlyReviewerTransport
transport_command = codex app-server --listen stdio://
transport_invoked = true
transport_status = completed
output_validation_status = validated
strict_json_valid = true
schema_valid = true
semantics_valid = true
evidence_scope_valid = true
review_status = reviewed
verdict = non_blocking_findings
risk_level = low
real_reviewer_started = true
real_reviewer_executed = true
native_process_started = true
codex_started = true
claude_code_started = false
provider_called = false
```

Persistence: Task 1→1, Run 1→1, Message 18→19, message_bound = true.

Safety: all no-write flags false; no raw output / workspace leakage; no new lingering app-server process.

### H-C5-B Real Claude Code Evidence

No repository commit.

First production smoke (wrong parent environment):

```text
old gateway: BASE_URL host = anyrouter.top, MODEL = claude-opus-4-8
→ real execution 1 time → ~180 seconds → HTTP 409, reviewer_transport_failed
→ no persistence, no Task/Run increment, no lingering process
```

Sanitized environment probe: removed Anthropic provider env vars → 0.92 seconds fast failure → proves no backup official Claude auth available locally.

Environment diagnosis:

```text
wrong old environment: anyrouter.top / claude-opus-4-8
correct verified MiMo environment: api.xiaomimimo.com / mimo-v2.5-pro
```

Direct CLI probe (same argv shape as production transport):

```text
claude -p "Review the content..." --permission-mode plan --no-session-persistence
duration = 8.06 seconds, exit code = 0, stdout = OK
```

Final E3 production API smoke under correct MiMo parent environment:

```text
real reviewer execution = 1
duration = 13.70 seconds
HTTP = 200
adapter_status = validated_output
requested_reviewer_executor = claude-code
execution_mode = native_capture_transport
transport_invoked = true
transport_status = completed
transport_error_code = null
output_validation_status = validated
strict_json_valid = true
schema_valid = true
semantics_valid = true
evidence_scope_valid = true
review_status = reviewed
verdict = no_blocking_findings
risk_level = low
real_reviewer_started = true
real_reviewer_executed = true
native_process_started = true
codex_started = false
claude_code_started = true
provider_called = false
```

Persistence: Task 1→1, Run 1→1, Message 18→19, message_bound = true.

Safety: all no-write flags false; no raw output / workspace leakage; no new lingering Claude process.

### Claude Environment Operational Note

After H-C5 completion, local Claude Code configuration was normalized to a single MiMo provider setup. This is a local operational change, not a repository production change. No repository commit. No production code change. No project tracked file change.

Target local structure:

```text
direct claude invocation
→ ~/.claude/settings.json
→ MiMo
→ api.xiaomimimo.com/anthropic
→ mimo-v2.5-pro
```

---

## P21-C Final Gate

### Gate

- P21-C-H-B2: Closed / Pass
- P21-C-H-C1: Closed / Pass
- P21-C-H-C2: Closed / Pass
- P21-C-H-C3: Closed / Pass
- P21-C-H-C4: Closed / Pass with note
- P21-C-H-C5: Closed / Pass with note
- P21-C overall: Closed / Pass with note

### Core Capability Conclusion

```text
controlled sandbox candidate diff
→ persisted readonly review handoff
→ execution preflight
→ explicit user confirmation
→ persisted trusted reviewer executor
→ persisted trusted workspace
→ current workspace revalidation
→ real Codex / Claude Code reviewer execution
→ strict output validation
→ review result persistence
```

### Product Boundary Record

- No automatic patch apply.
- No product runtime git add / commit / push.
- No automatic PR / merge.
- No branch deletion.
- No reset / checkout / switch / stash / rebase / tag.
- No automatic CI trigger.
- Reviewer verdict is not human approval.
- User confirmation is not Git write authorization.
- Product runtime Git write remains forbidden.

### AI Project Director Total Loop

- AI Project Director total loop: Partial.
- Final UAT not yet complete.
- Product runtime Git write still not opened.
- Full user closure cycle not yet finished.

---

## P21-D-A Stage Contract Design Closure

### Gate

- P21-D-A-R1: Closed / Pass
- P21-D-A overall: Closed / Pass

### Initial Design Commit

- `59edef851007a925d3ea215cc7d1ff658c1f33d7` — `docs: define P21-D review decision freshness gate`

### R1 Correction Commit

- `0f2d15f2d5c282e3a0e5f5c47a884811cbaf9f26` — `docs: correct P21-D automation and human escalation design`

### Core Conclusion

- Default flow is automated disposition.
- Human involvement is exception-based.
- Reviewer verdict is not human decision.
- AUTO_CONTINUE / AUTO_REWORK are not Git-write authorization.
- P21-D remains split into B / C / D / E.

---

## P21-D-B Automated Review Disposition Gate

### Gate

- P21-D-B-Codex: Closed / Pass
- P21-D-B-Mimocode: Closed / Pass
- P21-D-B overall: Closed / Pass

### Key Commits

- `60c279dd9142d22aebe88a3d78268eab73627012` — `backend: add automated review disposition gate`
- `42431cda4e003e5e45e18e000e78d6fa755d672c` — `test: lock automated review disposition gate contracts`

### Capability Record

```text
exact persisted P21-C review message
→ public review-result fingerprint revalidation
→ deterministic disposition
→ AUTO_CONTINUE / AUTO_REWORK / ESCALATE_TO_HUMAN
→ append-only ProjectDirectorMessage
```

### Boundary Record

- Does not consume disposition.
- Does not start continuation.
- Does not start rework.
- Does not create human package.
- Does not record human decision.
- Does not write files.
- Does not perform Git write.

---

## P21-D-C1 Atomic Disposition Consumption Preflight

### Gate

- P21-D-C1-Codex: Closed / Pass
- P21-D-C1-Mimocode: Closed / Pass
- P21-D-C1 overall: Closed / Pass

### Key Commits

- `b77540cbdf2338c3f4fda90ad89b41dbd8bcc856` — `backend: add disposition consumption preflight guard`
- `3afeddbf25824a8d2f3efec305cd603da60631b1` — `backend: make disposition preflight replay guard atomic`
- `033030616416b0084824a14078e6978b5b9a77d0` — `test: lock atomic disposition consumption preflight`
- `6d2580bc3aaba39a3115666207788cb2bd7ccec2` — `test: harden atomic disposition preflight evidence`

### Capability Record

- BEGIN IMMEDIATE before evidence read.
- Exact disposition validation.
- Review fingerprint revalidation.
- Source evidence binding.
- Full paginated replay detection.
- Append-only preflight evidence.
- Concurrent duplicate prevention.

Preflight is not consumption execution.

---

## P21-D-C2 Fresh Disposition Consumption

### Gate

- P21-D-C2-Codex: Closed / Pass
- P21-D-C2-Mimocode: Closed / Pass
- P21-D-C2 overall: Closed / Pass

### Key Commits

- `2f50a5a0aa1fab9739666463542ed643fb820eae` — `backend: add fresh disposition consumption gate`
- `09b562e4c96a6e881875726b8c3cd9590b5d49db` — `test: lock fresh disposition consumption contracts`
- `5a09d7a514e1e2d5032f40014b2342d2fc8874fc` — `test: close fresh disposition consumption gaps`

### Capability Record

- Consumes exact C1 preflight evidence.
- Revalidates disposition / review / diff / workspace freshness.
- Appends exactly one consumption record.
- AUTO_CONTINUE / AUTO_REWORK eligibility only.
- ESCALATE_TO_HUMAN remains routed to P21-D-D.

### Boundary Record

- Eligibility is not actual continuation / rework execution.
- No Task / Run / Worker creation.
- No patch apply.
- No Git write.

### P21-D-C2 Historical Contract Debt Closure

- Original baseline: `17 failed, 121 passed, 0 ERROR`.
- Final targeted contract suite: `139 passed, 0 failed, 0 ERROR`.
- Root-cause classification:
  - Fixture invalid: the historical C2 fixtures created ordinary target directories after P21-C-F adopted an exact persisted Git-base contract. Current production correctly failed closed with `base_commit_unavailable`.
  - Stale historical test: two target-freshness assertions treated uncommitted worktree edits as base drift. The current contract reads exact Git commit objects, so the tests now advance the base commit to prove the real drift behavior.
- Production repair: none. The P21-C exact-base freshness check remains strict; the C2 service was not relaxed for invalid historical evidence.
- Test evolution: C2 fixtures now initialize minimal Git repositories and persist a base commit; the suite explicitly verifies that an unavailable base commit stays fail closed.
- P21-C legacy path: preserved through `139 passed` C2 and `433 passed` P21-D-C1/C2/C3 disposition regression; automatic consumption still validates the legacy review/diff/workspace chain.
- P25-H bridge: preserved by the P25 bounded-rework suite (`226 passed`) and all P25 real-chain tests (`92 passed`); no P25 implementation, attempt limit, terminal rule, or runtime Git boundary changed.
- Caller-owned transaction, persistence-failure retry, SQLite immediate concurrency, same-session/fresh-session replay, and paginated replay contracts are covered by the passing C2 suite.
- P22 post-review regression: `95 passed`.
- P23 protected-transition regression: `61 passed`.
- P21-D-C2: Closed / Pass.
- P21-D-C2 historical contract debt: Closed / Pass.
- AI Project Director total loop remains `Partial`; this is local implementation and verification evidence awaiting independent review.

---

## P21-D-C3 Bounded Automatic Disposition Handoff

### Gate

- P21-D-C3-Codex: Closed / Pass
- P21-D-C3-Mimocode: Closed / Pass
- P21-D-C3 overall: Closed / Pass
- P21-D-C overall: Closed / Pass

### Key Commits

- `31911db1c2a8152e69838c49e8e1e4b0e21e7d6a` — `backend: add bounded disposition handoff gate`
- `d059816ef05bb93664ec2eb44d47cb660b979a4b` — `test: lock bounded disposition handoff contracts`
- `60f95b0c526cb2ac7221ac24a4cd1be55ff69faf` — `test: prove exact handoff evidence inheritance`

### Capability Record

```text
exact consumed disposition evidence
→ bounded continuation/rework handoff
→ append-only handoff message
→ exact evidence inheritance
```

### Boundary Record

- Handoff prepared only.
- Continuation not executed.
- Rework not executed.
- Rework budget remains bounded.
- No Task / Run / Worker / worktree.
- No file write.
- No patch apply.
- No Git write.

---

## P21-D-D1 Single-Source Human Escalation Package Preparation

### Production Commits

- `e32bd9beb55ddb730851efa40a01650d40ea69ba` — `backend: add human escalation package gate`
- `1143cf15bea9b330f7e8cb7f34cd3b549ea2cf59` — `backend: harden human escalation package gate`

Initial production static review found and R1 fixed:

- Public method name mismatch.
- Missing real Task / project binding.
- Incomplete exact message / action binding.
- Strict findings read before fingerprint trust.
- Incorrect `requires_confirmation` semantics.

Final public interface:

```python
prepare_human_escalation_package(
    *,
    session_id: UUID,
    source_task_id: UUID,
    source_message_id: UUID,
)
```

### Test Commits

- `d111f8a6c79056e107216e5fd6532baaf8812ce7` — `test: lock human escalation package contracts`
- `b659a50b19c6e7077194eacad5856140bb1ee016` — `test: close human escalation package evidence gaps`
- `8f531da62169ff8a7154affd199de9289f4338f1` — `test: isolate human escalation fingerprint evidence`

Test review process:

- Initial test suite had aggregate fingerprint, trust-order, false-only, replay-key and Barrier gaps.
- R1 closed trust-order, false-only, independent replay keys and Barrier contention.
- R2 isolated aggregate fingerprint evidence IDs and closed the final test-contract gap.

### Final Gate

- P21-D-D1-Codex: Closed / Pass
- P21-D-D1-Mimocode: Closed / Pass with verification note
- P21-D-D1 overall: Closed / Pass with verification note

### Final Local Verification Evidence

```text
D1 single-file targeted pytest: 166 passed
Adjacent targeted regression: 443 passed
compileall: passed
import smoke: passed
database is locked: not observed
```

Verification note: These pytest counts are Mimocode local execution evidence. The AI Project Director independently inspected origin/main, commit scope and test source. No GitHub Actions workflow run/status was available for this direct-push commit, so do not label these results as GitHub CI.

### D1 Capability Conclusion

```text
exact persisted ESCALATE_TO_HUMAN disposition
→ validate exact D-B message/action
→ reload exact P21-C review message
→ public fingerprint revalidation
→ strict evidence binding
→ deterministic aggregate evidence fingerprint
→ append one single-source human escalation package
→ wait for future structured human decision
```

Contract:

- Only ESCALATE_TO_HUMAN accepted.
- Trigger exactly `["high_review_risk"]`.
- Real Task / project binding.
- Strict single-action metadata validation.
- Findings trusted only after fingerprint success.
- Full paginated replay protection.
- BEGIN IMMEDIATE concurrency protection.
- One package under concurrent double invocation.
- High overall risk with no high finding is legal.
- Aggregate fingerprint excludes package ID and creation time.
- `requires_confirmation=true` means waiting for future structured decision.

### D1 Permanent Boundary

- Package creation is not human decision.
- `requires_confirmation` is not human approval.
- Human decision has not been recorded.
- No raw human confirmation text exists.
- No expiry / revoke exists.
- No decision consumption exists.
- No protected transition exists.
- No continuation / rework execution starts.
- No Task / Run / Worker / worktree is created.
- No file is written.
- No patch is applied.
- No product runtime Git write is authorized.

---

## P21-D-D2 Structured Human Escalation Decision Record

### Production Commit

- `9c1cdfdd60cc8440b21fe58bf18b0dfb96fd176b` — `backend: add human escalation decision record`

### Core Capability

```text
input: exact D1 human escalation package
accepts structured action only:
  APPROVE_CONTINUE
  REQUEST_REWORK
  REJECT
records append-only ProjectDirectorMessage
actor_type=human
does not save raw human confirmation text
does not create ApprovalRequest
does not create legacy ApprovalDecision
does not consume decision
does not execute transition
```

### Decision Confirmation Fingerprint

```text
canonical JSON
sorted keys
compact separators (",",":")
UTF-8
SHA-256
shared canonical builder between creation and public pure revalidation seam
```

### Public Seam

```python
revalidate_persisted_human_escalation_decision_fingerprint(
    *,
    session_id: UUID,
    source_task_id: UUID,
    source_decision_message_id: UUID,
    source_decision_action: dict[str, Any],
)
```

### Test Evidence

```text
D2 contract tests: 127 passed
real Barrier concurrency:
  one recorded
  one blocked
  one D2 message
three independent replay keys covered
100+ message pagination covered
```

### Gate

- P21-D-D2-Codex: Closed / Pass — static review
- P21-D-D2-Mimocode: Closed / Pass with verification note
- P21-D-D2 overall: Closed / Pass with verification note

---

## P21-D-D3 Human Decision Lifecycle — Revoke and Consumption Preflight

### Production Commit

- `c778085932ebd9d1d637817b419f5012673734dd` — `backend: add human decision lifecycle guard`

### Public Methods

```python
revoke_human_escalation_decision(
    *,
    session_id: UUID,
    source_task_id: UUID,
    source_message_id: UUID,
    actor: str,
    client_request_id: str,
)

prepare_human_escalation_decision_consumption_preflight(
    *,
    session_id: UUID,
    source_task_id: UUID,
    source_message_id: UUID,
    evaluated_at: datetime | None = None,
)
```

### Capability Record

```text
revocation status: revoked / blocked
preflight status: ready / blocked

APPROVE_CONTINUE → continuation eligible
REQUEST_REWORK → rework eligible
REJECT → terminal rejection preflight

evaluated_at >= decision_expires_at → blocked
revoked decision → blocked
already consumed decision → blocked
append-only revocation
no automatic expiry message
```

### Test Evidence

```text
D3 contract tests: 64 passed
revoke Barrier:
  one revoked
  one blocked
  one revocation
preflight Barrier:
  one ready
  one blocked
  one ready preflight
expiry equality boundary covered
pagination and malformed history fail-closed covered
```

### Gate

- P21-D-D3-Codex: Closed / Pass — static review
- P21-D-D3-Mimocode: Closed / Pass with verification note
- P21-D-D3 overall: Closed / Pass with verification note

---

## P21-D-D4 Atomic Human Decision Consumption

### Production Commit

- `0e6b3e9ecc4485a81966f683cdc6f40d602cf4b5` — `backend: add atomic human decision consumption`

### Public Methods

```python
consume_human_escalation_decision(
    *,
    session_id: UUID,
    source_task_id: UUID,
    source_message_id: UUID,
    consumed_at: datetime | None = None,
)

revalidate_persisted_human_escalation_decision_consumption_fingerprint(...)
```

### Transition Mapping

```text
APPROVE_CONTINUE → CONTINUE_GUARDRAIL
REQUEST_REWORK → BOUNDED_REWORK_GUARDRAIL
REJECT → TERMINAL_REJECTION
```

`TERMINAL_REJECTION` does not open protected transition. `CONTINUE_GUARDRAIL` and `BOUNDED_REWORK_GUARDRAIL` are guardrail eligibility only — neither actually starts continuation or rework.

### Atomicity

```text
full flow inside SQLite BEGIN IMMEDIATE
reloads D3 preflight and D2 decision
revalidates decision fingerprint
rechecks expiry, revocation, prior consumption
concurrent consumption of same decision produces exactly one D4 record
```

### Test Evidence

```text
D4 contract tests: 59 passed
real Barrier:
  one consumed
  one blocked
  one D4 consumption
no database is locked leak
```

### Gate

- P21-D-D4-Codex: Closed / Pass — static review
- P21-D-D4-Mimocode: Closed / Pass with verification note
- P21-D-D4 overall: Closed / Pass with verification note
- P21-D-D overall: Closed / Pass with verification note

---

## P21-D-E Unified Protected Transition Evidence Freshness Gate

### Production Commits

- `c4dbc26215842b6a8ac943f9057034c8bf3fdb6a` — `backend: add protected transition freshness gate`
- `9f98c8b512f23d00aa4cb0412b8d5c00ddba4bfa` — `backend: align freshness gate package confirmation`

### R1 Production Fix

Initial E shared `_exact_action()` with hardcoded `requires_confirmation=false`. But the D1 package legitimate contract is `requires_confirmation=true`. This caused the real D1→D2→D3→D4→E human chain to be incorrectly blocked.

R1 added `expected_requires_confirmation` per source type:

```text
C3 handoff: false
C2 consumption: false
D4 consumption: false
D2 decision: false
D1 package: true
```

### Public Methods

```python
prepare_protected_transition_evidence_freshness_gate(
    *,
    session_id: UUID,
    source_task_id: UUID,
    source_message_id: UUID,
    validated_at: datetime | None = None,
)

revalidate_persisted_protected_transition_freshness_fingerprint(...)
```

### Dual Path

Automatic:

```text
P21-C review
→ D-B disposition
→ C1 preflight
→ C2 consumption
→ C3 handoff
→ E freshness
```

Human:

```text
D1 package
→ D2 decision
→ D3 preflight
→ D4 consumption
→ E freshness
```

### Automatic Mapping

```text
AUTO_CONTINUE → CONTINUE_GUARDRAIL
AUTO_REWORK → BOUNDED_REWORK_GUARDRAIL
```

### Human Mapping

```text
APPROVE_CONTINUE → CONTINUE_GUARDRAIL
REQUEST_REWORK → BOUNDED_REWORK_GUARDRAIL
REJECT → blocked:
  terminal_rejection_has_no_protected_transition
```

### E Revalidation Scope

```text
exact source transition metadata
Task / session / project binding
P21-C review fingerprint
strict JSON / schema / semantics / evidence scope
source diff
trusted current workspace
current readonly diff
reviewed / persisted / current diff SHA equality
reviewed / persisted / current ordered scope equality
human decision expiry
post-consumption revocation
single D4 consumption
replay keys
```

### Success Contract

```text
evidence_fresh=true
gate_allows_protected_transition_guardrail=true
gate_allows_write=false
continuation_started=false
rework_started=false
```

Freshness Gate does not execute transitions.

### Test Commits

- `b7153bab4f5ba385222904ec569dd5e5a1470a1a` — `test: verify unified review decision freshness chain`
- `f4c6d17aacc8bbc9bac1084a213d4433de851a32` — `test: verify freshness confirmation and automatic path`
- `ddb5168ee772951001b31f0454f3c729159a4d32` — `test: close freshness evidence verification gaps`

### Test Review Process

Initial unified test (b7153bab):

```text
D2/D3/D4 test evidence passed independent review.
Initial E test was invalid:
  success fixture modified D1 package requires_confirmation from true to false
  no real automatic D-B→C1→C2→C3→E service chain
  automatic Barrier claim did not match actual test
```

E test R1 (f4c6d17a):

```text
removed D1 success fixture tampering
used untouched D1 package
added real D-B→C1→C2→C3→E automatic chain
added human and automatic threading.Barrier concurrency tests
```

Remaining gaps at R1:

```text
five confirmation errors not all directly verified at E layer
three replay keys not truly independent
automatic path full evidence binding assertions incomplete
```

E test R2 (ddb5168e):

```text
five confirmation errors all directly blocked at E layer
three replay keys each match only one key
prior E passes Domain and public fingerprint seam
automatic path补齐 review fingerprint, three diff SHA, three ordered scope, workspace binding
```

### Final Local Verification Evidence

```text
E targeted: 112 passed
D2/D3/D4/E unified: 362 passed
Adjacent regression: 959 passed
compileall: passed
import smoke: passed
database is locked: not observed
```

Verification note: These pytest counts are Mimocode local execution evidence. The AI Project Director independently inspected origin/main, commit scope and test source. No GitHub Actions workflow run/status was available for these direct-push commits, so do not label these results as GitHub CI.

### Confirmation Strict Negative Verification

All five confirmation errors directly verified at E layer:

```text
D1 package requires_confirmation=false
  → source_human_package_invalid
  → E message count=0

D2 decision requires_confirmation=true
  → source_human_decision_invalid
  → E message count=0

D4 consumption requires_confirmation=true
  → source_human_consumption_invalid
  → E message count=0

C2 consumption requires_confirmation=true
  → source_automatic_consumption_invalid
  → E message count=0

C3 handoff requires_confirmation=true
  → source_automatic_handoff_invalid
  → E message count=0
```

### Independent Replay Key Verification

Three truly independent tests:

```text
test_replay_by_transition_message_id_only:
  prior.source_transition_message_id == current
  prior.source_transition_record_id != current
  prior.source_review_message_id != current
  → blocked, prior_freshness_validation_detected=true

test_replay_by_transition_record_id_only:
  prior.source_transition_message_id != current
  prior.source_transition_record_id == current
  prior.source_review_message_id != current
  → blocked, prior_freshness_validation_detected=true

test_replay_by_review_message_id_only:
  prior.source_transition_message_id != current
  prior.source_transition_record_id != current
  prior.source_review_message_id == current
  → blocked, prior_freshness_validation_detected=true
```

Each prior E constructed via public `revalidate_persisted_protected_transition_freshness_fingerprint` seam, passes Domain reconstruction and fingerprint revalidation.

### Automatic Path Source Binding

```text
source_transition_message_id == C3 message.id
source_transition_record_id == C3 handoff_id
source_handoff_message_id == C3 message.id
source_disposition_consumption_message_id == C2 message.id
disposition_consumption_id == C2 consumption_id
source_disposition_message_id == D-B message.id
source_review_message_id == P21-C review message.id
source_diff_message_id == P21-C bound diff message.id
review_result_fingerprint matches revalidated
reviewed_diff_sha256 == persisted_source_diff_sha256 == current_diff_sha256
reviewed_scope_paths == persisted_source_scope_paths == current_scope_paths
workspace_path == trusted workspace
workspace_path_within_root == true
```

### Gate

- P21-D-E-Codex: Closed / Pass — static review
- P21-D-E-Mimocode: Closed / Pass with verification note
- P21-D-E overall: Closed / Pass with verification note

---

## P21-D Stage Design — Automated Review Disposition, Human Escalation & Evidence Freshness Gate

### Core Product Principle

P21-D is automation-first, not approval-first.

The default path is not:

```text
every review result → human decision
```

The default path must be:

```text
persisted validated review result
→ automated disposition
→ AUTO_CONTINUE / AUTO_REWORK / ESCALATE_TO_HUMAN
```

Human involvement is exception-based.

Human responsibility:

- Large direction decisions
- Major risk decisions
- Scope changes beyond confirmed boundaries
- Problems that cannot auto-converge
- Human-controlled stage / milestone checkpoints
- Future protected transitions

Human is not responsible for:

- Every small task
- Every ordinary reviewer result
- Every low-risk change
- Every ordinary automatic rework

### Current Starting State

P21-C is Closed / Pass with note.

Current available capability:

```text
controlled sandbox candidate diff
→ persisted readonly review handoff
→ execution preflight
→ explicit user confirmation for reviewer execution
→ persisted trusted reviewer executor
→ persisted trusted workspace
→ current workspace revalidation
→ real Codex / Claude Code reviewer execution
→ strict output validation
→ review result persistence
```

P21-C's explicit user confirmation only authorizes readonly reviewer execution. It is not a human decision after review result. It is not Git write authorization.

### Current Gap

Persisted review result already contains and binds:

- source task
- source preflight message
- source diff message
- reviewer executor
- source diff SHA256
- review prompt SHA256
- review scope paths
- review output schema
- strict validation result
- verdict
- risk level
- findings
- recommended next step

Current system does not have:

- automated disposition after review result
- disposition binding to exact review result
- review result fingerprint binding
- bounded automatic rework orchestration
- escalation trigger definition
- human escalation package aggregation
- decision expiry / revoke / replay protection
- decision consumption gate
- current diff freshness revalidation after review
- stale review evidence invalidation
- future pre-write guardrail eligibility result

### Three Dispositions

#### AUTO_CONTINUE

Current review result has passed strict validation and no escalation trigger is present.

System may continue automatic progression within confirmed project scope and governance boundaries.

Does not require human confirmation.

Does not authorize Git write.

#### AUTO_REWORK

Current result requires modification, but remains within confirmed scope and is an ordinary rework that can be handled automatically.

System enters bounded automatic rework path.

Does not by default require human confirmation.

Does not authorize unlimited retry.

Does not mean P21-D-A currently implements automatic rework.

#### ESCALATE_TO_HUMAN

Only when a clear escalation trigger is hit, an escalation package is built for human decision.

Must not convert every reviewer result into human approval by default.

### Reviewer Verdict Default Disposition Semantics

`no_blocking_findings`:

- Default: AUTO_CONTINUE
- Unless an escalation trigger is simultaneously present.

`non_blocking_findings`:

- Default: record findings → AUTO_CONTINUE
- Future governance policy may promote specific findings to AUTO_REWORK.
- Must not default to human confirmation only because non-blocking findings exist.

`changes_required`:

- Default: AUTO_REWORK
- As long as:
  - Still within confirmed scope
  - No high-risk escalation trigger present
  - Bounded rework budget not exhausted
  - No unresolvable non-convergence state
- Must not default to human confirmation only because of a first `changes_required`.

### Escalation Triggers

The following conceptual triggers require human escalation when present:

1. **Confirmed scope / plan expansion**: Requires expanding confirmed scope or changing large direction.

2. **High-risk or protected-surface change**: Involves explicitly high-risk areas or protected operations.

3. **Bounded rework budget exhausted**: Automatic rework reaches upper limit and still cannot pass.

4. **Repeated non-convergence**: Multiple modification-review cycles cannot converge.

5. **Trusted reviewer conflict**: If future same-target has multiple trusted reviewer results with conflicting key judgments.

6. **Human-controlled stage or milestone checkpoint**: Only stages or milestones explicitly marked by governance policy as human-controlled. Must not treat ordinary task completion as milestone approval.

7. **Protected future transition**: For example future entry into:
   - product runtime Git write
   - deployment
   - destructive operation
   - database migration
   - permission / security critical change

8. **Explicit governance policy escalation**: Governance policy explicitly requires human involvement.

### Non-Triggers

The following conditions in isolation must not default to human escalation:

- One ordinary task completing
- One reviewer result being produced
- `no_blocking_findings`
- `non_blocking_findings`
- First `changes_required`
- Ordinary low-risk code changes
- Ordinary naming / comment / small exception handling issues
- Automatic rework within bounded rework budget

### P21-D Final Goal

```text
persisted validated P21-C review result
→ deterministic automated disposition
→ AUTO_CONTINUE / AUTO_REWORK / ESCALATE_TO_HUMAN

AUTO_CONTINUE:
→ persist append-only disposition evidence
→ eligible for automatic continuation inside confirmed scope

AUTO_REWORK:
→ persist append-only disposition evidence
→ eligible for bounded automatic rework orchestration

ESCALATE_TO_HUMAN:
→ build persisted escalation package
→ human decision
→ decision binding / expiry / revoke / replay protection

Before entering any future protected transition:
→ reload relevant evidence
→ current trusted workspace revalidation
→ current readonly diff regeneration
→ evidence freshness comparison
→ stale evidence rejection
→ protected-transition eligibility
```

Success can still only mean:

- `gate_allows_protected_transition_guardrail = true`
- `gate_allows_write = false`

It must not mean: Git write authorized.

### P21-D Stage Split

- **P21-D-A**: Stage Contract Design
- **P21-D-B**: Automated Review Disposition Gate
- **P21-D-C**: Bounded Automatic Disposition Consumption
- **P21-D-D**: Human Escalation Decision Record
- **P21-D-E**: Protected Transition Evidence Freshness Gate

P21-D-A (current task) only locks the contract.

P21-D-B / P21-D-C / P21-D-D / P21-D-E must remain Not started.

### P21-D-B Contract — Automated Review Disposition Gate

1. Input must be an already-persisted P21-C readonly review execution message.

2. Client must not provide or override:
   - reviewer executor
   - workspace path
   - source diff SHA
   - review prompt SHA
   - review output
   - verdict
   - findings

   These values must be read from persisted trusted evidence.

3. P21-D-B computes and persists exactly one of:
   - `AUTO_CONTINUE`
   - `AUTO_REWORK`
   - `ESCALATE_TO_HUMAN`

   based on reviewer verdict and escalation trigger evaluation.

4. P21-D-B itself does not start Worker, does not execute rework, does not require human.

5. Reviewer verdict is never human decision.

6. Automated disposition is never Git write authorization.

7. Disposition record must bind at minimum:
   - `session_id`
   - `source_task_id`
   - `source_review_message_id`
   - `source_preflight_message_id`
   - `source_diff_message_id`
   - `requested_reviewer_executor`
   - `source_diff_sha256`
   - `review_prompt_sha256`
   - `review_scope_paths`
   - `review_output_schema_version`
   - review result fingerprint
   - disposition id
   - disposition type (`AUTO_CONTINUE` / `AUTO_REWORK` / `ESCALATE_TO_HUMAN`)
   - escalation trigger evaluation result (if applicable)
   - actor
   - client request id
   - disposition `created_at`

8. Use `ProjectDirectorMessage` append-only audit.

9. Do not add new DB table.

10. Do not create migration.

11. Do not use legacy P4-F `AgentMessage` as P21-D main persistence chain. Legacy P4-F serves only as expiry / revoke / replay / fingerprint / evidence binding mechanism reference.

12. P21-D-B must not create:
    - Task
    - Run
    - Worker
    - worktree
    - Git write
    - PR
    - merge
    - CI trigger

### P21-D-C Contract — Bounded Automatic Disposition Consumption

1. Consumes `AUTO_CONTINUE` and `AUTO_REWORK` dispositions.

2. `AUTO_CONTINUE`: ordinary flow may proceed automatically within confirmed scope.

3. `AUTO_REWORK`: enters bounded automatic rework path. Must not retry infinitely. Must stop and escalate when escalation trigger is hit.

4. P21-D-C does not handle `ESCALATE_TO_HUMAN` dispositions. Those are routed to P21-D-D.

5. Consumption ordering:

```text
persisted disposition
→ validate disposition message / type / source binding
→ validate disposition active
→ reload exact P21-C review result
→ validate review result fingerprint
→ validate strict_json_valid
→ validate schema_valid
→ validate semantics_valid
→ validate evidence_scope_valid
→ validate review_status = reviewed
→ validate verdict eligibility
→ reload exact source diff
→ validate source diff SHA256
→ validate ordered review scope paths
→ validate no-write safety flags
→ revalidate trusted current workspace
→ regenerate current readonly diff
→ compare current diff SHA256 with reviewed diff SHA256
→ compare current diff scope with reviewed scope
→ persist append-only consumption evidence
→ return continuation / rework eligibility
```

6. Any critical evidence change must set `ready = false` and produce a stable blocked reason.

7. Conceptual blocked reasons:
   - `disposition_missing`
   - `disposition_type_escalation_unhandled`
   - `review_result_missing`
   - `review_result_not_validated`
   - `review_result_fingerprint_mismatch`
   - `source_diff_missing`
   - `source_diff_sha256_mismatch`
   - `review_scope_paths_mismatch`
   - `trusted_workspace_invalid`
   - `current_diff_mismatch`
   - `review_evidence_stale`
   - `bounded_rework_budget_exhausted`
   - `rework_non_convergence`

8. Do not define HTTP status mapping in this design phase.

### P21-D-D Contract — Human Escalation Decision Record

1. Only dispositions of type `ESCALATE_TO_HUMAN` may build a human escalation package.

2. Human escalation package may aggregate one or multiple related task / review results.

3. Future human escalation objects may target:
   - one high-risk task
   - one stage
   - one milestone
   - a group of related changes
   - an unresolvable rework cycle

4. Human escalation package must conceptually bind at minimum:
   - escalation trigger
   - escalation scope
   - related task ids
   - related review message ids
   - unresolved blocking findings
   - risk summary
   - aggregate evidence fingerprint
   - proposed human decision scope

5. Human decision record must bind at minimum:
   - escalation package id
   - decision id
   - decision action
   - actor
   - client request id
   - decision `created_at`
   - decision `expires_at`
   - decision confirmation fingerprint

6. Human decision is never Git write authorization.

7. Do not persist raw human confirmation text.

8. Use `ProjectDirectorMessage` append-only audit.

9. Do not add new DB table.

10. Do not create migration.

11. P21-D-D must not create:
    - Task
    - Run
    - Worker
    - worktree
    - Git write
    - PR
    - merge
    - CI trigger

### P21-D-E Contract — Protected Transition Evidence Freshness Gate

Before entering any sensitive transition in the future, revalidates all evidence.

Includes but is not limited to:

- exact review evidence binding
- aggregate escalation evidence binding
- decision expiry
- decision revoke
- replay / reuse protection
- current workspace validity
- current diff freshness
- stale evidence rejection

P21-D-E still does not execute Git write.

Consumption ordering:

```text
persisted decision + disposition evidence
→ reload all relevant evidence
→ validate decision active / not expired / not revoked / not previously consumed
→ validate review result fingerprint
→ validate strict_json_valid / schema_valid / semantics_valid / evidence_scope_valid
→ revalidate trusted current workspace
→ regenerate current readonly diff
→ compare current diff SHA256 with reviewed diff SHA256
→ compare current diff scope with reviewed scope
→ persist append-only freshness validation evidence
→ return protected-transition eligibility
```

Success can only mean:

- `gate_allows_protected_transition_guardrail = true`
- `gate_allows_write = false`

### Append-Only Consumption Rule

- Must not modify old P21-C review message.
- Must not overwrite old disposition message.
- Must not overwrite old human escalation decision message.
- Successful consumption must add append-only evidence.
- Same decision must not be reused for multiple subsequent safety checks.

### Permanent Safety Boundary

- Automatic patch apply: Forbidden
- Product runtime git add: Forbidden
- Product runtime git commit: Forbidden
- Product runtime git push: Forbidden
- Automatic PR: Forbidden
- Automatic merge: Forbidden
- Branch deletion: Forbidden
- Reset / checkout / switch / stash / rebase / tag: Forbidden
- Automatic CI trigger: Forbidden

Reviewer verdict is not human approval.

Automated disposition is not Git write authorization.

Human escalation decision is not Git write authorization.

AUTO_CONTINUE does not authorize Git write.

AUTO_REWORK does not authorize Git write.

P21-D Pass does not open product runtime Git write.

Decision consumption is not transition execution.

APPROVE_CONTINUE does not authorize Git write.

### Stage Status

- P21-C: Closed / Pass with note
- P21-D-A: Closed / Pass
- P21-D-B: Closed / Pass
- P21-D-C1: Closed / Pass
- P21-D-C2: Closed / Pass
- P21-D-C3: Closed / Pass
- P21-D-C overall: Closed / Pass
- P21-D-D1: Closed / Pass with verification note
- P21-D-D2: Closed / Pass with verification note
- P21-D-D3: Closed / Pass with verification note
- P21-D-D4: Closed / Pass with verification note
- P21-D-D overall: Closed / Pass with verification note
- P21-D-E: Closed / Pass with verification note
- P21-D overall: Closed / Pass with verification note
- Product runtime Git write: Forbidden
- AI Project Director total loop: Partial

### Future Stage Boundary

P21-D is now Closed / Pass. This does not authorize product runtime Git write. The next stage must be decided by AI Project Director after re-inspecting the latest origin/main. Do not define P22. Do not name a future real Git write implementation stage. Do not claim Git write is now authorized.

---

## P22 Post-Review Automation Orchestrator

### Gate

- P22-A initial design: Closed / Pass
- P22-A-R1 replay design hardening: Closed / Pass
- P22-B production implementation: Closed / Pass after R1
- P22-C verification: Closed / Pass with verification note
- P22 overall: Closed / Pass with verification note
- Product runtime Git write: Forbidden
- AI Project Director total loop: Partial

### Key Commits

- `efba3b475bbaee5c811ce4443ff2591e01f438ca` — `docs: design p22 post-review automation orchestrator`
- `1f57734cf5351567dc4e1205f887de8a013c5cd9` — `docs: harden p22 orchestrator replay design`
- `3939285dd21251baece9e8901fa6335b7b961d63` — `backend: add post-review automation orchestrator`
- `8662de039b7adc85bd01b86ce8da3f6418d948a7` — `test: verify post-review automation orchestrator`
- `3a22170233fc5354e59aef3118fd8f7af42fa2d8` — `backend: fix p22 disposition replay evidence`
- `02cafc5a738392a52080b753f5df889612db36e8` — `test: reverify p22 disposition replay fix`
- `9aeae7bd467018862e7cce75b9ed7b94a63809dd` — `test: repair p22 freshness auto-chain fixture`

### Implemented Capability

Persisted P21-C readonly review result → P22 unified post-review orchestration entry point → D-B deterministic disposition.

Automatic path:

```text
AUTO_CONTINUE / AUTO_REWORK
→ D-B
→ C1 atomic consumption preflight
→ C2 disposition consumption
→ C3 bounded handoff
→ E freshness gate
→ ready_for_future_transition
```

Human escalation path:

```text
ESCALATE_TO_HUMAN
→ D-B
→ D1 human escalation package
→ waiting_for_human
→ stop
```

`ready_for_future_transition` is guardrail readiness for a future transition. It does not execute continuation. It does not execute rework. `waiting_for_human` does not mean a human decision has been recorded. P22 has no real transition executor.

### Replay and Evidence Contract

- read-before-invoke
- full paginated scan
- strict source / session / task / message / action / schema binding
- only valid evidence may be adopted
- corrupted, missing, or conflicting evidence fails closed
- D-B uses SQLite `BEGIN IMMEDIATE` to protect replay / create
- P22 summary uses append-only `ProjectDirectorMessage`
- sequential replay returns existing evidence
- concurrent orchestration ultimately accepts only the single valid chain and summary
- blocked path does not call subsequent steps

The multi-step chain does not run inside a single global database transaction.

### P22-BUG-001 Record

Initial D-B persisted action omitted `blocked_reasons`. P22 reconstructed all D-B DomainModel fields with `action.get(field_name)`. The missing field became `None` and failed strict Pydantic reconstruction. Fresh successful orchestration therefore could not persist a valid P22 summary.

Fix (`3a221702`): `_disposition_action` now persists `"blocked_reasons": list(result.blocked_reasons)`. Computed disposition persists `[]`.

This is not a fingerprint algorithm change.

### Test Fixture Regression Record

After the production fix, seven freshness adjacent tests initially returned `review_disposition_replay_conflict`.

Root cause: freshness test helper manually pre-seeded an old incomplete D-B action, then invoked the real D-B service. The old action lacked `blocked_reasons` and failed strict replay reconstruction.

Fix (`9aeae7bd`): removed manual D-B disposition pre-seeding and allowed the real D-B service to create the disposition evidence.

This was a test fixture / production contract mismatch. No fingerprint algorithm was changed. No replay validation was relaxed. No production code was modified. No xfail, xpass, or skip was used.

### Verification Evidence

```text
P22 core verification:
92 passed
0 failed
0 xfailed
0 xpassed

D-B + P22 combined:
183 passed
0 failed
0 xfailed
0 xpassed

P22-C-R2 original failing nodes:
7 passed

Full E freshness:
112 passed

Adjacent D-B/C1/C2/C3/D1/E regression:
710 passed
0 failed
0 xfailed
0 xpassed

Final P22 core rerun:
183 passed
0 failed
0 xfailed
0 xpassed
```

One Pydantic deprecation warning was observed (accessing `model_fields` on instance). This is not a test failure.

Verification note: These pytest counts are Mimocode local execution evidence. The AI Project Director independently inspected origin/main, commit scope, production fix, test fixture correction, and test source. No GitHub Actions workflow run/status was available for the direct-push commits. These results must not be labeled as GitHub CI.

### Permanent Boundary Record

```text
continuation_started = false
rework_started = false
human_decision_recorded = false
task_created = false
run_created = false
worker_started = false
worktree_created = false
main_project_file_written = false
sandbox_file_written = false
manifest_file_written = false
diff_file_written = false
patch_applied = false
git_write_performed = false
gate_allows_write = false
product_runtime_git_write_allowed = false
ai_project_director_total_loop = Partial
```

No new API. No frontend. No DB migration. No Task / Run / Worker. No real continuation. No real rework. No automatic patch apply. No product runtime git add / commit / push. No PR / merge / branch mutation. No automatic CI trigger.

### Final Stage Status

```text
P22-A: Closed / Pass
P22-B: Closed / Pass
P22-C: Closed / Pass with verification note
P22 overall: Closed / Pass with verification note

AUTO_CONTINUE real execution: Not started
AUTO_REWORK real execution: Not started
Human decision recording in P22: Not started
Product runtime Git write: Forbidden
AI Project Director total loop: Partial
```

### Future Boundary

P22 closure does not authorize actual continuation, actual rework, patch application, Task/Run/Worker creation, or Git write.

The next stage must be selected by the AI Project Director after independently re-inspecting the latest origin/main.

## P25 Final Bounded Rework Closure

### Implemented Scope

P25 now closes the persisted bounded rework loop for attempt indexes `0`, `1`, and `2` only. P25-F records an explicit inherited candidate state for a successful no-write retry, and P25-G reconstructs it only when the source P25-G manifest, exact business inventory, and exact-base unified diff all still match the source candidate diff SHA.

The lifecycle closeout is atomic for the source Task, exact Run, and append-only closure message:

```text
CONVERGED
Task RUNNING -> COMPLETED
Run RUNNING -> SUCCEEDED

NEXT_ATTEMPT_ELIGIBLE
Task RUNNING -> FAILED
Run RUNNING -> FAILED / VERIFICATION_FAILED

ESCALATE_TO_HUMAN
Task RUNNING -> FAILED -> WAITING_HUMAN
Run RUNNING -> FAILED
```

### Bounded Attempt Contract

```text
attempt limit = 3
legal attempt indexes = 0, 1, 2
attempt 3 = forbidden
```

- P23 is the only retry path from a failed attempt to the next exact Run.
- Same-session and fresh-session replay reuse persisted evidence and do not re-call the bounded executor or readonly reviewer.
- Every attempt retains distinct P23, package, reservation, claim, outcome, P25-G manifest/diff, P25-H review evidence, P22 summary, decision, and lifecycle closure identities.
- Terminal `empty_diff`, `unchanged_diff`, repeated review semantic fingerprint, repeated canonical blocking findings, attempt-limit exhaustion, and high-review-risk paths each leave no Run in `RUNNING` and create at most one terminal escalation package.

### Verification Evidence

```text
P25 lifecycle/final/terminal real chain: 13 passed
P25 package/reservation real chain: 9 passed
P25 all real-chain: 92 passed
P25 bounded rework suite: 226 passed
P25 dynamic suites: 95 passed
P23 adjacent state/concurrency regression: 61 passed
compileall app tests: passed

P21-D-C2 historical contract debt: Closed / Pass
current verification: 139 passed, 0 failed, 0 ERROR
```

### Permanent Boundaries

```text
product_runtime_git_write_allowed = false
product_runtime_git_add = false
product_runtime_git_commit = false
product_runtime_git_push = false
real_provider_call = false
native_process_start = false
generic Worker call = false in P25 real-chain coverage
```

### Final Stage Status

```text
P25-B package: Closed / Pass
P25-D reservation: Closed / Pass
P25-E invocation Claim: Closed / Pass
P25-F invocation Outcome: Closed / Pass
P25-G candidate diff: Closed / Pass
P25-H review reentry: Closed / Pass
P25-I convergence: Closed / Pass
P25 attempt lifecycle closure: Closed / Pass
P25 attempt 1 real bounded loop: Closed / Pass
P25 terminal boundaries: Closed / Pass
P25 overall: Closed / Pass

AI Project Director total loop: Partial
```

This records implementation and local verification evidence only. The independent final Gate remains outside this ledger update.

---

## P23 Protected Transition Execution and Exact Worker Invocation

### Gate

- P23-A contract design: Closed / Pass
- P23-B dispatch intent: Closed / Pass
- P23-C consumption preflight: Closed / Pass
- P23-D1 atomic consumption: Closed / Pass
- P23-D2-A exact reserved Worker seam: Closed / Pass
- P23-D2-B1 Worker start reservation: Closed / Pass
- P23-D2-B2 Worker invocation and durable outcome: Closed / Pass
- P23-D3 auto-advance coordinator: Closed / Pass
- P23-E verification: Closed / Pass with verification note
- P23 overall: Closed / Pass with verification note
- Product runtime Git write: Forbidden
- AI Project Director total loop: Partial

### Key Commits

- `8314d9eba91db3669399ed22b005101a7d46bbec` — `docs: design p23 protected transition dispatch`
- `703ddd643a4dc9eb94d921f1d0068bffe5debbb1` — `backend: add protected transition dispatch intent`
- `a25ef6b6dbec29cb4ee426e972e335f4f4e22b85` — `backend: add protected transition consumption preflight`
- `2909421eaaa017280882e09857dbbc205dc9329b` — `backend: consume protected transition dispatch atomically`
- `6684c4c8e6391bf4500bfabecd5f1b23b4b76bea` — `backend: defer p23 d1 events until commit`
- `b5febcb73976e051f05c2da3ccc29554b806c7ce` — `backend: add exact reserved run worker seam`
- `96681815a9635cd07bb7d2fe8c28519a2f8938c9` — `backend: reserve protected transition worker start`
- `ccc66b1f017d9f131de31c9418fc97281d0e8836` — `backend: harden p23 reservation lineage uniqueness`
- `cc58376b8fc9285fe857dbe5cc7190c09984fed9` — `backend: invoke reserved protected transition worker`
- `1ca3e5f5fc0cf66eedb6d3c93780a973ae0e0ab2` — `backend: bind p23 worker outcome to reservation`
- `84b545b5c5e12ec03130ee23d7d914ace9731118` — `backend: add protected transition auto advance coordinator`
- `cef78273e25fcbed25afa3c5e9ed6272dd5855d9` — `backend: resume p23 auto advance from persisted chain`
- `425b024399c8fa4873f62dffedb7a25b9dab848d` — `backend: fix p23 d3 p22 summary identity`
- `259b9223375cff8bddead15f1becafdf40dd3e75` — `backend: close p23 d1 post-commit transaction`
- `d2c271af3dd0061576ba5095317ee85f1e036e3c` — `test: close p23 d3 replay and recovery gaps`
- `42d32527981001bfe115c1145a04788522184e5e` — `test: verify p23 concurrency and full regression`
- `3ebe3594383a7bdd583fb0934617c5588c9b9165` — `test: tighten p23 concurrency and full suite evidence`
- `02433a81d232c00c8bbac0ba4732d10e2a53608a` — `test: align worker result guardrails with p23 snapshot`

### Implemented Capability

Automatic path:

```text
persisted P21-C review
→ P22 ready_for_future_transition
→ P23-B dispatch intent
→ P23-C current consumption preflight
→ P23-D1 atomic source Task claim and exact Run creation
→ P23-D2-B1 exact Worker start reservation
→ P23-D2-B2 durable invocation claim
→ TaskWorker.run_reserved_once(exact task_id, exact run_id)
→ durable returned / raised / not_invoked outcome
→ D3 terminal result
```

AUTO_CONTINUE:

```text
source Task continues through its exact reserved Run
continuation_started = true only in durable Worker outcome
```

AUTO_REWORK:

```text
same source Task enters bounded rework
rework_started = true only in durable Worker outcome
```

P23 does not create new business Tasks. P23 does not use TaskRouter to select other Tasks. D1 creates and binds one exact Run. Worker can only consume the B1-bound exact Task/Run. B2 claim is persisted before Worker call. Outcome is persisted after Worker returns, raises, or final current check blocks.

### Transaction and Replay Contract

- P23-B / P23-C / D1 / B1 / B2 all use persisted append-only evidence.
- D1 Task mutation + Run creation + D1 message belong to the same atomic transaction.
- D1 events are published only after commit.
- B1 reservation binds exact D1 message, Task, Run, fingerprint, and token.
- B2 durable claim is committed before Worker call.
- B2 outcome binds exact claim, reservation, and Run.
- D3 first checks persisted evidence, then decides whether to call the creation entry point.
- Complete outcome replay does not re-run current checks.
- Complete outcome replay does not re-call Worker.
- Existing claim without outcome returns `recovery_required`; Worker is not retried.

### Concurrency Contract

D1 same-source concurrency:

```text
one D1 message
one Run
one first-created
one persisted replay
```

B1 same-source concurrency:

```text
one reservation message
identical reservation ID / token / fingerprint
one first-created
one persisted replay
```

B2 same-source concurrency:

```text
one claim
one outcome
Worker called exactly once
competing call returns recovery/in-progress when claim exists but outcome is not yet complete
```

D3 same-source concurrency:

```text
complete P22/P23 evidence each exactly one
one Run
Worker called exactly once
completed replay returns original full evidence IDs
```

Completed outcome three-thread replay:

```text
all reuse original evidence
Worker not called
```

### Defect Records

#### P23-BUG-002

Problem: D1 published Task/Run events before transaction commit.

Risk: External observers could see non-durable-committed state.

Fix: `6684c4c8` — events deferred until after D1 commit.

#### P23-BUG-003

Problem: B1 persisted reservation lineage uniqueness validation was insufficient.

Fix: `ccc66b1f` — strengthened same-Run / same-D1 / same-reservation unique binding and conflict rejection.

#### P23-BUG-004

Problem: B2 claim/outcome binding to B1 reservation was insufficient.

Fix: `1ca3e5f5` — claim/outcome strictly bind reservation message, reservation identity, and Run.

#### P23-BUG-005

Problem: When a complete durable outcome existed, D3 replay could still pass through current-sensitive prepare/revalidation, causing terminal Task/Run or existing AgentSession to block legitimate replay.

Fix: `cef78273` — D3 prioritizes recovery from persisted P23-C, D1, B1, and B2 outcome to reconstruct the full chain.

#### P23-BUG-006

Problem: D3 incorrectly required P22 summary message ID to equal P22 `orchestration_id`.

Root cause: These are different identities.

Fix: `425b0243` — removed incorrect equality; downstream lineage uses exact persisted `p22.message.id`.

#### P23-BUG-007

Problem: D1 post-commit Task/Run lookup triggered SQLAlchemy autobegin; the shared Session was not restored to idle, and subsequent B1 `Session.begin()` raised `InvalidRequestError`.

Fix: `259b9223` — D1 post-commit event lookup closes the read-only autobegin transaction in a `finally` block.

### Verification Evidence

```text
D3 behavioral/replay suite:
12 passed

P23 D1-B2 adjacent regression:
95 passed

P22 adjacent regression:
92 passed

P23 concurrency suite:
5 passed

P23 concurrency stability:
3 rounds × 5 passed

P23 targeted total:
112 passed

WorkerRunResult guardrail:
8 passed

Correct-cwd full suite:
4194 passed
3 failed
```

The three failures are:

1. external executor module boundary contract debt
2. Project Director run evidence replay integration debt
3. Project Director Worker run evidence integration debt

All three tests fail on the P22 final baseline `54af386` with the same core assertions. P23 baseline-relative regression count = 0.

### Verification Note

All pytest counts are Mimocode local execution evidence.

The AI Project Director independently verified:

- latest origin/main
- commit scope
- production/test boundary
- D3 behavioral/replay test source
- concurrency tests with independent Session and shared Worker counter
- WorkerRunResult guardrail backfill
- P22 baseline comparison using the same test and code baseline

No GitHub Actions workflow run/status was available. These results must not be labeled as GitHub CI.

### Permanent Boundary Record

```text
new_business_task_created = false
source_task_only = true
exact_run_created = true
worker_invocation_claimed_before_call = true
worker_invocation_at_most_once = true
outcome_append_only = true

automatic_patch_apply = false
product_runtime_git_add = false
product_runtime_git_commit = false
product_runtime_git_push = false
product_runtime_pr_open = false
product_runtime_merge = false
product_runtime_git_write_allowed = false

AI Project Director total loop = Partial
```

P23 allows source Task status to enter `running`. P23 allows creating an exact Run. P23 allows calling the exact reserved Worker seam through B2. This does not equal authorization for product runtime Git write. P23 verification did not start a real provider, native executor, or network. Tests did not perform real workspace / file / patch writes.

### Final Stage Status

```text
P23-A: Closed / Pass
P23-B: Closed / Pass
P23-C: Closed / Pass
P23-D1: Closed / Pass
P23-D2-A: Closed / Pass
P23-D2-B1: Closed / Pass
P23-D2-B2: Closed / Pass
P23-D3: Closed / Pass
P23-E: Closed / Pass with verification note
P23 overall: Closed / Pass with verification note

P23 baseline-relative regression count: 0
Known pre-P23 full-suite debt: 3 tests

Product runtime Git write: Forbidden
AI Project Director total loop: Partial
```

### Future Boundary

P23 closure does not authorize product runtime Git write, automatic patch application, git add, git commit, git push, PR creation, merge, or automatic CI triggering.

It does not close the complete AI Project Director product loop.

The next stage must be selected by the AI Project Director after independently re-inspecting the latest origin/main.
