"""Build a minimal task-scoped execution context package before worker execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.project import Project, ProjectStage
from app.domain.project_role import ProjectRoleConfig
from app.domain.run import RunFailureCategory, RunStatus
from app.domain.task import (
    Task,
    TaskHumanStatus,
    TaskPriority,
    TaskRiskLevel,
)
from app.repositories.run_repository import RunRepository
from app.services.project_memory_service import (
    ProjectMemoryItem,
    ProjectMemoryService,
    TaskProjectMemoryContext,
)
from app.services.task_readiness_service import (
    TaskBlockingSignal,
    TaskDependencyReadinessItem,
    TaskReadinessService,
)


_RECENT_RUN_LIMIT = 3
_CONTEXT_SUMMARY_MAX_LENGTH = 1_200


@dataclass(slots=True, frozen=True)
class ContextRecentRunItem:
    """A compact excerpt from one previous run of the same task."""

    run_id: UUID
    status: RunStatus
    result_summary: str | None
    verification_summary: str | None
    failure_category: RunFailureCategory | None
    created_at: datetime


@dataclass(slots=True, frozen=True)
class TaskContextPackage:
    """Minimal context package assembled right before execution."""

    task_id: UUID
    task_title: str
    input_summary: str
    acceptance_criteria: list[str]
    priority: TaskPriority
    risk_level: TaskRiskLevel
    human_status: TaskHumanStatus
    paused_reason: str | None
    ready_for_execution: bool
    blocking_signals: list[TaskBlockingSignal]
    blocking_reasons: list[str]
    dependency_items: list[TaskDependencyReadinessItem]
    recent_runs: list[ContextRecentRunItem]
    context_summary: str


@dataclass(slots=True, frozen=True)
class ProjectStageContextRoleItem:
    """One role item included in the project-stage SOP context."""

    role_code: str
    role_name: str
    enabled: bool


@dataclass(slots=True, frozen=True)
class ProjectStageContextTaskItem:
    """One task item included in the project-stage SOP context."""

    task_id: UUID
    title: str
    status: str


@dataclass(slots=True, frozen=True)
class ProjectStageContextPackage:
    """Compact SOP context describing the current project stage."""

    project_id: UUID
    project_name: str
    current_stage: ProjectStage
    template_code: str | None
    template_name: str | None
    stage_title: str | None
    owner_roles: list[ProjectStageContextRoleItem]
    required_inputs: list[str]
    expected_outputs: list[str]
    guard_conditions: list[str]
    stage_tasks: list[ProjectStageContextTaskItem]
    can_advance: bool | None
    blocking_reasons: list[str]
    context_summary: str


class ContextBuilderService:
    """Assemble a conservative, task-scoped context package for execution."""

    def __init__(
        self,
        *,
        run_repository: RunRepository,
        task_readiness_service: TaskReadinessService,
        project_memory_service: ProjectMemoryService | None = None,
    ) -> None:
        self.run_repository = run_repository
        self.task_readiness_service = task_readiness_service
        self.project_memory_service = project_memory_service

    def build_context_package(
        self,
        *,
        task: Task,
        include_project_memory: bool = False,
        project_memory_limit: int = 3,
    ) -> TaskContextPackage:
        """Build the minimal context package for one task."""

        readiness = self.task_readiness_service.evaluate_task(task=task)
        recent_runs = self._build_recent_run_items(task.id)
        project_memory_context = (
            self.build_task_memory_context(
                task=task,
                limit=project_memory_limit,
            )
            if include_project_memory and project_memory_limit > 0
            else None
        )
        context_summary = self._build_context_summary(
            task=task,
            dependency_items=readiness.dependency_items,
            recent_runs=recent_runs,
            blocking_reasons=readiness.blocking_reasons,
            project_memory_context=project_memory_context,
        )

        return TaskContextPackage(
            task_id=task.id,
            task_title=task.title,
            input_summary=task.input_summary,
            acceptance_criteria=task.acceptance_criteria,
            priority=task.priority,
            risk_level=task.risk_level,
            human_status=task.human_status,
            paused_reason=task.paused_reason,
            ready_for_execution=readiness.ready_for_execution,
            blocking_signals=readiness.blocking_signals,
            blocking_reasons=readiness.blocking_reasons,
            dependency_items=readiness.dependency_items,
            recent_runs=recent_runs,
            context_summary=context_summary,
        )

    def build_task_memory_context(
        self,
        *,
        task: Task,
        limit: int = 3,
    ) -> TaskProjectMemoryContext | None:
        """Recall a small set of Day14 project memories for the provided task."""

        if self.project_memory_service is None or task.project_id is None or limit <= 0:
            return None

        return self.project_memory_service.build_task_memory_context(
            task=task,
            limit=limit,
        )

    def build_project_stage_context(
        self,
        *,
        project: Project,
        template_code: str | None,
        template_name: str | None,
        stage_title: str | None,
        owner_roles: list[ProjectRoleConfig],
        required_inputs: list[str],
        expected_outputs: list[str],
        guard_conditions: list[str],
        stage_tasks: list[Task],
        can_advance: bool | None,
        blocking_reasons: list[str],
    ) -> ProjectStageContextPackage:
        """Build a concise SOP context summary for one project stage."""

        role_items = [
            ProjectStageContextRoleItem(
                role_code=role.role_code.value,
                role_name=role.name,
                enabled=role.enabled,
            )
            for role in owner_roles
        ]
        task_items = [
            ProjectStageContextTaskItem(
                task_id=task.id,
                title=task.title,
                status=task.status.value,
            )
            for task in stage_tasks
        ]
        context_summary = self._build_project_stage_summary(
            project=project,
            template_name=template_name,
            stage_title=stage_title,
            owner_roles=role_items,
            required_inputs=required_inputs,
            expected_outputs=expected_outputs,
            guard_conditions=guard_conditions,
            stage_tasks=task_items,
            can_advance=can_advance,
            blocking_reasons=blocking_reasons,
        )

        return ProjectStageContextPackage(
            project_id=project.id,
            project_name=project.name,
            current_stage=project.stage,
            template_code=template_code,
            template_name=template_name,
            stage_title=stage_title,
            owner_roles=role_items,
            required_inputs=list(required_inputs),
            expected_outputs=list(expected_outputs),
            guard_conditions=list(guard_conditions),
            stage_tasks=task_items,
            can_advance=can_advance,
            blocking_reasons=list(blocking_reasons),
            context_summary=context_summary,
        )

    def _build_recent_run_items(self, task_id: UUID) -> list[ContextRecentRunItem]:
        """Collect the latest few runs for the current task."""

        runs = self.run_repository.list_by_task_id(task_id)[:_RECENT_RUN_LIMIT]
        return [
            ContextRecentRunItem(
                run_id=run.id,
                status=run.status,
                result_summary=run.result_summary,
                verification_summary=run.verification_summary,
                failure_category=run.failure_category,
                created_at=run.created_at,
            )
            for run in runs
        ]

    def _build_context_summary(
        self,
        *,
        task: Task,
        dependency_items: list[TaskDependencyReadinessItem],
        recent_runs: list[ContextRecentRunItem],
        blocking_reasons: list[str],
        project_memory_context: TaskProjectMemoryContext | None = None,
    ) -> str:
        """Compress the structured context into one readable summary."""

        summary_parts = [
            f"Goal: {task.input_summary.strip()}",
            self._build_acceptance_summary(task.acceptance_criteria),
            self._build_dependency_summary(dependency_items),
            self._build_recent_run_summary(recent_runs),
            (
                f"Task posture: priority={task.priority.value}, risk={task.risk_level.value}, "
                f"human={task.human_status.value}."
            ),
        ]

        if blocking_reasons:
            summary_parts.append(
                "Blocking signals: " + " | ".join(reason.strip() for reason in blocking_reasons)
            )
        else:
            summary_parts.append("Blocking signals: none.")

        if project_memory_context is not None and project_memory_context.items:
            summary_parts.append(
                "Project memory: " + self._build_project_memory_summary(project_memory_context.items)
            )

        summary = "\n".join(summary_parts)
        if len(summary) <= _CONTEXT_SUMMARY_MAX_LENGTH:
            return summary

        return summary[: _CONTEXT_SUMMARY_MAX_LENGTH - 3].rstrip() + "..."

    @staticmethod
    def _build_acceptance_summary(acceptance_criteria: list[str]) -> str:
        """Format acceptance criteria into a single compact sentence."""

        if not acceptance_criteria:
            return "Acceptance criteria: not explicitly defined."

        bullet_text = "; ".join(acceptance_criteria[:3])
        if len(acceptance_criteria) > 3:
            bullet_text += f"; and {len(acceptance_criteria) - 3} more"
        return f"Acceptance criteria: {bullet_text}."

    @staticmethod
    def _build_dependency_summary(
        dependency_items: list[TaskDependencyReadinessItem],
    ) -> str:
        """Format dependency state into a compact summary."""

        if not dependency_items:
            return "Dependencies: none."

        summary_parts = [
            f"{dependency.title}({'missing' if dependency.missing else dependency.status.value})"
            for dependency in dependency_items
        ]
        return "Dependencies: " + ", ".join(summary_parts) + "."

    @staticmethod
    def _build_recent_run_summary(recent_runs: list[ContextRecentRunItem]) -> str:
        """Format recent run history into a compact summary."""

        if not recent_runs:
            return "Recent runs: none."

        summary_parts = [
            f"{run.status.value}"
            + (
                f"/{run.failure_category.value}"
                if run.failure_category is not None
                else ""
            )
            for run in recent_runs
        ]
        return "Recent runs: " + " -> ".join(summary_parts) + "."

    @staticmethod
    def _build_project_memory_summary(items: list[ProjectMemoryItem]) -> str:
        """Format recalled project memories into one compact sentence."""

        if not items:
            return "none."

        summary_parts = [
            f"{item.memory_type.value}:{item.summary}"
            for item in items[:3]
        ]
        if len(items) > 3:
            summary_parts.append(f"and {len(items) - 3} more")
        return " | ".join(summary_parts) + "."

    @staticmethod
    def _build_project_stage_summary(
        *,
        project: Project,
        template_name: str | None,
        stage_title: str | None,
        owner_roles: list[ProjectStageContextRoleItem],
        required_inputs: list[str],
        expected_outputs: list[str],
        guard_conditions: list[str],
        stage_tasks: list[ProjectStageContextTaskItem],
        can_advance: bool | None,
        blocking_reasons: list[str],
    ) -> str:
        """Compress the current SOP stage into a readable context summary."""

        role_summary = (
            ", ".join(
                f"{role.role_name}{'' if role.enabled else '(disabled)'}"
                for role in owner_roles
            )
            if owner_roles
            else "none"
        )
        task_summary = (
            ", ".join(f"{task.title}({task.status})" for task in stage_tasks[:4])
            if stage_tasks
            else "none"
        )
        if len(stage_tasks) > 4:
            task_summary += f"; and {len(stage_tasks) - 4} more"

        summary_parts = [
            f"Project: {project.name}",
            f"Template: {template_name or 'not selected'}",
            f"Current stage: {stage_title or project.stage.value}",
            f"Owner roles: {role_summary}.",
            "Required inputs: "
            + ("; ".join(required_inputs) if required_inputs else "not defined.")
            ,
            "Expected outputs: "
            + ("; ".join(expected_outputs) if expected_outputs else "not defined.")
            ,
            "Guard conditions: "
            + ("; ".join(guard_conditions) if guard_conditions else "not defined.")
            ,
            f"Stage tasks: {task_summary}.",
        ]

        if can_advance is None:
            summary_parts.append("Advance readiness: unknown.")
        elif can_advance:
            summary_parts.append("Advance readiness: ready for the next stage.")
        else:
            blocker_text = " | ".join(blocking_reasons[:3]) if blocking_reasons else "blocked"
            summary_parts.append(f"Advance readiness: blocked - {blocker_text}.")

        summary = "\n".join(summary_parts)
        if len(summary) <= _CONTEXT_SUMMARY_MAX_LENGTH:
            return summary

        return summary[: _CONTEXT_SUMMARY_MAX_LENGTH - 3].rstrip() + "..."
