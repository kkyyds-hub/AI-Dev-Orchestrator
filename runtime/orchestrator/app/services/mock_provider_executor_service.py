"""Minimal mock provider executor used by Day05 Step6."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import TYPE_CHECKING

from app.domain.model_policy import ExecutorModelRoutingContract
from app.domain.prompt_contract import BuiltPromptEnvelope, ProviderUsageReceipt
from app.domain.task import Task

if TYPE_CHECKING:
    from app.services.context_builder_service import TaskContextPackage


@dataclass(slots=True, frozen=True)
class MockProviderExecutionResponse:
    """One minimal provider-like execution response for Day05 mock routing."""

    success: bool
    mode: str
    summary: str
    prompt_key: str | None = None
    prompt_char_count: int = 0
    provider_usage_receipt: ProviderUsageReceipt | None = None


_CHARS_PER_TOKEN = 4
_PROMPT_COST_PER_1K_TOKENS_USD = 0.0015
_COMPLETION_COST_PER_1K_TOKENS_USD = 0.0030
_MOCK_PROVIDER_RECEIPT_SOURCE = "mock_provider.receipt.v1"


class MockProviderExecutorService:
    """Execute one provider plan through a local mock provider path."""

    def execute(
        self,
        *,
        task: Task,
        payload: str,
        routing_contract: ExecutorModelRoutingContract,
        prompt_envelope: BuiltPromptEnvelope,
        context_package: "TaskContextPackage | None" = None,
    ) -> MockProviderExecutionResponse:
        """Return one normalized mock-provider execution response."""

        if routing_contract.primary_target is None:
            raise ValueError("Mock provider execution requires a primary target.")
        if prompt_envelope.provider_key != routing_contract.primary_target.provider_key:
            raise ValueError("Prompt envelope provider_key does not match routing contract.")
        if prompt_envelope.model_name != routing_contract.primary_target.model_name:
            raise ValueError("Prompt envelope model_name does not match routing contract.")

        target = routing_contract.primary_target
        summary_body = payload if payload else task.title
        context_suffix = (
            f" Context package: {context_package.context_summary}"
            if context_package is not None
            else ""
        )
        skill_suffix = ""
        if routing_contract.strategy_hint.selected_skill_codes:
            skill_suffix = (
                " Skills: "
                + ", ".join(routing_contract.strategy_hint.selected_skill_codes)
                + "."
            )

        summary = (
            "Mock provider execution succeeded. "
            f"Target {target.provider_key}/{target.model_name} "
            f"via {target.api_family}. "
            f"Prompt {prompt_envelope.template_ref.prompt_key}@{prompt_envelope.template_ref.version} "
            f"({prompt_envelope.prompt_char_count} chars). "
            f"Strategy {routing_contract.strategy_hint.strategy_code} "
            f"processed task '{task.title}' with payload: {summary_body}. "
            f"{routing_contract.route_reason}{skill_suffix}{context_suffix}"
        )
        prompt_tokens = self._estimate_tokens(prompt_envelope.prompt_text)
        completion_tokens = self._estimate_tokens(summary)
        provider_usage_receipt = ProviderUsageReceipt(
            provider_key=target.provider_key,
            model_name=target.model_name,
            receipt_id=f"mock-receipt-{task.id.hex[:12]}",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated_cost_usd=round(
                (prompt_tokens / 1_000) * _PROMPT_COST_PER_1K_TOKENS_USD
                + (completion_tokens / 1_000) * _COMPLETION_COST_PER_1K_TOKENS_USD,
                6,
            ),
            pricing_source=_MOCK_PROVIDER_RECEIPT_SOURCE,
        )
        return MockProviderExecutionResponse(
            success=True,
            mode="provider_mock",
            summary=summary,
            prompt_key=prompt_envelope.template_ref.prompt_key,
            prompt_char_count=prompt_envelope.prompt_char_count,
            provider_usage_receipt=provider_usage_receipt,
        )

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Approximate token usage for the mock-provider receipt."""

        normalized_text = text.strip()
        if not normalized_text:
            return 0
        return max(1, ceil(len(normalized_text) / _CHARS_PER_TOKEN))
