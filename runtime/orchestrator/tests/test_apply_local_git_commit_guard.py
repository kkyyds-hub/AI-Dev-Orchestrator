"""Guard-path coverage for apply-local and git-commit error categories.

BCG-16A-R2: verifies that the guard chain returns precise error_category:
  - preflight_not_passed (before gate)
  - commit_candidate_missing (before gate)
  - gate_not_approved (after preflight + candidate)
  - apply_not_done (git-commit before apply)
  - apply_verification_failed (verification failed then commit blocked)
"""

from __future__ import annotations

import subprocess
import tempfile
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
from app.services.git_write_state_tracker import (
    _resolve_git_write_state_path,
)
from app.services.local_git_write_service import _save_git_write_state


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


# ── Helper: create a minimal Git repo ──────────────────────────────────

def _init_git_repo(repo_dir: Path) -> Path:
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "README.md").write_text("# Test\n", encoding="utf-8")
    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo_dir), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test"], cwd=str(repo_dir), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo_dir), capture_output=True, check=True)
    subprocess.run(["git", "add", "-A"], cwd=str(repo_dir), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo_dir), capture_output=True, check=True)
    return repo_dir


# ── Helper: build minimal guard chain objects ──────────────────────────

def _make_task(session, project_id) -> Task:
    task = Task(
        project_id=project_id,
        title=f"test-task-{uuid4().hex[:8]}",
        input_summary="test",
        priority=TaskPriority.NORMAL,
        risk_level=TaskRiskLevel.NORMAL,
        human_status=TaskHumanStatus.NONE,
    )
    return TaskRepository(session).create(task)


def _make_deliverable(session, project_id) -> Deliverable:
    did = uuid4()
    d = Deliverable(
        id=did,
        project_id=project_id,
        type=DeliverableType.STAGE_ARTIFACT,
        title=f"test-deliverable-{uuid4().hex[:8]}",
        stage=ProjectStage.PLANNING,
        created_by_role_code="architect",
        current_version_number=1,
    )
    DeliverableRepository(session).create_with_initial_version(
        deliverable=d,
        initial_version=DeliverableVersion(
            id=uuid4(),
            deliverable_id=did,
            version_number=1,
            author_role_code="architect",
            summary="test",
            content="test",
        ),
    )
    return d


def _make_change_plan(session, project_id, task_id, deliverable_id) -> ChangePlan:
    cp = ChangePlan(
        project_id=project_id,
        task_id=task_id,
        primary_deliverable_id=deliverable_id,
        title=f"test-plan-{uuid4().hex[:8]}",
        status=ChangePlanStatus.DRAFT,
        current_version_number=1,
    )
    record = ChangePlanRepository(session).create_with_initial_version(
        change_plan=cp,
        initial_version=ChangePlanVersion(
            change_plan_id=cp.id,
            version_number=1,
            intent_summary="test",
            source_summary="test",
            focus_terms=["test"],
            target_files=[
                ChangePlanTargetFile(
                    relative_path="README.md", language="Markdown", file_type="md",
                    rationale="test", match_reasons=["test"],
                )
            ],
            expected_actions=["test"],
            risk_notes=["test"],
            verification_commands=["python -c \"print('ok')\""],
            related_deliverable_ids=[deliverable_id],
        ),
    )
    return record.change_plan


def _make_batch_snapshots(session, project_id, task_ids, deliverable_id, cp_ids):
    """Create 2 plan snapshots for a change batch (min_plan_snapshots=2)."""
    snaps = []
    for i in range(2):
        snaps.append(ChangeBatchPlanSnapshot(
            change_plan_id=cp_ids[i], change_plan_title=f"test-plan-{i}",
            change_plan_status=ChangePlanStatus.DRAFT,
            selected_version_id=uuid4(), selected_version_number=1,
            task_id=task_ids[i], task_title=f"test-task-{i}",
            task_priority=TaskPriority.NORMAL, task_risk_level=TaskRiskLevel.NORMAL,
            intent_summary="test", source_summary="test", focus_terms=["test"],
            target_files=[ChangePlanTargetFile(relative_path="README.md", language="Markdown", file_type="md", match_reasons=["test"])],
            expected_actions=["test"], risk_notes=["test"],
            verification_commands=["python -c \"print('ok')\""],
            related_deliverables=[],
        ))
    return snaps


def _make_change_batch(session, project_id, workspace_id, plan_snapshots, preflight_status, ready):
    assert len(plan_snapshots) >= 2, "ChangeBatch requires at least 2 plan_snapshots"
    return ChangeBatchRepository(session).create(
        ChangeBatch(
            project_id=project_id,
            repository_workspace_id=workspace_id,
            status=ChangeBatchStatus.PREPARING,
            title="test-batch",
            summary="test",
            plan_snapshots=plan_snapshots,
            preflight=ChangeBatchPreflight(
                status=preflight_status,
                summary="test preflight summary",
                blocked=(not ready),
                ready_for_execution=ready,
                manual_confirmation_required=(not ready),
                manual_confirmation_status="not_required" if ready else "pending",
                evaluated_at=None,
            ),
        )
    )


def _make_commit_candidate(session, project_id, change_batch_id):
    cid = uuid4()
    return CommitCandidateRepository(session).create(
        CommitCandidate(
            id=cid,
            project_id=project_id,
            change_batch_id=change_batch_id,
            change_batch_title="test-batch",
            status=CommitCandidateStatus.DRAFT,
            current_version_number=1,
            versions=[
                CommitCandidateVersion(
                    commit_candidate_id=cid,
                    version_number=1,
                    message_title="test commit",
                    message_body="test body",
                    impact_scope=["test"],
                    related_files=["README.md"],
                    verification_summary=CommitCandidateVerificationSummary(
                        total_runs=1, passed_runs=1, failed_runs=0, skipped_runs=0,
                    ),
                    related_deliverables=[],
                    evidence_package_key="test-key",
                    evidence_summary="test evidence",
                )
            ],
        )
    )


def _setup_batch(session, project_id, workspace_id, deliverable_id, *, preflight_status, ready, with_candidate=False):
    """Create 2 tasks + 2 plans + 2 snapshots + 1 batch. Optionally create commit candidate."""
    tasks = [_make_task(session, project_id) for _ in range(2)]
    cp_ids = [_make_change_plan(session, project_id, tasks[i].id, deliverable_id).id for i in range(2)]
    snaps = _make_batch_snapshots(session, project_id, [t.id for t in tasks], deliverable_id, cp_ids)
    batch = _make_change_batch(session, project_id, workspace_id, snaps, preflight_status, ready)
    if with_candidate:
        _make_commit_candidate(session, project_id, batch.id)
    return batch


def _setup_apply_state(change_batch_id, applied=True, vp=True):
    state_path = _resolve_git_write_state_path(change_batch_id)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    _save_git_write_state(change_batch_id, {
        "apply_local": {
            "status": "applied" if (applied and vp) else "applied_with_failed_verification",
            "change_batch_id": str(change_batch_id),
            "changed_files": ["README.md"],
            "verification_passed": vp,
        },
        "git_write_actions_triggered": False,
    })


# ── Tests ──────────────────────────────────────────────────────────────


class TestApplyLocalGuardPreflightNotPassed:
    """apply-local returns preflight_not_passed when preflight is not ready."""

    def test_preflight_not_started(self, client, sqlite_session_factory, tmp_path):
        session = sqlite_session_factory()
        repo = _init_git_repo(tmp_path / "repo")
        project = ProjectRepository(session).create(Project(name="t1", summary="t"))
        wid = RepositoryWorkspaceRepository(session).upsert(RepositoryWorkspace(
            project_id=project.id, root_path=str(repo.resolve()), display_name="t",
            default_base_branch="main", allowed_workspace_root=str(tmp_path.resolve()))).id
        d = _make_deliverable(session, project.id)
        batch = _setup_batch(session, project.id, wid, d.id,
                              preflight_status=ChangeBatchPreflightStatus.NOT_STARTED, ready=False,
                              with_candidate=True)
        session.close()

        resp = client.post(f"/repositories/change-batches/{batch.id}/apply-local",
                           json={"files": [{"relative_path": "README.md", "content": "ok"}]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["error_category"] == "preflight_not_passed", f"got {data.get('error_category')}"
        assert data["status"] == "failed"

    def test_preflight_blocked(self, client, sqlite_session_factory, tmp_path):
        session = sqlite_session_factory()
        repo = _init_git_repo(tmp_path / "repo")
        project = ProjectRepository(session).create(Project(name="t2", summary="t"))
        wid = RepositoryWorkspaceRepository(session).upsert(RepositoryWorkspace(
            project_id=project.id, root_path=str(repo.resolve()), display_name="t",
            default_base_branch="main", allowed_workspace_root=str(tmp_path.resolve()))).id
        d = _make_deliverable(session, project.id)
        batch = _setup_batch(session, project.id, wid, d.id,
                              preflight_status=ChangeBatchPreflightStatus.BLOCKED_REQUIRES_CONFIRMATION,
                              ready=False, with_candidate=True)
        session.close()

        resp = client.post(f"/repositories/change-batches/{batch.id}/apply-local",
                           json={"files": [{"relative_path": "README.md", "content": "ok"}]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["error_category"] == "preflight_not_passed", f"got {data.get('error_category')}"


class TestApplyLocalGuardCommitCandidateMissing:
    """apply-local returns commit_candidate_missing when preflight ready but no candidate."""

    def test_commit_candidate_missing(self, client, sqlite_session_factory, tmp_path):
        session = sqlite_session_factory()
        repo = _init_git_repo(tmp_path / "repo")
        project = ProjectRepository(session).create(Project(name="t3", summary="t"))
        wid = RepositoryWorkspaceRepository(session).upsert(RepositoryWorkspace(
            project_id=project.id, root_path=str(repo.resolve()), display_name="t",
            default_base_branch="main", allowed_workspace_root=str(tmp_path.resolve()))).id
        d = _make_deliverable(session, project.id)
        batch = _setup_batch(session, project.id, wid, d.id,
                              preflight_status=ChangeBatchPreflightStatus.READY_FOR_EXECUTION,
                              ready=True, with_candidate=False)  # NO candidate
        session.close()

        resp = client.post(f"/repositories/change-batches/{batch.id}/apply-local",
                           json={"files": [{"relative_path": "README.md", "content": "ok"}]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["error_category"] == "commit_candidate_missing", f"got {data.get('error_category')}"


class TestApplyLocalGuardGateNotApproved:
    """apply-local returns gate_not_approved when preflight+candidate ready but gate not approved."""

    def test_gate_not_approved(self, client, sqlite_session_factory, tmp_path):
        session = sqlite_session_factory()
        repo = _init_git_repo(tmp_path / "repo")
        project = ProjectRepository(session).create(Project(name="t4", summary="t"))
        wid = RepositoryWorkspaceRepository(session).upsert(RepositoryWorkspace(
            project_id=project.id, root_path=str(repo.resolve()), display_name="t",
            default_base_branch="main", allowed_workspace_root=str(tmp_path.resolve()))).id
        d = _make_deliverable(session, project.id)
        batch = _setup_batch(session, project.id, wid, d.id,
                              preflight_status=ChangeBatchPreflightStatus.READY_FOR_EXECUTION,
                              ready=True, with_candidate=True)
        session.close()

        resp = client.post(f"/repositories/change-batches/{batch.id}/apply-local",
                           json={"files": [{"relative_path": "README.md", "content": "ok"}]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["error_category"] == "gate_not_approved", f"got {data.get('error_category')}"


class TestGitCommitGuardApplyNotDone:
    """git-commit returns apply_not_done when called before apply-local."""

    def test_commit_before_apply(self, client, sqlite_session_factory, tmp_path):
        session = sqlite_session_factory()
        repo = _init_git_repo(tmp_path / "repo")
        project = ProjectRepository(session).create(Project(name="t5", summary="t"))
        wid = RepositoryWorkspaceRepository(session).upsert(RepositoryWorkspace(
            project_id=project.id, root_path=str(repo.resolve()), display_name="t",
            default_base_branch="main", allowed_workspace_root=str(tmp_path.resolve()))).id
        d = _make_deliverable(session, project.id)
        batch = _setup_batch(session, project.id, wid, d.id,
                              preflight_status=ChangeBatchPreflightStatus.READY_FOR_EXECUTION,
                              ready=True, with_candidate=False)
        session.close()

        resp = client.post(f"/repositories/change-batches/{batch.id}/git-commit", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["error_category"] == "apply_not_done", f"got {data.get('error_category')}"


class TestGitCommitGuardVerificationFailed:
    """git-commit returns apply_verification_failed when apply verification failed."""

    def test_verification_failed_block_commit(self, client, sqlite_session_factory, tmp_path):
        session = sqlite_session_factory()
        repo = _init_git_repo(tmp_path / "repo")
        project = ProjectRepository(session).create(Project(name="t6", summary="t"))
        wid = RepositoryWorkspaceRepository(session).upsert(RepositoryWorkspace(
            project_id=project.id, root_path=str(repo.resolve()), display_name="t",
            default_base_branch="main", allowed_workspace_root=str(tmp_path.resolve()))).id
        d = _make_deliverable(session, project.id)
        batch = _setup_batch(session, project.id, wid, d.id,
                              preflight_status=ChangeBatchPreflightStatus.READY_FOR_EXECUTION,
                              ready=True, with_candidate=False)
        session.close()

        _setup_apply_state(batch.id, applied=True, vp=False)
        resp = client.post(f"/repositories/change-batches/{batch.id}/git-commit", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["error_category"] == "apply_verification_failed", f"got {data.get('error_category')}"
