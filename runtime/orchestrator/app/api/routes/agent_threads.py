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
from app.repositories.agent_message_repository import AgentMessageRepository
from app.repositories.agent_session_repository import AgentSessionRepository
from app.services.agent_conversation_service import AgentConversationService


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


def get_agent_conversation_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> AgentConversationService:
    """Create Day11 conversation service dependency."""

    return AgentConversationService(
        agent_session_repository=AgentSessionRepository(session),
        agent_message_repository=AgentMessageRepository(session),
    )


router = APIRouter(prefix="/agent-threads", tags=["agent-threads"])


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
