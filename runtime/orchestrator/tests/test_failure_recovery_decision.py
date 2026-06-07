"""Targeted tests for P5-B failure recovery decision pure domain model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.failure_recovery_decision import (
    P5_FAILURE_RECOVERY_DECISION_AUDIT_EVENT_TYPE,
    FailureRecoveryDecision,
    FailureRecoveryDecisionBuilder,
    InstructionKind,
    RecoveryNextAction,
    RecoveryOwner,
)
from app.domain.run import RunFailureCategory
from app.domain.task import TaskBlockingReasonCode


def test_execution_failure_routes_to_codex_fix_and_retry_without_human_decision():
    decision = FailureRecoveryDecisionBuilder.build(
        failure_category=RunFailureCategory.EXECUTION_FAILED,
    )

    assert decision.failure_category == RunFailureCategory.EXECUTION_FAILED
    assert decision.reason_code is None
    assert decision.recoverable is True
    assert decision.retry_allowed is True
    assert decision.recommended_owner == RecoveryOwner.CODEX
    assert decision.next_action == RecoveryNextAction.FIX_AND_RETRY
    assert decision.next_instruction_kind == InstructionKind.CODE_FIX
    assert decision.next_instruction_draft is not None
    assert "Codex" in decision.next_instruction_draft
    assert decision.requires_human_decision is False
    assert decision.human_decision_reason is None
    assert "Codex" in decision.user_visible_summary_cn
    assert decision.audit_event_type == P5_FAILURE_RECOVERY_DECISION_AUDIT_EVENT_TYPE


def test_verification_failure_routes_to_codex_test_fix():
    decision = FailureRecoveryDecisionBuilder.build(
        failure_category=RunFailureCategory.VERIFICATION_FAILED,
    )

    assert decision.recoverable is True
    assert decision.retry_allowed is True
    assert decision.recommended_owner == RecoveryOwner.CODEX
    assert decision.next_action == RecoveryNextAction.FIX_AND_RETRY
    assert decision.next_instruction_kind == InstructionKind.TEST_FIX
    assert decision.requires_human_decision is False
    assert "验证失败" in decision.user_visible_summary_cn


def test_verification_configuration_failure_routes_to_deepseek_config_fix():
    decision = FailureRecoveryDecisionBuilder.build(
        failure_category=RunFailureCategory.VERIFICATION_CONFIGURATION_FAILED,
    )

    assert decision.recoverable is True
    assert decision.retry_allowed is False
    assert decision.recommended_owner == RecoveryOwner.DEEPSEEK
    assert decision.next_action == RecoveryNextAction.FIX_AND_RETRY
    assert decision.next_instruction_kind == InstructionKind.CONFIG_FIX
    assert decision.next_instruction_draft is not None
    assert "DeepSeek" in decision.next_instruction_draft
    assert decision.requires_human_decision is False
    assert "暂不直接重试" in decision.user_visible_summary_cn


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

    assert decision.recoverable is False
    assert decision.retry_allowed is False
    assert decision.recommended_owner == RecoveryOwner.USER
    assert decision.next_action == RecoveryNextAction.ESCALATE_TO_HUMAN
    assert decision.next_instruction_kind == InstructionKind.HUMAN_QUESTION
    assert decision.next_instruction_draft is None
    assert decision.requires_human_decision is True
    assert decision.human_decision_reason == (
        "涉及预算限制，需要用户确认是否增加预算或调整策略。"
    )
    assert "预算" in decision.user_visible_summary_cn


def test_budget_reason_code_overrides_execution_failure_to_user_decision():
    decision = FailureRecoveryDecisionBuilder.build(
        failure_category=RunFailureCategory.EXECUTION_FAILED,
        reason_code=TaskBlockingReasonCode.BUDGET_GUARD_BLOCKED,
    )

    assert decision.failure_category == RunFailureCategory.EXECUTION_FAILED
    assert decision.reason_code == TaskBlockingReasonCode.BUDGET_GUARD_BLOCKED
    assert decision.recommended_owner == RecoveryOwner.USER
    assert decision.retry_allowed is False
    assert decision.requires_human_decision is True
    assert "预算" in decision.human_decision_reason


def test_retry_limit_exceeded_requires_user_decision():
    decision = FailureRecoveryDecisionBuilder.build(
        failure_category=RunFailureCategory.RETRY_LIMIT_EXCEEDED,
    )

    assert decision.recoverable is False
    assert decision.retry_allowed is False
    assert decision.recommended_owner == RecoveryOwner.USER
    assert decision.next_action == RecoveryNextAction.ESCALATE_TO_HUMAN
    assert decision.next_instruction_kind == InstructionKind.HUMAN_QUESTION
    assert decision.requires_human_decision is True
    assert "重试上限" in decision.human_decision_reason


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

    assert decision.reason_code == reason_code
    assert decision.recommended_owner == RecoveryOwner.USER
    assert decision.next_action == RecoveryNextAction.ESCALATE_TO_HUMAN
    assert decision.retry_allowed is False
    assert decision.requires_human_decision is True
    assert "等待用户" in decision.user_visible_summary_cn


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

    assert decision.reason_code == reason_code
    assert decision.recoverable is False
    assert decision.retry_allowed is False
    assert decision.recommended_owner == RecoveryOwner.BLOCKED
    assert decision.next_action == RecoveryNextAction.PAUSE_AND_WAIT
    assert decision.next_instruction_kind == InstructionKind.PAUSE
    assert decision.requires_human_decision is False
    assert decision.human_decision_reason is None
    assert "依赖" in decision.user_visible_summary_cn


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

    assert decision.reason_code == reason_code
    assert decision.recommended_owner == RecoveryOwner.BLOCKED
    assert decision.next_action == RecoveryNextAction.PAUSE_AND_WAIT
    assert decision.next_instruction_kind == InstructionKind.PAUSE
    assert decision.retry_allowed is False
    assert decision.requires_human_decision is False


def test_task_not_pending_blocks_permanently_without_retry():
    decision = FailureRecoveryDecisionBuilder.build(
        failure_category=RunFailureCategory.EXECUTION_FAILED,
        reason_code=TaskBlockingReasonCode.TASK_NOT_PENDING,
    )

    assert decision.recommended_owner == RecoveryOwner.BLOCKED
    assert decision.next_action == RecoveryNextAction.BLOCK_PERMANENTLY
    assert decision.retry_allowed is False
    assert decision.requires_human_decision is False
    assert "不允许继续执行" in decision.user_visible_summary_cn


def test_consecutive_failure_threshold_escalates_to_user():
    decision = FailureRecoveryDecisionBuilder.build(
        failure_category=RunFailureCategory.VERIFICATION_FAILED,
        consecutive_failure_count=3,
    )

    assert decision.recoverable is False
    assert decision.retry_allowed is False
    assert decision.recommended_owner == RecoveryOwner.USER
    assert decision.next_action == RecoveryNextAction.ESCALATE_TO_HUMAN
    assert decision.next_instruction_kind == InstructionKind.HUMAN_QUESTION
    assert decision.requires_human_decision is True
    assert decision.human_decision_reason == (
        "任务已连续失败 3 次，需要人工判断是否继续。"
    )
    assert "连续失败 3 次" in decision.user_visible_summary_cn


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
        )


def test_decision_normalizes_blank_optional_text_to_none():
    decision = FailureRecoveryDecision(
        failure_category=RunFailureCategory.EXECUTION_FAILED,
        recoverable=True,
        retry_allowed=True,
        recommended_owner=RecoveryOwner.CODEX,
        next_action=RecoveryNextAction.FIX_AND_RETRY,
        next_instruction_kind=InstructionKind.CODE_FIX,
        next_instruction_draft="   ",
        human_decision_reason="   ",
        requires_human_decision=False,
        user_visible_summary_cn=" 可修复。 ",
    )

    assert decision.next_instruction_draft is None
    assert decision.human_decision_reason is None
    assert decision.user_visible_summary_cn == "可修复。"
