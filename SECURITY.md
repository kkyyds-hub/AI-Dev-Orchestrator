# Security Policy

## Support Status

AI-Dev-Orchestrator is an early-stage maintainer preview. There are no supported
release branches, long-term-support versions, or production security guarantees.
Security fixes are currently expected to target the latest `main` branch. Draft
release material for `v0.1.0-alpha` does not represent a published or supported
release.

The repository includes application-level safety controls, but it has not been
formally verified, independently audited, or hardened for hostile multi-tenant
deployment.

## Reporting A Vulnerability

Do not disclose an actionable vulnerability in a public Issue, Discussion, pull
request, commit message, or log attachment.

This repository does not currently have GitHub private vulnerability reporting
enabled, and no public maintainer security email has been verified. Until the
maintainer enables a private channel:

1. Do not publish exploit details or sensitive evidence.
2. Use the public `Security concern` issue form only to request a private contact
   channel. Include no reproduction steps, secrets, affected paths, payloads, or
   indicators that would enable exploitation.
3. Wait for the maintainer to establish a private channel before sharing the
   technical report.

Maintainer action required before broader adoption: enable **Settings > Security
> Private vulnerability reporting** in GitHub and update this file with the
verified channel.

Once a private report is received, the expected process is:

1. acknowledge receipt and establish a private discussion;
2. validate scope and affected revisions without exposing reporter data;
3. assess exploitability, impact, and whether credentials may be involved;
4. prepare and privately validate a minimal remediation;
5. coordinate disclosure and credit with the reporter;
6. publish an advisory or release only after the maintainer approves it.

No fixed response or remediation time is promised at this maturity level.

## What To Include Privately

- affected commit, branch, route, service, or executor;
- preconditions and the smallest safe reproduction;
- observed impact and expected security boundary;
- whether secrets, personal data, or third-party systems may be involved;
- relevant logs with credentials and personal data removed;
- suggested mitigations, if known.

Do not send live credentials, private repository contents, customer data,
malware, or destructive proof-of-concept payloads unless a maintainer explicitly
coordinates a safe method.

## Project-Specific Security Concerns

### Repository-content prompt injection

Source files, READMEs, Issues, generated logs, diffs, and test fixtures can
contain instructions intended to manipulate an AI agent. Treat repository text
as untrusted data, not as authorization. Agent-visible instructions must not
override the operator's explicit scope, approval requirements, or tool policy.

### Untrusted instructions in collaboration content

Issue bodies, pull-request comments, commit messages, and copied terminal output
may request secret disclosure or unsafe commands. Verify requests against the
maintainer's stated goal and repository policy before acting.

### Shell-command and filesystem risk

The backend contains local-command and native-executor paths. A process launched
as the current user can inherit meaningful filesystem and network access.
Application path checks are not a substitute for an operating-system sandbox,
container, disposable VM, or least-privilege account.

Use simulated or dry-run modes first. Inspect commands, working directories,
environment variables, timeouts, and candidate paths before enabling native
execution. Do not run the orchestrator against sensitive repositories on an
untrusted host.

### Secrets and credentials

Never commit API keys, access tokens, SSH keys, cookies, `.env` files, private
URLs, or copied provider responses containing credentials. `OPENAI_API_KEY` can
be supplied through the environment. Provider configuration can also be saved
under the runtime data directory and may contain a raw API key; protect or avoid
that persistence path and use short-lived, least-privilege credentials.

Logs, evidence packs, prompts, diffs, and reviewer output can also leak secrets.
Redact before attaching them to an Issue or pull request.

### Dependencies

Python and npm dependencies execute in the developer environment. A malicious or
compromised package, install script, or transitive dependency can bypass
application-level controls. Review lockfile changes, use trusted registries,
minimize install privileges, and investigate unexpected dependency behavior.
The repository does not currently provide committed CI dependency scanning or a
software bill of materials.

### Providers and external executors

Prompts, repository excerpts, diffs, and metadata sent to an external provider
leave the local trust boundary. Provider compatibility, retention, regional
processing, model behavior, and account policy are external concerns. Native
executors such as Codex or Claude Code also have their own configuration and tool
permissions. Review those systems independently and do not assume this project
constrains every downstream action.

### Sandbox escape and boundary violations

The Project Director flow includes backend-owned workspace roots, normalized
workspace names, path-containment checks, manifests, and candidate-file stages.
These are application controls. Report any way to escape an intended root,
traverse symlinks unexpectedly, write the main worktree, bypass a manifest, or
obtain broader process privileges.

### Unsafe AI-generated patches

Generated code can be incorrect, insecure, destructive, or outside scope even
when verification passes. Inspect the complete diff, run project-specific tests,
review dependency and configuration changes, and require human approval before
merging security-sensitive changes.

### Review bypass, stale decisions, and replay

Selected review flows bind source diffs, prompts, scopes, schema versions, and
review fingerprints. Freshness and consumption gates are designed to reject
mismatches, stale evidence, and duplicate consumption. Report any route that can
reuse a decision for a different diff, skip required review, change scope after
review, or consume the same authorization more than once.

These protections apply to selected Project Director chains, not automatically
to every task or Git operation.

### Audit evidence integrity

SQLite rows, JSONL logs, files under the runtime data directory, and append-only
application messages are locally writable by the same operating-system account.
They support investigation but are not cryptographically signed, remotely
attested, or protected against a fully compromised host. Report evidence
substitution, truncation, cross-session binding, or ordering problems.

## Public Disclosure Boundaries

Do not place the following in a public Issue:

- exploit steps for an unpatched vulnerability;
- credentials, tokens, session cookies, or private keys;
- private repository content or personal data;
- internal or private network addresses;
- unredacted prompts, logs, diffs, database files, or provider responses;
- details that enable sandbox escape, review bypass, evidence replay, or command
  injection before a mitigation is available.

For non-sensitive security hardening ideas that do not reveal a vulnerability,
use the `Security concern` issue form and state clearly that the report contains
no confidential details.

## Security References

- [Threat Model](docs/THREAT_MODEL.md)
- [Project Status](docs/PROJECT_STATUS.md)
- [Contributing](CONTRIBUTING.md)
