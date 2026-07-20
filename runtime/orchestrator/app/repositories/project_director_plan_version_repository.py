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
from app.domain.project_director_conversation_intelligence import FormalizationTarget
from app.domain.project_director_plan_version import (
    AgentTeamSuggestion,
    ComplexityAssessment,
    DeliverableBoundary,
    PlanPhase,
    PlanVersionStatus,
    ProjectDirectorPlanVersion,
    ProjectScopeSummary,
    ProposedTask,
    RepositoryBindingSuggestion,
    SkillBindingSuggestion,
    VerificationMechanismSuggestion,
)


class ProjectDirectorPlanVersionRepository:
    """CRUD for ProjectDirectorPlanVersion domain objects."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self, plan_version: ProjectDirectorPlanVersion
    ) -> ProjectDirectorPlanVersion:
        persisted_plan_version = self.create_no_commit(plan_version)
        self._session.commit()
        return self.get_by_id(persisted_plan_version.id) or persisted_plan_version

    def create_no_commit(
        self,
        plan_version: ProjectDirectorPlanVersion,
    ) -> ProjectDirectorPlanVersion:
        """Persist a draft inside the caller-owned transaction without committing."""

        row = self._to_row(plan_version)
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return self._to_domain(row)

    @staticmethod
    def _to_row(
        plan_version: ProjectDirectorPlanVersion,
    ) -> ProjectDirectorPlanVersionTable:
        return ProjectDirectorPlanVersionTable(
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
            project_scope_json=json.dumps(plan_version.project_scope.model_dump()),
            agent_team_suggestions_json=json.dumps(
                [item.model_dump() for item in plan_version.agent_team_suggestions]
            ),
            skill_binding_suggestions_json=json.dumps(
                [item.model_dump() for item in plan_version.skill_binding_suggestions]
            ),
            verification_mechanisms_json=json.dumps(
                [item.model_dump() for item in plan_version.verification_mechanisms]
            ),
            repository_binding_suggestions_json=json.dumps(
                [item.model_dump() for item in plan_version.repository_binding_suggestions]
            ),
            deliverable_boundaries_json=json.dumps(
                [item.model_dump() for item in plan_version.deliverable_boundaries]
            ),
            complexity_assessment_json=json.dumps(
                plan_version.complexity_assessment.model_dump()
            ),
            source=plan_version.source,
            source_detail=plan_version.source_detail,
            forbidden_actions_json=json.dumps(plan_version.forbidden_actions),
            formalization_target=(
                plan_version.formalization_target.value
                if plan_version.formalization_target is not None
                else None
            ),
            formalization_workspace_version=(
                plan_version.formalization_workspace_version
            ),
            formalization_source_message_ids_json=json.dumps(
                [str(item) for item in plan_version.formalization_source_message_ids]
            ),
            formalization_source_event_ids_json=json.dumps(
                [str(item) for item in plan_version.formalization_source_event_ids]
            ),
            confirmed_at=plan_version.confirmed_at,
            created_at=plan_version.created_at,
            updated_at=plan_version.updated_at,
        )

    def get_by_id(self, plan_version_id: UUID) -> ProjectDirectorPlanVersion | None:
        row = self._session.get(ProjectDirectorPlanVersionTable, plan_version_id)
        if row is None:
            return None
        return self._to_domain(row)

    def bind_project_no_commit(
        self,
        plan_version_id: UUID,
        project_id: UUID,
    ) -> ProjectDirectorPlanVersion:
        """Bind a plan version to a project without committing."""

        row = self._session.get(ProjectDirectorPlanVersionTable, plan_version_id)
        if row is None:
            raise ValueError(
                f"ProjectDirectorPlanVersion {plan_version_id} not found"
            )

        row.project_id = project_id
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        self._session.refresh(row)
        return self._to_domain(row)

    def list_by_status(
        self, status: PlanVersionStatus
    ) -> list[ProjectDirectorPlanVersion]:
        stmt = (
            select(ProjectDirectorPlanVersionTable)
            .where(ProjectDirectorPlanVersionTable.status == status)
            .order_by(ProjectDirectorPlanVersionTable.updated_at.desc())
        )
        rows = self._session.execute(stmt).scalars().all()
        return [self._to_domain(row) for row in rows]

    def list_recent_resumable(
        self,
        *,
        project_id: UUID | None = None,
        unbound_only: bool = False,
        limit: int = 20,
    ) -> list[ProjectDirectorPlanVersion]:
        """Return recent plan drafts that can be reviewed or continued."""

        resumable_statuses = (
            PlanVersionStatus.PENDING_CONFIRMATION,
            PlanVersionStatus.CONFIRMED,
            PlanVersionStatus.REJECTED,
        )
        stmt = (
            select(ProjectDirectorPlanVersionTable)
            .where(ProjectDirectorPlanVersionTable.status.in_(resumable_statuses))
            .order_by(ProjectDirectorPlanVersionTable.updated_at.desc())
            .limit(limit)
        )
        if unbound_only:
            stmt = stmt.where(ProjectDirectorPlanVersionTable.project_id.is_(None))
        elif project_id is not None:
            stmt = stmt.where(ProjectDirectorPlanVersionTable.project_id == project_id)

        rows = self._session.execute(stmt).scalars().all()
        return [self._to_domain(row) for row in rows]

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

    def get_by_formalization_source(
        self,
        *,
        session_id: UUID,
        target: FormalizationTarget,
        workspace_version: int,
    ) -> ProjectDirectorPlanVersion | None:
        row = self._session.execute(
            select(ProjectDirectorPlanVersionTable).where(
                ProjectDirectorPlanVersionTable.session_id == session_id,
                ProjectDirectorPlanVersionTable.formalization_target == target.value,
                ProjectDirectorPlanVersionTable.formalization_workspace_version
                == workspace_version,
            )
        ).scalar_one_or_none()
        return self._to_domain(row) if row is not None else None

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
        row.project_scope_json = json.dumps(plan_version.project_scope.model_dump())
        row.agent_team_suggestions_json = json.dumps(
            [item.model_dump() for item in plan_version.agent_team_suggestions]
        )
        row.skill_binding_suggestions_json = json.dumps(
            [item.model_dump() for item in plan_version.skill_binding_suggestions]
        )
        row.verification_mechanisms_json = json.dumps(
            [item.model_dump() for item in plan_version.verification_mechanisms]
        )
        row.repository_binding_suggestions_json = json.dumps(
            [item.model_dump() for item in plan_version.repository_binding_suggestions]
        )
        row.deliverable_boundaries_json = json.dumps(
            [item.model_dump() for item in plan_version.deliverable_boundaries]
        )
        row.complexity_assessment_json = json.dumps(
            plan_version.complexity_assessment.model_dump()
        )
        row.source = plan_version.source
        row.source_detail = plan_version.source_detail
        row.forbidden_actions_json = json.dumps(plan_version.forbidden_actions)
        row.formalization_target = (
            plan_version.formalization_target.value
            if plan_version.formalization_target is not None
            else None
        )
        row.formalization_workspace_version = plan_version.formalization_workspace_version
        row.formalization_source_message_ids_json = json.dumps(
            [str(item) for item in plan_version.formalization_source_message_ids]
        )
        row.formalization_source_event_ids_json = json.dumps(
            [str(item) for item in plan_version.formalization_source_event_ids]
        )
        row.confirmed_at = plan_version.confirmed_at
        row.updated_at = datetime.now(timezone.utc)

        self._session.commit()
        self._session.refresh(row)
        return self._to_domain(row)

    @staticmethod
    def _parse_model_list(
        raw_json: str | None,
        model_type: type[AgentTeamSuggestion]
        | type[SkillBindingSuggestion]
        | type[VerificationMechanismSuggestion]
        | type[RepositoryBindingSuggestion]
        | type[DeliverableBoundary],
    ):
        items = []
        try:
            raw = json.loads(raw_json) if raw_json else []
            if isinstance(raw, list):
                for item in raw:
                    try:
                        items.append(model_type(**item))
                    except (TypeError, ValidationError):
                        pass
        except (json.JSONDecodeError, TypeError):
            pass
        return items

    @staticmethod
    def _parse_model(raw_json: str | None, model_type, fallback):
        try:
            raw = json.loads(raw_json) if raw_json else {}
            if isinstance(raw, dict):
                return model_type(**raw)
        except (json.JSONDecodeError, TypeError, ValidationError):
            pass
        return fallback

    @staticmethod
    def _parse_uuid_list(
        raw_json: str | None,
        *,
        field_name: str,
        row_id: UUID,
    ) -> list[UUID]:
        if raw_json is None or raw_json == "":
            return []
        try:
            raw = json.loads(raw_json)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError(f"invalid_plan_version_{field_name}_json:{row_id}") from exc
        if not isinstance(raw, list):
            raise ValueError(f"invalid_plan_version_{field_name}_json:{row_id}")
        try:
            return [UUID(str(item)) for item in raw]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid_plan_version_{field_name}_json:{row_id}") from exc

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

        project_scope = ProjectDirectorPlanVersionRepository._parse_model(
            getattr(row, "project_scope_json", None),
            ProjectScopeSummary,
            ProjectScopeSummary(),
        )
        agent_team_suggestions = ProjectDirectorPlanVersionRepository._parse_model_list(
            getattr(row, "agent_team_suggestions_json", None), AgentTeamSuggestion
        )
        skill_binding_suggestions = ProjectDirectorPlanVersionRepository._parse_model_list(
            getattr(row, "skill_binding_suggestions_json", None), SkillBindingSuggestion
        )
        verification_mechanisms = ProjectDirectorPlanVersionRepository._parse_model_list(
            getattr(row, "verification_mechanisms_json", None), VerificationMechanismSuggestion
        )
        repository_binding_suggestions = ProjectDirectorPlanVersionRepository._parse_model_list(
            getattr(row, "repository_binding_suggestions_json", None), RepositoryBindingSuggestion
        )
        deliverable_boundaries = ProjectDirectorPlanVersionRepository._parse_model_list(
            getattr(row, "deliverable_boundaries_json", None), DeliverableBoundary
        )
        complexity_assessment = ProjectDirectorPlanVersionRepository._parse_model(
            getattr(row, "complexity_assessment_json", None),
            ComplexityAssessment,
            ComplexityAssessment(),
        )

        forbidden = []
        try:
            raw = json.loads(row.forbidden_actions_json) if row.forbidden_actions_json else []
            if isinstance(raw, list):
                forbidden = [str(f) for f in raw]
        except (json.JSONDecodeError, TypeError):
            pass

        formalization_target_raw = getattr(row, "formalization_target", None)
        if formalization_target_raw is None:
            formalization_target = None
        else:
            try:
                formalization_target = FormalizationTarget(formalization_target_raw)
            except ValueError as exc:
                raise ValueError(
                    f"invalid_plan_version_formalization_target:{row.id}"
                ) from exc

        formalization_source_message_ids = (
            ProjectDirectorPlanVersionRepository._parse_uuid_list(
                getattr(row, "formalization_source_message_ids_json", None),
                field_name="formalization_source_message_ids",
                row_id=row.id,
            )
        )
        formalization_source_event_ids = (
            ProjectDirectorPlanVersionRepository._parse_uuid_list(
                getattr(row, "formalization_source_event_ids_json", None),
                field_name="formalization_source_event_ids",
                row_id=row.id,
            )
        )

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
            project_scope=project_scope,
            agent_team_suggestions=agent_team_suggestions,
            skill_binding_suggestions=skill_binding_suggestions,
            verification_mechanisms=verification_mechanisms,
            repository_binding_suggestions=repository_binding_suggestions,
            deliverable_boundaries=deliverable_boundaries,
            complexity_assessment=complexity_assessment,
            source=getattr(row, "source", None) or "rule_fallback",
            source_detail=(
                getattr(row, "source_detail", None)
                or "deterministic_plan_generation"
            ),
            forbidden_actions=forbidden,
            formalization_target=formalization_target,
            formalization_workspace_version=getattr(
                row,
                "formalization_workspace_version",
                None,
            ),
            formalization_source_message_ids=formalization_source_message_ids,
            formalization_source_event_ids=formalization_source_event_ids,
            confirmed_at=ensure_utc_datetime(row.confirmed_at),
            created_at=ensure_utc_datetime(row.created_at) or datetime.now(timezone.utc),
            updated_at=ensure_utc_datetime(row.updated_at) or datetime.now(timezone.utc),
        )
