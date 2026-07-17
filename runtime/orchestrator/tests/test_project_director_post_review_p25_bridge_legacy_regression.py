"""Regression coverage for configured P25-H bridge legacy source routing."""

from __future__ import annotations

from app.core.db_tables import ProjectDirectorMessageTable
from app.services.project_director_post_review_source_evidence_resolver import (
    ProjectDirectorPostReviewSourceEvidenceResolver,
)
from app.services.project_director_bounded_rework_review_execution_service import (
    P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT,
)
from tests.p25_post_review_real_chain_test_support import (
    build_real_p25_attempt_zero_post_review_context,
)


def test_valid_p21_c_source_is_classified_as_legacy(tmp_path):
    context = build_real_p25_attempt_zero_post_review_context(tmp_path)
    try:
        resolver = ProjectDirectorPostReviewSourceEvidenceResolver(
            review_execution_service=context.review_execution_context.review_execution_service,
        )
        root_review_message_id = context.review_execution_context.h_a_result.preflight.old_review_message_id

        resolved = resolver.resolve(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_review_message_id=root_review_message_id,
        )

        assert resolved.source_review_kind == "p21_c"
        assert resolved.blocked_reasons == ()
        assert resolved.source_review_message_id == root_review_message_id
        if context.session.in_transaction():
            context.session.rollback()

        result = context.post_review_automation_service.orchestrate_post_review(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_review_message_id=root_review_message_id,
        )
        assert result.result.source_review_message_id == root_review_message_id
        assert result.result.orchestration_status == "ready_for_future_transition"
    finally:
        context.close()


def test_malformed_p25_marker_is_invalid_and_never_falls_back_to_legacy(tmp_path):
    context = build_real_p25_attempt_zero_post_review_context(tmp_path)
    try:
        source_review_message_id = (
            context.review_execution_context.h_a_result.preflight.old_review_message_id
        )
        row = context.session.get(ProjectDirectorMessageTable, source_review_message_id)
        assert row is not None
        row.intent = P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT
        context.session.commit()
        resolver = ProjectDirectorPostReviewSourceEvidenceResolver(
            review_execution_service=context.review_execution_context.review_execution_service,
        )

        resolved = resolver.resolve(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_review_message_id=source_review_message_id,
        )

        assert resolved.source_review_kind == "invalid"
        assert resolved.blocked_reasons == ("p25_h_marker_invalid",)
    finally:
        context.close()
