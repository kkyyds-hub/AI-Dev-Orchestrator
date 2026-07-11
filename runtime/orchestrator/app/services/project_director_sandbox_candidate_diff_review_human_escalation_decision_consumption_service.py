"""Atomic human escalation decision consumption for Project Director P21-D-D4."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_sandbox_candidate_diff_review_human_escalation_decision_consumption import (
    HumanEscalationDecisionTransitionKind,
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionResult,
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
from app.services.project_director_sandbox_candidate_diff_review_human_escalation_decision_lifecycle_service import (
    HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION,
    HUMAN_ESCALATION_DECISION_REVOCATION_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_candidate_diff_review_human_escalation_decision_service import (
    HUMAN_ESCALATION_DECISION_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionService,
    RevalidatedPersistedHumanEscalationDecisionFingerprint,
)


P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_SOURCE_DETAIL = (
    "p21_d_sandbox_candidate_diff_review_human_escalation_decision_consumed"
)
P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_ACTION_TYPE = (
    "p21_d_sandbox_candidate_diff_review_human_escalation_decision_consumption_record"
)
HUMAN_ESCALATION_DECISION_CONSUMPTION_SCHEMA_VERSION = "p21-d-d4.v1"

_CONSUMPTION_DOMAIN_FIELDS = (
    "consumption_status",
    "consumption_id",
    "source_preflight_message_id",
    "preflight_id",
    "source_decision_message_id",
    "decision_id",
    "source_package_message_id",
    "escalation_package_id",
    "decision_action",
    "decision_confirmation_fingerprint",
    "revalidated_decision_confirmation_fingerprint",
    "aggregate_evidence_fingerprint",
    "consumption_evidence_fingerprint",
    "decision_created_at",
    "decision_expires_at",
    "preflight_evaluated_at",
    "consumed_at",
    "source_preflight_validated",
    "source_decision_validated",
    "decision_fingerprint_revalidated",
    "exact_preflight_decision_binding_validated",
    "replay_check_completed",
    "decision_active_at_consumption",
    "decision_expired",
    "decision_revoked",
    "prior_consumption_detected",
    "blocked_reasons",
    "transition_kind",
    "continuation_guardrail_eligible",
    "bounded_rework_guardrail_eligible",
    "terminal_rejection",
    "gate_allows_protected_transition_guardrail",
    "decision_consumption_started",
    "decision_consumed",
    "continuation_started",
    "rework_started",
    "approval_request_created",
    "legacy_approval_decision_created",
    "main_project_file_written",
    "sandbox_file_written",
    "manifest_file_written",
    "diff_file_written",
    "patch_applied",
    "git_write_performed",
    "worktree_created",
    "worker_started",
    "task_created",
    "run_created",
    "gate_allows_write",
    "ai_project_director_total_loop",
)


@dataclass(frozen=True, slots=True)
class ConsumedSandboxCandidateDiffReviewHumanEscalationDecision:
    result: ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionResult
    message: ProjectDirectorMessage | None


@dataclass(frozen=True, slots=True)
class RevalidatedPersistedHumanEscalationDecisionConsumptionFingerprint:
    consumption_evidence_fingerprint: str
    blocked_reasons: list[str]
    source_consumption_message_id: UUID | None = None
    consumption_id: UUID | None = None
    source_preflight_message_id: UUID | None = None
    preflight_id: UUID | None = None
    source_decision_message_id: UUID | None = None
    decision_id: UUID | None = None
    source_package_message_id: UUID | None = None
    escalation_package_id: UUID | None = None
    decision_action: str | None = None
    decision_confirmation_fingerprint: str = ""
    revalidated_decision_confirmation_fingerprint: str = ""
    aggregate_evidence_fingerprint: str = ""
    decision_created_at: datetime | None = None
    decision_expires_at: datetime | None = None
    preflight_evaluated_at: datetime | None = None
    consumed_at: datetime | None = None
    transition_kind: HumanEscalationDecisionTransitionKind | None = None
    continuation_guardrail_eligible: bool = False
    bounded_rework_guardrail_eligible: bool = False
    terminal_rejection: bool = False
    gate_allows_protected_transition_guardrail: bool = False


@dataclass(frozen=True, slots=True)
class _ValidatedPreflightEvidence:
    action: dict[str, Any]
    result: ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionPreflightResult


@dataclass(frozen=True, slots=True)
class _ValidatedDecisionEvidence:
    action: dict[str, Any]
    stored_fingerprint: str
    revalidation: RevalidatedPersistedHumanEscalationDecisionFingerprint


@dataclass(frozen=True, slots=True)
class _ConsumptionHistory:
    decision_revoked: bool = False
    decision_consumed: bool = False
    preflight_consumed: bool = False
    multiple_ready_preflights: bool = False


class ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionService:
    """Consume one exact ready D3 preflight without executing its transition."""

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

    def consume_human_escalation_decision(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        consumed_at: datetime | None = None,
    ) -> ConsumedSandboxCandidateDiffReviewHumanEscalationDecision:
        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("human escalation decision consumption repositories required")
        with self._message_repository.sqlite_immediate_transaction():
            return self._consume_human_escalation_decision(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
                consumed_at=consumed_at,
            )

    @classmethod
    def revalidate_persisted_human_escalation_decision_consumption_fingerprint(
        cls,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_consumption_message_id: UUID,
        source_consumption_action: dict[str, Any],
    ) -> RevalidatedPersistedHumanEscalationDecisionConsumptionFingerprint:
        """Recompute one D4 evidence fingerprint without repository side effects."""

        blocked_reasons: list[str] = []
        action = source_consumption_action
        if (
            action.get("type")
            != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_ACTION_TYPE
        ):
            blocked_reasons.append("human_escalation_decision_consumption_action_type_invalid")
        if action.get("schema_version") != HUMAN_ESCALATION_DECISION_CONSUMPTION_SCHEMA_VERSION:
            blocked_reasons.append("human_escalation_decision_consumption_schema_version_mismatch")
        if action.get("session_id") != str(session_id):
            blocked_reasons.append("human_escalation_decision_consumption_session_mismatch")
        if action.get("source_task_id") != str(source_task_id):
            blocked_reasons.append("human_escalation_decision_consumption_task_mismatch")

        try:
            result = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionResult.model_validate(
                {
                    field_name: action.get(field_name)
                    for field_name in _CONSUMPTION_DOMAIN_FIELDS
                }
            )
        except ValidationError:
            result = None
            blocked_reasons.append(
                "human_escalation_decision_consumption_domain_reconstruction_invalid"
            )
        if result is not None and result.consumption_status != "consumed":
            blocked_reasons.append(
                "human_escalation_decision_consumption_domain_reconstruction_invalid"
            )
        if blocked_reasons or result is None:
            return RevalidatedPersistedHumanEscalationDecisionConsumptionFingerprint(
                consumption_evidence_fingerprint="",
                blocked_reasons=cls._dedupe(blocked_reasons),
                source_consumption_message_id=source_consumption_message_id,
            )

        canonical_payload = cls._consumption_evidence_canonical_payload(
            session_id=session_id,
            source_task_id=source_task_id,
            consumption_id=result.consumption_id,
            source_preflight_message_id=result.source_preflight_message_id,
            preflight_id=result.preflight_id,
            source_decision_message_id=result.source_decision_message_id,
            decision_id=result.decision_id,
            source_package_message_id=result.source_package_message_id,
            escalation_package_id=result.escalation_package_id,
            decision_action=result.decision_action,
            decision_confirmation_fingerprint=result.decision_confirmation_fingerprint,
            revalidated_decision_confirmation_fingerprint=(
                result.revalidated_decision_confirmation_fingerprint
            ),
            aggregate_evidence_fingerprint=result.aggregate_evidence_fingerprint,
            decision_created_at=result.decision_created_at,
            decision_expires_at=result.decision_expires_at,
            preflight_evaluated_at=result.preflight_evaluated_at,
            consumed_at=result.consumed_at,
            transition_kind=result.transition_kind,
            continuation_guardrail_eligible=result.continuation_guardrail_eligible,
            bounded_rework_guardrail_eligible=result.bounded_rework_guardrail_eligible,
            terminal_rejection=result.terminal_rejection,
            gate_allows_protected_transition_guardrail=(
                result.gate_allows_protected_transition_guardrail
            ),
        )
        return RevalidatedPersistedHumanEscalationDecisionConsumptionFingerprint(
            consumption_evidence_fingerprint=cls._canonical_payload_fingerprint(
                canonical_payload
            ),
            blocked_reasons=[],
            source_consumption_message_id=source_consumption_message_id,
            consumption_id=result.consumption_id,
            source_preflight_message_id=result.source_preflight_message_id,
            preflight_id=result.preflight_id,
            source_decision_message_id=result.source_decision_message_id,
            decision_id=result.decision_id,
            source_package_message_id=result.source_package_message_id,
            escalation_package_id=result.escalation_package_id,
            decision_action=result.decision_action,
            decision_confirmation_fingerprint=result.decision_confirmation_fingerprint,
            revalidated_decision_confirmation_fingerprint=(
                result.revalidated_decision_confirmation_fingerprint
            ),
            aggregate_evidence_fingerprint=result.aggregate_evidence_fingerprint,
            decision_created_at=result.decision_created_at,
            decision_expires_at=result.decision_expires_at,
            preflight_evaluated_at=result.preflight_evaluated_at,
            consumed_at=result.consumed_at,
            transition_kind=result.transition_kind,
            continuation_guardrail_eligible=result.continuation_guardrail_eligible,
            bounded_rework_guardrail_eligible=result.bounded_rework_guardrail_eligible,
            terminal_rejection=result.terminal_rejection,
            gate_allows_protected_transition_guardrail=(
                result.gate_allows_protected_transition_guardrail
            ),
        )

    def _consume_human_escalation_decision(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        consumed_at: datetime | None,
    ) -> ConsumedSandboxCandidateDiffReviewHumanEscalationDecision:
        blocked_reasons: list[str] = []
        preflight_evidence: _ValidatedPreflightEvidence | None = None
        decision_evidence: _ValidatedDecisionEvidence | None = None
        history = _ConsumptionHistory()
        normalized_consumed_at = consumed_at or datetime.now(timezone.utc)
        if not self._timezone_aware_datetime(normalized_consumed_at):
            blocked_reasons.append("human_escalation_decision_consumed_at_invalid")
            normalized_consumed_at = None

        session_obj = self._session_repository.get_by_id(session_id)
        source_task = self._task_repository.get_by_id(source_task_id)
        source_preflight_message = self._message_repository.get_by_id(source_message_id)
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
        if blocked_reasons or session_obj is None or source_task is None:
            return self._blocked_consumption(
                source_preflight_message_id=source_message_id,
                preflight_evidence=preflight_evidence,
                decision_evidence=decision_evidence,
                source_preflight_validated=False,
                source_decision_validated=False,
                fingerprint_revalidated=False,
                exact_binding_validated=False,
                replay_check_completed=False,
                history=history,
                decision_expired=False,
                blocked_reasons=blocked_reasons,
            )

        preflight_evidence = self._validated_preflight_evidence(
            source_message=source_preflight_message,
            session_id=session_id,
            source_task_id=source_task_id,
            source_project_id=session_obj.project_id,
            blocked_reasons=blocked_reasons,
        )
        if blocked_reasons or preflight_evidence is None:
            return self._blocked_consumption(
                source_preflight_message_id=source_message_id,
                preflight_evidence=preflight_evidence,
                decision_evidence=decision_evidence,
                source_preflight_validated=False,
                source_decision_validated=False,
                fingerprint_revalidated=False,
                exact_binding_validated=False,
                replay_check_completed=False,
                history=history,
                decision_expired=False,
                blocked_reasons=blocked_reasons,
            )

        preflight = preflight_evidence.result
        source_decision_message = self._message_repository.get_by_id(
            preflight.source_decision_message_id
        )
        decision_evidence = self._validated_decision_evidence(
            source_message=source_decision_message,
            session_id=session_id,
            source_task_id=source_task_id,
            source_project_id=session_obj.project_id,
            source_decision_message_id=preflight.source_decision_message_id,
            blocked_reasons=blocked_reasons,
        )
        if blocked_reasons or decision_evidence is None:
            return self._blocked_consumption(
                source_preflight_message_id=source_message_id,
                preflight_evidence=preflight_evidence,
                decision_evidence=decision_evidence,
                source_preflight_validated=True,
                source_decision_validated=False,
                fingerprint_revalidated=False,
                exact_binding_validated=False,
                replay_check_completed=False,
                history=history,
                decision_expired=False,
                blocked_reasons=blocked_reasons,
            )

        exact_binding_validated = self._validate_preflight_decision_binding(
            source_preflight_message_id=source_message_id,
            preflight=preflight,
            decision=decision_evidence,
            blocked_reasons=blocked_reasons,
        )
        if blocked_reasons:
            return self._blocked_consumption(
                source_preflight_message_id=source_message_id,
                preflight_evidence=preflight_evidence,
                decision_evidence=decision_evidence,
                source_preflight_validated=True,
                source_decision_validated=True,
                fingerprint_revalidated=True,
                exact_binding_validated=exact_binding_validated,
                replay_check_completed=False,
                history=history,
                decision_expired=False,
                blocked_reasons=blocked_reasons,
            )

        history = self._scan_consumption_history(
            session_id=session_id,
            source_project_id=session_obj.project_id,
            source_preflight_message_id=source_message_id,
            preflight_id=preflight.preflight_id,
            source_decision_message_id=preflight.source_decision_message_id,
            decision_id=preflight.decision_id,
            blocked_reasons=blocked_reasons,
        )
        decision_expired = (
            normalized_consumed_at >= decision_evidence.revalidation.decision_expires_at
        )
        if decision_expired:
            blocked_reasons.append("human_escalation_decision_expired")
        if history.decision_revoked:
            blocked_reasons.append("human_escalation_decision_revoked")
        if history.decision_consumed:
            blocked_reasons.append("human_escalation_decision_already_consumed")
        if history.preflight_consumed:
            blocked_reasons.append(
                "human_escalation_decision_preflight_already_consumed"
            )
        if history.multiple_ready_preflights:
            blocked_reasons.append(
                "human_escalation_decision_multiple_ready_preflights_detected"
            )
        blocked_reasons[:] = self._dedupe(blocked_reasons)
        if blocked_reasons:
            return self._blocked_consumption(
                source_preflight_message_id=source_message_id,
                preflight_evidence=preflight_evidence,
                decision_evidence=decision_evidence,
                source_preflight_validated=True,
                source_decision_validated=True,
                fingerprint_revalidated=True,
                exact_binding_validated=True,
                replay_check_completed=True,
                history=history,
                decision_expired=decision_expired,
                blocked_reasons=blocked_reasons,
            )

        transition = self._transition_for_action(decision_evidence.revalidation.decision_action)
        consumption_id = uuid4()
        canonical_payload = self._consumption_evidence_canonical_payload(
            session_id=session_id,
            source_task_id=source_task_id,
            consumption_id=consumption_id,
            source_preflight_message_id=source_message_id,
            preflight_id=preflight.preflight_id,
            source_decision_message_id=preflight.source_decision_message_id,
            decision_id=preflight.decision_id,
            source_package_message_id=preflight.source_package_message_id,
            escalation_package_id=preflight.escalation_package_id,
            decision_action=decision_evidence.revalidation.decision_action,
            decision_confirmation_fingerprint=decision_evidence.stored_fingerprint,
            revalidated_decision_confirmation_fingerprint=(
                decision_evidence.revalidation.decision_confirmation_fingerprint
            ),
            aggregate_evidence_fingerprint=(
                decision_evidence.revalidation.aggregate_evidence_fingerprint
            ),
            decision_created_at=decision_evidence.revalidation.decision_created_at,
            decision_expires_at=decision_evidence.revalidation.decision_expires_at,
            preflight_evaluated_at=preflight.evaluated_at,
            consumed_at=normalized_consumed_at,
            transition_kind=transition[0],
            continuation_guardrail_eligible=transition[1],
            bounded_rework_guardrail_eligible=transition[2],
            terminal_rejection=transition[3],
            gate_allows_protected_transition_guardrail=transition[4],
        )
        result = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionResult(
            consumption_status="consumed",
            consumption_id=consumption_id,
            source_preflight_message_id=source_message_id,
            preflight_id=preflight.preflight_id,
            source_decision_message_id=preflight.source_decision_message_id,
            decision_id=preflight.decision_id,
            source_package_message_id=preflight.source_package_message_id,
            escalation_package_id=preflight.escalation_package_id,
            decision_action=decision_evidence.revalidation.decision_action,
            decision_confirmation_fingerprint=decision_evidence.stored_fingerprint,
            revalidated_decision_confirmation_fingerprint=(
                decision_evidence.revalidation.decision_confirmation_fingerprint
            ),
            aggregate_evidence_fingerprint=(
                decision_evidence.revalidation.aggregate_evidence_fingerprint
            ),
            consumption_evidence_fingerprint=self._canonical_payload_fingerprint(
                canonical_payload
            ),
            decision_created_at=decision_evidence.revalidation.decision_created_at,
            decision_expires_at=decision_evidence.revalidation.decision_expires_at,
            preflight_evaluated_at=preflight.evaluated_at,
            consumed_at=normalized_consumed_at,
            source_preflight_validated=True,
            source_decision_validated=True,
            decision_fingerprint_revalidated=True,
            exact_preflight_decision_binding_validated=True,
            replay_check_completed=True,
            decision_active_at_consumption=True,
            decision_expired=False,
            decision_revoked=False,
            prior_consumption_detected=False,
            transition_kind=transition[0],
            continuation_guardrail_eligible=transition[1],
            bounded_rework_guardrail_eligible=transition[2],
            terminal_rejection=transition[3],
            gate_allows_protected_transition_guardrail=transition[4],
            decision_consumption_started=True,
            decision_consumed=True,
        )
        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "The exact D3 ready preflight decision was atomically consumed. "
                    "Only the next protected transition guardrail eligibility was "
                    "produced: APPROVE_CONTINUE did not start continuation, "
                    "REQUEST_REWORK did not start rework, and REJECT only forms a "
                    "terminal rejection. No Task, Run, Worker, worktree, file write, "
                    "patch apply, or Git write authorization was created. P21-D-E "
                    "final evidence freshness gate is still required, and AI Project "
                    "Director total loop remains Partial."
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="sandbox_candidate_diff_review_human_escalation_decision_consumption",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=(
                    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_SOURCE_DETAIL
                ),
                suggested_actions=[
                    self._consumption_action(
                        session_id=session_id,
                        source_task_id=source_task_id,
                        result=result,
                    )
                ],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                forbidden_actions_detected=self._forbidden_actions(),
                created_at=normalized_consumed_at,
            )
        )
        return ConsumedSandboxCandidateDiffReviewHumanEscalationDecision(
            result=result,
            message=message,
        )

    @staticmethod
    def _validated_preflight_evidence(
        *,
        source_message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        source_project_id: UUID | None,
        blocked_reasons: list[str],
    ) -> _ValidatedPreflightEvidence | None:
        if source_message is None:
            blocked_reasons.append("source_consumption_preflight_message_missing")
            return None
        checks = (
            (source_message.session_id == session_id, "source_preflight_session_mismatch"),
            (source_message.related_project_id == source_project_id, "source_preflight_project_mismatch"),
            (source_message.related_task_id == source_task_id, "source_preflight_task_mismatch"),
            (source_message.role == ProjectDirectorMessageRole.ASSISTANT, "source_preflight_role_invalid"),
            (source_message.source == ProjectDirectorMessageSource.SYSTEM, "source_preflight_source_invalid"),
            (
                source_message.intent
                == "sandbox_candidate_diff_review_human_escalation_decision_consumption_preflight",
                "source_preflight_intent_invalid",
            ),
            (
                source_message.source_detail
                == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL,
                "source_message_is_not_p21_d_d3_ready_preflight",
            ),
            (source_message.requires_confirmation is False, "source_preflight_confirmation_contract_invalid"),
            (source_message.risk_level == ProjectDirectorMessageRiskLevel.HIGH, "source_preflight_risk_level_invalid"),
        )
        for valid, reason in checks:
            if not valid:
                blocked_reasons.append(reason)
        if len(source_message.suggested_actions) != 1:
            blocked_reasons.append("source_consumption_preflight_record_missing")
            return None
        action = source_message.suggested_actions[0]
        if (
            not isinstance(action, dict)
            or action.get("type")
            != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_ACTION_TYPE
            or action.get("schema_version")
            != HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION
            or action.get("session_id") != str(session_id)
            or action.get("source_task_id") != str(source_task_id)
        ):
            blocked_reasons.append("source_consumption_preflight_record_invalid")
            return None
        try:
            result = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionPreflightResult.model_validate(
                {
                    key: value
                    for key, value in action.items()
                    if key not in {"type", "schema_version", "session_id", "source_task_id"}
                }
            )
        except ValidationError:
            blocked_reasons.append("source_preflight_domain_reconstruction_invalid")
            return None
        if (
            result.preflight_status != "ready"
            or result.evaluated_at is None
            or result.decision_expires_at is None
            or result.evaluated_at >= result.decision_expires_at
        ):
            blocked_reasons.append("source_preflight_domain_reconstruction_invalid")
            return None
        return _ValidatedPreflightEvidence(action=action, result=result)

    @staticmethod
    def _validated_decision_evidence(
        *,
        source_message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        source_project_id: UUID | None,
        source_decision_message_id: UUID,
        blocked_reasons: list[str],
    ) -> _ValidatedDecisionEvidence | None:
        if source_message is None:
            blocked_reasons.append("source_human_escalation_decision_message_missing")
            return None
        checks = (
            (source_message.session_id == session_id, "source_decision_session_mismatch"),
            (source_message.related_project_id == source_project_id, "source_decision_project_mismatch"),
            (source_message.related_task_id == source_task_id, "source_decision_task_mismatch"),
            (source_message.role == ProjectDirectorMessageRole.USER, "source_decision_role_invalid"),
            (source_message.source == ProjectDirectorMessageSource.SYSTEM, "source_decision_source_invalid"),
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
            (source_message.requires_confirmation is False, "source_decision_confirmation_contract_invalid"),
            (source_message.risk_level == ProjectDirectorMessageRiskLevel.HIGH, "source_decision_risk_level_invalid"),
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
            or action.get("schema_version") != HUMAN_ESCALATION_DECISION_SCHEMA_VERSION
            or action.get("decision_status") != "recorded"
        ):
            blocked_reasons.append("source_human_escalation_decision_record_invalid")
            return None
        revalidation = (
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionService
            .revalidate_persisted_human_escalation_decision_fingerprint(
                session_id=session_id,
                source_task_id=source_task_id,
                source_decision_message_id=source_decision_message_id,
                source_decision_action=action,
            )
        )
        blocked_reasons.extend(revalidation.blocked_reasons)
        stored_fingerprint = action.get("decision_confirmation_fingerprint")
        if not isinstance(stored_fingerprint, str):
            blocked_reasons.append("decision_confirmation_fingerprint_invalid")
            return None
        if stored_fingerprint != revalidation.decision_confirmation_fingerprint:
            blocked_reasons.append("decision_confirmation_fingerprint_mismatch")
        if blocked_reasons:
            return None
        return _ValidatedDecisionEvidence(
            action=action,
            stored_fingerprint=stored_fingerprint,
            revalidation=revalidation,
        )

    @classmethod
    def _validate_preflight_decision_binding(
        cls,
        *,
        source_preflight_message_id: UUID,
        preflight: ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionPreflightResult,
        decision: _ValidatedDecisionEvidence,
        blocked_reasons: list[str],
    ) -> bool:
        revalidation = decision.revalidation
        expected_bindings = (
            (preflight.source_decision_message_id, revalidation.source_decision_message_id),
            (preflight.decision_id, revalidation.decision_id),
            (preflight.source_package_message_id, revalidation.source_package_message_id),
            (preflight.escalation_package_id, revalidation.escalation_package_id),
            (preflight.decision_action, revalidation.decision_action),
            (preflight.decision_created_at, revalidation.decision_created_at),
            (preflight.decision_expires_at, revalidation.decision_expires_at),
            (preflight.decision_confirmation_fingerprint, decision.stored_fingerprint),
            (
                preflight.revalidated_decision_confirmation_fingerprint,
                revalidation.decision_confirmation_fingerprint,
            ),
        )
        if any(actual != expected for actual, expected in expected_bindings):
            blocked_reasons.append("consumption_preflight_decision_binding_mismatch")
        expected_eligibility = cls._preflight_eligibility_for_action(
            revalidation.decision_action
        )
        actual_eligibility = (
            preflight.continuation_eligible,
            preflight.rework_eligible,
            preflight.rejection_terminal,
        )
        if actual_eligibility != expected_eligibility:
            blocked_reasons.append("consumption_preflight_eligibility_mismatch")
        if source_preflight_message_id == preflight.source_decision_message_id:
            blocked_reasons.append("consumption_preflight_decision_binding_mismatch")
        return not blocked_reasons

    def _scan_consumption_history(
        self,
        *,
        session_id: UUID,
        source_project_id: UUID | None,
        source_preflight_message_id: UUID,
        preflight_id: UUID | None,
        source_decision_message_id: UUID,
        decision_id: UUID | None,
        blocked_reasons: list[str],
    ) -> _ConsumptionHistory:
        decision_revoked = False
        decision_consumed = False
        preflight_consumed = False
        multiple_ready_preflights = False
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
                    revocation = self._trusted_revocation(
                        message=message,
                        source_project_id=source_project_id,
                    )
                    if revocation is None:
                        blocked_reasons.append(
                            "prior_human_escalation_decision_revocation_record_invalid"
                        )
                    elif (
                        revocation.source_decision_message_id == source_decision_message_id
                        or revocation.decision_id == decision_id
                    ):
                        decision_revoked = True
                elif message.source_detail == (
                    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL
                ):
                    prior_preflight = self._trusted_preflight(
                        message=message,
                        source_project_id=source_project_id,
                    )
                    if prior_preflight is None:
                        blocked_reasons.append(
                            "prior_human_escalation_decision_preflight_record_invalid"
                        )
                    elif (
                        message.id != source_preflight_message_id
                        and (
                            prior_preflight.preflight_id == preflight_id
                            or prior_preflight.source_decision_message_id
                            == source_decision_message_id
                            or prior_preflight.decision_id == decision_id
                        )
                    ):
                        multiple_ready_preflights = True
                elif message.source_detail == (
                    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_SOURCE_DETAIL
                ):
                    prior_consumption = self._trusted_consumption(
                        message=message,
                        source_project_id=source_project_id,
                    )
                    if prior_consumption is None:
                        blocked_reasons.append(
                            "prior_human_escalation_decision_consumption_record_invalid"
                        )
                    else:
                        if (
                            prior_consumption.source_decision_message_id
                            == source_decision_message_id
                            or prior_consumption.decision_id == decision_id
                        ):
                            decision_consumed = True
                        if (
                            prior_consumption.source_preflight_message_id
                            == source_preflight_message_id
                            or prior_consumption.preflight_id == preflight_id
                        ):
                            preflight_consumed = True
            if not has_more or not messages:
                break
            before_message_id = messages[0].id
        blocked_reasons[:] = self._dedupe(blocked_reasons)
        return _ConsumptionHistory(
            decision_revoked=decision_revoked,
            decision_consumed=decision_consumed,
            preflight_consumed=preflight_consumed,
            multiple_ready_preflights=multiple_ready_preflights,
        )

    @staticmethod
    def _trusted_revocation(
        *,
        message: ProjectDirectorMessage,
        source_project_id: UUID | None,
    ) -> ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionRevocationResult | None:
        if (
            message.related_project_id != source_project_id
            or message.related_task_id is None
            or message.role != ProjectDirectorMessageRole.USER
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent
            != "sandbox_candidate_diff_review_human_escalation_decision_revocation"
            or message.requires_confirmation is not False
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
            or len(message.suggested_actions) != 1
        ):
            return None
        action = message.suggested_actions[0]
        if (
            not isinstance(action, dict)
            or action.get("type")
            != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_ACTION_TYPE
            or action.get("schema_version")
            != HUMAN_ESCALATION_DECISION_REVOCATION_SCHEMA_VERSION
            or action.get("session_id") != str(message.session_id)
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
        return result if result.revocation_status == "revoked" else None

    @staticmethod
    def _trusted_preflight(
        *,
        message: ProjectDirectorMessage,
        source_project_id: UUID | None,
    ) -> ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionPreflightResult | None:
        if (
            message.related_project_id != source_project_id
            or message.related_task_id is None
            or message.role != ProjectDirectorMessageRole.ASSISTANT
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent
            != "sandbox_candidate_diff_review_human_escalation_decision_consumption_preflight"
            or message.requires_confirmation is not False
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
            or len(message.suggested_actions) != 1
        ):
            return None
        action = message.suggested_actions[0]
        if (
            not isinstance(action, dict)
            or action.get("type")
            != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_ACTION_TYPE
            or action.get("schema_version")
            != HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION
            or action.get("session_id") != str(message.session_id)
            or action.get("source_task_id") != str(message.related_task_id)
        ):
            return None
        try:
            result = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionPreflightResult.model_validate(
                {
                    key: value
                    for key, value in action.items()
                    if key not in {"type", "schema_version", "session_id", "source_task_id"}
                }
            )
        except ValidationError:
            return None
        if (
            result.preflight_status != "ready"
            or result.evaluated_at is None
            or result.decision_expires_at is None
            or result.evaluated_at >= result.decision_expires_at
        ):
            return None
        return result

    @staticmethod
    def _trusted_consumption(
        *,
        message: ProjectDirectorMessage,
        source_project_id: UUID | None,
    ) -> ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionResult | None:
        if (
            message.related_project_id != source_project_id
            or message.related_task_id is None
            or message.role != ProjectDirectorMessageRole.ASSISTANT
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
            or action.get("type")
            != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_ACTION_TYPE
            or action.get("schema_version")
            != HUMAN_ESCALATION_DECISION_CONSUMPTION_SCHEMA_VERSION
            or action.get("session_id") != str(message.session_id)
            or action.get("source_task_id") != str(message.related_task_id)
        ):
            return None
        try:
            result = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionResult.model_validate(
                {
                    field_name: action.get(field_name)
                    for field_name in _CONSUMPTION_DOMAIN_FIELDS
                }
            )
        except ValidationError:
            return None
        if result.consumption_status != "consumed":
            return None
        revalidation = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionService.revalidate_persisted_human_escalation_decision_consumption_fingerprint(
            session_id=message.session_id,
            source_task_id=message.related_task_id,
            source_consumption_message_id=message.id,
            source_consumption_action=action,
        )
        if revalidation.blocked_reasons or (
            action.get("consumption_evidence_fingerprint")
            != revalidation.consumption_evidence_fingerprint
        ):
            return None
        return result

    @staticmethod
    def _transition_for_action(
        decision_action: str | None,
    ) -> tuple[HumanEscalationDecisionTransitionKind, bool, bool, bool, bool]:
        mapping = {
            "APPROVE_CONTINUE": (
                "CONTINUE_GUARDRAIL",
                True,
                False,
                False,
                True,
            ),
            "REQUEST_REWORK": (
                "BOUNDED_REWORK_GUARDRAIL",
                False,
                True,
                False,
                True,
            ),
            "REJECT": (
                "TERMINAL_REJECTION",
                False,
                False,
                True,
                False,
            ),
        }
        if decision_action not in mapping:
            raise ValueError("validated human escalation decision action required")
        return mapping[decision_action]

    @staticmethod
    def _preflight_eligibility_for_action(
        decision_action: str | None,
    ) -> tuple[bool, bool, bool] | None:
        return {
            "APPROVE_CONTINUE": (True, False, False),
            "REQUEST_REWORK": (False, True, False),
            "REJECT": (False, False, True),
        }.get(decision_action)

    @staticmethod
    def _consumption_evidence_canonical_payload(
        *,
        session_id: UUID,
        source_task_id: UUID,
        consumption_id: UUID,
        source_preflight_message_id: UUID,
        preflight_id: UUID,
        source_decision_message_id: UUID,
        decision_id: UUID,
        source_package_message_id: UUID,
        escalation_package_id: UUID,
        decision_action: str,
        decision_confirmation_fingerprint: str,
        revalidated_decision_confirmation_fingerprint: str,
        aggregate_evidence_fingerprint: str,
        decision_created_at: datetime,
        decision_expires_at: datetime,
        preflight_evaluated_at: datetime,
        consumed_at: datetime,
        transition_kind: HumanEscalationDecisionTransitionKind,
        continuation_guardrail_eligible: bool,
        bounded_rework_guardrail_eligible: bool,
        terminal_rejection: bool,
        gate_allows_protected_transition_guardrail: bool,
    ) -> dict[str, Any]:
        return {
            "schema_version": HUMAN_ESCALATION_DECISION_CONSUMPTION_SCHEMA_VERSION,
            "session_id": str(session_id),
            "source_task_id": str(source_task_id),
            "consumption_id": str(consumption_id),
            "source_preflight_message_id": str(source_preflight_message_id),
            "preflight_id": str(preflight_id),
            "source_decision_message_id": str(source_decision_message_id),
            "decision_id": str(decision_id),
            "source_package_message_id": str(source_package_message_id),
            "escalation_package_id": str(escalation_package_id),
            "decision_action": decision_action,
            "decision_confirmation_fingerprint": decision_confirmation_fingerprint,
            "revalidated_decision_confirmation_fingerprint": (
                revalidated_decision_confirmation_fingerprint
            ),
            "aggregate_evidence_fingerprint": aggregate_evidence_fingerprint,
            "decision_created_at": decision_created_at.isoformat(),
            "decision_expires_at": decision_expires_at.isoformat(),
            "preflight_evaluated_at": preflight_evaluated_at.isoformat(),
            "consumed_at": consumed_at.isoformat(),
            "transition_kind": transition_kind,
            "continuation_guardrail_eligible": continuation_guardrail_eligible,
            "bounded_rework_guardrail_eligible": bounded_rework_guardrail_eligible,
            "terminal_rejection": terminal_rejection,
            "gate_allows_protected_transition_guardrail": (
                gate_allows_protected_transition_guardrail
            ),
        }

    @staticmethod
    def _canonical_payload_fingerprint(canonical_payload: dict[str, Any]) -> str:
        canonical_json = json.dumps(
            canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @staticmethod
    def _consumption_action(
        *,
        session_id: UUID,
        source_task_id: UUID,
        result: ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionResult,
    ) -> dict[str, Any]:
        payload = result.model_dump(mode="json")
        payload.update(
            {
                "type": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_ACTION_TYPE,
                "schema_version": HUMAN_ESCALATION_DECISION_CONSUMPTION_SCHEMA_VERSION,
                "session_id": str(session_id),
                "source_task_id": str(source_task_id),
            }
        )
        return payload

    @staticmethod
    def _blocked_consumption(
        *,
        source_preflight_message_id: UUID,
        preflight_evidence: _ValidatedPreflightEvidence | None,
        decision_evidence: _ValidatedDecisionEvidence | None,
        source_preflight_validated: bool,
        source_decision_validated: bool,
        fingerprint_revalidated: bool,
        exact_binding_validated: bool,
        replay_check_completed: bool,
        history: _ConsumptionHistory,
        decision_expired: bool,
        blocked_reasons: list[str],
    ) -> ConsumedSandboxCandidateDiffReviewHumanEscalationDecision:
        preflight = preflight_evidence.result if preflight_evidence else None
        revalidation = decision_evidence.revalidation if decision_evidence else None
        return ConsumedSandboxCandidateDiffReviewHumanEscalationDecision(
            result=ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionResult(
                consumption_status="blocked",
                source_preflight_message_id=source_preflight_message_id,
                preflight_id=preflight.preflight_id if preflight else None,
                source_decision_message_id=(
                    preflight.source_decision_message_id if preflight else None
                ),
                decision_id=preflight.decision_id if preflight else None,
                source_package_message_id=(
                    preflight.source_package_message_id if preflight else None
                ),
                escalation_package_id=(
                    preflight.escalation_package_id if preflight else None
                ),
                decision_action=(
                    revalidation.decision_action
                    if revalidation
                    else preflight.decision_action if preflight else None
                ),
                decision_confirmation_fingerprint=(
                    decision_evidence.stored_fingerprint
                    if decision_evidence
                    else preflight.decision_confirmation_fingerprint if preflight else ""
                ),
                revalidated_decision_confirmation_fingerprint=(
                    revalidation.decision_confirmation_fingerprint
                    if revalidation
                    else (
                        preflight.revalidated_decision_confirmation_fingerprint
                        if preflight
                        else ""
                    )
                ),
                aggregate_evidence_fingerprint=(
                    revalidation.aggregate_evidence_fingerprint if revalidation else ""
                ),
                decision_created_at=(
                    revalidation.decision_created_at
                    if revalidation
                    else preflight.decision_created_at if preflight else None
                ),
                decision_expires_at=(
                    revalidation.decision_expires_at
                    if revalidation
                    else preflight.decision_expires_at if preflight else None
                ),
                preflight_evaluated_at=preflight.evaluated_at if preflight else None,
                source_preflight_validated=source_preflight_validated,
                source_decision_validated=source_decision_validated,
                decision_fingerprint_revalidated=fingerprint_revalidated,
                exact_preflight_decision_binding_validated=exact_binding_validated,
                replay_check_completed=replay_check_completed,
                decision_active_at_consumption=False,
                decision_expired=decision_expired,
                decision_revoked=history.decision_revoked,
                prior_consumption_detected=(
                    history.decision_consumed or history.preflight_consumed
                ),
                blocked_reasons=ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionService._dedupe(
                    blocked_reasons
                ),
            ),
            message=None,
        )

    @staticmethod
    def _forbidden_actions() -> list[str]:
        return [
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
            "p21_d_e_freshness_gate_required",
        ]

    @staticmethod
    def _timezone_aware_datetime(value: Any) -> bool:
        return (
            isinstance(value, datetime)
            and value.tzinfo is not None
            and value.utcoffset() is not None
        )

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
    "ConsumedSandboxCandidateDiffReviewHumanEscalationDecision",
    "HUMAN_ESCALATION_DECISION_CONSUMPTION_SCHEMA_VERSION",
    "P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_ACTION_TYPE",
    "P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_SOURCE_DETAIL",
    "ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionService",
    "RevalidatedPersistedHumanEscalationDecisionConsumptionFingerprint",
)
