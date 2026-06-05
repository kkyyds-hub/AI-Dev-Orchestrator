"""Guarded real workspace create service."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.worktree_create import WorktreeCreateResult, WorktreeWriteCommandPreview
from app.domain.worktree_prepare import WorktreeGitPreflight
from app.domain.agent_session import WorkspaceType
from app.repositories.agent_message_repository import AgentMessageRepository
from app.services.workspace_lifecycle_audit_service import (
    WorkspaceLifecycleAuditService,
)
from app.services.worktree_git_preflight_service import WorktreeGitPreflightService
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
    """Validate create preconditions and execute a minimal real worktree create."""

    def __init__(
        self,
        *,
        worktree_plan_service: WorktreePlanService,
        git_preflight_service: WorktreeGitPreflightService | None = None,
        write_command_runner: WorktreeWriteCommandRunner | None = None,
    ) -> None:
        self.worktree_plan_service = worktree_plan_service
        self.git_preflight_service = git_preflight_service or WorktreeGitPreflightService()
        self.write_command_runner = write_command_runner or WorktreeWriteCommandRunner()

    def create_workspace(self, request: WorktreeCreateRequest) -> WorktreeCreateResult:
        """Create one per-session worktree after guarded confirmation and preflight."""

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

        blockers: list[str] = []
        warnings: list[str] = []
        write_command_preview: list[WorktreeWriteCommandPreview] = []
        git_preflight: WorktreeGitPreflight | None = None

        if not plan.safe:
            blockers.extend(plan.blockers)
        if not plan.dry_run:
            blockers.append("workspace create only accepts dry-run plans")
        if not plan.requires_user_confirmation:
            blockers.append("workspace create requires a user-confirmed plan")

        repository_workspace = None
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
                blockers.extend(self._unsafe_preflight_blockers(git_preflight))
                if git_preflight.repository_head_sha is None:
                    blockers.append("repository HEAD could not be resolved")
                write_command_preview.append(
                    self.write_command_runner.git_worktree_add_new_branch(
                        repository_path=repository_workspace.root_path,
                        worktree_path=plan.worktree_path,
                        branch_name=plan.branch_name,
                        base_ref=(
                            git_preflight.repository_head_sha
                            if git_preflight.repository_head_sha is not None
                            else f"origin/{plan.base_branch or 'main'}"
                        ),
                    )
                )

        if blockers:
            self._write_last_workspace_error(
                session_id=request.agent_session_id,
                message=self._format_workspace_error("preflight blocked", blockers),
            )
            result = WorktreeCreateResult.failed_from_plan(
                plan=plan,
                submitted_plan_hash=submitted_plan_hash,
                blocked_reason="workspace_create_preflight_blocked",
                blockers=blockers,
                warnings=warnings,
                git_preflight=git_preflight,
                write_command_preview=write_command_preview,
                attempted_write_git=False,
                wrote_agent_session_error=True,
            )
            self._record_audit_event(result)
            return result

        if (
            repository_workspace is None
            or plan.branch_name is None
            or plan.worktree_path is None
            or git_preflight is None
            or not write_command_preview
        ):
            blockers.append("workspace create command could not be prepared")
            self._write_last_workspace_error(
                session_id=request.agent_session_id,
                message=self._format_workspace_error("create setup failed", blockers),
            )
            result = WorktreeCreateResult.failed_from_plan(
                plan=plan,
                submitted_plan_hash=submitted_plan_hash,
                blocked_reason="workspace_create_setup_failed",
                blockers=blockers,
                warnings=warnings,
                git_preflight=git_preflight,
                write_command_preview=write_command_preview,
                attempted_write_git=False,
                wrote_agent_session_error=True,
            )
            self._record_audit_event(result)
            return result

        write_result = self.write_command_runner.run(write_command_preview[0])
        if write_result.return_code != 0:
            stderr = write_result.stderr.strip() or write_result.stdout.strip()
            blockers.append(f"git worktree add failed: {stderr[:500]}")
            self._write_last_workspace_error(
                session_id=request.agent_session_id,
                message=self._format_workspace_error("git worktree add failed", blockers),
            )
            result = WorktreeCreateResult.failed_from_plan(
                plan=plan,
                submitted_plan_hash=submitted_plan_hash,
                blocked_reason="workspace_create_git_write_failed",
                blockers=blockers,
                warnings=warnings,
                git_preflight=git_preflight,
                write_command_preview=write_command_preview,
                attempted_write_git=True,
                wrote_agent_session_error=True,
            )
            self._record_audit_event(result)
            return result

        self.worktree_plan_service.agent_session_repository.update_status(
            request.agent_session_id,
            branch_name=plan.branch_name,
            workspace_type=WorkspaceType.WORKTREE,
            workspace_path=plan.worktree_path,
            workspace_clean=True,
            last_workspace_error=None,
        )

        result = WorktreeCreateResult.created_from_plan(
            plan=plan,
            submitted_plan_hash=submitted_plan_hash,
            git_preflight=git_preflight,
            write_command_preview=write_command_preview,
            warnings=warnings,
        )
        self._record_audit_event(result)
        return result

    @staticmethod
    def _unsafe_preflight_blockers(
        git_preflight: WorktreeGitPreflight,
    ) -> list[str]:
        """Translate read-only git preflight into unsafe blockers."""

        blockers: list[str] = []
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
        return blockers

    def _write_last_workspace_error(self, *, session_id: UUID, message: str) -> None:
        """Persist a bounded workspace error without changing workspace success fields."""

        self.worktree_plan_service.agent_session_repository.update_status(
            session_id,
            last_workspace_error=message[:2_000],
        )

    def _record_audit_event(self, result: WorktreeCreateResult) -> None:
        """Persist the create lifecycle audit event."""

        session = self.worktree_plan_service.agent_session_repository.get_by_id(
            result.agent_session_id
        )
        if session is None:
            return
        WorkspaceLifecycleAuditService(
            AgentMessageRepository(
                self.worktree_plan_service.agent_session_repository.session
            )
        ).record_create_result(session=session, result=result)

    @staticmethod
    def _format_workspace_error(prefix: str, blockers: list[str]) -> str:
        """Build the AgentSession.last_workspace_error payload."""

        details = "; ".join(item.strip() for item in blockers if item.strip())
        return f"{prefix}: {details}" if details else prefix
