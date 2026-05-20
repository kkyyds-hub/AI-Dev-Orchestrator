"""AI Project Director Task Creation Record domain model.

BCG-04A Phase1: records the mapping from a confirmed plan version
to the real tasks created in the queue.

Non-invasive: does NOT modify the Task domain model.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import Field

from app.domain._base import DomainModel


class ProjectDirectorTaskCreationRecord(DomainModel):
    """Immutable record of one plan-version → task-creation batch.

    Exactly one record per plan version.
    Used for: idempotency guard, traceability, GET query.
    """

    id: UUID = Field(default_factory=uuid4)
    plan_version_id: UUID
    session_id: UUID
    project_id: UUID
    version_no: int = Field(ge=1)
    source_type: str = Field(default="project_director_plan_version")
    task_ids: list[UUID] = Field(default_factory=list)
    task_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now())
