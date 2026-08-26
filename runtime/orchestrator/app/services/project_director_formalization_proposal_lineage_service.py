"""Shared read-only validation for persisted formalization proposal lineage."""

from __future__ import annotations

from uuid import UUID

from app.domain.project_director_discussion import (
    DiscussionEvent,
    DiscussionEventStatus,
    DiscussionEventType,
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


__all__ = ("ProjectDirectorFormalizationProposalLineageService",)
