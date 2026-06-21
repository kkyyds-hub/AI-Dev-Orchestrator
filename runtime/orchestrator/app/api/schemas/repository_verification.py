"""Repository verification baseline request and response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.repository_verification import (
    RepositoryVerificationBaseline,
    RepositoryVerificationCategory,
    RepositoryVerificationTemplate,
    RepositoryVerificationTemplateReference,
)


class RepositoryVerificationTemplateUpsertRequest(BaseModel):
    """One editable Day09 verification-template row submitted from the UI."""

    id: UUID | None = None
    category: RepositoryVerificationCategory
    name: str = Field(min_length=1, max_length=100)
    command: str = Field(min_length=1, max_length=2_000)
    working_directory: str = Field(default=".", min_length=1, max_length=500)
    timeout_seconds: int = Field(default=600, ge=30, le=7_200)
    enabled_by_default: bool = True
    description: str | None = Field(default=None, max_length=500)

    def to_domain_model(self, *, project_id: UUID) -> RepositoryVerificationTemplate:
        """Convert one request item into the Day09 domain model."""

        payload = dict(
            project_id=project_id,
            category=self.category,
            name=self.name,
            command=self.command,
            working_directory=self.working_directory,
            timeout_seconds=self.timeout_seconds,
            enabled_by_default=self.enabled_by_default,
            description=self.description,
        )
        if self.id is not None:
            payload["id"] = self.id

        return RepositoryVerificationTemplate(**payload)


class RepositoryVerificationBaselineUpsertRequest(BaseModel):
    """Full Day09 verification-baseline payload used by PUT."""

    templates: list[RepositoryVerificationTemplateUpsertRequest] = Field(
        min_length=4,
        max_length=4,
    )


class RepositoryVerificationTemplateReferenceResponse(BaseModel):
    """One reusable Day09 verification-template reference returned by the API."""

    id: UUID
    category: RepositoryVerificationCategory
    name: str
    command: str
    working_directory: str
    timeout_seconds: int
    enabled_by_default: bool
    description: str | None = None

    @classmethod
    def from_reference(
        cls,
        template: RepositoryVerificationTemplateReference,
    ) -> "RepositoryVerificationTemplateReferenceResponse":
        """Convert one template reference into an API DTO."""

        return cls(
            id=template.id,
            category=template.category,
            name=template.name,
            command=template.command,
            working_directory=template.working_directory,
            timeout_seconds=template.timeout_seconds,
            enabled_by_default=template.enabled_by_default,
            description=template.description,
        )


class RepositoryVerificationTemplateResponse(
    RepositoryVerificationTemplateReferenceResponse
):
    """One persisted Day09 verification template returned by repository endpoints."""

    project_id: UUID
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_template(
        cls,
        template: RepositoryVerificationTemplate,
    ) -> "RepositoryVerificationTemplateResponse":
        """Convert one Day09 template into an API DTO."""

        return cls(
            id=template.id,
            project_id=template.project_id,
            category=template.category,
            name=template.name,
            command=template.command,
            working_directory=template.working_directory,
            timeout_seconds=template.timeout_seconds,
            enabled_by_default=template.enabled_by_default,
            description=template.description,
            created_at=template.created_at,
            updated_at=template.updated_at,
        )


class RepositoryVerificationBaselineResponse(BaseModel):
    """One repository verification baseline shown on the Day09 repository page."""

    project_id: UUID
    template_count: int
    configured_categories: list[RepositoryVerificationCategory]
    last_updated_at: datetime | None = None
    templates: list[RepositoryVerificationTemplateResponse]

    @classmethod
    def from_baseline(
        cls,
        baseline: RepositoryVerificationBaseline,
    ) -> "RepositoryVerificationBaselineResponse":
        """Convert one Day09 baseline aggregate into an API DTO."""

        return cls(
            project_id=baseline.project_id,
            template_count=baseline.template_count,
            configured_categories=list(baseline.configured_categories),
            last_updated_at=baseline.last_updated_at,
            templates=[
                RepositoryVerificationTemplateResponse.from_template(template)
                for template in baseline.templates
            ],
        )
