"""Pure prelaunch chain snapshot for future native executor wiring."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _trim_required_string(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _dedupe_trimmed_strings(value: list[str]) -> list[str]:
    normalized_items: list[str] = []
    seen_items: set[str] = set()
    for item in value:
        normalized_item = item.strip()
        if not normalized_item or normalized_item in seen_items:
            continue
        normalized_items.append(normalized_item)
        seen_items.add(normalized_item)
    return normalized_items


class _PrelaunchChainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RealExecutorPrelaunchChainState(StrEnum):
    BLOCKED = "blocked"
    READY_FOR_NOOP_MANUAL_VALIDATION = "ready_for_noop_manual_validation"
    READY_FOR_NATIVE_LAUNCH_PRECHECK = "ready_for_native_launch_precheck"
    NATIVE_LAUNCH_NOT_STARTED = "native_launch_not_started"


class RealExecutorPrelaunchChainStepName(StrEnum):
    SILENT_DISPATCH_READINESS = "silent_dispatch_readiness"
    OPERATOR_VALIDATION = "operator_validation"
    REAL_EXECUTOR_PREFLIGHT = "real_executor_preflight"
    REAL_EXECUTOR_PREVIEW = "real_executor_preview"
    WORKSPACE_BINDING_PRECHECK = "workspace_binding_precheck"
    RUNTIME_BINDING_PRECHECK = "runtime_binding_precheck"
    EXECUTOR_LABEL_RESOLUTION = "executor_label_resolution"
    REDACTED_COMMAND_PLAN_PLACEHOLDER = "redacted_command_plan_placeholder"
    PROCESS_ADAPTER_NOOP_LIFECYCLE = "process_adapter_noop_lifecycle"
    AUDIT_EVENT_APPEND_ONLY_PLANNED = "audit_event_append_only_planned"
    NATIVE_LAUNCH_BLOCKED = "native_launch_blocked"
    PRODUCT_RUNTIME_GIT_WRITE_FORBIDDEN = "product_runtime_git_write_forbidden"


class RealExecutorPrelaunchChainStep(_PrelaunchChainModel):
    name: RealExecutorPrelaunchChainStepName
    ready: bool = False
    blocked_reason: str | None = None

    @field_validator("blocked_reason", mode="before")
    @classmethod
    def trim_blocked_reason(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class RealExecutorPrelaunchChainInput(_PrelaunchChainModel):
    silent_dispatch_ready: bool = False
    operator_validation_accepted: bool = False
    preflight_ready: bool = False
    preview_ready: bool = False
    workspace_bound: bool = False
    runtime_bound: bool = False
    executor_label: str = "codex"
    command_plan_redacted: bool = True
    noop_lifecycle_ready: bool = False
    audit_append_only_ready: bool = False
    native_process_started: bool = False
    product_runtime_git_write_allowed: bool = False
    frontend_required: bool = False
    frontend_change_allowed: bool = False

    @field_validator("executor_label", mode="before")
    @classmethod
    def trim_executor_label(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("executor_label")
    @classmethod
    def require_executor_label(cls, value: str) -> str:
        if not value:
            raise ValueError("executor_label must not be empty")
        return value

    @field_validator(
        "native_process_started",
        "product_runtime_git_write_allowed",
        "frontend_required",
        "frontend_change_allowed",
    )
    @classmethod
    def keep_forbidden_flags_disabled(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError("prelaunch chain keeps this capability disabled")
        return value


class RealExecutorPrelaunchChainSnapshot(_PrelaunchChainModel):
    current_state: RealExecutorPrelaunchChainState
    ordered_steps: list[RealExecutorPrelaunchChainStep] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    future_spawn_order: list[str] = Field(
        default_factory=lambda: ["workspace", "runtime", "agent"],
    )
    future_cleanup_order: list[str] = Field(
        default_factory=lambda: ["agent", "runtime", "workspace"],
    )
    native_launch_allowed: bool = False
    native_process_started: bool = False
    product_runtime_git_write_allowed: bool = False
    frontend_required: bool = False
    frontend_change_allowed: bool = False
    evaluated_at: datetime = Field(default_factory=_utc_now)

    @field_validator("blocked_reasons", mode="before")
    @classmethod
    def default_blocked_reasons(cls, value: Any) -> Any:
        if value is None:
            return []
        return value

    @field_validator("blocked_reasons")
    @classmethod
    def normalize_blocked_reasons(cls, value: list[str]) -> list[str]:
        return _dedupe_trimmed_strings(value)

    @field_validator(
        "native_launch_allowed",
        "native_process_started",
        "product_runtime_git_write_allowed",
        "frontend_required",
        "frontend_change_allowed",
    )
    @classmethod
    def keep_snapshot_forbidden_flags_disabled(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError("prelaunch snapshot cannot enable this flag")
        return value

    @model_validator(mode="after")
    def validate_snapshot_state(self) -> "RealExecutorPrelaunchChainSnapshot":
        if self.current_state == RealExecutorPrelaunchChainState.BLOCKED:
            if not self.blocked_reasons:
                raise ValueError("blocked prelaunch snapshot must include reasons")
        elif self.blocked_reasons:
            raise ValueError("non-blocked prelaunch snapshot must not include reasons")
        if self.future_spawn_order != ["workspace", "runtime", "agent"]:
            raise ValueError("future spawn order is fixed")
        if self.future_cleanup_order != ["agent", "runtime", "workspace"]:
            raise ValueError("future cleanup order is fixed")
        return self


class RealExecutorPrelaunchChainBuilder:
    _SUPPORTED_EXECUTOR_LABELS = frozenset({"codex", "claude-code", "claude code"})

    def build(
        self,
        chain_input: RealExecutorPrelaunchChainInput | None = None,
    ) -> RealExecutorPrelaunchChainSnapshot:
        source = chain_input or RealExecutorPrelaunchChainInput()
        blocked_reasons = self._blocked_reasons(source)
        current_state = self._current_state(source, blocked_reasons)

        return RealExecutorPrelaunchChainSnapshot(
            current_state=current_state,
            ordered_steps=self._ordered_steps(source),
            blocked_reasons=blocked_reasons,
            future_spawn_order=["workspace", "runtime", "agent"],
            future_cleanup_order=["agent", "runtime", "workspace"],
            native_launch_allowed=False,
            native_process_started=False,
            product_runtime_git_write_allowed=False,
            frontend_required=False,
            frontend_change_allowed=False,
        )

    def _current_state(
        self,
        source: RealExecutorPrelaunchChainInput,
        blocked_reasons: list[str],
    ) -> RealExecutorPrelaunchChainState:
        if blocked_reasons:
            return RealExecutorPrelaunchChainState.BLOCKED
        if source.operator_validation_accepted and source.noop_lifecycle_ready:
            return RealExecutorPrelaunchChainState.READY_FOR_NATIVE_LAUNCH_PRECHECK
        if source.operator_validation_accepted:
            return RealExecutorPrelaunchChainState.READY_FOR_NOOP_MANUAL_VALIDATION
        return RealExecutorPrelaunchChainState.NATIVE_LAUNCH_NOT_STARTED

    def _ordered_steps(
        self,
        source: RealExecutorPrelaunchChainInput,
    ) -> list[RealExecutorPrelaunchChainStep]:
        reason_by_step = {
            RealExecutorPrelaunchChainStepName.SILENT_DISPATCH_READINESS: (
                None if source.silent_dispatch_ready else "silent_dispatch_readiness_missing"
            ),
            RealExecutorPrelaunchChainStepName.OPERATOR_VALIDATION: (
                None if source.operator_validation_accepted else "operator_validation_missing"
            ),
            RealExecutorPrelaunchChainStepName.REAL_EXECUTOR_PREFLIGHT: (
                None if source.preflight_ready else "real_executor_preflight_missing"
            ),
            RealExecutorPrelaunchChainStepName.REAL_EXECUTOR_PREVIEW: (
                None if source.preview_ready else "real_executor_preview_missing"
            ),
            RealExecutorPrelaunchChainStepName.WORKSPACE_BINDING_PRECHECK: (
                None if source.workspace_bound else "workspace_binding_missing"
            ),
            RealExecutorPrelaunchChainStepName.RUNTIME_BINDING_PRECHECK: (
                None if source.runtime_bound else "runtime_binding_missing"
            ),
            RealExecutorPrelaunchChainStepName.EXECUTOR_LABEL_RESOLUTION: (
                None
                if self._executor_label_supported(source.executor_label)
                else "executor_label_not_supported"
            ),
            RealExecutorPrelaunchChainStepName.REDACTED_COMMAND_PLAN_PLACEHOLDER: (
                None if source.command_plan_redacted else "command_plan_not_redacted"
            ),
            RealExecutorPrelaunchChainStepName.PROCESS_ADAPTER_NOOP_LIFECYCLE: (
                None
                if source.noop_lifecycle_ready
                else "process_adapter_noop_lifecycle_missing"
            ),
            RealExecutorPrelaunchChainStepName.AUDIT_EVENT_APPEND_ONLY_PLANNED: (
                None if source.audit_append_only_ready else "audit_append_only_missing"
            ),
            RealExecutorPrelaunchChainStepName.NATIVE_LAUNCH_BLOCKED: None,
            RealExecutorPrelaunchChainStepName.PRODUCT_RUNTIME_GIT_WRITE_FORBIDDEN: None,
        }
        return [
            RealExecutorPrelaunchChainStep(
                name=step_name,
                ready=reason_by_step[step_name] is None,
                blocked_reason=reason_by_step[step_name],
            )
            for step_name in RealExecutorPrelaunchChainStepName
        ]

    def _blocked_reasons(self, source: RealExecutorPrelaunchChainInput) -> list[str]:
        return [
            step.blocked_reason
            for step in self._ordered_steps(source)
            if step.blocked_reason is not None
        ]

    def _executor_label_supported(self, executor_label: str) -> bool:
        return executor_label.strip().lower() in self._SUPPORTED_EXECUTOR_LABELS


__all__ = (
    "RealExecutorPrelaunchChainBuilder",
    "RealExecutorPrelaunchChainInput",
    "RealExecutorPrelaunchChainSnapshot",
    "RealExecutorPrelaunchChainState",
    "RealExecutorPrelaunchChainStep",
    "RealExecutorPrelaunchChainStepName",
)
