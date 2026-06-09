"""Pure domain contracts for the P9 real Git write pilot.

This module freezes P9-RGWP-B data shapes only. It does not execute Git,
launch external executors, inspect repositories, read environment values,
call services, expose APIs, or authorize product runtime Git writes.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


class RealGitWritePilotStatus(StrEnum):
    PENDING = "pending"
    PREVIEW_READY = "preview_ready"
    APPROVAL_REQUIRED = "approval_required"
    APPROVED = "approved"
    TOKEN_ISSUED = "token_issued"
    PREFLIGHT_READY = "preflight_ready"
    BLOCKED = "blocked"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class RealGitWritePilotOperationKind(StrEnum):
    CREATE_DOC_FILE = "create_doc_file"
    CREATE_COMMIT_CANDIDATE = "create_commit_candidate"
    LOCAL_BRANCH_CANDIDATE = "local_branch_candidate"


class RealGitWritePilotGateName(StrEnum):
    FEATURE_FLAG = "feature_flag"
    EXECUTOR_READINESS = "executor_readiness"
    WORKSPACE_WORKTREE = "workspace_worktree"
    TARGET_BRANCH_ALLOWLIST = "target_branch_allowlist"
    DIFF_PREVIEW = "diff_preview"
    SECRET_SCAN = "secret_scan"
    HUMAN_APPROVAL = "human_approval"
    ONE_SHOT_TOKEN = "one_shot_token"
    BUDGET_COST = "budget_cost"
    TIMEOUT_KILL_SWITCH = "timeout_kill_switch"
    ROLLBACK_PLAN = "rollback_plan"
    NO_DIRECT_MAIN_WRITE = "no_direct_main_write"
    NO_FORCE_PUSH = "no_force_push"
    NO_AUTO_PR_MERGE = "no_auto_pr_merge"
    APPEND_ONLY_AUDIT = "append_only_audit"
    POST_WRITE_VERIFY = "post_write_verify"
    MANUAL_FINAL_CONFIRMATION = "manual_final_confirmation"


class RealGitWritePilotGateStatus(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class RealGitWritePilotBlockReason(StrEnum):
    FEATURE_FLAG_DISABLED = "feature_flag_disabled"
    EXECUTOR_NOT_READY = "executor_not_ready"
    WORKSPACE_NOT_BOUND = "workspace_not_bound"
    TARGET_BRANCH_NOT_ALLOWED = "target_branch_not_allowed"
    MAIN_BRANCH_BLOCKED = "main_branch_blocked"
    FILE_SCOPE_NOT_ALLOWED = "file_scope_not_allowed"
    SECRET_DETECTED = "secret_detected"
    APPROVAL_MISSING = "approval_missing"
    TOKEN_MISSING_OR_EXPIRED = "token_missing_or_expired"
    BUDGET_EXCEEDED = "budget_exceeded"
    TIMEOUT_NOT_CONFIGURED = "timeout_not_configured"
    ROLLBACK_PLAN_MISSING = "rollback_plan_missing"
    FORCE_PUSH_REQUESTED = "force_push_requested"
    AUTO_PR_OR_MERGE_REQUESTED = "auto_pr_or_merge_requested"
    AUDIT_MISSING = "audit_missing"
    POST_WRITE_VERIFY_MISSING = "post_write_verify_missing"
    MANUAL_FINAL_CONFIRMATION_MISSING = "manual_final_confirmation_missing"
    PRODUCT_RUNTIME_WRITE_NOT_STARTED = "product_runtime_write_not_started"
    REAL_EXECUTION_NOT_STARTED = "real_execution_not_started"


class RealGitWritePilotApprovalDecision(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


REQUIRED_REAL_GIT_WRITE_PILOT_GATES: tuple[RealGitWritePilotGateName, ...] = tuple(
    RealGitWritePilotGateName
)

PREFLIGHT_REAL_GIT_WRITE_PILOT_GATES: tuple[RealGitWritePilotGateName, ...] = (
    RealGitWritePilotGateName.FEATURE_FLAG,
    RealGitWritePilotGateName.EXECUTOR_READINESS,
    RealGitWritePilotGateName.WORKSPACE_WORKTREE,
    RealGitWritePilotGateName.TARGET_BRANCH_ALLOWLIST,
    RealGitWritePilotGateName.DIFF_PREVIEW,
    RealGitWritePilotGateName.SECRET_SCAN,
    RealGitWritePilotGateName.HUMAN_APPROVAL,
    RealGitWritePilotGateName.ONE_SHOT_TOKEN,
    RealGitWritePilotGateName.BUDGET_COST,
    RealGitWritePilotGateName.TIMEOUT_KILL_SWITCH,
    RealGitWritePilotGateName.ROLLBACK_PLAN,
    RealGitWritePilotGateName.NO_DIRECT_MAIN_WRITE,
    RealGitWritePilotGateName.NO_FORCE_PUSH,
    RealGitWritePilotGateName.NO_AUTO_PR_MERGE,
    RealGitWritePilotGateName.APPEND_ONLY_AUDIT,
)

_SUSPICIOUS_TEXT_PATTERN = re.compile(
    r"("
    r"api\s*[_-]?\s*key|"
    r"token\s*[=:]|"
    r"secret|"
    r"password|"
    r"bearer\s+[A-Za-z0-9._~+/=-]{8,}|"
    r"sk-(?:ant-)?(?:proj-|svcacct-)?[A-Za-z0-9_-]{12,}|"
    r"github_pat_[A-Za-z0-9_]{12,}|"
    r"gh[pousr]_[A-Za-z0-9_]{12,}|"
    r"begin\s+private\s+key|"
    r"AKIA[0-9A-Z]{16}"
    r")",
    re.IGNORECASE,
)
_WINDOWS_DRIVE_PATH_PATTERN = re.compile(r"^[A-Za-z]:[\\/]")
_BRANCH_FORBIDDEN_PATTERN = re.compile(r"[\s~^:?*\[\\]")
_PILOT_BRANCH_PATTERN = re.compile(
    r"^ai/gitwrite-pilot/\d{4}-\d{2}-\d{2}-doc-only$",
)
_DOCS_MARKDOWN_PATH_PATTERN = re.compile(r"^docs/(?:[^/]+/)*[^/]+\.md$")
_COMMIT_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{7,64}$")
_FORBIDDEN_BRANCH_NAMES = {"main", "master", "release", "production", "staging", "gh-pages"}
_FORBIDDEN_BRANCH_PREFIXES = ("release/", "production/", "staging/", "gh-pages/")
_FORBIDDEN_ROLLBACK_ACTION_PATTERNS = (
    "reset --hard",
    "force push",
    "--force",
    "automatic rollback script",
    "auto rollback script",
    "automated rollback script",
)


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


def reject_pilot_suspicious_text(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if _SUSPICIOUS_TEXT_PATTERN.search(normalized):
        raise ValueError(f"{field_name} must not contain suspected credential text")
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
    if not _DOCS_MARKDOWN_PATH_PATTERN.fullmatch(normalized):
        raise ValueError("file path must match docs/**/*.md")
    return normalized


def _normalize_file_paths(values: list[str]) -> list[str]:
    normalized_items: list[str] = []
    seen_items: set[str] = set()
    for value in values:
        normalized = _validate_relative_file_path(value)
        if normalized in seen_items:
            continue
        normalized_items.append(normalized)
        seen_items.add(normalized)
    return normalized_items


def _validate_pilot_branch(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("target_branch must not be blank")
    if normalized == "HEAD":
        raise ValueError("target_branch must not be HEAD")
    if (
        ".." in normalized
        or normalized.startswith("/")
        or normalized.endswith("/")
        or _BRANCH_FORBIDDEN_PATTERN.search(normalized)
    ):
        raise ValueError("target_branch contains unsafe branch characters")
    if normalized in _FORBIDDEN_BRANCH_NAMES or normalized.startswith(
        _FORBIDDEN_BRANCH_PREFIXES,
    ):
        raise ValueError("target_branch is blocked for the real Git write pilot")
    if _PILOT_BRANCH_PATTERN.fullmatch(normalized) is None:
        raise ValueError("target_branch must match ai/gitwrite-pilot/<date>-doc-only")
    return normalized


def _validate_commit_id(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    if _COMMIT_ID_PATTERN.fullmatch(normalized) is None:
        raise ValueError(f"{field_name} must be a commit id")
    return normalized


def _dedupe_reasons(
    reasons: list[RealGitWritePilotBlockReason],
) -> list[RealGitWritePilotBlockReason]:
    normalized: list[RealGitWritePilotBlockReason] = []
    seen: set[RealGitWritePilotBlockReason] = set()
    for reason in reasons:
        if reason in seen:
            continue
        normalized.append(reason)
        seen.add(reason)
    return normalized


def _normalize_safe_text_list(
    values: list[str],
    field_name: str,
) -> list[str]:
    normalized_items: list[str] = []
    seen_items: set[str] = set()
    for value in values:
        normalized = reject_pilot_suspicious_text(value, field_name)
        if normalized is None or normalized in seen_items:
            continue
        normalized_items.append(normalized)
        seen_items.add(normalized)
    return normalized_items


class RealGitWritePilotGateCheck(DomainModel):
    gate_name: RealGitWritePilotGateName
    status: RealGitWritePilotGateStatus = RealGitWritePilotGateStatus.PENDING
    passed: bool = False
    block_reason: RealGitWritePilotBlockReason | None = None
    checked_at: datetime | None = None
    safe_summary: str | None = Field(default=None, max_length=1_000)

    @field_validator("checked_at")
    @classmethod
    def normalize_checked_at(cls, value: datetime | None) -> datetime | None:
        return _normalize_optional_datetime(value)

    @field_validator("safe_summary")
    @classmethod
    def validate_safe_summary(cls, value: str | None) -> str | None:
        return reject_pilot_suspicious_text(value, "safe_summary")

    @model_validator(mode="after")
    def validate_gate_check_contract(self) -> "RealGitWritePilotGateCheck":
        if self.status == RealGitWritePilotGateStatus.PASSED:
            if self.passed is not True:
                raise ValueError("passed gate status requires passed=True")
            if self.block_reason is not None:
                raise ValueError("passed gate status must not include block_reason")
        if self.status == RealGitWritePilotGateStatus.BLOCKED:
            if self.passed is not False:
                raise ValueError("blocked gate status requires passed=False")
            if self.block_reason is None:
                raise ValueError("blocked gate status requires block_reason")
        if self.status in {
            RealGitWritePilotGateStatus.PENDING,
            RealGitWritePilotGateStatus.NOT_APPLICABLE,
        }:
            if self.passed is not False:
                raise ValueError("non-passed gate status requires passed=False")
            if self.block_reason is not None:
                raise ValueError("non-blocked gate status must not include block_reason")
        return self


class RealGitWritePilotGateSnapshot(DomainModel):
    gate_checks: list[RealGitWritePilotGateCheck] = Field(min_length=1)
    evaluated_at: datetime = Field(default_factory=utc_now)
    all_required_gates_present: bool = False
    all_passed: bool = False
    blocking_reasons: list[RealGitWritePilotBlockReason] = Field(default_factory=list)

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)

    @model_validator(mode="after")
    def validate_snapshot_contract(self) -> "RealGitWritePilotGateSnapshot":
        gate_names = {check.gate_name for check in self.gate_checks}
        missing_gates = [
            gate.value
            for gate in REQUIRED_REAL_GIT_WRITE_PILOT_GATES
            if gate not in gate_names
        ]
        if missing_gates:
            raise ValueError(
                "RealGitWritePilotGateSnapshot missing required gates: "
                + ", ".join(missing_gates),
            )

        blocking_reasons = _dedupe_reasons(
            [
                check.block_reason
                for check in self.gate_checks
                if check.status == RealGitWritePilotGateStatus.BLOCKED
                and check.block_reason is not None
            ],
        )
        derived_all_passed = all(
            self.get_gate(gate).status == RealGitWritePilotGateStatus.PASSED
            and self.get_gate(gate).passed is True
            for gate in REQUIRED_REAL_GIT_WRITE_PILOT_GATES
        )

        object.__setattr__(self, "all_required_gates_present", True)
        object.__setattr__(self, "all_passed", derived_all_passed)
        object.__setattr__(self, "blocking_reasons", blocking_reasons)
        return self

    def get_gate(
        self,
        name: RealGitWritePilotGateName,
    ) -> RealGitWritePilotGateCheck:
        for check in self.gate_checks:
            if check.gate_name == name:
                return check
        raise KeyError(name)

    def failed_gates(self) -> list[RealGitWritePilotGateCheck]:
        return [
            check
            for check in self.gate_checks
            if check.status == RealGitWritePilotGateStatus.BLOCKED
        ]

    def pilot_preflight_gates_passed(self) -> bool:
        return all(
            self.get_gate(gate).status == RealGitWritePilotGateStatus.PASSED
            and self.get_gate(gate).passed is True
            for gate in PREFLIGHT_REAL_GIT_WRITE_PILOT_GATES
        )


class RealGitWritePilotRequest(DomainModel):
    pilot_id: str = Field(min_length=1, max_length=120)
    project_id: str = Field(min_length=1, max_length=120)
    run_id: str = Field(min_length=1, max_length=120)
    executor_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    repository_id: str = Field(min_length=1, max_length=120)
    base_commit: str = Field(min_length=7, max_length=64)
    target_branch: str = Field(min_length=1, max_length=200)
    allowed_branch_pattern: str = Field(
        default="ai/gitwrite-pilot/<date>-doc-only",
        max_length=200,
    )
    file_paths: list[str] = Field(min_length=1)
    operation_kinds: list[RealGitWritePilotOperationKind] = Field(
        default_factory=lambda: [
            RealGitWritePilotOperationKind.CREATE_DOC_FILE,
            RealGitWritePilotOperationKind.CREATE_COMMIT_CANDIDATE,
            RealGitWritePilotOperationKind.LOCAL_BRANCH_CANDIDATE,
        ],
        min_length=1,
    )
    requested_by: str = Field(min_length=1, max_length=120)
    requested_at: datetime
    expires_at: datetime
    status: RealGitWritePilotStatus = RealGitWritePilotStatus.PENDING
    gate_snapshot: RealGitWritePilotGateSnapshot
    product_runtime_git_write_executed: bool = False
    real_executor_started: bool = False

    @field_validator(
        "pilot_id",
        "project_id",
        "run_id",
        "executor_id",
        "workspace_id",
        "repository_id",
        "requested_by",
        mode="before",
    )
    @classmethod
    def trim_required_text(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("base_commit")
    @classmethod
    def validate_base_commit(cls, value: str) -> str:
        return _validate_commit_id(value, "base_commit")

    @field_validator("target_branch")
    @classmethod
    def validate_target_branch(cls, value: str) -> str:
        return _validate_pilot_branch(value)

    @field_validator("allowed_branch_pattern")
    @classmethod
    def validate_allowed_branch_pattern(cls, value: str) -> str:
        normalized = reject_pilot_suspicious_text(value, "allowed_branch_pattern")
        if normalized != "ai/gitwrite-pilot/<date>-doc-only":
            raise ValueError("allowed_branch_pattern is fixed for P9-RGWP-B")
        return normalized

    @field_validator("file_paths")
    @classmethod
    def normalize_file_paths(cls, values: list[str]) -> list[str]:
        normalized = _normalize_file_paths(values)
        if not normalized:
            raise ValueError("file_paths must not be empty")
        return normalized

    @field_validator("requested_at", "expires_at")
    @classmethod
    def normalize_required_timestamps(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)

    @model_validator(mode="after")
    def validate_request_contract(self) -> "RealGitWritePilotRequest":
        if self.expires_at <= self.requested_at:
            raise ValueError("expires_at must be later than requested_at")
        if self.product_runtime_git_write_executed is not False:
            raise ValueError("product runtime Git write must remain Not started")
        if self.real_executor_started is not False:
            raise ValueError("real executor must remain Not started")
        if not self.operation_kinds:
            raise ValueError("operation_kinds must not be empty")
        if (
            self.status == RealGitWritePilotStatus.APPROVED
            and self.gate_snapshot.get_gate(
                RealGitWritePilotGateName.HUMAN_APPROVAL,
            ).passed
            is not True
        ):
            raise ValueError("approved pilot request requires human approval gate")
        if (
            self.status == RealGitWritePilotStatus.TOKEN_ISSUED
            and self.gate_snapshot.get_gate(
                RealGitWritePilotGateName.ONE_SHOT_TOKEN,
            ).passed
            is not True
        ):
            raise ValueError("token issued pilot request requires one-shot token gate")
        if (
            self.status == RealGitWritePilotStatus.PREFLIGHT_READY
            and self.gate_snapshot.pilot_preflight_gates_passed() is not True
        ):
            raise ValueError("preflight ready pilot request requires preflight gates passed")
        return self


class RealGitWritePilotApproval(DomainModel):
    approval_id: str = Field(min_length=1, max_length=120)
    pilot_id: str = Field(min_length=1, max_length=120)
    approved_by: str | None = Field(default=None, max_length=120)
    approved_at: datetime | None = None
    one_shot_token_id: str | None = Field(default=None, min_length=1, max_length=120)
    token_hint: str | None = Field(default=None, max_length=200)
    expires_at: datetime | None = None
    approved_scope_summary: str | None = Field(default=None, max_length=1_000)
    decision: RealGitWritePilotApprovalDecision = RealGitWritePilotApprovalDecision.PENDING

    @field_validator(
        "approval_id",
        "pilot_id",
        "approved_by",
        "one_shot_token_id",
        "token_hint",
        mode="before",
    )
    @classmethod
    def trim_text(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    @field_validator("approved_at", "expires_at")
    @classmethod
    def normalize_optional_timestamps(cls, value: datetime | None) -> datetime | None:
        return _normalize_optional_datetime(value)

    @field_validator("approved_scope_summary", "token_hint")
    @classmethod
    def validate_safe_approval_text(cls, value: str | None) -> str | None:
        return reject_pilot_suspicious_text(value, "approval_text")

    @model_validator(mode="after")
    def validate_approval_contract(self) -> "RealGitWritePilotApproval":
        if self.decision == RealGitWritePilotApprovalDecision.APPROVED:
            if not self.approved_by:
                raise ValueError("approved decision requires approved_by")
            if self.approved_at is None:
                raise ValueError("approved decision requires approved_at")
            if not self.one_shot_token_id:
                raise ValueError("approved decision requires one_shot_token_id")
            if not self.token_hint:
                raise ValueError("approved decision requires token_hint")
            if self.expires_at is None:
                raise ValueError("approved decision requires expires_at")
            if self.expires_at <= self.approved_at:
                raise ValueError("expires_at must be later than approved_at")
        return self


class RealGitWritePilotRollbackPlan(DomainModel):
    rollback_plan_id: str = Field(min_length=1, max_length=120)
    pilot_id: str = Field(min_length=1, max_length=120)
    base_commit: str = Field(min_length=7, max_length=64)
    target_branch: str = Field(min_length=1, max_length=200)
    pilot_commit_id: str | None = Field(default=None, min_length=7, max_length=64)
    allowed_rollback_actions: list[str] = Field(min_length=1)
    forbidden_rollback_actions: list[str] = Field(min_length=1)
    safe_summary: str = Field(min_length=1, max_length=1_000)

    @field_validator("rollback_plan_id", "pilot_id", mode="before")
    @classmethod
    def trim_ids(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("base_commit")
    @classmethod
    def validate_base_commit(cls, value: str) -> str:
        return _validate_commit_id(value, "base_commit")

    @field_validator("pilot_commit_id")
    @classmethod
    def validate_pilot_commit_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_commit_id(value, "pilot_commit_id")

    @field_validator("target_branch")
    @classmethod
    def validate_target_branch(cls, value: str) -> str:
        return _validate_pilot_branch(value)

    @field_validator("allowed_rollback_actions")
    @classmethod
    def validate_allowed_actions(cls, values: list[str]) -> list[str]:
        normalized = _normalize_safe_text_list(values, "allowed_rollback_action")
        for action in normalized:
            lowered = action.lower()
            if any(pattern in lowered for pattern in _FORBIDDEN_ROLLBACK_ACTION_PATTERNS):
                raise ValueError("allowed_rollback_actions include forbidden action")
        if not normalized:
            raise ValueError("allowed_rollback_actions must not be empty")
        return normalized

    @field_validator("forbidden_rollback_actions")
    @classmethod
    def validate_forbidden_actions(cls, values: list[str]) -> list[str]:
        normalized = _normalize_safe_text_list(values, "forbidden_rollback_action")
        if not normalized:
            raise ValueError("forbidden_rollback_actions must not be empty")
        lowered_actions = " | ".join(action.lower() for action in normalized)
        if "reset --hard" not in lowered_actions:
            raise ValueError("forbidden_rollback_actions must block reset --hard")
        if "force push" not in lowered_actions and "--force" not in lowered_actions:
            raise ValueError("forbidden_rollback_actions must block force push")
        if "rollback script" not in lowered_actions:
            raise ValueError("forbidden_rollback_actions must block rollback scripts")
        return normalized

    @field_validator("safe_summary")
    @classmethod
    def validate_safe_summary(cls, value: str) -> str:
        normalized = reject_pilot_suspicious_text(value, "safe_summary")
        if normalized is None:
            raise ValueError("safe_summary must not be blank")
        return normalized


class RealGitWritePilotAuditEvent(DomainModel):
    event_id: str = Field(min_length=1, max_length=120)
    pilot_id: str = Field(min_length=1, max_length=120)
    event_type: str = Field(min_length=1, max_length=200)
    safe_summary: str = Field(min_length=1, max_length=1_000)
    timestamp: datetime
    append_only: bool = True
    metadata_count: int = Field(default=0, ge=0)

    @field_validator("event_id", "pilot_id", "event_type", mode="before")
    @classmethod
    def trim_required_text(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("safe_summary")
    @classmethod
    def validate_safe_summary(cls, value: str) -> str:
        normalized = reject_pilot_suspicious_text(value, "safe_summary")
        if normalized is None:
            raise ValueError("safe_summary must not be blank")
        return normalized

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)

    @model_validator(mode="after")
    def validate_audit_event_contract(self) -> "RealGitWritePilotAuditEvent":
        if self.append_only is not True:
            raise ValueError("pilot audit events must be append-only")
        return self
