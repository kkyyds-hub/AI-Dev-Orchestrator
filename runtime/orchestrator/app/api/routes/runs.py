"""Run log and replay endpoints."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.repositories.failure_review_repository import FailureReviewRepository
from app.repositories.run_repository import RunRepository
from app.services.decision_replay_service import (
    DecisionReplayService,
    DecisionTrace,
    DecisionTraceItem,
)
from app.services.failure_review_service import FailureReviewRecord, FailureReviewService
from app.services.run_logging_service import RunLogEvent, RunLogReadResult, RunLoggingService


class RunLogEventResponse(BaseModel):
    """Structured log event returned by Day 12 log APIs."""

    timestamp: str
    level: str
    event: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_event(cls, event: RunLogEvent) -> "RunLogEventResponse":
        """Convert a log event into an API DTO."""

        return cls(
            timestamp=event.timestamp,
            level=event.level,
            event=event.event,
            message=event.message,
            data=event.data,
        )


class RunLogResponse(BaseModel):
    """Bounded log payload for one run."""

    run_id: UUID
    log_path: str | None = None
    limit: int
    truncated: bool
    events: list[RunLogEventResponse]

    @classmethod
    def from_result(
        cls,
        *,
        run_id: UUID,
        limit: int,
        result: RunLogReadResult,
    ) -> "RunLogResponse":
        """Convert a log read result into an API DTO."""

        return cls(
            run_id=run_id,
            log_path=result.log_path,
            limit=limit,
            truncated=result.truncated,
            events=[RunLogEventResponse.from_event(event) for event in result.events],
        )


class FailureReviewResponse(BaseModel):
    """Stored failure review summary attached to one run trace."""

    review_id: str
    task_id: UUID
    task_title: str
    task_status: str
    run_id: UUID
    run_status: str
    created_at: str
    failure_category: str | None = None
    quality_gate_passed: bool | None = None
    route_reason: str | None = None
    result_summary: str | None = None
    log_path: str | None = None
    evidence_events: list[str]
    action_summary: str
    conclusion: str
    storage_path: str | None = None

    @classmethod
    def from_review(cls, review: FailureReviewRecord) -> "FailureReviewResponse":
        """Convert one stored review into an API DTO."""

        return cls(
            review_id=review.review_id,
            task_id=review.task_id,
            task_title=review.task_title,
            task_status=review.task_status.value,
            run_id=review.run_id,
            run_status=review.run_status.value,
            created_at=review.created_at.isoformat(),
            failure_category=(
                review.failure_category.value if review.failure_category is not None else None
            ),
            quality_gate_passed=review.quality_gate_passed,
            route_reason=review.route_reason,
            result_summary=review.result_summary,
            log_path=review.log_path,
            evidence_events=review.evidence_events,
            action_summary=review.action_summary,
            conclusion=review.conclusion,
            storage_path=review.storage_path,
        )


class DecisionTraceItemResponse(BaseModel):
    """One decision timeline item returned to the frontend."""

    timestamp: str
    stage: str
    title: str
    event: str
    level: str
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_item(cls, item: DecisionTraceItem) -> "DecisionTraceItemResponse":
        """Convert one trace node into an API DTO."""

        return cls(
            timestamp=item.timestamp,
            stage=item.stage,
            title=item.title,
            event=item.event,
            level=item.level,
            summary=item.summary,
            data=item.data,
        )


class DecisionTraceResponse(BaseModel):
    """Replay-friendly timeline for one persisted run."""

    run_id: UUID
    task_id: UUID
    run_status: str
    failure_category: str | None = None
    quality_gate_passed: bool | None = None
    trace_items: list[DecisionTraceItemResponse]
    failure_review: FailureReviewResponse | None = None

    @classmethod
    def from_trace(cls, trace: DecisionTrace) -> "DecisionTraceResponse":
        """Convert one replay trace into an API DTO."""

        return cls(
            run_id=trace.run_id,
            task_id=trace.task_id,
            run_status=trace.run_status.value,
            failure_category=(
                trace.failure_category.value if trace.failure_category is not None else None
            ),
            quality_gate_passed=trace.quality_gate_passed,
            trace_items=[
                DecisionTraceItemResponse.from_item(item) for item in trace.trace_items
            ],
            failure_review=(
                FailureReviewResponse.from_review(trace.failure_review)
                if trace.failure_review is not None
                else None
            ),
        )


def get_decision_replay_service() -> DecisionReplayService:
    """Create the replay service dependency."""

    run_logging_service = RunLoggingService()
    failure_review_service = FailureReviewService(
        failure_review_repository=FailureReviewRepository(),
        run_logging_service=run_logging_service,
    )
    return DecisionReplayService(
        run_logging_service=run_logging_service,
        failure_review_service=failure_review_service,
    )


router = APIRouter(prefix="/runs", tags=["runs"])


@router.get(
    "/{run_id}/logs",
    response_model=RunLogResponse,
    summary="获取运行日志事件",
)
def get_run_logs(
    run_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> RunLogResponse:
    """Return structured log events for one run."""

    run_repository = RunRepository(session)
    run = run_repository.get_by_id(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run not found: {run_id}",
        )

    log_result = RunLoggingService().read_events(log_path=run.log_path, limit=limit)
    return RunLogResponse.from_result(
        run_id=run_id,
        limit=limit,
        result=log_result,
    )


@router.get(
    "/{run_id}/decision-trace",
    response_model=DecisionTraceResponse,
    summary="获取运行决策回放",
)
def get_run_decision_trace(
    run_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    decision_replay_service: Annotated[
        DecisionReplayService,
        Depends(get_decision_replay_service),
    ],
) -> DecisionTraceResponse:
    """Return a replay-friendly decision timeline for one run."""

    run_repository = RunRepository(session)
    run = run_repository.get_by_id(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run not found: {run_id}",
        )

    trace = decision_replay_service.build_run_trace(run=run)
    return DecisionTraceResponse.from_trace(trace)
