"""P5 failure recovery decision pure domain model."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel
from app.domain.run import RunFailureCategory
from app.domain.task import TaskBlockingReasonCode


P5_FAILURE_RECOVERY_DECISION_AUDIT_EVENT_TYPE = "failure_recovery_decision"
P5_CONSECUTIVE_FAILURE_HUMAN_THRESHOLD = 3


class RecoveryOwner(StrEnum):
    """Recommended owner for the next recovery step."""

    CODEX = "codex"
    DEEPSEEK = "deepseek"
    USER = "user"
    BLOCKED = "blocked"


class RecoveryNextAction(StrEnum):
    """Normalized next action suggested by the recovery decision."""

    RETRY = "retry"
    FIX_AND_RETRY = "fix_and_retry"
    PAUSE_AND_WAIT = "pause_and_wait"
    REPLAN = "replan"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    BLOCK_PERMANENTLY = "block_permanently"
    ARCHIVE = "archive"


class InstructionKind(StrEnum):
    """Kind of the next instruction draft."""

    CODE_FIX = "code_fix"
    TEST_FIX = "test_fix"
    CONFIG_FIX = "config_fix"
    EVIDENCE_FIX = "evidence_fix"
    REPLAY = "replay"
    PAUSE = "pause"
    REPLAN = "replan"
    HUMAN_QUESTION = "human_question"


class FailureRecoveryDecision(DomainModel):
    """Structured P5 decision contract for a failed run.

    This model is intentionally pure domain logic. It does not persist data, call
    Worker/API code, write AgentMessage records, or trigger any git operation.
    """

    failure_category: RunFailureCategory
    reason_code: TaskBlockingReasonCode | None = None
    recoverable: bool
    retry_allowed: bool
    recommended_owner: RecoveryOwner
    next_action: RecoveryNextAction
    next_instruction_kind: InstructionKind
    next_instruction_draft: str | None = Field(default=None, max_length=2_000)
    requires_human_decision: bool
    human_decision_reason: str | None = Field(default=None, max_length=500)
    user_visible_summary_cn: str = Field(min_length=1, max_length=500)
    audit_event_type: str = Field(
        default=P5_FAILURE_RECOVERY_DECISION_AUDIT_EVENT_TYPE,
        min_length=1,
        max_length=100,
    )

    @field_validator(
        "next_instruction_draft",
        "human_decision_reason",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """Collapse blank optional text fields into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None

    @field_validator("user_visible_summary_cn", "audit_event_type")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim required text and reject blank values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("text fields cannot be blank.")
        return normalized_value

    @model_validator(mode="after")
    def validate_human_decision_reason(self) -> "FailureRecoveryDecision":
        """Human decisions must explain why the user is required."""

        if self.requires_human_decision and self.human_decision_reason is None:
            raise ValueError(
                "human_decision_reason is required when "
                "requires_human_decision is true."
            )

        return self


class FailureRecoveryDecisionBuilder:
    """Rule-based P5-B builder for pure failure recovery decisions."""

    @classmethod
    def build(
        cls,
        *,
        failure_category: RunFailureCategory,
        reason_code: TaskBlockingReasonCode | None = None,
        consecutive_failure_count: int = 1,
    ) -> FailureRecoveryDecision:
        """Build a recovery decision from existing failure signals."""

        if consecutive_failure_count < 1:
            raise ValueError("consecutive_failure_count must be greater than zero.")

        if consecutive_failure_count >= P5_CONSECUTIVE_FAILURE_HUMAN_THRESHOLD:
            return cls._continuous_failure_decision(
                failure_category=failure_category,
                reason_code=reason_code,
                consecutive_failure_count=consecutive_failure_count,
            )

        if reason_code in _BUDGET_REASON_CODES:
            return cls._budget_decision(failure_category, reason_code)

        if reason_code in _HUMAN_REASON_CODES:
            return cls._human_decision(failure_category, reason_code)

        if reason_code in _DEPENDENCY_REASON_CODES:
            return cls._dependency_blocked_decision(failure_category, reason_code)

        if reason_code in _PAUSE_REASON_CODES:
            return cls._paused_decision(failure_category, reason_code)

        if reason_code in _STATUS_BLOCKED_REASON_CODES:
            return cls._status_blocked_decision(failure_category, reason_code)

        if failure_category == RunFailureCategory.EXECUTION_FAILED:
            return FailureRecoveryDecision(
                failure_category=failure_category,
                reason_code=reason_code,
                recoverable=True,
                retry_allowed=True,
                recommended_owner=RecoveryOwner.CODEX,
                next_action=RecoveryNextAction.FIX_AND_RETRY,
                next_instruction_kind=InstructionKind.CODE_FIX,
                next_instruction_draft=(
                    "建议交给 Codex：请根据失败日志定位执行层或代码实现问题，"
                    "修复后仅运行必要的 targeted tests，并回报失败原因与修复证据。"
                ),
                requires_human_decision=False,
                user_visible_summary_cn=(
                    "执行失败可先由 Codex 修复并重试，当前不需要用户决策。"
                ),
            )

        if failure_category == RunFailureCategory.VERIFICATION_FAILED:
            return FailureRecoveryDecision(
                failure_category=failure_category,
                reason_code=reason_code,
                recoverable=True,
                retry_allowed=True,
                recommended_owner=RecoveryOwner.CODEX,
                next_action=RecoveryNextAction.FIX_AND_RETRY,
                next_instruction_kind=InstructionKind.TEST_FIX,
                next_instruction_draft=(
                    "建议交给 Codex：请根据验证失败证据修复实现或测试期望，"
                    "只运行对应验证命令，并保留质量门失败到修复通过的证据。"
                ),
                requires_human_decision=False,
                user_visible_summary_cn=(
                    "验证失败可先由 Codex 修复并重试，当前不需要用户决策。"
                ),
            )

        if failure_category == RunFailureCategory.VERIFICATION_CONFIGURATION_FAILED:
            return FailureRecoveryDecision(
                failure_category=failure_category,
                reason_code=reason_code,
                recoverable=True,
                retry_allowed=False,
                recommended_owner=RecoveryOwner.DEEPSEEK,
                next_action=RecoveryNextAction.FIX_AND_RETRY,
                next_instruction_kind=InstructionKind.CONFIG_FIX,
                next_instruction_draft=(
                    "建议交给 DeepSeek：请审查验证配置、证据口径或 ledger/Gate "
                    "规则是否不一致，先修正配置与证据说明，再允许重试。"
                ),
                requires_human_decision=False,
                user_visible_summary_cn=(
                    "验证配置失败应先由 DeepSeek 修正配置或证据口径，暂不直接重试。"
                ),
            )

        if failure_category in _BUDGET_FAILURE_CATEGORIES:
            return cls._budget_decision(failure_category, reason_code)

        if failure_category == RunFailureCategory.RETRY_LIMIT_EXCEEDED:
            return FailureRecoveryDecision(
                failure_category=failure_category,
                reason_code=reason_code,
                recoverable=False,
                retry_allowed=False,
                recommended_owner=RecoveryOwner.USER,
                next_action=RecoveryNextAction.ESCALATE_TO_HUMAN,
                next_instruction_kind=InstructionKind.HUMAN_QUESTION,
                next_instruction_draft=None,
                requires_human_decision=True,
                human_decision_reason="任务已达到重试上限，需要用户判断是否继续投入。",
                user_visible_summary_cn=(
                    "重试次数已达到上限，需要用户决定是否继续、改计划或停止。"
                ),
            )

        return FailureRecoveryDecision(
            failure_category=failure_category,
            reason_code=reason_code,
            recoverable=False,
            retry_allowed=False,
            recommended_owner=RecoveryOwner.BLOCKED,
            next_action=RecoveryNextAction.ARCHIVE,
            next_instruction_kind=InstructionKind.PAUSE,
            next_instruction_draft=None,
            requires_human_decision=False,
            user_visible_summary_cn="失败类型暂不可自动恢复，建议归档为已知不可修复状态。",
        )

    @staticmethod
    def _budget_decision(
        failure_category: RunFailureCategory,
        reason_code: TaskBlockingReasonCode | None,
    ) -> FailureRecoveryDecision:
        return FailureRecoveryDecision(
            failure_category=failure_category,
            reason_code=reason_code,
            recoverable=False,
            retry_allowed=False,
            recommended_owner=RecoveryOwner.USER,
            next_action=RecoveryNextAction.ESCALATE_TO_HUMAN,
            next_instruction_kind=InstructionKind.HUMAN_QUESTION,
            next_instruction_draft=None,
            requires_human_decision=True,
            human_decision_reason="涉及预算限制，需要用户确认是否增加预算或调整策略。",
            user_visible_summary_cn="预算限制已阻止继续执行，需要用户做预算或策略决策。",
        )

    @staticmethod
    def _human_decision(
        failure_category: RunFailureCategory,
        reason_code: TaskBlockingReasonCode | None,
    ) -> FailureRecoveryDecision:
        return FailureRecoveryDecision(
            failure_category=failure_category,
            reason_code=reason_code,
            recoverable=False,
            retry_allowed=False,
            recommended_owner=RecoveryOwner.USER,
            next_action=RecoveryNextAction.ESCALATE_TO_HUMAN,
            next_instruction_kind=InstructionKind.HUMAN_QUESTION,
            next_instruction_draft=None,
            requires_human_decision=True,
            human_decision_reason="当前任务正在等待用户或人工审核结果。",
            user_visible_summary_cn="任务正在等待用户或人工审核继续推进，暂不自动重试。",
        )

    @staticmethod
    def _dependency_blocked_decision(
        failure_category: RunFailureCategory,
        reason_code: TaskBlockingReasonCode | None,
    ) -> FailureRecoveryDecision:
        return FailureRecoveryDecision(
            failure_category=failure_category,
            reason_code=reason_code,
            recoverable=False,
            retry_allowed=False,
            recommended_owner=RecoveryOwner.BLOCKED,
            next_action=RecoveryNextAction.PAUSE_AND_WAIT,
            next_instruction_kind=InstructionKind.PAUSE,
            next_instruction_draft=None,
            requires_human_decision=False,
            user_visible_summary_cn="存在未满足依赖，任务应暂停等待依赖完成后再恢复。",
        )

    @staticmethod
    def _paused_decision(
        failure_category: RunFailureCategory,
        reason_code: TaskBlockingReasonCode | None,
    ) -> FailureRecoveryDecision:
        return FailureRecoveryDecision(
            failure_category=failure_category,
            reason_code=reason_code,
            recoverable=False,
            retry_allowed=False,
            recommended_owner=RecoveryOwner.BLOCKED,
            next_action=RecoveryNextAction.PAUSE_AND_WAIT,
            next_instruction_kind=InstructionKind.PAUSE,
            next_instruction_draft=None,
            requires_human_decision=False,
            user_visible_summary_cn="任务已暂停，需等待暂停条件解除后再继续。",
        )

    @staticmethod
    def _status_blocked_decision(
        failure_category: RunFailureCategory,
        reason_code: TaskBlockingReasonCode | None,
    ) -> FailureRecoveryDecision:
        return FailureRecoveryDecision(
            failure_category=failure_category,
            reason_code=reason_code,
            recoverable=False,
            retry_allowed=False,
            recommended_owner=RecoveryOwner.BLOCKED,
            next_action=RecoveryNextAction.BLOCK_PERMANENTLY,
            next_instruction_kind=InstructionKind.PAUSE,
            next_instruction_draft=None,
            requires_human_decision=False,
            user_visible_summary_cn="任务当前状态不允许继续执行，应阻塞而不是重试。",
        )

    @staticmethod
    def _continuous_failure_decision(
        *,
        failure_category: RunFailureCategory,
        reason_code: TaskBlockingReasonCode | None,
        consecutive_failure_count: int,
    ) -> FailureRecoveryDecision:
        return FailureRecoveryDecision(
            failure_category=failure_category,
            reason_code=reason_code,
            recoverable=False,
            retry_allowed=False,
            recommended_owner=RecoveryOwner.USER,
            next_action=RecoveryNextAction.ESCALATE_TO_HUMAN,
            next_instruction_kind=InstructionKind.HUMAN_QUESTION,
            next_instruction_draft=None,
            requires_human_decision=True,
            human_decision_reason=(
                f"任务已连续失败 {consecutive_failure_count} 次，需要人工判断是否继续。"
            ),
            user_visible_summary_cn=(
                f"任务已连续失败 {consecutive_failure_count} 次，需要用户决定下一步。"
            ),
        )


_BUDGET_FAILURE_CATEGORIES = {
    RunFailureCategory.DAILY_BUDGET_EXCEEDED,
    RunFailureCategory.SESSION_BUDGET_EXCEEDED,
}

_BUDGET_REASON_CODES = {
    TaskBlockingReasonCode.BUDGET_GUARD_BLOCKED,
}

_HUMAN_REASON_CODES = {
    TaskBlockingReasonCode.TASK_WAITING_HUMAN,
    TaskBlockingReasonCode.HUMAN_REVIEW_REQUESTED,
    TaskBlockingReasonCode.HUMAN_REVIEW_IN_PROGRESS,
}

_DEPENDENCY_REASON_CODES = {
    TaskBlockingReasonCode.DEPENDENCY_MISSING,
    TaskBlockingReasonCode.DEPENDENCY_INCOMPLETE,
}

_PAUSE_REASON_CODES = {
    TaskBlockingReasonCode.TASK_PAUSED,
    TaskBlockingReasonCode.PAUSE_NOTE_PRESENT,
}

_STATUS_BLOCKED_REASON_CODES = {
    TaskBlockingReasonCode.TASK_NOT_PENDING,
}
