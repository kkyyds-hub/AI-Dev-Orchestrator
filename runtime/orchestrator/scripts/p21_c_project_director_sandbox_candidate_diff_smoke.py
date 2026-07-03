"""P21-C-F Project Director sandbox candidate readonly diff generation smoke.

Uses isolated runtime data and does not start Codex, Claude Code, Worker
subprocesses, write files, apply patches, or perform Git writes.
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
    parser.add_argument("--keep-temp-data", action="store_true")
    parser.add_argument("--runtime-dir", type=Path)
    return parser.parse_args()


def _base_summary(runtime_data_dir: Path, sqlite_db_path: Path) -> dict[str, Any]:
    return {
        "smoke_status": "failed", "session_created": False, "session_id": None,
        "p21_c_workspace_guard": None, "p21_c_operation_manifest_guard": None,
        "p21_c_workspace_create": None, "p21_c_workspace_manifest_write": None,
        "p21_c_candidate_files_write": None, "p21_c_candidate_diff_generate": None,
        "p21_c_candidate_diff_user_confirmed_blocked": None,
        "p21_c_candidate_diff_non_candidate_write_source_blocked": None,
        "p21_c_candidate_diff_task_mismatch_blocked": None,
        "p21_c_candidate_diff_too_large_blocked": None,
        "p21_c_message_readback": None,
        "isolated_runtime_data": False, "workspace_path": None,
        "workspace_exists": False, "workspace_is_dir": False,
        "internal_manifest_file_exists": False,
        "candidate_file_path": None, "candidate_file_exists": False,
        "candidate_file_content_unchanged": False,
        "unified_diff_returned": False, "diff_file_written": False,
        "main_project_file_written": False, "sandbox_file_written": False,
        "manifest_file_written": False, "target_file_content_read": False,
        "candidate_file_content_read": False,
        "readonly_real_diff_generated": False, "real_diff_generated": False,
        "patch_applied": False, "worktree_created": False,
        "rollback_snapshot_created": False, "git_write_performed": False,
        "worker_started": False, "task_created": False, "run_created": False,
        "cleanup_required": False, "ai_project_director_total_loop": "Partial",
        "blocked_reasons": [], "risks": [], "unknowns": [],
        "runtime_data_dir": str(runtime_data_dir), "sqlite_db_path": str(sqlite_db_path),
    }


def _configure_isolated_environment(runtime_data_dir: Path) -> Path:
    sqlite_db_path = runtime_data_dir / "db" / "orchestrator.db"
    os.environ["RUNTIME_DATA_DIR"] = str(runtime_data_dir)
    os.environ["SQLITE_DB_PATH"] = str(sqlite_db_path)
    os.environ["WORKER_SIMULATE_EXECUTION_OVERRIDE"] = "true"
    os.environ.pop("OPENAI_API_KEY", None)
    return sqlite_db_path


def _request_json(client: Any, method: str, path: str, expected_status: int, **kwargs: Any) -> dict[str, Any]:
    response = getattr(client, method.lower())(path, **kwargs)
    if response.status_code != expected_status:
        raise RuntimeError(f"{method} {path} returned HTTP {response.status_code}, body: {response.text[:500]}")
    return response.json()


def _record_p14(*, session_id: str, source_task_id: str, source_message_id: str) -> str:
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
                requested_executor="codex", launch_mode="dry_run",
                native_executor_started=False, codex_started=False, claude_code_started=False,
                agent_session_bound=False, runtime_handle_id_present=False,
                process_handle_id_present=False, supervisor_registered=False,
                terminate_attempted=False, supervisor_cleanup_done=False,
                run_created=True, real_code_modified=False, git_write_performed=False,
                p9_production_safe_long_running_executor_lifecycle="Partial",
            ), source_detail=P14_LIFECYCLE_RESULT_SOURCE_DETAIL,
        )
        return str(msg.id)
    finally:
        db.close()


def _record_p15(*, session_id: str, source_task_id: str, source_message_id: str) -> str:
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
        r = svc.confirm_review(session_id=UUID(session_id), source_task_id=UUID(source_task_id),
                               source_message_id=UUID(source_message_id), user_confirmed=True,
                               requested_reviewer_executor="codex", review_mode="fake_review")
        return str(r.message.id)
    finally:
        db.close()


def _record_p16(*, session_id: str, source_task_id: str, source_message_id: str) -> str:
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
        r = svc.confirm_plan(session_id=UUID(session_id), source_task_id=UUID(source_task_id),
                             source_message_id=UUID(source_message_id), user_confirmed=True,
                             requested_programmer_executor="codex", planning_mode="fake_plan")
        return str(r.message.id)
    finally:
        db.close()


def _record_p17(*, session_id: str, source_task_id: str, source_message_id: str) -> str:
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
        r = svc.confirm_execution(session_id=UUID(session_id), source_task_id=UUID(source_task_id),
                                  source_message_id=UUID(source_message_id), user_confirmed=True,
                                  requested_programmer_executor="codex", execution_mode="fake_execution")
        return str(r.message.id)
    finally:
        db.close()


def _prepare_chain(*, summary: dict[str, Any]) -> tuple[str, str]:
    import warnings
    warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient` is deprecated.*", category=Warning)
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        proj = _request_json(client, "POST", "/projects", 201,
            json={"name": "P21-C-F smoke", "summary": "P21-C-F smoke.", "status": "active", "stage": "execution"})
        sess = _request_json(client, "POST", "/project-director/sessions", 201,
            json={"project_id": proj["id"], "goal_text": "P21-C-F diff generation smoke"})
        session_id = sess["id"]
        summary["session_created"] = True
        summary["session_id"] = session_id

        p11 = _request_json(client, "POST", f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run", 200,
            json={"user_goal": "P21-C-F evidence"})
        p12 = _request_json(client, "POST", f"/project-director/sessions/{session_id}/dry-run-task-dispatch", 200,
            json={"source_message_id": p11["message"]["id"], "user_confirmed": True})
        source_task_id = p12["created_task_id"]
        p12_msg_id = p12["message"]["id"]

        _request_json(client, "POST", "/workers/run-once", 200)
        _request_json(client, "POST", f"/project-director/sessions/{session_id}/controlled-executor-dispatch", 200,
            json={"source_task_id": source_task_id, "source_message_id": p12_msg_id,
                  "user_confirmed": True, "requested_agent_role": "programmer",
                  "requested_executor": "codex", "launch_mode": "dry_run"})

        p14_id = _record_p14(session_id=session_id, source_task_id=source_task_id, source_message_id=p12_msg_id)
        p15_id = _record_p15(session_id=session_id, source_task_id=source_task_id, source_message_id=p14_id)
        p16_id = _record_p16(session_id=session_id, source_task_id=source_task_id, source_message_id=p15_id)
        p17_id = _record_p17(session_id=session_id, source_task_id=source_task_id, source_message_id=p16_id)

        p20 = _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-write-preflight", 200,
            json={"source_task_id": source_task_id, "source_message_id": p17_id,
                  "user_confirmed": True, "preflight_mode": "dry_run",
                  "file_operations": [
                      {"path": "runtime/orchestrator/app/domain/new_module.py", "operation": "create",
                       "reason": "P21-C-F smoke", "patch_preview": ["PREVIEW ONLY: no repository file was modified."]}]})
        p21 = _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-write-execution", 200,
            json={"source_task_id": source_task_id, "source_message_id": p20["message"]["id"],
                  "user_confirmed": True, "execution_mode": "dry_run"})
        lock = _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-write-design-lock", 200,
            json={"source_task_id": source_task_id, "source_message_id": p21["message"]["id"], "user_confirmed": True})
        guard = _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-workspace-guard", 200,
            json={"source_task_id": source_task_id, "source_message_id": lock["message"]["id"], "user_confirmed": True})
        summary["p21_c_workspace_guard"] = guard.get("guard_status")
        manifest = _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-operation-manifest-guard", 200,
            json={"source_task_id": source_task_id, "source_message_id": guard["message"]["id"], "user_confirmed": True})
        summary["p21_c_operation_manifest_guard"] = manifest.get("manifest_status")
        create = _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-workspace-create", 200,
            json={"source_task_id": source_task_id, "source_message_id": manifest["message"]["id"], "user_confirmed": True})
        summary["p21_c_workspace_create"] = create.get("creation_status")
        write = _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-workspace-evidence-manifest", 200,
            json={"source_task_id": source_task_id, "source_message_id": create["message"]["id"], "user_confirmed": True})
        summary["p21_c_workspace_manifest_write"] = write.get("manifest_write_status")

        candidate_content = "print('new module')\n"
        ce = _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-candidate-files-write", 200,
            json={"source_task_id": source_task_id, "source_message_id": write["message"]["id"],
                  "user_confirmed": True,
                  "candidate_files": [{"relative_path": "runtime/orchestrator/app/domain/new_module.py",
                                       "content": candidate_content, "operation": "create"}]})
        summary["p21_c_candidate_files_write"] = ce.get("candidate_write_status")
        ce_msg_id = ce["message"]["id"]

        # Store candidate file info before diff
        ws_path = Path(ce.get("workspace_path", ""))
        summary["workspace_path"] = str(ws_path)
        summary["workspace_exists"] = ws_path.exists()
        summary["workspace_is_dir"] = ws_path.is_dir() if ws_path.exists() else False
        manifest_path = ws_path / ".ai-project-director" / "workspace-manifest.json"
        summary["internal_manifest_file_exists"] = manifest_path.exists()
        candidate_path = ws_path / "runtime" / "orchestrator" / "app" / "domain" / "new_module.py"
        summary["candidate_file_path"] = str(candidate_path)
        candidate_existed = candidate_path.exists()
        summary["candidate_file_exists"] = candidate_existed
        candidate_content_before = candidate_path.read_text(encoding="utf-8") if candidate_existed else ""

        # P21-C-F diff generate
        diff = _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-candidate-diff-generate", 200,
            json={"source_task_id": source_task_id, "source_message_id": ce_msg_id, "user_confirmed": True})
        summary["p21_c_candidate_diff_generate"] = diff.get("diff_generation_status")
        summary["unified_diff_returned"] = bool(diff.get("unified_diff_text"))
        summary["diff_file_written"] = False  # P21-C-F never writes diff files
        summary["main_project_file_written"] = diff.get("main_project_file_written", False)
        summary["sandbox_file_written"] = diff.get("sandbox_file_written", False)
        summary["manifest_file_written"] = diff.get("manifest_file_written", False)
        summary["target_file_content_read"] = diff.get("target_file_content_read", False)
        summary["candidate_file_content_read"] = diff.get("candidate_file_content_read", False)
        summary["readonly_real_diff_generated"] = diff.get("readonly_real_diff_generated", False)
        summary["real_diff_generated"] = diff.get("real_diff_generated", False)
        summary["patch_applied"] = diff.get("patch_applied", False)
        summary["worktree_created"] = diff.get("worktree_created", False)
        summary["rollback_snapshot_created"] = diff.get("rollback_snapshot_created", False)
        summary["git_write_performed"] = diff.get("git_write_performed", False)
        summary["worker_started"] = diff.get("worker_started", False)
        summary["task_created"] = diff.get("task_created", False)
        summary["run_created"] = diff.get("run_created", False)
        summary["cleanup_required"] = diff.get("cleanup_required", False)

        # Verify candidate file unchanged after diff
        if candidate_existed and candidate_path.exists():
            summary["candidate_file_content_unchanged"] = (
                candidate_path.read_text(encoding="utf-8") == candidate_content_before
            )

        # Blocked: user_confirmed=false
        _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-candidate-diff-generate", 409,
            json={"source_task_id": source_task_id, "source_message_id": ce_msg_id, "user_confirmed": False})
        summary["p21_c_candidate_diff_user_confirmed_blocked"] = "blocked"

        # Blocked: non-P21-C-E source
        _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-candidate-diff-generate", 409,
            json={"source_task_id": source_task_id, "source_message_id": write["message"]["id"], "user_confirmed": True})
        summary["p21_c_candidate_diff_non_candidate_write_source_blocked"] = "blocked"

        # Blocked: task mismatch
        p11b = _request_json(client, "POST", f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run", 200,
            json={"user_goal": "P21-C-F second evidence"})
        p12b = _request_json(client, "POST", f"/project-director/sessions/{session_id}/dry-run-task-dispatch", 200,
            json={"source_message_id": p11b["message"]["id"], "user_confirmed": True})
        task_b_id = p12b["created_task_id"]
        _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-candidate-diff-generate", 409,
            json={"source_task_id": task_b_id, "source_message_id": ce_msg_id, "user_confirmed": True})
        summary["p21_c_candidate_diff_task_mismatch_blocked"] = "blocked"

        # Blocked: max_diff_bytes too small
        _request_json(client, "POST", f"/project-director/sessions/{session_id}/sandbox-candidate-diff-generate", 409,
            json={"source_task_id": source_task_id, "source_message_id": ce_msg_id,
                  "user_confirmed": True, "max_diff_bytes": 1})
        summary["p21_c_candidate_diff_too_large_blocked"] = "blocked"

        # Message readback
        msgs = _request_json(client, "GET", f"/project-director/sessions/{session_id}/messages", 200)
        messages = msgs.get("messages") or []
        has_diff = any(m.get("source_detail") == "p21_c_sandbox_candidate_diff_generated" for m in messages)
        summary["p21_c_message_readback"] = "passed" if has_diff else "failed"

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
        _prepare_chain(summary=summary)
    except Exception as exc:
        summary["smoke_status"] = "failed"
        summary["blocked_reasons"].append(type(exc).__name__)
        return summary

    required = (
        "session_created", "p21_c_workspace_guard", "p21_c_operation_manifest_guard",
        "p21_c_workspace_create", "p21_c_workspace_manifest_write",
        "p21_c_candidate_files_write", "p21_c_candidate_diff_generate",
        "p21_c_candidate_diff_user_confirmed_blocked",
        "p21_c_candidate_diff_non_candidate_write_source_blocked",
        "p21_c_candidate_diff_task_mismatch_blocked",
        "p21_c_candidate_diff_too_large_blocked",
        "p21_c_message_readback", "isolated_runtime_data",
        "unified_diff_returned", "candidate_file_exists",
        "candidate_file_content_unchanged", "internal_manifest_file_exists",
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
        Path(tempfile.mkdtemp(prefix="p21-c-candidate-diff-smoke-"))
        if args.runtime_dir is None else args.runtime_dir
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
        print(f"P21-C-F diff generation smoke: {summary['smoke_status']}")
    return 0 if summary["smoke_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
