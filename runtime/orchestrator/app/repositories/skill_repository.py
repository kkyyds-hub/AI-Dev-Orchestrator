"""Persistence helpers for the Day13 Skill registry and role bindings."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.db_tables import (
    ProjectRoleSkillBindingTable,
    SkillTable,
    SkillVersionTable,
)
from app.domain._base import ensure_utc_datetime
from app.domain.project_role import ProjectRoleCode
from app.domain.skill import (
    ProjectRoleSkillBinding,
    SkillDefinition,
    SkillVersionRecord,
)


class SkillRepository:
    """Encapsulate Day13 persistence operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_skills(self) -> list[SkillDefinition]:
        """Return all Skill rows ordered by creation time and code."""

        statement = select(SkillTable).order_by(SkillTable.created_at.asc(), SkillTable.code.asc())
        skill_rows = self.session.execute(statement).scalars().all()
        return [self._to_skill_domain(skill_row) for skill_row in skill_rows]

    def get_skill_by_code(self, code: str) -> SkillDefinition | None:
        """Return one Skill by its stable code, if it exists."""

        statement = select(SkillTable).where(SkillTable.code == code)
        skill_row = self.session.execute(statement).scalar_one_or_none()
        if skill_row is None:
            return None

        return self._to_skill_domain(skill_row)

    def save_skill(self, skill: SkillDefinition) -> SkillDefinition:
        """Create or update one Skill row and return the stored value."""

        statement = select(SkillTable).where(SkillTable.code == skill.code)
        skill_row = self.session.execute(statement).scalar_one_or_none()
        if skill_row is None:
            skill_row = self._build_skill_row(skill)
            self.session.add(skill_row)
        else:
            self._apply_skill_domain_to_row(skill_row, skill)

        self.session.commit()
        self.session.refresh(skill_row)
        return self._to_skill_domain(skill_row)

    def create_many_skills(self, skills: list[SkillDefinition]) -> list[SkillDefinition]:
        """Persist multiple Skill rows."""

        if not skills:
            return []

        self.session.add_all([self._build_skill_row(skill) for skill in skills])
        self.session.commit()
        return self.list_skills()

    def list_versions_by_skill_ids(
        self,
        skill_ids: list[UUID],
    ) -> dict[UUID, list[SkillVersionRecord]]:
        """Return version histories keyed by Skill id."""

        if not skill_ids:
            return {}

        statement = (
            select(SkillVersionTable)
            .where(SkillVersionTable.skill_id.in_(skill_ids))
            .order_by(SkillVersionTable.created_at.asc(), SkillVersionTable.version.asc())
        )
        version_rows = self.session.execute(statement).scalars().all()
        grouped_versions: dict[UUID, list[SkillVersionRecord]] = {skill_id: [] for skill_id in skill_ids}
        for version_row in version_rows:
            grouped_versions.setdefault(version_row.skill_id, []).append(
                self._to_version_domain(version_row)
            )

        return grouped_versions

    def create_version(self, version_record: SkillVersionRecord) -> SkillVersionRecord:
        """Persist one Skill version snapshot."""

        version_row = self._build_version_row(version_record)
        self.session.add(version_row)
        self.session.commit()
        self.session.refresh(version_row)
        return self._to_version_domain(version_row)

    def create_many_versions(
        self,
        version_records: list[SkillVersionRecord],
    ) -> list[SkillVersionRecord]:
        """Persist multiple Skill version snapshots."""

        if not version_records:
            return []

        self.session.add_all(
            [self._build_version_row(version_record) for version_record in version_records]
        )
        self.session.commit()
        return version_records

    def list_role_bindings_by_project_id(
        self,
        project_id: UUID,
    ) -> list[ProjectRoleSkillBinding]:
        """Return one project's role bindings ordered by role and creation time."""

        statement = (
            select(ProjectRoleSkillBindingTable)
            .where(ProjectRoleSkillBindingTable.project_id == project_id)
            .order_by(
                ProjectRoleSkillBindingTable.role_code.asc(),
                ProjectRoleSkillBindingTable.created_at.asc(),
                ProjectRoleSkillBindingTable.skill_name.asc(),
            )
        )
        binding_rows = self.session.execute(statement).scalars().all()
        return [self._to_binding_domain(binding_row) for binding_row in binding_rows]

    def create_many_role_bindings(
        self,
        bindings: list[ProjectRoleSkillBinding],
    ) -> list[ProjectRoleSkillBinding]:
        """Persist multiple role bindings for one project."""

        if not bindings:
            return []

        self.session.add_all([self._build_binding_row(binding) for binding in bindings])
        self.session.commit()
        return self.list_role_bindings_by_project_id(bindings[0].project_id)

    def replace_role_bindings(
        self,
        *,
        project_id: UUID,
        role_code: ProjectRoleCode,
        bindings: list[ProjectRoleSkillBinding],
    ) -> list[ProjectRoleSkillBinding]:
        """Replace all bindings under one project role."""

        delete_statement = delete(ProjectRoleSkillBindingTable).where(
            ProjectRoleSkillBindingTable.project_id == project_id,
            ProjectRoleSkillBindingTable.role_code == role_code,
        )
        self.session.execute(delete_statement)
        if bindings:
            self.session.add_all([self._build_binding_row(binding) for binding in bindings])

        self.session.commit()
        return self.list_role_bindings_by_project_id(project_id)

    @staticmethod
    def _build_skill_row(skill: SkillDefinition) -> SkillTable:
        return SkillTable(
            id=skill.id,
            code=skill.code,
            name=skill.name,
            summary=skill.summary,
            purpose=skill.purpose,
            applicable_role_codes_json=SkillRepository._serialize_role_codes(
                skill.applicable_role_codes
            ),
            enabled=skill.enabled,
            current_version=skill.current_version,
            created_at=skill.created_at,
            updated_at=skill.updated_at,
        )

    @staticmethod
    def _apply_skill_domain_to_row(skill_row: SkillTable, skill: SkillDefinition) -> None:
        skill_row.code = skill.code
        skill_row.name = skill.name
        skill_row.summary = skill.summary
        skill_row.purpose = skill.purpose
        skill_row.applicable_role_codes_json = SkillRepository._serialize_role_codes(
            skill.applicable_role_codes
        )
        skill_row.enabled = skill.enabled
        skill_row.current_version = skill.current_version
        skill_row.updated_at = skill.updated_at

    @staticmethod
    def _to_skill_domain(skill_row: SkillTable) -> SkillDefinition:
        return SkillDefinition(
            id=skill_row.id,
            code=skill_row.code,
            name=skill_row.name,
            summary=skill_row.summary,
            purpose=skill_row.purpose,
            applicable_role_codes=SkillRepository._deserialize_role_codes(
                skill_row.applicable_role_codes_json
            ),
            enabled=skill_row.enabled,
            current_version=skill_row.current_version,
            created_at=ensure_utc_datetime(skill_row.created_at),
            updated_at=ensure_utc_datetime(skill_row.updated_at),
            version_history=[],
        )

    @staticmethod
    def _build_version_row(version_record: SkillVersionRecord) -> SkillVersionTable:
        return SkillVersionTable(
            id=version_record.id,
            skill_id=version_record.skill_id,
            version=version_record.version,
            name=version_record.name,
            summary=version_record.summary,
            purpose=version_record.purpose,
            applicable_role_codes_json=SkillRepository._serialize_role_codes(
                version_record.applicable_role_codes
            ),
            enabled=version_record.enabled,
            change_note=version_record.change_note,
            created_at=version_record.created_at,
        )

    @staticmethod
    def _to_version_domain(version_row: SkillVersionTable) -> SkillVersionRecord:
        return SkillVersionRecord(
            id=version_row.id,
            skill_id=version_row.skill_id,
            version=version_row.version,
            name=version_row.name,
            summary=version_row.summary,
            purpose=version_row.purpose,
            applicable_role_codes=SkillRepository._deserialize_role_codes(
                version_row.applicable_role_codes_json
            ),
            enabled=version_row.enabled,
            change_note=version_row.change_note,
            created_at=ensure_utc_datetime(version_row.created_at),
        )

    @staticmethod
    def _build_binding_row(binding: ProjectRoleSkillBinding) -> ProjectRoleSkillBindingTable:
        return ProjectRoleSkillBindingTable(
            id=binding.id,
            project_id=binding.project_id,
            role_code=binding.role_code,
            skill_id=binding.skill_id,
            skill_code=binding.skill_code,
            skill_name=binding.skill_name,
            bound_version=binding.bound_version,
            binding_source=binding.binding_source,
            created_at=binding.created_at,
            updated_at=binding.updated_at,
        )

    @staticmethod
    def _to_binding_domain(
        binding_row: ProjectRoleSkillBindingTable,
    ) -> ProjectRoleSkillBinding:
        return ProjectRoleSkillBinding(
            id=binding_row.id,
            project_id=binding_row.project_id,
            role_code=binding_row.role_code,
            skill_id=binding_row.skill_id,
            skill_code=binding_row.skill_code,
            skill_name=binding_row.skill_name,
            bound_version=binding_row.bound_version,
            binding_source=binding_row.binding_source,
            created_at=ensure_utc_datetime(binding_row.created_at),
            updated_at=ensure_utc_datetime(binding_row.updated_at),
        )

    @staticmethod
    def _serialize_role_codes(values: list[ProjectRoleCode]) -> str:
        return json.dumps([value.value for value in values], ensure_ascii=False)

    @staticmethod
    def _deserialize_role_codes(raw_value: str | None) -> list[ProjectRoleCode]:
        if not raw_value:
            return []

        try:
            decoded_value = json.loads(raw_value)
        except json.JSONDecodeError:
            return []

        if not isinstance(decoded_value, list):
            return []

        normalized_codes: list[ProjectRoleCode] = []
        seen_codes: set[ProjectRoleCode] = set()
        for item in decoded_value:
            try:
                role_code = ProjectRoleCode(str(item).strip())
            except ValueError:
                continue

            if role_code in seen_codes:
                continue

            normalized_codes.append(role_code)
            seen_codes.add(role_code)

        return normalized_codes
