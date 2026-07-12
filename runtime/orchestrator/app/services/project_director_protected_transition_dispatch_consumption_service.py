"""Project Director P23-D1 受保护转换调度原子消费服务。"""

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
from app.domain.project_director_protected_transition_dispatch_consumption import (
    ProjectDirectorProtectedTransitionDispatchConsumptionResult,
)
from app.domain.project_director_protected_transition_dispatch_consumption_preflight import (
    ProjectDirectorProtectedTransitionDispatchConsumptionPreflightResult,
)
from app.domain.run import Run, RunStatus
from app.domain.task import Task, TaskEventReason, TaskHumanStatus, TaskStatus
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.budget_guard_service import BudgetGuardDecision, BudgetGuardService
from app.services.event_stream_service import event_stream_service
from app.services.project_director_protected_transition_dispatch_consumption_preflight_service import (
    ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService,
)
from app.services.task_readiness_service import TaskReadinessService
from app.services.task_router_service import TaskRouterService, TaskRoutingCandidate
from app.services.task_state_machine_service import TaskStateMachineService


P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL = (
    "p23_d1_protected_transition_dispatch_consumed"
)
P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_ACTION_TYPE = (
    "p23_d1_protected_transition_dispatch_consumption_record"
)
PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SCHEMA_VERSION = "p23-d1.v1"

_INTENT = "protected_transition_dispatch_consumption"
_PAGE_SIZE = 100


@dataclass(frozen=True, slots=True)
class ConsumedProjectDirectorProtectedTransitionDispatch:
    """D1 原子消费结果及其 append-only evidence message。"""

    result: ProjectDirectorProtectedTransitionDispatchConsumptionResult
    message: ProjectDirectorMessage | None


@dataclass(frozen=True, slots=True)
class RevalidatedPersistedProtectedTransitionDispatchConsumption:
    """Pure revalidation of one exact persisted D1 consumption."""

    result: ProjectDirectorProtectedTransitionDispatchConsumptionResult | None
    message: ProjectDirectorMessage | None
    task: Task | None
    run: Run | None
    blocked_reasons: list[str]


@dataclass(frozen=True, slots=True)
class _ConsumptionHistory:
    valid_consumptions: list[
        tuple[
            ProjectDirectorProtectedTransitionDispatchConsumptionResult,
            ProjectDirectorMessage,
        ]
    ]
    invalid_reasons: list[str]


class _AtomicConsumptionRollback(RuntimeError):
    """携带回滚后的 blocked 证据，强制退出 immediate transaction。"""

    def __init__(self, *, reasons: list[str], values: dict[str, Any]) -> None:
        self.reasons = reasons
        self.values = values
        super().__init__(", ".join(reasons))


class ProjectDirectorProtectedTransitionDispatchConsumptionService:
    """原子消费 exact P23-C preflight，并 claim Task、预留 Run。"""

    def __init__(
        self,
        *,
        session_repository: ProjectDirectorSessionRepository,
        message_repository: ProjectDirectorMessageRepository,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        preflight_service: ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService,
        task_readiness_service: TaskReadinessService,
        task_state_machine_service: TaskStateMachineService,
        task_router_service: TaskRouterService,
        budget_guard_service: BudgetGuardService,
    ) -> None:
        self._session_repository = session_repository
        self._message_repository = message_repository
        self._task_repository = task_repository
        self._run_repository = run_repository
        self._preflight_service = preflight_service
        self._task_readiness_service = task_readiness_service
        self._task_state_machine_service = task_state_machine_service
        self._task_router_service = task_router_service
        self._budget_guard_service = budget_guard_service

    def consume_protected_transition_dispatch_preflight(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
    ) -> ConsumedProjectDirectorProtectedTransitionDispatch:
        """在一个 immediate transaction 内完成 replay 或首次原子消费。"""

        try:
            with self._message_repository.sqlite_immediate_transaction():
                outcome = self._consume_protected_transition_dispatch_preflight(
                    session_id=session_id,
                    source_task_id=source_task_id,
                    source_message_id=source_message_id,
                )
        except _AtomicConsumptionRollback as exc:
            return self._blocked(
                source_message_id=source_message_id,
                reasons=[*exc.reasons, "atomic_consumption_rolled_back"],
                values=exc.values,
            )

        if (
            outcome.result.consumption_status == "reserved_for_worker_start"
            and not outcome.result.resumed_from_existing_consumption
        ):
            try:
                self._publish_committed_reservation(outcome.result)
            except Exception:
                # 提交后的 SSE 仅作尽力通知，失败不能推翻已提交的 D1 证据。
                pass

        return outcome

    def revalidate_persisted_protected_transition_dispatch_consumption(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_consumption_message_id: UUID,
    ) -> RevalidatedPersistedProtectedTransitionDispatchConsumption:
        """Revalidate immutable D1 evidence without opening a transaction or writing."""

        message = self._message_repository.get_by_id(source_consumption_message_id)
        if message is None:
            return RevalidatedPersistedProtectedTransitionDispatchConsumption(
                result=None,
                message=None,
                task=None,
                run=None,
                blocked_reasons=["source_consumption_missing"],
            )
        if message.session_id != session_id:
            return RevalidatedPersistedProtectedTransitionDispatchConsumption(
                result=None,
                message=message,
                task=None,
                run=None,
                blocked_reasons=["source_consumption_session_mismatch"],
            )
        if message.related_task_id != source_task_id:
            return RevalidatedPersistedProtectedTransitionDispatchConsumption(
                result=None,
                message=message,
                task=None,
                run=None,
                blocked_reasons=["source_consumption_task_mismatch"],
            )

        session_obj = self._session_repository.get_by_id(session_id)
        task = self._task_repository.get_by_id(source_task_id)
        project_id = session_obj.project_id if session_obj is not None else None
        if task is None:
            return RevalidatedPersistedProtectedTransitionDispatchConsumption(
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
            return RevalidatedPersistedProtectedTransitionDispatchConsumption(
                result=None,
                message=message,
                task=task,
                run=None,
                blocked_reasons=["source_consumption_project_mismatch"],
            )

        result = self._trusted_consumption(
            message=message,
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=project_id,
        )
        if result is None:
            return RevalidatedPersistedProtectedTransitionDispatchConsumption(
                result=None,
                message=message,
                task=task,
                run=None,
                blocked_reasons=["source_consumption_invalid"],
            )
        if result.consumption_status != "reserved_for_worker_start":
            return RevalidatedPersistedProtectedTransitionDispatchConsumption(
                result=result,
                message=message,
                task=task,
                run=None,
                blocked_reasons=["source_consumption_not_reserved"],
            )

        preflight_revalidation = self._preflight_service.revalidate_persisted_only_protected_transition_dispatch_consumption_preflight(
            session_id=session_id,
            source_task_id=source_task_id,
            source_preflight_message_id=result.source_preflight_message_id,
        )
        preflight = preflight_revalidation.result
        if preflight_revalidation.blocked_reasons or preflight is None:
            reasons = (
                ["source_evidence_chain_invalid"]
                if "source_evidence_chain_invalid"
                in preflight_revalidation.blocked_reasons
                else ["source_preflight_invalid"]
            )
            return RevalidatedPersistedProtectedTransitionDispatchConsumption(
                result=result,
                message=message,
                task=task,
                run=None,
                blocked_reasons=reasons,
            )
        exact_bindings = (
            (result.source_preflight_id, preflight.preflight_id),
            (result.source_preflight_fingerprint, preflight.preflight_fingerprint),
            (result.source_intent_message_id, preflight.source_intent_message_id),
            (result.source_dispatch_intent_id, preflight.source_dispatch_intent_id),
            (
                result.source_dispatch_intent_fingerprint,
                preflight.source_dispatch_intent_fingerprint,
            ),
            (result.source_p22_summary_message_id, preflight.source_p22_summary_message_id),
            (result.source_review_message_id, preflight.source_review_message_id),
            (result.source_freshness_message_id, preflight.source_freshness_message_id),
            (result.disposition_type, preflight.disposition_type),
            (result.dispatch_kind, preflight.dispatch_kind),
            (result.target_task_strategy, preflight.target_task_strategy),
            (result.review_result_fingerprint, preflight.review_result_fingerprint),
            (
                result.review_semantic_fingerprint,
                preflight.review_semantic_fingerprint,
            ),
            (result.current_freshness_fingerprint, preflight.current_freshness_fingerprint),
            (result.source_diff_sha256, preflight.current_diff_sha256),
            (result.review_scope_paths, preflight.current_scope_paths),
            (result.workspace_path, preflight.workspace_path),
            (result.workspace_path_within_root, preflight.workspace_path_within_root),
            (result.rework_attempt_index, preflight.rework_attempt_index),
            (result.rework_attempt_limit, preflight.rework_attempt_limit),
        )
        if any(left != right for left, right in exact_bindings):
            return RevalidatedPersistedProtectedTransitionDispatchConsumption(
                result=result,
                message=message,
                task=task,
                run=None,
                blocked_reasons=["source_evidence_chain_invalid"],
            )

        run = self._run_repository.get_by_id(result.run_id)
        if run is None:
            return RevalidatedPersistedProtectedTransitionDispatchConsumption(
                result=result,
                message=message,
                task=task,
                run=None,
                blocked_reasons=["reserved_run_missing"],
            )
        if run.task_id != source_task_id:
            return RevalidatedPersistedProtectedTransitionDispatchConsumption(
                result=result,
                message=message,
                task=task,
                run=run,
                blocked_reasons=["reserved_run_task_mismatch"],
            )

        history = self._scan_consumption_history(
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=project_id,
        )
        exact_matches = [
            item
            for item in history.valid_consumptions
            if item[1].id == source_consumption_message_id
            and item[0].source_preflight_message_id == result.source_preflight_message_id
            and item[0].source_intent_message_id == result.source_intent_message_id
        ]
        if history.invalid_reasons or len(exact_matches) != 1:
            return RevalidatedPersistedProtectedTransitionDispatchConsumption(
                result=result,
                message=message,
                task=task,
                run=None,
                blocked_reasons=["source_consumption_replay_conflict"],
            )

        return RevalidatedPersistedProtectedTransitionDispatchConsumption(
            result=result,
            message=message,
            task=task,
            run=run,
            blocked_reasons=[],
        )

    def _consume_protected_transition_dispatch_preflight(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
    ) -> ConsumedProjectDirectorProtectedTransitionDispatch:
        session_obj = self._session_repository.get_by_id(session_id)
        source_task = self._task_repository.get_by_id(source_task_id)
        project_id = session_obj.project_id if session_obj is not None else None
        base_values = self._base_values(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            project_id=project_id,
            source_task=source_task,
        )
        if source_task is None:
            return self._blocked(
                source_message_id=source_message_id,
                reasons=["source_task_missing"],
                values=base_values,
            )
        if (
            session_obj is None
            or project_id is None
            or source_task.project_id != project_id
        ):
            return self._blocked(
                source_message_id=source_message_id,
                reasons=["target_task_scope_mismatch"],
                values=base_values,
            )

        preflight_message = self._message_repository.get_by_id(source_message_id)
        incoming_intent_id = self._source_intent_id_from_preflight_message(
            preflight_message
        )
        history = self._scan_consumption_history(
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=project_id,
        )
        if history.invalid_reasons:
            return self._blocked(
                source_message_id=source_message_id,
                reasons=history.invalid_reasons,
                values=base_values,
            )

        exact_matches = [
            item
            for item in history.valid_consumptions
            if item[0].source_preflight_message_id == source_message_id
            and item[0].source_intent_message_id == incoming_intent_id
        ]
        preflight_conflicts = [
            item
            for item in history.valid_consumptions
            if item[0].source_preflight_message_id == source_message_id
            and item[0].source_intent_message_id != incoming_intent_id
        ]
        intent_conflicts = [
            item
            for item in history.valid_consumptions
            if incoming_intent_id is not None
            and item[0].source_intent_message_id == incoming_intent_id
            and item[0].source_preflight_message_id != source_message_id
        ]
        replay_reasons: list[str] = []
        if len(exact_matches) > 1:
            replay_reasons.append("dispatch_consumption_replay_conflict")
        if preflight_conflicts:
            replay_reasons.append(
                "source_preflight_already_consumed_by_different_record"
            )
        if intent_conflicts:
            replay_reasons.append(
                "source_intent_already_consumed_by_different_record"
            )
        if replay_reasons:
            return self._blocked(
                source_message_id=source_message_id,
                reasons=replay_reasons,
                values=base_values,
            )
        if len(exact_matches) == 1:
            existing, existing_message = exact_matches[0]
            replayed = ProjectDirectorProtectedTransitionDispatchConsumptionResult.model_validate(
                {
                    **existing.model_dump(),
                    "resumed_from_existing_consumption": True,
                }
            )
            return ConsumedProjectDirectorProtectedTransitionDispatch(
                result=replayed,
                message=existing_message,
            )

        preflight_revalidation = self._preflight_service.revalidate_persisted_protected_transition_dispatch_consumption_preflight(
            session_id=session_id,
            source_task_id=source_task_id,
            source_preflight_message_id=source_message_id,
        )
        if preflight_revalidation.blocked_reasons or preflight_revalidation.result is None:
            return self._blocked(
                source_message_id=source_message_id,
                reasons=(
                    preflight_revalidation.blocked_reasons
                    or ["source_preflight_invalid"]
                ),
                values=base_values,
            )
        preflight = preflight_revalidation.result
        values = self._values_from_preflight(
            base_values=base_values,
            preflight=preflight,
        )

        if source_task.human_status in {
            TaskHumanStatus.REQUESTED,
            TaskHumanStatus.IN_PROGRESS,
        } or source_task.paused_reason:
            return self._blocked(
                source_message_id=source_message_id,
                reasons=["human_escalation_required"],
                values=values,
            )
        if preflight.target_task_id != source_task_id:
            return self._blocked(
                source_message_id=source_message_id,
                reasons=["target_task_scope_mismatch"],
                values=values,
            )

        budget = self._budget_guard_service.evaluate_before_execution(
            source_task_id,
            project_id=project_id,
        )
        values.update(self._budget_values(budget))
        if not budget.allowed:
            reasons = ["budget_guard_blocked"]
            if budget.retry_status.retry_limit_reached:
                reasons.append("retry_limit_reached")
            return self._blocked(
                source_message_id=source_message_id,
                reasons=reasons,
                values=values,
            )

        original_task = source_task
        retry_applied = False
        retry_event_reason: str | None = None
        if source_task.status == TaskStatus.PENDING:
            readiness = self._task_readiness_service.evaluate_task(task=source_task)
            if not readiness.ready_for_execution:
                return self._blocked(
                    source_message_id=source_message_id,
                    reasons=["target_task_not_ready"],
                    values=values,
                )
        elif (
            preflight.dispatch_kind == "auto_rework"
            and source_task.status in {TaskStatus.FAILED, TaskStatus.BLOCKED}
        ):
            transition = self._task_state_machine_service.build_retry_transition(
                task=source_task
            )
            retry_event_reason = transition.event_reason.value
            try:
                source_task = self._task_repository.set_status(
                    source_task_id,
                    transition.status,
                )
            except Exception as exc:
                raise _AtomicConsumptionRollback(
                    reasons=["source_task_state_invalid"],
                    values=values,
                ) from exc
            retry_applied = True
            source_task = self._task_repository.get_by_id(source_task_id)
            if source_task is None:
                raise _AtomicConsumptionRollback(
                    reasons=["source_task_missing"],
                    values=values,
                )
            readiness = self._task_readiness_service.evaluate_task(task=source_task)
            if not readiness.ready_for_execution:
                raise _AtomicConsumptionRollback(
                    reasons=["target_task_not_ready"],
                    values=values,
                )
        else:
            return self._blocked(
                source_message_id=source_message_id,
                reasons=["source_task_state_invalid"],
                values=values,
            )

        try:
            routing = self._task_router_service.evaluate_exact_task_for_dispatch(
                task=source_task
            )
        except Exception as exc:
            if retry_applied:
                raise _AtomicConsumptionRollback(
                    reasons=["exact_task_routing_not_ready"],
                    values=values,
                ) from exc
            return self._blocked(
                source_message_id=source_message_id,
                reasons=["exact_task_routing_not_ready"],
                values=values,
            )
        if not routing.ready or not routing.readiness.ready_for_execution:
            if retry_applied:
                raise _AtomicConsumptionRollback(
                    reasons=["exact_task_routing_not_ready"],
                    values=values,
                )
            return self._blocked(
                source_message_id=source_message_id,
                reasons=["exact_task_routing_not_ready"],
                values=values,
            )

        try:
            self._task_state_machine_service.build_claim_transition(task=source_task)
        except Exception as exc:
            if retry_applied:
                raise _AtomicConsumptionRollback(
                    reasons=["source_task_state_invalid"],
                    values=values,
                ) from exc
            return self._blocked(
                source_message_id=source_message_id,
                reasons=["source_task_state_invalid"],
                values=values,
            )
        try:
            claimed_task = self._task_repository.claim_pending_task(source_task_id)
        except Exception as exc:
            raise _AtomicConsumptionRollback(
                reasons=["task_claim_conflict"],
                values=values,
            ) from exc
        if claimed_task is None:
            raise _AtomicConsumptionRollback(
                reasons=["task_claim_conflict"],
                values=values,
            )

        try:
            run = self._create_running_run(
                source_task_id=source_task_id,
                routing=routing,
            )
        except Exception as exc:
            raise _AtomicConsumptionRollback(
                reasons=["run_creation_failed"],
                values=values,
            ) from exc
        if run.task_id != source_task_id or run.status != RunStatus.RUNNING:
            raise _AtomicConsumptionRollback(
                reasons=["run_binding_invalid"],
                values=values,
            )

        try:
            consumption = self._reserved_result(
                values=values,
                original_task=original_task,
                claimed_task=claimed_task,
                run=run,
                routing=routing,
                retry_applied=retry_applied,
                retry_event_reason=retry_event_reason,
            )
            message = self._message_repository.create(
                self._consumption_message(result=consumption)
            )
        except Exception as exc:
            raise _AtomicConsumptionRollback(
                reasons=["dispatch_consumption_replay_conflict"],
                values=values,
            ) from exc
        return ConsumedProjectDirectorProtectedTransitionDispatch(
            result=consumption,
            message=message,
        )

    def _create_running_run(
        self,
        *,
        source_task_id: UUID,
        routing: TaskRoutingCandidate,
    ) -> Run:
        return self._run_repository.add_running_run_no_event(
            task_id=source_task_id,
            model_name=routing.model_name,
            route_reason=routing.route_reason,
            routing_score=routing.routing_score,
            routing_score_breakdown=list(routing.routing_score_breakdown),
            strategy_decision=routing.strategy_decision,
            owner_role_code=routing.owner_role_code,
            upstream_role_code=routing.upstream_role_code,
            downstream_role_code=routing.downstream_role_code,
            handoff_reason=routing.handoff_reason,
            dispatch_status=routing.dispatch_status,
        )

    def _publish_committed_reservation(
        self,
        result: ProjectDirectorProtectedTransitionDispatchConsumptionResult,
    ) -> None:
        task = self._task_repository.get_by_id(result.source_task_id)
        run = self._run_repository.get_by_id(result.run_id)
        if task is None or task.status != TaskStatus.RUNNING:
            raise ValueError("Committed source task is not running")
        if run is None or run.task_id != result.source_task_id:
            raise ValueError("Committed run binding is invalid")

        event_stream_service.publish_task_updated(
            task=task,
            reason=TaskEventReason.CLAIMED,
            previous_status=TaskStatus(result.task_status_before),
        )
        self._run_repository.publish_created(run)

    def _scan_consumption_history(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        project_id: UUID,
    ) -> _ConsumptionHistory:
        valid: list[
            tuple[
                ProjectDirectorProtectedTransitionDispatchConsumptionResult,
                ProjectDirectorMessage,
            ]
        ] = []
        invalid_reasons: list[str] = []
        for message in self._iter_session_messages(session_id):
            if message.source_detail != P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL:
                continue
            action = self._single_action(message)
            claims_task = bool(
                action is not None
                and action.get("source_task_id") == str(source_task_id)
            )
            if message.related_task_id != source_task_id and not claims_task:
                continue
            result = self._trusted_consumption(
                message=message,
                session_id=session_id,
                source_task_id=source_task_id,
                project_id=project_id,
            )
            if result is None:
                invalid_reasons.append("dispatch_consumption_replay_conflict")
                continue
            run = self._run_repository.get_by_id(result.run_id)
            if run is None or run.task_id != source_task_id:
                invalid_reasons.append("run_binding_invalid")
                continue
            valid.append((result, message))
        return _ConsumptionHistory(
            valid_consumptions=valid,
            invalid_reasons=self._dedupe(invalid_reasons),
        )

    def _trusted_consumption(
        self,
        *,
        message: ProjectDirectorMessage,
        session_id: UUID,
        source_task_id: UUID,
        project_id: UUID,
    ) -> ProjectDirectorProtectedTransitionDispatchConsumptionResult | None:
        if (
            message.session_id != session_id
            or message.related_project_id != project_id
            or message.related_task_id != source_task_id
            or message.role != ProjectDirectorMessageRole.ASSISTANT
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent != _INTENT
            or message.source_detail
            != P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL
            or message.requires_confirmation is not False
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
        ):
            return None
        action = self._single_action(message)
        if (
            action is None
            or action.get("type")
            != P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_ACTION_TYPE
            or action.get("schema_version")
            != PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SCHEMA_VERSION
            or action.get("session_id") != str(session_id)
            or action.get("source_task_id") != str(source_task_id)
        ):
            return None
        try:
            result = ProjectDirectorProtectedTransitionDispatchConsumptionResult.model_validate(
                {
                    field_name: action.get(field_name)
                    for field_name in ProjectDirectorProtectedTransitionDispatchConsumptionResult.model_fields
                }
            )
        except ValidationError:
            return None
        if (
            result.consumption_status != "reserved_for_worker_start"
            or result.consumption_id != message.id
            or result.project_id != project_id
            or result.created_at != message.created_at
            or result.resumed_from_existing_consumption
            or result.consumption_fingerprint != self._consumption_fingerprint(result)
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
        original_task: Task,
        claimed_task: Task,
        run: Run,
        routing: TaskRoutingCandidate,
        retry_applied: bool,
        retry_event_reason: str | None,
    ) -> ProjectDirectorProtectedTransitionDispatchConsumptionResult:
        consumption_id = uuid4()
        result_values = {
            **values,
            "task_status_before": original_task.status.value,
            "task_human_status_before": original_task.human_status.value,
            "retry_transition_applied": retry_applied,
            "retry_transition_event_reason": retry_event_reason,
            "task_status_after": claimed_task.status.value,
            "task_claimed_at": claimed_task.updated_at,
            "run_id": run.id,
            "run_status": run.status.value,
            "run_route_reason": run.route_reason,
            "run_routing_score": run.routing_score,
            "run_strategy_code": routing.strategy_code,
            "run_model_name": run.model_name,
            "run_dispatch_status": run.dispatch_status,
            "run_created_at": run.created_at,
            "replay_check_completed": True,
        }
        result = ProjectDirectorProtectedTransitionDispatchConsumptionResult(
            consumption_status="reserved_for_worker_start",
            consumption_id=consumption_id,
            consumption_fingerprint="0" * 64,
            dispatch_intent_consumed=True,
            task_status_mutated=True,
            task_claimed=True,
            run_created=True,
            **result_values,
        )
        return ProjectDirectorProtectedTransitionDispatchConsumptionResult.model_validate(
            {
                **result.model_dump(),
                "consumption_fingerprint": self._consumption_fingerprint(result),
            }
        )

    def _consumption_message(
        self,
        *,
        result: ProjectDirectorProtectedTransitionDispatchConsumptionResult,
    ) -> ProjectDirectorMessage:
        action = result.model_dump(mode="json")
        action.update(
            {
                "type": P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_ACTION_TYPE,
                "schema_version": PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SCHEMA_VERSION,
                "session_id": str(result.session_id),
                "source_task_id": str(result.source_task_id),
            }
        )
        return ProjectDirectorMessage(
            id=result.consumption_id,
            session_id=result.session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content=(
                "The protected-transition dispatch was atomically consumed. The "
                "exact source task was claimed and one running Run was reserved. "
                "No Worker or runtime was started. AUTO_CONTINUE or AUTO_REWORK "
                "execution has not started. No workspace or project file was "
                "written, no patch was applied, and no Git write was authorized."
            ),
            sequence_no=self._message_repository.get_next_sequence_no(
                session_id=result.session_id
            ),
            intent=_INTENT,
            related_project_id=result.project_id,
            related_task_id=result.source_task_id,
            source=ProjectDirectorMessageSource.SYSTEM,
            source_detail=P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL,
            suggested_actions=[action],
            requires_confirmation=False,
            risk_level=ProjectDirectorMessageRiskLevel.HIGH,
            forbidden_actions_detected=self._forbidden_actions(),
            created_at=result.created_at,
        )

    @staticmethod
    def _base_values(
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        project_id: UUID | None,
        source_task: Task | None,
    ) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "project_id": project_id,
            "source_task_id": source_task_id,
            "target_task_id": source_task_id if source_task is not None else None,
            "source_preflight_message_id": source_message_id,
            "task_status_before": source_task.status.value if source_task else None,
            "task_human_status_before": (
                source_task.human_status.value if source_task else None
            ),
            "replay_check_completed": True,
        }

    @staticmethod
    def _values_from_preflight(
        *,
        base_values: dict[str, Any],
        preflight: ProjectDirectorProtectedTransitionDispatchConsumptionPreflightResult,
    ) -> dict[str, Any]:
        return {
            **base_values,
            "source_preflight_id": preflight.preflight_id,
            "source_preflight_fingerprint": preflight.preflight_fingerprint,
            "source_intent_message_id": preflight.source_intent_message_id,
            "source_dispatch_intent_id": preflight.source_dispatch_intent_id,
            "source_dispatch_intent_fingerprint": (
                preflight.source_dispatch_intent_fingerprint
            ),
            "source_p22_summary_message_id": preflight.source_p22_summary_message_id,
            "source_review_message_id": preflight.source_review_message_id,
            "source_freshness_message_id": preflight.source_freshness_message_id,
            "disposition_type": preflight.disposition_type,
            "dispatch_kind": preflight.dispatch_kind,
            "target_task_strategy": preflight.target_task_strategy,
            "review_result_fingerprint": preflight.review_result_fingerprint,
            "review_semantic_fingerprint": preflight.review_semantic_fingerprint,
            "current_freshness_fingerprint": preflight.current_freshness_fingerprint,
            "source_diff_sha256": preflight.current_diff_sha256,
            "review_scope_paths": list(preflight.current_scope_paths),
            "workspace_path": preflight.workspace_path,
            "workspace_path_within_root": preflight.workspace_path_within_root,
            "rework_attempt_index": preflight.rework_attempt_index,
            "rework_attempt_limit": preflight.rework_attempt_limit,
        }

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
    def _blocked(
        *,
        source_message_id: UUID,
        reasons: list[str],
        values: dict[str, Any],
    ) -> ConsumedProjectDirectorProtectedTransitionDispatch:
        result = ProjectDirectorProtectedTransitionDispatchConsumptionResult(
            consumption_status="blocked",
            source_preflight_message_id=source_message_id,
            blocked_reasons=list(dict.fromkeys(reasons)),
            **{
                key: value
                for key, value in values.items()
                if key not in {
                    "source_preflight_message_id",
                    "task_status_after",
                    "task_claimed_at",
                    "run_id",
                    "run_status",
                    "run_route_reason",
                    "run_routing_score",
                    "run_strategy_code",
                    "run_model_name",
                    "run_dispatch_status",
                    "run_created_at",
                    "dispatch_intent_consumed",
                    "task_status_mutated",
                    "task_claimed",
                    "run_created",
                }
            },
        )
        return ConsumedProjectDirectorProtectedTransitionDispatch(
            result=result,
            message=None,
        )

    @staticmethod
    def _consumption_fingerprint(
        result: ProjectDirectorProtectedTransitionDispatchConsumptionResult,
    ) -> str:
        payload = {
            "schema_version": PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SCHEMA_VERSION,
            "session_id": str(result.session_id),
            "project_id": str(result.project_id),
            "source_task_id": str(result.source_task_id),
            "target_task_id": str(result.target_task_id),
            "source_preflight_message_id": str(result.source_preflight_message_id),
            "source_preflight_id": str(result.source_preflight_id),
            "source_preflight_fingerprint": result.source_preflight_fingerprint,
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
            "current_freshness_fingerprint": result.current_freshness_fingerprint,
            "source_diff_sha256": result.source_diff_sha256,
            "review_scope_paths": list(result.review_scope_paths),
            "workspace_path": result.workspace_path,
            "rework_attempt_index": result.rework_attempt_index,
            "rework_attempt_limit": result.rework_attempt_limit,
            "task_status_before": result.task_status_before,
            "retry_transition_applied": result.retry_transition_applied,
            "task_status_after": result.task_status_after,
            "run_id": str(result.run_id),
            "run_status": result.run_status,
            "run_route_reason": result.run_route_reason,
            "run_routing_score": result.run_routing_score,
            "run_strategy_code": result.run_strategy_code,
            "run_model_name": result.run_model_name,
            "run_dispatch_status": result.run_dispatch_status,
        }
        return ProjectDirectorProtectedTransitionDispatchConsumptionService._canonical_fingerprint(
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
    def _source_intent_id_from_preflight_message(
        message: ProjectDirectorMessage | None,
    ) -> UUID | None:
        if message is None:
            return None
        action = ProjectDirectorProtectedTransitionDispatchConsumptionService._single_action(
            message
        )
        if action is None:
            return None
        try:
            return UUID(str(action.get("source_intent_message_id")))
        except (TypeError, ValueError):
            return None

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
            "no_worker_start",
            "no_runtime_start",
            "no_continuation_execution_start",
            "no_rework_execution_start",
            "no_task_creation",
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
    "P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_ACTION_TYPE",
    "P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL",
    "PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SCHEMA_VERSION",
    "ConsumedProjectDirectorProtectedTransitionDispatch",
    "ProjectDirectorProtectedTransitionDispatchConsumptionService",
    "RevalidatedPersistedProtectedTransitionDispatchConsumption",
)
