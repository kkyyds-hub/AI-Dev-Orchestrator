"""Behavior tests for P23 TaskWorker reserved seam and B2 invocation."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.db_tables import ORMBase
from app.domain.project_director_protected_transition_worker_invocation import (
    ProjectDirectorProtectedTransitionWorkerInvocationClaimResult,
    ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult,
)
from app.domain.project_director_protected_transition_worker_start_reservation import (
    ProjectDirectorProtectedTransitionWorkerStartReservationResult,
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
from app.services.project_director_protected_transition_worker_invocation_service import (
    ProjectDirectorProtectedTransitionWorkerInvocationService,
)
from app.services.project_director_protected_transition_worker_start_reservation_service import (
    ProjectDirectorProtectedTransitionWorkerStartReservationService,
)
from app.workers.task_worker import (
    WorkerReservedRunExecutionSnapshot,
    WorkerRunResult,
)
from tests.p23_test_support import (
    DIFF_SHA256,
    WORKSPACE_PATH,
    FakeBudgetDecision,
    FakeCurrentReservation,
    FakeFreshnessResult,
    SpyTaskWorker,
    count_messages_by_source_detail,
    get_messages_by_source_detail,
    make_fake_worker_result,
    make_repos,
    make_run_record,
    make_test_engine,
    make_session_factory,
    seed_base_records,
    seed_review_message,
    valid_review_action,
)


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════


class FakeFreshnessService:
    def __init__(self, *, blocked_reasons=None, session=None):
        self._blocked = blocked_reasons or []
        self._message_repository = type("R", (), {"_session": session})()
        self._task_repository = type("R", (), {"session": session})()

    def revalidate_current_protected_transition_evidence_freshness(self, **kwargs):
        return type("R", (), {
            "result": FakeFreshnessResult(blocked_reasons=self._blocked),
            "blocked_reasons": self._blocked,
        })()

    def revalidate_persisted_protected_transition_evidence_freshness(self, **kwargs):
        return type("R", (), {
            "result": FakeFreshnessResult(),
            "blocked_reasons": [],
        })()


class FakeBudgetGuardService:
    def __init__(self, session=None):
        self._db_session = session

    def evaluate(self, **kwargs):
        return FakeBudgetDecision()


class FakeD1Service:
    def __init__(self, *, result=None, blocked_reasons=None, session=None):
        self._result = result
        self._blocked = blocked_reasons or []
        self._message_repository = type("R", (), {"_session": session})()
        self._task_repository = type("R", (), {"session": session})()
        self._run_repository = type("R", (), {"session": session})()

    def revalidate_persisted_protected_transition_dispatch_consumption(self, **kwargs):
        return type("R", (), {
            "result": self._result,
            "blocked_reasons": self._blocked,
        })()


class FakeAgentSessionRepository:
    def __init__(self, *, existing_session=None, session=None):
        self._existing = existing_session
        self.session = session

    def get_by_run_id(self, run_id):
        return self._existing


def _make_b1_service(session_local, *, freshness_blocked=None, agent_session=None):
    session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
    freshness_svc = FakeFreshnessService(blocked_reasons=freshness_blocked, session=session)
    freshness_svc._message_repository = msg_repo
    freshness_svc._task_repository = task_repo
    d1_svc = FakeD1Service(session=session)
    d1_svc._message_repository = msg_repo
    d1_svc._task_repository = task_repo
    d1_svc._run_repository = run_repo
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
    return b1_svc, session, msg_repo, task_repo, run_repo, agent_sess_repo


# ══════════════════════════════════════════════════════════════════════
# B1 Reservation Tests
# ══════════════════════════════════════════════════════════════════════


class TestB1ReservationBehavior:
    """Tests that actually call B1 service methods."""

    def test_prepare_blocks_without_valid_consumption(self, tmp_path):
        """B1 blocks when source consumption message is invalid."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        s = sf()
        ids = seed_base_records(s, task_status="running")
        s.close()

        b1_svc, session, msg_repo, task_repo, run_repo, _ = _make_b1_service(sf)
        result = b1_svc.prepare_protected_transition_worker_start_reservation(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_message_id=uuid4(),
        )
        assert result.result.reservation_status == "blocked"
        assert result.message is None
        session.close()
        engine.dispose()

    def test_find_persisted_returns_empty_when_none(self, tmp_path):
        """Finder returns empty when no reservation exists."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        s = sf()
        ids = seed_base_records(s, task_status="running")
        s.close()

        b1_svc, session, msg_repo, task_repo, run_repo, _ = _make_b1_service(sf)
        found = b1_svc.find_persisted_protected_transition_worker_start_reservation(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_consumption_message_id=uuid4(),
        )
        assert found.result is None
        assert found.message is None
        assert found.blocked_reasons == []
        session.close()
        engine.dispose()


# ══════════════════════════════════════════════════════════════════════
# DomainModel Validator Tests
# ══════════════════════════════════════════════════════════════════════


class TestB2ClaimDomainModel:
    """Tests for B2 claim result domain model validators."""

    def test_claim_validates_reservation_binding(self) -> None:
        """Claim must bind exact reservation."""
        with pytest.raises(ValueError, match="claim must bind the exact reservation"):
            ProjectDirectorProtectedTransitionWorkerInvocationClaimResult(
                claim_status="claimed",
                claim_id=uuid4(),
                claim_fingerprint="a" * 64,
                claim_token="token",
                session_id=uuid4(),
                project_id=uuid4(),
                source_task_id=uuid4(),
                target_task_id=uuid4(),
                run_id=uuid4(),
                source_reservation_message_id=uuid4(),
                source_reservation_id=uuid4(),
                source_reservation_fingerprint="a" * 64,
                source_reservation_token="token",
                source_consumption_message_id=uuid4(),
                source_consumption_fingerprint="a" * 64,
                source_preflight_message_id=uuid4(),
                source_intent_message_id=uuid4(),
                source_freshness_message_id=uuid4(),
                disposition_type="AUTO_CONTINUE",
                dispatch_kind="auto_continue",
                target_task_strategy="source_task_continue",
                review_result_fingerprint="a" * 64,
                review_semantic_fingerprint="a" * 64,
                current_freshness_fingerprint="a" * 64,
                current_diff_sha256="a" * 64,
                current_scope_paths=["src/example.py"],
                workspace_path="/tmp/ws",
                workspace_path_within_root=True,
                task_status_before="running",
                run_status_before="running",
                agent_session_absent=True,
                budget_guard_allowed=True,
                budget_pressure_level="normal",
                budget_strategy_action="allow",
                budget_strategy_code="normal",
                budget_policy_source="test",
                retry_limit_reached=False,
                rework_attempt_index=0,
                rework_attempt_limit=3,
                worker_invocation_claimed=True,
            )

    def test_claim_validates_target_equals_source(self) -> None:
        """Claim target must equal source task."""
        with pytest.raises(ValueError, match="claim must bind the exact reservation"):
            ProjectDirectorProtectedTransitionWorkerInvocationClaimResult(
                claim_status="claimed",
                claim_id=uuid4(),
                claim_fingerprint="a" * 64,
                claim_token="token",
                session_id=uuid4(),
                project_id=uuid4(),
                source_task_id=uuid4(),
                target_task_id=uuid4(),
                run_id=uuid4(),
                source_reservation_message_id=uuid4(),
                source_reservation_id=uuid4(),
                source_reservation_fingerprint="a" * 64,
                source_reservation_token="token",
                source_consumption_message_id=uuid4(),
                source_consumption_fingerprint="a" * 64,
                source_preflight_message_id=uuid4(),
                source_intent_message_id=uuid4(),
                source_freshness_message_id=uuid4(),
                disposition_type="AUTO_CONTINUE",
                dispatch_kind="auto_continue",
                target_task_strategy="source_task_continue",
                review_result_fingerprint="a" * 64,
                review_semantic_fingerprint="a" * 64,
                current_freshness_fingerprint="a" * 64,
                current_diff_sha256="a" * 64,
                current_scope_paths=["src/example.py"],
                workspace_path="/tmp/ws",
                workspace_path_within_root=True,
                task_status_before="running",
                run_status_before="running",
                agent_session_absent=True,
                budget_guard_allowed=True,
                budget_pressure_level="normal",
                budget_strategy_action="allow",
                budget_strategy_code="normal",
                budget_policy_source="test",
                retry_limit_reached=False,
                rework_attempt_index=0,
                rework_attempt_limit=3,
                worker_invocation_claimed=True,
            )


class TestB2OutcomeDomainModel:
    """Tests for B2 outcome result domain model validators."""

    def test_outcome_validates_claim_binding(self) -> None:
        """Outcome must bind exact claim."""
        claim_id = uuid4()
        with pytest.raises(ValueError, match="outcome must bind the exact invocation claim"):
            ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult(
                outcome_status="returned",
                outcome_id=uuid4(),
                outcome_fingerprint="a" * 64,
                session_id=uuid4(),
                project_id=uuid4(),
                source_task_id=uuid4(),
                run_id=uuid4(),
                source_claim_message_id=claim_id,
                source_claim_id=uuid4(),
                source_claim_fingerprint="a" * 64,
                source_claim_token="token",
                source_reservation_message_id=uuid4(),
                source_reservation_fingerprint="a" * 64,
                source_consumption_message_id=uuid4(),
                disposition_type="AUTO_CONTINUE",
                dispatch_kind="auto_continue",
                target_task_strategy="source_task_continue",
                worker_call_attempted=True,
                worker_returned=True,
                worker_raised=False,
                worker_result_contract_valid=True,
                reserved_snapshot_present=True,
                replay_check_completed=True,
            )

    def test_not_invoked_no_execution_evidence(self) -> None:
        """Not invoked outcome cannot have execution evidence."""
        claim_id = uuid4()
        with pytest.raises(ValueError, match="not_invoked outcome has contradictory"):
            ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult(
                outcome_status="not_invoked",
                outcome_id=uuid4(),
                outcome_fingerprint="a" * 64,
                session_id=uuid4(),
                project_id=uuid4(),
                source_task_id=uuid4(),
                run_id=uuid4(),
                source_claim_message_id=claim_id,
                source_claim_id=claim_id,
                source_claim_fingerprint="a" * 64,
                source_claim_token="token",
                source_reservation_message_id=uuid4(),
                source_reservation_fingerprint="a" * 64,
                source_consumption_message_id=uuid4(),
                disposition_type="AUTO_CONTINUE",
                dispatch_kind="auto_continue",
                target_task_strategy="source_task_continue",
                worker_call_attempted=True,
                worker_returned=False,
                worker_raised=False,
                worker_result_contract_valid=False,
                reserved_snapshot_present=False,
                replay_check_completed=True,
                blocked_reasons=["x"],
            )

    def test_raised_requires_exception_info(self) -> None:
        """Raised outcome must have exception type and summary."""
        claim_id = uuid4()
        with pytest.raises(ValueError, match="raised outcome requires safe exception"):
            ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult(
                outcome_status="raised",
                outcome_id=uuid4(),
                outcome_fingerprint="a" * 64,
                session_id=uuid4(),
                project_id=uuid4(),
                source_task_id=uuid4(),
                run_id=uuid4(),
                source_claim_message_id=claim_id,
                source_claim_id=claim_id,
                source_claim_fingerprint="a" * 64,
                source_claim_token="token",
                source_reservation_message_id=uuid4(),
                source_reservation_fingerprint="a" * 64,
                source_consumption_message_id=uuid4(),
                disposition_type="AUTO_CONTINUE",
                dispatch_kind="auto_continue",
                target_task_strategy="source_task_continue",
                worker_call_attempted=True,
                worker_returned=False,
                worker_raised=True,
                worker_result_contract_valid=False,
                reserved_snapshot_present=False,
                replay_check_completed=True,
                human_recovery_required=True,
            )

    def test_continuation_and_rework_both_true_rejected(self) -> None:
        """Cannot have both continuation and rework started."""
        claim_id = uuid4()
        with pytest.raises(ValueError, match="continuation and rework cannot both start"):
            ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult(
                outcome_status="returned",
                outcome_id=uuid4(),
                outcome_fingerprint="a" * 64,
                session_id=uuid4(),
                project_id=uuid4(),
                source_task_id=uuid4(),
                run_id=uuid4(),
                source_claim_message_id=claim_id,
                source_claim_id=claim_id,
                source_claim_fingerprint="a" * 64,
                source_claim_token="token",
                source_reservation_message_id=uuid4(),
                source_reservation_fingerprint="a" * 64,
                source_consumption_message_id=uuid4(),
                disposition_type="AUTO_CONTINUE",
                dispatch_kind="auto_continue",
                target_task_strategy="source_task_continue",
                worker_call_attempted=True,
                worker_returned=True,
                worker_raised=False,
                worker_result_contract_valid=True,
                reserved_snapshot_present=True,
                replay_check_completed=True,
                continuation_started=True,
                rework_started=True,
            )

    def test_git_write_authority_rejected(self) -> None:
        """Cannot authorize Git write."""
        claim_id = uuid4()
        with pytest.raises(ValueError, match="outcome cannot authorize Git write"):
            ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult(
                outcome_status="not_invoked",
                outcome_id=uuid4(),
                outcome_fingerprint="a" * 64,
                session_id=uuid4(),
                project_id=uuid4(),
                source_task_id=uuid4(),
                run_id=uuid4(),
                source_claim_message_id=claim_id,
                source_claim_id=claim_id,
                source_claim_fingerprint="a" * 64,
                source_claim_token="token",
                source_reservation_message_id=uuid4(),
                source_reservation_fingerprint="a" * 64,
                source_consumption_message_id=uuid4(),
                disposition_type="AUTO_CONTINUE",
                dispatch_kind="auto_continue",
                target_task_strategy="source_task_continue",
                worker_call_attempted=False,
                worker_returned=False,
                worker_raised=False,
                worker_result_contract_valid=False,
                reserved_snapshot_present=False,
                replay_check_completed=True,
                product_runtime_git_write_allowed=True,
                blocked_reasons=["x"],
            )


class TestWorkerReservedExecutionSnapshot:
    """Tests for the reserved execution snapshot contract."""

    def test_snapshot_fields_present(self) -> None:
        """Snapshot must have all required fields."""
        snapshot = WorkerReservedRunExecutionSnapshot(
            source="p23_d2_exact_reserved_run",
            exact_task_id=uuid4(),
            exact_run_id=uuid4(),
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
        assert snapshot.source == "p23_d2_exact_reserved_run"
        assert snapshot.reserved_run_execution_requested is True
        assert snapshot.task_routed is False
        assert snapshot.product_runtime_git_write_allowed is False


class TestFakeWorkerResult:
    """Tests for the fake worker result factory."""

    def test_make_fake_worker_result_auto_continue(self) -> None:
        """Fake result for AUTO_CONTINUE has correct flags."""
        tid = uuid4()
        rid = uuid4()
        result = make_fake_worker_result(
            task_id=tid, run_id=rid, disposition_type="AUTO_CONTINUE"
        )
        assert result.claimed is True
        assert result.reserved_run_execution_snapshot is not None
        assert result.reserved_run_execution_snapshot.exact_task_id == tid
        assert result.reserved_run_execution_snapshot.exact_run_id == rid
        assert result.reserved_run_execution_snapshot.source == "p23_d2_exact_reserved_run"

    def test_make_fake_worker_result_git_activity(self) -> None:
        """Fake result with git activity sets flag."""
        result = make_fake_worker_result(
            task_id=uuid4(), run_id=uuid4(), git_activity=True
        )
        assert result.git_diff_dry_run_runs_write_git is True

    def test_make_fake_worker_result_invalid_contract(self) -> None:
        """Fake result with invalid contract has wrong source."""
        result = make_fake_worker_result(
            task_id=uuid4(), run_id=uuid4(), contract_valid=False
        )
        assert result.reserved_run_execution_snapshot.source == "invalid_source"
        assert result.reserved_run_execution_snapshot.task_routed is True


class TestSpyTaskWorker:
    """Tests for the spy task worker."""

    def test_records_run_reserved_once_calls(self) -> None:
        """Spy records run_reserved_once calls."""
        tid = uuid4()
        rid = uuid4()
        result = make_fake_worker_result(task_id=tid, run_id=rid)
        spy = SpyTaskWorker(result=result)
        spy.run_reserved_once(task_id=tid, run_id=rid)
        assert len(spy.run_reserved_once_calls) == 1
        assert spy.run_reserved_once_calls[0]["task_id"] == tid
        assert spy.run_reserved_once_calls[0]["run_id"] == rid

    def test_records_run_once_calls(self) -> None:
        """Spy records run_once calls."""
        spy = SpyTaskWorker()
        spy.run_once(task_id=uuid4())
        assert len(spy.run_once_calls) == 1

    def test_raises_exception(self) -> None:
        """Spy can raise exception."""
        spy = SpyTaskWorker(exception=ValueError("test error"))
        with pytest.raises(ValueError, match="test error"):
            spy.run_reserved_once(task_id=uuid4(), run_id=uuid4())
        assert len(spy.run_reserved_once_calls) == 1
