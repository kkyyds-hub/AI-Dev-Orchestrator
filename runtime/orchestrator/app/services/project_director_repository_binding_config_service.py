"""Service for project-level Project Director repository binding configs."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.project_director_repository_binding_config import (
    ProjectDirectorRepositoryBindingConfig,
    RepositoryBindingConfigStatus,
)
from app.repositories.project_director_repository_binding_config_repository import (
    ProjectDirectorRepositoryBindingConfigRepository,
)
from app.repositories.project_repository import ProjectRepository


@dataclass(slots=True)
class RepositoryBindingConfigReadResult:
    project_id: UUID
    config: ProjectDirectorRepositoryBindingConfig | None
    next_action: str


class ProjectDirectorRepositoryBindingConfigService:
    """Read/review project-level repository-binding configs only."""

    def __init__(
        self,
        *,
        config_repo: ProjectDirectorRepositoryBindingConfigRepository,
        project_repo: ProjectRepository,
    ) -> None:
        self._config_repo = config_repo
        self._project_repo = project_repo

    def get_for_project(self, project_id: UUID) -> RepositoryBindingConfigReadResult:
        if not self._project_repo.exists(project_id):
            raise ValueError(f"Project {project_id} not found")

        config = self._config_repo.get_by_project_id(project_id)
        return RepositoryBindingConfigReadResult(
            project_id=project_id,
            config=config,
            next_action=self._next_action_for(config),
        )

    def review_project_config(
        self,
        project_id: UUID,
        *,
        action: str,
        note: str = "",
    ) -> RepositoryBindingConfigReadResult:
        if action not in {"confirm", "reject"}:
            raise ValueError("action must be 'confirm' or 'reject'")

        current = self.get_for_project(project_id).config
        if current is None:
            raise ValueError(
                f"Repository binding config for project {project_id} not found"
            )

        if current.status != RepositoryBindingConfigStatus.PENDING_CONFIRMATION:
            raise ValueError(
                "Repository binding config has already been reviewed. "
                f"Current status: {current.status}."
            )

        next_status = (
            RepositoryBindingConfigStatus.CONFIRMED
            if action == "confirm"
            else RepositoryBindingConfigStatus.REJECTED
        )
        updated = self._config_repo.update_review(
            current.id,
            status=next_status,
            note=note,
        )
        return RepositoryBindingConfigReadResult(
            project_id=project_id,
            config=updated,
            next_action=self._next_action_for(updated),
        )

    @staticmethod
    def _next_action_for(
        config: ProjectDirectorRepositoryBindingConfig | None,
    ) -> str:
        if config is None:
            return "普通项目暂无 AI 主管仓库绑定配置。"
        if config.status == RepositoryBindingConfigStatus.PENDING_CONFIRMATION:
            return (
                "请在项目详情页确认或拒绝 AI 主管仓库绑定建议；"
                "确认后仍不会创建真实仓库绑定或写入仓库。"
            )
        if config.status == RepositoryBindingConfigStatus.CONFIRMED:
            return (
                "仓库绑定建议已确认；这只是项目级配置，"
                "不代表已创建真实 RepositoryWorkspace 或执行 git 操作。"
            )
        if config.status == RepositoryBindingConfigStatus.REJECTED:
            return "仓库绑定建议已拒绝；历史配置保留为只读回溯。"
        return "仓库绑定配置状态未知，请人工复核。"
