"""Atomically persist one already-supervised Director Runtime session turn.

This C4-B coordinator consumes a C4-A result only.  It never invokes a runtime,
creates execution records, or commits the caller's transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain._base import ensure_utc_datetime
from app.domain.project_director_message import ProjectDirectorMessage, ProjectDirectorMessageRole
from app.repositories.project_director_discussion_event_repository import (
    ProjectDirectorDiscussionEventRepository,
)
from app.repositories.project_director_discussion_workspace_repository import (
    ProjectDirectorDiscussionWorkspaceRepository,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.services.director_runtime_result_discussion_admission_service import (
    DirectorRuntimeDiscussionAdmissionResult,
    DirectorRuntimeResultDiscussionAdmissionService,
)
from app.services.director_runtime_result_discussion_persistence_service import (
    DirectorRuntimeDiscussionPersistenceResult,
    DirectorRuntimeDiscussionPersistenceStatus,
    DirectorRuntimeResultDiscussionPersistenceService,
)
from app.services.director_runtime_result_formalization_admission_service import (
    DirectorRuntimeFormalizationAdmissionResult,
    DirectorRuntimeFormalizationAdmissionStatus,
    DirectorRuntimeResultFormalizationAdmissionService,
)
from app.services.director_runtime_result_formalization_persistence_service import (
    DirectorRuntimeFormalizationPersistenceResult,
    DirectorRuntimeResultFormalizationPersistenceService,
)
from app.services.director_runtime_session_turn_service import (
    DirectorRuntimeSessionTurnResult,
)
from app.services.director_runtime_supervisor_service import DirectorRuntimeAttemptState


class DirectorRuntimeGovernedTurnPersistenceError(RuntimeError):
    """Stable fail-closed C4-B persistence rejection."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class DirectorRuntimeGovernedTurnPersistenceStatus(StrEnum):
    PERSISTED = "persisted"
    CONFIRMATION_REQUIRED = "confirmation_required"
    NOT_ADMITTED = "not_admitted"


@dataclass(frozen=True, slots=True)
class DirectorRuntimeGovernedTurnPersistenceResult:
    status: DirectorRuntimeGovernedTurnPersistenceStatus
    discussion_admission: DirectorRuntimeDiscussionAdmissionResult | None
    discussion_persistence: DirectorRuntimeDiscussionPersistenceResult | None
    formalization_admission: DirectorRuntimeFormalizationAdmissionResult | None
    formalization_persistence: DirectorRuntimeFormalizationPersistenceResult | None
    no_admission_reason: str | None = None


class DirectorRuntimeGovernedTurnPersistenceService:
    """Compose C2 and C3 under one caller-owned savepoint."""

    def __init__(
        self,
        *,
        session: Session,
        discussion_admission: DirectorRuntimeResultDiscussionAdmissionService | None = None,
        discussion_persistence: DirectorRuntimeResultDiscussionPersistenceService | None = None,
        formalization_admission: DirectorRuntimeResultFormalizationAdmissionService | None = None,
        formalization_persistence: DirectorRuntimeResultFormalizationPersistenceService | None = None,
    ) -> None:
        self._session = session
        self._sessions = ProjectDirectorSessionRepository(session)
        self._messages = ProjectDirectorMessageRepository(session)
        self._events = ProjectDirectorDiscussionEventRepository(session)
        self._workspaces = ProjectDirectorDiscussionWorkspaceRepository(session)
        self._discussion_admission = discussion_admission or DirectorRuntimeResultDiscussionAdmissionService()
        self._discussion_persistence = discussion_persistence or DirectorRuntimeResultDiscussionPersistenceService(session=session)
        self._formalization_admission = formalization_admission or DirectorRuntimeResultFormalizationAdmissionService(session=session)
        self._formalization_persistence = formalization_persistence or DirectorRuntimeResultFormalizationPersistenceService(session=session)

    def persist_session_turn(
        self,
        *,
        session_turn: DirectorRuntimeSessionTurnResult,
        assistant_message_id: UUID,
        occurred_at: datetime,
    ) -> DirectorRuntimeGovernedTurnPersistenceResult:
        """Persist one current candidate without committing the outer transaction."""
        candidate = session_turn.supervision_outcome.candidate
        if candidate is None:
            return DirectorRuntimeGovernedTurnPersistenceResult(
                status=DirectorRuntimeGovernedTurnPersistenceStatus.NOT_ADMITTED,
                discussion_admission=None,
                discussion_persistence=None,
                formalization_admission=None,
                formalization_persistence=None,
                no_admission_reason=(
                    session_turn.supervision_outcome.error.code
                    if session_turn.supervision_outcome.error is not None
                    else "director_runtime_governed_turn_candidate_missing"
                ),
            )
        self._validate_handoff(session_turn)
        user = self._revalidate_authoritative_user(session_turn)
        available_messages = self._all_messages(session_turn.session_id)
        admission = self._discussion_admission.admit(
            request=session_turn.request,
            result=candidate,
            assistant_message_id=assistant_message_id,
            assistant_message_sequence_no=session_turn.assistant_message_sequence_no,
            available_messages=available_messages,
            current_events=self._events.list_by_session_id(session_id=session_turn.session_id),
            current_workspace=self._workspaces.get_by_session_id(session_id=session_turn.session_id),
            start_sequence_no=self._events.get_next_sequence_no(session_id=session_turn.session_id),
            occurred_at=occurred_at,
        )
        assistant = admission.assistant_message_candidate
        if assistant is None:
            raise DirectorRuntimeGovernedTurnPersistenceError(
                "director_runtime_governed_turn_handoff_invalid"
            )
        self._validate_current_assistant_turn(user=user, assistant=assistant)

        with self._session.begin_nested():
            discussion = self._discussion_persistence.persist_admitted_turn(
                admission=admission,
                available_messages=available_messages,
            )
            if discussion.status is DirectorRuntimeDiscussionPersistenceStatus.CONFIRMATION_REQUIRED:
                return DirectorRuntimeGovernedTurnPersistenceResult(
                    status=DirectorRuntimeGovernedTurnPersistenceStatus.CONFIRMATION_REQUIRED,
                    discussion_admission=admission,
                    discussion_persistence=discussion,
                    formalization_admission=None,
                    formalization_persistence=None,
                )
            if discussion.status is DirectorRuntimeDiscussionPersistenceStatus.NOT_ADMITTED:
                return DirectorRuntimeGovernedTurnPersistenceResult(
                    status=DirectorRuntimeGovernedTurnPersistenceStatus.NOT_ADMITTED,
                    discussion_admission=admission,
                    discussion_persistence=discussion,
                    formalization_admission=None,
                    formalization_persistence=None,
                    no_admission_reason=discussion.no_admission_reason,
                )
            formalization_admission = self._formalization_admission.admit(
                request=session_turn.request,
                result=candidate,
                discussion_persistence=discussion,
                occurred_at=occurred_at,
            )
            if formalization_admission.status is DirectorRuntimeFormalizationAdmissionStatus.NOT_ADMITTED:
                return DirectorRuntimeGovernedTurnPersistenceResult(
                    status=DirectorRuntimeGovernedTurnPersistenceStatus.PERSISTED,
                    discussion_admission=admission,
                    discussion_persistence=discussion,
                    formalization_admission=formalization_admission,
                    formalization_persistence=None,
                )
            formalization_persistence = self._formalization_persistence.persist_admitted_candidate(
                admission=formalization_admission,
                request=session_turn.request,
                result=candidate,
                discussion_persistence=discussion,
                occurred_at=occurred_at,
            )
            return DirectorRuntimeGovernedTurnPersistenceResult(
                status=DirectorRuntimeGovernedTurnPersistenceStatus.PERSISTED,
                discussion_admission=admission,
                discussion_persistence=discussion,
                formalization_admission=formalization_admission,
                formalization_persistence=formalization_persistence,
            )

    def _validate_handoff(self, turn: DirectorRuntimeSessionTurnResult) -> None:
        request = turn.request
        outcome = turn.supervision_outcome
        candidate = outcome.candidate
        try:
            correlated = (
                UUID(request.session_id) == turn.session_id
                and UUID(request.project_id) == turn.project_id
                and UUID(request.message_id) == turn.user_message_id
            )
        except (TypeError, ValueError, AttributeError):
            correlated = False
        if (
            not correlated
            or candidate is None
            or request.request_id != outcome.request_id
            or candidate.request_id != request.request_id
            or turn.assistant_message_sequence_no != turn.user_message_sequence_no + 1
            or outcome.attempt_state is not DirectorRuntimeAttemptState.SUCCEEDED
        ):
            raise DirectorRuntimeGovernedTurnPersistenceError(
                "director_runtime_governed_turn_handoff_invalid"
            )

    def _revalidate_authoritative_user(
        self, turn: DirectorRuntimeSessionTurnResult
    ) -> ProjectDirectorMessage:
        session = self._sessions.get_by_id(turn.session_id)
        user = self._messages.get_by_id(turn.user_message_id)
        try:
            request_time = ensure_utc_datetime(
                datetime.fromisoformat(turn.request.current_user_message.occurred_at.replace("Z", "+00:00"))
            )
        except ValueError as exc:
            raise self._current_turn_stale() from exc
        if (
            session is None
            or session.project_id != turn.project_id
            or user is None
            or user.role is not ProjectDirectorMessageRole.USER
            or user.session_id != turn.session_id
            or user.related_project_id != turn.project_id
            or user.sequence_no != turn.user_message_sequence_no
            or user.content != turn.request.current_user_message.content
            or user.created_at != request_time
        ):
            raise self._current_turn_stale()
        return user

    def _validate_current_assistant_turn(
        self, *, user: ProjectDirectorMessage, assistant: ProjectDirectorMessage
    ) -> None:
        existing = self._messages.get_by_id(assistant.id)
        next_sequence = self._messages.get_next_sequence_no(session_id=user.session_id)
        if existing is None:
            if next_sequence != assistant.sequence_no:
                raise self._current_turn_stale()
            return
        if (
            existing.sequence_no != user.sequence_no + 1
            or next_sequence != existing.sequence_no + 1
        ):
            raise self._current_turn_stale()
        # Preserve C2-B's established exact-equivalence conflict contract.
        # This coordinator only owns whether the conversation turn is current.
        if not self._messages_equivalent(existing, assistant):
            return

    def _all_messages(self, session_id: UUID) -> tuple[ProjectDirectorMessage, ...]:
        collected: list[ProjectDirectorMessage] = []
        before: UUID | None = None
        while True:
            page, has_more = self._messages.list_by_session_id(
                session_id=session_id, limit=50, before_message_id=before
            )
            if not page:
                return tuple(collected)
            collected = page + collected
            if not has_more:
                return tuple(collected)
            before = page[0].id

    @staticmethod
    def _messages_equivalent(left: ProjectDirectorMessage, right: ProjectDirectorMessage) -> bool:
        return left.model_dump(mode="python") == right.model_dump(mode="python")

    @staticmethod
    def _current_turn_stale() -> DirectorRuntimeGovernedTurnPersistenceError:
        return DirectorRuntimeGovernedTurnPersistenceError(
            "director_runtime_governed_turn_current_turn_stale"
        )


__all__ = (
    "DirectorRuntimeGovernedTurnPersistenceError",
    "DirectorRuntimeGovernedTurnPersistenceResult",
    "DirectorRuntimeGovernedTurnPersistenceService",
    "DirectorRuntimeGovernedTurnPersistenceStatus",
)
