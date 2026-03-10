"""Run log endpoints."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.repositories.run_repository import RunRepository
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
