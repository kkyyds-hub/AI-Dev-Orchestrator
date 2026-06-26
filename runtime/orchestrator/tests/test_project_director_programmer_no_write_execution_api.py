"""API integration tests for P17 programmer no-write execution."""

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

FORBIDDEN_TOKEN_SUBSTRINGS = {"api_key", "token_value", "auth_token", "bearer"}

FORBIDDEN_OUTPUT_TEXTS = {
    "已执行提交",
    "已推送",
    "PR 已创建",
    "代码已写入",
    "代码已修改",
    "已授权 Git 写",
    "已启动 Codex",
    "已启动 Claude",
}

FORBIDDEN_DIFF_PATTERNS = ["diff --git", "+++ b/", "--- a/", "@@"]

ALL_APPLYABLE_DIFF_MARKERS = [
    "diff --git",
    "--- a/",
    "+++ b/",
    "@@",
    "index ",
    "new file mode ",
    "deleted file mode ",
    "rename from ",
    "rename to ",
]


def _sqlite_session_factory(tmp_path):
    db_path = tmp_path / "orchestrator-p17-test.db"
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


def _prepare_p17_chain(
    client: TestClient,
    sqlite_session_factory,
) -> tuple[str, str, str, str]:
    """Prepare full P11→P12→P13→P14→P15→P16 chain.

    Returns (session_id, task_id, p16_message_id, p12_source_msg_id).
    """
    session_response = client.post(
        "/project-director/sessions",
        json={"goal_text": "P17 programmer no-write execution test"},
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["id"]

    p11_response = client.post(
        f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
        json={"user_goal": "P17 test evidence"},
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

    return session_id, task_id, p16_message_id, p12_source_msg_id


# ── A. dry_run success ────────────────────────────────────────────────


def test_p17_dry_run_success(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p16_msg_id, _ = _prepare_p17_chain(
            client, session_factory
        )
        counts_before = {
            "tasks": _count_rows(session_factory, TaskTable),
            "runs": _count_rows(session_factory, RunTable),
            "messages": _count_rows(session_factory, ProjectDirectorMessageTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/programmer-no-write-execution",
            json={
                "source_task_id": task_id,
                "source_message_id": p16_msg_id,
                "user_confirmed": True,
                "requested_programmer_executor": "codex",
                "execution_mode": "dry_run",
            },
        )

        assert response.status_code == 200
        payload = response.json()

        assert payload["execution_status"] == "planned"
        assert payload["execution_mode"] == "dry_run"
        assert payload["programmer_agent"] is True
        assert payload["controlled_programmer_execution"] is True
        assert payload["no_write_execution"] is True
        assert payload["executor_backed_programmer_allowed"] is True
        assert payload["product_runtime_git_write_allowed"] is False
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
        assert payload["execution_message_bound"] is True
        assert payload["message"] is not None
        assert payload["message"]["source_detail"] == "p17_programmer_no_write_execution"
        assert payload["execution_summary"]
        assert len(payload["execution_steps"]) >= 1
        assert p16_msg_id in payload["source_plan_refs"]
        assert payload["ai_project_director_total_loop"] == "Partial"

        # P18: patch_preview safety assertions
        for line in payload.get("patch_preview", []):
            for marker in ALL_APPLYABLE_DIFF_MARKERS:
                assert not line.startswith(marker), (
                    f"dry_run patch_preview leaked applyable diff marker: {marker}"
                )
        for step in payload.get("execution_steps", []):
            for line in step.get("patch_preview", []):
                for marker in ALL_APPLYABLE_DIFF_MARKERS:
                    assert not line.startswith(marker), (
                        f"dry_run execution_step patch_preview leaked: {marker}"
                    )

        messages_response = client.get(
            f"/project-director/sessions/{session_id}/messages"
        )
        assert messages_response.status_code == 200
        messages = messages_response.json()["messages"]
        p17_msgs = [
            item for item in messages
            if item["source_detail"] == "p17_programmer_no_write_execution"
        ]
        assert len(p17_msgs) >= 1

    assert _count_rows(session_factory, TaskTable) == counts_before["tasks"]
    assert _count_rows(session_factory, RunTable) == counts_before["runs"]
    assert (
        _count_rows(session_factory, ProjectDirectorMessageTable)
        == counts_before["messages"] + 1
    )


# ── B. fake_execution success ─────────────────────────────────────────


def test_p17_fake_execution_success(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p16_msg_id, _ = _prepare_p17_chain(
            client, session_factory
        )
        counts_before = {
            "tasks": _count_rows(session_factory, TaskTable),
            "runs": _count_rows(session_factory, RunTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/programmer-no-write-execution",
            json={
                "source_task_id": task_id,
                "source_message_id": p16_msg_id,
                "user_confirmed": True,
                "execution_mode": "fake_execution",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["execution_status"] == "executed"
        assert payload["execution_mode"] == "fake_execution"
        assert len(payload["execution_steps"]) >= 2

        all_patch = []
        for step in payload["execution_steps"]:
            all_patch.extend(step.get("patch_preview", []))
        assert len(all_patch) >= 1
        for line in all_patch:
            assert "PREVIEW ONLY" in line.upper() or "PREVIEW" in line.upper() or "no repository file" in line.lower()

        # P18: patch_preview safety - no applyable diff markers in API output
        for line in payload.get("patch_preview", []):
            for marker in ALL_APPLYABLE_DIFF_MARKERS:
                assert not line.startswith(marker), (
                    f"fake_execution patch_preview leaked: {marker}"
                )
        for step in payload.get("execution_steps", []):
            for line in step.get("patch_preview", []):
                for marker in ALL_APPLYABLE_DIFF_MARKERS:
                    assert not line.startswith(marker), (
                        f"fake_execution step patch_preview leaked: {marker}"
                    )

        assert payload["actual_patch_applied"] is False
        assert payload["file_write_allowed"] is False
        assert payload["product_runtime_git_write_allowed"] is False
        assert payload["worktree_write_allowed"] is False
        assert payload["git_write_performed"] is False

        assert len(payload["implementation_notes"]) >= 1
        assert len(payload["handoff_notes"]) >= 1
        assert len(payload["risks"]) >= 1

        all_tests = []
        for step in payload["execution_steps"]:
            all_tests.extend(step.get("tests_to_run", []))
        assert len(all_tests) >= 1

    assert _count_rows(session_factory, TaskTable) == counts_before["tasks"]
    assert _count_rows(session_factory, RunTable) == counts_before["runs"]


# ── C. user_confirmed=false blocked ──────────────────────────────────


def test_p17_requires_user_confirmation(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p16_msg_id, _ = _prepare_p17_chain(
            client, session_factory
        )
        counts_before = {
            "messages": _count_rows(session_factory, ProjectDirectorMessageTable),
            "runs": _count_rows(session_factory, RunTable),
        }

        response = client.post(
            f"/project-director/sessions/{session_id}/programmer-no-write-execution",
            json={
                "source_task_id": task_id,
                "source_message_id": p16_msg_id,
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


def test_p17_controlled_no_write_blocked(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p16_msg_id, _ = _prepare_p17_chain(
            client, session_factory
        )

        response = client.post(
            f"/project-director/sessions/{session_id}/programmer-no-write-execution",
            json={
                "source_task_id": task_id,
                "source_message_id": p16_msg_id,
                "user_confirmed": True,
                "execution_mode": "controlled_no_write",
            },
        )

        assert response.status_code == 409
        assert "controlled_no_write_not_enabled_in_api" in response.json()["detail"]


# ── E. source message not in session ─────────────────────────────────


def test_p17_blocks_source_message_from_other_session(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p16_msg_id, _ = _prepare_p17_chain(
            client, session_factory
        )

        other_session = client.post(
            "/project-director/sessions",
            json={"goal_text": "P17 other session"},
        )
        assert other_session.status_code == 201
        other_session_id = other_session.json()["id"]

        response = client.post(
            f"/project-director/sessions/{other_session_id}/programmer-no-write-execution",
            json={
                "source_task_id": task_id,
                "source_message_id": p16_msg_id,
                "user_confirmed": True,
            },
        )

        assert response.status_code == 409
        assert "source_message_not_in_session" in response.json()["detail"]


# ── F. source message not P16 plan ────────────────────────────────────


def test_p17_blocks_non_p16_source_message(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, _p16_msg_id, p12_source_msg_id = _prepare_p17_chain(
            client, session_factory
        )

        response = client.post(
            f"/project-director/sessions/{session_id}/programmer-no-write-execution",
            json={
                "source_task_id": task_id,
                "source_message_id": p12_source_msg_id,
                "user_confirmed": True,
            },
        )

        assert response.status_code == 409
        assert "source_message_is_not_p16_programmer_no_write_plan" in response.json()["detail"]


# ── G. non P12 safe dry-run task blocked ─────────────────────────────


def test_p17_blocks_nonexistent_task(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, _task_id, p16_msg_id, _ = _prepare_p17_chain(
            client, session_factory
        )

        response = client.post(
            f"/project-director/sessions/{session_id}/programmer-no-write-execution",
            json={
                "source_task_id": str(uuid4()),
                "source_message_id": p16_msg_id,
                "user_confirmed": True,
            },
        )

        assert response.status_code == 404


# ── H. source_task / P16 plan message mismatch ───────────────────────


def test_p17_blocks_source_task_p16_message_mismatch(tmp_path) -> None:
    """Verify that using task A with P16 plan message from task B is blocked."""
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        # Create first chain (task A)
        session_id, task_a_id, p16_msg_a_id, _ = _prepare_p17_chain(
            client, session_factory
        )

        # Create second chain in the same session (task B)
        p11_response_b = client.post(
            f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
            json={"user_goal": "P17 second evidence for mismatch test"},
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

        p16_msg_b_id = _record_p16_plan_message(
            session_factory,
            session_id=session_id,
            source_task_id=task_b_id,
            source_message_id=p15_msg_b_id,
        )

        # Call P17 with task A + P16 plan message from task B
        response = client.post(
            f"/project-director/sessions/{session_id}/programmer-no-write-execution",
            json={
                "source_task_id": task_a_id,
                "source_message_id": p16_msg_b_id,
                "user_confirmed": True,
            },
        )

        if response.status_code == 200:
            raise AssertionError(
                "P17 implementation bug: accepted task A with P16 plan message from task B. "
                "Expected 409 with source_task_not_bound_to_p16_plan or equivalent."
            )

        assert response.status_code == 409


# ── I. response excludes sensitive/misleading fields ─────────────────


def test_p17_response_excludes_sensitive_fields(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p16_msg_id, _ = _prepare_p17_chain(
            client, session_factory
        )

        response = client.post(
            f"/project-director/sessions/{session_id}/programmer-no-write-execution",
            json={
                "source_task_id": task_id,
                "source_message_id": p16_msg_id,
                "user_confirmed": True,
                "execution_mode": "fake_execution",
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


# ── J. message readback ──────────────────────────────────────────────


def test_p17_message_readback(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p16_msg_id, _ = _prepare_p17_chain(
            client, session_factory
        )

        response = client.post(
            f"/project-director/sessions/{session_id}/programmer-no-write-execution",
            json={
                "source_task_id": task_id,
                "source_message_id": p16_msg_id,
                "user_confirmed": True,
                "execution_mode": "fake_execution",
            },
        )
        assert response.status_code == 200

        messages_response = client.get(
            f"/project-director/sessions/{session_id}/messages"
        )
        assert messages_response.status_code == 200
        messages = messages_response.json()["messages"]

        p17_msgs = [
            item for item in messages
            if item["source_detail"] == "p17_programmer_no_write_execution"
        ]
        assert len(p17_msgs) >= 1

        p17_msg = p17_msgs[0]
        assert p17_msg["related_task_id"] == task_id

        actions = p17_msg.get("suggested_actions") or []
        assert len(actions) >= 1
        action = actions[0]
        assert action["type"] == "p17_programmer_no_write_execution_record"
        assert action["actual_patch_applied"] is False
        assert action["git_write_performed"] is False
        assert action["ai_project_director_total_loop"] == "Partial"


# ── patch_preview safety ──────────────────────────────────────────────


def test_p17_patch_preview_is_preview_only(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p16_msg_id, _ = _prepare_p17_chain(
            client, session_factory
        )

        response = client.post(
            f"/project-director/sessions/{session_id}/programmer-no-write-execution",
            json={
                "source_task_id": task_id,
                "source_message_id": p16_msg_id,
                "user_confirmed": True,
                "execution_mode": "fake_execution",
            },
        )

        assert response.status_code == 200
        payload = response.json()

        all_patch_lines = list(payload.get("patch_preview", []))
        for step in payload.get("execution_steps", []):
            all_patch_lines.extend(step.get("patch_preview", []))

        assert len(all_patch_lines) >= 1
        for line in all_patch_lines:
            for marker in ALL_APPLYABLE_DIFF_MARKERS:
                assert not line.startswith(marker), (
                    f"patch_preview leaked applyable diff: {marker}"
                )
            # Each non-empty line should be preview-only
            assert (
                "PREVIEW ONLY" in line
                or "no repository file" in line.lower()
            ), f"patch_preview line is not preview-only: {line}"


def test_p17_api_response_patch_preview_safety_dry_run(tmp_path) -> None:
    """P18: verify dry_run response patch_preview contains no applyable diff markers."""
    session_factory = _sqlite_session_factory(tmp_path)
    app = _app(session_factory)

    with TestClient(app) as client:
        session_id, task_id, p16_msg_id, _ = _prepare_p17_chain(
            client, session_factory
        )

        response = client.post(
            f"/project-director/sessions/{session_id}/programmer-no-write-execution",
            json={
                "source_task_id": task_id,
                "source_message_id": p16_msg_id,
                "user_confirmed": True,
                "execution_mode": "dry_run",
            },
        )

        assert response.status_code == 200
        payload = response.json()

        all_lines = list(payload.get("patch_preview", []))
        for step in payload.get("execution_steps", []):
            all_lines.extend(step.get("patch_preview", []))

        for line in all_lines:
            for marker in ALL_APPLYABLE_DIFF_MARKERS:
                assert not line.startswith(marker)

        assert payload["actual_patch_applied"] is False
        assert payload["git_write_performed"] is False
        assert payload["ai_project_director_total_loop"] == "Partial"
