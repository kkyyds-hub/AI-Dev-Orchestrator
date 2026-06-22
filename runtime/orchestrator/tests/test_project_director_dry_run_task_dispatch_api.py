from __future__ import annotations

import json
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.api.router import api_router
from app.core.db import get_db_session
from app.core.db_tables import ORMBase, RunTable, TaskTable


def _sqlite_session_factory(tmp_path):
    db_path = tmp_path / "orchestrator-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


def _app(sqlite_session_factory) -> FastAPI:
    app = FastAPI()
    app.include_router(api_router)

    def override_get_db_session():
        session = sqlite_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session
    return app


def _count_rows(sqlite_session_factory, table) -> int:
    session = sqlite_session_factory()
    try:
        return session.execute(select(func.count()).select_from(table)).scalar_one()
    finally:
        session.close()


def _create_session_and_p11_message(client: TestClient) -> tuple[str, dict]:
    session_response = client.post(
        "/project-director/sessions",
        json={"goal_text": "P12-B confirmed dry-run task dispatch API"},
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["id"]

    dry_run_response = client.post(
        f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
        json={"user_goal": "P12-B create safe dry-run task from P11 message"},
    )
    assert dry_run_response.status_code == 200
    return session_id, dry_run_response.json()["message"]


def test_confirmed_dispatch_creates_safe_dry_run_task_and_message(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, source_message = _create_session_and_p11_message(client)
        counts_before = {
            "tasks": _count_rows(session_factory, TaskTable),
            "runs": _count_rows(session_factory, RunTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/dry-run-task-dispatch",
            json={
                "source_message_id": source_message["id"],
                "user_confirmed": True,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        created_task_id = payload["created_task_id"]
        assert payload["dispatch_status"] == "dispatched"
        assert payload["session_id"] == session_id
        assert payload["source_message_id"] == source_message["id"]
        assert created_task_id
        assert payload["evidence_pack_id"]
        assert payload["safe_dry_run_task"] is True
        assert payload["worker_simulate_required"] is True
        assert payload["product_runtime_git_write_allowed"] is False
        assert payload["frontend_required"] is False
        assert payload["native_executor_started"] is False
        assert payload["codex_started"] is False
        assert payload["claude_code_started"] is False
        assert payload["worker_started"] is False
        assert payload["ai_project_director_total_loop"] == "Partial"
        assert payload["message_bound"] is True
        assert payload["message"]["source_detail"] == "p12_dry_run_task_dispatch"
        assert payload["message"]["related_task_id"] == created_task_id

        task_response = client.get(f"/tasks/{created_task_id}")
        assert task_response.status_code == 200
        task = task_response.json()
        assert "Safe dry-run task dispatch" in task["title"]
        assert "SAFE DRY-RUN TASK DISPATCH ONLY" in task["input_summary"]
        assert f"source_message_id={source_message['id']}" in task["input_summary"]
        assert "product_runtime_git_write_allowed=false" in task["input_summary"]
        assert "codex_started=false" in task["input_summary"]
        assert "claude_code_started=false" in task["input_summary"]
        assert task["source_draft_id"] == f"p12-{source_message['id']}"
        assert task["status"] == "pending"
        assert task["risk_level"] == "low"

        runs_response = client.get(f"/tasks/{created_task_id}/runs")
        assert runs_response.status_code == 200
        assert runs_response.json() == []

        messages_response = client.get(
            f"/project-director/sessions/{session_id}/messages"
        )
        assert messages_response.status_code == 200
        messages = messages_response.json()["messages"]
        assert any(
            item["source_detail"] == "p11_evidence_to_agent_session_dry_run"
            for item in messages
        )
        assert any(
            item["source_detail"] == "p12_dry_run_task_dispatch"
            and item["related_task_id"] == created_task_id
            for item in messages
        )

    assert _count_rows(session_factory, TaskTable) == counts_before["tasks"] + 1
    assert _count_rows(session_factory, RunTable) == counts_before["runs"]

    forbidden_text = json.dumps(payload, ensure_ascii=False)
    for phrase in (
        "已执行提交",
        "已推送",
        "PR 已创建",
        "代码已写入",
        "已授权 Git 写",
        "已启动 Codex",
        "已启动 Claude",
    ):
        assert phrase not in forbidden_text


def test_dispatch_requires_user_confirmation(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, source_message = _create_session_and_p11_message(client)
        before_tasks = _count_rows(session_factory, TaskTable)
        response = client.post(
            f"/project-director/sessions/{session_id}/dry-run-task-dispatch",
            json={
                "source_message_id": source_message["id"],
                "user_confirmed": False,
            },
        )

    assert response.status_code == 409
    assert "user_confirmation_required" in response.json()["detail"]
    assert _count_rows(session_factory, TaskTable) == before_tasks


def test_dispatch_blocks_source_message_from_other_session(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        _source_session_id, source_message = _create_session_and_p11_message(client)
        other_session_response = client.post(
            "/project-director/sessions",
            json={"goal_text": "P12-B other session"},
        )
        assert other_session_response.status_code == 201
        other_session_id = other_session_response.json()["id"]
        before_tasks = _count_rows(session_factory, TaskTable)

        response = client.post(
            f"/project-director/sessions/{other_session_id}/dry-run-task-dispatch",
            json={
                "source_message_id": source_message["id"],
                "user_confirmed": True,
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "source_message_not_in_session"
    assert _count_rows(session_factory, TaskTable) == before_tasks


def test_dispatch_returns_404_for_missing_source_message(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_response = client.post(
            "/project-director/sessions",
            json={"goal_text": "P12-B missing source message"},
        )
        assert session_response.status_code == 201
        session_id = session_response.json()["id"]
        response = client.post(
            f"/project-director/sessions/{session_id}/dry-run-task-dispatch",
            json={"source_message_id": str(uuid4()), "user_confirmed": True},
        )

    assert response.status_code == 404
