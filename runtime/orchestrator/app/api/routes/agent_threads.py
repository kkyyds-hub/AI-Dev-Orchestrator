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
from app.domain.worktree_plan import WorktreePlan
from app.domain.worktree_plan_confirmation import WorktreePlanConfirmationReceipt
from app.repositories.agent_message_repository import AgentMessageRepository
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.repository_workspace_repository import RepositoryWorkspaceRepository
from app.services.agent_conversation_service import AgentConversationService
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
