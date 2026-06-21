"""Bind silent native executor launch decisions onto AgentSession."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.agent_session import (
    AgentType,
    CodingSessionActivityState,
    CodingSessionStatus,
    RuntimeType,
    WorkspaceType,
)
from app.external_executors.actual_native_launcher import (
    RealExecutorNativeLaunchInput,
    RealExecutorNativeLaunchMode,
    RealExecutorNativeLauncher,
)
from app.repositories.agent_session_repository import AgentSessionRepository


_SUPPORTED_EXECUTOR_LABELS = frozenset({"codex", "claude-code", "claude code"})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _trim_required_string(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _trim_optional_string(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


class _SilentLaunchModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RealExecutorSilentLaunchInput(_SilentLaunchModel):
    agent_session_id: UUID
    executor_label: str = "codex"
    workspace_path: str | None = None
    prelaunch_ready: bool = False
    launch_mode: RealExecutorNativeLaunchMode = RealExecutorNativeLaunchMode.DISABLED
    allow_native_process: bool = False
    command_plan_redacted: bool = True
    internal_auto_launch_policy_passed: bool = True
    product_runtime_git_write_allowed: bool = False
    frontend_required: bool = False
    frontend_change_allowed: bool = False

    @field_validator("executor_label", mode="before")
    @classmethod
    def trim_executor_label(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("workspace_path", mode="before")
    @classmethod
    def trim_workspace_path(cls, value: Any) -> Any:
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
            raise ValueError("silent launch keeps this capability disabled")
        return value

    @model_validator(mode="after")
    def validate_workspace_path(self) -> "RealExecutorSilentLaunchInput":
        if self.launch_mode == RealExecutorNativeLaunchMode.DISABLED:
            return self
        if self.workspace_path is None:
            raise ValueError("workspace_path is required")
        if not Path(self.workspace_path).is_absolute():
            raise ValueError("workspace_path must be absolute")
        return self


class RealExecutorSilentLaunchResult(_SilentLaunchModel):
    launch_status: str
    agent_session_bound: bool = False
    runtime_handle_id: str | None = None
    agent_session_id: UUID
    executor_label: str
    workspace_path: str | None = None
    coding_status_after: str | None = None
    activity_state_after: str | None = None
    native_process_started: bool = False
    product_runtime_git_write_allowed: bool = False
    frontend_required: bool = False
    frontend_change_allowed: bool = False
    blocked_reasons: list[str] = Field(default_factory=list)
    decided_at: datetime = Field(default_factory=_utc_now)

    @field_validator(
        "product_runtime_git_write_allowed",
        "frontend_required",
        "frontend_change_allowed",
    )
    @classmethod
    def keep_result_forbidden_flags_disabled(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError("silent launch result cannot enable this flag")
        return value


class RealExecutorSilentLaunchService:
    def __init__(
        self,
        *,
        agent_session_repository: AgentSessionRepository,
        native_launcher: RealExecutorNativeLauncher | None = None,
    ) -> None:
        self._agent_session_repository = agent_session_repository
        self._native_launcher = native_launcher or RealExecutorNativeLauncher()

    def launch(
        self,
        launch_input: RealExecutorSilentLaunchInput,
    ) -> RealExecutorSilentLaunchResult:
        native_decision = self._native_launcher.decide(
            self._native_launch_input(launch_input)
        )
        blocked_reasons = list(native_decision.blocked_reasons)
        if not launch_input.internal_auto_launch_policy_passed:
            blocked_reasons.append("internal_auto_launch_policy_failed")

        if (
            launch_input.internal_auto_launch_policy_passed
            and native_decision.launch_status == "launch_started"
            and native_decision.process_handle_id is not None
        ):
            updated = self._agent_session_repository.update_status(
                launch_input.agent_session_id,
                agent_type=self._agent_type(launch_input.executor_label),
                runtime_type=RuntimeType.PROCESS,
                runtime_handle_id=native_decision.process_handle_id,
                coding_status=CodingSessionStatus.SPAWNING,
                activity_state=CodingSessionActivityState.ACTIVE,
                workspace_type=WorkspaceType.WORKTREE,
                workspace_path=launch_input.workspace_path,
                last_workspace_error=None,
            )
            return RealExecutorSilentLaunchResult(
                launch_status="launch_started",
                agent_session_bound=True,
                runtime_handle_id=updated.runtime_handle_id,
                agent_session_id=launch_input.agent_session_id,
                executor_label=launch_input.executor_label,
                workspace_path=updated.workspace_path,
                coding_status_after=(
                    updated.coding_status.value
                    if updated.coding_status is not None
                    else None
                ),
                activity_state_after=(
                    updated.activity_state.value
                    if updated.activity_state is not None
                    else None
                ),
                native_process_started=native_decision.native_process_started,
                product_runtime_git_write_allowed=False,
                frontend_required=False,
                frontend_change_allowed=False,
                blocked_reasons=[],
            )

        return RealExecutorSilentLaunchResult(
            launch_status=(
                "blocked"
                if blocked_reasons
                else native_decision.launch_status
            ),
            agent_session_bound=False,
            runtime_handle_id=None,
            agent_session_id=launch_input.agent_session_id,
            executor_label=launch_input.executor_label,
            workspace_path=launch_input.workspace_path,
            coding_status_after=None,
            activity_state_after=None,
            native_process_started=False,
            product_runtime_git_write_allowed=False,
            frontend_required=False,
            frontend_change_allowed=False,
            blocked_reasons=blocked_reasons,
        )

    @staticmethod
    def _native_launch_input(
        launch_input: RealExecutorSilentLaunchInput,
    ) -> RealExecutorNativeLaunchInput:
        native_launch_mode = launch_input.launch_mode
        if not launch_input.internal_auto_launch_policy_passed:
            native_launch_mode = RealExecutorNativeLaunchMode.DISABLED
        return RealExecutorNativeLaunchInput(
            launch_mode=native_launch_mode,
            executor_label=launch_input.executor_label,
            workspace_path=launch_input.workspace_path,
            agent_session_id=str(launch_input.agent_session_id),
            prelaunch_ready=launch_input.prelaunch_ready,
            command_plan_redacted=launch_input.command_plan_redacted,
            product_runtime_git_write_allowed=False,
            frontend_required=False,
            frontend_change_allowed=False,
            allow_native_process=launch_input.allow_native_process,
        )

    @staticmethod
    def _agent_type(executor_label: str) -> AgentType:
        normalized_label = executor_label.strip().lower()
        if normalized_label == "codex":
            return AgentType.CODEX
        if normalized_label in {"claude-code", "claude code"}:
            return AgentType.CLAUDE_CODE
        raise ValueError("executor_label is not supported")


__all__ = (
    "RealExecutorSilentLaunchInput",
    "RealExecutorSilentLaunchResult",
    "RealExecutorSilentLaunchService",
)
