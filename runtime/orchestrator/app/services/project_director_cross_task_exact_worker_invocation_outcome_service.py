"""Invoke one P24 exact Worker and durably record its E4 outcome."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.domain._base import utc_now
from app.domain.agent_session import AgentSession
from app.domain.project_director_cross_task_continuation import (
    ProjectDirectorCrossTaskContinuationRoot,
)
from app.domain.project_director_cross_task_exact_run_reservation import (
    ProjectDirectorCrossTaskExactRunReservation,
)
from app.domain.project_director_cross_task_exact_worker_invocation_claim import (
    ProjectDirectorCrossTaskExactWorkerInvocationClaim,
    ProjectDirectorCrossTaskExactWorkerInvocationClaimResult,
)
from app.domain.project_director_cross_task_exact_worker_invocation_outcome import (
    CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_ACTION_TYPE,
    CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_INTENT,
    CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_SCHEMA_VERSION,
    CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL,
    CrossTaskExactWorkerInvocationOutcomeBlockedReason,
    ProjectDirectorCrossTaskExactWorkerInvocationOutcome,
    ProjectDirectorCrossTaskExactWorkerInvocationOutcomeResult,
)
from app.domain.project_director_cross_task_exact_worker_start_reservation import (
    ProjectDirectorCrossTaskExactWorkerStartReservation,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_next_task_instruction_package import (
    ProjectDirectorNextTaskInstructionPackage,
    compute_p24_contract_sha256,
)
from app.domain.project_role import ProjectRoleCode
from app.domain.run import Run, RunStatus
from app.domain.task import Task, TaskHumanStatus, TaskStatus
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.project_director_cross_task_exact_worker_invocation_claim_service import (
    ProjectDirectorCrossTaskExactWorkerInvocationClaimService,
    _Blocked as _ClaimBlocked,
)
from app.workers.task_worker import TaskWorker, WorkerRunResult


_PAGE_SIZE = 200
_OUTCOME_CONTENT_PREFIX = "P24 exact Worker invocation outcome"
_PRE_CALL_FAILED = (
    "exact_worker_invocation_outcome_pre_call_revalidation_failed"
)
_CLAIM_WITHOUT_OUTCOME = (
    "exact_worker_invocation_outcome_claim_without_outcome_recovery_required"
)
_PERSISTENCE_FAILED = "exact_worker_invocation_outcome_persistence_failed"
_WORKER_RESULT_INVALID = "exact_worker_invocation_outcome_worker_result_invalid"
_WORKER_BINDING_CONFLICT = (
    "exact_worker_invocation_outcome_worker_result_binding_conflict"
)
_WORKER_RAISED = "exact_worker_invocation_outcome_worker_raised"
_GIT_BOUNDARY_VIOLATION = (
    "exact_worker_invocation_outcome_git_boundary_violation"
)

_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)[\"']?\b(?:api[ _-]?key|authorization|password|secret|token|prompt|"
    r"environment(?:[ _-]?variable)?|env|provider[ _-]?credential)\b[\"']?"
    r"\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^,;]*)"
)
_BEARER_VALUE = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{1,}")

# Keep this list local and read-only so new Worker fields cannot silently make
# one Git-capable result look contract-valid.
_GIT_ACTIVITY_FIELDS = (
    "workspace_context_runs_write_git",
    "runtime_launch_dry_run_runs_write_git",
    "runtime_launch_gate_runs_write_git",
    "worktree_safe_command_proof_runs_write_git",
    "git_diff_dry_run_runs_write_git",
    "git_diff_dry_run_git_add_triggered",
    "git_diff_dry_run_git_commit_triggered",
    "git_diff_dry_run_git_push_triggered",
    "git_diff_dry_run_pr_opened",
    "git_diff_dry_run_danger_commands_applied",
    "git_operation_dry_run_runs_write_git",
    "git_operation_dry_run_git_add_triggered",
    "git_operation_dry_run_git_commit_triggered",
    "git_operation_dry_run_git_push_triggered",
    "git_operation_dry_run_pr_opened",
    "git_operation_dry_run_operation_applied",
    "delivery_gate_evidence_runs_write_git",
    "delivery_gate_evidence_git_add_triggered",
    "delivery_gate_evidence_git_commit_triggered",
    "delivery_gate_evidence_git_push_triggered",
    "delivery_gate_evidence_pr_opened",
    "delivery_gate_evidence_operation_applied",
    "delivery_gate_evidence_gate_allows_write",
    "delivery_human_approval_runs_write_git",
    "delivery_human_approval_git_add_triggered",
    "delivery_human_approval_git_commit_triggered",
    "delivery_human_approval_git_push_triggered",
    "delivery_human_approval_pr_opened",
    "delivery_human_approval_operation_applied",
    "delivery_human_approval_gate_allows_write",
)
_GIT_ACTIVITY_SNAPSHOT_NAMES = (
    "runtime_lifecycle_snapshot",
    "external_executor_snapshot",
    "reserved_run_execution_snapshot",
    "delivery_snapshot",
    "approval_snapshot",
)
_GIT_ACTIVITY_SNAPSHOT_FIELDS = (
    "runs_write_git",
    "git_add_triggered",
    "git_commit_triggered",
    "git_push_triggered",
    "pr_opened",
    "operation_applied",
    "gate_allows_write",
    "product_runtime_git_write_allowed",
)


@dataclass(frozen=True)
class _History:
    packages: tuple[
        tuple[ProjectDirectorMessage, ProjectDirectorNextTaskInstructionPackage],
        ...,
    ]
    roots: tuple[
        tuple[ProjectDirectorMessage, ProjectDirectorCrossTaskContinuationRoot],
        ...,
    ]
    exact_run_reservations: tuple[
        tuple[ProjectDirectorMessage, ProjectDirectorCrossTaskExactRunReservation],
        ...,
    ]
    worker_start_reservations: tuple[
        tuple[
            ProjectDirectorMessage,
            ProjectDirectorCrossTaskExactWorkerStartReservation,
        ],
        ...,
    ]
    invocation_claims: tuple[
        tuple[
            ProjectDirectorMessage,
            ProjectDirectorCrossTaskExactWorkerInvocationClaim,
        ],
        ...,
    ]
    invocation_outcomes: tuple[
        tuple[
            ProjectDirectorMessage,
            ProjectDirectorCrossTaskExactWorkerInvocationOutcome,
        ],
        ...,
    ]


@dataclass(frozen=True)
class _ExactGraph:
    root: ProjectDirectorCrossTaskContinuationRoot
    package: ProjectDirectorNextTaskInstructionPackage
    exact_run_reservation: ProjectDirectorCrossTaskExactRunReservation
    worker_start_reservation: ProjectDirectorCrossTaskExactWorkerStartReservation
    claim: ProjectDirectorCrossTaskExactWorkerInvocationClaim


@dataclass(frozen=True)
class _AfterState:
    task: Task | None
    run: Run | None
    agent_session: AgentSession | None
    blocked_reasons: tuple[CrossTaskExactWorkerInvocationOutcomeBlockedReason, ...]


class _Blocked(Exception):
    def __init__(
        self,
        reason: CrossTaskExactWorkerInvocationOutcomeBlockedReason,
    ) -> None:
        self.reason = reason
        super().__init__(reason)


class ProjectDirectorCrossTaskExactWorkerInvocationOutcomeService:
    """Consume one durable E3 claim, call its exact Worker once, append E4."""

    def __init__(
        self,
        *,
        message_repository: ProjectDirectorMessageRepository,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        agent_session_repository: AgentSessionRepository,
        claim_service: ProjectDirectorCrossTaskExactWorkerInvocationClaimService,
        task_worker: TaskWorker,
    ) -> None:
        self._message_repository = message_repository
        self._task_repository = task_repository
        self._run_repository = run_repository
        self._agent_session_repository = agent_session_repository
        self._claim_service = claim_service
        self._task_worker = task_worker
        self._require_shared_session()

    def invoke_exact_worker(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        continuation_root_record_id: UUID,
        instruction_package_id: UUID,
        exact_run_reservation_id: UUID,
        exact_worker_start_reservation_id: UUID,
    ) -> ProjectDirectorCrossTaskExactWorkerInvocationOutcomeResult:
        """Invoke only a newly-created exact claim and durably record outcome."""

        try:
            self._require_shared_session()
        except (AttributeError, TypeError, ValueError):
            return self._blocked_result(
                reason="exact_worker_invocation_outcome_claim_invalid",
            )

        shared_session = self._message_repository._session
        if shared_session.in_transaction():
            return self._blocked_result(
                reason="exact_worker_invocation_outcome_claim_invalid",
            )

        try:
            claim_result = self._claim_service.claim_exact_worker_invocation(
                session_id=session_id,
                project_id=project_id,
                continuation_root_record_id=continuation_root_record_id,
                instruction_package_id=instruction_package_id,
                exact_run_reservation_id=exact_run_reservation_id,
                exact_worker_start_reservation_id=(
                    exact_worker_start_reservation_id
                ),
            )
        except Exception:
            return self._blocked_result(
                reason="exact_worker_invocation_outcome_persistence_failed",
            )
        try:
            claim_result = (
                ProjectDirectorCrossTaskExactWorkerInvocationClaimResult
                .model_validate(claim_result.model_dump(mode="python"))
            )
        except (AttributeError, TypeError, ValueError, ValidationError):
            return self._blocked_result(
                reason="exact_worker_invocation_outcome_claim_invalid",
            )

        if claim_result.status == "blocked":
            return self._blocked_result(
                reason=self._map_claim_reasons(claim_result.blocked_reasons),
            )
        claim = claim_result.claim
        if claim is None:
            return self._blocked_result(
                reason="exact_worker_invocation_outcome_claim_invalid",
            )

        if claim_result.status == "invocation_claim_replayed":
            return self._resolve_replayed_claim(
                claim=claim,
                session_id=session_id,
                project_id=project_id,
                continuation_root_record_id=continuation_root_record_id,
                instruction_package_id=instruction_package_id,
                exact_run_reservation_id=exact_run_reservation_id,
                exact_worker_start_reservation_id=(
                    exact_worker_start_reservation_id
                ),
            )
        if (
            claim_result.status != "invocation_claim_created"
            or not claim_result.automatic_worker_call_allowed
        ):
            return self._blocked_result(
                reason="exact_worker_invocation_outcome_claim_invalid",
                claim_id=claim.exact_worker_invocation_claim_id,
            )

        pre_call_blocked_reasons: tuple[
            CrossTaskExactWorkerInvocationOutcomeBlockedReason,
            ...,
        ] = ()
        try:
            self._pre_call_revalidate(
                claim=claim,
                session_id=session_id,
                project_id=project_id,
                continuation_root_record_id=continuation_root_record_id,
                instruction_package_id=instruction_package_id,
                exact_run_reservation_id=exact_run_reservation_id,
                exact_worker_start_reservation_id=(
                    exact_worker_start_reservation_id
                ),
            )
        except _Blocked as exc:
            pre_call_blocked_reasons = self._dedupe_reasons(
                (_PRE_CALL_FAILED, exc.reason)
            )
        except Exception:
            pre_call_blocked_reasons = (
                _PRE_CALL_FAILED,
                "exact_worker_invocation_outcome_history_invalid",
            )
        finally:
            if shared_session.in_transaction():
                shared_session.rollback()

        worker_result: Any = None
        worker_exception: Exception | None = None
        if not pre_call_blocked_reasons:
            try:
                worker_result = self._task_worker.run_reserved_once(
                    task_id=claim.next_task_id,
                    run_id=claim.exact_run_id,
                )
            except Exception as exc:
                worker_exception = exc
            finally:
                if shared_session.in_transaction():
                    shared_session.rollback()

        try:
            self._require_shared_session()
            with self._message_repository.sqlite_immediate_transaction():
                result = self._record_or_replay_outcome(
                    claim=claim,
                    session_id=session_id,
                    project_id=project_id,
                    continuation_root_record_id=continuation_root_record_id,
                    instruction_package_id=instruction_package_id,
                    exact_run_reservation_id=exact_run_reservation_id,
                    exact_worker_start_reservation_id=(
                        exact_worker_start_reservation_id
                    ),
                    pre_call_blocked_reasons=pre_call_blocked_reasons,
                    worker_result=worker_result,
                    worker_exception=worker_exception,
                )
            return result
        except Exception:
            if shared_session.in_transaction():
                shared_session.rollback()
            return self._recovery_result(
                claim_id=claim.exact_worker_invocation_claim_id,
                reasons=(_CLAIM_WITHOUT_OUTCOME, _PERSISTENCE_FAILED),
            )

    def _resolve_replayed_claim(
        self,
        *,
        claim: ProjectDirectorCrossTaskExactWorkerInvocationClaim,
        session_id: UUID,
        project_id: UUID,
        continuation_root_record_id: UUID,
        instruction_package_id: UUID,
        exact_run_reservation_id: UUID,
        exact_worker_start_reservation_id: UUID,
    ) -> ProjectDirectorCrossTaskExactWorkerInvocationOutcomeResult:
        shared_session = self._message_repository._session
        try:
            self._require_shared_session()
            with self._message_repository.sqlite_immediate_transaction():
                history = self._load_history(
                    session_id=session_id,
                    target_claim=claim,
                    exact_run_reservation_id=exact_run_reservation_id,
                    exact_worker_start_reservation_id=(
                        exact_worker_start_reservation_id
                    ),
                )
                graph = self._locate_exact_graph(
                    history=history,
                    expected_claim=claim,
                    session_id=session_id,
                    project_id=project_id,
                    continuation_root_record_id=continuation_root_record_id,
                    instruction_package_id=instruction_package_id,
                    exact_run_reservation_id=exact_run_reservation_id,
                    exact_worker_start_reservation_id=(
                        exact_worker_start_reservation_id
                    ),
                )
                matches = self._matching_outcomes(history, graph.claim)
                if not matches:
                    return self._recovery_result(
                        claim_id=claim.exact_worker_invocation_claim_id,
                        reasons=(_CLAIM_WITHOUT_OUTCOME,),
                    )
                if len(matches) != 1:
                    raise _Blocked(
                        "exact_worker_invocation_outcome_replay_conflict"
                    )
                _, outcome = matches[0]
                return self._replayed_result(outcome)
        except _Blocked as exc:
            return self._blocked_result(
                reason=exc.reason,
                claim_id=claim.exact_worker_invocation_claim_id,
            )
        except Exception:
            if shared_session.in_transaction():
                shared_session.rollback()
            return self._recovery_result(
                claim_id=claim.exact_worker_invocation_claim_id,
                reasons=(_CLAIM_WITHOUT_OUTCOME, _PERSISTENCE_FAILED),
            )

    def _pre_call_revalidate(
        self,
        *,
        claim: ProjectDirectorCrossTaskExactWorkerInvocationClaim,
        session_id: UUID,
        project_id: UUID,
        continuation_root_record_id: UUID,
        instruction_package_id: UUID,
        exact_run_reservation_id: UUID,
        exact_worker_start_reservation_id: UUID,
    ) -> None:
        history = self._load_history(
            session_id=session_id,
            target_claim=claim,
            exact_run_reservation_id=exact_run_reservation_id,
            exact_worker_start_reservation_id=exact_worker_start_reservation_id,
        )
        graph = self._locate_exact_graph(
            history=history,
            expected_claim=claim,
            session_id=session_id,
            project_id=project_id,
            continuation_root_record_id=continuation_root_record_id,
            instruction_package_id=instruction_package_id,
            exact_run_reservation_id=exact_run_reservation_id,
            exact_worker_start_reservation_id=exact_worker_start_reservation_id,
        )
        self._validate_claim_for_call(graph.claim)
        self._validate_task_for_call(graph.claim)
        self._validate_run_for_call(graph.claim)
        self._validate_active_run_for_call(graph.claim)
        self._validate_agent_sessions_for_call(graph.claim)
        if self._matching_outcomes(history, graph.claim):
            raise _Blocked("exact_worker_invocation_outcome_replay_conflict")

        session = self._message_repository._session
        if session.new or session.dirty or session.deleted:
            raise _Blocked(
                "exact_worker_invocation_outcome_pre_call_revalidation_failed"
            )

    def _record_or_replay_outcome(
        self,
        *,
        claim: ProjectDirectorCrossTaskExactWorkerInvocationClaim,
        session_id: UUID,
        project_id: UUID,
        continuation_root_record_id: UUID,
        instruction_package_id: UUID,
        exact_run_reservation_id: UUID,
        exact_worker_start_reservation_id: UUID,
        pre_call_blocked_reasons: tuple[
            CrossTaskExactWorkerInvocationOutcomeBlockedReason,
            ...,
        ],
        worker_result: Any,
        worker_exception: Exception | None,
    ) -> ProjectDirectorCrossTaskExactWorkerInvocationOutcomeResult:
        history = self._load_history(
            session_id=session_id,
            target_claim=claim,
            exact_run_reservation_id=exact_run_reservation_id,
            exact_worker_start_reservation_id=exact_worker_start_reservation_id,
        )
        graph = self._locate_exact_graph(
            history=history,
            expected_claim=claim,
            session_id=session_id,
            project_id=project_id,
            continuation_root_record_id=continuation_root_record_id,
            instruction_package_id=instruction_package_id,
            exact_run_reservation_id=exact_run_reservation_id,
            exact_worker_start_reservation_id=exact_worker_start_reservation_id,
        )
        existing = self._matching_outcomes(history, graph.claim)
        if existing:
            if len(existing) != 1:
                raise _Blocked(
                    "exact_worker_invocation_outcome_replay_conflict"
                )
            return self._replayed_result(existing[0][1])

        after_state = self._load_after_state(graph.claim)
        outcome = self._build_outcome(
            graph=graph,
            pre_call_blocked_reasons=pre_call_blocked_reasons,
            worker_result=worker_result,
            worker_exception=worker_exception,
            after_state=after_state,
        )
        message = self._build_outcome_message(
            outcome=outcome,
            sequence_no=self._message_repository.get_next_sequence_no(
                session_id=session_id
            ),
        )
        persisted = self._message_repository.create(message)
        self._post_write_validate(persisted, outcome, graph)
        return ProjectDirectorCrossTaskExactWorkerInvocationOutcomeResult(
            status="outcome_recorded",
            exact_worker_invocation_claim_id=(
                claim.exact_worker_invocation_claim_id
            ),
            outcome=outcome,
            blocked_reasons=(),
            outcome_recorded=True,
            outcome_replayed=False,
            resumed_from_existing_outcome=False,
            recovery_required=outcome.human_recovery_required,
            automatic_worker_call_allowed=False,
            worker_call_attempted=outcome.worker_call_attempted,
            worker_call_state_indeterminate=False,
            product_runtime_git_write_allowed=False,
        )

    def _load_history(
        self,
        *,
        session_id: UUID,
        target_claim: ProjectDirectorCrossTaskExactWorkerInvocationClaim,
        exact_run_reservation_id: UUID,
        exact_worker_start_reservation_id: UUID,
    ) -> _History:
        try:
            messages = self._iter_session_messages(session_id)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(
                "exact_worker_invocation_outcome_history_invalid"
            ) from exc

        packages: list[Any] = []
        roots: list[Any] = []
        exact_runs: list[Any] = []
        worker_starts: list[Any] = []
        claims: list[Any] = []
        outcomes: list[Any] = []
        for message in messages:
            family_flags = (
                self._claim_service._is_package_family(message),
                self._claim_service._is_root_family(message),
                self._claim_service._is_exact_run_reservation_family(message),
                self._claim_service._is_worker_start_reservation_family(message),
                self._claim_service._is_invocation_claim_family(message),
                self._is_invocation_outcome_family(message),
            )
            if sum(family_flags) > 1:
                raise _Blocked(
                    "exact_worker_invocation_outcome_history_invalid"
                )
            if not any(family_flags):
                continue
            try:
                if family_flags[0]:
                    reason = (
                        "exact_worker_invocation_outcome_package_invalid"
                        if self._raw_action_id_matches(
                            message,
                            "package_id",
                            target_claim.instruction_package_id,
                        )
                        else "exact_worker_invocation_outcome_history_invalid"
                    )
                    packages.append(
                        (
                            message,
                            self._claim_service._parse_package_message(
                                message,
                                reason=self._claim_reason(reason),
                            ),
                        )
                    )
                elif family_flags[1]:
                    roots.append(
                        (
                            message,
                            self._claim_service._parse_root_message(
                                message,
                                reason=(
                                    "exact_worker_invocation_claim_history_invalid"
                                ),
                            ),
                        )
                    )
                elif family_flags[2]:
                    reason = (
                        "exact_worker_invocation_outcome_exact_run_reservation_invalid"
                        if self._raw_action_id_matches(
                            message,
                            "exact_run_reservation_id",
                            exact_run_reservation_id,
                        )
                        else "exact_worker_invocation_outcome_history_invalid"
                    )
                    exact_runs.append(
                        (
                            message,
                            self._claim_service._parse_exact_run_reservation_message(
                                message,
                                reason=self._claim_reason(reason),
                            ),
                        )
                    )
                elif family_flags[3]:
                    reason = (
                        "exact_worker_invocation_outcome_worker_start_reservation_invalid"
                        if self._raw_action_id_matches(
                            message,
                            "exact_worker_start_reservation_id",
                            exact_worker_start_reservation_id,
                        )
                        else "exact_worker_invocation_outcome_history_invalid"
                    )
                    worker_starts.append(
                        (
                            message,
                            self._claim_service._parse_worker_start_reservation_message(
                                message,
                                reason=self._claim_reason(reason),
                            ),
                        )
                    )
                elif family_flags[4]:
                    reason = (
                        "exact_worker_invocation_outcome_claim_invalid"
                        if self._message_targets_claim(message, target_claim)
                        else "exact_worker_invocation_outcome_history_invalid"
                    )
                    claims.append(
                        (
                            message,
                            self._claim_service._parse_invocation_claim_message(
                                message,
                                reason=self._claim_reason(reason),
                            ),
                        )
                    )
                else:
                    reason = (
                        "exact_worker_invocation_outcome_replay_conflict"
                        if self._message_targets_claim(message, target_claim)
                        else "exact_worker_invocation_outcome_history_invalid"
                    )
                    outcomes.append(
                        (
                            message,
                            self._parse_outcome_message(message, reason=reason),
                        )
                    )
            except _ClaimBlocked as exc:
                raise _Blocked(self._map_claim_reason(exc.reason)) from exc

        history = _History(
            packages=tuple(packages),
            roots=tuple(roots),
            exact_run_reservations=tuple(exact_runs),
            worker_start_reservations=tuple(worker_starts),
            invocation_claims=tuple(claims),
            invocation_outcomes=tuple(outcomes),
        )
        try:
            self._claim_service._validate_history_graph(
                history,
                exact_run_reservation_id=exact_run_reservation_id,
                exact_worker_start_reservation_id=(
                    exact_worker_start_reservation_id
                ),
            )
        except _ClaimBlocked as exc:
            raise _Blocked(self._map_claim_reason(exc.reason)) from exc
        self._validate_outcome_history(history, target_claim)
        return history

    def _iter_session_messages(
        self,
        session_id: UUID,
    ) -> list[ProjectDirectorMessage]:
        messages: list[ProjectDirectorMessage] = []
        before_message_id: UUID | None = None
        seen_cursors: set[UUID] = set()
        while True:
            page, has_more = self._message_repository.list_by_session_id(
                session_id=session_id,
                limit=_PAGE_SIZE,
                before_message_id=before_message_id,
            )
            messages.extend(page)
            if not has_more:
                break
            if not page:
                raise ValueError("exact invocation outcome history page is empty")
            next_cursor = page[0].id
            if next_cursor == before_message_id or next_cursor in seen_cursors:
                raise ValueError("exact invocation outcome history cursor stalled")
            seen_cursors.add(next_cursor)
            before_message_id = next_cursor

        ordered = sorted(messages, key=lambda item: item.sequence_no)
        message_ids = [message.id for message in ordered]
        sequence_numbers = [message.sequence_no for message in ordered]
        if (
            len(message_ids) != len(set(message_ids))
            or len(sequence_numbers) != len(set(sequence_numbers))
        ):
            raise ValueError("exact invocation outcome history is not unique")
        return ordered

    @staticmethod
    def _is_invocation_outcome_family(
        message: ProjectDirectorMessage,
    ) -> bool:
        return (
            message.intent == CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_INTENT
            or message.source_detail
            == CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL
            or any(
                isinstance(action, dict)
                and action.get("type")
                == CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_ACTION_TYPE
                for action in message.suggested_actions
            )
        )

    def _parse_outcome_message(
        self,
        message: ProjectDirectorMessage,
        *,
        reason: CrossTaskExactWorkerInvocationOutcomeBlockedReason,
    ) -> ProjectDirectorCrossTaskExactWorkerInvocationOutcome:
        action = self._strict_action(
            message,
            intent=CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_INTENT,
            source_detail=(
                CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL
            ),
            action_type=CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_ACTION_TYPE,
            schema_version=CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_SCHEMA_VERSION,
            reason=reason,
        )
        payload = dict(action)
        payload.pop("type", None)
        try:
            outcome = (
                ProjectDirectorCrossTaskExactWorkerInvocationOutcome
                .model_validate(payload)
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(reason) from exc
        if (
            outcome.worker_invocation_outcome_replay_key
            != outcome.compute_worker_invocation_outcome_replay_key(
                continuation_id=outcome.continuation_id,
                exact_worker_invocation_claim_id=(
                    outcome.exact_worker_invocation_claim_id
                ),
                exact_worker_invocation_claim_token=(
                    outcome.exact_worker_invocation_claim_token
                ),
                exact_worker_start_reservation_id=(
                    outcome.exact_worker_start_reservation_id
                ),
                next_task_id=outcome.next_task_id,
                exact_run_id=outcome.exact_run_id,
            )
            or outcome.worker_invocation_outcome_fingerprint
            != outcome.compute_fingerprint()
        ):
            raise _Blocked(reason)
        self._validate_outcome_message_binding(
            message,
            outcome,
            action=action,
            reason=reason,
        )
        return outcome

    @staticmethod
    def _strict_action(
        message: ProjectDirectorMessage,
        *,
        intent: str,
        source_detail: str,
        action_type: str,
        schema_version: str,
        reason: CrossTaskExactWorkerInvocationOutcomeBlockedReason,
    ) -> dict[str, Any]:
        if (
            message.role != ProjectDirectorMessageRole.ASSISTANT
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent != intent
            or message.source_detail != source_detail
            or message.requires_confirmation is not False
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
            or message.token_count is not None
            or message.estimated_cost is not None
            or len(message.suggested_actions) != 1
            or not isinstance(message.suggested_actions[0], dict)
        ):
            raise _Blocked(reason)
        action = message.suggested_actions[0]
        if (
            action.get("type") != action_type
            or action.get("schema_version") != schema_version
        ):
            raise _Blocked(reason)
        return action

    @staticmethod
    def _validate_outcome_message_binding(
        message: ProjectDirectorMessage,
        outcome: ProjectDirectorCrossTaskExactWorkerInvocationOutcome,
        *,
        action: dict[str, Any] | None = None,
        reason: CrossTaskExactWorkerInvocationOutcomeBlockedReason,
    ) -> None:
        expected_action = {
            "type": CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_ACTION_TYPE,
            **outcome.model_dump(mode="json"),
        }
        if (
            (action if action is not None else message.suggested_actions[0])
            != expected_action
            or message.id != outcome.exact_worker_invocation_outcome_id
            or message.content
            != (
                f"{_OUTCOME_CONTENT_PREFIX}: "
                f"{outcome.exact_worker_invocation_outcome_id}"
            )
            or message.session_id != outcome.session_id
            or message.related_plan_version_id != outcome.plan_version_id
            or message.related_project_id != outcome.project_id
            or message.related_task_id != outcome.next_task_id
            or message.created_at != outcome.created_at
            or message.forbidden_actions_detected
            != list(outcome.forbidden_actions)
        ):
            raise _Blocked(reason)

    def _validate_outcome_history(
        self,
        history: _History,
        target_claim: ProjectDirectorCrossTaskExactWorkerInvocationClaim,
    ) -> None:
        outcomes = [item[1] for item in history.invocation_outcomes]
        collections = (
            [item.exact_worker_invocation_outcome_id for item in outcomes],
            [item.worker_invocation_outcome_replay_key for item in outcomes],
            [item.exact_worker_invocation_claim_id for item in outcomes],
            [item.exact_worker_invocation_claim_token for item in outcomes],
            [item.exact_worker_start_reservation_id for item in outcomes],
            [item.exact_run_reservation_id for item in outcomes],
            [item.exact_run_id for item in outcomes],
        )
        if any(len(values) != len(set(values)) for values in collections):
            if any(self._outcome_targets_claim(item, target_claim) for item in outcomes):
                raise _Blocked(
                    "exact_worker_invocation_outcome_replay_conflict"
                )
            raise _Blocked("exact_worker_invocation_outcome_history_conflict")

        for outcome in outcomes:
            root_matches = [
                item
                for _, item in history.roots
                if item.record_id == outcome.continuation_root_record_id
            ]
            package_matches = [
                item
                for _, item in history.packages
                if item.package_id == outcome.instruction_package_id
            ]
            exact_run_matches = [
                item
                for _, item in history.exact_run_reservations
                if item.exact_run_reservation_id
                == outcome.exact_run_reservation_id
            ]
            worker_start_matches = [
                item
                for _, item in history.worker_start_reservations
                if item.exact_worker_start_reservation_id
                == outcome.exact_worker_start_reservation_id
            ]
            claim_matches = [
                item
                for _, item in history.invocation_claims
                if item.exact_worker_invocation_claim_id
                == outcome.exact_worker_invocation_claim_id
            ]
            reason: CrossTaskExactWorkerInvocationOutcomeBlockedReason = (
                "exact_worker_invocation_outcome_replay_conflict"
                if self._outcome_targets_claim(outcome, target_claim)
                else "exact_worker_invocation_outcome_history_conflict"
            )
            if any(
                len(matches) != 1
                for matches in (
                    root_matches,
                    package_matches,
                    exact_run_matches,
                    worker_start_matches,
                    claim_matches,
                )
            ):
                raise _Blocked(reason)
            self._validate_outcome_history_binding(
                outcome=outcome,
                root=root_matches[0],
                package=package_matches[0],
                exact_run_reservation=exact_run_matches[0],
                worker_start_reservation=worker_start_matches[0],
                claim=claim_matches[0],
                reason=reason,
            )

    def _validate_outcome_history_binding(
        self,
        *,
        outcome: ProjectDirectorCrossTaskExactWorkerInvocationOutcome,
        root: ProjectDirectorCrossTaskContinuationRoot,
        package: ProjectDirectorNextTaskInstructionPackage,
        exact_run_reservation: ProjectDirectorCrossTaskExactRunReservation,
        worker_start_reservation: ProjectDirectorCrossTaskExactWorkerStartReservation,
        claim: ProjectDirectorCrossTaskExactWorkerInvocationClaim,
        reason: CrossTaskExactWorkerInvocationOutcomeBlockedReason,
    ) -> None:
        try:
            self._claim_service._validate_claim_history_binding(
                claim,
                root,
                package,
                exact_run_reservation,
                worker_start_reservation,
                reason="exact_worker_invocation_claim_history_conflict",
            )
        except _ClaimBlocked as exc:
            raise _Blocked(reason) from exc
        if (
            outcome.continuation_sequence_no != 5
            or outcome.previous_record_id
            != claim.exact_worker_invocation_claim_id
            or outcome.replay_of_record_id is not None
            or outcome.continuation_id != claim.continuation_id
            or outcome.continuation_root_record_id
            != claim.continuation_root_record_id
            or outcome.continuation_root_fingerprint
            != claim.continuation_root_fingerprint
            or outcome.continuation_idempotency_key
            != claim.continuation_idempotency_key
            or outcome.instruction_package_id != claim.instruction_package_id
            or outcome.instruction_package_fingerprint
            != claim.instruction_package_fingerprint
            or outcome.instruction_candidate_fingerprint
            != claim.instruction_candidate_fingerprint
            or outcome.exact_run_reservation_id
            != claim.exact_run_reservation_id
            or outcome.exact_run_reservation_fingerprint
            != claim.exact_run_reservation_fingerprint
            or outcome.exact_run_reservation_replay_key
            != claim.exact_run_reservation_replay_key
            or outcome.exact_worker_start_reservation_id
            != claim.exact_worker_start_reservation_id
            or outcome.exact_worker_start_reservation_fingerprint
            != claim.exact_worker_start_reservation_fingerprint
            or outcome.exact_worker_start_reservation_replay_key
            != claim.exact_worker_start_reservation_replay_key
            or outcome.exact_worker_invocation_claim_fingerprint
            != claim.worker_invocation_claim_fingerprint
            or outcome.exact_worker_invocation_claim_replay_key
            != claim.worker_invocation_claim_replay_key
            or outcome.exact_worker_invocation_claim_token
            != claim.worker_invocation_claim_token
            or outcome.session_id != claim.session_id
            or outcome.project_id != claim.project_id
            or outcome.plan_version_id != claim.plan_version_id
            or outcome.task_creation_record_id != claim.task_creation_record_id
            or outcome.source_task_id != claim.source_task_id
            or outcome.source_run_id != claim.source_run_id
            or outcome.source_completion_evidence_id
            != claim.source_completion_evidence_id
            or outcome.source_completion_evidence_fingerprint
            != claim.source_completion_evidence_fingerprint
            or outcome.next_task_id != claim.next_task_id
            or outcome.next_task_index != claim.next_task_index
            or outcome.task_count != claim.task_count
            or outcome.exact_run_id != claim.exact_run_id
            or outcome.claim_worker_model_name != claim.worker_model_name
            or outcome.claim_worker_model_tier != claim.worker_model_tier
            or outcome.claim_worker_selected_skill_codes
            != tuple(item.skill_code for item in claim.worker_selected_skills)
            or outcome.claim_worker_selected_skill_names
            != tuple(item.skill_name for item in claim.worker_selected_skills)
            or outcome.claim_worker_owner_role_code
            != claim.worker_owner_role_code
            or outcome.claim_worker_upstream_role_code
            != claim.worker_upstream_role_code
            or outcome.claim_worker_downstream_role_code
            != claim.worker_downstream_role_code
        ):
            raise _Blocked(reason)

    def _locate_exact_graph(
        self,
        *,
        history: _History,
        expected_claim: ProjectDirectorCrossTaskExactWorkerInvocationClaim,
        session_id: UUID,
        project_id: UUID,
        continuation_root_record_id: UUID,
        instruction_package_id: UUID,
        exact_run_reservation_id: UUID,
        exact_worker_start_reservation_id: UUID,
    ) -> _ExactGraph:
        try:
            root, package, exact_run, worker_start = (
                self._claim_service._locate_exact_graph(
                    history=history,
                    session_id=session_id,
                    project_id=project_id,
                    continuation_root_record_id=continuation_root_record_id,
                    instruction_package_id=instruction_package_id,
                    exact_run_reservation_id=exact_run_reservation_id,
                    exact_worker_start_reservation_id=(
                        exact_worker_start_reservation_id
                    ),
                )
            )
        except _ClaimBlocked as exc:
            raise _Blocked(self._map_claim_reason(exc.reason)) from exc
        claims = [
            item
            for _, item in history.invocation_claims
            if item.exact_worker_invocation_claim_id
            == expected_claim.exact_worker_invocation_claim_id
        ]
        if len(claims) != 1 or claims[0] != expected_claim:
            raise _Blocked("exact_worker_invocation_outcome_claim_invalid")
        return _ExactGraph(
            root=root,
            package=package,
            exact_run_reservation=exact_run,
            worker_start_reservation=worker_start,
            claim=claims[0],
        )

    @staticmethod
    def _validate_claim_for_call(
        claim: ProjectDirectorCrossTaskExactWorkerInvocationClaim,
    ) -> None:
        try:
            validated = ProjectDirectorCrossTaskExactWorkerInvocationClaim.model_validate(
                claim.model_dump(mode="python")
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(
                "exact_worker_invocation_outcome_claim_invalid"
            ) from exc
        if (
            validated != claim
            or claim.worker_invocation_claim_replay_key
            != claim.compute_worker_invocation_claim_replay_key(
                continuation_id=claim.continuation_id,
                exact_worker_start_reservation_id=(
                    claim.exact_worker_start_reservation_id
                ),
                exact_run_reservation_id=claim.exact_run_reservation_id,
                instruction_package_id=claim.instruction_package_id,
                next_task_id=claim.next_task_id,
                exact_run_id=claim.exact_run_id,
            )
            or claim.worker_invocation_claim_token
            != claim.compute_worker_invocation_claim_token(
                exact_worker_invocation_claim_id=(
                    claim.exact_worker_invocation_claim_id
                ),
                worker_invocation_claim_replay_key=(
                    claim.worker_invocation_claim_replay_key
                ),
                exact_worker_start_reservation_id=(
                    claim.exact_worker_start_reservation_id
                ),
                exact_worker_start_reservation_fingerprint=(
                    claim.exact_worker_start_reservation_fingerprint
                ),
                exact_run_id=claim.exact_run_id,
            )
            or claim.worker_invocation_claim_fingerprint
            != claim.compute_fingerprint()
            or claim.worker_invocation_claimed is not True
            or claim.single_use_worker_call_authorized is not True
            or claim.worker_called is not False
            or claim.worker_call_attempted is not False
            or claim.product_runtime_git_write_allowed is not False
        ):
            raise _Blocked("exact_worker_invocation_outcome_claim_invalid")

    def _validate_task_for_call(
        self,
        claim: ProjectDirectorCrossTaskExactWorkerInvocationClaim,
    ) -> None:
        try:
            task = self._task_repository.get_by_id(claim.next_task_id)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(
                "exact_worker_invocation_outcome_task_identity_conflict"
            ) from exc
        if (
            task is None
            or task.id != claim.next_task_id
            or task.project_id != claim.project_id
            or task.status != TaskStatus.RUNNING
            or task.human_status
            not in {TaskHumanStatus.NONE, TaskHumanStatus.RESOLVED}
            or task.human_status.value != claim.task_human_status_before
            or task.paused_reason is not None
        ):
            raise _Blocked(
                "exact_worker_invocation_outcome_task_identity_conflict"
            )

    def _validate_run_for_call(
        self,
        claim: ProjectDirectorCrossTaskExactWorkerInvocationClaim,
    ) -> None:
        try:
            run = self._run_repository.get_by_id(claim.exact_run_id)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(
                "exact_worker_invocation_outcome_run_identity_conflict"
            ) from exc
        if (
            run is None
            or run.id != claim.exact_run_id
            or run.task_id != claim.next_task_id
            or run.status != RunStatus.RUNNING
            or run.started_at != claim.exact_run_started_at
            or run.created_at != claim.exact_run_created_at
            or run.finished_at is not None
            or run.failure_category is not None
            or run.quality_gate_passed is not None
        ):
            raise _Blocked(
                "exact_worker_invocation_outcome_run_identity_conflict"
            )
        decision = run.strategy_decision
        if (
            decision is None
            or run.model_name != claim.worker_model_name
            or decision.model_name != claim.worker_model_name
            or decision.model_tier != claim.worker_model_tier
            or tuple(decision.selected_skill_codes)
            != tuple(item.skill_code for item in claim.worker_selected_skills)
            or tuple(decision.selected_skill_names)
            != tuple(item.skill_name for item in claim.worker_selected_skills)
            or run.owner_role_code != claim.worker_owner_role_code
            or run.upstream_role_code != claim.worker_upstream_role_code
            or run.downstream_role_code != claim.worker_downstream_role_code
        ):
            raise _Blocked(
                "exact_worker_invocation_outcome_worker_authority_conflict"
            )

    def _validate_active_run_for_call(
        self,
        claim: ProjectDirectorCrossTaskExactWorkerInvocationClaim,
    ) -> None:
        try:
            runs = self._run_repository.list_by_task_id(claim.next_task_id)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(
                "exact_worker_invocation_outcome_run_identity_conflict"
            ) from exc
        active_ids = tuple(
            sorted(
                (
                    run.id
                    for run in runs
                    if run.status in {RunStatus.QUEUED, RunStatus.RUNNING}
                ),
                key=str,
            )
        )
        if active_ids != (claim.exact_run_id,):
            raise _Blocked(
                "exact_worker_invocation_outcome_run_identity_conflict"
            )

    def _validate_agent_sessions_for_call(
        self,
        claim: ProjectDirectorCrossTaskExactWorkerInvocationClaim,
    ) -> None:
        try:
            sessions = self._agent_session_repository.list_by_run_id(
                claim.exact_run_id
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(_WORKER_BINDING_CONFLICT) from exc
        if sessions:
            raise _Blocked(_WORKER_BINDING_CONFLICT)

    def _load_after_state(
        self,
        claim: ProjectDirectorCrossTaskExactWorkerInvocationClaim,
    ) -> _AfterState:
        task = self._task_repository.get_by_id(claim.next_task_id)
        run = self._run_repository.get_by_id(claim.exact_run_id)
        sessions = self._agent_session_repository.list_by_run_id(
            claim.exact_run_id
        )
        reasons: list[CrossTaskExactWorkerInvocationOutcomeBlockedReason] = []
        if (
            task is None
            or task.id != claim.next_task_id
            or task.project_id != claim.project_id
        ):
            reasons.append(
                "exact_worker_invocation_outcome_task_identity_conflict"
            )
        if (
            run is None
            or run.id != claim.exact_run_id
            or run.task_id != claim.next_task_id
        ):
            reasons.append(
                "exact_worker_invocation_outcome_run_identity_conflict"
            )
        agent_session = sessions[0] if len(sessions) == 1 else None
        if len(sessions) > 1:
            reasons.append(_WORKER_BINDING_CONFLICT)
        elif agent_session is not None and (
            agent_session.project_id != claim.project_id
            or agent_session.task_id != claim.next_task_id
            or agent_session.run_id != claim.exact_run_id
        ):
            reasons.append(_WORKER_BINDING_CONFLICT)
        return _AfterState(
            task=task,
            run=run,
            agent_session=agent_session,
            blocked_reasons=self._dedupe_reasons(tuple(reasons)),
        )

    def _build_outcome(
        self,
        *,
        graph: _ExactGraph,
        pre_call_blocked_reasons: tuple[
            CrossTaskExactWorkerInvocationOutcomeBlockedReason,
            ...,
        ],
        worker_result: Any,
        worker_exception: Exception | None,
        after_state: _AfterState,
    ) -> ProjectDirectorCrossTaskExactWorkerInvocationOutcome:
        claim = graph.claim
        formal_result = (
            worker_result if isinstance(worker_result, WorkerRunResult) else None
        )
        returned = not pre_call_blocked_reasons and worker_exception is None
        raised = not pre_call_blocked_reasons and worker_exception is not None
        status = "not_invoked" if pre_call_blocked_reasons else (
            "raised" if raised else "returned"
        )

        reasons: list[CrossTaskExactWorkerInvocationOutcomeBlockedReason] = list(
            pre_call_blocked_reasons
        )
        if status != "not_invoked":
            reasons.extend(after_state.blocked_reasons)
        if raised:
            reasons.append(_WORKER_RAISED)

        message = (
            self._safe_text(formal_result.message, 2_000)
            if formal_result is not None
            else None
        )
        execution_mode = (
            self._safe_text(formal_result.execution_mode, 200)
            if formal_result is not None
            else None
        )
        failure_category = (
            self._safe_text(
                self._enum_value(formal_result.failure_category),
                200,
            )
            if formal_result is not None
            else None
        )
        result_summary = (
            self._safe_text(formal_result.result_summary, 2_000)
            if formal_result is not None
            else None
        )
        raw_model_name = formal_result.model_name if formal_result else None
        raw_model_tier = formal_result.model_tier if formal_result else None
        raw_skill_codes = (
            formal_result.selected_skill_codes if formal_result else None
        )
        raw_skill_names = (
            formal_result.selected_skill_names if formal_result else None
        )
        raw_owner = formal_result.owner_role_code if formal_result else None
        raw_upstream = (
            formal_result.upstream_role_code if formal_result else None
        )
        raw_downstream = (
            formal_result.downstream_role_code if formal_result else None
        )
        result_model_name = (
            self._safe_text(raw_model_name, 100)
            if formal_result is not None
            else None
        )
        result_model_tier = (
            self._safe_text(raw_model_tier, 40)
            if formal_result is not None
            else None
        )
        result_skill_codes = (
            self._safe_tuple(raw_skill_codes, 200)
            if formal_result is not None
            else ()
        )
        result_skill_names = (
            self._safe_tuple(raw_skill_names, 200)
            if formal_result is not None
            else ()
        )
        result_owner = (
            self._safe_role(raw_owner)
            if formal_result is not None
            else None
        )
        result_upstream = (
            self._safe_role(raw_upstream)
            if formal_result is not None
            else None
        )
        result_downstream = (
            self._safe_role(raw_downstream)
            if formal_result is not None
            else None
        )
        route_reason = (
            self._safe_text(formal_result.route_reason, 2_000)
            if formal_result is not None
            else None
        )
        strategy_code = (
            self._safe_text(formal_result.strategy_code, 100)
            if formal_result is not None
            else None
        )
        dispatch_status = (
            self._safe_text(formal_result.dispatch_status, 100)
            if formal_result is not None
            else None
        )

        snapshot = (
            formal_result.reserved_run_execution_snapshot
            if formal_result is not None
            else None
        )
        raw_snapshot_present = snapshot is not None
        raw_snapshot_source = (
            getattr(snapshot, "source", None)
            if raw_snapshot_present
            else None
        )
        snapshot_source = (
            self._safe_text(raw_snapshot_source, 200)
            if raw_snapshot_present
            else None
        )
        snapshot_task_id = (
            getattr(snapshot, "exact_task_id", None)
            if isinstance(getattr(snapshot, "exact_task_id", None), UUID)
            else None
        )
        snapshot_run_id = (
            getattr(snapshot, "exact_run_id", None)
            if isinstance(getattr(snapshot, "exact_run_id", None), UUID)
            else None
        )
        snapshot_blocked_reasons = (
            tuple(
                dict.fromkeys(
                    self._safe_tuple(
                        getattr(snapshot, "blocked_reasons", ()),
                        500,
                    )
                )
            )
            if raw_snapshot_present
            else ()
        )
        raw_snapshot_blocked_reasons = (
            getattr(snapshot, "blocked_reasons", None)
            if raw_snapshot_present
            else None
        )
        raw_budget_rechecked = (
            getattr(snapshot, "budget_rechecked", None)
            if raw_snapshot_present
            else None
        )
        snapshot_present = bool(
            raw_snapshot_present
            and snapshot_source is not None
            and snapshot_task_id is not None
            and snapshot_run_id is not None
        )

        authority_valid = bool(
            formal_result is not None
            and isinstance(raw_model_name, str)
            and raw_model_name == raw_model_name.strip()
            and raw_model_name == claim.worker_model_name
            and isinstance(raw_model_tier, str)
            and raw_model_tier == raw_model_tier.strip()
            and raw_model_tier == claim.worker_model_tier
            and isinstance(raw_skill_codes, list)
            and all(isinstance(item, str) for item in raw_skill_codes)
            and tuple(raw_skill_codes)
            == tuple(item.skill_code for item in claim.worker_selected_skills)
            and result_skill_codes == tuple(raw_skill_codes)
            and isinstance(raw_skill_names, list)
            and all(isinstance(item, str) for item in raw_skill_names)
            and tuple(raw_skill_names)
            == tuple(item.skill_name for item in claim.worker_selected_skills)
            and result_skill_names == tuple(raw_skill_names)
            and isinstance(raw_owner, ProjectRoleCode)
            and raw_owner == claim.worker_owner_role_code
            and (
                raw_upstream is None
                or isinstance(raw_upstream, ProjectRoleCode)
            )
            and raw_upstream == claim.worker_upstream_role_code
            and (
                raw_downstream is None
                or isinstance(raw_downstream, ProjectRoleCode)
            )
            and raw_downstream == claim.worker_downstream_role_code
            and result_owner == raw_owner
            and result_upstream == raw_upstream
            and result_downstream == raw_downstream
        )
        if returned and formal_result is not None and not authority_valid:
            reasons.append(
                "exact_worker_invocation_outcome_worker_authority_conflict"
            )

        git_activity, git_activity_fields_valid = (
            self._worker_git_activity_state(formal_result)
            if formal_result is not None
            else (False, True)
        )
        git_boundary_violation = git_activity or not git_activity_fields_valid
        if git_boundary_violation:
            reasons.append(_GIT_BOUNDARY_VIOLATION)

        contract_valid = bool(
            returned
            and formal_result is not None
            and formal_result.claimed is True
            and isinstance(formal_result.message, str)
            and message
            and authority_valid
            and snapshot_present
            and isinstance(raw_snapshot_source, str)
            and raw_snapshot_source == "p23_d2_exact_reserved_run"
            and snapshot_source == raw_snapshot_source
            and getattr(snapshot, "reserved_run_execution_requested", None)
            is True
            and snapshot_task_id == claim.next_task_id
            and snapshot_run_id == claim.exact_run_id
            and getattr(snapshot, "exact_binding_validated", None) is True
            and getattr(snapshot, "task_routed", None) is False
            and getattr(snapshot, "task_claimed_in_this_cycle", None) is False
            and getattr(snapshot, "run_created_in_this_cycle", None) is False
            and getattr(snapshot, "existing_run_reused", None) is True
            and getattr(snapshot, "shared_execution_seam_used", None) is True
            and getattr(snapshot, "product_runtime_git_write_allowed", None)
            is False
            and isinstance(raw_budget_rechecked, bool)
            and isinstance(raw_snapshot_blocked_reasons, (list, tuple))
            and not raw_snapshot_blocked_reasons
            and not snapshot_blocked_reasons
            and not after_state.blocked_reasons
            and git_activity_fields_valid
            and not git_activity
        )
        if returned and not contract_valid:
            reasons.append(_WORKER_RESULT_INVALID)
        reasons_tuple = self._dedupe_reasons(tuple(reasons))

        task = after_state.task
        run = after_state.run
        agent = after_state.agent_session
        external_snapshot = (
            formal_result.external_executor_snapshot
            if formal_result is not None and returned
            else None
        )
        exception_type = (
            self._safe_text(type(worker_exception).__name__, 200)
            if worker_exception is not None
            else None
        )
        exception_summary = (
            self._safe_exception_summary(worker_exception)
            if worker_exception is not None
            else None
        )

        values: dict[str, Any] = {
            "exact_worker_invocation_outcome_id": uuid4(),
            "worker_invocation_outcome_fingerprint": "0" * 64,
            "worker_invocation_outcome_replay_key": (
                ProjectDirectorCrossTaskExactWorkerInvocationOutcome
                .compute_worker_invocation_outcome_replay_key(
                    continuation_id=claim.continuation_id,
                    exact_worker_invocation_claim_id=(
                        claim.exact_worker_invocation_claim_id
                    ),
                    exact_worker_invocation_claim_token=(
                        claim.worker_invocation_claim_token
                    ),
                    exact_worker_start_reservation_id=(
                        claim.exact_worker_start_reservation_id
                    ),
                    next_task_id=claim.next_task_id,
                    exact_run_id=claim.exact_run_id,
                )
            ),
            "created_at": utc_now(),
            "continuation_id": claim.continuation_id,
            "continuation_root_record_id": claim.continuation_root_record_id,
            "continuation_root_fingerprint": claim.continuation_root_fingerprint,
            "continuation_idempotency_key": claim.continuation_idempotency_key,
            "instruction_package_id": claim.instruction_package_id,
            "instruction_package_fingerprint": claim.instruction_package_fingerprint,
            "instruction_candidate_fingerprint": claim.instruction_candidate_fingerprint,
            "exact_run_reservation_id": claim.exact_run_reservation_id,
            "exact_run_reservation_fingerprint": claim.exact_run_reservation_fingerprint,
            "exact_run_reservation_replay_key": claim.exact_run_reservation_replay_key,
            "exact_worker_start_reservation_id": claim.exact_worker_start_reservation_id,
            "exact_worker_start_reservation_fingerprint": claim.exact_worker_start_reservation_fingerprint,
            "exact_worker_start_reservation_replay_key": claim.exact_worker_start_reservation_replay_key,
            "exact_worker_invocation_claim_id": claim.exact_worker_invocation_claim_id,
            "exact_worker_invocation_claim_fingerprint": claim.worker_invocation_claim_fingerprint,
            "exact_worker_invocation_claim_replay_key": claim.worker_invocation_claim_replay_key,
            "exact_worker_invocation_claim_token": claim.worker_invocation_claim_token,
            "continuation_sequence_no": 5,
            "previous_record_id": claim.exact_worker_invocation_claim_id,
            "replay_of_record_id": None,
            "status": status,
            "session_id": claim.session_id,
            "project_id": claim.project_id,
            "plan_version_id": claim.plan_version_id,
            "task_creation_record_id": claim.task_creation_record_id,
            "source_task_id": claim.source_task_id,
            "source_run_id": claim.source_run_id,
            "source_completion_evidence_id": claim.source_completion_evidence_id,
            "source_completion_evidence_fingerprint": claim.source_completion_evidence_fingerprint,
            "next_task_id": claim.next_task_id,
            "next_task_index": claim.next_task_index,
            "task_count": claim.task_count,
            "exact_run_id": claim.exact_run_id,
            "worker_called": status != "not_invoked",
            "worker_call_attempted": status != "not_invoked",
            "worker_returned": returned,
            "worker_raised": raised,
            "worker_started": status != "not_invoked",
            "worker_result_contract_valid": contract_valid,
            "worker_result_claimed": (
                formal_result.claimed
                if formal_result is not None
                and isinstance(formal_result.claimed, bool)
                and returned
                else None
            ),
            "worker_result_message": message if returned else None,
            "worker_execution_mode": execution_mode if returned else None,
            "worker_failure_category": failure_category if returned else None,
            "worker_quality_gate_passed": (
                formal_result.quality_gate_passed
                if formal_result is not None
                and isinstance(formal_result.quality_gate_passed, (bool, type(None)))
                and returned
                else None
            ),
            "worker_result_summary": result_summary if returned else None,
            "claim_worker_model_name": claim.worker_model_name,
            "claim_worker_model_tier": claim.worker_model_tier,
            "claim_worker_selected_skill_codes": tuple(
                item.skill_code for item in claim.worker_selected_skills
            ),
            "claim_worker_selected_skill_names": tuple(
                item.skill_name for item in claim.worker_selected_skills
            ),
            "claim_worker_owner_role_code": claim.worker_owner_role_code,
            "claim_worker_upstream_role_code": claim.worker_upstream_role_code,
            "claim_worker_downstream_role_code": claim.worker_downstream_role_code,
            "worker_result_model_name": result_model_name if returned else None,
            "worker_result_model_tier": result_model_tier if returned else None,
            "worker_result_selected_skill_codes": result_skill_codes if returned else (),
            "worker_result_selected_skill_names": result_skill_names if returned else (),
            "worker_result_owner_role_code": result_owner if returned else None,
            "worker_result_upstream_role_code": result_upstream if returned else None,
            "worker_result_downstream_role_code": result_downstream if returned else None,
            "worker_result_route_reason": route_reason if returned else None,
            "worker_result_strategy_code": strategy_code if returned else None,
            "worker_result_dispatch_status": dispatch_status if returned else None,
            "worker_authority_result_validated": authority_valid if returned else False,
            "reserved_snapshot_present": (
                snapshot_present if returned else False
            ),
            "reserved_snapshot_source": (
                snapshot_source if returned and snapshot_present else None
            ),
            "reserved_snapshot_exact_task_id": (
                snapshot_task_id if returned and snapshot_present else None
            ),
            "reserved_snapshot_exact_run_id": (
                snapshot_run_id if returned and snapshot_present else None
            ),
            "reserved_snapshot_exact_binding_validated": (
                getattr(snapshot, "exact_binding_validated", None) is True
                if returned and snapshot_present
                else False
            ),
            "reserved_snapshot_task_routed": (
                getattr(snapshot, "task_routed", None) is True
                if returned and snapshot_present
                else False
            ),
            "reserved_snapshot_task_claimed_in_this_cycle": (
                getattr(snapshot, "task_claimed_in_this_cycle", None) is True
                if returned and snapshot_present
                else False
            ),
            "reserved_snapshot_run_created_in_this_cycle": (
                getattr(snapshot, "run_created_in_this_cycle", None) is True
                if returned and snapshot_present
                else False
            ),
            "reserved_snapshot_budget_rechecked": (
                raw_budget_rechecked
                if returned and snapshot_present
                and isinstance(raw_budget_rechecked, bool)
                else False
            ),
            "reserved_snapshot_existing_run_reused": (
                getattr(snapshot, "existing_run_reused", None) is True
                if returned and snapshot_present
                else False
            ),
            "reserved_snapshot_shared_execution_seam_used": (
                getattr(snapshot, "shared_execution_seam_used", None) is True
                if returned and snapshot_present
                else False
            ),
            "reserved_snapshot_blocked_reasons": (
                snapshot_blocked_reasons
                if returned and snapshot_present
                else ()
            ),
            "task_status_after": self._enum_value(task.status) if task else None,
            "task_human_status_after": (
                self._enum_value(task.human_status) if task else None
            ),
            "task_paused_reason_after": (
                self._safe_text(task.paused_reason, 500) if task else None
            ),
            "run_status_after": self._enum_value(run.status) if run else None,
            "run_finished_at_after": run.finished_at if run else None,
            "run_failure_category_after": (
                self._safe_text(self._enum_value(run.failure_category), 200)
                if run
                else None
            ),
            "run_quality_gate_passed_after": (
                run.quality_gate_passed if run else None
            ),
            "agent_session_id": agent.id if agent else None,
            "agent_session_status": (
                self._enum_value(agent.status) if agent else None
            ),
            "agent_session_phase": (
                self._enum_value(agent.current_phase) if agent else None
            ),
            "runtime_handle_id": (
                self._safe_text(agent.runtime_handle_id, 2_000)
                if agent
                else None
            ),
            "native_process_started": bool(
                returned
                and external_snapshot is not None
                and getattr(external_snapshot, "native_process_started", None)
                is True
            ),
            "exception_type": exception_type if raised else None,
            "exception_summary": exception_summary if raised else None,
            "human_recovery_required": status != "returned" or not contract_valid,
            "worker_call_state_indeterminate": False,
            "blocked_reasons": reasons_tuple,
            "worker_reported_git_write_activity": git_activity if returned else False,
            "product_runtime_git_write_allowed": False,
        }
        provisional = ProjectDirectorCrossTaskExactWorkerInvocationOutcome.model_construct(
            **values
        )
        payload = provisional.model_dump(
            mode="python",
            exclude={"worker_invocation_outcome_fingerprint"},
        )
        values["worker_invocation_outcome_fingerprint"] = (
            compute_p24_contract_sha256(payload)
        )
        return ProjectDirectorCrossTaskExactWorkerInvocationOutcome.model_validate(
            values
        )

    @staticmethod
    def _build_outcome_message(
        *,
        outcome: ProjectDirectorCrossTaskExactWorkerInvocationOutcome,
        sequence_no: int,
    ) -> ProjectDirectorMessage:
        return ProjectDirectorMessage(
            id=outcome.exact_worker_invocation_outcome_id,
            session_id=outcome.session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content=(
                f"{_OUTCOME_CONTENT_PREFIX}: "
                f"{outcome.exact_worker_invocation_outcome_id}"
            ),
            sequence_no=sequence_no,
            intent=CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_INTENT,
            related_plan_version_id=outcome.plan_version_id,
            related_project_id=outcome.project_id,
            related_task_id=outcome.next_task_id,
            source=ProjectDirectorMessageSource.SYSTEM,
            source_detail=CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL,
            suggested_actions=[
                {
                    "type": CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_ACTION_TYPE,
                    **outcome.model_dump(mode="json"),
                }
            ],
            requires_confirmation=False,
            risk_level=ProjectDirectorMessageRiskLevel.HIGH,
            forbidden_actions_detected=list(outcome.forbidden_actions),
            token_count=None,
            estimated_cost=None,
            created_at=outcome.created_at,
        )

    def _post_write_validate(
        self,
        message: ProjectDirectorMessage,
        outcome: ProjectDirectorCrossTaskExactWorkerInvocationOutcome,
        graph: _ExactGraph,
    ) -> None:
        validated = ProjectDirectorCrossTaskExactWorkerInvocationOutcome.model_validate(
            outcome.model_dump(mode="python")
        )
        parsed = self._parse_outcome_message(
            message,
            reason="exact_worker_invocation_outcome_persistence_failed",
        )
        if (
            validated != outcome
            or parsed != outcome
            or outcome.worker_invocation_outcome_fingerprint
            != outcome.compute_fingerprint()
        ):
            raise ValueError("persisted exact invocation outcome is invalid")
        self._validate_outcome_history_binding(
            outcome=outcome,
            root=graph.root,
            package=graph.package,
            exact_run_reservation=graph.exact_run_reservation,
            worker_start_reservation=graph.worker_start_reservation,
            claim=graph.claim,
            reason="exact_worker_invocation_outcome_persistence_failed",
        )

    @staticmethod
    def _matching_outcomes(
        history: _History,
        claim: ProjectDirectorCrossTaskExactWorkerInvocationClaim,
    ) -> list[
        tuple[
            ProjectDirectorMessage,
            ProjectDirectorCrossTaskExactWorkerInvocationOutcome,
        ]
    ]:
        replay_key = (
            ProjectDirectorCrossTaskExactWorkerInvocationOutcome
            .compute_worker_invocation_outcome_replay_key(
                continuation_id=claim.continuation_id,
                exact_worker_invocation_claim_id=(
                    claim.exact_worker_invocation_claim_id
                ),
                exact_worker_invocation_claim_token=(
                    claim.worker_invocation_claim_token
                ),
                exact_worker_start_reservation_id=(
                    claim.exact_worker_start_reservation_id
                ),
                next_task_id=claim.next_task_id,
                exact_run_id=claim.exact_run_id,
            )
        )
        return [
            item
            for item in history.invocation_outcomes
            if item[1].worker_invocation_outcome_replay_key == replay_key
        ]

    @staticmethod
    def _outcome_targets_claim(
        outcome: ProjectDirectorCrossTaskExactWorkerInvocationOutcome,
        claim: ProjectDirectorCrossTaskExactWorkerInvocationClaim,
    ) -> bool:
        return (
            outcome.exact_worker_invocation_claim_id
            == claim.exact_worker_invocation_claim_id
            or outcome.exact_worker_invocation_claim_token
            == claim.worker_invocation_claim_token
            or outcome.exact_worker_start_reservation_id
            == claim.exact_worker_start_reservation_id
            or outcome.exact_run_reservation_id == claim.exact_run_reservation_id
            or outcome.exact_run_id == claim.exact_run_id
        )

    @classmethod
    def _message_targets_claim(
        cls,
        message: ProjectDirectorMessage,
        claim: ProjectDirectorCrossTaskExactWorkerInvocationClaim,
    ) -> bool:
        outcome_replay_key = (
            ProjectDirectorCrossTaskExactWorkerInvocationOutcome
            .compute_worker_invocation_outcome_replay_key(
                continuation_id=claim.continuation_id,
                exact_worker_invocation_claim_id=(
                    claim.exact_worker_invocation_claim_id
                ),
                exact_worker_invocation_claim_token=(
                    claim.worker_invocation_claim_token
                ),
                exact_worker_start_reservation_id=(
                    claim.exact_worker_start_reservation_id
                ),
                next_task_id=claim.next_task_id,
                exact_run_id=claim.exact_run_id,
            )
        )
        return any(
            cls._raw_action_id_matches(message, field_name, expected)
            for field_name, expected in (
                (
                    "exact_worker_invocation_claim_id",
                    claim.exact_worker_invocation_claim_id,
                ),
                (
                    "exact_worker_invocation_claim_token",
                    claim.worker_invocation_claim_token,
                ),
                (
                    "exact_worker_start_reservation_id",
                    claim.exact_worker_start_reservation_id,
                ),
                (
                    "exact_run_reservation_id",
                    claim.exact_run_reservation_id,
                ),
                ("exact_run_id", claim.exact_run_id),
                ("worker_invocation_outcome_replay_key", outcome_replay_key),
            )
        )

    @staticmethod
    def _raw_action_id_matches(
        message: ProjectDirectorMessage,
        field_name: str,
        expected: Any,
    ) -> bool:
        return (
            len(message.suggested_actions) == 1
            and isinstance(message.suggested_actions[0], dict)
            and str(message.suggested_actions[0].get(field_name))
            == str(expected)
        )

    @staticmethod
    def _worker_git_activity_state(
        result: WorkerRunResult,
    ) -> tuple[bool, bool]:
        activity = False
        fields_valid = True
        for field_name in _GIT_ACTIVITY_FIELDS:
            value = getattr(result, field_name, None)
            if value is not None and not isinstance(value, bool):
                fields_valid = False
            elif value is True:
                activity = True
        for snapshot_name in _GIT_ACTIVITY_SNAPSHOT_NAMES:
            snapshot = getattr(result, snapshot_name, None)
            if snapshot is None:
                continue
            for field_name in _GIT_ACTIVITY_SNAPSHOT_FIELDS:
                value = getattr(snapshot, field_name, None)
                if value is not None and not isinstance(value, bool):
                    fields_valid = False
                elif value is True:
                    activity = True
        return activity, fields_valid

    @classmethod
    def _safe_exception_summary(cls, exc: Exception) -> str:
        return cls._safe_text(
            exc,
            2_000,
            fallback="Worker raised an exception; details were redacted.",
        ) or "Worker raised an exception; details were redacted."

    @staticmethod
    def _safe_text(
        value: Any,
        max_length: int,
        *,
        fallback: str | None = None,
    ) -> str | None:
        if value is None:
            return fallback
        try:
            text = str(value)
        except Exception:
            return fallback
        text = text.replace("\r", " ").replace("\n", " ").strip()
        text = _SENSITIVE_ASSIGNMENT.sub("[REDACTED SENSITIVE VALUE]", text)
        text = _BEARER_VALUE.sub("[REDACTED BEARER VALUE]", text)
        text = " ".join(text.split()).strip()
        return text[:max_length].strip() or fallback

    @classmethod
    def _safe_tuple(
        cls,
        values: Any,
        max_length: int,
    ) -> tuple[str, ...]:
        if not isinstance(values, (list, tuple)):
            return ()
        normalized: list[str] = []
        for value in values:
            item = cls._safe_text(value, max_length)
            if item is not None:
                normalized.append(item)
        return tuple(normalized)

    @staticmethod
    def _safe_role(value: Any) -> ProjectRoleCode | None:
        if value is None:
            return None
        try:
            return ProjectRoleCode(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _enum_value(value: Any) -> str | None:
        if value is None:
            return None
        enum_value = getattr(value, "value", value)
        return str(enum_value).strip() or None

    @staticmethod
    def _dedupe_reasons(
        reasons: tuple[CrossTaskExactWorkerInvocationOutcomeBlockedReason, ...],
    ) -> tuple[CrossTaskExactWorkerInvocationOutcomeBlockedReason, ...]:
        return tuple(dict.fromkeys(reasons))

    @staticmethod
    def _claim_reason(
        reason: CrossTaskExactWorkerInvocationOutcomeBlockedReason,
    ) -> str:
        reverse = {
            "exact_worker_invocation_outcome_history_invalid": (
                "exact_worker_invocation_claim_history_invalid"
            ),
            "exact_worker_invocation_outcome_history_conflict": (
                "exact_worker_invocation_claim_history_conflict"
            ),
            "exact_worker_invocation_outcome_replay_conflict": (
                "exact_worker_invocation_claim_replay_conflict"
            ),
            "exact_worker_invocation_outcome_package_invalid": (
                "exact_worker_invocation_claim_package_invalid"
            ),
            "exact_worker_invocation_outcome_exact_run_reservation_invalid": (
                "exact_worker_invocation_claim_exact_run_reservation_invalid"
            ),
            "exact_worker_invocation_outcome_worker_start_reservation_invalid": (
                "exact_worker_invocation_claim_worker_start_reservation_invalid"
            ),
            "exact_worker_invocation_outcome_claim_invalid": (
                "exact_worker_invocation_claim_task_missing"
            ),
        }
        return reverse.get(
            reason,
            "exact_worker_invocation_claim_history_invalid",
        )

    @classmethod
    def _map_claim_reasons(
        cls,
        reasons: tuple[str, ...],
    ) -> CrossTaskExactWorkerInvocationOutcomeBlockedReason:
        if not reasons:
            return "exact_worker_invocation_outcome_claim_invalid"
        return cls._map_claim_reason(reasons[0])

    @staticmethod
    def _map_claim_reason(
        reason: str,
    ) -> CrossTaskExactWorkerInvocationOutcomeBlockedReason:
        direct = {
            "exact_worker_invocation_claim_history_invalid": (
                "exact_worker_invocation_outcome_history_invalid"
            ),
            "exact_worker_invocation_claim_history_conflict": (
                "exact_worker_invocation_outcome_history_conflict"
            ),
            "exact_worker_invocation_claim_replay_conflict": (
                "exact_worker_invocation_outcome_replay_conflict"
            ),
            "exact_worker_invocation_claim_package_invalid": (
                "exact_worker_invocation_outcome_package_invalid"
            ),
            "exact_worker_invocation_claim_exact_run_reservation_invalid": (
                "exact_worker_invocation_outcome_exact_run_reservation_invalid"
            ),
            "exact_worker_invocation_claim_worker_start_reservation_invalid": (
                "exact_worker_invocation_outcome_worker_start_reservation_invalid"
            ),
            "exact_worker_invocation_claim_worker_authority_conflict": (
                "exact_worker_invocation_outcome_worker_authority_conflict"
            ),
            "exact_worker_invocation_claim_git_boundary_violation": (
                "exact_worker_invocation_outcome_git_boundary_violation"
            ),
            "exact_worker_invocation_claim_persistence_failed": (
                "exact_worker_invocation_outcome_persistence_failed"
            ),
        }
        return direct.get(
            reason,
            "exact_worker_invocation_outcome_claim_invalid",
        )

    @staticmethod
    def _replayed_result(
        outcome: ProjectDirectorCrossTaskExactWorkerInvocationOutcome,
    ) -> ProjectDirectorCrossTaskExactWorkerInvocationOutcomeResult:
        return ProjectDirectorCrossTaskExactWorkerInvocationOutcomeResult(
            status="outcome_replayed",
            exact_worker_invocation_claim_id=(
                outcome.exact_worker_invocation_claim_id
            ),
            outcome=outcome,
            blocked_reasons=(),
            outcome_recorded=False,
            outcome_replayed=True,
            resumed_from_existing_outcome=True,
            recovery_required=outcome.human_recovery_required,
            automatic_worker_call_allowed=False,
            worker_call_attempted=outcome.worker_call_attempted,
            worker_call_state_indeterminate=False,
            product_runtime_git_write_allowed=False,
        )

    @staticmethod
    def _recovery_result(
        *,
        claim_id: UUID,
        reasons: tuple[CrossTaskExactWorkerInvocationOutcomeBlockedReason, ...],
    ) -> ProjectDirectorCrossTaskExactWorkerInvocationOutcomeResult:
        return ProjectDirectorCrossTaskExactWorkerInvocationOutcomeResult(
            status="recovery_required",
            exact_worker_invocation_claim_id=claim_id,
            outcome=None,
            blocked_reasons=tuple(dict.fromkeys(reasons)),
            outcome_recorded=False,
            outcome_replayed=False,
            resumed_from_existing_outcome=False,
            recovery_required=True,
            automatic_worker_call_allowed=False,
            worker_call_attempted=None,
            worker_call_state_indeterminate=True,
            product_runtime_git_write_allowed=False,
        )

    @staticmethod
    def _blocked_result(
        *,
        reason: CrossTaskExactWorkerInvocationOutcomeBlockedReason,
        claim_id: UUID | None = None,
    ) -> ProjectDirectorCrossTaskExactWorkerInvocationOutcomeResult:
        return ProjectDirectorCrossTaskExactWorkerInvocationOutcomeResult(
            status="blocked",
            exact_worker_invocation_claim_id=claim_id,
            outcome=None,
            blocked_reasons=(reason,),
            outcome_recorded=False,
            outcome_replayed=False,
            resumed_from_existing_outcome=False,
            recovery_required=False,
            automatic_worker_call_allowed=False,
            worker_call_attempted=False,
            worker_call_state_indeterminate=False,
            product_runtime_git_write_allowed=False,
        )

    def _require_shared_session(self) -> None:
        shared_session = self._message_repository._session
        dependencies = (
            self._task_repository.session,
            self._run_repository.session,
            self._agent_session_repository.session,
            self._task_worker.session,
            self._task_worker.task_repository.session,
            self._task_worker.run_repository.session,
            (
                self._task_worker.agent_conversation_service
                .agent_session_repository.session
            ),
            self._claim_service._message_repository._session,
            self._claim_service._task_repository.session,
            self._claim_service._run_repository.session,
            self._claim_service._agent_session_repository.session,
        )
        if any(candidate is not shared_session for candidate in dependencies):
            raise ValueError(
                "P24-E4B dependencies must share one SQLAlchemy Session"
            )


__all__ = (
    "ProjectDirectorCrossTaskExactWorkerInvocationOutcomeService",
)
