"""BCL-06 smoke: legacy_missing productization.

Covers:
1. provider_reported run NOT counted as legacy_missing.
2. heuristic run NOT counted as legacy_missing.
3. token_accounting_mode=NULL run counted as legacy_missing.
4. missing_mode_run_count preserved (old field).
5. missing_source_breakdown / legacy_missing_run_count present.
6. BCL-05 provider_cache fields preserved.
7. fallback_contract old fields preserved.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from _smoke_runtime_env import prepare_runtime_data_dir

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v5-bcl06-legacy-missing-smoke"

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
    os.environ["DAILY_BUDGET_USD"] = "50.00"
    os.environ["SESSION_BUDGET_USD"] = "80.00"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"
    (runtime_data_dir / "db").mkdir(parents=True, exist_ok=True)
    return runtime_data_dir


# -- Tests ---------------------------------------------------------------

def test_provider_reported_not_in_legacy_missing(client: TestClient) -> None:
    """provider_reported runs must not appear in legacy_missing_run_count."""
    from app.core.db import SessionLocal
    from app.repositories.run_repository import RunRepository
    from app.repositories.task_repository import TaskRepository
    from app.domain.run import RunStatus

    project = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-06 Provider", "summary": "Provider reported test."},
    )
    project_id = project["id"]

    session = SessionLocal()
    try:
        repo = RunRepository(session)
        # Create tasks
        for i in range(2):
            _request_json(client, "POST", "/tasks", 201,
                          {"title": f"Task {i}", "project_id": project_id,
                           "input_summary": f"Test {i}."})
        tasks = TaskRepository(session).list_by_project_id(UUID(project_id))
        tids = [t.id for t in tasks]

        # Run 0: provider_reported (normal worker path)
        r0 = repo.create_running_run(task_id=tids[0], model_name="test")
        repo.finish_run(run_id=r0.id, status=RunStatus.SUCCEEDED,
                        result_summary="Normal run.", estimated_cost=0.01,
                        token_accounting_mode="provider_reported")

        # Run 1: heuristic (normal worker path)
        r1 = repo.create_running_run(task_id=tids[1], model_name="test")
        repo.finish_run(run_id=r1.id, status=RunStatus.SUCCEEDED,
                        result_summary="Heuristic run.", estimated_cost=0.01,
                        token_accounting_mode="heuristic")

        session.commit()
    finally:
        session.close()

    diag = _request_json(
        client, "GET", f"/projects/{project_id}/cost-dashboard", 200,
    )
    fc = diag.get("fallback_contract", {})

    # Both are real worker outputs — NOT legacy missing
    assert fc.get("provider_reported_run_count") == 1
    assert fc.get("heuristic_run_count") == 1
    assert fc.get("missing_mode_run_count") == 0
    assert fc.get("legacy_missing_run_count") == 0, (
        f"legacy_missing should be 0 for normal worker runs, got {fc.get('legacy_missing_run_count')}"
    )
    assert fc.get("missing_source_breakdown", {}).get("legacy_or_replay", -1) == 0

    print("PASS test_provider_reported_not_in_legacy_missing")


def test_null_token_accounting_mode_is_legacy_missing(client: TestClient) -> None:
    """Runs with token_accounting_mode=NULL → counted as legacy_missing."""
    from app.core.db import SessionLocal
    from app.repositories.run_repository import RunRepository
    from app.repositories.task_repository import TaskRepository
    from app.domain.run import RunStatus

    project = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-06 Missing", "summary": "Missing mode test."},
    )
    project_id = project["id"]

    session = SessionLocal()
    try:
        repo = RunRepository(session)
        _request_json(client, "POST", "/tasks", 201,
                      {"title": "Task M", "project_id": project_id,
                       "input_summary": "Missing test."})
        tasks = TaskRepository(session).list_by_project_id(UUID(project_id))
        tid = tasks[0].id if tasks else None
        assert tid is not None

        # Run without token_accounting_mode (simulates legacy/pre-Day06 run)
        r = repo.create_running_run(task_id=tid, model_name="test")
        repo.finish_run(run_id=r.id, status=RunStatus.SUCCEEDED,
                        result_summary="Legacy run.", estimated_cost=0.01)
        # token_accounting_mode defaults to None
        session.commit()
    finally:
        session.close()

    diag = _request_json(
        client, "GET", f"/projects/{project_id}/cost-dashboard", 200,
    )
    fc = diag.get("fallback_contract", {})

    assert fc.get("missing_mode_run_count") == 1, (
        f"missing_mode_run_count should be 1, got {fc.get('missing_mode_run_count')}"
    )
    assert fc.get("legacy_missing_run_count") == 1, (
        f"legacy_missing_run_count should mirror missing_mode, got {fc.get('legacy_missing_run_count')}"
    )
    assert fc.get("missing_source_breakdown", {}).get("legacy_or_replay", -1) == 1
    assert fc.get("fallback_active") is True

    # missing_source_note must explain the boundary
    note = fc.get("missing_source_note", "")
    assert len(note) > 0, "missing_source_note must not be empty"
    assert "legacy" in note.lower() or "replay" in note.lower(), (
        f"missing_source_note must mention legacy/replay: {note}"
    )
    assert "normal worker" in note.lower() or "main chain" in note.lower(), (
        f"missing_source_note must explain normal worker is not the source: {note}"
    )

    print("PASS test_null_token_accounting_mode_is_legacy_missing")


def test_old_fields_preserved(client: TestClient) -> None:
    """Old fallback_contract and provider_cache fields are still present."""
    from app.core.db import SessionLocal
    from app.repositories.run_repository import RunRepository
    from app.repositories.task_repository import TaskRepository
    from app.domain.run import RunStatus

    project = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-06 Preserve", "summary": "Field preservation test."},
    )
    project_id = project["id"]

    session = SessionLocal()
    try:
        repo = RunRepository(session)
        for i in range(3):
            _request_json(client, "POST", "/tasks", 201,
                          {"title": f"Task P{i}", "project_id": project_id,
                           "input_summary": f"Test {i}."})
        tasks = TaskRepository(session).list_by_project_id(UUID(project_id))
        tids = [t.id for t in tasks]

        repo.finish_run(
            run_id=repo.create_running_run(task_id=tids[0], model_name="a").id,
            status=RunStatus.SUCCEEDED, result_summary="p", estimated_cost=0.01,
            token_accounting_mode="provider_reported",
            cache_source="provider_reported", cache_read_tokens=10,
        )
        repo.finish_run(
            run_id=repo.create_running_run(task_id=tids[1], model_name="b").id,
            status=RunStatus.SUCCEEDED, result_summary="h", estimated_cost=0.01,
            token_accounting_mode="heuristic",
            cache_source="not_reported",
        )
        repo.finish_run(
            run_id=repo.create_running_run(task_id=tids[2], model_name="c").id,
            status=RunStatus.SUCCEEDED, result_summary="m", estimated_cost=0.01,
        )
        session.commit()
    finally:
        session.close()

    diag = _request_json(
        client, "GET", f"/projects/{project_id}/cost-dashboard", 200,
    )

    # Old fallback_contract fields intact
    fc = diag.get("fallback_contract", {})
    assert "provider_reported_run_count" in fc
    assert "heuristic_run_count" in fc
    assert "missing_mode_run_count" in fc  # old field preserved
    assert "fallback_active" in fc
    assert "fallback_reason" in fc
    assert "legacy_missing_run_count" in fc  # new field
    assert "missing_source_note" in fc
    assert "missing_source_breakdown" in fc

    assert fc["provider_reported_run_count"] == 1
    assert fc["heuristic_run_count"] == 1
    assert fc["missing_mode_run_count"] == 1
    assert fc["legacy_missing_run_count"] == 1

    # BCL-05 provider_cache still intact
    pc = diag.get("provider_cache", {})
    assert "supported" in pc
    assert "reported_run_count" in pc
    assert "not_reported_run_count" in pc
    assert "missing_run_count" in pc
    assert "cache_hit_run_count" in pc
    assert pc.get("reported_run_count") == 1
    assert pc.get("not_reported_run_count") == 1
    assert pc.get("missing_run_count") == 1

    print("PASS test_old_fields_preserved")


# -- Harness -------------------------------------------------------------

if __name__ == "__main__":
    _prepare_env()

    from app.core.db import init_database
    from app.main import create_application

    init_database()
    app = create_application()
    client = TestClient(app)

    all_passed = True
    for fn in [
        test_provider_reported_not_in_legacy_missing,
        test_null_token_accounting_mode_is_legacy_missing,
        test_old_fields_preserved,
    ]:
        try:
            fn(client)
        except Exception as exc:
            print(f"FAIL {fn.__name__}: {exc}")
            import traceback
            traceback.print_exc()
            all_passed = False

    print()
    if all_passed:
        print("BCL-06 smoke: ALL PASSED")
    else:
        print("BCL-06 smoke: SOME FAILED")
        sys.exit(1)
