"""Service for project-level Project Director verification configs."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.project_director_verification_config import (
    ProjectDirectorVerificationConfig,
    VerificationConfigStatus,
)
from app.repositories.project_director_verification_config_repository import (
    ProjectDirectorVerificationConfigRepository,
)
from app.repositories.project_repository import ProjectRepository


@dataclass(slots=True)
class VerificationConfigReadResult:
    project_id: UUID
    config: ProjectDirectorVerificationConfig | None
    next_action: str


class ProjectDirectorVerificationConfigService:
    """Read/review project-level verification configs only."""

    def __init__(
        self,
        *,
        config_repo: ProjectDirectorVerificationConfigRepository,
        project_repo: ProjectRepository,
    ) -> None:
        self._config_repo = config_repo
        self._project_repo = project_repo

    def get_for_project(self, project_id: UUID) -> VerificationConfigReadResult:
        if not self._project_repo.exists(project_id):
            raise ValueError(f"Project {project_id} not found")

        config = self._config_repo.get_by_project_id(project_id)
        return VerificationConfigReadResult(
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
    ) -> VerificationConfigReadResult:
        if action not in {"confirm", "reject"}:
            raise ValueError("action must be 'confirm' or 'reject'")

        current = self.get_for_project(project_id).config
        if current is None:
            raise ValueError(f"Verification config for project {project_id} not found")

        if current.status != VerificationConfigStatus.PENDING_CONFIRMATION:
            raise ValueError(
                "Verification config has already been reviewed. "
                f"Current status: {current.status}."
            )

        next_status = (
            VerificationConfigStatus.CONFIRMED
            if action == "confirm"
            else VerificationConfigStatus.REJECTED
        )
        updated = self._config_repo.update_review(
            current.id,
            status=next_status,
            note=note,
        )
        return VerificationConfigReadResult(
            project_id=project_id,
            config=updated,
            next_action=self._next_action_for(updated),
        )

    @staticmethod
    def _next_action_for(config: ProjectDirectorVerificationConfig | None) -> str:
        if config is None:
            return "普通项目暂无 AI 主管验证机制配置。"
        if config.status == VerificationConfigStatus.PENDING_CONFIRMATION:
            return (
                "请在项目详情页确认或拒绝 AI 主管验证机制建议；"
                "确认后仍不会执行验证命令或创建 Run。"
            )
        if config.status == VerificationConfigStatus.CONFIRMED:
            return (
                "验证机制建议已确认；这只是项目级配置，"
                "不代表验证已执行或已通过，也不会创建 Run。"
            )
        if config.status == VerificationConfigStatus.REJECTED:
            return "验证机制建议已拒绝；历史配置保留为只读回溯。"
        return "验证机制配置状态未知，请人工复核。"
