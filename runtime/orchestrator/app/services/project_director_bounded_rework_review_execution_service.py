"""Execute one claimed P25-H readonly review and persist a fresh outcome."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID, uuid5

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.domain._base import utc_now
from app.domain.project_director_bounded_rework_contract import (
    BoundedReworkBlockedReason,
    compute_p25_contract_sha256,
)
from app.domain.project_director_bounded_rework_review_reentry import (
    P25_BOUNDED_REWORK_REVIEW_ATTEMPT_NAMESPACE,
    P25_BOUNDED_REWORK_REVIEW_ATTEMPT_SCHEMA_VERSION,
    P25_BOUNDED_REWORK_REVIEW_OUTCOME_NAMESPACE,
    P25_BOUNDED_REWORK_REVIEW_OUTCOME_SCHEMA_VERSION,
    P25_BOUNDED_REWORK_REVIEW_OUTPUT_SCHEMA_VERSION,
    ProjectDirectorBoundedReworkReviewInvocationAttempt,
    ProjectDirectorBoundedReworkReviewInvocationOutcome,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_sandbox_candidate_diff_readonly_reviewer_adapter import (
    ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.services.project_director_bounded_rework_review_reentry_preflight_service import (
    RevalidatedProjectDirectorBoundedReworkReviewClaim,
    ProjectDirectorBoundedReworkReviewReentryPreflightService,
)
from app.services.project_director_sandbox_candidate_diff_readonly_review_execution_service import (
    ReadonlyReviewerTransportResolverFactoryProtocol,
)
from app.services.project_director_sandbox_candidate_diff_readonly_reviewer_adapter_service import (
    ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService,
)
from app.services.project_director_sandbox_candidate_diff_review_execution_preflight_service import (
    ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService,
)


P25_BOUNDED_REWORK_REVIEW_ATTEMPT_SOURCE_DETAIL = (
    "p25_h_bounded_rework_review_invocation_attempt_reserved"
)
P25_BOUNDED_REWORK_REVIEW_ATTEMPT_ACTION_TYPE = (
    "p25_h_bounded_rework_review_invocation_attempt_record"
)
P25_BOUNDED_REWORK_REVIEW_ATTEMPT_INTENT = (
    "bounded_rework_review_reentry_invocation_attempt"
)

P25_BOUNDED_REWORK_REVIEW_OUTCOME_SOURCE_DETAIL = (
    "p25_h_bounded_rework_review_invocation_outcome_persisted"
)
P25_BOUNDED_REWORK_REVIEW_OUTCOME_ACTION_TYPE = (
    "p25_h_bounded_rework_review_invocation_outcome_record"
)
P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT = (
    "bounded_rework_review_reentry_invocation_outcome"
)

_P25_H_ATTEMPT_FALSE_BOUNDARIES = (
    "provider_called=false",
    "main_project_write_allowed=false",
    "product_runtime_git_write_allowed=false",
    "patch_apply_allowed=false",
    "git_write_allowed=false",
    "task_created=false",
    "run_created=false",
)

_P25_H_OUTCOME_FALSE_BOUNDARIES = (
    "provider_called=false",
    "main_project_write_allowed=false",
    "product_runtime_git_write_allowed=false",
    "patch_apply_allowed=false",
    "git_write_allowed=false",
    "task_created=false",
    "run_created=false",
)

_PAGE_SIZE = 200

ExecutedBoundedReworkReadonlyReviewStatus = Literal[
    "review_outcome_persisted",
    "review_outcome_replayed",
    "recovery_required",
    "blocked",
]

RevalidatedBoundedReworkReviewOutcomeStatus = Literal[
    "validated_output",
    "recovery_required",
    "blocked",
]


@dataclass(frozen=True, slots=True)
class ExecutedProjectDirectorBoundedReworkReadonlyReview:
    status: ExecutedBoundedReworkReadonlyReviewStatus
    review_attempt: ProjectDirectorBoundedReworkReviewInvocationAttempt | None
    review_attempt_message: ProjectDirectorMessage | None
    review_outcome: ProjectDirectorBoundedReworkReviewInvocationOutcome | None
    review_outcome_message: ProjectDirectorMessage | None
    blocked_reasons: tuple[BoundedReworkBlockedReason, ...]


@dataclass(frozen=True, slots=True)
class RevalidatedProjectDirectorBoundedReworkReviewOutcome:
    """Exact persisted H-B outcome and its reconstructed readonly lineage."""

    status: RevalidatedBoundedReworkReviewOutcomeStatus
    review_attempt: ProjectDirectorBoundedReworkReviewInvocationAttempt | None
    review_attempt_message: ProjectDirectorMessage | None
    review_outcome: ProjectDirectorBoundedReworkReviewInvocationOutcome | None
    review_outcome_message: ProjectDirectorMessage | None
    preflight: Any | None
    review_claim: Any | None
    candidate_diff: Any | None
    candidate_manifest: Any | None
    package: Any | None
    blocked_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _PersistedReviewExecutionHistory:
    attempts: tuple[
        tuple[ProjectDirectorMessage, ProjectDirectorBoundedReworkReviewInvocationAttempt],
        ...,
    ]
    outcomes: tuple[
        tuple[ProjectDirectorMessage, ProjectDirectorBoundedReworkReviewInvocationOutcome],
        ...,
    ]


@dataclass(frozen=True, slots=True)
class _ExecutionObservation:
    adapter_result: ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult | None
    safe_error_code: str | None


class _Blocked(RuntimeError):
    def __init__(self, reason: BoundedReworkBlockedReason) -> None:
        self.reason = reason
        super().__init__(reason)


class ProjectDirectorBoundedReworkReviewExecutionService:
    """Execute a claimed P25-H readonly review strictly outside write transactions."""

    def __init__(
        self,
        *,
        message_repository: ProjectDirectorMessageRepository,
        preflight_service: ProjectDirectorBoundedReworkReviewReentryPreflightService,
        transport_resolver_factory: ReadonlyReviewerTransportResolverFactoryProtocol,
        adapter_service: ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService
        | None = None,
    ) -> None:
        self._message_repository = message_repository
        self._preflight_service = preflight_service
        self._transport_resolver_factory = transport_resolver_factory
        self._adapter_service = (
            adapter_service
            or ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService()
        )
        if preflight_service._message_repository is not message_repository:
            raise ValueError("P25-H review execution dependencies must share one message repository")

    def execute_claimed_readonly_review(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_review_claim_message_id: UUID,
    ) -> ExecutedProjectDirectorBoundedReworkReadonlyReview:
        """Rebuild exact persisted evidence, call the reviewer once, and persist outcome."""

        initial = self._preflight_service.revalidate_persisted_review_reentry_claim_for_execution(
            session_id=session_id,
            source_task_id=source_task_id,
            source_review_claim_message_id=source_review_claim_message_id,
        )
        if initial.blocked_reasons:
            return self._blocked(initial.blocked_reasons[0])

        try:
            prompt = self._rebuild_prompt(initial)
        except _Blocked as exc:
            return self._blocked(exc.reason)
        except (TypeError, ValueError, ValidationError):
            return self._blocked("review_reentry_failed")

        self._rollback_read_transaction()
        try:
            with self._message_repository.sqlite_immediate_transaction():
                current = self._preflight_service.revalidate_persisted_review_reentry_claim_for_persistence(
                    session_id=session_id,
                    source_task_id=source_task_id,
                    source_review_claim_message_id=source_review_claim_message_id,
                )
                if current.blocked_reasons:
                    raise _Blocked(current.blocked_reasons[0])
                if not self._same_revalidated_claim_lineage(initial, current):
                    raise _Blocked("history_invalid")
                if self._rebuild_prompt(current) != prompt:
                    raise _Blocked("review_reentry_failed")
                history = self._load_history(session_id)
                replay = self._attempt_replay_state(history=history, current=current)
                if replay is not None:
                    return replay
                attempt = self._build_attempt(current=current)
                attempt_message = self._build_attempt_message(attempt)
                persisted_attempt_message = self._message_repository.create(attempt_message)
                if persisted_attempt_message != attempt_message:
                    raise _Blocked("persistence_failed")
        except _Blocked as exc:
            return self._blocked(exc.reason)
        except SQLAlchemyError:
            return self._blocked("persistence_failed")
        except (OSError, RuntimeError, TypeError, ValueError, ValidationError):
            return self._blocked("history_invalid")
        finally:
            self._rollback_read_transaction()

        try:
            observation = self._execute_once(current=current, prompt=prompt)
            outcome = self._build_outcome(
                current=current,
                attempt=attempt,
                observation=observation,
            )
        except (TypeError, ValueError, ValidationError):
            return self._recovery_required(attempt=attempt, attempt_message=persisted_attempt_message)

        self._rollback_read_transaction()
        try:
            with self._message_repository.sqlite_immediate_transaction():
                final = self._preflight_service.revalidate_persisted_review_reentry_claim_for_persistence(
                    session_id=session_id,
                    source_task_id=source_task_id,
                    source_review_claim_message_id=source_review_claim_message_id,
                )
                if final.blocked_reasons:
                    raise _Blocked(final.blocked_reasons[0])
                if not self._same_revalidated_claim_lineage(current, final):
                    raise _Blocked("history_invalid")
                if self._rebuild_prompt(final) != prompt:
                    raise _Blocked("review_reentry_failed")
                history = self._load_history(session_id)
                persisted_attempt = self._attempt_from_history(
                    history=history,
                    review_claim_id=final.review_claim.review_claim_id,
                )
                persisted_outcome = self._outcome_from_history(
                    history=history,
                    review_claim_id=final.review_claim.review_claim_id,
                )
                if persisted_outcome is not None:
                    outcome_message, historical_outcome = persisted_outcome
                    if (
                        persisted_attempt is None
                        or not self._outcome_binds_current(
                            outcome=historical_outcome,
                            attempt=persisted_attempt[1],
                            current=final,
                        )
                    ):
                        raise _Blocked("history_invalid")
                    return ExecutedProjectDirectorBoundedReworkReadonlyReview(
                        status="review_outcome_replayed",
                        review_attempt=persisted_attempt[1],
                        review_attempt_message=persisted_attempt[0],
                        review_outcome=historical_outcome,
                        review_outcome_message=outcome_message,
                        blocked_reasons=(),
                    )
                if (
                    persisted_attempt is None
                    or persisted_attempt[1].review_attempt_id != attempt.review_attempt_id
                    or persisted_attempt[1].review_attempt_fingerprint
                    != attempt.review_attempt_fingerprint
                ):
                    raise _Blocked("history_invalid")
                if not self._outcome_binds_current(
                    outcome=outcome,
                    attempt=attempt,
                    current=final,
                ):
                    raise _Blocked("history_invalid")
                outcome_message = self._build_outcome_message(outcome)
                persisted_outcome_message = self._message_repository.create(outcome_message)
                if persisted_outcome_message != outcome_message:
                    raise _Blocked("persistence_failed")
                return ExecutedProjectDirectorBoundedReworkReadonlyReview(
                    status="review_outcome_persisted",
                    review_attempt=attempt,
                    review_attempt_message=persisted_attempt_message,
                    review_outcome=outcome,
                    review_outcome_message=persisted_outcome_message,
                    blocked_reasons=(),
                )
        except (_Blocked, SQLAlchemyError, OSError, RuntimeError, TypeError, ValueError, ValidationError):
            return self._recovery_required(
                attempt=attempt,
                attempt_message=persisted_attempt_message,
            )
        finally:
            self._rollback_read_transaction()

    def revalidate_persisted_review_invocation_outcome(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_review_outcome_message_id: UUID,
    ) -> RevalidatedProjectDirectorBoundedReworkReviewOutcome:
        """Rebuild one exact validated H-B outcome without writes or reviewer calls."""

        caller_had_transaction = self._message_repository._session.in_transaction()
        try:
            history = self._load_history(session_id)
            outcome_matches = [
                item
                for item in history.outcomes
                if item[0].id == source_review_outcome_message_id
            ]
            if len(outcome_matches) > 1:
                raise _Blocked("history_invalid")
            if not outcome_matches:
                expected_attempts = [
                    item
                    for item in history.attempts
                    if uuid5(
                        P25_BOUNDED_REWORK_REVIEW_OUTCOME_NAMESPACE,
                        item[1].review_attempt_replay_key,
                    )
                    == source_review_outcome_message_id
                ]
                if len(expected_attempts) > 1:
                    raise _Blocked("history_invalid")
                if expected_attempts:
                    attempt_message, attempt = expected_attempts[0]
                    current = self._preflight_service.revalidate_persisted_review_reentry_claim_for_execution(
                        session_id=session_id,
                        source_task_id=source_task_id,
                        source_review_claim_message_id=attempt.review_claim_id,
                    )
                    if (
                        current.blocked_reasons
                        or not self._attempt_binds_current(
                            attempt=attempt,
                            current=current,
                        )
                        or not self._persisted_attempt_fingerprint_valid(
                            attempt=attempt,
                            current=current,
                        )
                    ):
                        raise _Blocked("history_invalid")
                    return self._revalidated_outcome_result(
                        status="recovery_required",
                        attempt=attempt,
                        attempt_message=attempt_message,
                        current=current,
                        blocked_reasons=("claim_without_outcome",),
                    )
                raise _Blocked("history_invalid")

            outcome_message, outcome = outcome_matches[0]
            attempt_matches = [
                item
                for item in history.attempts
                if item[1].review_attempt_id == outcome.review_attempt_id
            ]
            if len(attempt_matches) != 1:
                raise _Blocked("history_invalid")
            attempt_message, attempt = attempt_matches[0]

            current = self._preflight_service.revalidate_persisted_review_reentry_claim_for_execution(
                session_id=session_id,
                source_task_id=source_task_id,
                source_review_claim_message_id=outcome.review_claim_id,
            )
            if current.blocked_reasons:
                raise _Blocked(current.blocked_reasons[0])
            if not self._outcome_binds_current(
                outcome=outcome,
                attempt=attempt,
                current=current,
            ):
                raise _Blocked("history_invalid")
            if not self._persisted_attempt_and_outcome_fingerprints_valid(
                attempt=attempt,
                outcome=outcome,
                current=current,
            ):
                raise _Blocked("history_invalid")

            status: RevalidatedBoundedReworkReviewOutcomeStatus = "validated_output"
            blocked_reasons: tuple[str, ...] = ()
            if not self._validated_outcome_domain_gate(outcome):
                status = "blocked"
                blocked_reasons = ("review_outcome_not_validated",)
            return self._revalidated_outcome_result(
                status=status,
                attempt=attempt,
                attempt_message=attempt_message,
                outcome=outcome,
                outcome_message=outcome_message,
                current=current,
                blocked_reasons=blocked_reasons,
            )
        except _Blocked as exc:
            return self._revalidated_outcome_result(
                status="blocked",
                blocked_reasons=(str(exc.reason),),
            )
        except (SQLAlchemyError, OSError, RuntimeError, TypeError, ValueError, ValidationError):
            return self._revalidated_outcome_result(
                status="blocked",
                blocked_reasons=("history_invalid",),
            )
        finally:
            self._cleanup_local_read_transaction(
                caller_had_transaction=caller_had_transaction
            )

    def revalidate_review_outcome_for_candidate_diff(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_candidate_diff_message_id: UUID,
    ) -> RevalidatedProjectDirectorBoundedReworkReviewOutcome:
        """Locate the unique H-B attempt/outcome bound to one candidate diff."""

        caller_had_transaction = self._message_repository._session.in_transaction()
        try:
            history = self._load_history(session_id)
            attempts = [
                item
                for item in history.attempts
                if item[1].source_candidate_diff_message_id
                == source_candidate_diff_message_id
            ]
            outcomes = [
                item
                for item in history.outcomes
                if item[1].source_candidate_diff_message_id
                == source_candidate_diff_message_id
            ]
            if len(attempts) > 1 or len(outcomes) > 1:
                raise _Blocked("history_invalid")
            if not attempts:
                if outcomes:
                    raise _Blocked("history_invalid")
                return self._revalidated_outcome_result(
                    status="blocked",
                    blocked_reasons=("review_reentry_failed",),
                )

            attempt_message, attempt = attempts[0]
            if attempt.exact_task_id != source_task_id or any(
                outcome.exact_task_id != source_task_id
                for _, outcome in outcomes
            ):
                raise _Blocked("history_invalid")
            if outcomes and outcomes[0][1].review_attempt_id != attempt.review_attempt_id:
                raise _Blocked("history_invalid")
            outcome_message_id = (
                outcomes[0][0].id
                if outcomes
                else uuid5(
                    P25_BOUNDED_REWORK_REVIEW_OUTCOME_NAMESPACE,
                    attempt.review_attempt_replay_key,
                )
            )
            result = self.revalidate_persisted_review_invocation_outcome(
                session_id=session_id,
                source_task_id=source_task_id,
                source_review_outcome_message_id=outcome_message_id,
            )
            if (
                result.review_attempt is not None
                and (
                    result.review_attempt != attempt
                    or result.review_attempt_message != attempt_message
                    or result.review_attempt.source_candidate_diff_message_id
                    != source_candidate_diff_message_id
                )
            ):
                raise _Blocked("history_invalid")
            if (
                result.review_outcome is not None
                and result.review_outcome.source_candidate_diff_message_id
                != source_candidate_diff_message_id
            ):
                raise _Blocked("history_invalid")
            return result
        except _Blocked as exc:
            return self._revalidated_outcome_result(
                status="blocked",
                blocked_reasons=(str(exc.reason),),
            )
        except (SQLAlchemyError, OSError, RuntimeError, TypeError, ValueError, ValidationError):
            return self._revalidated_outcome_result(
                status="blocked",
                blocked_reasons=("history_invalid",),
            )
        finally:
            self._cleanup_local_read_transaction(
                caller_had_transaction=caller_had_transaction
            )

    def _execute_once(
        self,
        *,
        current: RevalidatedProjectDirectorBoundedReworkReviewClaim,
        prompt: str,
    ) -> _ExecutionObservation:
        if (
            current.package is None
            or current.package.workspace_binding is None
            or current.preflight is None
        ):
            raise ValueError("P25-H current lineage is incomplete")
        try:
            resolver = self._transport_resolver_factory(
                current.package.workspace_binding.workspace_path
            )
        except Exception:
            return _ExecutionObservation(
                adapter_result=None,
                safe_error_code="reviewer_transport_resolver_factory_raised",
            )
        try:
            transport = resolver(current.preflight.requested_reviewer_executor)
        except Exception:
            return _ExecutionObservation(
                adapter_result=None,
                safe_error_code="reviewer_transport_resolver_raised",
            )
        if not self._transport_looks_valid(transport):
            return _ExecutionObservation(
                adapter_result=None,
                safe_error_code="reviewer_transport_invalid",
            )
        try:
            adapter_result = self._adapter_service.validate_review_output_through_transport(
                requested_reviewer_executor=current.preflight.requested_reviewer_executor,
                review_prompt_text=prompt,
                expected_review_prompt_sha256=current.preflight.review_prompt_sha256,
                expected_review_prompt_bytes=current.preflight.review_prompt_bytes,
                review_scope_paths=list(current.preflight.review_scope_paths),
                review_output_schema_version=P25_BOUNDED_REWORK_REVIEW_OUTPUT_SCHEMA_VERSION,
                transport=transport,
            )
        except Exception:
            return _ExecutionObservation(
                adapter_result=None,
                safe_error_code="reviewer_transport_execute_raised",
            )
        return _ExecutionObservation(adapter_result=adapter_result, safe_error_code=None)

    @staticmethod
    def _transport_looks_valid(transport: Any) -> bool:
        return bool(transport is not None and callable(getattr(transport, "execute", None)))

    @staticmethod
    def _rebuild_prompt(
        current: RevalidatedProjectDirectorBoundedReworkReviewClaim,
    ) -> str:
        if current.preflight is None or current.candidate_diff is None:
            raise _Blocked("history_invalid")
        if (
            current.candidate_diff.new_diff_sha256
            != current.preflight.source_candidate_diff_sha256
        ):
            raise _Blocked("source_diff_mismatch")
        prompt = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService.build_readonly_review_prompt(
            requested_reviewer_executor=current.preflight.requested_reviewer_executor,
            source_diff_sha256=current.candidate_diff.new_diff_sha256,
            review_scope_paths=list(current.candidate_diff.scope_paths),
            unified_diff_text=current.candidate_diff.unified_diff_text,
            review_output_schema_version=P25_BOUNDED_REWORK_REVIEW_OUTPUT_SCHEMA_VERSION,
        )
        prompt_bytes = prompt.encode("utf-8")
        prompt_sha256 = hashlib.sha256(prompt_bytes).hexdigest()
        if (
            prompt_sha256 != current.preflight.review_prompt_sha256
            or len(prompt_bytes) != current.preflight.review_prompt_bytes
        ):
            raise _Blocked("review_reentry_failed")
        return prompt

    def _build_attempt(
        self,
        *,
        current: RevalidatedProjectDirectorBoundedReworkReviewClaim,
    ) -> ProjectDirectorBoundedReworkReviewInvocationAttempt:
        if (
            current.preflight is None
            or current.review_claim is None
            or current.candidate_diff is None
        ):
            raise ValueError("P25-H attempt lineage is incomplete")
        values = {
            "review_attempt_replay_key": (
                ProjectDirectorBoundedReworkReviewInvocationAttempt.compute_attempt_replay_key(
                    review_claim_replay_key=current.review_claim.review_claim_replay_key,
                    invocation_ordinal=current.review_claim.invocation_ordinal,
                )
            ),
            "created_at": utc_now(),
            "attempt_status": "call_reserved",
            "review_claim_id": current.review_claim.review_claim_id,
            "review_claim_fingerprint": current.review_claim.review_claim_fingerprint,
            "review_claim_replay_key": current.review_claim.review_claim_replay_key,
            "review_claim_token_fingerprint": hashlib.sha256(
                current.review_claim.review_claim_token.encode("utf-8")
            ).hexdigest(),
            "preflight_id": current.preflight.preflight_id,
            "preflight_fingerprint": current.preflight.preflight_fingerprint,
            "source_candidate_diff_message_id": current.candidate_diff.candidate_diff_id,
            "source_candidate_diff_id": current.candidate_diff.candidate_diff_id,
            "source_candidate_diff_fingerprint": (
                current.candidate_diff.candidate_diff_fingerprint
            ),
            "source_candidate_diff_sha256": current.candidate_diff.new_diff_sha256,
            "source_outcome_id": current.candidate_diff.source_outcome_id,
            "source_attempt_id": current.candidate_diff.source_attempt_id,
            "source_package_id": current.candidate_diff.source_package_id,
            "authority": current.review_claim.authority,
            "exact_task_id": current.review_claim.exact_task_id,
            "exact_run_id": current.review_claim.exact_run_id,
            "rework_attempt_index": current.review_claim.rework_attempt_index,
            "rework_attempt_limit": current.review_claim.rework_attempt_limit,
            "requested_reviewer_executor": (
                current.review_claim.requested_reviewer_executor
            ),
            "review_prompt_sha256": current.review_claim.review_prompt_sha256,
            "review_prompt_bytes": current.review_claim.review_prompt_bytes,
            "review_output_schema_version": (
                current.review_claim.review_output_schema_version
            ),
            "invocation_ordinal": current.review_claim.invocation_ordinal,
            "reviewer_call_reserved": True,
            "reviewer_call_attempted": False,
            "reviewer_started": False,
            "reviewer_returned": False,
            "reviewer_raised": False,
            "review_output_persisted": False,
            "provider_called": False,
            "main_project_write_allowed": False,
            "product_runtime_git_write_allowed": False,
            "patch_apply_allowed": False,
            "git_write_allowed": False,
            "task_created": False,
            "run_created": False,
        }
        review_attempt_id = uuid5(
            P25_BOUNDED_REWORK_REVIEW_ATTEMPT_NAMESPACE,
            values["review_attempt_replay_key"],
        )
        values["review_attempt_id"] = review_attempt_id
        draft = ProjectDirectorBoundedReworkReviewInvocationAttempt.model_construct(
            review_attempt_fingerprint="0" * 64,
            **values,
        )
        return ProjectDirectorBoundedReworkReviewInvocationAttempt(
            review_attempt_fingerprint=draft.compute_fingerprint(),
            **values,
        )

    def _build_outcome(
        self,
        *,
        current: RevalidatedProjectDirectorBoundedReworkReviewClaim,
        attempt: ProjectDirectorBoundedReworkReviewInvocationAttempt,
        observation: _ExecutionObservation,
    ) -> ProjectDirectorBoundedReworkReviewInvocationOutcome:
        if (
            current.preflight is None
            or current.review_claim is None
            or current.candidate_diff is None
            or current.candidate_manifest is None
            or current.invocation_outcome is None
        ):
            raise ValueError("P25-H outcome lineage is incomplete")
        adapter_result = observation.adapter_result
        outcome_status = "raised"
        blocked_reasons: tuple[str, ...] = ()
        safe_error_code = observation.safe_error_code
        review_semantic_fingerprint: str | None = None
        if adapter_result is not None:
            if adapter_result.adapter_status == "validated_output":
                outcome_status = "validated_output"
                safe_error_code = None
                review_semantic_fingerprint = self._review_semantic_fingerprint(
                    adapter_result=adapter_result,
                    source_candidate_diff_sha256=current.candidate_diff.new_diff_sha256,
                    review_scope_paths=current.preflight.review_scope_paths,
                )
            else:
                outcome_status = "blocked"
                safe_error_code = None
                blocked_reasons = tuple(dict.fromkeys(adapter_result.blocked_reasons))
        review_outcome_replay_key = (
            ProjectDirectorBoundedReworkReviewInvocationOutcome.compute_outcome_replay_key(
                review_attempt_replay_key=attempt.review_attempt_replay_key,
                source_candidate_diff_sha256=current.candidate_diff.new_diff_sha256,
                review_prompt_sha256=current.preflight.review_prompt_sha256,
                invocation_ordinal=current.preflight.invocation_ordinal,
            )
        )
        values = {
            "review_outcome_replay_key": review_outcome_replay_key,
            "created_at": utc_now(),
            "outcome_status": outcome_status,
            "review_attempt_id": attempt.review_attempt_id,
            "review_attempt_fingerprint": attempt.review_attempt_fingerprint,
            "review_attempt_replay_key": attempt.review_attempt_replay_key,
            "review_claim_id": current.review_claim.review_claim_id,
            "review_claim_fingerprint": current.review_claim.review_claim_fingerprint,
            "preflight_id": current.preflight.preflight_id,
            "preflight_fingerprint": current.preflight.preflight_fingerprint,
            "source_candidate_diff_message_id": current.candidate_diff.candidate_diff_id,
            "source_candidate_diff_id": current.candidate_diff.candidate_diff_id,
            "source_candidate_diff_fingerprint": (
                current.candidate_diff.candidate_diff_fingerprint
            ),
            "source_candidate_diff_sha256": current.candidate_diff.new_diff_sha256,
            "source_candidate_manifest_id": (
                current.candidate_manifest.candidate_manifest_id
            ),
            "source_candidate_manifest_fingerprint": (
                current.candidate_manifest.candidate_manifest_fingerprint
            ),
            "source_executor_outcome_id": current.invocation_outcome.outcome_id,
            "source_package_id": current.review_claim.source_package_id,
            "source_attempt_id": current.review_claim.source_attempt_id,
            "authority": current.review_claim.authority,
            "exact_task_id": current.review_claim.exact_task_id,
            "exact_run_id": current.review_claim.exact_run_id,
            "rework_attempt_index": current.review_claim.rework_attempt_index,
            "rework_attempt_limit": current.review_claim.rework_attempt_limit,
            "requested_reviewer_executor": (
                current.preflight.requested_reviewer_executor
            ),
            "review_prompt_sha256": current.preflight.review_prompt_sha256,
            "review_prompt_bytes": current.preflight.review_prompt_bytes,
            "review_scope_paths": current.preflight.review_scope_paths,
            "review_output_schema_version": (
                current.preflight.review_output_schema_version
            ),
            "invocation_ordinal": current.preflight.invocation_ordinal,
            "adapter_result": adapter_result,
            "review_result_fingerprint": self._review_result_fingerprint(
                current=current,
                attempt=attempt,
                adapter_result=adapter_result,
                safe_error_code=safe_error_code,
            ),
            "review_semantic_fingerprint": review_semantic_fingerprint,
            "safe_error_code": safe_error_code,
            "blocked_reasons": blocked_reasons,
            "recovery_required": False,
            "human_escalation_required": False,
        }
        review_outcome_id = uuid5(
            P25_BOUNDED_REWORK_REVIEW_OUTCOME_NAMESPACE,
            attempt.review_attempt_replay_key,
        )
        values["review_outcome_id"] = review_outcome_id
        draft = ProjectDirectorBoundedReworkReviewInvocationOutcome.model_construct(
            review_outcome_fingerprint="0" * 64,
            **values,
        )
        return ProjectDirectorBoundedReworkReviewInvocationOutcome(
            review_outcome_fingerprint=draft.compute_fingerprint(),
            **values,
        )

    @staticmethod
    def _review_result_fingerprint(
        *,
        current: RevalidatedProjectDirectorBoundedReworkReviewClaim,
        attempt: ProjectDirectorBoundedReworkReviewInvocationAttempt,
        adapter_result: ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult
        | None,
        safe_error_code: str | None,
    ) -> str:
        if (
            current.preflight is None
            or current.review_claim is None
            or current.candidate_diff is None
        ):
            raise ValueError("P25-H review result lineage is incomplete")
        payload = {
            "review_attempt_id": attempt.review_attempt_id,
            "review_attempt_fingerprint": attempt.review_attempt_fingerprint,
            "review_claim_id": current.review_claim.review_claim_id,
            "review_claim_fingerprint": current.review_claim.review_claim_fingerprint,
            "preflight_id": current.preflight.preflight_id,
            "preflight_fingerprint": current.preflight.preflight_fingerprint,
            "source_candidate_diff_id": current.candidate_diff.candidate_diff_id,
            "source_candidate_diff_fingerprint": (
                current.candidate_diff.candidate_diff_fingerprint
            ),
            "source_candidate_diff_sha256": current.candidate_diff.new_diff_sha256,
            "review_prompt_sha256": current.preflight.review_prompt_sha256,
            "review_prompt_bytes": current.preflight.review_prompt_bytes,
            "requested_reviewer_executor": (
                current.preflight.requested_reviewer_executor
            ),
            "authority": current.review_claim.authority,
            "exact_task_id": current.review_claim.exact_task_id,
            "exact_run_id": current.review_claim.exact_run_id,
            "rework_attempt_index": current.review_claim.rework_attempt_index,
            "review_scope_paths": current.preflight.review_scope_paths,
            "adapter_result": (
                adapter_result.model_dump(mode="python")
                if adapter_result is not None
                else None
            ),
            "safe_error_code": safe_error_code,
        }
        return compute_p25_contract_sha256(payload)

    @staticmethod
    def _review_semantic_fingerprint(
        *,
        adapter_result: ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult,
        source_candidate_diff_sha256: str,
        review_scope_paths: tuple[str, ...],
    ) -> str:
        findings = [
            {
                "finding_id": finding.finding_id,
                "severity": finding.severity,
                "title": finding.title,
                "summary": finding.summary,
                "evidence_paths": sorted(finding.evidence_paths),
                "recommended_action": finding.recommended_action,
            }
            for finding in adapter_result.findings
        ]
        findings.sort(key=lambda item: compute_p25_contract_sha256(item))
        return compute_p25_contract_sha256(
            {
                "verdict": adapter_result.verdict,
                "risk_level": adapter_result.risk_level,
                "summary": adapter_result.summary,
                "findings": findings,
                "recommended_next_step": adapter_result.recommended_next_step,
                "review_scope_paths": review_scope_paths,
                "source_candidate_diff_sha256": source_candidate_diff_sha256,
            }
        )

    @staticmethod
    def rebuild_persisted_review_result_fingerprint(
        outcome: ProjectDirectorBoundedReworkReviewInvocationOutcome,
    ) -> str:
        """Rebuild the canonical H-B result fingerprint from persisted fields."""

        return compute_p25_contract_sha256(
            {
                "review_attempt_id": outcome.review_attempt_id,
                "review_attempt_fingerprint": outcome.review_attempt_fingerprint,
                "review_claim_id": outcome.review_claim_id,
                "review_claim_fingerprint": outcome.review_claim_fingerprint,
                "preflight_id": outcome.preflight_id,
                "preflight_fingerprint": outcome.preflight_fingerprint,
                "source_candidate_diff_id": outcome.source_candidate_diff_id,
                "source_candidate_diff_fingerprint": (
                    outcome.source_candidate_diff_fingerprint
                ),
                "source_candidate_diff_sha256": outcome.source_candidate_diff_sha256,
                "review_prompt_sha256": outcome.review_prompt_sha256,
                "review_prompt_bytes": outcome.review_prompt_bytes,
                "requested_reviewer_executor": outcome.requested_reviewer_executor,
                "authority": outcome.authority,
                "exact_task_id": outcome.exact_task_id,
                "exact_run_id": outcome.exact_run_id,
                "rework_attempt_index": outcome.rework_attempt_index,
                "review_scope_paths": outcome.review_scope_paths,
                "adapter_result": (
                    outcome.adapter_result.model_dump(mode="python")
                    if outcome.adapter_result is not None
                    else None
                ),
                "safe_error_code": outcome.safe_error_code,
            }
        )

    @staticmethod
    def persisted_review_invocation_outcome_message_is_valid(
        message: ProjectDirectorMessage,
        outcome: ProjectDirectorBoundedReworkReviewInvocationOutcome,
    ) -> bool:
        """Expose exact H-B marker/message validation to readonly consumers."""

        return ProjectDirectorBoundedReworkReviewExecutionService._outcome_message_valid(
            message,
            outcome,
        )

    def _persisted_attempt_and_outcome_fingerprints_valid(
        self,
        *,
        attempt: ProjectDirectorBoundedReworkReviewInvocationAttempt,
        outcome: ProjectDirectorBoundedReworkReviewInvocationOutcome,
        current: RevalidatedProjectDirectorBoundedReworkReviewClaim,
    ) -> bool:
        if not self._persisted_attempt_fingerprint_valid(
            attempt=attempt,
            current=current,
        ):
            return False
        expected_attempt_replay_key = attempt.review_attempt_replay_key
        expected_outcome_replay_key = (
            ProjectDirectorBoundedReworkReviewInvocationOutcome.compute_outcome_replay_key(
                review_attempt_replay_key=expected_attempt_replay_key,
                source_candidate_diff_sha256=outcome.source_candidate_diff_sha256,
                review_prompt_sha256=outcome.review_prompt_sha256,
                invocation_ordinal=outcome.invocation_ordinal,
            )
        )
        return bool(
            outcome.review_outcome_replay_key == expected_outcome_replay_key
            and outcome.review_outcome_id
            == uuid5(P25_BOUNDED_REWORK_REVIEW_OUTCOME_NAMESPACE, expected_attempt_replay_key)
            and outcome.review_outcome_fingerprint == outcome.compute_fingerprint()
            and outcome.review_result_fingerprint
            == self.rebuild_persisted_review_result_fingerprint(outcome)
        )

    @staticmethod
    def _persisted_attempt_fingerprint_valid(
        *,
        attempt: ProjectDirectorBoundedReworkReviewInvocationAttempt,
        current: RevalidatedProjectDirectorBoundedReworkReviewClaim,
    ) -> bool:
        if current.review_claim is None:
            return False
        expected_attempt_replay_key = (
            ProjectDirectorBoundedReworkReviewInvocationAttempt.compute_attempt_replay_key(
                review_claim_replay_key=current.review_claim.review_claim_replay_key,
                invocation_ordinal=current.review_claim.invocation_ordinal,
            )
        )
        return bool(
            attempt.review_attempt_replay_key == expected_attempt_replay_key
            and attempt.review_attempt_id
            == uuid5(P25_BOUNDED_REWORK_REVIEW_ATTEMPT_NAMESPACE, expected_attempt_replay_key)
            and attempt.review_attempt_fingerprint == attempt.compute_fingerprint()
        )

    def _validated_outcome_domain_gate(
        self,
        outcome: ProjectDirectorBoundedReworkReviewInvocationOutcome,
    ) -> bool:
        if (
            outcome.outcome_status != "validated_output"
            or outcome.adapter_result is None
            or outcome.adapter_result.adapter_status != "validated_output"
            or outcome.recovery_required is not False
            or outcome.human_escalation_required is not False
            or outcome.safe_error_code is not None
            or outcome.blocked_reasons
            or not self._is_sha256(outcome.review_semantic_fingerprint)
        ):
            return False
        try:
            adapter_result = (
                ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult.model_validate(
                    outcome.adapter_result.model_dump(mode="python")
                )
            )
        except (TypeError, ValueError, ValidationError):
            return False
        return bool(
            adapter_result == outcome.adapter_result
            and outcome.review_semantic_fingerprint
            == self._review_semantic_fingerprint(
                adapter_result=adapter_result,
                source_candidate_diff_sha256=outcome.source_candidate_diff_sha256,
                review_scope_paths=outcome.review_scope_paths,
            )
        )

    @staticmethod
    def _is_sha256(value: Any) -> bool:
        if not isinstance(value, str) or len(value) != 64:
            return False
        try:
            int(value, 16)
        except ValueError:
            return False
        return value == value.lower()

    @staticmethod
    def _revalidated_outcome_result(
        *,
        status: RevalidatedBoundedReworkReviewOutcomeStatus,
        attempt: ProjectDirectorBoundedReworkReviewInvocationAttempt | None = None,
        attempt_message: ProjectDirectorMessage | None = None,
        outcome: ProjectDirectorBoundedReworkReviewInvocationOutcome | None = None,
        outcome_message: ProjectDirectorMessage | None = None,
        current: RevalidatedProjectDirectorBoundedReworkReviewClaim | None = None,
        blocked_reasons: tuple[str, ...] = (),
    ) -> RevalidatedProjectDirectorBoundedReworkReviewOutcome:
        return RevalidatedProjectDirectorBoundedReworkReviewOutcome(
            status=status,
            review_attempt=attempt,
            review_attempt_message=attempt_message,
            review_outcome=outcome,
            review_outcome_message=outcome_message,
            preflight=current.preflight if current is not None else None,
            review_claim=current.review_claim if current is not None else None,
            candidate_diff=current.candidate_diff if current is not None else None,
            candidate_manifest=(
                current.candidate_manifest if current is not None else None
            ),
            package=current.package if current is not None else None,
            blocked_reasons=blocked_reasons,
        )

    def _attempt_replay_state(
        self,
        *,
        history: _PersistedReviewExecutionHistory,
        current: RevalidatedProjectDirectorBoundedReworkReviewClaim,
    ) -> ExecutedProjectDirectorBoundedReworkReadonlyReview | None:
        if current.review_claim is None:
            raise _Blocked("history_invalid")
        attempt_entry = self._attempt_from_history(
            history=history,
            review_claim_id=current.review_claim.review_claim_id,
        )
        outcome_entry = self._outcome_from_history(
            history=history,
            review_claim_id=current.review_claim.review_claim_id,
        )
        if outcome_entry is not None and attempt_entry is None:
            raise _Blocked("history_invalid")
        if outcome_entry is not None:
            assert attempt_entry is not None
            attempt_message, attempt = attempt_entry
            outcome_message, outcome = outcome_entry
            if not self._outcome_binds_current(
                outcome=outcome,
                attempt=attempt,
                current=current,
            ):
                raise _Blocked("history_invalid")
            return ExecutedProjectDirectorBoundedReworkReadonlyReview(
                status="review_outcome_replayed",
                review_attempt=attempt,
                review_attempt_message=attempt_message,
                review_outcome=outcome,
                review_outcome_message=outcome_message,
                blocked_reasons=(),
            )
        if attempt_entry is not None:
            attempt_message, attempt = attempt_entry
            if not self._attempt_binds_current(attempt=attempt, current=current):
                raise _Blocked("history_invalid")
            return self._recovery_required(
                attempt=attempt,
                attempt_message=attempt_message,
            )
        return None

    @staticmethod
    def _attempt_from_history(
        *,
        history: _PersistedReviewExecutionHistory,
        review_claim_id: UUID,
    ) -> tuple[
        ProjectDirectorMessage,
        ProjectDirectorBoundedReworkReviewInvocationAttempt,
    ] | None:
        matches = [item for item in history.attempts if item[1].review_claim_id == review_claim_id]
        if len(matches) > 1:
            raise _Blocked("history_invalid")
        return matches[0] if matches else None

    @staticmethod
    def _outcome_from_history(
        *,
        history: _PersistedReviewExecutionHistory,
        review_claim_id: UUID,
    ) -> tuple[
        ProjectDirectorMessage,
        ProjectDirectorBoundedReworkReviewInvocationOutcome,
    ] | None:
        matches = [item for item in history.outcomes if item[1].review_claim_id == review_claim_id]
        if len(matches) > 1:
            raise _Blocked("history_invalid")
        return matches[0] if matches else None

    @staticmethod
    def _same_revalidated_claim_lineage(
        left: RevalidatedProjectDirectorBoundedReworkReviewClaim,
        right: RevalidatedProjectDirectorBoundedReworkReviewClaim,
    ) -> bool:
        return bool(
            left.preflight == right.preflight
            and left.review_claim == right.review_claim
            and left.package == right.package
            and left.reservation == right.reservation
            and left.invocation_claim == right.invocation_claim
            and left.invocation_outcome == right.invocation_outcome
            and left.candidate_manifest == right.candidate_manifest
            and left.candidate_diff == right.candidate_diff
        )

    @staticmethod
    def _attempt_binds_current(
        *,
        attempt: ProjectDirectorBoundedReworkReviewInvocationAttempt,
        current: RevalidatedProjectDirectorBoundedReworkReviewClaim,
    ) -> bool:
        return bool(
            current.preflight is not None
            and current.review_claim is not None
            and current.candidate_diff is not None
            and attempt.review_claim_id == current.review_claim.review_claim_id
            and attempt.review_claim_fingerprint
            == current.review_claim.review_claim_fingerprint
            and attempt.review_claim_replay_key
            == current.review_claim.review_claim_replay_key
            and attempt.review_claim_token_fingerprint
            == hashlib.sha256(
                current.review_claim.review_claim_token.encode("utf-8")
            ).hexdigest()
            and attempt.preflight_id == current.preflight.preflight_id
            and attempt.preflight_fingerprint == current.preflight.preflight_fingerprint
            and attempt.source_candidate_diff_message_id
            == current.candidate_diff.candidate_diff_id
            and attempt.source_candidate_diff_id
            == current.candidate_diff.candidate_diff_id
            and attempt.source_candidate_diff_fingerprint
            == current.candidate_diff.candidate_diff_fingerprint
            and attempt.source_candidate_diff_sha256
            == current.candidate_diff.new_diff_sha256
            and attempt.source_outcome_id == current.candidate_diff.source_outcome_id
            and attempt.source_attempt_id == current.candidate_diff.source_attempt_id
            and attempt.source_package_id == current.candidate_diff.source_package_id
            and attempt.authority == current.review_claim.authority
            and attempt.exact_task_id == current.review_claim.exact_task_id
            and attempt.exact_run_id == current.review_claim.exact_run_id
            and attempt.rework_attempt_index
            == current.review_claim.rework_attempt_index
            and attempt.rework_attempt_limit
            == current.review_claim.rework_attempt_limit
            and attempt.review_prompt_sha256 == current.preflight.review_prompt_sha256
            and attempt.review_prompt_bytes == current.preflight.review_prompt_bytes
            and attempt.requested_reviewer_executor
            == current.preflight.requested_reviewer_executor
            and attempt.review_output_schema_version
            == current.preflight.review_output_schema_version
            and attempt.invocation_ordinal == current.preflight.invocation_ordinal
        )

    def _outcome_binds_current(
        self,
        *,
        outcome: ProjectDirectorBoundedReworkReviewInvocationOutcome,
        attempt: ProjectDirectorBoundedReworkReviewInvocationAttempt,
        current: RevalidatedProjectDirectorBoundedReworkReviewClaim,
    ) -> bool:
        return bool(
            self._attempt_binds_current(attempt=attempt, current=current)
            and current.preflight is not None
            and current.review_claim is not None
            and current.candidate_diff is not None
            and current.candidate_manifest is not None
            and current.invocation_outcome is not None
            and outcome.review_attempt_id == attempt.review_attempt_id
            and outcome.review_attempt_fingerprint == attempt.review_attempt_fingerprint
            and outcome.review_attempt_replay_key == attempt.review_attempt_replay_key
            and outcome.review_claim_id == current.review_claim.review_claim_id
            and outcome.review_claim_fingerprint
            == current.review_claim.review_claim_fingerprint
            and outcome.preflight_id == current.preflight.preflight_id
            and outcome.preflight_fingerprint == current.preflight.preflight_fingerprint
            and outcome.source_candidate_diff_message_id
            == current.candidate_diff.candidate_diff_id
            and outcome.source_candidate_diff_id
            == current.candidate_diff.candidate_diff_id
            and outcome.source_candidate_diff_fingerprint
            == current.candidate_diff.candidate_diff_fingerprint
            and outcome.source_candidate_diff_sha256
            == current.candidate_diff.new_diff_sha256
            and outcome.source_candidate_manifest_id
            == current.candidate_manifest.candidate_manifest_id
            and outcome.source_candidate_manifest_fingerprint
            == current.candidate_manifest.candidate_manifest_fingerprint
            and outcome.source_executor_outcome_id == current.invocation_outcome.outcome_id
            and outcome.source_package_id == current.review_claim.source_package_id
            and outcome.source_attempt_id == current.review_claim.source_attempt_id
            and outcome.authority == current.review_claim.authority
            and outcome.exact_task_id == current.review_claim.exact_task_id
            and outcome.exact_run_id == current.review_claim.exact_run_id
            and outcome.rework_attempt_index
            == current.review_claim.rework_attempt_index
            and outcome.rework_attempt_limit
            == current.review_claim.rework_attempt_limit
            and outcome.review_prompt_sha256 == current.preflight.review_prompt_sha256
            and outcome.review_prompt_bytes == current.preflight.review_prompt_bytes
            and outcome.review_scope_paths == current.preflight.review_scope_paths
            and outcome.requested_reviewer_executor
            == current.preflight.requested_reviewer_executor
            and outcome.review_output_schema_version
            == current.preflight.review_output_schema_version
            and outcome.invocation_ordinal == current.preflight.invocation_ordinal
        )

    def _build_attempt_message(
        self,
        attempt: ProjectDirectorBoundedReworkReviewInvocationAttempt,
    ) -> ProjectDirectorMessage:
        return ProjectDirectorMessage(
            id=attempt.review_attempt_id,
            session_id=attempt.authority.session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content=(
                "P25 bounded rework review attempt reserved: "
                f"{attempt.review_attempt_id} claim {attempt.review_claim_id} "
                "call_reserved reviewer_call_attempted=false"
            ),
            sequence_no=self._message_repository.get_next_sequence_no(
                session_id=attempt.authority.session_id
            ),
            intent=P25_BOUNDED_REWORK_REVIEW_ATTEMPT_INTENT,
            related_project_id=attempt.authority.project_id,
            related_task_id=attempt.exact_task_id,
            source=ProjectDirectorMessageSource.SYSTEM,
            source_detail=P25_BOUNDED_REWORK_REVIEW_ATTEMPT_SOURCE_DETAIL,
            suggested_actions=[
                {
                    "type": P25_BOUNDED_REWORK_REVIEW_ATTEMPT_ACTION_TYPE,
                    **attempt.model_dump(mode="json"),
                }
            ],
            requires_confirmation=False,
            risk_level=ProjectDirectorMessageRiskLevel.HIGH,
            forbidden_actions_detected=list(_P25_H_ATTEMPT_FALSE_BOUNDARIES),
            token_count=None,
            estimated_cost=None,
            created_at=attempt.created_at,
        )

    def _build_outcome_message(
        self,
        outcome: ProjectDirectorBoundedReworkReviewInvocationOutcome,
    ) -> ProjectDirectorMessage:
        summary = self._safe_outcome_summary(outcome)
        verdict = ""
        if (
            outcome.outcome_status == "validated_output"
            and outcome.adapter_result is not None
            and outcome.adapter_result.verdict is not None
        ):
            verdict = f" verdict {outcome.adapter_result.verdict}"
        return ProjectDirectorMessage(
            id=outcome.review_outcome_id,
            session_id=outcome.authority.session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content=(
                "P25 bounded rework review outcome persisted: "
                f"{outcome.review_outcome_id} attempt {outcome.review_attempt_id} "
                f"status {outcome.outcome_status}{verdict} summary {summary}"
            ),
            sequence_no=self._message_repository.get_next_sequence_no(
                session_id=outcome.authority.session_id
            ),
            intent=P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT,
            related_project_id=outcome.authority.project_id,
            related_task_id=outcome.exact_task_id,
            source=ProjectDirectorMessageSource.SYSTEM,
            source_detail=P25_BOUNDED_REWORK_REVIEW_OUTCOME_SOURCE_DETAIL,
            suggested_actions=[
                {
                    "type": P25_BOUNDED_REWORK_REVIEW_OUTCOME_ACTION_TYPE,
                    **outcome.model_dump(mode="json"),
                }
            ],
            requires_confirmation=False,
            risk_level=ProjectDirectorMessageRiskLevel.HIGH,
            forbidden_actions_detected=list(_P25_H_OUTCOME_FALSE_BOUNDARIES),
            token_count=None,
            estimated_cost=None,
            created_at=outcome.created_at,
        )

    @staticmethod
    def _safe_outcome_summary(
        outcome: ProjectDirectorBoundedReworkReviewInvocationOutcome,
    ) -> str:
        if outcome.outcome_status == "validated_output":
            return "validated_review_output"
        if outcome.outcome_status == "blocked":
            return "review_output_blocked"
        return "reviewer_execution_raised"

    def _load_history(self, session_id: UUID) -> _PersistedReviewExecutionHistory:
        attempts: list[
            tuple[ProjectDirectorMessage, ProjectDirectorBoundedReworkReviewInvocationAttempt]
        ] = []
        outcomes: list[
            tuple[ProjectDirectorMessage, ProjectDirectorBoundedReworkReviewInvocationOutcome]
        ] = []
        for message in self._iter_session_messages(session_id):
            action = self._p25_h_b_action(message)
            if action is None:
                continue
            schema_version = action.get("schema_version")
            payload = dict(action)
            payload.pop("type", None)
            try:
                if schema_version == P25_BOUNDED_REWORK_REVIEW_ATTEMPT_SCHEMA_VERSION:
                    attempt = (
                        ProjectDirectorBoundedReworkReviewInvocationAttempt.model_validate(
                            payload
                        )
                    )
                    if not self._attempt_message_valid(message, attempt):
                        raise _Blocked("history_invalid")
                    attempts.append((message, attempt))
                elif schema_version == P25_BOUNDED_REWORK_REVIEW_OUTCOME_SCHEMA_VERSION:
                    outcome = (
                        ProjectDirectorBoundedReworkReviewInvocationOutcome.model_validate(
                            payload
                        )
                    )
                    if not self._outcome_message_valid(message, outcome):
                        raise _Blocked("history_invalid")
                    outcomes.append((message, outcome))
                else:
                    raise _Blocked("history_invalid")
            except _Blocked:
                raise
            except (TypeError, ValueError, ValidationError) as exc:
                raise _Blocked("history_invalid") from exc
        history = _PersistedReviewExecutionHistory(
            attempts=tuple(attempts),
            outcomes=tuple(outcomes),
        )
        self._validate_history(history)
        return history

    def _iter_session_messages(self, session_id: UUID) -> list[ProjectDirectorMessage]:
        messages: list[ProjectDirectorMessage] = []
        before_message_id: UUID | None = None
        while True:
            page, has_more = self._message_repository.list_by_session_id(
                session_id=session_id,
                limit=_PAGE_SIZE,
                before_message_id=before_message_id,
            )
            messages.extend(page)
            if not has_more:
                return sorted(messages, key=lambda item: item.sequence_no)
            if not page:
                raise _Blocked("history_invalid")
            before_message_id = page[0].id

    @staticmethod
    def _p25_h_b_action(message: ProjectDirectorMessage) -> dict[str, Any] | None:
        attempt_marked = (
            message.intent == P25_BOUNDED_REWORK_REVIEW_ATTEMPT_INTENT
            or message.source_detail == P25_BOUNDED_REWORK_REVIEW_ATTEMPT_SOURCE_DETAIL
            or any(
                isinstance(action, dict)
                and (
                    action.get("type") == P25_BOUNDED_REWORK_REVIEW_ATTEMPT_ACTION_TYPE
                    or action.get("schema_version")
                    == P25_BOUNDED_REWORK_REVIEW_ATTEMPT_SCHEMA_VERSION
                )
                for action in message.suggested_actions
            )
        )
        outcome_marked = (
            message.intent == P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT
            or message.source_detail == P25_BOUNDED_REWORK_REVIEW_OUTCOME_SOURCE_DETAIL
            or any(
                isinstance(action, dict)
                and (
                    action.get("type") == P25_BOUNDED_REWORK_REVIEW_OUTCOME_ACTION_TYPE
                    or action.get("schema_version")
                    == P25_BOUNDED_REWORK_REVIEW_OUTCOME_SCHEMA_VERSION
                )
                for action in message.suggested_actions
            )
        )
        if not attempt_marked and not outcome_marked:
            return None
        if attempt_marked and outcome_marked:
            raise _Blocked("history_invalid")
        if (
            message.role != ProjectDirectorMessageRole.ASSISTANT
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.requires_confirmation is not False
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
            or message.token_count is not None
            or message.estimated_cost is not None
            or len(message.suggested_actions) != 1
            or not isinstance(message.suggested_actions[0], dict)
        ):
            raise _Blocked("history_invalid")
        action = message.suggested_actions[0]
        if attempt_marked:
            if (
                message.intent != P25_BOUNDED_REWORK_REVIEW_ATTEMPT_INTENT
                or message.source_detail
                != P25_BOUNDED_REWORK_REVIEW_ATTEMPT_SOURCE_DETAIL
                or action.get("type")
                != P25_BOUNDED_REWORK_REVIEW_ATTEMPT_ACTION_TYPE
                or action.get("schema_version")
                != P25_BOUNDED_REWORK_REVIEW_ATTEMPT_SCHEMA_VERSION
            ):
                raise _Blocked("history_invalid")
            return action
        if (
            message.intent != P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT
            or message.source_detail != P25_BOUNDED_REWORK_REVIEW_OUTCOME_SOURCE_DETAIL
            or action.get("type") != P25_BOUNDED_REWORK_REVIEW_OUTCOME_ACTION_TYPE
            or action.get("schema_version")
            != P25_BOUNDED_REWORK_REVIEW_OUTCOME_SCHEMA_VERSION
        ):
            raise _Blocked("history_invalid")
        return action

    @staticmethod
    def _validate_history(history: _PersistedReviewExecutionHistory) -> None:
        attempt_ids = [item[1].review_attempt_id for item in history.attempts]
        attempt_replay_keys = [item[1].review_attempt_replay_key for item in history.attempts]
        attempt_claim_ids = [item[1].review_claim_id for item in history.attempts]
        outcome_ids = [item[1].review_outcome_id for item in history.outcomes]
        outcome_replay_keys = [item[1].review_outcome_replay_key for item in history.outcomes]
        outcome_attempt_ids = [item[1].review_attempt_id for item in history.outcomes]
        outcome_claim_ids = [item[1].review_claim_id for item in history.outcomes]
        groups = (
            attempt_ids,
            attempt_replay_keys,
            attempt_claim_ids,
            outcome_ids,
            outcome_replay_keys,
            outcome_attempt_ids,
            outcome_claim_ids,
        )
        if any(len(values) != len(set(values)) for values in groups):
            raise _Blocked("history_invalid")
        attempts = {item[1].review_attempt_id: item[1] for item in history.attempts}
        for _, outcome in history.outcomes:
            attempt = attempts.get(outcome.review_attempt_id)
            if (
                attempt is None
                or outcome.review_attempt_fingerprint
                != attempt.review_attempt_fingerprint
                or outcome.review_attempt_replay_key
                != attempt.review_attempt_replay_key
                or outcome.review_claim_id != attempt.review_claim_id
                or outcome.review_claim_fingerprint
                != attempt.review_claim_fingerprint
                or outcome.preflight_id != attempt.preflight_id
                or outcome.preflight_fingerprint != attempt.preflight_fingerprint
            ):
                raise _Blocked("history_invalid")

    @staticmethod
    def _attempt_message_valid(
        message: ProjectDirectorMessage,
        attempt: ProjectDirectorBoundedReworkReviewInvocationAttempt,
    ) -> bool:
        expected_action = {
            "type": P25_BOUNDED_REWORK_REVIEW_ATTEMPT_ACTION_TYPE,
            **attempt.model_dump(mode="json"),
        }
        return bool(
            message.id == attempt.review_attempt_id
            and message.created_at == attempt.created_at
            and message.session_id == attempt.authority.session_id
            and message.related_project_id == attempt.authority.project_id
            and message.related_task_id == attempt.exact_task_id
            and message.role == ProjectDirectorMessageRole.ASSISTANT
            and message.source == ProjectDirectorMessageSource.SYSTEM
            and message.intent == P25_BOUNDED_REWORK_REVIEW_ATTEMPT_INTENT
            and message.source_detail
            == P25_BOUNDED_REWORK_REVIEW_ATTEMPT_SOURCE_DETAIL
            and message.content
            == (
                "P25 bounded rework review attempt reserved: "
                f"{attempt.review_attempt_id} claim {attempt.review_claim_id} "
                "call_reserved reviewer_call_attempted=false"
            )
            and message.suggested_actions == [expected_action]
            and message.requires_confirmation is False
            and message.risk_level == ProjectDirectorMessageRiskLevel.HIGH
            and tuple(message.forbidden_actions_detected)
            == _P25_H_ATTEMPT_FALSE_BOUNDARIES
            and message.token_count is None
            and message.estimated_cost is None
        )

    @staticmethod
    def _outcome_message_valid(
        message: ProjectDirectorMessage,
        outcome: ProjectDirectorBoundedReworkReviewInvocationOutcome,
    ) -> bool:
        expected_action = {
            "type": P25_BOUNDED_REWORK_REVIEW_OUTCOME_ACTION_TYPE,
            **outcome.model_dump(mode="json"),
        }
        verdict = ""
        if (
            outcome.outcome_status == "validated_output"
            and outcome.adapter_result is not None
            and outcome.adapter_result.verdict is not None
        ):
            verdict = f" verdict {outcome.adapter_result.verdict}"
        return bool(
            message.id == outcome.review_outcome_id
            and message.created_at == outcome.created_at
            and message.session_id == outcome.authority.session_id
            and message.related_project_id == outcome.authority.project_id
            and message.related_task_id == outcome.exact_task_id
            and message.role == ProjectDirectorMessageRole.ASSISTANT
            and message.source == ProjectDirectorMessageSource.SYSTEM
            and message.intent == P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT
            and message.source_detail
            == P25_BOUNDED_REWORK_REVIEW_OUTCOME_SOURCE_DETAIL
            and message.content
            == (
                "P25 bounded rework review outcome persisted: "
                f"{outcome.review_outcome_id} attempt {outcome.review_attempt_id} "
                f"status {outcome.outcome_status}{verdict} summary "
                f"{ProjectDirectorBoundedReworkReviewExecutionService._safe_outcome_summary(outcome)}"
            )
            and message.suggested_actions == [expected_action]
            and message.requires_confirmation is False
            and message.risk_level == ProjectDirectorMessageRiskLevel.HIGH
            and tuple(message.forbidden_actions_detected)
            == _P25_H_OUTCOME_FALSE_BOUNDARIES
            and message.token_count is None
            and message.estimated_cost is None
        )

    def _rollback_read_transaction(self) -> None:
        if self._message_repository._session.in_transaction():
            self._message_repository._session.rollback()

    def _cleanup_local_read_transaction(
        self,
        *,
        caller_had_transaction: bool,
    ) -> None:
        if (
            not caller_had_transaction
            and self._message_repository._session.in_transaction()
        ):
            self._message_repository._session.rollback()

    @staticmethod
    def _blocked(
        reason: BoundedReworkBlockedReason,
    ) -> ExecutedProjectDirectorBoundedReworkReadonlyReview:
        return ExecutedProjectDirectorBoundedReworkReadonlyReview(
            status="blocked",
            review_attempt=None,
            review_attempt_message=None,
            review_outcome=None,
            review_outcome_message=None,
            blocked_reasons=(reason,),
        )

    @staticmethod
    def _recovery_required(
        *,
        attempt: ProjectDirectorBoundedReworkReviewInvocationAttempt,
        attempt_message: ProjectDirectorMessage,
    ) -> ExecutedProjectDirectorBoundedReworkReadonlyReview:
        return ExecutedProjectDirectorBoundedReworkReadonlyReview(
            status="recovery_required",
            review_attempt=attempt,
            review_attempt_message=attempt_message,
            review_outcome=None,
            review_outcome_message=None,
            blocked_reasons=("claim_without_outcome",),
        )


__all__ = (
    "ExecutedProjectDirectorBoundedReworkReadonlyReview",
    "P25_BOUNDED_REWORK_REVIEW_ATTEMPT_ACTION_TYPE",
    "P25_BOUNDED_REWORK_REVIEW_ATTEMPT_INTENT",
    "P25_BOUNDED_REWORK_REVIEW_ATTEMPT_SOURCE_DETAIL",
    "P25_BOUNDED_REWORK_REVIEW_OUTCOME_ACTION_TYPE",
    "P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT",
    "P25_BOUNDED_REWORK_REVIEW_OUTCOME_SOURCE_DETAIL",
    "ProjectDirectorBoundedReworkReviewExecutionService",
    "RevalidatedProjectDirectorBoundedReworkReviewOutcome",
)
