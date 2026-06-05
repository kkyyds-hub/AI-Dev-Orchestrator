"""P2-B Worker AgentSession.workspace_path read-only validation.

These tests cover the pure validation seam only. They do not invoke the worker
loop, do not start services, do not run git commands, and do not create or
clean real git worktrees.
"""

from __future__ import annotations

from uuid import uuid4

from app.api.routes.workers import WorkerRunOnceResponse
from app.domain.agent_session import (
    AgentSession,
    AgentType,
    RuntimeType,
    WorkspaceType,
)
from app.workers.task_worker import (
    WorkerRunResult,
    build_worker_runtime_launch_dry_run,
    resolve_worker_workspace_context,
    validate_worker_agent_workspace,
)
from app.workers.worktree_safe_command import WorkerWorktreeSafeCommandProofRunner
from app.services.worktree_command_runner import (
    WorktreeCommandResult,
    WorktreeCommandSpec,
)


class _FakeWorktreeCommandRunner:
    def __init__(
        self,
        *,
        return_code: int = 0,
        stdout: str = "true\n",
        stderr: str = "",
        mutates_repository: bool = False,
    ) -> None:
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr
        self.mutates_repository = mutates_repository
        self.requested_repository_path: str | None = None
        self.ran_spec: WorktreeCommandSpec | None = None

    def git_rev_parse_is_inside_work_tree(
        self,
        *,
        repository_path: str,
    ) -> WorktreeCommandSpec:
        self.requested_repository_path = repository_path
        return WorktreeCommandSpec(
            argv=("git", "rev-parse", "--is-inside-work-tree"),
            cwd=repository_path,
            timeout_seconds=30,
            mutates_repository=self.mutates_repository,
        )

    def run(self, spec: WorktreeCommandSpec) -> WorktreeCommandResult:
        self.ran_spec = spec
        return WorktreeCommandResult(
            spec=spec,
            return_code=self.return_code,
            stdout=self.stdout,
            stderr=self.stderr,
        )


def _session(
    *,
    workspace_type: WorkspaceType | None = WorkspaceType.WORKTREE,
    workspace_path: str | None = None,
    workspace_clean: bool | None = None,
    agent_type: AgentType | None = AgentType.OPENAI_PROVIDER,
    runtime_type: RuntimeType | None = RuntimeType.SUBPROCESS,
) -> AgentSession:
    return AgentSession(
        project_id=uuid4(),
        task_id=uuid4(),
        run_id=uuid4(),
        agent_type=agent_type,
        runtime_type=runtime_type,
        workspace_type=workspace_type,
        workspace_path=workspace_path,
        workspace_clean=workspace_clean,
    )


def test_validate_worker_agent_workspace_skips_non_worktree_sessions():
    result = validate_worker_agent_workspace(
        _session(workspace_type=WorkspaceType.IN_PLACE)
    )

    assert result.ready is True
    assert result.reason_code is None
    assert result.workspace_type == "in_place"
    assert result.resolved_workspace_path is None

    context = resolve_worker_workspace_context(result)

    assert context.ready is True
    assert context.source == "agent_session_non_worktree"
    assert context.uses_agent_workspace is False
    assert context.changes_cwd is False
    assert context.runs_git is False
    assert context.runs_write_git is False
    assert context.launches_runtime is False


def test_validate_worker_agent_workspace_blocks_missing_worktree_path():
    result = validate_worker_agent_workspace(_session(workspace_path=None))

    assert result.ready is False
    assert result.reason_code == "workspace_path_missing"
    assert "requires workspace_path" in result.summary

    context = resolve_worker_workspace_context(result)

    assert context.ready is False
    assert context.source == "agent_session_worktree_blocked"
    assert context.reason_code == "workspace_path_missing"
    assert context.uses_agent_workspace is False
    assert context.changes_cwd is False
    assert context.runs_write_git is False


def test_validate_worker_agent_workspace_blocks_relative_worktree_path():
    result = validate_worker_agent_workspace(
        _session(workspace_path="relative/worktree", workspace_clean=True)
    )

    assert result.ready is False
    assert result.reason_code == "workspace_path_not_absolute"


def test_validate_worker_agent_workspace_blocks_missing_directory(tmp_path):
    missing_path = tmp_path / "missing-worktree"
    result = validate_worker_agent_workspace(
        _session(workspace_path=missing_path.as_posix(), workspace_clean=True)
    )

    assert result.ready is False
    assert result.reason_code == "workspace_path_not_found"
    assert result.resolved_workspace_path == missing_path.as_posix()


def test_validate_worker_agent_workspace_blocks_file_path(tmp_path):
    file_path = tmp_path / "not-a-directory"
    file_path.write_text("not a worktree directory\n")

    result = validate_worker_agent_workspace(
        _session(workspace_path=file_path.as_posix(), workspace_clean=True)
    )

    assert result.ready is False
    assert result.reason_code == "workspace_path_not_directory"


def test_validate_worker_agent_workspace_blocks_unknown_clean_state(tmp_path):
    result = validate_worker_agent_workspace(
        _session(workspace_path=tmp_path.as_posix(), workspace_clean=None)
    )

    assert result.ready is False
    assert result.reason_code == "workspace_clean_unknown"
    assert "does not run git status" in result.summary


def test_validate_worker_agent_workspace_blocks_dirty_metadata(tmp_path):
    result = validate_worker_agent_workspace(
        _session(workspace_path=tmp_path.as_posix(), workspace_clean=False)
    )

    assert result.ready is False
    assert result.reason_code == "workspace_dirty"


def test_validate_worker_agent_workspace_accepts_existing_clean_worktree_metadata(
    tmp_path,
):
    result = validate_worker_agent_workspace(
        _session(workspace_path=tmp_path.as_posix(), workspace_clean=True)
    )

    assert result.ready is True
    assert result.reason_code is None
    assert result.workspace_type == "worktree"
    assert result.workspace_path == tmp_path.as_posix()
    assert result.workspace_clean is True
    assert result.resolved_workspace_path == tmp_path.as_posix()

    context = resolve_worker_workspace_context(result)

    assert context.ready is True
    assert context.source == "agent_session_worktree"
    assert context.workspace_path == tmp_path.as_posix()
    assert context.resolved_workspace_path == tmp_path.as_posix()
    assert context.uses_agent_workspace is True
    assert context.changes_cwd is False
    assert context.runs_git is False
    assert context.runs_write_git is False
    assert context.launches_runtime is False


def test_runtime_launch_dry_run_targets_clean_worktree_without_execution(tmp_path):
    session = _session(workspace_path=tmp_path.as_posix(), workspace_clean=True)
    validation = validate_worker_agent_workspace(session)
    context = resolve_worker_workspace_context(validation)

    dry_run = build_worker_runtime_launch_dry_run(
        agent_session=session,
        workspace_context=context,
    )

    assert dry_run.ready is True
    assert dry_run.source == "agent_session_worktree_runtime_dry_run"
    assert dry_run.reason_code is None
    assert dry_run.session_id == str(session.id)
    assert dry_run.agent_type == "openai_provider"
    assert dry_run.runtime_type == "subprocess"
    assert dry_run.workspace_path == tmp_path.as_posix()
    assert dry_run.resolved_workspace_path == tmp_path.as_posix()
    assert dry_run.launch_cwd_preview == tmp_path.as_posix()
    assert tmp_path.as_posix() in (dry_run.launch_command_preview or "")
    assert dry_run.uses_agent_workspace is True
    assert dry_run.command_preview_uses_workspace is True
    assert dry_run.execution_enabled is False
    assert dry_run.changes_cwd is False
    assert dry_run.runs_command is False
    assert dry_run.runs_git is False
    assert dry_run.runs_write_git is False
    assert dry_run.launches_runtime is False


def test_worktree_safe_command_proof_runs_one_allowlisted_probe_in_worktree(
    tmp_path,
):
    session = _session(workspace_path=tmp_path.as_posix(), workspace_clean=True)
    validation = validate_worker_agent_workspace(session)
    context = resolve_worker_workspace_context(validation)
    fake_runner = _FakeWorktreeCommandRunner()
    proof_runner = WorkerWorktreeSafeCommandProofRunner(
        command_runner=fake_runner,
    )

    proof = proof_runner.run_probe(workspace_context=context)

    assert proof.ready is True
    assert proof.source == "agent_session_worktree_safe_command"
    assert proof.reason_code is None
    assert proof.command == "git rev-parse --is-inside-work-tree"
    assert proof.cwd == tmp_path.as_posix()
    assert proof.exit_code == 0
    assert proof.stdout == "true"
    assert proof.stderr == ""
    assert proof.timed_out is False
    assert proof.read_only is True
    assert proof.allowlisted is True
    assert proof.uses_agent_workspace is True
    assert proof.changes_process_cwd is False
    assert proof.runs_command is True
    assert proof.runs_git is True
    assert proof.runs_write_git is False
    assert proof.launches_worker_loop is False
    assert proof.launches_ai_runtime is False
    assert fake_runner.requested_repository_path == tmp_path.as_posix()
    assert fake_runner.ran_spec is not None
    assert fake_runner.ran_spec.argv == (
        "git",
        "rev-parse",
        "--is-inside-work-tree",
    )
    assert fake_runner.ran_spec.cwd == tmp_path.as_posix()
    assert fake_runner.ran_spec.mutates_repository is False


def test_worktree_safe_command_proof_blocks_failed_probe(tmp_path):
    session = _session(workspace_path=tmp_path.as_posix(), workspace_clean=True)
    validation = validate_worker_agent_workspace(session)
    context = resolve_worker_workspace_context(validation)
    proof_runner = WorkerWorktreeSafeCommandProofRunner(
        command_runner=_FakeWorktreeCommandRunner(
            return_code=128,
            stdout="",
            stderr="fatal: not a git repository",
        ),
    )

    proof = proof_runner.run_probe(workspace_context=context)

    assert proof.ready is False
    assert proof.source == "agent_session_worktree_safe_command_blocked"
    assert proof.reason_code == "safe_command_failed"
    assert proof.command == "git rev-parse --is-inside-work-tree"
    assert proof.cwd == tmp_path.as_posix()
    assert proof.exit_code == 128
    assert proof.stderr == "fatal: not a git repository"
    assert proof.read_only is True
    assert proof.allowlisted is True
    assert proof.runs_command is True
    assert proof.runs_git is True
    assert proof.runs_write_git is False
    assert proof.launches_worker_loop is False
    assert proof.launches_ai_runtime is False


def test_worktree_safe_command_proof_skips_non_worktree_without_execution():
    session = _session(workspace_type=WorkspaceType.IN_PLACE)
    validation = validate_worker_agent_workspace(session)
    context = resolve_worker_workspace_context(validation)
    fake_runner = _FakeWorktreeCommandRunner()
    proof_runner = WorkerWorktreeSafeCommandProofRunner(
        command_runner=fake_runner,
    )

    proof = proof_runner.run_probe(workspace_context=context)

    assert proof.ready is True
    assert proof.source == "agent_session_non_worktree_safe_command_skipped"
    assert proof.command is None
    assert proof.cwd is None
    assert proof.allowlisted is False
    assert proof.uses_agent_workspace is False
    assert proof.runs_command is False
    assert proof.runs_git is False
    assert proof.runs_write_git is False
    assert proof.launches_worker_loop is False
    assert proof.launches_ai_runtime is False
    assert fake_runner.ran_spec is None


def test_worktree_safe_command_proof_rejects_mutating_probe_spec(tmp_path):
    session = _session(workspace_path=tmp_path.as_posix(), workspace_clean=True)
    validation = validate_worker_agent_workspace(session)
    context = resolve_worker_workspace_context(validation)
    proof_runner = WorkerWorktreeSafeCommandProofRunner(
        command_runner=_FakeWorktreeCommandRunner(mutates_repository=True),
    )

    proof = proof_runner.run_probe(workspace_context=context)

    assert proof.ready is False
    assert proof.reason_code == "safe_command_not_allowlisted"
    assert proof.read_only is False
    assert proof.allowlisted is False
    assert proof.runs_command is True
    assert proof.runs_git is True
    assert proof.runs_write_git is True
    assert proof.launches_worker_loop is False
    assert proof.launches_ai_runtime is False


def test_runtime_launch_dry_run_blocks_non_worktree_without_execution():
    session = _session(workspace_type=WorkspaceType.IN_PLACE)
    validation = validate_worker_agent_workspace(session)
    context = resolve_worker_workspace_context(validation)

    dry_run = build_worker_runtime_launch_dry_run(
        agent_session=session,
        workspace_context=context,
    )

    assert dry_run.ready is False
    assert dry_run.source == "agent_session_non_worktree"
    assert dry_run.reason_code == "agent_worktree_not_available"
    assert dry_run.launch_command_preview is None
    assert dry_run.uses_agent_workspace is False
    assert dry_run.command_preview_uses_workspace is False
    assert dry_run.execution_enabled is False
    assert dry_run.runs_command is False
    assert dry_run.launches_runtime is False


def test_runtime_launch_dry_run_blocks_invalid_worktree_context(tmp_path):
    session = _session(workspace_path=(tmp_path / "missing").as_posix())
    validation = validate_worker_agent_workspace(session)
    context = resolve_worker_workspace_context(validation)

    dry_run = build_worker_runtime_launch_dry_run(
        agent_session=session,
        workspace_context=context,
    )

    assert dry_run.ready is False
    assert dry_run.source == "workspace_context_blocked"
    assert dry_run.reason_code == "workspace_path_not_found"
    assert dry_run.launch_cwd_preview is None
    assert dry_run.launch_command_preview is None
    assert dry_run.runs_command is False
    assert dry_run.launches_runtime is False


def test_worker_run_once_response_exposes_workspace_context_evidence_fields():
    payload = WorkerRunOnceResponse.from_result(
        WorkerRunResult(
            claimed=True,
            message="resolver evidence only",
            workspace_type="worktree",
            workspace_path="/tmp/aido-worktree",
            workspace_clean=True,
            workspace_context_ready=True,
            workspace_context_source="agent_session_worktree",
            workspace_context_reason_code=None,
            workspace_context_path="/tmp/aido-worktree",
            workspace_context_resolved_path="/tmp/aido-worktree",
            workspace_context_uses_agent_workspace=True,
            workspace_context_changes_cwd=False,
            workspace_context_runs_git=False,
            workspace_context_runs_write_git=False,
            workspace_context_launches_runtime=False,
            runtime_launch_dry_run_ready=True,
            runtime_launch_dry_run_source=(
                "agent_session_worktree_runtime_dry_run"
            ),
            runtime_launch_dry_run_reason_code=None,
            runtime_launch_dry_run_session_id="session-123",
            runtime_launch_dry_run_agent_type="openai_provider",
            runtime_launch_dry_run_runtime_type="subprocess",
            runtime_launch_dry_run_workspace_path="/tmp/aido-worktree",
            runtime_launch_dry_run_resolved_workspace_path="/tmp/aido-worktree",
            runtime_launch_dry_run_launch_cwd_preview="/tmp/aido-worktree",
            runtime_launch_dry_run_launch_command_preview=(
                "RuntimeCreateConfig(session_id=session-123, "
                "runtime_type=subprocess, agent_type=openai_provider, "
                "workspace_path=/tmp/aido-worktree)"
            ),
            runtime_launch_dry_run_uses_agent_workspace=True,
            runtime_launch_dry_run_command_preview_uses_workspace=True,
            runtime_launch_dry_run_execution_enabled=False,
            runtime_launch_dry_run_changes_cwd=False,
            runtime_launch_dry_run_runs_command=False,
            runtime_launch_dry_run_runs_git=False,
            runtime_launch_dry_run_runs_write_git=False,
            runtime_launch_dry_run_launches_runtime=False,
        )
    ).model_dump(mode="json")

    assert payload["workspace_context_ready"] is True
    assert payload["workspace_context_source"] == "agent_session_worktree"
    assert payload["workspace_context_reason_code"] is None
    assert payload["workspace_context_path"] == "/tmp/aido-worktree"
    assert payload["workspace_context_resolved_path"] == "/tmp/aido-worktree"
    assert payload["workspace_context_uses_agent_workspace"] is True
    assert payload["workspace_context_changes_cwd"] is False
    assert payload["workspace_context_runs_git"] is False
    assert payload["workspace_context_runs_write_git"] is False
    assert payload["workspace_context_launches_runtime"] is False
    assert payload["runtime_launch_dry_run_ready"] is True
    assert (
        payload["runtime_launch_dry_run_source"]
        == "agent_session_worktree_runtime_dry_run"
    )
    assert payload["runtime_launch_dry_run_reason_code"] is None
    assert payload["runtime_launch_dry_run_session_id"] == "session-123"
    assert payload["runtime_launch_dry_run_agent_type"] == "openai_provider"
    assert payload["runtime_launch_dry_run_runtime_type"] == "subprocess"
    assert payload["runtime_launch_dry_run_workspace_path"] == "/tmp/aido-worktree"
    assert (
        payload["runtime_launch_dry_run_resolved_workspace_path"]
        == "/tmp/aido-worktree"
    )
    assert (
        payload["runtime_launch_dry_run_launch_cwd_preview"]
        == "/tmp/aido-worktree"
    )
    assert (
        "/tmp/aido-worktree"
        in payload["runtime_launch_dry_run_launch_command_preview"]
    )
    assert payload["runtime_launch_dry_run_uses_agent_workspace"] is True
    assert (
        payload["runtime_launch_dry_run_command_preview_uses_workspace"] is True
    )
    assert payload["runtime_launch_dry_run_execution_enabled"] is False
    assert payload["runtime_launch_dry_run_changes_cwd"] is False
    assert payload["runtime_launch_dry_run_runs_command"] is False
    assert payload["runtime_launch_dry_run_runs_git"] is False
    assert payload["runtime_launch_dry_run_runs_write_git"] is False
    assert payload["runtime_launch_dry_run_launches_runtime"] is False
