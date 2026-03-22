"""Role catalog orchestration for V3 Day05."""

from __future__ import annotations

from dataclasses import dataclass
import re
from uuid import UUID

from app.domain._base import utc_now
from app.domain.project_role import (
    ProjectRoleCatalog,
    ProjectRoleCode,
    ProjectRoleConfig,
    RoleCatalogEntry,
)
from app.domain.task import Task
from app.repositories.project_repository import ProjectRepository
from app.repositories.project_role_repository import ProjectRoleRepository


@dataclass(slots=True, frozen=True)
class ResolvedTaskRoleAssignment:
    """Resolved role assignment snapshot used by Day07 task routing."""

    owner_role_code: ProjectRoleCode | None
    upstream_role_code: ProjectRoleCode | None
    downstream_role_code: ProjectRoleCode | None
    dispatch_status: str
    handoff_reason: str
    responsibility_score: float
    matched_terms: tuple[str, ...] = ()


_ROLE_MATCH_HINTS: dict[ProjectRoleCode, tuple[str, ...]] = {
    ProjectRoleCode.PRODUCT_MANAGER: (
        "需求",
        "范围",
        "优先级",
        "验收",
        "里程碑",
        "brief",
        "澄清",
        "规划",
    ),
    ProjectRoleCode.ARCHITECT: (
        "架构",
        "方案",
        "设计",
        "接口",
        "模块",
        "数据结构",
        "技术路径",
        "依赖",
    ),
    ProjectRoleCode.ENGINEER: (
        "工程",
        "实现",
        "开发",
        "代码",
        "脚本",
        "配置",
        "修复",
        "联调",
        "自测",
    ),
    ProjectRoleCode.REVIEWER: (
        "评审",
        "review",
        "验证",
        "验收",
        "检查",
        "回归",
        "质量",
        "缺陷",
    ),
}


_SYSTEM_ROLE_CATALOG: tuple[RoleCatalogEntry, ...] = (
    RoleCatalogEntry(
        code=ProjectRoleCode.PRODUCT_MANAGER,
        name="产品经理",
        summary="负责把老板目标、范围边界和验收口径整理为可推进的项目输入。",
        responsibilities=[
            "澄清项目目标与业务价值",
            "拆解范围、优先级和关键里程碑",
            "协调需求变更并维护验收口径",
        ],
        input_boundary=[
            "老板 brief、补充说明与业务约束",
            "项目阶段目标与里程碑要求",
            "已有任务、风险和审批反馈",
        ],
        output_boundary=[
            "需求摘要、优先级和范围边界",
            "任务拆解建议与验收标准",
            "供架构/工程继续推进的明确输入",
        ],
        default_skill_slots=["需求澄清", "范围拆解", "优先级规划"],
        sort_order=10,
    ),
    RoleCatalogEntry(
        code=ProjectRoleCode.ARCHITECT,
        name="架构师",
        summary="负责把需求转成系统方案、关键接口、数据结构和技术风险判断。",
        responsibilities=[
            "设计系统边界与模块协作方式",
            "给出关键接口、数据结构和技术路径",
            "识别依赖、风险与实施前置条件",
        ],
        input_boundary=[
            "已澄清的需求摘要与验收口径",
            "现有代码结构、运行约束与外部依赖",
            "项目阶段守卫与关键风险提示",
        ],
        output_boundary=[
            "技术方案摘要与边界说明",
            "接口/数据结构草案",
            "供工程实现的依赖清单与风险提示",
        ],
        default_skill_slots=["方案设计", "依赖分析", "风险评估"],
        sort_order=20,
    ),
    RoleCatalogEntry(
        code=ProjectRoleCode.ENGINEER,
        name="工程师",
        summary="负责根据任务与方案完成实现、局部验证和交付说明。",
        responsibilities=[
            "实现代码、脚本或配置改动",
            "补齐必要的局部验证与自测记录",
            "输出实现说明、限制项和待跟进事项",
        ],
        input_boundary=[
            "已确认的任务说明与技术方案",
            "现有代码上下文与运行环境约束",
            "验收标准、风险提示和依赖条件",
        ],
        output_boundary=[
            "代码改动与实现结果",
            "自测/验证记录",
            "可供评审继续接力的交付说明",
        ],
        default_skill_slots=["代码实现", "局部验证", "变更说明"],
        sort_order=30,
    ),
    RoleCatalogEntry(
        code=ProjectRoleCode.REVIEWER,
        name="评审者",
        summary="负责复核交付结果是否满足验收口径，并形成通过/退回结论。",
        responsibilities=[
            "按验收标准复核交付结果",
            "指出风险、缺口和需要回退的原因",
            "形成审查结论并沉淀评审意见",
        ],
        input_boundary=[
            "待评审的代码改动、日志或交付物",
            "项目验收标准与阶段守卫要求",
            "工程实现说明与已知风险列表",
        ],
        output_boundary=[
            "评审意见与缺陷清单",
            "通过、阻塞或返工结论",
            "供老板/下游角色继续处理的审查摘要",
        ],
        default_skill_slots=["审查清单", "质量闸门", "风险回放"],
        sort_order=40,
    ),
)


class RoleCatalogService:
    """Expose one built-in role catalog and project-specific role configs."""

    def __init__(
        self,
        *,
        project_repository: ProjectRepository,
        project_role_repository: ProjectRoleRepository,
    ) -> None:
        self.project_repository = project_repository
        self.project_role_repository = project_role_repository
        self._catalog_entry_map = {entry.code: entry for entry in _SYSTEM_ROLE_CATALOG}

    def list_system_role_catalog(self) -> list[RoleCatalogEntry]:
        """Return the immutable built-in Day05 role catalog."""

        return [entry.model_copy(deep=True) for entry in _SYSTEM_ROLE_CATALOG]

    def get_project_role_catalog(self, project_id: UUID) -> ProjectRoleCatalog | None:
        """Return one project's role catalog snapshot, seeding defaults if needed."""

        if not self.project_repository.exists(project_id):
            return None

        roles = self._ensure_project_roles_initialized(project_id)
        return self._build_project_catalog(project_id=project_id, roles=roles)

    def update_project_role_config(
        self,
        *,
        project_id: UUID,
        role_code: ProjectRoleCode,
        enabled: bool,
        name: str,
        summary: str,
        responsibilities: list[str],
        input_boundary: list[str],
        output_boundary: list[str],
        default_skill_slots: list[str],
        custom_notes: str | None,
        sort_order: int,
    ) -> ProjectRoleConfig | None:
        """Persist one edited project-role config and return the stored value."""

        if not self.project_repository.exists(project_id):
            return None

        roles = self._ensure_project_roles_initialized(project_id)
        existing_role = next(
            (role for role in roles if role.role_code == role_code),
            None,
        )
        if existing_role is None:
            raise ValueError(f"Unknown role code: {role_code}")

        updated_role = ProjectRoleConfig(
            id=existing_role.id,
            project_id=existing_role.project_id,
            role_code=existing_role.role_code,
            enabled=enabled,
            name=name,
            summary=summary,
            responsibilities=responsibilities,
            input_boundary=input_boundary,
            output_boundary=output_boundary,
            default_skill_slots=default_skill_slots,
            custom_notes=custom_notes,
            sort_order=sort_order,
            created_at=existing_role.created_at,
            updated_at=utc_now(),
        )
        return self.project_role_repository.save(updated_role)

    def resolve_task_role_assignment(
        self,
        *,
        project_id: UUID | None,
        title: str,
        input_summary: str,
        acceptance_criteria: list[str],
        source_draft_id: str | None = None,
        requested_owner_role_code: ProjectRoleCode | None = None,
        requested_upstream_role_code: ProjectRoleCode | None = None,
        requested_downstream_role_code: ProjectRoleCode | None = None,
        dependency_tasks: list[Task] | None = None,
    ) -> ResolvedTaskRoleAssignment:
        """Resolve one task's owner/upstream/downstream role chain."""

        if project_id is None:
            return ResolvedTaskRoleAssignment(
                owner_role_code=requested_owner_role_code,
                upstream_role_code=requested_upstream_role_code,
                downstream_role_code=requested_downstream_role_code,
                dispatch_status="no_project",
                handoff_reason="任务未挂接项目，保留请求中的角色链路。",
                responsibility_score=0.0,
            )

        catalog = self.get_project_role_catalog(project_id)
        roles = catalog.roles if catalog is not None else []
        role_map = {role.role_code: role for role in roles}
        enabled_roles = sorted(
            [role for role in roles if role.enabled],
            key=self._role_sort_key,
        )
        enabled_role_codes = [role.role_code for role in enabled_roles]
        dependency_tasks = dependency_tasks or []

        reason_parts: list[str] = []
        matched_terms: tuple[str, ...] = ()

        owner_role_code: ProjectRoleCode | None = None
        responsibility_score = 0.0
        dispatch_status = "unresolved"

        if (
            requested_owner_role_code is not None
            and requested_owner_role_code in enabled_role_codes
        ):
            owner_role_code = requested_owner_role_code
            dispatch_status = "explicit_owner"
            responsibility_score = 30.0
            reason_parts.append(
                f"任务已显式指定责任角色「{self._role_label(requested_owner_role_code, role_map)}」。"
            )
        else:
            if requested_owner_role_code is not None:
                reason_parts.append(
                    f"显式责任角色「{self._role_label(requested_owner_role_code, role_map)}」当前未启用，改为可执行角色。"
                )

            dependency_downstream_codes = [
                task.downstream_role_code
                for task in dependency_tasks
                if task.downstream_role_code is not None
            ]
            dependency_owner_codes = [
                task.owner_role_code
                for task in dependency_tasks
                if task.owner_role_code is not None
            ]

            dependency_candidate = self._pick_first_enabled_role_code(
                dependency_downstream_codes,
                enabled_role_codes,
            )
            if dependency_candidate is not None:
                owner_role_code = dependency_candidate
                dispatch_status = "dependency_handoff"
                responsibility_score = 25.0
                reason_parts.append(
                    "责任角色继承自上游依赖任务的默认交接方向。"
                )
            elif dependency_owner_codes:
                dependency_owner_candidate = self._pick_first_enabled_role_code(
                    dependency_owner_codes,
                    enabled_role_codes,
                )
                if dependency_owner_candidate is not None:
                    owner_role_code = dependency_owner_candidate
                    dispatch_status = "dependency_owner_fallback"
                    responsibility_score = 18.0
                    reason_parts.append(
                        "责任角色回落到依赖任务的实际责任角色，保证链路不断档。"
                    )

            if owner_role_code is None:
                matched_role, matched_terms = self._match_role_by_responsibility(
                    enabled_roles=enabled_roles,
                    title=title,
                    input_summary=input_summary,
                    acceptance_criteria=acceptance_criteria,
                    source_draft_id=source_draft_id,
                )
                if matched_role is not None and matched_terms:
                    owner_role_code = matched_role.role_code
                    dispatch_status = "responsibility_match"
                    responsibility_score = min(40.0, 12.0 + len(matched_terms) * 4.0)
                    reason_parts.append(
                        "根据任务文本与角色职责命中词分派给"
                        f"「{matched_role.name}」：{', '.join(matched_terms[:3])}。"
                    )

            if owner_role_code is None and enabled_roles:
                owner_role_code = enabled_roles[0].role_code
                dispatch_status = "ordered_fallback"
                responsibility_score = 5.0
                reason_parts.append(
                    f"未命中明确职责关键词，回落到当前启用链路中的首个角色「{enabled_roles[0].name}」。"
                )

        upstream_role_code = requested_upstream_role_code
        if upstream_role_code is None:
            dependency_owner_codes = [
                task.owner_role_code
                for task in dependency_tasks
                if task.owner_role_code is not None
            ]
            upstream_role_code = self._pick_first_role_code(dependency_owner_codes)
            if upstream_role_code is None and owner_role_code is not None:
                upstream_role_code = self._previous_role_code(
                    owner_role_code,
                    enabled_role_codes,
                )

        downstream_role_code = requested_downstream_role_code
        if downstream_role_code is None and owner_role_code is not None:
            downstream_role_code = self._next_role_code(
                owner_role_code,
                enabled_role_codes,
            )

        if owner_role_code is not None:
            reason_parts.append(
                f"派发结果：当前由「{self._role_label(owner_role_code, role_map)}」负责执行。"
            )
        else:
            reason_parts.append("派发结果：当前没有解析出可执行责任角色。")

        if upstream_role_code is not None:
            reason_parts.append(
                f"上游来源角色：{self._role_label(upstream_role_code, role_map)}。"
            )
        else:
            reason_parts.append("上游来源角色：未识别。")

        if downstream_role_code is not None:
            reason_parts.append(
                f"下游交接角色：{self._role_label(downstream_role_code, role_map)}。"
            )
        else:
            reason_parts.append("下游交接角色：暂无。")

        return ResolvedTaskRoleAssignment(
            owner_role_code=owner_role_code,
            upstream_role_code=upstream_role_code,
            downstream_role_code=downstream_role_code,
            dispatch_status=dispatch_status,
            handoff_reason=" ".join(reason_parts),
            responsibility_score=responsibility_score,
            matched_terms=matched_terms,
        )

    def _ensure_project_roles_initialized(
        self,
        project_id: UUID,
    ) -> list[ProjectRoleConfig]:
        """Backfill any missing built-in roles for one project."""

        persisted_roles = self.project_role_repository.list_by_project_id(project_id)
        persisted_role_codes = {role.role_code for role in persisted_roles}
        missing_roles = [
            catalog_entry.create_project_role_config(project_id)
            for catalog_entry in _SYSTEM_ROLE_CATALOG
            if catalog_entry.code not in persisted_role_codes
        ]
        if not missing_roles:
            return persisted_roles

        return self.project_role_repository.create_many(missing_roles)

    @staticmethod
    def _build_project_catalog(
        *,
        project_id: UUID,
        roles: list[ProjectRoleConfig],
    ) -> ProjectRoleCatalog:
        """Build one counted role catalog snapshot for API responses."""

        return ProjectRoleCatalog(
            project_id=project_id,
            available_role_count=len(roles),
            enabled_role_count=sum(1 for role in roles if role.enabled),
            roles=roles,
        )

    @staticmethod
    def _role_sort_key(role: ProjectRoleConfig) -> tuple[int, str]:
        """Return one stable ordering key for project roles."""

        return role.sort_order, role.name

    @staticmethod
    def _pick_first_enabled_role_code(
        role_codes: list[ProjectRoleCode],
        enabled_role_codes: list[ProjectRoleCode],
    ) -> ProjectRoleCode | None:
        """Return the first role code that is currently enabled."""

        enabled_code_set = set(enabled_role_codes)
        for role_code in role_codes:
            if role_code in enabled_code_set:
                return role_code

        return None

    @staticmethod
    def _pick_first_role_code(
        role_codes: list[ProjectRoleCode],
    ) -> ProjectRoleCode | None:
        """Return the first available role code from one ordered list."""

        for role_code in role_codes:
            return role_code

        return None

    @staticmethod
    def _previous_role_code(
        role_code: ProjectRoleCode,
        ordered_role_codes: list[ProjectRoleCode],
    ) -> ProjectRoleCode | None:
        """Return the previous enabled role in the collaboration chain."""

        try:
            role_index = ordered_role_codes.index(role_code)
        except ValueError:
            return None

        if role_index <= 0:
            return None

        return ordered_role_codes[role_index - 1]

    @staticmethod
    def _next_role_code(
        role_code: ProjectRoleCode,
        ordered_role_codes: list[ProjectRoleCode],
    ) -> ProjectRoleCode | None:
        """Return the next enabled role in the collaboration chain."""

        try:
            role_index = ordered_role_codes.index(role_code)
        except ValueError:
            return None

        if role_index >= len(ordered_role_codes) - 1:
            return None

        return ordered_role_codes[role_index + 1]

    def _match_role_by_responsibility(
        self,
        *,
        enabled_roles: list[ProjectRoleConfig],
        title: str,
        input_summary: str,
        acceptance_criteria: list[str],
        source_draft_id: str | None,
    ) -> tuple[ProjectRoleConfig | None, tuple[str, ...]]:
        """Match one task text against enabled role responsibilities."""

        task_text = " ".join(
            [
                title.strip().lower(),
                input_summary.strip().lower(),
                *(item.strip().lower() for item in acceptance_criteria),
                (source_draft_id or "").strip().lower(),
            ]
        )
        if not task_text.strip():
            return None, ()

        scored_matches: list[tuple[int, ProjectRoleConfig, tuple[str, ...]]] = []
        for role in enabled_roles:
            keywords = self._collect_role_keywords(role)
            matched_terms = tuple(
                sorted(
                    {
                        keyword
                        for keyword in keywords
                        if keyword and keyword in task_text
                    },
                    key=lambda item: (-len(item), item),
                )
            )
            scored_matches.append((len(matched_terms), role, matched_terms))

        if not scored_matches:
            return None, ()

        scored_matches.sort(
            key=lambda item: (
                -item[0],
                item[1].sort_order,
                item[1].name,
            )
        )
        top_score, top_role, matched_terms = scored_matches[0]
        if top_score <= 0:
            return None, ()

        return top_role, matched_terms

    def _collect_role_keywords(self, role: ProjectRoleConfig) -> set[str]:
        """Collect role phrases and lightweight keyword fragments."""

        keywords = {
            keyword.strip().lower()
            for keyword in _ROLE_MATCH_HINTS.get(role.role_code, ())
            if keyword.strip()
        }
        phrases = [
            role.name,
            role.summary,
            *role.responsibilities,
            *role.input_boundary,
            *role.output_boundary,
            *role.default_skill_slots,
        ]
        for phrase in phrases:
            normalized_phrase = phrase.strip().lower()
            if not normalized_phrase:
                continue

            keywords.add(normalized_phrase)
            for item in re.split(r"[、，,；;：:\s/（）()\-]+", normalized_phrase):
                if len(item) >= 2:
                    keywords.add(item)

        return {keyword for keyword in keywords if len(keyword) >= 2}

    @staticmethod
    def _role_label(
        role_code: ProjectRoleCode,
        role_map: dict[ProjectRoleCode, ProjectRoleConfig],
    ) -> str:
        """Return the human-readable label for one role code."""

        role = role_map.get(role_code)
        return role.name if role is not None else role_code.value
