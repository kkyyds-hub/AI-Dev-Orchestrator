"""Run log, Day10 verification-run and replay endpoints."""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.repositories.failure_review_repository import FailureReviewRepository
from app.repositories.run_repository import RunRepository
from app.repositories.change_batch_repository import ChangeBatchRepository
from app.repositories.change_plan_repository import ChangePlanRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.repository_verification_repository import (
    RepositoryVerificationRepository,
)
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)
from app.repositories.verification_run_repository import VerificationRunRepository
from app.services.decision_replay_service import (
    DecisionReplayService,
    DecisionTrace,
    DecisionTraceItem,
)
from app.services.failure_review_service import FailureReviewRecord, FailureReviewService
from app.services.run_logging_service import RunLogEvent, RunLogReadResult, RunLoggingService
from app.services.verification_run_service import (
    VerificationRunAssociationError,
    VerificationRunChangeBatchNotFoundError,
    VerificationRunChangePlanNotFoundError,
    VerificationRunFeed,
    VerificationRunListItem,
    VerificationRunProjectNotFoundError,
    VerificationRunService,
    VerificationRunTemplateNotFoundError,
    VerificationRunWorkspaceNotFoundError,
)
from app.domain.verification_run import (
    VerificationRunCommandSource,
    VerificationRunFailureCategory,
    VerificationRunStatus,
)


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


class VerificationRunCreateRequest(BaseModel):
    """DTO used to record one structured Day10 verification-run result."""

    project_id: UUID
    change_plan_id: UUID
    change_batch_id: UUID
    verification_template_id: UUID | None = None
    command: str | None = Field(default=None, max_length=2_000)
    working_directory: str | None = Field(default=None, max_length=500)
    status: VerificationRunStatus
    failure_category: VerificationRunFailureCategory | None = None
    duration_seconds: float = Field(default=0.0, ge=0.0, le=86_400.0)
    output_summary: str = Field(min_length=1, max_length=2_000)


class VerificationRunResponse(BaseModel):
    """Enriched verification-run payload returned to the repository run view."""

    id: UUID
    project_id: UUID
    repository_workspace_id: UUID
    repository_root_path: str
    repository_display_name: str | None = None
    change_plan_id: UUID
    change_plan_title: str
    change_batch_id: UUID
    change_batch_title: str
    task_title: str | None = None
    verification_template_id: UUID | None = None
    verification_template_name: str | None = None
    verification_template_category: str | None = None
    command_source: VerificationRunCommandSource
    command: str
    working_directory: str
    status: VerificationRunStatus
    failure_category: VerificationRunFailureCategory | None = None
    duration_seconds: float
    output_summary: str
    started_at: datetime
    finished_at: datetime
    created_at: datetime

    @classmethod
    def from_item(cls, item: VerificationRunListItem) -> "VerificationRunResponse":
        """Convert one service-layer verification-run row into an API DTO."""

        run = item.verification_run
        return cls(
            id=run.id,
            project_id=run.project_id,
            repository_workspace_id=run.repository_workspace_id,
            repository_root_path=item.repository_root_path,
            repository_display_name=item.repository_display_name,
            change_plan_id=run.change_plan_id,
            change_plan_title=item.change_plan_title,
            change_batch_id=run.change_batch_id,
            change_batch_title=item.change_batch_title,
            task_title=item.task_title,
            verification_template_id=run.verification_template_id,
            verification_template_name=run.verification_template_name,
            verification_template_category=(
                run.verification_template_category.value
                if run.verification_template_category is not None
                else None
            ),
            command_source=run.command_source,
            command=run.command,
            working_directory=run.working_directory,
            status=run.status,
            failure_category=run.failure_category,
            duration_seconds=run.duration_seconds,
            output_summary=run.output_summary,
            started_at=run.started_at,
            finished_at=run.finished_at,
            created_at=run.created_at,
        )


class VerificationRunFeedResponse(BaseModel):
    """Project-scoped Day10 verification-run feed."""

    project_id: UUID
    repository_workspace_id: UUID
    repository_root_path: str
    repository_display_name: str | None = None
    change_batch_id: UUID | None = None
    total_runs: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    latest_run: VerificationRunResponse | None = None
    runs: list[VerificationRunResponse]

    @classmethod
    def from_feed(cls, feed: VerificationRunFeed) -> "VerificationRunFeedResponse":
        """Convert one service-layer verification-run feed into an API DTO."""

        return cls(
            project_id=feed.project_id,
            repository_workspace_id=feed.repository_workspace_id,
            repository_root_path=feed.repository_root_path,
            repository_display_name=feed.repository_display_name,
            change_batch_id=feed.change_batch_id,
            total_runs=feed.total_runs,
            status_counts={
                status.value: count for status, count in feed.status_counts.items()
            },
            latest_run=(
                VerificationRunResponse.from_item(feed.latest_run)
                if feed.latest_run is not None
                else None
            ),
            runs=[VerificationRunResponse.from_item(item) for item in feed.runs],
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


def get_failure_review_service() -> FailureReviewService:
    """Create the file-backed failure review service dependency."""

    return FailureReviewService(
        failure_review_repository=FailureReviewRepository(),
        run_logging_service=RunLoggingService(),
    )


def get_verification_run_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> VerificationRunService:
    """Create the Day10 verification-run service dependency."""

    return VerificationRunService(
        verification_run_repository=VerificationRunRepository(session),
        project_repository=ProjectRepository(session),
        repository_workspace_repository=RepositoryWorkspaceRepository(session),
        change_plan_repository=ChangePlanRepository(session),
        change_batch_repository=ChangeBatchRepository(session),
        repository_verification_repository=RepositoryVerificationRepository(session),
    )


router = APIRouter(prefix="/runs", tags=["runs"])


@router.post(
    "/verification",
    response_model=VerificationRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="记录结构化验证运行结果",
)
def create_verification_run(
    request: VerificationRunCreateRequest,
    verification_run_service: Annotated[
        VerificationRunService,
        Depends(get_verification_run_service),
    ],
) -> VerificationRunResponse:
    """Persist one structured Day10 verification-run result."""

    try:
        item = verification_run_service.record_verification_run(
            project_id=request.project_id,
            change_plan_id=request.change_plan_id,
            change_batch_id=request.change_batch_id,
            verification_template_id=request.verification_template_id,
            command=request.command,
            working_directory=request.working_directory,
            status=request.status,
            failure_category=request.failure_category,
            duration_seconds=request.duration_seconds,
            output_summary=request.output_summary,
        )
    except (
        VerificationRunProjectNotFoundError,
        VerificationRunWorkspaceNotFoundError,
        VerificationRunChangePlanNotFoundError,
        VerificationRunChangeBatchNotFoundError,
        VerificationRunTemplateNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except VerificationRunAssociationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return VerificationRunResponse.from_item(item)


@router.get(
    "/verification/projects/{project_id}",
    response_model=VerificationRunFeedResponse,
    summary="获取项目验证运行记录",
)
def get_project_verification_runs(
    project_id: UUID,
    verification_run_service: Annotated[
        VerificationRunService,
        Depends(get_verification_run_service),
    ],
    change_batch_id: UUID | None = Query(default=None),
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> VerificationRunFeedResponse:
    """Return the Day10 project-scoped verification-run feed."""

    try:
        feed = verification_run_service.list_project_runs(
            project_id=project_id,
            change_batch_id=change_batch_id,
            limit=limit,
        )
    except (
        VerificationRunProjectNotFoundError,
        VerificationRunWorkspaceNotFoundError,
        VerificationRunChangeBatchNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except VerificationRunAssociationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return VerificationRunFeedResponse.from_feed(feed)


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


@router.get(
    "/{run_id}/failure-review",
    response_model=FailureReviewResponse | None,
    summary="获取运行失败复盘记录",
)
def get_run_failure_review(
    run_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    failure_review_service: Annotated[
        FailureReviewService,
        Depends(get_failure_review_service),
    ],
) -> FailureReviewResponse | None:
    """Return one persisted failure review record by run id."""

    run_repository = RunRepository(session)
    run = run_repository.get_by_id(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run not found: {run_id}",
        )

    review = failure_review_service.get_review(run_id=run_id)
    return FailureReviewResponse.from_review(review) if review is not None else None
