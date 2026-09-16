# P26-BIG-D2 Working Memory, Compaction and Rehydration Contract Freeze

## 1. Scope, baseline, and status

This document freezes the D2-A architecture and contract only. It does not add Working Memory production code, change Python or TypeScript runtime behavior, alter transport lifecycle, add a Pi session backend, change the protocol, add a database/migration, or modify upstream Pi.

Baseline recorded after `git fetch origin` on 2026-09-16:

- `origin/main` and local `HEAD`: `ae8789efe08c6742ab46ebba76f9627d5fb3792e`.
- Parent: `77822b16d295f472250b16bdb3b45bbd80d4e087`.
- Subject: `feat: ground director runtime repository state`.
- Divergence: `0 0` for `HEAD...origin/main`.

Formal status entering D2 is `P26-BIG-D1 = PASS`; D1's bounded request and Context Planner are the authoritative grounding boundary. `P26-BIG-D = Partial`. D2 addresses Working Memory, compaction, runtime restart reconstruction, and long-conversation provenance. It does not begin E/F/G/H, P27, or P28.

## 2. Observed current lifecycle

The following are code observations, not design assumptions.

1. `StdioJsonlDirectorRuntimeTransport.invoke()` calls `asyncio.create_subprocess_exec`, writes exactly one JSON request line through `process.communicate`, awaits process termination, accepts exactly one JSON result line, and reaps/removes the child handle. One Python invoke therefore creates one Node subprocess.
2. `director-runtime.ts` reads all stdin, rejects anything other than exactly one non-empty request line, validates that request, executes it once, prints one result, and exits. One Node process therefore reads one request.
3. `executeDirectorRuntimeRequest()` calls `createDirectorModelContext(request)` and constructs `new Agent({ initialState: { model, systemPrompt, tools: [] } })` for that execution. The Agent is a fresh in-process object per execution.
4. No Director runtime path constructs, opens, or binds a Pi `SessionRepo`. There is no `InMemorySessionRepo`, `JsonlSessionRepo`, or SQLite Session backend in the Director invocation path.
5. The Python assembler reconstructs bounded context from the database on every request: current user message, recent raw messages, governed discussion projection/events, formalization state, authoritative facts, governance boundaries, and other validated request fields. The TypeScript Context Planner then renders that supplied request only.

The current one-process-per-request design is not a D2 defect. It proves that the Runtime cannot silently use a surviving process, Agent object, or transcript as cross-turn authoritative memory. D2-A deliberately uses this property to freeze a rebuild-first contract before any optional long-lived cache is considered.

## 3. Authority boundary: four memory layers

The Python database and Python Governance Kernel are the sole authoritative memory. Pi Runtime Working Memory is non-authoritative, disposable, rebuildable, and session-scoped.

| Layer | Examples | Authority and mutation rule |
| --- | --- | --- |
| A. Raw Evidence | persisted user/assistant raw messages, tool raw results, source IDs and timestamps | Evidence is database-owned. D may summarize a projection but cannot replace, delete, or reclassify A. |
| B. Authoritative Project Facts | Project, Task, confirmed session facts, PlanVersion, permissions, formal state | Python supplies fresh facts. D cannot write or override B. |
| C. Governed Discussion Memory | DiscussionEvent, DiscussionWorkspace, preferred/rejected/superseded decisions, open questions, active proposal | Python governance owns validation and persistence. Runtime output is only a candidate and never direct state mutation. |
| D. Runtime Working Memory | model working context, temporary summary, tool intermediate state, compaction output, ephemeral Agent state | Non-authoritative, request/session-scoped, disposable, and rebuildable from a new request. |

Layers A, B, and C always win over D. No Pi transcript, summary, retained tail, local JSONL, Pi SQLite file, in-memory Agent state, or second Runtime database is a source of formal project truth.

## 4. D2-v1 decision: rehydrate first

D2-v1 is **REHYDRATE-FIRST**. Every Runtime request must be able to rebuild sufficient working context from only a Python-produced, validated `DirectorRuntimeRequest`. It must not require a previous Node process, Agent object, Pi session file, JSONL transcript, Pi SQLite session database, or any other product-owned Runtime memory store.

The frozen rebuild pipeline is:

```text
Python authoritative DB
  -> DirectorRuntimeRequest
  -> validateDirectorRuntimeRequest
  -> Context Planner
  -> rebuild ephemeral Runtime Working Memory
  -> model / Agent loop
```

The same pipeline is used after a Runtime restart. A restart never restores formal facts from Pi session storage.

### Rebuild flows

| Situation | Required sequence | Forbidden dependency |
| --- | --- | --- |
| Cold start | Python reads current DB state, persists/identifies the current user turn, builds and validates a request, then creates fresh Runtime working context and Agent. | Prior process, Agent, or transcript. |
| Normal next turn | Python persists the new user input and rebuilds the next bounded request from current A/B/C state; Runtime creates fresh working context. | Assuming the prior in-memory summary is formal history. |
| Runtime crash | Python treats no unadmitted runtime candidate as committed; the retry/new attempt creates a fresh request from current DB state. | Reusing a partially mutated Agent or uncommitted summary. |
| Runtime restart | Process B follows the same DB-to-request pipeline as process A, keyed to the requested project/session. | Pi JSONL/SQLite recovery of project facts. |
| Model switch | Python supplies current DB context and selected runtime configuration; a fresh Agent uses the new model while B/C remain unchanged. | Model-specific persistent memory as project truth. |

## 5. Pinned and compactable context

The following are pinned fresh request context. Compaction must not replace them with a Runtime summary:

1. `governance_boundaries`.
2. `authoritative_facts`.
3. `current_user_message`.
4. `active_discussion_workspace`.
5. `active_formalization` state (proposal and PlanVersion).

The model's formal basis on every turn is the latest validated request, even if a Working Memory summary exists. D2-v1 may compact only non-authoritative working projections:

- older conversational working context;
- redundant historical raw-message projection;
- redundant historical discussion-event projection; and
- future tool traces or intermediate Runtime observations.

It must not compact into an authoritative replacement for Project, Task, formal confirmation, Workspace, Proposal/PlanVersion, or permission state.

## 6. Frozen `DirectorWorkingMemorySummary` concept

D2-B/C must implement a project-owned concept with at least the following semantics. Field spellings may change only if all meanings remain present.

```text
DirectorWorkingMemorySummary
  non_authoritative: true
  rebuildable: true
  project_id
  session_id
  source_request_id
  source_turn_identity
  summary_text
  source_message_ids[]
  source_discussion_event_ids[]
  source_section_names[]
  compaction_applied
  original_size
  compacted_size
  truncated_or_incomplete
```

The object is a runtime candidate/observation, never `user_explicit`, a formal fact, or a confirmed decision. Source references are mandatory: a summary must be able to answer which message IDs, DiscussionEvent IDs, and request sections contributed to it. If a source is outside the bounded request, the summary may not invent it.

## 7. Conflict, reversal, and old-evidence rules

### Conflict rule

When a Working Memory summary conflicts with fresh `authoritative_facts`, `DiscussionWorkspace`, or formalization state, fresh authoritative/governed database state wins without a compromise merge. The older summary is a stale candidate and must be discarded or rebuilt.

### User reversal rule

If an earlier turn favored option A and a later governed turn rejects A in favor of B, Working Memory must not present A as active. A may remain historical or superseded only with the reason and source reference. Active preference comes from the current governed state, not the summary wording.

### Old rejection recovery rule

If an older rejection reason lies outside the current bounded raw-message window, Runtime must obtain it through current `DiscussionWorkspace` or an explicitly governed historical-event retrieval path. Otherwise it must state `evidence gap`/`unknown`. It must not infer the reason from an old Pi transcript.

## 8. Compaction failure rule

Compaction failure must not write the database, write `DiscussionEvent`, modify `DiscussionWorkspace` or `PlanVersion`, discard the current request, or claim success.

If the already supplied bounded DB-backed request can safely run without compaction, Runtime falls back to that bounded context and records no authoritative mutation. If that fallback cannot safely satisfy the runtime context contract, the turn fails closed with a structured runtime failure. D2-v1 has no summary-persistence-on-failure escape hatch.

## 9. Restart acceptance and isolation contract

Future D2-D acceptance must prove that identical authoritative database state produces, before and after a full Runtime process restart:

- the same active constraints;
- the same active preference;
- the same rejected/superseded semantics;
- the same proposal identity; and
- the same project correlation.

Natural-language response phrasing may vary. Formal facts, active decisions, and project correlation may not. Working Memory keys and any future cache must bind at least `project_id` and `session_id`; Project A working state must never be reused for Project B. This remains mandatory if a later runtime becomes long-lived.

## 10. Pi session position

Pi `InMemorySessionRepo` is only a possible future ephemeral Runtime cache. Its process-memory loss must never lose project facts or governed decisions.

Pi `JsonlSessionRepo` persists session headers, entries, and records through filesystem-backed JSONL storage. It is prohibited as D2-v1 cross-turn product memory. The Pi SQLite session backend is likewise prohibited. Neither may be treated as an authoritative transcript, an official recovery source, or a second database of record. Any later consideration requires a separate contract after the rebuild acceptance contract passes.

## 11. Pi compaction findings and adapter boundary

The pinned upstream exposes `prepareCompaction(pathEntries, settings)` and `compact(preparation, models, model, ...)`.

- Preparation derives messages to summarize, optional split-turn prefix, retained recent tail, estimated tokens, prior summary, file-operation details, and settings from Pi session entries.
- `compact()` performs one or two summary model calls, returns a summary, usage, `tokensBefore`, retained tail, and file-operation details. Summary calls use a new ephemeral provider session ID and retries/provider configuration may apply.
- Pi compaction therefore presumes Agent/session entry state and can produce summary plus retained tail appropriate for a local agent harness.
- Its current result does not provide the required D2 project/session/request identity, message/event/request-section provenance, authoritative/non-authoritative classification, stale conflict rule, or governed reversal semantics.

Pi's algorithms can be evaluated as an implementation aid only behind a project-owned D2 adapter. The adapter must build inputs from the validated request, emit `DirectorWorkingMemorySummary` semantics, preserve provenance, keep pinned context fresh, and never write authoritative state. D2-A makes no upstream change and does not call this API.

## 12. Legacy `MemoryCompactionService` conclusion

`runtime/orchestrator/app/services/memory_compaction_service.py` is an existing task/context-governance mechanism. It deterministically merges a task context summary and optional project-memory hint, then applies headline-and-trim compaction based on a context budget. It is currently consumed by `ContextBuilderService`, task-worker wiring, and project API construction.

It is not directly reusable as Director Working Memory: it has no Director project/session/request identity, no message/event/section provenance, no retained-tail semantics, no conflict/reversal handling, no restart contract, and no authoritative-vs-runtime boundary. Its deterministic size-accounting and fail-safe no-write character are potentially reusable implementation mechanics only; its input/output semantics must not be repurposed without a project-owned D2 adapter and separate implementation task.

## 13. Explicit non-goals and prohibited designs

D2-A does not select or implement Pi `JsonlSessionRepo`, Pi SQLite sessions, a second Runtime memory database, persistent Pi transcript authority, Runtime-direct DiscussionEvent/Workspace writes, summary replacement of raw messages or authoritative facts, long-lived Node processes, or a Python transport redesign.

Runtime candidates remain subject to existing Python admission, governance, and persistence paths. No Runtime summary may directly commit formal state.

## 14. Follow-on construction sequence

1. **D2-B — Rehydratable Working Memory Planner:** define project-owned runtime-only data types and rebuild request projections; preserve all pinned context and project/session isolation. No persistent Pi session.
2. **D2-C — Compaction and Provenance:** add the project-owned adapter, source-reference preservation, stale/conflict/reversal behavior, compaction failure handling, and bounded rendering. Evaluate Pi compaction only behind that boundary.
3. **D2-D — Runtime Restart/Rehydration Verification:** independently prove cold start, normal turn, crash/restart, model switch, isolation, provenance, stale-summary rejection, and no-authoritative-write behavior across separate runtime processes.

Persistent Pi session storage is explicitly sequenced after, not before, a passing rebuild-first contract and would require a new approved task.

## 15. D2-A completion boundary

This document is the sole D2-A repository change. It is a contract freeze, not a production completion claim. D2-B, Working Memory production implementation, Pi Session persistence, and compaction implementation remain not started.
