# Open-Source Contribution Backlog

These proposals come from gaps observed in the current repository. They are not
promises, assigned work, or evidence of existing contributors. Before starting,
open a Feature request to confirm scope with the maintainer.

## 1. Reduce Backend Warnings And Clarify Test Scopes

**Scope:** Triage the current Starlette/httpx, naive UTC, and related deprecation
warnings. Define documented full-suite, focused-contract, smoke, and live-test
scopes without silently excluding important tests.

**Expected result:** The canonical backend suite remains green with a materially
smaller warning count and contributors can identify which tests require external
tools or explicit live flags.

**Relevant files:**

- `runtime/orchestrator/app/services/event_stream_service.py`
- `runtime/orchestrator/pyproject.toml`
- `runtime/orchestrator/tests/`
- `runtime/orchestrator/scripts/`
- public contribution and project-status documentation

**Acceptance criteria:**

- warning categories and counts are captured before changes;
- datetime behavior remains timezone-correct and regression-tested;
- focused tests and the canonical full suite remain green;
- live provider/native tests stay opt-in and visibly separated;
- [Project Status](PROJECT_STATUS.md) is updated with fresh evidence.

## 2. Add A Minimal, Non-Publishing CI Workflow

**Scope:** Add pull-request CI for backend tests, Python compilation, frontend
install/build, issue-form YAML, Markdown links, and secret scanning. Do not add
automatic release publishing or deployment.

**Expected result:** Contributors receive reproducible checks for the public
development contract on supported runner versions.

**Relevant files:**

- `.github/workflows/`
- `runtime/orchestrator/pyproject.toml`
- `apps/web/package.json`
- public Markdown and `.github/ISSUE_TEMPLATE/*.yml`

**Acceptance criteria:**

- least-privilege workflow permissions are explicit;
- no live provider or executor credential is required;
- dependency caches do not contain secrets or runtime data;
- required and optional checks are clearly distinguished;
- branch protections and release publication remain maintainer decisions.

## 3. Define Reproducible Backend Dependency Locking

**Scope:** Choose and document a portable uv workflow for the backend, including
whether `runtime/orchestrator/uv.lock` should be committed and how root-level
Python metadata should relate to the backend project.

**Expected result:** A fresh clone can install the same backend dependency graph
without copying a maintainer's virtual environment.

**Relevant files:**

- `pyproject.toml`
- `runtime/orchestrator/pyproject.toml`
- `runtime/orchestrator/README.md`
- `.gitignore`
- root READMEs and contribution guide

**Acceptance criteria:**

- the maintainer approves the chosen project root and lockfile location;
- clean-clone setup is tested on at least one declared Python version;
- installation does not require committed secrets or runtime data;
- dependency and license changes are reviewed;
- all public setup commands use the same workflow.

## 4. Publish Provider-Specific Setup And Safety Guidance

**Scope:** Document OpenAI and generic OpenAI-compatible configuration, model
tier mapping, endpoint trust, credential storage, timeout behavior, and a safe
connectivity test using redacted output.

**Expected result:** A contributor can understand what is local, what is sent to
the provider, and how to disable or remove saved credentials.

**Relevant files:**

- `runtime/orchestrator/app/services/provider_config_service.py`
- `runtime/orchestrator/app/services/openai_provider_executor_service*.py`
- `runtime/orchestrator/app/api/routes/provider_settings.py`
- provider tests and public security documentation

**Acceptance criteria:**

- no live key or private endpoint appears in tests or documentation;
- saved-config precedence and deletion/rotation are documented;
- provider compatibility is not generalized beyond tested behavior;
- example output masks credentials and sensitive response data;
- threat-model data-flow entries are updated.

## 5. Add Adversarial Sandbox Boundary Tests

**Scope:** Test traversal, symlinks, path replacement races, absolute paths,
Unicode normalization, Git hooks, nested worktrees, oversized manifests, and
workspace-root misconfiguration across sandbox-oriented services.

**Expected result:** Application-level containment assumptions and remaining OS
isolation gaps are explicit and regression-tested.

**Relevant files:**

- `project_director_sandbox_workspace_guard_service.py`
- `project_director_sandbox_operation_manifest_guard_service.py`
- `project_director_sandbox_candidate_file_write_service.py`
- `project_director_sandbox_workspace_creation_service.py`
- corresponding sandbox contract/API/smoke tests

**Acceptance criteria:**

- negative cases use temporary directories and never touch the developer's main
  worktree;
- tests cover POSIX and Windows path semantics where the code supports both;
- blocked results preserve stable, documented reasons;
- no test launches a live provider or performs a push;
- discovered non-mitigated risks are added to [Threat Model](THREAT_MODEL.md).

## 6. Validate Review Independence And Replay Resistance End To End

**Scope:** Build a deterministic integration test from candidate diff through
review handoff, reviewer output validation, disposition, freshness revalidation,
single consumption, and bounded handoff. Include changed-diff and duplicate-use
attacks.

**Expected result:** The exact flows protected against stale, mismatched, or
replayed decisions are understandable without internal phase knowledge.

**Relevant files:**

- `project_director_sandbox_candidate_diff_*review*` services and domains
- readonly reviewer transports and resolver
- disposition consumption and handoff tests

**Acceptance criteria:**

- a fake deterministic reviewer covers success without external credentials;
- diff, prompt, scope, schema, and fingerprint mismatches are rejected;
- repeated consumption is rejected atomically;
- audit messages can be read back in stable order;
- documentation states which other mutation paths remain outside this chain.

## 7. Add Audit Export And Redaction Guidance

**Scope:** Inventory audit/event records and define a read-only export format that
redacts secrets, private paths, prompts, and repository content by default.

**Expected result:** Maintainers can collect useful diagnostic evidence without
copying raw runtime databases or leaking credentials.

**Relevant files:**

- runtime, delivery, dispatch, workspace-lifecycle, and recovery audit services
- task/run logging and agent-message repositories
- API schemas and security documentation

**Acceptance criteria:**

- export is read-only and bounded by explicit project/session/run identifiers;
- sensitive fields have documented default redaction;
- tests include credential-like and private-path fixtures;
- output schema and compatibility policy are documented;
- no tamper-proof or compliance guarantee is claimed.

## 8. Prepare Non-Automatic Alpha Release Validation

**Scope:** Add a maintainer-triggered workflow or script that verifies version
consistency, changelog/release notes, tests, frontend build, links, license text,
and artifact contents without publishing a GitHub Release.

**Expected result:** The maintainer receives a reproducible release-candidate
report and can make the publication decision separately.

**Relevant files:**

- `CHANGELOG.md`
- `docs/releases/v0.1.0-alpha.md`
- Python and web package metadata
- future validation scripts or `.github/workflows/`

**Acceptance criteria:**

- default execution cannot publish, tag, push, or upload artifacts;
- versions and maturity labels are checked for consistency;
- generated archives exclude credentials, runtime data, local environments, and
  internal-only files;
- rollback instructions are included;
- publishing remains an explicit maintainer action.

## 9. Remediate Frontend Dependency Advisories

**Scope:** Review the current npm advisories for `postcss`, `react-router-dom`,
`vite`, and affected transitive packages. Upgrade only through a compatibility-
tested change; do not use an unreviewed forced major-version update.

**Expected result:** The production dependency audit has no unresolved high or
critical finding, or each remaining finding has a documented applicability and
maintainer-approved risk decision.

**Relevant files:**

- `apps/web/package.json`
- `apps/web/package-lock.json`
- `apps/web/src/app/router.tsx`
- `apps/web/vite.config.ts`
- web build and script tests

**Acceptance criteria:**

- current advisory IDs and affected ranges are recorded before changing versions;
- `npm ci`, `npm run build`, and directly affected routing/UI tests pass;
- Vite proxy behavior and production output are checked;
- lockfile license changes are reviewed;
- no audit result is suppressed solely to make the report green.
