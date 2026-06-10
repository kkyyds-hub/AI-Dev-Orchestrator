from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.external_executors.actual_contract import (
    RealExecutorAdapterProtocol,
    RealExecutorLaunchContext,
    RealExecutorOperationStatus,
    RealExecutorPollState,
    RealExecutorSafetyBoundary,
)
from app.external_executors.actual_disabled_adapter import (
    DISABLED_REASON,
    DisabledRealExecutorAdapter,
    DisabledRealExecutorAdapterAuditEvent,
    DisabledRealExecutorAdapterConfig,
    DisabledRealExecutorAdapterResultFactory,
)


DISABLED_ADAPTER_FILE = Path("app/external_executors/actual_disabled_adapter.py")

FORBIDDEN_RUNTIME_FIELDS = {
    "raw_command",
    "command",
    "args",
    "env",
    "env_vars",
    "api_key",
    "token_value",
    "auth_token",
    "secret",
    "password",
    "native_config_path",
    "cli_path",
    "process_handle",
    "stdout_path",
    "stderr_path",
    "log_path",
}

FORBIDDEN_IMPORT_SNIPPETS = {
    "app.api",
    "app.workers",
    "app.services",
    "app.repositories",
    "import subprocess",
    "from subprocess",
    "import os",
    "from os",
    "import pty",
    "from pty",
    "import shlex",
    "from shlex",
    "import pathlib",
    "from pathlib",
}

FORBIDDEN_EXECUTION_SNIPPETS = {
    "Popen",
    "shell=True",
    "os.popen",
    "asyncio.create_subprocess_exec",
    "asyncio.create_subprocess_shell",
    "tmux",
    "Codex CLI",
    "Claude Code",
    "DeepSeek CLI",
}

FORBIDDEN_ENVIRONMENT_SNIPPETS = {
    "environ",
    "getenv",
    "environment variable",
    "environment variables",
}


def _source() -> str:
    return DISABLED_ADAPTER_FILE.read_text()


def _module() -> ast.Module:
    return ast.parse(_source())


def _class_field_names(class_name: str) -> set[str]:
    for node in _module().body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            fields: set[str] = set()
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    fields.add(item.target.id)
            return fields
    raise AssertionError(f"{class_name} was not found")


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


def _context(boundary: RealExecutorSafetyBoundary | None = None) -> RealExecutorLaunchContext:
    return RealExecutorLaunchContext(
        request_id="request-1",
        executor_label="safe executor label",
        command_summary="future launch summary",
        workspace_hint="registered worktree",
        safety_boundary=boundary or _passing_boundary(),
    )


def test_disabled_real_executor_adapter_file_lives_under_external_executors() -> None:
    assert DISABLED_ADAPTER_FILE.is_file()
    assert DISABLED_ADAPTER_FILE.parts[:2] == ("app", "external_executors")


def test_disabled_real_executor_adapter_exists_and_matches_protocol_shape() -> None:
    adapter = DisabledRealExecutorAdapter()

    assert isinstance(adapter, RealExecutorAdapterProtocol)
    assert hasattr(adapter, "launch")
    assert hasattr(adapter, "poll")
    assert hasattr(adapter, "cancel")
    assert hasattr(adapter, "kill")
    assert hasattr(adapter, "cleanup")


def test_config_is_disabled_by_default_and_cannot_be_enabled() -> None:
    config = DisabledRealExecutorAdapterConfig()

    assert config.enabled is False
    assert config.disabled_reason == DISABLED_REASON

    with pytest.raises(ValidationError):
        DisabledRealExecutorAdapterConfig(enabled=True)


def test_launch_is_always_blocked_even_when_preflight_gates_pass() -> None:
    result = DisabledRealExecutorAdapter().launch(_context(_passing_boundary()))

    assert result.status is RealExecutorOperationStatus.BLOCKED
    assert DISABLED_REASON in result.blocking_reasons
    assert result.product_runtime_git_write_allowed is False
    assert result.audit_event_count == 1


def test_launch_result_preserves_preflight_blocking_reasons() -> None:
    result = DisabledRealExecutorAdapter().launch(_context(RealExecutorSafetyBoundary()))

    assert result.status is RealExecutorOperationStatus.BLOCKED
    assert DISABLED_REASON in result.blocking_reasons
    assert "feature_flag_disabled" in result.blocking_reasons
    assert "human_confirmation_missing" in result.blocking_reasons
    assert result.product_runtime_git_write_allowed is False


def test_poll_returns_safe_unknown_snapshot_without_process_probe() -> None:
    snapshot = DisabledRealExecutorAdapter().poll("session-1")

    assert snapshot.poll_state is RealExecutorPollState.UNKNOWN
    assert DISABLED_REASON in snapshot.blocking_reasons
    assert "session_not_started" in snapshot.blocking_reasons
    assert snapshot.product_runtime_git_write_allowed is False
    assert snapshot.audit_event_count == 1


def test_cancel_kill_and_cleanup_return_safe_results_without_system_calls() -> None:
    adapter = DisabledRealExecutorAdapter()

    cancel_result = adapter.cancel("session-1", "user requested stop")
    kill_result = adapter.kill("session-1", "operator requested stop")
    cleanup_result = adapter.cleanup("session-1")

    assert cancel_result.status is RealExecutorOperationStatus.BLOCKED
    assert kill_result.status is RealExecutorOperationStatus.BLOCKED
    assert cleanup_result.status is RealExecutorOperationStatus.COMPLETED

    for result in (cancel_result, kill_result, cleanup_result):
        assert DISABLED_REASON in result.blocking_reasons
        assert result.product_runtime_git_write_allowed is False
        assert result.audit_event_count == 1

    assert "cleanup_noop" in cleanup_result.blocking_reasons


def test_disabled_adapter_audit_event_is_safe_local_dto_only() -> None:
    event = DisabledRealExecutorAdapter().audit_event(
        kind="real_executor.launch_blocked",
        level="warn",
        summary="Real executor launch blocked because adapter is disabled",
        detail="safe local audit DTO only",
    )

    assert isinstance(event, DisabledRealExecutorAdapterAuditEvent)
    assert event.source == "external_executor"
    assert event.kind == "real_executor.launch_blocked"
    assert event.level == "warn"
    assert event.summary == "Real executor launch blocked because adapter is disabled"
    assert event.detail == "safe local audit DTO only"


@pytest.mark.parametrize(
    "value",
    [
        "contains api key",
        "contains token",
        "contains secret",
        "contains password",
        "contains bearer value",
        "contains sk-test",
    ],
)
def test_audit_event_rejects_suspected_credential_text(value: str) -> None:
    with pytest.raises(ValidationError):
        DisabledRealExecutorAdapterAuditEvent(
            kind="real_executor.launch_blocked",
            summary=value,
        )

    with pytest.raises(ValidationError):
        DisabledRealExecutorAdapterAuditEvent(
            kind=value,
            summary="safe summary",
        )


def test_result_factory_is_local_contract_helper_not_runtime_event_bus() -> None:
    factory = DisabledRealExecutorAdapterResultFactory()
    event = factory.audit_event(
        kind="real_executor.cleanup_noop",
        level="info",
        summary="Cleanup skipped because adapter is disabled",
    )

    assert isinstance(event, DisabledRealExecutorAdapterAuditEvent)
    assert not hasattr(factory, "record")
    assert not hasattr(factory, "publish")
    assert not hasattr(factory, "write")
    assert not hasattr(factory, "emit")


def test_disabled_adapter_field_names_do_not_include_forbidden_runtime_fields() -> None:
    checked_classes = {
        "DisabledRealExecutorAdapterConfig",
        "DisabledRealExecutorAdapterAuditEvent",
    }

    for class_name in checked_classes:
        assert _class_field_names(class_name).isdisjoint(FORBIDDEN_RUNTIME_FIELDS)


def test_actual_disabled_adapter_does_not_import_forbidden_layers_or_process_modules() -> None:
    source = _source()

    for snippet in FORBIDDEN_IMPORT_SNIPPETS:
        assert snippet not in source


def test_actual_disabled_adapter_does_not_contain_execution_traces() -> None:
    source = _source()

    for snippet in FORBIDDEN_EXECUTION_SNIPPETS:
        assert snippet not in source


def test_actual_disabled_adapter_does_not_read_environment_values() -> None:
    source = _source()

    for snippet in FORBIDDEN_ENVIRONMENT_SNIPPETS:
        assert snippet not in source


def test_actual_disabled_adapter_does_not_contain_forbidden_runtime_fields() -> None:
    source = _source()

    for snippet in {
        "raw_command",
        "env_vars",
        "token_value",
        "native_config_path",
        "process_handle",
        "stdout_path",
        "stderr_path",
        "log_path",
    }:
        assert snippet not in source


def test_actual_disabled_adapter_does_not_define_startable_adapter_name() -> None:
    for node in _module().body:
        if isinstance(node, ast.ClassDef):
            assert node.name != "RealExecutorAdapter"


def test_actual_disabled_adapter_does_not_create_api_frontend_worker_or_migration_entrypoints() -> None:
    assert not Path("app/api/routes/real_executor.py").exists()
    assert not Path("app/api/routes/real_executors.py").exists()
    assert not Path("app/workers/real_executor_worker.py").exists()
    assert not any(Path("migrations").glob("*real_executor*"))
    assert not Path("../../apps/web/real-executors").exists()
