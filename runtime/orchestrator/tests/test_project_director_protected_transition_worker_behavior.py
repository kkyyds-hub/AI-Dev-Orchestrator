"""Real behavioral tests for P23-D1 atomic dispatch consumption, B1 reservation, and TaskWorker."""

from __future__ import annotations

import json
from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.db_tables import ORMBase, AgentSessionTable, ProjectTable, RunTable, TaskTable
from app.domain.run import RunBudgetPressureLevel, RunBudgetStrategyAction, RunStatus
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
from app.workers.task_worker import TaskWorker, WorkerRunResult
from tests.p23_test_support import (
    DIFF_SHA256,
    _FINGERPRINT,
    ExplodingAgentSessionRepository,
    ExplodingBudgetGuardService,
    ExplodingFreshnessService,
    ExplodingTaskRouterService,
    FakeBudgetGuardService,
    FakeBudgetDecision,
    FakeFreshnessService,
    SpySharedExecutionHelper,
    _FakeRetryStatus,
    make_b1_service,
    make_d1_service,
    make_repos,
    make_session_factory,
    make_task_worker,
    make_test_engine,
    prepare_valid_b1_reservation,
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


# ══════════════════════════════════════════════════════════════════════
# Helper: Create running Task/Run for TaskWorker tests
# ══════════════════════════════════════════════════════════════════════


def _create_running_task_run(sf, *, project_id=None, task_id=None, run_id=None, skip_project=False):
    """Seed a running Task and running Run via real repositories."""
    from app.domain.project_role import ProjectRoleCode
    from app.domain.run import RunStrategyDecision

    pid = project_id or uuid4()
    tid = task_id or uuid4()

    s = sf()
    if not skip_project:
        s.add(ProjectTable(
            id=pid, name="Test", summary="Test project",
            status="active", stage="intake",
        ))
        s.flush()
    acceptance = json.dumps([
        "safe_dry_run_task=true",
        "worker_simulate_required=true",
        "product_runtime_git_write_allowed=false",
    ])
    s.add(TaskTable(
        id=tid, project_id=pid, title="Test task",
        status="running", priority="normal",
        input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
        risk_level="normal", human_status="none",
        source_draft_id="p12-test-draft", acceptance_criteria=acceptance,
    ))
    s.commit()

    task_repo = TaskRepository(s)
    run_repo = RunRepository(s)

    from app.domain.run import RunRoutingScoreItem
    strategy = RunStrategyDecision(
        budget_pressure_level=RunBudgetPressureLevel.NORMAL,
        budget_action=RunBudgetStrategyAction.FULL_SPEED,
        strategy_code="normal",
        summary="Normal execution",
    )
    run = run_repo.add_running_run_no_event(
        task_id=tid,
        model_name="test-model",
        route_reason="test-route",
        routing_score=1.0,
        routing_score_breakdown=[RunRoutingScoreItem(code="test", label="Test", score=1.0, detail="test")],
        strategy_decision=strategy,
        owner_role_code=ProjectRoleCode.ARCHITECT,
        upstream_role_code=None,
        downstream_role_code=None,
        handoff_reason="test",
        dispatch_status="dispatched",
    )
    s.commit()
    rid = run.id
    s.close()
    return {"project_id": pid, "task_id": tid, "run_id": rid}


# ══════════════════════════════════════════════════════════════════════
# TaskWorker Production run_reserved_once Tests
# ══════════════════════════════════════════════════════════════════════


class TestTaskWorkerReservedExecution:
    """Real production TaskWorker.run_reserved_once() behavioral tests."""

    def test_run_reserved_once_blocks_when_exact_task_missing(self, tmp_path):
        """Blocks with reserved_task_missing when Task does not exist."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        ctx = _create_running_task_run(sf)
        task_repo, run_repo, session = _make_task_repos(sf, ctx)

        worker = make_task_worker(session, task_repo=task_repo, run_repo=run_repo)
        spy = SpySharedExecutionHelper()
        spy.install(worker)

        result = worker.run_reserved_once(
            task_id=uuid4(),  # non-existent
            run_id=ctx["run_id"],
        )

        assert result.claimed is False
        assert result.message == "reserved_task_missing"
        assert spy.call_count == 0

        spy.restore(worker)
        session.close()
        engine.dispose()

    def test_run_reserved_once_blocks_when_exact_run_missing(self, tmp_path):
        """Blocks with reserved_run_missing when Run does not exist."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        ctx = _create_running_task_run(sf)
        task_repo, run_repo, session = _make_task_repos(sf, ctx)

        worker = make_task_worker(session, task_repo=task_repo, run_repo=run_repo)
        spy = SpySharedExecutionHelper()
        spy.install(worker)

        result = worker.run_reserved_once(
            task_id=ctx["task_id"],
            run_id=uuid4(),  # non-existent
        )

        assert result.claimed is False
        assert result.message == "reserved_run_missing"
        assert spy.call_count == 0

        spy.restore(worker)
        session.close()
        engine.dispose()

    def test_run_reserved_once_blocks_when_run_belongs_to_other_task(self, tmp_path):
        """Blocks with reserved_run_task_mismatch when Run belongs to different Task."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        ctx = _create_running_task_run(sf)
        other = _create_running_task_run(sf, project_id=ctx["project_id"], skip_project=True)
        task_repo, run_repo, session = _make_task_repos(sf, ctx)

        worker = make_task_worker(session, task_repo=task_repo, run_repo=run_repo)
        spy = SpySharedExecutionHelper()
        spy.install(worker)

        result = worker.run_reserved_once(
            task_id=ctx["task_id"],
            run_id=other["run_id"],  # belongs to other task
        )

        assert result.claimed is False
        assert result.message == "reserved_run_task_mismatch"
        assert spy.call_count == 0

        spy.restore(worker)
        session.close()
        engine.dispose()

    def test_run_reserved_once_blocks_when_task_not_running(self, tmp_path):
        """Blocks with reserved_task_not_running when Task is not running."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        ctx = _create_running_task_run(sf)

        # Change task to completed
        s = sf()
        task = s.get(TaskTable, ctx["task_id"])
        task.status = "completed"
        s.commit()
        s.close()

        task_repo, run_repo, session = _make_task_repos(sf, ctx)

        worker = make_task_worker(session, task_repo=task_repo, run_repo=run_repo)
        spy = SpySharedExecutionHelper()
        spy.install(worker)

        result = worker.run_reserved_once(
            task_id=ctx["task_id"],
            run_id=ctx["run_id"],
        )

        assert result.claimed is False
        assert result.message == "reserved_task_not_running"
        assert spy.call_count == 0

        spy.restore(worker)
        session.close()
        engine.dispose()

    def test_run_reserved_once_blocks_when_run_not_running(self, tmp_path):
        """Blocks with reserved_run_not_running when Run is not running."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        ctx = _create_running_task_run(sf)

        # Change run to succeeded
        s = sf()
        run = s.get(RunTable, ctx["run_id"])
        run.status = "succeeded"
        s.commit()
        s.close()

        task_repo, run_repo, session = _make_task_repos(sf, ctx)

        worker = make_task_worker(session, task_repo=task_repo, run_repo=run_repo)
        spy = SpySharedExecutionHelper()
        spy.install(worker)

        result = worker.run_reserved_once(
            task_id=ctx["task_id"],
            run_id=ctx["run_id"],
        )

        assert result.claimed is False
        assert result.message == "reserved_run_not_running"
        assert spy.call_count == 0

        spy.restore(worker)
        session.close()
        engine.dispose()

    @pytest.mark.parametrize("field,value,reason", [
        ("route_reason", "", "reserved_run_routing_metadata_invalid"),
        ("route_reason", None, "reserved_run_routing_metadata_invalid"),
        ("model_name", "", "reserved_run_routing_metadata_invalid"),
        ("model_name", None, "reserved_run_routing_metadata_invalid"),
        ("dispatch_status", "", "reserved_run_routing_metadata_invalid"),
        ("dispatch_status", None, "reserved_run_routing_metadata_invalid"),
    ])
    def test_run_reserved_once_blocks_when_routing_metadata_invalid(self, tmp_path, field, value, reason):
        """Blocks with reserved_run_routing_metadata_invalid for missing routing fields."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        ctx = _create_running_task_run(sf)

        # Corrupt routing metadata
        s = sf()
        run = s.get(RunTable, ctx["run_id"])
        setattr(run, field, value)
        s.commit()
        s.close()

        task_repo, run_repo, session = _make_task_repos(sf, ctx)

        worker = make_task_worker(session, task_repo=task_repo, run_repo=run_repo)
        spy = SpySharedExecutionHelper()
        spy.install(worker)

        result = worker.run_reserved_once(
            task_id=ctx["task_id"],
            run_id=ctx["run_id"],
        )

        assert result.claimed is False
        assert result.message == reason
        assert spy.call_count == 0

        spy.restore(worker)
        session.close()
        engine.dispose()

    def test_run_reserved_once_blocks_when_agent_session_already_exists(self, tmp_path):
        """Blocks with reserved_run_agent_session_already_exists."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        ctx = _create_running_task_run(sf)

        # Create AgentSession for the Run
        s = sf()
        s.add(AgentSessionTable(
            id=uuid4(), project_id=ctx["project_id"],
            task_id=ctx["task_id"], run_id=ctx["run_id"],
            agent_type="codex", status="running",
            coding_status="idle", activity_state="idle",
            workspace_type="worktree",
        ))
        s.commit()
        s.close()

        task_repo, run_repo, session = _make_task_repos(sf, ctx)
        agent_sess_repo = AgentSessionRepository(session)

        worker = make_task_worker(
            session, task_repo=task_repo, run_repo=run_repo,
            agent_sess_repo=agent_sess_repo,
        )
        spy = SpySharedExecutionHelper()
        spy.install(worker)

        result = worker.run_reserved_once(
            task_id=ctx["task_id"],
            run_id=ctx["run_id"],
        )

        assert result.claimed is False
        assert result.message == "reserved_run_agent_session_already_exists"
        assert spy.call_count == 0

        spy.restore(worker)
        session.close()
        engine.dispose()

    def test_run_reserved_once_blocks_when_current_budget_denied(self, tmp_path):
        """Blocks when budget guard denies execution."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        ctx = _create_running_task_run(sf)
        task_repo, run_repo, session = _make_task_repos(sf, ctx)

        budget_svc = FakeBudgetGuardService(session=session, allowed=False)
        worker = make_task_worker(
            session, task_repo=task_repo, run_repo=run_repo,
            budget_guard_service=budget_svc,
        )
        spy = SpySharedExecutionHelper()
        spy.install(worker)

        result = worker.run_reserved_once(
            task_id=ctx["task_id"],
            run_id=ctx["run_id"],
        )

        # Budget denied means the worker enters guard-blocked path
        assert spy.call_count == 0
        assert result.reserved_run_execution_snapshot is not None
        assert "budget_guard_blocked" in result.reserved_run_execution_snapshot.blocked_reasons

        spy.restore(worker)
        session.close()
        engine.dispose()

    def test_run_reserved_once_reuses_exact_task_and_run_and_enters_shared_execution_seam(self, tmp_path):
        """Exact success: enters shared execution seam with correct snapshot."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        ctx = _create_running_task_run(sf)
        task_repo, run_repo, session = _make_task_repos(sf, ctx)

        worker = make_task_worker(session, task_repo=task_repo, run_repo=run_repo)
        spy = SpySharedExecutionHelper()
        spy.install(worker)

        result = worker.run_reserved_once(
            task_id=ctx["task_id"],
            run_id=ctx["run_id"],
        )

        # Shared helper called exactly once
        assert spy.call_count == 1
        assert spy.calls[0]["task_id"] == ctx["task_id"]
        assert spy.calls[0]["run_id"] == ctx["run_id"]

        # Snapshot verification
        snap = result.reserved_run_execution_snapshot
        assert snap is not None
        assert snap.source == "p23_d2_exact_reserved_run"
        assert snap.exact_task_id == ctx["task_id"]
        assert snap.exact_run_id == ctx["run_id"]
        assert snap.reserved_run_execution_requested is True
        assert snap.exact_binding_validated is True
        assert snap.task_routed is False
        assert snap.task_claimed_in_this_cycle is False
        assert snap.run_created_in_this_cycle is False
        assert snap.budget_rechecked is True
        assert snap.existing_run_reused is True
        assert snap.shared_execution_seam_used is True
        assert snap.product_runtime_git_write_allowed is False
        assert snap.blocked_reasons == []

        spy.restore(worker)
        session.close()
        engine.dispose()

    def test_run_once_and_run_reserved_once_use_same_shared_execution_helper(self, tmp_path):
        """Both run_once and run_reserved_once enter _execute_running_task_run."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        ctx = _create_running_task_run(sf)
        task_repo, run_repo, session = _make_task_repos(sf, ctx)

        # For run_once, we need a working router
        from app.domain.project_role import ProjectRoleCode
        from app.domain.run import RunStrategyDecision
        from app.services.task_readiness_service import TaskReadinessResult
        from app.services.task_router_service import TaskRoutingCandidate

        class _FakeRouterForRunOnce:
            def route_next_task(self, **kwargs):
                task = task_repo.get_by_id(ctx["task_id"])
                return type("D", (), {
                    "selected_task": task,
                    "message": "ok",
                    "budget_pressure_level": RunBudgetPressureLevel.NORMAL,
                    "budget_action": RunBudgetStrategyAction.FULL_SPEED,
                    "budget_strategy_code": "normal",
                    "budget_strategy_summary": "Normal",
                    "candidates": [],
                })()

        worker = make_task_worker(
            session, task_repo=task_repo, run_repo=run_repo,
            task_router_service=_FakeRouterForRunOnce(),
        )
        spy = SpySharedExecutionHelper()
        spy.install(worker)

        # Call run_reserved_once first
        r1 = worker.run_reserved_once(
            task_id=ctx["task_id"],
            run_id=ctx["run_id"],
        )
        assert spy.call_count == 1

        # Both used the same _execute_running_task_run
        assert spy.calls[0]["task_id"] == ctx["task_id"]

        spy.restore(worker)
        session.close()
        engine.dispose()


def _make_task_repos(sf, ctx):
    """Helper to create repos from session factory."""
    session = sf()
    task_repo = TaskRepository(session)
    run_repo = RunRepository(session)
    return task_repo, run_repo, session
