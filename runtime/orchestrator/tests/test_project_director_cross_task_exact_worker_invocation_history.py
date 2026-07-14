"""P24-G History corruption tests."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.core.db_tables import ProjectDirectorMessageTable
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
    FakeTaskWorker,
    build_p24_chain,
    build_valid_outcome,
    build_worker_result_for_chain,
    corrupt_message_field,
    count_messages_by_source_detail,
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


@pytest.fixture
def engine(tmp_path):
    return make_test_engine(str(tmp_path / "test.db"))


@pytest.fixture
def session_local(engine):
    return make_session_factory(engine)


def _seed_and_invoke_e4b(session_local, chain, *, task_worker=None):
    """Seed full chain + run and invoke E4B. Returns (result, worker, msg_repo)."""
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

    if task_worker is None:
        task_worker = FakeTaskWorker(
            session=None,
            result=build_worker_result_for_chain(chain),
        )

    session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
    outcome_svc = make_outcome_service(
        session,
        msg_repo=msg_repo,
        task_repo=task_repo,
        run_repo=run_repo,
        agent_sess_repo=agent_sess_repo,
        task_worker=task_worker,
    )

    result = outcome_svc.invoke_exact_worker(
        session_id=chain.session_id,
        project_id=chain.project_id,
        continuation_root_record_id=chain.root_record_id,
        instruction_package_id=chain.package_id,
        exact_run_reservation_id=chain.exact_run_reservation_id,
        exact_worker_start_reservation_id=chain.worker_start_reservation_id,
    )
    return result, task_worker, msg_repo


# ── History Corruption Tests ────────────────────────────────────────


class TestHistoryCorruption:
    """Corruption tests that verify fail-closed behavior."""

    def test_message_role_corrupted(self, session_local):
        """Corrupted message role → blocked, no Worker call."""
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
        # Corrupt the package message role
        corrupt_message_field(s, chain.package_id, field="role", value="user")
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

        assert result.status == "blocked"
        assert result.automatic_worker_call_allowed is False
        assert fake_worker.call_count == 0

    def test_message_source_corrupted(self, session_local):
        """Corrupted message source → blocked, no Worker call."""
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
        # Corrupt the root message source (use a valid enum value that's wrong)
        corrupt_message_field(s, chain.root_record_id, field="source", value="ai")
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

        assert result.status == "blocked"
        assert fake_worker.call_count == 0

    def test_action_type_corrupted(self, session_local):
        """Corrupted action type → blocked."""
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
        # Corrupt the E1B action type
        e1b_msgs = [m for m in s.query(ProjectDirectorMessageTable).all()
                    if m.intent == "cross_task_exact_run_reservation"]
        if e1b_msgs:
            action = json.loads(e1b_msgs[0].suggested_actions_json)
            action[0]["type"] = "wrong_action_type"
            e1b_msgs[0].suggested_actions_json = json.dumps(action)
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

        assert result.status == "blocked"
        assert fake_worker.call_count == 0

    def test_schema_version_corrupted(self, session_local):
        """Corrupted schema version → blocked."""
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
        # Corrupt the E2A schema version
        e2a_msgs = [m for m in s.query(ProjectDirectorMessageTable).all()
                    if m.intent == "cross_task_exact_worker_start_reservation"]
        if e2a_msgs:
            action = json.loads(e2a_msgs[0].suggested_actions_json)
            action[0]["schema_version"] = "wrong_schema_version"
            e2a_msgs[0].suggested_actions_json = json.dumps(action)
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

        assert result.status == "blocked"
        assert fake_worker.call_count == 0

    def test_message_id_payload_id_mismatch(self, session_local):
        """Message ID != payload ID → blocked."""
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
        # Change the root message ID in the action payload
        root_msgs = [m for m in s.query(ProjectDirectorMessageTable).all()
                     if m.intent == "cross_task_auto_continue"]
        if root_msgs:
            action = json.loads(root_msgs[0].suggested_actions_json)
            action[0]["record_id"] = str(uuid4())
            root_msgs[0].suggested_actions_json = json.dumps(action)
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

        assert result.status == "blocked"
        assert fake_worker.call_count == 0

    def test_claim_fingerprint_corrupted(self, session_local):
        """Corrupted claim fingerprint → blocked."""
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
        # Corrupt the claim fingerprint in the action payload
        claim_msgs = [m for m in s.query(ProjectDirectorMessageTable).all()
                      if m.intent == "cross_task_exact_worker_invocation_claim"]
        if claim_msgs:
            action = json.loads(claim_msgs[0].suggested_actions_json)
            action[0]["worker_invocation_claim_fingerprint"] = "f" * 64
            claim_msgs[0].suggested_actions_json = json.dumps(action)
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

        assert result.status == "blocked"
        assert fake_worker.call_count == 0

    def test_claim_replay_key_corrupted(self, session_local):
        """Corrupted claim replay key → blocked."""
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
        # Corrupt the claim replay key
        claim_msgs = [m for m in s.query(ProjectDirectorMessageTable).all()
                      if m.intent == "cross_task_exact_worker_invocation_claim"]
        if claim_msgs:
            action = json.loads(claim_msgs[0].suggested_actions_json)
            action[0]["worker_invocation_claim_replay_key"] = "e" * 64
            claim_msgs[0].suggested_actions_json = json.dumps(action)
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

        assert result.status == "blocked"
        assert fake_worker.call_count == 0

    def test_claim_token_corrupted(self, session_local):
        """Corrupted claim token → blocked."""
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
        # Corrupt the claim token
        claim_msgs = [m for m in s.query(ProjectDirectorMessageTable).all()
                      if m.intent == "cross_task_exact_worker_invocation_claim"]
        if claim_msgs:
            action = json.loads(claim_msgs[0].suggested_actions_json)
            action[0]["worker_invocation_claim_token"] = "d" * 64
            claim_msgs[0].suggested_actions_json = json.dumps(action)
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

        assert result.status == "blocked"
        assert fake_worker.call_count == 0

    def test_dual_family_message(self, session_local):
        """Message matching two families → blocked."""
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
        # Make the root message also look like a package message
        root_msgs = [m for m in s.query(ProjectDirectorMessageTable).all()
                     if m.intent == "cross_task_auto_continue"]
        if root_msgs:
            root_msgs[0].intent = "cross_task_next_task_instruction_package"
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

        assert result.status == "blocked"
        assert fake_worker.call_count == 0

    def test_two_outcomes_same_claim(self, session_local):
        """Two Outcomes for same Claim → blocked/recovery."""
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
        # Seed two outcomes with different IDs but same replay key
        outcome1 = build_valid_outcome(chain, status="returned")
        seed_outcome_message(s, outcome1)
        # Create a second outcome with a different ID
        outcome2_values = outcome1.model_dump(mode="python")
        outcome2_values["exact_worker_invocation_outcome_id"] = uuid4()
        from app.domain.project_director_cross_task_exact_worker_invocation_outcome import ProjectDirectorCrossTaskExactWorkerInvocationOutcome
        from app.domain.project_director_next_task_instruction_package import compute_p24_contract_sha256
        provisional = ProjectDirectorCrossTaskExactWorkerInvocationOutcome.model_construct(**outcome2_values)
        fp = provisional.compute_fingerprint()
        outcome2_values["worker_invocation_outcome_fingerprint"] = fp
        outcome2 = ProjectDirectorCrossTaskExactWorkerInvocationOutcome.model_validate(outcome2_values)
        seed_outcome_message(s, outcome2)
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

        # Should be blocked or recovery due to duplicate outcomes
        assert result.status in ("blocked", "recovery_required")
        assert fake_worker.call_count == 0

    def test_broken_previous_record_id(self, session_local):
        """Broken previous_record_id chain → blocked."""
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
        # Corrupt E1B's previous_record_id in payload
        e1b_msgs = [m for m in s.query(ProjectDirectorMessageTable).all()
                    if m.intent == "cross_task_exact_run_reservation"]
        if e1b_msgs:
            action = json.loads(e1b_msgs[0].suggested_actions_json)
            action[0]["previous_record_id"] = str(uuid4())
            e1b_msgs[0].suggested_actions_json = json.dumps(action)
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

        assert result.status == "blocked"
        assert fake_worker.call_count == 0

    def test_outcome_fingerprint_corrupted(self, session_local):
        """Corrupted Outcome fingerprint → blocked."""
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
        # Corrupt the outcome fingerprint
        outcome_msgs = [m for m in s.query(ProjectDirectorMessageTable).all()
                        if m.intent == "cross_task_exact_worker_invocation_outcome"]
        if outcome_msgs:
            action = json.loads(outcome_msgs[0].suggested_actions_json)
            action[0]["worker_invocation_outcome_fingerprint"] = "c" * 64
            outcome_msgs[0].suggested_actions_json = json.dumps(action)
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

        # Corrupted fingerprint → blocked or recovery
        assert result.status in ("blocked", "recovery_required")
        assert fake_worker.call_count == 0

    def test_outcome_replay_key_corrupted(self, session_local):
        """Corrupted Outcome replay key → blocked."""
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
        # Corrupt the outcome replay key
        outcome_msgs = [m for m in s.query(ProjectDirectorMessageTable).all()
                        if m.intent == "cross_task_exact_worker_invocation_outcome"]
        if outcome_msgs:
            action = json.loads(outcome_msgs[0].suggested_actions_json)
            action[0]["worker_invocation_outcome_replay_key"] = "b" * 64
            outcome_msgs[0].suggested_actions_json = json.dumps(action)
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

        # Corrupted replay key → blocked or recovery
        assert result.status in ("blocked", "recovery_required")
        assert fake_worker.call_count == 0

    def test_two_outcomes_same_exact_run(self, session_local):
        """Two Outcomes for same exact Run → blocked/recovery."""
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
        # Seed first outcome
        outcome1 = build_valid_outcome(chain, status="returned")
        seed_outcome_message(s, outcome1)
        # Seed a second outcome with different ID but targeting same claim
        # by corrupting the outcome ID in the action payload
        outcome2 = build_valid_outcome(chain, status="returned")
        # Change the outcome ID to make it a different message
        from app.core.db_tables import ProjectDirectorMessageTable
        import json
        action = {
            "type": "p24_cross_task_exact_worker_invocation_outcome_record",
            **outcome2.model_dump(mode="json"),
        }
        # Use a different outcome ID
        different_outcome_id = uuid4()
        s.add(
            ProjectDirectorMessageTable(
                id=different_outcome_id,
                session_id=outcome2.session_id,
                role="assistant",
                content=f"P24 exact Worker invocation outcome: {different_outcome_id}",
                sequence_no=16,
                intent="cross_task_exact_worker_invocation_outcome",
                source="system",
                source_detail="p24_cross_task_exact_worker_invocation_outcome_recorded",
                suggested_actions_json=json.dumps([action]),
                requires_confirmation=False,
                risk_level="high",
                related_plan_version_id=outcome2.plan_version_id,
                related_project_id=outcome2.project_id,
                related_task_id=outcome2.next_task_id,
                created_at=outcome2.created_at,
                forbidden_actions_detected_json=json.dumps(list(outcome2.forbidden_actions)),
            )
        )
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

        assert result.status in ("blocked", "recovery_required")
        assert fake_worker.call_count == 0
