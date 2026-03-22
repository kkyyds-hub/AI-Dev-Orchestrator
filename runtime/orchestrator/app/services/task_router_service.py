"""Day 15 task router built on the strategy engine."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.project import ProjectStage
from app.domain.project_role import ProjectRoleCode
from app.domain.run import (
    RunBudgetPressureLevel,
    RunBudgetStrategyAction,
    RunRoutingScoreItem,
    RunStatus,
    RunStrategyDecision,
    RunStrategyReasonItem,
)
from app.domain.task import Task, TaskHumanStatus, TaskPriority, TaskRiskLevel
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.budget_guard_service import BudgetGuardService, BudgetSnapshot
from app.services.strategy_engine_service import ResolvedTaskStrategy, StrategyEngineService
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
    """One pending task evaluated by the Day 15 router."""

    task: Task
    readiness: TaskReadinessResult
    ready: bool
    routing_score: float | None
    route_reason: str
    routing_score_breakdown: list[RunRoutingScoreItem]
    execution_attempts: int
    recent_failure_count: int
    budget_pressure_level: RunBudgetPressureLevel
    budget_action: RunBudgetStrategyAction
    budget_strategy_code: str
    budget_score_adjustment: float
    project_stage: ProjectStage | None
    owner_role_code: ProjectRoleCode | None
    upstream_role_code: ProjectRoleCode | None
    downstream_role_code: ProjectRoleCode | None
    dispatch_status: str
    handoff_reason: str
    matched_terms: tuple[str, ...]
    model_name: str | None
    model_tier: str | None
    selected_skill_codes: tuple[str, ...]
    selected_skill_names: tuple[str, ...]
    strategy_code: str
    strategy_summary: str
    strategy_reasons: list[RunStrategyReasonItem]
    strategy_decision: RunStrategyDecision


@dataclass(slots=True, frozen=True)
class TaskRoutingDecision:
    """Selected task together with its explainable strategy context."""

    selected_task: Task | None
    routing_score: float | None
    route_reason: str | None
    routing_score_breakdown: list[RunRoutingScoreItem]
    candidates: list[TaskRoutingCandidate]
    message: str
    budget_pressure_level: RunBudgetPressureLevel
    budget_action: RunBudgetStrategyAction
    budget_strategy_code: str
    budget_strategy_summary: str
    project_stage: ProjectStage | None
    owner_role_code: ProjectRoleCode | None
    upstream_role_code: ProjectRoleCode | None
    downstream_role_code: ProjectRoleCode | None
    dispatch_status: str | None
    handoff_reason: str | None
    model_name: str | None
    model_tier: str | None
    selected_skill_codes: tuple[str, ...]
    selected_skill_names: tuple[str, ...]
    strategy_code: str | None
    strategy_summary: str | None
    strategy_reasons: list[RunStrategyReasonItem]
    strategy_decision: RunStrategyDecision | None


class TaskRouterService:
    """Pick the next runnable task using the centralized Day 15 strategy engine."""

    def __init__(
        self,
        *,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        task_readiness_service: TaskReadinessService,
        budget_guard_service: BudgetGuardService,
        strategy_engine_service: StrategyEngineService,
    ) -> None:
        self.task_repository = task_repository
        self.run_repository = run_repository
        self.task_readiness_service = task_readiness_service
        self.budget_guard_service = budget_guard_service
        self.strategy_engine_service = strategy_engine_service

    def route_next_task(self, project_id: UUID | None = None) -> TaskRoutingDecision:
        """Return the next task the worker should claim, optionally scoped to one project."""

        budget_snapshot = self.budget_guard_service.build_budget_snapshot()
        pending_tasks = self.task_repository.list_pending()
        if project_id is not None:
            pending_tasks = [task for task in pending_tasks if task.project_id == project_id]

        if not pending_tasks:
            return TaskRoutingDecision(
                selected_task=None,
                routing_score=None,
                route_reason=None,
                routing_score_breakdown=[],
                candidates=[],
                message="No pending tasks available for routing.",
                budget_pressure_level=budget_snapshot.pressure_level,
                budget_action=budget_snapshot.suggested_action,
                budget_strategy_code=budget_snapshot.strategy_code,
                budget_strategy_summary=budget_snapshot.strategy_summary,
                project_stage=None,
                owner_role_code=None,
                upstream_role_code=None,
                downstream_role_code=None,
                dispatch_status=None,
                handoff_reason=None,
                model_name=None,
                model_tier=None,
                selected_skill_codes=(),
                selected_skill_names=(),
                strategy_code=None,
                strategy_summary=None,
                strategy_reasons=[],
                strategy_decision=None,
            )

        candidates = [
            self._evaluate_task(task, budget_snapshot=budget_snapshot)
            for task in pending_tasks
        ]
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
                budget_pressure_level=budget_snapshot.pressure_level,
                budget_action=budget_snapshot.suggested_action,
                budget_strategy_code=budget_snapshot.strategy_code,
                budget_strategy_summary=budget_snapshot.strategy_summary,
                project_stage=None,
                owner_role_code=None,
                upstream_role_code=None,
                downstream_role_code=None,
                dispatch_status=None,
                handoff_reason=None,
                model_name=None,
                model_tier=None,
                selected_skill_codes=(),
                selected_skill_names=(),
                strategy_code=None,
                strategy_summary=None,
                strategy_reasons=[],
                strategy_decision=None,
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
                f"Router selected '{selected_candidate.task.title}' for "
                f"{self._role_label(selected_candidate.owner_role_code)} via "
                f"{selected_candidate.model_name or 'unassigned-model'} "
                f"with score {selected_candidate.routing_score:.1f}."
            ),
            budget_pressure_level=budget_snapshot.pressure_level,
            budget_action=budget_snapshot.suggested_action,
            budget_strategy_code=budget_snapshot.strategy_code,
            budget_strategy_summary=budget_snapshot.strategy_summary,
            project_stage=selected_candidate.project_stage,
            owner_role_code=selected_candidate.owner_role_code,
            upstream_role_code=selected_candidate.upstream_role_code,
            downstream_role_code=selected_candidate.downstream_role_code,
            dispatch_status=selected_candidate.dispatch_status,
            handoff_reason=selected_candidate.handoff_reason,
            model_name=selected_candidate.model_name,
            model_tier=selected_candidate.model_tier,
            selected_skill_codes=selected_candidate.selected_skill_codes,
            selected_skill_names=selected_candidate.selected_skill_names,
            strategy_code=selected_candidate.strategy_code,
            strategy_summary=selected_candidate.strategy_summary,
            strategy_reasons=selected_candidate.strategy_reasons,
            strategy_decision=selected_candidate.strategy_decision,
        )

    def _evaluate_task(
        self,
        task: Task,
        *,
        budget_snapshot: BudgetSnapshot,
    ) -> TaskRoutingCandidate:
        """Evaluate one pending task and explain the result."""

        readiness = self.task_readiness_service.evaluate_task(task=task)
        execution_attempts = self.run_repository.count_execution_attempts_by_task_id(task.id)
        recent_runs = self.run_repository.list_by_task_id(task.id)[:3]
        recent_failure_count = sum(1 for run in recent_runs if run.status in _FAILED_RUN_STATUSES)
        dependency_tasks = list(
            self.task_repository.get_by_ids(task.depends_on_task_ids).values()
        )
        strategy = self.strategy_engine_service.resolve_task_strategy(
            task=task,
            execution_attempts=execution_attempts,
            recent_failure_count=recent_failure_count,
            budget_snapshot=budget_snapshot,
            dependency_tasks=dependency_tasks,
        )

        if not readiness.ready_for_execution:
            blocking_text = " | ".join(readiness.blocking_reasons)
            routing_score_breakdown = [
                RunRoutingScoreItem(
                    code="readiness_gate",
                    label="就绪检查",
                    score=0.0,
                    detail=f"task blocked by: {blocking_text}",
                ),
                RunRoutingScoreItem(
                    code="role_responsibility_match",
                    label="角色职责匹配",
                    score=strategy.role_assignment.responsibility_score,
                    detail=(
                        f"dispatch={strategy.role_assignment.dispatch_status}; "
                        f"{strategy.role_assignment.handoff_reason}"
                    ),
                ),
                *strategy.routing_score_items,
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
                    strategy=strategy,
                ),
                routing_score_breakdown=routing_score_breakdown,
                execution_attempts=execution_attempts,
                recent_failure_count=recent_failure_count,
                budget_pressure_level=strategy.budget_directive.pressure_level,
                budget_action=strategy.budget_directive.suggested_action,
                budget_strategy_code=strategy.budget_directive.strategy_code,
                budget_score_adjustment=strategy.budget_directive.score_adjustment,
                project_stage=strategy.project_stage,
                owner_role_code=strategy.role_assignment.owner_role_code,
                upstream_role_code=strategy.role_assignment.upstream_role_code,
                downstream_role_code=strategy.role_assignment.downstream_role_code,
                dispatch_status=strategy.role_assignment.dispatch_status,
                handoff_reason=strategy.role_assignment.handoff_reason,
                matched_terms=strategy.role_assignment.matched_terms,
                model_name=strategy.model_profile.model_name,
                model_tier=strategy.model_tier,
                selected_skill_codes=strategy.selected_skill_codes,
                selected_skill_names=strategy.selected_skill_names,
                strategy_code=strategy.strategy_code,
                strategy_summary=strategy.strategy_summary,
                strategy_reasons=strategy.strategy_reasons,
                strategy_decision=strategy.strategy_decision,
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
                code="role_responsibility_match",
                label="角色职责匹配",
                score=strategy.role_assignment.responsibility_score,
                detail=(
                    f"dispatch={strategy.role_assignment.dispatch_status}; "
                    f"{strategy.role_assignment.handoff_reason}"
                ),
            ),
            *strategy.routing_score_items,
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
            RunRoutingScoreItem(
                code="budget_pressure_adjustment",
                label="预算压力调整",
                score=strategy.budget_directive.score_adjustment,
                detail=(
                    f"pressure={strategy.budget_directive.pressure_level.value}; "
                    f"action={strategy.budget_directive.suggested_action.value}; "
                    f"strategy={strategy.budget_directive.strategy_code}; "
                    f"preferred_model_tier={strategy.budget_directive.preferred_model_tier}; "
                    f"{strategy.budget_directive.detail}"
                ),
            ),
        ]
        routing_score = round(sum(item.score for item in routing_score_breakdown), 1)

        return TaskRoutingCandidate(
            task=task,
            readiness=readiness,
            ready=True,
            routing_score=routing_score,
            route_reason=self._build_route_reason(
                ready=True,
                routing_score=routing_score,
                score_breakdown=routing_score_breakdown,
                strategy=strategy,
            ),
            routing_score_breakdown=routing_score_breakdown,
            execution_attempts=execution_attempts,
            recent_failure_count=recent_failure_count,
            budget_pressure_level=strategy.budget_directive.pressure_level,
            budget_action=strategy.budget_directive.suggested_action,
            budget_strategy_code=strategy.budget_directive.strategy_code,
            budget_score_adjustment=strategy.budget_directive.score_adjustment,
            project_stage=strategy.project_stage,
            owner_role_code=strategy.role_assignment.owner_role_code,
            upstream_role_code=strategy.role_assignment.upstream_role_code,
            downstream_role_code=strategy.role_assignment.downstream_role_code,
            dispatch_status=strategy.role_assignment.dispatch_status,
            handoff_reason=strategy.role_assignment.handoff_reason,
            matched_terms=strategy.role_assignment.matched_terms,
            model_name=strategy.model_profile.model_name,
            model_tier=strategy.model_tier,
            selected_skill_codes=strategy.selected_skill_codes,
            selected_skill_names=strategy.selected_skill_names,
            strategy_code=strategy.strategy_code,
            strategy_summary=strategy.strategy_summary,
            strategy_reasons=strategy.strategy_reasons,
            strategy_decision=strategy.strategy_decision,
        )

    @classmethod
    def _build_route_reason(
        cls,
        *,
        ready: bool,
        routing_score: float | None,
        score_breakdown: list[RunRoutingScoreItem],
        strategy: ResolvedTaskStrategy,
    ) -> str:
        """Build one stable and human-readable route summary."""

        parts = [f"{item.code}({item.score:+.1f})" for item in score_breakdown]
        readiness_text = "readiness=yes" if ready else "readiness=no"
        budget_text = (
            f"budget={strategy.budget_directive.pressure_level.value}/"
            f"{strategy.budget_directive.suggested_action.value}"
            f"[{strategy.budget_directive.strategy_code}]"
        )
        role_text = (
            f"roles={cls._role_label(strategy.role_assignment.upstream_role_code)}"
            f"->{cls._role_label(strategy.role_assignment.owner_role_code)}"
        )
        if strategy.role_assignment.downstream_role_code is not None:
            role_text += (
                f"->{cls._role_label(strategy.role_assignment.downstream_role_code)}"
            )
        role_text += f"[{strategy.role_assignment.dispatch_status}]"
        stage_text = (
            f"stage={strategy.project_stage.value}"
            if strategy.project_stage is not None
            else "stage=unscoped"
        )
        skill_text = (
            ",".join(strategy.selected_skill_codes[:3])
            if strategy.selected_skill_codes
            else "none"
        )
        strategy_text = (
            f"strategy={strategy.strategy_code}; "
            f"model={strategy.model_profile.model_name}[{strategy.model_tier}]; "
            f"skills={skill_text}"
        )
        if routing_score is None:
            return (
                f"{readiness_text}; {budget_text}; {stage_text}; {role_text}; "
                f"{strategy_text}; " + ", ".join(parts)
            )

        return (
            f"{readiness_text}; {budget_text}; {stage_text}; {role_text}; "
            f"{strategy_text}; " + ", ".join(parts) + f"; total={routing_score:.1f}"
        )

    @staticmethod
    def _role_label(role_code: ProjectRoleCode | None) -> str:
        """Render one role code for route summaries."""

        return role_code.value if role_code is not None else "unassigned"
