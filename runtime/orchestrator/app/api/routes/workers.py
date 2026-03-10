"""Worker endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain.run import RunFailureCategory, RunStatus
from app.domain.task import TaskStatus
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.budget_guard_service import BudgetGuardService
from app.services.context_builder_service import ContextBuilderService
from app.services.cost_estimator_service import CostEstimatorService
from app.services.executor_service import ExecutorService
from app.services.run_logging_service import RunLoggingService
from app.services.task_readiness_service import TaskReadinessService
from app.services.task_router_service import TaskRouterService
from app.services.task_state_machine_service import TaskStateMachineService
from app.services.verifier_service import VerifierService
from app.workers.task_worker import TaskWorker, WorkerRunResult


class WorkerRunOnceResponse(BaseModel):
    """API response for one explicit worker cycle."""

    claimed: bool
    message: str
    execution_mode: str | None = None
    verification_mode: str | None = None
    verification_template: str | None = None
    verification_summary: str | None = None
    failure_category: RunFailureCategory | None = None
    quality_gate_passed: bool | None = None
    route_reason: str | None = None
    routing_score: float | None = None
    result_summary: str | None = None
    context_summary: str | None = None
    task_id: UUID | None = None
    task_title: str | None = None
    task_status: TaskStatus | None = None
    run_id: UUID | None = None
    run_status: RunStatus | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    estimated_cost: float | None = None
    log_path: str | None = None

    @classmethod
    def from_result(cls, result: WorkerRunResult) -> "WorkerRunOnceResponse":
        """Convert the internal worker result into an API DTO."""

        return cls(
            claimed=result.claimed,
            message=result.message,
            execution_mode=result.execution_mode,
            verification_mode=result.verification_mode,
            verification_template=result.verification_template,
            verification_summary=result.verification_summary,
            failure_category=result.failure_category,
            quality_gate_passed=result.quality_gate_passed,
            route_reason=result.route_reason,
            routing_score=result.routing_score,
            result_summary=result.result_summary,
            context_summary=result.context_summary,
            task_id=result.task.id if result.task else None,
            task_title=result.task.title if result.task else None,
            task_status=result.task.status if result.task else None,
            run_id=result.run.id if result.run else None,
            run_status=result.run.status if result.run else None,
            prompt_tokens=result.run.prompt_tokens if result.run else None,
            completion_tokens=result.run.completion_tokens if result.run else None,
            estimated_cost=result.run.estimated_cost if result.run else None,
            log_path=result.run.log_path if result.run else None,
        )


def get_task_worker(
    session: Annotated[Session, Depends(get_db_session)],
) -> TaskWorker:
    """Create the minimal worker graph for one request."""

    task_repository = TaskRepository(session)
    run_repository = RunRepository(session)
    budget_guard_service = BudgetGuardService(run_repository=run_repository)
    executor_service = ExecutorService()
    verifier_service = VerifierService(executor_service=executor_service)
    run_logging_service = RunLoggingService()
    cost_estimator_service = CostEstimatorService()
    task_state_machine_service = TaskStateMachineService()
    task_readiness_service = TaskReadinessService(
        task_repository=task_repository,
        run_repository=run_repository,
    )
    context_builder_service = ContextBuilderService(
        run_repository=run_repository,
        task_readiness_service=task_readiness_service,
    )
    task_router_service = TaskRouterService(
        task_repository=task_repository,
        run_repository=run_repository,
        task_readiness_service=task_readiness_service,
    )
    return TaskWorker(
        session=session,
        task_repository=task_repository,
        run_repository=run_repository,
        executor_service=executor_service,
        verifier_service=verifier_service,
        budget_guard_service=budget_guard_service,
        run_logging_service=run_logging_service,
        cost_estimator_service=cost_estimator_service,
        context_builder_service=context_builder_service,
        task_router_service=task_router_service,
        task_state_machine_service=task_state_machine_service,
    )


router = APIRouter(prefix="/workers", tags=["workers"])


@router.post(
    "/run-once",
    response_model=WorkerRunOnceResponse,
    summary="执行一次 Worker 最小循环",
)
def run_worker_once(
    task_worker: Annotated[TaskWorker, Depends(get_task_worker)],
) -> WorkerRunOnceResponse:
    """Explicitly trigger one worker cycle."""

    result = task_worker.run_once()
    return WorkerRunOnceResponse.from_result(result)
