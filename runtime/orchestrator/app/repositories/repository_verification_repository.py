"""Persistence helpers for V4 Day09 repository verification templates."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db_tables import RepositoryVerificationTemplateTable
from app.domain._base import ensure_utc_datetime
from app.domain.repository_verification import (
    RepositoryVerificationCategory,
    RepositoryVerificationTemplate,
)


_CATEGORY_ORDER = {
    RepositoryVerificationCategory.BUILD: 0,
    RepositoryVerificationCategory.TEST: 1,
    RepositoryVerificationCategory.LINT: 2,
    RepositoryVerificationCategory.TYPECHECK: 3,
}


class RepositoryVerificationRepository:
    """Encapsulate Day09 repository verification-template persistence."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_by_project_id(self, project_id: UUID) -> list[RepositoryVerificationTemplate]:
        """Return all verification templates for one project."""

        statement = select(RepositoryVerificationTemplateTable).where(
            RepositoryVerificationTemplateTable.project_id == project_id
        )
        template_rows = self.session.execute(statement).scalars().all()
        templates = [self.to_domain_model(template_row) for template_row in template_rows]
        return sorted(templates, key=lambda item: _CATEGORY_ORDER.get(item.category, 999))

    def get_by_ids_for_project(
        self,
        project_id: UUID,
        template_ids: list[UUID],
    ) -> dict[UUID, RepositoryVerificationTemplate]:
        """Resolve one project-scoped template set by ID."""

        unique_ids = list(dict.fromkeys(template_ids))
        if not unique_ids:
            return {}

        statement = select(RepositoryVerificationTemplateTable).where(
            RepositoryVerificationTemplateTable.project_id == project_id,
            RepositoryVerificationTemplateTable.id.in_(unique_ids),
        )
        template_rows = self.session.execute(statement).scalars().all()
        return {
            template.id: template
            for template in (
                self.to_domain_model(template_row) for template_row in template_rows
            )
        }

    def replace_for_project(
        self,
        project_id: UUID,
        templates: list[RepositoryVerificationTemplate],
    ) -> list[RepositoryVerificationTemplate]:
        """Replace one project's full Day09 baseline while preserving category IDs."""

        statement = select(RepositoryVerificationTemplateTable).where(
            RepositoryVerificationTemplateTable.project_id == project_id
        )
        existing_rows = self.session.execute(statement).scalars().all()
        existing_by_category = {
            template_row.category: template_row for template_row in existing_rows
        }
        incoming_categories = {template.category for template in templates}

        for template_row in existing_rows:
            if template_row.category in incoming_categories:
                continue
            self.session.delete(template_row)

        for template in templates:
            existing_row = existing_by_category.get(template.category)
            if existing_row is None:
                self.session.add(
                    RepositoryVerificationTemplateTable(
                        id=template.id,
                        project_id=project_id,
                        category=template.category,
                        name=template.name,
                        command=template.command,
                        working_directory=template.working_directory,
                        timeout_seconds=template.timeout_seconds,
                        enabled_by_default=template.enabled_by_default,
                        description=template.description,
                        created_at=template.created_at,
                        updated_at=template.updated_at,
                    )
                )
                continue

            existing_row.name = template.name
            existing_row.command = template.command
            existing_row.working_directory = template.working_directory
            existing_row.timeout_seconds = template.timeout_seconds
            existing_row.enabled_by_default = template.enabled_by_default
            existing_row.description = template.description
            existing_row.updated_at = template.updated_at

        self.session.commit()
        return self.list_by_project_id(project_id)

    @staticmethod
    def to_domain_model(
        template_row: RepositoryVerificationTemplateTable,
    ) -> RepositoryVerificationTemplate:
        """Convert one ORM row into the Day09 domain model."""

        return RepositoryVerificationTemplate(
            id=template_row.id,
            project_id=template_row.project_id,
            category=template_row.category,
            name=template_row.name,
            command=template_row.command,
            working_directory=template_row.working_directory,
            timeout_seconds=template_row.timeout_seconds,
            enabled_by_default=template_row.enabled_by_default,
            description=template_row.description,
            created_at=ensure_utc_datetime(template_row.created_at),
            updated_at=ensure_utc_datetime(template_row.updated_at),
        )
