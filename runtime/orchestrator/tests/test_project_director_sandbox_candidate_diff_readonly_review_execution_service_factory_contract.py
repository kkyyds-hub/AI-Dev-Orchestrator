"""Contract tests for execution service factory path."""

from __future__ import annotations

import ast
import hashlib
import inspect
from typing import Any
from unittest.mock import MagicMock
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
    ReadonlyReviewerTransportProtocol,
)
from app.services.project_director_sandbox_candidate_diff_readonly_review_execution_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
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

TRUSTED_WORKSPACE = "/trusted/persisted/workspace"


# ── Spy classes ─────────────────────────────────────────────────────


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


class SpyAdapter:
    def __init__(self, result=None):
        self._result = result or _validated_adapter_result()
        self.invocations: list[dict[str, Any]] = []

    def validate_review_output_through_transport(self, **kwargs):
        self.invocations.append(kwargs)
        return self._result


class SpyResolver:
    def __init__(self, transport=None):
        self._transport = transport or MagicMock(spec=ReadonlyReviewerTransportProtocol)
        self.calls: list[str] = []

    def __call__(self, executor: str):
        self.calls.append(executor)
        return self._transport


class SpyFactory:
    def __init__(self, resolver=None, *, raise_exc=None):
        self._resolver = resolver or SpyResolver()
        self._raise_exc = raise_exc
        self.calls: list[str] = []

    def __call__(self, workspace_path: str):
        self.calls.append(workspace_path)
        if self._raise_exc is not None:
            raise self._raise_exc
        return self._resolver


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
        "workspace_path": TRUSTED_WORKSPACE,
        "workspace_path_within_root": True,
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


def _make_preflight_message(action=None, **overrides):
    return ProjectDirectorMessage(
        id=PREFLIGHT_MSG_ID, session_id=SESSION_ID,
        role=ProjectDirectorMessageRole.ASSISTANT, content="preflight", sequence_no=5,
        intent="sandbox_candidate_diff_review_execution_preflight",
        related_project_id=PROJECT_ID, related_task_id=TASK_ID,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_EXECUTION_PREFLIGHT_SOURCE_DETAIL,
        suggested_actions=[action or _valid_preflight_action(**overrides)],
    )


def _make_diff_message(action=None, **overrides):
    return ProjectDirectorMessage(
        id=DIFF_MSG_ID, session_id=SESSION_ID,
        role=ProjectDirectorMessageRole.ASSISTANT, content="diff", sequence_no=3,
        intent="sandbox_candidate_diff",
        related_project_id=PROJECT_ID, related_task_id=TASK_ID,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL,
        suggested_actions=[action or _valid_diff_action(**overrides)],
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
    kwargs = dict(adapter_status="blocked", blocked_reasons=["test_blocked"])
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


def _call_factory_path(svc, *, factory, session_id=SESSION_ID, task_id=TASK_ID,
                        message_id=PREFLIGHT_MSG_ID):
    return svc.execute_candidate_diff_readonly_review_from_preflight_with_transport_resolver_factory(
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=message_id,
        transport_resolver_factory=factory,
    )


# ══════════════════════════════════════════════════════════════════════
# B1. Early preflight failure → Factory 0
# ══════════════════════════════════════════════════════════════════════


class TestEarlyPreflightFailure:
    def test_preflight_missing_factory_not_called(self) -> None:
        svc, msg_repo, adapter = _build_service(messages={})
        factory = SpyFactory()
        result = _call_factory_path(svc, factory=factory)
        assert result.result.adapter_status == "blocked"
        assert factory.calls == []
        assert adapter.invocations == []
        assert msg_repo.create_calls == []
        assert msg_repo.commit_calls == 0


# ══════════════════════════════════════════════════════════════════════
# B2. Source diff failure → Factory 0
# ══════════════════════════════════════════════════════════════════════


class TestSourceDiffFailure:
    def test_diff_message_missing_factory_not_called(self) -> None:
        preflight = _make_preflight_message()
        svc, _, _ = _build_service(messages={PREFLIGHT_MSG_ID: preflight})
        factory = SpyFactory()
        result = _call_factory_path(svc, factory=factory)
        assert result.result.adapter_status == "blocked"
        assert factory.calls == []


# ══════════════════════════════════════════════════════════════════════
# B3. Diff SHA mismatch → Factory 0
# ══════════════════════════════════════════════════════════════════════


class TestDiffShaMismatch:
    def test_sha_mismatch_factory_not_called(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message(unified_diff_text="different content\n")
        svc, _, _ = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        factory = SpyFactory()
        result = _call_factory_path(svc, factory=factory)
        assert result.result.adapter_status == "blocked"
        assert factory.calls == []


# ══════════════════════════════════════════════════════════════════════
# B4. Prompt SHA mismatch → Factory 0
# ══════════════════════════════════════════════════════════════════════


class TestPromptShaMismatch:
    def test_prompt_sha_mismatch_factory_not_called(self) -> None:
        preflight = _make_preflight_message(review_prompt_sha256="a" * 64)
        diff = _make_diff_message()
        svc, _, _ = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        factory = SpyFactory()
        result = _call_factory_path(svc, factory=factory)
        assert result.result.adapter_status == "blocked"
        assert "review_prompt_sha256_mismatch" in result.result.blocked_reasons
        assert factory.calls == []


# ══════════════════════════════════════════════════════════════════════
# B5. Prompt bytes mismatch → Factory 0
# ══════════════════════════════════════════════════════════════════════


class TestPromptBytesMismatch:
    def test_prompt_bytes_mismatch_factory_not_called(self) -> None:
        preflight = _make_preflight_message(review_prompt_bytes=999999)
        diff = _make_diff_message()
        svc, _, _ = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        factory = SpyFactory()
        result = _call_factory_path(svc, factory=factory)
        assert result.result.adapter_status == "blocked"
        assert "review_prompt_bytes_mismatch" in result.result.blocked_reasons
        assert factory.calls == []


# ══════════════════════════════════════════════════════════════════════
# B6. workspace_path missing → blocked
# ══════════════════════════════════════════════════════════════════════


class TestWorkspacePathMissing:
    def test_workspace_path_missing_blocked(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message(workspace_path=None)
        svc, msg_repo, adapter = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        factory = SpyFactory()
        result = _call_factory_path(svc, factory=factory)
        assert result.result.adapter_status == "blocked"
        assert "source_diff_workspace_path_missing" in result.result.blocked_reasons
        assert factory.calls == []
        assert adapter.invocations == []
        assert msg_repo.create_calls == []
        assert msg_repo.commit_calls == 0

    def test_workspace_path_empty_blocked(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message(workspace_path="")
        svc, _, _ = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        factory = SpyFactory()
        result = _call_factory_path(svc, factory=factory)
        assert "source_diff_workspace_path_missing" in result.result.blocked_reasons
        assert factory.calls == []


# ══════════════════════════════════════════════════════════════════════
# B7. workspace_path non-string / blank
# ══════════════════════════════════════════════════════════════════════


class TestWorkspacePathInvalid:
    @pytest.mark.parametrize("value", [None, "", "   ", 123])
    def test_invalid_workspace_path_blocked(self, value) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message(workspace_path=value)
        svc, _, _ = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        factory = SpyFactory()
        result = _call_factory_path(svc, factory=factory)
        assert "source_diff_workspace_path_missing" in result.result.blocked_reasons
        assert factory.calls == []


# ══════════════════════════════════════════════════════════════════════
# B8. workspace_path_within_root adversarial
# ══════════════════════════════════════════════════════════════════════


class TestWorkspacePathWithinRoot:
    @pytest.mark.parametrize("value", [False, None, 0, 1, "true"])
    def test_non_strict_true_blocked(self, value) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message(workspace_path_within_root=value)
        svc, _, _ = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        factory = SpyFactory()
        result = _call_factory_path(svc, factory=factory)
        assert "source_diff_workspace_path_not_within_root" in result.result.blocked_reasons
        assert factory.calls == []


# ══════════════════════════════════════════════════════════════════════
# B9. Factory exact once with persisted workspace
# ══════════════════════════════════════════════════════════════════════


class TestFactoryExactOnce:
    def test_factory_called_once_with_persisted_workspace(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        svc, _, _ = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        factory = SpyFactory()
        _call_factory_path(svc, factory=factory)
        assert factory.calls == [TRUSTED_WORKSPACE]


# ══════════════════════════════════════════════════════════════════════
# B10. Resolver exact once with persisted executor
# ══════════════════════════════════════════════════════════════════════


class TestResolverExactOnce:
    def test_codex_executor_passed_to_resolver(self) -> None:
        preflight = _make_preflight_message(executor="codex")
        diff = _make_diff_message()
        svc, _, _ = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        resolver = SpyResolver()
        factory = SpyFactory(resolver=resolver)
        _call_factory_path(svc, factory=factory)
        assert resolver.calls == ["codex"]

    def test_claude_code_executor_passed_to_resolver(self) -> None:
        diff_text = UNIFIED_DIFF
        diff_sha = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
        prompt = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService.build_readonly_review_prompt(
            requested_reviewer_executor="claude-code",
            source_diff_sha256=diff_sha,
            review_scope_paths=SCOPE_PATHS,
            unified_diff_text=diff_text,
            review_output_schema_version=REVIEW_OUTPUT_SCHEMA_VERSION,
        )
        preflight = _make_preflight_message(
            executor="claude-code",
            source_diff_sha256=diff_sha,
            review_prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            review_prompt_bytes=len(prompt.encode("utf-8")),
        )
        diff = _make_diff_message()
        svc, _, _ = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        resolver = SpyResolver()
        factory = SpyFactory(resolver=resolver)
        _call_factory_path(svc, factory=factory)
        assert resolver.calls == ["claude-code"]


# ══════════════════════════════════════════════════════════════════════
# B11. Adapter receives transport from resolver
# ══════════════════════════════════════════════════════════════════════


class TestAdapterReceivesTransport:
    def test_adapter_gets_resolver_transport(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        svc, _, adapter = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        sentinel_transport = MagicMock(spec=ReadonlyReviewerTransportProtocol)
        resolver = SpyResolver(transport=sentinel_transport)
        factory = SpyFactory(resolver=resolver)
        _call_factory_path(svc, factory=factory)
        assert adapter.invocations[0]["transport"] is sentinel_transport


# ══════════════════════════════════════════════════════════════════════
# B12. Success persistence
# ══════════════════════════════════════════════════════════════════════


class TestSuccessPersistence:
    def test_validated_creates_one_message(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        svc, msg_repo, _ = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        factory = SpyFactory()
        result = _call_factory_path(svc, factory=factory)
        assert result.result.adapter_status == "validated_output"
        assert len(msg_repo.create_calls) == 1
        assert msg_repo.commit_calls == 1
        assert result.message is not None


# ══════════════════════════════════════════════════════════════════════
# B13. Factory ValueError
# ══════════════════════════════════════════════════════════════════════


class TestFactoryValueError:
    def test_factory_value_error_blocked(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        svc, msg_repo, adapter = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        factory = SpyFactory(raise_exc=ValueError("workspace invalid"))
        result = _call_factory_path(svc, factory=factory)
        assert result.result.adapter_status == "blocked"
        assert "readonly_reviewer_transport_resolution_failed" in result.result.blocked_reasons
        assert factory.calls == [TRUSTED_WORKSPACE]
        assert adapter.invocations == []
        assert msg_repo.create_calls == []
        assert msg_repo.commit_calls == 0


# ══════════════════════════════════════════════════════════════════════
# B14. Factory RuntimeError
# ══════════════════════════════════════════════════════════════════════


class TestFactoryRuntimeError:
    def test_factory_runtime_error_blocked(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        svc, _, adapter = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        factory = SpyFactory(raise_exc=RuntimeError("crash"))
        result = _call_factory_path(svc, factory=factory)
        assert result.result.adapter_status == "blocked"
        assert "readonly_reviewer_transport_resolution_failed" in result.result.blocked_reasons
        assert adapter.invocations == []


# ══════════════════════════════════════════════════════════════════════
# B15. Factory returns None
# ══════════════════════════════════════════════════════════════════════


class TestFactoryReturnsNone:
    def test_factory_none_blocked(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        svc, _, adapter = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        factory = SpyFactory()
        factory._resolver = None

        def none_call(workspace_path):
            factory.calls.append(workspace_path)
            return None

        factory.__call__ = none_call
        result = _call_factory_path(svc, factory=factory)
        assert result.result.adapter_status == "blocked"
        assert "readonly_reviewer_transport_resolution_failed" in result.result.blocked_reasons
        assert adapter.invocations == []


# ══════════════════════════════════════════════════════════════════════
# B16. Resolver ValueError
# ══════════════════════════════════════════════════════════════════════


class TestResolverValueError:
    def test_resolver_value_error_blocked(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        svc, _, adapter = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )

        class FailingResolver:
            calls: list[str] = []
            def __call__(self, executor):
                FailingResolver.calls.append(executor)
                raise ValueError("bad executor")

        resolver = FailingResolver()
        factory = SpyFactory(resolver=resolver)
        result = _call_factory_path(svc, factory=factory)
        assert result.result.adapter_status == "blocked"
        assert "readonly_reviewer_transport_resolution_failed" in result.result.blocked_reasons
        assert factory.calls == [TRUSTED_WORKSPACE]
        assert resolver.calls == ["codex"]
        assert adapter.invocations == []


# ══════════════════════════════════════════════════════════════════════
# B17. Resolver RuntimeError
# ══════════════════════════════════════════════════════════════════════


class TestResolverRuntimeError:
    def test_resolver_runtime_error_blocked(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        svc, _, adapter = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )

        class FailingResolver:
            def __call__(self, executor):
                raise RuntimeError("crash")

        factory = SpyFactory(resolver=FailingResolver())
        result = _call_factory_path(svc, factory=factory)
        assert result.result.adapter_status == "blocked"
        assert "readonly_reviewer_transport_resolution_failed" in result.result.blocked_reasons
        assert adapter.invocations == []


# ══════════════════════════════════════════════════════════════════════
# B18. Resolver returns invalid transport
# ══════════════════════════════════════════════════════════════════════


class TestResolverInvalidTransport:
    def test_invalid_transport_blocked(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        svc, _, adapter = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )

        class BadResolver:
            def __call__(self, executor):
                return object()

        factory = SpyFactory(resolver=BadResolver())
        result = _call_factory_path(svc, factory=factory)
        assert result.result.adapter_status == "blocked"
        assert "readonly_reviewer_transport_resolution_failed" in result.result.blocked_reasons
        assert adapter.invocations == []


# ══════════════════════════════════════════════════════════════════════
# B19. Direct transport backward compatibility
# ══════════════════════════════════════════════════════════════════════


class TestDirectTransportCompat:
    def test_direct_transport_path_factory_zero(self) -> None:
        from app.external_executors.readonly_reviewer_transport import (
            FakeReadonlyReviewerTransport,
        )
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        svc, msg_repo, _ = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        spy_factory = SpyFactory()
        result = svc.execute_candidate_diff_readonly_review_from_preflight(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=PREFLIGHT_MSG_ID,
            transport=FakeReadonlyReviewerTransport(raw_output_text="ok"),
        )
        assert result.result.adapter_status == "validated_output"
        assert spy_factory.calls == []


# ══════════════════════════════════════════════════════════════════════
# B20. Direct resolver backward compatibility
# ══════════════════════════════════════════════════════════════════════


class TestDirectResolverCompat:
    def test_direct_resolver_path_factory_zero(self) -> None:
        preflight = _make_preflight_message()
        diff = _make_diff_message()
        svc, _, _ = _build_service(
            messages={PREFLIGHT_MSG_ID: preflight, DIFF_MSG_ID: diff},
        )
        spy_factory = SpyFactory()
        resolver = SpyResolver()
        result = svc.execute_candidate_diff_readonly_review_from_preflight_with_transport_resolver(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=PREFLIGHT_MSG_ID,
            transport_resolver=resolver,
        )
        assert result.result.adapter_status == "validated_output"
        assert spy_factory.calls == []


# ══════════════════════════════════════════════════════════════════════
# Execution Service module boundary
# ══════════════════════════════════════════════════════════════════════


class TestExecutionServiceModuleBoundary:
    def test_no_concrete_transport_imports(self) -> None:
        import app.services.project_director_sandbox_candidate_diff_readonly_review_execution_service as mod
        source = inspect.getsource(mod)
        tree = ast.parse(source)
        imported_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module is not None:
                    imported_modules.add(node.module)
        for mod_name in imported_modules:
            assert "readonly_reviewer_transport_resolver_factory" not in mod_name
            assert "readonly_reviewer_transport_resolver" not in mod_name or mod_name.endswith("_protocol")
            assert "readonly_reviewer_codex_app_server_transport" not in mod_name
            assert "readonly_reviewer_native_transport" not in mod_name

    def test_no_forbidden_imports(self) -> None:
        import app.services.project_director_sandbox_candidate_diff_readonly_review_execution_service as mod
        source = inspect.getsource(mod)
        tree = ast.parse(source)
        imported_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module is not None:
                    imported_modules.add(node.module)
        for mod_name in imported_modules:
            top = mod_name.split(".")[0]
            assert top not in {"os", "subprocess"}, f"Forbidden: {mod_name}"
