"""Stage 6-A deliverable compatibility contract tests."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uuid import UUID, uuid4

from app.api.router import api_router
from app.core.db import get_db_session
from app.core.db_tables import ORMBase, TaskTable
from app.domain.change_batch import (
    ChangeBatch,
    ChangeBatchLinkedDeliverable,
    ChangeBatchPlanSnapshot,
    ChangeBatchPreflight,
    ChangeBatchPreflightStatus,
    ChangeBatchStatus,
)
from app.domain.change_plan import ChangePlanTargetFile
from app.domain.repository_workspace import RepositoryWorkspace
from app.domain.verification_run import (
    VerificationRun,
    VerificationRunCommandSource,
    VerificationRunStatus,
)
from app.repositories.change_batch_repository import ChangeBatchRepository
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)
from app.repositories.verification_run_repository import VerificationRunRepository


def _build_client(tmp_path):
    client, _ = _build_client_with_session_factory(tmp_path)
    return client


def _build_client_with_session_factory(tmp_path):
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
    return TestClient(app), session_factory


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


def _set_task_source_draft_id(session_factory, task_id: str, source_draft_id: str) -> None:
    session = session_factory()
    try:
        task_row = session.get(TaskTable, UUID(task_id))
        assert task_row is not None
        task_row.source_draft_id = source_draft_id
        session.commit()
    finally:
        session.close()


def _create_minimal_change_evidence_chain(
    session_factory,
    tmp_path,
    *,
    project_id: str,
    task_id: str,
    deliverable: dict,
):
    session = session_factory()
    try:
        project_uuid = UUID(project_id)
        task_uuid = UUID(task_id)
        deliverable_uuid = UUID(deliverable["id"])
        workspace = RepositoryWorkspaceRepository(session).upsert(
            RepositoryWorkspace(
                project_id=project_uuid,
                root_path=str((tmp_path / "repo").resolve()),
                display_name="Stage 6-A evidence fixture",
                default_base_branch="main",
                allowed_workspace_root=str(tmp_path.resolve()),
            )
        )
        plan_ids = [uuid4(), uuid4()]
        snapshots = [
            ChangeBatchPlanSnapshot(
                change_plan_id=plan_id,
                change_plan_title=f"Stage 6-A evidence plan {index + 1}",
                change_plan_status="draft",
                selected_version_id=uuid4(),
                selected_version_number=1,
                task_id=task_uuid,
                task_title="Prepare compatibility deliverable",
                task_priority="normal",
                task_risk_level="normal",
                intent_summary=f"Collect evidence {index + 1}",
                source_summary="Existing change-evidence chain.",
                target_files=[
                    ChangePlanTargetFile(
                        relative_path=f"docs/evidence-{index + 1}.md",
                        language="Markdown",
                        file_type="md",
                        rationale="Stage 6-A evidence projection fixture.",
                    )
                ],
                expected_actions=["read existing evidence"],
                risk_notes=["projection only"],
                verification_commands=["python -m pytest tests/test_deliverable_compat_contract.py"],
                related_deliverables=[
                    ChangeBatchLinkedDeliverable(
                        deliverable_id=deliverable_uuid,
                        title=deliverable["title"],
                        type=deliverable["type"],
                        current_version_number=deliverable["version_no"],
                    )
                ],
            )
            for index, plan_id in enumerate(plan_ids)
        ]
        change_batch = ChangeBatchRepository(session).create(
            ChangeBatch(
                project_id=project_uuid,
                repository_workspace_id=workspace.id,
                status=ChangeBatchStatus.PREPARING,
                title="Stage 6-A evidence batch",
                summary="Existing change-evidence batch linked to the deliverable.",
                plan_snapshots=snapshots,
                preflight=ChangeBatchPreflight(
                    status=ChangeBatchPreflightStatus.READY_FOR_EXECUTION,
                    summary="Ready for evidence projection.",
                    blocked=False,
                    ready_for_execution=True,
                    manual_confirmation_required=False,
                    manual_confirmation_status="not_required",
                ),
            )
        )
        verification_run = VerificationRunRepository(session).create(
            VerificationRun(
                project_id=project_uuid,
                repository_workspace_id=workspace.id,
                change_plan_id=plan_ids[0],
                change_batch_id=change_batch.id,
                command_source=VerificationRunCommandSource.MANUAL,
                command="python -m pytest tests/test_deliverable_compat_contract.py",
                status=VerificationRunStatus.PASSED,
                output_summary="Compatibility contract passed.",
            )
        )
        return change_batch.id, verification_run.id
    finally:
        session.close()


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
    assert any(
        ref["kind"] == "task" and ref["ref"] == task_id
        for ref in created["evidence_refs"]
    )
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
    assert any(
        ref["kind"] == "task" and ref["ref"] == task_id
        for ref in versions[0]["evidence_refs"]
    )


def test_deliverable_compat_derives_existing_evidence_chain(tmp_path):
    client, session_factory = _build_client_with_session_factory(tmp_path)
    project_id = _create_project(client)
    task_id = _create_task(client, project_id)
    source_draft_id = "pdv:test-plan:1"
    _set_task_source_draft_id(session_factory, task_id, source_draft_id)

    create_response = client.post(
        "/deliverables",
        json={
            "project_id": project_id,
            "task_id": task_id,
            "type": "stage_artifact",
            "title": "Evidence-backed deliverable",
            "created_by": "engineer",
            "summary": "Evidence-backed summary.",
            "content_markdown": "# Evidence-backed deliverable",
        },
    )
    assert create_response.status_code == 201, create_response.text
    deliverable = create_response.json()
    deliverable_id = deliverable["id"]
    assert deliverable["source_draft_id"] == source_draft_id
    assert deliverable["repository_change_id"] is None
    assert {ref["kind"] for ref in deliverable["evidence_refs"]} >= {
        "task",
        "source_draft",
    }

    change_batch_id, verification_run_id = _create_minimal_change_evidence_chain(
        session_factory,
        tmp_path,
        project_id=project_id,
        task_id=task_id,
        deliverable=deliverable,
    )

    detail_response = client.get(f"/deliverables/{deliverable_id}")
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()
    assert detail["source_draft_id"] == source_draft_id
    assert detail["repository_change_id"] == str(change_batch_id)
    kinds = {ref["kind"] for ref in detail["evidence_refs"]}
    assert kinds >= {
        "task",
        "source_draft",
        "change_batch",
        "change_plan",
        "verification_run",
    }
    assert any(
        ref["kind"] == "verification_run" and ref["ref"] == str(verification_run_id)
        for ref in detail["evidence_refs"]
    )
    assert detail["versions"][0]["source_draft_id"] == source_draft_id
    assert detail["versions"][0]["repository_change_id"] == str(change_batch_id)

    list_response = client.get(f"/deliverables?project_id={project_id}")
    assert list_response.status_code == 200, list_response.text
    listed = list_response.json()[0]
    assert listed["source_draft_id"] == source_draft_id
    assert listed["repository_change_id"] == str(change_batch_id)
    assert listed["latest_version"]["source_draft_id"] == source_draft_id
    assert listed["latest_version"]["repository_change_id"] == str(change_batch_id)

    versions_response = client.get(f"/deliverables/{deliverable_id}/versions")
    assert versions_response.status_code == 200, versions_response.text
    version = versions_response.json()[0]
    assert version["source_draft_id"] == source_draft_id
    assert version["repository_change_id"] == str(change_batch_id)


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
