"""Read-only C3-A admission of runtime formalization proposal candidates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.domain.director_runtime_protocol import DirectorRuntimeRequest, DirectorTurnResult
from app.domain.project_director_conversation_intelligence import FormalizationProposal
from app.domain.project_director_discussion import (
    DiscussionActorClaim,
    DiscussionEvent,
    DiscussionEventType,
)
from app.domain.project_director_formalization_proposal import (
    FormalizationProposalStatus,
    ProjectDirectorFormalizationProposal,
)
from app.repositories.project_director_discussion_event_repository import (
    ProjectDirectorDiscussionEventRepository,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.services.director_runtime_result_discussion_persistence_service import (
    DirectorRuntimeDiscussionPersistenceResult,
    DirectorRuntimeDiscussionPersistenceStatus,
)
from app.services.project_director_formalization_proposal_lineage_service import (
    ProjectDirectorFormalizationProposalLineageService,
)


class DirectorRuntimeFormalizationAdmissionError(RuntimeError):
    """Stable fail-closed rejection before a runtime candidate can be persisted."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class DirectorRuntimeFormalizationAdmissionStatus(StrEnum):
    """Caller-visible outcome of C3-A candidate governance."""

    GOVERNED = "governed"
    NOT_ADMITTED = "not_admitted"


@dataclass(frozen=True, slots=True)
class DirectorRuntimeFormalizationAdmissionResult:
    """A read-only governed proposal candidate or an explicit no-admission."""

    status: DirectorRuntimeFormalizationAdmissionStatus
    readiness: str
    parsed_candidate: FormalizationProposal | None
    governed_proposal_candidate: ProjectDirectorFormalizationProposal | None
    source_events: tuple[DiscussionEvent, ...]
    no_admission_reason: str | None = None


class DirectorRuntimeResultFormalizationAdmissionService:
    """Govern one runtime proposal candidate against post-C2 P26 state."""

    def __init__(
        self,
        *,
        session: Session,
        lineage_service: ProjectDirectorFormalizationProposalLineageService | None = None,
    ) -> None:
        self._events = ProjectDirectorDiscussionEventRepository(session)
        self._lineage = lineage_service or ProjectDirectorFormalizationProposalLineageService(
            message_repository=ProjectDirectorMessageRepository(session),
            event_repository=self._events,
        )

    def admit(
        self,
        *,
        request: DirectorRuntimeRequest,
        result: DirectorTurnResult,
        discussion_persistence: DirectorRuntimeDiscussionPersistenceResult,
        occurred_at: datetime,
    ) -> DirectorRuntimeFormalizationAdmissionResult:
        """Return an in-memory proposal only after C2 and canonical lineage pass."""

        readiness = result.formalization.readiness
        if result.request_id != request.request_id:
            raise DirectorRuntimeFormalizationAdmissionError(
                "director_runtime_formalization_admission_request_id_mismatch"
            )
        if result.error is not None:
            return self._not_admitted(readiness, "runtime_error")
        raw_candidate = result.formalization.proposal_candidate
        if raw_candidate is None:
            return self._not_admitted(readiness, "no_formalization_candidate")
        if (
            discussion_persistence.status
            is not DirectorRuntimeDiscussionPersistenceStatus.PERSISTED
            or discussion_persistence.persisted_turn is None
        ):
            return self._not_admitted(readiness, "discussion_turn_not_persisted")

        try:
            parsed = FormalizationProposal.model_validate(raw_candidate)
            session_id = UUID(request.session_id)
            project_id = UUID(request.project_id)
            current_user_message_id = UUID(request.message_id)
        except (TypeError, ValidationError, ValueError) as exc:
            raise DirectorRuntimeFormalizationAdmissionError(
                "director_runtime_formalization_admission_candidate_invalid"
            ) from exc
        semantics = result.turn_semantics
        if (
            semantics.conversation_mode != "formalization_request"
            or not semantics.formal_action_requested
            or semantics.hypothetical_action
        ):
            raise DirectorRuntimeFormalizationAdmissionError(
                "director_runtime_formalization_admission_explicit_request_required"
            )

        persisted_turn = discussion_persistence.persisted_turn
        if not any(
            applied_event.event.event_type
            is DiscussionEventType.FORMALIZATION_REQUESTED
            and applied_event.event.created_by is DiscussionActorClaim.USER_EXPLICIT
            and current_user_message_id in applied_event.event.source_message_ids
            for applied_event in persisted_turn.delta_apply_result.persisted_events
        ):
            raise DirectorRuntimeFormalizationAdmissionError(
                "director_runtime_formalization_admission_explicit_request_required"
            )
        if current_user_message_id not in parsed.source_message_ids:
            raise DirectorRuntimeFormalizationAdmissionError(
                "director_runtime_formalization_admission_current_user_source_required"
            )

        workspace = persisted_turn.delta_apply_result.workspace
        pre_turn_version = self._pre_turn_workspace_version(request)
        if (
            workspace.version_no < 1
            or parsed.workspace_version not in {pre_turn_version, workspace.version_no}
        ):
            raise DirectorRuntimeFormalizationAdmissionError(
                "director_runtime_formalization_admission_workspace_version_invalid"
            )

        proposal = ProjectDirectorFormalizationProposal(
            proposal_id=parsed.proposal_id,
            session_id=session_id,
            project_id=project_id,
            assistant_message_id=persisted_turn.assistant_message.id,
            workspace_version=workspace.version_no,
            target=parsed.target,
            summary=parsed.summary,
            changes=parsed.changes,
            source_message_ids=parsed.source_message_ids,
            source_event_ids=parsed.source_event_ids,
            risk_summary=parsed.risk_summary,
            requires_confirmation=True,
            status=FormalizationProposalStatus.PROPOSED,
            confirmed_plan_version_id=None,
            created_at=occurred_at,
            updated_at=occurred_at,
            confirmed_at=None,
        )
        canonical_source_events = self._lineage.resolve_workspace_source_events(
            workspace=workspace,
            events=self._events.list_by_session_id(session_id=session_id),
        )
        source_events = self._lineage.validate(
            proposal=proposal,
            session_id=session_id,
            workspace=workspace,
            workspace_events=canonical_source_events,
        )
        if any(
            current_user_message_id in event.source_message_ids
            for event in source_events
        ):
            raise DirectorRuntimeFormalizationAdmissionError(
                "director_runtime_formalization_admission_"
                "source_event_turn_boundary_invalid"
            )
        return DirectorRuntimeFormalizationAdmissionResult(
            status=DirectorRuntimeFormalizationAdmissionStatus.GOVERNED,
            readiness=readiness,
            parsed_candidate=parsed,
            governed_proposal_candidate=proposal,
            source_events=source_events,
        )

    @staticmethod
    def _not_admitted(
        readiness: str, reason: str
    ) -> DirectorRuntimeFormalizationAdmissionResult:
        return DirectorRuntimeFormalizationAdmissionResult(
            status=DirectorRuntimeFormalizationAdmissionStatus.NOT_ADMITTED,
            readiness=readiness,
            parsed_candidate=None,
            governed_proposal_candidate=None,
            source_events=(),
            no_admission_reason=reason,
        )

    @staticmethod
    def _pre_turn_workspace_version(request: DirectorRuntimeRequest) -> int:
        snapshot = request.active_discussion_workspace
        if snapshot is None:
            return 0
        try:
            version = snapshot["version_no"]
        except (KeyError, TypeError) as exc:
            raise DirectorRuntimeFormalizationAdmissionError(
                "director_runtime_formalization_admission_workspace_version_invalid"
            ) from exc
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise DirectorRuntimeFormalizationAdmissionError(
                "director_runtime_formalization_admission_workspace_version_invalid"
            )
        return version


__all__ = (
    "DirectorRuntimeFormalizationAdmissionError",
    "DirectorRuntimeFormalizationAdmissionResult",
    "DirectorRuntimeFormalizationAdmissionStatus",
    "DirectorRuntimeResultFormalizationAdmissionService",
)
