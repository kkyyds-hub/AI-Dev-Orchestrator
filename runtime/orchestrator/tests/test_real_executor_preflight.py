from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.external_executors.actual_contract import (
    RealExecutorLaunchContext,
    RealExecutorOperationStatus,
    RealExecutorSafetyBoundary,
)
from app.external_executors.actual_preflight import (
    RealExecutorPreflightInput,
    RealExecutorPreflightResult,
    RealExecutorPreflightService,
)


PREFLIGHT_FILE = Path("app/external_executors/actual_preflight.py")

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
    return PREFLIGHT_FILE.read_text()


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


def _context(boundary: RealExecutorSafetyBoundary) -> RealExecutorLaunchContext:
    return RealExecutorLaunchContext(
        request_id="request-1",
        executor_label="codex-safe-label",
        command_summary="future real executor launch summary",
        workspace_hint="registered worktree",
        safety_boundary=boundary,
    )


def test_real_executor_preflight_file_lives_under_external_executors() -> None:
    assert PREFLIGHT_FILE.is_file()
    assert PREFLIGHT_FILE.parts[:2] == ("app", "external_executors")


def test_real_executor_preflight_service_exists() -> None:
    service = RealExecutorPreflightService()

    assert hasattr(service, "evaluate")
    assert hasattr(service, "evaluate_launch")


def test_all_gates_passed_returns_ready_accepted() -> None:
    result = RealExecutorPreflightService().evaluate_launch(_context(_passing_boundary()))

    assert result.ready is True
    assert result.status is RealExecutorOperationStatus.ACCEPTED
    assert result.blocking_reasons == []
    assert result.product_runtime_git_write_allowed is False
    assert result.safe_summary is not None
    assert "status=accepted" in result.safe_summary


@pytest.mark.parametrize(
    ("missing_gate", "reason"),
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
def test_any_missing_gate_returns_blocked_reason(missing_gate: str, reason: str) -> None:
    values = _passing_boundary().model_dump()
    values[missing_gate] = False
    result = RealExecutorPreflightService().evaluate(
        RealExecutorPreflightInput(
            context=_context(RealExecutorSafetyBoundary(**values)),
            safe_summary="explicit safe summary",
        ),
    )

    assert result.ready is False
    assert result.status is RealExecutorOperationStatus.BLOCKED
    assert reason in result.blocking_reasons
    assert result.safe_summary == "explicit safe summary"
    assert result.product_runtime_git_write_allowed is False


def test_product_runtime_git_write_allowed_is_forbidden() -> None:
    with pytest.raises(ValidationError):
        RealExecutorPreflightInput(
            context=_context(_passing_boundary()),
            product_runtime_git_write_allowed=True,
        )

    with pytest.raises(ValidationError):
        RealExecutorPreflightResult(
            ready=True,
            status=RealExecutorOperationStatus.ACCEPTED,
            product_runtime_git_write_allowed=True,
        )


@pytest.mark.parametrize(
    "safe_summary",
    [
        "contains api key",
        "contains token",
        "contains secret",
        "contains password",
        "contains bearer value",
        "contains sk-test",
    ],
)
def test_safe_summary_rejects_suspected_credential_text(safe_summary: str) -> None:
    with pytest.raises(ValidationError):
        RealExecutorPreflightInput(
            context=_context(_passing_boundary()),
            safe_summary=safe_summary,
        )

    with pytest.raises(ValidationError):
        RealExecutorPreflightResult(
            ready=True,
            status=RealExecutorOperationStatus.ACCEPTED,
            safe_summary=safe_summary,
        )


def test_preflight_result_requires_status_consistency() -> None:
    with pytest.raises(ValidationError):
        RealExecutorPreflightResult(
            ready=True,
            status=RealExecutorOperationStatus.BLOCKED,
        )

    with pytest.raises(ValidationError):
        RealExecutorPreflightResult(
            ready=False,
            status=RealExecutorOperationStatus.BLOCKED,
        )


def test_actual_preflight_does_not_import_forbidden_layers_or_process_modules() -> None:
    source = _source()

    for snippet in FORBIDDEN_IMPORT_SNIPPETS:
        assert snippet not in source


def test_actual_preflight_does_not_contain_execution_traces() -> None:
    source = _source()

    for snippet in FORBIDDEN_EXECUTION_SNIPPETS:
        assert snippet not in source


def test_actual_preflight_does_not_read_environment_values() -> None:
    source = _source()

    for snippet in FORBIDDEN_ENVIRONMENT_SNIPPETS:
        assert snippet not in source


def test_actual_preflight_does_not_define_real_adapter_implementation() -> None:
    for node in _module().body:
        if isinstance(node, ast.ClassDef):
            assert node.name != "RealExecutorAdapter"


def test_actual_preflight_does_not_create_api_frontend_worker_or_migration_entrypoints() -> None:
    assert not Path("app/api/routes/real_executor.py").exists()
    assert not Path("app/api/routes/real_executors.py").exists()
    assert not Path("app/workers/real_executor_worker.py").exists()
    assert not any(Path("migrations").glob("*real_executor*"))
    assert not Path("../../apps/web/real-executors").exists()
