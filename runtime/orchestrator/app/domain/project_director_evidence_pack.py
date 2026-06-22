"""P10-A readonly repository evidence pack for AI Project Director."""

from __future__ import annotations

from pydantic import Field

from app.domain._base import DomainModel


class ProjectDirectorEvidenceRef(DomainModel):
    """One repository fact used by the evidence pack."""

    ref_id: str = Field(min_length=1, max_length=120)
    relative_path: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=500)
    matched_terms: list[str] = Field(default_factory=list)


class ProjectDirectorRepoEvidencePack(DomainModel):
    """Readonly P10-A evidence pack.

    This object is evidence only. It does not authorize execution, task
    creation, worker dispatch, repository writes, or product runtime Git writes.
    """

    origin_main_commit: str = Field(min_length=7, max_length=64)
    evidence_pack_id: str = Field(min_length=1, max_length=160)
    repo_root: str = Field(min_length=1, max_length=1000)
    related_files: list[str] = Field(default_factory=list)
    impact_paths: list[str] = Field(default_factory=list)
    forbidden_paths: list[str] = Field(default_factory=list)
    suggested_tests: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    evidence_refs: list[ProjectDirectorEvidenceRef] = Field(default_factory=list)
    source_detail: dict[str, object] = Field(default_factory=dict)
    product_runtime_git_write_allowed: bool = False
    frontend_required: bool = False
