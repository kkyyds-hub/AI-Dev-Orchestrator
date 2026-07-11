# Threat Model

## Scope And Maturity

This threat model covers the local FastAPI backend, React control surface,
SQLite and file-based runtime data, provider integrations, native executors,
sandbox-oriented Project Director stages, reviewer transports, and human
approval records in the current repository.

It is a practical maintainer model, not a formal security proof. Controls marked
**implemented** have a current code or test anchor. Controls marked **partial**
apply only to selected flows or rely on operator configuration. **Planned** items
are not present safeguards.

## Assets

- source repositories and uncommitted worktrees;
- credentials, provider keys, Git credentials, and executor sessions;
- task goals, prompts, repository excerpts, diffs, and review output;
- SQLite state, JSONL logs, evidence packs, manifests, and audit messages;
- human approvals, review dispositions, and source bindings;
- availability and integrity of the developer workstation;
- external provider accounts and usage budgets.

## Actors

- a trusted maintainer or operator;
- a contributor whose code or Issue content may be benign or malicious;
- an AI model or coding executor that can misunderstand or ignore intent;
- an external provider or compromised provider account;
- a malicious or compromised dependency;
- a local process running under the same user;
- an attacker with repository, runtime-data, or host access.

## Trust Boundaries

1. **Human to control plane:** goals and confirmations enter FastAPI routes or the
   web interface.
2. **Repository content to model context:** untrusted files, commits, Issues, and
   diffs can become prompts or evidence.
3. **Control plane to shell/native executor:** commands cross into a process with
   operating-system privileges.
4. **Main repository to sandbox-oriented workspace:** candidate paths and writes
   must remain under backend-selected roots.
5. **Local system to external provider:** prompts and metadata leave the host.
6. **Execution to verification/review:** generated changes and output become
   evidence for later decisions.
7. **Evidence to disposition/human action:** a stored review can influence the
   next workflow stage.
8. **Application records to host storage:** SQLite and JSONL integrity ultimately
   depends on the local account and filesystem.

## Entry Points

- FastAPI routes under `runtime/orchestrator/app/api/routes`;
- the web control surface under `apps/web/src`;
- task descriptions, repository files, diffs, logs, and uploaded/copied text;
- environment variables and saved provider configuration;
- local verification commands and native executor processes;
- SQLite databases and runtime-data files;
- external provider and reviewer responses;
- Git state, worktrees, hooks, and dependency installation.

## Threats And Current Controls

| Threat | Existing mitigation | Status and evidence |
| --- | --- | --- |
| Repository prompt injection changes agent intent | Explicit workflow contracts, forbidden-action fields, confirmation requirements, and separate stages reduce implicit authority | **Partial:** `app/services/project_director_*`, especially `project_director_sandbox_workspace_guard_service.py`; no general prompt-injection detector |
| Arbitrary or unsafe process launch | Preflight contracts, explicit native launch modes, timeout/termination and process-supervisor components | **Partial:** `app/external_executors/actual_preflight.py`, `actual_native_launcher.py`, `actual_process_supervisor.py`; native processes still inherit host privileges |
| Write outside an intended workspace | Backend-owned workspace root, name policy, containment checks, operation manifests, and candidate-file services | **Implemented for selected stages:** `project_director_sandbox_workspace_guard_service.py`, `project_director_sandbox_operation_manifest_guard_service.py`, `project_director_sandbox_candidate_file_write_service.py`; covered by corresponding `tests/test_project_director_sandbox_*` suites |
| Main-worktree or Git mutation during guarded review/execution | Many guarded contracts force `product_runtime_git_write_allowed=false` and record forbidden actions | **Partial:** `app/external_executors/*`, Project Director sandbox domains/services; other local-command features are not an OS-enforced no-write boundary |
| Review uses a different diff, prompt, or scope | SHA-256 bindings, schema validation, review-scope checks, and source-message validation | **Implemented for the P21 candidate-diff chain:** `project_director_sandbox_candidate_diff_review_output_validation_service.py` and review contract tests |
| Stale or replayed review disposition is accepted | Current diff regeneration, fingerprint revalidation, SQLite immediate transaction, and append-only consumption record | **Implemented for the disposition-consumption chain:** `project_director_sandbox_candidate_diff_review_disposition_consumption_service.py`, its preflight service, and contract tests |
| Review stage is silently skipped | Separate review handoff, execution preflight, reviewer adapter, and disposition services expose explicit status and blocking reasons | **Partial:** selected Project Director flow only; independent review is not universal |
| Human approval is forged or bypassed | Approval domain models validate readiness, evidence, expiration/revocation, blocking reasons, and operation constraints | **Partial:** `app/domain/human_approval_gate.py`, `app/services/approval_service.py`, `tests/test_human_approval_gate.py`, `tests/test_delivery_human_approval_api.py`; no external identity provider |
| Secrets leak through configuration or output | `.env` patterns are ignored, provider API summaries mask keys, selected preflight summaries reject credential-like text | **Partial:** `.gitignore`, `provider_config_service.py`, `actual_preflight.py`; saved provider config can contain a raw key and logs/prompts need operator redaction |
| Provider output or endpoint is malicious | Provider configuration is normalized and calls are behind service abstractions | **Partial:** `provider_config_service.py`, `openai_provider_executor_service*.py`, `mock_provider_executor_service.py`; endpoint trust and response safety remain operator concerns |
| Audit records are missing | Runtime, delivery, dispatch, workspace lifecycle, recovery, task/run, and message records are persisted | **Implemented as local application records:** `runtime_event_audit_service.py`, `delivery_event_audit_service.py`, `agent_dispatch_audit_service.py`, `workspace_lifecycle_audit_service.py`, repositories and tests |
| Audit evidence is modified after the fact | Some workflows append rather than overwrite and bind records with IDs/hashes | **Partial:** local SQLite/JSONL data is not signed or protected from a compromised host |
| Dependency compromise | Lockfiles constrain resolved frontend packages; Python dependencies have bounded version ranges | **Partial:** `apps/web/package-lock.json`, `runtime/orchestrator/pyproject.toml`; no committed CI scanning, provenance policy, or SBOM |
| Denial of service or unbounded spend | Request timeouts, reviewer output limits, budget guards, retry limits, and worker concurrency settings | **Partial:** `app/core/config.py`, budget and worker services; no distributed rate limiting or tenant quotas |

Paths in this table are relative to `runtime/orchestrator/` unless stated
otherwise.

## Known Gaps

- No application authentication, authorization, role isolation, or multi-tenant
  security model is established.
- Application-level workspace containment is not an OS sandbox, container, VM,
  mandatory access-control policy, or formal capability system.
- Native processes can inherit the invoking user's filesystem, environment, Git
  credentials, and network access.
- Provider configuration may persist a raw API key in the runtime data directory.
- There is no committed secret scanning, dependency scanning, SAST, CodeQL,
  release signing, SBOM, or CI policy.
- Audit evidence is not cryptographically signed, remotely anchored, or protected
  from a compromised local account.
- Independent reviewer enforcement is not universal across all task, patch, and
  Git-write flows.
- Symlink, mount, hook, and race-condition resistance has not been independently
  validated as a complete sandbox boundary.
- The backend suite currently emits thousands of deprecation warnings; warning
  reduction and dependency compatibility remain maintenance work. See
  [Project Status](PROJECT_STATUS.md).
- The current frontend lockfile reports npm audit findings, including high
  severity findings in the production-dependency view; no compatibility-reviewed
  remediation is included in this documentation-only branch.
- GitHub private vulnerability reporting is not enabled as of this review.

## Planned Mitigations

These are backlog proposals, not implemented controls:

- add CI with tests, build, secret scanning, dependency review, and CodeQL;
- define a supported container or disposable-VM execution profile;
- move provider secrets to an OS keychain or external secret store;
- add adversarial tests for prompt injection, symlink traversal, TOCTOU path
  changes, malicious Git hooks, and reviewer replay;
- sign or externally anchor high-value evidence and release artifacts;
- enforce reviewer independence and approval policy across additional mutation
  paths;
- add authentication and authorization before any remote or multi-user use;
- publish dependency inventory and SBOM generation guidance;
- enable private vulnerability reporting and document a verified contact.

See [Open-Source Backlog](OPEN_SOURCE_BACKLOG.md) for contribution-ready scopes.

## Residual Risk

Even when every current gate passes, an AI-generated patch may be unsafe, a
verification command may be incomplete, a reviewer may be wrong, and a local
process may exceed the intended application boundary. A compromised host or user
account can modify source and evidence together. Human review, least privilege,
isolated environments, backups, and independent security assessment remain
necessary for sensitive use.

## Review Triggers

Update this model when a change introduces or materially alters:

- a native executor, provider, or network integration;
- a filesystem or Git write path;
- an approval, reviewer, or disposition contract;
- credential storage or logging;
- authentication, authorization, or remote deployment;
- evidence storage, hashing, or lifecycle behavior;
- release, CI, or dependency provenance controls.
