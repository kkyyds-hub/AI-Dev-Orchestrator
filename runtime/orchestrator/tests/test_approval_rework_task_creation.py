"""Tests for BCG-10-R1 approval-driven executable rework task creation."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api.router import api_router
from app.core.db import get_db_session
from app.core.db_tables import ORMBase, TaskTable
from app.domain.task import TaskStatus


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


def _create_project(client: TestClient) -> str:
    response = client.post(
        "/projects",
        json={
            "name": "BCG-10-R1 approval rework project",
            "summary": "Verify negative approval decisions create executable rework tasks.",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_source_task(client: TestClient, project_id: str) -> str:
    response = client.post(
        "/tasks",
        json={
            "project_id": project_id,
            "title": "Create original deliverable",
            "input_summary": "Prepare the initial deliverable for approval.",
            "acceptance_criteria": ["Initial deliverable exists"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_deliverable(client: TestClient, project_id: str, task_id: str) -> dict:
    response = client.post(
        "/deliverables",
        json={
            "project_id": project_id,
            "type": "prd",
            "title": "BCG-10-R1 PRD",
            "stage": "planning",
            "created_by_role_code": "product_manager",
            "summary": "Initial PRD submitted for boss approval.",
            "content": "# Initial PRD\n\nNeeds approval before execution.",
            "content_format": "markdown",
            "source_task_id": task_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_approval(client: TestClient, deliverable_id: str) -> dict:
    response = client.post(
        "/approvals",
        json={
            "deliverable_id": deliverable_id,
            "requester_role_code": "product_manager",
            "request_note": "Please review the PRD.",
            "due_in_hours": 24,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _rework_tasks(db_session, approval_id: str) -> list[TaskTable]:
    return list(
        db_session.execute(
            select(TaskTable)
            .where(TaskTable.source_draft_id.like("arw:%"))
            .where(TaskTable.input_summary.contains(approval_id))
            .order_by(TaskTable.created_at.asc())
        ).scalars()
    )


def test_request_changes_creates_executable_rework_task(client, db_session):
    project_id = _create_project(client)
    source_task_id = _create_source_task(client, project_id)
    deliverable = _create_deliverable(client, project_id, source_task_id)
    approval = _create_approval(client, deliverable["id"])

    response = client.post(
        f"/approvals/{approval['id']}/actions",
        json={
            "action": "request_changes",
            "actor_name": "Boss",
            "summary": "Please tighten the rollout section.",
            "comment": "The risk fallback and success metrics are too vague.",
            "requested_changes": ["Add rollout fallback", "Define success metrics"],
            "highlighted_risks": ["Ambiguous launch guardrail"],
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "changes_requested"

    tasks = _rework_tasks(db_session, approval["id"])
    assert len(tasks) == 1
    task = tasks[0]
    assert str(task.project_id) == project_id
    assert task.status == TaskStatus.PENDING
    assert task.priority == "high"
    assert task.risk_level == "high"
    assert task.source_draft_id.startswith("arw:")
    assert len(task.source_draft_id) <= 50
    assert approval["id"] in task.input_summary
    assert "request_changes" in task.input_summary
    assert "Add rollout fallback" in task.input_summary
    assert "Requested change handled: Add rollout fallback" in task.acceptance_criteria

    list_response = client.get("/tasks")
    assert list_response.status_code == 200
    queued = [item for item in list_response.json() if item["id"] == str(task.id)]
    assert queued and queued[0]["status"] == "pending"


def test_reject_creates_one_rework_task_and_closed_approval_is_idempotent(
    client,
    db_session,
):
    project_id = _create_project(client)
    source_task_id = _create_source_task(client, project_id)
    deliverable = _create_deliverable(client, project_id, source_task_id)
    approval = _create_approval(client, deliverable["id"])

    first_response = client.post(
        f"/approvals/{approval['id']}/actions",
        json={
            "action": "reject",
            "actor_name": "Boss",
            "summary": "Rejected until the PRD has concrete execution detail.",
            "requested_changes": ["Rewrite execution section"],
        },
    )
    assert first_response.status_code == 200, first_response.text
    assert first_response.json()["status"] == "rejected"

    second_response = client.post(
        f"/approvals/{approval['id']}/actions",
        json={
            "action": "reject",
            "actor_name": "Boss",
            "summary": "Duplicate reject should not create another task.",
        },
    )
    assert second_response.status_code == 422

    tasks = _rework_tasks(db_session, approval["id"])
    assert len(tasks) == 1
    assert tasks[0].status == TaskStatus.PENDING


def test_approve_does_not_create_rework_task(client, db_session):
    project_id = _create_project(client)
    source_task_id = _create_source_task(client, project_id)
    deliverable = _create_deliverable(client, project_id, source_task_id)
    approval = _create_approval(client, deliverable["id"])

    response = client.post(
        f"/approvals/{approval['id']}/actions",
        json={
            "action": "approve",
            "actor_name": "Boss",
            "summary": "Looks good.",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "approved"
    assert _rework_tasks(db_session, approval["id"]) == []


def test_missing_approval_still_returns_404_and_creates_no_task(client, db_session):
    missing_id = uuid4()

    response = client.post(
        f"/approvals/{missing_id}/actions",
        json={
            "action": "request_changes",
            "actor_name": "Boss",
            "summary": "Missing approval should fail.",
        },
    )

    assert response.status_code == 404
    tasks = list(db_session.execute(select(TaskTable)).scalars())
    assert tasks == []
