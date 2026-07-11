# Contributing To AI-Dev-Orchestrator

Thank you for considering a contribution. This repository is an early-stage
maintainer preview, so clarity about scope and maturity is as important as the
change itself.

## Before You Start

- Read [README.md](README.md), [Project Status](docs/PROJECT_STATUS.md),
  [Security Policy](SECURITY.md), and [Threat Model](docs/THREAT_MODEL.md).
- Search existing Issues and pull requests before proposing overlapping work.
- For a security vulnerability, do not open a normal Issue. Follow
  [SECURITY.md](SECURITY.md).
- Prefer a focused change that preserves existing service, domain, repository,
  route, worker, and feature boundaries.

## Project Maturity

The project is experimental. A file, route, or internal phase document does not
by itself prove a production-ready capability. Contributions must distinguish:

- behavior demonstrated by current code and tests;
- partial, guarded, dry-run, fake, or controlled-smoke behavior;
- planned work that is not implemented.

Do not add claims about users, adoption, downloads, performance, production use,
security guarantees, provider compatibility, or completed workflows without
verifiable repository evidence.

## Development Setup

### Backend

Requirements: Python 3.11-3.13 and `uv`.

```bash
cd runtime/orchestrator
RUNTIME_DATA_DIR="$(mktemp -d)" uv run --no-project --with-editable . \
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8011
```

Run backend tests with an isolated uv environment:

```bash
cd runtime/orchestrator
uv run --no-project --with-editable . --with pytest \
  pytest -q tests
```

The complete current baseline has known failures documented in
[Project Status](docs/PROJECT_STATUS.md). In a pull request, report both the
focused tests relevant to your change and any full-suite failures. Do not hide or
relabel a failing test as passing.

Compile the backend and scripts:

```bash
cd runtime/orchestrator
uv run --no-project --with-editable . \
  python -m compileall -q app scripts
```

### Web

```bash
cd apps/web
npm ci
npm run build
```

For local development, run
`VITE_BACKEND_URL=http://127.0.0.1:8011 npm run dev` after the backend is
available at `http://127.0.0.1:8011`.

## Branches And Commits

- Create a branch from the latest `main`.
- Use a short descriptive branch such as `docs/provider-setup`,
  `fix/review-freshness`, or `chore/oss-readiness`.
- Keep commits scoped and reviewable.
- Prefer clear commit subjects such as `docs: clarify reviewer boundaries`,
  `test: cover stale disposition rejection`, or `fix: contain sandbox path`.
- Do not mix unrelated formatting, generated output, or local editor files into
  the same commit.
- Do not force-push over another contributor's work without coordination.

## Change Requirements

### Code

- Follow the existing architecture and naming patterns.
- Keep API and persistence compatibility in mind. Call out schema, migration,
  default-value, and rollback implications.
- Add or update focused tests for behavioral changes.
- Prefer deterministic tests that do not require live credentials or external
  providers.
- Keep fake, preview, dry-run, controlled-smoke, and real execution modes
  visibly distinct.

### Documentation

- Update public documentation when setup, configuration, behavior, limitations,
  or security boundaries change.
- Verify every command you add.
- Keep English and Chinese README claims aligned when the public overview changes.
- Use normal-language maturity labels; explain internal phase identifiers when
  they are necessary.
- Mark incomplete functionality as planned, partial, experimental, or blocked.

### Security-Sensitive Changes

Changes involving executors, shell commands, filesystem writes, Git operations,
provider calls, credentials, prompts, review decisions, approval, evidence, or
audit records require additional scrutiny:

- identify assets and trust boundaries affected;
- document new entry points and failure modes;
- add negative tests for bypass and malformed input;
- show how paths, scope, source evidence, and permissions are bound;
- preserve timeouts, output limits, cleanup, and blocked-state behavior;
- update [Threat Model](docs/THREAT_MODEL.md) when the risk model changes;
- include rollback or disablement guidance;
- request maintainer review before enabling a real external action by default.

Do not include exploit details in a public pull request if the vulnerability is
not already safely resolved and coordinated.

## Secrets And Local Data

Never commit:

- API keys, tokens, passwords, cookies, private keys, or `.env` files;
- provider configuration containing credentials;
- runtime databases, logs, prompts, diffs, or evidence with private data;
- private repository URLs, internal network addresses, or personal data;
- copied terminal output that exposes credentials or user directories without a
  clear need and redaction.

Before committing, inspect `git diff --cached` and the exact staged file list.
Avoid broad staging commands when unrelated local files exist.

## Pull Requests

A pull request should include:

- the problem and intentionally limited scope;
- the implementation summary;
- security and compatibility impact;
- exact tests, builds, smoke checks, and manual evidence;
- documentation changes or a reason none are needed;
- known failures, limitations, and experimental behavior;
- rollback considerations;
- confirmation that no secrets or private data were added.

Draft pull requests are appropriate for early feedback, but they should still
state what is incomplete. Maintainers may ask for a smaller scope or stronger
evidence before review.

## Reporting Incomplete Behavior

Use direct status language:

- **Demonstrated:** code plus current focused evidence exists.
- **Partial / Experimental:** only some paths or environments are covered.
- **Planned:** no implementation should be inferred.
- **Blocked:** a named dependency or decision prevents progress.

Avoid “done,” “secure,” “fully integrated,” or “production-ready” unless the pull
request supplies evidence for the complete claim.

## Community Conduct

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
