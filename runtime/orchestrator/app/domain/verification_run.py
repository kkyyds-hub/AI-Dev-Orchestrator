"""Domain models for V4 Day10 structured repository verification runs."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now
from app.domain.repository_verification import RepositoryVerificationCategory


class VerificationRunStatus(StrEnum):
    """Stable Day10 verification-result states."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class VerificationRunCommandSource(StrEnum):
    """Where one verification command came from."""

    TEMPLATE = "template"
    MANUAL = "manual"


class VerificationRunFailureCategory(StrEnum):
    """Verification-specific Day10 failure or skip attribution categories."""

    COMMAND_FAILED = "command_failed"
    COMMAND_TIMEOUT = "command_timeout"
    CONFIGURATION_ERROR = "configuration_error"
    PRECHECK_BLOCKED = "precheck_blocked"
    MANUALLY_SKIPPED = "manually_skipped"
    WORKSPACE_UNAVAILABLE = "workspace_unavailable"


class VerificationRun(DomainModel):
    """One immutable repository-level verification result for a ChangeBatch command."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    repository_workspace_id: UUID
    change_plan_id: UUID
    change_batch_id: UUID
    verification_template_id: UUID | None = None
    verification_template_name: str | None = Field(default=None, max_length=100)
    verification_template_category: RepositoryVerificationCategory | None = None
    command_source: VerificationRunCommandSource
    command: str = Field(min_length=1, max_length=2_000)
    working_directory: str = Field(default=".", min_length=1, max_length=500)
    status: VerificationRunStatus
    failure_category: VerificationRunFailureCategory | None = None
    duration_seconds: float = Field(default=0.0, ge=0.0, le=86_400.0)
    output_summary: str = Field(min_length=1, max_length=2_000)
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime = Field(default_factory=utc_now)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("verification_template_name", "command", "output_summary")
    @classmethod
    def normalize_required_or_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        """Trim text fields and collapse blank optional values into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        if not normalized_value:
            return None

        return normalized_value

    @field_validator("working_directory")
    @classmethod
    def normalize_working_directory(cls, value: str) -> str:
        """Store one repository-relative POSIX working directory."""

        normalized_value = value.replace("\\", "/").strip()
        if not normalized_value:
            return "."

        normalized_path = PurePosixPath(normalized_value)
        if normalized_path.is_absolute() or ".." in normalized_path.parts:
            raise ValueError("Verification-run working_directory must stay inside the repository.")

        if normalized_path.as_posix() == ".":
            return "."

        return normalized_path.as_posix().lstrip("./")

    @model_validator(mode="after")
    def validate_run_state(self) -> "VerificationRun":
        """Normalize timestamps and keep template / failure invariants aligned."""

        object.__setattr__(self, "started_at", ensure_utc_datetime(self.started_at))
        object.__setattr__(self, "finished_at", ensure_utc_datetime(self.finished_at))
        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))

        if self.finished_at < self.started_at:
            raise ValueError("Verification-run finished_at cannot be earlier than started_at.")

        if self.command_source == VerificationRunCommandSource.TEMPLATE:
            if (
                self.verification_template_id is None
                or self.verification_template_name is None
                or self.verification_template_category is None
            ):
                raise ValueError(
                    "Template-backed verification runs must keep template id, name and category."
                )
        elif (
            self.verification_template_id is not None
            or self.verification_template_name is not None
            or self.verification_template_category is not None
        ):
            raise ValueError(
                "Manual verification runs cannot carry repository verification template fields."
            )

        if self.status == VerificationRunStatus.PASSED:
            if self.failure_category is not None:
                raise ValueError("Passed verification runs cannot keep a failure category.")
        elif self.failure_category is None:
            raise ValueError("Failed or skipped verification runs must record a failure category.")

        return self
