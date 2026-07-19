"""Optimistic-lock persistence for Project Director discussion workspaces."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.db_tables import (
    ProjectDirectorDiscussionWorkspaceTable,
    ProjectDirectorSessionTable,
)
from app.domain._base import ensure_utc_datetime, utc_now
from app.domain.project_director_discussion import DiscussionWorkspace


class ProjectDirectorDiscussionWorkspaceRepository:
    """Persist one derived workspace per session without committing."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_session_id(self, *, session_id: UUID) -> DiscussionWorkspace | None:
        row = self._session.get(ProjectDirectorDiscussionWorkspaceTable, session_id)
        return self._to_domain(row) if row is not None else None

    def create_if_absent(
        self,
        *,
        workspace: DiscussionWorkspace,
    ) -> tuple[DiscussionWorkspace, bool]:
        """Create version-zero workspace once, preserving a concurrent prior row."""

        self._validate_session_project(workspace)
        if workspace.version_no != 0 or workspace.last_event_sequence_no != 0:
            raise ValueError("discussion_workspace_initial_version_invalid")

        existing = self.get_by_session_id(session_id=workspace.session_id)
        if existing is not None:
            self._ensure_project_matches(existing, workspace)
            return existing, False

        row = self._to_row(workspace)
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError:
            existing = self.get_by_session_id(session_id=workspace.session_id)
            if existing is None:
                raise
            self._ensure_project_matches(existing, workspace)
            return existing, False
        return self._to_domain(row), True

    def update_if_version(
        self,
        *,
        workspace: DiscussionWorkspace,
        expected_version_no: int,
    ) -> DiscussionWorkspace:
        """Compare-and-swap one snapshot without overwriting a newer version."""

        self._validate_session_project(workspace)
        if workspace.version_no != expected_version_no + 1:
            raise ValueError("discussion_workspace_version_increment_invalid")

        state_json = self._state_json(workspace)
        now = utc_now()
        result = self._session.execute(
            update(ProjectDirectorDiscussionWorkspaceTable)
            .where(
                ProjectDirectorDiscussionWorkspaceTable.session_id == workspace.session_id,
                ProjectDirectorDiscussionWorkspaceTable.version_no == expected_version_no,
            )
            .values(
                project_id=workspace.project_id,
                topic=workspace.topic,
                discussion_status=workspace.discussion_status,
                state_json=state_json,
                version_no=workspace.version_no,
                last_event_sequence_no=workspace.last_event_sequence_no,
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            raise ValueError("discussion_workspace_stale_version")
        row = self._session.get(ProjectDirectorDiscussionWorkspaceTable, workspace.session_id)
        if row is None:
            raise ValueError("discussion_workspace_not_found")
        return self._to_domain(row)

    def _validate_session_project(self, workspace: DiscussionWorkspace) -> None:
        session_row = self._session.get(ProjectDirectorSessionTable, workspace.session_id)
        if session_row is None:
            raise ValueError("discussion_workspace_session_not_found")
        if workspace.project_id != session_row.project_id:
            raise ValueError("discussion_workspace_project_session_mismatch")

    @staticmethod
    def _ensure_project_matches(
        existing: DiscussionWorkspace,
        incoming: DiscussionWorkspace,
    ) -> None:
        if existing.project_id != incoming.project_id:
            raise ValueError("discussion_workspace_project_session_mismatch")

    @staticmethod
    def _json_dump(value: object) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        )

    @classmethod
    def _state_json(cls, workspace: DiscussionWorkspace) -> str:
        return cls._json_dump(
            {
                "active_option_ids": workspace.active_option_ids,
                "preferred_option_id": workspace.preferred_option_id,
                "active_constraint_ids": workspace.active_constraint_ids,
                "open_question_ids": workspace.open_question_ids,
                "temporary_conclusion_ids": workspace.temporary_conclusion_ids,
                "confirmed_decision_ids": workspace.confirmed_decision_ids,
                "latest_user_correction_event_id": workspace.latest_user_correction_event_id,
            }
        )

    @staticmethod
    def _parse_uuid_list(state: dict[str, Any], field_name: str) -> list[UUID]:
        value = state.get(field_name, [])
        if not isinstance(value, list):
            raise ValueError("invalid_discussion_workspace_state_json")
        try:
            return [UUID(str(item)) for item in value]
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_discussion_workspace_state_json") from exc

    @staticmethod
    def _parse_optional_uuid(state: dict[str, Any], field_name: str) -> UUID | None:
        value = state.get(field_name)
        if value is None:
            return None
        try:
            return UUID(str(value))
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_discussion_workspace_state_json") from exc

    @classmethod
    def _parse_state(cls, raw_value: str) -> dict[str, Any]:
        try:
            state = json.loads(raw_value)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid_discussion_workspace_state_json") from exc
        if not isinstance(state, dict):
            raise ValueError("invalid_discussion_workspace_state_json")
        return state

    @classmethod
    def _to_row(
        cls, workspace: DiscussionWorkspace
    ) -> ProjectDirectorDiscussionWorkspaceTable:
        return ProjectDirectorDiscussionWorkspaceTable(
            session_id=workspace.session_id,
            project_id=workspace.project_id,
            topic=workspace.topic,
            discussion_status=workspace.discussion_status,
            state_json=cls._state_json(workspace),
            version_no=workspace.version_no,
            last_event_sequence_no=workspace.last_event_sequence_no,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
        )

    @classmethod
    def _to_domain(
        cls, row: ProjectDirectorDiscussionWorkspaceTable
    ) -> DiscussionWorkspace:
        state = cls._parse_state(row.state_json)
        try:
            return DiscussionWorkspace(
                session_id=row.session_id,
                project_id=row.project_id,
                topic=row.topic,
                discussion_status=row.discussion_status,
                active_option_ids=cls._parse_uuid_list(state, "active_option_ids"),
                preferred_option_id=cls._parse_optional_uuid(
                    state, "preferred_option_id"
                ),
                active_constraint_ids=cls._parse_uuid_list(
                    state, "active_constraint_ids"
                ),
                open_question_ids=cls._parse_uuid_list(state, "open_question_ids"),
                temporary_conclusion_ids=cls._parse_uuid_list(
                    state, "temporary_conclusion_ids"
                ),
                confirmed_decision_ids=cls._parse_uuid_list(
                    state, "confirmed_decision_ids"
                ),
                latest_user_correction_event_id=cls._parse_optional_uuid(
                    state, "latest_user_correction_event_id"
                ),
                version_no=row.version_no,
                last_event_sequence_no=row.last_event_sequence_no,
                created_at=ensure_utc_datetime(row.created_at),
                updated_at=ensure_utc_datetime(row.updated_at),
            )
        except ValidationError as exc:
            raise ValueError(f"invalid_discussion_workspace_row:{row.session_id}") from exc
