from __future__ import annotations

from pathlib import Path

from app.domain.executor_config import (
    ExecutorBinaryDiscoveryStrategy,
    ExecutorConfigDiscovery,
    ExecutorConfigSource,
    ExecutorLoginStatus,
    ExecutorStatus,
)
from app.services.executor_config_discovery_service import (
    ExecutorConfigDiscoveryService,
    sanitize_discovery_error,
)


class FakeProbe:
    def __init__(self, results: dict[str, ExecutorConfigDiscovery]) -> None:
        self.results = results
        self.calls: list[tuple[str, str | None, ExecutorBinaryDiscoveryStrategy]] = []

    def discover(
        self,
        executor_id: str,
        binary_name: str | None,
        strategy: ExecutorBinaryDiscoveryStrategy,
    ) -> ExecutorConfigDiscovery:
        self.calls.append((executor_id, binary_name, strategy))
        return self.results.get(executor_id, ExecutorConfigDiscovery())


def discovery(
    *,
    cli_installed: bool = False,
    token_configured: bool = False,
    login_status: ExecutorLoginStatus = ExecutorLoginStatus.UNKNOWN,
    discovery_error: str | None = None,
) -> ExecutorConfigDiscovery:
    return ExecutorConfigDiscovery(
        source=ExecutorConfigSource.NONE,
        cli_installed=cli_installed,
        login_status=login_status,
        token_configured=token_configured,
        env_var_count=0,
        discovery_error=discovery_error,
    )


def test_service_returns_builtin_registry() -> None:
    snapshot = ExecutorConfigDiscoveryService().get_registry_snapshot()

    assert {profile.executor_id for profile in snapshot.profiles} == {
        "codex",
        "claude_code",
        "deepseek_api",
    }


def test_builtin_profiles_do_not_allow_git_write() -> None:
    snapshot = ExecutorConfigDiscoveryService().get_registry_snapshot()

    assert all(profile.capabilities.git_write is False for profile in snapshot.profiles)


def test_deepseek_api_is_api_only_without_binary_name() -> None:
    profile = ExecutorConfigDiscoveryService().get_profile("deepseek_api")

    assert profile is not None
    assert profile.binary_discovery_strategy == ExecutorBinaryDiscoveryStrategy.API_ONLY
    assert profile.binary_name is None


def test_default_noop_probe_does_not_execute_real_cli_and_returns_safe_statuses() -> None:
    service = ExecutorConfigDiscoveryService()
    snapshot = service.get_registry_snapshot()

    statuses = {profile.executor_id: profile.status for profile in snapshot.profiles}
    assert statuses["codex"] == ExecutorStatus.NOT_INSTALLED
    assert statuses["claude_code"] == ExecutorStatus.NOT_INSTALLED
    assert statuses["deepseek_api"] == ExecutorStatus.NOT_CONFIGURED
    assert all(profile.config_discovery.env_var_count == 0 for profile in snapshot.profiles)


def test_fake_probe_can_mark_codex_available() -> None:
    probe = FakeProbe(
        {
            "codex": discovery(
                cli_installed=True,
                token_configured=True,
                login_status=ExecutorLoginStatus.LOGGED_IN,
            ),
        },
    )

    profile = ExecutorConfigDiscoveryService(probe=probe).get_profile("codex")

    assert profile is not None
    assert profile.status == ExecutorStatus.AVAILABLE
    assert ("codex", "codex", ExecutorBinaryDiscoveryStrategy.PATH_LOOKUP) in probe.calls


def test_fake_probe_can_mark_claude_code_not_installed() -> None:
    probe = FakeProbe({"claude_code": discovery(cli_installed=False)})

    profile = ExecutorConfigDiscoveryService(probe=probe).get_profile("claude_code")

    assert profile is not None
    assert profile.status == ExecutorStatus.NOT_INSTALLED


def test_deepseek_api_without_token_is_not_configured() -> None:
    probe = FakeProbe({"deepseek_api": discovery(token_configured=False)})

    profile = ExecutorConfigDiscoveryService(probe=probe).get_profile("deepseek_api")

    assert profile is not None
    assert profile.status == ExecutorStatus.NOT_CONFIGURED


def test_deepseek_api_with_token_is_available() -> None:
    probe = FakeProbe({"deepseek_api": discovery(token_configured=True)})

    profile = ExecutorConfigDiscoveryService(probe=probe).get_profile("deepseek_api")

    assert profile is not None
    assert profile.status == ExecutorStatus.AVAILABLE


def test_discovery_error_is_sanitized() -> None:
    raw = (
        "api key: value-123 token=abc secret: hidden password=guess "
        "Bearer bearer-value sk-testsecret"
    )

    sanitized = sanitize_discovery_error(raw)

    assert sanitized is not None
    assert "value-123" not in sanitized
    assert "abc" not in sanitized
    assert "hidden" not in sanitized
    assert "guess" not in sanitized
    assert "bearer-value" not in sanitized
    assert "sk-testsecret" not in sanitized
    assert "[redacted]" in sanitized


def test_service_sanitizes_probe_discovery_error() -> None:
    probe = FakeProbe(
        {
            "codex": discovery(
                cli_installed=True,
                discovery_error="token: unsafe-token sk-unsafevalue",
            ),
        },
    )

    profile = ExecutorConfigDiscoveryService(probe=probe).get_profile("codex")

    assert profile is not None
    assert profile.config_discovery.discovery_error is not None
    assert "unsafe-token" not in profile.config_discovery.discovery_error
    assert "sk-unsafevalue" not in profile.config_discovery.discovery_error


def test_discovery_result_excludes_sensitive_fields() -> None:
    forbidden = {
        "env_vars_present",
        "native_config_path",
        "cli_path",
        "api_key",
        "token_value",
        "auth_token",
        "secret",
    }
    profile = ExecutorConfigDiscoveryService().get_profile("codex")

    assert profile is not None
    dumped = profile.config_discovery.model_dump()
    assert forbidden.isdisjoint(ExecutorConfigDiscovery.model_fields)
    assert forbidden.isdisjoint(dumped)
    assert "env_var_count" in dumped


def test_available_profiles_with_capability_filters_available_profiles() -> None:
    probe = FakeProbe(
        {
            "codex": discovery(
                cli_installed=True,
                token_configured=True,
                login_status=ExecutorLoginStatus.LOGGED_IN,
            ),
            "claude_code": discovery(cli_installed=False),
            "deepseek_api": discovery(token_configured=True),
        },
    )
    service = ExecutorConfigDiscoveryService(probe=probe)

    assert [profile.executor_id for profile in service.profiles_with_capability("code_fix")] == [
        "codex",
        "claude_code",
    ]
    assert [
        profile.executor_id
        for profile in service.available_profiles_with_capability("code_fix")
    ] == ["codex"]
    assert [
        profile.executor_id
        for profile in service.available_profiles_with_capability("route_planning")
    ] == ["deepseek_api"]


def test_domain_and_service_files_do_not_import_api_or_workers() -> None:
    for relative_path in [
        "app/domain/executor_config.py",
        "app/services/executor_config_discovery_service.py",
    ]:
        source = Path(relative_path).read_text()
        assert "app.api" not in source
        assert "app.workers" not in source


def test_service_file_does_not_import_subprocess_or_shell_helpers() -> None:
    source = Path("app/services/executor_config_discovery_service.py").read_text()

    assert "import subprocess" not in source
    assert "subprocess." not in source
    assert "os.popen" not in source
    assert "shell=True" not in source


def test_tests_do_not_reference_real_local_config_or_environment_secret_values() -> None:
    source = Path("tests/test_executor_config_discovery_service.py").read_text()

    assert ("~/" + "codex") not in source
    assert ("~/" + "claude") not in source
    assert ("os." + "environ") not in source


def test_service_does_not_create_sessions_or_call_executor_shell_execution() -> None:
    source = Path("app/services/executor_config_discovery_service.py").read_text()

    assert "ExecutorSession" not in source
    assert "run_shell_command" not in source
