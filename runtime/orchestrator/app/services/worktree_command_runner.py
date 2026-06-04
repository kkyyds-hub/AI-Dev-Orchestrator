"""Deny-by-default worktree git command allowlist.

P1-D-A defines the command surface only.  It intentionally does not execute
git, load a process runner, create worktrees, or create branches.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WorktreeCommandSpec:
    """Immutable preview of one allowlisted git command."""

    argv: tuple[str, ...]
    cwd: str
    timeout_seconds: int
    mutates_repository: bool


class WorktreeCommandRunner:
    """Deny-by-default command builder for future worktree operations.

    The class exposes named methods only; it does not accept arbitrary command
    strings.  P1-D-A stops at command specification so no git command is run.
    """

    def __init__(self, *, default_timeout_seconds: int = 120) -> None:
        if default_timeout_seconds <= 0:
            raise ValueError("default_timeout_seconds must be positive")
        self.default_timeout_seconds = default_timeout_seconds

    def git_fetch(self, *, repository_path: str, remote: str = "origin") -> WorktreeCommandSpec:
        """Allowlisted future command: git fetch <remote>."""

        return self._spec(
            cwd=repository_path,
            argv=("git", "fetch", remote),
            mutates_repository=False,
        )

    def git_rev_parse(self, *, repository_path: str, ref: str) -> WorktreeCommandSpec:
        """Allowlisted future command: git rev-parse <ref>."""

        return self._spec(
            cwd=repository_path,
            argv=("git", "rev-parse", ref),
            mutates_repository=False,
        )

    def git_status_porcelain(self, *, repository_path: str) -> WorktreeCommandSpec:
        """Allowlisted future command: git status --porcelain."""

        return self._spec(
            cwd=repository_path,
            argv=("git", "status", "--porcelain"),
            mutates_repository=False,
        )

    def git_worktree_list(self, *, repository_path: str) -> WorktreeCommandSpec:
        """Allowlisted future command: git worktree list --porcelain."""

        return self._spec(
            cwd=repository_path,
            argv=("git", "worktree", "list", "--porcelain"),
            mutates_repository=False,
        )

    def git_branch_list(self, *, repository_path: str, pattern: str) -> WorktreeCommandSpec:
        """Allowlisted future command: git branch --list <pattern>."""

        return self._spec(
            cwd=repository_path,
            argv=("git", "branch", "--list", pattern),
            mutates_repository=False,
        )

    def git_worktree_add(
        self,
        *,
        repository_path: str,
        worktree_path: str,
        base_ref: str,
    ) -> WorktreeCommandSpec:
        """Allowlisted future command: git worktree add <path> <base-ref>."""

        return self._spec(
            cwd=repository_path,
            argv=("git", "worktree", "add", worktree_path, base_ref),
            mutates_repository=True,
        )

    def git_checkout_new_branch(
        self,
        *,
        worktree_path: str,
        branch_name: str,
    ) -> WorktreeCommandSpec:
        """Allowlisted future command: git checkout -b <branch>."""

        return self._spec(
            cwd=worktree_path,
            argv=("git", "checkout", "-b", branch_name),
            mutates_repository=True,
        )

    def git_worktree_remove(
        self,
        *,
        repository_path: str,
        worktree_path: str,
        force: bool = True,
    ) -> WorktreeCommandSpec:
        """Allowlisted future command: git worktree remove [--force] <path>."""

        argv = ("git", "worktree", "remove", "--force", worktree_path)
        if not force:
            argv = ("git", "worktree", "remove", worktree_path)
        return self._spec(
            cwd=repository_path,
            argv=argv,
            mutates_repository=True,
        )

    def git_branch_delete(
        self,
        *,
        repository_path: str,
        branch_name: str,
        force: bool = True,
    ) -> WorktreeCommandSpec:
        """Allowlisted future command: git branch -D/-d <branch>."""

        delete_flag = "-D" if force else "-d"
        return self._spec(
            cwd=repository_path,
            argv=("git", "branch", delete_flag, branch_name),
            mutates_repository=True,
        )

    def _spec(
        self,
        *,
        cwd: str,
        argv: tuple[str, ...],
        mutates_repository: bool,
    ) -> WorktreeCommandSpec:
        """Build one immutable command spec after minimal path validation."""

        normalized_cwd = str(Path(cwd).expanduser())
        if not normalized_cwd.strip():
            raise ValueError("cwd must not be blank")
        if not all(part.strip() for part in argv):
            raise ValueError("argv parts must not be blank")
        return WorktreeCommandSpec(
            argv=argv,
            cwd=normalized_cwd,
            timeout_seconds=self.default_timeout_seconds,
            mutates_repository=mutates_repository,
        )
