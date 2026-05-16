"""BCL-02 smoke (rework): verify project closure diagnostics endpoint.

Covers:
- Non-existent project → 404.
- Fresh project → blocked + provider_not_configured + repository_not_bound + no_tasks.
- Provider configured but not tested → provider_not_tested + blocked.
- Has tasks but no provider/repo → still blocked (NOT ready).
- All tasks completed but no provider/repo → still blocked (NOT completed).
- Partially configured project aggregates real counts.

This smoke does NOT call OpenAI, trigger workers, write repositories, or produce side effects.
Repository binding and snapshot are NOT faked; fields are honest false/not_applicable.
Run coverage is limited: RunRepository aggregation is exercised via the service path,
but smoke does not create runs (no worker is triggered).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from _smoke_runtime_env import prepare_runtime_data_dir

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v5-bcl02-closure-diagnostics-rework-smoke"

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


def _configure_provider(client: TestClient, api_key: str) -> None:
    """Configure OpenAI provider with a test API key (no real validation)."""
    _request_json(
        client,
        "PUT",
        "/provider-settings/openai",
        200,
        {
            "api_key": api_key,
            "base_url": "https://api.openai.com/v1",
        },
    )


def _assert_blocking_codes_contain(diag: dict[str, object], *expected: str) -> None:
    """Assert all expected codes are present in blocking_reason_codes."""
    codes: list[str] = diag.get("blocking_reason_codes", [])  # type: ignore[assignment]
    for code in expected:
        assert code in codes, (
            f"Expected {code} in blocking_reason_codes, got {codes}"
        )


def _assert_blocking_codes_exclude(diag: dict[str, object], *unexpected: str) -> None:
    """Assert none of the unexpected codes are present."""
    codes: list[str] = diag.get("blocking_reason_codes", [])  # type: ignore[assignment]
    for code in unexpected:
        assert code not in codes, (
            f"Expected {code} NOT in blocking_reason_codes, got {codes}"
        )


def _assert_action_codes_contain(diag: dict[str, object], *expected: str) -> None:
    """Assert all expected action codes appear in next_actions."""
    actions: list[dict[str, object]] = diag.get("next_actions", [])  # type: ignore[assignment]
    actual_codes = {a["code"] for a in actions}
    for code in expected:
        assert code in actual_codes, (
            f"Expected next_action {code}, got {actual_codes}"
        )


# Only these API paths are known to exist in the current codebase.
_VALID_API_PATHS = frozenset({
    "PUT /provider-settings/openai",
    "POST /provider-settings/openai/test",
    "POST /planning/drafts",
})


def _assert_actions_have_real_api_paths(
    diag: dict[str, object], *, project_id: str
) -> None:
    """Every next_action.api must reference a real backend endpoint.

    `bind_repository` uses PUT /repositories/projects/{project_id} which is
    validated separately because it embeds the project id.
    """
    actions: list[dict[str, object]] = diag.get("next_actions", [])  # type: ignore[assignment]
    for action in actions:
        code = action["code"]
        api = str(action["api"])

        if code == "bind_repository":
            expected = f"PUT /repositories/projects/{project_id}"
            assert api == expected, (
                f"bind_repository api expected {expected}, got {api}"
            )
            continue

        assert api in _VALID_API_PATHS, (
            f"next_action {code} has unrecognized api path: {api}"
        )


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
    """Fresh project: no provider, no repo, no tasks → blocked with full next_actions."""
    project = _request_json(
        client,
        "POST",
        "/projects",
        201,
        {"name": "BCL-02 Fresh Rework", "summary": "Fresh project for rework smoke."},
    )
    project_id = project["id"]

    diag = _request_json(
        client, "GET", f"/projects/{project_id}/closure-diagnostics", 200
    )

    # Must be blocked
    assert diag["overall_status"] == "blocked", (
        f"Expected blocked, got {diag['overall_status']}"
    )

    # Blocking reason codes
    _assert_blocking_codes_contain(
        diag, "provider_not_configured", "repository_not_bound", "no_tasks"
    )
    _assert_blocking_codes_exclude(diag, "provider_not_tested")

    # Provider
    assert diag["provider"]["configured"] is False
    assert diag["provider"]["last_test_status"] == "not_applicable"

    # Repository
    assert diag["repository"]["bound"] is False
    assert diag["repository"]["snapshot_exists"] is False
    assert diag["repository"]["day15_flow_status"] == "not_applicable"

    # Task runtime — all zeros
    rt = diag["task_runtime"]
    assert rt["task_count"] == 0
    assert rt["pending_task_count"] == 0
    assert rt["run_count"] == 0

    # Governance — all zeros
    gov = diag["governance"]
    for field in ("memory_checkpoint_count", "agent_session_count",
                  "approval_count", "change_batch_count", "commit_candidate_count"):
        assert gov[field] == 0, f"governance.{field} expected 0, got {gov[field]}"

    # Next actions
    _assert_action_codes_contain(
        diag, "configure_provider", "test_provider", "bind_repository", "create_plan_draft"
    )
    for action in diag["next_actions"]:
        assert isinstance(action["code"], str) and action["code"]
        assert isinstance(action["label"], str) and action["label"]
        assert isinstance(action["api"], str) and action["api"]

    # Every next_action.api must be a real backend endpoint
    _assert_actions_have_real_api_paths(diag, project_id=str(project_id))

    print("PASS test_fresh_project_returns_blocked")


def test_provider_configured_but_not_tested(client: TestClient) -> None:
    """Provider configured with a key but never tested → provider_not_tested, still blocked."""
    # Configure provider first (shared state across projects)
    _configure_provider(client, "sk-test-smoke-bcl02-key")

    project = _request_json(
        client,
        "POST",
        "/projects",
        201,
        {"name": "BCL-02 Provider Not Tested", "summary": "Provider set but untested."},
    )
    project_id = project["id"]

    diag = _request_json(
        client, "GET", f"/projects/{project_id}/closure-diagnostics", 200
    )

    # Provider is configured but not tested
    assert diag["provider"]["configured"] is True, (
        f"Expected configured=True after PUT, got {diag['provider']}"
    )
    assert diag["provider"]["last_test_status"] == "not_tested"

    # Must still be blocked
    assert diag["overall_status"] == "blocked", (
        f"Expected blocked, got {diag['overall_status']}"
    )

    # Blocking reasons must include provider_not_tested, NOT provider_not_configured
    _assert_blocking_codes_contain(diag, "provider_not_tested")
    _assert_blocking_codes_exclude(diag, "provider_not_configured")

    # Action must include test_provider
    _assert_action_codes_contain(diag, "test_provider")

    print("PASS test_provider_configured_but_not_tested")


def test_has_tasks_but_provider_repo_missing(client: TestClient) -> None:
    """Project with pending tasks but no provider → overall_status must be blocked, NOT ready.

    Clearing provider config resets to not_configured state for this test.
    """
    # Clear provider config so we test the not-configured path
    _request_json(
        client,
        "PUT",
        "/provider-settings/openai",
        200,
        {"api_key": "", "base_url": "https://api.openai.com/v1"},
    )

    project = _request_json(
        client,
        "POST",
        "/projects",
        201,
        {"name": "BCL-02 Tasks No Provider", "summary": "Has tasks, missing provider & repo."},
    )
    project_id = project["id"]

    # Create pending tasks
    _request_json(
        client, "POST", "/tasks", 201,
        {"title": "Pending Task A", "project_id": project_id, "input_summary": "Task A."},
    )
    _request_json(
        client, "POST", "/tasks", 201,
        {"title": "Pending Task B", "project_id": project_id, "input_summary": "Task B."},
    )

    diag = _request_json(
        client, "GET", f"/projects/{project_id}/closure-diagnostics", 200
    )

    # Must be blocked — NOT ready
    assert diag["overall_status"] == "blocked", (
        f"Expected blocked (no provider, no repo), got {diag['overall_status']}"
    )

    # Should have provider/repo blocking codes, but NOT no_tasks
    _assert_blocking_codes_contain(diag, "provider_not_configured", "repository_not_bound")
    _assert_blocking_codes_exclude(diag, "no_tasks", "no_pending_tasks")

    # Real task counts
    rt = diag["task_runtime"]
    assert rt["task_count"] >= 2, f"Expected task_count >= 2, got {rt['task_count']}"
    assert rt["pending_task_count"] >= 2, f"Expected pending >= 2, got {rt['pending_task_count']}"

    print("PASS test_has_tasks_but_provider_repo_missing")


def test_all_tasks_completed_but_blocked(client: TestClient) -> None:
    """All tasks terminal (completed), but provider/repo still missing → blocked, NOT completed."""
    project = _request_json(
        client,
        "POST",
        "/projects",
        201,
        {"name": "BCL-02 Completed But Blocked", "summary": "Completed tasks, missing infra."},
    )
    project_id = project["id"]

    task = _request_json(
        client, "POST", "/tasks", 201,
        {"title": "Will Complete", "project_id": project_id, "input_summary": "Going to complete."},
    )

    # Directly set task to completed via repository (no dedicated API for this)
    from app.core.db import SessionLocal
    from app.repositories.task_repository import TaskRepository
    from app.domain.task import TaskStatus

    db_session = SessionLocal()
    try:
        TaskRepository(db_session).set_status(UUID(task["id"]), TaskStatus.COMPLETED)
        db_session.commit()
    finally:
        db_session.close()

    # For the "all completed" path to trigger, we need no pending tasks.
    # The single task was set to completed. No other tasks exist.
    # But we also have no provider and no repo → blocked wins over completed.

    diag = _request_json(
        client, "GET", f"/projects/{project_id}/closure-diagnostics", 200
    )

    # MUST be blocked, NOT completed — blocking reasons take priority
    assert diag["overall_status"] == "blocked", (
        f"Expected blocked (no provider + no repo), got {diag['overall_status']}"
    )

    _assert_blocking_codes_contain(diag, "provider_not_configured", "repository_not_bound")
    _assert_blocking_codes_exclude(diag, "no_tasks")

    # Task is terminal so no pending tasks → no_pending_tasks should appear
    _assert_blocking_codes_contain(diag, "no_pending_tasks")

    rt = diag["task_runtime"]
    assert rt["task_count"] == 1
    assert rt["pending_task_count"] == 0
    assert rt["run_count"] == 0

    print("PASS test_all_tasks_completed_but_blocked")


def test_partial_config_with_real_counts(client: TestClient) -> None:
    """Configure provider, create tasks → real counts aggregated, provider_not_tested still flagged."""
    _configure_provider(client, "sk-test-partial-config-key")

    project = _request_json(
        client,
        "POST",
        "/projects",
        201,
        {"name": "BCL-02 Partial Config", "summary": "Provider set, tasks exist, no repo."},
    )
    project_id = project["id"]

    _request_json(
        client, "POST", "/tasks", 201,
        {"title": "Task 1", "project_id": project_id, "input_summary": "First task."},
    )
    _request_json(
        client, "POST", "/tasks", 201,
        {"title": "Task 2", "project_id": project_id, "input_summary": "Second task."},
    )

    diag = _request_json(
        client, "GET", f"/projects/{project_id}/closure-diagnostics", 200
    )

    # Provider
    assert diag["provider"]["configured"] is True
    assert diag["provider"]["last_test_status"] == "not_tested"

    # Still blocked (no repo)
    assert diag["overall_status"] == "blocked"

    # Blocking codes: provider_not_tested (not not_configured), repository_not_bound
    _assert_blocking_codes_contain(diag, "provider_not_tested", "repository_not_bound")
    _assert_blocking_codes_exclude(diag, "provider_not_configured", "no_tasks")

    # Repository is honest
    assert diag["repository"]["bound"] is False
    assert diag["repository"]["snapshot_exists"] is False
    assert diag["repository"]["day15_flow_status"] == "not_applicable"

    # Task counts
    rt = diag["task_runtime"]
    assert rt["task_count"] >= 2
    assert rt["pending_task_count"] >= 2
    assert rt["run_count"] == 0

    # Governance
    gov = diag["governance"]
    assert isinstance(gov["agent_session_count"], int)
    assert isinstance(gov["approval_count"], int)
    assert isinstance(gov["change_batch_count"], int)
    assert isinstance(gov["commit_candidate_count"], int)

    # Actions
    _assert_action_codes_contain(diag, "test_provider", "bind_repository")
    _assert_actions_have_real_api_paths(diag, project_id=str(project_id))

    print("PASS test_partial_config_with_real_counts")


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
        ("test_provider_configured_but_not_tested", test_provider_configured_but_not_tested),
        ("test_has_tasks_but_provider_repo_missing", test_has_tasks_but_provider_repo_missing),
        ("test_all_tasks_completed_but_blocked", test_all_tasks_completed_but_blocked),
        ("test_partial_config_with_real_counts", test_partial_config_with_real_counts),
    ]:
        try:
            fn(client)
        except Exception as exc:
            print(f"FAIL {name}: {exc}")
            all_passed = False

    print()
    if all_passed:
        print("BCL-02 smoke (rework): ALL PASSED")
    else:
        print("BCL-02 smoke (rework): SOME FAILED")
        sys.exit(1)
