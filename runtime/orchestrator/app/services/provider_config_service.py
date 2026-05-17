"""Runtime provider settings service for OpenAI-compatible configuration."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from app.core.config import settings


ProviderConfigSource = Literal["saved_config", "env", "none"]
ProviderModelPreset = Literal["openai", "deepseek", "custom"]
DetectedProviderType = Literal["openai", "deepseek", "openai_compatible"]

MODEL_TIERS: tuple[str, str, str] = ("economy", "balanced", "premium")
_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_TIMEOUT_SECONDS = 120
_MASKED_SUFFIX_LENGTH = 4
_MASK_PREFIX = "********"
_OPENAI_PRESET_MODELS = {
    "economy": "gpt-5.5",
    "balanced": "gpt-5.5",
    "premium": "gpt-5.5",
}
_DEEPSEEK_PRESET_MODELS = {
    "economy": "deepseek-v4-pro",
    "balanced": "deepseek-v4-pro",
    "premium": "deepseek-v4-pro",
}


@dataclass(frozen=True, slots=True)
class OpenAIProviderRuntimeConfig:
    """Effective OpenAI-compatible provider runtime config consumed by services."""

    api_key: str | None
    base_url: str
    timeout_seconds: int
    source: ProviderConfigSource
    detected_provider_type: DetectedProviderType
    model_preset: ProviderModelPreset
    model_names: dict[str, str]


@dataclass(frozen=True, slots=True)
class OpenAIProviderConfigSummary:
    """Safe provider summary returned to API callers."""

    provider_key: str
    configured: bool
    masked_api_key: str | None
    base_url: str
    timeout_seconds: int
    source: ProviderConfigSource
    detected_provider_type: DetectedProviderType
    model_preset: ProviderModelPreset
    model_names: dict[str, str]


@dataclass(frozen=True, slots=True)
class OpenAIProviderSavedConfig:
    """Raw provider config persisted under runtime data directory."""

    api_key: str | None
    base_url: str
    timeout_seconds: int
    model_preset: ProviderModelPreset
    model_names: dict[str, str]


class ProviderConfigService:
    """Read and persist OpenAI-compatible provider settings for runtime execution."""

    def __init__(self, *, config_path: Path | None = None) -> None:
        self.config_path = (
            config_path
            if config_path is not None
            else settings.runtime_data_dir
            / "provider-settings"
            / "openai-provider-config.json"
        )

    def get_openai_summary(self) -> OpenAIProviderConfigSummary:
        """Return one safe summary view for provider settings."""

        runtime_config = self.resolve_openai_runtime_config()
        return OpenAIProviderConfigSummary(
            provider_key="openai",
            configured=bool(runtime_config.api_key),
            masked_api_key=self._mask_api_key(runtime_config.api_key),
            base_url=runtime_config.base_url,
            timeout_seconds=runtime_config.timeout_seconds,
            source=runtime_config.source,
            detected_provider_type=runtime_config.detected_provider_type,
            model_preset=runtime_config.model_preset,
            model_names=dict(runtime_config.model_names),
        )

    def update_openai_config(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int | None = None,
        model_preset: str | None = None,
        model_names: dict[str, str] | None = None,
    ) -> OpenAIProviderConfigSummary:
        """Persist one provider config update and return the new safe summary."""

        saved_config = self._load_saved_config()
        env_base_url = self._normalize_base_url(settings.openai_base_url)

        next_api_key = saved_config.api_key if saved_config is not None else None
        next_base_url = saved_config.base_url if saved_config is not None else env_base_url
        next_timeout_seconds = (
            saved_config.timeout_seconds
            if saved_config is not None
            else self._normalize_timeout_seconds(settings.openai_timeout_seconds)
        )
        next_model_preset = (
            saved_config.model_preset
            if saved_config is not None
            else self._default_preset_for_base_url(next_base_url)
        )
        next_model_names = (
            dict(saved_config.model_names)
            if saved_config is not None
            else self._preset_models(next_model_preset)
        )

        if api_key is not None:
            next_api_key = self._normalize_optional_str(api_key)
        if base_url is not None:
            next_base_url = self._normalize_base_url(base_url)
            if model_preset is None and model_names is None:
                next_model_preset = self._default_preset_for_base_url(next_base_url)
                next_model_names = self._preset_models(next_model_preset)
        if timeout_seconds is not None:
            next_timeout_seconds = self._normalize_timeout_seconds(timeout_seconds)
        if model_preset is not None:
            next_model_preset = self._normalize_model_preset(model_preset)
            if next_model_preset != "custom":
                next_model_names = self._preset_models(next_model_preset)
        if model_names is not None:
            next_model_names = self._normalize_model_names(model_names)
            next_model_preset = "custom"

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(
                {
                    "provider_key": "openai",
                    "api_key": next_api_key,
                    "base_url": next_base_url,
                    "timeout_seconds": next_timeout_seconds,
                    "model_preset": next_model_preset,
                    "model_names": next_model_names,
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
        env_api_key = settings.openai_api_key
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
                detected_provider_type=self.detect_provider_type(saved_config.base_url),
                model_preset=saved_config.model_preset,
                model_names=dict(saved_config.model_names),
            )

        default_preset = self._default_preset_for_base_url(env_base_url)
        if env_api_key:
            return OpenAIProviderRuntimeConfig(
                api_key=env_api_key,
                base_url=env_base_url,
                timeout_seconds=env_timeout_seconds,
                source="env",
                detected_provider_type=self.detect_provider_type(env_base_url),
                model_preset=default_preset,
                model_names=self._preset_models(default_preset),
            )

        return OpenAIProviderRuntimeConfig(
            api_key=None,
            base_url=env_base_url,
            timeout_seconds=env_timeout_seconds,
            source="none",
            detected_provider_type=self.detect_provider_type(env_base_url),
            model_preset=default_preset,
            model_names=self._preset_models(default_preset),
        )

    def get_model_name_for_tier(self, tier: str) -> str:
        """Return the configured model name for one strategy tier."""

        runtime_config = self.resolve_openai_runtime_config()
        normalized_tier = tier.strip().lower()
        if normalized_tier in runtime_config.model_names:
            return runtime_config.model_names[normalized_tier]
        return runtime_config.model_names["balanced"]

    def _load_saved_config(self) -> OpenAIProviderSavedConfig | None:
        """Load one saved provider config payload from runtime storage."""

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
        base_url = self._normalize_base_url(
            raw_base_url if isinstance(raw_base_url, str) else settings.openai_base_url
        )

        raw_preset = payload.get("model_preset")
        preset = (
            self._normalize_model_preset(raw_preset)
            if isinstance(raw_preset, str)
            else self._default_preset_for_base_url(base_url)
        )
        raw_model_names = payload.get("model_names")
        if isinstance(raw_model_names, dict):
            model_names = self._normalize_model_names(raw_model_names)
            if raw_preset is None:
                preset = "custom"
        else:
            model_names = self._preset_models(preset)

        return OpenAIProviderSavedConfig(
            api_key=(
                self._normalize_optional_str(raw_api_key)
                if isinstance(raw_api_key, str)
                else None
            ),
            base_url=base_url,
            timeout_seconds=self._normalize_timeout_seconds(raw_timeout_seconds),
            model_preset=preset,
            model_names=model_names,
        )

    @staticmethod
    def detect_provider_type(base_url: str | None) -> DetectedProviderType:
        """Infer the provider type from the OpenAI-compatible base URL."""

        normalized = (base_url or "").strip().lower()
        try:
            hostname = (urlsplit(normalized).hostname or "").lower()
        except ValueError:
            hostname = ""

        target = hostname or normalized
        if "deepseek.com" in target or "deepseek" in target:
            return "deepseek"
        if hostname == "api.openai.com" or target.rstrip("/") == "https://api.openai.com/v1":
            return "openai"
        return "openai_compatible"

    @classmethod
    def _default_preset_for_base_url(cls, base_url: str) -> ProviderModelPreset:
        detected = cls.detect_provider_type(base_url)
        if detected == "deepseek":
            return "deepseek"
        return "openai"

    @staticmethod
    def _preset_models(preset: ProviderModelPreset) -> dict[str, str]:
        if preset == "deepseek":
            return dict(_DEEPSEEK_PRESET_MODELS)
        if preset == "openai":
            return dict(_OPENAI_PRESET_MODELS)
        raise ValueError("Custom provider model preset requires explicit model_names.")

    @staticmethod
    def _normalize_model_preset(value: str) -> ProviderModelPreset:
        normalized = value.strip().lower()
        if normalized in {"openai", "deepseek", "custom"}:
            return normalized  # type: ignore[return-value]
        raise ValueError("model_preset must be one of: openai, deepseek, custom.")

    @staticmethod
    def _normalize_model_names(value: dict[str, object]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for tier in MODEL_TIERS:
            raw_model_name = value.get(tier)
            if not isinstance(raw_model_name, str):
                raise ValueError(f"model_names.{tier} must be a non-empty string.")
            model_name = raw_model_name.strip()
            if not model_name:
                raise ValueError(f"model_names.{tier} must be a non-empty string.")
            normalized[tier] = model_name
        return normalized

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
