"""Persist only C2-A-admitted runtime discussion turns through P26."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.orm import Session

from app.domain.project_director_message import ProjectDirectorMessage
from app.services.director_runtime_result_discussion_admission_service import (
    DirectorRuntimeDiscussionAdmissionResult,
)
from app.services.project_director_discussion_delta_gate_service import (
    DiscussionDeltaGateStatus,
)
from app.services.project_director_discussion_turn_persistence_service import (
    PersistedDiscussionTurnResult,
    ProjectDirectorDiscussionTurnPersistenceService,
)


class DirectorRuntimeDiscussionPersistenceError(RuntimeError):
    """Stable fail-closed error before a bridge call can write discussion state."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class DirectorRuntimeDiscussionPersistenceStatus(StrEnum):
    """Caller-visible result of handling one admitted runtime discussion turn."""

    PERSISTED = "persisted"
    CONFIRMATION_REQUIRED = "confirmation_required"
    NOT_ADMITTED = "not_admitted"


@dataclass(frozen=True, slots=True)
class DirectorRuntimeDiscussionPersistenceResult:
    """A no-write result or the existing P26 coordinator result."""

    status: DirectorRuntimeDiscussionPersistenceStatus
    persisted_turn: PersistedDiscussionTurnResult | None
    no_admission_reason: str | None = None


class DirectorRuntimeResultDiscussionPersistenceService:
    """Bridge a C2-A admission into the existing caller-owned P26 transaction."""

    def __init__(
        self,
        *,
        session: Session,
        turn_persistence: ProjectDirectorDiscussionTurnPersistenceService | None = None,
    ) -> None:
        self._turn_persistence = turn_persistence or (
            ProjectDirectorDiscussionTurnPersistenceService(session=session)
        )

    def persist_admitted_turn(
        self,
        *,
        admission: DirectorRuntimeDiscussionAdmissionResult,
        available_messages: Sequence[ProjectDirectorMessage],
    ) -> DirectorRuntimeDiscussionPersistenceResult:
        """Flush a prepared admission without committing the caller transaction."""

        self._validate_admission_type(admission)
        if admission.no_admission_reason is not None:
            self._validate_no_admission(admission)
            return DirectorRuntimeDiscussionPersistenceResult(
                status=DirectorRuntimeDiscussionPersistenceStatus.NOT_ADMITTED,
                persisted_turn=None,
                no_admission_reason=admission.no_admission_reason,
            )

        if (
            admission.delta is None
            or admission.assistant_message_candidate is None
            or admission.governed_delta is None
        ):
            self._raise_admission_invalid()

        if admission.governed_delta.status is DiscussionDeltaGateStatus.REQUIRES_CONFIRMATION:
            return DirectorRuntimeDiscussionPersistenceResult(
                status=DirectorRuntimeDiscussionPersistenceStatus.CONFIRMATION_REQUIRED,
                persisted_turn=None,
            )
        if admission.governed_delta.status is not DiscussionDeltaGateStatus.PREPARED:
            self._raise_admission_invalid()

        assistant_message = admission.assistant_message_candidate
        persisted_turn = self._turn_persistence.persist_assistant_turn(
            session_id=assistant_message.session_id,
            project_id=assistant_message.related_project_id,
            assistant_message=assistant_message,
            available_messages=available_messages,
            delta=admission.delta,
            occurred_at=assistant_message.created_at,
        )
        return DirectorRuntimeDiscussionPersistenceResult(
            status=DirectorRuntimeDiscussionPersistenceStatus.PERSISTED,
            persisted_turn=persisted_turn,
        )

    @staticmethod
    def _validate_admission_type(admission: DirectorRuntimeDiscussionAdmissionResult) -> None:
        if not isinstance(admission, DirectorRuntimeDiscussionAdmissionResult):
            DirectorRuntimeResultDiscussionPersistenceService._raise_admission_invalid()

    @staticmethod
    def _validate_no_admission(
        admission: DirectorRuntimeDiscussionAdmissionResult,
    ) -> None:
        if (
            admission.no_admission_reason not in {"no_delta_candidate", "runtime_error"}
            or admission.delta is not None
            or admission.assistant_message_candidate is not None
            or admission.governed_delta is not None
        ):
            DirectorRuntimeResultDiscussionPersistenceService._raise_admission_invalid()

    @staticmethod
    def _raise_admission_invalid() -> None:
        raise DirectorRuntimeDiscussionPersistenceError(
            "director_runtime_discussion_persistence_admission_invalid"
        )


__all__ = (
    "DirectorRuntimeDiscussionPersistenceError",
    "DirectorRuntimeDiscussionPersistenceResult",
    "DirectorRuntimeDiscussionPersistenceStatus",
    "DirectorRuntimeResultDiscussionPersistenceService",
)
