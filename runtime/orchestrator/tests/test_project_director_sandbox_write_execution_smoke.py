"""Smoke tests for P21-A sandbox write execution script."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    RUNTIME_ROOT / "scripts" / "p21_project_director_sandbox_write_execution_smoke.py"
)
RUNTIME_DATA_DIR = RUNTIME_ROOT / "data"


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


def test_p21_default_dry_run_smoke_passes() -> None:
    returncode, summary = _run_script()

    assert returncode == 0
    assert summary["smoke_status"] == "passed_dry_run"
    assert summary["session_created"] is True
    assert summary["p20_preflight_passed"] is True
    assert summary["p20_preflight_message_bound"] is True
    assert summary["p21_dry_run"] == "passed_planned"
    assert summary["p21_execution_status"] == "planned"
    assert summary["p21_execution_message_bound"] is True
    assert summary["p21_checked_operations_count"] >= 1
    assert summary["p21_operation_results_count"] >= 1
    assert summary["isolated_runtime_data"] is True
    assert Path(summary["runtime_data_dir"]) != RUNTIME_DATA_DIR.resolve()


# ── 2. fake_write smoke passes ───────────────────────────────────────


def test_p21_fake_write_smoke_passes() -> None:
    returncode, summary = _run_script("--execution-mode", "fake_write")

    assert returncode == 0
    assert summary["smoke_status"] == "passed_fake_write"
    assert summary["p21_fake_write"] == "passed_simulated"
    assert summary["p21_execution_status"] == "simulated"
    assert summary["p21_execution_message_bound"] is True
    assert summary["p21_operation_results_count"] >= 1


# ── 3. controlled_sandbox_write smoke blocked ────────────────────────


def test_p21_controlled_sandbox_write_smoke_blocked() -> None:
    returncode, summary = _run_script("--execution-mode", "controlled_sandbox_write")

    assert returncode == 1
    assert summary["smoke_status"] == "blocked"
    assert "controlled_sandbox_write_not_enabled_in_api" in summary["blocked_reasons"]


# ── 4. output no unsafe diff markers ─────────────────────────────────


def test_p21_output_no_unsafe_diff_markers() -> None:
    _returncode, summary = _run_script()
    serialized = json.dumps(summary, ensure_ascii=False)
    for marker in ["diff --git", "+++ b/", "--- a/", "@@", "index "]:
        assert marker not in serialized


# ── 5. product Git false ─────────────────────────────────────────────


def test_p21_product_git_false() -> None:
    _returncode, summary = _run_script()
    assert summary["product_runtime_git_write_allowed"] is False


# ── 6. main_worktree false ───────────────────────────────────────────


def test_p21_main_worktree_false() -> None:
    _returncode, summary = _run_script()
    assert summary["main_worktree_write_allowed"] is False


# ── 7. worktree false ────────────────────────────────────────────────


def test_p21_worktree_false() -> None:
    _returncode, summary = _run_script()
    assert summary["worktree_write_allowed"] is False


# ── 8. file_write false ──────────────────────────────────────────────


def test_p21_file_write_false() -> None:
    _returncode, summary = _run_script()
    assert summary["file_write_allowed"] is False


# ── 9. actual_patch_applied=false ────────────────────────────────────


def test_p21_actual_patch_applied_false() -> None:
    _returncode, summary = _run_script()
    assert summary["actual_patch_applied"] is False


# ── 10. no executor start ────────────────────────────────────────────


def test_p21_no_executor_start() -> None:
    _returncode, summary = _run_script()
    assert summary["native_executor_started"] is False
    assert summary["codex_started"] is False
    assert summary["claude_code_started"] is False


# ── 11. no worker/task/run creation by P21 ───────────────────────────


def test_p21_no_worker_task_run_creation() -> None:
    _returncode, summary = _run_script()
    assert summary["worker_started"] is False
    assert summary["task_created"] is False
    assert summary["run_created"] is False


# ── 12. no worktree created ──────────────────────────────────────────


def test_p21_no_worktree_created() -> None:
    _returncode, summary = _run_script()
    assert summary["worktree_created"] is False


# ── 13. no file written ──────────────────────────────────────────────


def test_p21_no_file_written() -> None:
    _returncode, summary = _run_script()
    assert summary["file_written"] is False


# ── 14. message_readback_ok ──────────────────────────────────────────


def test_p21_message_readback_ok() -> None:
    _returncode, summary = _run_script()
    assert summary["p21_execution_message_bound"] is True
    assert summary["p21_message_readback"] == "passed"


# ── 15. total loop remains Partial ───────────────────────────────────


def test_p21_total_loop_partial() -> None:
    _returncode, summary = _run_script()
    assert summary["ai_project_director_total_loop"] == "Partial"


# ── 16. blocked preflight cannot enter P21 ───────────────────────────


def test_p21_blocked_preflight_blocked() -> None:
    _returncode, summary = _run_script()
    assert summary["p21_blocked_preflight"] == "blocked"


# ── 17. source_task/message mismatch blocked ─────────────────────────


def test_p21_source_task_message_mismatch_blocked() -> None:
    _returncode, summary = _run_script()
    assert summary["p21_source_task_message_mismatch"] == "blocked"


# ── 18. controlled_sandbox_write blocked ─────────────────────────────


def test_p21_controlled_sandbox_write_blocked() -> None:
    _returncode, summary = _run_script()
    assert summary["p21_controlled_sandbox_write"] == "blocked"


# ── 19. no_write_boundary passed ─────────────────────────────────────


def test_p21_no_write_boundary_passed() -> None:
    _returncode, summary = _run_script()
    assert summary["no_write_boundary"] == "passed"
