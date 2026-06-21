"""Silent real executor dispatch readiness state model.

This module only reports whether backend prerequisites are present for a later
operator-controlled phase. It does not start native tools or expose process
output.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


class _SilentDispatchModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RealExecutorSilentDispatchState(StrEnum):
    BLOCKED = "blocked"
    READY_FOR_MANUAL_OPERATOR_VALIDATION = "ready_for_manual_operator_validation"
    NOOP_LIFECYCLE_READY = "noop_lifecycle_ready"
    NATIVE_LAUNCH_NOT_STARTED = "native_launch_not_started"


class RealExecutorSilentDispatchReadinessInput(_SilentDispatchModel):
    adapter_skeleton_ready: bool = True
    readback_api_ready: bool = True
    noop_lifecycle_api_ready: bool = True
    manual_operator_validation_ready: bool = False
    noop_lifecycle_verified: bool = False
    native_process_started: bool = False
    product_runtime_git_write_allowed: bool = False
    frontend_required: bool = False
    frontend_change_allowed: bool = False

    @field_validator(
        "native_process_started",
        "product_runtime_git_write_allowed",
        "frontend_required",
        "frontend_change_allowed",
    )
    @classmethod
    def enforce_forbidden_true_flags(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError("silent dispatch readiness keeps this capability disabled")
        return value


class RealExecutorSilentDispatchReadiness(_SilentDispatchModel):
    current_state: RealExecutorSilentDispatchState
    state_machine_states: list[RealExecutorSilentDispatchState] = Field(
        default_factory=list,
    )
    adapter_skeleton_ready: bool
    readback_api_ready: bool
    noop_lifecycle_api_ready: bool
    native_executor_launch_not_started: bool = True
    product_runtime_git_write_forbidden: bool = True
    native_process_started: bool = False
    product_runtime_git_write_allowed: bool = False
    frontend_required: bool = False
    frontend_change_allowed: bool = False
    blocking_reasons: list[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=_utc_now)

    @field_validator(
        "native_process_started",
        "product_runtime_git_write_allowed",
        "frontend_required",
        "frontend_change_allowed",
    )
    @classmethod
    def enforce_false_flags(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError("silent dispatch readiness cannot enable this flag")
        return value

    @field_validator("native_executor_launch_not_started", "product_runtime_git_write_forbidden")
    @classmethod
    def enforce_true_flags(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("silent dispatch readiness must preserve stopped boundaries")
        return value

    @field_validator("blocking_reasons", mode="before")
    @classmethod
    def default_blocking_reasons(cls, value: Any) -> Any:
        if value is None:
            return []
        return value

    @field_validator("blocking_reasons")
    @classmethod
    def normalize_blocking_reasons(cls, value: list[str]) -> list[str]:
        return _dedupe_trimmed_strings(value)

    @field_validator("state_machine_states", mode="before")
    @classmethod
    def default_state_machine_states(cls, value: Any) -> Any:
        if value is None:
            return []
        return value

    @model_validator(mode="after")
    def validate_state_consistency(self) -> "RealExecutorSilentDispatchReadiness":
        if self.current_state == RealExecutorSilentDispatchState.BLOCKED:
            if not self.blocking_reasons:
                raise ValueError("blocked silent dispatch readiness must include reasons")
        elif self.blocking_reasons:
            raise ValueError("non-blocked silent dispatch readiness must not include reasons")
        return self


class RealExecutorSilentDispatchReadinessBuilder:
    def build(
        self,
        readiness_input: RealExecutorSilentDispatchReadinessInput | None = None,
    ) -> RealExecutorSilentDispatchReadiness:
        source = readiness_input or RealExecutorSilentDispatchReadinessInput()
        reasons = self._blocking_reasons(source)

        if reasons:
            state = RealExecutorSilentDispatchState.BLOCKED
        elif source.noop_lifecycle_verified:
            state = RealExecutorSilentDispatchState.NOOP_LIFECYCLE_READY
        elif source.manual_operator_validation_ready:
            state = RealExecutorSilentDispatchState.READY_FOR_MANUAL_OPERATOR_VALIDATION
        else:
            state = RealExecutorSilentDispatchState.NATIVE_LAUNCH_NOT_STARTED

        return RealExecutorSilentDispatchReadiness(
            current_state=state,
            state_machine_states=list(RealExecutorSilentDispatchState),
            adapter_skeleton_ready=source.adapter_skeleton_ready,
            readback_api_ready=source.readback_api_ready,
            noop_lifecycle_api_ready=source.noop_lifecycle_api_ready,
            native_executor_launch_not_started=True,
            product_runtime_git_write_forbidden=True,
            native_process_started=False,
            product_runtime_git_write_allowed=False,
            frontend_required=False,
            frontend_change_allowed=False,
            blocking_reasons=reasons,
        )

    def _blocking_reasons(
        self,
        source: RealExecutorSilentDispatchReadinessInput,
    ) -> list[str]:
        reasons: list[str] = []
        if not source.adapter_skeleton_ready:
            reasons.append("adapter_skeleton_missing")
        if not source.readback_api_ready:
            reasons.append("readback_api_missing")
        if not source.noop_lifecycle_api_ready:
            reasons.append("noop_lifecycle_api_missing")
        return reasons


__all__ = (
    "RealExecutorSilentDispatchReadiness",
    "RealExecutorSilentDispatchReadinessBuilder",
    "RealExecutorSilentDispatchReadinessInput",
    "RealExecutorSilentDispatchState",
)
