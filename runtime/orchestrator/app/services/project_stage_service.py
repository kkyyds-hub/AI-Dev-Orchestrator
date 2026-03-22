"""Project milestone evaluation and stage-guard orchestration for V3 Day04."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.project import (
    Project,
    ProjectMilestone,
    ProjectMilestoneCode,
    ProjectStage,
    ProjectStageBlockingTask,
    ProjectStageGuard,
    ProjectStageHistoryEntry,
    ProjectStageHistoryOutcome,
    ProjectStatus,
)
from app.domain.task import Task, TaskBlockingReasonCode, TaskStatus
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.services.approval_service import ApprovalService
from app.services.sop_engine_service import SopEngineService
from app.services.task_readiness_service import TaskReadinessResult, TaskReadinessService
from app.services.task_state_machine_service import TaskStateMachineService


_STAGE_SEQUENCE = (
    ProjectStage.INTAKE,
    ProjectStage.PLANNING,
    ProjectStage.EXECUTION,
    ProjectStage.VERIFICATION,
    ProjectStage.DELIVERY,
)

_PLANNING_HARD_BLOCKER_CODES = {
    TaskBlockingReasonCode.DEPENDENCY_MISSING,
    TaskBlockingReasonCode.HUMAN_REVIEW_REQUESTED,
    TaskBlockingReasonCode.HUMAN_REVIEW_IN_PROGRESS,
    TaskBlockingReasonCode.TASK_PAUSED,
    TaskBlockingReasonCode.TASK_WAITING_HUMAN,
}


@dataclass(slots=True, frozen=True)
class ProjectStageAdvanceResult:
    """Outcome returned after one explicit stage-advance action."""

    project: Project
    previous_stage: ProjectStage
    attempted_stage: ProjectStage
    advanced: bool
    message: str
    stage_guard: ProjectStageGuard
    timeline_entry: ProjectStageHistoryEntry


class ProjectStageTransitionError(ValueError):
    """Raised when one stage transition violates the linear Day04 matrix."""


class ProjectStageService:
    """Evaluate stage guards and persist auditable stage transitions."""

    def __init__(
        self,
        *,
        project_repository: ProjectRepository,
        task_repository: TaskRepository,
        task_readiness_service: TaskReadinessService,
        task_state_machine_service: TaskStateMachineService,
        sop_engine_service: SopEngineService | None = None,
        approval_service: ApprovalService | None = None,
    ) -> None:
        self.project_repository = project_repository
        self.task_repository = task_repository
        self.task_readiness_service = task_readiness_service
        self.task_state_machine_service = task_state_machine_service
        self.sop_engine_service = sop_engine_service
        self.approval_service = approval_service

    def get_project_stage_guard(self, project: Project) -> ProjectStageGuard:
        """Return the current project's next-stage guard snapshot."""

        project_tasks = self.task_repository.list_by_project_id(project.id)
        return self.evaluate_stage_guard(project=project, tasks=project_tasks)

    def evaluate_stage_guard(
        self,
        *,
        project: Project,
        tasks: list[Task],
        target_stage: ProjectStage | None = None,
    ) -> ProjectStageGuard:
        """Return whether one project can legally move into its next stage."""

        attempted_stage = target_stage or self.get_next_stage(project.stage)
        if attempted_stage is None:
            return ProjectStageGuard(
                current_stage=project.stage,
                target_stage=None,
                can_advance=False,
                milestones=[],
                blocking_reasons=["当前已经处于最终阶段，没有更多可推进的项目阶段。"],
                blocking_tasks=[],
                total_tasks=len(tasks),
                ready_task_count=0,
                completed_task_count=sum(
                    1
                    for task in tasks
                    if self.task_state_machine_service.is_project_stage_complete(
                        task.status
                    )
                ),
                current_stage_task_count=0,
                current_stage_completed_task_count=0,
            )

        self._ensure_linear_transition(current_stage=project.stage, target_stage=attempted_stage)

        if self.sop_engine_service is not None and project.sop_template_code:
            sop_guard = self.sop_engine_service.build_stage_guard_evaluation(
                project=project,
                tasks=tasks,
            )
            milestones = [self._build_active_project_milestone(project)]
            blocking_tasks: list[ProjectStageBlockingTask] = []
            current_stage_task_count = 0
            current_stage_completed_task_count = 0
            if sop_guard is not None:
                milestones.extend(sop_guard.milestones)
                blocking_tasks = sop_guard.blocking_tasks
                current_stage_task_count = sop_guard.current_stage_task_count
                current_stage_completed_task_count = (
                    sop_guard.current_stage_completed_task_count
                )

            blocking_reasons = self._collect_blocking_reasons(milestones)
            return self._apply_approval_gate(
                project=project,
                stage_guard=ProjectStageGuard(
                    current_stage=project.stage,
                    target_stage=attempted_stage,
                    can_advance=not blocking_reasons,
                    milestones=milestones,
                    blocking_reasons=blocking_reasons,
                    blocking_tasks=blocking_tasks,
                    total_tasks=len(tasks),
                    ready_task_count=0,
                    completed_task_count=sum(
                        1
                        for task in tasks
                        if self.task_state_machine_service.is_project_stage_complete(
                            task.status
                        )
                    ),
                    current_stage_task_count=current_stage_task_count,
                    current_stage_completed_task_count=current_stage_completed_task_count,
                ),
            )

        readiness_map = self.task_readiness_service.evaluate_tasks(tasks=tasks)
        milestones, blocking_tasks, ready_task_count = self._build_stage_milestones(
            project=project,
            tasks=tasks,
            readiness_map=readiness_map,
            target_stage=attempted_stage,
        )
        blocking_reasons = self._collect_blocking_reasons(milestones)
        return self._apply_approval_gate(
            project=project,
            stage_guard=ProjectStageGuard(
                current_stage=project.stage,
                target_stage=attempted_stage,
                can_advance=not blocking_reasons,
                milestones=milestones,
                blocking_reasons=blocking_reasons,
                blocking_tasks=blocking_tasks,
                total_tasks=len(tasks),
                ready_task_count=ready_task_count,
                completed_task_count=sum(
                    1
                    for task in tasks
                    if self.task_state_machine_service.is_project_stage_complete(task.status)
                ),
                current_stage_task_count=0,
                current_stage_completed_task_count=0,
            ),
        )

    def advance_project_stage(
        self,
        *,
        project_id: UUID,
        note: str | None = None,
    ) -> ProjectStageAdvanceResult | None:
        """Attempt to advance one project to its next legal stage."""

        project = self.project_repository.get_by_id(project_id)
        if project is None:
            return None

        project_tasks = self.task_repository.list_by_project_id(project_id)
        attempted_stage = self.get_next_stage(project.stage)
        if attempted_stage is None:
            raise ProjectStageTransitionError("Project is already at the final delivery stage.")

        stage_guard = self.evaluate_stage_guard(
            project=project,
            tasks=project_tasks,
            target_stage=attempted_stage,
        )
        timeline_entry = ProjectStageHistoryEntry(
            from_stage=project.stage,
            to_stage=attempted_stage,
            outcome=(
                ProjectStageHistoryOutcome.APPLIED
                if stage_guard.can_advance
                else ProjectStageHistoryOutcome.BLOCKED
            ),
            note=note,
            reasons=stage_guard.blocking_reasons,
        )

        next_history = [*project.stage_history, timeline_entry]
        updated_project = self.project_repository.update_stage_state(
            project_id,
            stage=attempted_stage if stage_guard.can_advance else None,
            stage_history=next_history,
        )

        generated_task_count = 0
        if (
            stage_guard.can_advance
            and self.sop_engine_service is not None
            and updated_project.sop_template_code
        ):
            sync_result = self.sop_engine_service.ensure_current_stage_tasks(
                project=updated_project,
                tasks=self.task_repository.list_by_project_id(project_id),
            )
            updated_project = sync_result.project
            generated_task_count = len(sync_result.created_tasks)

        refreshed_guard = self.evaluate_stage_guard(
            project=updated_project,
            tasks=self.task_repository.list_by_project_id(project_id),
        )
        if stage_guard.can_advance:
            message = (
                f"项目已从「{self._stage_label(project.stage)}」推进到"
                f"「{self._stage_label(attempted_stage)}」。"
            )
            if generated_task_count > 0:
                message += f" 已按 SOP 自动补齐 {generated_task_count} 个当前阶段任务。"
        else:
            message = (
                f"项目未能进入「{self._stage_label(attempted_stage)}」，"
                "请先补齐里程碑后再推进。"
            )

        return ProjectStageAdvanceResult(
            project=updated_project,
            previous_stage=project.stage,
            attempted_stage=attempted_stage,
            advanced=stage_guard.can_advance,
            message=message,
            stage_guard=refreshed_guard,
            timeline_entry=timeline_entry,
        )

    def _apply_approval_gate(
        self,
        *,
        project: Project,
        stage_guard: ProjectStageGuard,
    ) -> ProjectStageGuard:
        """Merge Day10 approval blockers into the current stage-guard snapshot."""

        if self.approval_service is None or stage_guard.target_stage is None:
            return stage_guard

        approval_gate = self.approval_service.build_stage_gate(
            project_id=project.id,
            stage=project.stage,
        )
        if approval_gate.can_advance:
            return stage_guard

        return ProjectStageGuard(
            current_stage=stage_guard.current_stage,
            target_stage=stage_guard.target_stage,
            can_advance=False,
            milestones=stage_guard.milestones,
            blocking_reasons=self._deduplicate_strings(
                [*stage_guard.blocking_reasons, *approval_gate.blocking_reasons]
            ),
            blocking_tasks=stage_guard.blocking_tasks,
            total_tasks=stage_guard.total_tasks,
            ready_task_count=stage_guard.ready_task_count,
            completed_task_count=stage_guard.completed_task_count,
            current_stage_task_count=stage_guard.current_stage_task_count,
            current_stage_completed_task_count=stage_guard.current_stage_completed_task_count,
        )

    @staticmethod
    def get_next_stage(stage: ProjectStage) -> ProjectStage | None:
        """Return the next legal stage in the frozen Day04 order."""

        try:
            current_index = _STAGE_SEQUENCE.index(stage)
        except ValueError as exc:  # pragma: no cover - defensive only
            raise ProjectStageTransitionError(f"Unknown project stage: {stage}") from exc

        next_index = current_index + 1
        return _STAGE_SEQUENCE[next_index] if next_index < len(_STAGE_SEQUENCE) else None

    def _build_stage_milestones(
        self,
        *,
        project: Project,
        tasks: list[Task],
        readiness_map: dict[UUID, TaskReadinessResult],
        target_stage: ProjectStage,
    ) -> tuple[list[ProjectMilestone], list[ProjectStageBlockingTask], int]:
        """Build milestone checks for one stage transition."""

        milestones = [
            self._build_active_project_milestone(project),
        ]

        if target_stage == ProjectStage.PLANNING:
            milestones.append(self._build_brief_ready_milestone(project))
            return milestones, [], 0

        if target_stage == ProjectStage.EXECUTION:
            planning_blockers = self._build_planning_blocking_tasks(
                tasks=tasks,
                readiness_map=readiness_map,
            )
            ready_task_count = self._count_ready_execution_tasks(
                tasks=tasks,
                readiness_map=readiness_map,
            )
            milestones.extend(
                [
                    self._build_tasks_mapped_milestone(tasks),
                    self._build_ready_path_milestone(
                        tasks=tasks,
                        readiness_map=readiness_map,
                        ready_task_count=ready_task_count,
                    ),
                    self._build_planning_guard_milestone(planning_blockers),
                ]
            )
            return milestones, planning_blockers, ready_task_count

        completion_blockers = self._build_completion_blocking_tasks(tasks)
        milestones.extend(
            [
                self._build_tasks_mapped_milestone(tasks),
                self._build_all_tasks_completed_milestone(completion_blockers, tasks),
            ]
        )
        return milestones, completion_blockers, 0

    @staticmethod
    def _build_active_project_milestone(project: Project) -> ProjectMilestone:
        """Require the project to stay in an actively pushable status."""

        status_label = ProjectStageService._project_status_label(project.status)
        if project.status == ProjectStatus.ACTIVE:
            return ProjectMilestone(
                code=ProjectMilestoneCode.PROJECT_ACTIVE,
                title="项目处于可推进状态",
                satisfied=True,
                summary="项目当前为进行中状态，可以继续执行阶段推进检查。",
            )

        return ProjectMilestone(
            code=ProjectMilestoneCode.PROJECT_ACTIVE,
            title="项目处于可推进状态",
            satisfied=False,
            summary=f"项目当前状态为「{status_label}」，必须先恢复为进行中后才能推进阶段。",
            blocking_reasons=[
                f"项目状态为「{status_label}」，当前不能推进下一阶段。"
            ],
        )

    @staticmethod
    def _build_brief_ready_milestone(project: Project) -> ProjectMilestone:
        """Require the minimal project brief to exist before planning begins."""

        return ProjectMilestone(
            code=ProjectMilestoneCode.PROJECT_BRIEF_READY,
            title="项目目标与摘要已建档",
            satisfied=True,
            summary=(
                f"已记录项目名称「{project.name}」及摘要，"
                "可以从需求入口进入规划阶段。"
            ),
        )

    @staticmethod
    def _build_tasks_mapped_milestone(tasks: list[Task]) -> ProjectMilestone:
        """Require the project to have at least one mapped task."""

        if tasks:
            return ProjectMilestone(
                code=ProjectMilestoneCode.TASKS_MAPPED,
                title="已映射项目任务",
                satisfied=True,
                summary=f"当前项目已挂接 {len(tasks)} 个任务，可以继续检查阶段守卫。",
                related_task_ids=[task.id for task in tasks],
            )

        return ProjectMilestone(
            code=ProjectMilestoneCode.TASKS_MAPPED,
            title="已映射项目任务",
            satisfied=False,
            summary="项目当前还没有挂接任务，不能进入下一阶段。",
            blocking_reasons=["项目当前没有任何任务映射，必须先完成任务拆解。"],
        )

    def _build_ready_path_milestone(
        self,
        *,
        tasks: list[Task],
        readiness_map: dict[UUID, TaskReadinessResult],
        ready_task_count: int,
    ) -> ProjectMilestone:
        """Require at least one immediately executable path before execution starts."""

        active_execution_task_count = sum(
            1 for task in tasks if task.status in {TaskStatus.RUNNING, TaskStatus.COMPLETED}
        )
        if ready_task_count > 0 or active_execution_task_count > 0:
            related_task_ids = [
                task.id
                for task in tasks
                if task.status in {TaskStatus.RUNNING, TaskStatus.COMPLETED}
                or (
                    readiness_map.get(task.id) is not None
                    and readiness_map[task.id].ready_for_execution
                )
            ][:20]
            return ProjectMilestone(
                code=ProjectMilestoneCode.READY_PATH_AVAILABLE,
                title="至少存在一条可执行路径",
                satisfied=True,
                summary=(
                    f"当前已有 {ready_task_count} 个待执行任务通过守卫，"
                    f"另有 {active_execution_task_count} 个任务已进入或完成执行。"
                ),
                related_task_ids=related_task_ids,
            )

        blocking_reasons = [
            "当前没有可立即执行的任务，请先补齐依赖或清理人工/暂停/失败阻塞。"
        ]
        return ProjectMilestone(
            code=ProjectMilestoneCode.READY_PATH_AVAILABLE,
            title="至少存在一条可执行路径",
            satisfied=False,
            summary="所有任务都还没有形成可执行入口，项目暂时不能进入执行阶段。",
            blocking_reasons=blocking_reasons,
        )

    @staticmethod
    def _build_planning_guard_milestone(
        blocking_tasks: list[ProjectStageBlockingTask],
    ) -> ProjectMilestone:
        """Require planning-time hard blockers to be cleared."""

        if not blocking_tasks:
            return ProjectMilestone(
                code=ProjectMilestoneCode.PLANNING_GUARDS_CLEARED,
                title="规划阶段硬阻塞已清空",
                satisfied=True,
                summary="当前未发现人工介入、暂停、失败、阻塞或缺失依赖等硬阻塞。",
            )

        blocking_reasons = [
            f"仍有 {len(blocking_tasks)} 个任务被人工/暂停/依赖或失败阻塞拦住。"
        ]
        return ProjectMilestone(
            code=ProjectMilestoneCode.PLANNING_GUARDS_CLEARED,
            title="规划阶段硬阻塞已清空",
            satisfied=False,
            summary="存在需要先处理的规划期硬阻塞，项目暂时不能进入执行阶段。",
            blocking_reasons=blocking_reasons,
            related_task_ids=[item.task_id for item in blocking_tasks],
        )

    @staticmethod
    def _build_all_tasks_completed_milestone(
        blocking_tasks: list[ProjectStageBlockingTask],
        tasks: list[Task],
    ) -> ProjectMilestone:
        """Require all mapped tasks to finish before later-stage promotion."""

        if tasks and not blocking_tasks:
            return ProjectMilestone(
                code=ProjectMilestoneCode.ALL_TASKS_COMPLETED,
                title="所有任务已完成",
                satisfied=True,
                summary=f"当前项目的 {len(tasks)} 个任务都已完成，可以推进到下一阶段。",
                related_task_ids=[task.id for task in tasks],
            )

        if not tasks:
            return ProjectMilestone(
                code=ProjectMilestoneCode.ALL_TASKS_COMPLETED,
                title="所有任务已完成",
                satisfied=False,
                summary="项目当前还没有任务，无法判定阶段收口。",
                blocking_reasons=["项目当前没有任何任务，不能推进到下一阶段。"],
            )

        return ProjectMilestone(
            code=ProjectMilestoneCode.ALL_TASKS_COMPLETED,
            title="所有任务已完成",
            satisfied=False,
            summary="仍有任务没有完成收口，必须先清空未完成状态后才能推进阶段。",
            blocking_reasons=[
                f"仍有 {len(blocking_tasks)} 个任务未完成收口，项目不能推进下一阶段。"
            ],
            related_task_ids=[item.task_id for item in blocking_tasks],
        )

    def _build_planning_blocking_tasks(
        self,
        *,
        tasks: list[Task],
        readiness_map: dict[UUID, TaskReadinessResult],
    ) -> list[ProjectStageBlockingTask]:
        """Return planning-time hard blockers tied to concrete tasks."""

        blocking_items: list[ProjectStageBlockingTask] = []

        for task in tasks:
            relevant_reasons: list[str] = []
            readiness = readiness_map.get(task.id)
            if readiness is not None:
                relevant_reasons.extend(
                    self._translate_planning_signal_code(signal.code)
                    for signal in readiness.blocking_signals
                    if signal.code in _PLANNING_HARD_BLOCKER_CODES
                )

            if task.status in {
                TaskStatus.PAUSED,
                TaskStatus.WAITING_HUMAN,
                TaskStatus.FAILED,
                TaskStatus.BLOCKED,
            }:
                relevant_reasons.append(
                    self.task_state_machine_service.build_project_stage_block_message(
                        task.status
                    )
                )

            normalized_reasons = self._deduplicate_strings(relevant_reasons)
            if not normalized_reasons:
                continue

            blocking_items.append(
                ProjectStageBlockingTask(
                    task_id=task.id,
                    title=task.title,
                    status=task.status,
                    blocking_reasons=normalized_reasons,
                )
            )

        if blocking_items:
            return blocking_items

        ready_task_count = self._count_ready_execution_tasks(
            tasks=tasks,
            readiness_map=readiness_map,
        )
        if ready_task_count > 0:
            return []

        fallback_items: list[ProjectStageBlockingTask] = []
        for task in tasks:
            readiness = readiness_map.get(task.id)
            if readiness is None or readiness.ready_for_execution:
                continue

            if task.status not in {TaskStatus.PENDING, TaskStatus.RUNNING}:
                continue

            fallback_items.append(
                ProjectStageBlockingTask(
                    task_id=task.id,
                    title=task.title,
                    status=task.status,
                    blocking_reasons=(
                        readiness.blocking_reasons[:2]
                        or ["该任务尚未形成可执行入口，请继续补齐依赖闭环。"]
                    ),
                )
            )
            if len(fallback_items) >= 5:
                break

        return fallback_items

    @staticmethod
    def _translate_planning_signal_code(
        code: TaskBlockingReasonCode,
    ) -> str:
        """Map one readiness signal into Day04-facing Chinese blocker text."""

        mapping = {
            TaskBlockingReasonCode.DEPENDENCY_MISSING: "存在缺失依赖任务，必须先补齐依赖闭环。",
            TaskBlockingReasonCode.HUMAN_REVIEW_REQUESTED: "任务已请求人工处理，必须先完成人工介入。",
            TaskBlockingReasonCode.HUMAN_REVIEW_IN_PROGRESS: "任务正由人工处理中，必须等待人工处理完成。",
            TaskBlockingReasonCode.TASK_PAUSED: "任务已暂停，必须先恢复或重新规划。",
            TaskBlockingReasonCode.TASK_WAITING_HUMAN: "任务等待人工处理，必须先完成人工介入。",
        }
        return mapping.get(code, code.value)

    def _count_ready_execution_tasks(
        self,
        *,
        tasks: list[Task],
        readiness_map: dict[UUID, TaskReadinessResult],
    ) -> int:
        """Count how many pending tasks can immediately enter execution."""

        return sum(
            1
            for task in tasks
            if task.status == TaskStatus.PENDING
            and readiness_map.get(task.id) is not None
            and readiness_map[task.id].ready_for_execution
        )

    def _build_completion_blocking_tasks(
        self,
        tasks: list[Task],
    ) -> list[ProjectStageBlockingTask]:
        """Return all tasks that still block the project from later-stage promotion."""

        blocking_items: list[ProjectStageBlockingTask] = []

        for task in tasks:
            if self.task_state_machine_service.is_project_stage_complete(task.status):
                continue

            blocking_items.append(
                ProjectStageBlockingTask(
                    task_id=task.id,
                    title=task.title,
                    status=task.status,
                    blocking_reasons=[
                        self.task_state_machine_service.build_project_stage_block_message(
                            task.status
                        )
                    ],
                )
            )

        return blocking_items

    @staticmethod
    def _collect_blocking_reasons(milestones: list[ProjectMilestone]) -> list[str]:
        """Flatten milestone blockers into one stable project-level list."""

        blocking_reasons: list[str] = []
        for milestone in milestones:
            blocking_reasons.extend(milestone.blocking_reasons)

        return ProjectStageService._deduplicate_strings(blocking_reasons)

    @staticmethod
    def _deduplicate_strings(values: list[str]) -> list[str]:
        """Trim and deduplicate text while preserving order."""

        normalized_values: list[str] = []
        seen_values: set[str] = set()

        for value in values:
            normalized_value = value.strip()
            if not normalized_value or normalized_value in seen_values:
                continue

            normalized_values.append(normalized_value)
            seen_values.add(normalized_value)

        return normalized_values

    @staticmethod
    def _ensure_linear_transition(
        *,
        current_stage: ProjectStage,
        target_stage: ProjectStage,
    ) -> None:
        """Reject skip-level or backward stage changes."""

        expected_stage = ProjectStageService.get_next_stage(current_stage)
        if expected_stage == target_stage:
            return

        raise ProjectStageTransitionError(
            "Project stage transitions must follow intake -> planning -> execution "
            "-> verification -> delivery one step at a time."
        )

    @staticmethod
    def _stage_label(stage: ProjectStage) -> str:
        """Return one short Chinese label for stage summaries."""

        mapping = {
            ProjectStage.INTAKE: "需求入口",
            ProjectStage.PLANNING: "规划中",
            ProjectStage.EXECUTION: "执行中",
            ProjectStage.VERIFICATION: "验证中",
            ProjectStage.DELIVERY: "交付中",
        }
        return mapping.get(stage, stage.value)

    @staticmethod
    def _project_status_label(status: ProjectStatus) -> str:
        """Return one short Chinese label for project-status summaries."""

        mapping = {
            ProjectStatus.ACTIVE: "进行中",
            ProjectStatus.ON_HOLD: "挂起",
            ProjectStatus.COMPLETED: "已完成",
            ProjectStatus.ARCHIVED: "已归档",
        }
        return mapping.get(status, status.value)
