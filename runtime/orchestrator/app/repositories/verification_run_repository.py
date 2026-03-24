"""Persistence helpers for V4 Day10 repository verification runs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db_tables import VerificationRunTable
from app.domain._base import ensure_utc_datetime
from app.domain.verification_run import VerificationRun


class VerificationRunRepository:
    """Encapsulate Day10 verification-run persistence and lookup operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, verification_run: VerificationRun) -> VerificationRun:
        """Persist one immutable verification-run record."""

        verification_run_row = VerificationRunTable(
            id=verification_run.id,
            project_id=verification_run.project_id,
            repository_workspace_id=verification_run.repository_workspace_id,
            change_plan_id=verification_run.change_plan_id,
            change_batch_id=verification_run.change_batch_id,
            verification_template_id=verification_run.verification_template_id,
            verification_template_name=verification_run.verification_template_name,
            verification_template_category=verification_run.verification_template_category,
            command_source=verification_run.command_source,
            command=verification_run.command,
            working_directory=verification_run.working_directory,
            status=verification_run.status,
            failure_category=verification_run.failure_category,
            duration_seconds=verification_run.duration_seconds,
            output_summary=verification_run.output_summary,
            started_at=verification_run.started_at,
            finished_at=verification_run.finished_at,
            created_at=verification_run.created_at,
        )
        self.session.add(verification_run_row)
        self.session.commit()
        self.session.refresh(verification_run_row)
        return self.to_domain_model(verification_run_row)

    def get_by_id(self, verification_run_id: UUID) -> VerificationRun | None:
        """Return one verification run by ID, if present."""

        verification_run_row = self.session.get(VerificationRunTable, verification_run_id)
        if verification_run_row is None:
            return None

        return self.to_domain_model(verification_run_row)

    def list_by_project_id(
        self,
        project_id: UUID,
        *,
        change_batch_id: UUID | None = None,
        limit: int | None = None,
    ) -> list[VerificationRun]:
        """Return project-scoped verification runs ordered by latest completion."""

        statement = (
            select(VerificationRunTable)
            .where(VerificationRunTable.project_id == project_id)
            .order_by(
                VerificationRunTable.finished_at.desc(),
                VerificationRunTable.created_at.desc(),
            )
        )
        if change_batch_id is not None:
            statement = statement.where(
                VerificationRunTable.change_batch_id == change_batch_id
            )
        if limit is not None:
            statement = statement.limit(limit)

        verification_run_rows = self.session.execute(statement).scalars().all()
        return [self.to_domain_model(row) for row in verification_run_rows]

    @staticmethod
    def to_domain_model(verification_run_row: VerificationRunTable) -> VerificationRun:
        """Convert one ORM row into the Day10 domain model."""

        return VerificationRun(
            id=verification_run_row.id,
            project_id=verification_run_row.project_id,
            repository_workspace_id=verification_run_row.repository_workspace_id,
            change_plan_id=verification_run_row.change_plan_id,
            change_batch_id=verification_run_row.change_batch_id,
            verification_template_id=verification_run_row.verification_template_id,
            verification_template_name=verification_run_row.verification_template_name,
            verification_template_category=verification_run_row.verification_template_category,
            command_source=verification_run_row.command_source,
            command=verification_run_row.command,
            working_directory=verification_run_row.working_directory,
            status=verification_run_row.status,
            failure_category=verification_run_row.failure_category,
            duration_seconds=verification_run_row.duration_seconds,
            output_summary=verification_run_row.output_summary,
            started_at=ensure_utc_datetime(verification_run_row.started_at),
            finished_at=ensure_utc_datetime(verification_run_row.finished_at),
            created_at=ensure_utc_datetime(verification_run_row.created_at),
        )
