"""P25-H-C real P21-D disposition and P22 post-review regression coverage."""

from __future__ import annotations

from sqlalchemy import select

from app.core.db_tables import TaskTable
from tests.p25_post_review_real_chain_test_support import (
    build_real_p25_attempt_zero_post_review_context,
)


def test_post_review_orchestration_fails_closed_with_caller_owned_transaction(tmp_path):
    context = build_real_p25_attempt_zero_post_review_context(tmp_path)
    try:
        assert context.session.in_transaction() is False
        context.session.begin()
        task = context.session.get(TaskTable, context.task_id)
        assert task is not None
        task.input_summary = "caller-owned P25-H-C pending write"
        context.session.flush()

        result = context.orchestration_service.orchestrate_fresh_post_review(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_review_outcome_message_id=(
                context.h_b_result.review_outcome_message.id
            ),
        )

        assert result.status == "blocked"
        assert result.blocked_reasons == ("history_invalid",)
        assert context.session.in_transaction() is True
        assert context.session.execute(
            select(TaskTable.input_summary).where(TaskTable.id == context.task_id)
        ).scalar_one() == "caller-owned P25-H-C pending write"
    finally:
        if context.session.in_transaction():
            context.session.rollback()
        context.close()


def test_current_p25_h_outcome_creates_exact_p21_d_disposition(tmp_path):
    context = build_real_p25_attempt_zero_post_review_context(tmp_path)
    try:
        result = context.orchestration_service.orchestrate_fresh_post_review(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_review_outcome_message_id=(
                context.h_b_result.review_outcome_message.id
            ),
        )

        assert result.status == "post_review_orchestrated", result.blocked_reasons
        assert result.disposition is not None
        assert result.disposition_message is not None
        assert result.disposition.disposition_status == "computed"
        assert result.disposition.disposition_type == "AUTO_CONTINUE"
        assert result.disposition.source_review_message_id == (
            context.h_b_result.review_outcome_message.id
        )
        assert result.disposition.review_result_fingerprint == (
            context.h_b_result.review_outcome.review_result_fingerprint
        )
    finally:
        context.close()
