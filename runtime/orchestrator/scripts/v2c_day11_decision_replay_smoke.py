"""Smoke test for V2-C Day11 decision replay and review cluster endpoints."""

from __future__ import annotations

from pathlib import Path
import json
import os
import shutil


runtime_root = Path(__file__).resolve().parents[1] / "tmp" / "day11_smoke_runtime"
if runtime_root.exists():
    shutil.rmtree(runtime_root)

os.environ["RUNTIME_DATA_DIR"] = str(runtime_root)
os.environ["SQLITE_DB_DIR"] = str(runtime_root / "db")
os.environ["SQLITE_DB_PATH"] = str(runtime_root / "db" / "day11_smoke.db")

from fastapi.testclient import TestClient

from app.core.db import SessionLocal, init_database
from app.domain.run import RunFailureCategory, RunStatus
from app.domain.task import Task, TaskStatus
from app.main import app
from app.repositories.failure_review_repository import FailureReviewRepository
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.failure_review_service import FailureReviewService
from app.services.run_logging_service import RunLoggingService


def main() -> None:
    """Seed one failed run and verify the Day11 APIs return replay-ready payloads."""

    init_database()

    session = SessionLocal()
    task_repository = TaskRepository(session)
    run_repository = RunRepository(session)
    run_logging_service = RunLoggingService()
    failure_review_service = FailureReviewService(
        failure_review_repository=FailureReviewRepository(),
        run_logging_service=run_logging_service,
    )

    task = task_repository.create(
        Task(
            title="day11 smoke task",
            input_summary="Verify Day11 replay and clustering endpoints.",
            acceptance_criteria=[
                "decision trace endpoint works",
                "decision history endpoint works",
            ],
        )
    )
    run = run_repository.create_running_run(
        task_id=task.id,
        route_reason="readiness=yes; verification=enabled; total=120.0",
        routing_score=120.0,
    )
    log_path = run_logging_service.initialize_run_log(task_id=task.id, run_id=run.id)
    run = run_repository.set_log_path(run.id, log_path)

    run_logging_service.append_event(
        log_path=log_path,
        event="task_routed",
        message="Router selected the smoke task.",
        data={"routing_score": 120.0, "route_reason": run.route_reason},
    )
    run_logging_service.append_event(
        log_path=log_path,
        event="run_claimed",
        message="Worker claimed the smoke task.",
        data={"task_id": str(task.id), "run_id": str(run.id)},
    )
    run_logging_service.append_event(
        log_path=log_path,
        event="execution_finished",
        message="Execution finished but produced a failing verification result.",
        data={"result_summary": "Execution finished with output requiring verification."},
    )
    run_logging_service.append_event(
        log_path=log_path,
        event="verification_finished",
        level="warning",
        message="Verification failed for the smoke task.",
        data={"quality_gate_passed": False, "failure_category": "verification_failed"},
    )

    run = run_repository.finish_run(
        run.id,
        status=RunStatus.FAILED,
        result_summary="Verification failed for the smoke task.",
        verification_mode="command",
        verification_template="smoke",
        verification_summary="Smoke verification failed.",
        failure_category=RunFailureCategory.VERIFICATION_FAILED,
        quality_gate_passed=False,
    )
    task = task_repository.set_status(task.id, TaskStatus.FAILED)
    run_logging_service.append_event(
        log_path=log_path,
        event="run_finalized",
        message="Task and run were finalized for the smoke task.",
        data={
            "task_status": task.status.value,
            "run_status": run.status.value,
            "failure_category": run.failure_category.value,
        },
    )
    session.commit()

    review = failure_review_service.ensure_review(task=task, run=run)
    session.commit()
    session.close()

    with TestClient(app) as client:
        trace_response = client.get(f"/runs/{run.id}/decision-trace")
        history_response = client.get(f"/tasks/{task.id}/decision-history")
        clusters_response = client.get("/console/review-clusters")

    report = {
        "run_id": str(run.id),
        "task_id": str(task.id),
        "decision_trace_status": trace_response.status_code,
        "decision_trace_items": len(trace_response.json().get("trace_items", [])),
        "decision_trace_has_review": trace_response.json().get("failure_review") is not None,
        "decision_history_status": history_response.status_code,
        "decision_history_items": (
            len(history_response.json()) if isinstance(history_response.json(), list) else None
        ),
        "review_clusters_status": clusters_response.status_code,
        "review_clusters_count": (
            len(clusters_response.json()) if isinstance(clusters_response.json(), list) else None
        ),
        "created_review_id": review.review_id if review is not None else None,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
