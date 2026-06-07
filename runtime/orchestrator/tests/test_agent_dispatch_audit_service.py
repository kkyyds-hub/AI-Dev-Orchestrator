"""Targeted tests for P6-D agent dispatch AgentMessage persistence."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db_tables import ORMBase
from app.domain.agent_dispatch_decision import (
    P6_AGENT_DISPATCH_DECISION_AUDIT_EVENT_TYPE,
    AgentDispatchDecisionBuilder,
)
from app.domain.agent_message import AgentMessageRole, AgentMessageType
from app.domain.agent_session import (
    AgentSessionPhase,
    AgentSessionReviewStatus,
    AgentSessionStatus,
    AgentType,
    RuntimeType,
)
from app.domain.failure_recovery_decision import FailureRecoveryDecisionBuilder
from app.domain.project import Project
from app.domain.run import RunFailureCategory, RunStatus
from app.domain.task import Task, TaskStatus
from app.repositories.agent_message_repository import AgentMessageRepository
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.agent_dispatch_audit_service import AgentDispatchAuditService


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
        Project(name="P6-D dispatch events", summary="Dispatch event audit.")
    )
    task = TaskRepository(db_session).create(
        Task(
            project_id=project.id,
            title="Record dispatch event",
            input_summary="simulate: dispatch event audit",
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
        context_checkpoint_id="checkpoint-p6",
        context_rehydrated=True,
        summary="Dispatch audit session.",
        agent_type=AgentType.OPENAI_PROVIDER,
        runtime_type=RuntimeType.SUBPROCESS,
        workspace_path="/tmp/aido-worktree",
    )
    return session


def test_agent_dispatch_audit_service_records_dispatch_timeline_message(db_session):
    session = _persist_session(db_session)
    repository = AgentMessageRepository(db_session)
    service = AgentDispatchAuditService(repository)
    recovery_decision = FailureRecoveryDecisionBuilder.build(
        failure_category=RunFailureCategory.EXECUTION_FAILED,
    )
    dispatch_decision = AgentDispatchDecisionBuilder.build_from_failure_recovery_decision(
        failure_recovery_decision=recovery_decision,
        source_failure_recovery_decision_id="p5-decision-1",
        source_run_id=session.run_id,
        source_task_id=session.task_id,
        created_by="p6-d-test",
    )

    message = service.record_decision(
        session=session,
        decision=dispatch_decision,
        run_status=RunStatus.CANCELLED,
        task_status=TaskStatus.BLOCKED,
        result_summary="Worker failed and dispatch was suggested.",
    )
    duplicate_message = service.record_decision(
        session=session,
        decision=dispatch_decision,
        run_status=RunStatus.CANCELLED,
        task_status=TaskStatus.BLOCKED,
        result_summary="Worker failed and dispatch was suggested.",
    )

    messages = repository.list_by_session_id(session_id=session.id)
    payload = json.loads(message.content_detail or "{}")

    assert duplicate_message.id == message.id
    assert [item.id for item in messages] == [message.id]
    assert message.sequence_no == 1
    assert message.role == AgentMessageRole.SYSTEM
    assert message.message_type == AgentMessageType.TIMELINE
    assert message.event_type == P6_AGENT_DISPATCH_DECISION_AUDIT_EVENT_TYPE
    assert message.note_event_type is None
    assert message.phase == "executing"
    assert message.state_from == "cancelled"
    assert message.state_to == "suggested"
    assert "P6 调度建议" in message.content_summary
    assert "Codex 继续处理" in message.content_summary
    assert "不会自动派发、重试或创建任务" in message.content_summary
    assert "p5_owner_codex" not in message.content_summary
    assert "suggested" not in message.content_summary
    assert payload["p6_stage"] == "P6-D"
    assert payload["event_type"] == P6_AGENT_DISPATCH_DECISION_AUDIT_EVENT_TYPE
    assert payload["run_status"] == "cancelled"
    assert payload["task_status"] == "blocked"
    assert payload["result_summary"] == "Worker failed and dispatch was suggested."
    assert payload["decision"]["audit_event_type"] == (
        P6_AGENT_DISPATCH_DECISION_AUDIT_EVENT_TYPE
    )
    assert payload["decision"]["recommended_agent"] == "codex"
    assert payload["decision"]["dispatch_status"] == "suggested"
    assert payload["decision"]["dispatch_reason_code"] == "p5_owner_codex"
    assert payload["decision"]["safety_flags"]["agent_message_written"] is False
    assert payload["decision"]["safety_flags"]["worker_dispatch_triggered"] is False
    assert payload["decision"]["safety_flags"]["retry_triggered"] is False
    assert payload["decision"]["safety_flags"]["auto_dispatch_triggered"] is False
    assert payload["p6_d_audit"]["agent_message_recorded"] is True
    assert payload["p6_d_audit"]["api_response_exposed"] is False
    assert payload["p6_d_audit"]["retry_triggered"] is False
    assert payload["p6_d_audit"]["worker_dispatch_triggered"] is False
    assert payload["p6_d_audit"]["task_created"] is False
    assert payload["p6_d_audit"]["auto_dispatch_triggered"] is False
    assert payload["p6_d_audit"]["runs_git"] is False
    assert payload["p6_d_audit"]["runs_write_git"] is False
    assert payload["p6_d_audit"]["git_add_triggered"] is False
    assert payload["p6_d_audit"]["git_commit_triggered"] is False
    assert payload["p6_d_audit"]["git_push_triggered"] is False
    assert payload["p6_d_audit"]["pr_opened"] is False
    assert payload["p6_d_audit"]["merge_triggered"] is False
    assert payload["p6_d_audit"]["ci_triggered"] is False
    assert payload["p6_d_audit"]["execution_enabled"] is False


def test_agent_dispatch_audit_service_records_user_decision_without_draft(db_session):
    session = _persist_session(db_session)
    service = AgentDispatchAuditService(AgentMessageRepository(db_session))
    recovery_decision = FailureRecoveryDecisionBuilder.build(
        failure_category=RunFailureCategory.RETRY_LIMIT_EXCEEDED,
    )
    dispatch_decision = AgentDispatchDecisionBuilder.build_from_failure_recovery_decision(
        failure_recovery_decision=recovery_decision,
        source_run_id=session.run_id,
        source_task_id=session.task_id,
    )

    message = service.record_decision(
        session=session,
        decision=dispatch_decision,
        run_status=RunStatus.FAILED,
        task_status=TaskStatus.FAILED,
        result_summary=None,
    )

    payload = json.loads(message.content_detail or "{}")
    assert message.state_to == "needs_user_decision"
    assert "等待用户决策" in message.content_summary
    assert "当前不生成可执行指令草案" in message.content_summary
    assert payload["decision"]["recommended_agent"] == "user"
    assert payload["decision"]["dispatch_status"] == "needs_user_decision"
    assert payload["decision"]["instruction_draft"] is None
    assert payload["p6_d_audit"]["worker_dispatch_triggered"] is False
