"""Smoke tests for P16 programmer no-write plan script."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    RUNTIME_ROOT / "scripts" / "p16_project_director_programmer_no_write_plan_smoke.py"
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


# ── 1. default dry_run smoke passes ──────────────────────────────────


def test_p16_default_dry_run_smoke_passes() -> None:
    returncode, summary = _run_script()

    assert returncode == 0
    assert summary["smoke_status"] == "passed_dry_run"
    assert summary["planning_mode"] == "dry_run"
    assert summary["session_created"] is True
    assert summary["p11_dry_run_message_bound"] is True
    assert summary["p12_safe_task_created"] is True
    assert summary["p12_worker_run_once_ok"] is True
    assert summary["p13_dispatch_message_bound"] is True
    assert summary["p14_lifecycle_result_message_bound"] is True
    assert summary["p15_review_message_bound"] is True
    assert summary["p16_plan_message_bound"] is True
    assert summary["message_readback_ok"] is True
    assert summary["programmer_agent"] is True
    assert summary["controlled_programmer_planning"] is True
    assert summary["no_write_plan"] is True
    assert summary["executor_backed_programmer_allowed"] is True
    assert summary["implementation_summary_present"] is True
    assert summary["planned_steps_count"] >= 1
    assert summary["recommended_next_step_present"] is True
    assert summary["product_runtime_git_write_allowed"] is False
    assert summary["worktree_write_allowed"] is False
    assert summary["file_write_allowed"] is False
    assert summary["real_code_modified"] is False
    assert summary["git_write_performed"] is False
    assert summary["native_executor_started"] is False
    assert summary["codex_started"] is False
    assert summary["claude_code_started"] is False
    assert summary["worker_started"] is False
    assert summary["task_created"] is False
    assert summary["run_created"] is False
    assert summary["ai_project_director_total_loop"] == "Partial"
    assert summary["isolated_runtime_data"] is True
    assert Path(summary["runtime_data_dir"]) != RUNTIME_DATA_DIR.resolve()


# ── 2. fake_plan smoke passes ────────────────────────────────────────


def test_p16_fake_plan_smoke_passes() -> None:
    returncode, summary = _run_script("--planning-mode", "fake_plan")

    assert returncode == 0
    assert summary["smoke_status"] == "passed_fake_plan"
    assert summary["planning_mode"] == "fake_plan"
    assert summary["p16_plan_message_bound"] is True
    assert summary["message_readback_ok"] is True
    assert summary["planned_steps_count"] >= 2
    # In fake_plan mode, fallback targeted tests are added to individual steps
    # even when the source task has no test-related acceptance criteria.
    # The result-level required_targeted_tests_count may be 0 in that case.
    assert len(summary["risks"]) >= 1
    assert summary["product_runtime_git_write_allowed"] is False
    assert summary["worktree_write_allowed"] is False
    assert summary["file_write_allowed"] is False


# ── 3. controlled_no_write smoke blocked ─────────────────────────────


def test_p16_controlled_no_write_smoke_blocked() -> None:
    returncode, summary = _run_script("--planning-mode", "controlled_no_write")

    assert returncode == 1
    assert summary["smoke_status"] == "blocked"
    assert "controlled_no_write_not_enabled_in_api" in summary["blocked_reasons"]
    assert summary["p16_plan_message_bound"] is False
    assert summary["native_executor_started"] is False
    assert summary["codex_started"] is False
    assert summary["claude_code_started"] is False


# ── 4. output no sensitive fields ────────────────────────────────────


def test_p16_output_excludes_sensitive_fields() -> None:
    _returncode, summary = _run_script()
    serialized = json.dumps(summary, ensure_ascii=False).lower()

    for forbidden in FORBIDDEN_OUTPUT_KEYS:
        assert forbidden not in serialized, f"Found forbidden key: {forbidden}"
    for forbidden_text in {
        "raw_command",
        "raw_stdout",
        "raw_stderr",
        "已授权 git 写",
        "代码已写入",
    }:
        assert forbidden_text not in serialized


# ── 5-7. safety flags remain false ───────────────────────────────────


def test_p16_safety_flags_false() -> None:
    _returncode, summary = _run_script()

    assert summary["product_runtime_git_write_allowed"] is False
    assert summary["worktree_write_allowed"] is False
    assert summary["file_write_allowed"] is False
    assert summary["real_code_modified"] is False
    assert summary["git_write_performed"] is False


# ── 8. no executor start ────────────────────────────────────────────


def test_p16_no_executor_start() -> None:
    _returncode, summary = _run_script()

    assert summary["native_executor_started"] is False
    assert summary["codex_started"] is False
    assert summary["claude_code_started"] is False


# ── 9. no worker/task/run creation by P16 ────────────────────────────


def test_p16_no_worker_task_run_creation() -> None:
    _returncode, summary = _run_script()

    assert summary["worker_started"] is False
    assert summary["task_created"] is False
    assert summary["run_created"] is False


# ── 10. message_readback_ok=true ────────────────────────────────────


def test_p16_message_readback_ok() -> None:
    _returncode, summary = _run_script()

    assert summary["p16_plan_message_bound"] is True
    assert summary["message_readback_ok"] is True
