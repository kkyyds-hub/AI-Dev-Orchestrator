"""API integration tests for P21-A sandbox write execution."""

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


MISLEADING_TERMS = {
    "已修改代码",
    "已应用 patch",
    "已创建 worktree",
    "已清理 worktree",
    "已提交代码",
    "已推送",
    "Git 写入已授权",
    "可以提交代码",
    "已执行提交",
    "代码已提交",
    "PR 已创建",
    "合并请求已创建",
    "automatic commit",
    "git commit performed",
}

SAFE_NEGATION_PHRASES = [
    "no file was written",
    "no file written",
    "no patch was applied",
    "no patch applied",
    "no worktree was created",
    "no worktree",
]

ALL_WRITE_FLAGS = [
    "sandbox_write_allowed",
    "product_runtime_git_write_allowed",
    "main_worktree_write_allowed",
    "worktree_write_allowed",
    "file_write_allowed",
    "actual_patch_applied",
    "real_code_modified",
    "git_write_performed",
    "native_executor_started",
    "codex_started",
    "claude_code_started",
    "worker_started",
    "task_created",
    "run_created",
    "worktree_created",
    "worktree_cleaned_up",
    "rollback_snapshot_created",
    "cleanup_required",
]


def _sqlite_session_factory(tmp_path):
    db_path = tmp_path / "orchestrator-p21-test.db"
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


def _prepare_p21_chain(
    client: TestClient,
    sqlite_session_factory,
) -> tuple[str, str, str]:
    """Prepare full chain through P20 preflight.

    Returns (session_id, task_id, p20_message_id).
    """
    session_response = client.post(
        "/project-director/sessions",
        json={"goal_text": "P21 sandbox write execution test"},
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["id"]

    p11_response = client.post(
        f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
        json={"user_goal": "P21 test evidence"},
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

    # P20 preflight
    p20_response = client.post(
        f"/project-director/sessions/{session_id}/sandbox-write-preflight",
        json={
            "source_task_id": task_id,
            "source_message_id": p17_message_id,
            "user_confirmed": True,
            "preflight_mode": "dry_run",
            "file_operations": [
                {
                    "path": "runtime/orchestrator/app/domain/example.py",
                    "operation": "update",
                    "reason": "test update",
                    "patch_preview": ["PREVIEW ONLY: no repository file was modified."],
                }
            ],
        },
    )
    assert p20_response.status_code == 200
    p20_payload = p20_response.json()
    assert p20_payload["preflight_status"] == "passed"

    p20_message_id = p20_payload["message"]["id"]
    return session_id, task_id, p20_message_id


# ── A. dry_run success ────────────────────────────────────────────────


def test_p21_dry_run_success(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p20_msg_id = _prepare_p21_chain(client, session_factory)
        counts_before = {
            "tasks": _count_rows(session_factory, TaskTable),
            "runs": _count_rows(session_factory, RunTable),
            "messages": _count_rows(session_factory, ProjectDirectorMessageTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-execution",
            json={
                "source_task_id": task_id,
                "source_message_id": p20_msg_id,
                "user_confirmed": True,
                "execution_mode": "dry_run",
            },
        )

        assert response.status_code == 200
        payload = response.json()

        assert payload["execution_status"] == "planned"
        assert payload["execution_mode"] == "dry_run"
        assert payload["dry_run_only"] is True
        assert payload["fake_write_only"] is False
        assert payload["policy_only_source_verified"] is True
        assert payload["source_preflight_message_bound"] is True
        assert payload["checked_operations_count"] >= 1
        assert len(payload["operation_results"]) >= 1
        assert payload["operation_results"][0]["execution_status"] == "planned"
        assert payload["operation_results"][0]["source_preflight_path_policy_allowed"] is True
        assert payload["execution_message_bound"] is True
        assert payload["message"] is not None
        assert payload["message"]["source_detail"] == "p21_sandbox_write_execution"

        actions = payload["message"].get("suggested_actions") or []
        assert len(actions) >= 1
        assert actions[0]["type"] == "p21_sandbox_write_execution_record"

        # No-write flags
        for flag in ALL_WRITE_FLAGS:
            assert payload[flag] is False, f"{flag} should be False"

        assert payload["ai_project_director_total_loop"] == "Partial"

        # No Task/Run created
    assert _count_rows(session_factory, TaskTable) == counts_before["tasks"]
    assert _count_rows(session_factory, RunTable) == counts_before["runs"]
    assert (
        _count_rows(session_factory, ProjectDirectorMessageTable)
        == counts_before["messages"] + 1
    )


# ── B. fake_write success ────────────────────────────────────────────


def test_p21_fake_write_success(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p20_msg_id = _prepare_p21_chain(client, session_factory)

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-execution",
            json={
                "source_task_id": task_id,
                "source_message_id": p20_msg_id,
                "user_confirmed": True,
                "execution_mode": "fake_write",
            },
        )

        assert response.status_code == 200
        payload = response.json()

        assert payload["execution_status"] == "simulated"
        assert payload["execution_mode"] == "fake_write"
        assert payload["fake_write_only"] is True
        assert payload["dry_run_only"] is False
        assert payload["simulated_operations_count"] >= 1
        assert len(payload["operation_results"]) >= 1
        for op in payload["operation_results"]:
            assert op["execution_status"] == "simulated"

        # No-write flags
        for flag in ALL_WRITE_FLAGS:
            assert payload[flag] is False, f"{flag} should be False"

            # Misleading output check on summary and operation notes
            serialized = json.dumps(payload, ensure_ascii=False)
            for term in MISLEADING_TERMS:
                assert term not in serialized, f"Found misleading term: {term}"
            # Verify safe negation phrases are present in execution_summary
            summary_lower = payload.get("execution_summary", "").lower()
            assert "no file" in summary_lower or "simulated only" in summary_lower


# ── C. controlled_sandbox_write blocked ───────────────────────────────


def test_p21_controlled_sandbox_write_blocked(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p20_msg_id = _prepare_p21_chain(client, session_factory)

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-execution",
            json={
                "source_task_id": task_id,
                "source_message_id": p20_msg_id,
                "user_confirmed": True,
                "execution_mode": "controlled_sandbox_write",
            },
        )

        assert response.status_code == 409
        assert "controlled_sandbox_write_not_enabled_in_api" in response.json()["detail"]


# ── D. user_confirmed=false blocked ──────────────────────────────────


def test_p21_requires_user_confirmation(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p20_msg_id = _prepare_p21_chain(client, session_factory)

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-execution",
            json={
                "source_task_id": task_id,
                "source_message_id": p20_msg_id,
                "user_confirmed": False,
            },
        )

        assert response.status_code == 409
        assert "user_confirmation_required" in response.json()["detail"]


# ── E. blocked P20 preflight cannot enter P21 ────────────────────────


def test_p21_blocked_preflight_cannot_enter(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p20_msg_id = _prepare_p21_chain(client, session_factory)

        # Now create a second P20 preflight with a denied path
        p20_blocked_response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-preflight",
            json={
                "source_task_id": task_id,
                "source_message_id": p20_msg_id,
                "user_confirmed": True,
                "preflight_mode": "dry_run",
                "file_operations": [
                    {
                        "path": ".env",
                        "operation": "update",
                        "reason": "test denied path",
                    }
                ],
            },
        )
        assert p20_blocked_response.status_code == 409
        assert "path_policy_failed" in p20_blocked_response.json()["detail"]


# ── F. source_task/message mismatch blocked ──────────────────────────


def test_p21_source_task_message_mismatch(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_a_id, p20_msg_a_id = _prepare_p21_chain(
            client, session_factory
        )

        # Create second chain
        p11_b = client.post(
            f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
            json={"user_goal": "P21 second evidence"},
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
        p20_b = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-preflight",
            json={
                "source_task_id": task_b_id,
                "source_message_id": p17_b,
                "user_confirmed": True,
                "preflight_mode": "dry_run",
                "file_operations": [
                    {
                        "path": "runtime/orchestrator/app/domain/other.py",
                        "operation": "update",
                        "reason": "test",
                        "patch_preview": ["PREVIEW ONLY: no repository file was modified."],
                    }
                ],
            },
        )
        assert p20_b.status_code == 200
        p20_msg_b_id = p20_b.json()["message"]["id"]

        # Use task A + P20 message from task B
        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-execution",
            json={
                "source_task_id": task_a_id,
                "source_message_id": p20_msg_b_id,
                "user_confirmed": True,
            },
        )

        assert response.status_code == 409
        assert "source_task_not_bound_to_p20_preflight" in response.json()["detail"]


# ── G. non-P20 source_detail blocked ─────────────────────────────────


def test_p21_blocks_non_p20_source_message(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, _p20_msg_id = _prepare_p21_chain(
            client, session_factory
        )

        # Use P15 review message instead of P20 preflight
        p15_msg_id = _record_p15_review_message(
            session_factory,
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=_record_p14_lifecycle_message(
                session_factory,
                session_id=session_id,
                source_task_id=task_id,
                source_message_id=task_id,
            ),
        )

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-execution",
            json={
                "source_task_id": task_id,
                "source_message_id": p15_msg_id,
                "user_confirmed": True,
            },
        )

        assert response.status_code == 409
        assert "source_message_is_not_p20_sandbox_write_preflight" in response.json()["detail"]


# ── H. not found ─────────────────────────────────────────────────────


def test_p21_nonexistent_session(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        response = client.post(
            f"/project-director/sessions/{uuid4()}/sandbox-write-execution",
            json={
                "source_task_id": str(uuid4()),
                "source_message_id": str(uuid4()),
                "user_confirmed": True,
            },
        )
        assert response.status_code == 404


# ── I. message readback ──────────────────────────────────────────────


def test_p21_message_readback(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p20_msg_id = _prepare_p21_chain(
            client, session_factory
        )

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-execution",
            json={
                "source_task_id": task_id,
                "source_message_id": p20_msg_id,
                "user_confirmed": True,
                "execution_mode": "dry_run",
            },
        )
        assert response.status_code == 200

        messages_response = client.get(
            f"/project-director/sessions/{session_id}/messages"
        )
        assert messages_response.status_code == 200
        messages = messages_response.json()["messages"]

        p21_msgs = [
            item
            for item in messages
            if item["source_detail"] == "p21_sandbox_write_execution"
        ]
        assert len(p21_msgs) >= 1

        p21_msg = p21_msgs[0]
        assert p21_msg["related_task_id"] == task_id

        actions = p21_msg.get("suggested_actions") or []
        assert len(actions) >= 1
        action = actions[0]
        assert action["type"] == "p21_sandbox_write_execution_record"
        assert action["execution_status"] in ("planned", "simulated", "blocked")
        assert action["product_runtime_git_write_allowed"] is False
        assert action["file_write_allowed"] is False
        assert action["git_write_performed"] is False
        assert action["ai_project_director_total_loop"] == "Partial"


# ── J. misleading output check on dry_run ────────────────────────────


def test_p21_dry_run_no_misleading_output(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p20_msg_id = _prepare_p21_chain(
            client, session_factory
        )

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-execution",
            json={
                "source_task_id": task_id,
                "source_message_id": p20_msg_id,
                "user_confirmed": True,
                "execution_mode": "dry_run",
            },
        )

        assert response.status_code == 200
        payload = response.json()

        serialized = json.dumps(payload, ensure_ascii=False)
        for term in MISLEADING_TERMS:
            assert term not in serialized, f"Found misleading term: {term}"

        # Safe terms should be present
        summary_lower = payload.get("execution_summary", "").lower()
        assert "planned only" in summary_lower or "no file" in summary_lower
