"""Blocked workspace cleanup skeleton.

P1-E-A validates the current plan_hash and returns disabled cleanup command
previews.  It performs no git command, no filesystem deletion, no branch
removal, no worktree removal, and no AgentSession workspace mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from app.domain.worktree_cleanup import (
    WorktreeCleanupCommandPreview,
    WorktreeCleanupResult,
)
from app.services.worktree_plan_service import WorktreePlanService


@dataclass(frozen=True, slots=True)
class WorktreeCleanupRequest:
    """Request to preview cleanup for an exact dry-run plan hash."""

    agent_session_id: UUID
    plan_hash: str
    user_confirmed: bool = True


class WorktreeCleanupError(ValueError):
    """Raised when the cleanup skeleton cannot evaluate the request."""


class WorktreeCleanupHashMismatchError(WorktreeCleanupError):
    """Raised when the submitted plan hash is stale or mismatched."""


class WorktreeCleanupService:
    """Validate cleanup preconditions and return blocked command previews."""

    def __init__(self, *, worktree_plan_service: WorktreePlanService) -> None:
        self.worktree_plan_service = worktree_plan_service

    def cleanup_workspace(self, request: WorktreeCleanupRequest) -> WorktreeCleanupResult:
        """Return a blocked cleanup result without executing repository writes."""

        if not request.user_confirmed:
            raise WorktreeCleanupError(
                "workspace cleanup requires explicit user_confirmed=true"
            )

        submitted_plan_hash = request.plan_hash.strip()
        if not submitted_plan_hash:
            raise WorktreeCleanupError("plan_hash must not be blank")

        plan = self.worktree_plan_service.build_plan(
            agent_session_id=request.agent_session_id
        )
        if submitted_plan_hash != plan.plan_hash:
            raise WorktreeCleanupHashMismatchError(
                "submitted plan_hash does not match current workspace plan"
            )

        session = self.worktree_plan_service.agent_session_repository.get_by_id(
            request.agent_session_id
        )
        if session is None:
            raise WorktreeCleanupError(f"Agent session not found: {request.agent_session_id}")

        blockers = [
            "workspace cleanup execution is blocked in P1-E-A",
            "git worktree remove is not enabled",
            "git branch delete is not enabled",
        ]
        warnings = [
            "cleanup command preview is review-only and was not executed",
            "no worktree or branch was deleted",
            "no directory was removed",
            "AgentSession workspace fields were not changed",
        ]
        if not plan.safe:
            blockers.extend(plan.blockers)
        if not plan.dry_run:
            blockers.append("workspace cleanup only accepts dry-run plans")
        if not plan.requires_user_confirmation:
            blockers.append("workspace cleanup requires a user-confirmed plan")

        worktree_path = session.workspace_path or plan.worktree_path
        branch_name = session.branch_name or plan.branch_name
        if session.workspace_path is None:
            warnings.append("AgentSession has no workspace_path; using planned path preview")
        if session.branch_name is None:
            warnings.append("AgentSession has no branch_name; using planned branch preview")

        cleanup_command_preview = self._build_cleanup_command_preview(
            repository_cwd=self._repository_cwd(plan.project_id),
            worktree_path=worktree_path,
            branch_name=branch_name,
        )

        return WorktreeCleanupResult.blocked_from_plan(
            plan=plan,
            submitted_plan_hash=submitted_plan_hash,
            worktree_path=worktree_path,
            branch_name=branch_name,
            blockers=blockers,
            warnings=warnings,
            cleanup_command_preview=cleanup_command_preview,
        )

    def _repository_cwd(self, project_id: UUID) -> str:
        """Return repository root when bound, otherwise a stable non-executed cwd."""

        repository_workspace = (
            self.worktree_plan_service.repository_workspace_repository.get_by_project_id(
                project_id
            )
        )
        if repository_workspace is None:
            return str(Path.cwd())
        return repository_workspace.root_path

    @staticmethod
    def _build_cleanup_command_preview(
        *,
        repository_cwd: str,
        worktree_path: str | None,
        branch_name: str | None,
    ) -> list[WorktreeCleanupCommandPreview]:
        """Build disabled cleanup previews for later gated implementation."""

        previews: list[WorktreeCleanupCommandPreview] = []
        if worktree_path is not None:
            previews.append(
                WorktreeCleanupCommandPreview(
                    argv=("git", "worktree", "remove", worktree_path),
                    cwd=repository_cwd,
                    command_kind="git_worktree_remove",
                    execution_enabled=False,
                )
            )
        if branch_name is not None:
            previews.append(
                WorktreeCleanupCommandPreview(
                    argv=("git", "branch", "-d", branch_name),
                    cwd=repository_cwd,
                    command_kind="git_branch_delete",
                    execution_enabled=False,
                )
            )
        return previews
