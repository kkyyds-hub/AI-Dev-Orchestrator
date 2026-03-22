"""Planner endpoints for draft generation and bulk task creation."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain.change_plan import (
    ChangePlan,
    ChangePlanStatus,
    ChangePlanTargetFile,
    ChangePlanVersion,
)
from app.domain.deliverable import Deliverable
from app.domain.project_role import ProjectRoleCode
from app.domain.project import Project, ProjectStage, ProjectStatus
from app.domain.task import TaskHumanStatus, TaskPriority, TaskRiskLevel, TaskStatus
from app.repositories.change_plan_repository import ChangePlanRepository
from app.repositories.deliverable_repository import DeliverableRepository
from app.repositories.project_role_repository import ProjectRoleRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.budget_guard_service import BudgetGuardService
from app.services.change_plan_service import (
    ChangePlanDeliverableNotFoundError,
    ChangePlanDetail,
    ChangePlanNotFoundError,
    ChangePlanProjectNotFoundError,
    ChangePlanService,
    ChangePlanSummary,
    ChangePlanTaskNotFoundError,
    ChangePlanVersionView,
)
from app.services.planner_service import (
    PlanApplyResult,
    PlanDraft,
    PlannedProjectDraft,
    PlannedTaskDraft,
    PlannerService,
)
from app.services.project_service import ProjectService
from app.services.role_catalog_service import RoleCatalogService
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


class PlannerProjectDraftRequest(BaseModel):
    """Editable project draft used by the Day03 planning flow."""

    name: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=2_000)
    status: ProjectStatus = Field(default=ProjectStatus.ACTIVE)
    stage: ProjectStage = Field(default=ProjectStage.PLANNING)

    def to_service_model(self) -> PlannedProjectDraft:
        """Convert the API DTO into the planner service model."""

        return PlannedProjectDraft(
            name=self.name,
            summary=self.summary,
            status=self.status,
            stage=self.stage,
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
    project_id: UUID | None = Field(
        default=None,
        description="Optional existing project ID used as the target project.",
    )
    project: PlannerProjectDraftRequest | None = Field(
        default=None,
        description="Optional new project draft created before mapping tasks.",
    )
    tasks: list[PlannerTaskDraftRequest] = Field(
        min_length=1,
        max_length=10,
        description="Edited or accepted draft tasks to persist as real tasks.",
    )


class PlannerProjectDraftResponse(BaseModel):
    """Project draft returned by the Day03 planner entry."""

    name: str
    summary: str
    status: ProjectStatus
    stage: ProjectStage

    @classmethod
    def from_service_model(
        cls,
        project_draft: PlannedProjectDraft,
    ) -> "PlannerProjectDraftResponse":
        """Convert one planner-side project draft into an API DTO."""

        return cls(
            name=project_draft.name,
            summary=project_draft.summary,
            status=project_draft.status,
            stage=project_draft.stage,
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
    project: PlannerProjectDraftResponse | None = None

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
            project=(
                PlannerProjectDraftResponse.from_service_model(plan_draft.project)
                if plan_draft.project is not None
                else None
            ),
        )


class PlannerAppliedProjectResponse(BaseModel):
    """Target project returned after applying one planning draft."""

    id: UUID
    name: str
    summary: str
    status: ProjectStatus
    stage: ProjectStage

    @classmethod
    def from_project(cls, project: Project) -> "PlannerAppliedProjectResponse":
        """Convert one project domain object into an API DTO."""

        return cls(
            id=project.id,
            name=project.name,
            summary=project.summary,
            status=project.status,
            stage=project.stage,
        )


class PlannerCreatedTaskResponse(BaseModel):
    """Created task returned after applying a plan draft."""

    draft_id: str
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


class PlannerApplyResponse(BaseModel):
    """Response returned after applying one plan draft."""

    project_summary: str
    created_count: int
    tasks: list[PlannerCreatedTaskResponse]
    project: PlannerAppliedProjectResponse | None = None

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
            project=(
                PlannerAppliedProjectResponse.from_project(result.project)
                if result.project is not None
                else None
            ),
        )


class ChangePlanTargetFileRequest(BaseModel):
    """One target file submitted with a Day06 change-plan draft."""

    relative_path: str = Field(min_length=1, max_length=1_000)
    language: str = Field(min_length=1, max_length=100)
    file_type: str = Field(min_length=1, max_length=50)
    rationale: str | None = Field(default=None, max_length=300)
    match_reasons: list[str] = Field(default_factory=list, max_length=20)

    def to_domain_model(self) -> ChangePlanTargetFile:
        """Convert one API DTO into the change-plan target-file model."""

        return ChangePlanTargetFile(
            relative_path=self.relative_path,
            language=self.language,
            file_type=self.file_type,
            rationale=self.rationale,
            match_reasons=self.match_reasons,
        )


class ChangePlanTargetFileResponse(BaseModel):
    """One target-file item returned with a Day06 change-plan version."""

    relative_path: str
    language: str
    file_type: str
    rationale: str | None = None
    match_reasons: list[str]

    @classmethod
    def from_target_file(
        cls,
        target_file: ChangePlanTargetFile,
    ) -> "ChangePlanTargetFileResponse":
        """Convert one domain target file into an API DTO."""

        return cls(
            relative_path=target_file.relative_path,
            language=target_file.language,
            file_type=target_file.file_type,
            rationale=target_file.rationale,
            match_reasons=list(target_file.match_reasons),
        )


class ChangePlanDraftRequest(BaseModel):
    """Shared request fields used to create or append one Day06 draft version."""

    title: str | None = Field(default=None, max_length=200)
    primary_deliverable_id: UUID | None = None
    related_deliverable_ids: list[UUID] = Field(min_length=1, max_length=10)
    intent_summary: str = Field(min_length=1, max_length=2_000)
    source_summary: str = Field(min_length=1, max_length=1_200)
    focus_terms: list[str] = Field(default_factory=list, max_length=20)
    target_files: list[ChangePlanTargetFileRequest] = Field(min_length=1, max_length=30)
    expected_actions: list[str] = Field(min_length=1, max_length=20)
    risk_notes: list[str] = Field(min_length=1, max_length=20)
    verification_commands: list[str] = Field(min_length=1, max_length=20)
    context_pack_generated_at: datetime | None = None


class ChangePlanCreateRequest(ChangePlanDraftRequest):
    """Request body used to create one new change-plan head."""

    task_id: UUID


class ChangePlanVersionCreateRequest(ChangePlanDraftRequest):
    """Request body used to append one new immutable draft version."""


class ChangePlanLinkedDeliverableResponse(BaseModel):
    """One resolved deliverable attached to a change-plan version."""

    deliverable_id: UUID
    title: str
    type: str
    current_version_number: int

    @classmethod
    def from_deliverable(
        cls,
        deliverable: Deliverable,
    ) -> "ChangePlanLinkedDeliverableResponse":
        """Convert one deliverable into a minimal API DTO."""

        return cls(
            deliverable_id=deliverable.id,
            title=deliverable.title,
            type=deliverable.type.value,
            current_version_number=deliverable.current_version_number,
        )


class ChangePlanVersionResponse(BaseModel):
    """One immutable Day06 change-plan version returned by the API."""

    id: UUID
    version_number: int
    intent_summary: str
    source_summary: str
    focus_terms: list[str]
    target_files: list[ChangePlanTargetFileResponse]
    expected_actions: list[str]
    risk_notes: list[str]
    verification_commands: list[str]
    related_deliverables: list[ChangePlanLinkedDeliverableResponse]
    context_pack_generated_at: datetime | None = None
    created_at: datetime

    @classmethod
    def from_version_view(
        cls,
        item: ChangePlanVersionView,
    ) -> "ChangePlanVersionResponse":
        """Convert one service-layer version view into an API DTO."""

        return cls(
            id=item.version.id,
            version_number=item.version.version_number,
            intent_summary=item.version.intent_summary,
            source_summary=item.version.source_summary,
            focus_terms=list(item.version.focus_terms),
            target_files=[
                ChangePlanTargetFileResponse.from_target_file(target_file)
                for target_file in item.version.target_files
            ],
            expected_actions=list(item.version.expected_actions),
            risk_notes=list(item.version.risk_notes),
            verification_commands=list(item.version.verification_commands),
            related_deliverables=[
                ChangePlanLinkedDeliverableResponse.from_deliverable(deliverable)
                for deliverable in item.related_deliverables
            ],
            context_pack_generated_at=item.version.context_pack_generated_at,
            created_at=item.version.created_at,
        )


class ChangePlanSummaryResponse(BaseModel):
    """Project-scoped change-plan summary row returned to the frontend."""

    id: UUID
    project_id: UUID
    task_id: UUID
    task_title: str
    status: ChangePlanStatus
    title: str
    primary_deliverable_id: UUID | None = None
    current_version_number: int
    latest_version: ChangePlanVersionResponse
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_summary(
        cls,
        item: ChangePlanSummary,
    ) -> "ChangePlanSummaryResponse":
        """Convert one service-layer summary into an API DTO."""

        return cls(
            id=item.change_plan.id,
            project_id=item.change_plan.project_id,
            task_id=item.change_plan.task_id,
            task_title=item.task.title,
            status=item.change_plan.status,
            title=item.change_plan.title,
            primary_deliverable_id=item.change_plan.primary_deliverable_id,
            current_version_number=item.change_plan.current_version_number,
            latest_version=ChangePlanVersionResponse.from_version_view(item.latest_version),
            created_at=item.change_plan.created_at,
            updated_at=item.change_plan.updated_at,
        )


class ChangePlanDetailResponse(ChangePlanSummaryResponse):
    """Full Day06 change-plan detail returned for one plan thread."""

    versions: list[ChangePlanVersionResponse]

    @classmethod
    def from_detail(
        cls,
        detail: ChangePlanDetail,
    ) -> "ChangePlanDetailResponse":
        """Convert one service-layer detail into an API DTO."""

        latest_version = detail.versions[0]
        return cls(
            id=detail.change_plan.id,
            project_id=detail.change_plan.project_id,
            task_id=detail.change_plan.task_id,
            task_title=detail.task.title,
            status=detail.change_plan.status,
            title=detail.change_plan.title,
            primary_deliverable_id=detail.change_plan.primary_deliverable_id,
            current_version_number=detail.change_plan.current_version_number,
            latest_version=ChangePlanVersionResponse.from_version_view(latest_version),
            created_at=detail.change_plan.created_at,
            updated_at=detail.change_plan.updated_at,
            versions=[
                ChangePlanVersionResponse.from_version_view(version)
                for version in detail.versions
            ],
        )


def get_planner_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> PlannerService:
    """Create the planner dependency."""

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
    task_service = TaskService(
        task_repository=task_repository,
        project_repository=project_repository,
        budget_guard_service=budget_guard_service,
        task_state_machine_service=task_state_machine_service,
        role_catalog_service=role_catalog_service,
    )
    project_service = ProjectService(project_repository=project_repository)
    return PlannerService(
        task_service=task_service,
        project_service=project_service,
    )


def get_change_plan_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ChangePlanService:
    """Create the Day06 change-plan dependency."""

    return ChangePlanService(
        change_plan_repository=ChangePlanRepository(session),
        project_repository=ProjectRepository(session),
        task_repository=TaskRepository(session),
        deliverable_repository=DeliverableRepository(session),
    )


router = APIRouter(prefix="/planning", tags=["planning"])


@router.post(
    "/drafts",
    response_model=PlannerDraftResponse,
    summary="Create planning draft",
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
    summary="Apply planning draft",
)
def apply_plan_draft(
    request: PlannerApplyRequest,
    planner_service: Annotated[PlannerService, Depends(get_planner_service)],
) -> PlannerApplyResponse:
    """Persist one reviewed planner draft as actual tasks."""

    try:
        result = planner_service.apply_plan_draft(
            project_summary=request.project_summary,
            project_id=request.project_id,
            project_draft=(
                request.project.to_service_model() if request.project is not None else None
            ),
            task_drafts=[task.to_service_model() for task in request.tasks],
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return PlannerApplyResponse.from_service_model(result)


@router.post(
    "/projects/{project_id}/change-plans",
    response_model=ChangePlanDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create one Day06 change-plan draft",
)
def create_project_change_plan(
    project_id: UUID,
    request: ChangePlanCreateRequest,
    change_plan_service: Annotated[
        ChangePlanService,
        Depends(get_change_plan_service),
    ],
) -> ChangePlanDetailResponse:
    """Create one new project change-plan head with its initial immutable draft."""

    try:
        detail = change_plan_service.create_change_plan(
            project_id=project_id,
            task_id=request.task_id,
            title=request.title,
            primary_deliverable_id=request.primary_deliverable_id,
            related_deliverable_ids=request.related_deliverable_ids,
            intent_summary=request.intent_summary,
            source_summary=request.source_summary,
            focus_terms=request.focus_terms,
            target_files=[
                target_file.to_domain_model() for target_file in request.target_files
            ],
            expected_actions=request.expected_actions,
            risk_notes=request.risk_notes,
            verification_commands=request.verification_commands,
            context_pack_generated_at=request.context_pack_generated_at,
        )
    except (
        ChangePlanProjectNotFoundError,
        ChangePlanTaskNotFoundError,
        ChangePlanDeliverableNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return ChangePlanDetailResponse.from_detail(detail)


@router.get(
    "/projects/{project_id}/change-plans",
    response_model=list[ChangePlanSummaryResponse],
    summary="List Day06 change-plan drafts for one project",
)
def list_project_change_plans(
    project_id: UUID,
    change_plan_service: Annotated[
        ChangePlanService,
        Depends(get_change_plan_service),
    ],
    task_id: UUID | None = None,
) -> list[ChangePlanSummaryResponse]:
    """List project change-plan summaries and optional task-scoped mappings."""

    try:
        items = change_plan_service.list_change_plans(
            project_id=project_id,
            task_id=task_id,
        )
    except (ChangePlanProjectNotFoundError, ChangePlanTaskNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return [ChangePlanSummaryResponse.from_summary(item) for item in items]


@router.get(
    "/change-plans/{change_plan_id}",
    response_model=ChangePlanDetailResponse,
    summary="Get one Day06 change-plan detail",
)
def get_change_plan_detail(
    change_plan_id: UUID,
    change_plan_service: Annotated[
        ChangePlanService,
        Depends(get_change_plan_service),
    ],
) -> ChangePlanDetailResponse:
    """Return one change-plan head and all immutable draft versions."""

    try:
        detail = change_plan_service.get_change_plan_detail(change_plan_id)
    except (ChangePlanNotFoundError, ChangePlanTaskNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return ChangePlanDetailResponse.from_detail(detail)


@router.post(
    "/change-plans/{change_plan_id}/versions",
    response_model=ChangePlanDetailResponse,
    summary="Append one Day06 change-plan draft version",
)
def append_change_plan_version(
    change_plan_id: UUID,
    request: ChangePlanVersionCreateRequest,
    change_plan_service: Annotated[
        ChangePlanService,
        Depends(get_change_plan_service),
    ],
) -> ChangePlanDetailResponse:
    """Append one immutable draft version to an existing change-plan thread."""

    try:
        detail = change_plan_service.append_change_plan_version(
            change_plan_id=change_plan_id,
            title=request.title,
            primary_deliverable_id=request.primary_deliverable_id,
            related_deliverable_ids=request.related_deliverable_ids,
            intent_summary=request.intent_summary,
            source_summary=request.source_summary,
            focus_terms=request.focus_terms,
            target_files=[
                target_file.to_domain_model() for target_file in request.target_files
            ],
            expected_actions=request.expected_actions,
            risk_notes=request.risk_notes,
            verification_commands=request.verification_commands,
            context_pack_generated_at=request.context_pack_generated_at,
        )
    except (
        ChangePlanNotFoundError,
        ChangePlanTaskNotFoundError,
        ChangePlanDeliverableNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return ChangePlanDetailResponse.from_detail(detail)
