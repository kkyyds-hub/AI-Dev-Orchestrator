from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domain.director_runtime_protocol import (
    DIRECTOR_RUNTIME_SCHEMA_VERSION,
    DirectorRuntimeProtocolError,
    validate_director_runtime_request,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.core.db import configure_sqlite
from app.core.db_tables import ORMBase, ProjectDirectorSessionTable, ProjectTable
from app.domain.project_director_session import ProjectDirectorSessionStatus
from app.repositories.project_director_message_repository import ProjectDirectorMessageRepository
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.services.director_runtime_request_assembler_service import (
    DirectorRuntimeRequestAssemblerError,
    DirectorRuntimeRequestAssemblerService,
)

NOW = "2026-08-20T01:02:03.456789Z"


def payload(**overrides):
    value = {
        "schema_version": DIRECTOR_RUNTIME_SCHEMA_VERSION,
        "request_id": "request", "project_id": "project", "session_id": "session", "message_id": "current",
        "current_user_message": {"content": "current", "occurred_at": NOW, "actor_claim": "user"},
        "authoritative_facts": {}, "active_discussion_workspace": None, "relevant_discussion_events": [],
        "active_formalization": {"proposal": None, "plan_version": None},
        "governance_boundaries": {"authoritative_write": False, "director_may_modify_code": False, "formalization_requires_explicit_request": True, "confirmation_is_separate": True, "execution_boundary": "no_task_run_agent_session_before_execution"},
        "available_skills": [], "available_tools": [], "permission_context": {},
        "runtime_config": {"model_id": "m", "provider_profile_id": "p", "timeout_ms": 1.0, "max_tool_rounds": 0},
    }
    value.update(overrides)
    return value


def item(message_id="history", sequence_no=1, **overrides):
    value = {"message_id": message_id, "role": "assistant", "content": "history", "sequence_no": sequence_no, "occurred_at": NOW, "source": "ai"}
    value.update(overrides)
    return value


def test_protocol_defaults_old_v1_and_rejects_invalid_recent_windows():
    old = validate_director_runtime_request(payload())
    assert old.recent_raw_messages.items == []
    assert old.recent_raw_messages.has_more_before is False
    assert validate_director_runtime_request(payload(recent_raw_messages={"items": [item()], "has_more_before": False})).recent_raw_messages.items[0].message_id == "history"
    invalid = [
        {"items": [item(f"m-{index}", index + 1) for index in range(13)], "has_more_before": True},
        {"items": [item("same", 1), item("same", 2)], "has_more_before": False},
        {"items": [item("one", 2), item("two", 1)], "has_more_before": False},
        {"items": [item("current", 1)], "has_more_before": False},
        {"items": [], "has_more_before": True},
        {"items": [item(role="invalid")], "has_more_before": False},
        {"items": [item(source="invalid")], "has_more_before": False},
        {"items": [item(occurred_at="invalid")], "has_more_before": False},
    ]
    for window in invalid:
        with pytest.raises(DirectorRuntimeProtocolError):
            validate_director_runtime_request(payload(recent_raw_messages=window))


class Messages:
    def __init__(self, messages, has_more=False):
        self.messages = messages
        self.has_more = has_more
        self.calls = []

    def list_by_session_id(self, **kwargs):
        self.calls.append(kwargs)
        return self.messages, self.has_more


def message(session_id, sequence_no, *, role=ProjectDirectorMessageRole.USER, source=ProjectDirectorMessageSource.SYSTEM):
    return SimpleNamespace(id=uuid4(), session_id=session_id, sequence_no=sequence_no, role=role, source=source, content=f"message-{sequence_no}", created_at=datetime(2026, 8, 20, tzinfo=timezone.utc))


def test_real_sqlite_assembler_selects_short_history_before_current_user(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'recent.db').as_posix()}")
    @event.listens_for(engine, "connect")
    def setup(connection: sqlite3.Connection, _: object) -> None:
        configure_sqlite(connection, _)
    ORMBase.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        session_id, project_id = uuid4(), uuid4()
        db.add(ProjectTable(id=project_id, name="project", summary="project", status="active", stage="intake", created_at=datetime(2026, 8, 20, tzinfo=timezone.utc), updated_at=datetime(2026, 8, 20, tzinfo=timezone.utc)))
        db.commit()
        db.add(ProjectDirectorSessionTable(id=session_id, project_id=project_id, goal_text="goal", constraints="", status=ProjectDirectorSessionStatus.CONFIRMED, clarifying_questions_json="[]", clarifying_answers_json="[]", goal_summary="", confirmed_at=datetime(2026, 8, 20, tzinfo=timezone.utc), created_at=datetime(2026, 8, 20, tzinfo=timezone.utc), updated_at=datetime(2026, 8, 20, tzinfo=timezone.utc)))
        db.commit()
        repository = ProjectDirectorMessageRepository(db)
        prior_user = repository.create(ProjectDirectorMessage(session_id=session_id, role=ProjectDirectorMessageRole.USER, content="U1 historical", sequence_no=1, source=ProjectDirectorMessageSource.SYSTEM, source_detail="fixture"))
        prior_assistant = repository.create(ProjectDirectorMessage(session_id=session_id, role=ProjectDirectorMessageRole.ASSISTANT, content="A1 historical", sequence_no=2, source=ProjectDirectorMessageSource.AI, source_detail="fixture"))
        current = repository.create(ProjectDirectorMessage(session_id=session_id, role=ProjectDirectorMessageRole.USER, content="U2 current", sequence_no=3, source=ProjectDirectorMessageSource.SYSTEM, source_detail="fixture"))
        db.commit()
        request = DirectorRuntimeRequestAssemblerService(db_session=db).build_request(session_id=session_id, message_id=current.id, runtime_config=SimpleNamespace(model_id="m", provider_profile_id="p", timeout_ms=1.0, max_tool_rounds=0), request_id="sqlite-recent")
        assert [entry.content for entry in request.recent_raw_messages.items] == ["U1 historical", "A1 historical"]
        assert [entry.sequence_no for entry in request.recent_raw_messages.items] == [1, 2]
        assert request.current_user_message.content == "U2 current"
    finally:
        db.close()
        engine.dispose()


def test_assembler_recent_window_uses_latest_governed_history_oldest_to_newest_and_fails_closed():
    session_id = uuid4()
    current = message(session_id, 31)
    history = [message(session_id, sequence_no, role=ProjectDirectorMessageRole.ASSISTANT, source=ProjectDirectorMessageSource.AI) for sequence_no in range(19, 31)]
    service = object.__new__(DirectorRuntimeRequestAssemblerService)
    service._message_repository = Messages(history, has_more=True)
    selected = service._select_recent_raw_messages(session_id=session_id, current_message=current)
    assert service._message_repository.calls == [{"session_id": session_id, "limit": 12, "before_message_id": current.id}]
    assert [entry["sequence_no"] for entry in selected["items"]] == list(range(19, 31))
    assert selected["has_more_before"] is True
    assert all(entry["message_id"] != str(current.id) for entry in selected["items"])
    service._message_repository = Messages([message(uuid4(), 1)])
    with pytest.raises(DirectorRuntimeRequestAssemblerError, match="recent_message_invalid"):
        service._select_recent_raw_messages(session_id=session_id, current_message=current)
    service._message_repository = Messages([message(session_id, 31)])
    with pytest.raises(DirectorRuntimeRequestAssemblerError, match="recent_message_invalid"):
        service._select_recent_raw_messages(session_id=session_id, current_message=current)
