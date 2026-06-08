"""Pure domain contracts for P8 executor configuration discovery.

This module defines in-memory contracts only. It does not discover local
configuration, read environment variables, launch external processes, or create
runtime sessions.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


class ExecutorProvider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    OPENAI_COMPATIBLE = "openai_compatible"


class ExecutorBinaryDiscoveryStrategy(StrEnum):
    PATH_LOOKUP = "path_lookup"
    MANAGED_PATH = "managed_path"
    API_ONLY = "api_only"


class ExecutorPermissionModel(StrEnum):
    DEFAULT_DENY = "default_deny"
    ACCEPT_EDITS = "accept_edits"
    BYPASS_PERMISSIONS = "bypass_permissions"
    API_ONLY = "api_only"


class ExecutorStatus(StrEnum):
    AVAILABLE = "available"
    NOT_INSTALLED = "not_installed"
    NOT_CONFIGURED = "not_configured"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class ExecutorConfigSource(StrEnum):
    NATIVE_CONFIG = "native_config"
    ENV = "env"
    PROJECT_MANAGED = "project_managed"
    NONE = "none"


class ExecutorLoginStatus(StrEnum):
    LOGGED_IN = "logged_in"
    NOT_LOGGED_IN = "not_logged_in"
    EXPIRED = "expired"
    NOT_REQUIRED = "not_required"
    UNKNOWN = "unknown"


class ExecutorCapability(DomainModel):
    code_fix: bool = False
    test_fix: bool = False
    backend_domain: bool = False
    api_implementation: bool = False
    frontend_implementation: bool = False
    documentation: bool = False
    ledger_evidence: bool = False
    route_planning: bool = False
    design_explanation: bool = False
    git_read_only: bool = False
    git_write: bool = False
    shell_execution: bool = False
    file_system_write: bool = False
    requires_network: bool = False
    requires_auth_token: bool = False
    max_context_tokens: int | None = None

    @field_validator("max_context_tokens")
    @classmethod
    def validate_max_context_tokens(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("max_context_tokens must be a positive integer when provided")
        return value


class ExecutorConfigDiscovery(DomainModel):
    source: ExecutorConfigSource = ExecutorConfigSource.NONE
    cli_installed: bool = False
    binary_path_hint: str | None = None
    cli_version: str | None = None
    login_status: ExecutorLoginStatus = ExecutorLoginStatus.UNKNOWN
    default_model: str | None = None
    permission_mode: ExecutorPermissionModel | None = None
    native_config_valid: bool = False
    env_var_count: int = 0
    token_configured: bool = False
    last_checked_at: datetime | None = None
    discovery_error: str | None = None

    @field_validator(
        "binary_path_hint",
        "cli_version",
        "default_model",
        "discovery_error",
        mode="before",
    )
    @classmethod
    def trim_optional_string(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("env_var_count")
    @classmethod
    def validate_env_var_count(cls, value: int) -> int:
        if value < 0:
            raise ValueError("env_var_count must be greater than or equal to 0")
        return value

    @field_validator("last_checked_at")
    @classmethod
    def normalize_last_checked_at(cls, value: datetime | None) -> datetime | None:
        return ensure_utc_datetime(value)


class ExecutorProfile(DomainModel):
    executor_id: str
    display_name: str
    description: str | None = None
    provider: ExecutorProvider
    binary_name: str | None = None
    binary_discovery_strategy: ExecutorBinaryDiscoveryStrategy
    capabilities: ExecutorCapability = Field(default_factory=ExecutorCapability)
    config_discovery: ExecutorConfigDiscovery = Field(
        default_factory=ExecutorConfigDiscovery,
    )
    permission_model: ExecutorPermissionModel = ExecutorPermissionModel.DEFAULT_DENY
    status: ExecutorStatus = ExecutorStatus.UNKNOWN
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator(
        "executor_id",
        "display_name",
        "description",
        "binary_name",
        mode="before",
    )
    @classmethod
    def trim_strings(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("executor_id", "display_name")
    @classmethod
    def require_non_empty_string(cls, value: str) -> str:
        if not value:
            raise ValueError("value must not be empty")
        return value

    @field_validator("created_at", "updated_at")
    @classmethod
    def normalize_profile_datetime(cls, value: datetime) -> datetime:
        normalized = ensure_utc_datetime(value)
        if normalized is None:
            raise ValueError("datetime must not be None")
        return normalized

    @model_validator(mode="after")
    def validate_binary_name_for_strategy(self) -> "ExecutorProfile":
        if self.binary_discovery_strategy in {
            ExecutorBinaryDiscoveryStrategy.PATH_LOOKUP,
            ExecutorBinaryDiscoveryStrategy.MANAGED_PATH,
        } and not self.binary_name:
            raise ValueError("binary_name is required for binary discovery strategies")
        return self


class ExecutorRegistrySnapshot(DomainModel):
    profiles: list[ExecutorProfile] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_executor_ids(self) -> "ExecutorRegistrySnapshot":
        executor_ids = [profile.executor_id for profile in self.profiles]
        if len(executor_ids) != len(set(executor_ids)):
            raise ValueError("executor_id values must be unique")
        return self

    def get_profile(self, executor_id: str) -> ExecutorProfile | None:
        normalized_id = executor_id.strip()
        return next(
            (profile for profile in self.profiles if profile.executor_id == normalized_id),
            None,
        )

    def available_profiles(self) -> list[ExecutorProfile]:
        return [
            profile
            for profile in self.profiles
            if profile.status == ExecutorStatus.AVAILABLE
        ]

    def profiles_with_capability(self, capability_name: str) -> list[ExecutorProfile]:
        normalized_name = capability_name.strip()
        if not normalized_name:
            return []
        return [
            profile
            for profile in self.profiles
            if getattr(profile.capabilities, normalized_name, False) is True
        ]


ExecutorRegistry = ExecutorRegistrySnapshot


class ExecutorLaunchSafetyFlags(DomainModel):
    no_secret_exposure: bool = True
    launch_preview_only: bool = True
    no_external_process_launch: bool = True
    no_product_runtime_git_write: bool = True
    requires_human_confirmation_before_p9: bool = True


class ExecutorLaunchPreview(DomainModel):
    ready: bool = False
    reason_code: str | None = None
    executor_id: str
    launch_command_preview: str
    launch_cwd_hint: str | None = None
    workspace_bound: bool = False
    env_var_count: int = 0
    token_configured: bool = False
    permission_mode: ExecutorPermissionModel | None = None
    model_name: str | None = None
    estimated_cost_warning: str | None = None
    blocking_reasons: list[str] = Field(default_factory=list)
    safety_flags: ExecutorLaunchSafetyFlags = Field(
        default_factory=ExecutorLaunchSafetyFlags,
    )
    contract_kind: Literal["preview_only"] = "preview_only"

    @field_validator(
        "reason_code",
        "executor_id",
        "launch_command_preview",
        "launch_cwd_hint",
        "model_name",
        "estimated_cost_warning",
        mode="before",
    )
    @classmethod
    def trim_preview_strings(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("executor_id", "launch_command_preview")
    @classmethod
    def require_preview_string(cls, value: str) -> str:
        if not value:
            raise ValueError("value must not be empty")
        return value

    @field_validator("env_var_count")
    @classmethod
    def validate_preview_env_var_count(cls, value: int) -> int:
        if value < 0:
            raise ValueError("env_var_count must be greater than or equal to 0")
        return value

    @field_validator("blocking_reasons", mode="before")
    @classmethod
    def normalize_blocking_reasons(cls, value: Any) -> Any:
        if value is None:
            return []
        return value

    @field_validator("blocking_reasons")
    @classmethod
    def trim_blocking_reasons(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]
