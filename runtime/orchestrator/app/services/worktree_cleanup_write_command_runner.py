"""Guarded write git command boundary for worktree cleanup."""

from __future__ import annotations

from pathlib import Path
import subprocess

from app.domain.worktree_cleanup import WorktreeCleanupCommandPreview
from app.services.worktree_command_runner import WorktreeCommandResult


class WorktreeCleanupWriteCommandRunner:
    """Build and execute only the minimal allowed cleanup write command."""

    def __init__(self, *, default_timeout_seconds: int = 120) -> None:
        if default_timeout_seconds <= 0:
            raise ValueError("default_timeout_seconds must be positive")
        self.default_timeout_seconds = default_timeout_seconds

    def git_worktree_remove(
        self,
        *,
        repository_path: str,
        worktree_path: str,
    ) -> WorktreeCleanupCommandPreview:
        """Build the only P1-E-C mutating command: git worktree remove <path>."""

        return self._preview(
            cwd=repository_path,
            argv=("git", "worktree", "remove", worktree_path),
            command_kind="git_worktree_remove",
        )

    def run(self, preview: WorktreeCleanupCommandPreview) -> WorktreeCommandResult:
        """Execute one allowlisted worktree cleanup command."""

        self._ensure_cleanup_allowlisted(preview)
        try:
            completed = subprocess.run(
                preview.argv,
                cwd=preview.cwd,
                capture_output=True,
                text=True,
                timeout=preview.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return WorktreeCommandResult(
                spec=preview,
                return_code=124,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "git cleanup command timed out",
                timed_out=True,
            )
        return WorktreeCommandResult(
            spec=preview,
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def _preview(
        self,
        *,
        cwd: str,
        argv: tuple[str, ...],
        command_kind: str,
    ) -> WorktreeCleanupCommandPreview:
        """Build one enabled cleanup command preview with minimal validation."""

        normalized_cwd = str(Path(cwd).expanduser())
        if not normalized_cwd.strip():
            raise ValueError("cwd must not be blank")
        if not all(part.strip() for part in argv):
            raise ValueError("argv parts must not be blank")
        return WorktreeCleanupCommandPreview(
            argv=argv,
            cwd=normalized_cwd,
            timeout_seconds=self.default_timeout_seconds,
            mutates_repository=True,
            command_kind=command_kind,
            execution_enabled=True,
        )

    @staticmethod
    def _ensure_cleanup_allowlisted(preview: WorktreeCleanupCommandPreview) -> None:
        """Reject arbitrary cleanup commands before subprocess execution."""

        argv = preview.argv
        if not preview.execution_enabled:
            raise ValueError("cleanup command execution is disabled")
        if not preview.mutates_repository:
            raise ValueError("cleanup command must be marked as mutating")
        if preview.command_kind != "git_worktree_remove":
            raise ValueError("cleanup command kind is not allowlisted")
        if len(argv) != 4:
            raise ValueError("git worktree remove command shape is invalid")
        if argv[:3] != ("git", "worktree", "remove"):
            raise ValueError("git cleanup command is not allowlisted")
        worktree_path = Path(argv[3]).expanduser()
        if not worktree_path.is_absolute():
            raise ValueError("worktree path must be absolute")
