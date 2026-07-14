"""Shared immutable primitives for the P25 bounded rework contracts."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain._base import DomainModel


P25_BOUNDED_REWORK_SCHEMA_VERSION = "p25-b.v1"
P25_BOUNDED_REWORK_ATTEMPT_LIMIT = 3

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_LOWER_HEX_GIT_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_URI_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_SHELL_FRAGMENT = re.compile(r"[;&|`$<>\n\r]")
_INTERNAL_CONTROL_NAMES = frozenset(
    {
        ".git",
        ".ai-dev-orchestrator",
        ".orchestrator",
        "workspace-manifest.json",
        "workspace_manifest.json",
    }
)


BoundedReworkBlockedReason: TypeAlias = Literal[
    "history_invalid",
    "authority_invalid",
    "authority_replayed",
    "scope_invalid",
    "workspace_invalid",
    "base_commit_mismatch",
    "source_diff_mismatch",
    "review_findings_invalid",
    "instruction_package_conflict",
    "attempt_limit_exhausted",
    "non_convergence",
    "claim_without_outcome",
    "execution_result_invalid",
    "git_boundary_violation",
    "persistence_failed",
    "review_reentry_failed",
    "human_escalation_required",
]


def canonicalize_p25_contract_value(value: Any) -> Any:
    """Convert P25 values to a stable JSON-compatible representation."""

    if isinstance(value, BaseModel):
        return canonicalize_p25_contract_value(value.model_dump(mode="python"))
    if isinstance(value, dict):
        return {
            str(key): canonicalize_p25_contract_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [canonicalize_p25_contract_value(item) for item in value]
    if isinstance(value, UUID):
        return str(value).lower()
    if isinstance(value, Enum):
        return canonicalize_p25_contract_value(value.value)
    if isinstance(value, datetime):
        normalized = value
        if normalized.tzinfo is None or normalized.utcoffset() is None:
            normalized = normalized.replace(tzinfo=timezone.utc)
        return normalized.astimezone(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )
    return value


def compute_p25_contract_sha256(payload: dict[str, Any]) -> str:
    """Return lowercase SHA-256 for one canonical P25 payload."""

    canonical = json.dumps(
        canonicalize_p25_contract_value(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_utc_datetime(value: datetime, *, label: str) -> datetime:
    """Reject naive timestamps and normalize aware timestamps to UTC."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be UTC-aware")
    return value.astimezone(timezone.utc)


def require_sha256(value: str, *, label: str) -> str:
    if not _LOWER_HEX_SHA256.fullmatch(value):
        raise ValueError(f"{label} must be lowercase SHA-256")
    return value


def require_optional_sha256(value: str | None, *, label: str) -> str | None:
    if value is not None:
        require_sha256(value, label=label)
    return value


def require_git_commit(value: str, *, label: str) -> str:
    if not _LOWER_HEX_GIT_COMMIT.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase 40-character Git SHA")
    return value


def require_trimmed_text(value: str, *, label: str) -> str:
    if not value.strip() or value != value.strip():
        raise ValueError(f"{label} must be non-blank and trimmed")
    return value


def require_optional_trimmed_text(
    value: str | None,
    *,
    label: str,
) -> str | None:
    if value is not None:
        require_trimmed_text(value, label=label)
    return value


def validate_repository_relative_path(value: str) -> str:
    """Validate a canonical repository-relative POSIX contract path."""

    require_trimmed_text(value, label="scope path")
    if (
        value in {".", ".."}
        or value.startswith("/")
        or value.endswith("/")
        or "\\" in value
        or "//" in value
        or _URI_SCHEME.match(value)
        or _SHELL_FRAGMENT.search(value)
    ):
        raise ValueError("scope path must be canonical repository-relative POSIX")
    path = PurePosixPath(value)
    if path.as_posix() != value or any(
        part in {"", ".", ".."} or part in _INTERNAL_CONTROL_NAMES
        for part in path.parts
    ):
        raise ValueError("scope path contains traversal or control metadata")
    return value


def validate_unique_paths(values: tuple[str, ...], *, allow_empty: bool) -> tuple[str, ...]:
    if not allow_empty and not values:
        raise ValueError("prepared bounded rework scope must be non-empty")
    if len(values) != len(set(values)):
        raise ValueError("bounded rework scope paths must be unique")
    for value in values:
        validate_repository_relative_path(value)
    return values


def path_is_within_scope(path: str, scope_entry: str) -> bool:
    return path == scope_entry or path.startswith(f"{scope_entry}/")


def paths_overlap(left: str, right: str) -> bool:
    return path_is_within_scope(left, right) or path_is_within_scope(right, left)


class ProjectDirectorBoundedReworkAuthorityEnvelope(DomainModel):
    """Exact P22/P23 AUTO_REWORK authority accepted by P25."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: UUID
    project_id: UUID
    source_task_id: UUID
    target_task_id: UUID
    source_run_id: UUID

    source_review_message_id: UUID
    source_review_fingerprint: str = Field(min_length=64, max_length=64)
    source_review_semantic_fingerprint: str = Field(min_length=64, max_length=64)
    source_disposition_message_id: UUID
    source_p22_summary_message_id: UUID
    source_p23_dispatch_intent_id: UUID
    source_p23_dispatch_intent_fingerprint: str = Field(
        min_length=64,
        max_length=64,
    )
    source_p23_dispatch_consumption_id: UUID
    source_p23_dispatch_consumption_fingerprint: str = Field(
        min_length=64,
        max_length=64,
    )

    disposition_type: Literal["AUTO_REWORK"] = "AUTO_REWORK"
    route: Literal["bounded_automatic_rework"] = "bounded_automatic_rework"
    transition_kind: Literal["BOUNDED_REWORK_GUARDRAIL"] = (
        "BOUNDED_REWORK_GUARDRAIL"
    )
    transition_authority: Literal["AUTOMATED_DISPOSITION"] = (
        "AUTOMATED_DISPOSITION"
    )

    @field_validator(
        "source_review_fingerprint",
        "source_review_semantic_fingerprint",
        "source_p23_dispatch_intent_fingerprint",
        "source_p23_dispatch_consumption_fingerprint",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return require_sha256(value, label="bounded rework authority fingerprint")

    @model_validator(mode="after")
    def validate_authority(self) -> "ProjectDirectorBoundedReworkAuthorityEnvelope":
        if self.target_task_id != self.source_task_id:
            raise ValueError("bounded rework target Task must equal source Task")
        identities = (
            self.session_id,
            self.project_id,
            self.source_task_id,
            self.source_run_id,
            self.source_review_message_id,
            self.source_disposition_message_id,
            self.source_p22_summary_message_id,
            self.source_p23_dispatch_intent_id,
            self.source_p23_dispatch_consumption_id,
        )
        if len(identities) != len(set(identities)):
            raise ValueError("bounded rework authority identities must be distinct")
        return self


class ProjectDirectorBoundedReworkFinding(DomainModel):
    """One blocking readonly-review finding bound to scoped evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str = Field(min_length=1, max_length=80)
    severity: Literal["medium", "high"]
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=1_000)
    evidence_paths: tuple[str, ...] = Field(min_length=1, max_length=12)
    recommended_action: str = Field(min_length=1, max_length=500)

    @field_validator("finding_id", "title", "summary", "recommended_action")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return require_trimmed_text(value, label="bounded rework finding text")

    @field_validator("evidence_paths")
    @classmethod
    def validate_paths(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return validate_unique_paths(values, allow_empty=False)


class ProjectDirectorBoundedReworkCorrection(DomainModel):
    """One executable correction linked to a blocking finding identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    correction_id: str = Field(min_length=1, max_length=80)
    source_finding_id: str = Field(min_length=1, max_length=80)
    instruction: str = Field(min_length=1, max_length=1_000)

    @field_validator("correction_id", "source_finding_id", "instruction")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return require_trimmed_text(value, label="bounded rework correction text")


class ProjectDirectorBoundedReworkVerificationRequirement(DomainModel):
    """One immutable verification requirement from confirmed task evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requirement_id: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=1_000)

    @field_validator("requirement_id", "description")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return require_trimmed_text(value, label="verification requirement")


class ProjectDirectorBoundedReworkRepositoryBinding(DomainModel):
    """Confirmed repository identity without any write authority."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_binding_id: UUID
    project_id: UUID
    repository_root: str = Field(min_length=1, max_length=2_000)
    repository_binding_fingerprint: str = Field(min_length=64, max_length=64)

    @field_validator("repository_root")
    @classmethod
    def validate_root(cls, value: str) -> str:
        require_trimmed_text(value, label="repository root")
        if not value.startswith("/") or "\\" in value or value.endswith("/"):
            raise ValueError("repository root must be a canonical absolute POSIX path")
        return value

    @field_validator("repository_binding_fingerprint")
    @classmethod
    def validate_fingerprint(cls, value: str) -> str:
        return require_sha256(value, label="repository binding fingerprint")


class ProjectDirectorBoundedReworkWorkspaceBinding(DomainModel):
    """Confirmed sandbox workspace identity bound to one project."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_binding_id: UUID
    project_id: UUID
    workspace_path: str = Field(min_length=1, max_length=2_000)
    workspace_root: str = Field(min_length=1, max_length=2_000)
    workspace_binding_fingerprint: str = Field(min_length=64, max_length=64)

    @field_validator("workspace_path", "workspace_root")
    @classmethod
    def validate_workspace_paths(cls, value: str) -> str:
        require_trimmed_text(value, label="workspace path")
        if not value.startswith("/") or "\\" in value or value.endswith("/"):
            raise ValueError("workspace paths must be canonical absolute POSIX paths")
        return value

    @field_validator("workspace_binding_fingerprint")
    @classmethod
    def validate_fingerprint(cls, value: str) -> str:
        return require_sha256(value, label="workspace binding fingerprint")

    @model_validator(mode="after")
    def validate_containment(self) -> "ProjectDirectorBoundedReworkWorkspaceBinding":
        if not self.workspace_path.startswith(f"{self.workspace_root}/"):
            raise ValueError("workspace must be a strict child of workspace root")
        return self


class ProjectDirectorBoundedReworkModelSelection(DomainModel):
    """Selected executor model identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_name: str = Field(min_length=1, max_length=120)
    model_tier: str = Field(min_length=1, max_length=80)

    @field_validator("model_name", "model_tier")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return require_trimmed_text(value, label="selected model")


class ProjectDirectorBoundedReworkSkillSelection(DomainModel):
    """Selected Skill identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    skill_code: str = Field(min_length=1, max_length=120)
    skill_name: str = Field(min_length=1, max_length=200)

    @field_validator("skill_code", "skill_name")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return require_trimmed_text(value, label="selected Skill")


class ProjectDirectorBoundedReworkRoleSelection(DomainModel):
    """Selected owner-role identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role_code: str = Field(min_length=1, max_length=120)

    @field_validator("role_code")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return require_trimmed_text(value, label="selected role")


def validate_skill_selections(
    values: tuple[ProjectDirectorBoundedReworkSkillSelection, ...],
) -> tuple[ProjectDirectorBoundedReworkSkillSelection, ...]:
    if not values:
        raise ValueError("bounded rework requires at least one selected Skill")
    codes = tuple(item.skill_code for item in values)
    names = tuple(item.skill_name for item in values)
    if len(codes) != len(set(codes)) or len(names) != len(set(names)):
        raise ValueError("bounded rework selected Skills must be unique")
    return values


__all__ = (
    "BoundedReworkBlockedReason",
    "P25_BOUNDED_REWORK_ATTEMPT_LIMIT",
    "P25_BOUNDED_REWORK_SCHEMA_VERSION",
    "ProjectDirectorBoundedReworkAuthorityEnvelope",
    "ProjectDirectorBoundedReworkCorrection",
    "ProjectDirectorBoundedReworkFinding",
    "ProjectDirectorBoundedReworkModelSelection",
    "ProjectDirectorBoundedReworkRepositoryBinding",
    "ProjectDirectorBoundedReworkRoleSelection",
    "ProjectDirectorBoundedReworkSkillSelection",
    "ProjectDirectorBoundedReworkVerificationRequirement",
    "ProjectDirectorBoundedReworkWorkspaceBinding",
    "canonicalize_p25_contract_value",
    "compute_p25_contract_sha256",
    "normalize_utc_datetime",
    "path_is_within_scope",
    "paths_overlap",
    "require_git_commit",
    "require_optional_sha256",
    "require_optional_trimmed_text",
    "require_sha256",
    "require_trimmed_text",
    "validate_repository_relative_path",
    "validate_skill_selections",
    "validate_unique_paths",
)
