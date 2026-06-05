"""AgentSession runtime lifecycle snapshot domain model for P3-C1.

This module is intentionally independent from worker runtime adapters.  It
derives a read-only runtime lifecycle snapshot from persisted AgentSession
fields only, without launching, fake-launching, probing, or killing any runtime.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from app.domain._base import DomainModel
from app.domain.agent_session import (
    AgentSession,
    CodingSessionActivityState,
    CodingSessionStatus,
)


class AgentSessionRuntimeLifecycleState(StrEnum):
    """Runtime-axis lifecycle states exposed on AgentSession snapshots.

    Keep this naming aligned with the runtime-axis design and runtime adapter
    contract.  P3-C1 is evidence-only, so persisted coding/activity fields are
    not promoted to ``alive``/``exited`` without a launch/probe signal.
    """

    UNKNOWN = "unknown"
    SPAWNING = "spawning"
    ALIVE = "alive"
    EXITED = "exited"
    MISSING = "missing"
    PROBE_FAILED = "probe_failed"


class AgentSessionRuntimeLifecycleReason(StrEnum):
    """Runtime-axis reason codes for AgentSession lifecycle snapshots."""

    HANDLE_NOT_ASSIGNED = "handle_not_assigned"
    HANDLE_RECORDED_NO_PROBE = "handle_recorded_no_probe"
    SNAPSHOT_ONLY_NO_RUNTIME_PROBE = "snapshot_only_no_runtime_probe"


class AgentSessionDerivedLifecycleState(StrEnum):
    """Session-axis state derived from persisted AgentSession fields."""

    NOT_STARTED = "not_started"
    WORKING = "working"
    IDLE = "idle"
    NEEDS_INPUT = "needs_input"
    STUCK = "stuck"
    DONE = "done"
    TERMINATED = "terminated"


class AgentSessionDerivedLifecycleReason(StrEnum):
    """Reason codes for the session-axis derived lifecycle fields."""

    SESSION_CREATED = "session_created"
    CODING_WORKING = "coding_working"
    CODING_IDLE = "coding_idle"
    CODING_NEEDS_INPUT = "coding_needs_input"
    CODING_STUCK = "coding_stuck"
    CODING_COMPLETED = "coding_completed"
    CODING_FAILED = "coding_failed"
    CODING_TERMINATED = "coding_terminated"
    ACTIVITY_BLOCKED = "activity_blocked"
    ACTIVITY_EXITED = "activity_exited"


class AgentSessionRuntimeLifecycleSnapshot(DomainModel):
    """Read-only runtime lifecycle snapshot derived from one AgentSession."""

    session_id: UUID
    project_id: UUID
    task_id: UUID
    run_id: UUID
    state: AgentSessionRuntimeLifecycleState
    reason: AgentSessionRuntimeLifecycleReason
    session_lifecycle_state: AgentSessionDerivedLifecycleState
    session_lifecycle_reason: AgentSessionDerivedLifecycleReason
    summary: str = Field(max_length=2_000)
    agent_type: str | None = None
    runtime_type: str | None = None
    runtime_handle_id: str | None = Field(default=None, max_length=200)
    coding_status: str | None = None
    activity_state: str | None = None
    runtime_observed: bool = False
    runtime_handle_recorded: bool = False
    runtime_probe_started: bool = False
    fake_launch_started: bool = False
    real_runtime_started: bool = False
    execution_enabled: bool = False
    launches_ai_runtime: bool = False
    runs_real_command: bool = False
    changes_process_cwd: bool = False
    runs_git: bool = False
    runs_write_git: bool = False


def build_agent_session_runtime_lifecycle_snapshot(
    session: AgentSession,
) -> AgentSessionRuntimeLifecycleSnapshot:
    """Build a P3-C1 runtime lifecycle snapshot from persisted session fields.

    The function is pure and evidence-only.  It does not import worker runtime
    adapters, does not call fake launch helpers, and does not run runtime probes.
    """

    state, reason = _derive_runtime_state_and_reason(session)
    session_lifecycle_state, session_lifecycle_reason = (
        _derive_session_lifecycle_state_and_reason(session)
    )
    runtime_handle_recorded = session.runtime_handle_id is not None
    runtime_observed = runtime_handle_recorded or session.coding_status is not None
    summary = _build_summary(
        state=state,
        reason=reason,
        session_lifecycle_state=session_lifecycle_state,
        session_lifecycle_reason=session_lifecycle_reason,
        runtime_handle_recorded=runtime_handle_recorded,
    )

    return AgentSessionRuntimeLifecycleSnapshot(
        session_id=session.id,
        project_id=session.project_id,
        task_id=session.task_id,
        run_id=session.run_id,
        state=state,
        reason=reason,
        session_lifecycle_state=session_lifecycle_state,
        session_lifecycle_reason=session_lifecycle_reason,
        summary=summary,
        agent_type=session.agent_type.value if session.agent_type is not None else None,
        runtime_type=(
            session.runtime_type.value if session.runtime_type is not None else None
        ),
        runtime_handle_id=session.runtime_handle_id,
        coding_status=(
            session.coding_status.value if session.coding_status is not None else None
        ),
        activity_state=(
            session.activity_state.value if session.activity_state is not None else None
        ),
        runtime_observed=runtime_observed,
        runtime_handle_recorded=runtime_handle_recorded,
        runtime_probe_started=False,
        fake_launch_started=False,
        real_runtime_started=False,
        execution_enabled=False,
        launches_ai_runtime=False,
        runs_real_command=False,
        changes_process_cwd=False,
        runs_git=False,
        runs_write_git=False,
    )


def _derive_runtime_state_and_reason(
    session: AgentSession,
) -> tuple[
    AgentSessionRuntimeLifecycleState,
    AgentSessionRuntimeLifecycleReason,
]:
    """Derive runtime-axis state/reason without starting or probing runtime.

    P3-C1 intentionally cannot prove ``alive``, ``exited``, ``missing`` or
    ``probe_failed``.  It only reports whether a runtime handle has already
    been recorded while keeping the runtime lifecycle state at ``unknown``.
    The coding/activity lifecycle is exposed separately via
    ``session_lifecycle_state`` and ``session_lifecycle_reason``.
    """

    if session.runtime_handle_id is not None:
        return (
            AgentSessionRuntimeLifecycleState.UNKNOWN,
            AgentSessionRuntimeLifecycleReason.HANDLE_RECORDED_NO_PROBE,
        )
    if session.coding_status is not None or session.activity_state is not None:
        return (
            AgentSessionRuntimeLifecycleState.UNKNOWN,
            AgentSessionRuntimeLifecycleReason.SNAPSHOT_ONLY_NO_RUNTIME_PROBE,
        )
    return (
        AgentSessionRuntimeLifecycleState.UNKNOWN,
        AgentSessionRuntimeLifecycleReason.HANDLE_NOT_ASSIGNED,
    )


def _derive_session_lifecycle_state_and_reason(
    session: AgentSession,
) -> tuple[
    AgentSessionDerivedLifecycleState,
    AgentSessionDerivedLifecycleReason,
]:
    """Derive session-axis lifecycle state/reason from coding/activity fields."""

    if session.activity_state == CodingSessionActivityState.BLOCKED:
        return (
            AgentSessionDerivedLifecycleState.STUCK,
            AgentSessionDerivedLifecycleReason.ACTIVITY_BLOCKED,
        )
    if session.activity_state == CodingSessionActivityState.EXITED:
        return (
            AgentSessionDerivedLifecycleState.TERMINATED,
            AgentSessionDerivedLifecycleReason.ACTIVITY_EXITED,
        )

    match session.coding_status:
        case CodingSessionStatus.SPAWNING:
            return (
                AgentSessionDerivedLifecycleState.NOT_STARTED,
                AgentSessionDerivedLifecycleReason.SESSION_CREATED,
            )
        case CodingSessionStatus.WORKING:
            return (
                AgentSessionDerivedLifecycleState.WORKING,
                AgentSessionDerivedLifecycleReason.CODING_WORKING,
            )
        case CodingSessionStatus.IDLE:
            return (
                AgentSessionDerivedLifecycleState.IDLE,
                AgentSessionDerivedLifecycleReason.CODING_IDLE,
            )
        case CodingSessionStatus.NEEDS_INPUT:
            return (
                AgentSessionDerivedLifecycleState.NEEDS_INPUT,
                AgentSessionDerivedLifecycleReason.CODING_NEEDS_INPUT,
            )
        case CodingSessionStatus.STUCK:
            return (
                AgentSessionDerivedLifecycleState.STUCK,
                AgentSessionDerivedLifecycleReason.CODING_STUCK,
            )
        case CodingSessionStatus.COMPLETED:
            return (
                AgentSessionDerivedLifecycleState.DONE,
                AgentSessionDerivedLifecycleReason.CODING_COMPLETED,
            )
        case CodingSessionStatus.FAILED:
            return (
                AgentSessionDerivedLifecycleState.TERMINATED,
                AgentSessionDerivedLifecycleReason.CODING_FAILED,
            )
        case CodingSessionStatus.TERMINATED:
            return (
                AgentSessionDerivedLifecycleState.TERMINATED,
                AgentSessionDerivedLifecycleReason.CODING_TERMINATED,
            )
        case _:
            return (
                AgentSessionDerivedLifecycleState.NOT_STARTED,
                AgentSessionDerivedLifecycleReason.SESSION_CREATED,
            )


def _build_summary(
    *,
    state: AgentSessionRuntimeLifecycleState,
    reason: AgentSessionRuntimeLifecycleReason,
    session_lifecycle_state: AgentSessionDerivedLifecycleState,
    session_lifecycle_reason: AgentSessionDerivedLifecycleReason,
    runtime_handle_recorded: bool,
) -> str:
    """Build stable human-readable summary for API consumers."""

    return (
        "AgentSession runtime lifecycle snapshot is evidence-only and keeps "
        "runtime-axis state separate from coding/session state; "
        f"runtime_state={state.value}; runtime_reason={reason.value}; "
        f"session_lifecycle_state={session_lifecycle_state.value}; "
        f"session_lifecycle_reason={session_lifecycle_reason.value}; "
        f"runtime_handle_recorded={runtime_handle_recorded}; "
        "fake_launch_started=False; real_runtime_started=False; "
        "runtime_probe_started=False."
    )
