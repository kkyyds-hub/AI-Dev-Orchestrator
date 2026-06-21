from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.external_executors.actual_native_launcher import (
    FakeRealExecutorNativeRunner,
    RealExecutorNativeLaunchMode,
    RealExecutorNativeProcessHandle,
)
from app.external_executors.actual_process_supervisor import (
    RealExecutorProcessSupervisor,
)
from app.external_executors.actual_runner_wiring import (
    RealExecutorRunnerFactory,
    RealExecutorRunnerWiringInput,
    RealExecutorRunnerWiringMode,
)
from app.external_executors.actual_silent_launch_service import (
    RealExecutorSilentLaunchInput,
)


RUNNER_WIRING_FILE = Path("app/external_executors/actual_runner_wiring.py")
NATIVE_LAUNCHER_FILE = Path("app/external_executors/actual_native_launcher.py")


class _StartCountingRunner:
    def __init__(self) -> None:
        self.start_calls = 0

    def start(
        self,
        *,
        argv: tuple[str, ...],
        workspace_path: str,
        agent_session_id: str,
    ) -> RealExecutorNativeProcessHandle:
        self.start_calls += 1
        raise AssertionError("runner.start must not be called during wiring")


def test_default_factory_returns_fake_disabled_policy() -> None:
    fake_runner = FakeRealExecutorNativeRunner(process_handle_id="factory-fake")
    result = RealExecutorRunnerFactory(fake_runner=fake_runner).wire()

    assert result.runner_kind == "fake"
    assert result.launch_mode == RealExecutorNativeLaunchMode.DISABLED
    assert result.allow_native_process is False
    assert result.service_ready is True
    assert result.native_process_possible is False
    assert result.product_runtime_git_write_allowed is False
    assert result.frontend_required is False
    assert result.frontend_change_allowed is False
    assert "native_runner_fake_only" in result.blocked_reasons
    assert fake_runner.started is False


def test_subprocess_disabled_does_not_make_native_process_possible() -> None:
    process_runner = _StartCountingRunner()
    result = RealExecutorRunnerFactory(process_runner=process_runner).wire(
        RealExecutorRunnerWiringInput(
            wiring_mode=RealExecutorRunnerWiringMode.SUBPROCESS_DISABLED,
            launch_mode=RealExecutorNativeLaunchMode.ENABLED,
            allow_native_process=True,
            executor_label="codex",
        )
    )

    assert result.runner_kind == "subprocess"
    assert result.service_ready is True
    assert result.native_process_possible is False
    assert "native_runner_policy_disabled" in result.blocked_reasons
    assert process_runner.start_calls == 0


@pytest.mark.parametrize(
    ("launch_mode", "allow_native_process", "native_process_possible"),
    [
        (RealExecutorNativeLaunchMode.DISABLED, True, False),
        (RealExecutorNativeLaunchMode.DRY_RUN, True, False),
        (RealExecutorNativeLaunchMode.ENABLED, False, False),
        (RealExecutorNativeLaunchMode.ENABLED, True, True),
    ],
)
def test_subprocess_enabled_requires_enabled_launch_and_allow_native_process(
    launch_mode: RealExecutorNativeLaunchMode,
    allow_native_process: bool,
    native_process_possible: bool,
) -> None:
    process_runner = _StartCountingRunner()
    result = RealExecutorRunnerFactory(process_runner=process_runner).wire(
        RealExecutorRunnerWiringInput(
            wiring_mode=RealExecutorRunnerWiringMode.SUBPROCESS_ENABLED,
            launch_mode=launch_mode,
            allow_native_process=allow_native_process,
            executor_label="codex",
        )
    )

    assert result.runner_kind == "subprocess"
    assert result.native_process_possible is native_process_possible
    assert result.product_runtime_git_write_allowed is False
    assert result.frontend_required is False
    assert result.frontend_change_allowed is False
    assert process_runner.start_calls == 0


def test_factory_service_can_launch_with_fake_runner_when_later_invoked(db_session) -> None:
    from uuid import uuid4

    from app.domain.agent_session import (
        AgentSessionPhase,
        AgentSessionReviewStatus,
        AgentSessionStatus,
    )
    from app.repositories.agent_session_repository import AgentSessionRepository

    repository = AgentSessionRepository(db_session)
    session = repository.create(
        project_id=uuid4(),
        task_id=uuid4(),
        run_id=uuid4(),
        status=AgentSessionStatus.RUNNING,
        review_status=AgentSessionReviewStatus.NONE,
        current_phase=AgentSessionPhase.CONTEXT_READY,
        owner_role_code=None,
        context_checkpoint_id=None,
        context_rehydrated=False,
        summary="runner wiring",
    )
    result = RealExecutorRunnerFactory(
        fake_runner=FakeRealExecutorNativeRunner(process_handle_id="wired-fake"),
    ).wire(
        RealExecutorRunnerWiringInput(
            wiring_mode=RealExecutorRunnerWiringMode.FAKE,
            launch_mode=RealExecutorNativeLaunchMode.ENABLED,
            allow_native_process=True,
            executor_label="codex",
        ),
        agent_session_repository=repository,
    )

    assert result.silent_launch_service is not None
    launch_result = result.silent_launch_service.launch(
        RealExecutorSilentLaunchInput(
            agent_session_id=session.id,
            executor_label="codex",
            workspace_path="/tmp/wired-fake-workspace",
            prelaunch_ready=True,
            launch_mode=result.launch_mode,
            allow_native_process=result.allow_native_process,
        )
    )

    assert launch_result.launch_status == "launch_started"
    assert launch_result.runtime_handle_id == "wired-fake"


def test_factory_injects_process_supervisor_into_default_subprocess_runner(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    class _CapturedSubprocessRunner(_StartCountingRunner):
        def __init__(self, **kwargs) -> None:
            super().__init__()
            captured.update(kwargs)

    monkeypatch.setattr(
        "app.external_executors.actual_runner_wiring.SubprocessRealExecutorNativeRunner",
        _CapturedSubprocessRunner,
    )
    supervisor = RealExecutorProcessSupervisor()

    RealExecutorRunnerFactory(process_supervisor=supervisor).wire(
        RealExecutorRunnerWiringInput(
            wiring_mode=RealExecutorRunnerWiringMode.SUBPROCESS_ENABLED,
            launch_mode=RealExecutorNativeLaunchMode.ENABLED,
            allow_native_process=True,
            executor_label="codex",
        )
    )

    assert captured["process_supervisor"] is supervisor


def test_forbidden_true_flags_are_rejected() -> None:
    for field_name in [
        "product_runtime_git_write_allowed",
        "frontend_required",
        "frontend_change_allowed",
    ]:
        with pytest.raises(ValidationError):
            RealExecutorRunnerWiringInput(**{field_name: True})


def test_wiring_module_does_not_add_spawn_env_git_or_api_surface() -> None:
    source = RUNNER_WIRING_FILE.read_text()
    module = ast.parse(source)

    assert "Popen" not in source
    assert "create_subprocess" not in source
    assert "shell=True" not in source
    assert "os.environ" not in source
    assert "getenv" not in source
    assert "raw_command" not in source
    assert "stdout" not in source
    assert "stderr" not in source
    assert "api_key" not in source
    assert "secret" not in source.lower()
    assert "user_confirmed" not in source
    assert "confirmation_phrase" not in source
    assert "WorktreeCreateService" not in source
    assert "WorktreeCleanupService" not in source
    assert "WorktreeWriteCommandRunner" not in source
    assert "APIRouter" not in source
    assert "FastAPI" not in source
    for node in ast.walk(module):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {
                "start",
                "create_workspace",
                "cleanup_workspace",
                "run",
            }


def test_no_new_process_boundary_outside_native_launcher() -> None:
    for path in Path("app/external_executors").glob("actual_*.py"):
        if path == NATIVE_LAUNCHER_FILE:
            continue
        source = path.read_text()
        assert "Popen" not in source
        assert "create_subprocess" not in source


@pytest.fixture()
def db_session(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.db_tables import ORMBase

    db_path = tmp_path / "orchestrator-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
