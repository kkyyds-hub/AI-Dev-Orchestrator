"""Delivery diff dry-run audit events backed by the AgentMessage timeline."""

from __future__ import annotations

from app.domain.agent_message import AgentMessage, AgentMessageRole, AgentMessageType
from app.domain.agent_session import AgentSession
from app.domain.delivery_event import DeliveryEventBuilder, DeliveryEventSchema
from app.repositories.agent_message_repository import AgentMessageRepository


class DeliveryEventAuditService:
    """Append P4-B3 delivery diff dry-run events to AgentMessage.

    P4-B3 records only diff dry-run evidence events.  It does not implement
    delivery gates, run Git write commands, request human approvals, open PRs,
    trigger CI, or write RuntimeEvent rows.
    """

    def __init__(self, agent_message_repository: AgentMessageRepository) -> None:
        self.agent_message_repository = agent_message_repository

    def record_diff_dry_run_event(
        self,
        *,
        session: AgentSession,
        result: object | None,
        skipped_reason_code: str | None = None,
        workspace_path: str | None = None,
    ) -> AgentMessage:
        """Record one collected/skipped/failed delivery diff dry-run event."""

        event = DeliveryEventBuilder.from_diff_dry_run_result(
            session_id=session.id,
            project_id=session.project_id,
            task_id=session.task_id,
            run_id=session.run_id,
            result=result,
            skipped_reason_code=skipped_reason_code,
            workspace_path=workspace_path,
            created_by="TaskWorker.run_once",
        )
        return self._append_delivery_event_message(
            session=session,
            event=event,
        )

    def _append_delivery_event_message(
        self,
        *,
        session: AgentSession,
        event: DeliveryEventSchema,
    ) -> AgentMessage:
        """Append one delivery event into the per-session message timeline."""

        sequence_no = self.agent_message_repository.get_next_sequence_no(
            session_id=session.id
        )
        return self.agent_message_repository.create(
            session_id=session.id,
            project_id=session.project_id,
            task_id=session.task_id,
            run_id=session.run_id,
            sequence_no=sequence_no,
            role=AgentMessageRole.SYSTEM,
            message_type=AgentMessageType.TIMELINE,
            event_type=event.event_type.value,
            phase=session.current_phase.value,
            state_from=event.previous_delivery_state.value,
            state_to=event.next_delivery_state.value,
            intervention_type=None,
            note_event_type=None,
            context_checkpoint_id=session.context_checkpoint_id,
            context_rehydrated=session.context_rehydrated,
            content_summary=event.summary_cn,
            content_detail=event.to_content_detail_json(),
        )
