from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import api_router
from app.api.routes import runtime as runtime_route
from app.services.controlled_runtime_service import ControlledRuntimeService


FORBIDDEN_RESPONSE_KEYS = {
    "command",
    "raw_command",
    "raw_args",
    "env",
    "env_vars",
    "api_key",
    "token_value",
    "auth_token",
    "secret",
    "password",
    "cwd",
    "native_config_path",
    "cli_path",
    "process_handle",
    "log_path",
    "stdout_path",
    "stderr_path",
    "raw_output",
    "raw_error",
}


@pytest.fixture
def runtime_client() -> TestClient:
    app = FastAPI()
    app.include_router(api_router)
    service = ControlledRuntimeService()
    registry = runtime_route.InMemoryLaunchRequestRegistry()

    app.dependency_overrides[runtime_route.get_controlled_runtime_service] = lambda: service
    app.dependency_overrides[runtime_route.get_launch_request_registry] = lambda: registry

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _safe_launch_payload(**overrides) -> dict:
    payload = {
        "executor_id": "codex",
        "launch_preview_id": "preview-1",
        "project_id": "project-1",
        "task_id": "task-1",
        "run_id": "run-1",
        "requested_by": "user-1",
        "human_confirmed": True,
        "executor_ready": True,
        "launch_preview_ready": True,
        "workspace_bound": True,
        "workspace_path_hint": "/Users/kk/workspace/private",
        "estimated_cost": "1.25",
        "session_budget_limit": "2.00",
        "daily_budget_remaining": "10.00",
        "active_session_count": 0,
        "max_concurrent_sessions": 1,
        "timeout_configured": True,
        "cancellation_supported": True,
        "audit_event_ready": True,
        "executor_runtime_enabled": True,
    }
    payload.update(overrides)
    return payload


def _create_safe_request(client: TestClient) -> dict:
    response = client.post("/runtime/launch-requests", json=_safe_launch_payload())
    assert response.status_code == 201
    return response.json()


def _create_running_session(client: TestClient) -> dict:
    request = _create_safe_request(client)
    response = client.post(
        f"/runtime/launch-requests/{request['request_id']}/confirm",
        json={"approved_by": "user-1", "confirmation_text": "confirmed"},
    )
    assert response.status_code == 200
    return response.json()


def _assert_no_forbidden_keys(value) -> None:
    if isinstance(value, dict):
        assert FORBIDDEN_RESPONSE_KEYS.isdisjoint(value.keys())
        for nested in value.values():
            _assert_no_forbidden_keys(nested)
    elif isinstance(value, list):
        for item in value:
            _assert_no_forbidden_keys(item)


def test_get_runtime_sessions_defaults_to_empty_list(runtime_client: TestClient) -> None:
    response = runtime_client.get("/runtime/sessions")

    assert response.status_code == 200
    assert response.json() == []


def test_create_launch_request_default_feature_flag_off_is_blocked(
    runtime_client: TestClient,
) -> None:
    response = runtime_client.post(
        "/runtime/launch-requests",
        json={"executor_id": "codex", "launch_preview_id": "preview-1"},
    )
    data = response.json()

    assert response.status_code == 201
    assert data["status"] != "approved"
    assert data["status"] == "blocked"
    assert "feature_flag_disabled" in data["blocked_reasons"]
    assert data["safety_snapshot"]["all_passed"] is False
    assert "feature_flag_disabled" in data["safety_snapshot"]["blocking_reasons"]


def test_create_launch_request_never_auto_creates_session(
    runtime_client: TestClient,
) -> None:
    request = _create_safe_request(runtime_client)
    sessions = runtime_client.get("/runtime/sessions")

    assert request["status"] == "awaiting_confirmation"
    assert request["approved_at"] is None
    assert sessions.status_code == 200
    assert sessions.json() == []


def test_get_launch_request_returns_created_request(runtime_client: TestClient) -> None:
    request = _create_safe_request(runtime_client)

    response = runtime_client.get(f"/runtime/launch-requests/{request['request_id']}")

    assert response.status_code == 200
    assert response.json()["request_id"] == request["request_id"]


def test_confirm_failed_safety_request_returns_conflict_without_session(
    runtime_client: TestClient,
) -> None:
    request_response = runtime_client.post(
        "/runtime/launch-requests",
        json={"executor_id": "codex", "launch_preview_id": "preview-1"},
    )
    request_id = request_response.json()["request_id"]

    confirm_response = runtime_client.post(
        f"/runtime/launch-requests/{request_id}/confirm",
        json={"approved_by": "user-1"},
    )

    assert confirm_response.status_code == 409
    assert runtime_client.get("/runtime/sessions").json() == []


def test_confirm_missing_confirmation_returns_bad_request(
    runtime_client: TestClient,
) -> None:
    request = _create_safe_request(runtime_client)

    response = runtime_client.post(
        f"/runtime/launch-requests/{request['request_id']}/confirm",
        json={"approved_by": ""},
    )

    assert response.status_code == 400


def test_confirm_safe_request_creates_fake_running_session(
    runtime_client: TestClient,
) -> None:
    session = _create_running_session(runtime_client)

    assert session["state"] == "running"
    assert session["source"] == "fake_adapter"
    assert session["executor_id"] == "codex"
    assert session["launch_preview_id"] == "preview-1"
    assert session["process"]["process_id"] == 1


def test_confirm_fake_launch_records_created_launching_running_events(
    runtime_client: TestClient,
) -> None:
    session = _create_running_session(runtime_client)
    events_response = runtime_client.get(f"/runtime/sessions/{session['session_id']}/events")
    event_types = [event["event_type"] for event in events_response.json()["events"]]

    assert events_response.status_code == 200
    assert event_types == ["session.created", "session.launching", "session.running"]


def test_get_runtime_session_returns_fake_session(runtime_client: TestClient) -> None:
    session = _create_running_session(runtime_client)

    response = runtime_client.get(f"/runtime/sessions/{session['session_id']}")

    assert response.status_code == 200
    assert response.json()["session_id"] == session["session_id"]


def test_get_runtime_session_events_returns_event_stream(runtime_client: TestClient) -> None:
    session = _create_running_session(runtime_client)

    response = runtime_client.get(f"/runtime/sessions/{session['session_id']}/events")
    data = response.json()

    assert response.status_code == 200
    assert data["session_id"] == session["session_id"]
    assert data["total"] == 3
    assert all(event["append_only"] for event in data["events"])


def test_cancel_runtime_session_marks_fake_session_cancelled(
    runtime_client: TestClient,
) -> None:
    session = _create_running_session(runtime_client)

    response = runtime_client.post(
        f"/runtime/sessions/{session['session_id']}/cancel",
        json={"reason": "user requested"},
    )

    assert response.status_code == 200
    assert response.json()["state"] == "cancelled"
    events = runtime_client.get(f"/runtime/sessions/{session['session_id']}/events").json()
    assert events["events"][-1]["event_type"] == "session.cancelled"


def test_missing_runtime_session_and_request_return_not_found(
    runtime_client: TestClient,
) -> None:
    assert runtime_client.get("/runtime/sessions/missing").status_code == 404
    assert runtime_client.get("/runtime/sessions/missing/events").status_code == 404
    assert runtime_client.post("/runtime/sessions/missing/cancel", json={}).status_code == 404
    assert runtime_client.get("/runtime/launch-requests/missing").status_code == 404
    assert (
        runtime_client.post(
            "/runtime/launch-requests/missing/confirm",
            json={"approved_by": "user-1"},
        ).status_code
        == 404
    )


def test_runtime_responses_exclude_forbidden_keys(runtime_client: TestClient) -> None:
    request = _create_safe_request(runtime_client)
    session = runtime_client.post(
        f"/runtime/launch-requests/{request['request_id']}/confirm",
        json={"approved_by": "user-1"},
    ).json()
    responses = [
        runtime_client.get("/runtime/sessions").json(),
        runtime_client.get(f"/runtime/sessions/{session['session_id']}").json(),
        runtime_client.get(f"/runtime/sessions/{session['session_id']}/events").json(),
        runtime_client.get(f"/runtime/launch-requests/{request['request_id']}").json(),
    ]

    for response_body in responses:
        _assert_no_forbidden_keys(response_body)


def test_runtime_route_file_does_not_register_real_execution_endpoints() -> None:
    source = _runtime_route_source()

    forbidden_route_patterns = [
        r"@router\.post\(\s*[\"'][^\"']*/execute[\"']",
        r"@router\.post\(\s*[\"'][^\"']*/run[\"']",
        r"@router\.post\(\s*[\"'][^\"']*/start[\"']",
        r"@router\.post\(\s*[\"']/launch[\"']",
        r"@router\.post\(\s*[\"']/execute[\"']",
        r"@router\.post\(\s*[\"']/run[\"']",
        r"@router\.post\(\s*[\"']/start[\"']",
    ]

    for pattern in forbidden_route_patterns:
        assert re.search(pattern, source) is None


def test_runtime_route_file_does_not_import_process_launch_modules() -> None:
    source = _runtime_route_source()

    assert "subprocess" not in source
    assert "os.popen" not in source
    assert "asyncio.subprocess" not in source


def test_runtime_route_file_does_not_import_disallowed_services() -> None:
    source = _runtime_route_source()

    assert "app.services.executor_service" not in source
    assert "app.services.openai_provider_executor_service" not in source
    assert "app.services.provider_config_service" not in source


def test_runtime_route_file_does_not_read_local_config_or_environment() -> None:
    source = _runtime_route_source()

    assert "~/.codex" not in source
    assert "~/.claude" not in source
    assert "os.environ" not in source


def test_runtime_route_file_does_not_attach_approval_or_database() -> None:
    source = _runtime_route_source().lower()

    assert "approvalservice" not in source
    assert "app.api.routes.approvals" not in source
    assert "get_db_session" not in source
    assert "sessionmaker" not in source


def test_router_includes_runtime_router() -> None:
    source = Path("app/api/router.py").read_text(encoding="utf-8")

    assert "from app.api.routes.runtime import router as runtime_router" in source
    assert "api_router.include_router(runtime_router)" in source


def test_response_json_text_omits_raw_execution_surfaces(
    runtime_client: TestClient,
) -> None:
    session = _create_running_session(runtime_client)
    event_stream = runtime_client.get(
        f"/runtime/sessions/{session['session_id']}/events",
    ).json()
    text = json.dumps(event_stream, ensure_ascii=False)

    assert "raw_command" not in text
    assert "process_handle" not in text
    assert "raw_output" not in text


def _runtime_route_source() -> str:
    return Path("app/api/routes/runtime.py").read_text(encoding="utf-8")
