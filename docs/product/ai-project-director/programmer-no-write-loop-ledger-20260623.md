# Programmer No-Write Loop Ledger - 2026-06-23

> This ledger is the single backfill ledger for the programmer no-write loop.
> It records P16, P17, P18, P19, P20, P21-A, P21-B-A, P21-B-B, and P21-C evidence in one place to avoid one-ledger-per-stage documentation sprawl.
>
> 本文件是 programmer no-write loop 的统一总账，用于回填 P16/P17/P18/P19/P20/P21-A/P21-B-A/P21-B-B/P21-C 后续证据，避免每个小阶段新增单独 ledger。

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

## P21-D Stage Design — Post-Review Human Decision & Evidence Freshness Gate

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

- explicit human decision record after review result
- human decision binding to exact review result
- review result fingerprint binding
- decision expiry / revoke / replay protection
- decision consumption gate
- current diff freshness revalidation after review
- stale review evidence invalidation
- future pre-write guardrail eligibility result

### P21-D Final Goal

```text
persisted validated P21-C review result
→ explicit post-review human decision
→ append-only persisted decision evidence
→ decision / review / diff binding validation
→ decision freshness validation
→ current trusted workspace revalidation
→ current readonly diff regeneration
→ reviewed diff vs current diff fingerprint comparison
→ stale evidence rejection
→ future pre-write guardrail eligibility
```

Success can only mean:

- `gate_allows_prewrite_guardrail = true`
- `gate_allows_write = false`

It must not mean: Git write authorized.

### P21-D Stage Split

- **P21-D-A**: Stage Contract Design
- **P21-D-B**: Human Review Decision Record
- **P21-D-C**: Evidence Freshness Revalidation Gate

P21-D-A (current task) only locks the contract.

P21-D-B / P21-D-C must remain Not started.

### P21-D-B Contract

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

3. Legal reviewer verdict semantics:
   - `no_blocking_findings`: allows human to decide whether to enter next pre-write guardrail.
   - `non_blocking_findings`: allows human to decide after understanding findings whether to enter next pre-write guardrail.
   - `changes_required`: must not enter pre-write guardrail. Can only enter rework / reject semantics.

4. Reviewer verdict is never human decision.

5. Human decision is never Git write authorization.

6. Human decision record must bind at minimum:
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
   - decision id
   - decision action
   - actor
   - client request id
   - decision `created_at`
   - decision `expires_at`
   - decision confirmation fingerprint

7. Do not persist raw human confirmation text.

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

### P21-D-C Contract

Consumption ordering:

```text
persisted human decision
→ validate decision message / action type / source binding
→ validate decision active
→ validate not expired
→ validate not revoked
→ validate not previously consumed
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
→ persist append-only revalidation / consumption evidence
→ return pre-write guardrail eligibility
```

Any critical evidence change must set `ready = false` and produce a stable blocked reason.

Conceptual blocked reasons:

- `decision_missing`
- `decision_expired`
- `decision_revoked`
- `decision_already_consumed`
- `review_result_missing`
- `review_result_not_validated`
- `review_result_fingerprint_mismatch`
- `review_verdict_requires_changes`
- `source_diff_missing`
- `source_diff_sha256_mismatch`
- `review_scope_paths_mismatch`
- `trusted_workspace_invalid`
- `current_diff_mismatch`
- `review_evidence_stale`

Do not define HTTP status mapping in this design phase.

### Append-Only Consumption Rule

- Must not modify old P21-C review message.
- Must not overwrite old human decision message.
- Successful consumption of human decision must add append-only revalidation / consumption evidence.
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

Human decision is not Git write authorization.

P21-D Pass does not open product runtime Git write.

### Stage Status

- P21-C: Closed / Pass with note
- P21-D-A: Ready for AI Project Director review
- P21-D-B: Not started
- P21-D-C: Not started
- Product runtime Git write: Forbidden
- AI Project Director total loop: Partial

### Future Stage Boundary

Only after P21-D fully completes and passes independent Gate will AI Project Director re-inspect latest origin/main and decide whether the next stage enters future Git write design. Do not define P22. Do not name future real Git write implementation stage.
