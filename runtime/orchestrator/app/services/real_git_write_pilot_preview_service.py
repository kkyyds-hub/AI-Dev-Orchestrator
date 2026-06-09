"""Preview-only service for the P9 real Git write pilot.

The service builds a dry-run readback from explicit caller input only. It does
not inspect repositories, scan workspaces, launch executors, or perform Git
operations.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now
from app.domain.real_git_write_pilot import (
    REQUIRED_REAL_GIT_WRITE_PILOT_GATES,
    RealGitWritePilotBlockReason,
    RealGitWritePilotGateCheck,
    RealGitWritePilotGateName,
    RealGitWritePilotGateSnapshot,
    RealGitWritePilotGateStatus,
    RealGitWritePilotOperationKind,
    RealGitWritePilotRequest,
    RealGitWritePilotRollbackPlan,
    RealGitWritePilotStatus,
    reject_pilot_suspicious_text,
)


COMMAND_PLAN_SAFE_STEPS: tuple[str, ...] = (
    "validate pilot branch",
    "prepare doc-only file candidate",
    "prepare local commit candidate",
    "prepare rollback plan",
)
COMMAND_PLAN_FORBIDDEN_OPERATIONS: tuple[str, ...] = (
    "main write",
    "force push",
    "auto PR",
    "auto merge",
    "raw shell execution",
)


class RealGitWritePilotPreviewFeatureFlags(DomainModel):
    p9_real_executor_launch_enabled: bool = False
    product_runtime_git_write_enabled: bool = False
    real_git_write_pilot_enabled: bool = False

    def all_enabled(self) -> bool:
        return (
            self.p9_real_executor_launch_enabled is True
            and self.product_runtime_git_write_enabled is True
            and self.real_git_write_pilot_enabled is True
        )


class RealGitWritePilotPreviewGateInputs(DomainModel):
    executor_ready: bool = False
    workspace_bound: bool = False
    target_branch_allowed: bool = True
    diff_preview_ready: bool = False
    secret_scan_passed: bool = True
    human_approved: bool = False
    one_shot_token_issued: bool = False
    budget_within_limit: bool = True
    timeout_configured: bool = False
    rollback_plan_ready: bool = False
    append_only_audit_ready: bool = False
    force_push_requested: bool = False
    auto_pr_requested: bool = False
    auto_merge_requested: bool = False


class RealGitWritePilotPreviewRequest(DomainModel):
    pilot_id: str = Field(min_length=1, max_length=120)
    project_id: str = Field(min_length=1, max_length=120)
    run_id: str = Field(min_length=1, max_length=120)
    executor_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    repository_id: str = Field(min_length=1, max_length=120)
    base_commit: str = Field(min_length=7, max_length=64)
    target_branch: str = Field(min_length=1, max_length=200)
    file_paths: list[str] = Field(min_length=1)
    requested_by: str = Field(min_length=1, max_length=120)
    requested_at: datetime
    expires_at: datetime
    feature_flags: RealGitWritePilotPreviewFeatureFlags = Field(
        default_factory=RealGitWritePilotPreviewFeatureFlags,
    )
    gate_inputs: RealGitWritePilotPreviewGateInputs = Field(
        default_factory=RealGitWritePilotPreviewGateInputs,
    )
    diff_summary: str | None = Field(default=None, max_length=2_000)
    rollback_summary: str | None = Field(default=None, max_length=1_000)

    @field_validator(
        "pilot_id",
        "project_id",
        "run_id",
        "executor_id",
        "workspace_id",
        "repository_id",
        "target_branch",
        "requested_by",
        mode="before",
    )
    @classmethod
    def trim_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("requested_at", "expires_at")
    @classmethod
    def normalize_required_datetime(cls, value: datetime) -> datetime:
        normalized = ensure_utc_datetime(value)
        if normalized is None:
            raise ValueError("datetime must not be None")
        return normalized

    @field_validator("diff_summary", "rollback_summary")
    @classmethod
    def validate_safe_summary(cls, value: str | None) -> str | None:
        return reject_pilot_suspicious_text(value, "pilot_preview_summary")


class RealGitWritePilotCommandPlan(DomainModel):
    plan_id: str = Field(min_length=1, max_length=120)
    pilot_id: str = Field(min_length=1, max_length=120)
    target_branch: str = Field(min_length=1, max_length=200)
    file_paths: list[str] = Field(min_length=1)
    operation_kinds: list[RealGitWritePilotOperationKind] = Field(min_length=1)
    safe_steps: list[str] = Field(min_length=1)
    forbidden_operations: list[str] = Field(min_length=1)
    created_at: datetime

    @field_validator("safe_steps", "forbidden_operations")
    @classmethod
    def validate_safe_text_items(cls, values: list[str]) -> list[str]:
        normalized_items: list[str] = []
        for value in values:
            safe_value = reject_pilot_suspicious_text(value, "command_plan_text")
            if safe_value is None:
                continue
            normalized_items.append(safe_value)
        if not normalized_items:
            raise ValueError("command plan text items must not be empty")
        return normalized_items

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        normalized = ensure_utc_datetime(value)
        if normalized is None:
            raise ValueError("created_at must not be None")
        return normalized


class RealGitWritePilotPreview(DomainModel):
    pilot_id: str
    status: RealGitWritePilotStatus
    gate_snapshot: RealGitWritePilotGateSnapshot
    command_plan: RealGitWritePilotCommandPlan
    rollback_plan: RealGitWritePilotRollbackPlan
    safe_summary: str
    audit_event_summaries: list[str]
    product_runtime_git_write_executed: bool = False
    real_executor_started: bool = False
    created_at: datetime

    @field_validator("safe_summary")
    @classmethod
    def validate_safe_summary(cls, value: str) -> str:
        normalized = reject_pilot_suspicious_text(value, "safe_summary")
        if normalized is None:
            raise ValueError("safe_summary must not be blank")
        return normalized

    @field_validator("audit_event_summaries")
    @classmethod
    def validate_audit_summaries(cls, values: list[str]) -> list[str]:
        normalized_items: list[str] = []
        for value in values:
            safe_value = reject_pilot_suspicious_text(value, "audit_event_summary")
            if safe_value is not None:
                normalized_items.append(safe_value)
        return normalized_items

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        normalized = ensure_utc_datetime(value)
        if normalized is None:
            raise ValueError("created_at must not be None")
        return normalized


class RealGitWritePilotPreviewService:
    """Build preview-only readback for a future real Git write pilot."""

    def build_preview(
        self,
        request: RealGitWritePilotPreviewRequest,
    ) -> RealGitWritePilotPreview:
        created_at = utc_now()
        gate_snapshot = self._build_gate_snapshot(request, created_at)
        status = self._derive_status(gate_snapshot)
        pilot_request = RealGitWritePilotRequest(
            pilot_id=request.pilot_id,
            project_id=request.project_id,
            run_id=request.run_id,
            executor_id=request.executor_id,
            workspace_id=request.workspace_id,
            repository_id=request.repository_id,
            base_commit=request.base_commit,
            target_branch=request.target_branch,
            file_paths=request.file_paths,
            requested_by=request.requested_by,
            requested_at=request.requested_at,
            expires_at=request.expires_at,
            status=status,
            gate_snapshot=gate_snapshot,
            product_runtime_git_write_executed=False,
            real_executor_started=False,
        )
        command_plan = self._build_command_plan(pilot_request, created_at)
        rollback_plan = self._build_rollback_plan(request, created_at)

        return RealGitWritePilotPreview(
            pilot_id=pilot_request.pilot_id,
            status=status,
            gate_snapshot=gate_snapshot,
            command_plan=command_plan,
            rollback_plan=rollback_plan,
            safe_summary=(
                "Preview generated as dry-run readback only; no executor or product "
                "runtime write was started."
            ),
            audit_event_summaries=[
                "Preview request accepted from explicit caller input.",
                "Gate snapshot and semantic plan generated without repository side effects.",
            ],
            product_runtime_git_write_executed=False,
            real_executor_started=False,
            created_at=created_at,
        )

    def _build_gate_snapshot(
        self,
        request: RealGitWritePilotPreviewRequest,
        checked_at: datetime,
    ) -> RealGitWritePilotGateSnapshot:
        inputs = request.gate_inputs
        checks = {
            RealGitWritePilotGateName.FEATURE_FLAG: self._gate(
                RealGitWritePilotGateName.FEATURE_FLAG,
                request.feature_flags.all_enabled(),
                RealGitWritePilotBlockReason.FEATURE_FLAG_DISABLED,
                "pilot feature flags evaluated from request input",
                checked_at,
            ),
            RealGitWritePilotGateName.EXECUTOR_READINESS: self._gate(
                RealGitWritePilotGateName.EXECUTOR_READINESS,
                inputs.executor_ready,
                RealGitWritePilotBlockReason.EXECUTOR_NOT_READY,
                "executor readiness evaluated from request input",
                checked_at,
            ),
            RealGitWritePilotGateName.WORKSPACE_WORKTREE: self._gate(
                RealGitWritePilotGateName.WORKSPACE_WORKTREE,
                inputs.workspace_bound,
                RealGitWritePilotBlockReason.WORKSPACE_NOT_BOUND,
                "workspace binding evaluated from request input",
                checked_at,
            ),
            RealGitWritePilotGateName.TARGET_BRANCH_ALLOWLIST: self._gate(
                RealGitWritePilotGateName.TARGET_BRANCH_ALLOWLIST,
                inputs.target_branch_allowed,
                RealGitWritePilotBlockReason.TARGET_BRANCH_NOT_ALLOWED,
                "target branch allowlist evaluated from request input",
                checked_at,
            ),
            RealGitWritePilotGateName.DIFF_PREVIEW: self._gate(
                RealGitWritePilotGateName.DIFF_PREVIEW,
                inputs.diff_preview_ready and request.diff_summary is not None,
                RealGitWritePilotBlockReason.REAL_EXECUTION_NOT_STARTED,
                "diff preview summary evaluated from request input",
                checked_at,
            ),
            RealGitWritePilotGateName.SECRET_SCAN: self._gate(
                RealGitWritePilotGateName.SECRET_SCAN,
                inputs.secret_scan_passed,
                RealGitWritePilotBlockReason.SECRET_DETECTED,
                "sensitive text scan result evaluated from request input",
                checked_at,
            ),
            RealGitWritePilotGateName.HUMAN_APPROVAL: self._gate(
                RealGitWritePilotGateName.HUMAN_APPROVAL,
                inputs.human_approved,
                RealGitWritePilotBlockReason.APPROVAL_MISSING,
                "human approval remains separate from preview generation",
                checked_at,
                pending_when_false=True,
            ),
            RealGitWritePilotGateName.ONE_SHOT_TOKEN: self._gate(
                RealGitWritePilotGateName.ONE_SHOT_TOKEN,
                inputs.one_shot_token_issued,
                RealGitWritePilotBlockReason.TOKEN_MISSING_OR_EXPIRED,
                "one-shot approval token remains separate from preview generation",
                checked_at,
                pending_when_false=True,
            ),
            RealGitWritePilotGateName.BUDGET_COST: self._gate(
                RealGitWritePilotGateName.BUDGET_COST,
                inputs.budget_within_limit,
                RealGitWritePilotBlockReason.BUDGET_EXCEEDED,
                "budget gate evaluated from request input",
                checked_at,
            ),
            RealGitWritePilotGateName.TIMEOUT_KILL_SWITCH: self._gate(
                RealGitWritePilotGateName.TIMEOUT_KILL_SWITCH,
                inputs.timeout_configured,
                RealGitWritePilotBlockReason.TIMEOUT_NOT_CONFIGURED,
                "timeout gate evaluated from request input",
                checked_at,
            ),
            RealGitWritePilotGateName.ROLLBACK_PLAN: self._gate(
                RealGitWritePilotGateName.ROLLBACK_PLAN,
                inputs.rollback_plan_ready and request.rollback_summary is not None,
                RealGitWritePilotBlockReason.ROLLBACK_PLAN_MISSING,
                "rollback plan summary evaluated from request input",
                checked_at,
            ),
            RealGitWritePilotGateName.NO_DIRECT_MAIN_WRITE: self._gate(
                RealGitWritePilotGateName.NO_DIRECT_MAIN_WRITE,
                True,
                RealGitWritePilotBlockReason.MAIN_BRANCH_BLOCKED,
                "pilot branch pattern excludes protected branches",
                checked_at,
            ),
            RealGitWritePilotGateName.NO_FORCE_PUSH: self._gate(
                RealGitWritePilotGateName.NO_FORCE_PUSH,
                not inputs.force_push_requested,
                RealGitWritePilotBlockReason.FORCE_PUSH_REQUESTED,
                "force push is not part of preview-only scope",
                checked_at,
            ),
            RealGitWritePilotGateName.NO_AUTO_PR_MERGE: self._gate(
                RealGitWritePilotGateName.NO_AUTO_PR_MERGE,
                not inputs.auto_pr_requested and not inputs.auto_merge_requested,
                RealGitWritePilotBlockReason.AUTO_PR_OR_MERGE_REQUESTED,
                "auto PR and auto merge are not part of preview-only scope",
                checked_at,
            ),
            RealGitWritePilotGateName.APPEND_ONLY_AUDIT: self._gate(
                RealGitWritePilotGateName.APPEND_ONLY_AUDIT,
                inputs.append_only_audit_ready,
                RealGitWritePilotBlockReason.AUDIT_MISSING,
                "append-only audit readiness evaluated from request input",
                checked_at,
            ),
            RealGitWritePilotGateName.POST_WRITE_VERIFY: RealGitWritePilotGateCheck(
                gate_name=RealGitWritePilotGateName.POST_WRITE_VERIFY,
                status=RealGitWritePilotGateStatus.PENDING,
                passed=False,
                checked_at=checked_at,
                safe_summary="post-write verification is unavailable before execution",
            ),
            RealGitWritePilotGateName.MANUAL_FINAL_CONFIRMATION: RealGitWritePilotGateCheck(
                gate_name=RealGitWritePilotGateName.MANUAL_FINAL_CONFIRMATION,
                status=RealGitWritePilotGateStatus.PENDING,
                passed=False,
                checked_at=checked_at,
                safe_summary="manual final confirmation is unavailable before execution",
            ),
        }
        return RealGitWritePilotGateSnapshot(
            gate_checks=[checks[gate] for gate in REQUIRED_REAL_GIT_WRITE_PILOT_GATES],
            evaluated_at=checked_at,
        )

    def _gate(
        self,
        gate_name: RealGitWritePilotGateName,
        passed: bool,
        block_reason: RealGitWritePilotBlockReason,
        safe_summary: str,
        checked_at: datetime,
        pending_when_false: bool = False,
    ) -> RealGitWritePilotGateCheck:
        if passed:
            return RealGitWritePilotGateCheck(
                gate_name=gate_name,
                status=RealGitWritePilotGateStatus.PASSED,
                passed=True,
                checked_at=checked_at,
                safe_summary=safe_summary,
            )
        if pending_when_false:
            return RealGitWritePilotGateCheck(
                gate_name=gate_name,
                status=RealGitWritePilotGateStatus.PENDING,
                passed=False,
                checked_at=checked_at,
                safe_summary=safe_summary,
            )
        return RealGitWritePilotGateCheck(
            gate_name=gate_name,
            status=RealGitWritePilotGateStatus.BLOCKED,
            passed=False,
            block_reason=block_reason,
            checked_at=checked_at,
            safe_summary=safe_summary,
        )

    def _derive_status(
        self,
        gate_snapshot: RealGitWritePilotGateSnapshot,
    ) -> RealGitWritePilotStatus:
        if gate_snapshot.failed_gates():
            return RealGitWritePilotStatus.BLOCKED
        if gate_snapshot.pilot_preflight_gates_passed():
            return RealGitWritePilotStatus.PREFLIGHT_READY
        if (
            gate_snapshot.get_gate(RealGitWritePilotGateName.HUMAN_APPROVAL).passed
            is not True
        ):
            return RealGitWritePilotStatus.APPROVAL_REQUIRED
        if (
            gate_snapshot.get_gate(RealGitWritePilotGateName.ONE_SHOT_TOKEN).passed
            is not True
        ):
            return RealGitWritePilotStatus.APPROVED
        return RealGitWritePilotStatus.PREVIEW_READY

    def _build_command_plan(
        self,
        pilot_request: RealGitWritePilotRequest,
        created_at: datetime,
    ) -> RealGitWritePilotCommandPlan:
        return RealGitWritePilotCommandPlan(
            plan_id=f"pilot-command-plan-{pilot_request.pilot_id}",
            pilot_id=pilot_request.pilot_id,
            target_branch=pilot_request.target_branch,
            file_paths=pilot_request.file_paths,
            operation_kinds=pilot_request.operation_kinds,
            safe_steps=list(COMMAND_PLAN_SAFE_STEPS),
            forbidden_operations=list(COMMAND_PLAN_FORBIDDEN_OPERATIONS),
            created_at=created_at,
        )

    def _build_rollback_plan(
        self,
        request: RealGitWritePilotPreviewRequest,
        created_at: datetime,
    ) -> RealGitWritePilotRollbackPlan:
        return RealGitWritePilotRollbackPlan(
            rollback_plan_id=f"pilot-rollback-{request.pilot_id}",
            pilot_id=request.pilot_id,
            base_commit=request.base_commit,
            target_branch=request.target_branch,
            pilot_commit_id=None,
            allowed_rollback_actions=[
                "create revert commit for the pilot candidate",
                "delete unmerged pilot branch manually",
            ],
            forbidden_rollback_actions=[
                "reset --hard is forbidden",
                "force push is forbidden",
                "automatic rollback script is forbidden",
            ],
            safe_summary=(
                request.rollback_summary
                or "Rollback remains a contract-only plan; no cleanup was run."
            ),
        )
