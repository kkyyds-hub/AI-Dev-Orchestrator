"""Verifier service with Day 14 templates and quality gate metadata."""

from dataclasses import dataclass
import os
import shlex
import sys

from app.domain.run import RunFailureCategory
from app.domain.task import Task
from app.services.executor_service import ExecutionResult
from app.services.executor_service import ExecutorService
from app.services.task_instruction_parser import (
    extract_prefixed_payload,
    extract_verification_template,
)


@dataclass(slots=True, frozen=True)
class VerificationTemplateDefinition:
    """Built-in verification template definition."""

    name: str
    command: str
    description: str


@dataclass(slots=True)
class VerificationResult:
    """一次任务验证的最小结果。"""

    success: bool
    mode: str
    summary: str
    command: str | None = None
    exit_code: int | None = None
    template_name: str | None = None
    failure_category: RunFailureCategory | None = None
    quality_gate_passed: bool = False


class VerifierService:
    """提供 Day 8 / Day 14 的最小验证能力。"""

    def __init__(self, executor_service: ExecutorService | None = None) -> None:
        """复用本地命令执行基础能力，避免重复实现命令调用。"""

        self.executor_service = executor_service or ExecutorService()

    def verify_task(
        self,
        *,
        task: Task,
        execution_result: ExecutionResult,
    ) -> VerificationResult:
        """根据任务输入执行一次最小验证。"""

        template_name = extract_verification_template(task.input_summary)
        if template_name is not None:
            template = self._resolve_template(template_name)
            if template is None:
                return VerificationResult(
                    success=False,
                    mode="template",
                    summary=self._truncate_summary(
                        f"Verification template '{template_name}' is not supported. "
                        "Quality gate blocked task completion."
                    ),
                    template_name=template_name,
                    failure_category=RunFailureCategory.VERIFICATION_CONFIGURATION_FAILED,
                    quality_gate_passed=False,
                )

            command_result = self.executor_service.run_shell_command(template.command)
            return VerificationResult(
                success=command_result.success,
                mode="template",
                summary=self._truncate_summary(
                    self._build_template_verification_summary(
                        template=template,
                        command_summary=command_result.summary,
                    )
                ),
                command=template.command,
                exit_code=command_result.exit_code,
                template_name=template.name,
                failure_category=(
                    None
                    if command_result.success
                    else RunFailureCategory.VERIFICATION_FAILED
                ),
                quality_gate_passed=command_result.success,
            )

        verification_command = extract_prefixed_payload(
            task.input_summary,
            ("verify:", "check:"),
        )
        if verification_command is not None:
            command_result = self.executor_service.run_shell_command(verification_command)
            return VerificationResult(
                success=command_result.success,
                mode="shell",
                summary=self._truncate_summary(
                    self._build_shell_verification_summary(command_result.summary)
                ),
                command=verification_command,
                exit_code=command_result.exit_code,
                failure_category=(
                    None
                    if command_result.success
                    else RunFailureCategory.VERIFICATION_FAILED
                ),
                quality_gate_passed=command_result.success,
            )

        summary = (
            "Simulated verification succeeded. "
            f"Execution mode was {execution_result.mode}. "
            "Quality gate allowed task completion."
        )
        return VerificationResult(
            success=True,
            mode="simulate",
            summary=self._truncate_summary(summary),
            quality_gate_passed=True,
        )

    def _resolve_template(
        self,
        template_name: str,
    ) -> VerificationTemplateDefinition | None:
        """Return one built-in Day 14 verification template, if available."""

        return self._template_definitions().get(template_name)

    @staticmethod
    def _template_definitions() -> dict[str, VerificationTemplateDefinition]:
        """Return the small built-in verification template catalog."""

        python_pytest_command = VerifierService._build_python_module_command("pytest")
        python_compileall_command = VerifierService._build_python_module_command(
            "compileall",
            ".",
        )
        npm_test_command = "npm.cmd test" if os.name == "nt" else "npm test"
        npm_build_command = "npm.cmd run build" if os.name == "nt" else "npm run build"

        return {
            "pytest": VerificationTemplateDefinition(
                name="pytest",
                command=python_pytest_command,
                description="Run the local pytest suite.",
            ),
            "npm-test": VerificationTemplateDefinition(
                name="npm-test",
                command=npm_test_command,
                description="Run the local npm test script.",
            ),
            "npm-build": VerificationTemplateDefinition(
                name="npm-build",
                command=npm_build_command,
                description="Run the local npm build script.",
            ),
            "python-compileall": VerificationTemplateDefinition(
                name="python-compileall",
                command=python_compileall_command,
                description="Check Python source compilation recursively.",
            ),
        }

    @staticmethod
    def _build_python_module_command(module_name: str, *module_args: str) -> str:
        """Build a shell-safe command that uses the current Python interpreter."""

        command_parts = [sys.executable, "-m", module_name, *module_args]
        if os.name == "nt":
            escaped_executable = sys.executable.replace('"', '`"')
            escaped_args = [
                argument.replace('"', '`"')
                for argument in ("-m", module_name, *module_args)
            ]
            return " ".join(
                [
                    f'& "{escaped_executable}"',
                    *[f'"{argument}"' for argument in escaped_args],
                ]
            )

        return shlex.join(command_parts)

    @staticmethod
    def _build_template_verification_summary(
        *,
        template: VerificationTemplateDefinition,
        command_summary: str,
    ) -> str:
        """Convert a shell execution summary into template verification wording."""

        if command_summary.startswith("Shell command"):
            return command_summary.replace(
                "Shell command",
                f"Verification template '{template.name}'",
                1,
            )

        return f"Verification template '{template.name}' finished. {command_summary}"

    @staticmethod
    def _build_shell_verification_summary(command_summary: str) -> str:
        """把命令执行结果转换成验证口径摘要。"""

        if command_summary.startswith("Shell command"):
            return command_summary.replace("Shell command", "Verification command", 1)

        return command_summary

    @staticmethod
    def _truncate_summary(summary: str) -> str:
        """Keep verification summaries inside the persisted field limit."""

        if len(summary) <= 2_000:
            return summary

        return summary[: 1_997] + "..."
