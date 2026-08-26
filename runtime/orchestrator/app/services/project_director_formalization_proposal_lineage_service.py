"""Shared read-only validation for persisted formalization proposal lineage."""

from __future__ import annotations

from uuid import UUID

from app.domain.project_director_discussion import (
    DiscussionEvent,
    DiscussionEventStatus,
    DiscussionEventType,
    DiscussionStatus,
    DiscussionWorkspace,
)
from app.domain.project_director_formalization_proposal import (
    ProjectDirectorFormalizationProposal,
)
from app.repositories.project_director_discussion_event_repository import (
    ProjectDirectorDiscussionEventRepository,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.services.project_director_discussion_workspace_reducer_service import (
    ProjectDirectorDiscussionWorkspaceReducerService,
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


class ProjectDirectorFormalizationProposalLineageService:
    """Validate proposal provenance against one already-resolved workspace lineage."""

    def __init__(
        self,
        *,
        message_repository: ProjectDirectorMessageRepository,
        event_repository: ProjectDirectorDiscussionEventRepository,
    ) -> None:
        self._message_repository = message_repository
        self._event_repository = event_repository

    def validate(
        self,
        *,
        proposal: ProjectDirectorFormalizationProposal,
        session_id: UUID,
        workspace: DiscussionWorkspace,
        workspace_events: tuple[DiscussionEvent, ...] | list[DiscussionEvent],
    ) -> tuple[DiscussionEvent, ...]:
        """Return source events only when every canonical P26 lineage rule passes."""

        assistant_message = self._message_repository.get_by_id(
            proposal.assistant_message_id
        )
        if assistant_message is None:
            raise ValueError("project_director_formalization_proposal_lineage_invalid")
        if assistant_message.session_id != session_id:
            raise ValueError("project_director_formalization_proposal_session_mismatch")

        for message_id in proposal.source_message_ids:
            message = self._message_repository.get_by_id(message_id)
            if message is None:
                raise ValueError("project_director_formalization_source_message_not_found")
            if message.session_id != session_id:
                raise ValueError(
                    "project_director_formalization_source_message_session_mismatch"
                )

        valid_workspace_event_ids = {event.id for event in workspace_events}
        source_events: list[DiscussionEvent] = []
        for event_id in proposal.source_event_ids:
            event = self._event_repository.get_by_id(event_id=event_id)
            if event is None:
                raise ValueError("project_director_formalization_proposal_lineage_invalid")
            if (
                event.session_id != session_id
                or event.project_id != workspace.project_id
                or event.id not in valid_workspace_event_ids
                or event.event_type == DiscussionEventType.FORMALIZATION_REQUESTED
                or event.status
                in {DiscussionEventStatus.REJECTED, DiscussionEventStatus.HISTORICAL}
                or event.created_at >= proposal.created_at
                or proposal.assistant_message_id in event.source_message_ids
            ):
                raise ValueError(
                    "project_director_formalization_proposal_lineage_invalid"
                )
            source_events.append(event)
        if not source_events:
            raise ValueError("project_director_formalization_proposal_lineage_invalid")
        return tuple(source_events)

    def resolve_workspace_source_events(
        self,
        *,
        workspace: DiscussionWorkspace,
        events: tuple[DiscussionEvent, ...] | list[DiscussionEvent],
    ) -> tuple[DiscussionEvent, ...]:
        """Resolve the canonical, narrow source-event lineage for one workspace."""

        ordered_events = tuple(events)
        previous_sequence_no = 0
        for event in ordered_events:
            if event.session_id != workspace.session_id:
                raise ValueError("project_director_formalization_event_session_mismatch")
            if event.project_id != workspace.project_id:
                raise ValueError("project_director_formalization_event_project_mismatch")
            if event.sequence_no <= previous_sequence_no:
                raise ValueError(
                    "project_director_formalization_workspace_event_history_mismatch"
                )
            previous_sequence_no = event.sequence_no
            if event.sequence_no > workspace.last_event_sequence_no:
                raise ValueError(
                    "project_director_formalization_workspace_event_history_ahead"
                )
        if previous_sequence_no != workspace.last_event_sequence_no:
            raise ValueError(
                "project_director_formalization_workspace_event_history_mismatch"
            )

        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        resolution = reducer.resolve_events(
            session_id=workspace.session_id,
            project_id=workspace.project_id,
            events=ordered_events,
        )
        for event in resolution.effective_events:
            if event.event_type in _OPTION_EVENT_TYPES:
                self._option_id(event)
        rebuilt = reducer.rebuild_workspace(
            session_id=workspace.session_id,
            project_id=workspace.project_id,
            events=ordered_events,
            version_no=workspace.version_no,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
        )
        if not self._workspace_projection_matches(workspace, rebuilt):
            raise ValueError("project_director_formalization_workspace_projection_mismatch")

        effective_events = resolution.effective_events
        effective_by_id = {event.id: event for event in effective_events}
        source_events: list[DiscussionEvent] = []

        if workspace.topic:
            topic_event = next(
                (
                    event
                    for event in reversed(effective_events)
                    if event.event_type == DiscussionEventType.TOPIC_SET
                    and event.content == workspace.topic
                ),
                None,
            )
            if topic_event is None:
                raise ValueError("project_director_formalization_topic_event_not_found")
            source_events.append(topic_event)

        active_option_ids = set(workspace.active_option_ids)
        for event in effective_events:
            if event.event_type in _OPTION_EVENT_TYPES and self._option_id(event) in active_option_ids:
                source_events.append(event)

        self._append_direct_workspace_events(
            source_events=source_events,
            effective_by_id=effective_by_id,
            event_ids=workspace.active_constraint_ids,
            allowed_types=_CONSTRAINT_EVENT_TYPES,
        )
        self._append_direct_workspace_events(
            source_events=source_events,
            effective_by_id=effective_by_id,
            event_ids=workspace.open_question_ids,
            allowed_types=frozenset({DiscussionEventType.OPEN_QUESTION_ADDED}),
        )
        self._append_direct_workspace_events(
            source_events=source_events,
            effective_by_id=effective_by_id,
            event_ids=workspace.temporary_conclusion_ids,
            allowed_types=frozenset({DiscussionEventType.TEMPORARY_CONCLUSION_ADDED}),
        )
        self._append_direct_workspace_events(
            source_events=source_events,
            effective_by_id=effective_by_id,
            event_ids=workspace.confirmed_decision_ids,
            allowed_types=frozenset({DiscussionEventType.DECISION_CONFIRMED}),
        )
        if workspace.latest_user_correction_event_id is not None:
            self._append_direct_workspace_events(
                source_events=source_events,
                effective_by_id=effective_by_id,
                event_ids=(workspace.latest_user_correction_event_id,),
                allowed_types=frozenset({DiscussionEventType.USER_CORRECTION_RECORDED}),
            )

        status_event = next(
            (
                event
                for event in reversed(effective_events)
                if event.event_type in _STATUS_EVENT_TYPES
            ),
            None,
        )
        if status_event is not None:
            source_events.append(status_event)
        if workspace.discussion_status == DiscussionStatus.READY_TO_FORMALIZE and (
            status_event is None
            or status_event.event_type != DiscussionEventType.FORMALIZATION_REQUESTED
        ):
            raise ValueError("project_director_formalization_status_event_not_found")

        return self._validate_source_events(source_events=source_events, workspace=workspace)

    @staticmethod
    def _option_id(event: DiscussionEvent) -> UUID:
        try:
            raw_option_id = event.payload["option_id"]
            return raw_option_id if isinstance(raw_option_id, UUID) else UUID(str(raw_option_id))
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ValueError("project_director_formalization_option_id_invalid") from exc

    @staticmethod
    def _workspace_projection_matches(
        workspace: DiscussionWorkspace, rebuilt: DiscussionWorkspace
    ) -> bool:
        return (
            workspace.topic == rebuilt.topic
            and workspace.discussion_status == rebuilt.discussion_status
            and workspace.active_option_ids == rebuilt.active_option_ids
            and workspace.preferred_option_id == rebuilt.preferred_option_id
            and workspace.active_constraint_ids == rebuilt.active_constraint_ids
            and workspace.open_question_ids == rebuilt.open_question_ids
            and workspace.temporary_conclusion_ids == rebuilt.temporary_conclusion_ids
            and workspace.confirmed_decision_ids == rebuilt.confirmed_decision_ids
            and workspace.latest_user_correction_event_id == rebuilt.latest_user_correction_event_id
            and workspace.last_event_sequence_no == rebuilt.last_event_sequence_no
        )

    @staticmethod
    def _append_direct_workspace_events(
        *,
        source_events: list[DiscussionEvent],
        effective_by_id: dict[UUID, DiscussionEvent],
        event_ids: tuple[UUID, ...] | list[UUID],
        allowed_types: frozenset[DiscussionEventType],
    ) -> None:
        for event_id in event_ids:
            event = effective_by_id.get(event_id)
            if event is None:
                raise ValueError("project_director_formalization_event_not_found")
            if event.event_type not in allowed_types:
                raise ValueError("project_director_formalization_workspace_event_type_mismatch")
            source_events.append(event)

    @staticmethod
    def _validate_source_events(
        *,
        source_events: list[DiscussionEvent],
        workspace: DiscussionWorkspace,
    ) -> tuple[DiscussionEvent, ...]:
        unique_events = {event.id: event for event in source_events}
        ordered_events = tuple(sorted(unique_events.values(), key=lambda event: event.sequence_no))
        if not ordered_events or any(
            event.session_id != workspace.session_id
            or event.project_id != workspace.project_id
            or event.sequence_no > workspace.last_event_sequence_no
            for event in ordered_events
        ):
            raise ValueError("project_director_formalization_workspace_not_ready")
        return ordered_events


__all__ = ("ProjectDirectorFormalizationProposalLineageService",)
