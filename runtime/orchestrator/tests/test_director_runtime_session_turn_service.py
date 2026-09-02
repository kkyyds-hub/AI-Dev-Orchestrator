from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4

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

import sqlite3
from datetime import datetime, timezone
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.core.db import begin_sqlite_transaction, configure_sqlite
from app.core.db_tables import ORMBase, ProjectDirectorMessageTable, ProjectDirectorSessionTable, ProjectTable
from app.domain.project_director_message import ProjectDirectorMessage, ProjectDirectorMessageSource
from app.domain.project_director_session import ProjectDirectorSessionStatus
from app.repositories.project_director_message_repository import ProjectDirectorMessageRepository
from app.repositories.project_director_session_repository import ProjectDirectorSessionRepository
from app.services.director_runtime_request_assembler_service import DirectorRuntimeRequestAssemblerService, DirectorRuntimeRequestRuntimeConfigOptions
from app.services.director_runtime_supervisor_service import DirectorRuntimeSupervisor

REAL_PROJECT = UUID("77777777-7777-7777-7777-777777777777")
REAL_SESSION = UUID("88888888-8888-8888-8888-888888888888")
REAL_MESSAGE = UUID("99999999-9999-9999-9999-999999999999")

class _RealTransport:
    def __init__(self, hook=None): self.invoke_count, self.hook = 0, hook
    async def invoke(self, *, request_id, request):
        self.invoke_count += 1
        if self.hook: self.hook()
        return {"schema_version": "p26-big-director-runtime/v1", "request_id": request_id, "response_text": "deterministic", "turn_semantics": {"conversation_mode": "general_discussion", "formal_action_requested": False, "hypothetical_action": False, "confidence": 0.8}, "discussion_lifecycle": {"observed_status": None, "suggested_next_status": None}, "discussion_delta_candidate": None, "formalization": {"proposal_candidate": None, "readiness": "not_ready"}, "tool_activity": [], "source_references": [], "runtime_metadata": {"runtime_state": "ready", "model_id": "m", "provider_profile_id": "p", "usage": {}, "duration_ms": 1.0, "attempt": 0}, "error": None}
    async def cancel(self, *, request_id): pass

def _real_fixture(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'r1.db'}", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", configure_sqlite)
    event.listen(engine, "begin", lambda connection: begin_sqlite_transaction(connection))
    ORMBase.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)()
    now = datetime.now(timezone.utc)
    db.add(ProjectTable(id=REAL_PROJECT, name="R1", summary="R1", status="active", stage="intake", created_at=now, updated_at=now))
    db.flush()
    db.add(ProjectDirectorSessionTable(id=REAL_SESSION, project_id=REAL_PROJECT, goal_text="goal", constraints="", status=ProjectDirectorSessionStatus.CONFIRMED, clarifying_questions_json="[]", clarifying_answers_json="[]", goal_summary="", confirmed_at=now, created_at=now, updated_at=now))
    db.commit()
    ProjectDirectorMessageRepository(db).create(ProjectDirectorMessage(id=REAL_MESSAGE, session_id=REAL_SESSION, role=ProjectDirectorMessageRole.USER, content="hello", sequence_no=1, related_project_id=REAL_PROJECT, source=ProjectDirectorMessageSource.SYSTEM, source_detail="r1"))
    db.commit()
    assembler = DirectorRuntimeRequestAssemblerService(db_session=db)
    return engine, db, assembler

def _real_run(db, assembler, transport):
    supervisor = DirectorRuntimeSupervisor(transport=transport); supervisor.start()
    return DirectorRuntimeSessionTurnService(assembler=assembler, supervisor=supervisor, session_repository=ProjectDirectorSessionRepository(db), message_repository=ProjectDirectorMessageRepository(db)), supervisor

def _real_config():
    return DirectorRuntimeRequestRuntimeConfigOptions(model_id="m", provider_profile_id="p", timeout_ms=1000.0, max_tool_rounds=0)

def _insert_u2(db):
    ProjectDirectorMessageRepository(db).create(ProjectDirectorMessage(id=uuid4(), session_id=REAL_SESSION, role=ProjectDirectorMessageRole.USER, content="u2", sequence_no=2, related_project_id=REAL_PROJECT, source=ProjectDirectorMessageSource.SYSTEM, source_detail="r1")); db.commit()

def test_r1_real_stale_between_assembly_and_submit(tmp_path):
    engine, db, real_assembler = _real_fixture(tmp_path)
    try:
        class HookedAssembler:
            def build_request(self, **kwargs):
                request = real_assembler.build_request(**kwargs); _insert_u2(db); return request
        transport = _RealTransport(); service_obj, supervisor = _real_run(db, HookedAssembler(), transport)
        with pytest.raises(DirectorRuntimeSessionTurnError, match="director_runtime_session_turn_current_message_stale"):
            asyncio.run(service_obj.execute_turn(session_id=REAL_SESSION, message_id=REAL_MESSAGE, runtime_config=_real_config(), request_id="r1-before"))
        assert transport.invoke_count == 0 and supervisor._attempts == {}
    finally: db.close(); engine.dispose()

def test_r1_real_stale_during_runtime(tmp_path):
    engine, db, assembler = _real_fixture(tmp_path)
    try:
        transport = _RealTransport(lambda: _insert_u2(db)); service_obj, _ = _real_run(db, assembler, transport)
        result = asyncio.run(service_obj.execute_turn(session_id=REAL_SESSION, message_id=REAL_MESSAGE, runtime_config=_real_config(), request_id="r1-during"))
        assert transport.invoke_count == 1 and result.supervision_outcome.candidate is None and result.supervision_outcome.error.code == "director_runtime_session_turn_stale"
    finally: db.close(); engine.dispose()

def test_r1_real_happy_path(tmp_path):
    engine, db, assembler = _real_fixture(tmp_path)
    try:
        transport = _RealTransport(); service_obj, _ = _real_run(db, assembler, transport)
        result = asyncio.run(service_obj.execute_turn(session_id=REAL_SESSION, message_id=REAL_MESSAGE, runtime_config=_real_config(), request_id="r1-happy"))
        assert transport.invoke_count == 1 and result.supervision_outcome.candidate is not None
    finally: db.close(); engine.dispose()
