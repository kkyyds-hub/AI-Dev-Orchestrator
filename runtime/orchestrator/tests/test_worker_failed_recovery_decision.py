"""Targeted P5-C tests for failed worker run recovery decisions."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.db_tables import ORMBase
from app.domain.failure_recovery_decision import (
    P5_FAILURE_RECOVERY_DECISION_AUDIT_EVENT_TYPE,
    P5_FAILURE_RECOVERY_DECISION_SOURCE,
    P5_FAILURE_RECOVERY_DECISION_VERSION,
)
from app.domain.run import Run, RunFailureCategory, RunStatus
from app.domain.task import Task, TaskStatus
from app.repositories.failure_review_repository import FailureReviewRepository
from app.repositories.task_repository import TaskRepository
from app.services.failure_review_service import (
    P5C_FAILURE_RECOVERY_DECISION_PAYLOAD_KEY,
    FailureReviewService,
)
from app.services.run_logging_service import RunLoggingService
from app.workers.task_worker import build_task_worker


def _assert_p5c_internal_decision_payload(payload: dict) -> dict:
    decision = payload[P5C_FAILURE_RECOVERY_DECISION_PAYLOAD_KEY]

    assert decision["source"] == P5_FAILURE_RECOVERY_DECISION_SOURCE
    assert decision["version"] == P5_FAILURE_RECOVERY_DECISION_VERSION
    assert decision["audit_event_type"] == (
        P5_FAILURE_RECOVERY_DECISION_AUDIT_EVENT_TYPE
    )
    assert decision["failure_category"] == "execution_failed"
    assert decision["recoverable"] is True
    assert decision["retry_allowed"] is True
    assert decision["recommended_owner"] == "codex"
    assert decision["next_action"] == "fix_and_retry"
    assert decision["next_instruction_kind"] == "code_fix"
    assert decision["next_instruction_draft_required"] is True
    assert decision["next_instruction_draft"]
    assert decision["requires_human_decision"] is False
    assert decision["human_decision_reason"] is None
    assert decision["rule_codes"] == ["failure_execution_codex_fix_and_retry"]
    assert all(flag_value is False for flag_value in decision["safety_flags"].values())

    return decision


def test_failure_review_persists_internal_recovery_decision_payload(tmp_path):
    original_runtime_data_dir = settings.runtime_data_dir
    object.__setattr__(settings, "runtime_data_dir", tmp_path)
    try:
        task = Task(
            title="P5-C failed run",
            input_summary="simulate: failed worker recovery decision",
            status=TaskStatus.FAILED,
        )
        run = Run(
            task_id=task.id,
            status=RunStatus.FAILED,
            result_summary="Execution failed during worker run.",
            failure_category=RunFailureCategory.EXECUTION_FAILED,
            quality_gate_passed=False,
        )
        repository = FailureReviewRepository()
        service = FailureReviewService(
            failure_review_repository=repository,
            run_logging_service=RunLoggingService(),
        )

        review = service.ensure_review(task=task, run=run)
        payload = repository.get(run_id=run.id)
        api_facing_review = service.get_review(run_id=run.id)
    finally:
        object.__setattr__(settings, "runtime_data_dir", original_runtime_data_dir)

    assert review is not None
    assert payload is not None
    decision = _assert_p5c_internal_decision_payload(payload)
    assert api_facing_review is not None
    assert not hasattr(api_facing_review, P5C_FAILURE_RECOVERY_DECISION_PAYLOAD_KEY)
    assert "api_response_exposed" in decision["safety_flags"]
    assert decision["safety_flags"]["api_response_exposed"] is False
    assert decision["safety_flags"]["agent_message_written"] is False
    assert decision["safety_flags"]["retry_triggered"] is False


def test_worker_failed_run_generates_internal_recovery_decision_payload(tmp_path):
    original_runtime_data_dir = settings.runtime_data_dir
    original_simulate_override = settings.worker_simulate_execution_override
    original_simulate_failure_mode = settings.worker_simulate_failure_mode
    original_daily_budget = settings.daily_budget_usd
    original_session_budget = settings.session_budget_usd
    original_max_task_retries = settings.max_task_retries

    object.__setattr__(settings, "runtime_data_dir", tmp_path / "runtime-data")
    object.__setattr__(settings, "worker_simulate_execution_override", True)
    object.__setattr__(settings, "worker_simulate_failure_mode", "failed")
    object.__setattr__(settings, "daily_budget_usd", 100.0)
    object.__setattr__(settings, "session_budget_usd", 100.0)
    object.__setattr__(settings, "max_task_retries", 3)

    db_path = tmp_path / "orchestrator-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    session = session_factory()
    try:
        task = TaskRepository(session).create(
            Task(
                title="P5-C worker failed run",
                input_summary="created through API only",
            )
        )
        worker = build_task_worker(session=session)

        result = worker.run_once()
        run_id = result.run.id if result.run is not None else None
        assert isinstance(run_id, UUID)

        payload = FailureReviewRepository().get(run_id=run_id)
        persisted_task = TaskRepository(session).get_by_id(task.id)
    finally:
        session.close()
        object.__setattr__(settings, "runtime_data_dir", original_runtime_data_dir)
        object.__setattr__(
            settings,
            "worker_simulate_execution_override",
            original_simulate_override,
        )
        object.__setattr__(
            settings,
            "worker_simulate_failure_mode",
            original_simulate_failure_mode,
        )
        object.__setattr__(settings, "daily_budget_usd", original_daily_budget)
        object.__setattr__(settings, "session_budget_usd", original_session_budget)
        object.__setattr__(settings, "max_task_retries", original_max_task_retries)

    assert result.claimed is True
    assert result.run is not None
    assert result.run.status == RunStatus.FAILED
    assert result.failure_category == RunFailureCategory.EXECUTION_FAILED
    assert result.quality_gate_passed is False
    assert result.message.startswith("Worker execution failed via simulate.")
    assert persisted_task is not None
    assert persisted_task.status == TaskStatus.FAILED
    assert payload is not None
    _assert_p5c_internal_decision_payload(payload)
