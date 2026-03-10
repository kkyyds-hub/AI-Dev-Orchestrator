"""Persist worker run logs to local JSONL files."""

from pathlib import Path
import json
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.domain._base import utc_now


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
            "data": data or {},
        }

        absolute_path = self._resolve(log_path)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        with absolute_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False, default=str))
            file.write("\n")

    @staticmethod
    def _resolve(log_path: str) -> Path:
        """Resolve a runtime-relative log path to an absolute filesystem path."""

        return settings.runtime_data_dir / Path(log_path)
