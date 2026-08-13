"""Governed provider configuration bridge for the Director Runtime process.

This module owns the single, bounded translation between the existing Python
`ProviderConfigService` (the authoritative provider settings authority) and the
process-scoped environment consumed by the TypeScript Director Runtime child.

It intentionally does not read provider JSON files, re-derive base URL
normalization, re-detect provider type, or re-resolve model presets. All of that
remains inside `ProviderConfigService`. The only responsibility here is to turn
one resolved provider config into a controlled child environment whose profile
identifier can later be correlated against the runtime request.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.provider_config_service import (
    OpenAIProviderRuntimeConfig,
    ProviderConfigService,
)

# Canonical provider profile id for the OpenAI-compatible provider slot. The
# runtime request must name this exact profile before any credential is injected.
OPENAI_PROVIDER_PROFILE_ID = "openai"

# Process-scoped environment keys injected into the Director Runtime child.
ENV_PROVIDER_MODE = "DIRECTOR_RUNTIME_PROVIDER_MODE"
ENV_PROVIDER_BASE_URL = "DIRECTOR_RUNTIME_PROVIDER_BASE_URL"
ENV_PROVIDER_API_KEY = "DIRECTOR_RUNTIME_PROVIDER_API_KEY"
ENV_PROVIDER_PROFILE_ID = "DIRECTOR_RUNTIME_PROVIDER_PROFILE_ID"

# Runtime modes understood by the Director Runtime child. The synthetic mode is
# the implicit default and is never produced by this bridge.
PROVIDER_MODE_OPENAI_COMPATIBLE = "openai_compatible"


class DirectorRuntimeProviderConfigError(RuntimeError):
    """Fail-closed provider bridge resolution failure."""


@dataclass(frozen=True, slots=True)
class DirectorRuntimeProviderEnvironment:
    """Controlled process environment for one provider-backed Director Runtime child."""

    provider_profile_id: str
    mode: str
    base_url: str | None
    api_key: str | None

    def to_environment(self) -> dict[str, str]:
        """Render the process-scoped environment mapping, omitting missing secrets."""

        environment: dict[str, str] = {
            ENV_PROVIDER_MODE: self.mode,
            ENV_PROVIDER_PROFILE_ID: self.provider_profile_id,
        }
        if self.base_url is not None:
            environment[ENV_PROVIDER_BASE_URL] = self.base_url
        if self.api_key is not None:
            environment[ENV_PROVIDER_API_KEY] = self.api_key
        return environment


class DirectorRuntimeProviderConfigService:
    """Bridge one `ProviderConfigService` profile into a Director Runtime child environment."""

    def __init__(self, *, provider_config_service: ProviderConfigService | None = None) -> None:
        self._provider_config_service = provider_config_service or ProviderConfigService()

    def resolve_openai_runtime_config(self) -> OpenAIProviderRuntimeConfig:
        """Return the effective OpenAI-compatible runtime config without re-derivation."""

        return self._provider_config_service.resolve_openai_runtime_config()

    def build_openai_runtime_environment(
        self,
        *,
        provider_profile_id: str,
    ) -> DirectorRuntimeProviderEnvironment:
        """Resolve one profile into a controlled child environment, failing closed.

        Only the governed OpenAI-compatible profile slot is addressable. A request
        naming any other profile id fails closed here, and the resulting child
        environment still carries the resolved profile id so the runtime can
        correlate it against the request before any provider call is made.
        """

        if provider_profile_id != OPENAI_PROVIDER_PROFILE_ID:
            raise DirectorRuntimeProviderConfigError(
                "director_runtime_provider_profile_unknown"
            )

        config = self._provider_config_service.resolve_openai_runtime_config()
        return DirectorRuntimeProviderEnvironment(
            provider_profile_id=OPENAI_PROVIDER_PROFILE_ID,
            mode=PROVIDER_MODE_OPENAI_COMPATIBLE,
            base_url=config.base_url,
            api_key=config.api_key,
        )


__all__ = (
    "DirectorRuntimeProviderConfigError",
    "DirectorRuntimeProviderConfigService",
    "DirectorRuntimeProviderEnvironment",
    "ENV_PROVIDER_API_KEY",
    "ENV_PROVIDER_BASE_URL",
    "ENV_PROVIDER_MODE",
    "ENV_PROVIDER_PROFILE_ID",
    "OPENAI_PROVIDER_PROFILE_ID",
    "PROVIDER_MODE_OPENAI_COMPATIBLE",
)
