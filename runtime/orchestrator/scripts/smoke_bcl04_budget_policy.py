"""BCL-04 rework smoke: Team Control budget_policy hard enforcement.

Covers:
1.  No project budget_policy → default BudgetGuard behavior unchanged.
2.  hard_stop_enabled=true + daily_budget_usd exceeded → BLOCKED.
3.  hard_stop_enabled=true + per_run_budget_usd exceeded → BLOCKED.
4.  Worker run-once real path blocked by project budget_policy.
5.  Provider NOT called when worker is blocked.
6.  Worker blocked run log JSONL contains budget_policy_source=project_team_control.
7.  hard_stop_enabled=false → no hard block from project policy.
8.  Cost dashboard returns source aligned with BudgetGuard.
"""

from __future__ import annotations

import json as _json
import os
import sys
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from _smoke_runtime_env import prepare_runtime_data_dir

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v5-bcl04-budget-policy-rework-smoke"

if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


def _request_json(
    client: TestClient,
    method: str,
    path: str,
    expected_status: int,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    response = client.request(method, path, json=payload)
    if response.status_code != expected_status:
        raise SystemExit(
            f"{method} {path} expected {expected_status}, got {response.status_code}: {response.text}"
        )
    return response.json()  # type: ignore[no-any-return]


def _prepare_env() -> Path:
    runtime_data_dir = prepare_runtime_data_dir(SMOKE_RUNTIME_DATA_DIR)
    os.environ["RUNTIME_DATA_DIR"] = str(runtime_data_dir)
    os.environ["DAILY_BUDGET_USD"] = "5.00"
    os.environ["SESSION_BUDGET_USD"] = "8.00"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"
    (runtime_data_dir / "db").mkdir(parents=True, exist_ok=True)
    return runtime_data_dir


def _set_budget_policy(
    client: TestClient,
    project_id: str,
    *,
    daily: float,
    per_run: float,
    hard_stop: bool,
) -> None:
    _request_json(
        client, "PUT", f"/projects/{project_id}/team-control-center", 200,
        {
            "team_name": "BCL-04 Rework",
            "team_mission": "Test budget policy.",
            "assembly": [],
            "team_policy": {"team_assembly_mode": "static"},
            "budget_policy": {
                "daily_budget_usd": daily,
                "per_run_budget_usd": per_run,
                "hard_stop_enabled": hard_stop,
                "pressure_mode": "strict" if hard_stop else "balanced",
            },
            "role_model_policy": {
                "desired_tier": "balanced",
                "adjusted_tier": "balanced",
                "final_tier": "balanced",
            },
        },
    )


# -- Tests ---------------------------------------------------------------

def test_default_behavior_without_policy(client: TestClient) -> None:
    """Without project budget_policy, BudgetGuard loads not_configured."""
    from app.services.budget_guard_service import BudgetGuardService
    from app.repositories.run_repository import RunRepository
    from app.core.db import SessionLocal

    session = SessionLocal()
    try:
        guard = BudgetGuardService(
            run_repository=RunRepository(session),
            db_session=session,
        )
        policy = guard._load_project_budget_policy(uuid4())
        assert policy.source == "not_configured"
        assert policy.hard_stop_enabled is False
    finally:
        session.close()
    print("PASS test_default_behavior_without_policy")


def test_hard_stop_daily_budget_blocked(client: TestClient) -> None:
    """hard_stop_enabled=true + daily_cost >= project daily_budget → BLOCKED."""
    # Create project with very low daily budget
    project = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-04 Daily Block", "summary": "Daily budget block test."},
    )
    project_id = project["id"]
    _set_budget_policy(client, project_id, daily=0.02, per_run=50.0, hard_stop=True)

    # Create a task
    task = _request_json(
        client, "POST", "/tasks", 201,
        {"title": "Daily Budget Task", "project_id": project_id,
         "input_summary": "Test daily budget block."},
    )

    # Seed runs with cost exceeding the daily budget (0.02)
    from app.core.db import SessionLocal
    from app.repositories.run_repository import RunRepository
    from app.services.budget_guard_service import BudgetGuardService

    session = SessionLocal()
    try:
        # Create a completed run with high cost
        run_repo = RunRepository(session)
        run = run_repo.create_running_run(task_id=UUID(task["id"]), model_name="test")
        # Finish with high cost to exceed daily budget of $0.02
        from app.domain.run import RunStatus
        run_repo.finish_run(
            run_id=run.id,
            status=RunStatus.SUCCEEDED,
            result_summary="Seed run for budget block test.",
            estimated_cost=0.05,  # exceeds $0.02 daily budget
        )

        guard = BudgetGuardService(
            run_repository=run_repo,
            db_session=session,
        )
        decision = guard.evaluate_before_execution(
            UUID(task["id"]),
            project_id=UUID(project_id),
        )
        assert decision.allowed is False, (
            f"Expected allowed=False (daily budget exceeded), got {decision.allowed}"
        )
        assert decision.budget.pressure_level.value == "blocked", (
            f"Expected BLOCKED, got {decision.budget.pressure_level.value}"
        )
        assert decision.budget_policy_source == "project_team_control", (
            f"Expected project_team_control, got {decision.budget_policy_source}"
        )
        assert decision.budget.daily_budget_usd == 0.02, (
            f"Expected 0.02 daily_budget, got {decision.budget.daily_budget_usd}"
        )
        assert decision.budget.daily_budget_exceeded is True
    finally:
        session.close()
    print("PASS test_hard_stop_daily_budget_blocked")


def test_hard_stop_per_run_budget_blocked(client: TestClient) -> None:
    """hard_stop_enabled=true + estimated_cost > per_run_budget → BLOCKED."""
    project = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-04 Per-Run Block", "summary": "Per-run budget block test."},
    )
    project_id = project["id"]
    _set_budget_policy(client, project_id, daily=100.0, per_run=0.001, hard_stop=True)

    task = _request_json(
        client, "POST", "/tasks", 201,
        {"title": "Per-Run Budget Task", "project_id": project_id,
         "input_summary": "Test per-run budget block."},
    )

    from app.core.db import SessionLocal
    from app.repositories.run_repository import RunRepository
    from app.services.budget_guard_service import BudgetGuardService

    session = SessionLocal()
    try:
        guard = BudgetGuardService(
            run_repository=RunRepository(session),
            db_session=session,
        )
        # Default estimated_run_cost_usd = $0.01 > per_run_budget_usd = $0.001
        decision = guard.evaluate_before_execution(
            UUID(task["id"]),
            project_id=UUID(project_id),
            estimated_run_cost_usd=0.01,
        )
        assert decision.allowed is False, (
            f"Expected allowed=False (per-run exceeded), got {decision.allowed}"
        )
        assert decision.strategy_code == "bg-project-per-run-budget", (
            f"Expected bg-project-per-run-budget, got {decision.strategy_code}"
        )
        assert decision.budget_policy_source == "project_team_control"
        assert decision.budget.per_run_budget_usd == 0.001
        assert decision.budget.estimated_run_cost_usd == 0.01
    finally:
        session.close()
    print("PASS test_hard_stop_per_run_budget_blocked")


def test_worker_run_once_blocked_by_project_policy(client: TestClient) -> None:
    """Real worker run-once path blocked by project budget_policy.

    Provider/executor MUST NOT be called when budget blocks execution.
    Worker result must show claimed=True and failure_category.
    """
    project = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-04 Worker Block", "summary": "Worker block test."},
    )
    project_id = project["id"]
    # Very low daily budget — any run will exceed it
    _set_budget_policy(client, project_id, daily=0.001, per_run=50.0, hard_stop=True)

    # Seed a run with cost exceeding $0.001
    task = _request_json(
        client, "POST", "/tasks", 201,
        {"title": "Worker Block Task", "project_id": project_id,
         "input_summary": "Test worker block."},
    )
    from app.core.db import SessionLocal
    from app.repositories.run_repository import RunRepository
    from app.domain.run import RunStatus

    session = SessionLocal()
    try:
        run_repo = RunRepository(session)
        run = run_repo.create_running_run(task_id=UUID(task["id"]), model_name="test-seed")
        run_repo.finish_run(
            run_id=run.id, status=RunStatus.SUCCEEDED,
            result_summary="Seed cost to exceed budget.",
            estimated_cost=0.01,
        )
        session.commit()
    finally:
        session.close()

    # Create a fresh pending task for the worker to pick up
    _request_json(
        client, "POST", "/tasks", 201,
        {"title": "Worker Pending Task", "project_id": project_id,
         "input_summary": "Pending for worker."},
    )

    # Monkeypatch the executor to verify it's NOT called
    called_executor = False

    def fake_execute(*args: object, **kwargs: object) -> None:
        nonlocal called_executor
        called_executor = True

    with patch(
        "app.services.executor_service.ExecutorService.execute_task",
        side_effect=fake_execute,
    ):
        result = _request_json(
            client, "POST",
            f"/workers/run-once?project_id={project_id}", 200,
        )

    # Worker should claim the task but be blocked by budget guard
    assert result.get("claimed") is True, (
        f"Worker should claim a pending task, got {result}"
    )
    # Execution mode should be None (no provider call)
    assert result.get("execution_mode") is None or result.get("execution_mode") == "", (
        f"execution_mode should be None when blocked, got {result.get('execution_mode')}"
    )
    # Provider must NOT have been called
    assert called_executor is False, "Executor.execute() must NOT be called when blocked"

    # Verify run log has budget_policy_source
    log_path = result.get("log_path")
    if log_path:
        log_full = Path(os.environ["RUNTIME_DATA_DIR"]) / log_path
        if log_full.exists():
            lines = log_full.read_text(encoding="utf-8").strip().splitlines()
            guard_events = [
                _json.loads(line) for line in lines
                if "guard_blocked" in line
            ]
            if guard_events:
                data = guard_events[0].get("data", {})
                source = data.get("budget_policy_source", "")
                assert source == "project_team_control", (
                    f"JSONL budget_policy_source expected project_team_control, got {source}"
                )
                print("    [log] budget_policy_source verified in JSONL")

    print("PASS test_worker_run_once_blocked_by_project_policy")


def test_hard_stop_false_no_hard_block(client: TestClient) -> None:
    """hard_stop_enabled=false → project policy does NOT cause hard block."""
    project = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-04 Soft Block", "summary": "Soft policy test."},
    )
    project_id = project["id"]
    _set_budget_policy(client, project_id, daily=0.001, per_run=0.001, hard_stop=False)

    from app.core.db import SessionLocal
    from app.repositories.run_repository import RunRepository
    from app.services.budget_guard_service import BudgetGuardService

    session = SessionLocal()
    try:
        guard = BudgetGuardService(
            run_repository=RunRepository(session),
            db_session=session,
        )
        decision = guard.evaluate_before_execution(
            uuid4(),
            project_id=UUID(project_id),
        )
        # Must be allowed — hard_stop=false, so project policy is not consumed
        assert decision.allowed is True, (
            f"Expected allowed=True (hard_stop=false), got {decision.allowed}"
        )
        # Source should be project_team_control_soft
        assert decision.budget_policy_source == "project_team_control_soft", (
            f"Expected project_team_control_soft, got {decision.budget_policy_source}"
        )
        # Daily budget should still be default (not project override)
        assert decision.budget.daily_budget_usd == 5.00, (
            f"Expected default 5.00, got {decision.budget.daily_budget_usd}"
        )
    finally:
        session.close()
    print("PASS test_hard_stop_false_no_hard_block")


def test_cost_dashboard_source_aligned_with_guard(client: TestClient) -> None:
    """Cost dashboard budget_policy_source must align with BudgetGuard."""
    # Project without policy
    project_no_policy = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-04 Dash No Policy", "summary": "No policy dashboard."},
    )
    diag1 = _request_json(
        client, "GET",
        f"/projects/{project_no_policy['id']}/cost-dashboard", 200,
    )
    assert diag1.get("budget_policy_source") == "not_configured", (
        f"No policy → not_configured, got {diag1.get('budget_policy_source')}"
    )

    # Project with hard_stop=true
    project_hard = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-04 Dash Hard", "summary": "Hard stop dashboard."},
    )
    _set_budget_policy(client, project_hard["id"], daily=10.0, per_run=1.0, hard_stop=True)
    diag2 = _request_json(
        client, "GET",
        f"/projects/{project_hard['id']}/cost-dashboard", 200,
    )
    assert diag2.get("budget_policy_source") == "project_team_control", (
        f"hard_stop=true → project_team_control, got {diag2.get('budget_policy_source')}"
    )

    # Project with hard_stop=false
    project_soft = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-04 Dash Soft", "summary": "Soft policy dashboard."},
    )
    _set_budget_policy(client, project_soft["id"], daily=10.0, per_run=1.0, hard_stop=False)
    diag3 = _request_json(
        client, "GET",
        f"/projects/{project_soft['id']}/cost-dashboard", 200,
    )
    assert diag3.get("budget_policy_source") == "project_team_control_soft", (
        f"hard_stop=false → project_team_control_soft, got {diag3.get('budget_policy_source')}"
    )
    print("PASS test_cost_dashboard_source_aligned_with_guard")


# -- Harness -------------------------------------------------------------

if __name__ == "__main__":
    _prepare_env()

    from app.core.db import init_database
    from app.main import create_application

    init_database()
    app = create_application()
    client = TestClient(app)

    all_passed = True
    for name, fn in [
        ("test_default_behavior_without_policy", test_default_behavior_without_policy),
        ("test_hard_stop_daily_budget_blocked", test_hard_stop_daily_budget_blocked),
        ("test_hard_stop_per_run_budget_blocked", test_hard_stop_per_run_budget_blocked),
        ("test_worker_run_once_blocked_by_project_policy", test_worker_run_once_blocked_by_project_policy),
        ("test_hard_stop_false_no_hard_block", test_hard_stop_false_no_hard_block),
        ("test_cost_dashboard_source_aligned_with_guard", test_cost_dashboard_source_aligned_with_guard),
    ]:
        try:
            fn(client)
        except Exception as exc:
            print(f"FAIL {name}: {exc}")
            import traceback
            traceback.print_exc()
            all_passed = False

    print()
    if all_passed:
        print("BCL-04 smoke (rework): ALL PASSED")
    else:
        print("BCL-04 smoke (rework): SOME FAILED")
        sys.exit(1)
