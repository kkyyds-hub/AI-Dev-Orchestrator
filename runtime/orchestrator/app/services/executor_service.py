"""Executor 基础能力。

Day 7 先提供两种最小执行模式：

- 本地命令执行：当 `input_summary` 带命令前缀时执行本地命令
- 模拟执行：当没有命令前缀时返回一个最小模拟结果

这样可以在不扩展 Day 2 数据模型字段的前提下，
先把 `Executor` 以最低复杂度接进 `Worker` 链路。
"""

from dataclasses import dataclass
import os
import subprocess

from app.domain.task import Task
from app.services.task_instruction_parser import extract_prefixed_payload


_RESULT_SUMMARY_MAX_LENGTH = 2_000


@dataclass(slots=True)
class ExecutionResult:
    """一次任务执行的最小结果。"""

    success: bool
    mode: str
    summary: str
    command: str | None = None
    exit_code: int | None = None


class ExecutorService:
    """提供 Day 7 的最小执行能力。"""

    def execute_task(self, task: Task) -> ExecutionResult:
        """根据任务输入执行一次最小任务。"""

        input_summary = task.input_summary.strip()
        mode, payload = self._resolve_mode(input_summary)

        if mode == "shell":
            return self.run_shell_command(payload)

        return self._simulate_execution(task, payload)

    def run_shell_command(self, command: str) -> ExecutionResult:
        """对外暴露最小本地命令执行能力。"""

        return self._execute_shell_command(command)

    def _resolve_mode(self, input_summary: str) -> tuple[str, str]:
        """把任务输入解析为执行模式和对应载荷。"""

        command = extract_prefixed_payload(
            input_summary,
            ("shell:", "cmd:", "command:"),
        )
        if command is not None:
            return "shell", command

        simulate_payload = extract_prefixed_payload(
            input_summary,
            ("simulate:",),
        )
        if simulate_payload is not None:
            return "simulate", simulate_payload

        return "simulate", input_summary

    def _execute_shell_command(self, command: str) -> ExecutionResult:
        """执行一条本地命令。"""

        if not command:
            return ExecutionResult(
                success=False,
                mode="shell",
                summary="Shell command is empty.",
                command=command,
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
                mode="shell",
                summary=self._truncate_summary(
                    f"Shell command timed out after 30 seconds: {command}"
                ),
                command=command,
            )
        except Exception as exc:
            return ExecutionResult(
                success=False,
                mode="shell",
                summary=self._truncate_summary(
                    f"Shell command execution raised {type(exc).__name__}: {exc}"
                ),
                command=command,
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
                mode="shell",
                summary=self._truncate_summary(summary),
                command=command,
                exit_code=completed.returncode,
            )

        summary = (
            f"Shell command failed with exit code {completed.returncode}. "
            f"Output: {merged_output}"
            if merged_output
            else f"Shell command failed with exit code {completed.returncode}."
        )
        return ExecutionResult(
            success=False,
            mode="shell",
            summary=self._truncate_summary(summary),
            command=command,
            exit_code=completed.returncode,
        )

    def _simulate_execution(self, task: Task, payload: str) -> ExecutionResult:
        """返回一个最小模拟执行结果。"""

        summary_body = payload if payload else task.title
        summary = (
            "Simulated execution succeeded. "
            f"Task '{task.title}' was processed with summary: {summary_body}"
        )
        return ExecutionResult(
            success=True,
            mode="simulate",
            summary=self._truncate_summary(summary),
        )

    @staticmethod
    def _build_shell_command(command: str) -> list[str]:
        """按当前操作系统构造本地命令执行入口。"""

        if os.name == "nt":
            return ["powershell.exe", "-Command", command]

        return ["/bin/sh", "-lc", command]

    @staticmethod
    def _truncate_summary(summary: str) -> str:
        """把执行结果摘要裁剪到数据库字段允许的长度。"""

        if len(summary) <= _RESULT_SUMMARY_MAX_LENGTH:
            return summary

        return summary[: _RESULT_SUMMARY_MAX_LENGTH - 3] + "..."
