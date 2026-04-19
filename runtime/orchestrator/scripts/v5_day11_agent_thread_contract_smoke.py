"""Day11 smoke for agent-thread backend contracts used by Day12."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from fastapi.testclient import TestClient

from _smoke_runtime_env import prepare_runtime_data_dir

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v5-day11-agent-thread-smoke"

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
) -> dict[str, object] | list[object]:
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
                "name": "Day11 Agent Thread Smoke",
                "summary": "Validate session, timeline, and review-rework contracts.",
                "stage": "execution",
            },
        )
        project_id = project["id"]

        _request_json(
            client,
            "POST",
            "/tasks",
            201,
            {
                "project_id": project_id,
                "title": "Day11 success path",
                "input_summary": "simulate: produce a success artifact",
                "priority": "high",
                "acceptance_criteria": ["worker returns an agent session"],
            },
        )
        success_run = _request_json(
            client,
            "POST",
            f"/workers/run-once?project_id={project_id}",
            200,
        )
        success_session_id = success_run["agent_session_id"]
        _assert(success_session_id is not None, "success path should return agent_session_id")

        success_sessions = _request_json(
            client,
            "GET",
            f"/agent-threads/projects/{project_id}/sessions",
            200,
        )
        success_timeline = _request_json(
            client,
            "GET",
            f"/agent-threads/projects/{project_id}/timeline?session_id={success_session_id}",
            200,
        )
        success_interventions = _request_json(
            client,
            "GET",
            f"/agent-threads/projects/{project_id}/interventions?session_id={success_session_id}",
            200,
        )

        success_events = [item["event_type"] for item in success_timeline["messages"]]
        _assert(
            success_events
            == [
                "session_started",
                "context_recovery_ready",
                "execution_started",
                "execution_finished",
                "review_passed",
                "session_finalized",
            ],
            f"unexpected success timeline events: {success_events}",
        )
        _assert(
            success_run["agent_session_status"] == "completed",
            "success path should finalize as completed",
        )
        _assert(
            success_run["agent_review_status"] == "review_passed",
            "success path should finalize with review_passed",
        )

        _request_json(
            client,
            "POST",
            "/tasks",
            201,
            {
                "project_id": project_id,
                "title": "Day11 failure path",
                "input_summary": "simulate: produce a failure artifact\nverify: exit 1",
                "priority": "high",
                "acceptance_criteria": ["worker triggers review-rework"],
            },
        )
        failure_run = _request_json(
            client,
            "POST",
            f"/workers/run-once?project_id={project_id}",
            200,
        )
        failure_session_id = failure_run["agent_session_id"]
        _assert(failure_session_id is not None, "failure path should return agent_session_id")

        failure_sessions = _request_json(
            client,
            "GET",
            f"/agent-threads/projects/{project_id}/sessions",
            200,
        )
        failure_timeline = _request_json(
            client,
            "GET",
            f"/agent-threads/projects/{project_id}/timeline?session_id={failure_session_id}",
            200,
        )
        failure_interventions = _request_json(
            client,
            "GET",
            f"/agent-threads/projects/{project_id}/interventions?session_id={failure_session_id}",
            200,
        )

        failure_events = [item["event_type"] for item in failure_timeline["messages"]]
        _assert(
            failure_events
            == [
                "session_started",
                "context_recovery_ready",
                "execution_started",
                "execution_finished",
                "review_required",
                "rework_requested",
                "boss_note_event",
                "session_finalized",
            ],
            f"unexpected failure timeline events: {failure_events}",
        )
        _assert(
            [item["event_type"] for item in failure_interventions["items"]]
            == ["boss_note_event", "rework_requested", "review_required"],
            "failure intervention feed should return newest-first review/rework/note events",
        )

        latest_failure_session = next(
            item for item in failure_sessions if item["session_id"] == failure_session_id
        )
        _assert(
            latest_failure_session["latest_intervention_type"] == "boss_note",
            "failure session should preserve latest_intervention_type after finalization",
        )
        _assert(
            latest_failure_session["latest_note_event_type"] == "quality_gate_blocked",
            "failure session should preserve latest_note_event_type after finalization",
        )
        _assert(
            failure_run["agent_session_status"] == "failed",
            "failure path should finalize as failed when verification blocks completion",
        )
        _assert(
            failure_run["agent_review_status"] == "rework_required",
            "failure path should finalize with rework_required",
        )

    print(
        json.dumps(
            {
                "runtime_data_dir": str(SMOKE_RUNTIME_DATA_DIR),
                "runtime_data_dir_effective": str(runtime_data_dir),
                "project_id": project_id,
                "success_run": success_run,
                "success_sessions": success_sessions,
                "success_timeline": success_timeline,
                "success_interventions": success_interventions,
                "failure_run": failure_run,
                "failure_sessions": failure_sessions,
                "failure_timeline": failure_timeline,
                "failure_interventions": failure_interventions,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
