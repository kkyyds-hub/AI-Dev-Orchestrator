"""Pure GitWrite domain contracts for product runtime write gating.

This module freezes GitWrite-B data shapes only. It does not execute Git,
read host configuration, inspect environment values, create host processes,
call services, expose API schemas, write database rows, or authorize product
runtime Git writes.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime


class GitWriteIntentStatus(StrEnum):
    DRAFT = "draft"
    PREVIEW_REQUIRED = "preview_required"
    PREVIEW_READY = "preview_ready"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    EXPIRED = "expired"
    CONSUMED = "consumed"
    CANCELLED = "cancelled"


class GitWriteOperationKind(StrEnum):
    STAGE_FILES = "stage_files"
    CREATE_COMMIT = "create_commit"
    PUSH_BRANCH = "push_branch"
    CREATE_PR = "create_pr"


class GitWriteSafetyGateName(StrEnum):
    FEATURE_FLAG = "feature_flag"
    WORKSPACE_BOUND = "workspace_bound"
    TARGET_BRANCH_ALLOWLIST = "target_branch_allowlist"
    DIFF_PREVIEW = "diff_preview"
    SECRET_SCAN = "secret_scan"
    REVIEWED_FILES = "reviewed_files"
    FORCE_PUSH_DETECTION = "force_push_detection"
    DESTRUCTIVE_OPERATION_BLOCK = "destructive_operation_block"
    CI_TRIGGER_CONTROL = "ci_trigger_control"
    HUMAN_APPROVAL = "human_approval"
    ONE_SHOT_TOKEN = "one_shot_token"
    ROLLBACK_PLAN = "rollback_plan"
    DRY_RUN = "dry_run"
    AUDIT_EVENT = "audit_event"
    NO_PRODUCT_RUNTIME_GIT_WRITE = "no_product_runtime_git_write"


class GitWriteSafetyGateStatus(StrEnum):
    PASSED = "passed"
    BLOCKED = "blocked"
    PENDING = "pending"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class GitWriteBlockReason(StrEnum):
    FEATURE_FLAG_DISABLED = "feature_flag_disabled"
    WORKSPACE_NOT_BOUND = "workspace_not_bound"
    TARGET_BRANCH_NOT_ALLOWED = "target_branch_not_allowed"
    DIFF_PREVIEW_MISSING = "diff_preview_missing"
    SECRET_DETECTED = "secret_detected"
    UNREVIEWED_FILES = "unreviewed_files"
    FORCE_PUSH_DETECTED = "force_push_detected"
    DESTRUCTIVE_OPERATION_DETECTED = "destructive_operation_detected"
    CI_TRIGGER_NOT_CONFIRMED = "ci_trigger_not_confirmed"
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"
    ONE_SHOT_TOKEN_MISSING = "one_shot_token_missing"
    ROLLBACK_PLAN_MISSING = "rollback_plan_missing"
    DRY_RUN_MISSING = "dry_run_missing"
    AUDIT_EVENT_MISSING = "audit_event_missing"
    PRODUCT_RUNTIME_GIT_WRITE_FORBIDDEN = "product_runtime_git_write_forbidden"
    UNKNOWN = "unknown"


class GitWriteApprovalDecision(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class GitWriteSource(StrEnum):
    USER = "user"
    PROJECT_DIRECTOR = "project_director"
    EXECUTOR_RUNTIME = "executor_runtime"
    FAKE_ADAPTER = "fake_adapter"
    UNKNOWN = "unknown"


class GitWriteTokenStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    REVOKED = "revoked"


class GitWritePreviewStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    BLOCKED = "blocked"
    EXPIRED = "expired"


REQUIRED_GIT_WRITE_SAFETY_GATES: tuple[GitWriteSafetyGateName, ...] = tuple(
    GitWriteSafetyGateName
)

_SUSPICIOUS_TEXT_PATTERN = re.compile(
    r"(api\s*[_-]?\s*key|token|secret|password|bearer|sk-|begin\s+private\s+key)",
    re.IGNORECASE,
)
_WINDOWS_DRIVE_PATH_PATTERN = re.compile(r"^[A-Za-z]:[\\/]")
_BRANCH_FORBIDDEN_PATTERN = re.compile(r"[\s~^:?*\[\\]")


def reject_suspicious_secret_text(
    value: str | None,
    field_name: str,
) -> str | None:
    """Trim optional text and reject obvious credential-like fragments."""

    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if _SUSPICIOUS_TEXT_PATTERN.search(normalized):
        raise ValueError(f"{field_name} must not contain suspected credential text")
    return normalized


def sanitize_path_hint(value: str | None) -> str | None:
    """Trim path hints and redact host-specific absolute path shapes."""

    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if (
        normalized.startswith("/")
        or normalized.startswith("~")
        or normalized.startswith("\\\\")
        or _WINDOWS_DRIVE_PATH_PATTERN.match(normalized) is not None
    ):
        return "workspace hint provided"
    return normalized


def normalize_string_list(values: list[str]) -> list[str]:
    """Trim, deduplicate, and validate relative file paths."""

    normalized_items: list[str] = []
    seen_items: set[str] = set()
    for value in values:
        normalized = _validate_relative_file_path(value)
        if normalized in seen_items:
            continue
        normalized_items.append(normalized)
        seen_items.add(normalized)
    return normalized_items


def _trim_optional_string(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _trim_required_string(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _normalize_optional_datetime(value: datetime | None) -> datetime | None:
    return ensure_utc_datetime(value)


def _normalize_required_datetime(value: datetime) -> datetime:
    normalized = ensure_utc_datetime(value)
    if normalized is None:
        raise ValueError("datetime must not be None")
    return normalized


def _validate_relative_file_path(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("file path must not be blank")
    if "\x00" in normalized:
        raise ValueError("file path must not contain NUL")
    if (
        normalized.startswith("/")
        or normalized.startswith("\\")
        or normalized.startswith("~")
        or _WINDOWS_DRIVE_PATH_PATTERN.match(normalized) is not None
    ):
        raise ValueError("file path must be a relative path")
    parts = re.split(r"[\\/]+", normalized)
    if any(part == ".." for part in parts):
        raise ValueError("file path must not contain traversal")
    return normalized


def _validate_branch_name(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    if normalized == "HEAD":
        raise ValueError(f"{field_name} must not be HEAD")
    if (
        ".." in normalized
        or normalized.startswith("/")
        or normalized.endswith("/")
        or _BRANCH_FORBIDDEN_PATTERN.search(normalized)
    ):
        raise ValueError(f"{field_name} contains unsafe branch characters")
    return normalized


def _dedupe_reasons(
    reasons: list[GitWriteBlockReason],
) -> list[GitWriteBlockReason]:
    normalized: list[GitWriteBlockReason] = []
    seen: set[GitWriteBlockReason] = set()
    for reason in reasons:
        if reason in seen:
            continue
        normalized.append(reason)
        seen.add(reason)
    return normalized


class GitWriteSafetyGateCheck(DomainModel):
    gate_name: GitWriteSafetyGateName
    status: GitWriteSafetyGateStatus = GitWriteSafetyGateStatus.UNKNOWN
    passed: bool = False
    block_reason: GitWriteBlockReason | None = None
    safe_summary: str | None = None
    checked_at: datetime | None = None

    @field_validator("safe_summary")
    @classmethod
    def validate_safe_summary(cls, value: str | None) -> str | None:
        return reject_suspicious_secret_text(value, "safe_summary")

    @field_validator("checked_at")
    @classmethod
    def normalize_checked_at(cls, value: datetime | None) -> datetime | None:
        return _normalize_optional_datetime(value)

    @model_validator(mode="after")
    def validate_status_contract(self) -> "GitWriteSafetyGateCheck":
        if self.status == GitWriteSafetyGateStatus.PASSED:
            if self.passed is not True:
                raise ValueError("passed gate status requires passed=True")
            if self.block_reason is not None:
                raise ValueError("passed gate status must not include block_reason")
        if self.status == GitWriteSafetyGateStatus.BLOCKED:
            if self.passed is not False:
                raise ValueError("blocked gate status requires passed=False")
            if self.block_reason is None:
                raise ValueError("blocked gate status requires block_reason")
        return self


class GitWriteSafetyGateSnapshot(DomainModel):
    gate_checks: list[GitWriteSafetyGateCheck]
    all_passed: bool = False
    blocking_reasons: list[GitWriteBlockReason] = Field(default_factory=list)
    evaluated_at: datetime

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)

    @field_validator("blocking_reasons")
    @classmethod
    def normalize_blocking_reasons(
        cls,
        values: list[GitWriteBlockReason],
    ) -> list[GitWriteBlockReason]:
        return _dedupe_reasons(values)

    @model_validator(mode="after")
    def validate_snapshot_contract(self) -> "GitWriteSafetyGateSnapshot":
        gate_names = {check.gate_name for check in self.gate_checks}
        missing_gates = [
            gate.value
            for gate in REQUIRED_GIT_WRITE_SAFETY_GATES
            if gate not in gate_names
        ]
        if missing_gates:
            raise ValueError(
                "GitWriteSafetyGateSnapshot missing required gates: "
                + ", ".join(missing_gates)
            )

        blocking_reasons = _dedupe_reasons(
            [
                check.block_reason
                for check in self.gate_checks
                if check.status == GitWriteSafetyGateStatus.BLOCKED
                and check.block_reason is not None
            ]
        )
        derived_all_passed = all(
            self.get_gate(gate).status == GitWriteSafetyGateStatus.PASSED
            and self.get_gate(gate).passed is True
            for gate in REQUIRED_GIT_WRITE_SAFETY_GATES
        )

        if derived_all_passed and blocking_reasons:
            raise ValueError("all passed snapshot must not include blocking reasons")
        object.__setattr__(self, "all_passed", derived_all_passed)
        object.__setattr__(self, "blocking_reasons", blocking_reasons)
        return self

    def failed_gates(self) -> list[GitWriteSafetyGateCheck]:
        return [
            check
            for check in self.gate_checks
            if check.status == GitWriteSafetyGateStatus.BLOCKED
        ]

    def get_gate(
        self,
        name: GitWriteSafetyGateName,
    ) -> GitWriteSafetyGateCheck:
        for check in self.gate_checks:
            if check.gate_name == name:
                return check
        raise KeyError(name)


class GitWriteIntent(DomainModel):
    intent_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    repository_id: str | None = Field(default=None, max_length=120)
    project_id: str | None = Field(default=None, max_length=120)
    task_id: str | None = Field(default=None, max_length=120)
    run_id: str | None = Field(default=None, max_length=120)
    source: GitWriteSource = GitWriteSource.USER
    requested_by: str | None = Field(default=None, max_length=120)
    target_branch: str
    base_branch: str | None = None
    operation_kinds: list[GitWriteOperationKind] = Field(
        default_factory=lambda: [GitWriteOperationKind.CREATE_COMMIT],
        min_length=1,
    )
    file_paths: list[str] = Field(min_length=1)
    commit_message: str | None = Field(default=None, max_length=500)
    status: GitWriteIntentStatus = GitWriteIntentStatus.DRAFT
    safety_snapshot: GitWriteSafetyGateSnapshot | None = None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None

    @field_validator(
        "intent_id",
        "workspace_id",
        "repository_id",
        "project_id",
        "task_id",
        "run_id",
        "requested_by",
        mode="before",
    )
    @classmethod
    def trim_text(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    @field_validator("target_branch", mode="before")
    @classmethod
    def trim_target_branch(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("target_branch")
    @classmethod
    def validate_target_branch(cls, value: str) -> str:
        branch = _validate_branch_name(value, "target_branch")
        if branch is None:
            raise ValueError("target_branch must not be blank")
        return branch

    @field_validator("base_branch")
    @classmethod
    def validate_base_branch(cls, value: str | None) -> str | None:
        return _validate_branch_name(value, "base_branch")

    @field_validator("file_paths")
    @classmethod
    def normalize_file_paths(cls, values: list[str]) -> list[str]:
        normalized = normalize_string_list(values)
        if not normalized:
            raise ValueError("file_paths must not be empty")
        return normalized

    @field_validator("commit_message")
    @classmethod
    def validate_commit_message(cls, value: str | None) -> str | None:
        return reject_suspicious_secret_text(value, "commit_message")

    @field_validator("created_at", "updated_at")
    @classmethod
    def normalize_required_timestamps(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)

    @field_validator("expires_at")
    @classmethod
    def normalize_expires_at(cls, value: datetime | None) -> datetime | None:
        return _normalize_optional_datetime(value)

    @model_validator(mode="after")
    def validate_intent_contract(self) -> "GitWriteIntent":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not be earlier than created_at")
        if self.expires_at is not None and self.expires_at < self.created_at:
            raise ValueError("expires_at must not be earlier than created_at")
        if not self.operation_kinds:
            raise ValueError("operation_kinds must not be empty")
        if (
            self.status == GitWriteIntentStatus.APPROVED
            and (
                self.safety_snapshot is None
                or self.safety_snapshot.all_passed is not True
            )
        ):
            raise ValueError("approved GitWriteIntent requires all safety gates passed")
        return self

    def requires_preview(self) -> bool:
        return self.status in {
            GitWriteIntentStatus.DRAFT,
            GitWriteIntentStatus.PREVIEW_REQUIRED,
        }


class GitWritePreviewFile(DomainModel):
    path: str
    change_type: str = Field(min_length=1, max_length=80)
    additions: int = Field(default=0, ge=0)
    deletions: int = Field(default=0, ge=0)
    reviewed: bool = False
    contains_secret: bool = False
    safe_summary: str | None = Field(default=None, max_length=500)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _validate_relative_file_path(value)

    @field_validator("change_type", mode="before")
    @classmethod
    def trim_change_type(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("safe_summary")
    @classmethod
    def validate_safe_summary(cls, value: str | None) -> str | None:
        return reject_suspicious_secret_text(value, "safe_summary")


class GitWriteRollbackPlan(DomainModel):
    plan_id: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=1_000)
    restore_branch_hint: str | None = Field(default=None, max_length=200)
    restore_commit_hint: str | None = Field(default=None, max_length=200)
    generated_at: datetime

    @field_validator("plan_id", mode="before")
    @classmethod
    def trim_plan_id(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        normalized = reject_suspicious_secret_text(value, "summary")
        if normalized is None:
            raise ValueError("summary must not be blank")
        return normalized

    @field_validator("restore_branch_hint")
    @classmethod
    def validate_restore_branch_hint(cls, value: str | None) -> str | None:
        return _validate_branch_name(value, "restore_branch_hint")

    @field_validator("restore_commit_hint")
    @classmethod
    def trim_restore_commit_hint(cls, value: str | None) -> str | None:
        return reject_suspicious_secret_text(value, "restore_commit_hint")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)


class GitWritePreview(DomainModel):
    preview_id: str = Field(min_length=1, max_length=120)
    intent_id: str = Field(min_length=1, max_length=120)
    status: GitWritePreviewStatus = GitWritePreviewStatus.PENDING
    target_branch: str
    files: list[GitWritePreviewFile] = Field(min_length=1)
    diff_summary: str | None = Field(default=None, max_length=2_000)
    commit_message_preview: str | None = Field(default=None, max_length=500)
    pull_request_title_preview: str | None = Field(default=None, max_length=300)
    pull_request_body_preview: str | None = Field(default=None, max_length=2_000)
    rollback_plan: GitWriteRollbackPlan | None = None
    safety_snapshot: GitWriteSafetyGateSnapshot
    created_at: datetime
    expires_at: datetime | None = None

    @field_validator("preview_id", "intent_id", mode="before")
    @classmethod
    def trim_ids(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("target_branch")
    @classmethod
    def validate_target_branch(cls, value: str) -> str:
        branch = _validate_branch_name(value, "target_branch")
        if branch is None:
            raise ValueError("target_branch must not be blank")
        return branch

    @field_validator(
        "diff_summary",
        "commit_message_preview",
        "pull_request_title_preview",
        "pull_request_body_preview",
    )
    @classmethod
    def validate_safe_preview_text(cls, value: str | None) -> str | None:
        return reject_suspicious_secret_text(value, "preview_text")

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)

    @field_validator("expires_at")
    @classmethod
    def normalize_expires_at(cls, value: datetime | None) -> datetime | None:
        return _normalize_optional_datetime(value)

    @model_validator(mode="after")
    def validate_preview_contract(self) -> "GitWritePreview":
        if self.expires_at is not None and self.expires_at < self.created_at:
            raise ValueError("expires_at must not be earlier than created_at")
        if any(file.contains_secret for file in self.files):
            if self.status != GitWritePreviewStatus.BLOCKED:
                raise ValueError("preview with flagged credential material must be blocked")
        if self.status == GitWritePreviewStatus.READY:
            if any(not file.reviewed for file in self.files):
                raise ValueError("ready preview requires all files reviewed")
            if self.safety_snapshot.all_passed is not True:
                raise ValueError("ready preview requires all safety gates passed")
        if (
            self.status == GitWritePreviewStatus.BLOCKED
            and self.safety_snapshot.all_passed is True
        ):
            raise ValueError("blocked preview requires a non-passing safety snapshot")
        return self

    def ready_file_paths(self) -> list[str]:
        return [file.path for file in self.files if file.reviewed]


class OneShotApprovalToken(DomainModel):
    token_id: str = Field(min_length=1, max_length=120)
    token_hint: str = Field(min_length=1, max_length=200)
    intent_id: str = Field(min_length=1, max_length=120)
    preview_id: str = Field(min_length=1, max_length=120)
    status: GitWriteTokenStatus = GitWriteTokenStatus.PENDING
    issued_at: datetime
    expires_at: datetime
    consumed_at: datetime | None = None
    revoked_at: datetime | None = None

    @field_validator("token_id", "intent_id", "preview_id", mode="before")
    @classmethod
    def trim_ids(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("token_hint")
    @classmethod
    def validate_token_hint(cls, value: str) -> str:
        normalized = reject_suspicious_secret_text(value, "token_hint")
        if normalized is None:
            raise ValueError("token_hint must not be blank")
        return normalized

    @field_validator("issued_at", "expires_at")
    @classmethod
    def normalize_required_timestamps(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)

    @field_validator("consumed_at", "revoked_at")
    @classmethod
    def normalize_optional_timestamps(cls, value: datetime | None) -> datetime | None:
        return _normalize_optional_datetime(value)

    @model_validator(mode="after")
    def validate_token_contract(self) -> "OneShotApprovalToken":
        if self.expires_at <= self.issued_at:
            raise ValueError("expires_at must be later than issued_at")
        if self.consumed_at is not None and self.consumed_at < self.issued_at:
            raise ValueError("consumed_at must not be earlier than issued_at")
        if self.revoked_at is not None and self.revoked_at < self.issued_at:
            raise ValueError("revoked_at must not be earlier than issued_at")
        if self.status == GitWriteTokenStatus.ACTIVE and (
            self.consumed_at is not None or self.revoked_at is not None
        ):
            raise ValueError("active token must not be consumed or revoked")
        if self.status == GitWriteTokenStatus.CONSUMED and self.consumed_at is None:
            raise ValueError("consumed token requires consumed_at")
        if self.status == GitWriteTokenStatus.REVOKED and self.revoked_at is None:
            raise ValueError("revoked token requires revoked_at")
        return self

    def is_active(self, now: datetime) -> bool:
        normalized_now = _normalize_required_datetime(now)
        return (
            self.status == GitWriteTokenStatus.ACTIVE
            and self.consumed_at is None
            and self.revoked_at is None
            and self.issued_at <= normalized_now < self.expires_at
        )


class GitWriteApproval(DomainModel):
    approval_id: str = Field(min_length=1, max_length=120)
    intent_id: str = Field(min_length=1, max_length=120)
    preview_id: str = Field(min_length=1, max_length=120)
    decision: GitWriteApprovalDecision = GitWriteApprovalDecision.PENDING
    decided_by: str | None = Field(default=None, max_length=120)
    decided_at: datetime | None = None
    approval_note: str | None = Field(default=None, max_length=1_000)
    one_shot_token: OneShotApprovalToken | None = None
    safety_snapshot: GitWriteSafetyGateSnapshot

    @field_validator("approval_id", "intent_id", "preview_id", mode="before")
    @classmethod
    def trim_ids(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("decided_by")
    @classmethod
    def trim_decided_by(cls, value: str | None) -> str | None:
        return _trim_optional_string(value)

    @field_validator("decided_at")
    @classmethod
    def normalize_decided_at(cls, value: datetime | None) -> datetime | None:
        return _normalize_optional_datetime(value)

    @field_validator("approval_note")
    @classmethod
    def validate_approval_note(cls, value: str | None) -> str | None:
        return reject_suspicious_secret_text(value, "approval_note")

    @model_validator(mode="after")
    def validate_approval_contract(self) -> "GitWriteApproval":
        if self.decision == GitWriteApprovalDecision.APPROVED:
            if not self.decided_by:
                raise ValueError("approved decision requires decided_by")
            if self.decided_at is None:
                raise ValueError("approved decision requires decided_at")
            if self.one_shot_token is None:
                raise ValueError("approved decision requires one_shot_token")
            if self.safety_snapshot.all_passed is not True:
                raise ValueError("approved decision requires all safety gates passed")
        return self

    def is_approved(self) -> bool:
        return self.decision == GitWriteApprovalDecision.APPROVED


class GitWriteAuditEvent(DomainModel):
    event_id: str = Field(min_length=1, max_length=120)
    intent_id: str = Field(min_length=1, max_length=120)
    event_type: str = Field(min_length=1, max_length=200)
    timestamp: datetime
    safe_summary: str | None = Field(default=None, max_length=1_000)
    append_only: bool = True
    metadata_count: int = Field(default=0, ge=0)

    @field_validator("event_id", "intent_id", "event_type", mode="before")
    @classmethod
    def trim_required_text(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)

    @field_validator("safe_summary")
    @classmethod
    def validate_safe_summary(cls, value: str | None) -> str | None:
        return reject_suspicious_secret_text(value, "safe_summary")
