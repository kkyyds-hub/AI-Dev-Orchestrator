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
from app.domain.project import Project
from app.domain.task import Task, TaskPriority, TaskRiskLevel, TaskStatus
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository


@pytest.fixture()
def sqlite_session_factory(tmp_path):
    db_path = tmp_path / "orchestrator-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


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


@pytest.fixture()
def seeded_project(sqlite_session_factory):
    session = sqlite_session_factory()
    try:
        project = Project(
            name="阶段三项目总结项目",
            summary="验证项目总结生成、保存与读回链路是否稳定可用。",
        )
        project = ProjectRepository(session).create(project)

        TaskRepository(session).create(
            Task(
                project_id=project.id,
                title="解除交付清单阻塞",
                input_summary="整理最终交付清单并清除当前遗留阻塞项。",
                status=TaskStatus.BLOCKED,
                priority=TaskPriority.HIGH,
                risk_level=TaskRiskLevel.HIGH,
            )
        )
        TaskRepository(session).create(
            Task(
                project_id=project.id,
                title="补齐人工审批",
                input_summary="在推进下一阶段前等待负责人完成审批确认。",
                status=TaskStatus.WAITING_HUMAN,
                priority=TaskPriority.URGENT,
                risk_level=TaskRiskLevel.NORMAL,
            )
        )
        TaskRepository(session).create(
            Task(
                project_id=project.id,
                title="归档最终交付物",
                input_summary="在全部检查通过后归档交付产物。",
                status=TaskStatus.COMPLETED,
                priority=TaskPriority.NORMAL,
                risk_level=TaskRiskLevel.LOW,
            )
        )
        return str(project.id)
    finally:
        session.close()


def _assert_project_summary_payload(payload: dict, project_id: str) -> None:
    assert payload["project_id"] == project_id
    assert payload["status"] == "succeeded"
    assert payload["source"] == "rule_fallback"
    assert payload["model_provider"] == "local_rule_engine"
    assert payload["model_name"] == "project_summary.rule_fallback.v1"
    assert payload["triggered_ai"] is False
    assert payload["generated_at"] is not None
    assert payload["created_at"] is not None
    assert payload["updated_at"] is not None
    assert payload["source_fingerprint"] == payload["source_hash"]
    assert payload["prompt_hash"]
    assert payload["provider_receipt_id"] is None
    assert payload["error_summary"] is None
    assert payload["stale"] is False

    markdown = payload["summary_markdown"]
    assert "## 项目结论" in markdown
    assert "## 当前状态" in markdown
    assert "## 当前重点" in markdown
    assert "## 阶段进展" in markdown
    assert "## 下一步建议" in markdown
    assert "解除交付清单阻塞" in markdown
    assert "补齐人工审批" in markdown
    assert "项目状态：" in markdown
    assert "## Project Conclusion" not in markdown
    assert "## Current Status" not in markdown
    assert "## Current Focus" not in markdown
    assert "## Stage Progress" not in markdown
    assert "## Next Steps" not in markdown


def test_get_project_ai_summary_does_not_generate_when_empty(client, seeded_project):
    response = client.get(f"/projects/{seeded_project}/ai-summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == seeded_project
    assert payload["active_summary"] is None


def test_generate_project_ai_summary_saves_and_get_reads_back(client, seeded_project):
    generated = client.post(f"/projects/{seeded_project}/ai-summary/generate")

    assert generated.status_code == 200
    generated_payload = generated.json()
    _assert_project_summary_payload(generated_payload, seeded_project)

    readback = client.get(f"/projects/{seeded_project}/ai-summary")
    assert readback.status_code == 200
    readback_payload = readback.json()
    assert readback_payload["active_summary"]["id"] == generated_payload["id"]
    assert readback_payload["active_summary"]["summary_markdown"] == generated_payload["summary_markdown"]

    second_generate = client.post(f"/projects/{seeded_project}/ai-summary/generate")
    assert second_generate.status_code == 200
    assert second_generate.json()["id"] == generated_payload["id"]


def test_regenerate_project_ai_summary_creates_new_saved_snapshot(client, seeded_project):
    first = client.post(f"/projects/{seeded_project}/ai-summary/generate")
    assert first.status_code == 200
    first_payload = first.json()

    regenerated = client.post(f"/projects/{seeded_project}/ai-summary/regenerate")
    assert regenerated.status_code == 201
    regenerated_payload = regenerated.json()
    _assert_project_summary_payload(regenerated_payload, seeded_project)
    assert regenerated_payload["id"] != first_payload["id"]

    readback = client.get(f"/projects/{seeded_project}/ai-summary")
    assert readback.status_code == 200
    assert readback.json()["active_summary"]["id"] == regenerated_payload["id"]


def test_project_ai_summary_endpoints_return_404_for_missing_project(client):
    missing_id = uuid4()

    assert client.get(f"/projects/{missing_id}/ai-summary").status_code == 404
    assert client.post(f"/projects/{missing_id}/ai-summary/generate").status_code == 404
    assert client.post(f"/projects/{missing_id}/ai-summary/regenerate").status_code == 404
