"""Patch preview safety checks for Project Director preview-only outputs."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from app.domain._base import DomainModel


PatchPreviewSafetyStatus = Literal["safe", "sanitized", "blocked"]

APPLYABLE_DIFF_MARKERS = (
    "diff --git",
    "--- a/",
    "+++ b/",
    "@@",
    "index ",
    "new file mode ",
    "deleted file mode ",
    "rename from ",
    "rename to ",
)

PATCH_PREVIEW_SANITIZED_PLACEHOLDER = [
    "PREVIEW ONLY: applyable diff markers were removed from patch_preview.",
    "PREVIEW ONLY: no repository file was modified.",
]


class ProjectDirectorPatchPreviewSafetyFinding(DomainModel):
    """One unsafe marker finding without retaining raw patch line content."""

    marker: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=200)
    line_index: int | None = None


class ProjectDirectorPatchPreviewSafetyResult(DomainModel):
    """Sanitizer result for a preview-only patch preview channel."""

    status: PatchPreviewSafetyStatus
    original_count: int
    sanitized_preview: list[str] = Field(default_factory=list)
    unsafe_markers: list[ProjectDirectorPatchPreviewSafetyFinding] = Field(
        default_factory=list
    )
    blocked_reasons: list[str] = Field(default_factory=list)
    preview_only: bool = True
    applyable_diff_detected: bool = False
    actual_patch_applied: bool = False
    product_runtime_git_write_allowed: bool = False
    worktree_write_allowed: bool = False
    file_write_allowed: bool = False
    git_write_performed: bool = False
    ai_project_director_total_loop: str = "Partial"

    @field_validator(
        "actual_patch_applied",
        "product_runtime_git_write_allowed",
        "worktree_write_allowed",
        "file_write_allowed",
        "git_write_performed",
        mode="after",
    )
    @classmethod
    def reject_write_and_apply_flags(cls, value: bool) -> bool:
        if value:
            raise ValueError("patch preview safety flags must remain false")
        return value


def detect_applyable_diff_markers(
    preview: list[str],
) -> list[ProjectDirectorPatchPreviewSafetyFinding]:
    """Detect applyable diff markers without returning raw preview line content."""

    findings: list[ProjectDirectorPatchPreviewSafetyFinding] = []
    line_index = 0
    for preview_item in preview:
        for raw_line in preview_item.splitlines():
            stripped_line = raw_line.strip()
            for marker in APPLYABLE_DIFF_MARKERS:
                if stripped_line.startswith(marker):
                    findings.append(
                        ProjectDirectorPatchPreviewSafetyFinding(
                            marker=marker,
                            reason="applyable_diff_marker_detected",
                            line_index=line_index,
                        )
                    )
                    break
            line_index += 1
    return findings


def sanitize_patch_preview(
    preview: list[str],
) -> ProjectDirectorPatchPreviewSafetyResult:
    """Return preview-only output, replacing unsafe diff-shaped previews."""

    unsafe_markers = detect_applyable_diff_markers(preview)
    if not preview:
        return ProjectDirectorPatchPreviewSafetyResult(
            status="safe",
            original_count=0,
            sanitized_preview=[],
            applyable_diff_detected=False,
        )

    if not unsafe_markers:
        return ProjectDirectorPatchPreviewSafetyResult(
            status="safe",
            original_count=len(preview),
            sanitized_preview=list(preview),
            applyable_diff_detected=False,
        )

    return ProjectDirectorPatchPreviewSafetyResult(
        status="sanitized",
        original_count=len(preview),
        sanitized_preview=list(PATCH_PREVIEW_SANITIZED_PLACEHOLDER),
        unsafe_markers=unsafe_markers,
        blocked_reasons=["applyable_diff_marker_detected"],
        applyable_diff_detected=True,
    )


def assert_patch_preview_safe(preview: list[str]) -> list[str]:
    """Reject raw applyable diff markers before constructing domain objects."""

    result = sanitize_patch_preview(preview)
    if result.applyable_diff_detected:
        raise ValueError("patch_preview_contains_applyable_diff_marker")
    return list(preview)


__all__ = (
    "APPLYABLE_DIFF_MARKERS",
    "PatchPreviewSafetyStatus",
    "ProjectDirectorPatchPreviewSafetyFinding",
    "ProjectDirectorPatchPreviewSafetyResult",
    "assert_patch_preview_safe",
    "detect_applyable_diff_markers",
    "sanitize_patch_preview",
)
