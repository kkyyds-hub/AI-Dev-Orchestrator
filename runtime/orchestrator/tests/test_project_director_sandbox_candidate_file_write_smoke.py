"""Smoke tests for P21-C-E sandbox candidate file write script."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    RUNTIME_ROOT / "scripts" / "p21_c_project_director_sandbox_candidate_file_write_smoke.py"
)


def _run_script(*args: str) -> tuple[int, dict[str, Any]]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--json", *args],
        cwd=RUNTIME_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode, json.loads(result.stdout)


def test_p21ce_smoke_passes() -> None:
    returncode, summary = _run_script()
    assert returncode == 0
    assert summary["smoke_status"] == "passed"


def test_p21ce_session_created() -> None:
    _, summary = _run_script()
    assert summary["session_created"] is True


def test_p21ce_candidate_write_written() -> None:
    _, summary = _run_script()
    assert summary["p21_c_candidate_files_write"] == "written"


def test_p21ce_candidate_file_exists() -> None:
    _, summary = _run_script()
    assert summary["candidate_file_exists"] is True


def test_p21ce_candidate_file_content_matches() -> None:
    _, summary = _run_script()
    assert summary["candidate_file_content_matches"] is True


def test_p21ce_candidate_file_within_workspace() -> None:
    _, summary = _run_script()
    assert summary["candidate_file_within_workspace"] is True


def test_p21ce_candidate_file_not_under_internal_dir() -> None:
    _, summary = _run_script()
    assert summary["candidate_file_not_under_internal_dir"] is True


def test_p21ce_internal_manifest_still_exists() -> None:
    _, summary = _run_script()
    assert summary["internal_manifest_file_exists"] is True


def test_p21ce_blocked_paths() -> None:
    _, summary = _run_script()
    assert summary["p21_c_candidate_files_write_user_confirmed_blocked"] == "blocked"
    assert summary["p21_c_candidate_files_write_non_manifest_write_source_blocked"] == "blocked"
    assert summary["p21_c_candidate_files_write_task_mismatch_blocked"] == "blocked"
    assert summary["p21_c_candidate_files_write_path_not_declared_blocked"] == "blocked"
    assert summary["p21_c_candidate_files_write_internal_dir_blocked"] == "blocked"


def test_p21ce_no_write_boundary() -> None:
    _, summary = _run_script()
    assert summary["candidate_business_files_written"] is True
    assert summary["business_file_written"] is True
    assert summary["manifest_file_written"] is False
    assert summary["target_file_content_read"] is False
    assert summary["real_diff_generated"] is False
    assert summary["patch_applied"] is False
    assert summary["worktree_created"] is False
    assert summary["git_write_performed"] is False
    assert summary["worker_started"] is False
    assert summary["task_created"] is False
    assert summary["run_created"] is False


def test_p21ce_isolated_runtime() -> None:
    _, summary = _run_script()
    assert summary["isolated_runtime_data"] is True


def test_p21ce_message_readback() -> None:
    _, summary = _run_script()
    assert summary["p21_c_message_readback"] == "passed"


def test_p21ce_total_loop_partial() -> None:
    _, summary = _run_script()
    assert summary["ai_project_director_total_loop"] == "Partial"


def test_p21ce_output_no_misleading_terms() -> None:
    _, summary = _run_script()
    serialized = json.dumps(summary, ensure_ascii=False)
    for term in [
        "已写主项目文件", "已读取目标文件", "已生成 diff",
        "已应用 patch", "已创建 git worktree", "已提交代码", "已推送",
        "Git 写入已授权", "controlled sandbox write 已启用",
        "automatic commit", "git commit performed",
    ]:
        assert term not in serialized, f"Found misleading term: {term}"
