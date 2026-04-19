"""Day10 smoke for memory-governance control-surface contracts and actions."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from fastapi.testclient import TestClient

from _smoke_runtime_env import prepare_runtime_data_dir

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v5-day10-memory-governance-smoke"

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
    os.environ["DAILY_BUDGET_USD"] = "8.00"
    os.environ["SESSION_BUDGET_USD"] = "8.00"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"
    return runtime_data_dir


def main() -> None:
    runtime_data_dir = _prepare_env()

    from app.main import create_application

    app = create_application()

    with TestClient(app) as client:
        project = _request_json(
            client,
            "POST",
            "/projects",
            201,
            {
                "name": "Day10 Memory Governance Smoke",
                "summary": "Validate governance state, action, and run-once echo contracts.",
                "stage": "execution",
            },
        )
        project_id = project["id"]

        empty_state = _request_json(
            client,
            "GET",
            f"/projects/{project_id}/memory/governance",
            200,
        )
        _assert(empty_state["checkpoint_count"] == 0, "empty project should start with 0 checkpoints")
        _assert(
            empty_state["latest_run_id"] is None,
            "empty project should expose latest_run_id=null before execution",
        )

        empty_rehydrate = _request_json(
            client,
            "POST",
            f"/projects/{project_id}/memory/governance/rehydrate",
            200,
        )
        _assert(
            empty_rehydrate["rehydrated"] is False,
            "rehydrate without checkpoints should return rehydrated=false",
        )

        compact_response = client.post(
            f"/projects/{project_id}/memory/governance/compact",
            json={"target_chars": 900},
        )
        _assert(
            compact_response.status_code == 404,
            "compact without checkpoints should return 404",
        )
        empty_compact = compact_response.json()

        empty_reset = _request_json(
            client,
            "POST",
            f"/projects/{project_id}/memory/governance/reset",
            200,
        )
        _assert(
            empty_reset["reset_performed"] is True,
            "reset should succeed even when governance artifacts are empty",
        )

        task = _request_json(
            client,
            "POST",
            "/tasks",
            201,
            {
                "project_id": project_id,
                "title": "Create checkpoint via one worker cycle",
                "input_summary": "simulate: produce a concise memory governance smoke artifact",
                "priority": "high",
                "acceptance_criteria": [
                    "Worker returns governance checkpoint metadata",
                ],
            },
        )
        task_id = task["id"]

        run_once = _request_json(
            client,
            "POST",
            f"/workers/run-once?project_id={project_id}",
            200,
        )
        _assert(run_once["claimed"] is True, "worker should claim the smoke task")
        checkpoint_id = run_once["memory_governance_checkpoint_id"]
        run_id = run_once["run_id"]
        _assert(checkpoint_id, "worker response should expose checkpoint_id")
        _assert(run_id, "worker response should expose run_id")
        _assert(
            run_once["memory_governance_pressure_level"] is not None,
            "worker response should expose governance pressure level",
        )
        _assert(
            run_once["memory_governance_usage_ratio"] is not None,
            "worker response should expose governance usage ratio",
        )

        state_after_run = _request_json(
            client,
            "GET",
            f"/projects/{project_id}/memory/governance",
            200,
        )
        _assert(state_after_run["checkpoint_count"] == 1, "smoke run should persist one checkpoint")
        _assert(
            state_after_run["latest_checkpoint_id"] == checkpoint_id,
            "governance state should expose worker checkpoint_id",
        )
        _assert(
            state_after_run["latest_task_id"] == task_id,
            "governance state should expose latest_task_id from executed task",
        )
        _assert(
            state_after_run["latest_run_id"] == run_id,
            "governance state should expose latest_run_id from executed run",
        )

        compact_after_run = _request_json(
            client,
            "POST",
            f"/projects/{project_id}/memory/governance/compact",
            200,
            {"target_chars": 500},
        )
        _assert(
            compact_after_run["checkpoint_id"] == checkpoint_id,
            "compact action should target the latest checkpoint",
        )

        rehydrate_after_run = _request_json(
            client,
            "POST",
            f"/projects/{project_id}/memory/governance/rehydrate?task_id={task_id}",
            200,
        )
        _assert(
            rehydrate_after_run["rehydrated"] is True,
            "rehydrate should succeed after checkpoint creation",
        )
        _assert(
            rehydrate_after_run["used_checkpoint_id"] == checkpoint_id,
            "rehydrate should report the checkpoint it consumed",
        )

    print(
        json.dumps(
            {
                "runtime_data_dir": str(SMOKE_RUNTIME_DATA_DIR),
                "runtime_data_dir_effective": str(runtime_data_dir),
                "project_id": project_id,
                "task_id": task_id,
                "run_id": run_id,
                "checkpoint_id": checkpoint_id,
                "empty_state": empty_state,
                "empty_rehydrate": empty_rehydrate,
                "empty_compact": empty_compact,
                "empty_reset": empty_reset,
                "run_once": run_once,
                "state_after_run": state_after_run,
                "compact_after_run": compact_after_run,
                "rehydrate_after_run": rehydrate_after_run,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
