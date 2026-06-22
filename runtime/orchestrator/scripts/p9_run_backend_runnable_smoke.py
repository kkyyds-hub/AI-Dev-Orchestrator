"""P9-RUN-A backend runnable baseline smoke.

This script proves the basic FastAPI product path with isolated runtime data:
import app, initialize SQLite, call health/tasks APIs, run one simulate worker
cycle, and read persisted task/run data back through APIs.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any
import warnings


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_DATA_DIR = (RUNTIME_ROOT / "data").resolve()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON summary.")
    parser.add_argument(
        "--keep-temp-data",
        action="store_true",
        help="Keep the isolated runtime data directory after the smoke finishes.",
    )
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        help="Use this isolated runtime data directory instead of a temp directory.",
    )
    return parser.parse_args()


def _base_summary(runtime_data_dir: Path, sqlite_db_path: Path) -> dict[str, Any]:
    return {
        "smoke_status": "failed",
        "app_import_ok": False,
        "database_init_ok": False,
        "health_ok": False,
        "tasks_list_ok": False,
        "task_create_ok": False,
        "worker_run_once_ok": False,
        "task_detail_ok": False,
        "run_created": False,
        "isolated_runtime_data": False,
        "runtime_data_dir": str(runtime_data_dir),
        "sqlite_db_path": str(sqlite_db_path),
        "product_runtime_git_write_allowed": False,
        "frontend_required": False,
        "native_executor_started": False,
        "codex_started": False,
        "claude_code_started": False,
        "blocked_reasons": [],
    }


def _configure_isolated_environment(runtime_data_dir: Path) -> Path:
    sqlite_db_path = runtime_data_dir / "db" / "orchestrator.db"
    os.environ["RUNTIME_DATA_DIR"] = str(runtime_data_dir)
    os.environ["SQLITE_DB_PATH"] = str(sqlite_db_path)
    os.environ["WORKER_SIMULATE_EXECUTION_OVERRIDE"] = "true"
    os.environ.pop("OPENAI_API_KEY", None)
    return sqlite_db_path


def _request_json(
    client: Any,
    method: str,
    path: str,
    expected_status: int,
    **kwargs: Any,
) -> dict[str, Any] | list[Any]:
    response = getattr(client, method.lower())(path, **kwargs)
    if response.status_code != expected_status:
        raise RuntimeError(f"{method} {path} returned HTTP {response.status_code}")
    return response.json()


def run_smoke(runtime_data_dir: Path) -> dict[str, Any]:
    sqlite_db_path = _configure_isolated_environment(runtime_data_dir)
    summary = _base_summary(runtime_data_dir.resolve(), sqlite_db_path.resolve())
    summary["isolated_runtime_data"] = runtime_data_dir.resolve() != DEFAULT_RUNTIME_DATA_DIR

    if not summary["isolated_runtime_data"]:
        summary["smoke_status"] = "blocked"
        summary["blocked_reasons"].append("runtime_data_dir_must_be_isolated")
        return summary

    try:
        warnings.filterwarnings(
            "ignore",
            message="Using `httpx` with `starlette.testclient` is deprecated.*",
            category=Warning,
        )
        from fastapi.testclient import TestClient

        from app.main import app

        summary["app_import_ok"] = True

        with TestClient(app) as client:
            summary["database_init_ok"] = sqlite_db_path.exists()

            health = _request_json(client, "GET", "/health", 200)
            summary["health_ok"] = health.get("status") == "ok"

            tasks = _request_json(client, "GET", "/tasks", 200)
            summary["tasks_list_ok"] = isinstance(tasks, list)

            task = _request_json(
                client,
                "POST",
                "/tasks",
                201,
                json={
                    "title": "P9-RUN-A backend runnable smoke",
                    "input_summary": "simulate: prove backend runnable baseline without native executor",
                    "priority": "normal",
                    "acceptance_criteria": [
                        "GET /health works",
                        "POST /workers/run-once creates a run",
                    ],
                    "risk_level": "low",
                },
            )
            task_id = task["id"]
            summary["task_create_ok"] = bool(task_id)

            worker = _request_json(client, "POST", "/workers/run-once", 200)
            summary["worker_run_once_ok"] = (
                worker.get("claimed") is True
                and worker.get("task_id") == task_id
                and worker.get("run_id") is not None
            )

            detail = _request_json(client, "GET", f"/tasks/{task_id}/detail", 200)
            runs = detail.get("runs") if isinstance(detail, dict) else None
            summary["task_detail_ok"] = isinstance(runs, list)
            summary["run_created"] = bool(runs)

        required_checks = (
            "app_import_ok",
            "database_init_ok",
            "health_ok",
            "tasks_list_ok",
            "task_create_ok",
            "worker_run_once_ok",
            "task_detail_ok",
            "run_created",
            "isolated_runtime_data",
        )
        if all(summary[item] for item in required_checks):
            summary["smoke_status"] = "passed"
        else:
            summary["blocked_reasons"].append("required_smoke_check_failed")
    except Exception as exc:  # pragma: no cover - failure path is operator evidence.
        summary["smoke_status"] = "failed"
        summary["blocked_reasons"].append(type(exc).__name__)

    return summary


def main() -> int:
    args = _parse_args()
    temp_created = args.runtime_dir is None
    runtime_data_dir = (
        Path(tempfile.mkdtemp(prefix="p9-run-backend-smoke-"))
        if args.runtime_dir is None
        else args.runtime_dir
    ).resolve()
    runtime_data_dir.mkdir(parents=True, exist_ok=True)

    try:
        summary = run_smoke(runtime_data_dir)
    finally:
        should_cleanup = temp_created and not args.keep_temp_data
        if should_cleanup:
            shutil.rmtree(runtime_data_dir, ignore_errors=True)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    else:
        print(f"P9-RUN-A backend runnable smoke: {summary['smoke_status']}")

    return 0 if summary["smoke_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
