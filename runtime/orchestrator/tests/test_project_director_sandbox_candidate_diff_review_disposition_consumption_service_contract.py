"""Contract tests for P21-D-C2 disposition consumption & atomic replay guard."""

from __future__ import annotations

import hashlib
import json
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db_tables import (
    ORMBase,
    ProjectDirectorMessageTable,
    ProjectDirectorSessionTable,
    ProjectTable,
    TaskTable,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_sandbox_candidate_diff_review_disposition_consumption import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_sandbox_candidate_diff_service import (
    ProjectDirectorSandboxCandidateDiffService,
    P21_C_SANDBOX_CANDIDATE_DIFF_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL,
    SOURCE_CANDIDATE_WRITE_FALSE_FLAGS,
    SOURCE_MANIFEST_WRITE_FALSE_FLAGS,
    SOURCE_OPERATION_MANIFEST_FALSE_FLAGS,
)
from app.services.project_director_sandbox_candidate_diff_review_handoff_service import (
    ProjectDirectorSandboxCandidateDiffReviewHandoffService,
    P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_consumption_service import (
    DISPOSITION_CONSUMPTION_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMED_SOURCE_DETAIL,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_ACTION_TYPE,
    ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionService,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_consumption_preflight_service import (
    DISPOSITION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_service import (
    DEFERRED_TRIGGER_KINDS,
    EVALUATED_TRIGGER_KINDS,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL,
    REVIEW_DISPOSITION_SCHEMA_VERSION,
)
from app.services.project_director_sandbox_candidate_diff_readonly_review_execution_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_candidate_diff_review_execution_preflight_service import (
    REVIEW_OUTPUT_SCHEMA_VERSION,
)
from app.services.project_director_sandbox_candidate_file_write_service import (
    P21_C_SANDBOX_CANDIDATE_FILES_WRITE_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_FILES_WRITE_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_workspace_manifest_write_service import (
    P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_ACTION_TYPE,
    P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL,
    INTERNAL_MANIFEST_DIR_NAME,
    INTERNAL_MANIFEST_FILE_NAME,
)
from app.services.project_director_sandbox_workspace_creation_service import (
    P21_C_SANDBOX_WORKSPACE_CREATE_ACTION_TYPE,
    P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_operation_manifest_guard_service import (
    P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_ACTION_TYPE,
    P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL,
)

# ── Constants ───────────────────────────────────────────────────────

SESSION_ID = uuid4()
TASK_ID = uuid4()
PROJECT_ID = uuid4()

OP_MANIFEST_MSG_ID = uuid4()
WORKSPACE_CREATE_MSG_ID = uuid4()
WORKSPACE_MANIFEST_WRITE_MSG_ID = uuid4()
CANDIDATE_FILE_WRITE_MSG_ID = uuid4()
CANDIDATE_DIFF_MSG_ID = uuid4()
REVIEW_HANDOFF_MSG_ID = uuid4()
REVIEW_EXECUTION_MSG_ID = uuid4()
DISPOSITION_MSG_ID = uuid4()
C1_PREFLIGHT_MSG_ID = uuid4()

TARGET_CONTENT = "old content\n"
CANDIDATE_CONTENT = "new content\n"

_C1_FALSE_FLAGS = [
    "continuation_started",
    "rework_started",
    "disposition_consumed",
    "human_escalation_package_created",
    "human_decision_recorded",
    "main_project_file_written",
    "sandbox_file_written",
    "manifest_file_written",
    "diff_file_written",
    "patch_applied",
    "git_write_performed",
    "worktree_created",
    "worker_started",
    "task_created",
    "run_created",
    "gate_allows_write",
]

_CONSUMPTION_FALSE_FLAGS = [
    "continuation_started",
    "rework_started",
    "human_escalation_package_created",
    "human_decision_recorded",
    "main_project_file_written",
    "sandbox_file_written",
    "manifest_file_written",
    "diff_file_written",
    "patch_applied",
    "git_write_performed",
    "worktree_created",
    "worker_started",
    "task_created",
    "run_created",
    "gate_allows_write",
]


# ── Test database helpers ───────────────────────────────────────────


def _make_test_engine(db_path: str):
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )

    @event.listens_for(engine, "connect")
    def _configure_sqlite(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.close()

    ORMBase.metadata.create_all(bind=engine)
    return engine


def _make_session_factory(engine):
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


# ── Diff helpers ────────────────────────────────────────────────────


def _make_unified_diff(relative_path, old_content, new_content):
    import difflib

    diff_lines = difflib.unified_diff(
        old_content.splitlines(),
        new_content.splitlines(),
        fromfile=f"a/{relative_path}",
        tofile=f"b/{relative_path}",
        lineterm="",
    )
    diff_text = "\n".join(diff_lines)
    return f"{diff_text}\n" if diff_text else ""


def _initialize_exact_base_repository(repo_root) -> str:
    for args in (
        ("git", "init"),
        ("git", "config", "user.email", "p21-d-c2@example.invalid"),
        ("git", "config", "user.name", "P21-D-C2 contract test"),
        ("git", "add", "src"),
        ("git", "commit", "-m", "exact base"),
    ):
        subprocess.run(args, cwd=repo_root, check=True, capture_output=True)
    return subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit_repository_change(repo_root, message: str) -> str:
    for args in (
        ("git", "add", "src"),
        ("git", "commit", "-m", message),
    ):
        subprocess.run(args, cwd=repo_root, check=True, capture_output=True)
    return subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _compute_review_result_fingerprint(
    *,
    session_id=SESSION_ID,
    source_task_id=TASK_ID,
    source_review_message_id=REVIEW_EXECUTION_MSG_ID,
    source_preflight_message_id=REVIEW_HANDOFF_MSG_ID,
    source_diff_message_id=CANDIDATE_DIFF_MSG_ID,
    requested_reviewer_executor="codex",
    source_diff_sha256,
    review_prompt_sha256,
    review_scope_paths,
    review_output_schema_version=REVIEW_OUTPUT_SCHEMA_VERSION,
    raw_output_sha256,
    verdict="no_blocking_findings",
    risk_level="low",
):
    canonical_payload = {
        "session_id": str(session_id),
        "source_task_id": str(source_task_id),
        "source_review_message_id": str(source_review_message_id),
        "source_preflight_message_id": str(source_preflight_message_id),
        "source_diff_message_id": str(source_diff_message_id),
        "requested_reviewer_executor": requested_reviewer_executor,
        "source_diff_sha256": source_diff_sha256,
        "review_prompt_sha256": review_prompt_sha256,
        "review_scope_paths": review_scope_paths,
        "review_output_schema_version": review_output_schema_version,
        "raw_output_sha256": raw_output_sha256,
        "output_validation_status": "validated",
        "strict_json_valid": True,
        "schema_valid": True,
        "semantics_valid": True,
        "evidence_scope_valid": True,
        "review_status": "reviewed",
        "verdict": verdict,
        "risk_level": risk_level,
        "summary": "Review completed.",
        "findings": [],
        "recommended_next_step": "Proceed.",
    }
    canonical_json = json.dumps(
        canonical_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


# ── Filesystem setup ────────────────────────────────────────────────


def _setup_filesystem(tmp_path):
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    (repo_root / "src").mkdir()
    (repo_root / "src" / "example.py").write_text(TARGET_CONTENT, encoding="utf-8")
    base_commit_sha = _initialize_exact_base_repository(repo_root)

    workspace_root = (tmp_path / "project-director" / "sandbox-workspaces").resolve()
    workspace_root.mkdir(parents=True)
    workspace_path = (workspace_root / "ws1").resolve()
    workspace_path.mkdir()
    (workspace_path / "src").mkdir()
    (workspace_path / "src" / "example.py").write_text(CANDIDATE_CONTENT, encoding="utf-8")

    manifest_dir = (workspace_path / INTERNAL_MANIFEST_DIR_NAME).resolve()
    manifest_dir.mkdir()
    manifest_file = (manifest_dir / INTERNAL_MANIFEST_FILE_NAME).resolve()
    manifest = {
        "schema_version": "p21-c-d.v1",
        "internal_manifest_only": True,
        "ai_project_director_total_loop": "Partial",
        "manifest_file_path": manifest_file.as_posix(),
    }
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")

    unified_diff_text = _make_unified_diff("src/example.py", TARGET_CONTENT, CANDIDATE_CONTENT)
    diff_sha256 = hashlib.sha256(unified_diff_text.encode("utf-8")).hexdigest()
    raw_output_sha256 = hashlib.sha256(b"raw review output").hexdigest()
    review_prompt_sha256 = hashlib.sha256(b"review prompt").hexdigest()

    return {
        "repo_root": repo_root,
        "base_commit_sha": base_commit_sha,
        "workspace_root": workspace_root,
        "workspace_path": workspace_path,
        "unified_diff_text": unified_diff_text,
        "diff_sha256": diff_sha256,
        "raw_output_sha256": raw_output_sha256,
        "review_prompt_sha256": review_prompt_sha256,
        "relative_path": "src/example.py",
    }


# ── Seed helpers ────────────────────────────────────────────────────


def _seed_base_records(session: Session) -> None:
    session.add(
        ProjectTable(
            id=PROJECT_ID,
            name="Test",
            summary="Test project",
            status="active",
            stage="intake",
        )
    )
    session.flush()
    acceptance = json.dumps(
        [
            "safe_dry_run_task=true",
            "worker_simulate_required=true",
            "product_runtime_git_write_allowed=false",
            "native_executor_started=false",
            "codex_started=false",
            "claude_code_started=false",
        ]
    )
    session.add(
        TaskTable(
            id=TASK_ID,
            project_id=PROJECT_ID,
            title="Test task",
            status="pending",
            priority="normal",
            input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
            risk_level="normal",
            human_status="none",
            source_draft_id="p12-test-draft",
            acceptance_criteria=acceptance,
        )
    )
    session.add(
        ProjectDirectorSessionTable(
            id=SESSION_ID,
            project_id=PROJECT_ID,
            goal_text="Test goal",
            constraints="",
            status="confirmed",
        )
    )
    session.commit()


def _seed_message_chain(session: Session, fs_info: dict[str, Any]) -> None:
    workspace_path = fs_info["workspace_path"]
    repo_root = fs_info["repo_root"]
    unified_diff_text = fs_info["unified_diff_text"]
    diff_sha256 = fs_info["diff_sha256"]
    raw_output_sha256 = fs_info["raw_output_sha256"]
    review_prompt_sha256 = fs_info["review_prompt_sha256"]
    diff_bytes = len(unified_diff_text.encode("utf-8"))

    rel_path = fs_info.get("relative_path", "src/example.py")
    review_scope_paths = [rel_path]

    seq = 1

    # 1. Operation manifest
    op_action = {
        "type": P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_ACTION_TYPE,
        "manifest_status": "manifested",
        "operation_manifest_created": True,
        "manifest_allowed_operations_count": 1,
        "allowed_operation_paths": [rel_path],
        "manifest_operations": [
            {
                "path": rel_path,
                "operation": "update",
                "operation_manifest_allowed": True,
            }
        ],
        "source_message_id": str(OP_MANIFEST_MSG_ID),
        "source_task_id": str(TASK_ID),
        "ai_project_director_total_loop": "Partial",
    }
    for flag in SOURCE_OPERATION_MANIFEST_FALSE_FLAGS:
        op_action[flag] = False
    session.add(
        ProjectDirectorMessageTable(
            id=OP_MANIFEST_MSG_ID,
            session_id=SESSION_ID,
            role="assistant",
            content="Operation manifest guard passed.",
            sequence_no=seq,
            intent="sandbox_operation_manifest_guard",
            related_project_id=PROJECT_ID,
            related_task_id=TASK_ID,
            source="system",
            source_detail=P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([op_action]),
            requires_confirmation=False,
            risk_level="high",
        )
    )
    seq += 1

    # 2. Workspace creation
    ws_create_action = {
        "type": P21_C_SANDBOX_WORKSPACE_CREATE_ACTION_TYPE,
        "source_message_id": str(OP_MANIFEST_MSG_ID),
        "source_task_id": str(TASK_ID),
        "cleanup_required": False,
        "ai_project_director_total_loop": "Partial",
    }
    session.add(
        ProjectDirectorMessageTable(
            id=WORKSPACE_CREATE_MSG_ID,
            session_id=SESSION_ID,
            role="assistant",
            content="Workspace created.",
            sequence_no=seq,
            intent="sandbox_workspace_create",
            related_project_id=PROJECT_ID,
            related_task_id=TASK_ID,
            source="system",
            source_detail=P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([ws_create_action]),
            requires_confirmation=False,
            risk_level="high",
        )
    )
    seq += 1

    # 3. Workspace manifest write
    manifest_write_action = {
        "type": P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_ACTION_TYPE,
        "source_message_id": str(WORKSPACE_CREATE_MSG_ID),
        "source_task_id": str(TASK_ID),
        "manifest_file_written": True,
        "ai_project_director_total_loop": "Partial",
    }
    for flag in SOURCE_MANIFEST_WRITE_FALSE_FLAGS:
        manifest_write_action[flag] = False
    session.add(
        ProjectDirectorMessageTable(
            id=WORKSPACE_MANIFEST_WRITE_MSG_ID,
            session_id=SESSION_ID,
            role="assistant",
            content="Workspace manifest written.",
            sequence_no=seq,
            intent="sandbox_workspace_manifest_write",
            related_project_id=PROJECT_ID,
            related_task_id=TASK_ID,
            source="system",
            source_detail=P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([manifest_write_action]),
            requires_confirmation=False,
            risk_level="high",
        )
    )
    seq += 1

    # 4. Candidate file write
    candidate_write_action = {
        "type": P21_C_SANDBOX_CANDIDATE_FILES_WRITE_ACTION_TYPE,
        "source_message_id": str(WORKSPACE_MANIFEST_WRITE_MSG_ID),
        "source_task_id": str(TASK_ID),
        "workspace_path": workspace_path.as_posix(),
        "candidate_write_status": "written",
        "candidate_business_files_written": True,
        "business_file_written": True,
        "candidate_files_written_count": 1,
        "candidate_written_files": [
            {
                "relative_path": rel_path,
                "operation": "update",
                "workspace_file_path": (workspace_path / rel_path).as_posix(),
            }
        ],
        "ai_project_director_total_loop": "Partial",
    }
    for flag in SOURCE_CANDIDATE_WRITE_FALSE_FLAGS:
        candidate_write_action[flag] = False
    session.add(
        ProjectDirectorMessageTable(
            id=CANDIDATE_FILE_WRITE_MSG_ID,
            session_id=SESSION_ID,
            role="assistant",
            content="Candidate files written.",
            sequence_no=seq,
            intent="sandbox_candidate_files_write",
            related_project_id=PROJECT_ID,
            related_task_id=TASK_ID,
            source="system",
            source_detail=P21_C_SANDBOX_CANDIDATE_FILES_WRITE_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([candidate_write_action]),
            requires_confirmation=False,
            risk_level="high",
        )
    )
    seq += 1

    # 5. Candidate diff
    diff_entry = {
        "relative_path": rel_path,
        "operation": "update",
        "target_file_path": (repo_root / rel_path).as_posix(),
        "candidate_file_path": (workspace_path / rel_path).as_posix(),
        "target_file_existed": True,
        "candidate_file_existed": True,
        "target_file_content_read": True,
        "candidate_file_content_read": True,
        "unified_diff": unified_diff_text,
        "diff_bytes": diff_bytes,
    }
    diff_action = {
        "type": P21_C_SANDBOX_CANDIDATE_DIFF_ACTION_TYPE,
        "diff_generation_status": "generated",
        "source_task_id": str(TASK_ID),
        "source_message_id": str(CANDIDATE_FILE_WRITE_MSG_ID),
        "workspace_path": workspace_path.as_posix(),
        "workspace_path_within_root": True,
        "internal_manifest_file_path": (
            workspace_path / INTERNAL_MANIFEST_DIR_NAME / INTERNAL_MANIFEST_FILE_NAME
        ).as_posix(),
        "repo_root": fs_info["repo_root"].as_posix(),
        "readonly_real_diff_generated": True,
        "real_diff_generated": True,
        "diff_file_count": 1,
        "diff_bytes": diff_bytes,
        "diff_entries": [diff_entry],
        "unified_diff_text": unified_diff_text,
        "candidate_files_considered_count": 1,
        "candidate_files_diffed_count": 1,
        "candidate_files_blocked_count": 0,
        "target_file_content_read": True,
        "candidate_file_content_read": True,
        "cleanup_required": False,
        "ai_project_director_total_loop": "Partial",
    }
    for flag in [
        "main_project_file_written", "sandbox_file_written", "manifest_file_written",
        "diff_file_written", "patch_applied", "git_write_performed",
        "worktree_created", "worker_started", "task_created", "run_created",
        "controlled_sandbox_write_enabled", "sandbox_write_allowed",
        "product_runtime_git_write_allowed", "main_worktree_write_allowed",
        "worktree_write_allowed", "file_write_allowed",
        "actual_patch_applied", "real_code_modified",
        "native_executor_started", "codex_started", "claude_code_started",
        "worktree_cleaned_up", "rollback_snapshot_created",
    ]:
        diff_action[flag] = False
    session.add(
        ProjectDirectorMessageTable(
            id=CANDIDATE_DIFF_MSG_ID,
            session_id=SESSION_ID,
            role="assistant",
            content="Candidate diff generated.",
            sequence_no=seq,
            intent="sandbox_candidate_diff_generate",
            related_project_id=PROJECT_ID,
            related_task_id=TASK_ID,
            source="system",
            source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([diff_action]),
            requires_confirmation=False,
            risk_level="high",
        )
    )
    seq += 1

    # 6. Review handoff
    handoff_action = {
        "type": P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_ACTION_TYPE,
        "review_handoff_status": "created",
        "source_task_id": str(TASK_ID),
        "source_message_id": str(CANDIDATE_DIFF_MSG_ID),
        "source_diff_message_id": str(CANDIDATE_DIFF_MSG_ID),
        "handoff_mode": "readonly_real_diff_review",
        "requested_reviewer_executor": "codex",
        "source_diff_sha256": diff_sha256,
        "diff_file_count": 1,
        "diff_bytes": diff_bytes,
        "review_scope_paths": list(review_scope_paths),
        "cleanup_required": False,
        "ai_project_director_total_loop": "Partial",
    }
    for flag in [
        "reviewer_started", "review_executed", "review_verdict_generated",
        "review_findings_generated", "main_project_file_written",
        "sandbox_file_written", "manifest_file_written", "diff_file_written",
        "patch_applied", "product_runtime_git_write_allowed",
        "main_worktree_write_allowed", "worktree_write_allowed",
        "file_write_allowed", "actual_patch_applied", "real_code_modified",
        "git_write_performed", "native_executor_started", "codex_started",
        "claude_code_started", "worker_started", "task_created", "run_created",
        "worktree_created", "worktree_cleaned_up", "rollback_snapshot_created",
    ]:
        handoff_action[flag] = False
    session.add(
        ProjectDirectorMessageTable(
            id=REVIEW_HANDOFF_MSG_ID,
            session_id=SESSION_ID,
            role="assistant",
            content="Review handoff created.",
            sequence_no=seq,
            intent="sandbox_candidate_diff_review_handoff",
            related_project_id=PROJECT_ID,
            related_task_id=TASK_ID,
            source="system",
            source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([handoff_action]),
            requires_confirmation=False,
            risk_level="high",
        )
    )
    seq += 1

    # 7. Review execution
    fp = _compute_review_result_fingerprint(
        source_diff_sha256=diff_sha256,
        review_prompt_sha256=review_prompt_sha256,
        review_scope_paths=review_scope_paths,
        raw_output_sha256=raw_output_sha256,
    )
    review_action = {
        "type": P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
        "session_id": str(SESSION_ID),
        "source_task_id": str(TASK_ID),
        "source_preflight_message_id": str(REVIEW_HANDOFF_MSG_ID),
        "source_diff_message_id": str(CANDIDATE_DIFF_MSG_ID),
        "requested_reviewer_executor": "codex",
        "source_diff_sha256": diff_sha256,
        "review_prompt_sha256": review_prompt_sha256,
        "review_scope_paths": list(review_scope_paths),
        "review_output_schema_version": REVIEW_OUTPUT_SCHEMA_VERSION,
        "adapter_status": "validated_output",
        "output_validation_status": "validated",
        "raw_output_sha256": raw_output_sha256,
        "strict_json_valid": True,
        "schema_valid": True,
        "semantics_valid": True,
        "evidence_scope_valid": True,
        "review_status": "reviewed",
        "verdict": "no_blocking_findings",
        "risk_level": "low",
        "summary": "Review completed.",
        "findings": [],
        "recommended_next_step": "Proceed.",
        "ai_project_director_total_loop": "Partial",
    }
    for flag in [
        "main_project_file_written", "sandbox_file_written", "manifest_file_written",
        "diff_file_written", "patch_applied", "git_write_performed",
        "worktree_created", "worker_started", "task_created", "run_created",
    ]:
        review_action[flag] = False
    session.add(
        ProjectDirectorMessageTable(
            id=REVIEW_EXECUTION_MSG_ID,
            session_id=SESSION_ID,
            role="assistant",
            content="Readonly review executed.",
            sequence_no=seq,
            intent="sandbox_candidate_diff_readonly_review_execution",
            related_project_id=PROJECT_ID,
            related_task_id=TASK_ID,
            source="system",
            source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([review_action]),
            requires_confirmation=False,
            risk_level="high",
        )
    )
    seq += 1

    # 8. Disposition
    disposition_id = uuid4()
    disposition_action = {
        "type": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_ACTION_TYPE,
        "schema_version": REVIEW_DISPOSITION_SCHEMA_VERSION,
        "disposition_status": "computed",
        "session_id": str(SESSION_ID),
        "source_task_id": str(TASK_ID),
        "source_review_message_id": str(REVIEW_EXECUTION_MSG_ID),
        "source_preflight_message_id": str(REVIEW_HANDOFF_MSG_ID),
        "source_diff_message_id": str(CANDIDATE_DIFF_MSG_ID),
        "requested_reviewer_executor": "codex",
        "source_diff_sha256": diff_sha256,
        "review_prompt_sha256": review_prompt_sha256,
        "review_scope_paths": list(review_scope_paths),
        "review_output_schema_version": REVIEW_OUTPUT_SCHEMA_VERSION,
        "review_result_fingerprint": fp,
        "disposition_id": str(disposition_id),
        "disposition_type": "AUTO_CONTINUE",
        "disposition_reason": "review_has_no_blocking_findings",
        "source_review_verdict": "no_blocking_findings",
        "source_review_risk_level": "low",
        "escalation_triggers": [],
        "evaluated_trigger_kinds": list(EVALUATED_TRIGGER_KINDS),
        "deferred_trigger_kinds": list(DEFERRED_TRIGGER_KINDS),
        "actor": "system",
        "client_request_id": None,
        "disposition_created_at": datetime.now(timezone.utc).isoformat(),
        "ai_project_director_total_loop": "Partial",
    }
    for flag in _C1_FALSE_FLAGS:
        disposition_action[flag] = False
    session.add(
        ProjectDirectorMessageTable(
            id=DISPOSITION_MSG_ID,
            session_id=SESSION_ID,
            role="assistant",
            content="Disposition computed.",
            sequence_no=seq,
            intent="sandbox_candidate_diff_review_disposition",
            related_project_id=PROJECT_ID,
            related_task_id=TASK_ID,
            source="system",
            source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([disposition_action]),
            requires_confirmation=False,
            risk_level="high",
        )
    )
    seq += 1

    # 9. C1 preflight
    c1_action = {
        "type": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_ACTION_TYPE,
        "schema_version": DISPOSITION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION,
        "preflight_status": "ready",
        "session_id": str(SESSION_ID),
        "source_task_id": str(TASK_ID),
        "source_disposition_message_id": str(DISPOSITION_MSG_ID),
        "source_review_message_id": str(REVIEW_EXECUTION_MSG_ID),
        "source_preflight_message_id": str(REVIEW_HANDOFF_MSG_ID),
        "source_diff_message_id": str(CANDIDATE_DIFF_MSG_ID),
        "disposition_id": str(disposition_id),
        "disposition_type": "AUTO_CONTINUE",
        "disposition_reason": "review_has_no_blocking_findings",
        "review_result_fingerprint": fp,
        "revalidated_review_result_fingerprint": fp,
        "source_diff_sha256": diff_sha256,
        "review_prompt_sha256": review_prompt_sha256,
        "review_scope_paths": list(review_scope_paths),
        "review_output_schema_version": REVIEW_OUTPUT_SCHEMA_VERSION,
        "source_review_verdict": "no_blocking_findings",
        "source_review_risk_level": "low",
        "continuation_eligible": True,
        "rework_eligible": False,
        "replay_check_completed": True,
        "prior_preflight_detected": False,
        "blocked_reasons": [],
        "ai_project_director_total_loop": "Partial",
    }
    for flag in _C1_FALSE_FLAGS:
        c1_action[flag] = False
    session.add(
        ProjectDirectorMessageTable(
            id=C1_PREFLIGHT_MSG_ID,
            session_id=SESSION_ID,
            role="assistant",
            content="Disposition consumption preflight ready.",
            sequence_no=seq,
            intent="sandbox_candidate_diff_review_disposition_consumption_preflight",
            related_project_id=PROJECT_ID,
            related_task_id=TASK_ID,
            source="system",
            source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([c1_action]),
            requires_confirmation=False,
            risk_level="high",
        )
    )
    session.commit()


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def db_engine(tmp_path):
    db_path = str(tmp_path / "test.db")
    engine = _make_test_engine(db_path)
    yield engine
    engine.dispose()


@pytest.fixture()
def fs_info(tmp_path):
    return _setup_filesystem(tmp_path)


@pytest.fixture()
def seeded_session(db_engine, fs_info, monkeypatch):
    from app.services.project_director_sandbox_workspace_guard_service import (
        ProjectDirectorSandboxWorkspaceGuardService,
    )

    workspace_root = fs_info["workspace_root"]

    def _patched_workspace_root():
        return workspace_root

    monkeypatch.setattr(
        ProjectDirectorSandboxWorkspaceGuardService,
        "_workspace_root",
        staticmethod(_patched_workspace_root),
    )
    monkeypatch.setattr(
        ProjectDirectorSandboxCandidateDiffService,
        "_workspace_root",
        staticmethod(_patched_workspace_root),
    )

    SessionLocal = _make_session_factory(db_engine)
    session = SessionLocal()
    _seed_base_records(session)
    _seed_message_chain(session, fs_info)
    session.close()
    return SessionLocal


def _make_c2_service(session_local, fs_info):
    session = session_local()
    msg_repo = ProjectDirectorMessageRepository(session)
    sess_repo = ProjectDirectorSessionRepository(session)
    task_repo = TaskRepository(session)
    handoff_svc = ProjectDirectorSandboxCandidateDiffReviewHandoffService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
    )
    diff_svc = ProjectDirectorSandboxCandidateDiffService(
        repo_root=fs_info["repo_root"],
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
    )
    svc = ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        review_handoff_service=handoff_svc,
        candidate_diff_service=diff_svc,
    )
    return svc, session


# ══════════════════════════════════════════════════════════════════════
# A. Repository transaction contract
# ══════════════════════════════════════════════════════════════════════


class TestRepositoryTransactionContract:
    def test_blocked_return_releases_lock(self, seeded_session, fs_info) -> None:
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=uuid4(),
        )
        assert result.result.consumption_status == "blocked"
        assert "source_consumption_preflight_message_missing" in result.result.blocked_reasons
        assert result.message is None
        session.close()
        session_b = seeded_session()
        session_b.execute(text("BEGIN IMMEDIATE"))
        session_b.commit()
        session_b.close()


# ══════════════════════════════════════════════════════════════════════
# B. Domain contract
# ══════════════════════════════════════════════════════════════════════


class TestDomainContract:
    def test_blocked_state(self, seeded_session, fs_info) -> None:
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=uuid4(),
        )
        assert result.result.consumption_status == "blocked"
        assert result.result.evidence_fresh is False
        assert result.result.disposition_consumed is False
        assert result.result.continuation_eligible is False
        assert result.result.rework_eligible is False
        assert len(result.result.blocked_reasons) > 0
        session.close()

    @pytest.mark.parametrize("flag", _CONSUMPTION_FALSE_FLAGS)
    def test_forbidden_side_effect_flag_rejected(self, flag: str) -> None:
        base_kwargs = dict(
            consumption_status="consumed",
            consumption_id=uuid4(),
            source_consumption_preflight_message_id=uuid4(),
            source_disposition_message_id=uuid4(),
            source_review_message_id=uuid4(),
            source_diff_message_id=uuid4(),
            disposition_id=uuid4(),
            disposition_type="AUTO_CONTINUE",
            review_result_fingerprint="a" * 64,
            revalidated_review_result_fingerprint="a" * 64,
            reviewed_diff_sha256="b" * 64,
            persisted_source_diff_sha256="b" * 64,
            current_diff_sha256="b" * 64,
            reviewed_scope_paths=["src/a.py"],
            persisted_source_scope_paths=["src/a.py"],
            current_scope_paths=["src/a.py"],
            workspace_path="/tmp/ws",
            workspace_path_within_root=True,
            source_diff_revalidated=True,
            current_diff_regenerated=True,
            evidence_fresh=True,
            continuation_eligible=True,
            replay_check_completed=True,
            consumed_at=datetime.now(timezone.utc),
        )
        base_kwargs[flag] = True
        with pytest.raises(ValueError, match="disposition consumption may not"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(**base_kwargs)

    def test_blocked_requires_reasons(self) -> None:
        with pytest.raises(ValueError, match="blocked consumption requires a reason"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(
                consumption_status="blocked",
                source_consumption_preflight_message_id=uuid4(),
                blocked_reasons=[],
            )

    def test_blocked_no_freshness(self) -> None:
        with pytest.raises(ValueError, match="blocked consumption may not consume fresh evidence"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(
                consumption_status="blocked",
                source_consumption_preflight_message_id=uuid4(),
                evidence_fresh=True,
                blocked_reasons=["some_reason"],
            )

    def test_blocked_no_consumed(self) -> None:
        with pytest.raises(ValueError, match="blocked consumption may not consume fresh evidence"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(
                consumption_status="blocked",
                source_consumption_preflight_message_id=uuid4(),
                disposition_consumed=True,
                blocked_reasons=["some_reason"],
            )

    def test_blocked_no_eligibility(self) -> None:
        with pytest.raises(ValueError, match="blocked consumption may not expose eligibility"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(
                consumption_status="blocked",
                source_consumption_preflight_message_id=uuid4(),
                continuation_eligible=True,
                blocked_reasons=["some_reason"],
            )

    def test_consumed_requires_ids(self) -> None:
        with pytest.raises(ValueError, match="consumed disposition requires complete evidence bindings"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(
                consumption_status="consumed",
                consumption_id=None,
                source_consumption_preflight_message_id=uuid4(),
                source_disposition_message_id=uuid4(),
                source_review_message_id=uuid4(),
                source_diff_message_id=uuid4(),
                disposition_id=uuid4(),
                disposition_type="AUTO_CONTINUE",
                review_result_fingerprint="a" * 64,
                revalidated_review_result_fingerprint="a" * 64,
                reviewed_diff_sha256="a" * 64,
                persisted_source_diff_sha256="a" * 64,
                current_diff_sha256="a" * 64,
                reviewed_scope_paths=["src/x.py"],
                persisted_source_scope_paths=["src/x.py"],
                current_scope_paths=["src/x.py"],
                workspace_path="/ws",
                workspace_path_within_root=True,
                source_diff_revalidated=True,
                current_diff_regenerated=True,
                evidence_fresh=True,
                disposition_consumed=True,
                replay_check_completed=True,
                continuation_eligible=True,
                consumed_at=datetime.now(timezone.utc),
            )

    def test_consumed_requires_auto_type(self) -> None:
        with pytest.raises(ValueError, match="consumed disposition requires an automatic type"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(
                consumption_status="consumed",
                consumption_id=uuid4(),
                source_consumption_preflight_message_id=uuid4(),
                source_disposition_message_id=uuid4(),
                source_review_message_id=uuid4(),
                source_diff_message_id=uuid4(),
                disposition_id=uuid4(),
                disposition_type=None,
                review_result_fingerprint="a" * 64,
                revalidated_review_result_fingerprint="a" * 64,
                reviewed_diff_sha256="a" * 64,
                persisted_source_diff_sha256="a" * 64,
                current_diff_sha256="a" * 64,
                reviewed_scope_paths=["src/x.py"],
                persisted_source_scope_paths=["src/x.py"],
                current_scope_paths=["src/x.py"],
                workspace_path="/ws",
                workspace_path_within_root=True,
                source_diff_revalidated=True,
                current_diff_regenerated=True,
                evidence_fresh=True,
                disposition_consumed=True,
                replay_check_completed=True,
                continuation_eligible=True,
                consumed_at=datetime.now(timezone.utc),
            )

    def test_consumed_requires_valid_sha(self) -> None:
        with pytest.raises(ValueError, match="consumed disposition requires valid fingerprints"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(
                consumption_status="consumed",
                consumption_id=uuid4(),
                source_consumption_preflight_message_id=uuid4(),
                source_disposition_message_id=uuid4(),
                source_review_message_id=uuid4(),
                source_diff_message_id=uuid4(),
                disposition_id=uuid4(),
                disposition_type="AUTO_CONTINUE",
                review_result_fingerprint="invalid_sha",
                revalidated_review_result_fingerprint="invalid_sha",
                reviewed_diff_sha256="invalid_sha",
                persisted_source_diff_sha256="invalid_sha",
                current_diff_sha256="invalid_sha",
                reviewed_scope_paths=["src/x.py"],
                persisted_source_scope_paths=["src/x.py"],
                current_scope_paths=["src/x.py"],
                workspace_path="/ws",
                workspace_path_within_root=True,
                source_diff_revalidated=True,
                current_diff_regenerated=True,
                evidence_fresh=True,
                disposition_consumed=True,
                replay_check_completed=True,
                continuation_eligible=True,
                consumed_at=datetime.now(timezone.utc),
            )

    def test_consumed_requires_matching_fingerprints(self) -> None:
        with pytest.raises(ValueError, match="consumed disposition requires matching review fingerprints"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(
                consumption_status="consumed",
                consumption_id=uuid4(),
                source_consumption_preflight_message_id=uuid4(),
                source_disposition_message_id=uuid4(),
                source_review_message_id=uuid4(),
                source_diff_message_id=uuid4(),
                disposition_id=uuid4(),
                disposition_type="AUTO_CONTINUE",
                review_result_fingerprint="a" * 64,
                revalidated_review_result_fingerprint="b" * 64,
                reviewed_diff_sha256="a" * 64,
                persisted_source_diff_sha256="a" * 64,
                current_diff_sha256="a" * 64,
                reviewed_scope_paths=["src/x.py"],
                persisted_source_scope_paths=["src/x.py"],
                current_scope_paths=["src/x.py"],
                workspace_path="/ws",
                workspace_path_within_root=True,
                source_diff_revalidated=True,
                current_diff_regenerated=True,
                evidence_fresh=True,
                disposition_consumed=True,
                replay_check_completed=True,
                continuation_eligible=True,
                consumed_at=datetime.now(timezone.utc),
            )

    def test_consumed_requires_matching_diff_shas(self) -> None:
        with pytest.raises(ValueError, match="consumed disposition requires matching diff fingerprints"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(
                consumption_status="consumed",
                consumption_id=uuid4(),
                source_consumption_preflight_message_id=uuid4(),
                source_disposition_message_id=uuid4(),
                source_review_message_id=uuid4(),
                source_diff_message_id=uuid4(),
                disposition_id=uuid4(),
                disposition_type="AUTO_CONTINUE",
                review_result_fingerprint="a" * 64,
                revalidated_review_result_fingerprint="a" * 64,
                reviewed_diff_sha256="a" * 64,
                persisted_source_diff_sha256="b" * 64,
                current_diff_sha256="a" * 64,
                reviewed_scope_paths=["src/x.py"],
                persisted_source_scope_paths=["src/x.py"],
                current_scope_paths=["src/x.py"],
                workspace_path="/ws",
                workspace_path_within_root=True,
                source_diff_revalidated=True,
                current_diff_regenerated=True,
                evidence_fresh=True,
                disposition_consumed=True,
                replay_check_completed=True,
                continuation_eligible=True,
                consumed_at=datetime.now(timezone.utc),
            )

    def test_consumed_requires_scopes(self) -> None:
        with pytest.raises(ValueError, match="consumed disposition requires matching ordered scopes"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(
                consumption_status="consumed",
                consumption_id=uuid4(),
                source_consumption_preflight_message_id=uuid4(),
                source_disposition_message_id=uuid4(),
                source_review_message_id=uuid4(),
                source_diff_message_id=uuid4(),
                disposition_id=uuid4(),
                disposition_type="AUTO_CONTINUE",
                review_result_fingerprint="a" * 64,
                revalidated_review_result_fingerprint="a" * 64,
                reviewed_diff_sha256="a" * 64,
                persisted_source_diff_sha256="a" * 64,
                current_diff_sha256="a" * 64,
                reviewed_scope_paths=[],
                persisted_source_scope_paths=[],
                current_scope_paths=[],
                workspace_path="/ws",
                workspace_path_within_root=True,
                source_diff_revalidated=True,
                current_diff_regenerated=True,
                evidence_fresh=True,
                disposition_consumed=True,
                replay_check_completed=True,
                continuation_eligible=True,
                consumed_at=datetime.now(timezone.utc),
            )

    def test_consumed_requires_workspace(self) -> None:
        with pytest.raises(ValueError, match="consumed disposition requires a trusted workspace"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(
                consumption_status="consumed",
                consumption_id=uuid4(),
                source_consumption_preflight_message_id=uuid4(),
                source_disposition_message_id=uuid4(),
                source_review_message_id=uuid4(),
                source_diff_message_id=uuid4(),
                disposition_id=uuid4(),
                disposition_type="AUTO_CONTINUE",
                review_result_fingerprint="a" * 64,
                revalidated_review_result_fingerprint="a" * 64,
                reviewed_diff_sha256="a" * 64,
                persisted_source_diff_sha256="a" * 64,
                current_diff_sha256="a" * 64,
                reviewed_scope_paths=["src/x.py"],
                persisted_source_scope_paths=["src/x.py"],
                current_scope_paths=["src/x.py"],
                workspace_path="",
                workspace_path_within_root=True,
                source_diff_revalidated=True,
                current_diff_regenerated=True,
                evidence_fresh=True,
                disposition_consumed=True,
                replay_check_completed=True,
                continuation_eligible=True,
                consumed_at=datetime.now(timezone.utc),
            )

    def test_consumed_requires_fresh_flags(self) -> None:
        with pytest.raises(ValueError, match="consumed disposition requires fresh unreplayed evidence"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(
                consumption_status="consumed",
                consumption_id=uuid4(),
                source_consumption_preflight_message_id=uuid4(),
                source_disposition_message_id=uuid4(),
                source_review_message_id=uuid4(),
                source_diff_message_id=uuid4(),
                disposition_id=uuid4(),
                disposition_type="AUTO_CONTINUE",
                review_result_fingerprint="a" * 64,
                revalidated_review_result_fingerprint="a" * 64,
                reviewed_diff_sha256="a" * 64,
                persisted_source_diff_sha256="a" * 64,
                current_diff_sha256="a" * 64,
                reviewed_scope_paths=["src/x.py"],
                persisted_source_scope_paths=["src/x.py"],
                current_scope_paths=["src/x.py"],
                workspace_path="/ws",
                workspace_path_within_root=True,
                source_diff_revalidated=True,
                current_diff_regenerated=True,
                evidence_fresh=False,
                disposition_consumed=True,
                replay_check_completed=True,
                continuation_eligible=True,
                consumed_at=datetime.now(timezone.utc),
            )

    def test_consumed_requires_no_prior(self) -> None:
        with pytest.raises(ValueError, match="consumed disposition requires fresh unreplayed evidence"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(
                consumption_status="consumed",
                consumption_id=uuid4(),
                source_consumption_preflight_message_id=uuid4(),
                source_disposition_message_id=uuid4(),
                source_review_message_id=uuid4(),
                source_diff_message_id=uuid4(),
                disposition_id=uuid4(),
                disposition_type="AUTO_CONTINUE",
                review_result_fingerprint="a" * 64,
                revalidated_review_result_fingerprint="a" * 64,
                reviewed_diff_sha256="a" * 64,
                persisted_source_diff_sha256="a" * 64,
                current_diff_sha256="a" * 64,
                reviewed_scope_paths=["src/x.py"],
                persisted_source_scope_paths=["src/x.py"],
                current_scope_paths=["src/x.py"],
                workspace_path="/ws",
                workspace_path_within_root=True,
                source_diff_revalidated=True,
                current_diff_regenerated=True,
                evidence_fresh=True,
                disposition_consumed=True,
                replay_check_completed=True,
                prior_consumption_detected=True,
                continuation_eligible=True,
                consumed_at=datetime.now(timezone.utc),
            )

    def test_consumed_requires_no_blocked(self) -> None:
        with pytest.raises(ValueError, match="consumed disposition may not be blocked"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(
                consumption_status="consumed",
                consumption_id=uuid4(),
                source_consumption_preflight_message_id=uuid4(),
                source_disposition_message_id=uuid4(),
                source_review_message_id=uuid4(),
                source_diff_message_id=uuid4(),
                disposition_id=uuid4(),
                disposition_type="AUTO_CONTINUE",
                review_result_fingerprint="a" * 64,
                revalidated_review_result_fingerprint="a" * 64,
                reviewed_diff_sha256="a" * 64,
                persisted_source_diff_sha256="a" * 64,
                current_diff_sha256="a" * 64,
                reviewed_scope_paths=["src/x.py"],
                persisted_source_scope_paths=["src/x.py"],
                current_scope_paths=["src/x.py"],
                workspace_path="/ws",
                workspace_path_within_root=True,
                source_diff_revalidated=True,
                current_diff_regenerated=True,
                evidence_fresh=True,
                disposition_consumed=True,
                replay_check_completed=True,
                continuation_eligible=True,
                blocked_reasons=["stale"],
                consumed_at=datetime.now(timezone.utc),
            )

    def test_consumed_requires_eligibility_match(self) -> None:
        with pytest.raises(ValueError, match="consumption eligibility must match disposition type"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(
                consumption_status="consumed",
                consumption_id=uuid4(),
                source_consumption_preflight_message_id=uuid4(),
                source_disposition_message_id=uuid4(),
                source_review_message_id=uuid4(),
                source_diff_message_id=uuid4(),
                disposition_id=uuid4(),
                disposition_type="AUTO_CONTINUE",
                review_result_fingerprint="a" * 64,
                revalidated_review_result_fingerprint="a" * 64,
                reviewed_diff_sha256="a" * 64,
                persisted_source_diff_sha256="a" * 64,
                current_diff_sha256="a" * 64,
                reviewed_scope_paths=["src/x.py"],
                persisted_source_scope_paths=["src/x.py"],
                current_scope_paths=["src/x.py"],
                workspace_path="/ws",
                workspace_path_within_root=True,
                source_diff_revalidated=True,
                current_diff_regenerated=True,
                evidence_fresh=True,
                disposition_consumed=True,
                replay_check_completed=True,
                continuation_eligible=False,
                rework_eligible=True,
                consumed_at=datetime.now(timezone.utc),
            )

    def test_consumed_requires_timezone(self) -> None:
        with pytest.raises(ValueError, match="consumed disposition requires a timezone-aware timestamp"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(
                consumption_status="consumed",
                consumption_id=uuid4(),
                source_consumption_preflight_message_id=uuid4(),
                source_disposition_message_id=uuid4(),
                source_review_message_id=uuid4(),
                source_diff_message_id=uuid4(),
                disposition_id=uuid4(),
                disposition_type="AUTO_CONTINUE",
                review_result_fingerprint="a" * 64,
                revalidated_review_result_fingerprint="a" * 64,
                reviewed_diff_sha256="a" * 64,
                persisted_source_diff_sha256="a" * 64,
                current_diff_sha256="a" * 64,
                reviewed_scope_paths=["src/x.py"],
                persisted_source_scope_paths=["src/x.py"],
                current_scope_paths=["src/x.py"],
                workspace_path="/ws",
                workspace_path_within_root=True,
                source_diff_revalidated=True,
                current_diff_regenerated=True,
                evidence_fresh=True,
                disposition_consumed=True,
                replay_check_completed=True,
                continuation_eligible=True,
                consumed_at=datetime(2025, 1, 1),
            )

    @staticmethod
    def _valid_consumed_kwargs() -> dict:
        return dict(
            consumption_status="consumed",
            consumption_id=uuid4(),
            source_consumption_preflight_message_id=uuid4(),
            source_disposition_message_id=uuid4(),
            source_review_message_id=uuid4(),
            source_diff_message_id=uuid4(),
            disposition_id=uuid4(),
            disposition_type="AUTO_CONTINUE",
            review_result_fingerprint="a" * 64,
            revalidated_review_result_fingerprint="a" * 64,
            reviewed_diff_sha256="b" * 64,
            persisted_source_diff_sha256="b" * 64,
            current_diff_sha256="b" * 64,
            reviewed_scope_paths=["src/x.py"],
            persisted_source_scope_paths=["src/x.py"],
            current_scope_paths=["src/x.py"],
            workspace_path="/ws",
            workspace_path_within_root=True,
            source_diff_revalidated=True,
            current_diff_regenerated=True,
            evidence_fresh=True,
            disposition_consumed=True,
            replay_check_completed=True,
            continuation_eligible=True,
            consumed_at=datetime.now(timezone.utc),
        )

    @pytest.mark.parametrize("field", [
        "consumption_id",
        "source_disposition_message_id",
        "source_review_message_id",
        "source_diff_message_id",
        "disposition_id",
    ])
    def test_consumed_requires_id_field(self, field: str) -> None:
        kwargs = self._valid_consumed_kwargs()
        kwargs[field] = None
        with pytest.raises(ValueError, match="consumed disposition requires complete evidence bindings"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(**kwargs)

    def test_consumed_rejects_workspace_outside_root(self) -> None:
        kwargs = self._valid_consumed_kwargs()
        kwargs["workspace_path_within_root"] = False
        with pytest.raises(ValueError, match="consumed disposition requires a trusted workspace"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(**kwargs)

    @pytest.mark.parametrize("field", [
        "source_diff_revalidated",
        "current_diff_regenerated",
        "evidence_fresh",
        "disposition_consumed",
        "replay_check_completed",
    ])
    def test_consumed_requires_true_flag(self, field: str) -> None:
        kwargs = self._valid_consumed_kwargs()
        kwargs[field] = False
        with pytest.raises(ValueError, match="consumed disposition requires fresh unreplayed evidence"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(**kwargs)

    def test_consumed_rejects_prior_consumption_detected(self) -> None:
        kwargs = self._valid_consumed_kwargs()
        kwargs["prior_consumption_detected"] = True
        with pytest.raises(ValueError, match="consumed disposition requires fresh unreplayed evidence"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(**kwargs)

    def test_consumed_rejects_scope_mismatch(self) -> None:
        kwargs = self._valid_consumed_kwargs()
        kwargs["current_scope_paths"] = ["src/other.py"]
        with pytest.raises(ValueError, match="consumed disposition requires matching ordered scopes"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(**kwargs)

    def test_consumed_rejects_total_loop_not_partial(self) -> None:
        kwargs = self._valid_consumed_kwargs()
        kwargs["ai_project_director_total_loop"] = "Full"
        with pytest.raises(ValueError):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(**kwargs)


# ══════════════════════════════════════════════════════════════════════
# C. C1 evidence validation
# ══════════════════════════════════════════════════════════════════════


class TestC1EvidenceValidation:
    def test_c1_evidence_missing(self, seeded_session, fs_info) -> None:
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=uuid4(),
        )
        assert result.result.consumption_status == "blocked"
        assert "source_consumption_preflight_message_missing" in result.result.blocked_reasons
        session.close()

    def test_c1_session_mismatch(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["session_id"] = str(uuid4())
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "c1_binding_invalid" in result.result.blocked_reasons
        session.close()

    def test_c1_task_mismatch(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["source_task_id"] = str(uuid4())
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "c1_binding_invalid" in result.result.blocked_reasons
        session.close()

    def test_c1_wrong_source_detail(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        row.source_detail = "wrong_source_detail"
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "source_message_is_not_p21_d_c1_ready_preflight" in result.result.blocked_reasons
        session.close()

    def test_c1_wrong_action_type(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["type"] = "wrong_action_type"
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "p21_d_c1_ready_preflight_record_missing" in result.result.blocked_reasons
        session.close()

    def test_c1_wrong_schema_version(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["schema_version"] = "wrong-version"
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "c1_schema_version_mismatch" in result.result.blocked_reasons
        session.close()

    def test_c1_preflight_status_not_ready(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["preflight_status"] = "blocked"
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "c1_preflight_status_not_ready" in result.result.blocked_reasons
        session.close()

    def test_c1_blocked_reasons_non_empty(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["blocked_reasons"] = ["some_reason"]
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "c1_preflight_not_clean" in result.result.blocked_reasons
        session.close()

    def test_c1_source_not_system(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        row.source = "ai"
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "source_consumption_preflight_source_invalid" in result.result.blocked_reasons
        assert result.message is None
        assert result.result.disposition_consumed is False
        session.close()

    def test_c1_requires_confirmation_true(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        row.requires_confirmation = True
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "source_consumption_preflight_confirmation_contract_invalid" in result.result.blocked_reasons
        assert result.message is None
        assert result.result.disposition_consumed is False
        session.close()

    def test_c1_empty_actions(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        row.suggested_actions_json = json.dumps([])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "p21_d_c1_ready_preflight_record_missing" in result.result.blocked_reasons
        assert result.message is None
        assert result.result.disposition_consumed is False
        session.close()

    def test_c1_replay_not_completed(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["replay_check_completed"] = False
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "c1_preflight_not_clean" in result.result.blocked_reasons
        assert result.message is None
        assert result.result.disposition_consumed is False
        session.close()

    def test_c1_prior_preflight_detected(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["prior_preflight_detected"] = True
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "c1_preflight_not_clean" in result.result.blocked_reasons
        assert result.message is None
        assert result.result.disposition_consumed is False
        session.close()

    @pytest.mark.parametrize("field", [
        "source_disposition_message_id",
        "source_review_message_id",
        "source_preflight_message_id",
        "source_diff_message_id",
        "disposition_id",
    ])
    def test_c1_invalid_uuid_field(self, seeded_session, fs_info, field: str) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action[field] = "not-uuid"
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "c1_binding_invalid" in result.result.blocked_reasons
        assert result.message is None
        assert result.result.disposition_consumed is False
        assert result.result.continuation_eligible is False
        assert result.result.rework_eligible is False
        session.close()

    @pytest.mark.parametrize("field", [
        "review_result_fingerprint",
        "revalidated_review_result_fingerprint",
        "source_diff_sha256",
        "review_prompt_sha256",
    ])
    def test_c1_invalid_sha256_field(self, seeded_session, fs_info, field: str) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action[field] = "zzz"
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "c1_fingerprint_invalid" in result.result.blocked_reasons
        assert result.message is None
        assert result.result.disposition_consumed is False
        assert result.result.continuation_eligible is False
        assert result.result.rework_eligible is False
        session.close()

    def test_c1_fingerprints_differ(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        original_fp = action["review_result_fingerprint"]
        assert len(original_fp) == 64
        different_fp = hashlib.sha256(b"different-canonical-payload").hexdigest()
        assert different_fp != original_fp
        action["revalidated_review_result_fingerprint"] = different_fp
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "c1_review_fingerprint_mismatch" in result.result.blocked_reasons
        assert result.message is None
        assert result.result.disposition_consumed is False
        assert result.result.continuation_eligible is False
        assert result.result.rework_eligible is False
        session.close()

    def test_c1_empty_scope(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["review_scope_paths"] = []
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "c1_scope_invalid" in result.result.blocked_reasons
        assert result.message is None
        assert result.result.disposition_consumed is False
        session.close()

    def test_c1_duplicate_scope(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["review_scope_paths"] = ["a.py", "a.py"]
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "c1_scope_invalid" in result.result.blocked_reasons
        assert result.message is None
        assert result.result.disposition_consumed is False
        session.close()

    def test_c1_invalid_disposition_type(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["disposition_type"] = "UNKNOWN"
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "c1_eligibility_invalid" in result.result.blocked_reasons
        assert result.message is None
        assert result.result.disposition_consumed is False
        session.close()

    def test_c1_empty_disposition_reason(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["disposition_reason"] = ""
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "c1_binding_invalid" in result.result.blocked_reasons
        assert result.message is None
        assert result.result.disposition_consumed is False
        session.close()

    def test_c1_invalid_verdict(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["source_review_verdict"] = "unknown"
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "c1_binding_invalid" in result.result.blocked_reasons
        assert result.message is None
        assert result.result.disposition_consumed is False
        session.close()

    def test_c1_invalid_risk(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["source_review_risk_level"] = "unknown"
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "c1_binding_invalid" in result.result.blocked_reasons
        assert result.message is None
        assert result.result.disposition_consumed is False
        session.close()

    @pytest.mark.parametrize("flag", _C1_FALSE_FLAGS)
    def test_c1_write_boundary_violated(self, seeded_session, fs_info, flag: str) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action[flag] = True
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "c1_write_boundary_violated" in result.result.blocked_reasons
        assert result.message is None
        assert result.result.disposition_consumed is False
        assert result.result.continuation_eligible is False
        assert result.result.rework_eligible is False
        session.close()

    def test_c1_total_loop_not_partial(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["ai_project_director_total_loop"] = "Full"
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "c1_write_boundary_violated" in result.result.blocked_reasons
        assert result.message is None
        assert result.result.disposition_consumed is False
        session.close()


# ══════════════════════════════════════════════════════════════════════
# D. AUTO_CONTINUE unchanged success
# ══════════════════════════════════════════════════════════════════════


class TestAutoContinueUnchanged:
    def test_auto_continue_consumed(self, seeded_session, fs_info) -> None:
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "consumed"
        assert result.result.evidence_fresh is True
        assert result.result.disposition_consumed is True
        assert result.result.continuation_eligible is True
        assert result.result.rework_eligible is False
        assert result.result.source_diff_revalidated is True
        assert result.result.current_diff_regenerated is True
        assert result.result.replay_check_completed is True
        assert result.result.prior_consumption_detected is False
        assert result.result.blocked_reasons == []
        assert (
            result.result.reviewed_diff_sha256
            == result.result.persisted_source_diff_sha256
            == result.result.current_diff_sha256
        )
        assert (
            result.result.reviewed_scope_paths
            == result.result.persisted_source_scope_paths
            == result.result.current_scope_paths
        )
        assert result.message is not None
        session.close()


# ══════════════════════════════════════════════════════════════════════
# E. AUTO_REWORK unchanged success
# ══════════════════════════════════════════════════════════════════════


class TestAutoReworkUnchanged:
    def test_auto_rework_consumed(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, REVIEW_EXECUTION_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["verdict"] = "changes_required"
        action["risk_level"] = "medium"
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        fp = _compute_review_result_fingerprint(
            source_diff_sha256=fs_info["diff_sha256"],
            review_prompt_sha256=fs_info["review_prompt_sha256"],
            review_scope_paths=[fs_info.get("relative_path", "src/example.py")],
            raw_output_sha256=fs_info["raw_output_sha256"],
            verdict="changes_required", risk_level="medium",
        )
        disp_row = sess.get(ProjectDirectorMessageTable, DISPOSITION_MSG_ID)
        disp_action = json.loads(disp_row.suggested_actions_json)[0]
        disp_action["disposition_type"] = "AUTO_REWORK"
        disp_action["disposition_reason"] = "review_changes_required_within_automatic_rework_boundary"
        disp_action["source_review_verdict"] = "changes_required"
        disp_action["source_review_risk_level"] = "medium"
        disp_action["review_result_fingerprint"] = fp
        disp_row.suggested_actions_json = json.dumps([disp_action])
        sess.commit()
        c1_row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        c1_action = json.loads(c1_row.suggested_actions_json)[0]
        c1_action["disposition_type"] = "AUTO_REWORK"
        c1_action["disposition_reason"] = "review_changes_required_within_automatic_rework_boundary"
        c1_action["source_review_verdict"] = "changes_required"
        c1_action["source_review_risk_level"] = "medium"
        c1_action["review_result_fingerprint"] = fp
        c1_action["revalidated_review_result_fingerprint"] = fp
        c1_action["continuation_eligible"] = False
        c1_action["rework_eligible"] = True
        c1_row.suggested_actions_json = json.dumps([c1_action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "consumed"
        assert result.result.disposition_type == "AUTO_REWORK"
        assert result.result.continuation_eligible is False
        assert result.result.rework_eligible is True
        assert result.result.evidence_fresh is True
        session.close()

    def test_auto_rework_no_side_effects(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, REVIEW_EXECUTION_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["verdict"] = "changes_required"
        action["risk_level"] = "medium"
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        fp = _compute_review_result_fingerprint(
            source_diff_sha256=fs_info["diff_sha256"],
            review_prompt_sha256=fs_info["review_prompt_sha256"],
            review_scope_paths=[fs_info.get("relative_path", "src/example.py")],
            raw_output_sha256=fs_info["raw_output_sha256"],
            verdict="changes_required", risk_level="medium",
        )
        disp_row = sess.get(ProjectDirectorMessageTable, DISPOSITION_MSG_ID)
        disp_action = json.loads(disp_row.suggested_actions_json)[0]
        disp_action["disposition_type"] = "AUTO_REWORK"
        disp_action["disposition_reason"] = "review_changes_required_within_automatic_rework_boundary"
        disp_action["source_review_verdict"] = "changes_required"
        disp_action["source_review_risk_level"] = "medium"
        disp_action["review_result_fingerprint"] = fp
        disp_row.suggested_actions_json = json.dumps([disp_action])
        sess.commit()
        c1_row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        c1_action = json.loads(c1_row.suggested_actions_json)[0]
        c1_action["disposition_type"] = "AUTO_REWORK"
        c1_action["disposition_reason"] = "review_changes_required_within_automatic_rework_boundary"
        c1_action["source_review_verdict"] = "changes_required"
        c1_action["source_review_risk_level"] = "medium"
        c1_action["review_result_fingerprint"] = fp
        c1_action["revalidated_review_result_fingerprint"] = fp
        c1_action["continuation_eligible"] = False
        c1_action["rework_eligible"] = True
        c1_row.suggested_actions_json = json.dumps([c1_action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "consumed"
        assert result.result.disposition_type == "AUTO_REWORK"
        assert result.result.rework_eligible is True
        assert result.result.continuation_eligible is False
        assert result.result.disposition_consumed is True
        assert result.result.evidence_fresh is True
        assert result.result.source_diff_revalidated is True
        assert result.result.current_diff_regenerated is True
        assert result.result.replay_check_completed is True
        assert result.result.prior_consumption_detected is False
        assert result.result.blocked_reasons == []
        for flag in _CONSUMPTION_FALSE_FLAGS:
            assert getattr(result.result, flag) is False, f"{flag} should be False"
        session.close()


# ══════════════════════════════════════════════════════════════════════
# F. Review fingerprint validation
# ══════════════════════════════════════════════════════════════════════


class TestReviewFingerprintValidation:
    def test_fingerprint_mismatch(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["review_result_fingerprint"] = "b" * 64
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "c1_review_fingerprint_mismatch" in result.result.blocked_reasons
        session.close()


# ══════════════════════════════════════════════════════════════════════
# F2. Review message revalidation
# ══════════════════════════════════════════════════════════════════════


class TestReviewMessageRevalidation:
    def _run_with_recording(self, seeded_session, fs_info, tamper_fn=None):
        RecordingCandidateDiffInvocationService.invocation_count = 0
        session_factory = seeded_session()
        if tamper_fn is not None:
            tamper_fn(session_factory)
            session_factory.close()
            session_factory = seeded_session()
        session = session_factory
        msg_repo = ProjectDirectorMessageRepository(session)
        sess_repo = ProjectDirectorSessionRepository(session)
        task_repo = TaskRepository(session)
        handoff_svc = ProjectDirectorSandboxCandidateDiffReviewHandoffService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
        )
        diff_svc = RecordingCandidateDiffInvocationService(
            repo_root=fs_info["repo_root"],
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
        )
        svc = ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
            review_handoff_service=handoff_svc,
            candidate_diff_service=diff_svc,
        )
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        session.close()
        return result

    def test_review_message_missing(self, seeded_session, fs_info) -> None:
        def tamper(sess):
            row = sess.get(ProjectDirectorMessageTable, REVIEW_EXECUTION_MSG_ID)
            sess.delete(row)
            sess.commit()

        result = self._run_with_recording(seeded_session, fs_info, tamper)
        assert result.result.consumption_status == "blocked"
        assert "source_review_message_missing" in result.result.blocked_reasons
        assert result.message is None
        assert RecordingCandidateDiffInvocationService.invocation_count == 0

    def test_review_preflight_id_tampered(self, seeded_session, fs_info) -> None:
        def tamper(sess):
            row = sess.get(ProjectDirectorMessageTable, REVIEW_EXECUTION_MSG_ID)
            action = json.loads(row.suggested_actions_json)[0]
            action["source_preflight_message_id"] = str(uuid4())
            row.suggested_actions_json = json.dumps([action])
            sess.commit()

        result = self._run_with_recording(seeded_session, fs_info, tamper)
        assert result.result.consumption_status == "blocked"
        assert "review_source_binding_mismatch" in result.result.blocked_reasons
        assert result.message is None
        assert RecordingCandidateDiffInvocationService.invocation_count == 0

    def test_review_diff_id_tampered(self, seeded_session, fs_info) -> None:
        def tamper(sess):
            row = sess.get(ProjectDirectorMessageTable, REVIEW_EXECUTION_MSG_ID)
            action = json.loads(row.suggested_actions_json)[0]
            action["source_diff_message_id"] = str(uuid4())
            row.suggested_actions_json = json.dumps([action])
            sess.commit()

        result = self._run_with_recording(seeded_session, fs_info, tamper)
        assert result.result.consumption_status == "blocked"
        assert "review_source_binding_mismatch" in result.result.blocked_reasons
        assert result.message is None
        assert RecordingCandidateDiffInvocationService.invocation_count == 0

    def test_review_diff_sha_tampered(self, seeded_session, fs_info) -> None:
        def tamper(sess):
            row = sess.get(ProjectDirectorMessageTable, REVIEW_EXECUTION_MSG_ID)
            action = json.loads(row.suggested_actions_json)[0]
            action["source_diff_sha256"] = hashlib.sha256(b"tampered").hexdigest()
            row.suggested_actions_json = json.dumps([action])
            sess.commit()

        result = self._run_with_recording(seeded_session, fs_info, tamper)
        assert result.result.consumption_status == "blocked"
        assert "review_source_binding_mismatch" in result.result.blocked_reasons
        assert "review_result_fingerprint_mismatch" in result.result.blocked_reasons
        assert result.message is None
        assert RecordingCandidateDiffInvocationService.invocation_count == 0

    def test_review_prompt_sha_tampered(self, seeded_session, fs_info) -> None:
        def tamper(sess):
            row = sess.get(ProjectDirectorMessageTable, REVIEW_EXECUTION_MSG_ID)
            action = json.loads(row.suggested_actions_json)[0]
            action["review_prompt_sha256"] = hashlib.sha256(b"tampered").hexdigest()
            row.suggested_actions_json = json.dumps([action])
            sess.commit()

        result = self._run_with_recording(seeded_session, fs_info, tamper)
        assert result.result.consumption_status == "blocked"
        assert "review_source_binding_mismatch" in result.result.blocked_reasons
        assert "review_result_fingerprint_mismatch" in result.result.blocked_reasons
        assert result.message is None
        assert RecordingCandidateDiffInvocationService.invocation_count == 0

    def test_review_scope_tampered(self, seeded_session, fs_info) -> None:
        def tamper(sess):
            row = sess.get(ProjectDirectorMessageTable, REVIEW_EXECUTION_MSG_ID)
            action = json.loads(row.suggested_actions_json)[0]
            action["review_scope_paths"] = ["src/tampered.py"]
            row.suggested_actions_json = json.dumps([action])
            sess.commit()

        result = self._run_with_recording(seeded_session, fs_info, tamper)
        assert result.result.consumption_status == "blocked"
        assert "review_source_binding_mismatch" in result.result.blocked_reasons
        assert "review_result_fingerprint_mismatch" in result.result.blocked_reasons
        assert result.message is None
        assert RecordingCandidateDiffInvocationService.invocation_count == 0

    def test_review_schema_tampered(self, seeded_session, fs_info) -> None:
        def tamper(sess):
            row = sess.get(ProjectDirectorMessageTable, REVIEW_EXECUTION_MSG_ID)
            action = json.loads(row.suggested_actions_json)[0]
            action["review_output_schema_version"] = "wrong-version"
            row.suggested_actions_json = json.dumps([action])
            sess.commit()

        result = self._run_with_recording(seeded_session, fs_info, tamper)
        assert result.result.consumption_status == "blocked"
        assert "review_output_schema_version_mismatch" in result.result.blocked_reasons
        assert result.message is None
        assert RecordingCandidateDiffInvocationService.invocation_count == 0

    def test_review_verdict_tampered(self, seeded_session, fs_info) -> None:
        def tamper(sess):
            row = sess.get(ProjectDirectorMessageTable, REVIEW_EXECUTION_MSG_ID)
            action = json.loads(row.suggested_actions_json)[0]
            action["verdict"] = "invalid_verdict"
            row.suggested_actions_json = json.dumps([action])
            sess.commit()

        result = self._run_with_recording(seeded_session, fs_info, tamper)
        assert result.result.consumption_status == "blocked"
        assert "source_review_verdict_invalid" in result.result.blocked_reasons
        assert result.message is None
        assert RecordingCandidateDiffInvocationService.invocation_count == 0

    def test_review_risk_tampered(self, seeded_session, fs_info) -> None:
        def tamper(sess):
            row = sess.get(ProjectDirectorMessageTable, REVIEW_EXECUTION_MSG_ID)
            action = json.loads(row.suggested_actions_json)[0]
            action["risk_level"] = "invalid_risk"
            row.suggested_actions_json = json.dumps([action])
            sess.commit()

        result = self._run_with_recording(seeded_session, fs_info, tamper)
        assert result.result.consumption_status == "blocked"
        assert "source_review_risk_level_invalid" in result.result.blocked_reasons
        assert result.message is None
        assert RecordingCandidateDiffInvocationService.invocation_count == 0


# ══════════════════════════════════════════════════════════════════════
# G. Persisted source diff validation
# ══════════════════════════════════════════════════════════════════════


class TestPersistedSourceDiffValidation:
    def test_source_diff_sha256_mismatch(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        c1_row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        c1_action = json.loads(c1_row.suggested_actions_json)[0]
        c1_action["source_diff_sha256"] = hashlib.sha256(b"tampered").hexdigest()
        c1_row.suggested_actions_json = json.dumps([c1_action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "review_source_binding_mismatch" in result.result.blocked_reasons
        session.close()

    def test_review_scope_paths_mismatch(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        c1_row = sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        c1_action = json.loads(c1_row.suggested_actions_json)[0]
        c1_action["review_scope_paths"] = ["src/tampered.py"]
        c1_row.suggested_actions_json = json.dumps([c1_action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "review_source_binding_mismatch" in result.result.blocked_reasons
        session.close()

    def test_diff_message_missing(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, CANDIDATE_DIFF_MSG_ID)
        sess.delete(row)
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "source_diff_message_missing" in result.result.blocked_reasons
        session.close()

    def test_diff_wrong_source_detail(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, CANDIDATE_DIFF_MSG_ID)
        row.source_detail = "wrong_detail"
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "source_diff_validation_failed" in result.result.blocked_reasons
        assert "review_evidence_stale" in result.result.blocked_reasons
        session.close()

    def test_diff_text_tampered(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, CANDIDATE_DIFF_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["unified_diff_text"] = "tampered diff text\n"
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "source_diff_validation_failed" in result.result.blocked_reasons
        assert "review_evidence_stale" in result.result.blocked_reasons
        session.close()

    def test_diff_bytes_mismatch(self, seeded_session, fs_info) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, CANDIDATE_DIFF_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["diff_bytes"] = 999999
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        session.close()

    def test_diff_legitimate_but_different_sha(self, seeded_session, fs_info) -> None:
        import difflib
        old_text = "line one\nline two\nline three\n"
        new_text = "line one\nline two modified\nline three\n"
        diff_lines = difflib.unified_diff(
            old_text.splitlines(), new_text.splitlines(),
            fromfile="a/src/example.py", tofile="b/src/example.py", lineterm="",
        )
        new_diff_text = "\n".join(diff_lines) + "\n"
        new_sha = hashlib.sha256(new_diff_text.encode("utf-8")).hexdigest()
        new_bytes = len(new_diff_text.encode("utf-8"))
        rel = fs_info.get("relative_path", "src/example.py")
        ws_path = fs_info["workspace_path"]
        repo_root = fs_info["repo_root"]
        new_entry = {
            "relative_path": rel,
            "operation": "update",
            "target_file_path": (repo_root / rel).as_posix(),
            "candidate_file_path": (ws_path / rel).as_posix(),
            "target_file_existed": True,
            "candidate_file_existed": True,
            "target_file_content_read": True,
            "candidate_file_content_read": True,
            "unified_diff": new_diff_text,
            "diff_bytes": new_bytes,
        }
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, CANDIDATE_DIFF_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["unified_diff_text"] = new_diff_text
        action["diff_bytes"] = new_bytes
        action["diff_entries"] = [new_entry]
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "source_diff_sha256_mismatch" in result.result.blocked_reasons
        session.close()

    def test_diff_legitimate_but_different_scope(self, seeded_session, fs_info) -> None:
        rel = fs_info.get("relative_path", "src/example.py")
        ws_path = fs_info["workspace_path"]
        repo_root = fs_info["repo_root"]
        (repo_root / "src" / "other.py").write_text("other target\n", encoding="utf-8")
        (ws_path / "src" / "other.py").write_text("other candidate\n", encoding="utf-8")
        import difflib
        diff1 = difflib.unified_diff(
            "old content\n".splitlines(), "new content\n".splitlines(),
            fromfile=f"a/{rel}", tofile=f"b/{rel}", lineterm="",
        )
        diff_text1 = "\n".join(diff1) + "\n"
        diff2 = difflib.unified_diff(
            "other target\n".splitlines(), "other candidate\n".splitlines(),
            fromfile="a/src/other.py", tofile="b/src/other.py", lineterm="",
        )
        diff_text2 = "\n".join(diff2) + "\n"
        entry1 = {
            "relative_path": "src/other.py",
            "operation": "update",
            "target_file_path": (repo_root / "src" / "other.py").as_posix(),
            "candidate_file_path": (ws_path / "src" / "other.py").as_posix(),
            "target_file_existed": True, "candidate_file_existed": True,
            "target_file_content_read": True, "candidate_file_content_read": True,
            "unified_diff": diff_text2,
            "diff_bytes": len(diff_text2.encode("utf-8")),
        }
        entry2 = {
            "relative_path": rel,
            "operation": "update",
            "target_file_path": (repo_root / rel).as_posix(),
            "candidate_file_path": (ws_path / rel).as_posix(),
            "target_file_existed": True, "candidate_file_existed": True,
            "target_file_content_read": True, "candidate_file_content_read": True,
            "unified_diff": diff_text1,
            "diff_bytes": len(diff_text1.encode("utf-8")),
        }
        full_text = diff_text2 + diff_text1
        full_sha = hashlib.sha256(full_text.encode("utf-8")).hexdigest()
        full_bytes = len(full_text.encode("utf-8"))
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, CANDIDATE_DIFF_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["unified_diff_text"] = full_text
        action["diff_bytes"] = full_bytes
        action["diff_entries"] = [entry1, entry2]
        action["diff_file_count"] = 2
        action["candidate_files_considered_count"] = 2
        action["candidate_files_diffed_count"] = 2
        row.suggested_actions_json = json.dumps([action])
        sess.commit(); sess.close()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "review_scope_paths_mismatch" in result.result.blocked_reasons
        assert "review_evidence_stale" in result.result.blocked_reasons
        session.close()


# ══════════════════════════════════════════════════════════════════════
# H. Candidate file freshness
# ══════════════════════════════════════════════════════════════════════


class TestCandidateFileFreshness:
    def test_base_commit_unavailable_remains_fail_closed(
        self, seeded_session, fs_info, monkeypatch
    ) -> None:
        def _missing_head(_repo_root, *, blocked_reasons):
            blocked_reasons.append("base_commit_unavailable")
            return None

        monkeypatch.setattr(
            ProjectDirectorSandboxCandidateDiffService,
            "_read_repository_head",
            staticmethod(_missing_head),
        )
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert result.result.current_diff_regenerated is False
        assert "current_diff_regeneration_failed" in result.result.blocked_reasons
        assert "review_evidence_stale" in result.result.blocked_reasons
        assert result.message is None
        session.close()

    def test_candidate_file_stale(self, seeded_session, fs_info) -> None:
        rel = fs_info.get("relative_path", "src/example.py")
        (fs_info["workspace_path"] / rel).write_text("stale content\n", encoding="utf-8")
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert result.result.current_diff_regenerated is False
        assert "current_diff_regeneration_failed" in result.result.blocked_reasons
        assert "review_evidence_stale" in result.result.blocked_reasons
        assert result.message is None
        session.close()

    def test_candidate_content_larger(self, seeded_session, fs_info) -> None:
        rel = fs_info.get("relative_path", "src/example.py")
        much_larger = "x" * 5000 + "\n"
        (fs_info["workspace_path"] / rel).write_text(much_larger, encoding="utf-8")
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert result.result.current_diff_regenerated is False
        assert "current_diff_regeneration_failed" in result.result.blocked_reasons
        assert "review_evidence_stale" in result.result.blocked_reasons
        assert "current_diff_mismatch" not in result.result.blocked_reasons
        assert result.message is None
        session.close()

    def test_candidate_content_smaller(self, seeded_session, fs_info) -> None:
        rel = fs_info.get("relative_path", "src/example.py")
        shorter = "tiny\n"
        persisted_diff_bytes = len(fs_info["unified_diff_text"].encode("utf-8"))
        expected_diff = _make_unified_diff(rel, TARGET_CONTENT, shorter)
        assert expected_diff
        assert len(expected_diff.encode("utf-8")) < persisted_diff_bytes
        (fs_info["workspace_path"] / rel).write_text(shorter, encoding="utf-8")
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert result.result.current_diff_regenerated is True
        assert "current_diff_mismatch" in result.result.blocked_reasons
        assert "review_evidence_stale" in result.result.blocked_reasons
        assert "current_diff_regeneration_failed" not in result.result.blocked_reasons
        assert result.message is None
        session.close()

    def test_candidate_same_length_different_content(self, seeded_session, fs_info) -> None:
        rel = fs_info.get("relative_path", "src/example.py")
        original_candidate = CANDIDATE_CONTENT
        changed_candidate = "alt content\n"
        assert original_candidate != changed_candidate
        assert len(original_candidate.encode("utf-8")) == len(changed_candidate.encode("utf-8"))
        persisted_diff_bytes = len(fs_info["unified_diff_text"].encode("utf-8"))
        expected_diff = _make_unified_diff(rel, TARGET_CONTENT, changed_candidate)
        assert expected_diff
        assert len(expected_diff.encode("utf-8")) <= persisted_diff_bytes
        (fs_info["workspace_path"] / rel).write_text(changed_candidate, encoding="utf-8")
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert result.result.current_diff_regenerated is True
        assert "current_diff_mismatch" in result.result.blocked_reasons
        assert "review_evidence_stale" in result.result.blocked_reasons
        assert "current_diff_regeneration_failed" not in result.result.blocked_reasons
        assert result.message is None
        session.close()


# ══════════════════════════════════════════════════════════════════════
# I. Target file freshness
# ══════════════════════════════════════════════════════════════════════


class TestMainTargetFreshness:
    def test_target_file_stale(self, seeded_session, fs_info) -> None:
        rel = fs_info.get("relative_path", "src/example.py")
        (fs_info["repo_root"] / rel).write_text("modified target\n", encoding="utf-8")
        assert _commit_repository_change(fs_info["repo_root"], "target drift") != fs_info["base_commit_sha"]
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert result.result.current_diff_regenerated is False
        assert "current_diff_regeneration_failed" in result.result.blocked_reasons
        assert "review_evidence_stale" in result.result.blocked_reasons
        assert result.message is None
        session.close()

    def test_target_changed_regenerated(self, seeded_session, fs_info) -> None:
        rel = fs_info.get("relative_path", "src/example.py")
        changed_target = "alt target\n"
        assert TARGET_CONTENT != changed_target
        assert len(TARGET_CONTENT.encode("utf-8")) != len(changed_target.encode("utf-8"))
        persisted_diff_bytes = len(fs_info["unified_diff_text"].encode("utf-8"))
        expected_diff = _make_unified_diff(rel, changed_target, CANDIDATE_CONTENT)
        assert expected_diff
        assert len(expected_diff.encode("utf-8")) <= persisted_diff_bytes
        (fs_info["repo_root"] / rel).write_text(changed_target, encoding="utf-8")
        assert _commit_repository_change(fs_info["repo_root"], "target drift") != fs_info["base_commit_sha"]
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert result.result.current_diff_regenerated is True
        assert "current_diff_mismatch" in result.result.blocked_reasons
        assert "review_evidence_stale" in result.result.blocked_reasons
        assert "current_diff_regeneration_failed" not in result.result.blocked_reasons
        assert result.message is None
        session.close()


# ══════════════════════════════════════════════════════════════════════
# J. Workspace and manifest freshness
# ══════════════════════════════════════════════════════════════════════


class TestWorkspaceAndManifestFreshness:
    def test_workspace_deleted(self, seeded_session, fs_info) -> None:
        import shutil
        shutil.rmtree(fs_info["workspace_path"])
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "current_diff_regeneration_failed" in result.result.blocked_reasons
        session.close()

    def test_manifest_deleted(self, seeded_session, fs_info) -> None:
        manifest_file = (
            fs_info["workspace_path"] / INTERNAL_MANIFEST_DIR_NAME / INTERNAL_MANIFEST_FILE_NAME
        )
        manifest_file.unlink()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "current_diff_regeneration_failed" in result.result.blocked_reasons
        session.close()

    def test_manifest_invalid_json(self, seeded_session, fs_info) -> None:
        manifest_file = (
            fs_info["workspace_path"] / INTERNAL_MANIFEST_DIR_NAME / INTERNAL_MANIFEST_FILE_NAME
        )
        manifest_file.write_text("not valid json {{{", encoding="utf-8")
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "current_diff_regeneration_failed" in result.result.blocked_reasons
        session.close()

    def test_manifest_binding_tampered(self, seeded_session, fs_info) -> None:
        manifest_file = (
            fs_info["workspace_path"] / INTERNAL_MANIFEST_DIR_NAME / INTERNAL_MANIFEST_FILE_NAME
        )
        manifest = {
            "schema_version": "p21-c-d.v1",
            "internal_manifest_only": True,
            "ai_project_director_total_loop": "Partial",
            "manifest_file_path": "/wrong/path/manifest.json",
        }
        manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "current_diff_regeneration_failed" in result.result.blocked_reasons
        session.close()

    def test_candidate_file_deleted(self, seeded_session, fs_info) -> None:
        rel = fs_info.get("relative_path", "src/example.py")
        (fs_info["workspace_path"] / rel).unlink()
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert "current_diff_regeneration_failed" in result.result.blocked_reasons
        session.close()

    def test_workspace_outside_root(self, seeded_session, fs_info, monkeypatch) -> None:
        from app.services.project_director_sandbox_workspace_guard_service import (
            ProjectDirectorSandboxWorkspaceGuardService,
        )
        outside_root = fs_info["workspace_root"].parent / "other-root"
        outside_root.mkdir(parents=True, exist_ok=True)

        def _patched_outside_root():
            return outside_root

        monkeypatch.setattr(
            ProjectDirectorSandboxWorkspaceGuardService,
            "_workspace_root",
            staticmethod(_patched_outside_root),
        )
        monkeypatch.setattr(
            ProjectDirectorSandboxCandidateDiffService,
            "_workspace_root",
            staticmethod(_patched_outside_root),
        )
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "blocked"
        assert result.result.workspace_path_within_root is False
        assert "trusted_workspace_invalid" in result.result.blocked_reasons
        assert "current_diff_regeneration_failed" in result.result.blocked_reasons
        assert "review_evidence_stale" in result.result.blocked_reasons
        assert result.message is None
        session.close()


# ══════════════════════════════════════════════════════════════════════
# K. Sequential replay
# ══════════════════════════════════════════════════════════════════════


class TestSequentialReplay:
    def test_second_call_blocked(self, seeded_session, fs_info) -> None:
        svc1, s1 = _make_c2_service(seeded_session, fs_info)
        r1 = svc1.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert r1.result.consumption_status == "consumed"
        assert r1.message is not None
        s1.close()
        svc2, s2 = _make_c2_service(seeded_session, fs_info)
        r2 = svc2.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert r2.result.consumption_status == "blocked"
        assert r2.result.prior_consumption_detected is True
        assert "disposition_already_consumed" in r2.result.blocked_reasons
        assert r2.message is None
        s2.close()


# ══════════════════════════════════════════════════════════════════════
# L. Full-session pagination
# ══════════════════════════════════════════════════════════════════════


class TestFullSessionPagination:
    def test_prior_consumption_found_beyond_first_page(self, seeded_session, fs_info) -> None:
        svc1, s1 = _make_c2_service(seeded_session, fs_info)
        r1 = svc1.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert r1.result.consumption_status == "consumed"
        assert r1.message is not None
        consumed_msg_id = r1.message.id
        s1.close()
        filler_sess = seeded_session()
        for i in range(105):
            filler_sess.add(ProjectDirectorMessageTable(
                id=uuid4(), session_id=SESSION_ID, role="assistant",
                content=f"filler {i}", sequence_no=1000 + i,
                source="system", source_detail="filler",
            ))
        filler_sess.commit()
        check_repo = ProjectDirectorMessageRepository(filler_sess)
        first_page, has_more = check_repo.list_by_session_id(session_id=SESSION_ID, limit=100)
        assert has_more is True
        assert consumed_msg_id not in {m.id for m in first_page}
        filler_sess.close()
        svc2, s2 = _make_c2_service(seeded_session, fs_info)
        r2 = svc2.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert r2.result.consumption_status == "blocked"
        assert r2.result.prior_consumption_detected is True
        assert "disposition_already_consumed" in r2.result.blocked_reasons
        s2.close()


# ══════════════════════════════════════════════════════════════════════
# L2. Ordered scope freshness
# ══════════════════════════════════════════════════════════════════════


def _setup_two_file_fixture(tmp_path):
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    (repo_root / "src").mkdir()
    (repo_root / "src" / "a.py").write_text("old a\n", encoding="utf-8")
    (repo_root / "src" / "b.py").write_text("old b\n", encoding="utf-8")
    base_commit_sha = _initialize_exact_base_repository(repo_root)

    workspace_root = (tmp_path / "project-director" / "sandbox-workspaces").resolve()
    workspace_root.mkdir(parents=True)
    workspace_path = (workspace_root / "ws1").resolve()
    workspace_path.mkdir()
    (workspace_path / "src").mkdir()
    (workspace_path / "src" / "a.py").write_text("new a\n", encoding="utf-8")
    (workspace_path / "src" / "b.py").write_text("new b\n", encoding="utf-8")

    manifest_dir = (workspace_path / INTERNAL_MANIFEST_DIR_NAME).resolve()
    manifest_dir.mkdir()
    manifest_file = (manifest_dir / INTERNAL_MANIFEST_FILE_NAME).resolve()
    manifest = {
        "schema_version": "p21-c-d.v1",
        "internal_manifest_only": True,
        "ai_project_director_total_loop": "Partial",
        "manifest_file_path": manifest_file.as_posix(),
    }
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")

    import difflib
    diff_a_lines = difflib.unified_diff(
        "old a\n".splitlines(), "new a\n".splitlines(),
        fromfile="a/src/a.py", tofile="b/src/a.py", lineterm="",
    )
    diff_a = "\n".join(diff_a_lines) + "\n"
    diff_b_lines = difflib.unified_diff(
        "old b\n".splitlines(), "new b\n".splitlines(),
        fromfile="a/src/b.py", tofile="b/src/b.py", lineterm="",
    )
    diff_b = "\n".join(diff_b_lines) + "\n"
    unified_diff_text = diff_a + diff_b
    diff_sha256 = hashlib.sha256(unified_diff_text.encode("utf-8")).hexdigest()
    raw_output_sha256 = hashlib.sha256(b"raw review output 2file").hexdigest()
    review_prompt_sha256 = hashlib.sha256(b"review prompt 2file").hexdigest()

    return {
        "repo_root": repo_root,
        "base_commit_sha": base_commit_sha,
        "workspace_root": workspace_root,
        "workspace_path": workspace_path,
        "unified_diff_text": unified_diff_text,
        "diff_sha256": diff_sha256,
        "raw_output_sha256": raw_output_sha256,
        "review_prompt_sha256": review_prompt_sha256,
        "relative_path": "src/a.py",
        "scope_paths": ["src/a.py", "src/b.py"],
    }


class TestOrderedScopeFreshness:
    def _seed_and_run(self, db_engine, tmp_path, tamper_fn=None, monkeypatch=None):
        from app.services.project_director_sandbox_workspace_guard_service import (
            ProjectDirectorSandboxWorkspaceGuardService,
        )
        two_fs = _setup_two_file_fixture(tmp_path)
        workspace_root = two_fs["workspace_root"]

        def _patched_workspace_root():
            return workspace_root

        monkeypatch.setattr(
            ProjectDirectorSandboxWorkspaceGuardService,
            "_workspace_root",
            staticmethod(_patched_workspace_root),
        )
        monkeypatch.setattr(
            ProjectDirectorSandboxCandidateDiffService,
            "_workspace_root",
            staticmethod(_patched_workspace_root),
        )

        SessionLocal = _make_session_factory(db_engine)
        seed_session = SessionLocal()
        _seed_base_records(seed_session)
        two_fs["scope_paths"] = ["src/a.py", "src/b.py"]
        _seed_message_chain(seed_session, two_fs)
        seed_session.close()

        if tamper_fn is not None:
            tamper_session = SessionLocal()
            tamper_fn(tamper_session, two_fs)
            tamper_session.close()

        session = SessionLocal()
        msg_repo = ProjectDirectorMessageRepository(session)
        sess_repo = ProjectDirectorSessionRepository(session)
        task_repo = TaskRepository(session)
        handoff_svc = ProjectDirectorSandboxCandidateDiffReviewHandoffService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
        )
        diff_svc = ProjectDirectorSandboxCandidateDiffService(
            repo_root=two_fs["repo_root"],
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
        )
        svc = ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
            review_handoff_service=handoff_svc,
            candidate_diff_service=diff_svc,
        )
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        session.close()
        return result, two_fs

    def test_scope_missing_path(self, db_engine, tmp_path, monkeypatch) -> None:
        def tamper(sess, two_fs):
            row = sess.get(ProjectDirectorMessageTable, CANDIDATE_FILE_WRITE_MSG_ID)
            action = json.loads(row.suggested_actions_json)[0]
            action["candidate_written_files"] = [
                action["candidate_written_files"][0]
            ]
            action["candidate_files_written_count"] = 1
            row.suggested_actions_json = json.dumps([action])
            sess.commit()

        result, _ = self._seed_and_run(db_engine, tmp_path, tamper, monkeypatch)
        assert result.result.consumption_status == "blocked"
        assert "current_diff_mismatch" in result.result.blocked_reasons
        assert "review_evidence_stale" in result.result.blocked_reasons

    def test_scope_extra_path(self, db_engine, tmp_path, monkeypatch) -> None:
        def tamper(sess, two_fs):
            row = sess.get(ProjectDirectorMessageTable, CANDIDATE_DIFF_MSG_ID)
            action = json.loads(row.suggested_actions_json)[0]
            extra_entry = {
                "relative_path": "src/extra.py",
                "operation": "update",
                "target_file_path": (two_fs["repo_root"] / "src" / "extra.py").as_posix(),
                "candidate_file_path": (two_fs["workspace_path"] / "src" / "extra.py").as_posix(),
                "target_file_existed": False,
                "candidate_file_existed": False,
                "target_file_content_read": False,
                "candidate_file_content_read": False,
                "unified_diff": "",
                "diff_bytes": 0,
            }
            action["diff_entries"].append(extra_entry)
            action["diff_file_count"] = 3
            action["candidate_files_considered_count"] = 3
            action["candidate_files_diffed_count"] = 3
            row.suggested_actions_json = json.dumps([action])
            sess.commit()

        result, _ = self._seed_and_run(db_engine, tmp_path, tamper, monkeypatch)
        assert result.result.consumption_status == "blocked"
        assert "source_diff_validation_failed" in result.result.blocked_reasons
        assert "review_evidence_stale" in result.result.blocked_reasons

    def test_scope_reordered(self, db_engine, tmp_path, monkeypatch) -> None:
        def tamper(sess, two_fs):
            row = sess.get(ProjectDirectorMessageTable, CANDIDATE_DIFF_MSG_ID)
            action = json.loads(row.suggested_actions_json)[0]
            action["diff_entries"] = list(reversed(action["diff_entries"]))
            row.suggested_actions_json = json.dumps([action])
            sess.commit()

        result, _ = self._seed_and_run(db_engine, tmp_path, tamper, monkeypatch)
        assert result.result.consumption_status == "blocked"
        assert "current_diff_mismatch" in result.result.blocked_reasons
        assert "review_evidence_stale" in result.result.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# M. No-side-effect evidence
# ══════════════════════════════════════════════════════════════════════


class TestNoSideEffectEvidence:
    def test_consumed_result_no_side_effects(self, seeded_session, fs_info) -> None:
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "consumed"
        for flag in _CONSUMPTION_FALSE_FLAGS:
            assert getattr(result.result, flag) is False, f"{flag} should be False"
        assert result.result.ai_project_director_total_loop == "Partial"
        session.close()

    def test_consumed_message_action_no_side_effects(self, seeded_session, fs_info) -> None:
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        action = result.message.suggested_actions[0]
        for flag in _CONSUMPTION_FALSE_FLAGS:
            assert action.get(flag) is False, f"{flag} should be False in action"
        assert action["ai_project_director_total_loop"] == "Partial"
        session.close()


# ══════════════════════════════════════════════════════════════════════
# N. Append-only persistence
# ══════════════════════════════════════════════════════════════════════


class TestAppendOnlyPersistence:
    def test_consumed_message_contract(self, seeded_session, fs_info) -> None:
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.message is not None
        msg = result.message
        assert msg.source_detail == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMED_SOURCE_DETAIL
        assert msg.requires_confirmation is False
        assert msg.source == ProjectDirectorMessageSource.SYSTEM
        assert msg.related_task_id == TASK_ID
        assert msg.session_id == SESSION_ID
        assert msg.role == ProjectDirectorMessageRole.ASSISTANT
        action = msg.suggested_actions[0]
        assert action["type"] == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_ACTION_TYPE
        assert action["schema_version"] == DISPOSITION_CONSUMPTION_SCHEMA_VERSION
        assert action["consumption_status"] == "consumed"
        assert action["session_id"] == str(SESSION_ID)
        assert action["source_task_id"] == str(TASK_ID)
        assert action["source_consumption_preflight_message_id"] == str(C1_PREFLIGHT_MSG_ID)
        assert action["disposition_type"] == "AUTO_CONTINUE"
        assert len(action["review_result_fingerprint"]) == 64
        assert action["review_result_fingerprint"] == action["revalidated_review_result_fingerprint"]
        assert action["reviewed_diff_sha256"] == action["persisted_source_diff_sha256"] == action["current_diff_sha256"]
        session.close()

    def test_old_records_unchanged(self, seeded_session, fs_info) -> None:
        pre_sess = seeded_session()
        review_row_before = pre_sess.get(ProjectDirectorMessageTable, REVIEW_EXECUTION_MSG_ID)
        review_snapshot = {
            "id": str(review_row_before.id),
            "session_id": str(review_row_before.session_id),
            "role": review_row_before.role,
            "content": review_row_before.content,
            "sequence_no": review_row_before.sequence_no,
            "source": review_row_before.source,
            "source_detail": review_row_before.source_detail,
            "suggested_actions_json": review_row_before.suggested_actions_json,
            "requires_confirmation": review_row_before.requires_confirmation,
            "risk_level": review_row_before.risk_level,
            "related_project_id": str(review_row_before.related_project_id),
            "related_task_id": str(review_row_before.related_task_id),
        }
        disp_row_before = pre_sess.get(ProjectDirectorMessageTable, DISPOSITION_MSG_ID)
        disp_snapshot = {
            "id": str(disp_row_before.id),
            "session_id": str(disp_row_before.session_id),
            "role": disp_row_before.role,
            "content": disp_row_before.content,
            "sequence_no": disp_row_before.sequence_no,
            "source": disp_row_before.source,
            "source_detail": disp_row_before.source_detail,
            "suggested_actions_json": disp_row_before.suggested_actions_json,
            "requires_confirmation": disp_row_before.requires_confirmation,
            "risk_level": disp_row_before.risk_level,
            "related_project_id": str(disp_row_before.related_project_id),
            "related_task_id": str(disp_row_before.related_task_id),
        }
        c1_row_before = pre_sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        c1_snapshot = {
            "id": str(c1_row_before.id),
            "session_id": str(c1_row_before.session_id),
            "role": c1_row_before.role,
            "content": c1_row_before.content,
            "sequence_no": c1_row_before.sequence_no,
            "source": c1_row_before.source,
            "source_detail": c1_row_before.source_detail,
            "suggested_actions_json": c1_row_before.suggested_actions_json,
            "requires_confirmation": c1_row_before.requires_confirmation,
            "risk_level": c1_row_before.risk_level,
            "related_project_id": str(c1_row_before.related_project_id),
            "related_task_id": str(c1_row_before.related_task_id),
        }
        pre_sess.close()

        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "consumed"
        session.close()

        post_sess = seeded_session()
        review_row_after = post_sess.get(ProjectDirectorMessageTable, REVIEW_EXECUTION_MSG_ID)
        assert str(review_row_after.id) == review_snapshot["id"]
        assert str(review_row_after.session_id) == review_snapshot["session_id"]
        assert review_row_after.role == review_snapshot["role"]
        assert review_row_after.content == review_snapshot["content"]
        assert review_row_after.sequence_no == review_snapshot["sequence_no"]
        assert review_row_after.source == review_snapshot["source"]
        assert review_row_after.source_detail == review_snapshot["source_detail"]
        assert review_row_after.suggested_actions_json == review_snapshot["suggested_actions_json"]
        assert review_row_after.requires_confirmation == review_snapshot["requires_confirmation"]
        assert review_row_after.risk_level == review_snapshot["risk_level"]

        disp_row_after = post_sess.get(ProjectDirectorMessageTable, DISPOSITION_MSG_ID)
        assert str(disp_row_after.id) == disp_snapshot["id"]
        assert str(disp_row_after.session_id) == disp_snapshot["session_id"]
        assert disp_row_after.role == disp_snapshot["role"]
        assert disp_row_after.content == disp_snapshot["content"]
        assert disp_row_after.sequence_no == disp_snapshot["sequence_no"]
        assert disp_row_after.source == disp_snapshot["source"]
        assert disp_row_after.source_detail == disp_snapshot["source_detail"]
        assert disp_row_after.suggested_actions_json == disp_snapshot["suggested_actions_json"]
        assert disp_row_after.requires_confirmation == disp_snapshot["requires_confirmation"]
        assert disp_row_after.risk_level == disp_snapshot["risk_level"]

        c1_row_after = post_sess.get(ProjectDirectorMessageTable, C1_PREFLIGHT_MSG_ID)
        assert str(c1_row_after.id) == c1_snapshot["id"]
        assert str(c1_row_after.session_id) == c1_snapshot["session_id"]
        assert c1_row_after.role == c1_snapshot["role"]
        assert c1_row_after.content == c1_snapshot["content"]
        assert c1_row_after.sequence_no == c1_snapshot["sequence_no"]
        assert c1_row_after.source == c1_snapshot["source"]
        assert c1_row_after.source_detail == c1_snapshot["source_detail"]
        assert c1_row_after.suggested_actions_json == c1_snapshot["suggested_actions_json"]
        assert c1_row_after.requires_confirmation == c1_snapshot["requires_confirmation"]
        assert c1_row_after.risk_level == c1_snapshot["risk_level"]
        post_sess.close()

    def test_consumed_action_complete(self, seeded_session, fs_info) -> None:
        svc, session = _make_c2_service(seeded_session, fs_info)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.message is not None
        action = result.message.suggested_actions[0]

        assert action["consumption_status"] == "consumed"

        assert UUID(action["consumption_id"])
        from datetime import datetime as _dt
        consumed_at = _dt.fromisoformat(action["consumed_at"])
        assert consumed_at.tzinfo is not None

        assert action["source_consumption_preflight_message_id"] == str(C1_PREFLIGHT_MSG_ID)
        assert action["source_disposition_message_id"] == str(DISPOSITION_MSG_ID)
        assert action["source_review_message_id"] == str(REVIEW_EXECUTION_MSG_ID)
        assert action["source_diff_message_id"] == str(CANDIDATE_DIFF_MSG_ID)
        assert action["disposition_id"] is not None

        assert action["disposition_type"] == "AUTO_CONTINUE"
        assert action["disposition_reason"] == "review_has_no_blocking_findings"

        assert len(action["review_result_fingerprint"]) == 64
        assert len(action["revalidated_review_result_fingerprint"]) == 64
        assert action["review_result_fingerprint"] == action["revalidated_review_result_fingerprint"]
        assert len(action["review_result_fingerprint"]) == 64

        assert len(action["reviewed_diff_sha256"]) == 64
        assert len(action["persisted_source_diff_sha256"]) == 64
        assert len(action["current_diff_sha256"]) == 64
        assert action["reviewed_diff_sha256"] == action["persisted_source_diff_sha256"] == action["current_diff_sha256"]

        assert len(action["review_prompt_sha256"]) == 64
        assert action["review_prompt_sha256"] == fs_info["review_prompt_sha256"]

        rel = fs_info.get("relative_path", "src/example.py")
        assert action["reviewed_scope_paths"] == [rel]
        assert action["persisted_source_scope_paths"] == [rel]
        assert action["current_scope_paths"] == [rel]

        assert action["workspace_path"] == fs_info["workspace_path"].as_posix()
        assert action["workspace_path_within_root"] is True

        assert action["source_diff_revalidated"] is True
        assert action["current_diff_regenerated"] is True
        assert action["evidence_fresh"] is True
        assert action["disposition_consumed"] is True
        assert action["continuation_eligible"] is True
        assert action["rework_eligible"] is False
        assert action["replay_check_completed"] is True
        assert action["prior_consumption_detected"] is False
        assert action["blocked_reasons"] == []

        for flag in _CONSUMPTION_FALSE_FLAGS:
            assert action.get(flag) is False, f"{flag} should be False in action"

        assert action["ai_project_director_total_loop"] == "Partial"

        assert result.message.risk_level == "high"

        session2 = seeded_session()
        count = session2.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd"
            ),
            {
                "sd": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMED_SOURCE_DETAIL,
            },
        ).scalar()
        assert count == 1
        session2.close()
        session.close()


# ══════════════════════════════════════════════════════════════════════
# O. Large diff (>200KB)
# ══════════════════════════════════════════════════════════════════════


class _RecordingCandidateDiffService(ProjectDirectorSandboxCandidateDiffService):
    """Test subclass that records max_diff_bytes."""

    last_max_diff_bytes: int | None = None

    def build_candidate_diff_from_sources(self, **kwargs):
        _RecordingCandidateDiffService.last_max_diff_bytes = kwargs.get("max_diff_bytes")
        return super().build_candidate_diff_from_sources(**kwargs)


class RecordingCandidateDiffInvocationService(ProjectDirectorSandboxCandidateDiffService):
    """Test subclass that records invocation count."""

    invocation_count: int = 0

    def build_candidate_diff_from_sources(self, **kwargs):
        RecordingCandidateDiffInvocationService.invocation_count += 1
        return super().build_candidate_diff_from_sources(**kwargs)


class TestLargeDiffR1:
    def test_large_diff_consumed(self, db_engine, tmp_path, monkeypatch) -> None:
        from app.services.project_director_sandbox_workspace_guard_service import (
            ProjectDirectorSandboxWorkspaceGuardService,
        )

        line_len = 120
        old_content = ("A" * line_len + "\n") * 1200
        new_content = ("B" * line_len + "\n") * 1200

        repo_root = (tmp_path / "repo").resolve()
        repo_root.mkdir()
        (repo_root / "src").mkdir()
        (repo_root / "src" / "big.py").write_text(old_content, encoding="utf-8")
        _initialize_exact_base_repository(repo_root)

        workspace_root = (tmp_path / "project-director" / "sandbox-workspaces").resolve()
        workspace_root.mkdir(parents=True)
        workspace_path = (workspace_root / "ws1").resolve()
        workspace_path.mkdir()
        (workspace_path / "src").mkdir()
        (workspace_path / "src" / "big.py").write_text(new_content, encoding="utf-8")
        manifest_dir = (workspace_path / INTERNAL_MANIFEST_DIR_NAME).resolve()
        manifest_dir.mkdir()
        manifest_file = (manifest_dir / INTERNAL_MANIFEST_FILE_NAME).resolve()
        manifest = {
            "schema_version": "p21-c-d.v1",
            "internal_manifest_only": True,
            "ai_project_director_total_loop": "Partial",
            "manifest_file_path": manifest_file.as_posix(),
        }
        manifest_file.write_text(json.dumps(manifest), encoding="utf-8")

        def _patched_workspace_root():
            return workspace_root

        monkeypatch.setattr(
            ProjectDirectorSandboxWorkspaceGuardService,
            "_workspace_root",
            staticmethod(_patched_workspace_root),
        )
        monkeypatch.setattr(
            ProjectDirectorSandboxCandidateDiffService,
            "_workspace_root",
            staticmethod(_patched_workspace_root),
        )

        unified_diff_text = _make_unified_diff("src/big.py", old_content, new_content)
        diff_sha256 = hashlib.sha256(unified_diff_text.encode("utf-8")).hexdigest()
        diff_bytes = len(unified_diff_text.encode("utf-8"))
        raw_output_sha256 = hashlib.sha256(b"raw review output large").hexdigest()
        review_prompt_sha256 = hashlib.sha256(b"review prompt large").hexdigest()
        review_scope_paths = ["src/big.py"]

        assert diff_bytes > 200_000, f"Large diff must exceed 200KB, got {diff_bytes}"

        large_fs_info = {
            "repo_root": repo_root,
            "workspace_root": workspace_root,
            "workspace_path": workspace_path,
            "unified_diff_text": unified_diff_text,
            "diff_sha256": diff_sha256,
            "raw_output_sha256": raw_output_sha256,
            "review_prompt_sha256": review_prompt_sha256,
            "relative_path": "src/big.py",
        }

        SessionLocal = _make_session_factory(db_engine)
        seed_sess = SessionLocal()
        _seed_base_records(seed_sess)
        _seed_message_chain(seed_sess, large_fs_info)
        seed_sess.close()

        _RecordingCandidateDiffService.last_max_diff_bytes = None

        session = SessionLocal()
        msg_repo = ProjectDirectorMessageRepository(session)
        sess_repo = ProjectDirectorSessionRepository(session)
        task_repo = TaskRepository(session)
        handoff_svc = ProjectDirectorSandboxCandidateDiffReviewHandoffService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
        )
        diff_svc = _RecordingCandidateDiffService(
            repo_root=repo_root,
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
        )
        svc = ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
            review_handoff_service=handoff_svc,
            candidate_diff_service=diff_svc,
        )

        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=C1_PREFLIGHT_MSG_ID,
        )
        assert result.result.consumption_status == "consumed", f"blocked_reasons={result.result.blocked_reasons}"
        assert _RecordingCandidateDiffService.last_max_diff_bytes == diff_bytes
        assert result.result.current_diff_sha256 == diff_sha256
        session.close()


# ══════════════════════════════════════════════════════════════════════
# P. Concurrent competition
# ══════════════════════════════════════════════════════════════════════


class HoldingImmediateTransactionRepository(ProjectDirectorMessageRepository):
    """Test-only repo: acquires BEGIN IMMEDIATE then holds until released."""

    def __init__(self, session, writer_lock_acquired, release_writer):
        super().__init__(session)
        self._writer_lock_acquired = writer_lock_acquired
        self._release_writer = release_writer

    @contextmanager
    def sqlite_immediate_transaction(self):
        with super().sqlite_immediate_transaction():
            self._writer_lock_acquired.set()
            if not self._release_writer.wait(timeout=10):
                raise TimeoutError("writer release timeout")
            yield


class AttemptSignalingRepository(ProjectDirectorMessageRepository):
    """Test-only repo: signals before and after entering BEGIN IMMEDIATE."""

    def __init__(self, session, second_writer_attempted, second_writer_entered):
        super().__init__(session)
        self._second_writer_attempted = second_writer_attempted
        self._second_writer_entered = second_writer_entered

    @contextmanager
    def sqlite_immediate_transaction(self):
        self._second_writer_attempted.set()
        with super().sqlite_immediate_transaction():
            self._second_writer_entered.set()
            yield


class TestConcurrentCompetition:
    def test_two_threads_one_consumed_one_blocked(self, db_engine, fs_info, monkeypatch) -> None:
        from app.services.project_director_sandbox_workspace_guard_service import (
            ProjectDirectorSandboxWorkspaceGuardService,
        )

        workspace_root = fs_info["workspace_root"]

        def _patched_workspace_root():
            return workspace_root

        monkeypatch.setattr(
            ProjectDirectorSandboxWorkspaceGuardService,
            "_workspace_root",
            staticmethod(_patched_workspace_root),
        )
        monkeypatch.setattr(
            ProjectDirectorSandboxCandidateDiffService,
            "_workspace_root",
            staticmethod(_patched_workspace_root),
        )

        SessionLocal = _make_session_factory(db_engine)
        seed_session = SessionLocal()
        _seed_base_records(seed_session)
        _seed_message_chain(seed_session, fs_info)
        seed_session.close()

        writer_lock_acquired = threading.Event()
        release_writer = threading.Event()
        second_writer_attempted = threading.Event()
        second_writer_entered = threading.Event()

        results = []
        errors = []

        def worker_a():
            session = SessionLocal()
            msg_repo = HoldingImmediateTransactionRepository(
                session, writer_lock_acquired, release_writer,
            )
            sess_repo = ProjectDirectorSessionRepository(session)
            task_repo = TaskRepository(session)
            handoff_svc = ProjectDirectorSandboxCandidateDiffReviewHandoffService(
                session_repository=sess_repo,
                message_repository=msg_repo,
                task_repository=task_repo,
            )
            diff_svc = ProjectDirectorSandboxCandidateDiffService(
                repo_root=fs_info["repo_root"],
                session_repository=sess_repo,
                message_repository=msg_repo,
                task_repository=task_repo,
            )
            svc = ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionService(
                session_repository=sess_repo,
                message_repository=msg_repo,
                task_repository=task_repo,
                review_handoff_service=handoff_svc,
                candidate_diff_service=diff_svc,
            )
            try:
                result = svc.prepare_candidate_diff_review_disposition_consumption(
                    session_id=SESSION_ID,
                    source_task_id=TASK_ID,
                    source_message_id=C1_PREFLIGHT_MSG_ID,
                )
                results.append(result)
            except Exception as e:
                errors.append(f"thread-a:{type(e).__name__}:{e}")
            finally:
                session.close()

        def worker_b():
            session = SessionLocal()
            msg_repo = AttemptSignalingRepository(
                session, second_writer_attempted, second_writer_entered,
            )
            sess_repo = ProjectDirectorSessionRepository(session)
            task_repo = TaskRepository(session)
            handoff_svc = ProjectDirectorSandboxCandidateDiffReviewHandoffService(
                session_repository=sess_repo,
                message_repository=msg_repo,
                task_repository=task_repo,
            )
            diff_svc = ProjectDirectorSandboxCandidateDiffService(
                repo_root=fs_info["repo_root"],
                session_repository=sess_repo,
                message_repository=msg_repo,
                task_repository=task_repo,
            )
            svc = ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionService(
                session_repository=sess_repo,
                message_repository=msg_repo,
                task_repository=task_repo,
                review_handoff_service=handoff_svc,
                candidate_diff_service=diff_svc,
            )
            try:
                result = svc.prepare_candidate_diff_review_disposition_consumption(
                    session_id=SESSION_ID,
                    source_task_id=TASK_ID,
                    source_message_id=C1_PREFLIGHT_MSG_ID,
                )
                results.append(result)
            except Exception as e:
                errors.append(f"thread-b:{type(e).__name__}:{e}")
            finally:
                session.close()

        t_a = threading.Thread(target=worker_a)
        t_a.start()

        if not writer_lock_acquired.wait(timeout=30):
            raise TimeoutError("thread A did not acquire writer lock")

        t_b = threading.Thread(target=worker_b)
        t_b.start()

        if not second_writer_attempted.wait(timeout=30):
            raise TimeoutError("thread B did not attempt writer lock")

        assert not second_writer_entered.wait(timeout=0.25), (
            "thread B entered SQLite immediate transaction while A still holds lock"
        )

        release_writer.set()

        t_a.join(timeout=30)
        t_b.join(timeout=30)

        assert second_writer_entered.wait(timeout=0), (
            "thread B never entered SQLite immediate transaction after A released"
        )
        assert not t_a.is_alive(), "thread A did not finish"
        assert not t_b.is_alive(), "thread B did not finish"
        assert len(errors) == 0, f"Unexpected errors: {errors}"
        assert len(results) == 2

        statuses = [r.result.consumption_status for r in results]
        assert statuses.count("consumed") == 1
        assert statuses.count("blocked") == 1

        consumed_result = next(r for r in results if r.result.consumption_status == "consumed")
        blocked_result = next(r for r in results if r.result.consumption_status == "blocked")
        assert consumed_result.message is not None
        assert blocked_result.message is None
        assert blocked_result.result.prior_consumption_detected is True
        assert "disposition_already_consumed" in blocked_result.result.blocked_reasons

        verify_session = SessionLocal()
        count = verify_session.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd"
            ),
            {
                "sd": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMED_SOURCE_DETAIL,
            },
        ).scalar()
        assert count == 1
        verify_session.execute(text("BEGIN IMMEDIATE"))
        verify_session.commit()
        verify_session.close()
