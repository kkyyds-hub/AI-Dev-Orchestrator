"""Disabled real executor adapter skeleton for P9-REL-E.

This module preserves the future adapter method shape while keeping every
operation blocked or safely inert by default.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.external_executors.actual_contract import (
    RealExecutorLaunchContext,
    RealExecutorLifecycleIntent,
    RealExecutorOperationResult,
    RealExecutorOperationStatus,
    RealExecutorPollSnapshot,
    RealExecutorPollState,
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
DISABLED_REASON = "real_executor_disabled"


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
        raise ValueError("disabled adapter text must not contain suspected credential material")
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


class _DisabledAdapterModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DisabledRealExecutorAdapterConfig(_DisabledAdapterModel):
    enabled: bool = False
    disabled_reason: str = DISABLED_REASON
    audit_source: str = "external_executor"

    @field_validator("disabled_reason", "audit_source", mode="before")
    @classmethod
    def trim_required_strings(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("disabled_reason", "audit_source")
    @classmethod
    def validate_required_safe_text(cls, value: str) -> str:
        if not value:
            raise ValueError("value must not be empty")
        return _reject_sensitive_text(value) or value

    @field_validator("enabled")
    @classmethod
    def enforce_disabled(cls, value: bool) -> bool:
        if value is True:
            raise ValueError("disabled real executor adapter must remain disabled")
        return value


class DisabledRealExecutorAdapterAuditEvent(_DisabledAdapterModel):
    source: str = "external_executor"
    kind: str
    level: str = "warn"
    summary: str
    detail: str | None = None
    created_at: datetime = Field(default_factory=_utc_now)

    @field_validator("source", "kind", "level", "summary", mode="before")
    @classmethod
    def trim_required_strings(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("detail", mode="before")
    @classmethod
    def trim_detail(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    @field_validator("source", "kind", "level", "summary")
    @classmethod
    def validate_required_safe_text(cls, value: str) -> str:
        if not value:
            raise ValueError("value must not be empty")
        return _reject_sensitive_text(value) or value

    @field_validator("detail")
    @classmethod
    def validate_optional_safe_text(cls, value: str | None) -> str | None:
        return _reject_sensitive_text(value)


class DisabledRealExecutorAdapterResultFactory:
    def __init__(self, config: DisabledRealExecutorAdapterConfig | None = None) -> None:
        self._config = config or DisabledRealExecutorAdapterConfig()

    def launch_blocked(
        self,
        context: RealExecutorLaunchContext,
        *,
        extra_reasons: list[str] | None = None,
        safe_summary: str | None = None,
    ) -> RealExecutorOperationResult:
        reasons = self._reasons(extra_reasons)
        return RealExecutorOperationResult(
            lifecycle_intent=RealExecutorLifecycleIntent.LAUNCH,
            status=RealExecutorOperationStatus.BLOCKED,
            message=safe_summary
            or "Real executor launch blocked because adapter is disabled by default",
            blocking_reasons=reasons,
            audit_event_count=1,
            product_runtime_git_write_allowed=False,
        )

    def operation_blocked(
        self,
        lifecycle_intent: RealExecutorLifecycleIntent,
        *,
        reason: str | None = None,
    ) -> RealExecutorOperationResult:
        reasons = self._reasons([reason] if reason is not None else None)
        return RealExecutorOperationResult(
            lifecycle_intent=lifecycle_intent,
            status=RealExecutorOperationStatus.BLOCKED,
            message="Real executor operation blocked because adapter is disabled by default",
            blocking_reasons=reasons,
            audit_event_count=1,
            product_runtime_git_write_allowed=False,
        )

    def cleanup_noop(self, session_id: str) -> RealExecutorOperationResult:
        return RealExecutorOperationResult(
            lifecycle_intent=RealExecutorLifecycleIntent.CLEANUP,
            status=RealExecutorOperationStatus.COMPLETED,
            session_id=session_id,
            message="Cleanup skipped safely because adapter is disabled by default",
            blocking_reasons=[self._config.disabled_reason, "cleanup_noop"],
            audit_event_count=1,
            product_runtime_git_write_allowed=False,
        )

    def poll_snapshot(self, session_id: str) -> RealExecutorPollSnapshot:
        return RealExecutorPollSnapshot(
            session_id=session_id,
            poll_state=RealExecutorPollState.UNKNOWN,
            message="Polling skipped because adapter is disabled by default",
            blocking_reasons=[self._config.disabled_reason, "session_not_started"],
            audit_event_count=1,
            product_runtime_git_write_allowed=False,
        )

    def audit_event(
        self,
        *,
        kind: str,
        summary: str,
        level: str = "warn",
        detail: str | None = None,
    ) -> DisabledRealExecutorAdapterAuditEvent:
        return DisabledRealExecutorAdapterAuditEvent(
            source=self._config.audit_source,
            kind=kind,
            level=level,
            summary=summary,
            detail=detail,
        )

    def _reasons(self, extra_reasons: list[str] | None = None) -> list[str]:
        return _dedupe_trimmed_strings(
            [self._config.disabled_reason, *(extra_reasons or [])],
        )


class DisabledRealExecutorAdapter:
    def __init__(
        self,
        config: DisabledRealExecutorAdapterConfig | None = None,
        preflight_service: RealExecutorPreflightService | None = None,
        preview_builder: RealExecutorLaunchPlanPreviewBuilder | None = None,
        result_factory: DisabledRealExecutorAdapterResultFactory | None = None,
    ) -> None:
        self._config = config or DisabledRealExecutorAdapterConfig()
        self._preflight_service = preflight_service or RealExecutorPreflightService()
        self._preview_builder = preview_builder or RealExecutorLaunchPlanPreviewBuilder()
        self._result_factory = result_factory or DisabledRealExecutorAdapterResultFactory(
            self._config,
        )

    def launch(self, context: RealExecutorLaunchContext) -> RealExecutorOperationResult:
        preflight = self._preflight_service.evaluate_launch(context)
        preview = self._preview_builder.build(
            RealExecutorLaunchPlanPreviewInput(
                preview_id=f"disabled-preview-{context.request_id}",
                context=context,
                preflight_result=preflight,
            ),
        )
        return self._result_factory.launch_blocked(
            context,
            extra_reasons=list(preflight.blocking_reasons),
            safe_summary=preview.safe_summary,
        )

    def poll(self, session_id: str) -> RealExecutorPollSnapshot:
        return self._result_factory.poll_snapshot(session_id)

    def cancel(self, session_id: str, reason: str) -> RealExecutorOperationResult:
        return self._result_factory.operation_blocked(
            RealExecutorLifecycleIntent.CANCEL,
            reason="cancel_disabled",
        )

    def kill(self, session_id: str, reason: str) -> RealExecutorOperationResult:
        return self._result_factory.operation_blocked(
            RealExecutorLifecycleIntent.KILL,
            reason="kill_disabled",
        )

    def cleanup(self, session_id: str) -> RealExecutorOperationResult:
        return self._result_factory.cleanup_noop(session_id)

    def audit_event(
        self,
        *,
        kind: str,
        summary: str,
        level: str = "warn",
        detail: str | None = None,
    ) -> DisabledRealExecutorAdapterAuditEvent:
        return self._result_factory.audit_event(
            kind=kind,
            level=level,
            summary=summary,
            detail=detail,
        )


__all__ = (
    "DISABLED_REASON",
    "DisabledRealExecutorAdapter",
    "DisabledRealExecutorAdapterAuditEvent",
    "DisabledRealExecutorAdapterConfig",
    "DisabledRealExecutorAdapterResultFactory",
)
