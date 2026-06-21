"""Read-only composer for real executor prelaunch chain snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.external_executors.actual_operator_validation import (
    RealExecutorOperatorValidationStatus,
)
from app.external_executors.actual_prelaunch_chain import (
    RealExecutorPrelaunchChainBuilder,
    RealExecutorPrelaunchChainInput,
    RealExecutorPrelaunchChainSnapshot,
)


_COMPOSED_FROM = [
    "silent_dispatch",
    "operator_validation",
    "preflight",
    "preview",
    "workspace_binding",
    "runtime_binding",
    "process_adapter_noop_lifecycle",
    "audit_append_only",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _trim_required_string(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


class _PrelaunchComposerModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RealExecutorPrelaunchComposerInput(_PrelaunchComposerModel):
    silent_dispatch_ready: bool = False
    operator_validation_status: str = RealExecutorOperatorValidationStatus.MISSING.value
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

    @field_validator("operator_validation_status", "executor_label", mode="before")
    @classmethod
    def trim_required_strings(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("operator_validation_status")
    @classmethod
    def validate_operator_validation_status(cls, value: str) -> str:
        allowed_values = {status.value for status in RealExecutorOperatorValidationStatus}
        if value not in allowed_values:
            raise ValueError("operator_validation_status is not supported")
        return value

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
            raise ValueError("prelaunch composer keeps this capability disabled")
        return value


class RealExecutorPrelaunchComposerSnapshot(_PrelaunchComposerModel):
    prelaunch_snapshot: RealExecutorPrelaunchChainSnapshot
    composed_from: list[str] = Field(default_factory=lambda: list(_COMPOSED_FROM))
    composer_mode: Literal["read_only_composition"] = "read_only_composition"
    native_launch_allowed: bool = False
    native_process_started: bool = False
    product_runtime_git_write_allowed: bool = False
    frontend_required: bool = False
    frontend_change_allowed: bool = False
    composed_at: datetime = Field(default_factory=_utc_now)

    @field_validator("composed_from")
    @classmethod
    def enforce_composed_from(cls, value: list[str]) -> list[str]:
        if value != _COMPOSED_FROM:
            raise ValueError("composed_from is fixed")
        return value

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
            raise ValueError("prelaunch composer snapshot cannot enable this flag")
        return value


class RealExecutorPrelaunchComposer:
    def __init__(
        self,
        chain_builder: RealExecutorPrelaunchChainBuilder | None = None,
    ) -> None:
        self._chain_builder = chain_builder or RealExecutorPrelaunchChainBuilder()

    def compose(
        self,
        composer_input: RealExecutorPrelaunchComposerInput | None = None,
    ) -> RealExecutorPrelaunchComposerSnapshot:
        source = composer_input or RealExecutorPrelaunchComposerInput()
        chain_input = RealExecutorPrelaunchChainInput(
            silent_dispatch_ready=source.silent_dispatch_ready,
            operator_validation_accepted=self._operator_validation_accepted(source),
            preflight_ready=source.preflight_ready,
            preview_ready=source.preview_ready,
            workspace_bound=source.workspace_bound,
            runtime_bound=source.runtime_bound,
            executor_label=source.executor_label,
            command_plan_redacted=source.command_plan_redacted,
            noop_lifecycle_ready=source.noop_lifecycle_ready,
            audit_append_only_ready=source.audit_append_only_ready,
            native_process_started=False,
            product_runtime_git_write_allowed=False,
            frontend_required=False,
            frontend_change_allowed=False,
        )
        return RealExecutorPrelaunchComposerSnapshot(
            prelaunch_snapshot=self._chain_builder.build(chain_input),
            composed_from=list(_COMPOSED_FROM),
            composer_mode="read_only_composition",
            native_launch_allowed=False,
            native_process_started=False,
            product_runtime_git_write_allowed=False,
            frontend_required=False,
            frontend_change_allowed=False,
        )

    @staticmethod
    def _operator_validation_accepted(
        source: RealExecutorPrelaunchComposerInput,
    ) -> bool:
        return (
            source.operator_validation_status
            == RealExecutorOperatorValidationStatus.ACCEPTED_FOR_NOOP_VALIDATION.value
        )


__all__ = (
    "RealExecutorPrelaunchComposer",
    "RealExecutorPrelaunchComposerInput",
    "RealExecutorPrelaunchComposerSnapshot",
)
