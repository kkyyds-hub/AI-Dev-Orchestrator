"""Persistence helpers for Day07 change-batch execution-preparation records."""

from __future__ import annotations

import json
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db_tables import ChangeBatchTable
from app.domain._base import ensure_utc_datetime
from app.domain.change_batch import (
    ChangeBatch,
    ChangeBatchPlanSnapshot,
    ChangeBatchPreflight,
    ChangeBatchStatus,
)


class ChangeBatchRepository:
    """Encapsulate Day07 change-batch persistence operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, change_batch: ChangeBatch) -> ChangeBatch:
        """Persist one new change batch."""

        change_batch_row = ChangeBatchTable(
            id=change_batch.id,
            project_id=change_batch.project_id,
            repository_workspace_id=change_batch.repository_workspace_id,
            status=change_batch.status,
            title=change_batch.title,
            summary=change_batch.summary,
            plan_snapshots_json=self._serialize_plan_snapshots(change_batch.plan_snapshots),
            preflight_json=self._serialize_preflight(change_batch.preflight),
            created_at=change_batch.created_at,
            updated_at=change_batch.updated_at,
        )
        self.session.add(change_batch_row)
        self.session.commit()
        self.session.refresh(change_batch_row)
        return self._to_change_batch(change_batch_row)

    def update(self, change_batch: ChangeBatch) -> ChangeBatch:
        """Persist one updated change batch, including Day08 preflight state."""

        change_batch_row = self.session.get(ChangeBatchTable, change_batch.id)
        if change_batch_row is None:
            raise ValueError(f"Change batch not found: {change_batch.id}")

        change_batch_row.project_id = change_batch.project_id
        change_batch_row.repository_workspace_id = change_batch.repository_workspace_id
        change_batch_row.status = change_batch.status
        change_batch_row.title = change_batch.title
        change_batch_row.summary = change_batch.summary
        change_batch_row.plan_snapshots_json = self._serialize_plan_snapshots(
            change_batch.plan_snapshots
        )
        change_batch_row.preflight_json = self._serialize_preflight(change_batch.preflight)
        change_batch_row.created_at = change_batch.created_at
        change_batch_row.updated_at = change_batch.updated_at

        self.session.commit()
        self.session.refresh(change_batch_row)
        return self._to_change_batch(change_batch_row)

    def get_by_id(self, change_batch_id: UUID) -> ChangeBatch | None:
        """Return one persisted change batch by ID, if present."""

        change_batch_row = self.session.get(ChangeBatchTable, change_batch_id)
        if change_batch_row is None:
            return None

        return self._to_change_batch(change_batch_row)

    def get_active_by_project_id(self, project_id: UUID) -> ChangeBatch | None:
        """Return the current active Day07 batch for one project, if present."""

        statement = (
            select(ChangeBatchTable)
            .where(
                ChangeBatchTable.project_id == project_id,
                ChangeBatchTable.status == ChangeBatchStatus.PREPARING,
            )
            .order_by(ChangeBatchTable.updated_at.desc(), ChangeBatchTable.created_at.desc())
        )
        change_batch_row = self.session.execute(statement).scalars().first()
        if change_batch_row is None:
            return None

        return self._to_change_batch(change_batch_row)

    def list_by_project_id(self, project_id: UUID) -> list[ChangeBatch]:
        """Return all project change batches ordered by latest activity."""

        statement = (
            select(ChangeBatchTable)
            .where(ChangeBatchTable.project_id == project_id)
            .order_by(ChangeBatchTable.updated_at.desc(), ChangeBatchTable.created_at.desc())
        )
        change_batch_rows = self.session.execute(statement).scalars().all()
        return [self._to_change_batch(change_batch_row) for change_batch_row in change_batch_rows]

    @staticmethod
    def _to_change_batch(change_batch_row: ChangeBatchTable) -> ChangeBatch:
        """Convert one ORM row into its Day07 domain model."""

        return ChangeBatch(
            id=change_batch_row.id,
            project_id=change_batch_row.project_id,
            repository_workspace_id=change_batch_row.repository_workspace_id,
            status=change_batch_row.status,
            title=change_batch_row.title,
            summary=change_batch_row.summary,
            plan_snapshots=ChangeBatchRepository._deserialize_plan_snapshots(
                change_batch_row.plan_snapshots_json
            ),
            preflight=ChangeBatchRepository._deserialize_preflight(
                change_batch_row.preflight_json
            ),
            created_at=ensure_utc_datetime(change_batch_row.created_at),
            updated_at=ensure_utc_datetime(change_batch_row.updated_at),
        )

    @staticmethod
    def _serialize_plan_snapshots(values: list[ChangeBatchPlanSnapshot]) -> str:
        """Persist one snapshot list as JSON text."""

        return json.dumps(
            [value.model_dump(mode="json") for value in values],
            ensure_ascii=False,
        )

    @staticmethod
    def _serialize_preflight(value: ChangeBatchPreflight) -> str:
        """Persist one structured Day08 preflight result as JSON text."""

        return json.dumps(value.model_dump(mode="json"), ensure_ascii=False)

    @staticmethod
    def _deserialize_plan_snapshots(raw_value: str | None) -> list[ChangeBatchPlanSnapshot]:
        """Read one JSON-encoded snapshot list from SQLite."""

        if not raw_value:
            return []

        try:
            decoded_value = json.loads(raw_value)
        except json.JSONDecodeError:
            return []

        if not isinstance(decoded_value, list):
            return []

        normalized_items: list[ChangeBatchPlanSnapshot] = []
        for item in decoded_value:
            if not isinstance(item, dict):
                continue

            try:
                normalized_items.append(ChangeBatchPlanSnapshot.model_validate(item))
            except ValidationError:
                continue

        return normalized_items

    @staticmethod
    def _deserialize_preflight(raw_value: str | None) -> ChangeBatchPreflight:
        """Read one JSON-encoded Day08 preflight object from SQLite."""

        if not raw_value:
            return ChangeBatchPreflight()

        try:
            decoded_value = json.loads(raw_value)
        except json.JSONDecodeError:
            return ChangeBatchPreflight()

        if not isinstance(decoded_value, dict):
            return ChangeBatchPreflight()

        try:
            return ChangeBatchPreflight.model_validate(decoded_value)
        except ValidationError:
            return ChangeBatchPreflight()
