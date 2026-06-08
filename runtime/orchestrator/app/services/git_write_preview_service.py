"""Preview-only GitWrite service for GitWrite-C.

This module builds dry-run preview contracts from explicit caller input only.
It never reads repository state, reads environment values, launches host
processes, persists state, calls API or worker layers, approves writes, opens
pull requests, or performs product runtime Git writes.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now
from app.domain.git_write import (
    GitWriteBlockReason,
    GitWriteIntent,
    GitWritePreview,
    GitWritePreviewFile,
    GitWritePreviewStatus,
    GitWriteRollbackPlan,
    GitWriteSafetyGateCheck,
    GitWriteSafetyGateName,
    GitWriteSafetyGateSnapshot,
    GitWriteSafetyGateStatus,
    normalize_string_list,
    reject_suspicious_secret_text,
)


_SUSPECT_CREDENTIAL_PATTERN = re.compile(
    r"(api\s*[_-]?\s*key|token|secret|password|bearer|sk-|begin\s+private\s+key)",
    re.IGNORECASE,
)
_DESTRUCTIVE_OPERATION_MARKERS = frozenset(
    {
        "reset",
        "rebase",
        "stash",
        "tag",
        "delete_branch",
        "branch_delete",
        "checkout",
        "switch",
        "merge",
    }
)


class GitWriteChangedFileInput(DomainModel):
    """Explicit caller-provided file summary for preview generation."""

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
        return normalize_string_list([value])[0]

    @field_validator("change_type", mode="before")
    @classmethod
    def trim_change_type(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("safe_summary")
    @classmethod
    def validate_safe_summary(cls, value: str | None) -> str | None:
        return reject_suspicious_secret_text(value, "safe_summary")


class GitWritePreviewRequest(DomainModel):
    """Preview-only request built from explicit, already-collected evidence."""

    intent: GitWriteIntent
    changed_files: list[GitWriteChangedFileInput] = Field(min_length=1)
    allowed_branches: list[str] = Field(default_factory=list)
    feature_flag_enabled: bool = False
    diff_text: str | None = Field(default=None, max_length=50_000)
    diff_summary: str | None = Field(default=None, max_length=2_000)
    operation_kinds: list[str] = Field(default_factory=list)
    force_push_requested: bool = False
    destructive_operation_requested: bool = False
    ci_trigger_requested: bool = False
    audit_event_planned: bool = True
    product_runtime_git_write_executed: bool = False
    rollback_base_branch_hint: str | None = Field(default=None, max_length=200)
    rollback_base_commit_hint: str | None = Field(default=None, max_length=200)
    requested_at: datetime | None = None

    @field_validator("allowed_branches")
    @classmethod
    def normalize_allowed_branches(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            branch = value.strip()
            if not branch or branch in seen:
                continue
            normalized.append(branch)
            seen.add(branch)
        return normalized

    @field_validator("diff_text", "diff_summary", mode="before")
    @classmethod
    def trim_optional_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("operation_kinds")
    @classmethod
    def normalize_operation_kinds(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            operation = value.strip().lower().replace("-", "_")
            if not operation or operation in seen:
                continue
            normalized.append(operation)
            seen.add(operation)
        return normalized

    @field_validator("rollback_base_branch_hint")
    @classmethod
    def validate_rollback_base_branch_hint(cls, value: str | None) -> str | None:
        if value is None:
            return None
        branch = value.strip()
        return branch or None

    @field_validator("rollback_base_commit_hint")
    @classmethod
    def validate_rollback_base_commit_hint(cls, value: str | None) -> str | None:
        return reject_suspicious_secret_text(value, "rollback_base_commit_hint")

    @field_validator("requested_at")
    @classmethod
    def normalize_requested_at(cls, value: datetime | None) -> datetime | None:
        return ensure_utc_datetime(value)

    @model_validator(mode="after")
    def validate_changed_files_match_intent(self) -> "GitWritePreviewRequest":
        intent_paths = set(self.intent.file_paths)
        changed_paths = {changed_file.path for changed_file in self.changed_files}
        missing_from_preview = intent_paths - changed_paths
        if missing_from_preview:
            raise ValueError("changed_files must include every intent file path")
        return self

    def effective_operation_kinds(self) -> list[str]:
        intent_operations = [operation.value for operation in self.intent.operation_kinds]
        return [*intent_operations, *self.operation_kinds]


class SecretScanner:
    """Scans only caller-provided text and returns redacted findings."""

    def has_suspected_credential(self, *texts: str | None) -> bool:
        return any(
            text is not None and _SUSPECT_CREDENTIAL_PATTERN.search(text) is not None
            for text in texts
        )


class TargetBranchValidator:
    """Validates target branches against an explicit allowlist."""

    def is_allowed(self, target_branch: str, allowed_branches: list[str]) -> bool:
        return bool(allowed_branches) and target_branch in allowed_branches


class ForcePushDetector:
    """Detects force-push intent from explicit operation names and flags only."""

    def is_force_push_requested(
        self,
        operation_kinds: list[str],
        force_push_requested: bool,
    ) -> bool:
        if force_push_requested:
            return True
        return any("force" in operation and "push" in operation for operation in operation_kinds)


class RollbackPlanGenerator:
    """Builds rollback plan contracts without performing cleanup."""

    def generate(
        self,
        intent: GitWriteIntent,
        request: GitWritePreviewRequest,
        generated_at: datetime,
    ) -> GitWriteRollbackPlan:
        branch_hint = request.rollback_base_branch_hint or intent.base_branch or intent.target_branch
        return GitWriteRollbackPlan(
            plan_id=f"rollback-{intent.intent_id}",
            summary=(
                "Restore the target branch from recorded branch and commit hints "
                "before any future write step."
            ),
            restore_branch_hint=branch_hint,
            restore_commit_hint=request.rollback_base_commit_hint,
            generated_at=generated_at,
        )


class GitWritePreviewService:
    """Build GitWrite dry-run previews without side effects."""

    def __init__(
        self,
        secret_scanner: SecretScanner | None = None,
        branch_validator: TargetBranchValidator | None = None,
        force_push_detector: ForcePushDetector | None = None,
        rollback_plan_generator: RollbackPlanGenerator | None = None,
    ) -> None:
        self._secret_scanner = secret_scanner or SecretScanner()
        self._branch_validator = branch_validator or TargetBranchValidator()
        self._force_push_detector = force_push_detector or ForcePushDetector()
        self._rollback_plan_generator = rollback_plan_generator or RollbackPlanGenerator()

    def build_preview(self, request: GitWritePreviewRequest) -> GitWritePreview:
        evaluated_at = request.requested_at or utc_now()
        rollback_plan = self._rollback_plan_generator.generate(
            intent=request.intent,
            request=request,
            generated_at=evaluated_at,
        )
        secret_detected = self._secret_scanner.has_suspected_credential(
            request.diff_text,
            request.diff_summary,
            *(changed_file.safe_summary for changed_file in request.changed_files),
        ) or any(changed_file.contains_secret for changed_file in request.changed_files)
        operation_kinds = request.effective_operation_kinds()
        force_push_detected = self._force_push_detector.is_force_push_requested(
            operation_kinds=operation_kinds,
            force_push_requested=request.force_push_requested,
        )
        destructive_operation_detected = (
            request.destructive_operation_requested
            or _contains_destructive_operation(operation_kinds)
        )

        gate_checks = [
            _gate(
                GitWriteSafetyGateName.FEATURE_FLAG,
                request.feature_flag_enabled,
                GitWriteBlockReason.FEATURE_FLAG_DISABLED,
            ),
            _gate(
                GitWriteSafetyGateName.WORKSPACE_BOUND,
                bool(request.intent.workspace_id),
                GitWriteBlockReason.WORKSPACE_NOT_BOUND,
            ),
            _gate(
                GitWriteSafetyGateName.TARGET_BRANCH_ALLOWLIST,
                self._branch_validator.is_allowed(
                    request.intent.target_branch,
                    request.allowed_branches,
                ),
                GitWriteBlockReason.TARGET_BRANCH_NOT_ALLOWED,
            ),
            _gate(
                GitWriteSafetyGateName.DIFF_PREVIEW,
                request.diff_text is not None or request.diff_summary is not None,
                GitWriteBlockReason.DIFF_PREVIEW_MISSING,
            ),
            _gate(
                GitWriteSafetyGateName.SECRET_SCAN,
                not secret_detected,
                GitWriteBlockReason.SECRET_DETECTED,
            ),
            _gate(
                GitWriteSafetyGateName.REVIEWED_FILES,
                all(changed_file.reviewed for changed_file in request.changed_files),
                GitWriteBlockReason.UNREVIEWED_FILES,
            ),
            _gate(
                GitWriteSafetyGateName.FORCE_PUSH_DETECTION,
                not force_push_detected,
                GitWriteBlockReason.FORCE_PUSH_DETECTED,
            ),
            _gate(
                GitWriteSafetyGateName.DESTRUCTIVE_OPERATION_BLOCK,
                not destructive_operation_detected,
                GitWriteBlockReason.DESTRUCTIVE_OPERATION_DETECTED,
            ),
            _gate(
                GitWriteSafetyGateName.CI_TRIGGER_CONTROL,
                not request.ci_trigger_requested,
                GitWriteBlockReason.CI_TRIGGER_NOT_CONFIRMED,
            ),
            _pending_gate(
                GitWriteSafetyGateName.HUMAN_APPROVAL,
            ),
            _pending_gate(
                GitWriteSafetyGateName.ONE_SHOT_TOKEN,
            ),
            _gate(
                GitWriteSafetyGateName.ROLLBACK_PLAN,
                rollback_plan is not None,
                GitWriteBlockReason.ROLLBACK_PLAN_MISSING,
            ),
            _gate(
                GitWriteSafetyGateName.DRY_RUN,
                True,
                GitWriteBlockReason.DRY_RUN_MISSING,
            ),
            _gate(
                GitWriteSafetyGateName.AUDIT_EVENT,
                request.audit_event_planned,
                GitWriteBlockReason.AUDIT_EVENT_MISSING,
            ),
            _gate(
                GitWriteSafetyGateName.NO_PRODUCT_RUNTIME_GIT_WRITE,
                not request.product_runtime_git_write_executed,
                GitWriteBlockReason.PRODUCT_RUNTIME_GIT_WRITE_FORBIDDEN,
            ),
        ]
        safety_snapshot = GitWriteSafetyGateSnapshot(
            gate_checks=gate_checks,
            evaluated_at=evaluated_at,
        )
        preview_status = (
            GitWritePreviewStatus.READY
            if safety_snapshot.preview_gates_passed()
            else GitWritePreviewStatus.BLOCKED
        )

        return GitWritePreview(
            preview_id=f"preview-{request.intent.intent_id}",
            intent_id=request.intent.intent_id,
            status=preview_status,
            target_branch=request.intent.target_branch,
            files=[
                GitWritePreviewFile(
                    path=changed_file.path,
                    change_type=changed_file.change_type,
                    additions=changed_file.additions,
                    deletions=changed_file.deletions,
                    reviewed=changed_file.reviewed,
                    contains_secret=changed_file.contains_secret,
                    safe_summary=changed_file.safe_summary,
                )
                for changed_file in request.changed_files
            ],
            diff_summary=_safe_diff_summary(request.diff_summary, secret_detected),
            commit_message_preview=(
                None if secret_detected else request.intent.commit_message
            ),
            rollback_plan=rollback_plan,
            safety_snapshot=safety_snapshot,
            created_at=evaluated_at,
        )


def _gate(
    gate_name: GitWriteSafetyGateName,
    passed: bool,
    block_reason: GitWriteBlockReason,
) -> GitWriteSafetyGateCheck:
    if passed:
        return GitWriteSafetyGateCheck(
            gate_name=gate_name,
            status=GitWriteSafetyGateStatus.PASSED,
            passed=True,
        )
    return GitWriteSafetyGateCheck(
        gate_name=gate_name,
        status=GitWriteSafetyGateStatus.BLOCKED,
        passed=False,
        block_reason=block_reason,
    )


def _pending_gate(
    gate_name: GitWriteSafetyGateName,
) -> GitWriteSafetyGateCheck:
    return GitWriteSafetyGateCheck(
        gate_name=gate_name,
        status=GitWriteSafetyGateStatus.PENDING,
        passed=False,
    )


def _contains_destructive_operation(operation_kinds: list[str]) -> bool:
    normalized = {operation.strip().lower().replace("-", "_") for operation in operation_kinds}
    return bool(normalized.intersection(_DESTRUCTIVE_OPERATION_MARKERS))


def _safe_diff_summary(
    diff_summary: str | None,
    secret_detected: bool,
) -> str | None:
    if secret_detected:
        return "Change summary omitted due to sensitive content."
    return diff_summary
