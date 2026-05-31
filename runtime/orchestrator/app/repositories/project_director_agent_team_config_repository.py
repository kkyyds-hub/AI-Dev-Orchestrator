"""Repository for project-level Project Director agent team configs."""

from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db_tables import ProjectDirectorAgentTeamConfigTable
from app.domain._base import ensure_utc_datetime, utc_now
from app.domain.project_director_agent_team_config import (
    AgentTeamConfigStatus,
    ProjectDirectorAgentTeamConfig,
    ProjectDirectorAgentTeamMemberConfig,
)


class ProjectDirectorAgentTeamConfigRepository:
    """CRUD for ProjectDirectorAgentTeamConfig."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def session(self) -> Session:
        return self._session

    def add_no_commit(
        self, config: ProjectDirectorAgentTeamConfig
    ) -> ProjectDirectorAgentTeamConfig:
        row = ProjectDirectorAgentTeamConfigTable(
            id=config.id,
            project_id=config.project_id,
            plan_version_id=config.plan_version_id,
            source_draft_id=config.source_draft_id,
            status=config.status,
            agent_team_json=json.dumps(
                [item.model_dump() for item in config.agent_team],
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
    ) -> ProjectDirectorAgentTeamConfig | None:
        stmt = select(ProjectDirectorAgentTeamConfigTable).where(
            ProjectDirectorAgentTeamConfigTable.project_id == project_id
        )
        row = self._session.execute(stmt).scalars().first()
        return self._to_domain(row) if row is not None else None

    def get_by_plan_version_id(
        self, plan_version_id: UUID
    ) -> ProjectDirectorAgentTeamConfig | None:
        stmt = select(ProjectDirectorAgentTeamConfigTable).where(
            ProjectDirectorAgentTeamConfigTable.plan_version_id == plan_version_id
        )
        row = self._session.execute(stmt).scalars().first()
        return self._to_domain(row) if row is not None else None

    def update_review(
        self,
        config_id: UUID,
        *,
        status: AgentTeamConfigStatus,
        note: str = "",
        reviewed_at: datetime | None = None,
    ) -> ProjectDirectorAgentTeamConfig:
        row = self._session.get(ProjectDirectorAgentTeamConfigTable, config_id)
        if row is None:
            raise ValueError(f"Agent team config {config_id} not found")

        now = reviewed_at or utc_now()
        row.status = status
        row.review_note = note
        row.updated_at = now
        if status == AgentTeamConfigStatus.CONFIRMED:
            row.confirmed_at = now
        elif status == AgentTeamConfigStatus.REJECTED:
            row.rejected_at = now

        self._session.commit()
        self._session.refresh(row)
        return self._to_domain(row)

    @staticmethod
    def _to_domain(
        row: ProjectDirectorAgentTeamConfigTable,
    ) -> ProjectDirectorAgentTeamConfig:
        agent_team: list[ProjectDirectorAgentTeamMemberConfig] = []
        try:
            raw_team = json.loads(row.agent_team_json) if row.agent_team_json else []
            if isinstance(raw_team, list):
                for item in raw_team:
                    if isinstance(item, dict):
                        agent_team.append(
                            ProjectDirectorAgentTeamMemberConfig(**item)
                        )
        except (json.JSONDecodeError, TypeError, ValueError):
            agent_team = []

        warnings: list[str] = []
        try:
            raw_warnings = json.loads(row.warnings_json) if row.warnings_json else []
            if isinstance(raw_warnings, list):
                warnings = [str(item) for item in raw_warnings]
        except (json.JSONDecodeError, TypeError):
            warnings = []

        return ProjectDirectorAgentTeamConfig(
            id=row.id,
            project_id=row.project_id,
            plan_version_id=row.plan_version_id,
            source_draft_id=row.source_draft_id,
            status=row.status,
            agent_team=agent_team,
            warnings=warnings,
            review_note=row.review_note or "",
            created_at=ensure_utc_datetime(row.created_at) or utc_now(),
            updated_at=ensure_utc_datetime(row.updated_at) or utc_now(),
            confirmed_at=ensure_utc_datetime(row.confirmed_at),
            rejected_at=ensure_utc_datetime(row.rejected_at),
        )

