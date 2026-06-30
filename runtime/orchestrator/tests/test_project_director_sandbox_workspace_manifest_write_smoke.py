"""Smoke tests for P21-C-D sandbox workspace manifest write script."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    RUNTIME_ROOT / "scripts" / "p21_c_project_director_sandbox_workspace_manifest_write_smoke.py"
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


def test_p21cd_smoke_passes() -> None:
    returncode, summary = _run_script()
    assert returncode == 0
    assert summary["smoke_status"] == "passed"


def test_p21cd_session_created() -> None:
    _returncode, summary = _run_script()
    assert summary["session_created"] is True


def test_p21cd_workspace_guard() -> None:
    _returncode, summary = _run_script()
    assert summary["p21_c_workspace_guard"] == "guarded"


def test_p21cd_operation_manifest_guard() -> None:
    _returncode, summary = _run_script()
    assert summary["p21_c_operation_manifest_guard"] == "manifested"


def test_p21cd_workspace_create() -> None:
    _returncode, summary = _run_script()
    assert summary["p21_c_workspace_create"] in ("created", "already_exists")


def test_p21cd_manifest_write_written() -> None:
    _returncode, summary = _run_script()
    assert summary["p21_c_workspace_manifest_write"] == "written"


def test_p21cd_manifest_write_overwritten() -> None:
    _returncode, summary = _run_script()
    assert summary["p21_c_workspace_manifest_write_second_call"] == "overwritten"


def test_p21cd_blocked_paths() -> None:
    _returncode, summary = _run_script()
    assert summary["p21_c_workspace_manifest_write_user_confirmed_blocked"] == "blocked"
    assert summary["p21_c_workspace_manifest_write_non_creation_source_blocked"] == "blocked"
    assert summary["p21_c_workspace_manifest_write_task_mismatch_blocked"] == "blocked"


def test_p21cd_manifest_file_exists() -> None:
    _returncode, summary = _run_script()
    assert summary["manifest_file_exists"] is True
    assert summary["manifest_json_parseable"] is True
    assert summary["manifest_json_schema_version"] == "p21-c-d.v1"
    assert summary["manifest_json_no_secrets"] is True


def test_p21cd_workspace_no_business_files() -> None:
    _returncode, summary = _run_script()
    assert summary["workspace_has_no_business_files"] is True


def test_p21cd_no_write_boundary() -> None:
    _returncode, summary = _run_script()
    assert summary["manifest_file_written"] is True
    assert summary["manifest_file_overwritten"] is True
    assert summary["business_file_written"] is False
    assert summary["target_file_content_read"] is False
    assert summary["real_diff_generated"] is False
    assert summary["patch_applied"] is False
    assert summary["worktree_created"] is False
    assert summary["rollback_snapshot_created"] is False
    assert summary["git_write_performed"] is False
    assert summary["worker_started"] is False
    assert summary["task_created"] is False
    assert summary["run_created"] is False


def test_p21cd_isolated_runtime_data() -> None:
    _returncode, summary = _run_script()
    assert summary["isolated_runtime_data"] is True
    assert Path(summary["runtime_data_dir"]) != RUNTIME_DATA_DIR.resolve()


def test_p21cd_message_readback() -> None:
    _returncode, summary = _run_script()
    assert summary["p21_c_message_readback"] == "passed"


def test_p21cd_total_loop_partial() -> None:
    _returncode, summary = _run_script()
    assert summary["ai_project_director_total_loop"] == "Partial"


def test_p21cd_output_no_misleading_terms() -> None:
    _returncode, summary = _run_script()
    serialized = json.dumps(summary, ensure_ascii=False)
    for term in [
        "已写入业务文件", "已读取目标文件", "已生成 diff",
        "已应用 patch", "已创建 git worktree", "已提交代码", "已推送",
        "Git 写入已授权", "controlled sandbox write 已启用",
        "automatic commit", "git commit performed",
    ]:
        assert term not in serialized, f"Found misleading term: {term}"
