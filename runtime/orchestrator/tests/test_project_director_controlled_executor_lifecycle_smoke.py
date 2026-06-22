from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    RUNTIME_ROOT
    / "scripts"
    / "p13_project_director_controlled_executor_lifecycle_smoke.py"
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


def test_p13_project_director_controlled_executor_lifecycle_smoke_dry_run_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--json"],
        cwd=RUNTIME_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    summary = json.loads(result.stdout)

    assert summary["smoke_status"] == "passed_dry_run"
    assert summary["session_created"] is True
    assert summary["session_id"]
    assert summary["p11_dry_run_message_bound"] is True
    assert summary["p12_safe_task_created"] is True
    assert summary["p13_dispatch_message_bound"] is True
    assert summary["launch_mode"] == "dry_run"
    assert summary["requested_executor"] == "codex"
    assert summary["requested_agent_role"] == "programmer"
    assert summary["controlled_executor_pilot"] is True
    assert summary["executor_backed_agent"] is True
    assert summary["native_executor_started"] is False
    assert summary["codex_started"] is False
    assert summary["claude_code_started"] is False
    assert summary["agent_session_bound"] is False
    assert summary["runtime_handle_id_present"] is False
    assert summary["process_handle_id_present"] is False
    assert summary["supervisor_required"] is True
    assert summary["supervisor_registered"] is False
    assert summary["auto_terminate_required"] is True
    assert summary["terminate_attempted"] is False
    assert summary["cleanup_required"] is True
    assert summary["supervisor_cleanup_done"] is False
    assert summary["lifecycle_result_message_bound"] is True
    assert summary["message_readback_ok"] is True
    assert summary["product_runtime_git_write_allowed"] is False
    assert summary["worktree_write_allowed"] is False
    assert summary["frontend_required"] is False
    assert summary["run_created"] is False
    assert summary["real_code_modified"] is False
    assert summary["git_write_performed"] is False
    assert summary["ai_project_director_total_loop"] == "Partial"
    assert summary["p9_production_safe_long_running_executor_lifecycle"] == "Partial"
    assert summary["isolated_runtime_data"] is True
    assert Path(summary["runtime_data_dir"]) != RUNTIME_DATA_DIR.resolve()
    assert Path(summary["runtime_data_dir"]).exists() is False
    assert summary["sqlite_db_path"].endswith("/db/orchestrator.db")
    assert summary["blocked_reasons"] == []
    assert _walk_keys(summary).isdisjoint(FORBIDDEN_OUTPUT_KEYS)

    dispatch_summary = summary["p13_dispatch_response_summary"]
    assert dispatch_summary["dispatch_status"] == "planned"
    assert dispatch_summary["controlled_executor_pilot"] is True
    assert dispatch_summary["product_runtime_git_write_allowed"] is False
    assert dispatch_summary["worktree_write_allowed"] is False
    assert dispatch_summary["native_executor_started"] is False
    assert dispatch_summary["codex_started"] is False
    assert dispatch_summary["claude_code_started"] is False
    assert dispatch_summary["agent_session_bound"] is False
    assert dispatch_summary["run_created"] is False
    assert dispatch_summary["message_bound"] is True

    forbidden_text = json.dumps(summary, ensure_ascii=False).lower()
    for phrase in (
        "已执行提交",
        "已推送",
        "pr 已创建",
        "代码已写入",
        "已授权 git 写",
        "已启动 codex",
        "已启动 claude",
    ):
        assert phrase not in forbidden_text


def test_p13_controlled_smoke_blocks_without_required_safety_flags() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--json",
            "--launch-mode",
            "controlled_smoke",
        ],
        cwd=RUNTIME_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    summary = json.loads(result.stdout)

    assert result.returncode == 1
    assert summary["smoke_status"] == "blocked"
    assert "enable_native_process_required" in summary["blocked_reasons"]
    assert "auto_terminate_required" in summary["blocked_reasons"]
    assert "positive_timeout_seconds_required" in summary["blocked_reasons"]
    assert "supervisor_required" in summary["blocked_reasons"]
    assert "supervisor_cleanup_after_launch_required" in summary["blocked_reasons"]
    assert summary["native_executor_started"] is False
    assert summary["codex_started"] is False
    assert summary["claude_code_started"] is False
    assert summary["agent_session_bound"] is False
    assert summary["supervisor_registered"] is False
    assert summary["supervisor_cleanup_done"] is False
    assert summary["product_runtime_git_write_allowed"] is False
    assert summary["worktree_write_allowed"] is False
    assert summary["git_write_performed"] is False
    assert _walk_keys(summary).isdisjoint(FORBIDDEN_OUTPUT_KEYS)
