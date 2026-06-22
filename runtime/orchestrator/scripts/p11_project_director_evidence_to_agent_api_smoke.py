"""P11 Project Director evidence-to-agent API main-path smoke.

The smoke uses isolated runtime data and real FastAPI routes:
create Project Director session -> run session evidence-to-agent dry-run ->
read session messages. It does not start workers, native executors, Codex,
Claude Code, or product runtime Git writes.
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
        "dry_run_api_ok": False,
        "evidence_pack_created": False,
        "evidence_pack_id": None,
        "task_composer_consumed_evidence": False,
        "composed_tasks_count": 0,
        "programmer_assignment_created": False,
        "reviewer_assignment_created": False,
        "message_bound": False,
        "message_readback_ok": False,
        "product_runtime_git_write_allowed": False,
        "frontend_required": False,
        "native_executor_started": False,
        "codex_started": False,
        "claude_code_started": False,
        "worker_started": False,
        "real_task_created": False,
        "ai_project_director_total_loop": "Partial",
        "blocked_reasons": [],
        "runtime_data_dir": str(runtime_data_dir),
        "sqlite_db_path": str(sqlite_db_path),
        "isolated_runtime_data": False,
    }


def _configure_isolated_environment(runtime_data_dir: Path) -> Path:
    sqlite_db_path = runtime_data_dir / "db" / "orchestrator.db"
    os.environ["RUNTIME_DATA_DIR"] = str(runtime_data_dir)
    os.environ["SQLITE_DB_PATH"] = str(sqlite_db_path)
    os.environ.pop("OPENAI_API_KEY", None)
    return sqlite_db_path


def _request_json(
    client: Any,
    method: str,
    path: str,
    expected_status: int,
    **kwargs: Any,
) -> dict[str, Any]:
    response = getattr(client, method.lower())(path, **kwargs)
    if response.status_code != expected_status:
        raise RuntimeError(f"{method} {path} returned HTTP {response.status_code}")
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"{method} {path} did not return a JSON object")
    return data


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
                        "P11-C verify Project Director evidence-to-agent API "
                        "session dry-run main path"
                    )
                },
            )
            session_id = session_payload["id"]
            summary["session_created"] = bool(session_id)
            summary["session_id"] = session_id

            dry_run_payload = _request_json(
                client,
                "POST",
                f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
                200,
                json={"user_goal": "P11-C evidence-to-agent API smoke"},
            )
            dry_run_summary = dry_run_payload["dry_run_summary"]
            message = dry_run_payload.get("message") or {}
            summary["dry_run_api_ok"] = dry_run_summary.get("dry_run_status") == "passed"
            summary["evidence_pack_created"] = bool(
                dry_run_summary.get("evidence_pack_created")
            )
            summary["evidence_pack_id"] = dry_run_summary.get("evidence_pack_id")
            summary["task_composer_consumed_evidence"] = bool(
                dry_run_summary.get("task_composer_consumed_evidence")
            )
            summary["composed_tasks_count"] = int(
                dry_run_summary.get("composed_tasks_count") or 0
            )
            summary["programmer_assignment_created"] = bool(
                dry_run_summary.get("programmer_assignment_created")
            )
            summary["reviewer_assignment_created"] = bool(
                dry_run_summary.get("reviewer_assignment_created")
            )
            summary["product_runtime_git_write_allowed"] = False
            summary["frontend_required"] = False
            summary["native_executor_started"] = bool(
                dry_run_summary.get("native_executor_started")
            )
            summary["codex_started"] = bool(dry_run_summary.get("codex_started"))
            summary["claude_code_started"] = bool(
                dry_run_summary.get("claude_code_started")
            )
            summary["worker_started"] = bool(dry_run_summary.get("worker_started"))
            summary["real_task_created"] = bool(dry_run_summary.get("real_task_created"))
            summary["message_bound"] = (
                message.get("source_detail")
                == "p11_evidence_to_agent_session_dry_run"
            )

            messages_payload = _request_json(
                client,
                "GET",
                f"/project-director/sessions/{session_id}/messages",
                200,
            )
            messages = messages_payload.get("messages") or []
            summary["message_readback_ok"] = any(
                item.get("id") == message.get("id")
                and item.get("source_detail")
                == "p11_evidence_to_agent_session_dry_run"
                for item in messages
            )

        required_checks = (
            "session_created",
            "dry_run_api_ok",
            "evidence_pack_created",
            "task_composer_consumed_evidence",
            "programmer_assignment_created",
            "reviewer_assignment_created",
            "message_bound",
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
        Path(tempfile.mkdtemp(prefix="p11-evidence-api-smoke-"))
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
        print(f"P11 evidence-to-agent API smoke: {summary['smoke_status']}")

    return 0 if summary["smoke_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
