"""P6-B agent dispatch decision pure domain model.

This module is deliberately side-effect free. It does not build decisions from
P5 recovery decisions, call Worker/API code, write AgentMessage records, mutate
database tables, dispatch agents, create tasks, trigger retries, expose API
schemas, or perform git add/commit/push/PR/merge/delete branch/reset/checkout/
switch/stash/rebase/tag operations. It only defines the structured dispatch
decision contract for later P6 stages to consume.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now
from app.domain.failure_recovery_decision import InstructionKind


P6_AGENT_DISPATCH_DECISION_SOURCE = "agent_dispatch_decision"
P6_AGENT_DISPATCH_DECISION_VERSION = "p6_b.r3"
P6_AGENT_DISPATCH_DECISION_AUDIT_EVENT_TYPE = "agent_dispatch_decision"

P6B_FORBIDDEN_TRUE_SAFETY_FLAGS: tuple[str, ...] = (
    "runs_git",
    "runs_write_git",
    "git_add_triggered",
    "git_commit_triggered",
    "git_push_triggered",
    "pr_opened",
    "merge_triggered",
    "branch_deleted",
    "git_reset_triggered",
    "git_checkout_triggered",
    "git_switch_triggered",
    "git_stash_triggered",
    "git_rebase_triggered",
    "git_tag_triggered",
    "ci_triggered",
    "execution_enabled",
    "worker_dispatch_triggered",
    "api_response_exposed",
    "agent_message_written",
    "task_created",
    "retry_triggered",
    "auto_dispatch_triggered",
)


class DispatchAgent(StrEnum):
    """Agent recommended for the next human-reviewed dispatch step."""

    CODEX = "codex"
    DEEPSEEK = "deepseek"
    USER = "user"
    BLOCKED = "blocked"


class DispatchStatus(StrEnum):
    """Read-only dispatch recommendation status."""

    SUGGESTED = "suggested"
    NEEDS_USER_DECISION = "needs_user_decision"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class AgentDispatchDecisionSafetyFlags(DomainModel):
    """P6 dispatch safety flags.

    All flags default to false. P6-B pure domain code rejects runtime side
    effects, Git writes, API exposure, AgentMessage writes, worker dispatch,
    task creation, retry, and auto dispatch markers.
    """

    runs_git: bool = False
    runs_write_git: bool = False
    git_add_triggered: bool = False
    git_commit_triggered: bool = False
    git_push_triggered: bool = False
    pr_opened: bool = False
    merge_triggered: bool = False
    branch_deleted: bool = False
    git_reset_triggered: bool = False
    git_checkout_triggered: bool = False
    git_switch_triggered: bool = False
    git_stash_triggered: bool = False
    git_rebase_triggered: bool = False
    git_tag_triggered: bool = False
    ci_triggered: bool = False
    execution_enabled: bool = False
    worker_dispatch_triggered: bool = False
    api_response_exposed: bool = False
    agent_message_written: bool = False
    task_created: bool = False
    retry_triggered: bool = False
    auto_dispatch_triggered: bool = False

    @model_validator(mode="after")
    def validate_p6b_no_runtime_side_effects(
        self,
    ) -> "AgentDispatchDecisionSafetyFlags":
        enabled_forbidden_flags = [
            flag_name
            for flag_name in P6B_FORBIDDEN_TRUE_SAFETY_FLAGS
            if bool(getattr(self, flag_name))
        ]
        if enabled_forbidden_flags:
            raise ValueError(
                "P6-B agent dispatch decision must not execute Git, trigger CI, "
                "expose API responses, write AgentMessage rows, dispatch workers, "
                "create tasks, retry, or auto-dispatch agents: "
                + ", ".join(enabled_forbidden_flags)
            )
        return self


class AgentDispatchDecision(DomainModel):
    """Structured P6 dispatch recommendation contract.

    The decision is a read-only recommendation. It is not a command, does not
    launch an agent, and does not authorize Git writes or retry execution.
    """

    source: str = Field(
        default=P6_AGENT_DISPATCH_DECISION_SOURCE,
        min_length=1,
        max_length=100,
    )
    version: str = Field(
        default=P6_AGENT_DISPATCH_DECISION_VERSION,
        min_length=1,
        max_length=40,
    )
    dispatch_decision_id: str = Field(
        default_factory=lambda: str(uuid4()),
        min_length=1,
        max_length=120,
    )
    source_failure_recovery_decision_id: str | None = Field(
        default=None,
        max_length=120,
    )
    source_run_id: UUID | None = None
    source_task_id: UUID | None = None
    recommended_agent: DispatchAgent
    dispatch_status: DispatchStatus
    dispatch_reason_code: str = Field(min_length=1, max_length=120)
    dispatch_reason_cn: str = Field(min_length=1, max_length=500)
    instruction_kind: InstructionKind
    instruction_draft: str | None = Field(default=None, max_length=2_000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=50)
    audit_event_type: str = Field(
        default=P6_AGENT_DISPATCH_DECISION_AUDIT_EVENT_TYPE,
        min_length=1,
        max_length=100,
    )
    safety_flags: AgentDispatchDecisionSafetyFlags = Field(
        default_factory=AgentDispatchDecisionSafetyFlags
    )
    created_at: datetime = Field(default_factory=utc_now)
    created_by: str = Field(default="system", min_length=1, max_length=120)
    api_response_exposed: bool = False

    @field_validator(
        "source",
        "version",
        "dispatch_decision_id",
        "source_failure_recovery_decision_id",
        "dispatch_reason_code",
        "dispatch_reason_cn",
        "instruction_draft",
        "audit_event_type",
        "created_by",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        """Trim text fields and collapse blank optional text into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None

    @field_validator("evidence_refs")
    @classmethod
    def normalize_evidence_refs(cls, values: list[str]) -> list[str]:
        """Trim and deduplicate evidence refs while preserving order."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()
        for value in values:
            normalized_value = value.strip()
            if not normalized_value or normalized_value in seen_items:
                continue
            normalized_items.append(normalized_value)
            seen_items.add(normalized_value)
        return normalized_items

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        """Ensure created_at is timezone-aware UTC."""

        normalized_value = ensure_utc_datetime(value)
        if normalized_value is None:
            raise ValueError("created_at is required")
        return normalized_value

    @model_validator(mode="after")
    def validate_contract(self) -> "AgentDispatchDecision":
        """Validate P6-B pure dispatch decision invariants."""

        required_text_fields = {
            "source": self.source,
            "version": self.version,
            "dispatch_decision_id": self.dispatch_decision_id,
            "dispatch_reason_code": self.dispatch_reason_code,
            "dispatch_reason_cn": self.dispatch_reason_cn,
            "audit_event_type": self.audit_event_type,
            "created_by": self.created_by,
        }
        blank_required_fields = [
            field_name
            for field_name, field_value in required_text_fields.items()
            if field_value is None
        ]
        if blank_required_fields:
            raise ValueError(
                "required text fields must not be blank: "
                + ", ".join(blank_required_fields)
            )
        if self.source != P6_AGENT_DISPATCH_DECISION_SOURCE:
            raise ValueError(
                f"source must be {P6_AGENT_DISPATCH_DECISION_SOURCE!r}"
            )
        if self.version != P6_AGENT_DISPATCH_DECISION_VERSION:
            raise ValueError(
                f"version must be {P6_AGENT_DISPATCH_DECISION_VERSION!r}"
            )
        if self.audit_event_type != P6_AGENT_DISPATCH_DECISION_AUDIT_EVENT_TYPE:
            raise ValueError(
                "audit_event_type must be "
                f"{P6_AGENT_DISPATCH_DECISION_AUDIT_EVENT_TYPE!r}"
            )
        if not _contains_cjk(self.dispatch_reason_cn):
            raise ValueError("dispatch_reason_cn must contain Chinese text")
        if self.instruction_draft is not None and not _contains_cjk(
            self.instruction_draft
        ):
            raise ValueError("instruction_draft must contain Chinese text")
        if self.api_response_exposed != self.safety_flags.api_response_exposed:
            raise ValueError(
                "api_response_exposed must match safety_flags.api_response_exposed"
            )
        self._validate_status_agent_contract()
        return self

    def _validate_status_agent_contract(self) -> None:
        if self.dispatch_status == DispatchStatus.SUGGESTED:
            if self.recommended_agent not in {DispatchAgent.CODEX, DispatchAgent.DEEPSEEK}:
                raise ValueError("suggested decisions must recommend codex or deepseek")
            if self.instruction_draft is None:
                raise ValueError("suggested decisions require instruction_draft")
            return

        if self.dispatch_status == DispatchStatus.NEEDS_USER_DECISION:
            if self.recommended_agent != DispatchAgent.USER:
                raise ValueError("needs_user_decision decisions must recommend user")
            if self.instruction_kind != InstructionKind.HUMAN_QUESTION:
                raise ValueError(
                    "needs_user_decision decisions must use human_question instruction"
                )
            if self.instruction_draft is not None:
                raise ValueError(
                    "needs_user_decision decisions must not include executable drafts"
                )
            return

        if self.dispatch_status == DispatchStatus.BLOCKED:
            if self.recommended_agent != DispatchAgent.BLOCKED:
                raise ValueError("blocked decisions must recommend blocked")
            if self.instruction_draft is not None:
                raise ValueError("blocked decisions must not include executable drafts")
            return

        if self.dispatch_status == DispatchStatus.NOT_APPLICABLE:
            if self.recommended_agent != DispatchAgent.BLOCKED:
                raise ValueError("not_applicable decisions must recommend blocked")
            if self.instruction_draft is not None:
                raise ValueError(
                    "not_applicable decisions must not include executable drafts"
                )


def _contains_cjk(value: str) -> bool:
    return any(
        "\u4e00" <= char <= "\u9fff"
        or "\u3400" <= char <= "\u4dbf"
        or "\uf900" <= char <= "\ufaff"
        for char in value
    )
