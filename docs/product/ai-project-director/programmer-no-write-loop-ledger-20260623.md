# Programmer No-Write Loop Ledger - 2026-06-23

> This ledger is the single backfill ledger for the programmer no-write loop.
> It records P16, P17, P18, P19, and P20 evidence in one place to avoid one-ledger-per-stage documentation sprawl.
>
> 本文件是 programmer no-write loop 的统一总账，用于回填 P16/P17/P18/P19/P20 后续证据，避免每个小阶段新增单独 ledger。

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

### Current Capability After P20

P20 completes the following chain:

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
-> policy-only sandbox write preflight
-> Project Director message readback
```

Not yet available:

- Actual file modification
- Sandbox/worktree write
- Real diff application
- Targeted tests against changed code
- Reviewer reviews real diff
- Git add / commit / push / PR / merge by product runtime

### Next Step

P21 should still not open product runtime Git write.

Recommended P21: Controlled sandbox/worktree write execution may begin only as a staged no-Git capability.

Preferred P21-A: Implement sandbox/worktree write execution domain and service in `dry_run`/`fake_write` first, without actual file write.

Do not jump directly to `controlled_sandbox_write`.
Do not open product runtime Git write.
Do not open automatic commit/push/PR/merge.
