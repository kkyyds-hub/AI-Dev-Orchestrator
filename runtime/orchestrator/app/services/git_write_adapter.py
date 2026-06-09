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
    fake_evidence: "GitWriteAdapterEvidenceRecord | None" = None

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
            raise ValueError("GitWrite adapter result cannot return executed status")
        return self


class GitWriteAdapterEvidenceRecord(DomainModel):
    """Safe readback record for fake adapter evidence only."""

    evidence_id: str = Field(min_length=1, max_length=120)
    intent_id: str = Field(min_length=1, max_length=120)
    preview_id: str = Field(min_length=1, max_length=120)
    adapter_mode: GitWriteAdapterMode = GitWriteAdapterMode.FAKE
    status: GitWriteAdapterResultStatus
    fake_evidence_ready: bool = False
    fake_execution_recorded: bool = False
    product_runtime_git_write_executed: bool = False
    operation_plan_id: str = Field(min_length=1, max_length=120)
    rollback_plan_id: str = Field(min_length=1, max_length=120)
    safe_summary: str = Field(min_length=1, max_length=1_000)
    blocking_reason: GitWriteAdapterBlockReason | None = None
    audit_event_summaries: list[str] = Field(default_factory=list)
    created_at: datetime

    @field_validator(
        "evidence_id",
        "intent_id",
        "preview_id",
        "operation_plan_id",
        "rollback_plan_id",
        mode="before",
    )
    @classmethod
    def trim_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("safe_summary")
    @classmethod
    def validate_safe_summary(cls, value: str) -> str:
        normalized = reject_suspicious_secret_text(value, "fake_evidence_summary")
        if normalized is None:
            raise ValueError("safe_summary must not be blank")
        return normalized

    @field_validator("audit_event_summaries")
    @classmethod
    def validate_audit_event_summaries(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            safe_value = reject_suspicious_secret_text(
                value,
                "fake_evidence_audit_summary",
            )
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
    def validate_fake_evidence_contract(self) -> "GitWriteAdapterEvidenceRecord":
        if self.adapter_mode != GitWriteAdapterMode.FAKE:
            raise ValueError("fake adapter evidence requires adapter_mode=fake")
        if self.product_runtime_git_write_executed is not False:
            raise ValueError("fake adapter evidence must not mark product writes executed")
        if self.status == GitWriteAdapterResultStatus.EXECUTED:
            raise ValueError("fake adapter evidence must not use executed status")
        if self.status == GitWriteAdapterResultStatus.FAKE_EVIDENCE_READY:
            if self.fake_evidence_ready is not True:
                raise ValueError("ready fake evidence requires fake_evidence_ready=True")
            if self.fake_execution_recorded is not True:
                raise ValueError("ready fake evidence requires fake_execution_recorded=True")
            if self.blocking_reason is not None:
                raise ValueError("ready fake evidence must not include blocking_reason")
        else:
            if self.fake_evidence_ready is not False:
                raise ValueError("blocked fake evidence requires fake_evidence_ready=False")
            if self.fake_execution_recorded is not False:
                raise ValueError("blocked fake evidence requires fake_execution_recorded=False")
        return self


GitWriteFakeAdapterEvidence = GitWriteAdapterEvidenceRecord


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


class FakeGitWriteAdapter:
    """Fake adapter evidence builder for GitWrite-G; it never touches a repo."""

    def build_operation_plan(
        self,
        request: GitWriteAdapterRequest,
    ) -> GitWriteAdapterOperationPlan:
        now = utc_now()
        return GitWriteAdapterOperationPlan(
            plan_id=f"fake-adapter-plan-{request.intent_id}",
            intent_id=request.intent_id,
            preview_id=request.preview_id,
            workspace_id=request.workspace_id,
            target_branch=request.target_branch,
            operation_sequence=request.operation_kinds,
            rollback_plan_id=request.rollback_plan_id,
            safe_summary=(
                "Fake adapter plan recorded from explicit request input only; "
                "fake evidence only, no repository side effects."
            ),
            cleanup_plan_summary=(
                "Rollback and cleanup remain plan summaries only; no host cleanup was run."
            ),
            created_at=now,
        )

    def build_fake_evidence(
        self,
        request: GitWriteAdapterRequest,
    ) -> GitWriteAdapterEvidenceRecord:
        plan = self.build_operation_plan(request)
        status, reason, summary = _resolve_fake_evidence_result(request)
        ready = status == GitWriteAdapterResultStatus.FAKE_EVIDENCE_READY
        return GitWriteAdapterEvidenceRecord(
            evidence_id=f"fake-evidence-{request.intent_id}",
            intent_id=request.intent_id,
            preview_id=request.preview_id,
            adapter_mode=GitWriteAdapterMode.FAKE,
            status=status,
            fake_evidence_ready=ready,
            fake_execution_recorded=ready,
            product_runtime_git_write_executed=False,
            operation_plan_id=plan.plan_id,
            rollback_plan_id=request.rollback_plan_id,
            safe_summary=summary,
            blocking_reason=reason,
            audit_event_summaries=[
                "Intent and preview ids were read from explicit adapter request input.",
                "Fake adapter evidence recorded safe summaries only.",
                "Rollback and cleanup remain plan summaries; no host action was run.",
                "Product runtime Git write executed remains false.",
            ],
            created_at=utc_now(),
        )

    def run(self, request: GitWriteAdapterRequest) -> GitWriteAdapterResult:
        plan = self.build_operation_plan(request)
        evidence = self.build_fake_evidence(request)
        return GitWriteAdapterResult(
            status=evidence.status,
            executed=False,
            product_runtime_git_write_executed=False,
            safe_summary=evidence.safe_summary,
            blocking_reason=evidence.blocking_reason,
            audit_event_summaries=evidence.audit_event_summaries,
            operation_plan=plan,
            rollback_plan_id=request.rollback_plan_id,
            created_at=utc_now(),
            fake_evidence=evidence,
        )


def _resolve_fake_evidence_result(
    request: GitWriteAdapterRequest,
) -> tuple[
    GitWriteAdapterResultStatus,
    GitWriteAdapterBlockReason | None,
    str,
]:
    if request.adapter_mode != GitWriteAdapterMode.FAKE:
        return (
            GitWriteAdapterResultStatus.BLOCKED,
            GitWriteAdapterBlockReason.REAL_ADAPTER_NOT_STARTED,
            "Fake evidence only; non-fake adapter modes remain blocked and no write ran.",
        )
    if not request.product_runtime_write_enabled:
        return (
            GitWriteAdapterResultStatus.DISABLED,
            GitWriteAdapterBlockReason.PRODUCT_RUNTIME_WRITE_DISABLED,
            "Product runtime write flag is disabled; fake evidence is disabled and no write ran.",
        )
    if request.preview_status != GitWritePreviewStatus.READY:
        return (
            GitWriteAdapterResultStatus.BLOCKED,
            GitWriteAdapterBlockReason.PREVIEW_NOT_READY,
            "Preview is not ready; fake evidence is blocked and no write ran.",
        )
    if request.safety_snapshot.preview_gates_passed() is not True:
        return (
            GitWriteAdapterResultStatus.BLOCKED,
            GitWriteAdapterBlockReason.PREVIEW_NOT_READY,
            "Preview gates are not passing; fake evidence is blocked and no write ran.",
        )
    if request.safety_snapshot.adapter_write_gates_passed() is not True:
        return (
            GitWriteAdapterResultStatus.BLOCKED,
            GitWriteAdapterBlockReason.FULL_WRITE_GATE_NOT_PASSED,
            "Preview gates alone are insufficient; fake evidence is blocked and no write ran.",
        )
    return (
        GitWriteAdapterResultStatus.FAKE_EVIDENCE_READY,
        None,
        "Fake evidence only; adapter contract readback is ready and no repository side effects occurred.",
    )
