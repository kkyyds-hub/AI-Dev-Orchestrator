"""Blocked workspace prepare skeleton.

P1-D-C only validates the current plan_hash and returns a not-implemented
blocked result.  It performs no git command, no filesystem write, no
worktree/branch creation, and no AgentSession workspace mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.worktree_prepare import WorktreePrepareResult
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

    def __init__(self, *, worktree_plan_service: WorktreePlanService) -> None:
        self.worktree_plan_service = worktree_plan_service

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
            "workspace prepare execution is not implemented in P1-D-C",
        ]
        warnings = [
            "no git command was executed",
            "no worktree or branch was created",
            "AgentSession workspace fields were not changed",
        ]
        if not plan.safe:
            blockers.extend(plan.blockers)
        if not plan.dry_run:
            blockers.append("workspace prepare only accepts dry-run plans")
        if not plan.requires_user_confirmation:
            blockers.append("workspace prepare requires a user-confirmed plan")

        return WorktreePrepareResult.blocked_from_plan(
            plan=plan,
            submitted_plan_hash=submitted_plan_hash,
            blockers=blockers,
            warnings=warnings,
        )
