"""Repository for project-level Project Director skill binding configs."""

from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db_tables import ProjectDirectorSkillBindingConfigTable
from app.domain._base import ensure_utc_datetime, utc_now
from app.domain.project_director_skill_binding_config import (
    ProjectDirectorSkillBindingConfig,
    ProjectDirectorSkillBindingConfigItem,
    SkillBindingConfigStatus,
)


class ProjectDirectorSkillBindingConfigRepository:
    """CRUD for ProjectDirectorSkillBindingConfig."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def session(self) -> Session:
        return self._session

    def add_no_commit(
        self, config: ProjectDirectorSkillBindingConfig
    ) -> ProjectDirectorSkillBindingConfig:
        row = ProjectDirectorSkillBindingConfigTable(
            id=config.id,
            project_id=config.project_id,
            plan_version_id=config.plan_version_id,
            source_draft_id=config.source_draft_id,
            status=config.status,
            skill_bindings_json=json.dumps(
                [item.model_dump() for item in config.skill_bindings],
                ensure_ascii=False,
            ),
            warnings_json=json.dumps(config.warnings, ensure_ascii=False),
            review_note=config.review_note,
            created_at=config.created_at,
            updated_at=config.updated_at,
            confirmed_at=config.confirmed_at,
            rejected_at=config.rejected_at,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def get_by_project_id(
        self, project_id: UUID
    ) -> ProjectDirectorSkillBindingConfig | None:
        stmt = select(ProjectDirectorSkillBindingConfigTable).where(
            ProjectDirectorSkillBindingConfigTable.project_id == project_id
        )
        row = self._session.execute(stmt).scalars().first()
        return self._to_domain(row) if row is not None else None

    def get_by_plan_version_id(
        self, plan_version_id: UUID
    ) -> ProjectDirectorSkillBindingConfig | None:
        stmt = select(ProjectDirectorSkillBindingConfigTable).where(
            ProjectDirectorSkillBindingConfigTable.plan_version_id == plan_version_id
        )
        row = self._session.execute(stmt).scalars().first()
        return self._to_domain(row) if row is not None else None

    def update_review(
        self,
        config_id: UUID,
        *,
        status: SkillBindingConfigStatus,
        note: str = "",
        reviewed_at: datetime | None = None,
    ) -> ProjectDirectorSkillBindingConfig:
        row = self._session.get(ProjectDirectorSkillBindingConfigTable, config_id)
        if row is None:
            raise ValueError(f"Skill binding config {config_id} not found")

        now = reviewed_at or utc_now()
        row.status = status
        row.review_note = note
        row.updated_at = now
        if status == SkillBindingConfigStatus.CONFIRMED:
            row.confirmed_at = now
        elif status == SkillBindingConfigStatus.REJECTED:
            row.rejected_at = now

        self._session.commit()
        self._session.refresh(row)
        return self._to_domain(row)

    @staticmethod
    def _to_domain(
        row: ProjectDirectorSkillBindingConfigTable,
    ) -> ProjectDirectorSkillBindingConfig:
        skill_bindings: list[ProjectDirectorSkillBindingConfigItem] = []
        try:
            raw_items = json.loads(row.skill_bindings_json) if row.skill_bindings_json else []
            if isinstance(raw_items, list):
                for item in raw_items:
                    if isinstance(item, dict):
                        skill_bindings.append(
                            ProjectDirectorSkillBindingConfigItem(**item)
                        )
        except (json.JSONDecodeError, TypeError, ValueError):
            skill_bindings = []

        warnings: list[str] = []
        try:
            raw_warnings = json.loads(row.warnings_json) if row.warnings_json else []
            if isinstance(raw_warnings, list):
                warnings = [str(item) for item in raw_warnings]
        except (json.JSONDecodeError, TypeError):
            warnings = []

        return ProjectDirectorSkillBindingConfig(
            id=row.id,
            project_id=row.project_id,
            plan_version_id=row.plan_version_id,
            source_draft_id=row.source_draft_id,
            status=row.status,
            skill_bindings=skill_bindings,
            warnings=warnings,
            review_note=row.review_note or "",
            created_at=ensure_utc_datetime(row.created_at) or utc_now(),
            updated_at=ensure_utc_datetime(row.updated_at) or utc_now(),
            confirmed_at=ensure_utc_datetime(row.confirmed_at),
            rejected_at=ensure_utc_datetime(row.rejected_at),
        )
