"""Repository for Project Director Task Creation Records.

BCG-04A: persistence for plan-version → task-queue creation batches.
"""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db_tables import ProjectDirectorTaskCreationRecordTable
from app.domain._base import ensure_utc_datetime, utc_now
from app.domain.project_director_task_creation import (
    ProjectDirectorTaskCreationRecord,
)


class ProjectDirectorTaskCreationRecordRepository:
    """CRUD for ProjectDirectorTaskCreationRecord."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self, record: ProjectDirectorTaskCreationRecord
    ) -> ProjectDirectorTaskCreationRecord:
        row = ProjectDirectorTaskCreationRecordTable(
            id=record.id,
            plan_version_id=record.plan_version_id,
            session_id=record.session_id,
            project_id=record.project_id,
            version_no=record.version_no,
            source_type=record.source_type,
            task_ids_json=json.dumps(
                [str(tid) for tid in record.task_ids], ensure_ascii=False
            ),
            task_count=record.task_count,
            created_at=record.created_at,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return self._to_domain(row)

    def get_by_plan_version_id(
        self, plan_version_id: UUID
    ) -> ProjectDirectorTaskCreationRecord | None:
        stmt = select(ProjectDirectorTaskCreationRecordTable).where(
            ProjectDirectorTaskCreationRecordTable.plan_version_id == plan_version_id
        )
        row = self._session.execute(stmt).scalars().first()
        if row is None:
            return None
        return self._to_domain(row)

    @staticmethod
    def _to_domain(
        row: ProjectDirectorTaskCreationRecordTable,
    ) -> ProjectDirectorTaskCreationRecord:
        task_ids: list[UUID] = []
        try:
            raw = json.loads(row.task_ids_json) if row.task_ids_json else []
            if isinstance(raw, list):
                for item in raw:
                    try:
                        task_ids.append(UUID(str(item)))
                    except ValueError:
                        pass
        except (json.JSONDecodeError, TypeError):
            pass

        return ProjectDirectorTaskCreationRecord(
            id=row.id,
            plan_version_id=row.plan_version_id,
            session_id=row.session_id,
            project_id=row.project_id,
            version_no=row.version_no,
            source_type=row.source_type,
            task_ids=task_ids,
            task_count=row.task_count,
            created_at=ensure_utc_datetime(row.created_at) or utc_now(),
        )
