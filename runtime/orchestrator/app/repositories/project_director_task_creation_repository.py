"""Repository for Project Director Task Creation Records.

BCG-04A: persistence for plan-version → task-queue creation batches.
"""

from __future__ import annotations

import json
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db_tables import ProjectDirectorTaskCreationRecordTable
from app.domain._base import ensure_utc_datetime, utc_now
from app.domain.project_director_task_creation import (
    ProjectDirectorTaskCreationRecord,
)


class TaskCreationRecordConflictError(ValueError):
    """Raised when one plan version has multiple creation records."""


class TaskCreationRecordInvalidError(ValueError):
    """Raised when a creation record cannot be decoded without data loss."""


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

    def get_strict_by_plan_version_id(
        self,
        plan_version_id: UUID,
    ) -> ProjectDirectorTaskCreationRecord | None:
        """Return exactly one creation record after strict raw queue decoding."""

        statement = select(ProjectDirectorTaskCreationRecordTable).where(
            ProjectDirectorTaskCreationRecordTable.plan_version_id == plan_version_id
        )
        with self._session.no_autoflush:
            rows = self._session.execute(statement).scalars().all()
            if not rows:
                return None
            if len(rows) != 1:
                raise TaskCreationRecordConflictError(
                    "Multiple task creation records exist for one plan version."
                )
            return self._to_strict_domain(rows[0])

    @staticmethod
    def _to_strict_domain(
        row: ProjectDirectorTaskCreationRecordTable,
    ) -> ProjectDirectorTaskCreationRecord:
        try:
            raw_task_ids = json.loads(row.task_ids_json)
        except (json.JSONDecodeError, TypeError) as exc:
            raise TaskCreationRecordInvalidError(
                "Task creation record queue is invalid."
            ) from exc
        if not isinstance(raw_task_ids, list) or not raw_task_ids:
            raise TaskCreationRecordInvalidError(
                "Task creation record queue is invalid."
            )

        task_ids: list[UUID] = []
        for raw_item in raw_task_ids:
            if not isinstance(raw_item, str):
                raise TaskCreationRecordInvalidError(
                    "Task creation record queue is invalid."
                )
            try:
                task_id = UUID(raw_item)
            except ValueError as exc:
                raise TaskCreationRecordInvalidError(
                    "Task creation record queue is invalid."
                ) from exc
            if raw_item != str(task_id):
                raise TaskCreationRecordInvalidError(
                    "Task creation record queue is invalid."
                )
            task_ids.append(task_id)

        if len(task_ids) != len(set(task_ids)) or row.task_count != len(task_ids):
            raise TaskCreationRecordInvalidError(
                "Task creation record queue is invalid."
            )
        try:
            return ProjectDirectorTaskCreationRecord(
                id=row.id,
                plan_version_id=row.plan_version_id,
                session_id=row.session_id,
                project_id=row.project_id,
                version_no=row.version_no,
                source_type=row.source_type,
                task_ids=task_ids,
                task_count=row.task_count,
                created_at=ensure_utc_datetime(row.created_at),
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise TaskCreationRecordInvalidError(
                "Task creation record is invalid."
            ) from exc

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
