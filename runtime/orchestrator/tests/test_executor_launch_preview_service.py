from __future__ import annotations

from pathlib import Path

from app.domain.executor_config import (
    ExecutorBinaryDiscoveryStrategy,
    ExecutorConfigDiscovery,
    ExecutorConfigSource,
    ExecutorLoginStatus,
)
from app.services.executor_config_discovery_service import ExecutorConfigDiscoveryService
from app.services.executor_launch_preview_service import (
    ExecutorLaunchPreviewRequest,
    ExecutorLaunchPreviewService,
)


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


def service_with_probe(results: dict[str, ExecutorConfigDiscovery]) -> ExecutorLaunchPreviewService:
    return ExecutorLaunchPreviewService(
        discovery_service=ExecutorConfigDiscoveryService(probe=FakeProbe(results)),
    )


def test_not_installed_executor_generates_blocked_preview() -> None:
    preview = ExecutorLaunchPreviewService().build_preview("codex")

    assert preview is not None
    assert preview.ready is False
    assert "executor_not_installed" in preview.blocking_reasons
    assert "executor_not_available" in preview.blocking_reasons


def test_fake_available_codex_preview_is_ready_but_preview_only() -> None:
    preview = service_with_probe(
        {
            "codex": discovery(
                cli_installed=True,
                token_configured=True,
                login_status=ExecutorLoginStatus.LOGGED_IN,
            ),
        },
    ).build_preview("codex", ExecutorLaunchPreviewRequest(model_name="gpt-5"))

    assert preview is not None
    assert preview.ready is True
    assert preview.reason_code == "preview_ready"
    assert preview.launch_command_preview.startswith("PREVIEW ONLY:")
    assert "human-confirmation-required" in preview.launch_command_preview
    assert "p9_not_started" in preview.blocking_reasons


def test_preview_safety_flags_are_explicit() -> None:
    preview = ExecutorLaunchPreviewService().build_preview("codex")

    assert preview is not None
    assert preview.safety_flags.no_secret_exposure is True
    assert preview.safety_flags.launch_preview_only is True
    assert preview.safety_flags.no_external_process_launch is True
    assert preview.safety_flags.no_product_runtime_git_write is True
    assert preview.safety_flags.requires_human_confirmation_before_p9 is True


def test_deepseek_api_preview_does_not_imply_shell_or_file_execution() -> None:
    preview = service_with_probe(
        {"deepseek_api": discovery(token_configured=True)},
    ).build_preview("deepseek_api")

    assert preview is not None
    assert preview.ready is True
    assert preview.launch_command_preview == (
        "PREVIEW ONLY: deepseek_api [api-request-summary] "
        "[human-confirmation-required]"
    )
    lower_payload = preview.model_dump_json().lower()
    assert "shell" not in lower_payload
    assert "subprocess" not in lower_payload
    assert "file execution" not in lower_payload
    assert "execute" not in preview.launch_command_preview.lower()


def test_preview_payload_excludes_process_runtime_fields() -> None:
    preview = ExecutorLaunchPreviewService().build_preview("codex")

    assert preview is not None
    forbidden = {"pid", "exit_code", "log_path", "process_handle", "session_id"}
    assert_response_tree_excludes(preview.model_dump(), forbidden)


def test_preview_payload_excludes_sensitive_fields() -> None:
    preview = ExecutorLaunchPreviewService().build_preview("codex")

    assert preview is not None
    forbidden = {
        "api_key",
        "token_value",
        "auth_token",
        "secret",
        "env_vars_present",
        "native_config_path",
        "cli_path",
    }
    assert_response_tree_excludes(preview.model_dump(), forbidden)


def test_launch_cwd_hint_is_only_a_sanitized_hint() -> None:
    preview = ExecutorLaunchPreviewService().build_preview(
        "codex",
        ExecutorLaunchPreviewRequest(launch_cwd_hint="/Users/example/private/repo"),
    )

    assert preview is not None
    assert preview.launch_cwd_hint == "workspace hint provided"


def test_service_file_does_not_import_subprocess_or_shell_helpers() -> None:
    source = Path("app/services/executor_launch_preview_service.py").read_text()

    assert "import subprocess" not in source
    assert "subprocess." not in source
    assert "os.popen" not in source
    assert "shell=True" not in source


def test_service_file_does_not_read_real_local_config_or_environment() -> None:
    source = Path("app/services/executor_launch_preview_service.py").read_text()

    assert ("~/" + "codex") not in source
    assert ("~/" + "claude") not in source
    assert ("os." + "environ") not in source


def test_service_does_not_create_sessions_or_call_shell_execution() -> None:
    source = Path("app/services/executor_launch_preview_service.py").read_text()

    assert "ExecutorSession" not in source
    assert "run_shell_command" not in source


def assert_response_tree_excludes(payload, forbidden: set[str]) -> None:
    if isinstance(payload, dict):
        assert forbidden.isdisjoint(payload.keys())
        for value in payload.values():
            assert_response_tree_excludes(value, forbidden)
    elif isinstance(payload, list):
        for item in payload:
            assert_response_tree_excludes(item, forbidden)
