"""Targeted tests for P5-B failure recovery decision pure domain model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.failure_recovery_decision import (
    P5_FAILURE_RECOVERY_DECISION_AUDIT_EVENT_TYPE,
    P5_FAILURE_RECOVERY_DECISION_SOURCE,
    P5_FAILURE_RECOVERY_DECISION_VERSION,
    P5B_FORBIDDEN_TRUE_SAFETY_FLAGS,
    FailureRecoveryDecision,
    FailureRecoveryDecisionBuilder,
    FailureRecoveryDecisionSafetyFlags,
    InstructionKind,
    RecoveryNextAction,
    RecoveryOwner,
)
from app.domain.run import RunFailureCategory
from app.domain.task import TaskBlockingReasonCode


EXPECTED_FALSE_SAFETY_FLAGS = {
    "runs_git": False,
    "runs_write_git": False,
    "git_add_triggered": False,
    "git_commit_triggered": False,
    "git_push_triggered": False,
    "pr_opened": False,
    "merge_triggered": False,
    "branch_deleted": False,
    "git_reset_triggered": False,
    "git_checkout_triggered": False,
    "git_switch_triggered": False,
    "git_stash_triggered": False,
    "git_rebase_triggered": False,
    "git_tag_triggered": False,
    "ci_triggered": False,
    "execution_enabled": False,
    "worker_dispatch_triggered": False,
    "api_response_exposed": False,
    "agent_message_written": False,
    "task_created": False,
    "retry_triggered": False,
}

FORBIDDEN_USER_VISIBLE_GIT_WRITE_COPY = (
    "git add",
    "git commit",
    "git push",
    "PR",
    "merge",
    "删除 branch",
    "reset",
    "checkout",
    "switch",
    "stash",
    "rebase",
    "tag",
)


def _assert_pure_contract(decision: FailureRecoveryDecision) -> None:
    assert decision.source == P5_FAILURE_RECOVERY_DECISION_SOURCE
    assert decision.version == P5_FAILURE_RECOVERY_DECISION_VERSION
    assert decision.audit_event_type == P5_FAILURE_RECOVERY_DECISION_AUDIT_EVENT_TYPE
    assert decision.rule_codes
    assert decision.safety_flags.model_dump() == EXPECTED_FALSE_SAFETY_FLAGS
    assert decision.next_instruction_draft_required == (
        decision.next_instruction_draft is not None
    )
    assert _contains_cjk(decision.user_visible_summary_cn)
    assert not any(
        copy in decision.user_visible_summary_cn
        for copy in FORBIDDEN_USER_VISIBLE_GIT_WRITE_COPY
    )
    if decision.human_decision_reason is not None:
        assert _contains_cjk(decision.human_decision_reason)
        assert not any(
            copy in decision.human_decision_reason
            for copy in FORBIDDEN_USER_VISIBLE_GIT_WRITE_COPY
        )
    if decision.next_instruction_draft is not None:
        assert _contains_cjk(decision.next_instruction_draft)
        assert not any(
            copy in decision.next_instruction_draft
            for copy in FORBIDDEN_USER_VISIBLE_GIT_WRITE_COPY
        )

    payload = decision.model_dump(mode="json")
    assert payload["source"] == P5_FAILURE_RECOVERY_DECISION_SOURCE
    assert payload["version"] == P5_FAILURE_RECOVERY_DECISION_VERSION
    assert payload["audit_event_type"] == P5_FAILURE_RECOVERY_DECISION_AUDIT_EVENT_TYPE
    assert payload["safety_flags"] == EXPECTED_FALSE_SAFETY_FLAGS
    assert payload["next_instruction_draft_required"] == (
        payload["next_instruction_draft"] is not None
    )


def _contains_cjk(value: str) -> bool:
    return any(
        "\u4e00" <= char <= "\u9fff"
        or "\u3400" <= char <= "\u4dbf"
        or "\uf900" <= char <= "\ufaff"
        for char in value
    )


def test_execution_failure_routes_to_codex_fix_and_retry_without_human_decision():
    decision = FailureRecoveryDecisionBuilder.build(
        failure_category=RunFailureCategory.EXECUTION_FAILED,
    )

    _assert_pure_contract(decision)
    assert decision.failure_category == RunFailureCategory.EXECUTION_FAILED
    assert decision.reason_code is None
    assert decision.recoverable is True
    assert decision.retry_allowed is True
    assert decision.recommended_owner == RecoveryOwner.CODEX
    assert decision.next_action == RecoveryNextAction.FIX_AND_RETRY
    assert decision.next_instruction_kind == InstructionKind.CODE_FIX
    assert decision.next_instruction_draft_required is True
    assert decision.next_instruction_draft is not None
    assert "Codex" in decision.next_instruction_draft
    assert decision.requires_human_decision is False
    assert decision.human_decision_reason is None
    assert "Codex" in decision.user_visible_summary_cn
    assert decision.rule_codes == ["failure_execution_codex_fix_and_retry"]


def test_verification_failure_routes_to_codex_test_fix():
    decision = FailureRecoveryDecisionBuilder.build(
        failure_category=RunFailureCategory.VERIFICATION_FAILED,
    )

    _assert_pure_contract(decision)
    assert decision.recoverable is True
    assert decision.retry_allowed is True
    assert decision.recommended_owner == RecoveryOwner.CODEX
    assert decision.next_action == RecoveryNextAction.FIX_AND_RETRY
    assert decision.next_instruction_kind == InstructionKind.TEST_FIX
    assert decision.next_instruction_draft_required is True
    assert decision.requires_human_decision is False
    assert "验证失败" in decision.user_visible_summary_cn
    assert decision.rule_codes == ["failure_verification_codex_test_fix"]


def test_verification_configuration_failure_routes_to_deepseek_config_fix():
    decision = FailureRecoveryDecisionBuilder.build(
        failure_category=RunFailureCategory.VERIFICATION_CONFIGURATION_FAILED,
    )

    _assert_pure_contract(decision)
    assert decision.recoverable is True
    assert decision.retry_allowed is False
    assert decision.recommended_owner == RecoveryOwner.DEEPSEEK
    assert decision.next_action == RecoveryNextAction.FIX_AND_RETRY
    assert decision.next_instruction_kind == InstructionKind.CONFIG_FIX
    assert decision.next_instruction_draft_required is True
    assert decision.next_instruction_draft is not None
    assert "DeepSeek" in decision.next_instruction_draft
    assert decision.requires_human_decision is False
    assert "暂不直接重试" in decision.user_visible_summary_cn
    assert decision.rule_codes == ["failure_verification_config_deepseek_config_fix"]


@pytest.mark.parametrize(
    "failure_category",
    [
        RunFailureCategory.DAILY_BUDGET_EXCEEDED,
        RunFailureCategory.SESSION_BUDGET_EXCEEDED,
    ],
)
def test_budget_failure_requires_user_decision_and_blocks_retry(failure_category):
    decision = FailureRecoveryDecisionBuilder.build(
        failure_category=failure_category,
    )

    _assert_pure_contract(decision)
    assert decision.recoverable is False
    assert decision.retry_allowed is False
    assert decision.recommended_owner == RecoveryOwner.USER
    assert decision.next_action == RecoveryNextAction.ESCALATE_TO_HUMAN
    assert decision.next_instruction_kind == InstructionKind.HUMAN_QUESTION
    assert decision.next_instruction_draft_required is False
    assert decision.next_instruction_draft is None
    assert decision.requires_human_decision is True
    assert decision.human_decision_reason == (
        "涉及预算限制，需要用户确认是否增加预算或调整策略。"
    )
    assert "预算" in decision.user_visible_summary_cn
    assert decision.rule_codes == ["failure_budget_user_decision"]


def test_budget_reason_code_overrides_execution_failure_to_user_decision():
    decision = FailureRecoveryDecisionBuilder.build(
        failure_category=RunFailureCategory.EXECUTION_FAILED,
        reason_code=TaskBlockingReasonCode.BUDGET_GUARD_BLOCKED,
    )

    _assert_pure_contract(decision)
    assert decision.failure_category == RunFailureCategory.EXECUTION_FAILED
    assert decision.reason_code == TaskBlockingReasonCode.BUDGET_GUARD_BLOCKED
    assert decision.recommended_owner == RecoveryOwner.USER
    assert decision.retry_allowed is False
    assert decision.next_instruction_draft_required is False
    assert decision.next_instruction_draft is None
    assert decision.requires_human_decision is True
    assert "预算" in decision.human_decision_reason
    assert decision.rule_codes == ["reason_budget_guard_blocked"]


def test_retry_limit_exceeded_requires_user_decision():
    decision = FailureRecoveryDecisionBuilder.build(
        failure_category=RunFailureCategory.RETRY_LIMIT_EXCEEDED,
    )

    _assert_pure_contract(decision)
    assert decision.recoverable is False
    assert decision.retry_allowed is False
    assert decision.recommended_owner == RecoveryOwner.USER
    assert decision.next_action == RecoveryNextAction.ESCALATE_TO_HUMAN
    assert decision.next_instruction_kind == InstructionKind.HUMAN_QUESTION
    assert decision.next_instruction_draft_required is False
    assert decision.next_instruction_draft is None
    assert decision.requires_human_decision is True
    assert "重试上限" in decision.human_decision_reason
    assert decision.rule_codes == ["failure_retry_limit_user_decision"]


@pytest.mark.parametrize(
    "reason_code",
    [
        TaskBlockingReasonCode.TASK_WAITING_HUMAN,
        TaskBlockingReasonCode.HUMAN_REVIEW_REQUESTED,
        TaskBlockingReasonCode.HUMAN_REVIEW_IN_PROGRESS,
    ],
)
def test_human_reason_codes_require_user_decision(reason_code):
    decision = FailureRecoveryDecisionBuilder.build(
        failure_category=RunFailureCategory.EXECUTION_FAILED,
        reason_code=reason_code,
    )

    _assert_pure_contract(decision)
    assert decision.reason_code == reason_code
    assert decision.recommended_owner == RecoveryOwner.USER
    assert decision.next_action == RecoveryNextAction.ESCALATE_TO_HUMAN
    assert decision.retry_allowed is False
    assert decision.next_instruction_draft_required is False
    assert decision.next_instruction_draft is None
    assert decision.requires_human_decision is True
    assert "等待用户" in decision.user_visible_summary_cn
    assert decision.rule_codes == ["reason_human_waiting_user_decision"]


@pytest.mark.parametrize(
    "reason_code",
    [
        TaskBlockingReasonCode.DEPENDENCY_MISSING,
        TaskBlockingReasonCode.DEPENDENCY_INCOMPLETE,
    ],
)
def test_dependency_reason_codes_block_and_pause_without_human_decision(reason_code):
    decision = FailureRecoveryDecisionBuilder.build(
        failure_category=RunFailureCategory.EXECUTION_FAILED,
        reason_code=reason_code,
    )

    _assert_pure_contract(decision)
    assert decision.reason_code == reason_code
    assert decision.recoverable is False
    assert decision.retry_allowed is False
    assert decision.recommended_owner == RecoveryOwner.BLOCKED
    assert decision.next_action == RecoveryNextAction.PAUSE_AND_WAIT
    assert decision.next_instruction_kind == InstructionKind.PAUSE
    assert decision.next_instruction_draft_required is False
    assert decision.next_instruction_draft is None
    assert decision.requires_human_decision is False
    assert decision.human_decision_reason is None
    assert "依赖" in decision.user_visible_summary_cn
    assert decision.rule_codes == ["reason_dependency_blocked_pause"]


@pytest.mark.parametrize(
    "reason_code",
    [
        TaskBlockingReasonCode.TASK_PAUSED,
        TaskBlockingReasonCode.PAUSE_NOTE_PRESENT,
    ],
)
def test_pause_reason_codes_pause_and_wait(reason_code):
    decision = FailureRecoveryDecisionBuilder.build(
        failure_category=RunFailureCategory.VERIFICATION_FAILED,
        reason_code=reason_code,
    )

    _assert_pure_contract(decision)
    assert decision.reason_code == reason_code
    assert decision.recommended_owner == RecoveryOwner.BLOCKED
    assert decision.next_action == RecoveryNextAction.PAUSE_AND_WAIT
    assert decision.next_instruction_kind == InstructionKind.PAUSE
    assert decision.next_instruction_draft_required is False
    assert decision.next_instruction_draft is None
    assert decision.retry_allowed is False
    assert decision.requires_human_decision is False
    assert decision.rule_codes == ["reason_task_paused_wait"]


def test_task_not_pending_blocks_permanently_without_retry():
    decision = FailureRecoveryDecisionBuilder.build(
        failure_category=RunFailureCategory.EXECUTION_FAILED,
        reason_code=TaskBlockingReasonCode.TASK_NOT_PENDING,
    )

    _assert_pure_contract(decision)
    assert decision.recommended_owner == RecoveryOwner.BLOCKED
    assert decision.next_action == RecoveryNextAction.BLOCK_PERMANENTLY
    assert decision.retry_allowed is False
    assert decision.next_instruction_draft_required is False
    assert decision.next_instruction_draft is None
    assert decision.requires_human_decision is False
    assert "不允许继续执行" in decision.user_visible_summary_cn
    assert decision.rule_codes == ["reason_status_blocked_permanently"]


def test_consecutive_failure_threshold_escalates_to_user():
    decision = FailureRecoveryDecisionBuilder.build(
        failure_category=RunFailureCategory.VERIFICATION_FAILED,
        consecutive_failure_count=3,
    )

    _assert_pure_contract(decision)
    assert decision.recoverable is False
    assert decision.retry_allowed is False
    assert decision.recommended_owner == RecoveryOwner.USER
    assert decision.next_action == RecoveryNextAction.ESCALATE_TO_HUMAN
    assert decision.next_instruction_kind == InstructionKind.HUMAN_QUESTION
    assert decision.next_instruction_draft_required is False
    assert decision.next_instruction_draft is None
    assert decision.requires_human_decision is True
    assert decision.human_decision_reason == (
        "任务已连续失败 3 次，需要人工判断是否继续。"
    )
    assert "连续失败 3 次" in decision.user_visible_summary_cn
    assert decision.rule_codes == ["consecutive_failure_user_decision"]


def test_builder_rejects_invalid_consecutive_failure_count():
    with pytest.raises(ValueError, match="consecutive_failure_count"):
        FailureRecoveryDecisionBuilder.build(
            failure_category=RunFailureCategory.EXECUTION_FAILED,
            consecutive_failure_count=0,
        )


def test_decision_requires_human_reason_when_human_decision_is_true():
    with pytest.raises(ValidationError, match="human_decision_reason"):
        FailureRecoveryDecision(
            failure_category=RunFailureCategory.RETRY_LIMIT_EXCEEDED,
            recoverable=False,
            retry_allowed=False,
            recommended_owner=RecoveryOwner.USER,
            next_action=RecoveryNextAction.ESCALATE_TO_HUMAN,
            next_instruction_kind=InstructionKind.HUMAN_QUESTION,
            requires_human_decision=True,
            user_visible_summary_cn="需要用户判断是否继续。",
            rule_codes=["manual_invalid"],
        )


def test_decision_rejects_human_reason_when_human_decision_is_false():
    with pytest.raises(ValidationError, match="human_decision_reason must be empty"):
        FailureRecoveryDecision(
            failure_category=RunFailureCategory.EXECUTION_FAILED,
            recoverable=True,
            retry_allowed=True,
            recommended_owner=RecoveryOwner.CODEX,
            next_action=RecoveryNextAction.FIX_AND_RETRY,
            next_instruction_kind=InstructionKind.CODE_FIX,
            next_instruction_draft_required=True,
            next_instruction_draft="建议交给 Codex 修复。",
            human_decision_reason="不应出现。",
            requires_human_decision=False,
            user_visible_summary_cn="可修复。",
            rule_codes=["manual_invalid"],
        )


def test_decision_rejects_retry_allowed_when_not_recoverable():
    with pytest.raises(ValidationError, match="retry_allowed requires recoverable"):
        FailureRecoveryDecision(
            failure_category=RunFailureCategory.EXECUTION_FAILED,
            recoverable=False,
            retry_allowed=True,
            recommended_owner=RecoveryOwner.CODEX,
            next_action=RecoveryNextAction.RETRY,
            next_instruction_kind=InstructionKind.REPLAY,
            next_instruction_draft="建议重试。",
            requires_human_decision=False,
            user_visible_summary_cn="可重试。",
            rule_codes=["manual_invalid"],
        )


@pytest.mark.parametrize("flag_name", P5B_FORBIDDEN_TRUE_SAFETY_FLAGS)
def test_safety_flags_reject_all_runtime_side_effect_flags(flag_name):
    with pytest.raises(ValidationError, match="must not execute Git"):
        FailureRecoveryDecisionSafetyFlags(**{flag_name: True})


def test_decision_rejects_nested_illegal_safety_flags():
    with pytest.raises(ValidationError, match="must not execute Git"):
        FailureRecoveryDecision(
            failure_category=RunFailureCategory.EXECUTION_FAILED,
            recoverable=True,
            retry_allowed=True,
            recommended_owner=RecoveryOwner.CODEX,
            next_action=RecoveryNextAction.FIX_AND_RETRY,
            next_instruction_kind=InstructionKind.CODE_FIX,
            next_instruction_draft="建议交给 Codex 修复。",
            requires_human_decision=False,
            user_visible_summary_cn="可修复。",
            rule_codes=["manual_invalid"],
            safety_flags={"git_commit_triggered": True},
        )


def test_decision_normalizes_blank_optional_text_and_rule_codes():
    decision = FailureRecoveryDecision(
        failure_category=RunFailureCategory.EXECUTION_FAILED,
        recoverable=True,
        retry_allowed=True,
        recommended_owner=RecoveryOwner.CODEX,
            next_action=RecoveryNextAction.FIX_AND_RETRY,
            next_instruction_kind=InstructionKind.CODE_FIX,
            next_instruction_draft_required=True,
            next_instruction_draft=" 建议交给 Codex 修复。 ",
            human_decision_reason="   ",
            requires_human_decision=False,
            user_visible_summary_cn=" 可修复。 ",
            rule_codes=[" rule_a ", "", "rule_a", "rule_b"],
    )

    _assert_pure_contract(decision)
    assert decision.next_instruction_draft == "建议交给 Codex 修复。"
    assert decision.human_decision_reason is None
    assert decision.user_visible_summary_cn == "可修复。"
    assert decision.rule_codes == ["rule_a", "rule_b"]


def test_decision_rejects_required_draft_when_missing():
    with pytest.raises(ValidationError, match="next_instruction_draft is required"):
        FailureRecoveryDecision(
            failure_category=RunFailureCategory.EXECUTION_FAILED,
            recoverable=True,
            retry_allowed=True,
            recommended_owner=RecoveryOwner.CODEX,
            next_action=RecoveryNextAction.FIX_AND_RETRY,
            next_instruction_kind=InstructionKind.CODE_FIX,
            next_instruction_draft_required=True,
            next_instruction_draft=None,
            requires_human_decision=False,
            user_visible_summary_cn="可修复。",
            rule_codes=["manual_invalid"],
        )


def test_decision_rejects_unrequired_draft_when_present():
    with pytest.raises(ValidationError, match="next_instruction_draft must be empty"):
        FailureRecoveryDecision(
            failure_category=RunFailureCategory.EXECUTION_FAILED,
            recoverable=True,
            retry_allowed=True,
            recommended_owner=RecoveryOwner.CODEX,
            next_action=RecoveryNextAction.FIX_AND_RETRY,
            next_instruction_kind=InstructionKind.CODE_FIX,
            next_instruction_draft_required=False,
            next_instruction_draft="建议交给 Codex 修复。",
            requires_human_decision=False,
            user_visible_summary_cn="可修复。",
            rule_codes=["manual_invalid"],
        )


def test_decision_rejects_user_visible_summary_without_chinese():
    with pytest.raises(ValidationError, match="user_visible_summary_cn"):
        FailureRecoveryDecision(
            failure_category=RunFailureCategory.EXECUTION_FAILED,
            recoverable=True,
            retry_allowed=True,
            recommended_owner=RecoveryOwner.CODEX,
            next_action=RecoveryNextAction.FIX_AND_RETRY,
            next_instruction_kind=InstructionKind.CODE_FIX,
            next_instruction_draft_required=True,
            next_instruction_draft="建议交给 Codex 修复。",
            requires_human_decision=False,
            user_visible_summary_cn="fix and retry",
            rule_codes=["manual_invalid"],
        )


def test_decision_rejects_human_decision_reason_without_chinese():
    with pytest.raises(ValidationError, match="human_decision_reason"):
        FailureRecoveryDecision(
            failure_category=RunFailureCategory.RETRY_LIMIT_EXCEEDED,
            recoverable=False,
            retry_allowed=False,
            recommended_owner=RecoveryOwner.USER,
            next_action=RecoveryNextAction.ESCALATE_TO_HUMAN,
            next_instruction_kind=InstructionKind.HUMAN_QUESTION,
            next_instruction_draft_required=False,
            next_instruction_draft=None,
            requires_human_decision=True,
            human_decision_reason="need user decision",
            user_visible_summary_cn="需要用户判断是否继续。",
            rule_codes=["manual_invalid"],
        )


def test_decision_rejects_next_instruction_draft_without_chinese():
    with pytest.raises(ValidationError, match="next_instruction_draft"):
        FailureRecoveryDecision(
            failure_category=RunFailureCategory.EXECUTION_FAILED,
            recoverable=True,
            retry_allowed=True,
            recommended_owner=RecoveryOwner.CODEX,
            next_action=RecoveryNextAction.FIX_AND_RETRY,
            next_instruction_kind=InstructionKind.CODE_FIX,
            next_instruction_draft_required=True,
            next_instruction_draft="fix with targeted tests",
            requires_human_decision=False,
            user_visible_summary_cn="可修复。",
            rule_codes=["manual_invalid"],
        )


@pytest.mark.parametrize(
    ("failure_category", "overrides", "expected_error"),
    [
        (
            RunFailureCategory.EXECUTION_FAILED,
            {
                "recommended_owner": RecoveryOwner.DEEPSEEK,
                "next_instruction_kind": InstructionKind.CONFIG_FIX,
            },
            "execution failure_category invariant",
        ),
        (
            RunFailureCategory.VERIFICATION_FAILED,
            {"next_instruction_kind": InstructionKind.CODE_FIX},
            "verification failure_category invariant",
        ),
        (
            RunFailureCategory.VERIFICATION_CONFIGURATION_FAILED,
            {
                "retry_allowed": True,
                "recommended_owner": RecoveryOwner.CODEX,
                "next_instruction_kind": InstructionKind.CODE_FIX,
            },
            "verification-configuration failure_category invariant",
        ),
    ],
)
def test_decision_rejects_invalid_fixable_failure_category_contracts(
    failure_category,
    overrides,
    expected_error,
):
    values = {
        "failure_category": failure_category,
        "recoverable": True,
        "retry_allowed": True,
        "recommended_owner": RecoveryOwner.CODEX,
        "next_action": RecoveryNextAction.FIX_AND_RETRY,
        "next_instruction_kind": InstructionKind.CODE_FIX,
        "next_instruction_draft_required": True,
        "next_instruction_draft": "建议交给 Codex 修复。",
        "requires_human_decision": False,
        "user_visible_summary_cn": "可修复。",
        "rule_codes": ["manual_invalid"],
    }
    if failure_category == RunFailureCategory.VERIFICATION_FAILED:
        values["next_instruction_kind"] = InstructionKind.TEST_FIX
    if failure_category == RunFailureCategory.VERIFICATION_CONFIGURATION_FAILED:
        values.update(
            {
                "retry_allowed": False,
                "recommended_owner": RecoveryOwner.DEEPSEEK,
                "next_instruction_kind": InstructionKind.CONFIG_FIX,
                "next_instruction_draft": "建议交给 DeepSeek 修正配置。",
            }
        )
    values.update(overrides)

    with pytest.raises(ValidationError, match=expected_error):
        FailureRecoveryDecision(**values)


@pytest.mark.parametrize(
    "failure_category",
    [
        RunFailureCategory.DAILY_BUDGET_EXCEEDED,
        RunFailureCategory.SESSION_BUDGET_EXCEEDED,
        RunFailureCategory.RETRY_LIMIT_EXCEEDED,
    ],
)
def test_decision_rejects_budget_or_retry_limit_category_without_user_decision(
    failure_category,
):
    with pytest.raises(ValidationError, match="failure_category invariant"):
        FailureRecoveryDecision(
            failure_category=failure_category,
            recoverable=False,
            retry_allowed=False,
            recommended_owner=RecoveryOwner.BLOCKED,
            next_action=RecoveryNextAction.PAUSE_AND_WAIT,
            next_instruction_kind=InstructionKind.PAUSE,
            next_instruction_draft_required=False,
            next_instruction_draft=None,
            requires_human_decision=False,
            user_visible_summary_cn="暂不继续。",
            rule_codes=["manual_invalid"],
        )


def test_reason_code_override_allows_execution_failure_to_be_blocked():
    decision = FailureRecoveryDecision(
        failure_category=RunFailureCategory.EXECUTION_FAILED,
        reason_code=TaskBlockingReasonCode.DEPENDENCY_MISSING,
        recoverable=False,
        retry_allowed=False,
        recommended_owner=RecoveryOwner.BLOCKED,
        next_action=RecoveryNextAction.PAUSE_AND_WAIT,
        next_instruction_kind=InstructionKind.PAUSE,
        next_instruction_draft_required=False,
        next_instruction_draft=None,
        requires_human_decision=False,
        user_visible_summary_cn="存在依赖缺失，暂停等待。",
        rule_codes=["manual_dependency_override"],
    )

    _assert_pure_contract(decision)
    assert decision.reason_code == TaskBlockingReasonCode.DEPENDENCY_MISSING
    assert decision.recommended_owner == RecoveryOwner.BLOCKED


def test_builder_outputs_chinese_user_visible_fields_without_git_write_suggestions():
    decisions = [
        FailureRecoveryDecisionBuilder.build(
            failure_category=RunFailureCategory.EXECUTION_FAILED
        ),
        FailureRecoveryDecisionBuilder.build(
            failure_category=RunFailureCategory.VERIFICATION_CONFIGURATION_FAILED
        ),
        FailureRecoveryDecisionBuilder.build(
            failure_category=RunFailureCategory.RETRY_LIMIT_EXCEEDED
        ),
        FailureRecoveryDecisionBuilder.build(
            failure_category=RunFailureCategory.EXECUTION_FAILED,
            reason_code=TaskBlockingReasonCode.DEPENDENCY_MISSING,
        ),
    ]

    assert [decision.recommended_owner for decision in decisions] == [
        RecoveryOwner.CODEX,
        RecoveryOwner.DEEPSEEK,
        RecoveryOwner.USER,
        RecoveryOwner.BLOCKED,
    ]
    for decision in decisions:
        _assert_pure_contract(decision)
