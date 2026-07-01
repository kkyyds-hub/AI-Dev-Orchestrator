"""API integration tests for P21-C-E controlled sandbox candidate business file write."""

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
    "已写主项目文件",
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
    db_path = tmp_path / "orchestrator-p21ce-test.db"
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


def _record_p15_review_message(sqlite_session_factory, *, session_id, source_task_id, source_message_id):
    from app.services.project_director_readonly_review_service import ProjectDirectorReadonlyReviewService
    db = sqlite_session_factory()
    try:
        svc = ProjectDirectorReadonlyReviewService(
            session_repository=ProjectDirectorSessionRepository(db),
            message_repository=ProjectDirectorMessageRepository(db),
            task_repository=TaskRepository(db),
        )
        r = svc.confirm_review(
            session_id=UUID(session_id), source_task_id=UUID(source_task_id),
            source_message_id=UUID(source_message_id), user_confirmed=True,
            requested_reviewer_executor="codex", review_mode="fake_review",
        )
        return str(r.message.id)
    finally:
        db.close()


def _record_p16_plan_message(sqlite_session_factory, *, session_id, source_task_id, source_message_id):
    from app.services.project_director_programmer_no_write_plan_service import ProjectDirectorProgrammerNoWritePlanService
    db = sqlite_session_factory()
    try:
        svc = ProjectDirectorProgrammerNoWritePlanService(
            session_repository=ProjectDirectorSessionRepository(db),
            message_repository=ProjectDirectorMessageRepository(db),
            task_repository=TaskRepository(db),
        )
        r = svc.confirm_plan(
            session_id=UUID(session_id), source_task_id=UUID(source_task_id),
            source_message_id=UUID(source_message_id), user_confirmed=True,
            requested_programmer_executor="codex", planning_mode="fake_plan",
        )
        return str(r.message.id)
    finally:
        db.close()


def _record_p17_execution_message(sqlite_session_factory, *, session_id, source_task_id, source_message_id):
    from app.services.project_director_programmer_no_write_execution_service import ProjectDirectorProgrammerNoWriteExecutionService
    db = sqlite_session_factory()
    try:
        svc = ProjectDirectorProgrammerNoWriteExecutionService(
            session_repository=ProjectDirectorSessionRepository(db),
            message_repository=ProjectDirectorMessageRepository(db),
            task_repository=TaskRepository(db),
        )
        r = svc.confirm_execution(
            session_id=UUID(session_id), source_task_id=UUID(source_task_id),
            source_message_id=UUID(source_message_id), user_confirmed=True,
            requested_programmer_executor="codex", execution_mode="fake_execution",
        )
        return str(r.message.id)
    finally:
        db.close()


def _prepare_full_chain(client, sqlite_session_factory):
    """Build full chain through P21-C-D. Returns (session_id, task_id, p21_c_d_msg_id)."""
    s = client.post("/project-director/sessions", json={"goal_text": "P21-C-E test"})
    assert s.status_code == 201
    session_id = s.json()["id"]

    p11 = client.post(
        f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
        json={"user_goal": "P21-C-E evidence"},
    )
    assert p11.status_code == 200

    p12 = client.post(
        f"/project-director/sessions/{session_id}/dry-run-task-dispatch",
        json={"source_message_id": p11.json()["message"]["id"], "user_confirmed": True},
    )
    assert p12.status_code == 200
    task_id = p12.json()["created_task_id"]
    p12_msg_id = p12.json()["message"]["id"]

    client.post("/workers/run-once")

    client.post(
        f"/project-director/sessions/{session_id}/controlled-executor-dispatch",
        json={
            "source_task_id": task_id, "source_message_id": p12_msg_id,
            "user_confirmed": True, "requested_agent_role": "programmer",
            "requested_executor": "codex", "launch_mode": "dry_run",
        },
    )

    p14_id = _record_p14_lifecycle_message(
        sqlite_session_factory, session_id=session_id,
        source_task_id=task_id, source_message_id=p12_msg_id,
    )
    p15_id = _record_p15_review_message(
        sqlite_session_factory, session_id=session_id,
        source_task_id=task_id, source_message_id=p14_id,
    )
    p16_id = _record_p16_plan_message(
        sqlite_session_factory, session_id=session_id,
        source_task_id=task_id, source_message_id=p15_id,
    )
    p17_id = _record_p17_execution_message(
        sqlite_session_factory, session_id=session_id,
        source_task_id=task_id, source_message_id=p16_id,
    )

    # P20
    p20 = client.post(
        f"/project-director/sessions/{session_id}/sandbox-write-preflight",
        json={
            "source_task_id": task_id, "source_message_id": p17_id,
            "user_confirmed": True, "preflight_mode": "dry_run",
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
    assert p20.status_code == 200

    # P21-A
    p21 = client.post(
        f"/project-director/sessions/{session_id}/sandbox-write-execution",
        json={
            "source_task_id": task_id, "source_message_id": p20.json()["message"]["id"],
            "user_confirmed": True, "execution_mode": "dry_run",
        },
    )
    assert p21.status_code == 200

    # P21-B
    lock = client.post(
        f"/project-director/sessions/{session_id}/sandbox-write-design-lock",
        json={
            "source_task_id": task_id, "source_message_id": p21.json()["message"]["id"],
            "user_confirmed": True,
        },
    )
    assert lock.status_code == 200

    # P21-C-A
    guard = client.post(
        f"/project-director/sessions/{session_id}/sandbox-workspace-guard",
        json={
            "source_task_id": task_id, "source_message_id": lock.json()["message"]["id"],
            "user_confirmed": True,
        },
    )
    assert guard.status_code == 200

    # P21-C-B
    manifest = client.post(
        f"/project-director/sessions/{session_id}/sandbox-operation-manifest-guard",
        json={
            "source_task_id": task_id, "source_message_id": guard.json()["message"]["id"],
            "user_confirmed": True,
        },
    )
    assert manifest.status_code == 200

    # P21-C-C
    create = client.post(
        f"/project-director/sessions/{session_id}/sandbox-workspace-create",
        json={
            "source_task_id": task_id, "source_message_id": manifest.json()["message"]["id"],
            "user_confirmed": True,
        },
    )
    assert create.status_code == 200

    # P21-C-D
    write = client.post(
        f"/project-director/sessions/{session_id}/sandbox-workspace-evidence-manifest",
        json={
            "source_task_id": task_id, "source_message_id": create.json()["message"]["id"],
            "user_confirmed": True,
        },
    )
    assert write.status_code == 200

    return session_id, task_id, write.json()["message"]["id"]


# ══════════════════════════════════════════════════════════════════════
# P21-C-E Success Tests
# ══════════════════════════════════════════════════════════════════════


def test_candidate_write_success(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p21cd_msg_id = _prepare_full_chain(client, session_factory)
        counts_before = {
            "tasks": _count_rows(session_factory, TaskTable),
            "runs": _count_rows(session_factory, RunTable),
            "messages": _count_rows(session_factory, ProjectDirectorMessageTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/sandbox-candidate-files-write",
            json={
                "source_task_id": task_id,
                "source_message_id": p21cd_msg_id,
                "user_confirmed": True,
                "candidate_files": [
                    {
                        "relative_path": "runtime/orchestrator/app/domain/example.py",
                        "content": "print('candidate write test')\n",
                        "operation": "create",
                    },
                ],
            },
        )

        assert response.status_code == 200
        payload = response.json()

        assert payload["candidate_write_status"] == "written"
        assert payload["candidate_files_written_count"] == 1
        assert payload["candidate_files_blocked_count"] == 0
        assert payload["candidate_business_files_written"] is True
        assert payload["business_file_written"] is True
        assert payload["manifest_file_written"] is False
        assert payload["target_file_content_read"] is False
        assert payload["real_diff_generated"] is False
        assert payload["patch_applied"] is False
        assert payload["worktree_created"] is False
        assert payload["git_write_performed"] is False
        assert payload["source_manifest_write_verified"] is True
        assert payload["internal_manifest_verified"] is True
        assert payload["ai_project_director_total_loop"] == "Partial"

        for flag in ALL_WRITE_FLAGS:
            assert payload[flag] is False, f"{flag} should be False"

        # Verify workspace
        ws_path = Path(payload["workspace_path"])
        assert ws_path.exists()
        assert ws_path.is_dir()
        assert ".ai-project-director" not in payload["workspace_path"]

        # Verify candidate file
        written_files = payload["candidate_written_files"]
        assert len(written_files) == 1
        candidate_path = Path(written_files[0]["workspace_file_path"])
        assert candidate_path.exists()
        assert candidate_path.read_text(encoding="utf-8") == "print('candidate write test')\n"
        assert ".ai-project-director" not in str(candidate_path)

        # Internal manifest still exists
        manifest_path = ws_path / ".ai-project-director" / "workspace-manifest.json"
        assert manifest_path.exists()
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest_data["schema_version"] == "p21-c-d.v1"

        # Message exists
        assert payload["message"] is not None
        assert payload["message"]["source_detail"] == "p21_c_sandbox_candidate_files_written"
        actions = payload["message"].get("suggested_actions") or []
        assert len(actions) >= 1
        assert actions[0]["type"] == "p21_c_sandbox_candidate_files_write_record"

    # Exactly 1 message created, no Task/Run
    assert _count_rows(session_factory, TaskTable) == counts_before["tasks"]
    assert _count_rows(session_factory, RunTable) == counts_before["runs"]
    assert _count_rows(session_factory, ProjectDirectorMessageTable) == counts_before["messages"] + 1


# ══════════════════════════════════════════════════════════════════════
# P21-C-E Blocked Tests
# ══════════════════════════════════════════════════════════════════════


def test_candidate_write_user_confirmed_false_blocks(tmp_path) -> None:
    sf = _sqlite_session_factory(tmp_path)
    app = _app(sf)
    with TestClient(app) as client:
        sid, tid, msg_id = _prepare_full_chain(client, sf)
        msgs_before = _count_rows(sf, ProjectDirectorMessageTable)
        r = client.post(
            f"/project-director/sessions/{sid}/sandbox-candidate-files-write",
            json={
                "source_task_id": tid, "source_message_id": msg_id,
                "user_confirmed": False,
                "candidate_files": [{"relative_path": "x.py", "content": "x", "operation": "create"}],
            },
        )
        assert r.status_code == 409
        assert "user_confirmation_required" in r.json()["detail"]
        assert _count_rows(sf, ProjectDirectorMessageTable) == msgs_before


def test_candidate_write_non_p21cd_source_blocks(tmp_path) -> None:
    sf = _sqlite_session_factory(tmp_path)
    app = _app(sf)
    with TestClient(app) as client:
        sid, tid, _msg_id = _prepare_full_chain(client, sf)
        # Use P11 evidence message as wrong source
        p11 = client.post(
            f"/project-director/sessions/{sid}/evidence-to-agent/dry-run",
            json={"user_goal": "wrong source"},
        )
        wrong_msg = p11.json()["message"]["id"]
        msgs_before = _count_rows(sf, ProjectDirectorMessageTable)
        r = client.post(
            f"/project-director/sessions/{sid}/sandbox-candidate-files-write",
            json={
                "source_task_id": tid, "source_message_id": wrong_msg,
                "user_confirmed": True,
                "candidate_files": [{"relative_path": "x.py", "content": "x", "operation": "create"}],
            },
        )
        assert r.status_code == 409
        assert _count_rows(sf, ProjectDirectorMessageTable) == msgs_before


def test_candidate_write_source_task_mismatch_blocks(tmp_path) -> None:
    sf = _sqlite_session_factory(tmp_path)
    app = _app(sf)
    with TestClient(app) as client:
        sid, tid, msg_id = _prepare_full_chain(client, sf)
        msgs_before = _count_rows(sf, ProjectDirectorMessageTable)
        r = client.post(
            f"/project-director/sessions/{sid}/sandbox-candidate-files-write",
            json={
                "source_task_id": str(uuid4()), "source_message_id": msg_id,
                "user_confirmed": True,
                "candidate_files": [{"relative_path": "x.py", "content": "x", "operation": "create"}],
            },
        )
        assert r.status_code == 409
        assert _count_rows(sf, ProjectDirectorMessageTable) == msgs_before


def test_candidate_write_path_not_declared_blocks(tmp_path) -> None:
    sf = _sqlite_session_factory(tmp_path)
    app = _app(sf)
    with TestClient(app) as client:
        sid, tid, msg_id = _prepare_full_chain(client, sf)
        msgs_before = _count_rows(sf, ProjectDirectorMessageTable)
        r = client.post(
            f"/project-director/sessions/{sid}/sandbox-candidate-files-write",
            json={
                "source_task_id": tid, "source_message_id": msg_id,
                "user_confirmed": True,
                "candidate_files": [
                    {"relative_path": "src/undeclared.py", "content": "x", "operation": "create"},
                ],
            },
        )
        assert r.status_code == 409
        assert "candidate_file_path_not_declared_by_manifest" in r.json()["detail"]
        assert _count_rows(sf, ProjectDirectorMessageTable) == msgs_before


def test_candidate_write_internal_dir_blocks(tmp_path) -> None:
    sf = _sqlite_session_factory(tmp_path)
    app = _app(sf)
    with TestClient(app) as client:
        sid, tid, msg_id = _prepare_full_chain(client, sf)
        msgs_before = _count_rows(sf, ProjectDirectorMessageTable)
        r = client.post(
            f"/project-director/sessions/{sid}/sandbox-candidate-files-write",
            json={
                "source_task_id": tid, "source_message_id": msg_id,
                "user_confirmed": True,
                "candidate_files": [
                    {
                        "relative_path": ".ai-project-director/extra.json",
                        "content": "{}",
                        "operation": "create",
                    },
                ],
            },
        )
        assert r.status_code == 409
        assert _count_rows(sf, ProjectDirectorMessageTable) == msgs_before


def test_candidate_write_dotdot_blocks(tmp_path) -> None:
    sf = _sqlite_session_factory(tmp_path)
    app = _app(sf)
    with TestClient(app) as client:
        sid, tid, msg_id = _prepare_full_chain(client, sf)
        msgs_before = _count_rows(sf, ProjectDirectorMessageTable)
        r = client.post(
            f"/project-director/sessions/{sid}/sandbox-candidate-files-write",
            json={
                "source_task_id": tid, "source_message_id": msg_id,
                "user_confirmed": True,
                "candidate_files": [
                    {"relative_path": "../escape.py", "content": "x", "operation": "create"},
                ],
            },
        )
        assert r.status_code == 409
        assert _count_rows(sf, ProjectDirectorMessageTable) == msgs_before


def test_candidate_write_backslash_blocks(tmp_path) -> None:
    sf = _sqlite_session_factory(tmp_path)
    app = _app(sf)
    with TestClient(app) as client:
        sid, tid, msg_id = _prepare_full_chain(client, sf)
        msgs_before = _count_rows(sf, ProjectDirectorMessageTable)
        r = client.post(
            f"/project-director/sessions/{sid}/sandbox-candidate-files-write",
            json={
                "source_task_id": tid, "source_message_id": msg_id,
                "user_confirmed": True,
                "candidate_files": [
                    {"relative_path": "foo\\bar.py", "content": "x", "operation": "create"},
                ],
            },
        )
        assert r.status_code == 409
        assert _count_rows(sf, ProjectDirectorMessageTable) == msgs_before


def test_candidate_write_operation_mismatch_blocks(tmp_path) -> None:
    sf = _sqlite_session_factory(tmp_path)
    app = _app(sf)
    with TestClient(app) as client:
        sid, tid, msg_id = _prepare_full_chain(client, sf)
        msgs_before = _count_rows(sf, ProjectDirectorMessageTable)
        # Manifest declares "create" for example.py, request uses "update"
        r = client.post(
            f"/project-director/sessions/{sid}/sandbox-candidate-files-write",
            json={
                "source_task_id": tid, "source_message_id": msg_id,
                "user_confirmed": True,
                "candidate_files": [
                    {
                        "relative_path": "runtime/orchestrator/app/domain/example.py",
                        "content": "x",
                        "operation": "update",
                    },
                ],
            },
        )
        assert r.status_code == 409
        assert "candidate_file_operation_not_allowed" in r.json()["detail"]
        assert _count_rows(sf, ProjectDirectorMessageTable) == msgs_before


def test_candidate_write_content_too_large_blocks(tmp_path) -> None:
    sf = _sqlite_session_factory(tmp_path)
    app = _app(sf)
    with TestClient(app) as client:
        sid, tid, msg_id = _prepare_full_chain(client, sf)
        msgs_before = _count_rows(sf, ProjectDirectorMessageTable)
        big = "x" * (200 * 1024 + 1)
        r = client.post(
            f"/project-director/sessions/{sid}/sandbox-candidate-files-write",
            json={
                "source_task_id": tid, "source_message_id": msg_id,
                "user_confirmed": True,
                "candidate_files": [
                    {
                        "relative_path": "runtime/orchestrator/app/domain/example.py",
                        "content": big,
                        "operation": "create",
                    },
                ],
            },
        )
        assert r.status_code == 409
        assert _count_rows(sf, ProjectDirectorMessageTable) == msgs_before


# ══════════════════════════════════════════════════════════════════════
# Message Readback
# ══════════════════════════════════════════════════════════════════════


def test_message_readback(tmp_path) -> None:
    sf = _sqlite_session_factory(tmp_path)
    app = _app(sf)
    with TestClient(app) as client:
        sid, tid, msg_id = _prepare_full_chain(client, sf)

        r = client.post(
            f"/project-director/sessions/{sid}/sandbox-candidate-files-write",
            json={
                "source_task_id": tid, "source_message_id": msg_id,
                "user_confirmed": True,
                "candidate_files": [
                    {
                        "relative_path": "runtime/orchestrator/app/domain/example.py",
                        "content": "print('readback')",
                        "operation": "create",
                    },
                ],
            },
        )
        assert r.status_code == 200

        msgs = client.get(f"/project-director/sessions/{sid}/messages").json()["messages"]
        write_msgs = [m for m in msgs if m["source_detail"] == "p21_c_sandbox_candidate_files_written"]
        assert len(write_msgs) >= 1

        actions = write_msgs[0].get("suggested_actions") or []
        assert len(actions) >= 1
        assert actions[0]["type"] == "p21_c_sandbox_candidate_files_write_record"
        assert actions[0]["ai_project_director_total_loop"] == "Partial"

        serialized = json.dumps(write_msgs[0], ensure_ascii=False)
        for term in MISLEADING_TERMS:
            assert term not in serialized, f"Found misleading term: {term}"
