"""API integration tests for P21-B sandbox write design lock."""

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

ALL_WRITE_FLAGS = [
    "controlled_sandbox_write_enabled",
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
    db_path = tmp_path / "orchestrator-p21b-test.db"
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
    """Prepare full chain through P21-A.

    Returns (session_id, task_id, p21_execution_message_id).
    """
    session_response = client.post(
        "/project-director/sessions",
        json={"goal_text": "P21-B design lock test"},
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["id"]

    p11_response = client.post(
        f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
        json={"user_goal": "P21-B test evidence"},
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
                    "operation": "create",
                    "reason": "test create",
                    "patch_preview": ["PREVIEW ONLY: no repository file was modified."],
                },
                {
                    "path": "runtime/orchestrator/app/domain/existing.py",
                    "operation": "update",
                    "reason": "test update",
                    "patch_preview": ["PREVIEW ONLY: no repository file was modified."],
                },
            ],
        },
    )
    assert p20_response.status_code == 200
    p20_payload = p20_response.json()
    assert p20_payload["preflight_status"] == "passed"
    p20_message_id = p20_payload["message"]["id"]

    # P21-A execution (default dry_run)
    p21_response = client.post(
        f"/project-director/sessions/{session_id}/sandbox-write-execution",
        json={
            "source_task_id": task_id,
            "source_message_id": p20_message_id,
            "user_confirmed": True,
            "execution_mode": "dry_run",
        },
    )
    assert p21_response.status_code == 200
    p21_payload = p21_response.json()
    assert p21_payload["execution_status"] == "planned"
    p21_message_id = p21_payload["message"]["id"]

    return session_id, task_id, p21_message_id


def _prepare_p21_fake_write_chain(
    client: TestClient,
    sqlite_session_factory,
) -> tuple[str, str, str]:
    """Prepare chain through P21-A fake_write.

    Returns (session_id, task_id, p21_execution_message_id).
    """
    session_response = client.post(
        "/project-director/sessions",
        json={"goal_text": "P21-B design lock fake_write test"},
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["id"]

    p11_response = client.post(
        f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
        json={"user_goal": "P21-B fake_write test evidence"},
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

    client.post("/workers/run-once")

    client.post(
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
                    "operation": "create",
                    "reason": "test",
                    "patch_preview": ["PREVIEW ONLY: no repository file was modified."],
                },
            ],
        },
    )
    assert p20_response.status_code == 200
    p20_message_id = p20_response.json()["message"]["id"]

    p21_response = client.post(
        f"/project-director/sessions/{session_id}/sandbox-write-execution",
        json={
            "source_task_id": task_id,
            "source_message_id": p20_message_id,
            "user_confirmed": True,
            "execution_mode": "fake_write",
        },
    )
    assert p21_response.status_code == 200
    p21_payload = p21_response.json()
    assert p21_payload["execution_status"] == "simulated"
    p21_message_id = p21_payload["message"]["id"]

    return session_id, task_id, p21_message_id


# ── 1. Successful design lock from dry_run ───────────────────────────


def test_design_lock_dry_run_success(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p21_msg_id = _prepare_p21_chain(client, session_factory)
        counts_before = {
            "tasks": _count_rows(session_factory, TaskTable),
            "runs": _count_rows(session_factory, RunTable),
            "messages": _count_rows(session_factory, ProjectDirectorMessageTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-design-lock",
            json={
                "source_task_id": task_id,
                "source_message_id": p21_msg_id,
                "user_confirmed": True,
            },
        )

        assert response.status_code == 200
        payload = response.json()

        assert payload["design_lock_status"] == "locked"
        assert payload["source_execution_status"] == "planned"
        assert payload["source_execution_mode"] == "dry_run"
        assert payload["source_execution_message_bound"] is True
        assert payload["source_operation_intent_preserved"] is True
        assert payload["controlled_sandbox_write_design_locked"] is True

        for flag in ALL_WRITE_FLAGS:
            assert payload[flag] is False, f"{flag} should be False"

        assert payload["ai_project_director_total_loop"] == "Partial"
        assert len(payload["required_preconditions"]) > 0
        assert len(payload["allowed_future_write_scope"]) > 0
        assert "no_product_runtime_git_write" in payload["forbidden_runtime_actions"]
        assert "no_main_worktree_write" in payload["forbidden_runtime_actions"]
        assert "no_target_file_content_read_in_design_lock" in payload["forbidden_runtime_actions"]
        assert "operation_intent_missing" in payload["failure_states"]
        assert "real_write_not_allowed_in_design_lock" in payload["failure_states"]

        # Message exists
        assert payload["message"] is not None
        assert payload["message"]["source_detail"] == "p21_b_sandbox_write_design_lock"

        actions = payload["message"].get("suggested_actions") or []
        assert len(actions) >= 1
        assert actions[0]["type"] == "p21_b_sandbox_write_design_lock_record"
        for flag in ALL_WRITE_FLAGS:
            assert actions[0].get(flag) is False, f"action {flag} should be False"

    # Exactly 1 message created, no Task/Run
    assert _count_rows(session_factory, TaskTable) == counts_before["tasks"]
    assert _count_rows(session_factory, RunTable) == counts_before["runs"]
    assert (
        _count_rows(session_factory, ProjectDirectorMessageTable)
        == counts_before["messages"] + 1
    )


# ── 2. Successful design lock from fake_write ────────────────────────


def test_design_lock_fake_write_success(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p21_msg_id = _prepare_p21_fake_write_chain(
            client, session_factory
        )

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-design-lock",
            json={
                "source_task_id": task_id,
                "source_message_id": p21_msg_id,
                "user_confirmed": True,
            },
        )

        assert response.status_code == 200
        payload = response.json()

        assert payload["design_lock_status"] == "locked"
        assert payload["source_execution_status"] == "simulated"
        assert payload["source_execution_mode"] == "fake_write"
        assert payload["controlled_sandbox_write_design_locked"] is True

        for flag in ALL_WRITE_FLAGS:
            assert payload[flag] is False, f"{flag} should be False"


# ── 3. user_confirmed=false ──────────────────────────────────────────


def test_design_lock_requires_user_confirmation(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p21_msg_id = _prepare_p21_chain(client, session_factory)
        counts_before = {
            "messages": _count_rows(session_factory, ProjectDirectorMessageTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-design-lock",
            json={
                "source_task_id": task_id,
                "source_message_id": p21_msg_id,
                "user_confirmed": False,
            },
        )

        assert response.status_code == 409
        assert "user_confirmation_required" in response.json()["detail"]

    # No message created
    assert (
        _count_rows(session_factory, ProjectDirectorMessageTable)
        == counts_before["messages"]
    )


# ── 4. source message is not P21 execution ───────────────────────────


def test_design_lock_blocks_non_p21_source_message(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, _p21_msg_id = _prepare_p21_chain(client, session_factory)

        # Use P15 review message instead of P21
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

        counts_before = {
            "messages": _count_rows(session_factory, ProjectDirectorMessageTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-design-lock",
            json={
                "source_task_id": task_id,
                "source_message_id": p15_msg_id,
                "user_confirmed": True,
            },
        )

        assert response.status_code == 409
        assert "source_message_is_not_p21_sandbox_write_execution" in response.json()["detail"]

    assert (
        _count_rows(session_factory, ProjectDirectorMessageTable)
        == counts_before["messages"]
    )


# ── 5. source task/message mismatch ──────────────────────────────────


def test_design_lock_blocks_source_task_message_mismatch(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_a_id, p21_msg_a_id = _prepare_p21_chain(
            client, session_factory
        )

        # Create second chain
        p11_b = client.post(
            f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
            json={"user_goal": "P21-B second evidence"},
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

        client.post(
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

        p21_b = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-execution",
            json={
                "source_task_id": task_b_id,
                "source_message_id": p20_msg_b_id,
                "user_confirmed": True,
                "execution_mode": "dry_run",
            },
        )
        assert p21_b.status_code == 200
        p21_msg_b_id = p21_b.json()["message"]["id"]

        # Use task A + P21 message from task B
        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-design-lock",
            json={
                "source_task_id": task_a_id,
                "source_message_id": p21_msg_b_id,
                "user_confirmed": True,
            },
        )

        assert response.status_code == 409
        assert "source_task_not_bound_to_p21_execution" in response.json()["detail"]


# ── 6. P21 action has runtime write flag true ────────────────────────


def test_design_lock_blocks_runtime_write_flag_true(tmp_path) -> None:
    """This test requires injecting a P21 message with a runtime write flag true.
    Since we can't modify the P21-A service, we test at the service level instead.
    The API would also block this via the service."""
    from app.domain.project_director_message import (
        ProjectDirectorMessage,
        ProjectDirectorMessageRole,
        ProjectDirectorMessageSource,
    )
    from app.domain.task import Task
    from app.services.project_director_sandbox_write_design_lock_service import (
        ProjectDirectorSandboxWriteDesignLockService,
    )
    from app.services.project_director_sandbox_write_execution_service import (
        P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL,
    )

    session_id = uuid4()
    task_id = uuid4()

    task = Task(
        id=task_id,
        title="P21-B test task",
        source_draft_id="p12-test",
        input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
        acceptance_criteria=[
            "safe_dry_run_task=true",
            "worker_simulate_required=true",
            "product_runtime_git_write_allowed=false",
            "native_executor_started=false",
            "codex_started=false",
            "claude_code_started=false",
        ],
    )

    p21_action = {
        "type": "p21_sandbox_write_execution_record",
        "source_task_id": str(task_id),
        "execution_mode": "dry_run",
        "execution_status": "planned",
        "no_write_execution": True,
        "controlled_sandbox_write_enabled": False,
        "sandbox_write_allowed": True,  # <-- true
        "product_runtime_git_write_allowed": False,
        "main_worktree_write_allowed": False,
        "worktree_write_allowed": False,
        "file_write_allowed": False,
        "actual_patch_applied": False,
        "real_code_modified": False,
        "git_write_performed": False,
        "native_executor_started": False,
        "codex_started": False,
        "claude_code_started": False,
        "worker_started": False,
        "task_created": False,
        "run_created": False,
        "worktree_created": False,
        "worktree_cleaned_up": False,
        "rollback_snapshot_created": False,
        "cleanup_required": False,
        "operation_results": [
            {
                "operation_id": "p21-a-1",
                "path": "test.py",
                "operation": "create",
                "execution_status": "planned",
            }
        ],
    }

    message = ProjectDirectorMessage(
        session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="test",
        sequence_no=1,
        intent="sandbox_write_execution",
        related_project_id=uuid4(),
        related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL,
        suggested_actions=[p21_action],
    )

    service = ProjectDirectorSandboxWriteDesignLockService()
    result = service.build_design_lock_from_sources(
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=uuid4(),
        source_task=task,
        source_message=message,
        user_confirmed=True,
    )

    assert result.design_lock_status == "blocked"
    assert "real_write_not_allowed_in_design_lock" in result.blocked_reasons


# ── 7. P21 action has no operation intent ─────────────────────────────


def test_design_lock_blocks_operation_intent_missing(tmp_path) -> None:
    """Test at service level since we can't inject empty operation_results via API."""
    from app.domain.project_director_message import (
        ProjectDirectorMessage,
        ProjectDirectorMessageRole,
        ProjectDirectorMessageSource,
    )
    from app.domain.task import Task
    from app.services.project_director_sandbox_write_design_lock_service import (
        ProjectDirectorSandboxWriteDesignLockService,
    )
    from app.services.project_director_sandbox_write_execution_service import (
        P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL,
    )

    session_id = uuid4()
    task_id = uuid4()

    task = Task(
        id=task_id,
        title="P21-B test task",
        source_draft_id="p12-test",
        input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
        acceptance_criteria=[
            "safe_dry_run_task=true",
            "worker_simulate_required=true",
            "product_runtime_git_write_allowed=false",
            "native_executor_started=false",
            "codex_started=false",
            "claude_code_started=false",
        ],
    )

    p21_action = {
        "type": "p21_sandbox_write_execution_record",
        "source_task_id": str(task_id),
        "execution_mode": "dry_run",
        "execution_status": "planned",
        "no_write_execution": True,
        "controlled_sandbox_write_enabled": False,
        "sandbox_write_allowed": False,
        "product_runtime_git_write_allowed": False,
        "main_worktree_write_allowed": False,
        "worktree_write_allowed": False,
        "file_write_allowed": False,
        "actual_patch_applied": False,
        "real_code_modified": False,
        "git_write_performed": False,
        "native_executor_started": False,
        "codex_started": False,
        "claude_code_started": False,
        "worker_started": False,
        "task_created": False,
        "run_created": False,
        "worktree_created": False,
        "worktree_cleaned_up": False,
        "rollback_snapshot_created": False,
        "cleanup_required": False,
        "operation_results": [],  # empty
    }

    message = ProjectDirectorMessage(
        session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="test",
        sequence_no=1,
        intent="sandbox_write_execution",
        related_project_id=uuid4(),
        related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL,
        suggested_actions=[p21_action],
    )

    service = ProjectDirectorSandboxWriteDesignLockService()
    result = service.build_design_lock_from_sources(
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=uuid4(),
        source_task=task,
        source_message=message,
        user_confirmed=True,
    )

    assert result.design_lock_status == "blocked"
    assert "operation_intent_missing" in result.blocked_reasons


# ── 8. nonexistent session ───────────────────────────────────────────


def test_design_lock_nonexistent_session(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        response = client.post(
            f"/project-director/sessions/{uuid4()}/sandbox-write-design-lock",
            json={
                "source_task_id": str(uuid4()),
                "source_message_id": str(uuid4()),
                "user_confirmed": True,
            },
        )
        assert response.status_code == 404


# ── 9. Message readback ──────────────────────────────────────────────


def test_design_lock_message_readback(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p21_msg_id = _prepare_p21_chain(client, session_factory)

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-design-lock",
            json={
                "source_task_id": task_id,
                "source_message_id": p21_msg_id,
                "user_confirmed": True,
            },
        )
        assert response.status_code == 200

        messages_response = client.get(
            f"/project-director/sessions/{session_id}/messages"
        )
        assert messages_response.status_code == 200
        messages = messages_response.json()["messages"]

        lock_msgs = [
            item
            for item in messages
            if item["source_detail"] == "p21_b_sandbox_write_design_lock"
        ]
        assert len(lock_msgs) >= 1

        lock_msg = lock_msgs[0]
        actions = lock_msg.get("suggested_actions") or []
        assert len(actions) >= 1
        action = actions[0]
        assert action["type"] == "p21_b_sandbox_write_design_lock_record"

        # No misleading output
        serialized = json.dumps(lock_msg, ensure_ascii=False)
        for term in MISLEADING_TERMS:
            assert term not in serialized, f"Found misleading term: {term}"

        # Total loop Partial
        assert action["ai_project_director_total_loop"] == "Partial"


# ── 10. Counts ───────────────────────────────────────────────────────


def test_design_lock_creates_exactly_one_message(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p21_msg_id = _prepare_p21_chain(client, session_factory)
        counts_before = {
            "messages": _count_rows(session_factory, ProjectDirectorMessageTable),
            "tasks": _count_rows(session_factory, TaskTable),
            "runs": _count_rows(session_factory, RunTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-write-design-lock",
            json={
                "source_task_id": task_id,
                "source_message_id": p21_msg_id,
                "user_confirmed": True,
            },
        )
        assert response.status_code == 200

    assert (
        _count_rows(session_factory, ProjectDirectorMessageTable)
        == counts_before["messages"] + 1
    )
    assert _count_rows(session_factory, TaskTable) == counts_before["tasks"]
    assert _count_rows(session_factory, RunTable) == counts_before["runs"]
