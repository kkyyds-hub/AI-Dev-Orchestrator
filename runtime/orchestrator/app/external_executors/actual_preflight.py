"""Pure launch preflight evaluation for future real executor adapters.

This module belongs to P9-REL-C. It only evaluates explicit contract input and
does not implement a real adapter, inspect the host machine, start processes,
or create runtime entrypoints.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.external_executors.actual_contract import (
    RealExecutorLaunchContext,
    RealExecutorOperationStatus,
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


def _reject_sensitive_text(value: str | None) -> str | None:
    if value is not None and _SENSITIVE_TEXT_PATTERN.search(value):
        raise ValueError("safe summary must not contain suspected credential material")
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


class _PreflightModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RealExecutorPreflightInput(_PreflightModel):
    context: RealExecutorLaunchContext
    safe_summary: str | None = None
    product_runtime_git_write_allowed: bool = False

    @field_validator("safe_summary", mode="before")
    @classmethod
    def trim_safe_summary(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    @field_validator("safe_summary")
    @classmethod
    def validate_safe_summary(cls, value: str | None) -> str | None:
        return _reject_sensitive_text(value)

    @field_validator("product_runtime_git_write_allowed")
    @classmethod
    def prevent_product_runtime_git_write(cls, value: bool) -> bool:
        if value is True:
            raise ValueError("product runtime Git write is outside the P9-REL-C preflight")
        return value


class RealExecutorPreflightResult(_PreflightModel):
    ready: bool
    status: RealExecutorOperationStatus
    blocking_reasons: list[str] = Field(default_factory=list)
    safe_summary: str | None = None
    product_runtime_git_write_allowed: bool = False
    evaluated_at: datetime = Field(default_factory=_utc_now)

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

    @field_validator("safe_summary", mode="before")
    @classmethod
    def trim_safe_summary(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    @field_validator("safe_summary")
    @classmethod
    def validate_safe_summary(cls, value: str | None) -> str | None:
        return _reject_sensitive_text(value)

    @field_validator("product_runtime_git_write_allowed")
    @classmethod
    def prevent_product_runtime_git_write(cls, value: bool) -> bool:
        if value is True:
            raise ValueError("product runtime Git write is outside the P9-REL-C preflight")
        return value

    @model_validator(mode="after")
    def validate_status_consistency(self) -> "RealExecutorPreflightResult":
        if self.ready and self.status != RealExecutorOperationStatus.ACCEPTED:
            raise ValueError("ready preflight result must be accepted")
        if not self.ready and self.status != RealExecutorOperationStatus.BLOCKED:
            raise ValueError("blocked preflight result must use blocked status")
        if self.ready and self.blocking_reasons:
            raise ValueError("ready preflight result must not include blocking reasons")
        if not self.ready and not self.blocking_reasons:
            raise ValueError("blocked preflight result must include blocking reasons")
        return self


class RealExecutorPreflightService:
    def evaluate(self, preflight_input: RealExecutorPreflightInput) -> RealExecutorPreflightResult:
        return self.evaluate_launch(
            preflight_input.context,
            safe_summary=preflight_input.safe_summary,
        )

    def evaluate_launch(
        self,
        context: RealExecutorLaunchContext,
        *,
        safe_summary: str | None = None,
    ) -> RealExecutorPreflightResult:
        reasons = list(context.safety_boundary.blocking_reasons())
        ready = len(reasons) == 0
        status = (
            RealExecutorOperationStatus.ACCEPTED
            if ready
            else RealExecutorOperationStatus.BLOCKED
        )

        return RealExecutorPreflightResult(
            ready=ready,
            status=status,
            blocking_reasons=reasons,
            safe_summary=safe_summary or self._build_safe_summary(context, status),
            product_runtime_git_write_allowed=False,
        )

    def _build_safe_summary(
        self,
        context: RealExecutorLaunchContext,
        status: RealExecutorOperationStatus,
    ) -> str:
        summary_parts = [
            f"request_id={context.request_id}",
            f"executor_label={context.executor_label}",
            f"status={status.value}",
        ]
        if context.command_summary is not None:
            summary_parts.append(f"command_summary={context.command_summary}")
        if context.workspace_hint is not None:
            summary_parts.append(f"workspace_hint={context.workspace_hint}")
        return "; ".join(summary_parts)


__all__ = (
    "RealExecutorPreflightInput",
    "RealExecutorPreflightResult",
    "RealExecutorPreflightService",
)
