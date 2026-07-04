"""Smoke tests for P21-C-G sandbox diff review handoff script."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    RUNTIME_ROOT / "scripts" / "p21_c_project_director_sandbox_candidate_diff_review_handoff_smoke.py"
)


def _run(*args: str) -> tuple[int, dict[str, Any]]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--json", *args],
        cwd=RUNTIME_ROOT, check=False, capture_output=True, text=True,
    )
    return result.returncode, json.loads(result.stdout)


def test_smoke_passes() -> None:
    rc, s = _run()
    assert rc == 0
    assert s["smoke_status"] == "passed"


def test_handoff_created() -> None:
    _, s = _run()
    assert s["p21_c_candidate_diff_review_handoff"] == "created"


def test_sha256() -> None:
    _, s = _run()
    assert len(s["source_diff_sha256"]) == 64
    assert s["source_diff_sha256_length"] == 64


def test_review_scope_paths() -> None:
    _, s = _run()
    assert len(s["review_scope_paths"]) >= 1


def test_no_reviewer() -> None:
    _, s = _run()
    assert s["reviewer_started"] is False
    assert s["review_executed"] is False
    assert s["review_findings_generated"] is False
    assert s["review_verdict_generated"] is False


def test_no_write() -> None:
    _, s = _run()
    assert s["main_project_file_written"] is False
    assert s["sandbox_file_written"] is False
    assert s["manifest_file_written"] is False
    assert s["diff_file_written"] is False
    assert s["patch_applied"] is False
    assert s["worktree_created"] is False
    assert s["git_write_performed"] is False
    assert s["native_executor_started"] is False
    assert s["codex_started"] is False
    assert s["claude_code_started"] is False
    assert s["worker_started"] is False
    assert s["task_created"] is False
    assert s["run_created"] is False


def test_blocked_paths() -> None:
    _, s = _run()
    assert s["p21_c_handoff_user_confirmed_blocked"] == "blocked"
    assert s["p21_c_handoff_non_diff_source_blocked"] == "blocked"
    assert s["p21_c_handoff_task_mismatch_blocked"] == "blocked"


def test_message_readback() -> None:
    _, s = _run()
    assert s["p21_c_message_readback"] == "passed"


def test_isolated() -> None:
    _, s = _run()
    assert s["isolated_runtime_data"] is True


def test_total_loop() -> None:
    _, s = _run()
    assert s["ai_project_director_total_loop"] == "Partial"


def test_no_misleading() -> None:
    _, s = _run()
    serialized = json.dumps(s, ensure_ascii=False)
    for term in [
        "审查通过", "review passed", "已批准", "可以合入", "可以提交",
        "代码正确", "无风险", "reviewer 已启动", "review 已执行",
        "findings 已生成", "verdict 已生成", "已应用 patch",
        "已创建 worktree", "已执行 Git 写",
    ]:
        assert term not in serialized, f"Found misleading term: {term}"
