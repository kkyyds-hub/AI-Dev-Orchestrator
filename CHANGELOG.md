# Changelog

All notable public changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project intends to use [Semantic Versioning](https://semver.org/) when
it begins publishing releases.

## [Unreleased]

### Added

- English and Simplified Chinese public project overviews.
- Apache License 2.0 text for repository code.
- Project-specific security policy and practical threat model.
- Public project-status ledger and contribution-ready open-source backlog.
- Contribution guide, Contributor Covenant, issue forms, and pull-request
  template.
- Draft `v0.1.0-alpha` maintainer-preview release notes.

### Changed

- Moved a historical frontend structure closure report from the repository root
  to `docs/archive/` without rewriting its contents.
- Reconciled stale provider smoke, executor-boundary, and Project Director worker
  evidence tests with the current guarded runtime contracts; production behavior
  is unchanged.

### Removed

- Removed a one-off repository write-test artifact from the root.

## [0.1.0-alpha] - Unreleased Draft

This entry describes a proposed first alpha release. No Git tag or GitHub Release
is created by this changelog.

### Included In The Draft

- Local FastAPI and React/Vite orchestration control surfaces.
- SQLite-backed task, run, approval, evidence, and audit-oriented records.
- Simulated/local task execution, verification, routing, budgets, and retry
  controls.
- Experimental bounded external-executor, sandbox-oriented workspace, read-only
  reviewer, and evidence-freshness contracts.

### Known Limitations

- The complete backend suite passes the readiness run but emits substantial
  deprecation warnings.
- Native executors, reviewer transports, provider calls, and product-runtime Git
  operations remain partial, environment-dependent, or guarded.
- No production support, CI release automation, authentication, OS-level sandbox
  guarantee, or formal security assurance is provided.

[Unreleased]: docs/releases/v0.1.0-alpha.md
[0.1.0-alpha]: docs/releases/v0.1.0-alpha.md
