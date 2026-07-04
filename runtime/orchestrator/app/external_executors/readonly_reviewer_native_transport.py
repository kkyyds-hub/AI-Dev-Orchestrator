"""Native stdout capture transport for readonly reviewer execution."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.external_executors.actual_process_supervisor import (
    RealExecutorProcessSupervisor,
)
from app.external_executors.readonly_reviewer_transport import (
    ReadonlyReviewerTransportProtocol,
    ReadonlyReviewerTransportRawResult,
    ReadonlyReviewerTransportRequest,
)


_AGENT_SESSION_ID = "readonly-reviewer-native-capture"


class NativeReadonlyReviewerCaptureTransport(ReadonlyReviewerTransportProtocol):
    """Capture native reviewer stdout and leave validation to H-B1."""

    def __init__(
        self,
        *,
        workspace_path: str,
        timeout_seconds: float,
        process_supervisor: RealExecutorProcessSupervisor,
        popen_factory: Any,
        terminate_wait_seconds: float = 0.2,
    ) -> None:
        workspace = Path(workspace_path)
        if not workspace.is_absolute():
            raise ValueError("workspace_path must be absolute")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if terminate_wait_seconds <= 0:
            raise ValueError("terminate_wait_seconds must be positive")
        if process_supervisor is None:
            raise ValueError("process_supervisor is required")
        if popen_factory is None:
            raise ValueError("popen_factory is required")
        self._workspace_path = str(workspace)
        self._timeout_seconds = timeout_seconds
        self._terminate_wait_seconds = terminate_wait_seconds
        self._process_supervisor = process_supervisor
        self._popen_factory = popen_factory

    def execute(
        self,
        request: ReadonlyReviewerTransportRequest,
    ) -> ReadonlyReviewerTransportRawResult:
        argv = self._argv_for_executor(request.requested_reviewer_executor)
        process_handle_id = f"readonly-reviewer-{uuid4().hex}"
        process = None
        registered = False
        started = False
        codex_started = False
        claude_code_started = False

        try:
            process = self._popen_factory(
                list(argv),
                cwd=self._workspace_path,
                shell=False,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                close_fds=True,
            )
            started = True
            codex_started = request.requested_reviewer_executor == "codex"
            claude_code_started = (
                request.requested_reviewer_executor == "claude-code"
            )
            self._process_supervisor.register(
                process_handle_id,
                executor_label=request.requested_reviewer_executor,
                agent_session_id=_AGENT_SESSION_ID,
                workspace_path=self._workspace_path,
                process_adapter=process,
            )
            registered = True

            try:
                stdout_bytes, _stderr_bytes = process.communicate(
                    input=request.review_prompt_text.encode("utf-8"),
                    timeout=self._timeout_seconds,
                )
            except subprocess.TimeoutExpired:
                self._terminate_timeout_process(process_handle_id, process)
                return self._raw_result(
                    request=request,
                    transport_status="timeout",
                    transport_error_code="reviewer_native_timeout",
                    started=started,
                    executed=False,
                    codex_started=codex_started,
                    claude_code_started=claude_code_started,
                )

            returncode = getattr(process, "returncode", None)
            if returncode != 0:
                return self._raw_result(
                    request=request,
                    transport_status="failed",
                    transport_error_code="reviewer_native_exit_nonzero",
                    started=started,
                    executed=False,
                    codex_started=codex_started,
                    claude_code_started=claude_code_started,
                )

            try:
                raw_output_text = stdout_bytes.decode("utf-8")
            except UnicodeDecodeError:
                return self._raw_result(
                    request=request,
                    transport_status="failed",
                    transport_error_code="reviewer_stdout_invalid_utf8",
                    started=started,
                    executed=False,
                    codex_started=codex_started,
                    claude_code_started=claude_code_started,
                )

            return self._raw_result(
                request=request,
                transport_status="completed",
                transport_error_code=None,
                started=started,
                executed=True,
                codex_started=codex_started,
                claude_code_started=claude_code_started,
                raw_output_text=raw_output_text,
            )
        except Exception:
            if started:
                return self._raw_result(
                    request=request,
                    transport_status="failed",
                    transport_error_code="reviewer_native_failed",
                    started=started,
                    executed=False,
                    codex_started=codex_started,
                    claude_code_started=claude_code_started,
                )
            return self._raw_result(
                request=request,
                transport_status="failed",
                transport_error_code="reviewer_native_launch_failed",
                started=False,
                executed=False,
                codex_started=False,
                claude_code_started=False,
            )
        finally:
            if registered:
                self._process_supervisor.cleanup(process_handle_id)

    def _terminate_timeout_process(self, process_handle_id: str, process: Any) -> None:
        self._process_supervisor.terminate(process_handle_id)
        try:
            process.wait(timeout=self._terminate_wait_seconds)
        except subprocess.TimeoutExpired:
            self._process_supervisor.kill(process_handle_id)
            try:
                process.wait(timeout=self._terminate_wait_seconds)
            except subprocess.TimeoutExpired:
                pass

    @staticmethod
    def _argv_for_executor(requested_reviewer_executor: str) -> tuple[str, ...]:
        if requested_reviewer_executor == "codex":
            return ("codex",)
        if requested_reviewer_executor == "claude-code":
            return ("claude",)
        raise ValueError("requested_reviewer_executor is not supported")

    @staticmethod
    def _raw_result(
        *,
        request: ReadonlyReviewerTransportRequest,
        transport_status: str,
        transport_error_code: str | None,
        started: bool,
        executed: bool,
        codex_started: bool,
        claude_code_started: bool,
        raw_output_text: str = "",
    ) -> ReadonlyReviewerTransportRawResult:
        return ReadonlyReviewerTransportRawResult(
            transport_status=transport_status,
            requested_reviewer_executor=request.requested_reviewer_executor,
            raw_output_text=raw_output_text,
            transport_error_code=transport_error_code,
            transport_invoked=True,
            execution_mode="native_capture_transport",
            real_reviewer_started=started,
            real_reviewer_executed=executed,
            native_process_started=started,
            provider_called=False,
            codex_started=codex_started,
            claude_code_started=claude_code_started,
        )


__all__ = ("NativeReadonlyReviewerCaptureTransport",)
