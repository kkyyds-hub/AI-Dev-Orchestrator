"""Skill registry and role-binding endpoints for V3 Day13."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain.project_role import ProjectRoleCode
from app.domain.skill import (
    ProjectRoleBoundSkill,
    ProjectRoleSkillBindingGroup,
    ProjectSkillBindingSnapshot,
    SkillBindingSource,
    SkillDefinition,
    SkillRegistrySnapshot,
    SkillVersionRecord,
)
from app.repositories.project_repository import ProjectRepository
from app.repositories.project_role_repository import ProjectRoleRepository
from app.repositories.skill_repository import SkillRepository
from app.services.role_catalog_service import RoleCatalogService
from app.services.skill_registry_service import SkillRegistryService


class SkillVersionResponse(BaseModel):
    """One Skill version snapshot returned by the registry API."""

    id: UUID
    skill_id: UUID
    version: str
    name: str
    summary: str
    purpose: str
    applicable_role_codes: list[ProjectRoleCode]
    enabled: bool
    change_note: str | None = None
    created_at: datetime

    @classmethod
    def from_record(cls, record: SkillVersionRecord) -> "SkillVersionResponse":
        return cls(
            id=record.id,
            skill_id=record.skill_id,
            version=record.version,
            name=record.name,
            summary=record.summary,
            purpose=record.purpose,
            applicable_role_codes=list(record.applicable_role_codes),
            enabled=record.enabled,
            change_note=record.change_note,
            created_at=record.created_at,
        )


class SkillResponse(BaseModel):
    """One Skill returned by the Day13 registry endpoints."""

    id: UUID
    code: str
    name: str
    summary: str
    purpose: str
    applicable_role_codes: list[ProjectRoleCode]
    enabled: bool
    current_version: str
    created_at: datetime
    updated_at: datetime
    version_history: list[SkillVersionResponse]

    @classmethod
    def from_skill(cls, skill: SkillDefinition) -> "SkillResponse":
        return cls(
            id=skill.id,
            code=skill.code,
            name=skill.name,
            summary=skill.summary,
            purpose=skill.purpose,
            applicable_role_codes=list(skill.applicable_role_codes),
            enabled=skill.enabled,
            current_version=skill.current_version,
            created_at=skill.created_at,
            updated_at=skill.updated_at,
            version_history=[
                SkillVersionResponse.from_record(record)
                for record in skill.version_history
            ],
        )


class SkillRegistryResponse(BaseModel):
    """Skill registry snapshot returned by `GET /skills/registry`."""

    total_skill_count: int
    enabled_skill_count: int
    version_record_count: int
    skills: list[SkillResponse]
    generated_at: datetime

    @classmethod
    def from_snapshot(cls, snapshot: SkillRegistrySnapshot) -> "SkillRegistryResponse":
        return cls(
            total_skill_count=snapshot.total_skill_count,
            enabled_skill_count=snapshot.enabled_skill_count,
            version_record_count=snapshot.version_record_count,
            skills=[SkillResponse.from_skill(skill) for skill in snapshot.skills],
            generated_at=snapshot.generated_at,
        )


class SkillUpsertRequest(BaseModel):
    """Editable payload submitted to the Skill registry."""

    name: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=500)
    purpose: str = Field(min_length=1, max_length=1_000)
    applicable_role_codes: list[ProjectRoleCode] = Field(default_factory=list, max_length=12)
    enabled: bool = True
    version: str = Field(min_length=1, max_length=40)
    change_note: str | None = Field(default=None, max_length=1_000)


class ProjectRoleBoundSkillResponse(BaseModel):
    """One resolved role-binding Skill item returned to the frontend."""

    skill_id: UUID
    skill_code: str
    skill_name: str
    summary: str
    purpose: str
    bound_version: str
    registry_current_version: str | None = None
    registry_enabled: bool
    upgrade_available: bool
    applicable_role_codes: list[ProjectRoleCode]
    binding_source: SkillBindingSource
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_item(
        cls,
        item: ProjectRoleBoundSkill,
    ) -> "ProjectRoleBoundSkillResponse":
        return cls(
            skill_id=item.skill_id,
            skill_code=item.skill_code,
            skill_name=item.skill_name,
            summary=item.summary,
            purpose=item.purpose,
            bound_version=item.bound_version,
            registry_current_version=item.registry_current_version,
            registry_enabled=item.registry_enabled,
            upgrade_available=item.upgrade_available,
            applicable_role_codes=list(item.applicable_role_codes),
            binding_source=item.binding_source,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )


class ProjectRoleSkillBindingGroupResponse(BaseModel):
    """One role group returned by the Day13 binding API."""

    role_code: ProjectRoleCode
    role_name: str
    role_enabled: bool
    default_skill_slots: list[str]
    bound_skill_count: int
    skills: list[ProjectRoleBoundSkillResponse]

    @classmethod
    def from_group(
        cls,
        group: ProjectRoleSkillBindingGroup,
    ) -> "ProjectRoleSkillBindingGroupResponse":
        return cls(
            role_code=group.role_code,
            role_name=group.role_name,
            role_enabled=group.role_enabled,
            default_skill_slots=list(group.default_skill_slots),
            bound_skill_count=group.bound_skill_count,
            skills=[
                ProjectRoleBoundSkillResponse.from_item(skill)
                for skill in group.skills
            ],
        )


class ProjectSkillBindingSnapshotResponse(BaseModel):
    """Project-level role-binding snapshot returned by `GET /skills/projects/...`."""

    project_id: UUID
    project_name: str
    total_roles: int
    enabled_roles: int
    total_bound_skills: int
    outdated_binding_count: int
    roles: list[ProjectRoleSkillBindingGroupResponse]
    generated_at: datetime

    @classmethod
    def from_snapshot(
        cls,
        snapshot: ProjectSkillBindingSnapshot,
    ) -> "ProjectSkillBindingSnapshotResponse":
        return cls(
            project_id=snapshot.project_id,
            project_name=snapshot.project_name,
            total_roles=snapshot.total_roles,
            enabled_roles=snapshot.enabled_roles,
            total_bound_skills=snapshot.total_bound_skills,
            outdated_binding_count=snapshot.outdated_binding_count,
            roles=[
                ProjectRoleSkillBindingGroupResponse.from_group(role)
                for role in snapshot.roles
            ],
            generated_at=snapshot.generated_at,
        )


class ProjectRoleSkillBindingUpdateRequest(BaseModel):
    """Payload used to replace all Skill bindings under one project role."""

    skill_codes: list[str] = Field(default_factory=list, max_length=12)


def get_skill_registry_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> SkillRegistryService:
    """Create the Day13 Skill registry dependency."""

    project_repository = ProjectRepository(session)
    project_role_repository = ProjectRoleRepository(session)
    return SkillRegistryService(
        project_repository=project_repository,
        role_catalog_service=RoleCatalogService(
            project_repository=project_repository,
            project_role_repository=project_role_repository,
        ),
        skill_repository=SkillRepository(session),
    )


router = APIRouter(prefix="/skills", tags=["skills"])


@router.get(
    "/registry",
    response_model=SkillRegistryResponse,
    summary="获取 Skill 注册中心快照",
)
def get_skill_registry(
    skill_registry_service: Annotated[
        SkillRegistryService, Depends(get_skill_registry_service)
    ],
) -> SkillRegistryResponse:
    """Return the current Day13 Skill registry."""

    snapshot = skill_registry_service.list_skill_registry()
    return SkillRegistryResponse.from_snapshot(snapshot)


@router.put(
    "/{skill_code}",
    response_model=SkillResponse,
    summary="创建或更新 Skill 元数据",
)
def upsert_skill(
    skill_code: str,
    request: SkillUpsertRequest,
    skill_registry_service: Annotated[
        SkillRegistryService, Depends(get_skill_registry_service)
    ],
) -> SkillResponse:
    """Create or update one Skill entry inside the registry."""

    try:
        skill = skill_registry_service.upsert_skill(
            code=skill_code,
            name=request.name,
            summary=request.summary,
            purpose=request.purpose,
            applicable_role_codes=request.applicable_role_codes,
            enabled=request.enabled,
            version=request.version,
            change_note=request.change_note,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return SkillResponse.from_skill(skill)


@router.get(
    "/projects/{project_id}/bindings",
    response_model=ProjectSkillBindingSnapshotResponse,
    summary="获取项目角色 Skill 绑定快照",
)
def get_project_skill_bindings(
    project_id: UUID,
    skill_registry_service: Annotated[
        SkillRegistryService, Depends(get_skill_registry_service)
    ],
) -> ProjectSkillBindingSnapshotResponse:
    """Return one project's current role-to-Skill binding snapshot."""

    snapshot = skill_registry_service.get_project_skill_bindings(project_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    return ProjectSkillBindingSnapshotResponse.from_snapshot(snapshot)


@router.put(
    "/projects/{project_id}/bindings/{role_code}",
    response_model=ProjectRoleSkillBindingGroupResponse,
    summary="替换项目某个角色的 Skill 绑定",
)
def replace_project_role_skill_bindings(
    project_id: UUID,
    role_code: ProjectRoleCode,
    request: ProjectRoleSkillBindingUpdateRequest,
    skill_registry_service: Annotated[
        SkillRegistryService, Depends(get_skill_registry_service)
    ],
) -> ProjectRoleSkillBindingGroupResponse:
    """Replace all Skill bindings under one role for the selected project."""

    try:
        role_group = skill_registry_service.replace_project_role_skill_bindings(
            project_id=project_id,
            role_code=role_code,
            skill_codes=request.skill_codes,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if role_group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    return ProjectRoleSkillBindingGroupResponse.from_group(role_group)
