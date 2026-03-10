"""Planner endpoints for draft generation and bulk task creation."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain.task import TaskHumanStatus, TaskPriority, TaskRiskLevel, TaskStatus
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.budget_guard_service import BudgetGuardService
from app.services.planner_service import (
    PlanApplyResult,
    PlanDraft,
    PlannedTaskDraft,
    PlannerService,
)
from app.services.task_service import TaskService
from app.services.task_state_machine_service import TaskStateMachineService


class PlannerDraftRequest(BaseModel):
    """Request body for generating one heuristic task plan."""

    brief: str = Field(
        min_length=1,
        max_length=5_000,
        description="Project brief or problem statement used to derive task drafts.",
    )
    max_tasks: int = Field(
        default=6,
        ge=3,
        le=10,
        description="Maximum number of draft tasks to generate.",
    )


class PlannerTaskDraftRequest(BaseModel):
    """One editable task draft used by the apply endpoint."""

    draft_id: str = Field(
        min_length=1,
        max_length=50,
        description="Stable draft identifier returned by the planner.",
    )
    title: str = Field(min_length=1, max_length=200)
    input_summary: str = Field(min_length=1, max_length=2_000)
    priority: TaskPriority = Field(default=TaskPriority.NORMAL)
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=10)
    depends_on_draft_ids: list[str] = Field(default_factory=list, max_length=20)
    risk_level: TaskRiskLevel = Field(default=TaskRiskLevel.NORMAL)
    human_status: TaskHumanStatus = Field(default=TaskHumanStatus.NONE)
    paused_reason: str | None = Field(default=None, max_length=500)

    def to_service_model(self) -> PlannedTaskDraft:
        """Convert the API DTO into the planner service model."""

        return PlannedTaskDraft(
            draft_id=self.draft_id.strip(),
            title=self.title,
            input_summary=self.input_summary,
            priority=self.priority,
            acceptance_criteria=self.acceptance_criteria,
            depends_on_draft_ids=self.depends_on_draft_ids,
            risk_level=self.risk_level,
            human_status=self.human_status,
            paused_reason=self.paused_reason,
        )


class PlannerApplyRequest(BaseModel):
    """Request body for persisting a previously reviewed task draft."""

    project_summary: str = Field(
        min_length=1,
        max_length=2_000,
        description="Reviewed project summary returned by the draft endpoint.",
    )
    tasks: list[PlannerTaskDraftRequest] = Field(
        min_length=1,
        max_length=10,
        description="Edited or accepted draft tasks to persist as real tasks.",
    )


class PlannerTaskDraftResponse(BaseModel):
    """Task draft returned by the planner."""

    draft_id: str
    title: str
    input_summary: str
    priority: TaskPriority
    acceptance_criteria: list[str]
    depends_on_draft_ids: list[str]
    risk_level: TaskRiskLevel
    human_status: TaskHumanStatus
    paused_reason: str | None = None

    @classmethod
    def from_service_model(cls, draft: PlannedTaskDraft) -> "PlannerTaskDraftResponse":
        """Convert one planner draft into an API response."""

        return cls(
            draft_id=draft.draft_id,
            title=draft.title,
            input_summary=draft.input_summary,
            priority=draft.priority,
            acceptance_criteria=draft.acceptance_criteria,
            depends_on_draft_ids=draft.depends_on_draft_ids,
            risk_level=draft.risk_level,
            human_status=draft.human_status,
            paused_reason=draft.paused_reason,
        )


class PlannerDraftResponse(BaseModel):
    """Response returned after generating one task draft."""

    project_summary: str
    planning_notes: list[str]
    tasks: list[PlannerTaskDraftResponse]

    @classmethod
    def from_service_model(cls, plan_draft: PlanDraft) -> "PlannerDraftResponse":
        """Convert one planner draft aggregate into an API DTO."""

        return cls(
            project_summary=plan_draft.project_summary,
            planning_notes=plan_draft.planning_notes,
            tasks=[
                PlannerTaskDraftResponse.from_service_model(task)
                for task in plan_draft.tasks
            ],
        )


class PlannerCreatedTaskResponse(BaseModel):
    """Created task returned after applying a plan draft."""

    draft_id: str
    id: UUID
    title: str
    status: TaskStatus
    priority: TaskPriority
    input_summary: str
    acceptance_criteria: list[str]
    depends_on_task_ids: list[UUID]
    risk_level: TaskRiskLevel
    human_status: TaskHumanStatus
    paused_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_result(
        cls,
        *,
        draft_id: str,
        task,
    ) -> "PlannerCreatedTaskResponse":
        """Convert one persisted task into an API DTO."""

        return cls(
            draft_id=draft_id,
            id=task.id,
            title=task.title,
            status=task.status,
            priority=task.priority,
            input_summary=task.input_summary,
            acceptance_criteria=task.acceptance_criteria,
            depends_on_task_ids=task.depends_on_task_ids,
            risk_level=task.risk_level,
            human_status=task.human_status,
            paused_reason=task.paused_reason,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )


class PlannerApplyResponse(BaseModel):
    """Response returned after applying one plan draft."""

    project_summary: str
    created_count: int
    tasks: list[PlannerCreatedTaskResponse]

    @classmethod
    def from_service_model(cls, result: PlanApplyResult) -> "PlannerApplyResponse":
        """Convert one apply result into an API DTO."""

        return cls(
            project_summary=result.project_summary,
            created_count=len(result.created_tasks),
            tasks=[
                PlannerCreatedTaskResponse.from_result(
                    draft_id=created_task.draft_id,
                    task=created_task.task,
                )
                for created_task in result.created_tasks
            ],
        )


def get_planner_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> PlannerService:
    """Create the planner dependency."""

    task_repository = TaskRepository(session)
    run_repository = RunRepository(session)
    budget_guard_service = BudgetGuardService(run_repository=run_repository)
    task_state_machine_service = TaskStateMachineService()
    task_service = TaskService(
        task_repository=task_repository,
        budget_guard_service=budget_guard_service,
        task_state_machine_service=task_state_machine_service,
    )
    return PlannerService(task_service=task_service)


router = APIRouter(prefix="/planning", tags=["planning"])


@router.post(
    "/drafts",
    response_model=PlannerDraftResponse,
    summary="生成最小规划草案",
)
def create_plan_draft(
    request: PlannerDraftRequest,
    planner_service: Annotated[PlannerService, Depends(get_planner_service)],
) -> PlannerDraftResponse:
    """Generate one heuristic task draft from a brief."""

    try:
        plan_draft = planner_service.generate_plan_draft(
            brief=request.brief,
            max_tasks=request.max_tasks,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return PlannerDraftResponse.from_service_model(plan_draft)


@router.post(
    "/apply",
    response_model=PlannerApplyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="应用规划草案并批量创建任务",
)
def apply_plan_draft(
    request: PlannerApplyRequest,
    planner_service: Annotated[PlannerService, Depends(get_planner_service)],
) -> PlannerApplyResponse:
    """Persist one reviewed planner draft as actual tasks."""

    try:
        result = planner_service.apply_plan_draft(
            project_summary=request.project_summary,
            task_drafts=[task.to_service_model() for task in request.tasks],
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return PlannerApplyResponse.from_service_model(result)
