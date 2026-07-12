"""Shared test support for P23 protected transition tests."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import create_engine, event
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
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository


_SHA256 = lambda data: hashlib.sha256(data).hexdigest()
_DIFF_SHA256 = _SHA256(b"diff content")
_PROMPT_SHA256 = _SHA256(b"prompt content")
_RAW_OUTPUT_SHA256 = _SHA256(b"raw output")
_WORKSPACE_PATH = "/tmp/test-workspace-p23"


def make_test_engine(tmp_path: str):
    engine = create_engine(
        f"sqlite:///{tmp_path}",
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


def make_session_factory(engine):
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


def seed_base_records(
    session: Session,
    *,
    project_id: UUID | None = None,
    session_id: UUID | None = None,
    task_id: UUID | None = None,
) -> dict[str, UUID]:
    pid = project_id or uuid4()
    sid = session_id or uuid4()
    tid = task_id or uuid4()
    session.add(
        ProjectTable(
            id=pid, name="Test", summary="Test project",
            status="active", stage="intake",
        )
    )
    session.flush()
    acceptance = json.dumps([
        "safe_dry_run_task=true",
        "worker_simulate_required=true",
        "product_runtime_git_write_allowed=false",
    ])
    session.add(
        TaskTable(
            id=tid, project_id=pid, title="Test task",
            status="pending", priority="normal",
            input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
            risk_level="normal", human_status="none",
            source_draft_id="p12-test-draft", acceptance_criteria=acceptance,
        )
    )
    session.add(
        ProjectDirectorSessionTable(
            id=sid, project_id=pid,
            goal_text="Test goal", constraints="", status="confirmed",
        )
    )
    session.commit()
    return {"project_id": pid, "session_id": sid, "task_id": tid}


def valid_review_action(
    *,
    verdict: str = "no_blocking_findings",
    risk_level: str = "low",
    session_id: UUID | None = None,
    task_id: UUID | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    action: dict[str, Any] = {
        "type": "p21_c_sandbox_candidate_diff_readonly_review_execution_record",
        "session_id": str(session_id or uuid4()),
        "source_task_id": str(task_id or uuid4()),
        "source_preflight_message_id": str(uuid4()),
        "source_diff_message_id": str(uuid4()),
        "requested_reviewer_executor": "codex",
        "source_diff_sha256": _DIFF_SHA256,
        "review_prompt_sha256": _PROMPT_SHA256,
        "review_scope_paths": ["src/example.py"],
        "review_output_schema_version": "p21-c.v1",
        "adapter_status": "validated_output",
        "output_validation_status": "validated",
        "raw_output_sha256": _RAW_OUTPUT_SHA256,
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
        "workspace_path": _WORKSPACE_PATH,
        "workspace_path_within_root": True,
        "diff_generation_status": "generated",
        "readonly_real_diff_generated": True,
        "real_diff_generated": True,
        "diff_bytes": 100,
        "diff_file_count": 1,
        "unified_diff_text": "diff content",
        "diff_entries": [{"relative_path": "src/example.py", "unified_diff": "diff content", "operation": "update"}],
        "ai_project_director_total_loop": "Partial",
    }
    for flag in [
        "main_project_file_written", "sandbox_file_written", "manifest_file_written",
        "diff_file_written", "patch_applied", "git_write_performed",
        "worktree_created", "worker_started", "task_created", "run_created",
    ]:
        action[flag] = False
    action.update(overrides)
    return action


def seed_review_message(
    session: Session,
    *,
    session_id: UUID,
    task_id: UUID,
    project_id: UUID,
    msg_id: UUID | None = None,
    action: dict[str, Any] | None = None,
    seq_no: int = 50,
) -> UUID:
    mid = msg_id or uuid4()
    act = action or valid_review_action(session_id=session_id, task_id=task_id)
    session.add(
        ProjectDirectorMessageTable(
            id=mid, session_id=session_id, role="assistant",
            content="Readonly review executed.", sequence_no=seq_no,
            intent="sandbox_candidate_diff_readonly_review_execution",
            source="system",
            source_detail="p21_c_sandbox_candidate_diff_readonly_review_execution_executed",
            suggested_actions_json=json.dumps([act]),
            requires_confirmation=False, risk_level="high",
            related_project_id=project_id, related_task_id=task_id,
        )
    )
    session.commit()
    return mid


def make_repos(session_local):
    session = session_local()
    msg_repo = ProjectDirectorMessageRepository(session)
    sess_repo = ProjectDirectorSessionRepository(session)
    task_repo = TaskRepository(session)
    return session, msg_repo, sess_repo, task_repo


def count_messages_by_source_detail(
    msg_repo: ProjectDirectorMessageRepository,
    session_id: UUID,
    source_detail: str,
) -> int:
    msgs, _ = msg_repo.list_by_session_id(session_id=session_id, limit=200)
    return sum(1 for m in msgs if m.source_detail == source_detail)


def get_messages_by_source_detail(
    msg_repo: ProjectDirectorMessageRepository,
    session_id: UUID,
    source_detail: str,
) -> list[ProjectDirectorMessage]:
    msgs, _ = msg_repo.list_by_session_id(session_id=session_id, limit=200)
    return [m for m in msgs if m.source_detail == source_detail]
