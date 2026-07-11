# Open-Source Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an evidence-grounded, bilingual open-source readiness package, repository cleanup, validated GitHub metadata, and a draft pull request without changing product behavior.

**Architecture:** Treat repository evidence as the source of truth and build public documentation around a shared capability/status vocabulary. Keep policy, threat model, contribution workflow, project status, backlog, and release preparation in focused files; validate the complete public surface before any push or draft PR.

**Tech Stack:** Markdown, GitHub issue forms and pull-request templates, Git, GitHub CLI, Python/FastAPI tests, TypeScript/Vite build tooling.

---

### Task 1: Establish The Evidence And License Baseline

**Files:**
- Inspect: `runtime/orchestrator/app/`
- Inspect: `runtime/orchestrator/tests/`
- Inspect: `apps/web/src/`
- Inspect: `runtime/orchestrator/pyproject.toml`
- Inspect: `apps/web/package-lock.json`
- Inspect: Git history and tracked documentation

- [ ] **Step 1: Record the exact source baseline and protected paths**

Run:

```bash
git rev-parse origin/main
git status --short --branch
```

Expected: `origin/main` is `60f95b0c526cb2ac7221ac24a4cd1be55ff69faf`, the branch is `chore/oss-readiness`, and only the known user-owned untracked paths are present.

- [ ] **Step 2: Map publishable capabilities to code and tests**

Inspect the bounded executor, sandbox workspace, read-only reviewer, evidence gate, approval, provider abstraction, stale/replay protection, and audit-record paths. Record only claims that have a concrete implementation or test anchor; mark dry-run or guarded paths accordingly.

- [ ] **Step 3: Review licensing provenance**

Search tracked source and history for copyright/license notices, inspect direct dependency metadata and lockfile package licenses where available, and distinguish dependency licenses from repository code licensing.

- [ ] **Step 4: Decide whether Apache-2.0 can be added**

Expected: add the official Apache License 2.0 text only if no conflicting repository-code notice or copied incompatible code is identified; otherwise document the maintainer decision required.

### Task 2: Build The Bilingual Public Overview

**Files:**
- Create: `README.md`
- Create: `README.zh-CN.md`
- Create when allowed: `LICENSE`

- [ ] **Step 1: Write the English README**

Include language navigation, project status, audience, problem statement, verified capabilities, lifecycle diagram, trust model, architecture, repository map, verified development setup, configuration, example workflow, limitations, roadmap, contribution, security, and license sections.

- [ ] **Step 2: Write the Chinese README**

Mirror the English claims and status distinctions in natural concise Chinese. Do not add capabilities or certainty absent from the English source.

- [ ] **Step 3: Add the license when the Task 1 decision permits**

Use the unmodified official Apache License 2.0 text and identify it as the repository license in both READMEs.

- [ ] **Step 4: Verify README commands incrementally**

Run safe version, install, backend smoke/startup, frontend install/build, and health commands exactly as documented. Replace any broken command with a verified development command rather than changing product behavior.

- [ ] **Step 5: Commit the public overview**

```bash
git add README.md README.zh-CN.md LICENSE
git diff --cached --check
git commit -m "docs: rewrite public project overview"
```

If `LICENSE` is blocked, omit that path and explain the decision.

### Task 3: Add Security Policy And Threat Model

**Files:**
- Create: `SECURITY.md`
- Create: `docs/THREAT_MODEL.md`
- Create: `docs/PROJECT_STATUS.md`

- [ ] **Step 1: Write the reporting policy**

Document current support status, private reporting through GitHub's available security channel or a clearly marked maintainer contact fallback, non-disclosure expectations, response stages without response-time promises, and project-specific AI/tool risks.

- [ ] **Step 2: Write the threat model**

Separate assets, actors, entry points, trust boundaries, implemented mitigations, known gaps, planned mitigations, and residual risk. Attach each implemented mitigation to a code/test/document path.

- [ ] **Step 3: Write the public status ledger**

Classify capabilities as demonstrated, partial/experimental, or not implemented. Explain internal phase terminology in normal language or omit it.

- [ ] **Step 4: Cross-check security claims**

Search for absolute security language and ensure controls are described as risk reductions rather than guarantees.

- [ ] **Step 5: Commit security and status documentation**

```bash
git add SECURITY.md docs/THREAT_MODEL.md docs/PROJECT_STATUS.md
git diff --cached --check
git commit -m "docs: add security policy and threat model"
```

### Task 4: Add Contributor And GitHub Collaboration Surfaces

**Files:**
- Create: `CONTRIBUTING.md`
- Create: `CODE_OF_CONDUCT.md`
- Create: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Create: `.github/ISSUE_TEMPLATE/feature_request.yml`
- Create: `.github/ISSUE_TEMPLATE/security_concern.yml`
- Create: `.github/ISSUE_TEMPLATE/config.yml`
- Create: `.github/pull_request_template.md`

- [ ] **Step 1: Write contributor guidance**

Document maturity, verified setup, `chore/oss-readiness`-style branch naming examples, Conventional Commit-style scoped messages, tests, docs, security-sensitive reviews, secret prohibition, and honest experimental-status reporting.

- [ ] **Step 2: Add a recognized code of conduct**

Use Contributor Covenant 2.1 and leave a conspicuous project contact placeholder if no public maintainer contact is verified.

- [ ] **Step 3: Add valid issue forms**

Use GitHub issue-form YAML with required reproduction/scope fields. Redirect actual vulnerabilities from the public security form to `SECURITY.md`.

- [ ] **Step 4: Add the pull-request template**

Cover problem/scope, implementation, security, evidence, docs, compatibility, rollback, and no-secrets confirmation.

- [ ] **Step 5: Validate YAML and commit**

Parse each YAML file with an available structured parser, then run:

```bash
git add CONTRIBUTING.md CODE_OF_CONDUCT.md .github
git diff --cached --check
git commit -m "docs: add contribution and GitHub templates"
```

### Task 5: Organize History And Prepare Public Backlog

**Files:**
- Move: `FRONTEND_STRUCTURE_CLOSURE_REPORT.md` to `docs/archive/FRONTEND_STRUCTURE_CLOSURE_REPORT.md`
- Remove: `.__e_repo_write_test__.txt`
- Create: `docs/OPEN_SOURCE_BACKLOG.md`
- Modify only if justified: `.gitignore`

- [ ] **Step 1: Preserve the historical report**

Move the tracked report without rewriting its bytes unless a reversible encoding check proves an exact repair. Record the move in the PR description.

- [ ] **Step 2: Remove the one-off probe**

Delete only `.__e_repo_write_test__.txt`; do not remove other evidence or untracked local files.

- [ ] **Step 3: Write 5-10 contribution-ready backlog items**

For each item include scope, expected result, relevant files, and acceptance criteria. Base tasks on observed gaps such as CI, installation, end-to-end tests, provider docs, threat-model validation, observability, sandbox hardening, and release automation.

- [ ] **Step 4: Commit organization changes**

```bash
git add docs/archive/FRONTEND_STRUCTURE_CLOSURE_REPORT.md docs/OPEN_SOURCE_BACKLOG.md
git rm .__e_repo_write_test__.txt FRONTEND_STRUCTURE_CLOSURE_REPORT.md
git diff --cached --check
git commit -m "chore: organize public repository documentation"
```

Use an equivalent exact-path staging sequence if Git already recognizes the move.

### Task 6: Prepare Changelog And Draft Alpha Release

**Files:**
- Create: `CHANGELOG.md`
- Create: `docs/releases/v0.1.0-alpha.md`

- [ ] **Step 1: Write the changelog**

Use Keep a Changelog structure with an Unreleased section and a clearly dated or unreleased `0.1.0-alpha` preparation entry. Do not imply a GitHub Release exists.

- [ ] **Step 2: Write draft release notes**

Use the title `AI-Dev-Orchestrator v0.1.0-alpha - Maintainer Preview`. Include verified capabilities, controls, setup, limitations, compatibility, maturity, and rollback guidance.

- [ ] **Step 3: Commit release preparation**

```bash
git add CHANGELOG.md docs/releases/v0.1.0-alpha.md
git diff --cached --check
git commit -m "docs: prepare alpha release materials"
```

### Task 7: Validate The Complete Public Surface

**Files:**
- Validate: all files changed from `origin/main`
- Validate: commands referenced by `README.md` and `README.zh-CN.md`

- [ ] **Step 1: Run backend verification**

Run the complete existing backend test suite with the repository's installed environment, then compile the application and scripts. Capture pass/fail counts and warnings.

- [ ] **Step 2: Run frontend verification**

Run `npm ci` and `npm run build` from `apps/web`. Run directly relevant script tests when they have documented invocation paths.

- [ ] **Step 3: Verify README runtime commands**

Start the documented backend command with isolated temporary data, verify `/health`, and stop it cleanly. Run the documented smoke command and record its structured result.

- [ ] **Step 4: Validate Markdown and YAML**

Use a structured script to resolve every relative Markdown link and local anchor target that is practical to validate. Parse every new issue form as YAML.

- [ ] **Step 5: Scan for sensitive data and unsupported claims**

Scan added lines for token/key/password/private URL/internal IP/personal-data patterns. Review all `implemented`, `secure`, `production`, and equivalent claims against the evidence map.

- [ ] **Step 6: Prove no behavior or dependency change**

Run:

```bash
git diff --name-only origin/main...HEAD
git diff --check origin/main...HEAD
git status --short
```

Expected: no application source, dependency manifest, schema, provider integration, or production configuration changed; only the known user-owned untracked paths remain.

### Task 8: Update Metadata, Push, And Open Draft PR

**Files:**
- No repository file changes expected

- [ ] **Step 1: Update repository description and topics**

Use authenticated `gh repo edit` with the exact approved description and ten requested topics. Read the metadata back and compare exact values.

- [ ] **Step 2: Push only the feature branch**

```bash
git push -u origin chore/oss-readiness
```

- [ ] **Step 3: Create the draft pull request**

Create a draft PR targeting `main` titled `chore: improve open-source readiness and security documentation`. Include the complete file list, evidence-backed claims, moves/removals, validation, license decision, metadata result, remaining decisions, and no-runtime-behavior confirmation.

- [ ] **Step 4: Read back and verify delivery state**

Confirm the PR is draft, targets `main`, uses the expected head branch, lists the expected commits, and does not represent a published release or merge.
