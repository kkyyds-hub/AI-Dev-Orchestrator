"""Task endpoints."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain.project_role import ProjectRoleCode
from app.domain.run import (
    Run,
    RunBudgetPressureLevel,
    RunBudgetStrategyAction,
    RunFailureCategory,
    RunRoutingScoreItem,
    RunStatus,
)
from app.domain.task import (
    Task,
    TaskHumanStatus,
    TaskPriority,
    TaskRiskLevel,
    TaskStatus,
)
from app.repositories.project_repository import ProjectRepository
from app.repositories.project_role_repository import ProjectRoleRepository
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.failure_review_repository import FailureReviewRepository
from app.services.budget_guard_service import BudgetGuardService, BudgetSnapshot
from app.services.console_service import (
    ConsoleOverview,
    ConsoleService,
    ConsoleTaskDetail,
    ConsoleTaskItem,
)
from app.services.run_logging_service import RunLoggingService
from app.services.context_builder_service import (
    ContextBuilderService,
    ContextRecentRunItem,
    TaskContextPackage,
)
from app.services.decision_replay_service import (
    DecisionHistoryItem,
    DecisionReplayService,
)
from app.services.failure_review_service import FailureReviewService
from app.services.role_catalog_service import RoleCatalogService
from app.services.task_readiness_service import (
    TaskBlockingSignal,
    TaskDependencyReadinessItem,
    TaskReadinessService,
)
from app.services.task_service import (
    TaskRetryResult,
    TaskService,
    TaskStateActionResult,
)
from app.services.task_state_machine_service import TaskStateMachineService


class TaskCreateRequest(BaseModel):
    """DTO for task creation requests."""

    project_id: UUID | None = Field(
        default=None,
        description="Optional owning project ID for project-level grouping.",
    )
    title: str = Field(
        min_length=1,
        max_length=200,
        description="Task title shown in the console.",
    )
    input_summary: str = Field(
        min_length=1,
        max_length=2_000,
        description="Minimal task instruction summary used by the worker.",
    )
    priority: TaskPriority = Field(
        default=TaskPriority.NORMAL,
        description="Task priority. Defaults to `normal`.",
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Optional acceptance criteria checked by a human or future planner.",
    )
    depends_on_task_ids: list[UUID] = Field(
        default_factory=list,
        max_length=20,
        description="Optional task IDs that must complete before this task can run.",
    )
    risk_level: TaskRiskLevel = Field(
        default=TaskRiskLevel.NORMAL,
        description="Conservative task risk flag used by future routing rules.",
    )
    owner_role_code: ProjectRoleCode | None = Field(
        default=None,
        description="Optional explicit owner role for Day07 role dispatch.",
    )
    upstream_role_code: ProjectRoleCode | None = Field(
        default=None,
        description="Optional explicit upstream/source role for Day07 handoffs.",
    )
    downstream_role_code: ProjectRoleCode | None = Field(
        default=None,
        description="Optional explicit downstream/handoff role for Day07 handoffs.",
    )
    human_status: TaskHumanStatus = Field(
        default=TaskHumanStatus.NONE,
        description="Whether this task already needs human attention.",
    )
    paused_reason: str | None = Field(
        default=None,
        max_length=500,
        description="Optional pause note reserved for future pause / resume flows.",
    )


class TaskResponse(BaseModel):
    """Basic task response DTO."""

    id: UUID
    project_id: UUID | None = None
    title: str
    status: TaskStatus
    priority: TaskPriority
    input_summary: str
    acceptance_criteria: list[str]
    depends_on_task_ids: list[UUID]
    risk_level: TaskRiskLevel
    owner_role_code: ProjectRoleCode | None = None
    upstream_role_code: ProjectRoleCode | None = None
    downstream_role_code: ProjectRoleCode | None = None
    human_status: TaskHumanStatus
    paused_reason: str | None = None
    source_draft_id: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_task(cls, task: Task) -> "TaskResponse":
        """Convert the domain task into an API DTO."""

        return cls(
            id=task.id,
            project_id=task.project_id,
            title=task.title,
            status=task.status,
            priority=task.priority,
            input_summary=task.input_summary,
            acceptance_criteria=task.acceptance_criteria,
            depends_on_task_ids=task.depends_on_task_ids,
            risk_level=task.risk_level,
            owner_role_code=task.owner_role_code,
            upstream_role_code=task.upstream_role_code,
            downstream_role_code=task.downstream_role_code,
            human_status=task.human_status,
            paused_reason=task.paused_reason,
            source_draft_id=task.source_draft_id,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )


class TaskRetryResponse(BaseModel):
    """Response returned after a Day 12 retry action."""

    message: str
    task_id: UUID
    task_title: str
    previous_status: TaskStatus
    current_status: TaskStatus
    updated_at: datetime

    @classmethod
    def from_result(cls, result: TaskRetryResult) -> "TaskRetryResponse":
        """Convert the retry service result into an API DTO."""

        return cls(
            message=(
                "Task was reset to pending. "
                "A future worker run will create the next run attempt."
            ),
            task_id=result.task.id,
            task_title=result.task.title,
            previous_status=result.previous_status,
            current_status=result.task.status,
            updated_at=result.task.updated_at,
        )


class TaskControlRequest(BaseModel):
    """Request body for manual task state-control actions."""

    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Optional operator note for pause-style actions.",
    )


class TaskStateActionResponse(BaseModel):
    """Response returned after one manual task state transition."""

    message: str
    task_id: UUID
    task_title: str
    previous_status: TaskStatus
    current_status: TaskStatus
    human_status: TaskHumanStatus
    paused_reason: str | None = None
    updated_at: datetime

    @classmethod
    def from_result(
        cls,
        result: TaskStateActionResult,
    ) -> "TaskStateActionResponse":
        """Convert one task control result into an API DTO."""

        return cls(
            message=result.message,
            task_id=result.task.id,
            task_title=result.task.title,
            previous_status=result.previous_status,
            current_status=result.task.status,
            human_status=result.task.human_status,
            paused_reason=result.task.paused_reason,
            updated_at=result.task.updated_at,
        )


class TaskConsoleRunResponse(BaseModel):
    """Run details used by the Day 10 / Day 11 console views."""

    class RoutingScoreItemResponse(BaseModel):
        """One routing-score component returned to the console."""

        code: str
        label: str
        score: float
        detail: str

        @classmethod
        def from_item(
            cls,
            item: RunRoutingScoreItem,
        ) -> "TaskConsoleRunResponse.RoutingScoreItemResponse":
            """Convert one domain routing-score item into an API DTO."""

            return cls(
                code=item.code,
                label=item.label,
                score=item.score,
                detail=item.detail,
            )

    id: UUID
    status: RunStatus
    model_name: str | None = None
    route_reason: str | None = None
    routing_score: float | None = None
    routing_score_breakdown: list[RoutingScoreItemResponse] = Field(default_factory=list)
    strategy_decision: dict[str, object] | None = None
    owner_role_code: ProjectRoleCode | None = None
    upstream_role_code: ProjectRoleCode | None = None
    downstream_role_code: ProjectRoleCode | None = None
    handoff_reason: str | None = None
    dispatch_status: str | None = None
    result_summary: str | None = None
    prompt_tokens: int
    completion_tokens: int
    estimated_cost: float
    log_path: str | None = None
    verification_mode: str | None = None
    verification_template: str | None = None
    verification_command: str | None = None
    verification_summary: str | None = None
    failure_category: RunFailureCategory | None = None
    quality_gate_passed: bool | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime

    @classmethod
    def from_run(cls, run: Run) -> "TaskConsoleRunResponse":
        """Convert a domain run into a console response DTO."""

        return cls(
            id=run.id,
            status=run.status,
            model_name=run.model_name,
            route_reason=run.route_reason,
            routing_score=run.routing_score,
            routing_score_breakdown=[
                cls.RoutingScoreItemResponse.from_item(item)
                for item in run.routing_score_breakdown
            ],
            strategy_decision=(
                run.strategy_decision.model_dump(mode="json")
                if run.strategy_decision is not None
                else None
            ),
            owner_role_code=run.owner_role_code,
            upstream_role_code=run.upstream_role_code,
            downstream_role_code=run.downstream_role_code,
            handoff_reason=run.handoff_reason,
            dispatch_status=run.dispatch_status,
            result_summary=run.result_summary,
            prompt_tokens=run.prompt_tokens,
            completion_tokens=run.completion_tokens,
            estimated_cost=run.estimated_cost,
            log_path=run.log_path,
            verification_mode=run.verification_mode,
            verification_template=run.verification_template,
            verification_command=run.verification_command,
            verification_summary=run.verification_summary,
            failure_category=run.failure_category,
            quality_gate_passed=run.quality_gate_passed,
            started_at=run.started_at,
            finished_at=run.finished_at,
            created_at=run.created_at,
        )


class TaskConsoleItemResponse(BaseModel):
    """Task row used by the console homepage."""

    id: UUID
    title: str
    status: TaskStatus
    priority: TaskPriority
    input_summary: str
    acceptance_criteria: list[str]
    depends_on_task_ids: list[UUID]
    risk_level: TaskRiskLevel
    owner_role_code: ProjectRoleCode | None = None
    upstream_role_code: ProjectRoleCode | None = None
    downstream_role_code: ProjectRoleCode | None = None
    human_status: TaskHumanStatus
    paused_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    latest_run: TaskConsoleRunResponse | None = None

    @classmethod
    def from_item(cls, item: ConsoleTaskItem) -> "TaskConsoleItemResponse":
        """Convert a console item into its response DTO."""

        return cls(
            id=item.task.id,
            title=item.task.title,
            status=item.task.status,
            priority=item.task.priority,
            input_summary=item.task.input_summary,
            acceptance_criteria=item.task.acceptance_criteria,
            depends_on_task_ids=item.task.depends_on_task_ids,
            risk_level=item.task.risk_level,
            owner_role_code=item.task.owner_role_code,
            upstream_role_code=item.task.upstream_role_code,
            downstream_role_code=item.task.downstream_role_code,
            human_status=item.task.human_status,
            paused_reason=item.task.paused_reason,
            created_at=item.task.created_at,
            updated_at=item.task.updated_at,
            latest_run=(
                TaskConsoleRunResponse.from_run(item.latest_run)
                if item.latest_run is not None
                else None
            ),
        )


class TaskContextDependencyResponse(BaseModel):
    """Dependency summary included in the context preview."""

    task_id: UUID
    title: str
    status: TaskStatus
    latest_run_status: RunStatus | None = None
    latest_run_summary: str | None = None
    latest_failure_category: RunFailureCategory | None = None
    missing: bool = False

    @classmethod
    def from_item(
        cls,
        item: TaskDependencyReadinessItem,
    ) -> "TaskContextDependencyResponse":
        """Convert one dependency context item into an API DTO."""

        return cls(
            task_id=item.task_id,
            title=item.title,
            status=item.status,
            latest_run_status=item.latest_run_status,
            latest_run_summary=item.latest_run_summary,
            latest_failure_category=item.latest_failure_category,
            missing=item.missing,
        )


class TaskBlockingSignalResponse(BaseModel):
    """Structured blocking signal returned to the frontend."""

    code: str
    category: str
    message: str

    @classmethod
    def from_signal(
        cls,
        signal: TaskBlockingSignal,
    ) -> "TaskBlockingSignalResponse":
        """Convert one standardized blocking signal into an API DTO."""

        return cls(
            code=signal.code.value,
            category=signal.category.value,
            message=signal.message,
        )


class TaskContextRecentRunResponse(BaseModel):
    """Recent run excerpt included in the context preview."""

    run_id: UUID
    status: RunStatus
    result_summary: str | None = None
    verification_summary: str | None = None
    failure_category: RunFailureCategory | None = None
    created_at: datetime

    @classmethod
    def from_item(
        cls,
        item: ContextRecentRunItem,
    ) -> "TaskContextRecentRunResponse":
        """Convert one recent-run context item into an API DTO."""

        return cls(
            run_id=item.run_id,
            status=item.status,
            result_summary=item.result_summary,
            verification_summary=item.verification_summary,
            failure_category=item.failure_category,
            created_at=item.created_at,
        )


class TaskContextPreviewResponse(BaseModel):
    """Structured preview of the minimal context package."""

    task_id: UUID
    task_title: str
    input_summary: str
    acceptance_criteria: list[str]
    priority: TaskPriority
    risk_level: TaskRiskLevel
    human_status: TaskHumanStatus
    paused_reason: str | None = None
    ready_for_execution: bool
    blocking_signals: list["TaskBlockingSignalResponse"]
    blocking_reasons: list[str]
    dependency_items: list[TaskContextDependencyResponse]
    recent_runs: list[TaskContextRecentRunResponse]
    context_summary: str

    @classmethod
    def from_context(
        cls,
        context: TaskContextPackage,
    ) -> "TaskContextPreviewResponse":
        """Convert one task context package into an API DTO."""

        return cls(
            task_id=context.task_id,
            task_title=context.task_title,
            input_summary=context.input_summary,
            acceptance_criteria=context.acceptance_criteria,
            priority=context.priority,
            risk_level=context.risk_level,
            human_status=context.human_status,
            paused_reason=context.paused_reason,
            ready_for_execution=context.ready_for_execution,
            blocking_signals=[
                TaskBlockingSignalResponse.from_signal(signal)
                for signal in context.blocking_signals
            ],
            blocking_reasons=context.blocking_reasons,
            dependency_items=[
                TaskContextDependencyResponse.from_item(item)
                for item in context.dependency_items
            ],
            recent_runs=[
                TaskContextRecentRunResponse.from_item(item)
                for item in context.recent_runs
            ],
            context_summary=context.context_summary,
        )


class ConsoleBudgetResponse(BaseModel):
    """Budget snapshot returned on the Day 15 homepage."""

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
    pressure_level: RunBudgetPressureLevel
    suggested_action: RunBudgetStrategyAction
    strategy_code: str
    strategy_label: str
    strategy_summary: str
    budget_blocked_runs_daily: int
    budget_blocked_runs_session: int

    @classmethod
    def from_snapshot(cls, snapshot: BudgetSnapshot) -> "ConsoleBudgetResponse":
        """Convert one domain budget snapshot into an API DTO."""

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
            pressure_level=snapshot.pressure_level,
            suggested_action=snapshot.suggested_action,
            strategy_code=snapshot.strategy_code,
            strategy_label=snapshot.strategy_label,
            strategy_summary=snapshot.strategy_summary,
            budget_blocked_runs_daily=snapshot.budget_blocked_runs_daily,
            budget_blocked_runs_session=snapshot.budget_blocked_runs_session,
        )


class TaskConsoleDetailResponse(TaskConsoleItemResponse):
    """Aggregated task detail payload used by the Day 11 side panel."""

    runs: list[TaskConsoleRunResponse]
    context_preview: TaskContextPreviewResponse

    @classmethod
    def from_detail(cls, detail: ConsoleTaskDetail) -> "TaskConsoleDetailResponse":
        """Convert a console task detail into its response DTO."""

        return cls(
            id=detail.task.id,
            title=detail.task.title,
            status=detail.task.status,
            priority=detail.task.priority,
            input_summary=detail.task.input_summary,
            acceptance_criteria=detail.task.acceptance_criteria,
            depends_on_task_ids=detail.task.depends_on_task_ids,
            risk_level=detail.task.risk_level,
            owner_role_code=detail.task.owner_role_code,
            upstream_role_code=detail.task.upstream_role_code,
            downstream_role_code=detail.task.downstream_role_code,
            human_status=detail.task.human_status,
            paused_reason=detail.task.paused_reason,
            created_at=detail.task.created_at,
            updated_at=detail.task.updated_at,
            latest_run=(
                TaskConsoleRunResponse.from_run(detail.latest_run)
                if detail.latest_run is not None
                else None
            ),
            runs=[TaskConsoleRunResponse.from_run(run) for run in detail.runs],
            context_preview=TaskContextPreviewResponse.from_context(
                detail.context_preview
            ),
        )


class ConsoleOverviewResponse(BaseModel):
    """Aggregated homepage payload for the Day 10 console."""

    total_tasks: int
    pending_tasks: int
    running_tasks: int
    paused_tasks: int
    waiting_human_tasks: int
    completed_tasks: int
    failed_tasks: int
    blocked_tasks: int
    total_estimated_cost: float
    total_prompt_tokens: int
    total_completion_tokens: int
    budget: ConsoleBudgetResponse
    tasks: list[TaskConsoleItemResponse]

    @classmethod
    def from_overview(cls, overview: ConsoleOverview) -> "ConsoleOverviewResponse":
        """Convert service output into an API response DTO."""

        return cls(
            total_tasks=overview.total_tasks,
            pending_tasks=overview.pending_tasks,
            running_tasks=overview.running_tasks,
            paused_tasks=overview.paused_tasks,
            waiting_human_tasks=overview.waiting_human_tasks,
            completed_tasks=overview.completed_tasks,
            failed_tasks=overview.failed_tasks,
            blocked_tasks=overview.blocked_tasks,
            total_estimated_cost=overview.total_estimated_cost,
            total_prompt_tokens=overview.total_prompt_tokens,
            total_completion_tokens=overview.total_completion_tokens,
            budget=ConsoleBudgetResponse.from_snapshot(overview.budget),
            tasks=[TaskConsoleItemResponse.from_item(item) for item in overview.tasks],
        )


class DecisionHistoryItemResponse(BaseModel):
    """Task-level summary of one historical decision trace."""

    run_id: UUID
    status: RunStatus
    failure_category: RunFailureCategory | None = None
    quality_gate_passed: bool | None = None
    created_at: datetime
    headline: str
    stages: list[str]

    @classmethod
    def from_item(cls, item: DecisionHistoryItem) -> "DecisionHistoryItemResponse":
        """Convert one decision history summary into an API DTO."""

        return cls(
            run_id=item.run_id,
            status=item.status,
            failure_category=item.failure_category,
            quality_gate_passed=item.quality_gate_passed,
            created_at=datetime.fromisoformat(item.created_at),
            headline=item.headline,
            stages=item.stages,
        )


def build_task_responses(tasks: list[Task]) -> list[TaskResponse]:
    """Convert a list of domain tasks into API DTOs."""

    return [TaskResponse.from_task(task) for task in tasks]


def get_task_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> TaskService:
    """Create the task service dependency."""

    task_repository = TaskRepository(session)
    project_repository = ProjectRepository(session)
    project_role_repository = ProjectRoleRepository(session)
    run_repository = RunRepository(session)
    budget_guard_service = BudgetGuardService(run_repository=run_repository)
    task_state_machine_service = TaskStateMachineService()
    role_catalog_service = RoleCatalogService(
        project_repository=project_repository,
        project_role_repository=project_role_repository,
    )
    return TaskService(
        task_repository=task_repository,
        project_repository=project_repository,
        budget_guard_service=budget_guard_service,
        task_state_machine_service=task_state_machine_service,
        role_catalog_service=role_catalog_service,
    )


def get_console_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ConsoleService:
    """Create the console service dependency."""

    task_repository = TaskRepository(session)
    project_repository = ProjectRepository(session)
    run_repository = RunRepository(session)
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
    )


def get_decision_replay_service() -> DecisionReplayService:
    """Create the decision replay dependency."""

    run_logging_service = RunLoggingService()
    failure_review_service = FailureReviewService(
        failure_review_repository=FailureReviewRepository(),
        run_logging_service=run_logging_service,
    )
    return DecisionReplayService(
        run_logging_service=run_logging_service,
        failure_review_service=failure_review_service,
    )


router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建任务",
)
def create_task(
    request: TaskCreateRequest,
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    """Create a new task."""

    try:
        task = task_service.create_task(
            project_id=request.project_id,
            title=request.title,
            input_summary=request.input_summary,
            priority=request.priority,
            acceptance_criteria=request.acceptance_criteria,
            depends_on_task_ids=request.depends_on_task_ids,
            risk_level=request.risk_level,
            owner_role_code=request.owner_role_code,
            upstream_role_code=request.upstream_role_code,
            downstream_role_code=request.downstream_role_code,
            human_status=request.human_status,
            paused_reason=request.paused_reason,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return TaskResponse.from_task(task)


@router.get(
    "",
    response_model=list[TaskResponse],
    summary="获取任务列表",
)
def list_tasks(
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> list[TaskResponse]:
    """Return all tasks."""

    tasks = task_service.list_tasks()
    return build_task_responses(tasks)


@router.get(
    "/console",
    response_model=ConsoleOverviewResponse,
    summary="获取 Day 10 控制台首页数据",
)
def get_console_overview(
    console_service: Annotated[ConsoleService, Depends(get_console_service)],
) -> ConsoleOverviewResponse:
    """Return the aggregated Day 10 homepage payload."""

    overview = console_service.get_overview()
    return ConsoleOverviewResponse.from_overview(overview)


@router.get(
    "/{task_id}/runs",
    response_model=list[TaskConsoleRunResponse],
    summary="获取任务运行历史",
)
def list_task_runs(
    task_id: UUID,
    console_service: Annotated[ConsoleService, Depends(get_console_service)],
) -> list[TaskConsoleRunResponse]:
    """Return all persisted runs for one task."""

    runs = console_service.get_task_runs(task_id)
    if runs is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    return [TaskConsoleRunResponse.from_run(run) for run in runs]


@router.get(
    "/{task_id}/decision-history",
    response_model=list[DecisionHistoryItemResponse],
    summary="获取任务决策回放历史",
)
def get_task_decision_history(
    task_id: UUID,
    console_service: Annotated[ConsoleService, Depends(get_console_service)],
    decision_replay_service: Annotated[
        DecisionReplayService,
        Depends(get_decision_replay_service),
    ],
) -> list[DecisionHistoryItemResponse]:
    """Return the replay history summaries for one task."""

    runs = console_service.get_task_runs(task_id)
    if runs is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    history = decision_replay_service.build_task_history(runs=runs)
    return [DecisionHistoryItemResponse.from_item(item) for item in history]


@router.get(
    "/{task_id}/detail",
    response_model=TaskConsoleDetailResponse,
    summary="获取 Day 11 任务详情数据",
)
def get_task_detail(
    task_id: UUID,
    console_service: Annotated[ConsoleService, Depends(get_console_service)],
) -> TaskConsoleDetailResponse:
    """Return the aggregated Day 11 task detail payload."""

    detail = console_service.get_task_detail(task_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    return TaskConsoleDetailResponse.from_detail(detail)


@router.post(
    "/{task_id}/retry",
    response_model=TaskRetryResponse,
    summary="重试失败或阻塞任务",
)
def retry_task(
    task_id: UUID,
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskRetryResponse:
    """Reset one failed or blocked task back to `pending`."""

    try:
        retry_result = task_service.retry_task(task_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if retry_result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    return TaskRetryResponse.from_result(retry_result)


@router.post(
    "/{task_id}/pause",
    response_model=TaskStateActionResponse,
    summary="暂停任务",
)
def pause_task(
    task_id: UUID,
    request: TaskControlRequest,
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskStateActionResponse:
    """Move one task into the explicit `paused` state."""

    try:
        result = task_service.pause_task(task_id, reason=request.reason)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    return TaskStateActionResponse.from_result(result)


@router.post(
    "/{task_id}/resume",
    response_model=TaskStateActionResponse,
    summary="恢复暂停任务",
)
def resume_task(
    task_id: UUID,
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskStateActionResponse:
    """Resume one paused task."""

    try:
        result = task_service.resume_task(task_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    return TaskStateActionResponse.from_result(result)


@router.post(
    "/{task_id}/request-human",
    response_model=TaskStateActionResponse,
    summary="请求人工处理",
)
def request_human_review(
    task_id: UUID,
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskStateActionResponse:
    """Move one task into the explicit `waiting_human` state."""

    try:
        result = task_service.request_human_review(task_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    return TaskStateActionResponse.from_result(result)


@router.post(
    "/{task_id}/resolve-human",
    response_model=TaskStateActionResponse,
    summary="恢复人工处理任务",
)
def resolve_human_review(
    task_id: UUID,
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskStateActionResponse:
    """Resolve one `waiting_human` task back into routing."""

    try:
        result = task_service.resolve_human_review(task_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    return TaskStateActionResponse.from_result(result)


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="获取任务详情",
)
def get_task(
    task_id: UUID,
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    """Return one task by ID."""

    task = task_service.get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    return TaskResponse.from_task(task)
