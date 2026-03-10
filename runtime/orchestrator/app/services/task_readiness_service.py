"""Shared task readiness evaluation for routing and context building."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.run import RunFailureCategory, RunStatus
from app.domain.task import (
    Task,
    TaskBlockingReasonCategory,
    TaskBlockingReasonCode,
    TaskHumanStatus,
    TaskStatus,
)
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository


@dataclass(slots=True, frozen=True)
class TaskDependencyReadinessItem:
    """A dependency snapshot used by readiness and context preview."""

    task_id: UUID
    title: str
    status: TaskStatus
    latest_run_status: RunStatus | None
    latest_run_summary: str | None
    latest_failure_category: RunFailureCategory | None
    missing: bool = False


@dataclass(slots=True, frozen=True)
class TaskBlockingSignal:
    """One standardized reason explaining why a task is not ready."""

    code: TaskBlockingReasonCode
    category: TaskBlockingReasonCategory
    message: str


@dataclass(slots=True, frozen=True)
class TaskReadinessResult:
    """Shared answer to whether one task can execute right now."""

    task_id: UUID
    ready_for_execution: bool
    blocking_signals: list[TaskBlockingSignal]
    blocking_reasons: list[str]
    dependency_items: list[TaskDependencyReadinessItem]


class TaskReadinessService:
    """Build a single readiness result reused by router and context preview."""

    def __init__(
        self,
        *,
        task_repository: TaskRepository,
        run_repository: RunRepository,
    ) -> None:
        self.task_repository = task_repository
        self.run_repository = run_repository

    def evaluate_task(self, *, task: Task) -> TaskReadinessResult:
        """Return whether one task is ready for execution plus why not."""

        dependency_items = self._build_dependency_items(task.depends_on_task_ids)
        blocking_signals = self._build_blocking_signals(
            task=task,
            dependency_items=dependency_items,
        )
        return TaskReadinessResult(
            task_id=task.id,
            ready_for_execution=not blocking_signals,
            blocking_signals=blocking_signals,
            blocking_reasons=[signal.message for signal in blocking_signals],
            dependency_items=dependency_items,
        )

    def _build_dependency_items(
        self,
        dependency_ids: list[UUID],
    ) -> list[TaskDependencyReadinessItem]:
        """Collect current dependency states in original order."""

        if not dependency_ids:
            return []

        dependency_map = self.task_repository.get_by_ids(dependency_ids)
        dependency_items: list[TaskDependencyReadinessItem] = []
        for dependency_id in dependency_ids:
            dependency_task = dependency_map.get(dependency_id)
            if dependency_task is None:
                dependency_items.append(
                    TaskDependencyReadinessItem(
                        task_id=dependency_id,
                        title="Missing dependency task",
                        status=TaskStatus.BLOCKED,
                        latest_run_status=None,
                        latest_run_summary=None,
                        latest_failure_category=None,
                        missing=True,
                    )
                )
                continue

            dependency_runs = self.run_repository.list_by_task_id(dependency_id)
            latest_run = dependency_runs[0] if dependency_runs else None
            dependency_items.append(
                TaskDependencyReadinessItem(
                    task_id=dependency_task.id,
                    title=dependency_task.title,
                    status=dependency_task.status,
                    latest_run_status=latest_run.status if latest_run else None,
                    latest_run_summary=latest_run.result_summary if latest_run else None,
                    latest_failure_category=(
                        latest_run.failure_category if latest_run else None
                    ),
                )
            )

        return dependency_items

    @staticmethod
    def _build_blocking_signals(
        *,
        task: Task,
        dependency_items: list[TaskDependencyReadinessItem],
    ) -> list[TaskBlockingSignal]:
        """Return standardized blocking signals for one task."""

        signals: list[TaskBlockingSignal] = []

        for dependency in dependency_items:
            if dependency.missing:
                signals.append(
                    TaskBlockingSignal(
                        code=TaskBlockingReasonCode.DEPENDENCY_MISSING,
                        category=TaskBlockingReasonCategory.DEPENDENCY,
                        message=(
                            f"Dependency '{dependency.task_id}' is missing and must be recreated."
                        ),
                    )
                )
                continue

            if dependency.status != TaskStatus.COMPLETED:
                signals.append(
                    TaskBlockingSignal(
                        code=TaskBlockingReasonCode.DEPENDENCY_INCOMPLETE,
                        category=TaskBlockingReasonCategory.DEPENDENCY,
                        message=(
                            f"Dependency '{dependency.title}' is still {dependency.status.value}."
                        ),
                    )
                )

        signals.extend(TaskReadinessService._build_status_signals(task=task))

        if task.human_status == TaskHumanStatus.REQUESTED:
            signals.append(
                TaskBlockingSignal(
                    code=TaskBlockingReasonCode.HUMAN_REVIEW_REQUESTED,
                    category=TaskBlockingReasonCategory.HUMAN,
                    message="Human review was requested and must be resolved before execution.",
                )
            )
        elif task.human_status == TaskHumanStatus.IN_PROGRESS:
            signals.append(
                TaskBlockingSignal(
                    code=TaskBlockingReasonCode.HUMAN_REVIEW_IN_PROGRESS,
                    category=TaskBlockingReasonCategory.HUMAN,
                    message="Human review is currently in progress.",
                )
            )

        if task.paused_reason:
            signals.append(
                TaskBlockingSignal(
                    code=TaskBlockingReasonCode.PAUSE_NOTE_PRESENT,
                    category=TaskBlockingReasonCategory.PAUSE,
                    message=f"Task carries a pause note: {task.paused_reason}",
                )
            )

        return signals

    @staticmethod
    def _build_status_signals(task: Task) -> list[TaskBlockingSignal]:
        """Normalize task-status blocking rules into stable signals."""

        if task.status == TaskStatus.PENDING:
            return []

        if task.status == TaskStatus.PAUSED:
            return [
                TaskBlockingSignal(
                    code=TaskBlockingReasonCode.TASK_PAUSED,
                    category=TaskBlockingReasonCategory.PAUSE,
                    message="Task is explicitly paused.",
                )
            ]

        if task.status == TaskStatus.WAITING_HUMAN:
            return [
                TaskBlockingSignal(
                    code=TaskBlockingReasonCode.TASK_WAITING_HUMAN,
                    category=TaskBlockingReasonCategory.HUMAN,
                    message="Task is explicitly waiting for human review.",
                )
            ]

        return [
            TaskBlockingSignal(
                code=TaskBlockingReasonCode.TASK_NOT_PENDING,
                category=TaskBlockingReasonCategory.STATUS,
                message=TaskReadinessService._build_not_pending_message(task.status),
            )
        ]

    @staticmethod
    def _build_not_pending_message(status: TaskStatus) -> str:
        """Return a stable non-pending message for non-routable statuses."""

        if status == TaskStatus.RUNNING:
            return "Task is already running."
        if status == TaskStatus.COMPLETED:
            return "Task is already completed."
        if status == TaskStatus.FAILED:
            return "Task is failed; explicit retry or human action is required."
        if status == TaskStatus.BLOCKED:
            return "Task is blocked; explicit retry or human action is required."

        return f"Task status is {status.value} and cannot enter execution."
