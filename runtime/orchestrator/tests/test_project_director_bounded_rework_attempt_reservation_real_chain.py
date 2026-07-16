"""Independent real-chain checks for P25-D bounded rework reservation."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select

from app.core.db_tables import RunTable, TaskTable
from app.domain.project_role import ProjectRoleCode
from app.domain.task import Task
from app.services.project_director_bounded_rework_attempt_reservation_service import (
    P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_SOURCE_DETAIL,
)
from tests.p25_package_real_chain_test_support import (
    RealP25AttemptZeroPackageContext,
    build_real_p25_attempt_zero_package_context,
)
from tests.p25_reservation_real_chain_test_support import (
    build_fresh_reservation_services,
    build_reservation_service_from_context,
)


def _context(tmp_path) -> RealP25AttemptZeroPackageContext:
    return build_real_p25_attempt_zero_package_context(tmp_path)


def _prepare_package(context: RealP25AttemptZeroPackageContext):
    result = context.package_service.prepare_bounded_rework_instruction_package(
        session_id=context.session_id,
        source_task_id=context.task_id,
        source_p23_dispatch_consumption_message_id=(
            context.source_p23_consumption_message_id
        ),
    )
    assert result.status == "package_prepared", result.blocked_reasons
    assert result.blocked_reasons == ()
    assert result.message is not None
    assert result.package.rework_attempt_index == 0
    assert result.package.rework_attempt_limit == 3
    assert context.session.in_transaction() is False
    return result


def _p25_counts(package_service, session_id):
    session = package_service._message_repository._session
    caller_had_transaction = session.in_transaction()
    try:
        history = package_service._load_history(session_id)
        return (
            len(history.packages),
            len(history.reservations),
            len(history.claims),
            len(history.outcomes),
        )
    finally:
        if not caller_had_transaction and session.in_transaction():
            session.rollback()


def _task_and_run_counts(session):
    caller_had_transaction = session.in_transaction()
    try:
        return (
            session.scalar(select(func.count()).select_from(TaskTable)),
            session.scalar(select(func.count()).select_from(RunTable)),
        )
    finally:
        if not caller_had_transaction and session.in_transaction():
            session.rollback()


def _reservation_count(context: RealP25AttemptZeroPackageContext) -> int:
    caller_had_transaction = context.session.in_transaction()
    try:
        messages, _ = context.msg_repo.list_by_session_id(
            session_id=context.session_id,
            limit=200,
        )
        return sum(
            message.source_detail
            == P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_SOURCE_DETAIL
            for message in messages
        )
    finally:
        if not caller_had_transaction and context.session.in_transaction():
            context.session.rollback()


def test_real_attempt_zero_reserves_exact_p25_attempt(tmp_path):
    context = _context(tmp_path)
    try:
        package_result = _prepare_package(context)
        before_task_run_counts = _task_and_run_counts(context.session)
        reservation_service = build_reservation_service_from_context(context)

        result = reservation_service.reserve_bounded_rework_attempt(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_package_message_id=package_result.message.id,
        )

        assert result.status == "reservation_reserved", result.blocked_reasons
        assert result.blocked_reasons == ()
        assert result.reservation is not None
        assert result.message is not None
        assert result.reservation.package_id == package_result.package.package_id
        assert result.reservation.exact_task_id == context.task_id
        assert result.reservation.exact_run_id == package_result.package.authority.source_run_id
        assert result.reservation.rework_attempt_index == 0
        assert result.reservation.rework_attempt_limit == 3
        assert result.reservation.authority == package_result.package.authority
        assert context.session.in_transaction() is False
        assert _task_and_run_counts(context.session) == before_task_run_counts
        assert _p25_counts(context.package_service, context.session_id) == (1, 1, 0, 0)
    finally:
        context.close()


def test_real_attempt_zero_reservation_replays_exactly(tmp_path):
    context = _context(tmp_path)
    try:
        package_result = _prepare_package(context)
        reservation_service = build_reservation_service_from_context(context)
        first = reservation_service.reserve_bounded_rework_attempt(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_package_message_id=package_result.message.id,
        )
        replay = reservation_service.reserve_bounded_rework_attempt(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_package_message_id=package_result.message.id,
        )

        assert first.status == "reservation_reserved", first.blocked_reasons
        assert first.reservation is not None
        assert first.message is not None
        assert replay.status == "reservation_replayed", replay.blocked_reasons
        assert replay.reservation == first.reservation
        assert replay.message is not None
        assert replay.message.id == first.message.id
        assert context.session.in_transaction() is False
        assert _reservation_count(context) == 1
        assert _p25_counts(context.package_service, context.session_id) == (1, 1, 0, 0)
    finally:
        context.close()


def test_real_attempt_zero_reservation_replays_with_fresh_session(tmp_path):
    context = _context(tmp_path)
    fresh_services = None
    try:
        package_result = _prepare_package(context)
        first = build_reservation_service_from_context(context).reserve_bounded_rework_attempt(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_package_message_id=package_result.message.id,
        )
        assert first.status == "reservation_reserved", first.blocked_reasons
        assert first.reservation is not None
        assert first.message is not None

        context.session.close()
        fresh_services = build_fresh_reservation_services(context)
        replay = fresh_services.reservation_service.reserve_bounded_rework_attempt(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_package_message_id=package_result.message.id,
        )

        assert replay.status == "reservation_replayed", replay.blocked_reasons
        assert replay.reservation == first.reservation
        assert replay.message is not None
        assert replay.message.id == first.message.id
        assert replay.reservation.package_id == package_result.package.package_id
        assert fresh_services.session.in_transaction() is False
        assert _p25_counts(fresh_services.package_service, context.session_id) == (
            1,
            1,
            0,
            0,
        )
    finally:
        if fresh_services is not None:
            fresh_services.close()
        context.close()


def test_reservation_does_not_rollback_caller_owned_transaction(tmp_path):
    context = _context(tmp_path)
    try:
        package_result = _prepare_package(context)
        reservation_service = build_reservation_service_from_context(context)
        assert _p25_counts(context.package_service, context.session_id) == (1, 0, 0, 0)

        context.session.begin()
        caller_owned_task = context.session.get(TaskTable, context.task_id)
        assert caller_owned_task is not None
        caller_owned_task.input_summary = "caller-owned reservation pending write"
        context.session.flush()

        result = reservation_service.reserve_bounded_rework_attempt(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_package_message_id=package_result.message.id,
        )

        assert result.status == "blocked"
        assert result.blocked_reasons == ("history_invalid",)
        assert context.session.in_transaction() is True
        persisted_value = context.session.execute(
            select(TaskTable.input_summary).where(TaskTable.id == context.task_id)
        ).scalar_one()
        assert persisted_value == "caller-owned reservation pending write"
        assert _p25_counts(context.package_service, context.session_id) == (1, 0, 0, 0)
        assert _reservation_count(context) == 0
    finally:
        if context.session.in_transaction():
            context.session.rollback()
        context.close()


def test_reservation_releases_owned_read_transaction_when_preflight_blocks(tmp_path):
    context = _context(tmp_path)
    try:
        _prepare_package(context)
        reservation_service = build_reservation_service_from_context(context)

        result = reservation_service.reserve_bounded_rework_attempt(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_package_message_id=uuid4(),
        )

        assert result.status == "blocked"
        assert result.reservation is None
        assert result.message is None
        assert context.session.in_transaction() is False
        assert _reservation_count(context) == 0
        assert context.session.in_transaction() is False
        assert _p25_counts(context.package_service, context.session_id) == (1, 0, 0, 0)
    finally:
        context.close()


def test_reservation_rejects_cross_task_package_without_persistence(tmp_path):
    context = _context(tmp_path)
    try:
        package_result = _prepare_package(context)
        reservation_service = build_reservation_service_from_context(context)
        task_repository = reservation_service._task_repository
        other_task = task_repository.create(
            Task(
                project_id=context.project_id,
                title="Independent task for cross-task P25-D rejection",
                input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
                acceptance_criteria=["safe_dry_run_task=true"],
                owner_role_code=ProjectRoleCode.ARCHITECT,
            )
        )
        # TaskRepository.create() commits the new Task, then refreshes it.
        # Release that setup read transaction so this is an idle-caller check.
        if context.session.in_transaction():
            context.session.rollback()
        assert context.session.in_transaction() is False
        before_task_run_counts = _task_and_run_counts(context.session)

        result = reservation_service.reserve_bounded_rework_attempt(
            session_id=context.session_id,
            source_task_id=other_task.id,
            source_package_message_id=package_result.message.id,
        )

        assert result.status == "blocked"
        assert result.reservation is None
        assert result.message is None
        assert context.session.in_transaction() is False
        assert _reservation_count(context) == 0
        assert _task_and_run_counts(context.session) == before_task_run_counts
        assert _p25_counts(context.package_service, context.session_id) == (1, 0, 0, 0)
        assert context.session.in_transaction() is False
    finally:
        context.close()
