"""Day11 agent-thread APIs for Day12 timeline/intervention consumption."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain.agent_message import AgentMessage
from app.domain.agent_session import AgentSession
from app.domain.worktree_cleanup import (
    WorktreeCleanupCommandPreview,
    WorktreeCleanupPreflight,
    WorktreeCleanupResult,
)
from app.domain.worktree_create import WorktreeCreateResult, WorktreeWriteCommandPreview
from app.domain.worktree_plan import WorktreePlan
from app.domain.worktree_plan_confirmation import WorktreePlanConfirmationReceipt
from app.domain.worktree_prepare import WorktreeGitPreflight, WorktreePrepareResult
from app.repositories.agent_message_repository import AgentMessageRepository
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.repository_workspace_repository import RepositoryWorkspaceRepository
from app.services.agent_conversation_service import AgentConversationService
from app.services.worktree_cleanup_service import (
    WorktreeCleanupError,
    WorktreeCleanupHashMismatchError,
    WorktreeCleanupRequest,
    WorktreeCleanupService,
)
from app.services.worktree_create_service import (
    WorktreeCreateError,
    WorktreeCreateHashMismatchError,
    WorktreeCreateRequest,
    WorktreeCreateService,
)
from app.services.worktree_prepare_service import (
    WorktreePrepareError,
    WorktreePrepareHashMismatchError,
    WorktreePrepareRequest,
    WorktreePrepareService,
)
from app.services.worktree_plan_confirmation_service import (
    WorktreePlanConfirmationError,
    WorktreePlanConfirmationRequest,
    WorktreePlanConfirmationService,
    WorktreePlanHashMismatchError,
)
from app.services.worktree_plan_service import WorktreePlanService


class AgentSessionResponse(BaseModel):
    """Day12-consumable agent-thread session snapshot."""

    session_id: UUID
    project_id: UUID
    task_id: UUID
    run_id: UUID
    session_status: str
    review_status: str
    current_phase: str
    owner_role_code: str | None = None
    context_checkpoint_id: str | None = None
    context_rehydrated: bool
    latest_intervention_type: str | None = None
    latest_note_event_type: str | None = None
    summary: str | None = None
    agent_type: str | None = None
    runtime_type: str | None = None
    runtime_handle_id: str | None = None
    coding_status: str | None = None
    activity_state: str | None = None
    branch_name: str | None = None
    workspace_type: str | None = None
    workspace_path: str | None = None
    workspace_clean: bool | None = None
    last_workspace_error: str | None = None
    started_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None

    @classmethod
    def from_session(cls, session: AgentSession) -> "AgentSessionResponse":
        """Convert one domain session into API DTO."""

        return cls(
            session_id=session.id,
            project_id=session.project_id,
            task_id=session.task_id,
            run_id=session.run_id,
            session_status=session.status.value,
            review_status=session.review_status.value,
            current_phase=session.current_phase.value,
            owner_role_code=(
                session.owner_role_code.value if session.owner_role_code is not None else None
            ),
            context_checkpoint_id=session.context_checkpoint_id,
            context_rehydrated=session.context_rehydrated,
            latest_intervention_type=session.latest_intervention_type,
            latest_note_event_type=session.latest_note_event_type,
            summary=session.summary,
            agent_type=session.agent_type.value if session.agent_type is not None else None,
            runtime_type=(
                session.runtime_type.value if session.runtime_type is not None else None
            ),
            runtime_handle_id=session.runtime_handle_id,
            coding_status=(
                session.coding_status.value if session.coding_status is not None else None
            ),
            activity_state=(
                session.activity_state.value if session.activity_state is not None else None
            ),
            branch_name=session.branch_name,
            workspace_type=(
                session.workspace_type.value if session.workspace_type is not None else None
            ),
            workspace_path=session.workspace_path,
            workspace_clean=session.workspace_clean,
            last_workspace_error=session.last_workspace_error,
            started_at=session.started_at,
            updated_at=session.updated_at,
            finished_at=session.finished_at,
        )


class AgentMessageResponse(BaseModel):
    """Day12-consumable timeline message contract."""

    message_id: UUID
    session_id: UUID
    project_id: UUID
    task_id: UUID
    run_id: UUID
    sequence_no: int
    role: str
    message_type: str
    event_type: str
    phase: str | None = None
    state_from: str | None = None
    state_to: str | None = None
    intervention_type: str | None = None
    note_event_type: str | None = None
    context_checkpoint_id: str | None = None
    context_rehydrated: bool | None = None
    content_summary: str
    content_detail: str | None = None
    created_at: datetime

    @classmethod
    def from_message(cls, message: AgentMessage) -> "AgentMessageResponse":
        """Convert one domain message into API DTO."""

        return cls(
            message_id=message.id,
            session_id=message.session_id,
            project_id=message.project_id,
            task_id=message.task_id,
            run_id=message.run_id,
            sequence_no=message.sequence_no,
            role=message.role.value,
            message_type=message.message_type.value,
            event_type=message.event_type,
            phase=message.phase,
            state_from=message.state_from,
            state_to=message.state_to,
            intervention_type=message.intervention_type,
            note_event_type=message.note_event_type,
            context_checkpoint_id=message.context_checkpoint_id,
            context_rehydrated=message.context_rehydrated,
            content_summary=message.content_summary,
            content_detail=message.content_detail,
            created_at=message.created_at,
        )


class AgentTimelineResponse(BaseModel):
    """Project/session timeline replay payload."""

    project_id: UUID
    session_id: UUID | None = None
    total_messages: int
    messages: list[AgentMessageResponse] = Field(default_factory=list)


class AgentInterventionResponse(BaseModel):
    """Boss intervention/note-event feed payload."""

    project_id: UUID
    session_id: UUID | None = None
    total_items: int
    items: list[AgentMessageResponse] = Field(default_factory=list)


class AgentInterventionWriteRequest(BaseModel):
    """Formal session-level boss intervention write contract."""

    intervention_type: str = Field(min_length=1, max_length=80)
    note_event_type: str | None = Field(default=None, max_length=80)
    content_summary: str = Field(min_length=1, max_length=2_000)
    content_detail: str | None = Field(default=None, max_length=4_000)


class AgentInterventionWriteResponse(BaseModel):
    """Write-ack payload returned after persisting one boss intervention."""

    project_id: UUID
    session_id: UUID
    session: AgentSessionResponse
    intervention_message: AgentMessageResponse


class WorktreePlanResponse(BaseModel):
    """Dry-run preview for a future per-session worktree."""

    agent_session_id: UUID
    project_id: UUID
    repository_workspace_id: UUID | None = None
    safe: bool
    dry_run: bool
    requires_user_confirmation: bool
    plan_hash: str
    workspace_type: str
    worktree_path: str | None = None
    branch_name: str | None = None
    base_branch: str | None = None
    base_commit_sha: str | None = None
    git_commands_to_run: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def from_plan(cls, plan: WorktreePlan) -> "WorktreePlanResponse":
        """Convert domain plan to API DTO."""

        return cls(**plan.model_dump())


class WorktreePlanConfirmationRequestBody(BaseModel):
    """Explicit user confirmation body for one current workspace plan hash."""

    plan_hash: str = Field(min_length=64, max_length=64)
    user_confirmed: bool = True
    confirmed_by: str | None = Field(default=None, max_length=200)


class WorktreePlanConfirmationReceiptResponse(BaseModel):
    """Receipt returned after accepting a dry-run workspace plan confirmation."""

    agent_session_id: UUID
    project_id: UUID
    repository_workspace_id: UUID | None = None
    plan_hash: str
    confirmed_plan_hash: str
    confirmation_status: str
    confirmation_scope: str
    dry_run: bool
    requires_user_confirmation: bool
    worktree_path: str | None = None
    branch_name: str | None = None
    base_branch: str | None = None
    base_commit_sha: str | None = None
    confirmed_by: str | None = None
    confirmed_at: datetime
    next_action: str
    creates_worktree: bool
    creates_branch: bool
    mutates_agent_session_workspace: bool

    @classmethod
    def from_receipt(
        cls,
        receipt: WorktreePlanConfirmationReceipt,
    ) -> "WorktreePlanConfirmationReceiptResponse":
        """Convert domain receipt to API DTO."""

        return cls(**receipt.model_dump())


class WorktreePrepareRequestBody(BaseModel):
    """Request body for the blocked P1-D-C workspace prepare skeleton."""

    plan_hash: str = Field(min_length=64, max_length=64)
    user_confirmed: bool = True


class WorktreeGitPreflightResponse(BaseModel):
    """Read-only git preflight details for future workspace prepare execution."""

    preflight_status: str
    read_only: bool
    commands_run: list[str] = Field(default_factory=list)
    repository_is_git_worktree: bool | None = None
    repository_head_sha: str | None = None
    repository_clean: bool | None = None
    planned_branch_exists: bool | None = None
    planned_worktree_registered: bool | None = None
    registered_worktree_paths: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def from_preflight(
        cls,
        preflight: WorktreeGitPreflight,
    ) -> "WorktreeGitPreflightResponse":
        """Convert domain preflight to API DTO."""

        return cls(**preflight.model_dump())


class WorktreePrepareResponse(BaseModel):
    """Blocked response for future real workspace prepare execution."""

    agent_session_id: UUID
    project_id: UUID
    repository_workspace_id: UUID | None = None
    plan_hash: str
    submitted_plan_hash: str
    prepare_status: str
    blocked_reason: str
    dry_run: bool
    requires_user_confirmation: bool
    worktree_path: str | None = None
    branch_name: str | None = None
    base_branch: str | None = None
    base_commit_sha: str | None = None
    checked_at: datetime
    git_preflight: WorktreeGitPreflightResponse | None = None
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_action: str
    creates_worktree: bool
    creates_branch: bool
    runs_git: bool
    runs_write_git: bool
    mutates_agent_session_workspace: bool

    @classmethod
    def from_result(cls, result: WorktreePrepareResult) -> "WorktreePrepareResponse":
        """Convert domain prepare result to API DTO."""

        payload = result.model_dump()
        if result.git_preflight is not None:
            payload["git_preflight"] = WorktreeGitPreflightResponse.from_preflight(
                result.git_preflight
            )
        return cls(**payload)


class WorktreeCreateRequestBody(BaseModel):
    """Request body for guarded P1-D-E-B workspace creation."""

    plan_hash: str = Field(min_length=64, max_length=64)
    user_confirmed: bool = True


class WorktreeWriteCommandPreviewResponse(BaseModel):
    """Disabled preview of one future write git command."""

    argv: tuple[str, ...]
    cwd: str
    timeout_seconds: int
    mutates_repository: bool
    command_kind: str
    execution_enabled: bool

    @classmethod
    def from_preview(
        cls,
        preview: WorktreeWriteCommandPreview,
    ) -> "WorktreeWriteCommandPreviewResponse":
        """Convert domain write command preview to API DTO."""

        return cls(**preview.model_dump())


class WorktreeCreateResponse(BaseModel):
    """Response for guarded real workspace create execution."""

    agent_session_id: UUID
    project_id: UUID
    repository_workspace_id: UUID | None = None
    plan_hash: str
    submitted_plan_hash: str
    create_status: str
    blocked_reason: str | None = None
    dry_run: bool
    requires_user_confirmation: bool
    worktree_path: str | None = None
    branch_name: str | None = None
    base_branch: str | None = None
    base_commit_sha: str | None = None
    checked_at: datetime
    git_preflight: WorktreeGitPreflightResponse | None = None
    write_command_preview: list[WorktreeWriteCommandPreviewResponse] = Field(
        default_factory=list
    )
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_action: str
    creates_worktree: bool
    creates_branch: bool
    runs_git: bool
    runs_write_git: bool
    mutates_agent_session_workspace: bool

    @classmethod
    def from_result(cls, result: WorktreeCreateResult) -> "WorktreeCreateResponse":
        """Convert domain create result to API DTO."""

        payload = result.model_dump()
        if result.git_preflight is not None:
            payload["git_preflight"] = WorktreeGitPreflightResponse.from_preflight(
                result.git_preflight
            )
        payload["write_command_preview"] = [
            WorktreeWriteCommandPreviewResponse.from_preview(item)
            for item in result.write_command_preview
        ]
        return cls(**payload)


class WorktreeCleanupRequestBody(BaseModel):
    """Request body for P1-E-C guarded workspace cleanup."""

    plan_hash: str = Field(min_length=64, max_length=64)
    user_confirmed: bool = True


class WorktreeCleanupCommandPreviewResponse(BaseModel):
    """Disabled preview of one future cleanup command."""

    argv: tuple[str, ...]
    cwd: str
    timeout_seconds: int
    mutates_repository: bool
    command_kind: str
    execution_enabled: bool

    @classmethod
    def from_preview(
        cls,
        preview: WorktreeCleanupCommandPreview,
    ) -> "WorktreeCleanupCommandPreviewResponse":
        """Convert domain cleanup command preview to API DTO."""

        return cls(**preview.model_dump())


class WorktreeCleanupPreflightResponse(BaseModel):
    """Read-only cleanup preflight details for the current session worktree."""

    preflight_status: str
    read_only: bool
    commands_run: list[str] = Field(default_factory=list)
    worktree_path_exists: bool | None = None
    worktree_path_is_directory: bool | None = None
    worktree_path_safe: bool | None = None
    worktree_registered: bool | None = None
    worktree_clean: bool | None = None
    repository_is_git_worktree: bool | None = None
    registered_worktree_paths: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def from_preflight(
        cls,
        preflight: WorktreeCleanupPreflight,
    ) -> "WorktreeCleanupPreflightResponse":
        """Convert domain cleanup preflight to API DTO."""

        return cls(**preflight.model_dump())


class WorktreeCleanupResponse(BaseModel):
    """Blocked response for future workspace cleanup execution."""

    agent_session_id: UUID
    project_id: UUID
    repository_workspace_id: UUID | None = None
    plan_hash: str
    submitted_plan_hash: str
    cleanup_status: str
    blocked_reason: str | None = None
    dry_run: bool
    requires_user_confirmation: bool
    worktree_path: str | None = None
    branch_name: str | None = None
    base_branch: str | None = None
    base_commit_sha: str | None = None
    checked_at: datetime
    cleanup_preflight: WorktreeCleanupPreflightResponse | None = None
    cleanup_command_preview: list[WorktreeCleanupCommandPreviewResponse] = Field(
        default_factory=list
    )
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_action: str
    removes_worktree: bool
    deletes_branch: bool
    deletes_directory: bool
    runs_git: bool
    runs_write_git: bool
    mutates_agent_session_workspace: bool

    @classmethod
    def from_result(cls, result: WorktreeCleanupResult) -> "WorktreeCleanupResponse":
        """Convert domain cleanup result to API DTO."""

        payload = result.model_dump()
        if result.cleanup_preflight is not None:
            payload["cleanup_preflight"] = (
                WorktreeCleanupPreflightResponse.from_preflight(
                    result.cleanup_preflight
                )
            )
        payload["cleanup_command_preview"] = [
            WorktreeCleanupCommandPreviewResponse.from_preview(item)
            for item in result.cleanup_command_preview
        ]
        return cls(**payload)


def get_agent_conversation_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> AgentConversationService:
    """Create Day11 conversation service dependency."""

    return AgentConversationService(
        agent_session_repository=AgentSessionRepository(session),
        agent_message_repository=AgentMessageRepository(session),
        repository_workspace_repository=RepositoryWorkspaceRepository(session),
    )


def get_worktree_plan_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> WorktreePlanService:
    """Create the P1-C dry-run worktree plan service dependency."""

    return WorktreePlanService(
        agent_session_repository=AgentSessionRepository(session),
        repository_workspace_repository=RepositoryWorkspaceRepository(session),
    )


def get_worktree_plan_confirmation_service(
    worktree_plan_service: Annotated[
        WorktreePlanService, Depends(get_worktree_plan_service)
    ],
) -> WorktreePlanConfirmationService:
    """Create the P1-D-B workspace plan confirmation dependency."""

    return WorktreePlanConfirmationService(
        worktree_plan_service=worktree_plan_service,
    )


def get_worktree_prepare_service(
    worktree_plan_service: Annotated[
        WorktreePlanService, Depends(get_worktree_plan_service)
    ],
) -> WorktreePrepareService:
    """Create the P1-D-C blocked workspace prepare dependency."""

    return WorktreePrepareService(
        worktree_plan_service=worktree_plan_service,
    )


def get_worktree_create_service(
    worktree_plan_service: Annotated[
        WorktreePlanService, Depends(get_worktree_plan_service)
    ],
) -> WorktreeCreateService:
    """Create the P1-D-E-B guarded workspace create dependency."""

    return WorktreeCreateService(
        worktree_plan_service=worktree_plan_service,
    )


def get_worktree_cleanup_service(
    worktree_plan_service: Annotated[
        WorktreePlanService, Depends(get_worktree_plan_service)
    ],
) -> WorktreeCleanupService:
    """Create the P1-E-C guarded workspace cleanup dependency."""

    return WorktreeCleanupService(
        worktree_plan_service=worktree_plan_service,
    )


router = APIRouter(prefix="/agent-threads", tags=["agent-threads"])


@router.post(
    "/sessions/{session_id}/workspace-plan",
    response_model=WorktreePlanResponse,
    summary="Build a dry-run worktree plan for one agent session",
)
def create_agent_session_workspace_plan(
    session_id: UUID,
    worktree_plan_service: Annotated[
        WorktreePlanService, Depends(get_worktree_plan_service)
    ],
) -> WorktreePlanResponse:
    """Return a pure dry-run plan; no git command or filesystem write is executed."""

    try:
        plan = worktree_plan_service.build_plan(agent_session_id=session_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return WorktreePlanResponse.from_plan(plan)


@router.get(
    "/sessions/{session_id}/workspace-plan",
    response_model=WorktreePlanResponse,
    summary="Read back the current dry-run worktree plan for one agent session",
)
def get_agent_session_workspace_plan(
    session_id: UUID,
    worktree_plan_service: Annotated[
        WorktreePlanService, Depends(get_worktree_plan_service)
    ],
) -> WorktreePlanResponse:
    """Recompute the current pure dry-run plan without mutating repository state."""

    return create_agent_session_workspace_plan(
        session_id=session_id,
        worktree_plan_service=worktree_plan_service,
    )


@router.post(
    "/sessions/{session_id}/workspace-plan/confirm",
    response_model=WorktreePlanConfirmationReceiptResponse,
    summary="Confirm the current dry-run workspace plan hash",
)
def confirm_agent_session_workspace_plan(
    session_id: UUID,
    request: WorktreePlanConfirmationRequestBody,
    confirmation_service: Annotated[
        WorktreePlanConfirmationService,
        Depends(get_worktree_plan_confirmation_service),
    ],
) -> WorktreePlanConfirmationReceiptResponse:
    """Return a confirmation receipt; no worktree, branch, git, or session mutation occurs."""

    try:
        receipt = confirmation_service.confirm_plan(
            WorktreePlanConfirmationRequest(
                agent_session_id=session_id,
                plan_hash=request.plan_hash,
                user_confirmed=request.user_confirmed,
                confirmed_by=request.confirmed_by,
            )
        )
    except ValueError as exc:
        detail = str(exc)
        if "Agent session not found" in detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if isinstance(exc, WorktreePlanHashMismatchError):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        if isinstance(exc, WorktreePlanConfirmationError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=detail,
            ) from exc
        raise

    return WorktreePlanConfirmationReceiptResponse.from_receipt(receipt)


@router.post(
    "/sessions/{session_id}/workspace/prepare",
    response_model=WorktreePrepareResponse,
    summary="Validate and block future workspace prepare execution",
)
def prepare_agent_session_workspace(
    session_id: UUID,
    request: WorktreePrepareRequestBody,
    prepare_service: Annotated[
        WorktreePrepareService,
        Depends(get_worktree_prepare_service),
    ],
) -> WorktreePrepareResponse:
    """Return blocked/not_implemented; no git, branch, worktree, or session mutation occurs."""

    try:
        result = prepare_service.prepare_workspace(
            WorktreePrepareRequest(
                agent_session_id=session_id,
                plan_hash=request.plan_hash,
                user_confirmed=request.user_confirmed,
            )
        )
    except ValueError as exc:
        detail = str(exc)
        if "Agent session not found" in detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if isinstance(exc, WorktreePrepareHashMismatchError):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        if isinstance(exc, WorktreePrepareError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=detail,
            ) from exc
        raise

    return WorktreePrepareResponse.from_result(result)


@router.post(
    "/sessions/{session_id}/workspace/create",
    response_model=WorktreeCreateResponse,
    summary="Create a guarded per-session workspace worktree",
)
def create_agent_session_workspace(
    session_id: UUID,
    request: WorktreeCreateRequestBody,
    create_service: Annotated[
        WorktreeCreateService,
        Depends(get_worktree_create_service),
    ],
) -> WorktreeCreateResponse:
    """Create a worktree only after confirmation, hash match, and safe preflight."""

    try:
        result = create_service.create_workspace(
            WorktreeCreateRequest(
                agent_session_id=session_id,
                plan_hash=request.plan_hash,
                user_confirmed=request.user_confirmed,
            )
        )
    except ValueError as exc:
        detail = str(exc)
        if "Agent session not found" in detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if isinstance(exc, WorktreeCreateHashMismatchError):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        if isinstance(exc, WorktreeCreateError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=detail,
            ) from exc
        raise

    return WorktreeCreateResponse.from_result(result)


@router.post(
    "/sessions/{session_id}/workspace/cleanup",
    response_model=WorktreeCleanupResponse,
    summary="Execute guarded worktree cleanup after read-only preflight",
)
def cleanup_agent_session_workspace(
    session_id: UUID,
    request: WorktreeCleanupRequestBody,
    cleanup_service: Annotated[
        WorktreeCleanupService,
        Depends(get_worktree_cleanup_service),
    ],
) -> WorktreeCleanupResponse:
    """Remove a clean registered worktree only; branch deletion and direct file deletion are forbidden."""

    try:
        result = cleanup_service.cleanup_workspace(
            WorktreeCleanupRequest(
                agent_session_id=session_id,
                plan_hash=request.plan_hash,
                user_confirmed=request.user_confirmed,
            )
        )
    except ValueError as exc:
        detail = str(exc)
        if "Agent session not found" in detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if isinstance(exc, WorktreeCleanupHashMismatchError):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        if isinstance(exc, WorktreeCleanupError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=detail,
            ) from exc
        raise

    return WorktreeCleanupResponse.from_result(result)


@router.get(
    "/projects/{project_id}/sessions",
    response_model=list[AgentSessionResponse],
    summary="List Day11 agent sessions for one project",
)
def list_project_agent_sessions(
    project_id: UUID,
    agent_conversation_service: Annotated[
        AgentConversationService, Depends(get_agent_conversation_service)
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AgentSessionResponse]:
    """Return project-level agent sessions for Day12 session list consumption."""

    sessions = agent_conversation_service.list_project_sessions(
        project_id=project_id,
        limit=limit,
    )
    return [AgentSessionResponse.from_session(item) for item in sessions]


@router.get(
    "/projects/{project_id}/timeline",
    response_model=AgentTimelineResponse,
    summary="Replay Day11 agent timeline for one project or session",
)
def get_project_agent_timeline(
    project_id: UUID,
    agent_conversation_service: Annotated[
        AgentConversationService, Depends(get_agent_conversation_service)
    ],
    session_id: UUID | None = Query(default=None),
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> AgentTimelineResponse:
    """Return Day12 timeline payload including message/state/intervention fields."""

    messages = agent_conversation_service.list_project_timeline(
        project_id=project_id,
        session_id=session_id,
        limit=limit,
    )
    return AgentTimelineResponse(
        project_id=project_id,
        session_id=session_id,
        total_messages=len(messages),
        messages=[AgentMessageResponse.from_message(item) for item in messages],
    )


@router.get(
    "/projects/{project_id}/interventions",
    response_model=AgentInterventionResponse,
    summary="List Day11 review/rework/boss intervention events",
)
def get_project_agent_interventions(
    project_id: UUID,
    agent_conversation_service: Annotated[
        AgentConversationService, Depends(get_agent_conversation_service)
    ],
    session_id: UUID | None = Query(default=None),
    limit: Annotated[int, Query(ge=1, le=300)] = 100,
) -> AgentInterventionResponse:
    """Return intervention and note-event feed for Day12 intervention panel."""

    messages = agent_conversation_service.list_project_interventions(
        project_id=project_id,
        session_id=session_id,
        limit=limit,
    )
    # Keep newest first for intervention inbox consumption.
    messages = sorted(messages, key=lambda item: item.created_at, reverse=True)
    return AgentInterventionResponse(
        project_id=project_id,
        session_id=session_id,
        total_items=len(messages),
        items=[AgentMessageResponse.from_message(item) for item in messages],
    )


@router.post(
    "/projects/{project_id}/sessions/{session_id}/interventions",
    response_model=AgentInterventionWriteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Write one formal session-level boss intervention",
)
def create_session_boss_intervention(
    project_id: UUID,
    session_id: UUID,
    request: AgentInterventionWriteRequest,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> AgentInterventionWriteResponse:
    """Persist one Day12 intervention command on the selected agent session."""

    agent_conversation_service = AgentConversationService(
        agent_session_repository=AgentSessionRepository(db_session),
        agent_message_repository=AgentMessageRepository(db_session),
    )

    try:
        updated_session, message = agent_conversation_service.record_boss_intervention(
            project_id=project_id,
            session_id=session_id,
            intervention_type=request.intervention_type,
            note_event_type=request.note_event_type,
            intervention_summary=request.content_summary,
            intervention_detail=request.content_detail,
        )
        db_session.commit()
    except ValueError as exc:
        detail = str(exc)
        if detail.startswith("Agent session not found") or "does not belong to project" in detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if detail.startswith(
            "Agent session is finalized and does not accept boss interventions"
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from exc

    return AgentInterventionWriteResponse(
        project_id=project_id,
        session_id=session_id,
        session=AgentSessionResponse.from_session(updated_session),
        intervention_message=AgentMessageResponse.from_message(message),
    )
