"""Minimal task router for selecting the next runnable task."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.run import RunRoutingScoreItem, RunStatus
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
    routing_score_breakdown: list[RunRoutingScoreItem]
    execution_attempts: int
    recent_failure_count: int


@dataclass(slots=True, frozen=True)
class TaskRoutingDecision:
    """Selected task and the full evaluation summary."""

    selected_task: Task | None
    routing_score: float | None
    route_reason: str | None
    routing_score_breakdown: list[RunRoutingScoreItem]
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
                routing_score_breakdown=[],
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
                routing_score_breakdown=[],
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
            routing_score_breakdown=selected_candidate.routing_score_breakdown,
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
            routing_score_breakdown = [
                RunRoutingScoreItem(
                    code="readiness_gate",
                    label="就绪检查",
                    score=0.0,
                    detail=f"task blocked by: {blocking_text}",
                )
            ]
            return TaskRoutingCandidate(
                task=task,
                readiness=readiness,
                ready=False,
                routing_score=None,
                route_reason=self._build_route_reason(
                    ready=False,
                    routing_score=None,
                    score_breakdown=routing_score_breakdown,
                ),
                routing_score_breakdown=routing_score_breakdown,
                execution_attempts=execution_attempts,
                recent_failure_count=recent_failure_count,
            )

        priority_score = _PRIORITY_SCORES[task.priority]
        risk_adjustment = _RISK_ADJUSTMENTS[task.risk_level]
        human_adjustment = _HUMAN_STATUS_ADJUSTMENTS.get(task.human_status, 0.0)
        attempt_penalty = execution_attempts * _EXECUTION_ATTEMPT_PENALTY
        recent_failure_penalty = recent_failure_count * _RECENT_FAILURE_PENALTY

        routing_score_breakdown = [
            RunRoutingScoreItem(
                code="priority",
                label="优先级",
                score=priority_score,
                detail=(
                    f"priority={task.priority.value}; "
                    f"base score={priority_score:+.1f}"
                ),
            ),
            RunRoutingScoreItem(
                code="risk_level",
                label="风险等级",
                score=risk_adjustment,
                detail=(
                    f"risk={task.risk_level.value}; "
                    f"risk adjustment={risk_adjustment:+.1f}"
                ),
            ),
            RunRoutingScoreItem(
                code="human_status",
                label="人工状态",
                score=human_adjustment,
                detail=(
                    f"human_status={task.human_status.value}; "
                    f"status adjustment={human_adjustment:+.1f}"
                ),
            ),
            RunRoutingScoreItem(
                code="execution_attempts_penalty",
                label="执行次数惩罚",
                score=-attempt_penalty,
                detail=(
                    f"attempts={execution_attempts}; "
                    f"per attempt penalty={-_EXECUTION_ATTEMPT_PENALTY:.1f}"
                ),
            ),
            RunRoutingScoreItem(
                code="recent_failure_penalty",
                label="近期失败惩罚",
                score=-recent_failure_penalty,
                detail=(
                    f"recent_failures={recent_failure_count}; "
                    f"per failure penalty={-_RECENT_FAILURE_PENALTY:.1f}"
                ),
            ),
        ]
        routing_score = round(sum(item.score for item in routing_score_breakdown), 1)

        route_reason = self._build_route_reason(
            ready=True,
            routing_score=routing_score,
            score_breakdown=routing_score_breakdown,
        )
        return TaskRoutingCandidate(
            task=task,
            readiness=readiness,
            ready=True,
            routing_score=routing_score,
            route_reason=route_reason,
            routing_score_breakdown=routing_score_breakdown,
            execution_attempts=execution_attempts,
            recent_failure_count=recent_failure_count,
        )

    @staticmethod
    def _build_route_reason(
        *,
        ready: bool,
        routing_score: float | None,
        score_breakdown: list[RunRoutingScoreItem],
    ) -> str:
        """Build one stable and human-readable route summary."""

        parts = [f"{item.code}({item.score:+.1f})" for item in score_breakdown]
        readiness_text = "readiness=yes" if ready else "readiness=no"
        if routing_score is None:
            return f"{readiness_text}; " + ", ".join(parts)

        return (
            f"{readiness_text}; "
            + ", ".join(parts)
            + f"; total={routing_score:.1f}"
        )
