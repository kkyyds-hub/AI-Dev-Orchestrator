"""Contract tests for P20 sandbox write preflight domain model."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.project_director_sandbox_write_preflight import (
    ProjectDirectorFileOperationPlan,
    ProjectDirectorSandboxWritePreflightResult,
)


MISLEADING_TERMS = {
    "文件已写入",
    "已应用 patch",
    "已提交",
    "已推送",
    "已合并",
    "Git 写已授权",
    "worktree 已创建",
    "sandbox 已写入",
}


# ── A. FileOperationPlan accepts safe operation ───────────────────────


def test_file_operation_plan_accepts_safe_operation() -> None:
    plan = ProjectDirectorFileOperationPlan(
        path="runtime/orchestrator/app/domain/foo.py",
        operation="update",
        reason="fix bug",
        patch_preview=["PREVIEW ONLY: no repository file was modified."],
    )
    assert plan.path == "runtime/orchestrator/app/domain/foo.py"
    assert plan.operation == "update"
    assert plan.patch_preview == ["PREVIEW ONLY: no repository file was modified."]


# ── B. FileOperationPlan rejects unsafe patch_preview ─────────────────


@pytest.mark.parametrize(
    "marker",
    [
        "diff --git a/a.py b/a.py",
        "--- a/a.py",
        "+++ b/a.py",
        "@@ -1 +1 @@",
    ],
)
def test_file_operation_plan_rejects_unsafe_patch_preview(marker: str) -> None:
    with pytest.raises(ValueError, match="patch_preview_contains_applyable_diff_marker"):
        ProjectDirectorFileOperationPlan(
            path="runtime/orchestrator/app/domain/foo.py",
            operation="update",
            reason="fix",
            patch_preview=[marker],
        )


# ── C. Result default safety flags ────────────────────────────────────


def test_result_default_safety_flags() -> None:
    result = ProjectDirectorSandboxWritePreflightResult(
        preflight_status="passed",
        session_id=uuid4(),
    )
    assert result.policy_only_preflight is True
    assert result.sandbox_write_allowed is False
    assert result.product_runtime_git_write_allowed is False
    assert result.main_worktree_write_allowed is False
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


# ── D. result validator rejects true for forbidden flags ──────────────


@pytest.mark.parametrize(
    "field_name",
    [
        "sandbox_write_allowed",
        "product_runtime_git_write_allowed",
        "main_worktree_write_allowed",
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
        ProjectDirectorSandboxWritePreflightResult(
            preflight_status="passed",
            session_id=uuid4(),
            **{field_name: True},
        )


# ── E. blocked/passed counts can be represented ──────────────────────


def test_result_counts_and_paths() -> None:
    result = ProjectDirectorSandboxWritePreflightResult(
        preflight_status="passed",
        session_id=uuid4(),
        checked_operations_count=3,
        allowed_operations_count=2,
        blocked_operations_count=1,
        accepted_operations=[
            {"path": "a.py", "operation": "create"},
            {"path": "b.py", "operation": "update"},
        ],
        accepted_operation_paths=["a.py", "b.py"],
        blocked_operation_paths=["c.py"],
    )
    assert result.checked_operations_count == 3
    assert result.allowed_operations_count == 2
    assert result.blocked_operations_count == 1
    assert result.accepted_operations[0].path == "a.py"
    assert result.accepted_operations[0].operation == "create"
    assert result.accepted_operations[1].path == "b.py"
    assert result.accepted_operations[1].operation == "update"
    assert result.accepted_operation_paths == ["a.py", "b.py"]
    assert result.blocked_operation_paths == ["c.py"]


# ── F. output must not contain misleading terms ───────────────────────


def test_result_output_excludes_misleading_terms() -> None:
    result = ProjectDirectorSandboxWritePreflightResult(
        preflight_status="passed",
        session_id=uuid4(),
    )
    serialized = result.model_dump_json()
    for term in MISLEADING_TERMS:
        assert term not in serialized, f"Found misleading term: {term}"
