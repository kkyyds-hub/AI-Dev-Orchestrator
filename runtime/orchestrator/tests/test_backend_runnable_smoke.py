"""P9-RUN-A backend runnable smoke contract tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = RUNTIME_ROOT / "scripts" / "p9_run_backend_runnable_smoke.py"
RUNTIME_DATA_DIR = RUNTIME_ROOT / "data"
FORBIDDEN_OUTPUT_KEYS = {
    "api_key",
    "token",
    "secret",
    "raw stdout",
    "raw stderr",
    "pid",
    "raw command",
}


def _relative_files(root: Path) -> set[str]:
    if not root.exists():
        return set()
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


def _run_smoke(*args: str) -> dict[str, Any]:
    env = os.environ.copy()
    env.pop("RUNTIME_DATA_DIR", None)
    env.pop("SQLITE_DB_DIR", None)
    env.pop("SQLITE_DB_PATH", None)
    result = subprocess.run(
        [sys.executable, str(SMOKE_SCRIPT), "--json", *args],
        cwd=RUNTIME_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


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


def test_backend_runnable_smoke_passes_with_isolated_runtime_data() -> None:
    before_files = _relative_files(RUNTIME_DATA_DIR)

    summary = _run_smoke()

    assert summary["smoke_status"] == "passed"
    assert summary["app_import_ok"] is True
    assert summary["database_init_ok"] is True
    assert summary["health_ok"] is True
    assert summary["tasks_list_ok"] is True
    assert summary["task_create_ok"] is True
    assert summary["worker_run_once_ok"] is True
    assert summary["task_detail_ok"] is True
    assert summary["run_created"] is True
    assert summary["isolated_runtime_data"] is True
    assert summary["product_runtime_git_write_allowed"] is False
    assert summary["frontend_required"] is False
    assert summary["native_executor_started"] is False
    assert summary["codex_started"] is False
    assert summary["claude_code_started"] is False
    assert summary["blocked_reasons"] == []
    assert Path(summary["runtime_data_dir"]) != RUNTIME_DATA_DIR.resolve()
    assert Path(summary["runtime_data_dir"]).exists() is False
    assert _relative_files(RUNTIME_DATA_DIR) == before_files
    assert _walk_keys(summary).isdisjoint(FORBIDDEN_OUTPUT_KEYS)


def test_backend_runnable_smoke_can_keep_temp_data(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "kept-runtime"

    summary = _run_smoke("--runtime-dir", str(runtime_dir), "--keep-temp-data")

    assert summary["smoke_status"] == "passed"
    assert summary["isolated_runtime_data"] is True
    assert summary["run_created"] is True
    assert Path(summary["runtime_data_dir"]) == runtime_dir.resolve()
    assert Path(summary["runtime_data_dir"]).exists() is True
    assert Path(summary["sqlite_db_path"]).exists() is True
