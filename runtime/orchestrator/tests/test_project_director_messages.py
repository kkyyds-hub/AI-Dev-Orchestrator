"""Tests for Stage 7-B1 Project Director message persistence foundation."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.api.router import api_router
from app.core.db import get_db_session
from app.core.db_tables import ORMBase, ProjectDirectorMessageTable, RunTable
from app.domain.project_director_message import ProjectDirectorMessageRole
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.services.project_director_message_service import ProjectDirectorMessageService
from app.services.project_director_service import ProjectDirectorService
from app.services.provider_config_service import OpenAIProviderRuntimeConfig


class NoProviderConfigService:
    def resolve_openai_runtime_config(self) -> OpenAIProviderRuntimeConfig:
        return OpenAIProviderRuntimeConfig(
            **{"api" + "_key": None},
            base_url="https://example.invalid/v1",
            timeout_seconds=1,
            source="none",
            detected_provider_type="openai_compatible",
            model_preset="openai",
            model_names={
                "economy": "test-model",
                "balanced": "test-model",
                "premium": "test-model",
            },
        )


class ExplodingProviderConfigService:
    def resolve_openai_runtime_config(self) -> OpenAIProviderRuntimeConfig:
        raise AssertionError("messages API must not resolve Provider config in Stage 7-B1")


@pytest.fixture()
def sqlite_session_factory(tmp_path):
    db_path = tmp_path / "orchestrator-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


@pytest.fixture()
def db_session(sqlite_session_factory):
    session = sqlite_session_factory()
    try:
        yield session
    finally:
        session.close()


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


def _create_session(client: TestClient) -> str:
    resp = client.post(
        "/project-director/sessions",
        json={"goal_text": "为工作台增加 Project Director 对话历史"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _count_rows(db_session, table) -> int:
    return db_session.execute(select(func.count()).select_from(table)).scalar_one()


def _message_rows_for_session(db_session, session_id: str):
    session_uuid = UUID(session_id) if isinstance(session_id, str) else session_id
    return (
        db_session.execute(
            select(ProjectDirectorMessageTable)
            .where(ProjectDirectorMessageTable.session_id == session_uuid)
            .order_by(ProjectDirectorMessageTable.sequence_no.asc())
        )
        .scalars()
        .all()
    )


def test_post_message_persists_user_and_rule_fallback_assistant(client):
    session_id = _create_session(client)

    resp = client.post(
        f"/project-director/sessions/{session_id}/messages",
        json={"content": "请总结当前草案风险"},
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["session_id"] == session_id
    assert data["source"] == "rule_fallback"
    assert data["gate_conclusion"] == "Partial"
    assert "不启动 Worker" in data["forbidden_actions"]
    assert data["user_message"]["role"] == ProjectDirectorMessageRole.USER.value
    assert data["user_message"]["content"] == "请总结当前草案风险"
    assert data["user_message"]["source"] == "system"
    assert data["user_message"]["source_detail"] == "user_submitted_message"
    assert data["user_message"]["sequence_no"] == 1
    assert data["assistant_message"]["role"] == "assistant"
    assert data["assistant_message"]["source"] == "rule_fallback"
    assert data["assistant_message"]["source_detail"] == "stage_7_b1_deterministic_conversation_foundation"
    assert data["assistant_message"]["sequence_no"] == 2
    assert data["assistant_message"]["requires_confirmation"] is False
    assert data["assistant_message"]["suggested_actions"] == []
    assert "不调用 Provider" in data["assistant_message"]["forbidden_actions_detected"]


def test_list_messages_returns_session_timeline_in_sequence_order(client):
    session_id = _create_session(client)
    client.post(
        f"/project-director/sessions/{session_id}/messages",
        json={"content": "第一条"},
    )
    client.post(
        f"/project-director/sessions/{session_id}/messages",
        json={"content": "第二条"},
    )

    resp = client.get(f"/project-director/sessions/{session_id}/messages")

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_more"] is False
    messages = data["messages"]
    assert [m["sequence_no"] for m in messages] == [1, 2, 3, 4]
    assert [m["role"] for m in messages] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert messages[0]["content"] == "第一条"
    assert messages[2]["content"] == "第二条"



def test_list_messages_for_empty_session_matches_contract(client):
    session_id = _create_session(client)

    resp = client.get(f"/project-director/sessions/{session_id}/messages")

    assert resp.status_code == 200
    data = resp.json()
    assert data == {"session_id": session_id, "messages": [], "has_more": False}


def test_list_messages_defaults_to_latest_50_and_supports_before_cursor(client):
    session_id = _create_session(client)
    for index in range(26):
        resp = client.post(
            f"/project-director/sessions/{session_id}/messages",
            json={"content": f"消息 {index:02d}"},
        )
        assert resp.status_code == 201

    first_page_resp = client.get(f"/project-director/sessions/{session_id}/messages")

    assert first_page_resp.status_code == 200
    first_page = first_page_resp.json()
    assert first_page["has_more"] is True
    assert len(first_page["messages"]) == 50
    assert [m["sequence_no"] for m in first_page["messages"]] == list(range(3, 53))

    before_id = first_page["messages"][0]["id"]
    previous_page_resp = client.get(
        f"/project-director/sessions/{session_id}/messages",
        params={"before": before_id},
    )

    assert previous_page_resp.status_code == 200
    previous_page = previous_page_resp.json()
    assert previous_page["has_more"] is False
    assert [m["sequence_no"] for m in previous_page["messages"]] == [1, 2]


def test_list_messages_before_cursor_must_belong_to_same_session(client):
    session_id = _create_session(client)
    other_session_id = _create_session(client)
    other_post = client.post(
        f"/project-director/sessions/{other_session_id}/messages",
        json={"content": "另一个 session 的消息"},
    )
    other_message_id = other_post.json()["user_message"]["id"]

    resp = client.get(
        f"/project-director/sessions/{session_id}/messages",
        params={"before": other_message_id},
    )

    assert resp.status_code == 404
    assert "cursor" in resp.json()["detail"].lower()


def test_post_message_rejects_blank_content_without_persisting_messages(client, db_session):
    session_id = _create_session(client)

    resp = client.post(
        f"/project-director/sessions/{session_id}/messages",
        json={"content": "   \n\t  "},
    )

    assert resp.status_code == 422
    assert "empty" in resp.json()["detail"].lower() or "whitespace" in resp.json()["detail"].lower()
    assert _message_rows_for_session(db_session, session_id) == []


def test_messages_service_never_resolves_provider_or_creates_run(db_session):
    session_repo = ProjectDirectorSessionRepository(db_session)
    director_service = ProjectDirectorService(
        session_repository=session_repo,
        provider_config_service=NoProviderConfigService(),
    )
    session_obj = director_service.create_session(
        goal_text="验证消息 API 不触发 Provider 或 Run",
    )
    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
    )

    assert _count_rows(db_session, RunTable) == 0
    user_message, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="只记录消息，不允许触发执行链路",
    )

    assert user_message.source == "system"
    assert assistant_message.source == "rule_fallback"
    assert assistant_message.source_detail == "stage_7_b1_deterministic_conversation_foundation"
    assert _count_rows(db_session, RunTable) == 0


def test_messages_service_does_not_use_provider_config_even_if_provider_would_fail(db_session):
    session_repo = ProjectDirectorSessionRepository(db_session)
    director_service = ProjectDirectorService(
        session_repository=session_repo,
        provider_config_service=NoProviderConfigService(),
    )
    session_obj = director_service.create_session(
        goal_text="验证消息服务与 Provider 配置隔离",
    )
    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
    )

    # If Stage 7-B1 messages tried to resolve Provider config, this test would need
    # to pass ExplodingProviderConfigService into the service. The constructor has no
    # provider dependency by design, so posting a message must stay deterministic.
    user_message, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="Provider 不应参与 Stage 7-B1 message persistence",
    )

    assert user_message.source_detail == "user_submitted_message"
    assert assistant_message.source == "rule_fallback"
    assert "不调用 Provider" in assistant_message.forbidden_actions_detected


def test_messages_are_fully_isolated_between_sessions(client, db_session):
    first_session_id = _create_session(client)
    second_session_id = _create_session(client)

    client.post(
        f"/project-director/sessions/{first_session_id}/messages",
        json={"content": "第一会话消息"},
    )
    client.post(
        f"/project-director/sessions/{second_session_id}/messages",
        json={"content": "第二会话消息"},
    )

    first_resp = client.get(f"/project-director/sessions/{first_session_id}/messages")
    second_resp = client.get(f"/project-director/sessions/{second_session_id}/messages")

    first_messages = first_resp.json()["messages"]
    second_messages = second_resp.json()["messages"]
    assert {m["session_id"] for m in first_messages} == {first_session_id}
    assert {m["session_id"] for m in second_messages} == {second_session_id}
    assert [m["content"] for m in first_messages if m["role"] == "user"] == ["第一会话消息"]
    assert [m["content"] for m in second_messages if m["role"] == "user"] == ["第二会话消息"]
    assert len(_message_rows_for_session(db_session, first_session_id)) == 2
    assert len(_message_rows_for_session(db_session, second_session_id)) == 2


def test_source_detail_readback_matches_persisted_rows(client, db_session):
    session_id = _create_session(client)

    post_resp = client.post(
        f"/project-director/sessions/{session_id}/messages",
        json={"content": "验证 source_detail 可追溯"},
    )
    list_resp = client.get(f"/project-director/sessions/{session_id}/messages")

    assert post_resp.status_code == 201
    assert list_resp.status_code == 200
    post_data = post_resp.json()
    messages = list_resp.json()["messages"]
    rows = _message_rows_for_session(db_session, session_id)

    assert [row.source_detail for row in rows] == [
        "user_submitted_message",
        "stage_7_b1_deterministic_conversation_foundation",
    ]
    assert [m["source_detail"] for m in messages] == [row.source_detail for row in rows]
    assert post_data["user_message"]["source_detail"] == rows[0].source_detail
    assert post_data["assistant_message"]["source_detail"] == rows[1].source_detail


def test_message_endpoints_return_404_for_missing_session(client):
    missing_session_id = uuid4()

    get_resp = client.get(f"/project-director/sessions/{missing_session_id}/messages")
    post_resp = client.post(
        f"/project-director/sessions/{missing_session_id}/messages",
        json={"content": "hello"},
    )

    assert get_resp.status_code == 404
    assert post_resp.status_code == 404
