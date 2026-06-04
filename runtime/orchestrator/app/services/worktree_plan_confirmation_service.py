"""Confirmation skeleton for dry-run worktree plans.

P1-D-B validates a user-submitted plan_hash against the current recomputed
WorktreePlan and returns a non-persistent receipt.  It intentionally performs
no git command, no filesystem write, no worktree/branch creation, and no
AgentSession workspace mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.worktree_plan_confirmation import WorktreePlanConfirmationReceipt
from app.services.worktree_plan_service import WorktreePlanService


@dataclass(frozen=True, slots=True)
class WorktreePlanConfirmationRequest:
    """User intent to confirm one exact dry-run plan hash."""

    agent_session_id: UUID
    plan_hash: str
    user_confirmed: bool = True
    confirmed_by: str | None = None


class WorktreePlanConfirmationError(ValueError):
    """Raised when a workspace plan confirmation cannot be accepted."""


class WorktreePlanHashMismatchError(WorktreePlanConfirmationError):
    """Raised when the submitted plan hash is stale or mismatched."""


class WorktreePlanConfirmationService:
    """Validate plan-hash confirmation without executing the plan."""

    def __init__(self, *, worktree_plan_service: WorktreePlanService) -> None:
        self.worktree_plan_service = worktree_plan_service

    def confirm_plan(
        self,
        request: WorktreePlanConfirmationRequest,
    ) -> WorktreePlanConfirmationReceipt:
        """Return a receipt when the submitted hash matches the current plan."""

        if not request.user_confirmed:
            raise WorktreePlanConfirmationError(
                "workspace plan confirmation requires explicit user_confirmed=true"
            )

        submitted_plan_hash = request.plan_hash.strip()
        if not submitted_plan_hash:
            raise WorktreePlanConfirmationError("plan_hash must not be blank")

        plan = self.worktree_plan_service.build_plan(
            agent_session_id=request.agent_session_id
        )
        if not plan.safe:
            raise WorktreePlanConfirmationError(
                "workspace plan is blocked and cannot be confirmed"
            )
        if not plan.dry_run:
            raise WorktreePlanConfirmationError(
                "workspace plan confirmation only accepts dry-run plans"
            )
        if not plan.requires_user_confirmation:
            raise WorktreePlanConfirmationError(
                "workspace plan must require user confirmation"
            )
        if submitted_plan_hash != plan.plan_hash:
            raise WorktreePlanHashMismatchError(
                "submitted plan_hash does not match current workspace plan"
            )

        return WorktreePlanConfirmationReceipt.from_plan(
            plan=plan,
            confirmed_by=request.confirmed_by,
        )
