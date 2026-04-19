"""Compact oversized task context for Day09 memory-governance chain."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.context_budget_service import ContextBudgetSnapshot


_DEFAULT_COMPACT_TARGET_CHARS = 1_200


@dataclass(slots=True, frozen=True)
class MemoryCompactionResult:
    """Compaction output consumed by context builder and Day10 contracts."""

    compaction_applied: bool
    original_chars: int
    compacted_chars: int
    reduction_ratio: float
    compacted_summary: str
    strategy: str
    reasons: list[str]


class MemoryCompactionService:
    """Apply a deterministic summary compaction strategy for bad-context pressure."""

    def compact_context(
        self,
        *,
        context_summary: str,
        project_memory_context_summary: str | None,
        budget_snapshot: ContextBudgetSnapshot,
        target_chars: int = _DEFAULT_COMPACT_TARGET_CHARS,
    ) -> MemoryCompactionResult:
        """Compact context summary when budget pressure suggests governance action."""

        normalized_target_chars = max(target_chars, 400)
        memory_summary = (project_memory_context_summary or "").strip()
        merged = context_summary.strip()
        if memory_summary:
            merged = f"{merged}\n\nMemory hints:\n{memory_summary}"

        original_chars = len(merged)
        if not merged:
            return MemoryCompactionResult(
                compaction_applied=False,
                original_chars=0,
                compacted_chars=0,
                reduction_ratio=0.0,
                compacted_summary="",
                strategy="noop",
                reasons=[],
            )

        if (
            not budget_snapshot.bad_context_detected
            and budget_snapshot.usage_ratio < 0.7
            and original_chars <= normalized_target_chars
        ):
            return MemoryCompactionResult(
                compaction_applied=False,
                original_chars=original_chars,
                compacted_chars=original_chars,
                reduction_ratio=0.0,
                compacted_summary=merged,
                strategy="noop",
                reasons=[],
            )

        lines = [line.strip() for line in merged.splitlines() if line.strip()]
        headline_lines = lines[:6]
        if len(lines) > 6:
            headline_lines.append(f"(trimmed {len(lines) - 6} context lines)")
        compacted = "\n".join(headline_lines)
        if len(compacted) > normalized_target_chars:
            compacted = compacted[: normalized_target_chars - 3].rstrip() + "..."

        compacted_chars = len(compacted)
        reduction_ratio = (
            round(max(0.0, (original_chars - compacted_chars) / original_chars), 4)
            if original_chars > 0
            else 0.0
        )
        return MemoryCompactionResult(
            compaction_applied=True,
            original_chars=original_chars,
            compacted_chars=compacted_chars,
            reduction_ratio=reduction_ratio,
            compacted_summary=compacted,
            strategy="headline_and_trim",
            reasons=list(budget_snapshot.bad_context_reasons),
        )
