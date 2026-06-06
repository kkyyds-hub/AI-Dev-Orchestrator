"""P4-B1 read-only Git diff/status dry-run runner.

The runner is an evidence-only boundary.  It executes a narrow allowlist of
read-only Git commands and refuses every Git write command.  It does not run
``git add``, ``git commit``, ``git push``, open PRs, call TaskWorker, or write
AgentMessage events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import subprocess


MAX_CHANGED_FILE_PREVIEW = 200
MAX_DIFF_STAT_CHARS = 4_000
MAX_GIT_LOG_COUNT = 20


@dataclass(frozen=True, slots=True)
class GitDiffDryRunCommandSpec:
    """Immutable preview of one allowlisted read-only Git diff/status command."""

    argv: tuple[str, ...]
    cwd: str
    timeout_seconds: int
    mutates_repository: bool
    command_kind: str


@dataclass(frozen=True, slots=True)
class GitDiffDryRunCommandResult:
    """Captured result from one allowlisted read-only Git command."""

    spec: GitDiffDryRunCommandSpec
    return_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


@dataclass(frozen=True, slots=True)
class GitDiffDryRunResult:
    """Evidence-only Git diff/status preview — no Git write commands execute."""

    ready: bool
    source: str
    reason_code: str | None
    worktree_path: str | None
    has_changes: bool | None
    changed_files_count: int | None
    changed_files: list[str] = field(default_factory=list)
    added_files: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    deleted_files: list[str] = field(default_factory=list)
    renamed_files: list[str] = field(default_factory=list)
    status_summary_cn: str | None = None
    diff_stat: str | None = None
    diff_shortstat: str | None = None
    branch_name: str | None = None
    compare_branch: str | None = None
    command: str | None = None
    peek_command: str | None = None
    danger_commands_applied: bool | None = False
    runs_git: bool = True
    runs_write_git: bool = False
    git_add_triggered: bool = False
    git_commit_triggered: bool = False
    git_push_triggered: bool = False
    pr_opened: bool = False
    ci_triggered: bool = False
    execution_enabled: bool = False


class GitDiffDryRunRunner:
    """Deny-by-default runner for P4-B1 Git diff/status read-only evidence."""

    source = "agent_session_worktree_diff"

    def __init__(self, *, default_timeout_seconds: int = 30) -> None:
        if default_timeout_seconds <= 0:
            raise ValueError("default_timeout_seconds must be positive")
        self.default_timeout_seconds = default_timeout_seconds

    def git_status_porcelain(
        self,
        *,
        repository_path: str,
    ) -> GitDiffDryRunCommandSpec:
        """Allowlisted command: git status --porcelain=v1 --untracked-files=all."""

        return self._spec(
            cwd=repository_path,
            argv=("git", "status", "--porcelain=v1", "--untracked-files=all"),
            command_kind="git_status_porcelain",
        )

    def git_diff_stat(
        self,
        *,
        repository_path: str,
        paths: tuple[str, ...] = (),
    ) -> GitDiffDryRunCommandSpec:
        """Allowlisted command: git diff --stat [-- <paths>]."""

        return self._diff_spec(
            repository_path=repository_path,
            option="--stat",
            command_kind="git_diff_stat",
            paths=paths,
        )

    def git_diff_shortstat(
        self,
        *,
        repository_path: str,
    ) -> GitDiffDryRunCommandSpec:
        """Allowlisted command: git diff --shortstat."""

        return self._spec(
            cwd=repository_path,
            argv=("git", "diff", "--shortstat"),
            command_kind="git_diff_shortstat",
        )

    def git_diff_name_only(
        self,
        *,
        repository_path: str,
        cached: bool = False,
        paths: tuple[str, ...] = (),
    ) -> GitDiffDryRunCommandSpec:
        """Allowlisted command: git diff [--cached] --name-only [-- <paths>]."""

        argv: tuple[str, ...] = ("git", "diff")
        if cached:
            argv += ("--cached",)
        argv += ("--name-only",)
        if paths:
            argv += ("--", *paths)
        return self._spec(
            cwd=repository_path,
            argv=argv,
            command_kind="git_diff_name_only",
        )

    def git_diff_name_status(
        self,
        *,
        repository_path: str,
        cached: bool = False,
        paths: tuple[str, ...] = (),
    ) -> GitDiffDryRunCommandSpec:
        """Allowlisted command: git diff [--cached] --name-status [-- <paths>]."""

        argv: tuple[str, ...] = ("git", "diff")
        if cached:
            argv += ("--cached",)
        argv += ("--name-status",)
        if paths:
            argv += ("--", *paths)
        return self._spec(
            cwd=repository_path,
            argv=argv,
            command_kind="git_diff_name_status",
        )

    def git_log_oneline(
        self,
        *,
        repository_path: str,
        count: int = 5,
    ) -> GitDiffDryRunCommandSpec:
        """Allowlisted command: git log --oneline -n <N>."""

        if count <= 0 or count > MAX_GIT_LOG_COUNT:
            raise ValueError(f"count must be between 1 and {MAX_GIT_LOG_COUNT}")
        return self._spec(
            cwd=repository_path,
            argv=("git", "log", "--oneline", "-n", str(count)),
            command_kind="git_log_oneline",
        )

    def git_branch_current(
        self,
        *,
        repository_path: str,
    ) -> GitDiffDryRunCommandSpec:
        """Internal read-only helper: git rev-parse --abbrev-ref HEAD."""

        return self._spec(
            cwd=repository_path,
            argv=("git", "rev-parse", "--abbrev-ref", "HEAD"),
            command_kind="git_branch_current",
        )

    def run(
        self,
        spec: GitDiffDryRunCommandSpec,
    ) -> GitDiffDryRunCommandResult:
        """Execute one allowlisted read-only Git command."""

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
            return GitDiffDryRunCommandResult(
                spec=spec,
                return_code=124,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "git diff dry-run command timed out",
                timed_out=True,
            )
        return GitDiffDryRunCommandResult(
            spec=spec,
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def collect(
        self,
        *,
        repository_path: str,
        compare_branch: str | None = None,
    ) -> GitDiffDryRunResult:
        """Collect P4-B1 Git diff/status evidence from one worktree path."""

        worktree_path = str(Path(repository_path).expanduser())
        if not worktree_path.strip():
            return self._blocked(
                reason_code="worktree_path_missing",
                worktree_path=None,
            )
        path = Path(worktree_path)
        if not path.exists():
            return self._blocked(
                reason_code="worktree_path_not_found",
                worktree_path=worktree_path,
            )
        if not path.is_dir():
            return self._blocked(
                reason_code="worktree_path_not_directory",
                worktree_path=worktree_path,
            )

        status_result = self.run(
            self.git_status_porcelain(repository_path=worktree_path)
        )
        if not _command_succeeded(status_result):
            return self._blocked_from_command(
                result=status_result,
                reason_code="git_status_failed",
                worktree_path=worktree_path,
            )

        name_status_result = self.run(
            self.git_diff_name_status(repository_path=worktree_path)
        )
        if not _command_succeeded(name_status_result):
            return self._blocked_from_command(
                result=name_status_result,
                reason_code="git_diff_name_status_failed",
                worktree_path=worktree_path,
            )

        stat_result = self.run(self.git_diff_stat(repository_path=worktree_path))
        if not _command_succeeded(stat_result):
            return self._blocked_from_command(
                result=stat_result,
                reason_code="git_diff_stat_failed",
                worktree_path=worktree_path,
            )

        shortstat_result = self.run(
            self.git_diff_shortstat(repository_path=worktree_path)
        )
        if not _command_succeeded(shortstat_result):
            return self._blocked_from_command(
                result=shortstat_result,
                reason_code="git_diff_shortstat_failed",
                worktree_path=worktree_path,
            )

        branch_result = self.run(
            self.git_branch_current(repository_path=worktree_path)
        )
        branch_name = (
            branch_result.stdout.strip()
            if _command_succeeded(branch_result) and branch_result.stdout.strip()
            else None
        )

        status_changes = _parse_status_porcelain(status_result.stdout)
        diff_changes = _parse_name_status(name_status_result.stdout)
        changes = _merge_changes(status_changes=status_changes, diff_changes=diff_changes)
        added_files = sorted(path for path, kind in changes.items() if kind == "added")
        modified_files = sorted(path for path, kind in changes.items() if kind == "modified")
        deleted_files = sorted(path for path, kind in changes.items() if kind == "deleted")
        renamed_files = sorted(path for path, kind in changes.items() if kind == "renamed")
        changed_files = sorted(changes)
        changed_files_count = len(changed_files)
        has_changes = changed_files_count > 0

        return GitDiffDryRunResult(
            ready=True,
            source=self.source,
            reason_code=None,
            worktree_path=worktree_path,
            has_changes=has_changes,
            changed_files_count=changed_files_count,
            changed_files=changed_files[:MAX_CHANGED_FILE_PREVIEW],
            added_files=added_files[:MAX_CHANGED_FILE_PREVIEW],
            modified_files=modified_files[:MAX_CHANGED_FILE_PREVIEW],
            deleted_files=deleted_files[:MAX_CHANGED_FILE_PREVIEW],
            renamed_files=renamed_files[:MAX_CHANGED_FILE_PREVIEW],
            status_summary_cn=_build_status_summary_cn(
                added_count=len(added_files),
                modified_count=len(modified_files),
                deleted_count=len(deleted_files),
                renamed_count=len(renamed_files),
            ),
            diff_stat=_truncate_text(stat_result.stdout.strip(), MAX_DIFF_STAT_CHARS),
            diff_shortstat=shortstat_result.stdout.strip() or None,
            branch_name=branch_name,
            compare_branch=compare_branch,
            command="git status --porcelain=v1 --untracked-files=all",
            peek_command="git diff --name-status",
            danger_commands_applied=False,
        )

    def _diff_spec(
        self,
        *,
        repository_path: str,
        option: str,
        command_kind: str,
        paths: tuple[str, ...],
    ) -> GitDiffDryRunCommandSpec:
        argv: tuple[str, ...] = ("git", "diff", option)
        if paths:
            argv += ("--", *paths)
        return self._spec(
            cwd=repository_path,
            argv=argv,
            command_kind=command_kind,
        )

    def _spec(
        self,
        *,
        cwd: str,
        argv: tuple[str, ...],
        command_kind: str,
    ) -> GitDiffDryRunCommandSpec:
        normalized_cwd = str(Path(cwd).expanduser())
        if not normalized_cwd.strip():
            raise ValueError("cwd must not be blank")
        if not argv or not all(part.strip() for part in argv):
            raise ValueError("argv parts must not be blank")
        return GitDiffDryRunCommandSpec(
            argv=argv,
            cwd=normalized_cwd,
            timeout_seconds=self.default_timeout_seconds,
            mutates_repository=False,
            command_kind=command_kind,
        )

    def _blocked(
        self,
        *,
        reason_code: str,
        worktree_path: str | None,
    ) -> GitDiffDryRunResult:
        return GitDiffDryRunResult(
            ready=False,
            source=self.source,
            reason_code=reason_code,
            worktree_path=worktree_path,
            has_changes=None,
            changed_files_count=None,
            status_summary_cn=None,
            runs_git=False,
        )

    def _blocked_from_command(
        self,
        *,
        result: GitDiffDryRunCommandResult,
        reason_code: str,
        worktree_path: str,
    ) -> GitDiffDryRunResult:
        return GitDiffDryRunResult(
            ready=False,
            source=self.source,
            reason_code=(
                "git_diff_dry_run_command_timed_out"
                if result.timed_out
                else reason_code
            ),
            worktree_path=worktree_path,
            has_changes=None,
            changed_files_count=None,
            status_summary_cn=None,
            command=" ".join(result.spec.argv),
            runs_git=True,
        )

    @staticmethod
    def _ensure_read_only_allowlisted(spec: GitDiffDryRunCommandSpec) -> None:
        """Reject arbitrary commands and every Git write command shape."""

        if spec.mutates_repository:
            raise ValueError("mutating git command specs are not allowed")
        if spec.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        argv = spec.argv
        if not argv or argv[0] != "git":
            raise ValueError("only git commands can be checked")

        if argv in {
            ("git", "status", "--porcelain"),
            ("git", "status", "--porcelain=v1"),
            ("git", "status", "--porcelain=v1", "--untracked-files=all"),
        }:
            _ensure_kind(spec, "git_status_porcelain")
            return
        if _matches_diff_stat(argv):
            _ensure_kind(spec, "git_diff_stat")
            return
        if argv == ("git", "diff", "--shortstat"):
            _ensure_kind(spec, "git_diff_shortstat")
            return
        if _matches_diff_name(argv, "--name-only"):
            _ensure_kind(spec, "git_diff_name_only")
            return
        if _matches_diff_name(argv, "--name-status"):
            _ensure_kind(spec, "git_diff_name_status")
            return
        if _matches_log_oneline(argv):
            _ensure_kind(spec, "git_log_oneline")
            return
        if argv == ("git", "rev-parse", "--abbrev-ref", "HEAD"):
            _ensure_kind(spec, "git_branch_current")
            return

        raise ValueError(f"git command is not allowlisted: {' '.join(argv)}")


def _ensure_kind(spec: GitDiffDryRunCommandSpec, expected_kind: str) -> None:
    if spec.command_kind != expected_kind:
        raise ValueError("git command kind is not allowlisted")


def _matches_diff_stat(argv: tuple[str, ...]) -> bool:
    return _matches_diff_with_optional_paths(argv=argv, option="--stat")


def _matches_diff_name(argv: tuple[str, ...], option: str) -> bool:
    if len(argv) >= 4 and argv[:3] == ("git", "diff", "--cached") and argv[3] == option:
        return _has_valid_optional_paths(argv[4:])
    if len(argv) >= 3 and argv[:2] == ("git", "diff") and argv[2] == option:
        return _has_valid_optional_paths(argv[3:])
    return False


def _matches_diff_with_optional_paths(*, argv: tuple[str, ...], option: str) -> bool:
    if len(argv) >= 3 and argv[:2] == ("git", "diff") and argv[2] == option:
        return _has_valid_optional_paths(argv[3:])
    return False


def _has_valid_optional_paths(parts: tuple[str, ...]) -> bool:
    if not parts:
        return True
    if parts[0] != "--":
        return False
    return len(parts) > 1 and all(_is_safe_relative_path(part) for part in parts[1:])


def _matches_log_oneline(argv: tuple[str, ...]) -> bool:
    if len(argv) != 5 or argv[:4] != ("git", "log", "--oneline", "-n"):
        return False
    try:
        count = int(argv[4])
    except ValueError:
        return False
    return 1 <= count <= MAX_GIT_LOG_COUNT


def _is_safe_relative_path(value: str) -> bool:
    path = Path(value)
    return (
        value.strip() != ""
        and not path.is_absolute()
        and ".." not in path.parts
        and not value.startswith("-")
    )


def _command_succeeded(result: GitDiffDryRunCommandResult) -> bool:
    return result.return_code == 0 and not result.timed_out


def _parse_status_porcelain(output: str) -> dict[str, str]:
    changes: dict[str, str] = {}
    for line in output.splitlines():
        if len(line) < 4:
            continue
        status_code = line[:2]
        raw_path = line[3:].strip()
        if not raw_path:
            continue
        if " -> " in raw_path and (status_code[0] in {"R", "C"} or status_code[1] in {"R", "C"}):
            raw_path = raw_path.split(" -> ", 1)[1].strip()
        kind = _change_kind_from_status(status_code)
        if kind:
            changes[raw_path] = kind
    return changes


def _parse_name_status(output: str) -> dict[str, str]:
    changes: dict[str, str] = {}
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status_code = parts[0]
        raw_path = parts[-1].strip()
        if not raw_path:
            continue
        kind = _change_kind_from_status(status_code)
        if kind:
            changes[raw_path] = kind
    return changes


def _change_kind_from_status(status_code: str) -> str | None:
    if status_code.startswith("R") or "R" in status_code:
        return "renamed"
    if "A" in status_code or "?" in status_code:
        return "added"
    if "D" in status_code:
        return "deleted"
    if "M" in status_code:
        return "modified"
    return None


def _merge_changes(
    *,
    status_changes: dict[str, str],
    diff_changes: dict[str, str],
) -> dict[str, str]:
    merged = dict(status_changes)
    merged.update(diff_changes)
    return merged


def _build_status_summary_cn(
    *,
    added_count: int,
    modified_count: int,
    deleted_count: int,
    renamed_count: int,
) -> str:
    parts: list[str] = []
    if modified_count:
        parts.append(f"{modified_count} 个文件修改")
    if added_count:
        parts.append(f"{added_count} 个文件新增")
    if deleted_count:
        parts.append(f"{deleted_count} 个文件删除")
    if renamed_count:
        parts.append(f"{renamed_count} 个文件重命名")
    return "，".join(parts) if parts else "本次执行未产生文件变更"


def _truncate_text(value: str, max_length: int) -> str | None:
    if not value:
        return None
    if len(value) <= max_length:
        return value
    return f"{value[:max_length]}…"
