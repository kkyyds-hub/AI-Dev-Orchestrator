from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain.executor_runtime_safety import (
    REQUIRED_RUNTIME_SAFETY_GATES,
    ExecutorLaunchApproval,
    ExecutorLaunchRequest,
    RuntimeApprovalDecision,
    RuntimeBudgetGateInput,
    RuntimeConcurrencyGateInput,
    RuntimeFeatureFlagPolicy,
    RuntimeLaunchBlockReason,
    RuntimeLaunchRequestStatus,
    RuntimeSafetyEvaluationInput,
    RuntimeSafetyGateCheck,
    RuntimeSafetyGateName,
    RuntimeSafetyGateSnapshot,
    RuntimeSafetyGateStatus,
    RuntimeWorkspaceGateInput,
)


def _now() -> datetime:
    return datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)


def _passed_check(gate_name: RuntimeSafetyGateName) -> RuntimeSafetyGateCheck:
    return RuntimeSafetyGateCheck(
        gate_name=gate_name,
        status=RuntimeSafetyGateStatus.PASSED,
        passed=True,
    )


def _blocked_check(
    gate_name: RuntimeSafetyGateName,
    block_reason: RuntimeLaunchBlockReason,
) -> RuntimeSafetyGateCheck:
    return RuntimeSafetyGateCheck(
        gate_name=gate_name,
        status=RuntimeSafetyGateStatus.BLOCKED,
        passed=False,
        block_reason=block_reason,
    )


def _all_passed_snapshot() -> RuntimeSafetyGateSnapshot:
    return RuntimeSafetyGateSnapshot(
        gate_checks=[_passed_check(gate) for gate in REQUIRED_RUNTIME_SAFETY_GATES],
        evaluated_at=_now(),
    )


def _checks_with_replacements(
    replacements: dict[RuntimeSafetyGateName, RuntimeSafetyGateCheck],
) -> list[RuntimeSafetyGateCheck]:
    return [
        replacements.get(gate, _passed_check(gate))
        for gate in REQUIRED_RUNTIME_SAFETY_GATES
    ]


def _blocked_snapshot() -> RuntimeSafetyGateSnapshot:
    return RuntimeSafetyEvaluationInput().evaluate()


def _request(**overrides) -> ExecutorLaunchRequest:
    values = {
        "request_id": "request-1",
        "executor_id": "codex",
        "launch_preview_id": "preview-1",
        "safety_snapshot": _all_passed_snapshot(),
        "created_at": _now(),
    }
    values.update(overrides)
    return ExecutorLaunchRequest(**values)


def test_feature_flag_policy_defaults_all_false() -> None:
    policy = RuntimeFeatureFlagPolicy()

    assert policy.executor_runtime_enabled is False
    assert policy.real_executor_pilot_enabled is False
    assert policy.product_runtime_git_write_enabled is False


def test_feature_flag_default_gate_check_is_blocked() -> None:
    check = RuntimeFeatureFlagPolicy().gate_check()

    assert check.gate_name == RuntimeSafetyGateName.FEATURE_FLAG
    assert check.status == RuntimeSafetyGateStatus.BLOCKED
    assert check.passed is False
    assert check.block_reason == RuntimeLaunchBlockReason.FEATURE_FLAG_DISABLED


def test_passed_gate_check_requires_passed_true_and_no_block_reason() -> None:
    with pytest.raises(ValidationError):
        RuntimeSafetyGateCheck(
            gate_name=RuntimeSafetyGateName.FEATURE_FLAG,
            status=RuntimeSafetyGateStatus.PASSED,
            passed=False,
        )

    with pytest.raises(ValidationError):
        RuntimeSafetyGateCheck(
            gate_name=RuntimeSafetyGateName.FEATURE_FLAG,
            status=RuntimeSafetyGateStatus.PASSED,
            passed=True,
            block_reason=RuntimeLaunchBlockReason.FEATURE_FLAG_DISABLED,
        )


def test_blocked_gate_check_requires_passed_false_and_block_reason() -> None:
    with pytest.raises(ValidationError):
        RuntimeSafetyGateCheck(
            gate_name=RuntimeSafetyGateName.FEATURE_FLAG,
            status=RuntimeSafetyGateStatus.BLOCKED,
            passed=True,
            block_reason=RuntimeLaunchBlockReason.FEATURE_FLAG_DISABLED,
        )

    with pytest.raises(ValidationError):
        RuntimeSafetyGateCheck(
            gate_name=RuntimeSafetyGateName.FEATURE_FLAG,
            status=RuntimeSafetyGateStatus.BLOCKED,
            passed=False,
        )


def test_gate_check_safe_summary_rejects_suspected_credential_material() -> None:
    with pytest.raises(ValidationError):
        RuntimeSafetyGateCheck(
            gate_name=RuntimeSafetyGateName.NO_SECRET_EXPOSURE,
            safe_summary="contains api key value",
        )


def test_safety_gate_snapshot_must_cover_all_required_gates() -> None:
    missing_one = [
        _passed_check(gate)
        for gate in REQUIRED_RUNTIME_SAFETY_GATES
        if gate != RuntimeSafetyGateName.AUDIT_EVENT
    ]

    with pytest.raises(ValidationError):
        RuntimeSafetyGateSnapshot(gate_checks=missing_one)


def test_safety_gate_snapshot_all_passed_cannot_be_forged_when_blocked() -> None:
    blocked_feature_flag = _blocked_check(
        RuntimeSafetyGateName.FEATURE_FLAG,
        RuntimeLaunchBlockReason.FEATURE_FLAG_DISABLED,
    )
    checks = _checks_with_replacements(
        {RuntimeSafetyGateName.FEATURE_FLAG: blocked_feature_flag},
    )
    snapshot = RuntimeSafetyGateSnapshot(gate_checks=checks, all_passed=True)

    assert snapshot.all_passed is False
    assert snapshot.failed_gates() == [blocked_feature_flag]
    assert snapshot.get_gate(RuntimeSafetyGateName.FEATURE_FLAG) == blocked_feature_flag


def test_safety_gate_snapshot_blocking_reasons_are_deduplicated() -> None:
    checks = _checks_with_replacements(
        {
            RuntimeSafetyGateName.FEATURE_FLAG: _blocked_check(
                RuntimeSafetyGateName.FEATURE_FLAG,
                RuntimeLaunchBlockReason.UNKNOWN,
            ),
            RuntimeSafetyGateName.HUMAN_CONFIRMATION: _blocked_check(
                RuntimeSafetyGateName.HUMAN_CONFIRMATION,
                RuntimeLaunchBlockReason.UNKNOWN,
            ),
        },
    )
    snapshot = RuntimeSafetyGateSnapshot(gate_checks=checks)

    assert snapshot.blocking_reasons == [RuntimeLaunchBlockReason.UNKNOWN]


@pytest.mark.parametrize(
    "path_hint",
    [
        "/Users/kk/project",
        "~/project",
        "C:\\Users\\kk\\project",
        "\\\\server\\share\\project",
    ],
)
def test_workspace_path_hint_sanitizes_sensitive_path_shapes(path_hint: str) -> None:
    gate_input = RuntimeWorkspaceGateInput(workspace_path_hint=path_hint)

    assert gate_input.workspace_path_hint == "workspace hint provided"


@pytest.mark.parametrize(
    "field_name",
    ["estimated_cost", "session_budget_limit", "daily_budget_remaining"],
)
def test_budget_gate_input_rejects_negative_amounts(field_name: str) -> None:
    with pytest.raises(ValidationError):
        RuntimeBudgetGateInput(**{field_name: Decimal("-0.01")})


def test_budget_gate_blocks_when_estimated_cost_exceeds_session_limit() -> None:
    snapshot = RuntimeSafetyEvaluationInput(
        budget=RuntimeBudgetGateInput(
            estimated_cost=Decimal("2"),
            session_budget_limit=Decimal("1"),
        ),
    ).evaluate()

    assert RuntimeLaunchBlockReason.BUDGET_EXCEEDED in snapshot.blocking_reasons
    assert snapshot.get_gate(RuntimeSafetyGateName.COST_BUDGET).status == (
        RuntimeSafetyGateStatus.BLOCKED
    )


def test_budget_gate_blocks_when_estimated_cost_exceeds_daily_remaining() -> None:
    snapshot = RuntimeSafetyEvaluationInput(
        budget=RuntimeBudgetGateInput(
            estimated_cost=Decimal("2"),
            daily_budget_remaining=Decimal("1"),
        ),
    ).evaluate()

    assert RuntimeLaunchBlockReason.BUDGET_EXCEEDED in snapshot.blocking_reasons


def test_concurrency_gate_input_validates_counts() -> None:
    with pytest.raises(ValidationError):
        RuntimeConcurrencyGateInput(active_session_count=-1)

    with pytest.raises(ValidationError):
        RuntimeConcurrencyGateInput(max_concurrent_sessions=0)


def test_concurrency_gate_blocks_when_active_count_reaches_limit() -> None:
    snapshot = RuntimeSafetyEvaluationInput(
        concurrency=RuntimeConcurrencyGateInput(
            active_session_count=1,
            max_concurrent_sessions=1,
        ),
    ).evaluate()

    assert RuntimeLaunchBlockReason.CONCURRENCY_LIMIT_REACHED in snapshot.blocking_reasons


def test_default_safety_evaluation_blocks_required_launch_prerequisites() -> None:
    snapshot = RuntimeSafetyEvaluationInput().evaluate()

    assert snapshot.all_passed is False
    assert RuntimeLaunchBlockReason.FEATURE_FLAG_DISABLED in snapshot.blocking_reasons
    assert RuntimeLaunchBlockReason.HUMAN_CONFIRMATION_REQUIRED in snapshot.blocking_reasons
    assert RuntimeLaunchBlockReason.EXECUTOR_NOT_READY in snapshot.blocking_reasons
    assert RuntimeLaunchBlockReason.LAUNCH_PREVIEW_MISSING in snapshot.blocking_reasons
    assert RuntimeLaunchBlockReason.WORKSPACE_NOT_BOUND in snapshot.blocking_reasons


def test_safety_evaluation_all_conditions_satisfied_passes() -> None:
    snapshot = RuntimeSafetyEvaluationInput(
        feature_flags=RuntimeFeatureFlagPolicy(executor_runtime_enabled=True),
        executor_ready=True,
        launch_preview_ready=True,
        workspace=RuntimeWorkspaceGateInput(workspace_bound=True),
        budget=RuntimeBudgetGateInput(
            estimated_cost=Decimal("1"),
            session_budget_limit=Decimal("2"),
            daily_budget_remaining=Decimal("3"),
        ),
        concurrency=RuntimeConcurrencyGateInput(
            active_session_count=0,
            max_concurrent_sessions=1,
        ),
        human_confirmed=True,
        timeout_configured=True,
        cancellation_supported=True,
        audit_event_ready=True,
        no_secret_exposure=True,
        no_env_dump=True,
        no_product_git_write=True,
    ).evaluate()

    assert snapshot.all_passed is True
    assert snapshot.blocking_reasons == []


def test_no_product_git_write_false_is_blocked() -> None:
    snapshot = RuntimeSafetyEvaluationInput(no_product_git_write=False).evaluate()

    assert RuntimeLaunchBlockReason.PRODUCT_GIT_WRITE_FORBIDDEN in snapshot.blocking_reasons
    assert snapshot.get_gate(RuntimeSafetyGateName.NO_PRODUCT_GIT_WRITE).status == (
        RuntimeSafetyGateStatus.BLOCKED
    )


def test_secret_and_env_guards_false_are_blocked() -> None:
    snapshot = RuntimeSafetyEvaluationInput(
        no_secret_exposure=False,
        no_env_dump=False,
    ).evaluate()

    assert RuntimeLaunchBlockReason.SECRET_EXPOSURE_RISK in snapshot.blocking_reasons
    assert RuntimeLaunchBlockReason.ENV_DUMP_RISK in snapshot.blocking_reasons


def test_launch_request_default_status_is_not_approved() -> None:
    request = _request()

    assert request.status == RuntimeLaunchRequestStatus.DRAFT
    assert request.status != RuntimeLaunchRequestStatus.APPROVED


def test_launch_request_cannot_be_approved_when_safety_snapshot_failed() -> None:
    with pytest.raises(ValidationError):
        _request(
            status=RuntimeLaunchRequestStatus.APPROVED,
            human_confirmation_required=False,
            safety_snapshot=_blocked_snapshot(),
        )


def test_launch_request_approved_status_requires_approved_at_when_confirmation_required() -> None:
    with pytest.raises(ValidationError):
        _request(status=RuntimeLaunchRequestStatus.APPROVED)

    request = _request(
        status=RuntimeLaunchRequestStatus.APPROVED,
        approved_at=_now(),
    )

    assert request.status == RuntimeLaunchRequestStatus.APPROVED


def test_launch_request_required_ids_trim_and_reject_empty_strings() -> None:
    request = _request(
        request_id=" request-1 ",
        executor_id=" codex ",
        launch_preview_id=" preview-1 ",
    )

    assert request.request_id == "request-1"
    assert request.executor_id == "codex"
    assert request.launch_preview_id == "preview-1"

    with pytest.raises(ValidationError):
        _request(request_id="   ")

    with pytest.raises(ValidationError):
        _request(executor_id="   ")

    with pytest.raises(ValidationError):
        _request(launch_preview_id="   ")


def test_launch_request_expires_at_cannot_be_earlier_than_created_at() -> None:
    with pytest.raises(ValidationError):
        _request(expires_at=_now() - timedelta(seconds=1))


def test_launch_request_approved_at_cannot_be_earlier_than_created_at() -> None:
    with pytest.raises(ValidationError):
        _request(approved_at=_now() - timedelta(seconds=1))


def test_launch_request_consumed_at_cannot_be_earlier_than_approved_at() -> None:
    with pytest.raises(ValidationError):
        _request(
            approved_at=_now(),
            consumed_at=_now() - timedelta(seconds=1),
        )


def test_launch_request_merges_blocked_reasons_from_safety_snapshot() -> None:
    request = _request(
        safety_snapshot=_blocked_snapshot(),
        blocked_reasons=[RuntimeLaunchBlockReason.FEATURE_FLAG_DISABLED],
    )

    assert request.blocked_reasons.count(
        RuntimeLaunchBlockReason.FEATURE_FLAG_DISABLED,
    ) == 1
    assert RuntimeLaunchBlockReason.HUMAN_CONFIRMATION_REQUIRED in request.blocked_reasons


def test_launch_approval_default_decision_is_pending_not_approved() -> None:
    approval = ExecutorLaunchApproval(
        approval_id="approval-1",
        request_id="request-1",
    )

    assert approval.decision == RuntimeApprovalDecision.PENDING
    assert approval.decision != RuntimeApprovalDecision.APPROVED


def test_launch_approval_approved_decision_requires_decided_by_and_decided_at() -> None:
    with pytest.raises(ValidationError):
        ExecutorLaunchApproval(
            approval_id="approval-1",
            request_id="request-1",
            decision=RuntimeApprovalDecision.APPROVED,
            decided_at=_now(),
        )

    with pytest.raises(ValidationError):
        ExecutorLaunchApproval(
            approval_id="approval-1",
            request_id="request-1",
            decision=RuntimeApprovalDecision.APPROVED,
            decided_by="user",
        )


def test_launch_approval_required_ids_trim_and_reject_empty_strings() -> None:
    approval = ExecutorLaunchApproval(
        approval_id=" approval-1 ",
        request_id=" request-1 ",
    )

    assert approval.approval_id == "approval-1"
    assert approval.request_id == "request-1"

    with pytest.raises(ValidationError):
        ExecutorLaunchApproval(approval_id="   ", request_id="request-1")

    with pytest.raises(ValidationError):
        ExecutorLaunchApproval(approval_id="approval-1", request_id="   ")


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("confirmation_text", "contains token value"),
        ("safe_summary", "Bearer abc"),
    ],
)
def test_launch_approval_text_fields_reject_suspected_credential_material(
    field_name: str,
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        ExecutorLaunchApproval(
            approval_id="approval-1",
            request_id="request-1",
            **{field_name: value},
        )


def test_executor_runtime_safety_domain_does_not_import_service_api_or_worker_layers() -> None:
    source = Path("app/domain/executor_runtime_safety.py").read_text()

    assert "app.services" not in source
    assert "app.api" not in source
    assert "app.workers" not in source


def test_executor_runtime_safety_domain_does_not_import_subprocess_shell_helpers() -> None:
    source = Path("app/domain/executor_runtime_safety.py").read_text()

    assert "import subprocess" not in source
    assert "os.popen" not in source


def test_executor_runtime_safety_domain_excludes_forbidden_runtime_fields() -> None:
    source = Path("app/domain/executor_runtime_safety.py").read_text()
    forbidden_terms = {
        "command",
        "raw_command",
        "raw_args",
        "env_vars",
        "api_key",
        "token_value",
        "auth_token",
        "secret",
        "native_config_path",
        "cli_path",
        "process_handle",
        "log_path",
    }

    for term in forbidden_terms:
        assert f"{term}:" not in source


def test_reference_project_path_is_not_copied_into_executor_runtime_safety_domain() -> None:
    source = Path("app/domain/executor_runtime_safety.py").read_text()

    assert "/Users/kk/project explore/agent-orchestrator" not in source
    assert "project-explore-one" not in source
