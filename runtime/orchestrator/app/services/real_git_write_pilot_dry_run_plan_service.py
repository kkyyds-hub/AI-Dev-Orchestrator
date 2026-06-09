"""Dry-run semantic plan service for the P9 real Git write pilot.

The service turns preview and readiness readbacks into a semantic plan only.
It never emits raw shell commands, reads local host state, starts executors, or
performs repository operations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now
from app.domain.real_git_write_pilot import (
    RealGitWritePilotGateStatus,
    RealGitWritePilotStatus,
    reject_pilot_suspicious_text,
)
from app.services.real_git_write_pilot_preview_service import RealGitWritePilotPreview
from app.services.real_git_write_pilot_readiness_service import (
    RealGitWritePilotReadinessReadback,
)


DRY_RUN_SEMANTIC_STEP_DEFINITIONS: tuple[tuple[str, str, bool], ...] = (
    (
        "verify_executor_readiness_readback",
        "verify executor readiness readback",
        False,
    ),
    (
        "verify_workspace_binding_readback",
        "verify workspace binding readback",
        False,
    ),
    (
        "verify_pilot_branch_allowlist",
        "verify pilot branch allowlist",
        False,
    ),
    (
        "verify_docs_only_file_scope",
        "verify docs-only file scope",
        False,
    ),
    (
        "verify_preview_gate_snapshot",
        "verify preview gate snapshot",
        False,
    ),
    (
        "prepare_local_branch_candidate_description",
        "prepare local branch candidate description",
        False,
    ),
    (
        "prepare_doc_only_file_candidate_description",
        "prepare doc-only file candidate description",
        False,
    ),
    (
        "prepare_local_commit_candidate_description",
        "prepare local commit candidate description",
        False,
    ),
    (
        "prepare_rollback_plan_description",
        "prepare rollback plan description",
        False,
    ),
    (
        "wait_for_manual_approval",
        "wait for manual approval",
        True,
    ),
    (
        "wait_for_one_shot_approval_grant",
        "wait for one-shot approval grant",
        True,
    ),
)

DRY_RUN_FORBIDDEN_OPERATIONS: tuple[str, ...] = (
    "raw shell execution",
    "direct main write",
    "git force push",
    "automatic PR creation",
    "automatic merge",
    "branch delete",
    "reset hard",
    "tag creation",
    "stash operation",
)


class RealGitWritePilotDryRunPlanRequest(DomainModel):
    pilot_id: str = Field(min_length=1, max_length=120)
    preview: RealGitWritePilotPreview
    readiness: RealGitWritePilotReadinessReadback
    requested_by: str = Field(min_length=1, max_length=120)
    requested_at: datetime

    @field_validator("pilot_id", "requested_by", mode="before")
    @classmethod
    def trim_required_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("requested_at")
    @classmethod
    def normalize_requested_at(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)

    @model_validator(mode="after")
    def validate_readback_ids(self) -> "RealGitWritePilotDryRunPlanRequest":
        if self.preview.pilot_id != self.pilot_id:
            raise ValueError("preview pilot_id must match request pilot_id")
        if self.readiness.pilot_id != self.pilot_id:
            raise ValueError("readiness pilot_id must match request pilot_id")
        return self


class RealGitWritePilotDryRunStep(DomainModel):
    step_id: str = Field(min_length=1, max_length=120)
    step_order: int = Field(ge=1)
    step_kind: str = Field(min_length=1, max_length=120)
    safe_summary: str = Field(min_length=1, max_length=1_000)
    requires_human_confirmation: bool = False
    produces_repository_side_effect: bool = False

    @field_validator("step_id", "step_kind", "safe_summary")
    @classmethod
    def validate_safe_text(cls, value: str) -> str:
        normalized = reject_pilot_suspicious_text(value, "dry_run_step")
        if normalized is None:
            raise ValueError("dry-run step text must not be blank")
        return normalized

    @model_validator(mode="after")
    def enforce_no_side_effects(self) -> "RealGitWritePilotDryRunStep":
        if self.produces_repository_side_effect is not False:
            raise ValueError("dry-run steps must not produce repository side effects")
        return self


class RealGitWritePilotGateSnapshotSummary(DomainModel):
    total_gates: int
    passed_gates: int
    blocked_gates: int
    pending_gates: int
    not_applicable_gates: int
    all_passed: bool
    blocking_reasons: list[str]


class RealGitWritePilotDryRunPlan(DomainModel):
    pilot_id: str
    readiness_ready_for_preview: bool
    preview_status: RealGitWritePilotStatus
    gate_snapshot_summary: RealGitWritePilotGateSnapshotSummary
    semantic_steps: list[RealGitWritePilotDryRunStep] = Field(min_length=1)
    forbidden_operations: list[str] = Field(min_length=1)
    rollback_plan_summary: str
    audit_event_summaries: list[str]
    dry_run_ready: bool
    ready_for_execution: bool = False
    product_runtime_git_write_executed: bool = False
    real_executor_started: bool = False
    created_at: datetime

    @field_validator("forbidden_operations", "audit_event_summaries")
    @classmethod
    def validate_safe_text_items(cls, values: list[str]) -> list[str]:
        normalized_items: list[str] = []
        seen_items: set[str] = set()
        for value in values:
            safe_value = reject_pilot_suspicious_text(value, "dry_run_plan_text")
            if safe_value is not None and safe_value not in seen_items:
                normalized_items.append(safe_value)
                seen_items.add(safe_value)
        if not normalized_items:
            raise ValueError("dry-run plan text items must not be empty")
        return normalized_items

    @field_validator("rollback_plan_summary")
    @classmethod
    def validate_rollback_summary(cls, value: str) -> str:
        normalized = reject_pilot_suspicious_text(value, "rollback_plan_summary")
        if normalized is None:
            raise ValueError("rollback_plan_summary must not be blank")
        return normalized

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)

    @model_validator(mode="after")
    def enforce_no_execution_contract(self) -> "RealGitWritePilotDryRunPlan":
        if self.ready_for_execution is not False:
            raise ValueError("dry-run plan must not mark execution ready")
        if self.product_runtime_git_write_executed is not False:
            raise ValueError("product runtime Git write must remain Not started")
        if self.real_executor_started is not False:
            raise ValueError("real executor must remain Not started")
        return self


class RealGitWritePilotDryRunPlanService:
    """Build a dry-run semantic command plan without execution capability."""

    def build_plan(
        self,
        request: RealGitWritePilotDryRunPlanRequest,
    ) -> RealGitWritePilotDryRunPlan:
        created_at = utc_now()
        preview_status = request.preview.status
        dry_run_ready = (
            request.readiness.ready_for_preview is True
            and preview_status != RealGitWritePilotStatus.BLOCKED
        )

        return RealGitWritePilotDryRunPlan(
            pilot_id=request.pilot_id,
            readiness_ready_for_preview=request.readiness.ready_for_preview,
            preview_status=preview_status,
            gate_snapshot_summary=_summarize_gate_snapshot(request.preview),
            semantic_steps=_build_semantic_steps(request.pilot_id),
            forbidden_operations=list(DRY_RUN_FORBIDDEN_OPERATIONS),
            rollback_plan_summary=request.preview.rollback_plan.safe_summary,
            audit_event_summaries=[
                "Dry-run plan generated from preview and readiness readbacks.",
                "No executor launch, repository write, or host workspace inspection occurred.",
            ],
            dry_run_ready=dry_run_ready,
            ready_for_execution=False,
            product_runtime_git_write_executed=False,
            real_executor_started=False,
            created_at=created_at,
        )


def _build_semantic_steps(pilot_id: str) -> list[RealGitWritePilotDryRunStep]:
    return [
        RealGitWritePilotDryRunStep(
            step_id=f"{pilot_id}-dry-run-step-{index}",
            step_order=index,
            step_kind=step_kind,
            safe_summary=safe_summary,
            requires_human_confirmation=requires_human_confirmation,
            produces_repository_side_effect=False,
        )
        for index, (
            step_kind,
            safe_summary,
            requires_human_confirmation,
        ) in enumerate(DRY_RUN_SEMANTIC_STEP_DEFINITIONS, start=1)
    ]


def _summarize_gate_snapshot(
    preview: RealGitWritePilotPreview,
) -> RealGitWritePilotGateSnapshotSummary:
    checks = preview.gate_snapshot.gate_checks
    return RealGitWritePilotGateSnapshotSummary(
        total_gates=len(checks),
        passed_gates=sum(
            1 for check in checks if check.status == RealGitWritePilotGateStatus.PASSED
        ),
        blocked_gates=sum(
            1 for check in checks if check.status == RealGitWritePilotGateStatus.BLOCKED
        ),
        pending_gates=sum(
            1 for check in checks if check.status == RealGitWritePilotGateStatus.PENDING
        ),
        not_applicable_gates=sum(
            1
            for check in checks
            if check.status == RealGitWritePilotGateStatus.NOT_APPLICABLE
        ),
        all_passed=preview.gate_snapshot.all_passed,
        blocking_reasons=[
            reason.value for reason in preview.gate_snapshot.blocking_reasons
        ],
    )


def _normalize_required_datetime(value: datetime) -> datetime:
    normalized = ensure_utc_datetime(value)
    if normalized is None:
        raise ValueError("datetime must not be None")
    return normalized
