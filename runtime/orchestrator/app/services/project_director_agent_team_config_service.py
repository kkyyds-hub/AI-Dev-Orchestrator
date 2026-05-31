"""Service for project-level Project Director agent team configs."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.project_director_agent_team_config import (
    AgentTeamConfigStatus,
    ProjectDirectorAgentTeamConfig,
)
from app.repositories.project_director_agent_team_config_repository import (
    ProjectDirectorAgentTeamConfigRepository,
)
from app.repositories.project_repository import ProjectRepository


@dataclass(slots=True)
class AgentTeamConfigReadResult:
    project_id: UUID
    config: ProjectDirectorAgentTeamConfig | None
    next_action: str


class ProjectDirectorAgentTeamConfigService:
    """Read/review project-level agent-team configs only."""

    def __init__(
        self,
        *,
        config_repo: ProjectDirectorAgentTeamConfigRepository,
        project_repo: ProjectRepository,
    ) -> None:
        self._config_repo = config_repo
        self._project_repo = project_repo

    def get_for_project(self, project_id: UUID) -> AgentTeamConfigReadResult:
        if not self._project_repo.exists(project_id):
            raise ValueError(f"Project {project_id} not found")

        config = self._config_repo.get_by_project_id(project_id)
        return AgentTeamConfigReadResult(
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
    ) -> AgentTeamConfigReadResult:
        if action not in {"confirm", "reject"}:
            raise ValueError("action must be 'confirm' or 'reject'")

        current = self.get_for_project(project_id).config
        if current is None:
            raise ValueError(f"Agent team config for project {project_id} not found")

        if current.status != AgentTeamConfigStatus.PENDING_CONFIRMATION:
            raise ValueError(
                "Agent team config has already been reviewed. "
                f"Current status: {current.status}."
            )

        next_status = (
            AgentTeamConfigStatus.CONFIRMED
            if action == "confirm"
            else AgentTeamConfigStatus.REJECTED
        )
        updated = self._config_repo.update_review(
            current.id,
            status=next_status,
            note=note,
        )
        return AgentTeamConfigReadResult(
            project_id=project_id,
            config=updated,
            next_action=self._next_action_for(updated),
        )

    @staticmethod
    def _next_action_for(config: ProjectDirectorAgentTeamConfig | None) -> str:
        if config is None:
            return "普通项目暂无 AI 主管 Agent 编队配置。"
        if config.status == AgentTeamConfigStatus.PENDING_CONFIRMATION:
            return "请在项目详情页确认或拒绝 AI 主管 Agent 编队建议；确认后仍不会自动启动 Worker。"
        if config.status == AgentTeamConfigStatus.CONFIRMED:
            return "Agent 编队已确认；这只是项目级配置，不代表已创建 Agent Session。"
        if config.status == AgentTeamConfigStatus.REJECTED:
            return "Agent 编队建议已拒绝；历史配置保留为只读回溯。"
        return "Agent 编队配置状态未知，请人工复核。"

