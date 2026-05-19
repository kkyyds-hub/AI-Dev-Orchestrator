"""AI Project Director Confirmation Inbox service.

BCG-03 Phase1: read-only aggregation of pending confirmations.
No writes, no status changes, no task creation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.project_director_plan_version import PlanVersionStatus
from app.domain.project_director_session import ProjectDirectorSessionStatus
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)


@dataclass
class ConfirmationItem:
    """A single pending confirmation item in the inbox."""

    id: str  # composite: "{source_type}:{source_id}"
    source_type: str  # "goal_confirmation" | "plan_confirmation"
    source_id: UUID
    project_id: UUID | None
    session_id: UUID
    title: str
    summary: str
    status: str
    risk_level: str
    next_action: str
    confirm_api_hint: str
    created_at: str
    updated_at: str


def _iso(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.isoformat()


# ── Service ──────────────────────────────────────────────────────────


class ProjectDirectorConfirmationService:
    """Read-only aggregation of pending confirmations across sources."""

    def __init__(
        self,
        *,
        session_repository: ProjectDirectorSessionRepository,
        plan_version_repository: ProjectDirectorPlanVersionRepository,
    ) -> None:
        self._session_repo = session_repository
        self._plan_repo = plan_version_repository

    def get_all_confirmations(self) -> list[ConfirmationItem]:
        """Return all pending confirmations across all sources."""
        items: list[ConfirmationItem] = []
        items.extend(self._get_session_items())
        items.extend(self._get_plan_version_items())
        items.sort(key=lambda i: i.updated_at, reverse=True)
        return items

    def get_confirmations_by_project(
        self, project_id: UUID
    ) -> list[ConfirmationItem]:
        """Return pending confirmations filtered by project_id."""
        items: list[ConfirmationItem] = []
        items.extend(self._get_session_items(project_id=project_id))
        items.extend(self._get_plan_version_items(project_id=project_id))
        items.sort(key=lambda i: i.updated_at, reverse=True)
        return items

    def get_confirmations_by_session(
        self, session_id: UUID
    ) -> list[ConfirmationItem]:
        """Return pending confirmations filtered by session_id."""
        items: list[ConfirmationItem] = []
        items.extend(self._get_session_items(session_id=session_id))
        items.extend(self._get_plan_version_items(session_id=session_id))
        items.sort(key=lambda i: i.updated_at, reverse=True)
        return items

    # ── Private helpers ──────────────────────────────────────────────

    def _get_session_items(
        self,
        project_id: UUID | None = None,
        session_id: UUID | None = None,
    ) -> list[ConfirmationItem]:
        sessions = self._session_repo.list_by_status(
            ProjectDirectorSessionStatus.READY_TO_CONFIRM
        )
        items: list[ConfirmationItem] = []
        for s in sessions:
            if project_id is not None and s.project_id != project_id:
                continue
            if session_id is not None and s.id != session_id:
                continue
            total_q = len(s.clarifying_questions)
            answered_q = len(s.clarifying_answers)
            items.append(
                ConfirmationItem(
                    id=f"goal_confirmation:{s.id}",
                    source_type="goal_confirmation",
                    source_id=s.id,
                    project_id=s.project_id,
                    session_id=s.id,
                    title="目标确认",
                    summary=f"目标：{s.goal_text[:200]}（已答 {answered_q}/{total_q} 个澄清问题）",
                    status=s.status.value,
                    risk_level="normal",
                    next_action="审阅目标摘要后确认目标",
                    confirm_api_hint=f"POST /project-director/sessions/{s.id}/confirm",
                    created_at=_iso(s.created_at),
                    updated_at=_iso(s.updated_at),
                )
            )
        return items

    def _get_plan_version_items(
        self,
        project_id: UUID | None = None,
        session_id: UUID | None = None,
    ) -> list[ConfirmationItem]:
        plan_versions = self._plan_repo.list_by_status(
            PlanVersionStatus.PENDING_CONFIRMATION
        )
        items: list[ConfirmationItem] = []
        for pv in plan_versions:
            if project_id is not None and pv.project_id != project_id:
                continue
            if session_id is not None and pv.session_id != session_id:
                continue
            phase_count = len(pv.phases)
            task_count = len(pv.proposed_tasks)
            items.append(
                ConfirmationItem(
                    id=f"plan_confirmation:{pv.id}",
                    source_type="plan_confirmation",
                    source_id=pv.id,
                    project_id=pv.project_id,
                    session_id=pv.session_id,
                    title=f"计划版本 v{pv.version_no} 确认",
                    summary=(
                        f"计划包含 {phase_count} 个阶段、{task_count} 个建议任务。"
                        f"摘要：{pv.plan_summary[:200]}"
                    ),
                    status=pv.status.value,
                    risk_level="normal",
                    next_action="审阅计划版本后确认",
                    confirm_api_hint=(
                        f"POST /project-director/plan-versions/{pv.id}/confirm"
                    ),
                    created_at=_iso(pv.created_at),
                    updated_at=_iso(pv.updated_at),
                )
            )
        return items
