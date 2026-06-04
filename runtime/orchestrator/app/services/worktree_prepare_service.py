"""Blocked workspace prepare skeleton with read-only git preflight.

P1-D-D validates the current plan_hash, runs allowlisted read-only git
preflight, and returns a not-implemented blocked result.  It performs no write
git command, no filesystem write, no worktree/branch creation, and no
AgentSession workspace mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.worktree_prepare import WorktreeGitPreflight, WorktreePrepareResult
from app.services.worktree_git_preflight_service import WorktreeGitPreflightService
from app.services.worktree_plan_service import WorktreePlanService


@dataclass(frozen=True, slots=True)
class WorktreePrepareRequest:
    """Request to prepare a workspace from an exact dry-run plan hash."""

    agent_session_id: UUID
    plan_hash: str
    user_confirmed: bool = True


class WorktreePrepareError(ValueError):
    """Raised when the prepare skeleton cannot evaluate the request."""


class WorktreePrepareHashMismatchError(WorktreePrepareError):
    """Raised when the submitted plan hash is stale or mismatched."""


class WorktreePrepareService:
    """Validate prepare preconditions and return blocked/not_implemented."""

    def __init__(
        self,
        *,
        worktree_plan_service: WorktreePlanService,
        git_preflight_service: WorktreeGitPreflightService | None = None,
    ) -> None:
        self.worktree_plan_service = worktree_plan_service
        self.git_preflight_service = git_preflight_service or WorktreeGitPreflightService()

    def prepare_workspace(self, request: WorktreePrepareRequest) -> WorktreePrepareResult:
        """Return a blocked prepare result without executing repository writes."""

        if not request.user_confirmed:
            raise WorktreePrepareError(
                "workspace prepare requires explicit user_confirmed=true"
            )

        submitted_plan_hash = request.plan_hash.strip()
        if not submitted_plan_hash:
            raise WorktreePrepareError("plan_hash must not be blank")

        plan = self.worktree_plan_service.build_plan(
            agent_session_id=request.agent_session_id
        )
        if submitted_plan_hash != plan.plan_hash:
            raise WorktreePrepareHashMismatchError(
                "submitted plan_hash does not match current workspace plan"
            )

        blockers = [
            "workspace prepare execution is not implemented in P1-D-D",
        ]
        warnings = [
            "no write git command was executed",
            "no worktree or branch was created",
            "AgentSession workspace fields were not changed",
        ]
        git_preflight: WorktreeGitPreflight | None = None
        if not plan.safe:
            blockers.extend(plan.blockers)
        if not plan.dry_run:
            blockers.append("workspace prepare only accepts dry-run plans")
        if not plan.requires_user_confirmation:
            blockers.append("workspace prepare requires a user-confirmed plan")
        if plan.safe and plan.branch_name is not None and plan.worktree_path is not None:
            repository_workspace = (
                self.worktree_plan_service.repository_workspace_repository.get_by_project_id(
                    plan.project_id
                )
            )
            if repository_workspace is None:
                blockers.append("repository workspace is not bound for this project")
            else:
                git_preflight = self.git_preflight_service.run_preflight(
                    repository_path=repository_workspace.root_path,
                    planned_branch_name=plan.branch_name,
                    planned_worktree_path=plan.worktree_path,
                )
                if git_preflight.errors:
                    blockers.extend(git_preflight.errors)
                if git_preflight.repository_is_git_worktree is False:
                    blockers.append("repository root is not a git worktree")
                if git_preflight.repository_clean is False:
                    blockers.append("repository has uncommitted changes")
                if git_preflight.planned_branch_exists:
                    blockers.append("planned branch already exists")
                if git_preflight.planned_worktree_registered:
                    blockers.append("planned worktree path is already registered")

        return WorktreePrepareResult.blocked_from_plan(
            plan=plan,
            submitted_plan_hash=submitted_plan_hash,
            blockers=blockers,
            warnings=warnings,
            git_preflight=git_preflight,
        )
