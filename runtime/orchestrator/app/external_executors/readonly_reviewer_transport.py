"""Readonly reviewer transport protocol and fake transport for P21-C-H-B2-A."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


# ── Transport status ──────────────────────────────────────────────────


ReadonlyReviewerTransportStatus = Literal[
    "completed",
    "blocked",
    "timeout",
    "failed",
]

ReadonlyReviewerTransportExecutionMode = Literal[
    "fake_transport",
    "native_capture_transport",
]


# ── Transport request ─────────────────────────────────────────────────


class ReadonlyReviewerTransportRequest(BaseModel):
    """Internal transport input. Not an API request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    requested_reviewer_executor: Literal["codex", "claude-code"]
    review_prompt_text: str = Field(min_length=1)
    review_prompt_sha256: str = Field(min_length=64, max_length=64)
    review_prompt_bytes: int = Field(gt=0)
    review_scope_paths: list[str] = Field(min_length=1)
    review_output_schema_version: str = Field(min_length=1)


# ── Transport raw result ──────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ReadonlyReviewerTransportRawResult:
    """Raw transport result. Contains raw_output_text only transitively."""

    transport_status: ReadonlyReviewerTransportStatus
    requested_reviewer_executor: str
    raw_output_text: str = field(repr=False, compare=False, default="")
    transport_error_code: str | None = None
    transport_invoked: bool = False
    execution_mode: ReadonlyReviewerTransportExecutionMode = "fake_transport"
    real_reviewer_started: bool = False
    real_reviewer_executed: bool = False
    native_process_started: bool = False
    provider_called: bool = False
    codex_started: bool = False
    claude_code_started: bool = False


# ── Transport protocol ────────────────────────────────────────────────


@runtime_checkable
class ReadonlyReviewerTransportProtocol(Protocol):
    """Minimal transport protocol for readonly reviewer execution."""

    def execute(
        self,
        request: ReadonlyReviewerTransportRequest,
    ) -> ReadonlyReviewerTransportRawResult:
        ...


# ── Fake transport ────────────────────────────────────────────────────


class FakeReadonlyReviewerTransport:
    """Fake transport for testing the adapter seam. Never starts a real reviewer."""

    def __init__(
        self,
        *,
        raw_output_text: str = "",
        transport_status: ReadonlyReviewerTransportStatus = "completed",
        transport_error_code: str | None = None,
    ) -> None:
        self._raw_output_text = raw_output_text
        self._transport_status = transport_status
        self._transport_error_code = transport_error_code
        self.execute_calls: int = 0
        self.last_request: ReadonlyReviewerTransportRequest | None = None

    def execute(
        self,
        request: ReadonlyReviewerTransportRequest,
    ) -> ReadonlyReviewerTransportRawResult:
        self.execute_calls += 1
        self.last_request = request
        return ReadonlyReviewerTransportRawResult(
            transport_status=self._transport_status,
            requested_reviewer_executor=request.requested_reviewer_executor,
            raw_output_text=self._raw_output_text,
            transport_error_code=self._transport_error_code,
            transport_invoked=True,
            execution_mode="fake_transport",
            real_reviewer_started=False,
            real_reviewer_executed=False,
            native_process_started=False,
            provider_called=False,
            codex_started=False,
            claude_code_started=False,
        )


__all__ = (
    "FakeReadonlyReviewerTransport",
    "ReadonlyReviewerTransportProtocol",
    "ReadonlyReviewerTransportExecutionMode",
    "ReadonlyReviewerTransportRawResult",
    "ReadonlyReviewerTransportRequest",
    "ReadonlyReviewerTransportStatus",
)
