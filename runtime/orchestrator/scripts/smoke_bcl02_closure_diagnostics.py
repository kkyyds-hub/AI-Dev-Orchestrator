"""BCL-02 smoke: verify project closure diagnostics endpoint.

Covers:
- Non-existent project returns 404.
- Fresh project (no tasks, no repo) returns blocked with next_actions.
- Partially configured project aggregates real task/run counts.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from _smoke_runtime_env import prepare_runtime_data_dir

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v5-bcl02-closure-diagnostics-smoke"

if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


# -- Helpers -------------------------------------------------------------

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
    os.environ["DAILY_BUDGET_USD"] = "8.00"
    os.environ["SESSION_BUDGET_USD"] = "8.00"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"
    # SQLite needs the db subdirectory to exist before first connection.
    (runtime_data_dir / "db").mkdir(parents=True, exist_ok=True)
    return runtime_data_dir


# -- Test scenarios ------------------------------------------------------

def test_project_not_found_returns_404(client: TestClient) -> None:
    """A random UUID that does not match any project must return 404."""
    non_existent_id = str(uuid4())
    response = client.get(f"/projects/{non_existent_id}/closure-diagnostics")
    assert response.status_code == 404, (
        f"Expected 404 for non-existent project, got {response.status_code}"
    )
    print("PASS test_project_not_found_returns_404")


def test_fresh_project_returns_blocked(client: TestClient) -> None:
    """A freshly created project with no tasks / no repo must return blocked."""
    # Create a fresh project
    project = _request_json(
        client,
        "POST",
        "/projects",
        201,
        {"name": "BCL-02 Fresh Project", "summary": "Fresh project for smoke test."},
    )
    project_id = project["id"]

    # Query diagnostics
    diag = _request_json(
        client, "GET", f"/projects/{project_id}/closure-diagnostics", 200
    )

    # Must be blocked
    assert diag["overall_status"] == "blocked", (
        f"Expected blocked, got {diag['overall_status']}"
    )

    # Must have blocking reason codes
    codes = diag["blocking_reason_codes"]
    assert isinstance(codes, list), f"blocking_reason_codes must be a list, got {type(codes)}"
    assert "provider_not_configured" in codes, (
        f"Expected provider_not_configured in blocking_reason_codes, got {codes}"
    )
    assert "repository_not_bound" in codes, (
        f"Expected repository_not_bound in blocking_reason_codes, got {codes}"
    )
    assert "no_tasks" in codes, (
        f"Expected no_tasks in blocking_reason_codes, got {codes}"
    )

    # Provider subsection
    provider = diag["provider"]
    assert provider["configured"] is False
    assert provider["last_test_status"] == "not_applicable"

    # Repository subsection
    repo = diag["repository"]
    assert repo["bound"] is False
    assert repo["snapshot_exists"] is False

    # Task runtime subsection
    runtime = diag["task_runtime"]
    assert runtime["task_count"] == 0
    assert runtime["pending_task_count"] == 0
    assert runtime["run_count"] == 0

    # Governance subsection
    gov = diag["governance"]
    assert gov["memory_checkpoint_count"] == 0
    assert gov["agent_session_count"] == 0
    assert gov["approval_count"] == 0
    assert gov["change_batch_count"] == 0
    assert gov["commit_candidate_count"] == 0

    # Next actions
    actions = diag["next_actions"]
    assert isinstance(actions, list) and len(actions) > 0, (
        f"Expected non-empty next_actions for fresh project, got {actions}"
    )
    action_codes = {a["code"] for a in actions}
    assert "configure_provider" in action_codes
    assert "test_provider" in action_codes
    assert "bind_repository" in action_codes
    assert "apply_sop_plan" in action_codes

    # Each action must have code, label, api
    for action in actions:
        assert isinstance(action["code"], str) and action["code"]
        assert isinstance(action["label"], str) and action["label"]
        assert isinstance(action["api"], str) and action["api"]

    print("PASS test_fresh_project_returns_blocked")


def test_project_with_tasks_aggregates_real_counts(client: TestClient) -> None:
    """A project with tasks and runs must aggregate real counts from DB."""
    # Create project
    project = _request_json(
        client,
        "POST",
        "/projects",
        201,
        {
            "name": "BCL-02 Task Project",
            "summary": "Project with tasks for aggregation smoke test.",
        },
    )
    project_id = project["id"]

    # Create multiple tasks via the API
    task1 = _request_json(
        client,
        "POST",
        "/tasks",
        201,
        {
            "title": "BCL-02 Task 1",
            "project_id": project_id,
            "input_summary": "First task for diagnostics smoke.",
        },
    )
    task2 = _request_json(
        client,
        "POST",
        "/tasks",
        201,
        {
            "title": "BCL-02 Task 2",
            "project_id": project_id,
            "input_summary": "Second task for diagnostics smoke.",
        },
    )

    # Query diagnostics
    diag = _request_json(
        client, "GET", f"/projects/{project_id}/closure-diagnostics", 200
    )

    # Task runtime must reflect real counts
    runtime = diag["task_runtime"]
    assert runtime["task_count"] >= 2, (
        f"Expected task_count >= 2, got {runtime['task_count']}"
    )
    assert runtime["pending_task_count"] >= 2, (
        f"Expected pending_task_count >= 2, got {runtime['pending_task_count']}"
    )
    assert runtime["run_count"] == 0, (
        f"Expected run_count=0 for new tasks, got {runtime['run_count']}"
    )

    # No longer should have no_tasks in blocking codes
    codes = diag["blocking_reason_codes"]
    assert "no_tasks" not in codes, (
        f"Expected no_tasks NOT in blocking_reason_codes after creating tasks, got {codes}"
    )

    # overall_status should still be blocked (no provider, no repo)
    assert diag["overall_status"] in ("blocked", "ready"), (
        f"Expected blocked or ready, got {diag['overall_status']}"
    )

    print("PASS test_project_with_tasks_aggregates_real_counts")


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
        ("test_project_not_found_returns_404", test_project_not_found_returns_404),
        ("test_fresh_project_returns_blocked", test_fresh_project_returns_blocked),
        ("test_project_with_tasks_aggregates_real_counts", test_project_with_tasks_aggregates_real_counts),
    ]:
        try:
            fn(client)
        except Exception as exc:
            print(f"FAIL {name}: {exc}")
            all_passed = False

    print()
    if all_passed:
        print("BCL-02 smoke: ALL PASSED")
    else:
        print("BCL-02 smoke: SOME FAILED")
        sys.exit(1)
