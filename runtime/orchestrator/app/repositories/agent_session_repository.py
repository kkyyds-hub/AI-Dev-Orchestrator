"""Persistence helpers for Day11 agent-thread sessions."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db_tables import AgentSessionTable
from app.domain._base import ensure_utc_datetime, utc_now
from app.domain.agent_session import (
    AgentSession,
    AgentSessionPhase,
    AgentSessionReviewStatus,
    AgentSessionStatus,
)
from app.domain.project_role import ProjectRoleCode


class AgentSessionRepository:
    """Encapsulate Day11 agent-session persistence operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        project_id: UUID,
        task_id: UUID,
        run_id: UUID,
        status: AgentSessionStatus,
        review_status: AgentSessionReviewStatus,
        current_phase: AgentSessionPhase,
        owner_role_code: ProjectRoleCode | None,
        context_checkpoint_id: str | None,
        context_rehydrated: bool,
        summary: str | None,
    ) -> AgentSession:
        """Create and persist one new session row."""

        row = AgentSessionTable(
            project_id=project_id,
            task_id=task_id,
            run_id=run_id,
            status=status,
            review_status=review_status,
            current_phase=current_phase,
            owner_role_code=owner_role_code,
            context_checkpoint_id=context_checkpoint_id,
            context_rehydrated=context_rehydrated,
            summary=summary,
            started_at=utc_now(),
            updated_at=utc_now(),
        )
        self.session.add(row)
        self.session.flush()
        return self._to_domain(row)

    def get_by_id(self, session_id: UUID) -> AgentSession | None:
        """Return one session by ID."""

        row = self.session.get(AgentSessionTable, session_id)
        if row is None:
            return None
        return self._to_domain(row)

    def get_by_run_id(self, run_id: UUID) -> AgentSession | None:
        """Return one session bound to one run."""

        statement = (
            select(AgentSessionTable)
            .where(AgentSessionTable.run_id == run_id)
            .order_by(AgentSessionTable.started_at.desc())
            .limit(1)
        )
        row = self.session.execute(statement).scalar_one_or_none()
        if row is None:
            return None
        return self._to_domain(row)

    def list_by_project_id(
        self,
        *,
        project_id: UUID,
        limit: int = 20,
    ) -> list[AgentSession]:
        """Return project sessions ordered from newest to oldest."""

        statement = (
            select(AgentSessionTable)
            .where(AgentSessionTable.project_id == project_id)
            .order_by(AgentSessionTable.updated_at.desc())
            .limit(limit)
        )
        rows = self.session.execute(statement).scalars().all()
        return [self._to_domain(row) for row in rows]

    def update_status(
        self,
        session_id: UUID,
        *,
        status: AgentSessionStatus | None = None,
        review_status: AgentSessionReviewStatus | None = None,
        current_phase: AgentSessionPhase | None = None,
        latest_intervention_type: str | None = None,
        latest_note_event_type: str | None = None,
        summary: str | None = None,
        finished: bool = False,
    ) -> AgentSession:
        """Update status-phase fields and return the latest session snapshot."""

        row = self.session.get(AgentSessionTable, session_id)
        if row is None:
            raise ValueError(f"Agent session not found: {session_id}")

        if status is not None:
            row.status = status
        if review_status is not None:
            row.review_status = review_status
        if current_phase is not None:
            row.current_phase = current_phase

        if latest_intervention_type is not None:
            row.latest_intervention_type = latest_intervention_type.strip() or None
        if latest_note_event_type is not None:
            row.latest_note_event_type = latest_note_event_type.strip() or None
        if summary is not None:
            row.summary = summary.strip() or None
        row.updated_at = utc_now()
        if finished:
            row.finished_at = utc_now()

        self.session.flush()
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: AgentSessionTable) -> AgentSession:
        """Convert ORM row into domain model."""

        return AgentSession(
            id=row.id,
            project_id=row.project_id,
            task_id=row.task_id,
            run_id=row.run_id,
            status=row.status,
            review_status=row.review_status,
            current_phase=row.current_phase,
            owner_role_code=row.owner_role_code,
            context_checkpoint_id=row.context_checkpoint_id,
            context_rehydrated=row.context_rehydrated,
            latest_intervention_type=row.latest_intervention_type,
            latest_note_event_type=row.latest_note_event_type,
            summary=row.summary,
            started_at=ensure_utc_datetime(row.started_at),
            updated_at=ensure_utc_datetime(row.updated_at),
            finished_at=ensure_utc_datetime(row.finished_at),
        )
