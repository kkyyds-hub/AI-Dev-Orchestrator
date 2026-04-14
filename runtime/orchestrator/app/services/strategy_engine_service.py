"""Day 15 strategy engine for role, model and Skill routing."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from pydantic import Field, ValidationError, model_validator

from app.core.config import settings
from app.domain._base import DomainModel
from app.domain.project import Project, ProjectStage
from app.domain.project_role import ProjectRoleCode
from app.domain.run import (
    RunBudgetPressureLevel,
    RunBudgetStrategyAction,
    RunRoutingScoreItem,
    RunStrategyDecision,
    RunStrategyReasonItem,
)
from app.domain.skill import ProjectRoleBoundSkill
from app.domain.task import Task, TaskPriority, TaskRiskLevel
from app.repositories.project_repository import ProjectRepository
from app.services.budget_guard_service import (
    BudgetGuardService,
    BudgetRoutingDirective,
    BudgetSnapshot,
)
from app.services.role_catalog_service import (
    ResolvedTaskRoleAssignment,
    RoleCatalogService,
)
from app.services.skill_registry_service import SkillRegistryService


_MODEL_TIERS = ("economy", "balanced", "premium")
_STAGE_LABELS = {
    ProjectStage.INTAKE: "需求 Intake",
    ProjectStage.PLANNING: "规划",
    ProjectStage.EXECUTION: "执行",
    ProjectStage.VERIFICATION: "验证",
    ProjectStage.DELIVERY: "交付",
}
_ROLE_LABELS = {
    ProjectRoleCode.PRODUCT_MANAGER: "产品经理",
    ProjectRoleCode.ARCHITECT: "架构师",
    ProjectRoleCode.ENGINEER: "工程师",
    ProjectRoleCode.REVIEWER: "评审",
}


class StrategyModelProfile(DomainModel):
    """One configured model profile selectable by the strategy engine."""

    tier: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=100)
    model_name: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=500)


class StrategyRuleSet(DomainModel):
    """Minimal editable Day 15 strategy rule set."""

    version: str = Field(default="day15.v1", min_length=1, max_length=40)
    max_selected_skills: int = Field(default=3, ge=1, le=5)
    model_profiles: dict[str, StrategyModelProfile]
    budget_model_tiers: dict[str, str]
    role_model_tier_preferences: dict[str, str] = Field(default_factory=dict)
    stage_model_tier_overrides: dict[str, dict[str, str]] = Field(default_factory=dict)
    stage_role_boosts: dict[str, dict[str, float]] = Field(default_factory=dict)
    stage_skill_preferences: dict[str, dict[str, list[str]]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_referenced_model_tiers(self) -> "StrategyRuleSet":
        """Ensure all configured tier references point at declared profiles."""

        declared_tiers = set(self.model_profiles)
        if not declared_tiers:
            raise ValueError("At least one model profile must be configured.")

        referenced_tiers = set(self.budget_model_tiers.values()) | set(
            self.role_model_tier_preferences.values()
        )
        for stage_rules in self.stage_model_tier_overrides.values():
            referenced_tiers.update(stage_rules.values())

        missing_tiers = sorted(referenced_tiers - declared_tiers)
        if missing_tiers:
            raise ValueError(
                "Unknown model tier referenced by strategy rules: "
                + ", ".join(missing_tiers)
            )

        return self


class StrategyRuleSetSnapshot(DomainModel):
    """Serializable rule-set view returned to the UI."""

    source: str = Field(min_length=1, max_length=40)
    storage_path: str = Field(min_length=1, max_length=500)
    rules: dict[str, object] = Field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ResolvedTaskStrategy:
    """Resolved Day 15 strategy snapshot for one candidate task."""

    project: Project | None
    project_stage: ProjectStage | None
    role_assignment: ResolvedTaskRoleAssignment
    budget_snapshot: BudgetSnapshot
    budget_directive: BudgetRoutingDirective
    model_tier: str
    model_profile: StrategyModelProfile
    selected_skill_codes: tuple[str, ...]
    selected_skill_names: tuple[str, ...]
    strategy_code: str
    strategy_summary: str
    strategy_reasons: list[RunStrategyReasonItem]
    routing_score_items: list[RunRoutingScoreItem]
    rule_codes: tuple[str, ...]
    strategy_decision: RunStrategyDecision


@dataclass(slots=True, frozen=True)
class RoleModelPolicyRuntimeTrace:
    """Explain how role-model policy was applied for one routing decision."""

    source: str
    desired_tier: str
    adjusted_tier: str
    selected_tier: str
    stage_override_applied: bool
    stage_key: str
    role_key: str


def _default_rule_set() -> StrategyRuleSet:
    """Return the built-in Day 15 rule set."""

    return StrategyRuleSet(
        version="day15.v1",
        max_selected_skills=3,
        model_profiles={
            "economy": StrategyModelProfile(
                tier="economy",
                label="经济模型",
                model_name="gpt-4.1-mini",
                summary="预算紧张时优先选用的经济档模型。",
            ),
            "balanced": StrategyModelProfile(
                tier="balanced",
                label="均衡模型",
                model_name="gpt-4.1",
                summary="默认档位模型，兼顾质量与成本。",
            ),
            "premium": StrategyModelProfile(
                tier="premium",
                label="高质量模型",
                model_name="gpt-5",
                summary="高风险或验证阶段优先使用的高质量模型。",
            ),
        },
        budget_model_tiers={
            RunBudgetPressureLevel.NORMAL.value: "balanced",
            RunBudgetPressureLevel.WARNING.value: "balanced",
            RunBudgetPressureLevel.CRITICAL.value: "economy",
            RunBudgetPressureLevel.BLOCKED.value: "economy",
        },
        role_model_tier_preferences={
            ProjectRoleCode.PRODUCT_MANAGER.value: "balanced",
            ProjectRoleCode.ARCHITECT.value: "balanced",
            ProjectRoleCode.ENGINEER.value: "balanced",
            ProjectRoleCode.REVIEWER.value: "premium",
        },
        stage_model_tier_overrides={
            ProjectStage.PLANNING.value: {
                ProjectRoleCode.PRODUCT_MANAGER.value: "balanced",
                ProjectRoleCode.ARCHITECT.value: "balanced",
            },
            ProjectStage.EXECUTION.value: {
                ProjectRoleCode.ENGINEER.value: "balanced",
            },
            ProjectStage.VERIFICATION.value: {
                ProjectRoleCode.REVIEWER.value: "premium",
            },
        },
        stage_role_boosts={
            ProjectStage.INTAKE.value: {
                ProjectRoleCode.PRODUCT_MANAGER.value: 24.0,
                ProjectRoleCode.ARCHITECT.value: 6.0,
                ProjectRoleCode.ENGINEER.value: 0.0,
                ProjectRoleCode.REVIEWER.value: 0.0,
            },
            ProjectStage.PLANNING.value: {
                ProjectRoleCode.PRODUCT_MANAGER.value: 22.0,
                ProjectRoleCode.ARCHITECT.value: 14.0,
                ProjectRoleCode.ENGINEER.value: 4.0,
                ProjectRoleCode.REVIEWER.value: 4.0,
            },
            ProjectStage.EXECUTION.value: {
                ProjectRoleCode.PRODUCT_MANAGER.value: 4.0,
                ProjectRoleCode.ARCHITECT.value: 10.0,
                ProjectRoleCode.ENGINEER.value: 20.0,
                ProjectRoleCode.REVIEWER.value: 8.0,
            },
            ProjectStage.VERIFICATION.value: {
                ProjectRoleCode.PRODUCT_MANAGER.value: 2.0,
                ProjectRoleCode.ARCHITECT.value: 6.0,
                ProjectRoleCode.ENGINEER.value: 8.0,
                ProjectRoleCode.REVIEWER.value: 24.0,
            },
            ProjectStage.DELIVERY.value: {
                ProjectRoleCode.PRODUCT_MANAGER.value: 8.0,
                ProjectRoleCode.ARCHITECT.value: 4.0,
                ProjectRoleCode.ENGINEER.value: 6.0,
                ProjectRoleCode.REVIEWER.value: 18.0,
            },
        },
        stage_skill_preferences={
            ProjectStage.INTAKE.value: {
                ProjectRoleCode.PRODUCT_MANAGER.value: [
                    "requirements_clarification",
                    "scope_breakdown",
                    "priority_planning",
                ],
            },
            ProjectStage.PLANNING.value: {
                ProjectRoleCode.PRODUCT_MANAGER.value: [
                    "requirements_clarification",
                    "scope_breakdown",
                    "priority_planning",
                ],
                ProjectRoleCode.ARCHITECT.value: [
                    "solution_design",
                    "dependency_analysis",
                    "risk_assessment",
                ],
            },
            ProjectStage.EXECUTION.value: {
                ProjectRoleCode.ARCHITECT.value: [
                    "dependency_analysis",
                    "risk_assessment",
                ],
                ProjectRoleCode.ENGINEER.value: [
                    "code_implementation",
                    "local_verification",
                    "change_summary",
                ],
            },
            ProjectStage.VERIFICATION.value: {
                ProjectRoleCode.ENGINEER.value: [
                    "local_verification",
                    "change_summary",
                ],
                ProjectRoleCode.REVIEWER.value: [
                    "review_checklist",
                    "quality_gate",
                    "risk_replay",
                ],
            },
            ProjectStage.DELIVERY.value: {
                ProjectRoleCode.PRODUCT_MANAGER.value: [
                    "priority_planning",
                ],
                ProjectRoleCode.REVIEWER.value: [
                    "quality_gate",
                    "risk_replay",
                ],
            },
        },
    )


class StrategyEngineService:
    """Centralize Day 15 role / model / Skill routing rules."""

    def __init__(
        self,
        *,
        project_repository: ProjectRepository,
        role_catalog_service: RoleCatalogService,
        skill_registry_service: SkillRegistryService,
        budget_guard_service: BudgetGuardService,
    ) -> None:
        self.project_repository = project_repository
        self.role_catalog_service = role_catalog_service
        self.skill_registry_service = skill_registry_service
        self.budget_guard_service = budget_guard_service
        self.rules_path = (
            settings.runtime_data_dir / "strategy-rules" / "strategy-rule-set.json"
        )

    def get_rule_set_snapshot(self) -> StrategyRuleSetSnapshot:
        """Return the current rule set together with its source metadata."""

        rules, source = self._load_rule_set()
        return StrategyRuleSetSnapshot(
            source=source,
            storage_path=str(self.rules_path),
            rules=rules.model_dump(mode="json"),
        )

    def update_rule_set(self, *, rules_payload: dict[str, object]) -> StrategyRuleSetSnapshot:
        """Validate and persist one complete rule-set replacement."""

        try:
            rules = StrategyRuleSet.model_validate(rules_payload)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

        self.rules_path.parent.mkdir(parents=True, exist_ok=True)
        self.rules_path.write_text(
            json.dumps(rules.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return StrategyRuleSetSnapshot(
            source="runtime_override",
            storage_path=str(self.rules_path),
            rules=rules.model_dump(mode="json"),
        )

    def resolve_task_strategy(
        self,
        *,
        task: Task,
        execution_attempts: int,
        recent_failure_count: int,
        budget_snapshot: BudgetSnapshot | None = None,
        dependency_tasks: list[Task] | None = None,
    ) -> ResolvedTaskStrategy:
        """Resolve role, model and Skill choices for one candidate task."""

        rules, _ = self._load_rule_set()
        snapshot = budget_snapshot or self.budget_guard_service.build_budget_snapshot()
        budget_directive = self.budget_guard_service.build_routing_directive(
            risk_level=task.risk_level,
            execution_attempts=execution_attempts,
            recent_failure_count=recent_failure_count,
            snapshot=snapshot,
        )
        project = (
            self.project_repository.get_by_id(task.project_id)
            if task.project_id is not None
            else None
        )
        project_stage = project.stage if project is not None else None
        role_assignment = self.role_catalog_service.resolve_task_role_assignment(
            project_id=task.project_id,
            title=task.title,
            input_summary=task.input_summary,
            acceptance_criteria=task.acceptance_criteria,
            source_draft_id=task.source_draft_id,
            requested_owner_role_code=task.owner_role_code,
            requested_upstream_role_code=task.upstream_role_code,
            requested_downstream_role_code=task.downstream_role_code,
            dependency_tasks=dependency_tasks or [],
        )

        role_key = role_assignment.owner_role_code.value if role_assignment.owner_role_code else "unassigned"
        stage_key = project_stage.value if project_stage is not None else "unscoped"

        role_stage_score = rules.stage_role_boosts.get(stage_key, {}).get(role_key, 0.0)
        role_stage_detail = self._build_role_stage_detail(
            project_stage=project_stage,
            role_assignment=role_assignment,
            role_stage_score=role_stage_score,
        )

        selected_skills, skill_rule_codes, skill_score, skill_reason = self._select_skills(
            project_id=task.project_id,
            project_stage=project_stage,
            owner_role_code=role_assignment.owner_role_code,
            rules=rules,
        )
        selected_skill_codes = tuple(skill.skill_code for skill in selected_skills)
        selected_skill_names = tuple(skill.skill_name for skill in selected_skills)

        (
            model_tier,
            model_profile,
            model_rule_codes,
            model_score,
            model_reason,
            role_model_policy_trace,
        ) = self._select_model_profile(
            project_stage=project_stage,
            owner_role_code=role_assignment.owner_role_code,
            priority=task.priority,
            risk_level=task.risk_level,
            budget_pressure_level=snapshot.pressure_level,
            budget_action=snapshot.suggested_action,
            budget_preferred_model_tier=budget_directive.preferred_model_tier,
            rules=rules,
        )

        strategy_code = (
            f"se-{stage_key}-{role_key}-{model_tier}-{snapshot.pressure_level.value}"
        )[:100]
        rule_codes = tuple(
            code
            for code in (
                f"budget:{snapshot.pressure_level.value}",
                f"stage-role:{stage_key}:{role_key}",
                *skill_rule_codes,
                *model_rule_codes,
            )
            if code
        )

        strategy_reasons = [
            RunStrategyReasonItem(
                code="budget_pressure",
                label="预算压力",
                detail=(
                    f"预算压力为 {snapshot.pressure_level.value}，预算策略动作为 "
                    f"{snapshot.suggested_action.value}，预算守卫建议的基线模型层级为 "
                    f"{budget_directive.preferred_model_tier}。"
                ),
                score=budget_directive.score_adjustment,
            ),
            RunStrategyReasonItem(
                code="role_stage_alignment",
                label="阶段-角色匹配",
                detail=role_stage_detail,
                score=role_stage_score,
            ),
            RunStrategyReasonItem(
                code="skill_binding",
                label="Skill 绑定",
                detail=skill_reason,
                score=skill_score,
            ),
            RunStrategyReasonItem(
                code="model_selection",
                label="模型选择",
                detail=model_reason,
                score=model_score,
            ),
            RunStrategyReasonItem(
                code="role_model_policy_runtime",
                label="Role Model Policy Runtime",
                detail=(
                    f"source={role_model_policy_trace.source}; "
                    f"desired={role_model_policy_trace.desired_tier}; "
                    f"adjusted={role_model_policy_trace.adjusted_tier}; "
                    f"selected={role_model_policy_trace.selected_tier}; "
                    f"stage_override={role_model_policy_trace.stage_override_applied}."
                ),
                score=None,
            ),
        ]

        if role_assignment.matched_terms:
            strategy_reasons.append(
                RunStrategyReasonItem(
                    code="responsibility_terms",
                    label="职责命中词",
                    detail=(
                        "任务文本命中角色职责关键词："
                        + ", ".join(role_assignment.matched_terms[:4])
                    ),
                    score=role_assignment.responsibility_score,
                )
            )

        strategy_summary = self._build_strategy_summary(
            project_stage=project_stage,
            role_assignment=role_assignment,
            model_profile=model_profile,
            selected_skill_names=selected_skill_names,
            budget_snapshot=snapshot,
        )

        routing_score_items = [
            RunRoutingScoreItem(
                code="stage_role_alignment",
                label="阶段角色匹配",
                score=role_stage_score,
                detail=role_stage_detail,
            ),
            RunRoutingScoreItem(
                code="skill_binding_alignment",
                label="Skill 绑定加权",
                score=skill_score,
                detail=skill_reason,
            ),
            RunRoutingScoreItem(
                code="model_budget_alignment",
                label="模型预算匹配",
                score=model_score,
                detail=model_reason,
            ),
        ]

        strategy_decision = RunStrategyDecision(
            project_stage=project_stage,
            owner_role_code=role_assignment.owner_role_code,
            model_tier=model_tier,
            model_name=model_profile.model_name,
            selected_skill_codes=list(selected_skill_codes),
            selected_skill_names=list(selected_skill_names),
            budget_pressure_level=snapshot.pressure_level,
            budget_action=snapshot.suggested_action,
            strategy_code=strategy_code,
            summary=strategy_summary,
            role_model_policy_source=role_model_policy_trace.source,
            role_model_policy_desired_tier=role_model_policy_trace.desired_tier,
            role_model_policy_adjusted_tier=role_model_policy_trace.adjusted_tier,
            role_model_policy_final_tier=role_model_policy_trace.selected_tier,
            role_model_policy_stage_override_applied=(
                role_model_policy_trace.stage_override_applied
            ),
            rule_codes=list(rule_codes),
            reasons=strategy_reasons,
        )

        return ResolvedTaskStrategy(
            project=project,
            project_stage=project_stage,
            role_assignment=role_assignment,
            budget_snapshot=snapshot,
            budget_directive=budget_directive,
            model_tier=model_tier,
            model_profile=model_profile,
            selected_skill_codes=selected_skill_codes,
            selected_skill_names=selected_skill_names,
            strategy_code=strategy_code,
            strategy_summary=strategy_summary,
            strategy_reasons=strategy_reasons,
            routing_score_items=routing_score_items,
            rule_codes=rule_codes,
            strategy_decision=strategy_decision,
        )

    def _load_rule_set(self) -> tuple[StrategyRuleSet, str]:
        """Load the configured rule set with a safe default fallback."""

        if not self.rules_path.exists():
            return _default_rule_set(), "default"

        try:
            raw_payload = json.loads(self.rules_path.read_text(encoding="utf-8"))
            return StrategyRuleSet.model_validate(raw_payload), "runtime_override"
        except (OSError, json.JSONDecodeError, ValidationError):
            return _default_rule_set(), "default_fallback"
    def _select_skills(
        self,
        *,
        project_id,
        project_stage: ProjectStage | None,
        owner_role_code: ProjectRoleCode | None,
        rules: StrategyRuleSet,
    ) -> tuple[list[ProjectRoleBoundSkill], tuple[str, ...], float, str]:
        """Pick the most relevant bound Skills for the current stage and role."""

        if project_id is None or owner_role_code is None:
            return (
                [],
                (),
                0.0,
                "Task has no scoped project/owner role, so project-level Skill bindings are skipped.",
            )

        snapshot = self.skill_registry_service.get_project_skill_bindings(project_id)
        if snapshot is None:
            return (
                [],
                (),
                0.0,
                "Project Skill bindings are not initialized yet.",
            )

        role_group = next(
            (role for role in snapshot.roles if role.role_code == owner_role_code),
            None,
        )
        if role_group is None:
            return (
                [],
                (),
                0.0,
                f"Role {owner_role_code.value} has no available project Skill bindings.",
            )

        enabled_skills = [skill for skill in role_group.skills if skill.registry_enabled]
        stage_key = project_stage.value if project_stage is not None else "unscoped"
        preferred_codes = rules.stage_skill_preferences.get(stage_key, {}).get(
            owner_role_code.value,
            [],
        )
        preferred_matches = [
            skill for skill in enabled_skills if skill.skill_code in preferred_codes
        ]
        other_matches = [
            skill for skill in enabled_skills if skill.skill_code not in preferred_codes
        ]
        ordered_skills = [*preferred_matches, *other_matches]
        selected_skills = ordered_skills[: rules.max_selected_skills]

        if preferred_matches:
            score = min(18.0, 6.0 + len(selected_skills) * 4.0)
            return (
                selected_skills,
                (f"skills:{stage_key}:{owner_role_code.value}",),
                score,
                (
                    f"Stage {stage_key} configured preferred Skills for role "
                    f"{owner_role_code.value}: {', '.join(preferred_codes[:4])}; "
                    "selected "
                    + ", ".join(skill.skill_name for skill in selected_skills)
                    + "."
                ),
            )

        if selected_skills:
            score = min(8.0, 2.0 + len(selected_skills) * 2.0)
            return (
                selected_skills,
                (f"skills:fallback:{owner_role_code.value}",),
                score,
                (
                    "No stage-specific preferred Skills matched; using role-level enabled Skills: "
                    + ", ".join(skill.skill_name for skill in selected_skills)
                    + "."
                ),
            )

        return (
            [],
            (f"skills:missing:{owner_role_code.value}",),
            -8.0,
            (
                f"Role {owner_role_code.value} currently has no usable Skill bindings; "
                "routing score is conservatively reduced."
            ),
        )

    def _select_model_profile(
        self,
        *,
        project_stage: ProjectStage | None,
        owner_role_code: ProjectRoleCode | None,
        priority: TaskPriority,
        risk_level: TaskRiskLevel,
        budget_pressure_level: RunBudgetPressureLevel,
        budget_action: RunBudgetStrategyAction,
        budget_preferred_model_tier: str,
        rules: StrategyRuleSet,
    ) -> tuple[
        str,
        StrategyModelProfile,
        tuple[str, ...],
        float,
        str,
        RoleModelPolicyRuntimeTrace,
    ]:
        """Select the model profile under stage / role / budget constraints."""

        stage_key = project_stage.value if project_stage is not None else "unscoped"
        role_key = owner_role_code.value if owner_role_code is not None else "unassigned"
        desired_tier = rules.role_model_tier_preferences.get(
            role_key,
            budget_preferred_model_tier,
        )
        stage_override = rules.stage_model_tier_overrides.get(stage_key, {}).get(role_key)
        policy_source = (
            "stage_override"
            if stage_override
            else (
                "role_preference"
                if role_key in rules.role_model_tier_preferences
                else "budget_fallback"
            )
        )
        if stage_override:
            desired_tier = stage_override

        adjusted_tier = self._apply_risk_priority_adjustment(
            desired_tier=desired_tier,
            priority=priority,
            risk_level=risk_level,
            budget_pressure_level=budget_pressure_level,
            project_stage=project_stage,
            owner_role_code=owner_role_code,
        )
        selected_tier = self._cap_tier_by_budget(
            desired_tier=adjusted_tier,
            budget_pressure_level=budget_pressure_level,
            budget_preferred_model_tier=budget_preferred_model_tier,
        )
        model_profile = rules.model_profiles.get(selected_tier) or next(
            iter(rules.model_profiles.values())
        )
        score = self._score_model_budget_alignment(
            selected_tier=selected_tier,
            budget_pressure_level=budget_pressure_level,
            risk_level=risk_level,
            priority=priority,
        )
        role_model_policy_trace = RoleModelPolicyRuntimeTrace(
            source=policy_source,
            desired_tier=desired_tier,
            adjusted_tier=adjusted_tier,
            selected_tier=selected_tier,
            stage_override_applied=bool(stage_override),
            stage_key=stage_key,
            role_key=role_key,
        )

        return (
            selected_tier,
            model_profile,
            (
                f"model:budget:{budget_pressure_level.value}",
                f"model:role:{role_key}",
                f"model:stage:{stage_key}",
            ),
            score,
            (
                f"预算动作 {budget_action.value} 下的基线模型层级是 "
                f"{budget_preferred_model_tier}；角色/阶段期望层级是 {desired_tier}；"
                f"风险与优先级调整后为 {adjusted_tier}，最终选用 {selected_tier} -> "
                f"{model_profile.model_name}。"
            ),
            role_model_policy_trace,
        )

    @staticmethod
    def _apply_risk_priority_adjustment(
        *,
        desired_tier: str,
        priority: TaskPriority,
        risk_level: TaskRiskLevel,
        budget_pressure_level: RunBudgetPressureLevel,
        project_stage: ProjectStage | None,
        owner_role_code: ProjectRoleCode | None,
    ) -> str:
        """Apply lightweight quality-oriented promotions before budget capping."""

        if budget_pressure_level in {
            RunBudgetPressureLevel.CRITICAL,
            RunBudgetPressureLevel.BLOCKED,
        }:
            return "economy"

        tier = desired_tier
        if risk_level == TaskRiskLevel.HIGH or priority == TaskPriority.URGENT:
            tier = StrategyEngineService._promote_tier(tier)

        if (
            owner_role_code == ProjectRoleCode.REVIEWER
            and project_stage == ProjectStage.VERIFICATION
        ):
            tier = StrategyEngineService._promote_tier(tier)

        if (
            risk_level == TaskRiskLevel.LOW
            and priority == TaskPriority.LOW
            and budget_pressure_level == RunBudgetPressureLevel.WARNING
        ):
            tier = StrategyEngineService._demote_tier(tier)

        return tier

    @staticmethod
    def _cap_tier_by_budget(
        *,
        desired_tier: str,
        budget_pressure_level: RunBudgetPressureLevel,
        budget_preferred_model_tier: str,
    ) -> str:
        """Cap the desired tier to the highest budget-allowed level."""

        max_allowed_tier = {
            RunBudgetPressureLevel.NORMAL: "premium",
            RunBudgetPressureLevel.WARNING: "balanced",
            RunBudgetPressureLevel.CRITICAL: "economy",
            RunBudgetPressureLevel.BLOCKED: "economy",
        }[budget_pressure_level]

        target_index = _MODEL_TIERS.index(desired_tier) if desired_tier in _MODEL_TIERS else 1
        max_index = _MODEL_TIERS.index(max_allowed_tier)
        if target_index > max_index:
            return max_allowed_tier

        if desired_tier in _MODEL_TIERS:
            return desired_tier

        return budget_preferred_model_tier if budget_preferred_model_tier in _MODEL_TIERS else "balanced"

    @staticmethod
    def _score_model_budget_alignment(
        *,
        selected_tier: str,
        budget_pressure_level: RunBudgetPressureLevel,
        risk_level: TaskRiskLevel,
        priority: TaskPriority,
    ) -> float:
        """Produce one small routing bonus/penalty for model-vs-budget alignment."""

        if budget_pressure_level == RunBudgetPressureLevel.BLOCKED:
            return -30.0

        if budget_pressure_level == RunBudgetPressureLevel.CRITICAL:
            return 10.0 if selected_tier == "economy" else -15.0

        if budget_pressure_level == RunBudgetPressureLevel.WARNING:
            if selected_tier == "economy":
                return 6.0
            if selected_tier == "balanced":
                return 4.0
            return -8.0

        if selected_tier == "premium":
            return 10.0 if risk_level == TaskRiskLevel.HIGH or priority == TaskPriority.URGENT else 4.0
        if selected_tier == "balanced":
            return 6.0
        return 2.0 if risk_level == TaskRiskLevel.LOW else -3.0

    @staticmethod
    def _build_role_stage_detail(
        *,
        project_stage: ProjectStage | None,
        role_assignment: ResolvedTaskRoleAssignment,
        role_stage_score: float,
    ) -> str:
        """Build the explainable role-stage alignment detail."""

        if project_stage is None:
            return (
                "任务未挂接项目阶段，阶段加权不生效；仍保留角色派发结果："
                f"{role_assignment.handoff_reason}"
            )

        role_label = _ROLE_LABELS.get(
            role_assignment.owner_role_code,
            role_assignment.owner_role_code.value if role_assignment.owner_role_code else "未分配",
        )
        return (
            f"项目当前处于 {_STAGE_LABELS.get(project_stage, project_stage.value)} 阶段，"
            f"责任角色为 {role_label}，阶段加权为 {role_stage_score:+.1f}。"
        )

    @staticmethod
    def _build_strategy_summary(
        *,
        project_stage: ProjectStage | None,
        role_assignment: ResolvedTaskRoleAssignment,
        model_profile: StrategyModelProfile,
        selected_skill_names: tuple[str, ...],
        budget_snapshot: BudgetSnapshot,
    ) -> str:
        """Build one compact UI-facing strategy summary."""

        stage_text = (
            _STAGE_LABELS.get(project_stage, project_stage.value)
            if project_stage is not None
            else "未挂接项目"
        )
        role_text = _ROLE_LABELS.get(
            role_assignment.owner_role_code,
            role_assignment.owner_role_code.value if role_assignment.owner_role_code else "未分配角色",
        )
        skill_text = ", ".join(selected_skill_names) if selected_skill_names else "无额外 Skill"
        return (
            f"{stage_text} 阶段优先由 {role_text} 承接；预算为 "
            f"{budget_snapshot.pressure_level.value}/{budget_snapshot.suggested_action.value}，"
            f"模型选择 {model_profile.label}（{model_profile.model_name}），"
            f"Skill 使用 {skill_text}。"
        )

    @staticmethod
    def _promote_tier(tier: str) -> str:
        """Promote one model tier by one step."""

        if tier not in _MODEL_TIERS:
            return "balanced"

        current_index = _MODEL_TIERS.index(tier)
        return _MODEL_TIERS[min(current_index + 1, len(_MODEL_TIERS) - 1)]

    @staticmethod
    def _demote_tier(tier: str) -> str:
        """Demote one model tier by one step."""

        if tier not in _MODEL_TIERS:
            return "balanced"

        current_index = _MODEL_TIERS.index(tier)
        return _MODEL_TIERS[max(current_index - 1, 0)]
