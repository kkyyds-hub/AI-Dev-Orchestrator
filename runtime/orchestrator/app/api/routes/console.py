"""Console aggregation endpoints introduced during V2-B and V2-C."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.routes.workers import WorkerSlotSnapshotResponse
from app.core.db import get_db_session
from app.domain.task import TaskStatus
from app.repositories.failure_review_repository import FailureReviewRepository
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.budget_guard_service import BudgetGuardService, BudgetSnapshot
from app.services.console_metrics_service import (
    ConsoleFailureDistribution,
    ConsoleMetricsOverview,
    ConsoleMetricsService,
    ConsoleRoutingDistribution,
)
from app.services.failure_review_service import (
    FailureReviewCluster,
    FailureReviewService,
)
from app.services.run_logging_service import RunLoggingService
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


def get_failure_review_service() -> FailureReviewService:
    """Create the file-backed failure review service dependency."""

    return FailureReviewService(
        failure_review_repository=FailureReviewRepository(),
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
