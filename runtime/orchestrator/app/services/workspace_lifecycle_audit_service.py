"""Workspace lifecycle audit events backed by the AgentMessage timeline."""

from __future__ import annotations

import json
from typing import Any, Literal

from app.domain.agent_message import AgentMessageRole, AgentMessageType
from app.domain.agent_session import AgentSession
from app.domain.worktree_cleanup import WorktreeCleanupResult
from app.domain.worktree_create import WorktreeCreateResult
from app.repositories.agent_message_repository import AgentMessageRepository


WORKSPACE_CREATE_BLOCKED_EVENT = "workspace.create.blocked"
WORKSPACE_CREATE_FAILED_EVENT = "workspace.create.failed"
WORKSPACE_CREATE_CREATED_EVENT = "workspace.create.created"
WORKSPACE_CLEANUP_BLOCKED_EVENT = "workspace.cleanup.blocked"
WORKSPACE_CLEANUP_FAILED_EVENT = "workspace.cleanup.failed"
WORKSPACE_CLEANUP_CLEANED_EVENT = "workspace.cleanup.cleaned"

LifecycleAuditOutcome = Literal["blocked", "failed", "succeeded"]


class WorkspaceLifecycleAuditService:
    """Append workspace lifecycle audit notes to the existing AgentMessage stream."""

    event_type = "workspace_lifecycle_audit"

    def __init__(self, agent_message_repository: AgentMessageRepository) -> None:
        self.agent_message_repository = agent_message_repository

    def record_create_result(
        self,
        *,
        session: AgentSession,
        result: WorktreeCreateResult,
    ) -> None:
        """Record one workspace create lifecycle result as an AgentMessage note."""

        outcome = self._outcome_from_status(result.create_status)
        note_event_type = {
            "blocked": WORKSPACE_CREATE_BLOCKED_EVENT,
            "failed": WORKSPACE_CREATE_FAILED_EVENT,
            "succeeded": WORKSPACE_CREATE_CREATED_EVENT,
        }[outcome]
        self._append_audit_message(
            session=session,
            action="create",
            outcome=outcome,
            note_event_type=note_event_type,
            status=result.create_status,
            blocked_reason=result.blocked_reason,
            worktree_path=result.worktree_path,
            branch_name=result.branch_name,
            detail={
                "plan_hash": result.plan_hash,
                "submitted_plan_hash": result.submitted_plan_hash,
                "workspace_path": result.worktree_path,
                "branch_name": result.branch_name,
                "blocked_reason": result.blocked_reason,
                "create_status": result.create_status,
                "blockers": result.blockers,
                "warnings": result.warnings,
                "runs_git": result.runs_git,
                "runs_write_git": result.runs_write_git,
                "mutates_agent_session_workspace": (
                    result.mutates_agent_session_workspace
                ),
            },
        )

    def record_cleanup_result(
        self,
        *,
        session: AgentSession,
        result: WorktreeCleanupResult,
    ) -> None:
        """Record one workspace cleanup lifecycle result as an AgentMessage note."""

        outcome = self._outcome_from_status(result.cleanup_status)
        note_event_type = {
            "blocked": WORKSPACE_CLEANUP_BLOCKED_EVENT,
            "failed": WORKSPACE_CLEANUP_FAILED_EVENT,
            "succeeded": WORKSPACE_CLEANUP_CLEANED_EVENT,
        }[outcome]
        self._append_audit_message(
            session=session,
            action="cleanup",
            outcome=outcome,
            note_event_type=note_event_type,
            status=result.cleanup_status,
            blocked_reason=result.blocked_reason,
            worktree_path=result.worktree_path,
            branch_name=result.branch_name,
            detail={
                "plan_hash": result.plan_hash,
                "submitted_plan_hash": result.submitted_plan_hash,
                "workspace_path": result.worktree_path,
                "branch_name": result.branch_name,
                "blocked_reason": result.blocked_reason,
                "cleanup_status": result.cleanup_status,
                "blockers": result.blockers,
                "warnings": result.warnings,
                "runs_git": result.runs_git,
                "runs_write_git": result.runs_write_git,
                "removes_worktree": result.removes_worktree,
                "deletes_branch": result.deletes_branch,
                "deletes_directory": result.deletes_directory,
                "mutates_agent_session_workspace": (
                    result.mutates_agent_session_workspace
                ),
            },
        )

    def _append_audit_message(
        self,
        *,
        session: AgentSession,
        action: str,
        outcome: LifecycleAuditOutcome,
        note_event_type: str,
        status: str,
        blocked_reason: str | None,
        worktree_path: str | None,
        branch_name: str | None,
        detail: dict[str, Any],
    ) -> None:
        """Append one audit note into the existing per-session message timeline."""

        sequence_no = self.agent_message_repository.get_next_sequence_no(
            session_id=session.id
        )
        detail_payload = {
            **detail,
            "action": action,
            "outcome": outcome,
            "note_event_type": note_event_type,
        }
        self.agent_message_repository.create(
            session_id=session.id,
            project_id=session.project_id,
            task_id=session.task_id,
            run_id=session.run_id,
            sequence_no=sequence_no,
            role=AgentMessageRole.SYSTEM,
            message_type=AgentMessageType.NOTE_EVENT,
            event_type=self.event_type,
            phase=session.current_phase.value,
            state_from=None,
            state_to=status,
            intervention_type=None,
            note_event_type=note_event_type,
            context_checkpoint_id=session.context_checkpoint_id,
            context_rehydrated=session.context_rehydrated,
            content_summary=self._summary(
                action=action,
                outcome=outcome,
                blocked_reason=blocked_reason,
                worktree_path=worktree_path,
                branch_name=branch_name,
            ),
            content_detail=self._detail_json(detail_payload),
        )

    @staticmethod
    def _outcome_from_status(status: str) -> LifecycleAuditOutcome:
        """Map lifecycle result status strings to normalized audit outcomes."""

        if status in {"created", "cleaned"}:
            return "succeeded"
        if status == "failed":
            return "failed"
        return "blocked"

    @staticmethod
    def _summary(
        *,
        action: str,
        outcome: LifecycleAuditOutcome,
        blocked_reason: str | None,
        worktree_path: str | None,
        branch_name: str | None,
    ) -> str:
        """Build a compact frontend-readable lifecycle summary."""

        reason = f": {blocked_reason}" if blocked_reason else ""
        target = ""
        if branch_name or worktree_path:
            target = f" branch={branch_name or '-'} workspace={worktree_path or '-'}"
        return f"Workspace {action} {outcome}{reason}{target}"[:2_000]

    @staticmethod
    def _detail_json(detail: dict[str, Any]) -> str:
        """Serialize bounded structured evidence into AgentMessage.content_detail."""

        return json.dumps(detail, ensure_ascii=False, sort_keys=True)[:4_000]
