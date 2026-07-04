"""Contract tests for P21-C-H-A readonly review execution preflight."""

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
from app.domain.project_director_sandbox_candidate_diff_review_execution_preflight import (
    ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightResult,
)
from app.domain.task import Task
from app.services.project_director_sandbox_candidate_diff_review_execution_preflight_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_EXECUTION_PREFLIGHT_SOURCE_DETAIL,
    REVIEW_INPUT_SCHEMA_VERSION,
    REVIEW_OUTPUT_SCHEMA_VERSION,
    ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService,
)
from app.services.project_director_sandbox_candidate_diff_review_handoff_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_candidate_diff_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL,
)


SIDE_EFFECT_FLAGS = [
    "reviewer_started", "review_executed", "review_findings_generated",
    "review_verdict_generated", "provider_called", "native_executor_started",
    "codex_started", "claude_code_started", "main_project_file_written",
    "sandbox_file_written", "manifest_file_written", "diff_file_written",
    "patch_applied", "product_runtime_git_write_allowed", "git_write_performed",
    "worktree_created", "worker_started", "task_created", "run_created",
]

MISLEADING_TERMS = {
    "审查通过", "review passed", "已批准", "可以合入", "可以提交",
    "代码正确", "无风险", "reviewer 已启动", "review 已执行",
    "findings 已生成", "verdict 已生成", "已应用 patch",
    "已创建 worktree", "已执行 Git 写",
}


def _safe_dry_run_task(task_id=None) -> Task:
    return Task(
        id=task_id or uuid4(),
        title="P21-C-H-A test task",
        source_draft_id="p12-test",
        input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
        acceptance_criteria=[
            "safe_dry_run_task=true", "worker_simulate_required=true",
            "product_runtime_git_write_allowed=false", "native_executor_started=false",
            "codex_started=false", "claude_code_started=false",
        ],
    )


def _make_message(session_id, task_id, source_detail, action, *, sequence_no=1):
    return ProjectDirectorMessage(
        id=uuid4(), session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT, content="test",
        sequence_no=sequence_no, intent="test",
        related_project_id=uuid4(), related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=source_detail, suggested_actions=[action],
    )


def _valid_diff_entry(*, relative_path="src/a.py", operation="create",
                       unified_diff=None, diff_bytes=None):
    if unified_diff is None:
        unified_diff = f"--- /dev/null\n+++ b/{relative_path}\n+print('hello')\n"
    if diff_bytes is None:
        diff_bytes = len(unified_diff.encode("utf-8"))
    return {
        "relative_path": relative_path, "operation": operation,
        "target_file_path": f"/repo/{relative_path}",
        "candidate_file_path": f"/workspace/{relative_path}",
        "target_file_existed": operation == "update",
        "candidate_file_existed": True,
        "target_file_content_read": operation == "update",
        "candidate_file_content_read": True,
        "unified_diff": unified_diff, "diff_bytes": diff_bytes,
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
        "main_project_file_written": False, "sandbox_file_written": False,
        "manifest_file_written": False, "patch_applied": False,
        "product_runtime_git_write_allowed": False, "main_worktree_write_allowed": False,
        "worktree_write_allowed": False, "file_write_allowed": False,
        "actual_patch_applied": False, "real_code_modified": False,
        "git_write_performed": False, "native_executor_started": False,
        "codex_started": False, "claude_code_started": False,
        "worker_started": False, "task_created": False, "run_created": False,
        "worktree_created": False, "worktree_cleaned_up": False,
        "rollback_snapshot_created": False, "cleanup_required": False,
        "controlled_sandbox_write_enabled": False, "sandbox_write_allowed": False,
        "product_runtime_git_write_allowed": False, "main_worktree_write_allowed": False,
        "worktree_write_allowed": False, "file_write_allowed": False,
    }
    action.update(overrides)
    return action


def _valid_handoff_action(task_id, *, diff_action=None, source_diff_message_id=None,
                           review_scope_paths=None, **overrides):
    if diff_action is None:
        diff_action = _valid_diff_action(task_id)
    entries = diff_action.get("diff_entries", [])
    if review_scope_paths is None:
        seen: set[str] = set()
        review_scope_paths = []
        for e in entries:
            rp = e.get("relative_path", "")
            if rp and rp not in seen:
                review_scope_paths.append(rp)
                seen.add(rp)
    unified = diff_action.get("unified_diff_text", "")
    action = {
        "type": P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_ACTION_TYPE,
        "source_task_id": str(task_id),
        "review_handoff_status": "created",
        "source_diff_message_bound": True,
        "source_diff_verified": True,
        "source_diff_sha256": hashlib.sha256(unified.encode("utf-8")).hexdigest(),
        "diff_file_count": diff_action.get("diff_file_count", len(entries)),
        "diff_bytes": diff_action.get("diff_bytes", len(unified.encode("utf-8"))),
        "review_scope_paths": review_scope_paths,
        "requested_reviewer_executor": "codex",
        "source_diff_message_id": str(source_diff_message_id) if source_diff_message_id else str(uuid4()),
        "reviewer_started": False, "review_executed": False,
        "review_findings_generated": False, "review_verdict_generated": False,
        "main_project_file_written": False, "sandbox_file_written": False,
        "manifest_file_written": False, "diff_file_written": False,
        "patch_applied": False, "git_write_performed": False,
        "native_executor_started": False, "codex_started": False,
        "claude_code_started": False, "worker_started": False,
        "task_created": False, "run_created": False, "worktree_created": False,
        "worktree_cleaned_up": False, "rollback_snapshot_created": False,
        "ai_project_director_total_loop": "Partial",
    }
    action.update(overrides)
    return action


def _build_messages_and_service(session_id, task_id, *, diff_action=None,
                                 handoff_action=None, diff_entries=None,
                                 review_scope_paths=None, **handoff_overrides):
    if diff_action is None:
        diff_action = _valid_diff_action(task_id, entries=diff_entries)
    diff_msg_id = uuid4()
    diff_msg = _make_message(
        session_id, task_id, P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL,
        diff_action, sequence_no=1,
    )
    diff_msg = ProjectDirectorMessage(
        id=diff_msg_id, session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT, content="t", sequence_no=1,
        intent="t", related_project_id=uuid4(), related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL,
        suggested_actions=[diff_action],
    )

    if handoff_action is None:
        handoff_action = _valid_handoff_action(
            task_id, diff_action=diff_action,
            source_diff_message_id=diff_msg_id,
            review_scope_paths=review_scope_paths, **handoff_overrides,
        )
    handoff_msg_id = uuid4()
    handoff_msg = ProjectDirectorMessage(
        id=handoff_msg_id, session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT, content="t", sequence_no=2,
        intent="t", related_project_id=uuid4(), related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_SOURCE_DETAIL,
        suggested_actions=[handoff_action],
    )

    messages = {diff_msg_id: diff_msg, handoff_msg_id: handoff_msg}

    class FakeMsgRepo:
        def get_by_id(self, mid):
            return messages.get(mid)
        def get_next_sequence_no(self, sid):
            return 100
        def create(self, m):
            return m
        def commit(self):
            pass
    class FakeSessionRepo:
        def get_by_id(self, sid):
            if sid == session_id:
                return type("S", (), {"project_id": uuid4()})()
            return None
    class FakeTaskRepo:
        def get_by_id(self, tid):
            if tid == task_id:
                return _safe_dry_run_task(task_id)
            return None

    service = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService(
        session_repository=FakeSessionRepo(),
        message_repository=FakeMsgRepo(),
        task_repository=FakeTaskRepo(),
    )
    return service, handoff_msg_id, diff_msg_id


# ══════════════════════════════════════════════════════════════════════
# 1. Ready path
# ══════════════════════════════════════════════════════════════════════


class TestReadyPath:
    def test_ready_result_fields(self) -> None:
        session_id = uuid4()
        task_id = uuid4()
        service, handoff_msg_id, _ = _build_messages_and_service(session_id, task_id)
        result = service.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=session_id, source_task_id=task_id,
            source_message_id=handoff_msg_id,
            source_task=_safe_dry_run_task(task_id),
            source_handoff_message=service._message_repository.get_by_id(handoff_msg_id),
            user_confirmed=True,
        )
        assert result.review_execution_preflight_status == "ready"
        assert result.source_handoff_verified is True
        assert result.source_diff_verified is True
        assert len(result.source_diff_sha256) == 64
        assert len(result.review_prompt_sha256) == 64
        assert result.review_prompt_bytes > 0
        assert result.review_input_schema_version == REVIEW_INPUT_SCHEMA_VERSION
        assert result.review_output_schema_version == REVIEW_OUTPUT_SCHEMA_VERSION
        assert result.review_scope_paths == ["src/a.py"]
        assert result.ai_project_director_total_loop == "Partial"
        for flag in SIDE_EFFECT_FLAGS:
            assert getattr(result, flag) is False, f"{flag} should be False"


# ══════════════════════════════════════════════════════════════════════
# 2. G → F evidence binding blocked
# ══════════════════════════════════════════════════════════════════════


class TestEvidenceBindingBlocked:
    def test_user_confirmed_false(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService()
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=uuid4(), source_task_id=uuid4(), source_message_id=uuid4(),
            source_task=None, source_handoff_message=None, user_confirmed=False,
        )
        assert r.review_execution_preflight_status == "blocked"
        assert "user_confirmation_required" in r.blocked_reasons

    def test_source_task_missing(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService()
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=uuid4(), source_task_id=uuid4(), source_message_id=uuid4(),
            source_task=None, source_handoff_message=None, user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "blocked"
        assert "source_task_missing" in r.blocked_reasons

    def test_unsafe_task(self) -> None:
        bad = Task(id=uuid4(), title="bad", source_draft_id="bad",
                   input_summary="not safe", acceptance_criteria=[])
        svc = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService()
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=uuid4(), source_task_id=bad.id, source_message_id=uuid4(),
            source_task=bad, source_handoff_message=None, user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "blocked"
        assert "source_task_not_safe_dry_run" in r.blocked_reasons

    def test_g_message_missing(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService()
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=uuid4(), source_task_id=uuid4(), source_message_id=uuid4(),
            source_task=_safe_dry_run_task(), source_handoff_message=None, user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "blocked"
        assert "source_handoff_message_missing" in r.blocked_reasons

    def test_g_source_detail_wrong(self) -> None:
        sid, tid = uuid4(), uuid4()
        msg = _make_message(sid, tid, "wrong_source", {"type": "wrong"})
        svc = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService()
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=uuid4(),
            source_task=_safe_dry_run_task(tid), source_handoff_message=msg, user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "blocked"
        assert "source_message_is_not_p21_c_review_handoff" in r.blocked_reasons

    def test_g_action_type_wrong(self) -> None:
        sid, tid = uuid4(), uuid4()
        msg = _make_message(sid, tid, P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_SOURCE_DETAIL,
                            {"type": "wrong_type"})
        svc = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService()
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=uuid4(),
            source_task=_safe_dry_run_task(tid), source_handoff_message=msg, user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "blocked"
        assert "p21_c_review_handoff_record_missing" in r.blocked_reasons

    def test_g_source_task_mismatch(self) -> None:
        sid, tid_a, tid_b = uuid4(), uuid4(), uuid4()
        action = _valid_handoff_action(tid_b)
        msg = _make_message(sid, tid_b, P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_SOURCE_DETAIL, action)
        svc = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService()
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid_a, source_message_id=uuid4(),
            source_task=_safe_dry_run_task(tid_a), source_handoff_message=msg, user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "blocked"
        assert "source_task_not_bound_to_review_handoff" in r.blocked_reasons

    def test_g_status_not_created(self) -> None:
        sid, tid = uuid4(), uuid4()
        action = _valid_handoff_action(tid, review_handoff_status="blocked")
        msg = _make_message(sid, tid, P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_SOURCE_DETAIL, action)
        svc = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService()
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=uuid4(),
            source_task=_safe_dry_run_task(tid), source_handoff_message=msg, user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "blocked"
        assert "source_handoff_not_created" in r.blocked_reasons

    def test_g_diff_not_verified(self) -> None:
        sid, tid = uuid4(), uuid4()
        action = _valid_handoff_action(tid, source_diff_verified=False)
        msg = _make_message(sid, tid, P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_SOURCE_DETAIL, action)
        svc = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService()
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=uuid4(),
            source_task=_safe_dry_run_task(tid), source_handoff_message=msg, user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "blocked"
        assert "source_handoff_not_verified" in r.blocked_reasons

    def test_g_write_boundary_violation(self) -> None:
        sid, tid = uuid4(), uuid4()
        action = _valid_handoff_action(tid, reviewer_started=True)
        msg = _make_message(sid, tid, P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_SOURCE_DETAIL, action)
        svc = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService()
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=uuid4(),
            source_task=_safe_dry_run_task(tid), source_handoff_message=msg, user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "blocked"
        assert "source_handoff_write_boundary_violated" in r.blocked_reasons

    def test_f_message_missing(self) -> None:
        sid, tid = uuid4(), uuid4()
        action = _valid_handoff_action(tid, source_diff_message_id=uuid4())
        msg = _make_message(sid, tid, P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_SOURCE_DETAIL, action)
        # FakeMsgRepo returns None for unknown IDs
        class FakeMsgRepo:
            def get_by_id(self, mid):
                return msg if mid == msg.id else None
            def get_next_sequence_no(self, sid):
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
        svc = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService(
            session_repository=FakeSessionRepo(),
            message_repository=FakeMsgRepo(),
            task_repository=FakeTaskRepo(),
        )
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=msg.id,
            source_task=_safe_dry_run_task(tid), source_handoff_message=msg, user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "blocked"
        assert "source_diff_message_missing" in r.blocked_reasons

    def test_f_source_detail_wrong(self) -> None:
        sid, tid = uuid4(), uuid4()
        diff_action = _valid_diff_action(tid)
        diff_msg = _make_message(sid, tid, "wrong_source", diff_action)
        diff_msg_id = diff_msg.id
        handoff_action = _valid_handoff_action(tid, source_diff_message_id=diff_msg_id)
        handoff_msg = _make_message(sid, tid, P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_SOURCE_DETAIL, handoff_action)
        msgs = {diff_msg_id: diff_msg, handoff_msg.id: handoff_msg}
        class FakeMsgRepo:
            def get_by_id(self, mid):
                return msgs.get(mid)
            def get_next_sequence_no(self, sid):
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
        svc = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService(
            session_repository=FakeSessionRepo(),
            message_repository=FakeMsgRepo(),
            task_repository=FakeTaskRepo(),
        )
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=handoff_msg.id,
            source_task=_safe_dry_run_task(tid), source_handoff_message=handoff_msg, user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "blocked"
        assert "source_diff_message_is_not_p21_c_candidate_diff_generated" in r.blocked_reasons

    def test_f_diff_status_not_generated(self) -> None:
        sid, tid = uuid4(), uuid4()
        svc, hid, _ = _build_messages_and_service(
            sid, tid,
            diff_action=_valid_diff_action(tid, diff_generation_status="blocked"),
        )
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=hid,
            source_task=_safe_dry_run_task(tid),
            source_handoff_message=svc._message_repository.get_by_id(hid),
            user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "blocked"
        assert "source_diff_not_generated" in r.blocked_reasons

    def test_f_readonly_false(self) -> None:
        sid, tid = uuid4(), uuid4()
        svc, hid, _ = _build_messages_and_service(
            sid, tid,
            diff_action=_valid_diff_action(tid, readonly_real_diff_generated=False),
        )
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=hid,
            source_task=_safe_dry_run_task(tid),
            source_handoff_message=svc._message_repository.get_by_id(hid),
            user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "blocked"

    def test_f_write_boundary_violation(self) -> None:
        sid, tid = uuid4(), uuid4()
        svc, hid, _ = _build_messages_and_service(
            sid, tid,
            diff_action=_valid_diff_action(tid, main_project_file_written=True),
        )
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=hid,
            source_task=_safe_dry_run_task(tid),
            source_handoff_message=svc._message_repository.get_by_id(hid),
            user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "blocked"
        assert "source_diff_write_boundary_violated" in r.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# 3. SHA256 tests
# ══════════════════════════════════════════════════════════════════════


class TestSHA256:
    def test_correct_hash_ready(self) -> None:
        sid, tid = uuid4(), uuid4()
        svc, hid, _ = _build_messages_and_service(sid, tid)
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=hid,
            source_task=_safe_dry_run_task(tid),
            source_handoff_message=svc._message_repository.get_by_id(hid),
            user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "ready"
        assert len(r.source_diff_sha256) == 64

    def test_hash_mismatch_blocked(self) -> None:
        sid, tid = uuid4(), uuid4()
        diff_action = _valid_diff_action(tid)
        diff_text = diff_action["unified_diff_text"]
        wrong_hash = hashlib.sha256((diff_text + "x").encode("utf-8")).hexdigest()
        svc, hid, _ = _build_messages_and_service(
            sid, tid, diff_action=diff_action,
            source_diff_sha256=wrong_hash,
        )
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=hid,
            source_task=_safe_dry_run_task(tid),
            source_handoff_message=svc._message_repository.get_by_id(hid),
            user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "blocked"
        assert "source_diff_sha256_mismatch" in r.blocked_reasons

    def test_hash_not_64_chars_blocked(self) -> None:
        sid, tid = uuid4(), uuid4()
        svc, hid, _ = _build_messages_and_service(
            sid, tid, source_diff_sha256="tooshort",
        )
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=hid,
            source_task=_safe_dry_run_task(tid),
            source_handoff_message=svc._message_repository.get_by_id(hid),
            user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "blocked"
        assert "source_diff_sha256_invalid" in r.blocked_reasons

    def test_uppercase_hex_blocked(self) -> None:
        sid, tid = uuid4(), uuid4()
        diff_action = _valid_diff_action(tid)
        diff_text = diff_action["unified_diff_text"]
        upper_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest().upper()
        svc, hid, _ = _build_messages_and_service(
            sid, tid, diff_action=diff_action, source_diff_sha256=upper_hash,
        )
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=hid,
            source_task=_safe_dry_run_task(tid),
            source_handoff_message=svc._message_repository.get_by_id(hid),
            user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "blocked"
        assert "source_diff_sha256_invalid" in r.blocked_reasons

    def test_chinese_diff_utf8_hash(self) -> None:
        sid, tid = uuid4(), uuid4()
        diff_text = "--- /dev/null\n+++ b/src/a.py\n+你好，AI 主管\n"
        entries = [_valid_diff_entry(unified_diff=diff_text)]
        svc, hid, _ = _build_messages_and_service(
            sid, tid,
            diff_action=_valid_diff_action(tid, entries=entries, unified_diff_text=diff_text),
        )
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=hid,
            source_task=_safe_dry_run_task(tid),
            source_handoff_message=svc._message_repository.get_by_id(hid),
            user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "ready"
        expected = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
        assert r.source_diff_sha256 == expected


# ══════════════════════════════════════════════════════════════════════
# 4. Stable dedupe review scope
# ══════════════════════════════════════════════════════════════════════


class TestStableDedupeReviewScope:
    def test_single_file(self) -> None:
        sid, tid = uuid4(), uuid4()
        entries = [_valid_diff_entry(relative_path="src/a.py")]
        svc, hid, _ = _build_messages_and_service(sid, tid, diff_entries=entries)
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=hid,
            source_task=_safe_dry_run_task(tid),
            source_handoff_message=svc._message_repository.get_by_id(hid),
            user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "ready"
        assert r.review_scope_paths == ["src/a.py"]

    def test_multiple_files_preserve_order(self) -> None:
        sid, tid = uuid4(), uuid4()
        entries = [
            _valid_diff_entry(relative_path="src/b.py"),
            _valid_diff_entry(relative_path="src/a.py"),
        ]
        svc, hid, _ = _build_messages_and_service(sid, tid, diff_entries=entries)
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=hid,
            source_task=_safe_dry_run_task(tid),
            source_handoff_message=svc._message_repository.get_by_id(hid),
            user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "ready"
        assert r.review_scope_paths == ["src/b.py", "src/a.py"]

    def test_duplicate_path_dedup_preserve_first(self) -> None:
        sid, tid = uuid4(), uuid4()
        entries = [
            _valid_diff_entry(relative_path="src/a.py"),
            _valid_diff_entry(relative_path="src/b.py"),
            _valid_diff_entry(relative_path="src/a.py"),
        ]
        # F scope should be ["src/a.py", "src/b.py"] (deduped)
        # G must match
        svc, hid, _ = _build_messages_and_service(
            sid, tid, diff_entries=entries,
            review_scope_paths=["src/a.py", "src/b.py"],
        )
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=hid,
            source_task=_safe_dry_run_task(tid),
            source_handoff_message=svc._message_repository.get_by_id(hid),
            user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "ready"
        assert r.review_scope_paths == ["src/a.py", "src/b.py"]

    def test_scope_order_swapped_blocked(self) -> None:
        sid, tid = uuid4(), uuid4()
        entries = [
            _valid_diff_entry(relative_path="src/a.py"),
            _valid_diff_entry(relative_path="src/b.py"),
        ]
        # G has wrong order
        svc, hid, _ = _build_messages_and_service(
            sid, tid, diff_entries=entries,
            review_scope_paths=["src/b.py", "src/a.py"],
        )
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=hid,
            source_task=_safe_dry_run_task(tid),
            source_handoff_message=svc._message_repository.get_by_id(hid),
            user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "blocked"
        assert "review_scope_paths_missing" in r.blocked_reasons

    def test_scope_missing_path_blocked(self) -> None:
        sid, tid = uuid4(), uuid4()
        entries = [
            _valid_diff_entry(relative_path="src/a.py"),
            _valid_diff_entry(relative_path="src/b.py"),
        ]
        # G only has one path
        svc, hid, _ = _build_messages_and_service(
            sid, tid, diff_entries=entries,
            review_scope_paths=["src/a.py"],
        )
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=hid,
            source_task=_safe_dry_run_task(tid),
            source_handoff_message=svc._message_repository.get_by_id(hid),
            user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "blocked"
        assert "review_scope_paths_missing" in r.blocked_reasons

    def test_scope_extra_path_blocked(self) -> None:
        sid, tid = uuid4(), uuid4()
        entries = [_valid_diff_entry(relative_path="src/a.py")]
        # G has extra path
        svc, hid, _ = _build_messages_and_service(
            sid, tid, diff_entries=entries,
            review_scope_paths=["src/a.py", "src/b.py"],
        )
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=hid,
            source_task=_safe_dry_run_task(tid),
            source_handoff_message=svc._message_repository.get_by_id(hid),
            user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "blocked"
        assert "review_scope_paths_missing" in r.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# 5. Deterministic prompt builder
# ══════════════════════════════════════════════════════════════════════


class TestDeterministicPromptBuilder:
    def test_same_input_same_prompt(self) -> None:
        diff = "--- /dev/null\n+++ b/src/a.py\n+hello\n"
        hash_val = hashlib.sha256(diff.encode("utf-8")).hexdigest()
        p1 = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService.build_readonly_review_prompt(
            requested_reviewer_executor="codex", source_diff_sha256=hash_val,
            review_scope_paths=["src/a.py"], unified_diff_text=diff,
        )
        p2 = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService.build_readonly_review_prompt(
            requested_reviewer_executor="codex", source_diff_sha256=hash_val,
            review_scope_paths=["src/a.py"], unified_diff_text=diff,
        )
        assert p1 == p2
        assert hashlib.sha256(p1.encode("utf-8")).hexdigest() == hashlib.sha256(p2.encode("utf-8")).hexdigest()

    def test_diff_change_changes_prompt(self) -> None:
        hash1 = hashlib.sha256(b"diff1").hexdigest()
        hash2 = hashlib.sha256(b"diff2").hexdigest()
        p1 = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService.build_readonly_review_prompt(
            requested_reviewer_executor="codex", source_diff_sha256=hash1,
            review_scope_paths=["src/a.py"], unified_diff_text="diff1",
        )
        p2 = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService.build_readonly_review_prompt(
            requested_reviewer_executor="codex", source_diff_sha256=hash2,
            review_scope_paths=["src/a.py"], unified_diff_text="diff2",
        )
        assert p1 != p2

    def test_scope_order_change_changes_prompt(self) -> None:
        diff = "diff"
        hash_val = hashlib.sha256(diff.encode("utf-8")).hexdigest()
        p1 = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService.build_readonly_review_prompt(
            requested_reviewer_executor="codex", source_diff_sha256=hash_val,
            review_scope_paths=["a.py", "b.py"], unified_diff_text=diff,
        )
        p2 = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService.build_readonly_review_prompt(
            requested_reviewer_executor="codex", source_diff_sha256=hash_val,
            review_scope_paths=["b.py", "a.py"], unified_diff_text=diff,
        )
        assert p1 != p2

    def test_executor_change_changes_prompt(self) -> None:
        diff = "diff"
        hash_val = hashlib.sha256(diff.encode("utf-8")).hexdigest()
        p1 = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService.build_readonly_review_prompt(
            requested_reviewer_executor="codex", source_diff_sha256=hash_val,
            review_scope_paths=["a.py"], unified_diff_text=diff,
        )
        p2 = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService.build_readonly_review_prompt(
            requested_reviewer_executor="claude-code", source_diff_sha256=hash_val,
            review_scope_paths=["a.py"], unified_diff_text=diff,
        )
        assert p1 != p2

    def test_utf8_bytes(self) -> None:
        diff = "--- /dev/null\n+++ b/src/a.py\n+你好\n"
        hash_val = hashlib.sha256(diff.encode("utf-8")).hexdigest()
        prompt = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService.build_readonly_review_prompt(
            requested_reviewer_executor="codex", source_diff_sha256=hash_val,
            review_scope_paths=["src/a.py"], unified_diff_text=diff,
        )
        assert len(prompt.encode("utf-8")) > len(prompt)  # Chinese chars use more bytes


# ══════════════════════════════════════════════════════════════════════
# 6. Prompt fixed blocks
# ══════════════════════════════════════════════════════════════════════


class TestPromptFixedBlocks:
    def test_prompt_contains_required_sections(self) -> None:
        diff = "--- /dev/null\n+++ b/src/a.py\n+hello\n"
        hash_val = hashlib.sha256(diff.encode("utf-8")).hexdigest()
        prompt = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService.build_readonly_review_prompt(
            requested_reviewer_executor="codex", source_diff_sha256=hash_val,
            review_scope_paths=["src/a.py"], unified_diff_text=diff,
        )
        for section in ["[System Role]", "[Review Scope]", "[Source Diff Integrity]",
                         "[Review Instructions]", "[Unified Diff]", "[Required JSON Output]"]:
            assert section in prompt, f"Missing section: {section}"
        assert f"source_diff_sha256={hash_val}" in prompt
        assert "src/a.py" in prompt
        assert diff.strip() in prompt
        assert f"review_output_schema_version={REVIEW_OUTPUT_SCHEMA_VERSION}" in prompt


class TestPromptReadonlyRestrictions:
    def test_prompt_contains_readonly_prohibitions(self) -> None:
        diff = "diff"
        hash_val = hashlib.sha256(diff.encode("utf-8")).hexdigest()
        prompt = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService.build_readonly_review_prompt(
            requested_reviewer_executor="codex", source_diff_sha256=hash_val,
            review_scope_paths=["a.py"], unified_diff_text=diff,
        )
        for prohibition in [
            "must not read files", "must not request more files",
            "must not use shell", "must not use Git",
            "must not modify code", "must not apply patches",
            "must not create worktrees", "must not commit",
            "push", "must not treat the review verdict as human approval",
        ]:
            assert prohibition in prompt, f"Missing prohibition: {prohibition}"


class TestPromptStrictJSONContract:
    def test_prompt_requires_strict_json(self) -> None:
        diff = "diff"
        hash_val = hashlib.sha256(diff.encode("utf-8")).hexdigest()
        prompt = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService.build_readonly_review_prompt(
            requested_reviewer_executor="codex", source_diff_sha256=hash_val,
            review_scope_paths=["a.py"], unified_diff_text=diff,
        )
        assert "Return exactly one JSON object" in prompt
        assert "Do not use Markdown code fences" in prompt
        assert "Do not output XML or YAML" in prompt
        for field in ["review_status", "verdict", "risk_level", "summary", "findings", "recommended_next_step"]:
            assert field in prompt, f"Missing contract field: {field}"
        for finding_field in ["finding_id", "severity", "title", "summary", "evidence_paths", "recommended_action"]:
            assert finding_field in prompt, f"Missing finding field: {finding_field}"
        assert "findings must contain at most 20 items" in prompt
        assert "Do not output patches" in prompt
        assert "Do not output modified full files" in prompt
        assert "Do not output Git commands" in prompt


# ══════════════════════════════════════════════════════════════════════
# 7. Action does not contain prompt/diff
# ══════════════════════════════════════════════════════════════════════


class TestActionMinimization:
    def test_action_no_prompt_or_diff(self) -> None:
        sid, tid = uuid4(), uuid4()
        svc, hid, _ = _build_messages_and_service(sid, tid)
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=hid,
            source_task=_safe_dry_run_task(tid),
            source_handoff_message=svc._message_repository.get_by_id(hid),
            user_confirmed=True,
        )
        action = svc._review_execution_preflight_action(r)
        for forbidden_key in ["review_prompt_text", "prompt_text", "unified_diff_text",
                               "diff_entries", "api_key", "token", "base_url"]:
            assert forbidden_key not in action, f"Action contains forbidden key: {forbidden_key}"


# ══════════════════════════════════════════════════════════════════════
# 8. No file re-read
# ══════════════════════════════════════════════════════════════════════


class TestNoFileReRead:
    def test_ready_with_path_read_text_blocked(self, monkeypatch) -> None:
        from pathlib import Path
        monkeypatch.setattr(Path, "read_text", lambda self, *a, **kw: (_ for _ in ()).throw(AssertionError("H-A must not read files!")))
        sid, tid = uuid4(), uuid4()
        svc, hid, _ = _build_messages_and_service(sid, tid)
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=hid,
            source_task=_safe_dry_run_task(tid),
            source_handoff_message=svc._message_repository.get_by_id(hid),
            user_confirmed=True,
        )
        assert r.review_execution_preflight_status == "ready"


# ══════════════════════════════════════════════════════════════════════
# 9. No execution
# ══════════════════════════════════════════════════════════════════════


class TestNoExecution:
    def test_all_execution_flags_false(self) -> None:
        sid, tid = uuid4(), uuid4()
        svc, hid, _ = _build_messages_and_service(sid, tid)
        r = svc.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=sid, source_task_id=tid, source_message_id=hid,
            source_task=_safe_dry_run_task(tid),
            source_handoff_message=svc._message_repository.get_by_id(hid),
            user_confirmed=True,
        )
        assert r.reviewer_started is False
        assert r.review_executed is False
        assert r.provider_called is False
        assert r.native_executor_started is False
        assert r.codex_started is False
        assert r.claude_code_started is False
        assert r.review_findings_generated is False
        assert r.review_verdict_generated is False


# ══════════════════════════════════════════════════════════════════════
# 10. Domain validator
# ══════════════════════════════════════════════════════════════════════


class TestDomainValidatorRejectsTrueFlags:
    @pytest.mark.parametrize("field_name", SIDE_EFFECT_FLAGS)
    def test_rejects_true_flag(self, field_name: str) -> None:
        with pytest.raises(ValidationError, match="may not review, write, or execute"):
            ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightResult(
                review_execution_preflight_status="ready",
                session_id=uuid4(),
                review_execution_preflight_summary="test",
                recommended_next_step="next",
                **{field_name: True},
            )


# ══════════════════════════════════════════════════════════════════════
# 11. Output no misleading terms
# ══════════════════════════════════════════════════════════════════════


class TestOutputNoMisleadingTerms:
    def test_result_excludes_misleading_terms(self) -> None:
        result = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightResult(
            review_execution_preflight_status="blocked",
            session_id=uuid4(),
            review_execution_preflight_summary="blocked",
            recommended_next_step="next",
        )
        serialized = result.model_dump_json()
        for term in MISLEADING_TERMS:
            assert term not in serialized, f"Found misleading term: {term}"
