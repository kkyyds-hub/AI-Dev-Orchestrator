"""C3-B persistence-time governance for runtime formalization proposals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.director_runtime_protocol import DirectorRuntimeRequest, DirectorTurnResult
from app.domain.project_director_formalization_proposal import (
    ProjectDirectorFormalizationProposal,
)
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
        self._lineage = lineage_service or ProjectDirectorFormalizationProposalLineageService(
            message_repository=ProjectDirectorMessageRepository(session),
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
