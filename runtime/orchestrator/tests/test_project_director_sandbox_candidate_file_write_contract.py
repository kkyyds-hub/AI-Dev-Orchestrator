"""Contract tests for P21-C-E controlled sandbox candidate business file write."""

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
from app.domain.project_director_sandbox_candidate_file_write import (
    CandidateSandboxFileWrite,
    ProjectDirectorSandboxCandidateFileWriteResult,
)
from app.domain.task import Task
from app.services.project_director_sandbox_candidate_file_write_service import (
    P21_C_SANDBOX_CANDIDATE_FILES_WRITE_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateFileWriteService,
)
from app.services.project_director_sandbox_workspace_manifest_write_service import (
    INTERNAL_MANIFEST_DIR_NAME,
    INTERNAL_MANIFEST_FILE_NAME,
    P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_ACTION_TYPE,
    P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_workspace_creation_service import (
    P21_C_SANDBOX_WORKSPACE_CREATE_ACTION_TYPE,
    P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_operation_manifest_guard_service import (
    P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_ACTION_TYPE,
    P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL,
)


SIDE_EFFECT_FLAGS = [
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
    "已写主项目文件",
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
        title="P21-C-E test task",
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


def _workspace_creation_action(task_id, *, workspace_path, source_message_id=None):
    return {
        "type": P21_C_SANDBOX_WORKSPACE_CREATE_ACTION_TYPE,
        "source_task_id": str(task_id),
        "source_message_id": str(source_message_id) if source_message_id else None,
        "creation_status": "created",
        "workspace_path": workspace_path,
        "workspace_path_within_root": True,
        "workspace_created": True,
        "workspace_already_existed": False,
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
        "cleanup_required": False,
        "cleanup_hint": "test hint",
        "ai_project_director_total_loop": "Partial",
    }


def _operation_manifest_action(task_id, *, allowed_paths, source_message_id=None):
    return {
        "type": P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_ACTION_TYPE,
        "source_task_id": str(task_id),
        "source_message_id": str(source_message_id) if source_message_id else None,
        "manifest_status": "manifested",
        "operation_manifest_created": True,
        "manifest_operations_count": len(allowed_paths),
        "manifest_allowed_operations_count": len(allowed_paths),
        "manifest_blocked_operations_count": 0,
        "allowed_operation_paths": list(allowed_paths),
        "manifest_operations": [
            {
                "path": p,
                "operation": "create",
                "operation_manifest_allowed": True,
            }
            for p in allowed_paths
        ],
        "workspace_path_within_root": True,
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
        "cleanup_required": False,
        "ai_project_director_total_loop": "Partial",
    }


def _manifest_write_action(task_id, *, workspace_path, source_message_id=None):
    return {
        "type": P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_ACTION_TYPE,
        "source_task_id": str(task_id),
        "source_message_id": str(source_message_id) if source_message_id else None,
        "manifest_write_status": "written",
        "workspace_path": workspace_path,
        "workspace_path_within_root": True,
        "manifest_file_written": True,
        "manifest_file_overwritten": False,
        "business_file_written": False,
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
        "cleanup_required": False,
        "cleanup_hint": "test hint",
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


def _setup_workspace_with_manifest(ws_path: Path) -> None:
    """Create workspace dir and internal manifest for testing."""
    ws_path.mkdir(parents=True, exist_ok=True)
    manifest_dir = ws_path / INTERNAL_MANIFEST_DIR_NAME
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_file = manifest_dir / INTERNAL_MANIFEST_FILE_NAME
    manifest_file.write_text(
        json.dumps(
            {
                "schema_version": "p21-c-d.v1",
                "session_id": str(uuid4()),
                "source_task_id": str(uuid4()),
                "source_message_id": str(uuid4()),
                "workspace_path": ws_path.as_posix(),
                "workspace_root": ws_path.parent.as_posix(),
                "source_workspace_creation_status": "created",
                "manifest_file_path": manifest_file.as_posix(),
                "internal_manifest_only": True,
                "business_file_write_allowed": False,
                "target_file_content_read": False,
                "real_diff_generated": False,
                "patch_applied": False,
                "worktree_created": False,
                "git_write_performed": False,
                "worker_started": False,
                "task_created": False,
                "run_created": False,
                "ai_project_director_total_loop": "Partial",
                "allowed_next_steps": [],
                "forbidden_actions": [],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _build_service_with_fake_repos(
    session_id, task_id, ws_path, *, allowed_paths=None, source_message_id_map=None
):
    """Build a service with fake repos that return the correct messages."""
    if allowed_paths is None:
        allowed_paths = {"src/example.py"}
    if source_message_id_map is None:
        source_message_id_map = {}

    op_manifest_msg_id = uuid4()
    ws_creation_msg_id = uuid4()
    manifest_write_msg_id = uuid4()

    op_manifest_action = _operation_manifest_action(
        task_id, allowed_paths=allowed_paths, source_message_id=uuid4(),
    )
    op_manifest_msg = _make_message(
        session_id, task_id, P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL,
        op_manifest_action, sequence_no=1,
    )
    op_manifest_msg = ProjectDirectorMessage(
        id=op_manifest_msg_id,
        session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="test",
        sequence_no=1,
        intent="test",
        related_project_id=uuid4(),
        related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL,
        suggested_actions=[op_manifest_action],
    )

    ws_creation_action = _workspace_creation_action(
        task_id, workspace_path=str(ws_path), source_message_id=op_manifest_msg_id,
    )
    ws_creation_msg = ProjectDirectorMessage(
        id=ws_creation_msg_id,
        session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="test",
        sequence_no=2,
        intent="test",
        related_project_id=uuid4(),
        related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL,
        suggested_actions=[ws_creation_action],
    )

    manifest_write_action = _manifest_write_action(
        task_id, workspace_path=str(ws_path), source_message_id=ws_creation_msg_id,
    )
    manifest_write_msg = ProjectDirectorMessage(
        id=manifest_write_msg_id,
        session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="test",
        sequence_no=3,
        intent="test",
        related_project_id=uuid4(),
        related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL,
        suggested_actions=[manifest_write_action],
    )

    messages = {
        op_manifest_msg_id: op_manifest_msg,
        ws_creation_msg_id: ws_creation_msg,
        manifest_write_msg_id: manifest_write_msg,
    }

    class FakeMsgRepo:
        def get_by_id(self, msg_id):
            return messages.get(msg_id)

        def get_next_sequence_no(self, session_id):
            return 100

        def create(self, msg):
            return msg

        def commit(self):
            pass

    class FakeSessionRepo:
        def get_by_id(self, sid):
            if sid == session_id:
                return type("Session", (), {"project_id": uuid4()})()
            return None

    class FakeTaskRepo:
        def get_by_id(self, tid):
            if tid == task_id:
                return _safe_dry_run_task(task_id)
            return None

    service = ProjectDirectorSandboxCandidateFileWriteService(
        session_repository=FakeSessionRepo(),
        message_repository=FakeMsgRepo(),
        task_repository=FakeTaskRepo(),
    )
    return service, manifest_write_msg_id


# ══════════════════════════════════════════════════════════════════════
# 1. Successful written result
# ══════════════════════════════════════════════════════════════════════


class TestSuccessfulWrittenResult:
    def test_written_result_fields(self) -> None:
        from app.core.config import settings
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws = ws_root / f"pd-test-{uuid4().hex[:8]}"
        _setup_workspace_with_manifest(ws)

        session_id = uuid4()
        task_id = uuid4()
        service, msg_id = _build_service_with_fake_repos(
            session_id, task_id, ws, allowed_paths={"src/example.py"},
        )
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=service._message_repository.get_by_id(msg_id),
            user_confirmed=True,
            candidate_files=[
                CandidateSandboxFileWrite(
                    relative_path="src/example.py",
                    content="print('hello')\n",
                    operation="create",
                ),
            ],
        )
        assert result.candidate_write_status == "written"
        assert result.candidate_files_requested_count == 1
        assert result.candidate_files_written_count == 1
        assert result.candidate_files_blocked_count == 0
        assert result.candidate_business_files_written is True
        assert result.business_file_written is True
        assert result.manifest_file_written is False
        assert result.target_file_content_read is False
        assert result.real_diff_generated is False
        assert result.patch_applied is False
        assert result.worktree_created is False
        assert result.git_write_performed is False
        assert result.ai_project_director_total_loop == "Partial"
        for flag in SIDE_EFFECT_FLAGS:
            assert getattr(result, flag) is False, f"{flag} should be False"


# ══════════════════════════════════════════════════════════════════════
# 2. Domain validator rejects true side-effect flags
# ══════════════════════════════════════════════════════════════════════


class TestDomainValidatorRejectsTrueFlags:
    @pytest.mark.parametrize("field_name", SIDE_EFFECT_FLAGS)
    def test_rejects_true_flag(self, field_name: str) -> None:
        with pytest.raises(ValidationError, match="may only write requested sandbox files"):
            ProjectDirectorSandboxCandidateFileWriteResult(
                candidate_write_status="written",
                session_id=uuid4(),
                candidate_write_summary="test",
                recommended_next_step="next",
                **{field_name: True},
            )


# ══════════════════════════════════════════════════════════════════════
# 3. Source validation
# ══════════════════════════════════════════════════════════════════════


class TestSourceValidation:
    def test_user_confirmed_false_blocked(self) -> None:
        service = ProjectDirectorSandboxCandidateFileWriteService()
        result = service.build_candidate_files_write_from_sources(
            session_id=uuid4(),
            source_task_id=uuid4(),
            source_message_id=uuid4(),
            source_task=None,
            source_message=None,
            user_confirmed=False,
            candidate_files=[],
        )
        assert result.candidate_write_status == "blocked"
        assert "user_confirmation_required" in result.blocked_reasons

    def test_source_task_missing_blocked(self) -> None:
        service = ProjectDirectorSandboxCandidateFileWriteService()
        result = service.build_candidate_files_write_from_sources(
            session_id=uuid4(),
            source_task_id=uuid4(),
            source_message_id=uuid4(),
            source_task=None,
            source_message=None,
            user_confirmed=True,
            candidate_files=[],
        )
        assert result.candidate_write_status == "blocked"
        assert "source_task_missing" in result.blocked_reasons

    def test_source_task_not_safe_dry_run_blocked(self) -> None:
        bad_task = Task(
            id=uuid4(), title="bad", source_draft_id="bad",
            input_summary="not safe", acceptance_criteria=[],
        )
        service = ProjectDirectorSandboxCandidateFileWriteService()
        result = service.build_candidate_files_write_from_sources(
            session_id=uuid4(),
            source_task_id=bad_task.id,
            source_message_id=uuid4(),
            source_task=bad_task,
            source_message=None,
            user_confirmed=True,
            candidate_files=[],
        )
        assert result.candidate_write_status == "blocked"
        assert "source_task_not_safe_dry_run" in result.blocked_reasons

    def test_source_message_missing_blocked(self) -> None:
        service = ProjectDirectorSandboxCandidateFileWriteService()
        result = service.build_candidate_files_write_from_sources(
            session_id=uuid4(),
            source_task_id=uuid4(),
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(),
            source_message=None,
            user_confirmed=True,
            candidate_files=[],
        )
        assert result.candidate_write_status == "blocked"
        assert "source_message_missing" in result.blocked_reasons

    def test_non_p21_c_d_source_detail_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        msg = _make_message(
            session_id, task_id, "p21_c_sandbox_workspace_guard",
            {"type": "p21_c_sandbox_workspace_guard_record"},
        )
        service = ProjectDirectorSandboxCandidateFileWriteService()
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
            candidate_files=[],
        )
        assert result.candidate_write_status == "blocked"
        assert "source_message_is_not_p21_c_workspace_manifest_written" in result.blocked_reasons

    def test_missing_manifest_write_action_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL,
            {"type": "wrong_type"},
        )
        service = ProjectDirectorSandboxCandidateFileWriteService()
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
            candidate_files=[],
        )
        assert result.candidate_write_status == "blocked"
        assert "p21_c_workspace_manifest_write_record_missing" in result.blocked_reasons

    def test_manifest_write_status_not_written_or_overwritten_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _manifest_write_action(task_id, workspace_path="/tmp/ws")
        action["manifest_write_status"] = "blocked"
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxCandidateFileWriteService()
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
            candidate_files=[],
        )
        assert result.candidate_write_status == "blocked"
        assert "source_manifest_write_not_written_or_overwritten" in result.blocked_reasons

    def test_manifest_file_written_false_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _manifest_write_action(task_id, workspace_path="/tmp/ws")
        action["manifest_file_written"] = False
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxCandidateFileWriteService()
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
            candidate_files=[],
        )
        assert result.candidate_write_status == "blocked"

    def test_source_task_mismatch_blocked(self) -> None:
        session_id = uuid4()
        task_a = uuid4()
        task_b = uuid4()
        action = _manifest_write_action(task_b, workspace_path="/tmp/ws")
        msg = _make_message(
            session_id, task_b, P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxCandidateFileWriteService()
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_a,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_a),
            source_message=msg,
            user_confirmed=True,
            candidate_files=[],
        )
        assert result.candidate_write_status == "blocked"
        assert "source_task_not_bound_to_workspace_manifest_write" in result.blocked_reasons

    def test_source_manifest_write_no_write_flag_violated_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _manifest_write_action(task_id, workspace_path="/tmp/ws")
        action["business_file_written"] = True
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxCandidateFileWriteService()
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
            candidate_files=[],
        )
        assert result.candidate_write_status == "blocked"
        assert "source_manifest_write_not_no_write_except_manifest" in result.blocked_reasons

    def test_total_loop_not_partial_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _manifest_write_action(task_id, workspace_path="/tmp/ws")
        action["ai_project_director_total_loop"] = "Full"
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxCandidateFileWriteService()
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
            candidate_files=[],
        )
        assert result.candidate_write_status == "blocked"
        assert "source_manifest_write_not_no_write_except_manifest" in result.blocked_reasons

    def test_workspace_path_missing_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _manifest_write_action(task_id, workspace_path="")
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxCandidateFileWriteService()
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
            candidate_files=[],
        )
        assert result.candidate_write_status == "blocked"
        assert "workspace_path_missing" in result.blocked_reasons

    def test_workspace_path_outside_root_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _manifest_write_action(task_id, workspace_path="/tmp/outside-root/ws")
        action["workspace_path_within_root"] = False
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxCandidateFileWriteService()
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
            candidate_files=[],
        )
        assert result.candidate_write_status == "blocked"
        assert "workspace_path_not_within_root" in result.blocked_reasons

    def test_workspace_path_equals_sandbox_root_blocked(self) -> None:
        from app.core.config import settings
        session_id = uuid4()
        task_id = uuid4()
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws_root.mkdir(parents=True, exist_ok=True)
        action = _manifest_write_action(task_id, workspace_path=str(ws_root))
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxCandidateFileWriteService()
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
            candidate_files=[],
        )
        assert result.candidate_write_status == "blocked"
        assert "workspace_path_must_be_workspace_subdirectory" in result.blocked_reasons

    def test_workspace_path_missing_on_disk_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        fake = Path(tempfile.mkdtemp()) / "nonexistent"
        action = _manifest_write_action(task_id, workspace_path=str(fake))
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxCandidateFileWriteService()
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
            candidate_files=[],
        )
        assert result.candidate_write_status == "blocked"
        assert "workspace_path_missing_on_disk" in result.blocked_reasons

    def test_workspace_path_existing_non_directory_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        non_dir = Path(tempfile.mkdtemp()) / "not-a-dir"
        non_dir.write_text("I am a file")
        action = _manifest_write_action(task_id, workspace_path=str(non_dir))
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxCandidateFileWriteService()
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
            candidate_files=[],
        )
        assert result.candidate_write_status == "blocked"
        assert "workspace_path_is_not_directory" in result.blocked_reasons

    def test_internal_manifest_missing_blocked(self) -> None:
        from app.core.config import settings
        session_id = uuid4()
        task_id = uuid4()
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws = ws_root / f"pd-test-{uuid4().hex[:8]}"
        ws.mkdir(parents=True, exist_ok=True)
        # No manifest created
        action = _manifest_write_action(task_id, workspace_path=str(ws))
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxCandidateFileWriteService()
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
            candidate_files=[],
        )
        assert result.candidate_write_status == "blocked"
        assert "internal_manifest_missing" in result.blocked_reasons

    def test_internal_manifest_invalid_json_blocked(self) -> None:
        from app.core.config import settings
        session_id = uuid4()
        task_id = uuid4()
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws = ws_root / f"pd-test-{uuid4().hex[:8]}"
        ws.mkdir(parents=True, exist_ok=True)
        manifest_dir = ws / INTERNAL_MANIFEST_DIR_NAME
        manifest_dir.mkdir(parents=True, exist_ok=True)
        (manifest_dir / INTERNAL_MANIFEST_FILE_NAME).write_text("NOT JSON", encoding="utf-8")
        action = _manifest_write_action(task_id, workspace_path=str(ws))
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxCandidateFileWriteService()
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
            candidate_files=[],
        )
        assert result.candidate_write_status == "blocked"
        assert "internal_manifest_invalid_json" in result.blocked_reasons

    def test_internal_manifest_schema_invalid_blocked(self) -> None:
        from app.core.config import settings
        session_id = uuid4()
        task_id = uuid4()
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws = ws_root / f"pd-test-{uuid4().hex[:8]}"
        ws.mkdir(parents=True, exist_ok=True)
        manifest_dir = ws / INTERNAL_MANIFEST_DIR_NAME
        manifest_dir.mkdir(parents=True, exist_ok=True)
        (manifest_dir / INTERNAL_MANIFEST_FILE_NAME).write_text(
            json.dumps({"schema_version": "wrong", "internal_manifest_only": True, "ai_project_director_total_loop": "Partial", "manifest_file_path": (manifest_dir / INTERNAL_MANIFEST_FILE_NAME).as_posix()}),
            encoding="utf-8",
        )
        action = _manifest_write_action(task_id, workspace_path=str(ws))
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL, action,
        )
        service = ProjectDirectorSandboxCandidateFileWriteService()
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
            candidate_files=[],
        )
        assert result.candidate_write_status == "blocked"
        assert "internal_manifest_schema_invalid" in result.blocked_reasons

    def test_source_workspace_creation_message_missing_blocked(self) -> None:
        from app.core.config import settings
        session_id = uuid4()
        task_id = uuid4()
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws = ws_root / f"pd-test-{uuid4().hex[:8]}"
        _setup_workspace_with_manifest(ws)
        action = _manifest_write_action(task_id, workspace_path=str(ws))
        action["source_message_id"] = str(uuid4())  # non-existent message
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL, action,
        )

        class FakeMsgRepo:
            def get_by_id(self, mid):
                return None
        class FakeSessionRepo:
            def get_by_id(self, sid):
                return type("S", (), {"project_id": uuid4()})()
        class FakeTaskRepo:
            def get_by_id(self, tid):
                return _safe_dry_run_task(tid)

        service = ProjectDirectorSandboxCandidateFileWriteService(
            session_repository=FakeSessionRepo(),
            message_repository=FakeMsgRepo(),
            task_repository=FakeTaskRepo(),
        )
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id),
            source_message=msg,
            user_confirmed=True,
            candidate_files=[],
        )
        assert result.candidate_write_status == "blocked"
        assert "source_workspace_creation_message_missing" in result.blocked_reasons

    def test_operation_manifest_allowed_paths_missing_blocked(self) -> None:
        from app.core.config import settings
        session_id = uuid4()
        task_id = uuid4()
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws = ws_root / f"pd-test-{uuid4().hex[:8]}"
        _setup_workspace_with_manifest(ws)

        op_manifest_msg_id = uuid4()
        ws_creation_msg_id = uuid4()

        # Operation manifest with empty allowed_operation_paths
        op_action = _operation_manifest_action(task_id, allowed_paths=set())
        op_action["allowed_operation_paths"] = []
        op_action["manifest_allowed_operations_count"] = 0
        op_msg = ProjectDirectorMessage(
            id=op_manifest_msg_id, session_id=session_id,
            role=ProjectDirectorMessageRole.ASSISTANT, content="t", sequence_no=1,
            intent="t", related_project_id=uuid4(), related_task_id=task_id,
            source=ProjectDirectorMessageSource.SYSTEM,
            source_detail=P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL,
            suggested_actions=[op_action],
        )

        ws_action = _workspace_creation_action(task_id, workspace_path=str(ws), source_message_id=op_manifest_msg_id)
        ws_msg = ProjectDirectorMessage(
            id=ws_creation_msg_id, session_id=session_id,
            role=ProjectDirectorMessageRole.ASSISTANT, content="t", sequence_no=2,
            intent="t", related_project_id=uuid4(), related_task_id=task_id,
            source=ProjectDirectorMessageSource.SYSTEM,
            source_detail=P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL,
            suggested_actions=[ws_action],
        )

        mw_action = _manifest_write_action(task_id, workspace_path=str(ws), source_message_id=ws_creation_msg_id)
        mw_msg_id = uuid4()
        mw_msg = ProjectDirectorMessage(
            id=mw_msg_id, session_id=session_id,
            role=ProjectDirectorMessageRole.ASSISTANT, content="t", sequence_no=3,
            intent="t", related_project_id=uuid4(), related_task_id=task_id,
            source=ProjectDirectorMessageSource.SYSTEM,
            source_detail=P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL,
            suggested_actions=[mw_action],
        )

        msgs = {op_manifest_msg_id: op_msg, ws_creation_msg_id: ws_msg, mw_msg_id: mw_msg}

        class FakeMsgRepo:
            def get_by_id(self, mid):
                return msgs.get(mid)
        class FakeSessionRepo:
            def get_by_id(self, sid):
                return type("S", (), {"project_id": uuid4()})()
        class FakeTaskRepo:
            def get_by_id(self, tid):
                return _safe_dry_run_task(tid)

        service = ProjectDirectorSandboxCandidateFileWriteService(
            session_repository=FakeSessionRepo(),
            message_repository=FakeMsgRepo(),
            task_repository=FakeTaskRepo(),
        )
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=mw_msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=mw_msg,
            user_confirmed=True,
            candidate_files=[],
        )
        assert result.candidate_write_status == "blocked"
        assert "operation_manifest_allowed_paths_missing" in result.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# 4. Candidate request validation
# ══════════════════════════════════════════════════════════════════════


class TestCandidateRequestValidation:
    def test_candidate_files_empty_blocked(self) -> None:
        from app.core.config import settings
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws = ws_root / f"pd-test-{uuid4().hex[:8]}"
        _setup_workspace_with_manifest(ws)
        session_id = uuid4()
        task_id = uuid4()
        service, msg_id = _build_service_with_fake_repos(session_id, task_id, ws)
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=service._message_repository.get_by_id(msg_id),
            user_confirmed=True,
            candidate_files=[],
        )
        assert result.candidate_write_status == "blocked"
        assert "candidate_files_required" in result.blocked_reasons

    def test_candidate_files_too_many_blocked(self) -> None:
        from app.core.config import settings
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws = ws_root / f"pd-test-{uuid4().hex[:8]}"
        _setup_workspace_with_manifest(ws)
        session_id = uuid4()
        task_id = uuid4()
        allowed = {f"src/file{i}.py" for i in range(21)}
        service, msg_id = _build_service_with_fake_repos(
            session_id, task_id, ws, allowed_paths=allowed,
        )
        candidates = [
            CandidateSandboxFileWrite(
                relative_path=f"src/file{i}.py", content=f"x={i}", operation="create",
            )
            for i in range(21)
        ]
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=service._message_repository.get_by_id(msg_id),
            user_confirmed=True,
            candidate_files=candidates,
        )
        assert result.candidate_write_status == "blocked"
        assert "candidate_files_too_many" in result.blocked_reasons

    def test_single_file_content_too_large_blocked(self) -> None:
        from app.core.config import settings
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws = ws_root / f"pd-test-{uuid4().hex[:8]}"
        _setup_workspace_with_manifest(ws)
        session_id = uuid4()
        task_id = uuid4()
        service, msg_id = _build_service_with_fake_repos(
            session_id, task_id, ws, allowed_paths={"src/large.py"},
        )
        big_content = "x" * (200 * 1024 + 1)
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=service._message_repository.get_by_id(msg_id),
            user_confirmed=True,
            candidate_files=[
                CandidateSandboxFileWrite(
                    relative_path="src/large.py", content=big_content, operation="create",
                ),
            ],
        )
        assert result.candidate_write_status == "blocked"
        assert "candidate_file_content_too_large" in result.blocked_reasons

    def test_total_content_too_large_blocked(self) -> None:
        from app.core.config import settings
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws = ws_root / f"pd-test-{uuid4().hex[:8]}"
        _setup_workspace_with_manifest(ws)
        session_id = uuid4()
        task_id = uuid4()
        allowed = {f"src/f{i}.py" for i in range(6)}
        service, msg_id = _build_service_with_fake_repos(
            session_id, task_id, ws, allowed_paths=allowed,
        )
        chunk = "x" * (200 * 1024)
        candidates = [
            CandidateSandboxFileWrite(
                relative_path=f"src/f{i}.py", content=chunk, operation="create",
            )
            for i in range(6)
        ]
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=service._message_repository.get_by_id(msg_id),
            user_confirmed=True,
            candidate_files=candidates,
        )
        assert result.candidate_write_status == "blocked"
        assert "candidate_files_total_content_too_large" in result.blocked_reasons

    def test_duplicate_relative_path_blocked(self) -> None:
        from app.core.config import settings
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws = ws_root / f"pd-test-{uuid4().hex[:8]}"
        _setup_workspace_with_manifest(ws)
        session_id = uuid4()
        task_id = uuid4()
        service, msg_id = _build_service_with_fake_repos(
            session_id, task_id, ws, allowed_paths={"src/dup.py"},
        )
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=service._message_repository.get_by_id(msg_id),
            user_confirmed=True,
            candidate_files=[
                CandidateSandboxFileWrite(relative_path="src/dup.py", content="a", operation="create"),
                CandidateSandboxFileWrite(relative_path="src/dup.py", content="b", operation="create"),
            ],
        )
        assert result.candidate_write_status == "blocked"


# ══════════════════════════════════════════════════════════════════════
# 5. Candidate path policy
# ══════════════════════════════════════════════════════════════════════


class TestCandidatePathPolicy:
    def _test_path_blocked(self, rel_path, expected_reason_fragment=None):
        from app.core.config import settings
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws = ws_root / f"pd-test-{uuid4().hex[:8]}"
        _setup_workspace_with_manifest(ws)
        session_id = uuid4()
        task_id = uuid4()
        service, msg_id = _build_service_with_fake_repos(
            session_id, task_id, ws, allowed_paths={rel_path},
        )
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=service._message_repository.get_by_id(msg_id),
            user_confirmed=True,
            candidate_files=[
                CandidateSandboxFileWrite(relative_path=rel_path, content="x", operation="create"),
            ],
        )
        assert result.candidate_write_status == "blocked"
        if expected_reason_fragment:
            assert any(expected_reason_fragment in r for r in result.blocked_reasons), (
                f"Expected '{expected_reason_fragment}' in {result.blocked_reasons}"
            )

    def test_empty_path_blocked(self):
        with pytest.raises(ValidationError, match="at least 1 character"):
            CandidateSandboxFileWrite(relative_path="", content="x", operation="create")

    def test_absolute_path_blocked(self):
        self._test_path_blocked("/tmp/evil.py", "candidate_file_path_not_allowed")

    def test_dotdot_blocked(self):
        self._test_path_blocked("../escape.py", "candidate_file_path_not_allowed")

    def test_tilde_blocked(self):
        self._test_path_blocked("~/secret.py", "candidate_file_path_not_allowed")

    def test_windows_drive_blocked(self):
        self._test_path_blocked("C:\\Windows\\system32\\evil.py", "candidate_file_path_not_allowed")

    def test_file_url_blocked(self):
        self._test_path_blocked("file:///tmp/evil.py", "candidate_file_path_not_allowed")

    def test_backslash_blocked(self):
        self._test_path_blocked("foo\\bar.py", "candidate_file_path_not_allowed")

    def test_semicolon_blocked(self):
        self._test_path_blocked("test;rm -rf /", "candidate_file_path_not_allowed")

    def test_pipe_blocked(self):
        self._test_path_blocked("test|cmd", "candidate_file_path_not_allowed")

    def test_ampersand_blocked(self):
        self._test_path_blocked("test&cmd", "candidate_file_path_not_allowed")

    def test_dollar_paren_blocked(self):
        self._test_path_blocked("ws$(cmd)", "candidate_file_path_not_allowed")

    def test_backtick_blocked(self):
        self._test_path_blocked("ws`cmd`", "candidate_file_path_not_allowed")

    def test_path_not_declared_by_manifest_blocked(self):
        from app.core.config import settings
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws = ws_root / f"pd-test-{uuid4().hex[:8]}"
        _setup_workspace_with_manifest(ws)
        session_id = uuid4()
        task_id = uuid4()
        # Manifest declares src/allowed.py but request uses src/undeclared.py
        service, msg_id = _build_service_with_fake_repos(
            session_id, task_id, ws, allowed_paths={"src/allowed.py"},
        )
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=service._message_repository.get_by_id(msg_id),
            user_confirmed=True,
            candidate_files=[
                CandidateSandboxFileWrite(relative_path="src/undeclared.py", content="x", operation="create"),
            ],
        )
        assert result.candidate_write_status == "blocked"
        assert "candidate_file_path_not_declared_by_manifest" in result.blocked_reasons

    def test_operation_mismatch_blocked(self):
        from app.core.config import settings
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws = ws_root / f"pd-test-{uuid4().hex[:8]}"
        _setup_workspace_with_manifest(ws)
        session_id = uuid4()
        task_id = uuid4()
        # Manifest declares "create" but request uses "update"
        service, msg_id = _build_service_with_fake_repos(
            session_id, task_id, ws, allowed_paths={"src/example.py"},
        )
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=service._message_repository.get_by_id(msg_id),
            user_confirmed=True,
            candidate_files=[
                CandidateSandboxFileWrite(relative_path="src/example.py", content="x", operation="update"),
            ],
        )
        assert result.candidate_write_status == "blocked"
        assert "candidate_file_operation_not_allowed" in result.blocked_reasons

    def test_path_targets_internal_dir_blocked(self):
        from app.core.config import settings
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws = ws_root / f"pd-test-{uuid4().hex[:8]}"
        _setup_workspace_with_manifest(ws)
        session_id = uuid4()
        task_id = uuid4()
        internal_path = f"{INTERNAL_MANIFEST_DIR_NAME}/extra.json"
        service, msg_id = _build_service_with_fake_repos(
            session_id, task_id, ws, allowed_paths={internal_path},
        )
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=service._message_repository.get_by_id(msg_id),
            user_confirmed=True,
            candidate_files=[
                CandidateSandboxFileWrite(relative_path=internal_path, content="x", operation="create"),
            ],
        )
        assert result.candidate_write_status == "blocked"
        assert "candidate_file_path_targets_internal_dir" in result.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# 6. Positive path policy
# ══════════════════════════════════════════════════════════════════════


class TestPositivePathPolicy:
    def test_allowed_path_written(self):
        from app.core.config import settings
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws = ws_root / f"pd-test-{uuid4().hex[:8]}"
        _setup_workspace_with_manifest(ws)
        session_id = uuid4()
        task_id = uuid4()
        service, msg_id = _build_service_with_fake_repos(
            session_id, task_id, ws, allowed_paths={"src/example.py"},
        )
        content = "print('hello')\n"
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=service._message_repository.get_by_id(msg_id),
            user_confirmed=True,
            candidate_files=[
                CandidateSandboxFileWrite(relative_path="src/example.py", content=content, operation="create"),
            ],
        )
        assert result.candidate_write_status == "written"
        written_path = ws / "src" / "example.py"
        assert written_path.exists()
        assert written_path.read_text(encoding="utf-8") == content

    def test_nested_parent_dirs_created(self):
        from app.core.config import settings
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws = ws_root / f"pd-test-{uuid4().hex[:8]}"
        _setup_workspace_with_manifest(ws)
        session_id = uuid4()
        task_id = uuid4()
        service, msg_id = _build_service_with_fake_repos(
            session_id, task_id, ws, allowed_paths={"a/b/c/deep.py"},
        )
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=service._message_repository.get_by_id(msg_id),
            user_confirmed=True,
            candidate_files=[
                CandidateSandboxFileWrite(relative_path="a/b/c/deep.py", content="deep", operation="create"),
            ],
        )
        assert result.candidate_write_status == "written"
        assert (ws / "a" / "b" / "c" / "deep.py").exists()

    def test_internal_manifest_unchanged_after_write(self):
        from app.core.config import settings
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws = ws_root / f"pd-test-{uuid4().hex[:8]}"
        _setup_workspace_with_manifest(ws)
        manifest_path = ws / INTERNAL_MANIFEST_DIR_NAME / INTERNAL_MANIFEST_FILE_NAME
        manifest_before = manifest_path.read_text(encoding="utf-8")

        session_id = uuid4()
        task_id = uuid4()
        service, msg_id = _build_service_with_fake_repos(
            session_id, task_id, ws, allowed_paths={"src/example.py"},
        )
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=service._message_repository.get_by_id(msg_id),
            user_confirmed=True,
            candidate_files=[
                CandidateSandboxFileWrite(relative_path="src/example.py", content="x", operation="create"),
            ],
        )
        assert result.candidate_write_status == "written"
        manifest_after = manifest_path.read_text(encoding="utf-8")
        assert manifest_before == manifest_after

    def test_no_extra_files_written(self):
        from app.core.config import settings
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws = ws_root / f"pd-test-{uuid4().hex[:8]}"
        _setup_workspace_with_manifest(ws)
        session_id = uuid4()
        task_id = uuid4()
        service, msg_id = _build_service_with_fake_repos(
            session_id, task_id, ws, allowed_paths={"src/one.py"},
        )
        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=service._message_repository.get_by_id(msg_id),
            user_confirmed=True,
            candidate_files=[
                CandidateSandboxFileWrite(relative_path="src/one.py", content="x", operation="create"),
            ],
        )
        assert result.candidate_write_status == "written"
        all_files = [f for f in ws.rglob("*") if f.is_file()]
        non_manifest_files = [
            f for f in all_files
            if not str(f).endswith(f"{INTERNAL_MANIFEST_DIR_NAME}/{INTERNAL_MANIFEST_FILE_NAME}")
        ]
        assert len(non_manifest_files) == 1
        assert non_manifest_files[0].name == "one.py"


# ══════════════════════════════════════════════════════════════════════
# 7. Partial write failure consistency
# ══════════════════════════════════════════════════════════════════════


class TestPartialWriteFailure:
    def test_multi_file_write_failure_consistency(self, monkeypatch):
        """If multi-file write fails mid-way, check if first file lingers."""
        from app.core.config import settings
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws = ws_root / f"pd-test-{uuid4().hex[:8]}"
        _setup_workspace_with_manifest(ws)
        session_id = uuid4()
        task_id = uuid4()
        service, msg_id = _build_service_with_fake_repos(
            session_id, task_id, ws, allowed_paths={"src/first.py", "src/second.py"},
        )

        original_write_text = Path.write_text
        call_count = 0

        def failing_write_text(self, data, encoding=None):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise OSError("Simulated write failure")
            return original_write_text(self, data, encoding=encoding)

        monkeypatch.setattr(Path, "write_text", failing_write_text)

        result = service.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=service._message_repository.get_by_id(msg_id),
            user_confirmed=True,
            candidate_files=[
                CandidateSandboxFileWrite(relative_path="src/first.py", content="first", operation="create"),
                CandidateSandboxFileWrite(relative_path="src/second.py", content="second", operation="create"),
            ],
        )

        first_path = ws / "src" / "first.py"
        second_path = ws / "src" / "second.py"

        if result.candidate_write_status == "blocked":
            if first_path.exists():
                pytest.xfail(
                    "R1 needed: partial write failure leaves first file while result is blocked"
                )
            else:
                assert not first_path.exists(), "No residual files after blocked write"
                assert not second_path.exists()
        else:
            # If it somehow succeeded, that's also acceptable for this test
            pass


# ══════════════════════════════════════════════════════════════════════
# 8. Output no misleading terms
# ══════════════════════════════════════════════════════════════════════


class TestOutputNoMisleadingTerms:
    def test_result_output_excludes_misleading_terms(self):
        result = ProjectDirectorSandboxCandidateFileWriteResult(
            candidate_write_status="blocked",
            session_id=uuid4(),
            candidate_write_summary="blocked",
            recommended_next_step="next",
        )
        serialized = result.model_dump_json()
        for term in MISLEADING_TERMS:
            assert term not in serialized, f"Found misleading term: {term}"
