"""BCG-07A evidence: Run logs and decision history replay for PD tasks.

This suite proves that a Project Director-created task can be replayed through
the existing read-only run/task evidence APIs after the manual Worker finalizes
the run.  It intentionally reuses the simulate executor to keep the proof
deterministic and provider/network independent.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.router import api_router
from app.core.config import settings
from app.core.db import get_db_session
from app.core.db_tables import ORMBase, ProjectDirectorPlanVersionTable, RunTable, TaskTable
from app.domain.run import RunStatus
from app.domain.task import TaskStatus


@pytest.fixture()
def isolated_runtime_data_dir(tmp_path):
    """Keep JSONL run logs for this test away from the repository data dir."""

    original_runtime_data_dir = settings.runtime_data_dir
    runtime_data_dir = tmp_path / "runtime-data"
    object.__setattr__(settings, "runtime_data_dir", runtime_data_dir)
    try:
        yield runtime_data_dir
    finally:
        object.__setattr__(settings, "runtime_data_dir", original_runtime_data_dir)


@pytest.fixture()
def sqlite_session_factory(tmp_path, isolated_runtime_data_dir):
    db_path = tmp_path / "orchestrator-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
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
            "name": "BCG-07A evidence replay project",
            "summary": "Prove run logs and decision history replay for a PD task.",
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
                "Build a replay evidence chain for a Project Director-created "
                "task after Worker execution."
            ),
        },
    )
    assert resp.status_code == 201
    session = resp.json()

    answers = [
        {"question_id": question["id"], "answer": f"Replay evidence answer {idx}"}
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

    resp = client.post(f"/project-director/plan-versions/{plan_version['id']}/confirm")
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
            "simulate: BCG-07A replay evidence execution for Project Director "
            f"created task #{idx}."
        )
    row.proposed_tasks_json = json.dumps(proposed_tasks, ensure_ascii=False)
    db_session.commit()


def test_project_director_created_task_run_can_be_replayed_via_read_only_evidence_apis(
    client: TestClient,
    db_session,
    isolated_runtime_data_dir: Path,
):
    """BCG-07A: task/run/log/decision-history evidence is replayable via GET APIs."""

    project_id = _create_project(client)
    session_id = _create_and_confirm_session(client, project_id=project_id)
    plan_version = _create_confirmed_plan_version(client, session_id=session_id)
    _force_simulate_descriptions(db_session, plan_version_id=plan_version["id"])

    create_resp = client.post(
        f"/project-director/plan-versions/{plan_version['id']}/create-tasks"
    )
    assert create_resp.status_code == 201
    created_task_ids = create_resp.json()["created_task_ids"]
    assert created_task_ids

    worker_resp = client.post(f"/workers/run-once?project_id={project_id}")
    assert worker_resp.status_code == 200
    worker = worker_resp.json()

    task_id = worker["task_id"]
    run_id = worker["run_id"]
    assert task_id in created_task_ids
    assert worker["claimed"] is True
    assert worker["task_status"] == "completed"
    assert worker["run_status"] == "succeeded"
    assert worker["execution_mode"] == "simulate"
    assert worker["quality_gate_passed"] is True
    assert worker["log_path"]

    task_row = db_session.get(TaskTable, UUID(task_id))
    run_row = db_session.get(RunTable, UUID(run_id))
    assert task_row is not None
    assert task_row.source_draft_id == f"pdv:{plan_version['id']}:{plan_version['version_no']}"
    assert task_row.status == TaskStatus.COMPLETED
    assert run_row is not None
    assert run_row.task_id == task_row.id
    assert run_row.status == RunStatus.SUCCEEDED
    assert run_row.quality_gate_passed is True

    log_file = isolated_runtime_data_dir / worker["log_path"]
    assert log_file.exists()

    task_runs_resp = client.get(f"/tasks/{task_id}/runs")
    assert task_runs_resp.status_code == 200
    task_runs = task_runs_resp.json()
    assert [item["id"] for item in task_runs] == [run_id]
    assert task_runs[0]["log_path"] == worker["log_path"]
    assert task_runs[0]["quality_gate_passed"] is True

    logs_resp = client.get(f"/runs/{run_id}/logs?limit=200")
    assert logs_resp.status_code == 200
    logs_payload = logs_resp.json()
    assert logs_payload["run_id"] == run_id
    assert logs_payload["log_path"] == worker["log_path"]
    assert logs_payload["truncated"] is False
    log_events = [event["event"] for event in logs_payload["events"]]
    for expected_event in [
        "task_routed",
        "role_handoff",
        "run_claimed",
        "context_built",
        "execution_finished",
        "verification_finished",
        "cost_estimated",
        "run_finalized",
    ]:
        assert expected_event in log_events

    trace_resp = client.get(f"/runs/{run_id}/decision-trace")
    assert trace_resp.status_code == 200
    trace_payload = trace_resp.json()
    assert trace_payload["run_id"] == run_id
    assert trace_payload["task_id"] == task_id
    assert trace_payload["run_status"] == "succeeded"
    assert trace_payload["quality_gate_passed"] is True
    trace_events = [item["event"] for item in trace_payload["trace_items"]]
    for expected_event in [
        "task_routed",
        "role_handoff",
        "run_claimed",
        "execution_finished",
        "verification_finished",
        "run_finalized",
    ]:
        assert expected_event in trace_events
    trace_stages = {item["stage"] for item in trace_payload["trace_items"]}
    assert {"routing", "handoff", "claim", "execution", "verification", "finalize"}.issubset(
        trace_stages
    )

    history_resp = client.get(f"/tasks/{task_id}/decision-history")
    assert history_resp.status_code == 200
    history_payload = history_resp.json()
    assert len(history_payload) == 1
    history_item = history_payload[0]
    assert history_item["run_id"] == run_id
    assert history_item["status"] == "succeeded"
    assert history_item["quality_gate_passed"] is True
    assert history_item["failure_category"] is None
    assert "Task and run were finalized." in history_item["headline"]
    assert {"routing", "handoff", "claim", "execution", "verification", "finalize"}.issubset(
        set(history_item["stages"])
    )
