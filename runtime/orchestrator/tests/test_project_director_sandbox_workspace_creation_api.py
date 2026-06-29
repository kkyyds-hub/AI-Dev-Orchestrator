"""API integration tests for P21-C-C controlled sandbox workspace creation."""

from __future__ import annotations

import json
from pathlib import Path
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
    "已写入业务文件",
    "已写入 manifest 文件",
    "已读取目标文件",
    "已生成 diff",
    "已应用 patch",
    "已创建 git worktree",
    "已提交代码",
    "已推送",
    "Git 写入已授权",
    "controlled sandbox write 已启用",
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
]


def _sqlite_session_factory(tmp_path):
    db_path = tmp_path / "orchestrator-p21cc-test.db"
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


def _prepare_full_chain(
    client: TestClient,
    sqlite_session_factory,
) -> tuple[str, str, str]:
    """Prepare full chain through P21-C-B.

    Returns (session_id, task_id, p21_c_b_msg_id).
    """
    session_response = client.post(
        "/project-director/sessions",
        json={"goal_text": "P21-C-C workspace creation test"},
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["id"]

    p11_response = client.post(
        f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
        json={"user_goal": "P21-C-C test evidence"},
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
            ],
        },
    )
    assert p20_response.status_code == 200
    p20_message_id = p20_response.json()["message"]["id"]

    # P21-A execution
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
    p21_message_id = p21_response.json()["message"]["id"]

    # P21-B design lock
    lock_response = client.post(
        f"/project-director/sessions/{session_id}/sandbox-write-design-lock",
        json={
            "source_task_id": task_id,
            "source_message_id": p21_message_id,
            "user_confirmed": True,
        },
    )
    assert lock_response.status_code == 200
    lock_message_id = lock_response.json()["message"]["id"]

    # P21-C-A workspace guard
    guard_response = client.post(
        f"/project-director/sessions/{session_id}/sandbox-workspace-guard",
        json={
            "source_task_id": task_id,
            "source_message_id": lock_message_id,
            "user_confirmed": True,
        },
    )
    assert guard_response.status_code == 200
    guard_message_id = guard_response.json()["message"]["id"]

    # P21-C-B operation manifest guard
    manifest_response = client.post(
        f"/project-director/sessions/{session_id}/sandbox-operation-manifest-guard",
        json={
            "source_task_id": task_id,
            "source_message_id": guard_message_id,
            "user_confirmed": True,
        },
    )
    assert manifest_response.status_code == 200
    manifest_payload = manifest_response.json()
    assert manifest_payload["manifest_status"] == "manifested"
    manifest_message_id = manifest_payload["message"]["id"]

    return session_id, task_id, manifest_message_id


# ══════════════════════════════════════════════════════════════════════
# P21-C-C Workspace Create API Tests
# ══════════════════════════════════════════════════════════════════════


def test_workspace_create_success(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, manifest_msg_id = _prepare_full_chain(
            client, session_factory
        )
        counts_before = {
            "tasks": _count_rows(session_factory, TaskTable),
            "runs": _count_rows(session_factory, RunTable),
            "messages": _count_rows(session_factory, ProjectDirectorMessageTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-workspace-create",
            json={
                "source_task_id": task_id,
                "source_message_id": manifest_msg_id,
                "user_confirmed": True,
            },
        )

        assert response.status_code == 200
        payload = response.json()

        assert payload["creation_status"] == "created"
        assert payload["workspace_created"] is True
        assert payload["workspace_already_existed"] is False
        assert payload["workspace_path"] is not None
        assert payload["workspace_path_within_root"] is True
        assert payload["workspace_root"] is not None
        assert payload["source_manifest_status"] == "manifested"
        assert payload["source_manifest_message_bound"] is True
        assert payload["source_manifest_verified"] is True
        assert payload["cleanup_required"] is True
        assert payload["cleanup_hint"] != ""

        # All write flags false
        assert payload["workspace_written"] is False
        assert payload["file_written"] is False
        assert payload["manifest_file_written"] is False
        assert payload["target_file_content_read"] is False
        assert payload["real_diff_generated"] is False
        assert payload["patch_applied"] is False

        for flag in ALL_WRITE_FLAGS:
            assert payload[flag] is False, f"{flag} should be False"

        assert payload["ai_project_director_total_loop"] == "Partial"
        assert len(payload["required_preconditions"]) > 0
        assert len(payload["forbidden_creation_actions"]) > 0

        # Message exists
        assert payload["message"] is not None
        assert payload["message"]["source_detail"] == "p21_c_sandbox_workspace_created"

        actions = payload["message"].get("suggested_actions") or []
        assert len(actions) >= 1
        assert actions[0]["type"] == "p21_c_sandbox_workspace_create_record"
        assert actions[0]["creation_status"] == "created"

    # Exactly 1 message created, no Task/Run
    assert _count_rows(session_factory, TaskTable) == counts_before["tasks"]
    assert _count_rows(session_factory, RunTable) == counts_before["runs"]
    assert (
        _count_rows(session_factory, ProjectDirectorMessageTable)
        == counts_before["messages"] + 1
    )


def test_workspace_create_second_call_already_exists(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, manifest_msg_id = _prepare_full_chain(
            client, session_factory
        )

        # First call
        response1 = client.post(
            f"/project-director/sessions/{session_id}/sandbox-workspace-create",
            json={
                "source_task_id": task_id,
                "source_message_id": manifest_msg_id,
                "user_confirmed": True,
            },
        )
        assert response1.status_code == 200
        assert response1.json()["creation_status"] == "created"

        # Second call with same source message
        response2 = client.post(
            f"/project-director/sessions/{session_id}/sandbox-workspace-create",
            json={
                "source_task_id": task_id,
                "source_message_id": manifest_msg_id,
                "user_confirmed": True,
            },
        )
        assert response2.status_code == 200
        payload2 = response2.json()
        assert payload2["creation_status"] == "already_exists"
        assert payload2["workspace_created"] is False
        assert payload2["workspace_already_existed"] is True
        assert payload2["cleanup_required"] is False


def test_workspace_directory_exists_and_is_empty(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, manifest_msg_id = _prepare_full_chain(
            client, session_factory
        )

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-workspace-create",
            json={
                "source_task_id": task_id,
                "source_message_id": manifest_msg_id,
                "user_confirmed": True,
            },
        )
        assert response.status_code == 200
        payload = response.json()

        ws_path = Path(payload["workspace_path"])
        assert ws_path.exists(), "workspace directory should exist"
        assert ws_path.is_dir(), "workspace should be a directory"

        # No business files or manifest files written
        contents = list(ws_path.iterdir())
        assert len(contents) == 0, f"workspace should be empty, found: {contents}"


def test_workspace_create_user_confirmed_false_blocks(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, manifest_msg_id = _prepare_full_chain(
            client, session_factory
        )
        counts_before = {
            "messages": _count_rows(session_factory, ProjectDirectorMessageTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-workspace-create",
            json={
                "source_task_id": task_id,
                "source_message_id": manifest_msg_id,
                "user_confirmed": False,
            },
        )

        assert response.status_code == 409
        assert "user_confirmation_required" in response.json()["detail"]

    assert (
        _count_rows(session_factory, ProjectDirectorMessageTable)
        == counts_before["messages"]
    )


def test_workspace_create_non_manifest_source_blocks(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, _manifest_msg = _prepare_full_chain(
            client, session_factory
        )

        counts_before = {
            "messages": _count_rows(session_factory, ProjectDirectorMessageTable),
        }

        # Use P11 evidence message (wrong source type for P21-C-C)
        p11_response = client.post(
            f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
            json={"user_goal": "wrong source test"},
        )
        wrong_msg_id = p11_response.json()["message"]["id"]

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-workspace-create",
            json={
                "source_task_id": task_id,
                "source_message_id": wrong_msg_id,
                "user_confirmed": True,
            },
        )

        assert response.status_code == 409
        assert "source_message_is_not_p21_c_operation_manifest_guard" in response.json()["detail"]

    # counts_before was set before the P11 call, so add 1 for the P11 evidence message
    assert (
        _count_rows(session_factory, ProjectDirectorMessageTable)
        == counts_before["messages"] + 1
    )


def test_workspace_create_source_task_mismatch_blocks(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, manifest_msg_id = _prepare_full_chain(
            client, session_factory
        )

        wrong_task_id = str(uuid4())
        counts_before = {
            "messages": _count_rows(session_factory, ProjectDirectorMessageTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-workspace-create",
            json={
                "source_task_id": wrong_task_id,
                "source_message_id": manifest_msg_id,
                "user_confirmed": True,
            },
        )

        assert response.status_code == 409

    assert (
        _count_rows(session_factory, ProjectDirectorMessageTable)
        == counts_before["messages"]
    )


def test_workspace_create_nonexistent_session(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        response = client.post(
            f"/project-director/sessions/{uuid4()}/sandbox-workspace-create",
            json={
                "source_task_id": str(uuid4()),
                "source_message_id": str(uuid4()),
                "user_confirmed": True,
            },
        )
        assert response.status_code == 404


# ══════════════════════════════════════════════════════════════════════
# Message Readback
# ══════════════════════════════════════════════════════════════════════


def test_message_readback(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, manifest_msg_id = _prepare_full_chain(
            client, session_factory
        )

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-workspace-create",
            json={
                "source_task_id": task_id,
                "source_message_id": manifest_msg_id,
                "user_confirmed": True,
            },
        )
        assert response.status_code == 200

        messages_response = client.get(
            f"/project-director/sessions/{session_id}/messages"
        )
        assert messages_response.status_code == 200
        messages = messages_response.json()["messages"]

        create_msgs = [
            item
            for item in messages
            if item["source_detail"] == "p21_c_sandbox_workspace_created"
        ]
        assert len(create_msgs) >= 1

        create_msg = create_msgs[0]
        actions = create_msg.get("suggested_actions") or []
        assert len(actions) >= 1
        assert actions[0]["type"] == "p21_c_sandbox_workspace_create_record"
        assert actions[0]["ai_project_director_total_loop"] == "Partial"

        # No misleading output
        serialized = json.dumps(create_msg, ensure_ascii=False)
        for term in MISLEADING_TERMS:
            assert term not in serialized, f"Found misleading term: {term}"
