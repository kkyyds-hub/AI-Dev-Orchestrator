"""P1-C WorktreePlan dry-run coverage.

These tests verify pure planning behavior only. They do not call git, create
worktrees, create branches, or write to a repository.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes.agent_threads import WorktreePlanResponse
from app.core.db_tables import ORMBase
from app.domain.agent_session import (
    AgentSessionPhase,
    AgentSessionReviewStatus,
    AgentSessionStatus,
)
from app.domain.repository_workspace import RepositoryWorkspace
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.repository_workspace_repository import RepositoryWorkspaceRepository
from app.services.worktree_plan_service import (
    BranchNamePolicy,
    WorktreeGuardService,
    WorktreePlanService,
)


@pytest.fixture()
def db_session(tmp_path):
    """Create an isolated SQLite database with current metadata."""

    db_path = tmp_path / "orchestrator-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def _create_agent_session(db_session, *, project_id):
    """Persist one minimal AgentSession row for planning tests."""

    return AgentSessionRepository(db_session).create(
        project_id=project_id,
        task_id=uuid4(),
        run_id=uuid4(),
        status=AgentSessionStatus.RUNNING,
        review_status=AgentSessionReviewStatus.NONE,
        current_phase=AgentSessionPhase.CONTEXT_READY,
        owner_role_code=None,
        context_checkpoint_id=None,
        context_rehydrated=False,
        summary="Planning only",
    )


def test_branch_name_policy_generates_stable_safe_session_branch():
    """BranchNamePolicy is deterministic and git-safe without git calls."""

    session_id = uuid4()
    policy = BranchNamePolicy()

    branch_name = policy.generate(
        project_prefix="AI Dev Orchestrator!",
        session_id=session_id,
    )

    assert branch_name == policy.generate(
        project_prefix="AI Dev Orchestrator!",
        session_id=session_id,
    )
    assert branch_name.startswith("session/ai-dev-orchestrator-")
    assert branch_name.endswith(session_id.hex[:8])
    assert len(branch_name) <= BranchNamePolicy.max_length
    assert policy.validate(branch_name)


@pytest.mark.parametrize(
    "branch_name",
    [
        "",
        "/bad",
        "bad/",
        "bad//name",
        "bad..name",
        "bad.lock",
        "bad@{name",
        "bad\\name",
    ],
)
def test_branch_name_policy_rejects_unsafe_branch_names(branch_name):
    """Unsafe branch names are blocked before any future git operation."""

    assert not BranchNamePolicy().validate(branch_name)


def test_worktree_guard_blocks_path_outside_allowed_root(tmp_path):
    """Planned path must stay inside the configured allowed root."""

    allowed_root = tmp_path / "allowed"
    repository_root = tmp_path / "repo"
    outside_path = tmp_path / "outside" / "session-1"
    allowed_root.mkdir()
    repository_root.mkdir()

    result = WorktreeGuardService().validate_path(
        worktree_path=str(outside_path),
        allowed_root=str(allowed_root),
        repository_root_path=str(repository_root),
    )

    assert not result.safe
    assert "worktree path is outside allowed workspace root" in result.blockers


def test_worktree_guard_blocks_path_inside_source_repository(tmp_path):
    """Planned worktree must not be nested inside the source repository."""

    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    planned_path = repository_root / ".aido-worktrees" / "session-1"

    result = WorktreeGuardService().validate_path(
        worktree_path=str(planned_path),
        allowed_root=str(tmp_path),
        repository_root_path=str(repository_root),
    )

    assert not result.safe
    assert "worktree path cannot be inside the source repository" in result.blockers


def test_worktree_plan_blocks_missing_repository_workspace_binding(db_session):
    """No project repository binding means the dry-run plan is blocked."""

    session = _create_agent_session(db_session, project_id=uuid4())

    plan = WorktreePlanService(
        agent_session_repository=AgentSessionRepository(db_session),
        repository_workspace_repository=RepositoryWorkspaceRepository(db_session),
    ).build_plan(agent_session_id=session.id)

    assert not plan.safe
    assert plan.worktree_path is None
    assert plan.branch_name is None
    assert "repository workspace is not bound for this project" in plan.blockers
    assert plan.git_commands_to_run == []


def test_worktree_plan_generates_safe_dry_run_for_bound_repository(db_session, tmp_path):
    """Bound repository produces a descriptive dry-run plan and preview commands."""

    allowed_root = tmp_path / "workspaces"
    allowed_root.mkdir()
    repository_root = allowed_root / "repo"
    repository_root.mkdir()
    (repository_root / ".git").mkdir()

    project_id = uuid4()
    session = _create_agent_session(db_session, project_id=project_id)
    workspace = RepositoryWorkspaceRepository(db_session).upsert(
        RepositoryWorkspace(
            project_id=project_id,
            root_path=str(repository_root),
            display_name="Repo",
            default_base_branch="main",
            allowed_workspace_root=str(allowed_root),
        )
    )

    plan = WorktreePlanService(
        agent_session_repository=AgentSessionRepository(db_session),
        repository_workspace_repository=RepositoryWorkspaceRepository(db_session),
    ).build_plan(agent_session_id=session.id)

    assert plan.safe
    assert plan.repository_workspace_id == workspace.id
    assert plan.workspace_type == "worktree"
    assert plan.worktree_path is not None
    assert plan.worktree_path.startswith(str(allowed_root))
    assert plan.branch_name is not None
    assert plan.branch_name.startswith(f"session/proj-{project_id.hex[:8]}-")
    assert plan.base_branch == "main"
    assert plan.base_commit_sha is None
    assert plan.blockers == []
    assert len(plan.git_commands_to_run) == 2
    assert plan.git_commands_to_run[0].startswith("git worktree add ")
    assert plan.git_commands_to_run[1].startswith("git -C ")


def test_worktree_plan_response_exposes_dry_run_fields(db_session, tmp_path):
    """API DTO exposes WorktreePlan fields without executing the preview commands."""

    allowed_root = tmp_path / "workspaces"
    allowed_root.mkdir()
    repository_root = allowed_root / "repo"
    repository_root.mkdir()
    (repository_root / ".git").mkdir()

    project_id = uuid4()
    session = _create_agent_session(db_session, project_id=project_id)
    RepositoryWorkspaceRepository(db_session).upsert(
        RepositoryWorkspace(
            project_id=project_id,
            root_path=str(repository_root),
            display_name="Repo",
            allowed_workspace_root=str(allowed_root),
        )
    )
    plan = WorktreePlanService(
        agent_session_repository=AgentSessionRepository(db_session),
        repository_workspace_repository=RepositoryWorkspaceRepository(db_session),
    ).build_plan(agent_session_id=session.id)

    payload = WorktreePlanResponse.from_plan(plan).model_dump(mode="json")

    assert payload["agent_session_id"] == str(session.id)
    assert payload["project_id"] == str(project_id)
    assert payload["safe"] is True
    assert payload["workspace_type"] == "worktree"
    assert payload["worktree_path"] == plan.worktree_path
    assert payload["branch_name"] == plan.branch_name
    assert payload["base_branch"] == "main"
    assert payload["base_commit_sha"] is None
    assert payload["blockers"] == []
    assert payload["warnings"] == []
