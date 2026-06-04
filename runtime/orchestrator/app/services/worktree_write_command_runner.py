"""Write git command boundary previews for future worktree creation.

P1-D-E-A intentionally defines command shape only.  This module does not import
subprocess, expose a run method, execute git, or create worktrees/branches.
"""

from __future__ import annotations

from pathlib import Path

from app.domain.worktree_create import WorktreeWriteCommandPreview


class WorktreeWriteCommandRunner:
    """Build deny-by-default previews for future mutating worktree commands."""

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
        """Preview the future atomic command: git worktree add -b <branch> <path> <base>."""

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
            execution_enabled=False,
        )
