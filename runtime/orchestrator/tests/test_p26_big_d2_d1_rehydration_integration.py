"""D2-D1: rebuild Director context from authoritative SQLite across fresh children."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker

from app.core.db import configure_sqlite
from app.core.db_tables import ORMBase, ProjectDirectorSessionTable, ProjectTable
from app.domain.director_runtime_protocol import serialize_director_runtime_request
from app.domain.project_director_conversation_intelligence import (
    FormalizationChange,
    FormalizationChangeType,
    FormalizationTarget,
)
from app.domain.project_director_discussion import (
    DiscussionActorClaim,
    DiscussionEvent,
    DiscussionEventType,
    DiscussionWorkspace,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_formalization_proposal import ProjectDirectorFormalizationProposal
from app.domain.project_director_plan_version import ProjectDirectorPlanVersion
from app.domain.project_director_session import ProjectDirectorSessionStatus
from app.repositories.project_director_discussion_event_repository import (
    ProjectDirectorDiscussionEventRepository,
)
from app.repositories.project_director_discussion_workspace_repository import (
    ProjectDirectorDiscussionWorkspaceRepository,
)
from app.repositories.project_director_message_repository import ProjectDirectorMessageRepository
from app.repositories.project_director_formalization_proposal_repository import (
    ProjectDirectorFormalizationProposalRepository,
)
from app.repositories.project_director_plan_version_repository import ProjectDirectorPlanVersionRepository
from app.services.director_runtime_provider_config_service import (
    DirectorRuntimeProviderConfigService,
    OPENAI_PROVIDER_PROFILE_ID,
)
from app.services.director_runtime_request_assembler_service import (
    DirectorRuntimeRequestAssemblerService,
    DirectorRuntimeRequestRuntimeConfigOptions,
)
from app.services.director_runtime_supervisor_service import (
    DirectorRuntimeAttemptState,
    DirectorRuntimeSupervisor,
)
from app.services.director_runtime_transport import StdioJsonlDirectorRuntimeTransport
from app.services.project_director_discussion_workspace_reducer_service import (
    ProjectDirectorDiscussionWorkspaceReducerService,
)
from app.services.provider_config_service import ProviderConfigService


RUNTIME = Path(__file__).resolve().parents[2] / "director-runtime/dist/director-runtime.js"
FAKE_KEY = "d2-d1-test-only-fake-credential"
NOW = datetime(2026, 9, 16, tzinfo=timezone.utc)


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'authority.sqlite3'}")

    @event.listens_for(engine, "connect")
    def setup(connection: sqlite3.Connection, _: object) -> None:
        configure_sqlite(connection, _)

    ORMBase.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def snapshot(db):
    """Compare every actual SQLite row, not merely row counts."""
    tables = inspect(db.bind).get_table_names()
    return {
        table: tuple(tuple(repr(value) for value in row) for row in db.execute(text(f'SELECT * FROM "{table}" ORDER BY rowid')).all())
        for table in tables
        if table != "sqlite_sequence"
    }


def seed(db, label: str):
    project_id, session_id = uuid4(), uuid4()
    db.add(ProjectTable(id=project_id, name=f"{label} project", summary=f"FACT_{label}_V1", status="active", stage="intake", created_at=NOW, updated_at=NOW))
    db.commit()
    db.add(ProjectDirectorSessionTable(id=session_id, project_id=project_id, goal_text=f"GOAL_{label}", constraints=f"CONSTRAINT_{label}", status=ProjectDirectorSessionStatus.CONFIRMED, clarifying_questions_json="[]", clarifying_answers_json="[]", goal_summary=f"GOAL_{label}", confirmed_at=NOW, created_at=NOW, updated_at=NOW))
    db.commit()
    workspace_repository = ProjectDirectorDiscussionWorkspaceRepository(db)
    workspace_repository.create_if_absent(workspace=DiscussionWorkspace(session_id=session_id, project_id=project_id, topic="", version_no=0, last_event_sequence_no=0, created_at=NOW, updated_at=NOW))
    db.commit()
    return project_id, session_id


def message(db, session_id: UUID, sequence_no: int, content: str, role=ProjectDirectorMessageRole.USER):
    result = ProjectDirectorMessageRepository(db).create(ProjectDirectorMessage(session_id=session_id, role=role, content=content, sequence_no=sequence_no, source=ProjectDirectorMessageSource.SYSTEM, source_detail="test-fixture"))
    db.commit()
    return result


def discussion(db, project_id: UUID, session_id: UUID, source_message_id: UUID, entries):
    event_repository = ProjectDirectorDiscussionEventRepository(db)
    workspace_repository = ProjectDirectorDiscussionWorkspaceRepository(db)
    for kind, option_id, content in entries:
        event_value = DiscussionEvent(id=uuid4(), session_id=session_id, project_id=project_id, sequence_no=event_repository.get_next_sequence_no(session_id=session_id), event_type=kind, subject_key=str(option_id), content=content, payload={"option_id": str(option_id)}, source_message_ids=[source_message_id], created_by=DiscussionActorClaim.USER_EXPLICIT, confidence=1.0, created_at=NOW)
        event_repository.append_if_absent(event=event_value, idempotency_key=str(event_value.id))
    workspace = workspace_repository.get_by_session_id(session_id=session_id)
    updated, changed = ProjectDirectorDiscussionWorkspaceReducerService().reduce_workspace(workspace=workspace, events=event_repository.list_by_session_id(session_id=session_id))
    assert changed
    workspace_repository.update_if_version(workspace=updated, expected_version_no=workspace.version_no)
    db.commit()


def request(db, session_id: UUID, current_message_id: UUID, name: str, *, model="d2-model-one", timeout_ms=20000):
    with sessionmaker(bind=db.bind, expire_on_commit=False)() as independent_reader:
        result = DirectorRuntimeRequestAssemblerService(db_session=independent_reader).build_request(
            session_id=session_id,
            message_id=current_message_id,
            runtime_config=DirectorRuntimeRequestRuntimeConfigOptions(model_id=model, provider_profile_id=OPENAI_PROVIDER_PROFILE_ID, timeout_ms=timeout_ms, max_tool_rounds=0),
            request_id=name,
        )
    assert serialize_director_runtime_request(result)["request_id"] == name
    assert FAKE_KEY not in result.model_dump_json()
    return result


def sse_chunk(model, delta, finish):
    return f'data: {json.dumps({"id": "loopback", "object": "chat.completion.chunk", "created": 1, "model": model, "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]})}\n\n'.encode()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append(payload)
        response = self.server.responses[min(len(self.server.requests) - 1, len(self.server.responses) - 1)]
        if response.get("error"):
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'{"error":{"message":"loopback failure"}}')
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(sse_chunk(payload["model"], {"role": "assistant", "content": response["text"]}, None))
        self.wfile.write(sse_chunk(payload["model"], {}, response.get("finish", "stop")))
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, format, *args):  # noqa: A002
        pass


class Stub:
    def __init__(self, responses=None):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.requests = []
        self.server.responses = responses or [{"text": "FINAL_LOOPBACK"}]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_address[1]}/v1"

    @property
    def requests(self):
        return self.server.requests

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def environment(tmp_path, stub, *, semantic=False):
    config = ProviderConfigService(config_path=tmp_path / "provider-test.json")
    config.update_openai_config(api_key=FAKE_KEY, base_url=stub.url)
    bridge = DirectorRuntimeProviderConfigService(provider_config_service=config)
    return {
        **bridge.build_openai_runtime_environment(provider_profile_id=OPENAI_PROVIDER_PROFILE_ID).to_environment(),
        "DIRECTOR_RUNTIME_SEMANTIC_COMPACTION_MODE": "enabled" if semantic else "disabled",
        "DIRECTOR_RUNTIME_SYNTHETIC_MODE": "",
    }


async def invoke(current, child_environment):
    transport = StdioJsonlDirectorRuntimeTransport(command=("node", str(RUNTIME)), environment=child_environment, cancel_wait_seconds=0.5)
    supervisor = DirectorRuntimeSupervisor(transport=transport)
    supervisor.start()
    outcome = await supervisor.submit(request=current)
    assert transport.active_process_ids == frozenset()
    return outcome


def assert_success(outcome, current):
    assert outcome.attempt_state == DirectorRuntimeAttemptState.SUCCEEDED
    assert outcome.error is None
    candidate = outcome.candidate
    assert candidate is not None
    assert candidate.request_id == current.request_id
    assert candidate.tool_activity == []
    assert candidate.source_references[0].message_id == current.message_id
    assert candidate.runtime_metadata.model_id == current.runtime_config.model_id
    assert FAKE_KEY not in candidate.model_dump_json()


def model_input(stub, index=-1):
    return json.dumps(stub.requests[index]["messages"], ensure_ascii=False)


def test_cold_next_turn_reversal_restart_model_switch_and_interleaving(db, tmp_path, monkeypatch):
    started_process_ids = []
    original_spawn = asyncio.create_subprocess_exec

    async def record_spawn(*args, **kwargs):
        process = await original_spawn(*args, **kwargs)
        started_process_ids.append(process.pid)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", record_spawn)
    project_a, session_a = seed(db, "A")
    project_b, session_b = seed(db, "B")
    historical_a = message(db, session_a, 1, "OLDER_A_ONLY")
    current_a = message(db, session_a, 2, "CURRENT_A_1")
    current_b = message(db, session_b, 1, "CURRENT_B_1")
    option_a, option_b, option_other = uuid4(), uuid4(), uuid4()
    discussion(db, project_a, session_a, historical_a.id, [(DiscussionEventType.OPTION_ADDED, option_a, "OPTION_A"), (DiscussionEventType.OPTION_ADDED, option_b, "OPTION_B"), (DiscussionEventType.OPTION_PREFERRED, option_a, "PREFER_A")])
    discussion(db, project_b, session_b, current_b.id, [(DiscussionEventType.OPTION_ADDED, option_other, "OPTION_B_PROJECT"), (DiscussionEventType.OPTION_PREFERRED, option_other, "PREFER_B_PROJECT")])
    stub = Stub()
    try:
        child_env = environment(tmp_path, stub)
        async def scenario():
            first = request(db, session_a, current_a.id, "a1")
            before = snapshot(db)
            result = await invoke(first, child_env)
            assert_success(result, first)
            assert result.candidate.response_text == "FINAL_LOOPBACK"
            assert snapshot(db) == before
            first_input = model_input(stub)
            for expected in ("CURRENT_A_1", "OLDER_A_ONLY", "FACT_A_V1", str(option_a)):
                assert expected in first_input
            assert "FACT_B_V1" not in first_input

            second_project = request(db, session_b, current_b.id, "b1")
            result_b = await invoke(second_project, child_env)
            assert_success(result_b, second_project)
            assert snapshot(db) == before
            assert "FACT_B_V1" in model_input(stub)
            assert "FACT_A_V1" not in model_input(stub)

            next_message = message(db, session_a, 3, "CURRENT_A_2")
            discussion(db, project_a, session_a, next_message.id, [(DiscussionEventType.OPTION_REJECTED, option_a, "REJECT_A_REASON"), (DiscussionEventType.OPTION_PREFERRED, option_b, "PREFER_B")])
            project_row = db.get(ProjectTable, project_a)
            project_row.summary = "FACT_A_V2"
            db.commit()
            latest = request(db, session_a, next_message.id, "a2")
            assert str(latest.active_discussion_workspace["preferred_option_id"]) == str(option_b)
            assert latest.current_user_message.content == "CURRENT_A_2"
            assert str(latest.recent_raw_messages.items[-1].message_id) == str(current_a.id)
            before = snapshot(db)
            result_a2 = await invoke(latest, child_env)
            assert_success(result_a2, latest)
            a2_input = model_input(stub)
            assert "FACT_A_V2" in a2_input
            assert "REJECT_A_REASON" in model_input(stub)
            assert "FACT_B_V1" not in model_input(stub)
            assert snapshot(db) == before

            restarted = request(db, session_a, next_message.id, "a3-restart")
            switched = request(db, session_a, next_message.id, "a4-model", model="d2-model-two")
            for index, current in enumerate((restarted, switched)):
                result = await invoke(current, child_env)
                assert_success(result, current)
                if index == 0:
                    assert model_input(stub) == a2_input
                assert "FACT_A_V2" in model_input(stub)
                assert str(option_b) in model_input(stub)
                assert "CURRENT_A_2" in model_input(stub)
                assert snapshot(db) == before
            assert stub.requests[-1]["model"] == "d2-model-two"
            concurrent_a = request(db, session_a, next_message.id, "a5-concurrent")
            concurrent_b = request(db, session_b, current_b.id, "b2-concurrent")
            concurrent_results = await asyncio.gather(invoke(concurrent_a, child_env), invoke(concurrent_b, child_env))
            for result, current in zip(concurrent_results, (concurrent_a, concurrent_b)):
                assert_success(result, current)
            concurrent_inputs = [model_input(stub, -2), model_input(stub, -1)]
            assert sum("FACT_A_V2" in value and "FACT_B_V1" not in value for value in concurrent_inputs) == 1
            assert sum("FACT_B_V1" in value and "FACT_A_V2" not in value for value in concurrent_inputs) == 1
            assert snapshot(db) == before
            assert len(stub.requests) == 7
            assert len(started_process_ids) == len(set(started_process_ids)) == 7
        asyncio.run(scenario())
    finally:
        stub.close()


@pytest.mark.parametrize("summary_response", [{"text": "SEMANTIC_HISTORY_ONLY"}, {"text": "PARTIAL_DISCARDED", "finish": "length"}, {"error": True}])
def test_db_backed_semantic_eligibility_success_and_fallback(db, tmp_path, summary_response):
    project_id, session_id = seed(db, "SEMANTIC")
    historical = message(db, session_id, 1, "OLD_HISTORY_SENTINEL " + "older evidence " * 550)
    current = message(db, session_id, 2, "NEW_CURRENT_SENTINEL")
    preferred_option = uuid4()
    discussion(db, project_id, session_id, historical.id, [(DiscussionEventType.OPTION_ADDED, preferred_option, "OPTION_FRESH"), (DiscussionEventType.OPTION_PREFERRED, preferred_option, "PREFERRED_FRESH")])
    stub = Stub([summary_response, {"text": "FINAL_SEMANTIC_ANSWER"}])
    try:
        child_env = environment(tmp_path, stub, semantic=True)
        async def scenario():
            current_request = request(db, session_id, current.id, "semantic", timeout_ms=20000)
            before = snapshot(db)
            result = await invoke(current_request, child_env)
            assert_success(result, current_request)
            assert result.candidate.response_text == "FINAL_SEMANTIC_ANSWER"
            assert len(stub.requests) == 2
            assert "OLD_HISTORY_SENTINEL" in model_input(stub, 0)
            final = model_input(stub)
            for expected in ("FACT_SEMANTIC_V1", "NEW_CURRENT_SENTINEL", str(preferred_option)):
                assert expected in final
            if summary_response.get("finish", "stop") == "stop" and not summary_response.get("error"):
                assert "SEMANTIC_HISTORY_ONLY" in final
            else:
                assert "PARTIAL_DISCARDED" not in final
                assert "NON_AUTHORITATIVE_WORKING_MEMORY_PROJECTION" in final
            assert snapshot(db) == before
        asyncio.run(scenario())
    finally:
        stub.close()


def test_semantic_disabled_below_timeout_threshold(db, tmp_path):
    _, session_id = seed(db, "BUDGET")
    message(db, session_id, 1, "OLD_HISTORY_SENTINEL " + "older evidence " * 550)
    current = message(db, session_id, 2, "NEW_CURRENT_SENTINEL")
    stub = Stub()
    try:
        child_env = environment(tmp_path, stub, semantic=True)
        async def scenario():
            current_request = request(db, session_id, current.id, "short-budget", timeout_ms=4500)
            before = snapshot(db)
            assert_success(await invoke(current_request, child_env), current_request)
            assert len(stub.requests) == 1
            assert snapshot(db) == before
        asyncio.run(scenario())
    finally:
        stub.close()


def test_db_backed_formalization_and_provenance_after_fresh_process(db, tmp_path):
    project_id, session_id = seed(db, "FORMAL")
    source_message = message(db, session_id, 1, "SOURCE_FORMAL_TOPIC")
    assistant = message(db, session_id, 2, "ASSISTANT_FORMAL_PROPOSAL", role=ProjectDirectorMessageRole.ASSISTANT)
    current = message(db, session_id, 3, "CURRENT_FORMAL_USER")
    source_event = DiscussionEvent(id=uuid4(), session_id=session_id, project_id=project_id, sequence_no=1, event_type=DiscussionEventType.TOPIC_SET, subject_key="topic", content="FORMAL_TOPIC", source_message_ids=[source_message.id], created_by=DiscussionActorClaim.USER_EXPLICIT, confidence=1.0, created_at=NOW)
    event_repository = ProjectDirectorDiscussionEventRepository(db)
    event_repository.append_if_absent(event=source_event, idempotency_key=str(source_event.id))
    workspace_repository = ProjectDirectorDiscussionWorkspaceRepository(db)
    workspace = workspace_repository.get_by_session_id(session_id=session_id)
    updated, changed = ProjectDirectorDiscussionWorkspaceReducerService().reduce_workspace(workspace=workspace, events=[source_event])
    assert changed
    workspace_repository.update_if_version(workspace=updated, expected_version_no=0)
    db.commit()
    proposal = ProjectDirectorFormalizationProposal(
        proposal_id=uuid4(), session_id=session_id, project_id=project_id,
        assistant_message_id=assistant.id, workspace_version=updated.version_no,
        target=FormalizationTarget.PLAN_REVISION, summary="FORMAL_PROPOSAL_V1",
        changes=[FormalizationChange(change_type=FormalizationChangeType.UPDATE, subject_key="topic", summary="revise topic", source_event_ids=[source_event.id])],
        source_message_ids=[source_message.id], source_event_ids=[source_event.id],
        risk_summary="review only", requires_confirmation=True, created_at=NOW + timedelta(days=1), updated_at=NOW + timedelta(days=1),
    )
    ProjectDirectorFormalizationProposalRepository(db).create_no_commit(proposal)
    version = ProjectDirectorPlanVersion(
        session_id=session_id, project_id=project_id, version_no=1,
        plan_summary="FORMAL_PLAN_V1", formalization_proposal_id=proposal.proposal_id,
        formalization_target=FormalizationTarget.PLAN_REVISION,
        formalization_workspace_version=updated.version_no,
        formalization_source_message_ids=[source_message.id],
        formalization_source_event_ids=[source_event.id],
    )
    ProjectDirectorPlanVersionRepository(db).create(version)
    db.commit()
    stub = Stub()
    try:
        child_env = environment(tmp_path, stub)
        async def scenario():
            current_request = request(db, session_id, current.id, "formal-1")
            formalization = serialize_director_runtime_request(current_request)["active_formalization"]
            assert formalization["proposal"]["proposal_id"] == str(proposal.proposal_id)
            assert formalization["plan_version"]["id"] == str(version.id)
            before = snapshot(db)
            for name in ("formal-1", "formal-2"):
                built = current_request if name == "formal-1" else request(db, session_id, current.id, name)
                assert_success(await invoke(built, child_env), built)
                final = model_input(stub)
                for value in ("FORMAL_TOPIC", "FORMAL_PROPOSAL_V1", "FORMAL_PLAN_V1", str(source_event.id), str(source_message.id), "CURRENT_FORMAL_USER"):
                    assert value in final
                assert snapshot(db) == before
            assert model_input(stub, 0) == model_input(stub, 1)
        asyncio.run(scenario())
    finally:
        stub.close()


def test_oversized_db_corpus_skips_semantic_provider_call(db, tmp_path):
    _, session_id = seed(db, "OVERSIZED")
    for sequence_no in range(1, 6):
        message(db, session_id, sequence_no, f"HISTORY_{sequence_no}_" + "prior data " * 850)
    current = message(db, session_id, 6, "CURRENT_OVERSIZED")
    stub = Stub()
    try:
        child_env = environment(tmp_path, stub, semantic=True)
        async def scenario():
            built = request(db, session_id, current.id, "oversized", timeout_ms=20000)
            before = snapshot(db)
            assert_success(await invoke(built, child_env), built)
            assert len(stub.requests) == 1
            assert "CURRENT_OVERSIZED" in model_input(stub)
            assert "FACT_OVERSIZED_V1" in model_input(stub)
            assert snapshot(db) == before
        asyncio.run(scenario())
    finally:
        stub.close()


@pytest.mark.parametrize("history", ["", "a little previous context", "OLD_ELIGIBLE " + "history " * 800])
def test_empty_small_and_default_off_do_not_summarize(db, tmp_path, history):
    _, session_id = seed(db, "ELIGIBILITY")
    if history:
        message(db, session_id, 1, history)
    current = message(db, session_id, 2 if history else 1, "CURRENT_ELIGIBILITY")
    stub = Stub()
    try:
        child_env = environment(tmp_path, stub, semantic=bool(history) and len(history) < 100)
        async def scenario():
            built = request(db, session_id, current.id, "eligibility")
            before = snapshot(db)
            assert_success(await invoke(built, child_env), built)
            assert len(stub.requests) == 1
            assert "FACT_ELIGIBILITY_V1" in model_input(stub)
            assert snapshot(db) == before
        asyncio.run(scenario())
    finally:
        stub.close()


def test_system_fact_empty_message_lineage_is_structurally_complete(db, tmp_path):
    project_id, session_id = seed(db, "INCOMPLETE")
    message(db, session_id, 1, "OLD_INCOMPLETE " + "older evidence " * 550)
    current = message(db, session_id, 2, "CURRENT_INCOMPLETE")
    event_value = DiscussionEvent(id=uuid4(), session_id=session_id, project_id=project_id, sequence_no=1, event_type=DiscussionEventType.TOPIC_SET, subject_key="topic", content="SYSTEM_FACT_NO_MESSAGE_PROVENANCE", source_message_ids=[], created_by=DiscussionActorClaim.SYSTEM_FACT, confidence=1.0, created_at=NOW)
    ProjectDirectorDiscussionEventRepository(db).append_if_absent(event=event_value, idempotency_key=str(event_value.id))
    workspace_repository = ProjectDirectorDiscussionWorkspaceRepository(db)
    workspace = workspace_repository.get_by_session_id(session_id=session_id)
    updated, changed = ProjectDirectorDiscussionWorkspaceReducerService().reduce_workspace(workspace=workspace, events=[event_value])
    assert changed
    workspace_repository.update_if_version(workspace=updated, expected_version_no=0)
    db.commit()
    stub = Stub()
    try:
        child_env = environment(tmp_path, stub, semantic=True)
        async def scenario():
            built = request(db, session_id, current.id, "incomplete")
            before = snapshot(db)
            assert_success(await invoke(built, child_env), built)
            assert len(stub.requests) == 2
            assert "SYSTEM_FACT_NO_MESSAGE_PROVENANCE" in model_input(stub, 0)
            assert str(event_value.id) in model_input(stub, 0)
            assert "FACT_INCOMPLETE_V1" in model_input(stub)
            assert snapshot(db) == before
        asyncio.run(scenario())
    finally:
        stub.close()


def test_crash_timeout_reap_and_rebuild_from_current_db(db, tmp_path):
    _, session_id = seed(db, "CRASH")
    current = message(db, session_id, 1, "CRASH_TURN")
    stub = Stub()
    try:
        child_env = environment(tmp_path, stub)
        async def scenario():
            failing = request(db, session_id, current.id, "crash")
            before = snapshot(db)
            failure = await invoke(failing, {**child_env, "DIRECTOR_RUNTIME_SYNTHETIC_MODE": "throw", "DIRECTOR_RUNTIME_PROVIDER_MODE": ""})
            assert failure.candidate is None and failure.error is not None
            assert snapshot(db) == before
            blocked = request(db, session_id, current.id, "timeout", timeout_ms=50)
            timed_out = await invoke(blocked, {**child_env, "DIRECTOR_RUNTIME_SYNTHETIC_MODE": "block", "DIRECTOR_RUNTIME_PROVIDER_MODE": ""})
            assert timed_out.attempt_state == DirectorRuntimeAttemptState.TIMED_OUT
            assert timed_out.candidate is None
            assert snapshot(db) == before
            cancelling = request(db, session_id, current.id, "cancel", timeout_ms=10000)
            cancel_transport = StdioJsonlDirectorRuntimeTransport(command=("node", str(RUNTIME)), environment={**child_env, "DIRECTOR_RUNTIME_SYNTHETIC_MODE": "block", "DIRECTOR_RUNTIME_PROVIDER_MODE": ""}, cancel_wait_seconds=0.5)
            cancel_supervisor = DirectorRuntimeSupervisor(transport=cancel_transport)
            cancel_supervisor.start()
            pending = asyncio.create_task(cancel_supervisor.submit(request=cancelling))
            deadline = asyncio.get_running_loop().time() + 2
            while not cancel_transport.active_process_ids:
                assert asyncio.get_running_loop().time() < deadline
                await asyncio.sleep(0.01)
            assert await cancel_supervisor.cancel(request_id=cancelling.request_id)
            cancelled = await pending
            assert cancelled.attempt_state == DirectorRuntimeAttemptState.CANCELLED
            assert cancelled.candidate is None
            assert cancel_transport.active_process_ids == frozenset()
            assert snapshot(db) == before
            restarted = request(db, session_id, current.id, "recovered")
            assert_success(await invoke(restarted, child_env), restarted)
            assert "FACT_CRASH_V1" in model_input(stub)
            assert snapshot(db) == before
            assert len(stub.requests) == 1
        asyncio.run(scenario())
    finally:
        stub.close()


def test_old_raw_evidence_outside_python_window_is_not_invented(db, tmp_path):
    _, session_id = seed(db, "OLD")
    old = message(db, session_id, 1, "OLD_REJECTION_REASON_ONLY_OUTSIDE_WINDOW")
    for sequence_no in range(2, 16):
        message(db, session_id, sequence_no, f"UNRELATED_{sequence_no}")
    current = message(db, session_id, 16, "CURRENT_ASKS_ABOUT_OLD_REASON")
    stub = Stub()
    try:
        child_env = environment(tmp_path, stub)
        async def scenario():
            built = request(db, session_id, current.id, "old-evidence-gap")
            assert built.recent_raw_messages.has_more_before
            assert str(old.id) not in [str(item.message_id) for item in built.recent_raw_messages.items]
            before = snapshot(db)
            assert_success(await invoke(built, child_env), built)
            assert "OLD_REJECTION_REASON_ONLY_OUTSIDE_WINDOW" not in model_input(stub)
            assert "has_more_before" in model_input(stub)
            assert snapshot(db) == before
        asyncio.run(scenario())
    finally:
        stub.close()
