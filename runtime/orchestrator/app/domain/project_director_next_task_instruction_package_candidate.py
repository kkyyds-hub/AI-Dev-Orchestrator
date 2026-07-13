"""Immutable P24-D2A2 next-Task instruction package Candidate contracts."""

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
from app.domain.project_director_exact_next_task_routing_snapshot import (
    ProjectDirectorExactNextTaskRoutingResolution,
    ProjectDirectorNextTaskSourceAuthorityLineageSnapshot,
    ProjectDirectorRoutingScoreItemSnapshot,
    ProjectDirectorStrategyDecisionSnapshot,
    ProjectDirectorStrategyReasonSnapshot,
)
from app.domain.project_director_next_task_source_bundle import (
    ProjectDirectorDeliverableBoundarySnapshot,
)
from app.domain.project_role import ProjectRoleCode
from app.domain.repository_workspace import RepositoryAccessMode
from app.domain.run import RunBudgetPressureLevel, RunBudgetStrategyAction
from app.domain.task import TaskPriority, TaskRiskLevel


NEXT_TASK_INSTRUCTION_PACKAGE_CANDIDATE_SCHEMA_VERSION = (
    "p24-d-instruction-candidate.v1"
)

NextTaskInstructionPackageCandidateResolutionStatus = Literal[
    "package_candidate_ready",
    "plan_queue_exhausted",
    "blocked",
]
NextTaskInstructionPackageCandidateBlockedReason = Literal[
    "instruction_candidate_routing_invalid",
    "instruction_candidate_source_conflict",
    "instruction_candidate_task_missing",
    "instruction_candidate_task_conflict",
    "instruction_candidate_task_state_conflict",
    "instruction_candidate_scope_invalid",
    "instruction_candidate_scope_conflict",
    "instruction_candidate_repository_binding_missing",
    "instruction_candidate_repository_binding_ambiguous",
    "instruction_candidate_repository_target_invalid",
    "instruction_candidate_workspace_root_conflict",
    "instruction_candidate_workspace_escape",
    "instruction_candidate_branch_conflict",
    "instruction_candidate_workspace_root_scope_unconfirmed",
    "instruction_candidate_allowed_path_invalid",
    "instruction_candidate_allowed_path_duplicate",
    "instruction_candidate_forbidden_path_invalid",
    "instruction_candidate_forbidden_path_duplicate",
    "instruction_candidate_path_policy_conflict",
    "instruction_candidate_acceptance_criteria_missing",
    "instruction_candidate_verification_requirements_missing",
    "instruction_candidate_verification_requirement_unconfirmed",
    "instruction_candidate_human_confirmation_required",
    "instruction_candidate_routing_snapshot_invalid",
    "instruction_candidate_model_invalid",
    "instruction_candidate_skill_conflict",
    "instruction_candidate_invalid",
]
AcceptanceCriteriaSource = Literal["task", "confirmed_plan"]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_FORBIDDEN_ACTIONS = {
    "product_runtime_git_write",
    "git_add",
    "git_commit",
    "git_push",
    "pull_request_creation",
    "merge",
    "branch_destruction",
    "global_pending_task_scan",
    "next_task_skip",
    "plan_mutation",
    "duplicate_task_creation",
    "task_claim",
    "run_creation",
    "worker_invocation",
    "workspace_write",
    "verification_command_execution",
    "package_persistence",
    "continuation_persistence",
}


class _CandidateSnapshot(DomainModel):
    model_config = ConfigDict(frozen=True)


class _FingerprintSnapshot(_CandidateSnapshot):
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


class ProjectDirectorConfirmedInstructionScopeSnapshot(_CandidateSnapshot):
    model_config = ConfigDict(frozen=True)

    project_in_scope: tuple[str, ...]
    project_out_of_scope: tuple[str, ...]
    project_assumptions: tuple[str, ...]

    next_proposed_task_title: str
    next_proposed_task_description: str
    next_proposed_task_role_code: ProjectRoleCode
    next_proposed_task_priority_hint: str

    deliverable_boundaries: tuple[
        ProjectDirectorDeliverableBoundarySnapshot, ...
    ]

    @model_validator(mode="after")
    def validate_scope(
        self,
    ) -> "ProjectDirectorConfirmedInstructionScopeSnapshot":
        collections = (
            self.project_in_scope,
            self.project_out_of_scope,
            self.project_assumptions,
        )
        if any(not item.strip() for values in collections for item in values):
            raise ValueError("candidate scope entries must be non-blank")
        if any(
            not value.strip()
            for value in (
                self.next_proposed_task_title,
                self.next_proposed_task_description,
                self.next_proposed_task_priority_hint,
            )
        ):
            raise ValueError("candidate ProposedTask scope is incomplete")
        normalized_in_scope = {
            " ".join(value.split()).casefold()
            for value in self.project_in_scope
        }
        normalized_out_of_scope = {
            " ".join(value.split()).casefold()
            for value in self.project_out_of_scope
        }
        if normalized_in_scope & normalized_out_of_scope:
            raise ValueError("candidate scope is contradictory")
        for boundary in self.deliverable_boundaries:
            if any(
                not value.strip()
                for value in (
                    boundary.name,
                    boundary.description,
                    boundary.done_definition,
                    boundary.acceptance_signal,
                )
            ) or any(not item.strip() for item in boundary.required_contents):
                raise ValueError("candidate deliverable boundary is incomplete")
        return self


class ProjectDirectorCandidateRepositoryBindingSnapshot(_CandidateSnapshot):
    model_config = ConfigDict(frozen=True)

    binding_type: str
    binding_mode: str
    target: str
    configured_branch: str
    effective_branch: str
    focus_paths: tuple[str, ...]
    usage: str
    safety_note: str
    review_status: str


class ProjectDirectorCandidateWorkspaceBindingSnapshot(_CandidateSnapshot):
    model_config = ConfigDict(frozen=True)

    workspace_id: UUID
    project_id: UUID
    root_path: str
    allowed_workspace_root: str
    display_name: str
    access_mode: RepositoryAccessMode
    default_base_branch: str
    ignore_rule_summary: tuple[str, ...]


class ProjectDirectorCandidateVerificationRequirement(_CandidateSnapshot):
    model_config = ConfigDict(frozen=True)

    name: str
    purpose: str
    owner_role_code: str
    risk_level: str
    requires_user_confirmation: bool
    review_status: str

    @model_validator(mode="after")
    def validate_requirement(
        self,
    ) -> "ProjectDirectorCandidateVerificationRequirement":
        if any(
            not value.strip()
            for value in (
                self.name,
                self.owner_role_code,
                self.risk_level,
                self.review_status,
            )
        ):
            raise ValueError("candidate verification identity is incomplete")
        return self


class ProjectDirectorCandidateTestRequirement(_CandidateSnapshot):
    model_config = ConfigDict(frozen=True)

    mechanism_name: str
    command_or_method: str

    @model_validator(mode="after")
    def validate_requirement(self) -> "ProjectDirectorCandidateTestRequirement":
        if not self.mechanism_name.strip() or not self.command_or_method.strip():
            raise ValueError("candidate test requirement is incomplete")
        return self


class ProjectDirectorCandidateEvidenceRequirement(_CandidateSnapshot):
    model_config = ConfigDict(frozen=True)

    mechanism_name: str
    evidence_required: str

    @model_validator(mode="after")
    def validate_requirement(
        self,
    ) -> "ProjectDirectorCandidateEvidenceRequirement":
        if not self.mechanism_name.strip() or not self.evidence_required.strip():
            raise ValueError("candidate evidence requirement is incomplete")
        return self


class ProjectDirectorCandidateSelectedStrategy(_CandidateSnapshot):
    model_config = ConfigDict(frozen=True)

    strategy_code: str
    strategy_summary: str
    strategy_reasons: tuple[ProjectDirectorStrategyReasonSnapshot, ...]
    strategy_decision: ProjectDirectorStrategyDecisionSnapshot

    routing_score: float
    routing_score_breakdown: tuple[ProjectDirectorRoutingScoreItemSnapshot, ...]
    route_reason: str
    execution_attempts: int = Field(ge=0)
    recent_failure_count: int = Field(ge=0)

    budget_pressure_level: RunBudgetPressureLevel
    budget_action: RunBudgetStrategyAction
    budget_strategy_code: str
    budget_score_adjustment: float

    dispatch_status: str
    handoff_reason: str
    matched_terms: tuple[str, ...]
    project_stage: ProjectStage | None
    owner_role_code: ProjectRoleCode
    upstream_role_code: ProjectRoleCode | None
    downstream_role_code: ProjectRoleCode | None

    @field_validator("routing_score", "budget_score_adjustment")
    @classmethod
    def require_finite_score(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("candidate strategy scores must be finite")
        return value


class ProjectDirectorCandidateSelectedModel(_CandidateSnapshot):
    model_config = ConfigDict(frozen=True)

    model_name: str
    model_tier: str

    @model_validator(mode="after")
    def validate_model(self) -> "ProjectDirectorCandidateSelectedModel":
        if not self.model_name.strip() or not self.model_tier.strip():
            raise ValueError("candidate selected Model is incomplete")
        return self


class ProjectDirectorCandidateSelectedSkill(_CandidateSnapshot):
    model_config = ConfigDict(frozen=True)

    skill_code: str
    skill_name: str

    @model_validator(mode="after")
    def validate_skill(self) -> "ProjectDirectorCandidateSelectedSkill":
        if not self.skill_code.strip() or not self.skill_name.strip():
            raise ValueError("candidate selected Skill is incomplete")
        return self


class ProjectDirectorNextTaskInstructionPackageCandidate(_FingerprintSnapshot):
    """Deterministic, non-persisted instruction package Candidate."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["p24-d-instruction-candidate.v1"] = (
        NEXT_TASK_INSTRUCTION_PACKAGE_CANDIDATE_SCHEMA_VERSION
    )
    candidate_fingerprint: str = Field(min_length=64, max_length=64)

    source_bundle_fingerprint: str = Field(min_length=64, max_length=64)
    authority_lineage_fingerprint: str = Field(min_length=64, max_length=64)
    routing_snapshot_fingerprint: str = Field(min_length=64, max_length=64)

    session_id: UUID
    project_id: UUID
    plan_version_id: UUID
    plan_version_no: int = Field(ge=1)
    task_creation_record_id: UUID

    source_task_id: UUID
    source_run_id: UUID
    source_completion_evidence_id: UUID
    source_authority_lineage: (
        ProjectDirectorNextTaskSourceAuthorityLineageSnapshot
    )

    next_task_id: UUID
    next_task_index: int = Field(ge=0)
    task_count: int = Field(ge=1)
    task_title: str
    task_input_summary: str
    owner_role_code: ProjectRoleCode
    priority: TaskPriority
    risk_level: TaskRiskLevel
    depends_on_task_ids: tuple[UUID, ...]

    confirmed_scope: ProjectDirectorConfirmedInstructionScopeSnapshot

    repository_binding: ProjectDirectorCandidateRepositoryBindingSnapshot
    workspace_binding: ProjectDirectorCandidateWorkspaceBindingSnapshot
    allowed_paths: tuple[str, ...]
    forbidden_scope_entries: tuple[str, ...]
    workspace_ignore_rule_summary: tuple[str, ...]
    forbidden_paths: tuple[str, ...]

    acceptance_criteria_source: AcceptanceCriteriaSource
    acceptance_criteria: tuple[str, ...]

    verification_requirements: tuple[
        ProjectDirectorCandidateVerificationRequirement, ...
    ]
    test_requirements: tuple[ProjectDirectorCandidateTestRequirement, ...]
    evidence_requirements: tuple[
        ProjectDirectorCandidateEvidenceRequirement, ...
    ]

    selected_strategy: ProjectDirectorCandidateSelectedStrategy
    selected_model: ProjectDirectorCandidateSelectedModel
    selected_skills: tuple[ProjectDirectorCandidateSelectedSkill, ...]

    human_confirmation_required: Literal[False] = False
    human_confirmation_evidence_id: None = None
    product_runtime_git_write_allowed: Literal[False] = False
    forbidden_actions: tuple[str, ...]

    @field_validator(
        "candidate_fingerprint",
        "source_bundle_fingerprint",
        "authority_lineage_fingerprint",
        "routing_snapshot_fingerprint",
    )
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _LOWER_HEX_SHA256.fullmatch(value):
            raise ValueError("candidate hashes must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def validate_candidate(
        self,
    ) -> "ProjectDirectorNextTaskInstructionPackageCandidate":
        if self.next_task_index >= self.task_count:
            raise ValueError("candidate next Task index is outside the queue")
        if (
            self.authority_lineage_fingerprint
            != self.source_authority_lineage.authority_lineage_fingerprint
            or self.source_completion_evidence_id
            != self.source_authority_lineage.source_completion_evidence_id
            or self.owner_role_code != self.selected_strategy.owner_role_code
            or self.selected_model.model_name
            != self.selected_strategy.strategy_decision.model_name
            or self.selected_model.model_tier
            != self.selected_strategy.strategy_decision.model_tier
        ):
            raise ValueError("candidate authority or routing identity is inconsistent")
        if (
            not self.allowed_paths
            or len(self.allowed_paths) != len(set(self.allowed_paths))
            or len(self.forbidden_paths) != len(set(self.forbidden_paths))
        ):
            raise ValueError("candidate path policy must be non-empty and unique")
        if self.repository_binding.focus_paths != self.allowed_paths:
            raise ValueError("candidate repository focus paths are inconsistent")
        if self.project_id != self.workspace_binding.project_id:
            raise ValueError("candidate workspace binding identity is inconsistent")
        if (
            not self.acceptance_criteria
            or len(self.acceptance_criteria) != len(set(self.acceptance_criteria))
            or any(not item.strip() for item in self.acceptance_criteria)
        ):
            raise ValueError("candidate acceptance criteria are invalid")

        verification_names = tuple(
            item.name for item in self.verification_requirements
        )
        test_names = tuple(item.mechanism_name for item in self.test_requirements)
        evidence_names = tuple(
            item.mechanism_name for item in self.evidence_requirements
        )
        if (
            not verification_names
            or verification_names != test_names
            or verification_names != evidence_names
            or len(verification_names) != len(set(verification_names))
        ):
            raise ValueError("candidate verification requirement order is invalid")
        if any(
            not item.command_or_method.strip() for item in self.test_requirements
        ) or any(
            not item.evidence_required.strip()
            for item in self.evidence_requirements
        ):
            raise ValueError("candidate test or evidence requirement is empty")

        skill_codes = tuple(item.skill_code for item in self.selected_skills)
        skill_names = tuple(item.skill_name for item in self.selected_skills)
        if (
            not skill_codes
            or any(not code.strip() for code in skill_codes)
            or any(not name.strip() for name in skill_names)
            or len(skill_codes) != len(set(skill_codes))
            or len(skill_names) != len(set(skill_names))
            or skill_codes
            != self.selected_strategy.strategy_decision.selected_skill_codes
            or skill_names
            != self.selected_strategy.strategy_decision.selected_skill_names
        ):
            raise ValueError("candidate selected Skills are invalid")
        if (
            not self.forbidden_actions
            or len(self.forbidden_actions) != len(set(self.forbidden_actions))
            or not _REQUIRED_FORBIDDEN_ACTIONS.issubset(self.forbidden_actions)
        ):
            raise ValueError("candidate forbidden actions are incomplete")
        if self.candidate_fingerprint != self.compute_fingerprint():
            raise ValueError("candidate fingerprint does not match its payload")
        return self

    def compute_fingerprint(self) -> str:
        return self.fingerprint_payload(
            self.model_dump(mode="python", exclude={"candidate_fingerprint"})
        )


class ProjectDirectorNextTaskInstructionPackageCandidateResolution(DomainModel):
    """Three-state, fail-closed result for the readonly P24-D2A2 builder."""

    model_config = ConfigDict(frozen=True)

    status: NextTaskInstructionPackageCandidateResolutionStatus
    routing_resolution: ProjectDirectorExactNextTaskRoutingResolution
    candidate: ProjectDirectorNextTaskInstructionPackageCandidate | None = None
    blocked_reasons: tuple[
        NextTaskInstructionPackageCandidateBlockedReason, ...
    ] = ()
    product_runtime_git_write_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_resolution(
        self,
    ) -> "ProjectDirectorNextTaskInstructionPackageCandidateResolution":
        if len(self.blocked_reasons) != len(set(self.blocked_reasons)):
            raise ValueError("candidate blocked reasons must be unique")
        if self.status == "package_candidate_ready":
            if (
                self.routing_resolution.status != "routing_snapshot_resolved"
                or self.candidate is None
                or self.blocked_reasons
            ):
                raise ValueError("ready candidate resolution is inconsistent")
        elif self.status == "plan_queue_exhausted":
            if (
                self.routing_resolution.status != "plan_queue_exhausted"
                or self.candidate is not None
                or self.blocked_reasons
            ):
                raise ValueError("exhausted candidate resolution is inconsistent")
        elif self.candidate is not None or not self.blocked_reasons:
            raise ValueError("blocked candidate resolution is inconsistent")
        return self

    @classmethod
    def blocked(
        cls,
        routing_resolution: ProjectDirectorExactNextTaskRoutingResolution,
        *reasons: NextTaskInstructionPackageCandidateBlockedReason,
    ) -> "ProjectDirectorNextTaskInstructionPackageCandidateResolution":
        return cls(
            status="blocked",
            routing_resolution=routing_resolution,
            candidate=None,
            blocked_reasons=tuple(dict.fromkeys(reasons)),
        )


__all__ = (
    "NEXT_TASK_INSTRUCTION_PACKAGE_CANDIDATE_SCHEMA_VERSION",
    "AcceptanceCriteriaSource",
    "NextTaskInstructionPackageCandidateBlockedReason",
    "NextTaskInstructionPackageCandidateResolutionStatus",
    "ProjectDirectorCandidateEvidenceRequirement",
    "ProjectDirectorCandidateRepositoryBindingSnapshot",
    "ProjectDirectorCandidateSelectedModel",
    "ProjectDirectorCandidateSelectedSkill",
    "ProjectDirectorCandidateSelectedStrategy",
    "ProjectDirectorCandidateTestRequirement",
    "ProjectDirectorCandidateVerificationRequirement",
    "ProjectDirectorCandidateWorkspaceBindingSnapshot",
    "ProjectDirectorConfirmedInstructionScopeSnapshot",
    "ProjectDirectorNextTaskInstructionPackageCandidate",
    "ProjectDirectorNextTaskInstructionPackageCandidateResolution",
)
