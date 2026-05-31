"""CL-12 safe draft-chain readback coverage.

The readback endpoint must aggregate the repository draft evidence chain without
calling apply-local or git-commit.  It is deliberately review-only.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.router import api_router
from app.core.db import get_db_session
from app.core.db_tables import ORMBase
from app.domain.change_batch import (
    ChangeBatch,
    ChangeBatchLinkedDeliverable,
    ChangeBatchPlanSnapshot,
    ChangeBatchPreflight,
    ChangeBatchPreflightStatus,
    ChangeBatchStatus,
)
from app.domain.change_plan import (
    ChangePlan,
    ChangePlanStatus,
    ChangePlanTargetFile,
    ChangePlanVersion,
)
from app.domain.commit_candidate import (
    CommitCandidate,
    CommitCandidateLinkedDeliverable,
    CommitCandidateStatus,
    CommitCandidateVerificationSummary,
    CommitCandidateVersion,
)
from app.domain.deliverable import Deliverable, DeliverableType, DeliverableVersion
from app.domain.project import Project, ProjectStage
from app.domain.repository_workspace import RepositoryWorkspace
from app.domain.task import Task, TaskHumanStatus, TaskPriority, TaskRiskLevel
from app.repositories.change_batch_repository import ChangeBatchRepository
from app.repositories.change_plan_repository import ChangePlanRepository
from app.repositories.commit_candidate_repository import CommitCandidateRepository
from app.repositories.deliverable_repository import DeliverableRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)
from app.repositories.task_repository import TaskRepository


@pytest.fixture()
def sqlite_session_factory(tmp_path):
    db_path = tmp_path / "orchestrator-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
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


def _make_test_client(sqlite_session_factory) -> TestClient:
    app = FastAPI()
    app.include_router(api_router)

    def override_get_db_session():
        session = sqlite_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session
    return TestClient(app)


def _init_git_repo(repo_dir: Path) -> Path:
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "README.md").write_text("# Draft Chain\n", encoding="utf-8")
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=str(repo_dir),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(repo_dir),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=str(repo_dir),
        capture_output=True,
        check=True,
    )
    subprocess.run(["git", "add", "-A"], cwd=str(repo_dir), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(repo_dir),
        capture_output=True,
        check=True,
    )
    return repo_dir


def _make_task(session, project_id, title: str) -> Task:
    return TaskRepository(session).create(
        Task(
            project_id=project_id,
            title=title,
            input_summary=f"{title} input",
            priority=TaskPriority.NORMAL,
            risk_level=TaskRiskLevel.NORMAL,
            human_status=TaskHumanStatus.NONE,
        )
    )


def _make_deliverable(session, project_id) -> Deliverable:
    deliverable_id = uuid4()
    deliverable = Deliverable(
        id=deliverable_id,
        project_id=project_id,
        type=DeliverableType.STAGE_ARTIFACT,
        title="CL-12 draft evidence deliverable",
        stage=ProjectStage.PLANNING,
        created_by_role_code="architect",
        current_version_number=1,
    )
    DeliverableRepository(session).create_with_initial_version(
        deliverable=deliverable,
        initial_version=DeliverableVersion(
            id=uuid4(),
            deliverable_id=deliverable_id,
            version_number=1,
            author_role_code="architect",
            summary="deliverable evidence",
            content="deliverable evidence body",
        ),
    )
    return deliverable


def _make_change_plan(
    session,
    project_id,
    task_id,
    deliverable_id,
    title: str,
) -> ChangePlan:
    change_plan = ChangePlan(
        project_id=project_id,
        task_id=task_id,
        title=title,
        status=ChangePlanStatus.DRAFT,
        current_version_number=1,
    )
    record = ChangePlanRepository(session).create_with_initial_version(
        change_plan=change_plan,
        initial_version=ChangePlanVersion(
            change_plan_id=change_plan.id,
            version_number=1,
            intent_summary=f"{title} intent",
            source_summary=f"{title} source",
            focus_terms=["draft", "chain"],
            target_files=[
                ChangePlanTargetFile(
                    relative_path="README.md",
                    language="Markdown",
                    file_type="md",
                    rationale="CL-12 draft-chain target",
                    match_reasons=["test fixture"],
                )
            ],
            expected_actions=["review-only draft update"],
            risk_notes=["no git write"],
            verification_commands=["python -c \"print('ok')\""],
            related_deliverable_ids=[deliverable_id],
        ),
    )
    return record.change_plan


def _make_chain(sqlite_session_factory, tmp_path):
    session = sqlite_session_factory()
    try:
        repo = _init_git_repo(tmp_path / "repo")
        project = ProjectRepository(session).create(
            Project(name="CL-12 Draft Chain", summary="review-only chain")
        )
        workspace = RepositoryWorkspaceRepository(session).upsert(
            RepositoryWorkspace(
                project_id=project.id,
                root_path=str(repo.resolve()),
                display_name="draft-chain-fixture",
                default_base_branch="main",
                allowed_workspace_root=str(tmp_path.resolve()),
            )
        )

        tasks = [
            _make_task(session, project.id, "draft task 1"),
            _make_task(session, project.id, "draft task 2"),
        ]
        deliverable = _make_deliverable(session, project.id)
        plans = [
            _make_change_plan(
                session,
                project.id,
                tasks[0].id,
                deliverable.id,
                "draft plan 1",
            ),
            _make_change_plan(
                session,
                project.id,
                tasks[1].id,
                deliverable.id,
                "draft plan 2",
            ),
        ]
        snapshots = [
            ChangeBatchPlanSnapshot(
                change_plan_id=plans[index].id,
                change_plan_title=plans[index].title,
                change_plan_status=plans[index].status,
                selected_version_id=uuid4(),
                selected_version_number=1,
                task_id=tasks[index].id,
                task_title=tasks[index].title,
                task_priority=tasks[index].priority,
                task_risk_level=tasks[index].risk_level,
                intent_summary=f"intent {index}",
                source_summary=f"source {index}",
                focus_terms=["draft", "chain"],
                target_files=[
                    ChangePlanTargetFile(
                        relative_path="README.md",
                        language="Markdown",
                        file_type="md",
                        rationale="draft-chain target",
                        match_reasons=["readback"],
                    )
                ],
                expected_actions=["review-only"],
                risk_notes=["no apply-local"],
                verification_commands=["python -c \"print('ok')\""],
                related_deliverables=[
                    ChangeBatchLinkedDeliverable(
                        deliverable_id=deliverable.id,
                        title=deliverable.title,
                        type=deliverable.type,
                        current_version_number=deliverable.current_version_number,
                    )
                ],
            )
            for index in range(2)
        ]
        batch = ChangeBatchRepository(session).create(
            ChangeBatch(
                project_id=project.id,
                repository_workspace_id=workspace.id,
                status=ChangeBatchStatus.PREPARING,
                title="CL-12 review-only batch",
                summary="Batch used by the safe draft-chain readback test.",
                plan_snapshots=snapshots,
                preflight=ChangeBatchPreflight(
                    status=ChangeBatchPreflightStatus.READY_FOR_EXECUTION,
                    summary="Preflight ready for review-only draft generation.",
                    blocked=False,
                    ready_for_execution=True,
                    manual_confirmation_required=False,
                    manual_confirmation_status="not_required",
                ),
            )
        )
        candidate_id = uuid4()
        CommitCandidateRepository(session).create(
            CommitCandidate(
                id=candidate_id,
                project_id=project.id,
                change_batch_id=batch.id,
                change_batch_title=batch.title,
                status=CommitCandidateStatus.DRAFT,
                current_version_number=1,
                versions=[
                    CommitCandidateVersion(
                        commit_candidate_id=candidate_id,
                        version_number=1,
                        message_title="review-only CL-12 draft",
                        message_body="This is a review-only candidate; no git commit.",
                        impact_scope=["CL-12 evidence chain"],
                        related_files=["README.md"],
                        verification_summary=CommitCandidateVerificationSummary(
                            total_runs=1,
                            passed_runs=1,
                            failed_runs=0,
                            skipped_runs=0,
                        ),
                        related_deliverables=[
                            CommitCandidateLinkedDeliverable(
                                deliverable_id=deliverable.id,
                                title=deliverable.title,
                                type=deliverable.type,
                                stage=deliverable.stage,
                                current_version_number=deliverable.current_version_number,
                                latest_version_summary="deliverable evidence",
                            )
                        ],
                        evidence_package_key="cl12-draft-evidence",
                        evidence_summary="review-only evidence package",
                    )
                ],
            )
        )
        return project.id, batch.id
    finally:
        session.close()


def test_draft_chain_readback_is_review_only_and_does_not_trigger_git_writes(
    sqlite_session_factory,
    tmp_path,
):
    project_id, batch_id = _make_chain(sqlite_session_factory, tmp_path)

    with _make_test_client(sqlite_session_factory) as test_client:
        response = test_client.get(
            f"/repositories/projects/{project_id}/draft-chain-readback"
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["project_id"] == str(project_id)
    assert data["review_only"] is True
    assert data["safe_runtime_path"] is True
    assert data["selected_change_batch_id"] == str(batch_id)
    assert data["change_plan_count"] == 2
    assert data["change_batch_count"] == 1
    assert data["preflight_status"] == "ready_for_execution"
    assert data["preflight_ready_for_execution"] is True
    assert data["commit_candidate_present"] is True
    assert data["commit_candidate_status"] == "draft"
    assert data["commit_candidate_current_version"] == 1
    assert data["commit_candidate_revision_count"] == 1
    assert data["commit_candidate_related_file_count"] == 1
    assert data["commit_candidate_evidence_package_key"] == "cl12-draft-evidence"
    assert data["commit_candidate_review_only"] is True
    assert data["apply_local_triggered"] is False
    assert data["git_commit_triggered"] is False
    assert data["git_write_actions_triggered"] is False
    assert "/apply-local" in data["forbidden_actions"][0]
    assert "/git-commit" in data["forbidden_actions"][1]
    assert data["day15_flow"]["selected_change_batch_id"] == str(batch_id)
