"""Versioned, bounded Director Runtime protocol models.

These models describe immutable JSON snapshots and untrusted runtime candidates.
They intentionally contain no persistence, provider, filesystem, or executable
handles and perform no authoritative state mutation.
"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator


DIRECTOR_RUNTIME_SCHEMA_VERSION = "p26-big-director-runtime/v1"
_SENSITIVE_HANDLE_TOKENS = (
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "password",
    "secret",
)
_CANONICAL_TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$"
)


class DirectorRuntimeProtocolError(ValueError):
    """Safe, fail-closed protocol boundary failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class _ProtocolModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class DirectorRuntimeCurrentUserMessage(_ProtocolModel):
    content: str
    occurred_at: str
    actor_claim: Literal["user"]

    @field_validator("content", "occurred_at")
    @classmethod
    def require_non_blank(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("director_runtime_required_string_invalid")
        return value

    @field_validator("occurred_at")
    @classmethod
    def require_iso_timestamp(cls, value: str) -> str:
        if not _CANONICAL_TIMESTAMP_PATTERN.fullmatch(value):
            raise ValueError("director_runtime_occurred_at_invalid")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("director_runtime_occurred_at_invalid") from exc
        if parsed.tzinfo is None:
            raise ValueError("director_runtime_occurred_at_timezone_missing")
        return value


class DirectorRuntimeFormalizationContext(_ProtocolModel):
    proposal: dict[str, Any] | None
    plan_version: dict[str, Any] | None

    @field_validator("proposal", "plan_version")
    @classmethod
    def validate_snapshot(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is not None:
            _require_bounded_json(value, "director_runtime_snapshot_invalid")
        return value


class DirectorRuntimeGovernanceBoundaries(_ProtocolModel):
    authoritative_write: Literal[False]
    director_may_modify_code: Literal[False]
    formalization_requires_explicit_request: Literal[True]
    confirmation_is_separate: Literal[True]
    execution_boundary: Literal["no_task_run_agent_session_before_execution"]


class DirectorRuntimeAvailableSkill(_ProtocolModel):
    skill_id: str
    version: str
    enabled: bool

    @field_validator("skill_id", "version")
    @classmethod
    def require_non_blank(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("director_runtime_skill_field_invalid")
        return value


class DirectorRuntimeAvailableTool(_ProtocolModel):
    tool_id: str
    allowed: bool
    authorization_id: str | None
    idempotency_key: str | None

    @field_validator("tool_id")
    @classmethod
    def require_tool_id(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("director_runtime_tool_id_invalid")
        return value

    @field_validator("authorization_id", "idempotency_key")
    @classmethod
    def validate_optional_identifier(cls, value: str | None) -> str | None:
        if value is not None and (not value or value != value.strip()):
            raise ValueError("director_runtime_tool_identifier_invalid")
        return value

    @model_validator(mode="after")
    def require_explicit_authorization(self) -> "DirectorRuntimeAvailableTool":
        if self.allowed and (
            self.authorization_id is None or self.idempotency_key is None
        ):
            raise ValueError("director_runtime_tool_authorization_incomplete")
        if not self.allowed and (
            self.authorization_id is not None or self.idempotency_key is not None
        ):
            raise ValueError("director_runtime_tool_authorization_implicit")
        return self


class DirectorRuntimeConfig(_ProtocolModel):
    model_id: str
    provider_profile_id: str
    timeout_ms: float
    max_tool_rounds: int

    @field_validator("model_id", "provider_profile_id")
    @classmethod
    def require_non_blank(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("director_runtime_config_identifier_invalid")
        return value

    @field_validator("timeout_ms")
    @classmethod
    def require_positive_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("director_runtime_timeout_invalid")
        return value

    @field_validator("max_tool_rounds")
    @classmethod
    def require_non_negative_rounds(cls, value: int) -> int:
        if value < 0:
            raise ValueError("director_runtime_max_tool_rounds_invalid")
        return value


class DirectorRuntimeRequest(_ProtocolModel):
    schema_version: Literal[DIRECTOR_RUNTIME_SCHEMA_VERSION]
    request_id: str
    project_id: str
    session_id: str
    message_id: str
    current_user_message: DirectorRuntimeCurrentUserMessage
    authoritative_facts: dict[str, Any]
    active_discussion_workspace: dict[str, Any] | None
    relevant_discussion_events: list[dict[str, Any]]
    active_formalization: DirectorRuntimeFormalizationContext
    governance_boundaries: DirectorRuntimeGovernanceBoundaries
    available_skills: list[DirectorRuntimeAvailableSkill]
    available_tools: list[DirectorRuntimeAvailableTool]
    permission_context: dict[str, Any]
    runtime_config: DirectorRuntimeConfig

    @field_validator("request_id", "project_id", "session_id", "message_id")
    @classmethod
    def require_identity(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("director_runtime_identity_invalid")
        return value

    @field_validator(
        "authoritative_facts",
        "active_discussion_workspace",
        "relevant_discussion_events",
        "permission_context",
    )
    @classmethod
    def validate_bounded_snapshots(cls, value: Any) -> Any:
        _require_bounded_json(value, "director_runtime_live_handle_rejected")
        return value

    @model_validator(mode="after")
    def require_unique_tool_ids(self) -> "DirectorRuntimeRequest":
        tool_ids = [tool.tool_id for tool in self.available_tools]
        if len(tool_ids) != len(set(tool_ids)):
            raise ValueError("director_runtime_tool_id_duplicate")
        return self


class DirectorTurnSemantics(_ProtocolModel):
    conversation_mode: str
    formal_action_requested: bool
    hypothetical_action: bool
    confidence: float | None

    @field_validator("conversation_mode")
    @classmethod
    def require_conversation_mode(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("director_runtime_conversation_mode_invalid")
        return value


class DirectorDiscussionLifecycle(_ProtocolModel):
    observed_status: str | None
    suggested_next_status: str | None


class DirectorFormalizationCandidate(_ProtocolModel):
    proposal_candidate: dict[str, Any] | None
    readiness: Literal["not_ready", "candidate", "requires_confirmation"]

    @field_validator("proposal_candidate")
    @classmethod
    def validate_candidate(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is not None:
            _require_bounded_json(value, "director_runtime_candidate_invalid")
        return value


class DirectorToolActivity(_ProtocolModel):
    tool_id: str
    authorization_id: str | None
    status: Literal[
        "requested",
        "authorized",
        "started",
        "succeeded",
        "failed",
        "cancelled",
    ]
    idempotency_key: str | None
    safe_summary: str | None

    @field_validator("tool_id")
    @classmethod
    def require_tool_id(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("director_runtime_tool_activity_invalid")
        return value


class DirectorSourceReference(_ProtocolModel):
    message_id: str
    kind: str

    @field_validator("message_id", "kind")
    @classmethod
    def require_non_blank(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("director_runtime_source_reference_invalid")
        return value


class DirectorRuntimeMetadata(_ProtocolModel):
    runtime_state: Literal["ready", "busy", "degraded", "failed"]
    model_id: str
    provider_profile_id: str
    usage: dict[str, float | None]
    duration_ms: float
    attempt: int

    @field_validator("model_id", "provider_profile_id")
    @classmethod
    def require_non_blank(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("director_runtime_metadata_identifier_invalid")
        return value

    @field_validator("usage")
    @classmethod
    def validate_usage(cls, value: dict[str, float | None]) -> dict[str, float | None]:
        for key, usage_value in value.items():
            if not key or key != key.strip() or (
                usage_value is not None and not isinstance(usage_value, (int, float))
            ):
                raise ValueError("director_runtime_usage_invalid")
        return value

    @field_validator("duration_ms")
    @classmethod
    def require_non_negative_duration(cls, value: float) -> float:
        if value < 0:
            raise ValueError("director_runtime_duration_invalid")
        return value

    @field_validator("attempt")
    @classmethod
    def require_non_negative_attempt(cls, value: int) -> int:
        if value < 0:
            raise ValueError("director_runtime_attempt_invalid")
        return value


class DirectorRuntimeErrorPayload(_ProtocolModel):
    code: str
    stage: Literal["request", "model", "tool", "result_validation", "runtime"]
    retryable: bool
    safe_message: str

    @field_validator("code", "safe_message")
    @classmethod
    def require_non_blank(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("director_runtime_error_invalid")
        return value


class DirectorTurnResult(_ProtocolModel):
    schema_version: Literal[DIRECTOR_RUNTIME_SCHEMA_VERSION]
    request_id: str
    response_text: str
    turn_semantics: DirectorTurnSemantics
    discussion_lifecycle: DirectorDiscussionLifecycle
    discussion_delta_candidate: dict[str, Any] | None
    formalization: DirectorFormalizationCandidate
    tool_activity: list[DirectorToolActivity]
    source_references: list[DirectorSourceReference]
    runtime_metadata: DirectorRuntimeMetadata
    error: DirectorRuntimeErrorPayload | None

    @field_validator("request_id")
    @classmethod
    def require_request_id(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("director_runtime_result_request_id_invalid")
        return value

    @field_validator("discussion_delta_candidate")
    @classmethod
    def validate_discussion_candidate(
        cls, value: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        if value is not None:
            _require_bounded_json(value, "director_runtime_candidate_invalid")
        return value

    @model_validator(mode="after")
    def reject_partial_error_result(self) -> "DirectorTurnResult":
        if self.error is not None and (
            self.discussion_delta_candidate is not None
            or self.formalization.proposal_candidate is not None
        ):
            raise ValueError("director_runtime_error_result_contains_candidate")
        return self


class DirectorRuntimeFailure(_ProtocolModel):
    code: str
    stage: Literal["request", "model", "tool", "result_validation", "runtime"]
    retryable: bool
    safe_message: str


def serialize_director_runtime_request(request: DirectorRuntimeRequest) -> dict[str, Any]:
    """Return the bounded JSON snapshot passed to the runtime transport."""

    validated = validate_director_runtime_request(request.model_dump(mode="python"))
    return validated.model_dump(mode="json")


def validate_director_runtime_request(payload: Any) -> DirectorRuntimeRequest:
    """Reject malformed requests and non-JSON live handles before transport."""

    try:
        return DirectorRuntimeRequest.model_validate(payload)
    except (ValidationError, TypeError, ValueError) as exc:
        raise DirectorRuntimeProtocolError("director_runtime_request_invalid") from exc


def parse_director_turn_result(
    payload: Any,
    *,
    expected_request_id: str,
    authorized_tools: list[DirectorRuntimeAvailableTool] | None = None,
) -> DirectorTurnResult:
    """Parse one all-or-nothing untrusted candidate correlated to its request."""

    try:
        result = DirectorTurnResult.model_validate(payload)
    except (ValidationError, TypeError, ValueError) as exc:
        raise DirectorRuntimeProtocolError("director_runtime_result_invalid") from exc
    if result.request_id != expected_request_id:
        raise DirectorRuntimeProtocolError("director_runtime_result_request_id_mismatch")
    if authorized_tools is not None:
        by_tool_id = {tool.tool_id: tool for tool in authorized_tools}
        for activity in result.tool_activity:
            authorization = by_tool_id.get(activity.tool_id)
            if (
                authorization is None
                or not authorization.allowed
                or authorization.authorization_id != activity.authorization_id
                or authorization.idempotency_key != activity.idempotency_key
            ):
                raise DirectorRuntimeProtocolError(
                    "director_runtime_result_tool_activity_unauthorized"
                )
    return result


def normalize_runtime_failure(
    *,
    code: str,
    stage: Literal["request", "model", "tool", "result_validation", "runtime"],
    retryable: bool,
    safe_message: str,
) -> DirectorRuntimeFailure:
    """Create a sanitized failure object without preserving raw transport detail."""

    return DirectorRuntimeFailure(
        code=code,
        stage=stage,
        retryable=retryable,
        safe_message=safe_message,
    )


def _require_bounded_json(value: Any, error_code: str) -> None:
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, float):
        if value != value or value in {float("inf"), float("-inf")}:
            raise ValueError(error_code)
        return
    if isinstance(value, int):
        return
    if isinstance(value, list):
        for item in value:
            _require_bounded_json(item, error_code)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or _is_sensitive_handle_key(key):
                raise ValueError(error_code)
            _require_bounded_json(item, error_code)
        return
    raise ValueError(error_code)


def _is_sensitive_handle_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    if any(token in normalized for token in _SENSITIVE_HANDLE_TOKENS):
        return True
    return normalized == "token" or normalized.endswith("_token") or normalized.endswith(
        "_token_value"
    )


__all__ = (
    "DIRECTOR_RUNTIME_SCHEMA_VERSION",
    "DirectorRuntimeAvailableSkill",
    "DirectorRuntimeAvailableTool",
    "DirectorRuntimeConfig",
    "DirectorRuntimeFailure",
    "DirectorRuntimeProtocolError",
    "DirectorRuntimeRequest",
    "DirectorTurnResult",
    "normalize_runtime_failure",
    "parse_director_turn_result",
    "serialize_director_runtime_request",
    "validate_director_runtime_request",
)
