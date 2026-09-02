"""Bind one Director Runtime attempt to a current Project Director user turn.

This coordinator is deliberately read-only.  It performs authoritative
pre/post-flight checks, delegates request construction to C1, and delegates
runtime lifecycle/admission to the existing supervisor.  It never persists a
reply or creates execution-domain records.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.director_runtime_protocol import (
    DirectorRuntimeRequest,
    normalize_runtime_failure,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.services.director_runtime_request_assembler_service import (
    DirectorRuntimeRequestAssemblerService,
    DirectorRuntimeRequestRuntimeConfigOptions,
)
from app.services.director_runtime_supervisor_service import (
    DirectorRuntimeAttemptState,
    DirectorRuntimeLifecycleState,
    DirectorRuntimeSupervisionOutcome,
    DirectorRuntimeSupervisor,
)


class DirectorRuntimeSessionTurnError(RuntimeError):
    """Fail-closed session-turn binding rejection with a stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class DirectorRuntimeSessionTurnResult:
    """The complete identity and terminal outcome of one governed attempt."""

    project_id: UUID
    session_id: UUID
    user_message_id: UUID
    user_message_sequence_no: int
    assistant_message_sequence_no: int
    request: DirectorRuntimeRequest
    supervision_outcome: DirectorRuntimeSupervisionOutcome
    supervisor_state_after: DirectorRuntimeLifecycleState


class DirectorRuntimeSessionTurnService:
    """Execute a runtime request only for the session's current USER turn."""

    def __init__(
        self,
        *,
        assembler: DirectorRuntimeRequestAssemblerService,
        supervisor: DirectorRuntimeSupervisor,
        session_repository: ProjectDirectorSessionRepository,
        message_repository: ProjectDirectorMessageRepository,
    ) -> None:
        self._assembler = assembler
        self._supervisor = supervisor
        self._session_repository = session_repository
        self._message_repository = message_repository

    async def execute_turn(
        self,
        *,
        session_id: UUID,
        message_id: UUID,
        runtime_config: DirectorRuntimeRequestRuntimeConfigOptions,
        request_id: str,
    ) -> DirectorRuntimeSessionTurnResult:
        """Run one immutable request bound to ``message_id`` as the current turn."""
        if not isinstance(request_id, str) or not request_id.strip():
            raise DirectorRuntimeSessionTurnError(
                "director_runtime_session_turn_request_id_invalid"
            )

        session, user = self._preflight(session_id=session_id, message_id=message_id)
        assistant_sequence_no = user.sequence_no + 1
        request = self._assembler.build_request(
            session_id=session_id,
            message_id=message_id,
            runtime_config=runtime_config,
            request_id=request_id,
        )
        self._validate_request_correlation(
            request=request,
            session_id=session_id,
            project_id=session.project_id,
            message_id=message_id,
            request_id=request_id,
        )

        outcome = await self._supervisor.submit(request=request)
        if (
            outcome.candidate is not None
            and self._message_repository.get_next_sequence_no(session_id=session_id)
            != assistant_sequence_no
        ):
            outcome = self._stale_outcome(request_id=request_id)

        return DirectorRuntimeSessionTurnResult(
            project_id=session.project_id,
            session_id=session_id,
            user_message_id=user.id,
            user_message_sequence_no=user.sequence_no,
            assistant_message_sequence_no=assistant_sequence_no,
            request=request,
            supervision_outcome=outcome,
            supervisor_state_after=self._supervisor.state,
        )

    def _preflight(self, *, session_id: UUID, message_id: UUID):
        session = self._session_repository.get_by_id(session_id)
        if session is None:
            raise DirectorRuntimeSessionTurnError(
                "director_runtime_session_turn_session_not_found"
            )
        if session.project_id is None:
            raise DirectorRuntimeSessionTurnError(
                "director_runtime_session_turn_project_correlation_missing"
            )
        message = self._message_repository.get_by_id(message_id)
        if message is None:
            raise DirectorRuntimeSessionTurnError(
                "director_runtime_session_turn_message_not_found"
            )
        if message.session_id != session.id:
            raise DirectorRuntimeSessionTurnError(
                "director_runtime_session_turn_message_session_mismatch"
            )
        if message.related_project_id != session.project_id:
            raise DirectorRuntimeSessionTurnError(
                "director_runtime_session_turn_message_project_mismatch"
            )
        if message.role != ProjectDirectorMessageRole.USER:
            raise DirectorRuntimeSessionTurnError(
                "director_runtime_session_turn_message_role_invalid"
            )
        if self._message_repository.get_next_sequence_no(session_id=session_id) != message.sequence_no + 1:
            raise DirectorRuntimeSessionTurnError(
                "director_runtime_session_turn_current_message_stale"
            )
        return session, message

    @staticmethod
    def _validate_request_correlation(
        *,
        request: DirectorRuntimeRequest,
        session_id: UUID,
        project_id: UUID,
        message_id: UUID,
        request_id: str,
    ) -> None:
        try:
            correlated = (
                UUID(request.session_id) == session_id
                and UUID(request.project_id) == project_id
                and UUID(request.message_id) == message_id
            )
        except (ValueError, TypeError, AttributeError):
            correlated = False
        if not correlated or request.request_id != request_id:
            raise DirectorRuntimeSessionTurnError(
                "director_runtime_session_turn_request_correlation_mismatch"
            )

    @staticmethod
    def _stale_outcome(*, request_id: str) -> DirectorRuntimeSupervisionOutcome:
        return DirectorRuntimeSupervisionOutcome(
            request_id=request_id,
            attempt_state=DirectorRuntimeAttemptState.REJECTED,
            candidate=None,
            error=normalize_runtime_failure(
                code="director_runtime_session_turn_stale",
                stage="runtime",
                retryable=True,
                safe_message="The conversation advanced while the Director Runtime was running.",
            ),
        )


__all__ = (
    "DirectorRuntimeSessionTurnError",
    "DirectorRuntimeSessionTurnResult",
    "DirectorRuntimeSessionTurnService",
)
