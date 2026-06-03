"""Repository for AI Project Director session-scoped messages."""

from __future__ import annotations

import json
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db_tables import ProjectDirectorMessageTable
from app.domain._base import ensure_utc_datetime
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)


class ProjectDirectorMessageRepository:
    """CRUD helpers for Project Director conversation messages."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, message: ProjectDirectorMessage) -> ProjectDirectorMessage:
        row = ProjectDirectorMessageTable(
            id=message.id,
            session_id=message.session_id,
            role=message.role,
            content=message.content,
            sequence_no=message.sequence_no,
            intent=message.intent,
            related_plan_version_id=message.related_plan_version_id,
            related_project_id=message.related_project_id,
            related_task_id=message.related_task_id,
            source=message.source,
            source_detail=message.source_detail or "",
            suggested_actions_json=json.dumps(message.suggested_actions),
            requires_confirmation=message.requires_confirmation,
            risk_level=message.risk_level,
            forbidden_actions_detected_json=json.dumps(
                message.forbidden_actions_detected
            ),
            token_count=message.token_count,
            estimated_cost=message.estimated_cost,
            created_at=message.created_at,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def get_by_id(self, message_id: UUID) -> ProjectDirectorMessage | None:
        row = self._session.get(ProjectDirectorMessageTable, message_id)
        if row is None:
            return None
        return self._to_domain(row)

    def list_by_session_id(
        self,
        *,
        session_id: UUID,
        limit: int = 50,
        before_message_id: UUID | None = None,
    ) -> tuple[list[ProjectDirectorMessage], bool]:
        """Return the latest message window in chronological order.

        When before_message_id is supplied, return messages older than that
        cursor. Fetch limit + 1 rows to expose has_more without a count query.
        """

        statement = select(ProjectDirectorMessageTable).where(
            ProjectDirectorMessageTable.session_id == session_id
        )
        if before_message_id is not None:
            cursor_row = self._session.get(ProjectDirectorMessageTable, before_message_id)
            if cursor_row is None or cursor_row.session_id != session_id:
                raise ValueError(
                    f"Project Director message cursor {before_message_id} not found for session {session_id}"
                )
            statement = statement.where(
                ProjectDirectorMessageTable.sequence_no < cursor_row.sequence_no
            )

        statement = (
            statement.order_by(
                ProjectDirectorMessageTable.sequence_no.desc(),
                ProjectDirectorMessageTable.created_at.desc(),
            )
            .limit(limit + 1)
        )
        rows = self._session.execute(statement).scalars().all()
        has_more = len(rows) > limit
        window_rows = list(reversed(rows[:limit]))
        return [self._to_domain(row) for row in window_rows], has_more

    def get_next_sequence_no(self, *, session_id: UUID) -> int:
        statement = (
            select(ProjectDirectorMessageTable.sequence_no)
            .where(ProjectDirectorMessageTable.session_id == session_id)
            .order_by(ProjectDirectorMessageTable.sequence_no.desc())
            .limit(1)
        )
        latest = self._session.execute(statement).scalar_one_or_none()
        return 1 if latest is None else int(latest) + 1

    def commit(self) -> None:
        self._session.commit()

    @staticmethod
    def _load_json_list(raw_value: str | None) -> list:
        if not raw_value:
            return []
        try:
            parsed = json.loads(raw_value)
        except (json.JSONDecodeError, TypeError):
            return []
        return parsed if isinstance(parsed, list) else []

    @classmethod
    def _to_domain(cls, row: ProjectDirectorMessageTable) -> ProjectDirectorMessage:
        risk_level = None
        if row.risk_level is not None:
            try:
                risk_level = ProjectDirectorMessageRiskLevel(row.risk_level)
            except ValueError:
                risk_level = None

        try:
            return ProjectDirectorMessage(
                id=row.id,
                session_id=row.session_id,
                role=ProjectDirectorMessageRole(row.role),
                content=row.content,
                sequence_no=row.sequence_no,
                intent=row.intent,
                related_plan_version_id=row.related_plan_version_id,
                related_project_id=row.related_project_id,
                related_task_id=row.related_task_id,
                source=ProjectDirectorMessageSource(row.source),
                source_detail=row.source_detail,
                suggested_actions=cls._load_json_list(row.suggested_actions_json),
                requires_confirmation=row.requires_confirmation,
                risk_level=risk_level,
                forbidden_actions_detected=cls._load_json_list(
                    row.forbidden_actions_detected_json
                ),
                token_count=row.token_count,
                estimated_cost=row.estimated_cost,
                created_at=ensure_utc_datetime(row.created_at),
            )
        except ValidationError as exc:
            raise ValueError(f"Invalid ProjectDirectorMessage row {row.id}: {exc}") from exc
