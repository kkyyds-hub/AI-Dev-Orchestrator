from __future__ import annotations

import json
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.api.router import api_router
from app.core.db import get_db_session
from app.core.db_tables import ORMBase, ProjectDirectorMessageTable, RunTable, TaskTable
from app.domain.project_director_controlled_executor_dispatch import (
    ProjectDirectorControlledExecutorLifecycleResult,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_controlled_executor_dispatch_service import (
    P14_LIFECYCLE_RESULT_SOURCE_DETAIL,
    ProjectDirectorControlledExecutorDispatchService,
)


FORBIDDEN_OUTPUT_KEYS = {
    "api_key",
    "token",
    "secret",
    "pid",
    "raw command",
    "raw stdout",
    "raw stderr",
}


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


def _record_p14_lifecycle_message(
    sqlite_session_factory,
    *,
    session_id: str,
    source_task_id: str,
    source_message_id: str,
    requested_executor: str = "codex",
) -> str:
    db_session = sqlite_session_factory()
    try:
        service = ProjectDirectorControlledExecutorDispatchService(
            session_repository=ProjectDirectorSessionRepository(db_session),
            message_repository=ProjectDirectorMessageRepository(db_session),
            task_repository=TaskRepository(db_session),
        )
        message = service.record_lifecycle_result(
            result=ProjectDirectorControlledExecutorLifecycleResult(
                session_id=UUID(session_id),
                source_task_id=UUID(source_task_id),
                source_message_id=UUID(source_message_id),
                requested_agent_role="reviewer",
                requested_executor=requested_executor,  # type: ignore[arg-type]
                launch_mode="dry_run",
                product_runtime_git_write_allowed=False,
                worktree_write_allowed=False,
                frontend_required=False,
                run_created=True,
                real_code_modified=False,
                git_write_performed=False,
                ai_project_director_total_loop="Partial",
            ),
            source_detail=P14_LIFECYCLE_RESULT_SOURCE_DETAIL,
        )
        return str(message.id)
    finally:
        db_session.close()


def _prepare_p14_review_source(
    client: TestClient,
    sqlite_session_factory,
) -> tuple[str, dict, str]:
    session_response = client.post(
        "/project-director/sessions",
        json={"goal_text": "P15 readonly reviewer API"},
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["id"]

    p11_response = client.post(
        f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
        json={"user_goal": "P15 readonly reviewer source evidence"},
    )
    assert p11_response.status_code == 200
    p11_message = p11_response.json()["message"]

    p12_response = client.post(
        f"/project-director/sessions/{session_id}/dry-run-task-dispatch",
        json={"source_message_id": p11_message["id"], "user_confirmed": True},
    )
    assert p12_response.status_code == 200
    p12_payload = p12_response.json()

    worker_response = client.post("/workers/run-once")
    assert worker_response.status_code == 200

    p13_response = client.post(
        f"/project-director/sessions/{session_id}/controlled-executor-dispatch",
        json={
            "source_task_id": p12_payload["created_task_id"],
            "source_message_id": p12_payload["message"]["id"],
            "user_confirmed": True,
            "requested_agent_role": "reviewer",
            "requested_executor": "codex",
            "launch_mode": "dry_run",
        },
    )
    assert p13_response.status_code == 200

    p14_message_id = _record_p14_lifecycle_message(
        sqlite_session_factory,
        session_id=session_id,
        source_task_id=p12_payload["created_task_id"],
        source_message_id=p12_payload["message"]["id"],
    )
    return session_id, p12_payload, p14_message_id


def test_readonly_review_api_dry_run_binds_session_message(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, p12_payload, p14_message_id = _prepare_p14_review_source(
            client,
            session_factory,
        )
        counts_before = {
            "tasks": _count_rows(session_factory, TaskTable),
            "runs": _count_rows(session_factory, RunTable),
            "messages": _count_rows(session_factory, ProjectDirectorMessageTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/readonly-review",
            json={
                "source_task_id": p12_payload["created_task_id"],
                "source_message_id": p14_message_id,
                "user_confirmed": True,
                "requested_reviewer_executor": "codex",
                "review_mode": "dry_run",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["review_status"] == "planned"
        assert payload["session_id"] == session_id
        assert payload["source_task_id"] == p12_payload["created_task_id"]
        assert payload["source_message_id"] == p14_message_id
        assert payload["p14_lifecycle_message_id"] == p14_message_id
        assert payload["readonly_review"] is True
        assert payload["reviewer_agent"] is True
        assert payload["executor_backed_review_allowed"] is True
        assert payload["product_runtime_git_write_allowed"] is False
        assert payload["worktree_write_allowed"] is False
        assert payload["file_write_allowed"] is False
        assert payload["real_code_modified"] is False
        assert payload["git_write_performed"] is False
        assert payload["native_executor_started"] is False
        assert payload["codex_started"] is False
        assert payload["claude_code_started"] is False
        assert payload["review_result_message_bound"] is True
        assert payload["ai_project_director_total_loop"] == "Partial"

        messages_response = client.get(
            f"/project-director/sessions/{session_id}/messages"
        )
        assert messages_response.status_code == 200
        messages = messages_response.json()["messages"]
        assert any(
            item["source_detail"] == "p15_readonly_reviewer_review"
            and item["related_task_id"] == p12_payload["created_task_id"]
            for item in messages
        )

    assert _count_rows(session_factory, TaskTable) == counts_before["tasks"]
    assert _count_rows(session_factory, RunTable) == counts_before["runs"]
    assert (
        _count_rows(session_factory, ProjectDirectorMessageTable)
        == counts_before["messages"] + 1
    )

    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in FORBIDDEN_OUTPUT_KEYS:
        assert forbidden not in serialized
    for forbidden_text in ("已执行提交", "已推送", "pr 已创建", "代码已写入"):
        assert forbidden_text not in serialized


def test_readonly_review_api_fake_review_generates_findings(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, p12_payload, p14_message_id = _prepare_p14_review_source(
            client,
            session_factory,
        )
        response = client.post(
            f"/project-director/sessions/{session_id}/readonly-review",
            json={
                "source_task_id": p12_payload["created_task_id"],
                "source_message_id": p14_message_id,
                "user_confirmed": True,
                "requested_reviewer_executor": "claude-code",
                "review_mode": "fake_review",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["review_status"] == "reviewed"
    assert payload["review_mode"] == "fake_review"
    assert payload["requested_reviewer_executor"] == "claude-code"
    assert payload["review_summary"]
    assert len(payload["review_findings"]) == 1
    assert payload["native_executor_started"] is False
    assert payload["product_runtime_git_write_allowed"] is False


def test_readonly_review_api_requires_user_confirmation(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, p12_payload, p14_message_id = _prepare_p14_review_source(
            client,
            session_factory,
        )
        before_runs = _count_rows(session_factory, RunTable)
        response = client.post(
            f"/project-director/sessions/{session_id}/readonly-review",
            json={
                "source_task_id": p12_payload["created_task_id"],
                "source_message_id": p14_message_id,
                "user_confirmed": False,
            },
        )

    assert response.status_code == 409
    assert "user_confirmation_required" in response.json()["detail"]
    assert _count_rows(session_factory, RunTable) == before_runs


def test_readonly_review_api_blocks_non_p14_source_message(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, p12_payload, _p14_message_id = _prepare_p14_review_source(
            client,
            session_factory,
        )
        response = client.post(
            f"/project-director/sessions/{session_id}/readonly-review",
            json={
                "source_task_id": p12_payload["created_task_id"],
                "source_message_id": p12_payload["message"]["id"],
                "user_confirmed": True,
            },
        )

    assert response.status_code == 409
    assert "source_message_is_not_p14_lifecycle_result" in response.json()["detail"]


def test_readonly_review_api_blocks_source_message_from_other_session(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        _session_id, p12_payload, p14_message_id = _prepare_p14_review_source(
            client,
            session_factory,
        )
        other_session_response = client.post(
            "/project-director/sessions",
            json={"goal_text": "P15 other session"},
        )
        assert other_session_response.status_code == 201
        other_session_id = other_session_response.json()["id"]

        response = client.post(
            f"/project-director/sessions/{other_session_id}/readonly-review",
            json={
                "source_task_id": p12_payload["created_task_id"],
                "source_message_id": p14_message_id,
                "user_confirmed": True,
            },
        )

    assert response.status_code == 409
    assert "source_message_not_in_session" in response.json()["detail"]


def test_readonly_review_api_blocks_controlled_review_in_api(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, p12_payload, p14_message_id = _prepare_p14_review_source(
            client,
            session_factory,
        )
        response = client.post(
            f"/project-director/sessions/{session_id}/readonly-review",
            json={
                "source_task_id": p12_payload["created_task_id"],
                "source_message_id": p14_message_id,
                "user_confirmed": True,
                "review_mode": "controlled_review",
            },
        )

    assert response.status_code == 409
    assert "controlled_review_not_enabled_in_api" in response.json()["detail"]


def test_readonly_review_api_rejects_invalid_reviewer_executor(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, p12_payload, p14_message_id = _prepare_p14_review_source(
            client,
            session_factory,
        )
        response = client.post(
            f"/project-director/sessions/{session_id}/readonly-review",
            json={
                "source_task_id": p12_payload["created_task_id"],
                "source_message_id": p14_message_id,
                "user_confirmed": True,
                "requested_reviewer_executor": "shell",
            },
        )

    assert response.status_code == 422
