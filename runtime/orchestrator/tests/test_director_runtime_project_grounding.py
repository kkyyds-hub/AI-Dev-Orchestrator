from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

from app.core.db import configure_sqlite
from app.core.db_tables import (
    AgentSessionTable,
    ORMBase,
    ProjectDirectorDiscussionEventTable,
    ProjectDirectorDiscussionWorkspaceTable,
    ProjectDirectorFormalizationProposalTable,
    ProjectDirectorMessageTable,
    ProjectDirectorPlanVersionTable,
    ProjectDirectorSessionTable,
    ProjectTable,
    RunTable,
    TaskTable,
)
from app.domain.director_runtime_protocol import serialize_director_runtime_request
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_session import ProjectDirectorSessionStatus
from app.repositories.project_director_message_repository import ProjectDirectorMessageRepository
from app.repositories.task_repository import TaskRepository
from app.domain.task import Task, TaskStatus
from app.services.director_runtime_request_assembler_service import (
    DirectorRuntimeRequestAssemblerError,
    DirectorRuntimeRequestAssemblerService,
    DirectorRuntimeRequestRuntimeConfigOptions,
)


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'grounding.db').as_posix()}")
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


def seed(db, *, status=ProjectDirectorSessionStatus.CONFIRMED):
    now = datetime(2026, 8, 20, tzinfo=timezone.utc)
    project_id, session_id = uuid4(), uuid4()
    db.add(ProjectTable(id=project_id, name="grounded project", summary="authoritative summary", status="active", stage="intake", created_at=now, updated_at=now))
    db.commit()
    db.add(ProjectDirectorSessionTable(id=session_id, project_id=project_id, goal_text="unconfirmed goal", constraints="unconfirmed constraints", status=status, clarifying_questions_json="[]", clarifying_answers_json="[]", goal_summary="unconfirmed summary", confirmed_at=now, created_at=now, updated_at=now))
    db.commit()
    message = ProjectDirectorMessageRepository(db).create(ProjectDirectorMessage(session_id=session_id, role=ProjectDirectorMessageRole.USER, content="current", sequence_no=1, source=ProjectDirectorMessageSource.SYSTEM, source_detail="fixture"))
    db.commit()
    return project_id, session_id, message.id


def config():
    return DirectorRuntimeRequestRuntimeConfigOptions(model_id="m", provider_profile_id="p", timeout_ms=1.0, max_tool_rounds=0)


def test_real_project_snapshot_is_authoritative_and_read_only(db):
    project_id, session_id, message_id = seed(db)
    task_repository = TaskRepository(db)
    for status in (TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.COMPLETED, TaskStatus.BLOCKED):
        task_repository.create(Task(project_id=project_id, title=f"task-{status.value}", status=status, input_summary="fixture"))
    tables = (ProjectTable, TaskTable, RunTable, AgentSessionTable, ProjectDirectorMessageTable, ProjectDirectorDiscussionEventTable, ProjectDirectorDiscussionWorkspaceTable, ProjectDirectorFormalizationProposalTable, ProjectDirectorPlanVersionTable)
    before = {table.__tablename__: db.scalar(select(func.count()).select_from(table)) for table in tables}
    request = DirectorRuntimeRequestAssemblerService(db_session=db).build_request(session_id=session_id, message_id=message_id, runtime_config=config(), request_id="grounding")
    after = {table.__tablename__: db.scalar(select(func.count()).select_from(table)) for table in tables}
    snapshot = request.authoritative_facts["project_snapshot"]
    assert snapshot == {"id": str(project_id), "name": "grounded project", "summary": "authoritative summary", "status": "active", "stage": "intake", "task_stats": snapshot["task_stats"]}
    assert set(snapshot) == {"id", "name", "summary", "status", "stage", "task_stats"}
    assert snapshot["task_stats"]["total_tasks"] == 4
    assert snapshot["task_stats"]["pending_tasks"] == 1
    assert snapshot["task_stats"]["running_tasks"] == 1
    assert snapshot["task_stats"]["completed_tasks"] == 1
    assert snapshot["task_stats"]["blocked_tasks"] == 1
    assert before == after
    serialized = serialize_director_runtime_request(request)
    assert serialized["schema_version"] == "p26-big-director-runtime/v1"
    assert "project_snapshot" not in set(serialized) - {"authoritative_facts"}


def test_unconfirmed_session_gets_project_snapshot_without_session_authority_and_missing_project_fails_closed(db):
    _, session_id, message_id = seed(db, status=ProjectDirectorSessionStatus.DRAFT)
    request = DirectorRuntimeRequestAssemblerService(db_session=db).build_request(session_id=session_id, message_id=message_id, runtime_config=config())
    assert "project_snapshot" in request.authoritative_facts
    for key in ("goal", "constraints", "goal_summary", "confirmed_at"):
        assert key not in request.authoritative_facts
    missing = uuid4()
    service = DirectorRuntimeRequestAssemblerService(db_session=db, project_repository=SimpleNamespace(get_by_id=lambda _: None))
    session = service._session_repository.get_by_id(session_id)
    object.__setattr__(session, "project_id", missing)
    service._session_repository = SimpleNamespace(get_by_id=lambda _: session)
    with pytest.raises(DirectorRuntimeRequestAssemblerError, match="project_not_found"):
        service.build_request(session_id=session_id, message_id=message_id, runtime_config=config())
