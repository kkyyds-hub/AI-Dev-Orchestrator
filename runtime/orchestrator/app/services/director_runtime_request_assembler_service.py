"""Read-only assembly of one governed DirectorRuntimeRequest from P26 state.

This service translates persisted authoritative Project Director state — session,
current user message, discussion workspace, discussion event lineage, and active
formalization — into one frozen ``DirectorRuntimeRequest`` snapshot validated by
the existing protocol boundary.

Boundaries enforced here:

- Read-only: only ``get_*`` / ``list_*`` repository reads are used. This service
  never creates, updates, deletes, commits, flushes, or rolls back anything.
- Fail-closed: any missing or mismatched authoritative reference rejects the
  whole assembly with a safe error code instead of silently dropping data.
- Deterministic: the same database state always yields the same snapshot fields
  (event ordering follows the persisted discussion sequence numbers).
- No secrets: the assembler never reads provider configuration or credentials.
  Runtime secrets remain the responsibility of the B2 child-environment bridge.
- No runtime invocation: this service never calls the supervisor, transport,
  Node runtime, Pi, or any provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.domain._base import ensure_utc_datetime
from app.domain.director_runtime_protocol import (
    DirectorRuntimeRequest,
    validate_director_runtime_request,
)
from app.domain.project_director_discussion import DiscussionEvent, DiscussionWorkspace
from app.domain.project_director_formalization_proposal import (
    ProjectDirectorFormalizationProposal,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
)
from app.domain.project_director_plan_version import ProjectDirectorPlanVersion
from app.domain.project_director_session import (
    ProjectDirectorSession,
    ProjectDirectorSessionStatus,
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
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.services.project_director_discussion_workspace_reducer_service import (
    ProjectDirectorDiscussionWorkspaceReducerService,
)


class DirectorRuntimeRequestAssemblerError(RuntimeError):
    """Fail-closed assembly rejection with a safe, stable error code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class DirectorRuntimeProjectCorrelationBlocker(DirectorRuntimeRequestAssemblerError):
    """Session without a project correlation cannot name a request project_id.

    The frozen DirectorRuntimeRequest requires a non-blank project_id. When the
    authoritative session has no project correlation this service refuses to
    invent one; the Director decides the contract path forward.
    """

    def __init__(self) -> None:
        super().__init__(
            "director_runtime_request_assembler_project_correlation_blocked"
        )


@dataclass(frozen=True, slots=True)
class DirectorRuntimeRequestRuntimeConfigOptions:
    """Explicit non-secret runtime configuration for one assembled request.

    Provider credentials are never part of this object; they stay inside the
    B2 governed child-environment bridge.
    """

    model_id: str
    provider_profile_id: str
    timeout_ms: float
    max_tool_rounds: int

    def __post_init__(self) -> None:
        if not isinstance(self.model_id, str) or not self.model_id.strip():
            raise DirectorRuntimeRequestAssemblerError(
                "director_runtime_request_assembler_runtime_config_invalid"
            )
        if not isinstance(self.provider_profile_id, str) or not self.provider_profile_id.strip():
            raise DirectorRuntimeRequestAssemblerError(
                "director_runtime_request_assembler_runtime_config_invalid"
            )
        if (
            not isinstance(self.timeout_ms, (int, float))
            or isinstance(self.timeout_ms, bool)
            or not float(self.timeout_ms) > 0
        ):
            raise DirectorRuntimeRequestAssemblerError(
                "director_runtime_request_assembler_runtime_config_invalid"
            )
        if (
            not isinstance(self.max_tool_rounds, int)
            or isinstance(self.max_tool_rounds, bool)
            or self.max_tool_rounds < 0
        ):
            raise DirectorRuntimeRequestAssemblerError(
                "director_runtime_request_assembler_runtime_config_invalid"
            )


_GOVERNANCE_BOUNDARIES: Final[dict[str, Any]] = {
    "authoritative_write": False,
    "director_may_modify_code": False,
    "formalization_requires_explicit_request": True,
    "confirmation_is_separate": True,
    "execution_boundary": "no_task_run_agent_session_before_execution",
}

_PLAN_SNAPSHOT_FIELDS: Final[tuple[str, ...]] = (
    "id",
    "session_id",
    "project_id",
    "version_no",
    "status",
    "plan_summary",
    "formalization_proposal_id",
    "formalization_target",
    "formalization_workspace_version",
    "formalization_source_message_ids",
    "formalization_source_event_ids",
    "confirmed_at",
    "created_at",
    "updated_at",
)


class DirectorRuntimeRequestAssemblerService:
    """Assemble one governed DirectorRuntimeRequest from authoritative state.

    The service consumes existing repositories in strictly read-only fashion and
    returns a snapshot validated by ``validate_director_runtime_request``. It
    owns no transaction commit and performs no persistence.
    """

    def __init__(
        self,
        *,
        db_session: Session,
        session_repository: ProjectDirectorSessionRepository | None = None,
        message_repository: ProjectDirectorMessageRepository | None = None,
        workspace_repository: ProjectDirectorDiscussionWorkspaceRepository | None = None,
        event_repository: ProjectDirectorDiscussionEventRepository | None = None,
        proposal_repository: ProjectDirectorFormalizationProposalRepository | None = None,
        plan_version_repository: ProjectDirectorPlanVersionRepository | None = None,
    ) -> None:
        self._session_repository = session_repository or ProjectDirectorSessionRepository(
            db_session
        )
        self._message_repository = message_repository or ProjectDirectorMessageRepository(
            db_session
        )
        self._workspace_repository = (
            workspace_repository
            or ProjectDirectorDiscussionWorkspaceRepository(db_session)
        )
        self._event_repository = (
            event_repository or ProjectDirectorDiscussionEventRepository(db_session)
        )
        self._proposal_repository = (
            proposal_repository
            or ProjectDirectorFormalizationProposalRepository(db_session)
        )
        self._plan_version_repository = (
            plan_version_repository or ProjectDirectorPlanVersionRepository(db_session)
        )

    def build_request(
        self,
        *,
        session_id: UUID,
        message_id: UUID,
        runtime_config: DirectorRuntimeRequestRuntimeConfigOptions,
        request_id: str | None = None,
    ) -> DirectorRuntimeRequest:
        """Build one fail-closed request snapshot for an already-persisted message."""

        resolved_request_id = self._resolve_request_id(request_id)

        session = self._session_repository.get_by_id(session_id)
        if session is None:
            raise DirectorRuntimeRequestAssemblerError(
                "director_runtime_request_assembler_session_not_found"
            )
        if session.project_id is None:
            raise DirectorRuntimeProjectCorrelationBlocker()
        project_id = session.project_id

        message = self._validate_current_user_message(
            message_id=message_id, session_id=session_id
        )

        workspace = self._workspace_repository.get_by_session_id(session_id=session_id)
        if workspace is not None:
            self._validate_workspace_correlation(workspace, session=session)

        events = self._select_and_validate_events(
            session_id=session_id,
            project_id=project_id,
            workspace=workspace,
        )

        proposal, plan_version = self._resolve_active_formalization(
            session_id=session_id, project_id=project_id
        )

        payload = {
            "schema_version": "p26-big-director-runtime/v1",
            "request_id": resolved_request_id,
            "project_id": str(project_id),
            "session_id": str(session_id),
            "message_id": str(message.id),
            "current_user_message": {
                "content": message.content,
                "occurred_at": self._canonical_timestamp(message.created_at),
                "actor_claim": "user",
            },
            "authoritative_facts": self._authoritative_facts(session),
            "active_discussion_workspace": (
                workspace.model_dump(mode="json") if workspace is not None else None
            ),
            "relevant_discussion_events": [
                event.model_dump(mode="json") for event in events
            ],
            "active_formalization": {
                "proposal": (
                    proposal.model_dump(mode="json") if proposal is not None else None
                ),
                "plan_version": (
                    self._plan_version_snapshot(plan_version)
                    if plan_version is not None
                    else None
                ),
            },
            "governance_boundaries": dict(_GOVERNANCE_BOUNDARIES),
            "available_skills": [],
            "available_tools": [],
            "permission_context": {},
            "runtime_config": {
                "model_id": runtime_config.model_id,
                "provider_profile_id": runtime_config.provider_profile_id,
                "timeout_ms": runtime_config.timeout_ms,
                "max_tool_rounds": runtime_config.max_tool_rounds,
            },
        }
        return validate_director_runtime_request(payload)

    def _resolve_request_id(self, request_id: str | None) -> str:
        if request_id is None:
            return str(uuid4())
        if not isinstance(request_id, str) or not request_id.strip():
            raise DirectorRuntimeRequestAssemblerError(
                "director_runtime_request_assembler_request_id_invalid"
            )
        return request_id

    def _validate_current_user_message(
        self, *, message_id: UUID, session_id: UUID
    ) -> ProjectDirectorMessage:
        message = self._message_repository.get_by_id(message_id)
        if message is None:
            raise DirectorRuntimeRequestAssemblerError(
                "director_runtime_request_assembler_message_not_found"
            )
        if message.session_id != session_id:
            raise DirectorRuntimeRequestAssemblerError(
                "director_runtime_request_assembler_message_session_mismatch"
            )
        if message.role != ProjectDirectorMessageRole.USER:
            raise DirectorRuntimeRequestAssemblerError(
                "director_runtime_request_assembler_message_role_invalid"
            )
        return message

    @staticmethod
    def _validate_workspace_correlation(
        workspace: DiscussionWorkspace, *, session: ProjectDirectorSession
    ) -> None:
        if workspace.session_id != session.id:
            raise DirectorRuntimeRequestAssemblerError(
                "director_runtime_request_assembler_workspace_session_mismatch"
            )
        if workspace.project_id != session.project_id:
            raise DirectorRuntimeRequestAssemblerError(
                "director_runtime_request_assembler_workspace_project_mismatch"
            )

    def _select_and_validate_events(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        workspace: DiscussionWorkspace | None,
    ) -> list[DiscussionEvent]:
        """Return the workspace's applied event lineage in deterministic order.

        Without a persisted workspace there is no workspace-derived lineage to
        snapshot, so the event list is empty. With a workspace, the applied
        lineage is every persisted event up to the workspace's
        ``last_event_sequence_no`` — exactly the prefix the P26 reducer consumed
        when deriving that workspace version.
        """

        if workspace is None:
            return []

        events = self._event_repository.list_by_session_id(session_id=session_id)
        selected = [
            event
            for event in events
            if event.sequence_no <= workspace.last_event_sequence_no
        ]
        try:
            resolution = (
                ProjectDirectorDiscussionWorkspaceReducerService().resolve_events(
                    session_id=session_id,
                    project_id=project_id,
                    events=selected,
                )
            )
        except ValueError as exc:
            reducer_code = str(exc)
            reducer_prefix = "discussion_event_stream_"
            assembler_code = (
                "director_runtime_request_assembler_event_"
                + reducer_code.removeprefix(reducer_prefix)
                if reducer_code.startswith(reducer_prefix)
                else "director_runtime_request_assembler_event_history_invalid"
            )
            raise DirectorRuntimeRequestAssemblerError(assembler_code) from exc

        for event in resolution.ordered_events:
            self._validate_event_source_messages(event, session_id=session_id)
        return list(resolution.ordered_events)

    def _validate_event_source_messages(
        self,
        event: DiscussionEvent,
        *,
        session_id: UUID,
    ) -> None:
        for source_message_id in event.source_message_ids:
            source_message = self._message_repository.get_by_id(source_message_id)
            if source_message is None:
                raise DirectorRuntimeRequestAssemblerError(
                    "director_runtime_request_assembler_event_source_message_not_found"
                )
            if source_message.session_id != session_id:
                raise DirectorRuntimeRequestAssemblerError(
                    "director_runtime_request_assembler_event_source_message_session_mismatch"
                )

    def _resolve_active_formalization(
        self, *, session_id: UUID, project_id: UUID
    ) -> tuple[
        ProjectDirectorFormalizationProposal | None, ProjectDirectorPlanVersion | None
    ]:
        proposal = self._proposal_repository.get_active_for_session(
            session_id=session_id
        )
        if proposal is None:
            return None, None
        if proposal.session_id != session_id or proposal.project_id != project_id:
            raise DirectorRuntimeRequestAssemblerError(
                "director_runtime_request_assembler_proposal_project_mismatch"
            )
        for source_message_id in proposal.source_message_ids:
            source_message = self._message_repository.get_by_id(source_message_id)
            if source_message is None or source_message.session_id != session_id:
                raise DirectorRuntimeRequestAssemblerError(
                    "director_runtime_request_assembler_proposal_source_message_invalid"
                )

        plan_version = None
        if proposal.confirmed_plan_version_id is not None:
            plan_version = self._plan_version_repository.get_by_id(
                proposal.confirmed_plan_version_id
            )
        if plan_version is None:
            plan_version = self._plan_version_repository.get_by_formalization_proposal_id(
                proposal.proposal_id
            )
        if plan_version is not None:
            if plan_version.session_id != session_id:
                raise DirectorRuntimeRequestAssemblerError(
                    "director_runtime_request_assembler_plan_session_mismatch"
                )
            if plan_version.project_id != project_id:
                raise DirectorRuntimeRequestAssemblerError(
                    "director_runtime_request_assembler_plan_project_mismatch"
                )
        return proposal, plan_version

    @staticmethod
    def _authoritative_facts(session: ProjectDirectorSession) -> dict[str, Any]:
        """Return only facts already proven authoritative by confirmation.

        Unconfirmed sessions (draft/clarifying/ready_to_confirm) contribute no
        facts: their goal and constraints are still model-assisted drafts, not
        user decisions.
        """

        if session.status != ProjectDirectorSessionStatus.CONFIRMED:
            return {}
        facts: dict[str, Any] = {
            "session_status": str(session.status.value),
            "goal": session.goal_text,
        }
        if session.project_id is not None:
            facts["project_id"] = str(session.project_id)
        if session.goal_summary:
            facts["goal_summary"] = session.goal_summary
        if session.constraints:
            facts["constraints"] = session.constraints
        if session.confirmed_at is not None:
            facts["confirmed_at"] = (
                DirectorRuntimeRequestAssemblerService._canonical_timestamp(
                    session.confirmed_at
                )
            )
        return facts

    @staticmethod
    def _plan_version_snapshot(
        plan_version: ProjectDirectorPlanVersion,
    ) -> dict[str, Any]:
        dumped = plan_version.model_dump(mode="json")
        return {field: dumped[field] for field in _PLAN_SNAPSHOT_FIELDS}

    @staticmethod
    def _canonical_timestamp(value: object) -> str:
        normalized = ensure_utc_datetime(value)  # type: ignore[arg-type]
        if normalized is None:
            raise DirectorRuntimeRequestAssemblerError(
                "director_runtime_request_assembler_timestamp_invalid"
            )
        return normalized.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


__all__ = (
    "DirectorRuntimeProjectCorrelationBlocker",
    "DirectorRuntimeRequestAssemblerError",
    "DirectorRuntimeRequestAssemblerService",
    "DirectorRuntimeRequestRuntimeConfigOptions",
)
