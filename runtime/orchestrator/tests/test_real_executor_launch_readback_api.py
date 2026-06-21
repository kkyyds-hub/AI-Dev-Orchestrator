from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.api.routes.runtime import (
    cleanup_real_executor_noop_session,
    build_real_executor_launch_readback,
    build_real_executor_process_adapter_readback,
    cancel_real_executor_noop_session,
    create_real_executor_noop_session,
    get_real_executor_launch_readback_builder,
    get_real_executor_noop_session,
    kill_real_executor_noop_session,
    router,
)
from app.external_executors.actual_contract import (
    RealExecutorOperationStatus,
    RealExecutorSafetyBoundary,
)
from app.external_executors.actual_readback import (
    RealExecutorLaunchReadbackBuilder,
    RealExecutorLaunchReadbackRequest,
    RealExecutorLaunchReadbackResponse,
)


READBACK_FILE = Path("app/external_executors/actual_readback.py")
RUNTIME_ROUTE_FILE = Path("app/api/routes/runtime.py")

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
    "app.workers",
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


def _source(path: Path) -> str:
    return path.read_text()


def _module(path: Path) -> ast.Module:
    return ast.parse(_source(path))


def _class_field_names(path: Path, class_name: str) -> set[str]:
    for node in _module(path).body:
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


def _request(boundary: RealExecutorSafetyBoundary) -> RealExecutorLaunchReadbackRequest:
    return RealExecutorLaunchReadbackRequest(
        request_id="request-1",
        executor_label="safe executor label",
        command_summary="future launch summary",
        workspace_hint="registered worktree",
        safety_boundary=boundary,
    )


def test_real_executor_launch_readback_endpoint_exists() -> None:
    matches = [
        route
        for route in router.routes
        if getattr(route, "path", None) == "/runtime/real-executor/launch-readback"
    ]

    assert len(matches) == 1
    route = matches[0]
    assert "POST" in getattr(route, "methods", set())
    assert "execute" not in route.path
    assert "approve" not in route.path
    assert "confirm" not in route.path
    assert "consume" not in route.path


def test_guarded_process_adapter_readback_endpoint_exists() -> None:
    matches = [
        route
        for route in router.routes
        if getattr(route, "path", None)
        == "/runtime/real-executor/process-adapter-readback"
    ]

    assert len(matches) == 1
    route = matches[0]
    assert "GET" in getattr(route, "methods", set())
    endpoint_name = route.path.rsplit("/", 1)[-1]
    for forbidden in {"execute", "run", "start-native", "commit", "push", "merge"}:
        assert forbidden not in endpoint_name


def test_guarded_noop_lifecycle_endpoints_exist_without_execution_names() -> None:
    expected = {
        "/runtime/real-executor/process-adapter-noop-sessions": "POST",
        "/runtime/real-executor/process-adapter-noop-sessions/{session_id}": "GET",
        "/runtime/real-executor/process-adapter-noop-sessions/{session_id}/cancel": "POST",
        "/runtime/real-executor/process-adapter-noop-sessions/{session_id}/kill": "POST",
        "/runtime/real-executor/process-adapter-noop-sessions/{session_id}/cleanup": "POST",
    }

    for path, method in expected.items():
        matches = [route for route in router.routes if getattr(route, "path", None) == path]
        assert len(matches) == 1
        assert method in getattr(matches[0], "methods", set())
        route_suffix = path.removeprefix("/runtime/real-executor/")
        for forbidden in {"execute", "run", "start-native", "commit", "push", "merge"}:
            assert forbidden not in route_suffix


def test_guarded_noop_lifecycle_create_poll_cancel_kill_cleanup() -> None:
    created = create_real_executor_noop_session()

    assert created.api_mode == "noop_lifecycle"
    assert created.operation_status == "accepted"
    assert created.poll_state == "launch_pending"
    assert created.product_runtime_git_write_allowed is False
    assert created.native_process_started is False

    polled = get_real_executor_noop_session(created.session_id)
    assert polled.poll_state == "launch_pending"
    assert polled.product_runtime_git_write_allowed is False
    assert polled.native_process_started is False

    cancelled = cancel_real_executor_noop_session(created.session_id)
    assert cancelled.operation_status == "completed"
    assert cancelled.poll_state == "cancelled"
    assert cancelled.product_runtime_git_write_allowed is False
    assert cancelled.native_process_started is False

    killed = kill_real_executor_noop_session(created.session_id)
    assert killed.operation_status == "completed"
    assert killed.poll_state == "killed"
    assert killed.product_runtime_git_write_allowed is False
    assert killed.native_process_started is False

    cleaned = cleanup_real_executor_noop_session(created.session_id)
    assert cleaned.operation_status == "completed"
    assert cleaned.poll_state == "cleaned_up"
    assert cleaned.product_runtime_git_write_allowed is False
    assert cleaned.native_process_started is False


def test_guarded_noop_lifecycle_unknown_session_returns_readback_not_500() -> None:
    response = get_real_executor_noop_session("missing-session")

    assert response.operation_status == "not_found"
    assert response.poll_state == "unknown"
    assert "session_not_found" in response.blocking_reasons
    assert response.product_runtime_git_write_allowed is False
    assert response.native_process_started is False


def test_guarded_noop_lifecycle_responses_exclude_sensitive_and_raw_output_fields() -> None:
    created = create_real_executor_noop_session()
    responses = [
        created,
        get_real_executor_noop_session(created.session_id),
        cancel_real_executor_noop_session(created.session_id),
        kill_real_executor_noop_session(created.session_id),
        cleanup_real_executor_noop_session(created.session_id),
    ]

    for response in responses:
        body = response.model_dump_json().lower()
        for forbidden in {
            "api_key",
            "token",
            "secret",
            "bearer",
            "sk-",
            "password",
            "env",
            "stdout",
            "stderr",
            "raw_command",
        }:
            assert forbidden not in body
        assert response.product_runtime_git_write_allowed is False
        assert response.native_process_started is False


def test_guarded_process_adapter_readback_defaults_to_blocked() -> None:
    response = build_real_executor_process_adapter_readback()
    data = response.model_dump(mode="json")

    assert data["adapter_kind"] == "process_skeleton"
    assert set(data["supported_executor_labels"]) >= {"codex", "claude code", "claude-code"}
    assert data["default_launch_status"] == "blocked"
    assert "feature_flag_disabled" in data["default_blocking_reasons"]
    assert data["all_gates_pass_behavior"] == "noop_launch_pending"
    assert data["product_runtime_git_write_allowed"] is False
    assert data["native_process_started"] is False
    assert data["secret_exposure_blocked"] is True
    assert data["environment_dump_blocked"] is True


def test_guarded_process_adapter_readback_response_does_not_expose_sensitive_text() -> None:
    response = build_real_executor_process_adapter_readback()
    values = [
        str(value).lower()
        for value in response.model_dump(mode="json").values()
        if not isinstance(value, bool)
    ]
    body_values = " ".join(values)

    for forbidden in {"api_key", "token", "secret", "bearer", "sk-", "password"}:
        assert forbidden not in body_values


def test_guarded_process_adapter_readback_does_not_imply_write_or_execute_controls() -> None:
    response = build_real_executor_process_adapter_readback()
    body = response.model_dump_json().lower()

    for forbidden in {"execute", "commit", "push", "merge", "started native"}:
        assert forbidden not in body


def test_readback_file_lives_under_external_executors() -> None:
    assert READBACK_FILE.is_file()
    assert READBACK_FILE.parts[:2] == ("app", "external_executors")


def test_readback_builder_exists() -> None:
    assert isinstance(get_real_executor_launch_readback_builder(), RealExecutorLaunchReadbackBuilder)


def test_all_safety_gates_pass_still_returns_disabled_adapter_blocked() -> None:
    response = build_real_executor_launch_readback(
        _request(_passing_boundary()),
        get_real_executor_launch_readback_builder(),
    )

    assert isinstance(response, RealExecutorLaunchReadbackResponse)
    assert response.preflight_ready is True
    assert response.preflight_status is RealExecutorOperationStatus.ACCEPTED
    assert response.preview_ready is True
    assert response.preview_executable is False
    assert response.adapter_enabled is False
    assert response.adapter_launch_status is RealExecutorOperationStatus.BLOCKED
    assert "real_executor_disabled" in response.blocking_reasons
    assert response.real_executor_launch_started is False
    assert response.product_runtime_git_write_allowed is False
    assert response.api_mode == "read_only"


def test_blocked_safety_gates_return_blocking_reasons() -> None:
    response = build_real_executor_launch_readback(
        _request(RealExecutorSafetyBoundary()),
        get_real_executor_launch_readback_builder(),
    )

    assert response.preflight_ready is False
    assert response.preflight_status is RealExecutorOperationStatus.BLOCKED
    assert response.preview_ready is False
    assert response.adapter_launch_status is RealExecutorOperationStatus.BLOCKED
    assert "feature_flag_disabled" in response.blocking_reasons
    assert "human_confirmation_missing" in response.blocking_reasons
    assert "real_executor_disabled" in response.blocking_reasons
    assert response.preview_executable is False
    assert response.real_executor_launch_started is False
    assert response.product_runtime_git_write_allowed is False


def test_response_safety_flags_are_constant() -> None:
    response = RealExecutorLaunchReadbackBuilder().build(_request(_passing_boundary()))

    assert response.preview_executable is False
    assert response.real_executor_launch_started is False
    assert response.product_runtime_git_write_allowed is False
    assert response.adapter_enabled is False
    assert response.redaction_applied is True
    assert response.api_mode == "read_only"


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("executor_label", "contains api key"),
        ("command_summary", "contains token"),
        ("command_summary", "contains secret"),
        ("workspace_hint", "contains password"),
        ("workspace_hint", "contains bearer value"),
        ("executor_label", "contains sk-test"),
    ],
)
def test_readback_request_rejects_suspected_credential_text(
    field_name: str,
    value: str,
) -> None:
    payload = {
        "request_id": "request-1",
        "executor_label": "safe executor label",
    }
    payload[field_name] = value

    with pytest.raises(ValidationError):
        RealExecutorLaunchReadbackRequest(**payload)


@pytest.mark.parametrize(
    "field_name",
    [
        "raw_command",
        "args",
        "env",
        "env_vars",
        "token_value",
        "cli_path",
        "process_handle",
    ],
)
def test_readback_request_rejects_forbidden_runtime_fields(field_name: str) -> None:
    payload = {
        "request_id": "request-1",
        "executor_label": "safe executor label",
        field_name: "not allowed",
    }

    with pytest.raises(ValidationError):
        RealExecutorLaunchReadbackRequest(**payload)


def test_readback_field_names_do_not_include_forbidden_runtime_fields() -> None:
    checked_classes = {
        "RealExecutorLaunchReadbackRequest",
        "RealExecutorLaunchReadbackResponse",
    }

    for class_name in checked_classes:
        assert _class_field_names(READBACK_FILE, class_name).isdisjoint(
            FORBIDDEN_RUNTIME_FIELDS,
        )


def test_readback_module_does_not_import_forbidden_layers_or_process_modules() -> None:
    source = _source(READBACK_FILE)

    for snippet in FORBIDDEN_IMPORT_SNIPPETS:
        assert snippet not in source


def test_readback_module_does_not_contain_execution_traces() -> None:
    source = _source(READBACK_FILE)

    for snippet in FORBIDDEN_EXECUTION_SNIPPETS:
        assert snippet not in source


def test_readback_module_does_not_read_environment_values() -> None:
    source = _source(READBACK_FILE)

    for snippet in FORBIDDEN_ENVIRONMENT_SNIPPETS:
        assert snippet not in source


def test_runtime_route_readback_endpoint_stays_thin_and_read_only() -> None:
    source = _source(RUNTIME_ROUTE_FILE)

    assert "/real-executor/launch-readback" in source
    assert "/real-executor/process-adapter-readback" in source
    assert "RealExecutorLaunchReadbackBuilder" in source
    assert "task_worker" not in source
    assert "ExecutorService" not in source
    assert "subprocess" not in source
    assert "os.popen" not in source
    assert "shell=True" not in source


def test_no_frontend_worker_or_migration_entrypoints_added() -> None:
    assert not Path("app/workers/real_executor_worker.py").exists()
    assert not any(Path("migrations").glob("*real_executor*"))
    assert not Path("../../apps/web/real-executors").exists()
