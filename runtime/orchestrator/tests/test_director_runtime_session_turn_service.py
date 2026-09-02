from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

import pytest

from app.domain.director_runtime_protocol import validate_director_runtime_request
from app.domain.project_director_message import ProjectDirectorMessageRole
from app.services.director_runtime_session_turn_service import (
    DirectorRuntimeSessionTurnError,
    DirectorRuntimeSessionTurnService,
)
from app.services.director_runtime_supervisor_service import (
    DirectorRuntimeAttemptState,
    DirectorRuntimeLifecycleState,
    DirectorRuntimeSupervisionOutcome,
)


PROJECT = UUID("11111111-1111-1111-1111-111111111111")
SESSION = UUID("22222222-2222-2222-2222-222222222222")
MESSAGE = UUID("33333333-3333-3333-3333-333333333333")


@dataclass
class Session:
    id: UUID = SESSION
    project_id: UUID | None = PROJECT


@dataclass
class Message:
    id: UUID = MESSAGE
    session_id: UUID = SESSION
    related_project_id: UUID | None = PROJECT
    role: object = ProjectDirectorMessageRole.USER
    sequence_no: int = 1


class Repo:
    def __init__(self, session=None, message=None, next_no=2):
        self.session = session or Session()
        self.message = message or Message()
        self.next_no = next_no

    def get_by_id(self, value):
        return self.session if value == SESSION else self.message

    def get_next_sequence_no(self, *, session_id):
        return self.next_no


class Assembler:
    def __init__(self, request):
        self.request = request

    def build_request(self, **kwargs):
        assert kwargs["request_id"] == self.request.request_id
        return self.request


class Supervisor:
    def __init__(self, outcome, repo=None):
        self.outcome = outcome
        self.state = DirectorRuntimeLifecycleState.READY
        self.submit_count = 0
        self.repo = repo

    async def submit(self, *, request):
        self.submit_count += 1
        if self.repo is not None:
            self.repo.next_no = 3
        return self.outcome


def request_payload(request_id="req-1", session_id=SESSION, project_id=PROJECT, message_id=MESSAGE):
    return validate_director_runtime_request({
        "schema_version": "p26-big-director-runtime/v1", "request_id": request_id,
        "project_id": str(project_id), "session_id": str(session_id), "message_id": str(message_id),
        "current_user_message": {"content": "hello", "occurred_at": "2026-08-20T01:02:03Z", "actor_claim": "user"},
        "authoritative_facts": {}, "active_discussion_workspace": None,
        "relevant_discussion_events": [], "active_formalization": {"proposal": None, "plan_version": None},
        "governance_boundaries": {"authoritative_write": False, "director_may_modify_code": False,
        "formalization_requires_explicit_request": True, "confirmation_is_separate": True,
        "execution_boundary": "no_task_run_agent_session_before_execution"},
        "available_skills": [], "available_tools": [], "permission_context": {},
        "runtime_config": {"model_id": "m", "provider_profile_id": "p", "timeout_ms": 1000.0, "max_tool_rounds": 0},
    })


def outcome(request_id="req-1", candidate=True):
    return DirectorRuntimeSupervisionOutcome(
        request_id=request_id, attempt_state=DirectorRuntimeAttemptState.SUCCEEDED,
        candidate=request_payload(request_id) if False else (object() if candidate else None),
        error=None,
    ) if candidate else DirectorRuntimeSupervisionOutcome(
        request_id=request_id, attempt_state=DirectorRuntimeAttemptState.TIMED_OUT,
        candidate=None, error=object(),
    )


def service(repo, supervisor, request=None):
    return DirectorRuntimeSessionTurnService(
        assembler=Assembler(request or request_payload()), supervisor=supervisor,
        session_repository=repo, message_repository=repo,
    )


def test_happy_path_freezes_assistant_sequence_and_binds_identity():
    repo = Repo()
    supervisor = Supervisor(outcome())
    result = asyncio.run(service(repo, supervisor).execute_turn(
        session_id=SESSION, message_id=MESSAGE, runtime_config=object(), request_id="req-1"
    ))
    assert supervisor.submit_count == 1
    assert (result.project_id, result.session_id, result.user_message_id) == (PROJECT, SESSION, MESSAGE)
    assert (result.user_message_sequence_no, result.assistant_message_sequence_no) == (1, 2)
    assert result.supervision_outcome.candidate is not None

def test_stale_before_invocation_is_fail_closed():
    repo = Repo(next_no=3)
    supervisor = Supervisor(outcome())
    with pytest.raises(DirectorRuntimeSessionTurnError, match="current_message_stale"):
        asyncio.run(service(repo, supervisor).execute_turn(session_id=SESSION, message_id=MESSAGE, runtime_config=object(), request_id="req-1"))
    assert supervisor.submit_count == 0

def test_new_message_during_invocation_rejects_candidate():
    repo = Repo()
    supervisor = Supervisor(outcome(), repo=repo)
    result = asyncio.run(service(repo, supervisor).execute_turn(session_id=SESSION, message_id=MESSAGE, runtime_config=object(), request_id="req-1"))
    assert result.supervision_outcome.candidate is None
    assert result.supervision_outcome.error.code == "director_runtime_session_turn_stale"
    assert result.assistant_message_sequence_no == 2

def test_cross_session_and_project_mismatch_rejected_before_runtime():
    for message in (Message(session_id=UUID("44444444-4444-4444-4444-444444444444")), Message(related_project_id=UUID("55555555-5555-5555-5555-555555555555"))):
        repo = Repo(message=message)
        supervisor = Supervisor(outcome())
        with pytest.raises(DirectorRuntimeSessionTurnError):
            asyncio.run(service(repo, supervisor).execute_turn(session_id=SESSION, message_id=MESSAGE, runtime_config=object(), request_id="req-1"))
        assert supervisor.submit_count == 0

def test_assembler_correlation_tamper_rejected():
    repo = Repo()
    supervisor = Supervisor(outcome())
    with pytest.raises(DirectorRuntimeSessionTurnError, match="correlation_mismatch"):
        asyncio.run(service(repo, supervisor, request_payload(session_id=SESSION, message_id=UUID("66666666-6666-6666-6666-666666666666"))).execute_turn(session_id=SESSION, message_id=MESSAGE, runtime_config=object(), request_id="req-1"))
    assert supervisor.submit_count == 0
