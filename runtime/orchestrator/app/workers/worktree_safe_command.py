"""P2-D-R2 worker worktree safe read-only command proof.

This module is intentionally outside ``TaskWorker.run_once``.  It proves the
future worker execution seam can run one fixed, allowlisted read-only ``pwd``
command with subprocess ``cwd`` set to the AgentSession worktree, and can prove
the observed command cwd equals ``AgentSession.workspace_path``.  It does not
change the process cwd, start a worker loop, launch an AI runtime, or accept
arbitrary command text.
"""

from __future__ import annotations

from dataclasses import dataclass
import shlex
import subprocess

from app.workers.task_worker import WorkerWorkspaceContextResolution


@dataclass(frozen=True, slots=True)
class WorkerPwdCommandSpec:
    """Immutable preview of the one allowlisted proof command."""

    argv: tuple[str, ...]
    cwd: str
    timeout_seconds: int
    mutates_workspace: bool


@dataclass(frozen=True, slots=True)
class WorkerPwdCommandResult:
    """Captured result from the fixed ``pwd`` proof command."""

    spec: WorkerPwdCommandSpec
    return_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class WorkerPwdCommandRunner:
    """Deny-by-default runner exposing only ``pwd`` for cwd proof."""

    def __init__(self, *, default_timeout_seconds: int = 30) -> None:
        if default_timeout_seconds <= 0:
            raise ValueError("default_timeout_seconds must be positive")
        self.default_timeout_seconds = default_timeout_seconds

    def pwd(self, *, cwd: str) -> WorkerPwdCommandSpec:
        """Build the only allowlisted command spec: ``pwd``."""

        normalized_cwd = cwd.strip()
        if not normalized_cwd:
            raise ValueError("cwd must not be blank")
        return WorkerPwdCommandSpec(
            argv=("pwd",),
            cwd=normalized_cwd,
            timeout_seconds=self.default_timeout_seconds,
            mutates_workspace=False,
        )

    def run(self, spec: WorkerPwdCommandSpec) -> WorkerPwdCommandResult:
        """Execute one fixed read-only ``pwd`` command."""

        self._ensure_allowlisted(spec)
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
            return WorkerPwdCommandResult(
                spec=spec,
                return_code=124,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "pwd command timed out",
                timed_out=True,
            )
        return WorkerPwdCommandResult(
            spec=spec,
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    @staticmethod
    def _ensure_allowlisted(spec: WorkerPwdCommandSpec) -> None:
        if spec.argv != ("pwd",):
            raise ValueError("only pwd is allowlisted for worker cwd proof")
        if spec.mutates_workspace:
            raise ValueError("mutating command specs are not allowed")


@dataclass(slots=True, frozen=True)
class WorkerWorktreeSafeCommandProof:
    """Evidence for one fixed worker-side read-only command probe."""

    ready: bool
    source: str
    reason_code: str | None
    command: str | None
    cwd: str | None
    expected_workspace_path: str | None
    observed_pwd: str | None
    pwd_matches_workspace_path: bool | None
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

    def __init__(self, *, command_runner: WorkerPwdCommandRunner | None = None) -> None:
        self.command_runner = command_runner or WorkerPwdCommandRunner()

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
                expected_workspace_path=workspace_context.workspace_path,
                observed_pwd=None,
                pwd_matches_workspace_path=None,
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
                expected_workspace_path=workspace_context.workspace_path,
                observed_pwd=None,
                pwd_matches_workspace_path=None,
                exit_code=None,
                stdout=None,
                stderr=None,
                timed_out=None,
                read_only=True,
                allowlisted=False,
                uses_agent_workspace=False,
            )

        workspace_path = workspace_context.workspace_path
        if workspace_path is None:
            return WorkerWorktreeSafeCommandProof(
                ready=False,
                source="agent_session_worktree_safe_command_blocked",
                reason_code="workspace_path_missing",
                command=None,
                cwd=None,
                expected_workspace_path=None,
                observed_pwd=None,
                pwd_matches_workspace_path=None,
                exit_code=None,
                stdout=None,
                stderr=None,
                timed_out=None,
                read_only=True,
                allowlisted=False,
                uses_agent_workspace=True,
            )

        spec = self.command_runner.pwd(cwd=workspace_path)
        result = self.command_runner.run(spec)
        command = _format_observable_command(result.spec)
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        observed_pwd = stdout or None
        pwd_matches_workspace_path = observed_pwd == workspace_path
        allowlisted = _is_expected_read_only_probe(result.spec)
        ready = (
            allowlisted
            and result.return_code == 0
            and pwd_matches_workspace_path
        )

        if ready:
            reason_code = None
        elif not allowlisted:
            reason_code = "safe_command_not_allowlisted"
        elif result.timed_out:
            reason_code = "safe_command_timed_out"
        elif result.return_code != 0:
            reason_code = "safe_command_failed"
        elif not pwd_matches_workspace_path:
            reason_code = "pwd_mismatch_workspace_path"
        else:
            reason_code = "pwd_probe_not_ready"

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
            expected_workspace_path=workspace_path,
            observed_pwd=observed_pwd,
            pwd_matches_workspace_path=pwd_matches_workspace_path,
            exit_code=result.return_code,
            stdout=stdout[:500],
            stderr=stderr[:500],
            timed_out=result.timed_out,
            read_only=not result.spec.mutates_workspace,
            allowlisted=allowlisted,
            uses_agent_workspace=True,
            changes_process_cwd=False,
            runs_command=True,
            runs_git=False,
            runs_write_git=False,
            launches_worker_loop=False,
            launches_ai_runtime=False,
        )


def _is_expected_read_only_probe(spec: WorkerPwdCommandSpec) -> bool:
    return spec.argv == ("pwd",) and not spec.mutates_workspace


def _format_observable_command(spec: WorkerPwdCommandSpec) -> str:
    """Return a shell-escaped command string for evidence only."""

    return " ".join(shlex.quote(part) for part in spec.argv)
