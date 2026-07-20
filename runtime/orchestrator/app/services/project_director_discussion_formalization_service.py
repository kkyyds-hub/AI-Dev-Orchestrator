"""Explicit, review-only formalization of a governed discussion workspace."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.project_director_conversation_intelligence import FormalizationTarget
from app.domain.project_director_discussion import DiscussionEvent, DiscussionWorkspace
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


@dataclass(frozen=True, slots=True)
class DiscussionFormalizationResult:
    """The review-only plan draft created from a confirmed discussion state."""

    plan_version: ProjectDirectorPlanVersion
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
        plan_version_repository: ProjectDirectorPlanVersionRepository,
        plan_service: ProjectDirectorPlanService,
    ) -> None:
        self._session_repository = session_repository
        self._workspace_repository = discussion_workspace_repository
        self._event_repository = discussion_event_repository
        self._message_repository = message_repository
        self._plan_version_repository = plan_version_repository
        self._plan_service = plan_service

    def formalize_discussion(
        self,
        *,
        session_id: UUID,
        workspace_version: int,
        target: FormalizationTarget,
        user_confirmed: bool,
    ) -> DiscussionFormalizationResult:
        """Create or read back the plan draft for one confirmed workspace version."""

        shared_session = self._require_shared_session()
        try:
            if not user_confirmed:
                raise ValueError(
                    "project_director_formalization_user_confirmation_required"
                )
            if target != FormalizationTarget.PLAN_REVISION:
                raise ValueError("project_director_formalization_target_invalid")

            session_obj = self._session_repository.get_by_id(session_id)
            if session_obj is None:
                raise ValueError(f"Session {session_id} not found")
            if session_obj.status != ProjectDirectorSessionStatus.CONFIRMED:
                raise ValueError(
                    "project_director_formalization_session_not_confirmed"
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

            source_event_ids = self._collect_workspace_event_ids(workspace)
            if not source_event_ids:
                raise ValueError("project_director_formalization_workspace_not_ready")
            source_events = self._load_source_events(
                source_event_ids=source_event_ids,
                session_id=session_id,
                project_id=workspace.project_id,
                last_event_sequence_no=workspace.last_event_sequence_no,
            )
            source_message_ids = self._collect_source_message_ids(
                source_events,
                session_id=session_id,
            )

            existing = self._plan_version_repository.get_by_formalization_source(
                session_id=session_id,
                target=target,
                workspace_version=workspace_version,
            )
            if existing is not None:
                self._ensure_existing_provenance(
                    existing,
                    source_event_ids=source_event_ids,
                    source_message_ids=source_message_ids,
                )
                return self._result(
                    existing,
                    workspace_version=workspace_version,
                    target=target,
                    source_event_ids=source_event_ids,
                    source_message_ids=source_message_ids,
                    idempotent_replay=True,
                )

            revision_notes = self._revision_notes(
                target=target,
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
                workspace_version=workspace_version,
                target=target,
                source_event_ids=source_event_ids,
                source_message_ids=source_message_ids,
                plan_draft=plan_draft,
            )
            persisted_plan_version = self._plan_version_repository.create_no_commit(
                plan_version
            )
            shared_session.commit()
            return self._result(
                persisted_plan_version,
                workspace_version=workspace_version,
                target=target,
                source_event_ids=source_event_ids,
                source_message_ids=source_message_ids,
                idempotent_replay=False,
            )
        except IntegrityError as exc:
            shared_session.rollback()
            existing = self._plan_version_repository.get_by_formalization_source(
                session_id=session_id,
                target=target,
                workspace_version=workspace_version,
            )
            if existing is not None:
                self._ensure_existing_provenance(
                    existing,
                    source_event_ids=source_event_ids,
                    source_message_ids=source_message_ids,
                )
                return self._result(
                    existing,
                    workspace_version=workspace_version,
                    target=target,
                    source_event_ids=source_event_ids,
                    source_message_ids=source_message_ids,
                    idempotent_replay=True,
                )
            raise ValueError(
                "project_director_formalization_idempotency_conflict"
            ) from exc
        except BaseException:
            shared_session.rollback()
            raise

    def _require_shared_session(self) -> Session:
        repositories = (
            self._session_repository,
            self._workspace_repository,
            self._event_repository,
            self._message_repository,
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

    @staticmethod
    def _collect_workspace_event_ids(workspace: DiscussionWorkspace) -> tuple[UUID, ...]:
        candidates = [
            *workspace.active_option_ids,
            workspace.preferred_option_id,
            *workspace.active_constraint_ids,
            *workspace.open_question_ids,
            *workspace.temporary_conclusion_ids,
            *workspace.confirmed_decision_ids,
            workspace.latest_user_correction_event_id,
        ]
        return tuple(
            event_id
            for index, event_id in enumerate(candidates)
            if event_id is not None and event_id not in candidates[:index]
        )

    def _load_source_events(
        self,
        *,
        source_event_ids: tuple[UUID, ...],
        session_id: UUID,
        project_id: UUID | None,
        last_event_sequence_no: int,
    ) -> tuple[DiscussionEvent, ...]:
        events: list[DiscussionEvent] = []
        for event_id in source_event_ids:
            event = self._event_repository.get_by_id(event_id=event_id)
            if event is None:
                raise ValueError("project_director_formalization_event_not_found")
            if event.session_id != session_id:
                raise ValueError("project_director_formalization_event_session_mismatch")
            if event.project_id != project_id:
                raise ValueError("project_director_formalization_event_project_mismatch")
            if event.sequence_no > last_event_sequence_no:
                raise ValueError("project_director_formalization_event_sequence_invalid")
            events.append(event)
        return tuple(events)

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

    @staticmethod
    def _revision_notes(
        *,
        target: FormalizationTarget,
        workspace: DiscussionWorkspace,
        events: tuple[DiscussionEvent, ...],
    ) -> str:
        payload = {
            "formalization_target": target.value,
            "workspace_version": workspace.version_no,
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
        workspace_version: int,
        target: FormalizationTarget,
        source_event_ids: tuple[UUID, ...],
        source_message_ids: tuple[UUID, ...],
        plan_draft: PlanGenerationResult,
    ) -> ProjectDirectorPlanVersion:
        provenance_suffix = (
            f"; formalization_target={target.value}; "
            f"formalization_workspace_version={workspace_version}"
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
            formalization_target=target,
            formalization_workspace_version=workspace_version,
            formalization_source_message_ids=list(source_message_ids),
            formalization_source_event_ids=list(source_event_ids),
            confirmed_at=None,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _ensure_existing_provenance(
        existing: ProjectDirectorPlanVersion,
        *,
        source_event_ids: tuple[UUID, ...],
        source_message_ids: tuple[UUID, ...],
    ) -> None:
        if (
            tuple(existing.formalization_source_event_ids) != source_event_ids
            or tuple(existing.formalization_source_message_ids) != source_message_ids
        ):
            raise ValueError("project_director_formalization_idempotency_conflict")

    @staticmethod
    def _result(
        plan_version: ProjectDirectorPlanVersion,
        *,
        workspace_version: int,
        target: FormalizationTarget,
        source_event_ids: tuple[UUID, ...],
        source_message_ids: tuple[UUID, ...],
        idempotent_replay: bool,
    ) -> DiscussionFormalizationResult:
        return DiscussionFormalizationResult(
            plan_version=plan_version,
            workspace_version=workspace_version,
            target=target,
            source_message_ids=source_message_ids,
            source_event_ids=source_event_ids,
            idempotent_replay=idempotent_replay,
        )
