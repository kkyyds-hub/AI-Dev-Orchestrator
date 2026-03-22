"""File-backed storage for V2-C failure review records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.config import settings


class FailureReviewRepository:
    """Persist one failure review JSON document per run."""

    def __init__(self) -> None:
        self._base_dir = settings.runtime_data_dir / "failure-reviews"

    def save(self, *, run_id: UUID, payload: dict[str, Any]) -> str:
        """Write one failure review payload and return its runtime-relative path."""

        absolute_path = self._resolve_run_path(run_id)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        with absolute_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2, default=str)
            file.write("\n")

        return absolute_path.relative_to(settings.runtime_data_dir).as_posix()

    def get(self, *, run_id: UUID) -> dict[str, Any] | None:
        """Load one persisted review payload if it exists."""

        absolute_path = self._resolve_run_path(run_id)
        if not absolute_path.exists():
            return None

        try:
            raw_payload = json.loads(absolute_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

        return raw_payload if isinstance(raw_payload, dict) else None

    def list_all(self) -> list[dict[str, Any]]:
        """Return all stored review payloads ordered from newest to oldest."""

        if not self._base_dir.exists():
            return []

        payloads: list[tuple[float, dict[str, Any]]] = []
        for absolute_path in self._base_dir.rglob("*.json"):
            payload = self._load_payload(absolute_path)
            if payload is None:
                continue

            payloads.append((absolute_path.stat().st_mtime, payload))

        payloads.sort(key=lambda item: item[0], reverse=True)
        return [payload for _, payload in payloads]

    def list_for_run_ids(self, *, run_ids: list[UUID]) -> list[dict[str, Any]]:
        """Return stored review payloads belonging to the provided run IDs."""

        if not run_ids:
            return []

        expected_run_ids = {str(run_id) for run_id in run_ids}
        payloads: list[tuple[float, dict[str, Any]]] = []

        for absolute_path in self._base_dir.rglob("*.json"):
            payload = self._load_payload(absolute_path)
            if payload is None:
                continue

            if str(payload.get("run_id", "")) not in expected_run_ids:
                continue

            payloads.append((absolute_path.stat().st_mtime, payload))

        payloads.sort(key=lambda item: item[0], reverse=True)
        return [payload for _, payload in payloads]

    def _resolve_run_path(self, run_id: UUID) -> Path:
        """Return the absolute review path for one run."""

        run_prefix = str(run_id)[:2]
        return self._base_dir / run_prefix / f"{run_id}.json"

    @staticmethod
    def _load_payload(absolute_path: Path) -> dict[str, Any] | None:
        """Load one stored JSON payload and ignore broken files."""

        try:
            raw_payload = json.loads(absolute_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

        return raw_payload if isinstance(raw_payload, dict) else None
