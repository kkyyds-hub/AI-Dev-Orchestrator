from __future__ import annotations

import asyncio
from copy import deepcopy
from pathlib import Path
import sys
import time
from typing import Any

import pytest

from app.domain.director_runtime_protocol import (
    DIRECTOR_RUNTIME_SCHEMA_VERSION,
    DirectorRuntimeProtocolError,
    parse_director_turn_result,
    serialize_director_runtime_request,
    validate_director_runtime_request,
)
from app.services.director_runtime_supervisor_service import (
    DirectorRuntimeAttemptState,
    DirectorRuntimeLifecycleState,
    DirectorRuntimeSupervisor,
)
from app.services.director_runtime_transport import (
    DirectorRuntimeTransportError,
    StdioJsonlDirectorRuntimeTransport,
)


VALID_TIMESTAMPS = (
    "2026-08-10T01:00:00+08:00",
    "2026-08-09T17:00:00Z",
    "2026-08-09T17:00:00.1Z",
    "2026-08-09T17:00:00.123Z",
    "2026-08-09T17:00:00.123456+08:00",
    "2026-08-09T12:00:00-05:00",
)
INVALID_TIMESTAMPS = (
    "2026-08-10T01:00:00",
    "2026/08/10 01:00:00 +08:00",
    "August 10, 2026 01:00:00 +08:00",
    "2026-08-10 01:00:00+08:00",
    "2026-08-10T01:00:00+0800",
    "2026-08-10T01:00:00z",
    "2026-02-30T01:00:00+08:00",
    "2026-13-01T01:00:00+08:00",
    "2026-08-10T24:01:00+08:00",
    "2026-08-10T01:60:00+08:00",
    "2026-08-10T01:00:60+08:00",
    "not-a-date",
)


def _request_payload(
    *,
    request_id: str = "request-1",
    occurred_at: str = VALID_TIMESTAMPS[0],
) -> dict[str, Any]:
    return {
        "schema_version": DIRECTOR_RUNTIME_SCHEMA_VERSION,
        "request_id": request_id,
        "project_id": "project-1",
        "session_id": "session-1",
        "message_id": "message-1",
        "current_user_message": {
            "content": "hello",
            "occurred_at": occurred_at,
            "actor_claim": "user",
        },
        "authoritative_facts": {},
        "active_discussion_workspace": None,
        "relevant_discussion_events": [],
        "active_formalization": {"proposal": None, "plan_version": None},
        "governance_boundaries": {
            "authoritative_write": False,
            "director_may_modify_code": False,
            "formalization_requires_explicit_request": True,
            "confirmation_is_separate": True,
            "execution_boundary": "no_task_run_agent_session_before_execution",
        },
        "available_skills": [],
        "available_tools": [],
        "permission_context": {},
        "runtime_config": {
            "model_id": "model-1",
            "provider_profile_id": "profile-1",
            "timeout_ms": 1000.0,
            "max_tool_rounds": 0,
        },
    }


def _result_payload(*, request_id: str = "request-1") -> dict[str, Any]:
    return {
        "schema_version": DIRECTOR_RUNTIME_SCHEMA_VERSION,
        "request_id": request_id,
        "response_text": "safe response",
        "turn_semantics": {
            "conversation_mode": "general_discussion",
            "formal_action_requested": False,
            "hypothetical_action": False,
            "confidence": 0.8,
        },
        "discussion_lifecycle": {
            "observed_status": None,
            "suggested_next_status": None,
        },
        "discussion_delta_candidate": None,
        "formalization": {"proposal_candidate": None, "readiness": "not_ready"},
        "tool_activity": [],
        "source_references": [],
        "runtime_metadata": {
            "runtime_state": "ready",
            "model_id": "model-1",
            "provider_profile_id": "profile-1",
            "usage": {},
            "duration_ms": 1.0,
            "attempt": 0,
        },
        "error": None,
    }


def _request(**kwargs: Any):
    payload = _request_payload(**kwargs)
    return validate_director_runtime_request(payload)


class _StaticTransport:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        self.invoke_count = 0
        self.cancel_count = 0

    async def invoke(self, *, request_id: str, request: dict[str, Any]) -> dict[str, Any]:
        self.invoke_count += 1
        return self.result

    async def cancel(self, *, request_id: str) -> None:
        self.cancel_count += 1


class _BlockingTransport:
    def __init__(self, result: dict[str, Any] | None = None, *, cancel_raises: bool = False) -> None:
        self.result = result or _result_payload()
        self.cancel_raises = cancel_raises
        self.invoke_count = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def invoke(self, *, request_id: str, request: dict[str, Any]) -> dict[str, Any]:
        self.invoke_count += 1
        self.started.set()
        await self.release.wait()
        return self.result

    async def cancel(self, *, request_id: str) -> None:
        if self.cancel_raises:
            raise DirectorRuntimeTransportError("cancel cleanup failed")
        self.release.set()


class _DisconnectingTransport:
    async def invoke(self, *, request_id: str, request: dict[str, Any]) -> dict[str, Any]:
        raise DirectorRuntimeTransportError("raw stderr api_key=must-not-leak")

    async def cancel(self, *, request_id: str) -> None:
        return None


@pytest.mark.parametrize("occurred_at", VALID_TIMESTAMPS)
def test_request_accepts_canonical_timezone_timestamps(occurred_at: str) -> None:
    assert _request(occurred_at=occurred_at).current_user_message.occurred_at == occurred_at


@pytest.mark.parametrize("occurred_at", INVALID_TIMESTAMPS)
def test_request_rejects_noncanonical_timestamps(occurred_at: str) -> None:
    with pytest.raises(DirectorRuntimeProtocolError):
        _request(occurred_at=occurred_at)


@pytest.mark.parametrize(
    ("mutate", "label"),
    [
        (lambda value: value.update(schema_version="p26-big-director-runtime/v2"), "schema"),
        (lambda value: value.update(request_id=""), "blank request identity"),
        (lambda value: value["current_user_message"].update(extra=True), "nested key"),
        (lambda value: value.update(unexpected=True), "top level key"),
        (lambda value: value["governance_boundaries"].update(authoritative_write=True), "write"),
        (lambda value: value["governance_boundaries"].update(director_may_modify_code=True), "code"),
        (lambda value: value["governance_boundaries"].update(formalization_requires_explicit_request=False), "formalization"),
        (lambda value: value["governance_boundaries"].update(confirmation_is_separate=False), "confirmation"),
    ],
)
def test_request_rejects_closed_envelope_and_governance_bypass(mutate, label: str) -> None:
    payload = _request_payload()
    mutate(payload)
    with pytest.raises(DirectorRuntimeProtocolError):
        validate_director_runtime_request(payload)


@pytest.mark.parametrize(
    "tools",
    [
        [{"tool_id": "tool", "allowed": True, "authorization_id": None, "idempotency_key": "key"}],
        [{"tool_id": "tool", "allowed": True, "authorization_id": "auth", "idempotency_key": None}],
        [{"tool_id": "tool", "allowed": False, "authorization_id": "auth", "idempotency_key": None}],
        [
            {"tool_id": "tool", "allowed": False, "authorization_id": None, "idempotency_key": None},
            {"tool_id": "tool", "allowed": False, "authorization_id": None, "idempotency_key": None},
        ],
    ],
)
def test_request_rejects_invalid_tool_authorization(tools: list[dict[str, Any]]) -> None:
    payload = _request_payload()
    payload["available_tools"] = tools
    with pytest.raises(DirectorRuntimeProtocolError):
        validate_director_runtime_request(payload)


def test_request_accepts_open_bounded_snapshots_and_rejects_nested_sensitive_keys() -> None:
    payload = _request_payload()
    safe = {"custom_domain_fact": {"nested": [1, True, "value"]}}
    payload["authoritative_facts"] = safe
    payload["active_discussion_workspace"] = safe
    payload["relevant_discussion_events"] = [safe]
    payload["active_formalization"] = {"proposal": safe, "plan_version": safe}
    payload["permission_context"] = safe
    assert _request().schema_version == DIRECTOR_RUNTIME_SCHEMA_VERSION
    assert validate_director_runtime_request(payload).authoritative_facts == safe

    for field in ("authoritative_facts", "active_discussion_workspace", "permission_context"):
        sensitive = _request_payload()
        sensitive[field] = {"nested": {"api_key": "must-not-cross"}}
        with pytest.raises(DirectorRuntimeProtocolError):
            validate_director_runtime_request(sensitive)


@pytest.mark.parametrize("key", ("api_key", "secret", "credential", "password", "authorization", "token", "access_token"))
def test_result_rejects_sensitive_candidate_key(key: str) -> None:
    result = _result_payload()
    result["discussion_delta_candidate"] = {"nested": {key: "sensitive"}}
    with pytest.raises(DirectorRuntimeProtocolError):
        parse_director_turn_result(result, expected_request_id="request-1")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(schema_version="v2"),
        lambda value: value.update(request_id="other"),
        lambda value: value.pop("response_text"),
        lambda value: value.update(unexpected=True),
        lambda value: value["formalization"].update(readiness="invalid"),
        lambda value: value["turn_semantics"].update(unexpected=True),
    ],
)
def test_result_rejects_malformed_or_uncorrelated_whole_envelope(mutate) -> None:
    result = _result_payload()
    mutate(result)
    with pytest.raises(DirectorRuntimeProtocolError):
        parse_director_turn_result(result, expected_request_id="request-1")


@pytest.mark.parametrize("candidate_key", ("discussion_delta_candidate", "proposal_candidate"))
def test_result_error_cannot_salvage_any_candidate(candidate_key: str) -> None:
    result = _result_payload()
    result["error"] = {"code": "failure", "stage": "runtime", "retryable": False, "safe_message": "safe"}
    if candidate_key == "discussion_delta_candidate":
        result[candidate_key] = {"candidate": "must reject"}
    else:
        result["formalization"][candidate_key] = {"candidate": "must reject"}
    with pytest.raises(DirectorRuntimeProtocolError):
        parse_director_turn_result(result, expected_request_id="request-1")


@pytest.mark.parametrize(
    "activity",
    [
        {"tool_id": "unknown", "authorization_id": "auth", "idempotency_key": "key"},
        {"tool_id": "tool", "authorization_id": "auth", "idempotency_key": "key"},
        {"tool_id": "tool", "authorization_id": "wrong", "idempotency_key": "key"},
        {"tool_id": "tool", "authorization_id": "auth", "idempotency_key": "wrong"},
    ],
)
def test_result_rejects_unauthorized_tool_activity(activity: dict[str, str]) -> None:
    result = _result_payload()
    result["tool_activity"] = [{**activity, "status": "succeeded", "safe_summary": None}]
    tools = [
        {"tool_id": "tool", "allowed": True, "authorization_id": "auth", "idempotency_key": "key"},
    ]
    if activity["tool_id"] == "tool" and activity["authorization_id"] == "auth" and activity["idempotency_key"] == "key":
        tools[0] = {
            "tool_id": "tool",
            "allowed": False,
            "authorization_id": None,
            "idempotency_key": None,
        }
    request = validate_director_runtime_request({**_request_payload(), "available_tools": tools})
    with pytest.raises(DirectorRuntimeProtocolError):
        parse_director_turn_result(result, expected_request_id="request-1", authorized_tools=request.available_tools)


def test_supervisor_admits_one_valid_result_then_rejects_terminal_replay() -> None:
    async def scenario() -> None:
        transport = _StaticTransport(_result_payload())
        supervisor = DirectorRuntimeSupervisor(transport=transport)
        supervisor.start()
        outcome = await supervisor.submit(request=_request())
        assert outcome.attempt_state == DirectorRuntimeAttemptState.SUCCEEDED
        assert outcome.candidate is not None
        assert outcome.error is None
        assert supervisor.state == DirectorRuntimeLifecycleState.READY

        replay = await supervisor.submit(request=_request())
        assert replay.attempt_state == DirectorRuntimeAttemptState.REJECTED
        assert replay.candidate is None
        assert transport.invoke_count == 1

    asyncio.run(scenario())


def test_supervisor_rejects_invalid_request_without_transport_or_candidate() -> None:
    async def scenario() -> None:
        transport = _StaticTransport(_result_payload())
        supervisor = DirectorRuntimeSupervisor(transport=transport)
        supervisor.start()
        request = _request()
        invalid = request.model_copy(
            update={
                "current_user_message": request.current_user_message.model_copy(
                    update={"occurred_at": "not-a-date"}
                )
            }
        )
        outcome = await supervisor.submit(request=invalid)
        assert outcome.attempt_state == DirectorRuntimeAttemptState.REJECTED
        assert outcome.candidate is None
        assert transport.invoke_count == 0
        assert supervisor.state == DirectorRuntimeLifecycleState.READY

    asyncio.run(scenario())


def test_supervisor_rejects_active_duplicate_and_late_result_after_cancel() -> None:
    async def scenario() -> None:
        transport = _BlockingTransport()
        supervisor = DirectorRuntimeSupervisor(transport=transport)
        supervisor.start()
        first = asyncio.create_task(supervisor.submit(request=_request()))
        await transport.started.wait()
        duplicate = await supervisor.submit(request=_request())
        assert duplicate.attempt_state == DirectorRuntimeAttemptState.REJECTED
        assert duplicate.candidate is None
        assert transport.invoke_count == 1

        assert await supervisor.cancel(request_id="request-1") is True
        outcome = await first
        assert outcome.attempt_state == DirectorRuntimeAttemptState.CANCELLED
        assert outcome.candidate is None
        assert supervisor.state == DirectorRuntimeLifecycleState.STOPPED

    asyncio.run(scenario())


def test_supervisor_cancel_cleanup_failure_is_terminal_and_cannot_restart() -> None:
    async def scenario() -> None:
        transport = _BlockingTransport(cancel_raises=True)
        supervisor = DirectorRuntimeSupervisor(transport=transport)
        supervisor.start()
        task = asyncio.create_task(supervisor.submit(request=_request()))
        await transport.started.wait()
        assert await supervisor.cancel(request_id="request-1") is True
        transport.release.set()
        outcome = await task
        assert outcome.attempt_state == DirectorRuntimeAttemptState.FAILED
        assert outcome.candidate is None
        assert supervisor.state == DirectorRuntimeLifecycleState.FAILED
        with pytest.raises(RuntimeError, match="cannot_restart"):
            supervisor.start()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "result",
    [
        _result_payload(request_id="other-request"),
        {**_result_payload(), "tool_activity": [{"tool_id": "unknown", "authorization_id": "auth", "idempotency_key": "key", "status": "succeeded", "safe_summary": None}]},
        {**_result_payload(), "error": {"code": "failure", "stage": "runtime", "retryable": False, "safe_message": "safe"}, "discussion_delta_candidate": {"must": "not salvage"}},
    ],
)
def test_supervisor_rejects_invalid_result_without_partial_candidate(result: dict[str, Any]) -> None:
    async def scenario() -> None:
        transport = _StaticTransport(result)
        supervisor = DirectorRuntimeSupervisor(transport=transport)
        supervisor.start()
        outcome = await supervisor.submit(request=_request())
        assert outcome.attempt_state == DirectorRuntimeAttemptState.REJECTED
        assert outcome.candidate is None
        assert supervisor.state == DirectorRuntimeLifecycleState.DEGRADED

    asyncio.run(scenario())


def test_supervisor_timeout_cleanup_failure_keeps_candidate_empty() -> None:
    async def scenario() -> None:
        transport = _BlockingTransport(cancel_raises=True)
        supervisor = DirectorRuntimeSupervisor(transport=transport)
        supervisor.start()
        request = _request()
        request = request.model_copy(update={"runtime_config": request.runtime_config.model_copy(update={"timeout_ms": 10.0})})
        outcome = await supervisor.submit(request=request)
        assert outcome.attempt_state == DirectorRuntimeAttemptState.TIMED_OUT
        assert outcome.candidate is None
        assert supervisor.state == DirectorRuntimeLifecycleState.DEGRADED

    asyncio.run(scenario())


def test_supervisor_normalizes_disconnect_without_candidate_or_raw_detail() -> None:
    async def scenario() -> None:
        supervisor = DirectorRuntimeSupervisor(transport=_DisconnectingTransport())
        supervisor.start()
        outcome = await supervisor.submit(request=_request())
        assert outcome.attempt_state == DirectorRuntimeAttemptState.FAILED
        assert outcome.candidate is None
        assert outcome.error is not None
        assert "api_key" not in outcome.error.safe_message
        assert supervisor.state == DirectorRuntimeLifecycleState.FAILED

    asyncio.run(scenario())


def test_supervisor_public_lifecycle_transitions_and_invalid_restart() -> None:
    async def scenario() -> None:
        transport = _BlockingTransport()
        supervisor = DirectorRuntimeSupervisor(transport=transport)
        assert supervisor.state == DirectorRuntimeLifecycleState.STARTING
        supervisor.start()
        assert supervisor.state == DirectorRuntimeLifecycleState.READY
        with pytest.raises(RuntimeError, match="start_transition_invalid"):
            supervisor.start()

        supervisor.mark_degraded()
        assert supervisor.state == DirectorRuntimeLifecycleState.DEGRADED
        supervisor.start()
        assert supervisor.state == DirectorRuntimeLifecycleState.READY

        task = asyncio.create_task(supervisor.submit(request=_request()))
        await transport.started.wait()
        assert supervisor.state == DirectorRuntimeLifecycleState.BUSY
        assert await supervisor.cancel(request_id="request-1") is True
        assert supervisor.state == DirectorRuntimeLifecycleState.STOPPING
        outcome = await task
        assert outcome.attempt_state == DirectorRuntimeAttemptState.CANCELLED
        assert supervisor.state == DirectorRuntimeLifecycleState.STOPPED
        supervisor.start()
        assert supervisor.state == DirectorRuntimeLifecycleState.READY

    asyncio.run(scenario())


def _sleeping_transport(*, sleep_seconds: float = 30.0) -> StdioJsonlDirectorRuntimeTransport:
    child = "import sys,time; sys.stdin.readline(); time.sleep(%r)" % sleep_seconds
    return StdioJsonlDirectorRuntimeTransport(command=(sys.executable, "-c", child), cancel_wait_seconds=0.5)


async def _wait_for_child(transport: StdioJsonlDirectorRuntimeTransport) -> None:
    deadline = time.monotonic() + 2.0
    while not transport.active_process_ids:
        assert time.monotonic() < deadline, "child process did not start"
        await asyncio.sleep(0.01)


def test_real_subprocess_timeout_reaps_child_and_degrades_supervisor() -> None:
    async def scenario() -> None:
        transport = _sleeping_transport()
        supervisor = DirectorRuntimeSupervisor(transport=transport)
        supervisor.start()
        request = _request()
        request = request.model_copy(update={"runtime_config": request.runtime_config.model_copy(update={"timeout_ms": 50.0})})
        outcome = await supervisor.submit(request=request)
        assert outcome.attempt_state == DirectorRuntimeAttemptState.TIMED_OUT
        assert outcome.candidate is None
        assert supervisor.state == DirectorRuntimeLifecycleState.DEGRADED
        assert transport.active_process_ids == frozenset()

    asyncio.run(scenario())


def test_real_subprocess_cancel_terminates_nonzero_child_and_reaps_it() -> None:
    async def scenario() -> None:
        transport = _sleeping_transport()
        supervisor = DirectorRuntimeSupervisor(transport=transport)
        supervisor.start()
        task = asyncio.create_task(supervisor.submit(request=_request()))
        await _wait_for_child(transport)
        assert await supervisor.cancel(request_id="request-1") is True
        outcome = await task
        assert outcome.attempt_state == DirectorRuntimeAttemptState.CANCELLED
        assert outcome.candidate is None
        assert supervisor.state == DirectorRuntimeLifecycleState.STOPPED
        assert transport.active_process_ids == frozenset()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "child",
    [
        "import sys; sys.stdin.readline(); sys.stderr.write('api_key=secret'); raise SystemExit(7)",
        "import sys; sys.stdin.readline(); print('{broken')",
        "import sys; sys.stdin.readline(); print('{}'); print('{}')",
    ],
)
def test_real_subprocess_failure_never_admits_candidate_or_retains_child(child: str) -> None:
    async def scenario() -> None:
        transport = StdioJsonlDirectorRuntimeTransport(command=(sys.executable, "-c", child))
        supervisor = DirectorRuntimeSupervisor(transport=transport)
        supervisor.start()
        outcome = await supervisor.submit(request=_request())
        assert outcome.attempt_state == DirectorRuntimeAttemptState.FAILED
        assert outcome.candidate is None
        assert outcome.error is not None
        assert "api_key" not in outcome.error.safe_message
        assert transport.active_process_ids == frozenset()

    asyncio.run(scenario())


def test_a3_modules_and_serving_route_have_no_authoritative_or_runtime_wiring() -> None:
    root = Path(__file__).resolve().parents[1]
    module_sources = "\n".join(
        (root / relative).read_text()
        for relative in (
            "app/domain/director_runtime_protocol.py",
            "app/services/director_runtime_transport.py",
            "app/services/director_runtime_supervisor_service.py",
        )
    )
    for forbidden in (
        "DiscussionEvent", "DiscussionWorkspace", "FormalizationProposal", "PlanVersion",
        "create_run", "AgentSession", "Worker", "Codex", "Claude", "git ",
    ):
        assert forbidden not in module_sources
    serving_source = (root / "app/services/project_director_message_service.py").read_text()
    assert "DirectorRuntimeSupervisor" not in serving_source
    assert "StdioJsonlDirectorRuntimeTransport" not in serving_source
