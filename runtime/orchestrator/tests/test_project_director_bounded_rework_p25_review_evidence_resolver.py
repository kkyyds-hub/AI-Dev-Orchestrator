"""P25-H readonly review evidence compatibility coverage."""

from __future__ import annotations

from app.services.project_director_bounded_rework_review_outcome_evidence_adapter import (
    ProjectDirectorBoundedReworkReviewOutcomeEvidenceAdapter,
)
from tests.p25_real_chain_test_support import (
    build_real_p25_attempt_zero_through_review_outcome,
)
from tests.test_project_director_bounded_rework_p23_handoff_dynamic import (
    _prepare_scenario,
)
from tests.p23_test_support import make_session_factory, make_test_engine


def test_p25_h_adapter_accepts_validated_outcome_message(tmp_path):
    """A fresh P25-H validated Outcome is recognized as current review evidence."""
    engine = make_test_engine(str(tmp_path / "p25-h-adapter.db"))
    scenario = _prepare_scenario(make_session_factory(engine), target_index=1)

    result = ProjectDirectorBoundedReworkReviewOutcomeEvidenceAdapter(
        message_repository=scenario.msg_repo
    ).load_validated_outcome(
        session_id=scenario.ids["session_id"],
        project_id=scenario.ids["project_id"],
        source_task_id=scenario.ids["task_id"],
        source_review_outcome_message_id=scenario.latest.outcome_message.id,
    )

    assert result.outcome is not None, result.blocked_reasons
    assert result.outcome.review_outcome_id == scenario.latest.outcome_message.id
    assert result.outcome.outcome_status == "validated_output"
    assert result.outcome.adapter_result is not None
    assert result.outcome.adapter_result.adapter_status == "validated_output"

    scenario.session.close()
    engine.dispose()


def test_resolver_accepts_real_persisted_p25_h_outcome(tmp_path):
    """Current P25-H evidence and immutable P21-C root stay distinct."""
    chain = build_real_p25_attempt_zero_through_review_outcome(tmp_path)

    resolution = chain.evidence_resolver.resolve_bounded_rework_evidence_snapshot(
        session_id=chain.session_id,
        project_id=chain.project_id,
        source_task_id=chain.task_id,
        source_run_id=chain.run_id,
        source_review_message_id=chain.p25_review_outcome_message_id,
        source_review_fingerprint=chain.p25_review_outcome.review_result_fingerprint,
        source_review_semantic_fingerprint=(
            chain.p25_review_outcome.review_semantic_fingerprint
        ),
        source_freshness_message_id=chain.p25_freshness_message_id,
        source_diff_message_id=chain.p25_candidate_diff_message_id,
    )

    assert resolution.snapshot is not None, resolution.blocked_reasons
    assert resolution.snapshot.source_review_message_id == chain.p25_review_outcome_message_id
    assert resolution.snapshot.root_review_message_id == chain.root_p21c_review_message_id
    assert resolution.snapshot.source_candidate_diff_message_id == chain.p25_candidate_diff_message_id
    assert resolution.snapshot.review_output.findings

    chain.close()
