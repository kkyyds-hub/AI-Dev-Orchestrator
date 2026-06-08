"""Preview-only launch contract service for P8-E.

This service builds human-readable executor launch previews from safe executor
metadata. It never launches external processes, creates runtime sessions, reads
local native configuration, reads environment values, or persists state.
"""

from __future__ import annotations

from pydantic import field_validator

from app.domain._base import DomainModel
from app.domain.executor_config import (
    ExecutorLaunchPreview,
    ExecutorLaunchSafetyFlags,
    ExecutorProfile,
    ExecutorProvider,
    ExecutorStatus,
)
from app.services.executor_config_discovery_service import ExecutorConfigDiscoveryService


class ExecutorLaunchPreviewRequest(DomainModel):
    """Safe request context for a human-readable preview only."""

    operation_intent: str | None = None
    project_id: str | None = None
    task_id: str | None = None
    model_name: str | None = None
    workspace_bound: bool = False
    launch_cwd_hint: str | None = None
    require_human_confirmation: bool = True

    @field_validator(
        "operation_intent",
        "project_id",
        "task_id",
        "model_name",
        "launch_cwd_hint",
        mode="before",
    )
    @classmethod
    def trim_optional_string(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class ExecutorLaunchPreviewService:
    """Build launch previews without starting any runtime executor."""

    def __init__(self, discovery_service: ExecutorConfigDiscoveryService | None = None) -> None:
        self._discovery_service = discovery_service or ExecutorConfigDiscoveryService()

    def build_preview(
        self,
        executor_id: str,
        request: ExecutorLaunchPreviewRequest | None = None,
    ) -> ExecutorLaunchPreview | None:
        profile = self._discovery_service.get_profile(executor_id)
        if profile is None:
            return None

        safe_request = request or ExecutorLaunchPreviewRequest()
        safety_flags = ExecutorLaunchSafetyFlags()
        blocking_reasons = _build_blocking_reasons(profile, safety_flags, safe_request)
        ready = _is_preview_ready(profile, safety_flags)
        reason_code = _reason_code(profile, ready)

        return ExecutorLaunchPreview(
            ready=ready,
            reason_code=reason_code,
            executor_id=profile.executor_id,
            launch_command_preview=_build_launch_command_preview(profile),
            launch_cwd_hint=_sanitize_launch_cwd_hint(safe_request.launch_cwd_hint),
            workspace_bound=safe_request.workspace_bound,
            env_var_count=profile.config_discovery.env_var_count,
            token_configured=profile.config_discovery.token_configured,
            permission_mode=profile.config_discovery.permission_mode or profile.permission_model,
            model_name=safe_request.model_name,
            estimated_cost_warning=_estimated_cost_warning(profile),
            blocking_reasons=blocking_reasons,
            safety_flags=safety_flags,
        )


def _is_preview_ready(
    profile: ExecutorProfile,
    safety_flags: ExecutorLaunchSafetyFlags,
) -> bool:
    return (
        profile.status == ExecutorStatus.AVAILABLE
        and safety_flags.launch_preview_only is True
        and safety_flags.no_external_process_launch is True
        and safety_flags.no_product_runtime_git_write is True
        and safety_flags.requires_human_confirmation_before_p9 is True
    )


def _build_blocking_reasons(
    profile: ExecutorProfile,
    safety_flags: ExecutorLaunchSafetyFlags,
    request: ExecutorLaunchPreviewRequest,
) -> list[str]:
    reasons: list[str] = []

    if profile.status == ExecutorStatus.NOT_INSTALLED:
        reasons.extend(["executor_not_installed", "executor_not_available"])
    elif profile.status == ExecutorStatus.NOT_CONFIGURED:
        reasons.extend(["executor_not_configured", "executor_not_available"])
    elif profile.status == ExecutorStatus.DISABLED:
        reasons.extend(["executor_disabled", "executor_not_available"])
    elif profile.status == ExecutorStatus.UNKNOWN:
        reasons.extend(["executor_status_unknown", "executor_not_available"])
    elif profile.status != ExecutorStatus.AVAILABLE:
        reasons.append("executor_not_available")

    if not safety_flags.launch_preview_only:
        reasons.append("launch_preview_only")
    if not safety_flags.requires_human_confirmation_before_p9:
        reasons.append("human_confirmation_required_before_runtime")
    if not request.require_human_confirmation:
        reasons.append("human_confirmation_required_before_runtime")

    reasons.extend(["launch_preview_only", "p9_not_started"])
    if request.require_human_confirmation:
        reasons.append("human_confirmation_required_before_runtime")

    return _deduplicate(reasons)


def _reason_code(profile: ExecutorProfile, ready: bool) -> str:
    if ready:
        return "preview_ready"
    if profile.status in {
        ExecutorStatus.NOT_INSTALLED,
        ExecutorStatus.NOT_CONFIGURED,
        ExecutorStatus.DISABLED,
        ExecutorStatus.UNKNOWN,
    }:
        return "executor_not_available"
    return "preview_blocked_by_safety_gate"


def _build_launch_command_preview(profile: ExecutorProfile) -> str:
    preview_name = _preview_executor_name(profile)
    context_label = "api-request-summary" if profile.provider == ExecutorProvider.DEEPSEEK else "task-context"
    return f"PREVIEW ONLY: {preview_name} [{context_label}] [human-confirmation-required]"


def _preview_executor_name(profile: ExecutorProfile) -> str:
    if profile.executor_id == "claude_code":
        return "claude"
    return profile.executor_id


def _sanitize_launch_cwd_hint(value: str | None) -> str | None:
    if value is None:
        return None
    if value.startswith("/") or value.startswith("~"):
        return "workspace hint provided"
    if ":\\" in value or value.startswith("\\\\"):
        return "workspace hint provided"
    return value


def _estimated_cost_warning(profile: ExecutorProfile) -> str | None:
    if profile.capabilities.requires_network:
        return "Preview only; future runtime may require provider billing review."
    return None


def _deduplicate(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
