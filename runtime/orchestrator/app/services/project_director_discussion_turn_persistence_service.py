"""Transactional persistence coordinator for one assistant discussion turn.

Successful returns mean the assistant message and any governed discussion
writes have flushed into the caller-owned transaction.  This service never
commits or rolls back that transaction.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.project_director_discussion import DiscussionDelta
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.services.project_director_discussion_delta_apply_service import (
    DiscussionDeltaApplyStatus,
    GovernedDiscussionDeltaApplyResult,
    ProjectDirectorDiscussionDeltaApplyService,
)


@dataclass(frozen=True, slots=True)
class PersistedDiscussionTurnResult:
    """The caller-visible persistence result for one assistant turn."""

    assistant_message: ProjectDirectorMessage
    assistant_message_inserted: bool
    delta_apply_result: GovernedDiscussionDeltaApplyResult


class ProjectDirectorDiscussionTurnPersistenceService:
    """Persist an assistant message and D2 delta in one caller-owned savepoint.

    The coordinator does not own the outer ``Session`` transaction.  A caller
    may commit the returned state or roll back the message, discussion events,
    and workspace snapshot together.
    """

    def __init__(
        self,
        session: Session,
        message_repository: ProjectDirectorMessageRepository | None = None,
        delta_apply_service: ProjectDirectorDiscussionDeltaApplyService | None = None,
    ) -> None:
        self._session = session
        self._messages = message_repository or ProjectDirectorMessageRepository(session)
        self._delta_apply = delta_apply_service or (
            ProjectDirectorDiscussionDeltaApplyService(session)
        )

    def persist_assistant_turn(
        self,
        *,
        session_id: UUID,
        project_id: UUID | None,
        assistant_message: ProjectDirectorMessage,
        available_messages: Sequence[ProjectDirectorMessage],
        delta: DiscussionDelta,
        occurred_at: datetime | None = None,
    ) -> PersistedDiscussionTurnResult:
        """Flush one assistant turn without committing the caller transaction."""

        self._validate_assistant_message(
            session_id=session_id,
            project_id=project_id,
            assistant_message=assistant_message,
        )
        existing_message = self._messages.get_by_id(assistant_message.id)
        if existing_message is not None and not self._messages_equal(
            existing_message, assistant_message
        ):
            raise ValueError("discussion_turn_assistant_message_conflict")
        if existing_message is None and assistant_message.sequence_no != (
            self._messages.get_next_sequence_no(session_id=session_id)
        ):
            raise ValueError("discussion_turn_assistant_message_sequence_mismatch")

        with self._session.begin_nested():
            persisted_message = existing_message
            assistant_message_inserted = persisted_message is None
            if persisted_message is None:
                try:
                    persisted_message = self._messages.create(assistant_message)
                except IntegrityError as exc:
                    raise ValueError(
                        "discussion_turn_assistant_message_concurrent_conflict"
                    ) from exc

            normalized_messages = self._normalize_available_messages(
                available_messages=available_messages,
                persisted_assistant_message=persisted_message,
            )
            delta_apply_result = self._delta_apply.apply_delta(
                session_id=session_id,
                project_id=project_id,
                assistant_message=persisted_message,
                available_messages=normalized_messages,
                delta=delta,
                occurred_at=occurred_at,
            )
            self._validate_replay_state(
                assistant_message_inserted=assistant_message_inserted,
                delta=delta,
                delta_apply_result=delta_apply_result,
            )

        return PersistedDiscussionTurnResult(
            assistant_message=persisted_message,
            assistant_message_inserted=assistant_message_inserted,
            delta_apply_result=delta_apply_result,
        )

    @staticmethod
    def _validate_assistant_message(
        *,
        session_id: UUID,
        project_id: UUID | None,
        assistant_message: ProjectDirectorMessage,
    ) -> None:
        if assistant_message.role != ProjectDirectorMessageRole.ASSISTANT:
            raise ValueError("discussion_turn_assistant_message_role_invalid")
        if assistant_message.session_id != session_id:
            raise ValueError("discussion_turn_assistant_message_session_mismatch")
        if assistant_message.related_project_id != project_id:
            raise ValueError("discussion_turn_assistant_message_project_mismatch")

    @classmethod
    def _normalize_available_messages(
        cls,
        *,
        available_messages: Sequence[ProjectDirectorMessage],
        persisted_assistant_message: ProjectDirectorMessage,
    ) -> tuple[ProjectDirectorMessage, ...]:
        normalized: list[ProjectDirectorMessage] = []
        by_id: dict[UUID, ProjectDirectorMessage] = {}
        for message in available_messages:
            existing = by_id.get(message.id)
            if existing is None:
                by_id[message.id] = message
                normalized.append(message)
            elif not cls._messages_equal(existing, message):
                raise ValueError("discussion_turn_available_message_conflict")

        supplied_assistant = by_id.get(persisted_assistant_message.id)
        if supplied_assistant is None:
            normalized.append(persisted_assistant_message)
        elif not cls._messages_equal(
            supplied_assistant, persisted_assistant_message
        ):
            raise ValueError("discussion_turn_available_message_conflict")
        return tuple(normalized)

    @staticmethod
    def _validate_replay_state(
        *,
        assistant_message_inserted: bool,
        delta: DiscussionDelta,
        delta_apply_result: GovernedDiscussionDeltaApplyResult,
    ) -> None:
        status = delta_apply_result.status
        if assistant_message_inserted:
            if status is DiscussionDeltaApplyStatus.REPLAYED:
                raise ValueError("discussion_turn_replay_state_mismatch")
            return

        if status is DiscussionDeltaApplyStatus.REPLAYED:
            return
        if status is DiscussionDeltaApplyStatus.REQUIRES_CONFIRMATION:
            return
        if not delta.operations and status is DiscussionDeltaApplyStatus.NO_CHANGES:
            return
        if status is DiscussionDeltaApplyStatus.APPLIED:
            raise ValueError("discussion_turn_replay_state_mismatch")
        raise ValueError("discussion_turn_replay_state_mismatch")

    @staticmethod
    def _messages_equal(
        left: ProjectDirectorMessage, right: ProjectDirectorMessage
    ) -> bool:
        return left.model_dump(mode="python") == right.model_dump(mode="python")
