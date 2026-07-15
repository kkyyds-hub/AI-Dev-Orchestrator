"""Project Director P23-B 受保护转换调度意图结果契约。"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


ProtectedTransitionDispatchIntentStatus = Literal["prepared", "blocked"]
ProtectedTransitionDispatchKind = Literal["auto_continue", "auto_rework"]
ProtectedTransitionTargetTaskStrategy = Literal[
    "source_task_continue",
    "source_task_rework",
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProjectDirectorProtectedTransitionDispatchIntentResult(DomainModel):
    """一条只准备、不消费也不执行的受保护转换调度意图。"""

    intent_status: ProtectedTransitionDispatchIntentStatus
    dispatch_intent_id: UUID | None = None
    dispatch_intent_fingerprint: str = Field(default="", max_length=64)

    session_id: UUID
    project_id: UUID | None = None
    source_task_id: UUID
    target_task_id: UUID | None = None

    source_p22_summary_message_id: UUID
    source_review_message_id: UUID | None = None
    source_disposition_message_id: UUID | None = None
    source_consumption_preflight_message_id: UUID | None = None
    source_consumption_message_id: UUID | None = None
    source_handoff_message_id: UUID | None = None
    source_freshness_message_id: UUID | None = None
    source_p25_convergence_decision_message_id: UUID | None = None
    source_p25_convergence_decision_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )
    source_p25_convergence_decision_replay_key: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )
    source_p25_candidate_diff_message_id: UUID | None = None
    source_p25_review_outcome_message_id: UUID | None = None

    disposition_type: Literal["AUTO_CONTINUE", "AUTO_REWORK"] | None = None
    transition_kind: str | None = None
    transition_authority: str | None = None
    dispatch_kind: ProtectedTransitionDispatchKind | None = None
    target_task_strategy: ProtectedTransitionTargetTaskStrategy | None = None

    review_result_fingerprint: str = Field(default="", max_length=64)
    review_semantic_fingerprint: str = Field(default="", max_length=64)
    freshness_evidence_fingerprint: str = Field(default="", max_length=64)

    source_diff_sha256: str = Field(default="", max_length=64)
    review_scope_paths: list[str] = Field(default_factory=list)
    workspace_path: str = Field(default="", max_length=2_000)
    workspace_path_within_root: bool = False
    source_freshness_validated_at: datetime | None = None

    rework_attempt_index: int = Field(default=0, ge=0)
    rework_attempt_limit: int = Field(default=3, ge=1)

    replay_check_completed: bool = False
    resumed_from_existing_intent: bool = False

    created_at: datetime = Field(default_factory=utc_now)
    blocked_reasons: list[str] = Field(default_factory=list)

    task_status_mutated: bool = False
    task_created: bool = False
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
        "task_status_mutated",
        "task_created",
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
        """调度意图准备不得执行转换、写文件或授权 Git 写入。"""

        if value:
            raise ValueError("调度意图准备不得产生执行或写入副作用")
        return value

    @field_validator("created_at", "source_freshness_validated_at", mode="after")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        """统一持久化时间为带时区的 UTC 时间。"""

        return ensure_utc_datetime(value)

    @field_validator(
        "source_p25_convergence_decision_fingerprint",
        "source_p25_convergence_decision_replay_key",
        mode="after",
    )
    @classmethod
    def validate_optional_p25_hash(cls, value: str | None) -> str | None:
        if value is not None and not _LOWER_HEX_SHA256.match(value):
            raise ValueError("P25 convergence gate hash must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def validate_intent_state(
        self,
    ) -> "ProjectDirectorProtectedTransitionDispatchIntentResult":
        """校验 prepared 与 blocked 两种终态的严格边界。"""

        p25_gate_values = (
            self.source_p25_convergence_decision_message_id,
            self.source_p25_convergence_decision_fingerprint,
            self.source_p25_convergence_decision_replay_key,
            self.source_p25_candidate_diff_message_id,
            self.source_p25_review_outcome_message_id,
        )
        if any(value is not None for value in p25_gate_values) and any(
            value is None for value in p25_gate_values
        ):
            raise ValueError("P25 convergence gate fields must be all present or absent")

        if self.intent_status == "blocked":
            if not self.blocked_reasons:
                raise ValueError("blocked 调度意图必须包含原因")
            return self

        required_values = (
            self.dispatch_intent_id,
            self.project_id,
            self.target_task_id,
            self.source_review_message_id,
            self.source_disposition_message_id,
            self.source_consumption_preflight_message_id,
            self.source_consumption_message_id,
            self.source_handoff_message_id,
            self.source_freshness_message_id,
            self.disposition_type,
            self.transition_kind,
            self.transition_authority,
            self.dispatch_kind,
            self.target_task_strategy,
            self.source_freshness_validated_at,
        )
        if any(value is None for value in required_values):
            raise ValueError("prepared 调度意图必须包含完整证据身份")
        fingerprints = (
            self.dispatch_intent_fingerprint,
            self.review_result_fingerprint,
            self.review_semantic_fingerprint,
            self.freshness_evidence_fingerprint,
            self.source_diff_sha256,
        )
        if not all(_LOWER_HEX_SHA256.match(value) for value in fingerprints):
            raise ValueError("prepared 调度意图必须包含有效 SHA-256 指纹")
        if self.target_task_id != self.source_task_id:
            raise ValueError("调度目标必须是来源任务")
        if not self.review_scope_paths or not self.workspace_path:
            raise ValueError("prepared 调度意图必须包含审查范围与工作区")
        if not self.workspace_path_within_root:
            raise ValueError("prepared 调度意图必须绑定根目录内工作区")
        if not self.replay_check_completed:
            raise ValueError("prepared 调度意图必须完成 replay 检查")
        if self.blocked_reasons:
            raise ValueError("prepared 调度意图不得包含 blocked 原因")

        expected_mapping = {
            "AUTO_CONTINUE": (
                "CONTINUE_GUARDRAIL",
                "auto_continue",
                "source_task_continue",
                0,
            ),
            "AUTO_REWORK": (
                "BOUNDED_REWORK_GUARDRAIL",
                "auto_rework",
                "source_task_rework",
                self.rework_attempt_index,
            ),
        }[self.disposition_type]
        if (
            self.transition_kind,
            self.dispatch_kind,
            self.target_task_strategy,
            self.rework_attempt_index,
        ) != expected_mapping:
            raise ValueError("disposition 与调度映射不一致")
        if self.transition_authority != "AUTOMATED_DISPOSITION":
            raise ValueError("prepared 调度意图必须来自自动 disposition")
        if all(value is not None for value in p25_gate_values) and (
            self.dispatch_kind != "auto_rework"
            or self.disposition_type != "AUTO_REWORK"
            or self.target_task_strategy != "source_task_rework"
            or self.source_review_message_id
            != self.source_p25_review_outcome_message_id
            or self.rework_attempt_index not in {1, 2}
        ):
            raise ValueError("P25 convergence gate is invalid for this dispatch intent")
        return self


__all__ = (
    "ProjectDirectorProtectedTransitionDispatchIntentResult",
    "ProtectedTransitionDispatchIntentStatus",
    "ProtectedTransitionDispatchKind",
    "ProtectedTransitionTargetTaskStrategy",
)
