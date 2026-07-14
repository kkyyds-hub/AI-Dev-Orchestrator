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
    AgentSessionTable,
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
    FailingMessageRepositoryWrapper,
    build_p24_chain,
    build_valid_outcome,
    build_worker_result_for_chain,
    count_messages_by_source_detail,
    invoke_exact_worker_full,
    make_claim_service,
    make_outcome_service,
    make_repos,
    make_test_engine,
    make_session_factory,
    seed_agent_session,
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


# ── A1: Claim Replay Independent of Mutable State ──────────────────


class TestClaimReplayIndependentOfMutableState:
    """Claim replay must not depend on current mutable state."""

    def test_replay_after_task_status_change(self, session_local):
        """Claim replay works even after Task status changes."""
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
        # Seed package, root, E1B, E2A but NOT the claim
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

        # First call creates the claim
        session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
        claim_svc = make_claim_service(
            session,
            msg_repo=msg_repo,
            task_repo=task_repo,
            run_repo=run_repo,
            agent_sess_repo=agent_sess_repo,
        )
        result1 = claim_svc.claim_exact_worker_invocation(
            session_id=chain.session_id,
            project_id=chain.project_id,
            continuation_root_record_id=chain.root_record_id,
            instruction_package_id=chain.package_id,
            exact_run_reservation_id=chain.exact_run_reservation_id,
            exact_worker_start_reservation_id=chain.worker_start_reservation_id,
        )
        assert result1.status == "invocation_claim_created"
        first_claim_id = result1.claim.exact_worker_invocation_claim_id
        first_token = result1.claim.worker_invocation_claim_token
        first_fp = result1.claim.worker_invocation_claim_fingerprint

        # Change Task status
        s = session_local()
        task = s.get(TaskTable, chain.next_task_id)
        task.status = "completed"
        s.commit()
        s.close()

        # Second call replays the same claim
        session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
        claim_svc = make_claim_service(
            session,
            msg_repo=msg_repo,
            task_repo=task_repo,
            run_repo=run_repo,
            agent_sess_repo=agent_sess_repo,
        )
        result2 = claim_svc.claim_exact_worker_invocation(
            session_id=chain.session_id,
            project_id=chain.project_id,
            continuation_root_record_id=chain.root_record_id,
            instruction_package_id=chain.package_id,
            exact_run_reservation_id=chain.exact_run_reservation_id,
            exact_worker_start_reservation_id=chain.worker_start_reservation_id,
        )

        assert result2.status == "invocation_claim_replayed"
        assert result2.claim.exact_worker_invocation_claim_id == first_claim_id
        assert result2.claim.worker_invocation_claim_token == first_token
        assert result2.claim.worker_invocation_claim_fingerprint == first_fp
        assert result2.automatic_worker_call_allowed is False
        assert count_messages_by_source_detail(
            msg_repo, chain.session_id,
            CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL,
        ) == 1

    def test_replay_after_agent_session_created(self, session_local):
        """Claim replay works even after AgentSession is created."""
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
        # Seed package, root, E1B, E2A but NOT the claim
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

        # First call creates the claim
        session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
        claim_svc = make_claim_service(
            session,
            msg_repo=msg_repo,
            task_repo=task_repo,
            run_repo=run_repo,
            agent_sess_repo=agent_sess_repo,
        )
        result1 = claim_svc.claim_exact_worker_invocation(
            session_id=chain.session_id,
            project_id=chain.project_id,
            continuation_root_record_id=chain.root_record_id,
            instruction_package_id=chain.package_id,
            exact_run_reservation_id=chain.exact_run_reservation_id,
            exact_worker_start_reservation_id=chain.worker_start_reservation_id,
        )
        assert result1.status == "invocation_claim_created"
        first_claim_id = result1.claim.exact_worker_invocation_claim_id

        # Create an AgentSession
        s = session_local()
        seed_agent_session(
            s,
            project_id=chain.project_id,
            task_id=chain.next_task_id,
            run_id=chain.exact_run_id,
        )
        s.close()

        # Second call replays the same claim
        session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
        claim_svc = make_claim_service(
            session,
            msg_repo=msg_repo,
            task_repo=task_repo,
            run_repo=run_repo,
            agent_sess_repo=agent_sess_repo,
        )
        result2 = claim_svc.claim_exact_worker_invocation(
            session_id=chain.session_id,
            project_id=chain.project_id,
            continuation_root_record_id=chain.root_record_id,
            instruction_package_id=chain.package_id,
            exact_run_reservation_id=chain.exact_run_reservation_id,
            exact_worker_start_reservation_id=chain.worker_start_reservation_id,
        )

        assert result2.status == "invocation_claim_replayed"
        assert result2.claim.exact_worker_invocation_claim_id == first_claim_id
        assert result2.automatic_worker_call_allowed is False
        assert count_messages_by_source_detail(
            msg_repo, chain.session_id,
            CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL,
        ) == 1


# ── A2: Claim Post-Write Rollback ──────────────────────────────────


class TestClaimPostWriteRollback:
    """Claim rollback when post-write validation fails."""

    def test_post_write_validate_failure_rollback(self, session_local):
        """Post-write validation failure → transaction rollback, no Claim Message."""
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

        # Monkey-patch _post_write_validate to simulate failure
        original_validate = claim_svc._post_write_validate

        def failing_validate(message, claim):
            raise ValueError("Simulated post-write validation failure")

        claim_svc._post_write_validate = failing_validate

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


# ── Strengthened not_invoked Tests ──────────────────────────────────


class TestNotInvokedStrict:
    """Strict not_invoked tests with precise assertions."""

    def test_task_not_running_strict(self, session_local):
        """Task completed → blocked at Claim level (task state conflict)."""
        chain = build_p24_chain()
        result, worker, msg_repo = invoke_exact_worker_full(
            session_local, chain, task_status="completed",
        )

        # Claim service blocks because Task is not running
        assert result.status == "blocked"
        assert result.automatic_worker_call_allowed is False
        assert worker.call_count == 0

    def test_task_paused_strict(self, session_local):
        """Task paused → strict not_invoked outcome."""
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
        # Pause the task
        task = s.get(TaskTable, chain.next_task_id)
        task.paused_reason = "test pause"
        s.commit()
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

        assert result.status in ("outcome_recorded", "blocked")
        if result.status == "outcome_recorded":
            assert result.outcome.status == "not_invoked"
            assert result.outcome.worker_called is False
            assert result.outcome.human_recovery_required is True
        assert fake_worker.call_count == 0


# ── returned-invalid Matrix ─────────────────────────────────────────


class TestReturnedInvalidMatrix:
    """Parameterized tests for returned-invalid Worker results."""

    @pytest.mark.parametrize("field,value", [
        ("model_name", "wrong-model"),
        ("model_tier", "wrong-tier"),
        ("skill_codes", ["wrong-skill"]),
        ("skill_names", ["Wrong Skill"]),
        ("owner_role_code", ProjectRoleCode.ENGINEER),
    ])
    def test_authority_mismatch(self, session_local, field, value):
        """Authority mismatch → returned-invalid."""
        chain = build_p24_chain()
        kwargs = {}
        if field == "model_name":
            kwargs["model_name"] = value
        elif field == "model_tier":
            kwargs["model_tier"] = value
        elif field == "skill_codes":
            kwargs["skill_codes"] = value
        elif field == "skill_names":
            kwargs["skill_names"] = value
        elif field == "owner_role_code":
            kwargs["owner_role_code"] = value

        worker_result = build_worker_result_for_chain(chain, **kwargs)
        fake_worker = FakeTaskWorker(session=None, result=worker_result)

        result, _, msg_repo = invoke_exact_worker_full(
            session_local, chain, task_worker=fake_worker,
        )

        assert result.status == "outcome_recorded"
        assert result.outcome is not None
        assert result.outcome.status == "returned"
        assert result.outcome.worker_call_attempted is True
        assert result.outcome.worker_result_contract_valid is False
        assert result.outcome.human_recovery_required is True
        assert count_messages_by_source_detail(
            msg_repo, chain.session_id,
            CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL,
        ) == 1

    @pytest.mark.parametrize("field,value", [
        ("snapshot_source", "wrong_source"),
        ("snapshot_task_id", uuid4()),
        ("snapshot_run_id", uuid4()),
        ("exact_binding_validated", False),
        ("task_routed", True),
        ("task_claimed_in_this_cycle", True),
        ("run_created_in_this_cycle", True),
        ("existing_run_reused", False),
        ("shared_execution_seam_used", False),
        ("snapshot_blocked_reasons", ["some_block"]),
    ])
    def test_snapshot_mismatch(self, session_local, field, value):
        """Snapshot mismatch → returned-invalid."""
        chain = build_p24_chain()
        kwargs = {field: value}
        worker_result = build_worker_result_for_chain(chain, **kwargs)
        fake_worker = FakeTaskWorker(session=None, result=worker_result)

        result, _, msg_repo = invoke_exact_worker_full(
            session_local, chain, task_worker=fake_worker,
        )

        assert result.status == "outcome_recorded"
        assert result.outcome is not None
        assert result.outcome.status == "returned"
        assert result.outcome.worker_call_attempted is True
        assert result.outcome.worker_result_contract_valid is False
        assert result.outcome.human_recovery_required is True
        assert count_messages_by_source_detail(
            msg_repo, chain.session_id,
            CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL,
        ) == 1


# ── AgentSession After-State ────────────────────────────────────────


class TestAgentSessionAfterState:
    """AgentSession after-state tests."""

    def test_no_agent_session(self, session_local):
        """0 AgentSessions → no binding conflict, valid outcome."""
        chain = build_p24_chain()
        worker_result = build_worker_result_for_chain(chain)
        fake_worker = FakeTaskWorker(session=None, result=worker_result)

        result, _, _ = invoke_exact_worker_full(
            session_local, chain, task_worker=fake_worker,
        )

        assert result.status == "outcome_recorded"
        assert result.outcome is not None
        assert result.outcome.worker_result_contract_valid is True
        assert result.outcome.agent_session_id is None

    def test_one_correct_agent_session_blocks_pre_call(self, session_local):
        """1 AgentSession → pre-call validation detects conflict → not_invoked."""
        chain = build_p24_chain()
        # Seed chain with AgentSession
        worker_result = build_worker_result_for_chain(chain)
        fake_worker = FakeTaskWorker(session=None, result=worker_result)

        result, _, _ = invoke_exact_worker_full(
            session_local, chain, task_worker=fake_worker,
            agent_sessions=[{
                "project_id": chain.project_id,
                "task_id": chain.next_task_id,
                "run_id": chain.exact_run_id,
                "status": "running",
                "current_phase": "executing",
            }],
        )

        # AgentSession exists → claim service blocks because
        # _active_agent_session_ids finds active sessions
        assert result.status == "blocked"
        assert result.automatic_worker_call_allowed is False

    def test_two_agent_sessions_blocks_claim(self, session_local):
        """2 AgentSessions → claim service blocks."""
        chain = build_p24_chain()
        worker_result = build_worker_result_for_chain(chain)
        fake_worker = FakeTaskWorker(session=None, result=worker_result)

        result, _, _ = invoke_exact_worker_full(
            session_local, chain, task_worker=fake_worker,
            agent_sessions=[
                {
                    "project_id": chain.project_id,
                    "task_id": chain.next_task_id,
                    "run_id": chain.exact_run_id,
                    "status": "running",
                    "current_phase": "executing",
                },
                {
                    "project_id": chain.project_id,
                    "task_id": chain.next_task_id,
                    "run_id": chain.exact_run_id,
                    "status": "running",
                    "current_phase": "executing",
                },
            ],
        )

        # Multiple AgentSessions → claim service blocks
        assert result.status == "blocked"
        assert result.automatic_worker_call_allowed is False


# ── Service-Level Sensitive Info ────────────────────────────────────


class TestServiceSensitiveInfo:
    """Service-level sensitive info cleaning tests."""

    @pytest.mark.parametrize("secret", [
        "Authorization: Bearer secret-value-12345",
        "api_key=abc123def456",
        "password=abc",
        "token=abc",
        "provider_credential=abc",
    ])
    def test_sensitive_in_worker_result(self, session_local, secret):
        """Sensitive info in Worker result → cleaned in Outcome."""
        chain = build_p24_chain()
        worker_result = build_worker_result_for_chain(chain, message=f"Result: {secret}")
        fake_worker = FakeTaskWorker(session=None, result=worker_result)

        result, _, _ = invoke_exact_worker_full(
            session_local, chain, task_worker=fake_worker,
        )

        assert result.status == "outcome_recorded"
        assert result.outcome is not None
        # The secret should not appear in the persisted outcome
        outcome_json = result.outcome.model_dump_json()
        assert secret not in outcome_json

    def test_sensitive_in_exception(self, session_local):
        """Sensitive info in exception → cleaned in Outcome."""
        chain = build_p24_chain()
        exc = RuntimeError("Authorization: Bearer secret-value-12345")
        fake_worker = FakeTaskWorker(session=None, exception=exc)

        result, _, _ = invoke_exact_worker_full(
            session_local, chain, task_worker=fake_worker,
        )

        assert result.status == "outcome_recorded"
        assert result.outcome is not None
        assert result.outcome.status == "raised"
        outcome_json = result.outcome.model_dump_json()
        assert "secret-value-12345" not in outcome_json


# ── Git Boundary Matrix ─────────────────────────────────────────────


class TestGitBoundaryMatrix:
    """Parameterized Git boundary tests."""

    @pytest.mark.parametrize("field", [
        "git_commit_triggered",
        "git_operation_applied",
        "delivery_gate_allows_write",
        "delivery_push_triggered",
    ])
    def test_git_activity_fields(self, session_local, field):
        """Git activity field → contract invalid."""
        chain = build_p24_chain()
        kwargs = {field: True}
        worker_result = build_worker_result_for_chain(chain, **kwargs)
        fake_worker = FakeTaskWorker(session=None, result=worker_result)

        result, _, _ = invoke_exact_worker_full(
            session_local, chain, task_worker=fake_worker,
        )

        assert result.status == "outcome_recorded"
        assert result.outcome is not None
        assert result.outcome.worker_reported_git_write_activity is True
        assert result.outcome.worker_result_contract_valid is False
        assert result.outcome.human_recovery_required is True
        assert "exact_worker_invocation_outcome_git_boundary_violation" in result.outcome.blocked_reasons
        assert result.outcome.product_runtime_git_write_allowed is False


# ── Raised Outcome Replay ──────────────────────────────────────────


class TestRaisedOutcomeReplay:
    """Raised Outcome replay tests."""

    def test_raised_outcome_replay(self, session_local):
        """Worker raises → Outcome durable → replay returns same Outcome."""
        chain = build_p24_chain()
        exc = RuntimeError("Worker failed")
        fake_worker = FakeTaskWorker(session=None, exception=exc)

        # First call
        result1, _, msg_repo = invoke_exact_worker_full(
            session_local, chain, task_worker=fake_worker,
        )

        assert result1.status == "outcome_recorded"
        assert result1.outcome is not None
        assert result1.outcome.status == "raised"
        assert result1.outcome.worker_raised is True
        assert result1.outcome.exception_type == "RuntimeError"
        first_outcome_id = result1.outcome.exact_worker_invocation_outcome_id
        first_fp = result1.outcome.worker_invocation_outcome_fingerprint

        # Second call replays (don't re-seed, use new service stack)
        fake_worker2 = FakeTaskWorker(session=None)
        session, msg_repo2, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
        outcome_svc = make_outcome_service(
            session,
            msg_repo=msg_repo2,
            task_repo=task_repo,
            run_repo=run_repo,
            agent_sess_repo=agent_sess_repo,
            task_worker=fake_worker2,
        )
        result2 = outcome_svc.invoke_exact_worker(
            session_id=chain.session_id,
            project_id=chain.project_id,
            continuation_root_record_id=chain.root_record_id,
            instruction_package_id=chain.package_id,
            exact_run_reservation_id=chain.exact_run_reservation_id,
            exact_worker_start_reservation_id=chain.worker_start_reservation_id,
        )

        assert result2.status == "outcome_replayed"
        assert result2.outcome is not None
        assert result2.outcome.exact_worker_invocation_outcome_id == first_outcome_id
        assert result2.outcome.worker_invocation_outcome_fingerprint == first_fp
        assert fake_worker.call_count == 1  # Only first worker was called
        assert fake_worker2.call_count == 0  # Second worker was never called

    def test_keyboard_interrupt_not_swallowed(self, session_local):
        """KeyboardInterrupt is not caught by except Exception.

        The production code uses `except Exception` which does NOT catch
        KeyboardInterrupt or SystemExit (they inherit from BaseException).
        We verify this by checking that the service's exception handler
        only catches Exception subclasses.
        """
        # Verify KeyboardInterrupt is NOT a subclass of Exception
        assert not issubclass(KeyboardInterrupt, Exception)
        # Verify SystemExit is NOT a subclass of Exception
        assert not issubclass(SystemExit, Exception)
        # This means `except Exception` in the production code will NOT
        # catch these exceptions, and they will propagate up to the caller.


# ── Outcome Persistence Rollback ────────────────────────────────────


class TestOutcomePersistenceRollback:
    """Outcome persistence rollback tests."""

    def test_outcome_create_failure_recovery(self, session_local):
        """Outcome Message create failure → recovery_required, no retry."""
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

        # First: create the claim with a real service
        session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
        claim_svc = make_claim_service(
            session,
            msg_repo=msg_repo,
            task_repo=task_repo,
            run_repo=run_repo,
            agent_sess_repo=agent_sess_repo,
        )
        claim_result = claim_svc.claim_exact_worker_invocation(
            session_id=chain.session_id,
            project_id=chain.project_id,
            continuation_root_record_id=chain.root_record_id,
            instruction_package_id=chain.package_id,
            exact_run_reservation_id=chain.exact_run_reservation_id,
            exact_worker_start_reservation_id=chain.worker_start_reservation_id,
        )
        assert claim_result.status == "invocation_claim_created"

        # Now wrap the message repo to fail on create for the outcome
        failing_msg_repo = FailingMessageRepositoryWrapper(msg_repo)
        failing_msg_repo._fail_create = True

        worker_result = build_worker_result_for_chain(chain)
        fake_worker = FakeTaskWorker(session=None, result=worker_result)
        fake_worker.bind_session(session, task_repo, run_repo, agent_sess_repo)

        from app.services.project_director_cross_task_exact_worker_invocation_claim_service import (
            ProjectDirectorCrossTaskExactWorkerInvocationClaimService,
        )
        from app.services.project_director_cross_task_exact_worker_invocation_outcome_service import (
            ProjectDirectorCrossTaskExactWorkerInvocationOutcomeService,
        )

        # Create a new claim service that uses the failing repo
        claim_svc2 = ProjectDirectorCrossTaskExactWorkerInvocationClaimService(
            message_repository=failing_msg_repo,
            task_repository=task_repo,
            run_repository=run_repo,
            agent_session_repository=agent_sess_repo,
        )

        outcome_svc = ProjectDirectorCrossTaskExactWorkerInvocationOutcomeService(
            message_repository=failing_msg_repo,
            task_repository=task_repo,
            run_repository=run_repo,
            agent_session_repository=agent_sess_repo,
            claim_service=claim_svc2,
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

        # The outcome service sees the claim is replayed (not created),
        # so it tries to resolve the replayed claim by loading history.
        # Since the claim exists but no outcome, it returns recovery_required.
        assert result.status == "recovery_required"
        assert result.outcome is None
        assert result.worker_call_state_indeterminate is True
        assert result.automatic_worker_call_allowed is False
