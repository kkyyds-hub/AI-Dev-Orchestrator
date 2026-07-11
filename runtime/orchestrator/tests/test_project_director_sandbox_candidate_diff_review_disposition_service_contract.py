"""Contract tests for P21-D-B automated review disposition gate."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_sandbox_candidate_diff_review_disposition import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionResult,
)
from app.services.project_director_sandbox_candidate_diff_readonly_review_execution_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_service import (
    DEFERRED_TRIGGER_KINDS,
    EVALUATED_TRIGGER_KINDS,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL,
    REVIEW_DISPOSITION_SCHEMA_VERSION,
    ProjectDirectorSandboxCandidateDiffReviewDispositionService,
)
from app.services.project_director_sandbox_candidate_diff_review_execution_preflight_service import (
    REVIEW_OUTPUT_SCHEMA_VERSION,
)

# ── Constants ───────────────────────────────────────────────────────

SESSION_ID = uuid4()
TASK_ID = uuid4()
PROJECT_ID = uuid4()
SOURCE_REVIEW_MSG_ID = uuid4()
PREFLIGHT_MSG_ID = uuid4()
DIFF_MSG_ID = uuid4()

_TRUE_HEX_SHA256 = hashlib.sha256(b"diff content").hexdigest()
_PROMPT_SHA256 = hashlib.sha256(b"prompt content").hexdigest()
_RAW_OUTPUT_SHA256 = hashlib.sha256(b"raw output").hexdigest()

_SOURCE_REVIEW_FALSE_FLAGS = [
    "main_project_file_written",
    "sandbox_file_written",
    "manifest_file_written",
    "diff_file_written",
    "patch_applied",
    "git_write_performed",
    "worktree_created",
    "worker_started",
    "task_created",
    "run_created",
]


# ── Spy repositories ───────────────────────────────────────────────


class SpyMessageRepo:
    def __init__(
        self, messages: dict[Any, ProjectDirectorMessage] | None = None
    ) -> None:
        self._messages = messages or {}
        self.create_calls: list[ProjectDirectorMessage] = []
        self.commit_calls = 0

    @contextmanager
    def sqlite_immediate_transaction(self):
        yield
        self.commit()

    def get_by_id(self, mid):
        return self._messages.get(mid)

    def get_next_sequence_no(self, *, session_id):
        return 100

    def create(self, message):
        self.create_calls.append(message)
        self._messages[message.id] = message
        return message

    def commit(self):
        self.commit_calls += 1

    def list_by_session_id(
        self, *, session_id: UUID, limit: int = 100, before_message_id: UUID | None = None
    ) -> tuple[list[ProjectDirectorMessage], bool]:
        msgs = [m for m in self._messages.values() if m.session_id == session_id]
        msgs.sort(key=lambda m: m.sequence_no, reverse=True)
        if before_message_id is not None:
            idx = next((i for i, m in enumerate(msgs) if m.id == before_message_id), len(msgs))
            msgs = msgs[idx:]
        return msgs[:limit], len(msgs) > limit


class FakeSessionRepo:
    def __init__(self, session_exists: bool = True) -> None:
        self._session_exists = session_exists

    def get_by_id(self, sid):
        if self._session_exists and sid == SESSION_ID:
            return type("S", (), {"project_id": PROJECT_ID})()
        return None


# ── Builder helpers ─────────────────────────────────────────────────


def _valid_review_action(
    *,
    verdict="no_blocking_findings",
    risk_level="low",
    findings=None,
    **overrides,
):
    action = {
        "type": P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
        "session_id": str(SESSION_ID),
        "source_task_id": str(TASK_ID),
        "source_preflight_message_id": str(PREFLIGHT_MSG_ID),
        "source_diff_message_id": str(DIFF_MSG_ID),
        "requested_reviewer_executor": "codex",
        "source_diff_sha256": _TRUE_HEX_SHA256,
        "review_prompt_sha256": _PROMPT_SHA256,
        "review_scope_paths": ["src/example.py"],
        "review_output_schema_version": REVIEW_OUTPUT_SCHEMA_VERSION,
        "adapter_status": "validated_output",
        "output_validation_status": "validated",
        "raw_output_sha256": _RAW_OUTPUT_SHA256,
        "strict_json_valid": True,
        "schema_valid": True,
        "semantics_valid": True,
        "evidence_scope_valid": True,
        "review_status": "reviewed",
        "verdict": verdict,
        "risk_level": risk_level,
        "summary": "Review completed.",
        "findings": findings if findings is not None else [],
        "recommended_next_step": "Proceed.",
        "ai_project_director_total_loop": "Partial",
    }
    for flag in _SOURCE_REVIEW_FALSE_FLAGS:
        action[flag] = False
    action.update(overrides)
    return action


def _make_source_review_message(
    action=None,
    *,
    session_id=SESSION_ID,
    task_id=TASK_ID,
    source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
):
    return ProjectDirectorMessage(
        id=SOURCE_REVIEW_MSG_ID,
        session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="Readonly review executed.",
        sequence_no=50,
        intent="sandbox_candidate_diff_readonly_review_execution",
        related_project_id=PROJECT_ID,
        related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=source_detail,
        suggested_actions=[action or _valid_review_action()],
    )


def _build_service(
    *,
    messages=None,
    session_exists=True,
):
    msg_repo = SpyMessageRepo(messages or {})
    svc = ProjectDirectorSandboxCandidateDiffReviewDispositionService(
        session_repository=FakeSessionRepo(session_exists),
        message_repository=msg_repo,
    )
    return svc, msg_repo


def _call_service(
    svc,
    *,
    session_id=SESSION_ID,
    task_id=TASK_ID,
    message_id=SOURCE_REVIEW_MSG_ID,
):
    return svc.compute_candidate_diff_review_disposition(
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=message_id,
    )


# ══════════════════════════════════════════════════════════════════════
# A. Domain safety contract
# ══════════════════════════════════════════════════════════════════════


class TestDomainSafetyContract:
    def test_computed_must_have_disposition_type(self) -> None:
        msg = _make_source_review_message()
        svc, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        result = _call_service(svc)
        assert result.result.disposition_status == "computed"
        assert result.result.disposition_type is not None

    def test_computed_must_have_valid_64char_fingerprint(self) -> None:
        msg = _make_source_review_message()
        svc, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        result = _call_service(svc)
        fp = result.result.review_result_fingerprint
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)

    def test_computed_must_have_disposition_reason(self) -> None:
        msg = _make_source_review_message()
        svc, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        result = _call_service(svc)
        assert result.result.disposition_reason != ""

    def test_computed_must_not_have_blocked_reasons(self) -> None:
        msg = _make_source_review_message()
        svc, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        result = _call_service(svc)
        assert result.result.blocked_reasons == []

    def test_blocked_must_not_contain_disposition_type(self) -> None:
        svc, _ = _build_service(messages={})
        result = _call_service(svc)
        assert result.result.disposition_status == "blocked"
        assert result.result.disposition_type is None

    def test_blocked_must_not_contain_review_result_fingerprint(self) -> None:
        svc, _ = _build_service(messages={})
        result = _call_service(svc)
        assert result.result.review_result_fingerprint == ""

    @pytest.mark.parametrize(
        "flag",
        [
            "continuation_started",
            "rework_started",
            "human_escalation_package_created",
            "human_decision_recorded",
            "main_project_file_written",
            "sandbox_file_written",
            "manifest_file_written",
            "diff_file_written",
            "patch_applied",
            "git_write_performed",
            "worktree_created",
            "worker_started",
            "task_created",
            "run_created",
            "gate_allows_write",
        ],
    )
    def test_forbidden_side_effect_flag_rejected(self, flag: str) -> None:
        with pytest.raises(ValueError, match="review disposition may not execute"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionResult(
                disposition_status="computed",
                disposition_type="AUTO_CONTINUE",
                source_review_message_id=uuid4(),
                review_result_fingerprint="a" * 64,
                disposition_reason="test",
                **{flag: True},
            )

    def test_total_loop_can_only_be_partial(self) -> None:
        msg = _make_source_review_message()
        svc, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        result = _call_service(svc)
        assert result.result.ai_project_director_total_loop == "Partial"


# ══════════════════════════════════════════════════════════════════════
# B. AUTO_CONTINUE — no blocking findings
# ══════════════════════════════════════════════════════════════════════


class TestAutoContinueNoBlocking:
    def test_no_blocking_findings(self) -> None:
        action = _valid_review_action(
            verdict="no_blocking_findings", risk_level="low"
        )
        msg = _make_source_review_message(action=action)
        svc, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        result = _call_service(svc)
        assert result.result.disposition_status == "computed"
        assert result.result.disposition_type == "AUTO_CONTINUE"
        assert result.result.disposition_reason == "review_has_no_blocking_findings"
        assert result.result.escalation_triggers == []


# ══════════════════════════════════════════════════════════════════════
# C. AUTO_CONTINUE — non-blocking findings
# ══════════════════════════════════════════════════════════════════════


class TestAutoContinueNonBlocking:
    def test_non_blocking_findings_low_severity(self) -> None:
        findings = [{"finding_id": "F1", "severity": "low", "title": "Minor"}]
        action = _valid_review_action(
            verdict="non_blocking_findings",
            risk_level="medium",
            findings=findings,
        )
        msg = _make_source_review_message(action=action)
        svc, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        result = _call_service(svc)
        assert result.result.disposition_type == "AUTO_CONTINUE"
        assert (
            result.result.disposition_reason
            == "review_has_only_non_blocking_findings"
        )
        assert result.result.escalation_triggers == []


# ══════════════════════════════════════════════════════════════════════
# D. AUTO_REWORK
# ══════════════════════════════════════════════════════════════════════


class TestAutoRework:
    def test_changes_required_within_boundary(self) -> None:
        action = _valid_review_action(
            verdict="changes_required", risk_level="medium"
        )
        msg = _make_source_review_message(action=action)
        svc, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        result = _call_service(svc)
        assert result.result.disposition_type == "AUTO_REWORK"
        assert (
            result.result.disposition_reason
            == "review_changes_required_within_automatic_rework_boundary"
        )
        assert result.result.escalation_triggers == []


# ══════════════════════════════════════════════════════════════════════
# E. ESCALATE_TO_HUMAN — high risk
# ══════════════════════════════════════════════════════════════════════


class TestEscalateHighRisk:
    def test_top_level_high_risk(self) -> None:
        action = _valid_review_action(
            verdict="no_blocking_findings", risk_level="high"
        )
        msg = _make_source_review_message(action=action)
        svc, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        result = _call_service(svc)
        assert result.result.disposition_type == "ESCALATE_TO_HUMAN"
        assert result.result.escalation_triggers == ["high_review_risk"]


# ══════════════════════════════════════════════════════════════════════
# F. ESCALATE_TO_HUMAN — high severity finding
# ══════════════════════════════════════════════════════════════════════


class TestEscalateHighSeverityFinding:
    def test_high_severity_finding_triggers_escalation(self) -> None:
        findings = [{"finding_id": "F1", "severity": "high", "title": "Critical"}]
        action = _valid_review_action(
            verdict="no_blocking_findings",
            risk_level="low",
            findings=findings,
        )
        msg = _make_source_review_message(action=action)
        svc, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        result = _call_service(svc)
        assert result.result.disposition_type == "ESCALATE_TO_HUMAN"
        assert result.result.escalation_triggers == ["high_review_risk"]


# ══════════════════════════════════════════════════════════════════════
# G. Precedence: high risk overrides changes_required
# ══════════════════════════════════════════════════════════════════════


class TestPrecedence:
    def test_high_risk_overrides_changes_required(self) -> None:
        action = _valid_review_action(
            verdict="changes_required", risk_level="high"
        )
        msg = _make_source_review_message(action=action)
        svc, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        result = _call_service(svc)
        assert result.result.disposition_type == "ESCALATE_TO_HUMAN"
        assert result.result.escalation_triggers == ["high_review_risk"]


# ══════════════════════════════════════════════════════════════════════
# H. Evaluated / deferred trigger contract
# ══════════════════════════════════════════════════════════════════════


class TestTriggerKinds:
    def test_evaluated_trigger_kinds(self) -> None:
        msg = _make_source_review_message()
        svc, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        result = _call_service(svc)
        assert result.result.evaluated_trigger_kinds == ["high_review_risk"]

    def test_deferred_trigger_kinds(self) -> None:
        msg = _make_source_review_message()
        svc, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        result = _call_service(svc)
        assert result.result.deferred_trigger_kinds == [
            "confirmed_scope_or_plan_expansion",
            "protected_surface_change",
            "bounded_rework_budget_exhausted",
            "repeated_non_convergence",
            "trusted_reviewer_conflict",
            "human_controlled_stage_or_milestone_checkpoint",
            "protected_future_transition",
            "explicit_governance_policy_escalation",
        ]

    def test_deferred_triggers_not_in_evaluated(self) -> None:
        msg = _make_source_review_message()
        svc, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        result = _call_service(svc)
        for dt in result.result.deferred_trigger_kinds:
            assert dt not in result.result.evaluated_trigger_kinds

    def test_deferred_triggers_present_on_blocked(self) -> None:
        svc, _ = _build_service(messages={})
        result = _call_service(svc)
        assert result.result.disposition_status == "blocked"
        assert result.result.deferred_trigger_kinds == DEFERRED_TRIGGER_KINDS


# ══════════════════════════════════════════════════════════════════════
# I. Fingerprint determinism
# ══════════════════════════════════════════════════════════════════════


class TestFingerprintDeterminism:
    def test_same_evidence_same_fingerprint(self) -> None:
        msg = _make_source_review_message()
        svc, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        r1 = _call_service(svc)
        svc2, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        r2 = _call_service(svc2)
        assert r1.result.review_result_fingerprint == r2.result.review_result_fingerprint

    def test_different_disposition_ids_same_fingerprint(self) -> None:
        msg = _make_source_review_message()
        svc, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        r1 = _call_service(svc)
        svc2, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        r2 = _call_service(svc2)
        assert r1.result.review_result_fingerprint == r2.result.review_result_fingerprint

    def test_changed_diff_sha256_changes_fingerprint(self) -> None:
        action1 = _valid_review_action()
        msg1 = _make_source_review_message(action=action1)
        svc1, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg1})
        r1 = _call_service(svc1)

        action2 = _valid_review_action(
            source_diff_sha256=hashlib.sha256(b"other").hexdigest()
        )
        msg2 = _make_source_review_message(action=action2)
        svc2, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg2})
        r2 = _call_service(svc2)
        assert r1.result.review_result_fingerprint != r2.result.review_result_fingerprint

    def test_changed_verdict_changes_fingerprint(self) -> None:
        action1 = _valid_review_action(verdict="no_blocking_findings")
        msg1 = _make_source_review_message(action=action1)
        svc1, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg1})
        r1 = _call_service(svc1)

        action2 = _valid_review_action(verdict="changes_required")
        msg2 = _make_source_review_message(action=action2)
        svc2, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg2})
        r2 = _call_service(svc2)
        assert r1.result.review_result_fingerprint != r2.result.review_result_fingerprint

    def test_findings_key_order_canonicalized(self) -> None:
        f1 = {"severity": "low", "title": "X", "finding_id": "F1"}
        f2 = {"finding_id": "F1", "title": "X", "severity": "low"}
        action1 = _valid_review_action(findings=[f1])
        action2 = _valid_review_action(findings=[f2])
        msg1 = _make_source_review_message(action=action1)
        msg2 = _make_source_review_message(action=action2)
        svc1, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg1})
        svc2, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg2})
        r1 = _call_service(svc1)
        r2 = _call_service(svc2)
        assert r1.result.review_result_fingerprint == r2.result.review_result_fingerprint

    def test_scope_order_change_changes_fingerprint(self) -> None:
        action1 = _valid_review_action(
            review_scope_paths=["src/a.py", "src/b.py"]
        )
        msg1 = _make_source_review_message(action=action1)
        svc1, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg1})
        r1 = _call_service(svc1)

        action2 = _valid_review_action(
            review_scope_paths=["src/b.py", "src/a.py"]
        )
        msg2 = _make_source_review_message(action=action2)
        svc2, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg2})
        r2 = _call_service(svc2)
        assert r1.result.review_result_fingerprint != r2.result.review_result_fingerprint


# ══════════════════════════════════════════════════════════════════════
# J. Adversarial blocked cases
# ══════════════════════════════════════════════════════════════════════


class TestAdversarialBlocked:
    def _assert_blocked(
        self,
        svc,
        msg_repo,
        *,
        reason,
    ):
        result = _call_service(svc)
        assert result.result.disposition_status == "blocked"
        assert reason in result.result.blocked_reasons
        assert result.message is None
        assert msg_repo.create_calls == []

    def test_session_missing(self) -> None:
        svc, msg_repo = _build_service(
            messages={SOURCE_REVIEW_MSG_ID: _make_source_review_message()},
            session_exists=False,
        )
        self._assert_blocked(svc, msg_repo, reason="session_missing")

    def test_source_review_message_missing(self) -> None:
        svc, msg_repo = _build_service(messages={})
        self._assert_blocked(svc, msg_repo, reason="source_review_message_missing")

    def test_message_session_mismatch(self) -> None:
        msg = _make_source_review_message(session_id=uuid4())
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(
            svc, msg_repo, reason="source_review_message_session_mismatch"
        )

    def test_message_task_mismatch(self) -> None:
        msg = _make_source_review_message(task_id=uuid4())
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(
            svc, msg_repo, reason="source_review_message_task_mismatch"
        )

    def test_wrong_source_detail(self) -> None:
        msg = _make_source_review_message(source_detail="wrong_detail")
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(
            svc,
            msg_repo,
            reason="source_message_is_not_p21_c_readonly_review_execution",
        )

    def test_missing_action_type(self) -> None:
        msg = _make_source_review_message(action={"type": "wrong_type"})
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(
            svc,
            msg_repo,
            reason="p21_c_readonly_review_execution_record_missing",
        )

    def test_empty_suggested_actions(self) -> None:
        msg = ProjectDirectorMessage(
            id=SOURCE_REVIEW_MSG_ID,
            session_id=SESSION_ID,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content="review",
            sequence_no=50,
            intent="sandbox_candidate_diff_readonly_review_execution",
            related_project_id=PROJECT_ID,
            related_task_id=TASK_ID,
            source=ProjectDirectorMessageSource.SYSTEM,
            source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
            suggested_actions=[],
        )
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(
            svc,
            msg_repo,
            reason="p21_c_readonly_review_execution_record_missing",
        )

    def test_action_session_mismatch(self) -> None:
        action = _valid_review_action(session_id=str(uuid4()))
        msg = _make_source_review_message(action=action)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(
            svc, msg_repo, reason="source_review_action_session_mismatch"
        )

    def test_action_task_mismatch(self) -> None:
        action = _valid_review_action(source_task_id=str(uuid4()))
        msg = _make_source_review_message(action=action)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(
            svc, msg_repo, reason="source_review_action_task_mismatch"
        )

    def test_invalid_source_preflight_message_id(self) -> None:
        action = _valid_review_action(source_preflight_message_id="not-a-uuid")
        msg = _make_source_review_message(action=action)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(svc, msg_repo, reason="source_review_binding_invalid")

    def test_invalid_source_diff_message_id(self) -> None:
        action = _valid_review_action(source_diff_message_id="")
        msg = _make_source_review_message(action=action)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(svc, msg_repo, reason="source_review_binding_invalid")

    def test_invalid_requested_reviewer_executor(self) -> None:
        action = _valid_review_action(requested_reviewer_executor="invalid")
        msg = _make_source_review_message(action=action)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(
            svc, msg_repo, reason="requested_reviewer_executor_invalid"
        )

    def test_invalid_source_diff_sha256(self) -> None:
        action = _valid_review_action(source_diff_sha256="not_hex")
        msg = _make_source_review_message(action=action)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(svc, msg_repo, reason="source_diff_sha256_invalid")

    def test_invalid_review_prompt_sha256(self) -> None:
        action = _valid_review_action(review_prompt_sha256="bad")
        msg = _make_source_review_message(action=action)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(
            svc, msg_repo, reason="review_prompt_sha256_invalid"
        )

    def test_empty_review_scope_paths(self) -> None:
        action = _valid_review_action(review_scope_paths=[])
        msg = _make_source_review_message(action=action)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(svc, msg_repo, reason="review_scope_paths_invalid")

    def test_duplicate_review_scope_paths(self) -> None:
        action = _valid_review_action(
            review_scope_paths=["src/a.py", "src/a.py"]
        )
        msg = _make_source_review_message(action=action)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(svc, msg_repo, reason="review_scope_paths_invalid")

    def test_non_string_review_scope_paths(self) -> None:
        action = _valid_review_action(review_scope_paths=[123])
        msg = _make_source_review_message(action=action)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(svc, msg_repo, reason="review_scope_paths_invalid")

    def test_wrong_review_output_schema_version(self) -> None:
        action = _valid_review_action(review_output_schema_version="wrong")
        msg = _make_source_review_message(action=action)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(
            svc, msg_repo, reason="review_output_schema_version_mismatch"
        )

    @pytest.mark.parametrize(
        "override",
        [
            {"adapter_status": "blocked"},
            {"output_validation_status": "invalid"},
            {"strict_json_valid": False},
            {"schema_valid": False},
            {"semantics_valid": False},
            {"evidence_scope_valid": False},
            {"review_status": "pending"},
            {"raw_output_sha256": "not_sha"},
        ],
    )
    def test_source_review_not_validated(self, override: dict) -> None:
        action = _valid_review_action(**override)
        msg = _make_source_review_message(action=action)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(svc, msg_repo, reason="source_review_not_validated")

    def test_invalid_verdict(self) -> None:
        action = _valid_review_action(verdict="invalid_verdict")
        msg = _make_source_review_message(action=action)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(
            svc, msg_repo, reason="source_review_verdict_invalid"
        )

    def test_invalid_risk_level(self) -> None:
        action = _valid_review_action(risk_level="critical")
        msg = _make_source_review_message(action=action)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(
            svc, msg_repo, reason="source_review_risk_level_invalid"
        )

    def test_findings_not_list(self) -> None:
        action = _valid_review_action(findings="not_a_list")
        msg = _make_source_review_message(action=action)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(
            svc, msg_repo, reason="source_review_findings_invalid"
        )

    def test_finding_severity_invalid(self) -> None:
        findings = [{"severity": "critical"}]
        action = _valid_review_action(findings=findings)
        msg = _make_source_review_message(action=action)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(
            svc, msg_repo, reason="source_review_findings_invalid"
        )

    @pytest.mark.parametrize("flag", _SOURCE_REVIEW_FALSE_FLAGS)
    def test_no_write_flag_true(self, flag: str) -> None:
        action = _valid_review_action(**{flag: True})
        msg = _make_source_review_message(action=action)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(
            svc, msg_repo, reason="source_review_write_boundary_violated"
        )

    def test_total_loop_not_partial(self) -> None:
        action = _valid_review_action(ai_project_director_total_loop="Pass")
        msg = _make_source_review_message(action=action)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        self._assert_blocked(
            svc, msg_repo, reason="source_review_write_boundary_violated"
        )


# ══════════════════════════════════════════════════════════════════════
# K. Blocked reason stable ordering and dedup
# ══════════════════════════════════════════════════════════════════════


class TestBlockedReasonOrdering:
    def test_multiple_errors_stable_order_no_dup(self) -> None:
        action = _valid_review_action(
            verdict="invalid_verdict",
            risk_level="critical",
            session_id=str(uuid4()),
            source_task_id=str(uuid4()),
        )
        msg = _make_source_review_message(action=action)
        svc, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        result = _call_service(svc)
        reasons = result.result.blocked_reasons
        assert len(reasons) == len(set(reasons))
        assert reasons == sorted(set(reasons), key=reasons.index)

    def test_deterministic_order_across_runs(self) -> None:
        action = _valid_review_action(
            verdict="invalid_verdict",
            risk_level="critical",
        )
        msg = _make_source_review_message(action=action)
        svc1, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        r1 = _call_service(svc1)
        svc2, _ = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        r2 = _call_service(svc2)
        assert r1.result.blocked_reasons == r2.result.blocked_reasons


# ══════════════════════════════════════════════════════════════════════
# L. Append-only persistence
# ══════════════════════════════════════════════════════════════════════


class TestAppendOnlyPersistence:
    def _assert_persisted(self, result, msg_repo) -> dict[str, Any]:
        assert result.message is not None
        assert len(msg_repo.create_calls) == 1
        assert msg_repo.commit_calls == 1
        msg = msg_repo.create_calls[0]
        assert msg.source_detail == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL
        assert msg.requires_confirmation is False
        assert msg.source == ProjectDirectorMessageSource.SYSTEM
        assert msg.related_task_id == TASK_ID
        assert msg.session_id == SESSION_ID
        action = msg.suggested_actions[0]
        assert action["type"] == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_ACTION_TYPE
        assert action["schema_version"] == REVIEW_DISPOSITION_SCHEMA_VERSION
        assert action["actor"] == "system"
        assert action["client_request_id"] is None
        return action

    def test_auto_continue_persisted(self) -> None:
        action_in = _valid_review_action(
            verdict="no_blocking_findings", risk_level="low"
        )
        msg = _make_source_review_message(action=action_in)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        result = _call_service(svc)
        action = self._assert_persisted(result, msg_repo)
        assert action["disposition_type"] == "AUTO_CONTINUE"
        assert action["disposition_status"] == "computed"
        assert action["session_id"] == str(SESSION_ID)
        assert action["source_task_id"] == str(TASK_ID)
        assert action["source_review_message_id"] == str(SOURCE_REVIEW_MSG_ID)
        assert action["source_preflight_message_id"] == str(PREFLIGHT_MSG_ID)
        assert action["source_diff_message_id"] == str(DIFF_MSG_ID)
        assert action["requested_reviewer_executor"] == "codex"
        assert action["source_diff_sha256"] == _TRUE_HEX_SHA256
        assert action["review_prompt_sha256"] == _PROMPT_SHA256
        assert action["review_scope_paths"] == ["src/example.py"]
        assert action["review_output_schema_version"] == REVIEW_OUTPUT_SCHEMA_VERSION
        assert action["source_review_verdict"] == "no_blocking_findings"
        assert action["source_review_risk_level"] == "low"
        assert action["evaluated_trigger_kinds"] == EVALUATED_TRIGGER_KINDS
        assert action["deferred_trigger_kinds"] == list(DEFERRED_TRIGGER_KINDS)
        assert "review_result_fingerprint" in action
        assert "disposition_id" in action
        assert "disposition_created_at" in action

    def test_auto_rework_persisted(self) -> None:
        action_in = _valid_review_action(
            verdict="changes_required", risk_level="medium"
        )
        msg = _make_source_review_message(action=action_in)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        result = _call_service(svc)
        action = self._assert_persisted(result, msg_repo)
        assert action["disposition_type"] == "AUTO_REWORK"

    def test_escalate_persisted(self) -> None:
        action_in = _valid_review_action(
            verdict="no_blocking_findings", risk_level="high"
        )
        msg = _make_source_review_message(action=action_in)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        result = _call_service(svc)
        action = self._assert_persisted(result, msg_repo)
        assert action["disposition_type"] == "ESCALATE_TO_HUMAN"
        assert action["escalation_triggers"] == ["high_review_risk"]


# ══════════════════════════════════════════════════════════════════════
# M. No-side-effect persistence
# ══════════════════════════════════════════════════════════════════════


class TestNoSideEffectPersistence:
    _SIDE_EFFECT_FLAGS = [
        "continuation_started",
        "rework_started",
        "human_escalation_package_created",
        "human_decision_recorded",
        "main_project_file_written",
        "sandbox_file_written",
        "manifest_file_written",
        "diff_file_written",
        "patch_applied",
        "git_write_performed",
        "worktree_created",
        "worker_started",
        "task_created",
        "run_created",
        "gate_allows_write",
    ]

    def _assert_no_side_effects(self, action: dict) -> None:
        for flag in self._SIDE_EFFECT_FLAGS:
            assert action.get(flag) is False, f"{flag} should be False"
        assert action["ai_project_director_total_loop"] == "Partial"

    def test_auto_continue_no_side_effects(self) -> None:
        action_in = _valid_review_action(
            verdict="no_blocking_findings", risk_level="low"
        )
        msg = _make_source_review_message(action=action_in)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        result = _call_service(svc)
        action = result.message.suggested_actions[0]
        self._assert_no_side_effects(action)
        assert action["continuation_started"] is False

    def test_auto_rework_no_side_effects(self) -> None:
        action_in = _valid_review_action(
            verdict="changes_required", risk_level="medium"
        )
        msg = _make_source_review_message(action=action_in)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        result = _call_service(svc)
        action = result.message.suggested_actions[0]
        self._assert_no_side_effects(action)
        assert action["rework_started"] is False

    def test_escalate_no_side_effects(self) -> None:
        action_in = _valid_review_action(
            verdict="no_blocking_findings", risk_level="high"
        )
        msg = _make_source_review_message(action=action_in)
        svc, msg_repo = _build_service(messages={SOURCE_REVIEW_MSG_ID: msg})
        result = _call_service(svc)
        action = result.message.suggested_actions[0]
        self._assert_no_side_effects(action)
        assert action["human_escalation_package_created"] is False


# ══════════════════════════════════════════════════════════════════════
# N. Blocked path: no persistence
# ══════════════════════════════════════════════════════════════════════


class TestBlockedNoPersist:
    def test_blocked_no_message_no_commit(self) -> None:
        svc, msg_repo = _build_service(messages={})
        result = _call_service(svc)
        assert result.result.disposition_status == "blocked"
        assert result.message is None
        assert msg_repo.create_calls == []


# ══════════════════════════════════════════════════════════════════════
# O. Repository dependency contract
# ══════════════════════════════════════════════════════════════════════


class TestRepositoryDependency:
    def test_missing_session_repo(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewDispositionService(
            session_repository=None,
            message_repository=SpyMessageRepo(),
        )
        with pytest.raises(ValueError, match="repositories are required"):
            _call_service(svc)

    def test_missing_message_repo(self) -> None:
        svc = ProjectDirectorSandboxCandidateDiffReviewDispositionService(
            session_repository=FakeSessionRepo(),
            message_repository=None,
        )
        with pytest.raises(ValueError, match="repositories are required"):
            _call_service(svc)
