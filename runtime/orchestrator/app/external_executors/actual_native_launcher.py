"""Silent native executor launcher boundary for server-side use."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
import subprocess
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_SUPPORTED_EXECUTOR_LABELS = frozenset({"codex", "claude-code", "claude code"})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _trim_optional_string(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _trim_required_string(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _command_for_executor(executor_label: str) -> tuple[str, ...]:
    normalized_label = executor_label.strip().lower()
    if normalized_label == "codex":
        return ("codex",)
    if normalized_label in {"claude-code", "claude code"}:
        return ("claude",)
    raise ValueError("executor_label is not supported")


class _NativeLauncherModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RealExecutorNativeLaunchMode(StrEnum):
    DISABLED = "disabled"
    DRY_RUN = "dry_run"
    ENABLED = "enabled"


class RealExecutorNativeProcessHandle(_NativeLauncherModel):
    process_handle_id: str

    @field_validator("process_handle_id", mode="before")
    @classmethod
    def trim_process_handle_id(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("process_handle_id")
    @classmethod
    def require_process_handle_id(cls, value: str) -> str:
        if not value:
            raise ValueError("process_handle_id must not be empty")
        return value


class RealExecutorNativeLaunchInput(_NativeLauncherModel):
    launch_mode: RealExecutorNativeLaunchMode = RealExecutorNativeLaunchMode.DISABLED
    executor_label: str = "codex"
    workspace_path: str | None = None
    agent_session_id: str | None = None
    prelaunch_ready: bool = False
    command_plan_redacted: bool = True
    product_runtime_git_write_allowed: bool = False
    frontend_required: bool = False
    frontend_change_allowed: bool = False
    allow_native_process: bool = False

    @field_validator("executor_label", mode="before")
    @classmethod
    def trim_executor_label(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("workspace_path", "agent_session_id", mode="before")
    @classmethod
    def trim_optional_strings(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    @field_validator("executor_label")
    @classmethod
    def validate_executor_label(cls, value: str) -> str:
        if not value:
            raise ValueError("executor_label must not be empty")
        if value.strip().lower() not in _SUPPORTED_EXECUTOR_LABELS:
            raise ValueError("executor_label is not supported")
        return value

    @field_validator(
        "product_runtime_git_write_allowed",
        "frontend_required",
        "frontend_change_allowed",
    )
    @classmethod
    def keep_forbidden_flags_disabled(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError("native launcher keeps this capability disabled")
        return value

    @model_validator(mode="after")
    def validate_launch_inputs(self) -> "RealExecutorNativeLaunchInput":
        if self.launch_mode == RealExecutorNativeLaunchMode.DISABLED:
            return self
        if self.workspace_path is None:
            raise ValueError("workspace_path is required")
        if not Path(self.workspace_path).is_absolute():
            raise ValueError("workspace_path must be absolute")
        if self.agent_session_id is None:
            raise ValueError("agent_session_id is required")
        return self


class RealExecutorNativeLaunchDecision(_NativeLauncherModel):
    launch_status: str
    native_launch_attempted: bool
    native_process_started: bool
    process_handle_id: str | None = None
    executor_label: str
    workspace_path: str | None = None
    agent_session_id: str | None = None
    blocked_reasons: list[str] = Field(default_factory=list)
    product_runtime_git_write_allowed: bool = False
    frontend_required: bool = False
    frontend_change_allowed: bool = False
    raw_command_exposed: bool = False
    stdout_exposed: bool = False
    stderr_exposed: bool = False
    decided_at: datetime = Field(default_factory=_utc_now)

    @field_validator(
        "product_runtime_git_write_allowed",
        "frontend_required",
        "frontend_change_allowed",
        "raw_command_exposed",
        "stdout_exposed",
        "stderr_exposed",
    )
    @classmethod
    def keep_decision_forbidden_flags_disabled(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError("native launcher decision cannot expose this capability")
        return value


@runtime_checkable
class RealExecutorNativeRunnerProtocol(Protocol):
    def start(
        self,
        *,
        argv: tuple[str, ...],
        workspace_path: str,
        agent_session_id: str,
    ) -> RealExecutorNativeProcessHandle: ...


class FakeRealExecutorNativeRunner:
    def __init__(self, *, process_handle_id: str = "fake-native-process-handle") -> None:
        self.process_handle_id = process_handle_id
        self.started = False
        self.started_argv: tuple[str, ...] | None = None
        self.started_workspace_path: str | None = None
        self.started_agent_session_id: str | None = None

    def start(
        self,
        *,
        argv: tuple[str, ...],
        workspace_path: str,
        agent_session_id: str,
    ) -> RealExecutorNativeProcessHandle:
        self.started = True
        self.started_argv = argv
        self.started_workspace_path = workspace_path
        self.started_agent_session_id = agent_session_id
        return RealExecutorNativeProcessHandle(process_handle_id=self.process_handle_id)


class SubprocessRealExecutorNativeRunner:
    def start(
        self,
        *,
        argv: tuple[str, ...],
        workspace_path: str,
        agent_session_id: str,
    ) -> RealExecutorNativeProcessHandle:
        if not argv:
            raise ValueError("argv must not be empty")
        if not all(part.strip() for part in argv):
            raise ValueError("argv entries must not be empty")
        if not Path(workspace_path).is_absolute():
            raise ValueError("workspace_path must be absolute")

        process = subprocess.Popen(
            list(argv),
            cwd=workspace_path,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        return RealExecutorNativeProcessHandle(
            process_handle_id=f"native-process-{agent_session_id}-{process.pid}",
        )


class RealExecutorNativeLauncher:
    def __init__(
        self,
        *,
        runner: RealExecutorNativeRunnerProtocol | None = None,
    ) -> None:
        self._runner = runner or FakeRealExecutorNativeRunner()

    def decide(
        self,
        launch_input: RealExecutorNativeLaunchInput | None = None,
    ) -> RealExecutorNativeLaunchDecision:
        source = launch_input or RealExecutorNativeLaunchInput()
        blocked_reasons = self._blocked_reasons(source)
        if source.launch_mode == RealExecutorNativeLaunchMode.DRY_RUN and not blocked_reasons:
            return self._decision(
                source,
                launch_status="dry_run_ready",
                native_launch_attempted=False,
                native_process_started=False,
                process_handle_id=None,
                blocked_reasons=[],
            )
        if blocked_reasons:
            return self._decision(
                source,
                launch_status="blocked",
                native_launch_attempted=False,
                native_process_started=False,
                process_handle_id=None,
                blocked_reasons=blocked_reasons,
            )

        handle = self._runner.start(
            argv=_command_for_executor(source.executor_label),
            workspace_path=source.workspace_path or "",
            agent_session_id=source.agent_session_id or "",
        )
        return self._decision(
            source,
            launch_status="launch_started",
            native_launch_attempted=True,
            native_process_started=True,
            process_handle_id=handle.process_handle_id,
            blocked_reasons=[],
        )

    @staticmethod
    def _blocked_reasons(source: RealExecutorNativeLaunchInput) -> list[str]:
        reasons: list[str] = []
        if source.launch_mode == RealExecutorNativeLaunchMode.DISABLED:
            reasons.append("native_launch_disabled")
        if source.launch_mode == RealExecutorNativeLaunchMode.ENABLED:
            if not source.allow_native_process:
                reasons.append("native_process_not_allowed")
            if not source.prelaunch_ready:
                reasons.append("prelaunch_not_ready")
            if not source.command_plan_redacted:
                reasons.append("command_plan_not_redacted")
        return reasons

    @staticmethod
    def _decision(
        source: RealExecutorNativeLaunchInput,
        *,
        launch_status: str,
        native_launch_attempted: bool,
        native_process_started: bool,
        process_handle_id: str | None,
        blocked_reasons: list[str],
    ) -> RealExecutorNativeLaunchDecision:
        return RealExecutorNativeLaunchDecision(
            launch_status=launch_status,
            native_launch_attempted=native_launch_attempted,
            native_process_started=native_process_started,
            process_handle_id=process_handle_id,
            executor_label=source.executor_label,
            workspace_path=source.workspace_path,
            agent_session_id=source.agent_session_id,
            blocked_reasons=blocked_reasons,
            product_runtime_git_write_allowed=False,
            frontend_required=False,
            frontend_change_allowed=False,
            raw_command_exposed=False,
            stdout_exposed=False,
            stderr_exposed=False,
        )


__all__ = (
    "FakeRealExecutorNativeRunner",
    "RealExecutorNativeLaunchDecision",
    "RealExecutorNativeLaunchInput",
    "RealExecutorNativeLaunchMode",
    "RealExecutorNativeLauncher",
    "RealExecutorNativeProcessHandle",
    "RealExecutorNativeRunnerProtocol",
    "SubprocessRealExecutorNativeRunner",
)
