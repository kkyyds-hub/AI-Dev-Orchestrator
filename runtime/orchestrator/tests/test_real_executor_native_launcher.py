from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.external_executors.actual_native_launcher import (
    FakeRealExecutorNativeRunner,
    RealExecutorNativeLaunchInput,
    RealExecutorNativeLaunchMode,
    RealExecutorNativeLauncher,
    SubprocessRealExecutorNativeRunner,
)


NATIVE_LAUNCHER_FILE = Path("app/external_executors/actual_native_launcher.py")


def _source() -> str:
    return NATIVE_LAUNCHER_FILE.read_text()


def _module() -> ast.Module:
    return ast.parse(_source())


def _ready_input(**overrides) -> RealExecutorNativeLaunchInput:
    values = {
        "launch_mode": RealExecutorNativeLaunchMode.ENABLED,
        "executor_label": "codex",
        "workspace_path": "/tmp/ai-dev-orchestrator-workspace",
        "agent_session_id": "agent-session-1",
        "prelaunch_ready": True,
        "command_plan_redacted": True,
        "allow_native_process": True,
    }
    values.update(overrides)
    return RealExecutorNativeLaunchInput(**values)


def _decision(**overrides):
    return RealExecutorNativeLauncher(
        runner=FakeRealExecutorNativeRunner(process_handle_id="fake-handle-1"),
    ).decide(_ready_input(**overrides))


def test_default_disabled_blocks_without_native_attempt() -> None:
    decision = RealExecutorNativeLauncher().decide()

    assert decision.launch_status == "blocked"
    assert "native_launch_disabled" in decision.blocked_reasons
    assert decision.native_launch_attempted is False
    assert decision.native_process_started is False
    assert decision.process_handle_id is None


def test_dry_run_returns_ready_without_native_attempt() -> None:
    decision = _decision(
        launch_mode=RealExecutorNativeLaunchMode.DRY_RUN,
        allow_native_process=False,
    )

    assert decision.launch_status == "dry_run_ready"
    assert decision.native_launch_attempted is False
    assert decision.native_process_started is False
    assert decision.process_handle_id is None
    assert decision.blocked_reasons == []


def test_enabled_without_allow_native_process_blocks() -> None:
    decision = _decision(allow_native_process=False)

    assert decision.launch_status == "blocked"
    assert "native_process_not_allowed" in decision.blocked_reasons
    assert decision.native_launch_attempted is False
    assert decision.native_process_started is False


def test_enabled_with_prelaunch_not_ready_blocks() -> None:
    decision = _decision(prelaunch_ready=False)

    assert decision.launch_status == "blocked"
    assert "prelaunch_not_ready" in decision.blocked_reasons
    assert decision.native_launch_attempted is False
    assert decision.native_process_started is False


def test_enabled_with_unredacted_command_plan_blocks() -> None:
    decision = _decision(command_plan_redacted=False)

    assert decision.launch_status == "blocked"
    assert "command_plan_not_redacted" in decision.blocked_reasons
    assert decision.native_launch_attempted is False
    assert decision.native_process_started is False


def test_enabled_all_ready_uses_fake_runner_and_starts_boundary_only() -> None:
    runner = FakeRealExecutorNativeRunner(process_handle_id="fake-handle-1")
    launcher = RealExecutorNativeLauncher(runner=runner)

    decision = launcher.decide(_ready_input())

    assert decision.launch_status == "launch_started"
    assert decision.native_launch_attempted is True
    assert decision.native_process_started is True
    assert decision.process_handle_id == "fake-handle-1"
    assert runner.started is True
    assert runner.started_argv == ("codex",)
    assert runner.started_workspace_path == "/tmp/ai-dev-orchestrator-workspace"


def test_launch_started_keeps_product_git_and_frontend_flags_disabled() -> None:
    decision = _decision()

    assert decision.product_runtime_git_write_allowed is False
    assert decision.frontend_required is False
    assert decision.frontend_change_allowed is False


def test_launch_started_exposes_only_opaque_process_handle() -> None:
    decision = _decision()
    body = decision.model_dump()

    assert body["process_handle_id"] == "fake-handle-1"
    assert body["raw_command_exposed"] is False
    assert body["stdout_exposed"] is False
    assert body["stderr_exposed"] is False
    assert "raw_command" not in body
    assert "stdout" not in body
    assert "stderr" not in body


@pytest.mark.parametrize("executor_label", ["deepseek", "shell", ""])
def test_executor_label_outside_allowlist_is_rejected(executor_label: str) -> None:
    with pytest.raises(ValidationError):
        _ready_input(executor_label=executor_label)


@pytest.mark.parametrize("workspace_path", ["", "relative/path"])
def test_workspace_path_must_be_non_empty_absolute_path(workspace_path: str) -> None:
    with pytest.raises(ValidationError):
        _ready_input(workspace_path=workspace_path)


def test_agent_session_id_must_be_non_empty() -> None:
    with pytest.raises(ValidationError):
        _ready_input(agent_session_id=" ")


def test_forbidden_true_flags_are_rejected() -> None:
    for field_name in [
        "product_runtime_git_write_allowed",
        "frontend_required",
        "frontend_change_allowed",
    ]:
        with pytest.raises(ValidationError):
            _ready_input(**{field_name: True})


def test_subprocess_runner_exists_but_is_not_used_by_default_tests() -> None:
    runner = SubprocessRealExecutorNativeRunner()

    assert hasattr(runner, "start")
    assert isinstance(FakeRealExecutorNativeRunner(), FakeRealExecutorNativeRunner)


def test_subprocess_runner_source_uses_shell_false_and_no_env_reading() -> None:
    source = _source()

    assert "shell=True" not in source
    assert "shell=False" in source
    assert "os.environ" not in source
    assert "getenv" not in source


def test_module_and_response_exclude_sensitive_or_payload_fields() -> None:
    source = _source().lower()
    body = _decision().model_dump_json().lower()

    for forbidden in {
        "api_key",
        "token",
        "secret",
        "bearer",
        "sk-",
        "password",
        '"raw_command":',
        '"stdout":',
        '"stderr":',
        '"env":',
    }:
        assert forbidden not in source
        assert forbidden not in body


def test_only_native_launcher_module_adds_subprocess_boundary() -> None:
    source = _source()
    assert "subprocess" in source
    assert "Popen" in source
    assert "create_subprocess" not in source

    for path in Path("app/external_executors").glob("actual_*.py"):
        if path == NATIVE_LAUNCHER_FILE:
            continue
        other_source = path.read_text()
        assert "subprocess" not in other_source
        assert "Popen" not in other_source
        assert "create_subprocess" not in other_source


def test_module_does_not_call_worktree_create_cleanup_or_write_runner() -> None:
    source = _source()

    for forbidden in {
        "WorktreeCreateService",
        "WorktreeCleanupService",
        "WorktreeWriteCommandRunner",
        "create_workspace",
        "cleanup_workspace",
    }:
        assert forbidden not in source

    for node in ast.walk(_module()):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {
                "create_workspace",
                "cleanup_workspace",
                "run",
            }


def test_no_apps_web_changes_are_present() -> None:
    assert not any(Path("../../apps/web").glob("**/*native*launcher*"))
