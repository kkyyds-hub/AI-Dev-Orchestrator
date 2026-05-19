"""Tests for AI Project Director Confirmation Inbox.

BCG-03 Phase1: read-only aggregation of pending confirmations.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.router import api_router
from app.core.db import get_db_session
from app.core.db_tables import ORMBase
from app.domain.project_director_plan_version import PlanVersionStatus
from app.domain.project_director_session import ProjectDirectorSessionStatus


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


def _create_session(client, *, goal_text=None):
    """Create a session with answers submitted (ready_to_confirm)."""
    if goal_text is None:
        goal_text = "构建一个用户认证系统，包括登录、注册"
    resp = client.post(
        "/project-director/sessions",
        json={"goal_text": goal_text},
    )
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


# ── Tests ────────────────────────────────────────────────────────────


class TestConfirmationInbox:
    def test_ready_to_confirm_session_appears(self, client):
        """A session in ready_to_confirm status should appear in inbox."""
        session_id = _create_session(client)

        resp = client.get("/project-director/confirmations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

        goal_items = [
            i for i in data["items"] if i["source_type"] == "goal_confirmation"
        ]
        assert len(goal_items) >= 1
        goal = goal_items[0]
        assert goal["source_id"] == session_id
        assert goal["session_id"] == session_id
        assert goal["status"] == ProjectDirectorSessionStatus.READY_TO_CONFIRM.value
        assert goal["title"] == "目标确认"
        assert goal["confirm_api_hint"] == (
            f"POST /project-director/sessions/{session_id}/confirm"
        )
        assert "confirm" in goal["confirm_api_hint"]
        assert goal["next_action"]
        assert goal["risk_level"] == "normal"

    def test_confirmed_session_does_not_appear(self, client):
        """A confirmed session should NOT appear in inbox."""
        session_id = _create_session(client)
        _confirm_session(client, session_id)

        resp = client.get("/project-director/confirmations")
        data = resp.json()
        goal_ids = {
            i["source_id"]
            for i in data["items"]
            if i["source_type"] == "goal_confirmation"
        }
        assert session_id not in goal_ids

    def test_pending_confirmation_plan_version_appears(self, client):
        """A plan version in pending_confirmation should appear in inbox."""
        session_id = _create_session(client)
        _confirm_session(client, session_id)
        pv = _create_plan_version(client, session_id)

        resp = client.get("/project-director/confirmations")
        assert resp.status_code == 200
        data = resp.json()

        plan_items = [
            i for i in data["items"] if i["source_type"] == "plan_confirmation"
        ]
        assert len(plan_items) >= 1
        plan = plan_items[0]
        assert plan["source_id"] == pv["id"]
        assert plan["session_id"] == session_id
        assert plan["status"] == PlanVersionStatus.PENDING_CONFIRMATION.value
        assert "计划版本" in plan["title"]
        assert plan["confirm_api_hint"] == (
            f"POST /project-director/plan-versions/{pv['id']}/confirm"
        )

    def test_confirmed_plan_version_does_not_appear(self, client):
        """A confirmed plan version should NOT appear in inbox."""
        session_id = _create_session(client)
        _confirm_session(client, session_id)
        pv = _create_plan_version(client, session_id)
        _confirm_plan_version(client, pv["id"])

        resp = client.get("/project-director/confirmations")
        data = resp.json()
        plan_ids = {
            i["source_id"]
            for i in data["items"]
            if i["source_type"] == "plan_confirmation"
        }
        assert pv["id"] not in plan_ids

    def test_both_goal_and_plan_pending_appear(self, client):
        """When both goal (other session) and plan are pending, both appear."""
        # Session 1: confirmed + plan pending
        sid1 = _create_session(client)
        _confirm_session(client, sid1)
        _create_plan_version(client, sid1)

        # Session 2: ready_to_confirm (goal pending)
        sid2 = _create_session(client)

        resp = client.get("/project-director/confirmations")
        data = resp.json()
        assert data["total"] >= 2

        source_types = {i["source_type"] for i in data["items"]}
        assert "goal_confirmation" in source_types
        assert "plan_confirmation" in source_types

    def test_filter_by_project_id(self, client):
        """Filter confirmations by project_id."""
        # Create two sessions in ready_to_confirm status
        sid1 = _create_session(client)
        sid2 = _create_session(client, goal_text="另一个项目的目标：数据库迁移方案，范围明确")

        # Global query should see both
        resp = client.get("/project-director/confirmations")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

        # Filter by an arbitrary project_id → empty (neither session has project_id)
        resp = client.get(
            f"/project-director/projects/{uuid4()}/confirmations"
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_filter_by_session_id(self, client):
        """Filter confirmations by session_id."""
        sid1 = _create_session(client)
        sid2 = _create_session(client)

        # Session 1 has goal pending; confirm session 1 and add plan pending
        _confirm_session(client, sid1)
        _create_plan_version(client, sid1)

        # Filter by sid1 → plan_confirmation
        resp = client.get(
            f"/project-director/sessions/{sid1}/confirmations"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["source_type"] == "plan_confirmation"

        # Filter by sid2 → goal_confirmation
        resp = client.get(
            f"/project-director/sessions/{sid2}/confirmations"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["source_type"] == "goal_confirmation"

    def test_empty_inbox(self, client):
        """When nothing is pending, inbox should be empty."""
        # Don't create anything → empty
        resp = client.get("/project-director/confirmations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_inbox_sorted_by_updated_at_desc(self, client):
        """Items should be sorted by updated_at descending."""
        sid1 = _create_session(client)
        sid2 = _create_session(client)

        resp = client.get("/project-director/confirmations")
        data = resp.json()
        # Both are goal_confirmations
        goal_items = [
            i for i in data["items"] if i["source_type"] == "goal_confirmation"
        ]
        assert len(goal_items) >= 2
        # Most recently created should be first
        assert goal_items[0]["updated_at"] >= goal_items[1]["updated_at"]

    def test_does_not_change_source_state(self, client):
        """Reading inbox must not change any source object status."""
        session_id = _create_session(client)

        # Check session is ready_to_confirm
        resp = client.get(f"/project-director/sessions/{session_id}")
        status_before = resp.json()["status"]
        assert status_before == ProjectDirectorSessionStatus.READY_TO_CONFIRM.value

        # Query inbox multiple times
        for _ in range(3):
            client.get("/project-director/confirmations")
            client.get(f"/project-director/sessions/{session_id}/confirmations")

        # Status unchanged
        resp = client.get(f"/project-director/sessions/{session_id}")
        assert resp.json()["status"] == status_before

    def test_confirm_api_hint_present(self, client):
        """Every item must have a confirm_api_hint field."""
        # Session pending
        _create_session(client)

        resp = client.get("/project-director/confirmations")
        data = resp.json()
        for item in data["items"]:
            assert "confirm_api_hint" in item
            assert item["confirm_api_hint"]  # non-empty
            assert item["confirm_api_hint"].startswith("POST /project-director/")

    def test_all_required_fields_present(self, client):
        """Every item must have all required fields."""
        sid = _create_session(client)
        _confirm_session(client, sid)
        _create_plan_version(client, sid)

        required_fields = [
            "id", "source_type", "source_id", "project_id", "session_id",
            "title", "summary", "status", "risk_level", "next_action",
            "confirm_api_hint", "created_at", "updated_at",
        ]

        resp = client.get("/project-director/confirmations")
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            for field in required_fields:
                assert field in item, f"Missing field: {field}"
