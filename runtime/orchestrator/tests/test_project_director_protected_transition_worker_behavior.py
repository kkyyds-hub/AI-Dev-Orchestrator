"""Real behavioral tests for P23-D1 atomic dispatch consumption and B1 reservation."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.db_tables import ORMBase, AgentSessionTable
from app.domain.run import RunStatus
from app.domain.task import TaskStatus
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.project_director_protected_transition_dispatch_consumption_service import (
    P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL,
)
from app.services.project_director_protected_transition_worker_start_reservation_service import (
    P23_PROTECTED_TRANSITION_WORKER_START_RESERVATION_SOURCE_DETAIL,
    ProjectDirectorProtectedTransitionWorkerStartReservationService,
)
from tests.p23_test_support import (
    DIFF_SHA256,
    _FINGERPRINT,
    ExplodingAgentSessionRepository,
    ExplodingBudgetGuardService,
    ExplodingFreshnessService,
    FakeBudgetGuardService,
    FakeFreshnessService,
    make_b1_service,
    make_d1_service,
    make_repos,
    make_session_factory,
    make_test_engine,
    prepare_valid_preflight,
    seed_base_records,
    count_messages_by_source_detail,
)


# ══════════════════════════════════════════════════════════════════════
# Helper: Create full D1 success chain
# ══════════════════════════════════════════════════════════════════════


def _create_d1_success(sf, *, task_status="pending"):
    """Create a full D1 success chain and return all needed references."""
    s = sf()
    ids = seed_base_records(s, task_status=task_status)
    s.close()

    preflight_msg_id, session, msg_repo, task_repo, run_repo, preflight_svc = (
        prepare_valid_preflight(
            sf,
            session_id=ids["session_id"],
            task_id=ids["task_id"],
            project_id=ids["project_id"],
        )
    )
    agent_sess_repo = AgentSessionRepository(session)
    session.close()

    d1_svc, session, msg_repo, task_repo, run_repo = make_d1_service(
        sf, preflight_svc=preflight_svc,
        msg_repo=msg_repo, task_repo=task_repo, run_repo=run_repo,
    )
    d1_result = d1_svc.consume_protected_transition_dispatch_preflight(
        session_id=ids["session_id"],
        source_task_id=ids["task_id"],
        source_message_id=preflight_msg_id,
    )
    assert d1_result.result.consumption_status == "reserved_for_worker_start"
    session.close()

    return {
        "ids": ids,
        "preflight_msg_id": preflight_msg_id,
        "d1_result": d1_result,
        "d1_svc": d1_svc,
        "msg_repo": msg_repo,
        "task_repo": task_repo,
        "run_repo": run_repo,
        "agent_sess_repo": agent_sess_repo,
    }


# ══════════════════════════════════════════════════════════════════════
# B1 Real Service Behavioral Tests
# ══════════════════════════════════════════════════════════════════════


class TestB1ReservationBehavior:
    """Real B1 service behavioral tests using actual D1 success results."""

    def test_b1_success_creates_single_reservation_for_exact_consumption_and_run(self, tmp_path):
        """B1 creates exactly one reservation for the exact D1 consumption."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        ctx = _create_d1_success(sf)

        ids = ctx["ids"]
        d1_msg_id = ctx["d1_result"].message.id
        d1_run_id = ctx["d1_result"].result.run_id

        b1_svc, session, msg_repo, task_repo, run_repo, _ = make_b1_service(
            sf,
            msg_repo=ctx["msg_repo"],
            task_repo=ctx["task_repo"],
            run_repo=ctx["run_repo"],
            d1_service=ctx["d1_svc"],
        )

        result = b1_svc.prepare_protected_transition_worker_start_reservation(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_message_id=d1_msg_id,
        )

        assert result.result.reservation_status == "reserved"
        assert result.message is not None
        assert result.result.source_consumption_message_id == d1_msg_id
        assert result.result.run_id == d1_run_id
        assert result.result.reservation_id == result.message.id
        assert result.result.reservation_token is not None
        assert result.result.reservation_token != ""

        b1_count = count_messages_by_source_detail(
            msg_repo, ids["session_id"],
            P23_PROTECTED_TRANSITION_WORKER_START_RESERVATION_SOURCE_DETAIL,
        )
        assert b1_count == 1

        # Task/Run still running
        task = task_repo.get_by_id(ids["task_id"])
        assert task.status == TaskStatus.RUNNING
        run = run_repo.get_by_id(d1_run_id)
        assert run.status == RunStatus.RUNNING

        session.close()
        engine.dispose()

    def test_b1_replay_reuses_same_reservation(self, tmp_path):
        """Second B1 call returns same reservation."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        ctx = _create_d1_success(sf)

        ids = ctx["ids"]
        d1_msg_id = ctx["d1_result"].message.id

        # First call
        b1_svc, session, msg_repo, task_repo, run_repo, _ = make_b1_service(
            sf,
            msg_repo=ctx["msg_repo"],
            task_repo=ctx["task_repo"],
            run_repo=ctx["run_repo"],
            d1_service=ctx["d1_svc"],
        )
        r1 = b1_svc.prepare_protected_transition_worker_start_reservation(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_message_id=d1_msg_id,
        )
        assert r1.result.reservation_status == "reserved"
        first_id = r1.result.reservation_id
        first_token = r1.result.reservation_token
        first_fp = r1.result.reservation_fingerprint
        session.close()

        # Second call (replay)
        b1_svc2, session2, msg_repo2, task_repo2, run_repo2, _ = make_b1_service(
            sf,
            msg_repo=ctx["msg_repo"],
            task_repo=ctx["task_repo"],
            run_repo=ctx["run_repo"],
            d1_service=ctx["d1_svc"],
        )
        r2 = b1_svc2.prepare_protected_transition_worker_start_reservation(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_message_id=d1_msg_id,
        )

        assert r2.result.reservation_id == first_id
        assert r2.result.reservation_token == first_token
        assert r2.result.reservation_fingerprint == first_fp
        assert r2.result.resumed_from_existing_reservation is True

        b1_count = count_messages_by_source_detail(
            msg_repo, ids["session_id"],
            P23_PROTECTED_TRANSITION_WORKER_START_RESERVATION_SOURCE_DETAIL,
        )
        assert b1_count == 1

        session2.close()
        engine.dispose()

    def test_b1_blocks_initial_reservation_when_agent_session_exists(self, tmp_path):
        """B1 blocks when AgentSession already exists for the Run."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        ctx = _create_d1_success(sf)

        ids = ctx["ids"]
        d1_msg_id = ctx["d1_result"].message.id
        d1_run_id = ctx["d1_result"].result.run_id

        # Create AgentSession for the Run
        s = sf()
        s.add(AgentSessionTable(
            id=uuid4(),
            project_id=ids["project_id"],
            task_id=ids["task_id"],
            run_id=d1_run_id,
            agent_type="codex",
            status="running",
            coding_status="idle",
            activity_state="idle",
            workspace_type="worktree",
        ))
        s.commit()
        s.close()

        b1_svc, session, msg_repo, task_repo, run_repo, _ = make_b1_service(
            sf,
            msg_repo=ctx["msg_repo"],
            task_repo=ctx["task_repo"],
            run_repo=ctx["run_repo"],
            d1_service=ctx["d1_svc"],
        )

        result = b1_svc.prepare_protected_transition_worker_start_reservation(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_message_id=d1_msg_id,
        )

        assert result.result.reservation_status == "blocked"
        assert "reserved_run_agent_session_already_exists" in result.result.blocked_reasons
        assert result.message is None

        session.close()
        engine.dispose()

    def test_b1_blocks_initial_reservation_when_budget_denied(self, tmp_path):
        """B1 blocks when budget guard denies."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        ctx = _create_d1_success(sf)

        ids = ctx["ids"]
        d1_msg_id = ctx["d1_result"].message.id

        b1_svc, session, msg_repo, task_repo, run_repo, _ = make_b1_service(
            sf,
            msg_repo=ctx["msg_repo"],
            task_repo=ctx["task_repo"],
            run_repo=ctx["run_repo"],
            d1_service=ctx["d1_svc"],
            budget_allowed=False,
        )

        result = b1_svc.prepare_protected_transition_worker_start_reservation(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_message_id=d1_msg_id,
        )

        assert result.result.reservation_status == "blocked"
        assert "budget_guard_blocked" in result.result.blocked_reasons
        assert result.message is None

        session.close()
        engine.dispose()

    def test_b1_blocks_when_task_not_running(self, tmp_path):
        """B1 blocks when task is not in running state."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)

        # Create D1 with task_status="pending" but then change task state
        ctx = _create_d1_success(sf)
        ids = ctx["ids"]
        d1_msg_id = ctx["d1_result"].message.id

        # Change task to completed
        task = ctx["task_repo"].get_by_id(ids["task_id"])
        ctx["task_repo"].set_status(ids["task_id"], TaskStatus.COMPLETED)
        ctx["msg_repo"]._session.commit()

        b1_svc, session, msg_repo, task_repo, run_repo, _ = make_b1_service(
            sf,
            msg_repo=ctx["msg_repo"],
            task_repo=ctx["task_repo"],
            run_repo=ctx["run_repo"],
            d1_service=ctx["d1_svc"],
        )

        result = b1_svc.prepare_protected_transition_worker_start_reservation(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_message_id=d1_msg_id,
        )

        assert result.result.reservation_status == "blocked"
        assert result.message is None

        session.close()
        engine.dispose()

    def test_b1_blocks_when_run_not_running(self, tmp_path):
        """B1 blocks when run is not in running state."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        ctx = _create_d1_success(sf)

        ids = ctx["ids"]
        d1_msg_id = ctx["d1_result"].message.id
        d1_run_id = ctx["d1_result"].result.run_id

        # Change run to completed
        ctx["run_repo"].finish_run(d1_run_id, status=RunStatus.SUCCEEDED, result_summary="test")
        ctx["msg_repo"]._session.commit()

        b1_svc, session, msg_repo, task_repo, run_repo, _ = make_b1_service(
            sf,
            msg_repo=ctx["msg_repo"],
            task_repo=ctx["task_repo"],
            run_repo=ctx["run_repo"],
            d1_service=ctx["d1_svc"],
        )

        result = b1_svc.prepare_protected_transition_worker_start_reservation(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_message_id=d1_msg_id,
        )

        assert result.result.reservation_status == "blocked"
        assert result.message is None

        session.close()
        engine.dispose()

    def test_b1_persisted_finder_recovers_reservation_after_task_run_terminal(self, tmp_path):
        """B1 persisted finder can recover reservation even after Task/Run become terminal.

        Uses exploding spies to prove the persisted finder does NOT call:
        - current freshness revalidation
        - budget evaluation
        - AgentSession absence lookup
        """
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        ctx = _create_d1_success(sf)

        ids = ctx["ids"]
        d1_msg_id = ctx["d1_result"].message.id
        d1_run_id = ctx["d1_result"].result.run_id
        msg_repo = ctx["msg_repo"]
        task_repo = ctx["task_repo"]
        run_repo = ctx["run_repo"]

        # Create reservation with normal service
        b1_svc, session, _, _, _, _ = make_b1_service(
            sf,
            msg_repo=msg_repo,
            task_repo=task_repo,
            run_repo=run_repo,
            d1_service=ctx["d1_svc"],
        )
        r1 = b1_svc.prepare_protected_transition_worker_start_reservation(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_message_id=d1_msg_id,
        )
        assert r1.result.reservation_status == "reserved"
        reservation_msg_id = r1.message.id
        session.close()

        # Move Task/Run to terminal state
        task_repo.set_status(ids["task_id"], TaskStatus.COMPLETED)
        run_repo.finish_run(d1_run_id, status=RunStatus.SUCCEEDED, result_summary="test")
        msg_repo._session.commit()

        # Now create B1 service with exploding spies for finder
        session2 = msg_repo._session
        sess_repo2 = ProjectDirectorSessionRepository(session2)
        exploding_freshness = ExplodingFreshnessService(
            session=session2, msg_repo=msg_repo, task_repo=task_repo,
        )
        exploding_budget = ExplodingBudgetGuardService(session=session2)
        exploding_agent_sess = ExplodingAgentSessionRepository(session=session2)

        # Create a D1 service that shares the same repos (needed for shared session check)
        d1_svc_for_finder = ctx["d1_svc"]

        b1_finder_svc = ProjectDirectorProtectedTransitionWorkerStartReservationService(
            session_repository=sess_repo2,
            message_repository=msg_repo,
            task_repository=task_repo,
            run_repository=run_repo,
            agent_session_repository=exploding_agent_sess,
            dispatch_consumption_service=d1_svc_for_finder,
            freshness_service=exploding_freshness,
            budget_guard_service=exploding_budget,
        )

        found = b1_finder_svc.find_persisted_protected_transition_worker_start_reservation(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_consumption_message_id=d1_msg_id,
        )

        assert found.result is not None, "persisted finder must return existing reservation"
        assert found.result.reservation_id == reservation_msg_id
        assert found.message.id == reservation_msg_id
        assert found.blocked_reasons == [], f"unexpected blocked reasons: {found.blocked_reasons}"
        assert exploding_agent_sess._called is False, "persisted finder must not check AgentSession absence"

        engine.dispose()
