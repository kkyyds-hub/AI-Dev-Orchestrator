"""Skill registry orchestration for V3 Day13."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain._base import utc_now
from app.domain.project import Project
from app.domain.project_role import ProjectRoleCatalog, ProjectRoleCode, ProjectRoleConfig
from app.domain.skill import (
    ProjectRoleBoundSkill,
    ProjectRoleSkillBinding,
    ProjectRoleSkillBindingGroup,
    ProjectSkillBindingSnapshot,
    SkillBindingSource,
    SkillDefinition,
    SkillRegistrySnapshot,
    SkillVersionRecord,
)
from app.repositories.project_repository import ProjectRepository
from app.repositories.skill_repository import SkillRepository
from app.services.role_catalog_service import RoleCatalogService


@dataclass(slots=True, frozen=True)
class SkillSeedTemplate:
    """Immutable built-in Skill seed definition."""

    code: str
    name: str
    summary: str
    purpose: str
    applicable_role_codes: tuple[ProjectRoleCode, ...]
    initial_version: str = "1.0.0"
    enabled: bool = True
    change_note: str = "Built-in Day13 Skill seeded into the registry."


_SYSTEM_SKILL_TEMPLATES: tuple[SkillSeedTemplate, ...] = (
    SkillSeedTemplate(
        code="requirements_clarification",
        name="需求澄清",
        summary="帮助产品角色把老板目标、背景信息和验收口径整理为可执行输入。",
        purpose="聚焦需求补全、上下文澄清和目标边界确认，避免项目在 Intake / Planning 阶段带着模糊输入继续推进。",
        applicable_role_codes=(ProjectRoleCode.PRODUCT_MANAGER,),
    ),
    SkillSeedTemplate(
        code="scope_breakdown",
        name="范围拆解",
        summary="把项目范围拆成阶段、里程碑和优先级明确的工作包。",
        purpose="用于产品角色输出范围边界、关键里程碑和可执行拆解建议，减少 Day03 规划草案与 Day04 阶段守卫之间的断层。",
        applicable_role_codes=(ProjectRoleCode.PRODUCT_MANAGER,),
    ),
    SkillSeedTemplate(
        code="priority_planning",
        name="优先级规划",
        summary="帮助产品角色判断当前阶段最该先推进哪些目标与任务。",
        purpose="结合业务价值、风险和验收窗口给出优先级建议，为任务映射和老板审批提供排序依据。",
        applicable_role_codes=(ProjectRoleCode.PRODUCT_MANAGER,),
    ),
    SkillSeedTemplate(
        code="solution_design",
        name="方案设计",
        summary="帮助架构角色沉淀系统边界、模块方案与接口草案。",
        purpose="将需求转成技术方案、关键边界和实现约束，支撑 Day06-Day08 的 SOP 协作链路。",
        applicable_role_codes=(ProjectRoleCode.ARCHITECT,),
    ),
    SkillSeedTemplate(
        code="dependency_analysis",
        name="依赖分析",
        summary="识别实施前置条件、外部依赖和潜在集成风险。",
        purpose="帮助架构角色提前暴露技术依赖、系统接口和资源约束，减少执行阶段的阻塞。",
        applicable_role_codes=(ProjectRoleCode.ARCHITECT,),
    ),
    SkillSeedTemplate(
        code="risk_assessment",
        name="风险评估",
        summary="对方案和交付路径中的关键不确定性做风险判断与提示。",
        purpose="用于识别高风险实现点、回退成本和验证盲区，可供架构与评审角色共同使用。",
        applicable_role_codes=(ProjectRoleCode.ARCHITECT, ProjectRoleCode.REVIEWER),
    ),
    SkillSeedTemplate(
        code="code_implementation",
        name="代码实现",
        summary="帮助工程角色把任务和方案落实为实际代码、脚本或配置改动。",
        purpose="围绕实现、联调和落地执行提供结构化推进能力，是工程角色的核心交付 Skill。",
        applicable_role_codes=(ProjectRoleCode.ENGINEER,),
    ),
    SkillSeedTemplate(
        code="local_verification",
        name="局部验证",
        summary="帮助工程角色补齐最小验证步骤、自测结论与风险说明。",
        purpose="要求工程角色在提交交付前留下可复查的局部验证结果，衔接 Day12 的复盘与返工链路。",
        applicable_role_codes=(ProjectRoleCode.ENGINEER,),
    ),
    SkillSeedTemplate(
        code="change_summary",
        name="变更说明",
        summary="帮助工程角色整理改动范围、影响面和限制项说明。",
        purpose="让下游评审、审批和时间线视图能快速理解这次交付改了什么、为何这样改。",
        applicable_role_codes=(ProjectRoleCode.ENGINEER,),
    ),
    SkillSeedTemplate(
        code="review_checklist",
        name="审查清单",
        summary="帮助评审角色按固定检查项复核交付结果。",
        purpose="沉淀可重复复用的检查口径，让评审不再完全依赖临场发挥。",
        applicable_role_codes=(ProjectRoleCode.REVIEWER,),
    ),
    SkillSeedTemplate(
        code="quality_gate",
        name="质量闸门",
        summary="帮助评审角色针对验收标准给出放行、阻塞或返工建议。",
        purpose="把 Day10-Day12 的审批判断进一步前移到角色层面，让质量判断拥有独立配置与版本记录。",
        applicable_role_codes=(ProjectRoleCode.REVIEWER,),
    ),
    SkillSeedTemplate(
        code="risk_replay",
        name="风险回放",
        summary="帮助评审角色回看历史问题、失败案例与潜在回退路径。",
        purpose="将历史风险与本次交付串联起来，方便项目详情回看当前角色绑定了哪套审查能力。",
        applicable_role_codes=(ProjectRoleCode.REVIEWER,),
    ),
)


class SkillRegistryService:
    """Expose the Day13 Skill registry and project role-binding views."""

    def __init__(
        self,
        *,
        project_repository: ProjectRepository,
        role_catalog_service: RoleCatalogService,
        skill_repository: SkillRepository,
    ) -> None:
        self.project_repository = project_repository
        self.role_catalog_service = role_catalog_service
        self.skill_repository = skill_repository

    def list_skill_registry(self) -> SkillRegistrySnapshot:
        """Return the current Skill registry snapshot."""

        skills = self._ensure_skill_registry_initialized()
        return SkillRegistrySnapshot(
            total_skill_count=len(skills),
            enabled_skill_count=sum(1 for skill in skills if skill.enabled),
            version_record_count=sum(len(skill.version_history) for skill in skills),
            skills=skills,
        )

    def upsert_skill(
        self,
        *,
        code: str,
        name: str,
        summary: str,
        purpose: str,
        applicable_role_codes: list[ProjectRoleCode],
        enabled: bool,
        version: str,
        change_note: str | None,
    ) -> SkillDefinition:
        """Create or update one Skill and append a version record when needed."""

        normalized_code = SkillDefinition.normalize_code(code)
        existing_skills = self._ensure_skill_registry_initialized()
        existing_skill = next(
            (skill for skill in existing_skills if skill.code == normalized_code),
            None,
        )
        existing_history = (
            {record.version for record in existing_skill.version_history}
            if existing_skill is not None
            else set()
        )

        if (
            existing_skill is not None
            and version != existing_skill.current_version
            and version in existing_history
        ):
            raise ValueError(
                f"Skill version already exists for {normalized_code}: {version}. Please choose a new version."
            )

        if existing_skill is None:
            skill_to_save = SkillDefinition(
                code=normalized_code,
                name=name,
                summary=summary,
                purpose=purpose,
                applicable_role_codes=applicable_role_codes,
                enabled=enabled,
                current_version=version,
                created_at=utc_now(),
                updated_at=utc_now(),
                version_history=[],
            )
        else:
            skill_to_save = SkillDefinition(
                id=existing_skill.id,
                code=normalized_code,
                name=name,
                summary=summary,
                purpose=purpose,
                applicable_role_codes=applicable_role_codes,
                enabled=enabled,
                current_version=version,
                created_at=existing_skill.created_at,
                updated_at=utc_now(),
                version_history=[],
            )

        saved_skill = self.skill_repository.save_skill(skill_to_save)

        if existing_skill is None or version != existing_skill.current_version:
            self.skill_repository.create_version(
                SkillVersionRecord(
                    skill_id=saved_skill.id,
                    version=version,
                    name=name,
                    summary=summary,
                    purpose=purpose,
                    applicable_role_codes=applicable_role_codes,
                    enabled=enabled,
                    change_note=change_note,
                )
            )

        return self._get_skill_with_history(saved_skill.code)

    def get_project_skill_bindings(
        self,
        project_id: UUID,
    ) -> ProjectSkillBindingSnapshot | None:
        """Return one project's current role-to-Skill binding snapshot."""

        project = self.project_repository.get_by_id(project_id)
        if project is None:
            return None

        role_catalog = self.role_catalog_service.get_project_role_catalog(project_id)
        if role_catalog is None:
            return None

        skills = self._ensure_skill_registry_initialized()
        bindings = self.skill_repository.list_role_bindings_by_project_id(project_id)
        if not bindings:
            default_bindings = self._build_default_role_bindings(
                project_id=project_id,
                roles=role_catalog.roles,
                skills=skills,
            )
            if default_bindings:
                bindings = self.skill_repository.create_many_role_bindings(default_bindings)

        return self._build_project_binding_snapshot(
            project=project,
            role_catalog=role_catalog,
            skills=skills,
            bindings=bindings,
        )

    def replace_project_role_skill_bindings(
        self,
        *,
        project_id: UUID,
        role_code: ProjectRoleCode,
        skill_codes: list[str],
    ) -> ProjectRoleSkillBindingGroup | None:
        """Replace all Skill bindings under one project role."""

        project = self.project_repository.get_by_id(project_id)
        if project is None:
            return None

        role_catalog = self.role_catalog_service.get_project_role_catalog(project_id)
        if role_catalog is None:
            return None

        target_role = next(
            (role for role in role_catalog.roles if role.role_code == role_code),
            None,
        )
        if target_role is None:
            raise ValueError(f"Unknown role code for project: {role_code}")

        skills = self._ensure_skill_registry_initialized()
        skill_by_code = {skill.code: skill for skill in skills}
        normalized_codes: list[str] = []
        seen_codes: set[str] = set()
        for skill_code in skill_codes:
            normalized_code = SkillDefinition.normalize_code(skill_code)
            if normalized_code in seen_codes:
                continue
            normalized_codes.append(normalized_code)
            seen_codes.add(normalized_code)

        selected_skills: list[SkillDefinition] = []
        for normalized_code in normalized_codes:
            skill = skill_by_code.get(normalized_code)
            if skill is None:
                raise ValueError(f"Skill not found: {normalized_code}")
            if role_code not in skill.applicable_role_codes:
                raise ValueError(
                    f"Skill {normalized_code} is not applicable to role {role_code.value}."
                )
            if not skill.enabled:
                raise ValueError(f"Skill is disabled and cannot be bound: {normalized_code}")

            selected_skills.append(skill)

        new_bindings = [
            ProjectRoleSkillBinding(
                project_id=project_id,
                role_code=role_code,
                skill_id=skill.id,
                skill_code=skill.code,
                skill_name=skill.name,
                bound_version=skill.current_version,
                binding_source=SkillBindingSource.MANUAL,
            )
            for skill in selected_skills
        ]
        updated_bindings = self.skill_repository.replace_role_bindings(
            project_id=project_id,
            role_code=role_code,
            bindings=new_bindings,
        )
        snapshot = self._build_project_binding_snapshot(
            project=project,
            role_catalog=role_catalog,
            skills=skills,
            bindings=updated_bindings,
        )
        return next((role for role in snapshot.roles if role.role_code == role_code), None)

    def _get_skill_with_history(self, code: str) -> SkillDefinition:
        """Return one Skill together with its version history."""

        skills = self._load_registry_skills_with_history()
        matched_skill = next((skill for skill in skills if skill.code == code), None)
        if matched_skill is None:
            raise ValueError(f"Skill not found after save: {code}")

        return matched_skill

    def _ensure_skill_registry_initialized(self) -> list[SkillDefinition]:
        """Seed built-in Skills and backfill missing version rows if needed."""

        existing_skills = self.skill_repository.list_skills()
        existing_by_code = {skill.code: skill for skill in existing_skills}

        for template in _SYSTEM_SKILL_TEMPLATES:
            if template.code in existing_by_code:
                continue

            saved_skill = self.skill_repository.save_skill(
                SkillDefinition(
                    code=template.code,
                    name=template.name,
                    summary=template.summary,
                    purpose=template.purpose,
                    applicable_role_codes=list(template.applicable_role_codes),
                    enabled=template.enabled,
                    current_version=template.initial_version,
                )
            )
            self.skill_repository.create_version(
                SkillVersionRecord(
                    skill_id=saved_skill.id,
                    version=template.initial_version,
                    name=template.name,
                    summary=template.summary,
                    purpose=template.purpose,
                    applicable_role_codes=list(template.applicable_role_codes),
                    enabled=template.enabled,
                    change_note=template.change_note,
                )
            )

        skills = self.skill_repository.list_skills()
        versions_by_skill_id = self.skill_repository.list_versions_by_skill_ids(
            [skill.id for skill in skills]
        )

        backfilled = False
        for skill in skills:
            history = versions_by_skill_id.get(skill.id, [])
            history_versions = {record.version for record in history}
            if skill.current_version in history_versions:
                continue

            self.skill_repository.create_version(
                SkillVersionRecord(
                    skill_id=skill.id,
                    version=skill.current_version,
                    name=skill.name,
                    summary=skill.summary,
                    purpose=skill.purpose,
                    applicable_role_codes=skill.applicable_role_codes,
                    enabled=skill.enabled,
                    change_note="Backfilled current Skill state into version history.",
                )
            )
            backfilled = True

        if backfilled:
            return self._load_registry_skills_with_history()

        return self._build_skills_with_history(skills, versions_by_skill_id)

    def _load_registry_skills_with_history(self) -> list[SkillDefinition]:
        """Load all Skill rows together with their version history."""

        skills = self.skill_repository.list_skills()
        versions_by_skill_id = self.skill_repository.list_versions_by_skill_ids(
            [skill.id for skill in skills]
        )
        return self._build_skills_with_history(skills, versions_by_skill_id)

    @staticmethod
    def _build_skills_with_history(
        skills: list[SkillDefinition],
        versions_by_skill_id: dict[UUID, list[SkillVersionRecord]],
    ) -> list[SkillDefinition]:
        """Attach version history to Skill rows."""

        return [
            skill.model_copy(
                update={
                    "version_history": list(versions_by_skill_id.get(skill.id, [])),
                }
            )
            for skill in skills
        ]

    @staticmethod
    def _build_default_role_bindings(
        *,
        project_id: UUID,
        roles: list[ProjectRoleConfig],
        skills: list[SkillDefinition],
    ) -> list[ProjectRoleSkillBinding]:
        """Seed initial role bindings from Day05 default Skill slots."""

        bindings: list[ProjectRoleSkillBinding] = []
        enabled_skills = [skill for skill in skills if skill.enabled]

        for role in roles:
            default_slot_names = {slot.strip() for slot in role.default_skill_slots if slot.strip()}
            matched_skills = [
                skill
                for skill in enabled_skills
                if role.role_code in skill.applicable_role_codes
                and (not default_slot_names or skill.name in default_slot_names)
            ]
            if not matched_skills:
                matched_skills = [
                    skill
                    for skill in enabled_skills
                    if role.role_code in skill.applicable_role_codes
                ]

            for skill in matched_skills:
                bindings.append(
                    ProjectRoleSkillBinding(
                        project_id=project_id,
                        role_code=role.role_code,
                        skill_id=skill.id,
                        skill_code=skill.code,
                        skill_name=skill.name,
                        bound_version=skill.current_version,
                        binding_source=SkillBindingSource.DEFAULT_SEED,
                    )
                )

        return bindings

    @staticmethod
    def _build_project_binding_snapshot(
        *,
        project: Project,
        role_catalog: ProjectRoleCatalog,
        skills: list[SkillDefinition],
        bindings: list[ProjectRoleSkillBinding],
    ) -> ProjectSkillBindingSnapshot:
        """Resolve raw bindings into the Day13 project snapshot view."""

        bindings_by_role: dict[ProjectRoleCode, list[ProjectRoleSkillBinding]] = {}
        for binding in bindings:
            bindings_by_role.setdefault(binding.role_code, []).append(binding)

        skill_by_id = {skill.id: skill for skill in skills}
        role_groups: list[ProjectRoleSkillBindingGroup] = []

        for role in role_catalog.roles:
            role_bindings = bindings_by_role.get(role.role_code, [])
            resolved_skills: list[ProjectRoleBoundSkill] = []

            for binding in role_bindings:
                matched_skill = skill_by_id.get(binding.skill_id)
                if matched_skill is None:
                    resolved_skills.append(
                        ProjectRoleBoundSkill(
                            skill_id=binding.skill_id,
                            skill_code=binding.skill_code,
                            skill_name=binding.skill_name,
                            summary="Skill 当前已不在注册中心中。",
                            purpose="该绑定保留历史版本引用，请在注册中心中检查变更记录。",
                            bound_version=binding.bound_version,
                            registry_current_version=None,
                            registry_enabled=False,
                            upgrade_available=False,
                            applicable_role_codes=[role.role_code],
                            binding_source=binding.binding_source,
                            created_at=binding.created_at,
                            updated_at=binding.updated_at,
                        )
                    )
                    continue

                resolved_skills.append(
                    ProjectRoleBoundSkill(
                        skill_id=binding.skill_id,
                        skill_code=matched_skill.code,
                        skill_name=binding.skill_name,
                        summary=matched_skill.summary,
                        purpose=matched_skill.purpose,
                        bound_version=binding.bound_version,
                        registry_current_version=matched_skill.current_version,
                        registry_enabled=matched_skill.enabled,
                        upgrade_available=(
                            binding.bound_version != matched_skill.current_version
                        ),
                        applicable_role_codes=matched_skill.applicable_role_codes,
                        binding_source=binding.binding_source,
                        created_at=binding.created_at,
                        updated_at=binding.updated_at,
                    )
                )

            resolved_skills.sort(key=lambda item: (item.skill_name, item.skill_code))
            role_groups.append(
                ProjectRoleSkillBindingGroup(
                    role_code=role.role_code,
                    role_name=role.name,
                    role_enabled=role.enabled,
                    default_skill_slots=role.default_skill_slots,
                    bound_skill_count=len(resolved_skills),
                    skills=resolved_skills,
                )
            )

        return ProjectSkillBindingSnapshot(
            project_id=project.id,
            project_name=project.name,
            total_roles=len(role_groups),
            enabled_roles=sum(1 for role in role_groups if role.role_enabled),
            total_bound_skills=sum(len(role.skills) for role in role_groups),
            outdated_binding_count=sum(
                1
                for role in role_groups
                for skill in role.skills
                if skill.upgrade_available
            ),
            roles=role_groups,
        )
