"""Contract tests for P21-D-D3 human escalation decision lifecycle service."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.core.db_tables import (
    ProjectDirectorMessageTable,
    ProjectDirectorSessionTable,
    ProjectTable,
    TaskTable,
)
from app.domain.project_director_message import (
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository

# D1 helpers
from tests.test_project_director_sandbox_candidate_diff_review_human_escalation_package_service_contract import (
    SESSION_ID,
    TASK_ID,
    PROJECT_ID,
    SOURCE_REVIEW_MSG_ID,
    PREFLIGHT_MSG_ID,
    DIFF_MSG_ID,
    DISPOSITION_MSG_ID,
    DISPOSITION_ID,
    _DIFF_SHA256,
    _PROMPT_SHA256,
    _RAW_OUTPUT_SHA256,
    _make_test_engine,
    _make_session_factory,
    _seed_base_records,
    _seed_review_message,
    _seed_disposition_message,
    _valid_review_action,
    _compute_review_fingerprint_from_action,
    _d1_prepare,
)

# D2 service
from app.services.project_director_sandbox_candidate_diff_review_human_escalation_decision_service import (
    HUMAN_ESCALATION_DECISION_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionService,
)

# D3 service
from app.services.project_director_sandbox_candidate_diff_review_human_escalation_decision_lifecycle_service import (
    HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION,
    HUMAN_ESCALATION_DECISION_REVOCATION_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionLifecycleService,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_d2_service(session_local):
    session = session_local()
    msg_repo = ProjectDirectorMessageRepository(session)
    sess_repo = ProjectDirectorSessionRepository(session)
    task_repo = TaskRepository(session)
    svc = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
    )
    return svc, session


def _make_d3_service(session_local):
    session = session_local()
    msg_repo = ProjectDirectorMessageRepository(session)
    sess_repo = ProjectDirectorSessionRepository(session)
    task_repo = TaskRepository(session)
    svc = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionLifecycleService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
    )
    return svc, session


def _seed_d2_decision(
    SessionLocal,
    decision_action="APPROVE_CONTINUE",
    actor="human-reviewer",
    client_request_id=None,
    decision_expires_at=None,
):
    """Seed full chain from D1 through D2, return (decision_result, d2_msg_id, pkg_msg_id)."""
    pkg_msg_id, _ = _d1_prepare(SessionLocal)

    if client_request_id is None:
        client_request_id = f"req-{uuid4()}"
    if decision_expires_at is None:
        decision_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    svc, session = _make_d2_service(SessionLocal)
    result = svc.record_human_escalation_decision(
        session_id=SESSION_ID,
        source_task_id=TASK_ID,
        source_message_id=pkg_msg_id,
        decision_action=decision_action,
        actor=actor,
        client_request_id=client_request_id,
        decision_expires_at=decision_expires_at,
    )
    assert result.result.decision_status == "recorded"
    assert result.message is not None
    d2_msg_id = result.message.id
    session.close()
    return result, d2_msg_id, pkg_msg_id


def _seed_d2_decision_direct(
    SessionLocal,
    *,
    first_d2_msg_id: UUID,
    decision_action="APPROVE_CONTINUE",
    actor="human-reviewer",
    client_request_id=None,
    decision_expires_at=None,
    seq_no_start=300,
):
    """Seed a second D2 decision message directly in DB by cloning the first D2 message's action
    and modifying replay-sensitive fields (decision_id, client_request_id, etc.).

    Returns (d2_msg_id, first_decision_result).
    """
    if client_request_id is None:
        client_request_id = f"req-{uuid4()}"
    if decision_expires_at is None:
        decision_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    session = SessionLocal()
    first_row = session.get(ProjectDirectorMessageTable, first_d2_msg_id)
    assert first_row is not None
    first_action = json.loads(first_row.suggested_actions_json)[0]

    new_decision_id = str(uuid4())
    new_decision_created_at = datetime.now(timezone.utc)
    new_action = dict(first_action)
    new_action["decision_id"] = new_decision_id
    new_action["decision_action"] = decision_action
    new_action["actor"] = actor
    new_action["client_request_id"] = client_request_id
    new_action["decision_created_at"] = new_decision_created_at.isoformat()
    new_action["decision_expires_at"] = decision_expires_at.isoformat()

    # Recompute confirmation fingerprint for the new decision
    canonical_payload = (
        ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionService
        ._decision_confirmation_canonical_payload(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_package_message_id=UUID(first_action["source_package_message_id"]),
            escalation_package_id=UUID(first_action["escalation_package_id"]),
            source_disposition_message_id=UUID(first_action["source_disposition_message_id"]),
            source_review_message_id=UUID(first_action["source_review_message_id"]),
            source_preflight_message_id=UUID(first_action["source_preflight_message_id"]),
            source_diff_message_id=UUID(first_action["source_diff_message_id"]),
            disposition_id=UUID(first_action["disposition_id"]),
            aggregate_evidence_fingerprint=first_action["aggregate_evidence_fingerprint"],
            decision_scope=first_action["decision_scope"],
            decision_action=decision_action,
            actor_type="human",
            actor=actor,
            client_request_id=client_request_id,
            decision_id=UUID(new_decision_id),
            decision_created_at=new_decision_created_at,
            decision_expires_at=decision_expires_at,
        )
    )
    new_action["decision_confirmation_fingerprint"] = (
        ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionService
        ._canonical_payload_fingerprint(canonical_payload)
    )

    new_msg_id = uuid4()
    session.add(
        ProjectDirectorMessageTable(
            id=new_msg_id,
            session_id=SESSION_ID,
            role="user",
            content=(
                "One structured human escalation decision was recorded and "
                "bound to the exact D1 package. The decision has not been "
                "consumed. APPROVE_CONTINUE does not start continuation, "
                "REQUEST_REWORK does not start rework, and REJECT performs no "
                "cleanup or state change. No Task, Run, Worker, or worktree was "
                "created. No file write, patch apply, or Git write was authorized. "
                "AI Project Director total loop remains Partial."
            ),
            sequence_no=seq_no_start,
            intent="sandbox_candidate_diff_review_human_escalation_decision",
            source="system",
            source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([new_action]),
            requires_confirmation=False,
            risk_level="high",
            related_project_id=PROJECT_ID,
            related_task_id=TASK_ID,
        )
    )
    session.commit()
    session.close()
    return new_msg_id


def _tamper_d2_expires_at(SessionLocal, d2_msg_id: UUID, new_expires_at: datetime):
    """Tamper decision_expires_at in a stored D2 message action.

    Also adjusts decision_created_at to maintain domain invariant
    (expires_at > created_at) while still being expired relative to now.
    """
    session = SessionLocal()
    row = session.get(ProjectDirectorMessageTable, d2_msg_id)
    assert row is not None
    action = json.loads(row.suggested_actions_json)[0]
    # Set created_at to 1 second before expires_at to keep domain invariant
    new_created_at = new_expires_at - timedelta(seconds=1)
    action["decision_expires_at"] = new_expires_at.isoformat()
    action["decision_created_at"] = new_created_at.isoformat()

    # Recompute confirmation fingerprint with new timestamps
    canonical_payload = (
        ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionService
        ._decision_confirmation_canonical_payload(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_package_message_id=UUID(action["source_package_message_id"]),
            escalation_package_id=UUID(action["escalation_package_id"]),
            source_disposition_message_id=UUID(action["source_disposition_message_id"]),
            source_review_message_id=UUID(action["source_review_message_id"]),
            source_preflight_message_id=UUID(action["source_preflight_message_id"]),
            source_diff_message_id=UUID(action["source_diff_message_id"]),
            disposition_id=UUID(action["disposition_id"]),
            aggregate_evidence_fingerprint=action["aggregate_evidence_fingerprint"],
            decision_scope=action["decision_scope"],
            decision_action=action["decision_action"],
            actor_type=action["actor_type"],
            actor=action["actor"],
            client_request_id=action["client_request_id"],
            decision_id=UUID(action["decision_id"]),
            decision_created_at=new_created_at,
            decision_expires_at=new_expires_at,
        )
    )
    action["decision_confirmation_fingerprint"] = (
        ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionService
        ._canonical_payload_fingerprint(canonical_payload)
    )

    row.suggested_actions_json = json.dumps([action])
    session.commit()
    session.close()


def _seed_filler_messages_d3(
    session, start_seq: int, count: int = 105
) -> None:
    for i in range(count):
        session.add(
            ProjectDirectorMessageTable(
                id=uuid4(),
                session_id=SESSION_ID,
                role="user",
                content=f"filler-{i}",
                sequence_no=start_seq + i,
                source="system",
                source_detail="filler",
                suggested_actions_json="[]",
                requires_confirmation=False,
                risk_level="low",
                related_project_id=PROJECT_ID,
                related_task_id=TASK_ID,
            )
        )
    session.commit()


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def db_engine(tmp_path):
    db_path = str(tmp_path / "test.db")
    engine = _make_test_engine(db_path)
    yield engine
    engine.dispose()


@pytest.fixture()
def seeded_session(db_engine):
    SessionLocal = _make_session_factory(db_engine)
    session = SessionLocal()
    _seed_base_records(session)
    _seed_review_message(session)
    _seed_disposition_message(session)
    session.close()
    return SessionLocal


# ══════════════════════════════════════════════════════════════════════
# 1. TestConstants
# ══════════════════════════════════════════════════════════════════════


class TestConstants:
    def test_revocation_source_detail(self) -> None:
        assert (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_SOURCE_DETAIL
            == "p21_d_sandbox_candidate_diff_review_human_escalation_decision_revoked"
        )

    def test_revocation_action_type(self) -> None:
        assert (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_ACTION_TYPE
            == "p21_d_sandbox_candidate_diff_review_human_escalation_decision_revocation_record"
        )

    def test_revocation_schema_version(self) -> None:
        assert HUMAN_ESCALATION_DECISION_REVOCATION_SCHEMA_VERSION == "p21-d-d3-revoke.v1"

    def test_preflight_source_detail(self) -> None:
        assert (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL
            == "p21_d_sandbox_candidate_diff_review_human_escalation_decision_consumption_preflight_ready"
        )

    def test_preflight_action_type(self) -> None:
        assert (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_ACTION_TYPE
            == "p21_d_sandbox_candidate_diff_review_human_escalation_decision_consumption_preflight_record"
        )

    def test_preflight_schema_version(self) -> None:
        assert HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION == "p21-d-d3-preflight.v1"

    def test_decision_source_detail(self) -> None:
        assert (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_SOURCE_DETAIL
            == "p21_d_sandbox_candidate_diff_review_human_escalation_decision_recorded"
        )

    def test_decision_action_type(self) -> None:
        assert (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_ACTION_TYPE
            == "p21_d_sandbox_candidate_diff_review_human_escalation_decision_record"
        )

    def test_decision_schema_version(self) -> None:
        assert HUMAN_ESCALATION_DECISION_SCHEMA_VERSION == "p21-d-d2.v1"


# ══════════════════════════════════════════════════════════════════════
# 2. TestRevokeSuccess
# ══════════════════════════════════════════════════════════════════════


class TestRevokeSuccess:
    def _seed_and_revoke(
        self,
        db_engine,
        *,
        decision_action: str,
    ):
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        result, d2_msg_id, _ = _seed_d2_decision(
            SessionLocal, decision_action=decision_action
        )

        svc, session = _make_d3_service(SessionLocal)
        revoke_result = svc.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            actor="human-reviewer",
            client_request_id=f"revoke-{uuid4()}",
        )
        session.close()
        return revoke_result

    def test_approve_continue_revocation(self, db_engine) -> None:
        revoke_result = self._seed_and_revoke(db_engine, decision_action="APPROVE_CONTINUE")
        res = revoke_result.result
        assert res.revocation_status == "revoked"
        assert res.revoke_actor_type == "human"
        assert res.decision_revoked is True
        assert res.prior_revocation_detected is False
        assert res.source_decision_validated is True
        assert res.decision_fingerprint_revalidated is True
        assert res.replay_check_completed is True
        assert res.decision_expired is False
        assert res.blocked_reasons == []
        assert res.revocation_id is not None
        assert res.revoked_at is not None
        assert res.revoked_at.tzinfo is not None
        assert len(res.decision_confirmation_fingerprint) == 64
        assert res.decision_confirmation_fingerprint == res.revalidated_decision_confirmation_fingerprint

        msg = revoke_result.message
        assert msg is not None
        assert msg.role == ProjectDirectorMessageRole.USER
        assert msg.source == ProjectDirectorMessageSource.SYSTEM
        assert msg.requires_confirmation is False
        assert msg.risk_level == ProjectDirectorMessageRiskLevel.HIGH
        assert msg.related_project_id == PROJECT_ID
        assert msg.related_task_id == TASK_ID
        assert msg.intent == "sandbox_candidate_diff_review_human_escalation_decision_revocation"
        assert msg.source_detail == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_SOURCE_DETAIL
        assert len(msg.suggested_actions) == 1
        action = msg.suggested_actions[0]
        assert action["type"] == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_ACTION_TYPE
        assert action["schema_version"] == HUMAN_ESCALATION_DECISION_REVOCATION_SCHEMA_VERSION

    def test_request_rework_revocation(self, db_engine) -> None:
        revoke_result = self._seed_and_revoke(db_engine, decision_action="REQUEST_REWORK")
        res = revoke_result.result
        assert res.revocation_status == "revoked"
        assert res.revoke_actor_type == "human"
        assert res.decision_revoked is True
        assert res.blocked_reasons == []

        msg = revoke_result.message
        assert msg is not None
        assert msg.role == ProjectDirectorMessageRole.USER
        assert msg.source == ProjectDirectorMessageSource.SYSTEM
        assert msg.requires_confirmation is False
        assert msg.risk_level == ProjectDirectorMessageRiskLevel.HIGH
        assert len(msg.suggested_actions) == 1

    def test_reject_revocation(self, db_engine) -> None:
        revoke_result = self._seed_and_revoke(db_engine, decision_action="REJECT")
        res = revoke_result.result
        assert res.revocation_status == "revoked"
        assert res.revoke_actor_type == "human"
        assert res.decision_revoked is True
        assert res.blocked_reasons == []

        msg = revoke_result.message
        assert msg is not None
        assert msg.role == ProjectDirectorMessageRole.USER
        assert msg.source == ProjectDirectorMessageSource.SYSTEM
        assert msg.requires_confirmation is False
        assert msg.risk_level == ProjectDirectorMessageRiskLevel.HIGH
        assert len(msg.suggested_actions) == 1


# ══════════════════════════════════════════════════════════════════════
# 3. TestRevokeInputNormalization
# ══════════════════════════════════════════════════════════════════════


class TestRevokeInputNormalization:
    def test_actor_strip(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        svc, session = _make_d3_service(SessionLocal)
        result = svc.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            actor="  human-reviewer  ",
            client_request_id=f"revoke-{uuid4()}",
        )
        assert result.result.revocation_status == "revoked"
        assert result.result.revoke_actor == "human-reviewer"
        session.close()

    def test_client_request_id_strip(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        svc, session = _make_d3_service(SessionLocal)
        result = svc.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            actor="human-reviewer",
            client_request_id="  revoke-req-123  ",
        )
        assert result.result.revocation_status == "revoked"
        assert result.result.revoke_client_request_id == "revoke-req-123"
        session.close()

    def test_empty_actor_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        svc, session = _make_d3_service(SessionLocal)
        result = svc.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            actor="",
            client_request_id=f"revoke-{uuid4()}",
        )
        assert result.result.revocation_status == "blocked"
        assert "human_escalation_decision_revoke_actor_invalid" in result.result.blocked_reasons
        session.close()

    def test_empty_client_request_id_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        svc, session = _make_d3_service(SessionLocal)
        result = svc.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            actor="human-reviewer",
            client_request_id="",
        )
        assert result.result.revocation_status == "blocked"
        assert "human_decision_revoke_client_request_id_invalid" in result.result.blocked_reasons
        session.close()

    def test_actor_too_long_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        svc, session = _make_d3_service(SessionLocal)
        result = svc.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            actor="x" * 201,
            client_request_id=f"revoke-{uuid4()}",
        )
        assert result.result.revocation_status == "blocked"
        assert "human_escalation_decision_revoke_actor_invalid" in result.result.blocked_reasons
        session.close()

    def test_client_request_id_too_long_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        svc, session = _make_d3_service(SessionLocal)
        result = svc.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            actor="human-reviewer",
            client_request_id="x" * 201,
        )
        assert result.result.revocation_status == "blocked"
        assert "human_decision_revoke_client_request_id_invalid" in result.result.blocked_reasons
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 4. TestRevokeBlocked
# ══════════════════════════════════════════════════════════════════════


class TestRevokeBlocked:
    def test_revoked_then_repeat_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)
        revoke_req = f"revoke-{uuid4()}"

        svc, session = _make_d3_service(SessionLocal)
        first = svc.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            actor="human-reviewer",
            client_request_id=revoke_req,
        )
        assert first.result.revocation_status == "revoked"
        session.close()

        svc2, session2 = _make_d3_service(SessionLocal)
        second = svc2.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            actor="human-reviewer",
            client_request_id=f"revoke-{uuid4()}",
        )
        assert second.result.revocation_status == "blocked"
        assert "human_escalation_decision_already_revoked" in second.result.blocked_reasons
        session2.close()

    def test_expired_decision_blocked(self, db_engine) -> None:
        """Tamper a valid decision's expires_at to be in the past, then attempt revoke."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        # Tamper the stored expires_at to be in the past
        expired_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        _tamper_d2_expires_at(SessionLocal, d2_msg_id, expired_at)

        svc, session = _make_d3_service(SessionLocal)
        result = svc.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            actor="human-reviewer",
            client_request_id=f"revoke-{uuid4()}",
        )
        assert result.result.revocation_status == "blocked"
        assert "human_escalation_decision_expired" in result.result.blocked_reasons
        session.close()

    def test_client_request_id_reuse_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        first_result, d2_msg_id_a, _ = _seed_d2_decision(
            SessionLocal, decision_action="APPROVE_CONTINUE",
            client_request_id=f"decision-a-{uuid4()}",
        )

        # Create a second D2 decision directly in DB
        d2_msg_id_b = _seed_d2_decision_direct(
            SessionLocal,
            first_d2_msg_id=d2_msg_id_a,
            decision_action="REQUEST_REWORK",
            actor="human-reviewer",
            client_request_id=f"decision-b-{uuid4()}",
            seq_no_start=300,
        )

        shared_revoke_req = f"revoke-shared-{uuid4()}"

        svc, session = _make_d3_service(SessionLocal)
        first_revoke = svc.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id_a,
            actor="human-reviewer",
            client_request_id=shared_revoke_req,
        )
        assert first_revoke.result.revocation_status == "revoked"
        session.close()

        svc2, session2 = _make_d3_service(SessionLocal)
        second_revoke = svc2.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id_b,
            actor="human-reviewer",
            client_request_id=shared_revoke_req,
        )
        assert second_revoke.result.revocation_status == "blocked"
        assert "human_decision_revoke_client_request_id_reused" in second_revoke.result.blocked_reasons
        session2.close()

    def test_session_mismatch_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        svc, session = _make_d3_service(SessionLocal)
        result = svc.revoke_human_escalation_decision(
            session_id=uuid4(),
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            actor="human-reviewer",
            client_request_id=f"revoke-{uuid4()}",
        )
        assert result.result.revocation_status == "blocked"
        assert "session_missing" in result.result.blocked_reasons
        session.close()

    def test_task_mismatch_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        svc, session = _make_d3_service(SessionLocal)
        result = svc.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=uuid4(),
            source_message_id=d2_msg_id,
            actor="human-reviewer",
            client_request_id=f"revoke-{uuid4()}",
        )
        assert result.result.revocation_status == "blocked"
        assert "source_task_missing" in result.result.blocked_reasons
        session.close()

    def test_message_missing_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        svc, session = _make_d3_service(SessionLocal)
        result = svc.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=uuid4(),
            actor="human-reviewer",
            client_request_id=f"revoke-{uuid4()}",
        )
        assert result.result.revocation_status == "blocked"
        assert "source_human_escalation_decision_message_missing" in result.result.blocked_reasons
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 5. TestReplayKeys
# ══════════════════════════════════════════════════════════════════════


class TestReplayKeys:
    def _seed_two_decisions_with_fillers(self, db_engine, *, action_a, action_b):
        """Seed one D1→D2 chain, then insert filler + second D2 directly."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id_a, _ = _seed_d2_decision(
            SessionLocal, decision_action=action_a,
            client_request_id=f"decision-a-{uuid4()}",
        )

        session = SessionLocal()
        _seed_filler_messages_d3(session, start_seq=200, count=105)
        session.close()

        d2_msg_id_b = _seed_d2_decision_direct(
            SessionLocal,
            first_d2_msg_id=d2_msg_id_a,
            decision_action=action_b,
            actor="human-reviewer",
            client_request_id=f"decision-b-{uuid4()}",
            seq_no_start=400,
        )

        return SessionLocal, d2_msg_id_a, d2_msg_id_b

    def test_source_decision_message_id_replay_key(self, db_engine) -> None:
        SessionLocal, d2_msg_id_a, d2_msg_id_b = self._seed_two_decisions_with_fillers(
            db_engine, action_a="APPROVE_CONTINUE", action_b="REJECT"
        )

        svc, session = _make_d3_service(SessionLocal)
        revoke_a = svc.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id_a,
            actor="human-reviewer",
            client_request_id=f"revoke-a-{uuid4()}",
        )
        assert revoke_a.result.revocation_status == "revoked"
        session.close()

        # Revoking B should succeed (different source_decision_message_id)
        svc2, session2 = _make_d3_service(SessionLocal)
        revoke_b = svc2.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id_b,
            actor="human-reviewer",
            client_request_id=f"revoke-b-{uuid4()}",
        )
        assert revoke_b.result.revocation_status == "revoked"
        session2.close()

    def test_decision_id_replay_key(self, db_engine) -> None:
        SessionLocal, d2_msg_id_a, d2_msg_id_b = self._seed_two_decisions_with_fillers(
            db_engine, action_a="REQUEST_REWORK", action_b="APPROVE_CONTINUE"
        )

        svc, session = _make_d3_service(SessionLocal)
        revoke_a = svc.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id_a,
            actor="human-reviewer",
            client_request_id=f"revoke-a-{uuid4()}",
        )
        assert revoke_a.result.revocation_status == "revoked"
        assert revoke_a.result.decision_id is not None
        session.close()

        svc2, session2 = _make_d3_service(SessionLocal)
        revoke_b = svc2.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id_b,
            actor="human-reviewer",
            client_request_id=f"revoke-b-{uuid4()}",
        )
        assert revoke_b.result.revocation_status == "revoked"
        assert revoke_b.result.decision_id != revoke_a.result.decision_id
        session2.close()

    def test_revoke_client_request_id_replay_key(self, db_engine) -> None:
        SessionLocal, d2_msg_id_a, d2_msg_id_b = self._seed_two_decisions_with_fillers(
            db_engine, action_a="REJECT", action_b="REJECT"
        )

        shared_req = f"shared-revoke-{uuid4()}"

        svc, session = _make_d3_service(SessionLocal)
        revoke_a = svc.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id_a,
            actor="human-reviewer",
            client_request_id=shared_req,
        )
        assert revoke_a.result.revocation_status == "revoked"
        session.close()

        svc2, session2 = _make_d3_service(SessionLocal)
        revoke_b = svc2.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id_b,
            actor="human-reviewer",
            client_request_id=shared_req,
        )
        assert revoke_b.result.revocation_status == "blocked"
        assert "human_decision_revoke_client_request_id_reused" in revoke_b.result.blocked_reasons
        session2.close()


# ══════════════════════════════════════════════════════════════════════
# 6. TestRevokeConcurrency
# ══════════════════════════════════════════════════════════════════════


class TestRevokeConcurrency:
    def test_concurrent_revoke_one_revoked_one_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        barrier = threading.Barrier(2, timeout=30)
        results: list[dict] = []
        lock = threading.Lock()

        def _revoke(thread_id: int):
            barrier.wait()
            svc, session = _make_d3_service(SessionLocal)
            result = svc.revoke_human_escalation_decision(
                session_id=SESSION_ID,
                source_task_id=TASK_ID,
                source_message_id=d2_msg_id,
                actor="human-reviewer",
                client_request_id=f"concurrent-revoke-{thread_id}-{uuid4()}",
            )
            with lock:
                results.append({
                    "thread_id": thread_id,
                    "status": result.result.revocation_status,
                    "reasons": result.result.blocked_reasons,
                })
            session.close()

        t1 = threading.Thread(target=_revoke, args=(1,))
        t2 = threading.Thread(target=_revoke, args=(2,))
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        assert len(results) == 2
        statuses = [r["status"] for r in results]
        assert "revoked" in statuses
        assert "blocked" in statuses

        blocked_result = [r for r in results if r["status"] == "blocked"][0]
        assert "human_escalation_decision_already_revoked" in blocked_result["reasons"]

        # Verify exactly one DB record
        verify = SessionLocal()
        count = verify.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd"
            ),
            {"sd": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_SOURCE_DETAIL},
        ).scalar()
        assert count == 1
        verify.close()


# ══════════════════════════════════════════════════════════════════════
# 7. TestPreflightSuccess
# ══════════════════════════════════════════════════════════════════════


class TestPreflightSuccess:
    def _seed_and_preflight(self, db_engine, *, decision_action: str):
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(
            SessionLocal, decision_action=decision_action
        )

        svc, session = _make_d3_service(SessionLocal)
        evaluated_at = datetime.now(timezone.utc) + timedelta(hours=1)
        result = svc.prepare_human_escalation_decision_consumption_preflight(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            evaluated_at=evaluated_at,
        )
        session.close()
        return result

    def test_approve_continue_preflight(self, db_engine) -> None:
        pf = self._seed_and_preflight(db_engine, decision_action="APPROVE_CONTINUE")
        res = pf.result
        assert res.preflight_status == "ready"
        assert res.continuation_eligible is True
        assert res.rework_eligible is False
        assert res.rejection_terminal is False
        assert res.decision_consumed is False
        assert res.continuation_started is False
        assert res.rework_started is False
        assert res.gate_allows_write is False
        assert res.decision_active is True
        assert res.decision_expired is False
        assert res.decision_revoked is False
        assert res.prior_consumption_preflight_detected is False
        assert res.source_decision_validated is True
        assert res.decision_fingerprint_revalidated is True
        assert res.replay_check_completed is True
        assert res.blocked_reasons == []
        assert res.preflight_id is not None
        assert res.evaluated_at is not None

        msg = pf.message
        assert msg is not None
        assert msg.role == ProjectDirectorMessageRole.ASSISTANT
        assert msg.source == ProjectDirectorMessageSource.SYSTEM
        assert msg.requires_confirmation is False
        assert msg.risk_level == ProjectDirectorMessageRiskLevel.HIGH
        assert msg.intent == "sandbox_candidate_diff_review_human_escalation_decision_consumption_preflight"
        assert msg.source_detail == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL
        assert len(msg.suggested_actions) == 1
        action = msg.suggested_actions[0]
        assert action["type"] == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_ACTION_TYPE
        assert action["schema_version"] == HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION

    def test_request_rework_preflight(self, db_engine) -> None:
        pf = self._seed_and_preflight(db_engine, decision_action="REQUEST_REWORK")
        res = pf.result
        assert res.preflight_status == "ready"
        assert res.continuation_eligible is False
        assert res.rework_eligible is True
        assert res.rejection_terminal is False
        assert res.decision_consumed is False
        assert res.blocked_reasons == []

    def test_reject_preflight(self, db_engine) -> None:
        pf = self._seed_and_preflight(db_engine, decision_action="REJECT")
        res = pf.result
        assert res.preflight_status == "ready"
        assert res.continuation_eligible is False
        assert res.rework_eligible is False
        assert res.rejection_terminal is True
        assert res.decision_consumed is False
        assert res.blocked_reasons == []


# ══════════════════════════════════════════════════════════════════════
# 8. TestPreflightExpiry
# ══════════════════════════════════════════════════════════════════════


class TestPreflightExpiry:
    def test_naive_evaluated_at_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        svc, session = _make_d3_service(SessionLocal)
        result = svc.prepare_human_escalation_decision_consumption_preflight(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            evaluated_at=datetime(2025, 1, 1, 0, 0, 0),
        )
        assert result.result.preflight_status == "blocked"
        assert "human_escalation_decision_evaluated_at_invalid" in result.result.blocked_reasons
        session.close()

    def test_evaluated_at_before_expiry_ready(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
        _, d2_msg_id, _ = _seed_d2_decision(
            SessionLocal, decision_expires_at=expires_at
        )

        svc, session = _make_d3_service(SessionLocal)
        evaluated_at = expires_at - timedelta(seconds=10)
        result = svc.prepare_human_escalation_decision_consumption_preflight(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            evaluated_at=evaluated_at,
        )
        assert result.result.preflight_status == "ready"
        assert result.result.decision_active is True
        assert result.result.decision_expired is False
        session.close()

    def test_evaluated_at_equals_expiry_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
        _, d2_msg_id, _ = _seed_d2_decision(
            SessionLocal, decision_expires_at=expires_at
        )

        svc, session = _make_d3_service(SessionLocal)
        result = svc.prepare_human_escalation_decision_consumption_preflight(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            evaluated_at=expires_at,
        )
        assert result.result.preflight_status == "blocked"
        assert "human_escalation_decision_expired" in result.result.blocked_reasons
        session.close()

    def test_evaluated_at_after_expiry_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
        _, d2_msg_id, _ = _seed_d2_decision(
            SessionLocal, decision_expires_at=expires_at
        )

        svc, session = _make_d3_service(SessionLocal)
        evaluated_at = expires_at + timedelta(seconds=10)
        result = svc.prepare_human_escalation_decision_consumption_preflight(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            evaluated_at=evaluated_at,
        )
        assert result.result.preflight_status == "blocked"
        assert "human_escalation_decision_expired" in result.result.blocked_reasons
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 9. TestPreflightBlocked
# ══════════════════════════════════════════════════════════════════════


class TestPreflightBlocked:
    def test_revoked_decision_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        # Revoke first
        svc_r, session_r = _make_d3_service(SessionLocal)
        revoke_result = svc_r.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            actor="human-reviewer",
            client_request_id=f"revoke-{uuid4()}",
        )
        assert revoke_result.result.revocation_status == "revoked"
        session_r.close()

        # Preflight should be blocked
        svc_p, session_p = _make_d3_service(SessionLocal)
        pf = svc_p.prepare_human_escalation_decision_consumption_preflight(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            evaluated_at=datetime.now(timezone.utc),
        )
        assert pf.result.preflight_status == "blocked"
        assert "human_escalation_decision_already_revoked" in pf.result.blocked_reasons
        session_p.close()

    def test_consumed_decision_blocked(self, db_engine) -> None:
        """Consumed decisions should be blocked. Construct a fake D4 consumption message."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        decision_result, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        # Insert a fake D4 consumption message
        session = SessionLocal()
        consumption_action = {
            "type": "p21_d_sandbox_candidate_diff_review_human_escalation_decision_consumption_record",
            "session_id": str(SESSION_ID),
            "source_task_id": str(TASK_ID),
            "source_decision_message_id": str(d2_msg_id),
            "decision_id": str(decision_result.result.decision_id),
            "decision_consumed": True,
        }
        session.add(
            ProjectDirectorMessageTable(
                id=uuid4(),
                session_id=SESSION_ID,
                role="assistant",
                content="Decision consumed.",
                sequence_no=500,
                intent="sandbox_candidate_diff_review_human_escalation_decision_consumption",
                source="system",
                source_detail="p21_d_sandbox_candidate_diff_review_human_escalation_decision_consumed",
                suggested_actions_json=json.dumps([consumption_action]),
                requires_confirmation=False,
                risk_level="high",
                related_project_id=PROJECT_ID,
                related_task_id=TASK_ID,
            )
        )
        session.commit()
        session.close()

        svc, session = _make_d3_service(SessionLocal)
        pf = svc.prepare_human_escalation_decision_consumption_preflight(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            evaluated_at=datetime.now(timezone.utc),
        )
        assert pf.result.preflight_status == "blocked"
        assert "human_escalation_decision_already_consumed" in pf.result.blocked_reasons
        session.close()

    def test_already_has_ready_preflight_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        svc1, session1 = _make_d3_service(SessionLocal)
        first_pf = svc1.prepare_human_escalation_decision_consumption_preflight(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            evaluated_at=datetime.now(timezone.utc),
        )
        assert first_pf.result.preflight_status == "ready"
        session1.close()

        svc2, session2 = _make_d3_service(SessionLocal)
        second_pf = svc2.prepare_human_escalation_decision_consumption_preflight(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            evaluated_at=datetime.now(timezone.utc) + timedelta(seconds=1),
        )
        assert second_pf.result.preflight_status == "blocked"
        assert "human_escalation_decision_consumption_preflight_already_prepared" in second_pf.result.blocked_reasons
        session2.close()

    def test_session_missing_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        svc, session = _make_d3_service(SessionLocal)
        pf = svc.prepare_human_escalation_decision_consumption_preflight(
            session_id=uuid4(),
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            evaluated_at=datetime.now(timezone.utc),
        )
        assert pf.result.preflight_status == "blocked"
        assert "session_missing" in pf.result.blocked_reasons
        session.close()

    def test_task_missing_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        svc, session = _make_d3_service(SessionLocal)
        pf = svc.prepare_human_escalation_decision_consumption_preflight(
            session_id=SESSION_ID,
            source_task_id=uuid4(),
            source_message_id=d2_msg_id,
            evaluated_at=datetime.now(timezone.utc),
        )
        assert pf.result.preflight_status == "blocked"
        assert "source_task_missing" in pf.result.blocked_reasons
        session.close()

    def test_message_missing_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        svc, session = _make_d3_service(SessionLocal)
        pf = svc.prepare_human_escalation_decision_consumption_preflight(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=uuid4(),
            evaluated_at=datetime.now(timezone.utc),
        )
        assert pf.result.preflight_status == "blocked"
        assert "source_human_escalation_decision_message_missing" in pf.result.blocked_reasons
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 10. TestPreflightSourceVerification
# ══════════════════════════════════════════════════════════════════════


class TestPreflightSourceVerification:
    def _seed_tamper_and_preflight(
        self, db_engine, *, tamper_fn, expected_reason
    ):
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        # Tamper the D2 message
        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, d2_msg_id)
        tamper_fn(row)
        session.commit()
        session.close()

        svc, session = _make_d3_service(SessionLocal)
        pf = svc.prepare_human_escalation_decision_consumption_preflight(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            evaluated_at=datetime.now(timezone.utc),
        )
        assert pf.result.preflight_status == "blocked"
        assert expected_reason in pf.result.blocked_reasons
        session.close()

    def test_session_tampered(self, db_engine) -> None:
        """Tamper session_id with a foreign session that exists in the DB."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        # Insert a foreign session so FK passes
        foreign_session_id = uuid4()
        session = SessionLocal()
        session.add(
            ProjectDirectorSessionTable(
                id=foreign_session_id, project_id=PROJECT_ID,
                goal_text="Foreign", constraints="", status="confirmed",
            )
        )
        session.flush()
        row = session.get(ProjectDirectorMessageTable, d2_msg_id)
        row.session_id = foreign_session_id
        session.commit()
        session.close()

        svc, session = _make_d3_service(SessionLocal)
        pf = svc.prepare_human_escalation_decision_consumption_preflight(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            evaluated_at=datetime.now(timezone.utc),
        )
        assert pf.result.preflight_status == "blocked"
        assert "source_decision_session_mismatch" in pf.result.blocked_reasons
        session.close()

    def test_task_tampered(self, db_engine) -> None:
        """Tamper related_task_id with a foreign task that exists in the DB."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        foreign_task_id = uuid4()
        session = SessionLocal()
        session.add(
            TaskTable(
                id=foreign_task_id,
                project_id=PROJECT_ID,
                title="Foreign task",
                status="pending",
                priority="normal",
                input_summary="FOREIGN",
                risk_level="normal",
                human_status="none",
                source_draft_id="p12-foreign",
                acceptance_criteria="[]",
            )
        )
        session.flush()
        row = session.get(ProjectDirectorMessageTable, d2_msg_id)
        row.related_task_id = foreign_task_id
        session.commit()
        session.close()

        svc, session = _make_d3_service(SessionLocal)
        pf = svc.prepare_human_escalation_decision_consumption_preflight(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            evaluated_at=datetime.now(timezone.utc),
        )
        assert pf.result.preflight_status == "blocked"
        assert "source_decision_task_mismatch" in pf.result.blocked_reasons
        session.close()

    def test_role_tampered(self, db_engine) -> None:
        def tamper(row):
            row.role = "assistant"
        self._seed_tamper_and_preflight(db_engine, tamper_fn=tamper, expected_reason="source_decision_role_invalid")

    def test_source_tampered(self, db_engine) -> None:
        def tamper(row):
            row.source = "ai"
        self._seed_tamper_and_preflight(db_engine, tamper_fn=tamper, expected_reason="source_decision_source_invalid")

    def test_intent_tampered(self, db_engine) -> None:
        def tamper(row):
            row.intent = "wrong_intent"
        self._seed_tamper_and_preflight(db_engine, tamper_fn=tamper, expected_reason="source_decision_intent_invalid")

    def test_source_detail_tampered(self, db_engine) -> None:
        def tamper(row):
            row.source_detail = "wrong_detail"
        self._seed_tamper_and_preflight(db_engine, tamper_fn=tamper, expected_reason="source_message_is_not_p21_d_d2_decision")

    def test_requires_confirmation_tampered(self, db_engine) -> None:
        def tamper(row):
            row.requires_confirmation = True
        self._seed_tamper_and_preflight(db_engine, tamper_fn=tamper, expected_reason="source_decision_confirmation_contract_invalid")

    def test_risk_level_tampered(self, db_engine) -> None:
        def tamper(row):
            row.risk_level = "low"
        self._seed_tamper_and_preflight(db_engine, tamper_fn=tamper, expected_reason="source_decision_risk_level_invalid")

    def test_action_type_tampered(self, db_engine) -> None:
        def tamper(row):
            actions = json.loads(row.suggested_actions_json)
            actions[0]["type"] = "wrong_type"
            row.suggested_actions_json = json.dumps(actions)
        self._seed_tamper_and_preflight(db_engine, tamper_fn=tamper, expected_reason="source_human_escalation_decision_record_missing")

    def test_schema_version_tampered(self, db_engine) -> None:
        def tamper(row):
            actions = json.loads(row.suggested_actions_json)
            actions[0]["schema_version"] = "wrong"
            row.suggested_actions_json = json.dumps(actions)
        self._seed_tamper_and_preflight(db_engine, tamper_fn=tamper, expected_reason="human_escalation_decision_schema_version_mismatch")

    def test_project_tampered(self, db_engine) -> None:
        """Tamper related_project_id with a foreign project that exists in the DB."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        foreign_project_id = uuid4()
        session = SessionLocal()
        session.add(
            ProjectTable(
                id=foreign_project_id,
                name="Foreign",
                summary="Foreign project",
                status="active",
                stage="intake",
            )
        )
        session.flush()
        row = session.get(ProjectDirectorMessageTable, d2_msg_id)
        row.related_project_id = foreign_project_id
        session.commit()
        session.close()

        svc, session = _make_d3_service(SessionLocal)
        pf = svc.prepare_human_escalation_decision_consumption_preflight(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            evaluated_at=datetime.now(timezone.utc),
        )
        assert pf.result.preflight_status == "blocked"
        assert "source_decision_project_mismatch" in pf.result.blocked_reasons
        session.close()

    def test_empty_actions_blocked(self, db_engine) -> None:
        def tamper(row):
            row.suggested_actions_json = "[]"
        self._seed_tamper_and_preflight(db_engine, tamper_fn=tamper, expected_reason="source_human_escalation_decision_record_missing")

    def test_two_actions_blocked(self, db_engine) -> None:
        def tamper(row):
            actions = json.loads(row.suggested_actions_json)
            row.suggested_actions_json = json.dumps([actions[0], actions[0]])
        self._seed_tamper_and_preflight(db_engine, tamper_fn=tamper, expected_reason="source_human_escalation_decision_record_missing")

    def test_requires_confirmation_false_ok(self, db_engine) -> None:
        """D2 decision message has requires_confirmation=False which is correct."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        svc, session = _make_d3_service(SessionLocal)
        pf = svc.prepare_human_escalation_decision_consumption_preflight(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            evaluated_at=datetime.now(timezone.utc),
        )
        assert pf.result.preflight_status == "ready"
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 11. TestPreflightConcurrency
# ══════════════════════════════════════════════════════════════════════


class TestPreflightConcurrency:
    def test_concurrent_preflight_one_ready_one_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        barrier = threading.Barrier(2, timeout=30)
        results: list[dict] = []
        lock = threading.Lock()

        def _preflight(thread_id: int):
            barrier.wait()
            svc, session = _make_d3_service(SessionLocal)
            evaluated_at = datetime.now(timezone.utc) + timedelta(seconds=thread_id)
            result = svc.prepare_human_escalation_decision_consumption_preflight(
                session_id=SESSION_ID,
                source_task_id=TASK_ID,
                source_message_id=d2_msg_id,
                evaluated_at=evaluated_at,
            )
            with lock:
                results.append({
                    "thread_id": thread_id,
                    "status": result.result.preflight_status,
                    "reasons": result.result.blocked_reasons,
                })
            session.close()

        t1 = threading.Thread(target=_preflight, args=(1,))
        t2 = threading.Thread(target=_preflight, args=(2,))
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        assert len(results) == 2
        statuses = [r["status"] for r in results]
        assert "ready" in statuses
        assert "blocked" in statuses

        blocked_result = [r for r in results if r["status"] == "blocked"][0]
        assert "human_escalation_decision_consumption_preflight_already_prepared" in blocked_result["reasons"]

        # Verify exactly one DB preflight record
        verify = SessionLocal()
        count = verify.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd"
            ),
            {"sd": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL},
        ).scalar()
        assert count == 1
        verify.close()


# ══════════════════════════════════════════════════════════════════════
# 12. TestAppendOnly
# ══════════════════════════════════════════════════════════════════════


class TestAppendOnly:
    def test_d2_message_unchanged_after_revoke(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        # Capture D2 message state before revoke
        session = SessionLocal()
        before = session.get(ProjectDirectorMessageTable, d2_msg_id)
        before_actions = before.suggested_actions_json
        before_content = before.content
        before_role = before.role
        before_source = before.source
        before_intent = before.intent
        before_source_detail = before.source_detail
        before_requires_confirmation = before.requires_confirmation
        before_risk_level = before.risk_level
        session.close()

        svc, session = _make_d3_service(SessionLocal)
        revoke_result = svc.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            actor="human-reviewer",
            client_request_id=f"revoke-{uuid4()}",
        )
        assert revoke_result.result.revocation_status == "revoked"
        session.close()

        # Verify D2 message unchanged
        session = SessionLocal()
        after = session.get(ProjectDirectorMessageTable, d2_msg_id)
        assert after.suggested_actions_json == before_actions
        assert after.content == before_content
        assert after.role == before_role
        assert after.source == before_source
        assert after.intent == before_intent
        assert after.source_detail == before_source_detail
        assert after.requires_confirmation == before_requires_confirmation
        assert after.risk_level == before_risk_level
        session.close()

    def test_d2_message_unchanged_after_preflight(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        session = SessionLocal()
        before = session.get(ProjectDirectorMessageTable, d2_msg_id)
        before_actions = before.suggested_actions_json
        before_content = before.content
        session.close()

        svc, session = _make_d3_service(SessionLocal)
        pf = svc.prepare_human_escalation_decision_consumption_preflight(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            evaluated_at=datetime.now(timezone.utc),
        )
        assert pf.result.preflight_status == "ready"
        session.close()

        session = SessionLocal()
        after = session.get(ProjectDirectorMessageTable, d2_msg_id)
        assert after.suggested_actions_json == before_actions
        assert after.content == before_content
        session.close()

    def test_no_task_run_worker_created_by_revoke(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        svc, session = _make_d3_service(SessionLocal)
        revoke_result = svc.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            actor="human-reviewer",
            client_request_id=f"revoke-{uuid4()}",
        )
        assert revoke_result.result.revocation_status == "revoked"
        session.close()

        # Verify action has all side-effect flags false
        msg = revoke_result.message
        assert msg is not None
        action = msg.suggested_actions[0]
        for flag in [
            "decision_consumption_started",
            "decision_consumed",
            "continuation_started",
            "rework_started",
            "approval_request_created",
            "legacy_approval_decision_created",
            "main_project_file_written",
            "sandbox_file_written",
            "manifest_file_written",
            "diff_file_written",
            "patch_applied",
            "git_write_performed",
            "worktree_created",
            "worker_started",
            "task_created",
            "run_created",
            "gate_allows_write",
        ]:
            assert action.get(flag) is False, f"{flag} should be False"
        assert action["ai_project_director_total_loop"] == "Partial"

    def test_no_task_run_worker_created_by_preflight(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        svc, session = _make_d3_service(SessionLocal)
        pf = svc.prepare_human_escalation_decision_consumption_preflight(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            evaluated_at=datetime.now(timezone.utc),
        )
        assert pf.result.preflight_status == "ready"
        session.close()

        msg = pf.message
        assert msg is not None
        action = msg.suggested_actions[0]
        for flag in [
            "decision_consumption_started",
            "decision_consumed",
            "continuation_started",
            "rework_started",
            "approval_request_created",
            "legacy_approval_decision_created",
            "main_project_file_written",
            "sandbox_file_written",
            "manifest_file_written",
            "diff_file_written",
            "patch_applied",
            "git_write_performed",
            "worktree_created",
            "worker_started",
            "task_created",
            "run_created",
            "gate_allows_write",
        ]:
            assert action.get(flag) is False, f"{flag} should be False"
        assert action["ai_project_director_total_loop"] == "Partial"

    def test_revocation_forbidden_actions_list(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        svc, session = _make_d3_service(SessionLocal)
        revoke_result = svc.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            actor="human-reviewer",
            client_request_id=f"revoke-{uuid4()}",
        )
        assert revoke_result.result.revocation_status == "revoked"
        session.close()

        msg = revoke_result.message
        assert msg is not None
        forbidden = msg.forbidden_actions_detected
        for required in [
            "no_decision_consumption",
            "no_continuation_start",
            "no_rework_start",
            "no_task_creation",
            "no_run_creation",
            "no_worker_dispatch",
            "no_worktree_creation",
            "no_workspace_write",
            "no_main_project_file_write",
            "no_manifest_write",
            "no_diff_file_write",
            "no_patch_apply",
            "no_product_runtime_git_write",
            "no_pr_creation",
            "no_merge",
            "no_ci_trigger",
            "no_legacy_approval_request",
            "no_legacy_approval_decision",
        ]:
            assert required in forbidden

    def test_preflight_forbidden_actions_list(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        svc, session = _make_d3_service(SessionLocal)
        pf = svc.prepare_human_escalation_decision_consumption_preflight(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            evaluated_at=datetime.now(timezone.utc),
        )
        assert pf.result.preflight_status == "ready"
        session.close()

        msg = pf.message
        assert msg is not None
        forbidden = msg.forbidden_actions_detected
        for required in [
            "no_decision_consumption",
            "no_continuation_start",
            "no_rework_start",
            "no_task_creation",
            "no_run_creation",
            "no_worker_dispatch",
            "no_worktree_creation",
            "no_workspace_write",
            "no_main_project_file_write",
            "no_manifest_write",
            "no_diff_file_write",
            "no_patch_apply",
            "no_product_runtime_git_write",
            "no_pr_creation",
            "no_merge",
            "no_ci_trigger",
            "no_legacy_approval_request",
            "no_legacy_approval_decision",
        ]:
            assert required in forbidden

    def test_revocation_db_count_exactly_one(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        svc, session = _make_d3_service(SessionLocal)
        revoke_result = svc.revoke_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            actor="human-reviewer",
            client_request_id=f"revoke-{uuid4()}",
        )
        assert revoke_result.result.revocation_status == "revoked"
        msg_id = revoke_result.message.id
        session.close()

        verify = SessionLocal()
        row = verify.get(ProjectDirectorMessageTable, msg_id)
        assert row is not None
        assert row.role == "user"
        assert row.source == "system"
        assert row.requires_confirmation is False
        assert row.risk_level == "high"
        assert row.source_detail == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_SOURCE_DETAIL
        assert row.intent == "sandbox_candidate_diff_review_human_escalation_decision_revocation"

        actions = json.loads(row.suggested_actions_json)
        assert len(actions) == 1
        act = actions[0]
        assert act["type"] == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_ACTION_TYPE
        assert act["schema_version"] == HUMAN_ESCALATION_DECISION_REVOCATION_SCHEMA_VERSION
        assert act["revocation_status"] == "revoked"

        count = verify.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd"
            ),
            {"sd": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_SOURCE_DETAIL},
        ).scalar()
        assert count == 1
        verify.close()

    def test_preflight_db_count_exactly_one(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _, d2_msg_id, _ = _seed_d2_decision(SessionLocal)

        svc, session = _make_d3_service(SessionLocal)
        pf = svc.prepare_human_escalation_decision_consumption_preflight(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=d2_msg_id,
            evaluated_at=datetime.now(timezone.utc),
        )
        assert pf.result.preflight_status == "ready"
        msg_id = pf.message.id
        session.close()

        verify = SessionLocal()
        row = verify.get(ProjectDirectorMessageTable, msg_id)
        assert row is not None
        assert row.role == "assistant"
        assert row.source == "system"
        assert row.requires_confirmation is False
        assert row.risk_level == "high"
        assert row.source_detail == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL
        assert row.intent == "sandbox_candidate_diff_review_human_escalation_decision_consumption_preflight"

        actions = json.loads(row.suggested_actions_json)
        assert len(actions) == 1
        act = actions[0]
        assert act["type"] == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_ACTION_TYPE
        assert act["schema_version"] == HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION
        assert act["preflight_status"] == "ready"

        count = verify.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd"
            ),
            {"sd": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL},
        ).scalar()
        assert count == 1
        verify.close()
