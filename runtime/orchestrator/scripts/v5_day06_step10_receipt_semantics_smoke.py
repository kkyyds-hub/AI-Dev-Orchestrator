"""Day06 Step10 smoke for unified provider / non-provider receipt semantics."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from uuid import UUID

from fastapi.testclient import TestClient

from _smoke_runtime_env import prepare_runtime_data_dir

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "day06-step10-receipt-semantics"

if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


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
    return response.json()


def _prepare_env() -> Path:
    runtime_data_dir = prepare_runtime_data_dir(SMOKE_RUNTIME_DATA_DIR)
    os.environ["DAILY_BUDGET_USD"] = "0.10"
    os.environ["SESSION_BUDGET_USD"] = "0.20"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"
    return runtime_data_dir


def _load_run(run_repository, run_id: str):
    run = run_repository.get_by_id(UUID(run_id))
    _assert(run is not None, f"run was not persisted: {run_id}")
    return run


def main() -> None:
    runtime_data_dir = _prepare_env()

    from app.core.db import SessionLocal
    from app.main import create_application
    from app.repositories.run_repository import RunRepository

    app = create_application()

    with TestClient(app) as client:
        provider_task = _request_json(
            client,
            "POST",
            "/tasks",
            201,
            {
                "title": "day06-step10-provider-mock",
                "input_summary": "Unify receipt semantics on provider path.",
                "priority": "high",
            },
        )
        provider_result = _request_json(client, "POST", "/workers/run-once", 200)

        shell_task = _request_json(
            client,
            "POST",
            "/tasks",
            201,
            {
                "title": "day06-step10-shell",
                "input_summary": "shell: Write-Output 'day06-step10-shell'",
                "priority": "normal",
            },
        )
        shell_result = _request_json(client, "POST", "/workers/run-once", 200)

        simulate_task = _request_json(
            client,
            "POST",
            "/tasks",
            201,
            {
                "title": "day06-step10-simulate",
                "input_summary": "simulate: keep day06-step10 simulate path stable",
                "priority": "normal",
            },
        )
        simulate_result = _request_json(client, "POST", "/workers/run-once", 200)

    with SessionLocal() as session:
        run_repository = RunRepository(session)
        provider_run = _load_run(run_repository, str(provider_result["run_id"]))
        shell_run = _load_run(run_repository, str(shell_result["run_id"]))
        simulate_run = _load_run(run_repository, str(simulate_result["run_id"]))

    _assert(
        provider_result["execution_mode"] == "provider_mock",
        "provider_mock path was broken",
    )
    _assert(provider_run.provider_key == "openai", "provider path should persist provider_key")
    _assert(
        provider_run.token_accounting_mode == "provider_reported",
        "provider path should persist provider_reported accounting mode",
    )
    _assert(
        bool(provider_run.provider_receipt_id),
        "provider path should persist provider_receipt_id",
    )
    _assert(
        provider_run.token_pricing_source == "mock_provider.receipt.v1",
        "provider path should keep mock receipt pricing source",
    )

    _assert(shell_result["execution_mode"] == "shell", "shell path was broken")
    _assert(shell_run.provider_key is None, "shell path should not persist provider_key")
    _assert(
        shell_run.token_accounting_mode == "heuristic",
        "shell path should stay on heuristic accounting",
    )
    _assert(
        shell_run.provider_receipt_id is None,
        "shell path should not persist provider_receipt_id",
    )
    _assert(
        shell_run.token_pricing_source == "heuristic.shell.char_count.v1",
        "shell path should persist shell heuristic pricing source",
    )

    _assert(simulate_result["execution_mode"] == "simulate", "simulate path was broken")
    _assert(
        simulate_run.provider_key is None,
        "simulate path should not persist provider_key",
    )
    _assert(
        simulate_run.token_accounting_mode == "heuristic",
        "simulate path should stay on heuristic accounting",
    )
    _assert(
        simulate_run.provider_receipt_id is None,
        "simulate path should not persist provider_receipt_id",
    )
    _assert(
        simulate_run.token_pricing_source == "heuristic.simulate.char_count.v1",
        "simulate path should persist simulate heuristic pricing source",
    )

    print(
        json.dumps(
            {
                "runtime_data_dir": str(SMOKE_RUNTIME_DATA_DIR),
                "runtime_data_dir_effective": str(runtime_data_dir),
                "provider_task_id": provider_task["id"],
                "provider_run_id": provider_result["run_id"],
                "provider_run_record": {
                    "provider_key": provider_run.provider_key,
                    "token_accounting_mode": provider_run.token_accounting_mode,
                    "provider_receipt_id": provider_run.provider_receipt_id,
                    "token_pricing_source": provider_run.token_pricing_source,
                },
                "shell_task_id": shell_task["id"],
                "shell_run_id": shell_result["run_id"],
                "shell_run_record": {
                    "provider_key": shell_run.provider_key,
                    "token_accounting_mode": shell_run.token_accounting_mode,
                    "provider_receipt_id": shell_run.provider_receipt_id,
                    "token_pricing_source": shell_run.token_pricing_source,
                },
                "simulate_task_id": simulate_task["id"],
                "simulate_run_id": simulate_result["run_id"],
                "simulate_run_record": {
                    "provider_key": simulate_run.provider_key,
                    "token_accounting_mode": simulate_run.token_accounting_mode,
                    "provider_receipt_id": simulate_run.provider_receipt_id,
                    "token_pricing_source": simulate_run.token_pricing_source,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
