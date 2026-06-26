from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    RUNTIME_ROOT / "scripts" / "p15_project_director_readonly_reviewer_smoke.py"
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


def _assert_blocked_without_launch(summary: dict[str, Any]) -> None:
    assert summary["smoke_status"] == "blocked"
    assert summary["native_executor_started"] is False
    assert summary["codex_started"] is False
    assert summary["claude_code_started"] is False
    assert summary["agent_session_bound"] is False
    assert summary["supervisor_registered"] is False
    assert summary["terminate_attempted"] is False
    assert summary["supervisor_cleanup_done"] is False
    assert summary["product_runtime_git_write_allowed"] is False
    assert summary["worktree_write_allowed"] is False
    assert summary["file_write_allowed"] is False
    assert summary["real_code_modified"] is False
    assert summary["git_write_performed"] is False
    assert _walk_keys(summary).isdisjoint(FORBIDDEN_OUTPUT_KEYS)


def test_p15_default_dry_run_smoke_passes() -> None:
    returncode, summary = _run_script()

    assert returncode == 0
    assert summary["smoke_status"] == "passed_dry_run"
    assert summary["review_mode"] == "dry_run"
    assert summary["session_created"] is True
    assert summary["p11_dry_run_message_bound"] is True
    assert summary["p12_safe_task_created"] is True
    assert summary["p12_worker_run_once_ok"] is True
    assert summary["p13_dispatch_message_bound"] is True
    assert summary["p14_lifecycle_result_message_bound"] is True
    assert summary["p15_review_message_bound"] is True
    assert summary["message_readback_ok"] is True
    assert summary["readonly_review"] is True
    assert summary["reviewer_agent"] is True
    assert summary["executor_backed_review_allowed"] is True
    assert summary["native_executor_started"] is False
    assert summary["codex_started"] is False
    assert summary["claude_code_started"] is False
    assert summary["review_result_created"] is True
    assert summary["review_summary_present"] is True
    assert summary["recommended_next_step_present"] is True
    assert summary["product_runtime_git_write_allowed"] is False
    assert summary["worktree_write_allowed"] is False
    assert summary["file_write_allowed"] is False
    assert summary["real_code_modified"] is False
    assert summary["git_write_performed"] is False
    assert summary["ai_project_director_total_loop"] == "Partial"
    assert Path(summary["runtime_data_dir"]) != RUNTIME_DATA_DIR.resolve()
    assert _walk_keys(summary).isdisjoint(FORBIDDEN_OUTPUT_KEYS)


def test_p15_fake_review_smoke_passes_and_generates_findings() -> None:
    returncode, summary = _run_script("--review-mode", "fake_review")

    assert returncode == 0
    assert summary["smoke_status"] == "passed_fake_review"
    assert summary["review_mode"] == "fake_review"
    assert summary["p15_review_message_bound"] is True
    assert summary["message_readback_ok"] is True
    assert summary["review_result_created"] is True
    assert summary["review_findings_count"] == 1
    assert summary["review_summary_present"] is True
    assert summary["native_executor_started"] is False
    assert summary["codex_started"] is False
    assert summary["claude_code_started"] is False
    assert summary["product_runtime_git_write_allowed"] is False
    assert summary["worktree_write_allowed"] is False
    assert summary["file_write_allowed"] is False
    assert summary["real_code_modified"] is False
    assert summary["git_write_performed"] is False
    assert _walk_keys(summary).isdisjoint(FORBIDDEN_OUTPUT_KEYS)


def test_p15_controlled_review_missing_enable_native_process_blocks() -> None:
    returncode, summary = _run_script(
        "--review-mode",
        "controlled_review",
        "--auto-terminate",
        "--timeout-seconds",
        "2",
        "--use-supervisor",
        "--supervisor-cleanup-after-launch",
        "--readonly-output-dir",
        "/tmp/p15-readonly-review-output",
    )

    assert returncode == 1
    assert "enable_native_process_required" in summary["blocked_reasons"]
    _assert_blocked_without_launch(summary)


def test_p15_controlled_review_missing_auto_terminate_blocks() -> None:
    returncode, summary = _run_script(
        "--review-mode",
        "controlled_review",
        "--enable-native-process",
        "--timeout-seconds",
        "2",
        "--use-supervisor",
        "--supervisor-cleanup-after-launch",
        "--readonly-output-dir",
        "/tmp/p15-readonly-review-output",
    )

    assert returncode == 1
    assert "auto_terminate_required" in summary["blocked_reasons"]
    _assert_blocked_without_launch(summary)


def test_p15_controlled_review_missing_timeout_blocks() -> None:
    returncode, summary = _run_script(
        "--review-mode",
        "controlled_review",
        "--enable-native-process",
        "--auto-terminate",
        "--use-supervisor",
        "--supervisor-cleanup-after-launch",
        "--readonly-output-dir",
        "/tmp/p15-readonly-review-output",
    )

    assert returncode == 1
    assert "positive_timeout_seconds_required" in summary["blocked_reasons"]
    _assert_blocked_without_launch(summary)


def test_p15_controlled_review_missing_supervisor_blocks() -> None:
    returncode, summary = _run_script(
        "--review-mode",
        "controlled_review",
        "--enable-native-process",
        "--auto-terminate",
        "--timeout-seconds",
        "2",
        "--supervisor-cleanup-after-launch",
        "--readonly-output-dir",
        "/tmp/p15-readonly-review-output",
    )

    assert returncode == 1
    assert "supervisor_required" in summary["blocked_reasons"]
    _assert_blocked_without_launch(summary)


def test_p15_controlled_review_missing_cleanup_blocks() -> None:
    returncode, summary = _run_script(
        "--review-mode",
        "controlled_review",
        "--enable-native-process",
        "--auto-terminate",
        "--timeout-seconds",
        "2",
        "--use-supervisor",
        "--readonly-output-dir",
        "/tmp/p15-readonly-review-output",
    )

    assert returncode == 1
    assert "supervisor_cleanup_after_launch_required" in summary["blocked_reasons"]
    _assert_blocked_without_launch(summary)


def test_p15_controlled_review_missing_readonly_output_dir_blocks() -> None:
    returncode, summary = _run_script(
        "--review-mode",
        "controlled_review",
        "--enable-native-process",
        "--auto-terminate",
        "--timeout-seconds",
        "2",
        "--use-supervisor",
        "--supervisor-cleanup-after-launch",
    )

    assert returncode == 1
    assert "readonly_output_dir_required" in summary["blocked_reasons"]
    _assert_blocked_without_launch(summary)


def test_p15_output_does_not_contain_sensitive_payload_text() -> None:
    _returncode, summary = _run_script("--review-mode", "controlled_review")
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
