"""Stage 6-A deliverable compatibility contract tests."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.router import api_router
from app.core.db import get_db_session
from app.core.db_tables import ORMBase


def _build_client(tmp_path):
    db_path = tmp_path / "orchestrator-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    app = FastAPI()
    app.include_router(api_router)

    def override_get_db_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session
    return TestClient(app)


def _create_project(client: TestClient) -> str:
    response = client.post(
        "/projects",
        json={
            "name": "Stage 6-A deliverable contract project",
            "summary": "Verify deliverable compatibility API contract.",
            "stage": "delivery",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_task(client: TestClient, project_id: str) -> str:
    response = client.post(
        "/tasks",
        json={
            "project_id": project_id,
            "title": "Prepare compatibility deliverable",
            "input_summary": "Create a deliverable via Stage 6-A payload aliases.",
            "acceptance_criteria": ["Deliverable exists"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_stage_6a_deliverable_fields_and_compat_routes(tmp_path):
    client = _build_client(tmp_path)
    project_id = _create_project(client)
    task_id = _create_task(client, project_id)

    create_response = client.post(
        "/deliverables",
        json={
            "project_id": project_id,
            "task_id": task_id,
            "type": "spec",
            "title": "Stage 6-A Compatibility Spec",
            "created_by": "engineer",
            "summary": "Compatibility contract summary.",
            "content_markdown": "# Compatibility Spec\n\nFrontend-readable body.",
            "evidence_refs": [{"kind": "test", "ref": "pytest"}],
            "source_type": "task",
            "source_label": "Compatibility task",
        },
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    deliverable_id = created["id"]

    assert created["type"] == "spec"
    assert created["status"] == "draft"
    assert created["version_no"] == 1
    assert created["current_version_number"] == 1
    assert created["created_by"] == "engineer"
    assert created["task_id"] == task_id
    assert created["run_id"] is None
    assert created["content_markdown"].startswith("# Compatibility Spec")
    assert created["evidence_refs"] == []
    assert created["source_type"] == "task"

    list_response = client.get(f"/deliverables?project_id={project_id}")
    assert list_response.status_code == 200, list_response.text
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["id"] == deliverable_id
    assert listed[0]["status"] == "draft"
    assert listed[0]["version_no"] == 1
    assert listed[0]["summary"] == "Compatibility contract summary."
    assert listed[0]["content_markdown"].startswith("# Compatibility Spec")
    assert listed[0]["latest_version"]["version_no"] == 1
    assert listed[0]["latest_version"]["task_id"] == task_id

    detail_response = client.get(f"/deliverables/{deliverable_id}")
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()
    assert detail["status"] == "draft"
    assert detail["content_markdown"].startswith("# Compatibility Spec")
    assert detail["versions"][0]["version_no"] == 1
    assert detail["versions"][0]["content_markdown"].startswith("# Compatibility Spec")

    versions_response = client.get(f"/deliverables/{deliverable_id}/versions")
    assert versions_response.status_code == 200, versions_response.text
    versions = versions_response.json()
    assert len(versions) == 1
    assert versions[0]["version_no"] == 1
    assert versions[0]["task_id"] == task_id
    assert versions[0]["evidence_refs"] == []


def test_deliverable_status_derives_from_latest_current_version_approval(tmp_path):
    client = _build_client(tmp_path)
    project_id = _create_project(client)
    task_id = _create_task(client, project_id)

    create_response = client.post(
        "/deliverables",
        json={
            "project_id": project_id,
            "task_id": task_id,
            "type": "prd",
            "title": "Approval Status PRD",
            "stage": "delivery",
            "created_by_role_code": "product_manager",
            "summary": "Ready for approval.",
            "content": "# PRD\n\nReady for approval.",
        },
    )
    assert create_response.status_code == 201, create_response.text
    deliverable_id = create_response.json()["id"]

    approval_response = client.post(
        "/approvals",
        json={
            "deliverable_id": deliverable_id,
            "requester_role_code": "product_manager",
            "request_note": "Please approve this deliverable.",
        },
    )
    assert approval_response.status_code == 201, approval_response.text

    submitted_response = client.get(f"/deliverables/{deliverable_id}")
    assert submitted_response.status_code == 200, submitted_response.text
    assert submitted_response.json()["status"] == "pending_review"

    version_response = client.post(
        f"/deliverables/{deliverable_id}/versions",
        json={
            "created_by": "engineer",
            "summary": "Revised after submission.",
            "content_markdown": "# PRD\n\nRevised draft.",
        },
    )
    assert version_response.status_code == 200, version_response.text
    assert version_response.json()["version_no"] == 2
    assert version_response.json()["status"] == "draft"

    current_response = client.get(f"/deliverables/{deliverable_id}")
    assert current_response.status_code == 200, current_response.text
    assert current_response.json()["version_no"] == 2
    assert current_response.json()["status"] == "draft"
