"""Business services for V4 Day10 repository verification runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from uuid import UUID

from app.domain._base import utc_now
from app.domain.change_batch import ChangeBatch, ChangeBatchPlanSnapshot
from app.domain.change_plan import ChangePlanVersion
from app.domain.repository_verification import (
    RepositoryVerificationTemplate,
    RepositoryVerificationTemplateReference,
)
from app.domain.verification_run import (
    VerificationRun,
    VerificationRunCommandSource,
    VerificationRunFailureCategory,
    VerificationRunStatus,
)
from app.repositories.change_batch_repository import ChangeBatchRepository
from app.repositories.change_plan_repository import ChangePlanRecord, ChangePlanRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.repository_verification_repository import (
    RepositoryVerificationRepository,
)
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)
from app.repositories.verification_run_repository import VerificationRunRepository


@dataclass(slots=True, frozen=True)
class VerificationRunListItem:
    """One enriched Day10 verification-run row rendered in the repository run view."""

    verification_run: VerificationRun
    repository_root_path: str
    repository_display_name: str | None
    change_plan_title: str
    change_batch_title: str
    task_title: str | None


@dataclass(slots=True, frozen=True)
class VerificationRunFeed:
    """Project-scoped Day10 verification-run list returned to the UI."""

    project_id: UUID
    repository_workspace_id: UUID
    repository_root_path: str
    repository_display_name: str | None
    change_batch_id: UUID | None
    total_runs: int
    status_counts: dict[VerificationRunStatus, int]
    latest_run: VerificationRunListItem | None
    runs: list[VerificationRunListItem]


class VerificationRunError(ValueError):
    """Base error raised by the Day10 verification-run service."""


class VerificationRunProjectNotFoundError(VerificationRunError):
    """Raised when the target project cannot be resolved."""


class VerificationRunWorkspaceNotFoundError(VerificationRunError):
    """Raised when the target project has no bound repository workspace."""


class VerificationRunChangePlanNotFoundError(VerificationRunError):
    """Raised when the selected ChangePlan is missing."""


class VerificationRunChangeBatchNotFoundError(VerificationRunError):
    """Raised when the selected ChangeBatch is missing."""


class VerificationRunTemplateNotFoundError(VerificationRunError):
    """Raised when the selected repository verification template is missing."""


class VerificationRunAssociationError(VerificationRunError):
    """Raised when the requested plan / batch / template references do not align."""


class VerificationRunService:
    """Create and query structured Day10 repository verification-run records."""

    def __init__(
        self,
        *,
        verification_run_repository: VerificationRunRepository,
        project_repository: ProjectRepository,
        repository_workspace_repository: RepositoryWorkspaceRepository,
        change_plan_repository: ChangePlanRepository,
        change_batch_repository: ChangeBatchRepository,
        repository_verification_repository: RepositoryVerificationRepository,
    ) -> None:
        self.verification_run_repository = verification_run_repository
        self.project_repository = project_repository
        self.repository_workspace_repository = repository_workspace_repository
        self.change_plan_repository = change_plan_repository
        self.change_batch_repository = change_batch_repository
        self.repository_verification_repository = repository_verification_repository

    def record_verification_run(
        self,
        *,
        project_id: UUID,
        change_plan_id: UUID,
        change_batch_id: UUID,
        verification_template_id: UUID | None,
        command: str | None,
        working_directory: str | None,
        status: VerificationRunStatus,
        failure_category: VerificationRunFailureCategory | None,
        duration_seconds: float,
        output_summary: str,
    ) -> VerificationRunListItem:
        """Persist one structured Day10 verification-run result."""

        workspace = self._require_workspace(project_id)
        plan_record = self._require_change_plan(
            project_id=project_id,
            change_plan_id=change_plan_id,
        )
        change_batch = self._require_change_batch(
            project_id=project_id,
            change_batch_id=change_batch_id,
        )
        plan_snapshot = self._require_plan_snapshot(
            change_batch=change_batch,
            change_plan_id=change_plan_id,
        )

        (
            command_source,
            resolved_command,
            resolved_working_directory,
            template_snapshot,
        ) = self._resolve_command_binding(
            project_id=project_id,
            plan_record=plan_record,
            plan_snapshot=plan_snapshot,
            verification_template_id=verification_template_id,
            command=command,
            working_directory=working_directory,
            repository_root_path=Path(workspace.root_path),
        )

        finished_at = utc_now()
        started_at = finished_at - timedelta(seconds=duration_seconds)
        verification_run = VerificationRun(
            project_id=project_id,
            repository_workspace_id=workspace.id,
            change_plan_id=change_plan_id,
            change_batch_id=change_batch_id,
            verification_template_id=(
                template_snapshot.id if template_snapshot is not None else None
            ),
            verification_template_name=(
                template_snapshot.name if template_snapshot is not None else None
            ),
            verification_template_category=(
                template_snapshot.category if template_snapshot is not None else None
            ),
            command_source=command_source,
            command=resolved_command,
            working_directory=resolved_working_directory,
            status=status,
            failure_category=failure_category,
            duration_seconds=duration_seconds,
            output_summary=output_summary,
            started_at=started_at,
            finished_at=finished_at,
        )
        persisted_run = self.verification_run_repository.create(verification_run)
        return self._build_list_item(
            verification_run=persisted_run,
            repository_root_path=workspace.root_path,
            repository_display_name=workspace.display_name,
            plan_record=plan_record,
            change_batch=change_batch,
            plan_snapshot=plan_snapshot,
        )

    def list_project_runs(
        self,
        *,
        project_id: UUID,
        change_batch_id: UUID | None = None,
        limit: int = 10,
    ) -> VerificationRunFeed:
        """Return project-scoped Day10 verification runs for the repository view."""

        workspace = self._require_workspace(project_id)
        change_batch_filter = None
        if change_batch_id is not None:
            change_batch_filter = self._require_change_batch(
                project_id=project_id,
                change_batch_id=change_batch_id,
            )

        all_runs = self.verification_run_repository.list_by_project_id(
            project_id,
            change_batch_id=change_batch_id,
        )
        limited_runs = all_runs[:limit]

        plan_cache: dict[UUID, ChangePlanRecord] = {}
        batch_cache: dict[UUID, ChangeBatch] = {}
        items: list[VerificationRunListItem] = []
        for verification_run in limited_runs:
            plan_record = plan_cache.get(verification_run.change_plan_id)
            if plan_record is None:
                plan_record = self._require_change_plan(
                    project_id=project_id,
                    change_plan_id=verification_run.change_plan_id,
                )
                plan_cache[verification_run.change_plan_id] = plan_record

            change_batch = batch_cache.get(verification_run.change_batch_id)
            if change_batch is None:
                change_batch = self._require_change_batch(
                    project_id=project_id,
                    change_batch_id=verification_run.change_batch_id,
                )
                batch_cache[verification_run.change_batch_id] = change_batch

            plan_snapshot = self._require_plan_snapshot(
                change_batch=change_batch,
                change_plan_id=verification_run.change_plan_id,
            )
            items.append(
                self._build_list_item(
                    verification_run=verification_run,
                    repository_root_path=workspace.root_path,
                    repository_display_name=workspace.display_name,
                    plan_record=plan_record,
                    change_batch=change_batch,
                    plan_snapshot=plan_snapshot,
                )
            )

        status_counts = {
            status: 0 for status in VerificationRunStatus
        }
        for verification_run in all_runs:
            status_counts[verification_run.status] += 1

        return VerificationRunFeed(
            project_id=project_id,
            repository_workspace_id=workspace.id,
            repository_root_path=workspace.root_path,
            repository_display_name=workspace.display_name,
            change_batch_id=change_batch_filter.id if change_batch_filter is not None else None,
            total_runs=len(all_runs),
            status_counts=status_counts,
            latest_run=items[0] if items else None,
            runs=items,
        )

    def _require_workspace(self, project_id: UUID):
        """Ensure the target project exists and has one bound repository workspace."""

        if self.project_repository.get_by_id(project_id) is None:
            raise VerificationRunProjectNotFoundError(f"Project not found: {project_id}")

        workspace = self.repository_workspace_repository.get_by_project_id(project_id)
        if workspace is None:
            raise VerificationRunWorkspaceNotFoundError(
                f"Repository workspace not found for project: {project_id}"
            )

        return workspace

    def _require_change_plan(
        self,
        *,
        project_id: UUID,
        change_plan_id: UUID,
    ) -> ChangePlanRecord:
        """Resolve one ChangePlan and ensure it belongs to the target project."""

        plan_record = self.change_plan_repository.get_record_by_id(change_plan_id)
        if plan_record is None:
            raise VerificationRunChangePlanNotFoundError(
                f"Change plan not found: {change_plan_id}"
            )
        if plan_record.change_plan.project_id != project_id:
            raise VerificationRunAssociationError(
                "Change plan does not belong to the selected project."
            )

        return plan_record

    def _require_change_batch(
        self,
        *,
        project_id: UUID,
        change_batch_id: UUID,
    ) -> ChangeBatch:
        """Resolve one ChangeBatch and ensure it belongs to the target project."""

        change_batch = self.change_batch_repository.get_by_id(change_batch_id)
        if change_batch is None:
            raise VerificationRunChangeBatchNotFoundError(
                f"Change batch not found: {change_batch_id}"
            )
        if change_batch.project_id != project_id:
            raise VerificationRunAssociationError(
                "Change batch does not belong to the selected project."
            )

        return change_batch

    @staticmethod
    def _require_plan_snapshot(
        *,
        change_batch: ChangeBatch,
        change_plan_id: UUID,
    ) -> ChangeBatchPlanSnapshot:
        """Resolve one ChangePlan snapshot embedded inside a ChangeBatch."""

        for plan_snapshot in change_batch.plan_snapshots:
            if plan_snapshot.change_plan_id == change_plan_id:
                return plan_snapshot

        raise VerificationRunAssociationError(
            "Selected change plan is not part of the selected change batch."
        )

    def _resolve_command_binding(
        self,
        *,
        project_id: UUID,
        plan_record: ChangePlanRecord,
        plan_snapshot: ChangeBatchPlanSnapshot,
        verification_template_id: UUID | None,
        command: str | None,
        working_directory: str | None,
        repository_root_path: Path,
    ) -> tuple[
        VerificationRunCommandSource,
        str,
        str,
        RepositoryVerificationTemplateReference | None,
    ]:
        """Resolve one command binding from the selected plan / batch context."""

        latest_version = self._get_latest_version(plan_record)
        if verification_template_id is not None:
            template_snapshot = self._resolve_template_snapshot(
                verification_template_id=verification_template_id,
                plan_snapshot=plan_snapshot,
                latest_version=latest_version,
            )
            template_map = self.repository_verification_repository.get_by_ids_for_project(
                project_id,
                [verification_template_id],
            )
            template = template_map.get(verification_template_id)
            if template is None:
                raise VerificationRunTemplateNotFoundError(
                    f"Repository verification template not found: {verification_template_id}"
                )

            validated_working_directory = self._validate_working_directory(
                repository_root_path=repository_root_path,
                working_directory=template_snapshot.working_directory,
            )
            return (
                VerificationRunCommandSource.TEMPLATE,
                template_snapshot.command,
                validated_working_directory,
                self._merge_template_snapshot(
                    template_snapshot=template_snapshot,
                    template=template,
                ),
            )

        normalized_command = (command or "").strip()
        if not normalized_command:
            raise VerificationRunAssociationError(
                "Manual verification runs require one explicit command."
            )

        allowed_commands = {
            item for item in plan_snapshot.verification_commands if item.strip()
        } | {
            item for item in latest_version.verification_commands if item.strip()
        }
        if normalized_command not in allowed_commands:
            raise VerificationRunAssociationError(
                "Manual verification command is not linked to the selected change plan or batch."
            )

        normalized_working_directory = self._validate_working_directory(
            repository_root_path=repository_root_path,
            working_directory=working_directory or ".",
        )
        return (
            VerificationRunCommandSource.MANUAL,
            normalized_command,
            normalized_working_directory,
            None,
        )

    @staticmethod
    def _get_latest_version(plan_record: ChangePlanRecord) -> ChangePlanVersion:
        """Return the newest immutable version from one ChangePlan record."""

        if not plan_record.versions:
            raise VerificationRunAssociationError("Selected change plan has no persisted version.")

        return plan_record.versions[-1]

    @staticmethod
    def _resolve_template_snapshot(
        *,
        verification_template_id: UUID,
        plan_snapshot: ChangeBatchPlanSnapshot,
        latest_version: ChangePlanVersion,
    ) -> RepositoryVerificationTemplateReference:
        """Resolve one template snapshot that already belongs to this plan / batch."""

        for template_reference in plan_snapshot.verification_templates:
            if template_reference.id == verification_template_id:
                return template_reference

        for template_reference in latest_version.verification_templates:
            if template_reference.id == verification_template_id:
                return template_reference

        raise VerificationRunAssociationError(
            "Verification template is not linked to the selected change plan or change batch."
        )

    @staticmethod
    def _merge_template_snapshot(
        *,
        template_snapshot: RepositoryVerificationTemplateReference,
        template: RepositoryVerificationTemplate,
    ) -> RepositoryVerificationTemplateReference:
        """Prefer current persisted template metadata while preserving command snapshot fields."""

        return RepositoryVerificationTemplateReference(
            id=template.id,
            category=template_snapshot.category,
            name=template_snapshot.name,
            command=template_snapshot.command,
            working_directory=template_snapshot.working_directory,
            timeout_seconds=template_snapshot.timeout_seconds,
            enabled_by_default=template.enabled_by_default,
            description=template.description,
        )

    @staticmethod
    def _validate_working_directory(
        *,
        repository_root_path: Path,
        working_directory: str,
    ) -> str:
        """Ensure the selected working directory stays inside the bound repository."""

        normalized_working_directory = working_directory.replace("\\", "/").strip() or "."
        if normalized_working_directory == ".":
            target_path = repository_root_path
        else:
            target_path = (
                repository_root_path / normalized_working_directory
            ).resolve(strict=False)

        repository_root = repository_root_path.resolve(strict=True)
        try:
            target_path.relative_to(repository_root)
        except ValueError as exc:
            raise VerificationRunAssociationError(
                "Verification-run working_directory must stay inside the repository root."
            ) from exc

        if not target_path.exists() or not target_path.is_dir():
            raise VerificationRunAssociationError(
                f"Verification-run working_directory does not exist: {normalized_working_directory}"
            )

        return normalized_working_directory

    @staticmethod
    def _build_list_item(
        *,
        verification_run: VerificationRun,
        repository_root_path: str,
        repository_display_name: str | None,
        plan_record: ChangePlanRecord,
        change_batch: ChangeBatch,
        plan_snapshot: ChangeBatchPlanSnapshot,
    ) -> VerificationRunListItem:
        """Build one repository-view row from the persisted Day10 record."""

        return VerificationRunListItem(
            verification_run=verification_run,
            repository_root_path=repository_root_path,
            repository_display_name=repository_display_name,
            change_plan_title=plan_record.change_plan.title,
            change_batch_title=change_batch.title,
            task_title=plan_snapshot.task_title,
        )
