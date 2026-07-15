"""Persist or replay one P25-I-C2 terminal escalation package."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid5

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.domain._base import utc_now
from app.domain.project_director_bounded_rework_contract import (
    compute_p25_contract_sha256,
)
from app.domain.project_director_bounded_rework_terminal_escalation import (
    P25_BOUNDED_REWORK_TERMINAL_ESCALATION_NAMESPACE,
    P25_BOUNDED_REWORK_TERMINAL_ESCALATION_SCHEMA_VERSION,
    ProjectDirectorBoundedReworkTerminalEscalationFinding,
    ProjectDirectorBoundedReworkTerminalEscalationPackage,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_sandbox_candidate_diff_review_human_escalation_package import (
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.services.project_director_bounded_rework_convergence_service import (
    ProjectDirectorBoundedReworkConvergenceService,
    RevalidatedProjectDirectorBoundedReworkTerminalDecision,
)
from app.services.project_director_sandbox_candidate_diff_review_human_escalation_package_service import (
    HUMAN_ESCALATION_PACKAGE_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService,
)


P25_BOUNDED_REWORK_TERMINAL_ESCALATION_SOURCE_DETAIL = (
    "p25_i_c2_terminal_escalation_package_prepared"
)
P25_BOUNDED_REWORK_TERMINAL_ESCALATION_ACTION_TYPE = (
    "p25_bounded_rework_terminal_escalation_package_record"
)
P25_BOUNDED_REWORK_TERMINAL_ESCALATION_INTENT = (
    "bounded_rework_terminal_escalation_package"
)

_PAGE_SIZE = 200
_FALSE_BOUNDARIES = (
    "human_decision_recorded=false",
    "approval_request_created=false",
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

TerminalEscalationPersistenceStatus = Literal[
    "package_prepared",
    "package_replayed",
    "existing_human_package_reused",
    "recovery_required",
    "blocked",
]


@dataclass(frozen=True, slots=True)
class PreparedProjectDirectorBoundedReworkTerminalEscalation:
    status: TerminalEscalationPersistenceStatus
    package: ProjectDirectorBoundedReworkTerminalEscalationPackage | None
    message: ProjectDirectorMessage | None
    existing_human_package: (
        ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult
        | None
    )
    existing_human_package_message: ProjectDirectorMessage | None
    blocked_reasons: tuple[str, ...]


class _Blocked(RuntimeError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class ProjectDirectorBoundedReworkTerminalEscalationService:
    """Prepare one terminal package without recording a human decision."""

    def __init__(
        self,
        *,
        message_repository: ProjectDirectorMessageRepository,
        convergence_service: ProjectDirectorBoundedReworkConvergenceService,
    ) -> None:
        self._message_repository = message_repository
        self._convergence_service = convergence_service
        if convergence_service._message_repository is not message_repository:
            raise ValueError("P25-I-B and P25-I-C2 must share one message repository")

    def prepare_bounded_rework_terminal_escalation(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_convergence_decision_message_id: UUID,
    ) -> PreparedProjectDirectorBoundedReworkTerminalEscalation:
        """Persist, replay, or reuse one exact terminal escalation package."""

        if self._message_repository._session.in_transaction():
            return self._empty_result("recovery_required", "persistence_failed")

        initial = self._convergence_service.revalidate_terminal_escalation_decision(
            session_id=session_id,
            source_task_id=source_task_id,
            source_convergence_decision_message_id=(
                source_convergence_decision_message_id
            ),
        )
        if initial.blocked_reasons:
            return self._result_for_revalidation_failure(initial)
        if initial.decision is None:
            return self._empty_result(
                "blocked",
                "source_convergence_decision_invalid",
            )

        if initial.decision.decision_reason == "high_review_risk":
            try:
                return self._reuse_existing_human_package(
                    revalidated=initial,
                    session_id=session_id,
                    source_task_id=source_task_id,
                )
            except _Blocked as exc:
                return self._empty_result("blocked", exc.reason)
            except (RuntimeError, TypeError, ValueError, ValidationError):
                return self._empty_result(
                    "blocked",
                    "terminal_escalation_evidence_invalid",
                )
            finally:
                self._rollback_local_read_transaction()

        try:
            candidate = self._build_terminal_package(
                revalidated=initial,
                created_at=utc_now(),
            )
        except (RuntimeError, TypeError, ValueError, ValidationError):
            self._rollback_local_read_transaction()
            return self._empty_result(
                "blocked",
                "terminal_escalation_evidence_invalid",
            )
        self._rollback_local_read_transaction()

        try:
            with self._message_repository.sqlite_immediate_transaction():
                current = self._convergence_service.revalidate_terminal_escalation_decision_for_persistence(
                    session_id=session_id,
                    source_task_id=source_task_id,
                    source_convergence_decision_message_id=(
                        source_convergence_decision_message_id
                    ),
                )
                if current.blocked_reasons:
                    reason = current.blocked_reasons[0]
                    status: TerminalEscalationPersistenceStatus = (
                        "recovery_required"
                        if reason in {"persistence_failed", "claim_without_outcome"}
                        else "blocked"
                    )
                    return self._empty_result(status, reason)
                if current.decision is None:
                    raise _Blocked("source_convergence_decision_invalid")
                current_candidate = self._build_terminal_package(
                    revalidated=current,
                    created_at=candidate.created_at,
                )
                if (
                    current_candidate.package_replay_key
                    != candidate.package_replay_key
                    or current_candidate.package_fingerprint
                    != candidate.package_fingerprint
                ):
                    raise _Blocked("terminal_escalation_package_conflict")

                history = self._load_package_history(session_id)
                decision_matches = [
                    item
                    for item in history
                    if item[0].source_convergence_decision_message_id
                    == source_convergence_decision_message_id
                ]
                replay_matches = [
                    item
                    for item in history
                    if item[0].package_replay_key == candidate.package_replay_key
                ]
                if len(decision_matches) > 1:
                    raise _Blocked("history_invalid")
                if any(
                    item[0].source_convergence_decision_message_id
                    != source_convergence_decision_message_id
                    for item in replay_matches
                ):
                    raise _Blocked("terminal_escalation_package_conflict")
                if decision_matches:
                    existing, existing_message = decision_matches[0]
                    if (
                        existing.package_replay_key != candidate.package_replay_key
                        or existing.package_fingerprint
                        != candidate.package_fingerprint
                    ):
                        raise _Blocked("terminal_escalation_package_conflict")
                    return PreparedProjectDirectorBoundedReworkTerminalEscalation(
                        status="package_replayed",
                        package=existing,
                        message=existing_message,
                        existing_human_package=None,
                        existing_human_package_message=None,
                        blocked_reasons=(),
                    )

                message = self._build_package_message(candidate)
                persisted_message = self._message_repository.create(message)
                if persisted_message != message:
                    raise _Blocked("persistence_failed")
                return PreparedProjectDirectorBoundedReworkTerminalEscalation(
                    status="package_prepared",
                    package=candidate,
                    message=persisted_message,
                    existing_human_package=None,
                    existing_human_package_message=None,
                    blocked_reasons=(),
                )
        except _Blocked as exc:
            status = (
                "recovery_required"
                if exc.reason == "persistence_failed"
                else "blocked"
            )
            return self._empty_result(status, exc.reason)
        except SQLAlchemyError:
            return self._empty_result("recovery_required", "persistence_failed")
        except (RuntimeError, TypeError, ValueError, ValidationError):
            return self._empty_result("blocked", "history_invalid")
        finally:
            self._rollback_local_read_transaction()

    def _build_terminal_package(
        self,
        *,
        revalidated: RevalidatedProjectDirectorBoundedReworkTerminalDecision,
        created_at: datetime,
    ) -> ProjectDirectorBoundedReworkTerminalEscalationPackage:
        decision = revalidated.decision
        decision_message = revalidated.decision_message
        source_package = revalidated.package
        candidate_diff = revalidated.candidate_diff
        if (
            decision is None
            or decision_message is None
            or source_package is None
            or candidate_diff is None
            or source_package.authority is None
            or decision.decision_reason == "high_review_risk"
            or decision.source_package_id != source_package.package_id
            or decision.source_package_fingerprint
            != source_package.package_fingerprint
            or decision.source_candidate_diff_message_id
            != candidate_diff.candidate_diff_id
            or decision.source_candidate_diff_fingerprint
            != candidate_diff.candidate_diff_fingerprint
            or decision.authority != source_package.authority
            or decision.authority != candidate_diff.authority
        ):
            raise ValueError("terminal escalation lineage is incomplete")

        use_current_findings = candidate_diff.diff_status == "generated"
        if use_current_findings:
            review_outcome = revalidated.review_outcome
            review_message = revalidated.review_outcome_message
            p22_message = revalidated.p22_summary_message
            if (
                review_outcome is None
                or review_message is None
                or p22_message is None
                or review_outcome.adapter_result is None
                or decision.source_review_outcome_message_id != review_message.id
                or decision.source_review_outcome_id
                != review_outcome.review_outcome_id
                or decision.source_review_outcome_fingerprint
                != review_outcome.review_outcome_fingerprint
                or decision.source_review_result_fingerprint
                != review_outcome.review_result_fingerprint
                or decision.source_p22_summary_message_id != p22_message.id
            ):
                raise ValueError("terminal escalation review lineage is invalid")
            findings = self._project_findings(
                review_outcome.adapter_result.findings,
                finding_source="current_review",
            )
        else:
            findings = self._project_findings(
                source_package.blocking_findings,
                finding_source="prior_review",
            )

        replay_key = (
            ProjectDirectorBoundedReworkTerminalEscalationPackage
            .compute_replay_key(
                source_convergence_decision_replay_key=(
                    decision.decision_replay_key
                ),
                decision_reason=decision.decision_reason,
            )
        )
        package_id = uuid5(
            P25_BOUNDED_REWORK_TERMINAL_ESCALATION_NAMESPACE,
            replay_key,
        )
        values = {
            "terminal_escalation_package_id": package_id,
            "package_replay_key": replay_key,
            "created_at": created_at,
            "authority": decision.authority,
            "source_convergence_decision_message_id": decision_message.id,
            "source_convergence_decision_id": decision.decision_id,
            "source_convergence_decision_fingerprint": (
                decision.decision_fingerprint
            ),
            "source_convergence_decision_replay_key": decision.decision_replay_key,
            "decision_reason": decision.decision_reason,
            "source_package_id": decision.source_package_id,
            "source_package_fingerprint": decision.source_package_fingerprint,
            "source_attempt_id": decision.source_attempt_id,
            "source_executor_outcome_id": decision.source_executor_outcome_id,
            "source_candidate_diff_message_id": (
                decision.source_candidate_diff_message_id
            ),
            "source_candidate_diff_id": decision.source_candidate_diff_id,
            "source_candidate_diff_fingerprint": (
                decision.source_candidate_diff_fingerprint
            ),
            "candidate_diff_status": decision.candidate_diff_status,
            "candidate_non_convergence_reason": (
                candidate_diff.non_convergence_reason
            ),
            "source_review_outcome_message_id": (
                decision.source_review_outcome_message_id
            ),
            "source_review_outcome_id": decision.source_review_outcome_id,
            "source_review_outcome_fingerprint": (
                decision.source_review_outcome_fingerprint
            ),
            "source_review_result_fingerprint": (
                decision.source_review_result_fingerprint
            ),
            "source_p22_summary_message_id": (
                decision.source_p22_summary_message_id
            ),
            "current_rework_attempt_index": (
                decision.current_rework_attempt_index
            ),
            "rework_attempt_limit": decision.rework_attempt_limit,
            "previous_diff_sha256": decision.previous_diff_sha256,
            "current_diff_sha256": decision.current_diff_sha256,
            "previous_review_semantic_fingerprint": (
                decision.previous_review_semantic_fingerprint
            ),
            "current_review_semantic_fingerprint": (
                decision.current_review_semantic_fingerprint
            ),
            "previous_blocking_findings_fingerprint": (
                decision.previous_blocking_findings_fingerprint
            ),
            "current_blocking_findings_fingerprint": (
                decision.current_blocking_findings_fingerprint
            ),
            "unresolved_blocking_findings": findings,
            "risk_summary": (
                ProjectDirectorBoundedReworkTerminalEscalationPackage
                .build_risk_summary(
                    reason=decision.decision_reason,
                    attempt_index=decision.current_rework_attempt_index,
                    attempt_limit=decision.rework_attempt_limit,
                )
            ),
        }
        draft = ProjectDirectorBoundedReworkTerminalEscalationPackage.model_construct(
            package_fingerprint="0" * 64,
            **values,
        )
        return ProjectDirectorBoundedReworkTerminalEscalationPackage(
            package_fingerprint=draft.compute_fingerprint(),
            **values,
        )

    @staticmethod
    def _project_findings(
        source_findings: Any,
        *,
        finding_source: Literal["prior_review", "current_review"],
    ) -> tuple[ProjectDirectorBoundedReworkTerminalEscalationFinding, ...]:
        findings = [
            ProjectDirectorBoundedReworkTerminalEscalationFinding(
                finding_source=finding_source,
                severity=finding.severity,
                title=finding.title,
                evidence_paths=tuple(sorted(finding.evidence_paths)),
                recommended_action=finding.recommended_action,
            )
            for finding in source_findings
            if finding.severity in {"medium", "high"}
        ]
        if not findings:
            raise ValueError("terminal escalation requires blocking findings")
        unique_findings = {
            compute_p25_contract_sha256(finding.model_dump(mode="python")): finding
            for finding in findings
        }
        return tuple(
            unique_findings[fingerprint]
            for fingerprint in sorted(unique_findings)
        )

    def _reuse_existing_human_package(
        self,
        *,
        revalidated: RevalidatedProjectDirectorBoundedReworkTerminalDecision,
        session_id: UUID,
        source_task_id: UUID,
    ) -> PreparedProjectDirectorBoundedReworkTerminalEscalation:
        decision = revalidated.decision
        decision_message = revalidated.decision_message
        summary = revalidated.p22_summary
        summary_message = revalidated.p22_summary_message
        if (
            decision is None
            or decision_message is None
            or summary is None
            or summary_message is None
            or decision.decision_reason != "high_review_risk"
            or summary.orchestration_status != "waiting_for_human"
            or summary.route != "human_escalation"
            or decision.source_human_escalation_package_message_id is None
            or decision.source_human_escalation_package_message_id
            != summary.source_human_escalation_package_message_id
            or decision.source_p22_summary_message_id != summary_message.id
        ):
            raise _Blocked("terminal_escalation_evidence_invalid")
        if any(
            package.source_convergence_decision_message_id
            == decision_message.id
            for package, _message in self._load_package_history(session_id)
        ):
            raise _Blocked("terminal_escalation_package_conflict")
        package_message_id = decision.source_human_escalation_package_message_id
        package_message = self._message_repository.get_by_id(package_message_id)
        if package_message is None:
            raise _Blocked("terminal_escalation_evidence_invalid")
        if (
            package_message.session_id != session_id
            or package_message.related_project_id != decision.authority.project_id
            or package_message.related_task_id != source_task_id
            or package_message.role != ProjectDirectorMessageRole.ASSISTANT
            or package_message.source != ProjectDirectorMessageSource.SYSTEM
            or package_message.intent
            != "sandbox_candidate_diff_review_human_escalation_package"
            or package_message.source_detail
            != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_SOURCE_DETAIL
            or package_message.requires_confirmation is not True
            or package_message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
            or len(package_message.suggested_actions) != 1
            or not isinstance(package_message.suggested_actions[0], dict)
        ):
            raise _Blocked("terminal_escalation_evidence_invalid")
        action = package_message.suggested_actions[0]
        if (
            action.get("type")
            != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_ACTION_TYPE
            or action.get("schema_version")
            != HUMAN_ESCALATION_PACKAGE_SCHEMA_VERSION
        ):
            raise _Blocked("terminal_escalation_evidence_invalid")
        try:
            package = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult.model_validate(
                {
                    field_name: action.get(field_name)
                    for field_name in ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult.model_fields
                }
            )
        except ValidationError as exc:
            raise _Blocked("terminal_escalation_evidence_invalid") from exc
        fingerprint = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService.revalidate_persisted_human_escalation_package_fingerprint(
            session_id=session_id,
            source_task_id=source_task_id,
            source_package_message_id=package_message_id,
            source_package_action=action,
        )
        if (
            fingerprint.blocked_reasons
            or fingerprint.aggregate_evidence_fingerprint
            != package.aggregate_evidence_fingerprint
            or fingerprint.escalation_package_id != package.escalation_package_id
            or fingerprint.source_review_message_id
            != summary.source_review_message_id
        ):
            raise _Blocked("terminal_escalation_evidence_invalid")
        return PreparedProjectDirectorBoundedReworkTerminalEscalation(
            status="existing_human_package_reused",
            package=None,
            message=None,
            existing_human_package=package,
            existing_human_package_message=package_message,
            blocked_reasons=(),
        )

    def _load_package_history(
        self,
        session_id: UUID,
    ) -> tuple[
        tuple[
            ProjectDirectorBoundedReworkTerminalEscalationPackage,
            ProjectDirectorMessage,
        ],
        ...,
    ]:
        history: list[
            tuple[
                ProjectDirectorBoundedReworkTerminalEscalationPackage,
                ProjectDirectorMessage,
            ]
        ] = []
        for message in self._iter_session_messages(session_id):
            action = self._terminal_package_action(message)
            if action is None:
                continue
            payload = dict(action)
            payload.pop("type", None)
            try:
                package = ProjectDirectorBoundedReworkTerminalEscalationPackage.model_validate(
                    payload
                )
            except (TypeError, ValueError, ValidationError) as exc:
                raise _Blocked("history_invalid") from exc
            if not self._package_message_valid(message, package):
                raise _Blocked("history_invalid")
            history.append((package, message))
        return tuple(history)

    @staticmethod
    def _terminal_package_action(
        message: ProjectDirectorMessage,
    ) -> dict[str, Any] | None:
        marked = (
            str(message.intent or "").startswith(
                "bounded_rework_terminal_escalation"
            )
            or str(message.source_detail or "").startswith("p25_i_c2_")
            or any(
                isinstance(action, dict)
                and (
                    str(action.get("type", "")).startswith(
                        "p25_bounded_rework_terminal_escalation"
                    )
                    or str(action.get("schema_version", "")).startswith(
                        "p25-i-c2-terminal-escalation"
                    )
                )
                for action in message.suggested_actions
            )
        )
        if not marked:
            return None
        if (
            message.intent != P25_BOUNDED_REWORK_TERMINAL_ESCALATION_INTENT
            or message.source_detail
            != P25_BOUNDED_REWORK_TERMINAL_ESCALATION_SOURCE_DETAIL
            or len(message.suggested_actions) != 1
            or not isinstance(message.suggested_actions[0], dict)
            or message.suggested_actions[0].get("type")
            != P25_BOUNDED_REWORK_TERMINAL_ESCALATION_ACTION_TYPE
            or message.suggested_actions[0].get("schema_version")
            != P25_BOUNDED_REWORK_TERMINAL_ESCALATION_SCHEMA_VERSION
        ):
            raise _Blocked("history_invalid")
        return message.suggested_actions[0]

    def _build_package_message(
        self,
        package: ProjectDirectorBoundedReworkTerminalEscalationPackage,
    ) -> ProjectDirectorMessage:
        return ProjectDirectorMessage(
            id=package.terminal_escalation_package_id,
            session_id=package.authority.session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content=self._package_content(package),
            sequence_no=self._message_repository.get_next_sequence_no(
                session_id=package.authority.session_id
            ),
            intent=P25_BOUNDED_REWORK_TERMINAL_ESCALATION_INTENT,
            related_project_id=package.authority.project_id,
            related_task_id=package.authority.source_task_id,
            source=ProjectDirectorMessageSource.SYSTEM,
            source_detail=P25_BOUNDED_REWORK_TERMINAL_ESCALATION_SOURCE_DETAIL,
            suggested_actions=[
                {
                    "type": P25_BOUNDED_REWORK_TERMINAL_ESCALATION_ACTION_TYPE,
                    **package.model_dump(mode="json"),
                }
            ],
            requires_confirmation=False,
            risk_level=ProjectDirectorMessageRiskLevel.HIGH,
            forbidden_actions_detected=list(_FALSE_BOUNDARIES),
            token_count=None,
            estimated_cost=None,
            created_at=package.created_at,
        )

    @classmethod
    def _package_message_valid(
        cls,
        message: ProjectDirectorMessage,
        package: ProjectDirectorBoundedReworkTerminalEscalationPackage,
    ) -> bool:
        return bool(
            message.id == package.terminal_escalation_package_id
            and message.session_id == package.authority.session_id
            and message.related_project_id == package.authority.project_id
            and message.related_task_id == package.authority.source_task_id
            and message.role == ProjectDirectorMessageRole.ASSISTANT
            and message.source == ProjectDirectorMessageSource.SYSTEM
            and message.intent == P25_BOUNDED_REWORK_TERMINAL_ESCALATION_INTENT
            and message.source_detail
            == P25_BOUNDED_REWORK_TERMINAL_ESCALATION_SOURCE_DETAIL
            and message.content == cls._package_content(package)
            and message.suggested_actions
            == [
                {
                    "type": P25_BOUNDED_REWORK_TERMINAL_ESCALATION_ACTION_TYPE,
                    **package.model_dump(mode="json"),
                }
            ]
            and message.requires_confirmation is False
            and message.risk_level == ProjectDirectorMessageRiskLevel.HIGH
            and tuple(message.forbidden_actions_detected) == _FALSE_BOUNDARIES
            and message.token_count is None
            and message.estimated_cost is None
            and message.created_at == package.created_at
        )

    @staticmethod
    def _package_content(
        package: ProjectDirectorBoundedReworkTerminalEscalationPackage,
    ) -> str:
        return (
            "P25 bounded rework terminal escalation package persisted: "
            f"{package.terminal_escalation_package_id} reason "
            f"{package.decision_reason}. Automatic rework is terminal. No human "
            "decision, next attempt, Task, Run, Worker, file write, patch, or "
            "product-runtime Git operation was started."
        )

    def _iter_session_messages(
        self,
        session_id: UUID,
    ) -> list[ProjectDirectorMessage]:
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

    def _rollback_local_read_transaction(self) -> None:
        if self._message_repository._session.in_transaction():
            self._message_repository._session.rollback()

    @staticmethod
    def _result_for_revalidation_failure(
        revalidated: RevalidatedProjectDirectorBoundedReworkTerminalDecision,
    ) -> PreparedProjectDirectorBoundedReworkTerminalEscalation:
        reason = revalidated.blocked_reasons[0]
        status: TerminalEscalationPersistenceStatus = (
            "recovery_required"
            if reason in {"persistence_failed", "claim_without_outcome"}
            else "blocked"
        )
        return PreparedProjectDirectorBoundedReworkTerminalEscalation(
            status=status,
            package=None,
            message=None,
            existing_human_package=None,
            existing_human_package_message=None,
            blocked_reasons=revalidated.blocked_reasons,
        )

    @staticmethod
    def _empty_result(
        status: TerminalEscalationPersistenceStatus,
        reason: str,
    ) -> PreparedProjectDirectorBoundedReworkTerminalEscalation:
        return PreparedProjectDirectorBoundedReworkTerminalEscalation(
            status=status,
            package=None,
            message=None,
            existing_human_package=None,
            existing_human_package_message=None,
            blocked_reasons=(reason,),
        )


__all__ = (
    "P25_BOUNDED_REWORK_TERMINAL_ESCALATION_ACTION_TYPE",
    "P25_BOUNDED_REWORK_TERMINAL_ESCALATION_INTENT",
    "P25_BOUNDED_REWORK_TERMINAL_ESCALATION_SOURCE_DETAIL",
    "PreparedProjectDirectorBoundedReworkTerminalEscalation",
    "ProjectDirectorBoundedReworkTerminalEscalationService",
    "TerminalEscalationPersistenceStatus",
)
