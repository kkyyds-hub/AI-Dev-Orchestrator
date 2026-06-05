"""Blocked workspace cleanup skeleton with read-only preflight.

P1-E-B validates the current plan_hash, runs allowlisted read-only cleanup
preflight, and returns disabled cleanup command previews.  It performs no
write git command, no filesystem deletion, no branch removal, no worktree
removal, and no AgentSession workspace mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex
from uuid import UUID

from app.domain.worktree_cleanup import (
    WorktreeCleanupCommandPreview,
    WorktreeCleanupPreflight,
    WorktreeCleanupResult,
)
from app.services.worktree_command_runner import (
    WorktreeCommandResult,
    WorktreeCommandRunner,
    WorktreeCommandSpec,
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


class WorktreeCleanupPreflightService:
    """Run only read-only checks for cleanup eligibility and safety."""

    def __init__(
        self,
        *,
        command_runner: WorktreeCommandRunner | None = None,
    ) -> None:
        self.command_runner = command_runner or WorktreeCommandRunner()

    def run_preflight(
        self,
        *,
        repository_path: str,
        worktree_path: str,
        branch_name: str,
        allowed_workspace_root: str,
    ) -> WorktreeCleanupPreflight:
        """Inspect cleanup target state without removing worktree, refs, or files."""

        path_result = self._inspect_path(
            worktree_path=worktree_path,
            allowed_workspace_root=allowed_workspace_root,
        )
        specs = [
            self.command_runner.git_rev_parse_is_inside_work_tree(
                repository_path=repository_path,
            ),
            self.command_runner.git_worktree_list(repository_path=repository_path),
            self.command_runner.git_branch_list(
                repository_path=repository_path,
                pattern=branch_name,
            ),
        ]
        should_check_worktree_clean = (
            path_result.worktree_path_exists
            and path_result.worktree_path_is_directory
            and path_result.worktree_path_safe
        )
        if should_check_worktree_clean:
            specs.insert(
                2,
                self.command_runner.git_status_porcelain(repository_path=worktree_path),
            )
        results = [self.command_runner.run(spec) for spec in specs]
        errors = self._collect_errors(results)
        warnings = list(path_result.warnings)
        errors.extend(path_result.errors)

        inside_work_tree_result = results[0]
        worktree_list_result = results[1]
        status_result = results[2] if should_check_worktree_clean else None
        branch_result = results[3] if should_check_worktree_clean else results[2]
        registered_worktree_paths = self._parse_worktree_paths(
            worktree_list_result.stdout
        )
        normalized_worktree_path = str(Path(worktree_path).expanduser())
        worktree_registered = normalized_worktree_path in registered_worktree_paths
        if not worktree_registered:
            warnings.append("AgentSession worktree path is not registered")

        worktree_clean = None
        if status_result is not None and status_result.return_code == 0:
            worktree_clean = status_result.stdout.strip() == ""
            if not worktree_clean:
                warnings.append("AgentSession worktree has uncommitted changes")
        if status_result is None:
            warnings.append(
                "AgentSession worktree clean check was skipped because path is missing or unsafe"
            )

        branch_exists = None
        if branch_result.return_code == 0:
            branch_exists = bool(branch_result.stdout.strip())
            if not branch_exists:
                warnings.append("AgentSession branch was not found by read-only check")

        if path_result.worktree_path_exists is False:
            warnings.append("AgentSession worktree path does not exist")
        if path_result.worktree_path_safe is False:
            warnings.append("AgentSession worktree path is outside allowed workspace root")

        return WorktreeCleanupPreflight(
            preflight_status="failed" if errors else "passed",
            commands_run=[self._format_command(spec) for spec in specs],
            worktree_path_exists=path_result.worktree_path_exists,
            worktree_path_is_directory=path_result.worktree_path_is_directory,
            worktree_path_safe=path_result.worktree_path_safe,
            worktree_registered=worktree_registered,
            worktree_clean=worktree_clean,
            repository_is_git_worktree=(
                inside_work_tree_result.stdout.strip().lower() == "true"
                if inside_work_tree_result.return_code == 0
                else None
            ),
            registered_worktree_paths=registered_worktree_paths,
            errors=errors,
            warnings=warnings,
        )

    @staticmethod
    def _inspect_path(
        *,
        worktree_path: str,
        allowed_workspace_root: str,
    ) -> "_CleanupPathInspection":
        """Check cleanup target path safety with read-only pathlib calls."""

        errors: list[str] = []
        warnings: list[str] = []
        target_path = Path(worktree_path).expanduser()
        allowed_root_path = Path(allowed_workspace_root).expanduser()
        if not target_path.is_absolute():
            errors.append("AgentSession worktree path must be absolute")
        if not allowed_root_path.is_absolute():
            errors.append("allowed workspace root must be absolute")
        if errors:
            return _CleanupPathInspection(
                worktree_path_exists=target_path.exists(),
                worktree_path_is_directory=(
                    target_path.is_dir() if target_path.exists() else None
                ),
                worktree_path_safe=False,
                errors=errors,
                warnings=warnings,
            )

        target_resolved = target_path.resolve(strict=False)
        allowed_resolved = allowed_root_path.resolve(strict=False)
        worktree_path_safe = WorktreeCleanupPreflightService._is_within(
            target_resolved,
            allowed_resolved,
        )
        return _CleanupPathInspection(
            worktree_path_exists=target_path.exists(),
            worktree_path_is_directory=(
                target_path.is_dir() if target_path.exists() else None
            ),
            worktree_path_safe=worktree_path_safe,
            errors=errors,
            warnings=warnings,
        )

    @staticmethod
    def _collect_errors(results: list[WorktreeCommandResult]) -> list[str]:
        """Collect read-only command failures without exposing huge stderr payloads."""

        errors: list[str] = []
        for result in results:
            if result.return_code == 0:
                continue
            command = WorktreeCleanupPreflightService._format_command(result.spec)
            stderr = result.stderr.strip() or "command failed"
            errors.append(f"{command}: {stderr[:500]}")
        return errors

    @staticmethod
    def _parse_worktree_paths(stdout: str) -> list[str]:
        """Parse `git worktree list --porcelain` worktree paths."""

        paths: list[str] = []
        for line in stdout.splitlines():
            if not line.startswith("worktree "):
                continue
            path = line.removeprefix("worktree ").strip()
            if path:
                paths.append(path)
        return paths

    @staticmethod
    def _format_command(spec: WorktreeCommandSpec) -> str:
        """Return a shell-escaped command string for observability only."""

        return " ".join(shlex.quote(part) for part in spec.argv)

    @staticmethod
    def _is_within(child: Path, parent: Path) -> bool:
        """Return True when ``child`` is inside ``parent`` or equal to it."""

        try:
            child.relative_to(parent)
        except ValueError:
            return False
        return True


@dataclass(frozen=True, slots=True)
class _CleanupPathInspection:
    """Read-only filesystem inspection of the cleanup target path."""

    worktree_path_exists: bool
    worktree_path_is_directory: bool | None
    worktree_path_safe: bool
    errors: list[str]
    warnings: list[str]


class WorktreeCleanupService:
    """Validate cleanup preconditions and return blocked command previews."""

    def __init__(
        self,
        *,
        worktree_plan_service: WorktreePlanService,
        cleanup_preflight_service: WorktreeCleanupPreflightService | None = None,
    ) -> None:
        self.worktree_plan_service = worktree_plan_service
        self.cleanup_preflight_service = (
            cleanup_preflight_service or WorktreeCleanupPreflightService()
        )

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
        cleanup_preflight = None
        if session.workspace_path is not None and session.branch_name is not None:
            repository_workspace = (
                self.worktree_plan_service.repository_workspace_repository.get_by_project_id(
                    plan.project_id
                )
            )
            if repository_workspace is None:
                blockers.append("repository workspace is not bound for this project")
            else:
                cleanup_preflight = self.cleanup_preflight_service.run_preflight(
                    repository_path=repository_workspace.root_path,
                    worktree_path=worktree_path,
                    branch_name=branch_name,
                    allowed_workspace_root=repository_workspace.allowed_workspace_root,
                )
                blockers.extend(self._unsafe_preflight_blockers(cleanup_preflight))

        return WorktreeCleanupResult.blocked_from_plan(
            plan=plan,
            submitted_plan_hash=submitted_plan_hash,
            worktree_path=worktree_path,
            branch_name=branch_name,
            blockers=blockers,
            warnings=warnings,
            cleanup_preflight=cleanup_preflight,
            cleanup_command_preview=cleanup_command_preview,
        )

    @staticmethod
    def _unsafe_preflight_blockers(
        cleanup_preflight: WorktreeCleanupPreflight,
    ) -> list[str]:
        """Translate read-only cleanup preflight into cleanup blockers."""

        blockers: list[str] = []
        if cleanup_preflight.errors:
            blockers.extend(cleanup_preflight.errors)
        if cleanup_preflight.repository_is_git_worktree is False:
            blockers.append("repository root is not a git worktree")
        if cleanup_preflight.worktree_path_exists is False:
            blockers.append("AgentSession worktree path does not exist")
        if cleanup_preflight.worktree_path_is_directory is False:
            blockers.append("AgentSession worktree path is not a directory")
        if cleanup_preflight.worktree_path_safe is False:
            blockers.append("AgentSession worktree path is outside allowed workspace root")
        if cleanup_preflight.worktree_registered is False:
            blockers.append("AgentSession worktree path is not registered")
        if cleanup_preflight.worktree_clean is False:
            blockers.append("AgentSession worktree has uncommitted changes")
        return blockers

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
