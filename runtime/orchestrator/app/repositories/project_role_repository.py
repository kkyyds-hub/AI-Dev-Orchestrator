"""Persistence helpers for `ProjectRoleConfig` records."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db_tables import ProjectRoleTable
from app.domain._base import ensure_utc_datetime
from app.domain.project_role import ProjectRoleCode, ProjectRoleConfig


class ProjectRoleRepository:
    """Encapsulate project-role persistence operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_by_project_id(self, project_id: UUID) -> list[ProjectRoleConfig]:
        """Return one project's role configs ordered by sort order."""

        statement = (
            select(ProjectRoleTable)
            .where(ProjectRoleTable.project_id == project_id)
            .order_by(ProjectRoleTable.sort_order.asc(), ProjectRoleTable.created_at.asc())
        )
        role_rows = self.session.execute(statement).scalars().all()
        return [self._to_domain(role_row) for role_row in role_rows]

    def get_by_project_and_role_code(
        self,
        project_id: UUID,
        role_code: ProjectRoleCode,
    ) -> ProjectRoleConfig | None:
        """Return one persisted role config, if it exists."""

        statement = select(ProjectRoleTable).where(
            ProjectRoleTable.project_id == project_id,
            ProjectRoleTable.role_code == role_code,
        )
        role_row = self.session.execute(statement).scalar_one_or_none()
        if role_row is None:
            return None

        return self._to_domain(role_row)

    def create_many(self, role_configs: list[ProjectRoleConfig]) -> list[ProjectRoleConfig]:
        """Persist multiple role configs for one project."""

        if not role_configs:
            return []

        self.session.add_all([self._to_row(role_config) for role_config in role_configs])
        self.session.commit()
        return self.list_by_project_id(role_configs[0].project_id)

    def save(self, role_config: ProjectRoleConfig) -> ProjectRoleConfig:
        """Create or update one role config and return the stored value."""

        statement = select(ProjectRoleTable).where(
            ProjectRoleTable.project_id == role_config.project_id,
            ProjectRoleTable.role_code == role_config.role_code,
        )
        role_row = self.session.execute(statement).scalar_one_or_none()
        if role_row is None:
            role_row = self._to_row(role_config)
            self.session.add(role_row)
        else:
            self._apply_domain_to_row(role_row, role_config)

        self.session.commit()
        self.session.refresh(role_row)
        return self._to_domain(role_row)

    @staticmethod
    def _to_row(role_config: ProjectRoleConfig) -> ProjectRoleTable:
        """Convert one domain role config into an ORM row."""

        return ProjectRoleTable(
            id=role_config.id,
            project_id=role_config.project_id,
            role_code=role_config.role_code,
            enabled=role_config.enabled,
            name=role_config.name,
            summary=role_config.summary,
            responsibilities_json=ProjectRoleRepository._serialize_string_list(
                role_config.responsibilities
            ),
            input_boundary_json=ProjectRoleRepository._serialize_string_list(
                role_config.input_boundary
            ),
            output_boundary_json=ProjectRoleRepository._serialize_string_list(
                role_config.output_boundary
            ),
            default_skill_slots_json=ProjectRoleRepository._serialize_string_list(
                role_config.default_skill_slots
            ),
            custom_notes=role_config.custom_notes,
            sort_order=role_config.sort_order,
            created_at=role_config.created_at,
            updated_at=role_config.updated_at,
        )

    @staticmethod
    def _apply_domain_to_row(
        role_row: ProjectRoleTable,
        role_config: ProjectRoleConfig,
    ) -> None:
        """Copy one domain model onto an existing ORM row."""

        role_row.enabled = role_config.enabled
        role_row.name = role_config.name
        role_row.summary = role_config.summary
        role_row.responsibilities_json = ProjectRoleRepository._serialize_string_list(
            role_config.responsibilities
        )
        role_row.input_boundary_json = ProjectRoleRepository._serialize_string_list(
            role_config.input_boundary
        )
        role_row.output_boundary_json = ProjectRoleRepository._serialize_string_list(
            role_config.output_boundary
        )
        role_row.default_skill_slots_json = ProjectRoleRepository._serialize_string_list(
            role_config.default_skill_slots
        )
        role_row.custom_notes = role_config.custom_notes
        role_row.sort_order = role_config.sort_order
        role_row.updated_at = role_config.updated_at

    @staticmethod
    def _to_domain(role_row: ProjectRoleTable) -> ProjectRoleConfig:
        """Convert one ORM row back into the role-config domain model."""

        return ProjectRoleConfig(
            id=role_row.id,
            project_id=role_row.project_id,
            role_code=role_row.role_code,
            enabled=role_row.enabled,
            name=role_row.name,
            summary=role_row.summary,
            responsibilities=ProjectRoleRepository._deserialize_string_list(
                role_row.responsibilities_json
            ),
            input_boundary=ProjectRoleRepository._deserialize_string_list(
                role_row.input_boundary_json
            ),
            output_boundary=ProjectRoleRepository._deserialize_string_list(
                role_row.output_boundary_json
            ),
            default_skill_slots=ProjectRoleRepository._deserialize_string_list(
                role_row.default_skill_slots_json
            ),
            custom_notes=role_row.custom_notes,
            sort_order=role_row.sort_order,
            created_at=ensure_utc_datetime(role_row.created_at),
            updated_at=ensure_utc_datetime(role_row.updated_at),
        )

    @staticmethod
    def _serialize_string_list(values: list[str]) -> str:
        """Store one string list as JSON text in SQLite."""

        return json.dumps(values, ensure_ascii=False)

    @staticmethod
    def _deserialize_string_list(raw_value: str | None) -> list[str]:
        """Read one JSON-encoded string list from SQLite."""

        if not raw_value:
            return []

        try:
            decoded_value = json.loads(raw_value)
        except json.JSONDecodeError:
            return []

        if not isinstance(decoded_value, list):
            return []

        normalized_items: list[str] = []
        for item in decoded_value:
            normalized_item = str(item).strip()
            if normalized_item:
                normalized_items.append(normalized_item)

        return normalized_items
