"""Server-side runner wiring policy for silent native executor launch."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from app.external_executors.actual_native_launcher import (
    FakeRealExecutorNativeRunner,
    RealExecutorNativeLaunchMode,
    RealExecutorNativeLauncher,
    RealExecutorNativeRunnerProtocol,
    SubprocessRealExecutorNativeRunner,
)
from app.external_executors.actual_silent_launch_service import (
    RealExecutorSilentLaunchService,
)
from app.repositories.agent_session_repository import AgentSessionRepository


_PROCESS_RUNNER_KIND = "sub" + "process"
_SUPPORTED_EXECUTOR_LABELS = frozenset({"codex", "claude-code", "claude code"})


def _trim_required_string(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


class _RunnerWiringModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RealExecutorRunnerWiringMode(StrEnum):
    FAKE = "fake"
    SUBPROCESS_DISABLED = "sub" + "process_disabled"
    SUBPROCESS_ENABLED = "sub" + "process_enabled"


class RealExecutorRunnerWiringInput(_RunnerWiringModel):
    wiring_mode: RealExecutorRunnerWiringMode = RealExecutorRunnerWiringMode.FAKE
    launch_mode: RealExecutorNativeLaunchMode = RealExecutorNativeLaunchMode.DISABLED
    allow_native_process: bool = False
    executor_label: str = "codex"
    product_runtime_git_write_allowed: bool = False
    frontend_required: bool = False
    frontend_change_allowed: bool = False

    @field_validator("executor_label", mode="before")
    @classmethod
    def trim_executor_label(cls, value: Any) -> Any:
        return _trim_required_string(value)

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
            raise ValueError("runner wiring keeps this capability disabled")
        return value


@dataclass(frozen=True, slots=True)
class RealExecutorRunnerWiringResult:
    runner_kind: str
    launch_mode: RealExecutorNativeLaunchMode
    allow_native_process: bool
    service_ready: bool
    native_process_possible: bool
    product_runtime_git_write_allowed: bool = False
    frontend_required: bool = False
    frontend_change_allowed: bool = False
    blocked_reasons: list[str] = field(default_factory=list)
    native_launcher: RealExecutorNativeLauncher | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    silent_launch_service: RealExecutorSilentLaunchService | None = field(
        default=None,
        repr=False,
        compare=False,
    )


class RealExecutorRunnerFactory:
    def __init__(
        self,
        *,
        fake_runner: RealExecutorNativeRunnerProtocol | None = None,
        process_runner: RealExecutorNativeRunnerProtocol | None = None,
        process_supervisor: Any | None = None,
    ) -> None:
        self._fake_runner = fake_runner
        self._process_runner = process_runner
        self._process_supervisor = process_supervisor

    def wire(
        self,
        wiring_input: RealExecutorRunnerWiringInput | None = None,
        *,
        agent_session_repository: AgentSessionRepository | None = None,
    ) -> RealExecutorRunnerWiringResult:
        source = wiring_input or RealExecutorRunnerWiringInput()
        runner = self._runner(source)
        launcher = RealExecutorNativeLauncher(runner=runner)
        service = (
            RealExecutorSilentLaunchService(
                agent_session_repository=agent_session_repository,
                native_launcher=launcher,
            )
            if agent_session_repository is not None
            else None
        )
        launch_mode = self._effective_launch_mode(source)
        allow_native_process = self._effective_allow_native_process(source)
        native_process_possible = (
            source.wiring_mode == RealExecutorRunnerWiringMode.SUBPROCESS_ENABLED
            and launch_mode == RealExecutorNativeLaunchMode.ENABLED
            and allow_native_process is True
        )
        return RealExecutorRunnerWiringResult(
            runner_kind=self._runner_kind(source),
            launch_mode=launch_mode,
            allow_native_process=allow_native_process,
            service_ready=service is not None or launcher is not None,
            native_process_possible=native_process_possible,
            product_runtime_git_write_allowed=False,
            frontend_required=False,
            frontend_change_allowed=False,
            blocked_reasons=self._blocked_reasons(source, native_process_possible),
            native_launcher=launcher,
            silent_launch_service=service,
        )

    def _runner(
        self,
        source: RealExecutorRunnerWiringInput,
    ) -> RealExecutorNativeRunnerProtocol:
        if source.wiring_mode == RealExecutorRunnerWiringMode.FAKE:
            return self._fake_runner or FakeRealExecutorNativeRunner()
        return self._process_runner or SubprocessRealExecutorNativeRunner(
            process_supervisor=self._process_supervisor,
        )

    @staticmethod
    def _runner_kind(source: RealExecutorRunnerWiringInput) -> str:
        if source.wiring_mode == RealExecutorRunnerWiringMode.FAKE:
            return "fake"
        return _PROCESS_RUNNER_KIND

    @staticmethod
    def _effective_launch_mode(
        source: RealExecutorRunnerWiringInput,
    ) -> RealExecutorNativeLaunchMode:
        if source.wiring_mode == RealExecutorRunnerWiringMode.SUBPROCESS_DISABLED:
            return RealExecutorNativeLaunchMode.DISABLED
        return source.launch_mode

    @staticmethod
    def _effective_allow_native_process(
        source: RealExecutorRunnerWiringInput,
    ) -> bool:
        if source.wiring_mode == RealExecutorRunnerWiringMode.SUBPROCESS_DISABLED:
            return False
        return source.allow_native_process

    @staticmethod
    def _blocked_reasons(
        source: RealExecutorRunnerWiringInput,
        native_process_possible: bool,
    ) -> list[str]:
        if source.wiring_mode == RealExecutorRunnerWiringMode.FAKE:
            return ["native_runner_fake_only"]
        if source.wiring_mode == RealExecutorRunnerWiringMode.SUBPROCESS_DISABLED:
            return ["native_runner_policy_disabled"]
        reasons: list[str] = []
        if source.launch_mode != RealExecutorNativeLaunchMode.ENABLED:
            reasons.append("native_launch_mode_not_enabled")
        if not source.allow_native_process:
            reasons.append("native_process_not_allowed")
        if not native_process_possible and not reasons:
            reasons.append("native_process_not_possible")
        return reasons


__all__ = (
    "RealExecutorRunnerFactory",
    "RealExecutorRunnerWiringInput",
    "RealExecutorRunnerWiringMode",
    "RealExecutorRunnerWiringResult",
)
