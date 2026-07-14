"""P24-G Behavioral tests for E3B Claim Service and E4B Outcome Service."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.db_tables import (
    ORMBase,
    ProjectDirectorMessageTable,
    ProjectDirectorSessionTable,
    ProjectTable,
    RunTable,
    TaskTable,
)
from app.domain.project_director_cross_task_exact_worker_invocation_claim import (
    CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL,
    ProjectDirectorCrossTaskExactWorkerInvocationClaimResult,
)
from app.domain.project_director_cross_task_exact_worker_invocation_outcome import (
    CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL,
    ProjectDirectorCrossTaskExactWorkerInvocationOutcomeResult,
)
from app.domain.project_role import ProjectRoleCode
from app.domain.run import (
    RunBudgetPressureLevel,
    RunBudgetStrategyAction,
    RunStrategyDecision,
    RunStrategyReasonItem,
)
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.workers.task_worker import (
    WorkerReservedRunExecutionSnapshot,
    WorkerRunResult,
)

from tests.p24_test_support import (
    FakeTaskWorker,
    build_p24_chain,
    build_valid_outcome,
    count_messages_by_source_detail,
    make_claim_service,
    make_outcome_service,
    make_repos,
    make_test_engine,
    make_session_factory,
    seed_base_records,
    seed_claim_message,
    seed_e1b_message,
    seed_e2a_message,
    seed_full_p24_chain,
    seed_outcome_message,
    seed_package_message,
    seed_root_message,
    seed_run,
)


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def engine(tmp_path):
    return make_test_engine(str(tmp_path / "test.db"))


@pytest.fixture
def session_local(engine):
    return make_session_factory(engine)


# ── E3B Claim Service Tests ─────────────────────────────────────────


class TestE3BClaimService:
    """E3B Claim Service dynamic tests."""

    def test_first_claim_creates_message(self, session_local):
        """First exact call creates invocation_claim_created with one message."""
        chain = build_p24_chain()
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
        )
        s.close()

        session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
        claim_svc = make_claim_service(
            session,
            msg_repo=msg_repo,
            task_repo=task_repo,
            run_repo=run_repo,
            agent_sess_repo=agent_sess_repo,
        )

        result = claim_svc.claim_exact_worker_invocation(
            session_id=chain.session_id,
            project_id=chain.project_id,
            continuation_root_record_id=chain.root_record_id,
            instruction_package_id=chain.package_id,
            exact_run_reservation_id=chain.exact_run_reservation_id,
            exact_worker_start_reservation_id=chain.worker_start_reservation_id,
        )

        assert result.status == "invocation_claim_created"
        assert result.automatic_worker_call_allowed is True
        assert result.claim is not None
        assert count_messages_by_source_detail(
            msg_repo, chain.session_id,
            CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL,
        ) == 1

    def test_second_call_replays_claim(self, session_local):
        """Second call with same IDs replays claim, no new message."""
        chain = build_p24_chain()
        s = session_local()
        seed_base_records(
            s,
            session_id=chain.session_id,
            project_id=chain.project_id,
            task_id=chain.next_task_id,
            plan_version_id=chain.plan_version_id,
            task_status="running",
        )
        seed_full_p24_chain(s, chain)
        seed_run(
            s,
            run_id=chain.exact_run_id,
            task_id=chain.next_task_id,
            model_name=chain.claim.worker_model_name,
            started_at=chain.claim.exact_run_started_at,
            created_at=chain.claim.exact_run_created_at,
        )
        s.close()

        session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
        claim_svc = make_claim_service(
            session,
            msg_repo=msg_repo,
            task_repo=task_repo,
            run_repo=run_repo,
            agent_sess_repo=agent_sess_repo,
        )

        result = claim_svc.claim_exact_worker_invocation(
            session_id=chain.session_id,
            project_id=chain.project_id,
            continuation_root_record_id=chain.root_record_id,
            instruction_package_id=chain.package_id,
            exact_run_reservation_id=chain.exact_run_reservation_id,
            exact_worker_start_reservation_id=chain.worker_start_reservation_id,
        )

        assert result.status == "invocation_claim_replayed"
        assert result.automatic_worker_call_allowed is False
        assert result.claim is not None
        assert result.claim.exact_worker_invocation_claim_id == chain.claim_id
        assert count_messages_by_source_detail(
            msg_repo, chain.session_id,
            CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL,
        ) == 1

    def test_claim_rollback_on_persistence_failure(self, session_local):
        """Claim rollback leaves no half-written record."""
        chain = build_p24_chain()
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
        )
        s.close()

        session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
        claim_svc = make_claim_service(
            session,
            msg_repo=msg_repo,
            task_repo=task_repo,
            run_repo=run_repo,
            agent_sess_repo=agent_sess_repo,
        )

        # Monkey-patch _create_message to simulate failure
        original_create = claim_svc._create_message

        def failing_create(message):
            raise ValueError("Simulated persistence failure")

        claim_svc._create_message = failing_create

        result = claim_svc.claim_exact_worker_invocation(
            session_id=chain.session_id,
            project_id=chain.project_id,
            continuation_root_record_id=chain.root_record_id,
            instruction_package_id=chain.package_id,
            exact_run_reservation_id=chain.exact_run_reservation_id,
            exact_worker_start_reservation_id=chain.worker_start_reservation_id,
        )

        assert result.status == "blocked"
        assert result.claim is None
        assert count_messages_by_source_detail(
            msg_repo, chain.session_id,
            CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL,
        ) == 0


# ── E4B Outcome Service Tests ──────────────────────────────────────


class TestE4BOutcomeService:
    """E4B Outcome Service behavioral tests."""

    def test_happy_path_new_claim_worker_called(self, session_local):
        """New claim → Worker called once → Outcome recorded."""
        chain = build_p24_chain()
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
                selected_skill_codes=[s.skill_code for s in chain.claim.worker_selected_skills],
                selected_skill_names=[s.skill_name for s in chain.claim.worker_selected_skills],
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

        # Build valid worker result
        snapshot = WorkerReservedRunExecutionSnapshot(
            source="p23_d2_exact_reserved_run",
            exact_task_id=chain.next_task_id,
            exact_run_id=chain.exact_run_id,
            reserved_run_execution_requested=True,
            exact_binding_validated=True,
            task_routed=False,
            task_claimed_in_this_cycle=False,
            run_created_in_this_cycle=False,
            budget_rechecked=True,
            existing_run_reused=True,
            shared_execution_seam_used=True,
            product_runtime_git_write_allowed=False,
            blocked_reasons=[],
        )
        worker_result = WorkerRunResult(
            claimed=True,
            message="fake worker executed",
            execution_mode="fake",
            result_summary="fake execution",
            model_name=chain.claim.worker_model_name,
            model_tier=chain.claim.worker_model_tier,
            selected_skill_codes=[s.skill_code for s in chain.claim.worker_selected_skills],
            selected_skill_names=[s.skill_name for s in chain.claim.worker_selected_skills],
            owner_role_code=chain.claim.worker_owner_role_code,
            upstream_role_code=chain.claim.worker_upstream_role_code,
            downstream_role_code=chain.claim.worker_downstream_role_code,
            route_reason="test",
            strategy_code="normal",
            dispatch_status="dispatched",
            reserved_run_execution_snapshot=snapshot,
        )
        fake_worker = FakeTaskWorker(session=None, result=worker_result)

        session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
        outcome_svc = make_outcome_service(
            session,
            msg_repo=msg_repo,
            task_repo=task_repo,
            run_repo=run_repo,
            agent_sess_repo=agent_sess_repo,
            task_worker=fake_worker,
        )

        result = outcome_svc.invoke_exact_worker(
            session_id=chain.session_id,
            project_id=chain.project_id,
            continuation_root_record_id=chain.root_record_id,
            instruction_package_id=chain.package_id,
            exact_run_reservation_id=chain.exact_run_reservation_id,
            exact_worker_start_reservation_id=chain.worker_start_reservation_id,
        )

        assert result.status == "outcome_recorded"
        assert result.outcome is not None
        assert result.outcome.status == "returned"
        assert result.outcome.worker_call_attempted is True
        assert result.outcome.worker_result_contract_valid is True
        assert result.outcome.human_recovery_required is False
        assert fake_worker.call_count == 1
        assert fake_worker.run_reserved_once_calls[0]["task_id"] == chain.next_task_id
        assert fake_worker.run_reserved_once_calls[0]["run_id"] == chain.exact_run_id
        assert count_messages_by_source_detail(
            msg_repo, chain.session_id,
            CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL,
        ) == 1
        assert count_messages_by_source_detail(
            msg_repo, chain.session_id,
            CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL,
        ) == 1

    def test_replay_outcome(self, session_local):
        """Third call replays original outcome."""
        chain = build_p24_chain()
        s = session_local()
        seed_base_records(
            s,
            session_id=chain.session_id,
            project_id=chain.project_id,
            task_id=chain.next_task_id,
            plan_version_id=chain.plan_version_id,
            task_status="running",
        )
        seed_full_p24_chain(s, chain)
        outcome = build_valid_outcome(chain, status="returned")
        seed_outcome_message(s, outcome)
        seed_run(
            s,
            run_id=chain.exact_run_id,
            task_id=chain.next_task_id,
            model_name=chain.claim.worker_model_name,
            started_at=chain.claim.exact_run_started_at,
            created_at=chain.claim.exact_run_created_at,
        )
        s.close()

        fake_worker = FakeTaskWorker(session=None)
        session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
        outcome_svc = make_outcome_service(
            session,
            msg_repo=msg_repo,
            task_repo=task_repo,
            run_repo=run_repo,
            agent_sess_repo=agent_sess_repo,
            task_worker=fake_worker,
        )

        result = outcome_svc.invoke_exact_worker(
            session_id=chain.session_id,
            project_id=chain.project_id,
            continuation_root_record_id=chain.root_record_id,
            instruction_package_id=chain.package_id,
            exact_run_reservation_id=chain.exact_run_reservation_id,
            exact_worker_start_reservation_id=chain.worker_start_reservation_id,
        )

        assert result.status == "outcome_replayed"
        assert result.outcome is not None
        assert result.outcome.exact_worker_invocation_outcome_id == outcome.exact_worker_invocation_outcome_id
        assert result.resumed_from_existing_outcome is True
        assert fake_worker.call_count == 0

    def test_claim_without_outcome_recovery(self, session_local):
        """Claim exists but no Outcome → recovery_required."""
        chain = build_p24_chain()
        s = session_local()
        seed_base_records(
            s,
            session_id=chain.session_id,
            project_id=chain.project_id,
            task_id=chain.next_task_id,
            plan_version_id=chain.plan_version_id,
            task_status="running",
        )
        seed_full_p24_chain(s, chain)
        # Don't seed outcome
        seed_run(
            s,
            run_id=chain.exact_run_id,
            task_id=chain.next_task_id,
            model_name=chain.claim.worker_model_name,
            started_at=chain.claim.exact_run_started_at,
            created_at=chain.claim.exact_run_created_at,
        )
        s.close()

        fake_worker = FakeTaskWorker(session=None)
        session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
        outcome_svc = make_outcome_service(
            session,
            msg_repo=msg_repo,
            task_repo=task_repo,
            run_repo=run_repo,
            agent_sess_repo=agent_sess_repo,
            task_worker=fake_worker,
        )

        result = outcome_svc.invoke_exact_worker(
            session_id=chain.session_id,
            project_id=chain.project_id,
            continuation_root_record_id=chain.root_record_id,
            instruction_package_id=chain.package_id,
            exact_run_reservation_id=chain.exact_run_reservation_id,
            exact_worker_start_reservation_id=chain.worker_start_reservation_id,
        )

        assert result.status == "recovery_required"
        assert result.outcome is None
        assert result.worker_call_state_indeterminate is True
        assert result.automatic_worker_call_allowed is False
        assert fake_worker.call_count == 0

    def test_worker_raises_exception(self, session_local):
        """Worker exception → raised outcome."""
        chain = build_p24_chain()
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
                selected_skill_codes=[s.skill_code for s in chain.claim.worker_selected_skills],
                selected_skill_names=[s.skill_name for s in chain.claim.worker_selected_skills],
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

        fake_worker = FakeTaskWorker(
            session=None,
            exception=RuntimeError("Worker failed"),
        )

        session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
        outcome_svc = make_outcome_service(
            session,
            msg_repo=msg_repo,
            task_repo=task_repo,
            run_repo=run_repo,
            agent_sess_repo=agent_sess_repo,
            task_worker=fake_worker,
        )

        result = outcome_svc.invoke_exact_worker(
            session_id=chain.session_id,
            project_id=chain.project_id,
            continuation_root_record_id=chain.root_record_id,
            instruction_package_id=chain.package_id,
            exact_run_reservation_id=chain.exact_run_reservation_id,
            exact_worker_start_reservation_id=chain.worker_start_reservation_id,
        )

        assert result.status == "outcome_recorded"
        assert result.outcome is not None
        assert result.outcome.status == "raised"
        assert result.outcome.worker_raised is True
        assert result.outcome.worker_result_contract_valid is False
        assert result.outcome.human_recovery_required is True
        assert result.outcome.exception_type == "RuntimeError"
        assert fake_worker.call_count == 1

    def test_worker_returns_non_formal_object(self, session_local):
        """Worker returns non-WorkerRunResult → returned-invalid."""
        chain = build_p24_chain()
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
                selected_skill_codes=[s.skill_code for s in chain.claim.worker_selected_skills],
                selected_skill_names=[s.skill_name for s in chain.claim.worker_selected_skills],
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

        fake_worker = FakeTaskWorker(session=None, result={"not": "a WorkerRunResult"})

        session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
        outcome_svc = make_outcome_service(
            session,
            msg_repo=msg_repo,
            task_repo=task_repo,
            run_repo=run_repo,
            agent_sess_repo=agent_sess_repo,
            task_worker=fake_worker,
        )

        result = outcome_svc.invoke_exact_worker(
            session_id=chain.session_id,
            project_id=chain.project_id,
            continuation_root_record_id=chain.root_record_id,
            instruction_package_id=chain.package_id,
            exact_run_reservation_id=chain.exact_run_reservation_id,
            exact_worker_start_reservation_id=chain.worker_start_reservation_id,
        )

        assert result.status == "outcome_recorded"
        assert result.outcome is not None
        assert result.outcome.status == "returned"
        assert result.outcome.worker_result_contract_valid is False
        assert result.outcome.human_recovery_required is True
        assert fake_worker.call_count == 1

    def test_pre_call_revalidation_failure(self, session_local):
        """Task no longer running → not_invoked outcome."""
        chain = build_p24_chain()
        s = session_local()
        seed_base_records(
            s,
            session_id=chain.session_id,
            project_id=chain.project_id,
            task_id=chain.next_task_id,
            plan_version_id=chain.plan_version_id,
            task_status="completed",  # Not running!
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
        )
        s.close()

        fake_worker = FakeTaskWorker(session=None)

        session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
        outcome_svc = make_outcome_service(
            session,
            msg_repo=msg_repo,
            task_repo=task_repo,
            run_repo=run_repo,
            agent_sess_repo=agent_sess_repo,
            task_worker=fake_worker,
        )

        result = outcome_svc.invoke_exact_worker(
            session_id=chain.session_id,
            project_id=chain.project_id,
            continuation_root_record_id=chain.root_record_id,
            instruction_package_id=chain.package_id,
            exact_run_reservation_id=chain.exact_run_reservation_id,
            exact_worker_start_reservation_id=chain.worker_start_reservation_id,
        )

        # Should be blocked or outcome_recorded with not_invoked
        assert result.automatic_worker_call_allowed is False
        assert fake_worker.call_count == 0

    def test_git_boundary_violation(self, session_local):
        """Worker reports git write activity → contract invalid."""
        chain = build_p24_chain()
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
                selected_skill_codes=[s.skill_code for s in chain.claim.worker_selected_skills],
                selected_skill_names=[s.skill_name for s in chain.claim.worker_selected_skills],
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

        snapshot = WorkerReservedRunExecutionSnapshot(
            source="p23_d2_exact_reserved_run",
            exact_task_id=chain.next_task_id,
            exact_run_id=chain.exact_run_id,
            reserved_run_execution_requested=True,
            exact_binding_validated=True,
            task_routed=False,
            task_claimed_in_this_cycle=False,
            run_created_in_this_cycle=False,
            budget_rechecked=True,
            existing_run_reused=True,
            shared_execution_seam_used=True,
            product_runtime_git_write_allowed=False,
            blocked_reasons=[],
        )
        worker_result = WorkerRunResult(
            claimed=True,
            message="fake worker executed",
            execution_mode="fake",
            result_summary="fake execution",
            model_name=chain.claim.worker_model_name,
            model_tier=chain.claim.worker_model_tier,
            selected_skill_codes=[s.skill_code for s in chain.claim.worker_selected_skills],
            selected_skill_names=[s.skill_name for s in chain.claim.worker_selected_skills],
            owner_role_code=chain.claim.worker_owner_role_code,
            upstream_role_code=chain.claim.worker_upstream_role_code,
            downstream_role_code=chain.claim.worker_downstream_role_code,
            route_reason="test",
            strategy_code="normal",
            dispatch_status="dispatched",
            reserved_run_execution_snapshot=snapshot,
            git_diff_dry_run_git_commit_triggered=True,  # Git activity!
        )
        fake_worker = FakeTaskWorker(session=None, result=worker_result)

        session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
        outcome_svc = make_outcome_service(
            session,
            msg_repo=msg_repo,
            task_repo=task_repo,
            run_repo=run_repo,
            agent_sess_repo=agent_sess_repo,
            task_worker=fake_worker,
        )

        result = outcome_svc.invoke_exact_worker(
            session_id=chain.session_id,
            project_id=chain.project_id,
            continuation_root_record_id=chain.root_record_id,
            instruction_package_id=chain.package_id,
            exact_run_reservation_id=chain.exact_run_reservation_id,
            exact_worker_start_reservation_id=chain.worker_start_reservation_id,
        )

        assert result.status == "outcome_recorded"
        assert result.outcome is not None
        assert result.outcome.worker_result_contract_valid is False
        assert result.outcome.human_recovery_required is True
        assert result.outcome.product_runtime_git_write_allowed is False

    def test_budget_rechecked_true_and_false(self, session_local):
        """budget_rechecked true and false both produce valid outcomes."""
        for budget_rechecked in [True, False]:
            chain = build_p24_chain()
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

            snapshot = WorkerReservedRunExecutionSnapshot(
                source="p23_d2_exact_reserved_run",
                exact_task_id=chain.next_task_id,
                exact_run_id=chain.exact_run_id,
                reserved_run_execution_requested=True,
                exact_binding_validated=True,
                task_routed=False,
                task_claimed_in_this_cycle=False,
                run_created_in_this_cycle=False,
                budget_rechecked=budget_rechecked,
                existing_run_reused=True,
                shared_execution_seam_used=True,
                product_runtime_git_write_allowed=False,
                blocked_reasons=[],
            )
            worker_result = WorkerRunResult(
                claimed=True,
                message="fake worker executed",
                execution_mode="fake",
                result_summary="fake execution",
                model_name=chain.claim.worker_model_name,
                model_tier=chain.claim.worker_model_tier,
                selected_skill_codes=[sk.skill_code for sk in chain.claim.worker_selected_skills],
                selected_skill_names=[sk.skill_name for sk in chain.claim.worker_selected_skills],
                owner_role_code=chain.claim.worker_owner_role_code,
                upstream_role_code=chain.claim.worker_upstream_role_code,
                downstream_role_code=chain.claim.worker_downstream_role_code,
                route_reason="test",
                strategy_code="normal",
                dispatch_status="dispatched",
                reserved_run_execution_snapshot=snapshot,
            )
            fake_worker = FakeTaskWorker(session=None, result=worker_result)

            session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
            outcome_svc = make_outcome_service(
                session,
                msg_repo=msg_repo,
                task_repo=task_repo,
                run_repo=run_repo,
                agent_sess_repo=agent_sess_repo,
                task_worker=fake_worker,
            )

            result = outcome_svc.invoke_exact_worker(
                session_id=chain.session_id,
                project_id=chain.project_id,
                continuation_root_record_id=chain.root_record_id,
                instruction_package_id=chain.package_id,
                exact_run_reservation_id=chain.exact_run_reservation_id,
                exact_worker_start_reservation_id=chain.worker_start_reservation_id,
            )

            assert result.status == "outcome_recorded"
            assert result.outcome is not None
            assert result.outcome.worker_result_contract_valid is True
            assert result.outcome.reserved_snapshot_budget_rechecked == budget_rechecked
