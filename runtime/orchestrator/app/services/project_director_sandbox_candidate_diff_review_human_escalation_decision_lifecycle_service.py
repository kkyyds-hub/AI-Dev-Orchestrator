"""Human escalation decision lifecycle guard for Project Director P21-D-D3."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_sandbox_candidate_diff_review_human_escalation_decision_lifecycle import (
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionPreflightResult,
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionRevocationResult,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_sandbox_candidate_diff_review_human_escalation_decision_service import (
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionService,
    RevalidatedPersistedHumanEscalationDecisionFingerprint,
)


P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_SOURCE_DETAIL = (
    "p21_d_sandbox_candidate_diff_review_human_escalation_decision_revoked"
)
P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_ACTION_TYPE = (
    "p21_d_sandbox_candidate_diff_review_human_escalation_decision_revocation_record"
)
HUMAN_ESCALATION_DECISION_REVOCATION_SCHEMA_VERSION = "p21-d-d3-revoke.v1"

P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL = (
    "p21_d_sandbox_candidate_diff_review_human_escalation_decision_consumption_preflight_ready"
)
P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_ACTION_TYPE = (
    "p21_d_sandbox_candidate_diff_review_human_escalation_decision_consumption_preflight_record"
)
HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION = (
    "p21-d-d3-preflight.v1"
)

_FUTURE_DECISION_CONSUMPTION_SOURCE_DETAIL = (
    "p21_d_sandbox_candidate_diff_review_human_escalation_decision_consumed"
)
_FUTURE_DECISION_CONSUMPTION_ACTION_TYPE = (
    "p21_d_sandbox_candidate_diff_review_human_escalation_decision_consumption_record"
)


@dataclass(frozen=True, slots=True)
class RecordedSandboxCandidateDiffReviewHumanEscalationDecisionRevocation:
    result: ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionRevocationResult
    message: ProjectDirectorMessage | None


@dataclass(frozen=True, slots=True)
class PreparedSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionPreflight:
    result: ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionPreflightResult
    message: ProjectDirectorMessage | None


@dataclass(frozen=True, slots=True)
class _ValidatedDecisionEvidence:
    action: dict[str, Any]
    stored_fingerprint: str
    revalidation: RevalidatedPersistedHumanEscalationDecisionFingerprint


@dataclass(frozen=True, slots=True)
class _LifecycleHistory:
    decision_revoked: bool = False
    decision_consumed: bool = False
    prior_consumption_preflight_detected: bool = False
    revoke_client_request_id_reused: bool = False


class ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionLifecycleService:
    """Evaluate, revoke, or prepare consumption without consuming a D2 decision."""

    def __init__(
        self,
        *,
        session_repository: ProjectDirectorSessionRepository | None = None,
        message_repository: ProjectDirectorMessageRepository | None = None,
        task_repository: TaskRepository | None = None,
    ) -> None:
        self._session_repository = session_repository
        self._message_repository = message_repository
        self._task_repository = task_repository

    def revoke_human_escalation_decision(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        actor: str,
        client_request_id: str,
    ) -> RecordedSandboxCandidateDiffReviewHumanEscalationDecisionRevocation:
        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("human escalation decision lifecycle repositories required")
        with self._message_repository.sqlite_immediate_transaction():
            return self._revoke_human_escalation_decision(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
                actor=actor,
                client_request_id=client_request_id,
            )

    def prepare_human_escalation_decision_consumption_preflight(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        evaluated_at: datetime | None = None,
    ) -> PreparedSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionPreflight:
        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("human escalation decision lifecycle repositories required")
        with self._message_repository.sqlite_immediate_transaction():
            return self._prepare_consumption_preflight(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
                evaluated_at=evaluated_at,
            )

    def _revoke_human_escalation_decision(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        actor: str,
        client_request_id: str,
    ) -> RecordedSandboxCandidateDiffReviewHumanEscalationDecisionRevocation:
        blocked_reasons: list[str] = []
        evidence: _ValidatedDecisionEvidence | None = None
        history = _LifecycleHistory()
        replay_check_completed = False
        source_decision_validated = False
        fingerprint_revalidated = False
        normalized_actor = actor.strip() if isinstance(actor, str) else ""
        normalized_client_request_id = (
            client_request_id.strip() if isinstance(client_request_id, str) else ""
        )
        if not normalized_actor or len(normalized_actor) > 200:
            blocked_reasons.append("human_escalation_decision_revoke_actor_invalid")
            normalized_actor = ""
        if (
            not normalized_client_request_id
            or len(normalized_client_request_id) > 200
        ):
            blocked_reasons.append("human_decision_revoke_client_request_id_invalid")
            normalized_client_request_id = ""

        session_obj, source_task, source_message = self._load_source_objects(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            blocked_reasons=blocked_reasons,
        )
        if blocked_reasons or session_obj is None or source_task is None:
            return self._blocked_revocation(
                source_message_id=source_message_id,
                evidence=evidence,
                actor=normalized_actor,
                client_request_id=normalized_client_request_id,
                source_decision_validated=source_decision_validated,
                fingerprint_revalidated=fingerprint_revalidated,
                replay_check_completed=replay_check_completed,
                history=history,
                decision_expired=False,
                blocked_reasons=blocked_reasons,
            )

        evidence = self._validated_decision_evidence(
            source_message=source_message,
            session_id=session_id,
            source_task_id=source_task_id,
            source_project_id=session_obj.project_id,
            source_message_id=source_message_id,
            blocked_reasons=blocked_reasons,
        )
        if blocked_reasons or evidence is None:
            return self._blocked_revocation(
                source_message_id=source_message_id,
                evidence=evidence,
                actor=normalized_actor,
                client_request_id=normalized_client_request_id,
                source_decision_validated=False,
                fingerprint_revalidated=False,
                replay_check_completed=False,
                history=history,
                decision_expired=False,
                blocked_reasons=blocked_reasons,
            )
        source_decision_validated = True
        fingerprint_revalidated = True

        history = self._scan_lifecycle_history(
            session_id=session_id,
            source_decision_message_id=source_message_id,
            decision_id=evidence.revalidation.decision_id,
            revoke_client_request_id=normalized_client_request_id,
            blocked_reasons=blocked_reasons,
        )
        replay_check_completed = True
        revoked_at = datetime.now(timezone.utc)
        decision_expired = revoked_at >= evidence.revalidation.decision_expires_at
        if decision_expired:
            blocked_reasons.append("human_escalation_decision_expired")
        if history.decision_revoked:
            blocked_reasons.append("human_escalation_decision_already_revoked")
        if history.decision_consumed:
            blocked_reasons.append("human_escalation_decision_already_consumed")
        if history.revoke_client_request_id_reused:
            blocked_reasons.append("human_decision_revoke_client_request_id_reused")
        blocked_reasons[:] = self._dedupe(blocked_reasons)
        if blocked_reasons:
            return self._blocked_revocation(
                source_message_id=source_message_id,
                evidence=evidence,
                actor=normalized_actor,
                client_request_id=normalized_client_request_id,
                source_decision_validated=True,
                fingerprint_revalidated=True,
                replay_check_completed=True,
                history=history,
                decision_expired=decision_expired,
                blocked_reasons=blocked_reasons,
            )

        result = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionRevocationResult(
            revocation_status="revoked",
            revocation_id=uuid4(),
            source_decision_message_id=source_message_id,
            decision_id=evidence.revalidation.decision_id,
            source_package_message_id=evidence.revalidation.source_package_message_id,
            escalation_package_id=evidence.revalidation.escalation_package_id,
            decision_confirmation_fingerprint=evidence.stored_fingerprint,
            revalidated_decision_confirmation_fingerprint=(
                evidence.revalidation.decision_confirmation_fingerprint
            ),
            revoke_actor_type="human",
            revoke_actor=normalized_actor,
            revoke_client_request_id=normalized_client_request_id,
            revoked_at=revoked_at,
            source_decision_validated=True,
            decision_fingerprint_revalidated=True,
            replay_check_completed=True,
            prior_revocation_detected=False,
            decision_revoked=True,
            decision_expired=False,
        )
        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.USER,
                content=(
                    "One structured human escalation decision revocation was "
                    "recorded against the exact D2 decision. The decision was not "
                    "consumed, continuation or rework was not started, and no Task, "
                    "Run, Worker, worktree, file write, patch, or Git write occurred. "
                    "AI Project Director total loop remains Partial."
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="sandbox_candidate_diff_review_human_escalation_decision_revocation",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=(
                    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_SOURCE_DETAIL
                ),
                suggested_actions=[
                    self._revocation_action(
                        session_id=session_id,
                        source_task_id=source_task_id,
                        result=result,
                    )
                ],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                forbidden_actions_detected=self._forbidden_actions(),
                created_at=revoked_at,
            )
        )
        return RecordedSandboxCandidateDiffReviewHumanEscalationDecisionRevocation(
            result=result,
            message=message,
        )

    def _prepare_consumption_preflight(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        evaluated_at: datetime | None,
    ) -> PreparedSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionPreflight:
        blocked_reasons: list[str] = []
        evidence: _ValidatedDecisionEvidence | None = None
        history = _LifecycleHistory()
        normalized_evaluated_at = evaluated_at or datetime.now(timezone.utc)
        if not self._timezone_aware_datetime(normalized_evaluated_at):
            blocked_reasons.append("human_escalation_decision_evaluated_at_invalid")
            normalized_evaluated_at = None

        session_obj, source_task, source_message = self._load_source_objects(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            blocked_reasons=blocked_reasons,
        )
        if blocked_reasons or session_obj is None or source_task is None:
            return self._blocked_preflight(
                source_message_id=source_message_id,
                evidence=evidence,
                evaluated_at=normalized_evaluated_at,
                source_decision_validated=False,
                fingerprint_revalidated=False,
                replay_check_completed=False,
                history=history,
                decision_expired=False,
                blocked_reasons=blocked_reasons,
            )

        evidence = self._validated_decision_evidence(
            source_message=source_message,
            session_id=session_id,
            source_task_id=source_task_id,
            source_project_id=session_obj.project_id,
            source_message_id=source_message_id,
            blocked_reasons=blocked_reasons,
        )
        if blocked_reasons or evidence is None:
            return self._blocked_preflight(
                source_message_id=source_message_id,
                evidence=evidence,
                evaluated_at=normalized_evaluated_at,
                source_decision_validated=False,
                fingerprint_revalidated=False,
                replay_check_completed=False,
                history=history,
                decision_expired=False,
                blocked_reasons=blocked_reasons,
            )

        history = self._scan_lifecycle_history(
            session_id=session_id,
            source_decision_message_id=source_message_id,
            decision_id=evidence.revalidation.decision_id,
            revoke_client_request_id=None,
            blocked_reasons=blocked_reasons,
        )
        decision_expired = (
            normalized_evaluated_at >= evidence.revalidation.decision_expires_at
        )
        if decision_expired:
            blocked_reasons.append("human_escalation_decision_expired")
        if history.decision_revoked:
            blocked_reasons.append("human_escalation_decision_already_revoked")
        if history.decision_consumed:
            blocked_reasons.append("human_escalation_decision_already_consumed")
        if history.prior_consumption_preflight_detected:
            blocked_reasons.append(
                "human_escalation_decision_consumption_preflight_already_prepared"
            )
        blocked_reasons[:] = self._dedupe(blocked_reasons)
        if blocked_reasons:
            return self._blocked_preflight(
                source_message_id=source_message_id,
                evidence=evidence,
                evaluated_at=normalized_evaluated_at,
                source_decision_validated=True,
                fingerprint_revalidated=True,
                replay_check_completed=True,
                history=history,
                decision_expired=decision_expired,
                blocked_reasons=blocked_reasons,
            )

        eligibility = {
            "APPROVE_CONTINUE": (True, False, False),
            "REQUEST_REWORK": (False, True, False),
            "REJECT": (False, False, True),
        }[evidence.revalidation.decision_action]
        result = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionPreflightResult(
            preflight_status="ready",
            preflight_id=uuid4(),
            source_decision_message_id=source_message_id,
            decision_id=evidence.revalidation.decision_id,
            source_package_message_id=evidence.revalidation.source_package_message_id,
            escalation_package_id=evidence.revalidation.escalation_package_id,
            decision_action=evidence.revalidation.decision_action,
            decision_confirmation_fingerprint=evidence.stored_fingerprint,
            revalidated_decision_confirmation_fingerprint=(
                evidence.revalidation.decision_confirmation_fingerprint
            ),
            decision_created_at=evidence.revalidation.decision_created_at,
            decision_expires_at=evidence.revalidation.decision_expires_at,
            evaluated_at=normalized_evaluated_at,
            source_decision_validated=True,
            decision_fingerprint_revalidated=True,
            replay_check_completed=True,
            decision_active=True,
            decision_expired=False,
            decision_revoked=False,
            prior_consumption_preflight_detected=False,
            continuation_eligible=eligibility[0],
            rework_eligible=eligibility[1],
            rejection_terminal=eligibility[2],
        )
        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "One atomic human escalation decision consumption preflight was "
                    "prepared from the exact active D2 decision. Eligibility is only "
                    "evidence for a future D4 gate; no decision was consumed, no "
                    "continuation or rework started, and no Task, Run, Worker, "
                    "worktree, file write, patch, or Git write occurred. AI Project "
                    "Director total loop remains Partial."
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent=(
                    "sandbox_candidate_diff_review_human_escalation_decision_consumption_preflight"
                ),
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=(
                    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL
                ),
                suggested_actions=[
                    self._preflight_action(
                        session_id=session_id,
                        source_task_id=source_task_id,
                        result=result,
                    )
                ],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                forbidden_actions_detected=self._forbidden_actions(),
                created_at=normalized_evaluated_at,
            )
        )
        return PreparedSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionPreflight(
            result=result,
            message=message,
        )

    def _load_source_objects(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        blocked_reasons: list[str],
    ) -> tuple[Any | None, Any | None, ProjectDirectorMessage | None]:
        session_obj = self._session_repository.get_by_id(session_id)
        source_task = self._task_repository.get_by_id(source_task_id)
        source_message = self._message_repository.get_by_id(source_message_id)
        if session_obj is None:
            blocked_reasons.append("session_missing")
        if source_task is None:
            blocked_reasons.append("source_task_missing")
        if (
            session_obj is not None
            and source_task is not None
            and source_task.project_id != session_obj.project_id
        ):
            blocked_reasons.append("source_task_project_mismatch")
        return session_obj, source_task, source_message

    @classmethod
    def _validated_decision_evidence(
        cls,
        *,
        source_message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        source_project_id: UUID | None,
        source_message_id: UUID,
        blocked_reasons: list[str],
    ) -> _ValidatedDecisionEvidence | None:
        action = cls._source_decision_action(
            source_message=source_message,
            session_id=session_id,
            source_task_id=source_task_id,
            source_project_id=source_project_id,
            blocked_reasons=blocked_reasons,
        )
        if action is None:
            return None
        revalidation = (
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionService
            .revalidate_persisted_human_escalation_decision_fingerprint(
                session_id=session_id,
                source_task_id=source_task_id,
                source_decision_message_id=source_message_id,
                source_decision_action=action,
            )
        )
        blocked_reasons.extend(revalidation.blocked_reasons)
        stored_fingerprint = action.get("decision_confirmation_fingerprint")
        if not isinstance(stored_fingerprint, str):
            blocked_reasons.append("decision_confirmation_fingerprint_invalid")
            return None
        if blocked_reasons:
            return None
        if stored_fingerprint != revalidation.decision_confirmation_fingerprint:
            blocked_reasons.append("decision_confirmation_fingerprint_mismatch")
            return None
        return _ValidatedDecisionEvidence(
            action=action,
            stored_fingerprint=stored_fingerprint,
            revalidation=revalidation,
        )

    @staticmethod
    def _source_decision_action(
        *,
        source_message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        source_project_id: UUID | None,
        blocked_reasons: list[str],
    ) -> dict[str, Any] | None:
        if source_message is None:
            blocked_reasons.append("source_human_escalation_decision_message_missing")
            return None
        checks = (
            (source_message.session_id == session_id, "source_decision_session_mismatch"),
            (
                source_message.related_project_id == source_project_id,
                "source_decision_project_mismatch",
            ),
            (
                source_message.related_task_id == source_task_id,
                "source_decision_task_mismatch",
            ),
            (source_message.role == ProjectDirectorMessageRole.USER, "source_decision_role_invalid"),
            (
                source_message.source == ProjectDirectorMessageSource.SYSTEM,
                "source_decision_source_invalid",
            ),
            (
                source_message.intent
                == "sandbox_candidate_diff_review_human_escalation_decision",
                "source_decision_intent_invalid",
            ),
            (
                source_message.source_detail
                == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_SOURCE_DETAIL,
                "source_message_is_not_p21_d_d2_decision",
            ),
            (
                source_message.requires_confirmation is False,
                "source_decision_confirmation_contract_invalid",
            ),
            (
                source_message.risk_level == ProjectDirectorMessageRiskLevel.HIGH,
                "source_decision_risk_level_invalid",
            ),
        )
        for valid, reason in checks:
            if not valid:
                blocked_reasons.append(reason)
        if len(source_message.suggested_actions) != 1:
            blocked_reasons.append("source_human_escalation_decision_record_missing")
            return None
        action = source_message.suggested_actions[0]
        if (
            not isinstance(action, dict)
            or action.get("type")
            != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_ACTION_TYPE
        ):
            blocked_reasons.append("source_human_escalation_decision_record_missing")
            return None
        return action

    def _scan_lifecycle_history(
        self,
        *,
        session_id: UUID,
        source_decision_message_id: UUID,
        decision_id: UUID | None,
        revoke_client_request_id: str | None,
        blocked_reasons: list[str],
    ) -> _LifecycleHistory:
        decision_revoked = False
        decision_consumed = False
        prior_preflight = False
        client_reused = False
        before_message_id: UUID | None = None
        while True:
            messages, has_more = self._message_repository.list_by_session_id(
                session_id=session_id,
                limit=100,
                before_message_id=before_message_id,
            )
            for message in messages:
                if message.source_detail == (
                    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_SOURCE_DETAIL
                ):
                    result = self._trusted_revocation(message)
                    if result is None:
                        blocked_reasons.append(
                            "prior_human_escalation_decision_revocation_record_invalid"
                        )
                        continue
                    if (
                        result.source_decision_message_id
                        == source_decision_message_id
                        or result.decision_id == decision_id
                    ):
                        decision_revoked = True
                    if (
                        revoke_client_request_id is not None
                        and result.revoke_client_request_id
                        == revoke_client_request_id
                    ):
                        client_reused = True
                elif message.source_detail == (
                    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL
                ):
                    result = self._trusted_preflight(message)
                    if result is None:
                        blocked_reasons.append(
                            "prior_human_escalation_decision_consumption_preflight_record_invalid"
                        )
                        continue
                    if (
                        result.source_decision_message_id
                        == source_decision_message_id
                        or result.decision_id == decision_id
                    ):
                        prior_preflight = True
                elif message.source_detail == _FUTURE_DECISION_CONSUMPTION_SOURCE_DETAIL:
                    action = self._trusted_future_consumption(message)
                    if action is None:
                        blocked_reasons.append(
                            "prior_human_escalation_decision_consumption_record_invalid"
                        )
                        continue
                    if (
                        action["source_decision_message_id"]
                        == str(source_decision_message_id)
                        or action["decision_id"] == str(decision_id)
                    ):
                        decision_consumed = True
            if not has_more or not messages:
                break
            before_message_id = messages[0].id
        blocked_reasons[:] = self._dedupe(blocked_reasons)
        return _LifecycleHistory(
            decision_revoked=decision_revoked,
            decision_consumed=decision_consumed,
            prior_consumption_preflight_detected=prior_preflight,
            revoke_client_request_id_reused=client_reused,
        )

    @staticmethod
    def _trusted_revocation(
        message: ProjectDirectorMessage,
    ) -> ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionRevocationResult | None:
        if (
            message.role != ProjectDirectorMessageRole.USER
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent
            != "sandbox_candidate_diff_review_human_escalation_decision_revocation"
            or message.requires_confirmation is not False
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
            or len(message.suggested_actions) != 1
        ):
            return None
        action = message.suggested_actions[0]
        if not isinstance(action, dict) or action.get("type") != (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_ACTION_TYPE
        ):
            return None
        if action.get("schema_version") != HUMAN_ESCALATION_DECISION_REVOCATION_SCHEMA_VERSION:
            return None
        if (
            action.get("session_id") != str(message.session_id)
            or action.get("source_task_id") != str(message.related_task_id)
        ):
            return None
        try:
            result = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionRevocationResult.model_validate(
                {
                    key: value
                    for key, value in action.items()
                    if key not in {"type", "schema_version", "session_id", "source_task_id"}
                }
            )
        except ValidationError:
            return None
        if (
            action.get("revoke_actor") != result.revoke_actor
            or action.get("revoke_client_request_id")
            != result.revoke_client_request_id
        ):
            return None
        return result

    @staticmethod
    def _trusted_preflight(
        message: ProjectDirectorMessage,
    ) -> ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionPreflightResult | None:
        if (
            message.role != ProjectDirectorMessageRole.ASSISTANT
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent
            != "sandbox_candidate_diff_review_human_escalation_decision_consumption_preflight"
            or message.requires_confirmation is not False
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
            or len(message.suggested_actions) != 1
        ):
            return None
        action = message.suggested_actions[0]
        if not isinstance(action, dict) or action.get("type") != (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_ACTION_TYPE
        ):
            return None
        if action.get("schema_version") != (
            HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION
        ):
            return None
        if (
            action.get("session_id") != str(message.session_id)
            or action.get("source_task_id") != str(message.related_task_id)
        ):
            return None
        try:
            return ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionPreflightResult.model_validate(
                {
                    key: value
                    for key, value in action.items()
                    if key not in {"type", "schema_version", "session_id", "source_task_id"}
                }
            )
        except ValidationError:
            return None

    @staticmethod
    def _trusted_future_consumption(
        message: ProjectDirectorMessage,
    ) -> dict[str, Any] | None:
        if (
            message.role != ProjectDirectorMessageRole.ASSISTANT
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent
            != "sandbox_candidate_diff_review_human_escalation_decision_consumption"
            or message.requires_confirmation is not False
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
            or len(message.suggested_actions) != 1
        ):
            return None
        action = message.suggested_actions[0]
        if (
            not isinstance(action, dict)
            or action.get("type") != _FUTURE_DECISION_CONSUMPTION_ACTION_TYPE
            or action.get("session_id") != str(message.session_id)
            or action.get("source_task_id") != str(message.related_task_id)
            or not ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionLifecycleService._valid_uuid_text(
                action.get("source_decision_message_id")
            )
            or not ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionLifecycleService._valid_uuid_text(
                action.get("decision_id")
            )
            or action.get("decision_consumed") is not True
        ):
            return None
        return action

    @staticmethod
    def _revocation_action(
        *,
        session_id: UUID,
        source_task_id: UUID,
        result: ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionRevocationResult,
    ) -> dict[str, Any]:
        payload = result.model_dump(mode="json")
        payload.update(
            {
                "type": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_ACTION_TYPE,
                "schema_version": HUMAN_ESCALATION_DECISION_REVOCATION_SCHEMA_VERSION,
                "session_id": str(session_id),
                "source_task_id": str(source_task_id),
            }
        )
        return payload

    @staticmethod
    def _preflight_action(
        *,
        session_id: UUID,
        source_task_id: UUID,
        result: ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionPreflightResult,
    ) -> dict[str, Any]:
        payload = result.model_dump(mode="json")
        payload.update(
            {
                "type": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_ACTION_TYPE,
                "schema_version": HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION,
                "session_id": str(session_id),
                "source_task_id": str(source_task_id),
            }
        )
        return payload

    @staticmethod
    def _blocked_revocation(
        *,
        source_message_id: UUID,
        evidence: _ValidatedDecisionEvidence | None,
        actor: str,
        client_request_id: str,
        source_decision_validated: bool,
        fingerprint_revalidated: bool,
        replay_check_completed: bool,
        history: _LifecycleHistory,
        decision_expired: bool,
        blocked_reasons: list[str],
    ) -> RecordedSandboxCandidateDiffReviewHumanEscalationDecisionRevocation:
        revalidation = evidence.revalidation if evidence is not None else None
        return RecordedSandboxCandidateDiffReviewHumanEscalationDecisionRevocation(
            result=ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionRevocationResult(
                revocation_status="blocked",
                source_decision_message_id=source_message_id,
                decision_id=revalidation.decision_id if revalidation else None,
                source_package_message_id=(
                    revalidation.source_package_message_id if revalidation else None
                ),
                escalation_package_id=(
                    revalidation.escalation_package_id if revalidation else None
                ),
                decision_confirmation_fingerprint=(
                    evidence.stored_fingerprint if evidence else ""
                ),
                revalidated_decision_confirmation_fingerprint=(
                    revalidation.decision_confirmation_fingerprint
                    if revalidation
                    else ""
                ),
                revoke_actor_type="human",
                revoke_actor=actor,
                revoke_client_request_id=client_request_id,
                source_decision_validated=source_decision_validated,
                decision_fingerprint_revalidated=fingerprint_revalidated,
                replay_check_completed=replay_check_completed,
                prior_revocation_detected=history.decision_revoked,
                decision_revoked=history.decision_revoked,
                decision_expired=decision_expired,
                blocked_reasons=ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionLifecycleService._dedupe(
                    blocked_reasons
                ),
            ),
            message=None,
        )

    @staticmethod
    def _blocked_preflight(
        *,
        source_message_id: UUID,
        evidence: _ValidatedDecisionEvidence | None,
        evaluated_at: datetime | None,
        source_decision_validated: bool,
        fingerprint_revalidated: bool,
        replay_check_completed: bool,
        history: _LifecycleHistory,
        decision_expired: bool,
        blocked_reasons: list[str],
    ) -> PreparedSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionPreflight:
        revalidation = evidence.revalidation if evidence is not None else None
        return PreparedSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionPreflight(
            result=ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionPreflightResult(
                preflight_status="blocked",
                source_decision_message_id=source_message_id,
                decision_id=revalidation.decision_id if revalidation else None,
                source_package_message_id=(
                    revalidation.source_package_message_id if revalidation else None
                ),
                escalation_package_id=(
                    revalidation.escalation_package_id if revalidation else None
                ),
                decision_action=revalidation.decision_action if revalidation else None,
                decision_confirmation_fingerprint=(
                    evidence.stored_fingerprint if evidence else ""
                ),
                revalidated_decision_confirmation_fingerprint=(
                    revalidation.decision_confirmation_fingerprint
                    if revalidation
                    else ""
                ),
                decision_created_at=(
                    revalidation.decision_created_at if revalidation else None
                ),
                decision_expires_at=(
                    revalidation.decision_expires_at if revalidation else None
                ),
                evaluated_at=evaluated_at,
                source_decision_validated=source_decision_validated,
                decision_fingerprint_revalidated=fingerprint_revalidated,
                replay_check_completed=replay_check_completed,
                decision_active=False,
                decision_expired=decision_expired,
                decision_revoked=history.decision_revoked,
                prior_consumption_preflight_detected=(
                    history.prior_consumption_preflight_detected
                ),
                blocked_reasons=ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionLifecycleService._dedupe(
                    blocked_reasons
                ),
            ),
            message=None,
        )

    @staticmethod
    def _forbidden_actions() -> list[str]:
        return [
            "no_decision_consumption",
            "no_continuation_start",
            "no_rework_start",
            "no_task_creation",
            "no_run_creation",
            "no_worker_dispatch",
            "no_worktree_creation",
            "no_workspace_write",
            "no_main_project_file_write",
            "no_manifest_write",
            "no_diff_file_write",
            "no_patch_apply",
            "no_product_runtime_git_write",
            "no_pr_creation",
            "no_merge",
            "no_ci_trigger",
            "no_legacy_approval_request",
            "no_legacy_approval_decision",
        ]

    @staticmethod
    def _timezone_aware_datetime(value: Any) -> bool:
        return (
            isinstance(value, datetime)
            and value.tzinfo is not None
            and value.utcoffset() is not None
        )

    @staticmethod
    def _valid_uuid_text(value: Any) -> bool:
        if not isinstance(value, str) or not value:
            return False
        try:
            UUID(value)
        except ValueError:
            return False
        return True

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value in seen:
                continue
            result.append(value)
            seen.add(value)
        return result


__all__ = (
    "HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION",
    "HUMAN_ESCALATION_DECISION_REVOCATION_SCHEMA_VERSION",
    "P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_ACTION_TYPE",
    "P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL",
    "P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_ACTION_TYPE",
    "P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_SOURCE_DETAIL",
    "PreparedSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionPreflight",
    "ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionLifecycleService",
    "RecordedSandboxCandidateDiffReviewHumanEscalationDecisionRevocation",
)
