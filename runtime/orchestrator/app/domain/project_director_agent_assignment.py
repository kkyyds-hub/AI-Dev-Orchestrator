"""P10-C Project Director programmer/reviewer assignment models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.domain._base import DomainModel


class ProjectDirectorAssignedAgent(DomainModel):
    """One role assignment for a P10 dry-run chain."""

    role: Literal["programmer", "reviewer"]
    agent_kind: str = Field(min_length=1, max_length=80)
    executor_backed: bool
    readonly: bool
    write_authorized: bool = False
    assignment_mode: str = Field(default="dry_run_binding", max_length=120)
    responsibilities: list[str] = Field(default_factory=list)


class ProjectDirectorAgentAssignment(DomainModel):
    """P10-C agent binding result.

    Assignment is a dry-run scheduling decision. It does not start a native
    executor and does not grant product runtime Git write capability.
    """

    assignment_id: str = Field(min_length=1, max_length=160)
    assignment_status: Literal["assigned", "blocked"] = "blocked"
    source_evidence_pack_id: str = Field(min_length=1, max_length=160)
    source_task_ids: list[str] = Field(default_factory=list)
    director_role: str = Field(default="planner_reviewer_dispatcher", max_length=120)
    programmer_agent: ProjectDirectorAssignedAgent | None = None
    reviewer_agent: ProjectDirectorAssignedAgent | None = None
    programmer_executor_backed: bool = False
    reviewer_executor_backed: bool = False
    readonly_review_required: bool = True
    director_permanent_executor: bool = False
    reviewer_readonly: bool = True
    product_runtime_git_write_allowed: bool = False
    frontend_required: bool = False
    native_executor_started: bool = False
    codex_started: bool = False
    claude_code_started: bool = False
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
