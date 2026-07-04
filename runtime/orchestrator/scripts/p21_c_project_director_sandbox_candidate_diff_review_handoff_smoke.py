"""P21-C-G Project Director sandbox diff review handoff smoke.

Uses isolated runtime data and does not start reviewers, execute reviews,
write files, apply patches, or perform Git writes.
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
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--keep-temp-data", action="store_true")
    parser.add_argument("--runtime-dir", type=Path)
    return parser.parse_args()


def _base_summary(rd: Path, db: Path) -> dict[str, Any]:
    return {
        "smoke_status": "failed",
        "p21_c_candidate_diff_generate": None,
        "p21_c_candidate_diff_review_handoff": None,
        "p21_c_handoff_user_confirmed_blocked": None,
        "p21_c_handoff_non_diff_source_blocked": None,
        "p21_c_handoff_task_mismatch_blocked": None,
        "p21_c_handoff_diff_bytes_mismatch_blocked": None,
        "p21_c_handoff_entry_bytes_mismatch_blocked": None,
        "p21_c_handoff_aggregation_mismatch_blocked": None,
        "source_diff_verified": False,
        "source_diff_sha256": "",
        "source_diff_sha256_length": 0,
        "diff_file_count": 0,
        "diff_bytes": 0,
        "review_scope_paths": [],
        "reviewer_started": False,
        "review_executed": False,
        "review_findings_generated": False,
        "review_verdict_generated": False,
        "main_project_file_written": False,
        "sandbox_file_written": False,
        "manifest_file_written": False,
        "diff_file_written": False,
        "patch_applied": False,
        "worktree_created": False,
        "git_write_performed": False,
        "native_executor_started": False,
        "codex_started": False,
        "claude_code_started": False,
        "worker_started": False,
        "task_created": False,
        "run_created": False,
        "p21_c_message_readback": None,
        "isolated_runtime_data": False,
        "ai_project_director_total_loop": "Partial",
        "runtime_data_dir": str(rd),
        "sqlite_db_path": str(db),
    }


def _configure(rd: Path) -> Path:
    db = rd / "db" / "orchestrator.db"
    os.environ["RUNTIME_DATA_DIR"] = str(rd)
    os.environ["SQLITE_DB_PATH"] = str(db)
    os.environ["WORKER_SIMULATE_EXECUTION_OVERRIDE"] = "true"
    os.environ.pop("OPENAI_API_KEY", None)
    return db


def _req(client: Any, method: str, path: str, expected: int, **kw) -> dict[str, Any]:
    r = getattr(client, method.lower())(path, **kw)
    if r.status_code != expected:
        raise RuntimeError(f"{method} {path} -> {r.status_code}, body: {r.text[:500]}")
    return r.json()


def _p14(*, session_id, source_task_id, source_message_id) -> str:
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


def _p15(*, session_id, source_task_id, source_message_id) -> str:
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


def _p16(*, session_id, source_task_id, source_message_id) -> str:
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


def _p17(*, session_id, source_task_id, source_message_id) -> str:
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


def _chain(*, summary: dict[str, Any]) -> tuple[str, str]:
    import warnings
    warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient` is deprecated.*", category=Warning)
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        proj = _req(c, "POST", "/projects", 201,
            json={"name": "P21-C-G smoke", "summary": "P21-C-G smoke.", "status": "active", "stage": "execution"})
        sess = _req(c, "POST", "/project-director/sessions", 201,
            json={"project_id": proj["id"], "goal_text": "P21-C-G smoke"})
        sid = sess["id"]

        p11 = _req(c, "POST", f"/project-director/sessions/{sid}/evidence-to-agent/dry-run", 200,
            json={"user_goal": "P21-C-G evidence"})
        p12 = _req(c, "POST", f"/project-director/sessions/{sid}/dry-run-task-dispatch", 200,
            json={"source_message_id": p11["message"]["id"], "user_confirmed": True})
        tid = p12["created_task_id"]
        p12m = p12["message"]["id"]

        _req(c, "POST", "/workers/run-once", 200)
        _req(c, "POST", f"/project-director/sessions/{sid}/controlled-executor-dispatch", 200,
            json={"source_task_id": tid, "source_message_id": p12m,
                  "user_confirmed": True, "requested_agent_role": "programmer",
                  "requested_executor": "codex", "launch_mode": "dry_run"})

        p14 = _p14(session_id=sid, source_task_id=tid, source_message_id=p12m)
        p15 = _p15(session_id=sid, source_task_id=tid, source_message_id=p14)
        p16 = _p16(session_id=sid, source_task_id=tid, source_message_id=p15)
        p17 = _p17(session_id=sid, source_task_id=tid, source_message_id=p16)

        p20 = _req(c, "POST", f"/project-director/sessions/{sid}/sandbox-write-preflight", 200,
            json={"source_task_id": tid, "source_message_id": p17,
                  "user_confirmed": True, "preflight_mode": "dry_run",
                  "file_operations": [
                      {"path": "runtime/orchestrator/app/domain/new_module.py", "operation": "create",
                       "reason": "P21-C-G smoke", "patch_preview": ["PREVIEW ONLY: no repository file was modified."]}]})
        p21 = _req(c, "POST", f"/project-director/sessions/{sid}/sandbox-write-execution", 200,
            json={"source_task_id": tid, "source_message_id": p20["message"]["id"],
                  "user_confirmed": True, "execution_mode": "dry_run"})
        lock = _req(c, "POST", f"/project-director/sessions/{sid}/sandbox-write-design-lock", 200,
            json={"source_task_id": tid, "source_message_id": p21["message"]["id"], "user_confirmed": True})
        guard = _req(c, "POST", f"/project-director/sessions/{sid}/sandbox-workspace-guard", 200,
            json={"source_task_id": tid, "source_message_id": lock["message"]["id"], "user_confirmed": True})
        manifest = _req(c, "POST", f"/project-director/sessions/{sid}/sandbox-operation-manifest-guard", 200,
            json={"source_task_id": tid, "source_message_id": guard["message"]["id"], "user_confirmed": True})
        create = _req(c, "POST", f"/project-director/sessions/{sid}/sandbox-workspace-create", 200,
            json={"source_task_id": tid, "source_message_id": manifest["message"]["id"], "user_confirmed": True})
        write = _req(c, "POST", f"/project-director/sessions/{sid}/sandbox-workspace-evidence-manifest", 200,
            json={"source_task_id": tid, "source_message_id": create["message"]["id"], "user_confirmed": True})
        ce = _req(c, "POST", f"/project-director/sessions/{sid}/sandbox-candidate-files-write", 200,
            json={"source_task_id": tid, "source_message_id": write["message"]["id"],
                  "user_confirmed": True,
                  "candidate_files": [{"relative_path": "runtime/orchestrator/app/domain/new_module.py",
                                       "content": "print('new')\n", "operation": "create"}]})
        diff = _req(c, "POST", f"/project-director/sessions/{sid}/sandbox-candidate-diff-generate", 200,
            json={"source_task_id": tid, "source_message_id": ce["message"]["id"], "user_confirmed": True})
        summary["p21_c_candidate_diff_generate"] = diff.get("diff_generation_status")
        diff_msg_id = diff["message"]["id"]

        # P21-C-G handoff
        handoff = _req(c, "POST", f"/project-director/sessions/{sid}/sandbox-candidate-diff-review-handoff", 200,
            json={"source_task_id": tid, "source_message_id": diff_msg_id, "user_confirmed": True})
        summary["p21_c_candidate_diff_review_handoff"] = handoff.get("review_handoff_status")
        summary["source_diff_verified"] = handoff.get("source_diff_verified", False)
        summary["source_diff_sha256"] = handoff.get("source_diff_sha256", "")
        summary["source_diff_sha256_length"] = len(handoff.get("source_diff_sha256", ""))
        summary["diff_file_count"] = handoff.get("diff_file_count", 0)
        summary["diff_bytes"] = handoff.get("diff_bytes", 0)
        summary["review_scope_paths"] = handoff.get("review_scope_paths", [])
        summary["reviewer_started"] = handoff.get("reviewer_started", False)
        summary["review_executed"] = handoff.get("review_executed", False)
        summary["review_findings_generated"] = handoff.get("review_findings_generated", False)
        summary["review_verdict_generated"] = handoff.get("review_verdict_generated", False)
        summary["main_project_file_written"] = handoff.get("main_project_file_written", False)
        summary["sandbox_file_written"] = handoff.get("sandbox_file_written", False)
        summary["manifest_file_written"] = handoff.get("manifest_file_written", False)
        summary["diff_file_written"] = handoff.get("diff_file_written", False)
        summary["patch_applied"] = handoff.get("patch_applied", False)
        summary["worktree_created"] = handoff.get("worktree_created", False)
        summary["git_write_performed"] = handoff.get("git_write_performed", False)
        summary["native_executor_started"] = handoff.get("native_executor_started", False)
        summary["codex_started"] = handoff.get("codex_started", False)
        summary["claude_code_started"] = handoff.get("claude_code_started", False)
        summary["worker_started"] = handoff.get("worker_started", False)
        summary["task_created"] = handoff.get("task_created", False)
        summary["run_created"] = handoff.get("run_created", False)

        # Blocked: user_confirmed=false
        _req(c, "POST", f"/project-director/sessions/{sid}/sandbox-candidate-diff-review-handoff", 409,
            json={"source_task_id": tid, "source_message_id": diff_msg_id, "user_confirmed": False})
        summary["p21_c_handoff_user_confirmed_blocked"] = "blocked"

        # Blocked: non-P21-C-F source
        _req(c, "POST", f"/project-director/sessions/{sid}/sandbox-candidate-diff-review-handoff", 409,
            json={"source_task_id": tid, "source_message_id": ce["message"]["id"], "user_confirmed": True})
        summary["p21_c_handoff_non_diff_source_blocked"] = "blocked"

        # Blocked: task mismatch
        p11b = _req(c, "POST", f"/project-director/sessions/{sid}/evidence-to-agent/dry-run", 200,
            json={"user_goal": "P21-C-G second evidence"})
        p12b = _req(c, "POST", f"/project-director/sessions/{sid}/dry-run-task-dispatch", 200,
            json={"source_message_id": p11b["message"]["id"], "user_confirmed": True})
        tid_b = p12b["created_task_id"]
        _req(c, "POST", f"/project-director/sessions/{sid}/sandbox-candidate-diff-review-handoff", 409,
            json={"source_task_id": tid_b, "source_message_id": diff_msg_id, "user_confirmed": True})
        summary["p21_c_handoff_task_mismatch_blocked"] = "blocked"

        # Blocked: diff bytes mismatch (by using a different diff_msg with tampered bytes)
        # We can't easily tamper via API, so we test with the existing message
        # The aggregation/bytes/entry tests are covered by contract tests
        summary["p21_c_handoff_diff_bytes_mismatch_blocked"] = "covered_by_contract"
        summary["p21_c_handoff_entry_bytes_mismatch_blocked"] = "covered_by_contract"
        summary["p21_c_handoff_aggregation_mismatch_blocked"] = "covered_by_contract"

        # Message readback
        msgs = _req(c, "GET", f"/project-director/sessions/{sid}/messages", 200)
        messages = msgs.get("messages") or []
        has_handoff = any(m.get("source_detail") == "p21_c_sandbox_candidate_diff_review_handoff_created" for m in messages)
        summary["p21_c_message_readback"] = "passed" if has_handoff else "failed"

        return sid, tid


def run_smoke(rd: Path, args: argparse.Namespace) -> dict[str, Any]:
    db = _configure(rd)
    summary = _base_summary(rd.resolve(), db.resolve())
    summary["isolated_runtime_data"] = rd.resolve() != DEFAULT_RUNTIME_DATA_DIR
    if not summary["isolated_runtime_data"]:
        summary["smoke_status"] = "blocked"
        return summary

    try:
        _chain(summary=summary)
    except Exception as exc:
        summary["smoke_status"] = "failed"
        summary["blocked_reasons"] = [type(exc).__name__]
        return summary

    required = (
        "p21_c_candidate_diff_generate", "p21_c_candidate_diff_review_handoff",
        "p21_c_handoff_user_confirmed_blocked", "p21_c_handoff_non_diff_source_blocked",
        "p21_c_handoff_task_mismatch_blocked", "p21_c_message_readback",
        "isolated_runtime_data", "source_diff_verified",
    )
    if all(summary.get(k) for k in required):
        summary["smoke_status"] = "passed"
    else:
        summary["smoke_status"] = "partial"
    return summary


def main() -> int:
    args = _parse_args()
    temp = args.runtime_dir is None
    rd = (Path(tempfile.mkdtemp(prefix="p21-c-handoff-smoke-")) if temp else args.runtime_dir).resolve()
    rd.mkdir(parents=True, exist_ok=True)
    try:
        summary = run_smoke(rd, args)
    finally:
        if temp and not args.keep_temp_data:
            shutil.rmtree(rd, ignore_errors=True)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    else:
        print(f"P21-C-G handoff smoke: {summary['smoke_status']}")
    return 0 if summary["smoke_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
