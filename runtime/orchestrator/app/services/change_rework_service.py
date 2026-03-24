"""Day12 change-rework aggregation service for V4 repository closure."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain._base import utc_now
from app.domain.approval import ApprovalDecisionAction, ApprovalStatus
from app.domain.change_batch import (
    ChangeBatch,
    ChangeBatchManualConfirmationAction,
    ChangeBatchManualConfirmationDecision,
    ChangeBatchManualConfirmationStatus,
    ChangeBatchPreflightStatus,
)
from app.domain.verification_run import VerificationRun, VerificationRunFailureCategory
from app.repositories.change_batch_repository import ChangeBatchRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.verification_run_repository import VerificationRunRepository
from app.services.approval_service import ApprovalReworkCycle, ApprovalService
from app.services.decision_replay_service import (
    DecisionReplayService,
    ProjectFailureRetrospectiveItem,
)
from app.services.diff_summary_service import DiffSummaryError, DiffSummaryService


@dataclass(slots=True, frozen=True)
class ChangeReworkChainStep:
    """One traceable node in the Day12 rework chain."""

    step_id: str
    stage: str
    label: str
    summary: str
    occurred_at: datetime
    metadata: dict[str, Any]


@dataclass(slots=True, frozen=True)
class ChangeReworkItem:
    """One consolidated Day12 rework item with chain references."""

    rework_id: str
    project_id: UUID
    chain_source: str
    status: str
    recommendation: str
    closed: bool
    occurred_at: datetime
    change_batch_id: UUID | None
    change_batch_title: str | None
    evidence_package_key: str | None
    deliverable_id: UUID | None
    deliverable_title: str | None
    approval_id: UUID | None
    approval_status: ApprovalStatus | None
    decision_action: ApprovalDecisionAction | None
    reason_summary: str
    reason_comment: str | None
    requested_changes: list[str]
    highlighted_risks: list[str]
    latest_failure_category: str | None
    verification_total_runs: int
    verification_failed_runs: int
    linked_task_ids: list[UUID]
    linked_run_ids: list[UUID]
    steps: list[ChangeReworkChainStep]


@dataclass(slots=True, frozen=True)
class ProjectChangeReworkSummary:
    """Top-level counters for the Day12 change-rework panel."""

    total_items: int
    approval_rework_items: int
    verification_rework_items: int
    rollback_recommendations: int
    replan_recommendations: int
    open_items: int
    closed_items: int


@dataclass(slots=True, frozen=True)
class ProjectChangeReworkSnapshot:
    """Project-scoped Day12 rework payload."""

    project_id: UUID
    generated_at: datetime
    summary: ProjectChangeReworkSummary
    items: list[ChangeReworkItem]


@dataclass(slots=True, frozen=True)
class _VerificationBatchSummary:
    """Derived verification-run counters for one change batch."""

    total_runs: int
    failed_runs: int
    latest_finished_at: datetime | None
    latest_failure_run_id: UUID | None
    latest_failure_category: VerificationRunFailureCategory | None
    latest_failure_summary: str | None
    failed_run_ids: list[UUID]


class ChangeReworkService:
    """Aggregate plan -> verification -> failure/reject -> rework closures."""

    def __init__(
        self,
        *,
        project_repository: ProjectRepository,
        change_batch_repository: ChangeBatchRepository,
        verification_run_repository: VerificationRunRepository,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        approval_service: ApprovalService,
        decision_replay_service: DecisionReplayService,
        diff_summary_service: DiffSummaryService,
    ) -> None:
        self.project_repository = project_repository
        self.change_batch_repository = change_batch_repository
        self.verification_run_repository = verification_run_repository
        self.task_repository = task_repository
        self.run_repository = run_repository
        self.approval_service = approval_service
        self.decision_replay_service = decision_replay_service
        self.diff_summary_service = diff_summary_service

    def get_project_change_rework_snapshot(
        self,
        project_id: UUID,
    ) -> ProjectChangeReworkSnapshot | None:
        """Return Day12 project rework closure data or `None` if project is missing."""

        if self.project_repository.get_by_id(project_id) is None:
            return None

        batches = sorted(
            self.change_batch_repository.list_by_project_id(project_id),
            key=lambda item: (item.updated_at, item.created_at, str(item.id)),
            reverse=True,
        )
        batch_run_map = self._build_batch_run_map(project_id=project_id)

        tasks = self.task_repository.list_by_project_id(project_id)
        task_title_map = {task.id: task.title for task in tasks}
        runs = self.run_repository.list_by_task_ids(list(task_title_map))
        failure_map = self.decision_replay_service.index_project_failures_by_task(
            runs=runs,
            task_titles=task_title_map,
            limit_per_task=3,
        )

        rework_items: list[ChangeReworkItem] = []
        evidence_key_cache: dict[UUID, str | None] = {}
        linked_batch_ids: set[UUID] = set()

        for cycle in self.approval_service.list_project_rework_cycles(project_id) or []:
            related_batch = self._resolve_related_batch_for_cycle(
                cycle=cycle,
                batches=batches,
            )
            if related_batch is not None:
                linked_batch_ids.add(related_batch.id)

            verification_summary = self._build_verification_summary(
                batch_run_map.get(related_batch.id, []) if related_batch is not None else []
            )
            failure_refs = (
                self._collect_failure_refs_for_batch(
                    change_batch=related_batch,
                    failure_map=failure_map,
                )
                if related_batch is not None
                else []
            )
            recommendation = self._resolve_cycle_recommendation(
                cycle=cycle,
                related_batch=related_batch,
                verification_summary=verification_summary,
            )
            rework_items.append(
                ChangeReworkItem(
                    rework_id=f"approval-cycle:{cycle.cycle_id}",
                    project_id=project_id,
                    chain_source="approval_rework",
                    status=cycle.status,
                    recommendation=recommendation,
                    closed=cycle.status == "approved_after_rework",
                    occurred_at=cycle.resubmitted_at or cycle.decided_at,
                    change_batch_id=related_batch.id if related_batch is not None else None,
                    change_batch_title=(
                        related_batch.title if related_batch is not None else None
                    ),
                    evidence_package_key=self._resolve_evidence_package_key(
                        project_id=project_id,
                        change_batch=related_batch,
                        cache=evidence_key_cache,
                    ),
                    deliverable_id=cycle.deliverable_id,
                    deliverable_title=cycle.deliverable_title,
                    approval_id=cycle.approval_id,
                    approval_status=cycle.latest_approval_status,
                    decision_action=cycle.decision_action,
                    reason_summary=cycle.summary,
                    reason_comment=cycle.comment,
                    requested_changes=list(cycle.requested_changes),
                    highlighted_risks=list(cycle.highlighted_risks),
                    latest_failure_category=self._resolve_latest_failure_category(
                        verification_summary=verification_summary,
                        failure_refs=failure_refs,
                    ),
                    verification_total_runs=verification_summary.total_runs,
                    verification_failed_runs=verification_summary.failed_runs,
                    linked_task_ids=self._collect_task_ids(related_batch),
                    linked_run_ids=self._collect_linked_run_ids(
                        verification_summary=verification_summary,
                        failure_refs=failure_refs,
                    ),
                    steps=self._build_steps_for_cycle(
                        cycle=cycle,
                        related_batch=related_batch,
                        verification_summary=verification_summary,
                        failure_refs=failure_refs,
                    ),
                )
            )

        for change_batch in batches:
            if change_batch.id in linked_batch_ids:
                continue

            verification_summary = self._build_verification_summary(
                batch_run_map.get(change_batch.id, [])
            )
            manual_decision = self._get_latest_manual_decision(change_batch)
            manual_rejected = self._is_manual_rejected_batch(change_batch)
            has_verification_failure = verification_summary.failed_runs > 0

            if not manual_rejected and not has_verification_failure:
                continue

            failure_refs = self._collect_failure_refs_for_batch(
                change_batch=change_batch,
                failure_map=failure_map,
            )
            recommendation = self._resolve_batch_recommendation(
                manual_rejected=manual_rejected,
                verification_summary=verification_summary,
            )
            status = "manual_rejected" if manual_rejected else "verification_failed"
            reason_summary = self._resolve_batch_reason_summary(
                change_batch=change_batch,
                verification_summary=verification_summary,
                manual_decision=manual_decision,
            )
            reason_comment = (
                manual_decision.comment if manual_decision is not None else None
            )
            highlighted_risks = (
                list(manual_decision.highlighted_risks)
                if manual_decision is not None
                else []
            )

            primary_deliverable_id, primary_deliverable_title = (
                self._resolve_primary_deliverable(change_batch)
            )
            occurred_at = (
                manual_decision.created_at
                if manual_decision is not None
                else (verification_summary.latest_finished_at or change_batch.updated_at)
            )
            rework_items.append(
                ChangeReworkItem(
                    rework_id=f"batch-rework:{change_batch.id}",
                    project_id=project_id,
                    chain_source="verification_rework",
                    status=status,
                    recommendation=recommendation,
                    closed=False,
                    occurred_at=occurred_at,
                    change_batch_id=change_batch.id,
                    change_batch_title=change_batch.title,
                    evidence_package_key=self._resolve_evidence_package_key(
                        project_id=project_id,
                        change_batch=change_batch,
                        cache=evidence_key_cache,
                    ),
                    deliverable_id=primary_deliverable_id,
                    deliverable_title=primary_deliverable_title,
                    approval_id=None,
                    approval_status=None,
                    decision_action=None,
                    reason_summary=reason_summary,
                    reason_comment=reason_comment,
                    requested_changes=[],
                    highlighted_risks=highlighted_risks,
                    latest_failure_category=self._resolve_latest_failure_category(
                        verification_summary=verification_summary,
                        failure_refs=failure_refs,
                    ),
                    verification_total_runs=verification_summary.total_runs,
                    verification_failed_runs=verification_summary.failed_runs,
                    linked_task_ids=self._collect_task_ids(change_batch),
                    linked_run_ids=self._collect_linked_run_ids(
                        verification_summary=verification_summary,
                        failure_refs=failure_refs,
                    ),
                    steps=self._build_steps_for_batch_issue(
                        change_batch=change_batch,
                        verification_summary=verification_summary,
                        failure_refs=failure_refs,
                        manual_decision=manual_decision,
                        status=status,
                        recommendation=recommendation,
                    ),
                )
            )

        rework_items.sort(
            key=lambda item: (item.occurred_at, item.rework_id),
            reverse=True,
        )
        return ProjectChangeReworkSnapshot(
            project_id=project_id,
            generated_at=utc_now(),
            summary=self._build_summary(rework_items),
            items=rework_items,
        )

    def _build_batch_run_map(self, *, project_id: UUID) -> dict[UUID, list[VerificationRun]]:
        """Group project verification runs by change_batch_id."""

        grouped_runs: dict[UUID, list[VerificationRun]] = {}
        for run in self.verification_run_repository.list_by_project_id(
            project_id,
            limit=None,
        ):
            grouped_runs.setdefault(run.change_batch_id, []).append(run)
        return grouped_runs

    @staticmethod
    def _build_verification_summary(
        runs: list[VerificationRun],
    ) -> _VerificationBatchSummary:
        """Build one compact verification summary for a change batch."""

        if not runs:
            return _VerificationBatchSummary(
                total_runs=0,
                failed_runs=0,
                latest_finished_at=None,
                latest_failure_run_id=None,
                latest_failure_category=None,
                latest_failure_summary=None,
                failed_run_ids=[],
            )

        ordered_runs = sorted(
            runs,
            key=lambda item: (item.finished_at, item.created_at, str(item.id)),
            reverse=True,
        )
        failed_runs = [item for item in ordered_runs if item.status.value != "passed"]
        latest_failure = failed_runs[0] if failed_runs else None
        return _VerificationBatchSummary(
            total_runs=len(ordered_runs),
            failed_runs=len(failed_runs),
            latest_finished_at=ordered_runs[0].finished_at,
            latest_failure_run_id=(
                latest_failure.id if latest_failure is not None else None
            ),
            latest_failure_category=(
                latest_failure.failure_category if latest_failure is not None else None
            ),
            latest_failure_summary=(
                latest_failure.output_summary if latest_failure is not None else None
            ),
            failed_run_ids=[item.id for item in failed_runs],
        )

    @staticmethod
    def _resolve_related_batch_for_cycle(
        *,
        cycle: ApprovalReworkCycle,
        batches: list[ChangeBatch],
    ) -> ChangeBatch | None:
        """Best-effort mapping from one approval cycle to its originating change batch."""

        matching_batches = [
            batch
            for batch in batches
            if any(
                linked.deliverable_id == cycle.deliverable_id
                for snapshot in batch.plan_snapshots
                for linked in snapshot.related_deliverables
            )
        ]
        return matching_batches[0] if matching_batches else None

    @staticmethod
    def _collect_task_ids(change_batch: ChangeBatch | None) -> list[UUID]:
        """Collect unique task IDs from one change batch snapshot."""

        if change_batch is None:
            return []

        task_ids: list[UUID] = []
        seen_task_ids: set[UUID] = set()
        for snapshot in change_batch.plan_snapshots:
            if snapshot.task_id in seen_task_ids:
                continue
            task_ids.append(snapshot.task_id)
            seen_task_ids.add(snapshot.task_id)
        return task_ids

    @staticmethod
    def _collect_failure_refs_for_batch(
        *,
        change_batch: ChangeBatch,
        failure_map: dict[UUID, list[ProjectFailureRetrospectiveItem]],
    ) -> list[ProjectFailureRetrospectiveItem]:
        """Collect task-matched execution failures for one change batch."""

        collected_items: list[ProjectFailureRetrospectiveItem] = []
        seen_run_ids: set[UUID] = set()
        for task_id in ChangeReworkService._collect_task_ids(change_batch):
            for item in failure_map.get(task_id, []):
                if item.run_id in seen_run_ids:
                    continue
                collected_items.append(item)
                seen_run_ids.add(item.run_id)

        collected_items.sort(
            key=lambda item: (item.created_at, str(item.run_id)),
            reverse=True,
        )
        return collected_items

    def _resolve_evidence_package_key(
        self,
        *,
        project_id: UUID,
        change_batch: ChangeBatch | None,
        cache: dict[UUID, str | None],
    ) -> str | None:
        """Resolve and cache Day11 evidence package keys by change batch."""

        if change_batch is None:
            return None
        if change_batch.id in cache:
            return cache[change_batch.id]

        try:
            package = self.diff_summary_service.get_project_change_evidence(
                project_id,
                change_batch_id=change_batch.id,
            )
            cache[change_batch.id] = package.package_key
        except DiffSummaryError:
            cache[change_batch.id] = None

        return cache[change_batch.id]

    def _resolve_cycle_recommendation(
        self,
        *,
        cycle: ApprovalReworkCycle,
        related_batch: ChangeBatch | None,
        verification_summary: _VerificationBatchSummary,
    ) -> str:
        """Map one approval cycle into a stable Day12 recommendation."""

        if related_batch is not None and self._is_manual_rejected_batch(related_batch):
            return "rollback"
        if (
            verification_summary.failed_runs >= 2
            and cycle.decision_action == ApprovalDecisionAction.REJECT
        ):
            return "replan"
        if verification_summary.failed_runs >= 3:
            return "replan"
        return "rework"

    @staticmethod
    def _resolve_batch_recommendation(
        *,
        manual_rejected: bool,
        verification_summary: _VerificationBatchSummary,
    ) -> str:
        """Map one verification-side issue into Day12 recommendation text."""

        if manual_rejected:
            return "rollback"
        if verification_summary.failed_runs >= 2:
            return "replan"
        return "rework"

    @staticmethod
    def _resolve_latest_failure_category(
        *,
        verification_summary: _VerificationBatchSummary,
        failure_refs: list[ProjectFailureRetrospectiveItem],
    ) -> str | None:
        """Resolve one stable latest-failure category value."""

        if verification_summary.latest_failure_category is not None:
            return verification_summary.latest_failure_category.value
        if failure_refs and failure_refs[0].failure_category is not None:
            return failure_refs[0].failure_category.value
        return None

    @staticmethod
    def _collect_linked_run_ids(
        *,
        verification_summary: _VerificationBatchSummary,
        failure_refs: list[ProjectFailureRetrospectiveItem],
    ) -> list[UUID]:
        """Merge verification and execution failure run IDs."""

        linked_run_ids: list[UUID] = []
        seen_run_ids: set[UUID] = set()

        for run_id in verification_summary.failed_run_ids:
            if run_id in seen_run_ids:
                continue
            linked_run_ids.append(run_id)
            seen_run_ids.add(run_id)

        for item in failure_refs:
            if item.run_id in seen_run_ids:
                continue
            linked_run_ids.append(item.run_id)
            seen_run_ids.add(item.run_id)

        return linked_run_ids

    def _build_steps_for_cycle(
        self,
        *,
        cycle: ApprovalReworkCycle,
        related_batch: ChangeBatch | None,
        verification_summary: _VerificationBatchSummary,
        failure_refs: list[ProjectFailureRetrospectiveItem],
    ) -> list[ChangeReworkChainStep]:
        """Build one ordered chain for an approval-driven rework item."""

        steps: list[ChangeReworkChainStep] = []
        if related_batch is not None:
            steps.append(
                ChangeReworkChainStep(
                    step_id=f"plan:{related_batch.id}",
                    stage="plan",
                    label="变更计划",
                    summary=(
                        f"批次《{related_batch.title}》已冻结 "
                        f"{len(related_batch.plan_snapshots)} 条变更计划。"
                    ),
                    occurred_at=related_batch.created_at,
                    metadata={
                        "change_batch_id": str(related_batch.id),
                        "plan_count": len(related_batch.plan_snapshots),
                    },
                )
            )

        if verification_summary.total_runs > 0:
            steps.append(
                ChangeReworkChainStep(
                    step_id=f"verification:{cycle.cycle_id}",
                    stage="verification",
                    label="验证结果",
                    summary=(
                        f"共执行 {verification_summary.total_runs} 次验证，"
                        f"未通过 {verification_summary.failed_runs} 次。"
                    ),
                    occurred_at=(
                        verification_summary.latest_finished_at or cycle.decided_at
                    ),
                    metadata={
                        "total_runs": verification_summary.total_runs,
                        "failed_runs": verification_summary.failed_runs,
                        "latest_failure_category": (
                            verification_summary.latest_failure_category.value
                            if verification_summary.latest_failure_category is not None
                            else None
                        ),
                    },
                )
            )

        if failure_refs:
            latest_failure = failure_refs[0]
            steps.append(
                ChangeReworkChainStep(
                    step_id=f"failure:{latest_failure.run_id}",
                    stage="failure",
                    label="失败复盘",
                    summary=latest_failure.headline,
                    occurred_at=latest_failure.created_at,
                    metadata={
                        "run_id": str(latest_failure.run_id),
                        "task_id": str(latest_failure.task_id),
                        "failure_category": (
                            latest_failure.failure_category.value
                            if latest_failure.failure_category is not None
                            else None
                        ),
                    },
                )
            )

        steps.append(
            ChangeReworkChainStep(
                step_id=f"approval:{cycle.approval_id}",
                stage="decision",
                label="审批结论",
                summary=cycle.summary,
                occurred_at=cycle.decided_at,
                metadata={
                    "approval_id": str(cycle.approval_id),
                    "decision_action": cycle.decision_action.value,
                    "status": cycle.status,
                },
            )
        )
        steps.append(
            ChangeReworkChainStep(
                step_id=f"rework:{cycle.cycle_id}",
                stage="rework",
                label="回退重做",
                summary=self._build_rework_step_summary(cycle.status),
                occurred_at=cycle.resubmitted_at or cycle.decided_at,
                metadata={
                    "status": cycle.status,
                    "resubmitted_version_number": cycle.resubmitted_version_number,
                    "latest_approval_id": (
                        str(cycle.latest_approval_id)
                        if cycle.latest_approval_id is not None
                        else None
                    ),
                },
            )
        )

        steps.sort(key=lambda item: (item.occurred_at, item.step_id))
        return steps

    def _build_steps_for_batch_issue(
        self,
        *,
        change_batch: ChangeBatch,
        verification_summary: _VerificationBatchSummary,
        failure_refs: list[ProjectFailureRetrospectiveItem],
        manual_decision: ChangeBatchManualConfirmationDecision | None,
        status: str,
        recommendation: str,
    ) -> list[ChangeReworkChainStep]:
        """Build one ordered chain for verification/manual-reject rework items."""

        steps: list[ChangeReworkChainStep] = [
            ChangeReworkChainStep(
                step_id=f"plan:{change_batch.id}",
                stage="plan",
                label="变更计划",
                summary=(
                    f"批次《{change_batch.title}》已冻结 "
                    f"{len(change_batch.plan_snapshots)} 条变更计划。"
                ),
                occurred_at=change_batch.created_at,
                metadata={
                    "change_batch_id": str(change_batch.id),
                    "plan_count": len(change_batch.plan_snapshots),
                },
            )
        ]

        if verification_summary.total_runs > 0:
            steps.append(
                ChangeReworkChainStep(
                    step_id=f"verification:{change_batch.id}",
                    stage="verification",
                    label="验证结果",
                    summary=(
                        f"共执行 {verification_summary.total_runs} 次验证，"
                        f"未通过 {verification_summary.failed_runs} 次。"
                    ),
                    occurred_at=(
                        verification_summary.latest_finished_at
                        or change_batch.updated_at
                    ),
                    metadata={
                        "total_runs": verification_summary.total_runs,
                        "failed_runs": verification_summary.failed_runs,
                        "latest_failure_category": (
                            verification_summary.latest_failure_category.value
                            if verification_summary.latest_failure_category is not None
                            else None
                        ),
                    },
                )
            )

        if manual_decision is not None:
            steps.append(
                ChangeReworkChainStep(
                    step_id=f"manual-decision:{change_batch.id}",
                    stage="decision",
                    label="人工闸门结论",
                    summary=manual_decision.summary,
                    occurred_at=manual_decision.created_at,
                    metadata={
                        "action": manual_decision.action.value,
                        "actor_name": manual_decision.actor_name,
                    },
                )
            )

        if failure_refs:
            latest_failure = failure_refs[0]
            steps.append(
                ChangeReworkChainStep(
                    step_id=f"failure:{latest_failure.run_id}",
                    stage="failure",
                    label="失败复盘",
                    summary=latest_failure.headline,
                    occurred_at=latest_failure.created_at,
                    metadata={
                        "run_id": str(latest_failure.run_id),
                        "task_id": str(latest_failure.task_id),
                        "failure_category": (
                            latest_failure.failure_category.value
                            if latest_failure.failure_category is not None
                            else None
                        ),
                    },
                )
            )

        latest_occurred_at = max(
            (item.occurred_at for item in steps),
            default=change_batch.updated_at,
        )
        steps.append(
            ChangeReworkChainStep(
                step_id=f"rework:{change_batch.id}",
                stage="rework",
                label="回退重做",
                summary=self._build_batch_rework_step_summary(
                    status=status,
                    recommendation=recommendation,
                ),
                occurred_at=latest_occurred_at,
                metadata={
                    "status": status,
                    "recommendation": recommendation,
                },
            )
        )

        steps.sort(key=lambda item: (item.occurred_at, item.step_id))
        return steps

    @staticmethod
    def _build_rework_step_summary(status: str) -> str:
        """Render one concise cycle-status summary for UI display."""

        if status == "approved_after_rework":
            return "重做后的版本已通过审批并完成收口。"
        if status == "resubmitted_pending_approval":
            return "已重提审批，等待最新审批结论。"
        if status == "reworking":
            return "已进入重做中，等待完成后重新送审。"
        return "当前仍需回退重做，禁止直接覆盖原记录。"

    @staticmethod
    def _build_batch_rework_step_summary(*, status: str, recommendation: str) -> str:
        """Render one concise verification-side rework summary for UI display."""

        if status == "manual_rejected":
            return "人工闸门已驳回当前批次，需要先回退再重做。"
        if recommendation == "replan":
            return "连续验证未通过，建议重新规划后再执行。"
        return "验证未通过，需按失败归因回退重做。"

    @staticmethod
    def _get_latest_manual_decision(
        change_batch: ChangeBatch,
    ) -> ChangeBatchManualConfirmationDecision | None:
        """Return latest manual confirmation decision if present."""

        if not change_batch.preflight.decision_history:
            return None
        return change_batch.preflight.decision_history[-1]

    def _is_manual_rejected_batch(self, change_batch: ChangeBatch) -> bool:
        """Return whether one change batch has been manually rejected."""

        latest_decision = self._get_latest_manual_decision(change_batch)
        if (
            latest_decision is not None
            and latest_decision.action == ChangeBatchManualConfirmationAction.REJECT
        ):
            return True
        return (
            change_batch.preflight.status == ChangeBatchPreflightStatus.MANUAL_REJECTED
            or change_batch.preflight.manual_confirmation_status
            == ChangeBatchManualConfirmationStatus.REJECTED
        )

    @staticmethod
    def _resolve_batch_reason_summary(
        *,
        change_batch: ChangeBatch,
        verification_summary: _VerificationBatchSummary,
        manual_decision: ChangeBatchManualConfirmationDecision | None,
    ) -> str:
        """Resolve one stable reason summary for verification-side rework items."""

        if manual_decision is not None:
            return manual_decision.summary
        if verification_summary.latest_failure_summary:
            return verification_summary.latest_failure_summary
        if change_batch.preflight.summary:
            return change_batch.preflight.summary
        return "验证失败后已进入回退重做路径。"

    @staticmethod
    def _resolve_primary_deliverable(
        change_batch: ChangeBatch,
    ) -> tuple[UUID | None, str | None]:
        """Pick one representative deliverable from batch snapshots."""

        for snapshot in change_batch.plan_snapshots:
            if snapshot.related_deliverables:
                deliverable = snapshot.related_deliverables[0]
                return deliverable.deliverable_id, deliverable.title
        return None, None

    @staticmethod
    def _build_summary(items: list[ChangeReworkItem]) -> ProjectChangeReworkSummary:
        """Build stable Day12 top-level counters."""

        total_items = len(items)
        approval_rework_items = sum(
            1 for item in items if item.chain_source == "approval_rework"
        )
        verification_rework_items = total_items - approval_rework_items
        rollback_recommendations = sum(
            1 for item in items if item.recommendation == "rollback"
        )
        replan_recommendations = sum(
            1 for item in items if item.recommendation == "replan"
        )
        closed_items = sum(1 for item in items if item.closed)
        open_items = total_items - closed_items
        return ProjectChangeReworkSummary(
            total_items=total_items,
            approval_rework_items=approval_rework_items,
            verification_rework_items=verification_rework_items,
            rollback_recommendations=rollback_recommendations,
            replan_recommendations=replan_recommendations,
            open_items=open_items,
            closed_items=closed_items,
        )
