"""Resolve concrete transports for readonly reviewer execution."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.external_executors.actual_process_supervisor import (
    RealExecutorProcessSupervisor,
)
from app.external_executors.readonly_reviewer_codex_app_server_transport import (
    CodexAppServerReadonlyReviewerTransport,
)
from app.external_executors.readonly_reviewer_native_transport import (
    NativeReadonlyReviewerCaptureTransport,
)
from app.external_executors.readonly_reviewer_transport import (
    ReadonlyReviewerTransportProtocol,
)


class ReadonlyReviewerTransportResolver:
    """Create the concrete transport selected by validated executor evidence."""

    def __init__(
        self,
        *,
        workspace_path: str,
        timeout_seconds: float,
        max_output_bytes: int,
        process_supervisor: RealExecutorProcessSupervisor,
        popen_factory: Any,
        terminate_wait_seconds: float = 0.2,
        claude_code_child_environment: Mapping[str, str] | None = None,
    ) -> None:
        self._workspace_path = workspace_path
        self._timeout_seconds = timeout_seconds
        self._max_output_bytes = max_output_bytes
        self._process_supervisor = process_supervisor
        self._popen_factory = popen_factory
        self._terminate_wait_seconds = terminate_wait_seconds
        self._claude_code_child_environment = claude_code_child_environment

    def __call__(
        self,
        requested_reviewer_executor: str,
    ) -> ReadonlyReviewerTransportProtocol:
        if requested_reviewer_executor == "codex":
            return CodexAppServerReadonlyReviewerTransport(
                workspace_path=self._workspace_path,
                timeout_seconds=self._timeout_seconds,
                max_output_bytes=self._max_output_bytes,
                process_supervisor=self._process_supervisor,
                popen_factory=self._popen_factory,
                terminate_wait_seconds=self._terminate_wait_seconds,
            )
        if requested_reviewer_executor == "claude-code":
            return NativeReadonlyReviewerCaptureTransport(
                workspace_path=self._workspace_path,
                timeout_seconds=self._timeout_seconds,
                max_output_bytes=self._max_output_bytes,
                process_supervisor=self._process_supervisor,
                popen_factory=self._popen_factory,
                terminate_wait_seconds=self._terminate_wait_seconds,
                claude_code_child_environment=(
                    self._claude_code_child_environment
                ),
            )
        raise ValueError(
            "unsupported readonly reviewer executor: "
            f"{requested_reviewer_executor!r}"
        )


__all__ = ("ReadonlyReviewerTransportResolver",)
