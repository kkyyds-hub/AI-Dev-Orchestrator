"""In-memory prompt registry used by the worker prompt builder."""

from __future__ import annotations

from app.domain.prompt_contract import (
    PromptRegistryEntry,
    PromptRenderMode,
    PromptTemplateRef,
)


class PromptRegistryService:
    """Provide stable prompt templates for execution and verification paths."""

    def __init__(self) -> None:
        self._execution_entry = PromptRegistryEntry(
            template_ref=PromptTemplateRef(
                prompt_key="task_execution.default",
                version="day06.step1",
                description="Default Day06 execution prompt template.",
            ),
            render_mode=PromptRenderMode.EXECUTION,
            system_instruction=(
                "You are the execution worker for AI Dev Orchestrator. "
                "Follow acceptance criteria, respect role routing context, and produce a concise result summary."
            ),
            include_acceptance_criteria=True,
            include_context_summary=True,
            include_routing_summary=True,
        )
        self._verification_entry = PromptRegistryEntry(
            template_ref=PromptTemplateRef(
                prompt_key="task_verification.default",
                version="day06.step1",
                description="Default Day06 verification prompt template.",
            ),
            render_mode=PromptRenderMode.VERIFICATION,
            system_instruction=(
                "You are the verification worker for AI Dev Orchestrator. "
                "Evaluate completion quality against acceptance criteria and highlight risks."
            ),
            include_acceptance_criteria=True,
            include_context_summary=True,
            include_routing_summary=False,
        )

    def get_execution_entry(self) -> PromptRegistryEntry:
        """Return the default execution prompt template."""

        return self._execution_entry

    def get_verification_entry(self) -> PromptRegistryEntry:
        """Return the default verification prompt template."""

        return self._verification_entry

