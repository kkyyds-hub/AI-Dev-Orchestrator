"""Behavior tests for P23-D1 atomic dispatch consumption."""

from __future__ import annotations

import json
import threading
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.db_tables import ORMBase
from app.domain.project_director_protected_transition_dispatch_consumption import (
    ProjectDirectorProtectedTransitionDispatchConsumptionResult,
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
from app.services.budget_guard_service import BudgetGuardService
from app.services.project_director_protected_transition_dispatch_consumption_preflight_service import (
    ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService,
)
from app.services.project_director_protected_transition_dispatch_consumption_service import (
    ProjectDirectorProtectedTransitionDispatchConsumptionService,
)
from app.services.project_director_protected_transition_dispatch_intent_service import (
    ProjectDirectorProtectedTransitionDispatchIntentService,
)
from app.services.project_director_protected_transition_evidence_freshness_service import (
    ProjectDirectorProtectedTransitionEvidenceFreshnessService,
)
from app.services.task_readiness_service import TaskReadinessService
from app.services.task_router_service import TaskRouterService
from app.services.task_state_machine_service import TaskStateMachineService
from tests.p23_test_support import (
    DIFF_SHA256,
    WORKSPACE_PATH,
    FakeBudgetDecision,
    FakeCurrentReservation,
    FakeFreshnessResult,
    count_messages_by_source_detail,
    get_messages_by_source_detail,
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


class FakeTaskReadinessService:
    def evaluate_task(self, **kwargs):
        return type("R", (), {"ready": True, "blocked_reasons": []})()


class FakeTaskStateMachineService:
    def __init__(self):
        self.claim_calls = []

    def claim_task(self, **kwargs):
        self.claim_calls.append(kwargs)
        return type("R", (), {"status": "running"})()


class FakeTaskRouterService:
    def route_next_task(self, **kwargs):
        return None


class FakeBudgetGuardService:
    def __init__(self, session=None):
        self._db_session = session

    def evaluate(self, **kwargs):
        return FakeBudgetDecision()


class FakeFreshnessService:
    def __init__(self, *, blocked_reasons=None):
        self._blocked = blocked_reasons or []

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


class FakeIntentService:
    def __init__(self, session=None):
        self._message_repository = type("R", (), {"_session": session})()

    def revalidate_persisted_protected_transition_dispatch_intent(self, **kwargs):
        return type("R", (), {
            "result": type("I", (), {
                "intent_id": uuid4(),
                "dispatch_intent_fingerprint": "a" * 64,
                "source_dispatch_intent_id": uuid4(),
                "source_dispatch_intent_fingerprint": "a" * 64,
                "source_p22_summary_message_id": uuid4(),
                "source_review_message_id": uuid4(),
                "source_freshness_message_id": uuid4(),
                "disposition_type": "AUTO_CONTINUE",
                "dispatch_kind": "auto_continue",
                "target_task_strategy": "source_task_continue",
                "review_result_fingerprint": "a" * 64,
                "review_semantic_fingerprint": "a" * 64,
                "freshness_evidence_fingerprint": "a" * 64,
                "source_diff_sha256": DIFF_SHA256,
                "review_scope_paths": ["src/example.py"],
                "workspace_path": WORKSPACE_PATH,
                "workspace_path_within_root": True,
                "rework_attempt_index": 0,
                "rework_attempt_limit": 3,
            })(),
            "blocked_reasons": [],
        })()


def _make_d1_service(session_local, *, freshness_blocked=None):
    session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
    freshness_svc = FakeFreshnessService(blocked_reasons=freshness_blocked)
    intent_svc = FakeIntentService(session=session)
    intent_svc._message_repository = msg_repo
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
    return d1_svc, session, msg_repo, task_repo, run_repo


# ══════════════════════════════════════════════════════════════════════
# D1 Consumption Tests
# ══════════════════════════════════════════════════════════════════════


class TestD1ConsumptionBehavior:
    """Tests that actually call D1 service methods."""

    def test_consume_protected_transition_dispatch_preflight_blocked_without_preflight(self, tmp_path):
        """D1 blocks when no valid preflight exists."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        s = sf()
        ids = seed_base_records(s, task_status="pending")
        s.close()

        d1_svc, session, msg_repo, task_repo, run_repo = _make_d1_service(sf)
        result = d1_svc.consume_protected_transition_dispatch_preflight(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_message_id=uuid4(),
        )
        assert result.result.consumption_status == "blocked"
        assert result.message is None
        session.close()
        engine.dispose()

    def test_find_persisted_returns_empty_when_none(self, tmp_path):
        """Finder returns empty when no consumption exists."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        s = sf()
        ids = seed_base_records(s, task_status="pending")
        s.close()

        d1_svc, session, msg_repo, task_repo, run_repo = _make_d1_service(sf)
        found = d1_svc.find_persisted_protected_transition_dispatch_consumption(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_preflight_message_id=uuid4(),
        )
        assert found.result is None
        assert found.message is None
        assert found.blocked_reasons == []
        session.close()
        engine.dispose()

    def test_revalidate_returns_missing_when_no_message(self, tmp_path):
        """Revalidation returns missing when message doesn't exist."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        s = sf()
        ids = seed_base_records(s, task_status="pending")
        s.close()

        d1_svc, session, msg_repo, task_repo, run_repo = _make_d1_service(sf)
        found = d1_svc.revalidate_persisted_protected_transition_dispatch_consumption(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_consumption_message_id=uuid4(),
        )
        assert found.result is None
        assert "source_consumption_missing" in found.blocked_reasons
        session.close()
        engine.dispose()
