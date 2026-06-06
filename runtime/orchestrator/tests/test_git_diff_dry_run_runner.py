"""P4-B1 Git diff/status read-only dry-run runner tests."""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from app.services.git_diff_dry_run_runner import (
    GitDiffDryRunCommandSpec,
    GitDiffDryRunRunner,
)


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run Git only inside tmp_path repository fixtures."""

    return subprocess.run(
        ("git", *args),
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def _create_tmp_git_repository(parent_path: Path) -> Path:
    """Create a committed Git repository fixture under tmp_path."""

    repository_root = parent_path / "repo"
    repository_root.mkdir()
    _run_git(repository_root, "init", "-b", "main")
    _run_git(repository_root, "config", "user.email", "test@example.invalid")
    _run_git(repository_root, "config", "user.name", "AIDO Test")
    (repository_root / "README.md").write_text("fixture\n", encoding="utf-8")
    _run_git(repository_root, "add", "README.md")
    _run_git(repository_root, "commit", "-m", "initial fixture commit")
    return repository_root


def test_git_diff_dry_run_runner_exposes_only_read_only_allowlist(tmp_path):
    runner = GitDiffDryRunRunner(default_timeout_seconds=9)
    repository_path = str(tmp_path)

    specs = [
        runner.git_status_porcelain(repository_path=repository_path),
        runner.git_diff_stat(repository_path=repository_path),
        runner.git_diff_stat(
            repository_path=repository_path,
            paths=("README.md", "src/app.py"),
        ),
        runner.git_diff_shortstat(repository_path=repository_path),
        runner.git_diff_name_only(repository_path=repository_path),
        runner.git_diff_name_only(
            repository_path=repository_path,
            cached=True,
            paths=("README.md",),
        ),
        runner.git_diff_name_status(repository_path=repository_path),
        runner.git_diff_name_status(
            repository_path=repository_path,
            cached=True,
            paths=("README.md",),
        ),
        runner.git_log_oneline(repository_path=repository_path, count=3),
    ]

    assert [spec.command_kind for spec in specs] == [
        "git_status_porcelain",
        "git_diff_stat",
        "git_diff_stat",
        "git_diff_shortstat",
        "git_diff_name_only",
        "git_diff_name_only",
        "git_diff_name_status",
        "git_diff_name_status",
        "git_log_oneline",
    ]
    assert all(spec.argv[0] == "git" for spec in specs)
    assert all(spec.mutates_repository is False for spec in specs)
    assert all(spec.timeout_seconds == 9 for spec in specs)

    for spec in specs:
        runner._ensure_read_only_allowlisted(spec)


@pytest.mark.parametrize(
    "argv",
    [
        ("git", "add", "."),
        ("git", "commit", "-m", "delivery"),
        ("git", "push", "origin", "main"),
        ("git", "merge", "main"),
        ("git", "rebase", "main"),
        ("git", "reset", "--hard"),
        ("git", "checkout", "-b", "feature"),
        ("git", "switch", "main"),
        ("git", "stash"),
        ("git", "tag", "v1"),
        ("git", "branch", "-d", "feature"),
        ("git", "branch", "-D", "feature"),
        ("git", "worktree", "remove", "/tmp/worktree"),
    ],
)
def test_git_diff_dry_run_runner_rejects_git_write_commands(tmp_path, argv):
    runner = GitDiffDryRunRunner()
    spec = GitDiffDryRunCommandSpec(
        argv=argv,
        cwd=str(tmp_path),
        timeout_seconds=30,
        mutates_repository=True,
        command_kind="git_write",
    )

    with pytest.raises(ValueError, match="mutating git command specs are not allowed"):
        runner.run(spec)


def test_git_diff_dry_run_runner_rejects_unmarked_write_shapes(tmp_path):
    runner = GitDiffDryRunRunner()
    spec = GitDiffDryRunCommandSpec(
        argv=("git", "commit", "-m", "delivery"),
        cwd=str(tmp_path),
        timeout_seconds=30,
        mutates_repository=False,
        command_kind="git_commit",
    )

    with pytest.raises(ValueError, match="git command is not allowlisted"):
        runner.run(spec)


def test_git_diff_dry_run_runner_rejects_unsafe_path_filters(tmp_path):
    runner = GitDiffDryRunRunner()
    unsafe_specs = [
        GitDiffDryRunCommandSpec(
            argv=("git", "diff", "--stat", "--", "../outside.py"),
            cwd=str(tmp_path),
            timeout_seconds=30,
            mutates_repository=False,
            command_kind="git_diff_stat",
        ),
        GitDiffDryRunCommandSpec(
            argv=("git", "diff", "--name-only", "--", "-looks-like-option"),
            cwd=str(tmp_path),
            timeout_seconds=30,
            mutates_repository=False,
            command_kind="git_diff_name_only",
        ),
    ]

    for spec in unsafe_specs:
        with pytest.raises(ValueError, match="git command is not allowlisted"):
            runner._ensure_read_only_allowlisted(spec)


def test_git_diff_dry_run_collects_dirty_status_and_diff_evidence(tmp_path):
    repository_root = _create_tmp_git_repository(tmp_path)
    (repository_root / "README.md").write_text(
        "fixture\nmodified\n",
        encoding="utf-8",
    )
    (repository_root / "new_file.py").write_text("print('new')\n", encoding="utf-8")

    runner = GitDiffDryRunRunner()
    result = runner.collect(repository_path=str(repository_root), compare_branch="main")

    assert result.ready is True
    assert result.source == "agent_session_worktree_diff"
    assert result.reason_code is None
    assert result.worktree_path == str(repository_root)
    assert result.has_changes is True
    assert result.changed_files_count == 2
    assert result.changed_files == ["README.md", "new_file.py"]
    assert result.modified_files == ["README.md"]
    assert result.added_files == ["new_file.py"]
    assert result.deleted_files == []
    assert result.renamed_files == []
    assert result.status_summary_cn == "1 个文件修改，1 个文件新增"
    assert "README.md" in (result.diff_stat or "")
    assert "1 file changed" in (result.diff_shortstat or "")
    assert result.branch_name == "main"
    assert result.compare_branch == "main"
    assert result.command == "git status --porcelain=v1 --untracked-files=all"
    assert result.peek_command == "git diff --name-status"
    assert result.danger_commands_applied is False
    assert result.runs_git is True
    assert result.runs_write_git is False
    assert result.git_add_triggered is False
    assert result.git_commit_triggered is False
    assert result.git_push_triggered is False
    assert result.pr_opened is False
    assert result.ci_triggered is False
    assert result.execution_enabled is False

    status_after = _run_git(repository_root, "status", "--porcelain=v1").stdout
    assert "README.md" in status_after
    assert "new_file.py" in status_after


def test_git_diff_dry_run_collects_clean_worktree_evidence(tmp_path):
    repository_root = _create_tmp_git_repository(tmp_path)

    result = GitDiffDryRunRunner().collect(repository_path=str(repository_root))

    assert result.ready is True
    assert result.has_changes is False
    assert result.changed_files_count == 0
    assert result.changed_files == []
    assert result.status_summary_cn == "本次执行未产生文件变更"
    assert result.diff_stat is None
    assert result.diff_shortstat is None
    assert result.runs_git is True
    assert result.runs_write_git is False
    assert result.execution_enabled is False


def test_git_diff_dry_run_collects_deleted_file_evidence(tmp_path):
    repository_root = _create_tmp_git_repository(tmp_path)
    (repository_root / "README.md").unlink()

    result = GitDiffDryRunRunner().collect(repository_path=str(repository_root))

    assert result.ready is True
    assert result.has_changes is True
    assert result.changed_files == ["README.md"]
    assert result.deleted_files == ["README.md"]
    assert result.added_files == []
    assert result.modified_files == []
    assert result.renamed_files == []
    assert result.status_summary_cn == "1 个文件删除"
    assert result.runs_git is True
    assert result.runs_write_git is False
    assert result.git_add_triggered is False
    assert result.git_commit_triggered is False
    assert result.git_push_triggered is False
    assert result.pr_opened is False


def test_git_diff_dry_run_collects_renamed_file_evidence(tmp_path):
    repository_root = _create_tmp_git_repository(tmp_path)
    _run_git(repository_root, "mv", "README.md", "README_RENAMED.md")

    result = GitDiffDryRunRunner().collect(repository_path=str(repository_root))

    assert result.ready is True
    assert result.has_changes is True
    assert result.changed_files == ["README_RENAMED.md"]
    assert result.renamed_files == ["README_RENAMED.md"]
    assert result.added_files == []
    assert result.modified_files == []
    assert result.deleted_files == []
    assert result.status_summary_cn == "1 个文件重命名"
    assert result.runs_git is True
    assert result.runs_write_git is False
    assert result.execution_enabled is False


def test_git_diff_dry_run_returns_timeout_result(tmp_path, monkeypatch):
    repository_root = _create_tmp_git_repository(tmp_path)
    runner = GitDiffDryRunRunner(default_timeout_seconds=1)
    spec = runner.git_diff_stat(repository_path=str(repository_root))

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=kwargs.get("args") or args[0],
            timeout=kwargs["timeout"],
            output="partial stdout",
            stderr="partial stderr",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = runner.run(spec)

    assert result.return_code == 124
    assert result.stdout == "partial stdout"
    assert result.stderr == "partial stderr"
    assert result.timed_out is True
    assert result.spec == spec


def test_git_diff_dry_run_collect_maps_timeout_to_blocked_result(tmp_path, monkeypatch):
    repository_root = _create_tmp_git_repository(tmp_path)

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=kwargs.get("args") or args[0],
            timeout=kwargs["timeout"],
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = GitDiffDryRunRunner(default_timeout_seconds=1).collect(
        repository_path=str(repository_root)
    )

    assert result.ready is False
    assert result.reason_code == "git_diff_dry_run_command_timed_out"
    assert result.worktree_path == str(repository_root)
    assert result.has_changes is None
    assert result.changed_files_count is None
    assert result.command == "git status --porcelain=v1 --untracked-files=all"
    assert result.runs_git is True
    assert result.runs_write_git is False
    assert result.git_add_triggered is False
    assert result.git_commit_triggered is False
    assert result.git_push_triggered is False
    assert result.pr_opened is False
    assert result.execution_enabled is False


def test_git_diff_dry_run_uses_subprocess_arg_list_without_shell(tmp_path, monkeypatch):
    repository_root = _create_tmp_git_repository(tmp_path)
    runner = GitDiffDryRunRunner(default_timeout_seconds=7)
    spec = runner.git_status_porcelain(repository_path=str(repository_root))
    calls: list[dict[str, object]] = []

    class Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return Completed()

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = runner.run(spec)

    assert result.return_code == 0
    assert len(calls) == 1
    assert calls[0]["args"] == (spec.argv,)
    kwargs = calls[0]["kwargs"]
    assert kwargs["cwd"] == str(repository_root)
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["timeout"] == 7
    assert kwargs["check"] is False
    assert "shell" not in kwargs


def test_git_diff_dry_run_blocks_before_git_for_missing_worktree(tmp_path):
    missing_path = tmp_path / "missing"

    result = GitDiffDryRunRunner().collect(repository_path=str(missing_path))

    assert result.ready is False
    assert result.reason_code == "worktree_path_not_found"
    assert result.worktree_path == str(missing_path)
    assert result.has_changes is None
    assert result.changed_files_count is None
    assert result.runs_git is False
    assert result.runs_write_git is False
    assert result.execution_enabled is False
