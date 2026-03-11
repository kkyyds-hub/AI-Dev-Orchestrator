"""Persist and read worker run logs from local JSONL files."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import json
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.core.config import settings
from app.domain._base import utc_now
from app.services.event_stream_service import event_stream_service


@dataclass(slots=True, frozen=True)
class RunLogEvent:
    """Structured log event exposed to the Day 12 console."""

    timestamp: str
    level: str
    event: str
    message: str
    data: dict[str, Any]


@dataclass(slots=True, frozen=True)
class RunLogReadResult:
    """Bounded log read result for one run."""

    log_path: str | None
    events: list[RunLogEvent]
    truncated: bool


class RunLoggingService:
    """Write small structured run events to the local runtime log folder."""

    def initialize_run_log(self, *, task_id: UUID, run_id: UUID) -> str:
        """Create the Day 9 log file and return its runtime-relative path."""

        log_path = self.build_log_path(task_id=task_id, run_id=run_id)
        absolute_path = self._resolve(log_path)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.touch(exist_ok=True)
        return log_path

    def build_log_path(self, *, task_id: UUID, run_id: UUID) -> str:
        """Build a stable runtime-relative log file path."""

        return (Path("logs") / "task-runs" / str(task_id) / f"{run_id}.jsonl").as_posix()

    def append_event(
        self,
        *,
        log_path: str,
        event: str,
        message: str,
        level: str = "info",
        data: dict[str, Any] | None = None,
    ) -> None:
        """Append a single JSON line event to the run log file."""

        record = {
            "timestamp": utc_now().isoformat(),
            "level": level,
            "event": event,
            "message": message,
            "data": self._normalize_data(data or {}),
        }

        absolute_path = self._resolve(log_path)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        with absolute_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False, default=str))
            file.write("\n")

        task_id, run_id = self._extract_ids_from_log_path(log_path)
        event_stream_service.publish_log_event(
            task_id=task_id,
            run_id=run_id,
            log_path=log_path,
            record=record,
        )

    def read_events(
        self,
        *,
        log_path: str | None,
        limit: int = 100,
    ) -> RunLogReadResult:
        """Read the latest structured log events for one run."""

        if log_path is None:
            return RunLogReadResult(log_path=None, events=[], truncated=False)

        absolute_path = self._resolve(log_path)
        if not absolute_path.exists():
            return RunLogReadResult(log_path=log_path, events=[], truncated=False)

        with absolute_path.open("r", encoding="utf-8") as file:
            lines = [line.strip() for line in file if line.strip()]

        truncated = len(lines) > limit
        selected_lines = lines[-limit:]
        events: list[RunLogEvent] = []
        for line in selected_lines:
            try:
                raw_record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not isinstance(raw_record, dict):
                continue

            raw_data = raw_record.get("data")
            events.append(
                RunLogEvent(
                    timestamp=str(raw_record.get("timestamp", "")),
                    level=str(raw_record.get("level", "info")),
                    event=str(raw_record.get("event", "unknown")),
                    message=str(raw_record.get("message", "")),
                    data=raw_data if isinstance(raw_data, dict) else {},
                )
            )

        return RunLogReadResult(
            log_path=log_path,
            events=events,
            truncated=truncated,
        )

    @staticmethod
    def _resolve(log_path: str) -> Path:
        """Resolve a runtime-relative log path to an absolute filesystem path."""

        return settings.runtime_data_dir / Path(log_path)

    @staticmethod
    def _extract_ids_from_log_path(log_path: str) -> tuple[str | None, str | None]:
        """Best-effort extraction of task/run IDs from the runtime-relative log path."""

        path = Path(log_path)
        parts = path.parts
        if len(parts) < 4:
            return None, None

        task_id = parts[-2]
        run_id = path.stem
        return task_id, run_id

    @classmethod
    def _normalize_data(cls, value: Any) -> Any:
        """Convert nested enums and containers into JSON-friendly values."""

        if isinstance(value, Enum):
            return getattr(value, "value", str(value))
        if isinstance(value, BaseModel):
            return cls._normalize_data(value.model_dump())
        if isinstance(value, dict):
            return {str(key): cls._normalize_data(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._normalize_data(item) for item in value]
        return value
