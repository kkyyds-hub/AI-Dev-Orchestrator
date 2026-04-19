"""Day13 team assembly and team control center endpoints."""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.core.db_tables import ProjectTable
from app.domain.project import ProjectStage
from app.domain.project_role import ProjectRoleCode
from app.repositories.project_repository import ProjectRepository
from app.repositories.project_role_repository import ProjectRoleRepository
from app.repositories.run_repository import RunRepository
from app.repositories.skill_repository import SkillRepository
from app.services.budget_guard_service import BudgetGuardService
from app.services.role_catalog_service import RoleCatalogService
from app.services.skill_registry_service import SkillRegistryService
from app.services.strategy_engine_service import StrategyEngineService


ModelTier = Literal["economy", "balanced", "premium"]


class TeamAssemblyMemberDto(BaseModel):
    """One team assembly row configured by the control center."""

    role_code: ProjectRoleCode
    enabled: bool = True
    display_name: str = Field(min_length=1, max_length=100)
    allocation_percent: int = Field(default=100, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=500)


class TeamPolicyDto(BaseModel):
    """Minimal Day13 team policy persisted per project."""

    collaboration_mode: str = Field(default="role-led", min_length=1, max_length=40)
    intervention_mode: str = Field(default="boss-review", min_length=1, max_length=40)
    escalation_enabled: bool = True
    handoff_required: bool = True
    review_gate: str = Field(default="required", min_length=1, max_length=40)


class BudgetPolicyDto(BaseModel):
    """Project-level budget policy contract frozen for Day14 consumption."""

    daily_budget_usd: float = Field(default=100.0, ge=0.0, le=100000.0)
    per_run_budget_usd: float = Field(default=10.0, ge=0.0, le=10000.0)
    hard_stop_enabled: bool = False
    pressure_mode: str = Field(default="balanced", min_length=1, max_length=40)


class RoleModelPreferenceDto(BaseModel):
    """Role -> model tier preference to be written into strategy rules."""

    role_code: ProjectRoleCode
    model_tier: ModelTier


class RoleModelStageOverrideDto(BaseModel):
    """Stage+role -> model tier override to be written into strategy rules."""

    stage: ProjectStage
    role_code: ProjectRoleCode
    model_tier: ModelTier


class RoleModelPolicyDto(BaseModel):
    """Role model policy surface persisted through `/strategy/rules`."""

    role_preferences: list[RoleModelPreferenceDto] = Field(default_factory=list)
    stage_overrides: list[RoleModelStageOverrideDto] = Field(default_factory=list)


class TeamControlCenterRequest(BaseModel):
    """Payload submitted by Day13 team control center."""

    team_name: str = Field(min_length=1, max_length=120)
    team_mission: str = Field(min_length=1, max_length=1000)
    assembly: list[TeamAssemblyMemberDto] = Field(default_factory=list, max_length=20)
    team_policy: TeamPolicyDto
    budget_policy: BudgetPolicyDto
    role_model_policy: RoleModelPolicyDto = Field(default_factory=RoleModelPolicyDto)


class Day14PrerequisitesDto(BaseModel):
    """Fields that Day14 can consume directly for cost/dashboard aggregation."""

    team_size: int
    enabled_role_codes: list[ProjectRoleCode] = Field(default_factory=list)
    budget_policy_keys: list[str] = Field(default_factory=list)
    role_preference_count: int = 0
    stage_override_count: int = 0


class RuntimeConsumptionBoundaryDto(BaseModel):
    """Explicit runtime-consumption boundary for Day13 policy contracts."""

    role_model_policy_paths: list[str] = Field(default_factory=list)
    budget_policy_paths: list[str] = Field(default_factory=list)
    note: str


class TeamControlCenterResponse(BaseModel):
    """Snapshot returned by GET/PUT team control center endpoints."""

    project_id: UUID
    team_name: str
    team_mission: str
    assembly: list[TeamAssemblyMemberDto] = Field(default_factory=list)
    team_policy: TeamPolicyDto
    budget_policy: BudgetPolicyDto
    role_model_policy: RoleModelPolicyDto
    day14_prerequisites: Day14PrerequisitesDto
    runtime_consumption_boundary: RuntimeConsumptionBoundaryDto


def _parse_json_field(raw_value: str, *, fallback: Any) -> Any:
    """Parse one JSON field from SQLite with a safe fallback."""

    try:
        return json.loads(raw_value)
    except (TypeError, ValueError):
        return fallback


def _build_role_model_policy_dto(rules_payload: dict[str, Any]) -> RoleModelPolicyDto:
    """Extract the Day13 role model policy surface from strategy rules."""

    raw_role_preferences = rules_payload.get("role_model_tier_preferences")
    raw_stage_overrides = rules_payload.get("stage_model_tier_overrides")
    role_preferences_map = (
        raw_role_preferences if isinstance(raw_role_preferences, dict) else {}
    )
    stage_overrides_map = (
        raw_stage_overrides if isinstance(raw_stage_overrides, dict) else {}
    )

    role_preferences: list[RoleModelPreferenceDto] = []
    for role_code, tier in sorted(role_preferences_map.items()):
        if not isinstance(role_code, str) or not isinstance(tier, str):
            continue
        try:
            role_preferences.append(
                RoleModelPreferenceDto(
                    role_code=ProjectRoleCode(role_code),
                    model_tier=tier,  # type: ignore[arg-type]
                )
            )
        except ValueError:
            continue

    stage_overrides: list[RoleModelStageOverrideDto] = []
    for stage, role_map in sorted(stage_overrides_map.items()):
        if not isinstance(stage, str) or not isinstance(role_map, dict):
            continue
        for role_code, tier in sorted(role_map.items()):
            if not isinstance(role_code, str) or not isinstance(tier, str):
                continue
            try:
                stage_overrides.append(
                    RoleModelStageOverrideDto(
                        stage=ProjectStage(stage),
                        role_code=ProjectRoleCode(role_code),
                        model_tier=tier,  # type: ignore[arg-type]
                    )
                )
            except ValueError:
                continue

    return RoleModelPolicyDto(
        role_preferences=role_preferences,
        stage_overrides=stage_overrides,
    )


def _build_runtime_boundary() -> RuntimeConsumptionBoundaryDto:
    """Return a stable runtime boundary summary for Day13 contracts."""

    return RuntimeConsumptionBoundaryDto(
        role_model_policy_paths=[
            "GET /strategy/projects/{project_id}/preview",
            "POST /workers/run-once?project_id={project_id}",
        ],
        budget_policy_paths=[
            "POST /workers/run-once?project_id={project_id}",
            "GET /console/budget-health",
        ],
        note=(
            "Role model policy is consumed directly by strategy engine and worker routing. "
            "Budget policy is frozen as Day13 project-level contract and currently forms Day14 aggregation inputs; "
            "hard enforcement stays in existing budget guard paths."
        ),
    )


def _build_response(
    *,
    project_row: ProjectTable,
    strategy_rules: dict[str, Any],
) -> TeamControlCenterResponse:
    """Build one API snapshot from persisted project and strategy-rule state."""

    raw_assembly = _parse_json_field(project_row.team_assembly_json, fallback=[])
    raw_team_policy = _parse_json_field(project_row.team_policy_json, fallback={})
    raw_budget_policy = _parse_json_field(project_row.budget_policy_json, fallback={})

    assembly = [
        TeamAssemblyMemberDto.model_validate(item)
        for item in (raw_assembly if isinstance(raw_assembly, list) else [])
        if isinstance(item, dict)
    ]
    team_policy = TeamPolicyDto.model_validate(
        raw_team_policy if isinstance(raw_team_policy, dict) else {}
    )
    budget_policy = BudgetPolicyDto.model_validate(
        raw_budget_policy if isinstance(raw_budget_policy, dict) else {}
    )
    role_model_policy = _build_role_model_policy_dto(strategy_rules)

    enabled_role_codes = [member.role_code for member in assembly if member.enabled]
    return TeamControlCenterResponse(
        project_id=project_row.id,
        team_name=project_row.name,
        team_mission=project_row.summary,
        assembly=assembly,
        team_policy=team_policy,
        budget_policy=budget_policy,
        role_model_policy=role_model_policy,
        day14_prerequisites=Day14PrerequisitesDto(
            team_size=len(assembly),
            enabled_role_codes=enabled_role_codes,
            budget_policy_keys=sorted(raw_budget_policy.keys())
            if isinstance(raw_budget_policy, dict)
            else [],
            role_preference_count=len(role_model_policy.role_preferences),
            stage_override_count=len(role_model_policy.stage_overrides),
        ),
        runtime_consumption_boundary=_build_runtime_boundary(),
    )


def get_strategy_engine_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> StrategyEngineService:
    """Build the strategy engine dependency used by Day13 contract endpoints."""

    project_repository = ProjectRepository(session)
    role_catalog_service = RoleCatalogService(
        project_repository=project_repository,
        project_role_repository=ProjectRoleRepository(session),
    )
    skill_registry_service = SkillRegistryService(
        project_repository=project_repository,
        role_catalog_service=role_catalog_service,
        skill_repository=SkillRepository(session),
    )
    return StrategyEngineService(
        project_repository=project_repository,
        role_catalog_service=role_catalog_service,
        skill_registry_service=skill_registry_service,
        budget_guard_service=BudgetGuardService(run_repository=RunRepository(session)),
    )


router = APIRouter(prefix="/projects", tags=["projects"])


@router.get(
    "/{project_id}/team-control-center",
    response_model=TeamControlCenterResponse,
    summary="Get Day13 team assembly/team policy snapshot",
)
def get_team_control_center_snapshot(
    project_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    strategy_engine_service: Annotated[
        StrategyEngineService,
        Depends(get_strategy_engine_service),
    ],
) -> TeamControlCenterResponse:
    """Return one project's Day13 team assembly and team control center contract."""

    project_row = session.get(ProjectTable, project_id)
    if project_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    strategy_snapshot = strategy_engine_service.get_rule_set_snapshot()
    return _build_response(
        project_row=project_row,
        strategy_rules=strategy_snapshot.rules,
    )


@router.put(
    "/{project_id}/team-control-center",
    response_model=TeamControlCenterResponse,
    summary="Save Day13 team assembly/team policy snapshot",
)
def save_team_control_center_snapshot(
    project_id: UUID,
    request: TeamControlCenterRequest,
    session: Annotated[Session, Depends(get_db_session)],
    strategy_engine_service: Annotated[
        StrategyEngineService,
        Depends(get_strategy_engine_service),
    ],
) -> TeamControlCenterResponse:
    """Persist Day13 team policy and role model policy, then return the latest snapshot."""

    project_row = session.get(ProjectTable, project_id)
    if project_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    project_row.team_assembly_json = json.dumps(
        [member.model_dump(mode="json") for member in request.assembly],
        ensure_ascii=False,
    )
    project_row.team_policy_json = json.dumps(
        request.team_policy.model_dump(mode="json"),
        ensure_ascii=False,
    )
    project_row.budget_policy_json = json.dumps(
        request.budget_policy.model_dump(mode="json"),
        ensure_ascii=False,
    )
    session.commit()
    session.refresh(project_row)

    strategy_snapshot = strategy_engine_service.get_rule_set_snapshot()
    rules_payload = dict(strategy_snapshot.rules)
    rules_payload["role_model_tier_preferences"] = {
        item.role_code.value: item.model_tier
        for item in request.role_model_policy.role_preferences
    }
    stage_overrides_map: dict[str, dict[str, str]] = {}
    for item in request.role_model_policy.stage_overrides:
        stage_overrides_map.setdefault(item.stage.value, {})[item.role_code.value] = (
            item.model_tier
        )
    rules_payload["stage_model_tier_overrides"] = stage_overrides_map

    try:
        updated_strategy_snapshot = strategy_engine_service.update_rule_set(
            rules_payload=rules_payload,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return _build_response(
        project_row=project_row,
        strategy_rules=updated_strategy_snapshot.rules,
    )
