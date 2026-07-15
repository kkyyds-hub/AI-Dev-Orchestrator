"""Persist one replay-safe P25-I-B bounded rework convergence decision."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal
from uuid import UUID, uuid5

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.domain._base import utc_now
from app.domain.project_director_bounded_rework_candidate_diff import (
    ProjectDirectorBoundedReworkCandidateDiff,
)
from app.domain.project_director_bounded_rework_convergence import (
    P25_BOUNDED_REWORK_CONVERGENCE_DECISION_NAMESPACE,
    P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SCHEMA_VERSION,
    ProjectDirectorBoundedReworkConvergenceDecision,
)
from app.domain.project_director_bounded_rework_contract import (
    compute_p25_contract_sha256,
)
from app.domain.project_director_bounded_rework_instruction_package import (
    ProjectDirectorBoundedReworkInstructionPackage,
)
from app.domain.project_director_bounded_rework_review_reentry import (
    ProjectDirectorBoundedReworkReviewInvocationOutcome,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_post_review_automation import (
    ProjectDirectorPostReviewAutomationResult,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.services.project_director_bounded_rework_candidate_diff_service import (
    ProjectDirectorBoundedReworkCandidateDiffService,
    RevalidatedProjectDirectorBoundedReworkCandidateDiff,
)
from app.services.project_director_bounded_rework_review_execution_service import (
    ProjectDirectorBoundedReworkReviewExecutionService,
    RevalidatedProjectDirectorBoundedReworkReviewOutcome,
)
from app.services.project_director_post_review_automation_service import (
    ProjectDirectorPostReviewAutomationService,
    RevalidatedProjectDirectorPostReviewSummary,
)


P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SOURCE_DETAIL = (
    "p25_i_b_bounded_rework_convergence_decided"
)
P25_BOUNDED_REWORK_CONVERGENCE_DECISION_ACTION_TYPE = (
    "p25_bounded_rework_convergence_decision_record"
)
P25_BOUNDED_REWORK_CONVERGENCE_DECISION_INTENT = (
    "bounded_rework_convergence_decision"
)

_CANONICAL_BLOCKING_FINDINGS_SCHEMA_VERSION = (
    "p25-i-b-canonical-blocking-findings.v1"
)
_PAGE_SIZE = 200
_FALSE_BOUNDARIES = (
    "next_p23_intent_created=false",
    "next_p23_consumption_created=false",
    "next_package_created=false",
    "next_reservation_created=false",
    "next_claim_created=false",
    "executor_called=false",
    "reviewer_called=false",
    "provider_called=false",
    "task_created=false",
    "run_created=false",
    "worker_started=false",
    "main_project_file_written=false",
    "sandbox_file_written=false",
    "patch_applied=false",
    "git_write_performed=false",
    "product_runtime_git_write_allowed=false",
)

ConvergencePersistenceStatus = Literal[
    "decision_persisted",
    "decision_replayed",
    "recovery_required",
    "blocked",
]


@dataclass(frozen=True, slots=True)
class ProjectDirectorBoundedReworkConvergenceResult:
    status: ConvergencePersistenceStatus
    decision: ProjectDirectorBoundedReworkConvergenceDecision | None
    decision_message: ProjectDirectorMessage | None
    candidate_diff: ProjectDirectorBoundedReworkCandidateDiff | None
    candidate_diff_message: ProjectDirectorMessage | None
    review_outcome: ProjectDirectorBoundedReworkReviewInvocationOutcome | None
    review_outcome_message: ProjectDirectorMessage | None
    p22_summary: ProjectDirectorPostReviewAutomationResult | None
    p22_summary_message: ProjectDirectorMessage | None
    blocked_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RevalidatedProjectDirectorBoundedReworkNextAttemptDecision:
    decision: ProjectDirectorBoundedReworkConvergenceDecision | None
    decision_message: ProjectDirectorMessage | None
    candidate_diff: ProjectDirectorBoundedReworkCandidateDiff | None
    candidate_diff_message: ProjectDirectorMessage | None
    review_outcome: ProjectDirectorBoundedReworkReviewInvocationOutcome | None
    review_outcome_message: ProjectDirectorMessage | None
    p22_summary: ProjectDirectorPostReviewAutomationResult | None
    p22_summary_message: ProjectDirectorMessage | None
    blocked_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RevalidatedProjectDirectorBoundedReworkTerminalDecision:
    decision: ProjectDirectorBoundedReworkConvergenceDecision | None
    decision_message: ProjectDirectorMessage | None
    package: ProjectDirectorBoundedReworkInstructionPackage | None
    candidate_diff: ProjectDirectorBoundedReworkCandidateDiff | None
    candidate_diff_message: ProjectDirectorMessage | None
    review_outcome: ProjectDirectorBoundedReworkReviewInvocationOutcome | None
    review_outcome_message: ProjectDirectorMessage | None
    p22_summary: ProjectDirectorPostReviewAutomationResult | None
    p22_summary_message: ProjectDirectorMessage | None
    blocked_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _DecisionEvaluation:
    status: Literal["ready", "recovery_required", "blocked"]
    decision: ProjectDirectorBoundedReworkConvergenceDecision | None
    candidate: RevalidatedProjectDirectorBoundedReworkCandidateDiff
    review: RevalidatedProjectDirectorBoundedReworkReviewOutcome | None = None
    p22: RevalidatedProjectDirectorPostReviewSummary | None = None
    blocked_reasons: tuple[str, ...] = ()


class _Blocked(RuntimeError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def compute_canonical_blocking_findings_fingerprint(
    findings: Iterable[Any],
) -> str:
    """Hash the order-independent medium/high blocking-finding projection."""

    finding_hashes: list[str] = []
    for finding in findings:
        severity = getattr(finding, "severity", None)
        if severity not in {"medium", "high"}:
            continue
        title = getattr(finding, "title", None)
        evidence_paths = getattr(finding, "evidence_paths", None)
        recommended_action = getattr(finding, "recommended_action", None)
        if (
            not isinstance(title, str)
            or not title.strip()
            or not isinstance(recommended_action, str)
            or not recommended_action.strip()
            or not isinstance(evidence_paths, (list, tuple))
            or not evidence_paths
            or any(not isinstance(path, str) or not path for path in evidence_paths)
        ):
            raise ValueError("blocking finding projection is invalid")
        projection = {
            "severity": severity,
            "title": title,
            "evidence_paths": sorted(evidence_paths),
            "recommended_action": recommended_action,
        }
        finding_hashes.append(compute_p25_contract_sha256(projection))
    return compute_p25_contract_sha256(
        {
            "schema_version": _CANONICAL_BLOCKING_FINDINGS_SCHEMA_VERSION,
            "finding_hashes": sorted(set(finding_hashes)),
        }
    )


class ProjectDirectorBoundedReworkConvergenceService:
    """Derive and append one exact convergence decision from persisted evidence."""

    def __init__(
        self,
        *,
        message_repository: ProjectDirectorMessageRepository,
        candidate_diff_service: ProjectDirectorBoundedReworkCandidateDiffService,
        review_execution_service: ProjectDirectorBoundedReworkReviewExecutionService,
        post_review_automation_service: ProjectDirectorPostReviewAutomationService,
    ) -> None:
        self._message_repository = message_repository
        self._candidate_diff_service = candidate_diff_service
        self._review_execution_service = review_execution_service
        self._post_review_automation_service = post_review_automation_service
        shared_repositories = (
            candidate_diff_service._message_repository,
            review_execution_service._message_repository,
            post_review_automation_service._message_repository,
        )
        if any(repository is not message_repository for repository in shared_repositories):
            raise ValueError("P25-I-B dependencies must share one message repository")

    def decide_bounded_rework_convergence(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_candidate_diff_message_id: UUID,
    ) -> ProjectDirectorBoundedReworkConvergenceResult:
        """Persist or replay a decision without executing any next action."""

        if self._message_repository._session.in_transaction():
            return self._empty_result("blocked", "persistence_failed")

        try:
            initial = self._evaluate(
                session_id=session_id,
                source_task_id=source_task_id,
                source_candidate_diff_message_id=source_candidate_diff_message_id,
                persistence_revalidation=False,
            )
        except SQLAlchemyError:
            self._rollback_local_read_transaction()
            return self._empty_result("recovery_required", "persistence_failed")
        except (RuntimeError, TypeError, ValueError, ValidationError):
            self._rollback_local_read_transaction()
            return self._empty_result("blocked", "history_invalid")
        if initial.status != "ready" or initial.decision is None:
            result = self._result_from_evaluation(initial)
            self._rollback_local_read_transaction()
            return result
        self._rollback_local_read_transaction()

        try:
            with self._message_repository.sqlite_immediate_transaction():
                current = self._evaluate(
                    session_id=session_id,
                    source_task_id=source_task_id,
                    source_candidate_diff_message_id=(
                        source_candidate_diff_message_id
                    ),
                    persistence_revalidation=True,
                )
                if current.status != "ready" or current.decision is None:
                    return self._result_from_evaluation(current)
                if (
                    current.decision.decision_replay_key
                    != initial.decision.decision_replay_key
                    or current.decision.decision_fingerprint
                    != initial.decision.decision_fingerprint
                ):
                    raise _Blocked("history_invalid")

                existing = self._decision_for_candidate_diff(
                    session_id=session_id,
                    source_candidate_diff_message_id=(
                        source_candidate_diff_message_id
                    ),
                    decision_replay_key=current.decision.decision_replay_key,
                )
                if existing is not None:
                    decision, message = existing
                    if (
                        decision.decision_replay_key
                        != current.decision.decision_replay_key
                    ):
                        raise _Blocked("history_invalid")
                    if (
                        decision.decision_fingerprint
                        != current.decision.decision_fingerprint
                    ):
                        raise _Blocked("convergence_decision_conflict")
                    return self._result_from_evaluation(
                        current,
                        status="decision_replayed",
                        decision=decision,
                        decision_message=message,
                    )

                decision_message = self._build_decision_message(current.decision)
                persisted_message = self._message_repository.create(decision_message)
                if persisted_message != decision_message:
                    raise _Blocked("persistence_failed")
                return self._result_from_evaluation(
                    current,
                    status="decision_persisted",
                    decision=current.decision,
                    decision_message=persisted_message,
                )
        except _Blocked as exc:
            return self._result_from_evaluation(
                initial,
                status="blocked",
                blocked_reasons=(exc.reason,),
            )
        except SQLAlchemyError:
            return self._result_from_evaluation(
                initial,
                status="recovery_required",
                blocked_reasons=("persistence_failed",),
            )
        except (RuntimeError, TypeError, ValueError, ValidationError):
            return self._result_from_evaluation(
                initial,
                status="blocked",
                blocked_reasons=("history_invalid",),
            )
        finally:
            self._rollback_local_read_transaction()

    def revalidate_next_attempt_decision_for_p22_summary(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_p22_summary_message_id: UUID,
    ) -> RevalidatedProjectDirectorBoundedReworkNextAttemptDecision:
        """Rebuild one exact persisted next-attempt decision without writing."""

        session = self._message_repository._session
        caller_transaction_active = session.in_transaction()
        try:
            matches = [
                item
                for item in self._load_decision_history(session_id)
                if item[0].source_p22_summary_message_id
                == source_p22_summary_message_id
            ]
            if not matches:
                return self._empty_next_attempt_revalidation(
                    "next_attempt_decision_missing"
                )
            if len(matches) != 1:
                return self._empty_next_attempt_revalidation("history_invalid")

            persisted, persisted_message = matches[0]
            evaluation = self._evaluate(
                session_id=session_id,
                source_task_id=source_task_id,
                source_candidate_diff_message_id=(
                    persisted.source_candidate_diff_message_id
                ),
                persistence_revalidation=True,
            )
            if evaluation.status != "ready" or evaluation.decision is None:
                return self._next_attempt_revalidation_from_evaluation(
                    evaluation,
                    decision=persisted,
                    decision_message=persisted_message,
                    blocked_reasons=("convergence_decision_conflict",),
                )

            rebuilt = evaluation.decision
            persisted_payload = persisted.model_dump(
                mode="python",
                exclude={"created_at"},
            )
            rebuilt_payload = rebuilt.model_dump(
                mode="python",
                exclude={"created_at"},
            )
            if persisted_payload != rebuilt_payload:
                return self._next_attempt_revalidation_from_evaluation(
                    evaluation,
                    decision=persisted,
                    decision_message=persisted_message,
                    blocked_reasons=("convergence_decision_conflict",),
                )

            candidate = evaluation.candidate.candidate_diff
            review = evaluation.review
            p22 = evaluation.p22
            outcome = review.review_outcome if review is not None else None
            outcome_message = (
                review.review_outcome_message if review is not None else None
            )
            summary = p22.result if p22 is not None else None
            summary_message = p22.message if p22 is not None else None
            if (
                candidate is None
                or outcome is None
                or outcome_message is None
                or summary is None
                or summary_message is None
                or persisted.source_p22_summary_message_id
                != source_p22_summary_message_id
                or summary_message.id != source_p22_summary_message_id
                or persisted.source_review_outcome_message_id
                != summary.source_review_message_id
                or persisted.source_review_outcome_message_id
                != outcome_message.id
                or persisted.source_candidate_diff_message_id
                != outcome.source_candidate_diff_message_id
                or persisted.source_candidate_diff_message_id
                != candidate.candidate_diff_id
                or persisted.source_review_result_fingerprint
                != outcome.review_result_fingerprint
                or persisted.current_review_semantic_fingerprint
                != outcome.review_semantic_fingerprint
            ):
                return self._next_attempt_revalidation_from_evaluation(
                    evaluation,
                    decision=persisted,
                    decision_message=persisted_message,
                    blocked_reasons=("convergence_decision_conflict",),
                )

            if persisted.decision_type == "CONVERGED":
                blocked_reasons = ("convergence_already_terminal",)
            elif persisted.decision_type == "ESCALATE_TO_HUMAN":
                blocked_reasons = ("convergence_requires_human_escalation",)
            elif (
                persisted.decision_type != "NEXT_ATTEMPT_ELIGIBLE"
                or persisted.decision_reason != "changed_blocking_findings"
                or not persisted.next_attempt_eligible
                or persisted.automatic_processing_terminal
                or persisted.human_escalation_required
                or persisted.next_rework_attempt_index is None
            ):
                blocked_reasons = ("convergence_decision_conflict",)
            else:
                blocked_reasons = ()
            return self._next_attempt_revalidation_from_evaluation(
                evaluation,
                decision=persisted,
                decision_message=persisted_message,
                blocked_reasons=blocked_reasons,
            )
        except _Blocked as exc:
            return self._empty_next_attempt_revalidation(exc.reason)
        except SQLAlchemyError:
            return self._empty_next_attempt_revalidation("history_invalid")
        except (RuntimeError, TypeError, ValueError, ValidationError):
            return self._empty_next_attempt_revalidation("history_invalid")
        finally:
            if not caller_transaction_active and session.in_transaction():
                session.rollback()

    def revalidate_terminal_escalation_decision(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_convergence_decision_message_id: UUID,
    ) -> RevalidatedProjectDirectorBoundedReworkTerminalDecision:
        """Rebuild one terminal decision using ordinary immutable reads."""

        return self._revalidate_terminal_escalation_decision(
            session_id=session_id,
            source_task_id=source_task_id,
            source_convergence_decision_message_id=(
                source_convergence_decision_message_id
            ),
            persistence_revalidation=False,
        )

    def revalidate_terminal_escalation_decision_for_persistence(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_convergence_decision_message_id: UUID,
    ) -> RevalidatedProjectDirectorBoundedReworkTerminalDecision:
        """Rebuild one terminal decision without owning the caller transaction."""

        if not self._message_repository._session.in_transaction():
            return self._empty_terminal_revalidation("persistence_failed")
        return self._revalidate_terminal_escalation_decision(
            session_id=session_id,
            source_task_id=source_task_id,
            source_convergence_decision_message_id=(
                source_convergence_decision_message_id
            ),
            persistence_revalidation=True,
        )

    def _revalidate_terminal_escalation_decision(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_convergence_decision_message_id: UUID,
        persistence_revalidation: bool,
    ) -> RevalidatedProjectDirectorBoundedReworkTerminalDecision:
        session = self._message_repository._session
        caller_transaction_active = session.in_transaction()
        try:
            source_message = self._message_repository.get_by_id(
                source_convergence_decision_message_id
            )
            if source_message is None:
                return self._empty_terminal_revalidation(
                    "source_convergence_decision_missing"
                )
            try:
                action = self._decision_action(source_message)
                if action is None:
                    raise _Blocked("source_convergence_decision_invalid")
                payload = dict(action)
                payload.pop("type", None)
                source_decision = (
                    ProjectDirectorBoundedReworkConvergenceDecision.model_validate(
                        payload
                    )
                )
                if not self._decision_message_valid(
                    source_message,
                    source_decision,
                ):
                    raise _Blocked("source_convergence_decision_invalid")
            except (TypeError, ValueError, ValidationError, _Blocked):
                return self._empty_terminal_revalidation(
                    "source_convergence_decision_invalid"
                )

            decisions = [
                item
                for item in self._load_decision_history(session_id)
                if item[1].id == source_convergence_decision_message_id
            ]
            if len(decisions) != 1:
                return self._empty_terminal_revalidation("history_invalid")
            persisted, persisted_message = decisions[0]
            if (
                persisted != source_decision
                or persisted.authority.session_id != session_id
                or persisted.authority.source_task_id != source_task_id
            ):
                return self._empty_terminal_revalidation(
                    "source_convergence_decision_invalid"
                )

            evaluation = self._evaluate(
                session_id=session_id,
                source_task_id=source_task_id,
                source_candidate_diff_message_id=(
                    persisted.source_candidate_diff_message_id
                ),
                persistence_revalidation=persistence_revalidation,
            )
            if evaluation.status != "ready" or evaluation.decision is None:
                reason = (
                    evaluation.blocked_reasons[0]
                    if evaluation.blocked_reasons
                    else "terminal_escalation_evidence_invalid"
                )
                return self._terminal_revalidation_from_evaluation(
                    evaluation,
                    decision=persisted,
                    decision_message=persisted_message,
                    blocked_reasons=(reason,),
                )

            rebuilt = evaluation.decision
            if persisted.model_dump(
                mode="python",
                exclude={"created_at"},
            ) != rebuilt.model_dump(mode="python", exclude={"created_at"}):
                return self._terminal_revalidation_from_evaluation(
                    evaluation,
                    decision=persisted,
                    decision_message=persisted_message,
                    blocked_reasons=("source_convergence_decision_invalid",),
                )

            if persisted.decision_type == "CONVERGED":
                blocked_reasons = ("convergence_already_terminal",)
            elif persisted.decision_type == "NEXT_ATTEMPT_ELIGIBLE":
                blocked_reasons = ("next_attempt_still_eligible",)
            elif (
                persisted.decision_type != "ESCALATE_TO_HUMAN"
                or not persisted.human_escalation_required
                or not persisted.automatic_processing_terminal
                or persisted.next_attempt_eligible
                or persisted.next_rework_attempt_index is not None
            ):
                blocked_reasons = ("source_convergence_decision_invalid",)
            else:
                blocked_reasons = ()
            return self._terminal_revalidation_from_evaluation(
                evaluation,
                decision=persisted,
                decision_message=persisted_message,
                blocked_reasons=blocked_reasons,
            )
        except _Blocked:
            return self._empty_terminal_revalidation("history_invalid")
        except SQLAlchemyError:
            return self._empty_terminal_revalidation("persistence_failed")
        except (RuntimeError, TypeError, ValueError, ValidationError):
            return self._empty_terminal_revalidation("history_invalid")
        finally:
            if (
                not persistence_revalidation
                and not caller_transaction_active
                and session.in_transaction()
            ):
                session.rollback()

    def _evaluate(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_candidate_diff_message_id: UUID,
        persistence_revalidation: bool,
    ) -> _DecisionEvaluation:
        candidate = (
            self._candidate_diff_service.revalidate_persisted_candidate_diff_for_convergence_persistence(
                session_id=session_id,
                source_task_id=source_task_id,
                source_candidate_diff_message_id=source_candidate_diff_message_id,
            )
            if persistence_revalidation
            else self._candidate_diff_service.revalidate_persisted_candidate_diff_for_convergence(
                session_id=session_id,
                source_task_id=source_task_id,
                source_candidate_diff_message_id=source_candidate_diff_message_id,
            )
        )
        if candidate.blocked_reasons:
            return _DecisionEvaluation(
                status="blocked",
                decision=None,
                candidate=candidate,
                blocked_reasons=tuple(candidate.blocked_reasons),
            )
        if (
            candidate.package is None
            or candidate.invocation_outcome is None
            or candidate.candidate_diff is None
            or candidate.candidate_diff_message is None
        ):
            return _DecisionEvaluation(
                status="blocked",
                decision=None,
                candidate=candidate,
                blocked_reasons=("history_invalid",),
            )

        candidate_diff = candidate.candidate_diff
        if candidate_diff.diff_status == "non_convergence":
            try:
                decision = self._build_decision(
                    candidate=candidate,
                    review=None,
                    p22=None,
                )
            except _Blocked as exc:
                return _DecisionEvaluation(
                    status="blocked",
                    decision=None,
                    candidate=candidate,
                    blocked_reasons=(exc.reason,),
                )
            except (TypeError, ValueError, ValidationError):
                return _DecisionEvaluation(
                    status="blocked",
                    decision=None,
                    candidate=candidate,
                    blocked_reasons=("history_invalid",),
                )
            return _DecisionEvaluation(
                status="ready",
                decision=decision,
                candidate=candidate,
            )

        review = self._review_execution_service.revalidate_review_outcome_for_candidate_diff(
            session_id=session_id,
            source_task_id=source_task_id,
            source_candidate_diff_message_id=source_candidate_diff_message_id,
        )
        if review.status == "recovery_required":
            return _DecisionEvaluation(
                status="recovery_required",
                decision=None,
                candidate=candidate,
                review=review,
                blocked_reasons=review.blocked_reasons or ("claim_without_outcome",),
            )
        if (
            review.status != "validated_output"
            or review.review_outcome is None
            or review.review_outcome_message is None
        ):
            return _DecisionEvaluation(
                status="blocked",
                decision=None,
                candidate=candidate,
                review=review,
                blocked_reasons=review.blocked_reasons or ("review_reentry_failed",),
            )

        p22 = self._post_review_automation_service.revalidate_existing_post_review_summary(
            session_id=session_id,
            source_task_id=source_task_id,
            source_review_message_id=review.review_outcome_message.id,
        )
        if (
            p22.blocked_reasons
            or not p22.summary_exists
            or p22.result is None
            or p22.message is None
        ):
            return _DecisionEvaluation(
                status="blocked",
                decision=None,
                candidate=candidate,
                review=review,
                p22=p22,
                blocked_reasons=p22.blocked_reasons or ("history_invalid",),
            )
        try:
            decision = self._build_decision(
                candidate=candidate,
                review=review,
                p22=p22,
            )
        except _Blocked as exc:
            return _DecisionEvaluation(
                status="blocked",
                decision=None,
                candidate=candidate,
                review=review,
                p22=p22,
                blocked_reasons=(exc.reason,),
            )
        except (TypeError, ValueError, ValidationError):
            return _DecisionEvaluation(
                status="blocked",
                decision=None,
                candidate=candidate,
                review=review,
                p22=p22,
                blocked_reasons=("history_invalid",),
            )
        return _DecisionEvaluation(
            status="ready",
            decision=decision,
            candidate=candidate,
            review=review,
            p22=p22,
        )

    def _build_decision(
        self,
        *,
        candidate: RevalidatedProjectDirectorBoundedReworkCandidateDiff,
        review: RevalidatedProjectDirectorBoundedReworkReviewOutcome | None,
        p22: RevalidatedProjectDirectorPostReviewSummary | None,
    ) -> ProjectDirectorBoundedReworkConvergenceDecision:
        package = candidate.package
        executor_outcome = candidate.invocation_outcome
        candidate_diff = candidate.candidate_diff
        if package is None or executor_outcome is None or candidate_diff is None:
            raise _Blocked("history_invalid")
        if package.authority is None or package.rework_attempt_index is None:
            raise _Blocked("authority_invalid")

        previous_findings_fingerprint = (
            compute_canonical_blocking_findings_fingerprint(
                package.blocking_findings
            )
        )
        outcome: ProjectDirectorBoundedReworkReviewInvocationOutcome | None = None
        summary: ProjectDirectorPostReviewAutomationResult | None = None
        review_message: ProjectDirectorMessage | None = None
        p22_message: ProjectDirectorMessage | None = None
        current_findings_fingerprint: str | None = None
        semantics_changed: bool | None = None
        findings_changed: bool | None = None
        human_package_id: UUID | None = None

        if candidate_diff.diff_status == "non_convergence":
            if candidate_diff.non_convergence_reason not in {
                "empty_diff",
                "unchanged_diff",
            }:
                raise _Blocked("non_convergence")
            decision_type = "ESCALATE_TO_HUMAN"
            decision_reason = candidate_diff.non_convergence_reason
        else:
            if (
                review is None
                or p22 is None
                or review.review_outcome is None
                or review.review_outcome_message is None
                or p22.result is None
                or p22.message is None
            ):
                raise _Blocked("history_invalid")
            outcome = review.review_outcome
            review_message = review.review_outcome_message
            summary = p22.result
            p22_message = p22.message
            adapter = outcome.adapter_result
            if (
                outcome.outcome_status != "validated_output"
                or adapter is None
                or outcome.review_semantic_fingerprint is None
                or outcome.source_candidate_diff_message_id
                != candidate_diff.candidate_diff_id
                or summary.source_review_message_id != review_message.id
            ):
                raise _Blocked("history_invalid")
            current_findings_fingerprint = (
                compute_canonical_blocking_findings_fingerprint(adapter.findings)
            )
            semantics_changed = (
                outcome.review_semantic_fingerprint
                != package.authority.source_review_semantic_fingerprint
            )
            findings_changed = (
                current_findings_fingerprint != previous_findings_fingerprint
            )

            if (
                summary.orchestration_status == "waiting_for_human"
                and summary.route == "human_escalation"
                and summary.source_human_escalation_package_message_id is not None
                and adapter.risk_level == "high"
            ):
                decision_type = "ESCALATE_TO_HUMAN"
                decision_reason = "high_review_risk"
                human_package_id = (
                    summary.source_human_escalation_package_message_id
                )
            elif (
                summary.orchestration_status == "ready_for_future_transition"
                and summary.disposition_type == "AUTO_CONTINUE"
                and summary.route == "automatic_continuation"
                and adapter.verdict
                in {"no_blocking_findings", "non_blocking_findings"}
            ):
                decision_type = "CONVERGED"
                decision_reason = "review_converged"
            elif (
                summary.orchestration_status == "ready_for_future_transition"
                and summary.disposition_type == "AUTO_REWORK"
                and summary.route == "bounded_automatic_rework"
                and adapter.verdict == "changes_required"
            ):
                blocking_findings = [
                    finding
                    for finding in adapter.findings
                    if finding.severity in {"medium", "high"}
                ]
                if not blocking_findings:
                    raise _Blocked("review_findings_invalid")
                if not semantics_changed:
                    decision_type = "ESCALATE_TO_HUMAN"
                    decision_reason = "repeated_review_semantic_fingerprint"
                elif not findings_changed:
                    decision_type = "ESCALATE_TO_HUMAN"
                    decision_reason = "repeated_canonical_blocking_findings"
                elif (
                    candidate_diff.rework_attempt_index + 1
                    >= candidate_diff.rework_attempt_limit
                ):
                    decision_type = "ESCALATE_TO_HUMAN"
                    decision_reason = "attempt_limit_exhausted"
                else:
                    decision_type = "NEXT_ATTEMPT_ELIGIBLE"
                    decision_reason = "changed_blocking_findings"
            else:
                raise _Blocked("history_invalid")

        replay_key = (
            ProjectDirectorBoundedReworkConvergenceDecision.compute_replay_key(
                source_candidate_diff_replay_key=(
                    candidate_diff.candidate_diff_replay_key
                ),
                source_review_outcome_replay_key=(
                    outcome.review_outcome_replay_key if outcome is not None else None
                ),
                source_p22_summary_message_id=(
                    p22_message.id if p22_message is not None else None
                ),
                current_rework_attempt_index=candidate_diff.rework_attempt_index,
            )
        )
        decision_id = uuid5(
            P25_BOUNDED_REWORK_CONVERGENCE_DECISION_NAMESPACE,
            replay_key,
        )
        next_index = (
            candidate_diff.rework_attempt_index + 1
            if decision_type == "NEXT_ATTEMPT_ELIGIBLE"
            else None
        )
        values = {
            "decision_id": decision_id,
            "decision_replay_key": replay_key,
            "created_at": utc_now(),
            "decision_type": decision_type,
            "decision_reason": decision_reason,
            "authority": candidate_diff.authority,
            "source_package_id": package.package_id,
            "source_package_fingerprint": package.package_fingerprint,
            "source_attempt_id": candidate_diff.source_attempt_id,
            "source_executor_outcome_id": executor_outcome.outcome_id,
            "source_candidate_diff_message_id": candidate_diff.candidate_diff_id,
            "source_candidate_diff_id": candidate_diff.candidate_diff_id,
            "source_candidate_diff_fingerprint": (
                candidate_diff.candidate_diff_fingerprint
            ),
            "source_candidate_diff_replay_key": (
                candidate_diff.candidate_diff_replay_key
            ),
            "candidate_diff_status": candidate_diff.diff_status,
            "source_review_outcome_message_id": (
                review_message.id if review_message is not None else None
            ),
            "source_review_outcome_id": (
                outcome.review_outcome_id if outcome is not None else None
            ),
            "source_review_outcome_fingerprint": (
                outcome.review_outcome_fingerprint if outcome is not None else None
            ),
            "source_review_outcome_replay_key": (
                outcome.review_outcome_replay_key if outcome is not None else None
            ),
            "source_review_result_fingerprint": (
                outcome.review_result_fingerprint if outcome is not None else None
            ),
            "current_review_semantic_fingerprint": (
                outcome.review_semantic_fingerprint if outcome is not None else None
            ),
            "source_p22_summary_message_id": (
                p22_message.id if p22_message is not None else None
            ),
            "source_human_escalation_package_message_id": human_package_id,
            "current_rework_attempt_index": candidate_diff.rework_attempt_index,
            "rework_attempt_limit": candidate_diff.rework_attempt_limit,
            "next_rework_attempt_index": next_index,
            "previous_diff_sha256": candidate_diff.previous_diff_sha256,
            "current_diff_sha256": candidate_diff.new_diff_sha256,
            "previous_review_semantic_fingerprint": (
                package.authority.source_review_semantic_fingerprint
            ),
            "previous_blocking_findings_fingerprint": (
                previous_findings_fingerprint
            ),
            "current_blocking_findings_fingerprint": (
                current_findings_fingerprint
            ),
            "diff_changed": (
                candidate_diff.new_diff_sha256
                != candidate_diff.previous_diff_sha256
            ),
            "review_semantics_changed": semantics_changed,
            "blocking_findings_changed": findings_changed,
            "converged": decision_type == "CONVERGED",
            "next_attempt_eligible": decision_type == "NEXT_ATTEMPT_ELIGIBLE",
            "human_escalation_required": (
                decision_type == "ESCALATE_TO_HUMAN"
            ),
            "automatic_processing_terminal": (
                decision_type != "NEXT_ATTEMPT_ELIGIBLE"
            ),
        }
        draft = ProjectDirectorBoundedReworkConvergenceDecision.model_construct(
            decision_fingerprint="0" * 64,
            **values,
        )
        return ProjectDirectorBoundedReworkConvergenceDecision(
            decision_fingerprint=draft.compute_fingerprint(),
            **values,
        )

    def _decision_for_candidate_diff(
        self,
        *,
        session_id: UUID,
        source_candidate_diff_message_id: UUID,
        decision_replay_key: str,
    ) -> tuple[
        ProjectDirectorBoundedReworkConvergenceDecision,
        ProjectDirectorMessage,
    ] | None:
        decisions = self._load_decision_history(session_id)
        replay_matches = [
            item
            for item in decisions
            if item[0].decision_replay_key == decision_replay_key
        ]
        candidate_matches = [
            item
            for item in decisions
            if item[0].source_candidate_diff_message_id
            == source_candidate_diff_message_id
        ]
        if len(candidate_matches) > 1:
            raise _Blocked("history_invalid")
        if len(replay_matches) > 1:
            fingerprints = {item[0].decision_fingerprint for item in replay_matches}
            candidate_ids = {
                item[0].source_candidate_diff_message_id for item in replay_matches
            }
            if len(fingerprints) > 1 or len(candidate_ids) > 1:
                raise _Blocked("convergence_decision_conflict")
            raise _Blocked("history_invalid")
        if replay_matches and candidate_matches and replay_matches != candidate_matches:
            raise _Blocked("convergence_decision_conflict")
        if replay_matches and not candidate_matches:
            raise _Blocked("convergence_decision_conflict")
        return candidate_matches[0] if candidate_matches else None

    def _load_decision_history(
        self,
        session_id: UUID,
    ) -> tuple[
        tuple[
            ProjectDirectorBoundedReworkConvergenceDecision,
            ProjectDirectorMessage,
        ],
        ...,
    ]:
        decisions: list[
            tuple[
                ProjectDirectorBoundedReworkConvergenceDecision,
                ProjectDirectorMessage,
            ]
        ] = []
        for message in self._iter_session_messages(session_id):
            action = self._decision_action(message)
            if action is None:
                continue
            payload = dict(action)
            payload.pop("type", None)
            try:
                decision = ProjectDirectorBoundedReworkConvergenceDecision.model_validate(
                    payload
                )
            except (TypeError, ValueError, ValidationError) as exc:
                raise _Blocked("history_invalid") from exc
            if not self._decision_message_valid(message, decision):
                raise _Blocked("convergence_decision_conflict")
            decisions.append((decision, message))
        candidates = [
            item[0].source_candidate_diff_message_id for item in decisions
        ]
        if len(candidates) != len(set(candidates)):
            raise _Blocked("history_invalid")
        replay_groups: dict[
            str,
            list[ProjectDirectorBoundedReworkConvergenceDecision],
        ] = {}
        for decision, _ in decisions:
            replay_groups.setdefault(decision.decision_replay_key, []).append(
                decision
            )
        for group in replay_groups.values():
            if len(group) < 2:
                continue
            if len({item.decision_fingerprint for item in group}) > 1:
                raise _Blocked("convergence_decision_conflict")
            raise _Blocked("history_invalid")
        return tuple(decisions)

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
    def _decision_action(message: ProjectDirectorMessage) -> dict[str, Any] | None:
        marked = (
            str(message.intent or "").startswith("bounded_rework_convergence")
            or str(message.source_detail or "").startswith("p25_i_b_")
            or any(
                isinstance(action, dict)
                and (
                    str(action.get("type", "")).startswith(
                        "p25_bounded_rework_convergence"
                    )
                    or str(action.get("schema_version", "")).startswith(
                        "p25-i-b-"
                    )
                )
                for action in message.suggested_actions
            )
        )
        if not marked:
            return None
        if (
            len(message.suggested_actions) != 1
            or not isinstance(message.suggested_actions[0], dict)
        ):
            raise _Blocked("convergence_decision_conflict")
        action = message.suggested_actions[0]
        if (
            message.intent != P25_BOUNDED_REWORK_CONVERGENCE_DECISION_INTENT
            or message.source_detail
            != P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SOURCE_DETAIL
            or action.get("type")
            != P25_BOUNDED_REWORK_CONVERGENCE_DECISION_ACTION_TYPE
            or action.get("schema_version")
            != P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SCHEMA_VERSION
        ):
            raise _Blocked("convergence_decision_conflict")
        return action

    def _build_decision_message(
        self,
        decision: ProjectDirectorBoundedReworkConvergenceDecision,
    ) -> ProjectDirectorMessage:
        return ProjectDirectorMessage(
            id=decision.decision_id,
            session_id=decision.authority.session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content=self._decision_content(decision),
            sequence_no=self._message_repository.get_next_sequence_no(
                session_id=decision.authority.session_id
            ),
            intent=P25_BOUNDED_REWORK_CONVERGENCE_DECISION_INTENT,
            related_project_id=decision.authority.project_id,
            related_task_id=decision.authority.source_task_id,
            source=ProjectDirectorMessageSource.SYSTEM,
            source_detail=P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SOURCE_DETAIL,
            suggested_actions=[
                {
                    "type": P25_BOUNDED_REWORK_CONVERGENCE_DECISION_ACTION_TYPE,
                    **decision.model_dump(mode="json"),
                }
            ],
            requires_confirmation=False,
            risk_level=ProjectDirectorMessageRiskLevel.HIGH,
            forbidden_actions_detected=list(_FALSE_BOUNDARIES),
            token_count=None,
            estimated_cost=None,
            created_at=decision.created_at,
        )

    @classmethod
    def _decision_message_valid(
        cls,
        message: ProjectDirectorMessage,
        decision: ProjectDirectorBoundedReworkConvergenceDecision,
    ) -> bool:
        return bool(
            message.id == decision.decision_id
            and message.created_at == decision.created_at
            and message.session_id == decision.authority.session_id
            and message.related_project_id == decision.authority.project_id
            and message.related_task_id == decision.authority.source_task_id
            and message.role == ProjectDirectorMessageRole.ASSISTANT
            and message.source == ProjectDirectorMessageSource.SYSTEM
            and message.intent == P25_BOUNDED_REWORK_CONVERGENCE_DECISION_INTENT
            and message.source_detail
            == P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SOURCE_DETAIL
            and message.content == cls._decision_content(decision)
            and message.suggested_actions
            == [
                {
                    "type": P25_BOUNDED_REWORK_CONVERGENCE_DECISION_ACTION_TYPE,
                    **decision.model_dump(mode="json"),
                }
            ]
            and message.requires_confirmation is False
            and message.risk_level == ProjectDirectorMessageRiskLevel.HIGH
            and tuple(message.forbidden_actions_detected) == _FALSE_BOUNDARIES
            and message.token_count is None
            and message.estimated_cost is None
        )

    @staticmethod
    def _decision_content(
        decision: ProjectDirectorBoundedReworkConvergenceDecision,
    ) -> str:
        return (
            "P25 bounded rework convergence decision persisted: "
            f"{decision.decision_id} type {decision.decision_type} reason "
            f"{decision.decision_reason}. No next attempt, human decision, Task, "
            "Run, Worker, file write, patch, or product-runtime Git operation was "
            "started."
        )

    def _rollback_local_read_transaction(self) -> None:
        if self._message_repository._session.in_transaction():
            self._message_repository._session.rollback()

    @staticmethod
    def _result_from_evaluation(
        evaluation: _DecisionEvaluation,
        *,
        status: ConvergencePersistenceStatus | None = None,
        decision: ProjectDirectorBoundedReworkConvergenceDecision | None = None,
        decision_message: ProjectDirectorMessage | None = None,
        blocked_reasons: tuple[str, ...] | None = None,
    ) -> ProjectDirectorBoundedReworkConvergenceResult:
        candidate = evaluation.candidate
        review = evaluation.review
        p22 = evaluation.p22
        result_status: ConvergencePersistenceStatus
        if status is not None:
            result_status = status
        elif evaluation.status == "ready":
            result_status = "blocked"
        else:
            result_status = evaluation.status
        return ProjectDirectorBoundedReworkConvergenceResult(
            status=result_status,
            decision=decision,
            decision_message=decision_message,
            candidate_diff=candidate.candidate_diff,
            candidate_diff_message=candidate.candidate_diff_message,
            review_outcome=(review.review_outcome if review is not None else None),
            review_outcome_message=(
                review.review_outcome_message if review is not None else None
            ),
            p22_summary=(p22.result if p22 is not None else None),
            p22_summary_message=(p22.message if p22 is not None else None),
            blocked_reasons=(
                evaluation.blocked_reasons
                if blocked_reasons is None
                else blocked_reasons
            ),
        )

    @staticmethod
    def _empty_result(
        status: ConvergencePersistenceStatus,
        reason: str,
    ) -> ProjectDirectorBoundedReworkConvergenceResult:
        return ProjectDirectorBoundedReworkConvergenceResult(
            status=status,
            decision=None,
            decision_message=None,
            candidate_diff=None,
            candidate_diff_message=None,
            review_outcome=None,
            review_outcome_message=None,
            p22_summary=None,
            p22_summary_message=None,
            blocked_reasons=(reason,),
        )

    @staticmethod
    def _next_attempt_revalidation_from_evaluation(
        evaluation: _DecisionEvaluation,
        *,
        decision: ProjectDirectorBoundedReworkConvergenceDecision,
        decision_message: ProjectDirectorMessage,
        blocked_reasons: tuple[str, ...],
    ) -> RevalidatedProjectDirectorBoundedReworkNextAttemptDecision:
        review = evaluation.review
        p22 = evaluation.p22
        return RevalidatedProjectDirectorBoundedReworkNextAttemptDecision(
            decision=decision,
            decision_message=decision_message,
            candidate_diff=evaluation.candidate.candidate_diff,
            candidate_diff_message=evaluation.candidate.candidate_diff_message,
            review_outcome=(review.review_outcome if review is not None else None),
            review_outcome_message=(
                review.review_outcome_message if review is not None else None
            ),
            p22_summary=(p22.result if p22 is not None else None),
            p22_summary_message=(p22.message if p22 is not None else None),
            blocked_reasons=blocked_reasons,
        )

    @staticmethod
    def _empty_next_attempt_revalidation(
        reason: str,
    ) -> RevalidatedProjectDirectorBoundedReworkNextAttemptDecision:
        return RevalidatedProjectDirectorBoundedReworkNextAttemptDecision(
            decision=None,
            decision_message=None,
            candidate_diff=None,
            candidate_diff_message=None,
            review_outcome=None,
            review_outcome_message=None,
            p22_summary=None,
            p22_summary_message=None,
            blocked_reasons=(reason,),
        )

    @staticmethod
    def _terminal_revalidation_from_evaluation(
        evaluation: _DecisionEvaluation,
        *,
        decision: ProjectDirectorBoundedReworkConvergenceDecision,
        decision_message: ProjectDirectorMessage,
        blocked_reasons: tuple[str, ...],
    ) -> RevalidatedProjectDirectorBoundedReworkTerminalDecision:
        review = evaluation.review
        p22 = evaluation.p22
        return RevalidatedProjectDirectorBoundedReworkTerminalDecision(
            decision=decision,
            decision_message=decision_message,
            package=evaluation.candidate.package,
            candidate_diff=evaluation.candidate.candidate_diff,
            candidate_diff_message=evaluation.candidate.candidate_diff_message,
            review_outcome=(review.review_outcome if review is not None else None),
            review_outcome_message=(
                review.review_outcome_message if review is not None else None
            ),
            p22_summary=(p22.result if p22 is not None else None),
            p22_summary_message=(p22.message if p22 is not None else None),
            blocked_reasons=blocked_reasons,
        )

    @staticmethod
    def _empty_terminal_revalidation(
        reason: str,
    ) -> RevalidatedProjectDirectorBoundedReworkTerminalDecision:
        return RevalidatedProjectDirectorBoundedReworkTerminalDecision(
            decision=None,
            decision_message=None,
            package=None,
            candidate_diff=None,
            candidate_diff_message=None,
            review_outcome=None,
            review_outcome_message=None,
            p22_summary=None,
            p22_summary_message=None,
            blocked_reasons=(reason,),
        )


__all__ = (
    "ConvergencePersistenceStatus",
    "P25_BOUNDED_REWORK_CONVERGENCE_DECISION_ACTION_TYPE",
    "P25_BOUNDED_REWORK_CONVERGENCE_DECISION_INTENT",
    "P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SOURCE_DETAIL",
    "ProjectDirectorBoundedReworkConvergenceResult",
    "ProjectDirectorBoundedReworkConvergenceService",
    "RevalidatedProjectDirectorBoundedReworkNextAttemptDecision",
    "RevalidatedProjectDirectorBoundedReworkTerminalDecision",
    "compute_canonical_blocking_findings_fingerprint",
)
