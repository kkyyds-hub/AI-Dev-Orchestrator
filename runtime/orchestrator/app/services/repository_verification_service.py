"""Business services for V4 Day09 repository verification baselines."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.domain._base import utc_now
from app.domain.repository_verification import (
    RepositoryVerificationBaseline,
    RepositoryVerificationCategory,
    RepositoryVerificationTemplate,
    RepositoryVerificationTemplateReference,
)
from app.repositories.project_repository import ProjectRepository
from app.repositories.repository_verification_repository import (
    RepositoryVerificationRepository,
)
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)


_CATEGORY_ORDER = (
    RepositoryVerificationCategory.BUILD,
    RepositoryVerificationCategory.TEST,
    RepositoryVerificationCategory.LINT,
    RepositoryVerificationCategory.TYPECHECK,
)


class RepositoryVerificationError(ValueError):
    """Base error raised by the Day09 repository-verification service."""


class RepositoryVerificationProjectNotFoundError(RepositoryVerificationError):
    """Raised when the target project cannot be resolved."""


class RepositoryVerificationWorkspaceNotFoundError(RepositoryVerificationError):
    """Raised when Day09 is requested before Day01 repository binding exists."""


class RepositoryVerificationTemplateConfigError(RepositoryVerificationError):
    """Raised when the requested Day09 baseline payload is invalid."""


class RepositoryVerificationTemplateNotFoundError(RepositoryVerificationError):
    """Raised when a change plan references a missing verification template."""


class RepositoryVerificationService:
    """Create, update and resolve Day09 repository verification baselines."""

    def __init__(
        self,
        *,
        project_repository: ProjectRepository,
        repository_workspace_repository: RepositoryWorkspaceRepository,
        repository_verification_repository: RepositoryVerificationRepository,
    ) -> None:
        self.project_repository = project_repository
        self.repository_workspace_repository = repository_workspace_repository
        self.repository_verification_repository = repository_verification_repository

    def get_or_create_project_baseline(
        self,
        project_id: UUID,
    ) -> RepositoryVerificationBaseline:
        """Return one project's Day09 baseline, auto-seeding default templates if needed."""

        workspace = self._require_workspace(project_id)
        templates = self.repository_verification_repository.list_by_project_id(project_id)
        if not templates:
            templates = self.repository_verification_repository.replace_for_project(
                project_id,
                self._build_default_templates(
                    project_id=project_id,
                    repository_root_path=Path(workspace.root_path),
                ),
            )

        return RepositoryVerificationBaseline(
            project_id=project_id,
            templates=templates,
        )

    def replace_project_baseline(
        self,
        project_id: UUID,
        *,
        templates: list[RepositoryVerificationTemplate],
    ) -> RepositoryVerificationBaseline:
        """Replace one project's full Day09 baseline after validating it."""

        workspace = self._require_workspace(project_id)
        normalized_templates = self._normalize_templates(
            project_id=project_id,
            repository_root_path=Path(workspace.root_path),
            templates=templates,
        )
        persisted_templates = self.repository_verification_repository.replace_for_project(
            project_id,
            normalized_templates,
        )
        return RepositoryVerificationBaseline(
            project_id=project_id,
            templates=persisted_templates,
        )

    def resolve_template_references(
        self,
        project_id: UUID,
        template_ids: list[UUID],
    ) -> list[RepositoryVerificationTemplateReference]:
        """Resolve one ordered Day09 template-reference list for plans or batches."""

        unique_template_ids = list(dict.fromkeys(template_ids))
        if not unique_template_ids:
            return []

        template_map = self.repository_verification_repository.get_by_ids_for_project(
            project_id,
            unique_template_ids,
        )
        missing_ids = [
            template_id
            for template_id in unique_template_ids
            if template_id not in template_map
        ]
        if missing_ids:
            raise RepositoryVerificationTemplateNotFoundError(
                "Repository verification template not found: "
                + ", ".join(str(template_id) for template_id in missing_ids)
            )

        return [
            self._to_reference(template_map[template_id])
            for template_id in unique_template_ids
        ]

    def _require_workspace(self, project_id: UUID):
        """Validate the project exists and has a bound repository workspace."""

        if not self.project_repository.exists(project_id):
            raise RepositoryVerificationProjectNotFoundError(
                f"Project not found: {project_id}"
            )

        workspace = self.repository_workspace_repository.get_by_project_id(project_id)
        if workspace is None:
            raise RepositoryVerificationWorkspaceNotFoundError(
                f"Repository workspace not found for project: {project_id}"
            )

        return workspace

    def _normalize_templates(
        self,
        *,
        project_id: UUID,
        repository_root_path: Path,
        templates: list[RepositoryVerificationTemplate],
    ) -> list[RepositoryVerificationTemplate]:
        """Validate one full Day09 baseline payload and normalize timestamps."""

        if not templates:
            raise RepositoryVerificationTemplateConfigError(
                "Repository verification baseline requires at least one template."
            )

        categories = [template.category for template in templates]
        if set(categories) != set(_CATEGORY_ORDER):
            raise RepositoryVerificationTemplateConfigError(
                "Repository verification baseline must contain build / test / lint / typecheck exactly once."
            )

        if len(categories) != len(set(categories)):
            raise RepositoryVerificationTemplateConfigError(
                "Repository verification baseline cannot repeat categories."
            )

        now = utc_now()
        persisted_templates = {
            template.category: template
            for template in self.repository_verification_repository.list_by_project_id(project_id)
        }
        normalized_templates: list[RepositoryVerificationTemplate] = []

        for template in templates:
            normalized_working_directory = self._validate_working_directory(
                repository_root_path=repository_root_path,
                working_directory=template.working_directory,
            )
            existing_template = persisted_templates.get(template.category)
            normalized_templates.append(
                RepositoryVerificationTemplate(
                    id=existing_template.id if existing_template is not None else template.id,
                    project_id=project_id,
                    category=template.category,
                    name=template.name,
                    command=template.command,
                    working_directory=normalized_working_directory,
                    timeout_seconds=template.timeout_seconds,
                    enabled_by_default=template.enabled_by_default,
                    description=template.description,
                    created_at=(
                        existing_template.created_at
                        if existing_template is not None
                        else template.created_at
                    ),
                    updated_at=now,
                )
            )

        return sorted(
            normalized_templates,
            key=lambda item: _CATEGORY_ORDER.index(item.category),
        )

    def _build_default_templates(
        self,
        *,
        project_id: UUID,
        repository_root_path: Path,
    ) -> list[RepositoryVerificationTemplate]:
        """Return the minimal Day09 default baseline for this repository."""

        now = utc_now()
        defaults = [
            RepositoryVerificationTemplate(
                project_id=project_id,
                category=RepositoryVerificationCategory.BUILD,
                name="前端构建",
                command="npm run build",
                working_directory="apps/web",
                timeout_seconds=900,
                enabled_by_default=True,
                description="执行 apps/web 的 TypeScript + Vite 构建基线。",
                created_at=now,
                updated_at=now,
            ),
            RepositoryVerificationTemplate(
                project_id=project_id,
                category=RepositoryVerificationCategory.TEST,
                name="仓库烟测",
                command="python runtime/orchestrator/scripts/v4b_day08_preflight_guard_smoke.py",
                working_directory=".",
                timeout_seconds=900,
                enabled_by_default=True,
                description="运行当前仓库已有的 Day08 端到端烟测脚本。",
                created_at=now,
                updated_at=now,
            ),
            RepositoryVerificationTemplate(
                project_id=project_id,
                category=RepositoryVerificationCategory.LINT,
                name="后端源码编译检查",
                command="python -m compileall -q runtime/orchestrator/app runtime/orchestrator/scripts",
                working_directory=".",
                timeout_seconds=600,
                enabled_by_default=True,
                description="当前仓库未引入专用 lint 工具，先以 Python 源码编译检查承接 lint 类基线。",
                created_at=now,
                updated_at=now,
            ),
            RepositoryVerificationTemplate(
                project_id=project_id,
                category=RepositoryVerificationCategory.TYPECHECK,
                name="前端类型检查",
                command="npx tsc --noEmit",
                working_directory="apps/web",
                timeout_seconds=600,
                enabled_by_default=True,
                description="在 apps/web 执行前端 TypeScript 类型检查。",
                created_at=now,
                updated_at=now,
            ),
        ]

        return self._normalize_templates(
            project_id=project_id,
            repository_root_path=repository_root_path,
            templates=defaults,
        )

    @staticmethod
    def _validate_working_directory(
        *,
        repository_root_path: Path,
        working_directory: str,
    ) -> str:
        """Ensure the configured working directory exists inside the repository."""

        if working_directory == ".":
            target_path = repository_root_path
        else:
            target_path = (repository_root_path / working_directory).resolve(strict=False)

        repository_root_path = repository_root_path.resolve(strict=True)
        try:
            target_path.relative_to(repository_root_path)
        except ValueError as exc:
            raise RepositoryVerificationTemplateConfigError(
                "Repository verification working_directory must stay inside the repository root."
            ) from exc

        if not target_path.exists() or not target_path.is_dir():
            raise RepositoryVerificationTemplateConfigError(
                f"Repository verification working_directory does not exist: {working_directory}"
            )

        return working_directory

    @staticmethod
    def _to_reference(
        template: RepositoryVerificationTemplate,
    ) -> RepositoryVerificationTemplateReference:
        """Project one persisted template into a lightweight reference payload."""

        return RepositoryVerificationTemplateReference(
            id=template.id,
            category=template.category,
            name=template.name,
            command=template.command,
            working_directory=template.working_directory,
            timeout_seconds=template.timeout_seconds,
            enabled_by_default=template.enabled_by_default,
            description=template.description,
        )
