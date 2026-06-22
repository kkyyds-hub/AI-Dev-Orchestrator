# P12 Confirmed Dry-Run Task Dispatch Ledger - 2026-06-23

## Gate

- P12-A dry-run task dispatch contract: Pass
- P12-B confirmed dispatch API: Pass
- P12-C Worker simulate + session result smoke: Pass
- P12-D ledger: Pass with note
- P9 production-safe long-running executor lifecycle: Partial
- AI Project Director total loop: Partial

## Implemented Surface

- Confirmed dispatch endpoint: `POST /project-director/sessions/{session_id}/dry-run-task-dispatch`
- Worker result binding endpoint: `POST /project-director/sessions/{session_id}/dry-run-task-dispatch/worker-result`
- Message readback endpoint: `GET /project-director/sessions/{session_id}/messages`
- Task readback endpoints: `GET /tasks/{task_id}`, `GET /tasks/{task_id}/detail`, `GET /tasks/{task_id}/runs`
- Worker simulate endpoint: `POST /workers/run-once`
- Contract domain: `runtime/orchestrator/app/domain/project_director_dry_run_task_dispatch.py`
- Dispatch service: `runtime/orchestrator/app/services/project_director_dry_run_task_dispatch_service.py`
- Smoke script: `runtime/orchestrator/scripts/p12_project_director_dry_run_task_dispatch_smoke.py`

## Evidence Summary

P12-A defines the Project Director confirmed dry-run task dispatch contract. The contract converts a P11 evidence-to-agent dry-run trace into a confirmation-required safe task draft. It requires an `evidence_pack_id` and keeps `safe_dry_run_task=true`, `worker_simulate_required=true`, `product_runtime_git_write_allowed=false`, `frontend_required=false`, `native_executor_started=false`, `codex_started=false`, `claude_code_started=false`, and `ai_project_director_total_loop="Partial"`.

P12-B adds a confirmation API that creates one real `Task` database record from a P11 session dry-run message only when `user_confirmed=true`. The created Task is explicitly safe dry-run / simulate-only, starts as `pending`, carries the P11 `source_message_id` and `evidence_pack_id` in its input summary, and does not create a Run or call Worker. The API also appends a Project Director session message with `source_detail="p12_dry_run_task_dispatch"`.

P12-C proves the main path with isolated runtime data:

```text
create Project Director session
-> POST /project-director/sessions/{session_id}/evidence-to-agent/dry-run
-> POST /project-director/sessions/{session_id}/dry-run-task-dispatch
-> create safe dry-run Task
-> POST /workers/run-once in simulate mode
-> GET /tasks/{task_id}/detail and GET /tasks/{task_id}/runs
-> POST /project-director/sessions/{session_id}/dry-run-task-dispatch/worker-result
-> GET /project-director/sessions/{session_id}/messages
```

The P12 smoke proves the safe dry-run Task is created, Worker simulate is called, a Run is created, task/run readback succeeds, dispatch and Worker result messages are bound to the session, product runtime Git write remains forbidden, and Codex / Claude Code are not started.

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
    tests/test_project_director_dry_run_task_dispatch_contract.py \
    tests/test_project_director_dry_run_task_dispatch_api.py \
    tests/test_project_director_dry_run_task_dispatch_smoke.py \
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
  python scripts/p11_project_director_evidence_to_agent_api_smoke.py --json

uv run --no-project --with-editable . \
  --with 'fastapi>=0.115,<1.0' \
  --with 'httpx>=0.28,<1.0' \
  --with 'sqlalchemy>=2.0,<3.0' \
  --with 'pydantic>=2.0,<3.0' \
  python scripts/p12_project_director_dry_run_task_dispatch_smoke.py --json
```

## Boundary Record

- Product runtime Git write remains forbidden.
- Codex was not started by the P12 path.
- Claude Code was not started by the P12 path.
- `runtime/orchestrator/app/external_executors/**` remains unchanged.
- `runtime/orchestrator/app/workers/task_worker.py` remains unchanged.
- `apps/web/**` remains unchanged.
- `docs/superpowers/**` remains untouched.
- P12 creates a safe dry-run Task.
- P12 calls Worker simulate.
- P12 creates a Run through Worker simulate.
- P12 does not write code through product runtime execution.
- P12 does not authorize product runtime Git add / commit / push / PR / merge.
- P12 does not prove real programmer/reviewer executor lifecycle.
- P12 does not prove product-grade long-running executor lifecycle.
- AI Project Director total loop remains `Partial`.
- P9 production-safe long-running executor lifecycle remains `Partial`.

## Next Step

P13 should connect executor-backed programmer/reviewer under controlled lifecycle, or first harden confirmation/readback APIs. Do not open product runtime Git write yet.
