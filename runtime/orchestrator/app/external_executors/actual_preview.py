"""Non-executable launch plan preview for future real executor adapters.

This module belongs to P9-REL-D. It only turns explicit contract and preflight
input into a safe display preview. It does not implement an adapter, inspect
local executor configuration, start processes, or create runtime entrypoints.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.external_executors.actual_contract import (
    RealExecutorLaunchContext,
    RealExecutorLifecycleIntent,
    RealExecutorOperationStatus,
)
from app.external_executors.actual_preflight import RealExecutorPreflightResult


_SENSITIVE_TEXT_PATTERN = re.compile(
    r"(api\s*key|token|secret|password|bearer|sk-)",
    re.IGNORECASE,
)
_EXECUTION_TEXT_PATTERN = re.compile(
    r"(^\s*\$|&&|\|\||`|\$\(|\b(?:bash|zsh|sudo|curl|git\s+|python\s+|node\s+)\b)",
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
        raise ValueError("preview text must not contain suspected credential material")
    return value


def _reject_executable_text(value: str) -> str:
    if _EXECUTION_TEXT_PATTERN.search(value):
        raise ValueError("display steps must be explanatory text, not executable lines")
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


class _PreviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RealExecutorLaunchPlanPreviewInput(_PreviewModel):
    preview_id: str
    context: RealExecutorLaunchContext
    preflight_result: RealExecutorPreflightResult

    @field_validator("preview_id", mode="before")
    @classmethod
    def trim_preview_id(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("preview_id")
    @classmethod
    def validate_preview_id(cls, value: str) -> str:
        if not value:
            raise ValueError("preview_id must not be empty")
        return _reject_sensitive_text(value) or value


class RealExecutorLaunchPlanPreview(_PreviewModel):
    preview_id: str
    ready: bool
    status: RealExecutorOperationStatus
    executor_label: str
    lifecycle_intent: RealExecutorLifecycleIntent = RealExecutorLifecycleIntent.LAUNCH
    safe_summary: str | None = None
    blocking_reasons: list[str] = Field(default_factory=list)
    display_steps: list[str] = Field(default_factory=list)
    redaction_applied: bool = True
    executable: bool = False
    product_runtime_git_write_allowed: bool = False
    created_at: datetime = Field(default_factory=_utc_now)

    @field_validator("preview_id", "executor_label", mode="before")
    @classmethod
    def trim_required_strings(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("safe_summary", mode="before")
    @classmethod
    def trim_safe_summary(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    @field_validator("preview_id", "executor_label")
    @classmethod
    def validate_required_safe_text(cls, value: str) -> str:
        if not value:
            raise ValueError("value must not be empty")
        return _reject_sensitive_text(value) or value

    @field_validator("safe_summary")
    @classmethod
    def validate_safe_summary(cls, value: str | None) -> str | None:
        return _reject_sensitive_text(value)

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

    @field_validator("display_steps", mode="before")
    @classmethod
    def default_display_steps(cls, value: Any) -> Any:
        if value is None:
            return []
        return value

    @field_validator("display_steps")
    @classmethod
    def validate_display_steps(cls, value: list[str]) -> list[str]:
        normalized_steps = _dedupe_trimmed_strings(value)
        if not normalized_steps:
            raise ValueError("display_steps must include at least one explanatory step")
        for item in normalized_steps:
            _reject_sensitive_text(item)
            _reject_executable_text(item)
        return normalized_steps

    @field_validator("redaction_applied")
    @classmethod
    def enforce_redaction_applied(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("redaction_applied must remain true")
        return value

    @field_validator("executable")
    @classmethod
    def enforce_non_executable(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError("launch plan preview must remain non-executable")
        return value

    @field_validator("product_runtime_git_write_allowed")
    @classmethod
    def prevent_product_runtime_git_write(cls, value: bool) -> bool:
        if value is True:
            raise ValueError("product runtime Git write is outside the P9-REL-D preview")
        return value

    @model_validator(mode="after")
    def validate_status_consistency(self) -> "RealExecutorLaunchPlanPreview":
        if self.lifecycle_intent != RealExecutorLifecycleIntent.LAUNCH:
            raise ValueError("launch plan preview lifecycle_intent must be launch")
        if self.ready and self.status != RealExecutorOperationStatus.ACCEPTED:
            raise ValueError("ready preview must be accepted")
        if not self.ready and self.status != RealExecutorOperationStatus.BLOCKED:
            raise ValueError("blocked preview must use blocked status")
        if self.ready and self.blocking_reasons:
            raise ValueError("ready preview must not include blocking reasons")
        if not self.ready and not self.blocking_reasons:
            raise ValueError("blocked preview must include blocking reasons")
        return self


class RealExecutorLaunchPlanPreviewBuilder:
    def build(
        self,
        preview_input: RealExecutorLaunchPlanPreviewInput,
    ) -> RealExecutorLaunchPlanPreview:
        preflight = preview_input.preflight_result
        context = preview_input.context

        return RealExecutorLaunchPlanPreview(
            preview_id=preview_input.preview_id,
            ready=preflight.ready,
            status=preflight.status,
            executor_label=context.executor_label,
            lifecycle_intent=RealExecutorLifecycleIntent.LAUNCH,
            safe_summary=preflight.safe_summary,
            blocking_reasons=list(preflight.blocking_reasons),
            display_steps=self._display_steps(context, preflight),
            redaction_applied=True,
            executable=False,
            product_runtime_git_write_allowed=False,
        )

    def _display_steps(
        self,
        context: RealExecutorLaunchContext,
        preflight: RealExecutorPreflightResult,
    ) -> list[str]:
        steps = [
            f"Review executor label: {context.executor_label}.",
            "Confirm that the preflight result is recorded before any future launch phase.",
            "Keep this preview descriptive only; no executable launch line is produced.",
            "Keep product runtime repository write disabled for this preview.",
        ]
        if context.workspace_hint is not None:
            steps.append(f"Review workspace hint: {context.workspace_hint}.")
        if not preflight.ready:
            steps.append("Resolve the listed blocking reasons before any later launch phase.")
        return steps


__all__ = (
    "RealExecutorLaunchPlanPreview",
    "RealExecutorLaunchPlanPreviewBuilder",
    "RealExecutorLaunchPlanPreviewInput",
)
