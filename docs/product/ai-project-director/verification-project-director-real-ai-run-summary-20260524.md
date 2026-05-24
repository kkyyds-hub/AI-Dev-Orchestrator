# BCG-08A Verification - Real AI Run Summary Evidence

Date: 2026-05-24

## Scope

This verification proves that the existing AI run summary generate/regenerate
API can use a real provider-reported Worker run to produce a persisted
`source=ai` run summary that is readable and traceable.

Strict boundaries:

- Reuse the BCG-05B provider-reported run.
- Use existing run AI summary APIs.
- Do not add new write APIs.
- Do not change frontend code.
- Do not use mock/simulate as the summary generation substitute.
- Do not print or write any API key.
- Do not mark AI Project Director total closure Pass.

## Existing implementation checked

The phase was based on the existing implementation in:

- `runtime/orchestrator/app/api/routes/runs.py`
- `runtime/orchestrator/app/services/run_ai_summary_service.py`
- `runtime/orchestrator/app/repositories/run_ai_summary_repository.py`

Existing API behavior:

- `POST /runs/{run_id}/ai-summary/regenerate` forces a new run summary and marks
  prior active summaries stale.
- With provider config present, `RunAISummaryService` calls the provider through
  `OpenAIProviderExecutorService.generate_text`.
- On valid provider markdown, the summary is persisted with `source=ai`.
- `GET /runs/{run_id}/ai-summary` reads the active persisted summary.
- `GET /runs/{run_id}/ai-summaries` reads persisted summary history.

## Target provider-reported run

| Field | Value |
|---|---|
| run_id | `834b38aa-3669-4121-9424-3aa4999cad2e` |
| task_id | `db204e31-f244-4f9b-a469-abcc5e0b873f` |
| provider_key | `deepseek` |
| model_name | `deepseek-v4-pro` |
| token_accounting_mode | `provider_reported` |
| run_provider_receipt_id | `3d8bf6e7-fdfd-43db-bd9a-3abee685521d` |
| total_tokens | `446` |
| estimated_cost | `0.000768` |
| log_path | `logs/task-runs/db204e31-f244-4f9b-a469-abcc5e0b873f/834b38aa-3669-4121-9424-3aa4999cad2e.jsonl` |

## Summary API used

- Generate/regenerate: `POST /runs/834b38aa-3669-4121-9424-3aa4999cad2e/ai-summary/regenerate`
- Read current: `GET /runs/834b38aa-3669-4121-9424-3aa4999cad2e/ai-summary`
- Read history: `GET /runs/834b38aa-3669-4121-9424-3aa4999cad2e/ai-summaries`

## Live evidence command and result

Command:

```powershell
cd runtime/orchestrator
.\.venv\Scripts\python.exe scripts\bcg08a_real_ai_run_summary_live.py
```

Result summary:

```json
{
  "real_model_called": true,
  "summary_id": "9a229984-f5bd-4773-a6de-9db61786b837",
  "status": "succeeded",
  "source": "ai",
  "model_provider": "deepseek",
  "model_name": "deepseek-v4-pro",
  "provider_receipt_id": "dbec655b-49b2-4639-9757-70b71ce4347f",
  "error_summary": null,
  "stale": false,
  "source_version": "run.summary.v2",
  "history_count": 2,
  "generated_summary_in_history": true
}
```

Traceability fields were returned and persisted:

- `source_fingerprint=dfa78dc0fa548a858295ae7b742e4f9b14dbe833c60c977c61ed5b81df6c5df0`
- `source_hash=dfa78dc0fa548a858295ae7b742e4f9b14dbe833c60c977c61ed5b81df6c5df0`
- `prompt_hash=080d4beb982c1dd76dca985e0cbee2e208adf650f942cbe35c7a3d1b67a05126`

The generated summary was then read back as the active current summary and from
history:

- `current_active_summary_id=9a229984-f5bd-4773-a6de-9db61786b837`
- `history_active_summary_id=9a229984-f5bd-4773-a6de-9db61786b837`
- `history_count=2`

## Summary content excerpt

The generated `source=ai` markdown states that the run succeeded, the
`deepseek/deepseek-v4-pro` provider execution returned the expected evidence
sentence, the original run's simulated verifier passed, and the quality gate
allowed completion. It also cites the original provider run receipt
`3d8bf6e7-fdfd-43db-bd9a-3abee685521d`, execution mode `provider_openai`, and
quality-gate status.

## Fallback status

- Summary source: `ai`
- Summary status: `succeeded`
- `error_summary`: `null`
- `stale`: `false`
- Rule fallback used for BCG-08A summary generation: no

## Ordinary regression tests

Command:

```powershell
cd runtime/orchestrator
.\.venv\Scripts\python.exe -m pytest tests/test_run_ai_summaries.py tests/test_project_director_sessions.py tests/test_project_director_plan_versions.py tests/test_project_director_confirmations.py tests/test_project_director_task_creation.py tests/test_project_director_worker_run_evidence.py tests/test_project_director_run_evidence_replay.py -q
```

Result:

```text
132 passed, 3 warnings in 34.93s
```

The warnings are existing `HTTP_422_UNPROCESSABLE_ENTITY` deprecation warnings
from negative-path tests; no test failed.

## Frontend/build

- Frontend changed: no.
- `apps/web` build run: no.
- Reason: BCG-08A is backend/runtime live summary evidence only.

## Gate conclusion

BCG-08A Real AI Run Summary Evidence: Pass for this evidence phase.

AI Project Director total closure remains Partial. This proof does not close
repository, delivery, approval, governance, cost dashboard, or total rollup
gates by itself.
---

## BCG-08A-R2 copy guard closure addendum

Date: 2026-05-24

Purpose: close the BCG-08A-R1 acceptance gap without adding product scope or
entering BCG-09. R2 keeps the same real provider-reported target run and adds
hard copy-guard assertions to the live evidence script.

### Additional hard assertions

The live script now fails if any of the following is false:

- `summary_markdown.strip()` is not identical to `run.result_summary.strip()`.
- `summary_markdown.strip()` is not identical to `run.verification_summary.strip()`.
- The summary is not merely a raw `run.result_summary` excerpt followed only by
  trailing punctuation/formatting and then end-of-text.
- The summary is not merely a raw `run.verification_summary` excerpt followed
  only by trailing punctuation/formatting and then end-of-text.

### R2 live evidence result

Command:

```powershell
python runtime/orchestrator/scripts/bcg08a_real_ai_run_summary_live.py
```

Result summary:

```json
{
  "phase": "BCG-08A-R2 Real AI Run Summary Evidence Copy Guard Closure",
  "summary_id": "74fe9426-e869-43a7-95ed-933fcc75edc0",
  "source": "ai",
  "fallback_used": false,
  "error_summary": null,
  "copy_guard": {
    "summary_differs_from_result_summary": true,
    "summary_differs_from_verification_summary": true,
    "summary_not_result_summary_then_end": true,
    "summary_not_verification_summary_then_end": true
  },
  "evidence_coverage": {
    "provider_key": true,
    "model_name": true,
    "original_run_receipt": true,
    "execution_mode": true,
    "token_accounting_mode": true,
    "total_tokens": true,
    "estimated_cost": true,
    "log_path": true,
    "quality_gate": true
  }
}
```

The R2 run still used the existing APIs only:

- `POST /runs/834b38aa-3669-4121-9424-3aa4999cad2e/ai-summary/regenerate`
- `GET /runs/834b38aa-3669-4121-9424-3aa4999cad2e/ai-summary`
- `GET /runs/834b38aa-3669-4121-9424-3aa4999cad2e/ai-summaries`

No new write API was added. No frontend code was changed. The summary service
was not changed in R2; the fix is a minimum live-evidence acceptance guard and
documentation update.

### R2 ordinary regression

Command:

```powershell
cd runtime/orchestrator
python -m pytest tests
```

Result: `132 passed, 127 warnings`.

### R2 gate conclusion

BCG-08A-R2 minimum closure: Pass. AI Project Director total closure remains
Partial, and this addendum does not enter or satisfy BCG-09.
