from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.external_executors.actual_contract import (
    RealExecutorAdapterProtocol,
    RealExecutorLaunchContext,
    RealExecutorOperationStatus,
    RealExecutorPollState,
    RealExecutorSafetyBoundary,
)
from app.external_executors.actual_process_adapter import (
    PROCESS_ADAPTER_GATE_REASON,
    RealExecutorProcessAdapter,
)


PROCESS_ADAPTER_FILE = Path("app/external_executors/actual_process_adapter.py")


def _source() -> str:
    return PROCESS_ADAPTER_FILE.read_text()


def _module() -> ast.Module:
    return ast.parse(_source())


def _passing_boundary() -> RealExecutorSafetyBoundary:
    return RealExecutorSafetyBoundary(
        feature_flag_enabled=True,
        human_confirmation_present=True,
        executor_readiness_available=True,
        workspace_worktree_gate_passed=True,
        budget_cost_gate_passed=True,
        concurrency_gate_passed=True,
        timeout_supported=True,
        cancel_supported=True,
        kill_supported=True,
        audit_events_append_only=True,
        credential_exposure_blocked=True,
        environment_dump_blocked=True,
    )


def _context(
    *,
    executor_label: str = "Codex",
    boundary: RealExecutorSafetyBoundary | None = None,
) -> RealExecutorLaunchContext:
    return RealExecutorLaunchContext(
        request_id="request-1",
        executor_label=executor_label,
        command_summary="prepare guarded launch skeleton",
        workspace_hint="registered worktree",
        safety_boundary=boundary or RealExecutorSafetyBoundary(),
    )


def test_process_adapter_file_lives_under_external_executors() -> None:
    assert PROCESS_ADAPTER_FILE.is_file()
    assert PROCESS_ADAPTER_FILE.parts[:2] == ("app", "external_executors")


def test_process_adapter_exists_and_matches_protocol_shape() -> None:
    adapter = RealExecutorProcessAdapter()

    assert isinstance(adapter, RealExecutorAdapterProtocol)
    assert hasattr(adapter, "launch")
    assert hasattr(adapter, "poll")
    assert hasattr(adapter, "cancel")
    assert hasattr(adapter, "kill")
    assert hasattr(adapter, "cleanup")


@pytest.mark.parametrize("executor_label", ["Codex", "codex", "Claude Code", "claude-code"])
def test_launch_is_blocked_for_supported_labels_when_default_gates_fail(
    executor_label: str,
) -> None:
    result = RealExecutorProcessAdapter().launch(_context(executor_label=executor_label))

    assert result.status is RealExecutorOperationStatus.BLOCKED
    assert result.session_id is None
    assert PROCESS_ADAPTER_GATE_REASON in result.blocking_reasons
    assert "feature_flag_disabled" in result.blocking_reasons
    assert result.product_runtime_git_write_allowed is False


def test_launch_creates_noop_launch_pending_session_only_when_all_gates_pass() -> None:
    adapter = RealExecutorProcessAdapter()

    result = adapter.launch(_context(boundary=_passing_boundary()))

    assert result.status is RealExecutorOperationStatus.ACCEPTED
    assert result.session_id == "real-executor-session-request-1"
    assert result.blocking_reasons == []
    assert result.product_runtime_git_write_allowed is False
    assert "started" not in (result.message or "").lower()
    assert "pushed" not in (result.message or "").lower()
    assert "merge" not in (result.message or "").lower()

    snapshot = adapter.poll(result.session_id or "")
    assert snapshot.poll_state is RealExecutorPollState.LAUNCH_PENDING
    assert snapshot.executor_label == "Codex"
    assert snapshot.product_runtime_git_write_allowed is False


def test_poll_cancel_kill_and_cleanup_are_controlled_session_state_readback() -> None:
    adapter = RealExecutorProcessAdapter()
    session_id = adapter.launch(_context(boundary=_passing_boundary())).session_id
    assert session_id is not None

    cancel_result = adapter.cancel(session_id, "operator requested stop")
    assert cancel_result.status is RealExecutorOperationStatus.COMPLETED
    assert cancel_result.product_runtime_git_write_allowed is False
    assert adapter.poll(session_id).poll_state is RealExecutorPollState.CANCELLED

    kill_result = adapter.kill(session_id, "operator requested stop")
    assert kill_result.status is RealExecutorOperationStatus.COMPLETED
    assert kill_result.product_runtime_git_write_allowed is False
    assert adapter.poll(session_id).poll_state is RealExecutorPollState.KILLED

    cleanup_result = adapter.cleanup(session_id)
    assert cleanup_result.status is RealExecutorOperationStatus.COMPLETED
    assert cleanup_result.product_runtime_git_write_allowed is False
    assert adapter.poll(session_id).poll_state is RealExecutorPollState.CLEANED_UP


@pytest.mark.parametrize("operation", ["cancel", "kill", "cleanup"])
def test_lifecycle_operations_return_not_found_for_unknown_sessions(operation: str) -> None:
    adapter = RealExecutorProcessAdapter()
    method = getattr(adapter, operation)

    if operation == "cleanup":
        result = method("missing-session")
    else:
        result = method("missing-session", "operator requested stop")

    assert result.status is RealExecutorOperationStatus.NOT_FOUND
    assert result.product_runtime_git_write_allowed is False
    assert "session_not_found" in result.blocking_reasons


def test_process_adapter_does_not_import_process_env_or_forbidden_runtime_layers() -> None:
    source = _source()

    for snippet in {
        "app.api",
        "app.workers",
        "app.repositories",
        "import os",
        "from os",
        "import subprocess",
        "from subprocess",
        "environ",
        "getenv",
        "Popen",
        "create_subprocess",
        "shell=True",
        "stdout",
        "stderr",
        "api_key",
        "auth_token",
        "password",
    }:
        assert snippet not in source


def test_process_adapter_does_not_define_unqualified_real_executor_adapter_name() -> None:
    for node in _module().body:
        if isinstance(node, ast.ClassDef):
            assert node.name != "RealExecutorAdapter"
