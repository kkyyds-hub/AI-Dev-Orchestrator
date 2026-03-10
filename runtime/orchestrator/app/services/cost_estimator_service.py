"""Heuristic token and cost estimation for Day 9."""

from dataclasses import dataclass
from math import ceil

from app.domain.task import Task
from app.services.executor_service import ExecutionResult
from app.services.verifier_service import VerificationResult


_CHARS_PER_TOKEN = 4
_PROMPT_COST_PER_1K_TOKENS_USD = 0.0015
_COMPLETION_COST_PER_1K_TOKENS_USD = 0.0030


@dataclass(slots=True, frozen=True)
class CostEstimate:
    """Minimal persisted cost estimate for one worker run."""

    prompt_tokens: int
    completion_tokens: int
    estimated_cost: float


class CostEstimatorService:
    """Estimate token usage and cost before real provider accounting exists."""

    def estimate_run_cost(
        self,
        *,
        task: Task,
        execution: ExecutionResult,
        verification: VerificationResult | None,
    ) -> CostEstimate:
        """Build a heuristic cost snapshot from task input and run output."""

        prompt_text = "\n".join(
            part for part in (task.title.strip(), task.input_summary.strip()) if part
        )
        completion_parts = [execution.summary.strip()]
        if verification is not None:
            completion_parts.append(verification.summary.strip())

        completion_text = "\n".join(part for part in completion_parts if part)
        prompt_tokens = self._estimate_tokens(prompt_text)
        completion_tokens = self._estimate_tokens(completion_text)
        estimated_cost = round(
            (prompt_tokens / 1_000) * _PROMPT_COST_PER_1K_TOKENS_USD
            + (completion_tokens / 1_000) * _COMPLETION_COST_PER_1K_TOKENS_USD,
            6,
        )

        return CostEstimate(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost=estimated_cost,
        )

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Approximate token usage with a simple text-length heuristic."""

        normalized = text.strip()
        if not normalized:
            return 0

        return max(1, ceil(len(normalized) / _CHARS_PER_TOKEN))
