from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.external_executors.actual_prelaunch_chain import (
    RealExecutorPrelaunchChainBuilder,
    RealExecutorPrelaunchChainInput,
    RealExecutorPrelaunchChainState,
)


PRELAUNCH_CHAIN_FILE = Path("app/external_executors/actual_prelaunch_chain.py")
EXPECTED_STEPS = [
    "silent_dispatch_readiness",
    "operator_validation",
    "real_executor_preflight",
    "real_executor_preview",
    "workspace_binding_precheck",
    "runtime_binding_precheck",
    "executor_label_resolution",
    "redacted_command_plan_placeholder",
    "process_adapter_noop_lifecycle",
    "audit_event_append_only_planned",
    "native_launch_blocked",
    "product_runtime_git_write_forbidden",
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
FORBIDDEN_STATUS_TERMS = {
    "executed",
    "start-native",
    "launched",
    "completed_native",
    "committed",
    "pushed",
    "merged",
}


def _source() -> str:
    return PRELAUNCH_CHAIN_FILE.read_text()


def _module() -> ast.Module:
    return ast.parse(_source())


def _snapshot(**overrides):
    values = {
        "silent_dispatch_ready": True,
        "operator_validation_accepted": True,
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
    return RealExecutorPrelaunchChainBuilder().build(
        RealExecutorPrelaunchChainInput(**values),
    )


def test_default_snapshot_does_not_allow_native_launch() -> None:
    snapshot = RealExecutorPrelaunchChainBuilder().build()

    assert snapshot.current_state in {
        RealExecutorPrelaunchChainState.BLOCKED,
        RealExecutorPrelaunchChainState.NATIVE_LAUNCH_NOT_STARTED,
    }
    assert snapshot.native_launch_allowed is False
    assert snapshot.native_process_started is False
    assert snapshot.product_runtime_git_write_allowed is False
    assert snapshot.frontend_required is False
    assert snapshot.frontend_change_allowed is False


@pytest.mark.parametrize(
    ("field_name", "reason"),
    [
        ("silent_dispatch_ready", "silent_dispatch_readiness_missing"),
        ("operator_validation_accepted", "operator_validation_missing"),
        ("preflight_ready", "real_executor_preflight_missing"),
        ("preview_ready", "real_executor_preview_missing"),
        ("workspace_bound", "workspace_binding_missing"),
        ("runtime_bound", "runtime_binding_missing"),
        ("noop_lifecycle_ready", "process_adapter_noop_lifecycle_missing"),
        ("audit_append_only_ready", "audit_append_only_missing"),
    ],
)
def test_missing_required_chain_readiness_blocks(field_name: str, reason: str) -> None:
    snapshot = _snapshot(**{field_name: False})

    assert snapshot.current_state is RealExecutorPrelaunchChainState.BLOCKED
    assert reason in snapshot.blocked_reasons
    assert snapshot.native_launch_allowed is False
    assert snapshot.native_process_started is False


def test_unredacted_command_plan_blocks() -> None:
    snapshot = _snapshot(command_plan_redacted=False)

    assert snapshot.current_state is RealExecutorPrelaunchChainState.BLOCKED
    assert "command_plan_not_redacted" in snapshot.blocked_reasons
    assert snapshot.native_launch_allowed is False


def test_unsupported_executor_label_blocks() -> None:
    snapshot = _snapshot(executor_label="deepseek")

    assert snapshot.current_state is RealExecutorPrelaunchChainState.BLOCKED
    assert "executor_label_not_supported" in snapshot.blocked_reasons
    assert snapshot.native_launch_allowed is False


@pytest.mark.parametrize("executor_label", ["codex", "claude-code", "claude code"])
def test_all_ready_reaches_precheck_only_without_native_launch(executor_label: str) -> None:
    snapshot = _snapshot(executor_label=executor_label)

    assert snapshot.current_state in {
        RealExecutorPrelaunchChainState.READY_FOR_NATIVE_LAUNCH_PRECHECK,
        RealExecutorPrelaunchChainState.NATIVE_LAUNCH_NOT_STARTED,
    }
    assert snapshot.blocked_reasons == []
    assert snapshot.native_launch_allowed is False
    assert snapshot.native_process_started is False


def test_ordered_steps_are_fixed_and_complete() -> None:
    snapshot = _snapshot()

    assert [step.name for step in snapshot.ordered_steps] == EXPECTED_STEPS


def test_future_lifecycle_ordering_is_fixed() -> None:
    snapshot = _snapshot()

    assert snapshot.future_spawn_order == ["workspace", "runtime", "agent"]
    assert snapshot.future_cleanup_order == ["agent", "runtime", "workspace"]


def test_forbidden_flags_remain_false_in_every_response() -> None:
    snapshots = [
        RealExecutorPrelaunchChainBuilder().build(),
        _snapshot(silent_dispatch_ready=False),
        _snapshot(command_plan_redacted=False),
        _snapshot(executor_label="deepseek"),
        _snapshot(),
    ]

    for snapshot in snapshots:
        assert snapshot.native_process_started is False
        assert snapshot.product_runtime_git_write_allowed is False
        assert snapshot.frontend_required is False
        assert snapshot.frontend_change_allowed is False


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
        RealExecutorPrelaunchChainInput(**{field_name: True})


def test_status_and_payload_do_not_claim_forbidden_terminal_actions() -> None:
    body = " ".join(
        [
            _snapshot().current_state.value,
            *_snapshot(command_plan_redacted=False).blocked_reasons,
        ],
    ).lower()

    for forbidden in FORBIDDEN_STATUS_TERMS:
        assert forbidden not in body


def test_module_does_not_import_or_call_native_process_helpers() -> None:
    source = _source()

    for forbidden in FORBIDDEN_NATIVE_HELPERS:
        assert forbidden.lower() not in source.lower()


def test_module_and_response_exclude_sensitive_or_raw_output_terms() -> None:
    source = _source().lower()
    body = _snapshot().model_dump_json().lower()

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
