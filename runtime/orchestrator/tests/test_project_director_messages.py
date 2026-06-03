"""Tests for Stage 7-B1 Project Director message persistence foundation."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.router import api_router
from app.core.db import get_db_session
from app.core.db_tables import ORMBase
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


def _create_session(client: TestClient) -> str:
    resp = client.post(
        "/project-director/sessions",
        json={"goal_text": "为工作台增加 Project Director 对话历史"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


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
    assert data["user_message"]["sequence_no"] == 1
    assert data["assistant_message"]["role"] == "assistant"
    assert data["assistant_message"]["source"] == "rule_fallback"
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
    messages = resp.json()["messages"]
    assert [m["sequence_no"] for m in messages] == [1, 2, 3, 4]
    assert [m["role"] for m in messages] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert messages[0]["content"] == "第一条"
    assert messages[2]["content"] == "第二条"


def test_message_endpoints_return_404_for_missing_session(client):
    missing_session_id = uuid4()

    get_resp = client.get(f"/project-director/sessions/{missing_session_id}/messages")
    post_resp = client.post(
        f"/project-director/sessions/{missing_session_id}/messages",
        json={"content": "hello"},
    )

    assert get_resp.status_code == 404
    assert post_resp.status_code == 404
