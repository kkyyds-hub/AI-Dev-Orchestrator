# P9-REL Real Executor Launch Backend Evidence Ledger

## Ledger Scope

- Stage: `P9-REL-Ledger / Real Executor Launch Backend Evidence Ledger`
- Evidence date: `2026-06-22`
- Ledger type: backend evidence closeout
- Product goal: backend silent launch path for real Codex / Claude Code executor.
- This ledger records evidence only. It does not change code, frontend, API, tests, migrations, or runtime behavior.

## Current Backend Evidence

The P9-REL backend executor integration has the following evidence recorded in code and tests:

- Codex controlled native smoke passed.
- Claude Code controlled native smoke passed.
- Codex supervisor-managed native smoke passed.
- Claude Code supervisor-managed native smoke passed.
- TaskWorker supervisor-managed silent launch wiring passed.
- Worker subprocess lifecycle safety gate passed.

Key evidence surfaces:

- `runtime/orchestrator/app/external_executors/actual_native_launcher.py`
- `runtime/orchestrator/app/external_executors/actual_process_supervisor.py`
- `runtime/orchestrator/app/external_executors/actual_native_smoke.py`
- `runtime/orchestrator/app/workers/task_worker.py`
- `runtime/orchestrator/scripts/p9_real_executor_native_smoke.py`
- `runtime/orchestrator/tests/test_real_executor_native_smoke.py`
- `runtime/orchestrator/tests/test_worker_workspace_readonly_validation.py`

Latest critical commits:

- `3a9877320213d470b8f7b6e4e5ec89a7b2c9559c` - `backend: wire native process supervisor into smoke`
- `501a9d8e60eb8f0fa6e005a5f15b78a8e74a7a1e` - `backend: wire process supervisor into worker silent launch`
- `f48a14d8abf31129a4740e9f1cc04a2fc086c8fa` - `backend: guard worker native subprocess lifecycle`

## Worker Subprocess Safety Gate

The Worker subprocess-enabled path is guarded before native launch when all of the following are true:

- runner kind is `subprocess`
- launch mode is `enabled`
- native process is allowed
- a real subprocess runner would be used

Current required safety conditions:

- `process_supervisor` is required.
- At least one supervisor lifecycle policy is required:
  - `silent_launch_supervisor_terminate_after_launch=true`
  - `silent_launch_supervisor_cleanup_after_launch=true`

Blocked reasons recorded by the Worker gate:

- `worker_subprocess_requires_process_supervisor`
- `worker_subprocess_requires_supervisor_lifecycle_policy`

When the safety gate blocks, the external executor snapshot remains grouped under `external_executor_snapshot` and records:

- `attempted=true`
- `launch_status=blocked`
- `native_process_started=false`
- `runtime_handle_id_present=false`
- `supervisor_enabled` according to injected supervisor presence

## Safety Boundary

The current stage keeps the following boundaries:

- `frontend_required=false`
- `frontend_change_allowed=false`
- `product_runtime_git_write_allowed=false`
- no pid exposure
- no raw command exposure
- no raw stdout exposure
- no raw stderr exposure
- no env exposure
- no token exposure
- no secret exposure
- no api_key exposure
- subprocess launch requires supervisor plus lifecycle policy

Development workflow Git operations for this ledger are allowed and required for repository delivery. Product runtime Git writes remain forbidden and are not implemented or triggered by this ledger.

## Explicitly Not Complete

The following items remain not complete and must not be inferred from P9-REL backend evidence:

- No product-grade long-running executor lifecycle.
- No product runtime Git write capability.
- No frontend control surface for this capability.
- No new API route for this capability.
- No AI Director readonly repo evidence pack.
- No Project Director total-loop `Pass`.

## Next Stage Recommendation

Recommended next stage:

- `P10-A Project Director readonly repo evidence pack`

Goal:

- Before the AI Director assigns work, it should obtain real repository evidence first.
- The evidence pack should be readonly and should not enable product runtime Git writes.

## Gate Ledger

- `P9-REL backend executor integration`: `Pass with note`
  - Note: Backend evidence supports controlled native smoke, supervisor-managed smoke, Worker silent launch wiring, and Worker subprocess lifecycle safety gate.
- `P9 production-safe long-running executor lifecycle`: `Partial`
  - Note: Current stage only permits controlled startup with terminate/cleanup policy. Product-grade long-running lifecycle remains unfinished.
- `AI Project Director 总闭环`: `Partial`
  - Note: P9-REL backend executor evidence is a backend sub-gate only and must not be promoted to total-loop Pass.
