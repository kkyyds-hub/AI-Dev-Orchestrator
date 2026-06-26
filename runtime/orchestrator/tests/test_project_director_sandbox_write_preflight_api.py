"""API integration tests for P20 sandbox write preflight."""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest
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


FORBIDDEN_DIFF_PATTERNS = ["diff --git", "+++ b/", "--- a/", "@@", "index "]


def _sqlite_session_factory(tmp_path):
    db_path = tmp_path / "orchestrator-p20-test.db"
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
                requested_executor="codex",
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


def _record_p16_plan_message(
    sqlite_session_factory,
    *,
    session_id: str,
    source_task_id: str,
    source_message_id: str,
) -> str:
    from app.services.project_director_programmer_no_write_plan_service import (
        ProjectDirectorProgrammerNoWritePlanService,
    )

    db_session = sqlite_session_factory()
    try:
        service = ProjectDirectorProgrammerNoWritePlanService(
            session_repository=ProjectDirectorSessionRepository(db_session),
            message_repository=ProjectDirectorMessageRepository(db_session),
            task_repository=TaskRepository(db_session),
        )
        plan = service.confirm_plan(
            session_id=UUID(session_id),
            source_task_id=UUID(source_task_id),
            source_message_id=UUID(source_message_id),
            user_confirmed=True,
            requested_programmer_executor="codex",
            planning_mode="fake_plan",
        )
        return str(plan.message.id)
    finally:
        db_session.close()


def _record_p17_execution_message(
    sqlite_session_factory,
    *,
    session_id: str,
    source_task_id: str,
    source_message_id: str,
) -> str:
    from app.services.project_director_programmer_no_write_execution_service import (
        ProjectDirectorProgrammerNoWriteExecutionService,
    )

    db_session = sqlite_session_factory()
    try:
        service = ProjectDirectorProgrammerNoWriteExecutionService(
            session_repository=ProjectDirectorSessionRepository(db_session),
            message_repository=ProjectDirectorMessageRepository(db_session),
            task_repository=TaskRepository(db_session),
        )
        execution = service.confirm_execution(
            session_id=UUID(session_id),
            source_task_id=UUID(source_task_id),
            source_message_id=UUID(source_message_id),
            user_confirmed=True,
            requested_programmer_executor="codex",
            execution_mode="fake_execution",
        )
        return str(execution.message.id)
    finally:
        db_session.close()


def _prepare_p20_chain(
    client: TestClient,
    sqlite_session_factory,
) -> tuple[str, str, str]:
    """Prepare full P11→P12→P13→P14→P15→P16→P17 chain.

    Returns (session_id, task_id, p17_message_id).
    """
    session_response = client.post(
        "/project-director/sessions",
        json={"goal_text": "P20 sandbox write preflight test"},
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["id"]

    p11_response = client.post(
        f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
        json={"user_goal": "P20 test evidence"},
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

    p16_message_id = _record_p16_plan_message(
        sqlite_session_factory,
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=p15_message_id,
    )

    p17_message_id = _record_p17_execution_message(
        sqlite_session_factory,
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=p16_message_id,
    )

    return session_id, task_id, p17_message_id


def _safe_file_operation(
    path: str = "runtime/orchestrator/app/domain/example.py",
    operation: str = "update",
) -> dict:
    return {
        "path": path,
        "operation": operation,
        "reason": f"test {operation}",
        "patch_preview": ["PREVIEW ONLY: no repository file was modified."],
    }


# ── A. dry_run preflight success ─────────────────────────────────────


def test_p20_dry_run_success(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p17_msg_id = _prepare_p20_chain(client, session_factory)
        counts_before = {
            "tasks": _count_rows(session_factory, TaskTable),
            "runs": _count_rows(session_factory, RunTable),
            "messages": _count_rows(session_factory, ProjectDirectorMessageTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-preflight",
            json={
                "source_task_id": task_id,
                "source_message_id": p17_msg_id,
                "user_confirmed": True,
                "preflight_mode": "dry_run",
                "file_operations": [_safe_file_operation()],
            },
        )

        assert response.status_code == 200
        payload = response.json()

        assert payload["preflight_status"] == "passed"
        assert payload["policy_only_preflight"] is True
        assert payload["preflight_message_bound"] is True
        assert payload["checked_operations_count"] == 1
        assert payload["allowed_operations_count"] == 1
        assert payload["blocked_operations_count"] == 0
        assert len(payload["accepted_operation_paths"]) == 1
        assert payload["accepted_operations"] == [
            {
                "path": "runtime/orchestrator/app/domain/example.py",
                "operation": "update",
            }
        ]
        assert payload["path_policy_results"][0]["allowed"] is True

        # Safety flags
        assert payload["sandbox_write_allowed"] is False
        assert payload["product_runtime_git_write_allowed"] is False
        assert payload["main_worktree_write_allowed"] is False
        assert payload["worktree_write_allowed"] is False
        assert payload["file_write_allowed"] is False
        assert payload["actual_patch_applied"] is False
        assert payload["real_code_modified"] is False
        assert payload["git_write_performed"] is False
        assert payload["native_executor_started"] is False
        assert payload["codex_started"] is False
        assert payload["claude_code_started"] is False
        assert payload["worker_started"] is False
        assert payload["task_created"] is False
        assert payload["run_created"] is False
        assert payload["ai_project_director_total_loop"] == "Partial"

        # No Task/Run created by P20
    assert _count_rows(session_factory, TaskTable) == counts_before["tasks"]
    assert _count_rows(session_factory, RunTable) == counts_before["runs"]
    assert (
        _count_rows(session_factory, ProjectDirectorMessageTable)
        == counts_before["messages"] + 1
    )


# ── B. fake_preflight success ────────────────────────────────────────


def test_p20_fake_preflight_success(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p17_msg_id = _prepare_p20_chain(client, session_factory)

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-preflight",
            json={
                "source_task_id": task_id,
                "source_message_id": p17_msg_id,
                "user_confirmed": True,
                "preflight_mode": "fake_preflight",
                "file_operations": [_safe_file_operation()],
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["preflight_status"] == "passed"
        assert payload["policy_only_preflight"] is True
        assert payload["sandbox_write_allowed"] is False


# ── C. user_confirmed=false blocked ──────────────────────────────────


def test_p20_requires_user_confirmation(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p17_msg_id = _prepare_p20_chain(client, session_factory)

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-preflight",
            json={
                "source_task_id": task_id,
                "source_message_id": p17_msg_id,
                "user_confirmed": False,
                "file_operations": [_safe_file_operation()],
            },
        )

        assert response.status_code == 409
        assert "user_confirmation_required" in response.json()["detail"]


# ── D. controlled_sandbox_write blocked ───────────────────────────────


def test_p20_controlled_sandbox_write_blocked(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p17_msg_id = _prepare_p20_chain(client, session_factory)

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-preflight",
            json={
                "source_task_id": task_id,
                "source_message_id": p17_msg_id,
                "user_confirmed": True,
                "preflight_mode": "controlled_sandbox_write",
                "file_operations": [_safe_file_operation()],
            },
        )

        assert response.status_code == 409
        assert "controlled_sandbox_write_not_enabled_in_api" in response.json()["detail"]


# ── E. file_operations empty blocked ─────────────────────────────────


def test_p20_empty_file_operations_blocked(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p17_msg_id = _prepare_p20_chain(client, session_factory)

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-preflight",
            json={
                "source_task_id": task_id,
                "source_message_id": p17_msg_id,
                "user_confirmed": True,
                "file_operations": [],
            },
        )

        assert response.status_code == 409
        assert "file_operations_required" in response.json()["detail"]


# ── F. source message not in session ─────────────────────────────────


def test_p20_blocks_source_message_from_other_session(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p17_msg_id = _prepare_p20_chain(client, session_factory)

        other_session = client.post(
            "/project-director/sessions",
            json={"goal_text": "P20 other session"},
        )
        assert other_session.status_code == 201
        other_session_id = other_session.json()["id"]

        response = client.post(
            f"/project-director/sessions/{other_session_id}/sandbox-write-preflight",
            json={
                "source_task_id": task_id,
                "source_message_id": p17_msg_id,
                "user_confirmed": True,
                "file_operations": [_safe_file_operation()],
            },
        )

        assert response.status_code == 409
        assert "source_message_not_in_session" in response.json()["detail"]


# ── G. source message not P17 execution ──────────────────────────────


def test_p20_blocks_non_p17_source_message(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p17_msg_id = _prepare_p20_chain(client, session_factory)

        # Use a P15 review message instead of P17 execution
        p15_msg_id = _record_p15_review_message(
            session_factory,
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=_record_p14_lifecycle_message(
                session_factory,
                session_id=session_id,
                source_task_id=task_id,
                source_message_id=task_id,  # dummy
            ),
        )

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-preflight",
            json={
                "source_task_id": task_id,
                "source_message_id": p15_msg_id,
                "user_confirmed": True,
                "file_operations": [_safe_file_operation()],
            },
        )

        assert response.status_code == 409
        assert "source_message_is_not_p17_programmer_no_write_execution" in response.json()["detail"]


# ── H. source task/message mismatch blocked ──────────────────────────


def test_p20_blocks_source_task_message_mismatch(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_a_id, p17_msg_a_id = _prepare_p20_chain(client, session_factory)

        # Create second chain
        p11_b = client.post(
            f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
            json={"user_goal": "P20 second evidence"},
        )
        assert p11_b.status_code == 200
        p11_msg_b = p11_b.json()["message"]

        p12_b = client.post(
            f"/project-director/sessions/{session_id}/dry-run-task-dispatch",
            json={"source_message_id": p11_msg_b["id"], "user_confirmed": True},
        )
        assert p12_b.status_code == 200
        task_b_id = p12_b.json()["created_task_id"]
        p12_msg_b_id = p12_b.json()["message"]["id"]

        client.post("/workers/run-once")

        p13_b = client.post(
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
        assert p13_b.status_code == 200

        p14_b = _record_p14_lifecycle_message(
            session_factory,
            session_id=session_id,
            source_task_id=task_b_id,
            source_message_id=p12_msg_b_id,
        )
        p15_b = _record_p15_review_message(
            session_factory,
            session_id=session_id,
            source_task_id=task_b_id,
            source_message_id=p14_b,
        )
        p16_b = _record_p16_plan_message(
            session_factory,
            session_id=session_id,
            source_task_id=task_b_id,
            source_message_id=p15_b,
        )
        p17_b = _record_p17_execution_message(
            session_factory,
            session_id=session_id,
            source_task_id=task_b_id,
            source_message_id=p16_b,
        )

        # Use task A + P17 message from task B
        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-preflight",
            json={
                "source_task_id": task_a_id,
                "source_message_id": p17_b,
                "user_confirmed": True,
                "file_operations": [_safe_file_operation()],
            },
        )

        assert response.status_code == 409
        assert "source_task_not_bound_to_p17_execution" in response.json()["detail"]


# ── I. non-P12 safe dry-run task blocked ─────────────────────────────


def test_p20_blocks_nonexistent_task(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, _task_id, p17_msg_id = _prepare_p20_chain(client, session_factory)

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-preflight",
            json={
                "source_task_id": str(uuid4()),
                "source_message_id": p17_msg_id,
                "user_confirmed": True,
                "file_operations": [_safe_file_operation()],
            },
        )

        assert response.status_code == 404


# ── J. denied path blocked ───────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "docs/superpowers/plans/foo.md",
        "apps/web/src/foo.tsx",
        "../escape.py",
        "runtime/orchestrator/app/secret.py",
        "runtime/orchestrator/app/image.png",
        "package-lock.json",
    ],
)
def test_p20_denied_path_blocked(tmp_path, path: str) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p17_msg_id = _prepare_p20_chain(client, session_factory)

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-preflight",
            json={
                "source_task_id": task_id,
                "source_message_id": p17_msg_id,
                "user_confirmed": True,
                "file_operations": [_safe_file_operation(path)],
            },
        )

        assert response.status_code == 409
        assert "path_policy_failed" in response.json()["detail"]


# ── K. apps/web explicit allow behavior ──────────────────────────────


def test_p20_apps_web_blocked_without_allow_frontend(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p17_msg_id = _prepare_p20_chain(client, session_factory)

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-preflight",
            json={
                "source_task_id": task_id,
                "source_message_id": p17_msg_id,
                "user_confirmed": True,
                "allowed_path_prefixes": ["apps/web/"],
                "allow_frontend": False,
                "file_operations": [_safe_file_operation("apps/web/src/foo.tsx")],
            },
        )

        assert response.status_code == 409


def test_p20_apps_web_blocked_without_prefix(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p17_msg_id = _prepare_p20_chain(client, session_factory)

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-preflight",
            json={
                "source_task_id": task_id,
                "source_message_id": p17_msg_id,
                "user_confirmed": True,
                "allow_frontend": True,
                "file_operations": [_safe_file_operation("apps/web/src/foo.tsx")],
            },
        )

        assert response.status_code == 409


def test_p20_apps_web_allowed_with_both_flags(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p17_msg_id = _prepare_p20_chain(client, session_factory)

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-preflight",
            json={
                "source_task_id": task_id,
                "source_message_id": p17_msg_id,
                "user_confirmed": True,
                "allowed_path_prefixes": ["apps/web/"],
                "allow_frontend": True,
                "file_operations": [_safe_file_operation("apps/web/src/foo.tsx")],
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["preflight_status"] == "passed"
        assert payload["sandbox_write_allowed"] is False
        assert payload["file_write_allowed"] is False


# ── L. unsafe patch_preview blocked ──────────────────────────────────


def test_p20_unsafe_patch_preview_blocked(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p17_msg_id = _prepare_p20_chain(client, session_factory)

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-preflight",
            json={
                "source_task_id": task_id,
                "source_message_id": p17_msg_id,
                "user_confirmed": True,
                "file_operations": [
                    {
                        "path": "runtime/orchestrator/app/domain/foo.py",
                        "operation": "update",
                        "reason": "test",
                        "patch_preview": ["diff --git a/foo.py b/foo.py"],
                    }
                ],
            },
        )

        # Pydantic validation should reject at domain level
        assert response.status_code in (409, 422)


# ── M. operation=delete behavior ─────────────────────────────────────


def test_p20_operation_delete_behavior(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p17_msg_id = _prepare_p20_chain(client, session_factory)

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-preflight",
            json={
                "source_task_id": task_id,
                "source_message_id": p17_msg_id,
                "user_confirmed": True,
                "file_operations": [
                    {
                        "path": "runtime/orchestrator/app/domain/foo.py",
                        "operation": "delete",
                        "reason": "test delete",
                    }
                ],
            },
        )

        # Expected: 422 from Pydantic Literal validation or 409 from service
        assert response.status_code in (409, 422)


# ── N. no Task/Run/Worker by P20 ────────────────────────────────────


def test_p20_no_task_run_worker_creation(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p17_msg_id = _prepare_p20_chain(client, session_factory)
        counts_before = {
            "tasks": _count_rows(session_factory, TaskTable),
            "runs": _count_rows(session_factory, RunTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-preflight",
            json={
                "source_task_id": task_id,
                "source_message_id": p17_msg_id,
                "user_confirmed": True,
                "file_operations": [_safe_file_operation()],
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["worker_started"] is False
        assert payload["task_created"] is False
        assert payload["run_created"] is False

    assert _count_rows(session_factory, TaskTable) == counts_before["tasks"]
    assert _count_rows(session_factory, RunTable) == counts_before["runs"]


# ── O. message readback ──────────────────────────────────────────────


def test_p20_message_readback(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p17_msg_id = _prepare_p20_chain(client, session_factory)

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-preflight",
            json={
                "source_task_id": task_id,
                "source_message_id": p17_msg_id,
                "user_confirmed": True,
                "file_operations": [_safe_file_operation()],
            },
        )
        assert response.status_code == 200

        messages_response = client.get(
            f"/project-director/sessions/{session_id}/messages"
        )
        assert messages_response.status_code == 200
        messages = messages_response.json()["messages"]

        p20_msgs = [
            item for item in messages
            if item["source_detail"] == "p20_sandbox_write_preflight"
        ]
        assert len(p20_msgs) >= 1

        p20_msg = p20_msgs[0]
        assert p20_msg["related_task_id"] == task_id

        actions = p20_msg.get("suggested_actions") or []
        assert len(actions) >= 1
        action = actions[0]
        assert action["type"] == "p20_sandbox_write_preflight_record"
        assert action["policy_only_preflight"] is True
        assert action["sandbox_write_allowed"] is False
        assert action["file_write_allowed"] is False
        assert action["git_write_performed"] is False
        assert action["accepted_operations"] == [
            {
                "path": "runtime/orchestrator/app/domain/example.py",
                "operation": "update",
            }
        ]
        assert action["ai_project_director_total_loop"] == "Partial"
