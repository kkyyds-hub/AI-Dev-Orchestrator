"""Contract tests for P21-C-H-C1 readonly review execution orchestration service."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import uuid4

import pytest

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_sandbox_candidate_diff_readonly_reviewer_adapter import (
    ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult,
)
from app.external_executors.readonly_reviewer_transport import (
    FakeReadonlyReviewerTransport,
    ReadonlyReviewerTransportProtocol,
)
from app.services.project_director_sandbox_candidate_diff_readonly_review_execution_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
    ConfirmedSandboxCandidateDiffReadonlyReviewExecution,
    ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService,
)
from app.services.project_director_sandbox_candidate_diff_readonly_reviewer_adapter_service import (
    ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService,
)
from app.services.project_director_sandbox_candidate_diff_review_execution_preflight_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_EXECUTION_PREFLIGHT_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_EXECUTION_PREFLIGHT_SOURCE_DETAIL,
    REVIEW_OUTPUT_SCHEMA_VERSION,
    ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService,
)
from app.services.project_director_sandbox_candidate_diff_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL,
)

# ── Constants ───────────────────────────────────────────────────────

SESSION_ID = uuid4()
TASK_ID = uuid4()
PROJECT_ID = uuid4()
PREFLIGHT_MSG_ID = uuid4()
DIFF_MSG_ID = uuid4()

UNIFIED_DIFF = "--- a/src/example.py\n+++ b/src/example.py\n@@ -1 +1 @@\n-old\n+new\n"
SCOPE_PATHS = ["src/example.py"]

_TRUE_HEX_SHA256 = hashlib.sha256(UNIFIED_DIFF.encode("utf-8")).hexdigest()

REVIEW_PROMPT = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService.build_readonly_review_prompt(
    requested_reviewer_executor="codex",
    source_diff_sha256=_TRUE_HEX_SHA256,
    review_scope_paths=SCOPE_PATHS,
    unified_diff_text=UNIFIED_DIFF,
    review_output_schema_version=REVIEW_OUTPUT_SCHEMA_VERSION,
)
PROMPT_SHA256 = hashlib.sha256(REVIEW_PROMPT.encode("utf-8")).hexdigest()
PROMPT_BYTES = len(REVIEW_PROMPT.encode("utf-8"))

WRITE_FLAGS = [
    "main_project_file_written", "sandbox_file_written", "manifest_file_written",
    "diff_file_written", "patch_applied", "git_write_performed",
    "worktree_created", "worker_started", "task_created", "run_created",
]


# ── Spy repositories ───────────────────────────────────────────────


class SpyMessageRepo:
    def __init__(self, messages: dict[Any, ProjectDirectorMessage] | None = None) -> None:
        self._messages = messages or {}
        self.create_calls: list[ProjectDirectorMessage] = []
        self.commit_calls = 0

    def get_by_id(self, mid):
        return self._messages.get(mid)

    def get_next_sequence_no(self, *, session_id):
        return 100

    def create(self, message):
        self.create_calls.append(message)
        return message

    def commit(self):
        self.commit_calls += 1


class FakeSessionRepo:
    def __init__(self, session_exists: bool = True) -> None:
        self._session_exists = session_exists

    def get_by_id(self, sid):
        if self._session_exists and sid == SESSION_ID:
            return type("S", (), {"project_id": PROJECT_ID})()
        return None


class FakeTaskRepo:
    def __init__(self, task_exists: bool = True) -> None:
        self._task_exists = task_exists

    def get_by_id(self, tid):
        if self._task_exists and tid == TASK_ID:
            return type("T", (), {})()
        return None


# ── Spy adapter ─────────────────────────────────────────────────────


class SpyAdapter:
    """Records adapter invocations and returns a configurable result."""

    def __init__(
        self,
        result: ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult
        | None = None,
    ) -> None:
        self._result = result or _validated_adapter_result()
        self.invocations: list[dict[str, Any]] = []

    def validate_review_output_through_transport(self, **kwargs):
        self.invocations.append(kwargs)
        return self._result


# ── Builder helpers ─────────────────────────────────────────────────


def _valid_preflight_action(*, executor="codex", **overrides):
    action = {
        "type": P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_EXECUTION_PREFLIGHT_ACTION_TYPE,
        "review_execution_preflight_status": "ready",
        "source_task_id": str(TASK_ID),
        "source_diff_message_id": str(DIFF_MSG_ID),
        "requested_reviewer_executor": executor,
        "source_diff_sha256": _TRUE_HEX_SHA256,
        "review_prompt_sha256": PROMPT_SHA256,
        "review_prompt_bytes": PROMPT_BYTES,
        "review_scope_paths": list(SCOPE_PATHS),
        "review_output_schema_version": REVIEW_OUTPUT_SCHEMA_VERSION,
        "reviewer_started": False,
        "review_executed": False,
        "review_findings_generated": False,
        "review_verdict_generated": False,
        "provider_called": False,
        "native_executor_started": False,
        "codex_started": False,
        "claude_code_started": False,
        "main_project_file_written": False,
        "sandbox_file_written": False,
        "manifest_file_written": False,
        "diff_file_written": False,
        "patch_applied": False,
        "product_runtime_git_write_allowed": False,
        "git_write_performed": False,
        "worktree_created": False,
        "worker_started": False,
        "task_created": False,
        "run_created": False,
        "ai_project_director_total_loop": "Partial",
    }
    action.update(overrides)
    return action


def _valid_diff_action(*, diff_text=UNIFIED_DIFF, **overrides):
    diff_bytes = len(diff_text.encode("utf-8"))
    action = {
        "type": P21_C_SANDBOX_CANDIDATE_DIFF_ACTION_TYPE,
        "source_task_id": str(TASK_ID),
        "diff_generation_status": "generated",
        "readonly_real_diff_generated": True,
        "real_diff_generated": True,
        "unified_diff_text": diff_text,
        "diff_bytes": diff_bytes,
        "diff_entries": [{"relative_path": SCOPE_PATHS[0], "unified_diff": diff_text, "diff_bytes": diff_bytes}],
        "diff_file_count": 1,
        "main_project_file_written": False,
        "sandbox_file_written": False,
        "manifest_file_written": False,
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
    action.update(overrides)
    return action


def _make_preflight_message(action=None, *, session_id=SESSION_ID, task_id=TASK_ID,
                             source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_EXECUTION_PREFLIGHT_SOURCE_DETAIL):
    return ProjectDirectorMessage(
        id=PREFLIGHT_MSG_ID, session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT, content="preflight", sequence_no=5,
        intent="sandbox_candidate_diff_review_execution_preflight",
        related_project_id=PROJECT_ID, related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=source_detail,
        suggested_actions=[action or _valid_preflight_action()],
    )


def _make_diff_message(action=None, *, session_id=SESSION_ID, task_id=TASK_ID,
                        source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL):
    return ProjectDirectorMessage(
        id=DIFF_MSG_ID, session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT, content="diff", sequence_no=3,
        intent="sandbox_candidate_diff",
        related_project_id=PROJECT_ID, related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=source_detail,
        suggested_actions=[action or _valid_diff_action()],
    )


def _validated_adapter_result(**overrides):
    kwargs = dict(
        adapter_status="validated_output",
        execution_mode="fake_transport",
        requested_reviewer_executor="codex",
        review_prompt_verified=True,
        transport_invoked=True,
        transport_status="completed",
        output_validation_status="validated",
        raw_output_sha256="a" * 64,
        raw_output_bytes=100,
        strict_json_valid=True,
        schema_valid=True,
        semantics_valid=True,
        evidence_scope_valid=True,
        review_status="reviewed",
        verdict="no_blocking_findings",
        risk_level="low",
        summary="No issues.",
        findings=[],
        recommended_next_step="Proceed.",
        real_reviewer_started=False,
        real_reviewer_executed=False,
        native_process_started=False,
        provider_called=False,
        codex_started=False,
        claude_code_started=False,
    )
    kwargs.update(overrides)
    return ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult(**kwargs)


def _blocked_adapter_result(**overrides):
    kwargs = dict(
        adapter_status="blocked",
        blocked_reasons=["test_blocked"],
    )
    kwargs.update(overrides)
    return ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult(**kwargs)


def _build_service(*, messages=None, session_exists=True, task_exists=True,
                    adapter_result=None):
    msg_repo = SpyMessageRepo(messages or {})
    adapter = SpyAdapter(adapter_result)
    svc = ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService(
        session_repository=FakeSessionRepo(session_exists),
        message_repository=msg_repo,
        task_repository=FakeTaskRepo(task_exists),
        adapter_service=adapter,
    )
    return svc, msg_repo, adapter


def _call_service(svc, *, session_id=SESSION_ID, task_id=TASK_ID,
                   message_id=PREFLIGHT_MSG_ID, transport=None):
    transport = transport or FakeReadonlyReviewerTransport(raw_output_text="ok")
    return svc.execute_candidate_diff_readonly_review_from_preflight(
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=message_id,
        transport=transport,
    )


# ══════════════════════════════════════════════════════════════════════
# A. Happy path evidence reconstruction
# ══════════════════════════════════════════════════════════════════════


class TestHappyPath:
    def test_validated_result_and_message(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        svc, msg_repo, _adapter = _build_service(messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})
        result = _call_service(svc)
        assert result.result.adapter_status == "validated_output"
        assert result.message is not None
        assert len(msg_repo.create_calls) == 1
        assert msg_repo.commit_calls == 1

    def test_adapter_receives_persisted_evidence(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        adapter = SpyAdapter(_validated_adapter_result())
        msg_repo = SpyMessageRepo({PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})
        svc = ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService(
            session_repository=FakeSessionRepo(),
            message_repository=msg_repo,
            task_repository=FakeTaskRepo(),
            adapter_service=adapter,
        )
        _call_service(svc)
        inv = adapter.invocations[0]
        assert inv["requested_reviewer_executor"] == "codex"
        assert inv["review_scope_paths"] == SCOPE_PATHS
        assert inv["review_output_schema_version"] == REVIEW_OUTPUT_SCHEMA_VERSION
        assert inv["expected_review_prompt_sha256"] == PROMPT_SHA256
        assert inv["expected_review_prompt_bytes"] == PROMPT_BYTES


# ══════════════════════════════════════════════════════════════════════
# B. Production prompt reconstruction
# ══════════════════════════════════════════════════════════════════════


class TestPromptReconstruction:
    def test_service_prompt_matches_production_builder(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        adapter = SpyAdapter(_validated_adapter_result())
        msg_repo = SpyMessageRepo({PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})
        svc = ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService(
            session_repository=FakeSessionRepo(),
            message_repository=msg_repo,
            task_repository=FakeTaskRepo(),
            adapter_service=adapter,
        )
        _call_service(svc)
        inv = adapter.invocations[0]
        assert inv["review_prompt_text"] == REVIEW_PROMPT
        assert inv["expected_review_prompt_sha256"] == PROMPT_SHA256
        assert inv["expected_review_prompt_bytes"] == PROMPT_BYTES


# ══════════════════════════════════════════════════════════════════════
# C. Adapter invocation count
# ══════════════════════════════════════════════════════════════════════


class TestAdapterInvocationCount:
    def test_validated_path_adapter_called_once(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        adapter = SpyAdapter(_validated_adapter_result())
        msg_repo = SpyMessageRepo({PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})
        svc = ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService(
            session_repository=FakeSessionRepo(), message_repository=msg_repo,
            task_repository=FakeTaskRepo(), adapter_service=adapter,
        )
        _call_service(svc)
        assert len(adapter.invocations) == 1

    def test_adapter_blocked_path_adapter_called_once(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        adapter = SpyAdapter(_blocked_adapter_result())
        msg_repo = SpyMessageRepo({PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})
        svc = ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService(
            session_repository=FakeSessionRepo(), message_repository=msg_repo,
            task_repository=FakeTaskRepo(), adapter_service=adapter,
        )
        result = _call_service(svc)
        assert len(adapter.invocations) == 1
        assert result.message is None

    def test_evidence_blocked_adapter_not_called(self) -> None:
        svc, msg_repo, adapter = _build_service(messages={})
        result = _call_service(svc)
        assert result.result.adapter_status == "blocked"
        assert result.message is None
        assert len(adapter.invocations) == 0
        assert msg_repo.create_calls == []
        assert msg_repo.commit_calls == 0


# ══════════════════════════════════════════════════════════════════════
# D. Preflight source binding
# ══════════════════════════════════════════════════════════════════════


class TestPreflightSourceBinding:
    def _assert_blocked_before_adapter(self, svc, msg_repo, adapter, *, reason):
        result = _call_service(svc)
        assert result.result.adapter_status == "blocked"
        assert reason in result.result.blocked_reasons
        assert result.message is None
        assert len(adapter.invocations) == 0
        assert msg_repo.create_calls == []
        assert msg_repo.commit_calls == 0

    def test_preflight_message_missing(self) -> None:
        svc, msg_repo, adapter = _build_service(messages={})
        self._assert_blocked_before_adapter(svc, msg_repo, adapter, reason="source_preflight_message_missing")

    def test_preflight_session_mismatch(self) -> None:
        msg = _make_preflight_message(session_id=uuid4())
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: msg})
        self._assert_blocked_before_adapter(svc, msg_repo, adapter, reason="source_preflight_message_session_mismatch")

    def test_preflight_task_mismatch(self) -> None:
        msg = _make_preflight_message(task_id=uuid4())
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: msg})
        self._assert_blocked_before_adapter(svc, msg_repo, adapter, reason="source_preflight_message_task_mismatch")

    def test_wrong_source_detail(self) -> None:
        msg = _make_preflight_message(source_detail="wrong_detail")
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: msg})
        self._assert_blocked_before_adapter(svc, msg_repo, adapter, reason="source_message_is_not_p21_c_review_preflight")

    def test_wrong_action_type(self) -> None:
        action = _valid_preflight_action()
        action["type"] = "wrong_type"
        msg = _make_preflight_message(action=action)
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: msg})
        self._assert_blocked_before_adapter(svc, msg_repo, adapter, reason="p21_c_review_execution_preflight_record_missing")

    def test_action_source_task_id_mismatch(self) -> None:
        action = _valid_preflight_action(source_task_id=str(uuid4()))
        msg = _make_preflight_message(action=action)
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: msg})
        self._assert_blocked_before_adapter(svc, msg_repo, adapter, reason="source_task_not_bound_to_review_preflight")

    def test_preflight_status_not_ready(self) -> None:
        action = _valid_preflight_action(review_execution_preflight_status="blocked")
        msg = _make_preflight_message(action=action)
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: msg})
        self._assert_blocked_before_adapter(svc, msg_repo, adapter, reason="source_preflight_not_ready")

    def test_preflight_write_flag_true(self) -> None:
        action = _valid_preflight_action(reviewer_started=True)
        msg = _make_preflight_message(action=action)
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: msg})
        self._assert_blocked_before_adapter(svc, msg_repo, adapter, reason="source_preflight_write_boundary_violated")

    def test_preflight_total_loop_not_partial(self) -> None:
        action = _valid_preflight_action(ai_project_director_total_loop="Pass")
        msg = _make_preflight_message(action=action)
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: msg})
        self._assert_blocked_before_adapter(svc, msg_repo, adapter, reason="source_preflight_write_boundary_violated")


# ══════════════════════════════════════════════════════════════════════
# E. Persisted preflight evidence integrity
# ══════════════════════════════════════════════════════════════════════


class TestPreflightEvidenceIntegrity:
    def _assert_blocked(self, svc, msg_repo, adapter, *, reason):
        result = _call_service(svc)
        assert result.result.adapter_status == "blocked"
        assert reason in result.result.blocked_reasons
        assert len(adapter.invocations) == 0
        assert msg_repo.create_calls == []
        assert msg_repo.commit_calls == 0

    def test_invalid_executor(self) -> None:
        action = _valid_preflight_action(requested_reviewer_executor="invalid")
        msg = _make_preflight_message(action=action)
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: msg})
        self._assert_blocked(svc, msg_repo, adapter, reason="requested_reviewer_executor_invalid")

    def test_missing_source_diff_message_id(self) -> None:
        action = _valid_preflight_action()
        del action["source_diff_message_id"]
        msg = _make_preflight_message(action=action)
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: msg})
        self._assert_blocked(svc, msg_repo, adapter, reason="source_diff_message_id_missing")

    def test_invalid_source_diff_sha256(self) -> None:
        action = _valid_preflight_action(source_diff_sha256="not_hex")
        msg = _make_preflight_message(action=action)
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: msg})
        self._assert_blocked(svc, msg_repo, adapter, reason="source_diff_sha256_invalid")

    def test_invalid_review_prompt_sha256(self) -> None:
        action = _valid_preflight_action(review_prompt_sha256="bad")
        msg = _make_preflight_message(action=action)
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: msg})
        self._assert_blocked(svc, msg_repo, adapter, reason="review_prompt_sha256_invalid")

    def test_review_prompt_bytes_zero(self) -> None:
        action = _valid_preflight_action(review_prompt_bytes=0)
        msg = _make_preflight_message(action=action)
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: msg})
        self._assert_blocked(svc, msg_repo, adapter, reason="review_prompt_bytes_invalid")

    def test_missing_review_scope_paths(self) -> None:
        action = _valid_preflight_action(review_scope_paths=[])
        msg = _make_preflight_message(action=action)
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: msg})
        self._assert_blocked(svc, msg_repo, adapter, reason="review_scope_paths_missing")

    def test_duplicate_review_scope_paths(self) -> None:
        action = _valid_preflight_action(review_scope_paths=["a.py", "a.py"])
        msg = _make_preflight_message(action=action)
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: msg})
        self._assert_blocked(svc, msg_repo, adapter, reason="review_scope_paths_invalid")

    def test_invalid_schema_version(self) -> None:
        action = _valid_preflight_action(review_output_schema_version="wrong")
        msg = _make_preflight_message(action=action)
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: msg})
        self._assert_blocked(svc, msg_repo, adapter, reason="review_output_schema_version_mismatch")


# ══════════════════════════════════════════════════════════════════════
# F. Source diff binding
# ══════════════════════════════════════════════════════════════════════


class TestSourceDiffBinding:
    def _assert_blocked(self, svc, msg_repo, adapter, *, reason):
        result = _call_service(svc)
        assert result.result.adapter_status == "blocked"
        assert reason in result.result.blocked_reasons
        assert len(adapter.invocations) == 0
        assert msg_repo.create_calls == []
        assert msg_repo.commit_calls == 0

    def test_diff_message_missing(self) -> None:
        preflight = _make_preflight_message()
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: preflight})
        self._assert_blocked(svc, msg_repo, adapter, reason="source_diff_message_missing")

    def test_diff_session_mismatch(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message(session_id=uuid4())
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})
        self._assert_blocked(svc, msg_repo, adapter, reason="source_diff_message_session_mismatch")

    def test_diff_task_mismatch(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message(task_id=uuid4())
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})
        self._assert_blocked(svc, msg_repo, adapter, reason="source_diff_message_task_mismatch")

    def test_diff_wrong_source_detail(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message(source_detail="wrong")
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})
        self._assert_blocked(svc, msg_repo, adapter, reason="source_diff_message_is_not_p21_c_candidate_diff_generated")

    def test_diff_wrong_action_type(self) -> None:
        preflight = _make_preflight_message()
        diff_action = _valid_diff_action()
        diff_action["type"] = "wrong"
        diff = _make_diff_message(action=diff_action)
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})
        self._assert_blocked(svc, msg_repo, adapter, reason="p21_c_candidate_diff_generate_record_missing")

    def test_diff_action_task_mismatch(self) -> None:
        preflight = _make_preflight_message()
        diff_action = _valid_diff_action(source_task_id=str(uuid4()))
        diff = _make_diff_message(action=diff_action)
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})
        self._assert_blocked(svc, msg_repo, adapter, reason="source_task_not_bound_to_candidate_diff")


# ══════════════════════════════════════════════════════════════════════
# G. Source diff integrity
# ══════════════════════════════════════════════════════════════════════


class TestSourceDiffIntegrity:
    def _assert_blocked(self, svc, msg_repo, adapter, *, reason):
        result = _call_service(svc)
        assert result.result.adapter_status == "blocked"
        assert reason in result.result.blocked_reasons
        assert len(adapter.invocations) == 0
        assert msg_repo.create_calls == []
        assert msg_repo.commit_calls == 0

    def _build_with_diff_action(self, diff_action):
        preflight = _make_preflight_message()
        diff = _make_diff_message(action=diff_action)
        return _build_service(messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})

    def test_diff_not_generated(self) -> None:
        svc, msg_repo, adapter = self._build_with_diff_action(_valid_diff_action(diff_generation_status="pending"))
        self._assert_blocked(svc, msg_repo, adapter, reason="source_diff_not_generated")

    def test_readonly_not_true(self) -> None:
        svc, msg_repo, adapter = self._build_with_diff_action(_valid_diff_action(readonly_real_diff_generated=False))
        self._assert_blocked(svc, msg_repo, adapter, reason="source_diff_not_generated")

    def test_real_diff_not_generated(self) -> None:
        svc, msg_repo, adapter = self._build_with_diff_action(_valid_diff_action(real_diff_generated=False))
        self._assert_blocked(svc, msg_repo, adapter, reason="source_diff_not_generated")

    def test_write_flag_true(self) -> None:
        svc, msg_repo, adapter = self._build_with_diff_action(_valid_diff_action(git_write_performed=True))
        self._assert_blocked(svc, msg_repo, adapter, reason="source_diff_write_boundary_violated")

    def test_total_loop_not_partial(self) -> None:
        svc, msg_repo, adapter = self._build_with_diff_action(_valid_diff_action(ai_project_director_total_loop="Pass"))
        self._assert_blocked(svc, msg_repo, adapter, reason="source_diff_write_boundary_violated")

    def test_missing_unified_diff_text(self) -> None:
        svc, msg_repo, adapter = self._build_with_diff_action(_valid_diff_action(unified_diff_text=""))
        self._assert_blocked(svc, msg_repo, adapter, reason="source_diff_not_generated")

    def test_diff_bytes_mismatch(self) -> None:
        svc, msg_repo, adapter = self._build_with_diff_action(_valid_diff_action(diff_bytes=999))
        self._assert_blocked(svc, msg_repo, adapter, reason="source_diff_bytes_mismatch")

    def test_sha256_mismatch(self) -> None:
        svc, msg_repo, adapter = self._build_with_diff_action(_valid_diff_action(
            unified_diff_text="different content\n"
        ))
        self._assert_blocked(svc, msg_repo, adapter, reason="source_diff_sha256_mismatch")

    def test_diff_entries_missing(self) -> None:
        svc, msg_repo, adapter = self._build_with_diff_action(_valid_diff_action(diff_entries=[]))
        self._assert_blocked(svc, msg_repo, adapter, reason="source_diff_entries_missing")

    def test_diff_file_count_mismatch(self) -> None:
        svc, msg_repo, adapter = self._build_with_diff_action(_valid_diff_action(diff_file_count=5))
        self._assert_blocked(svc, msg_repo, adapter, reason="source_diff_file_count_mismatch")

    def test_invalid_diff_entry(self) -> None:
        svc, msg_repo, adapter = self._build_with_diff_action(_valid_diff_action(
            diff_entries=["not_a_dict"],
        ))
        self._assert_blocked(svc, msg_repo, adapter, reason="source_diff_entries_invalid")

    def test_entry_diff_bytes_mismatch(self) -> None:
        entry = {"relative_path": "src/example.py", "unified_diff": UNIFIED_DIFF, "diff_bytes": 999}
        svc, msg_repo, adapter = self._build_with_diff_action(_valid_diff_action(diff_entries=[entry]))
        self._assert_blocked(svc, msg_repo, adapter, reason="source_diff_entries_invalid")

    def test_scope_path_mismatch(self) -> None:
        entry = {"relative_path": "src/other.py", "unified_diff": UNIFIED_DIFF,
                 "diff_bytes": len(UNIFIED_DIFF.encode("utf-8"))}
        svc, msg_repo, adapter = self._build_with_diff_action(_valid_diff_action(diff_entries=[entry]))
        self._assert_blocked(svc, msg_repo, adapter, reason="review_scope_paths_mismatch")


# ══════════════════════════════════════════════════════════════════════
# H. Prompt fingerprint integrity
# ══════════════════════════════════════════════════════════════════════


class TestPromptFingerprint:
    def _assert_blocked(self, svc, msg_repo, adapter, *, reason):
        result = _call_service(svc)
        assert result.result.adapter_status == "blocked"
        assert reason in result.result.blocked_reasons
        assert len(adapter.invocations) == 0
        assert msg_repo.create_calls == []
        assert msg_repo.commit_calls == 0

    def test_prompt_sha256_mismatch(self) -> None:
        action = _valid_preflight_action(review_prompt_sha256="a" * 64)
        preflight = _make_preflight_message(action=action)
        diff = _make_diff_message()
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})
        self._assert_blocked(svc, msg_repo, adapter, reason="review_prompt_sha256_mismatch")

    def test_prompt_bytes_mismatch(self) -> None:
        action = _valid_preflight_action(review_prompt_bytes=999999)
        preflight = _make_preflight_message(action=action)
        diff = _make_diff_message()
        svc, msg_repo, adapter = _build_service(messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})
        self._assert_blocked(svc, msg_repo, adapter, reason="review_prompt_bytes_mismatch")


# ══════════════════════════════════════════════════════════════════════
# I. Caller-injected transport identity
# ══════════════════════════════════════════════════════════════════════


class TestCallerTransport:
    def test_same_transport_reaches_adapter(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        adapter = SpyAdapter(_validated_adapter_result())
        msg_repo = SpyMessageRepo({PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})
        svc = ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService(
            session_repository=FakeSessionRepo(), message_repository=msg_repo,
            task_repository=FakeTaskRepo(), adapter_service=adapter,
        )
        sentinel = FakeReadonlyReviewerTransport(raw_output_text="ok")
        svc.execute_candidate_diff_readonly_review_from_preflight(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=PREFLIGHT_MSG_ID, transport=sentinel,
        )
        assert adapter.invocations[0]["transport"] is sentinel


# ══════════════════════════════════════════════════════════════════════
# J. Adapter blocked → no persist
# ══════════════════════════════════════════════════════════════════════


class TestAdapterBlockedNoPersist:
    def test_blocked_no_message_created(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        adapter = SpyAdapter(_blocked_adapter_result())
        msg_repo = SpyMessageRepo({PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})
        svc = ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService(
            session_repository=FakeSessionRepo(), message_repository=msg_repo,
            task_repository=FakeTaskRepo(), adapter_service=adapter,
        )
        result = _call_service(svc)
        assert result.message is None
        assert msg_repo.create_calls == []
        assert msg_repo.commit_calls == 0


# ══════════════════════════════════════════════════════════════════════
# K. Validated exactly-one persistence
# ══════════════════════════════════════════════════════════════════════


class TestValidatedPersistence:
    def test_exactly_one_message_and_commit(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        msg_repo = SpyMessageRepo({PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})
        adapter = SpyAdapter(_validated_adapter_result())
        svc = ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService(
            session_repository=FakeSessionRepo(), message_repository=msg_repo,
            task_repository=FakeTaskRepo(), adapter_service=adapter,
        )
        result = _call_service(svc)
        assert len(msg_repo.create_calls) == 1
        assert msg_repo.commit_calls == 1
        assert result.message is not None


# ══════════════════════════════════════════════════════════════════════
# L. Persisted message contract
# ══════════════════════════════════════════════════════════════════════


class TestPersistedMessage:
    def test_message_fields(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        msg_repo = SpyMessageRepo({PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})
        svc = ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService(
            session_repository=FakeSessionRepo(), message_repository=msg_repo,
            task_repository=FakeTaskRepo(), adapter_service=SpyAdapter(),
        )
        result = _call_service(svc)
        msg = result.message
        assert msg.role == ProjectDirectorMessageRole.ASSISTANT
        assert msg.source == ProjectDirectorMessageSource.SYSTEM
        assert msg.source_detail == P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL
        assert msg.related_task_id == TASK_ID
        assert msg.requires_confirmation is False
        assert msg.risk_level == ProjectDirectorMessageRiskLevel.HIGH
        content = msg.content
        assert "verdict" in content.lower()
        assert "not human approval" in content or "不是 human" in content
        assert "not Git write authorization" in content or "不是 Git write" in content
        assert "no patch" in content.lower() or "没有应用 patch" in content
        assert "no Git write" in content or "没有执行 Git 写" in content
        assert "Partial" in content
        content_lower = content.lower()
        assert "approved to merge" not in content_lower
        assert "safe to merge" not in content_lower
        assert "production ready" not in content_lower
        assert "project complete" not in content_lower


# ══════════════════════════════════════════════════════════════════════
# M. Suggested action contract
# ══════════════════════════════════════════════════════════════════════


class TestSuggestedAction:
    REQUIRED_KEYS = [
        "session_id", "source_task_id", "source_preflight_message_id",
        "source_diff_message_id", "requested_reviewer_executor",
        "source_diff_sha256", "review_prompt_sha256", "review_prompt_bytes",
        "review_scope_paths", "review_output_schema_version",
        "adapter_status", "execution_mode", "transport_status",
        "transport_error_code", "output_validation_status",
        "raw_output_sha256", "raw_output_bytes",
        "strict_json_valid", "schema_valid", "semantics_valid",
        "evidence_scope_valid", "review_status", "verdict", "risk_level",
        "summary", "findings", "recommended_next_step",
        "real_reviewer_started", "real_reviewer_executed",
        "native_process_started", "provider_called", "codex_started",
        "claude_code_started", "ai_project_director_total_loop",
    ]

    def test_action_type_and_keys(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        msg_repo = SpyMessageRepo({PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})
        svc = ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService(
            session_repository=FakeSessionRepo(), message_repository=msg_repo,
            task_repository=FakeTaskRepo(), adapter_service=SpyAdapter(),
        )
        result = _call_service(svc)
        action = result.message.suggested_actions[0]
        assert action["type"] == P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE
        for key in self.REQUIRED_KEYS:
            assert key in action, f"Missing key: {key}"

    def test_action_evidence_values(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        msg_repo = SpyMessageRepo({PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})
        svc = ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService(
            session_repository=FakeSessionRepo(), message_repository=msg_repo,
            task_repository=FakeTaskRepo(), adapter_service=SpyAdapter(),
        )
        result = _call_service(svc)
        action = result.message.suggested_actions[0]
        assert action["session_id"] == str(SESSION_ID)
        assert action["source_task_id"] == str(TASK_ID)
        assert action["source_preflight_message_id"] == str(PREFLIGHT_MSG_ID)
        assert action["source_diff_message_id"] == str(DIFF_MSG_ID)
        assert action["requested_reviewer_executor"] == "codex"
        assert action["source_diff_sha256"] == _TRUE_HEX_SHA256
        assert action["review_prompt_sha256"] == PROMPT_SHA256
        assert action["review_prompt_bytes"] == PROMPT_BYTES
        assert action["review_scope_paths"] == SCOPE_PATHS
        assert action["adapter_status"] == "validated_output"
        assert action["transport_error_code"] is None

    def test_transport_error_code_propagation(self) -> None:
        result_with_error = _validated_adapter_result(
            transport_status="timeout",
            transport_error_code="reviewer_native_timeout",
        )
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        msg_repo = SpyMessageRepo({PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})
        svc = ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService(
            session_repository=FakeSessionRepo(), message_repository=msg_repo,
            task_repository=FakeTaskRepo(), adapter_service=SpyAdapter(result_with_error),
        )
        result = _call_service(svc)
        action = result.message.suggested_actions[0]
        assert action["transport_error_code"] == "reviewer_native_timeout"
        assert action["transport_status"] == "timeout"


# ══════════════════════════════════════════════════════════════════════
# N. Secret / raw output absence
# ══════════════════════════════════════════════════════════════════════


class TestSecretAbsence:
    def test_no_raw_output_text_in_action(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        msg_repo = SpyMessageRepo({PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})
        svc = ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService(
            session_repository=FakeSessionRepo(), message_repository=msg_repo,
            task_repository=FakeTaskRepo(), adapter_service=SpyAdapter(),
        )
        result = _call_service(svc)
        action = result.message.suggested_actions[0]
        action_str = json.dumps(action)
        assert "raw_output_text" not in action
        assert "ANTHROPIC_AUTH_TOKEN" not in action_str
        assert "ANTHROPIC_BASE_URL" not in action_str
        assert "API_KEY" not in action_str
        assert "credential" not in action_str
        assert "environment" not in action_str
        assert "secret" not in action_str
        forbidden_keys = {"raw_output_text", "review_prompt_text", "unified_diff_text"}
        for key in forbidden_keys:
            assert key not in action, f"Forbidden key present: {key}"


# ══════════════════════════════════════════════════════════════════════
# O. JSON-safe findings
# ══════════════════════════════════════════════════════════════════════


class TestJSONSafeFindings:
    def test_findings_json_serializable(self) -> None:
        finding = {
            "finding_id": "F1",
            "severity": "low",
            "title": "Minor",
            "summary": "Cosmetic issue.",
            "evidence_paths": ["src/example.py"],
            "recommended_action": "Ignore.",
        }
        result_with_finding = _validated_adapter_result(findings=[finding])
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        msg_repo = SpyMessageRepo({PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})
        svc = ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService(
            session_repository=FakeSessionRepo(), message_repository=msg_repo,
            task_repository=FakeTaskRepo(), adapter_service=SpyAdapter(result_with_finding),
        )
        result = _call_service(svc)
        action = result.message.suggested_actions[0]
        findings = action["findings"]
        assert isinstance(findings, list)
        assert len(findings) == 1
        assert isinstance(findings[0], dict)
        json.dumps(findings)


# ══════════════════════════════════════════════════════════════════════
# P. Side-effect boundary
# ══════════════════════════════════════════════════════════════════════


class TestSideEffectBoundary:
    def test_write_flags_false(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        msg_repo = SpyMessageRepo({PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff})
        svc = ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService(
            session_repository=FakeSessionRepo(), message_repository=msg_repo,
            task_repository=FakeTaskRepo(), adapter_service=SpyAdapter(),
        )
        result = _call_service(svc)
        action = result.message.suggested_actions[0]
        for flag in WRITE_FLAGS:
            assert action.get(flag) is False, f"{flag} should be False"
        assert action["ai_project_director_total_loop"] == "Partial"


# ══════════════════════════════════════════════════════════════════════
# Q. Repository dependency contract
# ══════════════════════════════════════════════════════════════════════


class TestRepositoryDependency:
    def test_missing_session_repo(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService(
            session_repository=None, message_repository=SpyMessageRepo(),
            task_repository=FakeTaskRepo(), adapter_service=SpyAdapter(),
        )
        with pytest.raises(ValueError, match="repositories are required"):
            _call_service(svc)

    def test_missing_message_repo(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService(
            session_repository=FakeSessionRepo(), message_repository=None,
            task_repository=FakeTaskRepo(), adapter_service=SpyAdapter(),
        )
        with pytest.raises(ValueError, match="repositories are required"):
            _call_service(svc)

    def test_missing_task_repo(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService(
            session_repository=FakeSessionRepo(), message_repository=SpyMessageRepo(),
            task_repository=None, adapter_service=SpyAdapter(),
        )
        with pytest.raises(ValueError, match="repositories are required"):
            _call_service(svc)


# ══════════════════════════════════════════════════════════════════════
# H-C2. Deferred transport resolver contracts
# ══════════════════════════════════════════════════════════════════════


class SpyResolver:
    """Test-side resolver that records calls and returns a configurable transport."""

    def __init__(self, transport=None, *, raise_exc=None) -> None:
        self._transport = transport or FakeReadonlyReviewerTransport(raw_output_text="ok")
        self._raise_exc = raise_exc
        self.calls: list[str] = []

    def __call__(self, requested_reviewer_executor: str):
        self.calls.append(requested_reviewer_executor)
        if self._raise_exc is not None:
            raise self._raise_exc
        return self._transport


def _call_resolver_service(svc, *, session_id=SESSION_ID, task_id=TASK_ID,
                            message_id=PREFLIGHT_MSG_ID, resolver=None):
    resolver = resolver or SpyResolver()
    return svc.execute_candidate_diff_readonly_review_from_preflight_with_transport_resolver(
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=message_id,
        transport_resolver=resolver,
    )


def _make_claude_preflight_message():
    """Build a preflight message with claude-code executor and matching prompt."""
    diff_text = UNIFIED_DIFF
    diff_sha = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    prompt = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService.build_readonly_review_prompt(
        requested_reviewer_executor="claude-code",
        source_diff_sha256=diff_sha,
        review_scope_paths=SCOPE_PATHS,
        unified_diff_text=diff_text,
        review_output_schema_version=REVIEW_OUTPUT_SCHEMA_VERSION,
    )
    action = _valid_preflight_action(
        requested_reviewer_executor="claude-code",
        source_diff_sha256=diff_sha,
        review_prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        review_prompt_bytes=len(prompt.encode("utf-8")),
    )
    return _make_preflight_message(action=action)


# ── A. Evidence blocked → resolver 0 ────────────────────────────────


class TestResolverEvidenceBlocked:
    def test_preflight_missing_resolver_not_called(self) -> None:
        svc, msg_repo, adapter = _build_service(messages={})
        resolver = SpyResolver()
        result = _call_resolver_service(svc, resolver=resolver)
        assert result.result.adapter_status == "blocked"
        assert "source_preflight_message_missing" in result.result.blocked_reasons
        assert resolver.calls == []
        assert len(adapter.invocations) == 0
        assert msg_repo.create_calls == []
        assert msg_repo.commit_calls == 0

    def test_prompt_sha256_mismatch_resolver_not_called(self) -> None:
        action = _valid_preflight_action(review_prompt_sha256="a" * 64)
        preflight = _make_preflight_message(action=action)
        diff = _make_diff_message()
        svc, msg_repo, adapter = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        resolver = SpyResolver()
        result = _call_resolver_service(svc, resolver=resolver)
        assert result.result.adapter_status == "blocked"
        assert "review_prompt_sha256_mismatch" in result.result.blocked_reasons
        assert resolver.calls == []
        assert len(adapter.invocations) == 0
        assert msg_repo.create_calls == []
        assert msg_repo.commit_calls == 0


# ── B. Resolver success → exactly 1 ────────────────────────────────


class TestResolverSuccessInvocation:
    def test_resolver_called_once_adapter_called_once(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        svc, msg_repo, adapter = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        sentinel = FakeReadonlyReviewerTransport(raw_output_text="ok")
        resolver = SpyResolver(transport=sentinel)
        result = _call_resolver_service(svc, resolver=resolver)
        assert len(resolver.calls) == 1
        assert len(adapter.invocations) == 1
        assert adapter.invocations[0]["transport"] is sentinel
        assert result.result.adapter_status == "validated_output"
        assert len(msg_repo.create_calls) == 1
        assert msg_repo.commit_calls == 1


# ── C. Resolver input from persisted executor ───────────────────────


class TestResolverInputFromPersistedExecutor:
    def test_codex_executor_passed_to_resolver(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        svc, _, _ = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        resolver = SpyResolver()
        _call_resolver_service(svc, resolver=resolver)
        assert resolver.calls == ["codex"]

    def test_claude_code_executor_passed_to_resolver(self) -> None:
        preflight = _make_claude_preflight_message()
        diff = _make_diff_message()
        svc, _, _ = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        resolver = SpyResolver()
        _call_resolver_service(svc, resolver=resolver)
        assert resolver.calls == ["claude-code"]


# ── D. Resolver exception failure ───────────────────────────────────


class TestResolverExceptionFailure:
    @pytest.mark.parametrize("exc", [ValueError("bad"), RuntimeError("crash")])
    def test_resolver_exception_blocks(self, exc) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        svc, msg_repo, adapter = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        resolver = SpyResolver(raise_exc=exc)
        result = _call_resolver_service(svc, resolver=resolver)
        assert len(resolver.calls) == 1
        assert result.result.adapter_status == "blocked"
        assert "readonly_reviewer_transport_resolution_failed" in result.result.blocked_reasons
        assert len(adapter.invocations) == 0
        assert msg_repo.create_calls == []
        assert msg_repo.commit_calls == 0


# ── E. Invalid resolved transport ───────────────────────────────────


class TestResolverInvalidTransport:
    def test_non_protocol_object_blocks(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        svc, msg_repo, adapter = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        resolver = SpyResolver(transport="not_a_transport")
        result = _call_resolver_service(svc, resolver=resolver)
        assert len(resolver.calls) == 1
        assert result.result.adapter_status == "blocked"
        assert "readonly_reviewer_transport_resolution_failed" in result.result.blocked_reasons
        assert len(adapter.invocations) == 0
        assert msg_repo.create_calls == []
        assert msg_repo.commit_calls == 0

    def test_none_object_blocks(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        svc, msg_repo, adapter = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )

        class NoneResolver:
            calls: list[str] = []
            def __call__(self, executor):
                NoneResolver.calls.append(executor)
                return None

        resolver = NoneResolver()
        result = _call_resolver_service(svc, resolver=resolver)
        assert len(resolver.calls) == 1
        assert result.result.adapter_status == "blocked"
        assert "readonly_reviewer_transport_resolution_failed" in result.result.blocked_reasons
        assert len(adapter.invocations) == 0


# ── F. Resolver success + Adapter blocked ───────────────────────────


class TestResolverSuccessAdapterBlocked:
    def test_adapter_blocked_no_persist(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        svc, msg_repo, adapter = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
            adapter_result=_blocked_adapter_result(),
        )
        resolver = SpyResolver()
        result = _call_resolver_service(svc, resolver=resolver)
        assert len(resolver.calls) == 1
        assert len(adapter.invocations) == 1
        assert result.result.adapter_status == "blocked"
        assert msg_repo.create_calls == []
        assert msg_repo.commit_calls == 0
        assert result.message is None


# ── G. Resolver success + validated output ──────────────────────────


class TestResolverSuccessValidated:
    def test_validated_one_message_one_commit(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        svc, msg_repo, adapter = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        resolver = SpyResolver()
        result = _call_resolver_service(svc, resolver=resolver)
        assert len(resolver.calls) == 1
        assert len(adapter.invocations) == 1
        assert result.result.adapter_status == "validated_output"
        assert len(msg_repo.create_calls) == 1
        assert msg_repo.commit_calls == 1
        assert result.message is not None


# ── H. Direct transport legacy (no resolver) ────────────────────────
# Covered by existing TestCallerTransport.test_same_transport_reaches_adapter
# No additional test needed; targeted regression verifies it.


# ── I. Resolver / transport / secret absence ────────────────────────


class TestResolverSecretAbsence:
    def test_resolver_transport_not_in_persisted_action(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        svc, _, _ = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        sentinel_secret = "SENTINEL_SECRET_SHOULD_NOT_APPEAR_12345"
        sentinel = FakeReadonlyReviewerTransport(raw_output_text=sentinel_secret)
        resolver = SpyResolver(transport=sentinel)
        result = _call_resolver_service(svc, resolver=resolver)
        action = result.message.suggested_actions[0]
        action_str = json.dumps(action)
        assert "resolver" not in action
        assert "transport" not in action
        assert "transport_resolver" not in action
        assert "raw_output_text" not in action
        assert "review_prompt_text" not in action
        assert "unified_diff_text" not in action
        assert sentinel_secret not in action_str
        assert "ANTHROPIC_AUTH_TOKEN" not in action_str
        assert "ANTHROPIC_BASE_URL" not in action_str
        assert "API_KEY" not in action_str
        assert "credential" not in action_str
        assert "environment" not in action_str
        assert "raw_output_text" not in action_str
        assert "transport_status" in action
        assert "transport_error_code" in action


# ── J. No concrete transport composition ────────────────────────────


class TestNoConcreteTransportBinding:
    def test_service_has_no_concrete_transport_imports(self) -> None:
        import inspect
        source = inspect.getsource(
            ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService
        )
        assert "NativeReadonlyReviewerCaptureTransport" not in source
        assert "CodexAppServerReadonlyReviewerTransport" not in source
        assert "MiMo" not in source
        assert "DeepSeek" not in source
