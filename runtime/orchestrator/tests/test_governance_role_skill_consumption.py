"""Governance role / Skill consumption readback API tests."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uuid import UUID

from app.api.router import api_router
from app.core.db import get_db_session
from app.core.db_tables import ORMBase, RunTable, TaskTable
from app.domain.project_role import ProjectRoleCode
from app.domain.run import (
    RunBudgetPressureLevel,
    RunBudgetStrategyAction,
    RunStatus,
    RunStrategyDecision,
)
from app.domain.task import TaskStatus
from app.repositories.run_repository import RunRepository


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


def _create_project(client: TestClient, *, name: str) -> str:
    resp = client.post(
        "/projects",
        json={
            "name": name,
            "summary": "Project used by governance consumption readback tests.",
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _strategy_decision(
    *,
    owner_role_code: ProjectRoleCode,
    skill_codes: list[str],
    skill_names: list[str],
) -> RunStrategyDecision:
    return RunStrategyDecision(
        owner_role_code=owner_role_code,
        model_tier="balanced",
        model_name="deepseek-v4-pro",
        selected_skill_codes=skill_codes,
        selected_skill_names=skill_names,
        budget_pressure_level=RunBudgetPressureLevel.NORMAL,
        budget_action=RunBudgetStrategyAction.FULL_SPEED,
        strategy_code=f"test-{owner_role_code.value}",
        summary="Test strategy decision persisted for governance readback.",
    )


def _create_task_with_run(
    db_session,
    *,
    project_id: str,
    title: str,
    owner_role_code: ProjectRoleCode,
    status: RunStatus = RunStatus.SUCCEEDED,
    skill_codes: list[str],
    skill_names: list[str],
    total_tokens: int = 0,
    estimated_cost: float = 0.0,
) -> RunTable:
    task = TaskTable(
        project_id=UUID(project_id),
        title=title,
        status=TaskStatus.COMPLETED,
        input_summary="simulate: governance consumption readback",
        owner_role_code=owner_role_code,
    )
    db_session.add(task)
    db_session.flush()

    run = RunTable(
        task_id=task.id,
        status=status,
        model_name="deepseek-v4-pro",
        owner_role_code=owner_role_code,
        result_summary=f"{title} finished.",
        total_tokens=total_tokens,
        estimated_cost=estimated_cost,
        strategy_decision_json=RunRepository._serialize_strategy_decision(
            _strategy_decision(
                owner_role_code=owner_role_code,
                skill_codes=skill_codes,
                skill_names=skill_names,
            )
        ),
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    return run


def test_project_role_skill_consumption_aggregates_persisted_runs(
    client: TestClient,
    db_session,
):
    project_id = _create_project(client, name="governance consumption project")
    other_project_id = _create_project(client, name="other project")

    _create_task_with_run(
        db_session,
        project_id=project_id,
        title="architect success",
        owner_role_code=ProjectRoleCode.ARCHITECT,
        skill_codes=["dependency_analysis", "solution_design"],
        skill_names=["依赖分析", "方案设计"],
        total_tokens=120,
        estimated_cost=0.012,
    )
    latest_architect_run = _create_task_with_run(
        db_session,
        project_id=project_id,
        title="architect failed",
        owner_role_code=ProjectRoleCode.ARCHITECT,
        status=RunStatus.FAILED,
        skill_codes=["dependency_analysis"],
        skill_names=["依赖分析"],
        total_tokens=30,
        estimated_cost=0.003,
    )
    _create_task_with_run(
        db_session,
        project_id=project_id,
        title="reviewer success",
        owner_role_code=ProjectRoleCode.REVIEWER,
        skill_codes=["risk_assessment"],
        skill_names=["风险评估"],
        total_tokens=40,
        estimated_cost=0.004,
    )
    _create_task_with_run(
        db_session,
        project_id=other_project_id,
        title="other project run",
        owner_role_code=ProjectRoleCode.ENGINEER,
        skill_codes=["implementation"],
        skill_names=["实现"],
        total_tokens=999,
        estimated_cost=9.99,
    )

    resp = client.get(f"/roles/projects/{project_id}/consumption")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["project_id"] == project_id
    assert payload["total_run_count"] == 3
    assert payload["role_consumption_count"] == 2
    assert payload["skill_consumption_count"] == 3

    roles = {item["role_code"]: item for item in payload["roles"]}
    assert roles["architect"]["run_count"] == 2
    assert roles["architect"]["succeeded_run_count"] == 1
    assert roles["architect"]["failed_run_count"] == 1
    assert roles["architect"]["total_tokens"] == 150
    assert roles["architect"]["latest_run_id"] == str(latest_architect_run.id)
    assert roles["reviewer"]["run_count"] == 1
    assert "engineer" not in roles

    skills = {item["skill_code"]: item for item in payload["skills"]}
    assert skills["dependency_analysis"]["run_count"] == 2
    assert skills["dependency_analysis"]["skill_name"] == "依赖分析"
    assert skills["solution_design"]["run_count"] == 1
    assert skills["risk_assessment"]["latest_owner_role_code"] == "reviewer"
    assert "implementation" not in skills


def test_project_role_skill_consumption_returns_404_for_missing_project(
    client: TestClient,
):
    resp = client.get("/roles/projects/11111111-1111-1111-1111-111111111111/consumption")

    assert resp.status_code == 404
