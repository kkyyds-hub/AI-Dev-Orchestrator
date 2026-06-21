"""Repository workspace, snapshot, verification baseline and change-batch endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.api.schemas.repository_change_batch import (
    ChangeBatchCreateRequest,
    ChangeBatchDetailResponse,
    ChangeBatchPreflightRequest,
    ChangeBatchSummaryResponse,
)
from app.api.schemas.repository_change_session import ChangeSessionResponse
from app.api.schemas.repository_code_context import (
    CodeContextPackBuildRequest,
    FileLocatorSearchRequest,
)
from app.api.schemas.repository_commit_candidate import (
    CommitCandidateDetailResponse,
    CommitCandidateDraftUpsertRequest,
    CommitCandidateSummaryResponse,
)
from app.api.schemas.repository_git_write import (
    ApplyLocalRequest,
    ApplyLocalResponse,
    GitCommitResponse,
)
from app.api.schemas.repository_release_gate import (
    ProjectRepositoryReleaseGateInboxResponse,
    RepositoryDay15FlowResponse,
    RepositoryDay15FlowStatus,
    RepositoryDay15FlowStepResponse,
    RepositoryDay15FlowStepStatus,
    RepositoryDraftChainReadbackResponse,
    RepositoryReleaseGateDetailResponse,
)
from app.api.schemas.repository_verification import (
    RepositoryVerificationBaselineResponse,
    RepositoryVerificationBaselineUpsertRequest,
)
from app.api.schemas.repository_snapshot import RepositorySnapshotResponse
from app.api.schemas.repository_workspace import (
    RepositoryWorkspaceBindRequest,
    RepositoryWorkspaceResponse,
    RepositoryWorkspaceSettingsResponse,
    RepositoryWorkspaceSettingsUpdateRequest,
)
from app.domain._base import utc_now
from app.domain.change_batch import (
    ChangeBatchPreflightStatus,
)
from app.domain.commit_candidate import (
    CommitCandidate,
)
from app.domain.code_context_pack import CodeContextPack, FileLocatorResult
from app.domain.repository_snapshot import (
    RepositorySnapshotStatus,
)
from app.repositories.change_batch_repository import ChangeBatchRepository
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.change_session_repository import ChangeSessionRepository
from app.repositories.change_plan_repository import ChangePlanRepository
from app.repositories.commit_candidate_repository import CommitCandidateRepository
from app.repositories.deliverable_repository import DeliverableRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.run_repository import RunRepository
from app.repositories.repository_snapshot_repository import (
    RepositorySnapshotRepository,
)
from app.repositories.repository_verification_repository import (
    RepositoryVerificationRepository,
)
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)
from app.repositories.task_repository import TaskRepository
from app.repositories.verification_run_repository import VerificationRunRepository
from app.services.change_batch_service import (
    ChangeBatchActiveConflictError,
    ChangeBatchDeliverableNotFoundError,
    ChangeBatchNotFoundError,
    ChangeBatchPlanNotFoundError,
    ChangeBatchPlanTaskConflictError,
    ChangeBatchProjectNotFoundError,
    ChangeBatchService,
    ChangeBatchWorkspaceNotFoundError,
)
from app.services.commit_candidate_service import (
    CommitCandidateBatchNotFoundError,
    CommitCandidateEvidenceUnavailableError,
    CommitCandidateNotFoundError,
    CommitCandidatePreflightNotReadyError,
    CommitCandidateProjectNotFoundError,
    CommitCandidateService,
    CommitCandidateVerificationNotPassedError,
)
from app.services.change_risk_guard_service import (
    ChangeRiskGuardBatchNotFoundError,
    ChangeRiskGuardProjectNotFoundError,
    ChangeRiskGuardService,
)
from app.services.branch_session_service import (
    BranchSessionInspectionError,
    BranchSessionProjectNotFoundError,
    BranchSessionService,
    BranchSessionWorkspaceNotFoundError,
)
from app.services.codebase_locator_service import (
    CodebaseLocatorProjectNotFoundError,
    CodebaseLocatorRequestError,
    CodebaseLocatorService,
    CodebaseLocatorTaskNotFoundError,
    CodebaseLocatorWorkspaceNotFoundError,
)
from app.services.context_builder_service import (
    CodeContextBuildError,
    ContextBuilderService,
)
from app.services.repository_scan_service import (
    RepositoryScanProjectNotFoundError,
    RepositoryScanService,
    RepositoryScanWorkspaceNotFoundError,
)
from app.services.diff_summary_service import DiffSummaryService
from app.services.repository_verification_service import (
    RepositoryVerificationProjectNotFoundError,
    RepositoryVerificationService,
    RepositoryVerificationTemplateConfigError,
    RepositoryVerificationWorkspaceNotFoundError,
)
from app.services.repository_workspace_service import (
    RepositoryWorkspaceNotFoundError,
    RepositoryWorkspacePathError,
    RepositoryWorkspaceProjectNotFoundError,
    RepositoryWorkspaceService,
)
from app.services.repository_workspace_settings_service import (
    RepositoryWorkspaceSettingsError,
    RepositoryWorkspaceSettingsService,
)
from app.services.repository_release_gate_service import (
    RepositoryReleaseChecklistItem,
    RepositoryReleaseChecklistItemStatus,
    RepositoryReleaseGate,
    RepositoryReleaseGateChangeBatchNotFoundError,
    RepositoryReleaseGateProjectNotFoundError,
    RepositoryReleaseGateService,
    RepositoryReleaseGateStatus,
)
from app.services.task_readiness_service import TaskReadinessService
from app.services.local_git_write_service import (
    LocalGitWriteError,
    LocalGitWriteService,
)
from app.services.git_write_state_tracker import get_git_write_action_summary


def build_repository_day15_flow_snapshot(
    *,
    project_id: UUID,
    project_repository: ProjectRepository,
    change_plan_repository: ChangePlanRepository,
    change_batch_repository: ChangeBatchRepository,
    repository_release_gate_service: RepositoryReleaseGateService,
) -> RepositoryDay15FlowResponse:
    """Aggregate Day01-Day14 state into one read-only Day15 flow snapshot."""

    project = project_repository.get_by_id(project_id)
    if project is None:
        raise RepositoryReleaseGateProjectNotFoundError(f"Project not found: {project_id}")

    change_plan_count = len(change_plan_repository.list_records_by_project_id(project_id))
    change_batches = change_batch_repository.list_by_project_id(project_id)
    selected_change_batch = change_batch_repository.get_active_by_project_id(
        project_id
    ) or next(iter(change_batches), None)

    selected_gate: RepositoryReleaseGate | None = None
    checklist_by_key: dict[str, RepositoryReleaseChecklistItem] = {}
    if selected_change_batch is not None:
        selected_gate = repository_release_gate_service.get_release_gate(
            selected_change_batch.id
        )
        checklist_by_key = {
            item.key: item for item in selected_gate.checklist_items
        }

    def _step_from_checklist(
        *,
        key: str,
        title: str,
        pending_summary: str,
    ) -> RepositoryDay15FlowStepResponse:
        item = checklist_by_key.get(key)
        if item is None:
            return RepositoryDay15FlowStepResponse(
                key=key,
                title=title,
                status=RepositoryDay15FlowStepStatus.PENDING,
                summary=pending_summary,
            )

        if item.status == RepositoryReleaseChecklistItemStatus.PASSED:
            return RepositoryDay15FlowStepResponse(
                key=key,
                title=title,
                status=RepositoryDay15FlowStepStatus.COMPLETED,
                summary=item.summary,
                evidence_key=item.evidence_key,
            )

        return RepositoryDay15FlowStepResponse(
            key=key,
            title=title,
            status=RepositoryDay15FlowStepStatus.BLOCKED,
            summary=item.gap_reason or item.summary,
            evidence_key=item.evidence_key,
        )

    if selected_gate is not None:
        repository_binding_step = _step_from_checklist(
            key="repository_binding",
            title="绑定仓库",
            pending_summary="尚未收集仓库绑定状态。",
        )
    elif project.repository_workspace is not None:
        repository_binding_step = RepositoryDay15FlowStepResponse(
            key="repository_binding",
            title="绑定仓库",
            status=RepositoryDay15FlowStepStatus.COMPLETED,
            summary=(
                "已绑定本地仓库："
                f"{project.repository_workspace.display_name}"
            ),
        )
    else:
        repository_binding_step = RepositoryDay15FlowStepResponse(
            key="repository_binding",
            title="绑定仓库",
            status=RepositoryDay15FlowStepStatus.BLOCKED,
            summary="尚未绑定本地仓库，闭环链路无法推进。",
        )

    if selected_gate is not None:
        snapshot_step = _step_from_checklist(
            key="snapshot_freshness",
            title="刷新快照",
            pending_summary="尚未收集快照状态。",
        )
    elif project.repository_workspace is None:
        snapshot_step = RepositoryDay15FlowStepResponse(
            key="snapshot_freshness",
            title="刷新快照",
            status=RepositoryDay15FlowStepStatus.BLOCKED,
            summary="未绑定仓库，无法生成快照。",
        )
    elif project.latest_repository_snapshot is None:
        snapshot_step = RepositoryDay15FlowStepResponse(
            key="snapshot_freshness",
            title="刷新快照",
            status=RepositoryDay15FlowStepStatus.PENDING,
            summary="尚未生成仓库快照，请先执行 Day02 刷新。",
        )
    elif project.latest_repository_snapshot.status == RepositorySnapshotStatus.SUCCESS:
        snapshot_step = RepositoryDay15FlowStepResponse(
            key="snapshot_freshness",
            title="刷新快照",
            status=RepositoryDay15FlowStepStatus.COMPLETED,
            summary="仓库快照已刷新并可用于后续链路。",
        )
    else:
        snapshot_step = RepositoryDay15FlowStepResponse(
            key="snapshot_freshness",
            title="刷新快照",
            status=RepositoryDay15FlowStepStatus.BLOCKED,
            summary=(
                project.latest_repository_snapshot.scan_error
                or "最近一次仓库快照刷新失败。"
            ),
        )

    if selected_gate is not None:
        change_plan_step = _step_from_checklist(
            key="change_plan",
            title="生成变更计划",
            pending_summary="尚未收集变更计划状态。",
        )
    elif change_plan_count > 0:
        change_plan_step = RepositoryDay15FlowStepResponse(
            key="change_plan",
            title="生成变更计划",
            status=RepositoryDay15FlowStepStatus.COMPLETED,
            summary=f"已沉淀 {change_plan_count} 份变更计划草案。",
        )
    else:
        change_plan_step = RepositoryDay15FlowStepResponse(
            key="change_plan",
            title="生成变更计划",
            status=RepositoryDay15FlowStepStatus.PENDING,
            summary="尚未生成变更计划草案。",
        )

    if selected_change_batch is not None:
        change_batch_step = RepositoryDay15FlowStepResponse(
            key="change_batch",
            title="建立批次",
            status=RepositoryDay15FlowStepStatus.COMPLETED,
            summary=(
                f"已建立变更批次《{selected_change_batch.title}》"
                "并进入 Day07-Day14 链路。"
            ),
        )
    elif change_plan_count > 0:
        change_batch_step = RepositoryDay15FlowStepResponse(
            key="change_batch",
            title="建立批次",
            status=RepositoryDay15FlowStepStatus.PENDING,
            summary=f"已有 {change_plan_count} 份计划，尚未归并为批次。",
        )
    else:
        change_batch_step = RepositoryDay15FlowStepResponse(
            key="change_batch",
            title="建立批次",
            status=RepositoryDay15FlowStepStatus.PENDING,
            summary="暂无可归并的变更计划。",
        )

    if selected_gate is not None:
        preflight_step = _step_from_checklist(
            key="risk_preflight",
            title="执行预检",
            pending_summary="尚未收集执行前预检状态。",
        )
    elif selected_change_batch is None:
        preflight_step = RepositoryDay15FlowStepResponse(
            key="risk_preflight",
            title="执行预检",
            status=RepositoryDay15FlowStepStatus.PENDING,
            summary="请先建立变更批次后再执行 Day08 预检。",
        )
    elif selected_change_batch.preflight.status in {
        ChangeBatchPreflightStatus.READY_FOR_EXECUTION,
        ChangeBatchPreflightStatus.MANUAL_CONFIRMED,
    }:
        preflight_step = RepositoryDay15FlowStepResponse(
            key="risk_preflight",
            title="执行预检",
            status=RepositoryDay15FlowStepStatus.COMPLETED,
            summary=selected_change_batch.preflight.summary
            or "执行前预检已通过。",
        )
    elif selected_change_batch.preflight.status in {
        ChangeBatchPreflightStatus.BLOCKED_REQUIRES_CONFIRMATION,
        ChangeBatchPreflightStatus.MANUAL_REJECTED,
    }:
        preflight_step = RepositoryDay15FlowStepResponse(
            key="risk_preflight",
            title="执行预检",
            status=RepositoryDay15FlowStepStatus.BLOCKED,
            summary=selected_change_batch.preflight.summary
            or "执行前预检处于阻断状态。",
        )
    else:
        preflight_step = RepositoryDay15FlowStepResponse(
            key="risk_preflight",
            title="执行预检",
            status=RepositoryDay15FlowStepStatus.PENDING,
            summary="当前批次尚未执行 Day08 预检。",
        )

    verification_step = _step_from_checklist(
        key="verification_results",
        title="记录验证",
        pending_summary="尚未收集验证结果。",
    )
    evidence_step = _step_from_checklist(
        key="diff_evidence",
        title="生成证据包",
        pending_summary="尚未生成 Day11 差异证据包。",
    )
    commit_draft_step = _step_from_checklist(
        key="commit_draft",
        title="形成提交草案",
        pending_summary="尚未生成 Day13 提交草案。",
    )

    if selected_gate is None:
        release_step = RepositoryDay15FlowStepResponse(
            key="release_judgement",
            title="展示放行判断",
            status=RepositoryDay15FlowStepStatus.PENDING,
            summary="尚未建立可用于放行判断的批次。",
        )
    elif selected_gate.blocked:
        release_step = RepositoryDay15FlowStepResponse(
            key="release_judgement",
            title="展示放行判断",
            status=RepositoryDay15FlowStepStatus.BLOCKED,
            summary=(
                "放行检查单仍有缺口："
                + "；".join(selected_gate.gap_reasons or selected_gate.missing_item_keys)
            ),
        )
    else:
        release_step = RepositoryDay15FlowStepResponse(
            key="release_judgement",
            title="展示放行判断",
            status=RepositoryDay15FlowStepStatus.COMPLETED,
            summary=(
                f"放行状态：{selected_gate.status.value}；"
                f"累计决策 {selected_gate.decision_count} 条。"
            ),
        )

    steps = [
        repository_binding_step,
        snapshot_step,
        change_plan_step,
        change_batch_step,
        preflight_step,
        verification_step,
        evidence_step,
        commit_draft_step,
        release_step,
    ]
    completed_step_count = sum(
        1
        for item in steps
        if item.status == RepositoryDay15FlowStepStatus.COMPLETED
    )
    blocked_step_count = sum(
        1
        for item in steps
        if item.status == RepositoryDay15FlowStepStatus.BLOCKED
    )
    overall_status = (
        RepositoryDay15FlowStatus.BLOCKED
        if blocked_step_count > 0
        else (
            RepositoryDay15FlowStatus.READY_FOR_REVIEW
            if completed_step_count == len(steps)
            else RepositoryDay15FlowStatus.IN_PROGRESS
        )
    )

    return RepositoryDay15FlowResponse(
        project_id=project.id,
        project_name=project.name,
        generated_at=utc_now(),
        selected_change_batch_id=(
            selected_change_batch.id if selected_change_batch is not None else None
        ),
        selected_change_batch_title=(
            selected_change_batch.title if selected_change_batch is not None else None
        ),
        overall_status=overall_status,
        completed_step_count=completed_step_count,
        total_step_count=len(steps),
        blocked_step_count=blocked_step_count,
        change_plan_count=change_plan_count,
        change_batch_count=len(change_batches),
        release_status=selected_gate.status if selected_gate is not None else None,
        release_qualification_established=(
            selected_gate.release_qualification_established
            if selected_gate is not None
            else False
        ),
        git_write_actions_triggered=(
            selected_gate.git_write_actions_triggered
            if selected_gate is not None
            else False
        ),
        steps=steps,
    )


def build_repository_draft_chain_readback(
    *,
    project_id: UUID,
    project_repository: ProjectRepository,
    change_plan_repository: ChangePlanRepository,
    change_batch_repository: ChangeBatchRepository,
    commit_candidate_repository: CommitCandidateRepository,
    repository_release_gate_service: RepositoryReleaseGateService,
) -> RepositoryDraftChainReadbackResponse:
    """Aggregate CL-12 draft-chain evidence without invoking git-write actions."""

    project = project_repository.get_by_id(project_id)
    if project is None:
        raise RepositoryReleaseGateProjectNotFoundError(f"Project not found: {project_id}")

    change_plan_count = len(change_plan_repository.list_records_by_project_id(project_id))
    change_batches = change_batch_repository.list_by_project_id(project_id)
    selected_change_batch = change_batch_repository.get_active_by_project_id(
        project_id
    ) or next(iter(change_batches), None)

    selected_gate: RepositoryReleaseGate | None = None
    selected_candidate: CommitCandidate | None = None
    git_write_summary = {
        "apply_local_triggered": False,
        "git_commit_triggered": False,
        "git_write_actions_triggered": False,
    }

    if selected_change_batch is not None:
        selected_candidate = commit_candidate_repository.get_by_change_batch_id(
            selected_change_batch.id
        )
        selected_gate = repository_release_gate_service.get_release_gate(
            selected_change_batch.id
        )
        git_write_summary = get_git_write_action_summary(selected_change_batch.id)

    day15_flow = build_repository_day15_flow_snapshot(
        project_id=project_id,
        project_repository=project_repository,
        change_plan_repository=change_plan_repository,
        change_batch_repository=change_batch_repository,
        repository_release_gate_service=repository_release_gate_service,
    )

    latest_candidate_version = (
        selected_candidate.versions[-1]
        if selected_candidate is not None and selected_candidate.versions
        else None
    )

    preflight = selected_change_batch.preflight if selected_change_batch else None
    return RepositoryDraftChainReadbackResponse(
        project_id=project.id,
        project_name=project.name,
        generated_at=utc_now(),
        selected_change_batch_id=(
            selected_change_batch.id if selected_change_batch is not None else None
        ),
        selected_change_batch_title=(
            selected_change_batch.title if selected_change_batch is not None else None
        ),
        change_plan_count=change_plan_count,
        change_batch_count=len(change_batches),
        preflight_status=preflight.status if preflight is not None else None,
        preflight_ready_for_execution=(
            bool(preflight.ready_for_execution) if preflight is not None else False
        ),
        commit_candidate_present=selected_candidate is not None,
        commit_candidate_id=(
            selected_candidate.id if selected_candidate is not None else None
        ),
        commit_candidate_status=(
            selected_candidate.status if selected_candidate is not None else None
        ),
        commit_candidate_current_version=(
            selected_candidate.current_version_number
            if selected_candidate is not None
            else None
        ),
        commit_candidate_revision_count=(
            len(selected_candidate.versions) if selected_candidate is not None else 0
        ),
        commit_candidate_related_file_count=(
            len(latest_candidate_version.related_files)
            if latest_candidate_version is not None
            else 0
        ),
        commit_candidate_evidence_package_key=(
            latest_candidate_version.evidence_package_key
            if latest_candidate_version is not None
            else None
        ),
        release_status=selected_gate.status if selected_gate is not None else None,
        release_blocked=bool(selected_gate.blocked) if selected_gate is not None else False,
        release_missing_item_keys=(
            list(selected_gate.missing_item_keys) if selected_gate is not None else []
        ),
        release_qualification_established=(
            selected_gate.release_qualification_established
            if selected_gate is not None
            else False
        ),
        git_write_actions_triggered=git_write_summary["git_write_actions_triggered"],
        apply_local_triggered=git_write_summary["apply_local_triggered"],
        git_commit_triggered=git_write_summary["git_commit_triggered"],
        day15_flow=day15_flow,
    )


def get_repository_workspace_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> RepositoryWorkspaceService:
    """Create the Day01 repository-workspace dependency."""

    project_repository = ProjectRepository(session)
    return RepositoryWorkspaceService(
        project_repository=project_repository,
        repository_workspace_repository=RepositoryWorkspaceRepository(session),
        repository_workspace_settings_service=RepositoryWorkspaceSettingsService(),
    )


def get_repository_workspace_settings_service() -> RepositoryWorkspaceSettingsService:
    """Create the repository workspace settings dependency."""

    return RepositoryWorkspaceSettingsService()


def get_repository_scan_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> RepositoryScanService:
    """Create the Day02 repository-scan dependency."""

    project_repository = ProjectRepository(session)
    repository_workspace_repository = RepositoryWorkspaceRepository(session)
    return RepositoryScanService(
        project_repository=project_repository,
        repository_workspace_repository=repository_workspace_repository,
        repository_snapshot_repository=RepositorySnapshotRepository(session),
    )


def get_repository_verification_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> RepositoryVerificationService:
    """Create the Day09 repository-verification dependency."""

    return RepositoryVerificationService(
        project_repository=ProjectRepository(session),
        repository_workspace_repository=RepositoryWorkspaceRepository(session),
        repository_verification_repository=RepositoryVerificationRepository(session),
    )


def get_branch_session_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> BranchSessionService:
    """Create the Day03 branch-session dependency."""

    project_repository = ProjectRepository(session)
    return BranchSessionService(
        project_repository=project_repository,
        repository_workspace_repository=RepositoryWorkspaceRepository(session),
        change_session_repository=ChangeSessionRepository(session),
    )


def get_codebase_locator_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> CodebaseLocatorService:
    """Create the Day05 file-locator dependency."""

    return CodebaseLocatorService(
        project_repository=ProjectRepository(session),
        repository_workspace_repository=RepositoryWorkspaceRepository(session),
        task_repository=TaskRepository(session),
    )


def get_code_context_builder_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ContextBuilderService:
    """Create the Day05 bounded code-context builder dependency."""

    task_repository = TaskRepository(session)
    run_repository = RunRepository(session)
    return ContextBuilderService(
        run_repository=run_repository,
        task_readiness_service=TaskReadinessService(
            task_repository=task_repository,
            run_repository=run_repository,
        ),
    )


def get_change_batch_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ChangeBatchService:
    """Create the Day07 change-batch dependency."""

    return ChangeBatchService(
        change_batch_repository=ChangeBatchRepository(session),
        change_plan_repository=ChangePlanRepository(session),
        project_repository=ProjectRepository(session),
        repository_workspace_repository=RepositoryWorkspaceRepository(session),
        task_repository=TaskRepository(session),
        deliverable_repository=DeliverableRepository(session),
    )


def get_change_risk_guard_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ChangeRiskGuardService:
    """Create the Day08 preflight risk-guard dependency."""

    return ChangeRiskGuardService(
        change_batch_repository=ChangeBatchRepository(session),
        project_repository=ProjectRepository(session),
    )


def get_commit_candidate_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> CommitCandidateService:
    """Create the Day13 commit-candidate dependency."""

    return CommitCandidateService(
        commit_candidate_repository=CommitCandidateRepository(session),
        change_batch_repository=ChangeBatchRepository(session),
        project_repository=ProjectRepository(session),
        diff_summary_service=DiffSummaryService(
            project_repository=ProjectRepository(session),
            repository_workspace_repository=RepositoryWorkspaceRepository(session),
            change_batch_repository=ChangeBatchRepository(session),
            deliverable_repository=DeliverableRepository(session),
            approval_repository=ApprovalRepository(session),
            verification_run_repository=VerificationRunRepository(session),
        ),
    )


def get_repository_release_gate_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> RepositoryReleaseGateService:
    """Create the Day14 repository release-gate dependency."""

    project_repository = ProjectRepository(session)
    repository_workspace_repository = RepositoryWorkspaceRepository(session)
    change_batch_repository = ChangeBatchRepository(session)
    commit_candidate_repository = CommitCandidateRepository(session)
    verification_run_repository = VerificationRunRepository(session)
    return RepositoryReleaseGateService(
        project_repository=project_repository,
        repository_workspace_repository=repository_workspace_repository,
        repository_snapshot_repository=RepositorySnapshotRepository(session),
        change_batch_repository=change_batch_repository,
        commit_candidate_repository=commit_candidate_repository,
        verification_run_repository=verification_run_repository,
        diff_summary_service=DiffSummaryService(
            project_repository=project_repository,
            repository_workspace_repository=repository_workspace_repository,
            change_batch_repository=change_batch_repository,
            deliverable_repository=DeliverableRepository(session),
            approval_repository=ApprovalRepository(session),
            verification_run_repository=verification_run_repository,
        ),
    )


def get_local_git_write_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> LocalGitWriteService:
    """Create the BCL-03 local-git-write dependency."""
    return LocalGitWriteService(
        change_batch_repository=ChangeBatchRepository(session),
        commit_candidate_repository=CommitCandidateRepository(session),
        workspace_repository=RepositoryWorkspaceRepository(session),
        release_gate_service=get_repository_release_gate_service(session),
    )


router = APIRouter(prefix="/repositories", tags=["repositories"])


@router.get(
    "/workspace-settings",
    response_model=RepositoryWorkspaceSettingsResponse,
    summary="Get repository workspace safety boundary settings",
)
def get_repository_workspace_settings(
    repository_workspace_settings_service: Annotated[
        RepositoryWorkspaceSettingsService,
        Depends(get_repository_workspace_settings_service),
    ],
) -> RepositoryWorkspaceSettingsResponse:
    """Return the effective allowed repository workspace roots."""

    try:
        summary = repository_workspace_settings_service.get_summary()
    except RepositoryWorkspaceSettingsError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return RepositoryWorkspaceSettingsResponse.from_summary(summary)


@router.put(
    "/workspace-settings",
    response_model=RepositoryWorkspaceSettingsResponse,
    summary="Update repository workspace safety boundary settings",
)
def update_repository_workspace_settings(
    request: RepositoryWorkspaceSettingsUpdateRequest,
    repository_workspace_settings_service: Annotated[
        RepositoryWorkspaceSettingsService,
        Depends(get_repository_workspace_settings_service),
    ],
) -> RepositoryWorkspaceSettingsResponse:
    """Persist the user-maintained repository workspace root allow-list."""

    try:
        summary = repository_workspace_settings_service.update_allowed_workspace_roots(
            request.allowed_workspace_roots
        )
    except RepositoryWorkspaceSettingsError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return RepositoryWorkspaceSettingsResponse.from_summary(summary)


@router.put(
    "/projects/{project_id}",
    response_model=RepositoryWorkspaceResponse,
    summary="Bind one project to a primary local repository workspace",
)
def bind_project_repository(
    project_id: UUID,
    request: RepositoryWorkspaceBindRequest,
    repository_workspace_service: Annotated[
        RepositoryWorkspaceService,
        Depends(get_repository_workspace_service),
    ],
) -> RepositoryWorkspaceResponse:
    """Create or replace one project's Day01 repository binding."""

    try:
        workspace = repository_workspace_service.bind_project_repository(
            project_id,
            root_path=request.root_path,
            display_name=request.display_name,
            access_mode=request.access_mode,
            default_base_branch=request.default_base_branch,
            ignore_rule_summary=request.ignore_rule_summary,
        )
    except RepositoryWorkspaceProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except RepositoryWorkspacePathError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return RepositoryWorkspaceResponse.from_workspace(workspace)


@router.get(
    "/projects/{project_id}",
    response_model=RepositoryWorkspaceResponse,
    summary="Get one project's primary local repository workspace",
)
def get_project_repository(
    project_id: UUID,
    repository_workspace_service: Annotated[
        RepositoryWorkspaceService,
        Depends(get_repository_workspace_service),
    ],
) -> RepositoryWorkspaceResponse:
    """Return the Day01 repository binding for one project."""

    try:
        workspace = repository_workspace_service.get_project_repository(project_id)
    except RepositoryWorkspaceProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository workspace not found for project: {project_id}",
        )

    return RepositoryWorkspaceResponse.from_workspace(workspace)


@router.get(
    "/projects/{project_id}/verification-baseline",
    response_model=RepositoryVerificationBaselineResponse,
    summary="Get or initialize one project's Day09 repository verification baseline",
)
def get_project_repository_verification_baseline(
    project_id: UUID,
    repository_verification_service: Annotated[
        RepositoryVerificationService,
        Depends(get_repository_verification_service),
    ],
) -> RepositoryVerificationBaselineResponse:
    """Return the Day09 verification baseline for one bound repository."""

    try:
        baseline = repository_verification_service.get_or_create_project_baseline(
            project_id
        )
    except (
        RepositoryVerificationProjectNotFoundError,
        RepositoryVerificationWorkspaceNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except RepositoryVerificationTemplateConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return RepositoryVerificationBaselineResponse.from_baseline(baseline)


@router.put(
    "/projects/{project_id}/verification-baseline",
    response_model=RepositoryVerificationBaselineResponse,
    summary="Replace one project's Day09 repository verification baseline",
)
def replace_project_repository_verification_baseline(
    project_id: UUID,
    request: RepositoryVerificationBaselineUpsertRequest,
    repository_verification_service: Annotated[
        RepositoryVerificationService,
        Depends(get_repository_verification_service),
    ],
) -> RepositoryVerificationBaselineResponse:
    """Replace the full Day09 verification baseline for one bound repository."""

    try:
        baseline = repository_verification_service.replace_project_baseline(
            project_id,
            templates=[
                template.to_domain_model(project_id=project_id)
                for template in request.templates
            ],
        )
    except (
        RepositoryVerificationProjectNotFoundError,
        RepositoryVerificationWorkspaceNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except RepositoryVerificationTemplateConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return RepositoryVerificationBaselineResponse.from_baseline(baseline)


@router.delete(
    "/projects/{project_id}",
    response_model=RepositoryWorkspaceResponse,
    summary="Unbind one project's primary local repository workspace",
)
def unbind_project_repository(
    project_id: UUID,
    repository_workspace_service: Annotated[
        RepositoryWorkspaceService,
        Depends(get_repository_workspace_service),
    ],
) -> RepositoryWorkspaceResponse:
    """Delete the Day01 repository binding for one project."""

    try:
        workspace = repository_workspace_service.unbind_project_repository(project_id)
    except RepositoryWorkspaceProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except RepositoryWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return RepositoryWorkspaceResponse.from_workspace(workspace)


@router.post(
    "/projects/{project_id}/snapshot/refresh",
    response_model=RepositorySnapshotResponse,
    summary="Refresh one project's latest repository workspace snapshot",
)
def refresh_project_repository_snapshot(
    project_id: UUID,
    repository_scan_service: Annotated[
        RepositoryScanService,
        Depends(get_repository_scan_service),
    ],
) -> RepositorySnapshotResponse:
    """Manually refresh one project's Day02 repository snapshot."""

    try:
        snapshot = repository_scan_service.scan_project_repository(project_id)
    except RepositoryScanProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except RepositoryScanWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return RepositorySnapshotResponse.from_snapshot(snapshot)


@router.get(
    "/projects/{project_id}/snapshot",
    response_model=RepositorySnapshotResponse,
    summary="Get one project's latest repository workspace snapshot",
)
def get_project_repository_snapshot(
    project_id: UUID,
    repository_scan_service: Annotated[
        RepositoryScanService,
        Depends(get_repository_scan_service),
    ],
) -> RepositorySnapshotResponse:
    """Return the latest persisted Day02 repository snapshot for one project."""

    try:
        snapshot = repository_scan_service.get_latest_project_snapshot(project_id)
    except RepositoryScanProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository snapshot not found for project: {project_id}",
        )

    return RepositorySnapshotResponse.from_snapshot(snapshot)


@router.post(
    "/projects/{project_id}/change-session",
    response_model=ChangeSessionResponse,
    summary="Capture one project's current Day03 change-session snapshot",
)
def capture_project_change_session(
    project_id: UUID,
    branch_session_service: Annotated[
        BranchSessionService,
        Depends(get_branch_session_service),
    ],
) -> ChangeSessionResponse:
    """Freeze one read-only Day03 branch/workspace state snapshot for a project."""

    try:
        change_session = branch_session_service.capture_project_change_session(project_id)
    except BranchSessionProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except BranchSessionWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except BranchSessionInspectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return ChangeSessionResponse.from_change_session(change_session)


@router.get(
    "/projects/{project_id}/change-session",
    response_model=ChangeSessionResponse,
    summary="Get one project's current Day03 change-session snapshot",
)
def get_project_change_session(
    project_id: UUID,
    branch_session_service: Annotated[
        BranchSessionService,
        Depends(get_branch_session_service),
    ],
) -> ChangeSessionResponse:
    """Return one project's active read-only Day03 branch-session snapshot."""

    try:
        change_session = branch_session_service.get_active_project_change_session(
            project_id
        )
    except BranchSessionProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except BranchSessionWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    if change_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Change session not found for project: {project_id}",
        )

    return ChangeSessionResponse.from_change_session(change_session)


@router.post(
    "/projects/{project_id}/file-locator/search",
    response_model=FileLocatorResult,
    summary="Locate Day05 candidate files for one task or planning brief",
)
def search_project_repository_files(
    project_id: UUID,
    request: FileLocatorSearchRequest,
    codebase_locator_service: Annotated[
        CodebaseLocatorService,
        Depends(get_codebase_locator_service),
    ],
) -> FileLocatorResult:
    """Return one minimal Day05 candidate file set for a task or planning brief."""

    try:
        return codebase_locator_service.locate_files(
            project_id,
            task_id=request.task_id,
            task_query=request.task_query,
            keywords=request.keywords,
            path_prefixes=request.path_prefixes,
            module_names=request.module_names,
            file_types=request.file_types,
            limit=request.limit,
        )
    except (
        CodebaseLocatorProjectNotFoundError,
        CodebaseLocatorWorkspaceNotFoundError,
        CodebaseLocatorTaskNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except CodebaseLocatorRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/projects/{project_id}/change-batches",
    response_model=list[ChangeBatchSummaryResponse],
    summary="List Day07 change-batch execution preparations for one project",
)
def list_project_change_batches(
    project_id: UUID,
    change_batch_service: Annotated[
        ChangeBatchService,
        Depends(get_change_batch_service),
    ],
) -> list[ChangeBatchSummaryResponse]:
    """Return all Day07 change batches under one project ordered by latest activity."""

    try:
        items = change_batch_service.list_change_batches(project_id)
    except ChangeBatchProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return [ChangeBatchSummaryResponse.from_summary(item) for item in items]


@router.post(
    "/projects/{project_id}/change-batches",
    response_model=ChangeBatchDetailResponse,
    summary="Create one Day07 execution-preparation batch from multiple change plans",
)
def create_project_change_batch(
    project_id: UUID,
    request: ChangeBatchCreateRequest,
    change_batch_service: Annotated[
        ChangeBatchService,
        Depends(get_change_batch_service),
    ],
) -> ChangeBatchDetailResponse:
    """Merge multiple latest ChangePlan heads into one Day07 change batch."""

    try:
        detail = change_batch_service.create_change_batch(
            project_id=project_id,
            title=request.title,
            change_plan_ids=request.change_plan_ids,
        )
    except (
        ChangeBatchProjectNotFoundError,
        ChangeBatchWorkspaceNotFoundError,
        ChangeBatchPlanNotFoundError,
        ChangeBatchDeliverableNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ChangeBatchActiveConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except (ChangeBatchPlanTaskConflictError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return ChangeBatchDetailResponse.from_detail(detail)


@router.get(
    "/change-batches/{change_batch_id}",
    response_model=ChangeBatchDetailResponse,
    summary="Get one Day07 change-batch execution-preparation detail",
)
def get_change_batch_detail(
    change_batch_id: UUID,
    change_batch_service: Annotated[
        ChangeBatchService,
        Depends(get_change_batch_service),
    ],
) -> ChangeBatchDetailResponse:
    """Return one Day07 change batch including task order, overlap risks and timeline."""

    try:
        detail = change_batch_service.get_change_batch_detail(change_batch_id)
    except ChangeBatchNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return ChangeBatchDetailResponse.from_detail(detail)


@router.post(
    "/change-batches/{change_batch_id}/preflight",
    response_model=ChangeBatchDetailResponse,
    summary="Run one Day08 execution-preflight guard for a change batch",
)
def run_change_batch_preflight(
    change_batch_id: UUID,
    request: ChangeBatchPreflightRequest,
    change_risk_guard_service: Annotated[
        ChangeRiskGuardService,
        Depends(get_change_risk_guard_service),
    ],
    change_batch_service: Annotated[
        ChangeBatchService,
        Depends(get_change_batch_service),
    ],
) -> ChangeBatchDetailResponse:
    """Classify Day08 risks before execution and persist the preflight result."""

    try:
        change_risk_guard_service.run_preflight(
            change_batch_id=change_batch_id,
            candidate_commands=request.candidate_commands,
        )
        detail = change_batch_service.get_change_batch_detail(change_batch_id)
    except (
        ChangeRiskGuardBatchNotFoundError,
        ChangeRiskGuardProjectNotFoundError,
        ChangeBatchNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return ChangeBatchDetailResponse.from_detail(detail)


@router.get(
    "/projects/{project_id}/release-gates",
    response_model=ProjectRepositoryReleaseGateInboxResponse,
    summary="List Day14 repository release-gate snapshots for one project",
)
def list_project_repository_release_gates(
    project_id: UUID,
    repository_release_gate_service: Annotated[
        RepositoryReleaseGateService,
        Depends(get_repository_release_gate_service),
    ],
) -> ProjectRepositoryReleaseGateInboxResponse:
    """Return project-scoped Day14 release-gate summaries."""

    try:
        inbox = repository_release_gate_service.list_project_release_gates(project_id)
    except RepositoryReleaseGateProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return ProjectRepositoryReleaseGateInboxResponse.from_inbox(inbox)


@router.get(
    "/change-batches/{change_batch_id}/release-checklist",
    response_model=RepositoryReleaseGateDetailResponse,
    summary="Get one Day14 release checklist and gate detail by change batch",
)
def get_change_batch_release_checklist(
    change_batch_id: UUID,
    repository_release_gate_service: Annotated[
        RepositoryReleaseGateService,
        Depends(get_repository_release_gate_service),
    ],
) -> RepositoryReleaseGateDetailResponse:
    """Return one Day14 release checklist snapshot for a selected change batch."""

    try:
        gate = repository_release_gate_service.get_release_gate(change_batch_id)
    except (
        RepositoryReleaseGateProjectNotFoundError,
        RepositoryReleaseGateChangeBatchNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return RepositoryReleaseGateDetailResponse.from_gate(gate)


@router.get(
    "/projects/{project_id}/day15-flow",
    response_model=RepositoryDay15FlowResponse,
    summary="Get the Day15 minimum closed-loop repository demo snapshot",
)
def get_project_day15_flow(
    project_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    repository_release_gate_service: Annotated[
        RepositoryReleaseGateService,
        Depends(get_repository_release_gate_service),
    ],
) -> RepositoryDay15FlowResponse:
    """Aggregate Day01-Day14 into one Day15 read-only closed-loop snapshot."""

    try:
        return build_repository_day15_flow_snapshot(
            project_id=project_id,
            project_repository=ProjectRepository(session),
            change_plan_repository=ChangePlanRepository(session),
            change_batch_repository=ChangeBatchRepository(session),
            repository_release_gate_service=repository_release_gate_service,
        )
    except (
        RepositoryReleaseGateProjectNotFoundError,
        RepositoryReleaseGateChangeBatchNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/projects/{project_id}/draft-chain-readback",
    response_model=RepositoryDraftChainReadbackResponse,
    summary="Get the CL-12 safe review-only repository draft-chain readback",
)
def get_project_draft_chain_readback(
    project_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    repository_release_gate_service: Annotated[
        RepositoryReleaseGateService,
        Depends(get_repository_release_gate_service),
    ],
) -> RepositoryDraftChainReadbackResponse:
    """Aggregate change plan → batch → preflight → draft → gate without git writes."""

    try:
        return build_repository_draft_chain_readback(
            project_id=project_id,
            project_repository=ProjectRepository(session),
            change_plan_repository=ChangePlanRepository(session),
            change_batch_repository=ChangeBatchRepository(session),
            commit_candidate_repository=CommitCandidateRepository(session),
            repository_release_gate_service=repository_release_gate_service,
        )
    except (
        RepositoryReleaseGateProjectNotFoundError,
        RepositoryReleaseGateChangeBatchNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/projects/{project_id}/commit-candidates",
    response_model=list[CommitCandidateSummaryResponse],
    summary="List Day13 commit-candidate drafts for one project",
)
def list_project_commit_candidates(
    project_id: UUID,
    commit_candidate_service: Annotated[
        CommitCandidateService,
        Depends(get_commit_candidate_service),
    ],
) -> list[CommitCandidateSummaryResponse]:
    """Return all Day13 commit-candidate summaries under one project."""

    try:
        candidates = commit_candidate_service.list_project_commit_candidates(project_id)
    except CommitCandidateProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return [
        CommitCandidateSummaryResponse.from_candidate(candidate)
        for candidate in candidates
    ]


@router.get(
    "/change-batches/{change_batch_id}/commit-candidate",
    response_model=CommitCandidateDetailResponse,
    summary="Get one Day13 commit-candidate draft by change batch",
)
def get_change_batch_commit_candidate(
    change_batch_id: UUID,
    commit_candidate_service: Annotated[
        CommitCandidateService,
        Depends(get_commit_candidate_service),
    ],
) -> CommitCandidateDetailResponse:
    """Return one Day13 commit-candidate including all draft revisions."""

    try:
        candidate = commit_candidate_service.get_change_batch_commit_candidate(
            change_batch_id
        )
    except (CommitCandidateBatchNotFoundError, CommitCandidateNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return CommitCandidateDetailResponse.from_candidate(candidate)


@router.post(
    "/change-batches/{change_batch_id}/commit-candidate",
    response_model=CommitCandidateDetailResponse,
    summary="Generate or revise one Day13 commit-candidate draft from evidence",
)
def generate_change_batch_commit_candidate(
    change_batch_id: UUID,
    request: CommitCandidateDraftUpsertRequest,
    commit_candidate_service: Annotated[
        CommitCandidateService,
        Depends(get_commit_candidate_service),
    ],
) -> CommitCandidateDetailResponse:
    """Generate a Day13 review-only commit draft or append one revision."""

    try:
        candidate = commit_candidate_service.generate_commit_candidate(
            change_batch_id=change_batch_id,
            message_title=request.message_title,
            message_body=request.message_body,
            impact_scope=request.impact_scope,
            related_files=request.related_files,
            revision_note=request.revision_note,
        )
    except (
        CommitCandidateBatchNotFoundError,
        CommitCandidateProjectNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (
        CommitCandidatePreflightNotReadyError,
        CommitCandidateVerificationNotPassedError,
        CommitCandidateEvidenceUnavailableError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return CommitCandidateDetailResponse.from_candidate(candidate)


@router.post(
    "/projects/{project_id}/context-pack",
    response_model=CodeContextPack,
    summary="Build one bounded Day05 CodeContextPack from selected repository files",
    operation_id="build_project_code_context_pack",
    description=(
        "BCG-12A-P0-R1: expose the project CodeContextPack API used by the "
        "web file-locator flow. The route resolves the bound repository "
        "workspace for the project and returns bounded excerpts for selected "
        "repository-relative paths."
    ),
)
def build_project_code_context_pack(
    project_id: UUID,
    request: CodeContextPackBuildRequest,
    codebase_locator_service: Annotated[
        CodebaseLocatorService,
        Depends(get_codebase_locator_service),
    ],
    context_builder_service: Annotated[
        ContextBuilderService,
        Depends(get_code_context_builder_service),
    ],
) -> CodeContextPack:
    """Build one bounded Day05 `CodeContextPack` from previously selected files."""

    locator_filters_present = any(
        [
            request.task_id is not None,
            bool(request.task_query and request.task_query.strip()),
            bool(request.keywords),
            bool(request.path_prefixes),
            bool(request.module_names),
            bool(request.file_types),
        ]
    )

    source_summary = "手动选择文件并生成代码上下文包。"
    focus_terms: list[str] = []
    derived_reason_map: dict[str, list[str]] = {}

    if locator_filters_present:
        try:
            locator_result = codebase_locator_service.locate_files(
                project_id,
                task_id=request.task_id,
                task_query=request.task_query,
                keywords=request.keywords,
                path_prefixes=request.path_prefixes,
                module_names=request.module_names,
                file_types=request.file_types,
                limit=max(request.limit, len(request.selected_paths), 20),
            )
        except (
            CodebaseLocatorProjectNotFoundError,
            CodebaseLocatorWorkspaceNotFoundError,
            CodebaseLocatorTaskNotFoundError,
        ) as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        except CodebaseLocatorRequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

        source_summary = locator_result.query.summary
        focus_terms = locator_result.query.keywords
        derived_reason_map = {
            candidate.relative_path: list(candidate.match_reasons)
            for candidate in locator_result.candidates
        }

    merged_reason_map = {
        path: [
            reason.strip()
            for reason in (
                request.selection_reasons_by_path.get(path)
                or derived_reason_map.get(path)
                or []
            )
            if reason.strip()
        ]
        for path in request.selected_paths
    }

    try:
        repository_root_path = codebase_locator_service.get_project_repository_root_path(
            project_id
        )
        return context_builder_service.build_code_context_pack(
            repository_root_path=repository_root_path,
            selected_paths=request.selected_paths,
            source_summary=source_summary,
            focus_terms=focus_terms,
            selection_reasons_by_path=merged_reason_map,
            max_total_bytes=request.max_total_bytes,
            max_bytes_per_file=request.max_bytes_per_file,
            project_id=project_id,
        )
    except (
        CodebaseLocatorProjectNotFoundError,
        CodebaseLocatorWorkspaceNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except CodebaseLocatorRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except CodeContextBuildError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


# -- BCL-03: Local git write ------------------------------------------------


@router.post(
    "/change-batches/{change_batch_id}/apply-local",
    response_model=ApplyLocalResponse,
    summary="BCL-03: Write changed files to the local repository workspace",
)
def apply_local_changes(
    change_batch_id: UUID,
    request: ApplyLocalRequest,
    session: Annotated[Session, Depends(get_db_session)],
    local_git_write_service: Annotated[
        LocalGitWriteService, Depends(get_local_git_write_service)
    ],
) -> ApplyLocalResponse:
    """Validate the full guard chain and write files to the workspace.

    Checks: workspace binding, release gate approval, preflight pass,
    commit candidate existence, path safety (no traversal, no .git, within workspace).
    Performs dry-run diff before writing.
    """
    files_payload = [
        {"relative_path": f.relative_path, "content": f.content}
        for f in request.files
    ]
    result = local_git_write_service.apply_local(
        change_batch_id=change_batch_id,
        files=files_payload,
    )
    return ApplyLocalResponse(
        status=str(result.get("status", "failed")),
        change_batch_id=UUID(str(result.get("change_batch_id", str(change_batch_id)))),
        changed_files=result.get("changed_files", []) or [],
        diff_summary=result.get("diff_summary", {}) or {},
        verification_passed=bool(result.get("verification_passed", False)),
        rollback_performed=bool(result.get("rollback_performed", False)),
        log_path=str(result.get("log_path", "")),
        error_category=result.get("error_category"),
        error_summary=result.get("error_summary"),
    )


@router.post(
    "/change-batches/{change_batch_id}/git-commit",
    response_model=GitCommitResponse,
    summary="BCL-03: Stage and commit changes in the local repository",
)
def git_commit_changes(
    change_batch_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    local_git_write_service: Annotated[
        LocalGitWriteService, Depends(get_local_git_write_service)
    ],
) -> GitCommitResponse:
    """Create a local git commit from a previously applied change batch.

    Requires a prior successful apply-local.  Re-validates release gate,
    preflight, and commit candidate before committing.
    Does NOT push or create remote branches.
    Sets git_write_actions_triggered=true.
    """
    result = local_git_write_service.git_commit(
        change_batch_id=change_batch_id,
    )
    return GitCommitResponse(
        status=str(result.get("status", "failed")),
        change_batch_id=UUID(str(result.get("change_batch_id", str(change_batch_id)))),
        commit_sha=result.get("commit_sha"),
        branch_name=result.get("branch_name"),
        changed_files=result.get("changed_files", []) or [],
        log_path=str(result.get("log_path", "")),
        error_category=result.get("error_category"),
        error_summary=result.get("error_summary"),
    )
