"""P3-B1 Fake runtime adapter targeted tests.

These tests cover the runtime adapter contract and fake lifecycle simulation.
They do NOT:
- start real subprocess / tmux / docker
- invoke Claude Code / Codex / DeepSeek / OpenCode
- run git commands
- create or clean real git worktrees
- start the worker loop
- modify the filesystem
"""

from __future__ import annotations

from uuid import uuid4

from app.domain.agent_session import (
    AgentSession,
    AgentType,
    RuntimeType,
    WorkspaceType,
)
from app.workers.runtime_adapter import (
    FakeRuntimeAdapter,
    RuntimeAdapter,
    RuntimeHandle,
    RuntimeLaunchGateResult,
    RuntimeLaunchRequest,
    RuntimeLaunchResult,
    RuntimeLifecycleReason,
    RuntimeLifecycleState,
    RuntimeProbeResult,
    build_runtime_lifecycle_snapshot,
    check_runtime_launch_gates,
    run_fake_runtime_simulation,
)
from app.workers.task_worker import (
    WorkerWorkspaceContextResolution,
    WorkerRuntimeLaunchDryRun,
    validate_worker_agent_workspace,
    resolve_worker_workspace_context,
    build_worker_runtime_launch_dry_run,
)
from app.workers.worktree_safe_command import (
    WorkerWorktreeSafeCommandProof,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _ready_context(tmp_path) -> WorkerWorkspaceContextResolution:
    """Build a ready workspace context for a clean worktree at *tmp_path*."""
    session = _session(
        workspace_path=tmp_path.as_posix(),
        workspace_clean=True,
    )
    validation = validate_worker_agent_workspace(session)
    return resolve_worker_workspace_context(validation)


def _ready_dry_run(tmp_path) -> WorkerRuntimeLaunchDryRun:
    """Build a ready dry-run for a clean worktree at *tmp_path*."""
    session = _session(
        workspace_path=tmp_path.as_posix(),
        workspace_clean=True,
    )
    validation = validate_worker_agent_workspace(session)
    context = resolve_worker_workspace_context(validation)
    return build_worker_runtime_launch_dry_run(
        agent_session=session,
        workspace_context=context,
    )


def _passed_proof() -> WorkerWorktreeSafeCommandProof:
    """Return a proof that represents a passed (ready) P2-D probe."""
    return WorkerWorktreeSafeCommandProof(
        ready=True,
        source="agent_session_worktree_safe_command",
        reason_code=None,
        command="pwd",
        cwd="/tmp/aido-worktree",
        expected_workspace_path="/tmp/aido-worktree",
        observed_pwd="/tmp/aido-worktree",
        pwd_matches_workspace_path=True,
        exit_code=0,
        stdout="/tmp/aido-worktree",
        stderr="",
        timed_out=False,
        read_only=True,
        allowlisted=True,
        uses_agent_workspace=True,
        runs_command=True,
    )


def _failed_proof(
    reason_code: str = "pwd_mismatch_workspace_path",
) -> WorkerWorktreeSafeCommandProof:
    """Return a proof that represents a failed P2-D probe."""
    return WorkerWorktreeSafeCommandProof(
        ready=False,
        source="agent_session_worktree_safe_command_blocked",
        reason_code=reason_code,
        command="pwd",
        cwd="/tmp/aido-worktree",
        expected_workspace_path="/tmp/aido-worktree",
        observed_pwd="/unexpected/path",
        pwd_matches_workspace_path=False,
        exit_code=0,
        stdout="/unexpected/path",
        stderr="",
        timed_out=False,
        read_only=True,
        allowlisted=True,
        uses_agent_workspace=True,
        runs_command=True,
    )


class _NonFakeRuntimeAdapter(RuntimeAdapter):
    """RuntimeAdapter test double that must never enter fake simulation."""

    def __init__(self) -> None:
        self.can_launch_called = False
        self.launch_called = False

    def adapter_kind(self) -> str:
        return "non_fake"

    def can_launch(
        self,
        *,
        agent_type: str,
        runtime_type: str,
    ) -> bool:
        self.can_launch_called = True
        return True

    def launch(
        self,
        *,
        request: RuntimeLaunchRequest,
    ) -> RuntimeLaunchResult:
        self.launch_called = True
        return RuntimeLaunchResult(
            launched=True,
            handle=RuntimeHandle(handle_kind="subprocess", handle_value="pid:1"),
            reason_code=RuntimeLifecycleReason.LAUNCH_SUCCEEDED,
        )

    def is_alive(
        self,
        *,
        handle: RuntimeHandle,
    ) -> RuntimeProbeResult:
        return RuntimeProbeResult(
            alive=True,
            state=RuntimeLifecycleState.ALIVE,
            reason=RuntimeLifecycleReason.PROBE_CONFIRMED_ALIVE,
        )

    def kill(
        self,
        *,
        handle: RuntimeHandle,
    ) -> RuntimeProbeResult:
        return RuntimeProbeResult(
            alive=False,
            state=RuntimeLifecycleState.EXITED,
            reason=RuntimeLifecycleReason.PROCESS_KILLED,
            exit_code=-1,
        )


# ---------------------------------------------------------------------------
# RuntimeHandle
# ---------------------------------------------------------------------------


class TestRuntimeHandle:
    def test_handle_to_string_and_roundtrip(self):
        handle = RuntimeHandle(handle_kind="fake", handle_value="pid:90001")
        assert handle.to_string() == "fake:pid:90001"
        parsed = RuntimeHandle.from_string("fake:pid:90001")
        assert parsed.handle_kind == "fake"
        assert parsed.handle_value == "pid:90001"

    def test_handle_from_string_rejects_malformed(self):
        try:
            RuntimeHandle.from_string("no-colon")
            raise AssertionError("expected ValueError")
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# FakeRuntimeAdapter — launch
# ---------------------------------------------------------------------------


class TestFakeAdapterLaunch:
    def test_launch_returns_fake_handle_no_subprocess(self):
        adapter = FakeRuntimeAdapter()
        request = RuntimeLaunchRequest(
            session_id="s-1",
            agent_type="openai_provider",
            runtime_type="subprocess",
            workspace_path="/tmp/aido-worktree",
        )
        result = adapter.launch(request=request)

        assert result.launched is True
        assert result.handle is not None
        assert result.handle.handle_kind == "fake"
        assert result.handle.handle_value.startswith("pid:")
        assert result.reason_code == RuntimeLifecycleReason.LAUNCH_SUCCEEDED

    def test_launch_increments_pid(self):
        adapter = FakeRuntimeAdapter()
        r1 = adapter.launch(
            request=RuntimeLaunchRequest(
                session_id="s-1",
                agent_type="openai_provider",
                runtime_type="subprocess",
                workspace_path="/tmp/aido-worktree",
            ),
        )
        r2 = adapter.launch(
            request=RuntimeLaunchRequest(
                session_id="s-2",
                agent_type="openai_provider",
                runtime_type="subprocess",
                workspace_path="/tmp/aido-worktree",
            ),
        )
        assert r1.handle is not None
        assert r2.handle is not None
        assert r1.handle.handle_value != r2.handle.handle_value


# ---------------------------------------------------------------------------
# FakeRuntimeAdapter — probe (is_alive)
# ---------------------------------------------------------------------------


class TestFakeAdapterProbe:
    def test_default_probe_returns_alive(self):
        adapter = FakeRuntimeAdapter()
        handle = RuntimeHandle(handle_kind="fake", handle_value="pid:90001")
        result = adapter.is_alive(handle=handle)

        assert result.alive is True
        assert result.state == RuntimeLifecycleState.ALIVE
        assert result.reason == RuntimeLifecycleReason.PROBE_CONFIRMED_ALIVE

    def test_override_probe_exited(self):
        adapter = FakeRuntimeAdapter()
        adapter.set_probe_result(
            RuntimeProbeResult(
                alive=False,
                state=RuntimeLifecycleState.EXITED,
                reason=RuntimeLifecycleReason.PROCESS_EXITED_NORMAL,
                exit_code=0,
            ),
        )
        handle = RuntimeHandle(handle_kind="fake", handle_value="pid:90001")
        result = adapter.is_alive(handle=handle)

        assert result.alive is False
        assert result.state == RuntimeLifecycleState.EXITED
        assert result.reason == RuntimeLifecycleReason.PROCESS_EXITED_NORMAL
        assert result.exit_code == 0

    def test_override_probe_missing(self):
        adapter = FakeRuntimeAdapter()
        adapter.set_probe_result(
            RuntimeProbeResult(
                alive=False,
                state=RuntimeLifecycleState.MISSING,
                reason=RuntimeLifecycleReason.HANDLE_LOST,
            ),
        )
        result = adapter.is_alive(
            handle=RuntimeHandle(handle_kind="fake", handle_value="pid:90001"),
        )
        assert result.state == RuntimeLifecycleState.MISSING
        assert result.reason == RuntimeLifecycleReason.HANDLE_LOST

    def test_override_probe_failed(self):
        adapter = FakeRuntimeAdapter()
        adapter.set_probe_result(
            RuntimeProbeResult(
                alive=None,
                state=RuntimeLifecycleState.PROBE_FAILED,
                reason=RuntimeLifecycleReason.PROBE_FAILED,
                error_summary="Simulated probe timeout",
            ),
        )
        result = adapter.is_alive(
            handle=RuntimeHandle(handle_kind="fake", handle_value="pid:90001"),
        )
        assert result.alive is None  # indeterminate
        assert result.state == RuntimeLifecycleState.PROBE_FAILED
        assert "timeout" in (result.error_summary or "")

    def test_reset_probe_override(self):
        adapter = FakeRuntimeAdapter()
        adapter.set_probe_result(
            RuntimeProbeResult(
                alive=False,
                state=RuntimeLifecycleState.EXITED,
                reason=RuntimeLifecycleReason.PROCESS_EXITED_ERROR,
                exit_code=1,
            ),
        )
        adapter.set_probe_result(None)
        result = adapter.is_alive(
            handle=RuntimeHandle(handle_kind="fake", handle_value="pid:90001"),
        )
        assert result.state == RuntimeLifecycleState.ALIVE


# ---------------------------------------------------------------------------
# FakeRuntimeAdapter — kill
# ---------------------------------------------------------------------------


class TestFakeAdapterKill:
    def test_kill_returns_exited_no_real_process(self):
        adapter = FakeRuntimeAdapter()
        handle = RuntimeHandle(handle_kind="fake", handle_value="pid:90001")
        result = adapter.kill(handle=handle)

        assert result.alive is False
        assert result.state == RuntimeLifecycleState.EXITED
        assert result.reason == RuntimeLifecycleReason.PROCESS_KILLED
        assert result.exit_code == -1
        assert "no real process" in (result.error_summary or "")


# ---------------------------------------------------------------------------
# FakeRuntimeAdapter — can_launch
# ---------------------------------------------------------------------------


class TestFakeAdapterCanLaunch:
    def test_can_launch_always_returns_true_in_fake_adapter(self):
        adapter = FakeRuntimeAdapter()
        assert adapter.can_launch(agent_type="openai_provider", runtime_type="subprocess") is True
        assert adapter.can_launch(agent_type="claude_code", runtime_type="tmux") is True
        assert adapter.can_launch(agent_type="", runtime_type="") is True

    def test_adapter_kind_is_fake(self):
        assert FakeRuntimeAdapter().adapter_kind() == "fake"


# ---------------------------------------------------------------------------
# Fake simulation safety boundary
# ---------------------------------------------------------------------------


class TestFakeRuntimeSimulationSafetyBoundary:
    def test_rejects_non_fake_runtime_adapter_before_any_adapter_method_call(self, tmp_path):
        context = _ready_context(tmp_path)
        dry_run = _ready_dry_run(tmp_path)
        proof = _passed_proof()
        adapter = _NonFakeRuntimeAdapter()

        try:
            run_fake_runtime_simulation(
                workspace_context=context,
                runtime_dry_run=dry_run,
                safe_command_proof=proof,
                runtime_adapter=adapter,
                agent_type="openai_provider",
                runtime_type="subprocess",
            )
            raise AssertionError("expected TypeError")
        except TypeError as exc:
            assert "only accepts FakeRuntimeAdapter" in str(exc)

        assert adapter.can_launch_called is False
        assert adapter.launch_called is False


# ---------------------------------------------------------------------------
# Gate chain — all passed
# ---------------------------------------------------------------------------


class TestGateChainAllPassed:
    def test_all_gates_passed_with_worktree_and_fake_adapter(self, tmp_path):
        context = _ready_context(tmp_path)
        dry_run = _ready_dry_run(tmp_path)
        proof = _passed_proof()
        adapter = FakeRuntimeAdapter()

        gate = check_runtime_launch_gates(
            workspace_context=context,
            runtime_dry_run=dry_run,
            safe_command_proof=proof,
            runtime_adapter=adapter,
            agent_type="openai_provider",
            runtime_type="subprocess",
        )

        assert gate.ready is True
        assert len(gate.gates_passed) == 5
        assert gate.gates_failed == []
        assert gate.blocking_reason_code is None
        assert gate.blocking_summary is None
        # P3-B1 safety flags — must all be False
        assert gate.execution_enabled is False
        assert gate.launches_ai_runtime is False
        assert gate.runs_git is False
        assert gate.runs_write_git is False
        assert gate.changes_process_cwd is False
        assert gate.runs_real_command is False

    def test_full_simulation_pipeline_all_gates_passed(self, tmp_path):
        context = _ready_context(tmp_path)
        dry_run = _ready_dry_run(tmp_path)
        proof = _passed_proof()
        adapter = FakeRuntimeAdapter()

        gate, launch = run_fake_runtime_simulation(
            workspace_context=context,
            runtime_dry_run=dry_run,
            safe_command_proof=proof,
            runtime_adapter=adapter,
            agent_type="openai_provider",
            runtime_type="subprocess",
        )

        assert gate.ready is True
        assert launch is not None
        assert launch.launched is True
        assert launch.handle is not None
        assert launch.handle.handle_kind == "fake"
        # Verify the handle was stored by the adapter
        probe = adapter.is_alive(handle=launch.handle)
        assert probe.state == RuntimeLifecycleState.ALIVE


# ---------------------------------------------------------------------------
# P3-C1 runtime lifecycle snapshot — no launch, no probe
# ---------------------------------------------------------------------------


class TestRuntimeLifecycleSnapshot:
    def test_ready_snapshot_records_gate_evidence_without_launch_or_probe(self, tmp_path):
        context = _ready_context(tmp_path)
        dry_run = _ready_dry_run(tmp_path)
        proof = _passed_proof()
        adapter = FakeRuntimeAdapter()

        gate = check_runtime_launch_gates(
            workspace_context=context,
            runtime_dry_run=dry_run,
            safe_command_proof=proof,
            runtime_adapter=adapter,
            agent_type="openai_provider",
            runtime_type="subprocess",
        )
        snapshot = build_runtime_lifecycle_snapshot(
            workspace_context=context,
            runtime_dry_run=dry_run,
            gate=gate,
            adapter_kind=adapter.adapter_kind(),
        )

        assert snapshot.ready is True
        assert snapshot.source == "runtime_lifecycle_snapshot_ready"
        assert snapshot.state == RuntimeLifecycleState.UNKNOWN
        assert snapshot.reason == RuntimeLifecycleReason.SNAPSHOT_ONLY
        assert snapshot.reason_code == "snapshot_only"
        assert snapshot.session_id == dry_run.session_id
        assert snapshot.adapter_kind == "fake"
        assert snapshot.runtime_handle_id is None
        assert snapshot.gates_passed == gate.gates_passed
        assert snapshot.gates_failed == []
        assert snapshot.launch_requested is False
        assert snapshot.fake_launch_started is False
        assert snapshot.real_runtime_started is False
        assert snapshot.runtime_probe_started is False
        assert snapshot.probe_state is None
        assert snapshot.execution_enabled is False
        assert snapshot.launches_ai_runtime is False
        assert "fake_launch_started=False" in snapshot.summary
        assert "runtime_probe_started=False" in snapshot.summary

    def test_blocked_snapshot_records_reason_without_launch_or_probe(self, tmp_path):
        context = _ready_context(tmp_path)
        proof = _passed_proof()
        adapter = FakeRuntimeAdapter()
        session = _session(
            workspace_path=tmp_path.as_posix(),
            workspace_clean=True,
            runtime_type=None,
        )
        dry_run = build_worker_runtime_launch_dry_run(
            agent_session=session,
            workspace_context=context,
        )

        gate = check_runtime_launch_gates(
            workspace_context=context,
            runtime_dry_run=dry_run,
            safe_command_proof=proof,
            runtime_adapter=adapter,
            agent_type="openai_provider",
            runtime_type=None,
        )
        snapshot = build_runtime_lifecycle_snapshot(
            workspace_context=context,
            runtime_dry_run=dry_run,
            gate=gate,
            adapter_kind=adapter.adapter_kind(),
        )

        assert snapshot.ready is False
        assert snapshot.source == "runtime_lifecycle_snapshot_blocked"
        assert snapshot.state == RuntimeLifecycleState.UNKNOWN
        assert snapshot.reason == RuntimeLifecycleReason.SNAPSHOT_ONLY
        assert snapshot.reason_code == "runtime_type_missing"
        assert snapshot.blocking_reason_code == "runtime_type_missing"
        assert snapshot.gates_failed == ["runtime_dry_run"]
        assert snapshot.runtime_handle_id is None
        assert snapshot.launch_requested is False
        assert snapshot.fake_launch_started is False
        assert snapshot.real_runtime_started is False
        assert snapshot.runtime_probe_started is False
        assert snapshot.probe_reason_code is None
        assert "controlled blocking evidence" in snapshot.summary


# ---------------------------------------------------------------------------
# Gate chain — workspace context blocked
# ---------------------------------------------------------------------------


class TestGateChainWorkspaceBlocked:
    def test_blocked_workspace_context_stops_at_g1(self, tmp_path):
        # Use a missing path to force workspace context not ready
        session = _session(
            workspace_path=(tmp_path / "missing-dir").as_posix(),
            workspace_clean=True,
        )
        validation = validate_worker_agent_workspace(session)
        context = resolve_worker_workspace_context(validation)
        assert context.ready is False  # precondition

        dry_run = build_worker_runtime_launch_dry_run(
            agent_session=session,
            workspace_context=context,
        )
        proof = _passed_proof()
        adapter = FakeRuntimeAdapter()

        gate = check_runtime_launch_gates(
            workspace_context=context,
            runtime_dry_run=dry_run,
            safe_command_proof=proof,
            runtime_adapter=adapter,
            agent_type="openai_provider",
            runtime_type="subprocess",
        )

        assert gate.ready is False
        assert "workspace_validation" in gate.gates_failed[0]
        assert gate.blocking_reason_code == "workspace_path_not_found"

    def test_non_worktree_session_blocked_at_g2(self, tmp_path):
        # IN_PLACE workspace: validation passes but uses_agent_workspace=False
        session = _session(workspace_type=WorkspaceType.IN_PLACE)
        validation = validate_worker_agent_workspace(session)
        context = resolve_worker_workspace_context(validation)
        assert context.ready is True
        assert context.uses_agent_workspace is False

        dry_run = build_worker_runtime_launch_dry_run(
            agent_session=session,
            workspace_context=context,
        )
        proof = _passed_proof()
        adapter = FakeRuntimeAdapter()

        gate = check_runtime_launch_gates(
            workspace_context=context,
            runtime_dry_run=dry_run,
            safe_command_proof=proof,
            runtime_adapter=adapter,
            agent_type="openai_provider",
            runtime_type="subprocess",
        )

        assert gate.ready is False
        assert "workspace_context" in gate.gates_failed[0]
        assert gate.blocking_reason_code == "agent_worktree_not_available"


# ---------------------------------------------------------------------------
# Gate chain — runtime dry-run blocked
# ---------------------------------------------------------------------------


class TestGateChainDryRunBlocked:
    def test_dry_run_not_ready_blocks_at_g3(self, tmp_path):
        context = _ready_context(tmp_path)
        proof = _passed_proof()
        adapter = FakeRuntimeAdapter()

        # Build a dry-run that is not ready (e.g. runtime_type missing)
        session = _session(
            workspace_path=tmp_path.as_posix(),
            workspace_clean=True,
            runtime_type=None,
        )
        dry_run = build_worker_runtime_launch_dry_run(
            agent_session=session,
            workspace_context=context,
        )
        assert dry_run.ready is False  # precondition

        gate = check_runtime_launch_gates(
            workspace_context=context,
            runtime_dry_run=dry_run,
            safe_command_proof=proof,
            runtime_adapter=adapter,
            agent_type="openai_provider",
            runtime_type=None,
        )

        assert gate.ready is False
        assert "runtime_dry_run" in gate.gates_failed[0]
        assert gate.blocking_reason_code == "runtime_type_missing"


# ---------------------------------------------------------------------------
# Gate chain — safe command proof blocked
# ---------------------------------------------------------------------------


class TestGateChainProofBlocked:
    def test_proof_failed_blocks_at_g4(self, tmp_path):
        context = _ready_context(tmp_path)
        dry_run = _ready_dry_run(tmp_path)
        proof = _failed_proof(reason_code="pwd_mismatch_workspace_path")
        adapter = FakeRuntimeAdapter()

        gate = check_runtime_launch_gates(
            workspace_context=context,
            runtime_dry_run=dry_run,
            safe_command_proof=proof,
            runtime_adapter=adapter,
            agent_type="openai_provider",
            runtime_type="subprocess",
        )

        assert gate.ready is False
        assert "safe_command_proof" in gate.gates_failed[0]
        assert gate.blocking_reason_code == "pwd_mismatch_workspace_path"

    def test_proof_failed_prevents_fake_launch_in_simulation(self, tmp_path):
        context = _ready_context(tmp_path)
        dry_run = _ready_dry_run(tmp_path)
        proof = _failed_proof(reason_code="safe_command_failed")
        adapter = FakeRuntimeAdapter()

        gate, launch = run_fake_runtime_simulation(
            workspace_context=context,
            runtime_dry_run=dry_run,
            safe_command_proof=proof,
            runtime_adapter=adapter,
            agent_type="openai_provider",
            runtime_type="subprocess",
        )

        assert gate.ready is False
        assert launch is None  # No launch when gate fails
        assert gate.execution_enabled is False

    def test_proof_timed_out_blocks_at_g4(self, tmp_path):
        context = _ready_context(tmp_path)
        dry_run = _ready_dry_run(tmp_path)
        timed_out_proof = WorkerWorktreeSafeCommandProof(
            ready=False,
            source="agent_session_worktree_safe_command_blocked",
            reason_code="safe_command_timed_out",
            command="pwd",
            cwd="/tmp/aido-worktree",
            expected_workspace_path="/tmp/aido-worktree",
            observed_pwd=None,
            pwd_matches_workspace_path=None,
            exit_code=124,
            stdout="",
            stderr="",
            timed_out=True,
            read_only=True,
            allowlisted=True,
            uses_agent_workspace=True,
            runs_command=True,
        )
        adapter = FakeRuntimeAdapter()

        gate = check_runtime_launch_gates(
            workspace_context=context,
            runtime_dry_run=dry_run,
            safe_command_proof=timed_out_proof,
            runtime_adapter=adapter,
            agent_type="openai_provider",
            runtime_type="subprocess",
        )

        assert gate.ready is False
        assert gate.blocking_reason_code == "safe_command_timed_out"


# ---------------------------------------------------------------------------
# Gate chain — adapter capability blocked
# ---------------------------------------------------------------------------


class TestGateChainAdapterBlocked:
    def test_no_adapter_blocks_at_g5(self, tmp_path):
        context = _ready_context(tmp_path)
        dry_run = _ready_dry_run(tmp_path)
        proof = _passed_proof()

        gate = check_runtime_launch_gates(
            workspace_context=context,
            runtime_dry_run=dry_run,
            safe_command_proof=proof,
            runtime_adapter=None,  # No adapter
            agent_type="openai_provider",
            runtime_type="subprocess",
        )

        assert gate.ready is False
        assert "adapter_capability" in gate.gates_failed[0]
        assert gate.blocking_reason_code == "adapter_unavailable"


# ---------------------------------------------------------------------------
# P3-B1 safety assertions
# ---------------------------------------------------------------------------


class TestP3B1Safety:
    def test_gate_result_always_has_execution_disabled(self, tmp_path):
        """Gate result must always have execution_enabled=False in P3-B1."""
        context = _ready_context(tmp_path)
        dry_run = _ready_dry_run(tmp_path)
        proof = _passed_proof()
        adapter = FakeRuntimeAdapter()

        gate = check_runtime_launch_gates(
            workspace_context=context,
            runtime_dry_run=dry_run,
            safe_command_proof=proof,
            runtime_adapter=adapter,
            agent_type="openai_provider",
            runtime_type="subprocess",
        )

        # Even when all gates pass, execution_enabled must be False
        assert gate.ready is True
        assert gate.execution_enabled is False
        assert gate.launches_ai_runtime is False
        assert gate.runs_real_command is False
        assert gate.changes_process_cwd is False
        assert gate.runs_git is False
        assert gate.runs_write_git is False

    def test_fake_adapter_never_calls_subprocess(self):
        """FakeRuntimeAdapter must not import subprocess or os.kill."""
        import inspect
        source = inspect.getsource(inspect.getmodule(FakeRuntimeAdapter))
        # The module-level source should not contain real process imports
        assert "import subprocess" not in source
        assert "from subprocess" not in source
        assert "os.kill" not in source
        assert "os.system" not in source

    def test_runtime_lifecycle_state_enum_values(self):
        """Verify the lifecycle state enum matches P3-A design."""
        states = set(RuntimeLifecycleState)
        assert states == {
            RuntimeLifecycleState.UNKNOWN,
            RuntimeLifecycleState.SPAWNING,
            RuntimeLifecycleState.ALIVE,
            RuntimeLifecycleState.EXITED,
            RuntimeLifecycleState.MISSING,
            RuntimeLifecycleState.PROBE_FAILED,
        }

    def test_runtime_lifecycle_reason_enum_values(self):
        """Verify the lifecycle reason enum has all expected categories."""
        reasons = set(RuntimeLifecycleReason)
        # Launch chain
        assert RuntimeLifecycleReason.LAUNCH_REQUESTED in reasons
        assert RuntimeLifecycleReason.LAUNCH_SUCCEEDED in reasons
        assert RuntimeLifecycleReason.LAUNCH_FAILED in reasons
        # Probe chain
        assert RuntimeLifecycleReason.PROBE_CONFIRMED_ALIVE in reasons
        assert RuntimeLifecycleReason.PROBE_FAILED in reasons
        assert RuntimeLifecycleReason.PROBE_RECOVERED in reasons
        # Exited chain
        assert RuntimeLifecycleReason.PROCESS_EXITED_NORMAL in reasons
        assert RuntimeLifecycleReason.PROCESS_EXITED_ERROR in reasons
        assert RuntimeLifecycleReason.PROCESS_KILLED in reasons
        # Missing chain
        assert RuntimeLifecycleReason.HANDLE_LOST in reasons
        assert RuntimeLifecycleReason.PROBE_LIMIT_EXHAUSTED in reasons
        # Adapter
        assert RuntimeLifecycleReason.ADAPTER_UNAVAILABLE in reasons
        assert RuntimeLifecycleReason.ADAPTER_LAUNCH_BLOCKED in reasons
