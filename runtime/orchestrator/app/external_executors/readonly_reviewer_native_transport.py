"""Native stdout capture transport for readonly reviewer execution."""

from __future__ import annotations

import os
import selectors
import subprocess
import time
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
_STDOUT_CHUNK_BYTES = 8192
_CLAUDE_REVIEW_INSTRUCTION = (
    "Review the content provided through stdin and return only the requested "
    "final review output."
)


class NativeReadonlyReviewerCaptureTransport(ReadonlyReviewerTransportProtocol):
    """Capture native reviewer stdout and leave validation to H-B1."""

    def __init__(
        self,
        *,
        workspace_path: str,
        timeout_seconds: float,
        max_output_bytes: int,
        process_supervisor: RealExecutorProcessSupervisor,
        popen_factory: Any,
        terminate_wait_seconds: float = 0.2,
    ) -> None:
        workspace = Path(workspace_path)
        if not workspace.is_absolute():
            raise ValueError("workspace_path must be absolute")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not isinstance(max_output_bytes, int) or max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive")
        if terminate_wait_seconds <= 0:
            raise ValueError("terminate_wait_seconds must be positive")
        if process_supervisor is None:
            raise ValueError("process_supervisor is required")
        if popen_factory is None:
            raise ValueError("popen_factory is required")
        self._workspace_path = str(workspace)
        self._timeout_seconds = timeout_seconds
        self._max_output_bytes = max_output_bytes
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
                stderr=subprocess.DEVNULL,
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
                stdout_bytes = self._capture_stdout_bounded(
                    process=process,
                    process_handle_id=process_handle_id,
                    prompt_bytes=request.review_prompt_text.encode("utf-8"),
                )
            except subprocess.TimeoutExpired:
                self._stop_started_process(
                    process_handle_id=process_handle_id,
                    process=process,
                    registered=registered,
                )
                return self._raw_result(
                    request=request,
                    transport_status="timeout",
                    transport_error_code="reviewer_native_timeout",
                    started=started,
                    executed=False,
                    codex_started=codex_started,
                    claude_code_started=claude_code_started,
                )
            except _StdoutTooLargeError:
                self._stop_started_process(
                    process_handle_id=process_handle_id,
                    process=process,
                    registered=registered,
                )
                return self._raw_result(
                    request=request,
                    transport_status="failed",
                    transport_error_code="reviewer_stdout_too_large",
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
                self._stop_started_process(
                    process_handle_id=process_handle_id,
                    process=process,
                    registered=registered,
                )
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
                try:
                    self._process_supervisor.cleanup(process_handle_id)
                except Exception:
                    pass

    def _capture_stdout_bounded(
        self,
        *,
        process: Any,
        process_handle_id: str,
        prompt_bytes: bytes,
    ) -> bytes:
        if getattr(process, "stdin", None) is None:
            raise RuntimeError("reviewer stdin pipe missing")
        if getattr(process, "stdout", None) is None:
            raise RuntimeError("reviewer stdout pipe missing")

        deadline = time.monotonic() + self._timeout_seconds
        process.stdin.write(prompt_bytes)
        process.stdin.close()
        stdout_fileno = self._stdout_fileno(process.stdout)
        if stdout_fileno is None:
            return self._capture_stdout_bounded_without_fileno(
                process=process,
                deadline=deadline,
            )

        selector = selectors.DefaultSelector()
        selector.register(stdout_fileno, selectors.EVENT_READ)
        try:
            return self._capture_stdout_bounded_with_selector(
                process=process,
                stdout_fileno=stdout_fileno,
                selector=selector,
                deadline=deadline,
            )
        finally:
            selector.close()

    def _capture_stdout_bounded_with_selector(
        self,
        *,
        process: Any,
        stdout_fileno: int,
        selector: selectors.BaseSelector,
        deadline: float,
    ) -> bytes:
        captured = bytearray()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(
                    cmd="readonly-reviewer-native-capture",
                    timeout=self._timeout_seconds,
                )

            events = selector.select(timeout=min(remaining, 0.05))
            if events:
                chunk = os.read(
                    stdout_fileno,
                    min(
                        _STDOUT_CHUNK_BYTES,
                        self._max_output_bytes - len(captured) + 1,
                    ),
                )
                if not chunk:
                    break
                captured.extend(chunk)
                if len(captured) > self._max_output_bytes:
                    raise _StdoutTooLargeError()
                continue

            if self._process_poll(process) is not None:
                break

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(
                cmd="readonly-reviewer-native-capture",
                timeout=self._timeout_seconds,
            )
        process.wait(timeout=remaining)
        return bytes(captured)

    def _capture_stdout_bounded_without_fileno(
        self,
        *,
        process: Any,
        deadline: float,
    ) -> bytes:
        captured = bytearray()

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(
                    cmd="readonly-reviewer-native-capture",
                    timeout=self._timeout_seconds,
                )

            chunk = process.stdout.read(
                min(
                    _STDOUT_CHUNK_BYTES,
                    self._max_output_bytes - len(captured) + 1,
                )
            )
            if chunk:
                captured.extend(chunk)
                if len(captured) > self._max_output_bytes:
                    raise _StdoutTooLargeError()
                continue

            returncode = self._process_poll(process)
            if returncode is not None:
                break
            try:
                process.wait(timeout=min(remaining, 0.05))
            except subprocess.TimeoutExpired:
                continue

        return bytes(captured)

    @staticmethod
    def _stdout_fileno(stdout_pipe: Any) -> int | None:
        fileno = getattr(stdout_pipe, "fileno", None)
        if fileno is None:
            return None
        try:
            return fileno()
        except (OSError, ValueError, TypeError):
            return None

    def _stop_started_process(
        self,
        *,
        process_handle_id: str,
        process: Any,
        registered: bool,
    ) -> None:
        self._terminate_process(
            process_handle_id=process_handle_id,
            process=process,
            registered=registered,
        )
        try:
            process.wait(timeout=self._terminate_wait_seconds)
        except subprocess.TimeoutExpired:
            self._kill_process(
                process_handle_id=process_handle_id,
                process=process,
                registered=registered,
            )
            try:
                process.wait(timeout=self._terminate_wait_seconds)
            except Exception:
                pass
        except Exception:
            self._kill_process(
                process_handle_id=process_handle_id,
                process=process,
                registered=registered,
            )

    def _terminate_process(
        self,
        *,
        process_handle_id: str,
        process: Any,
        registered: bool,
    ) -> None:
        try:
            if registered:
                self._process_supervisor.terminate(process_handle_id)
            else:
                self._call_process_method(process, "terminate")
        except Exception:
            pass

    def _kill_process(
        self,
        *,
        process_handle_id: str,
        process: Any,
        registered: bool,
    ) -> None:
        try:
            if registered:
                self._process_supervisor.kill(process_handle_id)
            else:
                self._call_process_method(process, "kill")
        except Exception:
            pass

    @staticmethod
    def _call_process_method(process: Any, method_name: str) -> None:
        method = getattr(process, method_name, None)
        if method is not None:
            method()

    @staticmethod
    def _process_poll(process: Any) -> int | None:
        poll = getattr(process, "poll", None)
        if poll is None:
            return None
        return poll()

    @staticmethod
    def _argv_for_executor(requested_reviewer_executor: str) -> tuple[str, ...]:
        if requested_reviewer_executor == "codex":
            return (
                "codex",
                "exec",
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--color",
                "never",
                "-",
            )
        if requested_reviewer_executor == "claude-code":
            return (
                "claude",
                "-p",
                _CLAUDE_REVIEW_INSTRUCTION,
                "--permission-mode",
                "plan",
                "--no-session-persistence",
            )
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


class _StdoutTooLargeError(RuntimeError):
    pass
