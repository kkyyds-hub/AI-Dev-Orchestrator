"""Atomically close the P23 Task/Run lifecycle selected by a P25-I decision."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid5

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.domain._base import utc_now
from app.domain.project_director_bounded_rework_attempt_lifecycle_closure import (
    P25_BOUNDED_REWORK_ATTEMPT_LIFECYCLE_CLOSURE_NAMESPACE,
    ProjectDirectorBoundedReworkAttemptLifecycleClosure,
)
from app.domain.project_director_bounded_rework_convergence import (
    ProjectDirectorBoundedReworkConvergenceDecision,
)
from app.domain.project_director_message import ProjectDirectorMessage, ProjectDirectorMessageRiskLevel, ProjectDirectorMessageRole, ProjectDirectorMessageSource
from app.domain.run import RunFailureCategory, RunStatus
from app.domain.task import TaskStatus
from app.repositories.project_director_message_repository import ProjectDirectorMessageRepository
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.project_director_bounded_rework_convergence_service import ProjectDirectorBoundedReworkConvergenceService
from app.services.project_director_protected_transition_dispatch_consumption_service import ProjectDirectorProtectedTransitionDispatchConsumptionService
from app.services.task_state_machine_service import TaskStateMachineService


P25_BOUNDED_REWORK_ATTEMPT_LIFECYCLE_CLOSURE_SOURCE_DETAIL = "p25_i_attempt_lifecycle_closed"
P25_BOUNDED_REWORK_ATTEMPT_LIFECYCLE_CLOSURE_INTENT = "bounded_rework_attempt_lifecycle_closure"
P25_BOUNDED_REWORK_ATTEMPT_LIFECYCLE_CLOSURE_ACTION_TYPE = "p25_bounded_rework_attempt_lifecycle_closure_record"


@dataclass(frozen=True, slots=True)
class ClosedProjectDirectorBoundedReworkAttemptLifecycle:
    status: Literal["closure_persisted", "closure_replayed", "blocked", "recovery_required"]
    closure: ProjectDirectorBoundedReworkAttemptLifecycleClosure | None
    message: ProjectDirectorMessage | None
    task: object | None
    run: object | None
    blocked_reasons: tuple[str, ...] = ()


class ProjectDirectorBoundedReworkAttemptLifecycleClosureService:
    def __init__(self, *, message_repository: ProjectDirectorMessageRepository, task_repository: TaskRepository, run_repository: RunRepository, dispatch_consumption_service: ProjectDirectorProtectedTransitionDispatchConsumptionService, convergence_service: ProjectDirectorBoundedReworkConvergenceService) -> None:
        self._message_repository = message_repository
        self._task_repository = task_repository
        self._run_repository = run_repository
        self._dispatch_consumption_service = dispatch_consumption_service
        self._convergence_service = convergence_service
        if convergence_service._message_repository is not message_repository:
            raise ValueError("P25-I-D must share convergence evidence")

    def close_bounded_rework_attempt_lifecycle(self, *, session_id: UUID, source_task_id: UUID, source_convergence_decision_message_id: UUID) -> ClosedProjectDirectorBoundedReworkAttemptLifecycle:
        session = self._message_repository._session
        if session.in_transaction():
            return self._blocked("persistence_failed")
        try:
            with self._message_repository.sqlite_immediate_transaction():
                decision, decision_message = self._load_decision(
                    session_id=session_id, source_task_id=source_task_id,
                    source_convergence_decision_message_id=source_convergence_decision_message_id,
                )
                consumption_message_id = self._consumption_message_id(
                    session_id, decision.authority.source_p23_dispatch_consumption_id
                )
                consumption = self._dispatch_consumption_service.revalidate_persisted_protected_transition_dispatch_consumption(
                    session_id=session_id, source_task_id=source_task_id,
                    source_consumption_message_id=consumption_message_id,
                )
                if consumption.blocked_reasons or consumption.result is None or consumption.run is None:
                    raise ValueError("source P23 consumption is invalid")
                if consumption.result.run_id != decision.authority.source_run_id or consumption.run.id != decision.authority.source_run_id:
                    raise ValueError("source run does not match decision authority")
                task = self._task_repository.get_by_id(source_task_id)
                run = self._run_repository.get_by_id(consumption.run.id)
                if task is None or run is None or run.task_id != source_task_id:
                    raise ValueError("attempt identity is invalid")
                existing = self._find_closure(session_id, source_convergence_decision_message_id)
                if existing is not None:
                    closure, message = existing
                    if not self._matches_persisted_state(closure, task, run):
                        raise ValueError("persisted closure state diverged")
                    return ClosedProjectDirectorBoundedReworkAttemptLifecycle("closure_replayed", closure, message, task, run)
                if task.status != TaskStatus.RUNNING or run.status != RunStatus.RUNNING:
                    raise ValueError("attempt is not an exact running P23 lifecycle")
                task_after, run_status, failure_category, quality_gate, kind = self._close_state(task, decision)
                finished = self._run_repository.finish_run_no_event(
                    run.id, status=run_status, result_summary="P25 bounded attempt lifecycle closed.",
                    failure_category=failure_category, quality_gate_passed=quality_gate,
                )
                if kind == "terminal_human_escalation":
                    self._task_repository.set_status(source_task_id, TaskStatus.FAILED)
                    human = TaskStateMachineService().build_request_human_review_transition(task=self._task_repository.get_by_id(source_task_id))
                    persisted_task = self._task_repository.update_control_state(source_task_id, status=human.status, human_status=human.human_status)
                else:
                    persisted_task = self._task_repository.update_control_state(source_task_id, status=task_after.status, human_status=task_after.human_status)
                closure = self._build_closure(decision, decision_message, consumption_message_id, consumption, task, persisted_task, run, finished, kind, failure_category, quality_gate)
                message = self._message_repository.create(self._message(closure, task.project_id))
                return ClosedProjectDirectorBoundedReworkAttemptLifecycle("closure_persisted", closure, message, persisted_task, finished)
        except SQLAlchemyError:
            return self._blocked("persistence_failed", recovery=True)
        except (TypeError, ValueError, ValidationError):
            return self._blocked("history_invalid")

    def _load_decision(self, *, session_id: UUID, source_task_id: UUID, source_convergence_decision_message_id: UUID):
        message = self._message_repository.get_by_id(source_convergence_decision_message_id)
        if message is None or message.session_id != session_id or message.related_task_id != source_task_id or message.intent != "bounded_rework_convergence_decision":
            raise ValueError("decision missing")
        actions = message.suggested_actions
        if len(actions) != 1 or actions[0].get("type") != "p25_bounded_rework_convergence_decision_record":
            raise ValueError("decision action invalid")
        payload = dict(actions[0]); payload.pop("type", None)
        decision = ProjectDirectorBoundedReworkConvergenceDecision.model_validate(payload)
        if decision.authority.session_id != session_id or decision.authority.source_task_id != source_task_id:
            raise ValueError("decision authority invalid")
        return decision, message

    def _consumption_message_id(self, session_id: UUID, consumption_id: UUID) -> UUID:
        messages, _ = self._message_repository.list_by_session_id(
            session_id=session_id, limit=500
        )
        matches = [
            message.id
            for message in messages
            if message.intent == "protected_transition_dispatch_consumption"
            and len(message.suggested_actions) == 1
            and message.suggested_actions[0].get("consumption_id")
            == str(consumption_id)
        ]
        if len(matches) != 1:
            raise ValueError("source P23 consumption evidence is invalid")
        return matches[0]

    @staticmethod
    def _close_state(task, decision):
        machine = TaskStateMachineService()
        if decision.decision_type == "CONVERGED":
            resolution = machine.build_execution_resolution(task=task, execution_succeeded=True, verification_present=True, verification_succeeded=True, verification_quality_gate_passed=True, verification_failure_category=None)
            return resolution.task_transition, resolution.run_status, resolution.failure_category, resolution.quality_gate_passed, "converged_success"
        resolution = machine.build_execution_resolution(task=task, execution_succeeded=True, verification_present=True, verification_succeeded=False, verification_quality_gate_passed=False, verification_failure_category=RunFailureCategory.VERIFICATION_FAILED)
        kind = "retryable_verification_failure" if decision.decision_type == "NEXT_ATTEMPT_ELIGIBLE" else "terminal_human_escalation"
        return resolution.task_transition, resolution.run_status, resolution.failure_category, resolution.quality_gate_passed, kind

    def _build_closure(self, decision, decision_message, consumption_message_id, consumption, before_task, after_task, before_run, after_run, kind, failure_category, quality_gate):
        replay_key = ProjectDirectorBoundedReworkAttemptLifecycleClosure.compute_replay_key(decision_replay_key=decision.decision_replay_key, source_run_id=before_run.id)
        values = dict(
            closure_id=uuid5(P25_BOUNDED_REWORK_ATTEMPT_LIFECYCLE_CLOSURE_NAMESPACE, replay_key),
            closure_replay_key=replay_key, created_at=utc_now(),
            source_convergence_decision_message_id=decision_message.id, source_convergence_decision_id=decision.decision_id, source_convergence_decision_fingerprint=decision.decision_fingerprint, source_convergence_decision_replay_key=decision.decision_replay_key,
            source_p23_dispatch_consumption_message_id=consumption_message_id, source_p23_dispatch_consumption_id=consumption.result.consumption_id, source_p23_dispatch_consumption_fingerprint=decision.authority.source_p23_dispatch_consumption_fingerprint,
            source_package_id=decision.source_package_id, source_attempt_id=decision.source_attempt_id, source_executor_outcome_id=decision.source_executor_outcome_id, source_candidate_diff_message_id=decision.source_candidate_diff_message_id, source_review_outcome_message_id=decision.source_review_outcome_message_id, source_p22_summary_message_id=decision.source_p22_summary_message_id,
            source_task_id=before_task.id, source_run_id=before_run.id, current_rework_attempt_index=decision.current_rework_attempt_index, next_rework_attempt_index=decision.next_rework_attempt_index, decision_type=decision.decision_type, decision_reason=decision.decision_reason, closure_kind=kind,
            task_status_before=before_task.status, task_status_after=after_task.status, task_human_status_before=before_task.human_status, task_human_status_after=after_task.human_status, run_status_before=before_run.status, run_status_after=after_run.status, run_failure_category=failure_category, quality_gate_passed=quality_gate,
        )
        draft = ProjectDirectorBoundedReworkAttemptLifecycleClosure.model_construct(closure_fingerprint="0" * 64, **values)
        return ProjectDirectorBoundedReworkAttemptLifecycleClosure(closure_fingerprint=draft.compute_fingerprint(), **values)

    def _message(self, closure, project_id):
        return ProjectDirectorMessage(session_id=closure.source_task_id if False else self._message_repository.get_by_id(closure.source_convergence_decision_message_id).session_id, role=ProjectDirectorMessageRole.ASSISTANT, content="P25 attempt Task/Run lifecycle was closed from exact convergence authority.", sequence_no=self._message_repository.get_next_sequence_no(session_id=self._message_repository.get_by_id(closure.source_convergence_decision_message_id).session_id), intent=P25_BOUNDED_REWORK_ATTEMPT_LIFECYCLE_CLOSURE_INTENT, related_project_id=project_id, related_task_id=closure.source_task_id, source=ProjectDirectorMessageSource.SYSTEM, source_detail=P25_BOUNDED_REWORK_ATTEMPT_LIFECYCLE_CLOSURE_SOURCE_DETAIL, suggested_actions=[{"type": P25_BOUNDED_REWORK_ATTEMPT_LIFECYCLE_CLOSURE_ACTION_TYPE, **closure.model_dump(mode="json")}], requires_confirmation=False, risk_level=ProjectDirectorMessageRiskLevel.HIGH, forbidden_actions_detected=["product_runtime_git_write_allowed=false", "worker_started=false", "task_created=false", "run_created=false"])

    def _find_closure(self, session_id, decision_message_id):
        messages, _ = self._message_repository.list_by_session_id(session_id=session_id, limit=500)
        matches = []
        for message in messages:
            if message.intent != P25_BOUNDED_REWORK_ATTEMPT_LIFECYCLE_CLOSURE_INTENT or len(message.suggested_actions) != 1:
                continue
            action = message.suggested_actions[0]
            if action.get("type") != P25_BOUNDED_REWORK_ATTEMPT_LIFECYCLE_CLOSURE_ACTION_TYPE or action.get("source_convergence_decision_message_id") != str(decision_message_id):
                continue
            payload = dict(action); payload.pop("type", None)
            matches.append((ProjectDirectorBoundedReworkAttemptLifecycleClosure.model_validate(payload), message))
        if len(matches) > 1:
            raise ValueError("closure history conflict")
        return matches[0] if matches else None

    @staticmethod
    def _matches_persisted_state(closure, task, run):
        return task.status == closure.task_status_after and task.human_status == closure.task_human_status_after and run.status == closure.run_status_after and run.failure_category == closure.run_failure_category and run.quality_gate_passed == closure.quality_gate_passed

    @staticmethod
    def _blocked(reason, recovery=False):
        return ClosedProjectDirectorBoundedReworkAttemptLifecycle("recovery_required" if recovery else "blocked", None, None, None, None, (reason,))
