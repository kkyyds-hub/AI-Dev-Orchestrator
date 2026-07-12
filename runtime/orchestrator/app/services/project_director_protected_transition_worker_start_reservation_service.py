"""Project Director P23-D2-B1 protected-transition Worker start reservation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_protected_transition_dispatch_consumption import (
    ProjectDirectorProtectedTransitionDispatchConsumptionResult,
)
from app.domain.project_director_protected_transition_worker_start_reservation import (
    ProjectDirectorProtectedTransitionWorkerStartReservationResult,
)
from app.domain.run import Run, RunStatus
from app.domain.task import Task, TaskHumanStatus, TaskStatus
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.budget_guard_service import BudgetGuardDecision, BudgetGuardService
from app.services.project_director_protected_transition_dispatch_consumption_service import (
    ProjectDirectorProtectedTransitionDispatchConsumptionService,
)
from app.services.project_director_protected_transition_evidence_freshness_service import (
    ProjectDirectorProtectedTransitionEvidenceFreshnessService,
    RevalidatedCurrentProtectedTransitionEvidenceFreshness,
)


P23_PROTECTED_TRANSITION_WORKER_START_RESERVATION_SOURCE_DETAIL = (
    "p23_d2_worker_start_reserved"
)
P23_PROTECTED_TRANSITION_WORKER_START_RESERVATION_ACTION_TYPE = (
    "p23_d2_worker_start_reservation_record"
)
PROTECTED_TRANSITION_WORKER_START_RESERVATION_SCHEMA_VERSION = "p23-d2-b1.v1"

_INTENT = "protected_transition_worker_start_reservation"
_PAGE_SIZE = 100


@dataclass(frozen=True, slots=True)
class PreparedProjectDirectorProtectedTransitionWorkerStartReservation:
    """B1 eligibility result and optional append-only reservation message."""

    result: ProjectDirectorProtectedTransitionWorkerStartReservationResult
    message: ProjectDirectorMessage | None


@dataclass(frozen=True, slots=True)
class RevalidatedPersistedProtectedTransitionWorkerStartReservation:
    """Immutable revalidation of one exact persisted B1 reservation."""

    result: ProjectDirectorProtectedTransitionWorkerStartReservationResult | None
    message: ProjectDirectorMessage | None
    task: Task | None
    run: Run | None
    blocked_reasons: list[str]


@dataclass(frozen=True, slots=True)
class RevalidatedCurrentProtectedTransitionWorkerStartReservation:
    """Current execution eligibility for one immutable B1 reservation."""

    result: ProjectDirectorProtectedTransitionWorkerStartReservationResult | None
    message: ProjectDirectorMessage | None
    task: Task | None
    run: Run | None
    current_freshness: RevalidatedCurrentProtectedTransitionEvidenceFreshness | None
    budget_decision: BudgetGuardDecision | None
    blocked_reasons: list[str]


@dataclass(frozen=True, slots=True)
class _CurrentReservationEvaluation:
    task: Task | None
    run: Run | None
    current_freshness: RevalidatedCurrentProtectedTransitionEvidenceFreshness | None
    budget_decision: BudgetGuardDecision | None
    values: dict[str, Any]
    blocked_reasons: list[str]


@dataclass(frozen=True, slots=True)
class _ReservationHistory:
    valid_reservations: list[
        tuple[
            ProjectDirectorProtectedTransitionWorkerStartReservationResult,
            ProjectDirectorMessage,
        ]
    ]
    invalid: bool = False


class ProjectDirectorProtectedTransitionWorkerStartReservationService:
    """Reserve one exact D1 Task/Run for a future Worker invocation."""

    def __init__(
        self,
        *,
        session_repository: ProjectDirectorSessionRepository,
        message_repository: ProjectDirectorMessageRepository,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        agent_session_repository: AgentSessionRepository,
        dispatch_consumption_service: ProjectDirectorProtectedTransitionDispatchConsumptionService,
        freshness_service: ProjectDirectorProtectedTransitionEvidenceFreshnessService,
        budget_guard_service: BudgetGuardService,
    ) -> None:
        self._session_repository = session_repository
        self._message_repository = message_repository
        self._task_repository = task_repository
        self._run_repository = run_repository
        self._agent_session_repository = agent_session_repository
        self._dispatch_consumption_service = dispatch_consumption_service
        self._freshness_service = freshness_service
        self._budget_guard_service = budget_guard_service
        self._require_shared_sqlalchemy_session()

    def prepare_protected_transition_worker_start_reservation(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
    ) -> PreparedProjectDirectorProtectedTransitionWorkerStartReservation:
        """Atomically replay or append one exact Worker start reservation."""

        with self._message_repository.sqlite_immediate_transaction():
            return self._prepare_protected_transition_worker_start_reservation(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
            )

    def revalidate_persisted_protected_transition_worker_start_reservation(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_reservation_message_id: UUID,
    ) -> RevalidatedPersistedProtectedTransitionWorkerStartReservation:
        """Rebuild immutable B1 evidence without checking current eligibility."""

        message = self._message_repository.get_by_id(source_reservation_message_id)
        if message is None:
            return RevalidatedPersistedProtectedTransitionWorkerStartReservation(
                result=None,
                message=None,
                task=None,
                run=None,
                blocked_reasons=["source_reservation_missing"],
            )
        if message.session_id != session_id:
            return RevalidatedPersistedProtectedTransitionWorkerStartReservation(
                result=None,
                message=message,
                task=None,
                run=None,
                blocked_reasons=["source_reservation_session_mismatch"],
            )
        if message.related_task_id != source_task_id:
            return RevalidatedPersistedProtectedTransitionWorkerStartReservation(
                result=None,
                message=message,
                task=None,
                run=None,
                blocked_reasons=["source_reservation_task_mismatch"],
            )

        session_obj = self._session_repository.get_by_id(session_id)
        task = self._task_repository.get_by_id(source_task_id)
        project_id = session_obj.project_id if session_obj is not None else None
        if task is None:
            return RevalidatedPersistedProtectedTransitionWorkerStartReservation(
                result=None,
                message=message,
                task=None,
                run=None,
                blocked_reasons=["source_task_missing"],
            )
        if (
            session_obj is None
            or project_id is None
            or message.related_project_id != project_id
            or task.project_id != project_id
        ):
            return RevalidatedPersistedProtectedTransitionWorkerStartReservation(
                result=None,
                message=message,
                task=task,
                run=None,
                blocked_reasons=["source_reservation_project_mismatch"],
            )

        result = self._trusted_reservation(
            message=message,
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=project_id,
        )
        if result is None or result.reservation_token is None:
            return RevalidatedPersistedProtectedTransitionWorkerStartReservation(
                result=None,
                message=message,
                task=task,
                run=None,
                blocked_reasons=["source_reservation_invalid"],
            )

        d1 = self._dispatch_consumption_service.revalidate_persisted_protected_transition_dispatch_consumption(
            session_id=session_id,
            source_task_id=source_task_id,
            source_consumption_message_id=result.source_consumption_message_id,
        )
        consumption = d1.result
        if d1.blocked_reasons or consumption is None:
            return RevalidatedPersistedProtectedTransitionWorkerStartReservation(
                result=result,
                message=message,
                task=task,
                run=None,
                blocked_reasons=(
                    ["source_evidence_chain_invalid"]
                    if "source_evidence_chain_invalid" in d1.blocked_reasons
                    else ["source_consumption_invalid"]
                ),
            )
        expected_values = self._values_from_consumption(consumption)
        immutable_bindings = (
            (result.project_id, expected_values["project_id"]),
            (result.target_task_id, expected_values["target_task_id"]),
            (result.run_id, expected_values["run_id"]),
            (result.source_consumption_id, expected_values["source_consumption_id"]),
            (
                result.source_consumption_fingerprint,
                expected_values["source_consumption_fingerprint"],
            ),
            (result.source_preflight_message_id, expected_values["source_preflight_message_id"]),
            (result.source_intent_message_id, expected_values["source_intent_message_id"]),
            (
                result.source_p22_summary_message_id,
                expected_values["source_p22_summary_message_id"],
            ),
            (result.source_review_message_id, expected_values["source_review_message_id"]),
            (
                result.source_freshness_message_id,
                expected_values["source_freshness_message_id"],
            ),
            (result.disposition_type, expected_values["disposition_type"]),
            (result.dispatch_kind, expected_values["dispatch_kind"]),
            (result.target_task_strategy, expected_values["target_task_strategy"]),
            (
                result.review_result_fingerprint,
                expected_values["review_result_fingerprint"],
            ),
            (
                result.review_semantic_fingerprint,
                expected_values["review_semantic_fingerprint"],
            ),
            (
                result.d1_current_freshness_fingerprint,
                expected_values["d1_current_freshness_fingerprint"],
            ),
            (result.source_diff_sha256, expected_values["source_diff_sha256"]),
            (result.review_scope_paths, expected_values["review_scope_paths"]),
            (result.workspace_path, expected_values["workspace_path"]),
            (
                result.workspace_path_within_root,
                expected_values["workspace_path_within_root"],
            ),
            (result.rework_attempt_index, expected_values["rework_attempt_index"]),
            (result.rework_attempt_limit, expected_values["rework_attempt_limit"]),
        )
        if any(left != right for left, right in immutable_bindings):
            return RevalidatedPersistedProtectedTransitionWorkerStartReservation(
                result=result,
                message=message,
                task=task,
                run=d1.run,
                blocked_reasons=["source_evidence_chain_invalid"],
            )

        run = self._run_repository.get_by_id(result.run_id)
        if run is None:
            return RevalidatedPersistedProtectedTransitionWorkerStartReservation(
                result=result,
                message=message,
                task=task,
                run=None,
                blocked_reasons=["reserved_run_missing"],
            )
        if run.task_id != source_task_id:
            return RevalidatedPersistedProtectedTransitionWorkerStartReservation(
                result=result,
                message=message,
                task=task,
                run=run,
                blocked_reasons=["reserved_run_task_mismatch"],
            )

        history = self._scan_reservation_history(
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=project_id,
        )
        exact = [item for item in history.valid_reservations if item[1].id == message.id]
        consumption_conflicts = [
            item
            for item in history.valid_reservations
            if item[0].source_consumption_message_id
            == result.source_consumption_message_id
            and item[1].id != message.id
        ]
        run_conflicts = [
            item
            for item in history.valid_reservations
            if item[0].run_id == result.run_id and item[1].id != message.id
        ]
        if history.invalid or len(exact) != 1 or consumption_conflicts or run_conflicts:
            return RevalidatedPersistedProtectedTransitionWorkerStartReservation(
                result=result,
                message=message,
                task=task,
                run=run,
                blocked_reasons=["source_reservation_lineage_conflict"],
            )
        return RevalidatedPersistedProtectedTransitionWorkerStartReservation(
            result=result,
            message=message,
            task=task,
            run=run,
            blocked_reasons=[],
        )

    def revalidate_current_protected_transition_worker_start_reservation(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_reservation_message_id: UUID,
    ) -> RevalidatedCurrentProtectedTransitionWorkerStartReservation:
        """Revalidate immutable B1 evidence plus current execution eligibility."""

        persisted = self.revalidate_persisted_protected_transition_worker_start_reservation(
            session_id=session_id,
            source_task_id=source_task_id,
            source_reservation_message_id=source_reservation_message_id,
        )
        if persisted.blocked_reasons or persisted.result is None:
            return RevalidatedCurrentProtectedTransitionWorkerStartReservation(
                result=persisted.result,
                message=persisted.message,
                task=persisted.task,
                run=persisted.run,
                current_freshness=None,
                budget_decision=None,
                blocked_reasons=list(persisted.blocked_reasons),
            )
        d1 = self._dispatch_consumption_service.revalidate_persisted_protected_transition_dispatch_consumption(
            session_id=session_id,
            source_task_id=source_task_id,
            source_consumption_message_id=persisted.result.source_consumption_message_id,
        )
        if d1.blocked_reasons or d1.result is None:
            return RevalidatedCurrentProtectedTransitionWorkerStartReservation(
                result=persisted.result,
                message=persisted.message,
                task=persisted.task,
                run=persisted.run,
                current_freshness=None,
                budget_decision=None,
                blocked_reasons=["source_consumption_invalid"],
            )
        current = self._evaluate_current_reservation_eligibility(
            consumption=d1.result,
        )
        return RevalidatedCurrentProtectedTransitionWorkerStartReservation(
            result=persisted.result,
            message=persisted.message,
            task=current.task,
            run=current.run,
            current_freshness=current.current_freshness,
            budget_decision=current.budget_decision,
            blocked_reasons=list(current.blocked_reasons),
        )

    def _prepare_protected_transition_worker_start_reservation(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
    ) -> PreparedProjectDirectorProtectedTransitionWorkerStartReservation:
        session_obj = self._session_repository.get_by_id(session_id)
        project_id = session_obj.project_id if session_obj is not None else None
        values: dict[str, Any] = {
            "session_id": session_id,
            "project_id": project_id,
            "source_task_id": source_task_id,
            "source_consumption_message_id": source_message_id,
            "replay_check_completed": True,
        }
        if session_obj is None or project_id is None:
            return self._blocked(
                reasons=["source_consumption_project_mismatch"],
                values=values,
            )

        d1_revalidation = self._dispatch_consumption_service.revalidate_persisted_protected_transition_dispatch_consumption(
            session_id=session_id,
            source_task_id=source_task_id,
            source_consumption_message_id=source_message_id,
        )
        consumption = d1_revalidation.result
        if d1_revalidation.blocked_reasons or consumption is None:
            return self._blocked(
                reasons=(
                    d1_revalidation.blocked_reasons
                    or ["source_consumption_invalid"]
                ),
                values=values,
            )
        values.update(self._values_from_consumption(consumption))
        current = self._evaluate_current_reservation_eligibility(
            consumption=consumption,
        )
        values.update(current.values)
        if current.blocked_reasons:
            return self._blocked(reasons=current.blocked_reasons, values=values)
        run = current.run
        if run is None:
            return self._blocked(reasons=["reserved_run_missing"], values=values)

        history = self._scan_reservation_history(
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=project_id,
        )
        replay_matches = [
            item
            for item in history.valid_reservations
            if item[0].source_consumption_message_id == source_message_id
            and item[0].run_id == run.id
        ]
        consumption_conflicts = [
            item
            for item in history.valid_reservations
            if item[0].source_consumption_message_id == source_message_id
            and item[0].run_id != run.id
        ]
        run_conflicts = [
            item
            for item in history.valid_reservations
            if item[0].run_id == run.id
            and item[0].source_consumption_message_id != source_message_id
        ]
        if (
            history.invalid
            or len(replay_matches) > 1
            or consumption_conflicts
            or run_conflicts
        ):
            return self._blocked(
                reasons=["worker_start_reservation_replay_conflict"],
                values=values,
            )
        if replay_matches:
            existing, existing_message = replay_matches[0]
            candidate = self._reserved_result(
                values=values,
                run=run,
                reservation_id=existing.reservation_id,
                reservation_token=existing.reservation_token,
                created_at=existing.created_at,
            )
            if candidate.reservation_fingerprint != existing.reservation_fingerprint:
                return self._blocked(
                    reasons=["worker_start_reservation_replay_conflict"],
                    values=values,
                )
            replayed = ProjectDirectorProtectedTransitionWorkerStartReservationResult.model_validate(
                {
                    **existing.model_dump(),
                    "resumed_from_existing_reservation": True,
                }
            )
            return PreparedProjectDirectorProtectedTransitionWorkerStartReservation(
                result=replayed,
                message=existing_message,
            )

        reservation = self._reserved_result(values=values, run=run)
        message = self._message_repository.create(
            self._reservation_message(result=reservation)
        )
        return PreparedProjectDirectorProtectedTransitionWorkerStartReservation(
            result=reservation,
            message=message,
        )

    def _evaluate_current_reservation_eligibility(
        self,
        *,
        consumption: ProjectDirectorProtectedTransitionDispatchConsumptionResult,
    ) -> _CurrentReservationEvaluation:
        """Evaluate the one shared B1/B2 current eligibility contract."""

        values: dict[str, Any] = {}
        reasons: list[str] = []
        task = self._task_repository.get_by_id(consumption.source_task_id)
        run = self._run_repository.get_by_id(consumption.run_id)
        if task is None:
            reasons.append("source_task_missing")
        else:
            values.update(
                task_status=task.status.value,
                task_human_status=task.human_status.value,
            )
            if task.id != consumption.source_task_id or task.project_id != consumption.project_id:
                reasons.append("source_task_scope_mismatch")
            if task.status != TaskStatus.RUNNING:
                reasons.append("source_task_not_running")
            if task.human_status in {
                TaskHumanStatus.REQUESTED,
                TaskHumanStatus.IN_PROGRESS,
            } or task.paused_reason:
                reasons.append("human_escalation_required")

        if run is None:
            reasons.append("reserved_run_missing")
        else:
            routing_valid = self._routing_metadata_valid(run)
            values.update(
                run_id=run.id,
                run_status=run.status.value,
                run_started_at=run.started_at,
                run_routing_metadata_valid=routing_valid,
            )
            if run.id != consumption.run_id or run.task_id != consumption.source_task_id:
                reasons.append("reserved_run_task_mismatch")
            if run.status != RunStatus.RUNNING or run.started_at is None:
                reasons.append("reserved_run_not_running")
            if not routing_valid:
                reasons.append("reserved_run_routing_metadata_invalid")

        current_freshness = self._freshness_service.revalidate_current_automatic_transition_evidence_from_persisted_freshness(
            session_id=consumption.session_id,
            source_task_id=consumption.source_task_id,
            source_freshness_message_id=consumption.source_freshness_message_id,
        )
        values.update(self._freshness_values(current_freshness))
        reasons.extend(
            self._freshness_blocked_reasons(
                consumption=consumption,
                current=current_freshness,
            )
        )

        budget = self._budget_guard_service.evaluate_before_execution(
            consumption.source_task_id,
            project_id=consumption.project_id,
        )
        values.update(self._budget_values(budget))
        if not budget.allowed:
            reasons.append("budget_guard_blocked")
        if budget.retry_status.retry_limit_reached:
            reasons.append("retry_limit_reached")

        agent_session = (
            self._agent_session_repository.get_by_run_id(run.id)
            if run is not None
            else None
        )
        values["agent_session_absent"] = agent_session is None
        if agent_session is not None:
            reasons.append("reserved_run_agent_session_already_exists")

        return _CurrentReservationEvaluation(
            task=task,
            run=run,
            current_freshness=current_freshness,
            budget_decision=budget,
            values=values,
            blocked_reasons=list(dict.fromkeys(reasons)),
        )

    def _scan_reservation_history(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        project_id: UUID,
    ) -> _ReservationHistory:
        valid: list[
            tuple[
                ProjectDirectorProtectedTransitionWorkerStartReservationResult,
                ProjectDirectorMessage,
            ]
        ] = []
        invalid = False
        for message in self._iter_session_messages(session_id):
            if message.source_detail != P23_PROTECTED_TRANSITION_WORKER_START_RESERVATION_SOURCE_DETAIL:
                continue
            action = self._single_action(message)
            claims_task = bool(
                action is not None
                and action.get("source_task_id") == str(source_task_id)
            )
            if message.related_task_id != source_task_id and not claims_task:
                continue
            result = self._trusted_reservation(
                message=message,
                session_id=session_id,
                source_task_id=source_task_id,
                project_id=project_id,
            )
            if result is None:
                invalid = True
            else:
                valid.append((result, message))
        return _ReservationHistory(valid_reservations=valid, invalid=invalid)

    def _trusted_reservation(
        self,
        *,
        message: ProjectDirectorMessage,
        session_id: UUID,
        source_task_id: UUID,
        project_id: UUID,
    ) -> ProjectDirectorProtectedTransitionWorkerStartReservationResult | None:
        if (
            message.session_id != session_id
            or message.related_project_id != project_id
            or message.related_task_id != source_task_id
            or message.role != ProjectDirectorMessageRole.ASSISTANT
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent != _INTENT
            or message.source_detail
            != P23_PROTECTED_TRANSITION_WORKER_START_RESERVATION_SOURCE_DETAIL
            or message.requires_confirmation is not False
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
        ):
            return None
        action = self._single_action(message)
        if (
            action is None
            or action.get("type")
            != P23_PROTECTED_TRANSITION_WORKER_START_RESERVATION_ACTION_TYPE
            or action.get("schema_version")
            != PROTECTED_TRANSITION_WORKER_START_RESERVATION_SCHEMA_VERSION
            or action.get("session_id") != str(session_id)
            or action.get("source_task_id") != str(source_task_id)
        ):
            return None
        try:
            result = ProjectDirectorProtectedTransitionWorkerStartReservationResult.model_validate(
                {
                    field_name: action.get(field_name)
                    for field_name in ProjectDirectorProtectedTransitionWorkerStartReservationResult.model_fields
                }
            )
        except ValidationError:
            return None
        run = self._run_repository.get_by_id(result.run_id)
        if (
            result.reservation_status != "reserved"
            or result.reservation_id != message.id
            or result.project_id != project_id
            or result.created_at != message.created_at
            or result.resumed_from_existing_reservation
            or run is None
            or run.task_id != source_task_id
            or result.reservation_fingerprint
            != self._reservation_fingerprint(result=result, run=run)
            or not set(self._forbidden_actions()).issubset(
                message.forbidden_actions_detected
            )
        ):
            return None
        return result

    def _reserved_result(
        self,
        *,
        values: dict[str, Any],
        run: Run,
        reservation_id: UUID | None = None,
        reservation_token: str | None = None,
        created_at: datetime | None = None,
    ) -> ProjectDirectorProtectedTransitionWorkerStartReservationResult:
        result_values = {
            "reservation_status": "reserved",
            "reservation_id": reservation_id or uuid4(),
            "reservation_fingerprint": "0" * 64,
            "reservation_token": reservation_token or uuid4().hex,
            "worker_start_reserved": True,
            **values,
        }
        if created_at is not None:
            result_values["created_at"] = created_at
        result = ProjectDirectorProtectedTransitionWorkerStartReservationResult(
            **result_values,
        )
        return ProjectDirectorProtectedTransitionWorkerStartReservationResult.model_validate(
            {
                **result.model_dump(),
                "reservation_fingerprint": self._reservation_fingerprint(
                    result=result,
                    run=run,
                ),
            }
        )

    def _reservation_message(
        self,
        *,
        result: ProjectDirectorProtectedTransitionWorkerStartReservationResult,
    ) -> ProjectDirectorMessage:
        action = result.model_dump(mode="json")
        action.update(
            {
                "type": P23_PROTECTED_TRANSITION_WORKER_START_RESERVATION_ACTION_TYPE,
                "schema_version": PROTECTED_TRANSITION_WORKER_START_RESERVATION_SCHEMA_VERSION,
                "session_id": str(result.session_id),
                "source_task_id": str(result.source_task_id),
            }
        )
        return ProjectDirectorMessage(
            id=result.reservation_id,
            session_id=result.session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content=(
                "An exact protected-transition Task and Run were reserved for a "
                "future Worker invocation after immutable D1 evidence, current "
                "freshness, budget, Task/Run binding, and AgentSession checks. "
                "The Worker was not invoked. No AgentSession or runtime was "
                "started. AUTO_CONTINUE or AUTO_REWORK execution has not started, "
                "and no Git write was authorized."
            ),
            sequence_no=self._message_repository.get_next_sequence_no(
                session_id=result.session_id
            ),
            intent=_INTENT,
            related_project_id=result.project_id,
            related_task_id=result.source_task_id,
            source=ProjectDirectorMessageSource.SYSTEM,
            source_detail=P23_PROTECTED_TRANSITION_WORKER_START_RESERVATION_SOURCE_DETAIL,
            suggested_actions=[action],
            requires_confirmation=False,
            risk_level=ProjectDirectorMessageRiskLevel.HIGH,
            forbidden_actions_detected=self._forbidden_actions(),
            created_at=result.created_at,
        )

    @staticmethod
    def _values_from_consumption(
        consumption: ProjectDirectorProtectedTransitionDispatchConsumptionResult,
    ) -> dict[str, Any]:
        return {
            "project_id": consumption.project_id,
            "target_task_id": consumption.target_task_id,
            "run_id": consumption.run_id,
            "source_consumption_id": consumption.consumption_id,
            "source_consumption_fingerprint": consumption.consumption_fingerprint,
            "source_preflight_message_id": consumption.source_preflight_message_id,
            "source_intent_message_id": consumption.source_intent_message_id,
            "source_p22_summary_message_id": consumption.source_p22_summary_message_id,
            "source_review_message_id": consumption.source_review_message_id,
            "source_freshness_message_id": consumption.source_freshness_message_id,
            "disposition_type": consumption.disposition_type,
            "dispatch_kind": consumption.dispatch_kind,
            "target_task_strategy": consumption.target_task_strategy,
            "review_result_fingerprint": consumption.review_result_fingerprint,
            "review_semantic_fingerprint": consumption.review_semantic_fingerprint,
            "d1_current_freshness_fingerprint": consumption.current_freshness_fingerprint,
            "source_diff_sha256": consumption.source_diff_sha256,
            "review_scope_paths": list(consumption.review_scope_paths),
            "workspace_path": consumption.workspace_path,
            "workspace_path_within_root": consumption.workspace_path_within_root,
            "rework_attempt_index": consumption.rework_attempt_index,
            "rework_attempt_limit": consumption.rework_attempt_limit,
        }

    @staticmethod
    def _freshness_values(
        current: RevalidatedCurrentProtectedTransitionEvidenceFreshness,
    ) -> dict[str, Any]:
        return {
            "reservation_current_freshness_fingerprint": current.current_freshness_fingerprint,
            "current_diff_sha256": current.current_diff_sha256,
            "current_scope_paths": list(current.current_scope_paths),
            "workspace_path": current.workspace_path,
            "workspace_path_within_root": current.workspace_path_within_root,
        }

    @staticmethod
    def _freshness_blocked_reasons(
        *,
        consumption: ProjectDirectorProtectedTransitionDispatchConsumptionResult,
        current: RevalidatedCurrentProtectedTransitionEvidenceFreshness,
    ) -> list[str]:
        reasons: list[str] = []
        if current.freshness_status != "ready" or current.blocked_reasons:
            reasons.append("current_freshness_revalidation_failed")
        if current.current_freshness_fingerprint != consumption.current_freshness_fingerprint:
            reasons.append("current_freshness_stale")
        if current.current_diff_sha256 != consumption.source_diff_sha256:
            reasons.append("current_diff_mismatch")
        if list(current.current_scope_paths) != list(consumption.review_scope_paths):
            reasons.append("current_scope_mismatch")
        if (
            current.workspace_path != consumption.workspace_path
            or not current.workspace_path_within_root
        ):
            reasons.append("current_workspace_invalid")
        return list(dict.fromkeys(reasons))

    @staticmethod
    def _budget_values(decision: BudgetGuardDecision) -> dict[str, Any]:
        return {
            "budget_guard_allowed": decision.allowed,
            "budget_pressure_level": decision.pressure_level.value,
            "budget_strategy_action": decision.suggested_action.value,
            "budget_strategy_code": decision.strategy_code,
            "budget_policy_source": decision.budget_policy_source,
            "retry_limit_reached": decision.retry_status.retry_limit_reached,
        }

    @staticmethod
    def _routing_metadata_valid(run: Run) -> bool:
        return all(
            (
                run.model_name,
                run.route_reason,
                run.routing_score is not None,
                run.routing_score_breakdown,
                run.strategy_decision,
                run.owner_role_code,
                run.dispatch_status,
            )
        )

    @staticmethod
    def _routing_identity(run: Run) -> dict[str, Any]:
        return {
            "model_name": run.model_name,
            "route_reason": run.route_reason,
            "routing_score": run.routing_score,
            "routing_score_breakdown": [
                item.model_dump(mode="json") for item in run.routing_score_breakdown
            ],
            "strategy_decision": (
                run.strategy_decision.model_dump(mode="json")
                if run.strategy_decision is not None
                else None
            ),
            "owner_role_code": (
                run.owner_role_code.value if run.owner_role_code is not None else None
            ),
            "dispatch_status": run.dispatch_status,
        }

    @classmethod
    def _reservation_fingerprint(
        cls,
        *,
        result: ProjectDirectorProtectedTransitionWorkerStartReservationResult,
        run: Run,
    ) -> str:
        payload = {
            "schema_version": PROTECTED_TRANSITION_WORKER_START_RESERVATION_SCHEMA_VERSION,
            "session_id": str(result.session_id),
            "project_id": str(result.project_id),
            "source_task_id": str(result.source_task_id),
            "target_task_id": str(result.target_task_id),
            "run_id": str(result.run_id),
            "source_consumption_message_id": str(result.source_consumption_message_id),
            "source_consumption_fingerprint": result.source_consumption_fingerprint,
            "source_preflight_message_id": str(result.source_preflight_message_id),
            "source_intent_message_id": str(result.source_intent_message_id),
            "source_p22_summary_message_id": str(
                result.source_p22_summary_message_id
            ),
            "source_review_message_id": str(result.source_review_message_id),
            "source_freshness_message_id": str(result.source_freshness_message_id),
            "disposition_type": result.disposition_type,
            "dispatch_kind": result.dispatch_kind,
            "target_task_strategy": result.target_task_strategy,
            "review_result_fingerprint": result.review_result_fingerprint,
            "review_semantic_fingerprint": result.review_semantic_fingerprint,
            "d1_current_freshness_fingerprint": result.d1_current_freshness_fingerprint,
            "reservation_current_freshness_fingerprint": result.reservation_current_freshness_fingerprint,
            "source_diff_sha256": result.source_diff_sha256,
            "current_diff_sha256": result.current_diff_sha256,
            "review_scope_paths": list(result.review_scope_paths),
            "current_scope_paths": list(result.current_scope_paths),
            "workspace_path": result.workspace_path,
            "task_status": result.task_status,
            "run_status": result.run_status,
            "run_routing_identity": cls._routing_identity(run),
            "rework_attempt_index": result.rework_attempt_index,
            "rework_attempt_limit": result.rework_attempt_limit,
        }
        return cls._canonical_fingerprint(payload)

    @staticmethod
    def _blocked(
        *,
        reasons: list[str],
        values: dict[str, Any],
    ) -> PreparedProjectDirectorProtectedTransitionWorkerStartReservation:
        result = ProjectDirectorProtectedTransitionWorkerStartReservationResult(
            reservation_status="blocked",
            blocked_reasons=list(dict.fromkeys(reasons)),
            **values,
        )
        return PreparedProjectDirectorProtectedTransitionWorkerStartReservation(
            result=result,
            message=None,
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

    def _require_shared_sqlalchemy_session(self) -> None:
        session = self._message_repository._session
        dependencies = (
            self._session_repository._session,
            self._task_repository.session,
            self._run_repository.session,
            self._agent_session_repository.session,
            self._budget_guard_service._db_session,
        )
        if any(candidate is not session for candidate in dependencies):
            raise ValueError("B1 dependencies must share one SQLAlchemy Session")
        if (
            self._dispatch_consumption_service._message_repository
            is not self._message_repository
            or self._dispatch_consumption_service._task_repository
            is not self._task_repository
            or self._dispatch_consumption_service._run_repository
            is not self._run_repository
            or self._freshness_service._message_repository
            is not self._message_repository
            or self._freshness_service._task_repository is not self._task_repository
        ):
            raise ValueError("B1 revalidation services must share repository instances")

    @staticmethod
    def _forbidden_actions() -> list[str]:
        return [
            "no_worker_invocation",
            "no_agent_session_creation",
            "no_runtime_start",
            "no_continuation_execution_start",
            "no_rework_execution_start",
            "no_task_creation",
            "no_run_creation",
            "no_task_status_mutation",
            "no_run_status_mutation",
            "no_product_runtime_git_write",
            "no_pr_creation",
            "no_merge",
            "no_ci_trigger",
        ]


__all__ = (
    "P23_PROTECTED_TRANSITION_WORKER_START_RESERVATION_ACTION_TYPE",
    "P23_PROTECTED_TRANSITION_WORKER_START_RESERVATION_SOURCE_DETAIL",
    "PROTECTED_TRANSITION_WORKER_START_RESERVATION_SCHEMA_VERSION",
    "PreparedProjectDirectorProtectedTransitionWorkerStartReservation",
    "ProjectDirectorProtectedTransitionWorkerStartReservationService",
    "RevalidatedCurrentProtectedTransitionWorkerStartReservation",
    "RevalidatedPersistedProtectedTransitionWorkerStartReservation",
)
