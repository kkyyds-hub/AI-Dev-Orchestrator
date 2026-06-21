from __future__ import annotations

import ast
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db_tables import ORMBase
from app.domain.agent_session import (
    AgentSessionPhase,
    AgentSessionReviewStatus,
    AgentSessionStatus,
    AgentType,
    CodingSessionActivityState,
    CodingSessionStatus,
    RuntimeType,
    WorkspaceType,
)
from app.external_executors.actual_native_launcher import (
    FakeRealExecutorNativeRunner,
    RealExecutorNativeLaunchMode,
    RealExecutorNativeLauncher,
)
from app.external_executors.actual_silent_launch_service import (
    RealExecutorSilentLaunchInput,
    RealExecutorSilentLaunchService,
)
from app.repositories.agent_session_repository import AgentSessionRepository


SILENT_LAUNCH_FILE = Path("app/external_executors/actual_silent_launch_service.py")


@pytest.fixture()
def db_session(tmp_path):
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


def _agent_session(repository: AgentSessionRepository):
    return repository.create(
        project_id=uuid4(),
        task_id=uuid4(),
        run_id=uuid4(),
        status=AgentSessionStatus.RUNNING,
        review_status=AgentSessionReviewStatus.NONE,
        current_phase=AgentSessionPhase.CONTEXT_READY,
        owner_role_code=None,
        context_checkpoint_id=None,
        context_rehydrated=False,
        summary="silent launch pending",
    )


def _service(repository: AgentSessionRepository, *, process_handle_id: str = "fake-handle-1"):
    return RealExecutorSilentLaunchService(
        agent_session_repository=repository,
        native_launcher=RealExecutorNativeLauncher(
            runner=FakeRealExecutorNativeRunner(process_handle_id=process_handle_id),
        ),
    )


def _input(agent_session_id, **overrides) -> RealExecutorSilentLaunchInput:
    values = {
        "agent_session_id": agent_session_id,
        "executor_label": "codex",
        "workspace_path": "/tmp/ai-dev-orchestrator-worktree",
        "prelaunch_ready": True,
        "launch_mode": RealExecutorNativeLaunchMode.ENABLED,
        "allow_native_process": True,
        "command_plan_redacted": True,
    }
    values.update(overrides)
    return RealExecutorSilentLaunchInput(**values)


def _launch(db_session, **overrides):
    repository = AgentSessionRepository(db_session)
    session = _agent_session(repository)
    result = _service(repository).launch(_input(session.id, **overrides))
    updated = repository.get_by_id(session.id)
    assert updated is not None
    return result, updated


def test_disabled_blocks_and_does_not_bind_agent_session(db_session) -> None:
    result, updated = _launch(
        db_session,
        launch_mode=RealExecutorNativeLaunchMode.DISABLED,
        allow_native_process=False,
        prelaunch_ready=False,
        workspace_path=None,
    )

    assert result.launch_status == "blocked"
    assert result.agent_session_bound is False
    assert result.runtime_handle_id is None
    assert updated.runtime_handle_id is None


def test_dry_run_ready_does_not_bind_runtime_handle(db_session) -> None:
    result, updated = _launch(
        db_session,
        launch_mode=RealExecutorNativeLaunchMode.DRY_RUN,
        allow_native_process=False,
    )

    assert result.launch_status == "dry_run_ready"
    assert result.agent_session_bound is False
    assert result.runtime_handle_id is None
    assert updated.runtime_handle_id is None


def test_enabled_blocks_when_internal_auto_launch_policy_fails(db_session) -> None:
    result, updated = _launch(
        db_session,
        internal_auto_launch_policy_passed=False,
    )

    assert result.launch_status == "blocked"
    assert "internal_auto_launch_policy_failed" in result.blocked_reasons
    assert result.agent_session_bound is False
    assert updated.runtime_handle_id is None


def test_enabled_blocks_when_native_process_is_not_allowed(db_session) -> None:
    result, updated = _launch(db_session, allow_native_process=False)

    assert result.launch_status == "blocked"
    assert "native_process_not_allowed" in result.blocked_reasons
    assert updated.runtime_handle_id is None


def test_enabled_blocks_when_prelaunch_is_not_ready(db_session) -> None:
    result, updated = _launch(db_session, prelaunch_ready=False)

    assert result.launch_status == "blocked"
    assert "prelaunch_not_ready" in result.blocked_reasons
    assert updated.runtime_handle_id is None


def test_enabled_blocks_when_workspace_path_is_missing(db_session) -> None:
    result, updated = _launch(db_session, workspace_path=None)

    assert result.launch_status == "blocked"
    assert "workspace_path_missing" in result.blocked_reasons
    assert result.agent_session_bound is False
    assert result.runtime_handle_id is None
    assert updated.runtime_handle_id is None


def test_enabled_all_ready_starts_fake_runner_and_binds_handle(db_session) -> None:
    result, updated = _launch(db_session)

    assert result.launch_status == "launch_started"
    assert result.native_process_started is True
    assert result.agent_session_bound is True
    assert result.runtime_handle_id == "fake-handle-1"
    assert updated.runtime_handle_id == "fake-handle-1"


@pytest.mark.parametrize(
    ("executor_label", "expected_agent_type"),
    [
        ("codex", AgentType.CODEX),
        ("claude-code", AgentType.CLAUDE_CODE),
        ("claude code", AgentType.CLAUDE_CODE),
    ],
)
def test_launch_started_binds_agent_and_runtime_fields(
    db_session,
    executor_label: str,
    expected_agent_type: AgentType,
) -> None:
    result, updated = _launch(db_session, executor_label=executor_label)

    assert result.launch_status == "launch_started"
    assert updated.agent_type == expected_agent_type
    assert updated.runtime_type == RuntimeType.PROCESS
    assert updated.coding_status == CodingSessionStatus.SPAWNING
    assert updated.activity_state == CodingSessionActivityState.ACTIVE
    assert updated.workspace_type == WorkspaceType.WORKTREE
    assert updated.workspace_path == "/tmp/ai-dev-orchestrator-worktree"
    assert result.coding_status_after == CodingSessionStatus.SPAWNING.value
    assert result.activity_state_after == CodingSessionActivityState.ACTIVE.value


@pytest.mark.parametrize(
    "overrides",
    [
        {"launch_mode": RealExecutorNativeLaunchMode.DISABLED, "workspace_path": None},
        {"launch_mode": RealExecutorNativeLaunchMode.DRY_RUN},
        {"allow_native_process": False},
        {"prelaunch_ready": False},
    ],
)
def test_blocked_and_dry_run_results_never_write_runtime_handle(
    db_session,
    overrides,
) -> None:
    result, updated = _launch(db_session, **overrides)

    assert result.runtime_handle_id is None
    assert updated.runtime_handle_id is None


def test_result_keeps_product_git_and_frontend_flags_disabled(db_session) -> None:
    result, _ = _launch(db_session)

    assert result.product_runtime_git_write_allowed is False
    assert result.frontend_required is False
    assert result.frontend_change_allowed is False


def test_result_does_not_expose_payload_or_sensitive_fields(db_session) -> None:
    result, _ = _launch(db_session)
    body = result.model_dump()
    serialized = result.model_dump_json().lower()

    for forbidden_field in {"raw_command", "stdout", "stderr", "env"}:
        assert forbidden_field not in body
    for forbidden_text in {"api_key", "token", "secret", "bearer", "sk-", "password"}:
        assert forbidden_text not in serialized


def test_module_does_not_add_process_or_env_boundary() -> None:
    source = SILENT_LAUNCH_FILE.read_text()

    assert "subprocess" not in source
    assert "Popen" not in source
    assert "create_subprocess" not in source
    assert "os.environ" not in source
    assert "getenv" not in source
    assert "shell=True" not in source


def test_module_does_not_call_worktree_services_or_write_runner() -> None:
    source = SILENT_LAUNCH_FILE.read_text()

    for forbidden in {
        "WorktreeCreateService",
        "WorktreeCleanupService",
        "WorktreeWriteCommandRunner",
        "create_workspace",
        "cleanup_workspace",
    }:
        assert forbidden not in source

    module = ast.parse(source)
    for node in ast.walk(module):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {"create_workspace", "cleanup_workspace", "run"}


def test_no_apps_web_silent_launch_surface_exists() -> None:
    apps_web = Path("../../apps/web")
    assert not any(apps_web.glob("**/*silent*launch*"))
    assert not any(apps_web.glob("**/*native*executor*"))
