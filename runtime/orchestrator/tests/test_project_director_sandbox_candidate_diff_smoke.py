"""Smoke tests for P21-C-F sandbox candidate diff generation script."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    RUNTIME_ROOT / "scripts" / "p21_c_project_director_sandbox_candidate_diff_smoke.py"
)


def _run_script(*args: str) -> tuple[int, dict[str, Any]]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--json", *args],
        cwd=RUNTIME_ROOT, check=False, capture_output=True, text=True,
    )
    return result.returncode, json.loads(result.stdout)


def test_p21cf_smoke_passes() -> None:
    rc, summary = _run_script()
    assert rc == 0
    assert summary["smoke_status"] == "passed"


def test_p21cf_diff_generated() -> None:
    _, summary = _run_script()
    assert summary["p21_c_candidate_diff_generate"] == "generated"


def test_p21cf_unified_diff_returned() -> None:
    _, summary = _run_script()
    assert summary["unified_diff_returned"] is True


def test_p21cf_no_diff_file_written() -> None:
    _, summary = _run_script()
    assert summary["diff_file_written"] is False


def test_p21cf_no_main_project_write() -> None:
    _, summary = _run_script()
    assert summary["main_project_file_written"] is False
    assert summary["sandbox_file_written"] is False
    assert summary["manifest_file_written"] is False


def test_p21cf_candidate_file_unchanged() -> None:
    _, summary = _run_script()
    assert summary["candidate_file_exists"] is True
    assert summary["candidate_file_content_unchanged"] is True


def test_p21cf_internal_manifest_unchanged() -> None:
    _, summary = _run_script()
    assert summary["internal_manifest_file_exists"] is True


def test_p21cf_blocked_paths() -> None:
    _, summary = _run_script()
    assert summary["p21_c_candidate_diff_user_confirmed_blocked"] == "blocked"
    assert summary["p21_c_candidate_diff_non_candidate_write_source_blocked"] == "blocked"
    assert summary["p21_c_candidate_diff_task_mismatch_blocked"] == "blocked"
    assert summary["p21_c_candidate_diff_too_large_blocked"] == "blocked"


def test_p21cf_no_write_flags() -> None:
    _, summary = _run_script()
    assert summary["readonly_real_diff_generated"] is True
    assert summary["real_diff_generated"] is True
    assert summary["target_file_content_read"] is True  # service sets to generated; per-entry is False for create
    assert summary["candidate_file_content_read"] is True
    assert summary["patch_applied"] is False
    assert summary["worktree_created"] is False
    assert summary["git_write_performed"] is False
    assert summary["worker_started"] is False
    assert summary["task_created"] is False
    assert summary["run_created"] is False


def test_p21cf_isolated_runtime() -> None:
    _, summary = _run_script()
    assert summary["isolated_runtime_data"] is True


def test_p21cf_message_readback() -> None:
    _, summary = _run_script()
    assert summary["p21_c_message_readback"] == "passed"


def test_p21cf_total_loop_partial() -> None:
    _, summary = _run_script()
    assert summary["ai_project_director_total_loop"] == "Partial"


def test_p21cf_no_misleading_terms() -> None:
    _, summary = _run_script()
    serialized = json.dumps(summary, ensure_ascii=False)
    for term in [
        "已写主项目文件", "已写 sandbox 文件", "已写 manifest 文件",
        "已写 diff 文件", "已应用 patch", "已创建 git worktree",
        "已提交代码", "已推送", "Git 写入已授权",
        "automatic commit", "git commit performed",
    ]:
        assert term not in serialized, f"Found misleading term: {term}"
