"""In-memory registry for supervised native executor processes."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _trim_required_string(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


class _ProcessSupervisorModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RealExecutorProcessStatus(StrEnum):
    REGISTERED = "registered"
    RUNNING = "running"
    TERMINATED = "terminated"
    KILLED = "killed"
    MISSING = "missing"
    CLEANUP_DONE = "cleanup_done"


class RealExecutorProcessRecord(_ProcessSupervisorModel):
    process_handle_id: str
    executor_label: str
    agent_session_id: str
    workspace_path: str | None = None
    status: RealExecutorProcessStatus = RealExecutorProcessStatus.REGISTERED

    @field_validator(
        "process_handle_id",
        "executor_label",
        "agent_session_id",
        "workspace_path",
        mode="before",
    )
    @classmethod
    def trim_strings(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("process_handle_id", "executor_label", "agent_session_id")
    @classmethod
    def require_strings(cls, value: str) -> str:
        if not value:
            raise ValueError("field must not be empty")
        return value


class RealExecutorProcessActionResult(_ProcessSupervisorModel):
    process_handle_id: str
    status: RealExecutorProcessStatus
    action_success: bool = False
    blocked_reasons: list[str] = Field(default_factory=list)

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


class RealExecutorProcessRegistrySnapshot(_ProcessSupervisorModel):
    total_records: int
    records: list[RealExecutorProcessRecord] = Field(default_factory=list)


class _RegistryEntry:
    def __init__(
        self,
        *,
        record: RealExecutorProcessRecord,
        process_adapter: Any | None,
    ) -> None:
        self.record = record
        self.process_adapter = process_adapter


class RealExecutorProcessSupervisor:
    def __init__(self) -> None:
        self._entries: dict[str, _RegistryEntry] = {}

    def register(
        self,
        handle,
        *,
        executor_label: str,
        agent_session_id: str,
        workspace_path: str | None,
        process_adapter: Any | None = None,
    ) -> RealExecutorProcessRecord:
        process_handle_id = self._handle_id(handle)
        record = RealExecutorProcessRecord(
            process_handle_id=process_handle_id,
            executor_label=executor_label,
            agent_session_id=agent_session_id,
            workspace_path=workspace_path,
            status=RealExecutorProcessStatus.RUNNING,
        )
        self._entries[process_handle_id] = _RegistryEntry(
            record=record,
            process_adapter=process_adapter,
        )
        return record

    def get_status(self, process_handle_id: str) -> RealExecutorProcessRecord:
        entry = self._entries.get(process_handle_id)
        if entry is None:
            return RealExecutorProcessRecord(
                process_handle_id=process_handle_id,
                executor_label="unknown",
                agent_session_id="unknown",
                workspace_path=None,
                status=RealExecutorProcessStatus.MISSING,
            )
        return entry.record

    def terminate(self, process_handle_id: str) -> RealExecutorProcessActionResult:
        return self._process_action(
            process_handle_id,
            status=RealExecutorProcessStatus.TERMINATED,
            adapter_method="terminate",
        )

    def kill(self, process_handle_id: str) -> RealExecutorProcessActionResult:
        return self._process_action(
            process_handle_id,
            status=RealExecutorProcessStatus.KILLED,
            adapter_method="kill",
        )

    def cleanup(self, process_handle_id: str) -> RealExecutorProcessActionResult:
        entry = self._entries.pop(process_handle_id, None)
        if entry is None:
            return self._missing_result(process_handle_id)
        return RealExecutorProcessActionResult(
            process_handle_id=process_handle_id,
            status=RealExecutorProcessStatus.CLEANUP_DONE,
            action_success=True,
            blocked_reasons=[],
        )

    def snapshot(self) -> RealExecutorProcessRegistrySnapshot:
        records = [entry.record for entry in self._entries.values()]
        return RealExecutorProcessRegistrySnapshot(
            total_records=len(records),
            records=records,
        )

    def _process_action(
        self,
        process_handle_id: str,
        *,
        status: RealExecutorProcessStatus,
        adapter_method: str,
    ) -> RealExecutorProcessActionResult:
        entry = self._entries.get(process_handle_id)
        if entry is None:
            return self._missing_result(process_handle_id)
        if entry.process_adapter is None:
            return RealExecutorProcessActionResult(
                process_handle_id=process_handle_id,
                status=entry.record.status,
                action_success=False,
                blocked_reasons=["process_adapter_missing"],
            )
        getattr(entry.process_adapter, adapter_method)()
        updated_record = entry.record.model_copy(update={"status": status})
        self._entries[process_handle_id] = _RegistryEntry(
            record=updated_record,
            process_adapter=entry.process_adapter,
        )
        return RealExecutorProcessActionResult(
            process_handle_id=process_handle_id,
            status=status,
            action_success=True,
            blocked_reasons=[],
        )

    @staticmethod
    def _missing_result(process_handle_id: str) -> RealExecutorProcessActionResult:
        return RealExecutorProcessActionResult(
            process_handle_id=process_handle_id,
            status=RealExecutorProcessStatus.MISSING,
            action_success=False,
            blocked_reasons=["process_handle_missing"],
        )

    @staticmethod
    def _handle_id(handle) -> str:
        if isinstance(handle, str):
            return handle.strip()
        return str(handle.process_handle_id).strip()


__all__ = (
    "RealExecutorProcessActionResult",
    "RealExecutorProcessRecord",
    "RealExecutorProcessRegistrySnapshot",
    "RealExecutorProcessStatus",
    "RealExecutorProcessSupervisor",
)
