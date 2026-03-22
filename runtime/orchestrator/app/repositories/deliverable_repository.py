"""Persistence helpers for deliverables and immutable version snapshots."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.db_tables import DeliverableTable, DeliverableVersionTable
from app.domain.deliverable import Deliverable, DeliverableVersion
from app.domain._base import ensure_utc_datetime


@dataclass(slots=True, frozen=True)
class DeliverableRecord:
    """One deliverable head together with its ordered immutable versions."""

    deliverable: Deliverable
    versions: list[DeliverableVersion]


class DeliverableRepository:
    """Encapsulate deliverable-related database operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_with_initial_version(
        self,
        *,
        deliverable: Deliverable,
        initial_version: DeliverableVersion,
    ) -> DeliverableRecord:
        """Persist one deliverable head together with its first snapshot."""

        if deliverable.id != initial_version.deliverable_id:
            raise ValueError("Initial deliverable version must target the new deliverable.")

        deliverable_row = DeliverableTable(
            id=deliverable.id,
            project_id=deliverable.project_id,
            type=deliverable.type,
            title=deliverable.title,
            stage=deliverable.stage,
            created_by_role_code=deliverable.created_by_role_code,
            current_version_number=deliverable.current_version_number,
            created_at=deliverable.created_at,
            updated_at=deliverable.updated_at,
        )
        deliverable_row.versions.append(self._build_version_row(initial_version))

        self.session.add(deliverable_row)
        self.session.commit()

        persisted_record = self.get_record_by_id(deliverable.id)
        if persisted_record is None:
            raise ValueError(
                f"Deliverable not found after initial persistence: {deliverable.id}"
            )

        return persisted_record

    def add_version(
        self,
        *,
        deliverable_id: UUID,
        version: DeliverableVersion,
    ) -> DeliverableRecord:
        """Append one immutable version and update the head version pointer."""

        if deliverable_id != version.deliverable_id:
            raise ValueError("Deliverable version deliverable_id does not match the target.")

        deliverable_row = self.session.get(DeliverableTable, deliverable_id)
        if deliverable_row is None:
            raise ValueError(f"Deliverable not found: {deliverable_id}")

        deliverable_row.current_version_number = version.version_number
        deliverable_row.updated_at = version.created_at
        self.session.add(self._build_version_row(version))
        self.session.commit()

        persisted_record = self.get_record_by_id(deliverable_id)
        if persisted_record is None:
            raise ValueError(
                f"Deliverable not found after version append: {deliverable_id}"
            )

        return persisted_record

    def get_record_by_id(self, deliverable_id: UUID) -> DeliverableRecord | None:
        """Return one deliverable plus all persisted versions."""

        statement = (
            select(DeliverableTable)
            .options(selectinload(DeliverableTable.versions))
            .where(DeliverableTable.id == deliverable_id)
        )
        deliverable_row = self.session.execute(statement).scalar_one_or_none()
        if deliverable_row is None:
            return None

        return self._to_record(deliverable_row)

    def list_records_by_project_id(self, project_id: UUID) -> list[DeliverableRecord]:
        """Return all deliverables under one project ordered by latest activity."""

        statement = (
            select(DeliverableTable)
            .options(selectinload(DeliverableTable.versions))
            .where(DeliverableTable.project_id == project_id)
            .order_by(DeliverableTable.updated_at.desc(), DeliverableTable.created_at.desc())
        )
        deliverable_rows = self.session.execute(statement).scalars().all()
        return [self._to_record(deliverable_row) for deliverable_row in deliverable_rows]

    @staticmethod
    def _build_version_row(version: DeliverableVersion) -> DeliverableVersionTable:
        """Convert one domain version snapshot into its ORM row."""

        return DeliverableVersionTable(
            id=version.id,
            deliverable_id=version.deliverable_id,
            version_number=version.version_number,
            author_role_code=version.author_role_code,
            summary=version.summary,
            content=version.content,
            content_format=version.content_format,
            source_task_id=version.source_task_id,
            source_run_id=version.source_run_id,
            created_at=version.created_at,
        )

    def _to_record(self, deliverable_row: DeliverableTable) -> DeliverableRecord:
        """Convert one ORM row bundle into domain objects."""

        versions = sorted(
            (self._to_version(version_row) for version_row in deliverable_row.versions),
            key=lambda item: (item.version_number, item.created_at),
            reverse=True,
        )
        return DeliverableRecord(
            deliverable=self._to_deliverable(deliverable_row),
            versions=versions,
        )

    @staticmethod
    def _to_deliverable(deliverable_row: DeliverableTable) -> Deliverable:
        """Convert one deliverable head row into its domain model."""

        return Deliverable(
            id=deliverable_row.id,
            project_id=deliverable_row.project_id,
            type=deliverable_row.type,
            title=deliverable_row.title,
            stage=deliverable_row.stage,
            created_by_role_code=deliverable_row.created_by_role_code,
            current_version_number=deliverable_row.current_version_number,
            created_at=ensure_utc_datetime(deliverable_row.created_at),
            updated_at=ensure_utc_datetime(deliverable_row.updated_at),
        )

    @staticmethod
    def _to_version(version_row: DeliverableVersionTable) -> DeliverableVersion:
        """Convert one persisted snapshot row into a domain version object."""

        return DeliverableVersion(
            id=version_row.id,
            deliverable_id=version_row.deliverable_id,
            version_number=version_row.version_number,
            author_role_code=version_row.author_role_code,
            summary=version_row.summary,
            content=version_row.content,
            content_format=version_row.content_format,
            source_task_id=version_row.source_task_id,
            source_run_id=version_row.source_run_id,
            created_at=ensure_utc_datetime(version_row.created_at),
        )
