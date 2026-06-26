"""P20 Project Director sandbox write preflight smoke.

Default and fake-preflight paths use isolated runtime data and do not start Codex,
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
        "--preflight-mode",
        choices=("dry_run", "fake_preflight", "controlled_sandbox_write"),
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
        "project_id_present": False,
        "p11_dry_run_message_bound": False,
        "p12_safe_task_created": False,
        "p12_worker_run_once_ok": False,
        "p13_dispatch_message_bound": False,
        "p14_lifecycle_result_message_bound": False,
        "p15_review_message_bound": False,
        "p16_plan_message_bound": False,
        "p17_execution_message_bound": False,
        "p20_preflight_message_bound": False,
        "message_readback_ok": False,
        "preflight_mode": "dry_run",
        "policy_only_preflight": True,
        "preflight_status": None,
        "checked_operations_count": 0,
        "allowed_operations_count": 0,
        "blocked_operations_count": 0,
        "accepted_operation_paths_count": 0,
        "blocked_operation_paths_count": 0,
        "path_policy_results_count": 0,
        "recommended_next_step_present": False,
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
        raise RuntimeError(f"{method} {path} returned HTTP {response.status_code}")
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
                "name": "P20 sandbox write preflight smoke",
                "summary": "Isolated Project Director sandbox write preflight smoke.",
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
            json={"project_id": project_id, "goal_text": "P20 sandbox write preflight"},
        )
        session_id = session_payload["id"]
        summary["session_created"] = bool(session_id)
        summary["session_id"] = session_id

        p11_payload = _request_json(
            client,
            "POST",
            f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
            200,
            json={"user_goal": "P20 evidence-to-agent source message"},
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
                "requested_agent_role": "programmer",
                "requested_executor": args.programmer_executor,
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
            requested_executor=args.programmer_executor,
        )
        summary["p14_lifecycle_result_message_bound"] = bool(p14_message_id)

        p15_message_id = _record_p15_review_result(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=p14_message_id,
        )
        summary["p15_review_message_bound"] = bool(p15_message_id)

        p16_message_id = _record_p16_plan_result(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=p15_message_id,
        )
        summary["p16_plan_message_bound"] = bool(p16_message_id)

        p17_message_id = _record_p17_execution_result(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=p16_message_id,
        )
        summary["p17_execution_message_bound"] = bool(p17_message_id)

        # P20 sandbox write preflight
        p20_payload = _request_json(
            client,
            "POST",
            f"/project-director/sessions/{session_id}/sandbox-write-preflight",
            200,
            json={
                "source_task_id": source_task_id,
                "source_message_id": p17_message_id,
                "user_confirmed": True,
                "preflight_mode": args.preflight_mode,
                "file_operations": [
                    {
                        "path": "runtime/orchestrator/app/domain/example.py",
                        "operation": "update",
                        "reason": "sandbox write preflight smoke test",
                        "patch_preview": ["PREVIEW ONLY: no repository file was modified."],
                    }
                ],
            },
        )

        summary["p20_preflight_message_bound"] = bool(
            p20_payload.get("preflight_message_bound")
        )
        summary["policy_only_preflight"] = p20_payload.get("policy_only_preflight", False)
        summary["preflight_status"] = p20_payload.get("preflight_status")
        summary["checked_operations_count"] = p20_payload.get("checked_operations_count", 0)
        summary["allowed_operations_count"] = p20_payload.get("allowed_operations_count", 0)
        summary["blocked_operations_count"] = p20_payload.get("blocked_operations_count", 0)
        summary["accepted_operation_paths_count"] = len(
            p20_payload.get("accepted_operation_paths") or []
        )
        summary["blocked_operation_paths_count"] = len(
            p20_payload.get("blocked_operation_paths") or []
        )
        summary["path_policy_results_count"] = len(
            p20_payload.get("path_policy_results") or []
        )
        summary["recommended_next_step_present"] = bool(
            p20_payload.get("recommended_next_step")
        )
        summary["sandbox_write_allowed"] = p20_payload.get("sandbox_write_allowed", False)
        summary["product_runtime_git_write_allowed"] = p20_payload.get(
            "product_runtime_git_write_allowed", False
        )
        summary["main_worktree_write_allowed"] = p20_payload.get(
            "main_worktree_write_allowed", False
        )
        summary["worktree_write_allowed"] = p20_payload.get("worktree_write_allowed", False)
        summary["file_write_allowed"] = p20_payload.get("file_write_allowed", False)
        summary["actual_patch_applied"] = p20_payload.get("actual_patch_applied", False)
        summary["real_code_modified"] = p20_payload.get("real_code_modified", False)
        summary["git_write_performed"] = p20_payload.get("git_write_performed", False)
        summary["native_executor_started"] = p20_payload.get("native_executor_started", False)
        summary["codex_started"] = p20_payload.get("codex_started", False)
        summary["claude_code_started"] = p20_payload.get("claude_code_started", False)
        summary["worker_started"] = p20_payload.get("worker_started", False)
        summary["task_created"] = p20_payload.get("task_created", False)
        summary["run_created"] = p20_payload.get("run_created", False)
        summary["risks"] = p20_payload.get("risks", [])
        summary["unknowns"] = p20_payload.get("unknowns", [])

        messages_payload = _request_json(
            client,
            "GET",
            f"/project-director/sessions/{session_id}/messages",
            200,
        )
        messages = messages_payload.get("messages") or []
        has_p20 = any(
            item.get("source_detail") == "p20_sandbox_write_preflight"
            for item in messages
        )
        summary["message_readback_ok"] = has_p20


def run_smoke(runtime_data_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    sqlite_db_path = _configure_isolated_environment(runtime_data_dir)
    summary = _base_summary(runtime_data_dir.resolve(), sqlite_db_path.resolve())
    summary["isolated_runtime_data"] = runtime_data_dir.resolve() != DEFAULT_RUNTIME_DATA_DIR
    summary["preflight_mode"] = args.preflight_mode

    if not summary["isolated_runtime_data"]:
        summary["smoke_status"] = "blocked"
        summary["blocked_reasons"].append("runtime_data_dir_must_be_isolated")
        return summary

    if args.preflight_mode == "controlled_sandbox_write":
        summary["smoke_status"] = "blocked"
        summary["blocked_reasons"].append("controlled_sandbox_write_not_enabled_in_api")
        return summary

    try:
        _prepare_project_director_chain(summary=summary, args=args)
    except Exception as exc:
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
        "p16_plan_message_bound",
        "p17_execution_message_bound",
        "p20_preflight_message_bound",
        "message_readback_ok",
        "recommended_next_step_present",
        "isolated_runtime_data",
    )
    if all(summary[item] for item in required_checks):
        summary["smoke_status"] = (
            "passed_fake_preflight"
            if args.preflight_mode == "fake_preflight"
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
        Path(tempfile.mkdtemp(prefix="p20-sandbox-write-preflight-smoke-"))
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
        print(f"P20 sandbox write preflight smoke: {summary['smoke_status']}")

    return (
        0
        if summary["smoke_status"] in {
            "passed_dry_run",
            "passed_fake_preflight",
            "passed_controlled_sandbox_write",
        }
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
