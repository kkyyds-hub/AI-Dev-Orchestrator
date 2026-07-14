"""P24-G Concurrency tests for Claim and Outcome services."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.db_tables import ORMBase
from app.domain.project_director_cross_task_exact_worker_invocation_claim import (
    CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL,
)
from app.domain.project_director_cross_task_exact_worker_invocation_outcome import (
    CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL,
)
from app.domain.run import (
    RunBudgetPressureLevel,
    RunBudgetStrategyAction,
    RunStrategyDecision,
    RunStrategyReasonItem,
)
from app.workers.task_worker import (
    WorkerReservedRunExecutionSnapshot,
    WorkerRunResult,
)

from tests.p24_test_support import (
    ExplodingWorkerAdapter,
    FakeTaskWorker,
    SharedGatedWorkerController,
    build_p24_chain,
    build_worker_result_for_chain,
    count_messages_by_source_detail,
    make_claim_service,
    make_outcome_service,
    make_repos,
    make_session_factory,
    make_test_engine,
    seed_agent_session,
    seed_base_records,
    seed_e1b_message,
    seed_e2a_message,
    seed_full_p24_chain,
    seed_outcome_message,
    seed_package_message,
    seed_root_message,
    seed_run,
)


# ── Helpers ─────────────────────────────────────────────────────────


def _make_file_engine(tmp_path):
    """Create a file-backed SQLite engine with WAL mode."""
    db_path = os.path.join(str(tmp_path), "concurrency_test.db")
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(engine, "connect")
    def _configure_sqlite(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA busy_timeout = 5000")
        cursor.close()

    ORMBase.metadata.create_all(bind=engine)
    return engine


def _seed_full_chain_for_concurrency(session_local, chain):
    """Seed all required records for concurrency tests."""
    s = session_local()
    seed_base_records(
        s,
        session_id=chain.session_id,
        project_id=chain.project_id,
        task_id=chain.next_task_id,
        plan_version_id=chain.plan_version_id,
        task_status="running",
    )
    seed_package_message(s, chain.package)
    seed_root_message(s, chain.root)
    seed_e1b_message(s, chain.exact_run_reservation)
    seed_e2a_message(s, chain.worker_start_reservation)
    seed_run(
        s,
        run_id=chain.exact_run_id,
        task_id=chain.next_task_id,
        model_name=chain.claim.worker_model_name,
        started_at=chain.claim.exact_run_started_at,
        created_at=chain.claim.exact_run_created_at,
        strategy_decision=RunStrategyDecision(
            version="1",
            project_stage=None,
            owner_role_code=chain.claim.worker_owner_role_code,
            model_tier=chain.claim.worker_model_tier,
            model_name=chain.claim.worker_model_name,
            selected_skill_codes=[sk.skill_code for sk in chain.claim.worker_selected_skills],
            selected_skill_names=[sk.skill_name for sk in chain.claim.worker_selected_skills],
            budget_pressure_level=RunBudgetPressureLevel.NORMAL,
            budget_action=RunBudgetStrategyAction.FULL_SPEED,
            strategy_code="normal",
            summary="Normal execution",
            role_model_policy_source="test",
            role_model_policy_desired_tier=chain.claim.worker_model_tier,
            role_model_policy_adjusted_tier=chain.claim.worker_model_tier,
            role_model_policy_final_tier=chain.claim.worker_model_tier,
            role_model_policy_stage_override_applied=False,
            rule_codes=["normal"],
            reasons=[RunStrategyReasonItem(code="normal", label="Normal", detail="Normal", score=1.0)],
        ),
    )
    s.close()


# ── Concurrent Claim Tests ──────────────────────────────────────────


class TestConcurrentClaim:
    """Two threads simultaneously request the same exact Claim."""

    def test_concurrent_claim_exactly_one_created(self, tmp_path):
        """Two concurrent Claim requests → exactly one created, one replayed."""
        engine = _make_file_engine(tmp_path)
        session_local = make_session_factory(engine)
        chain = build_p24_chain()

        _seed_full_chain_for_concurrency(session_local, chain)

        results = [None, None]
        barrier = threading.Barrier(2, timeout=15)

        def claim_worker(index):
            session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
            try:
                claim_svc = make_claim_service(
                    session,
                    msg_repo=msg_repo,
                    task_repo=task_repo,
                    run_repo=run_repo,
                    agent_sess_repo=agent_sess_repo,
                )
                barrier.wait()
                result = claim_svc.claim_exact_worker_invocation(
                    session_id=chain.session_id,
                    project_id=chain.project_id,
                    continuation_root_record_id=chain.root_record_id,
                    instruction_package_id=chain.package_id,
                    exact_run_reservation_id=chain.exact_run_reservation_id,
                    exact_worker_start_reservation_id=chain.worker_start_reservation_id,
                )
                results[index] = result
            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(claim_worker, i) for i in range(2)]
            for f in futures:
                f.result(timeout=30)

        statuses = {results[0].status, results[1].status}
        assert "invocation_claim_created" in statuses
        assert "invocation_claim_replayed" in statuses

        created = results[0] if results[0].status == "invocation_claim_created" else results[1]
        replayed = results[0] if results[0].status == "invocation_claim_replayed" else results[1]

        assert created.automatic_worker_call_allowed is True
        assert replayed.automatic_worker_call_allowed is False

        # Both must have the same Claim identity
        assert created.claim.exact_worker_invocation_claim_id == replayed.claim.exact_worker_invocation_claim_id
        assert created.claim.worker_invocation_claim_token == replayed.claim.worker_invocation_claim_token
        assert created.claim.worker_invocation_claim_fingerprint == replayed.claim.worker_invocation_claim_fingerprint

        # Exactly one Claim Message
        session, msg_repo, *_ = make_repos(session_local)
        assert count_messages_by_source_detail(
            msg_repo, chain.session_id,
            CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL,
        ) == 1


# ── Concurrent E4B Tests ───────────────────────────────────────────


class TestConcurrentE4B:
    """Thread A creates Claim + enters Worker, Thread B sees Claim without Outcome."""

    def test_concurrent_e4b_worker_called_once(self, tmp_path):
        """Thread A calls Worker (blocked), Thread B sees recovery_required."""
        engine = _make_file_engine(tmp_path)
        session_local = make_session_factory(engine)
        chain = build_p24_chain()

        _seed_full_chain_for_concurrency(session_local, chain)

        # Shared gated controller for Thread A's worker
        controller = SharedGatedWorkerController()
        controller.set_result(build_worker_result_for_chain(chain))

        # Thread B's worker must never be called
        exploding_worker = ExplodingWorkerAdapter()

        thread_a_result = [None]
        thread_b_result = [None]
        barrier = threading.Barrier(2, timeout=15)

        def thread_a():
            worker = FakeTaskWorker(session=None)
            worker.run_reserved_once = controller.run_reserved_once
            session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
            try:
                outcome_svc = make_outcome_service(
                    session,
                    msg_repo=msg_repo,
                    task_repo=task_repo,
                    run_repo=run_repo,
                    agent_sess_repo=agent_sess_repo,
                    task_worker=worker,
                )
                barrier.wait()
                result = outcome_svc.invoke_exact_worker(
                    session_id=chain.session_id,
                    project_id=chain.project_id,
                    continuation_root_record_id=chain.root_record_id,
                    instruction_package_id=chain.package_id,
                    exact_run_reservation_id=chain.exact_run_reservation_id,
                    exact_worker_start_reservation_id=chain.worker_start_reservation_id,
                )
                thread_a_result[0] = result
            finally:
                session.close()

        def thread_b():
            session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
            exploding_worker.bind_session(session, task_repo, run_repo, agent_sess_repo)
            try:
                outcome_svc = make_outcome_service(
                    session,
                    msg_repo=msg_repo,
                    task_repo=task_repo,
                    run_repo=run_repo,
                    agent_sess_repo=agent_sess_repo,
                    task_worker=exploding_worker,
                )
                barrier.wait()
                controller.wait_until_entered(timeout=10)
                result = outcome_svc.invoke_exact_worker(
                    session_id=chain.session_id,
                    project_id=chain.project_id,
                    continuation_root_record_id=chain.root_record_id,
                    instruction_package_id=chain.package_id,
                    exact_run_reservation_id=chain.exact_run_reservation_id,
                    exact_worker_start_reservation_id=chain.worker_start_reservation_id,
                )
                thread_b_result[0] = result
                controller.release()
            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            fa = executor.submit(thread_a)
            fb = executor.submit(thread_b)
            fa.result(timeout=30)
            fb.result(timeout=30)

        # Thread A: outcome_recorded
        assert thread_a_result[0].status == "outcome_recorded"
        assert thread_a_result[0].outcome is not None
        assert thread_a_result[0].outcome.status == "returned"
        assert thread_a_result[0].outcome.worker_call_attempted is True
        assert thread_a_result[0].outcome.worker_result_contract_valid is True
        thread_a_claim_id = thread_a_result[0].exact_worker_invocation_claim_id
        thread_a_outcome_id = thread_a_result[0].outcome.exact_worker_invocation_outcome_id
        thread_a_fp = thread_a_result[0].outcome.worker_invocation_outcome_fingerprint

        # Thread B: recovery_required with precise fields
        assert thread_b_result[0].status == "recovery_required"
        assert thread_b_result[0].outcome is None
        assert thread_b_result[0].exact_worker_invocation_claim_id == thread_a_claim_id
        assert thread_b_result[0].worker_call_attempted is None
        assert thread_b_result[0].worker_call_state_indeterminate is True
        assert thread_b_result[0].automatic_worker_call_allowed is False

        # Shared Worker called exactly once
        assert controller.call_count == 1

        # Third call replays Thread A's Outcome
        session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
        third_worker = FakeTaskWorker(session=None)
        outcome_svc = make_outcome_service(
            session,
            msg_repo=msg_repo,
            task_repo=task_repo,
            run_repo=run_repo,
            agent_sess_repo=agent_sess_repo,
            task_worker=third_worker,
        )
        third_result = outcome_svc.invoke_exact_worker(
            session_id=chain.session_id,
            project_id=chain.project_id,
            continuation_root_record_id=chain.root_record_id,
            instruction_package_id=chain.package_id,
            exact_run_reservation_id=chain.exact_run_reservation_id,
            exact_worker_start_reservation_id=chain.worker_start_reservation_id,
        )
        session.close()

        # Third: replay with exact identity
        assert third_result.status == "outcome_replayed"
        assert third_result.outcome is not None
        assert third_result.outcome.exact_worker_invocation_outcome_id == thread_a_outcome_id
        assert third_result.outcome.worker_invocation_outcome_fingerprint == thread_a_fp
        assert third_result.exact_worker_invocation_claim_id == thread_a_claim_id
        assert third_worker.call_count == 0

        # Final database assertions
        session, msg_repo, *_ = make_repos(session_local)
        assert count_messages_by_source_detail(
            msg_repo, chain.session_id,
            CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL,
        ) == 1
        assert count_messages_by_source_detail(
            msg_repo, chain.session_id,
            CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL,
        ) == 1
        # Verify Run count
        from app.core.db_tables import RunTable
        runs = session.query(RunTable).filter(RunTable.task_id == chain.next_task_id).all()
        assert len(runs) == 1
        session.close()

        # Total Worker calls across all threads = 1
        assert controller.call_count == 1
