"""Operator validation gate for silent real executor precheck.

This module models an explicit human operator checkpoint before any future
native phase. An accepted decision only permits noop/manual validation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


OPERATOR_VALIDATION_SAFE_PHRASE = "I understand this is noop validation only"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _trim_optional_string(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


class _OperatorValidationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RealExecutorOperatorValidationStatus(StrEnum):
    MISSING = "missing"
    PENDING = "pending"
    ACCEPTED_FOR_NOOP_VALIDATION = "accepted_for_noop_validation"
    REJECTED = "rejected"


class RealExecutorOperatorValidationScope(StrEnum):
    NOOP_LIFECYCLE_VALIDATION = "noop_lifecycle_validation"
    SILENT_DISPATCH_READINESS = "silent_dispatch_readiness"
    NATIVE_LAUNCH_PRECHECK = "native_launch_precheck"


class RealExecutorOperatorValidationInput(_OperatorValidationModel):
    operator_confirmed: bool = False
    confirmation_phrase: str | None = None
    validation_scope: RealExecutorOperatorValidationScope = (
        RealExecutorOperatorValidationScope.NOOP_LIFECYCLE_VALIDATION
    )
    native_process_started: bool = False
    product_runtime_git_write_allowed: bool = False
    frontend_required: bool = False
    frontend_change_allowed: bool = False
    secret_exposure_blocked: bool = True
    environment_dump_blocked: bool = True

    @field_validator("confirmation_phrase", mode="before")
    @classmethod
    def trim_confirmation_phrase(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    @field_validator(
        "native_process_started",
        "product_runtime_git_write_allowed",
        "frontend_required",
        "frontend_change_allowed",
    )
    @classmethod
    def enforce_disabled_flags(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError("operator validation keeps this capability disabled")
        return value

    @field_validator("secret_exposure_blocked", "environment_dump_blocked")
    @classmethod
    def enforce_blocked_safety_flags(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("operator validation requires safety blocking flags")
        return value


class RealExecutorOperatorValidationDecision(_OperatorValidationModel):
    status: RealExecutorOperatorValidationStatus
    operator_confirmed: bool
    confirmation_phrase: str | None = None
    validation_scope: RealExecutorOperatorValidationScope
    message: str | None = None
    validation_reasons: list[str] = Field(default_factory=list)
    native_process_started: bool = False
    product_runtime_git_write_allowed: bool = False
    frontend_required: bool = False
    frontend_change_allowed: bool = False
    secret_exposure_blocked: bool = True
    environment_dump_blocked: bool = True
    decided_at: datetime = Field(default_factory=_utc_now)

    @field_validator(
        "native_process_started",
        "product_runtime_git_write_allowed",
        "frontend_required",
        "frontend_change_allowed",
    )
    @classmethod
    def enforce_disabled_flags(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError("operator validation decision keeps this capability disabled")
        return value

    @field_validator("secret_exposure_blocked", "environment_dump_blocked")
    @classmethod
    def enforce_blocked_safety_flags(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("operator validation decision requires safety blocking flags")
        return value


class RealExecutorOperatorValidationGate:
    def evaluate(
        self,
        validation_input: RealExecutorOperatorValidationInput | None = None,
    ) -> RealExecutorOperatorValidationDecision:
        source = validation_input or RealExecutorOperatorValidationInput()

        if not source.operator_confirmed and source.confirmation_phrase is None:
            return self._decision(
                source,
                status=RealExecutorOperatorValidationStatus.MISSING,
                message="Operator confirmation has not been provided",
                validation_reasons=["operator_confirmation_missing"],
            )

        if not source.operator_confirmed:
            return self._decision(
                source,
                status=RealExecutorOperatorValidationStatus.PENDING,
                message="Operator confirmation is required before noop/manual precheck",
                validation_reasons=["operator_confirmation_pending"],
            )

        if source.confirmation_phrase != OPERATOR_VALIDATION_SAFE_PHRASE:
            return self._decision(
                source,
                status=RealExecutorOperatorValidationStatus.REJECTED,
                message="Operator confirmation phrase did not match noop/manual precheck phrase",
                validation_reasons=["confirmation_phrase_mismatch"],
            )

        return self._decision(
            source,
            status=RealExecutorOperatorValidationStatus.ACCEPTED_FOR_NOOP_VALIDATION,
            message="Operator validation accepted for noop/manual precheck only",
            validation_reasons=[],
        )

    def _decision(
        self,
        source: RealExecutorOperatorValidationInput,
        *,
        status: RealExecutorOperatorValidationStatus,
        message: str,
        validation_reasons: list[str],
    ) -> RealExecutorOperatorValidationDecision:
        return RealExecutorOperatorValidationDecision(
            status=status,
            operator_confirmed=source.operator_confirmed,
            confirmation_phrase=source.confirmation_phrase,
            validation_scope=source.validation_scope,
            message=message,
            validation_reasons=validation_reasons,
            native_process_started=False,
            product_runtime_git_write_allowed=False,
            frontend_required=False,
            frontend_change_allowed=False,
            secret_exposure_blocked=True,
            environment_dump_blocked=True,
        )


__all__ = (
    "OPERATOR_VALIDATION_SAFE_PHRASE",
    "RealExecutorOperatorValidationDecision",
    "RealExecutorOperatorValidationGate",
    "RealExecutorOperatorValidationInput",
    "RealExecutorOperatorValidationScope",
    "RealExecutorOperatorValidationStatus",
)
