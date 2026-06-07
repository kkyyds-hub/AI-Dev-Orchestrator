"""P6-D agent dispatch decision audit events backed by AgentMessage."""

from __future__ import annotations

import json
from typing import Any

from app.domain.agent_dispatch_decision import AgentDispatchDecision
from app.domain.agent_message import AgentMessage, AgentMessageRole, AgentMessageType
from app.domain.agent_session import AgentSession
from app.domain.run import RunStatus
from app.domain.task import TaskStatus
from app.repositories.agent_message_repository import AgentMessageRepository


class AgentDispatchAuditService:
    """Append P6 dispatch decisions to the AgentMessage timeline.

    P6-D records only an audit/timeline message for an already-built
    ``AgentDispatchDecision``. It does not expose API fields, dispatch workers,
    trigger retries, create tasks, mutate frontend contracts, or run Git/CI
    commands.
    """

    def __init__(self, agent_message_repository: AgentMessageRepository) -> None:
        self.agent_message_repository = agent_message_repository

    def record_decision(
        self,
        *,
        session: AgentSession,
        decision: AgentDispatchDecision,
        run_status: RunStatus,
        task_status: TaskStatus | None,
        result_summary: str | None,
    ) -> AgentMessage:
        """Record one P6 dispatch decision as a timeline message."""

        existing_message = next(
            (
                message
                for message in self.agent_message_repository.list_by_project_id(
                    project_id=session.project_id,
                    limit=1_000,
                    message_types=[AgentMessageType.TIMELINE],
                )
                if message.run_id == session.run_id
                and message.event_type == decision.audit_event_type
            ),
            None,
        )
        if existing_message is not None:
            return existing_message

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
            state_to=decision.dispatch_status.value,
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
    def _summary(decision: AgentDispatchDecision) -> str:
        """Build a compact Director-visible timeline summary."""

        agent_label = {
            "codex": "Codex 继续处理",
            "deepseek": "DeepSeek 继续处理",
            "user": "等待用户决策",
            "blocked": "当前不可调度",
        }[decision.recommended_agent.value]
        draft_clause = (
            "系统已保留下一步只读指令草案。"
            if decision.instruction_draft is not None
            else "当前不生成可执行指令草案。"
        )
        return (
            "P6 调度建议：系统已基于失败回流决策生成只读调度建议。"
            f"建议：{agent_label}。"
            f"{draft_clause}"
            "当前状态仅建议，未派发。"
            "不会自动派发、重试或创建任务。"
        )[:2_000]

    @staticmethod
    def _detail_json(
        *,
        decision: AgentDispatchDecision,
        run_status: RunStatus,
        task_status: TaskStatus | None,
        result_summary: str | None,
    ) -> str:
        """Serialize bounded structured evidence into AgentMessage.content_detail."""

        payload: dict[str, Any] = {
            "p6_stage": "P6-D",
            "event_type": decision.audit_event_type,
            "run_status": run_status.value,
            "task_status": task_status.value if task_status is not None else None,
            "result_summary": result_summary,
            "decision": decision.model_dump(mode="json"),
            "p6_d_safety": {
                "agent_message_recorded": True,
                "agent_message_written": True,
                "api_response_exposed": False,
                "retry_triggered": False,
                "worker_dispatch_triggered": False,
                "task_created": False,
                "auto_dispatch_triggered": False,
                "runs_git": False,
                "runs_write_git": False,
                "git_add_triggered": False,
                "git_commit_triggered": False,
                "git_push_triggered": False,
                "pr_opened": False,
                "merge_triggered": False,
                "branch_deleted": False,
                "git_reset_triggered": False,
                "git_checkout_triggered": False,
                "git_switch_triggered": False,
                "git_stash_triggered": False,
                "git_rebase_triggered": False,
                "git_tag_triggered": False,
                "ci_triggered": False,
                "execution_enabled": False,
            },
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)[:4_000]
