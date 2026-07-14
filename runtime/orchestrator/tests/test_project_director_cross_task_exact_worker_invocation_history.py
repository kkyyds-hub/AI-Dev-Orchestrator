"""P24-G History corruption tests with precise blocked_reasons assertions."""

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

from tests.p24_test_support import (
    FakeTaskWorker,
    build_p24_chain,
    build_valid_outcome,
    build_worker_result_for_chain,
    corrupt_message_field,
    count_messages_by_source_detail,
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


# ── History Corruption Tests ────────────────────────────────────────


class TestHistoryCorruption:
    """Corruption tests that verify fail-closed behavior with precise reasons."""

    def _assert_blocked(self, result, worker, msg_repo, chain, *,
                        expected_reason, expected_claims=0, expected_outcomes=0):
        """Common assertion for blocked corruption results."""
        assert result.status == "blocked"
        assert result.blocked_reasons == (expected_reason,)
        assert result.automatic_worker_call_allowed is False
        assert worker.call_count == 0
        assert count_messages_by_source_detail(
            msg_repo, chain.session_id,
            CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL,
        ) == expected_claims
        assert count_messages_by_source_detail(
            msg_repo, chain.session_id,
            CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL,
        ) == expected_outcomes

    def _seed_and_invoke(self, session_local, chain, *, corrupt_fn=None, seed_claim=False):
        """Helper: seed chain, optionally corrupt, invoke E4B."""
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
        if seed_claim:
            seed_claim_message(s, chain.claim)
        seed_run(
            s,
            run_id=chain.exact_run_id,
            task_id=chain.next_task_id,
            model_name=chain.claim.worker_model_name,
            started_at=chain.claim.exact_run_started_at,
            created_at=chain.claim.exact_run_created_at,
        )
        if corrupt_fn:
            corrupt_fn(s)
        s.close()

        fake_worker = FakeTaskWorker(session=None)
        session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
        outcome_svc = make_outcome_service(
            session, msg_repo=msg_repo, task_repo=task_repo,
            run_repo=run_repo, agent_sess_repo=agent_sess_repo,
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
        return result, fake_worker, msg_repo

    # 1. Message role corrupted
    def test_message_role_corrupted(self, session_local):
        chain = build_p24_chain()
        result, worker, msg_repo = self._seed_and_invoke(
            session_local, chain,
            corrupt_fn=lambda s: corrupt_message_field(s, chain.package_id, field="role", value="user"),
        )
        self._assert_blocked(result, worker, msg_repo, chain,
                             expected_reason="exact_worker_invocation_outcome_package_invalid")

    # 2. Message source corrupted
    def test_message_source_corrupted(self, session_local):
        chain = build_p24_chain()
        result, worker, msg_repo = self._seed_and_invoke(
            session_local, chain,
            corrupt_fn=lambda s: corrupt_message_field(s, chain.root_record_id, field="source", value="ai"),
        )
        self._assert_blocked(result, worker, msg_repo, chain,
                             expected_reason="exact_worker_invocation_outcome_history_invalid")

    # 3. Action type corrupted
    def test_action_type_corrupted(self, session_local):
        chain = build_p24_chain()
        def corrupt(s):
            msgs = [m for m in s.query(ProjectDirectorMessageTable).all()
                    if m.intent == "cross_task_exact_run_reservation"]
            if msgs:
                action = json.loads(msgs[0].suggested_actions_json)
                action[0]["type"] = "wrong_action_type"
                msgs[0].suggested_actions_json = json.dumps(action)
                s.commit()
        result, worker, msg_repo = self._seed_and_invoke(session_local, chain, corrupt_fn=corrupt)
        self._assert_blocked(result, worker, msg_repo, chain,
                             expected_reason="exact_worker_invocation_outcome_exact_run_reservation_invalid")

    # 4. Schema version corrupted
    def test_schema_version_corrupted(self, session_local):
        chain = build_p24_chain()
        def corrupt(s):
            msgs = [m for m in s.query(ProjectDirectorMessageTable).all()
                    if m.intent == "cross_task_exact_worker_start_reservation"]
            if msgs:
                action = json.loads(msgs[0].suggested_actions_json)
                action[0]["schema_version"] = "wrong_schema_version"
                msgs[0].suggested_actions_json = json.dumps(action)
                s.commit()
        result, worker, msg_repo = self._seed_and_invoke(session_local, chain, corrupt_fn=corrupt)
        self._assert_blocked(result, worker, msg_repo, chain,
                             expected_reason="exact_worker_invocation_outcome_worker_start_reservation_invalid")

    # 5. Message ID / payload ID mismatch
    def test_message_id_payload_id_mismatch(self, session_local):
        chain = build_p24_chain()
        def corrupt(s):
            msgs = [m for m in s.query(ProjectDirectorMessageTable).all()
                    if m.intent == "cross_task_auto_continue"]
            if msgs:
                action = json.loads(msgs[0].suggested_actions_json)
                action[0]["record_id"] = str(uuid4())
                msgs[0].suggested_actions_json = json.dumps(action)
                s.commit()
        result, worker, msg_repo = self._seed_and_invoke(session_local, chain, corrupt_fn=corrupt)
        self._assert_blocked(result, worker, msg_repo, chain,
                             expected_reason="exact_worker_invocation_outcome_history_invalid")

    # 6. Claim fingerprint corrupted
    def test_claim_fingerprint_corrupted(self, session_local):
        chain = build_p24_chain()
        def corrupt(s):
            msgs = [m for m in s.query(ProjectDirectorMessageTable).all()
                    if m.intent == "cross_task_exact_worker_invocation_claim"]
            if msgs:
                action = json.loads(msgs[0].suggested_actions_json)
                action[0]["worker_invocation_claim_fingerprint"] = "f" * 64
                msgs[0].suggested_actions_json = json.dumps(action)
                s.commit()
        result, worker, msg_repo = self._seed_and_invoke(
            session_local, chain, corrupt_fn=corrupt, seed_claim=True)
        self._assert_blocked(result, worker, msg_repo, chain,
                             expected_reason="exact_worker_invocation_outcome_replay_conflict",
                             expected_claims=1)

    # 7. Claim replay key corrupted
    def test_claim_replay_key_corrupted(self, session_local):
        chain = build_p24_chain()
        def corrupt(s):
            msgs = [m for m in s.query(ProjectDirectorMessageTable).all()
                    if m.intent == "cross_task_exact_worker_invocation_claim"]
            if msgs:
                action = json.loads(msgs[0].suggested_actions_json)
                action[0]["worker_invocation_claim_replay_key"] = "e" * 64
                msgs[0].suggested_actions_json = json.dumps(action)
                s.commit()
        result, worker, msg_repo = self._seed_and_invoke(
            session_local, chain, corrupt_fn=corrupt, seed_claim=True)
        self._assert_blocked(result, worker, msg_repo, chain,
                             expected_reason="exact_worker_invocation_outcome_replay_conflict",
                             expected_claims=1)

    # 8. Claim token corrupted
    def test_claim_token_corrupted(self, session_local):
        chain = build_p24_chain()
        def corrupt(s):
            msgs = [m for m in s.query(ProjectDirectorMessageTable).all()
                    if m.intent == "cross_task_exact_worker_invocation_claim"]
            if msgs:
                action = json.loads(msgs[0].suggested_actions_json)
                action[0]["worker_invocation_claim_token"] = "d" * 64
                msgs[0].suggested_actions_json = json.dumps(action)
                s.commit()
        result, worker, msg_repo = self._seed_and_invoke(
            session_local, chain, corrupt_fn=corrupt, seed_claim=True)
        self._assert_blocked(result, worker, msg_repo, chain,
                             expected_reason="exact_worker_invocation_outcome_replay_conflict",
                             expected_claims=1)

    # 9. Outcome fingerprint corrupted
    def test_outcome_fingerprint_corrupted(self, session_local):
        chain = build_p24_chain()
        def corrupt(s):
            seed_claim_message(s, chain.claim)
            outcome = build_valid_outcome(chain, status="returned")
            seed_outcome_message(s, outcome)
            msgs = [m for m in s.query(ProjectDirectorMessageTable).all()
                    if m.intent == "cross_task_exact_worker_invocation_outcome"]
            if msgs:
                action = json.loads(msgs[0].suggested_actions_json)
                action[0]["worker_invocation_outcome_fingerprint"] = "c" * 64
                msgs[0].suggested_actions_json = json.dumps(action)
                s.commit()
        result, worker, msg_repo = self._seed_and_invoke(session_local, chain, corrupt_fn=corrupt)
        self._assert_blocked(result, worker, msg_repo, chain,
                             expected_reason="exact_worker_invocation_outcome_replay_conflict",
                             expected_claims=1, expected_outcomes=1)

    # 10. Outcome replay key corrupted
    def test_outcome_replay_key_corrupted(self, session_local):
        chain = build_p24_chain()
        def corrupt(s):
            seed_claim_message(s, chain.claim)
            outcome = build_valid_outcome(chain, status="returned")
            seed_outcome_message(s, outcome)
            msgs = [m for m in s.query(ProjectDirectorMessageTable).all()
                    if m.intent == "cross_task_exact_worker_invocation_outcome"]
            if msgs:
                action = json.loads(msgs[0].suggested_actions_json)
                action[0]["worker_invocation_outcome_replay_key"] = "b" * 64
                msgs[0].suggested_actions_json = json.dumps(action)
                s.commit()
        result, worker, msg_repo = self._seed_and_invoke(session_local, chain, corrupt_fn=corrupt)
        self._assert_blocked(result, worker, msg_repo, chain,
                             expected_reason="exact_worker_invocation_outcome_replay_conflict",
                             expected_claims=1, expected_outcomes=1)

    # 11. Dual-family message
    def test_dual_family_message(self, session_local):
        chain = build_p24_chain()
        def corrupt(s):
            msgs = [m for m in s.query(ProjectDirectorMessageTable).all()
                    if m.intent == "cross_task_auto_continue"]
            if msgs:
                msgs[0].intent = "cross_task_next_task_instruction_package"
                s.commit()
        result, worker, msg_repo = self._seed_and_invoke(session_local, chain, corrupt_fn=corrupt)
        self._assert_blocked(result, worker, msg_repo, chain,
                             expected_reason="exact_worker_invocation_outcome_history_invalid")

    # 12. Two outcomes same claim
    def test_two_outcomes_same_claim(self, session_local):
        chain = build_p24_chain()
        def corrupt(s):
            seed_claim_message(s, chain.claim)
            outcome1 = build_valid_outcome(chain, status="returned")
            seed_outcome_message(s, outcome1)
            outcome2 = build_valid_outcome(chain, status="returned")
            seed_outcome_message(s, outcome2)
        result, worker, msg_repo = self._seed_and_invoke(session_local, chain, corrupt_fn=corrupt)
        assert result.status == "blocked"
        assert worker.call_count == 0
        # The reason depends on whether the history loads or not
        assert result.blocked_reasons[0] in (
            "exact_worker_invocation_outcome_history_invalid",
            "exact_worker_invocation_outcome_replay_conflict",
        )

    # 13. Two outcomes same exact run
    def test_two_outcomes_same_exact_run(self, session_local):
        chain = build_p24_chain()
        def corrupt(s):
            seed_claim_message(s, chain.claim)
            outcome1 = build_valid_outcome(chain, status="returned")
            seed_outcome_message(s, outcome1)
            outcome2 = build_valid_outcome(chain, status="returned")
            seed_outcome_message(s, outcome2)
        result, worker, msg_repo = self._seed_and_invoke(session_local, chain, corrupt_fn=corrupt)
        assert result.status == "blocked"
        assert worker.call_count == 0
        assert result.blocked_reasons[0] in (
            "exact_worker_invocation_outcome_history_invalid",
            "exact_worker_invocation_outcome_replay_conflict",
        )

    # 14. Broken previous_record_id
    def test_broken_previous_record_id(self, session_local):
        chain = build_p24_chain()
        def corrupt(s):
            msgs = [m for m in s.query(ProjectDirectorMessageTable).all()
                    if m.intent == "cross_task_exact_run_reservation"]
            if msgs:
                action = json.loads(msgs[0].suggested_actions_json)
                action[0]["previous_record_id"] = str(uuid4())
                msgs[0].suggested_actions_json = json.dumps(action)
                s.commit()
        result, worker, msg_repo = self._seed_and_invoke(session_local, chain, corrupt_fn=corrupt)
        self._assert_blocked(result, worker, msg_repo, chain,
                             expected_reason="exact_worker_invocation_outcome_exact_run_reservation_invalid")
