"""C3-B persistence-time governance for runtime formalization proposals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.director_runtime_protocol import DirectorRuntimeRequest, DirectorTurnResult
from app.domain.project_director_discussion import (
    DiscussionActorClaim,
    DiscussionEvent,
    DiscussionEventType,
)
from app.domain.project_director_formalization_proposal import (
    ProjectDirectorFormalizationProposal,
)
from app.domain.project_director_message import ProjectDirectorMessageRole
from app.repositories.project_director_discussion_event_repository import (
    ProjectDirectorDiscussionEventRepository,
)
from app.repositories.project_director_discussion_workspace_repository import (
    ProjectDirectorDiscussionWorkspaceRepository,
)
from app.repositories.project_director_formalization_proposal_repository import (
    ProjectDirectorFormalizationProposalRepository,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.services.director_runtime_result_discussion_persistence_service import (
    DirectorRuntimeDiscussionPersistenceResult,
)
from app.services.director_runtime_result_formalization_admission_service import (
    DirectorRuntimeFormalizationAdmissionResult,
    DirectorRuntimeFormalizationAdmissionStatus,
    DirectorRuntimeResultFormalizationAdmissionService,
)
from app.services.project_director_formalization_proposal_lineage_service import (
    ProjectDirectorFormalizationProposalLineageService,
)


class DirectorRuntimeFormalizationPersistenceError(RuntimeError):
    """Stable fail-closed error before C3-B can leave a proposal write."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class DirectorRuntimeFormalizationPersistenceStatus(StrEnum):
    """Caller-visible result of persistence-time formalization governance."""

    PERSISTED = "persisted"
    REPLAYED = "replayed"
    NOT_ADMITTED = "not_admitted"


@dataclass(frozen=True, slots=True)
class DirectorRuntimeFormalizationPersistenceResult:
    """One durable proposed proposal, an equivalent replay, or an explicit no-write."""

    status: DirectorRuntimeFormalizationPersistenceStatus
    stored_proposal: ProjectDirectorFormalizationProposal | None
    no_admission_reason: str | None = None


class DirectorRuntimeResultFormalizationPersistenceService:
    """Persist only a freshly re-admitted C3-A candidate in the caller transaction."""

    def __init__(
        self,
        *,
        session: Session,
        admission_service: DirectorRuntimeResultFormalizationAdmissionService | None = None,
        workspace_repository: ProjectDirectorDiscussionWorkspaceRepository | None = None,
        event_repository: ProjectDirectorDiscussionEventRepository | None = None,
        lineage_service: ProjectDirectorFormalizationProposalLineageService | None = None,
        proposal_repository: ProjectDirectorFormalizationProposalRepository | None = None,
    ) -> None:
        self._session = session
        self._events = event_repository or ProjectDirectorDiscussionEventRepository(session)
        self._admission = admission_service or DirectorRuntimeResultFormalizationAdmissionService(
            session=session
        )
        self._workspaces = workspace_repository or ProjectDirectorDiscussionWorkspaceRepository(
            session
        )
        self._messages = ProjectDirectorMessageRepository(session)
        self._lineage = lineage_service or ProjectDirectorFormalizationProposalLineageService(
            message_repository=self._messages,
            event_repository=self._events,
        )
        self._proposals = proposal_repository or ProjectDirectorFormalizationProposalRepository(
            session
        )

    def persist_admitted_candidate(
        self,
        *,
        admission: DirectorRuntimeFormalizationAdmissionResult,
        request: DirectorRuntimeRequest,
        result: DirectorTurnResult,
        discussion_persistence: DirectorRuntimeDiscussionPersistenceResult,
        occurred_at: datetime,
    ) -> DirectorRuntimeFormalizationPersistenceResult:
        """Re-admit and revalidate latest state before one proposal repository write."""

        fresh_admission = self._admission.admit(
            request=request,
            result=result,
            discussion_persistence=discussion_persistence,
            occurred_at=occurred_at,
        )
        if admission != fresh_admission:
            raise DirectorRuntimeFormalizationPersistenceError(
                "director_runtime_formalization_persistence_admission_mismatch"
            )
        if fresh_admission.status is DirectorRuntimeFormalizationAdmissionStatus.NOT_ADMITTED:
            return DirectorRuntimeFormalizationPersistenceResult(
                status=DirectorRuntimeFormalizationPersistenceStatus.NOT_ADMITTED,
                stored_proposal=None,
                no_admission_reason=fresh_admission.no_admission_reason,
            )
        proposal = fresh_admission.governed_proposal_candidate
        if proposal is None or fresh_admission.parsed_candidate is None:
            raise DirectorRuntimeFormalizationPersistenceError(
                "director_runtime_formalization_persistence_admission_mismatch"
            )

        self._validate_current_conversation_turn(
            request=request,
            discussion_persistence=discussion_persistence,
        )
        self._validate_current_formalization_request_evidence(
            request=request,
            discussion_persistence=discussion_persistence,
        )
        workspace = self._current_workspace(request=request, proposal=proposal)
        session_id = UUID(request.session_id)
        workspace_events = self._lineage.resolve_workspace_source_events(
            workspace=workspace,
            events=self._events.list_by_session_id(session_id=session_id),
        )
        self._lineage.validate(
            proposal=proposal,
            session_id=session_id,
            workspace=workspace,
            workspace_events=workspace_events,
        )

        existed_before = self._proposals.get_by_id(proposal.proposal_id) is not None
        with self._session.begin_nested():
            stored = self._proposals.create_no_commit(proposal)
            self._proposals.mark_superseded_no_commit(
                session_id=proposal.session_id,
                workspace_version=proposal.workspace_version,
                target=proposal.target,
                except_proposal_id=proposal.proposal_id,
            )
        return DirectorRuntimeFormalizationPersistenceResult(
            status=(
                DirectorRuntimeFormalizationPersistenceStatus.REPLAYED
                if existed_before
                else DirectorRuntimeFormalizationPersistenceStatus.PERSISTED
            ),
            stored_proposal=stored,
        )

    def _validate_current_conversation_turn(
        self,
        *,
        request: DirectorRuntimeRequest,
        discussion_persistence: DirectorRuntimeDiscussionPersistenceResult,
    ) -> None:
        persisted_turn = discussion_persistence.persisted_turn
        try:
            current_user_message_id = UUID(request.message_id)
            request_session_id = UUID(request.session_id)
            request_project_id = UUID(request.project_id)
            request_occurred_at = datetime.fromisoformat(
                request.current_user_message.occurred_at.replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise self._current_turn_stale() from exc
        if persisted_turn is None:
            raise self._current_turn_stale()

        user = self._messages.get_by_id(current_user_message_id)
        supplied_assistant = persisted_turn.assistant_message
        assistant = self._messages.get_by_id(supplied_assistant.id)
        if (
            user is None
            or assistant is None
            or user.role is not ProjectDirectorMessageRole.USER
            or assistant.role is not ProjectDirectorMessageRole.ASSISTANT
            or user.session_id != request_session_id
            or assistant.session_id != request_session_id
            or user.related_project_id != request_project_id
            or assistant.related_project_id != request_project_id
            or user.content != request.current_user_message.content
            or user.created_at != request_occurred_at
            or not self._messages_equivalent(assistant, supplied_assistant)
            or assistant.sequence_no != user.sequence_no + 1
            or self._messages.get_next_sequence_no(session_id=request_session_id)
            != assistant.sequence_no + 1
        ):
            raise self._current_turn_stale()

    @staticmethod
    def _messages_equivalent(left, right) -> bool:
        return left.model_dump(mode="python") == right.model_dump(mode="python")

    @staticmethod
    def _current_turn_stale() -> DirectorRuntimeFormalizationPersistenceError:
        return DirectorRuntimeFormalizationPersistenceError(
            "director_runtime_formalization_persistence_current_turn_stale"
        )

    def _validate_current_formalization_request_evidence(
        self,
        *,
        request: DirectorRuntimeRequest,
        discussion_persistence: DirectorRuntimeDiscussionPersistenceResult,
    ) -> None:
        persisted_turn = discussion_persistence.persisted_turn
        try:
            current_user_message_id = UUID(request.message_id)
        except ValueError as exc:
            raise DirectorRuntimeFormalizationPersistenceError(
                "director_runtime_formalization_persistence_"
                "explicit_request_evidence_stale"
            ) from exc
        if persisted_turn is None:
            raise DirectorRuntimeFormalizationPersistenceError(
                "director_runtime_formalization_persistence_"
                "explicit_request_evidence_stale"
            )
        for applied_event in persisted_turn.delta_apply_result.persisted_events:
            supplied_event = applied_event.event
            if (
                supplied_event.event_type is not DiscussionEventType.FORMALIZATION_REQUESTED
                or supplied_event.created_by is not DiscussionActorClaim.USER_EXPLICIT
                or current_user_message_id not in supplied_event.source_message_ids
            ):
                continue
            authoritative_event = self._events.get_by_id(event_id=supplied_event.id)
            if authoritative_event is None:
                continue
            if not self._events_equivalent(authoritative_event, supplied_event):
                raise DirectorRuntimeFormalizationPersistenceError(
                    "director_runtime_formalization_persistence_"
                    "explicit_request_evidence_stale"
                )
            return
        raise DirectorRuntimeFormalizationPersistenceError(
            "director_runtime_formalization_persistence_"
            "explicit_request_evidence_stale"
        )

    @staticmethod
    def _events_equivalent(left: DiscussionEvent, right: DiscussionEvent) -> bool:
        return left.model_dump(mode="python") == right.model_dump(mode="python")

    def _current_workspace(
        self,
        *,
        request: DirectorRuntimeRequest,
        proposal: ProjectDirectorFormalizationProposal,
    ):
        workspace = self._workspaces.get_by_session_id(session_id=proposal.session_id)
        try:
            request_project_id = UUID(request.project_id)
            request_session_id = UUID(request.session_id)
        except ValueError as exc:
            raise DirectorRuntimeFormalizationPersistenceError(
                "director_runtime_formalization_persistence_workspace_stale"
            ) from exc
        if (
            workspace is None
            or workspace.session_id != request_session_id
            or workspace.project_id != request_project_id
            or workspace.project_id != proposal.project_id
            or workspace.version_no != proposal.workspace_version
        ):
            raise DirectorRuntimeFormalizationPersistenceError(
                "director_runtime_formalization_persistence_workspace_stale"
            )
        return workspace


__all__ = (
    "DirectorRuntimeFormalizationPersistenceError",
    "DirectorRuntimeFormalizationPersistenceResult",
    "DirectorRuntimeFormalizationPersistenceStatus",
    "DirectorRuntimeResultFormalizationPersistenceService",
)
