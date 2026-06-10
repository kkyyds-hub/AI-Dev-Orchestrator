"""Read-only real executor launch readback for P9-REL-F1.

This module builds a safe API-facing readback from explicit request data. It
does not launch executors, generate executable commands, read host settings, or
write runtime state.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.external_executors.actual_contract import (
    RealExecutorLaunchContext,
    RealExecutorOperationStatus,
    RealExecutorSafetyBoundary,
)
from app.external_executors.actual_disabled_adapter import (
    DisabledRealExecutorAdapter,
    DisabledRealExecutorAdapterConfig,
)
from app.external_executors.actual_preflight import RealExecutorPreflightService
from app.external_executors.actual_preview import (
    RealExecutorLaunchPlanPreviewBuilder,
    RealExecutorLaunchPlanPreviewInput,
)


_SENSITIVE_TEXT_PATTERN = re.compile(
    r"(api\s*key|token|secret|password|bearer|sk-)",
    re.IGNORECASE,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _trim_optional_string(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _trim_required_string(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _reject_sensitive_text(value: str | None) -> str | None:
    if value is not None and _SENSITIVE_TEXT_PATTERN.search(value):
        raise ValueError("readback text must not contain suspected credential material")
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


class _ReadbackModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RealExecutorLaunchReadbackRequest(_ReadbackModel):
    request_id: str
    executor_label: str
    command_summary: str | None = None
    workspace_hint: str | None = None
    safety_boundary: RealExecutorSafetyBoundary = Field(
        default_factory=RealExecutorSafetyBoundary,
    )

    @field_validator("request_id", "executor_label", mode="before")
    @classmethod
    def trim_required_strings(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("command_summary", "workspace_hint", mode="before")
    @classmethod
    def trim_optional_strings(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    @field_validator("request_id", "executor_label")
    @classmethod
    def validate_required_safe_text(cls, value: str) -> str:
        if not value:
            raise ValueError("value must not be empty")
        return _reject_sensitive_text(value) or value

    @field_validator("command_summary", "workspace_hint")
    @classmethod
    def validate_optional_safe_text(cls, value: str | None) -> str | None:
        return _reject_sensitive_text(value)

    def to_launch_context(self) -> RealExecutorLaunchContext:
        return RealExecutorLaunchContext(
            request_id=self.request_id,
            executor_label=self.executor_label,
            command_summary=self.command_summary,
            workspace_hint=self.workspace_hint,
            safety_boundary=self.safety_boundary,
        )


class RealExecutorLaunchReadbackResponse(_ReadbackModel):
    readback_id: str
    executor_label: str
    preflight_ready: bool
    preflight_status: RealExecutorOperationStatus
    preview_ready: bool
    preview_executable: bool = False
    adapter_enabled: bool = False
    adapter_launch_status: RealExecutorOperationStatus
    blocking_reasons: list[str] = Field(default_factory=list)
    display_steps: list[str] = Field(default_factory=list)
    safe_summary: str | None = None
    redaction_applied: bool = True
    product_runtime_git_write_allowed: bool = False
    real_executor_launch_started: bool = False
    api_mode: Literal["read_only"] = "read_only"
    created_at: datetime = Field(default_factory=_utc_now)

    @field_validator("readback_id", "executor_label", mode="before")
    @classmethod
    def trim_required_strings(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("safe_summary", mode="before")
    @classmethod
    def trim_safe_summary(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    @field_validator("readback_id", "executor_label")
    @classmethod
    def validate_required_safe_text(cls, value: str) -> str:
        if not value:
            raise ValueError("value must not be empty")
        return _reject_sensitive_text(value) or value

    @field_validator("safe_summary")
    @classmethod
    def validate_safe_summary(cls, value: str | None) -> str | None:
        return _reject_sensitive_text(value)

    @field_validator("blocking_reasons", "display_steps", mode="before")
    @classmethod
    def default_lists(cls, value: Any) -> Any:
        if value is None:
            return []
        return value

    @field_validator("blocking_reasons", "display_steps")
    @classmethod
    def normalize_safe_strings(cls, value: list[str]) -> list[str]:
        normalized_items = _dedupe_trimmed_strings(value)
        for item in normalized_items:
            _reject_sensitive_text(item)
        return normalized_items

    @field_validator("preview_executable")
    @classmethod
    def enforce_non_executable_preview(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError("readback preview must remain non-executable")
        return value

    @field_validator("adapter_enabled")
    @classmethod
    def enforce_disabled_adapter(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError("readback adapter must remain disabled")
        return value

    @field_validator("redaction_applied")
    @classmethod
    def enforce_redaction_applied(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("readback redaction_applied must remain true")
        return value

    @field_validator("product_runtime_git_write_allowed")
    @classmethod
    def prevent_product_runtime_git_write(cls, value: bool) -> bool:
        if value is True:
            raise ValueError("product runtime Git write is outside read-only readback")
        return value

    @field_validator("real_executor_launch_started")
    @classmethod
    def prevent_real_executor_launch(cls, value: bool) -> bool:
        if value is True:
            raise ValueError("read-only readback must not start a real executor")
        return value


class RealExecutorLaunchReadbackBuilder:
    def __init__(
        self,
        preflight_service: RealExecutorPreflightService | None = None,
        preview_builder: RealExecutorLaunchPlanPreviewBuilder | None = None,
        disabled_adapter: DisabledRealExecutorAdapter | None = None,
        adapter_config: DisabledRealExecutorAdapterConfig | None = None,
    ) -> None:
        self._preflight_service = preflight_service or RealExecutorPreflightService()
        self._preview_builder = preview_builder or RealExecutorLaunchPlanPreviewBuilder()
        self._adapter_config = adapter_config or DisabledRealExecutorAdapterConfig()
        self._disabled_adapter = disabled_adapter or DisabledRealExecutorAdapter(
            config=self._adapter_config,
            preflight_service=self._preflight_service,
            preview_builder=self._preview_builder,
        )

    def build(
        self,
        request: RealExecutorLaunchReadbackRequest,
    ) -> RealExecutorLaunchReadbackResponse:
        context = request.to_launch_context()
        preflight = self._preflight_service.evaluate_launch(context)
        preview = self._preview_builder.build(
            RealExecutorLaunchPlanPreviewInput(
                preview_id=f"readback-preview-{request.request_id}",
                context=context,
                preflight_result=preflight,
            ),
        )
        adapter_result = self._disabled_adapter.launch(context)
        blocking_reasons = _dedupe_trimmed_strings(
            [
                *preflight.blocking_reasons,
                *preview.blocking_reasons,
                *adapter_result.blocking_reasons,
            ],
        )

        return RealExecutorLaunchReadbackResponse(
            readback_id=f"real-executor-readback-{request.request_id}",
            executor_label=context.executor_label,
            preflight_ready=preflight.ready,
            preflight_status=preflight.status,
            preview_ready=preview.ready,
            preview_executable=preview.executable,
            adapter_enabled=self._adapter_config.enabled,
            adapter_launch_status=adapter_result.status,
            blocking_reasons=blocking_reasons,
            display_steps=list(preview.display_steps),
            safe_summary=preview.safe_summary,
            redaction_applied=preview.redaction_applied,
            product_runtime_git_write_allowed=False,
            real_executor_launch_started=False,
            api_mode="read_only",
        )


__all__ = (
    "RealExecutorLaunchReadbackBuilder",
    "RealExecutorLaunchReadbackRequest",
    "RealExecutorLaunchReadbackResponse",
)
