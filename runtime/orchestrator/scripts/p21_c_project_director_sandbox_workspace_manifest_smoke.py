"""P21-C Project Director sandbox workspace manifest smoke.

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
        "p21_c_workspace_guard": None,
        "p21_c_operation_manifest_guard": None,
        "p21_c_workspace_invalid_name_blocked": None,
        "p21_c_manifest_non_p21c_source_blocked": None,
        "p21_c_workspace_user_confirmed_blocked": None,
        "p21_c_message_readback": None,
        "workspace_created": False,
        "workspace_written": False,
        "file_written": False,
        "target_file_content_read": False,
        "real_diff_generated": False,
        "patch_applied": False,
        "worktree_created": False,
        "rollback_snapshot_created": False,
        "git_write_performed": False,
        "worker_started": False,
        "task_created": False,
        "run_created": False,
        "ai_project_director_total_loop": "Partial",
        "isolated_runtime_data": False,
        "blocked_reasons": [],
        "risks": [],
        "unknowns": [],
        "runtime_data_dir": str(runtime_data_dir),
        "sqlite_db_path": str(sqlite_db_path),
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
) -> tuple[str, str]:
    """Build full chain through P21-C-B.

    Returns (session_id, source_task_id).
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
            json={"name": "P21-C smoke", "summary": "P21-C smoke test.", "status": "active", "stage": "execution"},
        )
        project_id = project_payload["id"]

        session_payload = _request_json(
            client, "POST", "/project-director/sessions", 201,
            json={"project_id": project_id, "goal_text": "P21-C workspace manifest smoke"},
        )
        session_id = session_payload["id"]
        summary["session_created"] = True
        summary["session_id"] = session_id

        p11_payload = _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run", 200,
            json={"user_goal": "P21-C evidence"},
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
                        "reason": "P21-C smoke",
                        "patch_preview": ["PREVIEW ONLY: no repository file was modified."],
                    },
                    {
                        "path": "runtime/orchestrator/app/domain/existing.py",
                        "operation": "update",
                        "reason": "P21-C smoke update",
                        "patch_preview": ["PREVIEW ONLY: no repository file was modified."],
                    },
                ],
            },
        )
        p20_message_id = p20_payload["message"]["id"]

        # P21-A execution
        p21_payload = _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/sandbox-write-execution", 200,
            json={
                "source_task_id": source_task_id, "source_message_id": p20_message_id,
                "user_confirmed": True, "execution_mode": "dry_run",
            },
        )
        p21_message_id = p21_payload["message"]["id"]

        # P21-B design lock
        lock_payload = _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/sandbox-write-design-lock", 200,
            json={
                "source_task_id": source_task_id, "source_message_id": p21_message_id,
                "user_confirmed": True,
            },
        )
        lock_message_id = lock_payload["message"]["id"]

        # P21-C-A workspace guard
        guard_payload = _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/sandbox-workspace-guard", 200,
            json={
                "source_task_id": source_task_id, "source_message_id": lock_message_id,
                "user_confirmed": True,
            },
        )
        summary["p21_c_workspace_guard"] = guard_payload.get("guard_status")
        summary["workspace_created"] = guard_payload.get("workspace_created", False)
        summary["workspace_written"] = guard_payload.get("workspace_written", False)
        guard_message_id = guard_payload["message"]["id"]

        # P21-C-B operation manifest guard
        manifest_payload = _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/sandbox-operation-manifest-guard", 200,
            json={
                "source_task_id": source_task_id, "source_message_id": guard_message_id,
                "user_confirmed": True,
            },
        )
        summary["p21_c_operation_manifest_guard"] = manifest_payload.get("manifest_status")
        summary["file_written"] = manifest_payload.get("file_written", False)
        summary["target_file_content_read"] = manifest_payload.get("target_file_content_read", False)
        summary["real_diff_generated"] = manifest_payload.get("real_diff_generated", False)
        summary["patch_applied"] = manifest_payload.get("patch_applied", False)
        summary["worktree_created"] = manifest_payload.get("worktree_created", False)
        summary["rollback_snapshot_created"] = manifest_payload.get("rollback_snapshot_created", False)
        summary["git_write_performed"] = manifest_payload.get("git_write_performed", False)
        summary["worker_started"] = manifest_payload.get("worker_started", False)
        summary["task_created"] = manifest_payload.get("task_created", False)
        summary["run_created"] = manifest_payload.get("run_created", False)

        # Blocked: user_confirmed=false
        _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/sandbox-workspace-guard", 409,
            json={
                "source_task_id": source_task_id, "source_message_id": lock_message_id,
                "user_confirmed": False,
            },
        )
        summary["p21_c_workspace_user_confirmed_blocked"] = "blocked"

        # Blocked: invalid workspace name
        _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/sandbox-workspace-guard", 409,
            json={
                "source_task_id": source_task_id, "source_message_id": lock_message_id,
                "user_confirmed": True,
                "requested_workspace_name": "../escape",
            },
        )
        summary["p21_c_workspace_invalid_name_blocked"] = "blocked"

        # Blocked: non-P21-C-A source for manifest
        _request_json(
            client, "POST", f"/project-director/sessions/{session_id}/sandbox-operation-manifest-guard", 409,
            json={
                "source_task_id": source_task_id, "source_message_id": lock_message_id,
                "user_confirmed": True,
            },
        )
        summary["p21_c_manifest_non_p21c_source_blocked"] = "blocked"

        # Message readback
        messages_payload = _request_json(
            client, "GET", f"/project-director/sessions/{session_id}/messages", 200,
        )
        messages = messages_payload.get("messages") or []
        has_guard = any(
            item.get("source_detail") == "p21_c_sandbox_workspace_guard"
            for item in messages
        )
        has_manifest = any(
            item.get("source_detail") == "p21_c_sandbox_operation_manifest_guard"
            for item in messages
        )
        summary["p21_c_message_readback"] = "passed" if (has_guard and has_manifest) else "failed"

        return session_id, source_task_id


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
        "p21_c_workspace_guard",
        "p21_c_operation_manifest_guard",
        "p21_c_workspace_invalid_name_blocked",
        "p21_c_manifest_non_p21c_source_blocked",
        "p21_c_workspace_user_confirmed_blocked",
        "p21_c_message_readback",
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
        Path(tempfile.mkdtemp(prefix="p21-c-workspace-manifest-smoke-"))
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
        print(f"P21-C workspace manifest smoke: {summary['smoke_status']}")

    return 0 if summary["smoke_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
