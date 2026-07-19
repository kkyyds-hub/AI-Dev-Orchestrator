"""Pure deterministic projection of Project Director discussion events."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain._base import ensure_utc_datetime, utc_now
from app.domain.project_director_discussion import (
    DiscussionEvent,
    DiscussionEventStatus,
    DiscussionEventType,
    DiscussionStatus,
    DiscussionWorkspace,
)


_EFFECTIVE_EVENT_STATUSES = frozenset(
    {DiscussionEventStatus.ACTIVE, DiscussionEventStatus.CONFIRMED}
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


@dataclass(frozen=True)
class DiscussionEventResolution:
    """A complete, ordered classification of one discussion event history."""

    ordered_events: tuple[DiscussionEvent, ...]
    effective_events: tuple[DiscussionEvent, ...]
    historical_events: tuple[DiscussionEvent, ...]
    superseded_event_ids: frozenset[UUID]


class ProjectDirectorDiscussionWorkspaceReducerService:
    """Build immutable discussion workspaces without persistence side effects."""

    def resolve_events(
        self,
        *,
        session_id: UUID,
        project_id: UUID | None,
        events: Sequence[DiscussionEvent],
    ) -> DiscussionEventResolution:
        """Validate, order, and classify the complete event history."""

        ordered_events = tuple(sorted(events, key=lambda event: event.sequence_no))
        event_by_id: dict[UUID, DiscussionEvent] = {}
        seen_sequences: set[int] = set()

        for event in ordered_events:
            if event.session_id != session_id:
                raise ValueError("discussion_event_stream_session_mismatch")
            if event.project_id != project_id:
                raise ValueError("discussion_event_stream_project_mismatch")
            if event.id in event_by_id:
                raise ValueError("discussion_event_stream_duplicate_event_id")
            if event.sequence_no in seen_sequences:
                raise ValueError("discussion_event_stream_duplicate_sequence")
            event_by_id[event.id] = event
            seen_sequences.add(event.sequence_no)

        superseded_event_ids: set[UUID] = set()
        for event in ordered_events:
            target_id = event.supersedes_event_id
            if target_id is None:
                continue
            target = event_by_id.get(target_id)
            if target is None:
                raise ValueError("discussion_event_stream_supersedes_not_found")
            if target.sequence_no >= event.sequence_no:
                raise ValueError("discussion_event_stream_supersedes_not_prior")
            if event.status in _EFFECTIVE_EVENT_STATUSES:
                superseded_event_ids.add(target_id)

        effective_events = tuple(
            event
            for event in ordered_events
            if event.status in _EFFECTIVE_EVENT_STATUSES
            and event.id not in superseded_event_ids
        )
        historical_events = tuple(
            event for event in ordered_events if event.id not in {item.id for item in effective_events}
        )
        return DiscussionEventResolution(
            ordered_events=ordered_events,
            effective_events=effective_events,
            historical_events=historical_events,
            superseded_event_ids=frozenset(superseded_event_ids),
        )

    def rebuild_workspace(
        self,
        *,
        session_id: UUID,
        project_id: UUID | None,
        events: Sequence[DiscussionEvent],
        version_no: int = 0,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> DiscussionWorkspace:
        """Rebuild a workspace projection from the complete event history."""

        resolution = self.resolve_events(
            session_id=session_id, project_id=project_id, events=events
        )
        event_by_id = {event.id: event for event in resolution.ordered_events}
        self._validate_target_event_types(resolution.ordered_events, event_by_id)

        topic = ""
        active_option_ids: list[UUID] = []
        preferred_option_id: UUID | None = None
        active_constraint_ids: list[UUID] = []
        open_question_ids: list[UUID] = []
        temporary_conclusion_ids: list[UUID] = []
        confirmed_decision_ids: list[UUID] = []
        latest_user_correction_event_id: UUID | None = None
        discussion_status = DiscussionStatus.EXPLORING
        explicit_status_seen = False

        for event in resolution.effective_events:
            event_type = event.event_type
            if event_type == DiscussionEventType.TOPIC_SET:
                topic = event.content
            elif event_type in _OPTION_EVENT_TYPES:
                option_id = self._option_id(event)
                if event_type == DiscussionEventType.OPTION_ADDED:
                    if option_id not in active_option_ids:
                        active_option_ids.append(option_id)
                elif event_type == DiscussionEventType.OPTION_UPDATED:
                    if option_id not in active_option_ids:
                        if self._is_option_replacement(
                            event=event,
                            event_by_id=event_by_id,
                            option_id=option_id,
                        ):
                            active_option_ids.append(option_id)
                        else:
                            self._require_active_option(option_id, active_option_ids)
                elif event_type == DiscussionEventType.OPTION_PREFERRED:
                    self._require_active_option(option_id, active_option_ids)
                    preferred_option_id = option_id
                    discussion_status = DiscussionStatus.CONVERGING
                    explicit_status_seen = True
                else:
                    self._require_active_option(option_id, active_option_ids)
                    active_option_ids.remove(option_id)
                    if preferred_option_id == option_id:
                        preferred_option_id = None
            elif event_type in _CONSTRAINT_EVENT_TYPES:
                active_constraint_ids.append(event.id)
            elif event_type == DiscussionEventType.OPEN_QUESTION_ADDED:
                open_question_ids.append(event.id)
            elif event_type == DiscussionEventType.TEMPORARY_CONCLUSION_ADDED:
                temporary_conclusion_ids.append(event.id)
            elif event_type == DiscussionEventType.DECISION_CONFIRMED:
                confirmed_decision_ids.append(event.id)
                discussion_status = DiscussionStatus.CONVERGING
                explicit_status_seen = True
            elif event_type == DiscussionEventType.USER_CORRECTION_RECORDED:
                latest_user_correction_event_id = event.id
            elif event_type == DiscussionEventType.FORMALIZATION_REQUESTED:
                discussion_status = DiscussionStatus.READY_TO_FORMALIZE
                explicit_status_seen = True
            elif event_type == DiscussionEventType.FORMALIZATION_CANCELLED:
                discussion_status = DiscussionStatus.CONVERGING
                explicit_status_seen = True

        if not explicit_status_seen and len(active_option_ids) >= 2:
            discussion_status = DiscussionStatus.COMPARING

        if resolution.ordered_events:
            default_created_at = resolution.ordered_events[0].created_at
            default_updated_at = resolution.ordered_events[-1].created_at
            last_event_sequence_no = resolution.ordered_events[-1].sequence_no
        else:
            default_created_at = utc_now()
            default_updated_at = default_created_at
            last_event_sequence_no = 0

        return DiscussionWorkspace(
            session_id=session_id,
            project_id=project_id,
            topic=topic,
            discussion_status=discussion_status,
            active_option_ids=active_option_ids,
            preferred_option_id=preferred_option_id,
            active_constraint_ids=active_constraint_ids,
            open_question_ids=open_question_ids,
            temporary_conclusion_ids=temporary_conclusion_ids,
            confirmed_decision_ids=confirmed_decision_ids,
            latest_user_correction_event_id=latest_user_correction_event_id,
            version_no=version_no,
            last_event_sequence_no=last_event_sequence_no,
            created_at=ensure_utc_datetime(created_at or default_created_at),
            updated_at=ensure_utc_datetime(updated_at or default_updated_at),
        )

    def reduce_workspace(
        self,
        *,
        workspace: DiscussionWorkspace,
        events: Sequence[DiscussionEvent],
        updated_at: datetime | None = None,
    ) -> tuple[DiscussionWorkspace, bool]:
        """Refresh a workspace from full history, incrementing only on change."""

        rebuilt = self.rebuild_workspace(
            session_id=workspace.session_id,
            project_id=workspace.project_id,
            events=events,
            version_no=workspace.version_no,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
        )
        if rebuilt.last_event_sequence_no < workspace.last_event_sequence_no:
            raise ValueError("discussion_workspace_event_history_regressed")
        if self._projection_matches(workspace, rebuilt):
            return workspace, False

        return (
            DiscussionWorkspace(
                session_id=workspace.session_id,
                project_id=workspace.project_id,
                topic=rebuilt.topic,
                discussion_status=rebuilt.discussion_status,
                active_option_ids=rebuilt.active_option_ids,
                preferred_option_id=rebuilt.preferred_option_id,
                active_constraint_ids=rebuilt.active_constraint_ids,
                open_question_ids=rebuilt.open_question_ids,
                temporary_conclusion_ids=rebuilt.temporary_conclusion_ids,
                confirmed_decision_ids=rebuilt.confirmed_decision_ids,
                latest_user_correction_event_id=rebuilt.latest_user_correction_event_id,
                version_no=workspace.version_no + 1,
                last_event_sequence_no=rebuilt.last_event_sequence_no,
                created_at=workspace.created_at,
                updated_at=ensure_utc_datetime(updated_at or utc_now()),
            ),
            True,
        )

    @staticmethod
    def _option_id(event: DiscussionEvent) -> UUID:
        raw_option_id = event.payload.get("option_id")
        try:
            return raw_option_id if isinstance(raw_option_id, UUID) else UUID(str(raw_option_id))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("discussion_workspace_reducer_option_id_invalid") from exc

    @staticmethod
    def _require_active_option(option_id: UUID, active_option_ids: list[UUID]) -> None:
        if option_id not in active_option_ids:
            raise ValueError("discussion_workspace_reducer_option_not_active")

    @classmethod
    def _is_option_replacement(
        cls,
        *,
        event: DiscussionEvent,
        event_by_id: dict[UUID, DiscussionEvent],
        option_id: UUID,
    ) -> bool:
        """Return whether an update replaces an earlier active option lineage."""

        current = event
        while current.event_type == DiscussionEventType.OPTION_UPDATED:
            target_id = current.supersedes_event_id
            if target_id is None:
                return False
            target = event_by_id.get(target_id)
            if (
                target is None
                or target.sequence_no >= current.sequence_no
                or target.status not in _EFFECTIVE_EVENT_STATUSES
                or target.event_type
                not in {
                    DiscussionEventType.OPTION_ADDED,
                    DiscussionEventType.OPTION_UPDATED,
                }
                or cls._option_id(target) != option_id
            ):
                return False
            if target.event_type == DiscussionEventType.OPTION_ADDED:
                return True
            current = target
        return False

    @staticmethod
    def _validate_target_event_types(
        events: Sequence[DiscussionEvent],
        event_by_id: dict[UUID, DiscussionEvent],
    ) -> None:
        for event in events:
            if event.event_type in {
                DiscussionEventType.CONSTRAINT_UPDATED,
                DiscussionEventType.CONSTRAINT_SUPERSEDED,
            }:
                target = event_by_id.get(event.supersedes_event_id)
                if target is None or target.event_type not in _CONSTRAINT_EVENT_TYPES:
                    raise ValueError("discussion_workspace_reducer_constraint_target_invalid")
            elif event.event_type == DiscussionEventType.OPEN_QUESTION_RESOLVED:
                target = event_by_id.get(event.supersedes_event_id)
                if target is None or target.event_type != DiscussionEventType.OPEN_QUESTION_ADDED:
                    raise ValueError("discussion_workspace_reducer_question_target_invalid")

    @staticmethod
    def _projection_matches(
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
            and workspace.latest_user_correction_event_id
            == rebuilt.latest_user_correction_event_id
            and workspace.last_event_sequence_no == rebuilt.last_event_sequence_no
        )
