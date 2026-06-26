"""P21-A Project Director sandbox write execution smoke.

Default dry_run and fake_write paths use isolated runtime data and do not start Codex,
Claude Code, Worker subprocesses, worktree writes, file writes, patch application,
or product runtime Git writes. Controlled sandbox write is blocked in this harness.
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
        "--execution-mode",
        choices=("dry_run", "fake_write", "controlled_sandbox_write"),
        default="dry_run",
    )
    parser.add_argument(
        "--programmer-executor",
        choices=("codex", "claude-code"),
        default="codex",
    )
    return parser.parse_args()


def _base_summary(runtime_data_dir: Path, sqlite_db_path: Path) -> dict[str, Any]:
    return {
        "smoke_status": "failed",
        "session_created": False,
        "session_id": None,
        "p20_preflight_passed": False,
        "p20_preflight_message_bound": False,
        "p21_dry_run": None,
        "p21_fake_write": None,
        "p21_controlled_sandbox_write": None,
        "p21_blocked_preflight": None,
        "p21_source_task_message_mismatch": None,
        "p21_message_readback": None,
        "no_write_boundary": "failed",
        "ai_project_director_total_loop": "Partial",
        "execution_mode": "dry_run",
        "p21_execution_status": None,
        "p21_execution_message_bound": False,
        "p21_checked_operations_count": 0,
        "p21_operation_results_count": 0,
        "sandbox_write_allowed": False,
        "product_runtime_git_write_allowed": False,
        "main_worktree_write_allowed": False,
        "worktree_write_allowed": False,
        "file_write_allowed": False,
        "actual_patch_applied": False,
        "real_code_modified": False,
        "git_write_performed": False,
        "native_executor_started": False,
        "codex_started": False,
        "claude_code_started": False,
        "worker_started": False,
        "task_created": False,
        "run_created": False,
        "worktree_created": False,
        "file_written": False,
        "runtime_data_dir": str(runtime_data_dir),
        "sqlite_db_path": str(sqlite_db_path),
        "isolated_runtime_data": False,
        "blocked_reasons": [],
        "risks": [],
        "unknowns": [],
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
        raise RuntimeError(
            f"{method} {path} returned HTTP {response.status_code}, "
            f"body: {response.text[:500]}"
        )
    return response.json()


def _record_p14_lifecycle_result(
    *,
    session_id: str,
    source_task_id: str,
    source_message_id: str,
    requested_executor: str,
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
                requested_agent_role="programmer",
                requested_executor=requested_executor,
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


def _record_p15_review_result(
    *,
    session_id: str,
    source_task_id: str,
    source_message_id: str,
) -> str:
    from app.core.db import SessionLocal
    from app.repositories.project_director_message_repository import (
        ProjectDirectorMessageRepository,
    )
    from app.repositories.project_director_session_repository import (
        ProjectDirectorSessionRepository,
    )
    from app.repositories.task_repository import TaskRepository
    from app.services.project_director_readonly_review_service import (
        ProjectDirectorReadonlyReviewService,
    )

    db_session = SessionLocal()
    try:
        service = ProjectDirectorReadonlyReviewService(
            session_repository=ProjectDirectorSessionRepository(db_session),
            message_repository=ProjectDirectorMessageRepository(db_session),
            task_repository=TaskRepository(db_session),
        )
        review = service.confirm_review(
            session_id=UUID(session_id),
            source_task_id=UUID(source_task_id),
            source_message_id=UUID(source_message_id),
            user_confirmed=True,
            requested_reviewer_executor="codex",
            review_mode="fake_review",
        )
        return str(review.message.id)
    finally:
        db_session.close()


def _record_p16_plan_result(
    *,
    session_id: str,
    source_task_id: str,
    source_message_id: str,
) -> str:
    from app.core.db import SessionLocal
    from app.repositories.project_director_message_repository import (
        ProjectDirectorMessageRepository,
    )
    from app.repositories.project_director_session_repository import (
        ProjectDirectorSessionRepository,
    )
    from app.repositories.task_repository import TaskRepository
    from app.services.project_director_programmer_no_write_plan_service import (
        ProjectDirectorProgrammerNoWritePlanService,
    )

    db_session = SessionLocal()
    try:
        service = ProjectDirectorProgrammerNoWritePlanService(
            session_repository=ProjectDirectorSessionRepository(db_session),
            message_repository=ProjectDirectorMessageRepository(db_session),
            task_repository=TaskRepository(db_session),
        )
        plan = service.confirm_plan(
            session_id=UUID(session_id),
            source_task_id=UUID(source_task_id),
            source_message_id=UUID(source_message_id),
            user_confirmed=True,
            requested_programmer_executor="codex",
            planning_mode="fake_plan",
        )
        return str(plan.message.id)
    finally:
        db_session.close()


def _record_p17_execution_result(
    *,
    session_id: str,
    source_task_id: str,
    source_message_id: str,
) -> str:
    from app.core.db import SessionLocal
    from app.repositories.project_director_message_repository import (
        ProjectDirectorMessageRepository,
    )
    from app.repositories.project_director_session_repository import (
        ProjectDirectorSessionRepository,
    )
    from app.repositories.task_repository import TaskRepository
    from app.services.project_director_programmer_no_write_execution_service import (
        ProjectDirectorProgrammerNoWriteExecutionService,
    )

    db_session = SessionLocal()
    try:
        service = ProjectDirectorProgrammerNoWriteExecutionService(
            session_repository=ProjectDirectorSessionRepository(db_session),
            message_repository=ProjectDirectorMessageRepository(db_session),
            task_repository=TaskRepository(db_session),
        )
        execution = service.confirm_execution(
            session_id=UUID(session_id),
            source_task_id=UUID(source_task_id),
            source_message_id=UUID(source_message_id),
            user_confirmed=True,
            requested_programmer_executor="codex",
            execution_mode="fake_execution",
        )
        return str(execution.message.id)
    finally:
        db_session.close()


def _prepare_project_director_chain(
    *,
    summary: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
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
                "name": "P21 sandbox write execution smoke",
                "summary": "Isolated Project Director sandbox write execution smoke.",
                "status": "active",
                "stage": "execution",
            },
        )
        project_id = project_payload["id"]

        session_payload = _request_json(
            client,
            "POST",
            "/project-director/sessions",
            201,
            json={"project_id": project_id, "goal_text": "P21 sandbox write execution"},
        )
        session_id = session_payload["id"]
        summary["session_created"] = bool(session_id)
        summary["session_id"] = session_id

        p11_payload = _request_json(
            client,
            "POST",
            f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
            200,
            json={"user_goal": "P21 evidence-to-agent source message"},
        )
        p11_message = p11_payload.get("message") or {}

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

        _request_json(client, "POST", "/workers/run-once", 200)

        _request_json(
            client,
            "POST",
            f"/project-director/sessions/{session_id}/controlled-executor-dispatch",
            200,
            json={
                "source_task_id": source_task_id,
                "source_message_id": source_message_id,
                "user_confirmed": True,
                "requested_agent_role": "programmer",
                "requested_executor": args.programmer_executor,
                "launch_mode": "dry_run",
            },
        )

        p14_message_id = _record_p14_lifecycle_result(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            requested_executor=args.programmer_executor,
        )

        p15_message_id = _record_p15_review_result(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=p14_message_id,
        )

        p16_message_id = _record_p16_plan_result(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=p15_message_id,
        )

        p17_message_id = _record_p17_execution_result(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=p16_message_id,
        )

        # P20 preflight
        p20_payload = _request_json(
            client,
            "POST",
            f"/project-director/sessions/{session_id}/sandbox-write-preflight",
            200,
            json={
                "source_task_id": source_task_id,
                "source_message_id": p17_message_id,
                "user_confirmed": True,
                "preflight_mode": "dry_run",
                "file_operations": [
                    {
                        "path": "runtime/orchestrator/app/domain/example.py",
                        "operation": "update",
                        "reason": "P21 smoke test",
                        "patch_preview": ["PREVIEW ONLY: no repository file was modified."],
                    }
                ],
            },
        )
        summary["p20_preflight_passed"] = p20_payload.get("preflight_status") == "passed"
        summary["p20_preflight_message_bound"] = bool(
            p20_payload.get("preflight_message_bound")
        )
        p20_message_id = p20_payload["message"]["id"]

        # Test blocked preflight cannot enter P21
        blocked_preflight_payload = _request_json(
            client,
            "POST",
            f"/project-director/sessions/{session_id}/sandbox-write-preflight",
            409,
            json={
                "source_task_id": source_task_id,
                "source_message_id": p17_message_id,
                "user_confirmed": True,
                "preflight_mode": "dry_run",
                "file_operations": [
                    {
                        "path": ".env",
                        "operation": "update",
                        "reason": "test denied path",
                    }
                ],
            },
        )
        summary["p21_blocked_preflight"] = "blocked"

        # Test controlled_sandbox_write blocked
        _request_json(
            client,
            "POST",
            f"/project-director/sessions/{session_id}/sandbox-write-execution",
            409,
            json={
                "source_task_id": source_task_id,
                "source_message_id": p20_message_id,
                "user_confirmed": True,
                "execution_mode": "controlled_sandbox_write",
            },
        )
        summary["p21_controlled_sandbox_write"] = "blocked"

        # Test source_task/message mismatch
        # Create second chain for mismatch test
        p11_b = _request_json(
            client,
            "POST",
            f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
            200,
            json={"user_goal": "P21 second evidence"},
        )
        p11_msg_b = p11_b.get("message") or {}

        p12_b = _request_json(
            client,
            "POST",
            f"/project-director/sessions/{session_id}/dry-run-task-dispatch",
            200,
            json={"source_message_id": p11_msg_b.get("id"), "user_confirmed": True},
        )
        task_b_id = p12_b.get("created_task_id")
        p12_msg_b_id = p12_b.get("message") or {}

        _request_json(client, "POST", "/workers/run-once", 200)

        _request_json(
            client,
            "POST",
            f"/project-director/sessions/{session_id}/controlled-executor-dispatch",
            200,
            json={
                "source_task_id": task_b_id,
                "source_message_id": p12_msg_b_id.get("id"),
                "user_confirmed": True,
                "requested_agent_role": "programmer",
                "requested_executor": args.programmer_executor,
                "launch_mode": "dry_run",
            },
        )

        p14_b = _record_p14_lifecycle_result(
            session_id=session_id,
            source_task_id=task_b_id,
            source_message_id=p12_msg_b_id.get("id"),
            requested_executor=args.programmer_executor,
        )
        p15_b = _record_p15_review_result(
            session_id=session_id,
            source_task_id=task_b_id,
            source_message_id=p14_b,
        )
        p16_b = _record_p16_plan_result(
            session_id=session_id,
            source_task_id=task_b_id,
            source_message_id=p15_b,
        )
        p17_b = _record_p17_execution_result(
            session_id=session_id,
            source_task_id=task_b_id,
            source_message_id=p16_b,
        )
        p20_b = _request_json(
            client,
            "POST",
            f"/project-director/sessions/{session_id}/sandbox-write-preflight",
            200,
            json={
                "source_task_id": task_b_id,
                "source_message_id": p17_b,
                "user_confirmed": True,
                "preflight_mode": "dry_run",
                "file_operations": [
                    {
                        "path": "runtime/orchestrator/app/domain/other.py",
                        "operation": "update",
                        "reason": "test",
                        "patch_preview": ["PREVIEW ONLY: no repository file was modified."],
                    }
                ],
            },
        )
        p20_msg_b_id = p20_b["message"]["id"]

        # Mismatch: task A + P20 message from task B
        _request_json(
            client,
            "POST",
            f"/project-director/sessions/{session_id}/sandbox-write-execution",
            409,
            json={
                "source_task_id": source_task_id,
                "source_message_id": p20_msg_b_id,
                "user_confirmed": True,
            },
        )
        summary["p21_source_task_message_mismatch"] = "blocked"

        # Main P21 execution
        p21_payload = _request_json(
            client,
            "POST",
            f"/project-director/sessions/{session_id}/sandbox-write-execution",
            200,
            json={
                "source_task_id": source_task_id,
                "source_message_id": p20_message_id,
                "user_confirmed": True,
                "execution_mode": args.execution_mode,
            },
        )

        summary["p21_execution_status"] = p21_payload.get("execution_status")
        summary["p21_execution_message_bound"] = bool(
            p21_payload.get("execution_message_bound")
        )
        summary["p21_checked_operations_count"] = p21_payload.get(
            "checked_operations_count", 0
        )
        summary["p21_operation_results_count"] = len(
            p21_payload.get("operation_results") or []
        )
        summary["sandbox_write_allowed"] = p21_payload.get("sandbox_write_allowed", False)
        summary["product_runtime_git_write_allowed"] = p21_payload.get(
            "product_runtime_git_write_allowed", False
        )
        summary["main_worktree_write_allowed"] = p21_payload.get(
            "main_worktree_write_allowed", False
        )
        summary["worktree_write_allowed"] = p21_payload.get("worktree_write_allowed", False)
        summary["file_write_allowed"] = p21_payload.get("file_write_allowed", False)
        summary["actual_patch_applied"] = p21_payload.get("actual_patch_applied", False)
        summary["real_code_modified"] = p21_payload.get("real_code_modified", False)
        summary["git_write_performed"] = p21_payload.get("git_write_performed", False)
        summary["native_executor_started"] = p21_payload.get("native_executor_started", False)
        summary["codex_started"] = p21_payload.get("codex_started", False)
        summary["claude_code_started"] = p21_payload.get("claude_code_started", False)
        summary["worker_started"] = p21_payload.get("worker_started", False)
        summary["task_created"] = p21_payload.get("task_created", False)
        summary["run_created"] = p21_payload.get("run_created", False)
        summary["worktree_created"] = p21_payload.get("worktree_created", False)
        summary["file_written"] = p21_payload.get("file_written", False)
        summary["risks"] = p21_payload.get("risks", [])
        summary["unknowns"] = p21_payload.get("unknowns", [])

        # Set dry_run/fake_write status
        if args.execution_mode == "dry_run":
            summary["p21_dry_run"] = (
                "passed_planned"
                if p21_payload.get("execution_status") == "planned"
                else "failed"
            )
        elif args.execution_mode == "fake_write":
            summary["p21_fake_write"] = (
                "passed_simulated"
                if p21_payload.get("execution_status") == "simulated"
                else "failed"
            )

        # Message readback
        messages_payload = _request_json(
            client,
            "GET",
            f"/project-director/sessions/{session_id}/messages",
            200,
        )
        messages = messages_payload.get("messages") or []
        has_p21 = any(
            item.get("source_detail") == "p21_sandbox_write_execution"
            for item in messages
        )
        summary["p21_message_readback"] = "passed" if has_p21 else "failed"

        # No-write boundary check
        all_false = all(
            not summary.get(flag, False)
            for flag in [
                "sandbox_write_allowed",
                "product_runtime_git_write_allowed",
                "main_worktree_write_allowed",
                "worktree_write_allowed",
                "file_write_allowed",
                "actual_patch_applied",
                "real_code_modified",
                "git_write_performed",
                "native_executor_started",
                "codex_started",
                "claude_code_started",
                "worker_started",
                "task_created",
                "run_created",
                "worktree_created",
                "file_written",
            ]
        )
        summary["no_write_boundary"] = "passed" if all_false else "failed"

        return summary


def run_smoke(runtime_data_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    sqlite_db_path = _configure_isolated_environment(runtime_data_dir)
    summary = _base_summary(runtime_data_dir.resolve(), sqlite_db_path.resolve())
    summary["isolated_runtime_data"] = (
        runtime_data_dir.resolve() != DEFAULT_RUNTIME_DATA_DIR
    )
    summary["execution_mode"] = args.execution_mode

    if not summary["isolated_runtime_data"]:
        summary["smoke_status"] = "blocked"
        summary["blocked_reasons"].append("runtime_data_dir_must_be_isolated")
        return summary

    if args.execution_mode == "controlled_sandbox_write":
        summary["smoke_status"] = "blocked"
        summary["blocked_reasons"].append(
            "controlled_sandbox_write_not_enabled_in_api"
        )
        return summary

    try:
        _prepare_project_director_chain(summary=summary, args=args)
    except Exception as exc:
        summary["smoke_status"] = "failed"
        summary["blocked_reasons"].append(type(exc).__name__)
        return summary

    required_checks = (
        "session_created",
        "p20_preflight_passed",
        "p20_preflight_message_bound",
        "p21_execution_message_bound",
        "p21_message_readback",
        "no_write_boundary",
        "isolated_runtime_data",
    )
    if all(summary.get(item) for item in required_checks):
        if args.execution_mode == "fake_write":
            summary["smoke_status"] = "passed_fake_write"
        else:
            summary["smoke_status"] = "passed_dry_run"
    else:
        summary["smoke_status"] = "partial"
        summary["blocked_reasons"].append("required_smoke_check_failed")

    return summary


def main() -> int:
    args = _parse_args()
    temp_created = args.runtime_dir is None
    runtime_data_dir = (
        Path(tempfile.mkdtemp(prefix="p21-sandbox-write-execution-smoke-"))
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
        print(f"P21 sandbox write execution smoke: {summary['smoke_status']}")

    return (
        0
        if summary["smoke_status"]
        in {"passed_dry_run", "passed_fake_write", "passed_controlled_sandbox_write"}
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
