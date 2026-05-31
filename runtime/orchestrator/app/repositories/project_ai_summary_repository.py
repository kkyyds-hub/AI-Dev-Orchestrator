"""Persistence helpers for project AI summary snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db_tables import ProjectAISummaryTable
from app.domain._base import utc_now
from app.domain.project_ai_summary import ProjectAISummary
from app.domain.run_ai_summary import RunAISummarySource, RunAISummaryStatus


class ProjectAISummaryRepository:
    """Encapsulate project summary persistence."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, summary: ProjectAISummary) -> ProjectAISummary:
        row = ProjectAISummaryTable(
            id=summary.id,
            project_id=summary.project_id,
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

    def get_active_by_project_id(self, project_id: UUID) -> ProjectAISummary | None:
        statement = (
            select(ProjectAISummaryTable)
            .where(
                ProjectAISummaryTable.project_id == project_id,
                ProjectAISummaryTable.stale.is_(False),
            )
            .order_by(
                ProjectAISummaryTable.generated_at.desc(),
                ProjectAISummaryTable.id.desc(),
            )
        )
        row = self.session.execute(statement).scalars().first()
        if row is None:
            return None
        return self._to_domain(row)

    def mark_active_stale(self, project_id: UUID) -> list[ProjectAISummary]:
        statement = select(ProjectAISummaryTable).where(
            ProjectAISummaryTable.project_id == project_id,
            ProjectAISummaryTable.stale.is_(False),
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
    def _to_domain(row: ProjectAISummaryTable) -> ProjectAISummary:
        fp = (row.source_fingerprint or "").strip()
        sh = (row.source_hash or "").strip()
        ph = (row.prompt_hash or "").strip()

        if not fp:
            fp = sh or sha256(
                f"legacy-project-ai-summary:{row.project_id}:{row.id}".encode()
            ).hexdigest()
        if not sh:
            sh = fp
        if not ph:
            ph = sha256(f"legacy-project-ai-summary-prompt:{fp}".encode()).hexdigest()

        now = utc_now()
        generated_at = row.generated_at or now
        created_at = row.created_at or generated_at
        updated_at = row.updated_at or created_at

        return ProjectAISummary(
            id=row.id,
            project_id=row.project_id,
            status=row.status or RunAISummaryStatus.SUCCEEDED,
            source=row.source or RunAISummarySource.RULE_FALLBACK,
            summary_markdown=row.summary_markdown or "(legacy project summary)",
            source_version=row.source_version or "legacy",
            source_fingerprint=fp,
            source_hash=sh,
            model_provider=row.model_provider,
            model_name=row.model_name,
            prompt_hash=ph,
            provider_receipt_id=row.provider_receipt_id,
            generated_at=generated_at,
            created_at=created_at,
            updated_at=updated_at,
            error_summary=row.error_summary,
            stale=bool(row.stale),
        )
