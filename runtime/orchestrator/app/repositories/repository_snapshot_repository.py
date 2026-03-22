"""Persistence helpers for `RepositorySnapshot` records."""

from __future__ import annotations

import json
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db_tables import RepositorySnapshotTable
from app.domain._base import ensure_utc_datetime
from app.domain.repository_snapshot import (
    RepositoryLanguageStat,
    RepositorySnapshot,
    RepositoryTreeNode,
)


class RepositorySnapshotRepository:
    """Encapsulate repository-snapshot persistence operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, snapshot: RepositorySnapshot) -> RepositorySnapshot:
        """Create or replace one project's latest repository snapshot."""

        statement = select(RepositorySnapshotTable).where(
            RepositorySnapshotTable.project_id == snapshot.project_id
        )
        snapshot_row = self.session.execute(statement).scalar_one_or_none()

        if snapshot_row is None:
            snapshot_row = RepositorySnapshotTable(
                id=snapshot.id,
                project_id=snapshot.project_id,
                repository_workspace_id=snapshot.repository_workspace_id,
                repository_root_path=snapshot.repository_root_path,
                status=snapshot.status,
                directory_count=snapshot.directory_count,
                file_count=snapshot.file_count,
                ignored_directory_names_json=self._serialize_model_list(
                    snapshot.ignored_directory_names
                ),
                language_breakdown_json=self._serialize_model_list(
                    snapshot.language_breakdown
                ),
                tree_json=self._serialize_model_list(snapshot.tree),
                scan_error=snapshot.scan_error,
                scanned_at=snapshot.scanned_at,
                created_at=snapshot.created_at,
                updated_at=snapshot.updated_at,
            )
            self.session.add(snapshot_row)
        else:
            snapshot_row.repository_workspace_id = snapshot.repository_workspace_id
            snapshot_row.repository_root_path = snapshot.repository_root_path
            snapshot_row.status = snapshot.status
            snapshot_row.directory_count = snapshot.directory_count
            snapshot_row.file_count = snapshot.file_count
            snapshot_row.ignored_directory_names_json = self._serialize_model_list(
                snapshot.ignored_directory_names
            )
            snapshot_row.language_breakdown_json = self._serialize_model_list(
                snapshot.language_breakdown
            )
            snapshot_row.tree_json = self._serialize_model_list(snapshot.tree)
            snapshot_row.scan_error = snapshot.scan_error
            snapshot_row.scanned_at = snapshot.scanned_at
            snapshot_row.updated_at = snapshot.updated_at

        self.session.commit()
        self.session.refresh(snapshot_row)
        return self.to_domain_model(snapshot_row)

    def get_by_project_id(self, project_id: UUID) -> RepositorySnapshot | None:
        """Return one project's latest repository snapshot, if present."""

        statement = select(RepositorySnapshotTable).where(
            RepositorySnapshotTable.project_id == project_id
        )
        snapshot_row = self.session.execute(statement).scalar_one_or_none()
        if snapshot_row is None:
            return None

        return self.to_domain_model(snapshot_row)

    @staticmethod
    def to_domain_model(snapshot_row: RepositorySnapshotTable) -> RepositorySnapshot:
        """Convert an ORM row back into the repository-snapshot domain model."""

        return RepositorySnapshot(
            id=snapshot_row.id,
            project_id=snapshot_row.project_id,
            repository_workspace_id=snapshot_row.repository_workspace_id,
            repository_root_path=snapshot_row.repository_root_path,
            status=snapshot_row.status,
            directory_count=snapshot_row.directory_count,
            file_count=snapshot_row.file_count,
            ignored_directory_names=RepositorySnapshotRepository._deserialize_string_list(
                snapshot_row.ignored_directory_names_json
            ),
            language_breakdown=RepositorySnapshotRepository._deserialize_model_list(
                snapshot_row.language_breakdown_json,
                RepositoryLanguageStat,
            ),
            tree=RepositorySnapshotRepository._deserialize_model_list(
                snapshot_row.tree_json,
                RepositoryTreeNode,
            ),
            scan_error=snapshot_row.scan_error,
            scanned_at=ensure_utc_datetime(snapshot_row.scanned_at),
            created_at=ensure_utc_datetime(snapshot_row.created_at),
            updated_at=ensure_utc_datetime(snapshot_row.updated_at),
        )

    @staticmethod
    def _serialize_model_list(raw_items: list[str] | list[object]) -> str:
        """Persist one list of scalars/domain models as JSON text in SQLite."""

        serialized_items: list[object] = []
        for item in raw_items:
            if hasattr(item, "model_dump"):
                serialized_items.append(item.model_dump(mode="json"))
            else:
                serialized_items.append(item)

        return json.dumps(serialized_items, ensure_ascii=False)

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
            if not isinstance(item, str):
                continue
            normalized_item = item.strip()
            if normalized_item:
                normalized_items.append(normalized_item)

        return normalized_items

    @staticmethod
    def _deserialize_model_list(
        raw_value: str | None,
        model_type: type[RepositoryLanguageStat] | type[RepositoryTreeNode],
    ) -> list[RepositoryLanguageStat] | list[RepositoryTreeNode]:
        """Read one JSON-encoded model list from SQLite."""

        if not raw_value:
            return []

        try:
            decoded_value = json.loads(raw_value)
        except json.JSONDecodeError:
            return []

        if not isinstance(decoded_value, list):
            return []

        normalized_items: list[RepositoryLanguageStat] | list[RepositoryTreeNode] = []
        for item in decoded_value:
            if not isinstance(item, dict):
                continue
            try:
                normalized_items.append(model_type.model_validate(item))
            except ValidationError:
                continue

        return normalized_items
