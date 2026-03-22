"""Persistence helpers for `RepositoryWorkspace` records."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db_tables import RepositoryWorkspaceTable
from app.domain._base import ensure_utc_datetime
from app.domain.repository_workspace import RepositoryWorkspace


class RepositoryWorkspaceRepository:
    """Encapsulate repository-workspace persistence operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, workspace: RepositoryWorkspace) -> RepositoryWorkspace:
        """Create or replace one project's bound repository workspace."""

        statement = select(RepositoryWorkspaceTable).where(
            RepositoryWorkspaceTable.project_id == workspace.project_id
        )
        workspace_row = self.session.execute(statement).scalar_one_or_none()

        if workspace_row is None:
            workspace_row = RepositoryWorkspaceTable(
                id=workspace.id,
                project_id=workspace.project_id,
                root_path=workspace.root_path,
                display_name=workspace.display_name,
                access_mode=workspace.access_mode,
                default_base_branch=workspace.default_base_branch,
                ignore_rule_summary_json=self._serialize_ignore_rule_summary(
                    workspace.ignore_rule_summary
                ),
                allowed_workspace_root=workspace.allowed_workspace_root,
                created_at=workspace.created_at,
                updated_at=workspace.updated_at,
            )
            self.session.add(workspace_row)
        else:
            workspace_row.root_path = workspace.root_path
            workspace_row.display_name = workspace.display_name
            workspace_row.access_mode = workspace.access_mode
            workspace_row.default_base_branch = workspace.default_base_branch
            workspace_row.ignore_rule_summary_json = self._serialize_ignore_rule_summary(
                workspace.ignore_rule_summary
            )
            workspace_row.allowed_workspace_root = workspace.allowed_workspace_root
            workspace_row.updated_at = workspace.updated_at

        self.session.commit()
        self.session.refresh(workspace_row)
        return self.to_domain_model(workspace_row)

    def get_by_project_id(self, project_id: UUID) -> RepositoryWorkspace | None:
        """Return the bound repository workspace for one project, if present."""

        statement = select(RepositoryWorkspaceTable).where(
            RepositoryWorkspaceTable.project_id == project_id
        )
        workspace_row = self.session.execute(statement).scalar_one_or_none()
        if workspace_row is None:
            return None

        return self.to_domain_model(workspace_row)

    def delete_by_project_id(self, project_id: UUID) -> RepositoryWorkspace | None:
        """Delete one project's bound repository workspace and return the removed row."""

        statement = select(RepositoryWorkspaceTable).where(
            RepositoryWorkspaceTable.project_id == project_id
        )
        workspace_row = self.session.execute(statement).scalar_one_or_none()
        if workspace_row is None:
            return None

        removed_workspace = self.to_domain_model(workspace_row)
        self.session.delete(workspace_row)
        self.session.commit()
        return removed_workspace

    @staticmethod
    def to_domain_model(workspace_row: RepositoryWorkspaceTable) -> RepositoryWorkspace:
        """Convert an ORM row back into the repository-workspace domain model."""

        return RepositoryWorkspace(
            id=workspace_row.id,
            project_id=workspace_row.project_id,
            root_path=workspace_row.root_path,
            display_name=workspace_row.display_name,
            access_mode=workspace_row.access_mode,
            default_base_branch=workspace_row.default_base_branch,
            ignore_rule_summary=RepositoryWorkspaceRepository._deserialize_ignore_rule_summary(
                workspace_row.ignore_rule_summary_json
            ),
            allowed_workspace_root=workspace_row.allowed_workspace_root,
            created_at=ensure_utc_datetime(workspace_row.created_at),
            updated_at=ensure_utc_datetime(workspace_row.updated_at),
        )

    @staticmethod
    def _serialize_ignore_rule_summary(ignore_rule_summary: list[str]) -> str:
        """Persist one ignore-summary list as JSON text in SQLite."""

        return json.dumps(ignore_rule_summary, ensure_ascii=False)

    @staticmethod
    def _deserialize_ignore_rule_summary(raw_value: str | None) -> list[str]:
        """Read one JSON-encoded ignore-summary list from SQLite."""

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
            if not isinstance(item, str):
                continue
            normalized_item = item.strip()
            if normalized_item:
                normalized_items.append(normalized_item)

        return normalized_items
