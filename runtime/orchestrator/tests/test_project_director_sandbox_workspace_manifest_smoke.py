"""Smoke tests for P21-C sandbox workspace manifest script."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    RUNTIME_ROOT / "scripts" / "p21_c_project_director_sandbox_workspace_manifest_smoke.py"
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


# ── 1. workspace guard passes ────────────────────────────────────────


def test_p21c_workspace_guard_passes() -> None:
    returncode, summary = _run_script()

    assert returncode == 0
    assert summary["smoke_status"] == "passed"
    assert summary["session_created"] is True
    assert summary["p21_c_workspace_guard"] == "guarded"
    assert summary["isolated_runtime_data"] is True
    assert Path(summary["runtime_data_dir"]) != RUNTIME_DATA_DIR.resolve()


# ── 2. operation manifest guard passes ───────────────────────────────


def test_p21c_operation_manifest_guard_passes() -> None:
    _returncode, summary = _run_script()
    assert summary["p21_c_operation_manifest_guard"] == "manifested"


# ── 3. blocked paths ─────────────────────────────────────────────────


def test_p21c_blocked_paths() -> None:
    _returncode, summary = _run_script()
    assert summary["p21_c_workspace_user_confirmed_blocked"] == "blocked"
    assert summary["p21_c_workspace_invalid_name_blocked"] == "blocked"
    assert summary["p21_c_manifest_non_p21c_source_blocked"] == "blocked"


# ── 4. no-write boundary ─────────────────────────────────────────────


def test_p21c_no_write_boundary() -> None:
    _returncode, summary = _run_script()
    assert summary["workspace_created"] is False
    assert summary["workspace_written"] is False
    assert summary["file_written"] is False
    assert summary["target_file_content_read"] is False
    assert summary["real_diff_generated"] is False
    assert summary["patch_applied"] is False
    assert summary["worktree_created"] is False
    assert summary["rollback_snapshot_created"] is False
    assert summary["git_write_performed"] is False
    assert summary["worker_started"] is False
    assert summary["task_created"] is False
    assert summary["run_created"] is False


# ── 5. message readback ──────────────────────────────────────────────


def test_p21c_message_readback() -> None:
    _returncode, summary = _run_script()
    assert summary["p21_c_message_readback"] == "passed"


# ── 6. total loop Partial ────────────────────────────────────────────


def test_p21c_total_loop_partial() -> None:
    _returncode, summary = _run_script()
    assert summary["ai_project_director_total_loop"] == "Partial"


# ── 7. output no misleading terms ────────────────────────────────────


def test_p21c_output_no_misleading_terms() -> None:
    _returncode, summary = _run_script()
    serialized = json.dumps(summary, ensure_ascii=False)
    for term in [
        "已创建目录", "已写入文件", "已读取目标文件", "已生成 diff",
        "已应用 patch", "已创建 worktree", "已提交代码", "已推送",
        "Git 写入已授权", "controlled sandbox write 已启用",
        "automatic commit", "git commit performed",
    ]:
        assert term not in serialized, f"Found misleading term: {term}"
