"""Concurrency tests for P23 protected transition exact-once guarantees.

Each thread creates its own SQLAlchemy Session and service stack.
Threads share only the SQLite file, threading.Barrier, and read-only UUIDs.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4

import pytest

from app.core.db_tables import AgentSessionTable
from app.domain.task import TaskStatus
from app.domain.run import RunStatus
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.project_director_protected_transition_dispatch_consumption_preflight_service import (
    ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService,
)
from app.services.project_director_protected_transition_dispatch_consumption_service import (
    ProjectDirectorProtectedTransitionDispatchConsumptionService,
)
from app.services.project_director_protected_transition_dispatch_intent_service import (
    ProjectDirectorProtectedTransitionDispatchIntentService,
)
from app.services.project_director_protected_transition_worker_invocation_service import (
    ProjectDirectorProtectedTransitionWorkerInvocationService,
)
from app.services.project_director_protected_transition_worker_start_reservation_service import (
    ProjectDirectorProtectedTransitionWorkerStartReservationService,
)
from app.services.project_director_protected_transition_auto_advance_service import (
    ProjectDirectorProtectedTransitionAutoAdvanceService,
)
from app.services.project_director_protected_transition_evidence_freshness_service import (
    ProjectDirectorProtectedTransitionEvidenceFreshnessService,
)
from app.workers.task_worker import WorkerRunResult, WorkerReservedRunExecutionSnapshot
from tests.p23_test_support import (
    DIFF_SHA256,
    _StubHandoff,
    _StubDiff,
    FakeBudgetGuardService,
    FakeTaskReadinessService,
    FakeTaskStateMachineService,
    FakeTaskRouterService,
    FakeTaskWorker,
    make_d3_worker_result,
    make_repos,
    make_session_factory,
    make_test_engine,
    seed_base_records,
    count_messages_by_source_detail,
    count_p23_evidence,
    _make_p22_service,
    _seed_p21_c_review_chain,
    P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL,
    P23_PROTECTED_TRANSITION_WORKER_START_RESERVATION_SOURCE_DETAIL,
    P23_PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL,
    P23_PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL,
)


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════


def _make_independent_stack(sf, *, session_id, task_id, project_id, fake_worker=None):
    """Create an independent service stack with its own Session."""
    session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(sf)

    freshness_svc = ProjectDirectorProtectedTransitionEvidenceFreshnessService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        review_handoff_service=_StubHandoff(),
        candidate_diff_service=_StubDiff(),
    )

    intent_svc = ProjectDirectorProtectedTransitionDispatchIntentService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
    )

    preflight_svc = ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        dispatch_intent_service=intent_svc,
        freshness_service=freshness_svc,
        task_readiness_service=FakeTaskReadinessService(),
        task_state_machine_service=FakeTaskStateMachineService(),
        budget_guard_service=FakeBudgetGuardService(session=session),
    )

    d1_svc = ProjectDirectorProtectedTransitionDispatchConsumptionService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        run_repository=run_repo,
        preflight_service=preflight_svc,
        task_readiness_service=FakeTaskReadinessService(),
        task_state_machine_service=FakeTaskStateMachineService(),
        task_router_service=FakeTaskRouterService(),
        budget_guard_service=FakeBudgetGuardService(session=session),
    )

    b1_svc = ProjectDirectorProtectedTransitionWorkerStartReservationService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        run_repository=run_repo,
        agent_session_repository=agent_sess_repo,
        dispatch_consumption_service=d1_svc,
        freshness_service=freshness_svc,
        budget_guard_service=FakeBudgetGuardService(session=session),
    )

    if fake_worker is None:
        fake_worker = FakeTaskWorker(session=session)
    else:
        fake_worker.session = session

    b2_svc = ProjectDirectorProtectedTransitionWorkerInvocationService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        run_repository=run_repo,
        agent_session_repository=agent_sess_repo,
        worker_start_reservation_service=b1_svc,
        freshness_service=freshness_svc,
        task_worker=fake_worker,
    )

    d3_svc = ProjectDirectorProtectedTransitionAutoAdvanceService(
        post_review_automation_service=_make_p22_service(session, msg_repo, sess_repo, task_repo),
        dispatch_intent_service=intent_svc,
        dispatch_consumption_preflight_service=preflight_svc,
        dispatch_consumption_service=d1_svc,
        worker_start_reservation_service=b1_svc,
        worker_invocation_service=b2_svc,
    )

    return {
        "session": session,
        "msg_repo": msg_repo,
        "sess_repo": sess_repo,
        "task_repo": task_repo,
        "run_repo": run_repo,
        "agent_sess_repo": agent_sess_repo,
        "freshness_svc": freshness_svc,
        "intent_svc": intent_svc,
        "preflight_svc": preflight_svc,
        "d1_svc": d1_svc,
        "b1_svc": b1_svc,
        "b2_svc": b2_svc,
        "d3_svc": d3_svc,
        "fake_worker": fake_worker,
    }


def _prepare_through_preflight(sf, *, session_id, task_id, project_id):
    """Run P22 → P23-B → P23-C and return the preflight message ID."""
    session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(sf)
    p22_svc = _make_p22_service(session, msg_repo, sess_repo, task_repo)
    freshness_svc = ProjectDirectorProtectedTransitionEvidenceFreshnessService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        review_handoff_service=_StubHandoff(),
        candidate_diff_service=_StubDiff(),
    )
    intent_svc = ProjectDirectorProtectedTransitionDispatchIntentService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
    )
    preflight_svc = ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        dispatch_intent_service=intent_svc,
        freshness_service=freshness_svc,
        task_readiness_service=FakeTaskReadinessService(),
        task_state_machine_service=FakeTaskStateMachineService(),
        budget_guard_service=FakeBudgetGuardService(session=session),
    )

    # Find the review message
    review_msgs = [
        m for m in msg_repo.list_by_session_id(session_id=session_id, limit=200)[0]
        if m.intent == "sandbox_candidate_diff_readonly_review_execution"
    ]
    review_msg_id = review_msgs[0].id

    if session.in_transaction():
        session.rollback()
    p22 = p22_svc.orchestrate_post_review(
        session_id=session_id, source_task_id=task_id, source_review_message_id=review_msg_id,
    )
    intent = intent_svc.prepare_protected_transition_dispatch_intent(
        session_id=session_id, source_task_id=task_id, source_message_id=p22.message.id,
    )
    pf = preflight_svc.prepare_protected_transition_dispatch_consumption_preflight(
        session_id=session_id, source_task_id=task_id, source_message_id=intent.message.id,
    )
    preflight_msg_id = pf.message.id
    session.close()
    return preflight_msg_id


def _prepare_through_d1(sf, *, session_id, task_id, project_id):
    """Run P22 → P23-B → P23-C → D1 and return (d1_msg_id, run_id)."""
    session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(sf)
    p22_svc = _make_p22_service(session, msg_repo, sess_repo, task_repo)
    freshness_svc = ProjectDirectorProtectedTransitionEvidenceFreshnessService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        review_handoff_service=_StubHandoff(),
        candidate_diff_service=_StubDiff(),
    )
    intent_svc = ProjectDirectorProtectedTransitionDispatchIntentService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
    )
    preflight_svc = ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        dispatch_intent_service=intent_svc,
        freshness_service=freshness_svc,
        task_readiness_service=FakeTaskReadinessService(),
        task_state_machine_service=FakeTaskStateMachineService(),
        budget_guard_service=FakeBudgetGuardService(session=session),
    )
    d1_svc = ProjectDirectorProtectedTransitionDispatchConsumptionService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        run_repository=run_repo,
        preflight_service=preflight_svc,
        task_readiness_service=FakeTaskReadinessService(),
        task_state_machine_service=FakeTaskStateMachineService(),
        task_router_service=FakeTaskRouterService(),
        budget_guard_service=FakeBudgetGuardService(session=session),
    )

    review_msgs = [
        m for m in msg_repo.list_by_session_id(session_id=session_id, limit=200)[0]
        if m.intent == "sandbox_candidate_diff_readonly_review_execution"
    ]
    review_msg_id = review_msgs[0].id

    if session.in_transaction():
        session.rollback()
    p22 = p22_svc.orchestrate_post_review(
        session_id=session_id, source_task_id=task_id, source_review_message_id=review_msg_id,
    )
    intent = intent_svc.prepare_protected_transition_dispatch_intent(
        session_id=session_id, source_task_id=task_id, source_message_id=p22.message.id,
    )
    pf = preflight_svc.prepare_protected_transition_dispatch_consumption_preflight(
        session_id=session_id, source_task_id=task_id, source_message_id=intent.message.id,
    )
    d1 = d1_svc.consume_protected_transition_dispatch_preflight(
        session_id=session_id, source_task_id=task_id, source_message_id=pf.message.id,
    )
    d1_msg_id = d1.message.id
    run_id = d1.result.run_id
    session.close()
    return d1_msg_id, run_id


def _prepare_through_b1(sf, *, session_id, task_id, project_id):
    """Run full chain through B1 and return (b1_msg_id, run_id)."""
    session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(sf)
    p22_svc = _make_p22_service(session, msg_repo, sess_repo, task_repo)
    freshness_svc = ProjectDirectorProtectedTransitionEvidenceFreshnessService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        review_handoff_service=_StubHandoff(),
        candidate_diff_service=_StubDiff(),
    )
    intent_svc = ProjectDirectorProtectedTransitionDispatchIntentService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
    )
    preflight_svc = ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        dispatch_intent_service=intent_svc,
        freshness_service=freshness_svc,
        task_readiness_service=FakeTaskReadinessService(),
        task_state_machine_service=FakeTaskStateMachineService(),
        budget_guard_service=FakeBudgetGuardService(session=session),
    )
    d1_svc = ProjectDirectorProtectedTransitionDispatchConsumptionService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        run_repository=run_repo,
        preflight_service=preflight_svc,
        task_readiness_service=FakeTaskReadinessService(),
        task_state_machine_service=FakeTaskStateMachineService(),
        task_router_service=FakeTaskRouterService(),
        budget_guard_service=FakeBudgetGuardService(session=session),
    )
    b1_svc = ProjectDirectorProtectedTransitionWorkerStartReservationService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        run_repository=run_repo,
        agent_session_repository=agent_sess_repo,
        dispatch_consumption_service=d1_svc,
        freshness_service=freshness_svc,
        budget_guard_service=FakeBudgetGuardService(session=session),
    )

    review_msgs = [
        m for m in msg_repo.list_by_session_id(session_id=session_id, limit=200)[0]
        if m.intent == "sandbox_candidate_diff_readonly_review_execution"
    ]
    review_msg_id = review_msgs[0].id

    if session.in_transaction():
        session.rollback()
    p22 = p22_svc.orchestrate_post_review(
        session_id=session_id, source_task_id=task_id, source_review_message_id=review_msg_id,
    )
    intent = intent_svc.prepare_protected_transition_dispatch_intent(
        session_id=session_id, source_task_id=task_id, source_message_id=p22.message.id,
    )
    pf = preflight_svc.prepare_protected_transition_dispatch_consumption_preflight(
        session_id=session_id, source_task_id=task_id, source_message_id=intent.message.id,
    )
    d1 = d1_svc.consume_protected_transition_dispatch_preflight(
        session_id=session_id, source_task_id=task_id, source_message_id=pf.message.id,
    )
    b1 = b1_svc.prepare_protected_transition_worker_start_reservation(
        session_id=session_id, source_task_id=task_id, source_message_id=d1.message.id,
    )
    b1_msg_id = b1.message.id
    run_id = d1.result.run_id
    session.close()
    return b1_msg_id, run_id


def _make_gated_worker():
    """Create a worker that blocks on first call until released."""
    counter = {"n": 0}
    worker_entered = threading.Event()
    release_worker = threading.Event()

    def gated_run_reserved_once(*, task_id, run_id):
        counter["n"] += 1
        if counter["n"] == 1:
            worker_entered.set()
            release_worker.wait(timeout=10)
            # Use independent session to update task/run
            # (the caller's session is the one B2 uses internally)
            return make_d3_worker_result(
                task_id=task_id, run_id=run_id, disposition_type="AUTO_CONTINUE",
            )
        raise AssertionError(f"Worker called a second time (call #{counter['n']})")

    return gated_run_reserved_once, counter, worker_entered, release_worker


# ══════════════════════════════════════════════════════════════════════
# Concurrency Tests
# ══════════════════════════════════════════════════════════════════════


class TestD1Concurrency:
    """D1 concurrent consumption exact-once tests."""

    def test_concurrent_d1_consumption_creates_one_task_claim_run_and_message(self, tmp_path):
        """Two threads consuming the same preflight → one D1 message, one Run."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)

        session_id = uuid4()
        task_id = uuid4()
        project_id = uuid4()

        # Seed base records + review chain
        s = sf()
        seed_base_records(s, project_id=project_id, session_id=session_id, task_id=task_id, task_status="pending")
        _seed_p21_c_review_chain(s, session_id=session_id, task_id=task_id, project_id=project_id)
        s.close()

        # Prepare through P23-C
        preflight_msg_id = _prepare_through_preflight(sf, session_id=session_id, task_id=task_id, project_id=project_id)

        barrier = threading.Barrier(2)
        results = [None, None]
        errors = []

        def consume_worker(idx):
            try:
                stack = _make_independent_stack(sf, session_id=session_id, task_id=task_id, project_id=project_id)
                barrier.wait(timeout=10)
                result = stack["d1_svc"].consume_protected_transition_dispatch_preflight(
                    session_id=session_id, source_task_id=task_id, source_message_id=preflight_msg_id,
                )
                results[idx] = result
                stack["session"].close()
            except Exception as e:
                errors.append((idx, e))

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(consume_worker, i) for i in range(2)]
            for f in as_completed(futures):
                f.result()  # propagate uncaught exceptions

        assert len(errors) == 0, f"Thread errors: {errors}"

        # Both should return valid results
        assert results[0] is not None
        assert results[1] is not None

        # Database assertions
        s = sf()
        task_repo = TaskRepository(s)
        run_repo = RunRepository(s)
        msg_repo = ProjectDirectorMessageRepository(s)

        task = task_repo.get_by_id(task_id)
        assert task.status == TaskStatus.RUNNING

        runs = run_repo.list_by_task_id(task_id)
        assert len(runs) == 1

        d1_count = count_messages_by_source_detail(msg_repo, session_id, P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL)
        assert d1_count == 1

        # Both results bind same D1 message and Run
        d1_msg_ids = {r.message.id for r in results}
        run_ids = {r.result.run_id for r in results}
        assert len(d1_msg_ids) == 1
        assert len(run_ids) == 1

        # Exactly one first-created, one replay
        flags = [r.result.resumed_from_existing_consumption for r in results]
        assert sorted(flags) == [False, True]

        s.close()
        engine.dispose()


class TestB1Concurrency:
    """B1 concurrent reservation exact-once tests."""

    def test_concurrent_b1_reservation_creates_one_exact_reservation(self, tmp_path):
        """Two threads reserving the same D1 → one B1 message, identical reservation fields."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)

        session_id = uuid4()
        task_id = uuid4()
        project_id = uuid4()

        s = sf()
        seed_base_records(s, project_id=project_id, session_id=session_id, task_id=task_id, task_status="pending")
        _seed_p21_c_review_chain(s, session_id=session_id, task_id=task_id, project_id=project_id)
        s.close()

        d1_msg_id, run_id = _prepare_through_d1(sf, session_id=session_id, task_id=task_id, project_id=project_id)

        barrier = threading.Barrier(2)
        results = [None, None]
        errors = []

        def reserve_worker(idx):
            try:
                stack = _make_independent_stack(sf, session_id=session_id, task_id=task_id, project_id=project_id)
                barrier.wait(timeout=10)
                result = stack["b1_svc"].prepare_protected_transition_worker_start_reservation(
                    session_id=session_id, source_task_id=task_id, source_message_id=d1_msg_id,
                )
                results[idx] = result
                stack["session"].close()
            except Exception as e:
                errors.append((idx, e))

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(reserve_worker, i) for i in range(2)]
            for f in as_completed(futures):
                f.result()

        assert len(errors) == 0, f"Thread errors: {errors}"
        assert results[0] is not None
        assert results[1] is not None

        # Database assertions
        s = sf()
        run_repo = RunRepository(s)
        msg_repo = ProjectDirectorMessageRepository(s)

        runs = run_repo.list_by_task_id(task_id)
        assert len(runs) == 1

        b1_count = count_messages_by_source_detail(msg_repo, session_id, P23_PROTECTED_TRANSITION_WORKER_START_RESERVATION_SOURCE_DETAIL)
        assert b1_count == 1

        # Both results bind same message, reservation_id, token, fingerprint, run_id
        assert results[0].message.id == results[1].message.id
        assert results[0].result.reservation_id == results[1].result.reservation_id
        assert results[0].result.reservation_token == results[1].result.reservation_token
        assert results[0].result.reservation_fingerprint == results[1].result.reservation_fingerprint
        assert results[0].result.run_id == results[1].result.run_id

        s.close()
        engine.dispose()


class TestB2Concurrency:
    """B2 concurrent invocation exact-once Worker tests."""

    def test_concurrent_b2_invocation_calls_worker_once_and_persists_one_outcome(self, tmp_path):
        """Two threads invoking B2 on same reservation → Worker called once, one outcome."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)

        session_id = uuid4()
        task_id = uuid4()
        project_id = uuid4()

        s = sf()
        seed_base_records(s, project_id=project_id, session_id=session_id, task_id=task_id, task_status="pending")
        _seed_p21_c_review_chain(s, session_id=session_id, task_id=task_id, project_id=project_id)
        s.close()

        b1_msg_id, run_id = _prepare_through_b1(sf, session_id=session_id, task_id=task_id, project_id=project_id)

        # Gated worker for thread A
        gated_fn, counter, worker_entered, release_worker = _make_gated_worker()
        gated_worker = FakeTaskWorker()
        gated_worker.run_reserved_once = gated_fn

        # Thread A stack with gated worker
        stack_a = _make_independent_stack(sf, session_id=session_id, task_id=task_id, project_id=project_id, fake_worker=gated_worker)

        # Thread B stack with default worker (should not be called)
        stack_b = _make_independent_stack(sf, session_id=session_id, task_id=task_id, project_id=project_id)

        result_a = [None]
        result_b = [None]
        errors = []

        def thread_a():
            try:
                result_a[0] = stack_a["b2_svc"].invoke_reserved_protected_transition_worker(
                    session_id=session_id, source_task_id=task_id, source_message_id=b1_msg_id,
                )
                stack_a["session"].close()
            except Exception as e:
                errors.append(("A", e))

        def thread_b():
            try:
                worker_entered.wait(timeout=10)
                result_b[0] = stack_b["b2_svc"].invoke_reserved_protected_transition_worker(
                    session_id=session_id, source_task_id=task_id, source_message_id=b1_msg_id,
                )
                stack_b["session"].close()
            except Exception as e:
                errors.append(("B", e))

        with ThreadPoolExecutor(max_workers=2) as pool:
            fa = pool.submit(thread_a)
            fb = pool.submit(thread_b)
            # Wait for thread B to return first (it should see claim exists)
            fb.result(timeout=15)
            # Now release the worker in thread A
            release_worker.set()
            fa.result(timeout=15)

        assert len(errors) == 0, f"Thread errors: {errors}"

        # Thread A should have returned outcome
        assert result_a[0] is not None
        assert result_a[0].outcome is not None

        # Thread B should have returned recovery/in-progress (claim exists, no outcome yet)
        assert result_b[0] is not None
        # Thread B sees claim exists but outcome may not be committed yet

        # Database assertions
        s = sf()
        msg_repo = ProjectDirectorMessageRepository(s)

        claim_count = count_messages_by_source_detail(msg_repo, session_id, P23_PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL)
        outcome_count = count_messages_by_source_detail(msg_repo, session_id, P23_PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL)
        assert claim_count == 1
        assert outcome_count == 1

        # Worker called exactly once
        assert counter["n"] == 1

        # Third call: replay
        stack_c = _make_independent_stack(sf, session_id=session_id, task_id=task_id, project_id=project_id)
        result_c = stack_c["b2_svc"].invoke_reserved_protected_transition_worker(
            session_id=session_id, source_task_id=task_id, source_message_id=b1_msg_id,
        )
        assert result_c.outcome is not None
        assert result_c.resumed_from_existing_outcome is True
        assert result_c.claim_message.id == result_a[0].claim_message.id
        assert result_c.outcome_message.id == result_a[0].outcome_message.id
        assert counter["n"] == 1  # Worker still only called once
        stack_c["session"].close()

        s.close()
        engine.dispose()


class TestD3Concurrency:
    """D3 concurrent full-chain exact-once tests."""

    def test_concurrent_d3_auto_continue_creates_one_chain_and_calls_worker_once(self, tmp_path):
        """Two threads running D3 on same review → one complete chain, Worker once."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)

        session_id = uuid4()
        task_id = uuid4()
        project_id = uuid4()

        s = sf()
        seed_base_records(s, project_id=project_id, session_id=session_id, task_id=task_id, task_status="pending")
        review_msg_id = _seed_p21_c_review_chain(s, session_id=session_id, task_id=task_id, project_id=project_id)
        s.close()

        # Gated worker
        gated_fn, counter, worker_entered, release_worker = _make_gated_worker()
        gated_worker = FakeTaskWorker()
        gated_worker.run_reserved_once = gated_fn

        stack_a = _make_independent_stack(sf, session_id=session_id, task_id=task_id, project_id=project_id, fake_worker=gated_worker)
        stack_b = _make_independent_stack(sf, session_id=session_id, task_id=task_id, project_id=project_id)

        result_a = [None]
        result_b = [None]
        errors = []

        def thread_a():
            try:
                result_a[0] = stack_a["d3_svc"].advance_post_review_protected_transition(
                    session_id=session_id, source_task_id=task_id, source_review_message_id=review_msg_id,
                )
                stack_a["session"].close()
            except Exception as e:
                errors.append(("A", e))

        def thread_b():
            try:
                worker_entered.wait(timeout=10)
                result_b[0] = stack_b["d3_svc"].advance_post_review_protected_transition(
                    session_id=session_id, source_task_id=task_id, source_review_message_id=review_msg_id,
                )
                stack_b["session"].close()
            except Exception as e:
                errors.append(("B", e))

        with ThreadPoolExecutor(max_workers=2) as pool:
            fa = pool.submit(thread_a)
            fb = pool.submit(thread_b)
            fb.result(timeout=15)
            release_worker.set()
            fa.result(timeout=15)

        assert len(errors) == 0, f"Thread errors: {errors}"

        # Thread A should have completed
        assert result_a[0] is not None
        assert result_a[0].auto_advance_status == "worker_returned"

        # Thread B may return recovery_required (claim exists, no outcome yet)
        assert result_b[0] is not None

        # Database: exactly one of each evidence
        s = sf()
        counts = count_p23_evidence(ProjectDirectorMessageRepository(s), session_id)
        for sd, count in counts.items():
            assert count == 1, f"Expected 1 for {sd}, got {count}"

        runs = RunRepository(s).list_by_task_id(task_id)
        assert len(runs) == 1
        assert counter["n"] == 1

        # Third call: replay
        stack_c = _make_independent_stack(sf, session_id=session_id, task_id=task_id, project_id=project_id)
        result_c = stack_c["d3_svc"].advance_post_review_protected_transition(
            session_id=session_id, source_task_id=task_id, source_review_message_id=review_msg_id,
        )
        assert result_c.auto_advance_status == "worker_returned"
        assert result_c.resumed_from_existing_evidence is True
        assert result_c.run_id == result_a[0].run_id
        assert counter["n"] == 1
        stack_c["session"].close()

        s.close()
        engine.dispose()

    def test_concurrent_completed_d3_replays_never_call_worker(self, tmp_path):
        """Three concurrent replays of completed D3 → all worker_returned, Worker never called."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)

        session_id = uuid4()
        task_id = uuid4()
        project_id = uuid4()

        s = sf()
        seed_base_records(s, project_id=project_id, session_id=session_id, task_id=task_id, task_status="pending")
        review_msg_id = _seed_p21_c_review_chain(s, session_id=session_id, task_id=task_id, project_id=project_id)
        s.close()

        # First: create complete chain
        worker_counter = {"n": 0}

        def counting_worker(*, task_id, run_id):
            worker_counter["n"] += 1
            s2 = sf()
            TaskRepository(s2).set_status(task_id, TaskStatus.COMPLETED)
            RunRepository(s2).finish_run(run_id, status=RunStatus.SUCCEEDED, result_summary="done")
            s2.commit()
            s2.close()
            return make_d3_worker_result(task_id=task_id, run_id=run_id, disposition_type="AUTO_CONTINUE")

        first_worker = FakeTaskWorker()
        first_worker.run_reserved_once = counting_worker
        stack_first = _make_independent_stack(sf, session_id=session_id, task_id=task_id, project_id=project_id, fake_worker=first_worker)
        r1 = stack_first["d3_svc"].advance_post_review_protected_transition(
            session_id=session_id, source_task_id=task_id, source_review_message_id=review_msg_id,
        )
        assert r1.auto_advance_status == "worker_returned"
        first_evidence_ids = {
            "p22": r1.source_p22_summary_message_id,
            "intent": r1.source_dispatch_intent_message_id,
            "preflight": r1.source_dispatch_consumption_preflight_message_id,
            "d1": r1.source_dispatch_consumption_message_id,
            "b1": r1.source_worker_start_reservation_message_id,
            "claim": r1.source_worker_invocation_claim_message_id,
            "outcome": r1.source_worker_invocation_outcome_message_id,
        }
        first_run_id = r1.run_id
        stack_first["session"].close()

        # Three concurrent replays with exploding workers
        barrier = threading.Barrier(3)
        results = [None, None, None]
        errors = []

        def replay_worker(idx):
            try:
                exploding = FakeTaskWorker()
                exploding.run_reserved_once = lambda **kw: (_ for _ in ()).throw(AssertionError("Worker must not be called on replay"))
                exploding.run_once = lambda **kw: (_ for _ in ()).throw(AssertionError("Worker must not be called on replay"))
                stack = _make_independent_stack(sf, session_id=session_id, task_id=task_id, project_id=project_id, fake_worker=exploding)
                barrier.wait(timeout=10)
                results[idx] = stack["d3_svc"].advance_post_review_protected_transition(
                    session_id=session_id, source_task_id=task_id, source_review_message_id=review_msg_id,
                )
                stack["session"].close()
            except Exception as e:
                errors.append((idx, e))

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(replay_worker, i) for i in range(3)]
            for f in as_completed(futures):
                f.result()

        assert len(errors) == 0, f"Thread errors: {errors}"

        for i in range(3):
            assert results[i].auto_advance_status == "worker_returned"
            assert results[i].resumed_from_existing_evidence is True
            second_ids = {
                "p22": results[i].source_p22_summary_message_id,
                "intent": results[i].source_dispatch_intent_message_id,
                "preflight": results[i].source_dispatch_consumption_preflight_message_id,
                "d1": results[i].source_dispatch_consumption_message_id,
                "b1": results[i].source_worker_start_reservation_message_id,
                "claim": results[i].source_worker_invocation_claim_message_id,
                "outcome": results[i].source_worker_invocation_outcome_message_id,
            }
            assert second_ids == first_evidence_ids
            assert results[i].run_id == first_run_id

        # Counts unchanged
        s = sf()
        counts = count_p23_evidence(ProjectDirectorMessageRepository(s), session_id)
        for sd, count in counts.items():
            assert count == 1, f"Expected 1 for {sd}, got {count}"
        assert worker_counter["n"] == 1

        s.close()
        engine.dispose()
