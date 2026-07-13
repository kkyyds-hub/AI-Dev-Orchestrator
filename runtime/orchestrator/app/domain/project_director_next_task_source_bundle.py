"""Immutable P24-D1 authoritative source bundle contracts."""

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
from app.domain.project_director_confirmed_plan_queue import (
    ProjectDirectorConfirmedPlanQueueSnapshot,
)
from app.domain.project_role import ProjectRoleCode
from app.domain.repository_workspace import RepositoryAccessMode
from app.domain.task import TaskPriority, TaskRiskLevel


NEXT_TASK_SOURCE_BUNDLE_SCHEMA_VERSION = "p24-d-next-task-source-bundle.v1"

NextTaskSourceBundleResolutionStatus = Literal[
    "source_bundle_resolved",
    "plan_queue_exhausted",
    "blocked",
]
NextTaskSourceBundleBlockedReason = Literal[
    "next_task_queue_invalid",
    "next_task_plan_source_invalid",
    "next_task_plan_source_conflict",
    "next_task_plan_task_mismatch",
    "next_task_agent_team_config_missing",
    "next_task_agent_team_config_conflict",
    "next_task_agent_team_config_invalid",
    "next_task_agent_team_config_not_confirmed",
    "next_task_skill_config_missing",
    "next_task_skill_config_conflict",
    "next_task_skill_config_invalid",
    "next_task_skill_config_not_confirmed",
    "next_task_repository_config_missing",
    "next_task_repository_config_conflict",
    "next_task_repository_config_invalid",
    "next_task_repository_config_not_confirmed",
    "next_task_verification_config_missing",
    "next_task_verification_config_conflict",
    "next_task_verification_config_invalid",
    "next_task_verification_config_not_confirmed",
    "next_task_owner_role_unconfirmed",
    "next_task_workspace_missing",
    "next_task_workspace_conflict",
    "next_task_workspace_invalid",
    "next_task_source_bundle_invalid",
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class _FrozenSnapshot(DomainModel):
    model_config = ConfigDict(frozen=True)


class _ConfirmedConfigSnapshot(_FrozenSnapshot):
    status: Literal["confirmed"]
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime
    rejected_at: None = None

    @model_validator(mode="after")
    def validate_confirmation_timeline(self) -> "_ConfirmedConfigSnapshot":
        created_at = ensure_utc_datetime(self.created_at)
        updated_at = ensure_utc_datetime(self.updated_at)
        confirmed_at = ensure_utc_datetime(self.confirmed_at)
        if created_at is None or updated_at is None or confirmed_at is None:
            raise ValueError("confirmed config timestamps are required")
        if self.rejected_at is not None or not (
            created_at <= confirmed_at <= updated_at
        ):
            raise ValueError("confirmed config timeline is invalid")
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "updated_at", updated_at)
        object.__setattr__(self, "confirmed_at", confirmed_at)
        return self


class ProjectDirectorPlanScopeSnapshot(_FrozenSnapshot):
    in_scope: tuple[str, ...] = ()
    out_of_scope: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()


class ProjectDirectorDeliverableBoundarySnapshot(_FrozenSnapshot):
    name: str
    description: str
    owner_role_code: ProjectRoleCode
    required_contents: tuple[str, ...] = ()
    done_definition: str
    acceptance_signal: str


class ProjectDirectorAgentTeamMemberSnapshot(_FrozenSnapshot):
    role_code: str
    role_name: str
    responsibility: str
    collaboration_notes: tuple[str, ...] = ()
    review_status: str


class ProjectDirectorAgentTeamConfigSnapshot(_ConfirmedConfigSnapshot):
    id: UUID
    project_id: UUID
    plan_version_id: UUID
    source_draft_id: str
    agent_team: tuple[ProjectDirectorAgentTeamMemberSnapshot, ...]
    warnings: tuple[str, ...] = ()
    review_note: str


class ProjectDirectorSkillBindingSnapshot(_FrozenSnapshot):
    skill_code: str
    skill_name: str
    owner_role_code: str
    usage: str
    activation_stage: str
    binding_mode: str
    reason: str
    review_status: str


class ProjectDirectorSkillBindingConfigSnapshot(_ConfirmedConfigSnapshot):
    id: UUID
    project_id: UUID
    plan_version_id: UUID
    source_draft_id: str
    skill_bindings: tuple[ProjectDirectorSkillBindingSnapshot, ...]
    warnings: tuple[str, ...] = ()
    review_note: str


class ProjectDirectorRepositoryBindingSnapshot(_FrozenSnapshot):
    binding_type: str
    binding_mode: str
    target: str
    branch: str
    focus_paths: tuple[str, ...] = ()
    usage: str
    safety_note: str
    review_status: str


class ProjectDirectorRepositoryBindingConfigSnapshot(_ConfirmedConfigSnapshot):
    id: UUID
    project_id: UUID
    plan_version_id: UUID
    source_draft_id: str
    repository_bindings: tuple[ProjectDirectorRepositoryBindingSnapshot, ...]
    warnings: tuple[str, ...] = ()
    review_note: str


class ProjectDirectorVerificationMechanismSnapshot(_FrozenSnapshot):
    name: str
    command_or_method: str
    purpose: str
    evidence_required: str
    owner_role_code: str
    risk_level: str
    requires_user_confirmation: bool
    review_status: str


class ProjectDirectorVerificationConfigSnapshot(_ConfirmedConfigSnapshot):
    id: UUID
    project_id: UUID
    plan_version_id: UUID
    source_draft_id: str
    verification_mechanisms: tuple[
        ProjectDirectorVerificationMechanismSnapshot, ...
    ]
    warnings: tuple[str, ...] = ()
    review_note: str


class ProjectDirectorRepositoryWorkspaceSnapshot(_FrozenSnapshot):
    id: UUID
    project_id: UUID
    root_path: str
    display_name: str
    access_mode: RepositoryAccessMode
    default_base_branch: str
    ignore_rule_summary: tuple[str, ...] = ()
    allowed_workspace_root: str
    created_at: datetime
    updated_at: datetime


class ProjectDirectorNextTaskSourceBundle(_FrozenSnapshot):
    """All static persisted authority for one exact immediate next Task."""

    schema_version: Literal["p24-d-next-task-source-bundle.v1"] = (
        NEXT_TASK_SOURCE_BUNDLE_SCHEMA_VERSION
    )
    source_bundle_fingerprint: str = Field(min_length=64, max_length=64)

    source_completion_evidence_id: UUID
    source_completion_evidence_fingerprint: str = Field(min_length=64, max_length=64)
    queue_fingerprint: str = Field(min_length=64, max_length=64)

    session_id: UUID
    project_id: UUID
    plan_version_id: UUID
    plan_version_no: int = Field(ge=1)
    task_creation_record_id: UUID

    source_task_id: UUID
    source_run_id: UUID
    source_task_index: int = Field(ge=0)

    next_task_id: UUID
    next_task_index: int = Field(ge=0)
    task_count: int = Field(ge=1)

    next_task_title: str
    next_task_input_summary: str
    next_task_owner_role_code: ProjectRoleCode
    next_task_priority: TaskPriority
    next_task_risk_level: TaskRiskLevel
    next_task_dependency_ids: tuple[UUID, ...] = ()

    proposed_task_title: str
    proposed_task_description: str
    proposed_task_role_code: ProjectRoleCode
    proposed_task_priority_hint: str

    project_scope: ProjectDirectorPlanScopeSnapshot
    plan_acceptance_criteria: tuple[str, ...]
    plan_risks: tuple[str, ...]
    deliverable_boundaries: tuple[
        ProjectDirectorDeliverableBoundarySnapshot, ...
    ]

    agent_team_config: ProjectDirectorAgentTeamConfigSnapshot
    confirmed_owner_member: ProjectDirectorAgentTeamMemberSnapshot

    skill_binding_config: ProjectDirectorSkillBindingConfigSnapshot
    all_confirmed_skill_bindings: tuple[ProjectDirectorSkillBindingSnapshot, ...]
    owner_confirmed_skill_bindings: tuple[
        ProjectDirectorSkillBindingSnapshot, ...
    ]

    repository_binding_config: ProjectDirectorRepositoryBindingConfigSnapshot
    confirmed_repository_bindings: tuple[
        ProjectDirectorRepositoryBindingSnapshot, ...
    ]

    verification_config: ProjectDirectorVerificationConfigSnapshot
    all_verification_mechanisms: tuple[
        ProjectDirectorVerificationMechanismSnapshot, ...
    ]
    owner_role_verification_mechanisms: tuple[
        ProjectDirectorVerificationMechanismSnapshot, ...
    ]
    human_confirmation_mechanisms: tuple[
        ProjectDirectorVerificationMechanismSnapshot, ...
    ]

    repository_workspace: ProjectDirectorRepositoryWorkspaceSnapshot

    product_runtime_git_write_allowed: Literal[False] = False
    forbidden_actions: tuple[str, ...]

    @field_validator(
        "source_bundle_fingerprint",
        "source_completion_evidence_fingerprint",
        "queue_fingerprint",
    )
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _LOWER_HEX_SHA256.fullmatch(value):
            raise ValueError("source bundle hashes must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def validate_authority(self) -> "ProjectDirectorNextTaskSourceBundle":
        locator = f"pdv:{self.plan_version_id}:{self.plan_version_no}"
        if (
            self.next_task_index != self.source_task_index + 1
            or self.next_task_index >= self.task_count
        ):
            raise ValueError("next Task index is outside the confirmed queue")
        if (
            self.next_task_title != self.proposed_task_title
            or self.next_task_owner_role_code != self.proposed_task_role_code
        ):
            raise ValueError("next Task and indexed ProposedTask do not match")
        expected_priority = {
            "high": TaskPriority.HIGH,
            "urgent": TaskPriority.URGENT,
            "low": TaskPriority.LOW,
        }.get(self.proposed_task_priority_hint.lower(), TaskPriority.NORMAL)
        if self.next_task_priority != expected_priority:
            raise ValueError("next Task priority does not match ProposedTask mapping")
        configs = (
            self.agent_team_config,
            self.skill_binding_config,
            self.repository_binding_config,
            self.verification_config,
        )
        if any(
            config.project_id != self.project_id
            or config.plan_version_id != self.plan_version_id
            or config.source_draft_id != locator
            or config.status != "confirmed"
            for config in configs
        ):
            raise ValueError("confirmed config authority does not match the queue")
        owner_code = self.next_task_owner_role_code.value
        owner_members = tuple(
            member
            for member in self.agent_team_config.agent_team
            if member.role_code == owner_code
        )
        if (
            len(owner_members) != 1
            or owner_members[0] != self.confirmed_owner_member
            or not self.confirmed_owner_member.responsibility.strip()
        ):
            raise ValueError("next Task owner is not uniquely confirmed")
        if self.repository_workspace.project_id != self.project_id:
            raise ValueError("repository workspace project does not match")
        if (
            not self.forbidden_actions
            or len(self.forbidden_actions) != len(set(self.forbidden_actions))
        ):
            raise ValueError("source bundle forbidden actions must be unique")
        if self.source_bundle_fingerprint != self.compute_fingerprint():
            raise ValueError("source bundle fingerprint does not match its payload")
        return self

    def compute_fingerprint(self) -> str:
        payload = self.model_dump(
            mode="python",
            exclude={"source_bundle_fingerprint"},
        )
        canonical = json.dumps(
            self._canonicalize(payload),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def fingerprint_payload(cls, payload: dict[str, Any]) -> str:
        canonical = json.dumps(
            cls._canonicalize(payload),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
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
            normalized = normalized.astimezone(timezone.utc)
            return normalized.isoformat().replace("+00:00", "Z")
        return value


class ProjectDirectorNextTaskSourceBundleResolution(DomainModel):
    """Fail-closed result of one P24-D1 source authority resolution."""

    model_config = ConfigDict(frozen=True)

    status: NextTaskSourceBundleResolutionStatus
    queue_snapshot: ProjectDirectorConfirmedPlanQueueSnapshot | None = None
    source_bundle: ProjectDirectorNextTaskSourceBundle | None = None
    blocked_reasons: tuple[NextTaskSourceBundleBlockedReason, ...] = ()

    @model_validator(mode="after")
    def validate_resolution(
        self,
    ) -> "ProjectDirectorNextTaskSourceBundleResolution":
        if self.status == "source_bundle_resolved":
            if (
                self.queue_snapshot is None
                or self.queue_snapshot.queue_exhausted
                or self.source_bundle is None
                or self.blocked_reasons
            ):
                raise ValueError("resolved source bundle result is inconsistent")
            snapshot = self.queue_snapshot
            bundle = self.source_bundle
            if (
                bundle.source_completion_evidence_id
                != snapshot.source_completion_evidence_id
                or bundle.source_completion_evidence_fingerprint
                != snapshot.source_completion_evidence_fingerprint
                or bundle.queue_fingerprint != snapshot.queue_fingerprint
                or bundle.session_id != snapshot.session_id
                or bundle.project_id != snapshot.project_id
                or bundle.plan_version_id != snapshot.plan_version_id
                or bundle.plan_version_no != snapshot.plan_version_no
                or bundle.task_creation_record_id
                != snapshot.task_creation_record_id
                or bundle.source_task_id != snapshot.source_task_id
                or bundle.source_task_index != snapshot.source_task_index
                or bundle.next_task_id != snapshot.next_task_id
                or bundle.next_task_index != snapshot.next_task_index
                or bundle.task_count != snapshot.task_count
            ):
                raise ValueError("source bundle does not match its queue snapshot")
        elif self.status == "plan_queue_exhausted":
            if (
                self.queue_snapshot is None
                or not self.queue_snapshot.queue_exhausted
                or self.source_bundle is not None
                or self.blocked_reasons
            ):
                raise ValueError("exhausted source bundle result is inconsistent")
        elif (
            self.source_bundle is not None
            or not self.blocked_reasons
            or len(self.blocked_reasons) != len(set(self.blocked_reasons))
        ):
            raise ValueError("blocked source bundle result is inconsistent")
        return self

    @classmethod
    def blocked(
        cls,
        *reasons: NextTaskSourceBundleBlockedReason,
        queue_snapshot: ProjectDirectorConfirmedPlanQueueSnapshot | None = None,
    ) -> "ProjectDirectorNextTaskSourceBundleResolution":
        return cls(
            status="blocked",
            queue_snapshot=queue_snapshot,
            source_bundle=None,
            blocked_reasons=tuple(dict.fromkeys(reasons)),
        )


__all__ = (
    "NEXT_TASK_SOURCE_BUNDLE_SCHEMA_VERSION",
    "NextTaskSourceBundleBlockedReason",
    "NextTaskSourceBundleResolutionStatus",
    "ProjectDirectorAgentTeamConfigSnapshot",
    "ProjectDirectorAgentTeamMemberSnapshot",
    "ProjectDirectorDeliverableBoundarySnapshot",
    "ProjectDirectorNextTaskSourceBundle",
    "ProjectDirectorNextTaskSourceBundleResolution",
    "ProjectDirectorPlanScopeSnapshot",
    "ProjectDirectorRepositoryBindingConfigSnapshot",
    "ProjectDirectorRepositoryBindingSnapshot",
    "ProjectDirectorRepositoryWorkspaceSnapshot",
    "ProjectDirectorSkillBindingConfigSnapshot",
    "ProjectDirectorSkillBindingSnapshot",
    "ProjectDirectorVerificationConfigSnapshot",
    "ProjectDirectorVerificationMechanismSnapshot",
)
