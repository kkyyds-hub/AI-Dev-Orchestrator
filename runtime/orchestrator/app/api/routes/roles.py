"""Role catalog endpoints for V3 Day05."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain.project_role import (
    ProjectRoleCatalog,
    ProjectRoleCode,
    ProjectRoleConfig,
    RoleCatalogEntry,
)
from app.repositories.project_repository import ProjectRepository
from app.repositories.project_role_repository import ProjectRoleRepository
from app.services.role_catalog_service import RoleCatalogService


class RoleCatalogItemResponse(BaseModel):
    """One built-in role entry returned by `GET /roles/catalog`."""

    code: ProjectRoleCode
    name: str
    summary: str
    responsibilities: list[str]
    input_boundary: list[str]
    output_boundary: list[str]
    default_skill_slots: list[str]
    enabled_by_default: bool
    sort_order: int

    @classmethod
    def from_entry(cls, entry: RoleCatalogEntry) -> "RoleCatalogItemResponse":
        """Convert one built-in role entry into an API DTO."""

        return cls(
            code=entry.code,
            name=entry.name,
            summary=entry.summary,
            responsibilities=entry.responsibilities,
            input_boundary=entry.input_boundary,
            output_boundary=entry.output_boundary,
            default_skill_slots=entry.default_skill_slots,
            enabled_by_default=entry.enabled_by_default,
            sort_order=entry.sort_order,
        )


class ProjectRoleConfigResponse(BaseModel):
    """One persisted role config returned by project role endpoints."""

    id: UUID
    project_id: UUID
    role_code: ProjectRoleCode
    enabled: bool
    name: str
    summary: str
    responsibilities: list[str]
    input_boundary: list[str]
    output_boundary: list[str]
    default_skill_slots: list[str]
    custom_notes: str | None = None
    sort_order: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_role_config(
        cls,
        role_config: ProjectRoleConfig,
    ) -> "ProjectRoleConfigResponse":
        """Convert one domain role config into an API DTO."""

        return cls(
            id=role_config.id,
            project_id=role_config.project_id,
            role_code=role_config.role_code,
            enabled=role_config.enabled,
            name=role_config.name,
            summary=role_config.summary,
            responsibilities=role_config.responsibilities,
            input_boundary=role_config.input_boundary,
            output_boundary=role_config.output_boundary,
            default_skill_slots=role_config.default_skill_slots,
            custom_notes=role_config.custom_notes,
            sort_order=role_config.sort_order,
            created_at=role_config.created_at,
            updated_at=role_config.updated_at,
        )


class ProjectRoleCatalogResponse(BaseModel):
    """Counted role-catalog snapshot returned for one project."""

    project_id: UUID
    available_role_count: int
    enabled_role_count: int
    roles: list[ProjectRoleConfigResponse]

    @classmethod
    def from_catalog(
        cls,
        catalog: ProjectRoleCatalog,
    ) -> "ProjectRoleCatalogResponse":
        """Convert one service-side project catalog into an API DTO."""

        return cls(
            project_id=catalog.project_id,
            available_role_count=catalog.available_role_count,
            enabled_role_count=catalog.enabled_role_count,
            roles=[
                ProjectRoleConfigResponse.from_role_config(role)
                for role in catalog.roles
            ],
        )


class ProjectRoleUpdateRequest(BaseModel):
    """Editable project-role payload submitted by the Day05 UI."""

    enabled: bool = True
    name: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=500)
    responsibilities: list[str] = Field(default_factory=list, max_length=12)
    input_boundary: list[str] = Field(default_factory=list, max_length=12)
    output_boundary: list[str] = Field(default_factory=list, max_length=12)
    default_skill_slots: list[str] = Field(default_factory=list, max_length=12)
    custom_notes: str | None = Field(default=None, max_length=1_000)
    sort_order: int = Field(default=0, ge=0)


def get_role_catalog_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> RoleCatalogService:
    """Create the Day05 role-catalog service dependency."""

    return RoleCatalogService(
        project_repository=ProjectRepository(session),
        project_role_repository=ProjectRoleRepository(session),
    )


router = APIRouter(prefix="/roles", tags=["roles"])


@router.get(
    "/catalog",
    response_model=list[RoleCatalogItemResponse],
    summary="获取系统内置角色目录",
)
def list_role_catalog(
    role_catalog_service: Annotated[
        RoleCatalogService, Depends(get_role_catalog_service)
    ],
) -> list[RoleCatalogItemResponse]:
    """Return the built-in Day05 role catalog."""

    entries = role_catalog_service.list_system_role_catalog()
    return [RoleCatalogItemResponse.from_entry(entry) for entry in entries]


@router.get(
    "/projects/{project_id}",
    response_model=ProjectRoleCatalogResponse,
    summary="获取项目角色配置目录",
)
def get_project_role_catalog(
    project_id: UUID,
    role_catalog_service: Annotated[
        RoleCatalogService, Depends(get_role_catalog_service)
    ],
) -> ProjectRoleCatalogResponse:
    """Return one project's role config snapshot."""

    catalog = role_catalog_service.get_project_role_catalog(project_id)
    if catalog is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    return ProjectRoleCatalogResponse.from_catalog(catalog)


@router.put(
    "/projects/{project_id}/{role_code}",
    response_model=ProjectRoleConfigResponse,
    summary="更新项目角色配置",
)
def update_project_role_config(
    project_id: UUID,
    role_code: ProjectRoleCode,
    request: ProjectRoleUpdateRequest,
    role_catalog_service: Annotated[
        RoleCatalogService, Depends(get_role_catalog_service)
    ],
) -> ProjectRoleConfigResponse:
    """Update one project's editable role configuration."""

    try:
        updated_role = role_catalog_service.update_project_role_config(
            project_id=project_id,
            role_code=role_code,
            enabled=request.enabled,
            name=request.name,
            summary=request.summary,
            responsibilities=request.responsibilities,
            input_boundary=request.input_boundary,
            output_boundary=request.output_boundary,
            default_skill_slots=request.default_skill_slots,
            custom_notes=request.custom_notes,
            sort_order=request.sort_order,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if updated_role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    return ProjectRoleConfigResponse.from_role_config(updated_role)
