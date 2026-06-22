from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    RUNTIME_ROOT / "scripts" / "p12_project_director_dry_run_task_dispatch_smoke.py"
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


def test_p12_project_director_dry_run_task_dispatch_smoke_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--json"],
        cwd=RUNTIME_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    summary = json.loads(result.stdout)

    assert summary["smoke_status"] == "passed"
    assert summary["session_created"] is True
    assert summary["session_id"]
    assert summary["p11_dry_run_message_bound"] is True
    assert summary["dispatch_api_ok"] is True
    assert summary["created_task_id"]
    assert summary["safe_dry_run_task"] is True
    assert summary["worker_run_once_ok"] is True
    assert summary["worker_started"] is True
    assert summary["worker_simulate_mode"] is True
    assert summary["run_created"] is True
    assert summary["run_id"]
    assert summary["task_detail_ok"] is True
    assert summary["run_readback_ok"] is True
    assert summary["session_dispatch_message_bound"] is True
    assert summary["session_worker_result_message_bound"] is True
    assert summary["message_readback_ok"] is True
    assert summary["isolated_runtime_data"] is True
    assert Path(summary["runtime_data_dir"]) != RUNTIME_DATA_DIR.resolve()
    assert Path(summary["runtime_data_dir"]).exists() is False
    assert summary["sqlite_db_path"].endswith("/db/orchestrator.db")
    assert summary["native_executor_started"] is False
    assert summary["codex_started"] is False
    assert summary["claude_code_started"] is False
    assert summary["product_runtime_git_write_allowed"] is False
    assert summary["frontend_required"] is False
    assert summary["ai_project_director_total_loop"] == "Partial"
    assert summary["p9_production_safe_long_running_executor_lifecycle"] == "Partial"
    assert summary["blocked_reasons"] == []
    assert _walk_keys(summary).isdisjoint(FORBIDDEN_OUTPUT_KEYS)

    forbidden_text = json.dumps(summary, ensure_ascii=False)
    for phrase in (
        "已执行提交",
        "已推送",
        "PR 已创建",
        "代码已写入",
        "已授权 Git 写",
        "已启动 Codex",
        "已启动 Claude",
    ):
        assert phrase not in forbidden_text
