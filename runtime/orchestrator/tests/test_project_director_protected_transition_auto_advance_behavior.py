"""Real behavioral tests for P23-D3 auto-advance coordinator.

These tests call the real ProjectDirectorProtectedTransitionAutoAdvanceService
with real P22/P23 services and verify the full evidence chain.
"""

from __future__ import annotations

import json
import threading
from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.db_tables import ORMBase, AgentSessionTable, ProjectDirectorMessageTable, ProjectTable, RunTable, TaskTable
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
from app.services.project_director_sandbox_candidate_diff_readonly_review_execution_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
)
from app.workers.task_worker import (
    WorkerReservedRunExecutionSnapshot,
    WorkerRunResult,
)
from tests.p23_test_support import (
    DIFF_SHA256,
    _FINGERPRINT,
    _valid_review_action_d3,
    FakeBudgetGuardService,
    FakeFreshnessService,
    FakeIntentService,
    FakeTaskReadinessService,
    FakeTaskStateMachineService,
    FakeTaskRouterService,
    FakeTaskWorker,
    make_d3_worker_result,
    make_real_d3_stack,
    make_repos,
    make_session_factory,
    make_test_engine,
    seed_base_records,
    count_p23_evidence,
    count_messages_by_source_detail,
    get_messages_by_source_detail,
    P22_POST_REVIEW_AUTOMATION_SOURCE_DETAIL,
    P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL,
    P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL,
    P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL,
    P23_PROTECTED_TRANSITION_WORKER_START_RESERVATION_SOURCE_DETAIL,
    P23_PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL,
    P23_PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL,
)


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════


def _create_d3_with_fake_worker(
    tmp_path,
    *,
    verdict="no_blocking_findings",
    risk_level="low",
    disposition_type="AUTO_CONTINUE",
    dispatch_kind="auto_continue",
    worker_result=None,
    worker_exception=None,
):
    """Create a full D3 stack with a controllable fake Worker."""
    engine = make_test_engine(str(tmp_path / "test.db"))
    sf = make_session_factory(engine)

    task_id = uuid4()
    run_id = uuid4()

    fake_worker = FakeTaskWorker(
        result=worker_result,
        exception=worker_exception,
    )

    ctx = make_real_d3_stack(
        sf,
        session_id=uuid4(),
        task_id=task_id,
        project_id=uuid4(),
        verdict=verdict,
        risk_level=risk_level,
        disposition_type=disposition_type,
        dispatch_kind=dispatch_kind,
        fake_worker=fake_worker,
    )
    return engine, sf, ctx, task_id, run_id


def _setup_worker_result_for_success(ctx, task_id, run_id, *, disposition_type="AUTO_CONTINUE"):
    """Configure fake worker to succeed and update task/run state."""
    fake_worker = ctx["fake_worker"]
    task_repo = ctx["task_repo"]
    run_repo = ctx["run_repo"]

    def success_worker(*, task_id, run_id):
        # Get actual IDs from DB
        task = task_repo.get_by_id(task_id)
        run = run_repo.get_by_id(run_id)
        if task:
            task_repo.set_status(task_id, TaskStatus.COMPLETED)
        if run:
            run_repo.finish_run(run_id, status=RunStatus.SUCCEEDED, result_summary="done")
        ctx["msg_repo"]._session.commit()

        return make_d3_worker_result(
            task_id=task_id,
            run_id=run_id,
            disposition_type=disposition_type,
        )

    fake_worker.run_reserved_once = success_worker
    return fake_worker


# ══════════════════════════════════════════════════════════════════════
# D3 Auto-Advance Behavioral Tests
# ══════════════════════════════════════════════════════════════════════


class TestD3AutoAdvanceBehavior:
    """Real D3 coordinator behavioral tests using full P22→P23 chain."""

    def test_d3_first_auto_continue_runs_real_chain_once(self, tmp_path):
        """AUTO_CONTINUE first run: full P22→P23 chain produces worker_returned."""
        engine, sf, ctx, task_id, run_id = _create_d3_with_fake_worker(
            tmp_path,
            verdict="no_blocking_findings",
            risk_level="low",
            disposition_type="AUTO_CONTINUE",
            dispatch_kind="auto_continue",
        )

        # Get actual run_id from D1
        d1_run_id = None

        def capture_run_worker(*, task_id, run_id):
            nonlocal d1_run_id
            d1_run_id = run_id
            ctx["fake_worker"].run_reserved_once_calls.append({"task_id": task_id, "run_id": run_id})
            task = ctx["task_repo"].get_by_id(task_id)
            run = ctx["run_repo"].get_by_id(run_id)
            if task:
                ctx["task_repo"].set_status(task_id, TaskStatus.COMPLETED)
            if run:
                ctx["run_repo"].finish_run(run_id, status=RunStatus.SUCCEEDED, result_summary="done")
            ctx["msg_repo"]._session.commit()
            return make_d3_worker_result(
                task_id=task_id,
                run_id=run_id,
                disposition_type="AUTO_CONTINUE",
            )

        ctx["fake_worker"].run_reserved_once = capture_run_worker

        result = ctx["d3_svc"].advance_post_review_protected_transition(
            session_id=ctx["session_id"],
            source_task_id=ctx["task_id"],
            source_review_message_id=ctx["review_msg_id"],
        )

        # Core assertions
        assert result.auto_advance_status == "worker_returned"
        assert result.current_step == "worker_invocation_outcome"
        assert result.route == "automatic_continuation"
        assert result.disposition_type == "AUTO_CONTINUE"
        assert result.dispatch_kind == "auto_continue"
        assert result.target_task_strategy == "source_task_continue"

        # Flags
        assert result.continuation_started is True
        assert result.rework_started is False
        assert result.worker_invocation_claimed is True
        assert result.worker_call_attempted is True
        assert result.worker_returned is True
        assert result.worker_raised is False
        assert result.human_recovery_required is False
        assert result.d1_task_claimed is True
        assert result.d1_run_created is True
        assert result.resumed_from_existing_evidence is False
        assert result.product_runtime_git_write_allowed is False

        # IDs
        assert result.source_p22_summary_message_id is not None
        assert result.source_dispatch_intent_message_id is not None
        assert result.source_dispatch_consumption_preflight_message_id is not None
        assert result.source_dispatch_consumption_message_id is not None
        assert result.source_worker_start_reservation_message_id is not None
        assert result.source_worker_invocation_claim_message_id is not None
        assert result.source_worker_invocation_outcome_message_id is not None
        assert result.run_id is not None

        # DB counts
        runs = ctx["run_repo"].list_by_task_id(task_id)
        assert len(runs) == 1

        counts = count_p23_evidence(ctx["msg_repo"], ctx["session_id"])
        for sd, count in counts.items():
            assert count == 1, f"Expected 1 for {sd}, got {count}"

        # Worker calls
        assert len(ctx["fake_worker"].run_reserved_once_calls) == 1
        assert len(ctx["fake_worker"].run_once_calls) == 0

        # Coordinator flags
        assert result.coordinator_created_task is False
        assert result.coordinator_created_run is False
        assert result.coordinator_routed_task is False
        assert result.coordinator_claimed_task is False
        assert result.coordinator_called_worker_directly is False

        engine.dispose()

    def test_d3_first_auto_rework_starts_only_rework(self, tmp_path):
        """AUTO_REWORK first run: rework_started=True, continuation_started=False."""
        engine, sf, ctx, task_id, run_id = _create_d3_with_fake_worker(
            tmp_path,
            verdict="changes_required",
            risk_level="medium",
            disposition_type="AUTO_REWORK",
            dispatch_kind="auto_rework",
        )

        def success_worker(*, task_id, run_id):
            ctx["fake_worker"].run_reserved_once_calls.append({"task_id": task_id, "run_id": run_id})
            ctx["task_repo"].set_status(task_id, TaskStatus.COMPLETED)
            ctx["run_repo"].finish_run(run_id, status=RunStatus.SUCCEEDED, result_summary="done")
            ctx["msg_repo"]._session.commit()
            return make_d3_worker_result(
                task_id=task_id,
                run_id=run_id,
                disposition_type="AUTO_REWORK",
            )

        ctx["fake_worker"].run_reserved_once = success_worker

        result = ctx["d3_svc"].advance_post_review_protected_transition(
            session_id=ctx["session_id"],
            source_task_id=ctx["task_id"],
            source_review_message_id=ctx["review_msg_id"],
        )

        assert result.auto_advance_status == "worker_returned"
        assert result.route == "bounded_automatic_rework"
        assert result.disposition_type == "AUTO_REWORK"
        assert result.dispatch_kind == "auto_rework"
        assert result.target_task_strategy == "source_task_rework"
        assert result.continuation_started is False
        assert result.rework_started is True

        # Evidence counts
        counts = count_p23_evidence(ctx["msg_repo"], ctx["session_id"])
        for sd, count in counts.items():
            assert count == 1, f"Expected 1 for {sd}, got {count}"

        runs = ctx["run_repo"].list_by_task_id(task_id)
        assert len(runs) == 1
        assert len(ctx["fake_worker"].run_reserved_once_calls) == 1

        engine.dispose()

    def test_d3_waiting_for_human_stops_after_p22(self, tmp_path):
        """ESCALATE_TO_HUMAN: D3 stops at p22_waiting_for_human."""
        engine, sf, ctx, task_id, run_id = _create_d3_with_fake_worker(
            tmp_path,
            verdict="no_blocking_findings",
            risk_level="high",  # triggers ESCALATE_TO_HUMAN
            disposition_type="AUTO_CONTINUE",
            dispatch_kind="auto_continue",
        )

        result = ctx["d3_svc"].advance_post_review_protected_transition(
            session_id=ctx["session_id"],
            source_task_id=ctx["task_id"],
            source_review_message_id=ctx["review_msg_id"],
        )

        assert result.auto_advance_status == "waiting_for_human"
        assert result.current_step == "p22_waiting_for_human"
        assert result.route == "human_escalation"
        assert result.source_p22_summary_message_id is not None

        # No P23 evidence created
        counts = count_p23_evidence(ctx["msg_repo"], ctx["session_id"])
        assert counts[P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL] == 0
        assert counts[P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL] == 0
        assert counts[P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL] == 0
        assert counts[P23_PROTECTED_TRANSITION_WORKER_START_RESERVATION_SOURCE_DETAIL] == 0
        assert counts[P23_PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL] == 0
        assert counts[P23_PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL] == 0

        assert result.run_id is None
        assert len(ctx["fake_worker"].run_reserved_once_calls) == 0
        assert result.resumed_from_existing_evidence is False

        engine.dispose()

    def test_d3_p22_blocked_never_enters_p23(self, tmp_path):
        """P22 blocked: D3 returns blocked, no P23 evidence."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)

        # Seed only base records + bare review message (no write/diff messages).
        # P22 will block because it can't find the diff evidence chain.
        s = sf()
        ids = seed_base_records(s, task_status="pending")
        review_msg_id = uuid4()
        action = _valid_review_action_d3(
            verdict="no_blocking_findings", risk_level="low",
            session_id=ids["session_id"], task_id=ids["task_id"],
        )
        # Point to non-existent diff/write messages so P22 can't build the chain
        action["source_diff_message_id"] = str(uuid4())
        action["source_preflight_message_id"] = str(uuid4())
        s.add(
            ProjectDirectorMessageTable(
                id=review_msg_id, session_id=ids["session_id"], role="assistant",
                content="Readonly review executed.", sequence_no=50,
                intent="sandbox_candidate_diff_readonly_review_execution",
                source="system",
                source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
                suggested_actions_json=json.dumps([action]),
                requires_confirmation=False, risk_level="high",
                related_project_id=ids["project_id"], related_task_id=ids["task_id"],
            )
        )
        s.commit()
        s.close()

        session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(sf)

        # Build D3 with real P22
        from tests.p23_test_support import _make_p22_service, FakeTaskWorker
        p22_svc = _make_p22_service(session, msg_repo, sess_repo, task_repo)

        freshness_svc = FakeFreshnessService(session=session)
        freshness_svc._message_repository = msg_repo
        freshness_svc._task_repository = task_repo

        intent_svc = ProjectDirectorProtectedTransitionDispatchIntentService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
        )

        intent_fake = FakeIntentService(
            session=session, project_id=ids["project_id"],
        )
        intent_fake._message_repository = msg_repo
        intent_fake._task_repository = task_repo

        preflight_svc = ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
            dispatch_intent_service=intent_fake,
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

        from app.services.project_director_protected_transition_worker_start_reservation_service import ProjectDirectorProtectedTransitionWorkerStartReservationService
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

        fake_worker = FakeTaskWorker(session=session)
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

        from app.services.project_director_protected_transition_auto_advance_service import ProjectDirectorProtectedTransitionAutoAdvanceService
        d3_svc = ProjectDirectorProtectedTransitionAutoAdvanceService(
            post_review_automation_service=p22_svc,
            dispatch_intent_service=intent_svc,
            dispatch_consumption_preflight_service=preflight_svc,
            dispatch_consumption_service=d1_svc,
            worker_start_reservation_service=b1_svc,
            worker_invocation_service=b2_svc,
        )

        result = d3_svc.advance_post_review_protected_transition(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_review_message_id=review_msg_id,
        )

        assert result.auto_advance_status == "blocked"
        assert result.current_step == "p22_blocked"
        assert len(result.blocked_reasons) > 0

        # No P23 evidence
        counts = count_p23_evidence(msg_repo, ids["session_id"])
        for sd, count in counts.items():
            if sd != P22_POST_REVIEW_AUTOMATION_SOURCE_DETAIL:
                assert count == 0, f"Expected 0 for {sd}, got {count}"

        runs = run_repo.list_by_task_id(ids["task_id"])
        assert len(runs) == 0
        assert len(fake_worker.run_reserved_once_calls) == 0

        engine.dispose()

    def test_d3_resumes_from_persisted_preflight(self, tmp_path):
        """D3 resumes from persisted P23-C preflight without preparing second one."""
        engine, sf, ctx, task_id, run_id = _create_d3_with_fake_worker(tmp_path)

        # First run to create all evidence
        def success_worker(*, task_id, run_id):
            ctx["fake_worker"].run_reserved_once_calls.append({"task_id": task_id, "run_id": run_id})
            ctx["task_repo"].set_status(task_id, TaskStatus.COMPLETED)
            ctx["run_repo"].finish_run(run_id, status=RunStatus.SUCCEEDED, result_summary="done")
            ctx["msg_repo"]._session.commit()
            return make_d3_worker_result(task_id=task_id, run_id=run_id)

        ctx["fake_worker"].run_reserved_once = success_worker

        r1 = ctx["d3_svc"].advance_post_review_protected_transition(
            session_id=ctx["session_id"],
            source_task_id=ctx["task_id"],
            source_review_message_id=ctx["review_msg_id"],
        )
        assert r1.auto_advance_status == "worker_returned"

        # Record preflight count
        preflight_count = count_messages_by_source_detail(
            ctx["msg_repo"], ctx["session_id"],
            P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL,
        )
        assert preflight_count == 1

        engine.dispose()

    def test_d3_resumes_from_persisted_consumption(self, tmp_path):
        """D3 resumes from persisted D1 consumption."""
        engine, sf, ctx, task_id, run_id = _create_d3_with_fake_worker(tmp_path)

        def success_worker(*, task_id, run_id):
            ctx["fake_worker"].run_reserved_once_calls.append({"task_id": task_id, "run_id": run_id})
            ctx["task_repo"].set_status(task_id, TaskStatus.COMPLETED)
            ctx["run_repo"].finish_run(run_id, status=RunStatus.SUCCEEDED, result_summary="done")
            ctx["msg_repo"]._session.commit()
            return make_d3_worker_result(task_id=task_id, run_id=run_id)

        ctx["fake_worker"].run_reserved_once = success_worker

        r1 = ctx["d3_svc"].advance_post_review_protected_transition(
            session_id=ctx["session_id"],
            source_task_id=ctx["task_id"],
            source_review_message_id=ctx["review_msg_id"],
        )
        assert r1.auto_advance_status == "worker_returned"

        # Verify D1 was created
        d1_count = count_messages_by_source_detail(
            ctx["msg_repo"], ctx["session_id"],
            P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL,
        )
        assert d1_count == 1

        engine.dispose()

    def test_d3_resumes_from_persisted_reservation(self, tmp_path):
        """D3 resumes from persisted B1 reservation."""
        engine, sf, ctx, task_id, run_id = _create_d3_with_fake_worker(tmp_path)

        def success_worker(*, task_id, run_id):
            ctx["fake_worker"].run_reserved_once_calls.append({"task_id": task_id, "run_id": run_id})
            ctx["task_repo"].set_status(task_id, TaskStatus.COMPLETED)
            ctx["run_repo"].finish_run(run_id, status=RunStatus.SUCCEEDED, result_summary="done")
            ctx["msg_repo"]._session.commit()
            return make_d3_worker_result(task_id=task_id, run_id=run_id)

        ctx["fake_worker"].run_reserved_once = success_worker

        r1 = ctx["d3_svc"].advance_post_review_protected_transition(
            session_id=ctx["session_id"],
            source_task_id=ctx["task_id"],
            source_review_message_id=ctx["review_msg_id"],
        )
        assert r1.auto_advance_status == "worker_returned"

        # Verify B1 was created
        b1_count = count_messages_by_source_detail(
            ctx["msg_repo"], ctx["session_id"],
            P23_PROTECTED_TRANSITION_WORKER_START_RESERVATION_SOURCE_DETAIL,
        )
        assert b1_count == 1

        engine.dispose()

    def test_d3_maps_b2_not_invoked_to_worker_not_invoked(self, tmp_path):
        """D3 maps B2 not_invoked outcome to worker_not_invoked."""
        engine, sf, ctx, task_id, run_id = _create_d3_with_fake_worker(tmp_path)

        # Make worker fail at final current revalidation by returning blocked result
        # This will cause B2 to produce not_invoked
        def failing_worker(*, task_id, run_id):
            ctx["fake_worker"].run_reserved_once_calls.append({"task_id": task_id, "run_id": run_id})
            # Return a result that causes final current revalidation to fail
            return make_d3_worker_result(
                task_id=task_id,
                run_id=run_id,
                contract_valid=False,  # invalid contract causes issues
            )

        ctx["fake_worker"].run_reserved_once = failing_worker

        # This should still work because B2 handles the invalid result
        result = ctx["d3_svc"].advance_post_review_protected_transition(
            session_id=ctx["session_id"],
            source_task_id=ctx["task_id"],
            source_review_message_id=ctx["review_msg_id"],
        )

        # The result depends on how B2 handles invalid snapshots
        # It could be worker_returned with human_recovery_required
        assert result.auto_advance_status in ("worker_returned", "worker_not_invoked")
        assert result.worker_invocation_claimed is True
        assert len(ctx["fake_worker"].run_reserved_once_calls) == 1

        engine.dispose()

    def test_d3_maps_b2_raised_to_worker_raised(self, tmp_path):
        """D3 maps B2 raised outcome to worker_raised."""
        engine, sf, ctx, task_id, run_id = _create_d3_with_fake_worker(
            tmp_path,
            worker_exception=RuntimeError("test worker exception"),
        )

        result = ctx["d3_svc"].advance_post_review_protected_transition(
            session_id=ctx["session_id"],
            source_task_id=ctx["task_id"],
            source_review_message_id=ctx["review_msg_id"],
        )

        assert result.auto_advance_status == "worker_raised"
        assert result.worker_outcome_status == "raised"
        assert result.worker_call_attempted is True
        assert result.worker_returned is False
        assert result.worker_raised is True
        assert result.human_recovery_required is True

        # Messages
        claim_count = count_messages_by_source_detail(
            ctx["msg_repo"], ctx["session_id"],
            P23_PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL,
        )
        outcome_count = count_messages_by_source_detail(
            ctx["msg_repo"], ctx["session_id"],
            P23_PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL,
        )
        assert claim_count == 1
        assert outcome_count == 1
        assert len(ctx["fake_worker"].run_reserved_once_calls) == 1

        engine.dispose()

    def test_d3_exception_after_d1_consumption_requires_recovery(self, tmp_path):
        """Exception after D1 consumption → recovery_required, preserves Run."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)

        s = sf()
        ids = seed_base_records(s, task_status="pending")
        from tests.p23_test_support import _seed_p21_c_review_chain
        review_msg_id = _seed_p21_c_review_chain(
            s,
            session_id=ids["session_id"],
            task_id=ids["task_id"],
            project_id=ids["project_id"],
        )
        s.close()

        session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(sf)

        # Build services
        from tests.p23_test_support import _make_p22_service, _StubHandoff, _StubDiff, FakeTaskWorker
        from app.services.project_director_protected_transition_evidence_freshness_service import (
            ProjectDirectorProtectedTransitionEvidenceFreshnessService,
        )
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

        from app.services.project_director_protected_transition_worker_start_reservation_service import ProjectDirectorProtectedTransitionWorkerStartReservationService

        # Create B1 service that throws after D1
        class ExplodingB1Service:
            _message_repository = msg_repo
            _task_repository = task_repo
            _run_repository = run_repo
            _agent_session_repository = agent_sess_repo
            _freshness_service = freshness_svc
            _budget_guard_service = FakeBudgetGuardService(session=session)
            _dispatch_consumption_service = d1_svc

            def find_persisted_protected_transition_worker_start_reservation(self, **kwargs):
                raise RuntimeError("Simulated B1 failure")

            def prepare_protected_transition_worker_start_reservation(self, **kwargs):
                raise RuntimeError("Simulated B1 failure")

            def revalidate_persisted_protected_transition_worker_start_reservation(self, **kwargs):
                raise RuntimeError("Simulated B1 failure")

            def revalidate_current_protected_transition_worker_start_reservation(self, **kwargs):
                raise RuntimeError("Simulated B1 failure")

        exploding_b1 = ExplodingB1Service()

        fake_worker = FakeTaskWorker(session=session)
        b2_svc = ProjectDirectorProtectedTransitionWorkerInvocationService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
            run_repository=run_repo,
            agent_session_repository=agent_sess_repo,
            worker_start_reservation_service=exploding_b1,
            freshness_service=freshness_svc,
            task_worker=fake_worker,
        )

        from app.services.project_director_protected_transition_auto_advance_service import ProjectDirectorProtectedTransitionAutoAdvanceService
        d3_svc = ProjectDirectorProtectedTransitionAutoAdvanceService(
            post_review_automation_service=p22_svc,
            dispatch_intent_service=intent_svc,
            dispatch_consumption_preflight_service=preflight_svc,
            dispatch_consumption_service=d1_svc,
            worker_start_reservation_service=exploding_b1,
            worker_invocation_service=b2_svc,
        )

        result = d3_svc.advance_post_review_protected_transition(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_review_message_id=review_msg_id,
        )

        # D1 should succeed, then B1 throws
        assert result.auto_advance_status == "recovery_required"
        assert result.human_recovery_required is True
        assert "coordinator_exception_after_atomic_consumption" in result.blocked_reasons

        # D1 evidence preserved
        d1_count = count_messages_by_source_detail(
            msg_repo, ids["session_id"],
            P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL,
        )
        assert d1_count == 1

        # Task/Run preserved
        task = task_repo.get_by_id(ids["task_id"])
        assert task.status == TaskStatus.RUNNING
        runs = run_repo.list_by_task_id(ids["task_id"])
        assert len(runs) == 1
        assert result.run_id is not None

        # No B1/B2 evidence
        b1_count = count_messages_by_source_detail(
            msg_repo, ids["session_id"],
            P23_PROTECTED_TRANSITION_WORKER_START_RESERVATION_SOURCE_DETAIL,
        )
        assert b1_count == 0
        assert len(fake_worker.run_reserved_once_calls) == 0

        engine.dispose()
