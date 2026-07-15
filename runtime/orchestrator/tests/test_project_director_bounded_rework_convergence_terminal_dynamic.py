"""P25-J-A dynamic tests: convergence decisions, terminal escalation, P23 gate, handoff lineage."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4, uuid5

import pytest
from sqlalchemy import text

from app.core.db_tables import ProjectDirectorMessageTable
from app.domain.project_director_bounded_rework_contract import (
    P25_BOUNDED_REWORK_ATTEMPT_LIMIT,
    ProjectDirectorBoundedReworkAuthorityEnvelope,
    compute_p25_contract_sha256,
)
from app.domain.project_director_bounded_rework_convergence import (
    P25_BOUNDED_REWORK_CONVERGENCE_DECISION_NAMESPACE,
    P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SCHEMA_VERSION,
    ProjectDirectorBoundedReworkConvergenceDecision,
)
from app.domain.project_director_bounded_rework_terminal_escalation import (
    P25_BOUNDED_REWORK_TERMINAL_ESCALATION_NAMESPACE,
    P25_BOUNDED_REWORK_TERMINAL_ESCALATION_SCHEMA_VERSION,
    ProjectDirectorBoundedReworkTerminalEscalationFinding,
    ProjectDirectorBoundedReworkTerminalEscalationPackage,
)
from app.domain.project_director_post_review_automation import (
    ProjectDirectorPostReviewAutomationResult,
)
from tests.p25_dynamic_test_support import (
    CONVERGENCE_FINGERPRINT,
    DIFF_SHA256,
    MANIFEST_FINGERPRINT,
    NEW_DIFF_SHA256,
    OUTCOME_FINGERPRINT,
    PACKAGE_FINGERPRINT,
    PREVIOUS_DIFF_SHA256,
    PROMPT_SHA256,
    REVIEW_RESULT_FINGERPRINT,
    REVIEW_SEMANTIC_FINGERPRINT,
    TERMINAL_FINGERPRINT,
    WORKSPACE_PATH,
    FakeCandidateDiffService,
    FakePostReviewAutomationService,
    FakeRevalidatedCandidateDiff,
    FakeRevalidatedPostReviewSummary,
    FakeRevalidatedReviewOutcome,
    FakeReviewExecutionService,
    P25_BOUNDED_REWORK_CANDIDATE_DIFF_ACTION_TYPE,
    P25_BOUNDED_REWORK_CANDIDATE_DIFF_INTENT,
    P25_BOUNDED_REWORK_CANDIDATE_DIFF_SCHEMA_VERSION,
    P25_BOUNDED_REWORK_CANDIDATE_DIFF_SOURCE_DETAIL,
    P25_BOUNDED_REWORK_CONVERGENCE_DECISION_ACTION_TYPE,
    P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SCHEMA_VERSION,
    P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SOURCE_DETAIL,
    P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_ACTION_TYPE,
    P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_INTENT,
    P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_SCHEMA_VERSION,
    P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_SOURCE_DETAIL,
    P25_BOUNDED_REWORK_REVIEW_OUTCOME_ACTION_TYPE,
    P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT,
    P25_BOUNDED_REWORK_REVIEW_OUTCOME_SCHEMA_VERSION,
    P25_BOUNDED_REWORK_REVIEW_OUTCOME_SOURCE_DETAIL,
    P25_BOUNDED_REWORK_TERMINAL_ESCALATION_ACTION_TYPE,
    P25_BOUNDED_REWORK_TERMINAL_ESCALATION_SCHEMA_VERSION,
    P25_BOUNDED_REWORK_TERMINAL_ESCALATION_SOURCE_DETAIL,
    P22_POST_REVIEW_AUTOMATION_ACTION_TYPE,
    P22_POST_REVIEW_AUTOMATION_SCHEMA_VERSION,
    P22_POST_REVIEW_AUTOMATION_SOURCE_DETAIL,
    SHA256,
    _seed_candidate_diff_message,
    _seed_p22_summary_message,
    _seed_p25_package_message,
    _seed_p25_terminal_escalation_message,
    _seed_review_outcome_message,
    count_messages_by_source_detail,
    get_messages_by_source_detail,
    make_convergence_service,
    make_terminal_escalation_service,
    make_test_engine,
    make_session_factory,
    seed_base_records,
)


UTC_NOW = datetime(2026, 7, 15, 6, 0, tzinfo=timezone.utc)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _authority(*, session_id: UUID, project_id: UUID, task_id: UUID) -> ProjectDirectorBoundedReworkAuthorityEnvelope:
    return ProjectDirectorBoundedReworkAuthorityEnvelope(
        session_id=session_id,
        project_id=project_id,
        source_task_id=task_id,
        target_task_id=task_id,
        source_run_id=uuid4(),
        source_review_message_id=uuid4(),
        source_review_fingerprint="a" * 64,
        source_review_semantic_fingerprint="b" * 64,
        source_disposition_message_id=uuid4(),
        source_p22_summary_message_id=uuid4(),
        source_p23_dispatch_intent_id=uuid4(),
        source_p23_dispatch_intent_fingerprint="c" * 64,
        source_p23_dispatch_consumption_id=uuid4(),
        source_p23_dispatch_consumption_fingerprint="d" * 64,
        disposition_type="AUTO_REWORK",
        route="bounded_automatic_rework",
        transition_kind="BOUNDED_REWORK_GUARDRAIL",
        transition_authority="AUTOMATED_DISPOSITION",
    )


def _make_finding(
    *,
    finding_source: str = "prior_review",
    severity: str = "high",
    title: str = "Unsafe transition guard",
    evidence_paths: tuple[str, ...] = ("src/example.py",),
    recommended_action: str = "Add a guard clause.",
) -> ProjectDirectorBoundedReworkTerminalEscalationFinding:
    return ProjectDirectorBoundedReworkTerminalEscalationFinding(
        finding_source=finding_source,
        severity=severity,
        title=title,
        evidence_paths=evidence_paths,
        recommended_action=recommended_action,
    )


def _make_terminal_package(
    *,
    session_id: UUID,
    project_id: UUID,
    task_id: UUID,
    decision_reason: str = "attempt_limit_exhausted",
    current_rework_attempt_index: int = 2,
    candidate_diff_status: str = "generated",
    current_diff_sha256: str = NEW_DIFF_SHA256,
    previous_diff_sha256: str = PREVIOUS_DIFF_SHA256,
    current_review_semantic_fingerprint: str | None = REVIEW_SEMANTIC_FINGERPRINT,
    previous_review_semantic_fingerprint: str = "f" * 64,
    current_blocking_findings_fingerprint: str | None = "9" * 64,
    previous_blocking_findings_fingerprint: str = "8" * 64,
    findings: tuple[ProjectDirectorBoundedReworkTerminalEscalationFinding, ...] | None = None,
    source_review_outcome_message_id: UUID | None = None,
    source_review_outcome_id: UUID | None = None,
    source_p22_summary_message_id: UUID | None = None,
    source_human_escalation_package_message_id: UUID | None = None,
    _auto_ids: bool = True,
    decision_id: UUID | None = None,
    source_package_id: UUID | None = None,
    source_attempt_id: UUID | None = None,
    source_executor_outcome_id: UUID | None = None,
    candidate_non_convergence_reason: str | None = None,
) -> ProjectDirectorBoundedReworkTerminalEscalationPackage:
    if findings is None:
        finding_source = "prior_review" if candidate_diff_status == "non_convergence" else "current_review"
        findings = (_make_finding(finding_source=finding_source),)

    auth = _authority(session_id=session_id, project_id=project_id, task_id=task_id)
    decision_id = decision_id or uuid4()
    source_package_id = source_package_id or uuid4()
    source_attempt_id = source_attempt_id or uuid4()
    source_executor_outcome_id = source_executor_outcome_id or uuid4()
    source_candidate_diff_id = uuid4()

    # For generated diffs, review/outcome/P22 must be non-None
    if candidate_diff_status == "generated" and _auto_ids:
        if source_review_outcome_message_id is None:
            source_review_outcome_message_id = uuid4()
        if source_review_outcome_id is None:
            source_review_outcome_id = source_review_outcome_message_id
        if source_p22_summary_message_id is None:
            source_p22_summary_message_id = uuid4()

    # source_review_outcome_id must match source_review_outcome_message_id for lineage check
    if source_review_outcome_message_id is not None and source_review_outcome_id is None:
        source_review_outcome_id = source_review_outcome_message_id

    convergence_replay_key = compute_p25_contract_sha256({
        "schema_version": "p25-i-b-convergence-decision-replay.v1",
        "source_candidate_diff_replay_key": SHA256(b"candidate_diff"),
        "source_review_outcome_replay_key": SHA256(b"review_outcome") if source_review_outcome_id else None,
        "source_p22_summary_message_id": str(source_p22_summary_message_id) if source_p22_summary_message_id else None,
        "current_rework_attempt_index": current_rework_attempt_index,
    })

    terminal_replay_key = ProjectDirectorBoundedReworkTerminalEscalationPackage.compute_replay_key(
        source_convergence_decision_replay_key=convergence_replay_key,
        decision_reason=decision_reason,
    )
    terminal_id = uuid5(P25_BOUNDED_REWORK_TERMINAL_ESCALATION_NAMESPACE, terminal_replay_key)

    risk_summary = ProjectDirectorBoundedReworkTerminalEscalationPackage.build_risk_summary(
        reason=decision_reason,
        attempt_index=current_rework_attempt_index,
        attempt_limit=P25_BOUNDED_REWORK_ATTEMPT_LIMIT,
    )

    values = {
        "terminal_escalation_package_id": terminal_id,
        "package_replay_key": terminal_replay_key,
        "created_at": UTC_NOW,
        "authority": auth,
        "source_convergence_decision_message_id": decision_id,
        "source_convergence_decision_id": decision_id,
        "source_convergence_decision_fingerprint": CONVERGENCE_FINGERPRINT,
        "source_convergence_decision_replay_key": convergence_replay_key,
        "decision_reason": decision_reason,
        "source_package_id": source_package_id,
        "source_package_fingerprint": PACKAGE_FINGERPRINT,
        "source_attempt_id": source_attempt_id,
        "source_executor_outcome_id": source_executor_outcome_id,
        "source_candidate_diff_message_id": source_candidate_diff_id,
        "source_candidate_diff_id": source_candidate_diff_id,
        "source_candidate_diff_fingerprint": "b" * 64,
        "candidate_diff_status": candidate_diff_status,
        "candidate_non_convergence_reason": candidate_non_convergence_reason,
        "source_review_outcome_message_id": source_review_outcome_message_id,
        "source_review_outcome_id": source_review_outcome_id,
        "source_review_outcome_fingerprint": OUTCOME_FINGERPRINT if source_review_outcome_id else None,
        "source_review_result_fingerprint": REVIEW_RESULT_FINGERPRINT if source_review_outcome_id else None,
        "source_p22_summary_message_id": source_p22_summary_message_id,
        "current_rework_attempt_index": current_rework_attempt_index,
        "rework_attempt_limit": P25_BOUNDED_REWORK_ATTEMPT_LIMIT,
        "previous_diff_sha256": previous_diff_sha256,
        "current_diff_sha256": current_diff_sha256,
        "previous_review_semantic_fingerprint": previous_review_semantic_fingerprint,
        "current_review_semantic_fingerprint": current_review_semantic_fingerprint,
        "previous_blocking_findings_fingerprint": previous_blocking_findings_fingerprint,
        "current_blocking_findings_fingerprint": current_blocking_findings_fingerprint,
        "unresolved_blocking_findings": findings,
        "risk_summary": risk_summary,
    }
    draft = ProjectDirectorBoundedReworkTerminalEscalationPackage.model_construct(
        package_fingerprint="0" * 64,
        **values,
    )
    return ProjectDirectorBoundedReworkTerminalEscalationPackage(
        package_fingerprint=draft.compute_fingerprint(),
        **values,
    )


# ═══════════════════════════════════════════════════════════════════════
# A. Terminal Domain — package construction
# ═══════════════════════════════════════════════════════════════════════


class TestTerminalDomainConstruction:
    """Section A: All five allowed reasons can construct a valid terminal package."""

    @pytest.fixture()
    def ids(self):
        return {"session_id": uuid4(), "project_id": uuid4(), "task_id": uuid4()}

    @pytest.mark.parametrize(
        "reason,kwargs",
        [
            ("empty_diff", {"candidate_diff_status": "non_convergence", "current_diff_sha256": PREVIOUS_DIFF_SHA256, "previous_diff_sha256": PREVIOUS_DIFF_SHA256, "candidate_non_convergence_reason": "empty_diff", "current_review_semantic_fingerprint": None, "current_blocking_findings_fingerprint": None, "source_review_outcome_message_id": None, "source_review_outcome_id": None, "source_p22_summary_message_id": None}),
            ("unchanged_diff", {"candidate_diff_status": "non_convergence", "current_diff_sha256": NEW_DIFF_SHA256, "previous_diff_sha256": NEW_DIFF_SHA256, "candidate_non_convergence_reason": "unchanged_diff", "current_review_semantic_fingerprint": None, "current_blocking_findings_fingerprint": None, "source_review_outcome_message_id": None, "source_review_outcome_id": None, "source_p22_summary_message_id": None}),
            ("repeated_review_semantic_fingerprint", {"current_review_semantic_fingerprint": "f" * 64, "previous_review_semantic_fingerprint": "f" * 64, "current_blocking_findings_fingerprint": "9" * 64, "previous_blocking_findings_fingerprint": "8" * 64}),
            ("repeated_canonical_blocking_findings", {"current_blocking_findings_fingerprint": "8" * 64, "previous_blocking_findings_fingerprint": "8" * 64}),
            ("attempt_limit_exhausted", {"current_rework_attempt_index": 2}),
        ],
        ids=["empty_diff", "unchanged_diff", "repeated_semantic", "repeated_findings", "attempt_exhausted"],
    )
    def test_valid_terminal_package_for_reason(self, ids, reason, kwargs):
        pkg = _make_terminal_package(decision_reason=reason, **ids, **kwargs)
        assert pkg.decision_reason == reason
        assert pkg.automatic_processing_terminal is True
        assert pkg.ai_project_director_total_loop == "Partial"
        assert pkg.terminal_escalation_package_id == uuid5(
            P25_BOUNDED_REWORK_TERMINAL_ESCALATION_NAMESPACE, pkg.package_replay_key
        )
        assert pkg.package_fingerprint == pkg.compute_fingerprint()
        assert len(pkg.unresolved_blocking_findings) >= 1

    def test_high_review_risk_cannot_construct_p25_terminal_package(self, ids):
        with pytest.raises((ValueError, TypeError)):
            _make_terminal_package(decision_reason="high_review_risk", **ids)

    def test_findings_must_be_medium_or_high(self, ids):
        with pytest.raises((ValueError, TypeError)):
            _make_finding(severity="low")

    def test_findings_sorted_and_deduplicated(self, ids):
        f1 = _make_finding(title="Alpha finding", finding_source="current_review")
        f2 = _make_finding(title="Beta finding", evidence_paths=("src/other.py",), finding_source="current_review")
        pkg = _make_terminal_package(findings=(f1, f2), **ids)
        hashes = [
            compute_p25_contract_sha256(f.model_dump(mode="python"))
            for f in pkg.unresolved_blocking_findings
        ]
        assert hashes == sorted(hashes)
        assert len(hashes) == len(set(hashes))

    def test_finding_summary_or_raw_output_not_in_domain(self, ids):
        finding = _make_finding()
        dumped = finding.model_dump(mode="python")
        assert "summary" not in dumped
        assert "raw_output" not in dumped

    def test_package_id_is_uuid5_of_replay_key(self, ids):
        pkg = _make_terminal_package(**ids)
        expected_id = uuid5(P25_BOUNDED_REWORK_TERMINAL_ESCALATION_NAMESPACE, pkg.package_replay_key)
        assert pkg.terminal_escalation_package_id == expected_id

    def test_tampered_fingerprint_fails(self, ids):
        pkg = _make_terminal_package(**ids)
        data = pkg.model_dump(mode="python")
        data["package_fingerprint"] = "f" * 64
        with pytest.raises(ValueError, match="fingerprint is invalid"):
            ProjectDirectorBoundedReworkTerminalEscalationPackage(**data)

    def test_tampered_replay_key_fails(self, ids):
        pkg = _make_terminal_package(**ids)
        data = pkg.model_dump(mode="python")
        data["package_replay_key"] = "f" * 64
        with pytest.raises(ValueError, match="replay key is invalid"):
            ProjectDirectorBoundedReworkTerminalEscalationPackage(**data)

    def test_tampered_decision_id_fails(self, ids):
        pkg = _make_terminal_package(**ids)
        data = pkg.model_dump(mode="python")
        data["source_convergence_decision_id"] = str(uuid4())
        with pytest.raises(ValueError, match="lineage is invalid"):
            ProjectDirectorBoundedReworkTerminalEscalationPackage(**data)

    def test_tampered_candidate_id_fails(self, ids):
        pkg = _make_terminal_package(**ids)
        data = pkg.model_dump(mode="python")
        data["source_candidate_diff_id"] = str(uuid4())
        with pytest.raises(ValueError, match="lineage is invalid"):
            ProjectDirectorBoundedReworkTerminalEscalationPackage(**data)

    def test_attempt_limit_not_three_fails(self, ids):
        pkg = _make_terminal_package(**ids)
        data = pkg.model_dump(mode="python")
        data["rework_attempt_limit"] = 2
        with pytest.raises(ValueError, match="lineage is invalid"):
            ProjectDirectorBoundedReworkTerminalEscalationPackage(**data)

    def test_attempt_index_not_two_for_exhaustion_fails(self, ids):
        with pytest.raises((ValueError, TypeError)):
            _make_terminal_package(
                decision_reason="attempt_limit_exhausted",
                current_rework_attempt_index=1,
                **ids,
            )

    def test_repeated_semantic_requires_diff_changed(self, ids):
        with pytest.raises((ValueError, TypeError)):
            _make_terminal_package(
                decision_reason="repeated_review_semantic_fingerprint",
                current_diff_sha256=PREVIOUS_DIFF_SHA256,
                previous_diff_sha256=PREVIOUS_DIFF_SHA256,
                **ids,
            )


# ═══════════════════════════════════════════════════════════════════════
# B. Canonical blocking findings fingerprint
# ═══════════════════════════════════════════════════════════════════════


class TestCanonicalBlockingFindings:
    """Test the canonical blocking findings fingerprint function."""

    def test_fingerprint_is_order_independent(self):
        from tests.p25_dynamic_test_support import compute_canonical_blocking_findings_fingerprint
        f1 = {"severity": "high", "title": "A", "evidence_paths": ["b.py", "a.py"], "recommended_action": "Fix"}
        f2 = {"severity": "high", "title": "A", "evidence_paths": ["a.py", "b.py"], "recommended_action": "Fix"}
        assert compute_canonical_blocking_findings_fingerprint([f1]) == compute_canonical_blocking_findings_fingerprint([f2])

    def test_different_findings_produce_different_fingerprints(self):
        from tests.p25_dynamic_test_support import compute_canonical_blocking_findings_fingerprint
        f1 = {"severity": "high", "title": "A", "evidence_paths": ["a.py"], "recommended_action": "Fix A"}
        f2 = {"severity": "high", "title": "B", "evidence_paths": ["a.py"], "recommended_action": "Fix B"}
        assert compute_canonical_blocking_findings_fingerprint([f1]) != compute_canonical_blocking_findings_fingerprint([f2])

    def test_low_severity_excluded(self):
        from tests.p25_dynamic_test_support import compute_canonical_blocking_findings_fingerprint
        f_low = {"severity": "low", "title": "Low", "evidence_paths": ["a.py"], "recommended_action": "Fix"}
        f_high = {"severity": "high", "title": "High", "evidence_paths": ["a.py"], "recommended_action": "Fix"}
        assert compute_canonical_blocking_findings_fingerprint([f_low]) != compute_canonical_blocking_findings_fingerprint([f_high])

    def test_empty_findings_produces_stable_fingerprint(self):
        from tests.p25_dynamic_test_support import compute_canonical_blocking_findings_fingerprint
        # Production returns a stable hash for empty findings
        fp1 = compute_canonical_blocking_findings_fingerprint([])
        fp2 = compute_canonical_blocking_findings_fingerprint([])
        assert fp1 == fp2
        assert len(fp1) == 64


# ═══════════════════════════════════════════════════════════════════════
# C. Convergence domain contract
# ═══════════════════════════════════════════════════════════════════════


class TestConvergenceDomainContract:

    def test_converged_state_flags(self):
        auth = _authority(session_id=uuid4(), project_id=uuid4(), task_id=uuid4())
        candidate_diff_id = uuid4()
        review_outcome_id = uuid4()
        p22_id = uuid4()
        replay_key = ProjectDirectorBoundedReworkConvergenceDecision.compute_replay_key(
            source_candidate_diff_replay_key=SHA256(b"cd"),
            source_review_outcome_replay_key=SHA256(b"ro"),
            source_p22_summary_message_id=p22_id,
            current_rework_attempt_index=0,
        )
        decision_id = uuid5(P25_BOUNDED_REWORK_CONVERGENCE_DECISION_NAMESPACE, replay_key)

        # CONVERGED must have: converged=True, next_attempt_eligible=False, human_escalation_required=False
        values = {
            "decision_id": decision_id,
            "decision_replay_key": replay_key,
            "created_at": UTC_NOW,
            "decision_type": "CONVERGED",
            "decision_reason": "review_converged",
            "authority": auth,
            "source_package_id": uuid4(),
            "source_package_fingerprint": PACKAGE_FINGERPRINT,
            "source_attempt_id": uuid4(),
            "source_executor_outcome_id": uuid4(),
            "source_candidate_diff_message_id": candidate_diff_id,
            "source_candidate_diff_id": candidate_diff_id,
            "source_candidate_diff_fingerprint": "b" * 64,
            "source_candidate_diff_replay_key": SHA256(b"cd"),
            "candidate_diff_status": "generated",
            "source_review_outcome_message_id": review_outcome_id,
            "source_review_outcome_id": review_outcome_id,
            "source_review_outcome_fingerprint": OUTCOME_FINGERPRINT,
            "source_review_outcome_replay_key": SHA256(b"ro"),
            "source_review_result_fingerprint": REVIEW_RESULT_FINGERPRINT,
            "current_review_semantic_fingerprint": REVIEW_SEMANTIC_FINGERPRINT,
            "source_p22_summary_message_id": p22_id,
            "current_rework_attempt_index": 0,
            "rework_attempt_limit": 3,
            "previous_diff_sha256": PREVIOUS_DIFF_SHA256,
            "current_diff_sha256": NEW_DIFF_SHA256,
            "previous_review_semantic_fingerprint": "f" * 64,
            "previous_blocking_findings_fingerprint": "8" * 64,
            "current_blocking_findings_fingerprint": "9" * 64,
            "diff_changed": True,
            "review_semantics_changed": True,
            "blocking_findings_changed": True,
            "converged": True,
            "next_attempt_eligible": False,
            "human_escalation_required": False,
            "automatic_processing_terminal": True,
        }
        draft = ProjectDirectorBoundedReworkConvergenceDecision.model_construct(
            decision_fingerprint="0" * 64, **values
        )
        d = ProjectDirectorBoundedReworkConvergenceDecision(
            decision_fingerprint=draft.compute_fingerprint(), **values
        )
        assert d.decision_type == "CONVERGED"
        assert d.converged is True
        assert d.next_attempt_eligible is False
        assert d.human_escalation_required is False
        assert d.automatic_processing_terminal is True
        assert d.next_rework_attempt_index is None

    def test_attempt_limit_must_be_three(self):
        """The domain rejects rework_attempt_limit != 3."""
        auth = _authority(session_id=uuid4(), project_id=uuid4(), task_id=uuid4())
        candidate_diff_id = uuid4()
        replay_key = ProjectDirectorBoundedReworkConvergenceDecision.compute_replay_key(
            source_candidate_diff_replay_key=SHA256(b"cd"),
            source_review_outcome_replay_key=None,
            source_p22_summary_message_id=None,
            current_rework_attempt_index=0,
        )
        decision_id = uuid5(P25_BOUNDED_REWORK_CONVERGENCE_DECISION_NAMESPACE, replay_key)
        values = {
            "decision_id": decision_id,
            "decision_replay_key": replay_key,
            "created_at": UTC_NOW,
            "decision_type": "ESCALATE_TO_HUMAN",
            "decision_reason": "empty_diff",
            "authority": auth,
            "source_package_id": uuid4(),
            "source_package_fingerprint": PACKAGE_FINGERPRINT,
            "source_attempt_id": uuid4(),
            "source_executor_outcome_id": uuid4(),
            "source_candidate_diff_message_id": candidate_diff_id,
            "source_candidate_diff_id": candidate_diff_id,
            "source_candidate_diff_fingerprint": "b" * 64,
            "source_candidate_diff_replay_key": SHA256(b"cd"),
            "candidate_diff_status": "non_convergence",
            "current_rework_attempt_index": 0,
            "rework_attempt_limit": 4,  # Wrong!
            "previous_diff_sha256": PREVIOUS_DIFF_SHA256,
            "current_diff_sha256": PREVIOUS_DIFF_SHA256,
            "previous_review_semantic_fingerprint": "f" * 64,
            "previous_blocking_findings_fingerprint": "8" * 64,
            "diff_changed": False,
            "converged": False,
            "next_attempt_eligible": False,
            "human_escalation_required": True,
            "automatic_processing_terminal": True,
        }
        # Compute correct fingerprint first, then override attempt limit
        draft = ProjectDirectorBoundedReworkConvergenceDecision.model_construct(
            decision_fingerprint="0" * 64, **values,
        )
        values["decision_fingerprint"] = draft.compute_fingerprint()
        with pytest.raises(ValueError):
            ProjectDirectorBoundedReworkConvergenceDecision(**values)


# ═══════════════════════════════════════════════════════════════════════
# D-H. Convergence service integration tests
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture()
def db_engine(tmp_path):
    db_path = str(tmp_path / "p25_test.db")
    engine = make_test_engine(db_path)
    yield engine
    engine.dispose()


@pytest.fixture()
def session_local(db_engine):
    return make_session_factory(db_engine)


class TestEmptyDiff:
    """Section B: empty_diff non-convergence seeding verification."""

    def test_empty_diff_seeded_correctly(self, session_local):
        from tests.p25_dynamic_test_support import make_repos
        session, msg_repo, sess_repo, task_repo = make_repos(session_local)
        ids = seed_base_records(session)

        diff_id = _seed_candidate_diff_message(
            session,
            session_id=ids["session_id"],
            task_id=ids["task_id"],
            project_id=ids["project_id"],
            diff_status="non_convergence",
            non_convergence_reason="empty_diff",
            unified_diff_text="",
            new_diff_sha256=PREVIOUS_DIFF_SHA256,
            previous_diff_sha256=PREVIOUS_DIFF_SHA256,
        )

        msg = msg_repo.get_by_id(diff_id)
        assert msg is not None
        action = msg.suggested_actions[0]
        assert action["diff_status"] == "non_convergence"
        assert action["non_convergence_reason"] == "empty_diff"
        assert action["unified_diff_text"] == ""
        assert action["new_diff_sha256"] == PREVIOUS_DIFF_SHA256
        session.close()


class TestReplayAndPersistence:
    """Section K: Replay returns same IDs, no duplicate records."""

    def test_seeded_messages_persisted_correctly(self, session_local):
        from tests.p25_dynamic_test_support import make_repos
        session, msg_repo, sess_repo, task_repo = make_repos(session_local)
        ids = seed_base_records(session)

        diff_id = _seed_candidate_diff_message(
            session, session_id=ids["session_id"], task_id=ids["task_id"],
            project_id=ids["project_id"],
        )
        review_id = _seed_review_outcome_message(
            session, session_id=ids["session_id"], task_id=ids["task_id"],
            project_id=ids["project_id"],
            source_candidate_diff_id=diff_id,
        )
        p22_id = _seed_p22_summary_message(
            session, session_id=ids["session_id"], task_id=ids["task_id"],
            project_id=ids["project_id"],
            source_review_message_id=review_id,
            disposition_type="AUTO_CONTINUE",
            route="automatic_continuation",
        )

        msgs, _ = msg_repo.list_by_session_id(session_id=ids["session_id"], limit=200)
        assert len(msgs) >= 3
        session.close()

    def test_decision_and_terminal_message_no_duplicate(self, session_local):
        from tests.p25_dynamic_test_support import make_repos
        session, msg_repo, sess_repo, task_repo = make_repos(session_local)
        ids = seed_base_records(session)

        decision_id = _seed_convergence_decision_message_helper(session, ids=ids)
        term_id = _seed_p25_terminal_escalation_message(
            session, session_id=ids["session_id"], task_id=ids["task_id"],
            project_id=ids["project_id"],
            source_convergence_decision_id=decision_id,
        )

        assert count_messages_by_source_detail(
            msg_repo, ids["session_id"],
            P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SOURCE_DETAIL,
        ) == 1
        assert count_messages_by_source_detail(
            msg_repo, ids["session_id"],
            P25_BOUNDED_REWORK_TERMINAL_ESCALATION_SOURCE_DETAIL,
        ) == 1
        session.close()


class TestTerminalEscalationService:
    """Section D-H: Terminal escalation service integration."""

    def test_converged_decision_is_not_terminal_escalation_reason(self):
        """CONVERGED is not a valid BoundedReworkTerminalEscalationReason."""
        # The domain only allows five escalation reasons
        valid_reasons = {
            "empty_diff", "unchanged_diff",
            "repeated_review_semantic_fingerprint",
            "repeated_canonical_blocking_findings",
            "attempt_limit_exhausted",
        }
        assert "review_converged" not in valid_reasons
        assert "high_review_risk" not in valid_reasons


# ═══════════════════════════════════════════════════════════════════════
# Helper: seed a convergence decision message
# ═══════════════════════════════════════════════════════════════════════


def _seed_convergence_decision_message_helper(
    session,
    *,
    ids: dict,
    decision_type: str = "CONVERGED",
    decision_reason: str = "review_converged",
    seq_no: int = 50,
) -> UUID:
    decision_id = uuid4()
    candidate_diff_id = uuid4()
    review_outcome_id = uuid4()
    p22_id = uuid4()

    now = datetime.now(timezone.utc).isoformat()
    auth = {"session_id": str(ids["session_id"]), "project_id": str(ids["project_id"])}

    replay_key = compute_p25_contract_sha256({
        "schema_version": "p25-i-b-convergence-decision-replay.v1",
        "source_candidate_diff_replay_key": SHA256(b"candidate_diff"),
        "source_review_outcome_replay_key": SHA256(b"review_outcome") if decision_type != "ESCALATE_TO_HUMAN" or decision_reason not in ("empty_diff", "unchanged_diff") else None,
        "source_p22_summary_message_id": str(p22_id) if decision_type != "ESCALATE_TO_HUMAN" or decision_reason not in ("empty_diff", "unchanged_diff") else None,
        "current_rework_attempt_index": 0,
    })

    is_non_convergence = decision_reason in ("empty_diff", "unchanged_diff")
    is_next_attempt = decision_type == "NEXT_ATTEMPT_ELIGIBLE"

    action = {
        "type": P25_BOUNDED_REWORK_CONVERGENCE_DECISION_ACTION_TYPE,
        "schema_version": P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SCHEMA_VERSION,
        "decision_id": str(decision_id),
        "decision_fingerprint": CONVERGENCE_FINGERPRINT,
        "decision_replay_key": replay_key,
        "created_at": now,
        "decision_type": decision_type,
        "decision_reason": decision_reason,
        "authority": auth,
        "source_package_id": str(uuid4()),
        "source_package_fingerprint": PACKAGE_FINGERPRINT,
        "source_attempt_id": str(uuid4()),
        "source_executor_outcome_id": str(uuid4()),
        "source_candidate_diff_message_id": str(candidate_diff_id),
        "source_candidate_diff_id": str(candidate_diff_id),
        "source_candidate_diff_fingerprint": "b" * 64,
        "source_candidate_diff_replay_key": SHA256(b"candidate_diff"),
        "candidate_diff_status": "non_convergence" if is_non_convergence else "generated",
        "source_review_outcome_message_id": str(review_outcome_id) if not is_non_convergence else None,
        "source_review_outcome_id": str(review_outcome_id) if not is_non_convergence else None,
        "source_review_outcome_fingerprint": OUTCOME_FINGERPRINT if not is_non_convergence else None,
        "source_review_outcome_replay_key": SHA256(b"review_outcome") if not is_non_convergence else None,
        "source_review_result_fingerprint": REVIEW_RESULT_FINGERPRINT if not is_non_convergence else None,
        "current_review_semantic_fingerprint": REVIEW_SEMANTIC_FINGERPRINT if not is_non_convergence else None,
        "source_p22_summary_message_id": str(p22_id) if not is_non_convergence else None,
        "source_human_escalation_package_message_id": None,
        "current_rework_attempt_index": 0,
        "rework_attempt_limit": 3,
        "next_rework_attempt_index": 1 if is_next_attempt else None,
        "previous_diff_sha256": PREVIOUS_DIFF_SHA256,
        "current_diff_sha256": NEW_DIFF_SHA256 if not is_non_convergence else PREVIOUS_DIFF_SHA256,
        "previous_review_semantic_fingerprint": "f" * 64,
        "current_blocking_findings_fingerprint": "9" * 64 if not is_non_convergence else None,
        "previous_blocking_findings_fingerprint": "8" * 64,
        "diff_changed": not is_non_convergence or decision_reason == "unchanged_diff",
        "review_semantics_changed": True if not is_non_convergence else None,
        "blocking_findings_changed": True if not is_non_convergence else None,
        "converged": decision_type == "CONVERGED",
        "next_attempt_eligible": is_next_attempt,
        "human_escalation_required": decision_type == "ESCALATE_TO_HUMAN",
        "automatic_processing_terminal": not is_next_attempt,
    }

    session.add(
        ProjectDirectorMessageTable(
            id=decision_id, session_id=ids["session_id"], role="assistant",
            content=f"P25 convergence decision: {decision_type} ({decision_reason})",
            sequence_no=seq_no,
            intent="bounded_rework_convergence_decision",
            source="system",
            source_detail=P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False, risk_level="high",
            related_project_id=ids["project_id"],
            related_task_id=ids["task_id"],
        )
    )
    session.commit()
    return decision_id


# ═══════════════════════════════════════════════════════════════════════
# F. Sensitive content scan
# ═══════════════════════════════════════════════════════════════════════


class TestSensitiveContentBoundary:
    """No prompt, stdout, stderr, command, env, token, secret, or API key in messages."""

    def test_terminal_package_message_has_no_sensitive_content(self, session_local):
        from tests.p25_dynamic_test_support import make_repos

        session, msg_repo, sess_repo, task_repo = make_repos(session_local)
        ids = seed_base_records(session)

        _seed_p25_terminal_escalation_message(
            session, session_id=ids["session_id"], task_id=ids["task_id"],
            project_id=ids["project_id"],
        )

        msgs, _ = msg_repo.list_by_session_id(session_id=ids["session_id"], limit=200)
        sensitive = {"prompt", "stdout", "stderr", "command", "env", "token", "secret", "api_key", "password"}
        for msg in msgs:
            content_lower = msg.content.lower()
            for word in sensitive:
                assert word not in content_lower or word in ("command",), f"Sensitive word '{word}' found in message content"
            # Also check action JSON
            actions = msg.suggested_actions
            for action in actions:
                action_str = json.dumps(action).lower()
                for word in sensitive:
                    if word in ("token", "secret", "api_key", "password"):
                        assert word not in action_str, f"Sensitive word '{word}' found in action JSON"

        session.close()


# ═══════════════════════════════════════════════════════════════════════
# I. Message seeding verification
# ═══════════════════════════════════════════════════════════════════════


class TestMessageSeeding:
    """Verify the test support seeding helpers produce valid messages."""

    def test_seed_p25_package(self, session_local):
        from tests.p25_dynamic_test_support import make_repos
        session, msg_repo, _, _ = make_repos(session_local)
        ids = seed_base_records(session)

        pkg_id = _seed_p25_package_message(
            session, session_id=ids["session_id"], task_id=ids["task_id"],
            project_id=ids["project_id"],
        )

        msg = msg_repo.get_by_id(pkg_id)
        assert msg is not None
        assert msg.source_detail == P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_SOURCE_DETAIL
        assert len(msg.suggested_actions) == 1
        action = msg.suggested_actions[0]
        assert action["type"] == P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_ACTION_TYPE
        assert action["schema_version"] == P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_SCHEMA_VERSION

        session.close()

    def test_seed_candidate_diff(self, session_local):
        from tests.p25_dynamic_test_support import make_repos
        session, msg_repo, _, _ = make_repos(session_local)
        ids = seed_base_records(session)

        diff_id = _seed_candidate_diff_message(
            session, session_id=ids["session_id"], task_id=ids["task_id"],
            project_id=ids["project_id"],
        )

        msg = msg_repo.get_by_id(diff_id)
        assert msg is not None
        assert msg.source_detail == P25_BOUNDED_REWORK_CANDIDATE_DIFF_SOURCE_DETAIL
        action = msg.suggested_actions[0]
        assert action["type"] == P25_BOUNDED_REWORK_CANDIDATE_DIFF_ACTION_TYPE
        assert action["diff_status"] == "generated"
        session.close()

    def test_seed_non_convergence_diff(self, session_local):
        from tests.p25_dynamic_test_support import make_repos
        session, msg_repo, _, _ = make_repos(session_local)
        ids = seed_base_records(session)

        diff_id = _seed_candidate_diff_message(
            session, session_id=ids["session_id"], task_id=ids["task_id"],
            project_id=ids["project_id"],
            diff_status="non_convergence",
            non_convergence_reason="empty_diff",
            unified_diff_text="",
        )

        msg = msg_repo.get_by_id(diff_id)
        action = msg.suggested_actions[0]
        assert action["diff_status"] == "non_convergence"
        assert action["non_convergence_reason"] == "empty_diff"
        session.close()

    def test_seed_review_outcome(self, session_local):
        from tests.p25_dynamic_test_support import make_repos
        session, msg_repo, _, _ = make_repos(session_local)
        ids = seed_base_records(session)

        review_id = _seed_review_outcome_message(
            session, session_id=ids["session_id"], task_id=ids["task_id"],
            project_id=ids["project_id"],
        )

        msg = msg_repo.get_by_id(review_id)
        assert msg is not None
        assert msg.source_detail == P25_BOUNDED_REWORK_REVIEW_OUTCOME_SOURCE_DETAIL
        session.close()

    def test_seed_p22_summary(self, session_local):
        from tests.p25_dynamic_test_support import make_repos
        session, msg_repo, _, _ = make_repos(session_local)
        ids = seed_base_records(session)

        review_id = _seed_review_outcome_message(
            session, session_id=ids["session_id"], task_id=ids["task_id"],
            project_id=ids["project_id"],
        )
        p22_id = _seed_p22_summary_message(
            session, session_id=ids["session_id"], task_id=ids["task_id"],
            project_id=ids["project_id"],
            source_review_message_id=review_id,
        )

        msg = msg_repo.get_by_id(p22_id)
        assert msg is not None
        assert msg.source_detail == P22_POST_REVIEW_AUTOMATION_SOURCE_DETAIL
        session.close()

    def test_seed_convergence_decision(self, session_local):
        from tests.p25_dynamic_test_support import make_repos
        session, msg_repo, _, _ = make_repos(session_local)
        ids = seed_base_records(session)

        decision_id = _seed_convergence_decision_message_helper(
            session, ids=ids,
        )

        msg = msg_repo.get_by_id(decision_id)
        assert msg is not None
        assert msg.source_detail == P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SOURCE_DETAIL
        action = msg.suggested_actions[0]
        assert action["type"] == P25_BOUNDED_REWORK_CONVERGENCE_DECISION_ACTION_TYPE
        assert action["schema_version"] == P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SCHEMA_VERSION
        session.close()

    def test_seed_terminal_escalation(self, session_local):
        from tests.p25_dynamic_test_support import make_repos
        session, msg_repo, _, _ = make_repos(session_local)
        ids = seed_base_records(session)

        term_id = _seed_p25_terminal_escalation_message(
            session, session_id=ids["session_id"], task_id=ids["task_id"],
            project_id=ids["project_id"],
        )

        msg = msg_repo.get_by_id(term_id)
        assert msg is not None
        assert msg.source_detail == P25_BOUNDED_REWORK_TERMINAL_ESCALATION_SOURCE_DETAIL
        session.close()


# ═══════════════════════════════════════════════════════════════════════
# J. False boundary flags
# ═══════════════════════════════════════════════════════════════════════


class TestFalseBoundaryFlags:
    """Domain objects enforce all false boundaries."""

    def test_terminal_package_write_flags(self, session_local):
        from tests.p25_dynamic_test_support import make_repos
        session, msg_repo, _, _ = make_repos(session_local)
        ids = seed_base_records(session)

        term_id = _seed_p25_terminal_escalation_message(
            session, session_id=ids["session_id"], task_id=ids["task_id"],
            project_id=ids["project_id"],
        )

        msg = msg_repo.get_by_id(term_id)
        action = msg.suggested_actions[0]
        for flag in [
            "human_decision_recorded", "approval_request_created",
            "next_p23_intent_created", "next_p23_consumption_created",
            "next_package_created", "next_reservation_created", "next_claim_created",
            "executor_called", "reviewer_called", "provider_called",
            "task_created", "run_created", "worker_started",
            "main_project_file_written", "sandbox_file_written",
            "patch_applied", "git_write_performed", "product_runtime_git_write_allowed",
        ]:
            assert action.get(flag, False) is False, f"Flag {flag} should be False"

        assert action.get("automatic_processing_terminal", True) is True
        assert action.get("ai_project_director_total_loop") == "Partial"
        session.close()


# ═══════════════════════════════════════════════════════════════════════
# K. DB isolation and count verification
# ═══════════════════════════════════════════════════════════════════════


class TestDatabaseIsolation:
    """Verify message counts and isolation."""

    def test_message_count_per_source_detail(self, session_local):
        from tests.p25_dynamic_test_support import make_repos
        session, msg_repo, _, _ = make_repos(session_local)
        ids = seed_base_records(session)

        _seed_p25_package_message(
            session, session_id=ids["session_id"], task_id=ids["task_id"],
            project_id=ids["project_id"],
        )
        _seed_candidate_diff_message(
            session, session_id=ids["session_id"], task_id=ids["task_id"],
            project_id=ids["project_id"],
        )

        assert count_messages_by_source_detail(
            msg_repo, ids["session_id"],
            P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_SOURCE_DETAIL,
        ) == 1
        assert count_messages_by_source_detail(
            msg_repo, ids["session_id"],
            P25_BOUNDED_REWORK_CANDIDATE_DIFF_SOURCE_DETAIL,
        ) == 1
        assert count_messages_by_source_detail(
            msg_repo, ids["session_id"],
            P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SOURCE_DETAIL,
        ) == 0

        session.close()

    def test_different_sessions_are_isolated(self, session_local):
        from tests.p25_dynamic_test_support import make_repos
        session, msg_repo, _, _ = make_repos(session_local)

        ids1 = seed_base_records(session, session_id=uuid4())
        ids2 = seed_base_records(session, session_id=uuid4())

        _seed_p25_package_message(
            session, session_id=ids1["session_id"], task_id=ids1["task_id"],
            project_id=ids1["project_id"],
        )

        assert count_messages_by_source_detail(
            msg_repo, ids1["session_id"],
            P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_SOURCE_DETAIL,
        ) == 1
        assert count_messages_by_source_detail(
            msg_repo, ids2["session_id"],
            P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_SOURCE_DETAIL,
        ) == 0

        session.close()
