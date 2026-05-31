"""Project AI summary generation and readback service."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from app.domain.project_ai_summary import ProjectAISummary
from app.domain.run_ai_summary import RunAISummarySource, RunAISummaryStatus
from app.domain.task import TaskPriority, TaskStatus
from app.repositories.project_ai_summary_repository import ProjectAISummaryRepository
from app.services.project_service import ProjectDetail, ProjectService


class ProjectAISummaryProjectNotFoundError(ValueError):
    """Raised when a requested project does not exist."""


@dataclass(frozen=True, slots=True)
class ProjectAISummaryContext:
    detail: ProjectDetail
    source_fingerprint: str
    prompt_hash: str
    summary_markdown: str


class ProjectAISummaryService:
    """Build and persist project-level summaries without calling AI providers."""

    SOURCE_VERSION = "project.summary.v1"
    MODEL_PROVIDER = "local_rule_engine"
    MODEL_NAME = "project_summary.rule_fallback.v1"

    def __init__(
        self,
        *,
        project_service: ProjectService,
        project_ai_summary_repository: ProjectAISummaryRepository,
    ) -> None:
        self.project_service = project_service
        self.project_ai_summary_repository = project_ai_summary_repository

    def get_active_summary(self, *, project_id: UUID) -> ProjectAISummary | None:
        self._require_project(project_id)
        return self.project_ai_summary_repository.get_active_by_project_id(project_id)

    def generate_project_summary(
        self,
        *,
        project_id: UUID,
        regenerate: bool = False,
    ) -> ProjectAISummary:
        context = self._build_context(project_id)
        if not regenerate:
            active = self.project_ai_summary_repository.get_active_by_project_id(project_id)
            if active is not None and active.source_fingerprint == context.source_fingerprint:
                return active

        if regenerate:
            self.project_ai_summary_repository.mark_active_stale(project_id)

        return self.project_ai_summary_repository.create(
            ProjectAISummary(
                project_id=project_id,
                status=RunAISummaryStatus.SUCCEEDED,
                source=RunAISummarySource.RULE_FALLBACK,
                summary_markdown=context.summary_markdown,
                source_version=self.SOURCE_VERSION,
                source_fingerprint=context.source_fingerprint,
                source_hash=context.source_fingerprint,
                model_provider=self.MODEL_PROVIDER,
                model_name=self.MODEL_NAME,
                prompt_hash=context.prompt_hash,
                provider_receipt_id=None,
                error_summary=None,
                stale=False,
            )
        )

    def regenerate_project_summary(self, *, project_id: UUID) -> ProjectAISummary:
        return self.generate_project_summary(project_id=project_id, regenerate=True)

    def _require_project(self, project_id: UUID) -> ProjectDetail:
        detail = self.project_service.get_project_detail(project_id)
        if detail is None:
            raise ProjectAISummaryProjectNotFoundError(f"Project not found: {project_id}")
        return detail

    def _build_context(self, project_id: UUID) -> ProjectAISummaryContext:
        detail = self._require_project(project_id)
        source_payload = self._build_source_payload(detail)
        source_json = json.dumps(source_payload, sort_keys=True, default=str, ensure_ascii=False)
        source_fingerprint = sha256(source_json.encode("utf-8")).hexdigest()
        prompt_hash = sha256(
            f"{self.SOURCE_VERSION}:rule-fallback:{source_fingerprint}".encode("utf-8")
        ).hexdigest()
        return ProjectAISummaryContext(
            detail=detail,
            source_fingerprint=source_fingerprint,
            prompt_hash=prompt_hash,
            summary_markdown=self._build_markdown(detail),
        )

    @staticmethod
    def _build_source_payload(detail: ProjectDetail) -> dict[str, object]:
        project = detail.project
        stats = project.task_stats
        return {
            "project": {
                "id": str(project.id),
                "name": project.name,
                "summary": project.summary,
                "status": project.status.value,
                "stage": project.stage.value,
                "updated_at": project.updated_at.isoformat(),
            },
            "task_stats": stats.model_dump(mode="json"),
            "tasks": [
                {
                    "id": str(item.task.id),
                    "title": item.task.title,
                    "status": item.task.status.value,
                    "priority": item.task.priority.value,
                    "risk_level": item.task.risk_level.value,
                    "human_status": item.task.human_status.value,
                    "input_summary": item.task.input_summary,
                    "updated_at": item.task.updated_at.isoformat(),
                }
                for item in detail.task_tree
            ],
            "stage_guard": (
                detail.stage_guard.model_dump(mode="json")
                if detail.stage_guard is not None
                else None
            ),
            "stage_timeline_count": len(detail.stage_timeline or []),
        }

    @staticmethod
    def _build_markdown(detail: ProjectDetail) -> str:
        project = detail.project
        stats = project.task_stats
        active_tasks = [
            item.task
            for item in detail.task_tree
            if item.task.status != TaskStatus.COMPLETED
        ]
        recent_timeline = max(
            detail.stage_timeline or [],
            key=lambda entry: entry.created_at,
            default=None,
        )
        stage_guard = detail.stage_guard

        priority_rank = {
            TaskPriority.URGENT: 0,
            TaskPriority.HIGH: 1,
            TaskPriority.NORMAL: 2,
            TaskPriority.LOW: 3,
        }
        status_rank = {
            TaskStatus.BLOCKED: 0,
            TaskStatus.FAILED: 1,
            TaskStatus.WAITING_HUMAN: 2,
            TaskStatus.RUNNING: 3,
            TaskStatus.PAUSED: 4,
            TaskStatus.PENDING: 5,
            TaskStatus.COMPLETED: 6,
        }
        top_tasks = sorted(
            active_tasks,
            key=lambda task: (
                status_rank.get(task.status, 99),
                priority_rank.get(task.priority, 99),
                -task.updated_at.timestamp(),
            ),
        )[:3]

        current_focus_lines = (
            [
                (
                    f"- {task.title} "
                    f"(status={task.status.value}, priority={task.priority.value}, risk={task.risk_level.value}): "
                    f"{task.input_summary}"
                )
                for task in top_tasks
            ]
            if top_tasks
            else ["- No active tasks remain; the project is closer to wrap-up or archive."]
        )

        stage_lines = [f"- Current stage: {project.stage.value}"]
        if stage_guard is not None:
            next_stage = stage_guard.target_stage.value if stage_guard.target_stage is not None else "none"
            stage_lines.append(f"- Next stage: {next_stage}")
            stage_lines.append(f"- Can advance now: {'yes' if stage_guard.can_advance else 'no'}")
            if stage_guard.blocking_reasons:
                stage_lines.extend(
                    f"- Blocking reason: {reason}" for reason in stage_guard.blocking_reasons[:3]
                )
            elif stage_guard.can_advance:
                stage_lines.append("- Stage guard is clear and ready for the next transition.")
        else:
            stage_lines.append("- Stage guard snapshot is unavailable.")

        next_step_lines: list[str] = []
        if stage_guard is not None and stage_guard.blocking_reasons:
            next_step_lines.extend(
                f"- Resolve stage blocker: {reason}" for reason in stage_guard.blocking_reasons[:2]
            )
        if stats.blocked_tasks > 0:
            next_step_lines.append(f"- Clear blocked tasks first (currently {stats.blocked_tasks}).")
        if stats.waiting_human_tasks > 0:
            next_step_lines.append(
                f"- Follow up waiting_human tasks (currently {stats.waiting_human_tasks})."
            )
        for task in top_tasks[:2]:
            next_step_lines.append(f"- Advance task: {task.title}.")
        if not next_step_lines:
            next_step_lines.append("- Keep the current pace and prepare the next review or closeout step.")

        recent_stage_text = (
            (
                "- Latest stage transition: "
                f"{recent_timeline.from_stage.value if recent_timeline.from_stage is not None else 'none'} "
                f"-> {recent_timeline.to_stage.value} "
                f"(outcome={recent_timeline.outcome.value})"
            )
            if recent_timeline is not None
            else "- Latest stage transition: none recorded."
        )

        lines = [
            "## Project Conclusion",
            project.summary,
            "",
            "## Current Status",
            f"- Project status: {project.status.value}",
            f"- Total tasks: {stats.total_tasks}",
            f"- Completed tasks: {stats.completed_tasks}",
            f"- Running tasks: {stats.running_tasks}",
            f"- Blocked tasks: {stats.blocked_tasks}",
            f"- Waiting human tasks: {stats.waiting_human_tasks}",
            (
                f"- Latest task update: {stats.last_task_updated_at.isoformat()}"
                if stats.last_task_updated_at is not None
                else "- Latest task update: none"
            ),
            "",
            "## Current Focus",
            *current_focus_lines,
            "",
            "## Stage Progress",
            *stage_lines,
            recent_stage_text,
            "",
            "## Next Steps",
            *next_step_lines[:4],
        ]
        return "\n".join(lines)
