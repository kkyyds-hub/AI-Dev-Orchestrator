"""Immutable P24-D2B1 formal next-Task instruction package contract."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime
from app.domain.project_director_exact_next_task_routing_snapshot import (
    ProjectDirectorNextTaskSourceAuthorityLineageSnapshot,
)
from app.domain.project_director_next_task_instruction_package_candidate import (
    NEXT_TASK_INSTRUCTION_PACKAGE_CANDIDATE_SCHEMA_VERSION,
    AcceptanceCriteriaSource,
    ProjectDirectorCandidateEvidenceRequirement,
    ProjectDirectorCandidateRepositoryBindingSnapshot,
    ProjectDirectorCandidateSelectedModel,
    ProjectDirectorCandidateSelectedSkill,
    ProjectDirectorCandidateSelectedStrategy,
    ProjectDirectorCandidateTestRequirement,
    ProjectDirectorCandidateVerificationRequirement,
    ProjectDirectorCandidateWorkspaceBindingSnapshot,
    ProjectDirectorConfirmedInstructionScopeSnapshot,
)
from app.domain.project_director_source_execution_authority import (
    SourceExecutionAuthorityKind,
)
from app.domain.project_role import ProjectRoleCode
from app.domain.task import TaskPriority, TaskRiskLevel


NEXT_TASK_INSTRUCTION_PACKAGE_SCHEMA_VERSION = "p24-d-instruction.v1"
NEXT_TASK_INSTRUCTION_PACKAGE_REPLAY_SCHEMA_VERSION = "p24-package-replay.v1"
NEXT_TASK_INSTRUCTION_PACKAGE_ACTION = "cross_task_auto_continue"

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
    "uncontrolled_workspace_write",
}


def canonicalize_p24_contract_value(value: Any) -> Any:
    """Convert P24 contract values into canonical JSON-compatible values."""

    if isinstance(value, BaseModel):
        return canonicalize_p24_contract_value(value.model_dump(mode="python"))
    if isinstance(value, dict):
        return {
            str(key): canonicalize_p24_contract_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [canonicalize_p24_contract_value(item) for item in value]
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


def compute_p24_contract_sha256(payload: dict[str, Any]) -> str:
    """Return lowercase SHA-256 for one canonical P24 contract payload."""

    canonical = json.dumps(
        canonicalize_p24_contract_value(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ProjectDirectorNextTaskInstructionPackage(DomainModel):
    """Formal immutable package produced from one exact D2A2 Candidate."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["p24-d-instruction.v1"] = (
        NEXT_TASK_INSTRUCTION_PACKAGE_SCHEMA_VERSION
    )

    package_id: UUID
    package_fingerprint: str = Field(min_length=64, max_length=64)
    package_replay_key: str = Field(min_length=64, max_length=64)
    created_at: datetime
    continuation_id: UUID
    supersedes_package_id: UUID | None = None

    instruction_candidate_schema_version: Literal[
        "p24-d-instruction-candidate.v1"
    ] = NEXT_TASK_INSTRUCTION_PACKAGE_CANDIDATE_SCHEMA_VERSION
    instruction_candidate_fingerprint: str = Field(min_length=64, max_length=64)

    session_id: UUID
    project_id: UUID
    plan_version_id: UUID
    plan_version_no: int = Field(ge=1)
    task_creation_record_id: UUID

    source_task_id: UUID
    source_run_id: UUID
    source_completion_evidence_id: UUID
    source_completion_evidence_fingerprint: str = Field(
        min_length=64,
        max_length=64,
    )

    source_execution_authority_kind: SourceExecutionAuthorityKind
    source_execution_authority_id: UUID
    source_execution_authority_fingerprint: str = Field(
        min_length=64,
        max_length=64,
    )
    source_worker_start_reservation_id: UUID
    source_worker_invocation_claim_id: UUID
    source_worker_invocation_outcome_id: UUID
    source_worker_outcome_schema_version: str
    source_worker_outcome_fingerprint: str = Field(min_length=64, max_length=64)

    source_review_id: UUID | None = None
    source_review_outcome: str | None = None
    source_transition_evidence_ids: tuple[UUID, ...]

    completion_policy_id: UUID
    completion_policy_version: int = Field(ge=1)
    completion_policy_fingerprint: str = Field(min_length=64, max_length=64)
    review_requirement: Literal["required", "not_required"]

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

    @field_validator("created_at", mode="after")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        normalized = ensure_utc_datetime(value)
        if normalized is None or normalized.tzinfo is None:
            raise ValueError("instruction package created_at must be UTC-aware")
        return normalized

    @field_validator(
        "package_fingerprint",
        "package_replay_key",
        "instruction_candidate_fingerprint",
        "source_completion_evidence_fingerprint",
        "source_execution_authority_fingerprint",
        "source_worker_outcome_fingerprint",
        "completion_policy_fingerprint",
    )
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _LOWER_HEX_SHA256.fullmatch(value):
            raise ValueError("instruction package hashes must be lowercase SHA-256")
        return value

    @field_validator("source_worker_outcome_schema_version")
    @classmethod
    def require_outcome_schema(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("source Worker outcome schema must be exact and non-blank")
        return value

    @field_validator("source_review_outcome")
    @classmethod
    def require_source_review_outcome(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or value != value.strip()):
            raise ValueError("source authority review outcome must be exact")
        return value

    @model_validator(mode="after")
    def validate_package(self) -> "ProjectDirectorNextTaskInstructionPackage":
        if self.package_id == self.continuation_id:
            raise ValueError("instruction package and continuation IDs must differ")
        if self.supersedes_package_id in {self.package_id, self.continuation_id}:
            raise ValueError("superseded package identity must be distinct")
        if self.next_task_id == self.source_task_id:
            raise ValueError("next Task must differ from the source Task")
        if self.next_task_index >= self.task_count:
            raise ValueError("instruction package next Task index is outside the queue")

        lineage = self.source_authority_lineage
        if (
            self.source_completion_evidence_id
            != lineage.source_completion_evidence_id
            or self.source_completion_evidence_fingerprint
            != lineage.source_completion_evidence_fingerprint
            or self.source_execution_authority_kind
            != lineage.source_execution_authority_kind
            or self.source_execution_authority_id
            != lineage.source_execution_authority_id
            or self.source_execution_authority_fingerprint
            != lineage.source_execution_authority_fingerprint
            or self.source_worker_start_reservation_id
            != lineage.source_reservation_id
            or self.source_worker_invocation_claim_id != lineage.source_claim_id
            or self.source_worker_invocation_outcome_id
            != lineage.source_outcome_id
            or self.source_worker_outcome_schema_version
            != lineage.source_outcome_schema_version
            or self.source_worker_outcome_fingerprint
            != lineage.source_outcome_fingerprint
            or self.source_review_id != lineage.source_review_id
            or self.source_review_outcome != lineage.source_review_outcome
            or self.source_transition_evidence_ids
            != lineage.source_transition_evidence_ids
            or self.completion_policy_id != lineage.completion_policy_id
            or self.completion_policy_version != lineage.completion_policy_version
            or self.completion_policy_fingerprint
            != lineage.completion_policy_fingerprint
            or self.review_requirement
            != lineage.completion_review_requirement
        ):
            raise ValueError("instruction package source authority aliases conflict")

        skill_codes = tuple(item.skill_code for item in self.selected_skills)
        skill_names = tuple(item.skill_name for item in self.selected_skills)
        if (
            self.owner_role_code != self.selected_strategy.owner_role_code
            or self.selected_model.model_name
            != self.selected_strategy.strategy_decision.model_name
            or self.selected_model.model_tier
            != self.selected_strategy.strategy_decision.model_tier
            or skill_codes
            != self.selected_strategy.strategy_decision.selected_skill_codes
            or skill_names
            != self.selected_strategy.strategy_decision.selected_skill_names
            or self.repository_binding.focus_paths != self.allowed_paths
        ):
            raise ValueError("instruction package Candidate semantics conflict")

        if (
            not self.forbidden_actions
            or len(self.forbidden_actions) != len(set(self.forbidden_actions))
            or any(
                not action.strip() or action != action.strip()
                for action in self.forbidden_actions
            )
            or not _REQUIRED_FORBIDDEN_ACTIONS.issubset(self.forbidden_actions)
        ):
            raise ValueError("instruction package forbidden actions are incomplete")
        if self.package_replay_key != self.compute_package_replay_key(
            continuation_id=self.continuation_id,
            source_completion_evidence_id=self.source_completion_evidence_id,
            next_task_id=self.next_task_id,
        ):
            raise ValueError("instruction package replay key does not match")
        if self.package_fingerprint != self.compute_fingerprint():
            raise ValueError("instruction package fingerprint does not match")
        return self

    @staticmethod
    def compute_package_replay_key(
        *,
        continuation_id: UUID,
        source_completion_evidence_id: UUID,
        next_task_id: UUID,
    ) -> str:
        return compute_p24_contract_sha256(
            {
                "schema_version": (
                    NEXT_TASK_INSTRUCTION_PACKAGE_REPLAY_SCHEMA_VERSION
                ),
                "action": NEXT_TASK_INSTRUCTION_PACKAGE_ACTION,
                "continuation_id": continuation_id,
                "source_completion_evidence_id": (
                    source_completion_evidence_id
                ),
                "next_task_id": next_task_id,
            }
        )

    def compute_fingerprint(self) -> str:
        return compute_p24_contract_sha256(
            self.model_dump(mode="python", exclude={"package_fingerprint"})
        )


__all__ = (
    "NEXT_TASK_INSTRUCTION_PACKAGE_ACTION",
    "NEXT_TASK_INSTRUCTION_PACKAGE_REPLAY_SCHEMA_VERSION",
    "NEXT_TASK_INSTRUCTION_PACKAGE_SCHEMA_VERSION",
    "ProjectDirectorNextTaskInstructionPackage",
    "canonicalize_p24_contract_value",
    "compute_p24_contract_sha256",
)
