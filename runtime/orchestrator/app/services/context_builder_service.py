"""Build a minimal task-scoped execution context package before worker execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.run import RunFailureCategory, RunStatus
from app.domain.task import (
    Task,
    TaskHumanStatus,
    TaskPriority,
    TaskRiskLevel,
)
from app.repositories.run_repository import RunRepository
from app.services.task_readiness_service import (
    TaskBlockingSignal,
    TaskDependencyReadinessItem,
    TaskReadinessService,
)


_RECENT_RUN_LIMIT = 3
_CONTEXT_SUMMARY_MAX_LENGTH = 1_200


@dataclass(slots=True, frozen=True)
class ContextRecentRunItem:
    """A compact excerpt from one previous run of the same task."""

    run_id: UUID
    status: RunStatus
    result_summary: str | None
    verification_summary: str | None
    failure_category: RunFailureCategory | None
    created_at: datetime


@dataclass(slots=True, frozen=True)
class TaskContextPackage:
    """Minimal context package assembled right before execution."""

    task_id: UUID
    task_title: str
    input_summary: str
    acceptance_criteria: list[str]
    priority: TaskPriority
    risk_level: TaskRiskLevel
    human_status: TaskHumanStatus
    paused_reason: str | None
    ready_for_execution: bool
    blocking_signals: list[TaskBlockingSignal]
    blocking_reasons: list[str]
    dependency_items: list[TaskDependencyReadinessItem]
    recent_runs: list[ContextRecentRunItem]
    context_summary: str


class ContextBuilderService:
    """Assemble a conservative, task-scoped context package for execution."""

    def __init__(
        self,
        *,
        run_repository: RunRepository,
        task_readiness_service: TaskReadinessService,
    ) -> None:
        self.run_repository = run_repository
        self.task_readiness_service = task_readiness_service

    def build_context_package(self, *, task: Task) -> TaskContextPackage:
        """Build the minimal context package for one task."""

        readiness = self.task_readiness_service.evaluate_task(task=task)
        recent_runs = self._build_recent_run_items(task.id)
        context_summary = self._build_context_summary(
            task=task,
            dependency_items=readiness.dependency_items,
            recent_runs=recent_runs,
            blocking_reasons=readiness.blocking_reasons,
        )

        return TaskContextPackage(
            task_id=task.id,
            task_title=task.title,
            input_summary=task.input_summary,
            acceptance_criteria=task.acceptance_criteria,
            priority=task.priority,
            risk_level=task.risk_level,
            human_status=task.human_status,
            paused_reason=task.paused_reason,
            ready_for_execution=readiness.ready_for_execution,
            blocking_signals=readiness.blocking_signals,
            blocking_reasons=readiness.blocking_reasons,
            dependency_items=readiness.dependency_items,
            recent_runs=recent_runs,
            context_summary=context_summary,
        )

    def _build_recent_run_items(self, task_id: UUID) -> list[ContextRecentRunItem]:
        """Collect the latest few runs for the current task."""

        runs = self.run_repository.list_by_task_id(task_id)[:_RECENT_RUN_LIMIT]
        return [
            ContextRecentRunItem(
                run_id=run.id,
                status=run.status,
                result_summary=run.result_summary,
                verification_summary=run.verification_summary,
                failure_category=run.failure_category,
                created_at=run.created_at,
            )
            for run in runs
        ]

    def _build_context_summary(
        self,
        *,
        task: Task,
        dependency_items: list[TaskDependencyReadinessItem],
        recent_runs: list[ContextRecentRunItem],
        blocking_reasons: list[str],
    ) -> str:
        """Compress the structured context into one readable summary."""

        summary_parts = [
            f"Goal: {task.input_summary.strip()}",
            self._build_acceptance_summary(task.acceptance_criteria),
            self._build_dependency_summary(dependency_items),
            self._build_recent_run_summary(recent_runs),
            (
                f"Task posture: priority={task.priority.value}, risk={task.risk_level.value}, "
                f"human={task.human_status.value}."
            ),
        ]

        if blocking_reasons:
            summary_parts.append(
                "Blocking signals: " + " | ".join(reason.strip() for reason in blocking_reasons)
            )
        else:
            summary_parts.append("Blocking signals: none.")

        summary = "\n".join(summary_parts)
        if len(summary) <= _CONTEXT_SUMMARY_MAX_LENGTH:
            return summary

        return summary[: _CONTEXT_SUMMARY_MAX_LENGTH - 3].rstrip() + "..."

    @staticmethod
    def _build_acceptance_summary(acceptance_criteria: list[str]) -> str:
        """Format acceptance criteria into a single compact sentence."""

        if not acceptance_criteria:
            return "Acceptance criteria: not explicitly defined."

        bullet_text = "; ".join(acceptance_criteria[:3])
        if len(acceptance_criteria) > 3:
            bullet_text += f"; and {len(acceptance_criteria) - 3} more"
        return f"Acceptance criteria: {bullet_text}."

    @staticmethod
    def _build_dependency_summary(
        dependency_items: list[TaskDependencyReadinessItem],
    ) -> str:
        """Format dependency state into a compact summary."""

        if not dependency_items:
            return "Dependencies: none."

        summary_parts = [
            f"{dependency.title}({'missing' if dependency.missing else dependency.status.value})"
            for dependency in dependency_items
        ]
        return "Dependencies: " + ", ".join(summary_parts) + "."

    @staticmethod
    def _build_recent_run_summary(recent_runs: list[ContextRecentRunItem]) -> str:
        """Format recent run history into a compact summary."""

        if not recent_runs:
            return "Recent runs: none."

        summary_parts = [
            f"{run.status.value}"
            + (
                f"/{run.failure_category.value}"
                if run.failure_category is not None
                else ""
            )
            for run in recent_runs
        ]
        return "Recent runs: " + " -> ".join(summary_parts) + "."
