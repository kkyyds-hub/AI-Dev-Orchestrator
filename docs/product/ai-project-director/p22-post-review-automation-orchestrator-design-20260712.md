# P22-A: Post-Review Automation Orchestrator Design

## 1. Background and Problem

P21-C produces validated readonly review results. P21-D provides disposition, consumption, handoff, human escalation, and freshness gate services. Each service operates independently with its own transaction and append-only message.

Current gap: No unified entry point chains these services into a single deterministic post-review flow. A caller must manually invoke D-B, then C1, then C2, then C3, then E (or D1 for human escalation), handling blocked results and idempotent recovery at each step.

P22-A designs a `ProjectDirectorPostReviewAutomationService` that unifies this chain.

## 2. Current P21-D Fact Baseline

### Existing services and public methods

| Service | Method | Input | Success status |
|---------|--------|-------|----------------|
| D-B Disposition | `compute_candidate_diff_review_disposition` | review message | `disposition_status="computed"` |
| C1 Preflight | `prepare_candidate_diff_review_disposition_consumption` | disposition message | `preflight_status="ready"` |
| C2 Consumption | `prepare_candidate_diff_review_disposition_consumption` | preflight message | `consumption_status="consumed"` |
| C3 Handoff | `prepare_candidate_diff_review_disposition_handoff` | consumption message | `handoff_status="prepared"` |
| D1 Package | `prepare_human_escalation_package` | disposition message | `package_status="prepared"` |
| E Freshness | `prepare_protected_transition_evidence_freshness_gate` | handoff or D4 message | `freshness_status="ready"` |

### Disposition types

```text
AUTO_CONTINUE → automatic path → C1 → C2 → C3 → E
AUTO_REWORK   → automatic path → C1 → C2 → C3 → E
ESCALATE_TO_HUMAN → human path → D1 → stop
```

### Transaction model

Each sub-service wraps its work in `sqlite_immediate_transaction()` via the message repository. Each produces exactly one append-only `ProjectDirectorMessage` on success.

### What freshness success means

```text
evidence_fresh = true
gate_allows_protected_transition_guardrail = true
gate_allows_write = false
```

It does not execute any transition.

## 3. P22-A Goals

1. Single public entry point for post-review automation.
2. Deterministic routing: automatic vs human.
3. Automatic path chains D-B → C1 → C2 → C3 → E.
4. Human path chains D-B → D1, then stops.
5. Fail-closed at any blocked step.
6. Idempotent recovery: resume from last successful step.
7. One append-only orchestration summary message.
8. No Task, Run, Worker, worktree, file write, or Git write.

## 4. Non-Goals

- Real AUTO_CONTINUE task execution.
- Real AUTO_REWORK execution.
- Human decision recording.
- API endpoint (P22-B may add later, not in this design).
- Worker dispatch.
- Database migration.
- Frontend changes.

## 5. Automatic Path

```text
P21-C review message (source_review_message_id)
  │
  ▼
D-B: compute_candidate_diff_review_disposition
  │  disposition_type ∈ {AUTO_CONTINUE, AUTO_REWORK}
  │  → disposition_status == "computed"
  │
  ▼
C1: prepare_candidate_diff_review_disposition_consumption (C1 service)
  │  source = D-B message
  │  → preflight_status == "ready"
  │
  ▼
C2: prepare_candidate_diff_review_disposition_consumption (C2 service)
  │  source = C1 message
  │  → consumption_status == "consumed"
  │
  ▼
C3: prepare_candidate_diff_review_disposition_handoff
  │  source = C2 message
  │  → handoff_status == "prepared"
  │
  ▼
E: prepare_protected_transition_evidence_freshness_gate
  │  source = C3 message
  │  → freshness_status == "ready"
  │
  ▼
orchestration_status = ready_for_future_transition
```

At each step, if the sub-service returns blocked, the orchestrator stops and returns blocked with the original reasons preserved.

## 6. Human Escalation Path

```text
P21-C review message (source_review_message_id)
  │
  ▼
D-B: compute_candidate_diff_review_disposition
  │  disposition_type == "ESCALATE_TO_HUMAN"
  │  → disposition_status == "computed"
  │
  ▼
D1: prepare_human_escalation_package
  │  source = D-B message
  │  → package_status == "prepared"
  │
  ▼
orchestration_status = waiting_for_human
```

The orchestrator stops after D1. It does not:
- Create a human decision.
- Default to any decision.
- Call C1/C2/C3/E.
- Create Task/Run/Worker.

## 7. State Machine

### Internal step states

```text
started
  → disposition_computed
    → [automatic path]
      → automatic_preflight_ready
        → automatic_disposition_consumed
          → automatic_handoff_prepared
            → freshness_ready
    → [human path]
      → human_escalation_package_prepared
  → blocked
```

### External orchestration statuses

```text
ready_for_future_transition  (automatic path success)
waiting_for_human            (human path success)
blocked                      (any step failed)
```

### Transition rules

| From | Allowed next | Condition |
|------|-------------|-----------|
| started | disposition_computed | D-B success |
| started | blocked | D-B blocked |
| disposition_computed | automatic_preflight_ready | AUTO_CONTINUE or AUTO_REWORK, C1 success |
| disposition_computed | human_escalation_package_prepared | ESCALATE_TO_HUMAN, D1 success |
| disposition_computed | blocked | C1 blocked or D1 blocked |
| automatic_preflight_ready | automatic_disposition_consumed | C2 success |
| automatic_preflight_ready | blocked | C2 blocked |
| automatic_disposition_consumed | automatic_handoff_prepared | C3 success |
| automatic_disposition_consumed | blocked | C3 blocked |
| automatic_handoff_prepared | freshness_ready | E success |
| automatic_handoff_prepared | blocked | E blocked |

### Terminal states

- `freshness_ready` → terminal (maps to `ready_for_future_transition`)
- `human_escalation_package_prepared` → terminal (maps to `waiting_for_human`)
- `blocked` → terminal

### Non-retryable transitions

Once a step succeeds, its message is persisted. Recovery reads the existing message rather than re-creating it.

## 8. Unified Result Contract

Uses project-standard `DomainModel` (Pydantic) with `Literal`, `Field`, `field_validator`, `model_validator`.

```python
OrchestrationStatus = Literal[
    "ready_for_future_transition",
    "waiting_for_human",
    "blocked",
]
OrchestrationRoute = Literal[
    "automatic_continuation",
    "bounded_automatic_rework",
    "human_escalation",
    "none",
]

class ProjectDirectorPostReviewAutomationResult(DomainModel):
    orchestration_status: OrchestrationStatus
    orchestration_id: UUID
    route: OrchestrationRoute
    current_step: str

    # Exact source evidence IDs
    source_review_message_id: UUID
    source_disposition_message_id: UUID | None = None
    source_consumption_preflight_message_id: UUID | None = None
    source_consumption_message_id: UUID | None = None
    source_handoff_message_id: UUID | None = None
    source_freshness_message_id: UUID | None = None
    source_human_escalation_package_message_id: UUID | None = None

    # Disposition details
    disposition_type: str | None = None
    handoff_kind: str | None = None
    transition_kind: str | None = None
    transition_authority: str | None = None

    # Freshness gate results
    evidence_fresh: bool = False
    gate_allows_protected_transition_guardrail: bool = False

    # Human path
    waiting_for_human: bool = False
    human_escalation_package_created: bool = False

    # Recovery
    replay_check_completed: bool = False
    resumed_from_existing_evidence: bool = False

    # Blocked
    blocked_reasons: list[str] = Field(default_factory=list)

    # Timestamps
    created_at: datetime | None = None

    # False flags (permanent)
    continuation_started: bool = False
    rework_started: bool = False
    human_decision_recorded: bool = False
    task_created: bool = False
    run_created: bool = False
    worker_started: bool = False
    worktree_created: bool = False
    main_project_file_written: bool = False
    sandbox_file_written: bool = False
    manifest_file_written: bool = False
    diff_file_written: bool = False
    patch_applied: bool = False
    git_write_performed: bool = False
    gate_allows_write: bool = False
    product_runtime_git_write_allowed: bool = False
    ai_project_director_total_loop: str = Field(default="Partial")
```

### Validators

- `ready_for_future_transition` must have C3 and E bindings, `evidence_fresh=True`, `gate_allows_protected_transition_guardrail=True`.
- `waiting_for_human` must have D1 binding, `human_escalation_package_created=True`.
- `blocked` must have non-empty `blocked_reasons`.
- Automatic route must NOT have `source_human_escalation_package_message_id`.
- Human route must NOT have C1/C2/C3/E bindings.
- Success states must have all required exact IDs populated.
- All false flags must be `False`.
- `ai_project_director_total_loop` must be `"Partial"`.
- `route` must be consistent with `disposition_type`.

### False flags by path

Automatic path:
```text
human_escalation_package_created = false
product_runtime_git_write_allowed = false
```

Human escalation success path:
```text
human_escalation_package_created = true
human_decision_recorded = false
product_runtime_git_write_allowed = false
```

All paths:
```text
continuation_started = false
rework_started = false
task_created = false
run_created = false
worker_started = false
worktree_created = false
main_project_file_written = false
sandbox_file_written = false
manifest_file_written = false
diff_file_written = false
patch_applied = false
git_write_performed = false
gate_allows_write = false
product_runtime_git_write_allowed = false
ai_project_director_total_loop = "Partial"
```

## 9. Append-Only Message Contract

The orchestrator creates exactly one `ProjectDirectorMessage` on completion:

```text
role: assistant
source: system
intent: post_review_automation_orchestration
source_detail: p22_post_review_automation_orchestrated
requires_confirmation: False
risk_level: high
```

The message content summarizes the orchestration outcome. The suggested action contains the full result as a single action dict.

Forbidden actions detected:

```text
no_continuation_start
no_rework_start
no_task_creation
no_run_creation
no_worker_dispatch
no_worktree_creation
no_workspace_write
no_main_project_file_write
no_manifest_write
no_diff_file_write
no_patch_apply
no_product_runtime_git_write
no_pr_creation
no_merge
no_ci_trigger
no_human_decision_recording
```

## 10. Exact Evidence Binding

The orchestration result preserves exact message IDs from each sub-service:

| Field | Source |
|-------|--------|
| `source_review_message_id` | Input parameter |
| `source_disposition_message_id` | D-B result `.message.id` |
| `source_consumption_preflight_message_id` | C1 result `.message.id` |
| `source_consumption_message_id` | C2 result `.message.id` |
| `source_handoff_message_id` | C3 result `.message.id` |
| `source_freshness_message_id` | E result `.message.id` |
| `source_human_escalation_package_message_id` | D1 result `.message.id` |

The orchestrator does not re-derive these IDs. It reads them from the sub-service results.

## 11. Idempotency and Recovery

### Problem

Sub-services block on duplicate calls (e.g., "disposition already exists"). The orchestrator cannot simply re-invoke all services on retry.

### Strategy: Read-before-invoke

Before calling each sub-service, the orchestrator searches for an existing trusted message for that step:

```text
For each step S in [D-B, C1, C2, C3, E, D1]:
  1. Search session messages for source_detail matching S
  2. Check if any message binds to the same source_review_message_id chain
  3. Validate action type, schema version, binding IDs, DomainModel reconstruction
  4. If found and valid: skip invocation, use existing message
  5. If not found: invoke S
  6. If found but invalid: fail-closed with conflicting_existing_orchestration_evidence
```

### Identifying the same review chain

All messages in the chain bind to the same `source_review_message_id` (directly or transitively through disposition → preflight → consumption → handoff → freshness).

### Finding existing messages

```text
D-B:  source_detail == disposition_computed, action.source_review_message_id matches
C1:   source_detail == preflight_ready, action.source_disposition_message_id matches
C2:   source_detail == disposition_consumed, action.source_preflight_message_id matches
C3:   source_detail == handoff_prepared, action.source_consumption_message_id matches
E:    source_detail == freshness_validated, source matches C3 or D4
D1:   source_detail == package_prepared, action.source_disposition_message_id matches
```

### Duplicate blocked adoption

When a sub-service returns a duplicate/replay blocked reason (e.g., `already_preflighted`, `already_consumed`, `handoff_already_prepared`, `human_escalation_package_already_created`, `prior_freshness_validation_detected`), the orchestrator must NOT immediately treat this as a business blocked. Instead:

```text
Sub-service returns duplicate/replay blocked
→ Orchestrator re-reads the corresponding exact persisted message
→ Validates action type, schema version, source binding, DomainModel reconstruction
→ If unique and valid: adopt existing message, continue to next step
→ If invalid or multiple conflicting: fail-closed
```

Ordinary safety blocked reasons (e.g., `source_review_message_missing`, `review_result_fingerprint_mismatch`) must still cause immediate stop. Only duplicate/replay reasons trigger adoption.

### Conflict resolution

- Multiple valid messages for the same step → fail-closed with `conflicting_existing_orchestration_evidence`
- One valid message → resume from that point
- No messages → invoke the step

### Concurrent orchestration

Two concurrent orchestrator calls for the same review:
- First to complete creates the orchestration summary message.
- Second finds the existing summary and returns it (legitimate idempotent replay).
- If neither has completed, the sub-services' own `sqlite_immediate_transaction` prevents duplicate step messages.
- D-B is an exception: see §11b.

## 11b. D-B Replay-Safe Hardening

### Current gap

D-B `compute_candidate_diff_review_disposition()` currently does NOT use `sqlite_immediate_transaction()` and has no prior disposition replay guard. Two concurrent calls for the same review can produce two disposition messages.

### Required P22-B modification

Modify `runtime/orchestrator/app/services/project_director_sandbox_candidate_diff_review_disposition_service.py`:

1. `compute_candidate_diff_review_disposition()` must use `sqlite_immediate_transaction()`.
2. Remove standalone `message_repository.commit()` inside the method.
3. Within the same immediate transaction:
   - Read and validate source review.
   - Compute `review_result_fingerprint`.
   - Scan existing D-B dispositions in the same session.
   - Use exact key to identify same-chain disposition: `session_id`, `source_task_id`, `source_review_message_id`, `review_result_fingerprint`.
   - No existing record → create one disposition.
   - One unique valid record → return existing message/result.
   - Multiple or conflicting → fail-closed.
4. Do NOT change disposition computation logic.
5. Do NOT change AUTO_CONTINUE / AUTO_REWORK / ESCALATE_TO_HUMAN mapping.
6. Do NOT add Task, Run, Worker, or write capability.

### D-B replay identification fields

If the existing D-B domain result is not modified, the following fields exist only in the P22 unified result:

```text
replay_check_completed: bool
resumed_from_existing_evidence: bool
```

## 12. Concurrency and Replay

### Sub-service concurrency

C1, C2, C3, D1, E use `sqlite_immediate_transaction()` with built-in duplicate guards. D-B requires P22-B hardening (see §11b).

### Orchestrator concurrency

The orchestrator does NOT wrap all sub-services in one outer transaction. It relies on:
1. Sub-service transactions for each step.
2. The orchestration summary message creation as a separate atomic write (see §13).
3. Legitimate idempotent replay for the summary (see below).

### Legitimate idempotent replay

When the orchestrator finds exactly one existing orchestration summary that satisfies ALL of:
- Same `session_id`
- Same `source_task_id`
- Same `source_review_message_id`
- Correct action type and schema version
- Route and status are legal
- Exact source bindings are consistent
- DomainModel reconstruction succeeds
- False flags are legal

Then:
```text
Return the existing result
Do NOT create a new summary
Do NOT re-invoke any sub-service
orchestration_status保持原值
replay_check_completed = true
resumed_from_existing_evidence = true
```

This is NOT blocked.

### Replay conflict

`post_review_orchestration_replay_conflict` is returned ONLY when:
- Multiple summaries found for the same review
- Summary action cannot be reconstructed
- Session / task / review binding inconsistency
- Source evidence IDs inconsistency
- Fingerprint or route inconsistency
- Summary status inconsistent with persisted step chain

## 13. Transaction Boundary

### Principle

Do not wrap all sub-services in one giant nested transaction.

### Rationale

Each sub-service already uses `sqlite_immediate_transaction()`. Nesting would require the sub-services to detect an outer transaction and participate in it, which changes their contract.

### Design

```text
Orchestrator:
  1. Check for existing legitimate summary (see §12)
     → found: return existing result
  2. For each step:
       invoke sub-service (sub-service manages its own transaction)
       if blocked: stop, persist blocked summary, return blocked
  3. Create orchestration summary (own sqlite_immediate_transaction)
  4. Return result
```

Each sub-service call is independent. If the orchestrator crashes after C2 but before C3, the next invocation will find the existing C1 and C2 messages and resume from C3.

### Summary atomic anti-duplicate

The orchestration summary uses its own `sqlite_immediate_transaction()`. Within this single transaction:

```text
Scan existing summaries for same (session_id, source_task_id, source_review_message_id)
→ One unique valid summary: return existing result (legitimate replay)
→ No summary: create one
→ Multiple or conflicting: fail-closed
```

This must be atomic. Do NOT use:
```text
query outside transaction → exit transaction → create
```

### Summary replay key

At minimum: `session_id`, `source_task_id`, `source_review_message_id`. May additionally include `route` and final transition message ID.

### Domain blocked summary persistence

Blocked orchestration results from legitimate sub-service business failures ARE persisted as summary messages with `orchestration_status="blocked"`. This prevents silent failures and enables idempotent replay of blocked results.

### Runtime exception handling

Database exceptions, encoding exceptions, and unexpected exceptions must NOT:
- Be fabricated as trusted business blocked evidence
- Generate虚假 blocked summary messages
- Be silently swallowed

Instead: transaction rolls back, exception propagates upward. Subsequent retry recovers through existing step messages.

### Sub-service success, summary failure

If all sub-services succeed but the summary write fails, the next invocation will find all existing step messages and re-attempt only the summary write.

## 14. Blocked Propagation

Rules:

1. Any sub-service returning blocked → orchestrator stops immediately.
2. Subsequent services are not called.
3. Original blocked_reasons are preserved in the orchestration result.
4. Orchestrator may add its own reason (e.g., `post_review_disposition_blocked`).
5. Blocked reasons are never deleted or rewritten.
6. Blocked is never converted to waiting or success.
7. Freshness blocked does not return `ready_for_future_transition`.
8. Human path never enters automatic C1.
9. Automatic path never creates D1 package.

### Orchestrator-level blocked reasons

```text
post_review_disposition_blocked
automatic_preflight_blocked
automatic_consumption_blocked
automatic_handoff_blocked
protected_transition_freshness_blocked
human_escalation_package_blocked
conflicting_existing_orchestration_evidence
post_review_orchestration_replay_conflict
```

## 15. Dependency Injection

### Required dependencies

```python
class ProjectDirectorPostReviewAutomationService:
    def __init__(
        self,
        *,
        session_repository: ProjectDirectorSessionRepository,
        message_repository: ProjectDirectorMessageRepository,
        task_repository: TaskRepository,
        disposition_service: ProjectDirectorSandboxCandidateDiffReviewDispositionService,
        preflight_service: ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightService,
        consumption_service: ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionService,
        handoff_service: ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService,
        human_escalation_package_service: ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService,
        freshness_service: ProjectDirectorProtectedTransitionEvidenceFreshnessService,
    ) -> None
```

All dependencies are injected. The orchestrator does not construct any sub-service internally.

### Testing

For tests, sub-services can be replaced with fakes/spies that return controlled results. The orchestrator's logic is purely flow orchestration — it does not re-implement any evidence validation.

### What the orchestrator must NOT do

- Re-implement D-B's disposition logic.
- Re-implement C1/C2/C3 evidence validation.
- Re-implement D1 package validation.
- Re-implement E freshness validation.
- Read raw database tables directly (use repositories).
- Construct sub-services from settings or config.

## 16. Permanent Safety Boundary

```text
Reviewer verdict is not human approval.
Automated disposition is not Git write authorization.
Human escalation decision is not Git write authorization.
Decision consumption is not transition execution.
Freshness Gate is not transition execution.
Orchestration completion is not transition execution.
AUTO_CONTINUE does not authorize Git write.
AUTO_REWORK does not authorize Git write.
APPROVE_CONTINUE does not authorize Git write.
P21-D Pass does not open product runtime Git write.
P22 Pass does not open product runtime Git write.

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

## 17. P22-B Codex Implementation Scope

### Allowed new files

```text
runtime/orchestrator/app/domain/project_director_post_review_automation.py
runtime/orchestrator/app/services/project_director_post_review_automation_service.py
```

### Allowed modifications

```text
runtime/orchestrator/app/services/project_director_sandbox_candidate_diff_review_disposition_service.py
```

Only for D-B replay-safe hardening (see §11b): add `sqlite_immediate_transaction`, prior disposition scan, replay guard. Do NOT change disposition computation logic.

### Allowed modifications (if needed for imports)

```text
runtime/orchestrator/app/domain/__init__.py
runtime/orchestrator/app/services/__init__.py
```

Only if the project uses these export files. Otherwise do not modify.

### Forbidden in P22-B

- API routes
- Request/response schemas
- Worker dispatch
- Task/Run creation
- Executor dispatch
- Frontend
- Database migration
- Real AUTO_CONTINUE execution
- Real AUTO_REWORK execution
- Human decision recording
- Ledger documentation
- Tests
- Smoke scripts
- Closure documentation

### Acceptance criteria for P22-B

1. `ProjectDirectorPostReviewAutomationResult` DomainModel passes Pydantic validation.
2. `ProjectDirectorPostReviewAutomationService` constructs with all injected dependencies.
3. `orchestrate_post_review` method exists with correct signature.
4. Automatic path (AUTO_CONTINUE) chains D-B → C1 → C2 → C3 → E and returns `ready_for_future_transition`.
5. Automatic path (AUTO_REWORK) chains D-B → C1 → C2 → C3 → E and returns `ready_for_future_transition`.
6. Human path chains D-B → D1 and returns `waiting_for_human`.
7. Any blocked sub-step stops immediately and returns `blocked`.
8. Orchestration summary message is created with correct metadata.
9. All false flags are False in result and message.
10. No Task/Run/Worker/worktree/file/Git write.
11. `compileall` passes.
12. Import smoke passes.
13. D-B is idempotent for the same exact review chain.
14. D-B concurrent calls do not produce two dispositions.
15. Legitimate repeated orchestration returns existing summary, not blocked.
16. Summary scan + create is atomic within one `sqlite_immediate_transaction`.
17. Duplicate blocked from sub-services can be resolved via exact persisted evidence adoption.
18. Multiple or conflicting evidence fails closed.
19. Runtime exceptions do not generate虚假 blocked summary.
20. DomainModel validates route, status, binding, and false flags.
21. Human path correctly expresses `human_escalation_package_created=True`.
22. All paths maintain `product_runtime_git_write_allowed=False`.

## 18. P22-C Mimo Test Plan

### Automatic continuation success

```text
review → AUTO_CONTINUE → C1 → C2 → C3 → E ready
  verify: orchestration_status=ready_for_future_transition
  verify: route=automatic_continuation
  verify: all source IDs populated
  verify: freshness_status=ready
  verify: no Task/Run/Worker
```

### Automatic rework handoff success

```text
review → AUTO_REWORK → C1 → C2 → C3 → E ready
  verify: orchestration_status=ready_for_future_transition
  verify: route=bounded_automatic_rework
  verify: handoff_kind=bounded_automatic_rework
```

### Human escalation success

```text
review → ESCALATE_TO_HUMAN → D1 → waiting_for_human
  verify: orchestration_status=waiting_for_human
  verify: route=human_escalation
  verify: human_escalation_package_created=True (on D1)
  verify: no C1/C2/C3/E called
```

### Each step blocked

| Blocked step | Expected behavior |
|-------------|-------------------|
| D-B blocked | `orchestration_status=blocked`, `post_review_disposition_blocked` |
| C1 blocked | `orchestration_status=blocked`, `automatic_preflight_blocked` |
| C2 blocked | `orchestration_status=blocked`, `automatic_consumption_blocked` |
| C3 blocked | `orchestration_status=blocked`, `automatic_handoff_blocked` |
| E blocked | `orchestration_status=blocked`, `protected_transition_freshness_blocked` |
| D1 blocked | `orchestration_status=blocked`, `human_escalation_package_blocked` |

### Route safety

- ESCALATE_TO_HUMAN must not call C1/C2/C3/E.
- AUTO_CONTINUE must not call D1.
- AUTO_REWORK must not call D1.
- After blocked, no subsequent service called.

### Idempotency and recovery

| Scenario | Expected |
|----------|----------|
| First complete success | Creates orchestration summary |
| Second call same review | Returns existing result, no duplicate |
| Crash after D-B, retry | Resumes from C1 |
| Crash after C1, retry | Resumes from C2 |
| Crash after C2, retry | Resumes from C3 |
| Crash after C3, retry | Resumes from E |
| Conflicting evidence | `conflicting_existing_orchestration_evidence` |
| Concurrent calls | One success, one blocked or replay |

### D-B replay

| Scenario | Expected |
|----------|----------|
| D-B sequential replay | Returns existing disposition |
| D-B concurrent replay | One success, one adoption or blocked |

### Summary replay

| Scenario | Expected |
|----------|----------|
| Summary sequential replay | Returns existing summary |
| Summary concurrent replay | One success, one adoption or blocked |
| Legitimate existing summary | Returns existing result |
| Multiple summary conflict | `post_review_orchestration_replay_conflict` |
| Corrupted summary action | `post_review_orchestration_replay_conflict` |

### Duplicate blocked adoption

| Scenario | Expected |
|----------|----------|
| D-B duplicate blocked | Adopt existing, continue |
| C1 duplicate blocked | Adopt existing, continue |
| C2 duplicate blocked | Adopt existing, continue |
| C3 duplicate blocked | Adopt existing, continue |
| D1 duplicate blocked | Adopt existing, continue |
| E duplicate blocked | Adopt existing, continue |
| Ordinary safety blocked | Immediate stop, no adoption |

### Runtime exception handling

| Scenario | Expected |
|----------|----------|
| Runtime exception | No虚假 blocked summary, exception propagates |

### Result field verification

| Scenario | Expected |
|----------|----------|
| Human path | `human_escalation_package_created=True` |
| All paths | `product_runtime_git_write_allowed=False` |

### Permanent boundary verification

All success and blocked scenarios verify:

```text
continuation_started = False
rework_started = False
task_created = False
run_created = False
worker_started = False
worktree_created = False
main_project_file_written = False
sandbox_file_written = False
patch_applied = False
git_write_performed = False
gate_allows_write = False
ai_project_director_total_loop = "Partial"
```

## 19. Gate Conditions

### P22-A Gate

- Design covers automatic and human paths.
- State machine defined with terminal and non-terminal states.
- Result contract includes all required fields.
- Idempotency and recovery strategy documented.
- Transaction boundary documented.
- Blocked propagation rules documented.
- Dependency injection specified.
- Permanent safety boundary preserved.
- P22-B scope and acceptance criteria defined.
- P22-C test matrix defined.

### P22-B Gate

- Domain model compiles.
- Service compiles.
- All acceptance criteria in §17 met.
- No forbidden files modified.

### P22-C Gate

- All targeted tests pass.
- Adjacent regression passes.
- compileall passes.
- Import smoke passes.
- No production bugs found.

## 20. Open Questions

1. Should the orchestration summary message include the full sub-service action chain, or just reference IDs?
2. Should recovery search be paginated for sessions with many messages?
3. Should the orchestrator support a `dry_run` mode that validates the chain without creating messages?
4. Should the orchestration result include a `freshness_evidence_fingerprint` for downstream use?
5. Should the orchestrator be responsible for detecting stale reviews (review too old)?

---

## Status

```text
P22-A original design review: Partial
P22-A-R1 design correction: complete candidate, awaiting AI Project Director review
P22-B implementation: Not started
P22-C tests: Not started
AUTO_CONTINUE real execution: Not started
AUTO_REWORK real execution: Not started
AI Project Director total loop: Partial
Product runtime Git write: Forbidden
```
