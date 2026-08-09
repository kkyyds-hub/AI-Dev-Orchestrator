"""Fail-closed in-process supervision for untrusted Director Runtime candidates."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum

from app.domain.director_runtime_protocol import (
    DirectorRuntimeFailure,
    DirectorRuntimeProtocolError,
    DirectorRuntimeRequest,
    DirectorTurnResult,
    normalize_runtime_failure,
    parse_director_turn_result,
    serialize_director_runtime_request,
)
from app.services.director_runtime_transport import (
    DirectorRuntimeTransport,
    DirectorRuntimeTransportError,
)


class DirectorRuntimeLifecycleState(StrEnum):
    STARTING = "starting"
    READY = "ready"
    BUSY = "busy"
    STOPPING = "stopping"
    STOPPED = "stopped"
    DEGRADED = "degraded"
    FAILED = "failed"


class DirectorRuntimeAttemptState(StrEnum):
    ACTIVE = "active"
    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(slots=True)
class _DirectorRuntimeAttempt:
    request_id: str
    state: DirectorRuntimeAttemptState = DirectorRuntimeAttemptState.ACTIVE
    cancellation_accepted: bool = False


@dataclass(frozen=True, slots=True)
class DirectorRuntimeSupervisionOutcome:
    """Either one validated candidate or a normalized terminal failure, never both."""

    request_id: str
    attempt_state: DirectorRuntimeAttemptState
    candidate: DirectorTurnResult | None
    error: DirectorRuntimeFailure | None

    def __post_init__(self) -> None:
        if (self.candidate is None) == (self.error is None):
            raise ValueError("director_runtime_outcome_must_be_candidate_or_failure")


class DirectorRuntimeSupervisor:
    """Own one in-memory runtime instance and reject unsafe result admission.

    This service has no repository dependency and never admits, persists, or
    executes a returned candidate. A failed instance remains failed; callers
    must construct a new supervisor to start another instance.
    """

    def __init__(self, *, transport: DirectorRuntimeTransport) -> None:
        self._transport = transport
        self._state = DirectorRuntimeLifecycleState.STARTING
        self._active: dict[str, _DirectorRuntimeAttempt] = {}
        self._attempts: dict[str, _DirectorRuntimeAttempt] = {}

    @property
    def state(self) -> DirectorRuntimeLifecycleState:
        return self._state

    def start(self) -> None:
        """Mark a newly created or intentionally stopped instance ready."""

        if self._state == DirectorRuntimeLifecycleState.FAILED:
            raise RuntimeError("director_runtime_failed_instance_cannot_restart")
        if self._active:
            raise RuntimeError("director_runtime_active_attempt_prevents_start")
        if self._state not in {
            DirectorRuntimeLifecycleState.STARTING,
            DirectorRuntimeLifecycleState.STOPPED,
            DirectorRuntimeLifecycleState.DEGRADED,
        }:
            raise RuntimeError("director_runtime_start_transition_invalid")
        self._state = DirectorRuntimeLifecycleState.READY

    def mark_degraded(self) -> None:
        if self._state not in {
            DirectorRuntimeLifecycleState.STARTING,
            DirectorRuntimeLifecycleState.READY,
            DirectorRuntimeLifecycleState.BUSY,
        }:
            raise RuntimeError("director_runtime_degraded_transition_invalid")
        self._state = DirectorRuntimeLifecycleState.DEGRADED

    async def submit(
        self,
        *,
        request: DirectorRuntimeRequest,
    ) -> DirectorRuntimeSupervisionOutcome:
        """Return one all-or-nothing untrusted candidate or a safe failure."""

        try:
            request_payload = serialize_director_runtime_request(request)
        except DirectorRuntimeProtocolError:
            return self._failure(
                request_id=_request_id_or_unknown(request),
                attempt_state=DirectorRuntimeAttemptState.REJECTED,
                code="director_runtime_request_invalid",
                stage="request",
                retryable=False,
                safe_message="The Director Runtime request was rejected before dispatch.",
            )

        if request.request_id in self._attempts:
            return self._failure(
                request_id=request.request_id,
                attempt_state=DirectorRuntimeAttemptState.REJECTED,
                code="director_runtime_duplicate_request_id",
                stage="runtime",
                retryable=False,
                safe_message="The Director Runtime request is already active or terminal.",
            )
        if self._state != DirectorRuntimeLifecycleState.READY:
            return self._failure(
                request_id=request.request_id,
                attempt_state=DirectorRuntimeAttemptState.REJECTED,
                code="director_runtime_not_ready",
                stage="runtime",
                retryable=True,
                safe_message="The Director Runtime is not ready to accept a request.",
            )

        attempt = _DirectorRuntimeAttempt(request_id=request.request_id)
        self._attempts[request.request_id] = attempt
        self._active[request.request_id] = attempt
        self._state = DirectorRuntimeLifecycleState.BUSY

        try:
            raw_result = await asyncio.wait_for(
                self._transport.invoke(
                    request_id=request.request_id,
                    request=request_payload,
                ),
                timeout=request.runtime_config.timeout_ms / 1000,
            )
        except TimeoutError:
            await self._cancel_after_timeout(request.request_id)
            return self._finish_failure(
                attempt=attempt,
                state=DirectorRuntimeAttemptState.TIMED_OUT,
                lifecycle_state=DirectorRuntimeLifecycleState.DEGRADED,
                code="director_runtime_timeout",
                stage="runtime",
                retryable=True,
                safe_message="The Director Runtime attempt timed out and no candidate was admitted.",
            )
        except (DirectorRuntimeTransportError, OSError, asyncio.CancelledError):
            return self._finish_failure(
                attempt=attempt,
                state=DirectorRuntimeAttemptState.FAILED,
                lifecycle_state=DirectorRuntimeLifecycleState.FAILED,
                code="director_runtime_transport_failed",
                stage="runtime",
                retryable=False,
                safe_message="The Director Runtime transport failed and no candidate was admitted.",
            )
        except Exception:  # noqa: BLE001 - raw runtime failures never cross this boundary
            return self._finish_failure(
                attempt=attempt,
                state=DirectorRuntimeAttemptState.FAILED,
                lifecycle_state=DirectorRuntimeLifecycleState.FAILED,
                code="director_runtime_failed",
                stage="runtime",
                retryable=False,
                safe_message="The Director Runtime failed and no candidate was admitted.",
            )

        if attempt.cancellation_accepted:
            return self._finish_failure(
                attempt=attempt,
                state=DirectorRuntimeAttemptState.CANCELLED,
                lifecycle_state=DirectorRuntimeLifecycleState.STOPPED,
                code="director_runtime_cancelled",
                stage="runtime",
                retryable=False,
                safe_message="The Director Runtime request was cancelled and late output was rejected.",
            )
        try:
            candidate = parse_director_turn_result(
                raw_result,
                expected_request_id=request.request_id,
                authorized_tools=request.available_tools,
            )
        except DirectorRuntimeProtocolError:
            return self._finish_failure(
                attempt=attempt,
                state=DirectorRuntimeAttemptState.REJECTED,
                lifecycle_state=DirectorRuntimeLifecycleState.DEGRADED,
                code="director_runtime_result_invalid",
                stage="result_validation",
                retryable=False,
                safe_message="The Director Runtime result was rejected without admitting a candidate.",
            )
        return self._finish_candidate(attempt=attempt, candidate=candidate)

    async def cancel(self, *, request_id: str) -> bool:
        """Accept cancellation and make any eventual output inadmissible."""

        attempt = self._active.get(request_id)
        if attempt is None or attempt.state != DirectorRuntimeAttemptState.ACTIVE:
            return False
        attempt.cancellation_accepted = True
        self._state = DirectorRuntimeLifecycleState.STOPPING
        try:
            await self._transport.cancel(request_id=request_id)
        except Exception:  # noqa: BLE001 - cancellation remains fail-closed
            self._state = DirectorRuntimeLifecycleState.FAILED
        return True

    async def _cancel_after_timeout(self, request_id: str) -> None:
        try:
            await self._transport.cancel(request_id=request_id)
        except Exception:
            pass

    def _finish_candidate(
        self,
        *,
        attempt: _DirectorRuntimeAttempt,
        candidate: DirectorTurnResult,
    ) -> DirectorRuntimeSupervisionOutcome:
        attempt.state = DirectorRuntimeAttemptState.SUCCEEDED
        self._active.pop(attempt.request_id, None)
        self._state = DirectorRuntimeLifecycleState.READY
        return DirectorRuntimeSupervisionOutcome(
            request_id=attempt.request_id,
            attempt_state=attempt.state,
            candidate=candidate,
            error=None,
        )

    def _finish_failure(
        self,
        *,
        attempt: _DirectorRuntimeAttempt,
        state: DirectorRuntimeAttemptState,
        lifecycle_state: DirectorRuntimeLifecycleState,
        code: str,
        stage: str,
        retryable: bool,
        safe_message: str,
    ) -> DirectorRuntimeSupervisionOutcome:
        attempt.state = state
        self._active.pop(attempt.request_id, None)
        self._state = lifecycle_state
        return self._failure(
            request_id=attempt.request_id,
            attempt_state=state,
            code=code,
            stage=stage,
            retryable=retryable,
            safe_message=safe_message,
        )

    @staticmethod
    def _failure(
        *,
        request_id: str,
        attempt_state: DirectorRuntimeAttemptState,
        code: str,
        stage: str,
        retryable: bool,
        safe_message: str,
    ) -> DirectorRuntimeSupervisionOutcome:
        return DirectorRuntimeSupervisionOutcome(
            request_id=request_id,
            attempt_state=attempt_state,
            candidate=None,
            error=normalize_runtime_failure(
                code=code,
                stage=stage,  # type: ignore[arg-type]
                retryable=retryable,
                safe_message=safe_message,
            ),
        )


def _request_id_or_unknown(request: DirectorRuntimeRequest) -> str:
    return request.request_id if isinstance(request.request_id, str) else "unknown"


__all__ = (
    "DirectorRuntimeAttemptState",
    "DirectorRuntimeLifecycleState",
    "DirectorRuntimeSupervisionOutcome",
    "DirectorRuntimeSupervisor",
)
