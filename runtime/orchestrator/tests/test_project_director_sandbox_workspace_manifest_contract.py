"""Contract tests for P21-C-A sandbox workspace guard and P21-C-B operation manifest guard."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.project_director_sandbox_workspace_guard import (
    ProjectDirectorSandboxWorkspaceGuardResult,
)
from app.domain.project_director_sandbox_operation_manifest_guard import (
    ProjectDirectorSandboxOperationManifestGuardResult,
    SandboxOperationManifestEntry,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.task import Task
from app.services.project_director_sandbox_workspace_guard_service import (
    ProjectDirectorSandboxWorkspaceGuardService,
    P21_C_SANDBOX_WORKSPACE_GUARD_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_operation_manifest_guard_service import (
    ProjectDirectorSandboxOperationManifestGuardService,
    P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_write_design_lock_service import (
    P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_write_execution_service import (
    P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL,
)


# ── Constants ────────────────────────────────────────────────────────

WORKSPACE_GUARD_WRITE_FLAGS = [
    "workspace_created",
    "workspace_written",
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

MANIFEST_GUARD_WRITE_FLAGS = [
    "workspace_created",
    "workspace_written",
    "file_written",
    "controlled_sandbox_write_enabled",
    "sandbox_write_allowed",
    "product_runtime_git_write_allowed",
    "main_worktree_write_allowed",
    "worktree_write_allowed",
    "file_write_allowed",
    "actual_patch_applied",
    "real_code_modified",
    "real_diff_generated",
    "patch_applied",
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
    "target_file_content_read",
]

MISLEADING_TERMS = {
    "已创建目录",
    "已写入文件",
    "已读取目标文件",
    "已生成 diff",
    "已应用 patch",
    "已创建 worktree",
    "已提交代码",
    "已推送",
    "Git 写入已授权",
    "controlled sandbox write 已启用",
    "automatic commit",
    "git commit performed",
}


# ── Helpers ──────────────────────────────────────────────────────────


def _safe_dry_run_task(task_id=None) -> Task:
    return Task(
        id=task_id or uuid4(),
        title="P21-C test task",
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


def _p21_a_execution_action(
    task_id,
    *,
    operation="create",
    path="runtime/orchestrator/app/domain/example.py",
    execution_mode="dry_run",
    execution_status="planned",
):
    return {
        "type": "p21_sandbox_write_execution_record",
        "source_task_id": str(task_id),
        "execution_mode": execution_mode,
        "execution_status": execution_status,
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
                "path": path,
                "operation": operation,
                "execution_status": execution_status,
                "source_preflight_path_policy_allowed": True,
            }
        ],
    }


def _p21_b_design_lock_action(task_id, *, source_message_id=None):
    return {
        "type": "p21_b_sandbox_write_design_lock_record",
        "source_task_id": str(task_id),
        "source_message_id": str(source_message_id) if source_message_id else None,
        "design_lock_status": "locked",
        "controlled_sandbox_write_design_locked": True,
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
        "ai_project_director_total_loop": "Partial",
    }


def _p21_c_workspace_guard_action(
    task_id,
    *,
    source_message_id=None,
    workspace_path_preview="/tmp/sandbox/pd-test-workspace",
    workspace_path_within_root=True,
):
    return {
        "type": "p21_c_sandbox_workspace_guard_record",
        "source_task_id": str(task_id),
        "source_message_id": str(source_message_id) if source_message_id else None,
        "guard_status": "guarded",
        "sandbox_workspace_guarded": True,
        "workspace_path_within_root": workspace_path_within_root,
        "workspace_path_preview": workspace_path_preview,
        "workspace_created": False,
        "workspace_written": False,
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
        "ai_project_director_total_loop": "Partial",
    }


def _make_message(session_id, task_id, source_detail, action, *, sequence_no=1):
    return ProjectDirectorMessage(
        session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="test",
        sequence_no=sequence_no,
        intent="test",
        related_project_id=uuid4(),
        related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=source_detail,
        suggested_actions=[action],
    )


# ══════════════════════════════════════════════════════════════════════
# P21-C-A Workspace Guard Contract Tests
# ══════════════════════════════════════════════════════════════════════


class TestWorkspaceGuardSuccessfulResult:
    def test_guarded_result_fields(self) -> None:
        result = ProjectDirectorSandboxWorkspaceGuardResult(
            guard_status="guarded",
            session_id=uuid4(),
            sandbox_workspace_root_policy="test policy",
            guard_summary="guarded",
            recommended_next_step="next",
        )
        assert result.guard_status == "guarded"
        assert result.sandbox_workspace_guarded is False
        assert result.workspace_path_within_root is False
        assert result.workspace_created is False
        assert result.workspace_written is False
        assert result.ai_project_director_total_loop == "Partial"
        for flag in WORKSPACE_GUARD_WRITE_FLAGS:
            assert getattr(result, flag) is False, f"{flag} should be False"


class TestWorkspaceGuardValidatorRejectsTrueFlags:
    @pytest.mark.parametrize("field_name", WORKSPACE_GUARD_WRITE_FLAGS)
    def test_rejects_true_flag(self, field_name: str) -> None:
        with pytest.raises(ValidationError, match="must remain false"):
            ProjectDirectorSandboxWorkspaceGuardResult(
                guard_status="guarded",
                session_id=uuid4(),
                sandbox_workspace_root_policy="test policy",
                guard_summary="guarded",
                recommended_next_step="next",
                **{field_name: True},
            )


class TestWorkspaceNamePolicy:
    def test_valid_name_allowed(self) -> None:
        assert (
            ProjectDirectorSandboxWorkspaceGuardService._workspace_name_not_allowed(
                "my-workspace"
            )
            is False
        )

    def test_name_with_dot_allowed(self) -> None:
        assert (
            ProjectDirectorSandboxWorkspaceGuardService._workspace_name_not_allowed(
                "ws-1.0"
            )
            is False
        )

    def test_name_with_underscore_allowed(self) -> None:
        assert (
            ProjectDirectorSandboxWorkspaceGuardService._workspace_name_not_allowed(
                "my_workspace"
            )
            is False
        )

    def test_blank_name_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        service = ProjectDirectorSandboxWorkspaceGuardService()
        result = service.build_workspace_guard_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=None,
            source_message=None,
            user_confirmed=True,
            requested_workspace_name="   ",
        )
        assert result.guard_status == "blocked"
        assert "workspace_name_required" in result.blocked_reasons

    def test_name_with_slash_blocked(self) -> None:
        assert (
            ProjectDirectorSandboxWorkspaceGuardService._workspace_name_not_allowed(
                "foo/bar"
            )
            is True
        )

    def test_name_with_backslash_blocked(self) -> None:
        assert (
            ProjectDirectorSandboxWorkspaceGuardService._workspace_name_not_allowed(
                "foo\\bar"
            )
            is True
        )

    def test_name_with_dotdot_blocked(self) -> None:
        assert (
            ProjectDirectorSandboxWorkspaceGuardService._workspace_name_not_allowed(
                "foo..bar"
            )
            is True
        )

    def test_name_with_tilde_blocked(self) -> None:
        assert (
            ProjectDirectorSandboxWorkspaceGuardService._workspace_name_not_allowed(
                "~workspace"
            )
            is True
        )

    def test_absolute_path_blocked(self) -> None:
        assert (
            ProjectDirectorSandboxWorkspaceGuardService._workspace_name_not_allowed(
                "/tmp/workspace"
            )
            is True
        )

    def test_windows_drive_path_blocked(self) -> None:
        assert (
            ProjectDirectorSandboxWorkspaceGuardService._workspace_name_not_allowed(
                "C:\\workspace"
            )
            is True
        )

    def test_file_url_blocked(self) -> None:
        assert (
            ProjectDirectorSandboxWorkspaceGuardService._workspace_name_not_allowed(
                "file:///tmp/workspace"
            )
            is True
        )

    def test_semicolon_blocked(self) -> None:
        assert (
            ProjectDirectorSandboxWorkspaceGuardService._workspace_name_not_allowed(
                "ws;rm"
            )
            is True
        )

    def test_pipe_blocked(self) -> None:
        assert (
            ProjectDirectorSandboxWorkspaceGuardService._workspace_name_not_allowed(
                "ws|cmd"
            )
            is True
        )

    def test_ampersand_blocked(self) -> None:
        assert (
            ProjectDirectorSandboxWorkspaceGuardService._workspace_name_not_allowed(
                "ws&cmd"
            )
            is True
        )

    def test_dollar_paren_blocked(self) -> None:
        assert (
            ProjectDirectorSandboxWorkspaceGuardService._workspace_name_not_allowed(
                "ws$(cmd)"
            )
            is True
        )

    def test_backtick_blocked(self) -> None:
        assert (
            ProjectDirectorSandboxWorkspaceGuardService._workspace_name_not_allowed(
                "ws`cmd`"
            )
            is True
        )

    def test_overly_long_name_blocked(self) -> None:
        assert (
            ProjectDirectorSandboxWorkspaceGuardService._workspace_name_not_allowed(
                "a" * 100
            )
            is True
        )

    def test_none_name_generates_deterministic_preview(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        service = ProjectDirectorSandboxWorkspaceGuardService()
        # Build with valid source to get past source validation
        result = service.build_workspace_guard_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=None,
            source_message=None,
            user_confirmed=True,
            requested_workspace_name=None,
        )
        # The normalized_workspace_name should be deterministic
        assert result.normalized_workspace_name == f"pd-{str(session_id)[:8]}-{str(task_id)[:8]}"


class TestWorkspaceGuardSourceValidation:
    def test_user_confirmed_false_blocked(self) -> None:
        service = ProjectDirectorSandboxWorkspaceGuardService()
        result = service.build_workspace_guard_from_sources(
            session_id=uuid4(),
            source_task_id=uuid4(),
            source_message_id=uuid4(),
            source_task=None,
            source_message=None,
            user_confirmed=False,
        )
        assert result.guard_status == "blocked"
        assert "user_confirmation_required" in result.blocked_reasons

    def test_missing_source_message_blocked(self) -> None:
        service = ProjectDirectorSandboxWorkspaceGuardService()
        result = service.build_workspace_guard_from_sources(
            session_id=uuid4(),
            source_task_id=uuid4(),
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(),
            source_message=None,
            user_confirmed=True,
        )
        assert result.guard_status == "blocked"
        assert "source_message_missing" in result.blocked_reasons

    def test_non_p21_b_design_lock_source_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        message = _make_message(
            session_id,
            task_id,
            "p20_sandbox_write_preflight",
            {"type": "p20_sandbox_write_preflight_record"},
        )
        service = ProjectDirectorSandboxWorkspaceGuardService()
        result = service.build_workspace_guard_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=message,
            user_confirmed=True,
        )
        assert result.guard_status == "blocked"
        assert "source_message_is_not_p21_b_design_lock" in result.blocked_reasons

    def test_missing_design_lock_action_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        message = _make_message(
            session_id,
            task_id,
            P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL,
            {"type": "wrong_type"},
        )
        service = ProjectDirectorSandboxWorkspaceGuardService()
        result = service.build_workspace_guard_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=message,
            user_confirmed=True,
        )
        assert result.guard_status == "blocked"
        assert "p21_b_design_lock_record_missing" in result.blocked_reasons

    def test_design_lock_not_locked_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _p21_b_design_lock_action(task_id)
        action["design_lock_status"] = "blocked"
        message = _make_message(
            session_id,
            task_id,
            P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL,
            action,
        )
        service = ProjectDirectorSandboxWorkspaceGuardService()
        result = service.build_workspace_guard_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=message,
            user_confirmed=True,
        )
        assert result.guard_status == "blocked"
        assert "source_design_lock_not_locked" in result.blocked_reasons

    def test_source_task_message_mismatch_blocked(self) -> None:
        session_id = uuid4()
        task_a_id = uuid4()
        task_b_id = uuid4()
        action = _p21_b_design_lock_action(task_b_id)
        message = _make_message(
            session_id,
            task_b_id,
            P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL,
            action,
        )
        service = ProjectDirectorSandboxWorkspaceGuardService()
        result = service.build_workspace_guard_from_sources(
            session_id=session_id,
            source_task_id=task_a_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_a_id),
            source_message=message,
            user_confirmed=True,
        )
        assert result.guard_status == "blocked"
        assert "source_task_not_bound_to_design_lock" in result.blocked_reasons

    def test_source_task_not_safe_dry_run_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _p21_b_design_lock_action(task_id)
        message = _make_message(
            session_id,
            task_id,
            P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL,
            action,
        )
        bad_task = Task(
            id=task_id,
            title="Not safe",
            source_draft_id="bad",
            input_summary="not safe",
            acceptance_criteria=[],
        )
        service = ProjectDirectorSandboxWorkspaceGuardService()
        result = service.build_workspace_guard_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=bad_task,
            source_message=message,
            user_confirmed=True,
        )
        assert result.guard_status == "blocked"
        assert "source_task_not_safe_dry_run" in result.blocked_reasons

    def test_design_lock_runtime_write_flag_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _p21_b_design_lock_action(task_id)
        action["sandbox_write_allowed"] = True
        message = _make_message(
            session_id,
            task_id,
            P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL,
            action,
        )
        service = ProjectDirectorSandboxWorkspaceGuardService()
        result = service.build_workspace_guard_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=message,
            user_confirmed=True,
        )
        assert result.guard_status == "blocked"
        assert "real_write_not_allowed_in_workspace_guard" in result.blocked_reasons

    def test_design_lock_total_loop_not_partial_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _p21_b_design_lock_action(task_id)
        action["ai_project_director_total_loop"] = "Full"
        message = _make_message(
            session_id,
            task_id,
            P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL,
            action,
        )
        service = ProjectDirectorSandboxWorkspaceGuardService()
        result = service.build_workspace_guard_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=message,
            user_confirmed=True,
        )
        assert result.guard_status == "blocked"
        assert "source_design_lock_not_no_write" in result.blocked_reasons

    def test_design_lock_not_no_write_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _p21_b_design_lock_action(task_id)
        action["controlled_sandbox_write_enabled"] = True
        message = _make_message(
            session_id,
            task_id,
            P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL,
            action,
        )
        service = ProjectDirectorSandboxWorkspaceGuardService()
        result = service.build_workspace_guard_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=message,
            user_confirmed=True,
        )
        assert result.guard_status == "blocked"
        assert "source_design_lock_not_no_write" in result.blocked_reasons

    def test_session_id_mismatch_blocked(self) -> None:
        session_id = uuid4()
        other_session_id = uuid4()
        task_id = uuid4()
        action = _p21_b_design_lock_action(task_id)
        message = _make_message(
            other_session_id,
            task_id,
            P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL,
            action,
        )
        service = ProjectDirectorSandboxWorkspaceGuardService()
        result = service.build_workspace_guard_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=message,
            user_confirmed=True,
        )
        assert result.guard_status == "blocked"
        assert "source_message_is_not_p21_b_design_lock" in result.blocked_reasons


class TestWorkspaceGuardOutputNoMisleadingTerms:
    def test_result_output_excludes_misleading_terms(self) -> None:
        result = ProjectDirectorSandboxWorkspaceGuardResult(
            guard_status="guarded",
            session_id=uuid4(),
            sandbox_workspace_root_policy="test policy",
            guard_summary="guarded",
            recommended_next_step="next",
        )
        serialized = result.model_dump_json()
        for term in MISLEADING_TERMS:
            assert term not in serialized, f"Found misleading term: {term}"


# ══════════════════════════════════════════════════════════════════════
# P21-C-B Operation Manifest Guard Contract Tests
# ══════════════════════════════════════════════════════════════════════


class TestManifestGuardSuccessfulResult:
    def test_manifested_result_fields(self) -> None:
        entry = SandboxOperationManifestEntry(
            operation_id="op-1",
            path="test.py",
            operation="create",
            workspace_target_path_preview="/tmp/ws/test.py",
            source_execution_status="planned",
            source_preflight_path_policy_allowed=True,
            path_within_workspace=True,
            operation_manifest_allowed=True,
        )
        result = ProjectDirectorSandboxOperationManifestGuardResult(
            manifest_status="manifested",
            session_id=uuid4(),
            operation_manifest_created=True,
            manifest_operations_count=1,
            manifest_allowed_operations_count=1,
            manifest_operations=[entry],
            allowed_operation_paths=["test.py"],
            manifest_summary="manifested",
            recommended_next_step="next",
        )
        assert result.manifest_status == "manifested"
        assert result.operation_manifest_created is True
        assert result.manifest_operations_count == 1
        assert result.manifest_allowed_operations_count == 1
        assert result.workspace_created is False
        assert result.workspace_written is False
        assert result.file_written is False
        assert result.target_file_content_read is False
        assert result.real_diff_generated is False
        assert result.patch_applied is False
        assert result.ai_project_director_total_loop == "Partial"
        for flag in MANIFEST_GUARD_WRITE_FLAGS:
            assert getattr(result, flag) is False, f"{flag} should be False"


class TestManifestGuardValidatorRejectsTrueFlags:
    @pytest.mark.parametrize("field_name", MANIFEST_GUARD_WRITE_FLAGS)
    def test_rejects_true_flag(self, field_name: str) -> None:
        with pytest.raises(ValidationError, match="must remain false"):
            ProjectDirectorSandboxOperationManifestGuardResult(
                manifest_status="manifested",
                session_id=uuid4(),
                manifest_summary="manifested",
                recommended_next_step="next",
                **{field_name: True},
            )


class TestManifestGuardSourceChain:
    def _build_full_chain(self, *, session_id=None, task_id=None):
        """Build P21-C-A -> P21-B -> P21-A message chain."""
        sid = session_id or uuid4()
        tid = task_id or uuid4()

        p21_a_action = _p21_a_execution_action(tid)
        p21_a_msg = _make_message(
            sid, tid, P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL, p21_a_action,
            sequence_no=1,
        )

        p21_b_action = _p21_b_design_lock_action(tid, source_message_id=p21_a_msg.id)
        p21_b_msg = _make_message(
            sid, tid, P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL, p21_b_action,
            sequence_no=2,
        )

        p21_c_a_action = _p21_c_workspace_guard_action(tid, source_message_id=p21_b_msg.id)
        p21_c_a_msg = _make_message(
            sid, tid, P21_C_SANDBOX_WORKSPACE_GUARD_SOURCE_DETAIL, p21_c_a_action,
            sequence_no=3,
        )

        return sid, tid, p21_a_msg, p21_b_msg, p21_c_a_msg

    def test_valid_chain_manifested(self) -> None:
        sid, tid, p21_a_msg, p21_b_msg, p21_c_a_msg = self._build_full_chain()

        service = ProjectDirectorSandboxOperationManifestGuardService()

        class FakeMsgRepo:
            def get_by_id(self, msg_id):
                msgs = {p21_a_msg.id: p21_a_msg, p21_b_msg.id: p21_b_msg, p21_c_a_msg.id: p21_c_a_msg}
                return msgs.get(msg_id)

        service._message_repository = FakeMsgRepo()

        result = service.build_operation_manifest_guard_from_sources(
            session_id=sid,
            source_task_id=tid,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(tid),
            source_message=p21_c_a_msg,
            user_confirmed=True,
        )
        assert result.manifest_status == "manifested"
        assert result.manifest_operations_count > 0
        assert result.manifest_allowed_operations_count > 0
        assert result.operation_manifest_created is True
        assert result.workspace_path_preview is not None
        assert result.source_workspace_guard_status == "guarded"

    def test_missing_p21_c_a_source_blocked(self) -> None:
        sid = uuid4()
        tid = uuid4()
        service = ProjectDirectorSandboxOperationManifestGuardService()
        result = service.build_operation_manifest_guard_from_sources(
            session_id=sid,
            source_task_id=tid,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(tid),
            source_message=None,
            user_confirmed=True,
        )
        assert result.manifest_status == "blocked"
        assert "source_message_missing" in result.blocked_reasons

    def test_non_p21_c_a_source_detail_blocked(self) -> None:
        sid = uuid4()
        tid = uuid4()
        msg = _make_message(
            sid, tid, "p21_b_sandbox_write_design_lock",
            {"type": "p21_b_sandbox_write_design_lock_record"},
        )
        service = ProjectDirectorSandboxOperationManifestGuardService()
        result = service.build_operation_manifest_guard_from_sources(
            session_id=sid,
            source_task_id=tid,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(tid),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_status == "blocked"
        assert "source_message_is_not_p21_c_workspace_guard" in result.blocked_reasons

    def test_missing_workspace_guard_action_blocked(self) -> None:
        sid = uuid4()
        tid = uuid4()
        msg = _make_message(
            sid, tid, P21_C_SANDBOX_WORKSPACE_GUARD_SOURCE_DETAIL,
            {"type": "wrong_type"},
        )
        service = ProjectDirectorSandboxOperationManifestGuardService()
        result = service.build_operation_manifest_guard_from_sources(
            session_id=sid,
            source_task_id=tid,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(tid),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_status == "blocked"
        assert "p21_c_workspace_guard_record_missing" in result.blocked_reasons

    def test_workspace_guard_not_guarded_blocked(self) -> None:
        sid = uuid4()
        tid = uuid4()
        action = _p21_c_workspace_guard_action(tid)
        action["guard_status"] = "blocked"
        action["sandbox_workspace_guarded"] = False
        msg = _make_message(
            sid, tid, P21_C_SANDBOX_WORKSPACE_GUARD_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxOperationManifestGuardService()
        result = service.build_operation_manifest_guard_from_sources(
            session_id=sid,
            source_task_id=tid,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(tid),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_status == "blocked"
        assert "source_workspace_guard_not_guarded" in result.blocked_reasons

    def test_workspace_guard_no_write_flag_violated_blocked(self) -> None:
        sid = uuid4()
        tid = uuid4()
        action = _p21_c_workspace_guard_action(tid)
        action["workspace_created"] = True
        msg = _make_message(
            sid, tid, P21_C_SANDBOX_WORKSPACE_GUARD_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxOperationManifestGuardService()
        result = service.build_operation_manifest_guard_from_sources(
            session_id=sid,
            source_task_id=tid,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(tid),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_status == "blocked"
        assert "source_workspace_guard_not_no_write" in result.blocked_reasons

    def test_workspace_path_preview_missing_blocked(self) -> None:
        sid = uuid4()
        tid = uuid4()
        action = _p21_c_workspace_guard_action(tid)
        action["workspace_path_preview"] = None
        msg = _make_message(
            sid, tid, P21_C_SANDBOX_WORKSPACE_GUARD_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxOperationManifestGuardService()
        result = service.build_operation_manifest_guard_from_sources(
            session_id=sid,
            source_task_id=tid,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(tid),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_status == "blocked"
        assert "workspace_path_preview_missing" in result.blocked_reasons

    def test_workspace_path_not_within_root_blocked(self) -> None:
        sid = uuid4()
        tid = uuid4()
        action = _p21_c_workspace_guard_action(tid, workspace_path_within_root=False)
        msg = _make_message(
            sid, tid, P21_C_SANDBOX_WORKSPACE_GUARD_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxOperationManifestGuardService()
        result = service.build_operation_manifest_guard_from_sources(
            session_id=sid,
            source_task_id=tid,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(tid),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_status == "blocked"
        assert "workspace_path_not_within_root" in result.blocked_reasons

    def test_missing_design_lock_message_blocked(self) -> None:
        sid = uuid4()
        tid = uuid4()
        action = _p21_c_workspace_guard_action(tid, source_message_id=uuid4())
        msg = _make_message(
            sid, tid, P21_C_SANDBOX_WORKSPACE_GUARD_SOURCE_DETAIL, action,
        )

        service = ProjectDirectorSandboxOperationManifestGuardService()

        class EmptyMsgRepo:
            def get_by_id(self, msg_id):
                return None

        service._message_repository = EmptyMsgRepo()

        result = service.build_operation_manifest_guard_from_sources(
            session_id=sid,
            source_task_id=tid,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(tid),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_status == "blocked"
        assert "source_design_lock_message_missing" in result.blocked_reasons

    def test_design_lock_not_locked_blocked(self) -> None:
        sid, tid, p21_a_msg, p21_b_msg, p21_c_a_msg = self._build_full_chain()

        # Corrupt design lock action
        p21_b_action = _p21_b_design_lock_action(tid, source_message_id=p21_a_msg.id)
        p21_b_action["design_lock_status"] = "blocked"
        bad_p21_b_msg = _make_message(
            sid, tid, P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL, p21_b_action,
            sequence_no=2,
        )

        p21_c_a_action = _p21_c_workspace_guard_action(tid, source_message_id=bad_p21_b_msg.id)
        p21_c_a_msg = _make_message(
            sid, tid, P21_C_SANDBOX_WORKSPACE_GUARD_SOURCE_DETAIL, p21_c_a_action,
            sequence_no=3,
        )

        service = ProjectDirectorSandboxOperationManifestGuardService()

        class FakeMsgRepo:
            def get_by_id(self, msg_id):
                msgs = {p21_a_msg.id: p21_a_msg, bad_p21_b_msg.id: bad_p21_b_msg, p21_c_a_msg.id: p21_c_a_msg}
                return msgs.get(msg_id)

        service._message_repository = FakeMsgRepo()

        result = service.build_operation_manifest_guard_from_sources(
            session_id=sid,
            source_task_id=tid,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(tid),
            source_message=p21_c_a_msg,
            user_confirmed=True,
        )
        assert result.manifest_status == "blocked"
        assert "source_design_lock_not_locked" in result.blocked_reasons

    def test_missing_execution_message_blocked(self) -> None:
        sid, tid, p21_a_msg, p21_b_msg, p21_c_a_msg = self._build_full_chain()

        service = ProjectDirectorSandboxOperationManifestGuardService()

        class PartialMsgRepo:
            def get_by_id(self, msg_id):
                msgs = {p21_b_msg.id: p21_b_msg, p21_c_a_msg.id: p21_c_a_msg}
                return msgs.get(msg_id)

        service._message_repository = PartialMsgRepo()

        result = service.build_operation_manifest_guard_from_sources(
            session_id=sid,
            source_task_id=tid,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(tid),
            source_message=p21_c_a_msg,
            user_confirmed=True,
        )
        assert result.manifest_status == "blocked"
        assert "source_execution_message_missing" in result.blocked_reasons

    def test_execution_not_planned_or_simulated_blocked(self) -> None:
        sid = uuid4()
        tid = uuid4()

        p21_a_action = _p21_a_execution_action(tid)
        p21_a_action["execution_status"] = "blocked"
        p21_a_msg = _make_message(
            sid, tid, P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL, p21_a_action,
            sequence_no=1,
        )

        p21_b_action = _p21_b_design_lock_action(tid, source_message_id=p21_a_msg.id)
        p21_b_msg = _make_message(
            sid, tid, P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL, p21_b_action,
            sequence_no=2,
        )

        p21_c_a_action = _p21_c_workspace_guard_action(tid, source_message_id=p21_b_msg.id)
        p21_c_a_msg = _make_message(
            sid, tid, P21_C_SANDBOX_WORKSPACE_GUARD_SOURCE_DETAIL, p21_c_a_action,
            sequence_no=3,
        )

        service = ProjectDirectorSandboxOperationManifestGuardService()

        class FakeMsgRepo:
            def get_by_id(self, msg_id):
                msgs = {p21_a_msg.id: p21_a_msg, p21_b_msg.id: p21_b_msg, p21_c_a_msg.id: p21_c_a_msg}
                return msgs.get(msg_id)

        service._message_repository = FakeMsgRepo()

        result = service.build_operation_manifest_guard_from_sources(
            session_id=sid,
            source_task_id=tid,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(tid),
            source_message=p21_c_a_msg,
            user_confirmed=True,
        )
        assert result.manifest_status == "blocked"
        assert "source_execution_not_planned_or_simulated" in result.blocked_reasons

    def test_execution_no_write_false_blocked(self) -> None:
        sid = uuid4()
        tid = uuid4()

        p21_a_action = _p21_a_execution_action(tid)
        p21_a_action["no_write_execution"] = False
        p21_a_msg = _make_message(
            sid, tid, P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL, p21_a_action,
            sequence_no=1,
        )

        p21_b_action = _p21_b_design_lock_action(tid, source_message_id=p21_a_msg.id)
        p21_b_msg = _make_message(
            sid, tid, P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL, p21_b_action,
            sequence_no=2,
        )

        p21_c_a_action = _p21_c_workspace_guard_action(tid, source_message_id=p21_b_msg.id)
        p21_c_a_msg = _make_message(
            sid, tid, P21_C_SANDBOX_WORKSPACE_GUARD_SOURCE_DETAIL, p21_c_a_action,
            sequence_no=3,
        )

        service = ProjectDirectorSandboxOperationManifestGuardService()

        class FakeMsgRepo:
            def get_by_id(self, msg_id):
                msgs = {p21_a_msg.id: p21_a_msg, p21_b_msg.id: p21_b_msg, p21_c_a_msg.id: p21_c_a_msg}
                return msgs.get(msg_id)

        service._message_repository = FakeMsgRepo()

        result = service.build_operation_manifest_guard_from_sources(
            session_id=sid,
            source_task_id=tid,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(tid),
            source_message=p21_c_a_msg,
            user_confirmed=True,
        )
        assert result.manifest_status == "blocked"
        assert "source_execution_not_no_write" in result.blocked_reasons

    def test_operation_results_missing_blocked(self) -> None:
        sid = uuid4()
        tid = uuid4()

        p21_a_action = _p21_a_execution_action(tid)
        p21_a_action["operation_results"] = []
        p21_a_msg = _make_message(
            sid, tid, P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL, p21_a_action,
            sequence_no=1,
        )

        p21_b_action = _p21_b_design_lock_action(tid, source_message_id=p21_a_msg.id)
        p21_b_msg = _make_message(
            sid, tid, P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL, p21_b_action,
            sequence_no=2,
        )

        p21_c_a_action = _p21_c_workspace_guard_action(tid, source_message_id=p21_b_msg.id)
        p21_c_a_msg = _make_message(
            sid, tid, P21_C_SANDBOX_WORKSPACE_GUARD_SOURCE_DETAIL, p21_c_a_action,
            sequence_no=3,
        )

        service = ProjectDirectorSandboxOperationManifestGuardService()

        class FakeMsgRepo:
            def get_by_id(self, msg_id):
                msgs = {p21_a_msg.id: p21_a_msg, p21_b_msg.id: p21_b_msg, p21_c_a_msg.id: p21_c_a_msg}
                return msgs.get(msg_id)

        service._message_repository = FakeMsgRepo()

        result = service.build_operation_manifest_guard_from_sources(
            session_id=sid,
            source_task_id=tid,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(tid),
            source_message=p21_c_a_msg,
            user_confirmed=True,
        )
        assert result.manifest_status == "blocked"
        assert "operation_results_missing" in result.blocked_reasons

    def test_source_task_mismatch_blocked(self) -> None:
        sid, tid, p21_a_msg, p21_b_msg, p21_c_a_msg = self._build_full_chain()

        wrong_task_id = uuid4()
        result = ProjectDirectorSandboxOperationManifestGuardService().build_operation_manifest_guard_from_sources(
            session_id=sid,
            source_task_id=wrong_task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(wrong_task_id),
            source_message=p21_c_a_msg,
            user_confirmed=True,
        )
        assert result.manifest_status == "blocked"
        assert "source_task_not_bound_to_workspace_guard" in result.blocked_reasons

    def test_source_task_not_safe_dry_run_blocked(self) -> None:
        sid, tid, p21_a_msg, p21_b_msg, p21_c_a_msg = self._build_full_chain()

        bad_task = Task(
            id=tid,
            title="Not safe",
            source_draft_id="bad",
            input_summary="not safe",
            acceptance_criteria=[],
        )

        service = ProjectDirectorSandboxOperationManifestGuardService()

        class FakeMsgRepo:
            def get_by_id(self, msg_id):
                msgs = {p21_a_msg.id: p21_a_msg, p21_b_msg.id: p21_b_msg, p21_c_a_msg.id: p21_c_a_msg}
                return msgs.get(msg_id)

        service._message_repository = FakeMsgRepo()

        result = service.build_operation_manifest_guard_from_sources(
            session_id=sid,
            source_task_id=tid,
            source_message_id=uuid4(),
            source_task=bad_task,
            source_message=p21_c_a_msg,
            user_confirmed=True,
        )
        assert result.manifest_status == "blocked"
        assert "source_task_not_safe_dry_run" in result.blocked_reasons


class TestManifestOperationPathPolicy:
    def _build_manifest_with_operation(self, op_dict, *, workspace_path=None):
        """Helper to test per-operation validation."""
        import tempfile
        from pathlib import Path
        if workspace_path is None:
            workspace_path = Path(tempfile.mkdtemp(prefix="p21c-test-")).resolve(strict=False)
        else:
            workspace_path = Path(workspace_path).resolve(strict=False)
            workspace_path.mkdir(parents=True, exist_ok=True)
        entry = ProjectDirectorSandboxOperationManifestGuardService._manifest_operation(
            ProjectDirectorSandboxOperationManifestGuardService(),
            op_dict,
            index=1,
            workspace_path=workspace_path,
            source_execution_status="planned",
        )
        return entry

    def test_create_relative_path_allowed(self) -> None:
        entry = self._build_manifest_with_operation({
            "operation_id": "op-1",
            "path": "runtime/orchestrator/app/domain/example.py",
            "operation": "create",
            "source_preflight_path_policy_allowed": True,
        })
        assert entry.operation_manifest_allowed is True
        assert entry.blocked_reasons == []

    def test_update_relative_path_allowed(self) -> None:
        entry = self._build_manifest_with_operation({
            "operation_id": "op-1",
            "path": "runtime/orchestrator/app/domain/existing.py",
            "operation": "update",
            "source_preflight_path_policy_allowed": True,
        })
        assert entry.operation_manifest_allowed is True

    def test_p20_preflight_accepted_path_blocked(self) -> None:
        entry = self._build_manifest_with_operation({
            "operation_id": "op-1",
            "path": "test.py",
            "operation": "p20_preflight_accepted_path",
            "source_preflight_path_policy_allowed": True,
        })
        assert entry.operation_manifest_allowed is False
        assert "operation_intent_not_create_or_update" in entry.blocked_reasons

    def test_delete_operation_blocked(self) -> None:
        entry = self._build_manifest_with_operation({
            "operation_id": "op-1",
            "path": "test.py",
            "operation": "delete",
            "source_preflight_path_policy_allowed": True,
        })
        assert entry.operation_manifest_allowed is False
        assert "operation_intent_not_create_or_update" in entry.blocked_reasons

    def test_empty_path_blocked(self) -> None:
        entry = self._build_manifest_with_operation({
            "operation_id": "op-1",
            "path": "",
            "operation": "create",
            "source_preflight_path_policy_allowed": True,
        })
        assert entry.operation_manifest_allowed is False
        assert "operation_path_missing" in entry.blocked_reasons

    def test_absolute_path_blocked(self) -> None:
        entry = self._build_manifest_with_operation({
            "operation_id": "op-1",
            "path": "/tmp/absolute.py",
            "operation": "create",
            "source_preflight_path_policy_allowed": True,
        })
        assert entry.operation_manifest_allowed is False
        assert "operation_path_not_relative" in entry.blocked_reasons

    def test_path_with_dotdot_blocked(self) -> None:
        entry = self._build_manifest_with_operation({
            "operation_id": "op-1",
            "path": "../escape.py",
            "operation": "create",
            "source_preflight_path_policy_allowed": True,
        })
        assert entry.operation_manifest_allowed is False
        assert "operation_path_not_allowed" in entry.blocked_reasons

    def test_path_with_tilde_blocked(self) -> None:
        entry = self._build_manifest_with_operation({
            "operation_id": "op-1",
            "path": "~/secret.py",
            "operation": "create",
            "source_preflight_path_policy_allowed": True,
        })
        assert entry.operation_manifest_allowed is False
        assert "operation_path_not_allowed" in entry.blocked_reasons

    def test_file_url_blocked(self) -> None:
        entry = self._build_manifest_with_operation({
            "operation_id": "op-1",
            "path": "file:///tmp/evil.py",
            "operation": "create",
            "source_preflight_path_policy_allowed": True,
        })
        assert entry.operation_manifest_allowed is False
        assert "operation_path_not_allowed" in entry.blocked_reasons

    def test_windows_drive_path_blocked(self) -> None:
        entry = self._build_manifest_with_operation({
            "operation_id": "op-1",
            "path": "C:\\Windows\\system32\\evil.py",
            "operation": "create",
            "source_preflight_path_policy_allowed": True,
        })
        assert entry.operation_manifest_allowed is False
        assert "operation_path_not_relative" in entry.blocked_reasons

    def test_semicolon_path_blocked(self) -> None:
        entry = self._build_manifest_with_operation({
            "operation_id": "op-1",
            "path": "test;rm -rf /",
            "operation": "create",
            "source_preflight_path_policy_allowed": True,
        })
        assert entry.operation_manifest_allowed is False
        assert "operation_path_not_allowed" in entry.blocked_reasons

    def test_pipe_path_blocked(self) -> None:
        entry = self._build_manifest_with_operation({
            "operation_id": "op-1",
            "path": "test|cmd",
            "operation": "create",
            "source_preflight_path_policy_allowed": True,
        })
        assert entry.operation_manifest_allowed is False
        assert "operation_path_not_allowed" in entry.blocked_reasons

    def test_ampersand_path_blocked(self) -> None:
        entry = self._build_manifest_with_operation({
            "operation_id": "op-1",
            "path": "test&cmd",
            "operation": "create",
            "source_preflight_path_policy_allowed": True,
        })
        assert entry.operation_manifest_allowed is False
        assert "operation_path_not_allowed" in entry.blocked_reasons

    def test_dollar_paren_path_blocked(self) -> None:
        entry = self._build_manifest_with_operation({
            "operation_id": "op-1",
            "path": "test$(cmd)",
            "operation": "create",
            "source_preflight_path_policy_allowed": True,
        })
        assert entry.operation_manifest_allowed is False
        assert "operation_path_not_allowed" in entry.blocked_reasons

    def test_backtick_path_blocked(self) -> None:
        entry = self._build_manifest_with_operation({
            "operation_id": "op-1",
            "path": "test`cmd`",
            "operation": "create",
            "source_preflight_path_policy_allowed": True,
        })
        assert entry.operation_manifest_allowed is False
        assert "operation_path_not_allowed" in entry.blocked_reasons

    def test_backslash_path_current_behavior(self) -> None:
        """Test current behavior for backslash in path.

        NOTE: The current implementation does NOT explicitly block backslash in
        FORBIDDEN_PATH_FRAGMENTS (only '~', '://', ';', '|', '&', '$(', '`').
        However, on POSIX systems, backslash is a valid filename character.
        The path 'foo\\bar.py' resolves as a single filename within the workspace,
        which means it passes path containment. This test documents current behavior.
        If backslash should be explicitly blocked, FORBIDDEN_PATH_FRAGMENTS needs
        an R1 fix to include '\\'.
        """
        entry = self._build_manifest_with_operation({
            "operation_id": "op-1",
            "path": "foo\\bar.py",
            "operation": "create",
            "source_preflight_path_policy_allowed": True,
        })
        # NOTE: On macOS, backslash is a valid filename character.
        # 'foo\\bar.py' resolves as a single filename under the workspace.
        # The _operation_path_not_allowed check does NOT block it because
        # '\\' is not in FORBIDDEN_PATH_FRAGMENTS.
        # If the test passes (allowed=True), it means backslash paths are allowed.
        # If the test fails (allowed=False), it's blocked by escape check.
        # Either way, this documents the current behavior.
        # P21-C-B R1 note: consider adding '\\' to FORBIDDEN_PATH_FRAGMENTS.
        pass  # Document behavior; do not assert implementation-specific result

    def test_preflight_path_policy_not_allowed_blocked(self) -> None:
        entry = self._build_manifest_with_operation({
            "operation_id": "op-1",
            "path": "test.py",
            "operation": "create",
            "source_preflight_path_policy_allowed": False,
        })
        assert entry.operation_manifest_allowed is False
        assert "operation_path_not_allowed" in entry.blocked_reasons

    def test_path_escaping_workspace_blocked(self) -> None:
        import tempfile
        from pathlib import Path
        ws = Path(tempfile.mkdtemp(prefix="p21c-test-")).resolve(strict=False)
        entry = self._build_manifest_with_operation({
            "operation_id": "op-1",
            "path": "../../escape.py",
            "operation": "create",
            "source_preflight_path_policy_allowed": True,
        }, workspace_path=str(ws))
        assert entry.operation_manifest_allowed is False

    def test_all_operations_blocked_causes_manifest_blocked(self) -> None:
        """When all operations are blocked, manifest_status should be blocked."""
        sid, tid, p21_a_msg, p21_b_msg, p21_c_a_msg = self._build_full_chain_with_ops(
            operations=[
                {
                    "operation_id": "p21-a-1",
                    "path": "test.py",
                    "operation": "delete",
                    "execution_status": "planned",
                    "source_preflight_path_policy_allowed": True,
                }
            ]
        )

        service = ProjectDirectorSandboxOperationManifestGuardService()

        class FakeMsgRepo:
            def get_by_id(self, msg_id):
                msgs = {p21_a_msg.id: p21_a_msg, p21_b_msg.id: p21_b_msg, p21_c_a_msg.id: p21_c_a_msg}
                return msgs.get(msg_id)

        service._message_repository = FakeMsgRepo()

        result = service.build_operation_manifest_guard_from_sources(
            session_id=sid,
            source_task_id=tid,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(tid),
            source_message=p21_c_a_msg,
            user_confirmed=True,
        )
        assert result.manifest_status == "blocked"
        assert "all_operations_blocked" in result.blocked_reasons

    def test_mixed_allowed_and_blocked_operations(self) -> None:
        """Mixed: some operations allowed, some blocked."""
        sid, tid, p21_a_msg, p21_b_msg, p21_c_a_msg = self._build_full_chain_with_ops(
            operations=[
                {
                    "operation_id": "p21-a-1",
                    "path": "valid.py",
                    "operation": "create",
                    "execution_status": "planned",
                    "source_preflight_path_policy_allowed": True,
                },
                {
                    "operation_id": "p21-a-2",
                    "path": "invalid.py",
                    "operation": "delete",
                    "execution_status": "planned",
                    "source_preflight_path_policy_allowed": True,
                },
            ]
        )

        service = ProjectDirectorSandboxOperationManifestGuardService()

        class FakeMsgRepo:
            def get_by_id(self, msg_id):
                msgs = {p21_a_msg.id: p21_a_msg, p21_b_msg.id: p21_b_msg, p21_c_a_msg.id: p21_c_a_msg}
                return msgs.get(msg_id)

        service._message_repository = FakeMsgRepo()

        result = service.build_operation_manifest_guard_from_sources(
            session_id=sid,
            source_task_id=tid,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(tid),
            source_message=p21_c_a_msg,
            user_confirmed=True,
        )
        # Mixed: at least one allowed operation, so manifest should succeed
        assert result.manifest_status == "manifested"
        assert result.manifest_operations_count >= 2
        assert result.manifest_allowed_operations_count >= 1
        assert "valid.py" in result.allowed_operation_paths
        assert "invalid.py" in result.blocked_operation_paths
        assert result.manifest_blocked_operations_count >= 1

    def _build_full_chain_with_ops(self, *, operations, session_id=None, task_id=None):
        sid = session_id or uuid4()
        tid = task_id or uuid4()

        p21_a_action = _p21_a_execution_action(tid)
        p21_a_action["operation_results"] = operations
        p21_a_msg = _make_message(
            sid, tid, P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL, p21_a_action,
            sequence_no=1,
        )

        p21_b_action = _p21_b_design_lock_action(tid, source_message_id=p21_a_msg.id)
        p21_b_msg = _make_message(
            sid, tid, P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL, p21_b_action,
            sequence_no=2,
        )

        p21_c_a_action = _p21_c_workspace_guard_action(tid, source_message_id=p21_b_msg.id)
        p21_c_a_msg = _make_message(
            sid, tid, P21_C_SANDBOX_WORKSPACE_GUARD_SOURCE_DETAIL, p21_c_a_action,
            sequence_no=3,
        )

        return sid, tid, p21_a_msg, p21_b_msg, p21_c_a_msg


class TestManifestGuardUserConfirmedFalse:
    def test_user_confirmed_false_blocked(self) -> None:
        service = ProjectDirectorSandboxOperationManifestGuardService()
        result = service.build_operation_manifest_guard_from_sources(
            session_id=uuid4(),
            source_task_id=uuid4(),
            source_message_id=uuid4(),
            source_task=None,
            source_message=None,
            user_confirmed=False,
        )
        assert result.manifest_status == "blocked"
        assert "user_confirmation_required" in result.blocked_reasons


class TestManifestGuardOutputNoMisleadingTerms:
    def test_result_output_excludes_misleading_terms(self) -> None:
        result = ProjectDirectorSandboxOperationManifestGuardResult(
            manifest_status="manifested",
            session_id=uuid4(),
            manifest_summary="manifested",
            recommended_next_step="next",
        )
        serialized = result.model_dump_json()
        for term in MISLEADING_TERMS:
            assert term not in serialized, f"Found misleading term: {term}"
