"""Explicit, review-only formalization of a governed discussion workspace."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.project_director_conversation_intelligence import FormalizationTarget
from app.domain.project_director_formalization_proposal import (
    FormalizationProposalStatus,
    ProjectDirectorFormalizationProposal,
)
from app.domain.project_director_discussion import DiscussionEvent, DiscussionWorkspace
from app.domain.project_director_discussion import (
    DiscussionEventStatus,
    DiscussionEventType,
    DiscussionStatus,
)
from app.domain.project_director_plan_version import (
    PlanVersionStatus,
    ProjectDirectorPlanVersion,
)
from app.domain.project_director_session import ProjectDirectorSessionStatus
from app.repositories.project_director_discussion_event_repository import (
    ProjectDirectorDiscussionEventRepository,
)
from app.repositories.project_director_discussion_workspace_repository import (
    ProjectDirectorDiscussionWorkspaceRepository,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_formalization_proposal_repository import (
    ProjectDirectorFormalizationProposalRepository,
)
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.services.project_director_plan_service import (
    _DEFAULT_FORBIDDEN_ACTIONS,
    PlanGenerationResult,
    ProjectDirectorPlanService,
)
from app.services.project_director_discussion_workspace_reducer_service import (
    ProjectDirectorDiscussionWorkspaceReducerService,
)
from app.services.project_director_formalization_proposal_lineage_service import (
    ProjectDirectorFormalizationProposalLineageService,
)


_OPTION_EVENT_TYPES = frozenset(
    {
        DiscussionEventType.OPTION_ADDED,
        DiscussionEventType.OPTION_UPDATED,
        DiscussionEventType.OPTION_PREFERRED,
        DiscussionEventType.OPTION_REJECTED,
    }
)
_CONSTRAINT_EVENT_TYPES = frozenset(
    {
        DiscussionEventType.CONSTRAINT_ADDED,
        DiscussionEventType.CONSTRAINT_UPDATED,
        DiscussionEventType.CONSTRAINT_SUPERSEDED,
    }
)
_STATUS_EVENT_TYPES = frozenset(
    {
        DiscussionEventType.OPTION_PREFERRED,
        DiscussionEventType.DECISION_CONFIRMED,
        DiscussionEventType.FORMALIZATION_REQUESTED,
        DiscussionEventType.FORMALIZATION_CANCELLED,
    }
)


@dataclass(frozen=True, slots=True)
class DiscussionFormalizationResult:
    """The review-only plan draft created from a confirmed discussion state."""

    plan_version: ProjectDirectorPlanVersion
    proposal_id: UUID
    workspace_version: int
    target: FormalizationTarget
    source_message_ids: tuple[UUID, ...]
    source_event_ids: tuple[UUID, ...]
    idempotent_replay: bool


class ProjectDirectorDiscussionFormalizationService:
    """Create one pending plan draft from an explicit workspace confirmation."""

    def __init__(
        self,
        *,
        session_repository: ProjectDirectorSessionRepository,
        discussion_workspace_repository: ProjectDirectorDiscussionWorkspaceRepository,
        discussion_event_repository: ProjectDirectorDiscussionEventRepository,
        message_repository: ProjectDirectorMessageRepository,
        formalization_proposal_repository: ProjectDirectorFormalizationProposalRepository,
        plan_version_repository: ProjectDirectorPlanVersionRepository,
        plan_service: ProjectDirectorPlanService,
    ) -> None:
        self._session_repository = session_repository
        self._workspace_repository = discussion_workspace_repository
        self._event_repository = discussion_event_repository
        self._message_repository = message_repository
        self._proposal_repository = formalization_proposal_repository
        self._plan_version_repository = plan_version_repository
        self._plan_service = plan_service
        self._proposal_lineage_service = (
            ProjectDirectorFormalizationProposalLineageService(
                message_repository=message_repository,
                event_repository=discussion_event_repository,
            )
        )

    def formalize_discussion(
        self,
        *,
        session_id: UUID,
        proposal_id: UUID,
        workspace_version: int,
        target: FormalizationTarget,
        user_confirmed: bool,
    ) -> DiscussionFormalizationResult:
        """Create or read back the draft for one persisted exact proposal."""

        shared_session = self._require_shared_session()
        try:
            if not user_confirmed:
                raise ValueError(
                    "project_director_formalization_user_confirmation_required"
                )
            if target != FormalizationTarget.PLAN_REVISION:
                raise ValueError("project_director_formalization_target_invalid")

            proposal = self._proposal_repository.get_by_id(proposal_id)
            if proposal is None:
                raise ValueError("project_director_formalization_proposal_not_found")
            if proposal.session_id != session_id:
                raise ValueError(
                    "project_director_formalization_proposal_session_mismatch"
                )

            session_obj = self._session_repository.get_by_id(session_id)
            if session_obj is None:
                raise ValueError(f"Session {session_id} not found")
            if session_obj.status != ProjectDirectorSessionStatus.CONFIRMED:
                raise ValueError(
                    "project_director_formalization_session_not_confirmed"
                )
            if proposal.project_id != session_obj.project_id:
                raise ValueError(
                    "project_director_formalization_proposal_project_mismatch"
                )
            if proposal.workspace_version != workspace_version:
                raise ValueError(
                    "project_director_formalization_proposal_workspace_mismatch"
                )
            if proposal.target != target:
                raise ValueError(
                    "project_director_formalization_proposal_target_mismatch"
                )

            workspace = self._workspace_repository.get_by_session_id(
                session_id=session_id
            )
            if workspace is None:
                raise ValueError("project_director_formalization_workspace_not_found")
            if workspace.version_no != workspace_version:
                raise ValueError(
                    "project_director_formalization_workspace_version_mismatch"
                )
            if workspace.version_no < 1:
                raise ValueError("project_director_formalization_workspace_not_ready")

            if proposal.status == FormalizationProposalStatus.CONFIRMED:
                return self._confirmed_replay_result(
                    proposal=proposal,
                    session_id=session_id,
                    workspace=workspace,
                )
            if proposal.status != FormalizationProposalStatus.PROPOSED:
                raise ValueError("project_director_formalization_proposal_not_active")

            workspace_events = self._resolve_workspace_source_events(
                workspace=workspace,
            )
            source_events = self._validate_proposal_lineage(
                proposal=proposal,
                session_id=session_id,
                workspace=workspace,
                workspace_events=workspace_events,
            )
            source_event_ids = tuple(proposal.source_event_ids)
            source_message_ids = tuple(proposal.source_message_ids)

            existing = self._plan_version_repository.get_by_formalization_proposal_id(
                proposal_id
            )
            if existing is not None:
                self._ensure_existing_proposal_provenance(
                    existing,
                    proposal_id=proposal_id,
                    source_event_ids=source_event_ids,
                    source_message_ids=source_message_ids,
                )
                return self._result(
                    existing,
                    proposal_id=proposal_id,
                    workspace_version=workspace_version,
                    target=target,
                    source_event_ids=source_event_ids,
                    source_message_ids=source_message_ids,
                    idempotent_replay=True,
                )

            revision_notes = self._revision_notes(
                proposal=proposal,
                workspace=workspace,
                events=source_events,
            )
            plan_draft = self._plan_service.generate_plan_draft(
                session_id=session_id,
                revision_notes=revision_notes,
            )
            plan_version = self._new_plan_version(
                session_id=session_id,
                project_id=session_obj.project_id,
                proposal=proposal,
                source_event_ids=source_event_ids,
                source_message_ids=source_message_ids,
                plan_draft=plan_draft,
            )
        except BaseException:
            shared_session.rollback()
            raise

        try:
            persisted_plan_version = self._plan_version_repository.create_no_commit(
                plan_version
            )
            self._proposal_repository.mark_confirmed_no_commit(
                proposal_id=proposal_id,
                confirmed_plan_version_id=persisted_plan_version.id,
            )
            shared_session.commit()
        except IntegrityError:
            shared_session.rollback()
            persisted_proposal = self._proposal_repository.get_by_id(proposal_id)
            existing = self._plan_version_repository.get_by_formalization_proposal_id(
                proposal_id
            )
            if (
                persisted_proposal is None
                or persisted_proposal.status != FormalizationProposalStatus.CONFIRMED
                or existing is None
            ):
                raise ValueError(
                    "project_director_formalization_proposal_already_confirmed_conflict"
                )
            self._ensure_existing_proposal_provenance(
                existing,
                proposal_id=proposal_id,
                source_event_ids=source_event_ids,
                source_message_ids=source_message_ids,
            )
            return self._result(
                existing,
                proposal_id=proposal_id,
                workspace_version=workspace_version,
                target=target,
                source_event_ids=source_event_ids,
                source_message_ids=source_message_ids,
                idempotent_replay=True,
            )
        except BaseException:
            shared_session.rollback()
            raise

        return self._result(
            persisted_plan_version,
            proposal_id=proposal_id,
            workspace_version=workspace_version,
            target=target,
            source_event_ids=source_event_ids,
            source_message_ids=source_message_ids,
            idempotent_replay=False,
        )

    def _require_shared_session(self) -> Session:
        repositories = (
            self._session_repository,
            self._workspace_repository,
            self._event_repository,
            self._message_repository,
            self._proposal_repository,
            self._plan_version_repository,
            getattr(self._plan_service, "_session_repo", None),
            getattr(self._plan_service, "_plan_repo", None),
        )
        sessions = [getattr(repository, "_session", None) for repository in repositories]
        if any(not isinstance(session, Session) for session in sessions):
            raise ValueError("project_director_formalization_shared_session_unavailable")
        shared_session = sessions[0]
        if any(session is not shared_session for session in sessions[1:]):
            raise ValueError("project_director_formalization_shared_session_mismatch")
        return shared_session

    def _resolve_workspace_source_events(
        self, *, workspace: DiscussionWorkspace
    ) -> tuple[DiscussionEvent, ...]:
        """Resolve provenance from the immutable event history behind one workspace."""
        events = tuple(
            self._event_repository.list_by_session_id(session_id=workspace.session_id)
        )
        return self._proposal_lineage_service.resolve_workspace_source_events(
            workspace=workspace,
            events=events,
        )

    def _collect_source_message_ids(
        self,
        events: tuple[DiscussionEvent, ...],
        *,
        session_id: UUID,
    ) -> tuple[UUID, ...]:
        message_ids: list[UUID] = []
        for event in events:
            for message_id in event.source_message_ids:
                if message_id in message_ids:
                    continue
                message = self._message_repository.get_by_id(message_id)
                if message is None:
                    raise ValueError(
                        "project_director_formalization_source_message_not_found"
                    )
                if message.session_id != session_id:
                    raise ValueError(
                        "project_director_formalization_source_message_session_mismatch"
                    )
                message_ids.append(message_id)
        if not message_ids:
            raise ValueError("project_director_formalization_source_messages_missing")
        return tuple(message_ids)

    def _validate_proposal_lineage(
        self,
        *,
        proposal: ProjectDirectorFormalizationProposal,
        session_id: UUID,
        workspace: DiscussionWorkspace,
        workspace_events: tuple[DiscussionEvent, ...],
    ) -> tuple[DiscussionEvent, ...]:
        """Validate that a persisted Proposal still names visible prior evidence."""
        return self._proposal_lineage_service.validate(
            proposal=proposal,
            session_id=session_id,
            workspace=workspace,
            workspace_events=workspace_events,
        )

    def _confirmed_replay_result(
        self,
        *,
        proposal: ProjectDirectorFormalizationProposal,
        session_id: UUID,
        workspace: DiscussionWorkspace,
    ) -> DiscussionFormalizationResult:
        if proposal.confirmed_plan_version_id is None:
            raise ValueError(
                "project_director_formalization_proposal_already_confirmed_conflict"
            )
        existing = self._plan_version_repository.get_by_id(
            proposal.confirmed_plan_version_id
        )
        if existing is None or existing.session_id != session_id:
            raise ValueError(
                "project_director_formalization_proposal_already_confirmed_conflict"
            )
        workspace_events = self._resolve_workspace_source_events(workspace=workspace)
        self._validate_proposal_lineage(
            proposal=proposal,
            session_id=session_id,
            workspace=workspace,
            workspace_events=workspace_events,
        )
        source_event_ids = tuple(proposal.source_event_ids)
        source_message_ids = tuple(proposal.source_message_ids)
        self._ensure_existing_proposal_provenance(
            existing,
            proposal_id=proposal.proposal_id,
            source_event_ids=source_event_ids,
            source_message_ids=source_message_ids,
        )
        return self._result(
            existing,
            proposal_id=proposal.proposal_id,
            workspace_version=proposal.workspace_version,
            target=proposal.target,
            source_event_ids=source_event_ids,
            source_message_ids=source_message_ids,
            idempotent_replay=True,
        )

    @staticmethod
    def _revision_notes(
        *,
        proposal: ProjectDirectorFormalizationProposal,
        workspace: DiscussionWorkspace,
        events: tuple[DiscussionEvent, ...],
    ) -> str:
        payload = {
            "formalization_proposal_id": proposal.proposal_id,
            "formalization_target": proposal.target.value,
            "workspace_version": proposal.workspace_version,
            "proposal_summary": proposal.summary,
            "proposal_risk_summary": proposal.risk_summary,
            "proposal_changes": [
                change.model_dump(mode="json") for change in proposal.changes
            ],
            "proposal_source_message_ids": proposal.source_message_ids,
            "proposal_source_event_ids": proposal.source_event_ids,
            "workspace_topic": workspace.topic,
            "workspace_discussion_status": workspace.discussion_status.value,
            "events": [
                {
                    "sequence_no": event.sequence_no,
                    "event_type": event.event_type.value,
                    "subject_key": event.subject_key,
                    "content": event.content,
                    "created_by": event.created_by.value,
                    "status": event.status.value,
                    "source_message_ids": event.source_message_ids,
                }
                for event in events
            ],
        }
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        )

    def _new_plan_version(
        self,
        *,
        session_id: UUID,
        project_id: UUID | None,
        proposal: ProjectDirectorFormalizationProposal,
        source_event_ids: tuple[UUID, ...],
        source_message_ids: tuple[UUID, ...],
        plan_draft: PlanGenerationResult,
    ) -> ProjectDirectorPlanVersion:
        provenance_suffix = (
            f"; formalization_proposal_id={proposal.proposal_id}; "
            f"formalization_target={proposal.target.value}; "
            f"formalization_workspace_version={proposal.workspace_version}"
        )
        source_detail = (
            plan_draft.source_detail[: 1000 - len(provenance_suffix)]
            + provenance_suffix
        )
        now = datetime.now(timezone.utc)
        return ProjectDirectorPlanVersion(
            id=uuid4(),
            session_id=session_id,
            project_id=project_id,
            version_no=self._plan_version_repository.get_next_version_no(session_id),
            status=PlanVersionStatus.PENDING_CONFIRMATION,
            plan_summary=plan_draft.plan_summary,
            phases=plan_draft.phases,
            proposed_tasks=plan_draft.proposed_tasks,
            acceptance_criteria=plan_draft.acceptance_criteria,
            risks=plan_draft.risks,
            project_scope=plan_draft.project_scope,
            agent_team_suggestions=plan_draft.agent_team_suggestions,
            skill_binding_suggestions=plan_draft.skill_binding_suggestions,
            verification_mechanisms=plan_draft.verification_mechanisms,
            repository_binding_suggestions=plan_draft.repository_binding_suggestions,
            deliverable_boundaries=plan_draft.deliverable_boundaries,
            complexity_assessment=plan_draft.complexity_assessment,
            source=plan_draft.source,
            source_detail=source_detail,
            forbidden_actions=list(_DEFAULT_FORBIDDEN_ACTIONS),
            formalization_proposal_id=proposal.proposal_id,
            formalization_target=proposal.target,
            formalization_workspace_version=proposal.workspace_version,
            formalization_source_message_ids=list(source_message_ids),
            formalization_source_event_ids=list(source_event_ids),
            confirmed_at=None,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _ensure_existing_proposal_provenance(
        existing: ProjectDirectorPlanVersion,
        *,
        proposal_id: UUID,
        source_event_ids: tuple[UUID, ...],
        source_message_ids: tuple[UUID, ...],
    ) -> None:
        if (
            existing.formalization_proposal_id != proposal_id
            or tuple(existing.formalization_source_event_ids) != source_event_ids
            or tuple(existing.formalization_source_message_ids) != source_message_ids
        ):
            raise ValueError("project_director_formalization_idempotency_conflict")

    @staticmethod
    def _result(
        plan_version: ProjectDirectorPlanVersion,
        *,
        proposal_id: UUID,
        workspace_version: int,
        target: FormalizationTarget,
        source_event_ids: tuple[UUID, ...],
        source_message_ids: tuple[UUID, ...],
        idempotent_replay: bool,
    ) -> DiscussionFormalizationResult:
        return DiscussionFormalizationResult(
            plan_version=plan_version,
            proposal_id=proposal_id,
            workspace_version=workspace_version,
            target=target,
            source_message_ids=source_message_ids,
            source_event_ids=source_event_ids,
            idempotent_replay=idempotent_replay,
        )
