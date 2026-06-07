"""P5 failure recovery decision pure domain model.

This module is deliberately side-effect free. It does not call TaskWorker,
expose API schemas, write AgentMessage rows, mutate database tables, dispatch
retries, create tasks, or perform git add/commit/push/PR/merge/delete branch/
reset/checkout/switch/stash/rebase/tag operations. It only normalizes existing
failure signals into a structured recovery decision contract.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel
from app.domain.run import RunFailureCategory
from app.domain.task import TaskBlockingReasonCode


P5_FAILURE_RECOVERY_DECISION_SOURCE = "failure_recovery_decision"
P5_FAILURE_RECOVERY_DECISION_VERSION = "p5_b.r1"
P5_FAILURE_RECOVERY_DECISION_AUDIT_EVENT_TYPE = "failure_recovery_decision"
P5_CONSECUTIVE_FAILURE_HUMAN_THRESHOLD = 3

P5B_FORBIDDEN_TRUE_SAFETY_FLAGS: tuple[str, ...] = (
    "runs_git",
    "runs_write_git",
    "git_add_triggered",
    "git_commit_triggered",
    "git_push_triggered",
    "pr_opened",
    "merge_triggered",
    "branch_deleted",
    "git_reset_triggered",
    "git_checkout_triggered",
    "git_switch_triggered",
    "git_stash_triggered",
    "git_rebase_triggered",
    "git_tag_triggered",
    "ci_triggered",
    "execution_enabled",
    "worker_dispatch_triggered",
    "api_response_exposed",
    "agent_message_written",
    "task_created",
    "retry_triggered",
)


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


class FailureRecoveryDecisionSafetyFlags(DomainModel):
    """P5-B R1 safety flags; every flag must remain false in pure domain code."""

    runs_git: bool = False
    runs_write_git: bool = False
    git_add_triggered: bool = False
    git_commit_triggered: bool = False
    git_push_triggered: bool = False
    pr_opened: bool = False
    merge_triggered: bool = False
    branch_deleted: bool = False
    git_reset_triggered: bool = False
    git_checkout_triggered: bool = False
    git_switch_triggered: bool = False
    git_stash_triggered: bool = False
    git_rebase_triggered: bool = False
    git_tag_triggered: bool = False
    ci_triggered: bool = False
    execution_enabled: bool = False
    worker_dispatch_triggered: bool = False
    api_response_exposed: bool = False
    agent_message_written: bool = False
    task_created: bool = False
    retry_triggered: bool = False

    @model_validator(mode="after")
    def validate_p5b_no_runtime_side_effects(
        self,
    ) -> "FailureRecoveryDecisionSafetyFlags":
        enabled_forbidden_flags = [
            flag_name
            for flag_name in P5B_FORBIDDEN_TRUE_SAFETY_FLAGS
            if bool(getattr(self, flag_name))
        ]
        if enabled_forbidden_flags:
            raise ValueError(
                "P5-B failure recovery decision must not execute Git, expose API, "
                "write AgentMessage, dispatch workers, create tasks, or trigger "
                "retries: "
                + ", ".join(enabled_forbidden_flags)
            )
        return self


class FailureRecoveryDecision(DomainModel):
    """Structured P5 decision contract for a failed run.

    This model is intentionally pure domain logic. It does not persist data, call
    Worker/API code, write AgentMessage records, dispatch retries, create tasks,
    or trigger any git operation.
    """

    source: str = Field(
        default=P5_FAILURE_RECOVERY_DECISION_SOURCE,
        min_length=1,
        max_length=100,
    )
    version: str = Field(
        default=P5_FAILURE_RECOVERY_DECISION_VERSION,
        min_length=1,
        max_length=40,
    )
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
    rule_codes: list[str] = Field(default_factory=list, max_length=20)
    safety_flags: FailureRecoveryDecisionSafetyFlags = Field(
        default_factory=FailureRecoveryDecisionSafetyFlags
    )

    @field_validator(
        "source",
        "version",
        "next_instruction_draft",
        "human_decision_reason",
        "user_visible_summary_cn",
        "audit_event_type",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        """Trim text fields and collapse blank optional text into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None

    @field_validator("rule_codes")
    @classmethod
    def normalize_rule_codes(cls, values: list[str]) -> list[str]:
        """Trim and deduplicate rule codes while preserving order."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()
        for value in values:
            normalized_value = value.strip()
            if not normalized_value or normalized_value in seen_items:
                continue
            normalized_items.append(normalized_value)
            seen_items.add(normalized_value)
        return normalized_items

    @model_validator(mode="after")
    def validate_contract(self) -> "FailureRecoveryDecision":
        """Validate P5-B R1 decision contract invariants."""

        if self.source != P5_FAILURE_RECOVERY_DECISION_SOURCE:
            raise ValueError(
                f"source must be {P5_FAILURE_RECOVERY_DECISION_SOURCE!r}"
            )
        if self.version != P5_FAILURE_RECOVERY_DECISION_VERSION:
            raise ValueError(
                f"version must be {P5_FAILURE_RECOVERY_DECISION_VERSION!r}"
            )
        if self.audit_event_type != P5_FAILURE_RECOVERY_DECISION_AUDIT_EVENT_TYPE:
            raise ValueError(
                "audit_event_type must be "
                f"{P5_FAILURE_RECOVERY_DECISION_AUDIT_EVENT_TYPE!r}"
            )
        if self.retry_allowed and not self.recoverable:
            raise ValueError("retry_allowed requires recoverable")
        if self.recommended_owner in {RecoveryOwner.USER, RecoveryOwner.BLOCKED}:
            if self.retry_allowed:
                raise ValueError("user or blocked decisions must not allow retry")
            if self.next_instruction_draft is not None:
                raise ValueError(
                    "user or blocked decisions must not include executable drafts"
                )
        if self.recommended_owner in {RecoveryOwner.CODEX, RecoveryOwner.DEEPSEEK}:
            if self.requires_human_decision:
                raise ValueError(
                    "codex/deepseek decisions must not require human decision"
                )
            if self.next_instruction_draft is None:
                raise ValueError(
                    "codex/deepseek decisions must include next_instruction_draft"
                )
        if self.requires_human_decision:
            if self.recommended_owner != RecoveryOwner.USER:
                raise ValueError("human decisions must be recommended to user")
            if self.next_action != RecoveryNextAction.ESCALATE_TO_HUMAN:
                raise ValueError("human decisions must escalate to human")
            if self.next_instruction_kind != InstructionKind.HUMAN_QUESTION:
                raise ValueError("human decisions must use human_question instruction")
            if self.human_decision_reason is None:
                raise ValueError(
                    "human_decision_reason is required when "
                    "requires_human_decision is true."
                )
        elif self.human_decision_reason is not None:
            raise ValueError(
                "human_decision_reason must be empty when "
                "requires_human_decision is false."
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
            return cls._budget_decision(
                failure_category,
                reason_code,
                rule_codes=["reason_budget_guard_blocked"],
            )

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
                rule_codes=["failure_execution_codex_fix_and_retry"],
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
                rule_codes=["failure_verification_codex_test_fix"],
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
                rule_codes=["failure_verification_config_deepseek_config_fix"],
            )

        if failure_category in _BUDGET_FAILURE_CATEGORIES:
            return cls._budget_decision(
                failure_category,
                reason_code,
                rule_codes=["failure_budget_user_decision"],
            )

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
                rule_codes=["failure_retry_limit_user_decision"],
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
            rule_codes=["failure_unknown_archive"],
        )

    @staticmethod
    def _budget_decision(
        failure_category: RunFailureCategory,
        reason_code: TaskBlockingReasonCode | None,
        *,
        rule_codes: list[str],
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
            rule_codes=rule_codes,
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
            rule_codes=["reason_human_waiting_user_decision"],
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
            rule_codes=["reason_dependency_blocked_pause"],
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
            rule_codes=["reason_task_paused_wait"],
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
            rule_codes=["reason_status_blocked_permanently"],
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
            rule_codes=["consecutive_failure_user_decision"],
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
