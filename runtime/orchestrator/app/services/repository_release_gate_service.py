"""Business services for V4 Day14 repository release-gate checklists."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
import json
from pathlib import Path
from uuid import UUID, uuid4

from app.core.config import settings
from app.domain._base import ensure_utc_datetime, utc_now
from app.domain.approval import (
    ApprovalDecisionAction,
    ApprovalStatus,
    map_approval_action_to_status,
)
from app.domain.change_batch import ChangeBatch, ChangeBatchPreflightStatus
from app.domain.commit_candidate import CommitCandidate
from app.domain.repository_snapshot import RepositorySnapshotStatus
from app.domain.verification_run import VerificationRunStatus
from app.repositories.change_batch_repository import ChangeBatchRepository
from app.repositories.commit_candidate_repository import CommitCandidateRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.repository_snapshot_repository import (
    RepositorySnapshotRepository,
)
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)
from app.repositories.verification_run_repository import VerificationRunRepository
from app.services.diff_summary_service import (
    DiffSummaryChangeBatchNotFoundError,
    DiffSummaryProjectNotFoundError,
    DiffSummaryService,
    DiffSummaryWorkspaceNotFoundError,
)


DEFAULT_SNAPSHOT_FRESHNESS_HOURS = 24
RELEASE_GATE_DECISION_DIR_NAME = "repository-release-gates"


class RepositoryReleaseGateError(ValueError):
    """Base error raised by the Day14 repository release-gate service."""


class RepositoryReleaseGateProjectNotFoundError(RepositoryReleaseGateError):
    """Raised when one requested project cannot be resolved."""


class RepositoryReleaseGateChangeBatchNotFoundError(RepositoryReleaseGateError):
    """Raised when one requested change batch cannot be resolved."""


class RepositoryReleaseGateActionValidationError(RepositoryReleaseGateError):
    """Raised when one Day14 action request is invalid."""


class RepositoryReleaseGateBlockedError(RepositoryReleaseGateError):
    """Raised when the release gate is blocked but an approval was attempted."""


class RepositoryReleaseChecklistItemStatus(StrEnum):
    """Stable Day14 release-checklist item statuses."""

    PASSED = "passed"
    MISSING = "missing"


class RepositoryReleaseGateStatus(StrEnum):
    """Stable Day14 release-gate statuses."""

    BLOCKED = "blocked"
    PENDING_APPROVAL = ApprovalStatus.PENDING_APPROVAL.value
    APPROVED = ApprovalStatus.APPROVED.value
    REJECTED = ApprovalStatus.REJECTED.value
    CHANGES_REQUESTED = ApprovalStatus.CHANGES_REQUESTED.value


@dataclass(slots=True, frozen=True)
class RepositoryReleaseChecklistItem:
    """One Day14 release-checklist item."""

    key: str
    title: str
    required: bool
    status: RepositoryReleaseChecklistItemStatus
    summary: str
    gap_reason: str | None = None
    evidence_key: str | None = None
    checked_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class RepositoryReleaseGateDecision:
    """One Day14 release-gate decision record compatible with V3 approvals."""

    id: UUID
    change_batch_id: UUID
    action: ApprovalDecisionAction
    actor_name: str
    summary: str
    comment: str | None
    highlighted_risks: list[str]
    requested_changes: list[str]
    created_at: datetime


@dataclass(slots=True, frozen=True)
class RepositoryReleaseGate:
    """One Day14 release-gate detail snapshot for a change batch."""

    project_id: UUID
    change_batch_id: UUID
    change_batch_title: str
    generated_at: datetime
    snapshot_age_minutes: int | None
    required_item_count: int
    passed_item_count: int
    checklist_items: list[RepositoryReleaseChecklistItem]
    missing_item_keys: list[str]
    gap_reasons: list[str]
    blocked: bool
    status: RepositoryReleaseGateStatus
    approval_status: ApprovalStatus | None
    release_qualification_established: bool
    git_write_actions_triggered: bool
    decision_count: int
    latest_decision: RepositoryReleaseGateDecision | None
    decisions: list[RepositoryReleaseGateDecision]


@dataclass(slots=True, frozen=True)
class RepositoryReleaseGateSummary:
    """One project-level Day14 release-gate summary row."""

    change_batch_id: UUID
    change_batch_title: str
    generated_at: datetime
    status: RepositoryReleaseGateStatus
    blocked: bool
    missing_item_count: int
    decision_count: int
    release_qualification_established: bool
    latest_decision: RepositoryReleaseGateDecision | None


@dataclass(slots=True, frozen=True)
class ProjectRepositoryReleaseGateInbox:
    """Project-scoped Day14 release-gate inbox summary."""

    project_id: UUID
    generated_at: datetime
    total_batches: int
    blocked_batches: int
    pending_batches: int
    approved_batches: int
    rejected_batches: int
    changes_requested_batches: int
    items: list[RepositoryReleaseGateSummary]


class RepositoryReleaseGateService:
    """Aggregate Day14 release checklists and persist release-gate decisions."""

    def __init__(
        self,
        *,
        project_repository: ProjectRepository,
        repository_workspace_repository: RepositoryWorkspaceRepository,
        repository_snapshot_repository: RepositorySnapshotRepository,
        change_batch_repository: ChangeBatchRepository,
        commit_candidate_repository: CommitCandidateRepository,
        verification_run_repository: VerificationRunRepository,
        diff_summary_service: DiffSummaryService,
        snapshot_freshness_threshold: timedelta = timedelta(
            hours=DEFAULT_SNAPSHOT_FRESHNESS_HOURS
        ),
    ) -> None:
        self.project_repository = project_repository
        self.repository_workspace_repository = repository_workspace_repository
        self.repository_snapshot_repository = repository_snapshot_repository
        self.change_batch_repository = change_batch_repository
        self.commit_candidate_repository = commit_candidate_repository
        self.verification_run_repository = verification_run_repository
        self.diff_summary_service = diff_summary_service
        self.snapshot_freshness_threshold = snapshot_freshness_threshold

    def list_project_release_gates(
        self,
        project_id: UUID,
    ) -> ProjectRepositoryReleaseGateInbox:
        """Return all Day14 release-gate summaries under one project."""

        self._ensure_project_exists(project_id)
        gates = [
            self.get_release_gate(change_batch.id)
            for change_batch in self.change_batch_repository.list_by_project_id(project_id)
        ]
        summaries = [
            RepositoryReleaseGateSummary(
                change_batch_id=gate.change_batch_id,
                change_batch_title=gate.change_batch_title,
                generated_at=gate.generated_at,
                status=gate.status,
                blocked=gate.blocked,
                missing_item_count=len(gate.missing_item_keys),
                decision_count=gate.decision_count,
                release_qualification_established=gate.release_qualification_established,
                latest_decision=gate.latest_decision,
            )
            for gate in gates
        ]

        return ProjectRepositoryReleaseGateInbox(
            project_id=project_id,
            generated_at=utc_now(),
            total_batches=len(summaries),
            blocked_batches=sum(
                1
                for item in summaries
                if item.status == RepositoryReleaseGateStatus.BLOCKED
            ),
            pending_batches=sum(
                1
                for item in summaries
                if item.status == RepositoryReleaseGateStatus.PENDING_APPROVAL
            ),
            approved_batches=sum(
                1
                for item in summaries
                if item.status == RepositoryReleaseGateStatus.APPROVED
            ),
            rejected_batches=sum(
                1
                for item in summaries
                if item.status == RepositoryReleaseGateStatus.REJECTED
            ),
            changes_requested_batches=sum(
                1
                for item in summaries
                if item.status == RepositoryReleaseGateStatus.CHANGES_REQUESTED
            ),
            items=summaries,
        )

    def get_release_gate(self, change_batch_id: UUID) -> RepositoryReleaseGate:
        """Return one Day14 release-gate detail for a selected change batch."""

        now = utc_now()
        change_batch = self._require_change_batch(change_batch_id)
        project_id = change_batch.project_id
        workspace = self.repository_workspace_repository.get_by_project_id(project_id)
        snapshot = self.repository_snapshot_repository.get_by_project_id(project_id)
        commit_candidate = self.commit_candidate_repository.get_by_change_batch_id(
            change_batch_id
        )
        decisions = self._load_decisions(change_batch_id=change_batch_id)

        checklist_items = self._build_checklist_items(
            now=now,
            change_batch=change_batch,
            workspace=workspace,
            snapshot=snapshot,
            commit_candidate=commit_candidate,
        )
        missing_items = [
            item
            for item in checklist_items
            if item.required and item.status == RepositoryReleaseChecklistItemStatus.MISSING
        ]
        missing_item_keys = [item.key for item in missing_items]
        gap_reasons = [item.gap_reason for item in missing_items if item.gap_reason]
        blocked = bool(missing_items)

        latest_decision = decisions[-1] if decisions else None
        approval_status = (
            None
            if blocked
            else (
                map_approval_action_to_status(latest_decision.action)
                if latest_decision is not None
                else ApprovalStatus.PENDING_APPROVAL
            )
        )
        status = (
            RepositoryReleaseGateStatus.BLOCKED
            if blocked
            else RepositoryReleaseGateStatus(approval_status.value)
        )
        release_qualification_established = (
            not blocked and approval_status == ApprovalStatus.APPROVED
        )

        snapshot_age_minutes = self._resolve_snapshot_age_minutes(
            now=now,
            snapshot=snapshot,
        )
        required_item_count = sum(1 for item in checklist_items if item.required)
        passed_item_count = sum(
            1
            for item in checklist_items
            if item.required and item.status == RepositoryReleaseChecklistItemStatus.PASSED
        )

        return RepositoryReleaseGate(
            project_id=project_id,
            change_batch_id=change_batch_id,
            change_batch_title=change_batch.title,
            generated_at=now,
            snapshot_age_minutes=snapshot_age_minutes,
            required_item_count=required_item_count,
            passed_item_count=passed_item_count,
            checklist_items=checklist_items,
            missing_item_keys=missing_item_keys,
            gap_reasons=gap_reasons,
            blocked=blocked,
            status=status,
            approval_status=approval_status,
            release_qualification_established=release_qualification_established,
            git_write_actions_triggered=False,
            decision_count=len(decisions),
            latest_decision=latest_decision,
            decisions=decisions,
        )

    def apply_release_gate_action(
        self,
        *,
        change_batch_id: UUID,
        action: ApprovalDecisionAction,
        actor_name: str,
        summary: str,
        comment: str | None = None,
        highlighted_risks: list[str] | None = None,
        requested_changes: list[str] | None = None,
    ) -> RepositoryReleaseGate:
        """Append one Day14 release-gate decision and return the latest snapshot."""

        change_batch = self._require_change_batch(change_batch_id)
        gate = self.get_release_gate(change_batch_id)

        normalized_actor_name = self._normalize_required_text(
            actor_name,
            field_name="actor_name",
            max_length=100,
        )
        normalized_summary = self._normalize_required_text(
            summary,
            field_name="summary",
            max_length=500,
        )
        normalized_comment = self._normalize_optional_text(comment, max_length=2_000)
        normalized_highlighted_risks = self._normalize_string_list(
            highlighted_risks or [],
            max_length=20,
        )
        normalized_requested_changes = self._normalize_string_list(
            requested_changes or [],
            max_length=20,
        )

        if action == ApprovalDecisionAction.APPROVE and gate.blocked:
            raise RepositoryReleaseGateBlockedError(
                "Release gate is blocked by missing required checklist items: "
                + "；".join(gate.gap_reasons or gate.missing_item_keys)
            )

        decision = RepositoryReleaseGateDecision(
            id=uuid4(),
            change_batch_id=change_batch_id,
            action=action,
            actor_name=normalized_actor_name,
            summary=normalized_summary,
            comment=normalized_comment,
            highlighted_risks=normalized_highlighted_risks,
            requested_changes=normalized_requested_changes,
            created_at=utc_now(),
        )
        persisted_decisions = [*gate.decisions, decision]
        self._save_decisions(
            change_batch_id=change_batch_id,
            project_id=change_batch.project_id,
            decisions=persisted_decisions,
        )
        return self.get_release_gate(change_batch_id)

    def _build_checklist_items(
        self,
        *,
        now: datetime,
        change_batch: ChangeBatch,
        workspace,
        snapshot,
        commit_candidate: CommitCandidate | None,
    ) -> list[RepositoryReleaseChecklistItem]:
        """Build the seven required Day14 release-checklist items."""

        return [
            self._build_repository_binding_item(now=now, workspace=workspace),
            self._build_snapshot_freshness_item(
                now=now,
                workspace=workspace,
                snapshot=snapshot,
            ),
            self._build_change_plan_item(now=now, change_batch=change_batch),
            self._build_risk_preflight_item(now=now, change_batch=change_batch),
            self._build_verification_item(now=now, change_batch=change_batch),
            self._build_diff_evidence_item(now=now, change_batch=change_batch),
            self._build_commit_draft_item(
                now=now,
                change_batch=change_batch,
                commit_candidate=commit_candidate,
            ),
        ]

    def _build_repository_binding_item(
        self,
        *,
        now: datetime,
        workspace,
    ) -> RepositoryReleaseChecklistItem:
        """Evaluate repository binding readiness."""

        if workspace is None:
            return RepositoryReleaseChecklistItem(
                key="repository_binding",
                title="仓库绑定",
                required=True,
                status=RepositoryReleaseChecklistItemStatus.MISSING,
                summary="项目尚未绑定本地主仓库。",
                gap_reason="缺少仓库绑定，放行检查单无法继续。",
                checked_at=now,
            )

        return RepositoryReleaseChecklistItem(
            key="repository_binding",
            title="仓库绑定",
            required=True,
            status=RepositoryReleaseChecklistItemStatus.PASSED,
            summary=f"已绑定仓库：{workspace.display_name} ({workspace.root_path})",
            checked_at=now,
        )

    def _build_snapshot_freshness_item(
        self,
        *,
        now: datetime,
        workspace,
        snapshot,
    ) -> RepositoryReleaseChecklistItem:
        """Evaluate repository-snapshot freshness."""

        if workspace is None:
            return RepositoryReleaseChecklistItem(
                key="snapshot_freshness",
                title="快照新鲜度",
                required=True,
                status=RepositoryReleaseChecklistItemStatus.MISSING,
                summary="仓库未绑定，无法核对快照新鲜度。",
                gap_reason="缺少仓库绑定导致无法验证快照。",
                checked_at=now,
            )

        if snapshot is None:
            return RepositoryReleaseChecklistItem(
                key="snapshot_freshness",
                title="快照新鲜度",
                required=True,
                status=RepositoryReleaseChecklistItemStatus.MISSING,
                summary="未找到仓库快照。",
                gap_reason="缺少仓库快照，请先执行 Day02 刷新。",
                checked_at=now,
            )

        if snapshot.repository_workspace_id != workspace.id:
            return RepositoryReleaseChecklistItem(
                key="snapshot_freshness",
                title="快照新鲜度",
                required=True,
                status=RepositoryReleaseChecklistItemStatus.MISSING,
                summary="仓库快照与当前绑定工作区不一致。",
                gap_reason="快照来源与当前仓库绑定不一致，请重新刷新快照。",
                checked_at=now,
            )

        if snapshot.status != RepositorySnapshotStatus.SUCCESS:
            return RepositoryReleaseChecklistItem(
                key="snapshot_freshness",
                title="快照新鲜度",
                required=True,
                status=RepositoryReleaseChecklistItemStatus.MISSING,
                summary="最新仓库快照状态为失败。",
                gap_reason=(
                    "仓库快照失败，需先修复扫描问题："
                    + (snapshot.scan_error or "无具体错误信息。")
                ),
                checked_at=now,
            )

        snapshot_age = now - snapshot.scanned_at
        if snapshot_age > self.snapshot_freshness_threshold:
            age_hours = round(snapshot_age.total_seconds() / 3600, 2)
            threshold_hours = round(
                self.snapshot_freshness_threshold.total_seconds() / 3600, 2
            )
            return RepositoryReleaseChecklistItem(
                key="snapshot_freshness",
                title="快照新鲜度",
                required=True,
                status=RepositoryReleaseChecklistItemStatus.MISSING,
                summary=(
                    f"最新快照已过期（约 {age_hours} 小时前），阈值 {threshold_hours} 小时。"
                ),
                gap_reason="快照过旧，需先刷新仓库快照后再放行。",
                checked_at=now,
            )

        age_minutes = max(0, int(snapshot_age.total_seconds() // 60))
        return RepositoryReleaseChecklistItem(
            key="snapshot_freshness",
            title="快照新鲜度",
            required=True,
            status=RepositoryReleaseChecklistItemStatus.PASSED,
            summary=f"快照有效，距今约 {age_minutes} 分钟。",
            checked_at=now,
        )

    def _build_change_plan_item(
        self,
        *,
        now: datetime,
        change_batch: ChangeBatch,
    ) -> RepositoryReleaseChecklistItem:
        """Evaluate Day07 change-plan coverage in the selected change batch."""

        plan_count = len(change_batch.plan_snapshots)
        target_file_count = sum(
            len(snapshot.target_files) for snapshot in change_batch.plan_snapshots
        )
        if plan_count <= 0 or target_file_count <= 0:
            return RepositoryReleaseChecklistItem(
                key="change_plan",
                title="变更计划",
                required=True,
                status=RepositoryReleaseChecklistItemStatus.MISSING,
                summary="变更批次缺少有效 ChangePlan 或目标文件集合。",
                gap_reason="缺少变更计划证据，无法评估放行范围。",
                checked_at=now,
            )

        return RepositoryReleaseChecklistItem(
            key="change_plan",
            title="变更计划",
            required=True,
            status=RepositoryReleaseChecklistItemStatus.PASSED,
            summary=f"已纳入 {plan_count} 个 ChangePlan，覆盖 {target_file_count} 个目标文件。",
            checked_at=now,
        )

    def _build_risk_preflight_item(
        self,
        *,
        now: datetime,
        change_batch: ChangeBatch,
    ) -> RepositoryReleaseChecklistItem:
        """Evaluate Day08 preflight readiness."""

        preflight = change_batch.preflight
        if (
            preflight.status
            not in {
                ChangeBatchPreflightStatus.READY_FOR_EXECUTION,
                ChangeBatchPreflightStatus.MANUAL_CONFIRMED,
            }
            or not preflight.ready_for_execution
        ):
            return RepositoryReleaseChecklistItem(
                key="risk_preflight",
                title="风险预检",
                required=True,
                status=RepositoryReleaseChecklistItemStatus.MISSING,
                summary=(
                    "执行前预检未达到可放行状态："
                    f"{preflight.status.value}。"
                ),
                gap_reason=(
                    "风险预检未通过（或仍待人工确认），禁止进入审批放行。"
                ),
                checked_at=now,
            )

        finding_count = preflight.finding_count
        return RepositoryReleaseChecklistItem(
            key="risk_preflight",
            title="风险预检",
            required=True,
            status=RepositoryReleaseChecklistItemStatus.PASSED,
            summary=f"预检已放行，记录风险项 {finding_count} 条。",
            checked_at=now,
        )

    def _build_verification_item(
        self,
        *,
        now: datetime,
        change_batch: ChangeBatch,
    ) -> RepositoryReleaseChecklistItem:
        """Evaluate Day09-Day10 verification results."""

        runs = self.verification_run_repository.list_by_project_id(
            change_batch.project_id,
            change_batch_id=change_batch.id,
        )
        total_runs = len(runs)
        passed_runs = sum(1 for run in runs if run.status == VerificationRunStatus.PASSED)
        failed_runs = sum(1 for run in runs if run.status == VerificationRunStatus.FAILED)
        skipped_runs = sum(1 for run in runs if run.status == VerificationRunStatus.SKIPPED)

        if total_runs <= 0 or passed_runs <= 0:
            return RepositoryReleaseChecklistItem(
                key="verification_results",
                title="验证结果",
                required=True,
                status=RepositoryReleaseChecklistItemStatus.MISSING,
                summary="缺少通过的仓库验证记录。",
                gap_reason="验证结果不足，至少需要一条通过记录。",
                checked_at=now,
            )

        if failed_runs > 0:
            return RepositoryReleaseChecklistItem(
                key="verification_results",
                title="验证结果",
                required=True,
                status=RepositoryReleaseChecklistItemStatus.MISSING,
                summary=f"存在失败验证记录：{failed_runs} 条。",
                gap_reason="验证未全量通过，需先处理失败记录。",
                checked_at=now,
            )

        return RepositoryReleaseChecklistItem(
            key="verification_results",
            title="验证结果",
            required=True,
            status=RepositoryReleaseChecklistItemStatus.PASSED,
            summary=f"验证通过：{passed_runs}/{total_runs}（跳过 {skipped_runs}）。",
            checked_at=now,
        )

    def _build_diff_evidence_item(
        self,
        *,
        now: datetime,
        change_batch: ChangeBatch,
    ) -> RepositoryReleaseChecklistItem:
        """Evaluate Day11 diff evidence availability."""

        try:
            evidence_package = self.diff_summary_service.get_project_change_evidence(
                change_batch.project_id,
                change_batch_id=change_batch.id,
            )
        except (
            DiffSummaryProjectNotFoundError,
            DiffSummaryWorkspaceNotFoundError,
            DiffSummaryChangeBatchNotFoundError,
        ) as exc:
            return RepositoryReleaseChecklistItem(
                key="diff_evidence",
                title="差异证据",
                required=True,
                status=RepositoryReleaseChecklistItemStatus.MISSING,
                summary="差异证据包不可用。",
                gap_reason=str(exc),
                checked_at=now,
            )

        if evidence_package.selected_change_batch_id != change_batch.id:
            return RepositoryReleaseChecklistItem(
                key="diff_evidence",
                title="差异证据",
                required=True,
                status=RepositoryReleaseChecklistItemStatus.MISSING,
                summary="证据包与目标变更批次不匹配。",
                gap_reason="差异证据与当前变更批次不一致。",
                checked_at=now,
            )

        changed_file_count = evidence_package.diff_summary.metrics.changed_file_count
        return RepositoryReleaseChecklistItem(
            key="diff_evidence",
            title="差异证据",
            required=True,
            status=RepositoryReleaseChecklistItemStatus.PASSED,
            summary=f"证据包可用，覆盖差异文件 {changed_file_count} 个。",
            evidence_key=evidence_package.package_key,
            checked_at=now,
        )

    def _build_commit_draft_item(
        self,
        *,
        now: datetime,
        change_batch: ChangeBatch,
        commit_candidate: CommitCandidate | None,
    ) -> RepositoryReleaseChecklistItem:
        """Evaluate Day13 commit-candidate draft readiness."""

        if commit_candidate is None or not commit_candidate.versions:
            return RepositoryReleaseChecklistItem(
                key="commit_draft",
                title="提交草案",
                required=True,
                status=RepositoryReleaseChecklistItemStatus.MISSING,
                summary="尚未生成 Day13 提交草案。",
                gap_reason="缺少提交草案，无法进入 Day14 放行审批。",
                checked_at=now,
            )

        latest_version = commit_candidate.versions[-1]
        verification_summary = latest_version.verification_summary
        if (
            verification_summary.passed_runs <= 0
            or verification_summary.failed_runs > 0
        ):
            return RepositoryReleaseChecklistItem(
                key="commit_draft",
                title="提交草案",
                required=True,
                status=RepositoryReleaseChecklistItemStatus.MISSING,
                summary="提交草案绑定的验证摘要不满足放行要求。",
                gap_reason="提交草案验证摘要不通过，需补齐后再审批。",
                checked_at=now,
            )

        if not latest_version.related_files:
            return RepositoryReleaseChecklistItem(
                key="commit_draft",
                title="提交草案",
                required=True,
                status=RepositoryReleaseChecklistItemStatus.MISSING,
                summary="提交草案缺少关联文件范围。",
                gap_reason="提交草案信息不完整，缺少关联文件。",
                checked_at=now,
            )

        return RepositoryReleaseChecklistItem(
            key="commit_draft",
            title="提交草案",
            required=True,
            status=RepositoryReleaseChecklistItemStatus.PASSED,
            summary=(
                f"草案 v{commit_candidate.current_version_number} 可审阅，"
                f"关联文件 {len(latest_version.related_files)} 个。"
            ),
            evidence_key=latest_version.evidence_package_key,
            checked_at=now,
        )

    @staticmethod
    def _resolve_snapshot_age_minutes(
        *,
        now: datetime,
        snapshot,
    ) -> int | None:
        """Return snapshot age in minutes when a valid timestamp is available."""

        if snapshot is None:
            return None

        age_delta = now - snapshot.scanned_at
        return max(0, int(age_delta.total_seconds() // 60))

    def _ensure_project_exists(self, project_id: UUID) -> None:
        """Require that the selected project exists."""

        if self.project_repository.get_by_id(project_id) is None:
            raise RepositoryReleaseGateProjectNotFoundError(
                f"Project not found: {project_id}"
            )

    def _require_change_batch(self, change_batch_id: UUID) -> ChangeBatch:
        """Require that the selected change batch exists."""

        change_batch = self.change_batch_repository.get_by_id(change_batch_id)
        if change_batch is None:
            raise RepositoryReleaseGateChangeBatchNotFoundError(
                f"Change batch not found: {change_batch_id}"
            )

        self._ensure_project_exists(change_batch.project_id)
        return change_batch

    def _load_decisions(self, *, change_batch_id: UUID) -> list[RepositoryReleaseGateDecision]:
        """Load persisted release-gate decisions for one change batch."""

        storage_path = self._resolve_decision_storage_path(change_batch_id)
        if not storage_path.exists():
            return []

        try:
            raw_payload = json.loads(storage_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

        if not isinstance(raw_payload, dict):
            return []

        raw_decisions = raw_payload.get("decisions", [])
        if not isinstance(raw_decisions, list):
            return []

        normalized_items: list[RepositoryReleaseGateDecision] = []
        for raw_decision in raw_decisions:
            if not isinstance(raw_decision, dict):
                continue
            decision = self._deserialize_decision(
                change_batch_id=change_batch_id,
                raw_value=raw_decision,
            )
            if decision is None:
                continue
            normalized_items.append(decision)

        normalized_items.sort(key=lambda item: item.created_at)
        return normalized_items

    def _save_decisions(
        self,
        *,
        change_batch_id: UUID,
        project_id: UUID,
        decisions: list[RepositoryReleaseGateDecision],
    ) -> None:
        """Persist release-gate decisions to a runtime-data JSON file."""

        storage_path = self._resolve_decision_storage_path(change_batch_id)
        storage_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "project_id": str(project_id),
            "change_batch_id": str(change_batch_id),
            "updated_at": utc_now().isoformat(),
            "decisions": [self._serialize_decision(item) for item in decisions],
        }
        storage_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _deserialize_decision(
        *,
        change_batch_id: UUID,
        raw_value: dict[str, object],
    ) -> RepositoryReleaseGateDecision | None:
        """Deserialize one stored decision row and ignore broken payloads."""

        try:
            action = ApprovalDecisionAction(str(raw_value["action"]))
            actor_name = str(raw_value["actor_name"]).strip()
            summary = str(raw_value["summary"]).strip()
            comment_raw = raw_value.get("comment")
            comment = (
                str(comment_raw).strip()
                if isinstance(comment_raw, str) and comment_raw.strip()
                else None
            )
            highlighted_risks_raw = raw_value.get("highlighted_risks") or []
            requested_changes_raw = raw_value.get("requested_changes") or []
            created_at_raw = str(raw_value["created_at"])
            created_at = ensure_utc_datetime(datetime.fromisoformat(created_at_raw))
            if created_at is None:
                return None

            decision_id = UUID(str(raw_value["id"]))
        except (KeyError, TypeError, ValueError):
            return None

        if not actor_name or not summary:
            return None

        highlighted_risks = RepositoryReleaseGateService._normalize_string_list(
            highlighted_risks_raw if isinstance(highlighted_risks_raw, list) else [],
            max_length=20,
        )
        requested_changes = RepositoryReleaseGateService._normalize_string_list(
            requested_changes_raw if isinstance(requested_changes_raw, list) else [],
            max_length=20,
        )
        return RepositoryReleaseGateDecision(
            id=decision_id,
            change_batch_id=change_batch_id,
            action=action,
            actor_name=actor_name,
            summary=summary,
            comment=comment,
            highlighted_risks=highlighted_risks,
            requested_changes=requested_changes,
            created_at=created_at,
        )

    @staticmethod
    def _serialize_decision(
        decision: RepositoryReleaseGateDecision,
    ) -> dict[str, object]:
        """Serialize one decision into JSON-compatible payload."""

        return {
            "id": str(decision.id),
            "change_batch_id": str(decision.change_batch_id),
            "action": decision.action.value,
            "actor_name": decision.actor_name,
            "summary": decision.summary,
            "comment": decision.comment,
            "highlighted_risks": list(decision.highlighted_risks),
            "requested_changes": list(decision.requested_changes),
            "created_at": decision.created_at.isoformat(),
        }

    @staticmethod
    def _normalize_required_text(
        value: str,
        *,
        field_name: str,
        max_length: int,
    ) -> str:
        """Normalize one required text field and raise stable Day14 errors."""

        normalized_value = value.strip()
        if not normalized_value:
            raise RepositoryReleaseGateActionValidationError(
                f"{field_name} cannot be blank."
            )
        if len(normalized_value) > max_length:
            raise RepositoryReleaseGateActionValidationError(
                f"{field_name} cannot exceed {max_length} characters."
            )

        return normalized_value

    @staticmethod
    def _normalize_optional_text(value: str | None, *, max_length: int) -> str | None:
        """Normalize one optional text field."""

        if value is None:
            return None

        normalized_value = value.strip()
        if not normalized_value:
            return None
        if len(normalized_value) > max_length:
            raise RepositoryReleaseGateActionValidationError(
                f"comment cannot exceed {max_length} characters."
            )

        return normalized_value

    @staticmethod
    def _normalize_string_list(values: list[str], *, max_length: int) -> list[str]:
        """Normalize one structured string list."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for raw_item in values:
            item = str(raw_item).strip()
            if not item or item in seen_items:
                continue
            if len(item) > 500:
                raise RepositoryReleaseGateActionValidationError(
                    "Structured list items cannot exceed 500 characters."
                )
            normalized_items.append(item)
            seen_items.add(item)
            if len(normalized_items) >= max_length:
                break

        return normalized_items

    @staticmethod
    def _resolve_decision_storage_path(change_batch_id: UUID) -> Path:
        """Resolve one change-batch decision-storage file path."""

        return (
            settings.runtime_data_dir
            / RELEASE_GATE_DECISION_DIR_NAME
            / f"{change_batch_id}.json"
        )
