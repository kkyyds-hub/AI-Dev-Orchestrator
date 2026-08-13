from __future__ import annotations

import asyncio
from pathlib import Path

from app.domain.director_runtime_protocol import (
    DIRECTOR_RUNTIME_SCHEMA_VERSION,
    validate_director_runtime_request,
)
from app.services.director_runtime_supervisor_service import (
    DirectorRuntimeAttemptState,
    DirectorRuntimeSupervisor,
)
from app.services.director_runtime_transport import StdioJsonlDirectorRuntimeTransport


RUNTIME = (
    Path(__file__).resolve().parents[2]
    / "director-runtime"
    / "dist"
    / "director-runtime.js"
)


def _request_payload(request_id: str) -> dict[str, object]:
    return {
        "schema_version": DIRECTOR_RUNTIME_SCHEMA_VERSION,
        "request_id": request_id,
        "project_id": "process-project",
        "session_id": "process-session",
        "message_id": f"message-{request_id}",
        "current_user_message": {
            "content": "Run the deterministic process loop.",
            "occurred_at": "2026-08-13T00:00:00Z",
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
        "available_tools": [
            {
                "tool_id": "allowed-but-unregistered",
                "allowed": True,
                "authorization_id": "process-authorization",
                "idempotency_key": "process-idempotency",
            }
        ],
        "permission_context": {},
        "runtime_config": {
            "model_id": "synthetic-director-model",
            "provider_profile_id": "synthetic-local",
            "timeout_ms": 1000.0,
            "max_tool_rounds": 0,
        },
    }


def _transport() -> StdioJsonlDirectorRuntimeTransport:
    return StdioJsonlDirectorRuntimeTransport(
        command=("node", str(RUNTIME)),
        cancel_wait_seconds=0.5,
    )


def test_process_transport_supervisor_admits_only_the_valid_deterministic_candidate() -> None:
    async def scenario() -> None:
        request = validate_director_runtime_request(_request_payload("process-success"))
        transport = _transport()
        supervisor = DirectorRuntimeSupervisor(transport=transport)
        supervisor.start()
        outcome = await supervisor.submit(request=request)

        assert outcome.attempt_state == DirectorRuntimeAttemptState.SUCCEEDED
        assert outcome.error is None
        assert outcome.candidate is not None
        assert outcome.candidate.request_id == request.request_id
        assert outcome.candidate.response_text == "synthetic director runtime response"
        assert outcome.candidate.tool_activity == []
        assert outcome.candidate.source_references[0].message_id == request.message_id
        assert transport.active_process_ids == frozenset()

    asyncio.run(scenario())


def test_process_stream_failure_timeout_and_cancel_reap_without_candidate_admission(monkeypatch) -> None:
    async def scenario() -> None:
        monkeypatch.setenv("DIRECTOR_RUNTIME_SYNTHETIC_MODE", "throw")
        stream_failure_transport = _transport()
        stream_failure_supervisor = DirectorRuntimeSupervisor(transport=stream_failure_transport)
        stream_failure_supervisor.start()
        stream_failure = await stream_failure_supervisor.submit(
            request=validate_director_runtime_request(_request_payload("process-stream-failure"))
        )
        assert stream_failure.candidate is None
        assert stream_failure.error is not None
        assert stream_failure_transport.active_process_ids == frozenset()

        monkeypatch.setenv("DIRECTOR_RUNTIME_SYNTHETIC_MODE", "block")
        timeout_transport = _transport()
        timeout_supervisor = DirectorRuntimeSupervisor(transport=timeout_transport)
        timeout_supervisor.start()
        timeout_request = validate_director_runtime_request(_request_payload("process-timeout"))
        timeout_request = timeout_request.model_copy(
            update={
                "runtime_config": timeout_request.runtime_config.model_copy(update={"timeout_ms": 50.0})
            }
        )
        timed_out = await timeout_supervisor.submit(request=timeout_request)
        assert timed_out.attempt_state == DirectorRuntimeAttemptState.TIMED_OUT
        assert timed_out.candidate is None
        assert timed_out.error is not None
        assert timeout_transport.active_process_ids == frozenset()

        cancel_transport = _transport()
        cancel_supervisor = DirectorRuntimeSupervisor(transport=cancel_transport)
        cancel_supervisor.start()
        cancel_request = validate_director_runtime_request(_request_payload("process-cancel"))
        submit = asyncio.create_task(cancel_supervisor.submit(request=cancel_request))
        deadline = asyncio.get_running_loop().time() + 2.0
        while not cancel_transport.active_process_ids:
            assert asyncio.get_running_loop().time() < deadline
            await asyncio.sleep(0.01)
        assert await cancel_supervisor.cancel(request_id=cancel_request.request_id) is True
        cancelled = await submit
        assert cancelled.attempt_state == DirectorRuntimeAttemptState.CANCELLED
        assert cancelled.candidate is None
        assert cancelled.error is not None
        assert cancel_transport.active_process_ids == frozenset()

    asyncio.run(scenario())
