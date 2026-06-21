from __future__ import annotations

import ast
from pathlib import Path

from app.external_executors.actual_process_supervisor import (
    RealExecutorProcessStatus,
    RealExecutorProcessSupervisor,
)


SUPERVISOR_FILE = Path("app/external_executors/actual_process_supervisor.py")


class _FakeProcessAdapter:
    def __init__(self) -> None:
        self.terminate_calls = 0
        self.kill_calls = 0

    def terminate(self) -> None:
        self.terminate_calls += 1

    def kill(self) -> None:
        self.kill_calls += 1


def _supervisor_with_process():
    process = _FakeProcessAdapter()
    supervisor = RealExecutorProcessSupervisor()
    record = supervisor.register(
        "opaque-handle-1",
        executor_label="codex",
        agent_session_id="agent-session-1",
        workspace_path="/tmp/ai-dev-orchestrator-workspace",
        process_adapter=process,
    )
    return supervisor, process, record


def test_register_then_get_status_returns_running_record() -> None:
    supervisor, _, record = _supervisor_with_process()

    assert record.process_handle_id == "opaque-handle-1"
    assert record.status == RealExecutorProcessStatus.RUNNING

    status = supervisor.get_status("opaque-handle-1")

    assert status.status == RealExecutorProcessStatus.RUNNING
    assert status.process_handle_id == "opaque-handle-1"
    assert status.executor_label == "codex"
    assert status.agent_session_id == "agent-session-1"
    assert status.workspace_path == "/tmp/ai-dev-orchestrator-workspace"


def test_terminate_registered_process_calls_adapter_without_exposing_pid() -> None:
    supervisor, process, _ = _supervisor_with_process()

    result = supervisor.terminate("opaque-handle-1")
    status = supervisor.get_status("opaque-handle-1")

    assert process.terminate_calls == 1
    assert process.kill_calls == 0
    assert result.status == RealExecutorProcessStatus.TERMINATED
    assert result.action_success is True
    assert status.status == RealExecutorProcessStatus.TERMINATED
    assert "pid" not in result.model_dump_json().lower()


def test_kill_registered_process_calls_adapter_without_exposing_pid() -> None:
    supervisor, process, _ = _supervisor_with_process()

    result = supervisor.kill("opaque-handle-1")
    status = supervisor.get_status("opaque-handle-1")

    assert process.terminate_calls == 0
    assert process.kill_calls == 1
    assert result.status == RealExecutorProcessStatus.KILLED
    assert result.action_success is True
    assert status.status == RealExecutorProcessStatus.KILLED
    assert "pid" not in result.model_dump_json().lower()


def test_cleanup_registered_handle_removes_registry_record_without_touching_workspace(
    tmp_path,
) -> None:
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    sentinel = workspace_path / "sentinel.txt"
    sentinel.write_text("keep")
    supervisor = RealExecutorProcessSupervisor()
    supervisor.register(
        "opaque-handle-1",
        executor_label="codex",
        agent_session_id="agent-session-1",
        workspace_path=workspace_path.as_posix(),
        process_adapter=_FakeProcessAdapter(),
    )

    result = supervisor.cleanup("opaque-handle-1")

    assert result.status == RealExecutorProcessStatus.CLEANUP_DONE
    assert result.action_success is True
    assert supervisor.get_status("opaque-handle-1").status == (
        RealExecutorProcessStatus.MISSING
    )
    assert sentinel.exists()


def test_missing_handle_actions_return_safe_missing_result() -> None:
    supervisor = RealExecutorProcessSupervisor()

    for result in [
        supervisor.terminate("missing-handle"),
        supervisor.kill("missing-handle"),
        supervisor.cleanup("missing-handle"),
    ]:
        assert result.status == RealExecutorProcessStatus.MISSING
        assert result.action_success is False
        assert result.process_handle_id == "missing-handle"


def test_snapshot_contains_only_safe_registry_fields() -> None:
    supervisor, _, _ = _supervisor_with_process()

    snapshot = supervisor.snapshot()
    serialized = snapshot.model_dump_json().lower()

    assert snapshot.total_records == 1
    assert snapshot.records[0].process_handle_id == "opaque-handle-1"
    for forbidden in {
        "raw_command",
        "stdout",
        "stderr",
        "env",
        "api_key",
        "token",
        "secret",
        "pid",
    }:
        assert forbidden not in serialized


def test_supervisor_module_does_not_add_process_env_git_or_api_surface() -> None:
    source = SUPERVISOR_FILE.read_text()
    module = ast.parse(source)

    assert "subprocess" not in source
    assert "Popen" not in source
    assert "create_subprocess" not in source
    assert "shell=True" not in source
    assert "os.environ" not in source
    assert "getenv" not in source
    assert "raw_command" not in source
    assert "stdout" not in source
    assert "stderr" not in source
    assert "api_key" not in source
    assert "token" not in source
    assert "secret" not in source.lower()
    assert "WorktreeCreateService" not in source
    assert "WorktreeCleanupService" not in source
    assert "WorktreeWriteCommandRunner" not in source
    assert "APIRouter" not in source
    assert "FastAPI" not in source
    for node in ast.walk(module):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {
                "create_workspace",
                "cleanup_workspace",
                "run",
            }


def test_no_apps_web_changes_are_added() -> None:
    assert not any(Path("../../apps/web").glob("**/*process*supervisor*"))
