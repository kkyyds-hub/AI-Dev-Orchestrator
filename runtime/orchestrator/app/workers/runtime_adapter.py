"""P3-B1 Runtime adapter contract and fake runtime lifecycle simulation.

This module defines the minimum adapter seam between the worker and any future
AI runtime (subprocess / tmux / docker).  The :class:`FakeRuntimeAdapter` is an
**evidence-only** simulation: it never starts a real process, never runs
subprocess, never invokes an AI coding tool (Claude Code / Codex / DeepSeek /
OpenCode), and never modifies the filesystem.

P3-B1 deliberately keeps all real-execution flags (``execution_enabled``,
``launches_runtime``, ``runs_command``) at ``False``, preserving the P2 safety
conclusion that "prove you can, but don't execute."

.. code-block:: text

   P2 safety contract still holds:
   - execution_enabled = False
   - launches_runtime = False
   - runs_git = False
   - runs_write_git = False
   - changes_process_cwd = False

   AI runtime automatic coding: Not started
   Git add / commit / push / PR product loop: Not started
   AI Project Director total closure: Partial
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4


# ---------------------------------------------------------------------------
# Lifecycle state and reason enums
# ---------------------------------------------------------------------------


class RuntimeLifecycleState(StrEnum):
    """P3-A runtime-axis lifecycle states."""

    UNKNOWN = "unknown"
    SPAWNING = "spawning"
    ALIVE = "alive"
    EXITED = "exited"
    MISSING = "missing"
    PROBE_FAILED = "probe_failed"


class RuntimeLifecycleReason(StrEnum):
    """P3-A runtime-axis transition reason codes."""

    # spawning chain
    LAUNCH_REQUESTED = "launch_requested"
    LAUNCH_SUCCEEDED = "launch_succeeded"
    LAUNCH_FAILED = "launch_failed"

    # alive / probe chain
    PROBE_CONFIRMED_ALIVE = "probe_confirmed_alive"
    PROBE_FAILED = "probe_failed"
    PROBE_RECOVERED = "probe_recovered"

    # exited chain
    PROCESS_EXITED_NORMAL = "process_exited_normal"
    PROCESS_EXITED_ERROR = "process_exited_error"
    PROCESS_KILLED = "process_killed"

    # missing chain
    HANDLE_LOST = "handle_lost"
    PROBE_LIMIT_EXHAUSTED = "probe_limit_exhausted"

    # adapter
    ADAPTER_UNAVAILABLE = "adapter_unavailable"
    ADAPTER_LAUNCH_BLOCKED = "adapter_launch_blocked"


# ---------------------------------------------------------------------------
# Runtime handle
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class RuntimeHandle:
    """Opaque handle that uniquely identifies a launched runtime process.

    P3-B1 ``handle_kind`` values are:
    - ``"fake"`` — produced by :class:`FakeRuntimeAdapter`; never backed by a
      real OS process.
    - ``"subprocess"`` — PID-based (future P3-B real launch).
    - ``"tmux"`` — tmux session name (future extension).
    - ``"docker"`` — container ID (future extension).

    The ``handle_value`` is the concrete identifier, e.g. ``"99999"`` for
    fake, ``"48291"`` for a PID, ``"aido-session-abc123"`` for tmux.
    """

    handle_kind: str
    handle_value: str

    def to_string(self) -> str:
        """Canonical string form consumed by ``AgentSession.runtime_handle_id``.

        Example: ``"fake:pid:99999"``, ``"pid:48291"``.
        """
        return f"{self.handle_kind}:{self.handle_value}"

    @classmethod
    def from_string(cls, value: str) -> RuntimeHandle:
        """Parse a canonical handle string back into a :class:`RuntimeHandle`."""
        if ":" not in value:
            raise ValueError(
                f"RuntimeHandle string must have kind:value format, got: {value!r}"
            )
        kind, rest = value.split(":", 1)
        return cls(handle_kind=kind, handle_value=rest)


# ---------------------------------------------------------------------------
# Launch request / result
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class RuntimeLaunchRequest:
    """Immutable launch parameters consumed by :meth:`RuntimeAdapter.launch`.

    ``workspace_path`` is the resolved absolute path from
    :class:`~app.workers.task_worker.WorkerWorkspaceContextResolution`.
    """

    session_id: str
    agent_type: str
    runtime_type: str
    workspace_path: str


@dataclass(slots=True, frozen=True)
class RuntimeLaunchResult:
    """Outcome of a :meth:`RuntimeAdapter.launch` call."""

    launched: bool
    handle: RuntimeHandle | None
    error_summary: str | None = None
    reason_code: RuntimeLifecycleReason | None = None


@dataclass(slots=True, frozen=True)
class RuntimeProbeResult:
    """Outcome of a :meth:`RuntimeAdapter.is_alive` call."""

    alive: bool | None  # None = probe_failed (indeterminate)
    state: RuntimeLifecycleState
    reason: RuntimeLifecycleReason
    exit_code: int | None = None
    error_summary: str | None = None


# ---------------------------------------------------------------------------
# Runtime adapter abstract contract
# ---------------------------------------------------------------------------


class RuntimeAdapter(ABC):
    """Abstract seam between the worker and a runtime execution environment.

    Concrete adapters implement how to launch, probe, and kill a runtime
    process.  P3-B1 supplies exactly one concrete implementation:
    :class:`FakeRuntimeAdapter`, which simulates all operations without
    touching the OS process table.
    """

    @abstractmethod
    def adapter_kind(self) -> str:
        """Return a stable identifier for this adapter (e.g. ``"fake"``)."""
        ...

    @abstractmethod
    def can_launch(
        self,
        *,
        agent_type: str,
        runtime_type: str,
    ) -> bool:
        """Return ``True`` when this adapter supports the given pairing.

        P3-B1 implementations must be conservative: return ``False`` for any
        combination the adapter is not explicitly designed for.
        """
        ...

    @abstractmethod
    def launch(
        self,
        *,
        request: RuntimeLaunchRequest,
    ) -> RuntimeLaunchResult:
        """Start a runtime process and return an opaque handle.

        **P3-B1 safety contract** — concrete implementations must NOT:
        - invoke ``subprocess.Popen`` with a real AI coding tool
        - start tmux / docker sessions
        - modify the filesystem
        - change the process working directory
        """
        ...

    @abstractmethod
    def is_alive(
        self,
        *,
        handle: RuntimeHandle,
    ) -> RuntimeProbeResult:
        """Probe whether a previously launched runtime is still running.

        **P3-B1 safety contract** — concrete implementations must NOT:
        - run ``ps`` / ``docker ps`` / ``tmux ls`` against real processes
        - interact with the OS process table in any way
        """
        ...

    @abstractmethod
    def kill(
        self,
        *,
        handle: RuntimeHandle,
    ) -> RuntimeProbeResult:
        """Terminate a running runtime process.

        **P3-B1 safety contract** — concrete implementations must NOT:
        - send OS signals (SIGTERM / SIGKILL)
        - kill tmux sessions or docker containers
        """
        ...


# ---------------------------------------------------------------------------
# Fake runtime adapter (evidence-only simulation)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class FakeRuntimeAdapter(RuntimeAdapter):
    """Evidence-only runtime adapter that never starts a real process.

    Every method returns deterministic, controllable data that exercises the
    runtime lifecycle state machine without touching the OS.  This adapter
    exists purely to prove that the gate chain, handle management, and probe
    state transitions work correctly end-to-end.

    **P3-B1 is NOT a real runtime.**  All real-execution flags remain
    ``False``.  The fake adapter can be replaced by a real subprocess/tmux/
    docker adapter in a future phase without changing the contract.
    """

    _next_fake_pid: int = field(default=90000, init=False)
    _probe_result_override: RuntimeProbeResult | None = field(default=None, init=False)

    # -- adapter metadata ---------------------------------------------------

    def adapter_kind(self) -> str:
        return "fake"

    def can_launch(
        self,
        *,
        agent_type: str,
        runtime_type: str,
    ) -> bool:
        """The fake adapter accepts any ``agent_type`` + ``runtime_type`` pairing.

        A real adapter (P3-B future) would validate against known capabilities,
        e.g. only ``subprocess`` for ``openai_provider``.
        """
        # P3-B1: accept everything so we can exercise the gate chain without
        # coupling to a real runtime.  The gate function is still responsible
        # for checking the *real* availability of the adapter.
        return True

    def launch(
        self,
        *,
        request: RuntimeLaunchRequest,
    ) -> RuntimeLaunchResult:
        """Simulate a launch without starting any OS process.

        Returns a fake handle ``fake:pid:NNNNN`` and clears any probe override
        to the default ``alive`` state.
        """
        pid = self._next_fake_pid
        self._next_fake_pid += 1
        handle = RuntimeHandle(handle_kind="fake", handle_value=f"pid:{pid}")
        # After a successful launch the next probe should report alive unless
        # the test explicitly overrides it.
        self._probe_result_override = None
        return RuntimeLaunchResult(
            launched=True,
            handle=handle,
            reason_code=RuntimeLifecycleReason.LAUNCH_SUCCEEDED,
        )

    def is_alive(
        self,
        *,
        handle: RuntimeHandle,
    ) -> RuntimeProbeResult:
        """Return a controllable fake probe result.

        By default returns ``alive``.  Call :meth:`set_probe_result` first to
        simulate ``exited``, ``missing``, or ``probe_failed``.
        """
        if self._probe_result_override is not None:
            return self._probe_result_override
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
        """Simulate process termination without sending any OS signal.

        Always returns ``exited`` with the ``PROCESS_KILLED`` reason.
        """
        return RuntimeProbeResult(
            alive=False,
            state=RuntimeLifecycleState.EXITED,
            reason=RuntimeLifecycleReason.PROCESS_KILLED,
            exit_code=-1,
            error_summary="Fake adapter simulated kill (no real process).",
        )

    def set_probe_result(self, result: RuntimeProbeResult | None) -> None:
        """Override the next :meth:`is_alive` return value.

        Pass ``None`` to reset to the default (alive).  Tests use this to
        drive the lifecycle state machine without real process manipulation.
        """
        self._probe_result_override = result


# ---------------------------------------------------------------------------
# Runtime launch gate aggregation
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class RuntimeLaunchGateResult:
    """Aggregate result of the P3-A gate chain (G1–G5).

    Consumed by the worker to decide whether the runtime lifecycle simulation
    can proceed (P3-B1) or, in a future phase, whether a real runtime process
    should be launched.
    """

    ready: bool
    """``True`` when every gate passed."""

    gates_passed: list[str] = field(default_factory=list)
    """Names of gates that passed, in evaluation order."""

    gates_failed: list[str] = field(default_factory=list)
    """Names of gates that failed, in evaluation order."""

    blocking_reason_code: str | None = None
    """``reason_code`` from the first failing gate, if any."""

    blocking_summary: str | None = None
    """Human-readable summary of the first blocking gate."""

    # -- P3-B1 hard safety flags --------------------------------------------
    # These must remain False throughout P3-B1.  They are present on the gate
    # result so that every caller — worker, API, tests — can trivially assert
    # that no real runtime has been engaged.

    changes_process_cwd: bool = False
    """P3-B1: always ``False``.  Real cwd changes are reserved for P3-B+."""

    runs_real_command: bool = False
    """P3-B1: always ``False``.  Real subprocess launches are reserved for P3-B+."""

    runs_git: bool = False
    """P3-B1: always ``False``.  Git commands are reserved for P4+."""

    runs_write_git: bool = False
    """P3-B1: always ``False``.  Git write commands are reserved for P4+."""

    launches_ai_runtime: bool = False
    """P3-B1: always ``False``.  AI runtime launch is reserved for P3-B+."""

    execution_enabled: bool = False
    """P3-B1: always ``False``.  Real execution is reserved for P3-B+."""


def _human_readable_gate_name(gate_index: int) -> str:
    return {
        1: "workspace_validation",
        2: "workspace_context",
        3: "runtime_dry_run",
        4: "safe_command_proof",
        5: "adapter_capability",
    }.get(gate_index, f"gate_{gate_index}")


def check_runtime_launch_gates(
    *,
    workspace_context,        # WorkerWorkspaceContextResolution
    runtime_dry_run,          # WorkerRuntimeLaunchDryRun
    safe_command_proof,       # WorkerWorktreeSafeCommandProof
    runtime_adapter: RuntimeAdapter | None = None,
    agent_type: str | None = None,
    runtime_type: str | None = None,
) -> RuntimeLaunchGateResult:
    """Evaluate the P3-A gate chain (G1–G5) without launching a runtime.

    **P3-B1 scope**: This function checks whether preconditions for a
    (simulated) runtime launch are met.  It does **not** call
    :meth:`RuntimeAdapter.launch`.  The returned
    :class:`RuntimeLaunchGateResult` always has ``execution_enabled=False``
    and all safety flags at ``False``.

    Gates (in order):
    1. workspace validation — ``workspace_context.ready``
    2. workspace context — ``workspace_context.uses_agent_workspace``
    3. runtime dry-run — ``runtime_dry_run.ready``
    4. safe command proof — ``safe_command_proof.ready``
    5. adapter capability — ``runtime_adapter.can_launch(agent_type, runtime_type)``
    """
    gates_passed: list[str] = []
    gates_failed: list[str] = []
    blocking_reason_code: str | None = None
    blocking_summary: str | None = None

    # -- G1: workspace validation -------------------------------------------
    if not workspace_context.ready:
        g1_name = _human_readable_gate_name(1)
        gates_failed.append(g1_name)
        blocking_reason_code = workspace_context.reason_code or "workspace_context_not_ready"
        blocking_summary = "Workspace context is not ready for runtime launch."
        return RuntimeLaunchGateResult(
            ready=False,
            gates_passed=gates_passed,
            gates_failed=gates_failed,
            blocking_reason_code=blocking_reason_code,
            blocking_summary=blocking_summary,
        )
    gates_passed.append(_human_readable_gate_name(1))

    # -- G2: workspace context (agent worktree check) -----------------------
    if not workspace_context.uses_agent_workspace:
        g2_name = _human_readable_gate_name(2)
        gates_failed.append(g2_name)
        blocking_reason_code = "agent_worktree_not_available"
        blocking_summary = (
            "Agent session is not bound to a clean worktree; "
            "runtime launch requires an active agent workspace."
        )
        return RuntimeLaunchGateResult(
            ready=False,
            gates_passed=gates_passed,
            gates_failed=gates_failed,
            blocking_reason_code=blocking_reason_code,
            blocking_summary=blocking_summary,
        )
    gates_passed.append(_human_readable_gate_name(2))

    # -- G3: runtime dry-run ------------------------------------------------
    if not runtime_dry_run.ready:
        g3_name = _human_readable_gate_name(3)
        gates_failed.append(g3_name)
        blocking_reason_code = runtime_dry_run.reason_code or "runtime_dry_run_not_ready"
        blocking_summary = (
            "Runtime launch dry-run configuration is not ready; "
            "agent_type / runtime_type / workspace_path may be missing."
        )
        return RuntimeLaunchGateResult(
            ready=False,
            gates_passed=gates_passed,
            gates_failed=gates_failed,
            blocking_reason_code=blocking_reason_code,
            blocking_summary=blocking_summary,
        )
    gates_passed.append(_human_readable_gate_name(3))

    # -- G4: safe command proof (P2-D) --------------------------------------
    if not safe_command_proof.ready:
        g4_name = _human_readable_gate_name(4)
        gates_failed.append(g4_name)
        blocking_reason_code = safe_command_proof.reason_code or "worktree_safe_command_proof_not_ready"
        blocking_summary = (
            "Worker worktree safe command proof (pwd) failed or is not ready; "
            "cwd proof is required before runtime launch."
        )
        return RuntimeLaunchGateResult(
            ready=False,
            gates_passed=gates_passed,
            gates_failed=gates_failed,
            blocking_reason_code=blocking_reason_code,
            blocking_summary=blocking_summary,
        )
    gates_passed.append(_human_readable_gate_name(4))

    # -- G5: adapter capability ---------------------------------------------
    if runtime_adapter is None:
        g5_name = _human_readable_gate_name(5)
        gates_failed.append(g5_name)
        blocking_reason_code = RuntimeLifecycleReason.ADAPTER_UNAVAILABLE.value
        blocking_summary = "No runtime adapter is configured; cannot launch runtime."
        return RuntimeLaunchGateResult(
            ready=False,
            gates_passed=gates_passed,
            gates_failed=gates_failed,
            blocking_reason_code=blocking_reason_code,
            blocking_summary=blocking_summary,
        )

    if not runtime_adapter.can_launch(
        agent_type=agent_type or "",
        runtime_type=runtime_type or "",
    ):
        g5_name = _human_readable_gate_name(5)
        gates_failed.append(g5_name)
        blocking_reason_code = RuntimeLifecycleReason.ADAPTER_LAUNCH_BLOCKED.value
        blocking_summary = (
            f"Runtime adapter '{runtime_adapter.adapter_kind()}' cannot launch "
            f"agent_type={agent_type}, runtime_type={runtime_type}."
        )
        return RuntimeLaunchGateResult(
            ready=False,
            gates_passed=gates_passed,
            gates_failed=gates_failed,
            blocking_reason_code=blocking_reason_code,
            blocking_summary=blocking_summary,
        )
    gates_passed.append(_human_readable_gate_name(5))

    # -- All gates passed ---------------------------------------------------
    # P3-B1 still does NOT launch a real runtime.  The caller decides whether
    # to proceed with a fake launch or stop.
    return RuntimeLaunchGateResult(
        ready=True,
        gates_passed=gates_passed,
        gates_failed=gates_failed,
        blocking_reason_code=None,
        blocking_summary=None,
    )


# ---------------------------------------------------------------------------
# Convenience: run the full P3-B1 fake simulation pipeline
# ---------------------------------------------------------------------------


def run_fake_runtime_simulation(
    *,
    workspace_context,       # WorkerWorkspaceContextResolution
    runtime_dry_run,         # WorkerRuntimeLaunchDryRun
    safe_command_proof,      # WorkerWorktreeSafeCommandProof
    runtime_adapter: RuntimeAdapter | None = None,
    agent_type: str | None = None,
    runtime_type: str | None = None,
) -> tuple[RuntimeLaunchGateResult, RuntimeLaunchResult | None]:
    """Evaluate gate chain and optionally perform a **fake** launch.

    This is the P3-B1 reference pipeline:

    1. Call :func:`check_runtime_launch_gates`.
    2. If gates pass **and** a ``runtime_adapter`` is provided, call
       ``runtime_adapter.launch()`` with a fake-only adapter.
    3. Return the gate result and (if applicable) the fake launch result.

    **P3-B1 safety**: the returned launch result is always from a
    :class:`FakeRuntimeAdapter`.  No real process is ever started by this
    function or its callees.

    Returns
    -------
    tuple[RuntimeLaunchGateResult, RuntimeLaunchResult | None]
        The gate result and an optional fake launch result.
    """
    gate = check_runtime_launch_gates(
        workspace_context=workspace_context,
        runtime_dry_run=runtime_dry_run,
        safe_command_proof=safe_command_proof,
        runtime_adapter=runtime_adapter,
        agent_type=agent_type,
        runtime_type=runtime_type,
    )

    if not gate.ready:
        return gate, None

    # P3-B1: even when gates pass, only perform a FAKE launch.
    # Real launch is gated behind execution_enabled=True in a future phase.
    if runtime_adapter is None:
        return gate, None

    request = RuntimeLaunchRequest(
        session_id=runtime_dry_run.session_id or "",
        agent_type=runtime_dry_run.agent_type or agent_type or "",
        runtime_type=runtime_dry_run.runtime_type or runtime_type or "",
        workspace_path=runtime_dry_run.launch_cwd_preview
        or workspace_context.resolved_workspace_path
        or "",
    )
    fake_launch = runtime_adapter.launch(request=request)
    return gate, fake_launch
