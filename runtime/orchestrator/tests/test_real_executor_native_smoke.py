from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.external_executors.actual_native_launcher import (
    RealExecutorNativeLaunchMode,
    RealExecutorNativeProcessHandle,
)
from app.external_executors.actual_native_smoke import (
    RealExecutorNativeSmokeInput,
    RealExecutorNativeSmokeRunner,
)


SMOKE_FILE = Path("app/external_executors/actual_native_smoke.py")
SMOKE_SCRIPT = Path("scripts/p9_real_executor_native_smoke.py")


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
        return RealExecutorNativeProcessHandle(process_handle_id="fake-process-handle")


def _smoke_script_module():
    spec = importlib.util.spec_from_file_location(
        "p9_real_executor_native_smoke",
        SMOKE_SCRIPT,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_smoke_script(args: list[str], capsys):
    exit_code = _smoke_script_module().main(args)
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out)


def test_smoke_default_fake_dry_run_does_not_start_native_process(tmp_path) -> None:
    runner = _StartCountingRunner()
    result = RealExecutorNativeSmokeRunner(fake_runner=runner).run(
        RealExecutorNativeSmokeInput(workspace_path=tmp_path.as_posix())
    )

    assert result.smoke_status == "dry_run_ready"
    assert result.runner_kind == "fake"
    assert result.launch_mode == RealExecutorNativeLaunchMode.DRY_RUN
    assert result.native_process_possible is False
    assert result.process_handle_id_present is False
    assert result.agent_session_bound is False
    assert result.product_runtime_git_write_allowed is False
    assert result.frontend_required is False
    assert result.frontend_change_allowed is False
    assert result.blocked_reasons == []
    assert runner.start_calls == 0


def test_smoke_fake_enabled_with_enable_native_process_binds_fake_handle(tmp_path) -> None:
    result = RealExecutorNativeSmokeRunner().run(
        RealExecutorNativeSmokeInput(
            runner_kind="fake",
            launch_mode=RealExecutorNativeLaunchMode.ENABLED,
            enable_native_process=True,
            workspace_path=tmp_path.as_posix(),
        )
    )

    assert result.smoke_status == "launch_started"
    assert result.runner_kind == "fake"
    assert result.native_process_possible is False
    assert result.process_handle_id_present is True
    assert result.agent_session_bound is True
    assert result.product_runtime_git_write_allowed is False


def test_subprocess_enabled_without_enable_native_process_blocks_without_start(
    tmp_path,
) -> None:
    process_runner = _StartCountingRunner()
    result = RealExecutorNativeSmokeRunner(process_runner=process_runner).run(
        RealExecutorNativeSmokeInput(
            runner_kind="subprocess",
            launch_mode=RealExecutorNativeLaunchMode.ENABLED,
            enable_native_process=False,
            workspace_path=tmp_path.as_posix(),
        )
    )

    assert result.smoke_status == "blocked"
    assert result.runner_kind == "subprocess"
    assert result.native_process_possible is False
    assert result.process_handle_id_present is False
    assert result.agent_session_bound is False
    assert "native_process_not_allowed" in result.blocked_reasons
    assert process_runner.start_calls == 0


def test_subprocess_enabled_without_termination_guard_blocks_without_start(
    tmp_path,
) -> None:
    process_runner = _StartCountingRunner()
    result = RealExecutorNativeSmokeRunner(process_runner=process_runner).run(
        RealExecutorNativeSmokeInput(
            runner_kind="subprocess",
            launch_mode=RealExecutorNativeLaunchMode.ENABLED,
            enable_native_process=True,
            workspace_path=tmp_path.as_posix(),
        )
    )

    assert result.smoke_status == "blocked"
    assert "native_smoke_requires_termination_guard" in result.blocked_reasons
    assert result.process_handle_id_present is False
    assert result.agent_session_bound is False
    assert process_runner.start_calls == 0


def test_subprocess_smoke_can_use_injected_runner_without_real_process(tmp_path) -> None:
    process_runner = _StartCountingRunner()
    result = RealExecutorNativeSmokeRunner(process_runner=process_runner).run(
        RealExecutorNativeSmokeInput(
            runner_kind="subprocess",
            launch_mode=RealExecutorNativeLaunchMode.ENABLED,
            enable_native_process=True,
            auto_terminate=True,
            workspace_path=tmp_path.as_posix(),
        )
    )

    assert result.smoke_status == "launch_started"
    assert result.native_process_possible is True
    assert result.process_handle_id_present is True
    assert result.agent_session_bound is True
    assert process_runner.start_calls == 1


def test_workspace_path_must_be_absolute() -> None:
    with pytest.raises(ValidationError):
        RealExecutorNativeSmokeInput(workspace_path="relative/workspace")


def test_smoke_result_safe_summary_excludes_payload_and_sensitive_fields(tmp_path) -> None:
    result = RealExecutorNativeSmokeRunner().run(
        RealExecutorNativeSmokeInput(workspace_path=tmp_path.as_posix())
    )
    body = result.model_dump()
    serialized = result.model_dump_json().lower()

    assert set(body) == {
        "smoke_status",
        "runner_kind",
        "launch_mode",
        "native_process_possible",
        "process_handle_id_present",
        "agent_session_bound",
        "product_runtime_git_write_allowed",
        "frontend_required",
        "frontend_change_allowed",
        "blocked_reasons",
    }
    for forbidden in {
        "raw_command",
        "stdout",
        "stderr",
        "env",
        "api_key",
        "token",
        "secret",
    }:
        assert forbidden not in serialized


def test_forbidden_flags_are_rejected(tmp_path) -> None:
    for field_name in [
        "product_runtime_git_write_allowed",
        "frontend_required",
        "frontend_change_allowed",
    ]:
        with pytest.raises(ValidationError):
            RealExecutorNativeSmokeInput(
                workspace_path=tmp_path.as_posix(),
                **{field_name: True},
            )


def test_cli_blocked_result_returns_zero_by_default(tmp_path, capsys) -> None:
    exit_code, summary = _run_smoke_script(
        [
            "--runner",
            "subprocess",
            "--launch-mode",
            "enabled",
            "--workspace-path",
            tmp_path.as_posix(),
            "--json",
        ],
        capsys,
    )

    assert exit_code == 0
    assert summary["smoke_status"] == "blocked"


def test_cli_fail_on_blocked_returns_two_for_blocked_result(tmp_path, capsys) -> None:
    exit_code, summary = _run_smoke_script(
        [
            "--runner",
            "subprocess",
            "--launch-mode",
            "enabled",
            "--workspace-path",
            tmp_path.as_posix(),
            "--fail-on-blocked",
            "--json",
        ],
        capsys,
    )

    assert exit_code == 2
    assert summary["smoke_status"] == "blocked"


def test_cli_fail_on_blocked_keeps_dry_run_ready_zero(tmp_path, capsys) -> None:
    exit_code, summary = _run_smoke_script(
        [
            "--launch-mode",
            "dry_run",
            "--workspace-path",
            tmp_path.as_posix(),
            "--fail-on-blocked",
            "--json",
        ],
        capsys,
    )

    assert exit_code == 0
    assert summary["smoke_status"] == "dry_run_ready"


def test_cli_subprocess_enabled_requires_termination_guard(tmp_path, capsys) -> None:
    exit_code, summary = _run_smoke_script(
        [
            "--runner",
            "subprocess",
            "--launch-mode",
            "enabled",
            "--enable-native-process",
            "--workspace-path",
            tmp_path.as_posix(),
            "--json",
        ],
        capsys,
    )

    assert exit_code == 0
    assert summary["smoke_status"] == "blocked"
    assert "native_smoke_requires_termination_guard" in summary["blocked_reasons"]


def test_cli_accepts_auto_terminate_without_native_process_in_dry_run(
    tmp_path,
    capsys,
) -> None:
    exit_code, summary = _run_smoke_script(
        [
            "--runner",
            "subprocess",
            "--auto-terminate",
            "--workspace-path",
            tmp_path.as_posix(),
            "--json",
        ],
        capsys,
    )

    assert exit_code == 0
    assert summary["smoke_status"] == "dry_run_ready"
    assert "native_smoke_requires_termination_guard" not in summary["blocked_reasons"]


def test_smoke_module_and_script_do_not_add_process_env_git_or_api_surface() -> None:
    for path in [SMOKE_FILE, SMOKE_SCRIPT]:
        source = path.read_text()
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
        assert "pid" not in source
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
                    "create_workspace",
                    "cleanup_workspace",
                }


def test_no_apps_web_changes_are_added() -> None:
    assert not any(Path("../../apps/web").glob("**/*native*smoke*"))
