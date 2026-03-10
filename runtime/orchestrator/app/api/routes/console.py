"""Console aggregation endpoints introduced during V2-B and V2-C."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain.task import TaskStatus
from app.repositories.failure_review_repository import FailureReviewRepository
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.budget_guard_service import BudgetGuardService
from app.services.failure_review_service import (
    FailureReviewCluster,
    FailureReviewService,
)
from app.services.run_logging_service import RunLoggingService
from app.services.worker_slot_service import worker_slot_service

from app.api.routes.workers import WorkerSlotSnapshotResponse


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


router = APIRouter(prefix="/console", tags=["console"])


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
