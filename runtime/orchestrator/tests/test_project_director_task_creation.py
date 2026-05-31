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
    ProjectDirectorAgentTeamConfigTable,
    ProjectDirectorRepositoryBindingConfigTable,
    ProjectDirectorSkillBindingConfigTable,
    ProjectDirectorVerificationConfigTable,
    ProjectTable,
    ProjectDirectorPlanVersionTable,
    RepositoryWorkspaceTable,
    RunTable,
    TaskTable,
)
from app.domain.project_director_plan_version import PlanVersionStatus
from app.domain.project_director_session import ProjectDirectorSessionStatus
from app.domain.task import TaskPriority, TaskStatus
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
        source_draft_id = f"pdv:{pv['id']}:{confirmed['version_no']}"

        assert data["plan_version_id"] == pv["id"]
        assert data["session_id"] == sid
        assert data["project_id"]
        assert data["project_name"]
        assert data["task_count"] == len(confirmed["proposed_tasks"])
        assert len(data["created_task_ids"]) == len(confirmed["proposed_tasks"])
        assert data["status"] == "created"
        assert data["already_created"] is False
        warnings_text = "\n".join(data["warnings"])
        assert "Agent Session" in warnings_text
        assert "未自动启动 Worker" in warnings_text
        assert "真实 Skill 绑定" in warnings_text
        assert "真实仓库绑定" in warnings_text
        assert "未执行验证命令" in warnings_text

        project_resp = client.get(f"/projects/{data['project_id']}")
        assert project_resp.status_code == 200
        project_data = project_resp.json()
        assert project_data["id"] == data["project_id"]
        assert project_data["source_plan_version_id"] == pv["id"]
        assert project_data["source_draft_id"] == source_draft_id
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

        for task_id in data["created_task_ids"]:
            task_resp = client.get(f"/tasks/{task_id}")
            assert task_resp.status_code == 200
            task_data = task_resp.json()
            assert task_data["project_id"] == data["project_id"]
            assert task_data["source_draft_id"] == source_draft_id

        task_sources = {
            task["id"]: (
                task["source_plan_version_id"],
                task["source_draft_id"],
            )
            for task in project_data["tasks"]
        }
        assert set(task_sources) == set(data["created_task_ids"])
        assert set(task_sources.values()) == {(pv["id"], source_draft_id)}

    def test_regular_project_readback_does_not_report_project_director_source(
        self, client
    ):
        """Regular project detail must not be mislabeled as AI-director-created."""
        project_id = _create_project(client, name="普通项目")

        project_resp = client.get(f"/projects/{project_id}")
        assert project_resp.status_code == 200
        project_data = project_resp.json()

        assert project_data["source_plan_version_id"] is None
        assert project_data["source_draft_id"] is None
        assert project_data["tasks"] == []

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
        second_warnings_text = "\n".join(second["warnings"])
        assert "Agent Session" in second_warnings_text
        assert "未自动启动 Worker" in second_warnings_text
        assert "真实 Skill 绑定" in second_warnings_text
        assert "真实仓库绑定" in second_warnings_text
        assert "未执行验证命令" in second_warnings_text
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

    def test_create_formal_project_creates_pending_agent_team_config(
        self, client, db_session
    ):
        """Formal project creation persists a pending project-level agent team config."""
        sid = _create_session(client)
        _confirm_session(client, sid)
        pv = _create_plan_version(client, sid)
        _confirm_plan_version(client, pv["id"])

        confirmed_resp = client.get(f"/project-director/plan-versions/{pv['id']}")
        assert confirmed_resp.status_code == 200
        confirmed = confirmed_resp.json()
        assert len(confirmed["agent_team_suggestions"]) > 0

        resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        assert resp.status_code == 200
        created = resp.json()

        config_resp = client.get(
            f"/project-director/projects/{created['project_id']}/agent-team-config"
        )
        assert config_resp.status_code == 200
        body = config_resp.json()
        config = body["config"]

        assert body["project_id"] == created["project_id"]
        assert config["project_id"] == created["project_id"]
        assert config["plan_version_id"] == pv["id"]
        assert config["source_draft_id"] == f"pdv:{pv['id']}:{confirmed['version_no']}"
        assert config["status"] == "pending_confirmation"
        assert len(config["agent_team"]) == len(confirmed["agent_team_suggestions"])
        assert "Agent 编队" in body["next_action"]
        assert any("Agent Session" in item for item in config["warnings"])
        assert any("Worker" in item for item in config["warnings"])

        rows = db_session.execute(
            select(ProjectDirectorAgentTeamConfigTable)
        ).scalars().all()
        assert len(rows) == 1

    def test_regular_project_agent_team_config_returns_null(self, client):
        """Regular projects do not show AI Director agent team config."""
        project_id = _create_project(client, name="普通项目")

        resp = client.get(
            f"/project-director/projects/{project_id}/agent-team-config"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["project_id"] == project_id
        assert body["config"] is None

    def test_review_agent_team_config_confirm_then_reject_conflicts(
        self, client, db_session
    ):
        """A pending agent team config can be confirmed once, without side effects."""
        sid = _create_session(client)
        _confirm_session(client, sid)
        pv = _create_plan_version(client, sid)
        _confirm_plan_version(client, pv["id"])
        create_resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        assert create_resp.status_code == 200
        project_id = create_resp.json()["project_id"]

        confirm_resp = client.post(
            f"/project-director/projects/{project_id}/agent-team-config/review",
            json={"action": "confirm", "note": "确认编队"},
        )
        assert confirm_resp.status_code == 200
        confirmed = confirm_resp.json()["config"]
        assert confirmed["status"] == "confirmed"
        assert confirmed["confirmed_at"] is not None
        assert confirmed["rejected_at"] is None

        reject_resp = client.post(
            f"/project-director/projects/{project_id}/agent-team-config/review",
            json={"action": "reject"},
        )
        assert reject_resp.status_code == 409

        assert db_session.execute(select(AgentSessionTable)).scalars().all() == []
        assert db_session.execute(select(RunTable)).scalars().all() == []
        assert db_session.execute(select(ProjectRoleSkillBindingTable)).scalars().all() == []
        assert db_session.execute(select(RepositoryWorkspaceTable)).scalars().all() == []

    def test_review_agent_team_config_reject_then_confirm_conflicts(self, client):
        """A rejected agent team config cannot be confirmed later."""
        sid = _create_session(client)
        _confirm_session(client, sid)
        pv = _create_plan_version(client, sid)
        _confirm_plan_version(client, pv["id"])
        create_resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        assert create_resp.status_code == 200
        project_id = create_resp.json()["project_id"]

        reject_resp = client.post(
            f"/project-director/projects/{project_id}/agent-team-config/review",
            json={"action": "reject", "note": "暂不采用"},
        )
        assert reject_resp.status_code == 200
        rejected = reject_resp.json()["config"]
        assert rejected["status"] == "rejected"
        assert rejected["rejected_at"] is not None
        assert rejected["confirmed_at"] is None

        confirm_resp = client.post(
            f"/project-director/projects/{project_id}/agent-team-config/review",
            json={"action": "confirm"},
        )
        assert confirm_resp.status_code == 409

    def test_create_formal_project_does_not_duplicate_agent_team_config(
        self, client, db_session
    ):
        """Repeated formalization readbacks the existing config without duplication."""
        sid = _create_session(client)
        _confirm_session(client, sid)
        pv = _create_plan_version(client, sid)
        _confirm_plan_version(client, pv["id"])

        first_resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        second_resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        assert first_resp.status_code == 200
        assert second_resp.status_code == 200
        project_id = first_resp.json()["project_id"]

        rows = db_session.execute(
            select(ProjectDirectorAgentTeamConfigTable)
        ).scalars().all()
        assert len(rows) == 1
        assert str(rows[0].project_id) == project_id
        assert str(rows[0].plan_version_id) == pv["id"]

        config_resp = client.get(
            f"/project-director/projects/{project_id}/agent-team-config"
        )
        assert config_resp.status_code == 200
        assert config_resp.json()["config"]["status"] == "pending_confirmation"

    def test_create_formal_project_creates_pending_skill_binding_config(
        self, client, db_session
    ):
        """Formal project creation persists pending project-level Skill suggestions."""
        sid = _create_session(client)
        _confirm_session(client, sid)
        pv = _create_plan_version(client, sid)
        _confirm_plan_version(client, pv["id"])

        confirmed_resp = client.get(f"/project-director/plan-versions/{pv['id']}")
        assert confirmed_resp.status_code == 200
        confirmed = confirmed_resp.json()
        assert len(confirmed["skill_binding_suggestions"]) > 0

        resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        assert resp.status_code == 200
        created = resp.json()

        config_resp = client.get(
            f"/project-director/projects/{created['project_id']}/skill-binding-config"
        )
        assert config_resp.status_code == 200
        body = config_resp.json()
        config = body["config"]

        assert body["project_id"] == created["project_id"]
        assert config["project_id"] == created["project_id"]
        assert config["plan_version_id"] == pv["id"]
        assert config["source_draft_id"] == f"pdv:{pv['id']}:{confirmed['version_no']}"
        assert config["status"] == "pending_confirmation"
        assert len(config["skill_bindings"]) == len(
            confirmed["skill_binding_suggestions"]
        )
        assert body["next_action"] == (
            "请在项目详情页确认或拒绝 AI 主管 Skill 绑定建议；"
            "确认后仍不会启用 Skill 或启动 Worker。"
        )
        assert "?" not in body["next_action"]
        assert any("Skill" in item for item in config["warnings"])
        assert any("Worker" in item for item in config["warnings"])

        rows = db_session.execute(
            select(ProjectDirectorSkillBindingConfigTable)
        ).scalars().all()
        assert len(rows) == 1

    def test_regular_project_skill_binding_config_returns_null(self, client):
        """Regular projects do not show AI Director Skill binding config."""
        project_id = _create_project(client, name="普通项目")

        resp = client.get(
            f"/project-director/projects/{project_id}/skill-binding-config"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["project_id"] == project_id
        assert body["config"] is None

    def test_review_skill_binding_config_confirm_then_reject_conflicts(
        self, client, db_session
    ):
        """A pending Skill config can be confirmed once, without side effects."""
        sid = _create_session(client)
        _confirm_session(client, sid)
        pv = _create_plan_version(client, sid)
        _confirm_plan_version(client, pv["id"])
        create_resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        assert create_resp.status_code == 200
        project_id = create_resp.json()["project_id"]

        confirm_resp = client.post(
            f"/project-director/projects/{project_id}/skill-binding-config/review",
            json={"action": "confirm", "note": "确认 Skill 绑定建议"},
        )
        assert confirm_resp.status_code == 200
        confirmed = confirm_resp.json()["config"]
        assert confirmed["status"] == "confirmed"
        assert confirmed["confirmed_at"] is not None
        assert confirmed["rejected_at"] is None

        reject_resp = client.post(
            f"/project-director/projects/{project_id}/skill-binding-config/review",
            json={"action": "reject"},
        )
        assert reject_resp.status_code == 409

        assert db_session.execute(select(AgentSessionTable)).scalars().all() == []
        assert db_session.execute(select(RunTable)).scalars().all() == []
        assert db_session.execute(select(ProjectRoleSkillBindingTable)).scalars().all() == []
        assert db_session.execute(select(RepositoryWorkspaceTable)).scalars().all() == []

    def test_review_skill_binding_config_reject_then_confirm_conflicts(self, client):
        """A rejected Skill config cannot be confirmed later."""
        sid = _create_session(client)
        _confirm_session(client, sid)
        pv = _create_plan_version(client, sid)
        _confirm_plan_version(client, pv["id"])
        create_resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        assert create_resp.status_code == 200
        project_id = create_resp.json()["project_id"]

        reject_resp = client.post(
            f"/project-director/projects/{project_id}/skill-binding-config/review",
            json={"action": "reject", "note": "暂不采用"},
        )
        assert reject_resp.status_code == 200
        rejected = reject_resp.json()["config"]
        assert rejected["status"] == "rejected"
        assert rejected["rejected_at"] is not None
        assert rejected["confirmed_at"] is None

        confirm_resp = client.post(
            f"/project-director/projects/{project_id}/skill-binding-config/review",
            json={"action": "confirm"},
        )
        assert confirm_resp.status_code == 409

    def test_create_formal_project_does_not_duplicate_skill_binding_config(
        self, client, db_session
    ):
        """Repeated formalization readbacks existing Skill config without duplication."""
        sid = _create_session(client)
        _confirm_session(client, sid)
        pv = _create_plan_version(client, sid)
        _confirm_plan_version(client, pv["id"])

        first_resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        second_resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        assert first_resp.status_code == 200
        assert second_resp.status_code == 200
        project_id = first_resp.json()["project_id"]

        rows = db_session.execute(
            select(ProjectDirectorSkillBindingConfigTable)
        ).scalars().all()
        assert len(rows) == 1
        assert str(rows[0].project_id) == project_id
        assert str(rows[0].plan_version_id) == pv["id"]

        config_resp = client.get(
            f"/project-director/projects/{project_id}/skill-binding-config"
        )
        assert config_resp.status_code == 200
        assert config_resp.json()["config"]["status"] == "pending_confirmation"

    def test_create_formal_project_creates_pending_repository_binding_config(
        self, client, db_session
    ):
        """Formal project creation persists pending project-level repository suggestions."""
        sid = _create_session(client)
        _confirm_session(client, sid)
        pv = _create_plan_version(client, sid)
        _confirm_plan_version(client, pv["id"])

        confirmed_resp = client.get(f"/project-director/plan-versions/{pv['id']}")
        assert confirmed_resp.status_code == 200
        confirmed = confirmed_resp.json()
        assert len(confirmed["repository_binding_suggestions"]) > 0

        resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        assert resp.status_code == 200
        created = resp.json()

        config_resp = client.get(
            f"/project-director/projects/{created['project_id']}/repository-binding-config"
        )
        assert config_resp.status_code == 200
        body = config_resp.json()
        config = body["config"]

        assert body["project_id"] == created["project_id"]
        assert config["project_id"] == created["project_id"]
        assert config["plan_version_id"] == pv["id"]
        assert config["source_draft_id"] == f"pdv:{pv['id']}:{confirmed['version_no']}"
        assert config["status"] == "pending_confirmation"
        assert len(config["repository_bindings"]) == len(
            confirmed["repository_binding_suggestions"]
        )
        assert body["next_action"] == (
            "请在项目详情页确认或拒绝 AI 主管仓库绑定建议；"
            "确认后仍不会创建真实仓库绑定或写入仓库。"
        )
        assert "?" not in body["next_action"]
        assert any("RepositoryWorkspace" in item for item in config["warnings"])
        assert any("写入仓库" in item for item in config["warnings"])
        assert any("git-commit" in item for item in config["warnings"])

        rows = db_session.execute(
            select(ProjectDirectorRepositoryBindingConfigTable)
        ).scalars().all()
        assert len(rows) == 1

    def test_regular_project_repository_binding_config_returns_null(self, client):
        """Regular projects do not show AI Director repository binding config."""
        project_id = _create_project(client, name="普通项目")

        resp = client.get(
            f"/project-director/projects/{project_id}/repository-binding-config"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["project_id"] == project_id
        assert body["config"] is None

    def test_review_repository_binding_config_confirm_then_reject_conflicts(
        self, client, db_session
    ):
        """A pending repository config can be confirmed once, without side effects."""
        sid = _create_session(client)
        _confirm_session(client, sid)
        pv = _create_plan_version(client, sid)
        _confirm_plan_version(client, pv["id"])
        create_resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        assert create_resp.status_code == 200
        project_id = create_resp.json()["project_id"]

        confirm_resp = client.post(
            f"/project-director/projects/{project_id}/repository-binding-config/review",
            json={"action": "confirm", "note": "确认仓库绑定建议"},
        )
        assert confirm_resp.status_code == 200
        confirmed = confirm_resp.json()["config"]
        assert confirmed["status"] == "confirmed"
        assert confirmed["confirmed_at"] is not None
        assert confirmed["rejected_at"] is None
        assert "RepositoryWorkspace" in confirm_resp.json()["next_action"]

        reject_resp = client.post(
            f"/project-director/projects/{project_id}/repository-binding-config/review",
            json={"action": "reject"},
        )
        assert reject_resp.status_code == 409

        assert db_session.execute(select(AgentSessionTable)).scalars().all() == []
        assert db_session.execute(select(RunTable)).scalars().all() == []
        assert db_session.execute(select(ProjectRoleSkillBindingTable)).scalars().all() == []
        assert db_session.execute(select(RepositoryWorkspaceTable)).scalars().all() == []

    def test_review_repository_binding_config_reject_then_confirm_conflicts(
        self, client, db_session
    ):
        """A rejected repository config cannot be confirmed later."""
        sid = _create_session(client)
        _confirm_session(client, sid)
        pv = _create_plan_version(client, sid)
        _confirm_plan_version(client, pv["id"])
        create_resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        assert create_resp.status_code == 200
        project_id = create_resp.json()["project_id"]

        reject_resp = client.post(
            f"/project-director/projects/{project_id}/repository-binding-config/review",
            json={"action": "reject", "note": "暂不采用"},
        )
        assert reject_resp.status_code == 200
        rejected = reject_resp.json()["config"]
        assert rejected["status"] == "rejected"
        assert rejected["rejected_at"] is not None
        assert rejected["confirmed_at"] is None

        confirm_resp = client.post(
            f"/project-director/projects/{project_id}/repository-binding-config/review",
            json={"action": "confirm"},
        )
        assert confirm_resp.status_code == 409

        assert db_session.execute(select(RepositoryWorkspaceTable)).scalars().all() == []

    def test_create_formal_project_does_not_duplicate_repository_binding_config(
        self, client, db_session
    ):
        """Repeated formalization readbacks existing repository config without duplication."""
        sid = _create_session(client)
        _confirm_session(client, sid)
        pv = _create_plan_version(client, sid)
        _confirm_plan_version(client, pv["id"])

        first_resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        second_resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        assert first_resp.status_code == 200
        assert second_resp.status_code == 200
        project_id = first_resp.json()["project_id"]

        rows = db_session.execute(
            select(ProjectDirectorRepositoryBindingConfigTable)
        ).scalars().all()
        assert len(rows) == 1
        assert str(rows[0].project_id) == project_id
        assert str(rows[0].plan_version_id) == pv["id"]

        config_resp = client.get(
            f"/project-director/projects/{project_id}/repository-binding-config"
        )
        assert config_resp.status_code == 200
        assert config_resp.json()["config"]["status"] == "pending_confirmation"

    def test_create_formal_project_creates_pending_verification_config(
        self, client, db_session
    ):
        """Formal project creation persists pending project-level verification suggestions."""
        sid = _create_session(client)
        _confirm_session(client, sid)
        pv = _create_plan_version(client, sid)
        _confirm_plan_version(client, pv["id"])

        confirmed_resp = client.get(f"/project-director/plan-versions/{pv['id']}")
        assert confirmed_resp.status_code == 200
        confirmed = confirmed_resp.json()
        assert len(confirmed["verification_mechanisms"]) > 0

        resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        assert resp.status_code == 200
        created = resp.json()

        config_resp = client.get(
            f"/project-director/projects/{created['project_id']}/verification-config"
        )
        assert config_resp.status_code == 200
        body = config_resp.json()
        config = body["config"]

        assert body["project_id"] == created["project_id"]
        assert config["project_id"] == created["project_id"]
        assert config["plan_version_id"] == pv["id"]
        assert config["source_draft_id"] == f"pdv:{pv['id']}:{confirmed['version_no']}"
        assert config["status"] == "pending_confirmation"
        assert len(config["verification_mechanisms"]) == len(
            confirmed["verification_mechanisms"]
        )
        assert body["next_action"] == (
            "请在项目详情页确认或拒绝 AI 主管验证机制建议；"
            "确认后仍不会执行验证命令或创建 Run。"
        )
        assert "?" not in body["next_action"]
        assert all("?" not in item for item in config["warnings"])
        assert any("不会自动执行命令" in item for item in config["warnings"])
        assert any("不会创建 Run" in item for item in config["warnings"])
        assert any("subprocess / os.system" in item for item in config["warnings"])

        high_risk_items = [
            item
            for item in config["verification_mechanisms"]
            if item["risk_level"] == "high"
        ]
        assert high_risk_items
        assert all(item["requires_user_confirmation"] is True for item in high_risk_items)

        rows = db_session.execute(
            select(ProjectDirectorVerificationConfigTable)
        ).scalars().all()
        assert len(rows) == 1

    def test_regular_project_verification_config_returns_null(self, client):
        """Regular projects do not show AI Director verification config."""
        project_id = _create_project(client, name="普通项目")

        resp = client.get(
            f"/project-director/projects/{project_id}/verification-config"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["project_id"] == project_id
        assert body["config"] is None
        assert "普通项目" in body["next_action"]

    def test_review_verification_config_confirm_then_reject_conflicts(
        self, client, db_session
    ):
        """A pending verification config can be confirmed once, without side effects."""
        sid = _create_session(client)
        _confirm_session(client, sid)
        pv = _create_plan_version(client, sid)
        _confirm_plan_version(client, pv["id"])
        create_resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        assert create_resp.status_code == 200
        project_id = create_resp.json()["project_id"]

        confirm_resp = client.post(
            f"/project-director/projects/{project_id}/verification-config/review",
            json={"action": "confirm", "note": "确认验证机制建议"},
        )
        assert confirm_resp.status_code == 200
        body = confirm_resp.json()
        confirmed = body["config"]
        assert confirmed["status"] == "confirmed"
        assert confirmed["confirmed_at"] is not None
        assert confirmed["rejected_at"] is None
        assert "不代表验证已执行或已通过" in body["next_action"]
        assert "?" not in body["next_action"]

        reject_resp = client.post(
            f"/project-director/projects/{project_id}/verification-config/review",
            json={"action": "reject"},
        )
        assert reject_resp.status_code == 409

        assert db_session.execute(select(RunTable)).scalars().all() == []
        assert db_session.execute(select(AgentSessionTable)).scalars().all() == []
        assert db_session.execute(select(ProjectRoleSkillBindingTable)).scalars().all() == []
        assert db_session.execute(select(RepositoryWorkspaceTable)).scalars().all() == []

    def test_review_verification_config_reject_then_confirm_conflicts(self, client):
        """A rejected verification config cannot be confirmed later."""
        sid = _create_session(client)
        _confirm_session(client, sid)
        pv = _create_plan_version(client, sid)
        _confirm_plan_version(client, pv["id"])
        create_resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        assert create_resp.status_code == 200
        project_id = create_resp.json()["project_id"]

        reject_resp = client.post(
            f"/project-director/projects/{project_id}/verification-config/review",
            json={"action": "reject", "note": "暂不采用"},
        )
        assert reject_resp.status_code == 200
        rejected = reject_resp.json()["config"]
        assert rejected["status"] == "rejected"
        assert rejected["rejected_at"] is not None
        assert rejected["confirmed_at"] is None

        confirm_resp = client.post(
            f"/project-director/projects/{project_id}/verification-config/review",
            json={"action": "confirm"},
        )
        assert confirm_resp.status_code == 409

    def test_create_formal_project_does_not_duplicate_verification_config(
        self, client, db_session
    ):
        """Repeated formalization readbacks existing verification config without duplication."""
        sid = _create_session(client)
        _confirm_session(client, sid)
        pv = _create_plan_version(client, sid)
        _confirm_plan_version(client, pv["id"])

        first_resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        second_resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        assert first_resp.status_code == 200
        assert second_resp.status_code == 200
        project_id = first_resp.json()["project_id"]

        rows = db_session.execute(
            select(ProjectDirectorVerificationConfigTable)
        ).scalars().all()
        assert len(rows) == 1
        assert str(rows[0].project_id) == project_id
        assert str(rows[0].plan_version_id) == pv["id"]

        config_resp = client.get(
            f"/project-director/projects/{project_id}/verification-config"
        )
        assert config_resp.status_code == 200
        assert config_resp.json()["config"]["status"] == "pending_confirmation"

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
            "next_action", "warnings", "forbidden_actions", "gate_conclusion",
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
        assert len(data["warnings"]) > 0
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

class TestProjectDirectorSetupReadiness:
    def _create_director_project(self, client):
        sid = _create_session(client)
        _confirm_session(client, sid)
        pv = _create_plan_version(client, sid)
        _confirm_plan_version(client, pv["id"])
        confirmed_resp = client.get(f"/project-director/plan-versions/{pv['id']}")
        assert confirmed_resp.status_code == 200
        confirmed = confirmed_resp.json()

        create_resp = client.post(
            f"/project-director/plan-versions/{pv['id']}/create-formal-project"
        )
        assert create_resp.status_code == 200
        created = create_resp.json()
        return sid, confirmed, created

    def test_setup_readiness_reports_initial_director_project_state(self, client):
        """A formal Project created from AI Director returns a read-only overview."""
        _, plan_version, created = self._create_director_project(client)
        project_id = created["project_id"]

        resp = client.get(f"/project-director/projects/{project_id}/setup-readiness")
        assert resp.status_code == 200
        data = resp.json()

        assert data["project_id"] == project_id
        assert data["created_by_director"] is True
        assert data["formal_project_created"] is True
        assert data["task_queue_created"] is True
        assert data["source_plan_version_id"] == plan_version["id"]
        assert data["source_draft_id"] == f"pdv:{plan_version['id']}:{plan_version['version_no']}"
        assert data["task_count"] == created["task_count"]
        assert data["pending_task_count"] == created["task_count"]
        assert data["agent_team_config_status"] == "pending_confirmation"
        assert data["skill_binding_config_status"] == "pending_confirmation"
        assert data["repository_binding_config_status"] == "pending_confirmation"
        assert data["verification_config_status"] == "pending_confirmation"
        assert data["pending_confirmation_count"] == 4
        assert data["confirmed_count"] == 0
        assert data["rejected_count"] == 0
        assert data["ready_for_manual_execution"] is False
        assert any("只读" in item for item in data["warnings"])
        assert any("不会启动 Worker" in item for item in data["warnings"])
        assert any("不会创建 Run" in item for item in data["warnings"])
        assert any("不会执行验证命令" in item for item in data["warnings"])
        assert any("不会写仓库" in item for item in data["warnings"])
        assert any("provider / planning/apply / apply-local / git-commit" in item for item in data["warnings"])
        assert ("?" * 3) not in json.dumps(data, ensure_ascii=False)

    def test_setup_readiness_becomes_ready_after_all_configs_confirmed(self, client):
        """All four confirmed configs allow only manual execution consideration."""
        _, _, created = self._create_director_project(client)
        project_id = created["project_id"]

        for config_name in [
            "agent-team-config",
            "skill-binding-config",
            "repository-binding-config",
            "verification-config",
        ]:
            review_resp = client.post(
                f"/project-director/projects/{project_id}/{config_name}/review",
                json={"action": "confirm"},
            )
            assert review_resp.status_code == 200

        resp = client.get(f"/project-director/projects/{project_id}/setup-readiness")
        assert resp.status_code == 200
        data = resp.json()

        assert data["confirmed_count"] == 4
        assert data["pending_confirmation_count"] == 0
        assert data["rejected_count"] == 0
        assert data["agent_team_config_status"] == "confirmed"
        assert data["skill_binding_config_status"] == "confirmed"
        assert data["repository_binding_config_status"] == "confirmed"
        assert data["verification_config_status"] == "confirmed"
        assert data["ready_for_manual_execution"] is True
        assert any("手动" in step and "Worker" in step for step in data["next_steps"])

    def test_setup_readiness_rejected_config_blocks_manual_execution(self, client):
        """Any rejected config keeps readiness false and explains the next step."""
        _, _, created = self._create_director_project(client)
        project_id = created["project_id"]

        reject_resp = client.post(
            f"/project-director/projects/{project_id}/repository-binding-config/review",
            json={"action": "reject", "note": "暂不采用"},
        )
        assert reject_resp.status_code == 200

        resp = client.get(f"/project-director/projects/{project_id}/setup-readiness")
        assert resp.status_code == 200
        data = resp.json()

        assert data["repository_binding_config_status"] == "rejected"
        assert data["rejected_count"] == 1
        assert data["ready_for_manual_execution"] is False
        assert any("拒绝" in step for step in data["next_steps"])

    def test_setup_readiness_regular_project_is_not_mislabeled(self, client):
        """Ordinary projects can call the API without being labeled as Director-created."""
        project_id = _create_project(client, name="普通项目")

        resp = client.get(f"/project-director/projects/{project_id}/setup-readiness")
        assert resp.status_code == 200
        data = resp.json()

        assert data["created_by_director"] is False
        assert data["source_plan_version_id"] is None
        assert data["source_draft_id"] is None
        assert data["task_count"] == 0
        assert data["pending_task_count"] == 0
        assert data["agent_team_config_status"] == "missing"
        assert data["skill_binding_config_status"] == "missing"
        assert data["repository_binding_config_status"] == "missing"
        assert data["verification_config_status"] == "missing"
        assert data["confirmed_count"] == 0
        assert data["ready_for_manual_execution"] is False

    def test_setup_readiness_ignores_non_pdv_source_draft_id(
        self, client, db_session
    ):
        """Non-pdv task source IDs must not mark ordinary projects as Director-created."""
        project_id = _create_project(client, name="普通来源项目")
        db_session.add(
            TaskTable(
                project_id=UUID(project_id),
                title="普通任务",
                status=TaskStatus.PENDING,
                priority=TaskPriority.NORMAL,
                input_summary="普通项目任务",
                source_draft_id="manual:external-1",
            )
        )
        db_session.commit()

        resp = client.get(f"/project-director/projects/{project_id}/setup-readiness")
        assert resp.status_code == 200
        data = resp.json()

        assert data["created_by_director"] is False
        assert data["source_plan_version_id"] is None
        assert data["source_draft_id"] is None
        assert data["task_count"] == 1
        assert data["pending_task_count"] == 1
        assert data["agent_team_config_status"] == "missing"
        assert data["skill_binding_config_status"] == "missing"
        assert data["repository_binding_config_status"] == "missing"
        assert data["verification_config_status"] == "missing"
        assert data["ready_for_manual_execution"] is False

    def test_setup_readiness_is_read_only_and_has_no_runtime_side_effects(
        self, client, db_session
    ):
        """Calling setup-readiness must not create execution/runtime resources."""
        _, _, created = self._create_director_project(client)
        project_id = created["project_id"]

        before = {
            "runs": len(db_session.execute(select(RunTable)).scalars().all()),
            "sessions": len(db_session.execute(select(AgentSessionTable)).scalars().all()),
            "skills": len(
                db_session.execute(select(ProjectRoleSkillBindingTable)).scalars().all()
            ),
            "workspaces": len(
                db_session.execute(select(RepositoryWorkspaceTable)).scalars().all()
            ),
        }

        resp = client.get(f"/project-director/projects/{project_id}/setup-readiness")
        assert resp.status_code == 200

        after = {
            "runs": len(db_session.execute(select(RunTable)).scalars().all()),
            "sessions": len(db_session.execute(select(AgentSessionTable)).scalars().all()),
            "skills": len(
                db_session.execute(select(ProjectRoleSkillBindingTable)).scalars().all()
            ),
            "workspaces": len(
                db_session.execute(select(RepositoryWorkspaceTable)).scalars().all()
            ),
        }
        assert after == before
