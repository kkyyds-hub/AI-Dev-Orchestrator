"""Contract tests for P21-C-H-B1 readonly reviewer output validation."""

from __future__ import annotations

import hashlib
import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.project_director_sandbox_candidate_diff_review_output import (
    ProjectDirectorSandboxCandidateDiffReviewOutputValidationResult,
)
from app.services.project_director_sandbox_candidate_diff_review_execution_preflight_service import (
    REVIEW_OUTPUT_SCHEMA_VERSION,
)
from app.services.project_director_sandbox_candidate_diff_review_output_validation_service import (
    ProjectDirectorSandboxCandidateDiffReviewOutputValidationService,
)


SIDE_EFFECT_FLAGS = [
    "reviewer_started", "review_executed", "provider_called",
    "native_executor_started", "codex_started", "claude_code_started",
    "main_project_file_written", "sandbox_file_written", "manifest_file_written",
    "diff_file_written", "patch_applied", "git_write_performed",
    "worktree_created", "worker_started", "task_created", "run_created",
]


def _valid_output_dict(*, verdict="no_blocking_findings", findings=None,
                        risk_level="low", summary="Looks good.",
                        recommended_next_step="Proceed.", review_status="reviewed"):
    d = {
        "review_status": review_status,
        "verdict": verdict,
        "risk_level": risk_level,
        "summary": summary,
        "findings": findings if findings is not None else [],
        "recommended_next_step": recommended_next_step,
    }
    return d


def _valid_finding(*, finding_id="F1", severity="medium", title="Issue",
                    summary="Found an issue.", evidence_paths=None,
                    recommended_action="Fix it."):
    return {
        "finding_id": finding_id,
        "severity": severity,
        "title": title,
        "summary": summary,
        "evidence_paths": ["src/a.py"] if evidence_paths is None else evidence_paths,
        "recommended_action": recommended_action,
    }


def _make_raw(output_dict):
    return json.dumps(output_dict, ensure_ascii=False)


SCOPE = ["src/a.py", "src/b.py"]


# ══════════════════════════════════════════════════════════════════════
# 1. Validated basic scenarios
# ══════════════════════════════════════════════════════════════════════


class TestValidatedBasicScenarios:
    def test_no_blocking_empty_findings(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        raw = _make_raw(_valid_output_dict(verdict="no_blocking_findings", findings=[]))
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "validated"
        assert r.strict_json_valid is True
        assert r.schema_valid is True
        assert r.semantics_valid is True
        assert r.evidence_scope_valid is True
        assert r.verdict == "no_blocking_findings"
        assert r.findings == []

    def test_no_blocking_non_empty_findings(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        findings = [_valid_finding(evidence_paths=["src/a.py"])]
        raw = _make_raw(_valid_output_dict(verdict="no_blocking_findings", findings=findings))
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "validated"
        assert r.verdict == "no_blocking_findings"
        assert len(r.findings) == 1

    def test_non_blocking_findings_one_valid(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        findings = [_valid_finding(evidence_paths=["src/b.py"])]
        raw = _make_raw(_valid_output_dict(verdict="non_blocking_findings", findings=findings))
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "validated"
        assert r.verdict == "non_blocking_findings"

    def test_changes_required_medium_finding(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        findings = [_valid_finding(severity="medium", evidence_paths=["src/a.py"])]
        raw = _make_raw(_valid_output_dict(verdict="changes_required", findings=findings))
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "validated"
        assert r.verdict == "changes_required"

    def test_changes_required_high_finding(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        findings = [_valid_finding(severity="high", evidence_paths=["src/a.py"])]
        raw = _make_raw(_valid_output_dict(verdict="changes_required", findings=findings))
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "validated"
        assert r.verdict == "changes_required"

    def test_validated_returns_all_fields(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        raw = _make_raw(_valid_output_dict())
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.review_status == "reviewed"
        assert r.verdict is not None
        assert r.risk_level is not None
        assert r.summary != ""
        assert r.recommended_next_step != ""
        for flag in SIDE_EFFECT_FLAGS:
            assert getattr(r, flag) is False, f"{flag} should be False"
        assert r.ai_project_director_total_loop == "Partial"


# ══════════════════════════════════════════════════════════════════════
# 2. Raw output fingerprint
# ══════════════════════════════════════════════════════════════════════


class TestRawOutputFingerprint:
    def test_sha256_correct(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        raw = _make_raw(_valid_output_dict())
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        assert r.raw_output_sha256 == expected

    def test_utf8_bytes(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        d = _valid_output_dict(summary="发现一个边界问题")
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.raw_output_bytes == len(raw.encode("utf-8"))
        assert r.raw_output_bytes > len(raw)  # Chinese chars use more bytes

    def test_result_does_not_contain_raw_output(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        raw = _make_raw(_valid_output_dict())
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        dumped = r.model_dump()
        assert "raw_output_text" not in dumped
        assert "raw_output" not in dumped


# ══════════════════════════════════════════════════════════════════════
# 3. Whitespace
# ══════════════════════════════════════════════════════════════════════


class TestWhitespace:
    def test_whitespace_wrapped_json_validated(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        inner = _make_raw(_valid_output_dict())
        raw = f"  \n  {inner}  \n  "
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "validated"
        # SHA256 and bytes are for the original raw text
        assert r.raw_output_sha256 == hashlib.sha256(raw.encode("utf-8")).hexdigest()
        assert r.raw_output_bytes == len(raw.encode("utf-8"))


# ══════════════════════════════════════════════════════════════════════
# 4. Schema version
# ══════════════════════════════════════════════════════════════════════


class TestSchemaVersion:
    def test_correct_version(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        raw = _make_raw(_valid_output_dict())
        r = svc.validate_raw_review_output(
            raw_output_text=raw, review_scope_paths=SCOPE,
            review_output_schema_version=REVIEW_OUTPUT_SCHEMA_VERSION,
        )
        assert r.validation_status == "validated"

    def test_wrong_version_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        raw = _make_raw(_valid_output_dict())
        r = svc.validate_raw_review_output(
            raw_output_text=raw, review_scope_paths=SCOPE,
            review_output_schema_version="p21-c-h-review-output.v2",
        )
        assert r.validation_status == "blocked"
        assert "review_output_schema_version_mismatch" in r.blocked_reasons
        assert r.verdict is None
        assert r.findings == []


# ══════════════════════════════════════════════════════════════════════
# 5. Output size
# ══════════════════════════════════════════════════════════════════════


class TestOutputSize:
    def test_max_bytes_zero_raises(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        with pytest.raises(ValueError, match="must be positive"):
            svc.validate_raw_review_output(
                raw_output_text="{}", review_scope_paths=SCOPE, max_review_output_bytes=0,
            )

    def test_too_large_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        big = "x" * 300
        r = svc.validate_raw_review_output(
            raw_output_text=big, review_scope_paths=SCOPE, max_review_output_bytes=100,
        )
        assert r.validation_status == "blocked"
        assert "review_output_too_large" in r.blocked_reasons

    def test_exact_limit_not_blocked_by_size(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        d = _valid_output_dict()
        raw = _make_raw(d)
        limit = len(raw.encode("utf-8"))
        r = svc.validate_raw_review_output(
            raw_output_text=raw, review_scope_paths=SCOPE, max_review_output_bytes=limit,
        )
        assert "review_output_too_large" not in r.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# 6. Strict JSON
# ══════════════════════════════════════════════════════════════════════


class TestStrictJSON:
    def test_empty_string_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        r = svc.validate_raw_review_output(raw_output_text="", review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert "review_output_missing" in r.blocked_reasons

    def test_whitespace_only_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        r = svc.validate_raw_review_output(raw_output_text="   \n  ", review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert "review_output_missing" in r.blocked_reasons

    def test_markdown_fence_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        inner = _make_raw(_valid_output_dict())
        raw = f"```json\n{inner}\n```"
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert "review_output_markdown_fence_forbidden" in r.blocked_reasons

    def test_natural_language_prefix_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        inner = _make_raw(_valid_output_dict())
        raw = f"Here is my review:\n{inner}"
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert "review_output_not_strict_json" in r.blocked_reasons

    def test_natural_language_suffix_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        inner = _make_raw(_valid_output_dict())
        raw = f"{inner}\nDone."
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert "review_output_not_strict_json" in r.blocked_reasons

    def test_malformed_json_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        r = svc.validate_raw_review_output(
            raw_output_text='{"review_status": "reviewed",}', review_scope_paths=SCOPE,
        )
        assert r.validation_status == "blocked"
        assert "review_output_not_strict_json" in r.blocked_reasons

    def test_top_level_array_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        r = svc.validate_raw_review_output(raw_output_text="[]", review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert "review_output_top_level_not_object" in r.blocked_reasons

    def test_top_level_string_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        r = svc.validate_raw_review_output(
            raw_output_text='"reviewed"', review_scope_paths=SCOPE,
        )
        assert r.validation_status == "blocked"
        assert "review_output_top_level_not_object" in r.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# 7. Duplicate JSON keys
# ══════════════════════════════════════════════════════════════════════


class TestDuplicateJsonKeys:
    def test_top_level_duplicate_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        raw = '{"verdict": "no_blocking_findings", "verdict": "changes_required"}'
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert "review_output_duplicate_json_key" in r.blocked_reasons

    def test_nested_finding_duplicate_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        # Must use raw JSON string because Python dict literals deduplicate keys
        raw = '{"review_status":"reviewed","verdict":"no_blocking_findings","risk_level":"low","summary":"S","findings":[{"finding_id":"F1","severity":"low","severity":"high","title":"T","summary":"S","evidence_paths":["src/a.py"],"recommended_action":"Fix"}],"recommended_next_step":"Next"}'
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert "review_output_duplicate_json_key" in r.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# 8. Top-level exact schema
# ══════════════════════════════════════════════════════════════════════


class TestTopLevelSchema:
    @pytest.mark.parametrize("missing_key", [
        "review_status", "verdict", "risk_level", "summary", "findings", "recommended_next_step",
    ])
    def test_missing_top_level_field_blocked(self, missing_key) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        d = _valid_output_dict()
        del d[missing_key]
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert "review_output_schema_invalid" in r.blocked_reasons

    @pytest.mark.parametrize("extra_field", ["patch", "git_command", "approved_to_merge", "raw_model_output"])
    def test_extra_top_level_field_blocked(self, extra_field) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        d = _valid_output_dict()
        d[extra_field] = "value"
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert "review_output_extra_fields" in r.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# 9. Finding exact schema
# ══════════════════════════════════════════════════════════════════════


class TestFindingSchema:
    @pytest.mark.parametrize("missing_key", [
        "finding_id", "severity", "title", "summary", "evidence_paths", "recommended_action",
    ])
    def test_missing_finding_field_blocked(self, missing_key) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        f = _valid_finding(evidence_paths=["src/a.py"])
        del f[missing_key]
        d = _valid_output_dict(findings=[f])
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert "review_output_finding_invalid" in r.blocked_reasons

    @pytest.mark.parametrize("extra_field", ["patch", "line_fix", "git_command"])
    def test_extra_finding_field_blocked(self, extra_field) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        f = _valid_finding(evidence_paths=["src/a.py"])
        f[extra_field] = "value"
        d = _valid_output_dict(findings=[f])
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert "review_output_finding_extra_fields" in r.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# 10. Finding ID unique
# ══════════════════════════════════════════════════════════════════════


class TestFindingIdUnique:
    def test_duplicate_finding_id_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        findings = [
            _valid_finding(finding_id="F1", evidence_paths=["src/a.py"]),
            _valid_finding(finding_id="F1", evidence_paths=["src/b.py"]),
        ]
        d = _valid_output_dict(findings=findings)
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert "review_output_finding_id_duplicate" in r.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# 11. Review scope paths
# ══════════════════════════════════════════════════════════════════════


class TestReviewScopePaths:
    def test_empty_scope_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        raw = _make_raw(_valid_output_dict())
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=[])
        assert r.validation_status == "blocked"
        assert "review_scope_paths_invalid" in r.blocked_reasons

    def test_duplicate_scope_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        raw = _make_raw(_valid_output_dict())
        r = svc.validate_raw_review_output(
            raw_output_text=raw, review_scope_paths=["src/a.py", "src/a.py"],
        )
        assert r.validation_status == "blocked"
        assert "review_scope_paths_invalid" in r.blocked_reasons

    def test_empty_string_in_scope_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        raw = _make_raw(_valid_output_dict())
        r = svc.validate_raw_review_output(
            raw_output_text=raw, review_scope_paths=["src/a.py", ""],
        )
        assert r.validation_status == "blocked"
        assert "review_scope_paths_invalid" in r.blocked_reasons

    def test_non_string_in_scope_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        raw = _make_raw(_valid_output_dict())
        r = svc.validate_raw_review_output(
            raw_output_text=raw, review_scope_paths=["src/a.py", 123],
        )
        assert r.validation_status == "blocked"
        assert "review_scope_paths_invalid" in r.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# 12. Evidence paths
# ══════════════════════════════════════════════════════════════════════


class TestEvidencePaths:
    def test_empty_evidence_paths_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        f = _valid_finding(evidence_paths=[])
        d = _valid_output_dict(findings=[f])
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        # Empty evidence_paths is caught by Pydantic min_length=1 (schema_invalid)
        # or by the service's _validate_findings_schema (evidence_paths_missing)
        assert any(
            reason in r.blocked_reasons
            for reason in ["review_output_evidence_paths_missing", "review_output_schema_invalid", "review_output_finding_invalid"]
        )

    def test_out_of_scope_evidence_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        f = _valid_finding(evidence_paths=["src/c.py"])
        d = _valid_output_dict(findings=[f])
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert "review_output_evidence_path_out_of_scope" in r.blocked_reasons

    def test_duplicate_evidence_path_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        f = _valid_finding(evidence_paths=["src/a.py", "src/a.py"])
        d = _valid_output_dict(findings=[f])
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert "review_output_evidence_path_duplicate" in r.blocked_reasons

    def test_multiple_valid_in_scope(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        f = _valid_finding(evidence_paths=["src/a.py", "src/b.py"])
        d = _valid_output_dict(findings=[f])
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "validated"


# ══════════════════════════════════════════════════════════════════════
# 13. Verdict semantics
# ══════════════════════════════════════════════════════════════════════


class TestVerdictSemantics:
    def test_non_blocking_empty_findings_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        raw = _make_raw(_valid_output_dict(verdict="non_blocking_findings", findings=[]))
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert "review_output_findings_required_for_verdict" in r.blocked_reasons

    def test_changes_required_empty_findings_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        raw = _make_raw(_valid_output_dict(verdict="changes_required", findings=[]))
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert "review_output_findings_required_for_verdict" in r.blocked_reasons

    def test_changes_required_only_low_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        f = _valid_finding(severity="low", evidence_paths=["src/a.py"])
        raw = _make_raw(_valid_output_dict(verdict="changes_required", findings=[f]))
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert "review_output_changes_required_severity_missing" in r.blocked_reasons

    def test_changes_required_medium_validated(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        f = _valid_finding(severity="medium", evidence_paths=["src/a.py"])
        raw = _make_raw(_valid_output_dict(verdict="changes_required", findings=[f]))
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "validated"

    def test_changes_required_high_validated(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        f = _valid_finding(severity="high", evidence_paths=["src/a.py"])
        raw = _make_raw(_valid_output_dict(verdict="changes_required", findings=[f]))
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "validated"

    def test_no_risk_level_coupling(self) -> None:
        """H-B1 must not enforce risk_level coupling beyond H-A contract."""
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        f = _valid_finding(severity="high", evidence_paths=["src/a.py"])
        raw = _make_raw(_valid_output_dict(
            verdict="changes_required", risk_level="low", findings=[f],
        ))
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "validated"


# ══════════════════════════════════════════════════════════════════════
# 14. Blocked trusted data clearing
# ══════════════════════════════════════════════════════════════════════


class TestBlockedTrustedDataClearing:
    def test_malformed_json_clears_trusted_data(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        r = svc.validate_raw_review_output(
            raw_output_text='{"bad": "json",}', review_scope_paths=SCOPE,
        )
        assert r.validation_status == "blocked"
        assert r.review_status is None
        assert r.verdict is None
        assert r.risk_level is None
        assert r.summary == ""
        assert r.findings == []
        assert r.recommended_next_step == ""

    def test_evidence_out_of_scope_clears_trusted_data(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        f = _valid_finding(evidence_paths=["src/evil.py"])
        d = _valid_output_dict(findings=[f])
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert r.verdict is None
        assert r.findings == []

    def test_verdict_semantic_violation_clears_trusted_data(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        raw = _make_raw(_valid_output_dict(verdict="non_blocking_findings", findings=[]))
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert r.verdict is None
        assert r.findings == []


# ══════════════════════════════════════════════════════════════════════
# 15. Validation flags
# ══════════════════════════════════════════════════════════════════════


class TestValidationFlags:
    def test_fully_validated(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        raw = _make_raw(_valid_output_dict())
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.strict_json_valid is True
        assert r.schema_valid is True
        assert r.semantics_valid is True
        assert r.evidence_scope_valid is True

    def test_malformed_json_flags(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        r = svc.validate_raw_review_output(
            raw_output_text='not json', review_scope_paths=SCOPE,
        )
        assert r.strict_json_valid is False
        assert r.schema_valid is False
        assert r.semantics_valid is False
        assert r.evidence_scope_valid is False

    def test_schema_valid_semantic_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        raw = _make_raw(_valid_output_dict(verdict="non_blocking_findings", findings=[]))
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.strict_json_valid is True
        assert r.schema_valid is True
        assert r.semantics_valid is False

    def test_schema_valid_evidence_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        f = _valid_finding(evidence_paths=["src/evil.py"])
        d = _valid_output_dict(findings=[f])
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.strict_json_valid is True
        assert r.schema_valid is True
        assert r.evidence_scope_valid is False


# ══════════════════════════════════════════════════════════════════════
# 16. Blocked reason dedupe / order
# ══════════════════════════════════════════════════════════════════════


class TestBlockedReasonDedupe:
    def test_duplicate_reason_deduped(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        # Two findings with duplicate evidence paths trigger same reason
        f1 = _valid_finding(finding_id="F1", evidence_paths=["src/a.py", "src/a.py"])
        f2 = _valid_finding(finding_id="F2", evidence_paths=["src/b.py", "src/b.py"])
        d = _valid_output_dict(findings=[f1, f2])
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        count = r.blocked_reasons.count("review_output_evidence_path_duplicate")
        assert count == 1

    def test_different_reasons_preserve_order(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        # Empty string triggers review_output_missing, invalid scope triggers review_scope_paths_invalid
        r = svc.validate_raw_review_output(raw_output_text="", review_scope_paths=[])
        assert r.blocked_reasons[0] == "review_output_missing"
        assert r.blocked_reasons[1] == "review_scope_paths_invalid"


# ══════════════════════════════════════════════════════════════════════
# 17. Domain constraints
# ══════════════════════════════════════════════════════════════════════


class TestDomainConstraints:
    def test_review_status_not_reviewed_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        d = _valid_output_dict(review_status="pending")
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert "review_output_schema_invalid" in r.blocked_reasons

    def test_invalid_verdict_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        d = _valid_output_dict(verdict="invalid_verdict")
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"

    def test_invalid_risk_level_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        d = _valid_output_dict(risk_level="critical")
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"

    def test_invalid_finding_severity_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        f = _valid_finding(severity="critical", evidence_paths=["src/a.py"])
        d = _valid_output_dict(findings=[f])
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"

    def test_empty_finding_id_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        f = _valid_finding(finding_id="", evidence_paths=["src/a.py"])
        d = _valid_output_dict(findings=[f])
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"

    def test_empty_title_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        f = _valid_finding(title="", evidence_paths=["src/a.py"])
        d = _valid_output_dict(findings=[f])
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"

    def test_empty_summary_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        f = _valid_finding(summary="", evidence_paths=["src/a.py"])
        d = _valid_output_dict(findings=[f])
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"

    def test_empty_recommended_action_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        f = _valid_finding(recommended_action="", evidence_paths=["src/a.py"])
        d = _valid_output_dict(findings=[f])
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"

    def test_empty_top_level_summary_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        d = _valid_output_dict(summary="")
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"

    def test_empty_recommended_next_step_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        d = _valid_output_dict(recommended_next_step="")
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"

    def test_finding_id_too_long_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        f = _valid_finding(finding_id="x" * 81, evidence_paths=["src/a.py"])
        d = _valid_output_dict(findings=[f])
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"

    def test_title_too_long_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        f = _valid_finding(title="x" * 201, evidence_paths=["src/a.py"])
        d = _valid_output_dict(findings=[f])
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"

    def test_finding_summary_too_long_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        f = _valid_finding(summary="x" * 1001, evidence_paths=["src/a.py"])
        d = _valid_output_dict(findings=[f])
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"

    def test_recommended_action_too_long_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        f = _valid_finding(recommended_action="x" * 501, evidence_paths=["src/a.py"])
        d = _valid_output_dict(findings=[f])
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"

    def test_top_level_summary_too_long_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        d = _valid_output_dict(summary="x" * 2001)
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"

    def test_recommended_next_step_too_long_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        d = _valid_output_dict(recommended_next_step="x" * 1001)
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"

    def test_too_many_findings_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        findings = [_valid_finding(finding_id=f"F{i}", evidence_paths=["src/a.py"]) for i in range(21)]
        d = _valid_output_dict(findings=findings)
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert "review_output_finding_invalid" in r.blocked_reasons

    def test_too_many_evidence_paths_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        paths = [f"src/{chr(97+i)}.py" for i in range(13)]
        f = _valid_finding(evidence_paths=paths)
        d = _valid_output_dict(findings=[f])
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=paths[:12] + ["src/m.py"])
        assert r.validation_status == "blocked"

    def test_findings_not_list_blocked(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        d = _valid_output_dict()
        d["findings"] = "not a list"
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert "review_output_finding_invalid" in r.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# 18. No auto-fix
# ══════════════════════════════════════════════════════════════════════


class TestNoAutoFix:
    def test_markdown_fence_not_auto_removed(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        inner = _make_raw(_valid_output_dict())
        raw = f"```json\n{inner}\n```"
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"

    def test_extra_fields_not_auto_removed(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        d = _valid_output_dict()
        d["patch"] = "diff --git a/..."
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"
        assert "review_output_extra_fields" in r.blocked_reasons

    def test_out_of_scope_evidence_not_filtered(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        f = _valid_finding(evidence_paths=["src/evil.py"])
        d = _valid_output_dict(findings=[f])
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"

    def test_duplicate_finding_not_deduped(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        findings = [
            _valid_finding(finding_id="F1", evidence_paths=["src/a.py"]),
            _valid_finding(finding_id="F1", evidence_paths=["src/b.py"]),
        ]
        d = _valid_output_dict(findings=findings)
        raw = _make_raw(d)
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "blocked"


# ══════════════════════════════════════════════════════════════════════
# 19. Domain side-effect validator
# ══════════════════════════════════════════════════════════════════════


class TestDomainSideEffectValidator:
    @pytest.mark.parametrize("field_name", SIDE_EFFECT_FLAGS)
    def test_rejects_true_flag(self, field_name: str) -> None:
        with pytest.raises(ValidationError, match="may not execute or write"):
            ProjectDirectorSandboxCandidateDiffReviewOutputValidationResult(
                validation_status="validated",
                review_output_schema_version="v1",
                raw_output_sha256="a" * 64,
                raw_output_bytes=100,
                strict_json_valid=True,
                schema_valid=True,
                semantics_valid=True,
                evidence_scope_valid=True,
                **{field_name: True},
            )


# ══════════════════════════════════════════════════════════════════════
# 20. Pure memory, no file I/O
# ══════════════════════════════════════════════════════════════════════


class TestPureMemoryNoExecution:
    def test_validated_with_path_io_blocked(self, monkeypatch) -> None:
        from pathlib import Path
        monkeypatch.setattr(Path, "read_text", lambda self, *a, **kw: (_ for _ in ()).throw(AssertionError("must not read!")))
        monkeypatch.setattr(Path, "write_text", lambda self, *a, **kw: (_ for _ in ()).throw(AssertionError("must not write!")))
        svc = ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        raw = _make_raw(_valid_output_dict())
        r = svc.validate_raw_review_output(raw_output_text=raw, review_scope_paths=SCOPE)
        assert r.validation_status == "validated"
        for flag in SIDE_EFFECT_FLAGS:
            assert getattr(r, flag) is False
