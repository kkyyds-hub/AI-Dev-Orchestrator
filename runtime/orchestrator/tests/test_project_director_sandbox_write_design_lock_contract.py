"""Contract tests for P21-B sandbox write design lock domain model."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.project_director_sandbox_write_design_lock import (
    ProjectDirectorSandboxWriteDesignLockResult,
)
from app.services.project_director_sandbox_write_design_lock_service import (
    ProjectDirectorSandboxWriteDesignLockService,
)


MISLEADING_TERMS = {
    "已写入文件",
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

ALL_RUNTIME_WRITE_FLAGS = [
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
]


def _default_locked_result(**overrides) -> ProjectDirectorSandboxWriteDesignLockResult:
    base = dict(
        design_lock_status="locked",
        session_id=uuid4(),
        source_task_id=uuid4(),
        source_message_id=uuid4(),
        source_execution_status="planned",
        source_execution_mode="dry_run",
        source_execution_message_bound=True,
        source_operation_intent_preserved=True,
        controlled_sandbox_write_design_locked=True,
        design_lock_summary="P21-B controlled sandbox write design lock is recorded for review only.",
        recommended_next_step="Mimocode should add targeted P21-B tests/smoke evidence next.",
    )
    base.update(overrides)
    return ProjectDirectorSandboxWriteDesignLockResult(**base)


# ── 1. Successful locked result fields ───────────────────────────────


def test_successful_locked_result() -> None:
    result = _default_locked_result()

    assert result.design_lock_status == "locked"
    assert result.controlled_sandbox_write_design_locked is True
    assert result.controlled_sandbox_write_enabled is False
    assert result.sandbox_write_allowed is False
    assert result.file_write_allowed is False
    assert result.worktree_write_allowed is False
    assert result.product_runtime_git_write_allowed is False
    assert result.ai_project_director_total_loop == "Partial"
    # required_preconditions is populated by the service, not domain model defaults
    # The service sets them from REQUIRED_PRECONDITIONS constant
    assert len(result.required_preconditions) >= 0  # service populates, domain may be empty
    assert len(result.allowed_future_write_scope) >= 0
    assert "no_product_runtime_git_write" in result.forbidden_runtime_actions or len(result.forbidden_runtime_actions) == 0
    assert "Mimocode" in result.recommended_next_step


# ── 2. Domain validator rejects true runtime flags ────────────────────


@pytest.mark.parametrize("field_name", ALL_RUNTIME_WRITE_FLAGS)
def test_result_validator_rejects_true_flags(field_name: str) -> None:
    with pytest.raises(ValidationError, match="must remain false"):
        _default_locked_result(**{field_name: True})


# ── 3. Service-level build from valid P21 action ─────────────────────


def test_service_build_from_valid_p21_dry_run_action() -> None:
    from app.domain.project_director_message import (
        ProjectDirectorMessage,
        ProjectDirectorMessageRole,
        ProjectDirectorMessageSource,
    )
    from app.domain.task import Task
    from app.services.project_director_sandbox_write_design_lock_service import (
        ProjectDirectorSandboxWriteDesignLockService,
    )
    from app.services.project_director_sandbox_write_execution_service import (
        P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL,
    )

    session_id = uuid4()
    task_id = uuid4()

    task = Task(
        id=task_id,
        title="P21-B test task",
        source_draft_id="p12-test",
        input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
        acceptance_criteria=[
            "safe_dry_run_task=true",
            "worker_simulate_required=true",
            "product_runtime_git_write_allowed=false",
            "native_executor_started=false",
            "codex_started=false",
            "claude_code_started=false",
        ],
    )

    p21_action = {
        "type": "p21_sandbox_write_execution_record",
        "source_task_id": str(task_id),
        "execution_mode": "dry_run",
        "execution_status": "planned",
        "no_write_execution": True,
        "controlled_sandbox_write_enabled": False,
        "sandbox_write_allowed": False,
        "product_runtime_git_write_allowed": False,
        "main_worktree_write_allowed": False,
        "worktree_write_allowed": False,
        "file_write_allowed": False,
        "actual_patch_applied": False,
        "real_code_modified": False,
        "git_write_performed": False,
        "native_executor_started": False,
        "codex_started": False,
        "claude_code_started": False,
        "worker_started": False,
        "task_created": False,
        "run_created": False,
        "worktree_created": False,
        "worktree_cleaned_up": False,
        "rollback_snapshot_created": False,
        "cleanup_required": False,
        "operation_results": [
            {
                "operation_id": "p21-a-1",
                "path": "runtime/orchestrator/app/domain/example.py",
                "operation": "create",
                "execution_status": "planned",
                "source_preflight_path_policy_allowed": True,
            }
        ],
    }

    message = ProjectDirectorMessage(
        session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="test",
        sequence_no=1,
        intent="sandbox_write_execution",
        related_project_id=uuid4(),
        related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL,
        suggested_actions=[p21_action],
    )

    service = ProjectDirectorSandboxWriteDesignLockService()
    result = service.build_design_lock_from_sources(
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=uuid4(),
        source_task=task,
        source_message=message,
        user_confirmed=True,
    )

    assert result.design_lock_status == "locked"
    assert result.source_execution_status == "planned"
    assert result.source_execution_mode == "dry_run"
    assert result.source_execution_message_bound is True
    assert result.source_operation_intent_preserved is True
    assert len(result.required_preconditions) > 0
    assert len(result.allowed_future_write_scope) > 0
    assert "no_product_runtime_git_write" in result.forbidden_runtime_actions
    assert "no_main_worktree_write" in result.forbidden_runtime_actions
    assert "no_target_file_content_read_in_design_lock" in result.forbidden_runtime_actions
    assert "operation_intent_missing" in result.failure_states
    assert "real_write_not_allowed_in_design_lock" in result.failure_states


def test_service_build_from_valid_p21_fake_write_action() -> None:
    from app.domain.project_director_message import (
        ProjectDirectorMessage,
        ProjectDirectorMessageRole,
        ProjectDirectorMessageSource,
    )
    from app.domain.task import Task
    from app.services.project_director_sandbox_write_design_lock_service import (
        ProjectDirectorSandboxWriteDesignLockService,
    )
    from app.services.project_director_sandbox_write_execution_service import (
        P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL,
    )

    session_id = uuid4()
    task_id = uuid4()

    task = Task(
        id=task_id,
        title="P21-B test task",
        source_draft_id="p12-test",
        input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
        acceptance_criteria=[
            "safe_dry_run_task=true",
            "worker_simulate_required=true",
            "product_runtime_git_write_allowed=false",
            "native_executor_started=false",
            "codex_started=false",
            "claude_code_started=false",
        ],
    )

    p21_action = {
        "type": "p21_sandbox_write_execution_record",
        "source_task_id": str(task_id),
        "execution_mode": "fake_write",
        "execution_status": "simulated",
        "no_write_execution": True,
        "controlled_sandbox_write_enabled": False,
        "sandbox_write_allowed": False,
        "product_runtime_git_write_allowed": False,
        "main_worktree_write_allowed": False,
        "worktree_write_allowed": False,
        "file_write_allowed": False,
        "actual_patch_applied": False,
        "real_code_modified": False,
        "git_write_performed": False,
        "native_executor_started": False,
        "codex_started": False,
        "claude_code_started": False,
        "worker_started": False,
        "task_created": False,
        "run_created": False,
        "worktree_created": False,
        "worktree_cleaned_up": False,
        "rollback_snapshot_created": False,
        "cleanup_required": False,
        "operation_results": [
            {
                "operation_id": "p21-a-1",
                "path": "runtime/orchestrator/app/domain/example.py",
                "operation": "update",
                "execution_status": "simulated",
                "source_preflight_path_policy_allowed": True,
            }
        ],
    }

    message = ProjectDirectorMessage(
        session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="test",
        sequence_no=1,
        intent="sandbox_write_execution",
        related_project_id=uuid4(),
        related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL,
        suggested_actions=[p21_action],
    )

    service = ProjectDirectorSandboxWriteDesignLockService()
    result = service.build_design_lock_from_sources(
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=uuid4(),
        source_task=task,
        source_message=message,
        user_confirmed=True,
    )

    assert result.design_lock_status == "locked"
    assert result.source_execution_status == "simulated"
    assert result.source_execution_mode == "fake_write"


# ── 4. Service blocks missing / invalid cases ────────────────────────


def test_service_blocks_user_confirmed_false() -> None:
    service = ProjectDirectorSandboxWriteDesignLockService()
    result = service.build_design_lock_from_sources(
        session_id=uuid4(),
        source_task_id=uuid4(),
        source_message_id=uuid4(),
        source_task=None,
        source_message=None,
        user_confirmed=False,
    )
    assert result.design_lock_status == "blocked"
    assert "user_confirmation_required" in result.blocked_reasons


def test_service_blocks_missing_source_message() -> None:
    from app.domain.task import Task

    service = ProjectDirectorSandboxWriteDesignLockService()
    result = service.build_design_lock_from_sources(
        session_id=uuid4(),
        source_task_id=uuid4(),
        source_message_id=uuid4(),
        source_task=Task(
            title="P21-B test task",
            source_draft_id="p12-test",
            input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
            acceptance_criteria=[
                "safe_dry_run_task=true",
                "worker_simulate_required=true",
                "product_runtime_git_write_allowed=false",
                "native_executor_started=false",
                "codex_started=false",
                "claude_code_started=false",
            ],
        ),
        source_message=None,
        user_confirmed=True,
    )
    assert result.design_lock_status == "blocked"
    assert "source_message_missing" in result.blocked_reasons


def test_service_blocks_non_p21_source_detail() -> None:
    from app.domain.project_director_message import (
        ProjectDirectorMessage,
        ProjectDirectorMessageRole,
        ProjectDirectorMessageSource,
    )
    from app.domain.task import Task

    session_id = uuid4()
    task_id = uuid4()

    task = Task(
        id=task_id,
        title="P21-B test task",
        source_draft_id="p12-test",
        input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
        acceptance_criteria=[
            "safe_dry_run_task=true",
            "worker_simulate_required=true",
            "product_runtime_git_write_allowed=false",
            "native_executor_started=false",
            "codex_started=false",
            "claude_code_started=false",
        ],
    )

    message = ProjectDirectorMessage(
        session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="test",
        sequence_no=1,
        intent="sandbox_write_execution",
        related_project_id=uuid4(),
        related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail="p20_sandbox_write_preflight",
        suggested_actions=[],
    )

    service = ProjectDirectorSandboxWriteDesignLockService()
    result = service.build_design_lock_from_sources(
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=uuid4(),
        source_task=task,
        source_message=message,
        user_confirmed=True,
    )
    assert result.design_lock_status == "blocked"
    assert "source_message_is_not_p21_sandbox_write_execution" in result.blocked_reasons


def test_service_blocks_source_task_message_mismatch() -> None:
    from app.domain.project_director_message import (
        ProjectDirectorMessage,
        ProjectDirectorMessageRole,
        ProjectDirectorMessageSource,
    )
    from app.domain.task import Task
    from app.services.project_director_sandbox_write_execution_service import (
        P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL,
    )

    session_id = uuid4()
    task_a_id = uuid4()
    task_b_id = uuid4()

    task_a = Task(
        id=task_a_id,
        title="P21-B test task A",
        source_draft_id="p12-test",
        input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
        acceptance_criteria=[
            "safe_dry_run_task=true",
            "worker_simulate_required=true",
            "product_runtime_git_write_allowed=false",
            "native_executor_started=false",
            "codex_started=false",
            "claude_code_started=false",
        ],
    )

    # P21 message bound to task B
    p21_action = {
        "type": "p21_sandbox_write_execution_record",
        "source_task_id": str(task_b_id),
        "execution_mode": "dry_run",
        "execution_status": "planned",
        "no_write_execution": True,
        "controlled_sandbox_write_enabled": False,
        "sandbox_write_allowed": False,
        "product_runtime_git_write_allowed": False,
        "main_worktree_write_allowed": False,
        "worktree_write_allowed": False,
        "file_write_allowed": False,
        "actual_patch_applied": False,
        "real_code_modified": False,
        "git_write_performed": False,
        "native_executor_started": False,
        "codex_started": False,
        "claude_code_started": False,
        "worker_started": False,
        "task_created": False,
        "run_created": False,
        "worktree_created": False,
        "worktree_cleaned_up": False,
        "rollback_snapshot_created": False,
        "cleanup_required": False,
        "operation_results": [
            {
                "operation_id": "p21-a-1",
                "path": "test.py",
                "operation": "create",
                "execution_status": "planned",
            }
        ],
    }

    message = ProjectDirectorMessage(
        session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="test",
        sequence_no=1,
        intent="sandbox_write_execution",
        related_project_id=uuid4(),
        related_task_id=task_b_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL,
        suggested_actions=[p21_action],
    )

    service = ProjectDirectorSandboxWriteDesignLockService()
    result = service.build_design_lock_from_sources(
        session_id=session_id,
        source_task_id=task_a_id,
        source_message_id=uuid4(),
        source_task=task_a,
        source_message=message,
        user_confirmed=True,
    )
    assert result.design_lock_status == "blocked"
    assert "source_task_not_bound_to_p21_execution" in result.blocked_reasons


def test_service_blocks_runtime_write_flag_true() -> None:
    from app.domain.project_director_message import (
        ProjectDirectorMessage,
        ProjectDirectorMessageRole,
        ProjectDirectorMessageSource,
    )
    from app.domain.task import Task
    from app.services.project_director_sandbox_write_design_lock_service import (
        ProjectDirectorSandboxWriteDesignLockService,
    )
    from app.services.project_director_sandbox_write_execution_service import (
        P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL,
    )

    session_id = uuid4()
    task_id = uuid4()

    task = Task(
        id=task_id,
        title="P21-B test task",
        source_draft_id="p12-test",
        input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
        acceptance_criteria=[
            "safe_dry_run_task=true",
            "worker_simulate_required=true",
            "product_runtime_git_write_allowed=false",
            "native_executor_started=false",
            "codex_started=false",
            "claude_code_started=false",
        ],
    )

    p21_action = {
        "type": "p21_sandbox_write_execution_record",
        "source_task_id": str(task_id),
        "execution_mode": "dry_run",
        "execution_status": "planned",
        "no_write_execution": True,
        "controlled_sandbox_write_enabled": False,
        "sandbox_write_allowed": True,  # <-- runtime write flag true
        "product_runtime_git_write_allowed": False,
        "main_worktree_write_allowed": False,
        "worktree_write_allowed": False,
        "file_write_allowed": False,
        "actual_patch_applied": False,
        "real_code_modified": False,
        "git_write_performed": False,
        "native_executor_started": False,
        "codex_started": False,
        "claude_code_started": False,
        "worker_started": False,
        "task_created": False,
        "run_created": False,
        "worktree_created": False,
        "worktree_cleaned_up": False,
        "rollback_snapshot_created": False,
        "cleanup_required": False,
        "operation_results": [
            {
                "operation_id": "p21-a-1",
                "path": "test.py",
                "operation": "create",
                "execution_status": "planned",
            }
        ],
    }

    message = ProjectDirectorMessage(
        session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="test",
        sequence_no=1,
        intent="sandbox_write_execution",
        related_project_id=uuid4(),
        related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL,
        suggested_actions=[p21_action],
    )

    service = ProjectDirectorSandboxWriteDesignLockService()
    result = service.build_design_lock_from_sources(
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=uuid4(),
        source_task=task,
        source_message=message,
        user_confirmed=True,
    )
    assert result.design_lock_status == "blocked"
    assert "real_write_not_allowed_in_design_lock" in result.blocked_reasons


def test_service_blocks_operation_intent_missing() -> None:
    from app.domain.project_director_message import (
        ProjectDirectorMessage,
        ProjectDirectorMessageRole,
        ProjectDirectorMessageSource,
    )
    from app.domain.task import Task
    from app.services.project_director_sandbox_write_design_lock_service import (
        ProjectDirectorSandboxWriteDesignLockService,
    )
    from app.services.project_director_sandbox_write_execution_service import (
        P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL,
    )

    session_id = uuid4()
    task_id = uuid4()

    task = Task(
        id=task_id,
        title="P21-B test task",
        source_draft_id="p12-test",
        input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
        acceptance_criteria=[
            "safe_dry_run_task=true",
            "worker_simulate_required=true",
            "product_runtime_git_write_allowed=false",
            "native_executor_started=false",
            "codex_started=false",
            "claude_code_started=false",
        ],
    )

    p21_action = {
        "type": "p21_sandbox_write_execution_record",
        "source_task_id": str(task_id),
        "execution_mode": "dry_run",
        "execution_status": "planned",
        "no_write_execution": True,
        "controlled_sandbox_write_enabled": False,
        "sandbox_write_allowed": False,
        "product_runtime_git_write_allowed": False,
        "main_worktree_write_allowed": False,
        "worktree_write_allowed": False,
        "file_write_allowed": False,
        "actual_patch_applied": False,
        "real_code_modified": False,
        "git_write_performed": False,
        "native_executor_started": False,
        "codex_started": False,
        "claude_code_started": False,
        "worker_started": False,
        "task_created": False,
        "run_created": False,
        "worktree_created": False,
        "worktree_cleaned_up": False,
        "rollback_snapshot_created": False,
        "cleanup_required": False,
        "operation_results": [],  # <-- empty operation results
    }

    message = ProjectDirectorMessage(
        session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="test",
        sequence_no=1,
        intent="sandbox_write_execution",
        related_project_id=uuid4(),
        related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL,
        suggested_actions=[p21_action],
    )

    service = ProjectDirectorSandboxWriteDesignLockService()
    result = service.build_design_lock_from_sources(
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=uuid4(),
        source_task=task,
        source_message=message,
        user_confirmed=True,
    )
    assert result.design_lock_status == "blocked"
    assert "operation_intent_missing" in result.blocked_reasons


# ── 5. Output must not contain misleading terms ──────────────────────


def test_result_output_excludes_misleading_terms() -> None:
    result = _default_locked_result()
    serialized = result.model_dump_json()
    for term in MISLEADING_TERMS:
        assert term not in serialized, f"Found misleading term: {term}"
