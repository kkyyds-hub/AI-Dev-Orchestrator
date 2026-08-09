# P26 Multi-turn Discussion & Conversation Intelligence Ledger - 2026-08-09

## Final Gate

- P26-H3 Provider Contract Gate: Pass
- P26-H4 Production Defect R1: Pass
- P26-H4 Final Multi-turn UAT: Pass
- P26-H5 Verification Evidence Integration: Pass
- P26-H: Pass

- P26-I: Closure candidate
- P27: Not started
- P28: Not started

## Summary

P26 gives the AI Project Director a persistent multi-turn discussion path. It records and rebuilds `DiscussionEvent` and `DiscussionWorkspace` state for topics, options, constraints, corrections, preferences, and rejections; preserves historical supersession; and reselects a rejected option with its original identity. Explicit formalization requests create a reviewable `FormalizationProposal`; only confirmation creates a `pending_confirmation` PlanVersion. Before the execution boundary, formalization does not create Tasks, Runs, or AgentSessions. Refresh/resume restores the discussion state, and project state remains isolated.

## Implemented Surface

- Turn interpretation: `runtime/orchestrator/app/services/project_director_turn_interpreter_service.py`
- Response generation and envelope validation: `runtime/orchestrator/app/services/project_director_response_engine_service.py`
- Discussion Delta Gate: `runtime/orchestrator/app/services/project_director_discussion_delta_gate_service.py`
- Workspace reduction and persistence: `runtime/orchestrator/app/services/project_director_discussion_workspace_reducer_service.py`, `runtime/orchestrator/app/services/project_director_discussion_turn_persistence_service.py`, `runtime/orchestrator/app/repositories/project_director_discussion_event_repository.py`, and `runtime/orchestrator/app/repositories/project_director_discussion_workspace_repository.py`
- Message Service integration: `runtime/orchestrator/app/services/project_director_message_service.py`
- Formalization proposal and confirmation: `runtime/orchestrator/app/domain/project_director_formalization_proposal.py`, `runtime/orchestrator/app/repositories/project_director_formalization_proposal_repository.py`, and `runtime/orchestrator/app/services/project_director_discussion_formalization_service.py`
- Workbench readback and frontend integration: `runtime/orchestrator/app/api/schemas/project_director_workbench.py` and `apps/web/src/features/workbench/ProjectDirectorWorkbenchSurface.tsx`

## Key Contract Changes

### Discussion Identity

Options use stable UUIDs. A rejected option is not recreated through `ADD_OPTION`: reselection uses the original UUID with `PREFER_OPTION` and supersedes the original rejection event.

### Actor and Provenance

An explicit user preference or reselection requires `actor_claim=user_explicit`; `source_message_ids` points to the current persisted user message.

### Formalization Boundary

Ambiguous approval is not formalization, and hypothetical discussion is not a formal action. Only an explicit formalization request can create a `FormalizationProposal`; that proposal still requires user confirmation. Confirmation creates only a `pending_confirmation` PlanVersion.

### Execution Boundary

At formalization and confirmation, the verified boundary is:

```text
Task = 0
Run = 0
AgentSession = 0
Worker start = 0
Codex start = 0
Claude Code start = 0
product runtime Git write = 0
```

### Frontend Boundary

`canOfferDiscussionFormalization` in `apps/web/src/features/workbench/ProjectDirectorWorkbenchSurface.tsx` permits the formalization confirmation path only when `workspace.discussion_status === "ready_to_formalize"`.

## Verified Commits

- `0a39594eb48d7440000eba5517a6dfacf8724d7c` — `test: cover p26 option alias reselection`; covers the P26 option-alias reselection contract across seven P26 backend test files.
- `53a5954d7d669ddb2d16850448419ff494049aaa` — `fix: gate p26 formalization by discussion status`; adds the three-line `ready_to_formalize` guard in `ProjectDirectorWorkbenchSurface.tsx`.

`53a5954d` was fast-forwarded to `main`; `main == verify/p26` at evidence integration.

## Test Evidence

### P26 Targeted/Stable Backend Regression

```text
1217 passed
0 failed
0 skipped
7.24s
5 existing warnings
```

This is P26 targeted/stable backend regression evidence, not a claim of a full repository regression.

### Frontend

```text
projectDirectorWorkbenchInteraction.test.mjs: 19 passed / 0 failed
projectDirectorDiscussionWorkbench.test.mjs: Pass
projectDirectorFormalizationProposal.test.mjs: Pass
npm run build: Pass
```

## Real Provider Evidence

```text
provider type: openai_compatible
model: mimo-v2.5
host: api.xiaomimimo.com
timeout: 120s
```

- Turn Interpreter: 73.657s, `source=provider`, `fallback=false`, `preference_update`, and resolved the original rejected A UUID.
- Response Engine: 46.698s, `source=provider`, `repair=false`, and produced a legal `PREFER_OPTION(A)` with the correct target, supersedes relation, `actor_claim=user_explicit`, and current-user source message.

Provider Compliance = Pass. System Safety = Pass. Production Defect = none. No Provider call is made by this ledger task.

## 20-turn UAT Evidence

```text
Project A user turns = 20
A UUID = 11111111-1111-1111-1111-111111111111
B UUID = 22222222-2222-2222-2222-222222222222
```

- Rejected A was reselected with its original UUID; `OPTION_ADDED(A)` total was 1; `PREFER_OPTION(A)` superseded the original rejection.
- All four constraints were retained: 4 / 4, 100%.
- The latest correction was effective, persisted, and restored after refresh.
- Hypothetical discussion had no formal side effects.
- Comparison did not mutate preference; a non-formal `temporary_conclusion` was allowed.
- Ambiguous approval created `FormalizationProposal +0` and `PlanVersion +0`.
- Explicit formalization created a lineage-valid `FormalizationProposal` with `requires_confirmation=true`.
- Proposal confirmation returned HTTP 201 and created one `pending_confirmation` PlanVersion.
- Refresh passed with fresh SQLAlchemy and service instances. Project B contamination was 0.

Final deterministic-UAT counts:

```text
Messages = 46
DiscussionEvents = 20
Workspaces = 2
Project A FormalizationProposals = 1
Project A PlanVersions = 1
Tasks = 0
Runs = 0
AgentSessions = 0
real Provider calls = 0
Fake Provider calls = 46
```

## Known Risks

Real Provider latency remains relatively high in the bounded contract gate: Turn Interpreter was approximately 73.657s and Response Engine approximately 46.698s. Contract correctness passed, but this remains an operational and UX risk rather than a P26 correctness blocker.

## Deferred / Out of Scope

P27 = Not started. P28 = Not started. They are later independent stages, not P26 Closure gaps. No known P26 correctness blocker remains.

## Stage Closure

- [Pass] Data/persistence path
- [Pass] Service/API/UI main flow
- [Pass] Multi-turn semantic discussion
- [Pass] Preference/rejection/correction history
- [Pass] Stable option identity / reselection
- [Pass] Explicit-only formalization
- [Pass] No Task/Run/AgentSession before execution boundary
- [Pass] Refresh/resume
- [Pass] Project isolation
- [Pass] Backend regression
- [Pass] Frontend regression/build
- [Pass] Real Provider contract
- [Pass] 20-turn UAT
- [Pass] Evidence integrated into main

P26 Closure Candidate = Pass.

## Next Phase

Next eligible stage after Director closure: P27.

P27 = Not started. P28 = Not started.
