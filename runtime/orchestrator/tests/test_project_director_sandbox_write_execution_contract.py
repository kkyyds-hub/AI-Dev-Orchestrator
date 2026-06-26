"""Contract tests for P21-A sandbox write execution domain model."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_sandbox_write_execution import (
    ProjectDirectorSandboxWriteExecutionResult,
    ProjectDirectorSandboxWriteOperationResult,
)
from app.domain.task import Task
from app.services.project_director_sandbox_write_execution_service import (
    ProjectDirectorSandboxWriteExecutionService,
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
        operation="update",
        execution_status="planned",
        source_preflight_path_policy_allowed=True,
        source_preflight_operation_type="p20_preflight_accepted_path",
    )
    base.update(overrides)
    return ProjectDirectorSandboxWriteOperationResult(**base)


def _safe_task() -> Task:
    return Task(
        title="safe task",
        input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
        acceptance_criteria=[
            "safe_dry_run_task=true",
            "worker_simulate_required=true",
            "product_runtime_git_write_allowed=false",
            "native_executor_started=false",
            "codex_started=false",
            "claude_code_started=false",
        ],
        source_draft_id="p12-test",
    )


def _p20_message(
    *,
    session_id,
    task_id,
    action: dict,
) -> ProjectDirectorMessage:
    return ProjectDirectorMessage(
        session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="P20 preflight",
        sequence_no=1,
        related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail="p20_sandbox_write_preflight",
        suggested_actions=[action],
    )


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
    assert op.operation == "update"
    assert op.source_preflight_operation_type == "p20_preflight_accepted_path"


def test_service_preserves_structured_operation_intent_from_p20_action() -> None:
    service = ProjectDirectorSandboxWriteExecutionService()
    session_id = uuid4()
    task = _safe_task()
    message = _p20_message(
        session_id=session_id,
        task_id=task.id,
        action={
            "type": "p20_sandbox_write_preflight_record",
            "source_task_id": str(task.id),
            "preflight_status": "passed",
            "policy_only_preflight": True,
            "checked_operations_count": 2,
            "blocked_operations_count": 0,
            "blocked_reasons": [],
            "accepted_operation_paths": [
                "runtime/orchestrator/app/domain/new_file.py",
                "runtime/orchestrator/app/domain/existing_file.py",
            ],
            "accepted_operations": [
                {
                    "path": "runtime/orchestrator/app/domain/new_file.py",
                    "operation": "create",
                },
                {
                    "path": "runtime/orchestrator/app/domain/existing_file.py",
                    "operation": "update",
                },
            ],
        },
    )

    result = service.build_execution_from_sources(
        session_id=session_id,
        source_task=task,
        source_message=message,
        user_confirmed=True,
        execution_mode="dry_run",
    )

    assert result.blocked_reasons == []
    assert [operation.operation for operation in result.operation_results] == [
        "create",
        "update",
    ]
    assert all(
        operation.source_preflight_operation_type == "p20_preflight_accepted_path"
        for operation in result.operation_results
    )


def test_service_falls_back_for_legacy_p20_action_with_paths_only() -> None:
    service = ProjectDirectorSandboxWriteExecutionService()
    session_id = uuid4()
    task = _safe_task()
    message = _p20_message(
        session_id=session_id,
        task_id=task.id,
        action={
            "type": "p20_sandbox_write_preflight_record",
            "source_task_id": str(task.id),
            "preflight_status": "passed",
            "policy_only_preflight": True,
            "checked_operations_count": 1,
            "blocked_operations_count": 0,
            "blocked_reasons": [],
            "accepted_operation_paths": [
                "runtime/orchestrator/app/domain/legacy.py",
            ],
        },
    )

    result = service.build_execution_from_sources(
        session_id=session_id,
        source_task=task,
        source_message=message,
        user_confirmed=True,
        execution_mode="dry_run",
    )

    assert result.blocked_reasons == []
    assert result.operation_results[0].operation == "p20_preflight_accepted_path"


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
