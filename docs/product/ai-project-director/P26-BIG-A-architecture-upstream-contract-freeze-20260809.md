# P26-BIG-A1 Architecture, Upstream & Contract Freeze

## 1. Current Repository Baseline

- Recorded after `git fetch origin` on 2026-08-09.
- `origin/main`: `663e10d844dae1893426e10f20858fdee4f2ec89`.
- Local `HEAD`: `663e10d844dae1893426e10f20858fdee4f2ec89`.
- Divergence: `0 0` for `HEAD...origin/main`.
- The pre-existing untracked `.codegraph/` directory is out of scope and remains untouched.
- This supplement is the only P26-BIG-A1 repository change. It does not create `runtime/director-runtime`, import Pi source, change Python or TypeScript production behavior, start a runtime, add a database migration, change the frontend, or start P26-BIG-B.

## 2. P26 Closure Baseline

P26 is `CLOSED / PASS`. Its closure ledger is [P26-multi-turn-discussion-conversation-intelligence-ledger-20260809.md](P26-multi-turn-discussion-conversation-intelligence-ledger-20260809.md).

The new runtime must preserve these P26 facts:

- `DiscussionEvent` and `DiscussionWorkspace` are the persisted discussion history and projection; option identity and supersession are governed by the Python path.
- A `FormalizationProposal` is created only for an explicit formalization request and still requires a user confirmation.
- Confirmation creates only a `pending_confirmation` `PlanVersion`; it does not create a `Task`, `Run`, or `AgentSession`, start a worker/Codex/Claude Code process, or perform a product-runtime Git write.
- P26 source, actor, formalization, confirmation, transaction, idempotency, refresh/resume, and project-isolation semantics remain fail-closed.

P26-BIG is a new runtime program, not a reason to weaken, reclassify, or reimplement those accepted semantics.

## 3. P26-BIG Hard Boundaries

The target composition is:

```text
Pi Agent Harness + AI-Dev-Orchestrator Governance Kernel + P26 semantics
= Governed Project Director Runtime
```

The following are frozen constraints:

1. The Python-owned database remains the single authoritative source of project facts and history.
2. Pi session state, transcript, compaction, and runtime memory are working memory only.
3. The TypeScript runtime never writes `DiscussionEvent`, `DiscussionWorkspace`, `FormalizationProposal`, `PlanVersion`, project state, or any other authoritative state directly.
4. Python validates sources and actors, applies the formalization and permission gates, owns transactions/idempotency/audit, and is the sole committer of P26 state.
5. The Director may not modify code. P26-BIG does not replace Codex or Claude Code as programming executors.
6. A runtime output is a candidate, not a committed fact: `candidate != committed authoritative state`.
7. Draft generation permission and final formal confirmation remain separate.
8. The legacy Provider chain is migration-only. There must not be two long-lived writable Project Director main chains.
9. P27 and P28 remain `Not started`.

## 4. Current Pi Upstream Baseline

The canonical upstream is [earendil-works/pi](https://github.com/earendil-works/pi). `badlogic/pi-mono` is a historical GitHub alias that currently permanently redirects to this canonical repository; it is not a second upstream.

| Item | Frozen observation |
| --- | --- |
| Canonical repository | `https://github.com/earendil-works/pi.git` |
| Historical alias / redirect | `https://github.com/badlogic/pi-mono.git` |
| GitHub repository ID | `1035029907` |
| Default branch | `main` |
| Selected revision | `936aff00918de1187f085f123c2812d8f2d67745` |
| Selected commit date | `2026-08-09T02:11:00+02:00` |
| Selected commit subject | `docs(agent): complete explicit-state harness design` |
| Selection reason | Exact commit observed on canonical `main` at this freeze. It is deliberately pinned for future controlled import and is never described merely as "latest". |
| Latest stable tag observed | `v0.84.1`, commit `53fa77ccd8a279eb87e92294ef3687b03ff80112`, dated `2026-08-07T07:46:28+02:00` |
| License | MIT, `Copyright (c) 2025 Mario Zechner` |
| Package manager | npm workspaces with `package-lock.json`; root scripts use npm. |
| Node requirement | `>=22.19.0` in the root and relevant packages. |
| TypeScript toolchain | Upstream package development dependencies pin TypeScript `5.9.3`; package builds use `tsgo`. |
| Build | `npm install --ignore-scripts`, then `npm run build` or `npm run build:offline`. |
| Check and tests | `npm run check`; `./test.sh` (the upstream test entry, which skips LLM-dependent tests without API keys). |
| Supported upstream surfaces | Node/TypeScript core packages; coding-agent documentation covers Windows, macOS/Unix terminal use, Termux, and standalone release binaries including `linux-x64`. Native TUI extras have Darwin and Windows build paths. |

The source is an npm workspace monorepo. Relevant packages are `packages/agent` (`@earendil-works/pi-agent-core`), `packages/ai` (`@earendil-works/pi-ai`), `packages/protocol`, `packages/client`, `packages/server`, `packages/session-backends/sqlite-node`, `packages/tui`, and `packages/coding-agent`. `packages/agent` exposes a general agent loop, state, harness/compaction/session helpers, skills, and tools. The separate coding-agent package is a terminal coding CLI with its own RPC entry and built-in file/shell tooling; it is not the Director Runtime.

## 5. License & Attribution

Any later internalization must retain the complete MIT text and copyright notice in `runtime/director-runtime/LICENSES/pi-MIT.txt`. `badlogic/pi-mono` is a historical GitHub alias that currently permanently redirects to the canonical `earendil-works/pi` repository. Both identities resolve to the same GitHub repository lineage. `UPSTREAM.md` must record the canonical repository URL, historical alias, repository ID `1035029907`, selected SHA, selected date, imported package paths, source license, and retrieval date.

No source is copied in A1. Consequently, no upstream license file is added in this change.

## 6. Package Inclusion Matrix

The status below classifies **P26-BIG capability ownership and usage policy**. It is not permission to import or execute a package during A1, and it is not a statement that a capability is absent from the physical build dependency closure.

| Upstream capability | Status | P26-BIG decision |
| --- | --- | --- |
| General agent loop and event subscription | INCLUDE | Reuse only behind the Director adapter; the adapter owns request construction and result normalization. |
| Model invocation and provider abstraction | REFERENCE ONLY | Governance ownership remains project-owned for provider credentials, allowlists, model selection, accounting, retries, fallback, and final selection. Pi AI may still be a technical dependency of a selected agent-core surface under the dependency-closure rule below. |
| Streaming primitives | INCLUDE | Permit non-authoritative response and activity streaming only. A stream cannot commit P26 state. |
| In-memory session/runtime primitives | INCLUDE | Use as working memory with explicit rebuild/rehydrate from Python-provided facts; never as a state store. |
| Skills | REFERENCE ONLY | Later mapping must use the project skill registry and governance boundary. A1 does not attach skills. |
| Tool abstraction | INCLUDE | Only as a typed request/activity abstraction after Python authorization. No upstream filesystem, shell, edit, write, or coding tool is inherited. |
| MCP | EXCLUDE | No MCP action or connection is part of A1. Future use requires a separately approved authorization contract. |
| Context and compaction algorithms | INCLUDE | Use only for runtime working context. Summaries are candidates and cannot overwrite authoritative discussion history. |
| Runtime events | INCLUDE | Normalize into runtime metadata/audit observations; do not treat upstream event order as authoritative discussion lifecycle. |
| Abort/cancel primitives | INCLUDE | Bind them to Python-supervised request IDs and explicit terminal states. |
| Error primitives | INCLUDE | Normalize errors to the frozen result contract without exposing credentials or raw provider data. |
| Protocol/client/server packages and process boundary | REFERENCE ONLY | They inform a later transport choice; A1 freezes no Pi wire protocol as the governance protocol. |
| SQLite session backend | EXCLUDE | It would create a competing persistent runtime history. |
| Coding-agent RPC adapter | EXCLUDE | It exposes coding-agent behavior and is not the governed Director Runtime. |
| CLI-only code and TUI/UI | EXCLUDE | No terminal or Pi UI is part of the Project Director control plane. |
| File/bash/edit/write tools and coding-agent-specific behavior | EXCLUDE | They conflict with the Director no-code-modification and executor boundaries. |

### Dependency Closure Rule

At selected revision `936aff00918de1187f085f123c2812d8f2d67745`, `packages/agent` publishes `@earendil-works/pi-agent-core` version `0.84.1`. Its manifest directly depends on `@earendil-works/pi-ai` (`^0.84.1`), `@earendil-works/pi-telemetry` (`^0.84.1`), `diff` (`8.0.4`), `ignore` (`7.0.5`), `typebox` (`1.3.7`), and `yaml` (`2.9.0`). The selected agent-core source also directly imports both `pi-ai` and `pi-telemetry`; therefore `packages/agent` depends on `packages/ai` and `packages/telemetry` at the selected upstream revision.

```text
The controlled Pi snapshot MUST include or explicitly replace
the minimal internal dependency closure required by the selected
agent-core surfaces.

A capability classified as REFERENCE ONLY for governance ownership
is not automatically absent from the technical build dependency closure.

No A2 import may vendor packages/agent alone and assume that its
workspace dependencies disappear.
```

Before copying any files, A2 must determine the minimal source/import closure from this selected immutable SHA. The future import manifest must classify every Pi internal dependency as either `vendored pinned source` or `explicit project replacement`; no implicit workspace dependency is allowed. Third-party npm dependencies must be exactly locked and recorded in the manifest and lockfile. The upstream range `^0.84.1` does not authorize a floating vendor baseline.

`technical dependency != governance authority`. If Pi AI is included only as a technical dependency, the provider credential policy, provider allowlist, model selection authority, accounting policy, and fallback authority remain AI-Dev-Orchestrator governance responsibilities.

## 7. Source Internalization Decision

The future source mechanism is a **controlled upstream directory with a reproducible, narrow vendor snapshot**. It is intentionally not created in A1.

| Mechanism | Decision | Reason |
| --- | --- | --- |
| `git subtree` | Not selected | It makes whole-monorepo history easy to retain, but imports substantially more than the narrow runtime surface and makes selective upgrades harder to audit. |
| Manual vendored source | Not selected by itself | A bare copy loses reproducibility and per-file provenance. |
| Workspace package copy | Not selected | It couples the project build graph to Pi's workspace/package assumptions and broad dependency surface. |
| Package dependency | Not selected | A semver dependency does not freeze source behavior tightly enough for governance, review, and local overlay control. |
| Temporary coding-agent RPC adapter | Not selected | It routes through a CLI whose tool, session, and coding behavior are out of scope. |
| Controlled upstream directory with import manifest | Selected | It permits a reviewed, SHA-pinned, path-limited source snapshot while keeping every project-owned adapter and policy outside the upstream tree. |

The future target layout is:

```text
runtime/
  orchestrator/                         # Python Governance Kernel
  director-runtime/                     # TypeScript runtime, not created in A1
    upstream/pi/                        # Exact selected-source snapshot only
    src/                                # Project-owned adapters, protocol, supervision client
    tests/                              # Contract, lifecycle, and compatibility tests
    UPSTREAM.md                         # SHA, paths, checksums, license, retrieval record
    LOCAL_PATCHES.md                    # Overlay and fork-patch register
    LICENSES/pi-MIT.txt                 # Upstream attribution
```

`upstream/pi/` is read-only by policy after import. Project code may adapt it only from `src/`; it must not make hidden edits inside the upstream tree. The import manifest must list source paths, SHA-256 values, package versions, direct dependencies, dependency-closure classification, and the exact upstream SHA. The first import is a later P26-BIG-A task with its own review, build, license, and compatibility evidence.

The future A2/A3 source retrieval default is `https://github.com/earendil-works/pi.git` pinned to `936aff00918de1187f085f123c2812d8f2d67745`. It must not silently advance because canonical `main` has new commits, and it must not use `main`, `latest`, or `^0.84.1` as authoritative vendor provenance. A new upstream SHA requires a later explicit AI Project Director freeze.

## 8. Python / TypeScript Responsibility Matrix

| Concern | Python Governance Kernel | TypeScript Director Runtime |
| --- | --- | --- |
| Raw user message and authoritative state | Persist, read, transactionally protect, and audit | Receive an immutable request snapshot only |
| P26 discussion | Validate candidate source/actor/semantics; commit `DiscussionEvent` and `DiscussionWorkspace` | Produce a `discussion_delta_candidate` only |
| Formalization and plan version | Apply formalization gate; create proposal and confirmed `PlanVersion` | Produce a proposal candidate/readiness only |
| Permission | Make the final authorization decision and supervise allowed execution | Request a named tool action only after supplied authorization context |
| Models and agent loop | Choose policy/configuration and supervise the runtime process | Invoke the selected model and run the in-memory loop |
| Context and memory | Provide authoritative facts and relevant historical projection | Plan bounded working context, compaction, and ephemeral memory |
| Tools/MCP | Issue or deny authority, enforce idempotency/audit | Execute only an approved capability; report activity/result candidate |
| Failure/recovery | Own request state, retry eligibility, and all authoritative no-commit decisions | Abort, stop, and return structured terminal error metadata |

The non-negotiable boundary is:

```text
TypeScript Runtime MUST NOT directly write authoritative project state.
```

## 9. DirectorRuntimeRequest Contract

The first implementation must use a versioned, JSON-serializable request. Python creates it only after persisting the user message and assembling the P26 context.

```ts
type DirectorRuntimeRequest = {
  schema_version: "p26-big-director-runtime/v1";
  request_id: string;                 // immutable UUID; idempotency and correlation key
  project_id: string;
  session_id: string;
  message_id: string;                 // already-persisted current user message
  current_user_message: {
    content: string;
    occurred_at: string;
    actor_claim: "user";
  };
  authoritative_facts: Record<string, unknown>;
  active_discussion_workspace: Record<string, unknown> | null;
  relevant_discussion_events: Array<Record<string, unknown>>;
  active_formalization: {
    proposal: Record<string, unknown> | null;
    plan_version: Record<string, unknown> | null;
  };
  governance_boundaries: {
    authoritative_write: false;
    director_may_modify_code: false;
    formalization_requires_explicit_request: true;
    confirmation_is_separate: true;
    execution_boundary: "no_task_run_agent_session_before_execution";
  };
  available_skills: Array<{ skill_id: string; version: string; enabled: boolean }>;
  available_tools: Array<{
    tool_id: string;
    allowed: boolean;
    authorization_id: string | null;
    idempotency_key: string | null;
  }>;
  permission_context: Record<string, unknown>;
  runtime_config: {
    model_id: string;
    provider_profile_id: string;
    timeout_ms: number;
    max_tool_rounds: number;
  };
};
```

The request contains no database connection, persistence handle, source of truth, unrestricted credential, or implicit tool permission. `authoritative_facts`, workspace, events, proposal, and PlanVersion are input snapshots, not objects the runtime may mutate and return as committed entities.

## 10. DirectorTurnResult Contract

The runtime returns one fully structured terminal result. Python treats every field other than transport-level metadata as untrusted candidate input and runs its existing or successor governance validation before any state change.

```ts
type DirectorTurnResult = {
  schema_version: "p26-big-director-runtime/v1";
  request_id: string;
  response_text: string;
  turn_semantics: {
    conversation_mode: string;
    formal_action_requested: boolean;
    hypothetical_action: boolean;
    confidence: number | null;
  };
  discussion_lifecycle: {
    observed_status: string | null;
    suggested_next_status: string | null;
  };
  discussion_delta_candidate: Record<string, unknown> | null;
  formalization: {
    proposal_candidate: Record<string, unknown> | null;
    readiness: "not_ready" | "candidate" | "requires_confirmation";
  };
  tool_activity: Array<{
    tool_id: string;
    authorization_id: string | null;
    status: "requested" | "authorized" | "started" | "succeeded" | "failed" | "cancelled";
    idempotency_key: string | null;
    safe_summary: string | null;
  }>;
  source_references: Array<{ message_id: string; kind: string }>;
  runtime_metadata: {
    runtime_state: "ready" | "busy" | "degraded" | "failed";
    model_id: string;
    provider_profile_id: string;
    usage: Record<string, number | null>;
    duration_ms: number;
    attempt: number;
  };
  error: {
    code: string;
    stage: "request" | "model" | "tool" | "result_validation" | "runtime";
    retryable: boolean;
    safe_message: string;
  } | null;
};
```

`response_text` may be presented only under the normal message flow. A non-null delta or proposal candidate does not bypass P26 source validation, actor validation, formalization eligibility, confirmation, transaction, or execution-boundary guards. An absent, malformed, mismatched-request, or schema-invalid result is rejected without applying a partial candidate.

## 11. Runtime Lifecycle

Python supervision owns the authoritative lifecycle record; TypeScript reports its local state and cannot advance a persisted request by itself.

| State | Meaning | Allowed transition |
| --- | --- | --- |
| `starting` | Process/adapter boot and compatibility checks are incomplete. | `ready`, `degraded`, `failed` |
| `ready` | Can accept one supervised request. | `busy`, `stopping`, `degraded`, `failed` |
| `busy` | A specific `request_id` is active. | `ready`, `stopping`, `degraded`, `failed` |
| `stopping` | No new request; abort and bounded cleanup are in progress. | `stopped`, `failed` |
| `stopped` | Process is intentionally unavailable. | `starting` |
| `degraded` | A recoverable dependency or capability is unavailable; Python decides whether requests are admissible. | `ready`, `stopping`, `failed` |
| `failed` | Terminal failed instance; it cannot accept or commit a request. | `starting` through a new supervised instance only |

Only one active runtime attempt may own a given `request_id`. A restart uses a new process instance and an incremented attempt record while retaining the original correlation key. Replay is allowed only when Python can prove that the prior attempt produced no admissible result and that any authorized tool invocation is idempotent or did not start.

## 12. Error / Abort Contract

| Condition | Required behavior |
| --- | --- |
| Request schema/identity failure | Reject before model invocation; persist a safe governance diagnostic only. |
| Request timeout or model timeout | Cancel the runtime signal, mark the attempt terminal, and apply no candidate. |
| Tool timeout, failure, or partial activity | Report only safe tool activity; do not infer success and do not commit a partial `DiscussionDelta`. |
| User abort/cancel | Python issues the cancel by `request_id`; runtime stops work and returns `cancelled` metadata if available. No later output is admissible. |
| Runtime crash/disconnect | Python marks the attempt failed, applies no result, and retains only auditable transport metadata. |
| Result schema validation failure | Discard the entire result candidate; never salvage individual delta operations. |
| Provider failure | Return a sanitized error; Python may select a separately governed fallback path, but only one chain may become the writer for that turn. |
| Restart/recovery | Rehydrate working memory only from a fresh Python request snapshot. Do not restore authoritative state from Pi session files. |

The atomicity rule is absolute:

```text
Runtime failure MUST NOT commit half a DiscussionDelta.
```

## 13. Upstream Patch Governance

Every future upstream touch is classified before implementation:

| Class | Meaning | Allowed location |
| --- | --- | --- |
| `overlay` | Project adapter/configuration with no upstream source change | `runtime/director-runtime/src/` |
| `hook` | Supported upstream extension point | Project-owned hook registration and `UPSTREAM.md` |
| `fork-patch` | Necessary modification to imported upstream source | `upstream/pi/` plus a mandatory `LOCAL_PATCHES.md` record |
| `replacement` | Project-owned implementation substituted for an upstream component | `src/`, with the replaced upstream surface marked excluded |
| `disabled` | Imported upstream capability deliberately unavailable | `UPSTREAM.md` and runtime policy |

`UPSTREAM.md` must list the canonical repository URL, historical alias, repository ID, baseline SHA, retrieval command/date, imported paths and hashes, license location, package versions, dependency closure, and upgrade procedure. `LOCAL_PATCHES.md` must list every overlay/hook/fork-patch/replacement/disabled decision. Each `fork-patch` entry must include its reason, project requirement, upstream baseline, affected files, upgrade-conflict risk, and compatibility test. No unrecorded local edit inside `upstream/pi/` is acceptable.

## 14. Legacy Provider Migration Strategy

The migration preserves a single authoritative writer per message turn.

| Step | Runtime posture | Authoritative-write rule |
| --- | --- | --- |
| 1. Shadow | Legacy remains the serving chain; Director Runtime observes an equivalent immutable request and emits diagnostics only. | Legacy alone may commit. |
| 2. Compare | Python normalizes and compares semantics, candidates, latency, usage, and errors. | Legacy alone may commit; comparison output is audit evidence only. |
| 3. Opt-in | Explicitly selected project/session uses the Director Runtime. | Exactly the selected chain may commit. The non-selected chain is not invoked as a writer. |
| 4. Default-on | New eligible traffic uses Director Runtime while a narrowly governed fallback remains available. | Runtime validation must finish before it becomes writer. A fallback starts a fresh, single-writer path; it never merges a partial runtime result. |
| 5. Burn-in | Monitor validated compatibility, error, timeout, cancellation, and no-double-write indicators. | Director Runtime is the writer for eligible traffic; Legacy does not co-commit. |
| 6. Retire | Stop new Legacy serving traffic after review evidence. | Legacy is no longer a writable main chain. |
| 7. Archive | Retain code, migration records, and read-only historical support under a stated retention policy. | No archived path can silently resume authoritative writing. |

During Shadow and Compare, neither chain may simultaneously commit authoritative state for the same turn. Permanent dual-write or permanent two-main-chain operation is prohibited.

## 15. Risks

1. **High - Pi's agent package exports harness tools and coding-oriented helpers beside general loop primitives.** Importing the package without path-level selection could bypass the Director/executor boundary. Mitigation: controlled narrow snapshot, explicit exclusion matrix, and no tool adapter without Python authorization.
2. **High - Runtime working memory can diverge from P26 history after compaction, timeout, or restart.** Mitigation: Python assembles every request from authoritative facts; rehydrate never treats Pi session data as a source of truth; full candidate validation remains mandatory.
3. **High - Migration can create duplicate or partial state when Legacy and Director both observe a turn.** Mitigation: per-turn writer ownership, request IDs, idempotency evidence, and a hard no-half-delta rule.

## 16. Deferred Items

The following are explicitly deferred:

- Creating `runtime/director-runtime` or importing any Pi source.
- Protocol implementation, process transport, initial build baseline, and runtime tests.
- Attaching real chat traffic, real MCP action, skills, tools, or a provider runtime.
- Deleting or changing the Legacy Provider chain.
- Any P26 production behavior, frontend, database migration, P26-BIG-B, P27, or P28 work.

## 17. P26-BIG-A Remaining Work

P26-BIG-A remains `Partial`. The next implementation sequence is:

1. Create the controlled `runtime/director-runtime` scaffold with attribution files and a manifest-driven, path-limited upstream import from canonical `https://github.com/earendil-works/pi.git` at `936aff00918de1187f085f123c2812d8f2d67745`; verify license, hashes, build requirements, and the minimal dependency closure.
2. Implement the versioned request/result protocol and Python supervisor/adapter without changing P26 commit semantics; add contract and failure-atomicity coverage.
3. Establish the initial runtime build baseline and a non-writing Shadow comparison before any Opt-in route.

The implementation owner for the runtime/backend work is `write-v5-runtime-backend`. If the implementation becomes a combined runtime, API, web, and verification package, route it to `drive-v5-orchestrator-delivery`; runtime evidence belongs to `verify-v5-runtime-and-regression` before any later gate decision.

## 18. Gate

```text
P26-BIG-A1 Architecture / Upstream / Contract Freeze = Awaiting Director Review

P26 = CLOSED / PASS
P26-BIG-A = Partial
P26-BIG-B = Not started
P27 = Not started
P28 = Not started
AI Project Director total loop = Partial
```

This document is a frozen architecture and execution-boundary supplement. It is not a runtime implementation, build proof, integration result, or P26-BIG-A Pass declaration.
