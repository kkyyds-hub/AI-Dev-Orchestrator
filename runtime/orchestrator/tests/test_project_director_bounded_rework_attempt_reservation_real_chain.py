"""Exact P25-D reservation diagnostics over the committed real P25-B chain."""

from __future__ import annotations

from sqlalchemy import func, select

from app.core.db_tables import ProjectDirectorMessageTable, RunTable, TaskTable
from app.services.project_director_bounded_rework_attempt_reservation_service import (
    P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_INTENT,
)
from app.services.project_director_bounded_rework_package_preparation_service import (
    P25_BOUNDED_REWORK_PACKAGE_INTENT,
)
from app.services.project_director_protected_transition_worker_invocation_service import (
    P23_PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL,
    P23_PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL,
)
from tests.p25_reservation_real_chain_test_support import (
    build_real_p25_attempt_zero_reservation_context,
    rebuild_reservation_service_with_new_session,
)


def _prepare_package(context):
    result = context.package_service.prepare_bounded_rework_instruction_package(
        session_id=context.package_context.session_id,
        source_task_id=context.package_context.task_id,
        source_p23_dispatch_consumption_message_id=(
            context.package_context.source_p23_consumption_message_id
        ),
    )
    assert result.status == "package_prepared", result.blocked_reasons
    assert result.message is not None
    return result


def _count_messages(session, session_id, *, intent=None, source_detail=None):
    statement = select(func.count()).select_from(ProjectDirectorMessageTable).where(
        ProjectDirectorMessageTable.session_id == session_id
    )
    if intent is not None:
        statement = statement.where(ProjectDirectorMessageTable.intent == intent)
    if source_detail is not None:
        statement = statement.where(
            ProjectDirectorMessageTable.source_detail == source_detail
        )
    return session.execute(statement).scalar_one()


def test_real_attempt_zero_reserves_exact_p25_attempt(tmp_path):
    context = build_real_p25_attempt_zero_reservation_context(tmp_path)
    try:
        package = _prepare_package(context)

        result = context.reservation_service.reserve_bounded_rework_attempt(
            session_id=context.package_context.session_id,
            source_task_id=context.package_context.task_id,
            source_package_message_id=package.message.id,
        )

        assert result.status == "reservation_reserved", result.blocked_reasons
        assert result.reservation is not None
        assert result.message is not None
        assert result.reservation.package_id == package.package.package_id
        assert result.reservation.exact_task_id == context.package_context.task_id
        assert result.reservation.exact_run_id == package.package.authority.source_run_id
        assert result.reservation.rework_attempt_index == 0
        assert result.reservation.rework_attempt_limit == 3
        assert context.session.execute(
            select(func.count()).select_from(TaskTable)
        ).scalar_one() == 1
        assert context.session.execute(
            select(func.count()).select_from(RunTable)
        ).scalar_one() == 1
        assert _count_messages(
            context.session,
            context.package_context.session_id,
            intent=P25_BOUNDED_REWORK_PACKAGE_INTENT,
        ) == 1
        assert _count_messages(
            context.session,
            context.package_context.session_id,
            intent=P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_INTENT,
        ) == 1
        assert _count_messages(
            context.session,
            context.package_context.session_id,
            intent="bounded_rework_invocation_claim",
        ) == 0
        assert _count_messages(
            context.session,
            context.package_context.session_id,
            intent="bounded_rework_invocation_outcome",
        ) == 0
        assert _count_messages(
            context.session,
            context.package_context.session_id,
            source_detail=P23_PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL,
        ) == 0
        assert _count_messages(
            context.session,
            context.package_context.session_id,
            source_detail=P23_PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL,
        ) == 0
    finally:
        context.close()


def test_real_attempt_zero_reservation_replays_with_new_session(tmp_path):
    context = build_real_p25_attempt_zero_reservation_context(tmp_path)
    replay_session = None
    try:
        package = _prepare_package(context)
        first = context.reservation_service.reserve_bounded_rework_attempt(
            session_id=context.package_context.session_id,
            source_task_id=context.package_context.task_id,
            source_package_message_id=package.message.id,
        )
        assert first.status == "reservation_reserved", first.blocked_reasons
        assert first.reservation is not None and first.message is not None
        context.session.close()

        replay_session, replay_service, _ = rebuild_reservation_service_with_new_session(
            context
        )
        replay = replay_service.reserve_bounded_rework_attempt(
            session_id=context.package_context.session_id,
            source_task_id=context.package_context.task_id,
            source_package_message_id=package.message.id,
        )

        assert replay.status == "reservation_replayed", replay.blocked_reasons
        assert replay.reservation is not None and replay.message is not None
        assert replay.reservation.reservation_id == first.reservation.reservation_id
        assert replay.message.id == first.message.id
        assert _count_messages(
            replay_session,
            context.package_context.session_id,
            intent=P25_BOUNDED_REWORK_PACKAGE_INTENT,
        ) == 1
        assert _count_messages(
            replay_session,
            context.package_context.session_id,
            intent=P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_INTENT,
        ) == 1
    finally:
        if replay_session is not None:
            replay_session.close()
        context.close()


def test_reservation_releases_only_service_owned_read_autobegin(tmp_path):
    context = build_real_p25_attempt_zero_reservation_context(tmp_path)
    try:
        package = _prepare_package(context)
        assert context.session.in_transaction() is False
        result = context.reservation_service.reserve_bounded_rework_attempt(
            session_id=context.package_context.session_id,
            source_task_id=context.package_context.task_id,
            source_package_message_id=package.message.id,
        )
        assert result.status == "reservation_reserved", result.blocked_reasons
    finally:
        context.close()


def test_reservation_does_not_rollback_caller_owned_transaction(tmp_path):
    context = build_real_p25_attempt_zero_reservation_context(tmp_path)
    try:
        package = _prepare_package(context)
        context.session.begin()
        task = context.session.get(TaskTable, context.package_context.task_id)
        assert task is not None
        task.input_summary = "caller-owned reservation pending write"
        context.session.flush()

        result = context.reservation_service.reserve_bounded_rework_attempt(
            session_id=context.package_context.session_id,
            source_task_id=context.package_context.task_id,
            source_package_message_id=package.message.id,
        )

        assert result.status == "blocked"
        assert result.blocked_reasons == ("history_invalid",)
        assert context.session.in_transaction() is True
        assert context.session.execute(
            select(TaskTable.input_summary).where(
                TaskTable.id == context.package_context.task_id
            )
        ).scalar_one() == "caller-owned reservation pending write"
        assert _count_messages(
            context.session,
            context.package_context.session_id,
            intent=P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_INTENT,
        ) == 0
    finally:
        if context.session.in_transaction():
            context.session.rollback()
        context.close()
