"""Smoke tests for P20 sandbox write preflight script."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    RUNTIME_ROOT / "scripts" / "p20_project_director_sandbox_write_preflight_smoke.py"
)
RUNTIME_DATA_DIR = RUNTIME_ROOT / "data"
FORBIDDEN_DIFF_PATTERNS = ["diff --git", "+++ b/", "--- a/", "@@", "index "]


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


def test_p20_default_dry_run_smoke_passes() -> None:
    returncode, summary = _run_script()

    assert returncode == 0
    assert summary["smoke_status"] == "passed_dry_run"
    assert summary["preflight_mode"] == "dry_run"
    assert summary["session_created"] is True
    assert summary["p11_dry_run_message_bound"] is True
    assert summary["p12_safe_task_created"] is True
    assert summary["p12_worker_run_once_ok"] is True
    assert summary["p13_dispatch_message_bound"] is True
    assert summary["p14_lifecycle_result_message_bound"] is True
    assert summary["p15_review_message_bound"] is True
    assert summary["p16_plan_message_bound"] is True
    assert summary["p17_execution_message_bound"] is True
    assert summary["p20_preflight_message_bound"] is True
    assert summary["message_readback_ok"] is True
    assert summary["policy_only_preflight"] is True
    assert summary["preflight_status"] == "passed"
    assert summary["checked_operations_count"] >= 1
    assert summary["allowed_operations_count"] >= 1
    assert summary["recommended_next_step_present"] is True
    assert summary["isolated_runtime_data"] is True
    assert Path(summary["runtime_data_dir"]) != RUNTIME_DATA_DIR.resolve()


# ── 2. fake_preflight smoke passes ───────────────────────────────────


def test_p20_fake_preflight_smoke_passes() -> None:
    returncode, summary = _run_script("--preflight-mode", "fake_preflight")

    assert returncode == 0
    assert summary["smoke_status"] == "passed_fake_preflight"
    assert summary["preflight_mode"] == "fake_preflight"
    assert summary["p20_preflight_message_bound"] is True
    assert summary["message_readback_ok"] is True
    assert summary["policy_only_preflight"] is True
    assert summary["preflight_status"] == "passed"


# ── 3. controlled_sandbox_write smoke blocked ────────────────────────


def test_p20_controlled_sandbox_write_smoke_blocked() -> None:
    returncode, summary = _run_script("--preflight-mode", "controlled_sandbox_write")

    assert returncode == 1
    assert summary["smoke_status"] == "blocked"
    assert "controlled_sandbox_write_not_enabled_in_api" in summary["blocked_reasons"]
    assert summary["p20_preflight_message_bound"] is False


# ── 4. output no unsafe diff markers ─────────────────────────────────


def test_p20_output_no_unsafe_diff_markers() -> None:
    _returncode, summary = _run_script()
    serialized = json.dumps(summary, ensure_ascii=False)
    for marker in FORBIDDEN_DIFF_PATTERNS:
        assert marker not in serialized, f"Smoke output contains unsafe diff marker: {marker}"


# ── 5. product Git false ─────────────────────────────────────────────


def test_p20_product_git_false() -> None:
    _returncode, summary = _run_script()
    assert summary["product_runtime_git_write_allowed"] is False


# ── 6. main_worktree false ───────────────────────────────────────────


def test_p20_main_worktree_false() -> None:
    _returncode, summary = _run_script()
    assert summary["main_worktree_write_allowed"] is False


# ── 7. worktree false ────────────────────────────────────────────────


def test_p20_worktree_false() -> None:
    _returncode, summary = _run_script()
    assert summary["worktree_write_allowed"] is False


# ── 8. file_write false ──────────────────────────────────────────────


def test_p20_file_write_false() -> None:
    _returncode, summary = _run_script()
    assert summary["file_write_allowed"] is False


# ── 9. actual_patch_applied=false ────────────────────────────────────


def test_p20_actual_patch_applied_false() -> None:
    _returncode, summary = _run_script()
    assert summary["actual_patch_applied"] is False


# ── 10. no executor start ────────────────────────────────────────────


def test_p20_no_executor_start() -> None:
    _returncode, summary = _run_script()
    assert summary["native_executor_started"] is False
    assert summary["codex_started"] is False
    assert summary["claude_code_started"] is False


# ── 11. no worker/task/run creation by P20 ───────────────────────────


def test_p20_no_worker_task_run_creation() -> None:
    _returncode, summary = _run_script()
    assert summary["worker_started"] is False
    assert summary["task_created"] is False
    assert summary["run_created"] is False


# ── 12. no worktree created ──────────────────────────────────────────


def test_p20_no_worktree_created() -> None:
    _returncode, summary = _run_script()
    assert summary["worktree_created"] is False


# ── 13. no file written ──────────────────────────────────────────────


def test_p20_no_file_written() -> None:
    _returncode, summary = _run_script()
    assert summary["file_written"] is False


# ── 14. message_readback_ok=true ────────────────────────────────────


def test_p20_message_readback_ok() -> None:
    _returncode, summary = _run_script()
    assert summary["p20_preflight_message_bound"] is True
    assert summary["message_readback_ok"] is True


# ── 15. total loop remains Partial ───────────────────────────────────


def test_p20_total_loop_partial() -> None:
    _returncode, summary = _run_script()
    assert summary["ai_project_director_total_loop"] == "Partial"
