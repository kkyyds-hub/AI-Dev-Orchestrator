"""Project Director P23-C 受保护转换调度消费前置检查服务。"""

from __future__ import annotations

import hashlib
import json
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
from app.domain.project_director_protected_transition_dispatch_consumption_preflight import (
    ProjectDirectorProtectedTransitionDispatchConsumptionPreflightResult,
)
from app.domain.project_director_protected_transition_dispatch_intent import (
    ProjectDirectorProtectedTransitionDispatchIntentResult,
)
from app.domain.task import Task, TaskHumanStatus, TaskStatus
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.budget_guard_service import BudgetGuardService
from app.services.project_director_protected_transition_dispatch_intent_service import (
    P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL,
    PROTECTED_TRANSITION_REWORK_ATTEMPT_LIMIT,
    ProjectDirectorProtectedTransitionDispatchIntentService,
)
from app.services.project_director_protected_transition_evidence_freshness_service import (
    ProjectDirectorProtectedTransitionEvidenceFreshnessService,
    RevalidatedCurrentProtectedTransitionEvidenceFreshness,
)
from app.services.task_readiness_service import TaskReadinessResult, TaskReadinessService
from app.services.task_state_machine_service import TaskStateMachineService


P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL = (
    "p23_protected_transition_dispatch_consumption_preflight_ready"
)
P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_PREFLIGHT_ACTION_TYPE = (
    "p23_protected_transition_dispatch_consumption_preflight_record"
)
PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION = "p23-c.v1"

_INTENT = "protected_transition_dispatch_consumption_preflight"
_PAGE_SIZE = 100


@dataclass(frozen=True, slots=True)
class PreparedProjectDirectorProtectedTransitionDispatchConsumptionPreflight:
    """P23-C 前置检查结果及其 append-only message。"""

    result: ProjectDirectorProtectedTransitionDispatchConsumptionPreflightResult
    message: ProjectDirectorMessage | None


@dataclass(frozen=True, slots=True)
class _PreflightHistory:
    valid_preflights: list[
        tuple[
            ProjectDirectorProtectedTransitionDispatchConsumptionPreflightResult,
            ProjectDirectorMessage,
        ]
    ]
    invalid: bool = False


class ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService:
    """重验 P23-B 意图、当前 freshness、任务与预算前置条件。"""

    def __init__(
        self,
        *,
        session_repository: ProjectDirectorSessionRepository,
        message_repository: ProjectDirectorMessageRepository,
        task_repository: TaskRepository,
        dispatch_intent_service: ProjectDirectorProtectedTransitionDispatchIntentService,
        freshness_service: ProjectDirectorProtectedTransitionEvidenceFreshnessService,
        task_readiness_service: TaskReadinessService,
        task_state_machine_service: TaskStateMachineService,
        budget_guard_service: BudgetGuardService,
    ) -> None:
        self._session_repository = session_repository
        self._message_repository = message_repository
        self._task_repository = task_repository
        self._dispatch_intent_service = dispatch_intent_service
        self._freshness_service = freshness_service
        self._task_readiness_service = task_readiness_service
        self._task_state_machine_service = task_state_machine_service
        self._budget_guard_service = budget_guard_service

    def prepare_protected_transition_dispatch_consumption_preflight(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
    ) -> PreparedProjectDirectorProtectedTransitionDispatchConsumptionPreflight:
        """在一个立即事务内完成全部只读重验并追加 ready 证据。"""

        with self._message_repository.sqlite_immediate_transaction():
            return self._prepare_protected_transition_dispatch_consumption_preflight(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
            )

    def _prepare_protected_transition_dispatch_consumption_preflight(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
    ) -> PreparedProjectDirectorProtectedTransitionDispatchConsumptionPreflight:
        validated_at = datetime.now(timezone.utc)
        blocked_reasons: list[str] = []
        session_obj = self._session_repository.get_by_id(session_id)
        source_task = self._task_repository.get_by_id(source_task_id)
        project_id = session_obj.project_id if session_obj is not None else None
        if source_task is None:
            blocked_reasons.append("source_task_missing")
        if (
            session_obj is None
            or project_id is None
            or source_task is not None
            and source_task.project_id != project_id
        ):
            blocked_reasons.append("target_task_scope_mismatch")

        intent_revalidation = (
            self._dispatch_intent_service
            .revalidate_persisted_protected_transition_dispatch_intent(
                session_id=session_id,
                source_task_id=source_task_id,
                source_intent_message_id=source_message_id,
            )
        )
        blocked_reasons.extend(intent_revalidation.blocked_reasons)
        intent = intent_revalidation.result
        if intent is not None:
            if intent.intent_status != "prepared":
                blocked_reasons.append("source_dispatch_intent_not_prepared")
            if intent.project_id != project_id:
                blocked_reasons.append("source_dispatch_intent_project_mismatch")
            if intent.target_task_id != source_task_id:
                blocked_reasons.append("target_task_scope_mismatch")

        current_freshness: RevalidatedCurrentProtectedTransitionEvidenceFreshness | None = None
        if intent is not None and intent.source_freshness_message_id is not None:
            current_freshness = self._freshness_service.revalidate_current_automatic_transition_evidence_from_persisted_freshness(
                session_id=session_id,
                source_task_id=source_task_id,
                source_freshness_message_id=intent.source_freshness_message_id,
            )
            if current_freshness.freshness_status != "ready":
                blocked_reasons.append("current_freshness_revalidation_failed")
                if any(
                    reason
                    in {
                        "current_workspace_invalid",
                        "current_diff_mismatch",
                        "current_scope_mismatch",
                    }
                    for reason in current_freshness.blocked_reasons
                ):
                    blocked_reasons.append("current_freshness_stale")
                blocked_reasons.extend(current_freshness.blocked_reasons)
        elif intent is not None:
            blocked_reasons.append("source_freshness_missing")

        readiness: TaskReadinessResult | None = None
        task_preparation_strategy: str | None = None
        planned_task_status = None
        if source_task is not None:
            readiness = self._task_readiness_service.evaluate_task(task=source_task)
            if source_task.human_status in {
                TaskHumanStatus.REQUESTED,
                TaskHumanStatus.IN_PROGRESS,
            } or source_task.paused_reason:
                blocked_reasons.append("human_escalation_required")
            if intent is not None and intent.dispatch_kind == "auto_continue":
                if (
                    source_task.status != TaskStatus.PENDING
                    or not readiness.ready_for_execution
                ):
                    blocked_reasons.append("source_task_state_invalid")
                    if not readiness.ready_for_execution:
                        blocked_reasons.append("target_task_not_ready")
                else:
                    task_preparation_strategy = "claim_pending"
                    planned_task_status = TaskStatus.PENDING.value
            elif intent is not None and intent.dispatch_kind == "auto_rework":
                if source_task.status == TaskStatus.PENDING:
                    if readiness.ready_for_execution:
                        task_preparation_strategy = "claim_pending"
                        planned_task_status = TaskStatus.PENDING.value
                    else:
                        blocked_reasons.append("target_task_not_ready")
                elif source_task.status in {TaskStatus.FAILED, TaskStatus.BLOCKED}:
                    transition = self._task_state_machine_service.build_retry_transition(
                        task=source_task
                    )
                    if transition.status != TaskStatus.PENDING:
                        blocked_reasons.append("source_task_state_invalid")
                    else:
                        task_preparation_strategy = "retry_to_pending_then_claim"
                        planned_task_status = transition.status.value
                else:
                    blocked_reasons.append("source_task_state_invalid")

        budget_decision = None
        if source_task is not None and project_id is not None:
            budget_decision = self._budget_guard_service.evaluate_before_execution(
                source_task_id,
                project_id=project_id,
            )
            if not budget_decision.allowed:
                blocked_reasons.append("budget_guard_blocked")

        non_convergence_checked = False
        non_convergence_detected = False
        if intent is not None and intent.dispatch_kind == "auto_rework":
            non_convergence_checked = True
            history, history_invalid = self._revalidated_rework_history(
                session_id=session_id,
                source_task_id=source_task_id,
            )
            if history_invalid:
                blocked_reasons.append("rework_attempt_history_invalid")
            elif intent.rework_attempt_index >= 1:
                previous = next(
                    (
                        item
                        for item in history
                        if item.rework_attempt_index
                        == intent.rework_attempt_index - 1
                    ),
                    None,
                )
                if previous is None:
                    blocked_reasons.append("rework_attempt_history_invalid")
                elif (
                    previous.review_semantic_fingerprint
                    == intent.review_semantic_fingerprint
                ):
                    non_convergence_detected = True
                    blocked_reasons.extend(
                        ["rework_non_convergence", "human_escalation_required"]
                    )

        preflight_history = self._scan_preflight_history(
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=project_id,
        )
        replay_matches = [
            item
            for item in preflight_history.valid_preflights
            if item[0].source_intent_message_id == source_message_id
        ]
        if preflight_history.invalid or len(replay_matches) > 1:
            blocked_reasons.append("dispatch_consumption_preflight_replay_conflict")

        blocked_reasons = self._dedupe(blocked_reasons)
        values = self._result_values(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            project_id=project_id,
            source_task=source_task,
            intent=intent,
            current_freshness=current_freshness,
            readiness=readiness,
            task_preparation_strategy=task_preparation_strategy,
            planned_task_status=planned_task_status,
            budget_decision=budget_decision,
            non_convergence_checked=non_convergence_checked,
            non_convergence_detected=non_convergence_detected,
            validated_at=validated_at,
        )
        if blocked_reasons:
            return self._blocked(
                source_message_id=source_message_id,
                blocked_reasons=blocked_reasons,
                values=values,
            )

        preflight_id = replay_matches[0][0].preflight_id if replay_matches else uuid4()
        created_at = (
            replay_matches[0][0].created_at if replay_matches else validated_at
        )
        candidate = self._ready_result(
            preflight_id=preflight_id,
            created_at=created_at,
            values=values,
        )
        if replay_matches:
            existing, existing_message = replay_matches[0]
            if existing.preflight_fingerprint != candidate.preflight_fingerprint:
                return self._blocked(
                    source_message_id=source_message_id,
                    blocked_reasons=[
                        "dispatch_consumption_preflight_replay_conflict"
                    ],
                    values=values,
                )
            replayed = ProjectDirectorProtectedTransitionDispatchConsumptionPreflightResult.model_validate(
                {
                    **candidate.model_dump(),
                    "resumed_from_existing_preflight": True,
                }
            )
            return PreparedProjectDirectorProtectedTransitionDispatchConsumptionPreflight(
                result=replayed,
                message=existing_message,
            )

        action = candidate.model_dump(mode="json")
        action.update(
            {
                "type": P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_PREFLIGHT_ACTION_TYPE,
                "schema_version": PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION,
                "session_id": str(session_id),
                "source_task_id": str(source_task_id),
            }
        )
        message = self._message_repository.create(
            ProjectDirectorMessage(
                id=candidate.preflight_id,
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "A protected-transition dispatch consumption preflight was "
                    "prepared after exact intent revalidation, current workspace/diff "
                    "freshness revalidation, task readiness checks, and budget checks. "
                    "The source intent was not consumed. No task status was changed, "
                    "no task was claimed, no run was created, no worker or runtime was "
                    "started, and no Git write was authorized."
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent=_INTENT,
                related_project_id=project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL,
                suggested_actions=[action],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                forbidden_actions_detected=self._forbidden_actions(),
                created_at=candidate.created_at,
            )
        )
        return PreparedProjectDirectorProtectedTransitionDispatchConsumptionPreflight(
            result=candidate,
            message=message,
        )

    def _revalidated_rework_history(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
    ) -> tuple[list[ProjectDirectorProtectedTransitionDispatchIntentResult], bool]:
        intents: list[ProjectDirectorProtectedTransitionDispatchIntentResult] = []
        invalid = False
        for message in self._iter_session_messages(session_id):
            if message.source_detail != P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL:
                continue
            action = self._single_action(message)
            claims_task = bool(
                action is not None
                and action.get("source_task_id") == str(source_task_id)
            )
            if message.related_task_id != source_task_id and not claims_task:
                continue
            revalidated = self._dispatch_intent_service.revalidate_persisted_protected_transition_dispatch_intent(
                session_id=session_id,
                source_task_id=source_task_id,
                source_intent_message_id=message.id,
            )
            if revalidated.blocked_reasons or revalidated.result is None:
                invalid = True
            elif revalidated.result.dispatch_kind == "auto_rework":
                intents.append(revalidated.result)
        indexes = [item.rework_attempt_index for item in intents]
        if (
            len(indexes) != len(set(indexes))
            or indexes
            and sorted(indexes) != list(range(max(indexes) + 1))
        ):
            invalid = True
        return sorted(intents, key=lambda item: item.rework_attempt_index), invalid

    def _scan_preflight_history(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        project_id: UUID | None,
    ) -> _PreflightHistory:
        valid: list[
            tuple[
                ProjectDirectorProtectedTransitionDispatchConsumptionPreflightResult,
                ProjectDirectorMessage,
            ]
        ] = []
        invalid = False
        for message in self._iter_session_messages(session_id):
            if message.source_detail != P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL:
                continue
            action = self._single_action(message)
            claims_task = bool(
                action is not None
                and action.get("source_task_id") == str(source_task_id)
            )
            if message.related_task_id != source_task_id and not claims_task:
                continue
            result = self._trusted_preflight(
                message=message,
                session_id=session_id,
                source_task_id=source_task_id,
                project_id=project_id,
            )
            if result is None:
                invalid = True
            else:
                valid.append((result, message))
        return _PreflightHistory(valid_preflights=valid, invalid=invalid)

    def _trusted_preflight(
        self,
        *,
        message: ProjectDirectorMessage,
        session_id: UUID,
        source_task_id: UUID,
        project_id: UUID | None,
    ) -> ProjectDirectorProtectedTransitionDispatchConsumptionPreflightResult | None:
        if (
            message.session_id != session_id
            or message.related_project_id != project_id
            or message.related_task_id != source_task_id
            or message.role != ProjectDirectorMessageRole.ASSISTANT
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent != _INTENT
            or message.source_detail
            != P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL
            or message.requires_confirmation is not False
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
        ):
            return None
        action = self._single_action(message)
        if (
            action is None
            or action.get("type")
            != P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_PREFLIGHT_ACTION_TYPE
            or action.get("schema_version")
            != PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION
            or action.get("session_id") != str(session_id)
            or action.get("source_task_id") != str(source_task_id)
        ):
            return None
        try:
            result = ProjectDirectorProtectedTransitionDispatchConsumptionPreflightResult.model_validate(
                {
                    field_name: action.get(field_name)
                    for field_name in ProjectDirectorProtectedTransitionDispatchConsumptionPreflightResult.model_fields
                }
            )
        except ValidationError:
            return None
        if (
            result.preflight_status != "ready"
            or result.preflight_id != message.id
            or result.project_id != project_id
            or result.created_at != message.created_at
            or result.resumed_from_existing_preflight
            or result.preflight_fingerprint != self._preflight_fingerprint(result)
            or not set(self._forbidden_actions()).issubset(
                message.forbidden_actions_detected
            )
        ):
            return None
        return result

    def _result_values(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        project_id: UUID | None,
        source_task: Task | None,
        intent: ProjectDirectorProtectedTransitionDispatchIntentResult | None,
        current_freshness: RevalidatedCurrentProtectedTransitionEvidenceFreshness | None,
        readiness: TaskReadinessResult | None,
        task_preparation_strategy: str | None,
        planned_task_status: str | None,
        budget_decision: Any,
        non_convergence_checked: bool,
        non_convergence_detected: bool,
        validated_at: datetime,
    ) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "project_id": project_id,
            "source_task_id": source_task_id,
            "target_task_id": intent.target_task_id if intent else None,
            "source_intent_message_id": source_message_id,
            "source_dispatch_intent_id": intent.dispatch_intent_id if intent else None,
            "source_dispatch_intent_fingerprint": (
                intent.dispatch_intent_fingerprint if intent else ""
            ),
            "source_p22_summary_message_id": (
                intent.source_p22_summary_message_id if intent else None
            ),
            "source_review_message_id": (
                intent.source_review_message_id if intent else None
            ),
            "source_freshness_message_id": (
                intent.source_freshness_message_id if intent else None
            ),
            "disposition_type": intent.disposition_type if intent else None,
            "dispatch_kind": intent.dispatch_kind if intent else None,
            "target_task_strategy": intent.target_task_strategy if intent else None,
            "review_result_fingerprint": (
                intent.review_result_fingerprint if intent else ""
            ),
            "review_semantic_fingerprint": (
                intent.review_semantic_fingerprint if intent else ""
            ),
            "persisted_freshness_evidence_fingerprint": (
                current_freshness.persisted_freshness_evidence_fingerprint
                if current_freshness
                else ""
            ),
            "current_freshness_fingerprint": (
                current_freshness.current_freshness_fingerprint
                if current_freshness
                else ""
            ),
            "reviewed_diff_sha256": (
                current_freshness.reviewed_diff_sha256 if current_freshness else ""
            ),
            "current_diff_sha256": (
                current_freshness.current_diff_sha256 if current_freshness else ""
            ),
            "reviewed_scope_paths": (
                list(current_freshness.reviewed_scope_paths)
                if current_freshness
                else []
            ),
            "current_scope_paths": (
                list(current_freshness.current_scope_paths)
                if current_freshness
                else []
            ),
            "workspace_path": current_freshness.workspace_path if current_freshness else "",
            "workspace_path_within_root": (
                current_freshness.workspace_path_within_root
                if current_freshness
                else False
            ),
            "task_status_before": source_task.status.value if source_task else None,
            "task_human_status_before": (
                source_task.human_status.value if source_task else None
            ),
            "task_readiness_ready": (
                readiness.ready_for_execution if readiness else False
            ),
            "task_readiness_blocking_reasons": (
                list(readiness.blocking_reasons) if readiness else []
            ),
            "task_preparation_strategy": task_preparation_strategy,
            "planned_task_status_after_preparation": planned_task_status,
            "budget_guard_allowed": (
                budget_decision.allowed if budget_decision else False
            ),
            "budget_pressure_level": (
                budget_decision.pressure_level.value if budget_decision else None
            ),
            "budget_strategy_action": (
                budget_decision.suggested_action.value if budget_decision else None
            ),
            "budget_strategy_code": (
                budget_decision.strategy_code if budget_decision else None
            ),
            "budget_policy_source": (
                budget_decision.budget_policy_source if budget_decision else None
            ),
            "retry_limit_reached": (
                budget_decision.retry_status.retry_limit_reached
                if budget_decision
                else False
            ),
            "rework_attempt_index": intent.rework_attempt_index if intent else 0,
            "rework_attempt_limit": (
                intent.rework_attempt_limit
                if intent
                else PROTECTED_TRANSITION_REWORK_ATTEMPT_LIMIT
            ),
            "non_convergence_checked": non_convergence_checked,
            "non_convergence_detected": non_convergence_detected,
            "replay_check_completed": True,
            "validated_at": validated_at,
        }

    def _ready_result(
        self,
        *,
        preflight_id: UUID,
        created_at: datetime,
        values: dict[str, Any],
    ) -> ProjectDirectorProtectedTransitionDispatchConsumptionPreflightResult:
        basis = ProjectDirectorProtectedTransitionDispatchConsumptionPreflightResult(
            preflight_status="ready",
            preflight_id=preflight_id,
            preflight_fingerprint="0" * 64,
            created_at=created_at,
            **values,
        )
        return ProjectDirectorProtectedTransitionDispatchConsumptionPreflightResult.model_validate(
            {
                **basis.model_dump(),
                "preflight_fingerprint": self._preflight_fingerprint(basis),
            }
        )

    @staticmethod
    def _blocked(
        *,
        source_message_id: UUID,
        blocked_reasons: list[str],
        values: dict[str, Any],
    ) -> PreparedProjectDirectorProtectedTransitionDispatchConsumptionPreflight:
        result = ProjectDirectorProtectedTransitionDispatchConsumptionPreflightResult(
            preflight_status="blocked",
            source_intent_message_id=source_message_id,
            blocked_reasons=list(dict.fromkeys(blocked_reasons)),
            **{
                key: value
                for key, value in values.items()
                if key != "source_intent_message_id"
            },
        )
        return PreparedProjectDirectorProtectedTransitionDispatchConsumptionPreflight(
            result=result,
            message=None,
        )

    @staticmethod
    def _preflight_fingerprint(
        result: ProjectDirectorProtectedTransitionDispatchConsumptionPreflightResult,
    ) -> str:
        payload = {
            "schema_version": PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION,
            "session_id": str(result.session_id),
            "project_id": str(result.project_id),
            "source_task_id": str(result.source_task_id),
            "target_task_id": str(result.target_task_id),
            "source_intent_message_id": str(result.source_intent_message_id),
            "source_dispatch_intent_id": str(result.source_dispatch_intent_id),
            "source_dispatch_intent_fingerprint": result.source_dispatch_intent_fingerprint,
            "source_p22_summary_message_id": str(result.source_p22_summary_message_id),
            "source_review_message_id": str(result.source_review_message_id),
            "source_freshness_message_id": str(result.source_freshness_message_id),
            "disposition_type": result.disposition_type,
            "dispatch_kind": result.dispatch_kind,
            "target_task_strategy": result.target_task_strategy,
            "review_result_fingerprint": result.review_result_fingerprint,
            "review_semantic_fingerprint": result.review_semantic_fingerprint,
            "persisted_freshness_evidence_fingerprint": result.persisted_freshness_evidence_fingerprint,
            "current_freshness_fingerprint": result.current_freshness_fingerprint,
            "reviewed_diff_sha256": result.reviewed_diff_sha256,
            "current_diff_sha256": result.current_diff_sha256,
            "reviewed_scope_paths": list(result.reviewed_scope_paths),
            "current_scope_paths": list(result.current_scope_paths),
            "workspace_path": result.workspace_path,
            "workspace_path_within_root": result.workspace_path_within_root,
            "task_status_before": result.task_status_before,
            "task_human_status_before": result.task_human_status_before,
            "task_preparation_strategy": result.task_preparation_strategy,
            "planned_task_status_after_preparation": result.planned_task_status_after_preparation,
            "rework_attempt_index": result.rework_attempt_index,
            "rework_attempt_limit": result.rework_attempt_limit,
            "non_convergence_detected": result.non_convergence_detected,
        }
        return ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService._canonical_fingerprint(
            payload
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
    def _single_action(message: ProjectDirectorMessage) -> dict[str, Any] | None:
        if (
            len(message.suggested_actions) != 1
            or not isinstance(message.suggested_actions[0], dict)
        ):
            return None
        return message.suggested_actions[0]

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
    def _dedupe(values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    @staticmethod
    def _forbidden_actions() -> list[str]:
        return [
            "no_dispatch_intent_consumption",
            "no_task_status_mutation",
            "no_task_claim",
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
    "P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_PREFLIGHT_ACTION_TYPE",
    "P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL",
    "PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION",
    "PreparedProjectDirectorProtectedTransitionDispatchConsumptionPreflight",
    "ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService",
)
