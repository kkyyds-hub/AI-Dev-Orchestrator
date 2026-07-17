"""Readonly source-authority bridge contracts for P25-H post-review evidence."""

from __future__ import annotations

from app.services.project_director_post_review_source_evidence_resolver import (
    ProjectDirectorPostReviewSourceEvidenceResolver,
)
from tests.p25_post_review_real_chain_test_support import (
    build_real_p25_attempt_zero_post_review_context,
)


def test_resolver_rebuilds_current_p25_h_review_and_p25_g_diff(tmp_path):
    context = build_real_p25_attempt_zero_post_review_context(tmp_path)
    try:
        resolver = ProjectDirectorPostReviewSourceEvidenceResolver(
            review_execution_service=context.review_execution_context.review_execution_service,
        )

        resolved = resolver.resolve(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_review_message_id=context.h_b_result.review_outcome_message.id,
        )

        outcome = context.h_b_result.review_outcome
        assert resolved.blocked_reasons == ()
        assert resolved.source_review_kind == "p25_h"
        assert resolved.source_review_message_id == context.h_b_result.review_outcome_message.id
        assert resolved.source_preflight_message_id == outcome.preflight_id
        assert resolved.source_diff_message_id == outcome.source_candidate_diff_message_id
        assert resolved.source_diff_sha256 == outcome.source_candidate_diff_sha256
        assert resolved.review_result_fingerprint == outcome.review_result_fingerprint
        assert resolved.review_semantic_fingerprint == outcome.review_semantic_fingerprint
        assert resolved.requested_reviewer_executor == outcome.requested_reviewer_executor
        assert resolved.review_prompt_sha256 == outcome.review_prompt_sha256
        assert resolved.review_scope_paths == outcome.review_scope_paths
        assert resolved.review_output_schema_version == outcome.review_output_schema_version
        assert resolved.source_review_verdict == "no_blocking_findings"
        assert resolved.source_review_risk_level == "low"
        assert resolved.exact_task_id == context.task_id
    finally:
        context.close()
