"""Blocked workspace create skeleton.

P1-D-E-A validates the current plan hash and returns a disabled write-command
preview.  It performs no git execution, no worktree/branch creation, no
filesystem write, and no AgentSession workspace mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.worktree_create import WorktreeCreateResult, WorktreeWriteCommandPreview
from app.services.worktree_plan_service import WorktreePlanService
from app.services.worktree_write_command_runner import WorktreeWriteCommandRunner


@dataclass(frozen=True, slots=True)
class WorktreeCreateRequest:
    """Request to create a workspace from an exact dry-run plan hash."""

    agent_session_id: UUID
    plan_hash: str
    user_confirmed: bool = True


class WorktreeCreateError(ValueError):
    """Raised when the blocked create skeleton cannot evaluate the request."""


class WorktreeCreateHashMismatchError(WorktreeCreateError):
    """Raised when the submitted plan hash is stale or mismatched."""


class WorktreeCreateService:
    """Validate create preconditions and return blocked/not_implemented."""

    def __init__(
        self,
        *,
        worktree_plan_service: WorktreePlanService,
        write_command_runner: WorktreeWriteCommandRunner | None = None,
    ) -> None:
        self.worktree_plan_service = worktree_plan_service
        self.write_command_runner = write_command_runner or WorktreeWriteCommandRunner()

    def create_workspace(self, request: WorktreeCreateRequest) -> WorktreeCreateResult:
        """Return a blocked create result without executing repository writes."""

        if not request.user_confirmed:
            raise WorktreeCreateError(
                "workspace create requires explicit user_confirmed=true"
            )

        submitted_plan_hash = request.plan_hash.strip()
        if not submitted_plan_hash:
            raise WorktreeCreateError("plan_hash must not be blank")

        plan = self.worktree_plan_service.build_plan(
            agent_session_id=request.agent_session_id
        )
        if submitted_plan_hash != plan.plan_hash:
            raise WorktreeCreateHashMismatchError(
                "submitted plan_hash does not match current workspace plan"
            )

        blockers = [
            "workspace create execution is not implemented in P1-D-E-A",
        ]
        warnings = [
            "write git command preview was generated but not executed",
            "no worktree or branch was created",
            "AgentSession workspace fields were not changed",
        ]
        write_command_preview: list[WorktreeWriteCommandPreview] = []

        if not plan.safe:
            blockers.extend(plan.blockers)
        if not plan.dry_run:
            blockers.append("workspace create only accepts dry-run plans")
        if not plan.requires_user_confirmation:
            blockers.append("workspace create requires a user-confirmed plan")

        if plan.safe and plan.branch_name is not None and plan.worktree_path is not None:
            repository_workspace = (
                self.worktree_plan_service.repository_workspace_repository.get_by_project_id(
                    plan.project_id
                )
            )
            if repository_workspace is None:
                blockers.append("repository workspace is not bound for this project")
            else:
                write_command_preview.append(
                    self.write_command_runner.git_worktree_add_new_branch(
                        repository_path=repository_workspace.root_path,
                        worktree_path=plan.worktree_path,
                        branch_name=plan.branch_name,
                        base_ref=f"origin/{plan.base_branch or 'main'}",
                    )
                )

        return WorktreeCreateResult.blocked_from_plan(
            plan=plan,
            submitted_plan_hash=submitted_plan_hash,
            blockers=blockers,
            warnings=warnings,
            write_command_preview=write_command_preview,
        )
