"""Safe metadata-only discovery service for P8 executor configuration.

The service owns a small built-in executor manifest and combines it with an
injected probe result. The default probe is intentionally no-op: it does not read
local configuration, inspect environment variable values, execute CLI commands,
or launch external processes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from pydantic import Field

from app.domain._base import DomainModel
from app.domain.executor_config import (
    ExecutorBinaryDiscoveryStrategy,
    ExecutorCapability,
    ExecutorConfigDiscovery,
    ExecutorConfigSource,
    ExecutorLoginStatus,
    ExecutorPermissionModel,
    ExecutorProfile,
    ExecutorProvider,
    ExecutorRegistrySnapshot,
    ExecutorStatus,
)


_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_ -]?key\s*[:=]\s*)\S+"),
    re.compile(r"(?i)(auth[_ -]?token\s*[:=]\s*)\S+"),
    re.compile(r"(?i)(token\s*[:=]\s*)\S+"),
    re.compile(r"(?i)(secret\s*[:=]\s*)\S+"),
    re.compile(r"(?i)(password\s*[:=]\s*)\S+"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"sk-[A-Za-z0-9_-]+"),
]


class ExecutorProfileManifest(DomainModel):
    executor_id: str
    display_name: str
    description: str | None = None
    provider: ExecutorProvider
    binary_name: str | None = None
    binary_discovery_strategy: ExecutorBinaryDiscoveryStrategy
    permission_model: ExecutorPermissionModel
    capabilities: ExecutorCapability = Field(default_factory=ExecutorCapability)
    disabled: bool = False


class ExecutorDiscoveryProbe(Protocol):
    def discover(
        self,
        executor_id: str,
        binary_name: str | None,
        strategy: ExecutorBinaryDiscoveryStrategy,
    ) -> ExecutorConfigDiscovery:
        """Return safe discovery metadata for a single executor."""


@dataclass(frozen=True)
class NoopExecutorDiscoveryProbe:
    """Safe default probe that performs no real local discovery."""

    def discover(
        self,
        executor_id: str,
        binary_name: str | None,
        strategy: ExecutorBinaryDiscoveryStrategy,
    ) -> ExecutorConfigDiscovery:
        login_status = (
            ExecutorLoginStatus.NOT_REQUIRED
            if strategy == ExecutorBinaryDiscoveryStrategy.API_ONLY
            else ExecutorLoginStatus.UNKNOWN
        )
        return ExecutorConfigDiscovery(
            source=ExecutorConfigSource.NONE,
            cli_installed=False,
            binary_path_hint=None,
            cli_version=None,
            login_status=login_status,
            default_model=None,
            permission_mode=None,
            native_config_valid=False,
            env_var_count=0,
            token_configured=False,
            last_checked_at=None,
            discovery_error=None,
        )


BUILT_IN_EXECUTOR_MANIFESTS: tuple[ExecutorProfileManifest, ...] = (
    ExecutorProfileManifest(
        executor_id="codex",
        display_name="Codex",
        description="可用于代码修改和测试修复的外部执行器配置摘要。",
        provider=ExecutorProvider.OPENAI,
        binary_name="codex",
        binary_discovery_strategy=ExecutorBinaryDiscoveryStrategy.PATH_LOOKUP,
        permission_model=ExecutorPermissionModel.DEFAULT_DENY,
        capabilities=ExecutorCapability(
            code_fix=True,
            test_fix=True,
            api_implementation=True,
            frontend_implementation=True,
            git_read_only=True,
            shell_execution=True,
            file_system_write=True,
            requires_auth_token=True,
        ),
    ),
    ExecutorProfileManifest(
        executor_id="claude_code",
        display_name="Claude Code",
        description="可用于代码修改和测试修复的外部执行器配置摘要。",
        provider=ExecutorProvider.ANTHROPIC,
        binary_name="claude",
        binary_discovery_strategy=ExecutorBinaryDiscoveryStrategy.PATH_LOOKUP,
        permission_model=ExecutorPermissionModel.DEFAULT_DENY,
        capabilities=ExecutorCapability(
            code_fix=True,
            test_fix=True,
            api_implementation=True,
            frontend_implementation=True,
            git_read_only=True,
            shell_execution=True,
            file_system_write=True,
            requires_auth_token=True,
        ),
    ),
    ExecutorProfileManifest(
        executor_id="deepseek_api",
        display_name="DeepSeek API",
        description="可用于文档、路线规划和设计解释的接口型执行器配置摘要。",
        provider=ExecutorProvider.DEEPSEEK,
        binary_name=None,
        binary_discovery_strategy=ExecutorBinaryDiscoveryStrategy.API_ONLY,
        permission_model=ExecutorPermissionModel.API_ONLY,
        capabilities=ExecutorCapability(
            documentation=True,
            ledger_evidence=True,
            route_planning=True,
            design_explanation=True,
            requires_network=True,
            requires_auth_token=True,
        ),
    ),
)


class ExecutorConfigDiscoveryService:
    def __init__(
        self,
        probe: ExecutorDiscoveryProbe | None = None,
        manifests: tuple[ExecutorProfileManifest, ...] | None = None,
    ) -> None:
        self._probe = probe or NoopExecutorDiscoveryProbe()
        self._manifests = manifests or BUILT_IN_EXECUTOR_MANIFESTS

    def get_registry_snapshot(self) -> ExecutorRegistrySnapshot:
        profiles = [self._build_profile(manifest) for manifest in self._manifests]
        return ExecutorRegistrySnapshot(profiles=profiles)

    def get_profile(self, executor_id: str) -> ExecutorProfile | None:
        return self.get_registry_snapshot().get_profile(executor_id)

    def available_profiles(self) -> list[ExecutorProfile]:
        return self.get_registry_snapshot().available_profiles()

    def available_profiles_with_capability(
        self,
        capability_name: str,
    ) -> list[ExecutorProfile]:
        return [
            profile
            for profile in self.available_profiles()
            if getattr(profile.capabilities, capability_name.strip(), False) is True
        ]

    def profiles_with_capability(self, capability_name: str) -> list[ExecutorProfile]:
        return self.get_registry_snapshot().profiles_with_capability(capability_name)

    def _build_profile(self, manifest: ExecutorProfileManifest) -> ExecutorProfile:
        raw_discovery = self._probe.discover(
            manifest.executor_id,
            manifest.binary_name,
            manifest.binary_discovery_strategy,
        )
        discovery = raw_discovery.model_copy(
            update={
                "discovery_error": sanitize_discovery_error(
                    raw_discovery.discovery_error,
                ),
            },
        )
        return ExecutorProfile(
            executor_id=manifest.executor_id,
            display_name=manifest.display_name,
            description=manifest.description,
            provider=manifest.provider,
            binary_name=manifest.binary_name,
            binary_discovery_strategy=manifest.binary_discovery_strategy,
            capabilities=manifest.capabilities,
            config_discovery=discovery,
            permission_model=manifest.permission_model,
            status=synthesize_executor_status(manifest, discovery),
        )


def synthesize_executor_status(
    manifest: ExecutorProfileManifest,
    discovery: ExecutorConfigDiscovery,
) -> ExecutorStatus:
    if manifest.disabled:
        return ExecutorStatus.DISABLED

    if manifest.binary_discovery_strategy == ExecutorBinaryDiscoveryStrategy.API_ONLY:
        return (
            ExecutorStatus.AVAILABLE
            if discovery.token_configured
            else ExecutorStatus.NOT_CONFIGURED
        )

    if not discovery.cli_installed:
        return ExecutorStatus.NOT_INSTALLED

    if manifest.capabilities.requires_auth_token and not discovery.token_configured:
        if discovery.login_status != ExecutorLoginStatus.LOGGED_IN:
            return ExecutorStatus.NOT_CONFIGURED

    if discovery.login_status == ExecutorLoginStatus.LOGGED_IN or discovery.token_configured:
        return ExecutorStatus.AVAILABLE

    if discovery.discovery_error:
        return ExecutorStatus.UNKNOWN

    return ExecutorStatus.UNKNOWN


def sanitize_discovery_error(message: str | None) -> str | None:
    if message is None:
        return None

    sanitized = message.strip()
    if not sanitized:
        return None

    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub(_redacted_match, sanitized)

    if len(sanitized) > 240:
        sanitized = f"{sanitized[:237]}..."

    return sanitized


def _redacted_match(match: re.Match[str]) -> str:
    value = match.group(0)
    lower = value.lower()
    if lower.startswith("bearer"):
        return "Bearer [redacted]"
    if lower.startswith("sk-"):
        return "[redacted]"
    if ":" in value:
        prefix = value.split(":", 1)[0]
        return f"{prefix}: [redacted]"
    if "=" in value:
        prefix = value.split("=", 1)[0]
        return f"{prefix}= [redacted]"
    return "[redacted]"
