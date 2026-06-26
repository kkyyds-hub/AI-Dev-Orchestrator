# P15 Readonly Reviewer Executor Deep-Review Ledger - 2026-06-23

## Gate

- P15-A readonly review contract: Pass
- P15-B readonly review API: Pass
- P15-C readonly reviewer smoke: Pass
- P15-D ledger: Pass with note
- P9 production-safe long-running executor lifecycle: Partial
- AI Project Director total loop: Partial

## Implemented Surface

- Domain contract: `runtime/orchestrator/app/domain/project_director_readonly_review.py`
- Service: `runtime/orchestrator/app/services/project_director_readonly_review_service.py`
- Endpoint: `POST /project-director/sessions/{session_id}/readonly-review`
- Smoke script: `runtime/orchestrator/scripts/p15_project_director_readonly_reviewer_smoke.py`
- Targeted tests:
  - `runtime/orchestrator/tests/test_project_director_readonly_review_contract.py`
  - `runtime/orchestrator/tests/test_project_director_readonly_review_api.py`
  - `runtime/orchestrator/tests/test_project_director_readonly_reviewer_smoke.py`

No frontend entrypoint was added. P15 does not modify `apps/web/**`.

## API Contract

Request example:

```json
{
  "source_task_id": "<p12-safe-dry-run-task-id>",
  "source_message_id": "<p14-lifecycle-result-message-id>",
  "user_confirmed": true,
  "requested_reviewer_executor": "codex",
  "review_mode": "dry_run"
}
```

Response summary:

```json
{
  "review_status": "planned",
  "readonly_review": true,
  "reviewer_agent": true,
  "executor_backed_review_allowed": true,
  "product_runtime_git_write_allowed": false,
  "worktree_write_allowed": false,
  "file_write_allowed": false,
  "real_code_modified": false,
  "git_write_performed": false,
  "native_executor_started": false,
  "codex_started": false,
  "claude_code_started": false,
  "review_result_message_bound": true,
  "ai_project_director_total_loop": "Partial"
}
```

The API writes a `p15_readonly_reviewer_review` session message and the message is readable through `GET /project-director/sessions/{session_id}/messages`. The API response does not inline the full message object, to avoid exposing generic message accounting fields in the readonly reviewer result surface.

## Evidence Summary

P15-A defines the readonly review contract. It requires:

- `readonly_review=true`
- `reviewer_agent=true`
- `executor_backed_review_allowed=true`
- `product_runtime_git_write_allowed=false`
- `worktree_write_allowed=false`
- `file_write_allowed=false`
- `real_code_modified=false`
- `git_write_performed=false`
- `native_executor_started=false` by default
- `codex_started=false` by default
- `claude_code_started=false` by default
- `ai_project_director_total_loop="Partial"`

P15-B adds the readonly review API. The API requires `user_confirmed=true`, validates that the source task is a P12 safe dry-run Task, validates that the source message belongs to the same Project Director session, and requires `source_detail="p14_controlled_subprocess_lifecycle_result"`. `review_mode=controlled_review` is blocked at the API layer.

P15-C adds an isolated smoke:

```text
Project Director session
-> P11 evidence-to-agent dry-run
-> P12 safe dry-run Task
-> P12 Worker simulate Run
-> P13 controlled executor dispatch intent
-> P14 lifecycle result message
-> P15 readonly reviewer review
-> Project Director session message readback
```

Default `dry_run` does not start Codex or Claude Code. `fake_review` generates deterministic review findings without starting Codex or Claude Code. `controlled_review` is gated by explicit safety flags and currently blocks rather than starting a real reviewer subprocess.

## Evidence Results

Default P15 dry-run smoke:

- `smoke_status="passed_dry_run"`
- `p15_review_message_bound=true`
- `message_readback_ok=true`
- `review_result_created=true`
- `review_summary_present=true`
- `recommended_next_step_present=true`
- `native_executor_started=false`
- `codex_started=false`
- `claude_code_started=false`
- `product_runtime_git_write_allowed=false`
- `worktree_write_allowed=false`
- `file_write_allowed=false`
- `real_code_modified=false`
- `git_write_performed=false`
- `ai_project_director_total_loop="Partial"`

P15 fake-review smoke:

- `smoke_status="passed_fake_review"`
- `review_findings_count=1`
- `p15_review_message_bound=true`
- `message_readback_ok=true`
- `native_executor_started=false`
- `codex_started=false`
- `claude_code_started=false`
- `product_runtime_git_write_allowed=false`
- `worktree_write_allowed=false`
- `file_write_allowed=false`
- `real_code_modified=false`
- `git_write_performed=false`

Real Codex readonly reviewer smoke:

- Not run.
- P15-C is closed from dry-run, fake-review, and safety-gate evidence only.

Real Claude readonly reviewer smoke:

- Not run.
- Claude fallback was not required for this ledger.

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
    tests/test_project_director_readonly_review_contract.py \
    tests/test_project_director_readonly_review_api.py \
    tests/test_project_director_readonly_reviewer_smoke.py \
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
  python scripts/p14_project_director_controlled_subprocess_smoke.py --json

uv run --no-project --with-editable . \
  --with 'fastapi>=0.115,<1.0' \
  --with 'httpx>=0.28,<1.0' \
  --with 'sqlalchemy>=2.0,<3.0' \
  --with 'pydantic>=2.0,<3.0' \
  python scripts/p15_project_director_readonly_reviewer_smoke.py --json

uv run --no-project --with-editable . \
  --with 'fastapi>=0.115,<1.0' \
  --with 'httpx>=0.28,<1.0' \
  --with 'sqlalchemy>=2.0,<3.0' \
  --with 'pydantic>=2.0,<3.0' \
  python scripts/p15_project_director_readonly_reviewer_smoke.py \
    --json \
    --review-mode fake_review
```

## Boundary Record

- Product runtime Git write remains forbidden.
- Worktree write remains forbidden.
- `file_write_allowed=false`.
- `real_code_modified=false`.
- `git_write_performed=false`.
- No product runtime `git add`, `git commit`, `git push`, PR, or merge was implemented or triggered.
- No reviewer output is treated as code completion, Git approval, PR approval, merge approval, or release approval.
- No pid, raw command, raw stdout, raw stderr, env, token, secret, or api_key is exposed by the P15 review result or smoke summary.
- `shell=True` was not introduced.
- Default smoke does not start Codex or Claude Code.
- Fake-review smoke does not start Codex or Claude Code.
- Controlled review requires all explicit safety flags and is not enabled in the API.
- `apps/web/**` remains unchanged.
- `docs/superpowers/**` remains untouched.
- No worktree write runner/service was called.
- AI Project Director total loop remains `Partial`.
- P9 production-safe long-running executor lifecycle remains `Partial` for this ledger because P15 did not collect new real controlled subprocess lifecycle evidence.

## Next Step

P16 should choose controlled programmer no-write execution or reviewer result hardening. Do not open product runtime Git write yet.
