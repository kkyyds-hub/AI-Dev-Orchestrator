# P23-A: Protected Transition Dispatch Contract Design

## 1. Background and Problem

P22 produces `ready_for_future_transition` or `waiting_for_human` summaries. These summaries bind exact evidence chains (D-B → C1 → C2 → C3 → E, or D-B → D1) and certify freshness. But P22 does not define how to convert a freshness-certified summary into a safe, auditable, replay-protected dispatch intent that the task system can consume.

Current gap: No contract exists for:

```text
trusted P22 summary
→ protected transition dispatch intent
→ future atomic consumption
→ future controlled task-system interaction
```

P23-A designs this contract without implementing it.

## 2. Current P22 Fact Baseline

### P22 automatic path result

```text
orchestration_status = ready_for_future_transition
route ∈ {automatic_continuation, bounded_automatic_rework}
disposition_type ∈ {AUTO_CONTINUE, AUTO_REWORK}
evidence_fresh = true
gate_allows_protected_transition_guardrail = true
gate_allows_write = false
blocked_reasons = []
```

### P22 human path result

```text
orchestration_status = waiting_for_human
route = human_escalation
disposition_type = ESCALATE_TO_HUMAN
waiting_for_human = true
```

### P22 permanent boundary

```text
continuation_started = false
rework_started = false
task_created = false
run_created = false
worker_started = false
worktree_created = false
patch_applied = false
git_write_performed = false
gate_allows_write = false
product_runtime_git_write_allowed = false
ai_project_director_total_loop = Partial
```

### Existing task system services

| Service | Role |
|---------|------|
| `TaskReadinessService` | Evaluates whether an existing task is eligible for execution |
| `TaskRouterService` | Selects next candidate task from pending queue |
| `TaskStateMachineService` | Manages task status transitions |
| `TaskWorker` | Claims task, creates Run, starts runtime |

P22 does not call any of these services.

## 3. P23-A Goals

1. Define `ProjectDirectorProtectedTransitionDispatchIntent` DomainModel.
2. Define trusted P22 summary input validation contract.
3. Define intent preparation service contract.
4. Define intent consumption preflight contract.
5. Define task-system integration boundary.
6. Define replay, concurrency, and atomicity contracts.
7. Define blocked reasons.
8. Define failure recovery taxonomy.
9. Define P23 stage split.
10. Preserve all permanent safety boundaries.

## 4. Non-Goals

- No new API endpoint.
- No production code modification.
- No test creation.
- No Worker modification.
- No Task/Run/Worker creation.
- No real AUTO_CONTINUE execution.
- No real AUTO_REWORK execution.
- No human decision recording.
- No frontend changes.
- No DB schema changes.
- No database migration.

## 5. Core Semantic: AUTO_CONTINUE

### Decision: Continue the source task's existing state machine

AUTO_CONTINUE means: the source task that produced the review is eligible to proceed to its next state-machine step. It does NOT mean: create a new task, select a different pending task, or modify the project plan.

### Rationale

The strongest evidence binding is to the source task itself. The P22 summary already binds `source_task_id`. The review was performed on this task's candidate diff. The freshness gate validated this task's workspace and diff. Routing to a different task would break this binding.

### What "continue" means

```text
source task is in a state where its next step can proceed
→ mark source task as ready for its next step
→ allow TaskWorker to claim it in its normal loop
```

### Source task current state

At P22 completion, the source task is typically in `pending` or a review-related state. The task has not been claimed by a Worker yet (P22 does not call Worker).

### Who marks the task as completed

P23 does NOT mark the task as completed. Task completion happens after Worker execution finishes successfully. P23 only prepares the dispatch intent that authorizes the task to proceed.

### P22 and task state

P22 does not have authority to change task state. P23 dispatch intent preparation also does not change task state. Only future P23-D consumption would mutate task state, and only through the existing `TaskStateMachineService`.

### TaskReadinessService integration

P23 consumption preflight calls `TaskReadinessService.evaluate_task()` to confirm the source task is still in a valid state for dispatch. This happens at consumption time, not at intent preparation time.

### TaskRouterService integration

P23 does NOT use `TaskRouterService.route_next_task()`. The dispatch target is explicitly the source task, not a router-selected candidate. This prevents routing to an unrelated task.

### Scope boundary

All dispatch stays within the same project, same session, same confirmed plan. The P22 summary already binds `session_id` and `source_task_id`. P23 validates these bindings at every step.

## 6. Core Semantic: AUTO_REWORK

### Decision: Bounded rework of the source task

AUTO_REWORK means: the review found issues that require modification, and the system may attempt a bounded rework of the same source task. It does NOT mean: create a new task or rework a different task.

### Rework target

The exact source task identified by `source_task_id` in the P22 summary.

### Rework scope

Limited to the original confirmed scope. The P22 summary binds `review_scope_paths` and `source_diff_sha256`. Rework must not expand beyond these paths or the project's confirmed boundaries.

### Rework attempt tracking

```text
rework_attempt_index: int  (0-based, starts at 0 for first rework)
rework_attempt_limit: int  (configured maximum, default 3)
```

Each AUTO_REWORK dispatch intent increments `rework_attempt_index`. When `rework_attempt_index >= rework_attempt_limit`, further rework is blocked with `rework_attempt_limit_exhausted`.

### Non-convergence判定

If two consecutive rework attempts produce the same review fingerprint (same findings, same verdict), the system判定 non-convergence and escalates to human with `rework_non_convergence`.

### Budget exhausted

When `rework_attempt_index >= rework_attempt_limit`, the system does NOT automatically escalate. It blocks with `rework_attempt_limit_exhausted`. Human escalation must be explicitly triggered by a future governance decision.

### Automatic task modification

P23 does NOT modify task acceptance criteria. The task's acceptance criteria remain as originally confirmed.

### P22 summary reuse

Each rework attempt requires a fresh P22 summary. The old summary is consumed by the dispatch intent. A new review → new P22 → new dispatch intent for the next attempt.

## 7. Trusted P22 Summary Input Contract

### Client-provided fields

```text
session_id: UUID
source_task_id: UUID
source_p22_summary_message_id: UUID
```

All other fields are read from the persisted P22 summary message.

### P22 summary validation requirements

The persisted P22 summary message must satisfy ALL of:

```text
source_detail = p22_post_review_automation_orchestrated
action type = p22_post_review_automation_record
schema version = p22-b.v1
orchestration_status = ready_for_future_transition
route ∈ {automatic_continuation, bounded_automatic_rework}
disposition_type ∈ {AUTO_CONTINUE, AUTO_REWORK}
evidence_fresh = true
gate_allows_protected_transition_guardrail = true
gate_allows_write = false
blocked_reasons = []
source_review_message_id is present
source_disposition_message_id is present
source_consumption_preflight_message_id is present
source_consumption_message_id is present
source_handoff_message_id is present
source_freshness_message_id is present
```

### Rejection conditions

The service must reject:

```text
waiting_for_human
blocked
ESCALATE_TO_HUMAN
missing E evidence
corrupted summary (DomainModel reconstruction fails)
multiple conflicting summaries
cross session/task/project summary
already consumed summary
stale summary (freshness evidence expired)
```

### User confirmation

普通 AUTO_CONTINUE / AUTO_REWORK 不需要显式用户确认。P22 的 `evidence_fresh=true` 和 `gate_allows_protected_transition_guardrail=true` 已经是自动路径的授权前置。未来 API 层可以添加可选的用户确认，但 P23 service 层不默认要求。

## 8. Dispatch Intent DomainModel

### Status

```python
DispatchIntentStatus = Literal["prepared", "consumed", "blocked"]
```

### Dispatch kind

```python
DispatchKind = Literal[
    "auto_continue",
    "auto_rework",
]
```

### Target task strategy

```python
TargetTaskStrategy = Literal[
    "source_task_continue",
    "source_task_rework",
]
```

### Full model

```python
class ProjectDirectorProtectedTransitionDispatchIntent(DomainModel):
    dispatch_intent_status: DispatchIntentStatus
    dispatch_intent_id: UUID
    session_id: UUID
    project_id: UUID
    source_task_id: UUID

    source_p22_summary_message_id: UUID
    source_review_message_id: UUID
    source_disposition_message_id: UUID
    source_consumption_preflight_message_id: UUID
    source_consumption_message_id: UUID
    source_handoff_message_id: UUID
    source_freshness_message_id: UUID

    disposition_type: Literal["AUTO_CONTINUE", "AUTO_REWORK"]
    transition_kind: str
    transition_authority: Literal["AUTOMATED_DISPOSITION"]
    dispatch_kind: DispatchKind
    target_task_id: UUID
    target_task_strategy: TargetTaskStrategy

    rework_attempt_index: int = 0
    rework_attempt_limit: int = 3

    scope_binding: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=utc_now)
    consumed_at: datetime | None = None

    blocked_reasons: list[str] = Field(default_factory=list)

    # False-only flags (permanent)
    task_status_mutated: bool = False
    task_created: bool = False
    run_created: bool = False
    worker_started: bool = False
    runtime_started: bool = False
    continuation_started: bool = False
    rework_started: bool = False
    worktree_created: bool = False
    file_written: bool = False
    patch_applied: bool = False
    git_write_performed: bool = False
    gate_allows_write: bool = False
    product_runtime_git_write_allowed: bool = False

    ai_project_director_total_loop: Literal["Partial"] = "Partial"
```

### Field requirements

| Field | Required | Source | In fingerprint | Replay key |
|-------|----------|--------|----------------|------------|
| `dispatch_intent_status` | yes | computed | yes | no |
| `dispatch_intent_id` | yes | generated | no | no |
| `session_id` | yes | client + validated | yes | yes |
| `project_id` | yes | P22 summary | yes | no |
| `source_task_id` | yes | client + validated | yes | yes |
| `source_p22_summary_message_id` | yes | client | yes | yes |
| `source_review_message_id` | yes | P22 summary | yes | no |
| `source_disposition_message_id` | yes | P22 summary | yes | no |
| `source_consumption_preflight_message_id` | yes | P22 summary | yes | no |
| `source_consumption_message_id` | yes | P22 summary | yes | no |
| `source_handoff_message_id` | yes | P22 summary | yes | no |
| `source_freshness_message_id` | yes | P22 summary | yes | no |
| `disposition_type` | yes | P22 summary | yes | no |
| `transition_kind` | yes | P22 summary | yes | no |
| `transition_authority` | yes | P22 summary | yes | no |
| `dispatch_kind` | yes | computed from disposition_type | yes | no |
| `target_task_id` | yes | = source_task_id | yes | no |
| `target_task_strategy` | yes | computed from dispatch_kind | yes | no |
| `rework_attempt_index` | yes (default 0) | computed or prior intent | yes | no |
| `rework_attempt_limit` | yes (default 3) | config | yes | no |
| `scope_binding` | yes (default {}) | P22 summary | yes | no |
| `created_at` | yes | generated | no | no |
| `consumed_at` | nullable | set at consumption | no | no |
| `blocked_reasons` | yes (default []) | computed | no | no |

### Fingerprint computation

```text
canonical JSON of:
  session_id
  source_task_id
  source_p22_summary_message_id
  disposition_type
  dispatch_kind
  target_task_strategy
  rework_attempt_index
sorted keys, compact separators, UTF-8, SHA-256
```

### Replay key

```text
(session_id, source_task_id, source_p22_summary_message_id, dispatch_kind)
```

Same P22 summary for the same task and same dispatch kind must not produce two intents.

## 9. Append-Only Message Contract

### Intent message metadata

```text
role = assistant
source = system
intent = protected_transition_dispatch_intent
source_detail = p23_protected_transition_dispatch_intent_prepared
requires_confirmation = false
risk_level = high
```

### Action type

```text
p23_protected_transition_dispatch_intent_record
```

### Schema version

```text
p23-b.v1
```

### Naming rationale

- `p23` prefix: matches project stage numbering.
- `protected_transition_dispatch_intent`: describes the purpose — preparing a dispatch intent under protected transition guardrails.
- `prepared`: the intent is prepared, not consumed.
- `record`: the action is a record of intent, not an execution.

### Persistence

Use `ProjectDirectorMessage` append-only audit. No new DB table.

## 10. Freshness Revalidation Strategy

### At intent preparation time

P23 does NOT re-run E freshness service. Instead:

```text
1. Read P22 summary from persisted message
2. Validate action type, schema version, all source bindings
3. Reconstruct DomainModel from action dict
4. Verify evidence_fresh = true
5. Verify gate_allows_protected_transition_guardrail = true
6. Verify blocked_reasons = []
7. Verify all required source message IDs exist in database
8. Verify source messages have correct source_detail values
```

This is a strict evidence revalidation, not a freshness re-computation. The P22 summary is trusted because it was created by the verified P22 orchestrator.

### At future consumption time

P23-C consumption preflight must:

```text
1. Re-read P22 summary (same validation as above)
2. Verify dispatch intent not already consumed
3. Check source task current state via TaskReadinessService
4. Optionally re-run current freshness check if:
   - time since P22 summary creation exceeds configured threshold
   - workspace has been modified since P22 summary creation
5. Atomic consumption within BEGIN IMMEDIATE
```

### Freshness lifetime

P22 freshness is a point-in-time evidence. It remains valid as long as:

```text
- Source task has not been modified
- Workspace has not been externally modified
- No new review has been performed on the same diff
- Dispatch intent has not been consumed
```

### Workspace/diff change invalidation

If the workspace or diff changes after P22 summary creation, the freshness evidence becomes stale. P23-C consumption must detect this by comparing the current workspace state with the P22 summary's bound evidence.

## 11. TaskReadinessService Integration

### At preparation time

P23-A preparation does NOT call TaskReadinessService. The intent is prepared based on P22 evidence alone.

### At consumption time

P23-C consumption preflight calls:

```python
TaskReadinessService.evaluate_task(
    task_id=source_task_id,
)
```

If the task is not in a valid state for dispatch (e.g., already claimed, already completed, cancelled), consumption is blocked with `source_task_state_invalid`.

## 12. TaskRouterService Integration

P23 does NOT use TaskRouterService. The dispatch target is always the explicit `source_task_id`. This prevents routing to unrelated tasks.

## 13. TaskWorker Integration Boundary

### P23 does NOT call Worker

P23 only prepares and preflights the dispatch intent. It does not claim tasks, create Runs, or start Workers.

### Future Worker integration (P23-D)

When P23-D is implemented, the Worker must:

```text
1. Read the dispatch intent message
2. Validate intent is consumed but not yet executed
3. Claim the target task via TaskStateMachineService
4. Create a Run bound to the dispatch intent
5. Start runtime
6. Report execution result
```

### Worker discovery

P23-D must NOT allow the generic Worker loop to automatically discover and execute all consumed dispatch intents. Instead:

```text
Explicit task-scoped call entry point
→ Worker receives exact dispatch_intent_id
→ Worker validates intent binding
→ Worker claims task
→ Worker creates Run
→ Worker starts runtime
```

This prevents the Worker from accidentally executing stale or conflicting intents.

## 14. Intent Preparation Replay Key

### Key

```text
(session_id, source_task_id, source_p22_summary_message_id, dispatch_kind)
```

### Behavior

- Same key, first call: creates intent.
- Same key, second call: returns existing intent (idempotent replay).
- Different key (different P22 summary for same task): creates new intent (new evidence).

### Atomicity

Intent preparation uses `sqlite_immediate_transaction()`:

```text
BEGIN IMMEDIATE
→ scan existing intents for same replay key
→ one valid existing: return existing (replay)
→ no existing: create one
→ multiple or conflicting: fail-closed
COMMIT
```

## 15. Intent Consumption Replay Key

### Key

```text
dispatch_intent_id
```

### Behavior

- First consumption: marks intent as consumed, proceeds to task-system interaction.
- Second consumption: blocked with `dispatch_intent_already_consumed`.

### Atomicity

Consumption uses `sqlite_immediate_transaction()`:

```text
BEGIN IMMEDIATE
→ read intent by dispatch_intent_id
→ validate status = prepared
→ validate P22 summary still valid
→ validate task still ready
→ mark intent consumed (set consumed_at)
→ (future: mutate task state, create Run)
COMMIT
```

## 16. Concurrency and Transactions

### Intent preparation

Two concurrent preparations for the same replay key:

```text
Thread A: BEGIN IMMEDIATE → scan → no existing → create → COMMIT
Thread B: BEGIN IMMEDIATE → scan → finds A's intent → return existing
```

Result: one intent, both threads get a valid result.

### Intent consumption

Two concurrent consumptions of the same intent:

```text
Thread A: BEGIN IMMEDIATE → read → status=prepared → mark consumed → COMMIT
Thread B: BEGIN IMMEDIATE → read → status=consumed → blocked
```

Result: one consumption, one blocked.

### Task state mutation

Task state mutation happens inside the consumption transaction:

```text
BEGIN IMMEDIATE
→ read intent
→ validate intent
→ read task
→ validate task state
→ mutate task state (via TaskStateMachineService)
→ create Run
→ COMMIT
```

Worker start happens AFTER the transaction commits. If Worker start fails, the task is in a "dispatched but not started" state. A recovery mechanism must handle this.

### Worker start failure

If Worker start fails after task claim and Run creation:

```text
Task is claimed but Worker not started
→ next consumption attempt blocked (intent already consumed)
→ recovery: background scanner detects claimed task without active Worker
→ re-attempt Worker start
→ or: escalate to human
```

### Long-held locks

Worker start must NOT be inside the database transaction. The transaction commits before Worker process launch.

## 17. Blocked Reasons

### Intent preparation blocked

```text
source_p22_summary_missing
source_p22_summary_invalid
source_p22_summary_session_mismatch
source_p22_summary_task_mismatch
source_p22_summary_not_ready
source_p22_summary_human_route_unhandled
source_freshness_missing
source_freshness_not_ready
dispatch_intent_replay_conflict
rework_attempt_limit_exhausted
rework_non_convergence
budget_guard_blocked
human_escalation_required
```

### Intent consumption blocked

```text
dispatch_intent_already_consumed
source_task_state_invalid
target_task_not_ready
target_task_scope_mismatch
freshness_stale
```

### Task-system blocked (future P23-D)

```text
task_claim_conflict
run_creation_failed
worker_start_failed
```

## 18. Failure Recovery Taxonomy

### Intent preparation blocked

| Reason | Retry? | Action |
|--------|--------|--------|
| `source_p22_summary_missing` | no | requires fresh P22 orchestration |
| `source_p22_summary_invalid` | no | requires fresh P22 orchestration |
| `source_p22_summary_session_mismatch` | no | client error |
| `source_p22_summary_task_mismatch` | no | client error |
| `source_p22_summary_not_ready` | no | P22 summary is blocked/waiting |
| `source_p22_summary_human_route_unhandled` | no | human path not handled by P23 |
| `source_freshness_missing` | no | requires fresh P22 orchestration |
| `source_freshness_not_ready` | no | requires fresh P22 orchestration |
| `dispatch_intent_replay_conflict` | no | data integrity issue |
| `rework_attempt_limit_exhausted` | no | human escalation required |
| `rework_non_convergence` | no | human escalation required |
| `budget_guard_blocked` | no | governance policy blocked |
| `human_escalation_required` | no | human decision needed |

### Intent consumption blocked

| Reason | Retry? | Action |
|--------|--------|--------|
| `dispatch_intent_already_consumed` | no | idempotent replay returns existing |
| `source_task_state_invalid` | maybe | re-check task state, may need human |
| `target_task_not_ready` | maybe | re-check readiness |
| `target_task_scope_mismatch` | no | scope violation |
| `freshness_stale` | no | requires fresh P22 re-orchestration |

### Task-system blocked (future P23-D)

| Reason | Retry? | Action |
|--------|--------|--------|
| `task_claim_conflict` | yes | safe retry with backoff |
| `run_creation_failed` | yes | safe retry |
| `worker_start_failed` | yes | safe retry, then escalate |

### Freshness re-requirement

Any `freshness_stale` or `source_p22_summary_*` invalidation requires a complete fresh P22 re-orchestration: new review → new D-B → C1 → C2 → C3 → E → new summary.

### No infinite loop

The old P22 summary is consumed by the dispatch intent. A new rework attempt requires a new review and new P22 summary. This prevents the same stale summary from triggering unlimited rework.

## 19. P23 Stage Split

### P23-A: Contract Design (this document)

Defines DomainModel, service contracts, replay keys, concurrency, blocked reasons. No implementation.

### P23-B: Persisted Dispatch Intent Preparation

Implements `ProjectDirectorProtectedTransitionDispatchIntentService.prepare_dispatch_intent()`. Reads P22 summary, validates, creates append-only intent message.

### P23-C: Atomic Dispatch Intent Consumption Preflight

Implements consumption preflight. Validates intent not consumed, task state valid, freshness still valid. Marks intent as consumed atomically.

### P23-D: Controlled Task-System Integration

Implements task state mutation, Run creation, Worker start. Integrates with TaskStateMachineService, TaskReadinessService, TaskWorker.

### P23-E: Verification / Replay / Concurrency / Closure

Tests, verification, ledger closure.

### Stage status

```text
P23-A: this document
P23-B: Not started
P23-C: Not started
P23-D: Not started
P23-E: Not started
```

## 20. Non-Goals (Explicit)

P23-A does NOT:

- Add new API endpoint.
- Modify Worker.
- Create Task.
- Create Run.
- Start Worker.
- Start Codex or Claude.
- Run provider.
- Change TaskStatus.
- Write workspace.
- Apply patch.
- Execute git add / commit / push.
- Create PR.
- Merge.
- Delete or switch branch.
- Trigger CI.
- Record human decision.
- Modify frontend.
- Modify DB schema.

## 21. Permanent Safety Boundary

```text
Reviewer verdict is not human approval.
Automated disposition is not Git write authorization.
Freshness Gate is not transition execution.
Dispatch intent preparation is not transition execution.
Dispatch intent consumption is not transition execution.
AUTO_CONTINUE does not authorize Git write.
AUTO_REWORK does not authorize Git write.
P23 does not authorize Git write.

Automatic patch apply: Forbidden
Product runtime git add: Forbidden
Product runtime git commit: Forbidden
Product runtime git push: Forbidden
Automatic PR: Forbidden
Automatic merge: Forbidden
Branch deletion: Forbidden
Reset / checkout / switch / stash / rebase / tag: Forbidden
Automatic CI trigger: Forbidden
```

## 22. Open Questions

1. Should P23 support a `dry_run` mode that validates the chain without creating intent?
2. Should rework attempt limit be configurable per project or global?
3. Should P23-C consumption optionally re-run E freshness if the summary is older than a threshold?
4. Should the dispatch intent include a `freshness_evidence_fingerprint` for downstream revalidation?
5. Should P23-D Worker integration use a dedicated dispatch queue or the existing task claim loop?
6. How should P23 handle the case where the source task has been externally modified between P22 summary creation and P23 consumption?

---

## Status

```text
P22: Closed / Pass with verification note
P23-A design: completed only after review
P23-B: Not started
P23-C: Not started
P23-D: Not started
P23-E: Not started

AUTO_CONTINUE real execution: Not started
AUTO_REWORK real execution: Not started
Task/Run/Worker creation from P22 evidence: Not started
Product runtime Git write: Forbidden
AI Project Director total loop: Partial
```
