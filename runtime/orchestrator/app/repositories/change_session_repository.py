"""Persistence helpers for `ChangeSession` records."""

from __future__ import annotations

import json
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db_tables import ChangeSessionTable
from app.domain._base import ensure_utc_datetime
from app.domain.change_session import ChangeSession, ChangeSessionDirtyFile


class ChangeSessionRepository:
    """Encapsulate Day03 change-session persistence operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, change_session: ChangeSession) -> ChangeSession:
        """Create or replace one project's active change-session snapshot."""

        statement = select(ChangeSessionTable).where(
            ChangeSessionTable.project_id == change_session.project_id
        )
        session_row = self.session.execute(statement).scalar_one_or_none()

        if session_row is None:
            session_row = ChangeSessionTable(
                id=change_session.id,
                project_id=change_session.project_id,
                repository_workspace_id=change_session.repository_workspace_id,
                repository_root_path=change_session.repository_root_path,
                current_branch=change_session.current_branch,
                head_ref=change_session.head_ref,
                head_commit_sha=change_session.head_commit_sha,
                baseline_branch=change_session.baseline_branch,
                baseline_ref=change_session.baseline_ref,
                baseline_commit_sha=change_session.baseline_commit_sha,
                workspace_status=change_session.workspace_status,
                guard_status=change_session.guard_status,
                guard_summary=change_session.guard_summary,
                blocking_reasons_json=self._serialize_string_list(
                    change_session.blocking_reasons
                ),
                dirty_file_count=change_session.dirty_file_count,
                dirty_files_truncated=change_session.dirty_files_truncated,
                dirty_files_json=self._serialize_dirty_files(change_session.dirty_files),
                created_at=change_session.created_at,
                updated_at=change_session.updated_at,
            )
            self.session.add(session_row)
        else:
            session_row.repository_workspace_id = change_session.repository_workspace_id
            session_row.repository_root_path = change_session.repository_root_path
            session_row.current_branch = change_session.current_branch
            session_row.head_ref = change_session.head_ref
            session_row.head_commit_sha = change_session.head_commit_sha
            session_row.baseline_branch = change_session.baseline_branch
            session_row.baseline_ref = change_session.baseline_ref
            session_row.baseline_commit_sha = change_session.baseline_commit_sha
            session_row.workspace_status = change_session.workspace_status
            session_row.guard_status = change_session.guard_status
            session_row.guard_summary = change_session.guard_summary
            session_row.blocking_reasons_json = self._serialize_string_list(
                change_session.blocking_reasons
            )
            session_row.dirty_file_count = change_session.dirty_file_count
            session_row.dirty_files_truncated = change_session.dirty_files_truncated
            session_row.dirty_files_json = self._serialize_dirty_files(
                change_session.dirty_files
            )
            session_row.created_at = change_session.created_at
            session_row.updated_at = change_session.updated_at

        self.session.commit()
        self.session.refresh(session_row)
        return self.to_domain_model(session_row)

    def get_by_project_id(self, project_id: UUID) -> ChangeSession | None:
        """Return one project's active change-session snapshot, if present."""

        statement = select(ChangeSessionTable).where(
            ChangeSessionTable.project_id == project_id
        )
        session_row = self.session.execute(statement).scalar_one_or_none()
        if session_row is None:
            return None

        return self.to_domain_model(session_row)

    @staticmethod
    def to_domain_model(session_row: ChangeSessionTable) -> ChangeSession:
        """Convert an ORM row back into the Day03 change-session domain model."""

        return ChangeSession(
            id=session_row.id,
            project_id=session_row.project_id,
            repository_workspace_id=session_row.repository_workspace_id,
            repository_root_path=session_row.repository_root_path,
            current_branch=session_row.current_branch,
            head_ref=session_row.head_ref,
            head_commit_sha=session_row.head_commit_sha,
            baseline_branch=session_row.baseline_branch,
            baseline_ref=session_row.baseline_ref,
            baseline_commit_sha=session_row.baseline_commit_sha,
            workspace_status=session_row.workspace_status,
            guard_status=session_row.guard_status,
            guard_summary=session_row.guard_summary,
            blocking_reasons=ChangeSessionRepository._deserialize_string_list(
                session_row.blocking_reasons_json
            ),
            dirty_file_count=session_row.dirty_file_count,
            dirty_files_truncated=session_row.dirty_files_truncated,
            dirty_files=ChangeSessionRepository._deserialize_dirty_files(
                session_row.dirty_files_json
            ),
            created_at=ensure_utc_datetime(session_row.created_at),
            updated_at=ensure_utc_datetime(session_row.updated_at),
        )

    @staticmethod
    def _serialize_string_list(raw_items: list[str]) -> str:
        """Persist one string list as JSON text in SQLite."""

        return json.dumps(raw_items, ensure_ascii=False)

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
    def _serialize_dirty_files(dirty_files: list[ChangeSessionDirtyFile]) -> str:
        """Persist one dirty-file preview list as JSON text in SQLite."""

        return json.dumps(
            [dirty_file.model_dump(mode="json") for dirty_file in dirty_files],
            ensure_ascii=False,
        )

    @staticmethod
    def _deserialize_dirty_files(raw_value: str | None) -> list[ChangeSessionDirtyFile]:
        """Read one JSON-encoded dirty-file preview list from SQLite."""

        if not raw_value:
            return []

        try:
            decoded_value = json.loads(raw_value)
        except json.JSONDecodeError:
            return []

        if not isinstance(decoded_value, list):
            return []

        normalized_items: list[ChangeSessionDirtyFile] = []
        for item in decoded_value:
            if not isinstance(item, dict):
                continue

            try:
                normalized_items.append(ChangeSessionDirtyFile.model_validate(item))
            except ValidationError:
                continue

        return normalized_items
