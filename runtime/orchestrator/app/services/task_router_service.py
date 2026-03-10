"""Minimal task router for selecting the next runnable task."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.run import RunStatus
from app.domain.task import Task, TaskHumanStatus, TaskPriority, TaskRiskLevel
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.task_readiness_service import TaskReadinessResult, TaskReadinessService


_PRIORITY_SCORES = {
    TaskPriority.LOW: 100.0,
    TaskPriority.NORMAL: 200.0,
    TaskPriority.HIGH: 300.0,
    TaskPriority.URGENT: 400.0,
}
_RISK_ADJUSTMENTS = {
    TaskRiskLevel.LOW: 20.0,
    TaskRiskLevel.NORMAL: 0.0,
    TaskRiskLevel.HIGH: -20.0,
}
_HUMAN_STATUS_ADJUSTMENTS = {
    TaskHumanStatus.NONE: 0.0,
    TaskHumanStatus.RESOLVED: 10.0,
}
_FAILED_RUN_STATUSES = {RunStatus.FAILED, RunStatus.CANCELLED}
_EXECUTION_ATTEMPT_PENALTY = 20.0
_RECENT_FAILURE_PENALTY = 35.0


@dataclass(slots=True, frozen=True)
class TaskRoutingCandidate:
    """One pending task evaluated by the router."""

    task: Task
    readiness: TaskReadinessResult
    ready: bool
    routing_score: float | None
    route_reason: str
    execution_attempts: int
    recent_failure_count: int


@dataclass(slots=True, frozen=True)
class TaskRoutingDecision:
    """Selected task and the full evaluation summary."""

    selected_task: Task | None
    routing_score: float | None
    route_reason: str | None
    candidates: list[TaskRoutingCandidate]
    message: str


class TaskRouterService:
    """Pick the next runnable task using conservative local heuristics."""

    def __init__(
        self,
        *,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        task_readiness_service: TaskReadinessService,
    ) -> None:
        self.task_repository = task_repository
        self.run_repository = run_repository
        self.task_readiness_service = task_readiness_service

    def route_next_task(self) -> TaskRoutingDecision:
        """Return the next task the worker should claim, if any."""

        pending_tasks = self.task_repository.list_pending()
        if not pending_tasks:
            return TaskRoutingDecision(
                selected_task=None,
                routing_score=None,
                route_reason=None,
                candidates=[],
                message="No pending tasks available for routing.",
            )

        candidates = [self._evaluate_task(task) for task in pending_tasks]
        ready_candidates = [candidate for candidate in candidates if candidate.ready]

        if not ready_candidates:
            blocked_summaries = [
                f"{candidate.task.title}: {candidate.route_reason}"
                for candidate in candidates[:3]
            ]
            blocked_text = " | ".join(blocked_summaries)
            return TaskRoutingDecision(
                selected_task=None,
                routing_score=None,
                route_reason=None,
                candidates=candidates,
                message=(
                    "Pending tasks exist, but none are currently routable. "
                    f"{blocked_text}"
                ),
            )

        ranked_candidates = sorted(
            ready_candidates,
            key=lambda candidate: (
                -(candidate.routing_score or 0.0),
                candidate.task.created_at,
                candidate.task.title.lower(),
            ),
        )
        selected_candidate = ranked_candidates[0]

        return TaskRoutingDecision(
            selected_task=selected_candidate.task,
            routing_score=selected_candidate.routing_score,
            route_reason=selected_candidate.route_reason,
            candidates=candidates,
            message=(
                f"Router selected '{selected_candidate.task.title}' with score "
                f"{selected_candidate.routing_score:.1f}."
            ),
        )

    def _evaluate_task(self, task: Task) -> TaskRoutingCandidate:
        """Evaluate one pending task and explain the result."""

        readiness = self.task_readiness_service.evaluate_task(task=task)
        execution_attempts = self.run_repository.count_execution_attempts_by_task_id(task.id)
        recent_runs = self.run_repository.list_by_task_id(task.id)[:3]
        recent_failure_count = sum(1 for run in recent_runs if run.status in _FAILED_RUN_STATUSES)

        if not readiness.ready_for_execution:
            blocking_text = " | ".join(readiness.blocking_reasons)
            return TaskRoutingCandidate(
                task=task,
                readiness=readiness,
                ready=False,
                routing_score=None,
                route_reason=f"Skipped because {blocking_text}",
                execution_attempts=execution_attempts,
                recent_failure_count=recent_failure_count,
            )

        priority_score = _PRIORITY_SCORES[task.priority]
        risk_adjustment = _RISK_ADJUSTMENTS[task.risk_level]
        human_adjustment = _HUMAN_STATUS_ADJUSTMENTS.get(task.human_status, 0.0)
        attempt_penalty = execution_attempts * _EXECUTION_ATTEMPT_PENALTY
        recent_failure_penalty = recent_failure_count * _RECENT_FAILURE_PENALTY
        routing_score = (
            priority_score
            + risk_adjustment
            + human_adjustment
            - attempt_penalty
            - recent_failure_penalty
        )

        route_reason = (
            f"priority={task.priority.value}(+{priority_score:.0f}), "
            f"risk={task.risk_level.value}({risk_adjustment:+.0f}), "
            f"human={task.human_status.value}({human_adjustment:+.0f}), "
            f"attempts={execution_attempts}(-{attempt_penalty:.0f}), "
            f"recent_failures={recent_failure_count}(-{recent_failure_penalty:.0f}), "
            f"readiness=yes => score={routing_score:.1f}"
        )
        return TaskRoutingCandidate(
            task=task,
            readiness=readiness,
            ready=True,
            routing_score=routing_score,
            route_reason=route_reason,
            execution_attempts=execution_attempts,
            recent_failure_count=recent_failure_count,
        )
