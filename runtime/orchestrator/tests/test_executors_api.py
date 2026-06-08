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


def test_executors_api_route_file_has_no_write_endpoints() -> None:
    source = Path("app/api/routes/executors.py").read_text()

    assert "@router.post" not in source
    assert "@router.put" not in source
    assert "@router.patch" not in source
    assert "@router.delete" not in source


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
