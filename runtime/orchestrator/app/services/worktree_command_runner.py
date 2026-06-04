"""Deny-by-default read-only worktree git command allowlist.

The runner executes only explicitly allowlisted read-only git commands.  It
never exposes worktree/branch creation or deletion commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass(frozen=True, slots=True)
class WorktreeCommandSpec:
    """Immutable preview of one allowlisted git command."""

    argv: tuple[str, ...]
    cwd: str
    timeout_seconds: int
    mutates_repository: bool


@dataclass(frozen=True, slots=True)
class WorktreeCommandResult:
    """Captured result from one allowlisted read-only git command."""

    spec: WorktreeCommandSpec
    return_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class WorktreeCommandRunner:
    """Deny-by-default command builder for read-only worktree checks.

    The class exposes named methods only; it does not accept arbitrary command
    strings.  P1-D-D permits execution of these read-only commands for
    preflight, while still forbidding mutating command specs.
    """

    def __init__(self, *, default_timeout_seconds: int = 120) -> None:
        if default_timeout_seconds <= 0:
            raise ValueError("default_timeout_seconds must be positive")
        self.default_timeout_seconds = default_timeout_seconds

    def git_rev_parse(self, *, repository_path: str, ref: str) -> WorktreeCommandSpec:
        """Allowlisted future command: git rev-parse <ref>."""

        return self._spec(
            cwd=repository_path,
            argv=("git", "rev-parse", ref),
            mutates_repository=False,
        )

    def run(self, spec: WorktreeCommandSpec) -> WorktreeCommandResult:
        """Execute one allowlisted read-only git command."""

        self._ensure_read_only_allowlisted(spec)
        try:
            completed = subprocess.run(
                spec.argv,
                cwd=spec.cwd,
                capture_output=True,
                text=True,
                timeout=spec.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return WorktreeCommandResult(
                spec=spec,
                return_code=124,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "git command timed out",
                timed_out=True,
            )
        return WorktreeCommandResult(
            spec=spec,
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
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

    @staticmethod
    def _ensure_read_only_allowlisted(spec: WorktreeCommandSpec) -> None:
        """Reject arbitrary or mutating command specs."""

        if spec.mutates_repository:
            raise ValueError("mutating git command specs are not allowed")
        argv = spec.argv
        if argv == ("git", "rev-parse", "HEAD"):
            return
        if argv == ("git", "status", "--porcelain"):
            return
        if argv == ("git", "worktree", "list", "--porcelain"):
            return
        if len(argv) == 4 and argv[:3] == ("git", "branch", "--list"):
            return
        raise ValueError(f"git command is not allowlisted: {' '.join(argv)}")
