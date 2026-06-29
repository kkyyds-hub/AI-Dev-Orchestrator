"""P21-B Project Director sandbox write design lock smoke.

Uses isolated runtime data and does not start Codex, Claude Code, Worker
subprocesses, worktree writes, file writes, patch application, or product
runtime Git writes.
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
    return parser.parse_args()


def _base_summary(runtime_data_dir: Path, sqlite_db_path: Path) -> dict[str, Any]:
    return {
        "smoke_status": "failed",
        "session_created": False,
        "session_id": None,
        "p21_b_dry_run_design_lock": None,
        "p21_b_fake_write_design_lock": None,
        "p21_b_user_confirmed_blocked": None,
        "p21_b_non_p21_source_blocked": None,
        "p21_b_mismatch_blocked": None,
        "p21_b_runtime_write_flag_blocked": None,
        "p21_b_operation_intent_missing_blocked": None,
        "p21_b_message_readback": None,
        "controlled_sandbox_write_enabled": False,
        "sandbox_write_allowed": False,
        "file_write_allowed": False,
        "worktree_write_allowed": False,
        "product_runtime_git_write_allowed": False,
        "git_write_performed": False,
        "worker_started": False,
        "task_created": False,
        "run_created": False,
        "worktree_created": False,
        "rollback_snapshot_created": False,
        "ai_project_director_total_loop": "Partial",
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
    *, session_id: str, source_task_id: str, source_message_id: str, requested_executor: str,
) -> str:
    from app.core.db import SessionLocal
    from app.domain.project_director_controlled_executor_dispatch import (
        ProjectDirectorControlledExecutorLifecycleResult,
    )
    from app.repositories.project_director_message_repository import ProjectDirectorMessageRepository
    from app.repositories.project_director_session_repository import ProjectDirectorSessionRepository
    from app.repositories.task_repository import TaskRepository
    from app.services.project_director_controlled_executor_dispatch_service import (
        P14_LIFECYCLE_RESULT_SOURCE_DETAIL, ProjectDirectorControlledExecutorDispatchService,
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
                native_executor_started=False, codex_started=False, claude_code_started=False,
                agent_session_bound=False, runtime_handle_id_present=False,
                process_handle_id_present=False, supervisor_registered=False,
                terminate_attempted=False, supervisor_cleanup_done=False,
                run_created=True, real_code_modified=False, git_write_performed=False,
                p9_production_safe_long_running_executor_lifecycle="Partial",
            ),
            source_detail=P14_LIFECYCLE_RESULT_SOURCE_DETAIL,
        )
        return str(message.id)
    finally:
        db_session.close()


def _record_p15_review_result(
    *, session_id: str, source_task_id: str, source_message_id: str,
) -> str:
    from app.core.db import SessionLocal
    from app.repositories.project_director_message_repository import ProjectDirectorMessageRepository
    from app.repositories.project_director_session_repository import ProjectDirectorSessionRepository
    from app.repositories.task_repository import TaskRepository
    from app.services.project_director_readonly_review_service import ProjectDirectorReadonlyReviewService

    db_session = SessionLocal()
    try:
        service = ProjectDirectorReadonlyReviewService(
            session_repository=ProjectDirectorSessionRepository(db_session),
            message_repository=ProjectDirectorMessageRepository(db_session),
            task_repository=TaskRepository(db_session),
        )
        review = service.confirm_review(
            session_id=UUID(session_id), source_task_id=UUID(source_task_id),
            source_message_id=UUID(source_message_id), user_confirmed=True,
            requested_reviewer_executor="codex", review_mode="fake_review",
        )
        return str(review.message.id)
    finally:
        db_session.close()


def _record_p16_plan_result(
    *, session_id: str, source_task_id: str, source_message_id: str,
) -> str:
    from app.core.db import SessionLocal
    from app.repositories.project_director_message_repository import ProjectDirectorMessageRepository
    from app.repositories.project_director_session_repository import ProjectDirectorSessionRepository
    from app.repositories.task_repository import TaskRepository
    from app.services.project_director_programmer_no_write_plan_service import ProjectDirectorProgrammerNoWritePlanService

    db_session = SessionLocal()
    try:
        service = ProjectDirectorProgrammerNoWritePlanService(
            session_repository=ProjectDirectorSessionRepository(db_session),
            message_repository=ProjectDirectorMessageRepository(db_session),
            task_repository=TaskRepository(db_session),
        )
        plan = service.confirm_plan(
            session_id=UUID(session_id), source_task_id=UUID(source_task_id),
            source_message_id=UUID(source_message_id), user_confirmed=True,
            requested_programmer_executor="codex", planning_mode="fake_plan",
        )
        return str(plan.message.id)
    finally:
        db_session.close()


def _record_p17_execution_result(
    *, session_id: str, source_task_id: str, source_message_id: str,
) -> str:
    from app.core.db import SessionLocal
    from app.repositories.project_director_message_repository import ProjectDirectorMessageRepository
    from app.repositories.project_director_session_repository import ProjectDirectorSessionRepository
    from app.repositories.task_repository import TaskRepository
    from app.services.project_director_programmer_no_write_execution_service import ProjectDirectorProgrammerNoWriteExecutionService

    db_session = SessionLocal()
    try:
        service = ProjectDirectorProgrammerNoWriteExecutionService(
            session_repository=ProjectDirectorSessionRepository(db_session),
            message_repository=ProjectDirectorMessageRepository(db_session),
            task_repository=TaskRepository(db_session),
        )
        execution = service.confirm_execution(
            session_id=UUID(session_id), source_task_id=UUID(source_task_id),
            source_message_id=UUID(source_message_id), user_confirmed=True,
            requested_programmer_executor="codex", execution_mode="fake_execution",
        )
        return str(execution.message.id)
    finally:
        db_session.close()


def _prepare_project_director_chain(
    *, summary: dict[str, Any],
) -> tuple[str, str, str, str]:
    """Build full chain through P21-A dry_run.

    Returns (session_id, task_id, p21_dry_run_msg_id, p21_fake_write_msg_id).
    """
    import warnings
    warnings.filterwarnings(
        "ignore", message="Using `httpx` with `starlette.testclient` is deprecated.*", category=Warning,
    )
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        project_payload = _request_json(
            client, "POST", "/projects", 201,
            json={"name": "P21-B smoke", "summary": "P21-B smoke test.", "status": "active", "stage": "execution"},
        )
        project_id = project_payload["id"]

        session_payload = _request_json(
            client, "POST", "/project-director/sessions", 201,
            json={"project_id": project_id, "goal_text": "P21-B design lock smoke"},
        )
        session_id = session_payload["id"]
        summary["session_created"] = True
        summary["session_id"] = session_id

        p11_payload = _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run", 200,
            json={"user_goal": "P21-B evidence"},
        )
        p11_message = p11_payload.get("message") or {}

        p12_payload = _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/dry-run-task-dispatch", 200,
            json={"source_message_id": p11_message.get("id"), "user_confirmed": True},
        )
        source_task_id = p12_payload.get("created_task_id")
        p12_message = p12_payload.get("message") or {}
        source_message_id = p12_message.get("id")

        _request_json(client, "POST", "/workers/run-once", 200)

        _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/controlled-executor-dispatch", 200,
            json={
                "source_task_id": source_task_id, "source_message_id": source_message_id,
                "user_confirmed": True, "requested_agent_role": "programmer",
                "requested_executor": "codex", "launch_mode": "dry_run",
            },
        )

        p14_message_id = _record_p14_lifecycle_result(
            session_id=session_id, source_task_id=source_task_id,
            source_message_id=source_message_id, requested_executor="codex",
        )
        p15_message_id = _record_p15_review_result(
            session_id=session_id, source_task_id=source_task_id, source_message_id=p14_message_id,
        )
        p16_message_id = _record_p16_plan_result(
            session_id=session_id, source_task_id=source_task_id, source_message_id=p15_message_id,
        )
        p17_message_id = _record_p17_execution_result(
            session_id=session_id, source_task_id=source_task_id, source_message_id=p16_message_id,
        )

        # P20 preflight
        p20_payload = _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/sandbox-write-preflight", 200,
            json={
                "source_task_id": source_task_id, "source_message_id": p17_message_id,
                "user_confirmed": True, "preflight_mode": "dry_run",
                "file_operations": [
                    {
                        "path": "runtime/orchestrator/app/domain/example.py",
                        "operation": "create",
                        "reason": "P21-B smoke",
                        "patch_preview": ["PREVIEW ONLY: no repository file was modified."],
                    },
                    {
                        "path": "runtime/orchestrator/app/domain/existing.py",
                        "operation": "update",
                        "reason": "P21-B smoke update",
                        "patch_preview": ["PREVIEW ONLY: no repository file was modified."],
                    },
                ],
            },
        )
        p20_message_id = p20_payload["message"]["id"]

        # P21-A dry_run
        p21_dry_run_payload = _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/sandbox-write-execution", 200,
            json={
                "source_task_id": source_task_id, "source_message_id": p20_message_id,
                "user_confirmed": True, "execution_mode": "dry_run",
            },
        )
        p21_dry_run_msg_id = p21_dry_run_payload["message"]["id"]

        # P21-A fake_write
        p21_fake_write_payload = _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/sandbox-write-execution", 200,
            json={
                "source_task_id": source_task_id, "source_message_id": p20_message_id,
                "user_confirmed": True, "execution_mode": "fake_write",
            },
        )
        p21_fake_write_msg_id = p21_fake_write_payload["message"]["id"]

        # P21-B design lock from dry_run
        lock_dry_run_payload = _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/sandbox-write-design-lock", 200,
            json={
                "source_task_id": source_task_id, "source_message_id": p21_dry_run_msg_id,
                "user_confirmed": True, "design_lock_mode": "dry_run",
            },
        )
        summary["p21_b_dry_run_design_lock"] = lock_dry_run_payload.get("design_lock_status")
        summary["controlled_sandbox_write_enabled"] = lock_dry_run_payload.get("controlled_sandbox_write_enabled", False)
        summary["sandbox_write_allowed"] = lock_dry_run_payload.get("sandbox_write_allowed", False)
        summary["file_write_allowed"] = lock_dry_run_payload.get("file_write_allowed", False)
        summary["worktree_write_allowed"] = lock_dry_run_payload.get("worktree_write_allowed", False)
        summary["product_runtime_git_write_allowed"] = lock_dry_run_payload.get("product_runtime_git_write_allowed", False)
        summary["git_write_performed"] = lock_dry_run_payload.get("git_write_performed", False)
        summary["worker_started"] = lock_dry_run_payload.get("worker_started", False)
        summary["task_created"] = lock_dry_run_payload.get("task_created", False)
        summary["run_created"] = lock_dry_run_payload.get("run_created", False)
        summary["worktree_created"] = lock_dry_run_payload.get("worktree_created", False)
        summary["rollback_snapshot_created"] = lock_dry_run_payload.get("rollback_snapshot_created", False)

        # P21-B design lock from fake_write
        lock_fake_write_payload = _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/sandbox-write-design-lock", 200,
            json={
                "source_task_id": source_task_id, "source_message_id": p21_fake_write_msg_id,
                "user_confirmed": True, "design_lock_mode": "dry_run",
            },
        )
        summary["p21_b_fake_write_design_lock"] = lock_fake_write_payload.get("design_lock_status")

        # Blocked: user_confirmed=false
        _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/sandbox-write-design-lock", 409,
            json={
                "source_task_id": source_task_id, "source_message_id": p21_dry_run_msg_id,
                "user_confirmed": False,
            },
        )
        summary["p21_b_user_confirmed_blocked"] = "blocked"

        # Blocked: non-P21 source message
        _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/sandbox-write-design-lock", 409,
            json={
                "source_task_id": source_task_id, "source_message_id": p15_message_id,
                "user_confirmed": True,
            },
        )
        summary["p21_b_non_p21_source_blocked"] = "blocked"

        # Blocked: mismatch
        p11_b = _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run", 200,
            json={"user_goal": "P21-B second evidence"},
        )
        p11_msg_b = p11_b.get("message") or {}

        p12_b = _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/dry-run-task-dispatch", 200,
            json={"source_message_id": p11_msg_b.get("id"), "user_confirmed": True},
        )
        task_b_id = p12_b.get("created_task_id")
        p12_msg_b_id = p12_b.get("message") or {}

        _request_json(client, "POST", "/workers/run-once", 200)

        _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/controlled-executor-dispatch", 200,
            json={
                "source_task_id": task_b_id, "source_message_id": p12_msg_b_id.get("id"),
                "user_confirmed": True, "requested_agent_role": "programmer",
                "requested_executor": "codex", "launch_mode": "dry_run",
            },
        )

        p14_b = _record_p14_lifecycle_result(
            session_id=session_id, source_task_id=task_b_id,
            source_message_id=p12_msg_b_id.get("id"), requested_executor="codex",
        )
        p15_b = _record_p15_review_result(
            session_id=session_id, source_task_id=task_b_id, source_message_id=p14_b,
        )
        p16_b = _record_p16_plan_result(
            session_id=session_id, source_task_id=task_b_id, source_message_id=p15_b,
        )
        p17_b = _record_p17_execution_result(
            session_id=session_id, source_task_id=task_b_id, source_message_id=p16_b,
        )
        p20_b = _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/sandbox-write-preflight", 200,
            json={
                "source_task_id": task_b_id, "source_message_id": p17_b,
                "user_confirmed": True, "preflight_mode": "dry_run",
                "file_operations": [
                    {
                        "path": "runtime/orchestrator/app/domain/other.py",
                        "operation": "update", "reason": "test",
                        "patch_preview": ["PREVIEW ONLY: no repository file was modified."],
                    },
                ],
            },
        )
        p20_msg_b_id = p20_b["message"]["id"]

        p21_b_exec = _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/sandbox-write-execution", 200,
            json={
                "source_task_id": task_b_id, "source_message_id": p20_msg_b_id,
                "user_confirmed": True, "execution_mode": "dry_run",
            },
        )
        p21_msg_b_id = p21_b_exec["message"]["id"]

        # Mismatch: task A + P21 message from task B
        _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/sandbox-write-design-lock", 409,
            json={
                "source_task_id": source_task_id, "source_message_id": p21_msg_b_id,
                "user_confirmed": True,
            },
        )
        summary["p21_b_mismatch_blocked"] = "blocked"

        # Blocked paths tested at service level in contract tests
        summary["p21_b_runtime_write_flag_blocked"] = "blocked_via_contract"
        summary["p21_b_operation_intent_missing_blocked"] = "blocked_via_contract"

        # Message readback
        messages_payload = _request_json(
            client, "GET", f"/project-director/sessions/{session_id}/messages", 200,
        )
        messages = messages_payload.get("messages") or []
        has_lock = any(
            item.get("source_detail") == "p21_b_sandbox_write_design_lock"
            for item in messages
        )
        summary["p21_b_message_readback"] = "passed" if has_lock else "failed"

        return session_id, source_task_id, p21_dry_run_msg_id, p21_fake_write_msg_id


def run_smoke(runtime_data_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    sqlite_db_path = _configure_isolated_environment(runtime_data_dir)
    summary = _base_summary(runtime_data_dir.resolve(), sqlite_db_path.resolve())
    summary["isolated_runtime_data"] = runtime_data_dir.resolve() != DEFAULT_RUNTIME_DATA_DIR

    if not summary["isolated_runtime_data"]:
        summary["smoke_status"] = "blocked"
        summary["blocked_reasons"].append("runtime_data_dir_must_be_isolated")
        return summary

    try:
        _prepare_project_director_chain(summary=summary)
    except Exception as exc:
        summary["smoke_status"] = "failed"
        summary["blocked_reasons"].append(type(exc).__name__)
        return summary

    required_checks = (
        "session_created",
        "p21_b_dry_run_design_lock",
        "p21_b_fake_write_design_lock",
        "p21_b_user_confirmed_blocked",
        "p21_b_non_p21_source_blocked",
        "p21_b_mismatch_blocked",
        "p21_b_message_readback",
        "isolated_runtime_data",
    )
    if all(summary.get(item) for item in required_checks):
        summary["smoke_status"] = "passed"
    else:
        summary["smoke_status"] = "partial"
        summary["blocked_reasons"].append("required_smoke_check_failed")

    return summary


def main() -> int:
    args = _parse_args()
    temp_created = args.runtime_dir is None
    runtime_data_dir = (
        Path(tempfile.mkdtemp(prefix="p21-b-design-lock-smoke-"))
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
        print(f"P21-B design lock smoke: {summary['smoke_status']}")

    return 0 if summary["smoke_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
