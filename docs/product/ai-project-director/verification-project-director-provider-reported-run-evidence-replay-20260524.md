# BCG-07B Verification - Provider-Reported Run Evidence Replay

Date: 2026-05-24

## Scope

This verification proves that the existing BCG-05B real provider-reported Worker
run can be replayed through the run/task/log/decision-history read paths.

Strict boundaries:

- Reuse the BCG-05B persisted provider run if the local DB/log evidence is
  present.
- Do not use mock or simulate execution as a substitute for provider evidence.
- Do not create tasks.
- Do not trigger Worker.
- Do not add write APIs.
- Do not change frontend code.
- Do not mark AI Project Director total closure Pass.

Note: the original BCG-05B run used the existing simulate verifier after real
provider execution. That verifier result is not used as a substitute for the
model execution evidence. Provider execution itself is proven by
`execution_mode=provider_openai`, `actual_execution_mode=provider_openai`,
`fallback_applied=false`, and `token_accounting_mode=provider_reported`.

## Reuse decision

BCG-07B reused the existing BCG-05B run. No new provider run was triggered.

Reason:

- The local runtime DB and JSONL log for the BCG-05B run were present.
- The run already contains real provider execution evidence and provider-reported
  token accounting.
- BCG-07B is a replay/read-path evidence phase, not a new model-output phase.

## Evidence IDs

| Field | Value |
|---|---|
| project_id | `423367da-966b-4c2e-b8c8-a4ff5f7f2377` |
| session_id | `1177d06d-1c71-4e17-979a-855645ea87d8` |
| plan_version_id | `8b906cf9-b7c0-49b3-b7e7-1d7a918ad956` |
| task_id | `db204e31-f244-4f9b-a469-abcc5e0b873f` |
| run_id | `834b38aa-3669-4121-9424-3aa4999cad2e` |

## Provider evidence

| Field | Value |
|---|---|
| provider_key | `deepseek` |
| model_name | `deepseek-v4-pro` |
| execution_mode | `provider_openai` |
| actual_execution_mode | `provider_openai` |
| fallback_applied | `false` |
| token_accounting_mode | `provider_reported` |
| provider_receipt_id | `3d8bf6e7-fdfd-43db-bd9a-3abee685521d` |
| prompt_tokens | `380` |
| completion_tokens | `66` |
| total_tokens | `446` |
| estimated_cost | `0.000768` |
| log_path | `logs/task-runs/db204e31-f244-4f9b-a469-abcc5e0b873f/834b38aa-3669-4121-9424-3aa4999cad2e.jsonl` |

## Read-only APIs replayed

No new API was added. The live evidence script reused:

- `GET /project-director/sessions/{session_id}`
- `GET /project-director/plan-versions/{plan_version_id}`
- `GET /project-director/plan-versions/{plan_version_id}/created-tasks`
- `GET /tasks/{task_id}/runs`
- `GET /runs/{run_id}/logs?limit=200`
- `GET /runs/{run_id}/decision-trace`
- `GET /tasks/{task_id}/decision-history`

## Live replay command and result

Command:

```powershell
cd runtime/orchestrator
.\.venv\Scripts\python.exe scripts\bcg07b_provider_reported_replay_live.py
```

Result summary:

```json
{
  "reused_existing_bcg05b_run": true,
  "provider_key": "deepseek",
  "model_name": "deepseek-v4-pro",
  "execution_mode": "provider_openai",
  "actual_execution_mode": "provider_openai",
  "fallback_applied": false,
  "token_accounting_mode": "provider_reported",
  "prompt_tokens": 380,
  "completion_tokens": 66,
  "total_tokens": 446,
  "estimated_cost": 0.000768,
  "log_event_count": 13,
  "trace_item_count": 13,
  "decision_history_items": 1,
  "decision_history_headline": "Task and run were finalized."
}
```

Log / trace events replayed:

```text
task_routed
role_handoff
run_claimed
context_built
memory_governance_checkpointed
execution_plan_ready
prompt_contract_built
execution_finished
verification_finished
token_accounting_ready
cost_estimated
run_finalized
approval_auto_created
```

Decision-trace stages replayed:

```text
routing, handoff, claim, context, runtime, execution, verification, cost, finalize
```

Task decision-history returned one item for the same run:

- `run_id=834b38aa-3669-4121-9424-3aa4999cad2e`
- `status=succeeded`
- `quality_gate_passed=true`
- `failure_category=null`
- `headline=Task and run were finalized.`

## Ordinary regression tests

Command:

```powershell
cd runtime/orchestrator
.\.venv\Scripts\python.exe -m pytest tests/test_project_director_sessions.py tests/test_project_director_plan_versions.py tests/test_project_director_confirmations.py tests/test_project_director_task_creation.py tests/test_project_director_worker_run_evidence.py tests/test_project_director_run_evidence_replay.py -q
```

Result:

```text
97 passed, 3 warnings
```

The warnings are existing `HTTP_422_UNPROCESSABLE_ENTITY` deprecation warnings
from negative-path tests; no test failed.

## Frontend/build

- Frontend changed: no.
- `apps/web` build run: no.
- Reason: BCG-07B is backend/runtime replay evidence only.

## Gate conclusion

BCG-07B Provider-Reported Run Evidence Replay: Pass for this replay phase.

AI Project Director total closure remains Partial. This proof does not close
repository, delivery, approval, governance, cost dashboard, or total rollup
gates by itself.
