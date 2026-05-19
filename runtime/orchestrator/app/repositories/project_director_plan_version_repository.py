"""Repository for AI Project Director Plan Versions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db_tables import ProjectDirectorPlanVersionTable
from app.domain._base import ensure_utc_datetime
from app.domain.project_director_plan_version import (
    PlanPhase,
    PlanVersionStatus,
    ProjectDirectorPlanVersion,
    ProposedTask,
)


class ProjectDirectorPlanVersionRepository:
    """CRUD for ProjectDirectorPlanVersion domain objects."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self, plan_version: ProjectDirectorPlanVersion
    ) -> ProjectDirectorPlanVersion:
        row = ProjectDirectorPlanVersionTable(
            id=plan_version.id,
            session_id=plan_version.session_id,
            project_id=plan_version.project_id,
            version_no=plan_version.version_no,
            status=plan_version.status,
            plan_summary=plan_version.plan_summary,
            phases_json=json.dumps(
                [p.model_dump() for p in plan_version.phases]
            ),
            proposed_tasks_json=json.dumps(
                [t.model_dump() for t in plan_version.proposed_tasks]
            ),
            acceptance_criteria_json=json.dumps(plan_version.acceptance_criteria),
            risks_json=json.dumps(plan_version.risks),
            forbidden_actions_json=json.dumps(plan_version.forbidden_actions),
            confirmed_at=plan_version.confirmed_at,
            created_at=plan_version.created_at,
            updated_at=plan_version.updated_at,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return self._to_domain(row)

    def get_by_id(self, plan_version_id: UUID) -> ProjectDirectorPlanVersion | None:
        row = self._session.get(ProjectDirectorPlanVersionTable, plan_version_id)
        if row is None:
            return None
        return self._to_domain(row)

    def list_by_session_id(
        self, session_id: UUID
    ) -> list[ProjectDirectorPlanVersion]:
        stmt = (
            select(ProjectDirectorPlanVersionTable)
            .where(ProjectDirectorPlanVersionTable.session_id == session_id)
            .order_by(ProjectDirectorPlanVersionTable.version_no.desc())
        )
        rows = self._session.execute(stmt).scalars().all()
        return [self._to_domain(row) for row in rows]

    def get_active_confirmed(
        self, session_id: UUID
    ) -> ProjectDirectorPlanVersion | None:
        stmt = (
            select(ProjectDirectorPlanVersionTable)
            .where(
                ProjectDirectorPlanVersionTable.session_id == session_id,
                ProjectDirectorPlanVersionTable.status
                == PlanVersionStatus.CONFIRMED,
            )
        )
        row = self._session.execute(stmt).scalars().first()
        if row is None:
            return None
        return self._to_domain(row)

    def get_next_version_no(self, session_id: UUID) -> int:
        stmt = (
            select(ProjectDirectorPlanVersionTable.version_no)
            .where(ProjectDirectorPlanVersionTable.session_id == session_id)
            .order_by(ProjectDirectorPlanVersionTable.version_no.desc())
            .limit(1)
        )
        result = self._session.execute(stmt).scalar_one_or_none()
        return (result or 0) + 1

    def update(
        self, plan_version: ProjectDirectorPlanVersion
    ) -> ProjectDirectorPlanVersion:
        row = self._session.get(ProjectDirectorPlanVersionTable, plan_version.id)
        if row is None:
            raise ValueError(
                f"ProjectDirectorPlanVersion {plan_version.id} not found"
            )

        row.project_id = plan_version.project_id
        row.version_no = plan_version.version_no
        row.status = plan_version.status
        row.plan_summary = plan_version.plan_summary
        row.phases_json = json.dumps(
            [p.model_dump() for p in plan_version.phases]
        )
        row.proposed_tasks_json = json.dumps(
            [t.model_dump() for t in plan_version.proposed_tasks]
        )
        row.acceptance_criteria_json = json.dumps(plan_version.acceptance_criteria)
        row.risks_json = json.dumps(plan_version.risks)
        row.forbidden_actions_json = json.dumps(plan_version.forbidden_actions)
        row.confirmed_at = plan_version.confirmed_at
        row.updated_at = datetime.now(timezone.utc)

        self._session.commit()
        self._session.refresh(row)
        return self._to_domain(row)

    @staticmethod
    def _to_domain(
        row: ProjectDirectorPlanVersionTable,
    ) -> ProjectDirectorPlanVersion:
        phases = []
        try:
            raw = json.loads(row.phases_json) if row.phases_json else []
            if isinstance(raw, list):
                for item in raw:
                    try:
                        phases.append(PlanPhase(**item))
                    except ValidationError:
                        pass
        except (json.JSONDecodeError, TypeError):
            pass

        tasks = []
        try:
            raw = json.loads(row.proposed_tasks_json) if row.proposed_tasks_json else []
            if isinstance(raw, list):
                for item in raw:
                    try:
                        tasks.append(ProposedTask(**item))
                    except ValidationError:
                        pass
        except (json.JSONDecodeError, TypeError):
            pass

        criteria = []
        try:
            raw = json.loads(row.acceptance_criteria_json) if row.acceptance_criteria_json else []
            if isinstance(raw, list):
                criteria = [str(c) for c in raw]
        except (json.JSONDecodeError, TypeError):
            pass

        risks = []
        try:
            raw = json.loads(row.risks_json) if row.risks_json else []
            if isinstance(raw, list):
                risks = [str(r) for r in raw]
        except (json.JSONDecodeError, TypeError):
            pass

        forbidden = []
        try:
            raw = json.loads(row.forbidden_actions_json) if row.forbidden_actions_json else []
            if isinstance(raw, list):
                forbidden = [str(f) for f in raw]
        except (json.JSONDecodeError, TypeError):
            pass

        return ProjectDirectorPlanVersion(
            id=row.id,
            session_id=row.session_id,
            project_id=row.project_id,
            version_no=row.version_no,
            status=row.status,
            plan_summary=row.plan_summary,
            phases=phases,
            proposed_tasks=tasks,
            acceptance_criteria=criteria,
            risks=risks,
            forbidden_actions=forbidden,
            confirmed_at=ensure_utc_datetime(row.confirmed_at),
            created_at=ensure_utc_datetime(row.created_at) or datetime.now(timezone.utc),
            updated_at=ensure_utc_datetime(row.updated_at) or datetime.now(timezone.utc),
        )
