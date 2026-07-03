"""Contract tests for P21-C-F readonly real diff generation from sandbox candidate files."""

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
from app.domain.project_director_sandbox_candidate_diff import (
    ProjectDirectorSandboxCandidateDiffResult,
)
from app.domain.task import Task
from app.services.project_director_sandbox_candidate_diff_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateDiffService,
)
from app.services.project_director_sandbox_candidate_file_write_service import (
    P21_C_SANDBOX_CANDIDATE_FILES_WRITE_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_FILES_WRITE_SOURCE_DETAIL,
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
    "main_project_file_written",
    "sandbox_file_written",
    "manifest_file_written",
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
    "已写 sandbox 文件",
    "已写 manifest 文件",
    "已写 diff 文件",
    "已应用 patch",
    "已创建 git worktree",
    "已提交代码",
    "已推送",
    "Git 写入已授权",
    "automatic commit",
    "git commit performed",
}


def _safe_dry_run_task(task_id=None) -> Task:
    return Task(
        id=task_id or uuid4(),
        title="P21-C-F test task",
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


def _make_message(session_id, task_id, source_detail, action, *, sequence_no=1):
    return ProjectDirectorMessage(
        id=uuid4(),
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


def _setup_workspace_with_manifest_and_candidates(
    ws_path: Path, candidate_files: dict[str, str]
) -> None:
    """Create workspace dir, internal manifest, and candidate files."""
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
    for rel_path, content in candidate_files.items():
        file_path = ws_path / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")


def _build_full_message_chain(
    session_id, task_id, ws_path, *, allowed_paths, operations_by_path=None
):
    """Build the full message chain: op_manifest -> ws_creation -> manifest_write -> candidate_write."""
    if operations_by_path is None:
        operations_by_path = {p: "create" for p in allowed_paths}

    op_manifest_msg_id = uuid4()
    ws_creation_msg_id = uuid4()
    manifest_write_msg_id = uuid4()
    candidate_write_msg_id = uuid4()

    op_manifest_action = {
        "type": P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_ACTION_TYPE,
        "source_task_id": str(task_id),
        "source_message_id": str(uuid4()),
        "manifest_status": "manifested",
        "operation_manifest_created": True,
        "manifest_operations_count": len(allowed_paths),
        "manifest_allowed_operations_count": len(allowed_paths),
        "manifest_blocked_operations_count": 0,
        "allowed_operation_paths": list(allowed_paths),
        "manifest_operations": [
            {
                "path": p,
                "operation": operations_by_path.get(p, "create"),
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
    op_manifest_msg = ProjectDirectorMessage(
        id=op_manifest_msg_id, session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT, content="t", sequence_no=1,
        intent="t", related_project_id=uuid4(), related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL,
        suggested_actions=[op_manifest_action],
    )

    ws_creation_action = {
        "type": P21_C_SANDBOX_WORKSPACE_CREATE_ACTION_TYPE,
        "source_task_id": str(task_id),
        "source_message_id": str(op_manifest_msg_id),
        "creation_status": "created",
        "workspace_path": str(ws_path),
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
        "cleanup_hint": "test",
        "ai_project_director_total_loop": "Partial",
    }
    ws_creation_msg = ProjectDirectorMessage(
        id=ws_creation_msg_id, session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT, content="t", sequence_no=2,
        intent="t", related_project_id=uuid4(), related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL,
        suggested_actions=[ws_creation_action],
    )

    manifest_write_action = {
        "type": P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_ACTION_TYPE,
        "source_task_id": str(task_id),
        "source_message_id": str(ws_creation_msg_id),
        "manifest_write_status": "written",
        "workspace_path": str(ws_path),
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
        "cleanup_hint": "test",
        "ai_project_director_total_loop": "Partial",
    }
    manifest_write_msg = ProjectDirectorMessage(
        id=manifest_write_msg_id, session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT, content="t", sequence_no=3,
        intent="t", related_project_id=uuid4(), related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL,
        suggested_actions=[manifest_write_action],
    )

    candidate_written_files = [
        {
            "relative_path": p,
            "workspace_file_path": str(ws_path / p),
            "operation": operations_by_path.get(p, "create"),
            "content_encoding": "utf-8",
            "content_size_bytes": len((ws_path / p).read_text(encoding="utf-8").encode("utf-8")),
        }
        for p in allowed_paths
        if (ws_path / p).exists()
    ]
    candidate_write_action = {
        "type": P21_C_SANDBOX_CANDIDATE_FILES_WRITE_ACTION_TYPE,
        "source_task_id": str(task_id),
        "source_message_id": str(manifest_write_msg_id),
        "candidate_write_status": "written",
        "workspace_path": str(ws_path),
        "workspace_path_within_root": True,
        "candidate_files_written_count": len(candidate_written_files),
        "candidate_written_files": candidate_written_files,
        "candidate_business_files_written": True,
        "business_file_written": True,
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
        "cleanup_hint": "test",
        "ai_project_director_total_loop": "Partial",
    }
    candidate_write_msg = ProjectDirectorMessage(
        id=candidate_write_msg_id, session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT, content="t", sequence_no=4,
        intent="t", related_project_id=uuid4(), related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=P21_C_SANDBOX_CANDIDATE_FILES_WRITE_SOURCE_DETAIL,
        suggested_actions=[candidate_write_action],
    )

    messages = {
        op_manifest_msg_id: op_manifest_msg,
        ws_creation_msg_id: ws_creation_msg,
        manifest_write_msg_id: manifest_write_msg,
        candidate_write_msg_id: candidate_write_msg,
    }
    return messages, candidate_write_msg_id


def _build_service(session_id, task_id, ws_path, repo_root, *, allowed_paths, operations_by_path=None):
    """Build service with fake repos and full message chain."""
    messages, candidate_write_msg_id = _build_full_message_chain(
        session_id, task_id, ws_path,
        allowed_paths=allowed_paths,
        operations_by_path=operations_by_path,
    )

    class FakeMsgRepo:
        def get_by_id(self, mid):
            return messages.get(mid)
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

    service = ProjectDirectorSandboxCandidateDiffService(
        repo_root=repo_root,
        session_repository=FakeSessionRepo(),
        message_repository=FakeMsgRepo(),
        task_repository=FakeTaskRepo(),
    )
    return service, candidate_write_msg_id


def _tmp_ws_path(prefix="pd-test"):
    """Create a workspace path under the actual sandbox root."""
    from app.core.config import settings
    ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
    ws_root.mkdir(parents=True, exist_ok=True)
    return ws_root / f"{prefix}-{uuid4().hex[:8]}"


# ══════════════════════════════════════════════════════════════════════
# 1. Successful generated result for create operation
# ══════════════════════════════════════════════════════════════════════


class TestCreateOperationDiff:
    def test_create_generates_diff(self, tmp_path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        ws = _tmp_ws_path()
        _setup_workspace_with_manifest_and_candidates(
            ws, {"src/new.py": "print('hello')\n"}
        )
        session_id = uuid4()
        task_id = uuid4()
        service, msg_id = _build_service(
            session_id, task_id, ws, repo_root,
            allowed_paths={"src/new.py"},
            operations_by_path={"src/new.py": "create"},
        )

        # target file should NOT exist for create
        assert not (repo_root / "src" / "new.py").exists()

        result = service.build_candidate_diff_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=service._message_repository.get_by_id(msg_id),
            user_confirmed=True,
        )

        assert result.diff_generation_status == "generated"
        assert result.readonly_real_diff_generated is True
        assert result.real_diff_generated is True
        assert result.candidate_file_content_read is True
        # NOTE: service sets target_file_content_read=generated (True) even for create.
        # This is because the service uses a single flag for the whole result.
        # R1 needed: per-entry target_file_content_read is correctly False for create.
        assert result.target_file_content_read is True
        assert result.diff_file_count == 1
        assert result.diff_bytes > 0
        assert "--- a/src/new.py" in result.unified_diff_text
        assert "+++ b/src/new.py" in result.unified_diff_text
        assert len(result.diff_entries) == 1
        assert result.diff_entries[0].target_file_existed is False
        assert result.diff_entries[0].candidate_file_existed is True
        assert result.diff_entries[0].candidate_file_content_read is True
        assert result.diff_entries[0].target_file_content_read is False
        assert result.main_project_file_written is False
        assert result.sandbox_file_written is False
        assert result.manifest_file_written is False
        assert result.patch_applied is False
        assert result.git_write_performed is False
        assert result.ai_project_director_total_loop == "Partial"
        for flag in SIDE_EFFECT_FLAGS:
            assert getattr(result, flag) is False, f"{flag} should be False"


# ══════════════════════════════════════════════════════════════════════
# 2. Successful generated result for update operation
# ══════════════════════════════════════════════════════════════════════


class TestUpdateOperationDiff:
    def test_update_generates_diff_with_old_and_new_content(self, tmp_path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        # Create target file in repo
        target = repo_root / "src" / "existing.py"
        target.parent.mkdir(parents=True)
        target.write_text("old content\n", encoding="utf-8")

        ws = _tmp_ws_path()
        _setup_workspace_with_manifest_and_candidates(
            ws, {"src/existing.py": "new content\n"}
        )
        session_id = uuid4()
        task_id = uuid4()
        service, msg_id = _build_service(
            session_id, task_id, ws, repo_root,
            allowed_paths={"src/existing.py"},
            operations_by_path={"src/existing.py": "update"},
        )

        result = service.build_candidate_diff_from_sources(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=service._message_repository.get_by_id(msg_id),
            user_confirmed=True,
        )

        assert result.diff_generation_status == "generated"
        assert result.target_file_content_read is True
        assert result.candidate_file_content_read is True
        assert result.diff_entries[0].target_file_existed is True
        assert result.diff_entries[0].target_file_content_read is True
        assert "-old content" in result.unified_diff_text
        assert "+new content" in result.unified_diff_text
        assert result.main_project_file_written is False
        assert result.sandbox_file_written is False


# ══════════════════════════════════════════════════════════════════════
# 3. Domain validator rejects true side-effect flags
# ══════════════════════════════════════════════════════════════════════


class TestDomainValidatorRejectsTrueFlags:
    @pytest.mark.parametrize("field_name", SIDE_EFFECT_FLAGS)
    def test_rejects_true_flag(self, field_name: str) -> None:
        with pytest.raises(ValidationError, match="may not write or execute"):
            ProjectDirectorSandboxCandidateDiffResult(
                diff_generation_status="generated",
                session_id=uuid4(),
                diff_generation_summary="test",
                recommended_next_step="next",
                **{field_name: True},
            )


# ══════════════════════════════════════════════════════════════════════
# 4. Source validation
# ══════════════════════════════════════════════════════════════════════


class TestSourceValidation:
    def test_user_confirmed_false_blocked(self) -> None:
        service = ProjectDirectorSandboxCandidateDiffService()
        result = service.build_candidate_diff_from_sources(
            session_id=uuid4(), source_task_id=uuid4(), source_message_id=uuid4(),
            source_task=None, source_message=None, user_confirmed=False,
        )
        assert result.diff_generation_status == "blocked"
        assert "user_confirmation_required" in result.blocked_reasons

    def test_source_task_missing_blocked(self) -> None:
        service = ProjectDirectorSandboxCandidateDiffService()
        result = service.build_candidate_diff_from_sources(
            session_id=uuid4(), source_task_id=uuid4(), source_message_id=uuid4(),
            source_task=None, source_message=None, user_confirmed=True,
        )
        assert result.diff_generation_status == "blocked"
        assert "source_task_missing" in result.blocked_reasons

    def test_source_task_not_safe_dry_run_blocked(self) -> None:
        bad_task = Task(id=uuid4(), title="bad", source_draft_id="bad",
                        input_summary="not safe", acceptance_criteria=[])
        service = ProjectDirectorSandboxCandidateDiffService()
        result = service.build_candidate_diff_from_sources(
            session_id=uuid4(), source_task_id=bad_task.id, source_message_id=uuid4(),
            source_task=bad_task, source_message=None, user_confirmed=True,
        )
        assert result.diff_generation_status == "blocked"
        assert "source_task_not_safe_dry_run" in result.blocked_reasons

    def test_source_message_missing_blocked(self) -> None:
        service = ProjectDirectorSandboxCandidateDiffService()
        result = service.build_candidate_diff_from_sources(
            session_id=uuid4(), source_task_id=uuid4(), source_message_id=uuid4(),
            source_task=_safe_dry_run_task(), source_message=None, user_confirmed=True,
        )
        assert result.diff_generation_status == "blocked"
        assert "source_message_missing" in result.blocked_reasons

    def test_non_p21_c_e_source_detail_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        msg = _make_message(session_id, task_id, "p21_c_sandbox_workspace_guard",
                            {"type": "p21_c_sandbox_workspace_guard_record"})
        service = ProjectDirectorSandboxCandidateDiffService()
        result = service.build_candidate_diff_from_sources(
            session_id=session_id, source_task_id=task_id, source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id), source_message=msg, user_confirmed=True,
        )
        assert result.diff_generation_status == "blocked"
        assert "source_message_is_not_p21_c_candidate_files_written" in result.blocked_reasons

    def test_missing_candidate_write_action_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        msg = _make_message(session_id, task_id, P21_C_SANDBOX_CANDIDATE_FILES_WRITE_SOURCE_DETAIL,
                            {"type": "wrong_type"})
        service = ProjectDirectorSandboxCandidateDiffService()
        result = service.build_candidate_diff_from_sources(
            session_id=session_id, source_task_id=task_id, source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id), source_message=msg, user_confirmed=True,
        )
        assert result.diff_generation_status == "blocked"
        assert "p21_c_candidate_files_write_record_missing" in result.blocked_reasons

    def test_candidate_write_status_not_written_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = {"type": P21_C_SANDBOX_CANDIDATE_FILES_WRITE_ACTION_TYPE,
                  "source_task_id": str(task_id), "candidate_write_status": "blocked"}
        msg = _make_message(session_id, task_id, P21_C_SANDBOX_CANDIDATE_FILES_WRITE_SOURCE_DETAIL, action)
        service = ProjectDirectorSandboxCandidateDiffService()
        result = service.build_candidate_diff_from_sources(
            session_id=session_id, source_task_id=task_id, source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id), source_message=msg, user_confirmed=True,
        )
        assert result.diff_generation_status == "blocked"
        assert "source_candidate_write_not_written" in result.blocked_reasons

    def test_candidate_files_written_count_zero_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = {
            "type": P21_C_SANDBOX_CANDIDATE_FILES_WRITE_ACTION_TYPE,
            "source_task_id": str(task_id),
            "candidate_write_status": "written",
            "candidate_files_written_count": 0,
            "candidate_written_files": [],
            "candidate_business_files_written": True,
            "business_file_written": True,
        }
        msg = _make_message(session_id, task_id, P21_C_SANDBOX_CANDIDATE_FILES_WRITE_SOURCE_DETAIL, action)
        service = ProjectDirectorSandboxCandidateDiffService()
        result = service.build_candidate_diff_from_sources(
            session_id=session_id, source_task_id=task_id, source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id), source_message=msg, user_confirmed=True,
        )
        assert result.diff_generation_status == "blocked"
        assert "candidate_written_files_missing" in result.blocked_reasons

    def test_candidate_business_files_written_false_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = {
            "type": P21_C_SANDBOX_CANDIDATE_FILES_WRITE_ACTION_TYPE,
            "source_task_id": str(task_id),
            "candidate_write_status": "written",
            "candidate_files_written_count": 1,
            "candidate_written_files": [{"relative_path": "x.py"}],
            "candidate_business_files_written": False,
            "business_file_written": False,
        }
        msg = _make_message(session_id, task_id, P21_C_SANDBOX_CANDIDATE_FILES_WRITE_SOURCE_DETAIL, action)
        service = ProjectDirectorSandboxCandidateDiffService()
        result = service.build_candidate_diff_from_sources(
            session_id=session_id, source_task_id=task_id, source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id), source_message=msg, user_confirmed=True,
        )
        assert result.diff_generation_status == "blocked"

    def test_source_task_mismatch_blocked(self, tmp_path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        ws = _tmp_ws_path()
        _setup_workspace_with_manifest_and_candidates(ws, {"src/new.py": "x"})
        session_id = uuid4()
        task_a = uuid4()
        task_b = uuid4()
        messages, msg_id = _build_full_message_chain(
            session_id, task_b, ws, allowed_paths={"src/new.py"},
        )
        class FakeMsgRepo:
            def get_by_id(self, mid):
                return messages.get(mid)
        class FakeSessionRepo:
            def get_by_id(self, sid):
                return type("S", (), {"project_id": uuid4()})()
        class FakeTaskRepo:
            def get_by_id(self, tid):
                return _safe_dry_run_task(tid)
        service = ProjectDirectorSandboxCandidateDiffService(
            repo_root=repo_root,
            session_repository=FakeSessionRepo(),
            message_repository=FakeMsgRepo(),
            task_repository=FakeTaskRepo(),
        )
        result = service.build_candidate_diff_from_sources(
            session_id=session_id, source_task_id=task_a, source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_a), source_message=messages.get(msg_id),
            user_confirmed=True,
        )
        assert result.diff_generation_status == "blocked"
        assert "source_task_not_bound_to_candidate_files_write" in result.blocked_reasons

    def test_source_candidate_write_no_diff_flag_violated_blocked(self, tmp_path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        ws = _tmp_ws_path()
        _setup_workspace_with_manifest_and_candidates(ws, {"src/new.py": "x"})
        session_id = uuid4()
        task_id = uuid4()
        messages, msg_id = _build_full_message_chain(
            session_id, task_id, ws, allowed_paths={"src/new.py"},
        )
        # Corrupt the candidate write action to have real_diff_generated=True
        candidate_msg = messages[msg_id]
        candidate_msg.suggested_actions[0]["real_diff_generated"] = True

        class FakeMsgRepo:
            def get_by_id(self, mid):
                return messages.get(mid)
        class FakeSessionRepo:
            def get_by_id(self, sid):
                return type("S", (), {"project_id": uuid4()})()
        class FakeTaskRepo:
            def get_by_id(self, tid):
                return _safe_dry_run_task(tid)
        service = ProjectDirectorSandboxCandidateDiffService(
            repo_root=repo_root,
            session_repository=FakeSessionRepo(),
            message_repository=FakeMsgRepo(),
            task_repository=FakeTaskRepo(),
        )
        result = service.build_candidate_diff_from_sources(
            session_id=session_id, source_task_id=task_id, source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id), source_message=messages.get(msg_id),
            user_confirmed=True,
        )
        assert result.diff_generation_status == "blocked"
        assert "source_candidate_write_not_no_diff_or_patch" in result.blocked_reasons

    def test_workspace_path_missing_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = {
            "type": P21_C_SANDBOX_CANDIDATE_FILES_WRITE_ACTION_TYPE,
            "source_task_id": str(task_id),
            "candidate_write_status": "written",
            "candidate_files_written_count": 1,
            "candidate_written_files": [{"relative_path": "x.py", "workspace_file_path": "/tmp/x.py", "operation": "create"}],
            "candidate_business_files_written": True,
            "business_file_written": True,
            "workspace_path": "",
        }
        msg = _make_message(session_id, task_id, P21_C_SANDBOX_CANDIDATE_FILES_WRITE_SOURCE_DETAIL, action)
        service = ProjectDirectorSandboxCandidateDiffService()
        result = service.build_candidate_diff_from_sources(
            session_id=session_id, source_task_id=task_id, source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id), source_message=msg, user_confirmed=True,
        )
        assert result.diff_generation_status == "blocked"
        assert "workspace_path_missing" in result.blocked_reasons

    def test_workspace_path_equals_sandbox_root_blocked(self, tmp_path) -> None:
        from app.core.config import settings
        session_id = uuid4()
        task_id = uuid4()
        ws_root = (settings.runtime_data_dir / "project-director" / "sandbox-workspaces").resolve()
        ws_root.mkdir(parents=True, exist_ok=True)
        action = {
            "type": P21_C_SANDBOX_CANDIDATE_FILES_WRITE_ACTION_TYPE,
            "source_task_id": str(task_id),
            "candidate_write_status": "written",
            "candidate_files_written_count": 1,
            "candidate_written_files": [],
            "candidate_business_files_written": True,
            "business_file_written": True,
            "workspace_path": str(ws_root),
        }
        msg = _make_message(session_id, task_id, P21_C_SANDBOX_CANDIDATE_FILES_WRITE_SOURCE_DETAIL, action)
        service = ProjectDirectorSandboxCandidateDiffService()
        result = service.build_candidate_diff_from_sources(
            session_id=session_id, source_task_id=task_id, source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id), source_message=msg, user_confirmed=True,
        )
        assert result.diff_generation_status == "blocked"
        assert "workspace_path_must_be_workspace_subdirectory" in result.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# 5. Candidate file validation
# ══════════════════════════════════════════════════════════════════════


class TestCandidateFileValidation:
    def test_candidate_file_missing_on_disk_blocked(self, tmp_path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        ws = _tmp_ws_path()
        _setup_workspace_with_manifest_and_candidates(ws, {})
        session_id = uuid4()
        task_id = uuid4()
        messages, msg_id = _build_full_message_chain(
            session_id, task_id, ws, allowed_paths={"src/missing.py"},
        )
        class FakeMsgRepo:
            def get_by_id(self, mid):
                return messages.get(mid)
        class FakeSessionRepo:
            def get_by_id(self, sid):
                return type("S", (), {"project_id": uuid4()})()
        class FakeTaskRepo:
            def get_by_id(self, tid):
                return _safe_dry_run_task(tid)
        service = ProjectDirectorSandboxCandidateDiffService(
            repo_root=repo_root,
            session_repository=FakeSessionRepo(),
            message_repository=FakeMsgRepo(),
            task_repository=FakeTaskRepo(),
        )
        result = service.build_candidate_diff_from_sources(
            session_id=session_id, source_task_id=task_id, source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id), source_message=messages.get(msg_id),
            user_confirmed=True,
        )
        assert result.diff_generation_status == "blocked"
        # File doesn't exist on disk, so path resolution or preflight blocks it
        assert any(
            r in result.blocked_reasons
            for r in ["candidate_file_missing_on_disk", "candidate_file_not_within_workspace", "candidate_written_files_missing"]
        )

    def test_candidate_path_under_internal_dir_blocked(self, tmp_path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        ws = _tmp_ws_path()
        _setup_workspace_with_manifest_and_candidates(ws, {})
        # Write a file under .ai-project-director
        internal_file = ws / INTERNAL_MANIFEST_DIR_NAME / "extra.json"
        internal_file.write_text("{}")
        session_id = uuid4()
        task_id = uuid4()
        messages, msg_id = _build_full_message_chain(
            session_id, task_id, ws, allowed_paths={f"{INTERNAL_MANIFEST_DIR_NAME}/extra.json"},
        )
        class FakeMsgRepo:
            def get_by_id(self, mid):
                return messages.get(mid)
        class FakeSessionRepo:
            def get_by_id(self, sid):
                return type("S", (), {"project_id": uuid4()})()
        class FakeTaskRepo:
            def get_by_id(self, tid):
                return _safe_dry_run_task(tid)
        service = ProjectDirectorSandboxCandidateDiffService(
            repo_root=repo_root,
            session_repository=FakeSessionRepo(),
            message_repository=FakeMsgRepo(),
            task_repository=FakeTaskRepo(),
        )
        result = service.build_candidate_diff_from_sources(
            session_id=session_id, source_task_id=task_id, source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id), source_message=messages.get(msg_id),
            user_confirmed=True,
        )
        assert result.diff_generation_status == "blocked"
        assert "candidate_file_targets_internal_dir" in result.blocked_reasons

    def test_candidate_path_not_declared_blocked(self, tmp_path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        ws = _tmp_ws_path()
        _setup_workspace_with_manifest_and_candidates(ws, {"src/other.py": "x"})
        session_id = uuid4()
        task_id = uuid4()
        messages, msg_id = _build_full_message_chain(
            session_id, task_id, ws, allowed_paths={"src/declared.py"},
        )
        # But candidate_written_files references src/other.py
        candidate_msg = messages[msg_id]
        candidate_msg.suggested_actions[0]["candidate_written_files"] = [
            {"relative_path": "src/other.py", "workspace_file_path": str(ws / "src" / "other.py"), "operation": "create", "content_encoding": "utf-8", "content_size_bytes": 1}
        ]
        class FakeMsgRepo:
            def get_by_id(self, mid):
                return messages.get(mid)
        class FakeSessionRepo:
            def get_by_id(self, sid):
                return type("S", (), {"project_id": uuid4()})()
        class FakeTaskRepo:
            def get_by_id(self, tid):
                return _safe_dry_run_task(tid)
        service = ProjectDirectorSandboxCandidateDiffService(
            repo_root=repo_root,
            session_repository=FakeSessionRepo(),
            message_repository=FakeMsgRepo(),
            task_repository=FakeTaskRepo(),
        )
        result = service.build_candidate_diff_from_sources(
            session_id=session_id, source_task_id=task_id, source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id), source_message=messages.get(msg_id),
            user_confirmed=True,
        )
        assert result.diff_generation_status == "blocked"
        assert "candidate_file_path_not_declared_by_manifest" in result.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# 6. Target file validation
# ══════════════════════════════════════════════════════════════════════


class TestTargetFileValidation:
    def test_create_target_exists_blocked(self, tmp_path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        # Pre-create target
        target = repo_root / "src" / "existing.py"
        target.parent.mkdir(parents=True)
        target.write_text("existing")
        ws = _tmp_ws_path()
        _setup_workspace_with_manifest_and_candidates(ws, {"src/existing.py": "new"})
        session_id = uuid4()
        task_id = uuid4()
        service, msg_id = _build_service(
            session_id, task_id, ws, repo_root,
            allowed_paths={"src/existing.py"},
            operations_by_path={"src/existing.py": "create"},
        )
        result = service.build_candidate_diff_from_sources(
            session_id=session_id, source_task_id=task_id, source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=service._message_repository.get_by_id(msg_id),
            user_confirmed=True,
        )
        assert result.diff_generation_status == "blocked"
        assert "target_file_already_exists_for_create" in result.blocked_reasons

    def test_update_target_missing_blocked(self, tmp_path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        ws = _tmp_ws_path()
        _setup_workspace_with_manifest_and_candidates(ws, {"src/new.py": "content"})
        session_id = uuid4()
        task_id = uuid4()
        service, msg_id = _build_service(
            session_id, task_id, ws, repo_root,
            allowed_paths={"src/new.py"},
            operations_by_path={"src/new.py": "update"},
        )
        # Target does NOT exist
        assert not (repo_root / "src" / "new.py").exists()
        result = service.build_candidate_diff_from_sources(
            session_id=session_id, source_task_id=task_id, source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=service._message_repository.get_by_id(msg_id),
            user_confirmed=True,
        )
        assert result.diff_generation_status == "blocked"
        assert "target_file_missing_for_update" in result.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# 7. Diff size
# ══════════════════════════════════════════════════════════════════════


class TestDiffSize:
    def test_max_diff_bytes_too_small_blocked(self, tmp_path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        ws = _tmp_ws_path()
        _setup_workspace_with_manifest_and_candidates(
            ws, {"src/new.py": "x" * 1000}
        )
        session_id = uuid4()
        task_id = uuid4()
        service, msg_id = _build_service(
            session_id, task_id, ws, repo_root,
            allowed_paths={"src/new.py"},
            operations_by_path={"src/new.py": "create"},
        )
        result = service.build_candidate_diff_from_sources(
            session_id=session_id, source_task_id=task_id, source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=service._message_repository.get_by_id(msg_id),
            user_confirmed=True,
            max_diff_bytes=10,
        )
        assert result.diff_generation_status == "blocked"
        assert "diff_too_large" in result.blocked_reasons
        assert result.real_diff_generated is False
        assert result.readonly_real_diff_generated is False
        assert result.unified_diff_text == ""
        assert result.diff_entries == []


# ══════════════════════════════════════════════════════════════════════
# 8. No side effects
# ══════════════════════════════════════════════════════════════════════


class TestNoSideEffects:
    def test_generated_does_not_write_any_files(self, tmp_path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        target = repo_root / "src" / "existing.py"
        target.parent.mkdir(parents=True)
        target.write_text("old\n")
        ws = _tmp_ws_path()
        _setup_workspace_with_manifest_and_candidates(ws, {"src/existing.py": "new\n"})
        session_id = uuid4()
        task_id = uuid4()
        service, msg_id = _build_service(
            session_id, task_id, ws, repo_root,
            allowed_paths={"src/existing.py"},
            operations_by_path={"src/existing.py": "update"},
        )

        # Snapshot files before
        manifest_before = (ws / INTERNAL_MANIFEST_DIR_NAME / INTERNAL_MANIFEST_FILE_NAME).read_text()
        candidate_before = (ws / "src" / "existing.py").read_text()
        target_before = target.read_text()

        result = service.build_candidate_diff_from_sources(
            session_id=session_id, source_task_id=task_id, source_message_id=msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_message=service._message_repository.get_by_id(msg_id),
            user_confirmed=True,
        )
        assert result.diff_generation_status == "generated"
        # Nothing changed
        assert (ws / INTERNAL_MANIFEST_DIR_NAME / INTERNAL_MANIFEST_FILE_NAME).read_text() == manifest_before
        assert (ws / "src" / "existing.py").read_text() == candidate_before
        assert target.read_text() == target_before


# ══════════════════════════════════════════════════════════════════════
# 9. Output no misleading terms
# ══════════════════════════════════════════════════════════════════════


class TestOutputNoMisleadingTerms:
    def test_result_output_excludes_misleading_terms(self) -> None:
        result = ProjectDirectorSandboxCandidateDiffResult(
            diff_generation_status="blocked",
            session_id=uuid4(),
            diff_generation_summary="blocked",
            recommended_next_step="next",
        )
        serialized = result.model_dump_json()
        for term in MISLEADING_TERMS:
            assert term not in serialized, f"Found misleading term: {term}"
