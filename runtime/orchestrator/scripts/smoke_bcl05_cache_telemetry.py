"""BCL-05 smoke: provider cache telemetry.

Covers:
1. ProviderUsageReceipt with cache fields → source=provider_reported.
2. ProviderUsageReceipt without cache fields → source=not_reported.
3. TokenAccountingSnapshot propagates cache from receipt.
4. Run persist + retrieval preserves cache fields.
5. Cost dashboard provider_cache aggregation is correct.
6. Old run without cache fields → stable missing.
7. Memory counts are NOT in provider_cache.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from _smoke_runtime_env import prepare_runtime_data_dir

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v5-bcl05-cache-telemetry-smoke"

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

def test_receipt_with_cache_fields_marks_provider_reported() -> None:
    """ProviderUsageReceipt with cache data sets cache_source=provider_reported."""
    from app.domain.prompt_contract import (
        ProviderUsageReceipt,
        ProviderReceiptSource,
    )

    receipt = ProviderUsageReceipt(
        provider_key="openai",
        model_name="gpt-4.1-mini",
        receipt_id="rcpt-cache-test-01",
        receipt_source=ProviderReceiptSource.REAL_PROVIDER,
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        estimated_cost_usd=0.01,
        pricing_source="openai.chat_completions.usage",
        cache_read_tokens=30,
        cache_write_tokens=0,
        cache_hit=True,
        cache_source="provider_reported",
    )
    assert receipt.cache_source == "provider_reported"
    assert receipt.cache_read_tokens == 30
    assert receipt.cache_hit is True
    assert receipt.cache_write_tokens == 0
    print("PASS test_receipt_with_cache_fields_marks_provider_reported")


def test_receipt_without_cache_fields_marks_not_reported() -> None:
    """ProviderUsageReceipt without cache data defaults to cache_source=not_reported."""
    from app.domain.prompt_contract import (
        ProviderUsageReceipt,
        ProviderReceiptSource,
    )

    receipt = ProviderUsageReceipt(
        provider_key="openai",
        model_name="gpt-4.1-mini",
        receipt_id="rcpt-no-cache-02",
        receipt_source=ProviderReceiptSource.REAL_PROVIDER,
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        estimated_cost_usd=0.01,
        pricing_source="openai.chat_completions.usage",
    )
    # Defaults should kick in
    assert receipt.cache_source == "not_reported"
    assert receipt.cache_read_tokens == 0
    assert receipt.cache_hit is False
    print("PASS test_receipt_without_cache_fields_marks_not_reported")


def test_token_accounting_propagates_cache() -> None:
    """TokenAccountingSnapshot carries cache fields from receipt."""
    from app.domain.prompt_contract import (
        ProviderUsageReceipt,
        ProviderReceiptSource,
        PromptTemplateRef,
    )
    from app.services.token_accounting_service import TokenAccountingService

    receipt = ProviderUsageReceipt(
        provider_key="openai",
        model_name="gpt-4.1-mini",
        receipt_id="rcpt-cache-test-03",
        receipt_source=ProviderReceiptSource.REAL_PROVIDER,
        prompt_tokens=200,
        completion_tokens=80,
        total_tokens=280,
        estimated_cost_usd=0.02,
        pricing_source="openai.chat_completions.usage",
        cache_read_tokens=50,
        cache_write_tokens=5,
        cache_hit=True,
        cache_source="provider_reported",
    )

    svc = TokenAccountingService()
    snapshot = svc._build_provider_reported_snapshot(
        prompt_envelope=None,
        provider_usage_receipt=receipt,
    )
    assert snapshot.cache_source == "provider_reported"
    assert snapshot.cache_read_tokens == 50
    assert snapshot.cache_write_tokens == 5
    assert snapshot.cache_hit is True
    print("PASS test_token_accounting_propagates_cache")


def test_run_persist_and_retrieve_cache_fields(client: TestClient) -> None:
    """Run persist + retrieve preserves cache fields via RunRepository."""
    from app.core.db import SessionLocal
    from app.repositories.run_repository import RunRepository
    from app.domain.run import RunStatus

    project = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-05 Cache Run", "summary": "Cache test run."},
    )
    project_id = project["id"]

    task = _request_json(
        client, "POST", "/tasks", 201,
        {"title": "Cache Task", "project_id": project_id,
         "input_summary": "Cache field test."},
    )

    session = SessionLocal()
    try:
        repo = RunRepository(session)
        run = repo.create_running_run(task_id=UUID(task["id"]), model_name="test")
        finished = repo.finish_run(
            run_id=run.id,
            status=RunStatus.SUCCEEDED,
            result_summary="Cache test run.",
            estimated_cost=0.01,
            cache_read_tokens=100,
            cache_write_tokens=10,
            cache_hit=True,
            cache_source="provider_reported",
        )
        assert finished.cache_source == "provider_reported"
        assert finished.cache_read_tokens == 100
        assert finished.cache_write_tokens == 10
        assert finished.cache_hit is True

        # Re-retrieve
        retrieved = repo.get_by_id(run.id)
        assert retrieved is not None
        assert retrieved.cache_source == "provider_reported"
        assert retrieved.cache_read_tokens == 100
    finally:
        session.close()
    print("PASS test_run_persist_and_retrieve_cache_fields")


def test_old_run_without_cache_stable_missing(client: TestClient) -> None:
    """Run without explicit cache fields → stable missing/defaults, no error."""
    from app.core.db import SessionLocal
    from app.repositories.run_repository import RunRepository
    from app.domain.run import RunStatus

    project = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-05 Old Run", "summary": "Old run test."},
    )
    project_id = project["id"]

    task = _request_json(
        client, "POST", "/tasks", 201,
        {"title": "Old Task", "project_id": project_id,
         "input_summary": "Old cache test."},
    )

    session = SessionLocal()
    try:
        repo = RunRepository(session)
        run = repo.create_running_run(task_id=UUID(task["id"]), model_name="test")
        # finish without cache fields
        finished = repo.finish_run(
            run_id=run.id,
            status=RunStatus.SUCCEEDED,
            result_summary="Old run without cache.",
            estimated_cost=0.01,
        )
        # Defaults
        assert finished.cache_source is None  # not set
        assert finished.cache_read_tokens == 0
        assert finished.cache_hit is False
    finally:
        session.close()
    print("PASS test_old_run_without_cache_stable_missing")


def test_cost_dashboard_provider_cache_aggregation(client: TestClient) -> None:
    """Cost dashboard provider_cache correctly aggregates cache telemetry."""
    from app.core.db import SessionLocal
    from app.repositories.run_repository import RunRepository
    from app.domain.run import RunStatus

    project = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-05 Dashboard", "summary": "Dashboard cache test."},
    )
    project_id = project["id"]

    # Create 3 runs with different cache states
    session = SessionLocal()
    try:
        repo = RunRepository(session)

        for i in range(3):
            task = _request_json(
                client, "POST", "/tasks", 201,
                {"title": f"Dash Task {i}", "project_id": project_id,
                 "input_summary": f"Test {i}."},
            )

        # Get all task IDs via repo
        from app.repositories.task_repository import TaskRepository
        all_tasks = TaskRepository(session).list_by_project_id(UUID(project_id))
        task_ids = [t.id for t in all_tasks]

        # Run 0: provider_reported with cache hit
        run0 = repo.create_running_run(task_id=task_ids[0], model_name="cache-hit")
        repo.finish_run(
            run_id=run0.id, status=RunStatus.SUCCEEDED,
            result_summary="Cache hit run.",
            estimated_cost=0.01,
            cache_read_tokens=40,
            cache_hit=True,
            cache_source="provider_reported",
        )

        # Run 1: provider_reported without cache hit
        run1 = repo.create_running_run(task_id=task_ids[1], model_name="no-cache")
        repo.finish_run(
            run_id=run1.id, status=RunStatus.SUCCEEDED,
            result_summary="No cache hit.",
            estimated_cost=0.01,
            cache_read_tokens=0,
            cache_hit=False,
            cache_source="not_reported",
        )

        # Run 2: missing (no cache_source)
        run2 = repo.create_running_run(task_id=task_ids[2], model_name="missing-cache")
        repo.finish_run(
            run_id=run2.id, status=RunStatus.SUCCEEDED,
            result_summary="Missing cache field.",
            estimated_cost=0.01,
        )
        session.commit()
    finally:
        session.close()

    # Query cost dashboard
    diag = _request_json(
        client, "GET", f"/projects/{project_id}/cost-dashboard", 200,
    )

    pc = diag.get("provider_cache", {})
    assert pc.get("supported") is True, (
        f"Expected supported=True (has provider_reported), got {pc}"
    )
    assert pc.get("reported_run_count") == 1, (
        f"Expected 1 reported_run, got {pc.get('reported_run_count')}"
    )
    assert pc.get("cache_hit_run_count") == 1, (
        f"Expected 1 cache_hit_run, got {pc.get('cache_hit_run_count')}"
    )
    assert pc.get("cache_read_tokens") == 40, (
        f"Expected 40 cache_read_tokens, got {pc.get('cache_read_tokens')}"
    )
    # not_reported + missing = 2
    assert pc.get("not_reported_run_count") == 2, (
        f"Expected 2 not_reported (1 not_reported + 1 missing), "
        f"got {pc.get('not_reported_run_count')}"
    )
    breakdown = pc.get("cache_source_breakdown", {})
    assert breakdown.get("provider_reported") == 1
    assert breakdown.get("not_reported") == 1
    assert breakdown.get("missing") == 1

    # cache_summary still uses memory counts (not provider cache)
    cs = diag.get("cache_summary", {})
    assert "cache_signal_note" in cs
    assert "memory" in str(cs.get("cache_signal_note", "")).lower(), (
        "cache_signal_note should mention memory (not provider cache)"
    )

    # Old fallback contract still exists
    fc = diag.get("fallback_contract", {})
    assert "provider_reported_run_count" in fc
    assert "heuristic_run_count" in fc
    assert "missing_mode_run_count" in fc
    assert "fallback_active" in fc

    print("PASS test_cost_dashboard_provider_cache_aggregation")


# -- Harness -------------------------------------------------------------

if __name__ == "__main__":
    _prepare_env()

    from app.core.db import init_database
    from app.main import create_application

    init_database()
    app = create_application()
    client = TestClient(app)

    all_passed = True
    # Tests that don't need client
    no_client_tests = [
        test_receipt_with_cache_fields_marks_provider_reported,
        test_receipt_without_cache_fields_marks_not_reported,
        test_token_accounting_propagates_cache,
    ]
    # Tests that need client
    client_tests = [
        test_run_persist_and_retrieve_cache_fields,
        test_old_run_without_cache_stable_missing,
        test_cost_dashboard_provider_cache_aggregation,
    ]

    for fn in no_client_tests:
        name = fn.__name__
        try:
            fn()
        except Exception as exc:
            print(f"FAIL {name}: {exc}")
            import traceback
            traceback.print_exc()
            all_passed = False

    for fn in client_tests:
        name = fn.__name__
        try:
            fn(client)
        except Exception as exc:
            print(f"FAIL {name}: {exc}")
            import traceback
            traceback.print_exc()
            all_passed = False

    print()
    if all_passed:
        print("BCL-05 smoke: ALL PASSED")
    else:
        print("BCL-05 smoke: SOME FAILED")
        sys.exit(1)
