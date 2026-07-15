"""Project Director P23-B 受保护转换调度意图准备服务。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.domain.project_director_bounded_rework_convergence import (
    ProjectDirectorBoundedReworkConvergenceDecision,
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
from app.domain.project_director_protected_transition_dispatch_intent import (
    ProjectDirectorProtectedTransitionDispatchIntentResult,
)
from app.domain.project_director_protected_transition_evidence_freshness import (
    ProjectDirectorProtectedTransitionEvidenceFreshnessResult,
)
from app.domain.project_director_sandbox_candidate_diff_review_disposition import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionResult,
)
from app.domain.project_director_sandbox_candidate_diff_review_disposition_consumption import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult,
)
from app.domain.project_director_sandbox_candidate_diff_review_disposition_consumption_preflight import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightResult,
)
from app.domain.project_director_sandbox_candidate_diff_review_disposition_handoff import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult,
)
from app.domain.project_director_sandbox_candidate_diff_review_output import (
    ProjectDirectorSandboxCandidateDiffValidatedReviewOutput,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_post_review_automation_service import (
    P22_POST_REVIEW_AUTOMATION_ACTION_TYPE,
    P22_POST_REVIEW_AUTOMATION_SOURCE_DETAIL,
    POST_REVIEW_AUTOMATION_SCHEMA_VERSION,
)
from app.services.project_director_bounded_rework_convergence_service import (
    ProjectDirectorBoundedReworkConvergenceService,
)
from app.services.project_director_protected_transition_evidence_freshness_service import (
    P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_ACTION_TYPE,
    P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SOURCE_DETAIL,
    PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SCHEMA_VERSION,
    ProjectDirectorProtectedTransitionEvidenceFreshnessService,
)
from app.services.project_director_sandbox_candidate_diff_readonly_review_execution_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_consumption_preflight_service import (
    DISPOSITION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_consumption_service import (
    DISPOSITION_CONSUMPTION_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMED_SOURCE_DETAIL,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_ACTION_TYPE,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_handoff_service import (
    DISPOSITION_HANDOFF_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_service import (
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL,
    REVIEW_DISPOSITION_SCHEMA_VERSION,
    ProjectDirectorSandboxCandidateDiffReviewDispositionService,
)
from app.services.project_director_sandbox_candidate_diff_review_execution_preflight_service import (
    REVIEW_OUTPUT_SCHEMA_VERSION,
)


P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL = (
    "p23_protected_transition_dispatch_intent_prepared"
)
P23_PROTECTED_TRANSITION_DISPATCH_INTENT_ACTION_TYPE = (
    "p23_protected_transition_dispatch_intent_record"
)
PROTECTED_TRANSITION_DISPATCH_INTENT_SCHEMA_VERSION = "p23-b.v1"
PROTECTED_TRANSITION_REWORK_ATTEMPT_LIMIT = 3

_INTENT = "protected_transition_dispatch_intent"
_PAGE_SIZE = 100


@dataclass(frozen=True, slots=True)
class PreparedProjectDirectorProtectedTransitionDispatchIntent:
    """调度意图准备结果及其 append-only message。"""

    result: ProjectDirectorProtectedTransitionDispatchIntentResult
    message: ProjectDirectorMessage | None


@dataclass(frozen=True, slots=True)
class RevalidatedPersistedProtectedTransitionDispatchIntent:
    """对一条已持久化 P23-B 调度意图的纯重验结果。"""

    result: ProjectDirectorProtectedTransitionDispatchIntentResult | None
    message: ProjectDirectorMessage | None
    blocked_reasons: list[str]


@dataclass(frozen=True, slots=True)
class _EvidenceChain:
    summary: ProjectDirectorPostReviewAutomationResult
    review_action: dict[str, Any]
    disposition: ProjectDirectorSandboxCandidateDiffReviewDispositionResult
    preflight: ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightResult
    consumption: ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult
    handoff: ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult
    freshness: ProjectDirectorProtectedTransitionEvidenceFreshnessResult
    review_semantic_fingerprint: str
    p25_convergence_decision: (
        ProjectDirectorBoundedReworkConvergenceDecision | None
    ) = None
    p25_convergence_decision_message: ProjectDirectorMessage | None = None


@dataclass(frozen=True, slots=True)
class _IntentHistory:
    valid_intents: list[
        tuple[
            ProjectDirectorProtectedTransitionDispatchIntentResult,
            ProjectDirectorMessage,
        ]
    ]
    invalid: bool = False


class ProjectDirectorProtectedTransitionDispatchIntentService:
    """从 exact persisted P22 证据准备可重放的调度意图。"""

    def __init__(
        self,
        *,
        session_repository: ProjectDirectorSessionRepository,
        message_repository: ProjectDirectorMessageRepository,
        task_repository: TaskRepository,
        bounded_rework_convergence_service: (
            ProjectDirectorBoundedReworkConvergenceService | None
        ) = None,
    ) -> None:
        self._session_repository = session_repository
        self._message_repository = message_repository
        self._task_repository = task_repository
        self._bounded_rework_convergence_service = (
            bounded_rework_convergence_service
        )
        if (
            bounded_rework_convergence_service is not None
            and bounded_rework_convergence_service._message_repository
            is not message_repository
        ):
            raise ValueError("P23 and P25-I-B must share one message repository")

    def prepare_protected_transition_dispatch_intent(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
    ) -> PreparedProjectDirectorProtectedTransitionDispatchIntent:
        """在一个立即事务内验证证据、检查 replay 并持久化意图。"""

        with self._message_repository.sqlite_immediate_transaction():
            return self._prepare_protected_transition_dispatch_intent(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
            )

    def revalidate_persisted_protected_transition_dispatch_intent(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_intent_message_id: UUID,
    ) -> RevalidatedPersistedProtectedTransitionDispatchIntent:
        """在调用方事务内纯重验 exact persisted P23-B 调度意图。"""

        source_message = self._message_repository.get_by_id(
            source_intent_message_id
        )
        if source_message is None:
            return RevalidatedPersistedProtectedTransitionDispatchIntent(
                result=None,
                message=None,
                blocked_reasons=["source_dispatch_intent_missing"],
            )
        if source_message.session_id != session_id:
            return RevalidatedPersistedProtectedTransitionDispatchIntent(
                result=None,
                message=source_message,
                blocked_reasons=["source_dispatch_intent_session_mismatch"],
            )
        if source_message.related_task_id != source_task_id:
            return RevalidatedPersistedProtectedTransitionDispatchIntent(
                result=None,
                message=source_message,
                blocked_reasons=["source_dispatch_intent_task_mismatch"],
            )

        session = self._session_repository.get_by_id(session_id)
        task = self._task_repository.get_by_id(source_task_id)
        if session is None or session.project_id is None:
            return RevalidatedPersistedProtectedTransitionDispatchIntent(
                result=None,
                message=source_message,
                blocked_reasons=["source_dispatch_intent_invalid"],
            )
        if task is None or task.project_id != session.project_id:
            return RevalidatedPersistedProtectedTransitionDispatchIntent(
                result=None,
                message=source_message,
                blocked_reasons=["source_dispatch_intent_project_mismatch"],
            )

        result = self._trusted_persisted_intent(
            message=source_message,
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=session.project_id,
        )
        if result is None:
            return RevalidatedPersistedProtectedTransitionDispatchIntent(
                result=None,
                message=source_message,
                blocked_reasons=["source_dispatch_intent_invalid"],
            )
        if result.intent_status != "prepared":
            return RevalidatedPersistedProtectedTransitionDispatchIntent(
                result=result,
                message=source_message,
                blocked_reasons=["source_dispatch_intent_not_prepared"],
            )

        summary_message = self._message_repository.get_by_id(
            result.source_p22_summary_message_id
        )
        summary, _summary_action, summary_reasons = self._trusted_p22_summary(
            message=summary_message,
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=session.project_id,
            source_message_id=result.source_p22_summary_message_id,
        )
        if summary_reasons or summary is None:
            return RevalidatedPersistedProtectedTransitionDispatchIntent(
                result=result,
                message=source_message,
                blocked_reasons=["source_p22_summary_invalid"],
            )
        chain, chain_reasons = self._load_exact_evidence_chain(
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=session.project_id,
            source_p22_summary_message_id=result.source_p22_summary_message_id,
            summary=summary,
        )
        if chain_reasons or chain is None:
            return RevalidatedPersistedProtectedTransitionDispatchIntent(
                result=result,
                message=source_message,
                blocked_reasons=["source_evidence_chain_invalid"],
            )

        history = self._scan_intent_history(
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=session.project_id,
        )
        replay_matches = [
            item
            for item in history.valid_intents
            if item[0].source_p22_summary_message_id
            == result.source_p22_summary_message_id
            and item[0].dispatch_kind == result.dispatch_kind
        ]
        decision_matches = self._p25_decision_intent_matches(
            history=history,
            chain=chain,
        )
        attempt_index, attempt_invalid = self._rework_attempt_index(
            history=history,
            replay_matches=replay_matches,
            dispatch_kind=result.dispatch_kind or "",
        )
        if (
            history.invalid
            or attempt_invalid
            or len(replay_matches) != 1
            or replay_matches[0][1].id != source_intent_message_id
            or len(decision_matches) > 1
            or (decision_matches and decision_matches != replay_matches)
        ):
            return RevalidatedPersistedProtectedTransitionDispatchIntent(
                result=result,
                message=source_message,
                blocked_reasons=["dispatch_intent_replay_conflict"],
            )
        if self._p25_attempt_history_invalid(
            chain=chain,
            attempt_index=attempt_index,
        ):
            return RevalidatedPersistedProtectedTransitionDispatchIntent(
                result=result,
                message=source_message,
                blocked_reasons=["rework_attempt_history_invalid"],
            )

        dispatch_kind, target_strategy = self._dispatch_mapping(
            summary.disposition_type
        )
        expected = self._prepared_result(
            dispatch_intent_id=result.dispatch_intent_id,
            session_id=session_id,
            project_id=session.project_id,
            source_task_id=source_task_id,
            source_message_id=result.source_p22_summary_message_id,
            chain=chain,
            dispatch_kind=dispatch_kind,
            target_strategy=target_strategy,
            attempt_index=result.rework_attempt_index,
        )
        if expected.dispatch_intent_fingerprint != result.dispatch_intent_fingerprint:
            reason = (
                "convergence_decision_conflict"
                if chain.p25_convergence_decision is not None
                else "source_dispatch_intent_invalid"
            )
            return RevalidatedPersistedProtectedTransitionDispatchIntent(
                result=result,
                message=source_message,
                blocked_reasons=[reason],
            )
        return RevalidatedPersistedProtectedTransitionDispatchIntent(
            result=result,
            message=source_message,
            blocked_reasons=[],
        )

    def _prepare_protected_transition_dispatch_intent(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
    ) -> PreparedProjectDirectorProtectedTransitionDispatchIntent:
        session = self._session_repository.get_by_id(session_id)
        if session is None:
            return self._blocked(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
                reasons=["source_p22_summary_invalid"],
            )
        task = self._task_repository.get_by_id(source_task_id)
        if (
            session.project_id is None
            or task is None
            or task.project_id != session.project_id
        ):
            return self._blocked(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
                project_id=session.project_id,
                reasons=["source_p22_summary_project_mismatch"],
            )

        source_message = self._message_repository.get_by_id(source_message_id)
        summary, summary_action, reasons = self._trusted_p22_summary(
            message=source_message,
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=session.project_id,
            source_message_id=source_message_id,
        )
        if (
            reasons == ["source_p22_summary_human_route_unhandled"]
            and summary is not None
        ):
            p25_terminal_reason = self._p25_terminal_reason_for_summary(
                session_id=session_id,
                source_task_id=source_task_id,
                project_id=session.project_id,
                source_p22_summary_message_id=source_message_id,
                summary=summary,
            )
            if p25_terminal_reason is not None:
                reasons = [p25_terminal_reason]
        if reasons or summary is None or summary_action is None:
            return self._blocked(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
                project_id=session.project_id,
                reasons=reasons or ["source_p22_summary_invalid"],
            )

        chain, reasons = self._load_exact_evidence_chain(
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=session.project_id,
            source_p22_summary_message_id=source_message_id,
            summary=summary,
        )
        if reasons or chain is None:
            return self._blocked_from_summary(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
                project_id=session.project_id,
                summary=summary,
                reasons=reasons or ["source_evidence_chain_invalid"],
            )

        dispatch_kind, target_strategy = self._dispatch_mapping(
            summary.disposition_type
        )
        history = self._scan_intent_history(
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=session.project_id,
        )
        if history.invalid:
            reason = (
                "rework_attempt_history_invalid"
                if dispatch_kind == "auto_rework"
                else "dispatch_intent_replay_conflict"
            )
            return self._blocked_from_chain(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
                project_id=session.project_id,
                chain=chain,
                dispatch_kind=dispatch_kind,
                target_strategy=target_strategy,
                reasons=[reason],
            )

        replay_matches = [
            item
            for item in history.valid_intents
            if item[0].source_p22_summary_message_id == source_message_id
            and item[0].dispatch_kind == dispatch_kind
        ]
        if len(replay_matches) > 1:
            return self._blocked_from_chain(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
                project_id=session.project_id,
                chain=chain,
                dispatch_kind=dispatch_kind,
                target_strategy=target_strategy,
                reasons=["dispatch_intent_replay_conflict"],
            )
        decision_matches = self._p25_decision_intent_matches(
            history=history,
            chain=chain,
        )
        if len(decision_matches) > 1 or (
            decision_matches and decision_matches != replay_matches
        ):
            return self._blocked_from_chain(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
                project_id=session.project_id,
                chain=chain,
                dispatch_kind=dispatch_kind,
                target_strategy=target_strategy,
                reasons=["dispatch_intent_replay_conflict"],
            )

        attempt_index, attempt_invalid = self._rework_attempt_index(
            history=history,
            replay_matches=replay_matches,
            dispatch_kind=dispatch_kind,
        )
        if attempt_invalid:
            return self._blocked_from_chain(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
                project_id=session.project_id,
                chain=chain,
                dispatch_kind=dispatch_kind,
                target_strategy=target_strategy,
                reasons=["rework_attempt_history_invalid"],
            )
        if self._p25_attempt_history_invalid(
            chain=chain,
            attempt_index=attempt_index,
        ):
            return self._blocked_from_chain(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
                project_id=session.project_id,
                chain=chain,
                dispatch_kind=dispatch_kind,
                target_strategy=target_strategy,
                attempt_index=attempt_index,
                reasons=["rework_attempt_history_invalid"],
            )
        if (
            dispatch_kind == "auto_rework"
            and attempt_index >= PROTECTED_TRANSITION_REWORK_ATTEMPT_LIMIT
        ):
            return self._blocked_from_chain(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
                project_id=session.project_id,
                chain=chain,
                dispatch_kind=dispatch_kind,
                target_strategy=target_strategy,
                attempt_index=attempt_index,
                reasons=["rework_attempt_limit_exhausted"],
            )

        candidate = self._prepared_result(
            dispatch_intent_id=(
                replay_matches[0][0].dispatch_intent_id
                if replay_matches
                else uuid4()
            ),
            session_id=session_id,
            project_id=session.project_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            chain=chain,
            dispatch_kind=dispatch_kind,
            target_strategy=target_strategy,
            attempt_index=attempt_index,
        )
        if replay_matches:
            existing, existing_message = replay_matches[0]
            if (
                existing.dispatch_intent_fingerprint
                != candidate.dispatch_intent_fingerprint
            ):
                return self._blocked_from_chain(
                    session_id=session_id,
                    source_task_id=source_task_id,
                    source_message_id=source_message_id,
                    project_id=session.project_id,
                    chain=chain,
                    dispatch_kind=dispatch_kind,
                    target_strategy=target_strategy,
                    attempt_index=attempt_index,
                    reasons=["dispatch_intent_replay_conflict"],
                )
            replayed = (
                ProjectDirectorProtectedTransitionDispatchIntentResult.model_validate(
                    {
                        **existing.model_dump(),
                        "replay_check_completed": True,
                        "resumed_from_existing_intent": True,
                    }
                )
            )
            return PreparedProjectDirectorProtectedTransitionDispatchIntent(
                result=replayed,
                message=existing_message,
            )

        action = candidate.model_dump(mode="json")
        for field_name in (
            "source_p25_convergence_decision_message_id",
            "source_p25_convergence_decision_fingerprint",
            "source_p25_convergence_decision_replay_key",
            "source_p25_candidate_diff_message_id",
            "source_p25_review_outcome_message_id",
        ):
            if action.get(field_name) is None:
                action.pop(field_name, None)
        action.update(
            {
                "type": P23_PROTECTED_TRANSITION_DISPATCH_INTENT_ACTION_TYPE,
                "schema_version": PROTECTED_TRANSITION_DISPATCH_INTENT_SCHEMA_VERSION,
                "session_id": str(session_id),
                "source_task_id": str(source_task_id),
            }
        )
        message = self._message_repository.create(
            ProjectDirectorMessage(
                id=candidate.dispatch_intent_id,
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "A protected-transition dispatch intent was prepared from exact, "
                    "persisted P22 evidence. No task status was changed, no task or run "
                    "was created, no worker or runtime was started, and no Git write was "
                    "authorized."
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent=_INTENT,
                related_project_id=session.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL,
                suggested_actions=[action],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                forbidden_actions_detected=self._forbidden_actions(),
                created_at=candidate.created_at,
            )
        )
        return PreparedProjectDirectorProtectedTransitionDispatchIntent(
            result=candidate,
            message=message,
        )

    def _trusted_p22_summary(
        self,
        *,
        message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        project_id: UUID,
        source_message_id: UUID,
    ) -> tuple[
        ProjectDirectorPostReviewAutomationResult | None,
        dict[str, Any] | None,
        list[str],
    ]:
        if message is None:
            return None, None, ["source_p22_summary_missing"]
        if message.id != source_message_id:
            return None, None, ["source_p22_summary_invalid"]
        if message.session_id != session_id:
            return None, None, ["source_p22_summary_session_mismatch"]
        if message.related_task_id != source_task_id:
            return None, None, ["source_p22_summary_task_mismatch"]
        if message.related_project_id != project_id:
            return None, None, ["source_p22_summary_project_mismatch"]
        action = self._exact_action(
            message=message,
            role=ProjectDirectorMessageRole.ASSISTANT,
            intent="post_review_automation_orchestration",
            source_detail=P22_POST_REVIEW_AUTOMATION_SOURCE_DETAIL,
            action_type=P22_POST_REVIEW_AUTOMATION_ACTION_TYPE,
            schema_version=POST_REVIEW_AUTOMATION_SCHEMA_VERSION,
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=project_id,
        )
        if action is None:
            return None, None, ["source_p22_summary_invalid"]
        try:
            summary = ProjectDirectorPostReviewAutomationResult.model_validate(
                {
                    field_name: action.get(field_name)
                    for field_name in ProjectDirectorPostReviewAutomationResult.model_fields
                }
            )
        except ValidationError:
            return None, None, ["source_p22_summary_invalid"]
        if (
            summary.orchestration_status == "waiting_for_human"
            or summary.route == "human_escalation"
        ):
            return summary, action, ["source_p22_summary_human_route_unhandled"]
        if summary.orchestration_status != "ready_for_future_transition":
            return None, None, ["source_p22_summary_not_ready"]
        expected = {
            "AUTO_CONTINUE": ("automatic_continuation", "CONTINUE_GUARDRAIL"),
            "AUTO_REWORK": ("bounded_automatic_rework", "BOUNDED_REWORK_GUARDRAIL"),
        }.get(summary.disposition_type)
        if (
            expected is None
            or (summary.route, summary.transition_kind) != expected
            or summary.transition_authority != "AUTOMATED_DISPOSITION"
            or not summary.evidence_fresh
            or not summary.gate_allows_protected_transition_guardrail
            or summary.gate_allows_write
            or summary.waiting_for_human
            or summary.blocked_reasons
        ):
            return None, None, ["source_p22_summary_mapping_invalid"]
        return summary, action, []

    def _p25_terminal_reason_for_summary(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        project_id: UUID,
        source_p22_summary_message_id: UUID,
        summary: ProjectDirectorPostReviewAutomationResult,
    ) -> str | None:
        review_message = self._message_repository.get_by_id(
            summary.source_review_message_id
        )
        if review_message is None:
            return None
        legacy_action = self._exact_action(
            message=review_message,
            role=ProjectDirectorMessageRole.ASSISTANT,
            intent="sandbox_candidate_diff_readonly_review_execution",
            source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
            action_type=P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
            schema_version=None,
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=project_id,
        )
        if legacy_action is not None:
            return None
        if (
            review_message.intent
            == "sandbox_candidate_diff_readonly_review_execution"
            or review_message.source_detail
            == P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL
            or any(
                isinstance(action, dict)
                and action.get("type")
                == P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE
                for action in review_message.suggested_actions
            )
        ):
            return None
        if self._bounded_rework_convergence_service is None:
            return "next_attempt_decision_missing"
        revalidated = (
            self._bounded_rework_convergence_service
            .revalidate_next_attempt_decision_for_p22_summary(
                session_id=session_id,
                source_task_id=source_task_id,
                source_p22_summary_message_id=source_p22_summary_message_id,
            )
        )
        if "convergence_already_terminal" in revalidated.blocked_reasons:
            return "p25_convergence_terminal"
        if "convergence_requires_human_escalation" in revalidated.blocked_reasons:
            return "p25_human_escalation_required"
        if revalidated.blocked_reasons:
            return revalidated.blocked_reasons[0]
        return "convergence_decision_conflict"

    def _load_exact_evidence_chain(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        project_id: UUID,
        source_p22_summary_message_id: UUID,
        summary: ProjectDirectorPostReviewAutomationResult,
    ) -> tuple[_EvidenceChain | None, list[str]]:
        ids_and_missing_reasons = (
            (summary.source_review_message_id, "source_review_message_missing"),
            (
                summary.source_disposition_message_id,
                "source_disposition_message_missing",
            ),
            (
                summary.source_consumption_preflight_message_id,
                "source_preflight_message_missing",
            ),
            (
                summary.source_consumption_message_id,
                "source_consumption_message_missing",
            ),
            (summary.source_handoff_message_id, "source_handoff_message_missing"),
            (
                summary.source_freshness_message_id,
                "source_freshness_message_missing",
            ),
        )
        loaded: list[ProjectDirectorMessage] = []
        for message_id, missing_reason in ids_and_missing_reasons:
            if message_id is None:
                return None, [missing_reason]
            message = self._message_repository.get_by_id(message_id)
            if message is None:
                return None, [missing_reason]
            loaded.append(message)
        (
            review_message,
            disposition_message,
            preflight_message,
            consumption_message,
            handoff_message,
            freshness_message,
        ) = loaded

        review_action = self._exact_action(
            message=review_message,
            role=ProjectDirectorMessageRole.ASSISTANT,
            intent="sandbox_candidate_diff_readonly_review_execution",
            source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
            action_type=P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
            schema_version=None,
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=project_id,
        )
        p25_decision: ProjectDirectorBoundedReworkConvergenceDecision | None = None
        p25_decision_message: ProjectDirectorMessage | None = None
        if review_action is None:
            legacy_review_marked = bool(
                review_message.intent
                == "sandbox_candidate_diff_readonly_review_execution"
                or review_message.source_detail
                == P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL
                or any(
                    isinstance(action, dict)
                    and action.get("type")
                    == P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE
                    for action in review_message.suggested_actions
                )
            )
            if legacy_review_marked:
                return None, ["source_evidence_chain_invalid"]
            if self._bounded_rework_convergence_service is None:
                return None, ["next_attempt_decision_missing"]

            p25_gate = (
                self._bounded_rework_convergence_service
                .revalidate_next_attempt_decision_for_p22_summary(
                    session_id=session_id,
                    source_task_id=source_task_id,
                    source_p22_summary_message_id=(
                        source_p22_summary_message_id
                    ),
                )
            )
            if p25_gate.blocked_reasons:
                reason = p25_gate.blocked_reasons[0]
                reason = {
                    "convergence_already_terminal": "p25_convergence_terminal",
                    "convergence_requires_human_escalation": (
                        "p25_human_escalation_required"
                    ),
                }.get(reason, reason)
                return None, [reason]
            p25_decision = p25_gate.decision
            p25_decision_message = p25_gate.decision_message
            candidate_diff = p25_gate.candidate_diff
            outcome = p25_gate.review_outcome
            outcome_message = p25_gate.review_outcome_message
            p22_summary = p25_gate.p22_summary
            p22_message = p25_gate.p22_summary_message
            if (
                summary.disposition_type != "AUTO_REWORK"
                or summary.route != "bounded_automatic_rework"
                or p25_decision is None
                or p25_decision_message is None
                or candidate_diff is None
                or outcome is None
                or outcome_message is None
                or p22_summary is None
                or p22_message is None
                or p22_message.id != source_p22_summary_message_id
                or p22_summary != summary
                or outcome_message.id != summary.source_review_message_id
                or outcome_message != review_message
                or p25_decision.source_review_outcome_message_id
                != review_message.id
                or p25_decision.source_candidate_diff_message_id
                != candidate_diff.candidate_diff_id
                or outcome.source_candidate_diff_message_id
                != candidate_diff.candidate_diff_id
                or outcome.source_candidate_diff_sha256
                != candidate_diff.new_diff_sha256
                or p25_decision.source_review_result_fingerprint
                != outcome.review_result_fingerprint
                or p25_decision.current_review_semantic_fingerprint
                != outcome.review_semantic_fingerprint
            ):
                return None, ["convergence_decision_conflict"]
            review_action = (
                review_message.suggested_actions[0]
                if len(review_message.suggested_actions) == 1
                and isinstance(review_message.suggested_actions[0], dict)
                else None
            )
        disposition_action = self._exact_action(
            message=disposition_message,
            role=ProjectDirectorMessageRole.ASSISTANT,
            intent="sandbox_candidate_diff_review_disposition",
            source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL,
            action_type=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_ACTION_TYPE,
            schema_version=REVIEW_DISPOSITION_SCHEMA_VERSION,
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=project_id,
        )
        preflight_action = self._exact_action(
            message=preflight_message,
            role=ProjectDirectorMessageRole.ASSISTANT,
            intent="sandbox_candidate_diff_review_disposition_consumption_preflight",
            source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL,
            action_type=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_ACTION_TYPE,
            schema_version=DISPOSITION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION,
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=project_id,
        )
        consumption_action = self._exact_action(
            message=consumption_message,
            role=ProjectDirectorMessageRole.ASSISTANT,
            intent="sandbox_candidate_diff_review_disposition_consumption",
            source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMED_SOURCE_DETAIL,
            action_type=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_ACTION_TYPE,
            schema_version=DISPOSITION_CONSUMPTION_SCHEMA_VERSION,
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=project_id,
        )
        handoff_action = self._exact_action(
            message=handoff_message,
            role=ProjectDirectorMessageRole.ASSISTANT,
            intent="sandbox_candidate_diff_review_disposition_handoff",
            source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_SOURCE_DETAIL,
            action_type=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_ACTION_TYPE,
            schema_version=DISPOSITION_HANDOFF_SCHEMA_VERSION,
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=project_id,
        )
        freshness_action = self._exact_action(
            message=freshness_message,
            role=ProjectDirectorMessageRole.ASSISTANT,
            intent="protected_transition_evidence_freshness",
            source_detail=P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SOURCE_DETAIL,
            action_type=P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_ACTION_TYPE,
            schema_version=PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SCHEMA_VERSION,
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=project_id,
        )
        if any(
            action is None
            for action in (
                review_action,
                disposition_action,
                preflight_action,
                consumption_action,
                handoff_action,
                freshness_action,
            )
        ):
            return None, ["source_evidence_chain_invalid"]

        try:
            disposition = self._domain_from_action(
                ProjectDirectorSandboxCandidateDiffReviewDispositionResult,
                disposition_action,
            )
            preflight = self._domain_from_action(
                ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightResult,
                preflight_action,
            )
            consumption = self._domain_from_action(
                ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult,
                consumption_action,
            )
            handoff = self._domain_from_action(
                ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult,
                handoff_action,
            )
            freshness = self._domain_from_action(
                ProjectDirectorProtectedTransitionEvidenceFreshnessResult,
                freshness_action,
            )
        except ValidationError:
            return None, ["source_evidence_chain_invalid"]

        review_revalidation = (
            ProjectDirectorSandboxCandidateDiffReviewDispositionService
            .revalidate_persisted_review_result_fingerprint(
                session_id=session_id,
                source_task_id=source_task_id,
                source_review_message_id=summary.source_review_message_id,
                source_review_message=review_message,
            )
        )
        if review_revalidation.blocked_reasons:
            return None, ["source_evidence_chain_invalid"]
        if p25_decision is not None and (
            review_revalidation.review_result_fingerprint
            != p25_decision.source_review_result_fingerprint
            or review_revalidation.source_diff_message_id
            != p25_decision.source_candidate_diff_message_id
            or review_revalidation.source_diff_sha256
            != p25_decision.current_diff_sha256
        ):
            return None, ["convergence_decision_conflict"]
        freshness_revalidation = (
            ProjectDirectorProtectedTransitionEvidenceFreshnessService
            .revalidate_persisted_protected_transition_freshness_fingerprint(
                session_id=session_id,
                source_task_id=source_task_id,
                source_freshness_message_id=summary.source_freshness_message_id,
                source_freshness_action=freshness_action,
            )
        )
        if freshness_revalidation.blocked_reasons:
            return None, ["source_freshness_binding_invalid"]

        disposition_id = self._uuid_from_action(disposition_action, "disposition_id")
        bindings_valid = all(
            (
                disposition.disposition_status == "computed",
                disposition.disposition_type == summary.disposition_type,
                disposition.source_review_message_id == summary.source_review_message_id,
                disposition.review_result_fingerprint
                == review_revalidation.review_result_fingerprint,
                disposition_action.get("source_preflight_message_id")
                == str(review_revalidation.source_preflight_message_id),
                disposition_action.get("source_diff_message_id")
                == str(review_revalidation.source_diff_message_id),
                disposition_action.get("source_diff_sha256")
                == review_revalidation.source_diff_sha256,
                disposition_action.get("review_scope_paths")
                == review_revalidation.review_scope_paths,
                preflight.preflight_status == "ready",
                preflight.source_disposition_message_id == summary.source_disposition_message_id,
                preflight.source_review_message_id == summary.source_review_message_id,
                preflight.disposition_id == disposition_id,
                preflight.disposition_type == summary.disposition_type,
                preflight.review_result_fingerprint
                == review_revalidation.review_result_fingerprint,
                preflight_action.get("source_preflight_message_id")
                == str(review_revalidation.source_preflight_message_id),
                preflight_action.get("source_diff_message_id")
                == str(review_revalidation.source_diff_message_id),
                consumption.consumption_status == "consumed",
                consumption.source_consumption_preflight_message_id
                == summary.source_consumption_preflight_message_id,
                consumption.source_disposition_message_id == summary.source_disposition_message_id,
                consumption.source_review_message_id == summary.source_review_message_id,
                consumption.source_diff_message_id == review_revalidation.source_diff_message_id,
                consumption.disposition_id == disposition_id,
                consumption.disposition_type == summary.disposition_type,
                consumption.review_result_fingerprint
                == review_revalidation.review_result_fingerprint,
                handoff.handoff_status == "prepared",
                handoff.source_consumption_message_id == summary.source_consumption_message_id,
                handoff.source_consumption_preflight_message_id
                == summary.source_consumption_preflight_message_id,
                handoff.source_disposition_message_id == summary.source_disposition_message_id,
                handoff.source_review_message_id == summary.source_review_message_id,
                handoff.source_diff_message_id == review_revalidation.source_diff_message_id,
                handoff.disposition_id == disposition_id,
                handoff.disposition_type == summary.disposition_type,
                handoff.review_result_fingerprint
                == review_revalidation.review_result_fingerprint,
                freshness.freshness_status == "ready",
                freshness.source_transition_message_id == summary.source_handoff_message_id,
                freshness.source_transition_record_id == handoff.handoff_id,
                freshness.source_handoff_message_id == summary.source_handoff_message_id,
                freshness.handoff_id == handoff.handoff_id,
                freshness.source_disposition_consumption_message_id
                == summary.source_consumption_message_id,
                freshness.disposition_consumption_id == consumption.consumption_id,
                freshness.source_disposition_message_id == summary.source_disposition_message_id,
                freshness.source_review_message_id == summary.source_review_message_id,
                freshness.source_diff_message_id == review_revalidation.source_diff_message_id,
                freshness.disposition_id == disposition_id,
                freshness.disposition_type == summary.disposition_type,
                freshness.transition_authority == summary.transition_authority,
                freshness.transition_kind == summary.transition_kind,
                freshness.review_result_fingerprint
                == review_revalidation.review_result_fingerprint,
                freshness.freshness_evidence_fingerprint
                == freshness_revalidation.freshness_evidence_fingerprint,
            )
        )
        if not bindings_valid:
            return None, ["source_evidence_chain_invalid"]
        if (
            not freshness.evidence_fresh
            or not freshness.gate_allows_protected_transition_guardrail
            or freshness.gate_allows_write
        ):
            return None, ["source_freshness_not_ready"]

        expected_handoff = {
            "AUTO_CONTINUE": "automatic_continuation",
            "AUTO_REWORK": "bounded_automatic_rework",
        }[summary.disposition_type]
        if handoff.handoff_kind != expected_handoff:
            return None, ["source_evidence_chain_invalid"]
        exact_values = (
            consumption.reviewed_diff_sha256,
            handoff.reviewed_diff_sha256,
            freshness.reviewed_diff_sha256,
            review_revalidation.source_diff_sha256,
        )
        if len(set(exact_values)) != 1:
            return None, ["source_evidence_chain_invalid"]
        exact_scopes = (
            consumption.reviewed_scope_paths,
            handoff.reviewed_scope_paths,
            freshness.reviewed_scope_paths,
            review_revalidation.review_scope_paths,
        )
        if any(value != exact_scopes[0] for value in exact_scopes[1:]):
            return None, ["source_evidence_chain_invalid"]
        if (
            consumption.workspace_path != handoff.workspace_path
            or consumption.workspace_path != freshness.workspace_path
            or not all(
                (
                    consumption.workspace_path_within_root,
                    handoff.workspace_path_within_root,
                    freshness.workspace_path_within_root,
                )
            )
        ):
            return None, ["source_evidence_chain_invalid"]

        semantic_fingerprint = (
            p25_decision.current_review_semantic_fingerprint
            if p25_decision is not None
            else self._review_semantic_fingerprint(
                review_action=review_action,
                expected_scope_paths=freshness.reviewed_scope_paths,
            )
        )
        if semantic_fingerprint is None:
            return None, ["source_evidence_chain_invalid"]
        if (
            p25_decision is not None
            and semantic_fingerprint
            != p25_decision.current_review_semantic_fingerprint
        ):
            return None, ["convergence_decision_conflict"]
        return (
            _EvidenceChain(
                summary=summary,
                review_action=review_action,
                disposition=disposition,
                preflight=preflight,
                consumption=consumption,
                handoff=handoff,
                freshness=freshness,
                review_semantic_fingerprint=semantic_fingerprint,
                p25_convergence_decision=p25_decision,
                p25_convergence_decision_message=p25_decision_message,
            ),
            [],
        )

    def _scan_intent_history(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        project_id: UUID,
    ) -> _IntentHistory:
        valid: list[
            tuple[
                ProjectDirectorProtectedTransitionDispatchIntentResult,
                ProjectDirectorMessage,
            ]
        ] = []
        invalid = False
        for message in self._iter_session_messages(session_id):
            if message.source_detail != P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL:
                continue
            raw_action = (
                message.suggested_actions[0]
                if len(message.suggested_actions) == 1
                and isinstance(message.suggested_actions[0], dict)
                else None
            )
            action_claims_current_task = bool(
                raw_action is not None
                and raw_action.get("source_task_id") == str(source_task_id)
            )
            if (
                message.related_task_id != source_task_id
                and not action_claims_current_task
            ):
                continue
            result = self._trusted_persisted_intent(
                message=message,
                session_id=session_id,
                source_task_id=source_task_id,
                project_id=project_id,
            )
            if result is None:
                invalid = True
            else:
                valid.append((result, message))
        return _IntentHistory(valid_intents=valid, invalid=invalid)

    def _trusted_persisted_intent(
        self,
        *,
        message: ProjectDirectorMessage,
        session_id: UUID,
        source_task_id: UUID,
        project_id: UUID,
    ) -> ProjectDirectorProtectedTransitionDispatchIntentResult | None:
        action = self._exact_action(
            message=message,
            role=ProjectDirectorMessageRole.ASSISTANT,
            intent=_INTENT,
            source_detail=P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL,
            action_type=P23_PROTECTED_TRANSITION_DISPATCH_INTENT_ACTION_TYPE,
            schema_version=PROTECTED_TRANSITION_DISPATCH_INTENT_SCHEMA_VERSION,
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=project_id,
        )
        if action is None:
            return None
        try:
            result = self._domain_from_action(
                ProjectDirectorProtectedTransitionDispatchIntentResult,
                action,
            )
        except ValidationError:
            return None
        if (
            result.intent_status != "prepared"
            or result.dispatch_intent_id != message.id
            or result.project_id != project_id
            or result.rework_attempt_limit
            != PROTECTED_TRANSITION_REWORK_ATTEMPT_LIMIT
            or (
                result.dispatch_kind == "auto_rework"
                and result.rework_attempt_index
                >= PROTECTED_TRANSITION_REWORK_ATTEMPT_LIMIT
            )
            or result.resumed_from_existing_intent
            or result.created_at != message.created_at
            or result.dispatch_intent_fingerprint != self._intent_fingerprint(result)
            or not set(self._forbidden_actions()).issubset(
                message.forbidden_actions_detected
            )
        ):
            return None
        return result

    @staticmethod
    def _rework_attempt_index(
        *,
        history: _IntentHistory,
        replay_matches: list[
            tuple[
                ProjectDirectorProtectedTransitionDispatchIntentResult,
                ProjectDirectorMessage,
            ]
        ],
        dispatch_kind: str,
    ) -> tuple[int, bool]:
        if dispatch_kind == "auto_continue":
            return 0, False
        indexes = [
            result.rework_attempt_index
            for result, _message in history.valid_intents
            if result.dispatch_kind == "auto_rework"
        ]
        if len(indexes) != len(set(indexes)):
            return 0, True
        if indexes and sorted(indexes) != list(range(max(indexes) + 1)):
            return 0, True
        if replay_matches:
            return replay_matches[0][0].rework_attempt_index, False
        return (max(indexes) + 1 if indexes else 0), False

    @staticmethod
    def _p25_decision_intent_matches(
        *,
        history: _IntentHistory,
        chain: _EvidenceChain,
    ) -> list[
        tuple[
            ProjectDirectorProtectedTransitionDispatchIntentResult,
            ProjectDirectorMessage,
        ]
    ]:
        decision_message = chain.p25_convergence_decision_message
        if decision_message is None:
            return []
        return [
            item
            for item in history.valid_intents
            if item[0].source_p25_convergence_decision_message_id
            == decision_message.id
        ]

    @staticmethod
    def _p25_attempt_history_invalid(
        *,
        chain: _EvidenceChain,
        attempt_index: int,
    ) -> bool:
        decision = chain.p25_convergence_decision
        if decision is None:
            return False
        return bool(
            decision.next_rework_attempt_index is None
            or decision.next_rework_attempt_index != attempt_index
            or decision.current_rework_attempt_index + 1
            != decision.next_rework_attempt_index
            or decision.next_rework_attempt_index >= decision.rework_attempt_limit
            or decision.rework_attempt_limit
            != PROTECTED_TRANSITION_REWORK_ATTEMPT_LIMIT
            or attempt_index not in {1, 2}
        )

    def _prepared_result(
        self,
        *,
        dispatch_intent_id: UUID | None,
        session_id: UUID,
        project_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        chain: _EvidenceChain,
        dispatch_kind: str,
        target_strategy: str,
        attempt_index: int,
    ) -> ProjectDirectorProtectedTransitionDispatchIntentResult:
        p25_decision = chain.p25_convergence_decision
        p25_decision_message = chain.p25_convergence_decision_message
        result = ProjectDirectorProtectedTransitionDispatchIntentResult(
            intent_status="prepared",
            dispatch_intent_id=dispatch_intent_id,
            dispatch_intent_fingerprint="0" * 64,
            session_id=session_id,
            project_id=project_id,
            source_task_id=source_task_id,
            target_task_id=source_task_id,
            source_p22_summary_message_id=source_message_id,
            source_review_message_id=chain.summary.source_review_message_id,
            source_disposition_message_id=chain.summary.source_disposition_message_id,
            source_consumption_preflight_message_id=(
                chain.summary.source_consumption_preflight_message_id
            ),
            source_consumption_message_id=chain.summary.source_consumption_message_id,
            source_handoff_message_id=chain.summary.source_handoff_message_id,
            source_freshness_message_id=chain.summary.source_freshness_message_id,
            source_p25_convergence_decision_message_id=(
                p25_decision_message.id if p25_decision_message is not None else None
            ),
            source_p25_convergence_decision_fingerprint=(
                p25_decision.decision_fingerprint
                if p25_decision is not None
                else None
            ),
            source_p25_convergence_decision_replay_key=(
                p25_decision.decision_replay_key
                if p25_decision is not None
                else None
            ),
            source_p25_candidate_diff_message_id=(
                p25_decision.source_candidate_diff_message_id
                if p25_decision is not None
                else None
            ),
            source_p25_review_outcome_message_id=(
                p25_decision.source_review_outcome_message_id
                if p25_decision is not None
                else None
            ),
            disposition_type=chain.summary.disposition_type,
            transition_kind=chain.summary.transition_kind,
            transition_authority=chain.summary.transition_authority,
            dispatch_kind=dispatch_kind,
            target_task_strategy=target_strategy,
            review_result_fingerprint=chain.freshness.review_result_fingerprint,
            review_semantic_fingerprint=chain.review_semantic_fingerprint,
            freshness_evidence_fingerprint=(
                chain.freshness.freshness_evidence_fingerprint
            ),
            source_diff_sha256=chain.freshness.reviewed_diff_sha256,
            review_scope_paths=list(chain.freshness.reviewed_scope_paths),
            workspace_path=chain.freshness.workspace_path,
            workspace_path_within_root=chain.freshness.workspace_path_within_root,
            source_freshness_validated_at=chain.freshness.validated_at,
            rework_attempt_index=attempt_index,
            rework_attempt_limit=PROTECTED_TRANSITION_REWORK_ATTEMPT_LIMIT,
            replay_check_completed=True,
        )
        return ProjectDirectorProtectedTransitionDispatchIntentResult.model_validate(
            {
                **result.model_dump(),
                "dispatch_intent_fingerprint": self._intent_fingerprint(result),
            }
        )

    @staticmethod
    def _intent_fingerprint(
        result: ProjectDirectorProtectedTransitionDispatchIntentResult,
    ) -> str:
        payload = {
            "schema_version": PROTECTED_TRANSITION_DISPATCH_INTENT_SCHEMA_VERSION,
            "session_id": str(result.session_id),
            "project_id": str(result.project_id),
            "source_task_id": str(result.source_task_id),
            "source_p22_summary_message_id": str(
                result.source_p22_summary_message_id
            ),
            "source_review_message_id": str(result.source_review_message_id),
            "source_disposition_message_id": str(result.source_disposition_message_id),
            "source_consumption_preflight_message_id": str(
                result.source_consumption_preflight_message_id
            ),
            "source_consumption_message_id": str(result.source_consumption_message_id),
            "source_handoff_message_id": str(result.source_handoff_message_id),
            "source_freshness_message_id": str(result.source_freshness_message_id),
            "disposition_type": result.disposition_type,
            "transition_kind": result.transition_kind,
            "transition_authority": result.transition_authority,
            "dispatch_kind": result.dispatch_kind,
            "target_task_id": str(result.target_task_id),
            "target_task_strategy": result.target_task_strategy,
            "review_result_fingerprint": result.review_result_fingerprint,
            "review_semantic_fingerprint": result.review_semantic_fingerprint,
            "freshness_evidence_fingerprint": result.freshness_evidence_fingerprint,
            "source_diff_sha256": result.source_diff_sha256,
            "review_scope_paths": list(result.review_scope_paths),
            "workspace_path": result.workspace_path,
            "workspace_path_within_root": result.workspace_path_within_root,
            "source_freshness_validated_at": (
                result.source_freshness_validated_at.isoformat()
                if result.source_freshness_validated_at
                else None
            ),
            "rework_attempt_index": result.rework_attempt_index,
            "rework_attempt_limit": result.rework_attempt_limit,
        }
        if result.source_p25_convergence_decision_message_id is not None:
            payload.update(
                {
                    "source_p25_convergence_decision_message_id": str(
                        result.source_p25_convergence_decision_message_id
                    ),
                    "source_p25_convergence_decision_fingerprint": (
                        result.source_p25_convergence_decision_fingerprint
                    ),
                    "source_p25_convergence_decision_replay_key": (
                        result.source_p25_convergence_decision_replay_key
                    ),
                    "source_p25_candidate_diff_message_id": str(
                        result.source_p25_candidate_diff_message_id
                    ),
                    "source_p25_review_outcome_message_id": str(
                        result.source_p25_review_outcome_message_id
                    ),
                }
            )
        return (
            ProjectDirectorProtectedTransitionDispatchIntentService
            ._canonical_fingerprint(payload)
        )

    @staticmethod
    def _review_semantic_fingerprint(
        *,
        review_action: dict[str, Any],
        expected_scope_paths: list[str],
    ) -> str | None:
        if review_action.get("review_output_schema_version") != REVIEW_OUTPUT_SCHEMA_VERSION:
            return None
        scope_paths = review_action.get("review_scope_paths")
        if scope_paths != expected_scope_paths:
            return None
        try:
            output = ProjectDirectorSandboxCandidateDiffValidatedReviewOutput.model_validate(
                {
                    "review_status": review_action.get("review_status"),
                    "verdict": review_action.get("verdict"),
                    "risk_level": review_action.get("risk_level"),
                    "summary": review_action.get("summary"),
                    "findings": review_action.get("findings"),
                    "recommended_next_step": review_action.get("recommended_next_step"),
                }
            )
        except ValidationError:
            return None
        findings = [
            {
                "severity": finding.severity,
                "title": finding.title,
                "summary": finding.summary,
                "evidence_paths": list(finding.evidence_paths),
                "recommended_action": finding.recommended_action,
            }
            for finding in output.findings
        ]
        findings.sort(
            key=lambda item: json.dumps(
                item,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
        )
        return (
            ProjectDirectorProtectedTransitionDispatchIntentService
            ._canonical_fingerprint(
                {
                    "verdict": output.verdict,
                    "risk_level": output.risk_level,
                    "summary": output.summary,
                    "findings": findings,
                    "recommended_next_step": output.recommended_next_step,
                    "review_scope_paths": list(expected_scope_paths),
                }
            )
        )

    @staticmethod
    def _exact_action(
        *,
        message: ProjectDirectorMessage,
        role: ProjectDirectorMessageRole,
        intent: str,
        source_detail: str,
        action_type: str,
        schema_version: str | None,
        session_id: UUID,
        source_task_id: UUID,
        project_id: UUID,
    ) -> dict[str, Any] | None:
        if (
            message.session_id != session_id
            or message.related_project_id != project_id
            or message.related_task_id != source_task_id
            or message.role != role
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent != intent
            or message.source_detail != source_detail
            or message.requires_confirmation is not False
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
            or len(message.suggested_actions) != 1
        ):
            return None
        action = message.suggested_actions[0]
        if (
            not isinstance(action, dict)
            or action.get("type") != action_type
            or action.get("session_id") != str(session_id)
            or action.get("source_task_id") != str(source_task_id)
            or (
                schema_version is not None
                and action.get("schema_version") != schema_version
            )
        ):
            return None
        return action

    @staticmethod
    def _domain_from_action(model: type[Any], action: dict[str, Any]) -> Any:
        return model.model_validate(
            {field_name: action.get(field_name) for field_name in model.model_fields}
        )

    def _iter_session_messages(
        self,
        session_id: UUID,
    ) -> list[ProjectDirectorMessage]:
        all_messages: list[ProjectDirectorMessage] = []
        before_message_id: UUID | None = None
        while True:
            messages, has_more = self._message_repository.list_by_session_id(
                session_id=session_id,
                limit=_PAGE_SIZE,
                before_message_id=before_message_id,
            )
            all_messages.extend(messages)
            if not has_more or not messages:
                return all_messages
            before_message_id = messages[0].id

    @staticmethod
    def _dispatch_mapping(disposition_type: str | None) -> tuple[str, str]:
        mapping = {
            "AUTO_CONTINUE": ("auto_continue", "source_task_continue"),
            "AUTO_REWORK": ("auto_rework", "source_task_rework"),
        }
        try:
            return mapping[disposition_type]
        except KeyError as exc:
            raise ValueError("unsupported protected transition disposition") from exc

    @staticmethod
    def _uuid_from_action(action: dict[str, Any], key: str) -> UUID | None:
        try:
            return UUID(str(action.get(key)))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _canonical_fingerprint(payload: dict[str, Any]) -> str:
        canonical_json = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @staticmethod
    def _blocked(
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        reasons: list[str],
        project_id: UUID | None = None,
        **values: Any,
    ) -> PreparedProjectDirectorProtectedTransitionDispatchIntent:
        result = ProjectDirectorProtectedTransitionDispatchIntentResult(
            intent_status="blocked",
            session_id=session_id,
            project_id=project_id,
            source_task_id=source_task_id,
            source_p22_summary_message_id=source_message_id,
            blocked_reasons=list(dict.fromkeys(reasons)),
            **values,
        )
        return PreparedProjectDirectorProtectedTransitionDispatchIntent(
            result=result,
            message=None,
        )

    def _blocked_from_summary(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        project_id: UUID,
        summary: ProjectDirectorPostReviewAutomationResult,
        reasons: list[str],
    ) -> PreparedProjectDirectorProtectedTransitionDispatchIntent:
        return self._blocked(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            project_id=project_id,
            reasons=reasons,
            source_review_message_id=summary.source_review_message_id,
            source_disposition_message_id=summary.source_disposition_message_id,
            source_consumption_preflight_message_id=(
                summary.source_consumption_preflight_message_id
            ),
            source_consumption_message_id=summary.source_consumption_message_id,
            source_handoff_message_id=summary.source_handoff_message_id,
            source_freshness_message_id=summary.source_freshness_message_id,
            disposition_type=(
                summary.disposition_type
                if summary.disposition_type in ("AUTO_CONTINUE", "AUTO_REWORK")
                else None
            ),
            transition_kind=summary.transition_kind,
            transition_authority=summary.transition_authority,
        )

    def _blocked_from_chain(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        project_id: UUID,
        chain: _EvidenceChain,
        dispatch_kind: str,
        target_strategy: str,
        reasons: list[str],
        attempt_index: int = 0,
    ) -> PreparedProjectDirectorProtectedTransitionDispatchIntent:
        return self._blocked(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            project_id=project_id,
            reasons=reasons,
            target_task_id=source_task_id,
            source_review_message_id=chain.summary.source_review_message_id,
            source_disposition_message_id=chain.summary.source_disposition_message_id,
            source_consumption_preflight_message_id=(
                chain.summary.source_consumption_preflight_message_id
            ),
            source_consumption_message_id=chain.summary.source_consumption_message_id,
            source_handoff_message_id=chain.summary.source_handoff_message_id,
            source_freshness_message_id=chain.summary.source_freshness_message_id,
            disposition_type=chain.summary.disposition_type,
            transition_kind=chain.summary.transition_kind,
            transition_authority=chain.summary.transition_authority,
            dispatch_kind=dispatch_kind,
            target_task_strategy=target_strategy,
            review_result_fingerprint=chain.freshness.review_result_fingerprint,
            review_semantic_fingerprint=chain.review_semantic_fingerprint,
            freshness_evidence_fingerprint=(
                chain.freshness.freshness_evidence_fingerprint
            ),
            source_diff_sha256=chain.freshness.reviewed_diff_sha256,
            review_scope_paths=list(chain.freshness.reviewed_scope_paths),
            workspace_path=chain.freshness.workspace_path,
            workspace_path_within_root=chain.freshness.workspace_path_within_root,
            source_freshness_validated_at=chain.freshness.validated_at,
            rework_attempt_index=attempt_index,
            rework_attempt_limit=PROTECTED_TRANSITION_REWORK_ATTEMPT_LIMIT,
            replay_check_completed=True,
        )

    @staticmethod
    def _forbidden_actions() -> list[str]:
        return [
            "no_task_status_mutation",
            "no_task_creation",
            "no_run_creation",
            "no_worker_start",
            "no_runtime_start",
            "no_continuation_start",
            "no_rework_start",
            "no_worktree_creation",
            "no_workspace_write",
            "no_main_project_file_write",
            "no_patch_apply",
            "no_product_runtime_git_write",
            "no_pr_creation",
            "no_merge",
            "no_ci_trigger",
        ]


__all__ = (
    "P23_PROTECTED_TRANSITION_DISPATCH_INTENT_ACTION_TYPE",
    "P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL",
    "PROTECTED_TRANSITION_DISPATCH_INTENT_SCHEMA_VERSION",
    "PROTECTED_TRANSITION_REWORK_ATTEMPT_LIMIT",
    "PreparedProjectDirectorProtectedTransitionDispatchIntent",
    "ProjectDirectorProtectedTransitionDispatchIntentService",
    "RevalidatedPersistedProtectedTransitionDispatchIntent",
)
