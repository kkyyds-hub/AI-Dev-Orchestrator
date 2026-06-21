from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.external_executors.actual_operator_validation import (
    OPERATOR_VALIDATION_SAFE_PHRASE,
    RealExecutorOperatorValidationGate,
    RealExecutorOperatorValidationInput,
    RealExecutorOperatorValidationScope,
    RealExecutorOperatorValidationStatus,
)


OPERATOR_VALIDATION_FILE = Path("app/external_executors/actual_operator_validation.py")


def _source() -> str:
    return OPERATOR_VALIDATION_FILE.read_text()


def _decision(
    payload: RealExecutorOperatorValidationInput | None = None,
):
    return RealExecutorOperatorValidationGate().evaluate(payload)


def test_operator_validation_defaults_to_not_accepted() -> None:
    decision = _decision()

    assert decision.status is RealExecutorOperatorValidationStatus.MISSING
    assert decision.operator_confirmed is False
    assert decision.validation_scope is RealExecutorOperatorValidationScope.NOOP_LIFECYCLE_VALIDATION
    assert decision.native_process_started is False
    assert decision.product_runtime_git_write_allowed is False


def test_operator_validation_stays_pending_without_operator_confirmation() -> None:
    decision = _decision(
        RealExecutorOperatorValidationInput(
            operator_confirmed=False,
            confirmation_phrase=OPERATOR_VALIDATION_SAFE_PHRASE,
        ),
    )

    assert decision.status is RealExecutorOperatorValidationStatus.PENDING
    assert decision.native_process_started is False
    assert decision.product_runtime_git_write_allowed is False


def test_operator_validation_rejects_mismatched_confirmation_phrase() -> None:
    decision = _decision(
        RealExecutorOperatorValidationInput(
            operator_confirmed=True,
            confirmation_phrase="I approve real launch",
        ),
    )

    assert decision.status is RealExecutorOperatorValidationStatus.REJECTED
    assert decision.native_process_started is False
    assert decision.product_runtime_git_write_allowed is False


def test_operator_validation_accepts_exact_safe_phrase_for_noop_validation_only() -> None:
    decision = _decision(
        RealExecutorOperatorValidationInput(
            operator_confirmed=True,
            confirmation_phrase=OPERATOR_VALIDATION_SAFE_PHRASE,
            validation_scope=RealExecutorOperatorValidationScope.NATIVE_LAUNCH_PRECHECK,
        ),
    )

    assert decision.status is RealExecutorOperatorValidationStatus.ACCEPTED_FOR_NOOP_VALIDATION
    assert decision.message == "Operator validation accepted for noop/manual precheck only"
    assert decision.native_process_started is False
    assert decision.product_runtime_git_write_allowed is False
    assert decision.frontend_required is False
    assert decision.frontend_change_allowed is False
    assert decision.secret_exposure_blocked is True
    assert decision.environment_dump_blocked is True


def test_operator_validation_rejects_scope_outside_allowlist() -> None:
    with pytest.raises(ValidationError):
        RealExecutorOperatorValidationInput(
            operator_confirmed=True,
            confirmation_phrase=OPERATOR_VALIDATION_SAFE_PHRASE,
            validation_scope="native_launch",
        )


@pytest.mark.parametrize(
    "scope",
    [
        RealExecutorOperatorValidationScope.NOOP_LIFECYCLE_VALIDATION,
        RealExecutorOperatorValidationScope.SILENT_DISPATCH_READINESS,
        RealExecutorOperatorValidationScope.NATIVE_LAUNCH_PRECHECK,
    ],
)
def test_operator_validation_allowlisted_scopes_do_not_start_native_process(
    scope: RealExecutorOperatorValidationScope,
) -> None:
    decision = _decision(
        RealExecutorOperatorValidationInput(
            operator_confirmed=True,
            confirmation_phrase=OPERATOR_VALIDATION_SAFE_PHRASE,
            validation_scope=scope,
        ),
    )

    assert decision.status is RealExecutorOperatorValidationStatus.ACCEPTED_FOR_NOOP_VALIDATION
    assert decision.validation_scope is scope
    assert decision.native_process_started is False
    assert decision.product_runtime_git_write_allowed is False


@pytest.mark.parametrize(
    "field_name",
    [
        "native_process_started",
        "product_runtime_git_write_allowed",
        "frontend_required",
        "frontend_change_allowed",
    ],
)
def test_operator_validation_input_rejects_forbidden_true_flags(field_name: str) -> None:
    with pytest.raises(ValidationError):
        RealExecutorOperatorValidationInput(**{field_name: True})


def test_operator_validation_status_and_messages_do_not_imply_execution_or_git_write() -> None:
    decisions = [
        _decision(),
        _decision(
            RealExecutorOperatorValidationInput(
                operator_confirmed=False,
                confirmation_phrase=OPERATOR_VALIDATION_SAFE_PHRASE,
            ),
        ),
        _decision(
            RealExecutorOperatorValidationInput(
                operator_confirmed=True,
                confirmation_phrase="wrong phrase",
            ),
        ),
        _decision(
            RealExecutorOperatorValidationInput(
                operator_confirmed=True,
                confirmation_phrase=OPERATOR_VALIDATION_SAFE_PHRASE,
            ),
        ),
    ]
    text = " ".join(
        f"{decision.status.value} {decision.message or ''}" for decision in decisions
    ).lower()

    for forbidden in {
        "execute",
        "run",
        "start-native",
        "launched",
        "completed_native",
        "commit",
        "push",
        "merge",
    }:
        assert forbidden not in text


def test_operator_validation_module_does_not_import_or_call_native_process_helpers() -> None:
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


def test_operator_validation_does_not_expose_raw_or_credential_material() -> None:
    source = _source().lower()
    decision = _decision(
        RealExecutorOperatorValidationInput(
            operator_confirmed=True,
            confirmation_phrase=OPERATOR_VALIDATION_SAFE_PHRASE,
        ),
    )
    body = decision.model_dump_json().lower()

    for forbidden in {
        "api_key",
        "bearer",
        "sk-",
        "password",
        "stdout",
        "stderr",
        "raw_command",
    }:
        assert forbidden not in source
        assert forbidden not in body
