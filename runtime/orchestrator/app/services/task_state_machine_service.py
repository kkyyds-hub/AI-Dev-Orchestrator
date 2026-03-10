"""Centralized task and run transition rules for V2-A."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.run import RunFailureCategory, RunStatus
from app.domain.task import Task, TaskEventReason, TaskHumanStatus, TaskStatus


@dataclass(slots=True, frozen=True)
class TaskStateTransition:
    """A validated task transition ready to be persisted."""

    status: TaskStatus
    event_reason: TaskEventReason
    message: str
    human_status: TaskHumanStatus | None = None
    update_human_status: bool = False
    paused_reason: str | None = None
    update_paused_reason: bool = False


@dataclass(slots=True, frozen=True)
class TaskRunStateResolution:
    """A validated task/run outcome after worker-side processing."""

    task_transition: TaskStateTransition
    run_status: RunStatus
    failure_category: RunFailureCategory | None
    quality_gate_passed: bool


class TaskStateTransitionError(ValueError):
    """Raised when one task transition violates the frozen Day 1 matrix."""

    def __init__(
        self,
        *,
        action: str,
        current_status: TaskStatus,
        allowed_statuses: tuple[TaskStatus, ...],
        detail: str,
    ) -> None:
        self.action = action
        self.current_status = current_status
        self.allowed_statuses = allowed_statuses
        super().__init__(detail)


class TaskStateMachineService:
    """Validate and normalize task/run state transitions."""

    def derive_initial_status(
        self,
        *,
        human_status: TaskHumanStatus,
        paused_reason: str | None,
    ) -> TaskStatus:
        """Derive the persisted task status from control metadata."""

        if human_status in {
            TaskHumanStatus.REQUESTED,
            TaskHumanStatus.IN_PROGRESS,
        }:
            return TaskStatus.WAITING_HUMAN

        if paused_reason:
            return TaskStatus.PAUSED

        return TaskStatus.PENDING

    def build_retry_transition(self, *, task: Task) -> TaskStateTransition:
        """Return the retry transition for one failed or blocked task."""

        self._ensure_allowed(
            task=task,
            action="retry",
            allowed_statuses=(TaskStatus.FAILED, TaskStatus.BLOCKED),
            detail="Only tasks in status 'failed' or 'blocked' can be retried.",
        )
        return TaskStateTransition(
            status=TaskStatus.PENDING,
            event_reason=TaskEventReason.RETRIED,
            message="Task was reset to pending for another worker attempt.",
        )

    def build_pause_transition(
        self,
        *,
        task: Task,
        reason: str | None,
    ) -> TaskStateTransition:
        """Return the explicit pause transition for one task."""

        self._ensure_allowed(
            task=task,
            action="pause",
            allowed_statuses=(TaskStatus.PENDING, TaskStatus.FAILED, TaskStatus.BLOCKED),
            detail=(
                "Only tasks in status 'pending', 'failed' or 'blocked' can be paused."
            ),
        )
        return TaskStateTransition(
            status=TaskStatus.PAUSED,
            paused_reason=reason or "Paused from console.",
            update_paused_reason=True,
            event_reason=TaskEventReason.PAUSED,
            message="Task was paused and removed from the runnable queue.",
        )

    def build_resume_transition(self, *, task: Task) -> TaskStateTransition:
        """Return the resume transition for one paused task."""

        self._ensure_allowed(
            task=task,
            action="resume",
            allowed_statuses=(TaskStatus.PAUSED,),
            detail="Only tasks in status 'paused' can be resumed.",
        )
        next_status = self.derive_initial_status(
            human_status=task.human_status,
            paused_reason=None,
        )
        message = "Task was resumed and returned to normal routing."
        if next_status == TaskStatus.WAITING_HUMAN:
            message = "Task was resumed, but it still requires human review."

        return TaskStateTransition(
            status=next_status,
            paused_reason=None,
            update_paused_reason=True,
            event_reason=TaskEventReason.RESUMED,
            message=message,
        )

    def build_request_human_review_transition(self, *, task: Task) -> TaskStateTransition:
        """Return the explicit waiting-human transition for one task."""

        self._ensure_allowed(
            task=task,
            action="request_human_review",
            allowed_statuses=(
                TaskStatus.PENDING,
                TaskStatus.FAILED,
                TaskStatus.BLOCKED,
                TaskStatus.PAUSED,
            ),
            detail=(
                "Only tasks in status 'pending', 'failed', 'blocked' or 'paused' "
                "can request human review."
            ),
        )
        next_human_status = (
            TaskHumanStatus.IN_PROGRESS
            if task.human_status == TaskHumanStatus.IN_PROGRESS
            else TaskHumanStatus.REQUESTED
        )
        return TaskStateTransition(
            status=TaskStatus.WAITING_HUMAN,
            human_status=next_human_status,
            update_human_status=True,
            paused_reason=None,
            update_paused_reason=True,
            event_reason=TaskEventReason.WAITING_HUMAN,
            message="Task is now waiting for human review before it can run again.",
        )

    def build_resolve_human_review_transition(self, *, task: Task) -> TaskStateTransition:
        """Return the resolved-human transition for one waiting task."""

        self._ensure_allowed(
            task=task,
            action="resolve_human_review",
            allowed_statuses=(TaskStatus.WAITING_HUMAN,),
            detail=(
                "Only tasks in status 'waiting_human' can be resolved back to pending."
            ),
        )
        return TaskStateTransition(
            status=TaskStatus.PENDING,
            human_status=TaskHumanStatus.RESOLVED,
            update_human_status=True,
            event_reason=TaskEventReason.HUMAN_RESOLVED,
            message="Human review was resolved. The task can be routed again.",
        )

    def build_claim_transition(self, *, task: Task) -> TaskStateTransition:
        """Return the worker claim transition for one pending task."""

        self._ensure_allowed(
            task=task,
            action="claim",
            allowed_statuses=(TaskStatus.PENDING,),
            detail="Only tasks in status 'pending' can be claimed for execution.",
        )
        return TaskStateTransition(
            status=TaskStatus.RUNNING,
            event_reason=TaskEventReason.CLAIMED,
            message="Task was claimed for execution.",
        )

    def build_guard_blocked_resolution(
        self,
        *,
        task: Task,
        failure_category: RunFailureCategory | None,
    ) -> TaskRunStateResolution:
        """Return the blocked task/run outcome for a guard rejection."""

        self._ensure_allowed(
            task=task,
            action="guard_block",
            allowed_statuses=(TaskStatus.RUNNING,),
            detail="Only tasks in status 'running' can be blocked by the guard.",
        )
        return TaskRunStateResolution(
            task_transition=TaskStateTransition(
                status=TaskStatus.BLOCKED,
                event_reason=TaskEventReason.GUARD_BLOCKED,
                message="Budget or retry guard blocked execution.",
            ),
            run_status=RunStatus.CANCELLED,
            failure_category=failure_category,
            quality_gate_passed=False,
        )

    def build_execution_resolution(
        self,
        *,
        task: Task,
        execution_succeeded: bool,
        verification_present: bool,
        verification_succeeded: bool,
        verification_quality_gate_passed: bool,
        verification_failure_category: RunFailureCategory | None,
    ) -> TaskRunStateResolution:
        """Return the finalized task/run outcome after execution."""

        self._ensure_allowed(
            task=task,
            action="finalize_execution",
            allowed_statuses=(TaskStatus.RUNNING,),
            detail="Only tasks in status 'running' can be finalized.",
        )

        if not execution_succeeded:
            return TaskRunStateResolution(
                task_transition=TaskStateTransition(
                    status=TaskStatus.FAILED,
                    event_reason=TaskEventReason.FINALIZED,
                    message="Task execution failed and the task was marked as failed.",
                ),
                run_status=RunStatus.FAILED,
                failure_category=RunFailureCategory.EXECUTION_FAILED,
                quality_gate_passed=False,
            )

        if not verification_present:
            return TaskRunStateResolution(
                task_transition=TaskStateTransition(
                    status=TaskStatus.COMPLETED,
                    event_reason=TaskEventReason.FINALIZED,
                    message="Task execution succeeded and no verification was required.",
                ),
                run_status=RunStatus.SUCCEEDED,
                failure_category=None,
                quality_gate_passed=True,
            )

        if verification_succeeded and verification_quality_gate_passed:
            return TaskRunStateResolution(
                task_transition=TaskStateTransition(
                    status=TaskStatus.COMPLETED,
                    event_reason=TaskEventReason.FINALIZED,
                    message="Task execution and verification both passed.",
                ),
                run_status=RunStatus.SUCCEEDED,
                failure_category=None,
                quality_gate_passed=True,
            )

        return TaskRunStateResolution(
            task_transition=TaskStateTransition(
                status=TaskStatus.FAILED,
                event_reason=TaskEventReason.FINALIZED,
                message="Task verification failed and the task was marked as failed.",
            ),
            run_status=RunStatus.FAILED,
            failure_category=(
                verification_failure_category or RunFailureCategory.VERIFICATION_FAILED
            ),
            quality_gate_passed=False,
        )

    @staticmethod
    def _ensure_allowed(
        *,
        task: Task,
        action: str,
        allowed_statuses: tuple[TaskStatus, ...],
        detail: str,
    ) -> None:
        """Raise one stable error when the transition is illegal."""

        if task.status in allowed_statuses:
            return

        raise TaskStateTransitionError(
            action=action,
            current_status=task.status,
            allowed_statuses=allowed_statuses,
            detail=detail,
        )
