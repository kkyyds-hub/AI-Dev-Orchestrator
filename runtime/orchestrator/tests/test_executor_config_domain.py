from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain.executor_config import (
    ExecutorBinaryDiscoveryStrategy,
    ExecutorCapability,
    ExecutorConfigDiscovery,
    ExecutorConfigSource,
    ExecutorLaunchPreview,
    ExecutorLaunchSafetyFlags,
    ExecutorLoginStatus,
    ExecutorPermissionModel,
    ExecutorProfile,
    ExecutorProvider,
    ExecutorRegistrySnapshot,
    ExecutorStatus,
)


def make_profile(
    executor_id: str = "codex",
    *,
    status: ExecutorStatus = ExecutorStatus.AVAILABLE,
    capability: ExecutorCapability | None = None,
    binary_discovery_strategy: ExecutorBinaryDiscoveryStrategy = ExecutorBinaryDiscoveryStrategy.PATH_LOOKUP,
    binary_name: str | None = "codex",
) -> ExecutorProfile:
    return ExecutorProfile(
        executor_id=executor_id,
        display_name=f" {executor_id} ",
        provider=ExecutorProvider.OPENAI,
        binary_name=binary_name,
        binary_discovery_strategy=binary_discovery_strategy,
        capabilities=capability or ExecutorCapability(),
        config_discovery=ExecutorConfigDiscovery(
            source=ExecutorConfigSource.NONE,
            cli_installed=False,
            login_status=ExecutorLoginStatus.UNKNOWN,
        ),
        permission_model=ExecutorPermissionModel.DEFAULT_DENY,
        status=status,
    )


def test_executor_capability_defaults_git_write_false() -> None:
    capability = ExecutorCapability()

    assert capability.git_write is False


@pytest.mark.parametrize("value", [0, -1])
def test_executor_capability_rejects_non_positive_context_tokens(value: int) -> None:
    with pytest.raises(ValidationError):
        ExecutorCapability(max_context_tokens=value)


def test_executor_config_discovery_contract_excludes_sensitive_fields() -> None:
    forbidden_fields = {
        "env_vars_present",
        "native_config_path",
        "cli_path",
        "api_key",
        "token_value",
        "auth_token",
        "secret",
    }

    assert forbidden_fields.isdisjoint(ExecutorConfigDiscovery.model_fields)

    with pytest.raises(ValidationError):
        ExecutorConfigDiscovery(api_key="plaintext")


@pytest.mark.parametrize("field_name", ["env_vars_present", "native_config_path", "cli_path"])
def test_executor_config_discovery_rejects_forbidden_extra_fields(field_name: str) -> None:
    with pytest.raises(ValidationError):
        ExecutorConfigDiscovery(**{field_name: "unsafe"})


def test_executor_config_discovery_uses_env_var_count_only() -> None:
    discovery = ExecutorConfigDiscovery(env_var_count=2)

    assert discovery.env_var_count == 2
    assert "env_var_count" in discovery.model_dump()
    assert "env_vars_present" not in discovery.model_dump()

    with pytest.raises(ValidationError):
        ExecutorConfigDiscovery(env_var_count=-1)


def test_executor_profile_trims_strings_and_rejects_empty_executor_id() -> None:
    profile = make_profile(executor_id=" codex ")

    assert profile.executor_id == "codex"
    assert profile.display_name == "codex"
    assert profile.binary_name == "codex"

    with pytest.raises(ValidationError):
        make_profile(executor_id="   ")


def test_api_only_executor_allows_missing_binary_name() -> None:
    profile = make_profile(
        executor_id="api_only",
        binary_discovery_strategy=ExecutorBinaryDiscoveryStrategy.API_ONLY,
        binary_name=None,
    )

    assert profile.binary_name is None


def test_path_lookup_executor_requires_binary_name() -> None:
    with pytest.raises(ValidationError):
        make_profile(
            executor_id="missing_binary",
            binary_discovery_strategy=ExecutorBinaryDiscoveryStrategy.PATH_LOOKUP,
            binary_name=None,
        )


def test_executor_registry_snapshot_rejects_duplicate_executor_id() -> None:
    with pytest.raises(ValidationError):
        ExecutorRegistrySnapshot(
            profiles=[
                make_profile(executor_id="codex"),
                make_profile(executor_id=" codex "),
            ],
        )


def test_available_profiles_returns_only_available_status() -> None:
    available = make_profile(executor_id="available", status=ExecutorStatus.AVAILABLE)
    disabled = make_profile(executor_id="disabled", status=ExecutorStatus.DISABLED)
    snapshot = ExecutorRegistrySnapshot(profiles=[available, disabled])

    assert snapshot.available_profiles() == [available]
    assert snapshot.get_profile(" available ") == available


def test_profiles_with_capability_filters_by_capability_name() -> None:
    code_profile = make_profile(
        executor_id="code",
        capability=ExecutorCapability(code_fix=True, documentation=False),
    )
    docs_profile = make_profile(
        executor_id="docs",
        capability=ExecutorCapability(code_fix=False, documentation=True),
    )
    snapshot = ExecutorRegistrySnapshot(profiles=[code_profile, docs_profile])

    assert snapshot.profiles_with_capability("code_fix") == [code_profile]
    assert snapshot.profiles_with_capability(" documentation ") == [docs_profile]
    assert snapshot.profiles_with_capability("unknown_capability") == []


def test_executor_launch_safety_flags_default_to_no_launch_no_git_write_and_confirmation() -> None:
    flags = ExecutorLaunchSafetyFlags()

    assert flags.no_secret_exposure is True
    assert flags.launch_preview_only is True
    assert flags.no_external_process_launch is True
    assert flags.no_product_runtime_git_write is True
    assert flags.requires_human_confirmation_before_p9 is True


def test_executor_launch_preview_excludes_runtime_process_fields() -> None:
    forbidden_fields = {"pid", "exit_code", "log_path", "process_handle"}

    assert forbidden_fields.isdisjoint(ExecutorLaunchPreview.model_fields)

    preview = ExecutorLaunchPreview(
        ready=False,
        reason_code="not_ready",
        executor_id="codex",
        launch_command_preview="codex --help",
        launch_cwd_hint=None,
        workspace_bound=False,
        env_var_count=0,
        token_configured=False,
        permission_mode=ExecutorPermissionModel.DEFAULT_DENY,
        model_name=None,
        estimated_cost_warning=None,
        blocking_reasons=[" 需要先完成配置 "],
    )

    dumped = preview.model_dump()
    assert forbidden_fields.isdisjoint(dumped)
    assert preview.contract_kind == "preview_only"
    assert preview.blocking_reasons == ["需要先完成配置"]

    with pytest.raises(ValidationError):
        ExecutorLaunchPreview(
            executor_id="codex",
            launch_command_preview="codex --help",
            pid=1234,
        )


def test_executor_config_domain_does_not_import_service_api_or_worker_layers() -> None:
    source = Path("app/domain/executor_config.py").read_text()

    assert "app.services" not in source
    assert "app.api" not in source
    assert "app.workers" not in source


def test_reference_project_path_is_not_copied_into_domain_file() -> None:
    source = Path("app/domain/executor_config.py").read_text()

    assert "/Users/kk/project explore/agent-orchestrator" not in source
    assert "project-explore-one" not in source
