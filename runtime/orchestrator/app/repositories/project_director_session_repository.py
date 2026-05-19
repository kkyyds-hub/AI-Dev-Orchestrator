"""Repository for AI Project Director sessions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db_tables import ProjectDirectorSessionTable
from app.domain._base import ensure_utc_datetime
from app.domain.project_director_session import (
    ClarifyingAnswer,
    ClarifyingQuestion,
    ProjectDirectorSession,
    ProjectDirectorSessionStatus,
)


class ProjectDirectorSessionRepository:
    """CRUD for ProjectDirectorSession domain objects backed by SQLite."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, session_obj: ProjectDirectorSession) -> ProjectDirectorSession:
        row = ProjectDirectorSessionTable(
            id=session_obj.id,
            project_id=session_obj.project_id,
            goal_text=session_obj.goal_text,
            constraints=session_obj.constraints,
            status=session_obj.status,
            clarifying_questions_json=json.dumps(
                [q.model_dump() for q in session_obj.clarifying_questions]
            ),
            clarifying_answers_json=json.dumps(
                [a.model_dump() for a in session_obj.clarifying_answers]
            ),
            goal_summary=session_obj.goal_summary,
            confirmed_at=session_obj.confirmed_at,
            created_at=session_obj.created_at,
            updated_at=session_obj.updated_at,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return self._to_domain(row)

    def get_by_id(self, session_id: UUID) -> ProjectDirectorSession | None:
        row = self._session.get(ProjectDirectorSessionTable, session_id)
        if row is None:
            return None
        return self._to_domain(row)

    def update(self, session_obj: ProjectDirectorSession) -> ProjectDirectorSession:
        row = self._session.get(ProjectDirectorSessionTable, session_obj.id)
        if row is None:
            raise ValueError(f"ProjectDirectorSession {session_obj.id} not found")

        row.project_id = session_obj.project_id
        row.goal_text = session_obj.goal_text
        row.constraints = session_obj.constraints
        row.status = session_obj.status
        row.clarifying_questions_json = json.dumps(
            [q.model_dump() for q in session_obj.clarifying_questions]
        )
        row.clarifying_answers_json = json.dumps(
            [a.model_dump() for a in session_obj.clarifying_answers]
        )
        row.goal_summary = session_obj.goal_summary
        row.confirmed_at = session_obj.confirmed_at
        row.updated_at = datetime.now(timezone.utc)

        self._session.commit()
        self._session.refresh(row)
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: ProjectDirectorSessionTable) -> ProjectDirectorSession:
        questions = []
        try:
            raw_qs = json.loads(row.clarifying_questions_json) if row.clarifying_questions_json else []
            if isinstance(raw_qs, list):
                for item in raw_qs:
                    try:
                        questions.append(ClarifyingQuestion(**item))
                    except ValidationError:
                        pass
        except (json.JSONDecodeError, TypeError):
            pass

        answers = []
        try:
            raw_as = json.loads(row.clarifying_answers_json) if row.clarifying_answers_json else []
            if isinstance(raw_as, list):
                for item in raw_as:
                    try:
                        answers.append(ClarifyingAnswer(**item))
                    except ValidationError:
                        pass
        except (json.JSONDecodeError, TypeError):
            pass

        return ProjectDirectorSession(
            id=row.id,
            project_id=row.project_id,
            goal_text=row.goal_text,
            constraints=row.constraints,
            status=row.status,
            clarifying_questions=questions,
            clarifying_answers=answers,
            goal_summary=row.goal_summary,
            confirmed_at=ensure_utc_datetime(row.confirmed_at),
            created_at=ensure_utc_datetime(row.created_at) or datetime.now(timezone.utc),
            updated_at=ensure_utc_datetime(row.updated_at) or datetime.now(timezone.utc),
        )
