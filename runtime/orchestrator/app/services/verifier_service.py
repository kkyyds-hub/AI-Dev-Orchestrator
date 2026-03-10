"""Verifier 基础能力。

Day 8 先提供两种最小验证模式：

- 本地命令验证：当 `input_summary` 中存在 `verify:` 或 `check:` 指令时执行本地命令
- 模拟验证：当没有显式验证指令时，返回一个最小模拟验证结果
"""

from dataclasses import dataclass

from app.domain.task import Task
from app.services.executor_service import ExecutionResult
from app.services.executor_service import ExecutorService
from app.services.task_instruction_parser import extract_prefixed_payload


@dataclass(slots=True)
class VerificationResult:
    """一次任务验证的最小结果。"""

    success: bool
    mode: str
    summary: str
    command: str | None = None
    exit_code: int | None = None


class VerifierService:
    """提供 Day 8 的最小验证能力。"""

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

        verification_command = extract_prefixed_payload(
            task.input_summary,
            ("verify:", "check:"),
        )
        if verification_command is not None:
            command_result = self.executor_service.run_shell_command(verification_command)
            return VerificationResult(
                success=command_result.success,
                mode="shell",
                summary=self._build_shell_verification_summary(command_result.summary),
                command=verification_command,
                exit_code=command_result.exit_code,
            )

        summary = (
            "Simulated verification succeeded. "
            f"Execution mode was {execution_result.mode}."
        )
        return VerificationResult(
            success=True,
            mode="simulate",
            summary=summary,
        )

    @staticmethod
    def _build_shell_verification_summary(command_summary: str) -> str:
        """把命令执行结果转换成验证口径摘要。"""

        if command_summary.startswith("Shell command"):
            return command_summary.replace("Shell command", "Verification command", 1)

        return command_summary
