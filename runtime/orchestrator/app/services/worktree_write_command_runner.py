"""Guarded write git command boundary for worktree creation."""

from __future__ import annotations

from pathlib import Path
import subprocess

from app.domain.worktree_create import WorktreeWriteCommandPreview
from app.services.worktree_command_runner import WorktreeCommandResult


class WorktreeWriteCommandRunner:
    """Build and execute the single allowlisted mutating worktree command."""

    def __init__(self, *, default_timeout_seconds: int = 120) -> None:
        if default_timeout_seconds <= 0:
            raise ValueError("default_timeout_seconds must be positive")
        self.default_timeout_seconds = default_timeout_seconds

    def git_worktree_add_new_branch(
        self,
        *,
        repository_path: str,
        worktree_path: str,
        branch_name: str,
        base_ref: str,
    ) -> WorktreeWriteCommandPreview:
        """Build the atomic command: git worktree add -b <branch> <path> <base>."""

        return self._preview(
            cwd=repository_path,
            argv=(
                "git",
                "worktree",
                "add",
                "-b",
                branch_name,
                worktree_path,
                base_ref,
            ),
            command_kind="git_worktree_add_new_branch",
        )

    def run(self, preview: WorktreeWriteCommandPreview) -> WorktreeCommandResult:
        """Execute one allowlisted mutating worktree command."""

        self._ensure_write_allowlisted(preview)
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
                stderr=exc.stderr or "git write command timed out",
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
    ) -> WorktreeWriteCommandPreview:
        """Build one disabled write command preview with minimal validation."""

        normalized_cwd = str(Path(cwd).expanduser())
        if not normalized_cwd.strip():
            raise ValueError("cwd must not be blank")
        if not all(part.strip() for part in argv):
            raise ValueError("argv parts must not be blank")
        return WorktreeWriteCommandPreview(
            argv=argv,
            cwd=normalized_cwd,
            timeout_seconds=self.default_timeout_seconds,
            mutates_repository=True,
            command_kind=command_kind,
            execution_enabled=True,
        )

    @staticmethod
    def _ensure_write_allowlisted(preview: WorktreeWriteCommandPreview) -> None:
        """Reject arbitrary mutating commands before subprocess execution."""

        argv = preview.argv
        if not preview.execution_enabled:
            raise ValueError("write command execution is disabled")
        if not preview.mutates_repository:
            raise ValueError("write command must be marked as mutating")
        if preview.command_kind != "git_worktree_add_new_branch":
            raise ValueError("write command kind is not allowlisted")
        if len(argv) != 7:
            raise ValueError("git worktree add command shape is invalid")
        if argv[:4] != ("git", "worktree", "add", "-b"):
            raise ValueError("git write command is not allowlisted")
        branch_name = argv[4]
        worktree_path = Path(argv[5]).expanduser()
        base_ref = argv[6]
        if branch_name.startswith("-"):
            raise ValueError("branch name must not start with '-'")
        if not worktree_path.is_absolute():
            raise ValueError("worktree path must be absolute")
        if base_ref.startswith("-"):
            raise ValueError("base ref must not start with '-'")
