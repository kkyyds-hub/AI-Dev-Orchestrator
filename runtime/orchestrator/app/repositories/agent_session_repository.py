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
    AgentType,
    CodingSessionActivityState,
    CodingSessionStatus,
    RuntimeType,
    WorkspaceType,
)
from app.domain.project_role import ProjectRoleCode


_UNSET = object()


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
        agent_type: AgentType | None = None,
        runtime_type: RuntimeType | None = None,
        runtime_handle_id: str | None = None,
        coding_status: CodingSessionStatus | None = None,
        activity_state: CodingSessionActivityState | None = None,
        branch_name: str | None = None,
        workspace_type: WorkspaceType | None = WorkspaceType.IN_PLACE,
        workspace_path: str | None = None,
        workspace_clean: bool | None = None,
        last_workspace_error: str | None = None,
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
            agent_type=agent_type,
            runtime_type=runtime_type,
            runtime_handle_id=(
                runtime_handle_id.strip() or None
                if runtime_handle_id is not None
                else None
            ),
            coding_status=coding_status,
            activity_state=activity_state,
            branch_name=branch_name.strip() or None if branch_name is not None else None,
            workspace_type=workspace_type,
            workspace_path=(
                workspace_path.strip() or None if workspace_path is not None else None
            ),
            workspace_clean=workspace_clean,
            last_workspace_error=(
                last_workspace_error.strip() or None
                if last_workspace_error is not None
                else None
            ),
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
        agent_type: AgentType | None = None,
        runtime_type: RuntimeType | None = None,
        runtime_handle_id: str | None = None,
        coding_status: CodingSessionStatus | None = None,
        activity_state: CodingSessionActivityState | None = None,
        branch_name: str | None = None,
        workspace_type: WorkspaceType | None = None,
        workspace_path: str | None = None,
        workspace_clean: bool | None = None,
        last_workspace_error: str | None | object = _UNSET,
        finished: bool = False,
    ) -> AgentSession:
        """Update session status/coding fields and return the latest snapshot."""

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
        if agent_type is not None:
            row.agent_type = agent_type
        if runtime_type is not None:
            row.runtime_type = runtime_type
        if runtime_handle_id is not None:
            row.runtime_handle_id = runtime_handle_id.strip() or None
        if coding_status is not None:
            row.coding_status = coding_status
        if activity_state is not None:
            row.activity_state = activity_state
        if branch_name is not None:
            row.branch_name = branch_name.strip() or None
        if workspace_type is not None:
            row.workspace_type = workspace_type
        if workspace_path is not None:
            row.workspace_path = workspace_path.strip() or None
        if workspace_clean is not None:
            row.workspace_clean = workspace_clean
        if last_workspace_error is not _UNSET:
            row.last_workspace_error = (
                last_workspace_error.strip() or None
                if isinstance(last_workspace_error, str)
                else None
            )
        row.updated_at = utc_now()
        if finished:
            row.finished_at = utc_now()

        self.session.flush()
        return self._to_domain(row)

    def mark_workspace_cleaned(self, session_id: UUID) -> AgentSession:
        """Clear workspace and branch bindings after guarded worktree cleanup."""

        row = self.session.get(AgentSessionTable, session_id)
        if row is None:
            raise ValueError(f"Agent session not found: {session_id}")

        row.workspace_path = None
        row.branch_name = None
        row.workspace_type = WorkspaceType.IN_PLACE
        row.workspace_clean = None
        row.last_workspace_error = None
        row.updated_at = utc_now()
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
            agent_type=row.agent_type,
            runtime_type=row.runtime_type,
            runtime_handle_id=row.runtime_handle_id,
            coding_status=row.coding_status,
            activity_state=row.activity_state,
            branch_name=row.branch_name,
            workspace_type=row.workspace_type,
            workspace_path=row.workspace_path,
            workspace_clean=row.workspace_clean,
            last_workspace_error=row.last_workspace_error,
            started_at=ensure_utc_datetime(row.started_at),
            updated_at=ensure_utc_datetime(row.updated_at),
            finished_at=ensure_utc_datetime(row.finished_at),
        )
