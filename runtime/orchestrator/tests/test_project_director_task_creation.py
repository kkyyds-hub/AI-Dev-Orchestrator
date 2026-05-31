"""Tests for BCG-04A Plan-to-Task Creation.

Confirmed plan version → real task queue creation.
No worker, no planning/apply, no repo writes.
"""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api.router import api_router
from app.core.db import get_db_session
from app.core.db_tables import (
    AgentSessionTable,
    ProjectRoleSkillBindingTable,
    ORMBase,
    ProjectTable,
    ProjectDirectorPlanVersionTable,
    RepositoryWorkspaceTable,
    RunTable,
    TaskTable,
)
from app.domain.project_director_plan_version import PlanVersionStatus
from app.domain.project_director_session import ProjectDirectorSessionStatus
from app.domain.task import TaskPriority
from app.repositories.project_director_task_creation_repository import (
    ProjectDirectorTaskCreationRecordRepository,
)


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def sqlite_session_factory(tmp_path):
    db_path = tmp_path / "orchestrator-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


@pytest.fixture()
def db_session(sqlite_session_factory):
    session = sqlite_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(sqlite_session_factory):
    app = FastAPI()
    app.include_router(api_router)

    def override_get_db_session():
        session = sqlite_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ── Helpers ──────────────────────────────────────────────────────────


def _create_project(client, *, name="测试项目"):
    resp = client.post(
        "/projects",
        json={"name": name, "summary": f"{name}：Plan-to-Task 创建测试"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_session(client, *, goal_text=None, project_id=None):
    if goal_text is None:
        goal_text = "构建一个用户认证系统，包括登录、注册"
    body: dict = {"goal_text": goal_text}
    if project_id is not None:
        body["project_id"] = project_id
    resp = client.post("/project-director/sessions", json=body)
    assert resp.status_code == 201
    session_id = resp.json()["id"]
    questions = resp.json()["clarifying_questions"]
    answers = [
        {"question_id": q["id"], "answer": f"回答 {i}"}
        for i, q in enumerate(questions)
    ]
    resp = client.post(
        f"/project-director/sessions/{session_id}/answers",
        json={"answers": answers},
    )
    assert resp.status_code == 200
    return session_id


def _confirm_session(client, session_id):
    resp = client.post(f"/project-director/sessions/{session_id}/confirm")
    assert resp.status_code == 200
    return resp.json()


def _create_plan_version(client, session_id):
    resp = client.post(
        f"/project-director/sessions/{session_id}/plan-versions"
    )
    assert resp.status_code == 201
    return resp.json()


def _confirm_plan_version(client, plan_version_id):
    resp = client.post(
        f"/project-director/plan-versions/{plan_version_id}/confirm"
    )
    assert resp.status_code == 200


def _setup_confirmed_plan_with_project(client):
    """Full setup: project → session → confirm → plan version → confirm."""
    project_id = _create_project(client, name="Plan-to-Task 项目")
    sid = _create_session(client, project_id=project_id)
    _confirm_session(client, sid)
    pv = _create_plan_version(client, sid)
    _confirm_plan_version(client, pv["id"])
    # Re-read to get confirmed status
    resp = client.get(f"/project-director/plan-versions/{pv['id']}")
    return resp.json(), sid, project_id


def _task_rows_for_plan(db_session, plan_version: dict) -> list[TaskTable]:
    source_draft_id = f"pdv:{plan_version['id']}:{plan_version['version_no']}"
    return list(
        db_session.execute(
            select(TaskTable).where(TaskTable.source_draft_id == source_draft_id)
        ).scalars()
    )


# ── Tests ────────────────────────────────────────────────────────────


class TestCreateTasks:
    def test_create_tasks_from_confirmed_plan_with_project(self, client):
        """Happy path: confirmed plan version with project_id creates real tasks."""
        plan_version, session_id, project_id = _setup_confirmed_plan_with_project(client)

        resp = client.post(
            f"/project-director/plan-versions/{plan_version['id']}/create-tasks"
        )
        assert resp.status_code == 201
        data = resp.json()

        assert data["plan_version_id"] == plan_version["id"]
        assert data["session_id"] == session_id
        assert data["project_id"] == project_id
        assert data["task_count"] == len(plan_version["proposed_tasks"])
        assert len(data["created_task_ids"]) == data["task_count"]
        assert data["status"] == "created"
        assert data["next_action"]
        assert data["forbidden_actions"]
        assert "不自动调用 Worker" in data["forbidden_actions"]
        assert "部分通过" in data["gate_conclusion"]

    def test_create_tasks_plan_version_not_found_returns_404(self, client):
        """Non-existent plan version returns 404."""
        resp = client.post(
            f"/project-director/plan-versions/{uuid4()}/create-tasks"
        )
        assert resp.status_code == 404

    def test_create_tasks_unconfirmed_plan_version_returns_409(self, client):
        """Plan version not in 'confirmed' status returns 409."""
        project_id = _create_project(client, name="未确认计划测试")
        sid = _create_session(client, project_id=project_id)
        _confirm_session(client, sid)
        pv = _create_plan_version(client, sid)
        # Plan version is in pending_confirmation, NOT confirmed

        resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-tasks"
        )
        assert resp.status_code == 409
        assert "only 'confirmed'" in resp.json()["detail"].lower()

    def test_create_tasks_plan_version_without_project_id_returns_409(self, client):
        """Plan version without project_id returns 409."""
        # Create session without project_id
        sid = _create_session(client)
        _confirm_session(client, sid)
        pv = _create_plan_version(client, sid)
        _confirm_plan_version(client, pv["id"])

        resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-tasks"
        )
        assert resp.status_code == 409
        assert "project_id" in resp.json()["detail"].lower()

    def test_duplicate_create_tasks_returns_409(self, client):
        """Second call to create-tasks returns 409."""
        plan_version, _, _ = _setup_confirmed_plan_with_project(client)

        # First call succeeds
        resp = client.post(
            f"/project-director/plan-versions/{plan_version['id']}/create-tasks"
        )
        assert resp.status_code == 201

        # Second call returns 409
        resp = client.post(
            f"/project-director/plan-versions/{plan_version['id']}/create-tasks"
        )
        assert resp.status_code == 409
        assert "already been created" in resp.json()["detail"].lower()

    def test_created_task_count_equals_proposed_task_count(self, client):
        """Number of created tasks must equal number of proposed_tasks."""
        plan_version, _, _ = _setup_confirmed_plan_with_project(client)

        resp = client.post(
            f"/project-director/plan-versions/{plan_version['id']}/create-tasks"
        )
        assert resp.status_code == 201
        data = resp.json()

        expected_count = len(plan_version["proposed_tasks"])
        assert data["task_count"] == expected_count
        assert len(data["created_task_ids"]) == expected_count

    def test_task_source_draft_id_is_set(self, client):
        """Every created task must have source_draft_id."""
        plan_version, _, _ = _setup_confirmed_plan_with_project(client)

        resp = client.post(
            f"/project-director/plan-versions/{plan_version['id']}/create-tasks"
        )
        data = resp.json()

        # Read each task and verify source_draft_id
        for task_id in data["created_task_ids"]:
            task_resp = client.get(f"/tasks/{task_id}")
            assert task_resp.status_code == 200
            task_data = task_resp.json()
            assert task_data["source_draft_id"]
            assert f"pdv:{plan_version['id']}" in task_data["source_draft_id"]

    def test_task_role_code_aligns_with_proposed_task(self, client):
        """Task owner_role_code must match proposed_task.suggested_role_code."""
        plan_version, _, _ = _setup_confirmed_plan_with_project(client)

        resp = client.post(
            f"/project-director/plan-versions/{plan_version['id']}/create-tasks"
        )
        data = resp.json()

        proposed = plan_version["proposed_tasks"]
        for i, task_id in enumerate(data["created_task_ids"]):
            task_resp = client.get(f"/tasks/{task_id}")
            task_data = task_resp.json()
            assert task_data["owner_role_code"] == proposed[i]["suggested_role_code"], (
                f"Task {i} role {task_data['owner_role_code']} != "
                f"proposed {proposed[i]['suggested_role_code']}"
            )

    def test_task_priority_mapping_correct(self, client):
        """Task priority must be correctly mapped from priority_hint."""
        plan_version, _, _ = _setup_confirmed_plan_with_project(client)

        # Verify priority_hint values exist in plan
        proposed = plan_version["proposed_tasks"]
        priority_hints = {p["priority_hint"] for p in proposed}

        resp = client.post(
            f"/project-director/plan-versions/{plan_version['id']}/create-tasks"
        )
        data = resp.json()

        for i, task_id in enumerate(data["created_task_ids"]):
            task_resp = client.get(f"/tasks/{task_id}")
            task_data = task_resp.json()
            hint = proposed[i]["priority_hint"].lower()

            # Verify mapping
            if hint == "high":
                assert task_data["priority"] == TaskPriority.HIGH.value
            elif hint == "urgent":
                assert task_data["priority"] == TaskPriority.URGENT.value
            elif hint == "low":
                assert task_data["priority"] == TaskPriority.LOW.value
            else:
                assert task_data["priority"] == TaskPriority.NORMAL.value

    def test_get_created_tasks_returns_task_ids(self, client):
        """GET created-tasks must return the task creation record."""
        plan_version, _, _ = _setup_confirmed_plan_with_project(client)

        # Create tasks first
        create_resp = client.post(
            f"/project-director/plan-versions/{plan_version['id']}/create-tasks"
        )
        assert create_resp.status_code == 201
        created = create_resp.json()

        # GET should return same data
        resp = client.get(
            f"/project-director/plan-versions/{plan_version['id']}/created-tasks"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_version_id"] == created["plan_version_id"]
        assert data["session_id"] == created["session_id"]
        assert data["task_count"] == created["task_count"]
        assert data["created_task_ids"] == created["created_task_ids"]
        assert data["status"] == "created"

    def test_get_created_tasks_before_creation_returns_404(self, client):
        """GET created-tasks before creating any returns 404."""
        plan_version, _, _ = _setup_confirmed_plan_with_project(client)

        resp = client.get(
            f"/project-director/plan-versions/{plan_version['id']}/created-tasks"
        )
        assert resp.status_code == 404

    def test_create_formal_project_from_confirmed_unbound_draft(
        self, client, db_session
    ):
        """Confirmed unbound draft creates a formal project + task queue."""
        sid = _create_session(client)
        _confirm_session(client, sid)
        pv = _create_plan_version(client, sid)
        _confirm_plan_version(client, pv["id"])

        confirmed_resp = client.get(f"/project-director/plan-versions/{pv['id']}")
        assert confirmed_resp.status_code == 200
        confirmed = confirmed_resp.json()
        assert confirmed["status"] == PlanVersionStatus.CONFIRMED.value
        assert confirmed["project_id"] is None

        # Approving/confirming the draft must not auto-create a Project/Task.
        assert db_session.execute(select(ProjectTable)).scalars().all() == []
        assert db_session.execute(select(TaskTable)).scalars().all() == []

        resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["plan_version_id"] == pv["id"]
        assert data["session_id"] == sid
        assert data["project_id"]
        assert data["project_name"]
        assert data["task_count"] == len(confirmed["proposed_tasks"])
        assert len(data["created_task_ids"]) == len(confirmed["proposed_tasks"])
        assert data["status"] == "created"
        assert data["already_created"] is False

        project_resp = client.get(f"/projects/{data['project_id']}")
        assert project_resp.status_code == 200
        project_data = project_resp.json()
        assert project_data["id"] == data["project_id"]
        assert project_data["task_stats"]["total_tasks"] == data["task_count"]
        assert not project_data["name"].startswith("#")
        assert project_data["name"] != "作战计划摘要"
        assert "用户认证系统" in project_data["name"]
        assert "正式项目与待执行任务队列已创建" in data["next_action"]
        assert "部分通过" in data["gate_conclusion"]
        assert ("Formal " + "Project") not in data["next_action"]
        assert ("Task " + "queue") not in data["gate_conclusion"]

        reread_plan_resp = client.get(f"/project-director/plan-versions/{pv['id']}")
        assert reread_plan_resp.status_code == 200
        assert reread_plan_resp.json()["project_id"] == data["project_id"]

        source_draft_id = f"pdv:{pv['id']}:{confirmed['version_no']}"
        for task_id in data["created_task_ids"]:
            task_resp = client.get(f"/tasks/{task_id}")
            assert task_resp.status_code == 200
            task_data = task_resp.json()
            assert task_data["project_id"] == data["project_id"]
            assert task_data["source_draft_id"] == source_draft_id

    def test_create_formal_project_is_idempotent(self, client, db_session):
        """Second formalization call readbacks the same rows without duplication."""
        sid = _create_session(client)
        _confirm_session(client, sid)
        pv = _create_plan_version(client, sid)
        _confirm_plan_version(client, pv["id"])

        first_resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        assert first_resp.status_code == 200
        first = first_resp.json()

        second_resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        assert second_resp.status_code == 200
        second = second_resp.json()

        assert second["status"] == "already_created"
        assert second["already_created"] is True
        assert second["project_id"] == first["project_id"]
        assert second["created_task_ids"] == first["created_task_ids"]
        assert second["task_count"] == first["task_count"]
        assert "不会重复创建" in second["next_action"]
        assert "部分通过" in second["gate_conclusion"]
        assert ("This confirmed " + "draft") not in second["next_action"]
        assert "Partial" not in second["gate_conclusion"]

        source_draft_id = f"pdv:{pv['id']}:1"
        task_rows = list(
            db_session.execute(
                select(TaskTable).where(TaskTable.source_draft_id == source_draft_id)
            ).scalars()
        )
        project_rows = db_session.execute(select(ProjectTable)).scalars().all()
        assert len(task_rows) == first["task_count"]
        assert len(project_rows) == 1

    def test_create_formal_project_does_not_create_execution_side_effects(
        self, client, db_session
    ):
        """Formalization stays at Project + pending Tasks only."""
        sid = _create_session(client)
        _confirm_session(client, sid)
        pv = _create_plan_version(client, sid)
        _confirm_plan_version(client, pv["id"])

        resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        assert resp.status_code == 200

        assert db_session.execute(select(RunTable)).scalars().all() == []
        assert db_session.execute(select(AgentSessionTable)).scalars().all() == []
        assert db_session.execute(select(ProjectRoleSkillBindingTable)).scalars().all() == []
        assert db_session.execute(select(RepositoryWorkspaceTable)).scalars().all() == []

    def test_create_tasks_does_not_create_runs(self, client):
        """Creating tasks must not create any runs."""
        plan_version, _, _ = _setup_confirmed_plan_with_project(client)

        resp = client.post(
            f"/project-director/plan-versions/{plan_version['id']}/create-tasks"
        )
        data = resp.json()

        # Check each created task has no runs
        for task_id in data["created_task_ids"]:
            runs_resp = client.get(f"/runs?task_id={task_id}")
            # If the runs endpoint filters by task_id, check response
            if runs_resp.status_code == 200:
                runs_data = runs_resp.json()
                task_runs = [
                    r for r in runs_data
                    if isinstance(r, dict) and str(r.get("task_id")) == str(task_id)
                ]
                assert len(task_runs) == 0, (
                    f"Task {task_id} has unexpected runs"
                )

    def test_all_response_fields_present(self, client):
        """TaskCreationResponse must contain all required fields."""
        plan_version, session_id, project_id = _setup_confirmed_plan_with_project(client)

        resp = client.post(
            f"/project-director/plan-versions/{plan_version['id']}/create-tasks"
        )
        assert resp.status_code == 201
        data = resp.json()

        required_fields = [
            "plan_version_id", "session_id", "project_id",
            "created_task_ids", "task_count", "status",
            "next_action", "forbidden_actions", "gate_conclusion",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        assert data["plan_version_id"] == plan_version["id"]
        assert data["session_id"] == session_id
        assert data["project_id"] == project_id
        assert data["task_count"] > 0
        assert len(data["created_task_ids"]) > 0
        assert data["status"] == "created"
        assert data["next_action"] != ""
        assert len(data["forbidden_actions"]) > 0
        assert data["gate_conclusion"] != ""

    # ── Hardening tests ─────────────────────────────────────────────

    def test_create_tasks_atomic_task_count_matches_record(self, client):
        """After create-tasks, every task in the response must exist in DB,
        and the creation record must match exactly."""
        plan_version, _, _ = _setup_confirmed_plan_with_project(client)

        # Create tasks
        create_resp = client.post(
            f"/project-director/plan-versions/{plan_version['id']}/create-tasks"
        )
        assert create_resp.status_code == 201
        data = create_resp.json()

        # Verify creation record exists
        get_resp = client.get(
            f"/project-director/plan-versions/{plan_version['id']}/created-tasks"
        )
        assert get_resp.status_code == 200
        record = get_resp.json()

        # Every task in the record must exist in DB
        existing_count = 0
        for task_id in record["created_task_ids"]:
            task_resp = client.get(f"/tasks/{task_id}")
            assert task_resp.status_code == 200, (
                f"Task {task_id} from record does not exist in DB"
            )
            existing_count += 1

        # Counts must match: response == record == DB
        assert existing_count == record["task_count"]
        assert existing_count == data["task_count"]

    def test_create_tasks_publishes_events_only_after_commit(
        self, client, db_session, monkeypatch
    ):
        """Successful batch emits one created event per committed task."""
        plan_version, _, _ = _setup_confirmed_plan_with_project(client)
        published_task_ids: list[str] = []

        def _capture_task_event(*, task, reason, previous_status=None):
            published_task_ids.append(str(task.id))

        monkeypatch.setattr(
            "app.repositories.task_repository.event_stream_service."
            "publish_task_updated",
            _capture_task_event,
        )

        resp = client.post(
            f"/project-director/plan-versions/{plan_version['id']}/create-tasks"
        )
        assert resp.status_code == 201
        data = resp.json()

        task_rows = _task_rows_for_plan(db_session, plan_version)
        persisted_task_ids = {str(row.id) for row in task_rows}

        assert len(task_rows) == data["task_count"]
        assert published_task_ids == data["created_task_ids"]
        assert set(published_task_ids) == persisted_task_ids

    def test_empty_proposed_task_description_falls_back_to_title(
        self, client, db_session
    ):
        """When proposed_task.description is empty, input_summary uses title fallback."""
        # Setup a confirmed plan version normally
        plan_version, sid, project_id = _setup_confirmed_plan_with_project(client)

        # Patch the stored plan version to have empty description in first proposed_task
        pv_id = UUID(plan_version["id"])
        row = db_session.get(ProjectDirectorPlanVersionTable, pv_id)
        assert row is not None
        tasks_data = json.loads(row.proposed_tasks_json)
        tasks_data[0]["description"] = ""
        row.proposed_tasks_json = json.dumps(tasks_data, ensure_ascii=False)
        db_session.commit()

        # Create tasks — should succeed with fallback
        resp = client.post(
            f"/project-director/plan-versions/{plan_version['id']}/create-tasks"
        )
        assert resp.status_code == 201
        data = resp.json()

        # The task corresponding to the empty-description proposed_task
        # must have input_summary containing the fallback
        first_task_id = data["created_task_ids"][0]
        task_resp = client.get(f"/tasks/{first_task_id}")
        assert task_resp.status_code == 200
        task_data = task_resp.json()
        assert task_data["input_summary"] != ""
        assert "由计划版本生成的任务" in task_data["input_summary"]
        assert tasks_data[0]["title"] in task_data["input_summary"]

    def test_duplicate_create_tasks_still_returns_409(self, client):
        """Duplicate create-tasks must still return 409 after hardening."""
        plan_version, _, _ = _setup_confirmed_plan_with_project(client)

        # First call succeeds
        resp = client.post(
            f"/project-director/plan-versions/{plan_version['id']}/create-tasks"
        )
        assert resp.status_code == 201

        # Second call returns 409
        resp = client.post(
            f"/project-director/plan-versions/{plan_version['id']}/create-tasks"
        )
        assert resp.status_code == 409
        assert "already been created" in resp.json()["detail"].lower()

        # Verify no additional tasks were created
        get_resp = client.get(
            f"/project-director/plan-versions/{plan_version['id']}/created-tasks"
        )
        record = get_resp.json()
        assert record["task_count"] == len(plan_version["proposed_tasks"])

    def test_atomic_rollback_on_record_creation_failure(
        self, client, db_session, monkeypatch
    ):
        """If TaskCreationRecord creation fails after tasks are added to
        session, no tasks or task-created events should be left behind."""
        plan_version, _, _ = _setup_confirmed_plan_with_project(client)
        published_task_ids: list[str] = []

        # Monkey-patch the repository's create method to raise
        original_create = ProjectDirectorTaskCreationRecordRepository.create

        def _failing_create(self, record):
            raise RuntimeError("Simulated record creation failure")

        def _capture_task_event(*, task, reason, previous_status=None):
            published_task_ids.append(str(task.id))

        monkeypatch.setattr(
            ProjectDirectorTaskCreationRecordRepository,
            "create",
            _failing_create,
        )
        monkeypatch.setattr(
            "app.repositories.task_repository.event_stream_service."
            "publish_task_updated",
            _capture_task_event,
        )

        try:
            resp = client.post(
                f"/project-director/plan-versions/{plan_version['id']}/create-tasks"
            )
            # Should return 422 because the record creation failed
            assert resp.status_code == 422

            # No tasks should have been persisted
            # Verify by trying to GET created-tasks — should be 404
            get_resp = client.get(
                f"/project-director/plan-versions/{plan_version['id']}/created-tasks"
            )
            assert get_resp.status_code == 404

            # No committed Task rows and no ghost SSE/console task events.
            assert _task_rows_for_plan(db_session, plan_version) == []
            assert published_task_ids == []
        finally:
            # Restore original
            monkeypatch.setattr(
                ProjectDirectorTaskCreationRecordRepository,
                "create",
                original_create,
            )
