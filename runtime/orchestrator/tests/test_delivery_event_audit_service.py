"""Targeted tests for P4-B3 delivery diff dry-run AgentMessage persistence."""

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
from app.domain.task import Task
from app.repositories.agent_message_repository import AgentMessageRepository
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.delivery_event_audit_service import DeliveryEventAuditService
from app.services.git_diff_dry_run_runner import GitDiffDryRunResult


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
        Project(name="P4-B3 delivery events", summary="Delivery diff event audit.")
    )
    task = TaskRepository(db_session).create(
        Task(
            project_id=project.id,
            title="Record delivery diff event",
            input_summary="simulate: delivery diff event audit",
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
        summary="Delivery diff audit session.",
        agent_type=AgentType.OPENAI_PROVIDER,
        runtime_type=RuntimeType.SUBPROCESS,
        workspace_path="/tmp/aido-worktree",
    )
    return session


def test_delivery_event_audit_service_records_collected_agent_message(db_session):
    session = _persist_session(db_session)
    repository = AgentMessageRepository(db_session)
    service = DeliveryEventAuditService(repository)
    result = GitDiffDryRunResult(
        ready=True,
        source="agent_session_worktree_diff",
        reason_code=None,
        worktree_path="/tmp/aido-worktree",
        has_changes=True,
        changed_files_count=1,
        changed_files=["README.md"],
        modified_files=["README.md"],
        status_summary_cn="1 个文件修改",
        branch_name="feature/p4-b3",
        compare_branch="main",
        command="git status --porcelain=v1 --untracked-files=all",
        peek_command="git diff --name-status",
        runs_git=True,
    )

    message = service.record_diff_dry_run_event(
        session=session,
        result=result,
    )

    payload = json.loads(message.content_detail or "{}")
    assert message.sequence_no == 1
    assert message.role == AgentMessageRole.SYSTEM
    assert message.message_type == AgentMessageType.TIMELINE
    assert message.event_type == "delivery_diff_dry_run_collected"
    assert message.note_event_type is None
    assert message.phase == "executing"
    assert message.state_from == "none"
    assert message.state_to == "diff_dirty"
    assert "尚未被提交或推送" in message.content_summary
    assert payload["event_type"] == message.event_type
    assert payload["created_by"] == "TaskWorker.run_once"
    assert payload["previous_delivery_state"] == "none"
    assert payload["next_delivery_state"] == "diff_dirty"
    assert payload["evidence"]["changed_files"] == ["README.md"]
    assert payload["evidence"]["status_summary_cn"] == "1 个文件修改"
    assert payload["safety_flags"] == {
        "runs_git": True,
        "runs_write_git": False,
        "git_add_triggered": False,
        "git_commit_triggered": False,
        "git_push_triggered": False,
        "pr_opened": False,
        "ci_triggered": False,
        "execution_enabled": False,
    }

    messages = repository.list_by_session_id(session_id=session.id)
    assert [item.id for item in messages] == [message.id]


def test_delivery_event_audit_service_records_skipped_and_failed_agent_messages(
    db_session,
):
    session = _persist_session(db_session)
    repository = AgentMessageRepository(db_session)
    service = DeliveryEventAuditService(repository)

    skipped = service.record_diff_dry_run_event(
        session=session,
        result=None,
        skipped_reason_code="worktree_path_unavailable",
        workspace_path=None,
    )
    failed = service.record_diff_dry_run_event(
        session=session,
        result=GitDiffDryRunResult(
            ready=False,
            source="agent_session_worktree_diff",
            reason_code="git_status_failed",
            worktree_path="/tmp/aido-worktree",
            has_changes=None,
            changed_files_count=None,
            command="git status --porcelain=v1 --untracked-files=all",
            runs_git=True,
        ),
    )

    skipped_payload = json.loads(skipped.content_detail or "{}")
    failed_payload = json.loads(failed.content_detail or "{}")
    assert skipped.sequence_no == 1
    assert failed.sequence_no == 2
    assert skipped.event_type == "delivery_diff_dry_run_skipped"
    assert skipped.state_to == "diff_skipped"
    assert skipped_payload["safety_flags"]["runs_git"] is False
    assert skipped_payload["safety_flags"]["runs_write_git"] is False
    assert failed.event_type == "delivery_diff_dry_run_failed"
    assert failed.state_to == "diff_failed"
    assert failed_payload["reason_code"] == "git_status_failed"
    assert failed_payload["safety_flags"]["runs_git"] is True
    assert failed_payload["safety_flags"]["runs_write_git"] is False
    assert failed_payload["safety_flags"]["git_add_triggered"] is False
    assert failed_payload["safety_flags"]["git_commit_triggered"] is False
    assert failed_payload["safety_flags"]["git_push_triggered"] is False
    assert failed_payload["safety_flags"]["pr_opened"] is False
    assert failed_payload["safety_flags"]["ci_triggered"] is False
    assert failed_payload["safety_flags"]["execution_enabled"] is False

    messages = repository.list_by_session_id(session_id=session.id)
    assert [item.event_type for item in messages] == [
        "delivery_diff_dry_run_skipped",
        "delivery_diff_dry_run_failed",
    ]
