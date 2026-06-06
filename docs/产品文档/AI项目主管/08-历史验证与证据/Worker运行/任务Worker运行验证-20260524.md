# BCG-05A Phase1 Verification - Created Task -> Worker Run Evidence

Date: 2026-05-24

## Scope

This verification proves that a real task created by BCG-04A can be claimed by the existing manual Worker endpoint and converted into a persisted Run.

Strict boundaries:

- No automatic Worker dispatch from `create-tasks`.
- No frontend change.
- No planning/apply call.
- No repository write.
- No AI Project Director total closure Pass.

## Worker entrypoint

`POST /workers/run-once?project_id={project_id}`

This is the existing manual single-cycle Worker endpoint. `project_id` scopes routing to tasks in the Project Director evidence project.

## Evidence chain

1. Create a project.
2. Create and confirm a Project Director session.
3. Create and confirm a Project Director plan version.
4. Force proposed task descriptions to explicit `simulate:` payloads for deterministic local execution.
5. Call `POST /project-director/plan-versions/{id}/create-tasks`.
6. Assert the response contains real `created_task_ids`.
7. Assert no `RunTable` rows exist for those tasks before Worker execution.
8. Call `POST /workers/run-once?project_id={project_id}`.
9. Assert Worker response: `claimed=true`, `task_id` is one of `created_task_ids`, `run_id` exists, `execution_mode=simulate`, `task_status=completed`, `run_status=succeeded`.
10. Assert DB persistence: `TaskTable.source_draft_id == pdv:{plan_version_id}:{version_no}`, `TaskTable.status=completed`, `RunTable.task_id == TaskTable.id`, `RunTable.status=succeeded`, `RunTable.quality_gate_passed=True`, and `RunTable.log_path` is persisted.

## Executor mode

The test uses explicit `simulate:` input summaries.

- `simulate` executor: yes.
- `provider_mock`: no.
- `provider_reported`: no.
- Real Provider/network call: no.

Reason: this phase is a deterministic Phase1 bridge evidence test for created task -> manual Worker -> Run persistence. Provider-reported runtime evidence remains a separate gate.

## Tests

New test file:

- `runtime/orchestrator/tests/test_project_director_worker_run_evidence.py`

Primary test:

- `test_created_project_director_task_can_be_claimed_by_worker_and_create_run`

Command run:

```powershell
cd runtime/orchestrator
.\.venv\Scripts\python.exe -m pytest tests/test_project_director_worker_run_evidence.py tests/test_project_director_task_creation.py -q
```

Result:

```text
19 passed, 1 warning
```

The warning is the existing `HTTP_422_UNPROCESSABLE_ENTITY` deprecation warning from the BCG-04A rollback test.

## Gate conclusion

BCG-05A: Partial / Phase1 evidence pass.

- Created Task -> manual Worker claim -> persisted Run: Pass with simulate executor.
- Automatic dispatch: Not in scope.
- Provider-reported Worker runtime evidence: Missing.
- AI Project Director total closure: Partial, not Pass.
