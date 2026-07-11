# Open-Source Readiness Design

## Objective

Prepare AI-Dev-Orchestrator for maintainer review before an application to
OpenAI Codex for Open Source and Codex Security. The work improves public
documentation, repository governance, contributor guidance, and release
preparation without changing application behavior.

## Baseline And Scope

- Base all work on `origin/main` commit
  `60f95b0c526cb2ac7221ac24a4cd1be55ff69faf`.
- Deliver on `chore/oss-readiness`; do not push to or merge into `main`.
- Do not modify application behavior, APIs, orchestration logic, dependencies,
  schemas, provider integrations, or production configuration.
- Preserve the existing untracked `.mimocode/`, `docs/superpowers/`, and root
  `uv.lock` paths without editing, deleting, moving, or committing them.
- Treat the user's attached requirements as the authoritative implementation
  specification.

## Evidence And Claim Policy

Public capability claims must map to current code, tests, repository
documentation, or Git history. The public documents will distinguish:

- demonstrated capabilities;
- controlled, bounded, or dry-run-only paths;
- partial or experimental integrations;
- roadmap items that are not implemented.

No document will claim adoption, production hardening, formal security,
benchmark results, completed end-to-end automation, or other facts that the
repository cannot prove.

## Documentation Design

The English and Chinese READMEs will share the same factual structure and link
to each other. They will position the project as an early-stage maintainer
preview, explain the problem and trust model, document verified development
commands, and state limitations next to the relevant capabilities.

Supporting public documents will separate responsibilities:

- `SECURITY.md`: reporting policy and project-specific security concerns;
- `docs/THREAT_MODEL.md`: assets, boundaries, threats, implemented controls,
  known gaps, and residual risk;
- `docs/PROJECT_STATUS.md`: demonstrated, partial, and unimplemented status;
- `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md`: contributor expectations;
- `.github/`: structured issue and pull-request intake;
- `docs/OPEN_SOURCE_BACKLOG.md`: contribution-ready work derived from gaps;
- `CHANGELOG.md` and `docs/releases/v0.1.0-alpha.md`: unpublished alpha release
  preparation.

The README architecture diagram will describe only the verified lifecycle:
human intent and approval, orchestration and evidence, bounded execution,
verification, read-only or independent review where supported, and recorded
outcomes.

## License Decision

Add the official Apache License 2.0 text only after checking repository history,
source notices, copied material, and dependency metadata for conflicts or
uncertainty. If that review cannot establish a responsible decision, omit the
license and record the exact maintainer decision required.

## Repository Organization

Limit root cleanup to tracked files with clear evidence:

- remove `.__e_repo_write_test__.txt` because it is a one-off write probe;
- preserve `FRONTEND_STRUCTURE_CLOSURE_REPORT.md` as history by moving it to
  `docs/archive/`, retaining its bytes unless a separate encoding repair is
  clearly safe and useful;
- leave unrelated tracked and all pre-existing untracked content untouched.

Update `.gitignore` only if repository evidence identifies a recurring generated
artifact that is not already covered.

## Validation And Delivery

Validation will cover the existing relevant backend tests, Python compilation,
the frontend production build, safely executable README setup commands,
relative Markdown links, sensitive-data patterns, English/Chinese claim
consistency, and the complete Git diff. Validation must also prove that no
application source or dependency declaration changed.

Use scoped commits grouped by public overview, security, collaboration,
organization, and release preparation. After validation, push the feature
branch and create a draft pull request targeting `main`. Update the GitHub
description and topics only through the authenticated maintainer account; do
not create Issues, publish a Release, or merge the pull request.

## Failure Handling

- A failing command is reported accurately and investigated before delivery.
- A broken README command is corrected in documentation unless the smallest
  necessary non-behavioral fix is explicitly justified.
- Unsupported claims are removed or downgraded rather than rationalized.
- License uncertainty blocks adding `LICENSE`, but does not block the remaining
  documentation work.
- GitHub permission or API failure leaves repository metadata unchanged and is
  documented with exact manual commands.
