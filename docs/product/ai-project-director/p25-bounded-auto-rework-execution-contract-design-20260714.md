# P25-A: Bounded AUTO_REWORK Execution Contract Design

## 1. Status and Decision

This document freezes the P25 bounded automatic rework contract from repository
facts at:

```text
origin/main = 362c19640c01493490544284f06981f54693f8a8
message     = test: finalize p24 corruption identity evidence
date        = 2026-07-14
```

Gate state remains:

```text
P24 Cross-Task AUTO_CONTINUE: Closed / Pass with verification note
P25-A contract design:        Pass (design-only self-assessment)
P25 overall:                  Partial
AI Project Director loop:     Partial
```

P24 is not reopened or reinterpreted by P25.

P25-A defines contracts and later production stages only. It does not execute a
rework, call a provider, modify a sandbox, create a Task/Run, or change
production code.

## 2. Scope and Non-Goals

P25 owns this exact source-Task rework loop:

```text
trusted P22 AUTO_REWORK summary
-> consumed P23 auto_rework dispatch authority
-> immutable rework instruction package
-> scope/workspace/repository/base/diff preflight
-> exact attempt reservation
-> durable invocation Claim
-> external bounded sandbox rework
-> durable invocation Outcome
-> new candidate manifest/diff
-> new readonly review
-> new P21-D disposition
-> new P22 summary
-> converge / new bounded attempt / human escalation
```

P25-A explicitly does not design or implement:

- an AUTO_CONTINUE change or cross-Task continuation;
- creation of a replacement business Task;
- mutation of the confirmed plan or original acceptance criteria;
- a frontend page or API endpoint;
- a schema migration;
- a real Codex, Claude Code, or provider call;
- a direct main-project file write;
- product-runtime `git add`, `commit`, `push`, PR, merge, branch deletion,
  `reset`, `checkout`, `switch`, `stash`, `rebase`, tag, or CI trigger;
- automatic patch application to the main repository;
- full UAT or a total-loop `Pass` claim.

## 3. Repository Fact Review

### 3.1 Current AUTO_REWORK support

| Layer | Existing fact | What it proves | What it does not prove |
|---|---|---|---|
| P22 Domain | `ProjectDirectorPostReviewAutomationResult` in `project_director_post_review_automation.py`; `_validate_automatic_success()` maps `AUTO_REWORK` to `bounded_automatic_rework` and `BOUNDED_REWORK_GUARDRAIL` | A reconstructed P22 summary can name the rework route and bind C1/C2/C3/E IDs | It permanently requires `rework_started=false` and cannot execute rework |
| P22 Service | `ProjectDirectorPostReviewAutomationService.orchestrate_post_review()` and `_orchestrate_automatic_path()` | D-B -> C1 -> C2 -> C3 -> E is replay-aware and persisted | It has no rework instruction, executor, candidate write, or review re-entry |
| P23 Intent Domain | `ProjectDirectorProtectedTransitionDispatchIntentResult` | Exact source Task, review/diff/scope/workspace fingerprints, attempt index, and route can be persisted | It has no findings payload, repository identity, base commit, or execution package |
| P23 Intent Service | `ProjectDirectorProtectedTransitionDispatchIntentService.prepare_protected_transition_dispatch_intent()` | Revalidates the exact P22 chain, creates a replay-protected intent, and counts contiguous rework indexes | Its `rework_attempt_limit=3` is a hard current contract, not proof that three real reworks are possible |
| P23 consumption | `ProjectDirectorProtectedTransitionDispatchConsumptionService._consume_protected_transition_dispatch_preflight()` | Exact source Task is claimed and one Run is reserved; `dispatch_intent_consumed=true` | The message says AUTO_REWORK execution has not started; no rework package exists |
| P23 invocation | `ProjectDirectorProtectedTransitionWorkerInvocationService.invoke_reserved_protected_transition_worker()` | Durable Claim -> external `TaskWorker.run_reserved_once()` -> durable Outcome, with call outside the DB transaction | It is a generic TaskWorker call. `rework_started=true` only means the shared execution seam ran; it does not prove bounded candidate edits or new diff/review |
| Programmer no-write | `ProjectDirectorProgrammerNoWriteExecutionService.build_execution_from_sources()` | Produces files/tests/preview handoff without writes | Its own `unknowns` state real file changes and review of a real diff remain absent |
| Candidate workspace write | `ProjectDirectorSandboxCandidateFileWriteService.confirm_candidate_files_write()` | Can write only confirmed candidate paths under a guarded sandbox workspace and roll back partial writes | It consumes caller-provided candidate content and the earlier P21 authority; it is not a P25 rework executor |
| Candidate diff | `ProjectDirectorSandboxCandidateDiffService.confirm_candidate_diff_generation()` | Can reconstruct a readonly in-memory unified diff from guarded candidate files | It currently compares against live target files and accepts only the P21 candidate-write lineage; P25 needs an exact base-bound adapter |
| Readonly reviewer | `ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService.execute_candidate_diff_readonly_review_from_preflight_with_transport_resolver_factory()` | Revalidates diff, prompt, workspace, scope, invokes a readonly reviewer, and persists strict output | No P25 service currently creates a fresh preflight from a rework diff or invokes this method automatically |

### 3.2 Exact stopping point

The trustworthy bounded-rework chain stops at the consumed P23 AUTO_REWORK
dispatch authority:

```text
P23 consumption_status = reserved_for_worker_start
dispatch_intent_consumed = true
source Task claimed = true
one exact Run created = true
rework instruction package = absent
bounded sandbox write = absent
new candidate diff = absent
new readonly review = absent
```

The existing generic P23 Worker invocation must not be treated as the missing
P25 implementation. It forwards the existing Task/Run to
`TaskWorker.run_reserved_once()` and records whether the shared execution seam
was used. It does not bind blocking findings, required corrections, allowed
candidate paths, base commit, or a new candidate-diff identity.

P25 must make the P23 AUTO_REWORK consumption an exclusive input to the P25
reservation path. The same consumption must not also be consumed by the generic
P23 Worker invocation path. AUTO_CONTINUE behavior remains unchanged.

### 3.3 Trusted execution authority

The only execution authority accepted by P25 is one exact persisted P23
dispatch consumption record that reconstructs successfully and satisfies all
of:

```text
consumption_status = reserved_for_worker_start
dispatch_intent_consumed = true
disposition_type = AUTO_REWORK
dispatch_kind = auto_rework
target_task_strategy = source_task_rework
target_task_id = source_task_id
source P23 intent is prepared and unique
source P22 summary is ready_for_future_transition
route = bounded_automatic_rework
transition_kind = BOUNDED_REWORK_GUARDRAIL
transition_authority = AUTOMATED_DISPOSITION
freshness and review lineage revalidate
workspace_path_within_root = true
product_runtime_git_write_allowed = false
```

The P22 summary, P23 intent, and P23 consumption form the authority lineage.
The review findings instruct the work but do not independently authorize an
external call.

### 3.4 Inputs that are evidence or hints, not authority

P25 must not trust any client-repeated value for:

- review verdict, findings, recommended actions, or summary;
- allowed/forbidden paths or acceptance criteria;
- repository root, workspace path, base commit, or source diff;
- model, skills, role, attempt index, or attempt limit;
- a claim that the previous attempt converged;
- any `rework_started` boolean from a generic P23 outcome;
- no-write patch previews or free-form `recommended_next_step` text;
- executor self-reported Git safety without independent result validation.

The client may provide only locator IDs:

```text
session_id
source_task_id
source_p23_dispatch_consumption_message_id
```

Every semantic field is reconstructed from persisted records and current
read-only repository/workspace evidence.

### 3.5 Findings, corrections, and scope facts

The persisted P21-C readonly-review action already contains:

```text
verdict
risk_level
summary
findings[]:
  severity
  title
  summary
  evidence_paths[]
  recommended_action
recommended_next_step
review_scope_paths[]
source_diff_sha256
```

`ProjectDirectorProtectedTransitionDispatchIntentService._review_semantic_fingerprint()`
reconstructs `ProjectDirectorSandboxCandidateDiffValidatedReviewOutput`, sorts
the findings canonically, and fingerprints these semantics. Therefore P25 has
reliable structured findings and per-finding recommended actions.

There is no independently persisted `recommended_changes[]` contract. P25 must
derive `required_corrections[]` only from validated blocking findings
(`medium`/`high` for a `changes_required` verdict) and each finding's
`recommended_action`. Free-form `recommended_next_step` remains context, not an
executable instruction.

`review_scope_paths` is reliable as reviewed scope evidence because P23
revalidates it across the review, disposition, consumption, handoff, and
freshness records. It is not sufficient alone as write authority. Effective
write scope is the intersection of:

```text
confirmed Task/plan allowed paths
repository binding allowed paths
workspace operation manifest allowed paths
review_scope_paths
```

An empty intersection or any finding path outside the intersection is
`scope_invalid`.

### 3.6 Best execution seam

The safest existing seam is the guarded sandbox candidate-write/diff boundary,
not direct main-repository mutation and not generic TaskWorker execution.

P25 should introduce a P25-specific external executor protocol after immutable
package preparation and Claim commit. The executor receives a workspace-bound,
path-bounded instruction projection. It may modify only candidate files under
that workspace. After return, P25 independently enumerates and hashes the
workspace, then reuses the containment and diff principles from:

```text
ProjectDirectorSandboxCandidateFileWriteService
ProjectDirectorSandboxCandidateDiffService
ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService
```

The P21 source-message contracts must not be forged or silently reused. P25-G
adds an explicit P25 outcome adapter or a P25-specific diff preparation service.

### 3.7 Diff regeneration and reviewer re-entry today

Current code can generate a candidate diff and execute a readonly review when
given the earlier P21 lineage. It cannot yet:

- accept a P25 rework Outcome as candidate-write authority;
- bind comparison content to the package's exact base commit rather than the
  mutable live repository;
- persist old-diff -> attempt -> new-diff lineage;
- automatically create a fresh review preflight after rework;
- automatically run P21-D and P22 again from that fresh review.

Therefore both capabilities exist as reusable lower-level seams but are not
currently wired into AUTO_REWORK.

### 3.8 P23/P24 patterns that P25 may reuse

P25 may reuse the pattern, not the identity, of:

- full append-only history scans with fail-closed corrupt-history handling;
- canonical semantic fingerprints and stable replay keys;
- `BEGIN IMMEDIATE` reservation/Claim transactions;
- commit Claim before any external call;
- no DB write transaction across Worker/provider/executor calls;
- a separate `BEGIN IMMEDIATE` Outcome transaction;
- Claim-without-Outcome as `recovery_required`, never an automatic recall;
- exact Task/Run and authority-envelope binding;
- post-commit publication only;
- safe error summaries without prompt, stdout/stderr, command, env, token,
  secret, or API key leakage.

P25 must create new P25 IDs, schema versions, fingerprints, replay keys, and
messages. P24 continuation records/packages/claims/outcomes must never be used
as AUTO_REWORK authority because P24 targets the exact next Task, while P25
must target the exact source Task. P24 completion evidence, next-Task package,
continuation root, Run reservation, Claim, and Outcome identities are all
incompatible.

## 4. Frozen P25 Semantics

### 4.1 Exact target

```text
target_task_id = source_task_id
new business Task created = false
TaskRouterService.route_next_task() called = false
confirmed plan mutated = false
acceptance criteria expanded = false
cross-Task routing = false
```

P25 may use the exact Run already reserved by the consumed P23 authority. It
must not create another Run for the same attempt.

### 4.2 Authority lineage

Every package, reservation, Claim, Outcome, diff, review, and convergence
record binds:

```text
session_id
project_id
source_task_id
source_review_message_id
source_review_fingerprint
source_review_semantic_fingerprint
source_disposition_message_id
source_p22_summary_message_id
source_p23_dispatch_intent_id
source_p23_dispatch_intent_fingerprint
source_p23_dispatch_consumption_id
source_p23_dispatch_consumption_fingerprint
source_run_id
disposition_type = AUTO_REWORK
route = bounded_automatic_rework
transition_kind = BOUNDED_REWORK_GUARDRAIL
transition_authority = AUTOMATED_DISPOSITION
```

Any missing, malformed, duplicated, cross-session/project/Task, or mismatched
record fails closed before package creation.

## 5. ProjectDirectorBoundedReworkInstructionPackage

### 5.1 Domain contract

P25-B introduces:

```text
ProjectDirectorBoundedReworkInstructionPackage
schema_version = p25-b.v1
package_status = prepared | blocked
```

A prepared package contains at least:

```text
package_id
package_schema_version
package_fingerprint
package_replay_key
created_at

session_id
project_id
source_task_id
target_task_id = source_task_id
source_run_id

source_review_message_id
source_review_fingerprint
source_review_semantic_fingerprint
source_disposition_message_id
source_p22_summary_message_id
source_p23_dispatch_intent_id
source_p23_dispatch_intent_fingerprint
source_p23_dispatch_consumption_id
source_p23_dispatch_consumption_fingerprint

disposition_type = AUTO_REWORK
route = bounded_automatic_rework
transition_kind = BOUNDED_REWORK_GUARDRAIL
transition_authority = AUTOMATED_DISPOSITION
review_verdict = changes_required
review_risk_level
review_summary
blocking_findings[]
required_corrections[]
recommended_next_step_context

confirmed_acceptance_criteria[]
verification_requirements[]
allowed_scope_paths[]
forbidden_scope_paths[]

repository_binding_id
repository_root
repository_binding_fingerprint
workspace_binding_id
workspace_path
workspace_root
workspace_binding_fingerprint
base_commit_sha
base_snapshot_fingerprint
source_candidate_diff_message_id
source_candidate_diff_sha256
source_candidate_diff_fingerprint

selected_model
selected_skills[]
selected_role

rework_attempt_index
rework_attempt_limit
previous_attempt_id
previous_outcome_id
previous_candidate_diff_sha256
previous_review_semantic_fingerprint
non_convergence_evidence[]

product_runtime_git_write_allowed = false
main_project_write_allowed = false
automatic_pr_allowed = false
automatic_merge_allowed = false
```

### 5.2 Persisted sources versus computed fields

Persisted and revalidated fields:

- all authority-lineage IDs/fingerprints and the exact Run;
- review verdict/risk/summary/findings/recommended actions;
- Task/plan acceptance criteria and verification requirements;
- confirmed repository binding and workspace creation/manifest binding;
- P23 diff SHA, scope, attempt index, and limit;
- prior P25 package/reservation/Claim/Outcome/diff/review identities;
- selected role/model/skills from confirmed execution configuration.

Service-computed fields:

- canonical normalized allowed-path intersection and forbidden-path union;
- `required_corrections[]` from validated blocking findings;
- exact repository/workspace/base snapshot fingerprints;
- previous-attempt linkage and non-convergence evidence;
- package replay key and package fingerprint;
- safe redacted instruction projection sent to the executor.

No computed field may broaden a persisted scope or acceptance criterion.

### 5.3 Fingerprint and replay

The package fingerprint covers every semantic field except its random ID,
creation timestamp, and fingerprint itself. The replay key is:

```text
sha256(
  schema_version,
  source_p23_dispatch_consumption_id,
  source_p23_dispatch_consumption_fingerprint,
  source_review_semantic_fingerprint,
  source_candidate_diff_sha256,
  repository_binding_fingerprint,
  workspace_binding_fingerprint,
  base_commit_sha,
  rework_attempt_index
)
```

Same key + same payload returns the same package. Same key + different payload
is `instruction_package_conflict`. A P23 consumption may bind exactly one P25
package.

## 6. Repository, Workspace, Base, and Scope Preflight

Before attempt reservation, P25-C revalidates:

1. The repository binding is confirmed, belongs to the same project, and its
   canonical root matches the package.
2. The workspace is a strict child of the configured sandbox root, is not a
   symlink escape, and matches its creation/manifest evidence.
3. The exact read-only repository `HEAD` equals `base_commit_sha`; otherwise
   `base_commit_mismatch`. No fallback to current mutable content is allowed.
4. The source candidate diff reconstructs to the exact persisted SHA and its
   paths equal the reviewed scope; otherwise `source_diff_mismatch`.
5. Each allowed path is normalized, repository-relative, and present in every
   required allowed-scope source. Any absolute path, `..`, URI, shell fragment,
   internal manifest path, `.git` path, or unconfirmed create/update operation
   is rejected.
6. Each blocking finding has evidence within the effective scope. Missing or
   malformed corrections are `review_findings_invalid`.
7. The P23 AUTO_REWORK consumption has no P23 generic Worker Claim/Outcome and
   no prior different P25 reservation.

Repository binding is currently only partially represented by `repo_root` in
the reviewed candidate-diff records, and no reviewed P22/P23 model contains a
base commit. P25-C must resolve these from confirmed persisted repository facts
and persist a snapshot. If no exact confirmed source exists, preparation blocks
with `authority_invalid` or `base_commit_mismatch`; it must not infer identity
from a client path.

## 7. Attempt and Budget Contract

### 7.1 Decision

P25 retains a zero-based attempt index and an immutable limit of three:

```text
valid indexes = 0, 1, 2
rework_attempt_limit = 3
next index 3 = attempt_limit_exhausted
```

This is retained for current persistence compatibility, not merely because the
P23 design document proposed it:

- P23 production code persists contiguous AUTO_REWORK intent indexes in
  append-only messages and rejects gaps/duplicates;
- P23 Domain, intent, consumption/preflight, and reservation contracts hard
  validate limit `3`;
- SQLite message history can reconstruct and replay this bounded sequence
  without a migration;
- three is a strict maximum, while non-convergence rules below normally stop
  earlier;
- changing the limit in P25 alone would invalidate current downstream
  fingerprints and persisted-contract validation.

The P21-D handoff contract currently has
`MAX_AUTOMATIC_REWORK_HANDOFFS_PER_TASK = 1` and its Domain requires
`rework_attempt_number=1`, `rework_attempt_limit=1` for AUTO_REWORK. This is a
real compatibility conflict: a second fresh review cannot complete the current
handoff path if that counter is global per Task.

P25 freezes the meanings separately:

```text
P21-D handoff limit: exactly one handoff record per exact review/disposition lineage
P25/P23 attempt limit: at most three external rework attempts per source Task chain
```

P25-I must narrow the P21-D replay/count identity to the exact fresh review and
disposition, while still allowing only one handoff for that lineage. It must not
change P23 attempt indexes or allow duplicate handoffs for one review.

### 7.2 Four distinct concepts

| Concept | Counter/identity | Rule |
|---|---|---|
| Executor failure retry | `invocation_ordinal`, separate from attempt | Initial P25 has no automatic retry. A returned/raised/indeterminate call is terminal for that Claim. A future operator-authorized no-side-effect retry needs a new Claim and explicit recovery record; it does not silently reuse the call |
| Same-attempt crash resume | same package/attempt/reservation/Claim IDs | Read persisted state only. If Claim exists without Outcome, never call the executor again |
| New rework attempt | next `rework_attempt_index` | Requires successful prior Outcome, new diff, new readonly review, new P21-D disposition, new P22 summary, and newly consumed P23 authority |
| Review returns `changes_required` again | convergence decision event | It may authorize the next attempt only if diff/findings changed, limit remains, and every authority gate is fresh |

Task retry count, Worker/provider transport retry count, P21-D handoff ordinal,
P23/P25 rework attempt index, and Claim replay count must never share one field.

## 8. Reservation, Claim, External Call, and Outcome

### 8.1 Exact attempt reservation

P25-D creates one
`ProjectDirectorBoundedReworkAttemptReservation` in `BEGIN IMMEDIATE` after all
preflight checks. It binds package, P23 consumption, exact Task/Run, attempt,
workspace/base/diff, and an unguessable reservation token.

The transaction must atomically prove:

- no P23 generic invocation Claim exists for the consumption/Run;
- no different P25 reservation exists for the consumption/Run/attempt;
- the Task/Run still match the consumed authority;
- no recovery or human-escalation lock is active.

The committed reservation is the only authority to create a Claim. It does not
call an executor or write a candidate file.

### 8.2 Durable Claim

P25-E creates one append-only
`ProjectDirectorBoundedReworkInvocationClaim` under `BEGIN IMMEDIATE` and commits
before the external call. The Claim binds every reservation identity plus:

```text
claim_id
claim_fingerprint
claim_token
executor_adapter_kind
selected_model/skills/role
workspace_before_manifest_fingerprint
workspace_before_content_fingerprint
invocation_ordinal = 0
```

One reservation and exact Run may have at most one normal P25 Claim. A Claim
may authorize at most one executor call.

### 8.3 External execution boundary

After Claim commit:

```text
close/rollback read-only SQLAlchemy autobegin
-> revalidate immutable current workspace/base/scope facts
-> call bounded executor exactly once outside any DB write transaction
-> independently inspect workspace and executor result
```

The executor receives no database session, Git-write authority, main-repository
write path, arbitrary cwd, or raw secrets. It receives only the redacted package
projection and exact sandbox workspace.

### 8.4 Durable Outcome

P25-F writes one
`ProjectDirectorBoundedReworkInvocationOutcome` in a separate
`BEGIN IMMEDIATE`. It records:

```text
outcome_id/schema/fingerprint/status
source Claim/reservation/package/P23 authority
executor attempted/started/returned/raised
safe error code and redacted summary
workspace before/after manifest and content fingerprints
declared changed paths
independently observed changed paths
scope validation result
Git-activity detection result
candidate files changed
candidate manifest identity
recovery_required
human_escalation_required
product_runtime_git_write_allowed = false
```

Outcome persistence never repeats the executor call.

### 8.5 Claim without Outcome

If Claim is durable and Outcome is absent:

```text
status = recovery_required
automatic executor retry = forbidden
new attempt = forbidden
diff/reviewer re-entry = forbidden until reconciliation
human/operator inspection = required
```

Recovery may reconstruct workspace fingerprints and persist a reconciliation
record. It may not assert whether the executor ran from absence of an Outcome.

If Outcome persistence itself fails, the service returns only
`persistence_failed` plus `recovery_required`; it does not write a weaker
success marker and does not recall the executor.

## 9. Sandbox and Git Boundary

### 9.1 Candidate writes

Allowed writes are only regular candidate files satisfying all of:

```text
canonical path is a strict child of exact workspace
relative path is in package.allowed_scope_paths
operation create/update is confirmed in operation manifest
path is not internal manifest/config/control metadata
path is not a symlink or hard-link escape
aggregate file count/bytes stay within configured limits
```

The runtime, not the executor, writes or updates the internal candidate manifest.
Partial system-managed writes use the existing rollback principle from
`ProjectDirectorSandboxCandidateFileWriteService._rollback_written_candidate_files()`.
External execution cannot be assumed rollback-safe, so before/after hashes and
human recovery are mandatory when the result is indeterminate.

### 9.2 Git boundary

P25 permits controlled read-only repository identity/diff inspection. It
forbids every product-runtime Git write and delivery action.

The executor result contract contains explicit booleans for Git add, commit,
push, branch/checkout/switch, reset, stash, rebase, tag, PR, merge, and CI
activity. P25 also compares repository HEAD/status and control-directory hashes
before and after execution. Any positive report or independently observed
change is `git_boundary_violation`, invalidates the Outcome as successful, and
requires human escalation.

No rework Outcome authorizes applying the candidate to main.

## 10. Candidate Diff Regeneration

P25-G runs only after a valid returned Outcome with changed candidate files:

1. Reconstruct package, reservation, Claim, and Outcome.
2. Verify observed changed paths exactly match the persisted candidate manifest
   and are a subset of allowed scope.
3. Resolve each old file from the exact `base_commit_sha`/base snapshot, not
   from mutable live main.
4. Read new candidate files from the exact workspace.
5. Generate canonical in-memory unified diff with size/count limits.
6. Persist a new candidate-diff record with:

```text
source_attempt_id
source_outcome_id
source_package_id
previous_diff_message_id
previous_diff_sha256
new_diff_message_id
new_diff_sha256
base_commit_sha
diff_entries[]
scope_paths[]
workspace_after_manifest_fingerprint
```

An empty or byte-identical new diff is `non_convergence`; it is not a successful
rework. The old diff record is immutable and never overwritten.

## 11. Readonly Reviewer Re-entry

P25-H creates a fresh P21-C-compatible review preflight from the new diff,
using a new prompt fingerprint and the exact workspace-bound transport resolver
factory. It then calls the existing readonly review execution seam and persists
a new review message.

The lineage is:

```text
old review -> P22/P23 authority -> P25 attempt -> P25 Outcome
-> new candidate diff -> new review preflight -> new readonly review
-> new P21-D disposition -> new P22 summary
```

The old review cannot be replayed as the result of a new diff. The new review
must bind the new diff message/SHA, current scope, attempt ID, Outcome ID, and
base commit. Review execution remains readonly and cannot approve Git or main
project writes.

After the new review:

- no blocking findings -> `AUTO_CONTINUE` and P25 converges;
- changed blocking findings and budget remains -> new P21-D/P22/P23 authority
  may prepare the next P25 attempt;
- any non-convergence/escalation condition -> `ESCALATE_TO_HUMAN` package and
  no new attempt.

## 12. Non-Convergence and Escalation

| Condition | Primary state | Automatic next attempt | Required action |
|---|---|---:|---|
| Consecutive identical review semantic fingerprint | `non_convergence` | No | `ESCALATE_TO_HUMAN` |
| Same canonical blocking-findings set on consecutive attempts, even if summary text changes | `non_convergence` | No | `ESCALATE_TO_HUMAN` |
| Candidate diff SHA unchanged or empty after execution | `non_convergence` | No | `ESCALATE_TO_HUMAN` |
| Changed/created path outside effective scope | `scope_invalid` | No | Block, preserve workspace, human recovery/escalation |
| Attempt index reaches limit | `attempt_limit_exhausted` | No | Persist human-escalation requirement |
| Executor raises/returns invalid result once | `recovery_required` | No automatic retry | Reconcile side effects; operator decision |
| Executor failure repeats after an explicitly authorized no-side-effect recovery | `non_convergence` | No | `ESCALATE_TO_HUMAN` |
| Git activity detected | `git_boundary_violation` | No | Preserve evidence and `ESCALATE_TO_HUMAN` |
| Claim exists without Outcome | `claim_without_outcome` | No | Recovery only; never recall executor |
| New review/preflight cannot be persisted or invoked | `review_reentry_failed` | No | Recovery; escalate if not safely repairable |

No state loops indefinitely. `blocked` prevents automatic progress,
`recovery_required` prevents new side effects until reconciliation, and
`human escalation` is terminal for automatic P25 processing.

## 13. Blocked Reason Taxonomy

| Stable reason | Classification | Meaning |
|---|---|---|
| `history_invalid` | blocked + recovery | Corrupt, forked, missing, or non-contiguous P25/P23 history |
| `authority_invalid` | blocked | P22/P23 authority cannot be reconstructed or is not AUTO_REWORK |
| `authority_replayed` | blocked + recovery | One authority is bound to conflicting package/reservation/Claim records |
| `scope_invalid` | blocked; escalate after side effect | Effective scope missing, malformed, or violated |
| `workspace_invalid` | blocked + recovery | Workspace missing, escaped, changed, or bound to another lineage |
| `base_commit_mismatch` | blocked | Repository/base snapshot is not the package base |
| `source_diff_mismatch` | blocked | Source diff content, SHA, paths, or base does not reconstruct |
| `review_findings_invalid` | blocked | Findings/corrections are malformed or outside scope |
| `instruction_package_conflict` | blocked + recovery | Same replay key has a different semantic payload |
| `attempt_limit_exhausted` | human escalation | No further automatic rework budget remains |
| `non_convergence` | human escalation | Same diff/review/findings or repeated failure proves no progress |
| `claim_without_outcome` | recovery + human inspection | Executor may have run; at-most-once prevents recall |
| `execution_result_invalid` | recovery; escalate if side effects possible | Returned contract, workspace, or declared/observed changes disagree |
| `git_boundary_violation` | blocked + recovery + human escalation | Product-runtime Git or repository-control activity was detected |
| `persistence_failed` | recovery | Reservation/Claim/Outcome/diff/review durable write failed |
| `review_reentry_failed` | recovery; eventual human escalation | Fresh diff cannot complete fresh readonly review flow |
| `human_escalation_required` | human escalation | Aggregate terminal marker; no automatic transition allowed |

Blocked/recovery messages contain stable codes and redacted summaries only.

## 14. Production Stage Split

### P25-B: Authority and instruction package Domain

- **Goal:** Add immutable authority/package/attempt/Claim/Outcome Domain models
  and canonical fingerprint helpers.
- **Allowed scope:** New P25 Domain files; bounded imports only.
- **Input/output:** Frozen contracts -> validated Domain models.
- **Transaction:** None; pure validation/fingerprinting.
- **Forbidden:** Service wiring, executor call, file write, Task/Run/Git/API/frontend.
- **Targeted tests:** frozen/blocked round-trip, false flags, fingerprint mutation,
  exact source Task, invalid path/base/authority.
- **Gate:** Domain cannot represent a prepared package with incomplete lineage,
  write authority, non-source target, or invalid attempt.

### P25-C: Authority and package preparation Service

- **Goal:** Reconstruct persisted P22/P23/review/config/repository/workspace
  evidence and persist one package.
- **Allowed scope:** New P25 preparation service and bounded read-only repository
  helpers.
- **Input/output:** three locator IDs -> prepared package/message or blocked.
- **Transaction:** One `BEGIN IMMEDIATE` for history scan and package append;
  repository/workspace read preflight occurs before final append and is
  revalidated in transaction.
- **Forbidden:** Trust client findings/scope/diff; claim Run; call executor; write files.
- **Targeted tests:** authority lineage, package replay/conflict, base/workspace,
  scope intersection, findings derivation, sensitive-text redaction.
- **Gate:** Same authority replays one package; every mismatched evidence source
  fails closed.

### P25-D: Exact rework attempt reservation

- **Goal:** Exclusively reserve the consumed P23 AUTO_REWORK authority and exact
  Run for one P25 attempt.
- **Allowed scope:** New reservation Domain/service plus minimal P23 routing guard
  so AUTO_REWORK cannot also enter generic invocation.
- **Input/output:** package + P23 consumption -> durable reservation.
- **Transaction:** One atomic `BEGIN IMMEDIATE`; no external side effect.
- **Forbidden:** New Task/Run, router selection, Worker/executor call, candidate write.
- **Targeted tests:** duplicate/concurrent reservation, generic-P23-vs-P25 race,
  Task/Run mismatch, replay, attempt limit.
- **Gate:** Exactly one exclusive consumer and no second Run.

### P25-E: Invocation Claim

- **Goal:** Persist exact at-most-once executor authority.
- **Allowed scope:** New Claim service/model and bounded coordinator wiring.
- **Input/output:** current reservation -> committed Claim.
- **Transaction:** One `BEGIN IMMEDIATE`; commit before return.
- **Forbidden:** Executor/provider/Worker call inside transaction; Outcome creation;
  candidate or Git write.
- **Targeted tests:** concurrent Claim, one Claim per reservation/Run, Claim replay,
  corrupt history, pre-call workspace drift.
- **Gate:** A committed Claim is necessary and sufficient for at most one P25
  adapter call, but is not success evidence.

### P25-F: External rework execution and durable Outcome

- **Goal:** Call a gated fake/real adapter once outside DB transaction, validate
  sandbox effects, and persist one Outcome.
- **Allowed scope:** P25 executor protocol/adapter/coordinator and Outcome service.
- **Input/output:** committed Claim -> external result -> durable Outcome.
- **Transaction:** Claim already committed; call outside transaction; Outcome in
  independent `BEGIN IMMEDIATE`.
- **Forbidden:** Blind retry, main-repo write, Git write, raw command/output/secret
  persistence, new Task/Run.
- **Targeted tests:** returned/raised/invalid, Claim without Outcome, Outcome
  rollback, Git activity, scope escape, declared/observed path mismatch.
- **Gate:** Every call has one Claim and at most one Outcome; missing Outcome is
  recovery, never recall.

### P25-G: Candidate manifest and diff regeneration

- **Goal:** Persist new candidate manifest/diff bound to Outcome and exact base.
- **Allowed scope:** P25 adapter around guarded manifest/diff services; bounded
  compatibility extension to accept P25 Outcome lineage.
- **Input/output:** valid Outcome/workspace -> new immutable diff record.
- **Transaction:** Read files outside DB write transaction; append validated
  metadata in `BEGIN IMMEDIATE` after final revalidation.
- **Forbidden:** Compare against drifting live main, apply patch, write main, Git.
- **Targeted tests:** changed/unchanged diff, base mismatch, scope enforcement,
  path/symlink escape, size limits, replay/conflict.
- **Gate:** New diff SHA and lineage are reproducible; unchanged diff is
  non-convergence.

### P25-H: Readonly reviewer re-entry

- **Goal:** Create fresh preflight, execute readonly review, then run fresh
  disposition/P22 orchestration.
- **Allowed scope:** P25 review coordinator and bounded adapters to existing P21-C,
  P21-D, and P22 services.
- **Input/output:** new diff -> new review -> new disposition/P22 summary.
- **Transaction:** Persist preflight; reviewer call outside write transaction;
  review/disposition/P22 keep their existing independent transactions.
- **Forbidden:** Reuse old review, treat verdict as human approval, write files/Git.
- **Targeted tests:** new diff binding, reviewer call once, invalid output,
  disposition routing, old-review replay rejection, review persistence failure.
- **Gate:** Every new diff receives a new review identity and exact lineage.

### P25-I: Convergence, attempt budget, and escalation

- **Goal:** Decide converge/new attempt/escalate; reconcile P21-D per-review
  handoff ordinal with P23/P25 global attempt budget.
- **Allowed scope:** New convergence/escalation service and the smallest P21-D
  handoff compatibility change needed for fresh-review lineage.
- **Input/output:** prior/current diff and review histories -> terminal decision or
  next-attempt eligibility.
- **Transaction:** One immediate history decision append; human package uses its
  own existing/new append transaction.
- **Forbidden:** Reset attempt budget, duplicate one-review handoff, reopen P24,
  auto-retry Claim without Outcome.
- **Targeted tests:** repeated fingerprint/findings, unchanged diff, indexes 0/1/2,
  index 3 exhaustion, P21-D fresh-review handoff, human escalation.
- **Gate:** No infinite loop and no second attempt without fresh P22/P23 authority.

### P25-J: Dynamic concurrency, rollback, and end-to-end verification

- **Goal:** Verify races, crash matrix, rollback/recovery, redaction, and full
  bounded loop using isolated runtime data.
- **Allowed scope:** P25 tests, gated fake executor, minimal defects found by tests,
  and evidence ledger only after proof.
- **Input/output:** isolated SQLite/sessions/workspaces -> reproducible evidence.
- **Transaction:** Exercise all reservation/Claim/call/Outcome boundaries and
  concurrent contenders.
- **Forbidden:** Real provider, main write, product-runtime Git, frontend/API,
  weakening assertions, premature total-loop Pass.
- **Targeted tests:** Full section 15 matrix.
- **Gate:** Targeted suite proves at-most-once, containment, replay, re-entry,
  convergence, recovery, and unchanged P24/AUTO_CONTINUE regressions.

## 15. Future Verification Matrix

Future dynamic tests use temporary SQLite databases, independent Project
Director Sessions, isolated sandbox roots, and a gated fake executor. They cover:

```text
Domain prepared/blocked round-trip and frozen false flags
package/attempt/Claim/Outcome fingerprint mutation
exact authority lineage and cross-session/project/Task rejection
client findings/scope/diff ignored
effective allowed/forbidden scope enforcement
repository/workspace/base commit binding
source diff reconstruction and mismatch
one-attempt at-most-once
P23 generic invocation versus P25 exclusive reservation race
concurrent reservation
concurrent Claim
Claim without Outcome
same-attempt crash resume without executor recall
Outcome rollback/persistence failure
executor raised
executor invalid return
declared versus observed changed paths
Git activity report and independent repository-control detection
candidate diff changed
candidate diff empty/unchanged
new diff exact-base regeneration
fresh readonly review rerun
old review reuse rejection
fresh P21-D/P22/P23 lineage for next attempt
repeated review semantic fingerprint
repeated canonical findings set
attempt indexes 0, 1, 2 and limit exhaustion at 3
P21-D one handoff per fresh review lineage
human escalation terminal state
sensitive text/error redaction
full replay after process restart
corrupt/forked history fail closed
AUTO_CONTINUE regression unchanged
P24 regression unchanged
product_runtime_git_write_allowed remains false
```

## 16. Gate Checklist

```text
[x] Current AUTO_REWORK names and readonly evidence mapped to concrete code
[x] Trustworthy chain stopping point identified
[x] Trusted authority separated from findings/hints
[x] Exact source Task and no-new-Task semantics frozen
[x] Immutable package fields, sources, fingerprint, and replay key frozen
[x] Repository/workspace/base/diff/scope bindings frozen
[x] P21-D limit=1 versus P23 limit=3 conflict explicitly resolved by meaning
[x] Attempt, executor retry, crash resume, and fresh-review retry separated
[x] Claim-before-call and independent Outcome transaction frozen
[x] Claim without Outcome forbids automatic retry
[x] Sandbox candidate-only and product-runtime Git boundaries frozen
[x] New diff and new readonly-review lineage frozen
[x] Non-convergence and human escalation rules bounded
[x] Stable blocked taxonomy provided
[x] P25-B through P25-J split into independently gated stages
[x] Future isolated verification matrix defined
[x] P24 Gate unchanged
[x] P25 overall and AI Project Director total loop remain Partial
```

P25-A may be proposed for independent review after this document is committed.
This design self-assessment does not mark P25 production execution or the AI
Project Director total loop complete.
