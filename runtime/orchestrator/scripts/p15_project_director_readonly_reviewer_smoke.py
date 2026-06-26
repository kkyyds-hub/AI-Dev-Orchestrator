"""P15 Project Director readonly reviewer smoke.

Default and fake-review paths use isolated runtime data and do not start Codex,
Claude Code, Worker subprocesses, worktree writes, file writes, or product
runtime Git writes. Controlled review is gated by explicit safety flags and is
blocked in this harness until a real sanitized reviewer-output path is added.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
from uuid import UUID

from p13_project_director_controlled_executor_lifecycle_smoke import (
    DEFAULT_RUNTIME_DATA_DIR,
)


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
        "--review-mode",
        choices=("dry_run", "fake_review", "controlled_review"),
        default="dry_run",
    )
    parser.add_argument(
        "--reviewer-executor",
        choices=("codex", "claude-code"),
        default="codex",
    )
    parser.add_argument("--enable-native-process", action="store_true")
    parser.add_argument("--auto-terminate", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=0.0)
    parser.add_argument("--use-supervisor", action="store_true")
    parser.add_argument("--supervisor-cleanup-after-launch", action="store_true")
    parser.add_argument("--readonly-output-dir", type=Path)
    return parser.parse_args()


def _base_summary(runtime_data_dir: Path, sqlite_db_path: Path) -> dict[str, Any]:
    return {
        "smoke_status": "failed",
        "session_created": False,
        "session_id": None,
        "project_id_present": False,
        "p11_dry_run_message_bound": False,
        "p12_safe_task_created": False,
        "p12_worker_run_once_ok": False,
        "p13_dispatch_message_bound": False,
        "p14_lifecycle_result_message_bound": False,
        "p15_review_message_bound": False,
        "message_readback_ok": False,
        "review_mode": "dry_run",
        "requested_reviewer_executor": "codex",
        "readonly_review": True,
        "reviewer_agent": True,
        "executor_backed_review_allowed": True,
        "native_executor_started": False,
        "codex_started": False,
        "claude_code_started": False,
        "agent_session_bound": False,
        "supervisor_registered": False,
        "terminate_attempted": False,
        "supervisor_cleanup_done": False,
        "review_result_created": False,
        "review_findings_count": 0,
        "review_summary_present": False,
        "recommended_next_step_present": False,
        "product_runtime_git_write_allowed": False,
        "worktree_write_allowed": False,
        "file_write_allowed": False,
        "real_code_modified": False,
        "git_write_performed": False,
        "ai_project_director_total_loop": "Partial",
        "p9_production_safe_long_running_executor_lifecycle": "Partial",
        "runtime_data_dir": str(runtime_data_dir),
        "sqlite_db_path": str(sqlite_db_path),
        "isolated_runtime_data": False,
        "blocked_reasons": [],
        "risks": [
            "readonly reviewer smoke is not code modification completion",
            "readonly reviewer smoke is not product runtime Git write authorization",
        ],
        "unknowns": [
            "real controlled reviewer subprocess evidence was not collected",
        ],
    }


def _configure_isolated_environment(runtime_data_dir: Path) -> Path:
    sqlite_db_path = runtime_data_dir / "db" / "orchestrator.db"
    os.environ["RUNTIME_DATA_DIR"] = str(runtime_data_dir)
    os.environ["SQLITE_DB_PATH"] = str(sqlite_db_path)
    os.environ["WORKER_SIMULATE_EXECUTION_OVERRIDE"] = "true"
    os.environ.pop("OPENAI_API_KEY", None)
    return sqlite_db_path


def _controlled_review_gate(args: argparse.Namespace) -> list[str]:
    if args.review_mode != "controlled_review":
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
    if args.readonly_output_dir is None:
        blocked_reasons.append("readonly_output_dir_required")
    return blocked_reasons


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


def _record_p14_lifecycle_result(
    *,
    session_id: str,
    source_task_id: str,
    source_message_id: str,
    requested_reviewer_executor: str,
) -> str:
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
        P14_LIFECYCLE_RESULT_SOURCE_DETAIL,
        ProjectDirectorControlledExecutorDispatchService,
    )

    db_session = SessionLocal()
    try:
        service = ProjectDirectorControlledExecutorDispatchService(
            session_repository=ProjectDirectorSessionRepository(db_session),
            message_repository=ProjectDirectorMessageRepository(db_session),
            task_repository=TaskRepository(db_session),
        )
        message = service.record_lifecycle_result(
            result=ProjectDirectorControlledExecutorLifecycleResult(
                session_id=UUID(session_id),
                source_task_id=UUID(source_task_id),
                source_message_id=UUID(source_message_id),
                requested_agent_role="reviewer",
                requested_executor=requested_reviewer_executor,  # type: ignore[arg-type]
                launch_mode="dry_run",
                native_executor_started=False,
                codex_started=False,
                claude_code_started=False,
                agent_session_bound=False,
                runtime_handle_id_present=False,
                process_handle_id_present=False,
                supervisor_registered=False,
                terminate_attempted=False,
                supervisor_cleanup_done=False,
                run_created=True,
                real_code_modified=False,
                git_write_performed=False,
                p9_production_safe_long_running_executor_lifecycle="Partial",
            ),
            source_detail=P14_LIFECYCLE_RESULT_SOURCE_DETAIL,
        )
        return str(message.id)
    finally:
        db_session.close()


def _prepare_project_director_chain(
    *,
    summary: dict[str, Any],
    args: argparse.Namespace,
) -> None:
    import warnings

    warnings.filterwarnings(
        "ignore",
        message="Using `httpx` with `starlette.testclient` is deprecated.*",
        category=Warning,
    )
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        project_payload = _request_json(
            client,
            "POST",
            "/projects",
            201,
            json={
                "name": "P15 readonly reviewer smoke",
                "summary": "Isolated Project Director readonly reviewer smoke.",
                "status": "active",
                "stage": "execution",
            },
        )
        project_id = project_payload["id"]
        summary["project_id_present"] = bool(project_id)

        session_payload = _request_json(
            client,
            "POST",
            "/project-director/sessions",
            201,
            json={"project_id": project_id, "goal_text": "P15 readonly review"},
        )
        session_id = session_payload["id"]
        summary["session_created"] = bool(session_id)
        summary["session_id"] = session_id

        p11_payload = _request_json(
            client,
            "POST",
            f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
            200,
            json={"user_goal": "P15 evidence-to-agent source message"},
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

        worker_payload = _request_json(client, "POST", "/workers/run-once", 200)
        summary["p12_worker_run_once_ok"] = (
            worker_payload.get("claimed") is True
            and worker_payload.get("task_id") == source_task_id
            and worker_payload.get("run_id") is not None
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
                "requested_agent_role": "reviewer",
                "requested_executor": args.reviewer_executor,
                "launch_mode": "dry_run",
            },
        )
        summary["p13_dispatch_message_bound"] = bool(
            p13_payload.get("message_bound")
        )

        p14_message_id = _record_p14_lifecycle_result(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            requested_reviewer_executor=args.reviewer_executor,
        )
        summary["p14_lifecycle_result_message_bound"] = bool(p14_message_id)

        review_payload = _request_json(
            client,
            "POST",
            f"/project-director/sessions/{session_id}/readonly-review",
            200,
            json={
                "source_task_id": source_task_id,
                "source_message_id": p14_message_id,
                "user_confirmed": True,
                "requested_reviewer_executor": args.reviewer_executor,
                "review_mode": args.review_mode,
            },
        )
        summary["p15_review_message_bound"] = bool(
            review_payload.get("review_result_message_bound")
        )
        summary["review_result_created"] = review_payload.get("review_status") in {
            "planned",
            "reviewed",
        }
        summary["review_findings_count"] = len(
            review_payload.get("review_findings") or []
        )
        summary["review_summary_present"] = bool(review_payload.get("review_summary"))
        summary["recommended_next_step_present"] = bool(
            review_payload.get("recommended_next_step")
        )

        messages_payload = _request_json(
            client,
            "GET",
            f"/project-director/sessions/{session_id}/messages",
            200,
        )
        messages = messages_payload.get("messages") or []
        has_p14 = any(
            item.get("source_detail") == "p14_controlled_subprocess_lifecycle_result"
            for item in messages
        )
        has_p15 = any(
            item.get("source_detail") == "p15_readonly_reviewer_review"
            for item in messages
        )
        summary["message_readback_ok"] = has_p14 and has_p15


def run_smoke(runtime_data_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    sqlite_db_path = _configure_isolated_environment(runtime_data_dir)
    summary = _base_summary(runtime_data_dir.resolve(), sqlite_db_path.resolve())
    summary["isolated_runtime_data"] = runtime_data_dir.resolve() != DEFAULT_RUNTIME_DATA_DIR
    summary["review_mode"] = args.review_mode
    summary["requested_reviewer_executor"] = args.reviewer_executor

    if not summary["isolated_runtime_data"]:
        summary["smoke_status"] = "blocked"
        summary["blocked_reasons"].append("runtime_data_dir_must_be_isolated")
        return summary

    gate_blocks = _controlled_review_gate(args)
    if gate_blocks:
        summary["smoke_status"] = "blocked"
        summary["blocked_reasons"].extend(gate_blocks)
        return summary

    if args.review_mode == "controlled_review":
        summary["smoke_status"] = "blocked"
        summary["blocked_reasons"].append("controlled_review_not_implemented")
        return summary

    try:
        _prepare_project_director_chain(summary=summary, args=args)
    except Exception as exc:  # pragma: no cover - operator smoke evidence path.
        summary["smoke_status"] = "failed"
        summary["blocked_reasons"].append(type(exc).__name__)
        return summary

    required_checks = (
        "session_created",
        "p11_dry_run_message_bound",
        "p12_safe_task_created",
        "p12_worker_run_once_ok",
        "p13_dispatch_message_bound",
        "p14_lifecycle_result_message_bound",
        "p15_review_message_bound",
        "message_readback_ok",
        "review_result_created",
        "review_summary_present",
        "recommended_next_step_present",
        "isolated_runtime_data",
    )
    if all(summary[item] for item in required_checks):
        summary["smoke_status"] = (
            "passed_fake_review"
            if args.review_mode == "fake_review"
            else "passed_dry_run"
        )
    else:
        summary["smoke_status"] = "partial"
        summary["blocked_reasons"].append("required_smoke_check_failed")
    return summary


def main() -> int:
    args = _parse_args()
    temp_created = args.runtime_dir is None
    runtime_data_dir = (
        Path(tempfile.mkdtemp(prefix="p15-readonly-reviewer-smoke-"))
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
        print(f"P15 readonly reviewer smoke: {summary['smoke_status']}")

    return (
        0
        if summary["smoke_status"] in {
            "passed_dry_run",
            "passed_fake_review",
            "passed_controlled_review",
        }
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
