"""Evaluate context-budget pressure for Day09 memory governance."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class ContextPressureLevel(StrEnum):
    """Stable pressure levels used by Day09 governance contracts."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(slots=True, frozen=True)
class ContextBudgetSnapshot:
    """Compact pressure snapshot consumed by Day09 governance chain."""

    task_id: UUID
    char_budget: int
    used_chars: int
    usage_ratio: float
    pressure_level: ContextPressureLevel
    bad_context_detected: bool
    bad_context_reasons: list[str]
    recommended_action: str


class ContextBudgetService:
    """Run deterministic context-pressure checks for one task context package."""

    def __init__(self, *, default_char_budget: int = 3_000) -> None:
        self.default_char_budget = max(default_char_budget, 800)

    def evaluate(
        self,
        *,
        task_id: UUID,
        context_summary: str,
        project_memory_context_summary: str | None,
        recent_run_count: int,
        blocking_reason_count: int,
    ) -> ContextBudgetSnapshot:
        """Assess context pressure and bad-context flags."""

        used_chars = (
            len(context_summary.strip())
            + len((project_memory_context_summary or "").strip())
        )
        usage_ratio = used_chars / self.default_char_budget

        bad_context_reasons: list[str] = []
        if usage_ratio >= 1.0:
            bad_context_reasons.append("context_budget_exceeded")
        if recent_run_count >= 3:
            bad_context_reasons.append("recent_run_history_dense")
        if blocking_reason_count >= 2:
            bad_context_reasons.append("blocking_signals_dense")

        if usage_ratio >= 1.0:
            pressure_level = ContextPressureLevel.HIGH
            recommended_action = "compact_and_rehydrate"
        elif usage_ratio >= 0.7:
            pressure_level = ContextPressureLevel.MEDIUM
            recommended_action = "compact"
        else:
            pressure_level = ContextPressureLevel.LOW
            recommended_action = "none"

        return ContextBudgetSnapshot(
            task_id=task_id,
            char_budget=self.default_char_budget,
            used_chars=used_chars,
            usage_ratio=round(usage_ratio, 4),
            pressure_level=pressure_level,
            bad_context_detected=bool(bad_context_reasons),
            bad_context_reasons=bad_context_reasons,
            recommended_action=recommended_action,
        )
