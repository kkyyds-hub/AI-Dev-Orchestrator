from __future__ import annotations

import json
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.api.router import api_router
from app.core.db import get_db_session
from app.core.db_tables import ORMBase, ProjectDirectorMessageTable, RunTable, TaskTable


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


def _prepare_p12_safe_task(client: TestClient) -> tuple[str, dict, dict]:
    session_response = client.post(
        "/project-director/sessions",
        json={"goal_text": "P13-B controlled executor dispatch API"},
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["id"]

    p11_response = client.post(
        f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
        json={"user_goal": "P13-B create controlled executor pilot intent"},
    )
    assert p11_response.status_code == 200
    p11_message = p11_response.json()["message"]

    p12_response = client.post(
        f"/project-director/sessions/{session_id}/dry-run-task-dispatch",
        json={"source_message_id": p11_message["id"], "user_confirmed": True},
    )
    assert p12_response.status_code == 200
    return session_id, p11_message, p12_response.json()


def test_controlled_executor_dispatch_dry_run_plans_intent_and_message(
    tmp_path,
) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, _p11_message, p12_payload = _prepare_p12_safe_task(client)
        counts_before = {
            "tasks": _count_rows(session_factory, TaskTable),
            "runs": _count_rows(session_factory, RunTable),
            "messages": _count_rows(session_factory, ProjectDirectorMessageTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/controlled-executor-dispatch",
            json={
                "source_task_id": p12_payload["created_task_id"],
                "source_message_id": p12_payload["message"]["id"],
                "user_confirmed": True,
                "requested_agent_role": "programmer",
                "requested_executor": "codex",
                "launch_mode": "dry_run",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["dispatch_status"] == "planned"
        assert payload["session_id"] == session_id
        assert payload["source_task_id"] == p12_payload["created_task_id"]
        assert payload["source_message_id"] == p12_payload["message"]["id"]
        assert payload["requested_agent_role"] == "programmer"
        assert payload["requested_executor"] == "codex"
        assert payload["launch_mode"] == "dry_run"
        assert payload["controlled_executor_pilot"] is True
        assert payload["executor_backed_agent"] is True
        assert payload["programmer_agent_allowed"] is True
        assert payload["reviewer_agent_allowed"] is True
        assert payload["product_runtime_git_write_allowed"] is False
        assert payload["worktree_write_allowed"] is False
        assert payload["frontend_required"] is False
        assert payload["native_executor_started"] is False
        assert payload["codex_started"] is False
        assert payload["claude_code_started"] is False
        assert payload["agent_session_bound"] is False
        assert payload["supervisor_required"] is True
        assert payload["auto_terminate_required"] is True
        assert payload["cleanup_required"] is True
        assert payload["process_handle_id_present"] is False
        assert payload["supervisor_registered"] is False
        assert payload["supervisor_cleanup_done"] is False
        assert payload["run_created"] is False
        assert payload["message_bound"] is True
        assert payload["ai_project_director_total_loop"] == "Partial"
        assert payload["p9_production_safe_long_running_executor_lifecycle"] == "Partial"

        messages_response = client.get(
            f"/project-director/sessions/{session_id}/messages"
        )
        assert messages_response.status_code == 200
        messages = messages_response.json()["messages"]
        assert any(
            item["source_detail"] == "p13_controlled_executor_dispatch"
            and item["related_task_id"] == p12_payload["created_task_id"]
            for item in messages
        )

    assert _count_rows(session_factory, TaskTable) == counts_before["tasks"]
    assert _count_rows(session_factory, RunTable) == counts_before["runs"]
    assert (
        _count_rows(session_factory, ProjectDirectorMessageTable)
        == counts_before["messages"] + 1
    )

    forbidden_text = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in (
        "api_key",
        "token",
        "secret",
        "pid",
        "raw command",
        "raw stdout",
        "raw stderr",
        "已执行提交",
        "已推送",
        "pr 已创建",
        "代码已写入",
        "已授权 git 写",
        "已启动 codex",
        "已启动 claude",
    ):
        assert forbidden not in forbidden_text


def test_controlled_executor_dispatch_requires_user_confirmation(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, _p11_message, p12_payload = _prepare_p12_safe_task(client)
        before_runs = _count_rows(session_factory, RunTable)
        response = client.post(
            f"/project-director/sessions/{session_id}/controlled-executor-dispatch",
            json={
                "source_task_id": p12_payload["created_task_id"],
                "source_message_id": p12_payload["message"]["id"],
                "user_confirmed": False,
                "requested_agent_role": "reviewer",
                "requested_executor": "claude-code",
            },
        )

    assert response.status_code == 409
    assert "user_confirmation_required" in response.json()["detail"]
    assert _count_rows(session_factory, RunTable) == before_runs


def test_controlled_executor_dispatch_blocks_source_message_from_other_session(
    tmp_path,
) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        _session_id, _p11_message, p12_payload = _prepare_p12_safe_task(client)
        other_session_response = client.post(
            "/project-director/sessions",
            json={"goal_text": "P13-B other session"},
        )
        assert other_session_response.status_code == 201
        other_session_id = other_session_response.json()["id"]

        response = client.post(
            f"/project-director/sessions/{other_session_id}/controlled-executor-dispatch",
            json={
                "source_task_id": p12_payload["created_task_id"],
                "source_message_id": p12_payload["message"]["id"],
                "user_confirmed": True,
                "requested_agent_role": "programmer",
                "requested_executor": "codex",
            },
        )

    assert response.status_code == 409
    assert "source_message_not_in_session" in response.json()["detail"]


def test_controlled_executor_dispatch_blocks_non_safe_dry_run_task(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, _p11_message, p12_payload = _prepare_p12_safe_task(client)
        response = client.post(
            f"/project-director/sessions/{session_id}/controlled-executor-dispatch",
            json={
                "source_task_id": str(uuid4()),
                "source_message_id": p12_payload["message"]["id"],
                "user_confirmed": True,
                "requested_agent_role": "programmer",
                "requested_executor": "codex",
            },
        )

    assert response.status_code == 404
    assert "Task" in response.json()["detail"]


def test_controlled_executor_dispatch_blocks_controlled_smoke_in_api(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, _p11_message, p12_payload = _prepare_p12_safe_task(client)
        response = client.post(
            f"/project-director/sessions/{session_id}/controlled-executor-dispatch",
            json={
                "source_task_id": p12_payload["created_task_id"],
                "source_message_id": p12_payload["message"]["id"],
                "user_confirmed": True,
                "requested_agent_role": "programmer",
                "requested_executor": "codex",
                "launch_mode": "controlled_smoke",
            },
        )

    assert response.status_code == 409
    assert "controlled_smoke_not_enabled_in_api" in response.json()["detail"]


def test_controlled_executor_dispatch_rejects_invalid_role_or_executor(
    tmp_path,
) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, _p11_message, p12_payload = _prepare_p12_safe_task(client)
        invalid_role_response = client.post(
            f"/project-director/sessions/{session_id}/controlled-executor-dispatch",
            json={
                "source_task_id": p12_payload["created_task_id"],
                "source_message_id": p12_payload["message"]["id"],
                "user_confirmed": True,
                "requested_agent_role": "owner",
                "requested_executor": "codex",
            },
        )
        invalid_executor_response = client.post(
            f"/project-director/sessions/{session_id}/controlled-executor-dispatch",
            json={
                "source_task_id": p12_payload["created_task_id"],
                "source_message_id": p12_payload["message"]["id"],
                "user_confirmed": True,
                "requested_agent_role": "programmer",
                "requested_executor": "shell",
            },
        )

    assert invalid_role_response.status_code == 422
    assert invalid_executor_response.status_code == 422
