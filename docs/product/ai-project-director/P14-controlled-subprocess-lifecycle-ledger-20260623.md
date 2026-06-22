# P14 Controlled Subprocess Lifecycle Smoke Ledger - 2026-06-23

## Gate

- P14-A controlled subprocess safety gate: Pass
- P14-B controlled subprocess launch + supervisor cleanup: Pass with note
- P14-C lifecycle result message binding: Pass
- P14-D ledger: Pass with note
- P9 production-safe long-running executor lifecycle: Pass with note
- AI Project Director total loop: Partial

## Implemented Surface

- Smoke script: `runtime/orchestrator/scripts/p14_project_director_controlled_subprocess_smoke.py`
- Targeted tests: `runtime/orchestrator/tests/test_project_director_controlled_subprocess_smoke.py`
- Lifecycle result binding service: `runtime/orchestrator/app/services/project_director_controlled_executor_dispatch_service.py`
- Message readback endpoint: `GET /project-director/sessions/{session_id}/messages`

No frontend entrypoint was added. The API endpoint `POST /project-director/sessions/{session_id}/controlled-executor-dispatch` still does not directly launch a controlled subprocess.

## Evidence Summary

P14-A adds a controlled subprocess smoke safety gate. Default smoke remains `dry_run`. `controlled_smoke` requires all of:

- `--launch-mode controlled_smoke`
- `--executor codex` or `--executor claude-code`
- `--requested-agent-role programmer` or `--requested-agent-role reviewer`
- `--enable-native-process`
- `--auto-terminate`
- `--timeout-seconds > 0`
- `--use-supervisor`
- `--supervisor-cleanup-after-launch`
- `--json`

Missing any safety flag returns `smoke_status="blocked"` and does not start a native executor, bind an AgentSession, register supervisor state, or mark cleanup done.

P14-B wires the smoke harness to the existing native launcher, runner wiring, silent launch service, AgentSession repository, and process supervisor. Default pytest uses a fake native runner only. The fake controlled smoke proves launch started, AgentSession bound, runtime/process handle present, supervisor registered, terminate attempted, and cleanup done without starting Codex or Claude Code.

P14-C records the lifecycle summary back into the Project Director session with `source_detail="p14_controlled_subprocess_lifecycle_result"` and readback through `GET /project-director/sessions/{session_id}/messages`. The message content and suggested action state that this smoke is not code modification completion, does not authorize product runtime Git write, and keeps AI Project Director total loop as `Partial`.

The P14 smoke creates an isolated Project and uses P12 safe Worker simulate to produce a Run for the existing AgentSession foreign-key contract. The summary reports `run_created_by="p12_worker_simulate"`. This Run is not a P14 code-modification run and is not a product Git write.

## Evidence Results

Default P14 dry-run smoke:

- `smoke_status="passed_dry_run"`
- `native_executor_started=false`
- `agent_session_bound=false`
- `process_handle_id_present=false`
- `product_runtime_git_write_allowed=false`
- `worktree_write_allowed=false`
- `real_code_modified=false`
- `git_write_performed=false`

Fake controlled smoke:

- Covered by `tests/test_project_director_controlled_subprocess_smoke.py`
- `smoke_status="passed_controlled_smoke"`
- `controlled_subprocess_runner="fake"`
- `agent_session_bound=true`
- `runtime_handle_id_present=true`
- `process_handle_id_present=true`
- `supervisor_registered=true`
- `terminate_attempted=true`
- `supervisor_cleanup_done=true`
- `p14_lifecycle_result_message_bound=true`
- `message_readback_ok=true`
- `product_runtime_git_write_allowed=false`
- `worktree_write_allowed=false`
- `real_code_modified=false`
- `git_write_performed=false`

Real Codex controlled subprocess smoke:

- Ran with explicit safety flags.
- Result: `smoke_status="passed_controlled_smoke"`
- `controlled_subprocess_runner="subprocess"`
- `requested_executor="codex"`
- `requested_agent_role="programmer"`
- `native_executor_started=true`
- `codex_started=true`
- `claude_code_started=false`
- `agent_session_bound=true`
- `runtime_handle_id_present=true`
- `process_handle_id_present=true`
- `supervisor_registered=true`
- `terminate_attempted=true`
- `supervisor_cleanup_done=true`
- `p14_lifecycle_result_message_bound=true`
- `message_readback_ok=true`
- `product_runtime_git_write_allowed=false`
- `worktree_write_allowed=false`
- `real_code_modified=false`
- `git_write_performed=false`

Real Claude controlled subprocess smoke:

- Not run. Codex controlled subprocess smoke passed, so Claude fallback was not required for this ledger.

## Targeted Tests

```bash
cd runtime/orchestrator

uv run --no-project --with-editable . \
  --with pytest \
  --with 'fastapi>=0.115,<1.0' \
  --with 'httpx>=0.28,<1.0' \
  --with 'sqlalchemy>=2.0,<3.0' \
  --with 'pydantic>=2.0,<3.0' \
  pytest \
    tests/test_project_director_controlled_subprocess_smoke.py \
    tests/test_project_director_controlled_executor_lifecycle_smoke.py \
    tests/test_project_director_controlled_executor_dispatch_api.py \
    -q
```

Compatibility and smoke evidence commands:

```bash
cd runtime/orchestrator

uv run --no-project --with-editable . \
  --with 'fastapi>=0.115,<1.0' \
  --with 'httpx>=0.28,<1.0' \
  --with 'sqlalchemy>=2.0,<3.0' \
  --with 'pydantic>=2.0,<3.0' \
  python scripts/p13_project_director_controlled_executor_lifecycle_smoke.py --json

uv run --no-project --with-editable . \
  --with 'fastapi>=0.115,<1.0' \
  --with 'httpx>=0.28,<1.0' \
  --with 'sqlalchemy>=2.0,<3.0' \
  --with 'pydantic>=2.0,<3.0' \
  python scripts/p14_project_director_controlled_subprocess_smoke.py --json

uv run --no-project --with-editable . \
  --with 'fastapi>=0.115,<1.0' \
  --with 'httpx>=0.28,<1.0' \
  --with 'sqlalchemy>=2.0,<3.0' \
  --with 'pydantic>=2.0,<3.0' \
  python scripts/p14_project_director_controlled_subprocess_smoke.py \
    --json \
    --launch-mode controlled_smoke \
    --executor codex \
    --requested-agent-role programmer \
    --enable-native-process \
    --auto-terminate \
    --timeout-seconds 2 \
    --use-supervisor \
    --supervisor-cleanup-after-launch
```

## Boundary Record

- Product runtime Git write remains forbidden.
- Worktree write remains forbidden.
- `product_runtime_git_write_allowed=true` was not introduced.
- `worktree_write_allowed=true` was not introduced.
- No product runtime `git add`, `git commit`, `git push`, PR, or merge was implemented or triggered.
- No code modification is a P14 smoke pass condition.
- No pid, raw command, raw stdout, raw stderr, env, token, secret, or api_key is exposed.
- `shell=True` was not introduced.
- Default smoke does not start Codex or Claude Code.
- Default pytest does not start Codex or Claude Code.
- Controlled subprocess smoke requires explicit safety flags.
- Supervisor registration, terminate, and cleanup are required for pass.
- `apps/web/**` remains unchanged.
- `docs/superpowers/**` remains untouched.
- `runtime/orchestrator/app/workers/task_worker.py` remains unchanged.
- No worktree write runner/service was called.
- AI Project Director total loop remains `Partial`.
- P9 production-safe long-running executor lifecycle is `Pass with note`, not full Pass, because this is still a controlled smoke and not the complete long-running lifecycle.

## Next Step

P15 should choose one of:

1. readonly reviewer executor deep-review path;
2. controlled programmer executor no-write execution;
3. executor lifecycle hardening.

Do not open product runtime Git write yet.
