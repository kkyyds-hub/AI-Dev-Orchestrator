"""Pure C2-A admission of untrusted runtime delta candidates into the P26 Gate."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ValidationError

from app.domain.director_runtime_protocol import DirectorRuntimeRequest, DirectorTurnResult
from app.domain.project_director_discussion import (
    DiscussionActorClaim,
    DiscussionDelta,
    DiscussionEvent,
    DiscussionWorkspace,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.services.project_director_discussion_delta_gate_service import (
    GovernedDiscussionDeltaResult,
    ProjectDirectorDiscussionDeltaGateService,
)


class DirectorRuntimeDiscussionAdmissionError(RuntimeError):
    """Stable fail-closed rejection before a runtime candidate reaches the Gate."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class DirectorRuntimeDiscussionAdmissionResult:
    """Read-only handoff from a runtime result to existing P26 governance."""

    delta: DiscussionDelta | None
    assistant_message_candidate: ProjectDirectorMessage | None
    governed_delta: GovernedDiscussionDeltaResult | None
    no_admission_reason: Literal["no_delta_candidate", "runtime_error"] | None


class DirectorRuntimeResultDiscussionAdmissionService:
    """Adapt an already-validated runtime result without persisting anything."""

    def __init__(
        self,
        *,
        delta_gate: ProjectDirectorDiscussionDeltaGateService | None = None,
    ) -> None:
        self._delta_gate = delta_gate or ProjectDirectorDiscussionDeltaGateService()

    def admit(
        self,
        *,
        request: DirectorRuntimeRequest,
        result: DirectorTurnResult,
        assistant_message_id: UUID,
        assistant_message_sequence_no: int,
        available_messages: Sequence[ProjectDirectorMessage],
        current_events: Sequence[DiscussionEvent],
        current_workspace: DiscussionWorkspace | None,
        start_sequence_no: int,
        occurred_at: datetime,
    ) -> DirectorRuntimeDiscussionAdmissionResult:
        """Validate one candidate shape, then delegate governance to the P26 Gate."""

        if result.request_id != request.request_id:
            raise DirectorRuntimeDiscussionAdmissionError(
                "director_runtime_discussion_admission_request_id_mismatch"
            )
        if result.error is not None:
            return DirectorRuntimeDiscussionAdmissionResult(
                delta=None,
                assistant_message_candidate=None,
                governed_delta=None,
                no_admission_reason="runtime_error",
            )
        if result.discussion_delta_candidate is None:
            return DirectorRuntimeDiscussionAdmissionResult(
                delta=None,
                assistant_message_candidate=None,
                governed_delta=None,
                no_admission_reason="no_delta_candidate",
            )

        try:
            delta = DiscussionDelta.model_validate(result.discussion_delta_candidate)
        except (TypeError, ValidationError, ValueError) as exc:
            raise DirectorRuntimeDiscussionAdmissionError(
                "director_runtime_discussion_admission_delta_invalid"
            ) from exc
        if any(
            operation.actor_claim
            in {
                DiscussionActorClaim.SYSTEM_FACT,
                DiscussionActorClaim.FORMAL_PROJECT_FACT,
            }
            for operation in delta.operations
        ):
            raise DirectorRuntimeDiscussionAdmissionError(
                "director_runtime_discussion_admission_authority_claim_invalid"
            )

        try:
            session_id = UUID(request.session_id)
            project_id = UUID(request.project_id)
        except (TypeError, ValueError) as exc:
            raise DirectorRuntimeDiscussionAdmissionError(
                "director_runtime_discussion_admission_request_correlation_invalid"
            ) from exc

        try:
            assistant_message = ProjectDirectorMessage(
                id=assistant_message_id,
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=result.response_text,
                sequence_no=assistant_message_sequence_no,
                related_project_id=project_id,
                source=ProjectDirectorMessageSource.AI,
                source_detail="director_runtime",
                created_at=occurred_at,
            )
        except (TypeError, ValidationError, ValueError) as exc:
            raise DirectorRuntimeDiscussionAdmissionError(
                "director_runtime_discussion_admission_assistant_message_invalid"
            ) from exc

        governed_delta = self._delta_gate.evaluate_delta(
            session_id=session_id,
            project_id=project_id,
            assistant_message=assistant_message,
            available_messages=available_messages,
            current_events=current_events,
            current_workspace=current_workspace,
            delta=delta,
            start_sequence_no=start_sequence_no,
            occurred_at=occurred_at,
        )
        return DirectorRuntimeDiscussionAdmissionResult(
            delta=delta,
            assistant_message_candidate=assistant_message,
            governed_delta=governed_delta,
            no_admission_reason=None,
        )


__all__ = (
    "DirectorRuntimeDiscussionAdmissionError",
    "DirectorRuntimeDiscussionAdmissionResult",
    "DirectorRuntimeResultDiscussionAdmissionService",
)
