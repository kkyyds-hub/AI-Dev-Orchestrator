"""Contract tests for P21-C-G readonly real diff review handoff."""

from __future__ import annotations

import hashlib
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_sandbox_candidate_diff_review_handoff import (
    ProjectDirectorSandboxCandidateDiffReviewHandoffResult,
)
from app.domain.task import Task
from app.services.project_director_sandbox_candidate_diff_review_handoff_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateDiffReviewHandoffService,
)
from app.services.project_director_sandbox_candidate_diff_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL,
)


SIDE_EFFECT_FLAGS = [
    "reviewer_started",
    "review_executed",
    "review_verdict_generated",
    "review_findings_generated",
    "main_project_file_written",
    "sandbox_file_written",
    "manifest_file_written",
    "diff_file_written",
    "patch_applied",
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
    "审查通过", "review passed", "已批准", "可以合入", "可以提交",
    "代码正确", "无风险", "reviewer 已启动", "review 已执行",
    "findings 已生成", "verdict 已生成", "已应用 patch",
    "已创建 worktree", "已执行 Git 写",
}

SOURCE_DIFF_FALSE_FLAGS = (
    "main_project_file_written", "sandbox_file_written", "manifest_file_written",
    "patch_applied", "product_runtime_git_write_allowed", "main_worktree_write_allowed",
    "worktree_write_allowed", "file_write_allowed", "actual_patch_applied",
    "real_code_modified", "git_write_performed", "native_executor_started",
    "codex_started", "claude_code_started", "worker_started",
    "task_created", "run_created", "worktree_created",
    "worktree_cleaned_up", "rollback_snapshot_created",
)


def _safe_dry_run_task(task_id=None) -> Task:
    return Task(
        id=task_id or uuid4(),
        title="P21-C-G test task",
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


def _valid_diff_entry(*, relative_path="src/a.py", operation="create",
                       unified_diff=None, diff_bytes=None):
    if unified_diff is None:
        unified_diff = f"--- /dev/null\n+++ b/{relative_path}\n+print('hello')\n"
    if diff_bytes is None:
        diff_bytes = len(unified_diff.encode("utf-8"))
    return {
        "relative_path": relative_path,
        "operation": operation,
        "target_file_path": f"/repo/{relative_path}",
        "candidate_file_path": f"/workspace/{relative_path}",
        "target_file_existed": operation == "update",
        "candidate_file_existed": True,
        "target_file_content_read": operation == "update",
        "candidate_file_content_read": True,
        "unified_diff": unified_diff,
        "diff_bytes": diff_bytes,
    }


def _valid_diff_action(task_id, *, entries=None, unified_diff_text=None, **overrides):
    if entries is None:
        entries = [_valid_diff_entry()]
    if unified_diff_text is None:
        unified_diff_text = "".join(e.get("unified_diff", "") for e in entries)
    action = {
        "type": P21_C_SANDBOX_CANDIDATE_DIFF_ACTION_TYPE,
        "source_task_id": str(task_id),
        "diff_generation_status": "generated",
        "workspace_path_within_root": True,
        "readonly_real_diff_generated": True,
        "real_diff_generated": True,
        "diff_file_count": len(entries),
        "diff_bytes": len(unified_diff_text.encode("utf-8")),
        "diff_entries": entries,
        "unified_diff_text": unified_diff_text,
        "target_file_content_read": any(e.get("target_file_content_read") for e in entries),
        "candidate_file_content_read": True,
        "ai_project_director_total_loop": "Partial",
        "main_project_file_written": False,
        "sandbox_file_written": False,
        "manifest_file_written": False,
        "patch_applied": False,
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
    }
    action.update(overrides)
    return action


def _build_service_and_result(session_id, task_id, action, *, user_confirmed=True):
    msg = _make_message(
        session_id, task_id, P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL, action,
    )
    service = ProjectDirectorSandboxCandidateDiffReviewHandoffService()
    result = service.build_candidate_diff_review_handoff_from_sources(
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=uuid4(),
        source_task=_safe_dry_run_task(task_id),
        source_message=msg,
        user_confirmed=user_confirmed,
    )
    return service, result, msg


# ══════════════════════════════════════════════════════════════════════
# 1. Successful created result
# ══════════════════════════════════════════════════════════════════════


class TestSuccessfulCreatedResult:
    def test_created_result_fields(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _valid_diff_action(task_id)
        _, result, _ = _build_service_and_result(session_id, task_id, action)

        assert result.review_handoff_status == "created"
        assert result.source_diff_message_bound is True
        assert result.source_diff_verified is True
        assert len(result.source_diff_sha256) == 64
        assert result.diff_file_count == 1
        assert result.diff_bytes > 0
        assert result.review_scope_paths == ["src/a.py"]
        assert result.reviewer_started is False
        assert result.review_executed is False
        assert result.review_findings_generated is False
        assert result.review_verdict_generated is False
        assert result.ai_project_director_total_loop == "Partial"
        for flag in SIDE_EFFECT_FLAGS:
            assert getattr(result, flag) is False, f"{flag} should be False"


# ══════════════════════════════════════════════════════════════════════
# 2. review_scope_paths
# ══════════════════════════════════════════════════════════════════════


class TestReviewScopePaths:
    def test_single_file(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _valid_diff_action(task_id)
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_scope_paths == ["src/a.py"]

    def test_multiple_files_preserve_order(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        entries = [
            _valid_diff_entry(relative_path="src/b.py"),
            _valid_diff_entry(relative_path="src/a.py"),
        ]
        action = _valid_diff_action(task_id, entries=entries)
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_scope_paths == ["src/b.py", "src/a.py"]

    def test_duplicate_paths_dedup_preserve_first_occurrence(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        entries = [
            _valid_diff_entry(relative_path="src/a.py"),
            _valid_diff_entry(relative_path="src/b.py"),
            _valid_diff_entry(relative_path="src/a.py"),
        ]
        action = _valid_diff_action(task_id, entries=entries)
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_scope_paths == ["src/a.py", "src/b.py"]


# ══════════════════════════════════════════════════════════════════════
# 3. SHA256 tests
# ══════════════════════════════════════════════════════════════════════


class TestSHA256:
    def test_sha256_stable(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _valid_diff_action(task_id)
        _, result1, _ = _build_service_and_result(session_id, task_id, action)
        _, result2, _ = _build_service_and_result(session_id, task_id, action)
        assert result1.source_diff_sha256 == result2.source_diff_sha256

    def test_sha256_changes_on_diff_change(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        diff1 = "--- /dev/null\n+++ b/src/a.py\n+hello\n"
        diff2 = "--- /dev/null\n+++ b/src/a.py\n+world\n"
        action1 = _valid_diff_action(task_id, entries=[_valid_diff_entry(unified_diff=diff1)],
                                      unified_diff_text=diff1)
        action2 = _valid_diff_action(task_id, entries=[_valid_diff_entry(unified_diff=diff2)],
                                      unified_diff_text=diff2)
        _, r1, _ = _build_service_and_result(session_id, task_id, action1)
        _, r2, _ = _build_service_and_result(session_id, task_id, action2)
        assert r1.source_diff_sha256 != r2.source_diff_sha256

    def test_sha256_blocked_is_empty(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _valid_diff_action(task_id, diff_generation_status="blocked")
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.source_diff_sha256 == ""

    def test_sha256_matches_hashlib(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        diff_text = "--- /dev/null\n+++ b/src/a.py\n+print('hello')\n"
        action = _valid_diff_action(task_id, entries=[_valid_diff_entry(unified_diff=diff_text)],
                                     unified_diff_text=diff_text)
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        expected = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
        assert result.source_diff_sha256 == expected

    def test_sha256_in_message_action(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _valid_diff_action(task_id)
        service, result, msg = _build_service_and_result(session_id, task_id, action)
        # The message action should contain the hash
        handoff_action = result  # we need to check via confirm path
        # Use confirm path to get the message
        class FakeMsgRepo:
            def get_by_id(self, mid):
                return msg
            def get_next_sequence_no(self, session_id):
                return 100
            def create(self, m):
                return m
            def commit(self):
                pass
        class FakeSessionRepo:
            def get_by_id(self, sid):
                return type("S", (), {"project_id": uuid4()})()
        class FakeTaskRepo:
            def get_by_id(self, tid):
                return _safe_dry_run_task(tid)

        svc = ProjectDirectorSandboxCandidateDiffReviewHandoffService(
            session_repository=FakeSessionRepo(),
            message_repository=FakeMsgRepo(),
            task_repository=FakeTaskRepo(),
        )
        confirmed = svc.confirm_candidate_diff_review_handoff(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            user_confirmed=True,
        )
        assert confirmed.result.source_diff_sha256 == result.source_diff_sha256


class TestSHA256UTF8:
    def test_chinese_diff_sha256_uses_utf8_bytes(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        diff_text = "--- /dev/null\n+++ b/src/a.py\n+你好，AI 主管\n"
        action = _valid_diff_action(task_id, entries=[_valid_diff_entry(unified_diff=diff_text)],
                                     unified_diff_text=diff_text)
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        expected = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
        assert result.source_diff_sha256 == expected
        assert result.diff_bytes == len(diff_text.encode("utf-8"))


# ══════════════════════════════════════════════════════════════════════
# 4. Diff integrity blocked tests
# ══════════════════════════════════════════════════════════════════════


class TestDiffIntegrityBlocked:
    def test_user_confirmed_false(self) -> None:
        service = ProjectDirectorSandboxCandidateDiffReviewHandoffService()
        result = service.build_candidate_diff_review_handoff_from_sources(
            session_id=uuid4(), source_task_id=uuid4(), source_message_id=uuid4(),
            source_task=None, source_message=None, user_confirmed=False,
        )
        assert result.review_handoff_status == "blocked"
        assert "user_confirmation_required" in result.blocked_reasons

    def test_source_task_missing(self) -> None:
        service = ProjectDirectorSandboxCandidateDiffReviewHandoffService()
        result = service.build_candidate_diff_review_handoff_from_sources(
            session_id=uuid4(), source_task_id=uuid4(), source_message_id=uuid4(),
            source_task=None, source_message=None, user_confirmed=True,
        )
        assert result.review_handoff_status == "blocked"
        assert "source_task_missing" in result.blocked_reasons

    def test_source_task_not_safe_dry_run(self) -> None:
        bad = Task(id=uuid4(), title="bad", source_draft_id="bad",
                   input_summary="not safe", acceptance_criteria=[])
        service = ProjectDirectorSandboxCandidateDiffReviewHandoffService()
        result = service.build_candidate_diff_review_handoff_from_sources(
            session_id=uuid4(), source_task_id=bad.id, source_message_id=uuid4(),
            source_task=bad, source_message=None, user_confirmed=True,
        )
        assert result.review_handoff_status == "blocked"
        assert "source_task_not_safe_dry_run" in result.blocked_reasons

    def test_source_message_missing(self) -> None:
        service = ProjectDirectorSandboxCandidateDiffReviewHandoffService()
        result = service.build_candidate_diff_review_handoff_from_sources(
            session_id=uuid4(), source_task_id=uuid4(), source_message_id=uuid4(),
            source_task=_safe_dry_run_task(), source_message=None, user_confirmed=True,
        )
        assert result.review_handoff_status == "blocked"
        assert "source_message_missing" in result.blocked_reasons

    def test_non_p21_c_f_source_detail(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        msg = _make_message(session_id, task_id, "wrong_source", {"type": "wrong"})
        service = ProjectDirectorSandboxCandidateDiffReviewHandoffService()
        result = service.build_candidate_diff_review_handoff_from_sources(
            session_id=session_id, source_task_id=task_id, source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id), source_message=msg, user_confirmed=True,
        )
        assert result.review_handoff_status == "blocked"
        assert "source_message_is_not_p21_c_candidate_diff_generated" in result.blocked_reasons

    def test_wrong_action_type(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        msg = _make_message(session_id, task_id, P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL,
                            {"type": "wrong_type"})
        service = ProjectDirectorSandboxCandidateDiffReviewHandoffService()
        result = service.build_candidate_diff_review_handoff_from_sources(
            session_id=session_id, source_task_id=task_id, source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_id), source_message=msg, user_confirmed=True,
        )
        assert result.review_handoff_status == "blocked"
        assert "p21_c_candidate_diff_generate_record_missing" in result.blocked_reasons

    def test_source_task_mismatch(self) -> None:
        session_id = uuid4()
        task_a = uuid4()
        task_b = uuid4()
        action = _valid_diff_action(task_b)
        msg = _make_message(session_id, task_b, P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL, action)
        service = ProjectDirectorSandboxCandidateDiffReviewHandoffService()
        result = service.build_candidate_diff_review_handoff_from_sources(
            session_id=session_id, source_task_id=task_a, source_message_id=uuid4(),
            source_task=_safe_dry_run_task(task_a), source_message=msg, user_confirmed=True,
        )
        assert result.review_handoff_status == "blocked"
        assert "source_task_not_bound_to_candidate_diff" in result.blocked_reasons

    def test_diff_generation_status_not_generated(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _valid_diff_action(task_id, diff_generation_status="blocked")
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"
        assert "source_diff_not_generated" in result.blocked_reasons

    def test_readonly_real_diff_generated_false(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _valid_diff_action(task_id, readonly_real_diff_generated=False)
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"
        assert "source_diff_not_readonly" in result.blocked_reasons

    def test_real_diff_generated_false(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _valid_diff_action(task_id, real_diff_generated=False)
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"
        assert "source_diff_not_readonly" in result.blocked_reasons

    def test_diff_file_count_zero(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _valid_diff_action(task_id, diff_file_count=0)
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"

    def test_diff_bytes_zero(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _valid_diff_action(task_id, diff_bytes=0)
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"

    def test_unified_diff_text_empty(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _valid_diff_action(task_id, unified_diff_text="")
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"

    def test_workspace_path_within_root_false(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _valid_diff_action(task_id, workspace_path_within_root=False)
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"

    def test_total_loop_not_partial(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _valid_diff_action(task_id, ai_project_director_total_loop="Full")
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"
        assert "source_diff_write_boundary_violated" in result.blocked_reasons


class TestWriteBoundaryViolations:
    @pytest.mark.parametrize("flag", [
        "main_project_file_written", "sandbox_file_written", "manifest_file_written",
        "patch_applied", "git_write_performed", "native_executor_started",
        "codex_started", "claude_code_started", "worker_started",
        "task_created", "run_created", "worktree_created",
    ])
    def test_write_flag_violation(self, flag) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _valid_diff_action(task_id, **{flag: True})
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"
        assert "source_diff_write_boundary_violated" in result.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# 5. diff_file_count integrity
# ══════════════════════════════════════════════════════════════════════


class TestDiffFileCountIntegrity:
    def test_entries_2_count_1_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        entries = [
            _valid_diff_entry(relative_path="src/a.py"),
            _valid_diff_entry(relative_path="src/b.py"),
        ]
        action = _valid_diff_action(task_id, entries=entries, diff_file_count=1)
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"
        assert "source_diff_file_count_mismatch" in result.blocked_reasons

    def test_entries_1_count_2_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        entries = [_valid_diff_entry()]
        action = _valid_diff_action(task_id, entries=entries, diff_file_count=2)
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"
        assert "source_diff_file_count_mismatch" in result.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# 6. total diff_bytes integrity
# ══════════════════════════════════════════════════════════════════════


class TestDiffBytesIntegrity:
    def test_bytes_mismatch_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _valid_diff_action(task_id, diff_bytes=999)
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"
        assert "source_diff_bytes_mismatch" in result.blocked_reasons

    def test_chinese_diff_bytes_uses_utf8(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        diff_text = "--- /dev/null\n+++ b/src/a.py\n+你好\n"
        action = _valid_diff_action(
            task_id,
            entries=[_valid_diff_entry(unified_diff=diff_text)],
            unified_diff_text=diff_text,
        )
        # The diff_bytes in action is set correctly by _valid_diff_action
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "created"
        assert result.diff_bytes == len(diff_text.encode("utf-8"))


# ══════════════════════════════════════════════════════════════════════
# 7. entry.diff_bytes integrity
# ══════════════════════════════════════════════════════════════════════


class TestEntryDiffBytesIntegrity:
    def test_entry_bytes_mismatch_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        entry = _valid_diff_entry()
        entry["diff_bytes"] = 999  # tamper
        action = _valid_diff_action(task_id, entries=[entry])
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"
        assert "source_diff_entry_bytes_mismatch" in result.blocked_reasons

    def test_chinese_entry_bytes_uses_utf8(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        diff_text = "--- /dev/null\n+++ b/src/a.py\n+你好，AI 主管\n"
        entry = _valid_diff_entry(unified_diff=diff_text)
        action = _valid_diff_action(
            task_id, entries=[entry], unified_diff_text=diff_text,
        )
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "created"


# ══════════════════════════════════════════════════════════════════════
# 8. diff aggregation integrity
# ══════════════════════════════════════════════════════════════════════


class TestDiffAggregationIntegrity:
    def test_order_swap_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        e1 = _valid_diff_entry(relative_path="src/a.py", unified_diff="diff-a\n")
        e2 = _valid_diff_entry(relative_path="src/b.py", unified_diff="diff-b\n")
        # Correct aggregation would be "diff-a\ndiff-b\n"
        # But we pass reversed
        action = _valid_diff_action(
            task_id, entries=[e1, e2], unified_diff_text="diff-b\ndiff-a\n",
        )
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"
        assert "source_diff_aggregation_mismatch" in result.blocked_reasons

    def test_truncated_aggregation_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        e1 = _valid_diff_entry(unified_diff="diff-a\ndiff-b\n")
        action = _valid_diff_action(
            task_id, entries=[e1], unified_diff_text="diff-a\ndiff-",  # truncated
        )
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"
        assert "source_diff_aggregation_mismatch" in result.blocked_reasons

    def test_extra_content_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        e1 = _valid_diff_entry(unified_diff="diff-a\n")
        action = _valid_diff_action(
            task_id, entries=[e1], unified_diff_text="diff-a\nextra\n",
        )
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"
        assert "source_diff_aggregation_mismatch" in result.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# 9. Entry schema / semantic validation
# ══════════════════════════════════════════════════════════════════════


class TestEntrySchemaValidation:
    def test_missing_required_field_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        for field in ["relative_path", "operation", "target_file_path", "candidate_file_path",
                       "target_file_existed", "candidate_file_existed", "target_file_content_read",
                       "candidate_file_content_read", "unified_diff", "diff_bytes"]:
            entry = _valid_diff_entry()
            del entry[field]
            action = _valid_diff_action(task_id, entries=[entry])
            _, result, _ = _build_service_and_result(session_id, task_id, action)
            assert result.review_handoff_status == "blocked", f"Missing {field} should block"
            assert "source_diff_entry_invalid" in result.blocked_reasons

    def test_delete_operation_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        entry = _valid_diff_entry(operation="delete")
        action = _valid_diff_action(task_id, entries=[entry])
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"
        assert "source_diff_entry_invalid" in result.blocked_reasons

    def test_candidate_file_existed_false_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        entry = _valid_diff_entry()
        entry["candidate_file_existed"] = False
        action = _valid_diff_action(task_id, entries=[entry])
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"
        assert "source_diff_entry_invalid" in result.blocked_reasons

    def test_candidate_file_content_read_false_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        entry = _valid_diff_entry()
        entry["candidate_file_content_read"] = False
        action = _valid_diff_action(task_id, entries=[entry])
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"
        assert "source_diff_entry_invalid" in result.blocked_reasons

    def test_empty_relative_path_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        entry = _valid_diff_entry()
        entry["relative_path"] = ""
        action = _valid_diff_action(task_id, entries=[entry])
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"
        assert "source_diff_entry_invalid" in result.blocked_reasons

    def test_empty_unified_diff_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        entry = _valid_diff_entry()
        entry["unified_diff"] = ""
        action = _valid_diff_action(task_id, entries=[entry])
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"
        assert "source_diff_entry_invalid" in result.blocked_reasons

    def test_create_entry_target_existed_true_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        entry = _valid_diff_entry(operation="create")
        entry["target_file_existed"] = True  # wrong for create
        action = _valid_diff_action(task_id, entries=[entry])
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"
        assert "source_diff_entry_invalid" in result.blocked_reasons

    def test_create_entry_target_content_read_true_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        entry = _valid_diff_entry(operation="create")
        entry["target_file_content_read"] = True  # wrong for create
        action = _valid_diff_action(task_id, entries=[entry])
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"
        assert "source_diff_entry_invalid" in result.blocked_reasons

    def test_update_entry_target_existed_false_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        entry = _valid_diff_entry(operation="update")
        entry["target_file_existed"] = False  # wrong for update
        action = _valid_diff_action(task_id, entries=[entry])
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"
        assert "source_diff_entry_invalid" in result.blocked_reasons

    def test_update_entry_target_content_read_false_blocked(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        entry = _valid_diff_entry(operation="update")
        entry["target_file_content_read"] = False  # wrong for update
        action = _valid_diff_action(task_id, entries=[entry])
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "blocked"
        assert "source_diff_entry_invalid" in result.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# 10. Domain validator
# ══════════════════════════════════════════════════════════════════════


class TestDomainValidatorRejectsTrueFlags:
    @pytest.mark.parametrize("field_name", SIDE_EFFECT_FLAGS)
    def test_rejects_true_flag(self, field_name: str) -> None:
        with pytest.raises(ValidationError, match="may not review, write, or execute"):
            ProjectDirectorSandboxCandidateDiffReviewHandoffResult(
                review_handoff_status="created",
                session_id=uuid4(),
                review_handoff_summary="test",
                recommended_next_step="next",
                **{field_name: True},
            )


# ══════════════════════════════════════════════════════════════════════
# 11. P21-C-G does not re-read files
# ══════════════════════════════════════════════════════════════════════


class TestNoFileReRead:
    def test_handoff_succeeds_with_path_read_text_blocked(self, monkeypatch) -> None:
        """P21-C-G only consumes message evidence, never reads files."""
        from pathlib import Path
        original = Path.read_text

        def failing_read_text(self, *args, **kwargs):
            raise AssertionError("P21-C-G must not read files!")

        monkeypatch.setattr(Path, "read_text", failing_read_text)

        session_id = uuid4()
        task_id = uuid4()
        action = _valid_diff_action(task_id)
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.review_handoff_status == "created"


# ══════════════════════════════════════════════════════════════════════
# 12. No reviewer started
# ══════════════════════════════════════════════════════════════════════


class TestNoReviewerStarted:
    def test_review_flags_all_false(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _valid_diff_action(task_id)
        _, result, _ = _build_service_and_result(session_id, task_id, action)
        assert result.reviewer_started is False
        assert result.review_executed is False
        assert result.review_findings_generated is False
        assert result.review_verdict_generated is False

    def test_success_message_is_handoff_not_review(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        action = _valid_diff_action(task_id)
        msg = _make_message(
            session_id, task_id, P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL, action,
        )

        class FakeMsgRepo:
            def get_by_id(self, mid):
                return msg
            def get_next_sequence_no(self, session_id):
                return 100
            def create(self, m):
                return m
            def commit(self):
                pass
        class FakeSessionRepo:
            def get_by_id(self, sid):
                return type("S", (), {"project_id": uuid4()})()
        class FakeTaskRepo:
            def get_by_id(self, tid):
                return _safe_dry_run_task(tid)

        svc = ProjectDirectorSandboxCandidateDiffReviewHandoffService(
            session_repository=FakeSessionRepo(),
            message_repository=FakeMsgRepo(),
            task_repository=FakeTaskRepo(),
        )
        confirmed = svc.confirm_candidate_diff_review_handoff(
            session_id=session_id,
            source_task_id=task_id,
            source_message_id=uuid4(),
            user_confirmed=True,
        )
        assert confirmed.message is not None
        assert confirmed.message.source_detail == P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_SOURCE_DETAIL


# ══════════════════════════════════════════════════════════════════════
# 13. Output no misleading terms
# ══════════════════════════════════════════════════════════════════════


class TestOutputNoMisleadingTerms:
    def test_result_excludes_misleading_terms(self) -> None:
        result = ProjectDirectorSandboxCandidateDiffReviewHandoffResult(
            review_handoff_status="blocked",
            session_id=uuid4(),
            review_handoff_summary="blocked",
            recommended_next_step="next",
        )
        serialized = result.model_dump_json()
        for term in MISLEADING_TERMS:
            assert term not in serialized, f"Found misleading term: {term}"
