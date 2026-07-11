"""BCG-05A evidence: Project Director created Task -> manual Worker -> Run.

This suite proves that tasks created by BCG-04A are real queue tasks that the
existing manual worker endpoint can claim and turn into persisted Run rows while
the runtime launch gate remains authoritative over a requested simulate path.
"""

from __future__ import annotations

import json
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api.router import api_router
from app.core.config import settings
from app.core.db import get_db_session
from app.core.db_tables import (
    ORMBase,
    ProjectDirectorPlanVersionTable,
    RunTable,
    TaskTable,
)
from app.domain.run import RunStatus
from app.domain.task import TaskStatus


@pytest.fixture()
def sqlite_session_factory(tmp_path):
    db_path = tmp_path / "orchestrator-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


@pytest.fixture(autouse=True)
def simulate_execution_override():
    """Keep this evidence test on its declared deterministic simulate path."""

    original_override = settings.worker_simulate_execution_override
    object.__setattr__(settings, "worker_simulate_execution_override", True)
    try:
        yield
    finally:
        object.__setattr__(
            settings,
            "worker_simulate_execution_override",
            original_override,
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
    resp = client.post(
        "/projects",
        json={
            "name": "BCG-05A worker evidence project",
            "summary": "Prove Project Director created tasks can be claimed by worker.",
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_and_confirm_session(client: TestClient, *, project_id: str) -> str:
    resp = client.post(
        "/project-director/sessions",
        json={
            "project_id": project_id,
            "goal_text": (
                "Build a small audit trail that proves created Project Director "
                "tasks can enter the worker run chain."
            ),
        },
    )
    assert resp.status_code == 201
    session = resp.json()

    answers = [
        {"question_id": question["id"], "answer": f"Evidence answer {idx}"}
        for idx, question in enumerate(session["clarifying_questions"])
    ]
    resp = client.post(
        f"/project-director/sessions/{session['id']}/answers",
        json={"answers": answers},
    )
    assert resp.status_code == 200

    resp = client.post(f"/project-director/sessions/{session['id']}/confirm")
    assert resp.status_code == 200
    return session["id"]


def _create_confirmed_plan_version(client: TestClient, *, session_id: str) -> dict:
    resp = client.post(f"/project-director/sessions/{session_id}/plan-versions")
    assert resp.status_code == 201
    plan_version = resp.json()

    resp = client.post(
        f"/project-director/plan-versions/{plan_version['id']}/confirm"
    )
    assert resp.status_code == 200

    resp = client.get(f"/project-director/plan-versions/{plan_version['id']}")
    assert resp.status_code == 200
    return resp.json()


def _force_simulate_descriptions(db_session, *, plan_version_id: str) -> None:
    row = db_session.get(ProjectDirectorPlanVersionTable, UUID(plan_version_id))
    assert row is not None
    proposed_tasks = json.loads(row.proposed_tasks_json)
    assert proposed_tasks
    for idx, task in enumerate(proposed_tasks, start=1):
        task["description"] = (
            "simulate: BCG-05A evidence execution for Project Director "
            f"created task #{idx}."
        )
    row.proposed_tasks_json = json.dumps(proposed_tasks, ensure_ascii=False)
    db_session.commit()


def test_created_project_director_task_can_be_claimed_by_worker_and_create_run(
    client: TestClient,
    db_session,
):
    """BCG-04A created Task is claimed by POST /workers/run-once and gets a Run."""

    project_id = _create_project(client)
    session_id = _create_and_confirm_session(client, project_id=project_id)
    plan_version = _create_confirmed_plan_version(client, session_id=session_id)
    _force_simulate_descriptions(db_session, plan_version_id=plan_version["id"])

    create_resp = client.post(
        f"/project-director/plan-versions/{plan_version['id']}/create-tasks"
    )
    assert create_resp.status_code == 201
    creation = create_resp.json()
    created_task_ids = creation["created_task_ids"]
    assert created_task_ids

    pre_worker_runs = db_session.execute(
        select(RunTable).where(RunTable.task_id.in_([UUID(tid) for tid in created_task_ids]))
    ).scalars().all()
    assert pre_worker_runs == []

    worker_resp = client.post(f"/workers/run-once?project_id={project_id}")
    assert worker_resp.status_code == 200
    worker = worker_resp.json()

    assert worker["claimed"] is True
    assert worker["task_id"] in created_task_ids
    assert worker["run_id"] is not None
    assert worker["execution_mode"] == "runtime_launch_gate"
    assert worker["task_status"] == "blocked"
    assert worker["run_status"] == "cancelled"
    assert worker["result_summary"]
    assert worker["log_path"]

    task_row = db_session.get(TaskTable, UUID(worker["task_id"]))
    run_row = db_session.get(RunTable, UUID(worker["run_id"]))

    assert task_row is not None
    assert task_row.id == UUID(worker["task_id"])
    assert task_row.source_draft_id == f"pdv:{plan_version['id']}:{plan_version['version_no']}"
    assert task_row.status == TaskStatus.BLOCKED

    assert run_row is not None
    assert run_row.task_id == task_row.id
    assert run_row.status == RunStatus.CANCELLED
    assert run_row.result_summary
    assert run_row.log_path == worker["log_path"]
    assert run_row.quality_gate_passed is False
