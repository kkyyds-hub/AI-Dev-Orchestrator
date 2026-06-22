# P11 Evidence-to-Agent Main Path Ledger - 2026-06-23

## Gate

- P11-A API dry-run surface: Pass
- P11-B session/message binding: Pass
- P11-C main path smoke: Pass
- P11-D evidence ledger: Pass with note
- P9 production-safe long-running executor lifecycle: Partial
- AI Project Director total loop: Partial

## Implemented Surface

- Non-session endpoint: `POST /project-director/evidence-to-agent/dry-run`
- Session endpoint: `POST /project-director/sessions/{session_id}/evidence-to-agent/dry-run`
- Message readback endpoint: `GET /project-director/sessions/{session_id}/messages`
- Shared service: `runtime/orchestrator/app/services/project_director_evidence_to_agent_dry_run_service.py`
- Smoke script: `runtime/orchestrator/scripts/p11_project_director_evidence_to_agent_api_smoke.py`

## Evidence Summary

P11-A wraps the P10 evidence-to-agent chain in a backend service and exposes a safe Project Director dry-run API. The response includes `product_runtime_git_write_allowed=false`, `frontend_required=false`, `ai_project_director_total_loop="Partial"`, `native_executor_started=false`, `codex_started=false`, and `claude_code_started=false`.

P11-B binds the dry-run result to a Project Director session by appending one assistant message with `source_detail="p11_evidence_to_agent_session_dry_run"`. The message records the evidence pack id, dry-run status, composed task count, programmer/reviewer assignment flags, product runtime Git write boundary, frontend boundary, and total-loop `Partial` state. It is a traceable supervisor message, not a real execution task.

P11-C proves the main path with isolated runtime data:

```text
create Project Director session
-> POST /project-director/sessions/{session_id}/evidence-to-agent/dry-run
-> read GET /project-director/sessions/{session_id}/messages
-> verify safe dry-run record
```

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
    tests/test_project_director_evidence_to_agent_dry_run.py \
    tests/test_project_director_evidence_to_agent_api.py \
    tests/test_project_director_evidence_to_agent_session.py \
    tests/test_project_director_evidence_to_agent_api_smoke.py \
    -q
```

Additional compatibility/evidence commands:

```bash
cd runtime/orchestrator

uv run --no-project --with-editable . \
  --with 'fastapi>=0.115,<1.0' \
  --with 'httpx>=0.28,<1.0' \
  --with 'sqlalchemy>=2.0,<3.0' \
  --with 'pydantic>=2.0,<3.0' \
  python scripts/p10_evidence_to_agent_dry_run.py --json

uv run --no-project --with-editable . \
  --with 'fastapi>=0.115,<1.0' \
  --with 'httpx>=0.28,<1.0' \
  --with 'sqlalchemy>=2.0,<3.0' \
  --with 'pydantic>=2.0,<3.0' \
  python scripts/p11_project_director_evidence_to_agent_api_smoke.py --json
```

## Boundary Record

- Product runtime Git write remains forbidden.
- Codex was not started by the P11 dry-run path.
- Claude Code was not started by the P11 dry-run path.
- `runtime/orchestrator/app/external_executors/**` remains unchanged.
- `runtime/orchestrator/app/workers/task_worker.py` remains unchanged.
- `apps/web/**` remains unchanged.
- No real execution task is created by the P11 dry-run endpoint.
- No Worker is called by the P11 dry-run endpoint.
- P11 is API + session dry-run integration only.
- P11 is not total product closure.
- AI Project Director total loop remains `Partial`.
- P9 production-safe long-running executor lifecycle remains `Partial`.

## Next Step

P12 should decide between API hardening, a frontend read-only surface, or long-running executor lifecycle work. P12 should not open product runtime Git write yet.
