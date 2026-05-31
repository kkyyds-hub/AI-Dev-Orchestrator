"""Service for project-level Project Director skill binding configs."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.project_director_skill_binding_config import (
    ProjectDirectorSkillBindingConfig,
    SkillBindingConfigStatus,
)
from app.repositories.project_director_skill_binding_config_repository import (
    ProjectDirectorSkillBindingConfigRepository,
)
from app.repositories.project_repository import ProjectRepository


@dataclass(slots=True)
class SkillBindingConfigReadResult:
    project_id: UUID
    config: ProjectDirectorSkillBindingConfig | None
    next_action: str


class ProjectDirectorSkillBindingConfigService:
    """Read/review project-level skill-binding configs only."""

    def __init__(
        self,
        *,
        config_repo: ProjectDirectorSkillBindingConfigRepository,
        project_repo: ProjectRepository,
    ) -> None:
        self._config_repo = config_repo
        self._project_repo = project_repo

    def get_for_project(self, project_id: UUID) -> SkillBindingConfigReadResult:
        if not self._project_repo.exists(project_id):
            raise ValueError(f"Project {project_id} not found")

        config = self._config_repo.get_by_project_id(project_id)
        return SkillBindingConfigReadResult(
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
    ) -> SkillBindingConfigReadResult:
        if action not in {"confirm", "reject"}:
            raise ValueError("action must be 'confirm' or 'reject'")

        current = self.get_for_project(project_id).config
        if current is None:
            raise ValueError(f"Skill binding config for project {project_id} not found")

        if current.status != SkillBindingConfigStatus.PENDING_CONFIRMATION:
            raise ValueError(
                "Skill binding config has already been reviewed. "
                f"Current status: {current.status}."
            )

        next_status = (
            SkillBindingConfigStatus.CONFIRMED
            if action == "confirm"
            else SkillBindingConfigStatus.REJECTED
        )
        updated = self._config_repo.update_review(
            current.id,
            status=next_status,
            note=note,
        )
        return SkillBindingConfigReadResult(
            project_id=project_id,
            config=updated,
            next_action=self._next_action_for(updated),
        )

    @staticmethod
    def _next_action_for(config: ProjectDirectorSkillBindingConfig | None) -> str:
        if config is None:
            return "?????? AI ?? Skill ?????"
        if config.status == SkillBindingConfigStatus.PENDING_CONFIRMATION:
            return "???????????? AI ?? Skill ??????????????? Skill ???????? Worker ???"
        if config.status == SkillBindingConfigStatus.CONFIRMED:
            return "Skill ???????????????????? Skill ???????"
        if config.status == SkillBindingConfigStatus.REJECTED:
            return "Skill ????????????????????"
        return "Skill ???????????????"
