"""BCL-02: Project closure diagnostics -- one read-only aggregation endpoint.

This service answers: "Why can this project not yet form a closed loop from
configuration through repository, task, worker, run, and delivery evidence?"
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.domain._base import utc_now
from app.domain.project import Project, ProjectStage
from app.domain.run import Run, RunStatus
from app.domain.task import Task, TaskStatus
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.change_batch_repository import ChangeBatchRepository
from app.repositories.commit_candidate_repository import CommitCandidateRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.repository_snapshot_repository import (
    RepositorySnapshotRepository,
)
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.project_memory_service import ProjectMemoryService
from app.services.provider_config_service import ProviderConfigService


# -- Domain models for the diagnostics response --------------------------------

class ClosureDiagnosticsNextAction:
    """One suggested next action for unblocking the project closure loop."""

    __slots__ = ("code", "label", "api")

    def __init__(self, *, code: str, label: str, api: str) -> None:
        self.code = code
        self.label = label
        self.api = api


class ClosureDiagnosticsResult:
    """Aggregate diagnostics result for one project."""

    __slots__ = (
        "project_id",
        "generated_at",
        "overall_status",
        "blocking_reason_codes",
        "provider_configured",
        "provider_last_test_status",
        "repository_bound",
        "repository_snapshot_exists",
        "repository_snapshot_status",
        "repository_day15_flow_status",
        "task_count",
        "pending_task_count",
        "run_count",
        "latest_run_status",
        "latest_run_log_path",
        "memory_checkpoint_count",
        "agent_session_count",
        "approval_count",
        "change_batch_count",
        "commit_candidate_count",
        "next_actions",
    )

    def __init__(
        self,
        *,
        project_id: UUID,
        generated_at: datetime,
        overall_status: str,
        blocking_reason_codes: list[str],
        provider_configured: bool,
        provider_last_test_status: str,
        repository_bound: bool,
        repository_snapshot_exists: bool,
        repository_snapshot_status: str | None,
        repository_day15_flow_status: str | None,
        task_count: int,
        pending_task_count: int,
        run_count: int,
        latest_run_status: str | None,
        latest_run_log_path: str | None,
        memory_checkpoint_count: int,
        agent_session_count: int,
        approval_count: int,
        change_batch_count: int,
        commit_candidate_count: int,
        next_actions: list[ClosureDiagnosticsNextAction],
    ) -> None:
        self.project_id = project_id
        self.generated_at = generated_at
        self.overall_status = overall_status
        self.blocking_reason_codes = blocking_reason_codes
        self.provider_configured = provider_configured
        self.provider_last_test_status = provider_last_test_status
        self.repository_bound = repository_bound
        self.repository_snapshot_exists = repository_snapshot_exists
        self.repository_snapshot_status = repository_snapshot_status
        self.repository_day15_flow_status = repository_day15_flow_status
        self.task_count = task_count
        self.pending_task_count = pending_task_count
        self.run_count = run_count
        self.latest_run_status = latest_run_status
        self.latest_run_log_path = latest_run_log_path
        self.memory_checkpoint_count = memory_checkpoint_count
        self.agent_session_count = agent_session_count
        self.approval_count = approval_count
        self.change_batch_count = change_batch_count
        self.commit_candidate_count = commit_candidate_count
        self.next_actions = next_actions


# -- Status derivation helpers -------------------------------------------------

def _derive_overall_status(
    *,
    blocking_reason_codes: list[str],
    has_running_tasks: bool,
    has_pending_tasks: bool,
    has_completed_tasks: bool,
    task_count: int,
) -> str:
    """Derive a stable `overall_status` from blocking reasons and task state."""

    if has_running_tasks:
        return "running"
    if task_count > 0 and not has_pending_tasks and not has_running_tasks:
        return "completed"
    if not blocking_reason_codes:
        return "ready"
    return "blocked"


def _build_blocking_reason_codes(
    *,
    provider_configured: bool,
    repository_bound: bool,
    repository_snapshot_exists: bool,
    task_count: int,
    pending_task_count: int,
) -> list[str]:
    """Build a stable, ordered list of blocking reason codes."""

    codes: list[str] = []

    if not provider_configured:
        codes.append("provider_not_configured")
    if not repository_bound:
        codes.append("repository_not_bound")
    elif not repository_snapshot_exists:
        codes.append("snapshot_missing")
    if task_count == 0:
        codes.append("no_tasks")
    elif pending_task_count == 0:
        codes.append("no_pending_tasks")

    return codes


def _build_next_actions(
    *,
    project_id: UUID,
    blocking_reason_codes: list[str],
    provider_configured: bool,
    repository_bound: bool,
    repository_snapshot_exists: bool,
    task_count: int,
    pending_task_count: int,
) -> list[ClosureDiagnosticsNextAction]:
    """Build ordered next actions to unblock the closure loop."""

    actions: list[ClosureDiagnosticsNextAction] = []

    if "provider_not_configured" in blocking_reason_codes:
        actions.append(
            ClosureDiagnosticsNextAction(
                code="configure_provider",
                label="配置 OpenAI 兼容网关",
                api="PUT /provider-settings/openai",
            )
        )
        actions.append(
            ClosureDiagnosticsNextAction(
                code="test_provider",
                label="测试 Provider 连接",
                api="POST /provider-settings/openai/test",
            )
        )
    elif provider_configured:
        # Provider is configured; suggest a test if never tested
        actions.append(
            ClosureDiagnosticsNextAction(
                code="test_provider",
                label="测试 Provider 连接",
                api="POST /provider-settings/openai/test",
            )
        )

    if "repository_not_bound" in blocking_reason_codes:
        actions.append(
            ClosureDiagnosticsNextAction(
                code="bind_repository",
                label="绑定代码仓库",
                api="POST /repositories/projects/{project_id}/bind",
            )
        )

    if repository_bound and not repository_snapshot_exists:
        actions.append(
            ClosureDiagnosticsNextAction(
                code="refresh_snapshot",
                label="刷新仓库快照",
                api=f"POST /repositories/projects/{project_id}/snapshot/refresh",
            )
        )

    if task_count == 0:
        actions.append(
            ClosureDiagnosticsNextAction(
                code="apply_sop_plan",
                label="应用 SOP 计划生成任务",
                api=f"POST /projects/{project_id}/apply-plan-draft",
            )
        )

    return actions


def _derive_day15_flow_status(
    *,
    repository_bound: bool,
    project_stage: ProjectStage | None,
) -> str | None:
    """Derive a coarse day15 flow status from available data.

    This is a simplified derivation based on project stage and repository
    binding state.  It does NOT run the full Day15 flow snapshot builder.
    """

    if not repository_bound:
        return "not_applicable"
    if project_stage is None:
        return "unknown"
    return project_stage.value


# -- Builder ------------------------------------------------------------------

def build_project_closure_diagnostics(
    *,
    project_id: UUID,
    project_repository: ProjectRepository,
    task_repository: TaskRepository,
    run_repository: RunRepository,
    workspace_repository: RepositoryWorkspaceRepository,
    snapshot_repository: RepositorySnapshotRepository,
    agent_session_repository: AgentSessionRepository,
    approval_repository: ApprovalRepository,
    change_batch_repository: ChangeBatchRepository,
    commit_candidate_repository: CommitCandidateRepository,
    provider_config_service: ProviderConfigService,
    project_memory_service: ProjectMemoryService,
) -> ClosureDiagnosticsResult:
    """Build one project closure diagnostics snapshot -- read-only, no side effects."""

    # --- Project lookup -------------------------------------------------------
    project: Project | None = project_repository.get_by_id(project_id)
    if project is None:
        raise ProjectClosureDiagnosticsProjectNotFoundError(project_id)

    # --- Provider -------------------------------------------------------------
    provider_summary = provider_config_service.get_openai_summary()
    provider_configured = provider_summary.configured
    # There is no persisted test-status store; we report honest defaults.
    provider_last_test_status = "not_tested" if provider_configured else "not_applicable"

    # --- Repository -----------------------------------------------------------
    workspace = workspace_repository.get_by_project_id(project_id)
    repository_bound = workspace is not None
    snapshot = snapshot_repository.get_by_project_id(project_id)
    repository_snapshot_exists = snapshot is not None
    repository_snapshot_status: str | None = (
        snapshot.status.value if snapshot is not None else None
    )
    repository_day15_flow_status = _derive_day15_flow_status(
        repository_bound=repository_bound,
        project_stage=project.stage,
    )

    # --- Task runtime ---------------------------------------------------------
    tasks: list[Task] = task_repository.list_by_project_id(project_id)
    task_count = len(tasks)
    pending_task_count = sum(1 for t in tasks if t.status == TaskStatus.PENDING)
    has_running_tasks = any(t.status == TaskStatus.RUNNING for t in tasks)
    has_completed_tasks = any(t.status == TaskStatus.COMPLETED for t in tasks)

    task_ids = [t.id for t in tasks]
    runs: list[Run] = run_repository.list_by_task_ids(task_ids) if task_ids else []
    run_count = len(runs)
    # Runs are ordered by created_at desc from list_by_task_ids
    latest_run: Run | None = runs[0] if runs else None
    latest_run_status: str | None = (
        latest_run.status.value if latest_run is not None else None
    )
    latest_run_log_path: str | None = (
        latest_run.log_path if latest_run is not None else None
    )

    # --- Governance -----------------------------------------------------------
    # Memory checkpoints -- via ProjectMemoryService governance state.
    try:
        governance_state = project_memory_service.get_memory_governance_state(
            project_id=project_id
        )
        memory_checkpoint_count = governance_state.checkpoint_count
    except Exception:
        memory_checkpoint_count = 0

    # Agent sessions
    try:
        sessions = agent_session_repository.list_by_project_id(project_id=project_id)
        agent_session_count = len(sessions)
    except Exception:
        agent_session_count = 0

    # Approvals
    try:
        approvals = approval_repository.list_records_by_project_id(project_id)
        approval_count = len(approvals)
    except Exception:
        approval_count = 0

    # Change batches
    try:
        change_batches = change_batch_repository.list_by_project_id(project_id)
        change_batch_count = len(change_batches)
    except Exception:
        change_batch_count = 0

    # Commit candidates
    try:
        commit_candidates = commit_candidate_repository.list_by_project_id(project_id)
        commit_candidate_count = len(commit_candidates)
    except Exception:
        commit_candidate_count = 0

    # --- Blocking reasons -----------------------------------------------------
    blocking_reason_codes = _build_blocking_reason_codes(
        provider_configured=provider_configured,
        repository_bound=repository_bound,
        repository_snapshot_exists=repository_snapshot_exists,
        task_count=task_count,
        pending_task_count=pending_task_count,
    )

    # --- Overall status -------------------------------------------------------
    overall_status = _derive_overall_status(
        blocking_reason_codes=blocking_reason_codes,
        has_running_tasks=has_running_tasks,
        has_pending_tasks=pending_task_count > 0,
        has_completed_tasks=has_completed_tasks,
        task_count=task_count,
    )

    # --- Next actions ---------------------------------------------------------
    next_actions = _build_next_actions(
        project_id=project_id,
        blocking_reason_codes=blocking_reason_codes,
        provider_configured=provider_configured,
        repository_bound=repository_bound,
        repository_snapshot_exists=repository_snapshot_exists,
        task_count=task_count,
        pending_task_count=pending_task_count,
    )

    return ClosureDiagnosticsResult(
        project_id=project_id,
        generated_at=utc_now(),
        overall_status=overall_status,
        blocking_reason_codes=blocking_reason_codes,
        provider_configured=provider_configured,
        provider_last_test_status=provider_last_test_status,
        repository_bound=repository_bound,
        repository_snapshot_exists=repository_snapshot_exists,
        repository_snapshot_status=repository_snapshot_status,
        repository_day15_flow_status=repository_day15_flow_status,
        task_count=task_count,
        pending_task_count=pending_task_count,
        run_count=run_count,
        latest_run_status=latest_run_status,
        latest_run_log_path=latest_run_log_path,
        memory_checkpoint_count=memory_checkpoint_count,
        agent_session_count=agent_session_count,
        approval_count=approval_count,
        change_batch_count=change_batch_count,
        commit_candidate_count=commit_candidate_count,
        next_actions=next_actions,
    )


# -- Exceptions ---------------------------------------------------------------

class ProjectClosureDiagnosticsProjectNotFoundError(Exception):
    """Raised when the requested project does not exist."""

    def __init__(self, project_id: UUID) -> None:
        super().__init__(f"Project not found: {project_id}")
        self.project_id = project_id
