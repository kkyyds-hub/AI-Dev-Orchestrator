"""Exact P25-B package-stage diagnostics over a real attempt-zero chain."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from app.core.db_tables import TaskTable
from app.domain._base import utc_now
from tests.p25_package_real_chain_test_support import (
    RealP25AttemptZeroPackageContext,
    build_real_p25_attempt_zero_package_context,
)


def _context(tmp_path) -> RealP25AttemptZeroPackageContext:
    return build_real_p25_attempt_zero_package_context(tmp_path)


def test_real_attempt_zero_p25_package_internal_stages(tmp_path):
    """All P25-B inputs revalidate before its one package persistence write."""
    context = _context(tmp_path)
    package_service = context.package_service
    try:
        assert context.msg_repo._session.in_transaction() is False
        authority = package_service._revalidate_authority(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_consumption_message_id=context.source_p23_consumption_message_id,
        )
        assert context.msg_repo._session.in_transaction() is True
        assert authority.rework_attempt_index == 0
        assert authority.rework_attempt_limit == 3
        assert authority.authority.source_run_id == context.run_id

        context.msg_repo._session.rollback()
        assert context.msg_repo._session.in_transaction() is False
        initial = context.evidence_resolver.resolve_bounded_rework_evidence_snapshot(
            session_id=context.session_id,
            project_id=context.project_id,
            source_task_id=context.task_id,
            source_run_id=authority.authority.source_run_id,
            source_review_message_id=authority.authority.source_review_message_id,
            source_review_fingerprint=authority.authority.source_review_fingerprint,
            source_review_semantic_fingerprint=(
                authority.authority.source_review_semantic_fingerprint
            ),
            source_freshness_message_id=authority.source_freshness_message_id,
            source_diff_message_id=authority.source_diff_message_id,
        )
        assert initial.snapshot is not None, initial.blocked_reasons
        assert context.msg_repo._session.in_transaction() is False

        with context.msg_repo.sqlite_immediate_transaction():
            history = package_service._load_history(context.session_id)
            assert len(history.packages) == 0
            assert len(history.reservations) == 0
            assert len(history.claims) == 0
            assert len(history.outcomes) == 0

            current_authority = package_service._revalidate_authority(
                session_id=context.session_id,
                source_task_id=context.task_id,
                source_consumption_message_id=(
                    context.source_p23_consumption_message_id
                ),
            )
            assert current_authority == authority
            current = context.evidence_resolver.revalidate_bounded_rework_evidence_snapshot(
                initial.snapshot
            )
            assert current.snapshot == initial.snapshot, current.blocked_reasons
            snapshot = current.snapshot
            assert snapshot is not None
            allowed_scope = package_service._intersect_scope_sources(
                snapshot.task_plan_allowed_paths,
                snapshot.repository_allowed_paths,
                snapshot.workspace_manifest_allowed_paths,
                snapshot.review_scope_paths,
            )
            findings, corrections = package_service._findings_and_corrections(
                evidence=snapshot,
                allowed_scope=allowed_scope,
            )
            lineage = package_service._attempt_lineage(
                history=history,
                authority_context=current_authority,
                evidence=snapshot,
            )
            assert lineage.rework_attempt_index == 0
            assert lineage.previous_attempt_id is None
            package = package_service._build_package(
                package_id=uuid4(),
                created_at=utc_now(),
                authority=current_authority.authority,
                evidence=snapshot,
                allowed_scope=allowed_scope,
                forbidden_scope=snapshot.trusted_forbidden_paths,
                findings=findings,
                corrections=corrections,
                lineage=lineage,
            )
            assert package.rework_attempt_index == 0
            assert package.authority == authority.authority
    finally:
        context.close()


def test_real_attempt_zero_prepares_p25_package(tmp_path):
    """The public P25-B API persists and then replays one exact package."""
    context = _context(tmp_path)
    try:
        first = context.package_service.prepare_bounded_rework_instruction_package(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_p23_dispatch_consumption_message_id=(
                context.source_p23_consumption_message_id
            ),
        )
        assert first.status == "package_prepared", first.blocked_reasons
        assert first.message is not None
        assert first.package.rework_attempt_index == 0
        assert len(first.package.blocking_findings) == 1

        replay = context.package_service.prepare_bounded_rework_instruction_package(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_p23_dispatch_consumption_message_id=(
                context.source_p23_consumption_message_id
            ),
        )
        assert replay.status == "package_replayed", replay.blocked_reasons
        assert replay.message is not None
        assert replay.message.id == first.message.id
        assert replay.package == first.package
        assert len(replay.package.blocking_findings) == 1
    finally:
        context.close()


def test_package_preparation_does_not_rollback_caller_owned_transaction(tmp_path):
    """An active caller transaction is rejected without losing its pending write."""
    context = _context(tmp_path)
    try:
        context.session.begin()
        caller_owned_task = context.session.get(TaskTable, context.task_id)
        assert caller_owned_task is not None
        caller_owned_task.input_summary = "caller-owned pending write"
        context.session.flush()

        result = context.package_service.prepare_bounded_rework_instruction_package(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_p23_dispatch_consumption_message_id=(
                context.source_p23_consumption_message_id
            ),
        )

        assert result.status == "blocked"
        assert result.blocked_reasons == ("history_invalid",)
        assert context.session.in_transaction() is True
        persisted_value = context.session.execute(
            select(TaskTable.input_summary).where(TaskTable.id == context.task_id)
        ).scalar_one()
        assert persisted_value == "caller-owned pending write"
    finally:
        if context.session.in_transaction():
            context.session.rollback()
        context.close()
