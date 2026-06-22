"""P12 Project Director confirmed dry-run task dispatch main-path smoke.

The smoke uses isolated runtime data and real FastAPI routes:
create session -> P11 evidence-to-agent dry-run -> confirmed P12 safe task
dispatch -> Worker simulate run-once -> task/run readback -> bind Worker
result back to the Project Director session. It does not start native
executors, Codex, Claude Code, external executors, or product runtime Git
writes.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
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
        "session_created": False,
        "session_id": None,
        "p11_dry_run_message_bound": False,
        "dispatch_api_ok": False,
        "created_task_id": None,
        "safe_dry_run_task": False,
        "worker_run_once_ok": False,
        "worker_started": False,
        "worker_simulate_mode": False,
        "run_created": False,
        "run_id": None,
        "task_detail_ok": False,
        "run_readback_ok": False,
        "session_dispatch_message_bound": False,
        "session_worker_result_message_bound": False,
        "message_readback_ok": False,
        "product_runtime_git_write_allowed": False,
        "frontend_required": False,
        "native_executor_started": False,
        "codex_started": False,
        "claude_code_started": False,
        "ai_project_director_total_loop": "Partial",
        "p9_production_safe_long_running_executor_lifecycle": "Partial",
        "runtime_data_dir": str(runtime_data_dir),
        "sqlite_db_path": str(sqlite_db_path),
        "isolated_runtime_data": False,
        "blocked_reasons": [],
        "risks": [
            "safe dry-run task dispatch is not real executor completion",
            "Worker simulate does not prove production-safe long-running lifecycle",
        ],
        "unknowns": [
            "real programmer/reviewer executor lifecycle remains unproven",
        ],
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

        with TestClient(app) as client:
            session_payload = _request_json(
                client,
                "POST",
                "/project-director/sessions",
                201,
                json={
                    "goal_text": (
                        "P12-C Project Director confirmed safe dry-run task "
                        "dispatch loop"
                    )
                },
            )
            session_id = session_payload["id"]
            summary["session_created"] = bool(session_id)
            summary["session_id"] = session_id

            p11_payload = _request_json(
                client,
                "POST",
                f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
                200,
                json={"user_goal": "P12-C evidence-to-agent source message"},
            )
            p11_message = p11_payload.get("message") or {}
            summary["p11_dry_run_message_bound"] = (
                p11_message.get("source_detail")
                == "p11_evidence_to_agent_session_dry_run"
            )

            dispatch_payload = _request_json(
                client,
                "POST",
                f"/project-director/sessions/{session_id}/dry-run-task-dispatch",
                200,
                json={
                    "source_message_id": p11_message.get("id"),
                    "user_confirmed": True,
                },
            )
            created_task_id = dispatch_payload.get("created_task_id")
            summary["dispatch_api_ok"] = (
                dispatch_payload.get("dispatch_status") == "dispatched"
            )
            summary["created_task_id"] = created_task_id
            summary["safe_dry_run_task"] = bool(
                dispatch_payload.get("safe_dry_run_task")
            )
            summary["session_dispatch_message_bound"] = bool(
                dispatch_payload.get("message_bound")
            )

            worker_payload = _request_json(client, "POST", "/workers/run-once", 200)
            run_id = worker_payload.get("run_id")
            summary["worker_started"] = True
            summary["worker_run_once_ok"] = (
                worker_payload.get("claimed") is True
                and worker_payload.get("task_id") == created_task_id
                and run_id is not None
            )
            summary["worker_simulate_mode"] = (
                worker_payload.get("execution_mode") == "simulate"
            )
            summary["run_created"] = run_id is not None
            summary["run_id"] = run_id

            detail_payload = _request_json(
                client, "GET", f"/tasks/{created_task_id}/detail", 200
            )
            detail_runs = (
                detail_payload.get("runs") if isinstance(detail_payload, dict) else []
            )
            summary["task_detail_ok"] = detail_payload.get("id") == created_task_id

            runs_payload = _request_json(
                client, "GET", f"/tasks/{created_task_id}/runs", 200
            )
            run_ids = {
                item.get("id")
                for item in runs_payload
                if isinstance(item, dict)
            }
            detail_run_ids = {
                item.get("id")
                for item in detail_runs
                if isinstance(item, dict)
            }
            summary["run_readback_ok"] = bool(
                run_id and run_id in run_ids and run_id in detail_run_ids
            )

            worker_result_payload = _request_json(
                client,
                "POST",
                f"/project-director/sessions/{session_id}/dry-run-task-dispatch/worker-result",
                200,
                json={
                    "task_id": created_task_id,
                    "run_id": run_id,
                    "worker_run_once_ok": summary["worker_run_once_ok"],
                    "worker_simulate_mode": summary["worker_simulate_mode"],
                    "run_created": summary["run_created"],
                    "run_readback_ok": summary["run_readback_ok"],
                },
            )
            summary["session_worker_result_message_bound"] = bool(
                worker_result_payload.get("message_bound")
            )

            messages_payload = _request_json(
                client,
                "GET",
                f"/project-director/sessions/{session_id}/messages",
                200,
            )
            messages = messages_payload.get("messages") or []
            has_p11 = any(
                item.get("source_detail")
                == "p11_evidence_to_agent_session_dry_run"
                for item in messages
            )
            has_dispatch = any(
                item.get("source_detail") == "p12_dry_run_task_dispatch"
                for item in messages
            )
            has_worker_result = any(
                item.get("source_detail") == "p12_dry_run_task_worker_result"
                for item in messages
            )
            summary["message_readback_ok"] = (
                has_p11 and has_dispatch and has_worker_result
            )

        required_checks = (
            "session_created",
            "p11_dry_run_message_bound",
            "dispatch_api_ok",
            "safe_dry_run_task",
            "worker_run_once_ok",
            "worker_simulate_mode",
            "run_created",
            "task_detail_ok",
            "run_readback_ok",
            "session_dispatch_message_bound",
            "session_worker_result_message_bound",
            "message_readback_ok",
            "isolated_runtime_data",
        )
        if all(summary[item] for item in required_checks):
            summary["smoke_status"] = "passed"
        else:
            summary["smoke_status"] = "partial"
            summary["blocked_reasons"].append("required_smoke_check_failed")
    except Exception as exc:  # pragma: no cover - failure path is operator evidence.
        summary["smoke_status"] = "failed"
        summary["blocked_reasons"].append(type(exc).__name__)

    return summary


def main() -> int:
    args = _parse_args()
    temp_created = args.runtime_dir is None
    runtime_data_dir = (
        Path(tempfile.mkdtemp(prefix="p12-dry-run-dispatch-smoke-"))
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
        print(f"P12 dry-run task dispatch smoke: {summary['smoke_status']}")

    return 0 if summary["smoke_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
