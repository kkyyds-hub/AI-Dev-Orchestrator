"""API integration tests for P21-C-H-A readonly review execution preflight."""

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
from app.services.project_director_sandbox_candidate_diff_review_execution_preflight_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_EXECUTION_PREFLIGHT_SOURCE_DETAIL,
    REVIEW_INPUT_SCHEMA_VERSION,
    REVIEW_OUTPUT_SCHEMA_VERSION,
)


MISLEADING_TERMS = {
    "审查通过", "review passed", "已批准", "可以合入", "可以提交",
    "代码正确", "无风险", "reviewer 已启动", "review 已执行",
    "findings 已生成", "verdict 已生成", "已应用 patch",
    "已创建 worktree", "已执行 Git 写",
}


def _sf(tmp_path):
    db_path = tmp_path / "orchestrator-p21cha-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _app(sf) -> FastAPI:
    app = FastAPI()
    app.include_router(api_router)
    def override():
        s = sf()
        try:
            yield s
        finally:
            s.close()
    app.dependency_overrides[get_db_session] = override
    return app


def _count(sf, table) -> int:
    s = sf()
    try:
        return s.execute(select(func.count()).select_from(table)).scalar_one()
    finally:
        s.close()


def _p14(sf, *, session_id, source_task_id, source_message_id):
    db = sf()
    try:
        svc = ProjectDirectorControlledExecutorDispatchService(
            session_repository=ProjectDirectorSessionRepository(db),
            message_repository=ProjectDirectorMessageRepository(db),
            task_repository=TaskRepository(db),
        )
        msg = svc.record_lifecycle_result(
            result=ProjectDirectorControlledExecutorLifecycleResult(
                session_id=UUID(session_id), source_task_id=UUID(source_task_id),
                source_message_id=UUID(source_message_id), requested_agent_role="programmer",
                requested_executor="codex", launch_mode="dry_run",
                product_runtime_git_write_allowed=False, worktree_write_allowed=False,
                frontend_required=False, run_created=True, real_code_modified=False,
                git_write_performed=False, ai_project_director_total_loop="Partial",
            ), source_detail=P14_LIFECYCLE_RESULT_SOURCE_DETAIL,
        )
        return str(msg.id)
    finally:
        db.close()


def _p15(sf, **kw):
    from app.services.project_director_readonly_review_service import ProjectDirectorReadonlyReviewService
    db = sf()
    try:
        svc = ProjectDirectorReadonlyReviewService(
            session_repository=ProjectDirectorSessionRepository(db),
            message_repository=ProjectDirectorMessageRepository(db),
            task_repository=TaskRepository(db),
        )
        r = svc.confirm_review(session_id=UUID(kw["session_id"]), source_task_id=UUID(kw["source_task_id"]),
                               source_message_id=UUID(kw["source_message_id"]), user_confirmed=True,
                               requested_reviewer_executor="codex", review_mode="fake_review")
        return str(r.message.id)
    finally:
        db.close()


def _p16(sf, **kw):
    from app.services.project_director_programmer_no_write_plan_service import ProjectDirectorProgrammerNoWritePlanService
    db = sf()
    try:
        svc = ProjectDirectorProgrammerNoWritePlanService(
            session_repository=ProjectDirectorSessionRepository(db),
            message_repository=ProjectDirectorMessageRepository(db),
            task_repository=TaskRepository(db),
        )
        r = svc.confirm_plan(session_id=UUID(kw["session_id"]), source_task_id=UUID(kw["source_task_id"]),
                             source_message_id=UUID(kw["source_message_id"]), user_confirmed=True,
                             requested_programmer_executor="codex", planning_mode="fake_plan")
        return str(r.message.id)
    finally:
        db.close()


def _p17(sf, **kw):
    from app.services.project_director_programmer_no_write_execution_service import ProjectDirectorProgrammerNoWriteExecutionService
    db = sf()
    try:
        svc = ProjectDirectorProgrammerNoWriteExecutionService(
            session_repository=ProjectDirectorSessionRepository(db),
            message_repository=ProjectDirectorMessageRepository(db),
            task_repository=TaskRepository(db),
        )
        r = svc.confirm_execution(session_id=UUID(kw["session_id"]), source_task_id=UUID(kw["source_task_id"]),
                                  source_message_id=UUID(kw["source_message_id"]), user_confirmed=True,
                                  requested_programmer_executor="codex", execution_mode="fake_execution")
        return str(r.message.id)
    finally:
        db.close()


def _prepare_full_chain(client, sf):
    s = client.post("/project-director/sessions", json={"goal_text": "P21-C-H-A test"})
    assert s.status_code == 201
    sid = s.json()["id"]

    p11 = client.post(f"/project-director/sessions/{sid}/evidence-to-agent/dry-run",
                      json={"user_goal": "P21-C-H-A evidence"})
    p12 = client.post(f"/project-director/sessions/{sid}/dry-run-task-dispatch",
                      json={"source_message_id": p11.json()["message"]["id"], "user_confirmed": True})
    tid = p12.json()["created_task_id"]
    p12m = p12.json()["message"]["id"]

    client.post("/workers/run-once")
    client.post(f"/project-director/sessions/{sid}/controlled-executor-dispatch",
                json={"source_task_id": tid, "source_message_id": p12m,
                      "user_confirmed": True, "requested_agent_role": "programmer",
                      "requested_executor": "codex", "launch_mode": "dry_run"})

    p14 = _p14(sf, session_id=sid, source_task_id=tid, source_message_id=p12m)
    p15 = _p15(sf, session_id=sid, source_task_id=tid, source_message_id=p14)
    p16 = _p16(sf, session_id=sid, source_task_id=tid, source_message_id=p15)
    p17 = _p17(sf, session_id=sid, source_task_id=tid, source_message_id=p16)

    p20 = client.post(f"/project-director/sessions/{sid}/sandbox-write-preflight",
                      json={"source_task_id": tid, "source_message_id": p17,
                            "user_confirmed": True, "preflight_mode": "dry_run",
                            "file_operations": [
                                {"path": "runtime/orchestrator/app/domain/new_module.py", "operation": "create",
                                 "reason": "test", "patch_preview": ["PREVIEW ONLY: no repository file was modified."]}]})
    p21 = client.post(f"/project-director/sessions/{sid}/sandbox-write-execution",
                      json={"source_task_id": tid, "source_message_id": p20.json()["message"]["id"],
                            "user_confirmed": True, "execution_mode": "dry_run"})
    lock = client.post(f"/project-director/sessions/{sid}/sandbox-write-design-lock",
                       json={"source_task_id": tid, "source_message_id": p21.json()["message"]["id"],
                             "user_confirmed": True})
    guard = client.post(f"/project-director/sessions/{sid}/sandbox-workspace-guard",
                        json={"source_task_id": tid, "source_message_id": lock.json()["message"]["id"],
                              "user_confirmed": True})
    manifest = client.post(f"/project-director/sessions/{sid}/sandbox-operation-manifest-guard",
                           json={"source_task_id": tid, "source_message_id": guard.json()["message"]["id"],
                                 "user_confirmed": True})
    create = client.post(f"/project-director/sessions/{sid}/sandbox-workspace-create",
                         json={"source_task_id": tid, "source_message_id": manifest.json()["message"]["id"],
                               "user_confirmed": True})
    write = client.post(f"/project-director/sessions/{sid}/sandbox-workspace-evidence-manifest",
                        json={"source_task_id": tid, "source_message_id": create.json()["message"]["id"],
                              "user_confirmed": True})
    ce = client.post(f"/project-director/sessions/{sid}/sandbox-candidate-files-write",
                     json={"source_task_id": tid, "source_message_id": write.json()["message"]["id"],
                           "user_confirmed": True,
                           "candidate_files": [{"relative_path": "runtime/orchestrator/app/domain/new_module.py",
                                                "content": "print('new')\n", "operation": "create"}]})
    diff = client.post(f"/project-director/sessions/{sid}/sandbox-candidate-diff-generate",
                       json={"source_task_id": tid, "source_message_id": ce.json()["message"]["id"],
                             "user_confirmed": True})
    handoff = client.post(f"/project-director/sessions/{sid}/sandbox-candidate-diff-review-handoff",
                          json={"source_task_id": tid, "source_message_id": diff.json()["message"]["id"],
                                "user_confirmed": True})
    assert handoff.status_code == 200

    return sid, tid, handoff.json()["message"]["id"]


# ══════════════════════════════════════════════════════════════════════
# Success
# ══════════════════════════════════════════════════════════════════════


def test_preflight_success(tmp_path) -> None:
    sf = _sf(tmp_path)
    app = _app(sf)
    with TestClient(app) as client:
        sid, tid, handoff_msg_id = _prepare_full_chain(client, sf)
        msgs_before = _count(sf, ProjectDirectorMessageTable)
        tasks_before = _count(sf, TaskTable)
        runs_before = _count(sf, RunTable)

        r = client.post(
            f"/project-director/sessions/{sid}/sandbox-candidate-diff-review-execution-preflight",
            json={"source_task_id": tid, "source_message_id": handoff_msg_id, "user_confirmed": True},
        )
        assert r.status_code == 200
        p = r.json()

        assert p["review_execution_preflight_status"] == "ready"
        assert p["source_handoff_verified"] is True
        assert p["source_diff_verified"] is True
        assert len(p["source_diff_sha256"]) == 64
        assert len(p["review_prompt_sha256"]) == 64
        assert p["review_prompt_bytes"] > 0
        assert p["review_input_schema_version"] == REVIEW_INPUT_SCHEMA_VERSION
        assert p["review_output_schema_version"] == REVIEW_OUTPUT_SCHEMA_VERSION
        assert len(p["review_scope_paths"]) >= 1
        assert p["reviewer_started"] is False
        assert p["review_executed"] is False
        assert p["provider_called"] is False
        assert p["codex_started"] is False
        assert p["claude_code_started"] is False
        assert p["main_project_file_written"] is False
        assert p["patch_applied"] is False
        assert p["git_write_performed"] is False
        assert p["worker_started"] is False
        assert p["task_created"] is False
        assert p["run_created"] is False
        assert p["ai_project_director_total_loop"] == "Partial"

        assert p["message"] is not None
        assert p["message"]["source_detail"] == P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_EXECUTION_PREFLIGHT_SOURCE_DETAIL
        actions = p["message"].get("suggested_actions") or []
        assert len(actions) >= 1
        assert actions[0]["type"] == "p21_c_sandbox_candidate_diff_review_execution_preflight_record"
        assert actions[0]["source_diff_sha256"] == p["source_diff_sha256"]
        assert actions[0]["review_prompt_sha256"] == p["review_prompt_sha256"]

    assert _count(sf, ProjectDirectorMessageTable) == msgs_before + 1
    assert _count(sf, TaskTable) == tasks_before
    assert _count(sf, RunTable) == runs_before


# ══════════════════════════════════════════════════════════════════════
# Blocked
# ══════════════════════════════════════════════════════════════════════


def test_preflight_user_confirmed_false_blocks(tmp_path) -> None:
    sf = _sf(tmp_path)
    app = _app(sf)
    with TestClient(app) as client:
        sid, tid, handoff_msg_id = _prepare_full_chain(client, sf)
        msgs_before = _count(sf, ProjectDirectorMessageTable)
        r = client.post(
            f"/project-director/sessions/{sid}/sandbox-candidate-diff-review-execution-preflight",
            json={"source_task_id": tid, "source_message_id": handoff_msg_id, "user_confirmed": False},
        )
        assert r.status_code == 409
        assert "user_confirmation_required" in r.json()["detail"]
        assert _count(sf, ProjectDirectorMessageTable) == msgs_before


def test_preflight_non_handoff_source_blocks(tmp_path) -> None:
    sf = _sf(tmp_path)
    app = _app(sf)
    with TestClient(app) as client:
        sid, tid, _ = _prepare_full_chain(client, sf)
        p11 = client.post(f"/project-director/sessions/{sid}/evidence-to-agent/dry-run",
                          json={"user_goal": "wrong source"})
        wrong = p11.json()["message"]["id"]
        msgs_before = _count(sf, ProjectDirectorMessageTable)
        r = client.post(
            f"/project-director/sessions/{sid}/sandbox-candidate-diff-review-execution-preflight",
            json={"source_task_id": tid, "source_message_id": wrong, "user_confirmed": True},
        )
        assert r.status_code == 409
        assert _count(sf, ProjectDirectorMessageTable) == msgs_before


def test_preflight_task_mismatch_blocks(tmp_path) -> None:
    sf = _sf(tmp_path)
    app = _app(sf)
    with TestClient(app) as client:
        sid, tid, handoff_msg_id = _prepare_full_chain(client, sf)
        msgs_before = _count(sf, ProjectDirectorMessageTable)
        r = client.post(
            f"/project-director/sessions/{sid}/sandbox-candidate-diff-review-execution-preflight",
            json={"source_task_id": str(uuid4()), "source_message_id": handoff_msg_id, "user_confirmed": True},
        )
        assert r.status_code == 409
        assert _count(sf, ProjectDirectorMessageTable) == msgs_before


# ══════════════════════════════════════════════════════════════════════
# Message Readback
# ══════════════════════════════════════════════════════════════════════


def test_message_readback(tmp_path) -> None:
    sf = _sf(tmp_path)
    app = _app(sf)
    with TestClient(app) as client:
        sid, tid, handoff_msg_id = _prepare_full_chain(client, sf)
        r = client.post(
            f"/project-director/sessions/{sid}/sandbox-candidate-diff-review-execution-preflight",
            json={"source_task_id": tid, "source_message_id": handoff_msg_id, "user_confirmed": True},
        )
        assert r.status_code == 200

        msgs = client.get(f"/project-director/sessions/{sid}/messages").json()["messages"]
        preflight_msgs = [m for m in msgs
                          if m["source_detail"] == P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_EXECUTION_PREFLIGHT_SOURCE_DETAIL]
        assert len(preflight_msgs) >= 1
        actions = preflight_msgs[0].get("suggested_actions") or []
        assert len(actions) >= 1
        assert actions[0]["type"] == "p21_c_sandbox_candidate_diff_review_execution_preflight_record"

        serialized = json.dumps(preflight_msgs[0], ensure_ascii=False)
        for term in MISLEADING_TERMS:
            assert term not in serialized, f"Found misleading term: {term}"
