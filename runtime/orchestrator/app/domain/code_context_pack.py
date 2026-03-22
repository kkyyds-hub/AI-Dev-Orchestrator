"""Domain models for Day05 file-location results and bounded code context packs."""

from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


class FileLocatorQuery(DomainModel):
    """Normalized query metadata used by the file locator and context-pack builder."""

    task_id: UUID | None = None
    task_title: str | None = Field(default=None, max_length=200)
    task_query: str | None = Field(default=None, max_length=2_000)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    path_prefixes: list[str] = Field(default_factory=list, max_length=20)
    module_names: list[str] = Field(default_factory=list, max_length=20)
    file_types: list[str] = Field(default_factory=list, max_length=10)
    limit: int = Field(default=12, ge=1, le=50)
    summary: str = Field(min_length=1, max_length=1_200)

    @field_validator("task_title", "task_query", "summary")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """Trim optional text fields and collapse blank strings to `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        if not normalized_value:
            return None

        return normalized_value

    @field_validator("keywords", "path_prefixes", "module_names", "file_types")
    @classmethod
    def normalize_string_lists(cls, values: list[str]) -> list[str]:
        """Trim, drop blanks and deduplicate normalized string lists."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for value in values:
            normalized_value = value.strip()
            if not normalized_value or normalized_value in seen_items:
                continue

            normalized_items.append(normalized_value)
            seen_items.add(normalized_value)

        return normalized_items


class FileLocatorCandidate(DomainModel):
    """One ranked candidate file returned by the Day05 locator."""

    relative_path: str = Field(min_length=1, max_length=1_000)
    language: str = Field(min_length=1, max_length=100)
    file_type: str = Field(min_length=1, max_length=50)
    byte_size: int = Field(default=0, ge=0)
    line_count: int = Field(default=0, ge=0)
    score: int = Field(default=0, ge=0)
    match_reasons: list[str] = Field(default_factory=list, max_length=20)
    matched_keywords: list[str] = Field(default_factory=list, max_length=20)
    preview: str | None = Field(default=None, max_length=300)

    @field_validator("relative_path")
    @classmethod
    def normalize_relative_path(cls, value: str) -> str:
        """Store one safe POSIX-style relative path."""

        normalized_value = value.replace("\\", "/").strip().lstrip("./")
        if not normalized_value:
            raise ValueError("relative_path cannot be blank.")

        normalized_path = PurePosixPath(normalized_value)
        if normalized_path.is_absolute() or ".." in normalized_path.parts:
            raise ValueError("relative_path must stay inside the repository root.")

        return normalized_path.as_posix()

    @field_validator("language", "file_type")
    @classmethod
    def normalize_candidate_text(cls, value: str) -> str:
        """Trim required candidate text fields."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("FileLocatorCandidate text fields cannot be blank.")

        return normalized_value

    @field_validator("preview")
    @classmethod
    def normalize_preview(cls, value: str | None) -> str | None:
        """Trim optional preview text while collapsing blank previews to `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        if not normalized_value:
            return None

        return normalized_value

    @field_validator("match_reasons", "matched_keywords")
    @classmethod
    def normalize_candidate_lists(cls, values: list[str]) -> list[str]:
        """Trim, drop blanks and deduplicate candidate list payloads."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for value in values:
            normalized_value = value.strip()
            if not normalized_value or normalized_value in seen_items:
                continue

            normalized_items.append(normalized_value)
            seen_items.add(normalized_value)

        return normalized_items


class FileLocatorResult(DomainModel):
    """Complete Day05 locator result for one project repository."""

    project_id: UUID
    repository_root_path: str = Field(min_length=1, max_length=1_000)
    ignored_directory_names: list[str] = Field(default_factory=list, max_length=40)
    query: FileLocatorQuery
    scanned_file_count: int = Field(default=0, ge=0)
    candidate_count: int = Field(default=0, ge=0)
    total_match_count: int = Field(default=0, ge=0)
    truncated: bool = False
    generated_at: datetime = Field(default_factory=utc_now)
    candidates: list[FileLocatorCandidate] = Field(default_factory=list, max_length=50)

    @field_validator("repository_root_path")
    @classmethod
    def normalize_root_path(cls, value: str) -> str:
        """Trim persisted repository root paths."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("repository_root_path cannot be blank.")

        return normalized_value

    @field_validator("ignored_directory_names")
    @classmethod
    def normalize_ignored_directory_names(cls, values: list[str]) -> list[str]:
        """Trim, drop blanks and deduplicate ignored directory names."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for value in values:
            normalized_value = value.strip()
            if not normalized_value or normalized_value in seen_items:
                continue

            normalized_items.append(normalized_value)
            seen_items.add(normalized_value)

        return normalized_items

    @model_validator(mode="after")
    def validate_result_state(self) -> "FileLocatorResult":
        """Keep aggregate counters and timestamps consistent."""

        object.__setattr__(self, "generated_at", ensure_utc_datetime(self.generated_at))

        if self.candidate_count != len(self.candidates):
            object.__setattr__(self, "candidate_count", len(self.candidates))

        if self.total_match_count < self.candidate_count:
            raise ValueError("total_match_count cannot be smaller than candidate_count.")

        return self


class CodeContextPackEntry(DomainModel):
    """One file excerpt stored inside a bounded Day05 `CodeContextPack`."""

    relative_path: str = Field(min_length=1, max_length=1_000)
    language: str = Field(min_length=1, max_length=100)
    file_type: str = Field(min_length=1, max_length=50)
    byte_size: int = Field(default=0, ge=0)
    line_count: int = Field(default=0, ge=0)
    included_bytes: int = Field(default=0, ge=0)
    included_line_count: int = Field(default=0, ge=0)
    start_line: int = Field(default=0, ge=0)
    end_line: int = Field(default=0, ge=0)
    truncated: bool = False
    match_reasons: list[str] = Field(default_factory=list, max_length=20)
    excerpt: str = Field(default="", max_length=20_000)

    @field_validator("relative_path")
    @classmethod
    def normalize_entry_relative_path(cls, value: str) -> str:
        """Store one safe POSIX-style relative path."""

        normalized_value = value.replace("\\", "/").strip().lstrip("./")
        if not normalized_value:
            raise ValueError("relative_path cannot be blank.")

        normalized_path = PurePosixPath(normalized_value)
        if normalized_path.is_absolute() or ".." in normalized_path.parts:
            raise ValueError("relative_path must stay inside the repository root.")

        return normalized_path.as_posix()

    @field_validator("language", "file_type")
    @classmethod
    def normalize_entry_text(cls, value: str) -> str:
        """Trim required entry text fields."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("CodeContextPackEntry text fields cannot be blank.")

        return normalized_value

    @field_validator("excerpt")
    @classmethod
    def normalize_excerpt(cls, value: str) -> str:
        """Normalize excerpt line endings while preserving code indentation."""

        return value.replace("\r\n", "\n").replace("\r", "\n")

    @field_validator("match_reasons")
    @classmethod
    def normalize_entry_reasons(cls, values: list[str]) -> list[str]:
        """Trim, drop blanks and deduplicate excerpt reasons."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for value in values:
            normalized_value = value.strip()
            if not normalized_value or normalized_value in seen_items:
                continue

            normalized_items.append(normalized_value)
            seen_items.add(normalized_value)

        return normalized_items

    @model_validator(mode="after")
    def validate_line_window(self) -> "CodeContextPackEntry":
        """Keep excerpt byte and line counters internally consistent."""

        if self.included_line_count > self.line_count:
            raise ValueError("included_line_count cannot exceed line_count.")

        if self.line_count == 0:
            if self.start_line != 0 or self.end_line != 0 or self.included_line_count != 0:
                raise ValueError("Empty files must keep line counters at zero.")
            return self

        if self.start_line < 1 or self.end_line < self.start_line:
            raise ValueError("Non-empty entries must keep a valid excerpt line window.")

        return self


class CodeContextPack(DomainModel):
    """Bounded code excerpt package prepared for later Day06 planning input."""

    project_id: UUID | None = None
    repository_root_path: str = Field(min_length=1, max_length=1_000)
    source_summary: str = Field(min_length=1, max_length=1_200)
    focus_terms: list[str] = Field(default_factory=list, max_length=20)
    selected_paths: list[str] = Field(default_factory=list, max_length=20)
    omitted_paths: list[str] = Field(default_factory=list, max_length=20)
    max_total_bytes: int = Field(ge=1)
    max_bytes_per_file: int = Field(ge=1)
    included_file_count: int = Field(default=0, ge=0)
    total_included_bytes: int = Field(default=0, ge=0)
    truncated: bool = False
    generated_at: datetime = Field(default_factory=utc_now)
    entries: list[CodeContextPackEntry] = Field(default_factory=list, max_length=20)

    @field_validator("repository_root_path", "source_summary")
    @classmethod
    def normalize_pack_text(cls, value: str) -> str:
        """Trim required pack-level text fields."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("CodeContextPack text fields cannot be blank.")

        return normalized_value

    @field_validator("focus_terms", "selected_paths", "omitted_paths")
    @classmethod
    def normalize_pack_lists(cls, values: list[str]) -> list[str]:
        """Trim, drop blanks and deduplicate string list payloads."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for value in values:
            normalized_value = value.replace("\\", "/").strip()
            if normalized_value.startswith("./"):
                normalized_value = normalized_value[2:]
            if not normalized_value or normalized_value in seen_items:
                continue

            normalized_items.append(normalized_value)
            seen_items.add(normalized_value)

        return normalized_items

    @model_validator(mode="after")
    def validate_pack_state(self) -> "CodeContextPack":
        """Keep aggregate counters and timestamps aligned with included entries."""

        object.__setattr__(self, "generated_at", ensure_utc_datetime(self.generated_at))

        if self.included_file_count != len(self.entries):
            object.__setattr__(self, "included_file_count", len(self.entries))

        computed_total_included_bytes = sum(entry.included_bytes for entry in self.entries)
        if self.total_included_bytes != computed_total_included_bytes:
            object.__setattr__(self, "total_included_bytes", computed_total_included_bytes)

        if self.total_included_bytes > self.max_total_bytes:
            raise ValueError("total_included_bytes cannot exceed max_total_bytes.")

        return self
