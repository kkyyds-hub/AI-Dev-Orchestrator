"""Repository workspace, snapshot, change-session, Day05 locator and Day07 batch endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain.change_batch import (
    ChangeBatchLinkedDeliverable,
    ChangeBatchStatus,
)
from app.domain.change_session import (
    ChangeSession,
    ChangeSessionDirtyFile,
    ChangeSessionDirtyFileScope,
    ChangeSessionGuardStatus,
    ChangeSessionWorkspaceStatus,
)
from app.domain.code_context_pack import CodeContextPack, FileLocatorResult
from app.domain.change_plan import ChangePlanTargetFile
from app.domain.repository_workspace import (
    RepositoryAccessMode,
    RepositoryWorkspace,
)
from app.domain.repository_snapshot import (
    RepositoryLanguageStat,
    RepositorySnapshot,
    RepositorySnapshotStatus,
    RepositoryTreeNode,
    RepositoryTreeNodeKind,
)
from app.repositories.change_batch_repository import ChangeBatchRepository
from app.repositories.change_session_repository import ChangeSessionRepository
from app.repositories.change_plan_repository import ChangePlanRepository
from app.repositories.deliverable_repository import DeliverableRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.run_repository import RunRepository
from app.repositories.repository_snapshot_repository import (
    RepositorySnapshotRepository,
)
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.change_batch_service import (
    ChangeBatchActiveConflictError,
    ChangeBatchDependencyView,
    ChangeBatchDetail,
    ChangeBatchNotFoundError,
    ChangeBatchPlanTaskConflictError,
    ChangeBatchProjectNotFoundError,
    ChangeBatchService,
    ChangeBatchSummary,
    ChangeBatchTargetFileView,
    ChangeBatchTaskView,
    ChangeBatchTimelineEntry,
    ChangeBatchWorkspaceNotFoundError,
    ChangeBatchPlanNotFoundError,
    ChangeBatchDeliverableNotFoundError,
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
from app.services.repository_workspace_service import (
    RepositoryWorkspaceNotFoundError,
    RepositoryWorkspacePathError,
    RepositoryWorkspaceProjectNotFoundError,
    RepositoryWorkspaceService,
)
from app.services.task_readiness_service import TaskReadinessService


class RepositoryWorkspaceBindRequest(BaseModel):
    """DTO used to bind one project to a local repository workspace."""

    root_path: str = Field(
        min_length=1,
        max_length=1_000,
        description="Absolute local repository root path under the configured safety boundary.",
    )
    display_name: str | None = Field(
        default=None,
        max_length=200,
        description="Optional label shown on future repository cards and project detail views.",
    )
    access_mode: RepositoryAccessMode = Field(
        default=RepositoryAccessMode.READ_ONLY,
        description="Current Day01 access mode. Only read-only binding is supported.",
    )
    default_base_branch: str = Field(
        default="main",
        min_length=1,
        max_length=200,
        description="Default baseline branch recorded for later Day03-Day14 flows.",
    )
    ignore_rule_summary: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Optional ignore-rule summary. Defaults to the Day01 conservative baseline.",
    )


class RepositoryWorkspaceResponse(BaseModel):
    """API DTO shared by repository routes and project detail payloads."""

    id: UUID
    project_id: UUID
    root_path: str
    display_name: str
    access_mode: RepositoryAccessMode
    default_base_branch: str
    ignore_rule_summary: list[str]
    allowed_workspace_root: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_workspace(
        cls,
        workspace: RepositoryWorkspace,
    ) -> "RepositoryWorkspaceResponse":
        """Convert one repository-workspace domain model into an API DTO."""

        return cls(
            id=workspace.id,
            project_id=workspace.project_id,
            root_path=workspace.root_path,
            display_name=workspace.display_name,
            access_mode=workspace.access_mode,
            default_base_branch=workspace.default_base_branch,
            ignore_rule_summary=list(workspace.ignore_rule_summary),
            allowed_workspace_root=workspace.allowed_workspace_root,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
        )


class RepositoryLanguageStatResponse(BaseModel):
    """One language/file-type bucket returned with a repository snapshot."""

    language: str
    file_count: int

    @classmethod
    def from_stat(
        cls,
        stat: RepositoryLanguageStat,
    ) -> "RepositoryLanguageStatResponse":
        """Convert one language stat into an API DTO."""

        return cls(language=stat.language, file_count=stat.file_count)


class RepositoryTreeNodeResponse(BaseModel):
    """One bounded tree node returned with the Day02 snapshot summary."""

    name: str
    relative_path: str
    kind: RepositoryTreeNodeKind
    directory_count: int
    file_count: int
    children: list["RepositoryTreeNodeResponse"] = Field(default_factory=list)
    truncated: bool = False

    @classmethod
    def from_node(
        cls,
        node: RepositoryTreeNode,
    ) -> "RepositoryTreeNodeResponse":
        """Convert one repository tree node into an API DTO."""

        return cls(
            name=node.name,
            relative_path=node.relative_path,
            kind=node.kind,
            directory_count=node.directory_count,
            file_count=node.file_count,
            children=[cls.from_node(child) for child in node.children],
            truncated=node.truncated,
        )


class RepositorySnapshotResponse(BaseModel):
    """Latest structured repository snapshot shared by repository/project payloads."""

    id: UUID
    project_id: UUID
    repository_workspace_id: UUID
    repository_root_path: str
    status: RepositorySnapshotStatus
    directory_count: int
    file_count: int
    ignored_directory_names: list[str]
    language_breakdown: list[RepositoryLanguageStatResponse]
    tree: list[RepositoryTreeNodeResponse]
    scan_error: str | None = None
    scanned_at: datetime
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_snapshot(
        cls,
        snapshot: RepositorySnapshot,
    ) -> "RepositorySnapshotResponse":
        """Convert one repository snapshot domain model into an API DTO."""

        return cls(
            id=snapshot.id,
            project_id=snapshot.project_id,
            repository_workspace_id=snapshot.repository_workspace_id,
            repository_root_path=snapshot.repository_root_path,
            status=snapshot.status,
            directory_count=snapshot.directory_count,
            file_count=snapshot.file_count,
            ignored_directory_names=list(snapshot.ignored_directory_names),
            language_breakdown=[
                RepositoryLanguageStatResponse.from_stat(stat)
                for stat in snapshot.language_breakdown
            ],
            tree=[RepositoryTreeNodeResponse.from_node(node) for node in snapshot.tree],
            scan_error=snapshot.scan_error,
            scanned_at=snapshot.scanned_at,
            created_at=snapshot.created_at,
            updated_at=snapshot.updated_at,
        )


class ChangeSessionDirtyFileResponse(BaseModel):
    """One bounded dirty-file preview item returned with a Day03 session snapshot."""

    path: str
    git_status: str
    change_scope: ChangeSessionDirtyFileScope

    @classmethod
    def from_dirty_file(
        cls,
        dirty_file: ChangeSessionDirtyFile,
    ) -> "ChangeSessionDirtyFileResponse":
        """Convert one change-session dirty-file item into an API DTO."""

        return cls(
            path=dirty_file.path,
            git_status=dirty_file.git_status,
            change_scope=dirty_file.change_scope,
        )


class ChangeSessionResponse(BaseModel):
    """Latest active Day03 change-session snapshot for one project repository."""

    id: UUID
    project_id: UUID
    repository_workspace_id: UUID
    repository_root_path: str
    current_branch: str
    head_ref: str
    head_commit_sha: str | None = None
    baseline_branch: str
    baseline_ref: str
    baseline_commit_sha: str | None = None
    workspace_status: ChangeSessionWorkspaceStatus
    guard_status: ChangeSessionGuardStatus
    guard_summary: str
    blocking_reasons: list[str]
    dirty_file_count: int
    dirty_files_truncated: bool = False
    dirty_files: list[ChangeSessionDirtyFileResponse]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_change_session(
        cls,
        change_session: ChangeSession,
    ) -> "ChangeSessionResponse":
        """Convert one Day03 change-session domain model into an API DTO."""

        return cls(
            id=change_session.id,
            project_id=change_session.project_id,
            repository_workspace_id=change_session.repository_workspace_id,
            repository_root_path=change_session.repository_root_path,
            current_branch=change_session.current_branch,
            head_ref=change_session.head_ref,
            head_commit_sha=change_session.head_commit_sha,
            baseline_branch=change_session.baseline_branch,
            baseline_ref=change_session.baseline_ref,
            baseline_commit_sha=change_session.baseline_commit_sha,
            workspace_status=change_session.workspace_status,
            guard_status=change_session.guard_status,
            guard_summary=change_session.guard_summary,
            blocking_reasons=list(change_session.blocking_reasons),
            dirty_file_count=change_session.dirty_file_count,
            dirty_files_truncated=change_session.dirty_files_truncated,
            dirty_files=[
                ChangeSessionDirtyFileResponse.from_dirty_file(item)
                for item in change_session.dirty_files
            ],
            created_at=change_session.created_at,
            updated_at=change_session.updated_at,
        )


class FileLocatorSearchRequest(BaseModel):
    """DTO for Day05 repository file-location search requests."""

    task_id: UUID | None = Field(
        default=None,
        description="Optional project task ID used to derive locator keywords and summary.",
    )
    task_query: str | None = Field(
        default=None,
        max_length=2_000,
        description="Optional planning or task brief used to derive extra locator keywords.",
    )
    keywords: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Optional explicit keywords merged with task-derived tokens.",
    )
    path_prefixes: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Optional relative path prefixes, such as runtime/orchestrator/app/services.",
    )
    module_names: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Optional module or folder names used as strong Day05 signals.",
    )
    file_types: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Optional file types such as py, tsx, markdown or yaml.",
    )
    limit: int = Field(
        default=12,
        ge=1,
        le=50,
        description="Maximum number of candidate files returned by the locator.",
    )


class CodeContextPackBuildRequest(FileLocatorSearchRequest):
    """DTO for Day05 bounded code-context pack requests."""

    selected_paths: list[str] = Field(
        min_length=1,
        max_length=20,
        description="Relative repository file paths selected from the Day05 candidate list.",
    )
    max_total_bytes: int = Field(
        default=12_000,
        ge=512,
        le=80_000,
        description="Maximum UTF-8 byte budget for the full CodeContextPack.",
    )
    max_bytes_per_file: int = Field(
        default=4_000,
        ge=256,
        le=20_000,
        description="Maximum UTF-8 byte budget allocated to each selected file excerpt.",
    )
    selection_reasons_by_path: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Optional candidate match reasons keyed by relative path for UI round-trips.",
    )


class ChangeBatchCreateRequest(BaseModel):
    """DTO used to create one new Day07 change batch."""

    title: str | None = Field(default=None, max_length=200)
    change_plan_ids: list[UUID] = Field(
        min_length=2,
        max_length=10,
        description="Latest ChangePlan heads selected for this execution-preparation batch.",
    )


class ChangeBatchTargetFileResponse(BaseModel):
    """One target file rendered inside a Day07 change-batch task."""

    relative_path: str
    language: str
    file_type: str
    rationale: str | None = None
    match_reasons: list[str]

    @classmethod
    def from_target_file(
        cls,
        target_file: ChangePlanTargetFile,
    ) -> "ChangeBatchTargetFileResponse":
        """Convert one target-file domain model into a Day07 API DTO."""

        return cls(
            relative_path=target_file.relative_path,
            language=target_file.language,
            file_type=target_file.file_type,
            rationale=target_file.rationale,
            match_reasons=list(target_file.match_reasons),
        )


class ChangeBatchLinkedDeliverableResponse(BaseModel):
    """One linked deliverable embedded in a Day07 batch snapshot."""

    deliverable_id: UUID
    title: str
    type: str
    current_version_number: int

    @classmethod
    def from_deliverable(
        cls,
        deliverable: ChangeBatchLinkedDeliverable,
    ) -> "ChangeBatchLinkedDeliverableResponse":
        """Convert one embedded deliverable snapshot into an API DTO."""

        return cls(
            deliverable_id=deliverable.deliverable_id,
            title=deliverable.title,
            type=deliverable.type.value,
            current_version_number=deliverable.current_version_number,
        )


class ChangeBatchDependencyResponse(BaseModel):
    """One task dependency shown inside the Day07 execution board."""

    task_id: UUID
    task_title: str
    in_batch: bool
    missing: bool
    order_index: int | None = None

    @classmethod
    def from_view(
        cls,
        dependency: ChangeBatchDependencyView,
    ) -> "ChangeBatchDependencyResponse":
        """Convert one service-layer dependency view into an API DTO."""

        return cls(
            task_id=dependency.task_id,
            task_title=dependency.task_title,
            in_batch=dependency.in_batch,
            missing=dependency.missing,
            order_index=dependency.order_index,
        )


class ChangeBatchTaskResponse(BaseModel):
    """One ordered task row returned with Day07 change-batch detail."""

    order_index: int
    task_id: UUID
    task_title: str
    task_priority: str
    task_risk_level: str
    change_plan_id: UUID
    change_plan_title: str
    selected_version_number: int
    intent_summary: str
    expected_actions: list[str]
    verification_commands: list[str]
    related_deliverables: list[ChangeBatchLinkedDeliverableResponse]
    dependencies: list[ChangeBatchDependencyResponse]
    target_files: list[ChangeBatchTargetFileResponse]
    overlap_file_paths: list[str]

    @classmethod
    def from_view(
        cls,
        item: ChangeBatchTaskView,
    ) -> "ChangeBatchTaskResponse":
        """Convert one service-layer task view into an API DTO."""

        return cls(
            order_index=item.order_index,
            task_id=item.task_id,
            task_title=item.task_title,
            task_priority=item.task_priority,
            task_risk_level=item.task_risk_level,
            change_plan_id=item.change_plan_id,
            change_plan_title=item.change_plan_title,
            selected_version_number=item.selected_version_number,
            intent_summary=item.intent_summary,
            expected_actions=list(item.expected_actions),
            verification_commands=list(item.verification_commands),
            related_deliverables=[
                ChangeBatchLinkedDeliverableResponse.from_deliverable(deliverable)
                for deliverable in item.related_deliverables
            ],
            dependencies=[
                ChangeBatchDependencyResponse.from_view(dependency)
                for dependency in item.dependencies
            ],
            target_files=[
                ChangeBatchTargetFileResponse.from_target_file(target_file)
                for target_file in item.target_files
            ],
            overlap_file_paths=list(item.overlap_file_paths),
        )


class ChangeBatchTargetFileAggregateResponse(BaseModel):
    """One repository-level file aggregate returned with Day07 batch detail."""

    relative_path: str
    language: str
    file_type: str
    match_reasons: list[str]
    rationales: list[str]
    task_ids: list[UUID]
    task_titles: list[str]
    change_plan_ids: list[UUID]
    change_plan_titles: list[str]
    overlap_count: int

    @classmethod
    def from_view(
        cls,
        item: ChangeBatchTargetFileView,
    ) -> "ChangeBatchTargetFileAggregateResponse":
        """Convert one aggregated file view into an API DTO."""

        return cls(
            relative_path=item.relative_path,
            language=item.language,
            file_type=item.file_type,
            match_reasons=list(item.match_reasons),
            rationales=list(item.rationales),
            task_ids=list(item.task_ids),
            task_titles=list(item.task_titles),
            change_plan_ids=list(item.change_plan_ids),
            change_plan_titles=list(item.change_plan_titles),
            overlap_count=item.overlap_count,
        )


class ChangeBatchTimelineEntryResponse(BaseModel):
    """One local Day07 timeline entry rendered in the repository board."""

    entry_type: str
    label: str
    summary: str
    occurred_at: datetime

    @classmethod
    def from_entry(
        cls,
        entry: ChangeBatchTimelineEntry,
    ) -> "ChangeBatchTimelineEntryResponse":
        """Convert one service-layer timeline entry into an API DTO."""

        return cls(
            entry_type=entry.entry_type,
            label=entry.label,
            summary=entry.summary,
            occurred_at=entry.occurred_at,
        )


class ChangeBatchSummaryResponse(BaseModel):
    """Project-scoped Day07 change-batch summary returned to the frontend."""

    id: UUID
    project_id: UUID
    repository_workspace_id: UUID | None = None
    status: ChangeBatchStatus
    title: str
    summary: str
    active: bool
    change_plan_count: int
    task_count: int
    target_file_count: int
    overlap_file_count: int
    dependency_count: int
    verification_command_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_summary(
        cls,
        item: ChangeBatchSummary,
    ) -> "ChangeBatchSummaryResponse":
        """Convert one Day07 service-layer summary into an API DTO."""

        return cls(
            id=item.change_batch.id,
            project_id=item.change_batch.project_id,
            repository_workspace_id=item.change_batch.repository_workspace_id,
            status=item.change_batch.status,
            title=item.change_batch.title,
            summary=item.change_batch.summary,
            active=item.active,
            change_plan_count=item.change_plan_count,
            task_count=item.task_count,
            target_file_count=item.target_file_count,
            overlap_file_count=item.overlap_file_count,
            dependency_count=item.dependency_count,
            verification_command_count=item.verification_command_count,
            created_at=item.change_batch.created_at,
            updated_at=item.change_batch.updated_at,
        )


class ChangeBatchDetailResponse(ChangeBatchSummaryResponse):
    """Full Day07 change-batch detail returned to the repository view."""

    tasks: list[ChangeBatchTaskResponse]
    target_files: list[ChangeBatchTargetFileAggregateResponse]
    overlap_files: list[ChangeBatchTargetFileAggregateResponse]
    timeline: list[ChangeBatchTimelineEntryResponse]

    @classmethod
    def from_detail(
        cls,
        detail: ChangeBatchDetail,
    ) -> "ChangeBatchDetailResponse":
        """Convert one Day07 service-layer detail into an API DTO."""

        summary = detail.summary
        return cls(
            id=summary.change_batch.id,
            project_id=summary.change_batch.project_id,
            repository_workspace_id=summary.change_batch.repository_workspace_id,
            status=summary.change_batch.status,
            title=summary.change_batch.title,
            summary=summary.change_batch.summary,
            active=summary.active,
            change_plan_count=summary.change_plan_count,
            task_count=summary.task_count,
            target_file_count=summary.target_file_count,
            overlap_file_count=summary.overlap_file_count,
            dependency_count=summary.dependency_count,
            verification_command_count=summary.verification_command_count,
            created_at=summary.change_batch.created_at,
            updated_at=summary.change_batch.updated_at,
            tasks=[ChangeBatchTaskResponse.from_view(item) for item in detail.tasks],
            target_files=[
                ChangeBatchTargetFileAggregateResponse.from_view(item)
                for item in detail.target_files
            ],
            overlap_files=[
                ChangeBatchTargetFileAggregateResponse.from_view(item)
                for item in detail.overlap_files
            ],
            timeline=[
                ChangeBatchTimelineEntryResponse.from_entry(item)
                for item in detail.timeline
            ],
        )


def get_repository_workspace_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> RepositoryWorkspaceService:
    """Create the Day01 repository-workspace dependency."""

    project_repository = ProjectRepository(session)
    return RepositoryWorkspaceService(
        project_repository=project_repository,
        repository_workspace_repository=RepositoryWorkspaceRepository(session),
    )


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


router = APIRouter(prefix="/repositories", tags=["repositories"])


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
    "/projects/{project_id}/context-pack",
    response_model=CodeContextPack,
    summary="Build one bounded Day05 CodeContextPack from selected repository files",
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


RepositoryTreeNodeResponse.model_rebuild()
