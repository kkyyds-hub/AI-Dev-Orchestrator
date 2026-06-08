from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import api_router
from app.api.routes.executors import get_executor_config_discovery_service
from app.domain.executor_config import (
    ExecutorBinaryDiscoveryStrategy,
    ExecutorConfigDiscovery,
    ExecutorConfigSource,
    ExecutorLoginStatus,
)
from app.services.executor_config_discovery_service import ExecutorConfigDiscoveryService


class FakeProbe:
    def __init__(self, results: dict[str, ExecutorConfigDiscovery]) -> None:
        self.results = results

    def discover(
        self,
        executor_id: str,
        binary_name: str | None,
        strategy: ExecutorBinaryDiscoveryStrategy,
    ) -> ExecutorConfigDiscovery:
        return self.results.get(executor_id, ExecutorConfigDiscovery())


def discovery(
    *,
    cli_installed: bool = False,
    token_configured: bool = False,
    login_status: ExecutorLoginStatus = ExecutorLoginStatus.UNKNOWN,
) -> ExecutorConfigDiscovery:
    return ExecutorConfigDiscovery(
        source=ExecutorConfigSource.NONE,
        cli_installed=cli_installed,
        login_status=login_status,
        token_configured=token_configured,
        env_var_count=0,
    )


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(api_router)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def fake_available_client() -> TestClient:
    app = FastAPI()
    app.include_router(api_router)

    def override_service() -> ExecutorConfigDiscoveryService:
        return ExecutorConfigDiscoveryService(
            probe=FakeProbe(
                {
                    "codex": discovery(
                        cli_installed=True,
                        token_configured=True,
                        login_status=ExecutorLoginStatus.LOGGED_IN,
                    ),
                    "claude_code": discovery(cli_installed=False),
                    "deepseek_api": discovery(token_configured=True),
                },
            ),
        )

    app.dependency_overrides[get_executor_config_discovery_service] = override_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_get_executors_returns_builtin_profiles(client: TestClient) -> None:
    response = client.get("/executors")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert {profile["executor_id"] for profile in data["profiles"]} == {
        "codex",
        "claude_code",
        "deepseek_api",
    }


def test_noop_probe_does_not_mark_cli_executors_available(client: TestClient) -> None:
    data = client.get("/executors").json()
    statuses = {profile["executor_id"]: profile["status"] for profile in data["profiles"]}

    assert statuses["codex"] != "available"
    assert statuses["claude_code"] != "available"
    assert statuses["codex"] == "not_installed"
    assert statuses["claude_code"] == "not_installed"


def test_get_executor_profile(client: TestClient) -> None:
    response = client.get("/executors/codex")

    assert response.status_code == 200
    data = response.json()
    assert data["executor_id"] == "codex"
    assert data["capabilities"]["git_write"] is False


def test_get_executor_profile_not_found(client: TestClient) -> None:
    response = client.get("/executors/not_real")

    assert response.status_code == 404


def test_get_executor_readiness_returns_blocking_reasons(client: TestClient) -> None:
    response = client.get("/executors/codex/readiness")

    assert response.status_code == 200
    data = response.json()
    assert data["executor_id"] == "codex"
    assert data["ready"] is False
    assert data["status"] == "not_installed"
    assert data["blocking_reasons"] == ["executor_not_installed"]
    assert "token" not in data["safe_summary"].lower()


def test_fake_probe_can_return_ready_true(fake_available_client: TestClient) -> None:
    response = fake_available_client.get("/executors/codex/readiness")

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert data["status"] == "available"
    assert data["blocking_reasons"] == []


def test_post_codex_launch_preview_returns_preview(client: TestClient) -> None:
    response = client.post("/executors/codex/launch-preview")

    assert response.status_code == 200
    data = response.json()
    assert data["executor_id"] == "codex"
    assert data["contract_kind"] == "preview_only"
    assert data["launch_command_preview"].startswith("PREVIEW ONLY:")
    assert data["safety_flags"]["launch_preview_only"] is True


def test_noop_probe_codex_launch_preview_is_not_ready(client: TestClient) -> None:
    response = client.post("/executors/codex/launch-preview")

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is False
    assert "executor_not_installed" in data["blocking_reasons"]
    assert "p9_not_started" in data["blocking_reasons"]


def test_fake_available_codex_launch_preview_ready_but_preview_only(
    fake_available_client: TestClient,
) -> None:
    response = fake_available_client.post(
        "/executors/codex/launch-preview",
        json={
            "operation_intent": "code fix",
            "project_id": "project-1",
            "task_id": "task-1",
            "model_name": "gpt-5",
            "workspace_bound": True,
            "launch_cwd_hint": "/private/workspace/path",
            "require_human_confirmation": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert data["reason_code"] == "preview_ready"
    assert data["launch_command_preview"].startswith("PREVIEW ONLY:")
    assert data["launch_cwd_hint"] == "workspace hint provided"
    assert data["workspace_bound"] is True
    assert data["safety_flags"]["no_external_process_launch"] is True
    assert data["safety_flags"]["no_product_runtime_git_write"] is True


def test_launch_preview_not_found_returns_404(client: TestClient) -> None:
    response = client.post("/executors/not_real/launch-preview")

    assert response.status_code == 404


def test_launch_preview_response_excludes_sensitive_and_runtime_fields(
    fake_available_client: TestClient,
) -> None:
    forbidden = {
        "pid",
        "exit_code",
        "log_path",
        "process_handle",
        "session_id",
        "api_key",
        "token_value",
        "auth_token",
        "secret",
        "env_vars_present",
        "native_config_path",
        "cli_path",
    }

    response = fake_available_client.post("/executors/codex/launch-preview")

    assert response.status_code == 200
    assert_response_tree_excludes(response.json(), forbidden)


def test_get_available_executors_only_returns_available_profiles(
    fake_available_client: TestClient,
) -> None:
    response = fake_available_client.get("/executors/available")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["available_count"] == 2
    assert {profile["executor_id"] for profile in data["profiles"]} == {
        "codex",
        "deepseek_api",
    }


def test_executor_responses_exclude_sensitive_discovery_fields(client: TestClient) -> None:
    forbidden = {
        "env_vars_present",
        "native_config_path",
        "cli_path",
        "api_key",
        "token_value",
        "auth_token",
        "secret",
    }

    payload = client.get("/executors").json()
    assert_response_tree_excludes(payload, forbidden)
    assert "env_var_count" in payload["profiles"][0]["config_discovery"]


def test_executor_responses_exclude_process_runtime_fields(client: TestClient) -> None:
    forbidden = {"pid", "exit_code", "log_path", "process_handle"}

    assert_response_tree_excludes(client.get("/executors").json(), forbidden)
    assert_response_tree_excludes(client.get("/executors/codex/readiness").json(), forbidden)


def test_executors_api_route_file_has_only_preview_post_endpoint() -> None:
    source = Path("app/api/routes/executors.py").read_text()

    assert "@router.post(" in source
    assert '"/{executor_id}/launch-preview"' in source
    assert "@router.put" not in source
    assert "@router.patch" not in source
    assert "@router.delete" not in source
    forbidden_route_fragments = [
        '"/{executor_id}/launch"',
        '"/{executor_id}/execute"',
        '"/{executor_id}/run"',
        '"/{executor_id}/start"',
        '"/{executor_id}/dispatch"',
    ]
    for route_fragment in forbidden_route_fragments:
        assert route_fragment not in source


def test_executors_api_route_file_does_not_import_execution_helpers() -> None:
    source = Path("app/api/routes/executors.py").read_text()

    assert "import subprocess" not in source
    assert "subprocess." not in source
    assert "os.popen" not in source
    assert "shell=True" not in source


def test_executors_api_route_file_does_not_read_local_config_or_environment() -> None:
    source = Path("app/api/routes/executors.py").read_text()

    assert ("~/" + "codex") not in source
    assert ("~/" + "claude") not in source
    assert ("os." + "environ") not in source


def test_router_includes_executors_router() -> None:
    source = Path("app/api/router.py").read_text()

    assert "executors_router" in source
    assert "include_router(executors_router)" in source


def assert_response_tree_excludes(payload, forbidden: set[str]) -> None:
    if isinstance(payload, dict):
        assert forbidden.isdisjoint(payload.keys())
        for value in payload.values():
            assert_response_tree_excludes(value, forbidden)
    elif isinstance(payload, list):
        for item in payload:
            assert_response_tree_excludes(item, forbidden)
