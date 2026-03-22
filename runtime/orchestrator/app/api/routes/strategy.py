"""Day 15 strategy preview and rule-edit endpoints."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain.project import Project
from app.domain.project_role import ProjectRoleCode
from app.domain.run import (
    RunBudgetPressureLevel,
    RunBudgetStrategyAction,
    RunRoutingScoreItem,
    RunStrategyReasonItem,
)
from app.repositories.project_repository import ProjectRepository
from app.repositories.project_role_repository import ProjectRoleRepository
from app.repositories.run_repository import RunRepository
from app.repositories.skill_repository import SkillRepository
from app.repositories.task_repository import TaskRepository
from app.services.budget_guard_service import BudgetGuardService
from app.services.role_catalog_service import RoleCatalogService
from app.services.skill_registry_service import SkillRegistryService
from app.services.strategy_engine_service import (
    StrategyEngineService,
    StrategyRuleSetSnapshot,
)
from app.services.task_readiness_service import TaskReadinessService
from app.services.task_router_service import TaskRouterService, TaskRoutingCandidate, TaskRoutingDecision


class StrategyRoutingScoreItemResponse(BaseModel):
    """One routing score component returned by the strategy preview API."""

    code: str
    label: str
    score: float
    detail: str

    @classmethod
    def from_item(
        cls,
        item: RunRoutingScoreItem,
    ) -> "StrategyRoutingScoreItemResponse":
        """Convert one routing-score item into an API DTO."""

        return cls(
            code=item.code,
            label=item.label,
            score=item.score,
            detail=item.detail,
        )


class StrategyReasonItemResponse(BaseModel):
    """One explainable Day 15 strategy reason returned to the UI."""

    code: str
    label: str
    detail: str
    score: float | None = None

    @classmethod
    def from_item(
        cls,
        item: RunStrategyReasonItem,
    ) -> "StrategyReasonItemResponse":
        """Convert one strategy reason into an API DTO."""

        return cls(
            code=item.code,
            label=item.label,
            detail=item.detail,
            score=item.score,
        )


class StrategyCandidateResponse(BaseModel):
    """One candidate row returned under the project strategy preview."""

    task_id: UUID
    title: str
    ready: bool
    routing_score: float | None = None
    route_reason: str
    project_stage: str | None = None
    owner_role_code: ProjectRoleCode | None = None
    upstream_role_code: ProjectRoleCode | None = None
    downstream_role_code: ProjectRoleCode | None = None
    dispatch_status: str
    handoff_reason: str
    matched_terms: list[str] = Field(default_factory=list)
    model_name: str | None = None
    model_tier: str | None = None
    selected_skill_codes: list[str] = Field(default_factory=list)
    selected_skill_names: list[str] = Field(default_factory=list)
    strategy_code: str
    strategy_summary: str
    strategy_reasons: list[StrategyReasonItemResponse] = Field(default_factory=list)
    routing_score_breakdown: list[StrategyRoutingScoreItemResponse] = Field(default_factory=list)
    execution_attempts: int
    recent_failure_count: int
    budget_pressure_level: RunBudgetPressureLevel
    budget_action: RunBudgetStrategyAction
    budget_strategy_code: str
    budget_score_adjustment: float
    blocking_signals: list[dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def from_candidate(
        cls,
        candidate: TaskRoutingCandidate,
    ) -> "StrategyCandidateResponse":
        """Convert one routing candidate into an API DTO."""

        return cls(
            task_id=candidate.task.id,
            title=candidate.task.title,
            ready=candidate.ready,
            routing_score=candidate.routing_score,
            route_reason=candidate.route_reason,
            project_stage=(
                candidate.project_stage.value if candidate.project_stage is not None else None
            ),
            owner_role_code=candidate.owner_role_code,
            upstream_role_code=candidate.upstream_role_code,
            downstream_role_code=candidate.downstream_role_code,
            dispatch_status=candidate.dispatch_status,
            handoff_reason=candidate.handoff_reason,
            matched_terms=list(candidate.matched_terms),
            model_name=candidate.model_name,
            model_tier=candidate.model_tier,
            selected_skill_codes=list(candidate.selected_skill_codes),
            selected_skill_names=list(candidate.selected_skill_names),
            strategy_code=candidate.strategy_code,
            strategy_summary=candidate.strategy_summary,
            strategy_reasons=[
                StrategyReasonItemResponse.from_item(item)
                for item in candidate.strategy_reasons
            ],
            routing_score_breakdown=[
                StrategyRoutingScoreItemResponse.from_item(item)
                for item in candidate.routing_score_breakdown
            ],
            execution_attempts=candidate.execution_attempts,
            recent_failure_count=candidate.recent_failure_count,
            budget_pressure_level=candidate.budget_pressure_level,
            budget_action=candidate.budget_action,
            budget_strategy_code=candidate.budget_strategy_code,
            budget_score_adjustment=candidate.budget_score_adjustment,
            blocking_signals=[
                {
                    "code": signal.code.value,
                    "category": signal.category.value,
                    "message": signal.message,
                }
                for signal in candidate.readiness.blocking_signals
            ],
        )


class ProjectStrategyPreviewResponse(BaseModel):
    """Project-scoped Day 15 strategy preview returned to the UI."""

    project_id: UUID
    project_name: str
    project_stage: str
    selected_task_id: UUID | None = None
    selected_task_title: str | None = None
    message: str
    budget_pressure_level: RunBudgetPressureLevel
    budget_action: RunBudgetStrategyAction
    budget_strategy_code: str
    budget_strategy_summary: str
    owner_role_code: ProjectRoleCode | None = None
    upstream_role_code: ProjectRoleCode | None = None
    downstream_role_code: ProjectRoleCode | None = None
    dispatch_status: str | None = None
    handoff_reason: str | None = None
    model_name: str | None = None
    model_tier: str | None = None
    selected_skill_codes: list[str] = Field(default_factory=list)
    selected_skill_names: list[str] = Field(default_factory=list)
    strategy_code: str | None = None
    strategy_summary: str | None = None
    strategy_reasons: list[StrategyReasonItemResponse] = Field(default_factory=list)
    routing_score: float | None = None
    route_reason: str | None = None
    routing_score_breakdown: list[StrategyRoutingScoreItemResponse] = Field(default_factory=list)
    candidates: list[StrategyCandidateResponse] = Field(default_factory=list)

    @classmethod
    def from_decision(
        cls,
        *,
        project: Project,
        decision: TaskRoutingDecision,
    ) -> "ProjectStrategyPreviewResponse":
        """Convert one project-scoped routing decision into a preview DTO."""

        return cls(
            project_id=project.id,
            project_name=project.name,
            project_stage=project.stage.value,
            selected_task_id=decision.selected_task.id if decision.selected_task else None,
            selected_task_title=decision.selected_task.title if decision.selected_task else None,
            message=decision.message,
            budget_pressure_level=decision.budget_pressure_level,
            budget_action=decision.budget_action,
            budget_strategy_code=decision.budget_strategy_code,
            budget_strategy_summary=decision.budget_strategy_summary,
            owner_role_code=decision.owner_role_code,
            upstream_role_code=decision.upstream_role_code,
            downstream_role_code=decision.downstream_role_code,
            dispatch_status=decision.dispatch_status,
            handoff_reason=decision.handoff_reason,
            model_name=decision.model_name,
            model_tier=decision.model_tier,
            selected_skill_codes=list(decision.selected_skill_codes),
            selected_skill_names=list(decision.selected_skill_names),
            strategy_code=decision.strategy_code,
            strategy_summary=decision.strategy_summary,
            strategy_reasons=[
                StrategyReasonItemResponse.from_item(item)
                for item in decision.strategy_reasons
            ],
            routing_score=decision.routing_score,
            route_reason=decision.route_reason,
            routing_score_breakdown=[
                StrategyRoutingScoreItemResponse.from_item(item)
                for item in decision.routing_score_breakdown
            ],
            candidates=[
                StrategyCandidateResponse.from_candidate(candidate)
                for candidate in decision.candidates
            ],
        )


class StrategyRulesResponse(BaseModel):
    """Editable rule-set payload returned to the frontend."""

    source: str
    storage_path: str
    rules: dict[str, Any]

    @classmethod
    def from_snapshot(
        cls,
        snapshot: StrategyRuleSetSnapshot,
    ) -> "StrategyRulesResponse":
        """Convert one service snapshot into an API DTO."""

        return cls(
            source=snapshot.source,
            storage_path=snapshot.storage_path,
            rules=snapshot.rules,
        )


class StrategyRulesUpdateRequest(BaseModel):
    """Whole-rule-set replacement request used by the Day 15 editor."""

    rules: dict[str, Any]


def get_strategy_engine_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> StrategyEngineService:
    """Create the Day 15 strategy engine dependency."""

    project_repository = ProjectRepository(session)
    role_catalog_service = RoleCatalogService(
        project_repository=project_repository,
        project_role_repository=ProjectRoleRepository(session),
    )
    skill_registry_service = SkillRegistryService(
        project_repository=project_repository,
        role_catalog_service=role_catalog_service,
        skill_repository=SkillRepository(session),
    )
    return StrategyEngineService(
        project_repository=project_repository,
        role_catalog_service=role_catalog_service,
        skill_registry_service=skill_registry_service,
        budget_guard_service=BudgetGuardService(run_repository=RunRepository(session)),
    )


def get_task_router_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> TaskRouterService:
    """Create a task router dependency for project strategy previews."""

    task_repository = TaskRepository(session)
    run_repository = RunRepository(session)
    budget_guard_service = BudgetGuardService(run_repository=run_repository)
    project_repository = ProjectRepository(session)
    role_catalog_service = RoleCatalogService(
        project_repository=project_repository,
        project_role_repository=ProjectRoleRepository(session),
    )
    skill_registry_service = SkillRegistryService(
        project_repository=project_repository,
        role_catalog_service=role_catalog_service,
        skill_repository=SkillRepository(session),
    )
    strategy_engine_service = StrategyEngineService(
        project_repository=project_repository,
        role_catalog_service=role_catalog_service,
        skill_registry_service=skill_registry_service,
        budget_guard_service=budget_guard_service,
    )
    return TaskRouterService(
        task_repository=task_repository,
        run_repository=run_repository,
        task_readiness_service=TaskReadinessService(
            task_repository=task_repository,
            run_repository=run_repository,
        ),
        budget_guard_service=budget_guard_service,
        strategy_engine_service=strategy_engine_service,
    )


router = APIRouter(prefix="/strategy", tags=["strategy"])


@router.get(
    "/rules",
    response_model=StrategyRulesResponse,
    summary="获取策略规则快照",
)
def get_strategy_rules(
    strategy_engine_service: Annotated[
        StrategyEngineService,
        Depends(get_strategy_engine_service),
    ],
) -> StrategyRulesResponse:
    """Return the current Day 15 rule set for the editor UI."""

    snapshot = strategy_engine_service.get_rule_set_snapshot()
    return StrategyRulesResponse.from_snapshot(snapshot)


@router.put(
    "/rules",
    response_model=StrategyRulesResponse,
    summary="更新策略规则快照",
)
def update_strategy_rules(
    request: StrategyRulesUpdateRequest,
    strategy_engine_service: Annotated[
        StrategyEngineService,
        Depends(get_strategy_engine_service),
    ],
) -> StrategyRulesResponse:
    """Replace the current Day 15 rule set with one validated payload."""

    try:
        snapshot = strategy_engine_service.update_rule_set(rules_payload=request.rules)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return StrategyRulesResponse.from_snapshot(snapshot)


@router.get(
    "/projects/{project_id}/preview",
    response_model=ProjectStrategyPreviewResponse,
    summary="获取项目策略决策预览",
)
def get_project_strategy_preview(
    project_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    task_router_service: Annotated[
        TaskRouterService,
        Depends(get_task_router_service),
    ],
) -> ProjectStrategyPreviewResponse:
    """Return one project-scoped preview of the next routing decision."""

    project = ProjectRepository(session).get_by_id(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    decision = task_router_service.route_next_task(project_id=project_id)
    return ProjectStrategyPreviewResponse.from_decision(
        project=project,
        decision=decision,
    )
