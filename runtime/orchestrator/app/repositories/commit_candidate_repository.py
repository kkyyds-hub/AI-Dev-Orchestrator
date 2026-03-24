"""Persistence helpers for V4 Day13 commit-candidate drafts."""

from __future__ import annotations

import json
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db_tables import CommitCandidateTable
from app.domain._base import ensure_utc_datetime
from app.domain.commit_candidate import CommitCandidate, CommitCandidateVersion


class CommitCandidateRepository:
    """Encapsulate Day13 commit-candidate persistence operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, candidate: CommitCandidate) -> CommitCandidate:
        """Persist one new commit-candidate aggregate."""

        row = CommitCandidateTable(
            id=candidate.id,
            project_id=candidate.project_id,
            change_batch_id=candidate.change_batch_id,
            change_batch_title=candidate.change_batch_title,
            status=candidate.status,
            current_version_number=candidate.current_version_number,
            versions_json=self._serialize_versions(candidate.versions),
            created_at=candidate.created_at,
            updated_at=candidate.updated_at,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return self.to_domain_model(row)

    def update(self, candidate: CommitCandidate) -> CommitCandidate:
        """Persist one updated commit-candidate aggregate."""

        row = self.session.get(CommitCandidateTable, candidate.id)
        if row is None:
            raise ValueError(f"Commit candidate not found: {candidate.id}")

        row.project_id = candidate.project_id
        row.change_batch_id = candidate.change_batch_id
        row.change_batch_title = candidate.change_batch_title
        row.status = candidate.status
        row.current_version_number = candidate.current_version_number
        row.versions_json = self._serialize_versions(candidate.versions)
        row.created_at = candidate.created_at
        row.updated_at = candidate.updated_at

        self.session.commit()
        self.session.refresh(row)
        return self.to_domain_model(row)

    def get_by_id(self, candidate_id: UUID) -> CommitCandidate | None:
        """Return one commit candidate by ID, if present."""

        row = self.session.get(CommitCandidateTable, candidate_id)
        if row is None:
            return None

        return self.to_domain_model(row)

    def get_by_change_batch_id(self, change_batch_id: UUID) -> CommitCandidate | None:
        """Return one commit candidate bound to the selected change batch, if present."""

        statement = select(CommitCandidateTable).where(
            CommitCandidateTable.change_batch_id == change_batch_id
        )
        row = self.session.execute(statement).scalars().first()
        if row is None:
            return None

        return self.to_domain_model(row)

    def list_by_project_id(self, project_id: UUID) -> list[CommitCandidate]:
        """Return all project commit candidates ordered by latest activity."""

        statement = (
            select(CommitCandidateTable)
            .where(CommitCandidateTable.project_id == project_id)
            .order_by(
                CommitCandidateTable.updated_at.desc(),
                CommitCandidateTable.created_at.desc(),
            )
        )
        rows = self.session.execute(statement).scalars().all()
        return [self.to_domain_model(row) for row in rows]

    @staticmethod
    def to_domain_model(row: CommitCandidateTable) -> CommitCandidate:
        """Convert one ORM row into the Day13 domain model."""

        return CommitCandidate(
            id=row.id,
            project_id=row.project_id,
            change_batch_id=row.change_batch_id,
            change_batch_title=row.change_batch_title,
            status=row.status,
            current_version_number=row.current_version_number,
            versions=CommitCandidateRepository._deserialize_versions(row.versions_json),
            created_at=ensure_utc_datetime(row.created_at),
            updated_at=ensure_utc_datetime(row.updated_at),
        )

    @staticmethod
    def _serialize_versions(versions: list[CommitCandidateVersion]) -> str:
        """Serialize immutable revision snapshots into JSON text."""

        return json.dumps(
            [item.model_dump(mode="json") for item in versions],
            ensure_ascii=False,
        )

    @staticmethod
    def _deserialize_versions(raw_value: str | None) -> list[CommitCandidateVersion]:
        """Deserialize persisted revision snapshots from JSON text."""

        if not raw_value:
            return []

        try:
            decoded_value = json.loads(raw_value)
        except json.JSONDecodeError:
            return []

        if not isinstance(decoded_value, list):
            return []

        normalized_items: list[CommitCandidateVersion] = []
        for item in decoded_value:
            if not isinstance(item, dict):
                continue
            try:
                normalized_items.append(CommitCandidateVersion.model_validate(item))
            except ValidationError:
                continue

        return normalized_items
