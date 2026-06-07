"""P5-D failure recovery decision audit events backed by AgentMessage."""

from __future__ import annotations

import json
from typing import Any

from app.domain.agent_message import AgentMessage, AgentMessageRole, AgentMessageType
from app.domain.agent_session import AgentSession
from app.domain.failure_recovery_decision import FailureRecoveryDecision
from app.domain.run import RunStatus
from app.domain.task import TaskStatus
from app.repositories.agent_message_repository import AgentMessageRepository


class FailureRecoveryAuditService:
    """Append P5 failure recovery decisions to the AgentMessage timeline.

    P5-D records only an audit/timeline message for an already-built internal
    ``FailureRecoveryDecision``. It does not expose API fields, dispatch workers,
    trigger retries, create tasks, mutate frontend contracts, or run Git commands.
    """

    def __init__(self, agent_message_repository: AgentMessageRepository) -> None:
        self.agent_message_repository = agent_message_repository

    def record_decision(
        self,
        *,
        session: AgentSession,
        decision: FailureRecoveryDecision,
        run_status: RunStatus,
        task_status: TaskStatus | None,
        result_summary: str | None,
    ) -> AgentMessage:
        """Record one P5 failure recovery decision as a timeline message."""

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
            event_type=decision.audit_event_type,
            phase=session.current_phase.value,
            state_from=run_status.value,
            state_to=decision.next_action.value,
            intervention_type=None,
            note_event_type=None,
            context_checkpoint_id=session.context_checkpoint_id,
            context_rehydrated=session.context_rehydrated,
            content_summary=self._summary(decision),
            content_detail=self._detail_json(
                decision=decision,
                run_status=run_status,
                task_status=task_status,
                result_summary=result_summary,
            ),
        )

    @staticmethod
    def _summary(decision: FailureRecoveryDecision) -> str:
        """Build a compact Director-visible timeline summary."""

        return (
            "P5 失败回流建议："
            f"{decision.user_visible_summary_cn} "
            f"owner={decision.recommended_owner.value} "
            f"action={decision.next_action.value} "
            f"draft_required={str(decision.next_instruction_draft_required).lower()}"
        )[:2_000]

    @staticmethod
    def _detail_json(
        *,
        decision: FailureRecoveryDecision,
        run_status: RunStatus,
        task_status: TaskStatus | None,
        result_summary: str | None,
    ) -> str:
        """Serialize bounded structured evidence into AgentMessage.content_detail."""

        payload: dict[str, Any] = {
            "p5_stage": "P5-D",
            "event_type": decision.audit_event_type,
            "run_status": run_status.value,
            "task_status": task_status.value if task_status is not None else None,
            "result_summary": result_summary,
            "decision": decision.model_dump(mode="json"),
            "p5_d_safety": {
                "api_response_exposed": False,
                "retry_triggered": False,
                "worker_dispatch_triggered": False,
                "task_created": False,
                "runs_git": False,
                "runs_write_git": False,
                "git_add_triggered": False,
                "git_commit_triggered": False,
                "git_push_triggered": False,
                "pr_opened": False,
            },
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)[:4_000]
