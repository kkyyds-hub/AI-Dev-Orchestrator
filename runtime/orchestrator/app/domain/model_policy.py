"""Model-routing contract primitives shared by executor and worker services."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator

from app.domain._base import DomainModel


class ExecutorRouteMode(StrEnum):
    """Execution mode selected after merging task prefixes and routing policy."""

    SHELL = "shell"
    SIMULATE = "simulate"
    PROVIDER = "provider"


class ExecutorImplicitFallbackMode(StrEnum):
    """Fallback mode reserved when provider execution is unavailable."""

    SIMULATE = "simulate"
    SHELL = "shell"


class ExecutorRoutingTarget(DomainModel):
    """Concrete provider target selected by the routing policy."""

    provider_key: str = Field(min_length=1, max_length=50)
    model_name: str = Field(min_length=1, max_length=100)
    api_family: str = Field(min_length=1, max_length=50)

    @field_validator("provider_key", "model_name", "api_family")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Normalize provider-target string fields."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Routing target fields cannot be blank.")
        return normalized_value


class ExecutorRoutingStrategyHint(DomainModel):
    """Explainable strategy snapshot passed through execution planning."""

    strategy_code: str = Field(min_length=1, max_length=100)
    model_tier: str | None = Field(default=None, max_length=40)
    selected_skill_codes: list[str] = Field(default_factory=list, max_length=12)
    selected_skill_names: list[str] = Field(default_factory=list, max_length=12)
    owner_role_code: str | None = Field(default=None, max_length=40)
    role_model_policy_source: str | None = Field(default=None, max_length=40)
    role_model_policy_desired_tier: str | None = Field(default=None, max_length=40)
    role_model_policy_adjusted_tier: str | None = Field(default=None, max_length=40)
    role_model_policy_final_tier: str | None = Field(default=None, max_length=40)
    role_model_policy_stage_override_applied: bool = False

    @field_validator("selected_skill_codes", "selected_skill_names")
    @classmethod
    def normalize_string_list(cls, value: list[str]) -> list[str]:
        """Trim and deduplicate ordered string lists."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()
        for item in value:
            normalized_item = item.strip()
            if not normalized_item or normalized_item in seen_items:
                continue
            normalized_items.append(normalized_item)
            seen_items.add(normalized_item)
        return normalized_items


class ExecutorModelRoutingContract(DomainModel):
    """Serializable provider-routing contract consumed by the executor."""

    version: str = Field(default="day05.step1", min_length=1, max_length=40)
    primary_mode: ExecutorRouteMode = ExecutorRouteMode.PROVIDER
    primary_target: ExecutorRoutingTarget | None = None
    implicit_fallback_mode: ExecutorImplicitFallbackMode = (
        ExecutorImplicitFallbackMode.SIMULATE
    )
    route_reason: str = Field(min_length=1, max_length=2_000)
    strategy_hint: ExecutorRoutingStrategyHint

