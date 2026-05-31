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
    PROJECT_STATUS_LABELS = {
        "active": "进行中",
        "on_hold": "已暂停",
        "completed": "已完成",
        "archived": "已归档",
    }
    PROJECT_STAGE_LABELS = {
        "intake": "立项受理",
        "planning": "方案规划",
        "execution": "执行推进",
        "verification": "验证确认",
        "delivery": "交付收口",
    }
    TASK_STATUS_LABELS = {
        "pending": "待处理",
        "running": "执行中",
        "paused": "已暂停",
        "waiting_human": "待人工处理",
        "completed": "已完成",
        "failed": "已失败",
        "blocked": "已阻塞",
    }
    TASK_PRIORITY_LABELS = {
        "low": "低",
        "normal": "中",
        "high": "高",
        "urgent": "紧急",
    }
    TASK_RISK_LABELS = {
        "low": "低",
        "normal": "中",
        "high": "高",
    }
    STAGE_OUTCOME_LABELS = {
        "applied": "已生效",
        "blocked": "被阻塞",
    }

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

        project_status_label = ProjectAISummaryService.PROJECT_STATUS_LABELS.get(
            project.status.value,
            project.status.value,
        )
        project_stage_label = ProjectAISummaryService.PROJECT_STAGE_LABELS.get(
            project.stage.value,
            project.stage.value,
        )

        current_focus_lines = (
            [
                (
                    f"- 《{task.title}》：状态为"
                    f"{ProjectAISummaryService.TASK_STATUS_LABELS.get(task.status.value, task.status.value)}，"
                    f"优先级为{ProjectAISummaryService.TASK_PRIORITY_LABELS.get(task.priority.value, task.priority.value)}，"
                    f"风险等级为{ProjectAISummaryService.TASK_RISK_LABELS.get(task.risk_level.value, task.risk_level.value)}。"
                    f"{task.input_summary}"
                )
                for task in top_tasks
            ]
            if top_tasks
            else ["- 当前没有未完成任务，项目已接近收尾或归档阶段。"]
        )

        stage_lines = [f"- 当前阶段：{project_stage_label}。"]
        if stage_guard is not None:
            next_stage = (
                ProjectAISummaryService.PROJECT_STAGE_LABELS.get(
                    stage_guard.target_stage.value,
                    stage_guard.target_stage.value,
                )
                if stage_guard.target_stage is not None
                else "暂无"
            )
            stage_lines.append(f"- 下一目标阶段：{next_stage}。")
            stage_lines.append(
                f"- 当前是否满足推进条件：{'可推进' if stage_guard.can_advance else '暂不可推进'}。"
            )
            if stage_guard.blocking_reasons:
                stage_lines.extend(
                    f"- 阶段阻塞原因：{reason}" for reason in stage_guard.blocking_reasons[:3]
                )
            elif stage_guard.can_advance:
                stage_lines.append("- 阶段守卫已通过，可进入下一阶段推进。")
        else:
            stage_lines.append("- 暂未获取到阶段守卫快照。")

        risk_lines = [
            f"- 当前阻塞任务数量：{stats.blocked_tasks}。",
            f"- 当前待人工处理任务数量：{stats.waiting_human_tasks}。",
        ]
        if stage_guard is not None and stage_guard.blocking_reasons:
            risk_lines.extend(
                f"- 阶段阻塞原因：{reason}" for reason in stage_guard.blocking_reasons[:3]
            )
        elif stage_guard is not None:
            risk_lines.append("- 当前未发现阶段阻塞原因。")
        else:
            risk_lines.append("- 暂未获取到阶段阻塞快照，请结合任务状态继续确认。")

        next_step_lines: list[str] = []
        if stage_guard is not None and stage_guard.blocking_reasons:
            next_step_lines.extend(
                f"- 优先解除阶段阻塞：{reason}。"
                for reason in stage_guard.blocking_reasons[:2]
            )
        if stats.blocked_tasks > 0:
            next_step_lines.append(f"- 优先处理阻塞任务，当前共有 {stats.blocked_tasks} 项。")
        if stats.waiting_human_tasks > 0:
            next_step_lines.append(
                f"- 跟进待人工处理事项，当前共有 {stats.waiting_human_tasks} 项。"
            )
        for task in top_tasks[:2]:
            next_step_lines.append(f"- 推进任务《{task.title}》。")
        if not next_step_lines:
            next_step_lines.append("- 保持当前节奏，并准备下一次评审或收尾动作。")

        recent_stage_text = (
            (
                "- 最新阶段变更："
                f"{ProjectAISummaryService.PROJECT_STAGE_LABELS.get(recent_timeline.from_stage.value, recent_timeline.from_stage.value) if recent_timeline.from_stage is not None else '无'}"
                f" → {ProjectAISummaryService.PROJECT_STAGE_LABELS.get(recent_timeline.to_stage.value, recent_timeline.to_stage.value)}，"
                f"结果为{ProjectAISummaryService.STAGE_OUTCOME_LABELS.get(recent_timeline.outcome.value, recent_timeline.outcome.value)}。"
            )
            if recent_timeline is not None
            else "- 最新阶段变更：暂无记录。"
        )

        lines = [
            "## 项目结论",
            (
                f"项目《{project.name}》当前处于{project_stage_label}阶段，"
                f"整体状态为{project_status_label}。{project.summary}"
            ),
            "",
            "## 当前状态",
            f"- 项目状态：{project_status_label}。",
            f"- 任务总数：{stats.total_tasks}。",
            f"- 已完成任务：{stats.completed_tasks}。",
            f"- 执行中任务：{stats.running_tasks}。",
            f"- 已阻塞任务：{stats.blocked_tasks}。",
            f"- 待人工处理任务：{stats.waiting_human_tasks}。",
            (
                f"- 最近一次任务更新时间：{stats.last_task_updated_at.isoformat()}。"
                if stats.last_task_updated_at is not None
                else "- 最近一次任务更新时间：暂无记录。"
            ),
            "",
            "## 当前重点",
            *current_focus_lines,
            "",
            "## 阶段进展",
            *stage_lines,
            recent_stage_text,
            "",
            "## 风险与阻塞",
            *risk_lines,
            "",
            "## 下一步建议",
            *next_step_lines[:4],
        ]
        return "\n".join(lines)
