# BCG-07A Verification - Run Evidence Replay / Decision History Evidence

Date: 2026-05-24

## Scope

This verification proves that a Project Director-created task can be replayed
after a manual Worker run through the existing read-only task/run/log/decision
history APIs.

Strict boundaries:

- Use the existing manual Worker entrypoint only.
- Reuse existing read-only observation APIs where possible.
- Do not add automatic scheduling.
- Do not add write APIs.
- Do not change frontend code.
- Do not call planning/apply.
- This phase is run evidence replay only; it is not AI Project Director total
  closure Pass.

## Read-only APIs reused

No new read-only API was added in this phase. The evidence test reused:

- `GET /tasks/{task_id}/runs`
- `GET /runs/{run_id}/logs?limit=200`
- `GET /runs/{run_id}/decision-trace`
- `GET /tasks/{task_id}/decision-history`

The existing write entrypoints used to create the prerequisite runtime evidence
were:

- `POST /project-director/sessions`
- `POST /project-director/sessions/{session_id}/answers`
- `POST /project-director/sessions/{session_id}/confirm`
- `POST /project-director/sessions/{session_id}/plan-versions`
- `POST /project-director/plan-versions/{plan_version_id}/confirm`
- `POST /project-director/plan-versions/{plan_version_id}/create-tasks`
- `POST /workers/run-once?project_id={project_id}`

## Evidence chain

The automated evidence test follows this chain:

1. Create a project for BCG-07A replay evidence.
2. Create and confirm a Project Director session.
3. Create and confirm a plan version.
4. Force deterministic `simulate:` task descriptions for provider-independent
   replay evidence.
5. Call BCG-04A `create-tasks`, producing real task queue rows with
   `source_draft_id=pdv:{plan_version_id}:{version_no}`.
6. Call the existing manual Worker endpoint,
   `POST /workers/run-once?project_id={project_id}`.
7. Worker claims one Project Director-created task and finalizes a persisted
   `RunTable` row.
8. `GET /tasks/{task_id}/runs` returns the run row, log path, and quality gate.
9. `GET /runs/{run_id}/logs?limit=200` returns structured JSONL events,
   including `task_routed`, `role_handoff`, `run_claimed`, `context_built`,
   `execution_finished`, `verification_finished`, `cost_estimated`, and
   `run_finalized`.
10. `GET /runs/{run_id}/decision-trace` returns replay stages including
    routing, handoff, claim, execution, verification, and finalize.
11. `GET /tasks/{task_id}/decision-history` returns a task-level replay summary
    linked to the same run.

## Backend adjustment

`DecisionReplayService._build_headline` now prefers core run evidence events
for task-level history headlines (`run_finalized`, guard/verification/execution
events) before falling back to the last log event. This prevents later auxiliary
events, such as auto-created approval metadata, from masking the run replay
headline.

This is a read-path behavior fix only. No new write endpoint was added.

## Test commands and results

Focused BCG-07A replay test:

```powershell
cd runtime/orchestrator
.\.venv\Scripts\python.exe -m pytest tests/test_project_director_run_evidence_replay.py -q
```

Result:

```text
1 passed in 2.02s
```

Project Director upstream regression plus BCG-07A:

```powershell
cd runtime/orchestrator
.\.venv\Scripts\python.exe -m pytest tests/test_project_director_sessions.py tests/test_project_director_plan_versions.py tests/test_project_director_confirmations.py tests/test_project_director_task_creation.py tests/test_project_director_worker_run_evidence.py tests/test_project_director_run_evidence_replay.py -q
```

Result:

```text
97 passed, 3 warnings in 27.25s
```

The warnings are existing `HTTP_422_UNPROCESSABLE_ENTITY` deprecation warnings
from negative-path tests; no test failed.

## Frontend/build

- Frontend changed: no.
- `apps/web` build run: no.
- Reason: BCG-07A is a backend run evidence replay/API proof; no frontend files
  were changed.

## Gate conclusion

BCG-07A Run Evidence Replay / Decision History Evidence: Pass for this
evidence-replay phase.

AI Project Director total closure remains Partial. This proof does not close
repository, deliverable, approval, governance, cost dashboard, or total rollup
gates.
