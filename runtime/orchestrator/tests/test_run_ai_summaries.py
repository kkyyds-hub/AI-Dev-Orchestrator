from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.router import api_router
from app.core.db import get_db_session
from app.core.db_tables import ORMBase, RunTable
from app.domain._base import utc_now
from app.domain.project import Project
from app.domain.run import RunStatus
from app.domain.run_ai_summary import RunAISummarySource, RunAISummaryStatus
from app.domain.task import Task, TaskPriority, TaskRiskLevel, TaskStatus
from app.repositories.project_repository import ProjectRepository
from app.repositories.run_ai_summary_repository import RunAISummaryRepository
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.run_ai_summary_service import RunAISummaryService


@pytest.fixture()
def sqlite_session_factory(tmp_path):
    db_path = tmp_path / "orchestrator-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@pytest.fixture()
def db_session(sqlite_session_factory):
    session = sqlite_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def seeded_run(db_session):
    project = Project(
        name="AI 摘要测试项目",
        summary="用于验证运行摘要后端契约。",
    )
    project = ProjectRepository(db_session).create(project)

    task = Task(
        project_id=project.id,
        title="整理运行摘要",
        input_summary="为当前运行生成一段中文摘要。",
        status=TaskStatus.COMPLETED,
        priority=TaskPriority.NORMAL,
        risk_level=TaskRiskLevel.NORMAL,
    )
    task = TaskRepository(db_session).create(task)

    run_id = uuid4()
    db_session.add(
        RunTable(
            id=run_id,
            task_id=task.id,
            status=RunStatus.SUCCEEDED,
            result_summary="执行完成，交付结果已记录。",
            verification_summary="验证通过。",
            quality_gate_passed=True,
            created_at=utc_now(),
            started_at=utc_now() - timedelta(minutes=5),
            finished_at=utc_now(),
        )
    )
    db_session.commit()

    return project, task, run_id


@pytest.fixture()
def run_ai_summary_service(db_session):
    return RunAISummaryService(
        run_repository=RunRepository(db_session),
        task_repository=TaskRepository(db_session),
        run_ai_summary_repository=RunAISummaryRepository(db_session),
    )


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


def test_generate_and_regenerate_run_ai_summary(run_ai_summary_service, db_session, seeded_run):
    project, task, run_id = seeded_run

    first = run_ai_summary_service.generate_run_summary(run_id=run_id)
    second = run_ai_summary_service.generate_run_summary(run_id=run_id)
    regenerated = run_ai_summary_service.generate_run_summary(run_id=run_id, regenerate=True)

    assert first.id == second.id
    assert first.status == RunAISummaryStatus.SUCCEEDED
    assert first.source == RunAISummarySource.RULE_FALLBACK
    assert first.source_fingerprint == first.source_hash
    assert first.model_provider == "local_rule_engine"
    assert first.model_name == "run_summary.rule_fallback.v2"
    assert first.prompt_hash
    assert first.summary_markdown.count("## ") == 5

    assert regenerated.id != first.id
    assert regenerated.stale is False

    history = RunAISummaryRepository(db_session).list_by_run_id(run_id)
    assert len(history) == 2
    assert history[0].id == regenerated.id
    assert history[1].id == first.id
    assert history[1].stale is True
    assert history[0].project_id == project.id
    assert history[0].task_id == task.id


def test_run_ai_summary_endpoints(client, seeded_run):
    _, _, run_id = seeded_run

    created = client.post(f"/runs/{run_id}/ai-summaries")
    assert created.status_code == 200
    created_payload = created.json()
    assert created_payload["run_id"] == str(run_id)
    assert created_payload["status"] == RunAISummaryStatus.SUCCEEDED.value
    assert created_payload["source"] == RunAISummarySource.RULE_FALLBACK.value
    assert created_payload["source_fingerprint"] == created_payload["source_hash"]
    assert created_payload["prompt_hash"]
    assert created_payload["summary_markdown"].count("## ") == 5

    history = client.get(f"/runs/{run_id}/ai-summaries")
    assert history.status_code == 200
    history_payload = history.json()
    assert history_payload["run_id"] == str(run_id)
    assert history_payload["active_summary"]["id"] == created_payload["id"]
    assert len(history_payload["summaries"]) == 1

    regenerated = client.post(f"/runs/{run_id}/ai-summaries/regenerate")
    assert regenerated.status_code == 201
    regenerated_payload = regenerated.json()
    assert regenerated_payload["id"] != created_payload["id"]
    assert regenerated_payload["status"] == RunAISummaryStatus.SUCCEEDED.value
    assert regenerated_payload["source"] == RunAISummarySource.RULE_FALLBACK.value

    history_after = client.get(f"/runs/{run_id}/ai-summaries")
    assert history_after.status_code == 200
    history_after_payload = history_after.json()
    assert len(history_after_payload["summaries"]) == 2
    assert history_after_payload["active_summary"]["id"] == regenerated_payload["id"]
    assert history_after_payload["summaries"][1]["stale"] is True


def test_run_ai_summary_endpoint_returns_404_for_missing_run(client):
    missing_run_id = uuid4()
    response = client.post(f"/runs/{missing_run_id}/ai-summaries")
    assert response.status_code == 404
