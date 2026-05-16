"""Provider-settings endpoints for OpenAI-compatible runtime configuration."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.services.openai_provider_executor_service import (
    OpenAIProviderExecutorService,
)
from app.services.provider_config_service import (
    OpenAIProviderConfigSummary,
    ProviderConfigService,
)


class OpenAIProviderSettingsSummaryResponse(BaseModel):
    """Safe provider summary returned to the frontend."""

    provider_key: str
    configured: bool
    masked_api_key: str | None = None
    base_url: str
    timeout_seconds: int
    source: Literal["saved_config", "env", "none"]
    detected_provider_type: Literal["openai", "deepseek", "openai_compatible"]
    model_preset: Literal["openai", "deepseek", "custom"]
    model_names: dict[str, str]

    @classmethod
    def from_summary(
        cls,
        summary: OpenAIProviderConfigSummary,
    ) -> "OpenAIProviderSettingsSummaryResponse":
        """Convert one service summary into the API response DTO."""

        return cls(
            provider_key=summary.provider_key,
            configured=summary.configured,
            masked_api_key=summary.masked_api_key,
            base_url=summary.base_url,
            timeout_seconds=summary.timeout_seconds,
            source=summary.source,
            detected_provider_type=summary.detected_provider_type,
            model_preset=summary.model_preset,
            model_names=dict(summary.model_names),
        )


class OpenAIProviderTestResponse(BaseModel):
    """Structured result of one provider connectivity test."""

    provider_key: str
    configured: bool
    base_url: str
    auth_valid: bool = False
    endpoint_reachable: bool = False
    api_family: str = "unknown"
    model_name: str
    model_usable: bool = False
    latency_ms: int = 0
    status: str = "failed"
    error_category: str | None = None
    error_summary: str | None = None
    tested_at: str | None = None


class OpenAIProviderSettingsUpdateRequest(BaseModel):
    """One OpenAI-compatible provider config update payload."""

    api_key: str | None = Field(
        default=None,
        description="Optional provider API key. Blank values clear locally saved key.",
    )
    base_url: str | None = Field(
        default=None,
        description="Optional OpenAI-compatible base URL.",
    )
    timeout_seconds: int | None = Field(
        default=None,
        ge=1,
        description="Optional provider request timeout (seconds).",
    )
    model_preset: Literal["openai", "deepseek", "custom"] | None = Field(
        default=None,
        description="Optional preset for economy/balanced/premium model names.",
    )
    model_names: dict[str, str] | None = Field(
        default=None,
        description="Optional custom economy/balanced/premium model names.",
    )


def get_provider_config_service() -> ProviderConfigService:
    """Create one provider config service dependency for request handling."""

    return ProviderConfigService()


router = APIRouter(prefix="/provider-settings", tags=["provider-settings"])


@router.get(
    "/openai",
    response_model=OpenAIProviderSettingsSummaryResponse,
    summary="Get OpenAI-compatible provider settings summary",
)
def get_openai_provider_settings(
    provider_config_service: Annotated[
        ProviderConfigService,
        Depends(get_provider_config_service),
    ],
) -> OpenAIProviderSettingsSummaryResponse:
    """Return current provider settings summary without plaintext key."""

    summary = provider_config_service.get_openai_summary()
    return OpenAIProviderSettingsSummaryResponse.from_summary(summary)


@router.put(
    "/openai",
    response_model=OpenAIProviderSettingsSummaryResponse,
    summary="Update OpenAI-compatible provider settings",
)
def update_openai_provider_settings(
    request: OpenAIProviderSettingsUpdateRequest,
    provider_config_service: Annotated[
        ProviderConfigService,
        Depends(get_provider_config_service),
    ],
) -> OpenAIProviderSettingsSummaryResponse:
    """Persist one provider config and return safe summary."""

    try:
        summary = provider_config_service.update_openai_config(
            api_key=request.api_key,
            base_url=request.base_url,
            timeout_seconds=request.timeout_seconds,
            model_preset=request.model_preset,
            model_names=request.model_names,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return OpenAIProviderSettingsSummaryResponse.from_summary(summary)


@router.post(
    "/openai/test",
    response_model=OpenAIProviderTestResponse,
    summary="Test OpenAI-compatible provider connectivity",
)
def test_openai_provider_connection(
    provider_config_service: Annotated[
        ProviderConfigService,
        Depends(get_provider_config_service),
    ],
) -> OpenAIProviderTestResponse:
    """Run one minimal connectivity test against the configured provider."""

    runtime_config = provider_config_service.resolve_openai_runtime_config()
    executor = OpenAIProviderExecutorService(
        api_key=runtime_config.api_key,
        base_url=runtime_config.base_url,
        timeout_seconds=runtime_config.timeout_seconds,
    )
    result = executor.test_connectivity(
        model_name=runtime_config.model_names.get("balanced", "gpt-5.5")
    )
    result["provider_key"] = runtime_config.detected_provider_type
    return OpenAIProviderTestResponse(**result)
