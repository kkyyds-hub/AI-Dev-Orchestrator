"""Project Director P23-D1 原子调度消费结果契约。"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


ProtectedTransitionDispatchConsumptionStatus = Literal[
    "reserved_for_worker_start",
    "blocked",
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProjectDirectorProtectedTransitionDispatchConsumptionResult(DomainModel):
    """原子消费调度意图，并为未来 Worker 启动预留 exact Run。"""

    consumption_status: ProtectedTransitionDispatchConsumptionStatus
    consumption_id: UUID | None = None
    consumption_fingerprint: str = Field(default="", max_length=64)

    session_id: UUID
    project_id: UUID | None = None
    source_task_id: UUID
    target_task_id: UUID | None = None

    source_preflight_message_id: UUID
    source_preflight_id: UUID | None = None
    source_preflight_fingerprint: str = Field(default="", max_length=64)

    source_intent_message_id: UUID | None = None
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
    current_freshness_fingerprint: str = Field(default="", max_length=64)
    source_diff_sha256: str = Field(default="", max_length=64)
    review_scope_paths: list[str] = Field(default_factory=list)
    workspace_path: str = Field(default="", max_length=2_000)
    workspace_path_within_root: bool = False

    rework_attempt_index: int = Field(default=0, ge=0)
    rework_attempt_limit: int = Field(default=3, ge=1)

    task_status_before: str | None = None
    task_human_status_before: str | None = None
    retry_transition_applied: bool = False
    retry_transition_event_reason: str | None = None
    task_status_after: str | None = None
    task_claimed_at: datetime | None = None

    run_id: UUID | None = None
    run_status: str | None = None
    run_route_reason: str | None = None
    run_routing_score: float | None = None
    run_strategy_code: str | None = None
    run_model_name: str | None = None
    run_dispatch_status: str | None = None
    run_created_at: datetime | None = None

    budget_guard_allowed: bool = False
    budget_pressure_level: str | None = None
    budget_strategy_action: str | None = None
    budget_strategy_code: str | None = None
    budget_policy_source: str | None = None
    retry_limit_reached: bool = False

    replay_check_completed: bool = False
    resumed_from_existing_consumption: bool = False
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

    @field_validator(
        "created_at",
        "task_claimed_at",
        "run_created_at",
        mode="after",
    )
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        """统一持久化时间为带时区的 UTC 时间。"""

        return ensure_utc_datetime(value)

    @field_validator(
        "task_created",
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
        """D1 不得启动执行、创建 Task 或产生 workspace/Git 写入。"""

        if value:
            raise ValueError("D1 原子消费不得产生越界执行或写入副作用")
        return value

    @model_validator(mode="after")
    def validate_consumption_state(
        self,
    ) -> "ProjectDirectorProtectedTransitionDispatchConsumptionResult":
        """校验 reserved 与 blocked 两种终态的严格组合。"""

        if self.consumption_status == "blocked":
            if self.consumption_id is not None:
                raise ValueError("blocked 消费不得创建 consumption 记录")
            if any(
                (
                    self.dispatch_intent_consumed,
                    self.task_status_mutated,
                    self.task_claimed,
                    self.run_created,
                )
            ):
                raise ValueError("blocked 消费不得报告任何原子写入成功")
            if not self.blocked_reasons:
                raise ValueError("blocked 消费必须包含原因")
            return self

        required_values = (
            self.consumption_id,
            self.project_id,
            self.target_task_id,
            self.source_preflight_id,
            self.source_intent_message_id,
            self.source_dispatch_intent_id,
            self.source_p22_summary_message_id,
            self.source_review_message_id,
            self.source_freshness_message_id,
            self.disposition_type,
            self.dispatch_kind,
            self.target_task_strategy,
            self.task_status_before,
            self.task_human_status_before,
            self.task_status_after,
            self.task_claimed_at,
            self.run_id,
            self.run_status,
            self.run_route_reason,
            self.run_routing_score,
            self.run_strategy_code,
            self.run_model_name,
            self.run_dispatch_status,
            self.run_created_at,
            self.budget_pressure_level,
            self.budget_strategy_action,
            self.budget_strategy_code,
            self.budget_policy_source,
        )
        if any(value is None for value in required_values):
            raise ValueError("reserved 消费必须包含完整 preflight、Task、Run 与预算证据")
        fingerprints = (
            self.consumption_fingerprint,
            self.source_preflight_fingerprint,
            self.source_dispatch_intent_fingerprint,
            self.review_result_fingerprint,
            self.review_semantic_fingerprint,
            self.current_freshness_fingerprint,
            self.source_diff_sha256,
        )
        if not all(_LOWER_HEX_SHA256.match(value) for value in fingerprints):
            raise ValueError("reserved 消费必须包含有效 SHA-256 指纹")
        if (
            self.target_task_id != self.source_task_id
            or self.source_preflight_id != self.source_preflight_message_id
            or self.source_dispatch_intent_id != self.source_intent_message_id
        ):
            raise ValueError("reserved 消费必须绑定 exact source 证据与任务")
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
            raise ValueError("reserved 消费必须遵守固定 rework attempt 边界")
        if not self.review_scope_paths or not self.workspace_path_within_root:
            raise ValueError("reserved 消费必须绑定可信 workspace 与有序 scope")
        if self.task_human_status_before in ("requested", "in_progress"):
            raise ValueError("人工介入中的任务不得被原子消费")
        if self.dispatch_kind == "auto_continue":
            if self.task_status_before != "pending" or self.retry_transition_applied:
                raise ValueError("AUTO_CONTINUE 只能直接 claim pending task")
        elif self.task_status_before == "pending":
            if self.retry_transition_applied:
                raise ValueError("pending AUTO_REWORK 不得伪造 retry transition")
        elif self.task_status_before in ("failed", "blocked"):
            if (
                not self.retry_transition_applied
                or self.retry_transition_event_reason != "retried"
            ):
                raise ValueError("failed/blocked AUTO_REWORK 必须记录 retry transition")
        else:
            raise ValueError("AUTO_REWORK 来源任务状态不合法")
        if (
            self.task_status_after != "running"
            or self.run_status != "running"
            or not all(
                (
                    self.dispatch_intent_consumed,
                    self.task_status_mutated,
                    self.task_claimed,
                    self.run_created,
                    self.budget_guard_allowed,
                    self.replay_check_completed,
                )
            )
            or self.retry_limit_reached
            or self.blocked_reasons
        ):
            raise ValueError("reserved 消费必须完整记录 claim、Run 与预算成功状态")
        return self


__all__ = (
    "ProjectDirectorProtectedTransitionDispatchConsumptionResult",
    "ProtectedTransitionDispatchConsumptionStatus",
)
