# OSS Readiness Test Contract Follow-Up

## Reverted Test Files

The following four files were modified during readiness work to align stale test
contracts with the current runtime. They have been reverted to their `main`
branch state so the OSS readiness PR remains documentation-only:

1. `runtime/orchestrator/scripts/smoke_bcl01_provider_test.py`
2. `runtime/orchestrator/tests/test_external_executor_module_boundary.py`
3. `runtime/orchestrator/tests/test_project_director_run_evidence_replay.py`
4. `runtime/orchestrator/tests/test_project_director_worker_run_evidence.py`

## Why Not Included In The OSS PR

The OSS readiness branch is scoped as a documentation-only change set. Test file
modifications alter observable repository behavior and should be reviewed as code
changes, not bundled with documentation, security policy, CI scaffolding, and
release notes. Keeping the PR documentation-only makes review simpler and avoids
mixing concerns.

## Behavior Differences

Each reverted test targets a seam that has evolved since the test was written:

| File | Difference |
| --- | --- |
| `smoke_bcl01_provider_test.py` | The provider request seam and receipt field moved to a V2 SDK shape; the legacy assertion expects the older request format. |
| `test_external_executor_module_boundary.py` | The boundary rule now permits orchestration-level imports from the dedicated external-executor package while continuing to reject direct process-launch imports. |
| `test_project_director_run_evidence_replay.py` | The runtime launch gate is now authoritative over a requested simulate path; the old test expected the simulate request to override the gate. |
| `test_project_director_worker_run_evidence.py` | Blocked-run evidence is now persisted and replayable; the old assertion expected the blocked state to prevent evidence capture. |

## What's Needed For An Independent PR

A follow-up pull request should:

1. update each test to target the current contract seam and field names;
2. verify that each test passes against the current backend without modifying
   production code;
3. include the focused test run output in the PR description;
4. keep changes scoped to test alignment — no unrelated refactors;
5. note any production-code surface change that the test update implies.
