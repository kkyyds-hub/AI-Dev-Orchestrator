from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any
import importlib.util


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    RUNTIME_ROOT
    / "scripts"
    / "p14_project_director_controlled_subprocess_smoke.py"
)
RUNTIME_DATA_DIR = RUNTIME_ROOT / "data"
FORBIDDEN_OUTPUT_KEYS = {
    "api_key",
    "token",
    "secret",
    "pid",
    "raw command",
    "raw stdout",
    "raw stderr",
}


def _walk_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        keys = {str(key).lower() for key in value}
        for child in value.values():
            keys.update(_walk_keys(child))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for child in value:
            keys.update(_walk_keys(child))
        return keys
    return set()


def _run_script(*args: str) -> tuple[int, dict[str, Any]]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--json", *args],
        cwd=RUNTIME_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode, json.loads(result.stdout)


def _load_smoke_module():
    scripts_dir = str(RUNTIME_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("p14_smoke", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert_blocked_without_launch(summary: dict[str, Any]) -> None:
    assert summary["smoke_status"] == "blocked"
    assert summary["native_executor_started"] is False
    assert summary["codex_started"] is False
    assert summary["claude_code_started"] is False
    assert summary["agent_session_bound"] is False
    assert summary["runtime_handle_id_present"] is False
    assert summary["process_handle_id_present"] is False
    assert summary["supervisor_registered"] is False
    assert summary["terminate_attempted"] is False
    assert summary["supervisor_cleanup_done"] is False
    assert summary["product_runtime_git_write_allowed"] is False
    assert summary["worktree_write_allowed"] is False
    assert summary["git_write_performed"] is False
    assert _walk_keys(summary).isdisjoint(FORBIDDEN_OUTPUT_KEYS)


def test_p14_default_smoke_is_dry_run_and_passes() -> None:
    returncode, summary = _run_script()

    assert returncode == 0
    assert summary["smoke_status"] == "passed_dry_run"
    assert summary["launch_mode"] == "dry_run"
    assert summary["session_created"] is True
    assert summary["project_id_present"] is True
    assert summary["p11_dry_run_message_bound"] is True
    assert summary["p12_safe_task_created"] is True
    assert summary["p12_worker_run_once_ok"] is True
    assert summary["p12_worker_simulate_mode"] is True
    assert summary["p13_dispatch_message_bound"] is True
    assert summary["message_readback_ok"] is True
    assert summary["native_executor_started"] is False
    assert summary["agent_session_bound"] is False
    assert summary["process_handle_id_present"] is False
    assert summary["product_runtime_git_write_allowed"] is False
    assert summary["worktree_write_allowed"] is False
    assert summary["ai_project_director_total_loop"] == "Partial"
    assert Path(summary["runtime_data_dir"]) != RUNTIME_DATA_DIR.resolve()
    assert Path(summary["runtime_data_dir"]).exists() is False
    assert _walk_keys(summary).isdisjoint(FORBIDDEN_OUTPUT_KEYS)


def test_p14_controlled_smoke_missing_enable_native_process_blocks() -> None:
    returncode, summary = _run_script(
        "--launch-mode",
        "controlled_smoke",
        "--auto-terminate",
        "--timeout-seconds",
        "2",
        "--use-supervisor",
        "--supervisor-cleanup-after-launch",
    )

    assert returncode == 1
    assert "enable_native_process_required" in summary["blocked_reasons"]
    _assert_blocked_without_launch(summary)


def test_p14_controlled_smoke_missing_auto_terminate_blocks() -> None:
    returncode, summary = _run_script(
        "--launch-mode",
        "controlled_smoke",
        "--enable-native-process",
        "--timeout-seconds",
        "2",
        "--use-supervisor",
        "--supervisor-cleanup-after-launch",
    )

    assert returncode == 1
    assert "auto_terminate_required" in summary["blocked_reasons"]
    _assert_blocked_without_launch(summary)


def test_p14_controlled_smoke_missing_timeout_blocks() -> None:
    returncode, summary = _run_script(
        "--launch-mode",
        "controlled_smoke",
        "--enable-native-process",
        "--auto-terminate",
        "--use-supervisor",
        "--supervisor-cleanup-after-launch",
    )

    assert returncode == 1
    assert "positive_timeout_seconds_required" in summary["blocked_reasons"]
    _assert_blocked_without_launch(summary)


def test_p14_controlled_smoke_missing_supervisor_blocks() -> None:
    returncode, summary = _run_script(
        "--launch-mode",
        "controlled_smoke",
        "--enable-native-process",
        "--auto-terminate",
        "--timeout-seconds",
        "2",
        "--supervisor-cleanup-after-launch",
    )

    assert returncode == 1
    assert "supervisor_required" in summary["blocked_reasons"]
    _assert_blocked_without_launch(summary)


def test_p14_controlled_smoke_missing_cleanup_blocks() -> None:
    returncode, summary = _run_script(
        "--launch-mode",
        "controlled_smoke",
        "--enable-native-process",
        "--auto-terminate",
        "--timeout-seconds",
        "2",
        "--use-supervisor",
    )

    assert returncode == 1
    assert "supervisor_cleanup_after_launch_required" in summary["blocked_reasons"]
    _assert_blocked_without_launch(summary)


def test_p14_output_does_not_contain_sensitive_payload_text() -> None:
    _returncode, summary = _run_script("--launch-mode", "controlled_smoke")
    serialized = json.dumps(summary, ensure_ascii=False).lower()

    for forbidden in {
        "api_key",
        "token",
        "secret",
        "pid",
        "raw command",
        "raw stdout",
        "raw stderr",
        "raw_command",
        "raw_stdout",
        "raw_stderr",
        "已授权 git 写",
        "代码已写入",
    }:
        assert forbidden not in serialized


def test_p14_controlled_smoke_with_all_safety_flags_uses_fake_runner() -> None:
    returncode, summary = _run_script(
        "--launch-mode",
        "controlled_smoke",
        "--executor",
        "codex",
        "--requested-agent-role",
        "programmer",
        "--enable-native-process",
        "--auto-terminate",
        "--timeout-seconds",
        "2",
        "--use-supervisor",
        "--supervisor-cleanup-after-launch",
        "--fake-runner",
    )

    assert returncode == 0
    assert summary["smoke_status"] == "passed_controlled_smoke"
    assert summary["launch_mode"] == "controlled_smoke"
    assert summary["requested_executor"] == "codex"
    assert summary["requested_agent_role"] == "programmer"
    assert summary["controlled_subprocess_runner"] == "fake"
    assert summary["session_created"] is True
    assert summary["project_id_present"] is True
    assert summary["p11_dry_run_message_bound"] is True
    assert summary["p12_safe_task_created"] is True
    assert summary["p12_worker_run_once_ok"] is True
    assert summary["p12_worker_simulate_mode"] is True
    assert summary["p13_dispatch_message_bound"] is True
    assert summary["source_task_id_present"] is True
    assert summary["source_message_id_present"] is True
    assert summary["run_id_present"] is True
    assert summary["native_executor_started"] is True
    assert summary["codex_started"] is True
    assert summary["claude_code_started"] is False
    assert summary["agent_session_bound"] is True
    assert summary["runtime_handle_id_present"] is True
    assert summary["process_handle_id_present"] is True
    assert summary["supervisor_required"] is True
    assert summary["supervisor_registered"] is True
    assert summary["terminate_attempted"] is True
    assert summary["cleanup_required"] is True
    assert summary["supervisor_cleanup_done"] is True
    assert summary["product_runtime_git_write_allowed"] is False
    assert summary["worktree_write_allowed"] is False
    assert summary["frontend_required"] is False
    assert summary["run_created"] is True
    assert summary["run_created_by"] == "p12_worker_simulate"
    assert summary["real_code_modified"] is False
    assert summary["git_write_performed"] is False
    assert summary["ai_project_director_total_loop"] == "Partial"
    assert summary["p9_production_safe_long_running_executor_lifecycle"] == (
        "Pass with note"
    )
    assert summary["blocked_reasons"] == []
    assert _walk_keys(summary).isdisjoint(FORBIDDEN_OUTPUT_KEYS)


def test_p14_controlled_smoke_executor_unavailable_blocks_safely(
    tmp_path,
    monkeypatch,
) -> None:
    module = _load_smoke_module()
    monkeypatch.setattr(module.shutil, "which", lambda _command_name: None)
    args = module.argparse.Namespace(
        json=True,
        keep_temp_data=False,
        runtime_dir=None,
        launch_mode="controlled_smoke",
        executor="codex",
        requested_agent_role="programmer",
        enable_native_process=True,
        auto_terminate=True,
        timeout_seconds=2.0,
        use_supervisor=True,
        supervisor_cleanup_after_launch=True,
        fake_runner=False,
    )

    runtime_dir = tmp_path / "p14-unavailable"
    runtime_dir.mkdir()
    summary = module.run_smoke(runtime_dir, args)

    assert summary["smoke_status"] == "blocked"
    assert "executor_unavailable" in summary["blocked_reasons"]
    assert summary["native_executor_started"] is False
    assert summary["agent_session_bound"] is False
    assert summary["process_handle_id_present"] is False
    assert summary["supervisor_registered"] is False
    assert summary["supervisor_cleanup_done"] is False
    assert summary["product_runtime_git_write_allowed"] is False
    assert summary["git_write_performed"] is False
    assert _walk_keys(summary).isdisjoint(FORBIDDEN_OUTPUT_KEYS)
