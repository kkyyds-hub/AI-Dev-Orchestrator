"""Render execution prompts from task/context/routing contracts."""

from __future__ import annotations

from app.domain.model_policy import ExecutorModelRoutingContract
from app.domain.prompt_contract import BuiltPromptEnvelope, PromptSection
from app.domain.task import Task
from app.services.context_builder_service import TaskContextPackage
from app.services.executor_service import ExecutionPlan
from app.services.prompt_registry_service import PromptRegistryService


_SECTION_CONTENT_MAX_LENGTH = 3_800


class PromptBuilderService:
    """Build prompt envelopes used by executor and token-accounting flows."""

    def __init__(
        self,
        *,
        prompt_registry_service: PromptRegistryService,
    ) -> None:
        self.prompt_registry_service = prompt_registry_service

    def build_execution_prompt(
        self,
        *,
        task: Task,
        context_package: TaskContextPackage,
        execution_plan: ExecutionPlan,
        routing_contract: ExecutorModelRoutingContract | None,
    ) -> BuiltPromptEnvelope:
        """Render one execution prompt envelope for the current worker cycle."""

        template_entry = self.prompt_registry_service.get_execution_entry()
        sections: list[PromptSection] = [
            PromptSection(
                key="system_instruction",
                title="System Instruction",
                content=template_entry.system_instruction,
            ),
            PromptSection(
                key="task_input",
                title="Task Input",
                content=self._truncate(task.input_summary),
            ),
        ]

        if template_entry.include_acceptance_criteria:
            sections.append(
                PromptSection(
                    key="acceptance_criteria",
                    title="Acceptance Criteria",
                    content=self._truncate(
                        self._build_acceptance_criteria_text(task.acceptance_criteria)
                    ),
                )
            )

        if template_entry.include_context_summary:
            sections.append(
                PromptSection(
                    key="context_summary",
                    title="Context Summary",
                    content=self._truncate(context_package.context_summary),
                )
            )
            if context_package.project_memory_enabled:
                sections.append(
                    PromptSection(
                        key="project_memory",
                        title="Project Memory Recall",
                        content=self._truncate(
                            self._build_project_memory_summary(context_package)
                        ),
                    )
                )

        if template_entry.include_routing_summary and routing_contract is not None:
            sections.append(
                PromptSection(
                    key="routing_summary",
                    title="Routing Summary",
                    content=self._truncate(
                        self._build_routing_summary(
                            execution_plan=execution_plan,
                            routing_contract=routing_contract,
                        )
                    ),
                )
            )

        sections.append(
            PromptSection(
                key="execution_mode",
                title="Execution Plan",
                content=self._truncate(
                    f"Execution mode: {execution_plan.mode}\n"
                    f"Payload: {execution_plan.payload.strip() or task.title}"
                ),
            )
        )

        prompt_text = "\n\n".join(
            f"[{section.title}]\n{section.content}" for section in sections
        ).strip()
        provider_key = (
            routing_contract.primary_target.provider_key
            if routing_contract is not None and routing_contract.primary_target is not None
            else None
        )
        model_name = (
            routing_contract.primary_target.model_name
            if routing_contract is not None and routing_contract.primary_target is not None
            else None
        )

        return BuiltPromptEnvelope(
            template_ref=template_entry.template_ref,
            render_mode=template_entry.render_mode,
            provider_key=provider_key,
            model_name=model_name,
            sections=sections,
            prompt_text=prompt_text,
            prompt_char_count=len(prompt_text),
        )

    @staticmethod
    def _build_acceptance_criteria_text(acceptance_criteria: list[str]) -> str:
        """Render acceptance criteria into one compact bullet-style section."""

        if not acceptance_criteria:
            return "- No explicit acceptance criteria were provided."

        return "\n".join(f"- {item}" for item in acceptance_criteria)

    @staticmethod
    def _build_project_memory_summary(context_package: TaskContextPackage) -> str:
        """Render project-memory recall metadata for prompt visibility."""

        lines = [
            f"Enabled: {context_package.project_memory_enabled}",
            f"Query: {context_package.project_memory_query_text or '(empty)'}",
            f"Items: {context_package.project_memory_item_count}",
        ]
        if context_package.project_memory_context_summary:
            lines.append(context_package.project_memory_context_summary)
        return "\n".join(lines)

    @staticmethod
    def _build_routing_summary(
        *,
        execution_plan: ExecutionPlan,
        routing_contract: ExecutorModelRoutingContract,
    ) -> str:
        """Render the routed provider/model and policy hint into one section."""

        strategy_hint = routing_contract.strategy_hint
        provider_target = routing_contract.primary_target
        provider_line = (
            f"Provider target: {provider_target.provider_key}/{provider_target.model_name}"
            if provider_target is not None
            else "Provider target: (not assigned)"
        )
        policy_lines = [
            f"Strategy code: {strategy_hint.strategy_code}",
            f"Model tier: {strategy_hint.model_tier or '(unknown)'}",
            provider_line,
            f"Fallback mode: {routing_contract.implicit_fallback_mode.value}",
            f"Route reason: {routing_contract.route_reason}",
        ]
        if strategy_hint.role_model_policy_source:
            policy_lines.append(
                f"Role Model Policy source: {strategy_hint.role_model_policy_source}"
            )
            policy_lines.append(
                "Role Model Policy tiers: "
                f"{strategy_hint.role_model_policy_desired_tier or '(n/a)'} -> "
                f"{strategy_hint.role_model_policy_adjusted_tier or '(n/a)'} -> "
                f"{strategy_hint.role_model_policy_final_tier or '(n/a)'}"
            )
            policy_lines.append(
                "Stage override applied: "
                f"{'yes' if strategy_hint.role_model_policy_stage_override_applied else 'no'}"
            )
        if strategy_hint.selected_skill_codes:
            policy_lines.append(
                "Selected skills: " + ", ".join(strategy_hint.selected_skill_codes)
            )
        policy_lines.append(f"Execution mode: {execution_plan.mode}")
        return "\n".join(policy_lines)

    @staticmethod
    def _truncate(value: str) -> str:
        """Keep section content inside prompt-contract length constraints."""

        normalized_value = value.strip()
        if len(normalized_value) <= _SECTION_CONTENT_MAX_LENGTH:
            return normalized_value
        return normalized_value[: _SECTION_CONTENT_MAX_LENGTH - 3].rstrip() + "..."

