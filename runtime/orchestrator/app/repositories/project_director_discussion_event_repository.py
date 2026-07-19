"""Append-only persistence for Project Director discussion events."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db_tables import (
    ProjectDirectorDiscussionEventTable,
    ProjectDirectorMessageTable,
    ProjectDirectorSessionTable,
)
from app.domain._base import ensure_utc_datetime
from app.domain.project_director_discussion import DiscussionEvent


class ProjectDirectorDiscussionEventRepository:
    """Append and read immutable discussion events without committing."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def append_if_absent(
        self,
        *,
        event: DiscussionEvent,
        idempotency_key: str,
    ) -> tuple[DiscussionEvent, bool]:
        """Append once, or return an equivalent prior event for a replay."""

        normalized_key = self._validate_idempotency_key(idempotency_key)
        existing = self.get_by_idempotency_key(
            session_id=event.session_id,
            idempotency_key=normalized_key,
        )
        if existing is not None:
            self._ensure_idempotency_equivalent(existing, event)
            return existing, False

        self._validate_session_project(event)
        self._validate_source_messages(event)
        self._validate_supersedes_target(event)

        row = self._to_row(event, idempotency_key=normalized_key)
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError:
            existing = self.get_by_idempotency_key(
                session_id=event.session_id,
                idempotency_key=normalized_key,
            )
            if existing is None:
                raise
            self._ensure_idempotency_equivalent(existing, event)
            return existing, False
        return self._to_domain(row), True

    def get_by_id(self, *, event_id: UUID) -> DiscussionEvent | None:
        row = self._session.get(ProjectDirectorDiscussionEventTable, event_id)
        return self._to_domain(row) if row is not None else None

    def get_by_idempotency_key(
        self,
        *,
        session_id: UUID,
        idempotency_key: str,
    ) -> DiscussionEvent | None:
        row = self._session.execute(
            select(ProjectDirectorDiscussionEventTable).where(
                ProjectDirectorDiscussionEventTable.session_id == session_id,
                ProjectDirectorDiscussionEventTable.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        return self._to_domain(row) if row is not None else None

    def get_next_sequence_no(self, *, session_id: UUID) -> int:
        row = self._session.execute(
            select(ProjectDirectorDiscussionEventTable.sequence_no)
            .where(ProjectDirectorDiscussionEventTable.session_id == session_id)
            .order_by(ProjectDirectorDiscussionEventTable.sequence_no.desc())
            .limit(1)
        ).scalar_one_or_none()
        return 1 if row is None else int(row) + 1

    def list_by_session_id(self, *, session_id: UUID) -> list[DiscussionEvent]:
        rows = self._session.execute(
            select(ProjectDirectorDiscussionEventTable)
            .where(ProjectDirectorDiscussionEventTable.session_id == session_id)
            .order_by(
                ProjectDirectorDiscussionEventTable.sequence_no.asc(),
                ProjectDirectorDiscussionEventTable.created_at.asc(),
            )
        ).scalars().all()
        return [self._to_domain(row) for row in rows]

    def _validate_session_project(self, event: DiscussionEvent) -> None:
        session_row = self._session.get(ProjectDirectorSessionTable, event.session_id)
        if session_row is None:
            raise ValueError("discussion_event_session_not_found")
        if event.project_id != session_row.project_id:
            raise ValueError("discussion_event_project_session_mismatch")

    def _validate_source_messages(self, event: DiscussionEvent) -> None:
        for message_id in event.source_message_ids:
            message_row = self._session.get(ProjectDirectorMessageTable, message_id)
            if message_row is None:
                raise ValueError("discussion_event_source_message_not_found")
            if message_row.session_id != event.session_id:
                raise ValueError("discussion_event_source_message_session_mismatch")

    def _validate_supersedes_target(self, event: DiscussionEvent) -> None:
        if event.supersedes_event_id is None:
            return
        target = self._session.get(
            ProjectDirectorDiscussionEventTable, event.supersedes_event_id
        )
        if target is None:
            raise ValueError("discussion_event_supersedes_not_found")
        if target.session_id != event.session_id:
            raise ValueError("discussion_event_supersedes_session_mismatch")

    @staticmethod
    def _json_dump(value: object) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        )

    @staticmethod
    def _validate_idempotency_key(idempotency_key: str) -> str:
        normalized_key = idempotency_key.strip()
        sensitive_markers = ("api_key", "api key", "authorization", "bearer ", "sk-")
        if (
            not normalized_key
            or len(normalized_key) > 256
            or any(marker in normalized_key.lower() for marker in sensitive_markers)
        ):
            raise ValueError("discussion_event_idempotency_key_invalid")
        return normalized_key

    @staticmethod
    def _json_object(raw_value: str, *, field_name: str) -> dict[str, Any]:
        try:
            value = json.loads(raw_value)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid_discussion_event_{field_name}_json") from exc
        if not isinstance(value, dict):
            raise ValueError(f"invalid_discussion_event_{field_name}_json")
        return value

    @staticmethod
    def _json_uuid_list(raw_value: str, *, field_name: str) -> list[UUID]:
        try:
            value = json.loads(raw_value)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid_discussion_event_{field_name}_json") from exc
        if not isinstance(value, list):
            raise ValueError(f"invalid_discussion_event_{field_name}_json")
        try:
            return [UUID(str(item)) for item in value]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid_discussion_event_{field_name}_json") from exc

    @classmethod
    def _to_row(
        cls,
        event: DiscussionEvent,
        *,
        idempotency_key: str,
    ) -> ProjectDirectorDiscussionEventTable:
        return ProjectDirectorDiscussionEventTable(
            id=event.id,
            session_id=event.session_id,
            project_id=event.project_id,
            sequence_no=event.sequence_no,
            event_type=event.event_type,
            subject_key=event.subject_key,
            content=event.content,
            status=event.status,
            payload_json=cls._json_dump(event.payload),
            source_message_ids_json=cls._json_dump(event.source_message_ids),
            supersedes_event_id=event.supersedes_event_id,
            created_by=event.created_by,
            confidence=event.confidence,
            idempotency_key=idempotency_key,
            created_at=event.created_at,
            source_surface=event.source_surface,
            source_entity_type=event.source_entity_type,
            source_entity_id=event.source_entity_id,
            trigger_type=event.trigger_type,
            interaction_case_id=event.interaction_case_id,
            external_context_pack_id=event.external_context_pack_id,
        )

    @classmethod
    def _to_domain(
        cls,
        row: ProjectDirectorDiscussionEventTable,
    ) -> DiscussionEvent:
        try:
            return DiscussionEvent(
                id=row.id,
                session_id=row.session_id,
                project_id=row.project_id,
                sequence_no=row.sequence_no,
                event_type=row.event_type,
                subject_key=row.subject_key,
                content=row.content,
                status=row.status,
                payload=cls._json_object(row.payload_json, field_name="payload"),
                source_message_ids=cls._json_uuid_list(
                    row.source_message_ids_json, field_name="source_message_ids"
                ),
                supersedes_event_id=row.supersedes_event_id,
                created_by=row.created_by,
                confidence=row.confidence,
                created_at=ensure_utc_datetime(row.created_at),
                source_surface=row.source_surface,
                source_entity_type=row.source_entity_type,
                source_entity_id=row.source_entity_id,
                trigger_type=row.trigger_type,
                interaction_case_id=row.interaction_case_id,
                external_context_pack_id=row.external_context_pack_id,
            )
        except ValidationError as exc:
            raise ValueError(f"invalid_discussion_event_row:{row.id}") from exc

    @classmethod
    def _ensure_idempotency_equivalent(
        cls,
        existing: DiscussionEvent,
        incoming: DiscussionEvent,
    ) -> None:
        fields = (
            "session_id",
            "project_id",
            "event_type",
            "subject_key",
            "content",
            "status",
            "source_message_ids",
            "supersedes_event_id",
            "created_by",
            "confidence",
            "source_surface",
            "source_entity_type",
            "source_entity_id",
            "trigger_type",
            "interaction_case_id",
            "external_context_pack_id",
        )
        if (
            any(getattr(existing, field) != getattr(incoming, field) for field in fields)
            or cls._canonical_payload(existing.payload)
            != cls._canonical_payload(incoming.payload)
        ):
            raise ValueError("discussion_event_idempotency_conflict")

    @classmethod
    def _canonical_payload(cls, payload: dict[str, Any]) -> str:
        """Return the persisted JSON representation used for payload equivalence."""

        return cls._json_dump(payload)
