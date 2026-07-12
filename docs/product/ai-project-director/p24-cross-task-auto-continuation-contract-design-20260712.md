# P24-A-R1: Cross-Task AUTO_CONTINUE Completion Authority Contract Refinement

## 1. Status and Decision

```text
P24-A-R1 scope: completion authority and completion policy contract refinement only
Production code: not changed
Tests: not changed and not run
Product runtime Git write: forbidden
AI Project Director total loop: Partial
```

P24 starts only after one exact source Task has durable success evidence. It resolves the immediately following Task from the ordered queue persisted by the same confirmed plan, builds an immutable instruction package, evaluates only that exact Task, reserves one exact Run, and invokes the Worker through an at-most-once claim/outcome boundary.

The current repository has a useful execution-success tuple, but it does **not** yet have a sufficient cross-task completion signal. `Task.status=completed` and `Run.status=succeeded` with `quality_gate_passed=true` prove the worker state machine's persisted completion result. They do not prove that every business-required verification was explicitly configured, atomically prove that delivery/approval obligations are settled, prove that no recovery is required, or provide an immutable `source_completion_evidence_id`. P24 therefore requires a new append-only source-completion evidence record before the next Task may start. Missing evidence always fails closed.

This document chooses an independent P24 lineage and audit stream over extending P23 records in place. P23 remains source-task-only. P24 may extract and reuse lower-level exact Task/Run reservation and Worker invocation primitives, but its package, idempotency identity, and continuation records are separate.

## 2. Repository Fact Baseline

### 2.1 Evidence references

| Concern | Repository evidence | Contract consequence |
|---|---|---|
| Task success transition | `TaskStateMachineService.build_execution_resolution()` in `runtime/orchestrator/app/services/task_state_machine_service.py` sets `TaskStatus.COMPLETED`, `RunStatus.SUCCEEDED`, and `quality_gate_passed=true` only when execution succeeds and verification passes, or when no verification is required | These persisted Task/Run fields are mandatory completion inputs |
| Stage completion | `TaskStateMachineService.is_project_stage_complete()` accepts only `TaskStatus.COMPLETED` | Failed, blocked, running, paused, and waiting-human Tasks cannot trigger P24 |
| Worker finalization | `TaskWorker._finalize_execution()` updates the Task and exact Run; `_execute_running_task_run()` commits them | P24 must reload persisted rows and never trust the returned `WorkerRunResult` alone |
| Delivery/approval timing | `TaskWorker._execute_running_task_run()` commits Task/Run before `_auto_create_run_deliverable()` and `_auto_create_run_approval()`; both helpers are best-effort and approval starts as `pending_approval` | Task/Run success is not sufficient proof that no human approval is pending |
| Publish completion | No `publish_completed` field, event, or record exists in the repository | P24 cannot infer publication/delivery completion; an explicit policy/result is required |
| P23 outcome | `ProjectDirectorProtectedTransitionWorkerInvocationService._build_outcome()` sets `continuation_started` when the shared execution seam was entered; it separately records Task/Run status and recovery flags | `continuation_started=true` proves start, not success |
| Exact Worker seam | `TaskWorker.run_reserved_once(task_id, run_id)` validates and executes one pre-existing running Task/Run without routing or creating another Run | Reusable after a P24-specific reservation and claim |
| P23 invocation safety | `ProjectDirectorProtectedTransitionWorkerInvocationService.invoke_reserved_protected_transition_worker()` performs claim transaction, external call outside a write transaction, then outcome transaction | Pattern is reusable; P23 domain identity is not |
| Exact task evaluation | `TaskRouterService.evaluate_exact_task_for_dispatch(task=...)` evaluates one caller-provided Task; `route_next_task()` scans/ranks the global pending queue | P24 must call only the exact evaluator |
| Base readiness | `TaskReadinessService.evaluate_task()` checks pending status, dependencies, human state, and pause state | Necessary but insufficient for P24 config/workspace/active-session checks |
| Plan task order | `ProjectDirectorTaskCreationService._create_tasks_atomic()` creates Tasks in `plan_version.proposed_tasks` order; `_create_task_queue_for_plan_version()` persists those IDs in the same order | `ProjectDirectorTaskCreationRecord.task_ids` is the authoritative queue |
| Task lineage | Task creation writes `source_draft_id = pdv:<plan_version_id>:<version_no>` | Parse only as a locator, then cross-check persisted plan and creation records |
| Creation uniqueness | `ProjectDirectorTaskCreationRecordTable` has `uq_task_creation_records_plan_version` | Exactly one creation record should exist per plan version |
| Creation-record parsing gap | `ProjectDirectorTaskCreationRecordRepository._to_domain()` silently drops malformed UUID entries | P24 needs a strict loader; lossy parsing must fail closed |
| Instruction sources | Confirmed plan version plus agent-team, skill, repository-binding, verification configs and `RepositoryWorkspace` contain scope/role/skill/verification/workspace facts | Suggestions or pending configs cannot authorize execution |

### 2.2 Current chain

```mermaid
flowchart LR
    A["P21-C persisted review"] --> B["P22 post-review automation"]
    B --> C["P23 dispatch intent and preflight"]
    C --> D["source Task atomic claim and exact Run"]
    D --> E["Worker start reservation"]
    E --> F["durable invocation claim"]
    F --> G["TaskWorker.run_reserved_once(source Task, exact Run)"]
    G --> H["durable invocation outcome"]
```

P23's target remains `source_task_id`. It does not locate another Task and does not prove that the source Task eventually satisfied every P24 completion obligation.

### 2.3 P24 target chain

```mermaid
flowchart LR
    A["source Task durable success"] --> B["source completion evidence"]
    B --> C["confirmed plan queue resolver"]
    C --> D["exact next Task"]
    D --> E["immutable instruction package"]
    E --> F["exact readiness and config gates"]
    F --> G["continuation root record"]
    G --> H["atomic exact Task claim and Run"]
    H --> I["Worker start reservation"]
    I --> J["invocation claim"]
    J --> K["TaskWorker.run_reserved_once(next Task, exact Run)"]
    K --> L["durable invocation outcome"]
```

## 3. Source Completion Authority, Policy, and Evidence Contract

### 3.1 Current repository conclusion

The repository does **not** currently expose a single reliable `source_completion_evidence` suitable for P24. The following values are explicitly insufficient on their own:

```text
P23 or P24 continuation_started = true
Worker was called
Worker returned an in-memory object
Run was created
Task entered running
Task.status = completed without an exact successful Run binding
Run.status = succeeded without the matching Task and immutable completion policy
```

The strongest existing execution-success tuple is:

```text
Task.id = source_task_id
Task.status = completed
Task.human_status in {none, resolved}
Task.paused_reason is null

Run.id = source_success_run_id
Run.task_id = source_task_id
Run.status = succeeded
Run.finished_at is not null
Run.quality_gate_passed = true
Run.failure_category is null

durable Worker outcome.task_id = source_task_id
durable Worker outcome.run_id = source_success_run_id
durable Worker outcome.outcome_status = returned
durable Worker outcome.worker_result_contract_valid = true
durable Worker outcome.human_recovery_required = false
durable Worker outcome.blocked_reasons = []
durable Worker outcome.worker_reported_git_write_activity = false
```

This tuple must be reconstructed from persisted rows and append-only messages. It cannot be read from a Worker return value. It still needs an immutable completion-policy snapshot and the exact evidence required by that policy.

### 3.2 General execution authority lineage

Completion evidence is authority-neutral. It does not require a P23 outcome specifically. P24-B introduces:

```text
SourceExecutionAuthorityKind = {
  p23_protected_transition,
  p24_cross_task_continuation
}

ProjectDirectorSourceExecutionAuthorityResolver
SourceExecutionAuthoritySnapshot
```

Resolver input:

```text
authority_kind
authority_record_id
source_task_id
source_run_id
```

Unified immutable snapshot fields:

```text
schema_version
authority_kind
authority_id
authority_fingerprint

reservation_id
reservation_fingerprint
claim_id
claim_fingerprint
outcome_id
outcome_schema_version
outcome_fingerprint

task_id
run_id
outcome_status
worker_result_contract_valid
recovery_required
blocked_reasons
worker_reported_git_write_activity
product_runtime_git_write_allowed

source_review_id
source_review_outcome
source_transition_evidence_ids
```

The resolver dispatches to a strict adapter by `authority_kind`:

| Authority kind | Adapter | Required persisted lineage |
|---|---|---|
| `p23_protected_transition` | `P23ProtectedTransitionExecutionAuthorityAdapter` | P23 D1 exact source Task/Run record, B1 reservation, B2 claim, B2 outcome, and their fingerprints |
| `p24_cross_task_continuation` | `P24CrossTaskExecutionAuthorityAdapter` | P24 continuation/package authority, exact next Task/Run record, P24 reservation, P24 claim, P24 outcome, and their fingerprints |

Both adapters must:

1. Load every authority/reservation/claim/outcome record from persistence and strictly reconstruct its declared schema.
2. Verify the authority, reservation, claim, and outcome form one unbroken lineage.
3. Verify every record binds the exact input Task and Run.
4. Require one durable outcome with `outcome_status=returned`, `worker_result_contract_valid=true`, `recovery_required=false`, empty blocked reasons, and no product runtime Git activity.
5. Require `product_runtime_git_write_allowed=false` throughout.
6. Reload the exact Task and Run from their repositories after reconstructing the authority; never accept the Worker's in-memory return value as completion.
7. Fail closed on missing, duplicate, malformed, unsupported-version, fingerprint-mismatched, or cross-authority records.

P23 compatibility aliases may be present for audit:

```text
source_p23_invocation_outcome_id: UUID | null
source_p24_invocation_outcome_id: UUID | null
```

They are not the general decision fields. The decision uses `source_execution_authority_kind`, `source_execution_authority_id`, and the unified outcome identity.

### 3.3 Completion policy repository fact decision

The current repository has useful policy **inputs**, but no trustworthy Task-scoped record that immutably decides all four completion axes.

| Axis | Existing facts | What they can prove | What they cannot prove |
|---|---|---|---|
| Review | P21-C validated review output has `review_status=reviewed` and verdicts `no_blocking_findings`, `non_blocking_findings`, `changes_required`; P21-D disposition binds its fingerprint | An exact persisted review happened and its result | Whether review is required for an arbitrary P24 Task, or that absence means not required |
| Verification | Confirmed `ProjectDirectorVerificationConfig` contains mechanisms and evidence requirements | Confirmed plan-level verification intent | Which mechanism is mandatory for one exact Task; absence/empty config cannot prove not required |
| Delivery | Confirmed plan has `deliverable_boundaries`; Deliverable rows can bind a source Task/Run | Expected plan-level artifacts and an actual persisted artifact version | A Task-specific required/not-required decision; absence cannot prove not required; no `publish_completed` signal exists |
| Approval | `ApprovalRequest` has `pending_approval`, `approved`, `rejected`, `changes_requested`; Worker best-effort creates pending approval after successful Run | State of an exact deliverable-version approval request | Whether approval is required for the Task; no row cannot prove not required |
| Human confirmation | P4-F `HumanApprovalRecord` has fingerprint and expiry | Approval of `git_add_commit_preview` only | It cannot authorize a completion policy because its scope/action enum is delivery-Git specific |

Confirmed repository-binding and agent-team configs remain required scope/role inputs, but they do not decide any completion axis. Task acceptance criteria and confirmed plan acceptance criteria are evidence inputs, not a substitute for an explicit policy decision.

Therefore P24 chooses one explicit solution: a new append-only policy proposal, an exact policy decision/confirmation record, and an immutable confirmed snapshot. P24-B may not invent, default, or silently normalize any core policy axis.

Policy-source resolution order is explicit and fail closed:

1. An exact immutable, Task-scoped confirmed requirement record would be authoritative if the repository had one; the current repository has none for any of the four axes.
2. Therefore, for P24 v1, the new `ProjectDirectorTaskCompletionPolicyDecision` is the only record allowed to decide `required` versus `not_required`, and its immutable confirmed snapshot is the only authority consumed by completion evidence.
3. Confirmed plan version, exact Task acceptance criteria, confirmed verification config, confirmed repository-binding config, confirmed agent-team config, deliverable boundaries, approval workflow records, and exact human-confirmation evidence are ordered proposal inputs and later satisfaction evidence. They may justify a proposed `required` value or prove that a required axis was satisfied, but they cannot independently decide `not_required` or override the Task-scoped decision.
4. Mutable Task fields, missing/empty config, missing Deliverable/Approval rows, and pending/rejected configs have no policy authority. Conflicting same-priority inputs or any missing confirmation leave the axis `unresolved`.

For review the trusted terminal evidence is the exact persisted P21-C-style validated review plus its disposition/fingerprint; for verification it is exact successful evidence matching the confirmed verification mechanism; for delivery it is an exact Task/Run-bound persisted deliverable version of the kind named by policy; for approval it is an exact `approved` request for that required deliverable version. These records satisfy a `required` axis only after the policy decision made it required. For every axis, only the new owner decision with non-empty reason evidence can prove `not_required`.

### 3.4 Completion policy proposal and confirmation seam

#### Proposal record

`ProjectDirectorTaskCompletionPolicyProposal` is append-only:

```text
source_detail = p24_task_completion_policy_proposed
intent = task_completion_policy_proposal
action type = p24_task_completion_policy_proposal_record
schema_version = p24-b-completion-policy-proposal.v1
related_plan_version_id = exact confirmed plan
related_project_id = exact project
related_task_id = exact Task
```

`prepare_task_completion_policy_proposal()` accepts only exact plan/creation-record/Task IDs. It loads the confirmed plan and confirmed configs, snapshots all relevant source IDs/fingerprints, and proposes each axis as `required` only where the source is explicit and Task-applicable. With the current schemas, plan-level review/verification/delivery/approval facts are not sufficiently Task-specific, so the affected axis remains `unresolved`. It never proposes `not_required` from absence.

Proposal idempotency key:

```text
sha256(canonical_json({
  schema_version: "p24-policy-proposal-replay.v1",
  action: "propose_task_completion_policy",
  session_id,
  project_id,
  plan_version_id,
  task_creation_record_id,
  task_id,
  policy_source_bundle_fingerprint
}))
```

The proposal is created/replayed under `BEGIN IMMEDIATE`. Changed source facts create a conflict or an explicit new proposal; they never mutate an existing proposal.

#### Policy decision record

`ProjectDirectorTaskCompletionPolicyDecision` is a new append-only, Task-scoped human/owner governance record. Existing P4-F Git-preview approvals cannot be reused.

```text
source_detail = p24_task_completion_policy_decided
intent = task_completion_policy_decision
action type = p24_task_completion_policy_decision_record
schema_version = p24-b-completion-policy-decision.v1

decision_id
decision_fingerprint
proposal_id
session_id
project_id
plan_version_id
task_creation_record_id
task_id
review_requirement
verification_requirement
delivery_requirement
approval_requirement
axis_reason_codes
confirmed_source_evidence_ids
decided_by
client_request_id
created_at
product_runtime_git_write_allowed = false
```

All four requirements must be explicitly selected as `required` or `not_required`. `unresolved` cannot be confirmed. Every `not_required` choice requires a non-empty reason code and exact human decision evidence. Every `required` choice identifies the acceptable evidence kind and terminal result. Reused `client_request_id`, mismatched proposal, or malformed fingerprint fails closed.

Decision idempotency key:

```text
(proposal_id, client_request_id, action=decide_task_completion_policy)
```

The decision and confirmed snapshot are appended in one `BEGIN IMMEDIATE` transaction after full lineage revalidation. P24-B exposes the domain/service entry only; it adds no API and cannot self-confirm on behalf of the user/owner.

### 3.5 Immutable completion policy snapshot

`ProjectDirectorTaskCompletionPolicySnapshot` is the only policy authority accepted by completion evidence.

```text
schema_version
completion_policy_id
completion_policy_version
completion_policy_fingerprint
completion_policy_status
created_at

session_id
project_id
plan_version_id
task_creation_record_id
task_id

source_proposal_id
source_decision_id
supersedes_completion_policy_id

review_requirement
verification_requirement
delivery_requirement
approval_requirement

review_policy_source
verification_policy_source
delivery_policy_source
approval_policy_source

review_policy_evidence_ids
verification_policy_evidence_ids
delivery_policy_evidence_ids
approval_policy_evidence_ids

required_terminal_task_status
required_terminal_run_status
required_quality_gate_result
required_review_terminal_results
required_verification_evidence_kinds
required_delivery_evidence_kinds
required_approval_terminal_results

human_confirmation_required
human_confirmation_evidence_id

product_runtime_git_write_allowed
forbidden_actions
```

Requirement values are:

```text
required
not_required
unresolved
```

Proposal/blocked snapshots may contain `unresolved` for audit. Only `completion_policy_status=confirmed`, with all four axes in `{required, not_required}`, an exact policy decision, `human_confirmation_required=true`, and matching confirmation evidence may authorize completion evidence. Version 1 starts at `1`; any change creates a new snapshot ID/version/fingerprint and links `supersedes_completion_policy_id`. Old completion evidence always replays against its original snapshot.

Fingerprint covers all semantic fields except `completion_policy_fingerprint`. Replay key:

```text
(source_proposal_id, source_decision_id, completion_policy_version,
 action=confirm_task_completion_policy)
```

#### Axis satisfaction rules

| Axis | `required` | `not_required` | `unresolved` |
|---|---|---|---|
| Review | Exact persisted review ID must bind the authority Task/Run or its declared candidate evidence; validation status is valid and verdict is in the policy's passing set (normally `no_blocking_findings` or `non_blocking_findings`) | Review ID may be null only because the confirmed snapshot and decision explicitly say not required | Fail closed |
| Verification | Exact Run verification evidence must match policy mechanism/evidence IDs, succeed, and quality gate must be true | Verification evidence may be absent only because the confirmed decision says not required; null `verification_mode` alone is irrelevant | Fail closed |
| Delivery | Exact source Task/Run-bound Deliverable and version must satisfy the policy's declared terminal evidence kind; current v1 can use `deliverable_version_persisted`, not nonexistent `publish_completed` | No Deliverable may be required only by explicit confirmed decision | Fail closed |
| Approval | Exact approval for the required deliverable version must be `approved`; pending/rejected/changes-requested blocks | No Approval row is acceptable only with explicit confirmed decision | Fail closed |

This seam has a real positive path: explicit proposal -> owner decision for all four axes -> confirmed immutable snapshot -> persisted authority outcome and Task/Run success -> required-axis evidence (or explicitly confirmed not-required axes) -> completion evidence. It is not an always-blocked placeholder.

### 3.6 General completion evidence model

P24-B introduces `ProjectDirectorSourceTaskCompletionEvidence` as an immutable DomainModel persisted in an append-only `ProjectDirectorMessage`. It is a derived completion certificate, not a mutable Task field.

```text
source_detail = p24_source_task_completion_evidence_recorded
intent = cross_task_source_completion_evidence
action type = p24_source_task_completion_evidence_record
schema_version = p24-b-completion.v2
related_plan_version_id = exact plan version
related_project_id = exact project
related_task_id = source Task
```

Required fields:

```text
schema_version
completion_evidence_id
completion_fingerprint
created_at

session_id
project_id
plan_version_id
task_creation_record_id
source_task_id
source_success_run_id

source_execution_authority_kind
source_execution_authority_id
source_execution_authority_fingerprint
source_worker_start_reservation_id
source_worker_invocation_claim_id
source_worker_invocation_outcome_id
source_worker_outcome_schema_version
source_worker_outcome_fingerprint

source_p23_invocation_outcome_id: UUID | null
source_p24_invocation_outcome_id: UUID | null
source_review_id: UUID | null
source_review_outcome: string | null
source_transition_evidence_ids

completion_policy_id
completion_policy_version
completion_policy_fingerprint

task_status
task_human_status
task_paused_reason_absent
run_status
run_finished_at
run_quality_gate_passed
run_failure_category_absent

review_requirement
review_evidence_ids
verification_requirement
verification_evidence_ids
delivery_requirement
deliverable_id: UUID | null
deliverable_version_id: UUID | null
approval_requirement
approval_id: UUID | null
approval_status: string | null

agent_session_id
agent_session_status
agent_session_phase
runtime_terminal
pending_human_approval_absent
recovery_required
worker_reported_git_write_activity
product_runtime_git_write_allowed
blocked_reasons
```

`source_review_id` and `source_review_outcome` are conditional: required policy needs an exact passing review; not-required policy permits null; unresolved policy blocks. `source_p23_invocation_outcome_id` and `source_p24_invocation_outcome_id` are optional audit aliases, with exactly one populated according to authority kind.

### 3.7 Issuance predicate

The evidence resolver may issue `completion_status=confirmed` only when all predicates are true:

1. Resolve a valid unified execution authority snapshot for either P23 or P24, with exact Task/Run lineage and no recovery, blocked reason, or Git activity.
2. Reload the persisted Task and exact Run and require the execution-success tuple in section 3.1.
3. Load the exact immutable completion policy by ID/version and verify its fingerprint, confirmed status, proposal/decision lineage, and same session/project/confirmed plan/creation record/Task.
4. Evaluate review, verification, delivery, and approval independently against the frozen policy. Every axis must be satisfied according to `required` or explicitly confirmed `not_required`; any `unresolved` blocks.
5. If an AgentSession exists for the Run, it is `completed`, phase is `finalized`, its Task/Run binding matches, and no active runtime state remains. Missing or multiple conflicting sessions fail closed.
6. No pending Task human state, pending required approval, active Run/AgentSession, authority recovery flag, or detected product runtime Git activity exists.
7. `product_runtime_git_write_allowed=false` is fixed in authority, policy, and evidence.

The completion fingerprint covers authority kind/ID/fingerprint, outcome schema/fingerprint, policy ID/version/fingerprint, Task/Run terminal facts, and all axis evidence IDs/results. It never reinterprets historical evidence using current mutable plan/config/Task state.

### 3.8 Identity, replay, and multi-hop continuation

Stable completion identity:

```text
(plan_version_id,
 source_task_id,
 source_success_run_id,
 source_execution_authority_kind,
 source_execution_authority_id,
 completion_policy_id,
 completion_policy_version,
 action=source_task_completion)
```

The resolver runs inside `BEGIN IMMEDIATE`, scans complete history, strictly reconstructs authority/policy/evidence, and returns one exact existing record or creates one. Multiple records, malformed history, a policy identity mismatch, or changed authority/policy fingerprint produces `source_completion_evidence_conflict` and requires human recovery. Replay loads the original policy snapshot; it does not re-run policy inference from current configs.

The SHA-256 fingerprint uses canonical JSON: sorted object keys, canonical lowercase UUIDs, UTC RFC 3339 datetimes, preserved plan order, and normalized set-like arrays. It covers all semantic fields including evidence ID and bound IDs, excluding only `completion_fingerprint` and replay-only response flags.

The schema supports continuous progression, not a single cross-task jump:

```mermaid
flowchart LR
    T1["Task 1"] --> P23["P23 durable outcome"]
    P23 --> E1["completion evidence 1"]
    E1 --> T2["P24 starts Task 2"]
    T2 --> O2["P24 durable outcome"]
    O2 --> E2["completion evidence 2"]
    E2 --> T3["P24 starts Task 3"]
    T3 --> O3["P24 durable outcome"]
    O3 --> E3["completion evidence 3"]
    E3 --> X["plan_queue_exhausted"]
```

Task 1 may use `p23_protected_transition`. Tasks 2 and later use `p24_cross_task_continuation`. Both adapters return the same `SourceExecutionAuthoritySnapshot`, and all Tasks use the same completion-policy and completion-evidence schemas. P24 therefore supports an arbitrary confirmed queue length subject to per-Task policy and readiness gates.

## 4. Confirmed Plan Lineage Contract

### 4.1 Safe `source_draft_id` parsing

The resolver accepts only this grammar:

```text
^pdv:([0-9a-fA-F-]{36}):([1-9][0-9]*)$
```

It then parses group 1 as a UUID and requires its canonical UUID text to equal the parsed value case-insensitively. Group 2 is a positive base-10 integer with no sign. Extra segments, whitespace, noncanonical UUIDs, zero/negative version numbers, or overflow are `plan_lineage_invalid`.

The string is only a locator. It is never the authority.

### 4.2 Cross-validation algorithm

For `source_task_id` and trusted completion evidence:

1. Reload the source Task and require the exact Task/Run/evidence binding.
2. Parse `source_task.source_draft_id` into `(plan_version_id, version_no)`.
3. Load the plan with `ProjectDirectorPlanVersionRepository.get_by_id()` and require `status=confirmed`.
4. Load exactly one `ProjectDirectorTaskCreationRecord` by `plan_version_id`.
5. Require the creation record's `source_type=project_director_plan_version`.
6. Require plan ID/version/session/project to match the parsed locator, completion evidence, Task project, creation record, and current Project Director session.
7. Strictly decode raw `task_ids_json`. It must be a JSON array of canonical UUIDs with no dropped/invalid entries, no duplicates, and `task_count == len(task_ids) > 0`.
8. Require `len(task_ids) == len(plan_version.proposed_tasks)` because task creation preserves that order.
9. Load every Task ID. Missing Tasks are a persistence fault. Every Task must have the same project and exact `pdv:<id>:<version>` lineage.
10. Require `source_task_id` to occur exactly once.

The current creation repository's lossy UUID parsing is not acceptable for this resolver. P24-C must add a strict read path or strict raw-row validation without weakening existing callers.

### 4.3 Ambiguity and rejection

Fail closed for:

```text
source_draft_id malformed or missing
plan version missing, not confirmed, or version mismatch
creation record missing or multiple/conflicting
session or project mismatch
task_ids malformed, empty, duplicated, truncated, or count-mismatched
source Task absent from task_ids or present more than once
any queue Task missing or carrying different lineage
plan proposed-task count mismatch
```

## 5. Exact Next Task Resolution

The authoritative algorithm is:

```text
source_index = task_ids.index(source_task_id)
next_index = source_index + 1

if next_index == len(task_ids):
    plan_queue_exhausted
else:
    next_task_id = task_ids[next_index]
```

The resolver then reloads `next_task_id` and revalidates its project and lineage. It never creates or reconstructs a business Task.

Permanent selection rules:

```text
Do not call TaskRouterService.route_next_task().
Do not scan the global pending queue.
Do not rank by priority to change plan order.
Do not cross project, session, or plan version.
Do not skip a blocked next Task.
Do not call create_tasks_from_plan_version().
Do not call create_formal_project_from_plan_version().
Do not recreate a missing next Task from ProposedTask.
Do not synthesize a continuation Task.
```

If the creation record names a next Task that is absent from the Task table, return `next_task_missing`, classify it as persistence corruption, and require human recovery.

Resolver outcomes:

```text
next_task_resolved
plan_queue_exhausted
source_task_not_in_plan_queue
plan_creation_record_missing
plan_lineage_invalid
next_task_missing
next_task_not_ready
next_task_state_conflict
next_task_dependency_blocked
next_task_budget_blocked
human_intervention_required
```

## 6. Immutable Next Task Instruction Package

### 6.1 Domain and persistence

P24-D introduces `ProjectDirectorNextTaskInstructionPackage`. It is stored as one append-only Project Director message and may never be edited after it is referenced by a Run reservation.

```text
source_detail = p24_next_task_instruction_package_prepared
intent = cross_task_next_task_instruction_package
action type = p24_next_task_instruction_package_record
schema_version = p24-d-instruction.v1
```

Required fields:

```text
schema_version
package_id
package_fingerprint
created_at
continuation_id

project_id
session_id
plan_version_id
plan_version_no
task_creation_record_id

source_task_id
source_run_id
source_completion_evidence_id
source_execution_authority_kind
source_execution_authority_id
source_execution_authority_fingerprint
source_worker_start_reservation_id
source_worker_invocation_claim_id
source_worker_invocation_outcome_id
source_worker_outcome_schema_version
source_worker_outcome_fingerprint
completion_policy_id
completion_policy_version
completion_policy_fingerprint
review_requirement
source_review_id: UUID | null
source_review_outcome: string | null
source_transition_evidence_ids

next_task_id
next_task_index
task_count
task_title
task_input_summary
owner_role_code
priority
depends_on_task_ids

confirmed_scope
allowed_paths
forbidden_paths
repository_binding
workspace_binding

acceptance_criteria
verification_requirements
test_requirements
evidence_requirements

selected_strategy
selected_model
selected_skills
risk_level
human_confirmation_required
human_confirmation_evidence_id

product_runtime_git_write_allowed
forbidden_actions
```

### 6.2 Source precedence and fail-closed rules

| Package data | Trusted source | Rejection rule |
|---|---|---|
| Source execution authority | Completion evidence's exact unified P23/P24 authority kind, ID, outcome identity/schema/fingerprint | Missing, unsupported, Task/Run-mismatched, or fingerprint-divergent authority blocks |
| Source completion policy | Completion evidence's exact immutable confirmed policy ID/version/fingerprint | Current config must not reinterpret the frozen source policy; identity/fingerprint mismatch blocks |
| Source review | Frozen completion policy plus completion evidence | `required` needs the exact passing review ID/outcome; `not_required` requires both fields null; `unresolved` blocks |
| Plan/task identity and order | Confirmed plan + strict creation record + persisted next Task | Any mismatch blocks |
| Task title/input/owner/priority/dependencies | Persisted next Task, cross-checked by index against `proposed_tasks[next_index]` | Missing role or divergent lineage blocks |
| Confirmed scope | Confirmed plan `project_scope`, deliverable boundaries, and next ProposedTask description | Empty or contradictory scope blocks |
| Allowed paths | `status=confirmed` repository-binding config `focus_paths`, normalized relative to the real RepositoryWorkspace root | Never infer from the source Task review scope; empty, absolute, escaping, or ambiguous paths block |
| Forbidden paths | Confirmed plan out-of-scope path entries plus repository/workspace safety policy | Contradiction with allowed paths blocks |
| Repository binding | Confirmed repository-binding config for the exact plan | Pending/rejected/missing config blocks |
| Workspace binding | `RepositoryWorkspaceRepository.get_by_project_id()` exact project binding | Missing workspace, root mismatch, or path escape blocks |
| Acceptance criteria | Persisted Task criteria when non-empty, otherwise confirmed plan acceptance criteria | If both are empty, block |
| Verification/test/evidence requirements | Confirmed verification config for exact plan, filtered for the next Task/role; plan acceptance/deliverable evidence requirements supplement it | Pending/rejected/missing required config blocks |
| Role | Next Task owner plus confirmed agent-team config | Missing team role or role mismatch blocks |
| Skills | Confirmed skill-binding config for the resolved owner role, intersected with exact strategy output | Missing required binding or unconfirmed skill blocks |
| Model/strategy | Fresh `evaluate_exact_task_for_dispatch(next_task)` result | Result is a snapshot; revalidate before Run creation |
| Human confirmation | Risk/config policy plus an exact persisted confirmation record | Required but absent/expired/mismatched confirmation blocks |

Task creation currently leaves Task acceptance criteria/dependencies at defaults and creates repository/skill/verification configs initially as `pending_confirmation`. P24 must not reinterpret those defaults as authorization. It must use the confirmed plan/config sources above and fail closed until they are confirmed.

The package always contains:

```text
product_runtime_git_write_allowed = false
```

Its forbidden actions include product runtime `git add`, `git commit`, `git push`, PR/merge, branch destruction, uncontrolled workspace writes, global Task routing, plan mutation, and duplicate Task creation.

### 6.3 Immutability and versioning

The fingerprint uses the same canonical JSON rules as completion evidence and covers every field except `package_fingerprint`. A replay returns the same persisted `package_id`, fingerprint, and payload.

The package replay key is:

```text
sha256(canonical_json({
  schema_version: "p24-package-replay.v1",
  action: "cross_task_auto_continue",
  continuation_id,
  source_completion_evidence_id,
  next_task_id
}))
```

The package and continuation root IDs are allocated and persisted in the same immediate transaction. If replay finds one package for this key, it revalidates and returns it. If current plan/config/workspace/confirmation facts no longer reproduce its semantic fingerprint, the package is stale or conflicting and execution stops; the service does not silently create another package.

Any semantic change, including path, model, skill, verification, confirmation, or source-evidence change, requires a new package ID and fingerprint. A package already bound to a continuation or Run is never silently replaced. If a newer package is legitimate, it creates a new explicit version with `supersedes_package_id`; it cannot reuse the original source-completion idempotency key unless the earlier continuation is terminally blocked before Task claim and an explicit human-authorized supersession record exists.

## 7. Append-Only Cross-Task Continuation Record

### 7.1 Logical root and event records

P24 uses one logical `continuation_id` per idempotency key and an append-only sequence of immutable state records. This satisfies both requirements: one valid progression identity and a durable history of later Run/reservation/invocation facts.

Root fields carried by every event:

```text
record_id
continuation_id
schema_version
action = cross_task_auto_continue
source_detail
created_at
sequence_no
previous_record_id

idempotency_key
source_task_id
source_run_id
source_completion_evidence_id
plan_version_id
task_creation_record_id
next_task_id: UUID | null
instruction_package_id: UUID | null

exact_run_id: UUID | null
worker_reservation_id: UUID | null
worker_invocation_claim_id: UUID | null
worker_outcome_id: UUID | null

new_task_created
run_created
worker_called

status
blocked_reasons
replay_of_record_id
product_runtime_git_write_allowed
```

Message metadata:

```text
source_detail = p24_cross_task_continuation_recorded
intent = cross_task_auto_continue
action type = p24_cross_task_continuation_record
schema_version = p24-d-continuation.v1
```

Allowed statuses:

```text
prepared
blocked
plan_queue_exhausted
next_task_reserved
next_task_run_created
worker_start_reserved
worker_invocation_claimed
worker_started
worker_returned
worker_failed
recovery_required
```

Field nullability and branch rules are normative:

| Field group | Always required | `next_task_resolved` / prepared branch | Worker stages | `plan_queue_exhausted` |
|---|---:|---:|---:|---:|
| `record_id`, `continuation_id`, replay key, source Task/Run/evidence, plan/creation lineage, status, Git boundary | Yes | Yes | Yes | Yes |
| `next_task_id`, `instruction_package_id` | No | Required before `prepared`/`next_task_reserved` is returned | Preserved unchanged | Must be null |
| `exact_run_id` | No | Null before Run creation, then required | Required | Must be null |
| `worker_reservation_id` | No | Null before reservation, then required | Required from reservation onward | Must be null |
| `worker_invocation_claim_id` | No | Null before claim | Required from claim onward | Must be null |
| `worker_outcome_id` | No | Null before outcome | Required only after durable outcome | Must be null |
| `new_task_created` | Yes | Always false because P24 reuses an existing Task | Always false | Must be false |
| `run_created` | Yes | False before Run, true only after exact Run commit | True | Must be false |
| `worker_called` | Yes | False before the external call boundary | True only when the call was attempted | Must be false |

No nullable next-task field may be populated on exhaustion, and no absent package/Run/outcome may be represented by a synthetic UUID.

`worker_started` means only that the external call boundary was crossed. It is not next-task completion. Completion of that next Task must later produce its own `ProjectDirectorSourceTaskCompletionEvidence`, which may trigger the following continuation.

Allowed state progression:

```text
prepared
  -> blocked
  -> plan_queue_exhausted
  -> next_task_reserved
       -> blocked
       -> next_task_run_created
            -> worker_start_reserved
                 -> worker_invocation_claimed
                      -> worker_started
                           -> worker_returned
                           -> worker_failed
                           -> recovery_required
```

`next_task_reserved` means the continuation/package owns authority for the exact next Task, but no Task status or Run has changed yet. `worker_started` is never written before the external call. It may be represented as an intermediate event only in the post-call outcome transaction when `worker_call_attempted=true`; after a crash with no outcome, the durable claim remains the sole indeterminate-side-effect marker and the state is reported as `recovery_required`.

### 7.2 Stable idempotency key

Canonical key payload:

```text
schema_version = p24-cross-task-idempotency.v1
action = cross_task_auto_continue
plan_version_id
source_task_id
source_success_run_id
source_completion_evidence_id
```

`idempotency_key = sha256(canonical_json(payload))`.

The same key must always replay:

```text
same continuation_id
same terminal record_id when plan_queue_exhausted
same next_task_id
same instruction_package_id
same exact_run_id, once created
same reservation/claim/outcome IDs, once created
no repeated Worker call
```

No in-memory lock is authoritative. All first-writer decisions occur under `BEGIN IMMEDIATE` with full-history validation. Multiple valid roots or divergent events for the same key are `continuation_replay_conflict` and require human recovery.

## 8. Exact Next Task Readiness and Dispatch

### 8.1 Layered eligibility

P24 must not overstate `TaskRouterService.evaluate_exact_task_for_dispatch()`. That method currently covers base readiness, dependency state, strategy, role scoring, selected model/skills, attempts, and budget-pressure scoring. P24 adds a wrapper gate for configuration and concurrency facts.

Evaluation order:

1. Reload and validate completion evidence, plan lineage, package, and exact next Task.
2. Require Task status `pending`, human status not requested/in-progress, and no pause reason.
3. Call `TaskReadinessService.evaluate_task(task=next_task)` and preserve structured dependency blockers.
4. Require no active Run for the exact next Task and no active AgentSession for that Task. P24 must add a repository query for active sessions because `get_by_run_id()` alone cannot prove task-wide absence.
5. Revalidate confirmed agent-team, skill, repository-binding, verification, real workspace, and any human-confirmation evidence against the package fingerprint.
6. Call only `TaskRouterService.evaluate_exact_task_for_dispatch(task=next_task)`.
7. Require candidate `ready=true`, readiness ready, strategy/model/role present, budget action not `block`, required selected skills confirmed, and risk/confirmation gates satisfied.
8. Re-run steps 1-7 inside the atomic Run-creation transaction before claiming the Task.

### 8.2 Block classification

| Condition | Class | Replay policy | Required action |
|---|---|---|---|
| Task already completed/failed/blocked or lineage changed | Permanent conflict | No automatic replay | Human investigation |
| Dependency incomplete | Temporary block | Safe to re-evaluate same root before any claim | Wait; do not skip Task |
| Budget blocked | Temporary policy block | Safe to re-evaluate before claim | Wait or human budget action |
| Missing Task, malformed lineage, duplicate record | Persistence/recovery | No automatic mutation | Human recovery |
| Missing/pending/rejected config | Governance block | Safe to re-evaluate before claim if root remains unclaimed | Confirm or correct config |
| Role/skill/repository/workspace mismatch | Governance/scope conflict | No blind retry | Human correction and new package if needed |
| Human confirmation required | Human block | Resume only with exact confirmation evidence | Human decision |
| Existing active Run/AgentSession | Concurrency conflict | Reconcile persisted owner first | Replay existing lineage or recover |
| Claim exists without outcome | Indeterminate side effect | Never recall Worker automatically | Human recovery |

The next Task is never skipped because it is blocked.

## 9. Service Boundaries

| Service | Input / output | Reads | Writes / transaction | Errors and replay |
|---|---|---|---|---|
| `ProjectDirectorSourceExecutionAuthorityResolver` | authority kind/record ID + exact source Task/Run -> unified immutable authority snapshot | P23 or P24 authority, reservation, claim, outcome, Task, Run | Read-only strict reconstruction; no mutation | Unsupported kind, broken lineage, schema/fingerprint mismatch, or Task/Run mismatch fails closed |
| `P23ProtectedTransitionExecutionAuthorityAdapter` | P23 authority lineage -> unified snapshot | Persisted P23 D1/B1/B2 messages plus Task/Run | Read-only | Preserves P23 wire IDs/replay; no P23 semantic change |
| `P24CrossTaskExecutionAuthorityAdapter` | P24 continuation/package/Run/invocation lineage -> unified snapshot | Persisted P24 records plus Task/Run | Read-only | P24 outcome must satisfy the same snapshot contract; malformed/incomplete lineage blocks |
| `ProjectDirectorSourceCompletionEvidenceResolver` | unified authority snapshot + immutable completion policy snapshot -> confirmed or blocked completion evidence | Task, Run, AgentSession, review, verification, deliverable, approval, plan lineage, authority/policy messages | One append-only evidence message under `BEGIN IMMEDIATE`; no Task/Run mutation | Full-history replay against original policy; missing/unresolved/mismatched policy or authority fails closed |
| `ProjectDirectorConfirmedPlanQueueResolver` | completion evidence -> plan/creation record/source index/exact next Task or exhausted | strict plan, raw creation record, all queue Tasks | Read-only; caller ends read transaction before external work | Deterministic and replayable; malformed/ambiguous lineage blocks |
| `ProjectDirectorNextTaskInstructionPackageBuilder` | resolved queue + confirmed configs + exact strategy -> immutable package | plan, Task, configs, RepositoryWorkspace, confirmation evidence | One package message under `BEGIN IMMEDIATE` | Same semantic input replays package; divergence blocks or requires explicit supersession |
| `ProjectDirectorCrossTaskContinuationRecordService` | idempotency key + state transition -> root/event record | full P24 history and bound messages | Append-only records under `BEGIN IMMEDIATE`; validates predecessor and monotonic sequence | Same state replays; forks/conflicts require recovery |
| `ExactTaskRunReservationService` (shared seam) | explicit target Task, immutable authority package, routing snapshot -> claimed Task + exact running Run | Task/readiness, Run, AgentSession, budget/strategy, authority record | CAS Task claim + `add_running_run_no_event()` + continuation event in one transaction; events published only after commit | Replay returns exact Run; no global routing |
| `ExactWorkerInvocationService` (shared seam) | explicit Task/Run + reservation + authority identity -> claim/outcome | Task, Run, AgentSession, reservation, authority | Claim transaction; Worker call outside write transaction; outcome transaction | Claim without outcome is recovery-required; outcome replays |
| `ProjectDirectorCrossTaskAutoContinueCoordinator` | source completion evidence ID -> unified P24 result | Calls services only | No direct table writes; no long transaction across services or Worker | Resumes at last durable step; never invents missing state |

The coordinator must not directly operate database tables, call `route_next_task()`, create Tasks, mutate a confirmed plan, invoke Worker without a reservation/claim, or bypass package/config validation.

## 10. Transaction and Event Contract

### 10.1 Normal sequence

```mermaid
sequenceDiagram
    participant C as P24 Coordinator
    participant E as Completion Evidence Resolver
    participant Q as Plan Queue Resolver
    participant P as Package/Continuation Service
    participant D as Exact Dispatch Service
    participant W as Exact Worker Invocation Service
    participant TW as TaskWorker

    C->>E: resolve(authority kind/record, source Task, exact source Run, policy ID/version)
    E->>E: reconstruct generic P23/P24 authority and frozen policy
    E->>E: BEGIN IMMEDIATE; revalidate; append evidence; COMMIT
    E-->>C: completion_evidence_id
    C->>Q: resolve exact next Task
    Q-->>C: next Task or plan_queue_exhausted
    alt plan_queue_exhausted
        C->>P: record terminal exhaustion
        P->>P: BEGIN IMMEDIATE; revalidate evidence/plan/replay; append one exhausted root/event; COMMIT
        P-->>C: same continuation_id, record_id, exhausted result
    else exact next Task resolved
        C->>P: prepare package and continuation root
        P->>P: BEGIN IMMEDIATE; scan replay; append package/root; COMMIT
        P-->>C: package_id, continuation_id
        C->>D: reserve exact next Task
        D->>D: BEGIN IMMEDIATE; revalidate; CAS claim; create exact Run; append event; COMMIT
        D-->>C: exact_run_id
        Note over D,C: publish Task/Run events only after commit
        C->>W: prepare Worker reservation
        W->>W: BEGIN IMMEDIATE; revalidate; append reservation; COMMIT
        C->>W: invoke exact reservation
        W->>W: BEGIN IMMEDIATE; append unique claim; COMMIT
        W->>TW: run_reserved_once(next_task_id, exact_run_id)
        Note over W,TW: no P24 write transaction held across call
        TW-->>W: Worker result or exception
        W->>W: BEGIN IMMEDIATE; revalidate; append outcome; COMMIT
        W-->>C: durable outcome or recovery_required
    end
```

`ProjectDirectorMessageRepository.create()` only flushes. The enclosing immediate transaction owns commit/rollback. Task and Run console events must follow the P23-D1 pattern: publish only after the transaction commits. No event may announce a Run, reservation, claim, or outcome that rolled back.

### 10.2 Atomic exact Run creation

Inside one `BEGIN IMMEDIATE` transaction:

```text
scan/replay continuation root and events
revalidate completion evidence and package fingerprint
revalidate exact next Task identity, pending state, dependencies, configs, budget, strategy
assert no active Run or AgentSession for exact next Task
TaskRepository.claim_pending_task(next_task_id)  # compare-and-set pending -> running
RunRepository.add_running_run_no_event(task_id=next_task_id, exact routing snapshot)
append next_task_run_created continuation event binding exact run_id
COMMIT
publish Task claimed and Run created events
```

If any step fails, the transaction rolls back Task claim, Run creation, and the event together. A replay after commit returns the exact persisted Run and does not call `claim_pending_task()` again.

## 11. Replay, Concurrency, and Crash Recovery

### 11.1 Required phase model

```text
Phase A1: generic authority/policy validation and completion evidence persistence
Phase A2: queue revalidation plus either package/root persistence or one terminal exhausted root/event
Phase B: exact Task claim + exact Run + continuation event (atomic)
Phase C: Worker start reservation persistence
Phase D: invocation claim persistence (commit-before-call)
Phase E: external TaskWorker.run_reserved_once call
Phase F: invocation outcome persistence (outcome-after-return)
```

### 11.2 Recovery sequence

```mermaid
sequenceDiagram
    participant R as Replay Caller
    participant S as P24 Persistence
    participant W as Worker Boundary

    R->>S: load by stable idempotency key
    alt terminal exhausted root/event exists
        S-->>R: replay same continuation_id, record_id, and exhausted result
    else completion evidence exists, final queue Task, no root
        S-->>R: revalidate under BEGIN IMMEDIATE; append one exhausted root/event
    else no root/claim exists and a next Task exists
        S-->>R: continue from last committed phase
    else root and exact Run exist, no reservation
        S-->>R: reuse exact Run; create reservation
    else reservation exists, no invocation claim
        S-->>R: reuse reservation; claim invocation
    else invocation claim exists, no outcome
        S-->>R: recovery_required; do not call Worker
    else complete outcome exists
        S-->>R: replay original IDs and result
    else conflicting or malformed history
        S-->>R: recovery_required; human reconciliation
    end
```

### 11.3 Crash matrix

| Crash/duplicate point | Persisted fact | Automatic behavior |
|---|---|---|
| Duplicate call before any root | No root | One caller creates root under immediate lock; other replays it |
| Crash after completion evidence commit, before exhaustion root | Completion evidence only | Revalidate evidence/plan under a later immediate transaction; append one exhausted root/event |
| Concurrent final-Task exhaustion calls | Serialized evidence/plan/history scan | One terminal exhausted root/event; all callers replay the same `continuation_id` and `record_id` |
| Concurrent calls during root/package creation | Serialized history scan | One package/root; all callers receive same IDs |
| Crash after package/root commit | Package and `prepared` root exist | Resume exact readiness; no duplicate package |
| Crash during Task claim/Run creation before commit | Nothing from transaction is durable | Safe to repeat Phase B |
| Crash after exact Run commit, before Worker reservation | Task running, exact Run and event durable | Reuse exact Run; create reservation; never create another Run |
| Crash after reservation commit, before claim | Reservation durable | Safe to create one claim |
| Concurrent invocation attempts | Immediate claim transaction | One claim commits; other sees claim and stops |
| Crash after claim, before Worker call | Claim, no outcome | `recovery_required`; no blind call because call boundary is indeterminate |
| Crash after Worker starts/returns, before outcome commit | Claim, no outcome | `recovery_required`; no blind re-call; reconcile Task/Run/AgentSession/runtime evidence manually or with an explicit recovery protocol |
| Worker raises | Claim plus persisted raised outcome when Phase F succeeds | Return `worker_failed`/`recovery_required`; no auto-recall |
| Crash after complete outcome commit | Full lineage | Replay same outcome and all IDs |
| Outcome persistence fails | Claim remains without outcome | `recovery_required`; never convert memory return into success |

The at-most-once guarantee is an invocation-authority guarantee: a durable claim is consumed before the external call. It deliberately favors fail-closed recovery over automatic retries after an indeterminate side effect.

## 12. State Decision Table

| Input state | Required durable evidence | Continue? | Result | Create Run? | Call Worker? | Human? |
|---|---|---:|---|---:|---:|---:|
| Worker merely started/returned | P23/P24 outcome lacks completion evidence | No | `source_completion_evidence_missing` | No | No | Maybe |
| Task completed but Run missing/mismatched | No exact success binding | No | `source_completion_evidence_invalid` | No | No | Yes |
| Task completed, exact Run succeeded, quality gate passed, approval policy unresolved | Partial success only | No | `source_completion_policy_unresolved` | No | No | Yes |
| Exact success plus pending approval | Exact approval `pending_approval` | No | `human_intervention_required` | No | No | Yes |
| Exact success plus recovery flag | P23/P24 authority has `recovery_required=true` or claim without outcome | No | `recovery_required` | No | No | Yes |
| Valid completion, malformed/mismatched lineage | Completion evidence plus invalid plan facts | No | `plan_lineage_invalid` | No | No | Yes |
| Valid completion, source absent from queue | Strict creation record | No | `source_task_not_in_plan_queue` | No | No | Yes |
| Valid completion, source is final queue Task | Strict queue with no next index | No | `plan_queue_exhausted` | No | No | No |
| Next ID declared but Task missing | Strict queue and missing row | No | `next_task_missing` | No | No | Yes |
| Exact next Task dependency incomplete | Readiness dependency snapshot | No | `next_task_dependency_blocked` | No | No | Not initially |
| Exact next Task budget blocked | Budget snapshot | No | `next_task_budget_blocked` | No | No | Maybe |
| Exact next Task needs confirmation | Confirmation policy, no matching evidence | No | `human_intervention_required` | No | No | Yes |
| Exact next Task already running/has active Run | Current Task/Run/session rows | No | `next_task_state_conflict` | No | No | Yes/reconcile |
| Exact next Task fully ready, no prior Run event | Valid package and all gates | Yes | `next_task_run_created` | Once | Not yet | No |
| Exact Run and reservation, no claim | Valid durable lineage | Yes | `worker_invocation_claimed` | No | Once after claim | No |
| Claim exists, no outcome | Claim only | No | `recovery_required` | No | No | Yes |
| Complete outcome exists | Exact claim/outcome | Replay | Existing result | No | No | As recorded |

## 13. Invariants

| Invariant | Enforcement |
|---|---|
| Never duplicate business Tasks | Resolve only IDs in creation record; creation services are forbidden |
| Never reorder/skip confirmed plan Tasks | `next_index = source_index + 1`; blocked next Task stops chain |
| Never select unrelated global Task | `route_next_task()` forbidden; exact evaluator only |
| Never treat Worker start as Task completion | Require immutable completion evidence derived from persisted terminal facts |
| Never duplicate Run | Atomic CAS claim + Run + event; replay returns bound `exact_run_id` |
| Worker invoked at most once per reservation | Commit unique claim before call; claim without outcome requires recovery |
| Never hold DB write lock across Worker/provider call | Three-phase claim/call/outcome boundary |
| Never publish rolled-back state | Task/Run and continuation events publish after commit only |
| Never reuse source review scope as next Task scope | Build package from exact plan/config/workspace sources |
| Never silently mutate used package | New semantic payload requires new package ID/fingerprint |
| Product runtime Git write remains forbidden | Fixed false field plus forbidden-action validation at every layer |
| Missing or ambiguous evidence fails closed | No fallback to memory return, heuristic Task selection, or synthetic records |

## 14. Plan Queue Exhaustion

When the source Task is the last ID in the strict ordered queue, append/replay one terminal continuation event:

```text
status = plan_queue_exhausted
next_task_id = null
instruction_package_id = null
exact_run_id = null
worker_reservation_id = null
worker_invocation_claim_id = null
worker_outcome_id = null
new_task_created = false
run_created = false
worker_called = false
product_runtime_git_write_allowed = false
```

No instruction package for a nonexistent next Task is required. The event still binds completion evidence, plan, creation record, source Task/Run, and queue length for audit.

The completion evidence is committed first in its own issuance transaction. After that commit, the coordinator opens a subsequent `BEGIN IMMEDIATE`, reloads the exact evidence and its frozen authority/policy fingerprints, revalidates confirmed plan lineage and the final queue index, scans the complete continuation history by the stable idempotency key, and appends exactly one terminal exhausted root/event if none exists. Completion evidence and exhaustion are therefore not falsely described as one atomic write, while the exhaustion first-writer decision is atomic.

Replay with the same idempotency key must return the same `continuation_id`, terminal `record_id`, and `plan_queue_exhausted` result. It must not build a package, allocate next-task/Run/Worker identities, or append a second exhausted record. A duplicate, divergent, malformed, or fingerprint-mismatched exhausted history returns `continuation_replay_conflict` and requires recovery.

Possible later actions include project-level acceptance, final summary, human confirmation, or phase closure. P24 does not start any of them automatically.

## 15. P23 Reuse and Compatibility Boundary

### 15.1 Reusable lower-level seams

P24 may extract target-agnostic primitives from:

```text
P23-D1 atomic exact Task claim and exact Run creation
P23-D2-B1 Worker start reservation validation
P23-D2-B2 claim-before-call and durable outcome pattern
TaskWorker.run_reserved_once(exact task_id, exact run_id)
post-commit Task/Run event publication
full-history replay and canonical fingerprint helpers
```

Recommended extraction:

```text
ExactTaskRunReservationService
ExactWorkerStartReservationService
ExactWorkerInvocationService
CanonicalAuditFingerprint helper
```

Each generic primitive receives an immutable authority envelope containing target Task, exact Run where applicable, authority kind (`p23_protected_transition` or `p24_cross_task_continuation`), authority record/package ID, fingerprint, and fixed Git boundary. Thin P23 adapters map existing P23 models without changing their wire payloads or replay keys. P24 adapters use P24 models.

### 15.2 Forbidden compatibility changes

P24 must not:

```text
change P23 target_task_id away from source_task_id
change P23 target_task_strategy/source_task_only semantics
reuse a P23 message ID as a P24 continuation/package ID
change P23 replay identities or fingerprints
allow P23 to route another pending Task
weaken P23 same-source concurrency protection
weaken P23 Worker at-most-once behavior
reinterpret P23 continuation_started as completion
```

P23 regression anchors remain:

```text
source_task_only = true
target_task_id = source_task_id
run_reserved_once receives P23 source Task and P23 exact Run
same P23 replay input returns same P23 records
claim without outcome remains recovery_required
```

## 16. Blocked Reason Taxonomy

### Completion

```text
source_completion_evidence_missing
source_completion_evidence_invalid
source_completion_evidence_conflict
source_execution_authority_missing
source_execution_authority_kind_unsupported
source_execution_authority_task_run_mismatch
source_execution_authority_schema_mismatch
source_execution_authority_fingerprint_mismatch
source_completion_policy_unresolved
source_completion_policy_missing
source_completion_policy_identity_mismatch
source_completion_policy_fingerprint_mismatch
source_review_policy_unresolved
source_verification_policy_unresolved
source_delivery_policy_unresolved
source_approval_policy_unresolved
source_task_not_completed
source_run_not_succeeded
source_quality_gate_not_passed
source_verification_evidence_missing
source_delivery_incomplete
source_approval_pending
source_agent_session_not_terminal
source_recovery_required
source_git_boundary_violation
```

### Lineage and queue

```text
plan_lineage_invalid
plan_version_missing
plan_version_not_confirmed
plan_creation_record_missing
plan_creation_record_conflict
plan_task_ids_invalid
source_task_not_in_plan_queue
next_task_missing
next_task_scope_mismatch
plan_queue_exhausted
```

### Package and readiness

```text
confirmed_scope_missing
allowed_paths_missing
repository_binding_not_confirmed
workspace_binding_missing
workspace_binding_mismatch
verification_config_not_confirmed
agent_role_not_confirmed
skill_binding_not_confirmed
instruction_package_conflict
next_task_not_ready
next_task_state_conflict
next_task_dependency_blocked
next_task_budget_blocked
active_run_conflict
active_agent_session_conflict
human_intervention_required
```

### Dispatch and recovery

```text
continuation_replay_conflict
task_claim_conflict
run_creation_failed
run_binding_invalid
worker_start_reservation_conflict
worker_invocation_claim_conflict
worker_invocation_in_progress_or_recovery_required
worker_outcome_persistence_failed_recovery_required
worker_execution_side_effects_indeterminate
```

Blocked responses include stable codes and safe summaries, never raw prompt, environment, command, stdout/stderr, token, secret, or API key data.

## 17. Planned Verification Matrix (Not Executed in P24-A)

Mimo must later cover at least:

```text
P23 protected-transition outcome -> generic authority snapshot -> completion evidence
P24 cross-task outcome -> generic authority snapshot -> completion evidence
Task 1 -> Task 2 -> Task 3 -> plan_queue_exhausted multi-hop simulation
authority kind/record with Task mismatch or Run mismatch
authority schema mismatch and authority fingerprint mismatch
completion policy identity mismatch and completion policy fingerprint change
review required with passing review / not_required with null review / unresolved fail closed
verification required with passing evidence / not_required with no evidence / unresolved fail closed
delivery required with exact deliverable version / not_required with no deliverable / unresolved fail closed
approval required with approved exact version / not_required with no approval / unresolved fail closed
policy replay uses original immutable snapshot after mutable config changes
Task completed but Run mismatched
quality gate false/null
pending/rejected/changes-requested approval
missing explicit approval policy
P23 continuation_started without completion
strict pdv parsing and every lineage mismatch
malformed task_ids_json (including silently-droppable UUID)
duplicate task_ids and task_count mismatch
source middle/last/not-in-queue
exhausted has null next_task_id/instruction_package_id/exact_run_id/reservation/claim/outcome IDs
exhausted has false new_task_created/run_created/worker_called flags
same exhausted key replays same continuation_id/record_id/result without a second record
next Task missing, blocked, dependency blocked, budget blocked
confirmed vs pending role/skill/repository/verification configs
allowed path escape and source-review-scope leakage rejection
exact evaluator called and route_next_task never called
same-input replay returns same package/Run/outcome IDs
two-thread continuation and invocation races
crash at every phase in the crash matrix
claim-without-outcome never recalls Worker
post-commit event ordering
P23 source-task-only and replay regression
product_runtime_git_write_allowed remains false
```

These are planned tests only. P24-A runs no pytest, runtime, Worker, provider, native executor, or CI.

## 18. Production Stage Split

The delivery order is production code first, then Mimo writes and runs the unified tests.

### P24-B: Source completion evidence and domain contracts

**Goal:** Add generic P23/P24 execution-authority reconstruction, immutable Task completion-policy proposal/decision/snapshot contracts, immutable completion evidence, and strict replay/conflict handling.

**Expected files:**

```text
runtime/orchestrator/app/domain/project_director_source_execution_authority.py
runtime/orchestrator/app/domain/project_director_task_completion_policy.py
runtime/orchestrator/app/domain/project_director_source_task_completion_evidence.py
runtime/orchestrator/app/services/project_director_source_execution_authority_resolver.py
runtime/orchestrator/app/services/project_director_p23_execution_authority_adapter.py
runtime/orchestrator/app/services/project_director_p24_execution_authority_adapter.py (domain adapter interface/strict contract; real P24 outcome producer remains P24-E)
runtime/orchestrator/app/services/project_director_task_completion_policy_service.py
runtime/orchestrator/app/services/project_director_source_completion_evidence_service.py
runtime/orchestrator/app/repositories/project_director_message_repository.py (only if a bounded strict query helper is needed)
runtime/orchestrator/app/repositories/deliverable_repository.py (read-only exact Run helper if missing)
runtime/orchestrator/app/repositories/approval_repository.py (read-only exact version helper if missing)
runtime/orchestrator/app/repositories/agent_session_repository.py (read-only exact active-state helper if missing)
```

**Forbidden:** next-Task resolution, Task/Run creation, Worker call, API/frontend, tests, product runtime Git write.

**Transaction:** append-only policy proposal; owner decision plus confirmed policy snapshot in one immediate transaction; completion replay scan and append in a separate immediate transaction; no external side effect.

**Acceptance:** one P23 adapter and one P24 adapter interface produce the unified snapshot contract; a real confirmed policy path can issue an immutable evidence ID; partial authority/Task/Run, any unresolved axis, or authority/policy identity/fingerprint conflict fails closed; same exact authority/policy/source completion replays the same evidence.

**Dependency:** P23 durable outcome and existing Task/Run finalization. P24-B must not wait for P24-E to avoid P23-only coupling: it defines the P24 adapter/domain input now, while P24-E later produces the concrete P24 outcome.

### P24-C: Confirmed plan exact next-Task resolver

**Goal:** Strictly validate `pdv:` lineage and raw creation record, then resolve only `task_ids[index+1]` or exhaustion.

**Expected files:**

```text
runtime/orchestrator/app/domain/project_director_cross_task_plan_queue.py
runtime/orchestrator/app/repositories/project_director_task_creation_repository.py
runtime/orchestrator/app/services/project_director_confirmed_plan_queue_resolver.py
```

**Forbidden:** Task creation/reconstruction, router global selection, Run/Worker, API/frontend, tests.

**Transaction:** read-only strict snapshot; no mutation.

**Acceptance:** malformed JSON/UUID, mismatch, missing Task, ambiguity, final Task, and exact next Task have deterministic results; no skipping.

**Dependency:** P24-B completion evidence.

### P24-D: Instruction package and append-only continuation record

**Goal:** Build one immutable package from confirmed scope/config/workspace facts and create one logical continuation root/event stream.

**Expected files:**

```text
runtime/orchestrator/app/domain/project_director_next_task_instruction_package.py
runtime/orchestrator/app/domain/project_director_cross_task_continuation.py
runtime/orchestrator/app/services/project_director_next_task_instruction_package_service.py
runtime/orchestrator/app/services/project_director_cross_task_continuation_record_service.py
```

Bounded read-only helpers may be added to the existing plan/config/workspace repositories.

**Forbidden:** claim Task, create Run, call Worker, mutate configs/plan, API/frontend, tests.

**Transaction:** package/root replay scan and append under immediate transaction.

**Acceptance:** package covers every required field, paths are evidence-derived, Git flag is false, semantic mutation creates a new package, and same input replays the same IDs.

**Dependency:** P24-B and P24-C.

### P24-E: Exact next Task Run/reservation/Worker integration

**Goal:** Add exact P24 readiness wrapper, atomic Task claim/Run creation, P24 reservation, invocation claim/outcome, and coordinator wiring.

**Expected files:**

```text
runtime/orchestrator/app/services/exact_task_run_reservation_service.py
runtime/orchestrator/app/services/exact_worker_start_reservation_service.py
runtime/orchestrator/app/services/exact_worker_invocation_service.py
runtime/orchestrator/app/services/project_director_cross_task_dispatch_service.py
runtime/orchestrator/app/services/project_director_cross_task_auto_continue_service.py
runtime/orchestrator/app/repositories/agent_session_repository.py
runtime/orchestrator/app/services/project_director_protected_transition_* (thin compatibility adapters only if extraction requires them)
```

**Forbidden:** `route_next_task()`, Task creation, plan mutation, unreserved Worker call, API/frontend unless separately approved, tests, product runtime Git write.

**Transaction:** atomic exact claim/Run/event; separate reservation; claim-before-call; call outside transaction; outcome transaction; post-commit events.

**Acceptance:** exact next Task only, one Run, one reservation, one claim, at-most-once Worker call, same-input replay, and unchanged P23 source-task behavior. The durable P24 outcome must expose every field needed by `SourceExecutionAuthoritySnapshot`: authority/reservation/claim/outcome identities and fingerprints, exact Task/Run, outcome schema/status, contract-valid flag, recovery/blocked state, Git activity, and fixed false Git boundary, so the completed Task can authorize the following hop.

**Dependency:** P24-D package/root and all earlier stages.

### P24-F: Replay, concurrency, and recovery production hardening

**Goal:** Complete history scanners, conflict classification, recovery readback, event ordering, and safe operator-facing recovery results.

**Expected files:** bounded modifications to P24 services/domains/repositories from B-E; no broad refactor.

**Forbidden:** blind Worker retry after claim, memory locks as authority, raw secret/process output, API/frontend unless separately approved, tests, product runtime Git write.

**Transaction:** preserve the phase model; recovery reads cannot cross the external call boundary.

**Acceptance:** every crash-matrix row has a deterministic persisted result; malformed/forked history fails closed; no duplicate Task/Run/Worker activity.

**Dependency:** P24-E complete production chain.

### P24-G: Mimo unified tests, regression, defect repair, and ledger closeout

**Goal:** Mimo writes and runs the full P24 test matrix, exercises concurrency/recovery, verifies P23 regressions, repairs defects found by tests, and records evidence.

**Expected files:** P24-focused test files, minimal defect fixes, and the existing unified ledger only after evidence exists.

**Forbidden:** weakening assertions to force green, claiming CI/runtime proof not run, changing product runtime Git boundary, premature total-loop Pass.

**Transaction:** tests must verify real commit/replay/event boundaries with isolated data.

**Acceptance:** the section 17 matrix passes, including P23- and P24-origin evidence, three-Task multi-hop, every policy axis in required/not-required/unresolved states, authority/policy mismatch and fingerprint conflicts, exhausted null/false fields, and exhausted stable replay; required regressions pass; `git diff --check` passes; P23 remains source-task-only; P24 Gate is proposed to the independent AI Project Director, not self-closed.

**Dependency:** all production stages P24-B through P24-F complete.

## 19. P24-A Non-Goals and Permanent Safety Boundary

This design does not modify production code, schemas, migrations, APIs, frontend, or tests. It does not execute a Worker/provider/native executor, write a workspace, create a Task/Run, or change a plan.

Permanent runtime boundary:

```text
Automatic workspace patch/apply: forbidden
Product runtime git add: forbidden
Product runtime git commit: forbidden
Product runtime git push: forbidden
Automatic PR/merge: forbidden
Destructive branch/reset/stash/rebase/tag operations: forbidden
Global unrelated Task routing: forbidden
product_runtime_git_write_allowed = false
```

## 20. P24-A Gate Checklist

```text
[x] Current reliable completion signal assessed from code
[x] Existing signal judged insufficient and minimum new seam defined
[x] continuation_started explicitly rejected as completion
[x] Completion evidence accepts both P23 and P24 execution authority kinds
[x] Unified authority resolver/snapshot and strict P23/P24 adapters defined
[x] Task 1 -> Task 2 -> Task 3 multi-hop authority lineage defined
[x] Append-only policy proposal, owner decision, and immutable confirmed snapshot defined
[x] Review/verification/delivery/approval use required/not_required/unresolved and fail closed
[x] Evidence/package bind completion policy ID, version, fingerprint, and authority-neutral outcome identity
[x] Confirmed plan lineage and strict task_ids validation defined
[x] Exact next Task comes only from task_ids[index + 1]
[x] route_next_task() forbidden
[x] Existing Tasks reused; duplicate Task creation forbidden
[x] Immutable instruction package fields and sources defined
[x] Append-only continuation root/events defined
[x] Stable idempotency key and concurrency contract defined
[x] claim-before-call, commit-before-side-effect, outcome-after-return defined
[x] Crash/replay/recovery matrix defined
[x] plan_queue_exhausted null fields, false side-effect flags, separate transaction, and stable record replay defined
[x] Service and transaction boundaries defined
[x] P23 reusable seams and compatibility prohibitions defined
[x] P24-B generic authority/policy/evidence, P24-E outcome contract, and P24-G R1 matrix synchronized
[x] No unresolved core semantic placeholder remains
[x] product_runtime_git_write_allowed=false remains invariant
```

P24-A-R1 may be proposed for independent review after this document is committed. It must not self-declare P24-A-R1, P24, or the AI Project Director total loop Closed; the total loop remains `Partial` pending independent Gate review and later implementation/UAT evidence.
