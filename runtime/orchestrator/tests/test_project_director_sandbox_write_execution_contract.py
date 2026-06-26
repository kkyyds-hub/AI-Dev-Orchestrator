"""Contract tests for P21-A sandbox write execution domain model."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.project_director_sandbox_write_execution import (
    ProjectDirectorSandboxWriteExecutionResult,
    ProjectDirectorSandboxWriteOperationResult,
)


MISLEADING_TERMS = {
    "已修改代码",
    "已应用 patch",
    "已创建 worktree",
    "已清理 worktree",
    "已提交代码",
    "已推送",
    "Git 写入已授权",
    "可以提交代码",
    "已执行提交",
    "代码已提交",
    "PR 已创建",
    "合并请求已创建",
    "automatic commit",
    "git commit performed",
}


def _default_result(**overrides) -> ProjectDirectorSandboxWriteExecutionResult:
    base = dict(
        execution_status="planned",
        session_id=uuid4(),
        execution_summary="P21-A dry-run execution result was planned only.",
        recommended_next_step="Add targeted P21-A evidence.",
    )
    base.update(overrides)
    return ProjectDirectorSandboxWriteExecutionResult(**base)


def _default_operation(**overrides) -> ProjectDirectorSandboxWriteOperationResult:
    base = dict(
        operation_id="p21-a-1",
        path="runtime/orchestrator/app/domain/foo.py",
        operation="p20_preflight_accepted_path",
        execution_status="planned",
        source_preflight_path_policy_allowed=True,
    )
    base.update(overrides)
    return ProjectDirectorSandboxWriteOperationResult(**base)


# ── 1. dry_run result ─────────────────────────────────────────────────


def test_dry_run_result_fields() -> None:
    result = _default_result(
        execution_status="planned",
        execution_mode="dry_run",
        dry_run_only=True,
        fake_write_only=False,
        policy_only_source_verified=True,
        source_preflight_message_bound=True,
        checked_operations_count=1,
        operation_results=[_default_operation()],
    )
    assert result.execution_status == "planned"
    assert result.execution_mode == "dry_run"
    assert result.dry_run_only is True
    assert result.fake_write_only is False
    assert result.policy_only_source_verified is True
    assert result.source_preflight_message_bound is True
    assert result.checked_operations_count == 1
    assert len(result.operation_results) == 1
    assert result.operation_results[0].execution_status == "planned"
    assert result.operation_results[0].source_preflight_path_policy_allowed is True


# ── 2. fake_write result ─────────────────────────────────────────────


def test_fake_write_result_fields() -> None:
    result = _default_result(
        execution_status="simulated",
        execution_mode="fake_write",
        dry_run_only=False,
        fake_write_only=True,
        simulated_operations_count=2,
        operation_results=[
            _default_operation(operation_id="p21-a-1", execution_status="simulated"),
            _default_operation(
                operation_id="p21-a-2",
                path="runtime/orchestrator/tests/test_foo.py",
                execution_status="simulated",
            ),
        ],
        execution_summary="P21-A fake-write execution result was simulated only.",
    )
    assert result.execution_status == "simulated"
    assert result.execution_mode == "fake_write"
    assert result.dry_run_only is False
    assert result.fake_write_only is True
    assert result.simulated_operations_count == 2
    assert len(result.operation_results) == 2
    for op in result.operation_results:
        assert op.execution_status == "simulated"
    summary_lower = result.execution_summary.lower()
    assert "simulated" in summary_lower
    assert "file" not in summary_lower or "no file" in summary_lower


# ── 3. controlled_sandbox_write must be blocked ──────────────────────


def test_controlled_sandbox_write_blocked() -> None:
    result = _default_result(
        execution_status="blocked",
        execution_mode="controlled_sandbox_write",
        blocked_reasons=["controlled_sandbox_write_not_enabled_in_api"],
    )
    assert result.execution_status == "blocked"
    assert "controlled_sandbox_write_not_enabled_in_api" in result.blocked_reasons
    assert result.sandbox_write_allowed is False
    assert result.product_runtime_git_write_allowed is False
    assert result.file_write_allowed is False
    assert result.actual_patch_applied is False
    assert result.native_executor_started is False
    assert result.worker_started is False
    assert result.task_created is False
    assert result.run_created is False
    assert result.git_write_performed is False


# ── 4. no-write boundary flags must remain false ─────────────────────


@pytest.mark.parametrize(
    "field_name",
    [
        "controlled_sandbox_write_enabled",
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
        "worktree_created",
        "worktree_cleaned_up",
        "rollback_snapshot_created",
        "cleanup_required",
    ],
)
def test_result_validator_rejects_true_flags(field_name: str) -> None:
    with pytest.raises(ValidationError, match="must remain false"):
        _default_result(**{field_name: True})


@pytest.mark.parametrize(
    "field_name",
    [
        "rollback_snapshot_available",
        "cleanup_required",
        "file_written",
        "patch_applied",
        "worktree_written",
        "git_write_performed",
    ],
)
def test_operation_validator_rejects_true_flags(field_name: str) -> None:
    with pytest.raises(ValidationError, match="must remain false"):
        _default_operation(**{field_name: True})


# ── 5. ai_project_director_total_loop must be Partial ────────────────


def test_total_loop_partial() -> None:
    result = _default_result()
    assert result.ai_project_director_total_loop == "Partial"


# ── 6. operation result structure ────────────────────────────────────


def test_operation_result_fields() -> None:
    op = _default_operation()
    assert op.file_written is False
    assert op.patch_applied is False
    assert op.worktree_written is False
    assert op.git_write_performed is False
    assert op.source_preflight_path_policy_allowed is True
    assert op.operation == "p20_preflight_accepted_path"


# ── 7. output must not contain misleading terms ──────────────────────


def test_result_output_excludes_misleading_terms() -> None:
    result = _default_result()
    serialized = result.model_dump_json()
    for term in MISLEADING_TERMS:
        assert term not in serialized, f"Found misleading term: {term}"


def test_operation_output_excludes_misleading_terms() -> None:
    op = _default_operation()
    serialized = op.model_dump_json()
    for term in MISLEADING_TERMS:
        assert term not in serialized, f"Found misleading term: {term}"
