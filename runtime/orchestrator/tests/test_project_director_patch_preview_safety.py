"""Contract tests for P18 patch preview sanitizer / diff safety hardening."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.project_director_patch_preview_safety import (
    APPLYABLE_DIFF_MARKERS,
    ProjectDirectorPatchPreviewSafetyResult,
    assert_patch_preview_safe,
    detect_applyable_diff_markers,
    sanitize_patch_preview,
)


# ── A. empty preview is safe ──────────────────────────────────────────


def test_empty_preview_is_safe() -> None:
    result = sanitize_patch_preview([])

    assert result.status == "safe"
    assert result.original_count == 0
    assert result.sanitized_preview == []
    assert result.applyable_diff_detected is False
    assert result.actual_patch_applied is False
    assert result.product_runtime_git_write_allowed is False
    assert result.worktree_write_allowed is False
    assert result.file_write_allowed is False
    assert result.git_write_performed is False
    assert result.ai_project_director_total_loop == "Partial"


# ── B. preview-only content remains unchanged ─────────────────────────


def test_preview_only_content_remains_unchanged() -> None:
    preview = ["PREVIEW ONLY: no repository file was modified."]
    result = sanitize_patch_preview(preview)

    assert result.status == "safe"
    assert result.sanitized_preview == preview
    assert result.unsafe_markers == []
    assert result.blocked_reasons == []


# ── C. detects all unsafe markers ─────────────────────────────────────


@pytest.mark.parametrize(
    "marker",
    list(APPLYABLE_DIFF_MARKERS),
)
def test_detects_unsafe_marker(marker: str) -> None:
    preview = [f"{marker} some content after"]
    result = sanitize_patch_preview(preview)

    assert result.applyable_diff_detected is True
    assert result.status == "sanitized"
    assert "applyable_diff_marker_detected" in result.blocked_reasons
    assert len(result.unsafe_markers) >= 1
    assert result.unsafe_markers[0].marker == marker
    assert result.unsafe_markers[0].reason == "applyable_diff_marker_detected"


# ── D. sanitizer must not retain raw unsafe line ──────────────────────


def test_sanitizer_does_not_retain_raw_unsafe_content() -> None:
    preview = [
        "diff --git a/secret.py b/secret.py",
        "+API_KEY=abc",
    ]
    result = sanitize_patch_preview(preview)

    for line in result.sanitized_preview:
        assert "diff --git" not in line
        assert "API_KEY" not in line

    assert all(
        "PREVIEW ONLY" in line or "no repository file" in line.lower()
        for line in result.sanitized_preview
    )

    for finding in result.unsafe_markers:
        assert "API_KEY" not in finding.marker
        assert "API_KEY" not in finding.reason
        assert "secret.py" not in finding.marker
        assert "secret.py" not in finding.reason


# ── E. assert_patch_preview_safe accepts safe preview ─────────────────


def test_assert_patch_preview_safe_accepts_safe_preview() -> None:
    preview = ["PREVIEW ONLY: consider file.py; no repository file was modified."]
    result = assert_patch_preview_safe(preview)
    assert result == preview


# ── F. assert_patch_preview_safe rejects unsafe preview ───────────────


def test_assert_patch_preview_safe_rejects_unsafe_preview() -> None:
    preview = ["diff --git a/a.py b/a.py"]
    with pytest.raises(ValueError, match="patch_preview_contains_applyable_diff_marker"):
        assert_patch_preview_safe(preview)


# ── G. safety result validators reject dangerous true flags ───────────


@pytest.mark.parametrize(
    "field_name",
    [
        "actual_patch_applied",
        "product_runtime_git_write_allowed",
        "worktree_write_allowed",
        "file_write_allowed",
        "git_write_performed",
    ],
)
def test_safety_result_validator_rejects_true_flags(field_name: str) -> None:
    with pytest.raises(ValidationError, match="must remain false"):
        ProjectDirectorPatchPreviewSafetyResult(
            status="safe",
            original_count=0,
            **{field_name: True},
        )


# ── Additional: multline preview with embedded diff ───────────────────


def test_multiline_preview_item_with_embedded_diff_detected() -> None:
    preview = ["diff --git a/a.py b/a.py\n@@ -1 +1 @@\n-old\n+new"]
    result = sanitize_patch_preview(preview)

    assert result.applyable_diff_detected is True
    assert result.status == "sanitized"
    assert "diff --git" not in " ".join(result.sanitized_preview)
    assert "@@" not in " ".join(result.sanitized_preview)


# ── Additional: mixed safe and unsafe ─────────────────────────────────


def test_mixed_safe_and_unsafe_preview_sanitized() -> None:
    preview = [
        "PREVIEW ONLY: consider src/foo.py",
        "diff --git a/src/foo.py b/src/foo.py",
    ]
    result = sanitize_patch_preview(preview)

    assert result.status == "sanitized"
    assert result.applyable_diff_detected is True
    for line in result.sanitized_preview:
        assert "diff --git" not in line
