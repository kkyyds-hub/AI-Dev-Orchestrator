"""P25-specific boundary for one bounded sandbox rework invocation."""

from __future__ import annotations

import re
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.project_director_bounded_rework_contract import (
    ProjectDirectorBoundedReworkModelSelection,
    ProjectDirectorBoundedReworkRoleSelection,
    ProjectDirectorBoundedReworkSkillSelection,
    validate_absolute_posix_path,
    validate_repository_relative_path,
    validate_unique_paths,
)


_SENSITIVE_TEXT_PATTERN = re.compile(
    r"(?i)(authorization\s*:|api[_ -]?key\s*[:=]|token\s*[:=]|"
    r"secret\s*[:=]|password\s*[:=]|bearer\s+|sk-[a-z0-9]|"
    r"stdout\s*:|stderr\s*:|prompt\s*:|environment\s*:|env\s*:|"
    r"command\s*:)"
)


class _BoundedReworkExecutorContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ProjectDirectorBoundedReworkExecutorFinding(_BoundedReworkExecutorContract):
    finding_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    evidence_paths: tuple[str, ...]

    @field_validator("evidence_paths", mode="before")
    @classmethod
    def normalize_evidence_paths(cls, values: Any) -> Any:
        return _normalize_paths(values)

    @field_validator("evidence_paths")
    @classmethod
    def validate_evidence_paths(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return validate_unique_paths(values, allow_empty=False)


class ProjectDirectorBoundedReworkExecutorCorrection(_BoundedReworkExecutorContract):
    correction_id: str = Field(min_length=1, max_length=80)
    source_finding_id: str = Field(min_length=1, max_length=80)
    instruction: str = Field(min_length=1, max_length=1_000)


class ProjectDirectorBoundedReworkExecutorVerificationRequirement(
    _BoundedReworkExecutorContract
):
    requirement_id: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=1_000)


def _normalize_paths(values: Any) -> Any:
    if not isinstance(values, (list, tuple)):
        return values
    normalized = tuple(sorted(set(values)))
    for value in normalized:
        validate_repository_relative_path(value)
    return normalized


class ProjectDirectorBoundedReworkExecutorRequest(_BoundedReworkExecutorContract):
    """Redacted projection of one exact persisted package and Claim."""

    request_id: UUID
    executor_adapter_kind: str = Field(min_length=1, max_length=120)
    workspace_path: str = Field(min_length=1, max_length=2_000)

    allowed_scope_paths: tuple[str, ...]
    forbidden_scope_paths: tuple[str, ...] = ()
    blocking_findings: tuple[ProjectDirectorBoundedReworkExecutorFinding, ...]
    required_corrections: tuple[ProjectDirectorBoundedReworkExecutorCorrection, ...]
    confirmed_acceptance_criteria: tuple[str, ...]
    verification_requirements: tuple[
        ProjectDirectorBoundedReworkExecutorVerificationRequirement,
        ...,
    ]

    selected_model: ProjectDirectorBoundedReworkModelSelection
    selected_skills: tuple[ProjectDirectorBoundedReworkSkillSelection, ...]
    selected_role: ProjectDirectorBoundedReworkRoleSelection
    rework_attempt_index: int = Field(ge=0, lt=3)
    rework_attempt_limit: Literal[3] = 3

    product_runtime_git_write_allowed: Literal[False] = False
    main_project_write_allowed: Literal[False] = False

    @field_validator("executor_adapter_kind")
    @classmethod
    def validate_adapter_kind(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("executor adapter kind must be trimmed")
        return value

    @field_validator("workspace_path")
    @classmethod
    def validate_workspace_path(cls, value: str) -> str:
        return validate_absolute_posix_path(value)

    @field_validator("allowed_scope_paths", "forbidden_scope_paths", mode="before")
    @classmethod
    def normalize_scope_paths(cls, values: Any) -> Any:
        return _normalize_paths(values)

    @field_validator("allowed_scope_paths")
    @classmethod
    def validate_allowed_scope_paths(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return validate_unique_paths(values, allow_empty=False)

    @field_validator("forbidden_scope_paths")
    @classmethod
    def validate_forbidden_scope_paths(
        cls,
        values: tuple[str, ...],
    ) -> tuple[str, ...]:
        return validate_unique_paths(values, allow_empty=True)


class ProjectDirectorBoundedReworkExecutorResult(_BoundedReworkExecutorContract):
    """Safe adapter declaration; the coordinator independently verifies it."""

    result_status: Literal["returned"] = "returned"
    declared_changed_paths: tuple[str, ...] = ()
    safe_summary: str = Field(min_length=1, max_length=1_000)

    git_add: bool = False
    git_commit: bool = False
    git_push: bool = False
    branch_create: bool = False
    branch_delete: bool = False
    checkout: bool = False
    switch: bool = False
    reset: bool = False
    stash: bool = False
    rebase: bool = False
    tag: bool = False
    pull_request: bool = False
    merge: bool = False
    ci_trigger: bool = False
    main_project_write: bool = False
    workspace_escape: bool = False

    @field_validator("declared_changed_paths", mode="before")
    @classmethod
    def normalize_declared_paths(cls, values: Any) -> Any:
        return _normalize_paths(values)

    @field_validator("declared_changed_paths")
    @classmethod
    def validate_declared_paths(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return validate_unique_paths(values, allow_empty=True)

    @field_validator("safe_summary")
    @classmethod
    def validate_safe_summary(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("safe summary must be trimmed")
        if _SENSITIVE_TEXT_PATTERN.search(value):
            raise ValueError("safe summary contains suspected sensitive material")
        return value


@runtime_checkable
class ProjectDirectorBoundedReworkExecutorProtocol(Protocol):
    def execute_bounded_rework(
        self,
        request: ProjectDirectorBoundedReworkExecutorRequest,
    ) -> ProjectDirectorBoundedReworkExecutorResult: ...


__all__ = (
    "ProjectDirectorBoundedReworkExecutorCorrection",
    "ProjectDirectorBoundedReworkExecutorFinding",
    "ProjectDirectorBoundedReworkExecutorProtocol",
    "ProjectDirectorBoundedReworkExecutorRequest",
    "ProjectDirectorBoundedReworkExecutorResult",
    "ProjectDirectorBoundedReworkExecutorVerificationRequirement",
)
