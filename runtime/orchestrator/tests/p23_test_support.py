"""Shared test support for P23 protected transition tests."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from dataclasses import dataclass, field
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
    RunTable,
    TaskTable,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.run import Run, RunStatus
from app.domain.task import Task, TaskStatus
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.workers.task_worker import (
    WorkerReservedRunExecutionSnapshot,
    WorkerRunResult,
    WorkerSilentLaunchSnapshot,
)


_SHA256 = lambda data: hashlib.sha256(data).hexdigest()
DIFF_SHA256 = _SHA256(b"diff content")
PROMPT_SHA256 = _SHA256(b"prompt content")
RAW_OUTPUT_SHA256 = _SHA256(b"raw output")
WORKSPACE_PATH = "/tmp/test-workspace-p23"


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
    task_status: str = "pending",
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
            status=task_status, priority="normal",
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
        "source_diff_sha256": DIFF_SHA256,
        "review_prompt_sha256": PROMPT_SHA256,
        "review_scope_paths": ["src/example.py"],
        "review_output_schema_version": "p21-c.v1",
        "adapter_status": "validated_output",
        "output_validation_status": "validated",
        "raw_output_sha256": RAW_OUTPUT_SHA256,
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
        "workspace_path": WORKSPACE_PATH,
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
    run_repo = RunRepository(session)
    agent_sess_repo = AgentSessionRepository(session)
    return session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo


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


def make_run_record(
    session: Session,
    *,
    run_id: UUID | None = None,
    task_id: UUID,
    project_id: UUID,
    status: str = "running",
) -> UUID:
    rid = run_id or uuid4()
    session.add(
        RunTable(
            id=rid, task_id=task_id, project_id=project_id,
            status=status, route_reason="test",
            routing_score=1.0, strategy_code="test",
            model_name="test-model", dispatch_status="dispatched",
        )
    )
    session.commit()
    return rid


@dataclass
class FakeBudgetDecision:
    allowed: bool = True

    @property
    def pressure_level(self):
        return _FakePressure()

    @property
    def suggested_action(self):
        return _FakeAction()

    strategy_code: str = "normal"
    budget_policy_source: str = "test"

    @property
    def retry_status(self):
        return _FakeRetryStatus()


class _FakePressure:
    value = "normal"


class _FakeAction:
    value = "allow"


class _FakeRetryStatus:
    retry_limit_reached = False


@dataclass
class FakeFreshnessResult:
    current_freshness_fingerprint: str = "a" * 64
    current_diff_sha256: str = DIFF_SHA256
    current_scope_paths: list[str] = field(default_factory=lambda: ["src/example.py"])
    workspace_path: str = WORKSPACE_PATH
    workspace_path_within_root: bool = True
    blocked_reasons: list[str] = field(default_factory=list)


@dataclass
class FakeCurrentReservation:
    result: Any = None
    message: Any = None
    task: Any = None
    run: Any = None
    current_freshness: Any = None
    budget_decision: Any = None
    blocked_reasons: list[str] = field(default_factory=list)


def make_fake_worker_result(
    *,
    task_id: UUID,
    run_id: UUID,
    disposition_type: str = "AUTO_CONTINUE",
    git_activity: bool = False,
    contract_valid: bool = True,
) -> WorkerRunResult:
    execution_started = contract_valid
    continuation = disposition_type == "AUTO_CONTINUE" and execution_started
    rework = disposition_type == "AUTO_REWORK" and execution_started
    snapshot = WorkerReservedRunExecutionSnapshot(
        source="p23_d2_exact_reserved_run",
        exact_task_id=task_id,
        exact_run_id=run_id,
        reserved_run_execution_requested=True,
        exact_binding_validated=True,
        task_routed=False,
        task_claimed_in_this_cycle=False,
        run_created_in_this_cycle=False,
        budget_rechecked=True,
        existing_run_reused=True,
        shared_execution_seam_used=execution_started,
        product_runtime_git_write_allowed=False,
        blocked_reasons=[],
    )
    if not contract_valid:
        snapshot = WorkerReservedRunExecutionSnapshot(
            source="invalid_source",
            exact_task_id=task_id,
            exact_run_id=run_id,
            reserved_run_execution_requested=False,
            exact_binding_validated=False,
            task_routed=True,
            task_claimed_in_this_cycle=True,
            run_created_in_this_cycle=True,
            budget_rechecked=False,
            existing_run_reused=False,
            shared_execution_seam_used=False,
            product_runtime_git_write_allowed=True,
            blocked_reasons=[],
        )
    return WorkerRunResult(
        claimed=True,
        message="Worker executed successfully",
        execution_mode="fake",
        result_summary="Fake execution",
        reserved_run_execution_snapshot=snapshot,
        git_diff_dry_run_runs_write_git=git_activity,
    )


class SpyTaskWorker:
    """Fake TaskWorker that records calls without executing real runtime."""

    def __init__(self, *, result: WorkerRunResult | None = None, exception: Exception | None = None):
        self._result = result
        self._exception = exception
        self.run_reserved_once_calls: list[dict[str, UUID]] = []
        self.run_once_calls: list[dict[str, Any]] = []

    def run_reserved_once(self, *, task_id: UUID, run_id: UUID) -> WorkerRunResult:
        self.run_reserved_once_calls.append({"task_id": task_id, "run_id": run_id})
        if self._exception:
            raise self._exception
        return self._result

    def run_once(self, *, task_id: UUID | None = None) -> WorkerRunResult | None:
        self.run_once_calls.append({"task_id": task_id})
        return None


class SpyEventStream:
    """Fake event stream that records published events."""

    def __init__(self):
        self.events: list[dict[str, Any]] = []

    def publish(self, event_type: str, data: dict[str, Any]) -> None:
        self.events.append({"type": event_type, "data": data})

    def clear(self):
        self.events.clear()
