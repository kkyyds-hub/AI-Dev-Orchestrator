"""Executor baseline capabilities with Day05 Step1 routing-contract support."""

from __future__ import annotations

from dataclasses import dataclass
import os
import subprocess
from typing import TYPE_CHECKING

from app.domain.model_policy import ExecutorModelRoutingContract, ExecutorRouteMode
from app.domain.prompt_contract import BuiltPromptEnvelope, ProviderUsageReceipt
from app.domain.task import Task
from app.services.mock_provider_executor_service import MockProviderExecutorService
from app.services.task_instruction_parser import extract_prefixed_payload

if TYPE_CHECKING:
    from app.services.context_builder_service import TaskContextPackage


_RESULT_SUMMARY_MAX_LENGTH = 2_000


@dataclass(slots=True)
class ExecutionResult:
    """Minimal result returned by one executor attempt."""

    success: bool
    mode: str
    summary: str
    command: str | None = None
    exit_code: int | None = None
    prompt_key: str | None = None
    prompt_char_count: int = 0
    provider_usage_receipt: ProviderUsageReceipt | None = None


@dataclass(slots=True, frozen=True)
class RequestedExecutionMode:
    """One execution mode request resolved from task input prefixes."""

    mode: str
    payload: str
    is_explicit: bool


@dataclass(slots=True, frozen=True)
class ExecutionPlan:
    """Executor-facing plan after merging prefixes and routing contract."""

    mode: str
    payload: str
    routing_contract: ExecutorModelRoutingContract | None = None


class ExecutorService:
    """Provide shell/simulate execution while reserving a provider-routing seam."""

    def __init__(
        self,
        *,
        mock_provider_executor_service: MockProviderExecutorService | None = None,
    ) -> None:
        """Initialize the minimal executor graph for Day05 Step6."""

        self.mock_provider_executor_service = (
            mock_provider_executor_service or MockProviderExecutorService()
        )

    def execute_task(
        self,
        task: Task,
        *,
        context_package: "TaskContextPackage | None" = None,
        routing_contract: ExecutorModelRoutingContract | None = None,
        prompt_envelope: BuiltPromptEnvelope | None = None,
    ) -> ExecutionResult:
        """Execute one task via the merged execution plan."""

        plan = self.build_execution_plan(
            task=task,
            routing_contract=routing_contract,
        )

        if plan.mode == ExecutorRouteMode.SHELL.value:
            return self.run_shell_command(plan.payload, prompt_envelope=prompt_envelope)

        if plan.mode == ExecutorRouteMode.PROVIDER.value:
            return self._execute_provider_mode(
                task,
                plan.payload,
                routing_contract=plan.routing_contract,
                prompt_envelope=prompt_envelope,
                context_package=context_package,
            )

        return self._simulate_execution(
            task,
            plan.payload,
            context_package=context_package,
            prompt_envelope=prompt_envelope,
        )

    def _execute_provider_mode(
        self,
        task: Task,
        payload: str,
        *,
        routing_contract: ExecutorModelRoutingContract | None,
        prompt_envelope: BuiltPromptEnvelope | None,
        context_package: "TaskContextPackage | None" = None,
    ) -> ExecutionResult:
        """Execute the provider path through the local mock provider service."""

        if routing_contract is None or prompt_envelope is None:
            return self._simulate_provider_fallback(
                task,
                payload,
                routing_contract=routing_contract,
                prompt_envelope=prompt_envelope,
                context_package=context_package,
            )

        try:
            provider_response = self.mock_provider_executor_service.execute(
                task=task,
                payload=payload,
                routing_contract=routing_contract,
                prompt_envelope=prompt_envelope,
                context_package=context_package,
            )
        except Exception:
            return self._simulate_provider_fallback(
                task,
                payload,
                routing_contract=routing_contract,
                prompt_envelope=prompt_envelope,
                context_package=context_package,
            )

        return ExecutionResult(
            success=provider_response.success,
            mode=provider_response.mode,
            summary=self._truncate_summary(provider_response.summary),
            prompt_key=provider_response.prompt_key,
            prompt_char_count=provider_response.prompt_char_count,
            provider_usage_receipt=provider_response.provider_usage_receipt,
        )

    def build_execution_plan(
        self,
        *,
        task: Task,
        routing_contract: ExecutorModelRoutingContract | None = None,
    ) -> ExecutionPlan:
        """Merge explicit shell/simulate prefixes with the new routing contract."""

        requested_mode = self._resolve_mode(task.input_summary.strip())
        if requested_mode.mode == ExecutorRouteMode.SHELL.value:
            return ExecutionPlan(mode=requested_mode.mode, payload=requested_mode.payload)

        if requested_mode.is_explicit and requested_mode.mode == ExecutorRouteMode.SIMULATE.value:
            return ExecutionPlan(mode=requested_mode.mode, payload=requested_mode.payload)

        if routing_contract is not None and routing_contract.primary_mode == ExecutorRouteMode.PROVIDER:
            return ExecutionPlan(
                mode=ExecutorRouteMode.PROVIDER.value,
                payload=requested_mode.payload,
                routing_contract=routing_contract,
            )

        return ExecutionPlan(
            mode=requested_mode.mode,
            payload=requested_mode.payload,
            routing_contract=routing_contract,
        )

    def run_shell_command(
        self,
        command: str,
        *,
        prompt_envelope: BuiltPromptEnvelope | None = None,
    ) -> ExecutionResult:
        """Expose the minimal local shell capability."""

        return self._execute_shell_command(command, prompt_envelope=prompt_envelope)

    def _resolve_mode(self, input_summary: str) -> RequestedExecutionMode:
        """Resolve the requested mode from legacy task prefixes."""

        command = extract_prefixed_payload(
            input_summary,
            ("shell:", "cmd:", "command:"),
        )
        if command is not None:
            return RequestedExecutionMode(
                mode=ExecutorRouteMode.SHELL.value,
                payload=command,
                is_explicit=True,
            )

        simulate_payload = extract_prefixed_payload(
            input_summary,
            ("simulate:",),
        )
        if simulate_payload is not None:
            return RequestedExecutionMode(
                mode=ExecutorRouteMode.SIMULATE.value,
                payload=simulate_payload,
                is_explicit=True,
            )

        return RequestedExecutionMode(
            mode=ExecutorRouteMode.SIMULATE.value,
            payload=input_summary,
            is_explicit=False,
        )

    def _execute_shell_command(
        self,
        command: str,
        *,
        prompt_envelope: BuiltPromptEnvelope | None = None,
    ) -> ExecutionResult:
        """Execute one local shell command."""

        if not command:
            return ExecutionResult(
                success=False,
                mode=ExecutorRouteMode.SHELL.value,
                summary="Shell command is empty.",
                command=command,
                prompt_key=(
                    prompt_envelope.template_ref.prompt_key if prompt_envelope is not None else None
                ),
                prompt_char_count=(
                    prompt_envelope.prompt_char_count if prompt_envelope is not None else 0
                ),
            )

        try:
            completed = subprocess.run(
                self._build_shell_command(command),
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                mode=ExecutorRouteMode.SHELL.value,
                summary=self._truncate_summary(
                    f"Shell command timed out after 30 seconds: {command}"
                ),
                command=command,
                prompt_key=(
                    prompt_envelope.template_ref.prompt_key if prompt_envelope is not None else None
                ),
                prompt_char_count=(
                    prompt_envelope.prompt_char_count if prompt_envelope is not None else 0
                ),
            )
        except Exception as exc:
            return ExecutionResult(
                success=False,
                mode=ExecutorRouteMode.SHELL.value,
                summary=self._truncate_summary(
                    f"Shell command execution raised {type(exc).__name__}: {exc}"
                ),
                command=command,
                prompt_key=(
                    prompt_envelope.template_ref.prompt_key if prompt_envelope is not None else None
                ),
                prompt_char_count=(
                    prompt_envelope.prompt_char_count if prompt_envelope is not None else 0
                ),
            )

        output_parts = [completed.stdout.strip(), completed.stderr.strip()]
        merged_output = "\n".join(part for part in output_parts if part).strip()

        if completed.returncode == 0:
            summary = (
                f"Shell command succeeded with exit code 0. Output: {merged_output}"
                if merged_output
                else "Shell command succeeded with exit code 0."
            )
            return ExecutionResult(
                success=True,
                mode=ExecutorRouteMode.SHELL.value,
                summary=self._truncate_summary(summary),
                command=command,
                exit_code=completed.returncode,
                prompt_key=(
                    prompt_envelope.template_ref.prompt_key if prompt_envelope is not None else None
                ),
                prompt_char_count=(
                    prompt_envelope.prompt_char_count if prompt_envelope is not None else 0
                ),
            )

        summary = (
            f"Shell command failed with exit code {completed.returncode}. "
            f"Output: {merged_output}"
            if merged_output
            else f"Shell command failed with exit code {completed.returncode}."
        )
        return ExecutionResult(
            success=False,
            mode=ExecutorRouteMode.SHELL.value,
            summary=self._truncate_summary(summary),
            command=command,
            exit_code=completed.returncode,
            prompt_key=(
                prompt_envelope.template_ref.prompt_key if prompt_envelope is not None else None
            ),
            prompt_char_count=(
                prompt_envelope.prompt_char_count if prompt_envelope is not None else 0
            ),
        )

    def _simulate_execution(
        self,
        task: Task,
        payload: str,
        *,
        context_package: "TaskContextPackage | None" = None,
        prompt_envelope: BuiltPromptEnvelope | None = None,
    ) -> ExecutionResult:
        """Return one minimal simulated execution result."""

        summary_body = payload if payload else task.title
        context_suffix = (
            f" Context package: {context_package.context_summary}"
            if context_package is not None
            else ""
        )
        summary = (
            "Simulated execution succeeded. "
            f"Task '{task.title}' was processed with summary: {summary_body}."
            f"{context_suffix}"
        )
        return ExecutionResult(
            success=True,
            mode=ExecutorRouteMode.SIMULATE.value,
            summary=self._truncate_summary(summary),
            prompt_key=(
                prompt_envelope.template_ref.prompt_key if prompt_envelope is not None else None
            ),
            prompt_char_count=(
                prompt_envelope.prompt_char_count if prompt_envelope is not None else 0
            ),
        )

    def _simulate_provider_fallback(
        self,
        task: Task,
        payload: str,
        *,
        routing_contract: ExecutorModelRoutingContract | None,
        prompt_envelope: BuiltPromptEnvelope | None,
        context_package: "TaskContextPackage | None" = None,
    ) -> ExecutionResult:
        """Keep Step1 provider routing safe by falling back to simulate execution."""

        summary_body = payload if payload else task.title
        context_suffix = (
            f" Context package: {context_package.context_summary}"
            if context_package is not None
            else ""
        )
        routing_suffix = ""
        if routing_contract is not None and routing_contract.primary_target is not None:
            routing_suffix = (
                " Provider routing contract reserved "
                f"{routing_contract.primary_target.provider_key}/"
                f"{routing_contract.primary_target.model_name}. "
                f"{routing_contract.route_reason}"
            )
        prompt_suffix = ""
        if prompt_envelope is not None:
            prompt_suffix = (
                " Prompt contract prepared "
                f"{prompt_envelope.template_ref.prompt_key}@{prompt_envelope.template_ref.version} "
                f"({prompt_envelope.prompt_char_count} chars)."
            )

        summary = (
            "Simulated execution succeeded. "
            "Day05 Step1 currently lands only the provider/model routing contract skeleton,"
            " so executor keeps simulate fallback."
            f"{routing_suffix}{prompt_suffix} Task '{task.title}' was processed with summary: {summary_body}."
            f"{context_suffix}"
        )
        return ExecutionResult(
            success=True,
            mode=ExecutorRouteMode.SIMULATE.value,
            summary=self._truncate_summary(summary),
            prompt_key=(
                prompt_envelope.template_ref.prompt_key if prompt_envelope is not None else None
            ),
            prompt_char_count=(
                prompt_envelope.prompt_char_count if prompt_envelope is not None else 0
            ),
        )

    @staticmethod
    def _build_shell_command(command: str) -> list[str]:
        """Build the shell invocation for the current operating system."""

        if os.name == "nt":
            return ["powershell.exe", "-Command", command]

        return ["/bin/sh", "-lc", command]

    @staticmethod
    def _truncate_summary(summary: str) -> str:
        """Trim result summaries to fit the persisted storage budget."""

        if len(summary) <= _RESULT_SUMMARY_MAX_LENGTH:
            return summary

        return summary[: _RESULT_SUMMARY_MAX_LENGTH - 3] + "..."
