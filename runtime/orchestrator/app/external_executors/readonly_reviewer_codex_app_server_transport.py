"""Codex app-server stdio transport for readonly reviewer execution."""

from __future__ import annotations

import json
import os
import subprocess
import threading
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


_AGENT_SESSION_ID = "readonly-reviewer-codex-app-server"
_CLIENT_INFO = {
    "name": "ai_dev_orchestrator_readonly_reviewer",
    "title": "AI Dev Orchestrator Readonly Reviewer",
    "version": "0.1.0",
}
_PROCESS_ARGV = (
    "codex",
    "app-server",
    "--listen",
    "stdio://",
)
_STDOUT_CHUNK_BYTES = 8192
_STDIN_CHUNK_BYTES = 8192
_MAX_PROTOCOL_LINE_BYTES = 1024 * 1024


class CodexAppServerReadonlyReviewerTransport(ReadonlyReviewerTransportProtocol):
    """Run a readonly Codex app-server turn and capture final agent output."""

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
        if request.requested_reviewer_executor != "codex":
            raise ValueError("requested_reviewer_executor is not supported")

        process_handle_id = f"readonly-reviewer-codex-app-server-{uuid4().hex}"
        process = None
        registered = False
        started = False
        reader = None
        writer_handles: list[_StdinWriterHandle] = []

        try:
            process = self._popen_factory(
                list(_PROCESS_ARGV),
                cwd=self._workspace_path,
                shell=False,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
            started = True
            self._process_supervisor.register(
                process_handle_id,
                executor_label="codex",
                agent_session_id=_AGENT_SESSION_ID,
                workspace_path=self._workspace_path,
                process_adapter=process,
            )
            registered = True
            deadline = time.monotonic() + self._timeout_seconds
            reader = self._start_stdout_reader(process=process)

            try:
                raw_output_text = self._run_protocol(
                    request=request,
                    process=process,
                    reader=reader,
                    writer_handles=writer_handles,
                    deadline=deadline,
                )
            except _TransportFailure as exc:
                return self._raw_result(
                    request=request,
                    transport_status=exc.transport_status,
                    transport_error_code=exc.transport_error_code,
                    started=started,
                    executed=False,
                )

            if len(raw_output_text.encode("utf-8")) > self._max_output_bytes:
                return self._raw_result(
                    request=request,
                    transport_status="failed",
                    transport_error_code="reviewer_stdout_too_large",
                    started=started,
                    executed=False,
                )

            return self._raw_result(
                request=request,
                transport_status="completed",
                transport_error_code=None,
                started=started,
                executed=True,
                raw_output_text=raw_output_text,
            )
        except Exception:
            if started:
                return self._raw_result(
                    request=request,
                    transport_status="failed",
                    transport_error_code="reviewer_native_failed",
                    started=True,
                    executed=False,
                )
            return self._raw_result(
                request=request,
                transport_status="failed",
                transport_error_code="reviewer_native_launch_failed",
                started=False,
                executed=False,
            )
        finally:
            if started:
                self._stop_started_process(
                    process_handle_id=process_handle_id,
                    process=process,
                    registered=registered,
                    reader=reader,
                    writer_handles=writer_handles,
                )
            elif registered:
                self._cleanup_supervisor(process_handle_id)

    def _run_protocol(
        self,
        *,
        request: ReadonlyReviewerTransportRequest,
        process: Any,
        reader: "_StdoutReaderHandle",
        writer_handles: list["_StdinWriterHandle"],
        deadline: float,
    ) -> str:
        self._send_jsonl_bounded(
            process=process,
            message={
                "id": 1,
                "method": "initialize",
                "params": {"clientInfo": dict(_CLIENT_INFO)},
            },
            writer_handles=writer_handles,
            deadline=deadline,
        )
        initialize_response = self._wait_for_response(
            reader=reader,
            request_id=1,
            deadline=deadline,
            failure_code="reviewer_codex_app_server_initialize_failed",
        )
        if "result" not in initialize_response:
            raise _TransportFailure(
                "failed",
                "reviewer_codex_app_server_initialize_failed",
            )

        self._send_jsonl_bounded(
            process=process,
            message={"method": "initialized", "params": {}},
            writer_handles=writer_handles,
            deadline=deadline,
        )
        self._send_jsonl_bounded(
            process=process,
            message={
                "id": 2,
                "method": "thread/start",
                "params": {
                    "cwd": self._workspace_path,
                    "approvalPolicy": "never",
                    "sandbox": "readOnly",
                    "serviceName": "ai_dev_orchestrator_readonly_reviewer",
                },
            },
            writer_handles=writer_handles,
            deadline=deadline,
        )
        thread_response = self._wait_for_response(
            reader=reader,
            request_id=2,
            deadline=deadline,
            failure_code="reviewer_codex_app_server_thread_start_failed",
        )
        thread_id = self._extract_thread_id(thread_response)
        if not thread_id:
            raise _TransportFailure(
                "failed",
                "reviewer_codex_app_server_thread_start_failed",
            )
        thread_ephemeral = self._extract_thread_ephemeral(thread_response)

        failure: _TransportFailure | None = None
        raw_output_text: str | None = None
        try:
            self._send_jsonl_bounded(
                process=process,
                message={
                    "id": 3,
                    "method": "turn/start",
                    "params": {
                        "threadId": thread_id,
                        "input": [
                            {
                                "type": "text",
                                "text": request.review_prompt_text,
                            }
                        ],
                        "cwd": self._workspace_path,
                        "approvalPolicy": "never",
                        "sandboxPolicy": {
                            "type": "readOnly",
                            "access": {"type": "fullAccess"},
                        },
                    },
                },
                writer_handles=writer_handles,
                deadline=deadline,
            )
            turn_response = self._wait_for_response(
                reader=reader,
                request_id=3,
                deadline=deadline,
                failure_code="reviewer_codex_app_server_turn_failed",
            )
            initial_turn_status = self._extract_status(turn_response)
            if initial_turn_status in {"failed", "error"}:
                raise _TransportFailure(
                    "failed",
                    "reviewer_codex_app_server_turn_failed",
                )
            if initial_turn_status == "interrupted":
                raise _TransportFailure(
                    "failed",
                    "reviewer_codex_app_server_turn_interrupted",
                )

            final_status = self._wait_for_turn_completed(
                reader=reader,
                deadline=deadline,
            )
            if final_status in {"failed", "error"}:
                raise _TransportFailure(
                    "failed",
                    "reviewer_codex_app_server_turn_failed",
                )
            if final_status == "interrupted":
                raise _TransportFailure(
                    "failed",
                    "reviewer_codex_app_server_turn_interrupted",
                )

            raw_output_text = reader.final_agent_output()
            if raw_output_text is None:
                raise _TransportFailure(
                    "failed",
                    "reviewer_codex_app_server_output_missing",
                )
        except _TransportFailure as exc:
            failure = exc
        finally:
            cleanup_failure = self._cleanup_thread(
                process=process,
                reader=reader,
                thread_id=thread_id,
                thread_ephemeral=thread_ephemeral,
                writer_handles=writer_handles,
                deadline=deadline,
            )
            if failure is None and cleanup_failure is not None:
                failure = cleanup_failure

        if failure is not None:
            raise failure
        assert raw_output_text is not None
        return raw_output_text

    def _cleanup_thread(
        self,
        *,
        process: Any,
        reader: "_StdoutReaderHandle",
        thread_id: str,
        thread_ephemeral: bool,
        writer_handles: list["_StdinWriterHandle"],
        deadline: float,
    ) -> "_TransportFailure | None":
        if thread_ephemeral:
            return None
        try:
            self._send_jsonl_bounded(
                process=process,
                message={
                    "id": 4,
                    "method": "thread/delete",
                    "params": {"threadId": thread_id},
                },
                writer_handles=writer_handles,
                deadline=deadline,
            )
            cleanup_response = self._wait_for_response(
                reader=reader,
                request_id=4,
                deadline=deadline,
                failure_code="reviewer_codex_app_server_thread_cleanup_failed",
            )
            if not self._thread_cleanup_succeeded(cleanup_response):
                return _TransportFailure(
                    "failed",
                    "reviewer_codex_app_server_thread_cleanup_failed",
                )
        except _TransportFailure:
            return _TransportFailure(
                "failed",
                "reviewer_codex_app_server_thread_cleanup_failed",
            )
        return None

    def _start_stdout_reader(self, *, process: Any) -> "_StdoutReaderHandle":
        stdout_pipe = getattr(process, "stdout", None)
        if stdout_pipe is None:
            raise RuntimeError("codex app-server stdout pipe missing")
        state = _StdoutReaderState()
        thread = threading.Thread(
            target=self._read_stdout_jsonl,
            kwargs={"stdout_pipe": stdout_pipe, "state": state},
            daemon=True,
        )
        thread.start()
        return _StdoutReaderHandle(thread=thread, state=state)

    def _read_stdout_jsonl(
        self,
        *,
        stdout_pipe: Any,
        state: "_StdoutReaderState",
    ) -> None:
        buffer = bytearray()
        try:
            while not state.stop_requested.is_set():
                chunk = self._read_stdout_chunk(stdout_pipe)
                if not chunk:
                    break
                buffer.extend(chunk)
                while True:
                    newline_index = buffer.find(b"\n")
                    if newline_index < 0:
                        break
                    line = bytes(buffer[:newline_index])
                    del buffer[:newline_index + 1]
                    self._handle_protocol_line(line=line, state=state)
                    if state.failed:
                        return
                if len(buffer) > _MAX_PROTOCOL_LINE_BYTES:
                    state.fail("reviewer_codex_app_server_protocol_too_large")
                    break
            if buffer and not state.failed:
                state.fail("reviewer_codex_app_server_protocol_failed")
        except UnicodeDecodeError:
            state.fail("reviewer_stdout_invalid_utf8")
        except json.JSONDecodeError:
            state.fail("reviewer_codex_app_server_protocol_failed")
        except Exception:
            state.fail("reviewer_codex_app_server_protocol_failed")
        finally:
            state.done.set()
            with state.condition:
                state.condition.notify_all()

    @staticmethod
    def _read_stdout_chunk(stdout_pipe: Any) -> bytes:
        fileno = getattr(stdout_pipe, "fileno", None)
        if fileno is not None:
            try:
                return os.read(fileno(), _STDOUT_CHUNK_BYTES)
            except (OSError, TypeError, ValueError):
                pass
        read1 = getattr(stdout_pipe, "read1", None)
        if read1 is not None:
            chunk = read1(_STDOUT_CHUNK_BYTES)
            if isinstance(chunk, str):
                return chunk.encode("utf-8")
            return chunk
        read = getattr(stdout_pipe, "read", None)
        if read is None:
            return b""
        chunk = read(_STDOUT_CHUNK_BYTES)
        if isinstance(chunk, str):
            return chunk.encode("utf-8")
        return chunk

    def _handle_protocol_line(
        self,
        *,
        line: bytes,
        state: "_StdoutReaderState",
    ) -> None:
        if not line:
            return
        if len(line) > _MAX_PROTOCOL_LINE_BYTES:
            state.fail("reviewer_codex_app_server_protocol_too_large")
            return
        message = json.loads(line.decode("utf-8"))
        if not isinstance(message, dict):
            state.fail("reviewer_codex_app_server_protocol_failed")
            return
        with state.condition:
            request_id = message.get("id")
            if request_id is not None:
                state.responses[request_id] = message
            self._capture_agent_message(message=message, state=state)
            if self._is_turn_completed(message):
                state.turn_completed = True
                status = self._extract_status(message)
                state.turn_final_status = status or "completed"
            state.condition.notify_all()

    def _capture_agent_message(
        self,
        *,
        message: dict[str, Any],
        state: "_StdoutReaderState",
    ) -> None:
        item = self._extract_completed_item(message)
        if not item or item.get("type") != "agentMessage":
            return
        text = item.get("text")
        if not isinstance(text, str):
            return
        phase = item.get("phase")
        if phase == "commentary":
            return
        if phase == "final_answer":
            state.final_answer_agent_message = text
            return
        if phase is None:
            state.last_unphased_agent_message = text

    def _wait_for_response(
        self,
        *,
        reader: "_StdoutReaderHandle",
        request_id: int,
        deadline: float,
        failure_code: str,
    ) -> dict[str, Any]:
        response = reader.wait_for_response(
            request_id=request_id,
            deadline=deadline,
            timeout_seconds=self._timeout_seconds,
        )
        self._raise_if_reader_failed(reader)
        if response is None and reader.is_done():
            raise _TransportFailure(
                "failed",
                "reviewer_codex_app_server_protocol_failed",
            )
        if response is None:
            raise _TransportFailure("timeout", "reviewer_native_timeout")
        if "error" in response:
            raise _TransportFailure("failed", failure_code)
        return response

    def _wait_for_turn_completed(
        self,
        *,
        reader: "_StdoutReaderHandle",
        deadline: float,
    ) -> str:
        status = reader.wait_for_turn_completed(
            deadline=deadline,
            timeout_seconds=self._timeout_seconds,
        )
        self._raise_if_reader_failed(reader)
        if status is None and reader.is_done():
            raise _TransportFailure(
                "failed",
                "reviewer_codex_app_server_protocol_failed",
            )
        if status is None:
            raise _TransportFailure("timeout", "reviewer_native_timeout")
        return status

    def _send_jsonl_bounded(
        self,
        *,
        process: Any,
        message: dict[str, Any],
        writer_handles: list["_StdinWriterHandle"],
        deadline: float,
    ) -> None:
        stdin_pipe = getattr(process, "stdin", None)
        if stdin_pipe is None:
            raise _TransportFailure("failed", "reviewer_stdin_write_failed")
        payload = json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
        state = _StdinWriterState()
        done = threading.Event()
        thread = threading.Thread(
            target=self._write_stdin_payload,
            kwargs={
                "stdin_pipe": stdin_pipe,
                "payload": payload,
                "state": state,
                "done": done,
            },
            daemon=True,
        )
        writer = _StdinWriterHandle(thread=thread, done=done, state=state)
        writer_handles.append(writer)
        thread.start()
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not done.wait(timeout=remaining):
            raise _TransportFailure("timeout", "reviewer_native_timeout")
        thread.join(timeout=min(remaining, self._terminate_wait_seconds))
        if state.failed or not state.completed:
            raise _TransportFailure("failed", "reviewer_stdin_write_failed")

    def _write_stdin_payload(
        self,
        *,
        stdin_pipe: Any,
        payload: bytes,
        state: "_StdinWriterState",
        done: threading.Event,
    ) -> None:
        try:
            offset = 0
            while offset < len(payload):
                chunk = payload[offset:offset + _STDIN_CHUNK_BYTES]
                written = stdin_pipe.write(chunk)
                if written is None:
                    offset += len(chunk)
                elif written > 0:
                    offset += written
                else:
                    raise BrokenPipeError("stdin write made no progress")
                flush = getattr(stdin_pipe, "flush", None)
                if flush is not None:
                    flush()
            state.completed = True
        except Exception:
            state.failed = True
        finally:
            done.set()

    def _stop_started_process(
        self,
        *,
        process_handle_id: str,
        process: Any,
        registered: bool,
        reader: "_StdoutReaderHandle | None",
        writer_handles: list["_StdinWriterHandle"],
    ) -> None:
        try:
            self._close_process_stdin(process)
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
                try:
                    process.wait(timeout=self._terminate_wait_seconds)
                except Exception:
                    pass
        finally:
            if reader is not None:
                reader.request_stop()
                reader.thread.join(timeout=self._terminate_wait_seconds)
            self._join_writer_handles_bounded(writer_handles)
            self._cleanup_supervisor(process_handle_id)

    def _join_writer_handles_bounded(
        self,
        writer_handles: list["_StdinWriterHandle"],
    ) -> None:
        for writer in writer_handles:
            writer.thread.join(timeout=self._terminate_wait_seconds)

    def _terminate_process(
        self,
        *,
        process_handle_id: str,
        process: Any,
        registered: bool,
    ) -> None:
        supervisor_terminated = False
        try:
            if registered:
                result = self._process_supervisor.terminate(process_handle_id)
                supervisor_terminated = bool(
                    getattr(result, "action_success", False)
                )
        except Exception:
            pass
        if not supervisor_terminated:
            self._call_process_method(process, "terminate")

    def _kill_process(
        self,
        *,
        process_handle_id: str,
        process: Any,
        registered: bool,
    ) -> None:
        supervisor_killed = False
        try:
            if registered:
                result = self._process_supervisor.kill(process_handle_id)
                supervisor_killed = bool(getattr(result, "action_success", False))
        except Exception:
            pass
        if not supervisor_killed:
            self._call_process_method(process, "kill")

    def _cleanup_supervisor(self, process_handle_id: str) -> None:
        try:
            self._process_supervisor.cleanup(process_handle_id)
        except Exception:
            pass

    def _close_process_stdin(self, process: Any) -> None:
        stdin_pipe = getattr(process, "stdin", None)
        if stdin_pipe is None:
            return
        try:
            if not getattr(stdin_pipe, "closed", False):
                stdin_pipe.close()
        except Exception:
            pass

    def _raise_if_reader_failed(self, reader: "_StdoutReaderHandle") -> None:
        error_code = reader.error_code()
        if error_code is None:
            return
        if error_code == "reviewer_codex_app_server_protocol_too_large":
            raise _TransportFailure("failed", error_code)
        if error_code == "reviewer_stdout_invalid_utf8":
            raise _TransportFailure("failed", error_code)
        raise _TransportFailure("failed", "reviewer_codex_app_server_protocol_failed")

    @staticmethod
    def _extract_thread_id(message: dict[str, Any]) -> str | None:
        result = message.get("result")
        if not isinstance(result, dict):
            return None
        thread = result.get("thread")
        if isinstance(thread, dict) and isinstance(thread.get("id"), str):
            return thread["id"]
        thread_id = result.get("threadId")
        if isinstance(thread_id, str):
            return thread_id
        return None

    @staticmethod
    def _extract_thread_ephemeral(message: dict[str, Any]) -> bool:
        result = message.get("result")
        if not isinstance(result, dict):
            return False
        thread = result.get("thread")
        if isinstance(thread, dict):
            return thread.get("ephemeral") is True
        return result.get("ephemeral") is True

    @staticmethod
    def _extract_status(message: dict[str, Any]) -> str | None:
        for container in (message, message.get("result"), message.get("params")):
            if isinstance(container, dict) and isinstance(container.get("status"), str):
                return container["status"]
            if isinstance(container, dict):
                turn = container.get("turn")
                if isinstance(turn, dict) and isinstance(turn.get("status"), str):
                    return turn["status"]
        return None

    @staticmethod
    def _thread_cleanup_succeeded(message: dict[str, Any]) -> bool:
        result = message.get("result")
        if result is True:
            return True
        if isinstance(result, dict):
            success = result.get("success")
            if success is None:
                return "error" not in result
            return success is True
        return result is not False and result is not None

    @staticmethod
    def _extract_completed_item(message: dict[str, Any]) -> dict[str, Any] | None:
        event_name = (
            message.get("method")
            or message.get("type")
            or message.get("event")
            or message.get("name")
        )
        if event_name != "item/completed":
            return None
        params = message.get("params")
        candidates: list[Any] = []
        if isinstance(params, dict):
            candidates.extend([params.get("item"), params.get("completedItem")])
        candidates.extend([message.get("item"), message.get("completedItem")])
        for candidate in candidates:
            if isinstance(candidate, dict):
                return candidate
        return None

    @staticmethod
    def _is_turn_completed(message: dict[str, Any]) -> bool:
        event_name = (
            message.get("method")
            or message.get("type")
            or message.get("event")
            or message.get("name")
        )
        return event_name == "turn/completed"

    @staticmethod
    def _call_process_method(process: Any, method_name: str) -> None:
        method = getattr(process, method_name, None)
        if method is not None:
            method()

    @staticmethod
    def _raw_result(
        *,
        request: ReadonlyReviewerTransportRequest,
        transport_status: str,
        transport_error_code: str | None,
        started: bool,
        executed: bool,
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
            codex_started=started,
            claude_code_started=False,
        )


__all__ = ("CodexAppServerReadonlyReviewerTransport",)


class _TransportFailure(RuntimeError):
    def __init__(self, transport_status: str, transport_error_code: str) -> None:
        super().__init__(transport_error_code)
        self.transport_status = transport_status
        self.transport_error_code = transport_error_code


class _StdinWriterState:
    def __init__(self) -> None:
        self.completed = False
        self.failed = False


class _StdinWriterHandle:
    def __init__(
        self,
        *,
        thread: threading.Thread,
        done: threading.Event,
        state: _StdinWriterState,
    ) -> None:
        self.thread = thread
        self.done = done
        self._state = state

    @property
    def completed(self) -> bool:
        return self._state.completed

    @property
    def failed(self) -> bool:
        return self._state.failed


class _StdoutReaderState:
    def __init__(self) -> None:
        self.condition = threading.Condition()
        self.done = threading.Event()
        self.stop_requested = threading.Event()
        self.responses: dict[Any, dict[str, Any]] = {}
        self.turn_completed = False
        self.turn_final_status: str | None = None
        self.final_answer_agent_message: str | None = None
        self.last_unphased_agent_message: str | None = None
        self.failed = False
        self.error_code: str | None = None

    def fail(self, error_code: str) -> None:
        with self.condition:
            self.failed = True
            self.error_code = error_code
            self.condition.notify_all()


class _StdoutReaderHandle:
    def __init__(
        self,
        *,
        thread: threading.Thread,
        state: _StdoutReaderState,
    ) -> None:
        self.thread = thread
        self._state = state

    def wait_for_response(
        self,
        *,
        request_id: int,
        deadline: float,
        timeout_seconds: float,
    ) -> dict[str, Any] | None:
        with self._state.condition:
            while (
                request_id not in self._state.responses
                and not self._state.failed
                and not self._state.done.is_set()
            ):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._state.condition.wait(timeout=min(remaining, 0.05))
            return self._state.responses.pop(request_id, None)

    def wait_for_turn_completed(
        self,
        *,
        deadline: float,
        timeout_seconds: float,
    ) -> str | None:
        with self._state.condition:
            while (
                not self._state.turn_completed
                and not self._state.failed
                and not self._state.done.is_set()
            ):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._state.condition.wait(timeout=min(remaining, 0.05))
            return self._state.turn_final_status

    def final_agent_output(self) -> str | None:
        if self._state.final_answer_agent_message is not None:
            return self._state.final_answer_agent_message
        return self._state.last_unphased_agent_message

    def error_code(self) -> str | None:
        return self._state.error_code

    def is_done(self) -> bool:
        return self._state.done.is_set()

    def request_stop(self) -> None:
        self._state.stop_requested.set()
