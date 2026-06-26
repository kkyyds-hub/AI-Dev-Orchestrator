"""Smoke tests for P17 programmer no-write execution script."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    RUNTIME_ROOT / "scripts" / "p17_project_director_programmer_no_write_execution_smoke.py"
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

FORBIDDEN_DIFF_PATTERNS = ["diff --git", "+++ b/", "--- a/", "@@"]


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


def test_p17_default_dry_run_smoke_passes() -> None:
    returncode, summary = _run_script()

    assert returncode == 0
    assert summary["smoke_status"] == "passed_dry_run"
    assert summary["execution_mode"] == "dry_run"
    assert summary["session_created"] is True
    assert summary["p11_dry_run_message_bound"] is True
    assert summary["p12_safe_task_created"] is True
    assert summary["p12_worker_run_once_ok"] is True
    assert summary["p13_dispatch_message_bound"] is True
    assert summary["p14_lifecycle_result_message_bound"] is True
    assert summary["p15_review_message_bound"] is True
    assert summary["p16_plan_message_bound"] is True
    assert summary["p17_execution_message_bound"] is True
    assert summary["message_readback_ok"] is True
    assert summary["programmer_agent"] is True
    assert summary["controlled_programmer_execution"] is True
    assert summary["no_write_execution"] is True
    assert summary["executor_backed_programmer_allowed"] is True
    assert summary["execution_summary_present"] is True
    assert summary["execution_steps_count"] >= 1
    assert summary["recommended_next_step_present"] is True
    assert summary["product_runtime_git_write_allowed"] is False
    assert summary["worktree_write_allowed"] is False
    assert summary["file_write_allowed"] is False
    assert summary["actual_patch_applied"] is False
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


# ── 2. fake_execution smoke passes ───────────────────────────────────


def test_p17_fake_execution_smoke_passes() -> None:
    returncode, summary = _run_script("--execution-mode", "fake_execution")

    assert returncode == 0
    assert summary["smoke_status"] == "passed_fake_execution"
    assert summary["execution_mode"] == "fake_execution"
    assert summary["p17_execution_message_bound"] is True
    assert summary["message_readback_ok"] is True
    assert summary["execution_steps_count"] >= 2
    assert summary["patch_preview_count"] >= 1
    assert summary["implementation_notes_count"] >= 1
    assert summary["handoff_notes_count"] >= 1
    assert len(summary["risks"]) >= 1
    assert summary["product_runtime_git_write_allowed"] is False
    assert summary["worktree_write_allowed"] is False
    assert summary["file_write_allowed"] is False
    assert summary["actual_patch_applied"] is False


# ── 3. controlled_no_write smoke blocked ─────────────────────────────


def test_p17_controlled_no_write_smoke_blocked() -> None:
    returncode, summary = _run_script("--execution-mode", "controlled_no_write")

    assert returncode == 1
    assert summary["smoke_status"] == "blocked"
    assert "controlled_no_write_not_enabled_in_api" in summary["blocked_reasons"]
    assert summary["p17_execution_message_bound"] is False
    assert summary["native_executor_started"] is False
    assert summary["codex_started"] is False
    assert summary["claude_code_started"] is False


# ── 4. output no sensitive fields ────────────────────────────────────


def test_p17_output_excludes_sensitive_fields() -> None:
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
        "代码已修改",
    }:
        assert forbidden_text not in serialized


# ── 5-7. safety flags remain false ───────────────────────────────────


def test_p17_safety_flags_false() -> None:
    _returncode, summary = _run_script()

    assert summary["product_runtime_git_write_allowed"] is False
    assert summary["worktree_write_allowed"] is False
    assert summary["file_write_allowed"] is False
    assert summary["real_code_modified"] is False
    assert summary["git_write_performed"] is False


# ── 8. actual_patch_applied=false ────────────────────────────────────


def test_p17_actual_patch_applied_false() -> None:
    _returncode, summary = _run_script()
    assert summary["actual_patch_applied"] is False


# ── 9. no executor start ────────────────────────────────────────────


def test_p17_no_executor_start() -> None:
    _returncode, summary = _run_script()

    assert summary["native_executor_started"] is False
    assert summary["codex_started"] is False
    assert summary["claude_code_started"] is False


# ── 10. no worker/task/run creation by P17 ───────────────────────────


def test_p17_no_worker_task_run_creation() -> None:
    _returncode, summary = _run_script()

    assert summary["worker_started"] is False
    assert summary["task_created"] is False
    assert summary["run_created"] is False


# ── 11. patch_preview is preview-only ────────────────────────────────


def test_p17_patch_preview_is_preview_only() -> None:
    _returncode, summary = _run_script("--execution-mode", "fake_execution")

    assert summary["actual_patch_applied"] is False
    assert summary["git_write_performed"] is False

    # P18: verify smoke JSON output does not contain applyable diff markers
    serialized = json.dumps(summary, ensure_ascii=False)
    for marker in FORBIDDEN_DIFF_PATTERNS:
        assert marker not in serialized, (
            f"Smoke output contains unsafe diff marker: {marker}"
        )


# ── 12. message_readback_ok=true ────────────────────────────────────


def test_p17_message_readback_ok() -> None:
    _returncode, summary = _run_script()

    assert summary["p17_execution_message_bound"] is True
    assert summary["message_readback_ok"] is True
