"""Bounded JSONL transport seam for the future TypeScript Director Runtime."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol


class DirectorRuntimeTransportError(RuntimeError):
    """Raised when the bounded runtime transport cannot return one JSON result."""


class DirectorRuntimeTransport(Protocol):
    async def invoke(self, *, request_id: str, request: dict[str, Any]) -> dict[str, Any]:
        """Send one serialized request and return one complete JSON object."""

    async def cancel(self, *, request_id: str) -> None:
        """Request bounded cancellation for the active request, if present."""


@dataclass(slots=True)
class _RuntimeProcessHandle:
    process: asyncio.subprocess.Process
    communicate_task: asyncio.Task[tuple[bytes, bytes]]
    cleanup_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    reaped: bool = False


class StdioJsonlDirectorRuntimeTransport:
    """Run one trusted, configured command without shell interpolation.

    The command is constructed by application configuration, never by a protocol
    request. Output must be a single complete JSON line; logs and partial output
    are rejected rather than interpreted as a candidate.
    """

    def __init__(self, *, command: Sequence[str], cancel_wait_seconds: float = 1.0) -> None:
        if not command or any(not isinstance(part, str) or not part.strip() for part in command):
            raise ValueError("director_runtime_transport_command_invalid")
        if cancel_wait_seconds <= 0:
            raise ValueError("director_runtime_transport_cancel_wait_invalid")
        self._command = tuple(command)
        self._cancel_wait_seconds = cancel_wait_seconds
        self._processes: dict[str, _RuntimeProcessHandle] = {}

    @property
    def active_process_ids(self) -> frozenset[int]:
        """Return only live transport-owned child IDs for bounded diagnostics."""

        return frozenset(
            handle.process.pid
            for handle in self._processes.values()
            if handle.process.pid is not None and not handle.reaped
        )

    async def invoke(self, *, request_id: str, request: dict[str, Any]) -> dict[str, Any]:
        if request_id in self._processes:
            raise DirectorRuntimeTransportError("director_runtime_transport_duplicate_request")
        try:
            process = await asyncio.create_subprocess_exec(
                *self._command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise DirectorRuntimeTransportError("director_runtime_transport_start_failed") from exc

        communicate_task = asyncio.create_task(
            process.communicate(
                json.dumps(request, separators=(",", ":")).encode("utf-8") + b"\n"
            )
        )
        communicate_task.add_done_callback(_consume_task_exception)
        handle = _RuntimeProcessHandle(
            process=process,
            communicate_task=communicate_task,
        )
        self._processes[request_id] = handle
        try:
            stdout, _stderr = await asyncio.shield(communicate_task)
        except asyncio.CancelledError:
            await asyncio.shield(self._terminate_and_reap(request_id, handle))
            raise
        except Exception as exc:  # noqa: BLE001 - transport details are never surfaced
            raise DirectorRuntimeTransportError("director_runtime_transport_disconnected") from exc
        finally:
            self._remove_reaped_handle(request_id, handle)

        if process.returncode != 0:
            raise DirectorRuntimeTransportError("director_runtime_transport_failed")
        lines = [line for line in stdout.decode("utf-8", errors="replace").splitlines() if line]
        if len(lines) != 1:
            raise DirectorRuntimeTransportError("director_runtime_transport_result_missing")
        try:
            payload = json.loads(lines[0])
        except json.JSONDecodeError as exc:
            raise DirectorRuntimeTransportError("director_runtime_transport_result_invalid") from exc
        if not isinstance(payload, dict):
            raise DirectorRuntimeTransportError("director_runtime_transport_result_invalid")
        return payload

    async def cancel(self, *, request_id: str) -> None:
        handle = self._processes.get(request_id)
        if handle is None:
            return
        await self._terminate_and_reap(request_id, handle)

    async def _terminate_and_reap(
        self,
        request_id: str,
        handle: _RuntimeProcessHandle,
    ) -> None:
        """Terminate one child, then wait for its communicate task to reap it."""

        async with handle.cleanup_lock:
            if handle.reaped:
                self._remove_reaped_handle(request_id, handle)
                return
            process = handle.process
            if process.returncode is None:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass
            try:
                await asyncio.wait_for(
                    asyncio.shield(handle.communicate_task),
                    timeout=self._cancel_wait_seconds,
                )
            except TimeoutError:
                if process.returncode is None:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                try:
                    await asyncio.wait_for(
                        asyncio.shield(handle.communicate_task),
                        timeout=self._cancel_wait_seconds,
                    )
                except TimeoutError as exc:
                    raise DirectorRuntimeTransportError(
                        "director_runtime_transport_cancel_failed"
                    ) from exc
            except Exception as exc:  # noqa: BLE001 - no child error payload is exposed
                raise DirectorRuntimeTransportError(
                    "director_runtime_transport_disconnected"
                ) from exc
            if process.returncode is None:
                raise DirectorRuntimeTransportError(
                    "director_runtime_transport_cancel_failed"
                )
            handle.reaped = True
            self._remove_reaped_handle(request_id, handle)

    def _remove_reaped_handle(
        self,
        request_id: str,
        handle: _RuntimeProcessHandle,
    ) -> None:
        if handle.reaped or (
            handle.process.returncode is not None and handle.communicate_task.done()
        ):
            handle.reaped = True
            if self._processes.get(request_id) is handle:
                self._processes.pop(request_id, None)


def _consume_task_exception(task: asyncio.Task[tuple[bytes, bytes]]) -> None:
    """Consume an abandoned communication task error without exposing internals."""

    try:
        task.exception()
    except BaseException:
        pass


__all__ = (
    "DirectorRuntimeTransport",
    "DirectorRuntimeTransportError",
    "StdioJsonlDirectorRuntimeTransport",
)
