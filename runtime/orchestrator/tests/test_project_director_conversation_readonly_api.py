"""P7-C1 Project Director ConversationList read-only API tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.router import api_router
from app.core.db import get_db_session
from app.core.db_tables import (
    ORMBase,
    ProjectDirectorMessageTable,
    ProjectDirectorSessionTable,
)
from app.domain.project import Project
from app.domain.project_director_message import (
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_session import (
    ProjectDirectorSession,
    ProjectDirectorSessionStatus,
)
from app.domain.project_director_plan_version import (
    PlanVersionStatus,
    ProjectDirectorPlanVersion,
)
from app.domain.project_director_task_creation import (
    ProjectDirectorTaskCreationRecord,
)
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.project_director_task_creation_repository import (
    ProjectDirectorTaskCreationRecordRepository,
)
from app.repositories.project_repository import ProjectRepository


@pytest.fixture()
def sqlite_session_factory(tmp_path):
    db_path = tmp_path / "orchestrator-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


@pytest.fixture()
def client(sqlite_session_factory):
    app = FastAPI()
    app.include_router(api_router)

    def override_get_db_session():
        session = sqlite_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def db_session(sqlite_session_factory):
    session = sqlite_session_factory()
    try:
        yield session
    finally:
        session.close()


def _count_rows(db_session: Session, table) -> int:
    return db_session.execute(select(func.count()).select_from(table)).scalar_one()


def _seed_session(
    db_session: Session,
    *,
    goal_text: str,
    project_id: UUID | None = None,
    updated_at: datetime,
    status: ProjectDirectorSessionStatus = ProjectDirectorSessionStatus.CLARIFYING,
) -> ProjectDirectorSession:
    return ProjectDirectorSessionRepository(db_session).create(
        ProjectDirectorSession(
            project_id=project_id,
            goal_text=goal_text,
            status=status,
            created_at=updated_at,
            updated_at=updated_at,
        )
    )


def _seed_message(
    db_session: Session,
    *,
    session_id: UUID,
    role: ProjectDirectorMessageRole,
    content: str,
    sequence_no: int,
    created_at: datetime,
    requires_confirmation: bool = False,
) -> None:
    db_session.add(
        ProjectDirectorMessageTable(
            session_id=session_id,
            role=role,
            content=content,
            sequence_no=sequence_no,
            source=ProjectDirectorMessageSource.RULE_FALLBACK,
            source_detail="test_seed",
            suggested_actions_json="[]",
            requires_confirmation=requires_confirmation,
            forbidden_actions_detected_json="[]",
            created_at=created_at,
        )
    )
    db_session.commit()


def _seed_plan_version(
    db_session: Session,
    *,
    session_id: UUID,
    project_id: UUID | None = None,
    version_no: int = 1,
    status: PlanVersionStatus = PlanVersionStatus.PENDING_CONFIRMATION,
    created_at: datetime,
) -> ProjectDirectorPlanVersion:
    return ProjectDirectorPlanVersionRepository(db_session).create(
        ProjectDirectorPlanVersion(
            session_id=session_id,
            project_id=project_id,
            version_no=version_no,
            status=status,
            plan_summary="测试计划草案",
            created_at=created_at,
            updated_at=created_at,
        )
    )


def _seed_task_creation(
    db_session: Session,
    *,
    plan_version: ProjectDirectorPlanVersion,
    project_id: UUID,
    created_at: datetime,
) -> ProjectDirectorTaskCreationRecord:
    return ProjectDirectorTaskCreationRecordRepository(db_session).create(
        ProjectDirectorTaskCreationRecord(
            plan_version_id=plan_version.id,
            session_id=plan_version.session_id,
            project_id=project_id,
            version_no=plan_version.version_no,
            task_ids=[uuid4()],
            task_count=1,
            created_at=created_at,
        )
    )


def test_conversation_list_default_sort_by_last_message_desc(
    client: TestClient,
    db_session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    older = _seed_session(
        db_session,
        goal_text="较早的主管会话",
        updated_at=now - timedelta(hours=4),
    )
    newer = _seed_session(
        db_session,
        goal_text="较新的主管会话",
        updated_at=now - timedelta(hours=4),
    )
    _seed_message(
        db_session,
        session_id=older.id,
        role=ProjectDirectorMessageRole.USER,
        content="旧消息",
        sequence_no=1,
        created_at=now - timedelta(hours=2),
    )
    _seed_message(
        db_session,
        session_id=newer.id,
        role=ProjectDirectorMessageRole.USER,
        content="新消息",
        sequence_no=1,
        created_at=now - timedelta(minutes=5),
    )

    resp = client.get("/project-director/conversations")

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_more"] is False
    assert [item["conversation_id"] for item in data["conversations"]] == [
        str(newer.id),
        str(older.id),
    ]
    assert data["conversations"][0]["last_message_preview"] == "新消息"
    assert data["conversations"][0]["message_count"] == 1
    assert data["conversations"][0]["kind"] == "project_onboarding"


def test_conversation_list_sort_uses_last_message_before_session_update(
    client: TestClient,
    db_session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    recently_updated_session = _seed_session(
        db_session,
        goal_text="session 更新较新但消息较旧",
        updated_at=now,
    )
    recently_messaged_session = _seed_session(
        db_session,
        goal_text="session 更新较旧但消息较新",
        updated_at=now - timedelta(hours=6),
    )
    _seed_message(
        db_session,
        session_id=recently_updated_session.id,
        role=ProjectDirectorMessageRole.USER,
        content="较旧消息",
        sequence_no=1,
        created_at=now - timedelta(hours=2),
    )
    _seed_message(
        db_session,
        session_id=recently_messaged_session.id,
        role=ProjectDirectorMessageRole.USER,
        content="较新消息",
        sequence_no=1,
        created_at=now - timedelta(minutes=5),
    )

    resp = client.get("/project-director/conversations")

    assert resp.status_code == 200
    assert resp.json()["conversations"][0]["conversation_id"] == str(
        recently_messaged_session.id
    )


def test_conversation_list_before_cursor_paginates_without_writes(
    client: TestClient,
    db_session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    newest = _seed_session(
        db_session,
        goal_text="最新会话",
        updated_at=now - timedelta(hours=4),
    )
    middle = _seed_session(
        db_session,
        goal_text="中间会话",
        updated_at=now - timedelta(hours=4),
    )
    oldest = _seed_session(
        db_session,
        goal_text="最旧会话",
        updated_at=now - timedelta(hours=4),
    )
    for session_obj, minutes_ago in (
        (newest, 5),
        (middle, 15),
        (oldest, 30),
    ):
        _seed_message(
            db_session,
            session_id=session_obj.id,
            role=ProjectDirectorMessageRole.USER,
            content=session_obj.goal_text,
            sequence_no=1,
            created_at=now - timedelta(minutes=minutes_ago),
        )
    session_count_before = _count_rows(db_session, ProjectDirectorSessionTable)
    message_count_before = _count_rows(db_session, ProjectDirectorMessageTable)

    first_page = client.get("/project-director/conversations?limit=2")
    cursor = first_page.json()["conversations"][1]["conversation_id"]
    second_page = client.get(f"/project-director/conversations?limit=2&before={cursor}")

    assert first_page.status_code == 200
    assert first_page.json()["has_more"] is True
    assert [item["conversation_id"] for item in first_page.json()["conversations"]] == [
        str(newest.id),
        str(middle.id),
    ]
    assert second_page.status_code == 200
    assert second_page.json()["has_more"] is False
    assert [item["conversation_id"] for item in second_page.json()["conversations"]] == [
        str(oldest.id),
    ]
    assert _count_rows(db_session, ProjectDirectorSessionTable) == session_count_before
    assert _count_rows(db_session, ProjectDirectorMessageTable) == message_count_before


def test_conversation_list_unknown_before_cursor_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    _seed_session(
        db_session,
        goal_text="已有会话",
        updated_at=now,
    )

    resp = client.get(
        "/project-director/conversations?before=00000000-0000-0000-0000-000000000000"
    )

    assert resp.status_code == 422
    assert "cursor" in resp.json()["detail"]


def test_conversation_list_limit_is_capped_at_100(
    client: TestClient,
    db_session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    for index in range(105):
        session_obj = _seed_session(
            db_session,
            goal_text=f"批量会话 {index:03d}",
            updated_at=now - timedelta(hours=8),
        )
        _seed_message(
            db_session,
            session_id=session_obj.id,
            role=ProjectDirectorMessageRole.USER,
            content=f"消息 {index:03d}",
            sequence_no=1,
            created_at=now - timedelta(minutes=index),
        )

    resp = client.get("/project-director/conversations?limit=500")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["conversations"]) == 100
    assert data["has_more"] is True


def test_conversation_list_kind_is_plan_review_when_latest_plan_exists(
    client: TestClient,
    db_session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    session_obj = _seed_session(
        db_session,
        goal_text="计划审核会话",
        updated_at=now - timedelta(hours=1),
    )
    _seed_plan_version(
        db_session,
        session_id=session_obj.id,
        created_at=now - timedelta(minutes=20),
    )

    resp = client.get("/project-director/conversations?kind=plan_review")

    assert resp.status_code == 200
    conversations = resp.json()["conversations"]
    assert len(conversations) == 1
    assert conversations[0]["conversation_id"] == str(session_obj.id)
    assert conversations[0]["kind"] == "plan_review"


def test_conversation_list_kind_is_follow_up_when_task_creation_exists(
    client: TestClient,
    db_session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    project = ProjectRepository(db_session).create(
        Project(name="Follow-up 项目", summary="kind inference")
    )
    session_obj = _seed_session(
        db_session,
        goal_text="任务创建后的跟进会话",
        project_id=project.id,
        updated_at=now - timedelta(hours=1),
        status=ProjectDirectorSessionStatus.CONFIRMED,
    )
    plan_version = _seed_plan_version(
        db_session,
        session_id=session_obj.id,
        project_id=project.id,
        status=PlanVersionStatus.CONFIRMED,
        created_at=now - timedelta(minutes=20),
    )
    _seed_task_creation(
        db_session,
        plan_version=plan_version,
        project_id=project.id,
        created_at=now - timedelta(minutes=10),
    )

    resp = client.get("/project-director/conversations?kind=follow_up")

    assert resp.status_code == 200
    conversations = resp.json()["conversations"]
    assert len(conversations) == 1
    assert conversations[0]["conversation_id"] == str(session_obj.id)
    assert conversations[0]["kind"] == "follow_up"


def test_conversation_list_project_and_awaiting_user_filters(
    client: TestClient,
    db_session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    project = ProjectRepository(db_session).create(
        Project(name="P7-C1 测试项目", summary="ConversationList filter")
    )
    awaiting = _seed_session(
        db_session,
        goal_text="需要用户确认的会话",
        project_id=project.id,
        updated_at=now - timedelta(hours=1),
    )
    other = _seed_session(
        db_session,
        goal_text="其他项目外会话",
        updated_at=now - timedelta(hours=1),
    )
    _seed_message(
        db_session,
        session_id=awaiting.id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="请确认是否继续。",
        sequence_no=1,
        created_at=now - timedelta(minutes=10),
        requires_confirmation=True,
    )
    _seed_message(
        db_session,
        session_id=other.id,
        role=ProjectDirectorMessageRole.USER,
        content="普通消息",
        sequence_no=1,
        created_at=now - timedelta(minutes=5),
    )

    resp = client.get(
        f"/project-director/conversations?project_id={project.id}&status=awaiting_user"
    )

    assert resp.status_code == 200
    conversations = resp.json()["conversations"]
    assert len(conversations) == 1
    assert conversations[0]["conversation_id"] == str(awaiting.id)
    assert conversations[0]["requires_user_action"] is True
    assert conversations[0]["owner_scope"] == "project"


def test_conversation_restore_does_not_create_session_or_messages(
    client: TestClient,
    db_session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    session_obj = _seed_session(
        db_session,
        goal_text="恢复已有主管会话",
        updated_at=now - timedelta(hours=1),
    )
    _seed_message(
        db_session,
        session_id=session_obj.id,
        role=ProjectDirectorMessageRole.USER,
        content="请恢复这条会话。",
        sequence_no=1,
        created_at=now - timedelta(minutes=20),
    )
    session_count_before = _count_rows(db_session, ProjectDirectorSessionTable)
    message_count_before = _count_rows(db_session, ProjectDirectorMessageTable)

    resp = client.get(f"/project-director/conversations/{session_obj.id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["conversation"]["conversation_id"] == str(session_obj.id)
    assert data["session"]["id"] == str(session_obj.id)
    assert data["recent_messages"][0]["content"] == "请恢复这条会话。"
    assert _count_rows(db_session, ProjectDirectorSessionTable) == session_count_before
    assert _count_rows(db_session, ProjectDirectorMessageTable) == message_count_before


def test_conversation_with_mismatched_project_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    project = ProjectRepository(db_session).create(
        Project(name="真实所属项目", summary="owner")
    )
    other_project = ProjectRepository(db_session).create(
        Project(name="错误请求项目", summary="other")
    )
    session_obj = _seed_session(
        db_session,
        goal_text="带项目归属的会话",
        project_id=project.id,
        updated_at=now,
    )

    resp = client.get(
        f"/project-director/conversations/{session_obj.id}?project_id={other_project.id}"
    )

    assert resp.status_code == 422
    assert "does not match" in resp.json()["detail"]


def test_conversation_timeline_is_read_only_message_replay(
    client: TestClient,
    db_session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    session_obj = _seed_session(
        db_session,
        goal_text="读取时间线",
        updated_at=now - timedelta(hours=1),
    )
    _seed_message(
        db_session,
        session_id=session_obj.id,
        role=ProjectDirectorMessageRole.USER,
        content="第一条消息",
        sequence_no=1,
        created_at=now - timedelta(minutes=25),
    )
    _seed_message(
        db_session,
        session_id=session_obj.id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="第二条回复",
        sequence_no=2,
        created_at=now - timedelta(minutes=20),
    )
    message_count_before = _count_rows(db_session, ProjectDirectorMessageTable)

    resp = client.get(f"/project-director/conversations/{session_obj.id}/timeline")

    assert resp.status_code == 200
    data = resp.json()
    assert data["conversation_id"] == str(session_obj.id)
    assert [item["kind"] for item in data["items"]] == ["message", "message"]
    assert "第一条消息" in data["items"][0]["summary_cn"]
    assert _count_rows(db_session, ProjectDirectorMessageTable) == message_count_before


def test_conversation_post_endpoint_not_implemented_for_p7_c1_readonly_scope(
    client: TestClient,
    db_session: Session,
) -> None:
    session_count_before = _count_rows(db_session, ProjectDirectorSessionTable)

    resp = client.post(
        "/project-director/conversations",
        json={"kind": "general_discussion", "goal_text": "不要在本轮创建"},
    )

    assert resp.status_code == 405
    assert _count_rows(db_session, ProjectDirectorSessionTable) == session_count_before
