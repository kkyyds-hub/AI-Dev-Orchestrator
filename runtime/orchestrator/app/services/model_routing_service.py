"""Translate strategy decisions into executor-facing routing contracts."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.model_policy import (
    ExecutorModelRoutingContract,
    ExecutorRouteMode,
    ExecutorRoutingStrategyHint,
    ExecutorRoutingTarget,
)
from app.domain.run import RunStrategyDecision


@dataclass(slots=True, frozen=True)
class _ProviderBinding:
    """Resolved provider metadata derived from the selected model name."""

    provider_key: str
    api_family: str


class ModelRoutingService:
    """Build minimal provider-routing contracts from strategy decisions."""

    def build_contract_from_strategy_decision(
        self,
        strategy_decision: RunStrategyDecision | None,
    ) -> ExecutorModelRoutingContract | None:
        """Convert one strategy decision into an executor routing contract."""

        if strategy_decision is None:
            return None
        if strategy_decision.model_name is None:
            return None

        provider_binding = self._resolve_provider_binding(strategy_decision.model_name)
        route_reason = (
            strategy_decision.summary.strip()
            or f"Route selected by strategy {strategy_decision.strategy_code}."
        )

        return ExecutorModelRoutingContract(
            primary_mode=ExecutorRouteMode.PROVIDER,
            primary_target=ExecutorRoutingTarget(
                provider_key=provider_binding.provider_key,
                model_name=strategy_decision.model_name,
                api_family=provider_binding.api_family,
            ),
            route_reason=route_reason,
            strategy_hint=ExecutorRoutingStrategyHint(
                strategy_code=strategy_decision.strategy_code,
                model_tier=strategy_decision.model_tier,
                selected_skill_codes=list(strategy_decision.selected_skill_codes),
                selected_skill_names=list(strategy_decision.selected_skill_names),
                owner_role_code=(
                    strategy_decision.owner_role_code.value
                    if strategy_decision.owner_role_code is not None
                    else None
                ),
                role_model_policy_source=strategy_decision.role_model_policy_source,
                role_model_policy_desired_tier=(
                    strategy_decision.role_model_policy_desired_tier
                ),
                role_model_policy_adjusted_tier=(
                    strategy_decision.role_model_policy_adjusted_tier
                ),
                role_model_policy_final_tier=strategy_decision.role_model_policy_final_tier,
                role_model_policy_stage_override_applied=(
                    strategy_decision.role_model_policy_stage_override_applied
                ),
            ),
        )

    @staticmethod
    def _resolve_provider_binding(model_name: str) -> _ProviderBinding:
        """Infer one provider key and API family from the routed model name."""

        normalized_name = model_name.strip().lower()
        if normalized_name.startswith("gpt-"):
            return _ProviderBinding(provider_key="openai", api_family="responses")
        if normalized_name.startswith("claude-"):
            return _ProviderBinding(provider_key="anthropic", api_family="messages")
        if normalized_name.startswith("gemini-"):
            return _ProviderBinding(provider_key="google", api_family="generative_language")
        return _ProviderBinding(provider_key="openai", api_family="responses")

