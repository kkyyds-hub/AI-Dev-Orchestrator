"""Persistence helpers for run AI summary records."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.db_tables import RunAISummaryTable
from app.domain.run_ai_summary import (
    RunAISummary,
    RunAISummaryStatus,
    RunAISummaryType,
)


class RunAISummaryRepository:
    """Encapsulate persistence operations for run AI summaries."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, summary: RunAISummary) -> RunAISummary:
        """Persist one run AI summary snapshot."""

        row = RunAISummaryTable(
            id=summary.id,
            run_id=summary.run_id,
            project_id=summary.project_id,
            task_id=summary.task_id,
            deliverable_id=summary.deliverable_id,
            summary_type=summary.summary_type,
            status=summary.status,
            source=summary.source,
            summary_markdown=summary.summary_markdown,
            source_version=summary.source_version,
            source_fingerprint=summary.source_fingerprint,
            source_hash=summary.source_hash,
            model_provider=summary.model_provider,
            model_name=summary.model_name,
            prompt_hash=summary.prompt_hash,
            provider_receipt_id=summary.provider_receipt_id,
            generated_at=summary.generated_at,
            created_at=summary.created_at,
            updated_at=summary.updated_at,
            error_summary=summary.error_summary,
            stale=summary.stale,
        )
        self.session.add(row)
        self.session.flush()
        self.session.commit()
        return self._to_domain(row)

    def get_by_id(self, summary_id: UUID) -> RunAISummary | None:
        """Return one AI summary by ID if it exists."""

        row = self.session.get(RunAISummaryTable, summary_id)
        if row is None:
            return None

        return self._to_domain(row)

    def list_by_run_id(self, run_id: UUID) -> list[RunAISummary]:
        """Return all summary records for one run ordered newest first."""

        statement = (
            select(RunAISummaryTable)
            .where(RunAISummaryTable.run_id == run_id)
            .order_by(
                RunAISummaryTable.generated_at.desc(),
                RunAISummaryTable.id.desc(),
            )
        )
        rows = self.session.execute(statement).scalars().all()
        return [self._to_domain(row) for row in rows]

    def get_active_by_run_id(
        self,
        run_id: UUID,
    ) -> RunAISummary | None:
        """Return the current non-stale RUN-type summary for one run.

        This is the convenience alias used by the singular /ai-summary endpoints.
        """
        return self.get_active_by_run_id_and_type(
            run_id=run_id,
            summary_type=RunAISummaryType.RUN,
        )

    def get_active_by_run_id_and_type(
        self,
        *,
        run_id: UUID,
        summary_type: RunAISummaryType = RunAISummaryType.RUN,
    ) -> RunAISummary | None:
        """Return the current non-stale summary for one run and type."""

        statement = (
            select(RunAISummaryTable)
            .where(
                RunAISummaryTable.run_id == run_id,
                RunAISummaryTable.summary_type == summary_type,
                RunAISummaryTable.stale.is_(False),
            )
            .order_by(
                RunAISummaryTable.generated_at.desc(),
                RunAISummaryTable.id.desc(),
            )
        )
        row = self.session.execute(statement).scalars().first()
        if row is None:
            return None

        return self._to_domain(row)

    def mark_active_stale(
        self,
        *,
        run_id: UUID,
        summary_type: RunAISummaryType = RunAISummaryType.RUN,
    ) -> list[RunAISummary]:
        """Mark every active summary for one run and type as stale."""

        statement = (
            select(RunAISummaryTable)
            .where(
                RunAISummaryTable.run_id == run_id,
                RunAISummaryTable.summary_type == summary_type,
                RunAISummaryTable.stale.is_(False),
            )
            .order_by(
                RunAISummaryTable.generated_at.desc(),
                RunAISummaryTable.id.desc(),
            )
        )
        rows = self.session.execute(statement).scalars().all()
        now = datetime.now(timezone.utc)
        for row in rows:
            row.stale = True
            row.updated_at = now

        if rows:
            self.session.flush()
            self.session.commit()

        return [self._to_domain(row) for row in rows]

    # ── State-flow helpers ───────────────────────────────────────

    def upsert_pending(
        self,
        summary: RunAISummary,
    ) -> RunAISummary:
        """Insert or replace a PENDING summary for one run.

        If an active summary already exists for this run+type it is marked
        stale before the new PENDING record is created.
        """

        self.mark_active_stale(
            run_id=summary.run_id,
            summary_type=summary.summary_type,
        )
        return self.create(summary)

    def mark_succeeded(
        self,
        *,
        summary_id: UUID,
        summary_markdown: str,
        source_fingerprint: str | None = None,
        prompt_hash: str | None = None,
    ) -> RunAISummary | None:
        """Transition one summary to SUCCEEDED with final content."""

        row = self.session.get(RunAISummaryTable, summary_id)
        if row is None:
            return None

        row.status = RunAISummaryStatus.SUCCEEDED
        row.summary_markdown = summary_markdown
        row.updated_at = datetime.now(timezone.utc)
        if source_fingerprint is not None:
            row.source_fingerprint = source_fingerprint
        if prompt_hash is not None:
            row.prompt_hash = prompt_hash
        row.error_summary = None

        self.session.flush()
        self.session.commit()
        return self._to_domain(row)

    def mark_failed(
        self,
        *,
        summary_id: UUID,
        error_summary: str,
    ) -> RunAISummary | None:
        """Transition one summary to FAILED and record the reason."""

        row = self.session.get(RunAISummaryTable, summary_id)
        if row is None:
            return None

        row.status = RunAISummaryStatus.FAILED
        row.error_summary = error_summary
        row.updated_at = datetime.now(timezone.utc)

        self.session.flush()
        self.session.commit()
        return self._to_domain(row)

    def mark_stale_if_source_changed(
        self,
        *,
        run_id: UUID,
        current_fingerprint: str,
        summary_type: RunAISummaryType = RunAISummaryType.RUN,
    ) -> list[RunAISummary]:
        """Mark active summaries stale when the source fingerprint changed."""

        statement = (
            select(RunAISummaryTable)
            .where(
                RunAISummaryTable.run_id == run_id,
                RunAISummaryTable.summary_type == summary_type,
                RunAISummaryTable.stale.is_(False),
                RunAISummaryTable.source_fingerprint != current_fingerprint,
            )
        )
        rows = self.session.execute(statement).scalars().all()
        now = datetime.now(timezone.utc)
        for row in rows:
            row.stale = True
            row.updated_at = now

        if rows:
            self.session.flush()
            self.session.commit()

        return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: RunAISummaryTable) -> RunAISummary:
        """Convert one ORM row into a domain summary."""

        return RunAISummary(
            id=row.id,
            run_id=row.run_id,
            project_id=row.project_id,
            task_id=row.task_id,
            deliverable_id=row.deliverable_id,
            summary_type=row.summary_type,
            status=row.status,
            source=row.source,
            summary_markdown=row.summary_markdown,
            source_version=row.source_version,
            source_fingerprint=row.source_fingerprint,
            source_hash=row.source_hash,
            model_provider=row.model_provider,
            model_name=row.model_name,
            prompt_hash=row.prompt_hash,
            provider_receipt_id=row.provider_receipt_id,
            generated_at=row.generated_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
            error_summary=row.error_summary,
            stale=row.stale,
        )
