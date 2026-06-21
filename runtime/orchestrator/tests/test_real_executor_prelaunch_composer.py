from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.external_executors.actual_prelaunch_chain import (
    RealExecutorPrelaunchChainState,
    RealExecutorPrelaunchChainStepName,
)
from app.external_executors.actual_prelaunch_composer import (
    RealExecutorPrelaunchComposer,
    RealExecutorPrelaunchComposerInput,
)


COMPOSER_FILE = Path("app/external_executors/actual_prelaunch_composer.py")
EXPECTED_COMPOSED_FROM = [
    "silent_dispatch",
    "operator_validation",
    "preflight",
    "preview",
    "workspace_binding",
    "runtime_binding",
    "process_adapter_noop_lifecycle",
    "audit_append_only",
]
FORBIDDEN_NATIVE_HELPERS = {
    "subprocess",
    "Popen",
    "os.environ",
    "getenv",
    "shell=True",
    "asyncio.create_subprocess",
}
FORBIDDEN_PAYLOAD_TERMS = {
    "api_key",
    "token",
    "secret",
    "bearer",
    "sk-",
    "password",
    "stdout",
    "stderr",
    "raw_command",
    "env",
}
FORBIDDEN_ACTION_TERMS = {
    "run",
    "execute",
    "start-native",
    "launched",
    "completed_native",
    "commit",
    "push",
    "merge",
}


def _source() -> str:
    return COMPOSER_FILE.read_text()


def _module() -> ast.Module:
    return ast.parse(_source())


def _all_ready_input(**overrides) -> RealExecutorPrelaunchComposerInput:
    values = {
        "silent_dispatch_ready": True,
        "operator_validation_status": "accepted_for_noop_validation",
        "preflight_ready": True,
        "preview_ready": True,
        "workspace_bound": True,
        "runtime_bound": True,
        "executor_label": "codex",
        "command_plan_redacted": True,
        "noop_lifecycle_ready": True,
        "audit_append_only_ready": True,
    }
    values.update(overrides)
    return RealExecutorPrelaunchComposerInput(**values)


def _compose(**overrides):
    payload = _all_ready_input(**overrides)
    return RealExecutorPrelaunchComposer().compose(payload)


def _step_ready(snapshot, step_name: RealExecutorPrelaunchChainStepName) -> bool:
    for step in snapshot.prelaunch_snapshot.ordered_steps:
        if step.name is step_name:
            return step.ready
    raise AssertionError(f"missing step {step_name}")


def test_composer_default_snapshot_does_not_allow_native_launch() -> None:
    snapshot = RealExecutorPrelaunchComposer().compose()

    assert snapshot.prelaunch_snapshot.current_state in {
        RealExecutorPrelaunchChainState.BLOCKED,
        RealExecutorPrelaunchChainState.NATIVE_LAUNCH_NOT_STARTED,
    }
    assert snapshot.composer_mode == "read_only_composition"
    assert snapshot.native_launch_allowed is False
    assert snapshot.native_process_started is False
    assert snapshot.product_runtime_git_write_allowed is False
    assert snapshot.frontend_required is False
    assert snapshot.frontend_change_allowed is False


@pytest.mark.parametrize("status", ["missing", "pending", "rejected"])
def test_non_accepted_operator_validation_status_blocks(status: str) -> None:
    snapshot = _compose(operator_validation_status=status)

    assert snapshot.prelaunch_snapshot.current_state is RealExecutorPrelaunchChainState.BLOCKED
    assert "operator_validation_missing" in snapshot.prelaunch_snapshot.blocked_reasons
    assert _step_ready(snapshot, RealExecutorPrelaunchChainStepName.OPERATOR_VALIDATION) is False
    assert snapshot.native_launch_allowed is False


def test_accepted_operator_validation_status_is_the_only_passing_operator_status() -> None:
    snapshot = _compose(operator_validation_status="accepted_for_noop_validation")

    assert _step_ready(snapshot, RealExecutorPrelaunchChainStepName.OPERATOR_VALIDATION) is True
    assert "operator_validation_missing" not in snapshot.prelaunch_snapshot.blocked_reasons
    assert snapshot.native_launch_allowed is False


@pytest.mark.parametrize(
    ("field_name", "reason"),
    [
        ("preflight_ready", "real_executor_preflight_missing"),
        ("preview_ready", "real_executor_preview_missing"),
        ("workspace_bound", "workspace_binding_missing"),
        ("runtime_bound", "runtime_binding_missing"),
        ("command_plan_redacted", "command_plan_not_redacted"),
        ("noop_lifecycle_ready", "process_adapter_noop_lifecycle_missing"),
        ("audit_append_only_ready", "audit_append_only_missing"),
    ],
)
def test_missing_composer_prerequisites_block(field_name: str, reason: str) -> None:
    snapshot = _compose(**{field_name: False})

    assert snapshot.prelaunch_snapshot.current_state is RealExecutorPrelaunchChainState.BLOCKED
    assert reason in snapshot.prelaunch_snapshot.blocked_reasons
    assert snapshot.native_launch_allowed is False


def test_silent_dispatch_missing_blocks() -> None:
    snapshot = _compose(silent_dispatch_ready=False)

    assert snapshot.prelaunch_snapshot.current_state is RealExecutorPrelaunchChainState.BLOCKED
    assert "silent_dispatch_readiness_missing" in snapshot.prelaunch_snapshot.blocked_reasons


def test_unsupported_executor_label_blocks() -> None:
    snapshot = _compose(executor_label="deepseek")

    assert snapshot.prelaunch_snapshot.current_state is RealExecutorPrelaunchChainState.BLOCKED
    assert "executor_label_not_supported" in snapshot.prelaunch_snapshot.blocked_reasons


@pytest.mark.parametrize("executor_label", ["codex", "claude-code", "claude code"])
def test_all_ready_reaches_precheck_only(executor_label: str) -> None:
    snapshot = _compose(executor_label=executor_label)

    assert snapshot.prelaunch_snapshot.current_state is (
        RealExecutorPrelaunchChainState.READY_FOR_NATIVE_LAUNCH_PRECHECK
    )
    assert snapshot.prelaunch_snapshot.blocked_reasons == []
    assert snapshot.native_launch_allowed is False
    assert snapshot.prelaunch_snapshot.native_launch_allowed is False


def test_future_ordering_remains_fixed() -> None:
    snapshot = _compose()

    assert snapshot.prelaunch_snapshot.future_spawn_order == ["workspace", "runtime", "agent"]
    assert snapshot.prelaunch_snapshot.future_cleanup_order == ["agent", "runtime", "workspace"]


def test_composed_from_names_all_read_only_inputs() -> None:
    snapshot = _compose()

    assert snapshot.composed_from == EXPECTED_COMPOSED_FROM


def test_forbidden_output_flags_remain_false_for_every_response_shape() -> None:
    snapshots = [
        RealExecutorPrelaunchComposer().compose(),
        _compose(operator_validation_status="missing"),
        _compose(preflight_ready=False),
        _compose(command_plan_redacted=False),
        _compose(),
    ]

    for snapshot in snapshots:
        assert snapshot.native_process_started is False
        assert snapshot.product_runtime_git_write_allowed is False
        assert snapshot.frontend_required is False
        assert snapshot.frontend_change_allowed is False
        assert snapshot.prelaunch_snapshot.native_process_started is False
        assert snapshot.prelaunch_snapshot.product_runtime_git_write_allowed is False
        assert snapshot.prelaunch_snapshot.frontend_required is False
        assert snapshot.prelaunch_snapshot.frontend_change_allowed is False


@pytest.mark.parametrize(
    "field_name",
    [
        "native_process_started",
        "product_runtime_git_write_allowed",
        "frontend_required",
        "frontend_change_allowed",
    ],
)
def test_input_rejects_forbidden_true_flags(field_name: str) -> None:
    with pytest.raises(ValidationError):
        RealExecutorPrelaunchComposerInput(**{field_name: True})


def test_status_and_response_do_not_contain_forbidden_action_words() -> None:
    body = " ".join(
        [
            _compose().prelaunch_snapshot.current_state.value,
            *_compose(command_plan_redacted=False).prelaunch_snapshot.blocked_reasons,
            *_compose().composed_from,
            _compose().composer_mode,
        ],
    ).lower()

    for forbidden in FORBIDDEN_ACTION_TERMS:
        assert re.search(rf"\b{re.escape(forbidden)}\b", body) is None


def test_module_does_not_import_or_call_native_process_helpers() -> None:
    source = _source()

    for forbidden in FORBIDDEN_NATIVE_HELPERS:
        assert forbidden.lower() not in source.lower()


def test_module_and_response_exclude_sensitive_or_raw_output_terms() -> None:
    source = _source().lower()
    body = _compose().model_dump_json().lower()

    for forbidden in FORBIDDEN_PAYLOAD_TERMS:
        assert forbidden not in source
        assert forbidden not in body


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
