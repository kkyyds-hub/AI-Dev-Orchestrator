"""Repository branch-session helpers for V4 Day03."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from uuid import UUID

from app.domain._base import utc_now
from app.domain.change_session import (
    ChangeSession,
    ChangeSessionDirtyFile,
    ChangeSessionDirtyFileScope,
    ChangeSessionGuardStatus,
    ChangeSessionWorkspaceStatus,
)
from app.repositories.change_session_repository import ChangeSessionRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)


GIT_COMMAND_TIMEOUT_SECONDS = 10
MAX_CHANGE_SESSION_DIRTY_FILE_PREVIEW = 20


class BranchSessionError(ValueError):
    """Base error raised by the Day03 branch-session service."""


class BranchSessionProjectNotFoundError(BranchSessionError):
    """Raised when one project is missing during Day03 session capture."""


class BranchSessionWorkspaceNotFoundError(BranchSessionError):
    """Raised when one project has no bound repository workspace."""


class BranchSessionInspectionError(BranchSessionError):
    """Raised when the bound repository can no longer be inspected as a Git repo."""


@dataclass(slots=True)
class _GitRepositoryState:
    """In-memory Git state captured before persisting the Day03 session snapshot."""

    current_branch: str
    head_ref: str
    head_commit_sha: str | None
    baseline_ref: str
    baseline_commit_sha: str | None
    workspace_status: ChangeSessionWorkspaceStatus
    guard_status: ChangeSessionGuardStatus
    guard_summary: str
    blocking_reasons: list[str]
    dirty_file_count: int
    dirty_files_truncated: bool
    dirty_files: list[ChangeSessionDirtyFile]


class BranchSessionService:
    """Capture and read one project's current Day03 change-session snapshot."""

    def __init__(
        self,
        *,
        project_repository: ProjectRepository,
        repository_workspace_repository: RepositoryWorkspaceRepository,
        change_session_repository: ChangeSessionRepository,
    ) -> None:
        self.project_repository = project_repository
        self.repository_workspace_repository = repository_workspace_repository
        self.change_session_repository = change_session_repository

    def capture_project_change_session(self, project_id: UUID) -> ChangeSession:
        """Capture or refresh one project's current active change-session snapshot."""

        if not self.project_repository.exists(project_id):
            raise BranchSessionProjectNotFoundError(f"Project not found: {project_id}")

        workspace = self.repository_workspace_repository.get_by_project_id(project_id)
        if workspace is None:
            raise BranchSessionWorkspaceNotFoundError(
                f"Repository workspace not found for project: {project_id}"
            )

        repository_root_path = Path(workspace.root_path)
        git_state = self._inspect_git_repository(
            repository_root_path,
            baseline_branch=workspace.default_base_branch,
        )

        existing_session = self.change_session_repository.get_by_project_id(project_id)
        now = utc_now()
        change_session_payload = dict(
            project_id=project_id,
            repository_workspace_id=workspace.id,
            repository_root_path=workspace.root_path,
            current_branch=git_state.current_branch,
            head_ref=git_state.head_ref,
            head_commit_sha=git_state.head_commit_sha,
            baseline_branch=workspace.default_base_branch,
            baseline_ref=git_state.baseline_ref,
            baseline_commit_sha=git_state.baseline_commit_sha,
            workspace_status=git_state.workspace_status,
            guard_status=git_state.guard_status,
            guard_summary=git_state.guard_summary,
            blocking_reasons=git_state.blocking_reasons,
            dirty_file_count=git_state.dirty_file_count,
            dirty_files_truncated=git_state.dirty_files_truncated,
            dirty_files=git_state.dirty_files,
            created_at=(
                existing_session.created_at
                if (
                    existing_session is not None
                    and existing_session.repository_workspace_id == workspace.id
                    and existing_session.repository_root_path == workspace.root_path
                )
                else now
            ),
            updated_at=now,
        )
        if existing_session is not None:
            change_session_payload["id"] = existing_session.id

        change_session = ChangeSession(**change_session_payload)
        return self.change_session_repository.upsert(change_session)

    def get_active_project_change_session(self, project_id: UUID) -> ChangeSession | None:
        """Return one project's active Day03 change-session snapshot, if present."""

        if not self.project_repository.exists(project_id):
            raise BranchSessionProjectNotFoundError(f"Project not found: {project_id}")

        workspace = self.repository_workspace_repository.get_by_project_id(project_id)
        if workspace is None:
            raise BranchSessionWorkspaceNotFoundError(
                f"Repository workspace not found for project: {project_id}"
            )

        change_session = self.change_session_repository.get_by_project_id(project_id)
        if change_session is None:
            return None

        if change_session.repository_workspace_id != workspace.id:
            return None
        if change_session.repository_root_path != workspace.root_path:
            return None

        return change_session

    def _inspect_git_repository(
        self,
        repository_root_path: Path,
        *,
        baseline_branch: str,
    ) -> _GitRepositoryState:
        """Read the minimal Day03 Git state needed for one change-session snapshot."""

        if not repository_root_path.exists():
            raise BranchSessionInspectionError(
                "Repository root_path does not exist during Day03 session capture."
            )
        if not repository_root_path.is_dir():
            raise BranchSessionInspectionError(
                "Repository root_path must point to one local directory during Day03 session capture."
            )
        if not (repository_root_path / ".git").exists():
            raise BranchSessionInspectionError(
                "Repository root_path is no longer a local Git repository root."
            )

        current_branch = self._run_git(
            repository_root_path,
            "symbolic-ref",
            "--quiet",
            "--short",
            "HEAD",
            check=False,
        ) or "(detached)"
        head_ref = self._run_git(
            repository_root_path,
            "symbolic-ref",
            "--quiet",
            "HEAD",
            check=False,
        ) or "HEAD"
        head_commit_sha = self._run_git(
            repository_root_path,
            "rev-parse",
            "HEAD",
            check=False,
        ) or None
        baseline_ref, baseline_commit_sha = self._resolve_baseline_ref(
            repository_root_path,
            baseline_branch=baseline_branch,
        )
        dirty_file_count, dirty_files_truncated, dirty_files = self._list_dirty_files(
            repository_root_path
        )
        workspace_status = (
            ChangeSessionWorkspaceStatus.DIRTY
            if dirty_file_count > 0
            else ChangeSessionWorkspaceStatus.CLEAN
        )
        blocking_reasons = self._build_blocking_reasons(
            current_branch=current_branch,
            head_commit_sha=head_commit_sha,
            baseline_branch=baseline_branch,
            baseline_commit_sha=baseline_commit_sha,
            workspace_status=workspace_status,
            dirty_file_count=dirty_file_count,
        )
        guard_status = (
            ChangeSessionGuardStatus.BLOCKED
            if blocking_reasons
            else ChangeSessionGuardStatus.READY
        )
        guard_summary = (
            blocking_reasons[0]
            if blocking_reasons
            else "当前仓库状态满足 Day03 只读会话基线，可供后续变更规划复用。"
        )
        return _GitRepositoryState(
            current_branch=current_branch,
            head_ref=head_ref,
            head_commit_sha=head_commit_sha,
            baseline_ref=baseline_ref,
            baseline_commit_sha=baseline_commit_sha,
            workspace_status=workspace_status,
            guard_status=guard_status,
            guard_summary=guard_summary,
            blocking_reasons=blocking_reasons,
            dirty_file_count=dirty_file_count,
            dirty_files_truncated=dirty_files_truncated,
            dirty_files=dirty_files,
        )

    @staticmethod
    def _build_blocking_reasons(
        *,
        current_branch: str,
        head_commit_sha: str | None,
        baseline_branch: str,
        baseline_commit_sha: str | None,
        workspace_status: ChangeSessionWorkspaceStatus,
        dirty_file_count: int,
    ) -> list[str]:
        """Translate raw Git state into the Day03 guard-blocking reasons."""

        blocking_reasons: list[str] = []

        if current_branch == "(detached)":
            blocking_reasons.append(
                "当前仓库处于 detached HEAD，Day03 只记录状态，不直接进入后续变更计划。"
            )
        if head_commit_sha is None:
            blocking_reasons.append(
                "当前 HEAD 还没有可解析的提交引用，无法形成稳定的会话基线。"
            )
        if baseline_commit_sha is None:
            blocking_reasons.append(
                f"默认基线分支 `{baseline_branch}` 当前无法解析为提交引用。"
            )
        if workspace_status == ChangeSessionWorkspaceStatus.DIRTY:
            blocking_reasons.append(
                f"工作区存在 {dirty_file_count} 个未提交改动/未跟踪文件；Day03 只记录风险，不自动清理。"
            )

        return blocking_reasons

    def _resolve_baseline_ref(
        self,
        repository_root_path: Path,
        *,
        baseline_branch: str,
    ) -> tuple[str, str | None]:
        """Resolve one configured baseline branch into the closest available Git ref."""

        for candidate_ref in (
            f"refs/heads/{baseline_branch}",
            f"refs/remotes/origin/{baseline_branch}",
        ):
            commit_sha = self._run_git(
                repository_root_path,
                "rev-parse",
                "--verify",
                f"{candidate_ref}^{{commit}}",
                check=False,
            )
            if commit_sha:
                return candidate_ref, commit_sha

        return f"refs/heads/{baseline_branch}", None

    def _list_dirty_files(
        self,
        repository_root_path: Path,
    ) -> tuple[int, bool, list[ChangeSessionDirtyFile]]:
        """Read one bounded dirty-file preview from `git status --porcelain`."""

        raw_output = self._run_git(
            repository_root_path,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            check=True,
        )
        if not raw_output:
            return 0, False, []

        dirty_files: list[ChangeSessionDirtyFile] = []
        dirty_file_count = 0

        for line in raw_output.splitlines():
            if len(line) < 3:
                continue

            dirty_file_count += 1
            git_status = line[:2]
            raw_path = line[3:].strip()
            if " -> " in raw_path and git_status[0] in {"R", "C"}:
                raw_path = raw_path.split(" -> ", 1)[1]

            if len(dirty_files) >= MAX_CHANGE_SESSION_DIRTY_FILE_PREVIEW:
                continue

            dirty_files.append(
                ChangeSessionDirtyFile(
                    path=raw_path,
                    git_status=git_status,
                    change_scope=self._infer_dirty_file_scope(git_status),
                )
            )

        return (
            dirty_file_count,
            dirty_file_count > len(dirty_files),
            dirty_files,
        )

    @staticmethod
    def _infer_dirty_file_scope(git_status: str) -> ChangeSessionDirtyFileScope:
        """Reduce one porcelain status pair into the Day03 preview scope enum."""

        if git_status == "??":
            return ChangeSessionDirtyFileScope.UNTRACKED

        index_status = git_status[0]
        worktree_status = git_status[1]
        if index_status != " " and worktree_status != " ":
            return ChangeSessionDirtyFileScope.MIXED
        if index_status != " ":
            return ChangeSessionDirtyFileScope.STAGED

        return ChangeSessionDirtyFileScope.UNSTAGED

    @staticmethod
    def _run_git(
        repository_root_path: Path,
        *args: str,
        check: bool,
    ) -> str:
        """Run one read-only Git command and normalize its text output."""

        git_environment = os.environ.copy()
        git_environment.setdefault("GIT_OPTIONAL_LOCKS", "0")

        try:
            completed_process = subprocess.run(
                ["git", *args],
                cwd=repository_root_path,
                env=git_environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=GIT_COMMAND_TIMEOUT_SECONDS,
                check=False,
            )
        except FileNotFoundError as exc:  # pragma: no cover - environment-specific
            raise BranchSessionInspectionError("Git executable is not available.") from exc
        except OSError as exc:
            raise BranchSessionInspectionError(
                f"Unable to inspect the bound repository path: {repository_root_path}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise BranchSessionInspectionError(
                f"Timed out while reading Git state for repository: {repository_root_path}"
            ) from exc

        output = (completed_process.stdout or "").rstrip("\r\n")
        if completed_process.returncode == 0:
            return output
        if not check:
            return ""

        error_message = (
            (completed_process.stderr or "").strip()
            or output
            or f"Git command failed: git {' '.join(args)}"
        )
        raise BranchSessionInspectionError(error_message)
