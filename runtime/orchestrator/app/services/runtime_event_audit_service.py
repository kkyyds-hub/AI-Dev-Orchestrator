"""Runtime lifecycle audit events backed by the AgentMessage timeline."""

from __future__ import annotations

from app.domain.agent_message import AgentMessage, AgentMessageRole, AgentMessageType
from app.domain.agent_session import AgentSession
from app.domain.runtime_event import RuntimeEventBuilder, RuntimeEventSchema
from app.repositories.agent_message_repository import AgentMessageRepository


class RuntimeEventAuditService:
    """Append P3-D runtime gate events to the existing AgentMessage stream.

    P3-D3 intentionally records only launch-gate evidence events.  It does not
    start fake launches, start real runtimes, probe runtime processes, run git,
    or write any future non-gate runtime lifecycle event.
    """

    def __init__(self, agent_message_repository: AgentMessageRepository) -> None:
        self.agent_message_repository = agent_message_repository

    def record_launch_gate_event(
        self,
        *,
        session: AgentSession,
        gate_result: object,
        adapter_kind: str | None,
        workspace_path: str | None,
        observed_pwd: str | None,
        launch_cwd_preview: str | None,
    ) -> AgentMessage:
        """Record one evaluated/blocked runtime launch gate event."""

        event = RuntimeEventBuilder.from_gate_result(
            session_id=session.id,
            project_id=session.project_id,
            task_id=session.task_id,
            run_id=session.run_id,
            gate_result=gate_result,
            runtime_type=(
                session.runtime_type.value
                if session.runtime_type is not None
                else None
            ),
            agent_type=(
                session.agent_type.value
                if session.agent_type is not None
                else None
            ),
            adapter_kind=adapter_kind,
            workspace_path=workspace_path,
            observed_pwd=observed_pwd,
            launch_cwd_preview=launch_cwd_preview,
            created_by="TaskWorker.run_once",
        )
        return self._append_runtime_event_message(
            session=session,
            event=event,
        )

    def _append_runtime_event_message(
        self,
        *,
        session: AgentSession,
        event: RuntimeEventSchema,
    ) -> AgentMessage:
        """Append one runtime event into the per-session message timeline."""

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
            state_from=event.previous_runtime_state.value,
            state_to=event.next_runtime_state.value,
            intervention_type=None,
            note_event_type=None,
            context_checkpoint_id=session.context_checkpoint_id,
            context_rehydrated=session.context_rehydrated,
            content_summary=event.summary_cn,
            content_detail=event.to_content_detail_json(),
        )
