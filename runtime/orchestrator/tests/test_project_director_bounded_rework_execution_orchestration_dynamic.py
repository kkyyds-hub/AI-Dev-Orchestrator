"""Dynamic tests for the dedicated P25 bounded rework execution coordinator."""

from __future__ import annotations

from app.services.project_director_bounded_rework_attempt_reservation_service import (
    P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_SOURCE_DETAIL,
)
from app.services.project_director_bounded_rework_invocation_claim_service import (
    P25_BOUNDED_REWORK_INVOCATION_CLAIM_SOURCE_DETAIL,
)
from app.services.project_director_bounded_rework_invocation_outcome_service import (
    P25_BOUNDED_REWORK_INVOCATION_OUTCOME_SOURCE_DETAIL,
)
from tests.p23_test_support import (
    count_messages_by_source_detail,
    make_p25_auto_rework_d3_stack,
    make_session_factory,
    make_test_engine,
)


P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_SOURCE_DETAIL = (
    "p25_b_bounded_rework_instruction_package_prepared"
)


def test_real_p25_execution_coordinator_persists_exact_outcome(tmp_path):
    """The coordinator creates one real P25 B-to-F lineage without new Task/Run."""
    engine = make_test_engine(str(tmp_path / "test.db"))
    ctx = make_p25_auto_rework_d3_stack(
        make_session_factory(engine),
        tmp_path=tmp_path,
    )

    result = ctx["p25_execution_svc"].execute_bounded_rework_from_consumption(
        session_id=ctx["session_id"],
        source_task_id=ctx["task_id"],
        source_p23_dispatch_consumption_message_id=ctx["consumption_message_id"],
    )

    assert result.status == "outcome_recorded", result.blocked_reasons
    assert result.package is not None
    assert result.reservation is not None
    assert result.claim is not None
    assert result.outcome is not None
    assert result.package.authority.target_task_id == ctx["task_id"]
    assert result.package.authority.source_run_id == ctx["run_id"]
    assert ctx["fake_bounded_executor"].calls == 1
    assert len(ctx["task_repo"].list_by_project_id(ctx["project_id"])) == 1
    assert len(ctx["run_repo"].list_by_task_id(ctx["task_id"])) == 1
    assert result.outcome.product_runtime_git_write_allowed is False
    assert result.outcome.main_project_write_allowed is False
    assert result.outcome.patch_apply_allowed is False
    for source_detail in (
        P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_SOURCE_DETAIL,
        P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_SOURCE_DETAIL,
        P25_BOUNDED_REWORK_INVOCATION_CLAIM_SOURCE_DETAIL,
        P25_BOUNDED_REWORK_INVOCATION_OUTCOME_SOURCE_DETAIL,
    ):
        assert count_messages_by_source_detail(
            ctx["msg_repo"], ctx["session_id"], source_detail
        ) == 1

    engine.dispose()


def test_real_p25_execution_coordinator_replays_without_executor_recall(tmp_path):
    """A second coordinator instance reuses durable P25 evidence exactly once."""
    engine = make_test_engine(str(tmp_path / "test.db"))
    ctx = make_p25_auto_rework_d3_stack(
        make_session_factory(engine),
        tmp_path=tmp_path,
    )

    first = ctx["p25_execution_svc"].execute_bounded_rework_from_consumption(
        session_id=ctx["session_id"],
        source_task_id=ctx["task_id"],
        source_p23_dispatch_consumption_message_id=ctx["consumption_message_id"],
    )
    replay = ctx["make_p25_execution_service"]().execute_bounded_rework_from_consumption(
        session_id=ctx["session_id"],
        source_task_id=ctx["task_id"],
        source_p23_dispatch_consumption_message_id=ctx["consumption_message_id"],
    )

    assert first.status == "outcome_recorded", first.blocked_reasons
    assert replay.status == "outcome_replayed"
    assert replay.package_message.id == first.package_message.id
    assert replay.reservation_message.id == first.reservation_message.id
    assert replay.claim_message.id == first.claim_message.id
    assert replay.outcome_message.id == first.outcome_message.id
    assert ctx["fake_bounded_executor"].calls == 1
    for source_detail in (
        P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_SOURCE_DETAIL,
        P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_SOURCE_DETAIL,
        P25_BOUNDED_REWORK_INVOCATION_CLAIM_SOURCE_DETAIL,
        P25_BOUNDED_REWORK_INVOCATION_OUTCOME_SOURCE_DETAIL,
    ):
        assert count_messages_by_source_detail(
            ctx["msg_repo"], ctx["session_id"], source_detail
        ) == 1

    engine.dispose()
