"""Immutable P25-B bounded rework instruction package contract."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domain._base import DomainModel
from app.domain.project_director_bounded_rework_contract import (
    BoundedReworkBlockedReason,
    P25_BOUNDED_REWORK_ATTEMPT_LIMIT,
    P25_BOUNDED_REWORK_SCHEMA_VERSION,
    ProjectDirectorBoundedReworkAuthorityEnvelope,
    ProjectDirectorBoundedReworkCorrection,
    ProjectDirectorBoundedReworkFinding,
    ProjectDirectorBoundedReworkModelSelection,
    ProjectDirectorBoundedReworkRepositoryBinding,
    ProjectDirectorBoundedReworkRoleSelection,
    ProjectDirectorBoundedReworkSkillSelection,
    ProjectDirectorBoundedReworkVerificationRequirement,
    ProjectDirectorBoundedReworkWorkspaceBinding,
    compute_p25_contract_sha256,
    normalize_utc_datetime,
    path_is_within_scope,
    paths_overlap,
    require_git_commit,
    require_optional_sha256,
    require_optional_trimmed_text,
    require_sha256,
    require_trimmed_text,
    validate_skill_selections,
    validate_unique_paths,
)


BoundedReworkInstructionPackageStatus = Literal["prepared", "blocked"]


class ProjectDirectorBoundedReworkInstructionPackage(DomainModel):
    """A prepared immutable instruction or a fail-closed blocked result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["p25-b.v1"] = P25_BOUNDED_REWORK_SCHEMA_VERSION
    package_id: UUID
    package_status: BoundedReworkInstructionPackageStatus
    package_fingerprint: str = Field(min_length=64, max_length=64)
    package_replay_key: str | None = Field(default=None, min_length=64, max_length=64)
    created_at: datetime

    authority: ProjectDirectorBoundedReworkAuthorityEnvelope | None = None
    review_verdict: Literal["changes_required"] | None = None
    review_risk_level: Literal["low", "medium", "high"] | None = None
    review_summary: str | None = Field(default=None, max_length=2_000)
    blocking_findings: tuple[ProjectDirectorBoundedReworkFinding, ...] = ()
    required_corrections: tuple[ProjectDirectorBoundedReworkCorrection, ...] = ()
    recommended_next_step_context: str | None = Field(default=None, max_length=1_000)

    confirmed_acceptance_criteria: tuple[str, ...] = ()
    verification_requirements: tuple[
        ProjectDirectorBoundedReworkVerificationRequirement,
        ...,
    ] = ()
    allowed_scope_paths: tuple[str, ...] = ()
    forbidden_scope_paths: tuple[str, ...] = ()

    repository_binding: ProjectDirectorBoundedReworkRepositoryBinding | None = None
    workspace_binding: ProjectDirectorBoundedReworkWorkspaceBinding | None = None
    base_commit_sha: str | None = Field(default=None, min_length=40, max_length=40)
    base_snapshot_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )
    source_candidate_diff_message_id: UUID | None = None
    source_candidate_diff_sha256: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )
    source_candidate_diff_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )

    selected_model: ProjectDirectorBoundedReworkModelSelection | None = None
    selected_skills: tuple[ProjectDirectorBoundedReworkSkillSelection, ...] = ()
    selected_role: ProjectDirectorBoundedReworkRoleSelection | None = None

    rework_attempt_index: int | None = Field(default=None, ge=0, lt=3)
    rework_attempt_limit: int | None = None
    previous_attempt_id: UUID | None = None
    previous_outcome_id: UUID | None = None
    previous_rework_attempt_index: int | None = Field(default=None, ge=0, lt=2)
    previous_candidate_diff_sha256: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )
    previous_review_semantic_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )
    non_convergence_evidence: tuple[str, ...] = ()

    blocked_reasons: tuple[BoundedReworkBlockedReason, ...] = ()
    blocked_summary: str | None = Field(default=None, max_length=1_000)

    product_runtime_git_write_allowed: Literal[False] = False
    main_project_write_allowed: Literal[False] = False
    automatic_pr_allowed: Literal[False] = False
    automatic_merge_allowed: Literal[False] = False
    git_add_allowed: Literal[False] = False
    git_commit_allowed: Literal[False] = False
    git_push_allowed: Literal[False] = False
    branch_operation_allowed: Literal[False] = False
    ci_trigger_allowed: Literal[False] = False

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return normalize_utc_datetime(value, label="bounded rework package created_at")

    @field_validator("package_fingerprint")
    @classmethod
    def validate_package_fingerprint(cls, value: str) -> str:
        return require_sha256(value, label="bounded rework package fingerprint")

    @field_validator("package_replay_key")
    @classmethod
    def validate_package_replay_key(cls, value: str | None) -> str | None:
        return require_optional_sha256(value, label="bounded rework package replay key")

    @field_validator(
        "base_snapshot_fingerprint",
        "source_candidate_diff_sha256",
        "source_candidate_diff_fingerprint",
        "previous_candidate_diff_sha256",
        "previous_review_semantic_fingerprint",
    )
    @classmethod
    def validate_optional_hashes(cls, value: str | None) -> str | None:
        return require_optional_sha256(value, label="bounded rework package hash")

    @field_validator("base_commit_sha")
    @classmethod
    def validate_base_commit(cls, value: str | None) -> str | None:
        if value is not None:
            require_git_commit(value, label="bounded rework base commit")
        return value

    @field_validator(
        "review_summary",
        "recommended_next_step_context",
        "blocked_summary",
    )
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return require_optional_trimmed_text(value, label="bounded rework package text")

    @field_validator("confirmed_acceptance_criteria", "non_convergence_evidence")
    @classmethod
    def validate_text_collections(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("bounded rework package text collections must be unique")
        for value in values:
            require_trimmed_text(value, label="bounded rework package collection item")
        return values

    @field_validator("allowed_scope_paths")
    @classmethod
    def validate_allowed_paths(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return validate_unique_paths(values, allow_empty=True)

    @field_validator("forbidden_scope_paths")
    @classmethod
    def validate_forbidden_paths(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return validate_unique_paths(values, allow_empty=True)

    @field_validator("selected_skills")
    @classmethod
    def validate_skills(
        cls,
        values: tuple[ProjectDirectorBoundedReworkSkillSelection, ...],
    ) -> tuple[ProjectDirectorBoundedReworkSkillSelection, ...]:
        if values:
            return validate_skill_selections(values)
        return values

    @model_validator(mode="after")
    def validate_package(self) -> "ProjectDirectorBoundedReworkInstructionPackage":
        if self.package_status == "prepared":
            self._validate_prepared()
        else:
            self._validate_blocked()
        if self.package_fingerprint != self.compute_fingerprint():
            raise ValueError("bounded rework package fingerprint does not match")
        return self

    def _validate_prepared(self) -> None:
        required = (
            self.package_replay_key,
            self.authority,
            self.review_verdict,
            self.review_risk_level,
            self.review_summary,
            self.repository_binding,
            self.workspace_binding,
            self.base_commit_sha,
            self.base_snapshot_fingerprint,
            self.source_candidate_diff_message_id,
            self.source_candidate_diff_sha256,
            self.source_candidate_diff_fingerprint,
            self.selected_model,
            self.selected_role,
            self.rework_attempt_index,
            self.rework_attempt_limit,
        )
        if any(value is None for value in required):
            raise ValueError("prepared bounded rework package requires full authority")
        if self.blocked_reasons or self.blocked_summary is not None:
            raise ValueError("prepared bounded rework package cannot be blocked")
        if not self.blocking_findings or not self.required_corrections:
            raise ValueError("prepared AUTO_REWORK package requires blocking findings")
        if not self.confirmed_acceptance_criteria or not self.verification_requirements:
            raise ValueError("prepared bounded rework package requires confirmed checks")
        validate_unique_paths(self.allowed_scope_paths, allow_empty=False)
        validate_skill_selections(self.selected_skills)

        assert self.authority is not None
        assert self.repository_binding is not None
        assert self.workspace_binding is not None
        assert self.source_candidate_diff_message_id is not None
        assert self.source_candidate_diff_sha256 is not None
        assert self.base_commit_sha is not None
        assert self.rework_attempt_index is not None
        if (
            self.repository_binding.project_id != self.authority.project_id
            or self.workspace_binding.project_id != self.authority.project_id
        ):
            raise ValueError("repository/workspace project aliases conflict")
        binding_ids = {
            self.repository_binding.repository_binding_id,
            self.workspace_binding.workspace_binding_id,
            self.source_candidate_diff_message_id,
        }
        authority_ids = {
            self.authority.session_id,
            self.authority.project_id,
            self.authority.source_task_id,
            self.authority.source_run_id,
            self.authority.source_review_message_id,
            self.authority.source_disposition_message_id,
            self.authority.source_p22_summary_message_id,
            self.authority.source_p23_dispatch_intent_id,
            self.authority.source_p23_dispatch_consumption_id,
        }
        if len(binding_ids) != 3 or binding_ids & authority_ids:
            raise ValueError("bounded rework package identities must be distinct")

        for allowed in self.allowed_scope_paths:
            if any(paths_overlap(allowed, forbidden) for forbidden in self.forbidden_scope_paths):
                raise ValueError("forbidden scope cannot be covered by allowed scope")

        finding_ids = tuple(item.finding_id for item in self.blocking_findings)
        correction_ids = tuple(item.correction_id for item in self.required_corrections)
        correction_sources = tuple(
            item.source_finding_id for item in self.required_corrections
        )
        if (
            len(finding_ids) != len(set(finding_ids))
            or len(correction_ids) != len(set(correction_ids))
            or len(correction_sources) != len(set(correction_sources))
            or set(correction_sources) != set(finding_ids)
        ):
            raise ValueError("every correction must bind one unique blocking finding")
        severity_rank = {"medium": 1, "high": 2}
        highest_finding_risk = max(
            self.blocking_findings,
            key=lambda finding: severity_rank[finding.severity],
        ).severity
        if self.review_risk_level != highest_finding_risk:
            raise ValueError("review risk must match the highest blocking finding")
        for finding in self.blocking_findings:
            if any(
                not any(
                    path_is_within_scope(evidence_path, allowed_path)
                    for allowed_path in self.allowed_scope_paths
                )
                for evidence_path in finding.evidence_paths
            ):
                raise ValueError("finding evidence must remain inside allowed scope")

        requirement_ids = tuple(
            item.requirement_id for item in self.verification_requirements
        )
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("verification requirement identities must be unique")
        if self.rework_attempt_limit != P25_BOUNDED_REWORK_ATTEMPT_LIMIT:
            raise ValueError("bounded rework attempt limit must equal three")
        previous = (
            self.previous_attempt_id,
            self.previous_outcome_id,
            self.previous_rework_attempt_index,
            self.previous_candidate_diff_sha256,
            self.previous_review_semantic_fingerprint,
        )
        if self.rework_attempt_index == 0 and any(value is not None for value in previous):
            raise ValueError("initial bounded rework attempt cannot forge prior lineage")
        if self.rework_attempt_index > 0 and any(value is None for value in previous):
            raise ValueError("later bounded rework attempts require complete prior lineage")
        if self.rework_attempt_index > 0 and (
            self.previous_rework_attempt_index != self.rework_attempt_index - 1
            or self.previous_attempt_id == self.previous_outcome_id
            or self.previous_attempt_id in binding_ids | authority_ids | {self.package_id}
            or self.previous_outcome_id in binding_ids | authority_ids | {self.package_id}
        ):
            raise ValueError("previous attempt lineage conflicts with current attempt")
        if self.package_replay_key != self.compute_package_replay_key(
            authority=self.authority,
            source_candidate_diff_sha256=self.source_candidate_diff_sha256,
            repository_binding_fingerprint=(
                self.repository_binding.repository_binding_fingerprint
            ),
            workspace_binding_fingerprint=(
                self.workspace_binding.workspace_binding_fingerprint
            ),
            base_commit_sha=self.base_commit_sha,
            rework_attempt_index=self.rework_attempt_index,
        ):
            raise ValueError("bounded rework package replay key does not match")

    def _validate_blocked(self) -> None:
        if (
            not self.blocked_reasons
            or len(self.blocked_reasons) != len(set(self.blocked_reasons))
            or self.blocked_summary is None
        ):
            raise ValueError("blocked bounded rework package requires stable reasons")
        executable_values = (
            self.package_replay_key,
            self.authority,
            self.review_verdict,
            self.review_risk_level,
            self.review_summary,
            self.recommended_next_step_context,
            self.repository_binding,
            self.workspace_binding,
            self.base_commit_sha,
            self.base_snapshot_fingerprint,
            self.source_candidate_diff_message_id,
            self.source_candidate_diff_sha256,
            self.source_candidate_diff_fingerprint,
            self.selected_model,
            self.selected_role,
            self.rework_attempt_index,
            self.rework_attempt_limit,
            self.previous_attempt_id,
            self.previous_outcome_id,
            self.previous_rework_attempt_index,
            self.previous_candidate_diff_sha256,
            self.previous_review_semantic_fingerprint,
        )
        executable_collections = (
            self.blocking_findings,
            self.required_corrections,
            self.confirmed_acceptance_criteria,
            self.verification_requirements,
            self.allowed_scope_paths,
            self.forbidden_scope_paths,
            self.selected_skills,
            self.non_convergence_evidence,
        )
        if any(value is not None for value in executable_values) or any(
            executable_collections
        ):
            raise ValueError("blocked package cannot contain executable authority")

    @staticmethod
    def compute_package_replay_key(
        *,
        authority: ProjectDirectorBoundedReworkAuthorityEnvelope,
        source_candidate_diff_sha256: str,
        repository_binding_fingerprint: str,
        workspace_binding_fingerprint: str,
        base_commit_sha: str,
        rework_attempt_index: int,
    ) -> str:
        return compute_p25_contract_sha256(
            {
                "schema_version": P25_BOUNDED_REWORK_SCHEMA_VERSION,
                "source_p23_dispatch_consumption_id": (
                    authority.source_p23_dispatch_consumption_id
                ),
                "source_p23_dispatch_consumption_fingerprint": (
                    authority.source_p23_dispatch_consumption_fingerprint
                ),
                "source_review_semantic_fingerprint": (
                    authority.source_review_semantic_fingerprint
                ),
                "source_candidate_diff_sha256": source_candidate_diff_sha256,
                "repository_binding_fingerprint": repository_binding_fingerprint,
                "workspace_binding_fingerprint": workspace_binding_fingerprint,
                "base_commit_sha": base_commit_sha,
                "rework_attempt_index": rework_attempt_index,
            }
        )

    def compute_fingerprint(self) -> str:
        return compute_p25_contract_sha256(
            self.model_dump(
                mode="python",
                exclude={"package_id", "created_at", "package_fingerprint"},
            )
        )


__all__ = (
    "BoundedReworkInstructionPackageStatus",
    "ProjectDirectorBoundedReworkInstructionPackage",
)
