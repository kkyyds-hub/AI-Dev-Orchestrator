"""Run domain model definitions."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now
from app.domain.project import ProjectStage
from app.domain.project_role import ProjectRoleCode


class RunStatus(StrEnum):
    """Status of a single execution attempt."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunFailureCategory(StrEnum):
    """Structured failure categories exposed by the Day 14 quality gate."""

    EXECUTION_FAILED = "execution_failed"
    VERIFICATION_FAILED = "verification_failed"
    VERIFICATION_CONFIGURATION_FAILED = "verification_configuration_failed"
    DAILY_BUDGET_EXCEEDED = "daily_budget_exceeded"
    SESSION_BUDGET_EXCEEDED = "session_budget_exceeded"
    RETRY_LIMIT_EXCEEDED = "retry_limit_exceeded"


class RunBudgetPressureLevel(StrEnum):
    """Normalized budget-pressure level used by V2-B routing and guard decisions."""

    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    BLOCKED = "blocked"


class RunBudgetStrategyAction(StrEnum):
    """Suggested action exposed by the V2-B budget strategy."""

    FULL_SPEED = "full_speed"
    CONSERVATIVE = "conservative"
    DEGRADED = "degraded"
    BLOCK = "block"


class RunEventReason(StrEnum):
    """Stable run event reasons published to the console stream."""

    CREATED = "created"
    LOG_PATH_SET = "log_path_set"
    FINISHED = "finished"


class RunRoutingScoreItem(DomainModel):
    """One normalized routing-score contribution item."""

    code: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=100)
    score: float
    detail: str = Field(min_length=1, max_length=500)


class RunStrategyReasonItem(DomainModel):
    """One explainable reason emitted by the Day 15 strategy engine."""

    code: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=100)
    detail: str = Field(min_length=1, max_length=1_000)
    score: float | None = None


class RunStrategyDecision(DomainModel):
    """Persisted Day 15 strategy snapshot attached to one run."""

    version: str = Field(default="day15.v1", min_length=1, max_length=40)
    project_stage: ProjectStage | None = None
    owner_role_code: ProjectRoleCode | None = None
    model_tier: str | None = Field(default=None, max_length=40)
    model_name: str | None = Field(default=None, max_length=100)
    selected_skill_codes: list[str] = Field(default_factory=list, max_length=12)
    selected_skill_names: list[str] = Field(default_factory=list, max_length=12)
    budget_pressure_level: RunBudgetPressureLevel
    budget_action: RunBudgetStrategyAction
    strategy_code: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=2_000)
    role_model_policy_source: str | None = Field(default=None, max_length=40)
    role_model_policy_desired_tier: str | None = Field(default=None, max_length=40)
    role_model_policy_adjusted_tier: str | None = Field(default=None, max_length=40)
    role_model_policy_final_tier: str | None = Field(default=None, max_length=40)
    role_model_policy_stage_override_applied: bool = False
    rule_codes: list[str] = Field(default_factory=list, max_length=20)
    reasons: list[RunStrategyReasonItem] = Field(default_factory=list, max_length=20)

    @field_validator("selected_skill_codes", "selected_skill_names", "rule_codes")
    @classmethod
    def normalize_string_lists(cls, value: list[str]) -> list[str]:
        """Trim and deduplicate string list fields while preserving order."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for item in value:
            normalized_item = item.strip()
            if not normalized_item or normalized_item in seen_items:
                continue

            normalized_items.append(normalized_item)
            seen_items.add(normalized_item)

        return normalized_items


class Run(DomainModel):
    """Minimal persisted execution record."""

    id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    status: RunStatus = Field(default=RunStatus.QUEUED)
    model_name: str | None = Field(default=None, max_length=100)
    route_reason: str | None = Field(default=None, max_length=2_000)
    routing_score: float | None = Field(default=None)
    routing_score_breakdown: list[RunRoutingScoreItem] = Field(default_factory=list)
    strategy_decision: RunStrategyDecision | None = None
    owner_role_code: ProjectRoleCode | None = None
    upstream_role_code: ProjectRoleCode | None = None
    downstream_role_code: ProjectRoleCode | None = None
    handoff_reason: str | None = Field(default=None, max_length=1_000)
    dispatch_status: str | None = Field(default=None, max_length=100)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result_summary: str | None = Field(default=None, max_length=2_000)
    provider_key: str | None = Field(default=None, max_length=50)
    prompt_template_key: str | None = Field(default=None, max_length=100)
    prompt_template_version: str | None = Field(default=None, max_length=40)
    prompt_char_count: int = Field(default=0, ge=0)
    token_accounting_mode: str | None = Field(default=None, max_length=40)
    provider_receipt_id: str | None = Field(default=None, max_length=100)
    total_tokens: int = Field(default=0, ge=0)
    token_pricing_source: str | None = Field(default=None, max_length=100)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0.0, ge=0.0)
    log_path: str | None = Field(default=None, max_length=500)
    verification_mode: str | None = Field(default=None, max_length=100)
    verification_template: str | None = Field(default=None, max_length=100)
    verification_command: str | None = Field(default=None, max_length=500)
    verification_summary: str | None = Field(default=None, max_length=2_000)
    failure_category: RunFailureCategory | None = None
    quality_gate_passed: bool | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator(
        "model_name",
        "handoff_reason",
        "dispatch_status",
        "provider_key",
        "prompt_template_key",
        "prompt_template_version",
        "token_accounting_mode",
        "provider_receipt_id",
        "token_pricing_source",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """Collapse blank optional text fields into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None

    @model_validator(mode="after")
    def validate_time_range(self) -> "Run":
        """Ensure persisted timestamps are always UTC-aware."""

        object.__setattr__(self, "started_at", ensure_utc_datetime(self.started_at))
        object.__setattr__(self, "finished_at", ensure_utc_datetime(self.finished_at))
        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))

        if (
            self.started_at is not None
            and self.finished_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError("finished_at cannot be earlier than started_at")

        return self
