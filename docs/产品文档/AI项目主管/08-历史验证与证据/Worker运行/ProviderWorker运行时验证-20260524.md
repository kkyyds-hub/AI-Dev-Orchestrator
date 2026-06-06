# BCG-05B Verification - Provider-Reported Worker Runtime Evidence

Date: 2026-05-24

## Scope

This document records real provider-reported Worker runtime evidence for a Project Director-created task.

Strict boundaries:

- Use the existing manual Worker entrypoint only.
- Do not add automatic scheduling.
- Do not change frontend code.
- Do not call planning/apply.
- Do not write repositories.
- Do not mark AI Project Director total closure Pass.

## Provider configuration observed

Safe runtime summary only; the API key was not printed.

- configured: true
- source: saved_config
- base_url: `https://api.deepseek.com`
- detected_provider_type: `deepseek`
- model_preset: `deepseek`
- model_names: `{"economy":"deepseek-v4-pro","balanced":"deepseek-v4-pro","premium":"deepseek-v4-pro"}`
- timeout_seconds: 30

## Worker entrypoint

`POST /workers/run-once?project_id=423367da-966b-4c2e-b8c8-a4ff5f7f2377`

This was a manual single-cycle Worker run scoped to the evidence project.

## Evidence chain

1. Created project `423367da-966b-4c2e-b8c8-a4ff5f7f2377`.
2. Created and confirmed Project Director session `1177d06d-1c71-4e17-979a-855645ea87d8`.
3. Created and confirmed plan version `8b906cf9-b7c0-49b3-b7e7-1d7a918ad956`.
4. Called `POST /project-director/plan-versions/{id}/create-tasks`, producing real task queue entries.
5. Called `POST /workers/run-once?project_id=423367da-966b-4c2e-b8c8-a4ff5f7f2377`.
6. Worker claimed task `db204e31-f244-4f9b-a469-abcc5e0b873f`.
7. Worker created and finalized run `834b38aa-3669-4121-9424-3aa4999cad2e`.
8. Persisted Run row reported `token_accounting_mode=provider_reported`.

## Runtime evidence

| Field | Value |
|---|---|
| project_id | `423367da-966b-4c2e-b8c8-a4ff5f7f2377` |
| task_id | `db204e31-f244-4f9b-a469-abcc5e0b873f` |
| run_id | `834b38aa-3669-4121-9424-3aa4999cad2e` |
| task_status | `completed` |
| run_status | `succeeded` |
| execution_mode | `provider_openai` |
| verification_mode | `simulate` |
| provider_key | `deepseek` |
| model_name | `deepseek-v4-pro` |
| token_accounting_mode | `provider_reported` |
| provider_receipt_id | `3d8bf6e7-fdfd-43db-bd9a-3abee685521d` |
| prompt_tokens | `380` |
| completion_tokens | `66` |
| total_tokens | `446` |
| estimated_cost | `0.000768` |
| cache_source | `provider_reported` |
| quality_gate_passed | `true` |
| log_path | `logs/task-runs/db204e31-f244-4f9b-a469-abcc5e0b873f/834b38aa-3669-4121-9424-3aa4999cad2e.jsonl` |

Result summary prefix:

```text
Execution: OpenAI-compatible provider execution succeeded. Target deepseek/deepseek-v4-pro via chat_completions at https://api.deepseek.com/v1/chat/completions. Receipt 3d8bf6e7-fdfd-43db-bd9a-3abee685521d. Output: BCG-05B provider evidence task 1 completed.
Verification: Simulated verification succeeded. Execution mode was provider_openai. Quality gate allowed task completion.
```

## Mock/simulate usage

- Provider execution used real provider path: yes, `execution_mode=provider_openai`.
- Persisted accounting was provider-reported: yes, `token_accounting_mode=provider_reported`.
- `provider_mock`: no.
- `simulate` executor for task execution: no.
- Verification mode: existing simulate verifier. This does not replace provider execution evidence.

## Regression tests

Command run after evidence capture:

```powershell
cd runtime/orchestrator
.\.venv\Scripts\python.exe -m pytest tests/test_project_director_sessions.py tests/test_project_director_plan_versions.py tests/test_project_director_confirmations.py tests/test_project_director_task_creation.py tests/test_project_director_worker_run_evidence.py -q
```

Result:

```text
96 passed, 3 warnings
```

The warnings are existing `HTTP_422_UNPROCESSABLE_ENTITY` deprecation warnings from negative-path tests; no test failed.

## Gate conclusion

BCG-05B provider_reported runtime evidence: Pass for this phase.

AI Project Director total closure remains Partial. This evidence does not close repository, delivery, approval, governance, cost dashboard, or total rollup gates by itself.
