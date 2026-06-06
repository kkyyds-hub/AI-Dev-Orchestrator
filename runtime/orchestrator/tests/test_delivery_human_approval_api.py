"""Targeted tests for the P4-F2-C delivery human approval API."""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.api.router import api_router
from app.api.routes.approvals import (
    DELIVERY_HUMAN_APPROVAL_API_ACTOR_DISPLAY_NAME,
    DELIVERY_HUMAN_APPROVAL_API_ACTOR_ID,
)
from app.core.config import settings
from app.core.db import get_db_session
from app.core.db_tables import (
    AgentMessageTable,
    ApprovalDecisionTable,
    ApprovalRequestTable,
    ORMBase,
)
from app.domain._base import utc_now
from app.domain.agent_session import (
    AgentSessionPhase,
    AgentSessionReviewStatus,
    AgentSessionStatus,
    WorkspaceType,
)
from app.domain.human_approval_gate import (
    HUMAN_APPROVAL_ACTION_APPROVE_GIT_ADD_COMMIT_PREVIEW,
    HUMAN_APPROVAL_SCOPE_GIT_ADD_COMMIT_PREVIEW,
)
from app.domain.project import Project
from app.domain.project_role import ProjectRoleCode
from app.domain.task import Task, TaskPriority, TaskRiskLevel
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.run_logging_service import (
    DELIVERY_EVIDENCE_SNAPSHOT_EVENT,
    DELIVERY_EVIDENCE_SNAPSHOT_MESSAGE,
    DELIVERY_EVIDENCE_SNAPSHOT_SOURCE_RUN_LOG_JSONL,
    DELIVERY_EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
    RunLoggingService,
)


@pytest.fixture()
def sqlite_session_factory(tmp_path):
    db_path = tmp_path / "orchestrator-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


@pytest.fixture()
def client(sqlite_session_factory, tmp_path):
    app = FastAPI()
    app.include_router(api_router)
    original_runtime_data_dir = settings.runtime_data_dir
    object.__setattr__(settings, "runtime_data_dir", tmp_path / "runtime-data")

    def override_get_db_session():
        session = sqlite_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    object.__setattr__(settings, "runtime_data_dir", original_runtime_data_dir)


@pytest.fixture()
def db_session(sqlite_session_factory):
    session = sqlite_session_factory()
    try:
        yield session
    finally:
        session.close()


def _count_rows(db_session, table) -> int:
    return int(db_session.execute(select(func.count()).select_from(table)).scalar_one())


def _seed_run_with_session(
    db_session,
    *,
    log_path: str | None = None,
    create_agent_session: bool = True,
):
    project = ProjectRepository(db_session).create(
        Project(
            name="P4-F2-C approval api project",
            summary="Verify minimal delivery human approval API.",
        )
    )
    task = TaskRepository(db_session).create(
        Task(
            project_id=project.id,
            title="Prepare delivery approval evidence",
            input_summary="Create read-only evidence before human approval.",
            priority=TaskPriority.HIGH,
            risk_level=TaskRiskLevel.NORMAL,
        )
    )
    run_repository = RunRepository(db_session)
    run = run_repository.create_running_run(
        task_id=task.id,
        owner_role_code=ProjectRoleCode.ENGINEER,
    )
    if log_path is not None:
        run = run_repository.set_log_path(run.id, log_path)
    agent_session = None
    if create_agent_session:
        agent_session = AgentSessionRepository(db_session).create(
            project_id=project.id,
            task_id=task.id,
            run_id=run.id,
            status=AgentSessionStatus.RUNNING,
            review_status=AgentSessionReviewStatus.NONE,
            current_phase=AgentSessionPhase.EXECUTING,
            owner_role_code=ProjectRoleCode.ENGINEER,
            context_checkpoint_id=None,
            context_rehydrated=False,
            summary="Session used by P4-F2-C approval API tests.",
            workspace_type=WorkspaceType.WORKTREE,
            workspace_path="/tmp/p4f2c-approval-api",
            workspace_clean=True,
        )
    db_session.commit()
    return project, task, run, agent_session


def _write_delivery_evidence_snapshot(*, task_id, run_id) -> str:
    service = RunLoggingService()
    log_path = service.initialize_run_log(task_id=task_id, run_id=run_id)
    service.append_delivery_evidence_snapshot(
        log_path=log_path,
        run_id=run_id,
        operation_dry_run={
            "ready": True,
            "source": "git_operation_dry_run",
            "proposed_operation": "git_add_commit",
            "proposed_commit_message": "fix: stabilize delivery evidence",
            "changed_files_count": 1,
            "changed_files": ["runtime/orchestrator/app/api/routes/approvals.py"],
            "safety_flags": {
                "runs_git": False,
                "runs_write_git": False,
                "git_add_triggered": False,
                "git_commit_triggered": False,
                "git_push_triggered": False,
                "pr_opened": False,
                "ci_triggered": False,
                "execution_enabled": False,
                "operation_applied": False,
                "approval_granted": False,
            },
        },
        delivery_gate_evidence={
            "ready": True,
            "source": "delivery_gate_evidence",
            "changed_files_count": 1,
            "changed_files": ["runtime/orchestrator/app/api/routes/approvals.py"],
            "safety_flags": {
                "runs_git": False,
                "runs_write_git": False,
                "git_add_triggered": False,
                "git_commit_triggered": False,
                "git_push_triggered": False,
                "pr_opened": False,
                "ci_triggered": False,
                "execution_enabled": False,
                "operation_applied": False,
                "approval_granted": False,
                "gate_allows_user_confirmation": True,
                "gate_allows_write": False,
            },
        },
    )
    return log_path


def _approval_request_payload(run_id, **overrides) -> dict:
    payload = {
        "run_id": str(run_id),
        "approval_requested_action": HUMAN_APPROVAL_ACTION_APPROVE_GIT_ADD_COMMIT_PREVIEW,
        "approval_scope": HUMAN_APPROVAL_SCOPE_GIT_ADD_COMMIT_PREVIEW,
        "approval_confirmation_text": "确认提交预览：允许进入下一阶段安全检查。",
        "approval_client_request_id": "client-request-1",
        "approval_expires_at": (utc_now() + timedelta(hours=1)).isoformat(),
        "expected_changed_files": [
            "runtime/orchestrator/app/api/routes/approvals.py"
        ],
        "expected_proposed_commit_message": "fix: stabilize delivery evidence",
    }
    payload.update(overrides)
    return payload


def test_delivery_human_approval_api_actor_seam_constants_are_local_user():
    assert DELIVERY_HUMAN_APPROVAL_API_ACTOR_ID == "local_user"
    assert DELIVERY_HUMAN_APPROVAL_API_ACTOR_DISPLAY_NAME == "本地用户"


def test_delivery_human_approval_api_evaluates_snapshot_without_persisting_confirmation(
    client,
    db_session,
):
    _, task, run, agent_session = _seed_run_with_session(db_session)
    log_path = _write_delivery_evidence_snapshot(task_id=task.id, run_id=run.id)
    RunRepository(db_session).set_log_path(run.id, log_path)
    db_session.commit()

    confirmation_text = "确认提交预览：允许进入下一阶段安全检查。"
    response = client.post(
        "/approvals/delivery-human-approval",
        json=_approval_request_payload(
            run.id,
            approval_confirmation_text=confirmation_text,
            approval_actor_id="untrusted-request-actor",
            approval_actor_display_name="Untrusted Request Actor",
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["reason_code"] is None
    assert payload["source"] == "delivery_human_approval"
    assert payload["run_id"] == str(run.id)
    assert payload["task_id"] == str(task.id)
    assert payload["project_id"] == str(agent_session.project_id)
    assert payload["session_id"] == str(agent_session.id)
    assert payload["approval_granted"] is True
    assert payload["approval_required"] is True
    assert payload["approval_requested_action"] == HUMAN_APPROVAL_ACTION_APPROVE_GIT_ADD_COMMIT_PREVIEW
    assert payload["approval_scope"] == HUMAN_APPROVAL_SCOPE_GIT_ADD_COMMIT_PREVIEW
    assert payload["approved_by"] == DELIVERY_HUMAN_APPROVAL_API_ACTOR_ID
    assert (
        payload["approved_by_display_name"]
        == DELIVERY_HUMAN_APPROVAL_API_ACTOR_DISPLAY_NAME
    )
    assert payload["approval_client_request_id"] == "client-request-1"
    assert payload["approval_confirmation_fingerprint"]
    assert confirmation_text not in response.text
    assert "untrusted-request-actor" not in response.text
    assert "Untrusted Request Actor" not in response.text
    assert payload["operation_dry_run_ready"] is True
    assert payload["delivery_gate_evidence_ready"] is True
    assert payload["delivery_gate_allows_user_confirmation"] is True
    assert payload["delivery_gate_allows_write"] is False
    assert payload["proposed_operation"] == "git_add_commit"
    assert payload["proposed_commit_message"] == "fix: stabilize delivery evidence"
    assert payload["changed_files"] == [
        "runtime/orchestrator/app/api/routes/approvals.py"
    ]
    assert payload["safety_flags"]["gate_allows_write"] is False
    assert payload["safety_flags"]["gate_allows_next_guardrail"] is True
    assert payload["safety_flags"]["git_add_triggered"] is False
    assert payload["safety_flags"]["git_commit_triggered"] is False
    assert payload["safety_flags"]["git_push_triggered"] is False
    assert payload["evidence_snapshot_event"] == DELIVERY_EVIDENCE_SNAPSHOT_EVENT
    assert payload["evidence_snapshot_log_path"] == log_path
    assert payload["evidence_snapshot_schema_version"] == DELIVERY_EVIDENCE_SNAPSHOT_SCHEMA_VERSION
    assert payload["evidence_snapshot_source"] == DELIVERY_EVIDENCE_SNAPSHOT_SOURCE_RUN_LOG_JSONL

    assert _count_rows(db_session, ApprovalRequestTable) == 0
    assert _count_rows(db_session, ApprovalDecisionTable) == 0
    assert _count_rows(db_session, AgentMessageTable) == 0


def test_delivery_human_approval_api_blocks_when_snapshot_missing(
    client,
    db_session,
):
    _, _, run, _ = _seed_run_with_session(
        db_session,
        log_path="logs/task-runs/missing/missing.jsonl",
    )

    response = client.post(
        "/approvals/delivery-human-approval",
        json=_approval_request_payload(
            run.id,
            approval_confirmation_text="确认提交预览",
            approval_client_request_id="client-request-missing-snapshot",
            expected_changed_files=["README.md"],
            expected_proposed_commit_message="fix: missing snapshot",
        ),
    )

    assert response.status_code == 409
    assert "Delivery evidence snapshot not found" in response.json()["detail"]
    assert _count_rows(db_session, ApprovalRequestTable) == 0
    assert _count_rows(db_session, ApprovalDecisionTable) == 0
    assert _count_rows(db_session, AgentMessageTable) == 0


def test_delivery_human_approval_api_rejects_invalid_snapshot_contract(
    client,
    db_session,
):
    _, task, run, _ = _seed_run_with_session(db_session)
    service = RunLoggingService()
    log_path = service.initialize_run_log(task_id=task.id, run_id=run.id)
    service.append_event(
        log_path=log_path,
        event=DELIVERY_EVIDENCE_SNAPSHOT_EVENT,
        message=DELIVERY_EVIDENCE_SNAPSHOT_MESSAGE,
        data={
            "schema_version": "invalid.v1",
            "snapshot_source": DELIVERY_EVIDENCE_SNAPSHOT_SOURCE_RUN_LOG_JSONL,
            "operation_dry_run_available": True,
            "delivery_gate_evidence_available": True,
            "operation_dry_run": {},
            "delivery_gate_evidence": {},
        },
    )
    RunRepository(db_session).set_log_path(run.id, log_path)
    db_session.commit()

    response = client.post(
        "/approvals/delivery-human-approval",
        json=_approval_request_payload(run.id),
    )

    assert response.status_code == 409
    assert "schema_version_mismatch" in response.json()["detail"]
    assert _count_rows(db_session, ApprovalRequestTable) == 0
    assert _count_rows(db_session, ApprovalDecisionTable) == 0
    assert _count_rows(db_session, AgentMessageTable) == 0


def test_delivery_human_approval_api_returns_blocked_when_agent_session_missing(
    client,
    db_session,
):
    _, task, run, _ = _seed_run_with_session(
        db_session,
        create_agent_session=False,
    )
    log_path = _write_delivery_evidence_snapshot(task_id=task.id, run_id=run.id)
    RunRepository(db_session).set_log_path(run.id, log_path)
    db_session.commit()

    response = client.post(
        "/approvals/delivery-human-approval",
        json=_approval_request_payload(
            run.id,
            approval_client_request_id="client-request-missing-session",
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert payload["reason_code"] == "agent_session_missing"
    assert payload["session_id"] == "missing"
    assert payload["approval_granted"] is False
    assert payload["safety_flags"]["gate_allows_next_guardrail"] is False
    assert "H1:agent_session_missing" in payload["blocking_reasons"]
    assert _count_rows(db_session, ApprovalRequestTable) == 0
    assert _count_rows(db_session, ApprovalDecisionTable) == 0
    assert _count_rows(db_session, AgentMessageTable) == 0


def test_delivery_human_approval_api_returns_blocked_on_changed_files_mismatch(
    client,
    db_session,
):
    _, task, run, _ = _seed_run_with_session(db_session)
    log_path = _write_delivery_evidence_snapshot(task_id=task.id, run_id=run.id)
    RunRepository(db_session).set_log_path(run.id, log_path)
    db_session.commit()

    response = client.post(
        "/approvals/delivery-human-approval",
        json=_approval_request_payload(
            run.id,
            approval_client_request_id="client-request-files-mismatch",
            expected_changed_files=["README.md"],
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert payload["reason_code"] == "changed_files_mismatch"
    assert payload["approval_granted"] is False
    assert payload["approved_by"] == DELIVERY_HUMAN_APPROVAL_API_ACTOR_ID
    assert "H20:changed_files_mismatch" in payload["blocking_reasons"]
    assert payload["safety_flags"]["gate_allows_next_guardrail"] is False


def test_delivery_human_approval_api_returns_blocked_on_commit_message_mismatch(
    client,
    db_session,
):
    _, task, run, _ = _seed_run_with_session(db_session)
    log_path = _write_delivery_evidence_snapshot(task_id=task.id, run_id=run.id)
    RunRepository(db_session).set_log_path(run.id, log_path)
    db_session.commit()

    response = client.post(
        "/approvals/delivery-human-approval",
        json=_approval_request_payload(
            run.id,
            approval_client_request_id="client-request-commit-message-mismatch",
            expected_proposed_commit_message="fix: different message",
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert payload["reason_code"] == "commit_message_mismatch"
    assert payload["approval_granted"] is False
    assert payload["approved_by"] == DELIVERY_HUMAN_APPROVAL_API_ACTOR_ID
    assert "H21:commit_message_mismatch" in payload["blocking_reasons"]
    assert payload["safety_flags"]["gate_allows_next_guardrail"] is False
