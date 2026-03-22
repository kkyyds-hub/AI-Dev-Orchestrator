"""Repository workspace service helpers for V4 Day01."""

from __future__ import annotations

from pathlib import Path
import tempfile
from uuid import UUID

from app.core.config import settings
from app.domain._base import utc_now
from app.domain.repository_workspace import RepositoryAccessMode, RepositoryWorkspace
from app.repositories.project_repository import ProjectRepository
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)


DEFAULT_REPOSITORY_IGNORE_RULE_SUMMARY = (
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
)


class RepositoryWorkspaceError(ValueError):
    """Base error raised by the repository-workspace service."""


class RepositoryWorkspaceProjectNotFoundError(RepositoryWorkspaceError):
    """Raised when binding one repository for a missing project."""


class RepositoryWorkspaceNotFoundError(RepositoryWorkspaceError):
    """Raised when one project has no bound repository workspace."""


class RepositoryWorkspacePathError(RepositoryWorkspaceError):
    """Raised when one candidate repository path violates Day01 boundaries."""


class RepositoryWorkspaceService:
    """Handle project-to-repository binding and path-safety validation."""

    def __init__(
        self,
        *,
        project_repository: ProjectRepository,
        repository_workspace_repository: RepositoryWorkspaceRepository,
    ) -> None:
        self.project_repository = project_repository
        self.repository_workspace_repository = repository_workspace_repository

    def bind_project_repository(
        self,
        project_id: UUID,
        *,
        root_path: str,
        display_name: str | None = None,
        access_mode: RepositoryAccessMode = RepositoryAccessMode.READ_ONLY,
        default_base_branch: str = "main",
        ignore_rule_summary: list[str] | None = None,
    ) -> RepositoryWorkspace:
        """Create or update one project's primary local repository entry."""

        if not self.project_repository.exists(project_id):
            raise RepositoryWorkspaceProjectNotFoundError(
                f"Project not found: {project_id}"
            )

        normalized_root_path = self._validate_and_resolve_root_path(root_path)
        existing_workspace = self.repository_workspace_repository.get_by_project_id(
            project_id
        )
        now = utc_now()
        workspace_payload = dict(
            project_id=project_id,
            root_path=str(normalized_root_path),
            display_name=self._resolve_display_name(
                display_name=display_name,
                root_path=normalized_root_path,
            ),
            access_mode=access_mode,
            default_base_branch=self._normalize_base_branch(default_base_branch),
            ignore_rule_summary=self._normalize_ignore_rule_summary(ignore_rule_summary),
            allowed_workspace_root=str(self._get_allowed_workspace_root()),
            created_at=(
                existing_workspace.created_at if existing_workspace is not None else now
            ),
            updated_at=now,
        )
        if existing_workspace is not None:
            workspace_payload["id"] = existing_workspace.id

        workspace = RepositoryWorkspace(**workspace_payload)

        return self.repository_workspace_repository.upsert(workspace)

    def get_project_repository(self, project_id: UUID) -> RepositoryWorkspace | None:
        """Return one project's bound repository workspace, if present."""

        if not self.project_repository.exists(project_id):
            raise RepositoryWorkspaceProjectNotFoundError(
                f"Project not found: {project_id}"
            )

        return self.repository_workspace_repository.get_by_project_id(project_id)

    def unbind_project_repository(self, project_id: UUID) -> RepositoryWorkspace:
        """Remove one project's primary repository binding."""

        if not self.project_repository.exists(project_id):
            raise RepositoryWorkspaceProjectNotFoundError(
                f"Project not found: {project_id}"
            )

        removed_workspace = self.repository_workspace_repository.delete_by_project_id(
            project_id
        )
        if removed_workspace is None:
            raise RepositoryWorkspaceNotFoundError(
                f"Repository workspace not found for project: {project_id}"
            )

        return removed_workspace

    @staticmethod
    def _resolve_display_name(*, display_name: str | None, root_path: Path) -> str:
        """Build one stable display name from request data or the folder name."""

        if display_name is not None and display_name.strip():
            return display_name.strip()

        return root_path.name or str(root_path)

    @staticmethod
    def _normalize_base_branch(default_base_branch: str) -> str:
        """Trim one optional base-branch value and apply the Day01 default."""

        normalized_value = default_base_branch.strip()
        return normalized_value or "main"

    @staticmethod
    def _normalize_ignore_rule_summary(
        ignore_rule_summary: list[str] | None,
    ) -> list[str]:
        """Apply the Day01 default ignore summary when the caller omits it."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for item in ignore_rule_summary or []:
            normalized_item = item.strip()
            if not normalized_item or normalized_item in seen_items:
                continue

            normalized_items.append(normalized_item)
            seen_items.add(normalized_item)

        if normalized_items:
            return normalized_items

        return list(DEFAULT_REPOSITORY_IGNORE_RULE_SUMMARY)

    def _validate_and_resolve_root_path(self, root_path: str) -> Path:
        """Normalize and validate one candidate local repository path."""

        normalized_input = root_path.strip()
        if not normalized_input:
            raise RepositoryWorkspacePathError("Repository root_path cannot be blank.")

        candidate_path = Path(normalized_input).expanduser()
        if not candidate_path.is_absolute():
            raise RepositoryWorkspacePathError(
                "Repository root_path must be an absolute local path."
            )

        try:
            resolved_root_path = candidate_path.resolve(strict=True)
        except FileNotFoundError as exc:
            raise RepositoryWorkspacePathError(
                "Repository root_path does not exist."
            ) from exc

        if not resolved_root_path.is_dir():
            raise RepositoryWorkspacePathError(
                "Repository root_path must point to one local directory."
            )

        allowed_workspace_root = self._get_allowed_workspace_root()
        try:
            resolved_root_path.relative_to(allowed_workspace_root)
        except ValueError as exc:
            raise RepositoryWorkspacePathError(
                "Repository root_path exceeds the configured allowed workspace root."
            ) from exc

        runtime_data_dir = settings.runtime_data_dir.resolve(strict=False)
        if (
            resolved_root_path == runtime_data_dir
            or runtime_data_dir in resolved_root_path.parents
        ):
            raise RepositoryWorkspacePathError(
                "Repository root_path cannot point inside the orchestrator runtime data directory."
            )

        system_temp_dir = Path(tempfile.gettempdir()).resolve(strict=False)
        if (
            resolved_root_path == system_temp_dir
            or system_temp_dir in resolved_root_path.parents
        ):
            raise RepositoryWorkspacePathError(
                "Repository root_path cannot point inside the system temporary directory."
            )

        if not (resolved_root_path / ".git").exists():
            raise RepositoryWorkspacePathError(
                "Repository root_path must point to one local Git repository root."
            )

        return resolved_root_path

    @staticmethod
    def _get_allowed_workspace_root() -> Path:
        """Return the configured Day01 workspace boundary as one existing directory."""

        candidate_root = settings.repository_workspace_root_dir
        if not candidate_root.exists():
            raise RepositoryWorkspacePathError(
                "Configured allowed workspace root does not exist."
            )
        if not candidate_root.is_dir():
            raise RepositoryWorkspacePathError(
                "Configured allowed workspace root must be a directory."
            )

        return candidate_root.resolve(strict=True)
