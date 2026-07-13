"""Immutable P24-D2A1 exact next-Task routing contracts."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain._base import DomainModel
from app.domain.project import ProjectStage
from app.domain.project_director_next_task_source_bundle import (
    ProjectDirectorNextTaskSourceBundle,
)
from app.domain.project_director_source_execution_authority import (
    SourceExecutionAuthorityKind,
)
from app.domain.project_role import ProjectRoleCode
from app.domain.run import RunBudgetPressureLevel, RunBudgetStrategyAction
from app.domain.task import TaskHumanStatus, TaskPriority, TaskRiskLevel, TaskStatus


NEXT_TASK_SOURCE_AUTHORITY_LINEAGE_SCHEMA_VERSION = (
    "p24-d-source-authority-lineage.v1"
)
EXACT_NEXT_TASK_ROUTING_SCHEMA_VERSION = "p24-d-exact-next-task-routing.v1"

ExactNextTaskRoutingResolutionStatus = Literal[
    "routing_snapshot_resolved",
    "plan_queue_exhausted",
    "blocked",
]
ExactNextTaskRoutingBlockedReason = Literal[
    "next_task_source_bundle_invalid",
    "next_task_completion_evidence_invalid",
    "next_task_completion_evidence_conflict",
    "next_task_missing",
    "next_task_identity_conflict",
    "next_task_state_conflict",
    "next_task_human_intervention_required",
    "next_task_routing_identity_conflict",
    "next_task_routing_authority_unavailable",
    "next_task_dependency_blocked",
    "next_task_not_ready",
    "next_task_budget_blocked",
    "next_task_strategy_invalid",
    "next_task_model_unresolved",
    "next_task_dispatch_status_invalid",
    "next_task_owner_role_conflict",
    "next_task_selected_skill_unconfirmed",
    "next_task_selected_skills_missing",
    "next_task_human_confirmation_required",
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_FORBIDDEN_ACTIONS = {
    "product_runtime_git_write",
    "global_pending_task_scan",
    "next_task_skip",
    "task_claim",
    "run_creation",
    "worker_invocation",
    "workspace_write",
    "verification_command_execution",
}


class _FingerprintSnapshot(DomainModel):
    model_config = ConfigDict(frozen=True)

    @classmethod
    def fingerprint_payload(cls, payload: dict[str, Any]) -> str:
        canonical = json.dumps(
            cls._canonicalize(payload),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def _canonicalize(cls, value: Any) -> Any:
        if isinstance(value, BaseModel):
            return cls._canonicalize(value.model_dump(mode="python"))
        if isinstance(value, dict):
            return {str(key): cls._canonicalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._canonicalize(item) for item in value]
        if isinstance(value, UUID):
            return str(value).lower()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            normalized = value
            if normalized.tzinfo is None:
                normalized = normalized.replace(tzinfo=timezone.utc)
            return (
                normalized.astimezone(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )
        return value


class ProjectDirectorNextTaskSourceAuthorityLineageSnapshot(
    _FingerprintSnapshot
):
    """Completion-evidence authority frozen for the exact routing decision."""

    schema_version: Literal["p24-d-source-authority-lineage.v1"] = (
        NEXT_TASK_SOURCE_AUTHORITY_LINEAGE_SCHEMA_VERSION
    )

    source_completion_evidence_id: UUID
    source_completion_evidence_fingerprint: str = Field(min_length=64, max_length=64)

    source_execution_authority_kind: SourceExecutionAuthorityKind
    source_execution_authority_id: UUID
    source_execution_authority_fingerprint: str = Field(
        min_length=64,
        max_length=64,
    )

    source_reservation_id: UUID
    source_claim_id: UUID
    source_outcome_id: UUID
    source_outcome_schema_version: str = Field(min_length=1, max_length=100)
    source_outcome_fingerprint: str = Field(min_length=64, max_length=64)

    source_review_id: UUID | None = None
    source_review_outcome: str | None = Field(default=None, max_length=100)
    source_transition_evidence_ids: tuple[UUID, ...]

    completion_policy_id: UUID
    completion_policy_version: int = Field(ge=1)
    completion_policy_fingerprint: str = Field(min_length=64, max_length=64)

    completion_review_requirement: Literal["required", "not_required"]
    completion_review_satisfaction_status: Literal[
        "satisfied",
        "not_required_by_policy",
    ]
    completion_review_evidence_kind: str = Field(min_length=1, max_length=100)
    completion_review_evidence_ids: tuple[UUID, ...]

    source_completion_review_id: UUID | None = None
    source_completion_review_result_fingerprint: str | None = Field(
        default=None,
        max_length=64,
    )
    source_completion_review_verdict: str | None = Field(default=None, max_length=100)
    source_completion_review_disposition_id: UUID | None = None
    source_completion_review_disposition_type: str | None = Field(
        default=None,
        max_length=100,
    )
    source_completion_review_diff_id: UUID | None = None
    source_completion_review_diff_sha256: str | None = Field(
        default=None,
        max_length=64,
    )

    product_runtime_git_write_allowed: Literal[False] = False
    authority_lineage_fingerprint: str = Field(min_length=64, max_length=64)

    @field_validator(
        "source_completion_evidence_fingerprint",
        "source_execution_authority_fingerprint",
        "source_outcome_fingerprint",
        "completion_policy_fingerprint",
        "authority_lineage_fingerprint",
    )
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _LOWER_HEX_SHA256.fullmatch(value):
            raise ValueError("authority lineage hashes must be lowercase SHA-256")
        return value

    @field_validator(
        "source_completion_review_result_fingerprint",
        "source_completion_review_diff_sha256",
    )
    @classmethod
    def require_optional_sha256(cls, value: str | None) -> str | None:
        if value is not None and not _LOWER_HEX_SHA256.fullmatch(value):
            raise ValueError("completion review hashes must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def validate_lineage(
        self,
    ) -> "ProjectDirectorNextTaskSourceAuthorityLineageSnapshot":
        if (
            not self.source_transition_evidence_ids
            or len(self.source_transition_evidence_ids)
            != len(set(self.source_transition_evidence_ids))
            or not self.completion_review_evidence_ids
            or len(self.completion_review_evidence_ids)
            != len(set(self.completion_review_evidence_ids))
        ):
            raise ValueError("authority lineage evidence IDs must be non-empty and unique")
        if self.source_review_id is None and self.source_review_outcome is not None:
            raise ValueError("authority review outcome requires its authority review ID")
        completion_review_facts = (
            self.source_completion_review_id,
            self.source_completion_review_result_fingerprint,
            self.source_completion_review_verdict,
            self.source_completion_review_disposition_id,
            self.source_completion_review_disposition_type,
            self.source_completion_review_diff_id,
            self.source_completion_review_diff_sha256,
        )
        if self.completion_review_requirement == "not_required":
            if (
                self.completion_review_satisfaction_status
                != "not_required_by_policy"
                or any(item is not None for item in completion_review_facts)
            ):
                raise ValueError("not-required completion review facts are inconsistent")
        elif (
            self.completion_review_satisfaction_status != "satisfied"
            or any(item is None for item in completion_review_facts)
            or self.completion_review_evidence_ids[0]
            != self.source_completion_review_id
        ):
            raise ValueError("required completion review facts are inconsistent")
        if self.authority_lineage_fingerprint != self.compute_fingerprint():
            raise ValueError("authority lineage fingerprint does not match its payload")
        return self

    def compute_fingerprint(self) -> str:
        return self.fingerprint_payload(
            self.model_dump(
                mode="python",
                exclude={"authority_lineage_fingerprint"},
            )
        )


class ProjectDirectorRoutingScoreItemSnapshot(DomainModel):
    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=100)
    score: float
    detail: str = Field(min_length=1, max_length=500)

    @field_validator("score")
    @classmethod
    def require_finite_score(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("routing score item must be finite")
        return value


class ProjectDirectorStrategyReasonSnapshot(DomainModel):
    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=100)
    detail: str = Field(min_length=1, max_length=1_000)
    score: float | None = None

    @field_validator("score")
    @classmethod
    def require_finite_optional_score(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("strategy reason score must be finite")
        return value


class ProjectDirectorStrategyDecisionSnapshot(DomainModel):
    model_config = ConfigDict(frozen=True)

    version: str = Field(min_length=1, max_length=40)
    project_stage: ProjectStage | None = None
    owner_role_code: ProjectRoleCode
    model_tier: str = Field(min_length=1, max_length=40)
    model_name: str = Field(min_length=1, max_length=100)
    selected_skill_codes: tuple[str, ...]
    selected_skill_names: tuple[str, ...]
    budget_pressure_level: RunBudgetPressureLevel
    budget_action: RunBudgetStrategyAction
    strategy_code: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=2_000)
    role_model_policy_source: str | None = Field(default=None, max_length=40)
    role_model_policy_desired_tier: str | None = Field(default=None, max_length=40)
    role_model_policy_adjusted_tier: str | None = Field(default=None, max_length=40)
    role_model_policy_final_tier: str | None = Field(default=None, max_length=40)
    role_model_policy_stage_override_applied: bool = False
    rule_codes: tuple[str, ...]
    reasons: tuple[ProjectDirectorStrategyReasonSnapshot, ...]

    @field_validator("model_tier", "model_name", "strategy_code", "summary")
    @classmethod
    def require_nonblank_identity(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("strategy decision identity must be non-blank")
        return value

    @model_validator(mode="after")
    def validate_decision(self) -> "ProjectDirectorStrategyDecisionSnapshot":
        if (
            not self.selected_skill_codes
            or len(self.selected_skill_codes) != len(self.selected_skill_names)
            or len(self.selected_skill_codes) != len(set(self.selected_skill_codes))
            or len(self.selected_skill_names) != len(set(self.selected_skill_names))
            or len(self.rule_codes) != len(set(self.rule_codes))
        ):
            raise ValueError("strategy decision Skill or rule identity is inconsistent")
        return self


class ProjectDirectorExactNextTaskRoutingSnapshot(_FingerprintSnapshot):
    """Deterministic readonly Router result for one exact next Task."""

    schema_version: Literal["p24-d-exact-next-task-routing.v1"] = (
        EXACT_NEXT_TASK_ROUTING_SCHEMA_VERSION
    )
    routing_snapshot_fingerprint: str = Field(min_length=64, max_length=64)

    source_bundle_fingerprint: str = Field(min_length=64, max_length=64)
    authority_lineage_fingerprint: str = Field(min_length=64, max_length=64)

    session_id: UUID
    project_id: UUID
    plan_version_id: UUID
    task_creation_record_id: UUID

    source_task_id: UUID
    source_run_id: UUID
    source_completion_evidence_id: UUID

    next_task_id: UUID
    next_task_index: int = Field(ge=0)
    task_count: int = Field(ge=1)

    task_status: TaskStatus
    task_human_status: TaskHumanStatus
    task_paused_reason_absent: Literal[True] = True
    task_owner_role_code: ProjectRoleCode
    task_priority: TaskPriority
    task_risk_level: TaskRiskLevel
    task_dependency_ids: tuple[UUID, ...]

    ready: Literal[True] = True
    readiness_ready: Literal[True] = True
    readiness_blocking_codes: tuple[str, ...] = ()

    routing_score: float
    routing_score_breakdown: tuple[ProjectDirectorRoutingScoreItemSnapshot, ...]
    route_reason: str = Field(min_length=1, max_length=4_000)

    execution_attempts: int = Field(ge=0)
    recent_failure_count: int = Field(ge=0)

    budget_pressure_level: RunBudgetPressureLevel
    budget_action: RunBudgetStrategyAction
    budget_strategy_code: str = Field(min_length=1, max_length=100)
    budget_score_adjustment: float

    project_stage: ProjectStage | None = None
    owner_role_code: ProjectRoleCode
    upstream_role_code: ProjectRoleCode | None = None
    downstream_role_code: ProjectRoleCode | None = None

    dispatch_status: str = Field(min_length=1, max_length=100)
    handoff_reason: str = Field(min_length=1, max_length=2_000)
    matched_terms: tuple[str, ...]

    model_name: str = Field(min_length=1, max_length=100)
    model_tier: str = Field(min_length=1, max_length=40)

    selected_skill_codes: tuple[str, ...]
    selected_skill_names: tuple[str, ...]

    strategy_code: str = Field(min_length=1, max_length=100)
    strategy_summary: str = Field(min_length=1, max_length=2_000)
    strategy_reasons: tuple[ProjectDirectorStrategyReasonSnapshot, ...]
    strategy_decision: ProjectDirectorStrategyDecisionSnapshot

    human_confirmation_required: Literal[False] = False
    human_confirmation_evidence_id: None = None

    product_runtime_git_write_allowed: Literal[False] = False
    forbidden_actions: tuple[str, ...]

    @field_validator(
        "routing_snapshot_fingerprint",
        "source_bundle_fingerprint",
        "authority_lineage_fingerprint",
    )
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _LOWER_HEX_SHA256.fullmatch(value):
            raise ValueError("routing snapshot hashes must be lowercase SHA-256")
        return value

    @field_validator("routing_score", "budget_score_adjustment")
    @classmethod
    def require_finite_score(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("routing snapshot scores must be finite")
        return value

    @field_validator("model_name", "model_tier")
    @classmethod
    def require_nonblank_model_identity(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("routing snapshot model identity must be non-blank")
        return value

    @model_validator(mode="after")
    def validate_snapshot(self) -> "ProjectDirectorExactNextTaskRoutingSnapshot":
        if self.next_task_index >= self.task_count:
            raise ValueError("exact next Task index is outside the confirmed queue")
        if self.task_status != TaskStatus.PENDING or self.readiness_blocking_codes:
            raise ValueError("resolved routing snapshot must freeze a ready pending Task")
        if self.task_human_status in {
            TaskHumanStatus.REQUESTED,
            TaskHumanStatus.IN_PROGRESS,
        }:
            raise ValueError("resolved routing snapshot cannot require human work")
        if (
            self.owner_role_code != self.task_owner_role_code
            or self.strategy_decision.project_stage != self.project_stage
            or self.strategy_decision.owner_role_code != self.owner_role_code
            or self.strategy_decision.model_name != self.model_name
            or self.strategy_decision.model_tier != self.model_tier
            or self.strategy_decision.budget_pressure_level
            != self.budget_pressure_level
            or self.strategy_decision.budget_action != self.budget_action
            or self.strategy_decision.strategy_code != self.strategy_code
            or self.strategy_decision.summary != self.strategy_summary
            or self.strategy_decision.selected_skill_codes
            != self.selected_skill_codes
            or self.strategy_decision.selected_skill_names
            != self.selected_skill_names
            or self.strategy_decision.reasons != self.strategy_reasons
        ):
            raise ValueError("routing snapshot identity conflicts with strategy output")
        if (
            not self.selected_skill_codes
            or len(self.selected_skill_codes) != len(self.selected_skill_names)
            or len(self.selected_skill_codes) != len(set(self.selected_skill_codes))
            or len(self.selected_skill_names) != len(set(self.selected_skill_names))
        ):
            raise ValueError("resolved routing snapshot requires unique selected Skills")
        if (
            not self.forbidden_actions
            or len(self.forbidden_actions) != len(set(self.forbidden_actions))
            or not _REQUIRED_FORBIDDEN_ACTIONS.issubset(self.forbidden_actions)
        ):
            raise ValueError("routing snapshot forbidden actions must be non-empty and unique")
        if self.routing_snapshot_fingerprint != self.compute_fingerprint():
            raise ValueError("routing snapshot fingerprint does not match its payload")
        return self

    def compute_fingerprint(self) -> str:
        return self.fingerprint_payload(
            self.model_dump(
                mode="python",
                exclude={"routing_snapshot_fingerprint"},
            )
        )


class ProjectDirectorExactNextTaskRoutingResolution(DomainModel):
    """Three-state fail-closed result for P24-D2A1 exact routing."""

    model_config = ConfigDict(frozen=True)

    status: ExactNextTaskRoutingResolutionStatus
    source_bundle: ProjectDirectorNextTaskSourceBundle | None = None
    authority_lineage: (
        ProjectDirectorNextTaskSourceAuthorityLineageSnapshot | None
    ) = None
    routing_snapshot: ProjectDirectorExactNextTaskRoutingSnapshot | None = None
    blocked_reasons: tuple[ExactNextTaskRoutingBlockedReason, ...] = ()
    routing_blocker_codes: tuple[str, ...] = ()
    product_runtime_git_write_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_resolution(
        self,
    ) -> "ProjectDirectorExactNextTaskRoutingResolution":
        if (
            len(self.blocked_reasons) != len(set(self.blocked_reasons))
            or len(self.routing_blocker_codes)
            != len(set(self.routing_blocker_codes))
        ):
            raise ValueError("routing resolution reasons and codes must be unique")
        if self.status == "routing_snapshot_resolved":
            if (
                self.source_bundle is None
                or self.authority_lineage is None
                or self.routing_snapshot is None
                or self.blocked_reasons
                or self.routing_blocker_codes
            ):
                raise ValueError("resolved routing result is inconsistent")
            bundle = self.source_bundle
            lineage = self.authority_lineage
            snapshot = self.routing_snapshot
            if (
                lineage.source_completion_evidence_id
                != bundle.source_completion_evidence_id
                or lineage.source_completion_evidence_fingerprint
                != bundle.source_completion_evidence_fingerprint
                or snapshot.source_bundle_fingerprint
                != bundle.source_bundle_fingerprint
                or snapshot.authority_lineage_fingerprint
                != lineage.authority_lineage_fingerprint
                or snapshot.session_id != bundle.session_id
                or snapshot.project_id != bundle.project_id
                or snapshot.plan_version_id != bundle.plan_version_id
                or snapshot.task_creation_record_id
                != bundle.task_creation_record_id
                or snapshot.source_task_id != bundle.source_task_id
                or snapshot.source_run_id != bundle.source_run_id
                or snapshot.source_completion_evidence_id
                != bundle.source_completion_evidence_id
                or snapshot.next_task_id != bundle.next_task_id
                or snapshot.next_task_index != bundle.next_task_index
                or snapshot.task_count != bundle.task_count
            ):
                raise ValueError("resolved routing snapshots have conflicting identity")
        elif self.status == "plan_queue_exhausted":
            if (
                self.source_bundle is not None
                or self.authority_lineage is not None
                or self.routing_snapshot is not None
                or self.blocked_reasons
                or self.routing_blocker_codes
            ):
                raise ValueError("exhausted routing result is inconsistent")
        elif self.routing_snapshot is not None or not self.blocked_reasons:
            raise ValueError("blocked routing result requires reasons and no snapshot")
        elif self.authority_lineage is not None:
            if self.source_bundle is None:
                raise ValueError("blocked authority lineage requires its source bundle")
            if (
                self.authority_lineage.source_completion_evidence_id
                != self.source_bundle.source_completion_evidence_id
                or self.authority_lineage.source_completion_evidence_fingerprint
                != self.source_bundle.source_completion_evidence_fingerprint
            ):
                raise ValueError("blocked routing evidence has conflicting identity")
        return self

    @classmethod
    def blocked(
        cls,
        *reasons: ExactNextTaskRoutingBlockedReason,
        source_bundle: ProjectDirectorNextTaskSourceBundle | None = None,
        authority_lineage: (
            ProjectDirectorNextTaskSourceAuthorityLineageSnapshot | None
        ) = None,
        routing_blocker_codes: tuple[str, ...] = (),
    ) -> "ProjectDirectorExactNextTaskRoutingResolution":
        return cls(
            status="blocked",
            source_bundle=source_bundle,
            authority_lineage=authority_lineage,
            routing_snapshot=None,
            blocked_reasons=tuple(dict.fromkeys(reasons)),
            routing_blocker_codes=tuple(dict.fromkeys(routing_blocker_codes)),
        )


__all__ = (
    "EXACT_NEXT_TASK_ROUTING_SCHEMA_VERSION",
    "NEXT_TASK_SOURCE_AUTHORITY_LINEAGE_SCHEMA_VERSION",
    "ExactNextTaskRoutingBlockedReason",
    "ExactNextTaskRoutingResolutionStatus",
    "ProjectDirectorExactNextTaskRoutingResolution",
    "ProjectDirectorExactNextTaskRoutingSnapshot",
    "ProjectDirectorNextTaskSourceAuthorityLineageSnapshot",
    "ProjectDirectorRoutingScoreItemSnapshot",
    "ProjectDirectorStrategyDecisionSnapshot",
    "ProjectDirectorStrategyReasonSnapshot",
)
