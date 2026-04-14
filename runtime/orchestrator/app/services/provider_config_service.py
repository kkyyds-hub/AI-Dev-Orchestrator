"""Runtime provider settings service for minimal OpenAI configuration."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal

from app.core.config import settings


ProviderConfigSource = Literal["saved_config", "env", "none"]
_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_TIMEOUT_SECONDS = 30
_MASKED_SUFFIX_LENGTH = 4
_MASK_PREFIX = "********"


@dataclass(frozen=True, slots=True)
class OpenAIProviderRuntimeConfig:
    """Effective OpenAI provider runtime config consumed by executor services."""

    api_key: str | None
    base_url: str
    timeout_seconds: int
    source: ProviderConfigSource


@dataclass(frozen=True, slots=True)
class OpenAIProviderConfigSummary:
    """Safe OpenAI provider summary returned to API callers."""

    provider_key: str
    configured: bool
    masked_api_key: str | None
    base_url: str
    timeout_seconds: int
    source: ProviderConfigSource


@dataclass(frozen=True, slots=True)
class OpenAIProviderSavedConfig:
    """Raw OpenAI provider config persisted under runtime data directory."""

    api_key: str | None
    base_url: str
    timeout_seconds: int


class ProviderConfigService:
    """Read and persist minimal OpenAI provider settings for runtime execution."""

    def __init__(self, *, config_path: Path | None = None) -> None:
        self.config_path = (
            config_path
            if config_path is not None
            else settings.runtime_data_dir
            / "provider-settings"
            / "openai-provider-config.json"
        )

    def get_openai_summary(self) -> OpenAIProviderConfigSummary:
        """Return one safe summary view for OpenAI provider settings."""

        runtime_config = self.resolve_openai_runtime_config()
        return OpenAIProviderConfigSummary(
            provider_key="openai",
            configured=bool(runtime_config.api_key),
            masked_api_key=self._mask_api_key(runtime_config.api_key),
            base_url=runtime_config.base_url,
            timeout_seconds=runtime_config.timeout_seconds,
            source=runtime_config.source,
        )

    def update_openai_config(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int | None = None,
    ) -> OpenAIProviderConfigSummary:
        """Persist one OpenAI config update and return the new safe summary."""

        saved_config = self._load_saved_config()
        next_api_key = saved_config.api_key if saved_config is not None else None
        next_base_url = (
            saved_config.base_url
            if saved_config is not None
            else self._normalize_base_url(settings.openai_base_url)
        )
        next_timeout_seconds = (
            saved_config.timeout_seconds
            if saved_config is not None
            else self._normalize_timeout_seconds(settings.openai_timeout_seconds)
        )

        if api_key is not None:
            next_api_key = self._normalize_optional_str(api_key)
        if base_url is not None:
            next_base_url = self._normalize_base_url(base_url)
        if timeout_seconds is not None:
            next_timeout_seconds = self._normalize_timeout_seconds(timeout_seconds)

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(
                {
                    "provider_key": "openai",
                    "api_key": next_api_key,
                    "base_url": next_base_url,
                    "timeout_seconds": next_timeout_seconds,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return self.get_openai_summary()

    def resolve_openai_runtime_config(self) -> OpenAIProviderRuntimeConfig:
        """Resolve one effective runtime config: saved config first, then env fallback."""

        saved_config = self._load_saved_config()
        env_api_key = self._normalize_optional_str(settings.openai_api_key)
        env_base_url = self._normalize_base_url(settings.openai_base_url)
        env_timeout_seconds = self._normalize_timeout_seconds(settings.openai_timeout_seconds)

        if saved_config is not None:
            resolved_api_key = saved_config.api_key or env_api_key
            if saved_config.api_key:
                source: ProviderConfigSource = "saved_config"
            elif env_api_key:
                source = "env"
            else:
                source = "saved_config"
            return OpenAIProviderRuntimeConfig(
                api_key=resolved_api_key,
                base_url=saved_config.base_url,
                timeout_seconds=saved_config.timeout_seconds,
                source=source,
            )

        if env_api_key:
            return OpenAIProviderRuntimeConfig(
                api_key=env_api_key,
                base_url=env_base_url,
                timeout_seconds=env_timeout_seconds,
                source="env",
            )

        return OpenAIProviderRuntimeConfig(
            api_key=None,
            base_url=env_base_url,
            timeout_seconds=env_timeout_seconds,
            source="none",
        )

    def _load_saved_config(self) -> OpenAIProviderSavedConfig | None:
        """Load one saved OpenAI config payload from runtime storage."""

        if not self.config_path.exists():
            return None

        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        if not isinstance(payload, dict):
            return None

        raw_api_key = payload.get("api_key")
        raw_base_url = payload.get("base_url")
        raw_timeout_seconds = payload.get("timeout_seconds")

        api_key = (
            self._normalize_optional_str(raw_api_key) if isinstance(raw_api_key, str) else None
        )
        base_url = self._normalize_base_url(
            raw_base_url if isinstance(raw_base_url, str) else settings.openai_base_url
        )
        timeout_seconds = self._normalize_timeout_seconds(raw_timeout_seconds)

        return OpenAIProviderSavedConfig(
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )

    @staticmethod
    def _normalize_optional_str(value: str | None) -> str | None:
        """Normalize one optional string by trimming and mapping blank to missing."""

        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return normalized

    @staticmethod
    def _normalize_base_url(value: str | None) -> str:
        """Normalize one base URL with default fallback."""

        if value is None:
            return _DEFAULT_BASE_URL
        normalized = value.strip().rstrip("/")
        if not normalized:
            return _DEFAULT_BASE_URL
        return normalized

    @staticmethod
    def _normalize_timeout_seconds(value: object) -> int:
        """Normalize one timeout value with lower-bound guard."""

        if isinstance(value, bool):
            return _DEFAULT_TIMEOUT_SECONDS
        if isinstance(value, int):
            timeout_seconds = value
        elif isinstance(value, float):
            timeout_seconds = int(value)
        elif isinstance(value, str):
            try:
                timeout_seconds = int(value.strip())
            except ValueError:
                return _DEFAULT_TIMEOUT_SECONDS
        else:
            return _DEFAULT_TIMEOUT_SECONDS

        if timeout_seconds < 1:
            return _DEFAULT_TIMEOUT_SECONDS
        return timeout_seconds

    @staticmethod
    def _mask_api_key(api_key: str | None) -> str | None:
        """Mask one API key so API responses never expose full plaintext."""

        if not api_key:
            return None
        normalized = api_key.strip()
        if len(normalized) <= _MASKED_SUFFIX_LENGTH:
            return _MASK_PREFIX
        suffix = normalized[-_MASKED_SUFFIX_LENGTH:]
        return f"{_MASK_PREFIX}{suffix}"
