"""Contract tests for P17 programmer no-write execution domain model."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.project_director_programmer_no_write_execution import (
    ProjectDirectorProgrammerNoWriteExecutionResult,
    ProjectDirectorProgrammerNoWriteExecutionStep,
)


FORBIDDEN_SENSITIVE_TERMS = {
    "api_key",
    "token",
    "secret",
    "pid",
    "raw command",
    "raw stdout",
    "raw stderr",
    "已执行提交",
    "已推送",
    "PR 已创建",
    "代码已写入",
    "代码已修改",
    "已授权 Git 写",
    "已启动 Codex",
    "已启动 Claude",
}

FORBIDDEN_DIFF_PATTERNS = [
    "diff --git",
    "+++ b/",
    "--- a/",
    "@@",
]


def _default_result(**overrides) -> ProjectDirectorProgrammerNoWriteExecutionResult:
    base = dict(
        execution_status="planned",
        session_id=uuid4(),
        source_task_id=uuid4(),
        source_message_id=uuid4(),
    )
    base.update(overrides)
    return ProjectDirectorProgrammerNoWriteExecutionResult(**base)


# ── 1. Default safety fields ─────────────────────────────────────────


def test_result_default_safety_fields() -> None:
    result = _default_result()

    assert result.programmer_agent is True
    assert result.controlled_programmer_execution is True
    assert result.no_write_execution is True
    assert result.executor_backed_programmer_allowed is True
    assert result.product_runtime_git_write_allowed is False
    assert result.worktree_write_allowed is False
    assert result.file_write_allowed is False
    assert result.actual_patch_applied is False
    assert result.real_code_modified is False
    assert result.git_write_performed is False
    assert result.native_executor_started is False
    assert result.codex_started is False
    assert result.claude_code_started is False
    assert result.worker_started is False
    assert result.task_created is False
    assert result.run_created is False
    assert result.ai_project_director_total_loop == "Partial"


# ── 2. Validator rejects true for forbidden flags ─────────────────────


@pytest.mark.parametrize(
    "field_name",
    [
        "product_runtime_git_write_allowed",
        "worktree_write_allowed",
        "file_write_allowed",
        "actual_patch_applied",
        "real_code_modified",
        "git_write_performed",
        "native_executor_started",
        "codex_started",
        "claude_code_started",
        "worker_started",
        "task_created",
        "run_created",
    ],
)
def test_result_validator_rejects_true_forbidden_flags(field_name: str) -> None:
    with pytest.raises(ValidationError, match="must remain false"):
        _default_result(**{field_name: True})


# ── 3. ExecutionStep structure completeness ───────────────────────────


def test_execution_step_has_all_required_fields() -> None:
    step = ProjectDirectorProgrammerNoWriteExecutionStep(
        step_id="p17-execution-1",
        title="Test execution step",
        summary="A test execution step summary.",
        source_plan_step_ids=["p16-plan-1"],
        files_considered=["src/foo.py"],
        patch_preview=["PREVIEW ONLY: consider src/foo.py"],
        tests_to_run=["test_foo.py"],
        risk_notes=["low risk"],
    )

    assert step.step_id == "p17-execution-1"
    assert step.title == "Test execution step"
    assert step.summary == "A test execution step summary."
    assert step.source_plan_step_ids == ["p16-plan-1"]
    assert step.files_considered == ["src/foo.py"]
    assert step.patch_preview == ["PREVIEW ONLY: consider src/foo.py"]
    assert step.tests_to_run == ["test_foo.py"]
    assert step.risk_notes == ["low risk"]


def test_execution_step_fields_have_length_constraints() -> None:
    with pytest.raises(ValidationError):
        ProjectDirectorProgrammerNoWriteExecutionStep(
            step_id="", title="t", summary="s"
        )

    with pytest.raises(ValidationError):
        ProjectDirectorProgrammerNoWriteExecutionStep(
            step_id="x", title="", summary="s"
        )

    with pytest.raises(ValidationError):
        ProjectDirectorProgrammerNoWriteExecutionStep(
            step_id="x", title="t", summary=""
        )


# ── 4. patch_preview must be preview-only, not an applyable diff ──────


def test_patch_preview_must_not_be_applyable_diff() -> None:
    result = _default_result(
        patch_preview=[
            "PREVIEW ONLY: consider src/foo.py; no repository file was modified."
        ]
    )
    for line in result.patch_preview:
        for pattern in FORBIDDEN_DIFF_PATTERNS:
            assert not line.startswith(pattern), (
                f"patch_preview contains applyable diff pattern: {pattern}"
            )


@pytest.mark.parametrize(
    "diff_line",
    [
        "diff --git a/src/foo.py b/src/foo.py",
        "+++ b/src/foo.py",
        "--- a/src/foo.py",
        "@@ -1,3 +1,4 @@",
    ],
)
def test_execution_step_patch_preview_diff_format_is_not_generated_by_service(
    diff_line: str,
) -> None:
    """This test verifies service-generated patch_preview remains preview-only.

    P18 also adds domain-level patch_preview validation; separate tests assert
    raw applyable diff markers are rejected by Step and Result models.
    """
    from app.domain.project_director_programmer_no_write_execution import (
        ProgrammerNoWriteExecutionMode,
    )
    from app.services.project_director_programmer_no_write_execution_service import (
        ProjectDirectorProgrammerNoWriteExecutionService,
    )

    preview = ProjectDirectorProgrammerNoWriteExecutionService._patch_preview(
        ["src/foo.py"],
        execution_mode="fake_execution",  # type: ignore[arg-type]
    )
    for line in preview:
        assert not line.startswith("diff --git"), f"Service leaked diff: {line}"
        assert not line.startswith("+++ b/"), f"Service leaked diff: {line}"
        assert not line.startswith("--- a/"), f"Service leaked diff: {line}"
        assert not line.startswith("@@"), f"Service leaked diff: {line}"
        assert "PREVIEW ONLY" in line or "no repository file" in line.lower()


# ── 5. Output does not contain sensitive/misleading terms ─────────────


def test_result_output_excludes_sensitive_terms() -> None:
    result = _default_result()
    serialized = result.model_dump_json().lower()

    for term in FORBIDDEN_SENSITIVE_TERMS:
        assert term.lower() not in serialized, f"Found forbidden term: {term}"


def test_result_with_steps_excludes_sensitive_terms() -> None:
    result = _default_result(
        execution_steps=[
            ProjectDirectorProgrammerNoWriteExecutionStep(
                step_id="p17-execution-1",
                title="Inspect P16 plan",
                summary="Use the P16 plan as execution evidence.",
            )
        ],
        execution_summary="Programmer no-write execution prepared.",
        recommended_next_step="Run safety tests.",
    )
    serialized = result.model_dump_json().lower()

    for term in FORBIDDEN_SENSITIVE_TERMS:
        assert term.lower() not in serialized, f"Found forbidden term: {term}"


# ── 6. P18: domain validator rejects unsafe patch_preview ─────────────


def test_step_patch_preview_rejects_unsafe_marker() -> None:
    with pytest.raises(ValueError, match="patch_preview_contains_applyable_diff_marker"):
        ProjectDirectorProgrammerNoWriteExecutionStep(
            step_id="p17-execution-1",
            title="Test step",
            summary="Test summary.",
            patch_preview=["diff --git a/a.py b/a.py"],
        )


def test_result_patch_preview_rejects_unsafe_marker() -> None:
    with pytest.raises(ValueError, match="patch_preview_contains_applyable_diff_marker"):
        _default_result(patch_preview=["@@ -1 +1 @@"])


def test_step_safe_preview_only_still_passes() -> None:
    step = ProjectDirectorProgrammerNoWriteExecutionStep(
        step_id="p17-execution-1",
        title="Test step",
        summary="Test summary.",
        patch_preview=["PREVIEW ONLY: consider file.py; no repository file was modified."],
    )
    assert step.patch_preview == [
        "PREVIEW ONLY: consider file.py; no repository file was modified."
    ]


def test_result_safe_preview_only_still_passes() -> None:
    result = _default_result(
        patch_preview=["PREVIEW ONLY: no repository file was modified."]
    )
    assert result.patch_preview == [
        "PREVIEW ONLY: no repository file was modified."
    ]


@pytest.mark.parametrize(
    "marker",
    [
        "diff --git a/a.py b/a.py",
        "--- a/a.py",
        "+++ b/a.py",
        "@@ -1 +1 @@",
        "index abc123..def456",
        "new file mode 100644",
        "deleted file mode 100644",
        "rename from old.py",
        "rename to new.py",
    ],
)
def test_step_patch_preview_rejects_each_unsafe_marker(marker: str) -> None:
    with pytest.raises(ValueError, match="patch_preview_contains_applyable_diff_marker"):
        ProjectDirectorProgrammerNoWriteExecutionStep(
            step_id="p17-execution-1",
            title="Test step",
            summary="Test summary.",
            patch_preview=[marker],
        )
