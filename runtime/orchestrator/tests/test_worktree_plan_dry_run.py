"""Worktree plan/prepare/create coverage.

Plan, confirmation, and prepare coverage remains non-mutating. P1-D-E-B create
coverage uses only tmp_path git fixtures for real worktree/branch execution.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes.agent_threads import (
    WorktreeCleanupRequestBody,
    WorktreeCleanupResponse,
    WorktreeCreateRequestBody,
    WorktreeCreateResponse,
    WorktreePlanConfirmationReceiptResponse,
    WorktreePlanResponse,
    WorktreePrepareRequestBody,
    WorktreePrepareResponse,
    cleanup_agent_session_workspace,
    create_agent_session_workspace,
    prepare_agent_session_workspace,
)
from app.core.db_tables import ORMBase
from app.domain.agent_session import (
    AgentSessionPhase,
    AgentSessionReviewStatus,
    AgentSessionStatus,
)
from app.domain.repository_workspace import RepositoryWorkspace
from app.domain.worktree_prepare import WorktreeGitPreflight
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.repository_workspace_repository import RepositoryWorkspaceRepository
from app.services.worktree_command_runner import (
    WorktreeCommandResult,
    WorktreeCommandRunner,
    WorktreeCommandSpec,
)
from app.services.worktree_cleanup_service import (
    WorktreeCleanupHashMismatchError,
    WorktreeCleanupRequest,
    WorktreeCleanupService,
)
from app.services.worktree_create_service import (
    WorktreeCreateHashMismatchError,
    WorktreeCreateRequest,
    WorktreeCreateService,
)
from app.services.worktree_git_preflight_service import WorktreeGitPreflightService
from app.services.worktree_prepare_service import (
    WorktreePrepareHashMismatchError,
    WorktreePrepareRequest,
    WorktreePrepareService,
)
from app.services.worktree_plan_confirmation_service import (
    WorktreePlanConfirmationError,
    WorktreePlanConfirmationRequest,
    WorktreePlanConfirmationService,
    WorktreePlanHashMismatchError,
)
from app.services.worktree_plan_service import (
    BranchNamePolicy,
    WorktreeGuardService,
    WorktreePlanService,
)
from app.services.worktree_write_command_runner import WorktreeWriteCommandRunner


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


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run git only inside tmp_path repository fixtures."""

    return subprocess.run(
        ("git", *args),
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def _create_tmp_git_repository(parent_path: Path) -> Path:
    """Create a committed git repository fixture under tmp_path."""

    repository_root = parent_path / "repo"
    repository_root.mkdir()
    _run_git(repository_root, "init")
    _run_git(repository_root, "config", "user.email", "test@example.invalid")
    _run_git(repository_root, "config", "user.name", "AIDO Test")
    (repository_root / "README.md").write_text("fixture\n")
    _run_git(repository_root, "add", "README.md")
    _run_git(repository_root, "commit", "-m", "initial fixture commit")
    return repository_root


def _create_bound_git_session(db_session, tmp_path):
    """Persist one session bound to a real tmp_path git repository."""

    allowed_root = tmp_path / "workspaces"
    allowed_root.mkdir()
    repository_root = _create_tmp_git_repository(allowed_root)
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
    plan_service = WorktreePlanService(
        agent_session_repository=AgentSessionRepository(db_session),
        repository_workspace_repository=RepositoryWorkspaceRepository(db_session),
    )
    plan = plan_service.build_plan(agent_session_id=session.id)
    return project_id, session, repository_root, plan_service, plan


class FakeWorktreeGitPreflightService:
    """Test double that simulates read-only git preflight without executing git."""

    def __init__(
        self,
        *,
        preflight: WorktreeGitPreflight | None = None,
    ) -> None:
        self.preflight = preflight or WorktreeGitPreflight(
            preflight_status="passed",
            commands_run=[
                "git rev-parse --is-inside-work-tree",
                "git rev-parse HEAD",
                "git status --porcelain",
                "git worktree list --porcelain",
                "git branch --list session/*",
            ],
            repository_is_git_worktree=True,
            repository_head_sha="a" * 40,
            repository_clean=True,
            planned_branch_exists=False,
            planned_worktree_registered=False,
            registered_worktree_paths=["/tmp/repo"],
        )
        self.calls: list[dict[str, str]] = []

    def run_preflight(
        self,
        *,
        repository_path: str,
        planned_branch_name: str,
        planned_worktree_path: str,
    ) -> WorktreeGitPreflight:
        """Record the preflight call and return a fixed read-only result."""

        self.calls.append(
            {
                "repository_path": repository_path,
                "planned_branch_name": planned_branch_name,
                "planned_worktree_path": planned_worktree_path,
            }
        )
        return self.preflight


class FakeReadOnlyCommandRunner:
    """Test double for WorktreeGitPreflightService that never executes git."""

    default_timeout_seconds = 30

    def __init__(self) -> None:
        self.run_specs: list[WorktreeCommandSpec] = []

    def git_rev_parse_is_inside_work_tree(
        self,
        *,
        repository_path: str,
    ) -> WorktreeCommandSpec:
        return WorktreeCommandSpec(
            argv=("git", "rev-parse", "--is-inside-work-tree"),
            cwd=repository_path,
            timeout_seconds=self.default_timeout_seconds,
            mutates_repository=False,
        )

    def git_rev_parse(self, *, repository_path: str, ref: str) -> WorktreeCommandSpec:
        return WorktreeCommandSpec(
            argv=("git", "rev-parse", ref),
            cwd=repository_path,
            timeout_seconds=self.default_timeout_seconds,
            mutates_repository=False,
        )

    def git_status_porcelain(self, *, repository_path: str) -> WorktreeCommandSpec:
        return WorktreeCommandSpec(
            argv=("git", "status", "--porcelain"),
            cwd=repository_path,
            timeout_seconds=self.default_timeout_seconds,
            mutates_repository=False,
        )

    def git_worktree_list(self, *, repository_path: str) -> WorktreeCommandSpec:
        return WorktreeCommandSpec(
            argv=("git", "worktree", "list", "--porcelain"),
            cwd=repository_path,
            timeout_seconds=self.default_timeout_seconds,
            mutates_repository=False,
        )

    def git_branch_list(self, *, repository_path: str, pattern: str) -> WorktreeCommandSpec:
        return WorktreeCommandSpec(
            argv=("git", "branch", "--list", pattern),
            cwd=repository_path,
            timeout_seconds=self.default_timeout_seconds,
            mutates_repository=False,
        )

    def run(self, spec: WorktreeCommandSpec) -> WorktreeCommandResult:
        self.run_specs.append(spec)
        stdout_by_argv = {
            ("git", "rev-parse", "--is-inside-work-tree"): "true\n",
            ("git", "rev-parse", "HEAD"): "b" * 40 + "\n",
            ("git", "status", "--porcelain"): "",
            (
                "git",
                "worktree",
                "list",
                "--porcelain",
            ): "worktree /tmp/repo\nHEAD " + "b" * 40 + "\nbranch refs/heads/main\n",
            ("git", "branch", "--list", "session/proj-test-12345678"): "",
        }
        return WorktreeCommandResult(
            spec=spec,
            return_code=0,
            stdout=stdout_by_argv.get(spec.argv, ""),
            stderr="",
        )


class FailingWriteCommandRunner(WorktreeWriteCommandRunner):
    """Test double that records the allowlisted write command but returns failure."""

    def __init__(self) -> None:
        super().__init__()
        self.calls = []

    def run(self, preview):
        self.calls.append(preview)
        return WorktreeCommandResult(
            spec=preview,
            return_code=1,
            stdout="",
            stderr="simulated worktree add failure",
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
    assert plan.dry_run is True
    assert plan.requires_user_confirmation is True
    assert len(plan.plan_hash) == 64
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


def test_worktree_plan_hash_is_stable_for_same_inputs(db_session, tmp_path):
    """Same dry-run inputs produce the same stale-plan hash."""

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
            default_base_branch="main",
            allowed_workspace_root=str(allowed_root),
        )
    )
    service = WorktreePlanService(
        agent_session_repository=AgentSessionRepository(db_session),
        repository_workspace_repository=RepositoryWorkspaceRepository(db_session),
    )

    first_plan = service.build_plan(agent_session_id=session.id)
    second_plan = service.build_plan(agent_session_id=session.id)

    assert first_plan.plan_hash == second_plan.plan_hash


def test_worktree_plan_hash_changes_when_plan_fields_change(db_session, tmp_path):
    """Changing canonical plan fields changes the hash."""

    allowed_root = tmp_path / "workspaces"
    allowed_root.mkdir()
    repository_root = allowed_root / "repo"
    repository_root.mkdir()
    (repository_root / ".git").mkdir()

    project_id = uuid4()
    session = _create_agent_session(db_session, project_id=project_id)
    workspace_repository = RepositoryWorkspaceRepository(db_session)
    workspace_repository.upsert(
        RepositoryWorkspace(
            project_id=project_id,
            root_path=str(repository_root),
            display_name="Repo",
            default_base_branch="main",
            allowed_workspace_root=str(allowed_root),
        )
    )
    service = WorktreePlanService(
        agent_session_repository=AgentSessionRepository(db_session),
        repository_workspace_repository=workspace_repository,
    )

    first_plan = service.build_plan(agent_session_id=session.id)
    workspace_repository.upsert(
        RepositoryWorkspace(
            project_id=project_id,
            root_path=str(repository_root),
            display_name="Repo",
            default_base_branch="develop",
            allowed_workspace_root=str(allowed_root),
        )
    )
    second_plan = service.build_plan(agent_session_id=session.id)

    assert first_plan.plan_hash != second_plan.plan_hash


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
    assert payload["dry_run"] is True
    assert payload["requires_user_confirmation"] is True
    assert payload["plan_hash"] == plan.plan_hash
    assert payload["workspace_type"] == "worktree"
    assert payload["worktree_path"] == plan.worktree_path
    assert payload["branch_name"] == plan.branch_name
    assert payload["base_branch"] == "main"
    assert payload["base_commit_sha"] is None
    assert payload["blockers"] == []
    assert payload["warnings"] == []


def test_worktree_plan_confirmation_receipt_accepts_current_hash_only(
    db_session, tmp_path
):
    """Confirmation returns a receipt for the current safe dry-run plan hash."""

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
    plan_service = WorktreePlanService(
        agent_session_repository=AgentSessionRepository(db_session),
        repository_workspace_repository=RepositoryWorkspaceRepository(db_session),
    )
    plan = plan_service.build_plan(agent_session_id=session.id)

    receipt = WorktreePlanConfirmationService(
        worktree_plan_service=plan_service,
    ).confirm_plan(
        WorktreePlanConfirmationRequest(
            agent_session_id=session.id,
            plan_hash=plan.plan_hash,
            user_confirmed=True,
            confirmed_by=" reviewer ",
        )
    )

    assert receipt.agent_session_id == session.id
    assert receipt.project_id == project_id
    assert receipt.plan_hash == plan.plan_hash
    assert receipt.confirmed_plan_hash == plan.plan_hash
    assert receipt.confirmation_status == "confirmed"
    assert receipt.confirmation_scope == "workspace_plan_dry_run"
    assert receipt.dry_run is True
    assert receipt.requires_user_confirmation is True
    assert receipt.worktree_path == plan.worktree_path
    assert receipt.branch_name == plan.branch_name
    assert receipt.confirmed_by == "reviewer"
    assert receipt.next_action == "await_explicit_workspace_creation_request"
    assert receipt.creates_worktree is False
    assert receipt.creates_branch is False
    assert receipt.mutates_agent_session_workspace is False

    unchanged_session = AgentSessionRepository(db_session).get_by_id(session.id)
    assert unchanged_session is not None
    assert unchanged_session.workspace_path is None
    assert unchanged_session.branch_name is None


def test_worktree_plan_confirmation_rejects_stale_plan_hash(db_session, tmp_path):
    """Submitted plan_hash must match the current recomputed dry-run plan."""

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
    plan_service = WorktreePlanService(
        agent_session_repository=AgentSessionRepository(db_session),
        repository_workspace_repository=RepositoryWorkspaceRepository(db_session),
    )

    with pytest.raises(WorktreePlanHashMismatchError):
        WorktreePlanConfirmationService(worktree_plan_service=plan_service).confirm_plan(
            WorktreePlanConfirmationRequest(
                agent_session_id=session.id,
                plan_hash="0" * 64,
                user_confirmed=True,
            )
        )


def test_worktree_plan_confirmation_rejects_blocked_plan(db_session):
    """Blocked dry-run plans cannot produce a confirmation receipt."""

    session = _create_agent_session(db_session, project_id=uuid4())
    plan_service = WorktreePlanService(
        agent_session_repository=AgentSessionRepository(db_session),
        repository_workspace_repository=RepositoryWorkspaceRepository(db_session),
    )
    blocked_plan = plan_service.build_plan(agent_session_id=session.id)

    with pytest.raises(WorktreePlanConfirmationError):
        WorktreePlanConfirmationService(worktree_plan_service=plan_service).confirm_plan(
            WorktreePlanConfirmationRequest(
                agent_session_id=session.id,
                plan_hash=blocked_plan.plan_hash,
                user_confirmed=True,
            )
        )


def test_worktree_plan_confirmation_receipt_response_exposes_guard_fields(
    db_session, tmp_path
):
    """Receipt DTO exposes confirmation guard fields without execution semantics."""

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
    plan_service = WorktreePlanService(
        agent_session_repository=AgentSessionRepository(db_session),
        repository_workspace_repository=RepositoryWorkspaceRepository(db_session),
    )
    plan = plan_service.build_plan(agent_session_id=session.id)
    receipt = WorktreePlanConfirmationService(
        worktree_plan_service=plan_service,
    ).confirm_plan(
        WorktreePlanConfirmationRequest(
            agent_session_id=session.id,
            plan_hash=plan.plan_hash,
            user_confirmed=True,
        )
    )

    payload = WorktreePlanConfirmationReceiptResponse.from_receipt(receipt).model_dump(
        mode="json"
    )

    assert payload["agent_session_id"] == str(session.id)
    assert payload["project_id"] == str(project_id)
    assert payload["plan_hash"] == plan.plan_hash
    assert payload["confirmed_plan_hash"] == plan.plan_hash
    assert payload["confirmation_status"] == "confirmed"
    assert payload["confirmation_scope"] == "workspace_plan_dry_run"
    assert payload["dry_run"] is True
    assert payload["requires_user_confirmation"] is True
    assert payload["creates_worktree"] is False
    assert payload["creates_branch"] is False
    assert payload["mutates_agent_session_workspace"] is False


def test_worktree_prepare_skeleton_returns_blocked_for_current_hash(
    db_session, tmp_path
):
    """Prepare skeleton validates the hash but remains blocked/not_implemented."""

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
    plan_service = WorktreePlanService(
        agent_session_repository=AgentSessionRepository(db_session),
        repository_workspace_repository=RepositoryWorkspaceRepository(db_session),
    )
    plan = plan_service.build_plan(agent_session_id=session.id)
    fake_preflight = FakeWorktreeGitPreflightService()

    result = WorktreePrepareService(
        worktree_plan_service=plan_service,
        git_preflight_service=fake_preflight,
    ).prepare_workspace(
        WorktreePrepareRequest(
            agent_session_id=session.id,
            plan_hash=plan.plan_hash,
            user_confirmed=True,
        )
    )

    assert result.agent_session_id == session.id
    assert result.project_id == project_id
    assert result.plan_hash == plan.plan_hash
    assert result.submitted_plan_hash == plan.plan_hash
    assert result.prepare_status == "blocked"
    assert result.blocked_reason == "workspace_prepare_not_implemented"
    assert result.dry_run is True
    assert result.requires_user_confirmation is True
    assert result.worktree_path == plan.worktree_path
    assert result.branch_name == plan.branch_name
    assert result.creates_worktree is False
    assert result.creates_branch is False
    assert result.runs_git is True
    assert result.runs_write_git is False
    assert result.mutates_agent_session_workspace is False
    assert result.git_preflight is not None
    assert result.git_preflight.read_only is True
    assert result.git_preflight.preflight_status == "passed"
    assert result.git_preflight.repository_is_git_worktree is True
    assert result.git_preflight.repository_clean is True
    assert result.git_preflight.planned_branch_exists is False
    assert result.git_preflight.planned_worktree_registered is False
    assert "workspace prepare execution is not implemented in P1-D-D" in result.blockers
    assert fake_preflight.calls == [
        {
            "repository_path": str(repository_root),
            "planned_branch_name": plan.branch_name,
            "planned_worktree_path": plan.worktree_path,
        }
    ]

    unchanged_session = AgentSessionRepository(db_session).get_by_id(session.id)
    assert unchanged_session is not None
    assert unchanged_session.workspace_path is None
    assert unchanged_session.branch_name is None


@pytest.mark.parametrize(
    ("preflight_overrides", "expected_blocker"),
    [
        (
            {"repository_is_git_worktree": False},
            "repository root is not a git worktree",
        ),
        (
            {"repository_clean": False},
            "repository has uncommitted changes",
        ),
        (
            {"planned_branch_exists": True},
            "planned branch already exists",
        ),
        (
            {"planned_worktree_registered": True},
            "planned worktree path is already registered",
        ),
    ],
)
def test_worktree_prepare_blocks_unsafe_preflight_states(
    db_session, tmp_path, preflight_overrides, expected_blocker
):
    """Unsafe read-only preflight states explicitly block workspace prepare."""

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
    plan_service = WorktreePlanService(
        agent_session_repository=AgentSessionRepository(db_session),
        repository_workspace_repository=RepositoryWorkspaceRepository(db_session),
    )
    plan = plan_service.build_plan(agent_session_id=session.id)
    preflight_payload = {
        "preflight_status": "passed",
        "commands_run": [
            "git rev-parse --is-inside-work-tree",
            "git rev-parse HEAD",
            "git status --porcelain",
            "git worktree list --porcelain",
            "git branch --list session/*",
        ],
        "repository_is_git_worktree": True,
        "repository_clean": True,
        "planned_branch_exists": False,
        "planned_worktree_registered": False,
    }
    preflight_payload.update(preflight_overrides)
    preflight = WorktreeGitPreflight(**preflight_payload)

    result = WorktreePrepareService(
        worktree_plan_service=plan_service,
        git_preflight_service=FakeWorktreeGitPreflightService(preflight=preflight),
    ).prepare_workspace(
        WorktreePrepareRequest(
            agent_session_id=session.id,
            plan_hash=plan.plan_hash,
            user_confirmed=True,
        )
    )

    assert result.prepare_status == "blocked"
    assert expected_blocker in result.blockers
    assert result.creates_worktree is False
    assert result.creates_branch is False
    assert result.runs_write_git is False
    assert result.mutates_agent_session_workspace is False

    unchanged_session = AgentSessionRepository(db_session).get_by_id(session.id)
    assert unchanged_session is not None
    assert unchanged_session.workspace_path is None
    assert unchanged_session.branch_name is None


def test_worktree_prepare_skeleton_rejects_stale_plan_hash(db_session, tmp_path):
    """Prepare skeleton uses the same current-plan hash stale check."""

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
    plan_service = WorktreePlanService(
        agent_session_repository=AgentSessionRepository(db_session),
        repository_workspace_repository=RepositoryWorkspaceRepository(db_session),
    )

    with pytest.raises(WorktreePrepareHashMismatchError):
        WorktreePrepareService(worktree_plan_service=plan_service).prepare_workspace(
            WorktreePrepareRequest(
                agent_session_id=session.id,
                plan_hash="0" * 64,
                user_confirmed=True,
            )
        )


def test_worktree_prepare_skeleton_keeps_blocked_plan_blocked(db_session):
    """Blocked plans return an explicit skeleton blocker plus plan blockers."""

    session = _create_agent_session(db_session, project_id=uuid4())
    plan_service = WorktreePlanService(
        agent_session_repository=AgentSessionRepository(db_session),
        repository_workspace_repository=RepositoryWorkspaceRepository(db_session),
    )
    blocked_plan = plan_service.build_plan(agent_session_id=session.id)

    result = WorktreePrepareService(worktree_plan_service=plan_service).prepare_workspace(
        WorktreePrepareRequest(
            agent_session_id=session.id,
            plan_hash=blocked_plan.plan_hash,
            user_confirmed=True,
        )
    )

    assert result.prepare_status == "blocked"
    assert "workspace prepare execution is not implemented in P1-D-D" in result.blockers
    assert "repository workspace is not bound for this project" in result.blockers
    assert result.creates_worktree is False
    assert result.creates_branch is False
    assert result.runs_git is False
    assert result.runs_write_git is False
    assert result.mutates_agent_session_workspace is False


def test_worktree_prepare_response_exposes_blocked_guard_fields(db_session, tmp_path):
    """Prepare response makes not-implemented and no-mutation fields observable."""

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
    plan_service = WorktreePlanService(
        agent_session_repository=AgentSessionRepository(db_session),
        repository_workspace_repository=RepositoryWorkspaceRepository(db_session),
    )
    plan = plan_service.build_plan(agent_session_id=session.id)
    result = WorktreePrepareService(
        worktree_plan_service=plan_service,
        git_preflight_service=FakeWorktreeGitPreflightService(),
    ).prepare_workspace(
        WorktreePrepareRequest(
            agent_session_id=session.id,
            plan_hash=plan.plan_hash,
            user_confirmed=True,
        )
    )

    payload = WorktreePrepareResponse.from_result(result).model_dump(mode="json")

    assert payload["agent_session_id"] == str(session.id)
    assert payload["project_id"] == str(project_id)
    assert payload["plan_hash"] == plan.plan_hash
    assert payload["submitted_plan_hash"] == plan.plan_hash
    assert payload["prepare_status"] == "blocked"
    assert payload["blocked_reason"] == "workspace_prepare_not_implemented"
    assert payload["dry_run"] is True
    assert payload["requires_user_confirmation"] is True
    assert payload["creates_worktree"] is False
    assert payload["creates_branch"] is False
    assert payload["runs_git"] is True
    assert payload["runs_write_git"] is False
    assert payload["mutates_agent_session_workspace"] is False
    assert payload["git_preflight"]["read_only"] is True
    assert payload["git_preflight"]["preflight_status"] == "passed"
    assert payload["git_preflight"]["repository_is_git_worktree"] is True
    assert payload["git_preflight"]["commands_run"] == [
        "git rev-parse --is-inside-work-tree",
        "git rev-parse HEAD",
        "git status --porcelain",
        "git worktree list --porcelain",
        "git branch --list session/*",
    ]


def test_worktree_prepare_endpoint_returns_blocked_skeleton(db_session, tmp_path):
    """Route function returns the blocked prepare DTO without mutating the session."""

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
    plan_service = WorktreePlanService(
        agent_session_repository=AgentSessionRepository(db_session),
        repository_workspace_repository=RepositoryWorkspaceRepository(db_session),
    )
    plan = plan_service.build_plan(agent_session_id=session.id)
    prepare_service = WorktreePrepareService(
        worktree_plan_service=plan_service,
        git_preflight_service=FakeWorktreeGitPreflightService(),
    )

    response = prepare_agent_session_workspace(
        session_id=session.id,
        request=WorktreePrepareRequestBody(
            plan_hash=plan.plan_hash,
            user_confirmed=True,
        ),
        prepare_service=prepare_service,
    )

    assert response.prepare_status == "blocked"
    assert response.blocked_reason == "workspace_prepare_not_implemented"
    assert response.plan_hash == plan.plan_hash
    assert response.creates_worktree is False
    assert response.creates_branch is False
    assert response.runs_git is True
    assert response.runs_write_git is False
    assert response.git_preflight is not None
    assert response.git_preflight.read_only is True
    assert response.git_preflight.repository_is_git_worktree is True
    assert response.mutates_agent_session_workspace is False

    unchanged_session = AgentSessionRepository(db_session).get_by_id(session.id)
    assert unchanged_session is not None
    assert unchanged_session.workspace_path is None
    assert unchanged_session.branch_name is None


def test_worktree_write_command_runner_builds_executable_allowlisted_command(tmp_path):
    """Write runner builds the single executable worktree add command shape."""

    runner = WorktreeWriteCommandRunner(default_timeout_seconds=30)
    repository_path = str(tmp_path / "repo")
    worktree_path = str(tmp_path / "workspaces" / "session-1")

    preview = runner.git_worktree_add_new_branch(
        repository_path=repository_path,
        worktree_path=worktree_path,
        branch_name="session/proj-test-12345678",
        base_ref="HEAD",
    )

    assert preview.argv == (
        "git",
        "worktree",
        "add",
        "-b",
        "session/proj-test-12345678",
        worktree_path,
        "HEAD",
    )
    assert preview.cwd == repository_path
    assert preview.timeout_seconds == 30
    assert preview.mutates_repository is True
    assert preview.command_kind == "git_worktree_add_new_branch"
    assert preview.execution_enabled is True
    assert hasattr(runner, "run")


def test_worktree_create_executes_real_worktree_and_writes_agent_session(
    db_session, tmp_path
):
    """Create validates hash/preflight, runs one git worktree add, and persists workspace fields."""

    project_id, session, repository_root, plan_service, plan = _create_bound_git_session(
        db_session, tmp_path
    )
    AgentSessionRepository(db_session).update_status(
        session.id,
        last_workspace_error="stale workspace failure",
    )

    result = WorktreeCreateService(worktree_plan_service=plan_service).create_workspace(
        WorktreeCreateRequest(
            agent_session_id=session.id,
            plan_hash=plan.plan_hash,
            user_confirmed=True,
        )
    )

    assert result.agent_session_id == session.id
    assert result.project_id == project_id
    assert result.plan_hash == plan.plan_hash
    assert result.submitted_plan_hash == plan.plan_hash
    assert result.create_status == "created"
    assert result.blocked_reason is None
    assert result.dry_run is False
    assert result.requires_user_confirmation is True
    assert result.worktree_path == plan.worktree_path
    assert result.branch_name == plan.branch_name
    assert result.base_commit_sha == _run_git(repository_root, "rev-parse", "HEAD").stdout.strip()
    assert result.creates_worktree is True
    assert result.creates_branch is True
    assert result.runs_git is True
    assert result.runs_write_git is True
    assert result.mutates_agent_session_workspace is True
    assert result.git_preflight is not None
    assert result.git_preflight.read_only is True
    assert result.git_preflight.repository_clean is True
    assert result.git_preflight.planned_branch_exists is False
    assert result.git_preflight.planned_worktree_registered is False
    assert result.blockers == []
    assert len(result.write_command_preview) == 1
    assert result.write_command_preview[0].argv == (
        "git",
        "worktree",
        "add",
        "-b",
        plan.branch_name,
        plan.worktree_path,
        result.base_commit_sha,
    )
    assert result.write_command_preview[0].execution_enabled is True
    assert Path(plan.worktree_path).is_dir()
    assert (Path(plan.worktree_path) / "README.md").read_text() == "fixture\n"
    assert _run_git(repository_root, "branch", "--list", plan.branch_name).stdout.strip()

    updated_session = AgentSessionRepository(db_session).get_by_id(session.id)
    assert updated_session is not None
    assert updated_session.workspace_type == "worktree"
    assert updated_session.workspace_path == plan.worktree_path
    assert updated_session.branch_name == plan.branch_name
    assert updated_session.workspace_clean is True
    assert updated_session.last_workspace_error is None


def test_worktree_create_rejects_stale_plan_hash(db_session, tmp_path):
    """Create uses current-plan hash stale check before any write git command."""

    _, session, _, plan_service, _ = _create_bound_git_session(db_session, tmp_path)

    with pytest.raises(WorktreeCreateHashMismatchError):
        WorktreeCreateService(worktree_plan_service=plan_service).create_workspace(
            WorktreeCreateRequest(
                agent_session_id=session.id,
                plan_hash="0" * 64,
                user_confirmed=True,
            )
        )


def test_worktree_create_blocks_unsafe_preflight_and_writes_last_error(
    db_session, tmp_path
):
    """Unsafe read-only preflight blocks writes and records last_workspace_error."""

    _, session, _, plan_service, plan = _create_bound_git_session(db_session, tmp_path)
    preflight = WorktreeGitPreflight(
        preflight_status="passed",
        commands_run=["git status --porcelain"],
        repository_is_git_worktree=True,
        repository_head_sha="c" * 40,
        repository_clean=False,
        planned_branch_exists=False,
        planned_worktree_registered=False,
    )

    result = WorktreeCreateService(
        worktree_plan_service=plan_service,
        git_preflight_service=FakeWorktreeGitPreflightService(preflight=preflight),
    ).create_workspace(
        WorktreeCreateRequest(
            agent_session_id=session.id,
            plan_hash=plan.plan_hash,
            user_confirmed=True,
        )
    )

    assert result.create_status == "blocked"
    assert result.blocked_reason == "workspace_create_preflight_blocked"
    assert "repository has uncommitted changes" in result.blockers
    assert result.creates_worktree is False
    assert result.creates_branch is False
    assert result.runs_git is True
    assert result.runs_write_git is False
    assert result.mutates_agent_session_workspace is True
    assert not Path(plan.worktree_path).exists()

    updated_session = AgentSessionRepository(db_session).get_by_id(session.id)
    assert updated_session is not None
    assert updated_session.workspace_path is None
    assert updated_session.branch_name is None
    assert updated_session.workspace_clean is None
    assert updated_session.last_workspace_error is not None
    assert updated_session.last_workspace_error.startswith("preflight blocked:")
    assert "repository has uncommitted changes" in updated_session.last_workspace_error


def test_worktree_create_write_failure_records_last_workspace_error(
    db_session, tmp_path
):
    """Plan/preflight blockers persist last_workspace_error without running write git."""

    _, session, _, plan_service, plan = _create_bound_git_session(db_session, tmp_path)
    Path(plan.worktree_path).mkdir(parents=True)
    (Path(plan.worktree_path) / "occupied.txt").write_text("busy\n")

    result = WorktreeCreateService(worktree_plan_service=plan_service).create_workspace(
        WorktreeCreateRequest(
            agent_session_id=session.id,
            plan_hash=plan.plan_hash,
            user_confirmed=True,
        )
    )

    assert result.create_status == "blocked"
    assert result.blocked_reason == "workspace_create_preflight_blocked"
    assert "worktree path already exists and is not empty" in result.blockers
    assert result.runs_write_git is False
    assert result.mutates_agent_session_workspace is True

    updated_session = AgentSessionRepository(db_session).get_by_id(session.id)
    assert updated_session is not None
    assert updated_session.workspace_path is None
    assert updated_session.branch_name is None
    assert updated_session.last_workspace_error is not None
    assert "worktree path already exists and is not empty" in updated_session.last_workspace_error


def test_worktree_create_write_command_failure_records_last_workspace_error(
    db_session, tmp_path
):
    """If git worktree add fails, success fields stay unchanged and last error is persisted."""

    _, session, _, plan_service, plan = _create_bound_git_session(db_session, tmp_path)
    failing_runner = FailingWriteCommandRunner()

    result = WorktreeCreateService(
        worktree_plan_service=plan_service,
        write_command_runner=failing_runner,
    ).create_workspace(
        WorktreeCreateRequest(
            agent_session_id=session.id,
            plan_hash=plan.plan_hash,
            user_confirmed=True,
        )
    )

    assert result.create_status == "failed"
    assert result.blocked_reason == "workspace_create_git_write_failed"
    assert result.runs_write_git is True
    assert result.runs_git is True
    assert result.mutates_agent_session_workspace is True
    assert "git worktree add failed: simulated worktree add failure" in result.blockers
    assert len(failing_runner.calls) == 1
    assert failing_runner.calls[0].argv[:4] == ("git", "worktree", "add", "-b")
    assert not Path(plan.worktree_path).exists()

    updated_session = AgentSessionRepository(db_session).get_by_id(session.id)
    assert updated_session is not None
    assert updated_session.workspace_path is None
    assert updated_session.branch_name is None
    assert updated_session.workspace_clean is None
    assert updated_session.last_workspace_error is not None
    assert updated_session.last_workspace_error.startswith("git worktree add failed:")


def test_worktree_create_response_exposes_created_guard_fields(db_session, tmp_path):
    """Create response exposes preflight, write command, and mutation fields."""

    _, session, _, plan_service, plan = _create_bound_git_session(db_session, tmp_path)
    result = WorktreeCreateService(worktree_plan_service=plan_service).create_workspace(
        WorktreeCreateRequest(
            agent_session_id=session.id,
            plan_hash=plan.plan_hash,
            user_confirmed=True,
        )
    )

    payload = WorktreeCreateResponse.from_result(result).model_dump(mode="json")

    assert payload["agent_session_id"] == str(session.id)
    assert payload["plan_hash"] == plan.plan_hash
    assert payload["submitted_plan_hash"] == plan.plan_hash
    assert payload["create_status"] == "created"
    assert payload["blocked_reason"] is None
    assert payload["creates_worktree"] is True
    assert payload["creates_branch"] is True
    assert payload["runs_git"] is True
    assert payload["runs_write_git"] is True
    assert payload["mutates_agent_session_workspace"] is True
    assert payload["git_preflight"]["read_only"] is True
    assert payload["write_command_preview"][0]["mutates_repository"] is True
    assert payload["write_command_preview"][0]["execution_enabled"] is True


def test_worktree_create_endpoint_creates_workspace(db_session, tmp_path):
    """Route function creates the worktree and mutates the session workspace fields."""

    _, session, _, plan_service, plan = _create_bound_git_session(db_session, tmp_path)
    create_service = WorktreeCreateService(worktree_plan_service=plan_service)

    response = create_agent_session_workspace(
        session_id=session.id,
        request=WorktreeCreateRequestBody(
            plan_hash=plan.plan_hash,
            user_confirmed=True,
        ),
        create_service=create_service,
    )

    assert response.create_status == "created"
    assert response.blocked_reason is None
    assert response.plan_hash == plan.plan_hash
    assert response.creates_worktree is True
    assert response.creates_branch is True
    assert response.runs_git is True
    assert response.runs_write_git is True
    assert response.mutates_agent_session_workspace is True
    assert response.git_preflight is not None
    assert response.git_preflight.read_only is True
    assert response.write_command_preview[0].execution_enabled is True

    updated_session = AgentSessionRepository(db_session).get_by_id(session.id)
    assert updated_session is not None
    assert updated_session.workspace_path == plan.worktree_path
    assert updated_session.branch_name == plan.branch_name

def test_worktree_git_preflight_service_runs_only_read_only_commands():
    """Git preflight invokes only read-only allowlisted commands."""

    runner = FakeReadOnlyCommandRunner()
    preflight = WorktreeGitPreflightService(command_runner=runner).run_preflight(
        repository_path="/tmp/repo",
        planned_branch_name="session/proj-test-12345678",
        planned_worktree_path="/tmp/workspaces/session-1",
    )

    assert [spec.argv for spec in runner.run_specs] == [
        ("git", "rev-parse", "--is-inside-work-tree"),
        ("git", "rev-parse", "HEAD"),
        ("git", "status", "--porcelain"),
        ("git", "worktree", "list", "--porcelain"),
        ("git", "branch", "--list", "session/proj-test-12345678"),
    ]
    assert all(not spec.mutates_repository for spec in runner.run_specs)
    assert preflight.preflight_status == "passed"
    assert preflight.read_only is True
    assert preflight.repository_is_git_worktree is True
    assert preflight.repository_head_sha == "b" * 40
    assert preflight.repository_clean is True
    assert preflight.planned_branch_exists is False
    assert preflight.planned_worktree_registered is False
    assert preflight.registered_worktree_paths == ["/tmp/repo"]
    assert preflight.errors == []
    assert preflight.commands_run == [
        "git rev-parse --is-inside-work-tree",
        "git rev-parse HEAD",
        "git status --porcelain",
        "git worktree list --porcelain",
        "git branch --list session/proj-test-12345678",
    ]


def test_worktree_command_runner_exposes_deny_by_default_allowlist_specs(tmp_path):
    """Runner returns immutable specs only for read-only preflight commands."""

    runner = WorktreeCommandRunner(default_timeout_seconds=30)
    repository_path = str(tmp_path / "repo")

    inside_work_tree = runner.git_rev_parse_is_inside_work_tree(
        repository_path=repository_path,
    )
    rev_parse = runner.git_rev_parse(repository_path=repository_path, ref="HEAD")
    status = runner.git_status_porcelain(repository_path=repository_path)
    worktree_list = runner.git_worktree_list(repository_path=repository_path)
    branch_list = runner.git_branch_list(
        repository_path=repository_path,
        pattern="session/*",
    )

    assert inside_work_tree.argv == ("git", "rev-parse", "--is-inside-work-tree")
    assert rev_parse.argv == ("git", "rev-parse", "HEAD")
    assert status.argv == ("git", "status", "--porcelain")
    assert worktree_list.argv == ("git", "worktree", "list", "--porcelain")
    assert branch_list.argv == ("git", "branch", "--list", "session/*")
    assert all(
        not spec.mutates_repository
        for spec in [inside_work_tree, rev_parse, status, worktree_list, branch_list]
    )
    assert rev_parse.timeout_seconds == 30


def test_worktree_command_runner_does_not_expose_write_specs():
    """P1-D-A boundary exposes no mutating worktree or branch specs."""

    runner = WorktreeCommandRunner()

    assert not hasattr(runner, "git_fetch")
    assert not hasattr(runner, "git_worktree_add")
    assert not hasattr(runner, "git_checkout_new_branch")
    assert not hasattr(runner, "git_worktree_remove")
    assert not hasattr(runner, "git_branch_delete")


def test_worktree_command_runner_rejects_arbitrary_or_mutating_specs(tmp_path):
    """Runner execution rejects arbitrary or mutating command specs."""

    runner = WorktreeCommandRunner()
    repository_path = str(tmp_path / "repo")

    with pytest.raises(ValueError):
        runner.run(
            WorktreeCommandSpec(
                argv=("git", "checkout", "-b", "session/test"),
                cwd=repository_path,
                timeout_seconds=30,
                mutates_repository=True,
            )
        )

    with pytest.raises(ValueError):
        runner.run(
            WorktreeCommandSpec(
                argv=("git", "fetch", "origin"),
                cwd=repository_path,
                timeout_seconds=30,
                mutates_repository=False,
            )
        )


def test_worktree_cleanup_returns_blocked_preview_without_mutation(db_session, tmp_path):
    """P1-E-A cleanup is a blocked skeleton and never removes worktree/branch."""

    _, session, _, plan_service, plan = _create_bound_git_session(db_session, tmp_path)

    result = WorktreeCleanupService(worktree_plan_service=plan_service).cleanup_workspace(
        WorktreeCleanupRequest(
            agent_session_id=session.id,
            plan_hash=plan.plan_hash,
            user_confirmed=True,
        )
    )

    assert result.cleanup_status == "blocked"
    assert result.blocked_reason == "workspace_cleanup_blocked"
    assert "workspace cleanup execution is blocked in P1-E-A" in result.blockers
    assert "git worktree remove is not enabled" in result.blockers
    assert "git branch delete is not enabled" in result.blockers
    assert result.worktree_path == plan.worktree_path
    assert result.branch_name == plan.branch_name
    assert result.removes_worktree is False
    assert result.deletes_branch is False
    assert result.deletes_directory is False
    assert result.runs_git is False
    assert result.runs_write_git is False
    assert result.mutates_agent_session_workspace is False
    assert result.cleanup_command_preview == [
        result.cleanup_command_preview[0],
        result.cleanup_command_preview[1],
    ]
    assert result.cleanup_command_preview[0].argv == (
        "git",
        "worktree",
        "remove",
        plan.worktree_path,
    )
    assert result.cleanup_command_preview[0].command_kind == "git_worktree_remove"
    assert result.cleanup_command_preview[0].execution_enabled is False
    assert result.cleanup_command_preview[1].argv == (
        "git",
        "branch",
        "-d",
        plan.branch_name,
    )
    assert result.cleanup_command_preview[1].command_kind == "git_branch_delete"
    assert result.cleanup_command_preview[1].execution_enabled is False
    assert not Path(plan.worktree_path).exists()

    unchanged_session = AgentSessionRepository(db_session).get_by_id(session.id)
    assert unchanged_session is not None
    assert unchanged_session.workspace_path is None
    assert unchanged_session.branch_name is None
    assert unchanged_session.workspace_clean is None
    assert unchanged_session.last_workspace_error is None


def test_worktree_cleanup_rejects_stale_plan_hash(db_session, tmp_path):
    """Cleanup preview requires the current dry-run plan hash."""

    _, session, _, plan_service, _ = _create_bound_git_session(db_session, tmp_path)

    with pytest.raises(WorktreeCleanupHashMismatchError):
        WorktreeCleanupService(worktree_plan_service=plan_service).cleanup_workspace(
            WorktreeCleanupRequest(
                agent_session_id=session.id,
                plan_hash="0" * 64,
                user_confirmed=True,
            )
        )


def test_worktree_cleanup_response_exposes_blocked_guard_fields(db_session, tmp_path):
    """Cleanup API DTO exposes review-only command previews and false mutation flags."""

    _, session, _, plan_service, plan = _create_bound_git_session(db_session, tmp_path)
    result = WorktreeCleanupService(worktree_plan_service=plan_service).cleanup_workspace(
        WorktreeCleanupRequest(
            agent_session_id=session.id,
            plan_hash=plan.plan_hash,
            user_confirmed=True,
        )
    )

    payload = WorktreeCleanupResponse.from_result(result).model_dump(mode="json")

    assert payload["agent_session_id"] == str(session.id)
    assert payload["plan_hash"] == plan.plan_hash
    assert payload["submitted_plan_hash"] == plan.plan_hash
    assert payload["cleanup_status"] == "blocked"
    assert payload["blocked_reason"] == "workspace_cleanup_blocked"
    assert payload["removes_worktree"] is False
    assert payload["deletes_branch"] is False
    assert payload["deletes_directory"] is False
    assert payload["runs_git"] is False
    assert payload["runs_write_git"] is False
    assert payload["mutates_agent_session_workspace"] is False
    assert payload["cleanup_command_preview"][0]["command_kind"] == "git_worktree_remove"
    assert payload["cleanup_command_preview"][0]["execution_enabled"] is False
    assert payload["cleanup_command_preview"][1]["command_kind"] == "git_branch_delete"
    assert payload["cleanup_command_preview"][1]["execution_enabled"] is False


def test_worktree_cleanup_endpoint_returns_blocked_preview(db_session, tmp_path):
    """Route function returns blocked cleanup preview without executing cleanup."""

    _, session, _, plan_service, plan = _create_bound_git_session(db_session, tmp_path)
    cleanup_service = WorktreeCleanupService(worktree_plan_service=plan_service)

    response = cleanup_agent_session_workspace(
        session_id=session.id,
        request=WorktreeCleanupRequestBody(
            plan_hash=plan.plan_hash,
            user_confirmed=True,
        ),
        cleanup_service=cleanup_service,
    )

    assert response.cleanup_status == "blocked"
    assert response.blocked_reason == "workspace_cleanup_blocked"
    assert response.removes_worktree is False
    assert response.deletes_branch is False
    assert response.deletes_directory is False
    assert response.runs_git is False
    assert response.runs_write_git is False
    assert response.mutates_agent_session_workspace is False
    assert response.cleanup_command_preview[0].argv == (
        "git",
        "worktree",
        "remove",
        plan.worktree_path,
    )
    assert response.cleanup_command_preview[0].execution_enabled is False
    assert response.cleanup_command_preview[1].argv == (
        "git",
        "branch",
        "-d",
        plan.branch_name,
    )
    assert response.cleanup_command_preview[1].execution_enabled is False

    unchanged_session = AgentSessionRepository(db_session).get_by_id(session.id)
    assert unchanged_session is not None
    assert unchanged_session.workspace_path is None
    assert unchanged_session.branch_name is None
