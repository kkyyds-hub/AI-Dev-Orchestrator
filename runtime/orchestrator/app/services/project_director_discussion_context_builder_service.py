"""Read-only deterministic assembly for Project Director discussion context."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import re
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.project_director_conversation_intelligence import TurnInterpretation
from app.domain.project_director_discussion import (
    DiscussionEvent,
    DiscussionEventStatus,
    DiscussionEventType,
    DiscussionWorkspace,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
)
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
from app.repositories.project_director_task_creation_repository import (
    ProjectDirectorTaskCreationRecordRepository,
)
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.services.project_director_context_builder_service import (
    ProjectDirectorContextBuilderService,
)
from app.services.project_director_discussion_context_planner_service import (
    DiscussionContextPlan,
    DiscussionContextSection,
    FormalFactContextScope,
    ProjectDirectorDiscussionContextPlannerService,
)
from app.services.project_director_discussion_workspace_reducer_service import (
    DiscussionEventResolution,
    ProjectDirectorDiscussionWorkspaceReducerService,
)


@dataclass(frozen=True, slots=True)
class PinnedDiscussionFormalFacts:
    """Scope-trimmed formal facts for a discussion turn."""

    scope: FormalFactContextScope
    session_id: UUID
    project_id: UUID | None

    goal_text: str
    constraints: str
    session_status: str
    goal_summary: str
    confirmed_at: str | None

    latest_plan_version: dict[str, object] | None
    task_creation: dict[str, object] | None
    project_snapshot: dict[str, object] | None
    task_snapshot: dict[str, object] | None


@dataclass(frozen=True, slots=True)
class ResolvedDiscussionContextEvent:
    """One event with its context-read status after supersession resolution."""

    event: DiscussionEvent
    resolved_status: DiscussionEventStatus


@dataclass(frozen=True, slots=True)
class ActiveDiscussionWorkspaceContext:
    """A stored workspace with the effective events needed to read it."""

    workspace: DiscussionWorkspace
    active_events: tuple[DiscussionEvent, ...]


@dataclass(frozen=True, slots=True)
class DiscussionContextAssembly:
    """Read-only, deterministic context data for one persisted user turn."""

    plan: DiscussionContextPlan
    pinned_formal_facts: PinnedDiscussionFormalFacts

    recent_raw_messages: tuple[ProjectDirectorMessage, ...]
    active_workspace: ActiveDiscussionWorkspaceContext | None
    relevant_events: tuple[ResolvedDiscussionContextEvent, ...]

    current_user_message: ProjectDirectorMessage
    silent_governance_boundaries: tuple[str, ...]


_UUID_TEXT_PATTERN = re.compile(
    r"(?<![0-9a-fA-F])[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?![0-9a-fA-F])"
)

_OPTION_CONTENT_TYPES = (
    DiscussionEventType.OPTION_ADDED,
    DiscussionEventType.OPTION_UPDATED,
)

_CONSTRAINT_TYPES = (
    DiscussionEventType.CONSTRAINT_ADDED,
    DiscussionEventType.CONSTRAINT_UPDATED,
    DiscussionEventType.CONSTRAINT_SUPERSEDED,
)


class ProjectDirectorDiscussionContextBuilderService:
    """Build a deterministic read-only discussion context assembly."""

    def __init__(
        self,
        session: Session,
        *,
        planner: ProjectDirectorDiscussionContextPlannerService | None = None,
        formal_context_builder: ProjectDirectorContextBuilderService | None = None,
        session_repository: ProjectDirectorSessionRepository | None = None,
        message_repository: ProjectDirectorMessageRepository | None = None,
        event_repository: ProjectDirectorDiscussionEventRepository | None = None,
        workspace_repository: ProjectDirectorDiscussionWorkspaceRepository | None = None,
        reducer: ProjectDirectorDiscussionWorkspaceReducerService | None = None,
    ) -> None:
        self._planner = planner or ProjectDirectorDiscussionContextPlannerService()
        self._session_repository = session_repository or ProjectDirectorSessionRepository(
            session
        )
        self._message_repository = message_repository or ProjectDirectorMessageRepository(
            session
        )
        self._event_repository = event_repository or ProjectDirectorDiscussionEventRepository(
            session
        )
        self._workspace_repository = (
            workspace_repository
            or ProjectDirectorDiscussionWorkspaceRepository(session)
        )
        self._reducer = reducer or ProjectDirectorDiscussionWorkspaceReducerService()
        self._formal_context_builder = (
            formal_context_builder
            or ProjectDirectorContextBuilderService(
                session_repository=self._session_repository,
                message_repository=self._message_repository,
                plan_version_repository=ProjectDirectorPlanVersionRepository(session),
                task_creation_repository=ProjectDirectorTaskCreationRecordRepository(
                    session
                ),
                project_repository=ProjectRepository(session),
                task_repository=TaskRepository(session),
            )
        )

    def build_context(
        self,
        *,
        session_id: UUID,
        project_id: UUID | None,
        current_user_message: ProjectDirectorMessage,
        interpretation: TurnInterpretation,
    ) -> DiscussionContextAssembly:
        """Assemble only the sections the real E1 plan selects."""

        self._validate_current_user_message(
            session_id=session_id,
            project_id=project_id,
            current_user_message=current_user_message,
        )
        workspace = self._workspace_repository.get_by_session_id(session_id=session_id)
        plan = self._planner.plan_context(
            interpretation=interpretation, workspace=workspace
        )
        formal_context = self._formal_context_builder.build_context(session_id=session_id)

        requires_event_stream = (
            DiscussionContextSection.ACTIVE_DISCUSSION_WORKSPACE
            in plan.selected_sections
            or DiscussionContextSection.RELEVANT_DISCUSSION_EVENTS
            in plan.selected_sections
        )
        resolution: DiscussionEventResolution | None = None
        all_events: tuple[DiscussionEvent, ...] = ()
        if requires_event_stream:
            all_events = tuple(
                self._event_repository.list_by_session_id(session_id=session_id)
            )
            resolution = self._validate_workspace_against_events(
                session_id=session_id,
                project_id=project_id,
                workspace=workspace,
                all_events=all_events,
            )

        recent_messages, _ = self._message_repository.list_by_session_id(
            session_id=session_id,
            limit=plan.recent_message_limit,
            before_message_id=current_user_message.id,
        )
        active_workspace = (
            self._build_active_workspace_context(
                workspace=self._require_workspace(workspace),
                resolution=self._require_resolution(resolution),
            )
            if DiscussionContextSection.ACTIVE_DISCUSSION_WORKSPACE
            in plan.selected_sections
            else None
        )
        relevant_events = (
            self._build_relevant_events(
                plan=plan, resolution=self._require_resolution(resolution)
            )
            if DiscussionContextSection.RELEVANT_DISCUSSION_EVENTS
            in plan.selected_sections
            else ()
        )

        return DiscussionContextAssembly(
            plan=plan,
            pinned_formal_facts=self._build_pinned_formal_facts(
                scope=plan.formal_fact_scope, formal_context=formal_context
            ),
            recent_raw_messages=tuple(recent_messages),
            active_workspace=active_workspace,
            relevant_events=relevant_events,
            current_user_message=current_user_message,
            silent_governance_boundaries=tuple(formal_context.safety_boundary),
        )

    def _validate_current_user_message(
        self,
        *,
        session_id: UUID,
        project_id: UUID | None,
        current_user_message: ProjectDirectorMessage,
    ) -> None:
        if current_user_message.role != ProjectDirectorMessageRole.USER:
            raise ValueError("discussion_context_current_message_role_invalid")
        if current_user_message.session_id != session_id:
            raise ValueError("discussion_context_current_message_session_mismatch")
        if current_user_message.related_project_id != project_id:
            raise ValueError("discussion_context_current_message_project_mismatch")

        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            raise ValueError("discussion_context_session_not_found")
        if session_obj.project_id != project_id:
            raise ValueError("discussion_context_session_project_mismatch")

        persisted_message = self._message_repository.get_by_id(current_user_message.id)
        if persisted_message is None:
            raise ValueError("discussion_context_current_message_not_found")
        if persisted_message.model_dump(mode="python") != current_user_message.model_dump(
            mode="python"
        ):
            raise ValueError("discussion_context_current_message_conflict")

    def _validate_workspace_against_events(
        self,
        *,
        session_id: UUID,
        project_id: UUID | None,
        workspace: DiscussionWorkspace | None,
        all_events: tuple[DiscussionEvent, ...],
    ) -> DiscussionEventResolution:
        if all_events and workspace is None:
            raise ValueError("discussion_context_workspace_missing_for_events")
        if workspace is None:
            return self._reducer.resolve_events(
                session_id=session_id, project_id=project_id, events=all_events
            )
        if workspace.session_id != session_id:
            raise ValueError("discussion_context_workspace_session_mismatch")
        if workspace.project_id != project_id:
            raise ValueError("discussion_context_workspace_project_mismatch")

        resolution = self._reducer.resolve_events(
            session_id=session_id, project_id=project_id, events=all_events
        )
        expected_cursor = (
            resolution.ordered_events[-1].sequence_no
            if resolution.ordered_events
            else 0
        )
        if workspace.last_event_sequence_no != expected_cursor:
            raise ValueError("discussion_context_workspace_event_cursor_mismatch")
        _, changed = self._reducer.reduce_workspace(
            workspace=workspace, events=all_events
        )
        if changed:
            raise ValueError("discussion_context_workspace_projection_mismatch")
        return resolution

    @staticmethod
    def _require_workspace(
        workspace: DiscussionWorkspace | None,
    ) -> DiscussionWorkspace:
        if workspace is None:
            raise ValueError("discussion_context_workspace_missing_for_events")
        return workspace

    @staticmethod
    def _require_resolution(
        resolution: DiscussionEventResolution | None,
    ) -> DiscussionEventResolution:
        if resolution is None:
            raise RuntimeError("discussion context event resolution was not built")
        return resolution

    @staticmethod
    def _build_pinned_formal_facts(
        *,
        scope: FormalFactContextScope,
        formal_context: object,
    ) -> PinnedDiscussionFormalFacts:
        latest_plan_version = None
        task_creation = None
        project_snapshot = None
        task_snapshot = None
        if scope == FormalFactContextScope.CORE_AND_PLAN:
            latest_plan_version = deepcopy(formal_context.latest_plan_version)
        elif scope == FormalFactContextScope.CORE_AND_STATUS:
            latest_plan_version = deepcopy(formal_context.latest_plan_version)
            task_creation = deepcopy(formal_context.task_creation)
            project_snapshot = deepcopy(formal_context.project_snapshot)
            task_snapshot = deepcopy(formal_context.task_snapshot)

        return PinnedDiscussionFormalFacts(
            scope=scope,
            session_id=formal_context.session_id,
            project_id=formal_context.project_id,
            goal_text=formal_context.goal_text,
            constraints=formal_context.constraints,
            session_status=formal_context.session_status,
            goal_summary=formal_context.goal_summary,
            confirmed_at=formal_context.confirmed_at,
            latest_plan_version=latest_plan_version,
            task_creation=task_creation,
            project_snapshot=project_snapshot,
            task_snapshot=task_snapshot,
        )

    def _build_active_workspace_context(
        self,
        *,
        workspace: DiscussionWorkspace,
        resolution: DiscussionEventResolution,
    ) -> ActiveDiscussionWorkspaceContext:
        effective_by_id = {event.id: event for event in resolution.effective_events}
        selected_events: list[DiscussionEvent] = []

        if workspace.topic:
            topic_events = [
                event
                for event in resolution.effective_events
                if event.event_type == DiscussionEventType.TOPIC_SET
            ]
            if not topic_events or topic_events[-1].content != workspace.topic:
                raise ValueError("discussion_context_workspace_topic_mismatch")
            selected_events.append(topic_events[-1])

        for option_id in workspace.active_option_ids:
            option_events = [
                event
                for event in resolution.effective_events
                if event.event_type in _OPTION_CONTENT_TYPES
                and self._event_option_id(event) == option_id
            ]
            if not option_events:
                raise ValueError("discussion_context_workspace_option_missing")
            selected_events.append(option_events[-1])

        if workspace.preferred_option_id is not None:
            preferred = [
                event
                for event in resolution.effective_events
                if event.event_type == DiscussionEventType.OPTION_PREFERRED
                and self._event_option_id(event) == workspace.preferred_option_id
            ]
            if not preferred:
                raise ValueError("discussion_context_workspace_reference_invalid")
            selected_events.append(preferred[-1])

        self._append_required_effective_events(
            selected_events=selected_events,
            effective_by_id=effective_by_id,
            event_ids=workspace.active_constraint_ids,
            allowed_types=_CONSTRAINT_TYPES,
        )
        self._append_required_effective_events(
            selected_events=selected_events,
            effective_by_id=effective_by_id,
            event_ids=workspace.open_question_ids,
            allowed_types=(DiscussionEventType.OPEN_QUESTION_ADDED,),
        )
        self._append_required_effective_events(
            selected_events=selected_events,
            effective_by_id=effective_by_id,
            event_ids=workspace.temporary_conclusion_ids,
            allowed_types=(DiscussionEventType.TEMPORARY_CONCLUSION_ADDED,),
        )
        self._append_required_effective_events(
            selected_events=selected_events,
            effective_by_id=effective_by_id,
            event_ids=workspace.confirmed_decision_ids,
            allowed_types=(DiscussionEventType.DECISION_CONFIRMED,),
        )
        if workspace.latest_user_correction_event_id is not None:
            self._append_required_effective_events(
                selected_events=selected_events,
                effective_by_id=effective_by_id,
                event_ids=(workspace.latest_user_correction_event_id,),
                allowed_types=(DiscussionEventType.USER_CORRECTION_RECORDED,),
            )

        unique_events = {event.id: event for event in selected_events}
        return ActiveDiscussionWorkspaceContext(
            workspace=workspace,
            active_events=tuple(
                sorted(unique_events.values(), key=self._event_sort_key)
            ),
        )

    @staticmethod
    def _append_required_effective_events(
        *,
        selected_events: list[DiscussionEvent],
        effective_by_id: dict[UUID, DiscussionEvent],
        event_ids: tuple[UUID, ...] | list[UUID],
        allowed_types: tuple[DiscussionEventType, ...],
    ) -> None:
        for event_id in event_ids:
            event = effective_by_id.get(event_id)
            if event is None or event.event_type not in allowed_types:
                raise ValueError("discussion_context_workspace_reference_invalid")
            selected_events.append(event)

    def _build_relevant_events(
        self,
        *,
        plan: DiscussionContextPlan,
        resolution: DiscussionEventResolution,
    ) -> tuple[ResolvedDiscussionContextEvent, ...]:
        candidates = [
            ResolvedDiscussionContextEvent(
                event=event,
                resolved_status=self._resolved_status(
                    event=event, resolution=resolution
                ),
            )
            for event in resolution.ordered_events
        ]
        filtered = [
            item
            for item in candidates
            if item.event.event_type in plan.included_event_types
            and item.resolved_status in plan.included_event_statuses
            and self._matches_references(item.event, plan)
        ]
        recent_first = sorted(
            filtered, key=lambda item: self._event_sort_key(item.event), reverse=True
        )[: plan.relevant_event_limit]
        return tuple(
            sorted(recent_first, key=lambda item: self._event_sort_key(item.event))
        )

    @staticmethod
    def _resolved_status(
        *,
        event: DiscussionEvent,
        resolution: DiscussionEventResolution,
    ) -> DiscussionEventStatus:
        if event.id in resolution.superseded_event_ids:
            return DiscussionEventStatus.SUPERSEDED
        if event in resolution.effective_events:
            return event.status
        if event.status == DiscussionEventStatus.REJECTED:
            return DiscussionEventStatus.REJECTED
        if event.status == DiscussionEventStatus.SUPERSEDED:
            return DiscussionEventStatus.SUPERSEDED
        return DiscussionEventStatus.HISTORICAL

    def _matches_references(
        self, event: DiscussionEvent, plan: DiscussionContextPlan
    ) -> bool:
        if not plan.referenced_option_ids and not plan.referenced_entity_ids:
            return True
        return self._matches_option_reference(
            event=event, option_ids=plan.referenced_option_ids
        ) or self._matches_entity_reference(
            event=event, entity_ids=plan.referenced_entity_ids
        )

    def _matches_option_reference(
        self, *, event: DiscussionEvent, option_ids: tuple[UUID, ...]
    ) -> bool:
        if not option_ids:
            return False
        event_option_id = self._event_option_id(event)
        return (
            event_option_id in option_ids
            or any(event.subject_key == f"option:{option_id}" for option_id in option_ids)
        )

    def _matches_entity_reference(
        self, *, event: DiscussionEvent, entity_ids: tuple[UUID, ...]
    ) -> bool:
        if not entity_ids:
            return False
        event_ids = {event.id, event.supersedes_event_id, *event.source_message_ids}
        subject_ids = {
            UUID(match.group(0)) for match in _UUID_TEXT_PATTERN.finditer(event.subject_key)
        }
        payload_ids = self._collect_payload_uuids(event.payload)
        return any(
            entity_id in event_ids or entity_id in subject_ids or entity_id in payload_ids
            for entity_id in entity_ids
        )

    @classmethod
    def _collect_payload_uuids(cls, value: object) -> set[UUID]:
        if isinstance(value, UUID):
            return {value}
        if isinstance(value, dict):
            return set().union(
                *(cls._collect_payload_uuids(item) for item in value.values())
            )
        if isinstance(value, (list, tuple)):
            return set().union(*(cls._collect_payload_uuids(item) for item in value))
        if isinstance(value, str):
            try:
                return {UUID(value)}
            except ValueError:
                return set()
        return set()

    @staticmethod
    def _event_option_id(event: DiscussionEvent) -> UUID | None:
        raw_option_id = event.payload.get("option_id")
        try:
            return raw_option_id if isinstance(raw_option_id, UUID) else UUID(
                str(raw_option_id)
            )
        except (TypeError, ValueError, AttributeError):
            return None

    @staticmethod
    def _event_sort_key(event: DiscussionEvent) -> tuple[int, datetime, str]:
        return event.sequence_no, event.created_at, str(event.id)
