"""API integration tests for P16 programmer no-write planning."""

from __future__ import annotations

import json
from uuid import UUID, uuid4

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
    "secret",
    "pid",
    "raw command",
    "raw stdout",
    "raw stderr",
}

# "token" appears as a substring in legitimate field name "token_count"
# from ProjectDirectorMessageResponse. Use a word-boundary check instead.
FORBIDDEN_TOKEN_SUBSTRINGS = {"api_key", "token_value", "auth_token", "bearer"}

FORBIDDEN_OUTPUT_TEXTS = {
    "已执行提交",
    "已推送",
    "PR 已创建",
    "代码已写入",
    "已授权 Git 写",
    "已启动 Codex",
    "已启动 Claude",
}


def _sqlite_session_factory(tmp_path):
    db_path = tmp_path / "orchestrator-p16-test.db"
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
                requested_agent_role="programmer",
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


def _record_p15_review_message(
    sqlite_session_factory,
    *,
    session_id: str,
    source_task_id: str,
    source_message_id: str,
) -> str:
    """Record a P15 readonly review message via the service."""
    from app.services.project_director_readonly_review_service import (
        ProjectDirectorReadonlyReviewService,
    )

    db_session = sqlite_session_factory()
    try:
        service = ProjectDirectorReadonlyReviewService(
            session_repository=ProjectDirectorSessionRepository(db_session),
            message_repository=ProjectDirectorMessageRepository(db_session),
            task_repository=TaskRepository(db_session),
        )
        review = service.confirm_review(
            session_id=UUID(session_id),
            source_task_id=UUID(source_task_id),
            source_message_id=UUID(source_message_id),
            user_confirmed=True,
            requested_reviewer_executor="codex",
            review_mode="fake_review",
        )
        return str(review.message.id)
    finally:
        db_session.close()


def _prepare_p16_chain(
    client: TestClient,
    sqlite_session_factory,
) -> tuple[str, str, str, str, dict]:
    """Prepare full P11→P12→P13→P14→P15 chain and return (session_id, task_id, p15_message_id, p12_source_msg_id, p12_payload)."""
    session_response = client.post(
        "/project-director/sessions",
        json={"goal_text": "P16 programmer no-write plan test"},
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["id"]

    p11_response = client.post(
        f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
        json={"user_goal": "P16 test evidence"},
    )
    assert p11_response.status_code == 200
    p11_message = p11_response.json()["message"]

    p12_response = client.post(
        f"/project-director/sessions/{session_id}/dry-run-task-dispatch",
        json={"source_message_id": p11_message["id"], "user_confirmed": True},
    )
    assert p12_response.status_code == 200
    p12_payload = p12_response.json()
    task_id = p12_payload["created_task_id"]
    p12_source_msg_id = p12_payload["message"]["id"]

    worker_response = client.post("/workers/run-once")
    assert worker_response.status_code == 200

    p13_response = client.post(
        f"/project-director/sessions/{session_id}/controlled-executor-dispatch",
        json={
            "source_task_id": task_id,
            "source_message_id": p12_source_msg_id,
            "user_confirmed": True,
            "requested_agent_role": "programmer",
            "requested_executor": "codex",
            "launch_mode": "dry_run",
        },
    )
    assert p13_response.status_code == 200

    p14_message_id = _record_p14_lifecycle_message(
        sqlite_session_factory,
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=p12_source_msg_id,
    )

    p15_message_id = _record_p15_review_message(
        sqlite_session_factory,
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=p14_message_id,
    )

    return session_id, task_id, p15_message_id, p12_source_msg_id, p12_payload


# ── A. dry_run success ────────────────────────────────────────────────


def test_p16_dry_run_success(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p15_msg_id, _, _ = _prepare_p16_chain(
            client, session_factory
        )
        counts_before = {
            "tasks": _count_rows(session_factory, TaskTable),
            "runs": _count_rows(session_factory, RunTable),
            "messages": _count_rows(session_factory, ProjectDirectorMessageTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/programmer-no-write-plan",
            json={
                "source_task_id": task_id,
                "source_message_id": p15_msg_id,
                "user_confirmed": True,
                "requested_programmer_executor": "codex",
                "planning_mode": "dry_run",
            },
        )

        assert response.status_code == 200
        payload = response.json()

        assert payload["plan_status"] == "planned"
        assert payload["planning_mode"] == "dry_run"
        assert payload["programmer_agent"] is True
        assert payload["controlled_programmer_planning"] is True
        assert payload["no_write_plan"] is True
        assert payload["executor_backed_programmer_allowed"] is True
        assert payload["product_runtime_git_write_allowed"] is False
        assert payload["worktree_write_allowed"] is False
        assert payload["file_write_allowed"] is False
        assert payload["real_code_modified"] is False
        assert payload["git_write_performed"] is False
        assert payload["native_executor_started"] is False
        assert payload["codex_started"] is False
        assert payload["claude_code_started"] is False
        assert payload["worker_started"] is False
        assert payload["task_created"] is False
        assert payload["run_created"] is False
        assert payload["plan_message_bound"] is True
        assert payload["message"] is not None
        assert payload["message"]["source_detail"] == "p16_programmer_no_write_plan"
        assert payload["implementation_summary"]
        assert len(payload["planned_steps"]) >= 1
        assert p15_msg_id in payload["reviewer_feedback_refs"]
        assert payload["ai_project_director_total_loop"] == "Partial"

        messages_response = client.get(
            f"/project-director/sessions/{session_id}/messages"
        )
        assert messages_response.status_code == 200
        messages = messages_response.json()["messages"]
        assert any(
            item["source_detail"] == "p16_programmer_no_write_plan"
            for item in messages
        )

    assert _count_rows(session_factory, TaskTable) == counts_before["tasks"]
    assert _count_rows(session_factory, RunTable) == counts_before["runs"]
    assert (
        _count_rows(session_factory, ProjectDirectorMessageTable)
        == counts_before["messages"] + 1
    )


# ── B. fake_plan success ─────────────────────────────────────────────


def test_p16_fake_plan_success(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p15_msg_id, _, _ = _prepare_p16_chain(
            client, session_factory
        )
        counts_before = {
            "tasks": _count_rows(session_factory, TaskTable),
            "runs": _count_rows(session_factory, RunTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/programmer-no-write-plan",
            json={
                "source_task_id": task_id,
                "source_message_id": p15_msg_id,
                "user_confirmed": True,
                "planning_mode": "fake_plan",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["plan_status"] == "planned"
        assert payload["planning_mode"] == "fake_plan"
        assert len(payload["planned_steps"]) >= 2

        all_tests = []
        for step in payload["planned_steps"]:
            all_tests.extend(step.get("required_targeted_tests", []))
        assert len(all_tests) >= 1

        assert len(payload["risks"]) >= 1

    assert _count_rows(session_factory, TaskTable) == counts_before["tasks"]
    assert _count_rows(session_factory, RunTable) == counts_before["runs"]


# ── C. user_confirmed=false blocked ──────────────────────────────────


def test_p16_requires_user_confirmation(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p15_msg_id, _, _ = _prepare_p16_chain(
            client, session_factory
        )
        counts_before = {
            "messages": _count_rows(session_factory, ProjectDirectorMessageTable),
            "runs": _count_rows(session_factory, RunTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/programmer-no-write-plan",
            json={
                "source_task_id": task_id,
                "source_message_id": p15_msg_id,
                "user_confirmed": False,
            },
        )

        assert response.status_code == 409
        assert "user_confirmation_required" in response.json()["detail"]

    assert _count_rows(session_factory, RunTable) == counts_before["runs"]
    assert (
        _count_rows(session_factory, ProjectDirectorMessageTable)
        == counts_before["messages"]
    )


# ── D. controlled_no_write blocked ───────────────────────────────────


def test_p16_controlled_no_write_blocked(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p15_msg_id, _, _ = _prepare_p16_chain(
            client, session_factory
        )

        response = client.post(
            f"/project-director/sessions/{session_id}/programmer-no-write-plan",
            json={
                "source_task_id": task_id,
                "source_message_id": p15_msg_id,
                "user_confirmed": True,
                "planning_mode": "controlled_no_write",
            },
        )

        assert response.status_code == 409
        assert "controlled_no_write_not_enabled_in_api" in response.json()["detail"]


# ── E. source message not in session ─────────────────────────────────


def test_p16_blocks_source_message_from_other_session(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p15_msg_id, _, _ = _prepare_p16_chain(
            client, session_factory
        )

        other_session = client.post(
            "/project-director/sessions",
            json={"goal_text": "P16 other session"},
        )
        assert other_session.status_code == 201
        other_session_id = other_session.json()["id"]

        response = client.post(
            f"/project-director/sessions/{other_session_id}/programmer-no-write-plan",
            json={
                "source_task_id": task_id,
                "source_message_id": p15_msg_id,
                "user_confirmed": True,
            },
        )

        assert response.status_code == 409
        assert "source_message_not_in_session" in response.json()["detail"]


# ── F. source message not P15 readonly review ────────────────────────


def test_p16_blocks_non_p15_source_message(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, _p15_msg_id, p12_source_msg_id, _ = _prepare_p16_chain(
            client, session_factory
        )

        response = client.post(
            f"/project-director/sessions/{session_id}/programmer-no-write-plan",
            json={
                "source_task_id": task_id,
                "source_message_id": p12_source_msg_id,
                "user_confirmed": True,
            },
        )

        assert response.status_code == 409
        assert "source_message_is_not_p15_readonly_review" in response.json()["detail"]


# ── G. non P12 safe dry-run task blocked ─────────────────────────────


def test_p16_blocks_nonexistent_task(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, _task_id, p15_msg_id, _, _ = _prepare_p16_chain(
            client, session_factory
        )

        response = client.post(
            f"/project-director/sessions/{session_id}/programmer-no-write-plan",
            json={
                "source_task_id": str(uuid4()),
                "source_message_id": p15_msg_id,
                "user_confirmed": True,
            },
        )

        assert response.status_code == 404


# ── H. source_task / P15 message mismatch ────────────────────────────


def test_p16_blocks_source_task_p15_message_mismatch(tmp_path) -> None:
    """Verify that using task A with P15 review message from task B is blocked.

    This tests source binding safety. If the P16 service does not enforce this,
    the test will fail, revealing an implementation gap.
    """
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        # Create first chain (task A)
        session_id, task_a_id, p15_msg_a_id, p12_msg_a_id, _ = _prepare_p16_chain(
            client, session_factory
        )

        # Create second chain in the same session (task B)
        p11_response_b = client.post(
            f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
            json={"user_goal": "P16 second evidence for mismatch test"},
        )
        assert p11_response_b.status_code == 200
        p11_msg_b = p11_response_b.json()["message"]

        p12_response_b = client.post(
            f"/project-director/sessions/{session_id}/dry-run-task-dispatch",
            json={"source_message_id": p11_msg_b["id"], "user_confirmed": True},
        )
        assert p12_response_b.status_code == 200
        p12_payload_b = p12_response_b.json()
        task_b_id = p12_payload_b["created_task_id"]
        p12_msg_b_id = p12_payload_b["message"]["id"]

        worker_response_b = client.post("/workers/run-once")
        assert worker_response_b.status_code == 200

        p13_response_b = client.post(
            f"/project-director/sessions/{session_id}/controlled-executor-dispatch",
            json={
                "source_task_id": task_b_id,
                "source_message_id": p12_msg_b_id,
                "user_confirmed": True,
                "requested_agent_role": "programmer",
                "requested_executor": "codex",
                "launch_mode": "dry_run",
            },
        )
        assert p13_response_b.status_code == 200

        p14_msg_b_id = _record_p14_lifecycle_message(
            session_factory,
            session_id=session_id,
            source_task_id=task_b_id,
            source_message_id=p12_msg_b_id,
        )

        p15_msg_b_id = _record_p15_review_message(
            session_factory,
            session_id=session_id,
            source_task_id=task_b_id,
            source_message_id=p14_msg_b_id,
        )

        # Now call P16 with task A + P15 review message from task B
        response = client.post(
            f"/project-director/sessions/{session_id}/programmer-no-write-plan",
            json={
                "source_task_id": task_a_id,
                "source_message_id": p15_msg_b_id,
                "user_confirmed": True,
            },
        )

        # This SHOULD be blocked. If it's 200, the P16 service has a gap.
        if response.status_code == 200:
            # Implementation gap: P16 does not verify source_task ↔ P15 message binding
            raise AssertionError(
                "P16 implementation bug: accepted task A with P15 review message from task B. "
                "Expected 409 with source_task_not_bound_to_p15_review or equivalent. "
                "P16 service does not verify source_task ↔ P15 review message binding."
            )

        assert response.status_code == 409


# ── I. response excludes sensitive/misleading fields ─────────────────


def test_p16_response_excludes_sensitive_fields(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p15_msg_id, _, _ = _prepare_p16_chain(
            client, session_factory
        )

        response = client.post(
            f"/project-director/sessions/{session_id}/programmer-no-write-plan",
            json={
                "source_task_id": task_id,
                "source_message_id": p15_msg_id,
                "user_confirmed": True,
                "planning_mode": "fake_plan",
            },
        )

        assert response.status_code == 200
        payload = response.json()

        serialized = json.dumps(payload, ensure_ascii=False).lower()
        for forbidden in FORBIDDEN_OUTPUT_KEYS:
            assert forbidden not in serialized, f"Found forbidden key: {forbidden}"
        for forbidden in FORBIDDEN_TOKEN_SUBSTRINGS:
            assert forbidden not in serialized, f"Found forbidden token substring: {forbidden}"
        for forbidden_text in FORBIDDEN_OUTPUT_TEXTS:
            assert forbidden_text not in serialized, f"Found forbidden text: {forbidden_text}"
