"""Bounded JSONL transport seam for the future TypeScript Director Runtime."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from typing import Any, Protocol


class DirectorRuntimeTransportError(RuntimeError):
    """Raised when the bounded runtime transport cannot return one JSON result."""


class DirectorRuntimeTransport(Protocol):
    async def invoke(self, *, request_id: str, request: dict[str, Any]) -> dict[str, Any]:
        """Send one serialized request and return one complete JSON object."""

    async def cancel(self, *, request_id: str) -> None:
        """Request bounded cancellation for the active request, if present."""


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
        self._processes: dict[str, asyncio.subprocess.Process] = {}

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

        self._processes[request_id] = process
        try:
            stdout, _stderr = await process.communicate(
                json.dumps(request, separators=(",", ":")).encode("utf-8") + b"\n"
            )
        except Exception as exc:  # noqa: BLE001 - transport details are never surfaced
            raise DirectorRuntimeTransportError("director_runtime_transport_disconnected") from exc
        finally:
            self._processes.pop(request_id, None)

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
        process = self._processes.get(request_id)
        if process is None or process.returncode is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=self._cancel_wait_seconds)
        except TimeoutError:
            process.kill()
            try:
                await asyncio.wait_for(process.wait(), timeout=self._cancel_wait_seconds)
            except TimeoutError as exc:
                raise DirectorRuntimeTransportError(
                    "director_runtime_transport_cancel_failed"
                ) from exc


__all__ = (
    "DirectorRuntimeTransport",
    "DirectorRuntimeTransportError",
    "StdioJsonlDirectorRuntimeTransport",
)
