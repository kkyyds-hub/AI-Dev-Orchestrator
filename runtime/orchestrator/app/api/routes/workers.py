"""Worker endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain.project_role import ProjectRoleCode
from app.domain.run import (
    RunBudgetPressureLevel,
    RunBudgetStrategyAction,
    RunFailureCategory,
    RunRoutingScoreItem,
    RunStatus,
)
from app.domain.task import TaskStatus
from app.services.worker_slot_service import WorkerSlotSnapshot, WorkerSlotState, WorkerSlotStatus
from app.workers.task_worker import TaskWorker, WorkerRunResult, build_task_worker
from app.workers.worker_pool import WorkerPoolRunResult, worker_pool


class WorkerRunOnceResponse(BaseModel):
    """API response for one explicit worker cycle."""

    class RoutingScoreItemResponse(BaseModel):
        """One routing-score component returned to the caller."""

        code: str
        label: str
        score: float
        detail: str

        @classmethod
        def from_item(
            cls,
            item: RunRoutingScoreItem,
        ) -> "WorkerRunOnceResponse.RoutingScoreItemResponse":
            """Convert one domain routing-score item into an API DTO."""

            return cls(
                code=item.code,
                label=item.label,
                score=item.score,
                detail=item.detail,
            )

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
    routing_score_breakdown: list[RoutingScoreItemResponse] = Field(default_factory=list)
    budget_pressure_level: RunBudgetPressureLevel | None = None
    budget_action: RunBudgetStrategyAction | None = None
    budget_strategy_code: str | None = None
    budget_strategy_summary: str | None = None
    result_summary: str | None = None
    context_summary: str | None = None
    model_name: str | None = None
    model_tier: str | None = None
    selected_skill_codes: list[str] = Field(default_factory=list)
    selected_skill_names: list[str] = Field(default_factory=list)
    strategy_code: str | None = None
    strategy_summary: str | None = None
    owner_role_code: ProjectRoleCode | None = None
    upstream_role_code: ProjectRoleCode | None = None
    downstream_role_code: ProjectRoleCode | None = None
    handoff_reason: str | None = None
    dispatch_status: str | None = None
    project_memory_enabled: bool | None = None
    project_memory_query_text: str | None = None
    project_memory_item_count: int | None = None
    project_memory_context_summary: str | None = None
    task_id: UUID | None = None
    task_title: str | None = None
    task_status: TaskStatus | None = None
    run_id: UUID | None = None
    run_status: RunStatus | None = None
    provider_key: str | None = None
    prompt_template_key: str | None = None
    prompt_template_version: str | None = None
    prompt_char_count: int | None = None
    token_accounting_mode: str | None = None
    provider_receipt_id: str | None = None
    total_tokens: int | None = None
    token_pricing_source: str | None = None
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
            routing_score_breakdown=[
                cls.RoutingScoreItemResponse.from_item(item)
                for item in result.routing_score_breakdown
            ],
            budget_pressure_level=result.budget_pressure_level,
            budget_action=result.budget_action,
            budget_strategy_code=result.budget_strategy_code,
            budget_strategy_summary=result.budget_strategy_summary,
            result_summary=result.result_summary,
            context_summary=result.context_summary,
            model_name=result.model_name,
            model_tier=result.model_tier,
            selected_skill_codes=result.selected_skill_codes,
            selected_skill_names=result.selected_skill_names,
            strategy_code=result.strategy_code,
            strategy_summary=result.strategy_summary,
            owner_role_code=result.owner_role_code,
            upstream_role_code=result.upstream_role_code,
            downstream_role_code=result.downstream_role_code,
            handoff_reason=result.handoff_reason,
            dispatch_status=result.dispatch_status,
            project_memory_enabled=result.project_memory_enabled,
            project_memory_query_text=result.project_memory_query_text,
            project_memory_item_count=result.project_memory_item_count,
            project_memory_context_summary=result.project_memory_context_summary,
            task_id=result.task.id if result.task else None,
            task_title=result.task.title if result.task else None,
            task_status=result.task.status if result.task else None,
            run_id=result.run.id if result.run else None,
            run_status=result.run.status if result.run else None,
            provider_key=result.run.provider_key if result.run else None,
            prompt_template_key=result.run.prompt_template_key if result.run else None,
            prompt_template_version=result.run.prompt_template_version if result.run else None,
            prompt_char_count=result.run.prompt_char_count if result.run else None,
            token_accounting_mode=result.run.token_accounting_mode if result.run else None,
            provider_receipt_id=result.run.provider_receipt_id if result.run else None,
            total_tokens=result.run.total_tokens if result.run else None,
            token_pricing_source=result.run.token_pricing_source if result.run else None,
            prompt_tokens=result.run.prompt_tokens if result.run else None,
            completion_tokens=result.run.completion_tokens if result.run else None,
            estimated_cost=result.run.estimated_cost if result.run else None,
            log_path=result.run.log_path if result.run else None,
        )


def get_task_worker(
    session: Annotated[Session, Depends(get_db_session)],
) -> TaskWorker:
    """Create the minimal worker graph for one request."""

    return build_task_worker(session=session)


class WorkerSlotResponse(BaseModel):
    """Visible state of one local worker slot."""

    slot_id: int
    state: WorkerSlotState
    worker_name: str | None = None
    task_id: str | None = None
    task_title: str | None = None
    run_id: str | None = None
    acquired_at: str | None = None
    last_task_id: str | None = None
    last_task_title: str | None = None
    last_run_id: str | None = None
    last_released_at: str | None = None

    @classmethod
    def from_status(cls, status: WorkerSlotStatus) -> "WorkerSlotResponse":
        """Convert one slot snapshot into an API DTO."""

        return cls(
            slot_id=status.slot_id,
            state=status.state,
            worker_name=status.worker_name,
            task_id=status.task_id,
            task_title=status.task_title,
            run_id=status.run_id,
            acquired_at=status.acquired_at.isoformat() if status.acquired_at else None,
            last_task_id=status.last_task_id,
            last_task_title=status.last_task_title,
            last_run_id=status.last_run_id,
            last_released_at=(
                status.last_released_at.isoformat() if status.last_released_at else None
            ),
        )


class WorkerSlotSnapshotResponse(BaseModel):
    """Pool-wide worker-slot summary returned to the frontend."""

    max_concurrent_workers: int
    running_slots: int
    idle_slots: int
    slots: list[WorkerSlotResponse]

    @classmethod
    def from_snapshot(
        cls,
        snapshot: WorkerSlotSnapshot,
    ) -> "WorkerSlotSnapshotResponse":
        """Convert one slot snapshot into an API DTO."""

        return cls(
            max_concurrent_workers=snapshot.max_concurrent_workers,
            running_slots=snapshot.running_slots,
            idle_slots=snapshot.idle_slots,
            slots=[WorkerSlotResponse.from_status(slot) for slot in snapshot.slots],
        )


class WorkerPoolRunResponse(BaseModel):
    """API response for one local worker-pool cycle."""

    requested_workers: int
    launched_workers: int
    claimed_runs: int
    idle_workers: int
    results: list[WorkerRunOnceResponse]
    slot_snapshot: WorkerSlotSnapshotResponse

    @classmethod
    def from_result(cls, result: WorkerPoolRunResult) -> "WorkerPoolRunResponse":
        """Convert one pool-cycle result into an API DTO."""

        return cls(
            requested_workers=result.requested_workers,
            launched_workers=result.launched_workers,
            claimed_runs=result.claimed_runs,
            idle_workers=result.idle_workers,
            results=[WorkerRunOnceResponse.from_result(item) for item in result.results],
            slot_snapshot=WorkerSlotSnapshotResponse.from_snapshot(result.slot_snapshot),
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


@router.post(
    "/run-pool-once",
    response_model=WorkerPoolRunResponse,
    summary="执行一次固定槽位 Worker Pool 循环",
)
def run_worker_pool_once(
    requested_workers: Annotated[int | None, Query(ge=1, le=8)] = None,
) -> WorkerPoolRunResponse:
    """Explicitly trigger one limited-parallel worker-pool cycle."""

    result = worker_pool.run_once(requested_workers=requested_workers)
    return WorkerPoolRunResponse.from_result(result)
