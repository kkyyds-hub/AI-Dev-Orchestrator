"""Targeted tests for P3-D3 runtime gate event persistence."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db_tables import ORMBase
from app.domain.agent_message import AgentMessageRole, AgentMessageType
from app.domain.agent_session import (
    AgentSessionPhase,
    AgentSessionReviewStatus,
    AgentSessionStatus,
    AgentType,
    RuntimeType,
)
from app.domain.project import Project
from app.domain.runtime_event import RUNTIME_EVENT_TYPES, RuntimeEventType
from app.domain.task import Task
from app.repositories.agent_message_repository import AgentMessageRepository
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.runtime_event_audit_service import RuntimeEventAuditService
from app.workers.runtime_adapter import RuntimeLaunchGateResult


@pytest.fixture()
def db_session(tmp_path):
    """Create an isolated SQLite database with current metadata."""

    db_path = tmp_path / "orchestrator-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def _persist_session(db_session):
    project = ProjectRepository(db_session).create(
        Project(name="P3-D3 runtime events", summary="Runtime gate event audit.")
    )
    task = TaskRepository(db_session).create(
        Task(
            project_id=project.id,
            title="Record runtime gate event",
            input_summary="simulate: gate event audit",
        )
    )
    run = RunRepository(db_session).create_running_run(task_id=task.id)
    session = AgentSessionRepository(db_session).create(
        project_id=project.id,
        task_id=task.id,
        run_id=run.id,
        status=AgentSessionStatus.RUNNING,
        review_status=AgentSessionReviewStatus.NONE,
        current_phase=AgentSessionPhase.EXECUTING,
        owner_role_code=None,
        context_checkpoint_id="checkpoint-1",
        context_rehydrated=False,
        summary="Runtime gate audit session.",
        agent_type=AgentType.OPENAI_PROVIDER,
        runtime_type=RuntimeType.SUBPROCESS,
        workspace_path="/tmp/aido-worktree",
    )
    return session


def test_runtime_event_audit_service_records_gate_evaluated_agent_message(db_session):
    session = _persist_session(db_session)
    repository = AgentMessageRepository(db_session)
    service = RuntimeEventAuditService(repository)
    gate = RuntimeLaunchGateResult(
        ready=True,
        gates_passed=[
            "workspace_validation",
            "workspace_context",
            "runtime_dry_run",
            "safe_command_proof",
            "adapter_capability",
        ],
    )

    message = service.record_launch_gate_event(
        session=session,
        gate_result=gate,
        adapter_kind="fake",
        workspace_path="/tmp/aido-worktree",
        observed_pwd="/tmp/aido-worktree",
        launch_cwd_preview="/tmp/aido-worktree",
    )

    payload = json.loads(message.content_detail or "{}")
    assert message.sequence_no == 1
    assert message.role == AgentMessageRole.SYSTEM
    assert message.message_type == AgentMessageType.TIMELINE
    assert message.event_type == "runtime_launch_gate_evaluated"
    assert message.note_event_type is None
    assert message.phase == "executing"
    assert message.state_from == "unknown"
    assert message.state_to == "unknown"
    assert payload["event_type"] == "runtime_launch_gate_evaluated"
    assert payload["event_type"] == message.event_type
    assert payload["reason_code"] == "launch_gate_evaluated"
    assert payload["created_by"] == "TaskWorker.run_once"
    assert payload["adapter_kind"] == "fake"
    assert payload["runtime_type"] == "subprocess"
    assert payload["agent_type"] == "openai_provider"
    assert payload["runtime_handle_id"] is None
    assert payload["evidence"]["pwd_matches_workspace_path"] is True
    assert payload["safety_flags"] == {
        "execution_enabled": False,
        "launches_ai_runtime": False,
        "runs_real_command": False,
        "runs_git": False,
        "runs_write_git": False,
        "changes_process_cwd": False,
        "fake_launch_started": False,
        "real_runtime_started": False,
        "runtime_probe_started": False,
    }

    messages = repository.list_by_session_id(session_id=session.id)
    assert [item.id for item in messages] == [message.id]


def test_runtime_event_audit_service_records_gate_blocked_agent_message(db_session):
    session = _persist_session(db_session)
    service = RuntimeEventAuditService(AgentMessageRepository(db_session))
    gate = RuntimeLaunchGateResult(
        ready=False,
        gates_passed=["workspace_validation", "workspace_context"],
        gates_failed=["runtime_dry_run"],
        blocking_reason_code="runtime_type_missing",
        blocking_summary="Runtime launch dry-run is not ready.",
    )

    message = service.record_launch_gate_event(
        session=session,
        gate_result=gate,
        adapter_kind="fake",
        workspace_path="/tmp/aido-worktree",
        observed_pwd="/tmp/aido-worktree",
        launch_cwd_preview=None,
    )

    payload = json.loads(message.content_detail or "{}")
    assert message.message_type == AgentMessageType.TIMELINE
    assert message.event_type == "runtime_launch_gate_blocked"
    assert message.note_event_type is None
    assert payload["event_type"] == "runtime_launch_gate_blocked"
    assert payload["event_type"] == message.event_type
    assert payload["reason_code"] == "runtime_type_missing"
    assert payload["created_by"] == "TaskWorker.run_once"
    assert payload["evidence"]["gates_failed"] == ["runtime_dry_run"]
    assert payload["evidence"]["blocking_summary"] == (
        "Runtime launch dry-run is not ready."
    )
    assert payload["safety_flags"]["fake_launch_started"] is False
    assert payload["safety_flags"]["real_runtime_started"] is False
    assert payload["safety_flags"]["runtime_probe_started"] is False


def test_p3d3_runtime_event_audit_still_only_records_gate_event_types():
    recorded_event_types = (
        RuntimeEventType.LAUNCH_GATE_EVALUATED,
        RuntimeEventType.LAUNCH_GATE_BLOCKED,
    )
    future_not_started = [
        event_type
        for event_type in RUNTIME_EVENT_TYPES
        if event_type not in recorded_event_types
    ]

    assert [event.value for event in recorded_event_types] == [
        "runtime_launch_gate_evaluated",
        "runtime_launch_gate_blocked",
    ]
    assert len(future_not_started) == 12
