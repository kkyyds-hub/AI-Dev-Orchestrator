# Project Status

Last reviewed against `origin/main` commit
`60f95b0c526cb2ac7221ac24a4cd1be55ff69faf` on 2026-07-11.

## Development Stage

**Early-stage / Maintainer Preview / Experimental**

AI-Dev-Orchestrator is a local-first research and development repository. It has
a broad application surface and extensive contract tests, but it is not a
published, supported, or production-hardened product. Internal phase names in
historical documents represent incremental development slices, not release or
security certification levels.

## Demonstrated Functionality

The following is implemented in current code and exercised by repository tests
or smoke scripts:

| Capability | Evidence |
| --- | --- |
| FastAPI application, health endpoint, and modular API routers | `runtime/orchestrator/app/main.py`, `app/api/router.py`, route tests |
| React/Vite local control surface | `apps/web/src`, successful `npm run build` validation recorded in this readiness work |
| Project, task, run, approval, repository, deliverable, agent, cost, and console domain surfaces | `app/api/routes`, `app/domain`, `app/repositories`, corresponding tests |
| SQLite-backed state and JSONL run logging | `app/core/db.py`, `app/core/db_tables.py`, `app/services/run_logging_service.py` |
| Simulated and local-command task execution with verification | `app/services/executor_service.py`, `verifier_service.py`, `app/workers/task_worker.py` |
| Routing, retry, budget, and concurrency controls | task router, budget guard, state machine, worker pool, and related tests |
| Mock and OpenAI-compatible provider service abstractions | `mock_provider_executor_service.py`, `openai_provider_executor_service*.py`, `provider_config_service.py` |
| Bounded external-executor preflight, launch, supervision, and readback components | `app/external_executors`, targeted contract tests and controlled smoke scripts |
| Sandbox-oriented workspace root, manifest, candidate-write, and diff stages | `project_director_sandbox_*` domains/services and contract/API/smoke tests |
| Read-only reviewer handoff, transport, validation, and disposition stages for selected flows | `project_director_*readonly_review*`, reviewer transport modules, targeted tests |
| Review/diff binding and fresh disposition consumption | SHA-256 and fingerprint validation in candidate-diff review services and tests |
| Human approval and escalation records | `app/domain/human_approval_gate.py`, approval services/routes, approval tests |
| Local audit-oriented event and message records | runtime, delivery, dispatch, workspace-lifecycle, recovery, task/run, and agent-message services |

“Demonstrated” means the repository contains the behavior and focused evidence.
It does not mean every combination, provider, host, or adversarial condition has
been tested.

## Partial Or Experimental Functionality

| Capability | Current boundary |
| --- | --- |
| Real native executors | Components and guarded smoke paths exist, but many tests use fakes or explicit controlled-smoke flags. This is not an unattended production executor platform. |
| Read-only independent review | Supported in selected Project Director chains; it is not a mandatory stage for every execution or write path. |
| Sandbox execution | Workspace containment and candidate-write controls exist at the application layer. There is no general OS/container isolation guarantee. |
| Provider-backed execution | OpenAI-compatible configuration and services exist. Real behavior depends on external credentials, endpoints, models, and provider policies. |
| Product-runtime Git operations | Multiple dry-run, preview, guard, and pilot components exist. Permission is deliberately false in many contracts; total automated Git delivery is not claimed. |
| Evidence integrity | Hashes, IDs, schema validation, freshness checks, and append-oriented records cover selected chains. Local evidence is not signed or tamper-proof against host compromise. |
| Cost accounting | Current values include estimates and configured price logic; they are not independently reconciled provider billing records. |
| Web/backend coverage | The control surface covers many backend domains, but historical and experimental pages may not represent a fully integrated end-to-end user journey. |

## Not Yet Established

- a stable installation package or one-command production deployment;
- committed CI/CD, automated release publishing, or supported release channels;
- authentication, authorization, multi-tenancy, or hardened remote operation;
- formal security verification, independent audit, or a security SLA;
- OS-enforced sandboxing for every executor;
- universal independent review and human approval across every mutation path;
- cryptographically signed evidence, builds, or releases;
- verified support for every OpenAI-compatible provider and model;
- a public adoption, contributor, download, or production-usage record;
- a verified private vulnerability reporting channel.

## Current Validation Baseline

On 2026-07-11, before changing public documentation, the existing backend suite
was run from `runtime/orchestrator` with:

```bash
./.venv/bin/python -m pytest -q --tb=short
```

Result: **3,462 passed, 10 failed, 3,005 warnings** in 365.18 seconds.

The failures were present without application-source changes from this branch:

- seven assertions in `scripts/smoke_bcl01_provider_test.py` target an older
  provider connectivity contract (`provider_receipt_id` and the removed
  `_post_json_request` seam);
- `tests/test_external_executor_module_boundary.py` expects no external executor
  import in `task_worker.py`, while the current worker includes the later runtime
  integration;
- `tests/test_project_director_run_evidence_replay.py` expects completion where
  the current launch gate blocks;
- `tests/test_project_director_worker_run_evidence.py` expects `simulate` where
  the current result reports `runtime_launch_gate`.

This readiness branch does not repair those contracts because its scope excludes
application behavior and test changes. Focused tests used as evidence must still
be run and reported separately; a passing focused test does not make the complete
baseline green.

The verified frontend commands completed successfully:

- `npm ci`: installed 270 packages;
- `npm run build`: TypeScript and Vite build passed, with a chunk-size warning;
- `npm audit`: 8 findings (1 low, 2 moderate, 5 high);
- `npm audit --omit=dev`: 3 high findings.

The affected audit entries include direct dependencies `postcss`,
`react-router-dom`, and `vite`, plus transitive packages. This branch does not
change dependency versions because dependency and compatibility changes are
outside its scope.

## Known Limitations

- Runtime data and saved provider configuration are local files; operators must
  protect them and avoid committing them.
- A process started by the orchestrator can inherit the current user's privileges.
- Historical documentation is extensive and includes internal status language
  that should not be treated as current public release status.
- The backend README contains long phase-specific smoke guidance; the root README
  is the public starting point.
- Frontend dependencies are locked, while Python uses bounded dependency ranges
  and does not currently commit a backend lockfile.
- There is no repository-level CI to enforce test, build, link, secret, or license
  checks for pull requests.

## Near-Term Priorities

1. Restore a green, clearly scoped backend test baseline.
2. Triage and remediate the current frontend dependency advisories with focused
   compatibility and regression testing.
3. Add CI for backend tests, frontend build, Markdown links, secrets, dependencies,
   and license checks.
4. Define a reproducible backend dependency lock and supported developer matrix.
5. Validate sandbox and reviewer boundaries with adversarial security tests.
6. Document and test provider-specific setup without committing credentials.
7. Enable private vulnerability reporting and establish a security response path.
8. Automate alpha release validation without automatically publishing releases.

Detailed contribution scopes are in [Open-Source Backlog](OPEN_SOURCE_BACKLOG.md).
