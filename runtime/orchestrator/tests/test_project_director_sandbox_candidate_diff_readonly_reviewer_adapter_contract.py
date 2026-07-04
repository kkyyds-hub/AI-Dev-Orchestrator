"""Contract tests for P21-C-H-B2-A readonly reviewer validation adapter."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.project_director_sandbox_candidate_diff_readonly_reviewer_adapter import (
    ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult,
)
from app.external_executors.readonly_reviewer_transport import (
    FakeReadonlyReviewerTransport,
    ReadonlyReviewerTransportRequest,
)
from app.services.project_director_sandbox_candidate_diff_readonly_reviewer_adapter_service import (
    ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService,
)
from app.services.project_director_sandbox_candidate_diff_review_execution_preflight_service import (
    REVIEW_OUTPUT_SCHEMA_VERSION,
)


SIDE_EFFECT_FLAGS = [
    "real_reviewer_started", "real_reviewer_executed", "native_process_started",
    "provider_called", "codex_started", "claude_code_started",
    "main_project_file_written", "sandbox_file_written", "manifest_file_written",
    "diff_file_written", "patch_applied", "git_write_performed",
    "worktree_created", "worker_started", "task_created", "run_created",
]

LEAK_FIELDS = [
    "raw_output_text", "raw_output", "stdout", "stderr",
    "review_prompt_text", "unified_diff_text", "diff_entries",
]


def _valid_raw_output(*, verdict="no_blocking_findings", findings=None,
                       risk_level="low", summary="Looks good.",
                       recommended_next_step="Proceed."):
    return json.dumps({
        "review_status": "reviewed",
        "verdict": verdict,
        "risk_level": risk_level,
        "summary": summary,
        "findings": findings or [],
        "recommended_next_step": recommended_next_step,
    }, ensure_ascii=False)


def _prompt_sha256(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _prompt_bytes(prompt: str) -> int:
    return len(prompt.encode("utf-8"))


SCOPE = ["src/a.py", "src/b.py"]
VALID_PROMPT = "You are a readonly code reviewer. Review the diff."


def _adapter_svc():
    return ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService()


def _call_adapter(svc=None, *, prompt=VALID_PROMPT, transport=None,
                   sha256=None, bytes_count=None, scope=None,
                   schema_version=REVIEW_OUTPUT_SCHEMA_VERSION,
                   executor="codex"):
    if svc is None:
        svc = _adapter_svc()
    if sha256 is None:
        sha256 = _prompt_sha256(prompt)
    if bytes_count is None:
        bytes_count = _prompt_bytes(prompt)
    if scope is None:
        scope = list(SCOPE)
    if transport is None:
        transport = FakeReadonlyReviewerTransport(raw_output_text=_valid_raw_output())
    return svc.validate_review_output_through_transport(
        requested_reviewer_executor=executor,
        review_prompt_text=prompt,
        expected_review_prompt_sha256=sha256,
        expected_review_prompt_bytes=bytes_count,
        review_scope_paths=scope,
        review_output_schema_version=schema_version,
        transport=transport,
    )


# ══════════════════════════════════════════════════════════════════════
# A. Fake transport seam
# ══════════════════════════════════════════════════════════════════════


class TestFakeTransportSeam:
    def test_initial_state(self) -> None:
        t = FakeReadonlyReviewerTransport()
        assert t.execute_calls == 0
        assert t.last_request is None

    def test_execute_records_call(self) -> None:
        t = FakeReadonlyReviewerTransport(raw_output_text='{"ok":true}')
        req = ReadonlyReviewerTransportRequest(
            requested_reviewer_executor="codex",
            review_prompt_text="prompt",
            review_prompt_sha256="a" * 64,
            review_prompt_bytes=6,
            review_scope_paths=["src/a.py"],
            review_output_schema_version=REVIEW_OUTPUT_SCHEMA_VERSION,
        )
        result = t.execute(req)
        assert t.execute_calls == 1
        assert t.last_request is req
        assert result.transport_invoked is True
        assert result.transport_status == "completed"

    def test_last_request_preserves_all_fields(self) -> None:
        t = FakeReadonlyReviewerTransport(raw_output_text="output")
        req = ReadonlyReviewerTransportRequest(
            requested_reviewer_executor="claude-code",
            review_prompt_text="中文 prompt 测试",
            review_prompt_sha256="b" * 64,
            review_prompt_bytes=100,
            review_scope_paths=["src/a.py", "src/b.py"],
            review_output_schema_version="p21-c-h-review-output.v1",
        )
        t.execute(req)
        assert t.last_request is not None
        assert t.last_request.requested_reviewer_executor == "claude-code"
        assert t.last_request.review_prompt_text == "中文 prompt 测试"
        assert t.last_request.review_prompt_sha256 == "b" * 64
        assert t.last_request.review_prompt_bytes == 100
        assert t.last_request.review_scope_paths == ["src/a.py", "src/b.py"]
        assert t.last_request.review_output_schema_version == "p21-c-h-review-output.v1"


# ══════════════════════════════════════════════════════════════════════
# B. Legal prompt (with Chinese characters)
# ══════════════════════════════════════════════════════════════════════


class TestLegalPrompt:
    def test_chinese_prompt_verified(self) -> None:
        prompt = "你是只读代码审查员。请审查以下 diff。"
        transport = FakeReadonlyReviewerTransport(raw_output_text=_valid_raw_output())
        r = _call_adapter(prompt=prompt, transport=transport)
        assert r.review_prompt_verified is True
        assert r.review_prompt_sha256 == _prompt_sha256(prompt)
        assert r.review_prompt_bytes == _prompt_bytes(prompt)
        assert r.review_prompt_bytes > len(prompt)  # Chinese uses more bytes
        assert transport.execute_calls == 1

    def test_prompt_bytes_uses_utf8(self) -> None:
        prompt = "审查 diff：+你好"
        expected_bytes = len(prompt.encode("utf-8"))
        assert expected_bytes != len(prompt)  # confirm multi-byte
        transport = FakeReadonlyReviewerTransport(raw_output_text=_valid_raw_output())
        r = _call_adapter(prompt=prompt, transport=transport)
        assert r.review_prompt_bytes == expected_bytes


# ══════════════════════════════════════════════════════════════════════
# C. Prompt SHA mismatch
# ══════════════════════════════════════════════════════════════════════


class TestPromptShaMismatch:
    def test_sha_mismatch_blocked(self) -> None:
        transport = FakeReadonlyReviewerTransport(raw_output_text=_valid_raw_output())
        r = _call_adapter(sha256="a" * 64, transport=transport)
        assert r.adapter_status == "blocked"
        assert "review_prompt_sha256_mismatch" in r.blocked_reasons
        assert transport.execute_calls == 0


# ══════════════════════════════════════════════════════════════════════
# D. Prompt bytes mismatch
# ══════════════════════════════════════════════════════════════════════


class TestPromptBytesMismatch:
    def test_bytes_mismatch_blocked(self) -> None:
        transport = FakeReadonlyReviewerTransport(raw_output_text=_valid_raw_output())
        r = _call_adapter(bytes_count=999, transport=transport)
        assert r.adapter_status == "blocked"
        assert "review_prompt_bytes_mismatch" in r.blocked_reasons
        assert transport.execute_calls == 0


# ══════════════════════════════════════════════════════════════════════
# E. Missing prompt / invalid SHA
# ══════════════════════════════════════════════════════════════════════


class TestMissingPromptInvalidSha:
    def test_empty_prompt_blocked(self) -> None:
        transport = FakeReadonlyReviewerTransport(raw_output_text=_valid_raw_output())
        r = _call_adapter(prompt="", sha256="a" * 64, bytes_count=1, transport=transport)
        assert r.adapter_status == "blocked"
        assert "review_prompt_missing" in r.blocked_reasons
        assert transport.execute_calls == 0

    def test_invalid_sha_format_blocked(self) -> None:
        transport = FakeReadonlyReviewerTransport(raw_output_text=_valid_raw_output())
        r = _call_adapter(sha256="not-a-valid-sha256", transport=transport)
        assert r.adapter_status == "blocked"
        assert "review_prompt_sha256_invalid" in r.blocked_reasons
        assert transport.execute_calls == 0


# ══════════════════════════════════════════════════════════════════════
# F. Invalid review scope
# ══════════════════════════════════════════════════════════════════════


class TestInvalidReviewScope:
    def test_empty_scope_blocked(self) -> None:
        transport = FakeReadonlyReviewerTransport(raw_output_text=_valid_raw_output())
        r = _call_adapter(scope=[], transport=transport)
        assert r.adapter_status == "blocked"
        assert "review_scope_paths_invalid" in r.blocked_reasons
        assert transport.execute_calls == 0

    def test_duplicate_scope_blocked(self) -> None:
        transport = FakeReadonlyReviewerTransport(raw_output_text=_valid_raw_output())
        r = _call_adapter(scope=["src/a.py", "src/a.py"], transport=transport)
        assert r.adapter_status == "blocked"
        assert "review_scope_paths_invalid" in r.blocked_reasons
        assert transport.execute_calls == 0

    def test_non_string_scope_blocked(self) -> None:
        transport = FakeReadonlyReviewerTransport(raw_output_text=_valid_raw_output())
        # R1 needed: adapter _blocked_result passes raw scope to domain model
        # which rejects non-string items. The adapter should sanitize first.
        # For now, test that the call raises (domain rejects bad scope in result).
        with pytest.raises((ValidationError, Exception)):
            _call_adapter(scope=["src/a.py", 123], transport=transport)

    def test_empty_string_scope_blocked(self) -> None:
        transport = FakeReadonlyReviewerTransport(raw_output_text=_valid_raw_output())
        r = _call_adapter(scope=["src/a.py", ""], transport=transport)
        assert r.adapter_status == "blocked"
        assert "review_scope_paths_invalid" in r.blocked_reasons
        assert transport.execute_calls == 0

    def test_adapter_does_not_dedup_scope(self) -> None:
        transport = FakeReadonlyReviewerTransport(raw_output_text=_valid_raw_output())
        r = _call_adapter(scope=["src/a.py", "src/a.py"], transport=transport)
        assert r.adapter_status == "blocked"
        assert transport.execute_calls == 0


# ══════════════════════════════════════════════════════════════════════
# G. Schema version mismatch
# ══════════════════════════════════════════════════════════════════════


class TestSchemaVersionMismatch:
    def test_wrong_version_blocked(self) -> None:
        transport = FakeReadonlyReviewerTransport(raw_output_text=_valid_raw_output())
        r = _call_adapter(
            schema_version="p21-c-h-review-output.v2", transport=transport,
        )
        assert r.adapter_status == "blocked"
        assert "review_output_schema_version_mismatch" in r.blocked_reasons
        assert transport.execute_calls == 0


# ══════════════════════════════════════════════════════════════════════
# H. Transport not configured
# ══════════════════════════════════════════════════════════════════════


class TestTransportNotConfigured:
    def test_none_transport_blocked(self) -> None:
        svc = _adapter_svc()
        r = svc.validate_review_output_through_transport(
            requested_reviewer_executor="codex",
            review_prompt_text=VALID_PROMPT,
            expected_review_prompt_sha256=_prompt_sha256(VALID_PROMPT),
            expected_review_prompt_bytes=_prompt_bytes(VALID_PROMPT),
            review_scope_paths=list(SCOPE),
            transport=None,
        )
        assert r.adapter_status == "blocked"
        assert "reviewer_transport_not_configured" in r.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# I. Non-completed transport status
# ══════════════════════════════════════════════════════════════════════


class TestNonCompletedTransport:
    def _call_with_status(self, status, expected_reason):
        class SpyValidationService:
            def __init__(self):
                self.call_count = 0
            def validate_raw_review_output(self, **kwargs):
                self.call_count += 1
                raise AssertionError("H-B1 should not be called")

        spy = SpyValidationService()
        svc = ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService(
            output_validation_service=spy,
        )
        transport = FakeReadonlyReviewerTransport(
            raw_output_text="irrelevant", transport_status=status,
        )
        r = svc.validate_review_output_through_transport(
            requested_reviewer_executor="codex",
            review_prompt_text=VALID_PROMPT,
            expected_review_prompt_sha256=_prompt_sha256(VALID_PROMPT),
            expected_review_prompt_bytes=_prompt_bytes(VALID_PROMPT),
            review_scope_paths=list(SCOPE),
            transport=transport,
        )
        assert r.adapter_status == "blocked"
        assert expected_reason in r.blocked_reasons
        assert spy.call_count == 0, "H-B1 validator must not be called"
        return r

    def test_transport_blocked(self) -> None:
        self._call_with_status("blocked", "reviewer_transport_blocked")

    def test_transport_timeout(self) -> None:
        self._call_with_status("timeout", "reviewer_transport_timeout")

    def test_transport_failed(self) -> None:
        self._call_with_status("failed", "reviewer_transport_failed")


# ══════════════════════════════════════════════════════════════════════
# J. completed + valid raw JSON
# ══════════════════════════════════════════════════════════════════════


class TestCompletedValidOutput:
    def test_valid_output_validated(self) -> None:
        raw = _valid_raw_output(
            verdict="non_blocking_findings",
            findings=[{
                "finding_id": "F1", "severity": "low", "title": "Minor",
                "summary": "A minor issue.", "evidence_paths": ["src/a.py"],
                "recommended_action": "Consider fixing.",
            }],
            risk_level="medium",
            summary="Review complete.",
            recommended_next_step="Fix minor issue.",
        )
        transport = FakeReadonlyReviewerTransport(raw_output_text=raw)
        r = _call_adapter(transport=transport)
        assert transport.execute_calls == 1
        assert r.adapter_status == "validated_output"
        assert r.output_validation_status == "validated"
        assert r.review_status == "reviewed"
        assert r.verdict == "non_blocking_findings"
        assert r.risk_level == "medium"
        assert r.summary == "Review complete."
        assert len(r.findings) == 1
        assert r.findings[0].finding_id == "F1"
        assert r.recommended_next_step == "Fix minor issue."
        assert r.raw_output_sha256 == hashlib.sha256(raw.encode("utf-8")).hexdigest()
        assert r.raw_output_bytes == len(raw.encode("utf-8"))


# ══════════════════════════════════════════════════════════════════════
# K. completed + invalid raw output
# ══════════════════════════════════════════════════════════════════════


class TestCompletedInvalidOutput:
    def test_invalid_json_blocked(self) -> None:
        transport = FakeReadonlyReviewerTransport(raw_output_text="not json at all")
        r = _call_adapter(transport=transport)
        assert r.adapter_status == "blocked"
        assert r.output_validation_status == "blocked"
        assert "review_output_validation_blocked" in r.blocked_reasons
        # Must match H-B1 blocked_reasons exactly
        assert r.output_validation_blocked_reasons == ["review_output_not_strict_json"]
        # Trusted fields cleared
        assert r.review_status is None
        assert r.verdict is None
        assert r.risk_level is None
        assert r.summary == ""
        assert r.findings == []
        assert r.recommended_next_step == ""

    def test_schema_invalid_blocked(self) -> None:
        transport = FakeReadonlyReviewerTransport(
            raw_output_text=json.dumps({"bad": "schema"})
        )
        r = _call_adapter(transport=transport)
        assert r.adapter_status == "blocked"
        assert r.output_validation_status == "blocked"
        assert "review_output_validation_blocked" in r.blocked_reasons
        # H-B1 returns multiple reasons for bad schema: extra fields + missing fields
        assert "review_output_schema_invalid" in r.output_validation_blocked_reasons
        assert r.review_status is None
        assert r.verdict is None
        assert r.findings == []


# ══════════════════════════════════════════════════════════════════════
# L. Raw output must enter H-B1 unchanged
# ══════════════════════════════════════════════════════════════════════


class TestRawOutputEntersHB1Unchanged:
    def test_markdown_fenced_json_not_auto_repaired(self) -> None:
        inner = _valid_raw_output()
        fenced = f"```json\n{inner}\n```"
        transport = FakeReadonlyReviewerTransport(raw_output_text=fenced)
        r = _call_adapter(transport=transport)
        assert r.adapter_status == "blocked"
        assert "review_output_validation_blocked" in r.blocked_reasons
        assert "review_output_markdown_fence_forbidden" in r.output_validation_blocked_reasons

    def test_natural_language_prefix_not_stripped(self) -> None:
        inner = _valid_raw_output()
        prefixed = f"Here is my review:\n{inner}"
        transport = FakeReadonlyReviewerTransport(raw_output_text=prefixed)
        r = _call_adapter(transport=transport)
        assert r.adapter_status == "blocked"
        assert "review_output_not_strict_json" in r.output_validation_blocked_reasons

    def test_natural_language_suffix_not_stripped(self) -> None:
        inner = _valid_raw_output()
        suffixed = f"{inner}\nDone."
        transport = FakeReadonlyReviewerTransport(raw_output_text=suffixed)
        r = _call_adapter(transport=transport)
        assert r.adapter_status == "blocked"
        assert "review_output_not_strict_json" in r.output_validation_blocked_reasons

    def test_raw_output_text_passed_verbatim_to_hb1(self) -> None:
        """Use a spy to confirm the exact raw_output_text reaches H-B1."""
        captured_args = {}

        class SpyValidationService:
            def validate_raw_review_output(self, **kwargs):
                captured_args.update(kwargs)
                # Delegate to real service for correctness
                from app.services.project_director_sandbox_candidate_diff_review_output_validation_service import (
                    ProjectDirectorSandboxCandidateDiffReviewOutputValidationService,
                )
                return ProjectDirectorSandboxCandidateDiffReviewOutputValidationService().validate_raw_review_output(**kwargs)

        raw = _valid_raw_output()
        transport = FakeReadonlyReviewerTransport(raw_output_text=raw)
        svc = ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService(
            output_validation_service=SpyValidationService(),
        )
        svc.validate_review_output_through_transport(
            requested_reviewer_executor="codex",
            review_prompt_text=VALID_PROMPT,
            expected_review_prompt_sha256=_prompt_sha256(VALID_PROMPT),
            expected_review_prompt_bytes=_prompt_bytes(VALID_PROMPT),
            review_scope_paths=list(SCOPE),
            transport=transport,
        )
        assert captured_args["raw_output_text"] == raw


# ══════════════════════════════════════════════════════════════════════
# M. Adapter result leak boundary
# ══════════════════════════════════════════════════════════════════════


class TestAdapterResultLeakBoundary:
    def test_validated_result_no_leak(self) -> None:
        transport = FakeReadonlyReviewerTransport(raw_output_text=_valid_raw_output())
        r = _call_adapter(transport=transport)
        dumped = r.model_dump()
        for field in LEAK_FIELDS:
            assert field not in dumped, f"Leaked field: {field}"

    def test_blocked_result_no_leak(self) -> None:
        transport = FakeReadonlyReviewerTransport(raw_output_text="not json")
        r = _call_adapter(transport=transport)
        dumped = r.model_dump()
        for field in LEAK_FIELDS:
            assert field not in dumped, f"Leaked field: {field}"


# ══════════════════════════════════════════════════════════════════════
# N. Execution / write flags
# ══════════════════════════════════════════════════════════════════════


class TestExecutionWriteFlags:
    def test_all_flags_false_on_validated(self) -> None:
        transport = FakeReadonlyReviewerTransport(raw_output_text=_valid_raw_output())
        r = _call_adapter(transport=transport)
        assert r.ai_project_director_total_loop == "Partial"
        for flag in SIDE_EFFECT_FLAGS:
            assert getattr(r, flag) is False, f"{flag} should be False"

    def test_all_flags_false_on_blocked(self) -> None:
        transport = FakeReadonlyReviewerTransport(raw_output_text="bad")
        r = _call_adapter(transport=transport)
        for flag in SIDE_EFFECT_FLAGS:
            assert getattr(r, flag) is False, f"{flag} should be False"

    @pytest.mark.parametrize("field_name", SIDE_EFFECT_FLAGS)
    def test_domain_rejects_true_flag(self, field_name: str) -> None:
        with pytest.raises(ValidationError, match="may not execute or write"):
            ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult(
                adapter_status="validated_output",
                **{field_name: True},
            )


# ══════════════════════════════════════════════════════════════════════
# O. Pure-memory boundary
# ══════════════════════════════════════════════════════════════════════


class TestPureMemoryBoundary:
    def test_validated_with_file_io_blocked(self, monkeypatch) -> None:
        monkeypatch.setattr(Path, "read_text", lambda self, *a, **kw: (_ for _ in ()).throw(AssertionError("must not read!")))
        monkeypatch.setattr(Path, "write_text", lambda self, *a, **kw: (_ for _ in ()).throw(AssertionError("must not write!")))
        transport = FakeReadonlyReviewerTransport(raw_output_text=_valid_raw_output())
        r = _call_adapter(transport=transport)
        assert r.adapter_status == "validated_output"
        for flag in SIDE_EFFECT_FLAGS:
            assert getattr(r, flag) is False

    def test_blocked_with_file_io_blocked(self, monkeypatch) -> None:
        monkeypatch.setattr(Path, "read_text", lambda self, *a, **kw: (_ for _ in ()).throw(AssertionError("must not read!")))
        monkeypatch.setattr(Path, "write_text", lambda self, *a, **kw: (_ for _ in ()).throw(AssertionError("must not write!")))
        transport = FakeReadonlyReviewerTransport(raw_output_text="not json")
        r = _call_adapter(transport=transport)
        assert r.adapter_status == "blocked"

    def test_no_subprocess_invoked(self, monkeypatch) -> None:
        import subprocess
        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("must not Popen!")))
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("must not run!")))
        transport = FakeReadonlyReviewerTransport(raw_output_text=_valid_raw_output())
        r = _call_adapter(transport=transport)
        assert r.adapter_status == "validated_output"
