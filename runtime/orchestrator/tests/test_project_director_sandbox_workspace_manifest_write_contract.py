"""Contract tests for P21-C-D controlled sandbox workspace evidence manifest write."""

from __future__ import annotations

import json
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
from app.domain.project_director_sandbox_workspace_manifest_write import (
    ProjectDirectorSandboxWorkspaceManifestWriteResult,
)
from app.domain.task import Task
from app.services.project_director_sandbox_workspace_creation_service import (
    P21_C_SANDBOX_WORKSPACE_CREATE_ACTION_TYPE,
    P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_workspace_manifest_write_service import (
    ProjectDirectorSandboxWorkspaceManifestWriteService,
)


SIDE_EFFECT_FLAGS = [
    "business_file_written",
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


def _safe_dry_run_task(task_id=None) -> Task:
    return Task(
        id=task_id or uuid4(),
        title="P21-C-D test task",
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


def _workspace_creation_action(
    task_id,
    *,
    workspace_path,
    workspace_created=True,
    workspace_already_existed=False,
    creation_status="created",
    cleanup_required=False,
):
    return {
        "type": P21_C_SANDBOX_WORKSPACE_CREATE_ACTION_TYPE,
        "source_task_id": str(task_id),
        "creation_status": creation_status,
        "workspace_path": workspace_path,
        "workspace_path_within_root": True,
        "workspace_created": workspace_created,
        "workspace_already_existed": workspace_already_existed,
        "workspace_written": False,
        "file_written": False,
        "manifest_file_written": False,
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
        "cleanup_required": cleanup_required,
        "cleanup_hint": "test cleanup hint",
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
# 1. Successful written result
# ══════════════════════════════════════════════════════════════════════


class TestSuccessfulWrittenResult:
    def test_written_result_fields(self, tmp_path) -> None:
        workspace_dir = tmp_path / "sandbox" / "ws-test"
        workspace_dir.mkdir(parents=True)

        result = ProjectDirectorSandboxWorkspaceManifestWriteResult(
            manifest_write_status="written",
            session_id=uuid4(),
            workspace_path=str(workspace_dir),
            workspace_path_within_root=True,
            workspace_root=str(tmp_path / "sandbox"),
            manifest_dir_path=str(workspace_dir / ".ai-project-director"),
            manifest_file_path=str(workspace_dir / ".ai-project-director" / "workspace-manifest.json"),
            manifest_dir_created=True,
            manifest_file_written=True,
            manifest_file_overwritten=False,
            cleanup_required=False,
            cleanup_hint="test hint",
            manifest_write_summary="written",
            recommended_next_step="next",
        )
        assert result.manifest_write_status == "written"
        assert result.manifest_file_written is True
        assert result.manifest_file_overwritten is False
        assert result.business_file_written is False
        assert result.target_file_content_read is False
        assert result.real_diff_generated is False
        assert result.patch_applied is False
        assert result.workspace_path_within_root is True
        assert result.cleanup_hint != ""
        assert result.ai_project_director_total_loop == "Partial"
        for flag in SIDE_EFFECT_FLAGS:
            assert getattr(result, flag) is False, f"{flag} should be False"


# ══════════════════════════════════════════════════════════════════════
# 2. Overwritten result
# ══════════════════════════════════════════════════════════════════════


class TestOverwrittenResult:
    def test_overwritten_result_fields(self, tmp_path) -> None:
        workspace_dir = tmp_path / "sandbox" / "ws-test"
        workspace_dir.mkdir(parents=True)

        result = ProjectDirectorSandboxWorkspaceManifestWriteResult(
            manifest_write_status="overwritten",
            session_id=uuid4(),
            workspace_path=str(workspace_dir),
            workspace_path_within_root=True,
            workspace_root=str(tmp_path / "sandbox"),
            manifest_dir_path=str(workspace_dir / ".ai-project-director"),
            manifest_file_path=str(workspace_dir / ".ai-project-director" / "workspace-manifest.json"),
            manifest_file_written=True,
            manifest_file_overwritten=True,
            cleanup_required=False,
            cleanup_hint="test hint",
            manifest_write_summary="overwritten",
            recommended_next_step="next",
        )
        assert result.manifest_write_status == "overwritten"
        assert result.manifest_file_written is True
        assert result.manifest_file_overwritten is True


# ══════════════════════════════════════════════════════════════════════
# 3. Domain validator rejects true side-effect flags
# ══════════════════════════════════════════════════════════════════════


class TestDomainValidatorRejectsTrueFlags:
    @pytest.mark.parametrize("field_name", SIDE_EFFECT_FLAGS)
    def test_rejects_true_flag(self, field_name: str) -> None:
        with pytest.raises(ValidationError, match="may only write the internal manifest"):
            ProjectDirectorSandboxWorkspaceManifestWriteResult(
                manifest_write_status="written",
                session_id=uuid4(),
                manifest_write_summary="test",
                recommended_next_step="next",
                **{field_name: True},
            )


# ══════════════════════════════════════════════════════════════════════
# 4. Source validation
# ══════════════════════════════════════════════════════════════════════


class TestSourceValidation:
    def test_user_confirmed_false_blocked(self) -> None:
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        result = service.build_workspace_manifest_write_from_sources(
            session_id=uuid4(),
            source_task_id=uuid4(),
            source_message_id=uuid4(),
            source_task=None,
            source_message=None,
            user_confirmed=False,
        )
        assert result.manifest_write_status == "blocked"
        assert "user_confirmation_required" in result.blocked_reasons

    def test_source_task_missing_blocked(self) -> None:
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        result = service.build_workspace_manifest_write_from_sources(
            session_id=uuid4(),
            source_task_id=uuid4(),
            source_message_id=uuid4(),
            source_task=None,
            source_message=None,
            user_confirmed=True,
        )
        assert result.manifest_write_status == "blocked"
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
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        result = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=bad_task,
            source_message=None,
            user_confirmed=True,
        )
        assert result.manifest_write_status == "blocked"
        assert "source_task_not_safe_dry_run" in result.blocked_reasons

    def test_source_message_missing_blocked(self) -> None:
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        result = service.build_workspace_manifest_write_from_sources(
            session_id=uuid4(),
            source_task_id=uuid4(),
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(),
            source_message=None,
            user_confirmed=True,
        )
        assert result.manifest_write_status == "blocked"
        assert "source_message_missing" in result.blocked_reasons

    def test_non_p21_c_c_source_detail_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        msg = _make_message(
            session_id, task_id, "p21_c_sandbox_workspace_guard",
            {"type": "p21_c_sandbox_workspace_guard_record"},
        )
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        result = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_write_status == "blocked"
        assert "source_message_is_not_p21_c_workspace_created" in result.blocked_reasons

    def test_missing_workspace_create_action_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL,
            {"type": "wrong_type"},
        )
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        result = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_write_status == "blocked"
        assert "p21_c_workspace_create_record_missing" in result.blocked_reasons

    def test_creation_status_not_created_or_existing_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        ws = Path(tempfile.mkdtemp(prefix="p21c-d-test-")).resolve(strict=False)
        action = _workspace_creation_action(task_id, workspace_path=str(ws))
        action["creation_status"] = "blocked"
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        result = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_write_status == "blocked"
        assert "source_workspace_creation_not_created_or_existing" in result.blocked_reasons

    def test_workspace_created_false_and_already_existed_false_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        ws = Path(tempfile.mkdtemp(prefix="p21c-d-test-")).resolve(strict=False)
        action = _workspace_creation_action(task_id, workspace_path=str(ws))
        action["workspace_created"] = False
        action["workspace_already_existed"] = False
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        result = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_write_status == "blocked"

    def test_source_task_mismatch_blocked(self) -> None:
        session_id = uuid4()
        task_a_id = uuid4()
        task_b_id = uuid4()
        ws = Path(tempfile.mkdtemp(prefix="p21c-d-test-")).resolve(strict=False)
        action = _workspace_creation_action(task_b_id, workspace_path=str(ws))
        msg = _make_message(
            session_id, task_b_id, P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        result = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_a_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_a_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_write_status == "blocked"
        assert "source_task_not_bound_to_workspace_creation" in result.blocked_reasons

    def test_source_workspace_creation_no_write_flag_violated_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        ws = Path(tempfile.mkdtemp(prefix="p21c-d-test-")).resolve(strict=False)
        action = _workspace_creation_action(task_id, workspace_path=str(ws))
        action["workspace_written"] = True
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        result = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_write_status == "blocked"
        assert "source_workspace_creation_not_no_write" in result.blocked_reasons

    def test_total_loop_not_partial_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        ws = Path(tempfile.mkdtemp(prefix="p21c-d-test-")).resolve(strict=False)
        action = _workspace_creation_action(task_id, workspace_path=str(ws))
        action["ai_project_director_total_loop"] = "Full"
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        result = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_write_status == "blocked"
        assert "source_workspace_creation_not_no_write" in result.blocked_reasons

    def test_workspace_path_missing_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _workspace_creation_action(task_id, workspace_path="")
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        result = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_write_status == "blocked"
        assert "workspace_path_missing" in result.blocked_reasons

    def test_workspace_path_outside_root_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _workspace_creation_action(
            task_id, workspace_path="/tmp/outside-root/ws",
        )
        action["workspace_path_within_root"] = False
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        result = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_write_status == "blocked"
        assert "workspace_path_not_within_root" in result.blocked_reasons

    def test_workspace_path_missing_on_disk_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        fake_path = Path(tempfile.mkdtemp(prefix="p21c-d-test-")) / "nonexistent"
        action = _workspace_creation_action(task_id, workspace_path=str(fake_path))
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        result = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_write_status == "blocked"
        assert "workspace_path_missing_on_disk" in result.blocked_reasons

    def test_workspace_path_existing_non_directory_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        non_dir = Path(tempfile.mkdtemp(prefix="p21c-d-test-")) / "not-a-dir"
        non_dir.write_text("I am a file")
        action = _workspace_creation_action(task_id, workspace_path=str(non_dir))
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        result = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_write_status == "blocked"
        assert "workspace_path_is_not_directory" in result.blocked_reasons

    def test_manifest_dir_existing_as_non_directory_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        from app.core.config import settings
        ws_root = settings.runtime_data_dir / "project-director" / "sandbox-workspaces"
        ws_root.mkdir(parents=True, exist_ok=True)
        ws = ws_root / f"test-manifest-dir-{uuid4().hex[:8]}"
        ws.mkdir(parents=True, exist_ok=True)
        manifest_dir = ws / ".ai-project-director"
        manifest_dir.write_text("I am a file, not a dir")
        action = _workspace_creation_action(task_id, workspace_path=str(ws))
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        result = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_write_status == "blocked"
        assert "manifest_dir_create_failed" in result.blocked_reasons

    def test_invalid_write_mode_blocked_at_service_level(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        with pytest.raises((ValidationError, ValueError)):
            service.build_workspace_manifest_write_from_sources(
                session_id=session_id,
                source_task_id=task_id,
                source_message_id=uuid4(),
                source_task=_safe_dry_run_task(task_id),
                source_message=None,
                user_confirmed=True,
                write_mode="invalid_mode",
            )

    def test_session_id_mismatch_blocked(self) -> None:
        session_id = uuid4()
        other_session_id = uuid4()
        task_id = uuid4()
        ws = Path(tempfile.mkdtemp(prefix="p21c-d-test-")).resolve(strict=False)
        action = _workspace_creation_action(task_id, workspace_path=str(ws))
        msg = _make_message(
            other_session_id, task_id, P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        result = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_write_status == "blocked"
        assert "source_message_is_not_p21_c_workspace_created" in result.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# 5. Strict workspace path (workspace_path equals sandbox root)
# ══════════════════════════════════════════════════════════════════════


class TestWorkspacePathEqualsSandboxRoot:
    def test_workspace_path_equals_root_is_blocked(self, tmp_path) -> None:
        """R1: workspace_path equal to sandbox root must be blocked."""
        session_id = uuid4()
        task_id = uuid4()
        from app.core.config import settings
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws_root.mkdir(parents=True, exist_ok=True)
        action = _workspace_creation_action(task_id, workspace_path=str(ws_root))
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        result = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_write_status == "blocked"
        assert "workspace_path_must_be_workspace_subdirectory" in result.blocked_reasons
        assert result.manifest_file_written is False
        assert result.business_file_written is False

    def test_workspace_path_strict_subdirectory_still_written(self) -> None:
        """R1: workspace_path as strict child of sandbox root still succeeds."""
        session_id = uuid4()
        task_id = uuid4()
        from app.core.config import settings
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws_root.mkdir(parents=True, exist_ok=True)
        ws = ws_root / f"pd-test-{uuid4().hex[:8]}"
        ws.mkdir(parents=True, exist_ok=True)
        action = _workspace_creation_action(task_id, workspace_path=str(ws))
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        result = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_write_status == "written"
        assert result.manifest_file_written is True
        assert result.manifest_file_path is not None
        assert result.manifest_file_path.endswith(".ai-project-director/workspace-manifest.json")


# ══════════════════════════════════════════════════════════════════════
# 6. Manifest JSON content tests
# ══════════════════════════════════════════════════════════════════════


class TestManifestJsonContent:
    def test_manifest_json_content_valid(self, tmp_path) -> None:
        session_id = uuid4()
        task_id = uuid4()
        from app.core.config import settings
        ws_root = settings.runtime_data_dir / "project-director" / "sandbox-workspaces"
        ws_root.mkdir(parents=True, exist_ok=True)
        ws = ws_root / f"test-json-{uuid4().hex[:8]}"
        ws.mkdir(parents=True, exist_ok=True)
        action = _workspace_creation_action(task_id, workspace_path=str(ws))
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        result = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_write_status == "written"
        assert result.manifest_file_path is not None

        manifest_path = Path(result.manifest_file_path)
        assert manifest_path.exists()
        raw = manifest_path.read_text(encoding="utf-8")
        data = json.loads(raw)

        assert data["schema_version"] == "p21-c-d.v1"
        assert data["session_id"] == str(session_id)
        assert data["source_task_id"] == str(task_id)
        assert data["workspace_path"] is not None
        assert data["workspace_root"] is not None
        assert data["source_workspace_creation_status"] is not None
        assert data["manifest_file_path"] == result.manifest_file_path
        assert data["internal_manifest_only"] is True
        assert data["business_file_write_allowed"] is False
        assert data["target_file_content_read"] is False
        assert data["real_diff_generated"] is False
        assert data["patch_applied"] is False
        assert data["worktree_created"] is False
        assert data["git_write_performed"] is False
        assert data["worker_started"] is False
        assert data["task_created"] is False
        assert data["run_created"] is False
        assert data["ai_project_director_total_loop"] == "Partial"
        assert "allowed_next_steps" in data
        assert "forbidden_actions" in data

    def test_manifest_json_no_secrets(self, tmp_path) -> None:
        session_id = uuid4()
        task_id = uuid4()
        from app.core.config import settings
        ws_root = settings.runtime_data_dir / "project-director" / "sandbox-workspaces"
        ws_root.mkdir(parents=True, exist_ok=True)
        ws = ws_root / f"test-json-{uuid4().hex[:8]}"
        ws.mkdir(parents=True, exist_ok=True)
        action = _workspace_creation_action(task_id, workspace_path=str(ws))
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        result = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_write_status == "written"
        manifest_path = Path(result.manifest_file_path)
        raw = manifest_path.read_text(encoding="utf-8")
        data = json.loads(raw)

        secret_keys = ["key", "token", "base_url", "api_key", "secret"]
        for k in secret_keys:
            assert k not in data, f"Manifest JSON should not contain key '{k}'"
        assert data.get("target_file_content_read") is not True

    def test_manifest_file_path_equals_fixed_path(self, tmp_path) -> None:
        session_id = uuid4()
        task_id = uuid4()
        from app.core.config import settings
        ws_root = settings.runtime_data_dir / "project-director" / "sandbox-workspaces"
        ws_root.mkdir(parents=True, exist_ok=True)
        ws = ws_root / f"test-json-{uuid4().hex[:8]}"
        ws.mkdir(parents=True, exist_ok=True)
        action = _workspace_creation_action(task_id, workspace_path=str(ws))
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        result = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert result.manifest_write_status == "written"
        expected_suffix = ".ai-project-director/workspace-manifest.json"
        assert result.manifest_file_path.endswith(expected_suffix)


# ══════════════════════════════════════════════════════════════════════
# 7. Overwrite behavior
# ══════════════════════════════════════════════════════════════════════


class TestOverwriteBehavior:
    def test_second_write_overwrites_same_file(self, tmp_path) -> None:
        session_id = uuid4()
        task_id = uuid4()
        source_message_id = uuid4()
        from app.core.config import settings
        ws_root = settings.runtime_data_dir / "project-director" / "sandbox-workspaces"
        ws_root.mkdir(parents=True, exist_ok=True)
        ws = ws_root / f"test-ow-{uuid4().hex[:8]}"
        ws.mkdir(parents=True, exist_ok=True)
        action = _workspace_creation_action(task_id, workspace_path=str(ws))
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()

        r1 = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=source_message_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert r1.manifest_write_status == "written"
        assert r1.manifest_file_overwritten is False

        r2 = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=source_message_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert r2.manifest_write_status == "overwritten"
        assert r2.manifest_file_overwritten is True
        assert r2.manifest_file_path == r1.manifest_file_path

    def test_overwrite_only_manifest_file(self, tmp_path) -> None:
        session_id = uuid4()
        task_id = uuid4()
        from app.core.config import settings
        ws_root = settings.runtime_data_dir / "project-director" / "sandbox-workspaces"
        ws_root.mkdir(parents=True, exist_ok=True)
        ws = ws_root / f"test-ow-{uuid4().hex[:8]}"
        ws.mkdir(parents=True, exist_ok=True)
        action = _workspace_creation_action(task_id, workspace_path=str(ws))
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxWorkspaceManifestWriteService()
        r1 = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert r1.manifest_write_status == "written"

        r2 = service.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
        )
        assert r2.manifest_write_status == "overwritten"

        manifest_dir = Path(r2.manifest_file_path).parent
        all_files = list(manifest_dir.iterdir())
        assert len(all_files) == 1
        assert all_files[0].name == "workspace-manifest.json"


# ══════════════════════════════════════════════════════════════════════
# 8. Output must not contain misleading terms
# ══════════════════════════════════════════════════════════════════════


class TestOutputNoMisleadingTerms:
    def test_result_output_excludes_misleading_terms(self) -> None:
        result = ProjectDirectorSandboxWorkspaceManifestWriteResult(
            manifest_write_status="blocked",
            session_id=uuid4(),
            manifest_write_summary="blocked",
            recommended_next_step="next",
        )
        serialized = result.model_dump_json()
        for term in MISLEADING_TERMS:
            assert term not in serialized, f"Found misleading term: {term}"
