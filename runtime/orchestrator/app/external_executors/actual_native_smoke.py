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
from app.external_executors.actual_process_supervisor import (
    RealExecutorProcessStatus,
    RealExecutorProcessSupervisor,
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
    use_supervisor: bool = False
    supervisor_terminate_after_launch: bool = False
    supervisor_cleanup_after_launch: bool = False
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
    supervisor_enabled: bool = False
    supervisor_status: RealExecutorProcessStatus | None = None
    supervisor_registered: bool = False
    supervisor_cleanup_done: bool = False
    supervisor_action_success: bool | None = None

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
        process_supervisor: RealExecutorProcessSupervisor | None = None,
    ) -> None:
        self._fake_runner = fake_runner
        self._process_runner = process_runner
        self._process_supervisor = process_supervisor

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
            supervisor_summary = self._supervisor_summary(
                smoke_input=smoke_input,
                launch_result=launch_result,
                agent_session_id=str(agent_session.id),
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
                **supervisor_summary,
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
                process_supervisor=(
                    self._supervisor(smoke_input) if smoke_input.use_supervisor else None
                ),
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
            supervisor_enabled=smoke_input.use_supervisor,
            supervisor_status=None,
            supervisor_registered=False,
            supervisor_cleanup_done=False,
            supervisor_action_success=None,
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

    def _supervisor(
        self,
        smoke_input: RealExecutorNativeSmokeInput,
    ) -> RealExecutorProcessSupervisor:
        if self._process_supervisor is None:
            self._process_supervisor = RealExecutorProcessSupervisor()
        return self._process_supervisor

    def _supervisor_summary(
        self,
        *,
        smoke_input: RealExecutorNativeSmokeInput,
        launch_result,
        agent_session_id: str,
    ) -> dict[str, object]:
        if not smoke_input.use_supervisor:
            return {
                "supervisor_enabled": False,
                "supervisor_status": None,
                "supervisor_registered": False,
                "supervisor_cleanup_done": False,
                "supervisor_action_success": None,
            }
        supervisor = self._supervisor(smoke_input)
        process_handle_id = launch_result.runtime_handle_id
        if process_handle_id is None:
            return {
                "supervisor_enabled": True,
                "supervisor_status": None,
                "supervisor_registered": False,
                "supervisor_cleanup_done": False,
                "supervisor_action_success": None,
            }

        record = supervisor.get_status(process_handle_id)
        if (
            record.status == RealExecutorProcessStatus.MISSING
            and self._process_runner is not None
        ):
            record = supervisor.register(
                process_handle_id,
                executor_label=smoke_input.executor_label,
                agent_session_id=agent_session_id,
                workspace_path=smoke_input.workspace_path,
                process_adapter=self._process_runner,
            )

        supervisor_status = record.status
        supervisor_registered = record.status != RealExecutorProcessStatus.MISSING
        supervisor_action_success: bool | None = None
        supervisor_cleanup_done = False

        if supervisor_registered and smoke_input.supervisor_terminate_after_launch:
            action_result = supervisor.terminate(process_handle_id)
            supervisor_status = action_result.status
            supervisor_action_success = action_result.action_success

        if supervisor_registered and smoke_input.supervisor_cleanup_after_launch:
            action_result = supervisor.cleanup(process_handle_id)
            supervisor_status = action_result.status
            supervisor_action_success = action_result.action_success
            supervisor_cleanup_done = (
                action_result.status == RealExecutorProcessStatus.CLEANUP_DONE
                and action_result.action_success
            )

        return {
            "supervisor_enabled": True,
            "supervisor_status": supervisor_status,
            "supervisor_registered": supervisor_registered,
            "supervisor_cleanup_done": supervisor_cleanup_done,
            "supervisor_action_success": supervisor_action_success,
        }


__all__ = (
    "RealExecutorNativeSmokeInput",
    "RealExecutorNativeSmokeResult",
    "RealExecutorNativeSmokeRunner",
)
