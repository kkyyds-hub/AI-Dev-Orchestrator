from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import get_type_hints

import pytest
from pydantic import ValidationError

from app.external_executors.actual_contract import (
    RealExecutorAdapterProtocol,
    RealExecutorCapability,
    RealExecutorLaunchContext,
    RealExecutorLifecycleIntent,
    RealExecutorOperationResult,
    RealExecutorOperationStatus,
    RealExecutorPollSnapshot,
    RealExecutorPollState,
    RealExecutorSafetyBoundary,
)


CONTRACT_FILE = Path("app/external_executors/actual_contract.py")

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
    "os.popen",
    "shell=True",
    "Popen",
    "asyncio.create_subprocess_exec",
    "asyncio.create_subprocess_shell",
    "tmux",
    "Codex CLI",
    "Claude Code",
    "DeepSeek CLI",
}


def _source() -> str:
    return CONTRACT_FILE.read_text()


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


def test_real_executor_contract_file_lives_under_external_executors() -> None:
    assert CONTRACT_FILE.is_file()
    assert CONTRACT_FILE.parts[:2] == ("app", "external_executors")


def test_real_executor_adapter_protocol_declares_only_contract_methods() -> None:
    methods = {
        name: member
        for name, member in inspect.getmembers(RealExecutorAdapterProtocol)
        if inspect.isfunction(member) and not name.startswith("_")
    }

    assert set(methods) == {"launch", "poll", "cancel", "kill", "cleanup"}

    type_hints = {
        name: get_type_hints(member, globalns=member.__globals__)
        for name, member in methods.items()
    }
    assert type_hints["launch"]["context"] is RealExecutorLaunchContext
    assert type_hints["launch"]["return"] is RealExecutorOperationResult
    assert type_hints["poll"]["session_id"] is str
    assert type_hints["poll"]["return"] is RealExecutorPollSnapshot
    assert type_hints["cancel"]["session_id"] is str
    assert type_hints["cancel"]["reason"] is str
    assert type_hints["cancel"]["return"] is RealExecutorOperationResult
    assert type_hints["kill"]["session_id"] is str
    assert type_hints["kill"]["reason"] is str
    assert type_hints["kill"]["return"] is RealExecutorOperationResult
    assert type_hints["cleanup"]["session_id"] is str
    assert type_hints["cleanup"]["return"] is RealExecutorOperationResult


def test_capabilities_and_lifecycle_intents_are_explicit_contract_enums() -> None:
    assert {item.value for item in RealExecutorLifecycleIntent} == {
        "launch",
        "poll",
        "cancel",
        "kill",
        "cleanup",
    }
    assert {item.value for item in RealExecutorCapability} == {
        "launch",
        "poll",
        "cancel",
        "kill",
        "cleanup",
        "timeout",
        "append_only_audit",
        "block_credential_exposure",
        "block_environment_dump",
        "block_product_runtime_git_write",
    }


def test_safety_boundary_defaults_block_launch_and_product_runtime_git_write() -> None:
    boundary = RealExecutorSafetyBoundary()

    assert boundary.is_launchable() is False
    assert boundary.product_runtime_git_write_allowed is False
    assert set(boundary.blocking_reasons()) == {
        "feature_flag_disabled",
        "human_confirmation_missing",
        "executor_readiness_missing",
        "workspace_worktree_gate_failed",
        "budget_cost_gate_failed",
        "concurrency_gate_failed",
        "timeout_not_supported",
        "cancel_not_supported",
        "kill_not_supported",
    }


def test_safety_boundary_requires_all_launch_gates() -> None:
    boundary = RealExecutorSafetyBoundary(
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

    assert boundary.is_launchable() is True
    assert boundary.blocking_reasons() == ()


@pytest.mark.parametrize(
    "missing_gate,reason",
    [
        ("feature_flag_enabled", "feature_flag_disabled"),
        ("human_confirmation_present", "human_confirmation_missing"),
        ("executor_readiness_available", "executor_readiness_missing"),
        ("workspace_worktree_gate_passed", "workspace_worktree_gate_failed"),
        ("budget_cost_gate_passed", "budget_cost_gate_failed"),
        ("concurrency_gate_passed", "concurrency_gate_failed"),
        ("timeout_supported", "timeout_not_supported"),
        ("cancel_supported", "cancel_not_supported"),
        ("kill_supported", "kill_not_supported"),
        ("audit_events_append_only", "audit_events_not_append_only"),
        ("credential_exposure_blocked", "credential_exposure_not_blocked"),
        ("environment_dump_blocked", "environment_dump_not_blocked"),
    ],
)
def test_any_missing_safety_gate_blocks_launch(missing_gate: str, reason: str) -> None:
    values = {
        "feature_flag_enabled": True,
        "human_confirmation_present": True,
        "executor_readiness_available": True,
        "workspace_worktree_gate_passed": True,
        "budget_cost_gate_passed": True,
        "concurrency_gate_passed": True,
        "timeout_supported": True,
        "cancel_supported": True,
        "kill_supported": True,
        "audit_events_append_only": True,
        "credential_exposure_blocked": True,
        "environment_dump_blocked": True,
    }
    values[missing_gate] = False

    boundary = RealExecutorSafetyBoundary(**values)

    assert boundary.is_launchable() is False
    assert reason in boundary.blocking_reasons()


def test_launch_context_derives_blocked_or_accepted_status_from_safety_boundary() -> None:
    blocked_context = RealExecutorLaunchContext(
        request_id="request-1",
        executor_label="codex-safe-label",
    )
    assert blocked_context.operation_status() is RealExecutorOperationStatus.BLOCKED

    accepted_context = RealExecutorLaunchContext(
        request_id="request-2",
        executor_label="codex-safe-label",
        command_summary="summarized future launch intent",
        workspace_hint="registered worktree",
        safety_boundary=RealExecutorSafetyBoundary(
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
        ),
    )
    assert accepted_context.operation_status() is RealExecutorOperationStatus.ACCEPTED


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("executor_label", "executor with api key"),
        ("command_summary", "run with bearer value"),
        ("command_summary", "launch using sk-test"),
        ("workspace_hint", "token workspace"),
        ("workspace_hint", "secret folder"),
        ("executor_label", "password label"),
    ],
)
def test_safe_summary_fields_reject_suspected_credential_text(
    field_name: str,
    value: str,
) -> None:
    payload = {
        "request_id": "request-1",
        "executor_label": "safe executor",
    }
    payload[field_name] = value

    with pytest.raises(ValidationError):
        RealExecutorLaunchContext(**payload)


def test_result_and_poll_snapshot_reject_product_runtime_git_write() -> None:
    with pytest.raises(ValidationError):
        RealExecutorSafetyBoundary(product_runtime_git_write_allowed=True)

    with pytest.raises(ValidationError):
        RealExecutorOperationResult(
            lifecycle_intent=RealExecutorLifecycleIntent.LAUNCH,
            status=RealExecutorOperationStatus.ACCEPTED,
            product_runtime_git_write_allowed=True,
        )

    with pytest.raises(ValidationError):
        RealExecutorPollSnapshot(
            session_id="session-1",
            poll_state=RealExecutorPollState.RUNNING,
            product_runtime_git_write_allowed=True,
        )


def test_contract_models_forbid_extra_runtime_fields() -> None:
    with pytest.raises(ValidationError):
        RealExecutorLaunchContext(
            request_id="request-1",
            executor_label="safe executor",
            raw_command="not allowed",
        )

    with pytest.raises(ValidationError):
        RealExecutorOperationResult(
            lifecycle_intent=RealExecutorLifecycleIntent.LAUNCH,
            status=RealExecutorOperationStatus.ACCEPTED,
            process_handle="not allowed",
        )


def test_contract_field_names_do_not_include_forbidden_runtime_fields() -> None:
    checked_classes = {
        "RealExecutorLaunchContext",
        "RealExecutorPollSnapshot",
        "RealExecutorOperationResult",
        "RealExecutorSafetyBoundary",
    }

    for class_name in checked_classes:
        assert _class_field_names(class_name).isdisjoint(FORBIDDEN_RUNTIME_FIELDS)


def test_actual_contract_does_not_import_forbidden_layers_or_process_modules() -> None:
    source = _source()

    for snippet in FORBIDDEN_IMPORT_SNIPPETS:
        assert snippet not in source


def test_actual_contract_does_not_contain_execution_traces() -> None:
    source = _source()

    for snippet in FORBIDDEN_EXECUTION_SNIPPETS:
        assert snippet not in source


def test_actual_contract_does_not_define_real_adapter_implementation() -> None:
    for node in _module().body:
        if isinstance(node, ast.ClassDef):
            assert node.name != "RealExecutorAdapter"


def test_actual_contract_does_not_create_api_frontend_worker_or_migration_entrypoints() -> None:
    assert not Path("app/api/routes/real_executor.py").exists()
    assert not Path("app/api/routes/real_executors.py").exists()
    assert not Path("app/workers/real_executor_worker.py").exists()
    assert not any(Path("migrations").glob("*real_executor*"))
    assert not Path("../../apps/web/real-executors").exists()
