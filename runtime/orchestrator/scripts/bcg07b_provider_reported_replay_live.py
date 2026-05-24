"""BCG-07B live evidence: replay an existing provider-reported Worker run.

This script intentionally reuses the BCG-05B real provider run captured in the
local runtime database/log store.  It does not create tasks, does not call the
Worker, and does not use mock/simulate as a substitute for provider execution.

Expected evidence run:
- project_id: 423367da-966b-4c2e-b8c8-a4ff5f7f2377
- session_id: 1177d06d-1c71-4e17-979a-855645ea87d8
- plan_version_id: 8b906cf9-b7c0-49b3-b7e7-1d7a918ad956
- task_id: db204e31-f244-4f9b-a469-abcc5e0b873f
- run_id: 834b38aa-3669-4121-9424-3aa4999cad2e
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from fastapi.testclient import TestClient

ORCHESTRATOR_ROOT = Path(__file__).resolve().parents[1]
if str(ORCHESTRATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_ROOT))

from app.core.config import settings
from app.main import app


PROJECT_ID = "423367da-966b-4c2e-b8c8-a4ff5f7f2377"
SESSION_ID = "1177d06d-1c71-4e17-979a-855645ea87d8"
PLAN_VERSION_ID = "8b906cf9-b7c0-49b3-b7e7-1d7a918ad956"
TASK_ID = "db204e31-f244-4f9b-a469-abcc5e0b873f"
RUN_ID = "834b38aa-3669-4121-9424-3aa4999cad2e"

EXPECTED_PROVIDER_KEY = "deepseek"
EXPECTED_MODEL_NAME = "deepseek-v4-pro"
EXPECTED_EXECUTION_MODE = "provider_openai"
EXPECTED_TOKEN_ACCOUNTING_MODE = "provider_reported"
EXPECTED_RECEIPT_ID = "3d8bf6e7-fdfd-43db-bd9a-3abee685521d"
EXPECTED_LOG_PATH = (
    "logs/task-runs/db204e31-f244-4f9b-a469-abcc5e0b873f/"
    "834b38aa-3669-4121-9424-3aa4999cad2e.jsonl"
)


def _assert(condition: bool, message: str) -> None:
    """Raise a concise assertion error for smoke-script failures."""

    if not condition:
        raise AssertionError(message)


def _request_json(client: TestClient, path: str) -> Any:
    """GET one API path and return JSON, failing loudly on non-200 responses."""

    response = client.get(path)
    _assert(response.status_code == 200, f"{path} failed: {response.status_code}")
    return response.json()


def _event_by_name(events: list[dict[str, Any]], event_name: str) -> dict[str, Any]:
    """Return the first structured log event by name."""

    for event in events:
        if event.get("event") == event_name:
            return event
    raise AssertionError(f"Missing log event: {event_name}")


def main() -> None:
    """Replay the BCG-05B provider-reported run through read-only APIs."""

    log_file = settings.runtime_data_dir / Path(EXPECTED_LOG_PATH)
    _assert(log_file.exists(), f"Expected JSONL log file does not exist: {log_file}")

    with TestClient(app) as client:
        session_payload = _request_json(
            client,
            f"/project-director/sessions/{SESSION_ID}",
        )
        plan_payload = _request_json(
            client,
            f"/project-director/plan-versions/{PLAN_VERSION_ID}",
        )
        created_tasks_payload = _request_json(
            client,
            f"/project-director/plan-versions/{PLAN_VERSION_ID}/created-tasks",
        )
        task_runs_payload = _request_json(client, f"/tasks/{TASK_ID}/runs")
        logs_payload = _request_json(client, f"/runs/{RUN_ID}/logs?limit=200")
        trace_payload = _request_json(client, f"/runs/{RUN_ID}/decision-trace")
        history_payload = _request_json(client, f"/tasks/{TASK_ID}/decision-history")

    _assert(session_payload["id"] == SESSION_ID, "Session ID mismatch.")
    _assert(session_payload["project_id"] == PROJECT_ID, "Session project mismatch.")
    _assert(session_payload["status"] == "confirmed", "Session is not confirmed.")
    _assert(plan_payload["id"] == PLAN_VERSION_ID, "Plan version ID mismatch.")
    _assert(plan_payload["session_id"] == SESSION_ID, "Plan session mismatch.")
    _assert(plan_payload["project_id"] == PROJECT_ID, "Plan project mismatch.")
    _assert(plan_payload["status"] == "confirmed", "Plan version is not confirmed.")

    created_task_ids = list(created_tasks_payload["created_task_ids"])
    _assert(TASK_ID in created_task_ids, "Expected BCG-05B task was not created by plan.")

    matching_runs = [item for item in task_runs_payload if item["id"] == RUN_ID]
    _assert(len(matching_runs) == 1, "Expected exactly one matching run in task runs.")
    run = matching_runs[0]
    _assert(run["status"] == "succeeded", "Provider run did not succeed.")
    _assert(run["provider_key"] == EXPECTED_PROVIDER_KEY, "provider_key mismatch.")
    _assert(run["model_name"] == EXPECTED_MODEL_NAME, "model_name mismatch.")
    _assert(
        run["token_accounting_mode"] == EXPECTED_TOKEN_ACCOUNTING_MODE,
        "token_accounting_mode mismatch.",
    )
    _assert(run["provider_receipt_id"] == EXPECTED_RECEIPT_ID, "receipt mismatch.")
    _assert(run["prompt_tokens"] == 380, "prompt_tokens mismatch.")
    _assert(run["completion_tokens"] == 66, "completion_tokens mismatch.")
    _assert(run["total_tokens"] == 446, "total_tokens mismatch.")
    _assert(run["estimated_cost"] == 0.000768, "estimated_cost mismatch.")
    _assert(run["log_path"] == EXPECTED_LOG_PATH, "log_path mismatch.")
    _assert(run["quality_gate_passed"] is True, "quality gate did not pass.")

    events = logs_payload["events"]
    event_names = [event["event"] for event in events]
    for expected_event in [
        "task_routed",
        "role_handoff",
        "run_claimed",
        "context_built",
        "execution_plan_ready",
        "prompt_contract_built",
        "execution_finished",
        "verification_finished",
        "token_accounting_ready",
        "cost_estimated",
        "run_finalized",
    ]:
        _assert(expected_event in event_names, f"Missing replay log event: {expected_event}")

    execution_event = _event_by_name(events, "execution_finished")
    execution_data = execution_event["data"]
    _assert(execution_data["mode"] == EXPECTED_EXECUTION_MODE, "execution mode mismatch.")
    _assert(
        execution_data["actual_execution_mode"] == EXPECTED_EXECUTION_MODE,
        "actual execution mode mismatch.",
    )
    _assert(execution_data["requested_provider_key"] == EXPECTED_PROVIDER_KEY, "provider mismatch.")
    _assert(execution_data["fallback_applied"] is False, "provider run used fallback.")
    _assert("provider execution succeeded" in execution_event["message"], "execution summary mismatch.")

    token_event = _event_by_name(events, "token_accounting_ready")
    token_data = token_event["data"]
    _assert(
        token_data["accounting_mode"] == EXPECTED_TOKEN_ACCOUNTING_MODE,
        "log token accounting mode mismatch.",
    )
    _assert(token_data["provider_key"] == EXPECTED_PROVIDER_KEY, "log provider mismatch.")
    _assert(token_data["model_name"] == EXPECTED_MODEL_NAME, "log model mismatch.")
    _assert(token_data["provider_receipt_id"] == EXPECTED_RECEIPT_ID, "log receipt mismatch.")
    _assert(token_data["prompt_tokens"] == 380, "log prompt tokens mismatch.")
    _assert(token_data["completion_tokens"] == 66, "log completion tokens mismatch.")
    _assert(token_data["total_tokens"] == 446, "log total tokens mismatch.")
    _assert(token_data["estimated_cost_usd"] == 0.000768, "log cost mismatch.")

    trace_events = [item["event"] for item in trace_payload["trace_items"]]
    trace_stages = [item["stage"] for item in trace_payload["trace_items"]]
    _assert(trace_payload["run_id"] == RUN_ID, "trace run_id mismatch.")
    _assert(trace_payload["task_id"] == TASK_ID, "trace task_id mismatch.")
    _assert(trace_payload["run_status"] == "succeeded", "trace run_status mismatch.")
    _assert(trace_payload["quality_gate_passed"] is True, "trace quality gate mismatch.")
    for expected_event in [
        "execution_finished",
        "token_accounting_ready",
        "cost_estimated",
        "run_finalized",
    ]:
        _assert(expected_event in trace_events, f"trace missing event: {expected_event}")
    for expected_stage in ["execution", "verification", "cost", "finalize"]:
        _assert(expected_stage in trace_stages, f"trace missing stage: {expected_stage}")

    _assert(len(history_payload) == 1, "Expected one task decision-history item.")
    history_item = history_payload[0]
    _assert(history_item["run_id"] == RUN_ID, "history run_id mismatch.")
    _assert(history_item["status"] == "succeeded", "history status mismatch.")
    _assert(history_item["quality_gate_passed"] is True, "history quality gate mismatch.")
    _assert(history_item["failure_category"] is None, "history failure category mismatch.")
    _assert(
        history_item["headline"] == "Task and run were finalized.",
        "history headline did not use core run-finalized evidence.",
    )

    report = {
        "phase": "BCG-07B Provider-Reported Run Evidence Replay",
        "reused_existing_bcg05b_run": True,
        "project_id": PROJECT_ID,
        "session_id": SESSION_ID,
        "plan_version_id": PLAN_VERSION_ID,
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "provider_key": run["provider_key"],
        "model_name": run["model_name"],
        "execution_mode": execution_data["mode"],
        "actual_execution_mode": execution_data["actual_execution_mode"],
        "fallback_applied": execution_data["fallback_applied"],
        "token_accounting_mode": run["token_accounting_mode"],
        "provider_receipt_id": run["provider_receipt_id"],
        "prompt_tokens": run["prompt_tokens"],
        "completion_tokens": run["completion_tokens"],
        "total_tokens": run["total_tokens"],
        "estimated_cost": run["estimated_cost"],
        "log_path": run["log_path"],
        "log_event_count": len(events),
        "log_events": event_names,
        "trace_item_count": len(trace_payload["trace_items"]),
        "trace_events": trace_events,
        "trace_stages": trace_stages,
        "decision_history_items": len(history_payload),
        "decision_history_headline": history_item["headline"],
        "runtime_data_dir": str(settings.runtime_data_dir),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
