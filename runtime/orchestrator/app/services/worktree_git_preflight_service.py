"""Read-only git preflight for future workspace prepare execution."""

from __future__ import annotations

from pathlib import Path
import shlex

from app.domain.worktree_prepare import WorktreeGitPreflight
from app.services.worktree_command_runner import (
    WorktreeCommandResult,
    WorktreeCommandRunner,
    WorktreeCommandSpec,
)


class WorktreeGitPreflightService:
    """Run only allowlisted read-only git commands and summarize repository state."""

    def __init__(self, *, command_runner: WorktreeCommandRunner | None = None) -> None:
        self.command_runner = command_runner or WorktreeCommandRunner()

    def run_preflight(
        self,
        *,
        repository_path: str,
        planned_branch_name: str,
        planned_worktree_path: str,
    ) -> WorktreeGitPreflight:
        """Read current repository status without mutating refs, branches, or worktrees."""

        specs = [
            self.command_runner.git_rev_parse(
                repository_path=repository_path,
                ref="HEAD",
            ),
            self.command_runner.git_status_porcelain(repository_path=repository_path),
            self.command_runner.git_worktree_list(repository_path=repository_path),
            self.command_runner.git_branch_list(
                repository_path=repository_path,
                pattern=planned_branch_name,
            ),
        ]
        results = [self.command_runner.run(spec) for spec in specs]
        errors = self._collect_errors(results)
        status_result = results[1]
        worktree_result = results[2]
        branch_result = results[3]
        registered_worktree_paths = self._parse_worktree_paths(worktree_result.stdout)
        planned_worktree_registered = (
            str(Path(planned_worktree_path).expanduser()) in registered_worktree_paths
        )

        warnings: list[str] = []
        repository_clean = None
        if status_result.return_code == 0:
            repository_clean = status_result.stdout.strip() == ""
            if not repository_clean:
                warnings.append("repository has uncommitted changes")

        planned_branch_exists = None
        if branch_result.return_code == 0:
            planned_branch_exists = bool(branch_result.stdout.strip())
            if planned_branch_exists:
                warnings.append("planned branch already exists")
        if planned_worktree_registered:
            warnings.append("planned worktree path is already registered")

        return WorktreeGitPreflight(
            preflight_status="failed" if errors else "passed",
            commands_run=[self._format_command(spec) for spec in specs],
            repository_head_sha=(
                results[0].stdout.strip() if results[0].return_code == 0 else None
            ),
            repository_clean=repository_clean,
            planned_branch_exists=planned_branch_exists,
            planned_worktree_registered=planned_worktree_registered,
            registered_worktree_paths=registered_worktree_paths,
            errors=errors,
            warnings=warnings,
        )

    @staticmethod
    def _collect_errors(results: list[WorktreeCommandResult]) -> list[str]:
        """Collect command failures without exposing huge stderr payloads."""

        errors: list[str] = []
        for result in results:
            if result.return_code == 0:
                continue
            command = WorktreeGitPreflightService._format_command(result.spec)
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
