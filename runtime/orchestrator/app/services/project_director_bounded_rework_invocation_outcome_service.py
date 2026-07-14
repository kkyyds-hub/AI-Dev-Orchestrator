"""Execute one exact P25 bounded rework Claim and persist one durable Outcome."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.domain._base import utc_now
from app.domain.project_director_bounded_rework_attempt_reservation import (
    ProjectDirectorBoundedReworkAttemptReservation,
)
from app.domain.project_director_bounded_rework_contract import (
    BoundedReworkBlockedReason,
    compute_p25_contract_sha256,
    path_is_within_scope,
    paths_overlap,
)
from app.domain.project_director_bounded_rework_instruction_package import (
    ProjectDirectorBoundedReworkInstructionPackage,
)
from app.domain.project_director_bounded_rework_invocation_claim import (
    ProjectDirectorBoundedReworkInvocationClaim,
)
from app.domain.project_director_bounded_rework_invocation_outcome import (
    BoundedReworkGitActivityKind,
    ProjectDirectorBoundedReworkInvocationOutcome,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.external_executors.project_director_bounded_rework_executor import (
    ProjectDirectorBoundedReworkExecutorCorrection,
    ProjectDirectorBoundedReworkExecutorFinding,
    ProjectDirectorBoundedReworkExecutorProtocol,
    ProjectDirectorBoundedReworkExecutorRequest,
    ProjectDirectorBoundedReworkExecutorResult,
    ProjectDirectorBoundedReworkExecutorVerificationRequirement,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.services.project_director_bounded_rework_invocation_claim_service import (
    BoundedReworkWorkspaceInspectionError,
    BoundedReworkWorkspaceSnapshot,
    ProjectDirectorBoundedReworkInvocationClaimService,
    RevalidatedPersistedBoundedReworkInvocationClaim,
)


P25_BOUNDED_REWORK_INVOCATION_OUTCOME_SOURCE_DETAIL = (
    "p25_bounded_rework_invocation_outcome_recorded"
)
P25_BOUNDED_REWORK_INVOCATION_OUTCOME_ACTION_TYPE = (
    "p25_bounded_rework_invocation_outcome_record"
)
P25_BOUNDED_REWORK_INVOCATION_OUTCOME_INTENT = (
    "bounded_rework_invocation_outcome"
)

_CANDIDATE_MANIFEST_SCHEMA_VERSION = "p25-f-candidate-manifest-identity.v1"
_REPOSITORY_STATUS_SCHEMA_VERSION = "p25-f-repository-status.v1"
_GIT_CONTROL_SCHEMA_VERSION = "p25-f-git-control.v1"
_INTERNAL_CONTROL_NAMES = frozenset(
    {".git", ".ai-project-director", ".ai-dev-orchestrator", ".orchestrator"}
)
_MAX_GIT_STATUS_BYTES = 1024 * 1024
_MAX_GIT_CONTROL_ENTRIES = 512
_MAX_GIT_CONTROL_FILE_BYTES = 1024 * 1024
_MAX_GIT_CONTROL_TOTAL_BYTES = 4 * 1024 * 1024
_GIT_TIMEOUT_SECONDS = 5
_GIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")

_OUTCOME_FALSE_BOUNDARIES = (
    "product_runtime_git_write_allowed=false",
    "main_project_write_allowed=false",
    "git_add_allowed=false",
    "git_commit_allowed=false",
    "git_push_allowed=false",
    "branch_operation_allowed=false",
    "pull_request_allowed=false",
    "merge_allowed=false",
    "ci_trigger_allowed=false",
)

OutcomeExecutionStatus = Literal[
    "outcome_recorded",
    "outcome_replayed",
    "blocked",
]


@dataclass(frozen=True, slots=True)
class ExecutedProjectDirectorBoundedReworkInvocation:
    status: OutcomeExecutionStatus
    claim: ProjectDirectorBoundedReworkInvocationClaim | None
    claim_message: ProjectDirectorMessage | None
    outcome: ProjectDirectorBoundedReworkInvocationOutcome | None
    outcome_message: ProjectDirectorMessage | None
    blocked_reasons: tuple[BoundedReworkBlockedReason, ...]
    recovery_required: bool = False
    human_escalation_required: bool = False


@dataclass(frozen=True, slots=True)
class _RepositorySnapshot:
    head_sha: str
    status_fingerprint: str
    git_control_fingerprint: str


@dataclass(frozen=True, slots=True)
class _ExecutionObservation:
    before_workspace: BoundedReworkWorkspaceSnapshot
    before_repository: _RepositorySnapshot
    after_workspace: BoundedReworkWorkspaceSnapshot | None
    after_repository: _RepositorySnapshot | None
    executor_result: ProjectDirectorBoundedReworkExecutorResult | None
    executor_exception_type: str | None
    executor_result_invalid: bool
    executor_started: bool
    pre_call_error: BoundedReworkBlockedReason | None = None
    inspection_error: BoundedReworkBlockedReason | None = None
    inspection_indeterminate: bool = False
    repository_inspection_indeterminate: bool = False


class _Blocked(RuntimeError):
    def __init__(self, reason: BoundedReworkBlockedReason) -> None:
        self.reason = reason
        super().__init__(reason)


class ProjectDirectorBoundedReworkInvocationOutcomeService:
    """Coordinate Claim, external execution, and separate Outcome persistence."""

    def __init__(
        self,
        *,
        message_repository: ProjectDirectorMessageRepository,
        claim_service: ProjectDirectorBoundedReworkInvocationClaimService,
        bounded_rework_executor: ProjectDirectorBoundedReworkExecutorProtocol,
    ) -> None:
        self._message_repository = message_repository
        self._claim_service = claim_service
        self._bounded_rework_executor = bounded_rework_executor
        if claim_service._message_repository is not message_repository:
            raise ValueError("P25-F dependencies must share one message repository")
        if not isinstance(
            bounded_rework_executor,
            ProjectDirectorBoundedReworkExecutorProtocol,
        ):
            raise TypeError("P25-F requires a bounded rework executor adapter")

    def execute_bounded_rework_from_reservation(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_reservation_message_id: UUID,
    ) -> ExecutedProjectDirectorBoundedReworkInvocation:
        """Execute only a Claim created by this coordinator invocation."""

        phase_one = self._claim_service.claim_bounded_rework_invocation(
            session_id=session_id,
            source_task_id=source_task_id,
            source_reservation_message_id=source_reservation_message_id,
        )
        if phase_one.status == "claim_replayed":
            return self._replay_claim_outcome(
                session_id=session_id,
                source_task_id=source_task_id,
                claim=phase_one.claim,
                claim_message=phase_one.message,
            )
        if phase_one.status != "claim_claimed":
            historical = self._claim_service.revalidate_persisted_bounded_rework_invocation_from_reservation(
                session_id=session_id,
                source_task_id=source_task_id,
                source_reservation_message_id=source_reservation_message_id,
            )
            self._rollback_read_transaction()
            if (
                not historical.blocked_reasons
                and historical.claim is not None
                and historical.message is not None
                and historical.outcome is not None
                and historical.outcome_message is not None
            ):
                return ExecutedProjectDirectorBoundedReworkInvocation(
                    status="outcome_replayed",
                    claim=historical.claim,
                    claim_message=historical.message,
                    outcome=historical.outcome,
                    outcome_message=historical.outcome_message,
                    blocked_reasons=(),
                    recovery_required=historical.outcome.recovery_required,
                    human_escalation_required=(
                        historical.outcome.human_escalation_required
                    ),
                )
            if (
                not historical.blocked_reasons
                and historical.claim is not None
                and historical.outcome is None
            ):
                return self._blocked(
                    "claim_without_outcome",
                    claim=historical.claim,
                    claim_message=historical.message,
                )
            return ExecutedProjectDirectorBoundedReworkInvocation(
                status="blocked",
                claim=phase_one.claim,
                claim_message=phase_one.message,
                outcome=None,
                outcome_message=None,
                blocked_reasons=phase_one.blocked_reasons,
                recovery_required=bool(
                    set(phase_one.blocked_reasons)
                    & {
                        "claim_without_outcome",
                        "history_invalid",
                        "persistence_failed",
                        "git_boundary_violation",
                        "human_escalation_required",
                    }
                ),
                human_escalation_required=bool(
                    set(phase_one.blocked_reasons)
                    & {"git_boundary_violation", "human_escalation_required"}
                ),
            )
        claim = phase_one.claim
        claim_message = phase_one.message
        if claim is None or claim_message is None:
            return self._blocked("history_invalid")

        current = self._claim_service.revalidate_persisted_bounded_rework_invocation_claim(
            session_id=session_id,
            source_task_id=source_task_id,
            source_claim_message_id=claim.claim_id,
        )
        if (
            current.blocked_reasons
            or current.claim != claim
            or current.message != claim_message
            or current.outcome is not None
            or current.reservation is None
            or current.package is None
        ):
            self._rollback_read_transaction()
            return self._blocked(
                current.blocked_reasons[0]
                if current.blocked_reasons
                else "history_invalid",
                claim=claim,
                claim_message=claim_message,
            )

        try:
            before_workspace = (
                self._claim_service.inspect_revalidated_bounded_rework_workspace(
                    current
                )
            )
            before_repository = self._snapshot_repository(current.package)
        except (OSError, RuntimeError, TypeError, ValueError, subprocess.SubprocessError):
            self._rollback_read_transaction()
            return self._persist_pre_call_outcome(
                current=current,
                before_workspace=self._claim_snapshot(claim),
                pre_call_error="workspace_invalid",
            )

        pre_call_error = self._pre_call_error(
            claim=claim,
            package=current.package,
            workspace=before_workspace,
            repository=before_repository,
        )
        if pre_call_error is not None:
            self._rollback_read_transaction()
            return self._persist_pre_call_outcome(
                current=current,
                before_workspace=before_workspace,
                before_repository=before_repository,
                pre_call_error=pre_call_error,
            )

        try:
            request = self._build_executor_request(
                claim=claim,
                package=current.package,
            )
        except (TypeError, ValueError, ValidationError):
            self._rollback_read_transaction()
            return self._persist_pre_call_outcome(
                current=current,
                before_workspace=before_workspace,
                before_repository=before_repository,
                pre_call_error="history_invalid",
            )

        # End SQLAlchemy's read autobegin before crossing the external boundary.
        self._rollback_read_transaction()
        executor_result: ProjectDirectorBoundedReworkExecutorResult | None = None
        executor_exception_type: str | None = None
        executor_result_invalid = False
        try:
            raw_result: Any = self._bounded_rework_executor.execute_bounded_rework(
                request
            )
        except Exception as exc:
            executor_exception_type = type(exc).__name__
        else:
            try:
                executor_result = ProjectDirectorBoundedReworkExecutorResult.model_validate(
                    raw_result
                )
            except (TypeError, ValueError, ValidationError):
                executor_result_invalid = True
        finally:
            self._rollback_read_transaction()

        after_workspace: BoundedReworkWorkspaceSnapshot | None = None
        after_repository: _RepositorySnapshot | None = None
        inspection_indeterminate = False
        inspection_error: BoundedReworkBlockedReason | None = None
        try:
            after_workspace = (
                self._claim_service.inspect_revalidated_bounded_rework_workspace(
                    current,
                    observe_out_of_scope_files=True,
                )
            )
        except BoundedReworkWorkspaceInspectionError as exc:
            inspection_error = exc.reason
            inspection_indeterminate = True
        except (OSError, RuntimeError, TypeError, ValueError, subprocess.SubprocessError):
            inspection_indeterminate = True
        repository_inspection_indeterminate = False
        try:
            after_repository = self._snapshot_repository(current.package)
        except (OSError, RuntimeError, TypeError, ValueError, subprocess.SubprocessError):
            repository_inspection_indeterminate = True

        observation = _ExecutionObservation(
            before_workspace=before_workspace,
            before_repository=before_repository,
            after_workspace=after_workspace,
            after_repository=after_repository,
            executor_result=executor_result,
            executor_exception_type=executor_exception_type,
            executor_result_invalid=executor_result_invalid,
            executor_started=True,
            inspection_error=inspection_error,
            inspection_indeterminate=inspection_indeterminate,
            repository_inspection_indeterminate=(
                repository_inspection_indeterminate
            ),
        )
        return self._persist_outcome(
            current=current,
            observation=observation,
        )

    def _replay_claim_outcome(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        claim: ProjectDirectorBoundedReworkInvocationClaim | None,
        claim_message: ProjectDirectorMessage | None,
    ) -> ExecutedProjectDirectorBoundedReworkInvocation:
        if claim is None or claim_message is None:
            return self._blocked("history_invalid")
        current = self._claim_service.revalidate_persisted_bounded_rework_invocation_claim_for_outcome_persistence(
            session_id=session_id,
            source_task_id=source_task_id,
            source_claim_message_id=claim.claim_id,
        )
        self._rollback_read_transaction()
        if current.blocked_reasons:
            return self._blocked(
                current.blocked_reasons[0],
                claim=claim,
                claim_message=claim_message,
            )
        if (
            current.claim != claim
            or current.message != claim_message
            or current.outcome is None
            or current.outcome_message is None
        ):
            return self._blocked(
                "history_invalid",
                claim=claim,
                claim_message=claim_message,
            )
        return ExecutedProjectDirectorBoundedReworkInvocation(
            status="outcome_replayed",
            claim=claim,
            claim_message=claim_message,
            outcome=current.outcome,
            outcome_message=current.outcome_message,
            blocked_reasons=(),
            recovery_required=current.outcome.recovery_required,
            human_escalation_required=(
                current.outcome.human_escalation_required
            ),
        )

    def _persist_pre_call_outcome(
        self,
        *,
        current: RevalidatedPersistedBoundedReworkInvocationClaim,
        before_workspace: BoundedReworkWorkspaceSnapshot,
        pre_call_error: BoundedReworkBlockedReason,
        before_repository: _RepositorySnapshot | None = None,
    ) -> ExecutedProjectDirectorBoundedReworkInvocation:
        repository = before_repository or _RepositorySnapshot(
            head_sha="0" * 40,
            status_fingerprint="0" * 64,
            git_control_fingerprint="0" * 64,
        )
        return self._persist_outcome(
            current=current,
            observation=_ExecutionObservation(
                before_workspace=before_workspace,
                before_repository=repository,
                after_workspace=None,
                after_repository=None,
                executor_result=None,
                executor_exception_type=None,
                executor_result_invalid=False,
                executor_started=False,
                pre_call_error=pre_call_error,
            ),
        )

    def _persist_outcome(
        self,
        *,
        current: RevalidatedPersistedBoundedReworkInvocationClaim,
        observation: _ExecutionObservation,
    ) -> ExecutedProjectDirectorBoundedReworkInvocation:
        claim = current.claim
        claim_message = current.message
        if claim is None or claim_message is None:
            return self._blocked("history_invalid")
        self._rollback_read_transaction()
        try:
            with self._message_repository.sqlite_immediate_transaction():
                if observation.executor_started:
                    final = self._claim_service.revalidate_persisted_bounded_rework_invocation_claim_for_outcome_persistence(
                        session_id=claim.authority.session_id,
                        source_task_id=claim.exact_task_id,
                        source_claim_message_id=claim.claim_id,
                    )
                else:
                    final = self._claim_service.revalidate_persisted_bounded_rework_invocation_claim(
                        session_id=claim.authority.session_id,
                        source_task_id=claim.exact_task_id,
                        source_claim_message_id=claim.claim_id,
                    )
                if final.blocked_reasons:
                    raise _Blocked(final.blocked_reasons[0])
                if final.outcome is not None:
                    if final.outcome_message is None:
                        raise _Blocked("history_invalid")
                    return ExecutedProjectDirectorBoundedReworkInvocation(
                        status="outcome_replayed",
                        claim=claim,
                        claim_message=claim_message,
                        outcome=final.outcome,
                        outcome_message=final.outcome_message,
                        blocked_reasons=(),
                        recovery_required=final.outcome.recovery_required,
                        human_escalation_required=(
                            final.outcome.human_escalation_required
                        ),
                    )
                if (
                    final.claim != claim
                    or final.message != claim_message
                    or final.reservation != current.reservation
                    or final.package != current.package
                ):
                    raise _Blocked("history_invalid")

                final_observation = self._finalize_observation(
                    final=final,
                    observation=observation,
                )
                outcome = self._build_outcome(
                    current=final,
                    observation=final_observation,
                )
                outcome_message = self._build_outcome_message(outcome)
                persisted = self._message_repository.create(outcome_message)
                if persisted != outcome_message:
                    raise _Blocked("persistence_failed")
                return ExecutedProjectDirectorBoundedReworkInvocation(
                    status="outcome_recorded",
                    claim=claim,
                    claim_message=claim_message,
                    outcome=outcome,
                    outcome_message=persisted,
                    blocked_reasons=(),
                    recovery_required=outcome.recovery_required,
                    human_escalation_required=(
                        outcome.human_escalation_required
                    ),
                )
        except _Blocked as exc:
            return self._blocked(
                exc.reason,
                claim=claim,
                claim_message=claim_message,
            )
        except (SQLAlchemyError, OSError, RuntimeError, TypeError, ValueError, ValidationError):
            self._message_repository._session.rollback()
            return self._blocked(
                "persistence_failed",
                claim=claim,
                claim_message=claim_message,
            )

    def _finalize_observation(
        self,
        *,
        final: RevalidatedPersistedBoundedReworkInvocationClaim,
        observation: _ExecutionObservation,
    ) -> _ExecutionObservation:
        if not observation.executor_started:
            return observation
        final_workspace: BoundedReworkWorkspaceSnapshot | None = None
        final_repository: _RepositorySnapshot | None = None
        try:
            final_workspace = (
                self._claim_service.inspect_revalidated_bounded_rework_workspace(
                    final,
                    observe_out_of_scope_files=True,
                )
            )
        except BoundedReworkWorkspaceInspectionError as exc:
            return _ExecutionObservation(
                before_workspace=observation.before_workspace,
                before_repository=observation.before_repository,
                after_workspace=observation.after_workspace,
                after_repository=observation.after_repository,
                executor_result=observation.executor_result,
                executor_exception_type=observation.executor_exception_type,
                executor_result_invalid=observation.executor_result_invalid,
                executor_started=observation.executor_started,
                pre_call_error=observation.pre_call_error,
                inspection_error=exc.reason,
                inspection_indeterminate=True,
                repository_inspection_indeterminate=(
                    observation.repository_inspection_indeterminate
                ),
            )
        except (OSError, RuntimeError, TypeError, ValueError, subprocess.SubprocessError):
            return _ExecutionObservation(
                before_workspace=observation.before_workspace,
                before_repository=observation.before_repository,
                after_workspace=observation.after_workspace,
                after_repository=observation.after_repository,
                executor_result=observation.executor_result,
                executor_exception_type=observation.executor_exception_type,
                executor_result_invalid=observation.executor_result_invalid,
                executor_started=observation.executor_started,
                pre_call_error=observation.pre_call_error,
                inspection_error=observation.inspection_error,
                inspection_indeterminate=True,
                repository_inspection_indeterminate=(
                    observation.repository_inspection_indeterminate
                ),
            )
        repository_inspection_indeterminate = (
            observation.repository_inspection_indeterminate
        )
        effective_after_repository = observation.after_repository
        try:
            if final.package is None:
                raise ValueError("missing revalidated package")
            final_repository = self._snapshot_repository(final.package)
        except (OSError, RuntimeError, TypeError, ValueError, subprocess.SubprocessError):
            repository_inspection_indeterminate = True
        else:
            effective_after_repository = final_repository
        workspace_changed_during_persistence = bool(
            observation.after_workspace is not None
            and observation.after_workspace != final_workspace
        )
        repository_changed_during_persistence = bool(
            final_repository is not None
            and observation.after_repository is not None
            and final_repository != observation.after_repository
        )
        repository_final_state_unknown = final_repository is None
        changed_during_persistence = bool(
            workspace_changed_during_persistence
            or repository_changed_during_persistence
        )
        return _ExecutionObservation(
            before_workspace=observation.before_workspace,
            before_repository=observation.before_repository,
            after_workspace=final_workspace,
            after_repository=effective_after_repository,
            executor_result=observation.executor_result,
            executor_exception_type=observation.executor_exception_type,
            executor_result_invalid=observation.executor_result_invalid,
            executor_started=observation.executor_started,
            pre_call_error=observation.pre_call_error,
            inspection_error=observation.inspection_error,
            inspection_indeterminate=(
                observation.inspection_indeterminate or changed_during_persistence
            ),
            repository_inspection_indeterminate=(
                repository_inspection_indeterminate
                or repository_final_state_unknown
            ),
        )

    def _build_outcome(
        self,
        *,
        current: RevalidatedPersistedBoundedReworkInvocationClaim,
        observation: _ExecutionObservation,
    ) -> ProjectDirectorBoundedReworkInvocationOutcome:
        claim = current.claim
        reservation = current.reservation
        package = current.package
        if claim is None or reservation is None or package is None:
            raise _Blocked("history_invalid")

        after_workspace = observation.after_workspace
        observed_paths = self._changed_paths(
            observation.before_workspace,
            after_workspace,
        ) if after_workspace is not None else ()
        result = observation.executor_result
        declared_paths = result.declared_changed_paths if result is not None else ()
        git_kinds = self._git_activity_kinds(observation)
        internal_change = any(self._is_internal_path(path) for path in observed_paths)
        scope_escape = bool(
            result is not None
            and (result.workspace_escape or result.main_project_write)
        )
        scope_invalid = any(
            not any(path_is_within_scope(path, allowed) for allowed in package.allowed_scope_paths)
            or any(paths_overlap(path, forbidden) for forbidden in package.forbidden_scope_paths)
            for path in observed_paths
        )
        manifest_only_change = bool(
            after_workspace is not None
            and observation.before_workspace.manifest_fingerprint
            != after_workspace.manifest_fingerprint
            and not observed_paths
        )
        side_effect_indeterminate = bool(
            observation.inspection_indeterminate
            or observation.repository_inspection_indeterminate
            or observation.after_workspace is None
            or observation.after_repository is None
        )

        outcome_status: str
        safe_error_code: str | None = None
        redacted_error_summary: str | None = None
        executor_result_valid = False
        recovery_required = True
        human_escalation_required = False
        scope_validation_status = "indeterminate"
        side_effect_state = "indeterminate"
        persisted_declared_paths: tuple[str, ...] = ()
        persisted_observed_paths: tuple[str, ...] = ()

        if observation.pre_call_error is not None:
            outcome_status = "recovery_required"
            safe_error_code = observation.pre_call_error
            redacted_error_summary = "P25 pre-call validation did not authorize execution"
            side_effect_state = "none"
        elif git_kinds:
            outcome_status = "human_escalation_required"
            safe_error_code = "git_boundary_violation"
            redacted_error_summary = "Git or repository control activity was detected"
            human_escalation_required = True
            scope_validation_status = "invalid"
            side_effect_state = (
                "indeterminate"
                if side_effect_indeterminate
                else "observed" if observed_paths else "none"
            )
        elif (
            internal_change
            or scope_escape
            or scope_invalid
            or manifest_only_change
            or observation.inspection_error
            in {"scope_invalid", "workspace_invalid"}
        ):
            outcome_status = "human_escalation_required"
            safe_error_code = (
                "workspace_invalid"
                if internal_change
                or scope_escape
                or manifest_only_change
                or observation.inspection_error == "workspace_invalid"
                else "scope_invalid"
            )
            redacted_error_summary = "Workspace or bounded scope control was violated"
            human_escalation_required = True
            scope_validation_status = "invalid"
            side_effect_state = "observed" if observed_paths else "indeterminate"
        elif observation.inspection_indeterminate or after_workspace is None:
            outcome_status = "recovery_required"
            safe_error_code = "workspace_invalid"
            redacted_error_summary = "Post-execution inspection was indeterminate"
        elif observation.executor_exception_type is not None:
            outcome_status = "raised"
            safe_error_code = "executor_raised"
            redacted_error_summary = (
                f"{observation.executor_exception_type}: bounded rework executor raised"
            )
        elif observation.executor_result_invalid or result is None:
            outcome_status = "invalid_result"
            safe_error_code = "execution_result_invalid"
            redacted_error_summary = "Bounded rework executor returned an invalid contract"
        elif declared_paths != observed_paths:
            outcome_status = "invalid_result"
            safe_error_code = "execution_result_invalid"
            redacted_error_summary = "Declared and observed workspace changes did not match"
            scope_validation_status = "invalid"
            side_effect_state = "observed" if observed_paths else "indeterminate"
        else:
            outcome_status = "returned"
            executor_result_valid = True
            recovery_required = False
            scope_validation_status = "valid"
            side_effect_state = "observed" if observed_paths else "none"

        can_persist_changed_paths = bool(
            observed_paths
            and declared_paths
            and not observation.inspection_indeterminate
            and after_workspace is not None
        )
        if can_persist_changed_paths:
            persisted_declared_paths = declared_paths
            persisted_observed_paths = observed_paths
        elif observed_paths:
            side_effect_state = "indeterminate"
            if outcome_status == "returned":
                outcome_status = "invalid_result"
                executor_result_valid = False
                recovery_required = True
                safe_error_code = "execution_result_invalid"
                redacted_error_summary = "Workspace changes could not be represented safely"

        candidate_files_changed = bool(persisted_observed_paths)
        candidate_manifest_id = uuid4() if candidate_files_changed else None
        candidate_manifest_fingerprint = None
        if candidate_manifest_id is not None and after_workspace is not None:
            candidate_manifest_fingerprint = self._candidate_manifest_fingerprint(
                candidate_manifest_id=candidate_manifest_id,
                claim=claim,
                reservation=reservation,
                package=package,
                after_workspace=after_workspace,
                observed_paths=persisted_observed_paths,
            )

        values = {
            "outcome_id": uuid4(),
            "outcome_replay_key": ProjectDirectorBoundedReworkInvocationOutcome.compute_outcome_replay_key(
                claim_id=claim.claim_id,
                claim_token=claim.claim_token,
                reservation_id=reservation.reservation_id,
                package_id=package.package_id,
                exact_task_id=claim.exact_task_id,
                exact_run_id=claim.exact_run_id,
            ),
            "created_at": utc_now(),
            "outcome_status": outcome_status,
            "claim_id": claim.claim_id,
            "claim_fingerprint": claim.claim_fingerprint,
            "claim_token": claim.claim_token,
            "reservation_id": reservation.reservation_id,
            "reservation_fingerprint": reservation.reservation_fingerprint,
            "package_id": package.package_id,
            "package_fingerprint": package.package_fingerprint,
            "authority": claim.authority,
            "exact_task_id": claim.exact_task_id,
            "exact_run_id": claim.exact_run_id,
            "rework_attempt_index": claim.rework_attempt_index,
            "rework_attempt_limit": claim.rework_attempt_limit,
            "invocation_ordinal": claim.invocation_ordinal,
            "executor_attempted": observation.executor_started,
            "executor_started": observation.executor_started,
            "executor_returned": bool(
                observation.executor_started
                and observation.executor_exception_type is None
            ),
            "executor_raised": observation.executor_exception_type is not None,
            "executor_result_valid": executor_result_valid,
            "safe_error_code": safe_error_code,
            "redacted_error_summary": redacted_error_summary,
            "workspace_before_manifest_fingerprint": claim.workspace_before_manifest_fingerprint,
            "workspace_before_content_fingerprint": claim.workspace_before_content_fingerprint,
            "workspace_after_manifest_fingerprint": (
                after_workspace.manifest_fingerprint if after_workspace else None
            ),
            "workspace_after_content_fingerprint": (
                after_workspace.content_fingerprint if after_workspace else None
            ),
            "declared_changed_paths": persisted_declared_paths,
            "observed_changed_paths": persisted_observed_paths,
            "scope_validation_status": scope_validation_status,
            "git_activity_detected": bool(git_kinds),
            "git_activity_kinds": git_kinds,
            "side_effect_state": side_effect_state,
            "candidate_manifest_id": candidate_manifest_id,
            "candidate_manifest_fingerprint": candidate_manifest_fingerprint,
            "candidate_files_changed": candidate_files_changed,
            "recovery_required": recovery_required,
            "human_escalation_required": human_escalation_required,
            "product_runtime_git_write_allowed": False,
            "main_project_write_allowed": False,
            "git_add_allowed": False,
            "git_commit_allowed": False,
            "git_push_allowed": False,
            "branch_operation_allowed": False,
            "pull_request_allowed": False,
            "merge_allowed": False,
            "ci_trigger_allowed": False,
        }
        draft = ProjectDirectorBoundedReworkInvocationOutcome.model_construct(
            **values,
            outcome_fingerprint="0" * 64,
        )
        return ProjectDirectorBoundedReworkInvocationOutcome(
            **values,
            outcome_fingerprint=draft.compute_fingerprint(),
        )

    @staticmethod
    def _build_executor_request(
        *,
        claim: ProjectDirectorBoundedReworkInvocationClaim,
        package: ProjectDirectorBoundedReworkInstructionPackage,
    ) -> ProjectDirectorBoundedReworkExecutorRequest:
        if (
            package.workspace_binding is None
            or package.selected_model is None
            or package.selected_role is None
            or package.rework_attempt_index is None
            or package.rework_attempt_limit != 3
        ):
            raise ValueError("persisted package is not executable")
        return ProjectDirectorBoundedReworkExecutorRequest(
            request_id=claim.claim_id,
            executor_adapter_kind=claim.executor_adapter_kind,
            workspace_path=package.workspace_binding.workspace_path,
            allowed_scope_paths=package.allowed_scope_paths,
            forbidden_scope_paths=package.forbidden_scope_paths,
            blocking_findings=tuple(
                ProjectDirectorBoundedReworkExecutorFinding(
                    finding_id=item.finding_id,
                    title=item.title,
                    evidence_paths=item.evidence_paths,
                )
                for item in package.blocking_findings
            ),
            required_corrections=tuple(
                ProjectDirectorBoundedReworkExecutorCorrection(
                    correction_id=item.correction_id,
                    source_finding_id=item.source_finding_id,
                    instruction=item.instruction,
                )
                for item in package.required_corrections
            ),
            confirmed_acceptance_criteria=package.confirmed_acceptance_criteria,
            verification_requirements=tuple(
                ProjectDirectorBoundedReworkExecutorVerificationRequirement(
                    requirement_id=item.requirement_id,
                    description=item.description,
                )
                for item in package.verification_requirements
            ),
            selected_model=claim.selected_model,
            selected_skills=claim.selected_skills,
            selected_role=claim.selected_role,
            rework_attempt_index=claim.rework_attempt_index,
            rework_attempt_limit=claim.rework_attempt_limit,
            product_runtime_git_write_allowed=False,
            main_project_write_allowed=False,
        )

    @staticmethod
    def _pre_call_error(
        *,
        claim: ProjectDirectorBoundedReworkInvocationClaim,
        package: ProjectDirectorBoundedReworkInstructionPackage,
        workspace: BoundedReworkWorkspaceSnapshot,
        repository: _RepositorySnapshot,
    ) -> BoundedReworkBlockedReason | None:
        if (
            workspace.manifest_fingerprint
            != claim.workspace_before_manifest_fingerprint
            or workspace.content_fingerprint
            != claim.workspace_before_content_fingerprint
        ):
            return "workspace_invalid"
        if package.base_commit_sha is None or repository.head_sha != package.base_commit_sha:
            return "base_commit_mismatch"
        return None

    @staticmethod
    def _claim_snapshot(
        claim: ProjectDirectorBoundedReworkInvocationClaim,
    ) -> BoundedReworkWorkspaceSnapshot:
        return BoundedReworkWorkspaceSnapshot(
            manifest_fingerprint=claim.workspace_before_manifest_fingerprint,
            content_fingerprint=claim.workspace_before_content_fingerprint,
            file_entries=(),
        )

    @staticmethod
    def _changed_paths(
        before: BoundedReworkWorkspaceSnapshot,
        after: BoundedReworkWorkspaceSnapshot | None,
    ) -> tuple[str, ...]:
        if after is None:
            return ()
        before_entries = {item.path: item for item in before.file_entries}
        after_entries = {item.path: item for item in after.file_entries}
        return tuple(
            sorted(
                path
                for path in before_entries.keys() | after_entries.keys()
                if before_entries.get(path) != after_entries.get(path)
            )
        )

    @staticmethod
    def _is_internal_path(path: str) -> bool:
        parts = PurePosixPath(path).parts
        return bool(parts and parts[0] in _INTERNAL_CONTROL_NAMES)

    @staticmethod
    def _candidate_manifest_fingerprint(
        *,
        candidate_manifest_id: UUID,
        claim: ProjectDirectorBoundedReworkInvocationClaim,
        reservation: ProjectDirectorBoundedReworkAttemptReservation,
        package: ProjectDirectorBoundedReworkInstructionPackage,
        after_workspace: BoundedReworkWorkspaceSnapshot,
        observed_paths: tuple[str, ...],
    ) -> str:
        after_entries = {item.path: item for item in after_workspace.file_entries}
        return compute_p25_contract_sha256(
            {
                "schema_version": _CANDIDATE_MANIFEST_SCHEMA_VERSION,
                "candidate_manifest_id": candidate_manifest_id,
                "claim_id": claim.claim_id,
                "claim_fingerprint": claim.claim_fingerprint,
                "reservation_id": reservation.reservation_id,
                "package_id": package.package_id,
                "rework_attempt_index": claim.rework_attempt_index,
                "workspace_after_manifest_fingerprint": after_workspace.manifest_fingerprint,
                "workspace_after_content_fingerprint": after_workspace.content_fingerprint,
                "changed_files": [
                    {
                        "path": path,
                        "content_sha256": (
                            after_entries[path].content_sha256
                            if path in after_entries
                            else None
                        ),
                        "deleted": path not in after_entries,
                    }
                    for path in observed_paths
                ],
            }
        )

    @staticmethod
    def _git_activity_kinds(
        observation: _ExecutionObservation,
    ) -> tuple[BoundedReworkGitActivityKind, ...]:
        result = observation.executor_result
        reported: dict[BoundedReworkGitActivityKind, bool] = {
            "git_add": bool(result and result.git_add),
            "git_commit": bool(result and result.git_commit),
            "git_push": bool(result and result.git_push),
            "branch_create": bool(result and result.branch_create),
            "branch_delete": bool(result and result.branch_delete),
            "checkout": bool(result and result.checkout),
            "switch": bool(result and result.switch),
            "reset": bool(result and result.reset),
            "stash": bool(result and result.stash),
            "rebase": bool(result and result.rebase),
            "tag": bool(result and result.tag),
            "pull_request": bool(result and result.pull_request),
            "merge": bool(result and result.merge),
            "ci_trigger": bool(result and result.ci_trigger),
            "repository_head_changed": bool(
                observation.after_repository
                and observation.before_repository.head_sha
                != observation.after_repository.head_sha
            ),
            "repository_status_changed": bool(
                observation.after_repository
                and observation.before_repository.status_fingerprint
                != observation.after_repository.status_fingerprint
            ),
            "git_control_metadata_changed": bool(
                observation.repository_inspection_indeterminate
                or (
                    observation.after_repository
                    and observation.before_repository.git_control_fingerprint
                    != observation.after_repository.git_control_fingerprint
                )
            ),
        }
        return tuple(kind for kind, detected in reported.items() if detected)

    @classmethod
    def _snapshot_repository(
        cls,
        package: ProjectDirectorBoundedReworkInstructionPackage,
    ) -> _RepositorySnapshot:
        binding = package.repository_binding
        if binding is None:
            raise ValueError("repository binding is required")
        root = Path(binding.repository_root)
        root_stat = root.lstat()
        if (
            root.resolve(strict=True) != root
            or not stat.S_ISDIR(root_stat.st_mode)
            or stat.S_ISLNK(root_stat.st_mode)
        ):
            raise ValueError("repository root is not an exact directory")
        head_raw = cls._run_git(root, ("rev-parse", "--verify", "HEAD"))
        head_sha = head_raw.decode("ascii", errors="strict").strip().lower()
        if not _GIT_SHA_PATTERN.fullmatch(head_sha):
            raise ValueError("repository HEAD is invalid")
        status_raw = cls._run_git(
            root,
            ("status", "--porcelain=v1", "-z", "--untracked-files=all"),
        )
        if len(status_raw) > _MAX_GIT_STATUS_BYTES:
            raise ValueError("repository status exceeds bounded inspection limit")
        status_fingerprint = compute_p25_contract_sha256(
            {
                "schema_version": _REPOSITORY_STATUS_SCHEMA_VERSION,
                "status_hex": status_raw.hex(),
            }
        )
        return _RepositorySnapshot(
            head_sha=head_sha,
            status_fingerprint=status_fingerprint,
            git_control_fingerprint=cls._git_control_fingerprint(root),
        )

    @staticmethod
    def _run_git(root: Path, arguments: tuple[str, ...]) -> bytes:
        environment = dict(os.environ)
        environment["GIT_OPTIONAL_LOCKS"] = "0"
        completed = subprocess.run(
            ("git", "-C", root.as_posix(), *arguments),
            shell=False,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=_GIT_TIMEOUT_SECONDS,
            env=environment,
        )
        return completed.stdout

    @classmethod
    def _git_control_fingerprint(cls, repository_root: Path) -> str:
        git_root = repository_root / ".git"
        git_stat = git_root.lstat()
        if (
            stat.S_ISLNK(git_stat.st_mode)
            or not stat.S_ISDIR(git_stat.st_mode)
            or git_root.resolve(strict=True) != git_root
        ):
            raise ValueError("bounded Git control directory is invalid")
        paths: list[Path] = []
        for name in ("HEAD", "index", "packed-refs"):
            candidate = git_root / name
            if candidate.exists():
                paths.append(candidate)
        refs = git_root / "refs"
        if refs.exists():
            for directory, directory_names, file_names in os.walk(
                refs,
                topdown=True,
                followlinks=False,
            ):
                directory_names.sort()
                file_names.sort()
                directory_path = Path(directory)
                for name in directory_names:
                    item_stat = (directory_path / name).lstat()
                    if stat.S_ISLNK(item_stat.st_mode):
                        raise ValueError("Git control directory contains a symlink")
                paths.extend(directory_path / name for name in file_names)
                if len(paths) > _MAX_GIT_CONTROL_ENTRIES:
                    raise ValueError("Git control inspection exceeds entry limit")
        entries: list[dict[str, object]] = []
        total_bytes = 0
        for path in sorted(paths):
            relative = path.relative_to(git_root).as_posix()
            data = cls._read_bounded_regular_file(path)
            total_bytes += len(data)
            if (
                total_bytes > _MAX_GIT_CONTROL_TOTAL_BYTES
            ):
                raise ValueError("Git control inspection changed or exceeded limits")
            entries.append(
                {
                    "path": relative,
                    "size": len(data),
                    "content_sha256": hashlib.sha256(data).hexdigest(),
                }
            )
        return compute_p25_contract_sha256(
            {
                "schema_version": _GIT_CONTROL_SCHEMA_VERSION,
                "entries": entries,
            }
        )

    @classmethod
    def _read_bounded_regular_file(cls, path: Path) -> bytes:
        before = path.lstat()
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or before.st_nlink != 1
            or before.st_size > _MAX_GIT_CONTROL_FILE_BYTES
        ):
            raise ValueError("Git control file is not safely bounded")
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        try:
            opened = os.fstat(descriptor)
            if cls._stat_identity(before) != cls._stat_identity(opened):
                raise ValueError("Git control file changed before inspection")
            chunks: list[bytes] = []
            read_bytes = 0
            while True:
                chunk = os.read(descriptor, 64 * 1024)
                if not chunk:
                    break
                read_bytes += len(chunk)
                if read_bytes > _MAX_GIT_CONTROL_FILE_BYTES:
                    raise ValueError("Git control file exceeds inspection limit")
                chunks.append(chunk)
            after = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        if (
            read_bytes != before.st_size
            or cls._stat_identity(before) != cls._stat_identity(after)
        ):
            raise ValueError("Git control file changed during inspection")
        return b"".join(chunks)

    @staticmethod
    def _stat_identity(value: os.stat_result) -> tuple[int, ...]:
        return (
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_nlink,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )

    def _build_outcome_message(
        self,
        outcome: ProjectDirectorBoundedReworkInvocationOutcome,
    ) -> ProjectDirectorMessage:
        return ProjectDirectorMessage(
            id=outcome.outcome_id,
            session_id=outcome.authority.session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content=f"P25 bounded rework invocation outcome: {outcome.outcome_id}",
            sequence_no=self._message_repository.get_next_sequence_no(
                session_id=outcome.authority.session_id
            ),
            intent=P25_BOUNDED_REWORK_INVOCATION_OUTCOME_INTENT,
            related_project_id=outcome.authority.project_id,
            related_task_id=outcome.exact_task_id,
            source=ProjectDirectorMessageSource.SYSTEM,
            source_detail=P25_BOUNDED_REWORK_INVOCATION_OUTCOME_SOURCE_DETAIL,
            suggested_actions=[
                {
                    "type": P25_BOUNDED_REWORK_INVOCATION_OUTCOME_ACTION_TYPE,
                    **outcome.model_dump(mode="json"),
                }
            ],
            requires_confirmation=False,
            risk_level=ProjectDirectorMessageRiskLevel.HIGH,
            forbidden_actions_detected=list(_OUTCOME_FALSE_BOUNDARIES),
            token_count=None,
            estimated_cost=None,
            created_at=outcome.created_at,
        )

    def _rollback_read_transaction(self) -> None:
        if self._message_repository._session.in_transaction():
            self._message_repository._session.rollback()

    @staticmethod
    def _blocked(
        reason: BoundedReworkBlockedReason,
        *,
        claim: ProjectDirectorBoundedReworkInvocationClaim | None = None,
        claim_message: ProjectDirectorMessage | None = None,
    ) -> ExecutedProjectDirectorBoundedReworkInvocation:
        return ExecutedProjectDirectorBoundedReworkInvocation(
            status="blocked",
            claim=claim,
            claim_message=claim_message,
            outcome=None,
            outcome_message=None,
            blocked_reasons=(reason,),
            recovery_required=reason
            in {
                "claim_without_outcome",
                "history_invalid",
                "persistence_failed",
                "git_boundary_violation",
                "human_escalation_required",
            },
            human_escalation_required=reason
            in {"git_boundary_violation", "human_escalation_required"},
        )


__all__ = (
    "ExecutedProjectDirectorBoundedReworkInvocation",
    "OutcomeExecutionStatus",
    "P25_BOUNDED_REWORK_INVOCATION_OUTCOME_ACTION_TYPE",
    "P25_BOUNDED_REWORK_INVOCATION_OUTCOME_INTENT",
    "P25_BOUNDED_REWORK_INVOCATION_OUTCOME_SOURCE_DETAIL",
    "ProjectDirectorBoundedReworkInvocationOutcomeService",
)
