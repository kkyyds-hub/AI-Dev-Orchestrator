"""Task endpoints."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain.run import Run, RunStatus
from app.domain.task import Task, TaskPriority, TaskStatus
from app.repositories.task_repository import TaskRepository
from app.services.console_service import ConsoleOverview, ConsoleService, ConsoleTaskItem
from app.services.task_service import TaskService


class TaskCreateRequest(BaseModel):
    """DTO for task creation requests."""

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


class TaskResponse(BaseModel):
    """Basic task response DTO."""

    id: UUID
    title: str
    status: TaskStatus
    priority: TaskPriority
    input_summary: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_task(cls, task: Task) -> "TaskResponse":
        """Convert the domain task into an API DTO."""

        return cls(
            id=task.id,
            title=task.title,
            status=task.status,
            priority=task.priority,
            input_summary=task.input_summary,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )


class TaskConsoleRunResponse(BaseModel):
    """Latest run details used by the Day 10 console homepage."""

    id: UUID
    status: RunStatus
    result_summary: str | None = None
    prompt_tokens: int
    completion_tokens: int
    estimated_cost: float
    log_path: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime

    @classmethod
    def from_run(cls, run: Run) -> "TaskConsoleRunResponse":
        """Convert a domain run into a console response DTO."""

        return cls(
            id=run.id,
            status=run.status,
            result_summary=run.result_summary,
            prompt_tokens=run.prompt_tokens,
            completion_tokens=run.completion_tokens,
            estimated_cost=run.estimated_cost,
            log_path=run.log_path,
            started_at=run.started_at,
            finished_at=run.finished_at,
            created_at=run.created_at,
        )


class TaskConsoleItemResponse(BaseModel):
    """Task row used by the Day 10 console homepage."""

    id: UUID
    title: str
    status: TaskStatus
    priority: TaskPriority
    input_summary: str
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
            created_at=item.task.created_at,
            updated_at=item.task.updated_at,
            latest_run=(
                TaskConsoleRunResponse.from_run(item.latest_run)
                if item.latest_run is not None
                else None
            ),
        )


class ConsoleOverviewResponse(BaseModel):
    """Aggregated homepage payload for the Day 10 console."""

    total_tasks: int
    pending_tasks: int
    running_tasks: int
    completed_tasks: int
    failed_tasks: int
    blocked_tasks: int
    total_estimated_cost: float
    total_prompt_tokens: int
    total_completion_tokens: int
    tasks: list[TaskConsoleItemResponse]

    @classmethod
    def from_overview(cls, overview: ConsoleOverview) -> "ConsoleOverviewResponse":
        """Convert service output into an API response DTO."""

        return cls(
            total_tasks=overview.total_tasks,
            pending_tasks=overview.pending_tasks,
            running_tasks=overview.running_tasks,
            completed_tasks=overview.completed_tasks,
            failed_tasks=overview.failed_tasks,
            blocked_tasks=overview.blocked_tasks,
            total_estimated_cost=overview.total_estimated_cost,
            total_prompt_tokens=overview.total_prompt_tokens,
            total_completion_tokens=overview.total_completion_tokens,
            tasks=[TaskConsoleItemResponse.from_item(item) for item in overview.tasks],
        )


def build_task_responses(tasks: list[Task]) -> list[TaskResponse]:
    """Convert a list of domain tasks into API DTOs."""

    return [TaskResponse.from_task(task) for task in tasks]


def get_task_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> TaskService:
    """Create the task service dependency."""

    task_repository = TaskRepository(session)
    return TaskService(task_repository=task_repository)


def get_console_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ConsoleService:
    """Create the console service dependency."""

    task_repository = TaskRepository(session)
    return ConsoleService(task_repository=task_repository)


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

    task = task_service.create_task(
        title=request.title,
        input_summary=request.input_summary,
        priority=request.priority,
    )
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
