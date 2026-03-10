"""V2-A Day5 smoke checks for task state-machine stability.

This script runs a minimal API-level smoke test against an isolated runtime
data directory and writes a JSON report under the Day5 plan folder.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
from typing import Any, Iterator

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_ROOT = REPO_ROOT / "runtime" / "orchestrator"
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "day5-state-machine-smoke"
REPORT_PATH = (
    REPO_ROOT
    / "docs"
    / "90-每日计划"
    / "2026-03-28-V2A状态机验证与文档收口"
    / "artifacts"
    / "v2a_day5_state_machine_smoke_report.json"
)


@dataclass(slots=True)
class SmokeCase:
    """One smoke-check outcome."""

    case_id: str
    title: str
    passed: bool
    details: dict[str, Any]


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _request_json(
    client: TestClient,
    method: str,
    path: str,
    *,
    expected_status: int,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = client.request(method=method, url=path, json=json_body)
    if response.status_code != expected_status:
        raise AssertionError(
            f"{method} {path} expected {expected_status}, got {response.status_code}: "
            f"{response.text}"
        )

    data = response.json()
    if not isinstance(data, dict):
        raise AssertionError(f"{method} {path} did not return one JSON object.")
    return data


def _create_task(
    client: TestClient,
    *,
    title: str,
    input_summary: str,
    priority: str = "high",
) -> dict[str, Any]:
    return _request_json(
        client,
        "POST",
        "/tasks",
        expected_status=201,
        json_body={
            "title": title,
            "input_summary": input_summary,
            "priority": priority,
        },
    )


@contextmanager
def _temporary_budget_limits(
    *,
    daily_budget_usd: float,
    session_budget_usd: float,
) -> Iterator[None]:
    # Import lazily after env is prepared in `main`.
    from app.core.config import settings

    previous_daily = settings.daily_budget_usd
    previous_session = settings.session_budget_usd
    object.__setattr__(settings, "daily_budget_usd", daily_budget_usd)
    object.__setattr__(settings, "session_budget_usd", session_budget_usd)
    try:
        yield
    finally:
        object.__setattr__(settings, "daily_budget_usd", previous_daily)
        object.__setattr__(settings, "session_budget_usd", previous_session)


def _prepare_env() -> None:
    if SMOKE_RUNTIME_DATA_DIR.exists():
        shutil.rmtree(SMOKE_RUNTIME_DATA_DIR)
    SMOKE_RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)

    os.environ["RUNTIME_DATA_DIR"] = str(SMOKE_RUNTIME_DATA_DIR)
    os.environ["DAILY_BUDGET_USD"] = "0.05"
    os.environ["SESSION_BUDGET_USD"] = "0.20"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"


def _case_main_path(client: TestClient) -> SmokeCase:
    task = _create_task(
        client,
        title="day5-main-path",
        input_summary="simulate: run the happy path smoke check",
    )
    worker = _request_json(client, "POST", "/workers/run-once", expected_status=200)
    task_detail = _request_json(
        client,
        "GET",
        f"/tasks/{task['id']}",
        expected_status=200,
    )
    run_logs = _request_json(
        client,
        "GET",
        f"/runs/{worker['run_id']}/logs?limit=100",
        expected_status=200,
    )
    event_names = [event.get("event") for event in run_logs.get("events", [])]

    _assert(worker["claimed"] is True, "Worker should claim one task on main path.")
    _assert(worker["task_id"] == task["id"], "Worker should execute the created task.")
    _assert(worker["task_status"] == "completed", "Task should end in completed.")
    _assert(worker["run_status"] == "succeeded", "Run should end in succeeded.")
    _assert(task_detail["status"] == "completed", "Task detail must match completed status.")
    _assert("run_claimed" in event_names, "Run logs should contain run_claimed.")
    _assert("execution_finished" in event_names, "Run logs should contain execution_finished.")
    _assert("run_finalized" in event_names, "Run logs should contain run_finalized.")

    return SmokeCase(
        case_id="P2A5-S1-1",
        title="主路径 pending -> running -> completed",
        passed=True,
        details={
            "task_id": task["id"],
            "run_id": worker["run_id"],
            "task_status": worker["task_status"],
            "run_status": worker["run_status"],
            "log_events": event_names,
        },
    )


def _case_failed_and_retry(client: TestClient) -> SmokeCase:
    task = _create_task(
        client,
        title="day5-failed-retry",
        input_summary="shell: exit 1",
    )
    first_run = _request_json(client, "POST", "/workers/run-once", expected_status=200)
    retry_result = _request_json(
        client,
        "POST",
        f"/tasks/{task['id']}/retry",
        expected_status=200,
    )

    _assert(first_run["task_id"] == task["id"], "Failed-path run should target created task.")
    _assert(first_run["task_status"] == "failed", "Task should fail on shell exit 1.")
    _assert(first_run["run_status"] == "failed", "Run should be failed.")
    _assert(
        first_run["failure_category"] == "execution_failed",
        "Failure category should be execution_failed.",
    )
    _assert(retry_result["previous_status"] == "failed", "Retry should come from failed.")
    _assert(retry_result["current_status"] == "pending", "Retry should reset task to pending.")

    return SmokeCase(
        case_id="P2A5-S1-2",
        title="失败路径 failed -> retry -> pending",
        passed=True,
        details={
            "task_id": task["id"],
            "run_id": first_run["run_id"],
            "failure_category": first_run["failure_category"],
            "retry_previous_status": retry_result["previous_status"],
            "retry_current_status": retry_result["current_status"],
        },
    )


def _case_blocked_and_retry(client: TestClient) -> SmokeCase:
    task = _create_task(
        client,
        title="day5-blocked-retry",
        input_summary="simulate: trigger guard blocked flow",
    )

    with _temporary_budget_limits(daily_budget_usd=0.0, session_budget_usd=0.0):
        blocked_run = _request_json(client, "POST", "/workers/run-once", expected_status=200)

    retry_result = _request_json(
        client,
        "POST",
        f"/tasks/{task['id']}/retry",
        expected_status=200,
    )

    _assert(blocked_run["task_id"] == task["id"], "Blocked-path run should target created task.")
    _assert(blocked_run["task_status"] == "blocked", "Task should become blocked.")
    _assert(blocked_run["run_status"] == "cancelled", "Run should be cancelled on guard block.")
    _assert(
        blocked_run["failure_category"] in {"daily_budget_exceeded", "session_budget_exceeded"},
        "Blocked run should carry one budget failure category.",
    )
    _assert(retry_result["previous_status"] == "blocked", "Retry should come from blocked.")
    _assert(retry_result["current_status"] == "pending", "Retry should reset blocked task.")

    return SmokeCase(
        case_id="P2A5-S1-3",
        title="守卫阻断路径 blocked -> retry -> pending",
        passed=True,
        details={
            "task_id": task["id"],
            "run_id": blocked_run["run_id"],
            "failure_category": blocked_run["failure_category"],
            "retry_previous_status": retry_result["previous_status"],
            "retry_current_status": retry_result["current_status"],
        },
    )


def _case_pause_and_human_flow(client: TestClient) -> SmokeCase:
    task = _create_task(
        client,
        title="day5-pause-human",
        input_summary="simulate: pause and human state transitions",
    )
    pause_result = _request_json(
        client,
        "POST",
        f"/tasks/{task['id']}/pause",
        expected_status=200,
        json_body={"reason": "day5 smoke pause"},
    )
    resume_result = _request_json(
        client,
        "POST",
        f"/tasks/{task['id']}/resume",
        expected_status=200,
    )
    request_human_result = _request_json(
        client,
        "POST",
        f"/tasks/{task['id']}/request-human",
        expected_status=200,
    )
    resolve_human_result = _request_json(
        client,
        "POST",
        f"/tasks/{task['id']}/resolve-human",
        expected_status=200,
    )

    _assert(pause_result["current_status"] == "paused", "Pause should set paused status.")
    _assert(resume_result["current_status"] == "pending", "Resume should return pending.")
    _assert(
        request_human_result["current_status"] == "waiting_human",
        "Request-human should set waiting_human.",
    )
    _assert(
        resolve_human_result["current_status"] == "pending",
        "Resolve-human should return pending.",
    )
    _assert(
        resolve_human_result["human_status"] == "resolved",
        "Resolve-human should set human_status resolved.",
    )

    return SmokeCase(
        case_id="P2A5-S1-4",
        title="控制路径 paused / waiting_human 的进入与恢复",
        passed=True,
        details={
            "task_id": task["id"],
            "pause_current_status": pause_result["current_status"],
            "resume_current_status": resume_result["current_status"],
            "request_human_current_status": request_human_result["current_status"],
            "resolve_human_current_status": resolve_human_result["current_status"],
            "resolve_human_status": resolve_human_result["human_status"],
        },
    )


def _case_illegal_transitions(client: TestClient) -> SmokeCase:
    task = _create_task(
        client,
        title="day5-illegal-transitions",
        input_summary="simulate: illegal transition checks",
    )

    retry_resp = client.post(f"/tasks/{task['id']}/retry")
    resume_resp = client.post(f"/tasks/{task['id']}/resume")
    request_human = _request_json(
        client,
        "POST",
        f"/tasks/{task['id']}/request-human",
        expected_status=200,
    )
    pause_waiting_resp = client.post(
        f"/tasks/{task['id']}/pause",
        json={"reason": "should fail on waiting_human"},
    )

    _assert(retry_resp.status_code == 409, "Retry on pending should return 409.")
    _assert(resume_resp.status_code == 409, "Resume on pending should return 409.")
    _assert(request_human["current_status"] == "waiting_human", "Task should be waiting_human.")
    _assert(
        pause_waiting_resp.status_code == 409,
        "Pause on waiting_human should return 409.",
    )

    return SmokeCase(
        case_id="P2A5-S1-5",
        title="非法转移统一返回 HTTP 409",
        passed=True,
        details={
            "task_id": task["id"],
            "retry_status_code": retry_resp.status_code,
            "resume_status_code": resume_resp.status_code,
            "pause_waiting_human_status_code": pause_waiting_resp.status_code,
        },
    )


def main() -> None:
    _prepare_env()

    # Import app only after environment variables are prepared.
    from app.main import create_application

    app = create_application()
    cases: list[SmokeCase] = []

    with TestClient(app) as client:
        cases.append(_case_main_path(client))
        cases.append(_case_failed_and_retry(client))
        cases.append(_case_blocked_and_retry(client))
        cases.append(_case_pause_and_human_flow(client))
        cases.append(_case_illegal_transitions(client))

    report_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime_data_dir": str(SMOKE_RUNTIME_DATA_DIR),
        "total_cases": len(cases),
        "passed_cases": sum(1 for case in cases if case.passed),
        "cases": [
            {
                "case_id": case.case_id,
                "title": case.title,
                "passed": case.passed,
                "details": case.details,
            }
            for case in cases
        ],
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"[day5-smoke] {report_payload['passed_cases']}/{report_payload['total_cases']} "
        f"cases passed."
    )
    print(f"[day5-smoke] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
