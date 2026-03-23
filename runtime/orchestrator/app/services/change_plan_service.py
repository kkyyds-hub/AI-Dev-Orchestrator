"""Business services for Day06 change-plan draft mapping and versioning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain._base import utc_now
from app.domain.change_plan import (
    ChangePlan,
    ChangePlanTargetFile,
    ChangePlanVersion,
)
from app.domain.repository_verification import (
    RepositoryVerificationTemplateReference,
)
from app.domain.deliverable import Deliverable
from app.domain.task import Task
from app.repositories.change_plan_repository import (
    ChangePlanRecord,
    ChangePlanRepository,
)
from app.repositories.deliverable_repository import DeliverableRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.services.repository_verification_service import (
    RepositoryVerificationService,
)


@dataclass(slots=True, frozen=True)
class ChangePlanVersionView:
    """One change-plan version plus its resolved related deliverables."""

    version: ChangePlanVersion
    related_deliverables: list[Deliverable]


@dataclass(slots=True, frozen=True)
class ChangePlanSummary:
    """One project-scoped change-plan summary row."""

    change_plan: ChangePlan
    task: Task
    latest_version: ChangePlanVersionView


@dataclass(slots=True, frozen=True)
class ChangePlanDetail:
    """Full change-plan detail including all immutable draft versions."""

    change_plan: ChangePlan
    task: Task
    versions: list[ChangePlanVersionView]


class ChangePlanError(ValueError):
    """Base error raised by the Day06 change-plan service."""


class ChangePlanProjectNotFoundError(ChangePlanError):
    """Raised when the requested project is missing."""


class ChangePlanTaskNotFoundError(ChangePlanError):
    """Raised when the requested task cannot be resolved inside the project."""


class ChangePlanNotFoundError(ChangePlanError):
    """Raised when the requested change plan is missing."""


class ChangePlanDeliverableNotFoundError(ChangePlanError):
    """Raised when one related deliverable cannot be resolved inside the project."""


class ChangePlanService:
    """Create, version and query structured Day06 change-plan drafts."""

    def __init__(
        self,
        *,
        change_plan_repository: ChangePlanRepository,
        project_repository: ProjectRepository,
        task_repository: TaskRepository,
        deliverable_repository: DeliverableRepository,
        repository_verification_service: RepositoryVerificationService,
    ) -> None:
        self.change_plan_repository = change_plan_repository
        self.project_repository = project_repository
        self.task_repository = task_repository
        self.deliverable_repository = deliverable_repository
        self.repository_verification_service = repository_verification_service

    def create_change_plan(
        self,
        *,
        project_id: UUID,
        task_id: UUID,
        title: str | None,
        primary_deliverable_id: UUID | None,
        related_deliverable_ids: list[UUID],
        intent_summary: str,
        source_summary: str,
        focus_terms: list[str],
        target_files: list[ChangePlanTargetFile],
        expected_actions: list[str],
        risk_notes: list[str],
        verification_commands: list[str],
        verification_template_ids: list[UUID],
        context_pack_generated_at: datetime | None = None,
    ) -> ChangePlanDetail:
        """Create one new change-plan head with its first immutable draft version."""

        task = self._resolve_task(project_id=project_id, task_id=task_id)
        deliverable_map = self._build_project_deliverable_map(project_id)
        resolved_related_deliverable_ids = self._resolve_related_deliverable_ids(
            deliverable_map=deliverable_map,
            primary_deliverable_id=primary_deliverable_id,
            related_deliverable_ids=related_deliverable_ids,
        )
        resolved_primary_deliverable_id = (
            primary_deliverable_id or resolved_related_deliverable_ids[0]
        )
        verification_templates = self._resolve_verification_templates(
            project_id=project_id,
            verification_template_ids=verification_template_ids,
        )
        timestamp = utc_now()
        change_plan = ChangePlan(
            project_id=project_id,
            task_id=task.id,
            primary_deliverable_id=resolved_primary_deliverable_id,
            title=self._resolve_title(
                explicit_title=title,
                task=task,
                primary_deliverable=deliverable_map[resolved_primary_deliverable_id],
            ),
            current_version_number=1,
            created_at=timestamp,
            updated_at=timestamp,
        )
        initial_version = ChangePlanVersion(
            change_plan_id=change_plan.id,
            version_number=1,
            intent_summary=intent_summary,
            source_summary=source_summary,
            focus_terms=focus_terms,
            target_files=target_files,
            expected_actions=expected_actions,
            risk_notes=risk_notes,
            verification_commands=verification_commands,
            verification_templates=verification_templates,
            related_deliverable_ids=resolved_related_deliverable_ids,
            context_pack_generated_at=context_pack_generated_at,
            created_at=timestamp,
        )
        record = self.change_plan_repository.create_with_initial_version(
            change_plan=change_plan,
            initial_version=initial_version,
        )
        return self._to_detail(record, task=task, deliverable_map=deliverable_map)

    def append_change_plan_version(
        self,
        *,
        change_plan_id: UUID,
        title: str | None,
        primary_deliverable_id: UUID | None,
        intent_summary: str,
        source_summary: str,
        focus_terms: list[str],
        target_files: list[ChangePlanTargetFile],
        expected_actions: list[str],
        risk_notes: list[str],
        verification_commands: list[str],
        verification_template_ids: list[UUID],
        related_deliverable_ids: list[UUID],
        context_pack_generated_at: datetime | None = None,
    ) -> ChangePlanDetail:
        """Append one new immutable draft version to an existing change plan."""

        record = self.change_plan_repository.get_record_by_id(change_plan_id)
        if record is None:
            raise ChangePlanNotFoundError(f"Change plan not found: {change_plan_id}")

        task = self._resolve_task(
            project_id=record.change_plan.project_id,
            task_id=record.change_plan.task_id,
        )
        deliverable_map = self._build_project_deliverable_map(record.change_plan.project_id)
        resolved_related_deliverable_ids = self._resolve_related_deliverable_ids(
            deliverable_map=deliverable_map,
            primary_deliverable_id=(
                primary_deliverable_id or record.change_plan.primary_deliverable_id
            ),
            related_deliverable_ids=related_deliverable_ids,
        )
        resolved_primary_deliverable_id = (
            primary_deliverable_id
            or record.change_plan.primary_deliverable_id
            or resolved_related_deliverable_ids[0]
        )
        resolved_title = self._resolve_title(
            explicit_title=title or record.change_plan.title,
            task=task,
            primary_deliverable=deliverable_map[resolved_primary_deliverable_id],
        )
        verification_templates = self._resolve_verification_templates(
            project_id=record.change_plan.project_id,
            verification_template_ids=verification_template_ids,
        )
        timestamp = utc_now()
        version = ChangePlanVersion(
            change_plan_id=record.change_plan.id,
            version_number=record.change_plan.current_version_number + 1,
            intent_summary=intent_summary,
            source_summary=source_summary,
            focus_terms=focus_terms,
            target_files=target_files,
            expected_actions=expected_actions,
            risk_notes=risk_notes,
            verification_commands=verification_commands,
            verification_templates=verification_templates,
            related_deliverable_ids=resolved_related_deliverable_ids,
            context_pack_generated_at=context_pack_generated_at,
            created_at=timestamp,
        )
        persisted_record = self.change_plan_repository.add_version(
            change_plan_id=record.change_plan.id,
            version=version,
            title=resolved_title,
            primary_deliverable_id=resolved_primary_deliverable_id,
        )
        return self._to_detail(
            persisted_record,
            task=task,
            deliverable_map=deliverable_map,
        )

    def list_change_plans(
        self,
        *,
        project_id: UUID,
        task_id: UUID | None = None,
    ) -> list[ChangePlanSummary]:
        """List project-scoped change plans, optionally filtered to one task."""

        self._ensure_project_exists(project_id)
        if task_id is not None:
            self._resolve_task(project_id=project_id, task_id=task_id)

        deliverable_map = self._build_project_deliverable_map(project_id)
        task_map = {
            task.id: task
            for task in self.task_repository.list_by_project_id(project_id)
        }
        records = self.change_plan_repository.list_records_by_project_id(
            project_id,
            task_id=task_id,
        )

        summaries: list[ChangePlanSummary] = []
        for record in records:
            task = task_map.get(record.change_plan.task_id)
            if task is None or not record.versions:
                continue
            summaries.append(
                ChangePlanSummary(
                    change_plan=record.change_plan,
                    task=task,
                    latest_version=self._to_version_view(
                        record.versions[0],
                        deliverable_map=deliverable_map,
                    ),
                )
            )

        return summaries

    def get_change_plan_detail(self, change_plan_id: UUID) -> ChangePlanDetail:
        """Return one change-plan detail together with all immutable versions."""

        record = self.change_plan_repository.get_record_by_id(change_plan_id)
        if record is None:
            raise ChangePlanNotFoundError(f"Change plan not found: {change_plan_id}")

        task = self.task_repository.get_by_id(record.change_plan.task_id)
        if task is None or task.project_id != record.change_plan.project_id:
            raise ChangePlanTaskNotFoundError(
                f"Task not found in project: {record.change_plan.task_id}"
            )

        deliverable_map = self._build_project_deliverable_map(record.change_plan.project_id)
        return self._to_detail(record, task=task, deliverable_map=deliverable_map)

    def _to_detail(
        self,
        record: ChangePlanRecord,
        *,
        task: Task,
        deliverable_map: dict[UUID, Deliverable],
    ) -> ChangePlanDetail:
        """Convert one persisted change-plan record into a detail view."""

        return ChangePlanDetail(
            change_plan=record.change_plan,
            task=task,
            versions=[
                self._to_version_view(version, deliverable_map=deliverable_map)
                for version in record.versions
            ],
        )

    @staticmethod
    def _to_version_view(
        version: ChangePlanVersion,
        *,
        deliverable_map: dict[UUID, Deliverable],
    ) -> ChangePlanVersionView:
        """Resolve deliverable IDs inside one version into deliverable summaries."""

        return ChangePlanVersionView(
            version=version,
            related_deliverables=[
                deliverable_map[deliverable_id]
                for deliverable_id in version.related_deliverable_ids
                if deliverable_id in deliverable_map
            ],
        )

    def _resolve_verification_templates(
        self,
        *,
        project_id: UUID,
        verification_template_ids: list[UUID],
    ) -> list[RepositoryVerificationTemplateReference]:
        """Resolve one ordered Day09 verification-template selection."""

        return self.repository_verification_service.resolve_template_references(
            project_id,
            verification_template_ids,
        )

    def _ensure_project_exists(self, project_id: UUID) -> None:
        """Validate that the requested project exists."""

        if self.project_repository.get_by_id(project_id) is None:
            raise ChangePlanProjectNotFoundError(f"Project not found: {project_id}")

    def _resolve_task(self, *, project_id: UUID, task_id: UUID) -> Task:
        """Resolve one project task or raise a project-scoped error."""

        self._ensure_project_exists(project_id)
        task = self.task_repository.get_by_id(task_id)
        if task is None or task.project_id != project_id:
            raise ChangePlanTaskNotFoundError(f"Task not found in project: {task_id}")

        return task

    def _build_project_deliverable_map(self, project_id: UUID) -> dict[UUID, Deliverable]:
        """Return all deliverables under one project keyed by ID."""

        self._ensure_project_exists(project_id)
        return {
            record.deliverable.id: record.deliverable
            for record in self.deliverable_repository.list_records_by_project_id(project_id)
        }

    def _resolve_related_deliverable_ids(
        self,
        *,
        deliverable_map: dict[UUID, Deliverable],
        primary_deliverable_id: UUID | None,
        related_deliverable_ids: list[UUID],
    ) -> list[UUID]:
        """Validate and normalize related deliverable IDs for one draft version."""

        normalized_ids: list[UUID] = []
        seen_ids: set[UUID] = set()

        candidate_ids = [
            *( [primary_deliverable_id] if primary_deliverable_id is not None else [] ),
            *related_deliverable_ids,
        ]
        for deliverable_id in candidate_ids:
            if deliverable_id is None or deliverable_id in seen_ids:
                continue
            if deliverable_id not in deliverable_map:
                raise ChangePlanDeliverableNotFoundError(
                    f"Deliverable not found in project: {deliverable_id}"
                )
            normalized_ids.append(deliverable_id)
            seen_ids.add(deliverable_id)

        if not normalized_ids:
            raise ChangePlanDeliverableNotFoundError(
                "Change plan must link at least one deliverable inside the project."
            )

        return normalized_ids

    @staticmethod
    def _resolve_title(
        *,
        explicit_title: str | None,
        task: Task,
        primary_deliverable: Deliverable,
    ) -> str:
        """Build one stable head title for the change-plan thread."""

        normalized_title = (explicit_title or "").strip()
        if normalized_title:
            return normalized_title

        generated_title = f"{task.title} / {primary_deliverable.title} 变更计划"
        if len(generated_title) <= 200:
            return generated_title

        return generated_title[:197].rstrip() + "..."
