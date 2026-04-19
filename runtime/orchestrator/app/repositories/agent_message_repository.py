"""Persistence helpers for Day11 agent-thread messages."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db_tables import AgentMessageTable
from app.domain._base import ensure_utc_datetime
from app.domain.agent_message import AgentMessage, AgentMessageRole, AgentMessageType


class AgentMessageRepository:
    """Encapsulate Day11 agent-message persistence operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        task_id: UUID,
        run_id: UUID,
        sequence_no: int,
        role: AgentMessageRole,
        message_type: AgentMessageType,
        event_type: str,
        phase: str | None,
        state_from: str | None,
        state_to: str | None,
        intervention_type: str | None,
        note_event_type: str | None,
        context_checkpoint_id: str | None,
        context_rehydrated: bool | None,
        content_summary: str,
        content_detail: str | None,
    ) -> AgentMessage:
        """Persist one message row."""

        row = AgentMessageTable(
            session_id=session_id,
            project_id=project_id,
            task_id=task_id,
            run_id=run_id,
            sequence_no=sequence_no,
            role=role,
            message_type=message_type,
            event_type=event_type.strip(),
            phase=phase.strip() if phase else None,
            state_from=state_from.strip() if state_from else None,
            state_to=state_to.strip() if state_to else None,
            intervention_type=intervention_type.strip() if intervention_type else None,
            note_event_type=note_event_type.strip() if note_event_type else None,
            context_checkpoint_id=(
                context_checkpoint_id.strip() if context_checkpoint_id else None
            ),
            context_rehydrated=context_rehydrated,
            content_summary=content_summary.strip(),
            content_detail=content_detail.strip() if content_detail else None,
        )
        self.session.add(row)
        self.session.flush()
        return self._to_domain(row)

    def list_by_session_id(
        self,
        *,
        session_id: UUID,
        limit: int = 200,
    ) -> list[AgentMessage]:
        """Return timeline messages for one session in ascending sequence order."""

        statement = (
            select(AgentMessageTable)
            .where(AgentMessageTable.session_id == session_id)
            .order_by(AgentMessageTable.sequence_no.asc(), AgentMessageTable.created_at.asc())
            .limit(limit)
        )
        rows = self.session.execute(statement).scalars().all()
        return [self._to_domain(row) for row in rows]

    def list_by_project_id(
        self,
        *,
        project_id: UUID,
        limit: int = 200,
        session_id: UUID | None = None,
        message_types: list[AgentMessageType] | None = None,
    ) -> list[AgentMessage]:
        """Return project-level messages ordered from newest to oldest."""

        statement = select(AgentMessageTable).where(
            AgentMessageTable.project_id == project_id
        )
        if session_id is not None:
            statement = statement.where(AgentMessageTable.session_id == session_id)
        if message_types:
            statement = statement.where(AgentMessageTable.message_type.in_(message_types))

        statement = statement.order_by(
            AgentMessageTable.created_at.desc(),
            AgentMessageTable.sequence_no.desc(),
        ).limit(limit)
        rows = self.session.execute(statement).scalars().all()
        return [self._to_domain(row) for row in rows]

    def get_next_sequence_no(self, *, session_id: UUID) -> int:
        """Return the next per-session message sequence number."""

        statement = (
            select(AgentMessageTable.sequence_no)
            .where(AgentMessageTable.session_id == session_id)
            .order_by(AgentMessageTable.sequence_no.desc())
            .limit(1)
        )
        latest = self.session.execute(statement).scalar_one_or_none()
        if latest is None:
            return 1
        return int(latest) + 1

    @staticmethod
    def _to_domain(row: AgentMessageTable) -> AgentMessage:
        """Convert ORM row into domain model."""

        return AgentMessage(
            id=row.id,
            session_id=row.session_id,
            project_id=row.project_id,
            task_id=row.task_id,
            run_id=row.run_id,
            sequence_no=row.sequence_no,
            role=row.role,
            message_type=row.message_type,
            event_type=row.event_type,
            phase=row.phase,
            state_from=row.state_from,
            state_to=row.state_to,
            intervention_type=row.intervention_type,
            note_event_type=row.note_event_type,
            context_checkpoint_id=row.context_checkpoint_id,
            context_rehydrated=row.context_rehydrated,
            content_summary=row.content_summary,
            content_detail=row.content_detail,
            created_at=ensure_utc_datetime(row.created_at),
        )
