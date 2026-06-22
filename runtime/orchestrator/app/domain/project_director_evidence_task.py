"""P10-B evidence-grounded Project Director task draft models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.domain._base import DomainModel


class ProjectDirectorEvidenceTask(DomainModel):
    """A draft task grounded in a P10-A evidence pack.

    This is not a queued product task and does not authorize execution.
    """

    source_evidence_pack_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    objective: str = Field(min_length=1, max_length=1000)
    evidence_refs: list[str] = Field(default_factory=list)
    allowed_files: list[str] = Field(default_factory=list)
    forbidden_files: list[str] = Field(default_factory=list)
    required_reading: list[str] = Field(default_factory=list)
    targeted_tests: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    user_confirmation_required: bool = True
    product_runtime_git_write_allowed: bool = False


class ProjectDirectorEvidenceTaskCompositionResult(DomainModel):
    """P10-B task composition result."""

    source_evidence_pack_id: str = Field(min_length=1, max_length=160)
    composition_status: Literal["composed", "blocked"] = "blocked"
    composed_tasks: list[ProjectDirectorEvidenceTask] = Field(default_factory=list)
    allowed_files: list[str] = Field(default_factory=list)
    forbidden_files: list[str] = Field(default_factory=list)
    required_reading: list[str] = Field(default_factory=list)
    targeted_tests: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    user_confirmation_required: bool = True
    product_runtime_git_write_allowed: bool = False
