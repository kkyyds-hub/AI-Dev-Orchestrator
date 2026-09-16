from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, delete, event, select
from sqlalchemy.orm import sessionmaker

from app.core.db import configure_sqlite
from app.core.db_tables import (
    ORMBase,
    ProjectDirectorMessageTable,
    ProjectDirectorSessionTable,
    ProjectTable,
    TaskTable,
)
from app.domain.director_runtime_protocol import serialize_director_runtime_request
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_session import ProjectDirectorSessionStatus
from app.domain.project_role import ProjectRoleCode
from app.domain.task import Task, TaskStatus
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.director_runtime_request_assembler_service import (
    DirectorRuntimeRequestAssemblerError,
    DirectorRuntimeRequestAssemblerService,
    DirectorRuntimeRequestRuntimeConfigOptions,
)


NOW = datetime(2026, 9, 16, 6, 0, 0, tzinfo=timezone.utc)
CONFIG = DirectorRuntimeRequestRuntimeConfigOptions(
    model_id="task-grounding", provider_profile_id="local", timeout_ms=1.0, max_tool_rounds=0
)
TOP_LEVEL_KEYS = {
    "schema_version", "request_id", "project_id", "session_id", "message_id",
    "current_user_message", "recent_raw_messages", "authoritative_facts",
    "active_discussion_workspace", "relevant_discussion_events", "active_formalization",
    "governance_boundaries", "available_skills", "available_tools", "permission_context",
    "runtime_config",
}
TASK_SNAPSHOT_KEYS = {"total", "returned", "has_more", "ordered_by", "items"}
TASK_ITEM_KEYS = {
    "id", "title", "status", "priority", "risk_level", "owner_role_code",
    "human_status", "updated_at",
}


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'task-grounding.sqlite').as_posix()}")

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


def create_project(db, *, name: str) -> UUID:
    project_id = uuid4()
    db.add(ProjectTable(
        id=project_id, name=name, summary=f"{name} summary", status="active", stage="planning",
        created_at=NOW, updated_at=NOW,
    ))
    db.commit()
    return project_id


def create_session(db, *, project_id: UUID, status: ProjectDirectorSessionStatus):
    session_id = uuid4()
    db.add(ProjectDirectorSessionTable(
        id=session_id, project_id=project_id, goal_text=f"{status.value} goal",
        goal_summary=f"{status.value} summary", constraints=f"{status.value} constraints",
        status=status, clarifying_questions_json="[]", clarifying_answers_json="[]",
        confirmed_at=NOW + timedelta(minutes=1), created_at=NOW, updated_at=NOW,
    ))
    db.commit()
    message = ProjectDirectorMessageRepository(db).create(ProjectDirectorMessage(
        session_id=session_id, role=ProjectDirectorMessageRole.USER,
        content=f"current message for {status.value}", sequence_no=1,
        related_project_id=project_id, source=ProjectDirectorMessageSource.SYSTEM,
        source_detail="task grounding fixture", created_at=NOW,
    ))
    db.commit()
    return session_id, message.id


def create_tasks(db, *, project_id: UUID, count: int, statuses: list[TaskStatus] | None = None, same_updated_at: bool = False):
    created: list[Task] = []
    repository = TaskRepository(db)
    for index in range(count):
        timestamp = NOW if same_updated_at else NOW + timedelta(seconds=index)
        task = Task(
            id=uuid4(), project_id=project_id, title=f"{project_id.hex[:6]}-task-{index:02d}",
            status=(statuses[index] if statuses is not None else TaskStatus.PENDING),
            input_summary="intentionally excluded from task snapshot",
            owner_role_code=ProjectRoleCode.ENGINEER if index == 0 else None,
            created_at=timestamp, updated_at=timestamp,
        )
        repository.create(task)
        created.append(task)
    return created


def build_serialized(db, *, session_id: UUID, message_id: UUID, request_id: str):
    return serialize_director_runtime_request(
        DirectorRuntimeRequestAssemblerService(db_session=db).build_request(
            session_id=session_id, message_id=message_id, runtime_config=CONFIG, request_id=request_id,
        )
    )


def expected_order(tasks: list[Task]) -> list[Task]:
    return sorted(
        tasks,
        key=lambda task: (task.updated_at, task.created_at, task.id.int),
        reverse=True,
    )


@pytest.mark.parametrize("count", [0, 1, 12, 13, 50])
def test_task_snapshot_boundaries_and_full_item_ordering(db, count: int):
    project_id = create_project(db, name=f"boundary-{count}")
    tasks = create_tasks(db, project_id=project_id, count=count)
    session_id, message_id = create_session(db, project_id=project_id, status=ProjectDirectorSessionStatus.CONFIRMED)

    request = build_serialized(db, session_id=session_id, message_id=message_id, request_id=f"boundary-{count}")
    snapshot = request["authoritative_facts"]["task_snapshot"]
    selected = expected_order(tasks)[:12]

    assert set(snapshot) == TASK_SNAPSHOT_KEYS
    assert snapshot["total"] == count
    assert snapshot["returned"] == min(count, 12)
    assert snapshot["has_more"] is (count > 12)
    assert snapshot["ordered_by"] == "updated_at_desc"
    assert [item["id"] for item in snapshot["items"]] == [str(task.id) for task in selected]
    for item, task in zip(snapshot["items"], selected, strict=True):
        assert set(item) == TASK_ITEM_KEYS
        assert item == {
            "id": str(task.id), "title": task.title, "status": task.status.value,
            "priority": task.priority.value, "risk_level": task.risk_level.value,
            "owner_role_code": task.owner_role_code.value if task.owner_role_code else None,
            "human_status": task.human_status.value,
            "updated_at": task.updated_at.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
        }


def test_task_snapshot_same_timestamp_tie_breaker_is_deterministic(db):
    project_id = create_project(db, name="same-timestamp")
    tasks = create_tasks(db, project_id=project_id, count=8, same_updated_at=True)
    session_id, message_id = create_session(db, project_id=project_id, status=ProjectDirectorSessionStatus.CONFIRMED)

    first = build_serialized(db, session_id=session_id, message_id=message_id, request_id="same-timestamp-1")
    second = build_serialized(db, session_id=session_id, message_id=message_id, request_id="same-timestamp-2")
    expected_ids = [str(task.id) for task in expected_order(tasks)]

    assert [item["id"] for item in first["authoritative_facts"]["task_snapshot"]["items"]] == expected_ids
    assert [item["id"] for item in second["authoritative_facts"]["task_snapshot"]["items"]] == expected_ids


def test_task_snapshot_isolates_projects_and_serializes_all_task_statuses(db):
    project_a = create_project(db, name="project-a")
    project_b = create_project(db, name="project-b")
    statuses = list(TaskStatus)
    a_tasks = create_tasks(db, project_id=project_a, count=len(statuses), statuses=statuses)
    create_tasks(db, project_id=project_b, count=1)
    b_row = db.execute(select(TaskTable).where(TaskTable.project_id == project_b)).scalar_one()
    b_row.title = "PROJECT_B_LATEST_SENTINEL_MUST_NOT_LEAK"
    b_row.updated_at = NOW + timedelta(days=10)
    db.commit()
    session_id, message_id = create_session(db, project_id=project_a, status=ProjectDirectorSessionStatus.CONFIRMED)

    request = build_serialized(db, session_id=session_id, message_id=message_id, request_id="project-isolation")
    snapshot = request["authoritative_facts"]["task_snapshot"]

    assert snapshot["total"] == len(a_tasks)
    assert {item["id"] for item in snapshot["items"]} == {str(task.id) for task in a_tasks}
    assert "PROJECT_B_LATEST_SENTINEL_MUST_NOT_LEAK" not in {item["title"] for item in snapshot["items"]}
    assert {item["status"] for item in snapshot["items"]} == {status.value for status in TaskStatus}


def test_confirmation_boundary_read_only_and_protocol_parity(db):
    project_id = create_project(db, name="confirmation-boundary")
    create_tasks(db, project_id=project_id, count=1)
    confirmed_session_id, confirmed_message_id = create_session(
        db, project_id=project_id, status=ProjectDirectorSessionStatus.CONFIRMED,
    )
    before = {
        "projects": [(row.id, row.updated_at) for row in db.execute(select(ProjectTable)).scalars()],
        "tasks": [(row.id, row.updated_at) for row in db.execute(select(TaskTable)).scalars()],
        "sessions": [(row.id, row.updated_at) for row in db.execute(select(ProjectDirectorSessionTable)).scalars()],
        "messages": [(row.id, row.created_at) for row in db.execute(select(ProjectDirectorMessageTable)).scalars()],
    }
    confirmed = build_serialized(db, session_id=confirmed_session_id, message_id=confirmed_message_id, request_id="confirmed")
    after = {
        "projects": [(row.id, row.updated_at) for row in db.execute(select(ProjectTable)).scalars()],
        "tasks": [(row.id, row.updated_at) for row in db.execute(select(TaskTable)).scalars()],
        "sessions": [(row.id, row.updated_at) for row in db.execute(select(ProjectDirectorSessionTable)).scalars()],
        "messages": [(row.id, row.created_at) for row in db.execute(select(ProjectDirectorMessageTable)).scalars()],
    }

    facts = confirmed["authoritative_facts"]
    assert before == after
    assert {"project_snapshot", "task_snapshot", "session_status", "goal", "project_id", "goal_summary", "constraints", "confirmed_at"} <= set(facts)
    assert facts["task_snapshot"]["total"] == facts["project_snapshot"]["task_stats"]["total_tasks"]
    assert set(confirmed) == TOP_LEVEL_KEYS
    assert confirmed["schema_version"] == "p26-big-director-runtime/v1"

    for status in (
        ProjectDirectorSessionStatus.DRAFT,
        ProjectDirectorSessionStatus.CLARIFYING,
        ProjectDirectorSessionStatus.READY_TO_CONFIRM,
    ):
        session_id, message_id = create_session(db, project_id=project_id, status=status)
        unconfirmed = build_serialized(db, session_id=session_id, message_id=message_id, request_id=f"unconfirmed-{status.value}")
        assert set(unconfirmed["authoritative_facts"]) == {
            "project_snapshot",
            "task_snapshot",
            "repository_snapshot",
        }


def test_stale_project_total_before_coherent_read_fails_closed(db):
    project_id = create_project(db, name="stale-total")
    create_tasks(db, project_id=project_id, count=13)
    session_id, message_id = create_session(
        db,
        project_id=project_id,
        status=ProjectDirectorSessionStatus.CONFIRMED,
    )
    writer = sessionmaker(bind=db.get_bind(), expire_on_commit=False)()

    class DeleteBeforeCoherentRead:
        def __init__(self) -> None:
            self._delegate = TaskRepository(db)

        def list_recent_with_total_by_project_id(
            self, requested_project_id: UUID, *, limit: int
        ):
            task_id = writer.execute(
                select(TaskTable.id)
                .where(TaskTable.project_id == requested_project_id)
                .order_by(TaskTable.updated_at.asc(), TaskTable.created_at.asc())
                .limit(1)
            ).scalar_one()
            writer.execute(delete(TaskTable).where(TaskTable.id == task_id))
            writer.commit()
            return self._delegate.list_recent_with_total_by_project_id(
                requested_project_id,
                limit=limit,
            )

    try:
        with pytest.raises(
            DirectorRuntimeRequestAssemblerError,
            match="director_runtime_request_assembler_task_snapshot_inconsistent",
        ):
            DirectorRuntimeRequestAssemblerService(
                db_session=db,
                task_repository=DeleteBeforeCoherentRead(),
            ).build_request(
                session_id=session_id,
                message_id=message_id,
                runtime_config=CONFIG,
                request_id="stale-total",
            )
    finally:
        writer.close()
