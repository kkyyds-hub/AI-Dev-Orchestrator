"""Project Director P22-B 审查后自动编排统一结果契约。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


PostReviewAutomationStatus = Literal[
    "ready_for_future_transition",
    "waiting_for_human",
    "blocked",
]
PostReviewAutomationRoute = Literal[
    "automatic_continuation",
    "bounded_automatic_rework",
    "human_escalation",
    "none",
]


class ProjectDirectorPostReviewAutomationResult(DomainModel):
    """一次审查后证据链编排的统一、只读结果。"""

    orchestration_status: PostReviewAutomationStatus
    orchestration_id: UUID
    route: PostReviewAutomationRoute
    current_step: str = Field(min_length=1, max_length=80)

    source_review_message_id: UUID
    source_disposition_message_id: UUID | None = None
    source_consumption_preflight_message_id: UUID | None = None
    source_consumption_message_id: UUID | None = None
    source_handoff_message_id: UUID | None = None
    source_freshness_message_id: UUID | None = None
    source_human_escalation_package_message_id: UUID | None = None

    disposition_type: str | None = None
    handoff_kind: str | None = None
    transition_kind: str | None = None
    transition_authority: str | None = None

    evidence_fresh: bool = False
    gate_allows_protected_transition_guardrail: bool = False
    waiting_for_human: bool = False
    human_escalation_package_created: bool = False

    replay_check_completed: bool = False
    resumed_from_existing_evidence: bool = False

    blocked_reasons: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)

    continuation_started: bool = False
    rework_started: bool = False
    human_decision_recorded: bool = False
    task_created: bool = False
    run_created: bool = False
    worker_started: bool = False
    worktree_created: bool = False
    main_project_file_written: bool = False
    sandbox_file_written: bool = False
    manifest_file_written: bool = False
    diff_file_written: bool = False
    patch_applied: bool = False
    git_write_performed: bool = False
    gate_allows_write: bool = False
    product_runtime_git_write_allowed: bool = False

    ai_project_director_total_loop: Literal["Partial"] = "Partial"

    @field_validator(
        "continuation_started",
        "rework_started",
        "human_decision_recorded",
        "task_created",
        "run_created",
        "worker_started",
        "worktree_created",
        "main_project_file_written",
        "sandbox_file_written",
        "manifest_file_written",
        "diff_file_written",
        "patch_applied",
        "git_write_performed",
        "gate_allows_write",
        "product_runtime_git_write_allowed",
        mode="after",
    )
    @classmethod
    def reject_forbidden_side_effect_flags(cls, value: bool) -> bool:
        """拒绝任何执行、文件写入或 Git 写入授权。"""

        if value:
            raise ValueError("审查后编排不得执行转换或授权写入")
        return value

    @field_validator("created_at", mode="after")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        """统一持久化时间为带时区的 UTC 时间。"""

        normalized = ensure_utc_datetime(value)
        if normalized is None:
            raise ValueError("编排结果必须包含创建时间")
        return normalized

    @model_validator(mode="after")
    def validate_orchestration_state(
        self,
    ) -> "ProjectDirectorPostReviewAutomationResult":
        """校验终态、路由和精确证据绑定的一致性。"""

        if self.orchestration_status == "ready_for_future_transition":
            self._validate_automatic_success()
        elif self.orchestration_status == "waiting_for_human":
            self._validate_human_success()
        else:
            self._validate_blocked_state()
        return self

    def _validate_automatic_success(self) -> None:
        expected_by_disposition = {
            "AUTO_CONTINUE": (
                "automatic_continuation",
                "automatic_continuation",
                "CONTINUE_GUARDRAIL",
            ),
            "AUTO_REWORK": (
                "bounded_automatic_rework",
                "bounded_automatic_rework",
                "BOUNDED_REWORK_GUARDRAIL",
            ),
        }
        expected = expected_by_disposition.get(self.disposition_type)
        if expected is None or (
            self.route,
            self.handoff_kind,
            self.transition_kind,
        ) != expected:
            raise ValueError("自动路径的 disposition、route 与 transition 必须一致")
        required_ids = (
            self.source_disposition_message_id,
            self.source_consumption_preflight_message_id,
            self.source_consumption_message_id,
            self.source_handoff_message_id,
            self.source_freshness_message_id,
        )
        if any(value is None for value in required_ids):
            raise ValueError("自动路径成功必须包含完整 C1/C2/C3/E 证据绑定")
        if self.source_human_escalation_package_message_id is not None:
            raise ValueError("自动路径不得绑定人工升级包")
        if self.transition_authority != "AUTOMATED_DISPOSITION":
            raise ValueError("自动路径必须使用自动 disposition 权限来源")
        if not self.evidence_fresh or not self.gate_allows_protected_transition_guardrail:
            raise ValueError("自动路径成功必须通过 freshness guardrail")
        if self.waiting_for_human or self.human_escalation_package_created:
            raise ValueError("自动路径不得报告等待人工或创建人工升级包")
        if self.blocked_reasons:
            raise ValueError("自动路径成功结果不得包含 blocked 原因")

    def _validate_human_success(self) -> None:
        if self.route != "human_escalation" or self.disposition_type != "ESCALATE_TO_HUMAN":
            raise ValueError("人工路径必须来自 ESCALATE_TO_HUMAN disposition")
        if self.source_disposition_message_id is None:
            raise ValueError("人工路径必须绑定 disposition message")
        if self.source_human_escalation_package_message_id is None:
            raise ValueError("人工路径必须绑定 D1 package message")
        automatic_ids = (
            self.source_consumption_preflight_message_id,
            self.source_consumption_message_id,
            self.source_handoff_message_id,
            self.source_freshness_message_id,
        )
        if any(value is not None for value in automatic_ids):
            raise ValueError("人工路径不得绑定 C1/C2/C3/E message")
        if any(
            value is not None
            for value in (
                self.handoff_kind,
                self.transition_kind,
                self.transition_authority,
            )
        ):
            raise ValueError("人工等待终态不得伪造自动转换信息")
        if not self.waiting_for_human or not self.human_escalation_package_created:
            raise ValueError("人工路径必须报告等待人工且 D1 package 已创建")
        if self.evidence_fresh or self.gate_allows_protected_transition_guardrail:
            raise ValueError("人工等待终态不得通过 freshness guardrail")
        if self.blocked_reasons:
            raise ValueError("人工路径成功结果不得包含 blocked 原因")

    def _validate_blocked_state(self) -> None:
        if not self.blocked_reasons:
            raise ValueError("blocked 编排结果必须包含原因")
        if self.evidence_fresh or self.gate_allows_protected_transition_guardrail:
            raise ValueError("blocked 编排结果不得允许受保护转换")
        if self.waiting_for_human:
            raise ValueError("blocked 编排结果不得报告等待人工")
        if self.human_escalation_package_created:
            raise ValueError("blocked 编排结果不得报告新建人工升级包")


__all__ = (
    "PostReviewAutomationRoute",
    "PostReviewAutomationStatus",
    "ProjectDirectorPostReviewAutomationResult",
)
