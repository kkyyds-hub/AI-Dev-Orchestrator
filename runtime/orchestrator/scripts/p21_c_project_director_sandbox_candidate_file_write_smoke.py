"""P21-C-E Project Director sandbox candidate business file write smoke.

Uses isolated runtime data and does not start Codex, Claude Code, Worker
subprocesses, worktree writes, main project file writes, patch application,
or product runtime Git writes.
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
        "--keep-temp-data", action="store_true",
        help="Keep the isolated runtime data directory after the smoke finishes.",
    )
    parser.add_argument(
        "--runtime-dir", type=Path,
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
        "p21_c_workspace_create": None,
        "p21_c_workspace_manifest_write": None,
        "p21_c_candidate_files_write": None,
        "p21_c_candidate_files_write_user_confirmed_blocked": None,
        "p21_c_candidate_files_write_non_manifest_write_source_blocked": None,
        "p21_c_candidate_files_write_task_mismatch_blocked": None,
        "p21_c_candidate_files_write_path_not_declared_blocked": None,
        "p21_c_candidate_files_write_internal_dir_blocked": None,
        "p21_c_message_readback": None,
        "isolated_runtime_data": False,
        "workspace_path": None,
        "workspace_exists": False,
        "workspace_is_dir": False,
        "internal_manifest_file_exists": False,
        "candidate_file_path": None,
        "candidate_file_exists": False,
        "candidate_file_content_matches": False,
        "candidate_file_within_workspace": False,
        "candidate_file_not_under_internal_dir": False,
        "candidate_business_files_written": False,
        "business_file_written": False,
        "manifest_file_written": False,
        "target_file_content_read": False,
        "real_diff_generated": False,
        "patch_applied": False,
        "worktree_created": False,
        "rollback_snapshot_created": False,
        "git_write_performed": False,
        "worker_started": False,
        "task_created": False,
        "run_created": False,
        "cleanup_required": False,
        "ai_project_director_total_loop": "Partial",
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


def _request_json(client: Any, method: str, path: str, expected_status: int, **kwargs: Any) -> dict[str, Any] | list[Any]:
    response = getattr(client, method.lower())(path, **kwargs)
    if response.status_code != expected_status:
        raise RuntimeError(
            f"{method} {path} returned HTTP {response.status_code}, body: {response.text[:500]}"
        )
    return response.json()


def _record_p14_lifecycle_result(*, session_id: str, source_task_id: str, source_message_id: str, requested_executor: str) -> str:
    from app.core.db import SessionLocal
    from app.domain.project_director_controlled_executor_dispatch import ProjectDirectorControlledExecutorLifecycleResult
    from app.repositories.project_director_message_repository import ProjectDirectorMessageRepository
    from app.repositories.project_director_session_repository import ProjectDirectorSessionRepository
    from app.repositories.task_repository import TaskRepository
    from app.services.project_director_controlled_executor_dispatch_service import P14_LIFECYCLE_RESULT_SOURCE_DETAIL, ProjectDirectorControlledExecutorDispatchService

    db = SessionLocal()
    try:
        svc = ProjectDirectorControlledExecutorDispatchService(
            session_repository=ProjectDirectorSessionRepository(db),
            message_repository=ProjectDirectorMessageRepository(db),
            task_repository=TaskRepository(db),
        )
        msg = svc.record_lifecycle_result(
            result=ProjectDirectorControlledExecutorLifecycleResult(
                session_id=UUID(session_id), source_task_id=UUID(source_task_id),
                source_message_id=UUID(source_message_id), requested_agent_role="programmer",
                requested_executor=requested_executor, launch_mode="dry_run",
                native_executor_started=False, codex_started=False, claude_code_started=False,
                agent_session_bound=False, runtime_handle_id_present=False,
                process_handle_id_present=False, supervisor_registered=False,
                terminate_attempted=False, supervisor_cleanup_done=False,
                run_created=True, real_code_modified=False, git_write_performed=False,
                p9_production_safe_long_running_executor_lifecycle="Partial",
            ),
            source_detail=P14_LIFECYCLE_RESULT_SOURCE_DETAIL,
        )
        return str(msg.id)
    finally:
        db.close()


def _record_p15_review_result(*, session_id: str, source_task_id: str, source_message_id: str) -> str:
    from app.core.db import SessionLocal
    from app.repositories.project_director_message_repository import ProjectDirectorMessageRepository
    from app.repositories.project_director_session_repository import ProjectDirectorSessionRepository
    from app.repositories.task_repository import TaskRepository
    from app.services.project_director_readonly_review_service import ProjectDirectorReadonlyReviewService

    db = SessionLocal()
    try:
        svc = ProjectDirectorReadonlyReviewService(
            session_repository=ProjectDirectorSessionRepository(db),
            message_repository=ProjectDirectorMessageRepository(db),
            task_repository=TaskRepository(db),
        )
        r = svc.confirm_review(
            session_id=UUID(session_id), source_task_id=UUID(source_task_id),
            source_message_id=UUID(source_message_id), user_confirmed=True,
            requested_reviewer_executor="codex", review_mode="fake_review",
        )
        return str(r.message.id)
    finally:
        db.close()


def _record_p16_plan_result(*, session_id: str, source_task_id: str, source_message_id: str) -> str:
    from app.core.db import SessionLocal
    from app.repositories.project_director_message_repository import ProjectDirectorMessageRepository
    from app.repositories.project_director_session_repository import ProjectDirectorSessionRepository
    from app.repositories.task_repository import TaskRepository
    from app.services.project_director_programmer_no_write_plan_service import ProjectDirectorProgrammerNoWritePlanService

    db = SessionLocal()
    try:
        svc = ProjectDirectorProgrammerNoWritePlanService(
            session_repository=ProjectDirectorSessionRepository(db),
            message_repository=ProjectDirectorMessageRepository(db),
            task_repository=TaskRepository(db),
        )
        r = svc.confirm_plan(
            session_id=UUID(session_id), source_task_id=UUID(source_task_id),
            source_message_id=UUID(source_message_id), user_confirmed=True,
            requested_programmer_executor="codex", planning_mode="fake_plan",
        )
        return str(r.message.id)
    finally:
        db.close()


def _record_p17_execution_result(*, session_id: str, source_task_id: str, source_message_id: str) -> str:
    from app.core.db import SessionLocal
    from app.repositories.project_director_message_repository import ProjectDirectorMessageRepository
    from app.repositories.project_director_session_repository import ProjectDirectorSessionRepository
    from app.repositories.task_repository import TaskRepository
    from app.services.project_director_programmer_no_write_execution_service import ProjectDirectorProgrammerNoWriteExecutionService

    db = SessionLocal()
    try:
        svc = ProjectDirectorProgrammerNoWriteExecutionService(
            session_repository=ProjectDirectorSessionRepository(db),
            message_repository=ProjectDirectorMessageRepository(db),
            task_repository=TaskRepository(db),
        )
        r = svc.confirm_execution(
            session_id=UUID(session_id), source_task_id=UUID(source_task_id),
            source_message_id=UUID(source_message_id), user_confirmed=True,
            requested_programmer_executor="codex", execution_mode="fake_execution",
        )
        return str(r.message.id)
    finally:
        db.close()


def _prepare_project_director_chain(*, summary: dict[str, Any]) -> tuple[str, str]:
    """Build full chain through P21-C-E. Returns (session_id, source_task_id)."""
    import warnings
    warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient` is deprecated.*", category=Warning)
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        proj = _request_json(client, "POST", "/projects", 201,
            json={"name": "P21-C-E smoke", "summary": "P21-C-E smoke.", "status": "active", "stage": "execution"})
        proj_id = proj["id"]

        sess = _request_json(client, "POST", "/project-director/sessions", 201,
            json={"project_id": proj_id, "goal_text": "P21-C-E candidate file write smoke"})
        session_id = sess["id"]
        summary["session_created"] = True
        summary["session_id"] = session_id

        p11 = _request_json(client, "POST", f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run", 200,
            json={"user_goal": "P21-C-E evidence"})
        p11_msg = p11.get("message") or {}

        p12 = _request_json(client, "POST", f"/project-director/sessions/{session_id}/dry-run-task-dispatch", 200,
            json={"source_message_id": p11_msg.get("id"), "user_confirmed": True})
        source_task_id = p12.get("created_task_id")
        p12_msg = p12.get("message") or {}
        source_message_id = p12_msg.get("id")

        _request_json(client, "POST", "/workers/run-once", 200)

        _request_json(client, "POST", f"/project-director/sessions/{session_id}/controlled-executor-dispatch", 200,
            json={"source_task_id": source_task_id, "source_message_id": source_message_id,
                  "user_confirmed": True, "requested_agent_role": "programmer",
                  "requested_executor": "codex", "launch_mode": "dry_run"})

        p14_id = _record_p14_lifecycle_result(session_id=session_id, source_task_id=source_task_id,
            source_message_id=source_message_id, requested_executor="codex")
        p15_id = _record_p15_review_result(session_id=session_id, source_task_id=source_task_id, source_message_id=p14_id)
        p16_id = _record_p16_plan_result(session_id=session_id, source_task_id=source_task_id, source_message_id=p15_id)
        p17_id = _record_p17_execution_result(session_id=session_id, source_task_id=source_task_id, source_message_id=p16_id)

        # P20
        p20 = _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-write-preflight", 200,
            json={"source_task_id": source_task_id, "source_message_id": p17_id,
                  "user_confirmed": True, "preflight_mode": "dry_run",
                  "file_operations": [
                      {"path": "runtime/orchestrator/app/domain/example.py", "operation": "create",
                       "reason": "P21-C-E smoke", "patch_preview": ["PREVIEW ONLY: no repository file was modified."]}]})
        p20_id = p20["message"]["id"]

        # P21-A
        p21 = _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-write-execution", 200,
            json={"source_task_id": source_task_id, "source_message_id": p20_id,
                  "user_confirmed": True, "execution_mode": "dry_run"})
        p21_id = p21["message"]["id"]

        # P21-B
        lock = _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-write-design-lock", 200,
            json={"source_task_id": source_task_id, "source_message_id": p21_id, "user_confirmed": True})
        lock_id = lock["message"]["id"]

        # P21-C-A
        guard = _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-workspace-guard", 200,
            json={"source_task_id": source_task_id, "source_message_id": lock_id, "user_confirmed": True})
        summary["p21_c_workspace_guard"] = guard.get("guard_status")
        guard_id = guard["message"]["id"]

        # P21-C-B
        manifest = _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-operation-manifest-guard", 200,
            json={"source_task_id": source_task_id, "source_message_id": guard_id, "user_confirmed": True})
        summary["p21_c_operation_manifest_guard"] = manifest.get("manifest_status")
        manifest_id = manifest["message"]["id"]

        # P21-C-C
        create = _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-workspace-create", 200,
            json={"source_task_id": source_task_id, "source_message_id": manifest_id, "user_confirmed": True})
        summary["p21_c_workspace_create"] = create.get("creation_status")
        create_id = create["message"]["id"]

        # P21-C-D
        write = _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-workspace-evidence-manifest", 200,
            json={"source_task_id": source_task_id, "source_message_id": create_id, "user_confirmed": True})
        summary["p21_c_workspace_manifest_write"] = write.get("manifest_write_status")
        write_id = write["message"]["id"]

        # P21-C-E (first call - written)
        candidate_content = "print('P21-C-E smoke test')\n"
        ce = _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-candidate-files-write", 200,
            json={"source_task_id": source_task_id, "source_message_id": write_id, "user_confirmed": True,
                  "candidate_files": [
                      {"relative_path": "runtime/orchestrator/app/domain/example.py",
                       "content": candidate_content, "operation": "create"}]})
        summary["p21_c_candidate_files_write"] = ce.get("candidate_write_status")
        summary["workspace_path"] = ce.get("workspace_path")
        summary["candidate_business_files_written"] = ce.get("candidate_business_files_written", False)
        summary["business_file_written"] = ce.get("business_file_written", False)
        summary["manifest_file_written"] = ce.get("manifest_file_written", False)
        summary["target_file_content_read"] = ce.get("target_file_content_read", False)
        summary["real_diff_generated"] = ce.get("real_diff_generated", False)
        summary["patch_applied"] = ce.get("patch_applied", False)
        summary["worktree_created"] = ce.get("worktree_created", False)
        summary["rollback_snapshot_created"] = ce.get("rollback_snapshot_created", False)
        summary["git_write_performed"] = ce.get("git_write_performed", False)
        summary["worker_started"] = ce.get("worker_started", False)
        summary["task_created"] = ce.get("task_created", False)
        summary["run_created"] = ce.get("run_created", False)
        summary["cleanup_required"] = ce.get("cleanup_required", False)

        # Verify workspace
        ws_path = Path(ce.get("workspace_path", ""))
        summary["workspace_exists"] = ws_path.exists() if str(ws_path) else False
        summary["workspace_is_dir"] = ws_path.is_dir() if ws_path.exists() else False

        # Verify internal manifest
        manifest_path = ws_path / ".ai-project-director" / "workspace-manifest.json"
        summary["internal_manifest_file_exists"] = manifest_path.exists() if ws_path.exists() else False

        # Verify candidate file
        written_files = ce.get("candidate_written_files", [])
        if written_files:
            cf_path = Path(written_files[0].get("workspace_file_path", ""))
            summary["candidate_file_path"] = str(cf_path)
            summary["candidate_file_exists"] = cf_path.exists()
            if cf_path.exists():
                actual = cf_path.read_text(encoding="utf-8")
                summary["candidate_file_content_matches"] = actual == candidate_content
            summary["candidate_file_within_workspace"] = str(cf_path).startswith(str(ws_path))
            summary["candidate_file_not_under_internal_dir"] = ".ai-project-director" not in str(cf_path)

        # Blocked: user_confirmed=false
        _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-candidate-files-write", 409,
            json={"source_task_id": source_task_id, "source_message_id": write_id, "user_confirmed": False,
                  "candidate_files": [{"relative_path": "x.py", "content": "x", "operation": "create"}]})
        summary["p21_c_candidate_files_write_user_confirmed_blocked"] = "blocked"

        # Blocked: non-P21-C-D source
        _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-candidate-files-write", 409,
            json={"source_task_id": source_task_id, "source_message_id": create_id, "user_confirmed": True,
                  "candidate_files": [{"relative_path": "x.py", "content": "x", "operation": "create"}]})
        summary["p21_c_candidate_files_write_non_manifest_write_source_blocked"] = "blocked"

        # Blocked: task mismatch
        p11b = _request_json(client, "POST", f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run", 200,
            json={"user_goal": "P21-C-E second evidence"})
        p11b_msg = p11b.get("message") or {}
        p12b = _request_json(client, "POST", f"/project-director/sessions/{session_id}/dry-run-task-dispatch", 200,
            json={"source_message_id": p11b_msg.get("id"), "user_confirmed": True})
        task_b_id = p12b.get("created_task_id")
        _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-candidate-files-write", 409,
            json={"source_task_id": task_b_id, "source_message_id": write_id, "user_confirmed": True,
                  "candidate_files": [{"relative_path": "x.py", "content": "x", "operation": "create"}]})
        summary["p21_c_candidate_files_write_task_mismatch_blocked"] = "blocked"

        # Blocked: path not declared by manifest
        _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-candidate-files-write", 409,
            json={"source_task_id": source_task_id, "source_message_id": write_id, "user_confirmed": True,
                  "candidate_files": [{"relative_path": "src/undeclared.py", "content": "x", "operation": "create"}]})
        summary["p21_c_candidate_files_write_path_not_declared_blocked"] = "blocked"

        # Blocked: path under internal dir
        _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-candidate-files-write", 409,
            json={"source_task_id": source_task_id, "source_message_id": write_id, "user_confirmed": True,
                  "candidate_files": [{"relative_path": ".ai-project-director/extra.json", "content": "{}", "operation": "create"}]})
        summary["p21_c_candidate_files_write_internal_dir_blocked"] = "blocked"

        # Message readback
        msgs = _request_json(client, "GET", f"/project-director/sessions/{session_id}/messages", 200)
        messages = msgs.get("messages") or []
        has_write = any(m.get("source_detail") == "p21_c_sandbox_candidate_files_written" for m in messages)
        summary["p21_c_message_readback"] = "passed" if has_write else "failed"

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

    required = (
        "session_created", "p21_c_workspace_guard", "p21_c_operation_manifest_guard",
        "p21_c_workspace_create", "p21_c_workspace_manifest_write",
        "p21_c_candidate_files_write",
        "p21_c_candidate_files_write_user_confirmed_blocked",
        "p21_c_candidate_files_write_non_manifest_write_source_blocked",
        "p21_c_candidate_files_write_task_mismatch_blocked",
        "p21_c_candidate_files_write_path_not_declared_blocked",
        "p21_c_candidate_files_write_internal_dir_blocked",
        "p21_c_message_readback", "isolated_runtime_data",
        "candidate_file_exists", "candidate_file_content_matches",
        "candidate_file_within_workspace", "candidate_file_not_under_internal_dir",
        "internal_manifest_file_exists",
    )
    if all(summary.get(k) for k in required):
        summary["smoke_status"] = "passed"
    else:
        summary["smoke_status"] = "partial"
        summary["blocked_reasons"].append("required_smoke_check_failed")

    return summary


def main() -> int:
    args = _parse_args()
    temp_created = args.runtime_dir is None
    runtime_data_dir = (
        Path(tempfile.mkdtemp(prefix="p21-c-candidate-file-write-smoke-"))
        if args.runtime_dir is None
        else args.runtime_dir
    ).resolve()
    runtime_data_dir.mkdir(parents=True, exist_ok=True)

    try:
        summary = run_smoke(runtime_data_dir, args)
    finally:
        if temp_created and not args.keep_temp_data:
            shutil.rmtree(runtime_data_dir, ignore_errors=True)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    else:
        print(f"P21-C-E candidate file write smoke: {summary['smoke_status']}")

    return 0 if summary["smoke_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
