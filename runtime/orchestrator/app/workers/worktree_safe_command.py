"""P2-D worker worktree safe read-only command proof.

This module is intentionally outside ``TaskWorker.run_once``.  It proves the
future worker execution seam can run one fixed, allowlisted read-only command
with ``cwd`` set to the AgentSession worktree, without changing the process cwd,
starting a worker loop, launching an AI runtime, or accepting arbitrary command
text.
"""

from __future__ import annotations

from dataclasses import dataclass
import shlex

from app.services.worktree_command_runner import (
    WorktreeCommandRunner,
    WorktreeCommandSpec,
)
from app.workers.task_worker import WorkerWorkspaceContextResolution


@dataclass(slots=True, frozen=True)
class WorkerWorktreeSafeCommandProof:
    """Evidence for one fixed worker-side read-only command probe."""

    ready: bool
    source: str
    reason_code: str | None
    command: str | None
    cwd: str | None
    exit_code: int | None
    stdout: str | None
    stderr: str | None
    timed_out: bool | None
    read_only: bool
    allowlisted: bool
    uses_agent_workspace: bool
    changes_process_cwd: bool = False
    runs_command: bool = False
    runs_git: bool = False
    runs_write_git: bool = False
    launches_worker_loop: bool = False
    launches_ai_runtime: bool = False


class WorkerWorktreeSafeCommandProofRunner:
    """Run exactly one allowlisted read-only command in a resolved worktree."""

    def __init__(self, *, command_runner: WorktreeCommandRunner | None = None) -> None:
        self.command_runner = command_runner or WorktreeCommandRunner()

    def run_probe(
        self,
        *,
        workspace_context: WorkerWorkspaceContextResolution,
    ) -> WorkerWorktreeSafeCommandProof:
        """Execute the fixed P2-D probe when a worktree context is ready."""

        if not workspace_context.ready:
            return WorkerWorktreeSafeCommandProof(
                ready=False,
                source="workspace_context_blocked",
                reason_code=workspace_context.reason_code
                or "workspace_context_not_ready",
                command=None,
                cwd=workspace_context.resolved_workspace_path
                or workspace_context.workspace_path,
                exit_code=None,
                stdout=None,
                stderr=None,
                timed_out=None,
                read_only=True,
                allowlisted=False,
                uses_agent_workspace=False,
            )

        if not workspace_context.uses_agent_workspace:
            return WorkerWorktreeSafeCommandProof(
                ready=True,
                source="agent_session_non_worktree_safe_command_skipped",
                reason_code=None,
                command=None,
                cwd=None,
                exit_code=None,
                stdout=None,
                stderr=None,
                timed_out=None,
                read_only=True,
                allowlisted=False,
                uses_agent_workspace=False,
            )

        cwd = workspace_context.resolved_workspace_path or workspace_context.workspace_path
        if cwd is None:
            return WorkerWorktreeSafeCommandProof(
                ready=False,
                source="agent_session_worktree_safe_command_blocked",
                reason_code="workspace_path_missing",
                command=None,
                cwd=None,
                exit_code=None,
                stdout=None,
                stderr=None,
                timed_out=None,
                read_only=True,
                allowlisted=False,
                uses_agent_workspace=True,
            )

        spec = self.command_runner.git_rev_parse_is_inside_work_tree(
            repository_path=cwd,
        )
        result = self.command_runner.run(spec)
        command = _format_observable_command(result.spec)
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        allowlisted = _is_expected_read_only_probe(result.spec)
        ready = allowlisted and result.return_code == 0 and stdout.lower() == "true"

        if ready:
            reason_code = None
        elif not allowlisted:
            reason_code = "safe_command_not_allowlisted"
        elif result.timed_out:
            reason_code = "safe_command_timed_out"
        elif result.return_code != 0:
            reason_code = "safe_command_failed"
        else:
            reason_code = "workspace_not_git_worktree"

        return WorkerWorktreeSafeCommandProof(
            ready=ready,
            source=(
                "agent_session_worktree_safe_command"
                if ready
                else "agent_session_worktree_safe_command_blocked"
            ),
            reason_code=reason_code,
            command=command,
            cwd=result.spec.cwd,
            exit_code=result.return_code,
            stdout=stdout[:500],
            stderr=stderr[:500],
            timed_out=result.timed_out,
            read_only=not result.spec.mutates_repository,
            allowlisted=allowlisted,
            uses_agent_workspace=True,
            changes_process_cwd=False,
            runs_command=True,
            runs_git=True,
            runs_write_git=result.spec.mutates_repository,
            launches_worker_loop=False,
            launches_ai_runtime=False,
        )


def _is_expected_read_only_probe(spec: WorktreeCommandSpec) -> bool:
    return (
        spec.argv == ("git", "rev-parse", "--is-inside-work-tree")
        and not spec.mutates_repository
    )


def _format_observable_command(spec: WorktreeCommandSpec) -> str:
    """Return a shell-escaped command string for evidence only."""

    return " ".join(shlex.quote(part) for part in spec.argv)
