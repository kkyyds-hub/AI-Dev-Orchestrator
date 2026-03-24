"""Business services for V4 Day11 repository diff summaries and evidence packages."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path, PurePosixPath
import subprocess
from uuid import NAMESPACE_URL, UUID, uuid5

from app.domain._base import utc_now
from app.domain.change_batch import ChangeBatch
from app.domain.change_evidence import (
    ChangeEvidenceApprovalReference,
    ChangeEvidenceDeliverableReference,
    ChangeEvidencePackage,
    ChangeEvidencePlanItem,
    ChangeEvidenceReverseLookup,
    ChangeEvidenceSnapshot,
    ChangeEvidenceSnapshotKind,
    ChangeEvidenceVerificationRunItem,
    ChangeEvidenceVerificationSummary,
    DiffComparisonMode,
    DiffFileChange,
    DiffFileChangeKind,
    DiffSummary,
)
from app.repositories.approval_repository import ApprovalRecord, ApprovalRepository
from app.repositories.change_batch_repository import ChangeBatchRepository
from app.repositories.deliverable_repository import DeliverableRecord, DeliverableRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)
from app.repositories.verification_run_repository import VerificationRunRepository


GIT_COMMAND_TIMEOUT_SECONDS = 10
MAX_KEY_FILES = 8
MAX_DELIVERABLE_REFERENCES = 6
MAX_APPROVAL_REFERENCES = 6
MAX_VERIFICATION_SAMPLE_RUNS = 8
MAX_SNAPSHOTS = 12


class DiffSummaryError(ValueError):
    """Base error raised by the Day11 diff-summary service."""


class DiffSummaryProjectNotFoundError(DiffSummaryError):
    """Raised when one project cannot be resolved."""


class DiffSummaryWorkspaceNotFoundError(DiffSummaryError):
    """Raised when one project has no bound repository workspace."""


class DiffSummaryDeliverableNotFoundError(DiffSummaryError):
    """Raised when the requested deliverable cannot be resolved."""


class DiffSummaryApprovalNotFoundError(DiffSummaryError):
    """Raised when the requested approval cannot be resolved."""


class DiffSummaryChangeBatchNotFoundError(DiffSummaryError):
    """Raised when the requested change batch cannot be resolved."""


@dataclass(slots=True)
class _TargetFileContext:
    """Aggregated ChangeBatch context attached to one repository file path."""

    task_ids: list[UUID] = field(default_factory=list)
    change_plan_ids: list[UUID] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class _GitComparisonState:
    """Resolved Git refs and dirty-file preview used by the Day11 diff builder."""

    baseline_ref: str
    baseline_label: str
    target_label: str
    dirty_status_by_path: dict[str, str]
    notes: list[str]


class DiffSummaryService:
    """Assemble Day11 file-level diff summaries and acceptance evidence packages."""

    def __init__(
        self,
        *,
        project_repository: ProjectRepository,
        repository_workspace_repository: RepositoryWorkspaceRepository,
        change_batch_repository: ChangeBatchRepository,
        deliverable_repository: DeliverableRepository,
        approval_repository: ApprovalRepository,
        verification_run_repository: VerificationRunRepository,
    ) -> None:
        self.project_repository = project_repository
        self.repository_workspace_repository = repository_workspace_repository
        self.change_batch_repository = change_batch_repository
        self.deliverable_repository = deliverable_repository
        self.approval_repository = approval_repository
        self.verification_run_repository = verification_run_repository

    def get_project_change_evidence(
        self,
        project_id: UUID,
        *,
        change_batch_id: UUID | None = None,
    ) -> ChangeEvidencePackage:
        """Return one project-scoped Day11 evidence package."""

        self._ensure_project_exists(project_id)
        selected_change_batch = self._resolve_change_batch(
            project_id=project_id,
            change_batch_id=change_batch_id,
            deliverable_id=None,
        )
        return self._build_change_evidence_package(
            project_id=project_id,
            selected_change_batch=selected_change_batch,
            selected_deliverable_id=None,
            selected_approval_id=None,
        )

    def get_deliverable_change_evidence(
        self,
        deliverable_id: UUID,
    ) -> ChangeEvidencePackage:
        """Return one deliverable-scoped Day11 evidence package."""

        deliverable_record = self.deliverable_repository.get_record_by_id(deliverable_id)
        if deliverable_record is None:
            raise DiffSummaryDeliverableNotFoundError(
                f"Deliverable not found: {deliverable_id}"
            )

        project_id = deliverable_record.deliverable.project_id
        self._ensure_project_exists(project_id)
        selected_change_batch = self._resolve_change_batch(
            project_id=project_id,
            change_batch_id=None,
            deliverable_id=deliverable_id,
        )
        return self._build_change_evidence_package(
            project_id=project_id,
            selected_change_batch=selected_change_batch,
            selected_deliverable_id=deliverable_id,
            selected_approval_id=None,
        )

    def get_approval_change_evidence(
        self,
        approval_id: UUID,
    ) -> ChangeEvidencePackage:
        """Return one approval-scoped Day11 evidence package."""

        approval_record = self.approval_repository.get_record_by_id(approval_id)
        if approval_record is None:
            raise DiffSummaryApprovalNotFoundError(f"Approval not found: {approval_id}")

        project_id = approval_record.approval.project_id
        deliverable_id = approval_record.approval.deliverable_id
        self._ensure_project_exists(project_id)
        selected_change_batch = self._resolve_change_batch(
            project_id=project_id,
            change_batch_id=None,
            deliverable_id=deliverable_id,
        )
        return self._build_change_evidence_package(
            project_id=project_id,
            selected_change_batch=selected_change_batch,
            selected_deliverable_id=deliverable_id,
            selected_approval_id=approval_id,
        )

    def _build_change_evidence_package(
        self,
        *,
        project_id: UUID,
        selected_change_batch: ChangeBatch | None,
        selected_deliverable_id: UUID | None,
        selected_approval_id: UUID | None,
    ) -> ChangeEvidencePackage:
        """Assemble one Day11 evidence package from project, repo and approval context."""

        workspace = self._require_workspace(project_id)
        deliverable_records = self.deliverable_repository.list_records_by_project_id(project_id)
        deliverable_record_map = {
            record.deliverable.id: record for record in deliverable_records
        }

        diff_summary = self._build_diff_summary(
            project_id=project_id,
            repository_workspace_id=workspace.id,
            repository_root_path=workspace.root_path,
            baseline_branch=workspace.default_base_branch,
            selected_change_batch=selected_change_batch,
        )
        plan_items = self._build_plan_items(selected_change_batch)
        deliverables = self._build_deliverable_references(
            deliverable_record_map=deliverable_record_map,
            selected_change_batch=selected_change_batch,
            selected_deliverable_id=selected_deliverable_id,
        )
        approvals = self._build_approval_references(
            project_id=project_id,
            deliverables=deliverables,
            selected_deliverable_id=selected_deliverable_id,
            selected_approval_id=selected_approval_id,
        )
        verification_summary = self._build_verification_summary(
            project_id=project_id,
            selected_change_batch=selected_change_batch,
        )
        snapshots = self._build_snapshots(
            selected_change_batch=selected_change_batch,
            deliverables=deliverables,
            approvals=approvals,
            verification_summary=verification_summary,
        )
        reverse_lookup = ChangeEvidenceReverseLookup(
            project_id=project_id,
            change_batch_id=selected_change_batch.id if selected_change_batch else None,
            deliverable_ids=[item.deliverable_id for item in deliverables],
            approval_ids=[item.approval_id for item in approvals],
        )
        package_key = self._build_package_key(
            project_id=project_id,
            selected_change_batch=selected_change_batch,
            selected_deliverable_id=selected_deliverable_id,
            selected_approval_id=selected_approval_id,
            deliverables=deliverables,
            approvals=approvals,
            diff_summary=diff_summary,
            verification_summary=verification_summary,
        )
        summary = self._build_package_summary(
            selected_change_batch=selected_change_batch,
            diff_summary=diff_summary,
            plan_items=plan_items,
            verification_summary=verification_summary,
            deliverables=deliverables,
            approvals=approvals,
        )

        return ChangeEvidencePackage(
            project_id=project_id,
            repository_workspace_id=workspace.id,
            repository_root_path=workspace.root_path,
            package_key=package_key,
            summary=summary,
            selected_change_batch_id=selected_change_batch.id if selected_change_batch else None,
            selected_change_batch_title=selected_change_batch.title
            if selected_change_batch
            else None,
            selected_deliverable_id=selected_deliverable_id,
            selected_approval_id=selected_approval_id,
            generated_at=utc_now(),
            diff_summary=diff_summary,
            plan_items=plan_items,
            verification_summary=verification_summary,
            deliverables=deliverables,
            approvals=approvals,
            snapshots=snapshots,
            reverse_lookup=reverse_lookup,
        )

    def _build_diff_summary(
        self,
        *,
        project_id: UUID,
        repository_workspace_id: UUID,
        repository_root_path: str,
        baseline_branch: str,
        selected_change_batch: ChangeBatch | None,
    ) -> DiffSummary:
        """Build one file-level Day11 diff summary from the bound Git repository."""

        repository_root = Path(repository_root_path)
        target_file_context_map = self._build_target_file_context_map(selected_change_batch)

        try:
            git_state = self._resolve_git_comparison_state(
                repository_root,
                baseline_branch=baseline_branch,
            )
            name_status_map = self._read_git_name_status(
                repository_root,
                baseline_ref=git_state.baseline_ref,
            )
            numstat_map = self._read_git_numstat(
                repository_root,
                baseline_ref=git_state.baseline_ref,
            )
        except DiffSummaryError as exc:
            return DiffSummary(
                project_id=project_id,
                repository_workspace_id=repository_workspace_id,
                repository_root_path=repository_root_path,
                baseline_label=baseline_branch,
                target_label="当前工作区",
                comparison_mode=DiffComparisonMode.BASELINE_TO_WORKTREE,
                dirty_workspace=False,
                dirty_file_count=0,
                note=str(exc),
                generated_at=utc_now(),
                files=[],
                key_files=[],
            )

        diff_rows_by_path: dict[str, DiffFileChange] = {}

        for path, change_kind in name_status_map.items():
            context = target_file_context_map.get(path)
            added_line_count, deleted_line_count = numstat_map.get(path, (0, 0))
            diff_rows_by_path[path] = DiffFileChange(
                relative_path=path,
                change_kind=change_kind,
                added_line_count=added_line_count,
                deleted_line_count=deleted_line_count,
                in_change_batch=context is not None,
                in_dirty_workspace=path in git_state.dirty_status_by_path,
                linked_task_ids=list(context.task_ids) if context is not None else [],
                linked_change_plan_ids=(
                    list(context.change_plan_ids) if context is not None else []
                ),
            )

        for path, (added_line_count, deleted_line_count) in numstat_map.items():
            if path in diff_rows_by_path:
                continue

            context = target_file_context_map.get(path)
            diff_rows_by_path[path] = DiffFileChange(
                relative_path=path,
                change_kind=DiffFileChangeKind.MODIFIED,
                added_line_count=added_line_count,
                deleted_line_count=deleted_line_count,
                in_change_batch=context is not None,
                in_dirty_workspace=path in git_state.dirty_status_by_path,
                linked_task_ids=list(context.task_ids) if context is not None else [],
                linked_change_plan_ids=(
                    list(context.change_plan_ids) if context is not None else []
                ),
            )

        for path, git_status in git_state.dirty_status_by_path.items():
            if path in diff_rows_by_path:
                diff_rows_by_path[path].notes.append(f"工作区状态 {git_status}")
                continue

            if git_status != "??":
                continue

            context = target_file_context_map.get(path)
            diff_rows_by_path[path] = DiffFileChange(
                relative_path=path,
                change_kind=DiffFileChangeKind.UNTRACKED,
                added_line_count=self._count_file_lines(repository_root / path),
                deleted_line_count=0,
                in_change_batch=context is not None,
                in_dirty_workspace=True,
                linked_task_ids=list(context.task_ids) if context is not None else [],
                linked_change_plan_ids=(
                    list(context.change_plan_ids) if context is not None else []
                ),
                notes=["当前为未跟踪文件"],
            )

        files = sorted(
            diff_rows_by_path.values(),
            key=lambda item: (
                0 if item.in_change_batch else 1,
                -item.changed_line_count,
                item.relative_path,
            ),
        )
        key_files = self._select_key_files(files)

        note = "；".join(git_state.notes) if git_state.notes else None
        return DiffSummary(
            project_id=project_id,
            repository_workspace_id=repository_workspace_id,
            repository_root_path=repository_root_path,
            baseline_label=git_state.baseline_label,
            target_label=git_state.target_label,
            comparison_mode=DiffComparisonMode.BASELINE_TO_WORKTREE,
            dirty_workspace=bool(git_state.dirty_status_by_path),
            dirty_file_count=len(git_state.dirty_status_by_path),
            note=note,
            generated_at=utc_now(),
            files=files,
            key_files=key_files,
        )

    def _build_plan_items(
        self,
        selected_change_batch: ChangeBatch | None,
    ) -> list[ChangeEvidencePlanItem]:
        """Project one selected ChangeBatch into evidence-package plan items."""

        if selected_change_batch is None:
            return []

        return [
            ChangeEvidencePlanItem(
                change_plan_id=snapshot.change_plan_id,
                change_plan_title=snapshot.change_plan_title,
                selected_version_number=snapshot.selected_version_number,
                task_id=snapshot.task_id,
                task_title=snapshot.task_title,
                intent_summary=snapshot.intent_summary,
                expected_actions=list(snapshot.expected_actions),
                risk_notes=list(snapshot.risk_notes),
                target_file_paths=[
                    target_file.relative_path for target_file in snapshot.target_files
                ],
                verification_commands=list(snapshot.verification_commands),
                verification_template_names=[
                    template.name for template in snapshot.verification_templates
                ],
                related_deliverable_ids=[
                    deliverable.deliverable_id
                    for deliverable in snapshot.related_deliverables
                ],
                related_deliverable_titles=[
                    deliverable.title for deliverable in snapshot.related_deliverables
                ],
            )
            for snapshot in selected_change_batch.plan_snapshots
        ]

    def _build_deliverable_references(
        self,
        *,
        deliverable_record_map: dict[UUID, DeliverableRecord],
        selected_change_batch: ChangeBatch | None,
        selected_deliverable_id: UUID | None,
    ) -> list[ChangeEvidenceDeliverableReference]:
        """Build one ordered deliverable-reference list for the evidence package."""

        deliverable_ids: list[UUID] = []
        if selected_deliverable_id is not None:
            deliverable_ids.append(selected_deliverable_id)

        if selected_change_batch is not None:
            for snapshot in selected_change_batch.plan_snapshots:
                for deliverable in snapshot.related_deliverables:
                    if deliverable.deliverable_id not in deliverable_ids:
                        deliverable_ids.append(deliverable.deliverable_id)

        if not deliverable_ids:
            for record in deliverable_record_map.values():
                deliverable_ids.append(record.deliverable.id)
                if len(deliverable_ids) >= MAX_DELIVERABLE_REFERENCES:
                    break

        items: list[ChangeEvidenceDeliverableReference] = []
        for deliverable_id in deliverable_ids[:MAX_DELIVERABLE_REFERENCES]:
            record = deliverable_record_map.get(deliverable_id)
            if record is None:
                continue

            latest_version = record.versions[0] if record.versions else None
            items.append(
                ChangeEvidenceDeliverableReference(
                    deliverable_id=record.deliverable.id,
                    title=record.deliverable.title,
                    type=record.deliverable.type,
                    stage=record.deliverable.stage,
                    current_version_number=record.deliverable.current_version_number,
                    latest_version_id=latest_version.id if latest_version else None,
                    latest_version_summary=latest_version.summary if latest_version else None,
                    latest_version_created_at=(
                        latest_version.created_at if latest_version else None
                    ),
                    source_task_id=latest_version.source_task_id if latest_version else None,
                    source_run_id=latest_version.source_run_id if latest_version else None,
                    selected=record.deliverable.id == selected_deliverable_id,
                )
            )

        return items

    def _build_approval_references(
        self,
        *,
        project_id: UUID,
        deliverables: list[ChangeEvidenceDeliverableReference],
        selected_deliverable_id: UUID | None,
        selected_approval_id: UUID | None,
    ) -> list[ChangeEvidenceApprovalReference]:
        """Build one approval-context list for the evidence package."""

        ordered_records: list[ApprovalRecord] = []
        seen_ids: set[UUID] = set()

        def append_record(record: ApprovalRecord | None) -> None:
            if record is None or record.approval.id in seen_ids:
                return

            ordered_records.append(record)
            seen_ids.add(record.approval.id)

        if selected_approval_id is not None:
            append_record(self.approval_repository.get_record_by_id(selected_approval_id))

        if selected_deliverable_id is not None:
            for record in self.approval_repository.list_records_by_deliverable_id(
                selected_deliverable_id
            )[:3]:
                append_record(record)

        for deliverable in deliverables:
            append_record(
                self.approval_repository.get_latest_record_by_deliverable_id(
                    deliverable.deliverable_id
                )
            )

        if not ordered_records:
            for record in self.approval_repository.list_records_by_project_id(project_id)[:3]:
                append_record(record)

        items: list[ChangeEvidenceApprovalReference] = []
        for record in ordered_records[:MAX_APPROVAL_REFERENCES]:
            latest_decision = record.decisions[-1] if record.decisions else None
            approval = record.approval
            items.append(
                ChangeEvidenceApprovalReference(
                    approval_id=approval.id,
                    deliverable_id=approval.deliverable_id,
                    deliverable_title=approval.deliverable_title,
                    deliverable_version_number=approval.deliverable_version_number,
                    status=approval.status,
                    request_note=approval.request_note,
                    latest_summary=approval.latest_summary,
                    latest_decision_action=latest_decision.action if latest_decision else None,
                    latest_decision_summary=(
                        latest_decision.summary if latest_decision else None
                    ),
                    latest_decision_actor_name=(
                        latest_decision.actor_name if latest_decision else None
                    ),
                    latest_decision_at=(
                        latest_decision.created_at if latest_decision else None
                    ),
                    requested_changes=(
                        list(latest_decision.requested_changes)
                        if latest_decision
                        else []
                    ),
                    highlighted_risks=(
                        list(latest_decision.highlighted_risks)
                        if latest_decision
                        else []
                    ),
                    requested_at=approval.requested_at,
                    due_at=approval.due_at,
                    decided_at=approval.decided_at,
                    selected=approval.id == selected_approval_id,
                )
            )

        return items

    def _build_verification_summary(
        self,
        *,
        project_id: UUID,
        selected_change_batch: ChangeBatch | None,
    ) -> ChangeEvidenceVerificationSummary:
        """Build one verification-result summary for the evidence package."""

        runs = self.verification_run_repository.list_by_project_id(
            project_id,
            change_batch_id=selected_change_batch.id if selected_change_batch else None,
        )
        batch_cache: dict[UUID, ChangeBatch | None] = {}
        items: list[ChangeEvidenceVerificationRunItem] = []

        for run in runs[:MAX_VERIFICATION_SAMPLE_RUNS]:
            change_batch = selected_change_batch
            if change_batch is None or change_batch.id != run.change_batch_id:
                if run.change_batch_id not in batch_cache:
                    batch_cache[run.change_batch_id] = self.change_batch_repository.get_by_id(
                        run.change_batch_id
                    )
                change_batch = batch_cache[run.change_batch_id]

            plan_snapshot = None
            if change_batch is not None:
                plan_snapshot = next(
                    (
                        snapshot
                        for snapshot in change_batch.plan_snapshots
                        if snapshot.change_plan_id == run.change_plan_id
                    ),
                    None,
                )

            items.append(
                ChangeEvidenceVerificationRunItem(
                    verification_run_id=run.id,
                    change_batch_id=run.change_batch_id,
                    change_batch_title=(
                        change_batch.title if change_batch is not None else str(run.change_batch_id)
                    ),
                    change_plan_id=run.change_plan_id,
                    change_plan_title=(
                        plan_snapshot.change_plan_title
                        if plan_snapshot is not None
                        else str(run.change_plan_id)
                    ),
                    task_title=plan_snapshot.task_title if plan_snapshot is not None else None,
                    verification_template_name=run.verification_template_name,
                    status=run.status,
                    failure_category=run.failure_category,
                    command_source=run.command_source,
                    command=run.command,
                    output_summary=run.output_summary,
                    started_at=run.started_at,
                    finished_at=run.finished_at,
                )
            )

        return ChangeEvidenceVerificationSummary(
            total_runs=len(runs),
            passed_runs=sum(1 for run in runs if run.status.value == "passed"),
            failed_runs=sum(1 for run in runs if run.status.value == "failed"),
            skipped_runs=sum(1 for run in runs if run.status.value == "skipped"),
            latest_finished_at=runs[0].finished_at if runs else None,
            runs=items,
        )

    def _build_snapshots(
        self,
        *,
        selected_change_batch: ChangeBatch | None,
        deliverables: list[ChangeEvidenceDeliverableReference],
        approvals: list[ChangeEvidenceApprovalReference],
        verification_summary: ChangeEvidenceVerificationSummary,
    ) -> list[ChangeEvidenceSnapshot]:
        """Build a compact Day11 snapshot timeline used for approval-before/after comparison."""

        snapshots: list[ChangeEvidenceSnapshot] = []

        if selected_change_batch is not None:
            snapshots.append(
                ChangeEvidenceSnapshot(
                    snapshot_id=f"change-batch:{selected_change_batch.id}",
                    label=f"ChangeBatch · {selected_change_batch.title}",
                    summary=selected_change_batch.summary,
                    snapshot_kind=ChangeEvidenceSnapshotKind.CHANGE_BATCH,
                    source_id=str(selected_change_batch.id),
                    recorded_at=selected_change_batch.updated_at,
                    selected=True,
                )
            )

        for deliverable in deliverables:
            if (
                deliverable.latest_version_id is None
                or deliverable.latest_version_created_at is None
            ):
                continue

            snapshots.append(
                ChangeEvidenceSnapshot(
                    snapshot_id=f"deliverable:{deliverable.deliverable_id}:v{deliverable.current_version_number}",
                    label=f"{deliverable.title} · v{deliverable.current_version_number}",
                    summary=deliverable.latest_version_summary
                    or "当前版本已纳入 Day11 证据包。",
                    snapshot_kind=ChangeEvidenceSnapshotKind.DELIVERABLE_VERSION,
                    source_id=str(deliverable.latest_version_id),
                    recorded_at=deliverable.latest_version_created_at,
                    selected=deliverable.selected,
                )
            )

        for approval in approvals:
            snapshots.append(
                ChangeEvidenceSnapshot(
                    snapshot_id=f"approval:{approval.approval_id}",
                    label=f"{approval.deliverable_title} 审批 · v{approval.deliverable_version_number}",
                    summary=approval.latest_decision_summary
                    or approval.latest_summary
                    or "老板审批上下文已纳入 Day11 证据包。",
                    snapshot_kind=ChangeEvidenceSnapshotKind.APPROVAL,
                    source_id=str(approval.approval_id),
                    recorded_at=approval.latest_decision_at
                    or approval.decided_at
                    or approval.requested_at,
                    selected=approval.selected,
                )
            )

        if verification_summary.runs:
            latest_run = verification_summary.runs[0]
            snapshots.append(
                ChangeEvidenceSnapshot(
                    snapshot_id=f"verification:{latest_run.verification_run_id}",
                    label=f"验证结果 · {latest_run.change_plan_title}",
                    summary=latest_run.output_summary,
                    snapshot_kind=ChangeEvidenceSnapshotKind.VERIFICATION_RUN,
                    source_id=str(latest_run.verification_run_id),
                    recorded_at=latest_run.finished_at,
                    selected=False,
                )
            )

        return sorted(
            snapshots,
            key=lambda item: (item.recorded_at, item.snapshot_id),
            reverse=True,
        )[:MAX_SNAPSHOTS]

    @staticmethod
    def _build_package_key(
        *,
        project_id: UUID,
        selected_change_batch: ChangeBatch | None,
        selected_deliverable_id: UUID | None,
        selected_approval_id: UUID | None,
        deliverables: list[ChangeEvidenceDeliverableReference],
        approvals: list[ChangeEvidenceApprovalReference],
        diff_summary: DiffSummary,
        verification_summary: ChangeEvidenceVerificationSummary,
    ) -> str:
        """Build one deterministic package key that changes with the evidence snapshot."""

        seed = "|".join(
            [
                str(project_id),
                str(selected_change_batch.id) if selected_change_batch else "no-batch",
                str(selected_deliverable_id) if selected_deliverable_id else "no-deliverable",
                str(selected_approval_id) if selected_approval_id else "no-approval",
                f"diff:{diff_summary.metrics.changed_file_count}:{diff_summary.metrics.total_added_line_count}:{diff_summary.metrics.total_deleted_line_count}",
                ",".join(
                    f"{item.deliverable_id}:{item.current_version_number}"
                    for item in deliverables
                ),
                ",".join(
                    f"{item.approval_id}:{item.deliverable_version_number}:{item.status.value}"
                    for item in approvals
                ),
                f"runs:{verification_summary.total_runs}:{verification_summary.latest_finished_at.isoformat() if verification_summary.latest_finished_at else 'none'}",
            ]
        )
        return f"cep-{uuid5(NAMESPACE_URL, seed)}"

    @staticmethod
    def _build_package_summary(
        *,
        selected_change_batch: ChangeBatch | None,
        diff_summary: DiffSummary,
        plan_items: list[ChangeEvidencePlanItem],
        verification_summary: ChangeEvidenceVerificationSummary,
        deliverables: list[ChangeEvidenceDeliverableReference],
        approvals: list[ChangeEvidenceApprovalReference],
    ) -> str:
        """Build one short narrative summary shown at the top of the evidence package."""

        prefix = (
            f"基于批次《{selected_change_batch.title}》"
            if selected_change_batch is not None
            else "基于当前项目上下文"
        )
        return (
            f"{prefix}汇总 {diff_summary.metrics.changed_file_count} 个差异文件、"
            f"{len(plan_items)} 个变更计划快照、"
            f"{verification_summary.total_runs} 条验证记录、"
            f"{len(deliverables)} 个交付件引用和 {len(approvals)} 条审批上下文。"
        )

    @staticmethod
    def _build_target_file_context_map(
        selected_change_batch: ChangeBatch | None,
    ) -> dict[str, _TargetFileContext]:
        """Aggregate ChangeBatch task / plan linkage by repository-relative file path."""

        if selected_change_batch is None:
            return {}

        mapping: dict[str, _TargetFileContext] = {}
        for snapshot in selected_change_batch.plan_snapshots:
            for target_file in snapshot.target_files:
                normalized_path = DiffSummaryService._normalize_relative_path(
                    target_file.relative_path
                )
                if not normalized_path:
                    continue

                context = mapping.setdefault(normalized_path, _TargetFileContext())
                if snapshot.task_id not in context.task_ids:
                    context.task_ids.append(snapshot.task_id)
                if snapshot.change_plan_id not in context.change_plan_ids:
                    context.change_plan_ids.append(snapshot.change_plan_id)

        return mapping

    @staticmethod
    def _select_key_files(files: list[DiffFileChange]) -> list[DiffFileChange]:
        """Pick a compact key-file list for boss acceptance review."""

        if not files:
            return []

        preferred_files = [
            item
            for item in files
            if item.in_change_batch
            or item.change_kind in {DiffFileChangeKind.DELETED, DiffFileChangeKind.UNTRACKED}
        ]
        source_files = preferred_files or files
        return source_files[:MAX_KEY_FILES]

    def _resolve_change_batch(
        self,
        *,
        project_id: UUID,
        change_batch_id: UUID | None,
        deliverable_id: UUID | None,
    ) -> ChangeBatch | None:
        """Resolve the most relevant ChangeBatch for one Day11 evidence scope."""

        if change_batch_id is not None:
            change_batch = self.change_batch_repository.get_by_id(change_batch_id)
            if change_batch is None or change_batch.project_id != project_id:
                raise DiffSummaryChangeBatchNotFoundError(
                    f"Change batch not found: {change_batch_id}"
                )

            return change_batch

        if deliverable_id is not None:
            for change_batch in self.change_batch_repository.list_by_project_id(project_id):
                if any(
                    deliverable.deliverable_id == deliverable_id
                    for snapshot in change_batch.plan_snapshots
                    for deliverable in snapshot.related_deliverables
                ):
                    return change_batch

        return self.change_batch_repository.get_active_by_project_id(
            project_id
        ) or next(
            iter(self.change_batch_repository.list_by_project_id(project_id)),
            None,
        )

    def _ensure_project_exists(self, project_id: UUID) -> None:
        """Require that the target project exists before Day11 work begins."""

        if self.project_repository.get_by_id(project_id) is None:
            raise DiffSummaryProjectNotFoundError(f"Project not found: {project_id}")

    def _require_workspace(self, project_id: UUID):
        """Require one bound repository workspace for Day11 diff / evidence views."""

        workspace = self.repository_workspace_repository.get_by_project_id(project_id)
        if workspace is None:
            raise DiffSummaryWorkspaceNotFoundError(
                f"Repository workspace not found for project: {project_id}"
            )

        return workspace

    def _resolve_git_comparison_state(
        self,
        repository_root: Path,
        *,
        baseline_branch: str,
    ) -> _GitComparisonState:
        """Resolve the Day11 baseline ref and current dirty workspace preview."""

        notes: list[str] = []
        baseline_ref = self._resolve_git_ref(
            repository_root,
            f"refs/heads/{baseline_branch}",
            f"refs/remotes/origin/{baseline_branch}",
            baseline_branch,
        )
        baseline_label = baseline_ref or baseline_branch
        if baseline_ref is None:
            baseline_ref = "HEAD"
            notes.append(
                f"未解析到基线分支 `{baseline_branch}`，Day11 差异暂退回到 HEAD 对当前工作区。"
            )

        current_branch = (
            self._run_git(
                repository_root,
                "rev-parse",
                "--abbrev-ref",
                "HEAD",
                check=False,
            )
            or "HEAD"
        )
        dirty_status_by_path = self._read_git_dirty_status(repository_root)

        return _GitComparisonState(
            baseline_ref=baseline_ref,
            baseline_label=baseline_label,
            target_label=f"{current_branch} 工作区",
            dirty_status_by_path=dirty_status_by_path,
            notes=notes,
        )

    def _read_git_name_status(
        self,
        repository_root: Path,
        *,
        baseline_ref: str,
    ) -> dict[str, DiffFileChangeKind]:
        """Read one path -> change-kind mapping using `git diff --name-status`."""

        raw_output = self._run_git(
            repository_root,
            "diff",
            "--name-status",
            "--no-renames",
            baseline_ref,
            check=True,
        )
        mapping: dict[str, DiffFileChangeKind] = {}
        for line in raw_output.splitlines():
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue

            status_code, relative_path = parts
            normalized_path = self._normalize_relative_path(relative_path)
            if not normalized_path:
                continue

            first_code = status_code[:1]
            if first_code == "A":
                mapping[normalized_path] = DiffFileChangeKind.ADDED
            elif first_code == "D":
                mapping[normalized_path] = DiffFileChangeKind.DELETED
            else:
                mapping[normalized_path] = DiffFileChangeKind.MODIFIED

        return mapping

    def _read_git_numstat(
        self,
        repository_root: Path,
        *,
        baseline_ref: str,
    ) -> dict[str, tuple[int, int]]:
        """Read one path -> (added_lines, deleted_lines) mapping from Git numstat."""

        raw_output = self._run_git(
            repository_root,
            "diff",
            "--numstat",
            "--no-renames",
            baseline_ref,
            check=True,
        )
        mapping: dict[str, tuple[int, int]] = {}
        for line in raw_output.splitlines():
            parts = line.split("\t", 2)
            if len(parts) != 3:
                continue

            raw_added, raw_deleted, relative_path = parts
            normalized_path = self._normalize_relative_path(relative_path)
            if not normalized_path:
                continue

            mapping[normalized_path] = (
                0 if raw_added == "-" else int(raw_added),
                0 if raw_deleted == "-" else int(raw_deleted),
            )

        return mapping

    def _read_git_dirty_status(self, repository_root: Path) -> dict[str, str]:
        """Read one bounded map of dirty or untracked files from Git status."""

        raw_output = self._run_git(
            repository_root,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            check=True,
        )
        mapping: dict[str, str] = {}
        for line in raw_output.splitlines():
            if len(line) < 3:
                continue

            git_status = line[:2]
            raw_path = line[3:].strip()
            if " -> " in raw_path and git_status[0] in {"R", "C"}:
                raw_path = raw_path.split(" -> ", 1)[1]

            normalized_path = self._normalize_relative_path(raw_path)
            if not normalized_path:
                continue

            mapping[normalized_path] = git_status

        return mapping

    @staticmethod
    def _count_file_lines(file_path: Path) -> int:
        """Return a best-effort line count for one untracked file."""

        try:
            raw_bytes = file_path.read_bytes()
        except OSError:
            return 0

        if not raw_bytes:
            return 0

        return len(raw_bytes.splitlines()) or 1

    def _resolve_git_ref(self, repository_root: Path, *candidates: str) -> str | None:
        """Resolve the first Git ref candidate that points at an existing commit."""

        for candidate in candidates:
            if not candidate:
                continue

            resolved_value = self._run_git(
                repository_root,
                "rev-parse",
                "--verify",
                f"{candidate}^{{commit}}",
                check=False,
            )
            if resolved_value:
                return candidate

        return None

    @staticmethod
    def _normalize_relative_path(value: str) -> str:
        """Normalize one Git-reported relative path into a stable POSIX path."""

        normalized_value = value.replace("\\", "/").strip().strip('"')
        if not normalized_value:
            return ""

        normalized_path = PurePosixPath(normalized_value)
        if normalized_path.is_absolute() or ".." in normalized_path.parts:
            return ""

        return normalized_path.as_posix().lstrip("./")

    @staticmethod
    def _run_git(
        repository_root: Path,
        *args: str,
        check: bool,
    ) -> str:
        """Run one read-only Git command and normalize its text output."""

        git_environment = os.environ.copy()
        git_environment.setdefault("GIT_OPTIONAL_LOCKS", "0")

        try:
            completed_process = subprocess.run(
                ["git", *args],
                cwd=repository_root,
                env=git_environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=GIT_COMMAND_TIMEOUT_SECONDS,
                check=False,
            )
        except FileNotFoundError as exc:  # pragma: no cover - environment-specific
            raise DiffSummaryError("Git executable is not available.") from exc
        except OSError as exc:
            raise DiffSummaryError(
                f"Unable to inspect the bound repository path: {repository_root}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise DiffSummaryError(
                f"Timed out while reading Git diff state for repository: {repository_root}"
            ) from exc

        output = (completed_process.stdout or "").rstrip("\r\n")
        if completed_process.returncode == 0:
            return output
        if not check:
            return ""

        error_message = (
            (completed_process.stderr or "").strip()
            or output
            or f"Git command failed: git {' '.join(args)}"
        )
        raise DiffSummaryError(error_message)
