"""Repository workspace, snapshot, change-session and Day05 locator endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain.change_session import (
    ChangeSession,
    ChangeSessionDirtyFile,
    ChangeSessionDirtyFileScope,
    ChangeSessionGuardStatus,
    ChangeSessionWorkspaceStatus,
)
from app.domain.code_context_pack import CodeContextPack, FileLocatorResult
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
from app.repositories.change_session_repository import ChangeSessionRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.run_repository import RunRepository
from app.repositories.repository_snapshot_repository import (
    RepositorySnapshotRepository,
)
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)
from app.repositories.task_repository import TaskRepository
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
