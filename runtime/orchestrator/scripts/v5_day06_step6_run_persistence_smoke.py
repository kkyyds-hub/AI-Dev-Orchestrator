"""Day06 Step6 smoke for persisted prompt/token run fields."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
from uuid import UUID

from fastapi.testclient import TestClient


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "day06-step6-run-persistence"

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


def _prepare_env() -> None:
    if SMOKE_RUNTIME_DATA_DIR.exists():
        shutil.rmtree(SMOKE_RUNTIME_DATA_DIR)
    SMOKE_RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)

    os.environ["RUNTIME_DATA_DIR"] = str(SMOKE_RUNTIME_DATA_DIR)
    os.environ["DAILY_BUDGET_USD"] = "0.10"
    os.environ["SESSION_BUDGET_USD"] = "0.20"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"


def main() -> None:
    _prepare_env()

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
                "title": "day06-step6-provider",
                "input_summary": "Persist prompt/token fields into run record.",
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
                "title": "day06-step6-shell",
                "input_summary": "shell: Write-Output 'day06-step6-shell'",
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
                "title": "day06-step6-simulate",
                "input_summary": "simulate: keep day06-step8 simulate path",
                "priority": "normal",
            },
        )
        simulate_result = _request_json(client, "POST", "/workers/run-once", 200)

    with SessionLocal() as session:
        run_repository = RunRepository(session)
        persisted_provider_run = run_repository.get_by_id(UUID(str(provider_result["run_id"])))
        persisted_shell_run = run_repository.get_by_id(UUID(str(shell_result["run_id"])))

    _assert(persisted_provider_run is not None, "provider run was not persisted")
    _assert(persisted_shell_run is not None, "shell run was not persisted")
    _assert(provider_result["execution_mode"] == "provider_mock", "provider mock path was broken")
    _assert(provider_result["provider_key"] == "openai", "provider_key was not exposed on worker response")
    _assert(
        persisted_provider_run.prompt_template_key == "task_execution.default",
        "prompt_template_key was not persisted on run",
    )
    _assert(
        persisted_provider_run.prompt_template_version == "day06.step1",
        "prompt_template_version was not persisted on run",
    )
    _assert(persisted_provider_run.prompt_char_count > 0, "prompt_char_count was not persisted")
    _assert(
        persisted_provider_run.token_accounting_mode == "provider_reported",
        "token_accounting_mode was not upgraded to provider_reported",
    )
    _assert(persisted_provider_run.total_tokens > 0, "total_tokens was not persisted")
    _assert(
        persisted_provider_run.token_pricing_source == "mock_provider.receipt.v1",
        "token_pricing_source was not upgraded to receipt style",
    )
    _assert(
        bool(persisted_provider_run.provider_receipt_id),
        "provider_receipt_id was not persisted",
    )
    _assert(shell_result["execution_mode"] == "shell", "shell explicit prefix was broken")
    _assert(
        persisted_shell_run.prompt_template_key == "task_execution.default",
        "shell path should keep the built prompt contract key readable",
    )
    _assert(
        persisted_shell_run.total_tokens > 0,
        "shell path should keep token accounting totals readable",
    )
    _assert(simulate_result["execution_mode"] == "simulate", "simulate explicit prefix was broken")

    print(
        json.dumps(
            {
                "runtime_data_dir": str(SMOKE_RUNTIME_DATA_DIR),
                "provider_task_id": provider_task["id"],
                "provider_run_id": provider_result["run_id"],
                "provider_run_record": {
                    "provider_key": persisted_provider_run.provider_key,
                    "model_name": persisted_provider_run.model_name,
                    "prompt_template_key": persisted_provider_run.prompt_template_key,
                    "prompt_template_version": persisted_provider_run.prompt_template_version,
                    "prompt_char_count": persisted_provider_run.prompt_char_count,
                    "token_accounting_mode": persisted_provider_run.token_accounting_mode,
                    "provider_receipt_id": persisted_provider_run.provider_receipt_id,
                    "total_tokens": persisted_provider_run.total_tokens,
                    "token_pricing_source": persisted_provider_run.token_pricing_source,
                    "prompt_tokens": persisted_provider_run.prompt_tokens,
                    "completion_tokens": persisted_provider_run.completion_tokens,
                    "estimated_cost": persisted_provider_run.estimated_cost,
                },
                "shell_task_id": shell_task["id"],
                "shell_run_id": shell_result["run_id"],
                "shell_run_record": {
                    "provider_key": persisted_shell_run.provider_key,
                    "prompt_template_key": persisted_shell_run.prompt_template_key,
                    "total_tokens": persisted_shell_run.total_tokens,
                    "prompt_tokens": persisted_shell_run.prompt_tokens,
                    "completion_tokens": persisted_shell_run.completion_tokens,
                },
                "simulate_task_id": simulate_task["id"],
                "simulate_run_id": simulate_result["run_id"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
