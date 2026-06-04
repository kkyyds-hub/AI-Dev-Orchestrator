"""P0 coding-session field coverage for AgentSession.

These tests stay at repository/service/DTO level. They do not start services,
run worker instances, or touch a real repository.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.api.routes.agent_threads import AgentSessionResponse
from app.api.routes.workers import WorkerRunOnceResponse
from app.core.db_tables import ORMBase
from app.domain.agent_session import (
    AgentSessionPhase,
    AgentSessionReviewStatus,
    AgentSessionStatus,
    AgentType,
    CodingSessionActivityState,
    CodingSessionStatus,
    RuntimeType,
)
from app.domain.project import Project
from app.domain.run import RunStatus
from app.domain.task import Task
from app.repositories.agent_message_repository import AgentMessageRepository
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.agent_conversation_service import AgentConversationService
from app.services.context_builder_service import AgentThreadContextSeed
from app.workers.task_worker import WorkerRunResult


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


def test_agent_sessions_table_contains_p0_coding_columns(db_session):
    """AgentSession keeps P0 observability in the existing table."""

    columns = {
        column["name"]
        for column in inspect(db_session.bind).get_columns("agent_sessions")
    }

    assert {
        "agent_type",
        "runtime_type",
        "runtime_handle_id",
        "coding_status",
        "activity_state",
        "branch_name",
    }.issubset(columns)


def test_agent_session_repository_round_trips_p0_coding_fields(db_session):
    """Repository create/read/update preserves P0 coding fields."""

    repository = AgentSessionRepository(db_session)
    session = repository.create(
        project_id=uuid4(),
        task_id=uuid4(),
        run_id=uuid4(),
        status=AgentSessionStatus.RUNNING,
        review_status=AgentSessionReviewStatus.NONE,
        current_phase=AgentSessionPhase.CONTEXT_READY,
        owner_role_code=None,
        context_checkpoint_id=None,
        context_rehydrated=False,
        summary="Started",
        agent_type=AgentType.OPENAI_PROVIDER,
        runtime_type=RuntimeType.SUBPROCESS,
        runtime_handle_id=" subprocess:local ",
        coding_status=CodingSessionStatus.WORKING,
        activity_state=CodingSessionActivityState.ACTIVE,
        branch_name=" main ",
    )

    assert session.agent_type == AgentType.OPENAI_PROVIDER
    assert session.runtime_type == RuntimeType.SUBPROCESS
    assert session.runtime_handle_id == "subprocess:local"
    assert session.coding_status == CodingSessionStatus.WORKING
    assert session.activity_state == CodingSessionActivityState.ACTIVE
    assert session.branch_name == "main"

    updated = repository.update_status(
        session.id,
        coding_status=CodingSessionStatus.COMPLETED,
        activity_state=CodingSessionActivityState.EXITED,
        branch_name="",
        finished=True,
    )

    assert updated.coding_status == CodingSessionStatus.COMPLETED
    assert updated.activity_state == CodingSessionActivityState.EXITED
    assert updated.branch_name is None
    assert updated.finished_at is not None


def test_agent_conversation_service_fills_p0_defaults_and_final_state(db_session):
    """TaskWorker's service path gets the P0 default fill logic."""

    project = ProjectRepository(db_session).create(
        Project(name="P0 coding fields", summary="Project for session defaults.")
    )
    task = TaskRepository(db_session).create(
        Task(
            project_id=project.id,
            title="P0 session task",
            input_summary="simulate: validate agent session P0 observability",
        )
    )
    run = RunRepository(db_session).create_running_run(task_id=task.id)

    service = AgentConversationService(
        agent_session_repository=AgentSessionRepository(db_session),
        agent_message_repository=AgentMessageRepository(db_session),
    )

    session = service.start_session(
        project_id=project.id,
        task_id=task.id,
        run_id=run.id,
        owner_role_code=None,
        context_seed=AgentThreadContextSeed(
            task_id=task.id,
            context_checkpoint_id=None,
            context_rehydrated=False,
            pressure_level=None,
            usage_ratio=None,
            bad_context_detected=False,
            bad_context_reasons=[],
            context_contract_summary="No checkpoint.",
        ),
    )

    assert session.agent_type == AgentType.OPENAI_PROVIDER
    assert session.runtime_type == RuntimeType.SUBPROCESS
    assert session.runtime_handle_id is None
    assert session.coding_status == CodingSessionStatus.WORKING
    assert session.activity_state == CodingSessionActivityState.ACTIVE
    assert session.branch_name is None

    finalized = service.finalize_session(
        session_id=session.id,
        run_status=RunStatus.SUCCEEDED,
        run_failure_category=None,
        final_summary="Done",
    )

    assert finalized.coding_status == CodingSessionStatus.COMPLETED
    assert finalized.activity_state == CodingSessionActivityState.EXITED


def test_agent_session_response_exposes_p0_coding_fields(db_session):
    """Existing agent-thread response exposes P0 fields without new routes."""

    session = AgentSessionRepository(db_session).create(
        project_id=uuid4(),
        task_id=uuid4(),
        run_id=uuid4(),
        status=AgentSessionStatus.RUNNING,
        review_status=AgentSessionReviewStatus.NONE,
        current_phase=AgentSessionPhase.EXECUTING,
        owner_role_code=None,
        context_checkpoint_id=None,
        context_rehydrated=False,
        summary="Executing",
        agent_type=AgentType.OPENAI_PROVIDER,
        runtime_type=RuntimeType.SUBPROCESS,
        coding_status=CodingSessionStatus.WORKING,
        activity_state=CodingSessionActivityState.ACTIVE,
    )

    payload = AgentSessionResponse.from_session(session).model_dump(mode="json")

    assert payload["agent_type"] == "openai_provider"
    assert payload["runtime_type"] == "subprocess"
    assert payload["runtime_handle_id"] is None
    assert payload["coding_status"] == "working"
    assert payload["activity_state"] == "active"
    assert payload["branch_name"] is None


def test_worker_run_once_response_exposes_p0_coding_fields_without_running_worker():
    """Existing worker response DTO can expose P0 fields without invoking a worker."""

    payload = WorkerRunOnceResponse.from_result(
        WorkerRunResult(
            claimed=True,
            message="DTO only",
            agent_type="openai_provider",
            runtime_type="subprocess",
            runtime_handle_id=None,
            coding_status="completed",
            activity_state="exited",
            branch_name=None,
        )
    ).model_dump(mode="json")

    assert payload["agent_type"] == "openai_provider"
    assert payload["runtime_type"] == "subprocess"
    assert payload["runtime_handle_id"] is None
    assert payload["coding_status"] == "completed"
    assert payload["activity_state"] == "exited"
    assert payload["branch_name"] is None
