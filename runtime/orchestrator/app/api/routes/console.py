"""Console aggregation endpoints shared by boss home, role workbench and console views."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.routes.repositories import (
    ChangeSessionResponse,
    RepositorySnapshotResponse,
    RepositoryWorkspaceResponse,
)
from app.api.routes.workers import WorkerSlotSnapshotResponse
from app.core.db import get_db_session
from app.domain.change_session import ChangeSession
from app.domain.project import ProjectStage, ProjectStatus
from app.domain.project_role import ProjectRoleCode
from app.domain.run import RunStatus
from app.domain.task import TaskHumanStatus, TaskPriority, TaskRiskLevel, TaskStatus
from app.repositories.change_session_repository import ChangeSessionRepository
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.deliverable_repository import DeliverableRepository
from app.repositories.failure_review_repository import FailureReviewRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.project_role_repository import ProjectRoleRepository
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.approval_service import ApprovalService
from app.services.budget_guard_service import BudgetGuardService, BudgetSnapshot
from app.services.console_service import (
    ConsoleProjectItem,
    ConsoleProjectLatestTask,
    ConsoleProjectOverview,
    ConsoleProjectStageItem,
    ConsoleRoleHandoffItem,
    ConsoleRoleLane,
    ConsoleRoleWorkbenchOverview,
    ConsoleRoleWorkbenchTaskItem,
    ConsoleService,
)
from app.services.console_metrics_service import (
    ConsoleFailureDistribution,
    ConsoleMetricsOverview,
    ConsoleMetricsService,
    ConsoleRoutingDistribution,
)
from app.services.context_builder_service import ContextBuilderService
from app.services.failure_review_service import (
    FailureReviewCluster,
    FailureReviewService,
)
from app.services.role_catalog_service import RoleCatalogService
from app.services.run_logging_service import RunLoggingService
from app.services.task_readiness_service import TaskReadinessService
from app.services.worker_slot_service import worker_slot_service


class ConsoleMetricsResponse(BaseModel):
    """Core run/cost metrics payload returned by `/console/metrics`."""

    total_runs: int
    queued_runs: int
    running_runs: int
    succeeded_runs: int
    failed_runs: int
    cancelled_runs: int
    total_estimated_cost: float
    avg_estimated_cost: float
    total_prompt_tokens: int
    total_completion_tokens: int
    avg_prompt_tokens: float
    avg_completion_tokens: float
    latest_run_created_at: datetime | None = None

    @classmethod
    def from_overview(cls, overview: ConsoleMetricsOverview) -> "ConsoleMetricsResponse":
        """Convert one service-side metrics snapshot into API DTO."""

        return cls(
            total_runs=overview.total_runs,
            queued_runs=overview.queued_runs,
            running_runs=overview.running_runs,
            succeeded_runs=overview.succeeded_runs,
            failed_runs=overview.failed_runs,
            cancelled_runs=overview.cancelled_runs,
            total_estimated_cost=overview.total_estimated_cost,
            avg_estimated_cost=overview.avg_estimated_cost,
            total_prompt_tokens=overview.total_prompt_tokens,
            total_completion_tokens=overview.total_completion_tokens,
            avg_prompt_tokens=overview.avg_prompt_tokens,
            avg_completion_tokens=overview.avg_completion_tokens,
            latest_run_created_at=overview.latest_run_created_at,
        )


class ConsoleBudgetHealthResponse(BaseModel):
    """Budget pressure snapshot returned by `/console/budget-health`."""

    daily_budget_usd: float
    daily_cost_used: float
    daily_cost_remaining: float
    daily_usage_ratio: float
    daily_budget_exceeded: bool
    daily_window_started_at: datetime
    session_budget_usd: float
    session_cost_used: float
    session_cost_remaining: float
    session_usage_ratio: float
    session_budget_exceeded: bool
    session_started_at: datetime
    max_task_retries: int
    pressure_level: str
    suggested_action: str
    strategy_code: str
    strategy_label: str
    strategy_summary: str
    budget_blocked_runs_daily: int
    budget_blocked_runs_session: int

    @classmethod
    def from_snapshot(cls, snapshot: BudgetSnapshot) -> "ConsoleBudgetHealthResponse":
        """Convert one budget snapshot into API DTO."""

        return cls(
            daily_budget_usd=snapshot.daily_budget_usd,
            daily_cost_used=snapshot.daily_cost_used,
            daily_cost_remaining=snapshot.daily_cost_remaining,
            daily_usage_ratio=snapshot.daily_usage_ratio,
            daily_budget_exceeded=snapshot.daily_budget_exceeded,
            daily_window_started_at=snapshot.daily_window_started_at,
            session_budget_usd=snapshot.session_budget_usd,
            session_cost_used=snapshot.session_cost_used,
            session_cost_remaining=snapshot.session_cost_remaining,
            session_usage_ratio=snapshot.session_usage_ratio,
            session_budget_exceeded=snapshot.session_budget_exceeded,
            session_started_at=snapshot.session_started_at,
            max_task_retries=snapshot.max_task_retries,
            pressure_level=snapshot.pressure_level.value,
            suggested_action=snapshot.suggested_action.value,
            strategy_code=snapshot.strategy_code,
            strategy_label=snapshot.strategy_label,
            strategy_summary=snapshot.strategy_summary,
            budget_blocked_runs_daily=snapshot.budget_blocked_runs_daily,
            budget_blocked_runs_session=snapshot.budget_blocked_runs_session,
        )


class RunStatusDistributionResponse(BaseModel):
    """One status distribution item for console failure insights."""

    status: str
    label: str
    count: int


class FailureCategoryDistributionResponse(BaseModel):
    """One failure-category distribution item for console failure insights."""

    category_code: str
    category_label: str
    count: int


class ConsoleFailureDistributionResponse(BaseModel):
    """Failure distribution payload returned by `/console/failure-distribution`."""

    total_runs: int
    failed_or_cancelled_runs: int
    status_distribution: list[RunStatusDistributionResponse]
    failure_category_distribution: list[FailureCategoryDistributionResponse]

    @classmethod
    def from_distribution(
        cls,
        distribution: ConsoleFailureDistribution,
    ) -> "ConsoleFailureDistributionResponse":
        """Convert one service-side failure distribution into API DTO."""

        return cls(
            total_runs=distribution.total_runs,
            failed_or_cancelled_runs=distribution.failed_or_cancelled_runs,
            status_distribution=[
                RunStatusDistributionResponse(
                    status=item.status.value,
                    label=item.label,
                    count=item.count,
                )
                for item in distribution.status_distribution
            ],
            failure_category_distribution=[
                FailureCategoryDistributionResponse(
                    category_code=item.category_code,
                    category_label=item.category_label,
                    count=item.count,
                )
                for item in distribution.failure_category_distribution
            ],
        )


class RoutingDistributionItemResponse(BaseModel):
    """One routing-reason distribution item."""

    reason_code: str
    reason_label: str
    count: int


class ConsoleRoutingDistributionResponse(BaseModel):
    """Routing distribution payload returned by `/console/routing-distribution`."""

    total_routed_runs: int
    distribution: list[RoutingDistributionItemResponse]

    @classmethod
    def from_distribution(
        cls,
        distribution: ConsoleRoutingDistribution,
    ) -> "ConsoleRoutingDistributionResponse":
        """Convert one service-side routing distribution into API DTO."""

        return cls(
            total_routed_runs=distribution.total_routed_runs,
            distribution=[
                RoutingDistributionItemResponse(
                    reason_code=item.reason_code,
                    reason_label=item.reason_label,
                    count=item.count,
                )
                for item in distribution.distribution
            ],
        )


class ConsoleWorkerSlotOverviewResponse(BaseModel):
    """Worker-slot panel payload used by the V2-C console."""

    pending_tasks: int
    running_tasks: int
    blocked_tasks: int
    budget_guard_active: bool
    slot_snapshot: WorkerSlotSnapshotResponse


class ReviewClusterResponse(BaseModel):
    """One console-ready failure review cluster."""

    cluster_key: str
    failure_category: str
    count: int
    latest_run_created_at: str
    route_reason_excerpt: str | None = None
    sample_task_titles: list[str]
    run_ids: list[str]

    @classmethod
    def from_cluster(cls, cluster: FailureReviewCluster) -> "ReviewClusterResponse":
        """Convert one cluster into an API DTO."""

        return cls(
            cluster_key=cluster.cluster_key,
            failure_category=cluster.failure_category,
            count=cluster.count,
            latest_run_created_at=cluster.latest_run_created_at.isoformat(),
            route_reason_excerpt=cluster.route_reason_excerpt,
            sample_task_titles=cluster.sample_task_titles,
            run_ids=[str(run_id) for run_id in cluster.run_ids],
        )


class BossProjectTaskStatsResponse(BaseModel):
    """Task aggregation attached to one boss-homepage project item."""

    total_tasks: int
    pending_tasks: int
    running_tasks: int
    paused_tasks: int
    waiting_human_tasks: int
    completed_tasks: int
    failed_tasks: int
    blocked_tasks: int
    last_task_updated_at: datetime | None = None


class BossProjectLatestTaskResponse(BaseModel):
    """Minimal latest-task snapshot shown inside the project detail panel."""

    task_id: str
    title: str
    status: TaskStatus
    priority: TaskPriority
    risk_level: TaskRiskLevel
    human_status: TaskHumanStatus
    updated_at: datetime
    latest_run_status: RunStatus | None = None
    latest_run_summary: str | None = None

    @classmethod
    def from_latest_task(
        cls,
        latest_task: ConsoleProjectLatestTask,
    ) -> "BossProjectLatestTaskResponse":
        """Convert one service-side latest-task snapshot into an API DTO."""

        return cls(
            task_id=str(latest_task.task.id),
            title=latest_task.task.title,
            status=latest_task.task.status,
            priority=latest_task.task.priority,
            risk_level=latest_task.task.risk_level,
            human_status=latest_task.task.human_status,
            updated_at=latest_task.task.updated_at,
            latest_run_status=(
                latest_task.latest_run.status if latest_task.latest_run is not None else None
            ),
            latest_run_summary=(
                latest_task.latest_run.result_summary
                if latest_task.latest_run is not None
                else None
            ),
        )


class BossProjectItemResponse(BaseModel):
    """One project card/row returned to the Day04 boss homepage."""

    id: str
    name: str
    summary: str
    status: ProjectStatus
    stage: ProjectStage
    task_stats: BossProjectTaskStatsResponse
    latest_progress_summary: str
    latest_progress_at: datetime | None = None
    key_risk_summary: str
    risk_level: str
    blocked: bool
    estimated_cost: float
    prompt_tokens: int
    completion_tokens: int
    attention_task_count: int
    high_risk_task_count: int
    latest_task: BossProjectLatestTaskResponse | None = None
    repository_workspace: RepositoryWorkspaceResponse | None = None
    latest_repository_snapshot: RepositorySnapshotResponse | None = None
    current_change_session: ChangeSessionResponse | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_item(
        cls,
        item: ConsoleProjectItem,
        *,
        current_change_session: ChangeSession | None = None,
    ) -> "BossProjectItemResponse":
        """Convert one service-side project item into an API DTO."""

        return cls(
            id=str(item.project.id),
            name=item.project.name,
            summary=item.project.summary,
            status=item.project.status,
            stage=item.project.stage,
            task_stats=BossProjectTaskStatsResponse(
                total_tasks=item.project.task_stats.total_tasks,
                pending_tasks=item.project.task_stats.pending_tasks,
                running_tasks=item.project.task_stats.running_tasks,
                paused_tasks=item.project.task_stats.paused_tasks,
                waiting_human_tasks=item.project.task_stats.waiting_human_tasks,
                completed_tasks=item.project.task_stats.completed_tasks,
                failed_tasks=item.project.task_stats.failed_tasks,
                blocked_tasks=item.project.task_stats.blocked_tasks,
                last_task_updated_at=item.project.task_stats.last_task_updated_at,
            ),
            latest_progress_summary=item.latest_progress_summary,
            latest_progress_at=item.latest_progress_at,
            key_risk_summary=item.key_risk_summary,
            risk_level=item.risk_level,
            blocked=item.blocked,
            estimated_cost=item.estimated_cost,
            prompt_tokens=item.prompt_tokens,
            completion_tokens=item.completion_tokens,
            attention_task_count=item.attention_task_count,
            high_risk_task_count=item.high_risk_task_count,
            latest_task=(
                BossProjectLatestTaskResponse.from_latest_task(item.latest_task)
                if item.latest_task is not None
                else None
            ),
            repository_workspace=(
                RepositoryWorkspaceResponse.from_workspace(item.project.repository_workspace)
                if item.project.repository_workspace is not None
                else None
            ),
            latest_repository_snapshot=(
                RepositorySnapshotResponse.from_snapshot(
                    item.project.latest_repository_snapshot
                )
                if item.project.latest_repository_snapshot is not None
                else None
            ),
            current_change_session=(
                ChangeSessionResponse.from_change_session(current_change_session)
                if current_change_session is not None
                else None
            ),
            created_at=item.project.created_at,
            updated_at=item.project.updated_at,
        )


class BossProjectStageDistributionResponse(BaseModel):
    """One stage bucket displayed by the boss homepage summary cards."""

    stage: ProjectStage
    count: int

    @classmethod
    def from_item(
        cls,
        item: ConsoleProjectStageItem,
    ) -> "BossProjectStageDistributionResponse":
        """Convert one stage-distribution bucket into an API DTO."""

        return cls(stage=item.stage, count=item.count)


class BossProjectOverviewResponse(BaseModel):
    """Project-first homepage payload returned by `/console/project-overview`."""

    total_projects: int
    active_projects: int
    completed_projects: int
    blocked_projects: int
    total_project_tasks: int
    unassigned_tasks: int
    stage_distribution: list[BossProjectStageDistributionResponse]
    budget: ConsoleBudgetHealthResponse
    projects: list[BossProjectItemResponse]

    @classmethod
    def from_overview(
        cls,
        overview: ConsoleProjectOverview,
        *,
        current_change_sessions: dict[UUID, ChangeSession | None] | None = None,
    ) -> "BossProjectOverviewResponse":
        """Convert the boss-homepage service payload into an API DTO."""

        return cls(
            total_projects=overview.total_projects,
            active_projects=overview.active_projects,
            completed_projects=overview.completed_projects,
            blocked_projects=overview.blocked_projects,
            total_project_tasks=overview.total_project_tasks,
            unassigned_tasks=overview.unassigned_tasks,
            stage_distribution=[
                BossProjectStageDistributionResponse.from_item(item)
                for item in overview.stage_distribution
            ],
            budget=ConsoleBudgetHealthResponse.from_snapshot(overview.budget),
            projects=[
                BossProjectItemResponse.from_item(
                    item,
                    current_change_session=(
                        current_change_sessions.get(item.project.id)
                        if current_change_sessions is not None
                        else None
                    ),
                )
                for item in overview.projects
            ],
        )


class RoleWorkbenchTaskResponse(BaseModel):
    """One task card rendered inside a Day08 role lane."""

    task_id: str
    project_id: str | None = None
    project_name: str | None = None
    title: str
    status: TaskStatus
    priority: TaskPriority
    risk_level: TaskRiskLevel
    human_status: TaskHumanStatus
    input_summary: str
    owner_role_code: ProjectRoleCode | None = None
    upstream_role_code: ProjectRoleCode | None = None
    downstream_role_code: ProjectRoleCode | None = None
    created_at: datetime
    updated_at: datetime
    latest_run_id: str | None = None
    latest_run_status: RunStatus | None = None
    latest_run_summary: str | None = None
    latest_run_log_path: str | None = None

    @classmethod
    def from_item(cls, item: ConsoleRoleWorkbenchTaskItem) -> "RoleWorkbenchTaskResponse":
        """Convert one role-workbench task card into an API DTO."""

        return cls(
            task_id=str(item.task.id),
            project_id=str(item.task.project_id) if item.task.project_id is not None else None,
            project_name=item.project.name if item.project is not None else None,
            title=item.task.title,
            status=item.task.status,
            priority=item.task.priority,
            risk_level=item.task.risk_level,
            human_status=item.task.human_status,
            input_summary=item.task.input_summary,
            owner_role_code=item.task.owner_role_code,
            upstream_role_code=item.task.upstream_role_code,
            downstream_role_code=item.task.downstream_role_code,
            created_at=item.task.created_at,
            updated_at=item.task.updated_at,
            latest_run_id=str(item.latest_run.id) if item.latest_run is not None else None,
            latest_run_status=item.latest_run.status if item.latest_run is not None else None,
            latest_run_summary=(
                item.latest_run.result_summary if item.latest_run is not None else None
            ),
            latest_run_log_path=item.latest_run.log_path if item.latest_run is not None else None,
        )


class RoleWorkbenchHandoffResponse(BaseModel):
    """One recent role handoff item shown on the Day08 timeline."""

    id: str
    timestamp: datetime
    project_id: str | None = None
    project_name: str | None = None
    task_id: str
    task_title: str
    run_id: str | None = None
    run_status: RunStatus | None = None
    owner_role_code: ProjectRoleCode | None = None
    upstream_role_code: ProjectRoleCode | None = None
    downstream_role_code: ProjectRoleCode | None = None
    dispatch_status: str | None = None
    handoff_reason: str | None = None
    message: str
    log_path: str | None = None

    @classmethod
    def from_item(
        cls,
        item: ConsoleRoleHandoffItem,
    ) -> "RoleWorkbenchHandoffResponse":
        """Convert one service-side handoff event into an API DTO."""

        return cls(
            id=item.id,
            timestamp=item.timestamp,
            project_id=str(item.project.id) if item.project is not None else None,
            project_name=item.project.name if item.project is not None else None,
            task_id=str(item.task.id),
            task_title=item.task.title,
            run_id=str(item.latest_run.id) if item.latest_run is not None else None,
            run_status=item.latest_run.status if item.latest_run is not None else None,
            owner_role_code=item.owner_role_code,
            upstream_role_code=item.upstream_role_code,
            downstream_role_code=item.downstream_role_code,
            dispatch_status=item.dispatch_status,
            handoff_reason=item.handoff_reason,
            message=item.message,
            log_path=item.log_path,
        )


class RoleWorkbenchLaneResponse(BaseModel):
    """One role lane returned by `/console/role-workbench`."""

    role_code: ProjectRoleCode
    role_name: str
    role_summary: str
    enabled: bool
    current_task_count: int
    blocked_task_count: int
    running_task_count: int
    recent_handoff_count: int
    current_tasks: list[RoleWorkbenchTaskResponse]
    blocked_tasks: list[RoleWorkbenchTaskResponse]
    running_tasks: list[RoleWorkbenchTaskResponse]
    recent_handoffs: list[RoleWorkbenchHandoffResponse]

    @classmethod
    def from_lane(cls, lane: ConsoleRoleLane) -> "RoleWorkbenchLaneResponse":
        """Convert one service-side role lane into an API DTO."""

        return cls(
            role_code=lane.role.role_code,
            role_name=lane.role.role_name,
            role_summary=lane.role.role_summary,
            enabled=lane.role.enabled,
            current_task_count=len(lane.current_tasks),
            blocked_task_count=len(lane.blocked_tasks),
            running_task_count=len(lane.running_tasks),
            recent_handoff_count=len(lane.recent_handoffs),
            current_tasks=[
                RoleWorkbenchTaskResponse.from_item(item) for item in lane.current_tasks
            ],
            blocked_tasks=[
                RoleWorkbenchTaskResponse.from_item(item) for item in lane.blocked_tasks
            ],
            running_tasks=[
                RoleWorkbenchTaskResponse.from_item(item) for item in lane.running_tasks
            ],
            recent_handoffs=[
                RoleWorkbenchHandoffResponse.from_item(item)
                for item in lane.recent_handoffs
            ],
        )


class RoleWorkbenchOverviewResponse(BaseModel):
    """Aggregated Day08 role workbench response."""

    project_id: str | None = None
    project_name: str | None = None
    project_status: ProjectStatus | None = None
    project_stage: ProjectStage | None = None
    scope_label: str
    total_roles: int
    enabled_roles: int
    total_tasks: int
    active_tasks: int
    running_tasks: int
    blocked_tasks: int
    unassigned_tasks: int
    recent_handoff_count: int
    budget: ConsoleBudgetHealthResponse
    lanes: list[RoleWorkbenchLaneResponse]
    recent_handoffs: list[RoleWorkbenchHandoffResponse]
    generated_at: datetime

    @classmethod
    def from_overview(
        cls,
        overview: ConsoleRoleWorkbenchOverview,
    ) -> "RoleWorkbenchOverviewResponse":
        """Convert the service-side workbench aggregate into an API DTO."""

        return cls(
            project_id=str(overview.project.id) if overview.project is not None else None,
            project_name=overview.project.name if overview.project is not None else None,
            project_status=overview.project.status if overview.project is not None else None,
            project_stage=overview.project.stage if overview.project is not None else None,
            scope_label=overview.scope_label,
            total_roles=overview.total_roles,
            enabled_roles=overview.enabled_roles,
            total_tasks=overview.total_tasks,
            active_tasks=overview.active_tasks,
            running_tasks=overview.running_tasks,
            blocked_tasks=overview.blocked_tasks,
            unassigned_tasks=overview.unassigned_tasks,
            recent_handoff_count=overview.recent_handoff_count,
            budget=ConsoleBudgetHealthResponse.from_snapshot(overview.budget),
            lanes=[RoleWorkbenchLaneResponse.from_lane(item) for item in overview.lanes],
            recent_handoffs=[
                RoleWorkbenchHandoffResponse.from_item(item)
                for item in overview.recent_handoffs
            ],
            generated_at=overview.generated_at,
        )


def get_failure_review_service() -> FailureReviewService:
    """Create the file-backed failure review service dependency."""

    return FailureReviewService(
        failure_review_repository=FailureReviewRepository(),
        run_logging_service=RunLoggingService(),
    )


def get_console_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ConsoleService:
    """Create the shared console aggregation dependency."""

    task_repository = TaskRepository(session)
    project_repository = ProjectRepository(session)
    run_repository = RunRepository(session)
    role_catalog_service = RoleCatalogService(
        project_repository=project_repository,
        project_role_repository=ProjectRoleRepository(session),
    )
    approval_service = ApprovalService(
        approval_repository=ApprovalRepository(session),
        deliverable_repository=DeliverableRepository(session),
        project_repository=project_repository,
    )
    budget_guard_service = BudgetGuardService(run_repository=run_repository)
    task_readiness_service = TaskReadinessService(
        task_repository=task_repository,
        run_repository=run_repository,
    )
    context_builder_service = ContextBuilderService(
        run_repository=run_repository,
        task_readiness_service=task_readiness_service,
    )
    return ConsoleService(
        task_repository=task_repository,
        run_repository=run_repository,
        project_repository=project_repository,
        budget_guard_service=budget_guard_service,
        context_builder_service=context_builder_service,
        approval_service=approval_service,
        role_catalog_service=role_catalog_service,
        run_logging_service=RunLoggingService(),
    )


def get_console_metrics_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ConsoleMetricsService:
    """Create the console metrics aggregation dependency."""

    run_repository = RunRepository(session)
    budget_guard_service = BudgetGuardService(run_repository=run_repository)
    return ConsoleMetricsService(
        run_repository=run_repository,
        budget_guard_service=budget_guard_service,
    )


router = APIRouter(prefix="/console", tags=["console"])


@router.get(
    "/project-overview",
    response_model=BossProjectOverviewResponse,
    summary="获取老板首页项目总览",
)
def get_project_overview(
    console_service: Annotated[ConsoleService, Depends(get_console_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> BossProjectOverviewResponse:
    """Return the Day04 boss homepage payload with repository entry summaries."""

    overview = console_service.get_project_overview()
    change_session_repository = ChangeSessionRepository(session)
    current_change_sessions = {
        item.project.id: change_session_repository.get_by_project_id(item.project.id)
        for item in overview.projects
    }
    return BossProjectOverviewResponse.from_overview(
        overview,
        current_change_sessions=current_change_sessions,
    )


@router.get(
    "/role-workbench",
    response_model=RoleWorkbenchOverviewResponse,
    summary="获取角色工作台聚合视图",
)
def get_role_workbench(
    console_service: Annotated[ConsoleService, Depends(get_console_service)],
    project_id: UUID | None = None,
) -> RoleWorkbenchOverviewResponse:
    """Return the Day08 role workbench payload for one project or all projects."""

    overview = console_service.get_role_workbench(project_id=project_id)
    if overview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    return RoleWorkbenchOverviewResponse.from_overview(overview)


@router.get(
    "/metrics",
    response_model=ConsoleMetricsResponse,
    summary="获取控制台核心指标",
)
def get_console_metrics(
    console_metrics_service: Annotated[
        ConsoleMetricsService,
        Depends(get_console_metrics_service),
    ],
) -> ConsoleMetricsResponse:
    """Return compact run and cost metrics for console overview cards."""

    overview = console_metrics_service.get_metrics()
    return ConsoleMetricsResponse.from_overview(overview)


@router.get(
    "/budget-health",
    response_model=ConsoleBudgetHealthResponse,
    summary="获取预算健康快照",
)
def get_console_budget_health(
    console_metrics_service: Annotated[
        ConsoleMetricsService,
        Depends(get_console_metrics_service),
    ],
) -> ConsoleBudgetHealthResponse:
    """Return current budget pressure, strategy and usage ratios."""

    snapshot = console_metrics_service.get_budget_health()
    return ConsoleBudgetHealthResponse.from_snapshot(snapshot)


@router.get(
    "/failure-distribution",
    response_model=ConsoleFailureDistributionResponse,
    summary="获取失败类型与状态分布",
)
def get_console_failure_distribution(
    console_metrics_service: Annotated[
        ConsoleMetricsService,
        Depends(get_console_metrics_service),
    ],
) -> ConsoleFailureDistributionResponse:
    """Return grouped failure categories and run-status distribution."""

    distribution = console_metrics_service.get_failure_distribution()
    return ConsoleFailureDistributionResponse.from_distribution(distribution)


@router.get(
    "/routing-distribution",
    response_model=ConsoleRoutingDistributionResponse,
    summary="获取路由原因分布",
)
def get_console_routing_distribution(
    console_metrics_service: Annotated[
        ConsoleMetricsService,
        Depends(get_console_metrics_service),
    ],
) -> ConsoleRoutingDistributionResponse:
    """Return coarse routing-reason buckets prepared for console panels."""

    distribution = console_metrics_service.get_routing_distribution()
    return ConsoleRoutingDistributionResponse.from_distribution(distribution)


@router.get(
    "/worker-slots",
    response_model=ConsoleWorkerSlotOverviewResponse,
    summary="获取本地 Worker 槽位概览",
)
def get_worker_slots(
    session: Annotated[Session, Depends(get_db_session)],
) -> ConsoleWorkerSlotOverviewResponse:
    """Return local worker-slot state plus minimal queue pressure metrics."""

    task_repository = TaskRepository(session)
    run_repository = RunRepository(session)
    tasks = task_repository.list_all()
    budget_snapshot = BudgetGuardService(run_repository=run_repository).build_budget_snapshot()

    pending_tasks = sum(1 for task in tasks if task.status == TaskStatus.PENDING)
    running_tasks = sum(1 for task in tasks if task.status == TaskStatus.RUNNING)
    blocked_tasks = sum(1 for task in tasks if task.status == TaskStatus.BLOCKED)

    return ConsoleWorkerSlotOverviewResponse(
        pending_tasks=pending_tasks,
        running_tasks=running_tasks,
        blocked_tasks=blocked_tasks,
        budget_guard_active=(
            budget_snapshot.daily_budget_exceeded or budget_snapshot.session_budget_exceeded
        ),
        slot_snapshot=WorkerSlotSnapshotResponse.from_snapshot(worker_slot_service.snapshot()),
    )


@router.get(
    "/review-clusters",
    response_model=list[ReviewClusterResponse],
    summary="获取失败复盘聚类概览",
)
def get_review_clusters(
    failure_review_service: Annotated[
        FailureReviewService,
        Depends(get_failure_review_service),
    ],
) -> list[ReviewClusterResponse]:
    """Return coarse failure clusters aggregated from stored reviews."""

    clusters = failure_review_service.list_clusters()
    return [ReviewClusterResponse.from_cluster(cluster) for cluster in clusters]
