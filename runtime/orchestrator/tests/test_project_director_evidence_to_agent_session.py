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
from app.domain.project_director_session import (
    ProjectDirectorSession,
    ProjectDirectorSessionStatus,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)


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


def _seed_session(sqlite_session_factory) -> str:
    session = sqlite_session_factory()
    try:
        seeded = ProjectDirectorSessionRepository(session).create(
            ProjectDirectorSession(
                goal_text="P11-B evidence-to-agent session dry-run",
                status=ProjectDirectorSessionStatus.CLARIFYING,
                goal_summary="P11-B dry-run session",
            )
        )
        return str(seeded.id)
    finally:
        session.close()


def _count_rows(sqlite_session_factory, table) -> int:
    session = sqlite_session_factory()
    try:
        return session.execute(select(func.count()).select_from(table)).scalar_one()
    finally:
        session.close()


def test_session_dry_run_binds_safe_message_readback(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)
    session_id = _seed_session(session_factory)
    counts_before = {
        "tasks": _count_rows(session_factory, TaskTable),
        "runs": _count_rows(session_factory, RunTable),
    }

    with TestClient(app) as client:
        response = client.post(
            f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
            json={"user_goal": "P11-B bind dry-run result to session readback"},
        )
        messages_response = client.get(f"/project-director/sessions/{session_id}/messages")

    assert response.status_code == 200
    payload = response.json()
    summary = payload["dry_run_summary"]
    message = payload["message"]
    assert summary["dry_run_status"] == "passed"
    assert summary["product_runtime_git_write_allowed"] is False
    assert summary["frontend_required"] is False
    assert summary["ai_project_director_total_loop"] == "Partial"
    assert summary["real_task_created"] is False
    assert summary["worker_started"] is False
    assert message["source_detail"] == "p11_evidence_to_agent_session_dry_run"
    assert message["role"] == "assistant"
    assert "不代表执行完成" in message["content"]
    assert "产品运行时 Git 写仍未开放" in message["content"]
    assert "Partial" in message["content"]

    action = message["suggested_actions"][0]
    assert action["evidence_pack_id"] == summary["evidence_pack_id"]
    assert action["dry_run_status"] == "passed"
    assert action["composed_tasks_count"] == summary["composed_tasks_count"]
    assert action["programmer_assignment_created"] is True
    assert action["reviewer_assignment_created"] is True
    assert action["product_runtime_git_write_allowed"] is False
    assert action["frontend_required"] is False
    assert action["ai_project_director_total_loop"] == "Partial"

    assert messages_response.status_code == 200
    messages = messages_response.json()["messages"]
    assert len(messages) == 1
    assert messages[0]["id"] == message["id"]
    assert messages[0]["source_detail"] == "p11_evidence_to_agent_session_dry_run"

    forbidden_text = json.dumps(payload, ensure_ascii=False)
    for phrase in (
        "已执行提交",
        "已推送",
        "PR 已创建",
        "任务已完成",
        "代码已写入",
        "已授权 Git 写",
        "已启动 Codex",
        "已启动 Claude",
    ):
        assert phrase not in forbidden_text

    assert _count_rows(session_factory, TaskTable) == counts_before["tasks"]
    assert _count_rows(session_factory, RunTable) == counts_before["runs"]


def test_session_dry_run_returns_404_for_missing_session(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        response = client.post(
            f"/project-director/sessions/{uuid4()}/evidence-to-agent/dry-run",
            json={"user_goal": "missing session"},
        )

    assert response.status_code == 404
