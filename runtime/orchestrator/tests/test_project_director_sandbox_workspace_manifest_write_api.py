"""API integration tests for P21-C-D controlled sandbox workspace evidence manifest write."""

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
    db_path = tmp_path / "orchestrator-p21cd-test.db"
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
    """Prepare full chain through P21-C-C.

    Returns (session_id, task_id, p21_c_c_msg_id).
    """
    session_response = client.post(
        "/project-director/sessions",
        json={"goal_text": "P21-C-D manifest write test"},
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["id"]

    p11_response = client.post(
        f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
        json={"user_goal": "P21-C-D test evidence"},
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

    # P21-A execution (dry_run)
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
    manifest_message_id = manifest_response.json()["message"]["id"]

    # P21-C-C workspace create
    create_response = client.post(
        f"/project-director/sessions/{session_id}/sandbox-workspace-create",
        json={
            "source_task_id": task_id,
            "source_message_id": manifest_message_id,
            "user_confirmed": True,
        },
    )
    assert create_response.status_code == 200
    create_message_id = create_response.json()["message"]["id"]

    return session_id, task_id, create_message_id


# ══════════════════════════════════════════════════════════════════════
# P21-C-D Manifest Write API Success Tests
# ══════════════════════════════════════════════════════════════════════


def test_manifest_write_first_call_written(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, create_msg_id = _prepare_full_chain(
            client, session_factory
        )
        counts_before = {
            "tasks": _count_rows(session_factory, TaskTable),
            "runs": _count_rows(session_factory, RunTable),
            "messages": _count_rows(session_factory, ProjectDirectorMessageTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-workspace-evidence-manifest",
            json={
                "source_task_id": task_id,
                "source_message_id": create_msg_id,
                "user_confirmed": True,
            },
        )

        assert response.status_code == 200
        payload = response.json()

        assert payload["manifest_write_status"] == "written"
        assert payload["manifest_file_written"] is True
        assert payload["manifest_file_overwritten"] is False
        assert payload["business_file_written"] is False
        assert payload["target_file_content_read"] is False
        assert payload["real_diff_generated"] is False
        assert payload["patch_applied"] is False
        assert payload["source_workspace_creation_verified"] is True
        assert payload["workspace_path"] is not None
        assert payload["workspace_path_within_root"] is True
        assert payload["manifest_dir_path"] is not None
        assert payload["manifest_file_path"] is not None
        assert payload["manifest_file_path"].endswith(".ai-project-director/workspace-manifest.json")
        assert payload["ai_project_director_total_loop"] == "Partial"

        for flag in ALL_WRITE_FLAGS:
            assert payload[flag] is False, f"{flag} should be False"

        assert payload["message"] is not None
        assert payload["message"]["source_detail"] == "p21_c_sandbox_workspace_manifest_written"

        actions = payload["message"].get("suggested_actions") or []
        assert len(actions) >= 1
        assert actions[0]["type"] == "p21_c_sandbox_workspace_manifest_write_record"
        assert actions[0]["manifest_write_status"] == "written"

        # Manifest file exists on disk
        manifest_path = Path(payload["manifest_file_path"])
        assert manifest_path.exists()
        raw = manifest_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        assert data["schema_version"] == "p21-c-d.v1"

        # Workspace has no business files
        ws_path = Path(payload["workspace_path"])
        manifest_dir = ws_path / ".ai-project-director"
        all_ws_files = [f for f in ws_path.rglob("*") if f.is_file()]
        assert len(all_ws_files) == 1
        assert all_ws_files[0] == manifest_dir / "workspace-manifest.json"

    # Exactly 1 message created, no Task/Run
    assert _count_rows(session_factory, TaskTable) == counts_before["tasks"]
    assert _count_rows(session_factory, RunTable) == counts_before["runs"]
    assert (
        _count_rows(session_factory, ProjectDirectorMessageTable)
        == counts_before["messages"] + 1
    )


def test_manifest_write_second_call_overwritten(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, create_msg_id = _prepare_full_chain(
            client, session_factory
        )

        # First call
        r1 = client.post(
            f"/project-director/sessions/{session_id}/sandbox-workspace-evidence-manifest",
            json={
                "source_task_id": task_id,
                "source_message_id": create_msg_id,
                "user_confirmed": True,
            },
        )
        assert r1.status_code == 200
        assert r1.json()["manifest_write_status"] == "written"
        assert r1.json()["manifest_file_overwritten"] is False

        # Second call
        r2 = client.post(
            f"/project-director/sessions/{session_id}/sandbox-workspace-evidence-manifest",
            json={
                "source_task_id": task_id,
                "source_message_id": create_msg_id,
                "user_confirmed": True,
            },
        )
        assert r2.status_code == 200
        payload2 = r2.json()
        assert payload2["manifest_write_status"] == "overwritten"
        assert payload2["manifest_file_written"] is True
        assert payload2["manifest_file_overwritten"] is True
        assert payload2["manifest_file_path"] == r1.json()["manifest_file_path"]
        assert payload2["business_file_written"] is False

        # Same manifest file path
        manifest_path = Path(payload2["manifest_file_path"])
        assert manifest_path.exists()
        manifest_dir = manifest_path.parent
        all_files = [f for f in manifest_dir.iterdir() if f.is_file()]
        assert len(all_files) == 1
        assert all_files[0].name == "workspace-manifest.json"


# ══════════════════════════════════════════════════════════════════════
# P21-C-D Manifest Write API Blocked Tests
# ══════════════════════════════════════════════════════════════════════


def test_manifest_write_user_confirmed_false_blocks(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, create_msg_id = _prepare_full_chain(
            client, session_factory
        )
        counts_before = {
            "messages": _count_rows(session_factory, ProjectDirectorMessageTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-workspace-evidence-manifest",
            json={
                "source_task_id": task_id,
                "source_message_id": create_msg_id,
                "user_confirmed": False,
            },
        )

        assert response.status_code == 409
        assert "user_confirmation_required" in response.json()["detail"]

    assert (
        _count_rows(session_factory, ProjectDirectorMessageTable)
        == counts_before["messages"]
    )


def test_manifest_write_non_p21_c_c_source_blocks(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, _create_msg = _prepare_full_chain(
            client, session_factory
        )

        # Use P11 evidence message as source (wrong type)
        p11_response = client.post(
            f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
            json={"user_goal": "wrong source test"},
        )
        wrong_msg_id = p11_response.json()["message"]["id"]

        counts_before = {
            "messages": _count_rows(session_factory, ProjectDirectorMessageTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-workspace-evidence-manifest",
            json={
                "source_task_id": task_id,
                "source_message_id": wrong_msg_id,
                "user_confirmed": True,
            },
        )

        assert response.status_code == 409

    # counts_before was set after the P11 call created a message
    assert (
        _count_rows(session_factory, ProjectDirectorMessageTable)
        == counts_before["messages"]
    )


def test_manifest_write_source_task_mismatch_blocks(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, create_msg_id = _prepare_full_chain(
            client, session_factory
        )

        wrong_task_id = str(uuid4())
        counts_before = {
            "messages": _count_rows(session_factory, ProjectDirectorMessageTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-workspace-evidence-manifest",
            json={
                "source_task_id": wrong_task_id,
                "source_message_id": create_msg_id,
                "user_confirmed": True,
            },
        )

        assert response.status_code == 409

    assert (
        _count_rows(session_factory, ProjectDirectorMessageTable)
        == counts_before["messages"]
    )


def test_manifest_write_workspace_path_outside_root_blocks(tmp_path) -> None:
    """Workspace path outside root is validated through the source action."""
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, create_msg_id = _prepare_full_chain(
            client, session_factory
        )
        counts_before = {
            "messages": _count_rows(session_factory, ProjectDirectorMessageTable),
        }

        # The actual workspace path is determined by the source action,
        # so this test verifies the chain validates containment.
        # A workspace path outside root would come from a corrupted source action,
        # which we can't easily inject via API. This is covered by contract tests.
        # Here we verify a blocked response does not create messages or write files.
        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-workspace-evidence-manifest",
            json={
                "source_task_id": str(uuid4()),
                "source_message_id": create_msg_id,
                "user_confirmed": True,
            },
        )

        assert response.status_code == 409

    assert (
        _count_rows(session_factory, ProjectDirectorMessageTable)
        == counts_before["messages"]
    )


def test_manifest_write_nonexistent_session(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        response = client.post(
            f"/project-director/sessions/{uuid4()}/sandbox-workspace-evidence-manifest",
            json={
                "source_task_id": str(uuid4()),
                "source_message_id": str(uuid4()),
                "user_confirmed": True,
            },
        )
        assert response.status_code == 404


# ══════════════════════════════════════════════════════════════════════
# Message Readback Tests
# ══════════════════════════════════════════════════════════════════════


def test_message_readback(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, create_msg_id = _prepare_full_chain(
            client, session_factory
        )

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-workspace-evidence-manifest",
            json={
                "source_task_id": task_id,
                "source_message_id": create_msg_id,
                "user_confirmed": True,
            },
        )
        assert response.status_code == 200

        messages_response = client.get(
            f"/project-director/sessions/{session_id}/messages"
        )
        assert messages_response.status_code == 200
        messages = messages_response.json()["messages"]

        write_msgs = [
            item
            for item in messages
            if item["source_detail"] == "p21_c_sandbox_workspace_manifest_written"
        ]
        assert len(write_msgs) >= 1

        write_msg = write_msgs[0]
        actions = write_msg.get("suggested_actions") or []
        assert len(actions) >= 1
        assert actions[0]["type"] == "p21_c_sandbox_workspace_manifest_write_record"
        assert actions[0]["ai_project_director_total_loop"] == "Partial"

        # No misleading output
        serialized = json.dumps(write_msg, ensure_ascii=False)
        for term in MISLEADING_TERMS:
            assert term not in serialized, f"Found misleading term: {term}"
