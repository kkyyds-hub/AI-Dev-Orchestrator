"""Read-only context builder for Project Director conversational messages.

Stage 7-B2 foundation: collect a compact, session-scoped context package for
provider-first chat responses. This service is read-only: it does not create
runs, dispatch workers, execute planning/apply, apply-local, or write repos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.domain.project_director_message import ProjectDirectorMessage
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.project_director_task_creation_repository import (
    ProjectDirectorTaskCreationRecordRepository,
)
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository


@dataclass(frozen=True, slots=True)
class ProjectDirectorConversationContext:
    """Compact context package passed to Project Director chat generation."""

    session_id: UUID
    project_id: UUID | None
    goal_text: str
    constraints: str
    session_status: str
    goal_summary: str
    confirmed_at: str | None = None
    clarifying_questions: list[dict[str, object]] = field(default_factory=list)
    clarifying_answers: list[dict[str, str]] = field(default_factory=list)
    recent_messages: list[ProjectDirectorMessage] = field(default_factory=list)
    latest_plan_version: dict[str, object] | None = None
    task_creation: dict[str, object] | None = None
    project_snapshot: dict[str, object] | None = None
    task_snapshot: dict[str, object] | None = None
    safety_boundary: list[str] = field(default_factory=list)


class ProjectDirectorContextBuilderService:
    """Build a read-only context package for one Project Director session."""

    DEFAULT_RECENT_MESSAGE_LIMIT = 20

    def __init__(
        self,
        *,
        session_repository: ProjectDirectorSessionRepository,
        message_repository: ProjectDirectorMessageRepository,
        plan_version_repository: ProjectDirectorPlanVersionRepository | None = None,
        task_creation_repository: ProjectDirectorTaskCreationRecordRepository
        | None = None,
        project_repository: ProjectRepository | None = None,
        task_repository: TaskRepository | None = None,
    ) -> None:
        self._session_repository = session_repository
        self._message_repository = message_repository
        self._plan_version_repository = plan_version_repository
        self._task_creation_repository = task_creation_repository
        self._project_repository = project_repository
        self._task_repository = task_repository

    def build_context(
        self,
        *,
        session_id: UUID,
        recent_message_limit: int = DEFAULT_RECENT_MESSAGE_LIMIT,
    ) -> ProjectDirectorConversationContext:
        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Project Director session {session_id} not found")

        safe_limit = max(1, min(recent_message_limit, 50))
        recent_messages, _ = self._message_repository.list_by_session_id(
            session_id=session_id,
            limit=safe_limit,
        )

        latest_plan_version = self._build_latest_plan_version(session_id=session_id)
        return ProjectDirectorConversationContext(
            session_id=session_obj.id,
            project_id=session_obj.project_id,
            goal_text=session_obj.goal_text,
            constraints=session_obj.constraints,
            session_status=session_obj.status.value,
            goal_summary=session_obj.goal_summary,
            confirmed_at=(
                session_obj.confirmed_at.isoformat()
                if session_obj.confirmed_at
                else None
            ),
            clarifying_questions=[
                {
                    "id": question.id,
                    "question": question.question,
                    "hint": question.hint,
                    "required": question.required,
                    "source": question.source,
                }
                for question in session_obj.clarifying_questions
            ],
            clarifying_answers=[
                {"question_id": answer.question_id, "answer": answer.answer}
                for answer in session_obj.clarifying_answers
            ],
            recent_messages=recent_messages,
            latest_plan_version=latest_plan_version,
            task_creation=self._build_task_creation_readback(
                latest_plan_version=latest_plan_version
            ),
            project_snapshot=self._build_project_snapshot(
                project_id=session_obj.project_id
            ),
            task_snapshot=self._build_task_snapshot(project_id=session_obj.project_id),
            safety_boundary=[
                "不启动 Worker",
                "不创建 Run",
                "不执行 planning/apply",
                "不执行 apply-local",
                "不写仓库",
                "不执行 suggested_actions",
            ],
        )

    def _build_latest_plan_version(
        self, *, session_id: UUID
    ) -> dict[str, object] | None:
        if self._plan_version_repository is None:
            return None
        versions = self._plan_version_repository.list_by_session_id(session_id)
        if not versions:
            return None
        latest = versions[0]
        return {
            "id": str(latest.id),
            "version_no": latest.version_no,
            "status": latest.status.value,
            "source": latest.source,
            "source_detail": latest.source_detail,
            "plan_summary": latest.plan_summary[:2000],
            "phases": [
                {
                    "sequence": phase.sequence,
                    "name": phase.name,
                    "goal": phase.goal,
                    "task_count_hint": phase.task_count_hint,
                }
                for phase in latest.phases[:8]
            ],
            "proposed_tasks": [
                {
                    "title": task.title,
                    "description": task.description[:500],
                    "suggested_role_code": task.suggested_role_code.value,
                    "priority_hint": task.priority_hint,
                }
                for task in latest.proposed_tasks[:12]
            ],
            "risks": latest.risks[:8],
            "acceptance_criteria": latest.acceptance_criteria[:8],
            "project_scope": latest.project_scope.model_dump(),
            "complexity_assessment": latest.complexity_assessment.model_dump(),
        }

    def _build_task_creation_readback(
        self, *, latest_plan_version: dict[str, object] | None
    ) -> dict[str, object] | None:
        if self._task_creation_repository is None or latest_plan_version is None:
            return None
        plan_version_id = latest_plan_version.get("id")
        if plan_version_id is None:
            return None
        try:
            record = self._task_creation_repository.get_by_plan_version_id(
                UUID(str(plan_version_id))
            )
        except ValueError:
            return None
        if record is None:
            return None

        project_name: str | None = None
        if self._project_repository is not None:
            project = self._project_repository.get_by_id(record.project_id)
            if project is not None:
                project_name = project.name

        return {
            "plan_version_id": str(record.plan_version_id),
            "project_id": str(record.project_id),
            "project_name": project_name,
            "version_no": record.version_no,
            "task_count": record.task_count,
            "created_task_ids": [str(task_id) for task_id in record.task_ids],
            "source_type": record.source_type,
            "status": "created",
            "created_at": record.created_at.isoformat(),
        }

    def _build_project_snapshot(
        self, *, project_id: UUID | None
    ) -> dict[str, object] | None:
        if project_id is None or self._project_repository is None:
            return None
        project = self._project_repository.get_by_id(project_id)
        if project is None:
            return None
        return {
            "id": str(project.id),
            "name": project.name,
            "summary": project.summary,
            "status": project.status.value,
            "stage": project.stage.value,
            "task_stats": project.task_stats.model_dump(),
        }

    def _build_task_snapshot(
        self, *, project_id: UUID | None
    ) -> dict[str, object] | None:
        if project_id is None or self._task_repository is None:
            return None
        tasks = self._task_repository.list_by_project_id(project_id)
        status_counts: dict[str, int] = {}
        for task in tasks:
            status_counts[task.status.value] = (
                status_counts.get(task.status.value, 0) + 1
            )
        return {
            "total": len(tasks),
            "status_counts": status_counts,
            "recent_tasks": [
                {
                    "id": str(task.id),
                    "title": task.title,
                    "status": task.status.value,
                    "risk_level": task.risk_level.value,
                    "owner_role_code": (
                        task.owner_role_code.value if task.owner_role_code else None
                    ),
                }
                for task in tasks[:10]
            ],
        }
