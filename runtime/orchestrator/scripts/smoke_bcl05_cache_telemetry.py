"""BCL-05 rework smoke: provider cache telemetry with full payload parsing.

Covers:
1.  _extract_usage Chat Completions cached_tokens → provider_reported + cache_hit.
2.  _extract_usage Chat Completions cached_tokens=0 → provider_reported, cache_hit=False.
3.  _extract_usage Responses input_tokens_details.cached_tokens → provider_reported.
4.  _extract_usage no cache fields → not_reported.
5.  _extract_usage compat top-level cache_read_tokens → provider_reported.
6.  ProviderUsageReceipt / TokenAccountingSnapshot / Run persist chain.
7.  Old run without cache → stable missing.
8.  Cost dashboard: reported / not_reported / missing split correctly.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from _smoke_runtime_env import prepare_runtime_data_dir

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v5-bcl05-cache-telemetry-rework-smoke"

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


# -- Direct _extract_usage tests (test the real parsing function) ---------

def test_extract_usage_chat_completions_cached_tokens() -> None:
    """Chat Completions prompt_tokens_details.cached_tokens=40 → provider_reported + cache_hit."""
    from app.services.openai_provider_executor_service import OpenAIProviderExecutorService

    payload = {
        "id": "chatcmpl-test",
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "prompt_tokens_details": {"cached_tokens": 40},
        },
    }
    usage = OpenAIProviderExecutorService._extract_usage(payload, api_family="chat_completions")
    assert usage["cache_read_tokens"] == 40
    assert usage["cache_hit"] == 1
    assert usage["cache_provider_reported"] is True
    print("PASS test_extract_usage_chat_completions_cached_tokens")


def test_extract_usage_chat_completions_cached_tokens_zero() -> None:
    """Chat Completions cached_tokens=0 → still provider_reported, cache_hit=False."""
    from app.services.openai_provider_executor_service import OpenAIProviderExecutorService

    payload = {
        "id": "chatcmpl-test-zero",
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "prompt_tokens_details": {"cached_tokens": 0},
        },
    }
    usage = OpenAIProviderExecutorService._extract_usage(payload, api_family="chat_completions")
    assert usage["cache_read_tokens"] == 0
    assert usage["cache_hit"] == 0
    assert usage["cache_provider_reported"] is True, (
        "cache_provider_reported must be True even when cached_tokens=0"
    )
    print("PASS test_extract_usage_chat_completions_cached_tokens_zero")


def test_extract_usage_responses_input_tokens_details() -> None:
    """Responses API input_tokens_details.cached_tokens=30 → provider_reported + cache_hit."""
    from app.services.openai_provider_executor_service import OpenAIProviderExecutorService

    payload = {
        "id": "resp-test",
        "usage": {
            "input_tokens": 200,
            "output_tokens": 80,
            "total_tokens": 280,
            "input_tokens_details": {"cached_tokens": 30},
        },
    }
    usage = OpenAIProviderExecutorService._extract_usage(payload, api_family="responses")
    assert usage["cache_read_tokens"] == 30
    assert usage["cache_hit"] == 1
    assert usage["cache_provider_reported"] is True
    # Responses uses input_tokens/output_tokens
    assert usage["prompt_tokens"] == 200
    assert usage["completion_tokens"] == 80
    print("PASS test_extract_usage_responses_input_tokens_details")


def test_extract_usage_no_cache_fields() -> None:
    """No cache fields in usage payload → not_reported."""
    from app.services.openai_provider_executor_service import OpenAIProviderExecutorService

    payload = {
        "id": "no-cache-test",
        "usage": {
            "prompt_tokens": 50,
            "completion_tokens": 30,
            "total_tokens": 80,
        },
    }
    usage = OpenAIProviderExecutorService._extract_usage(payload, api_family="chat_completions")
    assert usage["cache_read_tokens"] == 0
    assert usage["cache_hit"] == 0
    assert usage["cache_provider_reported"] is False
    print("PASS test_extract_usage_no_cache_fields")


def test_extract_usage_compat_top_level_cache_keys() -> None:
    """Compat gateway top-level cache_read_tokens / cache_write_tokens → provider_reported."""
    from app.services.openai_provider_executor_service import OpenAIProviderExecutorService

    payload = {
        "id": "compat-test",
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "cache_read_tokens": 25,
            "cache_write_tokens": 5,
        },
    }
    usage = OpenAIProviderExecutorService._extract_usage(payload, api_family="chat_completions")
    assert usage["cache_read_tokens"] == 25
    assert usage["cache_write_tokens"] == 5
    assert usage["cache_hit"] == 1
    assert usage["cache_provider_reported"] is True
    print("PASS test_extract_usage_compat_top_level_cache_keys")


# -- Receipt / snapshot / Run persist tests -------------------------------

def test_receipt_and_run_chain(client: TestClient) -> None:
    """Full chain: receipt → snapshot → run persist → retrieve."""
    from app.domain.prompt_contract import (
        ProviderUsageReceipt, ProviderReceiptSource, PromptTemplateRef,
    )
    from app.services.token_accounting_service import TokenAccountingService
    from app.core.db import SessionLocal
    from app.repositories.run_repository import RunRepository
    from app.domain.run import RunStatus

    receipt = ProviderUsageReceipt(
        provider_key="openai",
        model_name="gpt-4.1-mini",
        receipt_id="rcpt-chain",
        receipt_source=ProviderReceiptSource.REAL_PROVIDER,
        prompt_tokens=200, completion_tokens=80, total_tokens=280,
        estimated_cost_usd=0.02,
        pricing_source="openai.chat_completions.usage",
        cache_read_tokens=60, cache_write_tokens=5,
        cache_hit=True, cache_source="provider_reported",
    )

    svc = TokenAccountingService()
    snapshot = svc._build_provider_reported_snapshot(
        prompt_envelope=None, provider_usage_receipt=receipt,
    )
    assert snapshot.cache_source == "provider_reported"
    assert snapshot.cache_read_tokens == 60

    # Persist via Run
    project = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-05 Chain", "summary": "Chain test."},
    )
    task = _request_json(
        client, "POST", "/tasks", 201,
        {"title": "Chain Task", "project_id": project["id"],
         "input_summary": "Test."},
    )

    session = SessionLocal()
    try:
        repo = RunRepository(session)
        run = repo.create_running_run(task_id=UUID(task["id"]), model_name="test")
        finished = repo.finish_run(
            run_id=run.id, status=RunStatus.SUCCEEDED,
            result_summary="Chain test.",
            estimated_cost=0.02,
            cache_read_tokens=60, cache_write_tokens=5,
            cache_hit=True, cache_source="provider_reported",
        )
        assert finished.cache_source == "provider_reported"
        retrieved = repo.get_by_id(run.id)
        assert retrieved is not None
        assert retrieved.cache_source == "provider_reported"
    finally:
        session.close()
    print("PASS test_receipt_and_run_chain")


def test_old_run_missing_cache(client: TestClient) -> None:
    """Old run without cache fields → stable missing (None/0/False)."""
    from app.core.db import SessionLocal
    from app.repositories.run_repository import RunRepository
    from app.domain.run import RunStatus

    project = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-05 Old", "summary": "Old run test."},
    )
    task = _request_json(
        client, "POST", "/tasks", 201,
        {"title": "Old Task", "project_id": project["id"],
         "input_summary": "Test."},
    )
    session = SessionLocal()
    try:
        repo = RunRepository(session)
        run = repo.create_running_run(task_id=UUID(task["id"]), model_name="test")
        finished = repo.finish_run(
            run_id=run.id, status=RunStatus.SUCCEEDED,
            result_summary="Old run.", estimated_cost=0.01,
        )
        assert finished.cache_source is None
        assert finished.cache_read_tokens == 0
        assert finished.cache_hit is False
    finally:
        session.close()
    print("PASS test_old_run_missing_cache")


# -- Cost dashboard aggregation tests ------------------------------------

def test_cost_dashboard_provider_cache_split(client: TestClient) -> None:
    """provider_cache correctly splits reported / not_reported / missing."""
    from app.core.db import SessionLocal
    from app.repositories.run_repository import RunRepository
    from app.repositories.task_repository import TaskRepository
    from app.domain.run import RunStatus

    project = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-05 Dash", "summary": "Dashboard split test."},
    )
    project_id = project["id"]

    session = SessionLocal()
    try:
        repo = RunRepository(session)
        for i in range(4):
            _request_json(
                client, "POST", "/tasks", 201,
                {"title": f"Dash Task {i}", "project_id": project_id,
                 "input_summary": f"Test {i}."},
            )
        all_tasks = TaskRepository(session).list_by_project_id(UUID(project_id))
        tids = [t.id for t in all_tasks]

        # Run 0: provider_reported with cache hit
        r0 = repo.create_running_run(task_id=tids[0], model_name="hit")
        repo.finish_run(run_id=r0.id, status=RunStatus.SUCCEEDED,
                        result_summary="Hit", estimated_cost=0.01,
                        cache_read_tokens=40, cache_hit=True,
                        cache_source="provider_reported")

        # Run 1: provider_reported with cached_tokens=0 (no hit)
        r1 = repo.create_running_run(task_id=tids[1], model_name="reported-no-hit")
        repo.finish_run(run_id=r1.id, status=RunStatus.SUCCEEDED,
                        result_summary="No hit", estimated_cost=0.01,
                        cache_read_tokens=0, cache_hit=False,
                        cache_source="provider_reported")

        # Run 2: not_reported (explicit)
        r2 = repo.create_running_run(task_id=tids[2], model_name="not-rep")
        repo.finish_run(run_id=r2.id, status=RunStatus.SUCCEEDED,
                        result_summary="Not reported", estimated_cost=0.01,
                        cache_source="not_reported")

        # Run 3: no cache_source (missing)
        r3 = repo.create_running_run(task_id=tids[3], model_name="missing")
        repo.finish_run(run_id=r3.id, status=RunStatus.SUCCEEDED,
                        result_summary="Missing", estimated_cost=0.01)
        session.commit()
    finally:
        session.close()

    diag = _request_json(
        client, "GET", f"/projects/{project_id}/cost-dashboard", 200,
    )
    pc = diag.get("provider_cache", {})

    assert pc.get("supported") is True
    assert pc.get("reported_run_count") == 2, (
        f"Expected 2 reported, got {pc.get('reported_run_count')}"
    )
    assert pc.get("not_reported_run_count") == 1, (
        f"Expected 1 not_reported, got {pc.get('not_reported_run_count')}"
    )
    assert pc.get("missing_run_count") == 1, (
        f"Expected 1 missing, got {pc.get('missing_run_count')}"
    )
    assert pc.get("cache_hit_run_count") == 1, (
        f"Expected 1 cache_hit (only run 0), got {pc.get('cache_hit_run_count')}"
    )
    assert pc.get("cache_read_tokens") == 40, (
        f"Expected 40 cache_read_tokens, got {pc.get('cache_read_tokens')}"
    )

    bd = pc.get("cache_source_breakdown", {})
    assert bd.get("provider_reported") == 2
    assert bd.get("not_reported") == 1
    assert bd.get("missing") == 1

    # Old fields still intact
    fc = diag.get("fallback_contract", {})
    assert "provider_reported_run_count" in fc
    assert "heuristic_run_count" in fc
    assert "missing_mode_run_count" in fc

    # cache_summary still uses memory, not provider cache
    cs = diag.get("cache_summary", {})
    note = cs.get("cache_signal_note", "")
    assert "memory" in note.lower(), (
        "cache_signal_note should mention memory counts, not provider cache"
    )

    print("PASS test_cost_dashboard_provider_cache_split")


# -- Harness -------------------------------------------------------------

if __name__ == "__main__":
    _prepare_env()

    from app.core.db import init_database
    from app.main import create_application

    init_database()
    app = create_application()
    client = TestClient(app)

    all_passed = True

    # Direct _extract_usage tests (no client needed)
    direct_tests = [
        test_extract_usage_chat_completions_cached_tokens,
        test_extract_usage_chat_completions_cached_tokens_zero,
        test_extract_usage_responses_input_tokens_details,
        test_extract_usage_no_cache_fields,
        test_extract_usage_compat_top_level_cache_keys,
    ]
    for fn in direct_tests:
        try:
            fn()
        except Exception as exc:
            print(f"FAIL {fn.__name__}: {exc}")
            import traceback
            traceback.print_exc()
            all_passed = False

    # Client tests
    client_tests = [
        test_receipt_and_run_chain,
        test_old_run_missing_cache,
        test_cost_dashboard_provider_cache_split,
    ]
    for fn in client_tests:
        try:
            fn(client)
        except Exception as exc:
            print(f"FAIL {fn.__name__}: {exc}")
            import traceback
            traceback.print_exc()
            all_passed = False

    print()
    if all_passed:
        print("BCL-05 smoke (rework): ALL PASSED")
    else:
        print("BCL-05 smoke (rework): SOME FAILED")
        sys.exit(1)
