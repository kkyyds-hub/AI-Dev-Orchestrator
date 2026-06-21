"""Repository file-locator and code-context request schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class FileLocatorSearchRequest(BaseModel):
    """DTO for Day05 repository file-location search requests."""

    task_id: UUID | None = Field(
        default=None,
        description="Optional project task ID used to derive locator keywords and summary.",
    )
    task_query: str | None = Field(
        default=None,
        max_length=2_000,
        description="Optional planning or task brief used to derive extra locator keywords.",
    )
    keywords: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Optional explicit keywords merged with task-derived tokens.",
    )
    path_prefixes: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Optional relative path prefixes, such as runtime/orchestrator/app/services.",
    )
    module_names: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Optional module or folder names used as strong Day05 signals.",
    )
    file_types: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Optional file types such as py, tsx, markdown or yaml.",
    )
    limit: int = Field(
        default=12,
        ge=1,
        le=50,
        description="Maximum number of candidate files returned by the locator.",
    )


class CodeContextPackBuildRequest(FileLocatorSearchRequest):
    """DTO for Day05 bounded code-context pack requests."""

    selected_paths: list[str] = Field(
        min_length=1,
        max_length=20,
        description="Relative repository file paths selected from the Day05 candidate list.",
    )
    max_total_bytes: int = Field(
        default=12_000,
        ge=512,
        le=80_000,
        description="Maximum UTF-8 byte budget for the full CodeContextPack.",
    )
    max_bytes_per_file: int = Field(
        default=4_000,
        ge=256,
        le=20_000,
        description="Maximum UTF-8 byte budget allocated to each selected file excerpt.",
    )
    selection_reasons_by_path: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Optional candidate match reasons keyed by relative path for UI round-trips.",
    )
