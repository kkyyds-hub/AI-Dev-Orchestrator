"""Business services for the V3 Day09/Day11 deliverable repository."""

from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
import json
from uuid import UUID

from app.domain._base import utc_now
from app.domain.deliverable import (
    Deliverable,
    DeliverableContentFormat,
    DeliverableType,
    DeliverableVersion,
)
from app.domain.project import ProjectStage
from app.domain.project_role import ProjectRoleCode
from app.repositories.deliverable_repository import (
    DeliverableRecord,
    DeliverableRepository,
)
from app.repositories.project_repository import ProjectRepository
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository


@dataclass(slots=True, frozen=True)
class DeliverableSummary:
    """One deliverable head summarized with its latest immutable version."""

    deliverable: Deliverable
    latest_version: DeliverableVersion
    total_versions: int


@dataclass(slots=True, frozen=True)
class DeliverableDetail:
    """Full deliverable detail used by the Day09 center page."""

    deliverable: Deliverable
    versions: list[DeliverableVersion]


@dataclass(slots=True, frozen=True)
class ProjectDeliverableSnapshot:
    """Project-scoped deliverable repository view."""

    project_id: UUID
    total_deliverables: int
    total_versions: int
    generated_at: datetime
    deliverables: list[DeliverableSummary]


@dataclass(slots=True, frozen=True)
class TaskRelatedDeliverable:
    """One deliverable version associated with a task or one of its runs."""

    deliverable: Deliverable
    version: DeliverableVersion


@dataclass(slots=True, frozen=True)
class DeliverableTimelineEntry:
    """One immutable deliverable-version event surfaced on the Day11 timeline."""

    deliverable: Deliverable
    version: DeliverableVersion


@dataclass(slots=True, frozen=True)
class DeliverableDiffLine:
    """One normalized line-level diff row between two deliverable versions."""

    kind: str
    content: str
    base_line_number: int | None
    target_line_number: int | None


@dataclass(slots=True, frozen=True)
class DeliverableVersionDiff:
    """Minimal version-comparison payload used by the Day11 diff panel."""

    deliverable: Deliverable
    base_version: DeliverableVersion
    target_version: DeliverableVersion
    format_changed: bool
    added_line_count: int
    removed_line_count: int
    unchanged_line_count: int
    changed_block_count: int
    diff_lines: list[DeliverableDiffLine]


class DeliverableService:
    """Handle creation, snapshot submission and scoped deliverable queries."""

    def __init__(
        self,
        *,
        deliverable_repository: DeliverableRepository,
        project_repository: ProjectRepository,
        task_repository: TaskRepository,
        run_repository: RunRepository,
    ) -> None:
        self.deliverable_repository = deliverable_repository
        self.project_repository = project_repository
        self.task_repository = task_repository
        self.run_repository = run_repository

    def create_deliverable(
        self,
        *,
        project_id: UUID,
        type: DeliverableType,
        title: str,
        stage: ProjectStage,
        created_by_role_code: ProjectRoleCode,
        summary: str,
        content: str,
        content_format: DeliverableContentFormat = DeliverableContentFormat.MARKDOWN,
        source_task_id: UUID | None = None,
        source_run_id: UUID | None = None,
    ) -> DeliverableDetail:
        """Create one new deliverable with its initial immutable snapshot."""

        if self.project_repository.get_by_id(project_id) is None:
            raise ValueError(f"Project not found: {project_id}")

        resolved_task_id, resolved_run_id = self._resolve_source_links(
            project_id=project_id,
            source_task_id=source_task_id,
            source_run_id=source_run_id,
        )
        timestamp = utc_now()
        deliverable = Deliverable(
            project_id=project_id,
            type=type,
            title=title,
            stage=stage,
            created_by_role_code=created_by_role_code,
            current_version_number=1,
            created_at=timestamp,
            updated_at=timestamp,
        )
        initial_version = DeliverableVersion(
            deliverable_id=deliverable.id,
            version_number=1,
            author_role_code=created_by_role_code,
            summary=summary,
            content=content,
            content_format=content_format,
            source_task_id=resolved_task_id,
            source_run_id=resolved_run_id,
            created_at=timestamp,
        )
        record = self.deliverable_repository.create_with_initial_version(
            deliverable=deliverable,
            initial_version=initial_version,
        )
        return self._to_detail(record)

    def submit_deliverable_version(
        self,
        *,
        deliverable_id: UUID,
        author_role_code: ProjectRoleCode,
        summary: str,
        content: str,
        content_format: DeliverableContentFormat = DeliverableContentFormat.MARKDOWN,
        source_task_id: UUID | None = None,
        source_run_id: UUID | None = None,
    ) -> DeliverableDetail:
        """Append one new immutable version to an existing deliverable."""

        record = self.deliverable_repository.get_record_by_id(deliverable_id)
        if record is None:
            raise ValueError(f"Deliverable not found: {deliverable_id}")

        resolved_task_id, resolved_run_id = self._resolve_source_links(
            project_id=record.deliverable.project_id,
            source_task_id=source_task_id,
            source_run_id=source_run_id,
        )
        next_version_number = record.deliverable.current_version_number + 1
        version = DeliverableVersion(
            deliverable_id=deliverable_id,
            version_number=next_version_number,
            author_role_code=author_role_code,
            summary=summary,
            content=content,
            content_format=content_format,
            source_task_id=resolved_task_id,
            source_run_id=resolved_run_id,
            created_at=utc_now(),
        )
        updated_record = self.deliverable_repository.add_version(
            deliverable_id=deliverable_id,
            version=version,
        )
        return self._to_detail(updated_record)

    def get_deliverable_detail(self, deliverable_id: UUID) -> DeliverableDetail | None:
        """Return one deliverable plus all submitted versions."""

        record = self.deliverable_repository.get_record_by_id(deliverable_id)
        if record is None:
            return None

        return self._to_detail(record)

    def get_project_deliverable_snapshot(
        self,
        project_id: UUID,
    ) -> ProjectDeliverableSnapshot | None:
        """Return the Day09 project-scoped deliverable repository view."""

        if self.project_repository.get_by_id(project_id) is None:
            return None

        records = self.deliverable_repository.list_records_by_project_id(project_id)
        deliverables = [self._to_summary(record) for record in records if record.versions]
        return ProjectDeliverableSnapshot(
            project_id=project_id,
            total_deliverables=len(deliverables),
            total_versions=sum(item.total_versions for item in deliverables),
            generated_at=utc_now(),
            deliverables=deliverables,
        )

    def list_related_deliverables_by_task(
        self,
        task_id: UUID,
    ) -> list[TaskRelatedDeliverable] | None:
        """Return deliverable versions linked to one task or its runs."""

        task = self.task_repository.get_by_id(task_id)
        if task is None:
            return None

        if task.project_id is None:
            return []

        run_ids = {run.id for run in self.run_repository.list_by_task_id(task_id)}
        records = self.deliverable_repository.list_records_by_project_id(task.project_id)
        related_items: list[TaskRelatedDeliverable] = []

        for record in records:
            for version in record.versions:
                if version.source_task_id == task_id or (
                    version.source_run_id is not None and version.source_run_id in run_ids
                ):
                    related_items.append(
                        TaskRelatedDeliverable(
                            deliverable=record.deliverable,
                            version=version,
                        )
                    )

        related_items.sort(
            key=lambda item: (item.version.created_at, item.version.version_number),
            reverse=True,
        )
        return related_items

    def list_project_timeline_entries(
        self,
        project_id: UUID,
    ) -> list[DeliverableTimelineEntry] | None:
        """Flatten all deliverable-version submissions under one project."""

        if self.project_repository.get_by_id(project_id) is None:
            return None

        records = self.deliverable_repository.list_records_by_project_id(project_id)
        timeline_entries: list[DeliverableTimelineEntry] = []
        for record in records:
            for version in record.versions:
                timeline_entries.append(
                    DeliverableTimelineEntry(
                        deliverable=record.deliverable,
                        version=version,
                    )
                )

        timeline_entries.sort(
            key=lambda item: (item.version.created_at, item.version.version_number),
            reverse=True,
        )
        return timeline_entries

    def compare_deliverable_versions(
        self,
        *,
        deliverable_id: UUID,
        base_version_number: int,
        target_version_number: int,
    ) -> DeliverableVersionDiff | None:
        """Return a minimal line-level comparison between two saved versions."""

        record = self.deliverable_repository.get_record_by_id(deliverable_id)
        if record is None:
            return None

        version_by_number = {
            version.version_number: version for version in record.versions
        }
        base_version = version_by_number.get(base_version_number)
        if base_version is None:
            raise ValueError(
                f"Deliverable version not found: v{base_version_number}"
            )

        target_version = version_by_number.get(target_version_number)
        if target_version is None:
            raise ValueError(
                f"Deliverable version not found: v{target_version_number}"
            )

        (
            diff_lines,
            added_line_count,
            removed_line_count,
            unchanged_line_count,
            changed_block_count,
        ) = self._build_diff_lines(
            base_lines=self._normalize_content_lines(base_version),
            target_lines=self._normalize_content_lines(target_version),
        )

        return DeliverableVersionDiff(
            deliverable=record.deliverable,
            base_version=base_version,
            target_version=target_version,
            format_changed=base_version.content_format != target_version.content_format,
            added_line_count=added_line_count,
            removed_line_count=removed_line_count,
            unchanged_line_count=unchanged_line_count,
            changed_block_count=changed_block_count,
            diff_lines=diff_lines,
        )

    def _resolve_source_links(
        self,
        *,
        project_id: UUID,
        source_task_id: UUID | None,
        source_run_id: UUID | None,
    ) -> tuple[UUID | None, UUID | None]:
        """Validate linked task/run references and normalize implied task IDs."""

        task_id = source_task_id
        run_id = source_run_id

        task = None
        if task_id is not None:
            task = self.task_repository.get_by_id(task_id)
            if task is None:
                raise ValueError(f"Task not found: {task_id}")
            if task.project_id != project_id:
                raise ValueError("Linked task must belong to the same project.")

        if run_id is not None:
            run = self.run_repository.get_by_id(run_id)
            if run is None:
                raise ValueError(f"Run not found: {run_id}")

            run_task = self.task_repository.get_by_id(run.task_id)
            if run_task is None:
                raise ValueError(f"Run task not found: {run.task_id}")
            if run_task.project_id != project_id:
                raise ValueError("Linked run must belong to the same project.")

            if task_id is None:
                task = run_task
                task_id = run.task_id
            elif run.task_id != task_id:
                raise ValueError("Linked run must belong to the linked task.")

        if task is not None and task.project_id != project_id:
            raise ValueError("Linked task must belong to the same project.")

        return task_id, run_id

    @staticmethod
    def _to_summary(record: DeliverableRecord) -> DeliverableSummary:
        """Build one summary card from a persisted deliverable record."""

        latest_version = record.versions[0]
        return DeliverableSummary(
            deliverable=record.deliverable,
            latest_version=latest_version,
            total_versions=len(record.versions),
        )

    @staticmethod
    def _to_detail(record: DeliverableRecord) -> DeliverableDetail:
        """Convert one repository record into a service detail object."""

        return DeliverableDetail(
            deliverable=record.deliverable,
            versions=list(record.versions),
        )

    @staticmethod
    def _normalize_content_lines(version: DeliverableVersion) -> list[str]:
        """Normalize one deliverable snapshot into comparable lines."""

        content = version.content.replace("\r\n", "\n").replace("\r", "\n")
        if version.content_format == DeliverableContentFormat.JSON:
            try:
                content = json.dumps(
                    json.loads(content),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            except json.JSONDecodeError:
                pass

        return content.split("\n")

    @staticmethod
    def _build_diff_lines(
        *,
        base_lines: list[str],
        target_lines: list[str],
    ) -> tuple[list[DeliverableDiffLine], int, int, int, int]:
        """Build a minimal line-level diff using a sequence matcher."""

        matcher = SequenceMatcher(a=base_lines, b=target_lines)
        diff_lines: list[DeliverableDiffLine] = []
        added_line_count = 0
        removed_line_count = 0
        unchanged_line_count = 0
        changed_block_count = 0

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for offset, line in enumerate(base_lines[i1:i2], start=0):
                    diff_lines.append(
                        DeliverableDiffLine(
                            kind="context",
                            content=line,
                            base_line_number=i1 + offset + 1,
                            target_line_number=j1 + offset + 1,
                        )
                    )
                    unchanged_line_count += 1
                continue

            if tag == "replace":
                changed_block_count += 1
            elif tag in {"insert", "delete"}:
                changed_block_count += 1

            if tag in {"replace", "delete"}:
                for offset, line in enumerate(base_lines[i1:i2], start=0):
                    diff_lines.append(
                        DeliverableDiffLine(
                            kind="removed",
                            content=line,
                            base_line_number=i1 + offset + 1,
                            target_line_number=None,
                        )
                    )
                    removed_line_count += 1

            if tag in {"replace", "insert"}:
                for offset, line in enumerate(target_lines[j1:j2], start=0):
                    diff_lines.append(
                        DeliverableDiffLine(
                            kind="added",
                            content=line,
                            base_line_number=None,
                            target_line_number=j1 + offset + 1,
                        )
                    )
                    added_line_count += 1

        return (
            diff_lines,
            added_line_count,
            removed_line_count,
            unchanged_line_count,
            changed_block_count,
        )
