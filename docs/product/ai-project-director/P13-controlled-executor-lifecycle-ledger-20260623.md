# P13 Controlled Executor Lifecycle Pilot Ledger - 2026-06-23

## Gate

- P13-A controlled executor dispatch contract: Pass
- P13-B confirmed controlled executor dispatch API: Pass
- P13-C controlled executor lifecycle smoke: Pass with note
- P13-D ledger: Pass with note
- P9 production-safe long-running executor lifecycle: Partial
- AI Project Director total loop: Partial

## Implemented Surface

- Controlled dispatch endpoint: `POST /project-director/sessions/{session_id}/controlled-executor-dispatch`
- Message readback endpoint: `GET /project-director/sessions/{session_id}/messages`
- Contract domain: `runtime/orchestrator/app/domain/project_director_controlled_executor_dispatch.py`
- Dispatch service: `runtime/orchestrator/app/services/project_director_controlled_executor_dispatch_service.py`
- Smoke script: `runtime/orchestrator/scripts/p13_project_director_controlled_executor_lifecycle_smoke.py`

## Evidence Summary

P13-A defines a controlled executor-backed dispatch contract derived from P12 safe dry-run Task evidence. It requires `user_confirmed=true`, a P12 safe dry-run source Task, and a P12 dispatch or Worker-result source message. It distinguishes safe dry-run task, controlled executor pilot task, and production Git write task. This stage only permits the controlled executor pilot and keeps `product_runtime_git_write_allowed=false`, `worktree_write_allowed=false`, `native_executor_started=false`, `codex_started=false`, `claude_code_started=false`, `supervisor_required=true`, `auto_terminate_required=true`, `cleanup_required=true`, `frontend_required=false`, and `ai_project_director_total_loop="Partial"`.

P13-B adds the confirmed controlled executor dispatch API. The default `launch_mode="dry_run"` records a Project Director session message with `source_detail="p13_controlled_executor_dispatch"`. It does not create a new Task, does not create a Run, does not call Worker, does not call external executors, and does not start Codex or Claude Code. `launch_mode="controlled_smoke"` is blocked at the API layer with `controlled_smoke_not_enabled_in_api`; controlled subprocess behavior is only allowed from the explicit smoke harness.

P13-C proves the dry-run lifecycle trace with isolated runtime data:

```text
create Project Director session
-> POST /project-director/sessions/{session_id}/evidence-to-agent/dry-run
-> POST /project-director/sessions/{session_id}/dry-run-task-dispatch
-> create P12 safe dry-run Task
-> POST /project-director/sessions/{session_id}/controlled-executor-dispatch
-> record p13_controlled_executor_lifecycle_result session message
-> GET /project-director/sessions/{session_id}/messages
```

The default P13 smoke proves P11 dry-run message binding, P12 safe task creation, P13 dispatch message binding, P13 lifecycle result message binding, and message readback. It reports `smoke_status="passed_dry_run"`, `native_executor_started=false`, `codex_started=false`, `claude_code_started=false`, `agent_session_bound=false`, `run_created=false`, `real_code_modified=false`, and `git_write_performed=false`.

No real controlled subprocess smoke was run for this ledger. The script includes safety gates for `controlled_smoke`, but default pytest and default smoke stay dry-run only.

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
    tests/test_project_director_controlled_executor_dispatch_contract.py \
    tests/test_project_director_controlled_executor_dispatch_api.py \
    tests/test_project_director_controlled_executor_lifecycle_smoke.py \
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
  python scripts/p12_project_director_dry_run_task_dispatch_smoke.py --json

uv run --no-project --with-editable . \
  --with 'fastapi>=0.115,<1.0' \
  --with 'httpx>=0.28,<1.0' \
  --with 'sqlalchemy>=2.0,<3.0' \
  --with 'pydantic>=2.0,<3.0' \
  python scripts/p13_project_director_controlled_executor_lifecycle_smoke.py --json
```

## Boundary Record

- Product runtime Git write remains forbidden.
- Worktree write remains forbidden.
- `product_runtime_git_write_allowed=true` was not introduced.
- Codex and Claude Code are not started by the default path.
- Controlled subprocess launch is not part of default pytest or default smoke.
- Controlled subprocess is only allowed behind explicit smoke flags.
- Real controlled subprocess smoke was not run for this ledger.
- No real code modification is a pass condition.
- Safe dry-run Task remains safe.
- P12 Worker simulate loop remains compatible.
- `runtime/orchestrator/app/external_executors/**` remains unchanged.
- `runtime/orchestrator/app/workers/task_worker.py` remains unchanged.
- `apps/web/**` remains unchanged.
- `docs/superpowers/**` remains untouched.
- P13 does not prove a product-level long-running executor lifecycle.
- P13 does not prove a real programmer/reviewer code-modification loop.
- P13 does not authorize product runtime git add / commit / push / PR / merge.
- AI Project Director total loop remains `Partial`.
- P9 production-safe long-running executor lifecycle remains `Partial`.

## Next Step

P14 should choose one of:

1. readonly reviewer executor deep-review path;
2. controlled programmer executor no-write task;
3. executor lifecycle hardening.

Do not open product runtime Git write yet.
