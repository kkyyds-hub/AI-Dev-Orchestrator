"""Project Director P22-B 审查后自动编排服务。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_post_review_automation import (
    ProjectDirectorPostReviewAutomationResult,
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
from app.domain.project_director_sandbox_candidate_diff_review_disposition_handoff import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult,
)
from app.domain.project_director_sandbox_candidate_diff_review_disposition_consumption_preflight import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightResult,
)
from app.domain.project_director_sandbox_candidate_diff_review_human_escalation_package import (
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_protected_transition_evidence_freshness_service import (
    P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_ACTION_TYPE,
    P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SOURCE_DETAIL,
    PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SCHEMA_VERSION,
    ProjectDirectorProtectedTransitionEvidenceFreshnessService,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_consumption_preflight_service import (
    DISPOSITION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightService,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_consumption_service import (
    DISPOSITION_CONSUMPTION_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMED_SOURCE_DETAIL,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_ACTION_TYPE,
    ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionService,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_handoff_service import (
    DISPOSITION_HANDOFF_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_service import (
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL,
    REVIEW_DISPOSITION_SCHEMA_VERSION,
    ProjectDirectorSandboxCandidateDiffReviewDispositionService,
)
from app.services.project_director_sandbox_candidate_diff_review_human_escalation_package_service import (
    HUMAN_ESCALATION_PACKAGE_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService,
)
from app.services.project_director_post_review_source_evidence_resolver import (
    ProjectDirectorPostReviewSourceEvidenceResolver,
)


P22_POST_REVIEW_AUTOMATION_SOURCE_DETAIL = (
    "p22_post_review_automation_orchestrated"
)
P22_POST_REVIEW_AUTOMATION_ACTION_TYPE = (
    "p22_post_review_automation_record"
)
POST_REVIEW_AUTOMATION_SCHEMA_VERSION = "p22-b.v1"

_SUMMARY_INTENT = "post_review_automation_orchestration"
_PAGE_SIZE = 100


@dataclass(frozen=True, slots=True)
class PreparedProjectDirectorPostReviewAutomation:
    """统一编排结果及其 append-only summary message。"""

    result: ProjectDirectorPostReviewAutomationResult
    message: ProjectDirectorMessage | None


@dataclass(frozen=True, slots=True)
class RevalidatedProjectDirectorPostReviewSummary:
    """Readonly exact-summary lookup for one persisted review identity."""

    summary_exists: bool
    result: ProjectDirectorPostReviewAutomationResult | None
    message: ProjectDirectorMessage | None
    blocked_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _StepContract:
    source_detail: str
    intent: str
    action_type: str
    schema_version: str
    model: type[Any]
    status_field: str
    success_status: str


@dataclass(frozen=True, slots=True)
class _EvidenceScan:
    result: Any | None = None
    message: ProjectDirectorMessage | None = None
    conflict: bool = False


@dataclass(frozen=True, slots=True)
class _StepOutcome:
    result: Any | None = None
    message: ProjectDirectorMessage | None = None
    blocked_reasons: list[str] | None = None
    conflict: bool = False
    resumed: bool = False


_DISPOSITION = _StepContract(
    source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL,
    intent="sandbox_candidate_diff_review_disposition",
    action_type=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_ACTION_TYPE,
    schema_version=REVIEW_DISPOSITION_SCHEMA_VERSION,
    model=ProjectDirectorSandboxCandidateDiffReviewDispositionResult,
    status_field="disposition_status",
    success_status="computed",
)
_PREFLIGHT = _StepContract(
    source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL,
    intent="sandbox_candidate_diff_review_disposition_consumption_preflight",
    action_type=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_ACTION_TYPE,
    schema_version=DISPOSITION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION,
    model=ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightResult,
    status_field="preflight_status",
    success_status="ready",
)
_CONSUMPTION = _StepContract(
    source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMED_SOURCE_DETAIL,
    intent="sandbox_candidate_diff_review_disposition_consumption",
    action_type=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_ACTION_TYPE,
    schema_version=DISPOSITION_CONSUMPTION_SCHEMA_VERSION,
    model=ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult,
    status_field="consumption_status",
    success_status="consumed",
)
_HANDOFF = _StepContract(
    source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_SOURCE_DETAIL,
    intent="sandbox_candidate_diff_review_disposition_handoff",
    action_type=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_ACTION_TYPE,
    schema_version=DISPOSITION_HANDOFF_SCHEMA_VERSION,
    model=ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult,
    status_field="handoff_status",
    success_status="prepared",
)
_HUMAN_PACKAGE = _StepContract(
    source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_SOURCE_DETAIL,
    intent="sandbox_candidate_diff_review_human_escalation_package",
    action_type=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_ACTION_TYPE,
    schema_version=HUMAN_ESCALATION_PACKAGE_SCHEMA_VERSION,
    model=ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult,
    status_field="package_status",
    success_status="prepared",
)
_FRESHNESS = _StepContract(
    source_detail=P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SOURCE_DETAIL,
    intent="protected_transition_evidence_freshness",
    action_type=P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_ACTION_TYPE,
    schema_version=PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SCHEMA_VERSION,
    model=ProjectDirectorProtectedTransitionEvidenceFreshnessResult,
    status_field="freshness_status",
    success_status="ready",
)


class ProjectDirectorPostReviewAutomationService:
    """串联 D-B、C1/C2/C3/E 或 D1，但不执行任何转换。"""

    def __init__(
        self,
        *,
        session_repository: ProjectDirectorSessionRepository,
        message_repository: ProjectDirectorMessageRepository,
        task_repository: TaskRepository,
        disposition_service: ProjectDirectorSandboxCandidateDiffReviewDispositionService,
        preflight_service: ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightService,
        consumption_service: ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionService,
        handoff_service: ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService,
        human_escalation_package_service: ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService,
        freshness_service: ProjectDirectorProtectedTransitionEvidenceFreshnessService,
    ) -> None:
        self._session_repository = session_repository
        self._message_repository = message_repository
        self._task_repository = task_repository
        self._disposition_service = disposition_service
        self._preflight_service = preflight_service
        self._consumption_service = consumption_service
        self._handoff_service = handoff_service
        self._human_escalation_package_service = human_escalation_package_service
        self._freshness_service = freshness_service

    def configure_p25_h_source_evidence_resolver(
        self,
        resolver: ProjectDirectorPostReviewSourceEvidenceResolver,
    ) -> None:
        """Bind the readonly P25-H authority bridge for H-C orchestration only."""

        self._consumption_service._source_evidence_resolver = resolver
        self._freshness_service._source_evidence_resolver = resolver

    def revalidate_existing_post_review_summary(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_review_message_id: UUID,
    ) -> RevalidatedProjectDirectorPostReviewSummary:
        """Return missing, one exact valid summary, or a fail-closed conflict."""

        caller_had_transaction = self._message_repository._session.in_transaction()
        try:
            summary = self._scan_summary(
                session_id=session_id,
                source_task_id=source_task_id,
                source_review_message_id=source_review_message_id,
            )
        finally:
            if (
                not caller_had_transaction
                and self._message_repository._session.in_transaction()
            ):
                self._message_repository._session.rollback()
        if summary.conflict:
            return RevalidatedProjectDirectorPostReviewSummary(
                summary_exists=False,
                result=None,
                message=None,
                blocked_reasons=("post_review_orchestration_replay_conflict",),
            )
        if summary.result is None or summary.message is None:
            return RevalidatedProjectDirectorPostReviewSummary(
                summary_exists=False,
                result=None,
                message=None,
                blocked_reasons=(),
            )
        return RevalidatedProjectDirectorPostReviewSummary(
            summary_exists=True,
            result=summary.result,
            message=summary.message,
            blocked_reasons=(),
        )

    def orchestrate_post_review(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_review_message_id: UUID,
    ) -> PreparedProjectDirectorPostReviewAutomation:
        """从一条已持久化 P21-C review message 编排后续证据链。"""

        with self._message_repository.sqlite_immediate_transaction():
            summary = self._scan_summary(
                session_id=session_id,
                source_task_id=source_task_id,
                source_review_message_id=source_review_message_id,
            )
        if summary.conflict:
            return self._summary_conflict(source_review_message_id)
        if summary.result is not None and summary.message is not None:
            return self._replayed_summary(summary.result, summary.message)

        with self._message_repository.sqlite_immediate_transaction():
            session_obj = self._session_repository.get_by_id(session_id)
            source_task = self._task_repository.get_by_id(source_task_id)
        if session_obj is None:
            raise ValueError("Project Director session not found")
        if source_task is None:
            raise ValueError("source task not found")
        if session_obj.project_id != source_task.project_id:
            raise ValueError("source task does not belong to the session project")

        state: dict[str, Any] = {
            "source_review_message_id": source_review_message_id,
        }
        resumed = False

        disposition = self._load_or_invoke_step(
            contract=_DISPOSITION,
            session_id=session_id,
            source_task_id=source_task_id,
            bindings={"source_review_message_id": source_review_message_id},
            invoke=lambda: self._disposition_service.compute_candidate_diff_review_disposition(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_review_message_id,
            ),
            duplicate_reason=None,
        )
        resumed = resumed or disposition.resumed
        if disposition.conflict:
            return self._persist_blocked(
                session_id=session_id,
                source_task_id=source_task_id,
                session_project_id=session_obj.project_id,
                state=state,
                reasons=["conflicting_existing_orchestration_evidence"],
                resumed=resumed,
            )
        if disposition.blocked_reasons:
            return self._persist_blocked(
                session_id=session_id,
                source_task_id=source_task_id,
                session_project_id=session_obj.project_id,
                state=state,
                reasons=disposition.blocked_reasons + ["post_review_disposition_blocked"],
                resumed=resumed,
            )
        self._bind_step(state, "source_disposition_message_id", disposition)
        state["disposition_type"] = disposition.result.disposition_type
        state["route"] = self._route_for_disposition(
            disposition.result.disposition_type
        )

        if disposition.result.disposition_type == "ESCALATE_TO_HUMAN":
            return self._orchestrate_human_path(
                session_id=session_id,
                source_task_id=source_task_id,
                session_project_id=session_obj.project_id,
                state=state,
                resumed=resumed,
            )
        return self._orchestrate_automatic_path(
            session_id=session_id,
            source_task_id=source_task_id,
            session_project_id=session_obj.project_id,
            state=state,
            resumed=resumed,
        )

    def _orchestrate_human_path(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        session_project_id: UUID | None,
        state: dict[str, Any],
        resumed: bool,
    ) -> PreparedProjectDirectorPostReviewAutomation:
        package = self._load_or_invoke_step(
            contract=_HUMAN_PACKAGE,
            session_id=session_id,
            source_task_id=source_task_id,
            bindings={
                "source_disposition_message_id": state[
                    "source_disposition_message_id"
                ],
                "source_review_message_id": state["source_review_message_id"],
            },
            invoke=lambda: self._human_escalation_package_service.prepare_human_escalation_package(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=state["source_disposition_message_id"],
            ),
            duplicate_reason="human_escalation_package_already_created",
        )
        resumed = resumed or package.resumed
        if package.conflict:
            return self._persist_blocked(
                session_id=session_id,
                source_task_id=source_task_id,
                session_project_id=session_project_id,
                state=state,
                reasons=["conflicting_existing_orchestration_evidence"],
                resumed=resumed,
            )
        if package.blocked_reasons:
            return self._persist_blocked(
                session_id=session_id,
                source_task_id=source_task_id,
                session_project_id=session_project_id,
                state=state,
                reasons=package.blocked_reasons + ["human_escalation_package_blocked"],
                resumed=resumed,
            )
        self._bind_step(
            state,
            "source_human_escalation_package_message_id",
            package,
        )
        result = self._result_from_state(
            state=state,
            orchestration_status="waiting_for_human",
            current_step="human_escalation_package_prepared",
            resumed=resumed,
            waiting_for_human=True,
            human_escalation_package_created=True,
        )
        return self._persist_summary(
            session_id=session_id,
            source_task_id=source_task_id,
            session_project_id=session_project_id,
            result=result,
        )

    def _orchestrate_automatic_path(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        session_project_id: UUID | None,
        state: dict[str, Any],
        resumed: bool,
    ) -> PreparedProjectDirectorPostReviewAutomation:
        steps = (
            (
                _PREFLIGHT,
                "source_disposition_message_id",
                "source_consumption_preflight_message_id",
                self._preflight_service.prepare_candidate_diff_review_disposition_consumption,
                "disposition_already_preflighted",
                "automatic_preflight_blocked",
            ),
            (
                _CONSUMPTION,
                "source_consumption_preflight_message_id",
                "source_consumption_message_id",
                self._consumption_service.prepare_candidate_diff_review_disposition_consumption,
                "disposition_already_consumed",
                "automatic_consumption_blocked",
            ),
            (
                _HANDOFF,
                "source_consumption_message_id",
                "source_handoff_message_id",
                self._handoff_service.prepare_candidate_diff_review_disposition_handoff,
                "handoff_already_prepared",
                "automatic_handoff_blocked",
            ),
            (
                _FRESHNESS,
                "source_handoff_message_id",
                "source_freshness_message_id",
                self._freshness_service.prepare_protected_transition_evidence_freshness_gate,
                "protected_transition_freshness_already_validated",
                "protected_transition_freshness_blocked",
            ),
        )
        last_result: Any | None = None
        for (
            contract,
            source_state_key,
            target_state_key,
            method,
            duplicate_reason,
            coordinator_reason,
        ) in steps:
            source_message_id = state[source_state_key]
            bindings = self._automatic_step_bindings(
                contract=contract,
                state=state,
                source_message_id=source_message_id,
            )
            outcome = self._load_or_invoke_step(
                contract=contract,
                session_id=session_id,
                source_task_id=source_task_id,
                bindings=bindings,
                invoke=lambda method=method, source_message_id=source_message_id: method(
                    session_id=session_id,
                    source_task_id=source_task_id,
                    source_message_id=source_message_id,
                ),
                duplicate_reason=duplicate_reason,
            )
            resumed = resumed or outcome.resumed
            if outcome.conflict:
                return self._persist_blocked(
                    session_id=session_id,
                    source_task_id=source_task_id,
                    session_project_id=session_project_id,
                    state=state,
                    reasons=["conflicting_existing_orchestration_evidence"],
                    resumed=resumed,
                )
            if outcome.blocked_reasons:
                return self._persist_blocked(
                    session_id=session_id,
                    source_task_id=source_task_id,
                    session_project_id=session_project_id,
                    state=state,
                    reasons=outcome.blocked_reasons + [coordinator_reason],
                    resumed=resumed,
                )
            self._bind_step(state, target_state_key, outcome)
            last_result = outcome.result
            if contract is _HANDOFF:
                state["handoff_kind"] = outcome.result.handoff_kind
            elif contract is _FRESHNESS:
                state["transition_kind"] = outcome.result.transition_kind
                state["transition_authority"] = outcome.result.transition_authority

        result = self._result_from_state(
            state=state,
            orchestration_status="ready_for_future_transition",
            current_step="freshness_ready",
            resumed=resumed,
            evidence_fresh=last_result.evidence_fresh,
            gate_allows_protected_transition_guardrail=(
                last_result.gate_allows_protected_transition_guardrail
            ),
        )
        return self._persist_summary(
            session_id=session_id,
            source_task_id=source_task_id,
            session_project_id=session_project_id,
            result=result,
        )

    def _load_or_invoke_step(
        self,
        *,
        contract: _StepContract,
        session_id: UUID,
        source_task_id: UUID,
        bindings: dict[str, UUID],
        invoke: Callable[[], Any],
        duplicate_reason: str | None,
    ) -> _StepOutcome:
        with self._message_repository.sqlite_immediate_transaction():
            scan = self._scan_step(
                contract=contract,
                session_id=session_id,
                source_task_id=source_task_id,
                bindings=bindings,
            )
        if scan.conflict:
            return _StepOutcome(conflict=True)
        if scan.result is not None:
            return _StepOutcome(
                result=scan.result,
                message=scan.message,
                resumed=True,
            )

        prepared = invoke()
        result = prepared.result
        if getattr(result, contract.status_field) != contract.success_status:
            blocked_reasons = list(result.blocked_reasons)
            if duplicate_reason is not None and blocked_reasons == [duplicate_reason]:
                with self._message_repository.sqlite_immediate_transaction():
                    adopted = self._scan_step(
                        contract=contract,
                        session_id=session_id,
                        source_task_id=source_task_id,
                        bindings=bindings,
                    )
                if adopted.result is not None and not adopted.conflict:
                    return _StepOutcome(
                        result=adopted.result,
                        message=adopted.message,
                        resumed=True,
                    )
                return _StepOutcome(conflict=True)
            return _StepOutcome(blocked_reasons=blocked_reasons)
        if prepared.message is None:
            raise ValueError("successful orchestration step requires a message")
        return _StepOutcome(result=result, message=prepared.message)

    def _scan_step(
        self,
        *,
        contract: _StepContract,
        session_id: UUID,
        source_task_id: UUID,
        bindings: dict[str, UUID],
    ) -> _EvidenceScan:
        matches: list[tuple[Any, ProjectDirectorMessage]] = []
        conflict = False
        for message in self._iter_session_messages(session_id):
            if message.source_detail != contract.source_detail:
                continue
            action = self._single_action(message)
            if action is None:
                if message.related_task_id == source_task_id:
                    conflict = True
                continue
            if not self._action_binds(action, bindings):
                continue
            result = self._trusted_step_result(
                message=message,
                action=action,
                contract=contract,
                session_id=session_id,
                source_task_id=source_task_id,
            )
            if result is None:
                conflict = True
            else:
                matches.append((result, message))
        if conflict or len(matches) > 1:
            return _EvidenceScan(conflict=True)
        if not matches:
            return _EvidenceScan()
        result, message = matches[0]
        return _EvidenceScan(result=result, message=message)

    def _trusted_step_result(
        self,
        *,
        message: ProjectDirectorMessage,
        action: dict[str, Any],
        contract: _StepContract,
        session_id: UUID,
        source_task_id: UUID,
    ) -> Any | None:
        if (
            message.session_id != session_id
            or message.role != ProjectDirectorMessageRole.ASSISTANT
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent != contract.intent
            or message.related_task_id != source_task_id
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
            or action.get("type") != contract.action_type
            or action.get("schema_version") != contract.schema_version
            or action.get("session_id") != str(session_id)
            or action.get("source_task_id") != str(source_task_id)
        ):
            return None
        try:
            result = contract.model.model_validate(
                {
                    field_name: action.get(field_name)
                    for field_name in contract.model.model_fields
                }
            )
        except ValidationError:
            return None
        if getattr(result, contract.status_field) != contract.success_status:
            return None
        if contract is _DISPOSITION and not self._replayed_disposition_is_current(
            action=action,
            result=result,
            session_id=session_id,
            source_task_id=source_task_id,
        ):
            return None
        return result

    def _replayed_disposition_is_current(
        self,
        *,
        action: dict[str, Any],
        result: ProjectDirectorSandboxCandidateDiffReviewDispositionResult,
        session_id: UUID,
        source_task_id: UUID,
    ) -> bool:
        """复用 D-B revalidation，确认已有 disposition 仍绑定当前 review。"""

        source_review_message = self._message_repository.get_by_id(
            result.source_review_message_id
        )
        revalidation = ProjectDirectorSandboxCandidateDiffReviewDispositionService.revalidate_persisted_review_result_fingerprint(
            session_id=session_id,
            source_task_id=source_task_id,
            source_review_message_id=result.source_review_message_id,
            source_review_message=source_review_message,
        )
        return (
            not revalidation.blocked_reasons
            and result.review_result_fingerprint
            == revalidation.review_result_fingerprint
            and action.get("source_preflight_message_id")
            == str(revalidation.source_preflight_message_id)
            and action.get("source_diff_message_id")
            == str(revalidation.source_diff_message_id)
            and action.get("requested_reviewer_executor")
            == revalidation.requested_reviewer_executor
            and action.get("source_diff_sha256") == revalidation.source_diff_sha256
            and action.get("review_prompt_sha256")
            == revalidation.review_prompt_sha256
            and action.get("review_scope_paths")
            == (revalidation.review_scope_paths or [])
            and action.get("review_output_schema_version")
            == revalidation.review_output_schema_version
            and action.get("source_review_verdict") == revalidation.verdict
            and action.get("source_review_risk_level") == revalidation.risk_level
        )

    def _scan_summary(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_review_message_id: UUID,
    ) -> _EvidenceScan:
        matches: list[
            tuple[ProjectDirectorPostReviewAutomationResult, ProjectDirectorMessage]
        ] = []
        conflict = False
        for message in self._iter_session_messages(session_id):
            if message.source_detail != P22_POST_REVIEW_AUTOMATION_SOURCE_DETAIL:
                continue
            action = self._single_action(message)
            if action is None:
                if message.related_task_id == source_task_id:
                    conflict = True
                continue
            action_review_message_id = action.get("source_review_message_id")
            if action_review_message_id is None:
                if message.related_task_id == source_task_id:
                    conflict = True
                continue
            if action_review_message_id != str(source_review_message_id):
                continue
            result = self._trusted_summary_result(
                message=message,
                action=action,
                session_id=session_id,
                source_task_id=source_task_id,
                source_review_message_id=source_review_message_id,
            )
            if result is None:
                conflict = True
            else:
                matches.append((result, message))
        if conflict or len(matches) > 1:
            return _EvidenceScan(conflict=True)
        if not matches:
            return _EvidenceScan()
        result, message = matches[0]
        return _EvidenceScan(result=result, message=message)

    def _trusted_summary_result(
        self,
        *,
        message: ProjectDirectorMessage,
        action: dict[str, Any],
        session_id: UUID,
        source_task_id: UUID,
        source_review_message_id: UUID,
    ) -> ProjectDirectorPostReviewAutomationResult | None:
        if (
            message.session_id != session_id
            or message.role != ProjectDirectorMessageRole.ASSISTANT
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent != _SUMMARY_INTENT
            or message.related_task_id != source_task_id
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
            or action.get("type") != P22_POST_REVIEW_AUTOMATION_ACTION_TYPE
            or action.get("schema_version") != POST_REVIEW_AUTOMATION_SCHEMA_VERSION
            or action.get("session_id") != str(session_id)
            or action.get("source_task_id") != str(source_task_id)
        ):
            return None
        try:
            result = ProjectDirectorPostReviewAutomationResult.model_validate(
                {
                    field_name: action.get(field_name)
                    for field_name in ProjectDirectorPostReviewAutomationResult.model_fields
                }
            )
        except ValidationError:
            return None
        if result.source_review_message_id != source_review_message_id:
            return None
        if not self._summary_evidence_chain_valid(
            result=result,
            session_id=session_id,
            source_task_id=source_task_id,
        ):
            return None
        return result

    def _summary_evidence_chain_valid(
        self,
        *,
        result: ProjectDirectorPostReviewAutomationResult,
        session_id: UUID,
        source_task_id: UUID,
    ) -> bool:
        checks = (
            (
                result.source_disposition_message_id,
                _DISPOSITION,
                {
                    "source_review_message_id": result.source_review_message_id,
                },
            ),
            (
                result.source_consumption_preflight_message_id,
                _PREFLIGHT,
                {
                    "source_disposition_message_id": result.source_disposition_message_id,
                    "source_review_message_id": result.source_review_message_id,
                },
            ),
            (
                result.source_consumption_message_id,
                _CONSUMPTION,
                {
                    "source_consumption_preflight_message_id": result.source_consumption_preflight_message_id,
                    "source_disposition_message_id": result.source_disposition_message_id,
                    "source_review_message_id": result.source_review_message_id,
                },
            ),
            (
                result.source_handoff_message_id,
                _HANDOFF,
                {
                    "source_consumption_message_id": result.source_consumption_message_id,
                    "source_consumption_preflight_message_id": result.source_consumption_preflight_message_id,
                    "source_disposition_message_id": result.source_disposition_message_id,
                    "source_review_message_id": result.source_review_message_id,
                },
            ),
            (
                result.source_freshness_message_id,
                _FRESHNESS,
                {
                    "source_transition_message_id": result.source_handoff_message_id,
                    "source_handoff_message_id": result.source_handoff_message_id,
                    "source_disposition_message_id": result.source_disposition_message_id,
                    "source_review_message_id": result.source_review_message_id,
                },
            ),
            (
                result.source_human_escalation_package_message_id,
                _HUMAN_PACKAGE,
                {
                    "source_disposition_message_id": result.source_disposition_message_id,
                    "source_review_message_id": result.source_review_message_id,
                },
            ),
        )
        for message_id, contract, expected_bindings in checks:
            if message_id is None:
                continue
            if any(value is None for value in expected_bindings.values()):
                return False
            message = self._message_repository.get_by_id(message_id)
            if message is None or message.source_detail != contract.source_detail:
                return False
            action = self._single_action(message)
            if action is None or not self._action_binds(
                action,
                expected_bindings,
            ):
                return False
            if self._trusted_step_result(
                message=message,
                action=action,
                contract=contract,
                session_id=session_id,
                source_task_id=source_task_id,
            ) is None:
                return False
        return True

    def _persist_blocked(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        session_project_id: UUID | None,
        state: dict[str, Any],
        reasons: list[str],
        resumed: bool,
    ) -> PreparedProjectDirectorPostReviewAutomation:
        result = self._result_from_state(
            state=state,
            orchestration_status="blocked",
            current_step="blocked",
            resumed=resumed,
            blocked_reasons=self._dedupe(reasons),
        )
        return self._persist_summary(
            session_id=session_id,
            source_task_id=source_task_id,
            session_project_id=session_project_id,
            result=result,
        )

    def _persist_summary(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        session_project_id: UUID | None,
        result: ProjectDirectorPostReviewAutomationResult,
    ) -> PreparedProjectDirectorPostReviewAutomation:
        with self._message_repository.sqlite_immediate_transaction():
            existing = self._scan_summary(
                session_id=session_id,
                source_task_id=source_task_id,
                source_review_message_id=result.source_review_message_id,
            )
            if existing.conflict:
                return self._summary_conflict(result.source_review_message_id)
            if existing.result is not None and existing.message is not None:
                if not self._summary_matches_candidate(existing.result, result):
                    return self._summary_conflict(result.source_review_message_id)
                return self._replayed_summary(existing.result, existing.message)

            if not self._summary_evidence_chain_valid(
                result=result,
                session_id=session_id,
                source_task_id=source_task_id,
            ):
                return self._summary_conflict(result.source_review_message_id)

            action = result.model_dump(mode="json")
            action.update(
                {
                    "type": P22_POST_REVIEW_AUTOMATION_ACTION_TYPE,
                    "schema_version": POST_REVIEW_AUTOMATION_SCHEMA_VERSION,
                    "session_id": str(session_id),
                    "source_task_id": str(source_task_id),
                }
            )
            message = self._message_repository.create(
                ProjectDirectorMessage(
                    session_id=session_id,
                    role=ProjectDirectorMessageRole.ASSISTANT,
                    content=(
                        "协调器只完成审查后证据链编排。没有启动继续或返工，"
                        "没有创建 Task、Run 或 Worker，没有写入文件，也没有执行"
                        "产品运行时 Git 操作。AI Project Director 总闭环仍为 Partial。"
                    ),
                    sequence_no=self._message_repository.get_next_sequence_no(
                        session_id=session_id
                    ),
                    intent=_SUMMARY_INTENT,
                    related_project_id=session_project_id,
                    related_task_id=source_task_id,
                    source=ProjectDirectorMessageSource.SYSTEM,
                    source_detail=P22_POST_REVIEW_AUTOMATION_SOURCE_DETAIL,
                    suggested_actions=[action],
                    requires_confirmation=False,
                    risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                    forbidden_actions_detected=self._forbidden_actions(),
                    created_at=result.created_at,
                )
            )
            return PreparedProjectDirectorPostReviewAutomation(
                result=result,
                message=message,
            )

    @staticmethod
    def _result_from_state(
        *,
        state: dict[str, Any],
        orchestration_status: str,
        current_step: str,
        resumed: bool,
        **updates: Any,
    ) -> ProjectDirectorPostReviewAutomationResult:
        values = {
            "orchestration_status": orchestration_status,
            "orchestration_id": uuid4(),
            "route": state.get("route", "none"),
            "current_step": current_step,
            "source_review_message_id": state["source_review_message_id"],
            "source_disposition_message_id": state.get(
                "source_disposition_message_id"
            ),
            "source_consumption_preflight_message_id": state.get(
                "source_consumption_preflight_message_id"
            ),
            "source_consumption_message_id": state.get(
                "source_consumption_message_id"
            ),
            "source_handoff_message_id": state.get("source_handoff_message_id"),
            "source_freshness_message_id": state.get(
                "source_freshness_message_id"
            ),
            "source_human_escalation_package_message_id": state.get(
                "source_human_escalation_package_message_id"
            ),
            "disposition_type": state.get("disposition_type"),
            "handoff_kind": state.get("handoff_kind"),
            "transition_kind": state.get("transition_kind"),
            "transition_authority": state.get("transition_authority"),
            "replay_check_completed": True,
            "resumed_from_existing_evidence": resumed,
            "created_at": datetime.now(timezone.utc),
        }
        values.update(updates)
        return ProjectDirectorPostReviewAutomationResult(**values)

    @staticmethod
    def _bind_step(
        state: dict[str, Any],
        key: str,
        outcome: _StepOutcome,
    ) -> None:
        if outcome.message is None or outcome.result is None:
            raise ValueError("successful orchestration step requires trusted evidence")
        state[key] = outcome.message.id

    @staticmethod
    def _automatic_step_bindings(
        *,
        contract: _StepContract,
        state: dict[str, Any],
        source_message_id: UUID,
    ) -> dict[str, UUID]:
        common = {
            "source_review_message_id": state["source_review_message_id"],
            "source_disposition_message_id": state[
                "source_disposition_message_id"
            ],
        }
        if contract is _PREFLIGHT:
            return common
        if contract is _CONSUMPTION:
            return {
                **common,
                "source_consumption_preflight_message_id": source_message_id,
            }
        if contract is _HANDOFF:
            return {
                **common,
                "source_consumption_preflight_message_id": state[
                    "source_consumption_preflight_message_id"
                ],
                "source_consumption_message_id": source_message_id,
            }
        if contract is _FRESHNESS:
            return {
                **common,
                "source_transition_message_id": source_message_id,
                "source_handoff_message_id": source_message_id,
            }
        raise ValueError("unsupported automatic orchestration step")

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
    def _single_action(message: ProjectDirectorMessage) -> dict[str, Any] | None:
        if len(message.suggested_actions) != 1:
            return None
        action = message.suggested_actions[0]
        return action if isinstance(action, dict) else None

    @staticmethod
    def _action_binds(action: dict[str, Any], bindings: dict[str, UUID]) -> bool:
        return all(action.get(key) == str(value) for key, value in bindings.items())

    @staticmethod
    def _route_for_disposition(disposition_type: str) -> str:
        routes = {
            "AUTO_CONTINUE": "automatic_continuation",
            "AUTO_REWORK": "bounded_automatic_rework",
            "ESCALATE_TO_HUMAN": "human_escalation",
        }
        try:
            return routes[disposition_type]
        except KeyError as exc:
            raise ValueError("unsupported review disposition type") from exc

    @staticmethod
    def _replayed_summary(
        result: ProjectDirectorPostReviewAutomationResult,
        message: ProjectDirectorMessage,
    ) -> PreparedProjectDirectorPostReviewAutomation:
        replayed = ProjectDirectorPostReviewAutomationResult.model_validate(
            {
                **result.model_dump(),
                "replay_check_completed": True,
                "resumed_from_existing_evidence": True,
            }
        )
        return PreparedProjectDirectorPostReviewAutomation(
            result=replayed,
            message=message,
        )

    @staticmethod
    def _summary_matches_candidate(
        existing: ProjectDirectorPostReviewAutomationResult,
        candidate: ProjectDirectorPostReviewAutomationResult,
    ) -> bool:
        """比较影响路由和证据链的稳定字段，忽略本次调用元数据。"""

        ignored = {
            "orchestration_id",
            "created_at",
            "replay_check_completed",
            "resumed_from_existing_evidence",
        }
        existing_values = existing.model_dump()
        candidate_values = candidate.model_dump()
        return all(
            existing_values[field_name] == candidate_values[field_name]
            for field_name in existing.model_fields
            if field_name not in ignored
        )

    @staticmethod
    def _summary_conflict(
        source_review_message_id: UUID,
    ) -> PreparedProjectDirectorPostReviewAutomation:
        return PreparedProjectDirectorPostReviewAutomation(
            result=ProjectDirectorPostReviewAutomationResult(
                orchestration_status="blocked",
                orchestration_id=uuid4(),
                route="none",
                current_step="blocked",
                source_review_message_id=source_review_message_id,
                replay_check_completed=True,
                blocked_reasons=["post_review_orchestration_replay_conflict"],
            ),
            message=None,
        )

    @staticmethod
    def _forbidden_actions() -> list[str]:
        return [
            "no_continuation_start",
            "no_rework_start",
            "no_human_decision_recording",
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
        ]

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value for value in values if value))


__all__ = (
    "POST_REVIEW_AUTOMATION_SCHEMA_VERSION",
    "P22_POST_REVIEW_AUTOMATION_ACTION_TYPE",
    "P22_POST_REVIEW_AUTOMATION_SOURCE_DETAIL",
    "PreparedProjectDirectorPostReviewAutomation",
    "ProjectDirectorPostReviewAutomationService",
    "RevalidatedProjectDirectorPostReviewSummary",
)
