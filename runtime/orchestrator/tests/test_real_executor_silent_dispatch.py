from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.external_executors.actual_silent_dispatch import (
    RealExecutorSilentDispatchReadiness,
    RealExecutorSilentDispatchReadinessBuilder,
    RealExecutorSilentDispatchReadinessInput,
    RealExecutorSilentDispatchState,
)


SILENT_DISPATCH_FILE = Path("app/external_executors/actual_silent_dispatch.py")


def _source() -> str:
    return SILENT_DISPATCH_FILE.read_text()


def _readiness(
    payload: RealExecutorSilentDispatchReadinessInput | None = None,
) -> RealExecutorSilentDispatchReadiness:
    return RealExecutorSilentDispatchReadinessBuilder().build(payload)


def test_silent_dispatch_readiness_defaults_to_native_launch_not_started() -> None:
    readiness = _readiness()

    assert readiness.current_state is RealExecutorSilentDispatchState.NATIVE_LAUNCH_NOT_STARTED
    assert RealExecutorSilentDispatchState.BLOCKED in readiness.state_machine_states
    assert RealExecutorSilentDispatchState.READY_FOR_MANUAL_OPERATOR_VALIDATION in (
        readiness.state_machine_states
    )
    assert RealExecutorSilentDispatchState.NOOP_LIFECYCLE_READY in readiness.state_machine_states
    assert RealExecutorSilentDispatchState.NATIVE_LAUNCH_NOT_STARTED in (
        readiness.state_machine_states
    )


def test_silent_dispatch_readiness_marks_backend_prerequisites_ready() -> None:
    readiness = _readiness()

    assert readiness.adapter_skeleton_ready is True
    assert readiness.readback_api_ready is True
    assert readiness.noop_lifecycle_api_ready is True
    assert readiness.native_executor_launch_not_started is True
    assert readiness.product_runtime_git_write_forbidden is True


def test_silent_dispatch_readiness_keeps_frontend_frozen_and_native_process_off() -> None:
    readiness = _readiness()

    assert readiness.native_process_started is False
    assert readiness.product_runtime_git_write_allowed is False
    assert readiness.frontend_required is False
    assert readiness.frontend_change_allowed is False


def test_silent_dispatch_readiness_blocks_when_required_backend_prerequisites_are_missing() -> None:
    readiness = _readiness(
        RealExecutorSilentDispatchReadinessInput(
            adapter_skeleton_ready=False,
            readback_api_ready=False,
            noop_lifecycle_api_ready=False,
        ),
    )

    assert readiness.current_state is RealExecutorSilentDispatchState.BLOCKED
    assert "adapter_skeleton_missing" in readiness.blocking_reasons
    assert "readback_api_missing" in readiness.blocking_reasons
    assert "noop_lifecycle_api_missing" in readiness.blocking_reasons
    assert readiness.native_process_started is False
    assert readiness.product_runtime_git_write_allowed is False


def test_silent_dispatch_readiness_can_mark_manual_operator_validation_ready() -> None:
    readiness = _readiness(
        RealExecutorSilentDispatchReadinessInput(
            manual_operator_validation_ready=True,
        ),
    )

    assert readiness.current_state is (
        RealExecutorSilentDispatchState.READY_FOR_MANUAL_OPERATOR_VALIDATION
    )
    assert readiness.native_process_started is False
    assert readiness.product_runtime_git_write_allowed is False


def test_silent_dispatch_readiness_can_mark_noop_lifecycle_ready_before_native_launch() -> None:
    readiness = _readiness(
        RealExecutorSilentDispatchReadinessInput(
            manual_operator_validation_ready=True,
            noop_lifecycle_verified=True,
        ),
    )

    assert readiness.current_state is RealExecutorSilentDispatchState.NOOP_LIFECYCLE_READY
    assert readiness.native_executor_launch_not_started is True
    assert readiness.native_process_started is False
    assert readiness.product_runtime_git_write_allowed is False


@pytest.mark.parametrize(
    "field_name",
    [
        "native_process_started",
        "product_runtime_git_write_allowed",
        "frontend_required",
        "frontend_change_allowed",
    ],
)
def test_silent_dispatch_readiness_rejects_forbidden_true_flags(field_name: str) -> None:
    with pytest.raises(ValidationError):
        RealExecutorSilentDispatchReadinessInput(**{field_name: True})


def test_silent_dispatch_readiness_text_does_not_imply_execution_or_git_write() -> None:
    readiness = _readiness()
    safe_terms = " ".join(
        [
            readiness.current_state.value,
            *[state.value for state in readiness.state_machine_states],
            *readiness.blocking_reasons,
        ],
    ).lower()

    for forbidden in {
        "execute",
        "run",
        "start-native",
        "commit",
        "push",
        "merge",
        "launched_native",
        "completed_native",
    }:
        assert forbidden not in safe_terms


def test_silent_dispatch_module_does_not_import_or_call_native_process_helpers() -> None:
    source = _source()

    for forbidden in {
        "subprocess",
        "popen",
        "os.environ",
        "getenv",
        "shell=true",
        "create_subprocess",
    }:
        assert forbidden not in source.lower()


def test_silent_dispatch_module_and_response_exclude_sensitive_or_raw_output_terms() -> None:
    source = _source().lower()
    body = _readiness().model_dump_json().lower()

    for forbidden in {
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
    }:
        assert forbidden not in source
        assert forbidden not in body
