"""P13 Project Director controlled executor lifecycle pilot smoke.

Default path uses isolated runtime data and real FastAPI routes:
create session -> P11 evidence-to-agent dry-run -> P12 safe dry-run task
dispatch -> P13 controlled executor dispatch dry_run -> lifecycle result
message readback. It does not start native executors, Codex, Claude Code,
Worker, external executor subprocesses, worktree writes, or product runtime
Git writes.
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
    parser.add_argument(
        "--launch-mode",
        choices=("dry_run", "controlled_smoke"),
        default="dry_run",
    )
    parser.add_argument(
        "--executor",
        choices=("codex", "claude-code"),
        default="codex",
    )
    parser.add_argument(
        "--requested-agent-role",
        choices=("programmer", "reviewer"),
        default="programmer",
    )
    parser.add_argument("--enable-native-process", action="store_true")
    parser.add_argument("--auto-terminate", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=0.0)
    parser.add_argument("--use-supervisor", action="store_true")
    parser.add_argument("--supervisor-cleanup-after-launch", action="store_true")
    return parser.parse_args()


def _base_summary(runtime_data_dir: Path, sqlite_db_path: Path) -> dict[str, Any]:
    return {
        "smoke_status": "failed",
        "session_created": False,
        "session_id": None,
        "p11_dry_run_message_bound": False,
        "p12_safe_task_created": False,
        "p13_dispatch_message_bound": False,
        "launch_mode": "dry_run",
        "requested_executor": "codex",
        "requested_agent_role": "programmer",
        "controlled_executor_pilot": True,
        "executor_backed_agent": True,
        "native_executor_started": False,
        "codex_started": False,
        "claude_code_started": False,
        "agent_session_bound": False,
        "runtime_handle_id_present": False,
        "process_handle_id_present": False,
        "supervisor_required": True,
        "supervisor_registered": False,
        "auto_terminate_required": True,
        "terminate_attempted": False,
        "cleanup_required": True,
        "supervisor_cleanup_done": False,
        "lifecycle_result_message_bound": False,
        "message_readback_ok": False,
        "product_runtime_git_write_allowed": False,
        "worktree_write_allowed": False,
        "frontend_required": False,
        "run_created": False,
        "real_code_modified": False,
        "git_write_performed": False,
        "ai_project_director_total_loop": "Partial",
        "p9_production_safe_long_running_executor_lifecycle": "Partial",
        "runtime_data_dir": str(runtime_data_dir),
        "sqlite_db_path": str(sqlite_db_path),
        "isolated_runtime_data": False,
        "p13_dispatch_response_summary": {},
        "blocked_reasons": [],
        "risks": [
            "controlled executor lifecycle pilot is not code execution completion",
            "dry_run smoke does not prove production-safe long-running lifecycle",
        ],
        "unknowns": [
            "real controlled subprocess smoke is optional and not part of default pytest",
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


def _controlled_smoke_gate(args: argparse.Namespace) -> list[str]:
    if args.launch_mode != "controlled_smoke":
        return []
    blocked_reasons: list[str] = []
    if not args.enable_native_process:
        blocked_reasons.append("enable_native_process_required")
    if not args.auto_terminate:
        blocked_reasons.append("auto_terminate_required")
    if args.timeout_seconds <= 0:
        blocked_reasons.append("positive_timeout_seconds_required")
    if not args.use_supervisor:
        blocked_reasons.append("supervisor_required")
    if not args.supervisor_cleanup_after_launch:
        blocked_reasons.append("supervisor_cleanup_after_launch_required")
    return blocked_reasons


def _record_lifecycle_result(
    *,
    session_id: str,
    source_task_id: str,
    source_message_id: str,
    requested_agent_role: str,
    requested_executor: str,
    launch_mode: str,
) -> None:
    from uuid import UUID

    from app.core.db import SessionLocal
    from app.domain.project_director_controlled_executor_dispatch import (
        ProjectDirectorControlledExecutorLifecycleResult,
    )
    from app.repositories.project_director_message_repository import (
        ProjectDirectorMessageRepository,
    )
    from app.repositories.project_director_session_repository import (
        ProjectDirectorSessionRepository,
    )
    from app.repositories.task_repository import TaskRepository
    from app.services.project_director_controlled_executor_dispatch_service import (
        ProjectDirectorControlledExecutorDispatchService,
    )

    db_session = SessionLocal()
    try:
        service = ProjectDirectorControlledExecutorDispatchService(
            session_repository=ProjectDirectorSessionRepository(db_session),
            message_repository=ProjectDirectorMessageRepository(db_session),
            task_repository=TaskRepository(db_session),
        )
        service.record_lifecycle_result(
            result=ProjectDirectorControlledExecutorLifecycleResult(
                session_id=UUID(session_id),
                source_task_id=UUID(source_task_id),
                source_message_id=UUID(source_message_id),
                requested_agent_role=requested_agent_role,  # type: ignore[arg-type]
                requested_executor=requested_executor,  # type: ignore[arg-type]
                launch_mode=launch_mode,  # type: ignore[arg-type]
                native_executor_started=False,
                codex_started=False,
                claude_code_started=False,
                agent_session_bound=False,
                runtime_handle_id_present=False,
                process_handle_id_present=False,
                supervisor_registered=False,
                terminate_attempted=False,
                supervisor_cleanup_done=False,
                run_created=False,
                real_code_modified=False,
                git_write_performed=False,
            )
        )
    finally:
        db_session.close()


def run_smoke(runtime_data_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    sqlite_db_path = _configure_isolated_environment(runtime_data_dir)
    summary = _base_summary(runtime_data_dir.resolve(), sqlite_db_path.resolve())
    summary["isolated_runtime_data"] = runtime_data_dir.resolve() != DEFAULT_RUNTIME_DATA_DIR
    summary["launch_mode"] = args.launch_mode
    summary["requested_executor"] = args.executor
    summary["requested_agent_role"] = args.requested_agent_role

    if not summary["isolated_runtime_data"]:
        summary["smoke_status"] = "blocked"
        summary["blocked_reasons"].append("runtime_data_dir_must_be_isolated")
        return summary

    gate_blocks = _controlled_smoke_gate(args)
    if gate_blocks:
        summary["smoke_status"] = "blocked"
        summary["blocked_reasons"].extend(gate_blocks)
        return summary

    if args.launch_mode == "controlled_smoke":
        summary["smoke_status"] = "blocked"
        summary["blocked_reasons"].append("controlled_smoke_not_run_by_default")
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
                        "P13-C Project Director controlled executor lifecycle pilot"
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
                json={"user_goal": "P13-C evidence-to-agent source message"},
            )
            p11_message = p11_payload.get("message") or {}
            summary["p11_dry_run_message_bound"] = (
                p11_message.get("source_detail")
                == "p11_evidence_to_agent_session_dry_run"
            )

            p12_payload = _request_json(
                client,
                "POST",
                f"/project-director/sessions/{session_id}/dry-run-task-dispatch",
                200,
                json={
                    "source_message_id": p11_message.get("id"),
                    "user_confirmed": True,
                },
            )
            source_task_id = p12_payload.get("created_task_id")
            p12_message = p12_payload.get("message") or {}
            source_message_id = p12_message.get("id")
            summary["p12_safe_task_created"] = bool(
                source_task_id and p12_payload.get("safe_dry_run_task") is True
            )

            p13_payload = _request_json(
                client,
                "POST",
                f"/project-director/sessions/{session_id}/controlled-executor-dispatch",
                200,
                json={
                    "source_task_id": source_task_id,
                    "source_message_id": source_message_id,
                    "user_confirmed": True,
                    "requested_agent_role": args.requested_agent_role,
                    "requested_executor": args.executor,
                    "launch_mode": "dry_run",
                },
            )
            summary["p13_dispatch_message_bound"] = bool(
                p13_payload.get("message_bound")
            )
            summary["p13_dispatch_response_summary"] = {
                "dispatch_status": p13_payload.get("dispatch_status"),
                "controlled_executor_pilot": p13_payload.get(
                    "controlled_executor_pilot"
                ),
                "executor_backed_agent": p13_payload.get("executor_backed_agent"),
                "requested_agent_role": p13_payload.get("requested_agent_role"),
                "requested_executor": p13_payload.get("requested_executor"),
                "product_runtime_git_write_allowed": p13_payload.get(
                    "product_runtime_git_write_allowed"
                ),
                "worktree_write_allowed": p13_payload.get("worktree_write_allowed"),
                "native_executor_started": p13_payload.get("native_executor_started"),
                "codex_started": p13_payload.get("codex_started"),
                "claude_code_started": p13_payload.get("claude_code_started"),
                "agent_session_bound": p13_payload.get("agent_session_bound"),
                "run_created": p13_payload.get("run_created"),
                "message_bound": p13_payload.get("message_bound"),
                "ai_project_director_total_loop": p13_payload.get(
                    "ai_project_director_total_loop"
                ),
            }

            _record_lifecycle_result(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
                requested_agent_role=args.requested_agent_role,
                requested_executor=args.executor,
                launch_mode="dry_run",
            )
            summary["lifecycle_result_message_bound"] = True

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
            has_p12 = any(
                item.get("source_detail") == "p12_dry_run_task_dispatch"
                for item in messages
            )
            has_p13_dispatch = any(
                item.get("source_detail") == "p13_controlled_executor_dispatch"
                for item in messages
            )
            has_p13_lifecycle = any(
                item.get("source_detail")
                == "p13_controlled_executor_lifecycle_result"
                for item in messages
            )
            summary["message_readback_ok"] = (
                has_p11 and has_p12 and has_p13_dispatch and has_p13_lifecycle
            )

        required_checks = (
            "session_created",
            "p11_dry_run_message_bound",
            "p12_safe_task_created",
            "p13_dispatch_message_bound",
            "lifecycle_result_message_bound",
            "message_readback_ok",
            "isolated_runtime_data",
        )
        if all(summary[item] for item in required_checks):
            summary["smoke_status"] = "passed_dry_run"
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
        Path(tempfile.mkdtemp(prefix="p13-controlled-executor-smoke-"))
        if args.runtime_dir is None
        else args.runtime_dir
    ).resolve()
    runtime_data_dir.mkdir(parents=True, exist_ok=True)

    try:
        summary = run_smoke(runtime_data_dir, args)
    finally:
        should_cleanup = temp_created and not args.keep_temp_data
        if should_cleanup:
            shutil.rmtree(runtime_data_dir, ignore_errors=True)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    else:
        print(f"P13 controlled executor lifecycle smoke: {summary['smoke_status']}")

    return 0 if summary["smoke_status"] in {"passed", "passed_dry_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
