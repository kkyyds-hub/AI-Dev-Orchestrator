"""GitWrite-F adapter contract and disabled adapter seam.

This module defines adapter request, operation plan, and result readback
contracts. The disabled adapter never performs product runtime Git writes,
does not inspect repositories, does not read environment values, and does not
launch host processes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now
from app.domain.git_write import (
    GitWriteAdapterBlockReason,
    GitWriteAdapterMode,
    GitWriteAdapterResultStatus,
    GitWriteOperationKind,
    GitWritePreviewStatus,
    GitWriteSafetyGateSnapshot,
    normalize_string_list,
    reject_suspicious_secret_text,
)


class GitWriteAdapterOperationPlan(DomainModel):
    """A contract-only operation sequence for a future adapter."""

    plan_id: str = Field(min_length=1, max_length=120)
    intent_id: str = Field(min_length=1, max_length=120)
    preview_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    target_branch: str = Field(min_length=1, max_length=200)
    operation_sequence: list[GitWriteOperationKind] = Field(min_length=1)
    rollback_plan_id: str = Field(min_length=1, max_length=120)
    safe_summary: str = Field(min_length=1, max_length=1_000)
    cleanup_plan_summary: str | None = Field(default=None, max_length=1_000)
    created_at: datetime

    @field_validator(
        "plan_id",
        "intent_id",
        "preview_id",
        "workspace_id",
        "target_branch",
        "rollback_plan_id",
        mode="before",
    )
    @classmethod
    def trim_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("safe_summary", "cleanup_plan_summary")
    @classmethod
    def validate_safe_text(cls, value: str | None) -> str | None:
        return reject_suspicious_secret_text(value, "adapter_plan_text")

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        normalized = ensure_utc_datetime(value)
        if normalized is None:
            raise ValueError("created_at must not be None")
        return normalized


class GitWriteAdapterRequest(DomainModel):
    intent_id: str = Field(min_length=1, max_length=120)
    preview_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    target_branch: str = Field(min_length=1, max_length=200)
    file_paths: list[str] = Field(min_length=1)
    operation_kinds: list[GitWriteOperationKind] = Field(min_length=1)
    approval_id: str = Field(min_length=1, max_length=120)
    one_shot_token_id: str = Field(min_length=1, max_length=120)
    rollback_plan_id: str = Field(min_length=1, max_length=120)
    requested_by: str | None = Field(default=None, max_length=120)
    requested_at: datetime
    product_runtime_write_enabled: bool = False
    adapter_mode: GitWriteAdapterMode = GitWriteAdapterMode.DISABLED
    preview_status: GitWritePreviewStatus
    safety_snapshot: GitWriteSafetyGateSnapshot

    @field_validator(
        "intent_id",
        "preview_id",
        "workspace_id",
        "target_branch",
        "approval_id",
        "one_shot_token_id",
        "rollback_plan_id",
        mode="before",
    )
    @classmethod
    def trim_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("requested_by", mode="before")
    @classmethod
    def trim_requested_by(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("file_paths")
    @classmethod
    def normalize_file_paths(cls, values: list[str]) -> list[str]:
        normalized = normalize_string_list(values)
        if not normalized:
            raise ValueError("file_paths must not be empty")
        return normalized

    @field_validator("requested_at")
    @classmethod
    def normalize_requested_at(cls, value: datetime) -> datetime:
        normalized = ensure_utc_datetime(value)
        if normalized is None:
            raise ValueError("requested_at must not be None")
        return normalized

    @model_validator(mode="after")
    def validate_request_contract(self) -> "GitWriteAdapterRequest":
        if not self.operation_kinds:
            raise ValueError("operation_kinds must not be empty")
        return self


class GitWriteAdapterResult(DomainModel):
    status: GitWriteAdapterResultStatus
    executed: bool = False
    product_runtime_git_write_executed: bool = False
    safe_summary: str = Field(min_length=1, max_length=1_000)
    blocking_reason: GitWriteAdapterBlockReason | None = None
    audit_event_summaries: list[str] = Field(default_factory=list)
    operation_plan: GitWriteAdapterOperationPlan
    rollback_plan_id: str = Field(min_length=1, max_length=120)
    created_at: datetime

    @field_validator("safe_summary")
    @classmethod
    def validate_safe_summary(cls, value: str) -> str:
        normalized = reject_suspicious_secret_text(value, "safe_summary")
        if normalized is None:
            raise ValueError("safe_summary must not be blank")
        return normalized

    @field_validator("audit_event_summaries")
    @classmethod
    def validate_audit_event_summaries(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            safe_value = reject_suspicious_secret_text(value, "audit_event_summary")
            if safe_value is not None:
                normalized.append(safe_value)
        return normalized

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        normalized = ensure_utc_datetime(value)
        if normalized is None:
            raise ValueError("created_at must not be None")
        return normalized

    @model_validator(mode="after")
    def validate_disabled_contract(self) -> "GitWriteAdapterResult":
        if self.executed is not False:
            raise ValueError("GitWrite-F adapter result must not be executed")
        if self.product_runtime_git_write_executed is not False:
            raise ValueError("GitWrite-F must not mark product runtime writes executed")
        if self.status == GitWriteAdapterResultStatus.EXECUTED:
            raise ValueError("GitWrite-F disabled adapter cannot return executed status")
        return self


class GitWriteAdapter(Protocol):
    def build_operation_plan(
        self,
        request: GitWriteAdapterRequest,
    ) -> GitWriteAdapterOperationPlan:
        ...

    def run(self, request: GitWriteAdapterRequest) -> GitWriteAdapterResult:
        ...


class DisabledGitWriteAdapter:
    """Disabled adapter seam for GitWrite-F; it only returns safe readback."""

    def build_operation_plan(
        self,
        request: GitWriteAdapterRequest,
    ) -> GitWriteAdapterOperationPlan:
        now = utc_now()
        return GitWriteAdapterOperationPlan(
            plan_id=f"adapter-plan-{request.intent_id}",
            intent_id=request.intent_id,
            preview_id=request.preview_id,
            workspace_id=request.workspace_id,
            target_branch=request.target_branch,
            operation_sequence=request.operation_kinds,
            rollback_plan_id=request.rollback_plan_id,
            safe_summary=(
                "Adapter plan recorded as a contract only; real adapter work is not started."
            ),
            cleanup_plan_summary=(
                "Cleanup remains a future contract step; no host resource cleanup was run."
            ),
            created_at=now,
        )

    def run(self, request: GitWriteAdapterRequest) -> GitWriteAdapterResult:
        plan = self.build_operation_plan(request)
        status, reason, summary = _resolve_disabled_result(request)
        return GitWriteAdapterResult(
            status=status,
            executed=False,
            product_runtime_git_write_executed=False,
            safe_summary=summary,
            blocking_reason=reason,
            audit_event_summaries=[
                "Adapter request received as safe readback.",
                "Disabled adapter returned without repository side effects.",
            ],
            operation_plan=plan,
            rollback_plan_id=request.rollback_plan_id,
            created_at=utc_now(),
        )


def _resolve_disabled_result(
    request: GitWriteAdapterRequest,
) -> tuple[GitWriteAdapterResultStatus, GitWriteAdapterBlockReason, str]:
    if not request.product_runtime_write_enabled:
        return (
            GitWriteAdapterResultStatus.DISABLED,
            GitWriteAdapterBlockReason.PRODUCT_RUNTIME_WRITE_DISABLED,
            "Product runtime write flag is disabled; adapter returned without side effects.",
        )
    if request.preview_status != GitWritePreviewStatus.READY:
        return (
            GitWriteAdapterResultStatus.BLOCKED,
            GitWriteAdapterBlockReason.PREVIEW_NOT_READY,
            "Preview is not ready; adapter cannot proceed.",
        )
    if request.safety_snapshot.preview_gates_passed() is not True:
        return (
            GitWriteAdapterResultStatus.BLOCKED,
            GitWriteAdapterBlockReason.PREVIEW_NOT_READY,
            "Preview gates are not passing; adapter cannot proceed.",
        )
    if request.safety_snapshot.adapter_write_gates_passed() is not True:
        return (
            GitWriteAdapterResultStatus.BLOCKED,
            GitWriteAdapterBlockReason.FULL_WRITE_GATE_NOT_PASSED,
            "Preview gates alone are insufficient; full write gates are not passing.",
        )
    if request.adapter_mode != GitWriteAdapterMode.DISABLED:
        return (
            GitWriteAdapterResultStatus.BLOCKED,
            GitWriteAdapterBlockReason.REAL_ADAPTER_NOT_STARTED,
            "Requested adapter mode is not available in GitWrite-F; real adapter is Not started.",
        )
    return (
        GitWriteAdapterResultStatus.DISABLED,
        GitWriteAdapterBlockReason.REAL_ADAPTER_NOT_STARTED,
        "Full gates passed in the request, but GitWrite-F keeps the adapter disabled.",
    )
