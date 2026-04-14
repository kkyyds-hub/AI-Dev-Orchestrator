"""Heuristic token and cost estimation for Day 9 / Day06-Step1 contracts."""

from dataclasses import dataclass

from app.domain.prompt_contract import (
    BuiltPromptEnvelope,
    PromptRenderMode,
    PromptTemplateRef,
    TokenAccountingSnapshot,
)
from app.domain.task import Task
from app.services.executor_service import ExecutionResult
from app.services.token_accounting_service import TokenAccountingService
from app.services.verifier_service import VerificationResult


@dataclass(slots=True, frozen=True)
class CostEstimate:
    """Minimal persisted cost estimate for one worker run."""

    prompt_tokens: int
    completion_tokens: int
    estimated_cost: float


class CostEstimatorService:
    """Estimate token usage and cost before real provider accounting exists."""

    def __init__(
        self,
        *,
        token_accounting_service: TokenAccountingService | None = None,
    ) -> None:
        self.token_accounting_service = token_accounting_service or TokenAccountingService()

    def estimate_run_cost(
        self,
        *,
        task: Task,
        execution: ExecutionResult,
        verification: VerificationResult | None,
        prompt_envelope: BuiltPromptEnvelope | None = None,
        token_accounting_snapshot: TokenAccountingSnapshot | None = None,
    ) -> CostEstimate:
        """Build a heuristic cost snapshot from task input and run output."""
        if token_accounting_snapshot is not None:
            return CostEstimate(
                prompt_tokens=token_accounting_snapshot.prompt_tokens,
                completion_tokens=token_accounting_snapshot.completion_tokens,
                estimated_cost=token_accounting_snapshot.estimated_cost_usd,
            )

        completion_parts = [execution.summary.strip()]
        if verification is not None:
            completion_parts.append(verification.summary.strip())

        completion_text = "\n".join(part for part in completion_parts if part)
        effective_prompt_envelope = self._resolve_effective_prompt_envelope(
            task=task,
            prompt_envelope=prompt_envelope,
            execution=execution,
        )
        token_snapshot = self.token_accounting_service.build_snapshot(
            prompt_envelope=effective_prompt_envelope,
            completion_text=completion_text,
            execution_mode=execution.mode,
            provider_usage_receipt=execution.provider_usage_receipt,
        )

        return CostEstimate(
            prompt_tokens=token_snapshot.prompt_tokens,
            completion_tokens=token_snapshot.completion_tokens,
            estimated_cost=token_snapshot.estimated_cost_usd,
        )

    @staticmethod
    def _resolve_effective_prompt_envelope(
        *,
        task: Task,
        prompt_envelope: BuiltPromptEnvelope | None,
        execution: ExecutionResult,
    ) -> BuiltPromptEnvelope | None:
        """Prefer real provider receipts over synthetic prompt fallback envelopes."""

        if prompt_envelope is not None:
            return prompt_envelope
        if execution.provider_usage_receipt is not None:
            return None
        return CostEstimatorService._build_fallback_prompt_envelope(task)

    @staticmethod
    def _build_fallback_prompt_envelope(task: Task) -> BuiltPromptEnvelope:
        """Preserve legacy accounting when Day06 prompt build has not yet run."""

        fallback_prompt_text = "\n".join(
            part for part in (task.title.strip(), task.input_summary.strip()) if part
        ).strip()
        if not fallback_prompt_text:
            fallback_prompt_text = task.title.strip()

        return BuiltPromptEnvelope(
            template_ref=PromptTemplateRef(
                prompt_key="task_execution.legacy_fallback",
                version="day06.step1",
                description="Fallback prompt basis derived from task title and input summary.",
            ),
            render_mode=PromptRenderMode.EXECUTION,
            sections=[],
            prompt_text=fallback_prompt_text,
            prompt_char_count=len(fallback_prompt_text),
        )
