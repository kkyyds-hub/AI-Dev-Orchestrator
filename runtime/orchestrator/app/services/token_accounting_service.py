"""Day06 Step1 minimal token accounting service."""

from __future__ import annotations

from math import ceil

from app.domain.model_policy import ExecutorRouteMode
from app.domain.prompt_contract import (
    BuiltPromptEnvelope,
    PromptTemplateRef,
    ProviderUsageReceipt,
    TokenAccountingMode,
    TokenAccountingSnapshot,
)

_CHARS_PER_TOKEN = 4
_PROMPT_COST_PER_1K_TOKENS_USD = 0.0015
_COMPLETION_COST_PER_1K_TOKENS_USD = 0.0030
_HEURISTIC_PRICING_SOURCE_BY_MODE = {
    ExecutorRouteMode.PROVIDER.value: "heuristic.provider.char_count.v1",
    "provider_mock": "heuristic.provider_mock.char_count.v1",
    ExecutorRouteMode.SHELL.value: "heuristic.shell.char_count.v1",
    ExecutorRouteMode.SIMULATE.value: "heuristic.simulate.char_count.v1",
}
_DEFAULT_HEURISTIC_PRICING_SOURCE = "heuristic.char_count.v1"


class TokenAccountingService:
    """Estimate token usage until provider-side usage reports land."""

    def build_snapshot(
        self,
        *,
        prompt_envelope: BuiltPromptEnvelope | None,
        completion_text: str,
        execution_mode: str | None = None,
        provider_usage_receipt: ProviderUsageReceipt | None = None,
    ) -> TokenAccountingSnapshot:
        """Build one token accounting snapshot from prompt and completion text."""

        if provider_usage_receipt is not None:
            return self._build_provider_reported_snapshot(
                prompt_envelope=prompt_envelope,
                provider_usage_receipt=provider_usage_receipt,
            )

        prompt_text = prompt_envelope.prompt_text if prompt_envelope is not None else ""
        prompt_tokens = self._estimate_tokens(prompt_text)
        completion_tokens = self._estimate_tokens(completion_text)
        estimated_cost = round(
            (prompt_tokens / 1_000) * _PROMPT_COST_PER_1K_TOKENS_USD
            + (completion_tokens / 1_000) * _COMPLETION_COST_PER_1K_TOKENS_USD,
            6,
        )

        template_ref = (
            prompt_envelope.template_ref
            if prompt_envelope is not None
            else PromptTemplateRef(
                prompt_key="task_execution.legacy_fallback",
                version="day06.step1",
                description="Fallback token accounting contract without a built prompt envelope.",
            )
        )

        normalized_mode = self._normalize_execution_mode(execution_mode)
        provider_key, model_name = self._resolve_heuristic_provider_binding(
            execution_mode=normalized_mode,
            prompt_envelope=prompt_envelope,
        )
        return TokenAccountingSnapshot(
            accounting_mode=TokenAccountingMode.HEURISTIC,
            template_ref=template_ref,
            provider_key=provider_key,
            model_name=model_name,
            provider_receipt_id=None,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated_cost_usd=estimated_cost,
            pricing_source=self._resolve_heuristic_pricing_source(normalized_mode),
        )

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Approximate token usage with a simple text-length heuristic."""

        normalized_text = text.strip()
        if not normalized_text:
            return 0
        return max(1, ceil(len(normalized_text) / _CHARS_PER_TOKEN))

    @staticmethod
    def _normalize_execution_mode(execution_mode: str | None) -> str | None:
        """Normalize one execution mode value for downstream semantic branching."""

        if execution_mode is None:
            return None

        normalized_mode = execution_mode.strip().lower()
        return normalized_mode or None

    @staticmethod
    def _is_provider_execution_mode(execution_mode: str | None) -> bool:
        """Return whether one execution mode represents a provider-backed path."""

        return execution_mode is not None and execution_mode.startswith("provider")

    def _build_provider_reported_snapshot(
        self,
        *,
        prompt_envelope: BuiltPromptEnvelope | None,
        provider_usage_receipt: ProviderUsageReceipt,
    ) -> TokenAccountingSnapshot:
        """Prefer normalized provider receipts whenever one is available."""

        if prompt_envelope is not None:
            if prompt_envelope.provider_key != provider_usage_receipt.provider_key:
                raise ValueError("provider_usage_receipt.provider_key does not match prompt.")
            if prompt_envelope.model_name != provider_usage_receipt.model_name:
                raise ValueError("provider_usage_receipt.model_name does not match prompt.")

        template_ref = (
            prompt_envelope.template_ref
            if prompt_envelope is not None
            else PromptTemplateRef(
                prompt_key="task_execution.provider_receipt_fallback",
                version="day06.step10",
                description="Fallback prompt ref when only provider usage receipt exists.",
            )
        )
        return TokenAccountingSnapshot(
            accounting_mode=TokenAccountingMode.PROVIDER_REPORTED,
            template_ref=template_ref,
            provider_key=provider_usage_receipt.provider_key,
            model_name=provider_usage_receipt.model_name,
            provider_receipt_id=provider_usage_receipt.receipt_id,
            prompt_tokens=provider_usage_receipt.prompt_tokens,
            completion_tokens=provider_usage_receipt.completion_tokens,
            total_tokens=provider_usage_receipt.total_tokens,
            estimated_cost_usd=provider_usage_receipt.estimated_cost_usd,
            pricing_source=provider_usage_receipt.pricing_source,
        )

    def _resolve_heuristic_provider_binding(
        self,
        *,
        execution_mode: str | None,
        prompt_envelope: BuiltPromptEnvelope | None,
    ) -> tuple[str | None, str | None]:
        """Keep provider fields only on provider-backed heuristic paths."""

        if not self._is_provider_execution_mode(execution_mode) or prompt_envelope is None:
            return None, None

        return prompt_envelope.provider_key, prompt_envelope.model_name

    @staticmethod
    def _resolve_heuristic_pricing_source(execution_mode: str | None) -> str:
        """Return the stable heuristic pricing source for one execution mode."""

        if execution_mode is None:
            return _DEFAULT_HEURISTIC_PRICING_SOURCE

        return _HEURISTIC_PRICING_SOURCE_BY_MODE.get(
            execution_mode,
            _DEFAULT_HEURISTIC_PRICING_SOURCE,
        )
