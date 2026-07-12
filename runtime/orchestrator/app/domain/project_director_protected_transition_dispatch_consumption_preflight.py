"""Project Director P23-C 受保护转换调度消费前置检查契约。"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


ProtectedTransitionDispatchConsumptionPreflightStatus = Literal[
    "ready",
    "blocked",
]
ProtectedTransitionTaskPreparationStrategy = Literal[
    "claim_pending",
    "retry_to_pending_then_claim",
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProjectDirectorProtectedTransitionDispatchConsumptionPreflightResult(
    DomainModel
):
    """只做消费前置检查、不消费调度意图也不执行任务。"""

    preflight_status: ProtectedTransitionDispatchConsumptionPreflightStatus
    preflight_id: UUID | None = None
    preflight_fingerprint: str = Field(default="", max_length=64)

    session_id: UUID
    project_id: UUID | None = None
    source_task_id: UUID
    target_task_id: UUID | None = None

    source_intent_message_id: UUID
    source_dispatch_intent_id: UUID | None = None
    source_dispatch_intent_fingerprint: str = Field(default="", max_length=64)
    source_p22_summary_message_id: UUID | None = None
    source_review_message_id: UUID | None = None
    source_freshness_message_id: UUID | None = None

    disposition_type: Literal["AUTO_CONTINUE", "AUTO_REWORK"] | None = None
    dispatch_kind: Literal["auto_continue", "auto_rework"] | None = None
    target_task_strategy: Literal[
        "source_task_continue",
        "source_task_rework",
    ] | None = None

    review_result_fingerprint: str = Field(default="", max_length=64)
    review_semantic_fingerprint: str = Field(default="", max_length=64)
    persisted_freshness_evidence_fingerprint: str = Field(default="", max_length=64)
    current_freshness_fingerprint: str = Field(default="", max_length=64)

    reviewed_diff_sha256: str = Field(default="", max_length=64)
    current_diff_sha256: str = Field(default="", max_length=64)
    reviewed_scope_paths: list[str] = Field(default_factory=list)
    current_scope_paths: list[str] = Field(default_factory=list)
    workspace_path: str = Field(default="", max_length=2_000)
    workspace_path_within_root: bool = False

    task_status_before: str | None = None
    task_human_status_before: str | None = None
    task_readiness_ready: bool = False
    task_readiness_blocking_reasons: list[str] = Field(default_factory=list)
    task_preparation_strategy: ProtectedTransitionTaskPreparationStrategy | None = None
    planned_task_status_after_preparation: str | None = None

    budget_guard_allowed: bool = False
    budget_pressure_level: str | None = None
    budget_strategy_action: str | None = None
    budget_strategy_code: str | None = None
    budget_policy_source: str | None = None
    retry_limit_reached: bool = False

    rework_attempt_index: int = Field(default=0, ge=0)
    rework_attempt_limit: int = Field(default=3, ge=1)
    non_convergence_checked: bool = False
    non_convergence_detected: bool = False

    replay_check_completed: bool = False
    resumed_from_existing_preflight: bool = False
    validated_at: datetime = Field(default_factory=utc_now)
    created_at: datetime = Field(default_factory=utc_now)
    blocked_reasons: list[str] = Field(default_factory=list)

    dispatch_intent_consumed: bool = False
    task_status_mutated: bool = False
    task_created: bool = False
    task_claimed: bool = False
    run_created: bool = False
    worker_started: bool = False
    runtime_started: bool = False
    continuation_started: bool = False
    rework_started: bool = False
    worktree_created: bool = False
    main_project_file_written: bool = False
    sandbox_file_written: bool = False
    manifest_file_written: bool = False
    diff_file_written: bool = False
    file_written: bool = False
    patch_applied: bool = False
    git_write_performed: bool = False
    gate_allows_write: bool = False
    product_runtime_git_write_allowed: bool = False
    ai_project_director_total_loop: Literal["Partial"] = "Partial"

    @field_validator("validated_at", "created_at", mode="after")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        """统一前置检查时间为带时区的 UTC 时间。"""

        return ensure_utc_datetime(value)

    @field_validator(
        "dispatch_intent_consumed",
        "task_status_mutated",
        "task_created",
        "task_claimed",
        "run_created",
        "worker_started",
        "runtime_started",
        "continuation_started",
        "rework_started",
        "worktree_created",
        "main_project_file_written",
        "sandbox_file_written",
        "manifest_file_written",
        "diff_file_written",
        "file_written",
        "patch_applied",
        "git_write_performed",
        "gate_allows_write",
        "product_runtime_git_write_allowed",
        mode="after",
    )
    @classmethod
    def reject_forbidden_side_effect_flags(cls, value: bool) -> bool:
        """P23-C 不得消费意图、执行任务或产生写入副作用。"""

        if value:
            raise ValueError("调度消费前置检查不得产生执行或写入副作用")
        return value

    @model_validator(mode="after")
    def validate_preflight_state(
        self,
    ) -> "ProjectDirectorProtectedTransitionDispatchConsumptionPreflightResult":
        """校验 ready 与 blocked 的严格状态边界。"""

        if self.preflight_status == "blocked":
            if self.preflight_id is not None:
                raise ValueError("blocked 前置检查不得创建记录")
            if not self.blocked_reasons:
                raise ValueError("blocked 前置检查必须包含原因")
            return self

        required_ids = (
            self.preflight_id,
            self.project_id,
            self.target_task_id,
            self.source_dispatch_intent_id,
            self.source_p22_summary_message_id,
            self.source_review_message_id,
            self.source_freshness_message_id,
        )
        if any(value is None for value in required_ids):
            raise ValueError("ready 前置检查必须包含完整证据身份")
        if any(
            value is None
            for value in (
                self.disposition_type,
                self.dispatch_kind,
                self.target_task_strategy,
            )
        ):
            raise ValueError("ready 前置检查必须包含完整调度语义")
        fingerprints = (
            self.preflight_fingerprint,
            self.source_dispatch_intent_fingerprint,
            self.review_result_fingerprint,
            self.review_semantic_fingerprint,
            self.persisted_freshness_evidence_fingerprint,
            self.current_freshness_fingerprint,
            self.reviewed_diff_sha256,
            self.current_diff_sha256,
        )
        if not all(_LOWER_HEX_SHA256.match(value) for value in fingerprints):
            raise ValueError("ready 前置检查必须包含有效 SHA-256 指纹")
        if self.target_task_id != self.source_task_id:
            raise ValueError("调度消费目标必须是来源任务")
        if self.source_dispatch_intent_id != self.source_intent_message_id:
            raise ValueError("调度意图记录必须绑定 exact source message")
        expected_dispatch = {
            "AUTO_CONTINUE": ("auto_continue", "source_task_continue"),
            "AUTO_REWORK": ("auto_rework", "source_task_rework"),
        }[self.disposition_type]
        if (self.dispatch_kind, self.target_task_strategy) != expected_dispatch:
            raise ValueError("disposition 与调度策略映射不一致")
        if (
            self.rework_attempt_limit != 3
            or self.rework_attempt_index >= self.rework_attempt_limit
            or self.dispatch_kind == "auto_continue"
            and self.rework_attempt_index != 0
        ):
            raise ValueError("ready 前置检查必须遵守固定 rework attempt 边界")
        if (
            self.reviewed_diff_sha256 != self.current_diff_sha256
            or not self.reviewed_scope_paths
            or self.reviewed_scope_paths != self.current_scope_paths
            or not self.workspace_path
            or not self.workspace_path_within_root
        ):
            raise ValueError("ready 前置检查必须绑定当前一致的 diff 与 scope")
        if self.task_preparation_strategy == "claim_pending":
            if self.task_status_before != "pending" or not self.task_readiness_ready:
                raise ValueError("claim_pending 必须绑定可执行的 pending 任务")
        elif self.task_preparation_strategy == "retry_to_pending_then_claim":
            if (
                self.task_status_before not in ("failed", "blocked")
                or self.planned_task_status_after_preparation != "pending"
            ):
                raise ValueError("retry 策略必须绑定 failed/blocked 到 pending")
        else:
            raise ValueError("ready 前置检查必须包含合法任务准备策略")
        if self.task_human_status_before in ("requested", "in_progress"):
            raise ValueError("人工介入中的任务不得进入 ready 前置检查")
        if not all(
            (
                self.budget_pressure_level,
                self.budget_strategy_action,
                self.budget_strategy_code,
                self.budget_policy_source,
            )
        ):
            raise ValueError("ready 前置检查必须包含完整预算只读快照")
        if (
            self.dispatch_kind == "auto_continue"
            and self.non_convergence_checked
            or self.dispatch_kind == "auto_rework"
            and not self.non_convergence_checked
        ):
            raise ValueError("non-convergence 检查必须匹配调度类型")
        if (
            not self.budget_guard_allowed
            or self.retry_limit_reached
            or self.non_convergence_detected
            or not self.replay_check_completed
            or self.blocked_reasons
        ):
            raise ValueError("ready 前置检查未满足预算、收敛或 replay 条件")
        return self


__all__ = (
    "ProjectDirectorProtectedTransitionDispatchConsumptionPreflightResult",
    "ProtectedTransitionDispatchConsumptionPreflightStatus",
    "ProtectedTransitionTaskPreparationStrategy",
)
