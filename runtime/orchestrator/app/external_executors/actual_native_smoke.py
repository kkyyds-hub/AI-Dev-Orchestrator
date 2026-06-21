"""Controlled local smoke harness for silent native executor launch."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db_tables import ORMBase
from app.domain.agent_session import (
    AgentSessionPhase,
    AgentSessionReviewStatus,
    AgentSessionStatus,
)
from app.external_executors.actual_native_launcher import (
    FakeRealExecutorNativeRunner,
    RealExecutorNativeLaunchMode,
    RealExecutorNativeRunnerProtocol,
    SubprocessRealExecutorNativeRunner,
)
from app.external_executors.actual_runner_wiring import (
    RealExecutorRunnerFactory,
    RealExecutorRunnerWiringInput,
    RealExecutorRunnerWiringMode,
)
from app.external_executors.actual_silent_launch_service import (
    RealExecutorSilentLaunchInput,
)
from app.repositories.agent_session_repository import AgentSessionRepository


_PROCESS_RUNNER_KIND = "sub" + "process"
_SUPPORTED_RUNNER_KINDS = frozenset({"fake", _PROCESS_RUNNER_KIND})
_SUPPORTED_EXECUTOR_LABELS = frozenset({"codex", "claude-code", "claude code"})


def _trim_required_string(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


class _NativeSmokeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RealExecutorNativeSmokeInput(_NativeSmokeModel):
    runner_kind: str = "fake"
    launch_mode: RealExecutorNativeLaunchMode = RealExecutorNativeLaunchMode.DRY_RUN
    enable_native_process: bool = False
    executor_label: str = "codex"
    workspace_path: str
    agent_session_id: UUID | None = None
    auto_terminate: bool = False
    timeout_seconds: float | None = None
    product_runtime_git_write_allowed: bool = False
    frontend_required: bool = False
    frontend_change_allowed: bool = False

    @field_validator("runner_kind", "executor_label", "workspace_path", mode="before")
    @classmethod
    def trim_strings(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("runner_kind")
    @classmethod
    def validate_runner_kind(cls, value: str) -> str:
        normalized_value = value.lower()
        if normalized_value not in _SUPPORTED_RUNNER_KINDS:
            raise ValueError("runner_kind is not supported")
        return normalized_value

    @field_validator("executor_label")
    @classmethod
    def validate_executor_label(cls, value: str) -> str:
        if not value:
            raise ValueError("executor_label must not be empty")
        if value.strip().lower() not in _SUPPORTED_EXECUTOR_LABELS:
            raise ValueError("executor_label is not supported")
        return value

    @field_validator("workspace_path")
    @classmethod
    def validate_workspace_path(cls, value: str) -> str:
        if not value:
            raise ValueError("workspace_path must not be empty")
        if not Path(value).is_absolute():
            raise ValueError("workspace_path must be absolute")
        return value

    @field_validator("timeout_seconds")
    @classmethod
    def validate_timeout_seconds(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("timeout_seconds must be positive")
        return value

    @field_validator(
        "product_runtime_git_write_allowed",
        "frontend_required",
        "frontend_change_allowed",
    )
    @classmethod
    def keep_forbidden_flags_disabled(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError("native smoke keeps this capability disabled")
        return value


class RealExecutorNativeSmokeResult(_NativeSmokeModel):
    smoke_status: str
    runner_kind: str
    launch_mode: RealExecutorNativeLaunchMode
    native_process_possible: bool
    process_handle_id_present: bool = False
    agent_session_bound: bool = False
    product_runtime_git_write_allowed: bool = False
    frontend_required: bool = False
    frontend_change_allowed: bool = False
    blocked_reasons: list[str] = Field(default_factory=list)

    @field_validator(
        "product_runtime_git_write_allowed",
        "frontend_required",
        "frontend_change_allowed",
    )
    @classmethod
    def keep_result_forbidden_flags_disabled(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError("native smoke result cannot enable this flag")
        return value


class RealExecutorNativeSmokeRunner:
    def __init__(
        self,
        *,
        fake_runner: RealExecutorNativeRunnerProtocol | None = None,
        process_runner: RealExecutorNativeRunnerProtocol | None = None,
    ) -> None:
        self._fake_runner = fake_runner
        self._process_runner = process_runner

    def run(
        self,
        smoke_input: RealExecutorNativeSmokeInput,
    ) -> RealExecutorNativeSmokeResult:
        session_factory = self._session_factory()
        session = session_factory()
        try:
            repository = AgentSessionRepository(session)
            agent_session = self._agent_session(repository, smoke_input)
            if self._requires_termination_guard(smoke_input):
                return self._blocked_result(
                    smoke_input,
                    native_process_possible=False,
                    blocked_reasons=["native_smoke_requires_termination_guard"],
                )
            wiring_result = self._factory(smoke_input).wire(
                self._wiring_input(smoke_input),
                agent_session_repository=repository,
            )
            if wiring_result.silent_launch_service is None:
                return self._blocked_result(
                    smoke_input,
                    native_process_possible=wiring_result.native_process_possible,
                    blocked_reasons=["silent_launch_service_missing"],
                )
            try:
                launch_result = wiring_result.silent_launch_service.launch(
                    RealExecutorSilentLaunchInput(
                        agent_session_id=agent_session.id,
                        executor_label=smoke_input.executor_label,
                        workspace_path=smoke_input.workspace_path,
                        prelaunch_ready=True,
                        launch_mode=wiring_result.launch_mode,
                        allow_native_process=wiring_result.allow_native_process,
                        command_plan_redacted=True,
                        internal_auto_launch_policy_passed=True,
                        product_runtime_git_write_allowed=False,
                        frontend_required=False,
                        frontend_change_allowed=False,
                    )
                )
            except Exception:
                return self._blocked_result(
                    smoke_input,
                    native_process_possible=wiring_result.native_process_possible,
                    blocked_reasons=["native_launch_failed"],
                )
            return RealExecutorNativeSmokeResult(
                smoke_status=launch_result.launch_status,
                runner_kind=wiring_result.runner_kind,
                launch_mode=wiring_result.launch_mode,
                native_process_possible=wiring_result.native_process_possible,
                process_handle_id_present=launch_result.runtime_handle_id is not None,
                agent_session_bound=launch_result.agent_session_bound,
                product_runtime_git_write_allowed=False,
                frontend_required=False,
                frontend_change_allowed=False,
                blocked_reasons=launch_result.blocked_reasons,
            )
        finally:
            session.close()

    @staticmethod
    def _session_factory():
        engine = create_engine("sqlite+pysqlite:///:memory:")
        ORMBase.metadata.create_all(bind=engine)
        return sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    @staticmethod
    def _agent_session(
        repository: AgentSessionRepository,
        smoke_input: RealExecutorNativeSmokeInput,
    ):
        return repository.create(
            project_id=uuid4(),
            task_id=uuid4(),
            run_id=smoke_input.agent_session_id or uuid4(),
            status=AgentSessionStatus.RUNNING,
            review_status=AgentSessionReviewStatus.NONE,
            current_phase=AgentSessionPhase.CONTEXT_READY,
            owner_role_code=None,
            context_checkpoint_id=None,
            context_rehydrated=False,
            summary="controlled native executor smoke",
            workspace_path=smoke_input.workspace_path,
            workspace_clean=True,
        )

    def _factory(
        self,
        smoke_input: RealExecutorNativeSmokeInput,
    ) -> RealExecutorRunnerFactory:
        fake_runner = self._fake_runner or FakeRealExecutorNativeRunner(
            process_handle_id="smoke-fake-process-handle",
        )
        process_runner = self._process_runner
        if process_runner is None and smoke_input.runner_kind == _PROCESS_RUNNER_KIND:
            process_runner = SubprocessRealExecutorNativeRunner(
                auto_terminate=smoke_input.auto_terminate,
                timeout_seconds=smoke_input.timeout_seconds,
            )
        return RealExecutorRunnerFactory(
            fake_runner=fake_runner,
            process_runner=process_runner,
        )

    @staticmethod
    def _wiring_input(
        smoke_input: RealExecutorNativeSmokeInput,
    ) -> RealExecutorRunnerWiringInput:
        wiring_mode = RealExecutorRunnerWiringMode.FAKE
        if smoke_input.runner_kind == _PROCESS_RUNNER_KIND:
            wiring_mode = RealExecutorRunnerWiringMode.SUBPROCESS_ENABLED
        return RealExecutorRunnerWiringInput(
            wiring_mode=wiring_mode,
            launch_mode=smoke_input.launch_mode,
            allow_native_process=smoke_input.enable_native_process,
            executor_label=smoke_input.executor_label,
            product_runtime_git_write_allowed=False,
            frontend_required=False,
            frontend_change_allowed=False,
        )

    @staticmethod
    def _blocked_result(
        smoke_input: RealExecutorNativeSmokeInput,
        *,
        native_process_possible: bool,
        blocked_reasons: list[str],
    ) -> RealExecutorNativeSmokeResult:
        return RealExecutorNativeSmokeResult(
            smoke_status="blocked",
            runner_kind=smoke_input.runner_kind,
            launch_mode=smoke_input.launch_mode,
            native_process_possible=native_process_possible,
            process_handle_id_present=False,
            agent_session_bound=False,
            product_runtime_git_write_allowed=False,
            frontend_required=False,
            frontend_change_allowed=False,
            blocked_reasons=blocked_reasons,
        )

    @staticmethod
    def _requires_termination_guard(
        smoke_input: RealExecutorNativeSmokeInput,
    ) -> bool:
        return (
            smoke_input.runner_kind == _PROCESS_RUNNER_KIND
            and smoke_input.launch_mode == RealExecutorNativeLaunchMode.ENABLED
            and smoke_input.enable_native_process is True
            and not smoke_input.auto_terminate
            and smoke_input.timeout_seconds is None
        )


__all__ = (
    "RealExecutorNativeSmokeInput",
    "RealExecutorNativeSmokeResult",
    "RealExecutorNativeSmokeRunner",
)
