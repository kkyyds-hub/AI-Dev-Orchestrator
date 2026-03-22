"""Minimal heuristic planner service for turning one brief into task drafts."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import re
from uuid import UUID

from app.domain.project import Project, ProjectStage, ProjectStatus
from app.domain.task import Task, TaskHumanStatus, TaskPriority, TaskRiskLevel
from app.services.project_service import ProjectService
from app.services.task_service import TaskService


_DEFAULT_MAX_TASKS = 6
_MAX_TASK_TITLE_LENGTH = 60
_MAX_PROJECT_NAME_LENGTH = 80
_MAX_SUMMARY_LENGTH = 240
_SENTENCE_SPLIT_PATTERN = re.compile(r"[。！？!?；;\n]+")
_BULLET_PATTERN = re.compile(
    r"^\s*(?:[-*+]|(?:\d+|[一二三四五六七八九十]+)[\.\、\)])\s*(.+)$"
)

_HIGH_PRIORITY_KEYWORDS = (
    "核心",
    "必须",
    "优先",
    "阻塞",
    "接口",
    "后端",
    "数据库",
    "模型",
    "调度",
    "验证",
    "修复",
)
_LOW_PRIORITY_KEYWORDS = ("文档", "说明", "样式", "展示", "文案")
_HIGH_RISK_KEYWORDS = (
    "迁移",
    "删除",
    "重构",
    "权限",
    "鉴权",
    "安全",
    "预算",
    "数据库",
    "状态机",
    "并发",
    "部署",
)
_LOW_RISK_KEYWORDS = ("文档", "展示", "文案", "样式", "说明")


@dataclass(slots=True, frozen=True)
class PlannedTaskDraft:
    """One task draft proposed by the heuristic planner."""

    draft_id: str
    title: str
    input_summary: str
    priority: TaskPriority
    acceptance_criteria: list[str]
    depends_on_draft_ids: list[str]
    risk_level: TaskRiskLevel
    human_status: TaskHumanStatus = TaskHumanStatus.NONE
    paused_reason: str | None = None


@dataclass(slots=True, frozen=True)
class PlannedProjectDraft:
    """Minimal project draft returned by the Day03 planner entry."""

    name: str
    summary: str
    status: ProjectStatus = ProjectStatus.ACTIVE
    stage: ProjectStage = ProjectStage.PLANNING


@dataclass(slots=True, frozen=True)
class PlanDraft:
    """Draft planning result returned before persistence."""

    project_summary: str
    planning_notes: list[str]
    tasks: list[PlannedTaskDraft]
    project: PlannedProjectDraft | None = None


@dataclass(slots=True, frozen=True)
class AppliedDraftTask:
    """Created task together with its source draft ID."""

    draft_id: str
    task: Task


@dataclass(slots=True, frozen=True)
class PlanApplyResult:
    """Persistence result after applying one draft."""

    project_summary: str
    created_tasks: list[AppliedDraftTask]
    project: Project | None = None


class PlannerService:
    """Turn one brief into a conservative task plan and persist it if requested."""

    def __init__(
        self,
        task_service: TaskService,
        project_service: ProjectService,
    ) -> None:
        self.task_service = task_service
        self.project_service = project_service

    def generate_plan_draft(
        self,
        *,
        brief: str,
        max_tasks: int = _DEFAULT_MAX_TASKS,
    ) -> PlanDraft:
        """Build a deterministic task draft from one project brief."""

        normalized_brief = self._normalize_brief(brief)
        candidate_items = self._extract_candidate_items(normalized_brief)
        capped_max_tasks = max(3, min(max_tasks, 10))
        implementation_capacity = max(capped_max_tasks - 2, 1)
        implementation_items = candidate_items[:implementation_capacity]

        project_summary = self._build_project_summary(normalized_brief)
        project_draft = PlannedProjectDraft(
            name=self._build_project_name(
                brief=normalized_brief,
                candidate_items=candidate_items,
            ),
            summary=project_summary,
            status=ProjectStatus.ACTIVE,
            stage=ProjectStage.PLANNING,
        )
        planning_notes = [
            "当前使用本地启发式 Planner，不依赖外部模型。",
            "默认生成‘范围澄清 -> 子任务推进 -> 整体验证’的保守链路。",
            "草案应用前可以人工调整项目名称、项目摘要、任务标题、依赖、验收标准和风险等级。",
            "草案应用只负责创建项目与映射任务，不会自动触发执行。",
        ]

        drafts: list[PlannedTaskDraft] = []
        analysis_draft = PlannedTaskDraft(
            draft_id="draft-1",
            title="整理范围与验收标准",
            input_summary=(
                "基于当前 brief 整理任务边界、关键约束、最小验收标准和潜在风险：\n"
                f"{project_summary}"
            ),
            priority=TaskPriority.HIGH,
            acceptance_criteria=[
                "明确本次工作的目标边界",
                "列出最小可验证验收标准",
                "识别关键依赖、风险或人工介入点",
            ],
            depends_on_draft_ids=[],
            risk_level=self._infer_risk_level(normalized_brief),
        )
        drafts.append(analysis_draft)

        implementation_draft_ids: list[str] = []
        for index, item in enumerate(implementation_items, start=2):
            draft_id = f"draft-{index}"
            implementation_draft_ids.append(draft_id)
            drafts.append(
                PlannedTaskDraft(
                    draft_id=draft_id,
                    title=self._build_task_title(item),
                    input_summary=self._build_task_input_summary(item),
                    priority=self._infer_priority(item),
                    acceptance_criteria=self._build_acceptance_criteria(item),
                    depends_on_draft_ids=[analysis_draft.draft_id],
                    risk_level=self._infer_risk_level(item),
                )
            )

        verification_dependency_ids = (
            implementation_draft_ids if implementation_draft_ids else [analysis_draft.draft_id]
        )
        drafts.append(
            PlannedTaskDraft(
                draft_id=f"draft-{len(drafts) + 1}",
                title="整体验证与收尾",
                input_summary=(
                    "汇总前序任务结果，执行最小验证，补齐必要说明，并记录剩余风险或阻塞项。"
                ),
                priority=TaskPriority.NORMAL,
                acceptance_criteria=[
                    "主要链路具备最小验证结论",
                    "关键改动有对应说明或交接信息",
                    "剩余风险、阻塞项或人工待办被明确记录",
                ],
                depends_on_draft_ids=verification_dependency_ids,
                risk_level=TaskRiskLevel.NORMAL,
            )
        )

        return PlanDraft(
            project_summary=project_summary,
            planning_notes=planning_notes,
            tasks=drafts,
            project=project_draft,
        )

    def apply_plan_draft(
        self,
        *,
        project_summary: str,
        task_drafts: list[PlannedTaskDraft],
        project_draft: PlannedProjectDraft | None = None,
        project_id: UUID | None = None,
    ) -> PlanApplyResult:
        """Persist a draft plan as actual tasks in dependency order."""

        if not task_drafts:
            raise ValueError("Planner draft must contain at least one task.")
        if project_draft is not None and project_id is not None:
            raise ValueError("Cannot create a new project draft and target an existing project at the same time.")

        target_project: Project | None = None
        target_project_id = project_id

        if project_draft is not None:
            target_project = self.project_service.create_project(
                name=project_draft.name,
                summary=project_draft.summary,
                status=project_draft.status,
                stage=project_draft.stage,
            )
            target_project_id = target_project.id
        elif project_id is not None:
            target_project = self.project_service.get_project(project_id)
            if target_project is None:
                raise ValueError(f"Project not found: {project_id}")

        draft_map = self._build_draft_map(task_drafts)
        creation_order = self._topological_order(task_drafts, draft_map)
        created_task_ids: dict[str, UUID] = {}
        created_tasks: list[AppliedDraftTask] = []

        for draft in creation_order:
            dependency_ids = [
                created_task_ids[draft_id] for draft_id in draft.depends_on_draft_ids
            ]
            created_task = self.task_service.create_task(
                project_id=target_project_id,
                title=draft.title,
                input_summary=draft.input_summary,
                priority=draft.priority,
                acceptance_criteria=draft.acceptance_criteria,
                depends_on_task_ids=dependency_ids,
                risk_level=draft.risk_level,
                human_status=draft.human_status,
                paused_reason=draft.paused_reason,
                source_draft_id=draft.draft_id,
            )
            created_task_ids[draft.draft_id] = created_task.id
            created_tasks.append(
                AppliedDraftTask(
                    draft_id=draft.draft_id,
                    task=created_task,
                )
            )

        refreshed_project: Project | None = None
        if target_project_id is not None:
            refreshed_project = self.project_service.get_project(target_project_id)

        normalized_summary = self._build_project_summary(project_summary)
        if refreshed_project is not None:
            normalized_summary = refreshed_project.summary

        return PlanApplyResult(
            project_summary=normalized_summary,
            created_tasks=created_tasks,
            project=refreshed_project,
        )

    @staticmethod
    def _normalize_brief(brief: str) -> str:
        """Collapse extra whitespace while keeping paragraph breaks readable."""

        normalized_lines = [line.strip() for line in brief.splitlines() if line.strip()]
        normalized_brief = "\n".join(normalized_lines).strip()
        if not normalized_brief:
            raise ValueError("Planner brief cannot be empty.")

        return normalized_brief

    def _extract_candidate_items(self, brief: str) -> list[str]:
        """Extract candidate sub-goals from bullets or sentences."""

        bullet_items: list[str] = []
        for line in brief.splitlines():
            matched = _BULLET_PATTERN.match(line)
            if matched:
                bullet_items.append(self._normalize_candidate_text(matched.group(1)))

        if len(bullet_items) >= 2:
            return self._deduplicate_non_empty(bullet_items)

        sentence_items = [
            self._normalize_candidate_text(item)
            for item in _SENTENCE_SPLIT_PATTERN.split(brief)
        ]
        normalized_items = self._deduplicate_non_empty(sentence_items)
        if normalized_items:
            return normalized_items

        return [brief]

    @staticmethod
    def _normalize_candidate_text(text: str) -> str:
        """Normalize one candidate sentence."""

        normalized_text = re.sub(r"\s+", " ", text).strip(" -\t")
        return normalized_text

    @staticmethod
    def _deduplicate_non_empty(items: list[str]) -> list[str]:
        """Keep unique non-empty items in original order."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()
        for item in items:
            if not item or item in seen_items:
                continue
            normalized_items.append(item)
            seen_items.add(item)
        return normalized_items

    def _build_project_name(self, *, brief: str, candidate_items: list[str]) -> str:
        """Build a concise project draft name from one brief."""

        candidate_name = candidate_items[0] if candidate_items else brief.splitlines()[0]
        normalized_name = re.sub(r"\s+", " ", candidate_name).strip()
        normalized_name = re.sub(r"^[：:]+", "", normalized_name).strip()
        normalized_name = re.sub(r"[。！？!?；;]+$", "", normalized_name).strip()

        if not normalized_name:
            normalized_name = "未命名项目草案"

        if len(normalized_name) <= _MAX_PROJECT_NAME_LENGTH:
            return normalized_name

        return normalized_name[: _MAX_PROJECT_NAME_LENGTH - 3].rstrip() + "..."

    def _build_project_summary(self, brief: str) -> str:
        """Return a compact project summary suitable for API responses."""

        summary_source = brief.replace("\n", " ").strip()
        if len(summary_source) <= _MAX_SUMMARY_LENGTH:
            return summary_source

        return summary_source[: _MAX_SUMMARY_LENGTH - 3].rstrip() + "..."

    def _build_task_title(self, item: str) -> str:
        """Turn one candidate item into a concise task title."""

        normalized_item = item.strip()
        if len(normalized_item) <= _MAX_TASK_TITLE_LENGTH:
            return normalized_item

        return normalized_item[: _MAX_TASK_TITLE_LENGTH - 3].rstrip() + "..."

    @staticmethod
    def _build_task_input_summary(item: str) -> str:
        """Turn one candidate item into a worker-facing summary."""

        return f"围绕以下子目标推进实现，并输出最小可验证结果：\n{item.strip()}"

    @staticmethod
    def _build_acceptance_criteria(item: str) -> list[str]:
        """Build conservative acceptance criteria for one candidate item."""

        normalized_item = item.strip()
        return [
            f"完成子目标：{normalized_item}",
            "输出可验证的实现结果、接口或结构化说明",
            "记录必要的限制、风险或后续待办",
        ]

    @staticmethod
    def _infer_priority(item: str) -> TaskPriority:
        """Infer a conservative task priority from keywords."""

        lowered_item = item.lower()
        if any(keyword in item for keyword in _HIGH_PRIORITY_KEYWORDS):
            return TaskPriority.HIGH
        if any(keyword in item for keyword in _LOW_PRIORITY_KEYWORDS) or "docs" in lowered_item:
            return TaskPriority.LOW
        return TaskPriority.NORMAL

    @staticmethod
    def _infer_risk_level(item: str) -> TaskRiskLevel:
        """Infer a coarse task risk level from keywords."""

        lowered_item = item.lower()
        if any(keyword in item for keyword in _HIGH_RISK_KEYWORDS):
            return TaskRiskLevel.HIGH
        if any(keyword in item for keyword in _LOW_RISK_KEYWORDS) or "docs" in lowered_item:
            return TaskRiskLevel.LOW
        return TaskRiskLevel.NORMAL

    @staticmethod
    def _build_draft_map(
        task_drafts: list[PlannedTaskDraft],
    ) -> dict[str, PlannedTaskDraft]:
        """Validate draft IDs and return a lookup map."""

        draft_map: dict[str, PlannedTaskDraft] = {}
        for draft in task_drafts:
            if draft.draft_id in draft_map:
                raise ValueError(f"Duplicate planner draft id: {draft.draft_id}")
            draft_map[draft.draft_id] = draft
        return draft_map

    def _topological_order(
        self,
        task_drafts: list[PlannedTaskDraft],
        draft_map: dict[str, PlannedTaskDraft],
    ) -> list[PlannedTaskDraft]:
        """Return drafts in dependency-safe order and reject invalid graphs."""

        original_order = {draft.draft_id: index for index, draft in enumerate(task_drafts)}
        indegree: dict[str, int] = {}
        outgoing: dict[str, list[str]] = {draft.draft_id: [] for draft in task_drafts}

        for draft in task_drafts:
            dependency_ids = []
            for dependency_id in draft.depends_on_draft_ids:
                if dependency_id == draft.draft_id:
                    raise ValueError(
                        f"Planner draft cannot depend on itself: {draft.draft_id}"
                    )
                if dependency_id not in draft_map:
                    raise ValueError(
                        f"Planner draft dependency not found: {dependency_id}"
                    )
                dependency_ids.append(dependency_id)

            unique_dependency_ids = list(dict.fromkeys(dependency_ids))
            indegree[draft.draft_id] = len(unique_dependency_ids)
            for dependency_id in unique_dependency_ids:
                outgoing[dependency_id].append(draft.draft_id)

        ready_queue = deque(
            sorted(
                (draft_id for draft_id, degree in indegree.items() if degree == 0),
                key=lambda draft_id: original_order[draft_id],
            )
        )
        ordered_drafts: list[PlannedTaskDraft] = []

        while ready_queue:
            draft_id = ready_queue.popleft()
            ordered_drafts.append(draft_map[draft_id])

            next_ready_ids: list[str] = []
            for dependent_id in outgoing[draft_id]:
                indegree[dependent_id] -= 1
                if indegree[dependent_id] == 0:
                    next_ready_ids.append(dependent_id)

            for dependent_id in sorted(next_ready_ids, key=lambda item: original_order[item]):
                ready_queue.append(dependent_id)

        if len(ordered_drafts) != len(task_drafts):
            raise ValueError("Planner draft dependencies contain a cycle.")

        return ordered_drafts
