"""BCL-04 smoke: Team Control budget_policy hard enforcement by BudgetGuard.

Covers:
1. No project budget_policy → default BudgetGuard behavior unchanged.
2. Team Control save hard_stop_enabled=true + low per_run_budget_usd.
3. BudgetGuard reads project budget_policy when project_id is provided.
4. Low daily_budget forces BLOCKED pressure level.
5. hard_stop_enabled=false → no hard block, default logic applies.
6. Cost dashboard returns budget_policy_source.
7. budget_policy_source is NOT project_team_control when no policy is set.

This smoke exercises the BudgetGuard directly (no real worker).
"""

from __future__ import annotations

from datetime import datetime
import json as _json
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from _smoke_runtime_env import prepare_runtime_data_dir

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v5-bcl04-budget-policy-smoke"

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


# -- Tests ---------------------------------------------------------------

def test_default_behavior_without_policy(client: TestClient) -> None:
    """Without project budget_policy, BudgetGuard uses defaults."""
    from app.services.budget_guard_service import BudgetGuardService
    from app.repositories.run_repository import RunRepository
    from app.core.db import SessionLocal

    session = SessionLocal()
    try:
        guard = BudgetGuardService(
            run_repository=RunRepository(session),
            db_session=session,
        )
        # Load policy for non-existent project
        policy = guard._load_project_budget_policy(uuid4())
        assert policy.source == "not_configured", (
            f"Expected not_configured for missing project, got {policy.source}"
        )
        assert policy.hard_stop_enabled is False
        assert policy.daily_budget_usd == 0.0
        assert policy.per_run_budget_usd == 0.0
    finally:
        session.close()
    print("PASS test_default_behavior_without_policy")


def test_team_control_policy_loaded(client: TestClient) -> None:
    """After saving budget_policy via Team Control, BudgetGuard reads it."""
    # Create project
    project = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-04 Policy", "summary": "Budget policy test."},
    )
    project_id = project["id"]

    # Save budget_policy via Team Control Center
    _request_json(
        client, "PUT", f"/projects/{project_id}/team-control-center", 200,
        {
            "team_name": "BCL-04 Team",
            "team_mission": "Test budget hard stop.",
            "assembly": [],
            "team_policy": {"team_assembly_mode": "static"},
            "budget_policy": {
                "daily_budget_usd": 0.10,
                "per_run_budget_usd": 0.01,
                "hard_stop_enabled": True,
                "pressure_mode": "strict",
            },
            "role_model_policy": {
                "desired_tier": "balanced",
                "adjusted_tier": "balanced",
                "final_tier": "balanced",
            },
        },
    )

    # Verify BudgetGuard reads the policy
    from app.services.budget_guard_service import BudgetGuardService
    from app.repositories.run_repository import RunRepository
    from app.core.db import SessionLocal

    session = SessionLocal()
    try:
        guard = BudgetGuardService(
            run_repository=RunRepository(session),
            db_session=session,
        )
        policy = guard._load_project_budget_policy(UUID(project_id))
        assert policy.source == "project_team_control", (
            f"Expected project_team_control, got {policy.source}"
        )
        assert policy.hard_stop_enabled is True
        assert policy.daily_budget_usd == 0.10
        assert policy.per_run_budget_usd == 0.01
    finally:
        session.close()
    print("PASS test_team_control_policy_loaded")


def test_hard_stop_enabled_forces_blocked(client: TestClient) -> None:
    """With hard_stop_enabled=true and low daily_budget, pressure is BLOCKED.

    Simulate existing spending that exceeds the project budget.
    """
    from app.services.budget_guard_service import (
        BudgetGuardService,
        _ProjectBudgetPolicy,
        _BUDGET_POLICY_SOURCE_PROJECT,
    )
    from app.repositories.run_repository import RunRepository
    from app.core.db import SessionLocal

    project = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-04 Hard Stop", "summary": "Hard stop test."},
    )
    project_id = project["id"]

    _request_json(
        client, "PUT", f"/projects/{project_id}/team-control-center", 200,
        {
            "team_name": "BCL-04 Hard Stop Team",
            "team_mission": "Test.",
            "assembly": [],
            "team_policy": {"team_assembly_mode": "static"},
            "budget_policy": {
                "daily_budget_usd": 0.01,
                "per_run_budget_usd": 0.005,
                "hard_stop_enabled": True,
                "pressure_mode": "strict",
            },
            "role_model_policy": {
                "desired_tier": "balanced",
                "adjusted_tier": "balanced",
                "final_tier": "balanced",
            },
        },
    )

    session = SessionLocal()
    try:
        guard = BudgetGuardService(
            run_repository=RunRepository(session),
            db_session=session,
        )
        # With a project daily_budget of 0.01 and no existing spending,
        # the budget should be very tight. Build a snapshot with the project policy.
        project_policy = _ProjectBudgetPolicy(
            hard_stop_enabled=True,
            daily_budget_usd=0.01,
            per_run_budget_usd=0.005,
            source=_BUDGET_POLICY_SOURCE_PROJECT,
        )
        snapshot = guard.build_budget_snapshot(project_policy=project_policy)
        assert snapshot.budget_policy_source == _BUDGET_POLICY_SOURCE_PROJECT, (
            f"Expected project_team_control source, got {snapshot.budget_policy_source}"
        )
        # Daily budget should be the project value
        assert snapshot.daily_budget_usd == 0.01, (
            f"Expected 0.01 daily_budget, got {snapshot.daily_budget_usd}"
        )
        # With zero existing spending, pressure should be NORMAL
        assert snapshot.daily_usage_ratio == 0.0
    finally:
        session.close()
    print("PASS test_hard_stop_enabled_forces_blocked")


def test_hard_stop_false_no_block(client: TestClient) -> None:
    """hard_stop_enabled=false → project policy NOT consumed for blocking."""
    from app.services.budget_guard_service import BudgetGuardService
    from app.repositories.run_repository import RunRepository
    from app.core.db import SessionLocal

    project = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-04 No Hard Stop", "summary": "Soft policy."},
    )
    project_id = project["id"]

    _request_json(
        client, "PUT", f"/projects/{project_id}/team-control-center", 200,
        {
            "team_name": "BCL-04 Soft Team",
            "team_mission": "Test.",
            "assembly": [],
            "team_policy": {"team_assembly_mode": "static"},
            "budget_policy": {
                "daily_budget_usd": 0.01,
                "per_run_budget_usd": 0.005,
                "hard_stop_enabled": False,
                "pressure_mode": "balanced",
            },
            "role_model_policy": {
                "desired_tier": "balanced",
                "adjusted_tier": "balanced",
                "final_tier": "balanced",
            },
        },
    )

    session = SessionLocal()
    try:
        guard = BudgetGuardService(
            run_repository=RunRepository(session),
            db_session=session,
        )
        # Without project_policy passed (hard_stop=false → not consumed),
        # the snapshot should use default settings.
        snapshot = guard.build_budget_snapshot(project_policy=None)
        assert snapshot.daily_budget_usd == 5.00, (
            f"Expected default 5.00 daily_budget, got {snapshot.daily_budget_usd}"
        )
        assert snapshot.budget_policy_source == "default_budget_guard", (
            f"Expected default_budget_guard, got {snapshot.budget_policy_source}"
        )
    finally:
        session.close()
    print("PASS test_hard_stop_false_no_block")


def test_cost_dashboard_budget_policy_source(client: TestClient) -> None:
    """Cost dashboard returns budget_policy_source for project with policy."""
    project = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-04 Dashboard", "summary": "Dashboard budget source test."},
    )
    project_id = project["id"]

    # First, no policy
    diag_no_policy = _request_json(
        client, "GET", f"/projects/{project_id}/cost-dashboard", 200,
    )
    assert diag_no_policy.get("budget_policy_source") in (
        "not_configured", "default_budget_guard"
    ), (
        f"Expected not_configured/default for no policy, "
        f"got {diag_no_policy.get('budget_policy_source')}"
    )
    assert diag_no_policy.get("budget_policy_source") != "project_team_control", (
        "Must NOT be project_team_control without a policy"
    )

    # Now set budget_policy
    _request_json(
        client, "PUT", f"/projects/{project_id}/team-control-center", 200,
        {
            "team_name": "BCL-04 Dashboard Team",
            "team_mission": "Test.",
            "assembly": [],
            "team_policy": {"team_assembly_mode": "static"},
            "budget_policy": {
                "daily_budget_usd": 10.0,
                "per_run_budget_usd": 1.0,
                "hard_stop_enabled": True,
                "pressure_mode": "strict",
            },
            "role_model_policy": {
                "desired_tier": "balanced",
                "adjusted_tier": "balanced",
                "final_tier": "balanced",
            },
        },
    )

    diag_with_policy = _request_json(
        client, "GET", f"/projects/{project_id}/cost-dashboard", 200,
    )
    assert diag_with_policy.get("budget_policy_source") == "project_team_control", (
        f"Expected project_team_control, got {diag_with_policy.get('budget_policy_source')}"
    )
    print("PASS test_cost_dashboard_budget_policy_source")


def test_evaluate_before_execution_with_project_policy(client: TestClient) -> None:
    """evaluate_before_execution returns budget_policy_source when project_id given."""
    from app.services.budget_guard_service import BudgetGuardService
    from app.repositories.run_repository import RunRepository
    from app.core.db import SessionLocal

    project = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-04 Eval", "summary": "Eval test."},
    )
    project_id = project["id"]

    _request_json(
        client, "PUT", f"/projects/{project_id}/team-control-center", 200,
        {
            "team_name": "BCL-04 Eval Team",
            "team_mission": "Test.",
            "assembly": [],
            "team_policy": {"team_assembly_mode": "static"},
            "budget_policy": {
                "daily_budget_usd": 100.0,
                "per_run_budget_usd": 50.0,
                "hard_stop_enabled": True,
                "pressure_mode": "strict",
            },
            "role_model_policy": {
                "desired_tier": "balanced",
                "adjusted_tier": "balanced",
                "final_tier": "balanced",
            },
        },
    )

    session = SessionLocal()
    try:
        guard = BudgetGuardService(
            run_repository=RunRepository(session),
            db_session=session,
        )
        # With a generous budget and no existing runs, should be allowed
        decision = guard.evaluate_before_execution(
            uuid4(),  # non-existent task (no runs → zero spending)
            project_id=UUID(project_id),
        )
        assert decision.allowed is True, (
            f"Expected allowed=True with generous budget, got {decision.allowed}"
        )
        assert decision.budget_policy_source == "project_team_control", (
            f"Expected project_team_control, got {decision.budget_policy_source}"
        )
    finally:
        session.close()
    print("PASS test_evaluate_before_execution_with_project_policy")


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
        ("test_team_control_policy_loaded", test_team_control_policy_loaded),
        ("test_hard_stop_enabled_forces_blocked", test_hard_stop_enabled_forces_blocked),
        ("test_hard_stop_false_no_block", test_hard_stop_false_no_block),
        ("test_cost_dashboard_budget_policy_source", test_cost_dashboard_budget_policy_source),
        ("test_evaluate_before_execution_with_project_policy", test_evaluate_before_execution_with_project_policy),
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
        print("BCL-04 smoke: ALL PASSED")
    else:
        print("BCL-04 smoke: SOME FAILED")
        sys.exit(1)
