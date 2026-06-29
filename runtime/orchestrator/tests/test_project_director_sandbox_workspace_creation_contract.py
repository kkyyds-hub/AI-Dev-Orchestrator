"""Contract tests for P21-C-C controlled sandbox workspace creation."""

from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_sandbox_workspace_creation import (
    ProjectDirectorSandboxWorkspaceCreationResult,
)
from app.domain.task import Task
from app.services.project_director_sandbox_workspace_creation_service import (
    P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL,
    ProjectDirectorSandboxWorkspaceCreationService,
)
from app.services.project_director_sandbox_operation_manifest_guard_service import (
    P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL,
)


# ── Constants ────────────────────────────────────────────────────────

SIDE_EFFECT_FLAGS = [
    "workspace_written",
    "file_written",
    "manifest_file_written",
    "target_file_content_read",
    "real_diff_generated",
    "patch_applied",
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
]

MISLEADING_TERMS = {
    "已写入业务文件",
    "已写入 manifest 文件",
    "已读取目标文件",
    "已生成 diff",
    "已应用 patch",
    "已创建 git worktree",
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
        title="P21-C-C test task",
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


def _manifest_guard_action(
    task_id,
    *,
    source_message_id=None,
    workspace_path_preview,
    workspace_path_within_root=True,
):
    return {
        "type": "p21_c_sandbox_operation_manifest_guard_record",
        "source_task_id": str(task_id),
        "source_message_id": str(source_message_id) if source_message_id else None,
        "manifest_status": "manifested",
        "operation_manifest_created": True,
        "manifest_operations_count": 1,
        "manifest_allowed_operations_count": 1,
        "manifest_blocked_operations_count": 0,
        "workspace_path_preview": workspace_path_preview,
        "workspace_path_within_root": workspace_path_within_root,
        "workspace_created": False,
        "workspace_written": False,
        "file_written": False,
        "target_file_content_read": False,
        "real_diff_generated": False,
        "patch_applied": False,
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
# 1. Successful created result
# ══════════════════════════════════════════════════════════════════════


class TestSuccessfulCreatedResult:
    def test_created_result_fields(self, tmp_path) -> None:
        workspace_dir = tmp_path / "sandbox" / "ws-test"
        workspace_dir.mkdir(parents=True)

        result = ProjectDirectorSandboxWorkspaceCreationResult(
            creation_status="created",
            session_id=uuid4(),
            workspace_path=str(workspace_dir),
            workspace_path_within_root=True,
            workspace_root=str(tmp_path / "sandbox"),
            workspace_created=True,
            cleanup_required=True,
            cleanup_hint="cleanup required",
            creation_summary="workspace created",
            recommended_next_step="next",
        )
        assert result.creation_status == "created"
        assert result.workspace_created is True
        assert result.workspace_already_existed is False
        assert result.workspace_path_within_root is True
        assert result.cleanup_required is True
        assert result.cleanup_hint != ""
        assert result.workspace_written is False
        assert result.file_written is False
        assert result.manifest_file_written is False
        assert result.target_file_content_read is False
        assert result.real_diff_generated is False
        assert result.patch_applied is False
        assert result.ai_project_director_total_loop == "Partial"
        for flag in SIDE_EFFECT_FLAGS:
            assert getattr(result, flag) is False, f"{flag} should be False"


# ══════════════════════════════════════════════════════════════════════
# 2. Already exists result
# ══════════════════════════════════════════════════════════════════════


class TestAlreadyExistsResult:
    def test_already_exists_result_fields(self, tmp_path) -> None:
        workspace_dir = tmp_path / "sandbox" / "ws-test"
        workspace_dir.mkdir(parents=True)

        result = ProjectDirectorSandboxWorkspaceCreationResult(
            creation_status="already_exists",
            session_id=uuid4(),
            workspace_path=str(workspace_dir),
            workspace_path_within_root=True,
            workspace_root=str(tmp_path / "sandbox"),
            workspace_already_existed=True,
            cleanup_required=False,
            cleanup_hint="no cleanup needed",
            creation_summary="already existed",
            recommended_next_step="next",
        )
        assert result.creation_status == "already_exists"
        assert result.workspace_created is False
        assert result.workspace_already_existed is True
        assert result.cleanup_required is False
        assert "not modified" in result.cleanup_hint or "already existed" in result.cleanup_hint or "no cleanup" in result.cleanup_hint


# ══════════════════════════════════════════════════════════════════════
# 3. Domain validator rejects true side-effect flags
# ══════════════════════════════════════════════════════════════════════


class TestDomainValidatorRejectsTrueFlags:
    @pytest.mark.parametrize("field_name", SIDE_EFFECT_FLAGS)
    def test_rejects_true_flag(self, field_name: str) -> None:
        with pytest.raises(ValidationError, match="may only create the workspace directory"):
            ProjectDirectorSandboxWorkspaceCreationResult(
                creation_status="created",
                session_id=uuid4(),
                creation_summary="test",
                recommended_next_step="next",
                **{field_name: True},
            )


# ══════════════════════════════════════════════════════════════════════
# 4. Source validation
# ══════════════════════════════════════════════════════════════════════


class TestSourceValidation:
    def test_user_confirmed_false_blocked(self) -> None:
        service = ProjectDirectorSandboxWorkspaceCreationService()
        result = service.build_workspace_creation_from_sources(
            session_id=uuid4(),
            source_task_id=uuid4(),
            source_message_id=uuid4(),
            source_task=None,
            source_message=None,
            user_confirmed=False,
        )
        assert result.creation_status == "blocked"
        assert "user_confirmation_required" in result.blocked_reasons

    def test_source_task_missing_blocked(self) -> None:
        service = ProjectDirectorSandboxWorkspaceCreationService()
        result = service.build_workspace_creation_from_sources(
            session_id=uuid4(),
            source_task_id=uuid4(),
            source_message_id=uuid4(),
            source_task=None,
            source_message=None,
            user_confirmed=True,
        )
        assert result.creation_status == "blocked"
        assert "source_task_missing" in result.blocked_reasons

    def test_source_task_not_safe_dry_run_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        bad_task = Task(
            id=task_id,
            title="Not safe",
            source_draft_id="bad",
            input_summary="not safe",
            acceptance_criteria=[],
        )
        service = ProjectDirectorSandboxWorkspaceCreationService()
        result = service.build_workspace_creation_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=bad_task,
            source_message=None,
            user_confirmed=True,
        )
        assert result.creation_status == "blocked"
        assert "source_task_not_safe_dry_run" in result.blocked_reasons

    def test_source_message_missing_blocked(self) -> None:
        service = ProjectDirectorSandboxWorkspaceCreationService()
        result = service.build_workspace_creation_from_sources(
            session_id=uuid4(),
            source_task_id=uuid4(),
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(),
            source_message=None,
            user_confirmed=True,
        )
        assert result.creation_status == "blocked"
        assert "source_message_missing" in result.blocked_reasons

    def test_non_manifest_source_detail_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        msg = _make_message(
            session_id, task_id, "p21_c_sandbox_workspace_guard",
            {"type": "p21_c_sandbox_workspace_guard_record"},
        )
        service = ProjectDirectorSandboxWorkspaceCreationService()
        result = service.build_workspace_creation_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.creation_status == "blocked"
        assert "source_message_is_not_p21_c_operation_manifest_guard" in result.blocked_reasons

    def test_missing_manifest_action_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL,
            {"type": "wrong_type"},
        )
        service = ProjectDirectorSandboxWorkspaceCreationService()
        result = service.build_workspace_creation_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.creation_status == "blocked"
        assert "p21_c_operation_manifest_guard_record_missing" in result.blocked_reasons

    def test_manifest_not_manifested_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        ws = Path(tempfile.mkdtemp(prefix="p21c-c-test-")).resolve(strict=False)
        action = _manifest_guard_action(task_id, workspace_path_preview=str(ws))
        action["manifest_status"] = "blocked"
        action["operation_manifest_created"] = False
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceCreationService()
        result = service.build_workspace_creation_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.creation_status == "blocked"
        assert "source_manifest_not_manifested" in result.blocked_reasons

    def test_manifest_allowed_count_zero_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        ws = Path(tempfile.mkdtemp(prefix="p21c-c-test-")).resolve(strict=False)
        action = _manifest_guard_action(task_id, workspace_path_preview=str(ws))
        action["manifest_allowed_operations_count"] = 0
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceCreationService()
        result = service.build_workspace_creation_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.creation_status == "blocked"
        assert "source_manifest_not_manifested" in result.blocked_reasons

    def test_source_task_mismatch_blocked(self) -> None:
        session_id = uuid4()
        task_a_id = uuid4()
        task_b_id = uuid4()
        ws = Path(tempfile.mkdtemp(prefix="p21c-c-test-")).resolve(strict=False)
        action = _manifest_guard_action(task_b_id, workspace_path_preview=str(ws))
        msg = _make_message(
            session_id, task_b_id, P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceCreationService()
        result = service.build_workspace_creation_from_sources(
            session_id=session_id,
            source_task_id=task_a_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_a_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.creation_status == "blocked"
        assert "source_task_not_bound_to_manifest_guard" in result.blocked_reasons

    def test_manifest_no_write_flag_violated_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        ws = Path(tempfile.mkdtemp(prefix="p21c-c-test-")).resolve(strict=False)
        action = _manifest_guard_action(task_id, workspace_path_preview=str(ws))
        action["workspace_written"] = True
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceCreationService()
        result = service.build_workspace_creation_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.creation_status == "blocked"
        assert "source_manifest_not_no_write" in result.blocked_reasons

    def test_total_loop_not_partial_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        ws = Path(tempfile.mkdtemp(prefix="p21c-c-test-")).resolve(strict=False)
        action = _manifest_guard_action(task_id, workspace_path_preview=str(ws))
        action["ai_project_director_total_loop"] = "Full"
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceCreationService()
        result = service.build_workspace_creation_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.creation_status == "blocked"
        assert "source_manifest_not_no_write" in result.blocked_reasons

    def test_workspace_path_preview_missing_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _manifest_guard_action(task_id, workspace_path_preview="")
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceCreationService()
        result = service.build_workspace_creation_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.creation_status == "blocked"
        assert "workspace_path_preview_missing" in result.blocked_reasons

    def test_workspace_path_outside_root_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _manifest_guard_action(
            task_id,
            workspace_path_preview="/tmp/outside-root/ws",
            workspace_path_within_root=False,
        )
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceCreationService()
        result = service.build_workspace_creation_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.creation_status == "blocked"
        assert "workspace_path_not_within_root" in result.blocked_reasons

    def test_workspace_path_existing_non_directory_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        # Use the actual sandbox root so the path passes root containment
        from app.core.config import settings
        ws_root = settings.runtime_data_dir / "project-director" / "sandbox-workspaces"
        ws_root.mkdir(parents=True, exist_ok=True)
        non_dir = ws_root / "not-a-dir-file"
        non_dir.write_text("I am a file")

        action = _manifest_guard_action(task_id, workspace_path_preview=str(non_dir))
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceCreationService()
        result = service.build_workspace_creation_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.creation_status == "blocked"
        assert "workspace_path_is_not_directory" in result.blocked_reasons
        non_dir.unlink(missing_ok=True)

    def test_session_id_mismatch_blocked(self) -> None:
        session_id = uuid4()
        other_session_id = uuid4()
        task_id = uuid4()
        ws = Path(tempfile.mkdtemp(prefix="p21c-c-test-")).resolve(strict=False)
        action = _manifest_guard_action(task_id, workspace_path_preview=str(ws))
        msg = _make_message(
            other_session_id, task_id, P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceCreationService()
        result = service.build_workspace_creation_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.creation_status == "blocked"
        assert "source_message_is_not_p21_c_operation_manifest_guard" in result.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# 5. Output must not contain misleading terms
# ══════════════════════════════════════════════════════════════════════


class TestOutputNoMisleadingTerms:
    def test_result_output_excludes_misleading_terms(self) -> None:
        result = ProjectDirectorSandboxWorkspaceCreationResult(
            creation_status="blocked",
            session_id=uuid4(),
            creation_summary="blocked",
            recommended_next_step="next",
        )
        serialized = result.model_dump_json()
        for term in MISLEADING_TERMS:
            assert term not in serialized, f"Found misleading term: {term}"


# ══════════════════════════════════════════════════════════════════════
# 6. Service mkdir behavior (tested via API to use proper sandbox root)
# ══════════════════════════════════════════════════════════════════════

# NOTE: Actual mkdir behavior (created/already_exists/parent creation)
# is tested via the API integration tests which use the proper sandbox root
# under isolated runtime data. Service-level tests above verify all
# validation and blocking logic.
