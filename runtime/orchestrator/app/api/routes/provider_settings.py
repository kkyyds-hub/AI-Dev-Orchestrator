"""Minimal provider-settings endpoints for OpenAI runtime configuration."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.services.provider_config_service import (
    OpenAIProviderConfigSummary,
    ProviderConfigService,
)


class OpenAIProviderSettingsSummaryResponse(BaseModel):
    """Safe OpenAI provider summary returned to the frontend."""

    provider_key: str
    configured: bool
    masked_api_key: str | None = None
    base_url: str
    timeout_seconds: int
    source: Literal["saved_config", "env", "none"]

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
        )


class OpenAIProviderSettingsUpdateRequest(BaseModel):
    """One minimal OpenAI provider config update payload."""

    api_key: str | None = Field(
        default=None,
        description="Optional OpenAI API key. Blank values clear locally saved key.",
    )
    base_url: str | None = Field(
        default=None,
        description="Optional OpenAI base URL.",
    )
    timeout_seconds: int | None = Field(
        default=None,
        ge=1,
        description="Optional OpenAI request timeout (seconds).",
    )


def get_provider_config_service() -> ProviderConfigService:
    """Create one provider config service dependency for request handling."""

    return ProviderConfigService()


router = APIRouter(prefix="/provider-settings", tags=["provider-settings"])


@router.get(
    "/openai",
    response_model=OpenAIProviderSettingsSummaryResponse,
    summary="Get OpenAI provider settings summary",
)
def get_openai_provider_settings(
    provider_config_service: Annotated[
        ProviderConfigService,
        Depends(get_provider_config_service),
    ],
) -> OpenAIProviderSettingsSummaryResponse:
    """Return current OpenAI provider settings summary without plaintext key."""

    summary = provider_config_service.get_openai_summary()
    return OpenAIProviderSettingsSummaryResponse.from_summary(summary)


@router.put(
    "/openai",
    response_model=OpenAIProviderSettingsSummaryResponse,
    summary="Update OpenAI provider settings",
)
def update_openai_provider_settings(
    request: OpenAIProviderSettingsUpdateRequest,
    provider_config_service: Annotated[
        ProviderConfigService,
        Depends(get_provider_config_service),
    ],
) -> OpenAIProviderSettingsSummaryResponse:
    """Persist one minimal OpenAI provider config and return safe summary."""

    try:
        summary = provider_config_service.update_openai_config(
            api_key=request.api_key,
            base_url=request.base_url,
            timeout_seconds=request.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return OpenAIProviderSettingsSummaryResponse.from_summary(summary)
