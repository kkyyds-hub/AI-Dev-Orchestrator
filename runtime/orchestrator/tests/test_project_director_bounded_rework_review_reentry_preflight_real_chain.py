"""P25-H-A real-chain transaction and replay coverage without reviewer execution."""

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, select

from app.core.db_tables import RunTable, TaskTable
from app.services.project_director_bounded_rework_review_reentry_preflight_service import (
    P25_BOUNDED_REWORK_REVIEW_CLAIM_INTENT,
    P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_INTENT,
)
from tests.p25_review_reentry_preflight_real_chain_test_support import (
    build_fresh_review_preflight_services,
    build_real_p25_attempt_zero_review_preflight_context,
)


def _review_reentry_messages(context):
    session = context.message_repository._session
    caller_had_transaction = session.in_transaction()
    try:
        messages, has_more = context.message_repository.list_by_session_id(
            session_id=context.session_id,
            limit=200,
        )
        assert has_more is False
        return tuple(
            message
            for message in messages
            if message.intent
            in {
                P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_INTENT,
                P25_BOUNDED_REWORK_REVIEW_CLAIM_INTENT,
            }
        )
    finally:
        if not caller_had_transaction and session.in_transaction():
            session.rollback()


def _task_run_counts(session):
    caller_had_transaction = session.in_transaction()
    try:
        return (
            session.scalar(select(func.count()).select_from(TaskTable)),
            session.scalar(select(func.count()).select_from(RunTable)),
        )
    finally:
        if not caller_had_transaction and session.in_transaction():
            session.rollback()


def test_review_preflight_does_not_rollback_caller_owned_transaction(tmp_path):
    context = build_real_p25_attempt_zero_review_preflight_context(tmp_path)
    try:
        assert context.session.in_transaction() is False
        manifest_path = (
            context.environment["workspace_path"]
            / ".ai-project-director/workspace-manifest.json"
        )
        manifest_before = (
            manifest_path.read_bytes(),
            manifest_path.stat().st_ino,
            manifest_path.stat().st_mtime_ns,
        )

        context.session.begin()
        task = context.session.get(TaskTable, context.task_id)
        assert task is not None
        task.input_summary = "caller-owned P25-H-A pending write"
        context.session.flush()

        result = context.review_preflight_service.prepare_review_reentry_preflight_and_claim(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=context.candidate_diff_result.diff_message.id,
        )

        assert result.status == "blocked"
        assert result.blocked_reasons == ("history_invalid",)
        assert context.session.in_transaction() is True
        assert context.session.execute(
            select(TaskTable.input_summary).where(TaskTable.id == context.task_id)
        ).scalar_one() == "caller-owned P25-H-A pending write"
        assert _review_reentry_messages(context) == ()
        assert manifest_before == (
            manifest_path.read_bytes(),
            manifest_path.stat().st_ino,
            manifest_path.stat().st_mtime_ns,
        )
    finally:
        if context.session.in_transaction():
            context.session.rollback()
        context.close()


def test_real_attempt_zero_prepares_review_reentry_preflight_and_claim(tmp_path):
    context = build_real_p25_attempt_zero_review_preflight_context(tmp_path)
    try:
        result = context.review_preflight_service.prepare_review_reentry_preflight_and_claim(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=context.candidate_diff_result.diff_message.id,
        )

        assert result.status == "review_preflight_claimed", result.blocked_reasons
        assert result.blocked_reasons == ()
        assert result.preflight is not None and result.preflight_message is not None
        assert result.review_claim is not None and result.review_claim_message is not None
        preflight, claim = result.preflight, result.review_claim
        candidate = context.candidate_diff_result.candidate_diff
        manifest = context.candidate_diff_result.candidate_manifest
        package = context.candidate_context.outcome_context.claim_context.package_result.package
        reservation = context.candidate_context.outcome_context.claim_context.reservation_result.reservation
        outcome = context.outcome_result.outcome
        invocation_claim = context.outcome_result.claim
        assert candidate is not None and manifest is not None
        assert outcome is not None and invocation_claim is not None
        assert preflight.source_candidate_diff_message_id == context.candidate_diff_result.diff_message.id
        assert preflight.source_candidate_diff_id == candidate.candidate_diff_id
        assert preflight.source_candidate_diff_fingerprint == candidate.candidate_diff_fingerprint
        assert preflight.source_candidate_diff_replay_key == candidate.candidate_diff_replay_key
        assert preflight.source_candidate_diff_sha256 == candidate.new_diff_sha256
        assert preflight.source_candidate_manifest_id == manifest.candidate_manifest_id
        assert preflight.source_candidate_manifest_fingerprint == manifest.candidate_manifest_fingerprint
        assert preflight.source_outcome_id == outcome.outcome_id
        assert preflight.source_claim_id == invocation_claim.claim_id
        assert preflight.source_reservation_id == reservation.reservation_id
        assert preflight.source_package_id == package.package_id
        assert preflight.source_attempt_id == reservation.reservation_id
        assert (preflight.exact_task_id, preflight.exact_run_id) == (
            context.task_id,
            context.candidate_context.outcome_context.claim_context.package_context.run_id,
        )
        assert (preflight.rework_attempt_index, preflight.rework_attempt_limit) == (0, 3)
        assert preflight.base_commit_sha == package.base_commit_sha
        assert preflight.base_snapshot_fingerprint == package.base_snapshot_fingerprint
        assert preflight.workspace_binding_id == package.workspace_binding.workspace_binding_id
        assert preflight.workspace_binding_fingerprint == package.workspace_binding.workspace_binding_fingerprint
        assert preflight.review_scope_paths == ("src/example.py",)
        assert preflight.old_review_message_id == package.authority.source_review_message_id
        assert preflight.old_review_fingerprint == package.authority.source_review_fingerprint
        assert preflight.old_review_semantic_fingerprint == package.authority.source_review_semantic_fingerprint
        assert preflight.source_candidate_diff_message_id != preflight.old_review_source_diff_message_id
        assert preflight.source_candidate_diff_sha256 != preflight.old_review_source_diff_sha256
        assert preflight.requested_reviewer_executor in {"codex", "claude-code"}
        assert preflight.review_prompt_sha256 != preflight.old_review_prompt_sha256
        assert preflight.review_prompt_bytes > 0
        assert preflight.reviewer_attempted is False
        assert preflight.reviewer_started is False
        assert preflight.reviewer_returned is False
        assert preflight.reviewer_raised is False
        assert preflight.review_output_persisted is False
        assert preflight.provider_called is False
        assert claim.preflight_id == preflight.preflight_id
        assert claim.preflight_fingerprint == preflight.preflight_fingerprint
        assert claim.preflight_replay_key == preflight.preflight_replay_key
        assert claim.source_candidate_diff_message_id == preflight.source_candidate_diff_message_id
        assert claim.source_candidate_diff_sha256 == preflight.source_candidate_diff_sha256
        assert claim.source_outcome_id == preflight.source_outcome_id
        assert claim.source_attempt_id == preflight.source_attempt_id
        assert claim.source_package_id == preflight.source_package_id
        assert claim.authority == preflight.authority
        assert claim.exact_task_id == preflight.exact_task_id
        assert claim.exact_run_id == preflight.exact_run_id
        assert (claim.rework_attempt_index, claim.rework_attempt_limit) == (0, 3)
        assert claim.requested_reviewer_executor == preflight.requested_reviewer_executor
        assert claim.review_prompt_sha256 == preflight.review_prompt_sha256
        assert claim.review_prompt_bytes == preflight.review_prompt_bytes
        assert claim.invocation_ordinal == 0
        assert len(claim.review_claim_token) == 64
        assert claim.review_claim_token not in result.review_claim_message.content
        assert claim.reviewer_call_attempted is False
        assert claim.reviewer_started is False
        assert claim.reviewer_returned is False
        assert claim.reviewer_raised is False
        assert claim.review_success_evidence_present is False
        assert claim.provider_called_by_claim is False
        assert _review_reentry_messages(context) == (
            result.preflight_message,
            result.review_claim_message,
        )
    finally:
        context.close()


def test_same_session_review_preflight_replays_exactly(tmp_path):
    context = build_real_p25_attempt_zero_review_preflight_context(tmp_path)
    try:
        first = context.review_preflight_service.prepare_review_reentry_preflight_and_claim(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=context.candidate_diff_result.diff_message.id,
        )
        assert first.status == "review_preflight_claimed", first.blocked_reasons

        replay = context.review_preflight_service.prepare_review_reentry_preflight_and_claim(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=context.candidate_diff_result.diff_message.id,
        )

        assert replay.status == "review_preflight_replayed", replay.blocked_reasons
        assert replay.preflight == first.preflight
        assert replay.preflight_message == first.preflight_message
        assert replay.review_claim == first.review_claim
        assert replay.review_claim_message == first.review_claim_message
        assert _review_reentry_messages(context) == (
            first.preflight_message,
            first.review_claim_message,
        )
    finally:
        context.close()


def test_fresh_session_review_preflight_replays_and_revalidates_claim(tmp_path):
    context = build_real_p25_attempt_zero_review_preflight_context(tmp_path)
    fresh = None
    try:
        first = context.review_preflight_service.prepare_review_reentry_preflight_and_claim(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=context.candidate_diff_result.diff_message.id,
        )
        assert first.status == "review_preflight_claimed", first.blocked_reasons
        assert first.review_claim_message is not None
        context.session.close()
        fresh = build_fresh_review_preflight_services(context)

        replay = fresh.review_preflight_service.prepare_review_reentry_preflight_and_claim(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=context.candidate_diff_result.diff_message.id,
        )
        revalidated = fresh.review_preflight_service.revalidate_persisted_review_reentry_claim_for_execution(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_review_claim_message_id=first.review_claim_message.id,
        )

        assert replay.status == "review_preflight_replayed", replay.blocked_reasons
        assert replay.preflight == first.preflight
        assert replay.preflight_message == first.preflight_message
        assert replay.review_claim == first.review_claim
        assert replay.review_claim_message == first.review_claim_message
        assert revalidated.blocked_reasons == ()
        assert revalidated.preflight == first.preflight
        assert revalidated.review_claim == first.review_claim
        assert revalidated.candidate_manifest == context.candidate_diff_result.candidate_manifest
        assert revalidated.candidate_diff == context.candidate_diff_result.candidate_diff
        assert revalidated.invocation_outcome == context.outcome_result.outcome
        assert revalidated.invocation_claim == context.outcome_result.claim
        assert fresh.session.in_transaction() is False
        assert context.candidate_context.outcome_context.executor.call_count == 1
    finally:
        if fresh is not None:
            fresh.close()
        context.close()


def test_review_claim_persistence_failure_rolls_back_preflight_atomically(tmp_path):
    context = build_real_p25_attempt_zero_review_preflight_context(tmp_path)
    original_create = context.message_repository.create
    try:
        def create_with_claim_failure(message):
            if message.intent == P25_BOUNDED_REWORK_REVIEW_CLAIM_INTENT:
                raise SQLAlchemyError("injected P25-H-A Claim persistence failure")
            return original_create(message)

        context.message_repository.create = create_with_claim_failure
        result = context.review_preflight_service.prepare_review_reentry_preflight_and_claim(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=context.candidate_diff_result.diff_message.id,
        )
        context.message_repository.create = original_create

        assert result.status == "blocked"
        assert result.blocked_reasons == ("persistence_failed",)
        assert _review_reentry_messages(context) == ()
        assert context.session.in_transaction() is False
    finally:
        context.message_repository.create = original_create
        context.close()


def test_workspace_drift_blocks_review_preflight_without_persistence(tmp_path):
    context = build_real_p25_attempt_zero_review_preflight_context(tmp_path)
    try:
        workspace_file = context.environment["workspace_path"] / "src/example.py"
        workspace_file.write_text("workspace drift\n", encoding="utf-8")

        result = context.review_preflight_service.prepare_review_reentry_preflight_and_claim(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=context.candidate_diff_result.diff_message.id,
        )

        assert result.status == "blocked"
        assert result.blocked_reasons == ("workspace_invalid",)
        assert _review_reentry_messages(context) == ()
    finally:
        context.close()


def test_cross_task_candidate_diff_is_blocked_without_persistence(tmp_path):
    context = build_real_p25_attempt_zero_review_preflight_context(tmp_path)
    try:
        result = context.review_preflight_service.prepare_review_reentry_preflight_and_claim(
            session_id=context.session_id,
            source_task_id=context.project_id,
            source_candidate_diff_message_id=context.candidate_diff_result.diff_message.id,
        )

        assert result.status == "blocked"
        assert _review_reentry_messages(context) == ()
        assert context.session.in_transaction() is False
    finally:
        context.close()


def test_review_preflight_does_not_create_task_run_or_review_outcome(tmp_path):
    context = build_real_p25_attempt_zero_review_preflight_context(tmp_path)
    try:
        before_counts = _task_run_counts(context.session)
        result = context.review_preflight_service.prepare_review_reentry_preflight_and_claim(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=context.candidate_diff_result.diff_message.id,
        )
        all_messages, has_more = context.message_repository.list_by_session_id(
            session_id=context.session_id,
            limit=200,
        )
        assert has_more is False

        assert result.status == "review_preflight_claimed", result.blocked_reasons
        assert _task_run_counts(context.session) == before_counts
        assert not any(
            message.intent == "bounded_rework_review_reentry_invocation_outcome"
            for message in all_messages
        )
        assert context.candidate_context.outcome_context.executor.call_count == 1
    finally:
        if context.session.in_transaction():
            context.session.rollback()
        context.close()
