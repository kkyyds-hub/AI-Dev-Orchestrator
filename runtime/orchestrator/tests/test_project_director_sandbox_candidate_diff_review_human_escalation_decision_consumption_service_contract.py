"""Contract tests for P21-D-D4 human escalation decision consumption service."""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db_tables import (
    ORMBase,
    ProjectDirectorMessageTable,
    ProjectDirectorSessionTable,
    ProjectTable,
    TaskTable,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
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
from app.services.project_director_sandbox_candidate_diff_review_human_escalation_decision_consumption_service import (
    HUMAN_ESCALATION_DECISION_CONSUMPTION_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionService,
)
from app.services.project_director_sandbox_candidate_diff_review_human_escalation_decision_lifecycle_service import (
    HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION,
    HUMAN_ESCALATION_DECISION_REVOCATION_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionLifecycleService,
)
from app.services.project_director_sandbox_candidate_diff_review_human_escalation_decision_service import (
    HUMAN_ESCALATION_DECISION_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionService,
)
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


# ── Service helpers ─────────────────────────────────────────────────


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


def _make_d4_service(session_local):
    session = session_local()
    msg_repo = ProjectDirectorMessageRepository(session)
    sess_repo = ProjectDirectorSessionRepository(session)
    task_repo = TaskRepository(session)
    svc = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
    )
    return svc, session


def _seed_full_chain(
    SessionLocal,
    decision_action="APPROVE_CONTINUE",
    expires_hours=1,
    *,
    d2_expires_at: datetime | None = None,
    d3_evaluated_at: datetime | None = None,
):
    """Seed D1+D2+D3-preflight, return (preflight_result, preflight_msg_id, d2_msg_id, pkg_msg_id)."""
    # D1
    pkg_msg_id, _pkg_seq = _d1_prepare(SessionLocal)

    # D2
    expires = d2_expires_at or datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    d2_svc, d2_session = _make_d2_service(SessionLocal)
    d2_result = d2_svc.record_human_escalation_decision(
        session_id=SESSION_ID,
        source_task_id=TASK_ID,
        source_message_id=pkg_msg_id,
        decision_action=decision_action,
        actor="test-actor",
        client_request_id=f"req-{uuid4()}",
        decision_expires_at=expires,
    )
    assert d2_result.result.decision_status == "recorded"
    assert d2_result.message is not None
    d2_msg_id = d2_result.message.id
    d2_session.close()

    # D3
    d3_svc, d3_session = _make_d3_service(SessionLocal)
    d3_result = d3_svc.prepare_human_escalation_decision_consumption_preflight(
        session_id=SESSION_ID,
        source_task_id=TASK_ID,
        source_message_id=d2_msg_id,
        evaluated_at=d3_evaluated_at,
    )
    assert d3_result.result.preflight_status == "ready"
    assert d3_result.message is not None
    preflight_msg_id = d3_result.message.id
    d3_session.close()

    return d3_result, preflight_msg_id, d2_msg_id, pkg_msg_id


def _seed_filler_messages(session: Session, start_seq: int, count: int = 105) -> None:
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


def _seed_revocation_message(
    session: Session,
    *,
    d2_msg_id: UUID,
    decision_id: UUID,
    seq_no: int = 200,
) -> UUID:
    """Seed a D3 revocation message for the given decision."""
    revocation_msg_id = uuid4()
    action = {
        "type": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_ACTION_TYPE,
        "schema_version": HUMAN_ESCALATION_DECISION_REVOCATION_SCHEMA_VERSION,
        "session_id": str(SESSION_ID),
        "source_task_id": str(TASK_ID),
        "revocation_status": "revoked",
        "revocation_id": str(uuid4()),
        "source_decision_message_id": str(d2_msg_id),
        "decision_id": str(decision_id),
        "source_package_message_id": str(uuid4()),
        "escalation_package_id": str(uuid4()),
        "decision_confirmation_fingerprint": "a" * 64,
        "revalidated_decision_confirmation_fingerprint": "a" * 64,
        "revoke_actor_type": "human",
        "revoke_actor": "test-revoker",
        "revoke_client_request_id": f"revoke-{uuid4()}",
        "revoked_at": datetime.now(timezone.utc).isoformat(),
        "source_decision_validated": True,
        "decision_fingerprint_revalidated": True,
        "replay_check_completed": True,
        "prior_revocation_detected": False,
        "decision_revoked": True,
        "decision_expired": False,
        "decision_consumption_started": False,
        "decision_consumed": False,
        "continuation_started": False,
        "rework_started": False,
        "approval_request_created": False,
        "legacy_approval_decision_created": False,
        "main_project_file_written": False,
        "sandbox_file_written": False,
        "manifest_file_written": False,
        "diff_file_written": False,
        "patch_applied": False,
        "git_write_performed": False,
        "worktree_created": False,
        "worker_started": False,
        "task_created": False,
        "run_created": False,
        "gate_allows_write": False,
        "ai_project_director_total_loop": "Partial",
    }
    session.add(
        ProjectDirectorMessageTable(
            id=revocation_msg_id,
            session_id=SESSION_ID,
            role="user",
            content="Decision revoked.",
            sequence_no=seq_no,
            intent="sandbox_candidate_diff_review_human_escalation_decision_revocation",
            source="system",
            source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False,
            risk_level="high",
            related_project_id=PROJECT_ID,
            related_task_id=TASK_ID,
        )
    )
    session.commit()
    return revocation_msg_id


def _seed_prior_consumption_message(
    session: Session,
    *,
    d2_msg_id: UUID | None = None,
    decision_id: UUID | None = None,
    preflight_msg_id: UUID | None = None,
    preflight_id: UUID | None = None,
    seq_no: int = 200,
) -> UUID:
    """Seed a D4 consumption message to trigger prior-consumption detection."""
    consumption_msg_id = uuid4()
    action = {
        "type": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_ACTION_TYPE,
        "schema_version": HUMAN_ESCALATION_DECISION_CONSUMPTION_SCHEMA_VERSION,
        "session_id": str(SESSION_ID),
        "source_task_id": str(TASK_ID),
        "consumption_status": "consumed",
        "consumption_id": str(uuid4()),
        "source_preflight_message_id": str(preflight_msg_id or uuid4()),
        "preflight_id": str(preflight_id or uuid4()),
        "source_decision_message_id": str(d2_msg_id or uuid4()),
        "decision_id": str(decision_id or uuid4()),
        "source_package_message_id": str(uuid4()),
        "escalation_package_id": str(uuid4()),
        "decision_action": "APPROVE_CONTINUE",
        "decision_confirmation_fingerprint": "a" * 64,
        "revalidated_decision_confirmation_fingerprint": "a" * 64,
        "aggregate_evidence_fingerprint": "b" * 64,
        "consumption_evidence_fingerprint": "c" * 64,
        "decision_created_at": datetime.now(timezone.utc).isoformat(),
        "decision_expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "preflight_evaluated_at": datetime.now(timezone.utc).isoformat(),
        "consumed_at": datetime.now(timezone.utc).isoformat(),
        "source_preflight_validated": True,
        "source_decision_validated": True,
        "decision_fingerprint_revalidated": True,
        "exact_preflight_decision_binding_validated": True,
        "replay_check_completed": True,
        "decision_active_at_consumption": True,
        "decision_expired": False,
        "decision_revoked": False,
        "prior_consumption_detected": False,
        "blocked_reasons": [],
        "transition_kind": "CONTINUE_GUARDRAIL",
        "continuation_guardrail_eligible": True,
        "bounded_rework_guardrail_eligible": False,
        "terminal_rejection": False,
        "gate_allows_protected_transition_guardrail": True,
        "decision_consumption_started": True,
        "decision_consumed": True,
        "continuation_started": False,
        "rework_started": False,
        "approval_request_created": False,
        "legacy_approval_decision_created": False,
        "main_project_file_written": False,
        "sandbox_file_written": False,
        "manifest_file_written": False,
        "diff_file_written": False,
        "patch_applied": False,
        "git_write_performed": False,
        "worktree_created": False,
        "worker_started": False,
        "task_created": False,
        "run_created": False,
        "gate_allows_write": False,
        "ai_project_director_total_loop": "Partial",
    }
    session.add(
        ProjectDirectorMessageTable(
            id=consumption_msg_id,
            session_id=SESSION_ID,
            role="assistant",
            content="Decision consumed.",
            sequence_no=seq_no,
            intent="sandbox_candidate_diff_review_human_escalation_decision_consumption",
            source="system",
            source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False,
            risk_level="high",
            related_project_id=PROJECT_ID,
            related_task_id=TASK_ID,
        )
    )
    session.commit()
    return consumption_msg_id


def _seed_prior_preflight_message(
    session: Session,
    *,
    d2_msg_id: UUID,
    decision_id: UUID,
    seq_no: int = 200,
) -> UUID:
    """Seed a D3 preflight message to trigger multiple-ready-preflights detection."""
    preflight_msg_id = uuid4()
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    evaluated = datetime.now(timezone.utc)
    action = {
        "type": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_ACTION_TYPE,
        "schema_version": HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION,
        "session_id": str(SESSION_ID),
        "source_task_id": str(TASK_ID),
        "preflight_status": "ready",
        "preflight_id": str(uuid4()),
        "source_decision_message_id": str(d2_msg_id),
        "decision_id": str(decision_id),
        "source_package_message_id": str(uuid4()),
        "escalation_package_id": str(uuid4()),
        "decision_action": "APPROVE_CONTINUE",
        "decision_confirmation_fingerprint": "a" * 64,
        "revalidated_decision_confirmation_fingerprint": "a" * 64,
        "decision_created_at": datetime.now(timezone.utc).isoformat(),
        "decision_expires_at": expires.isoformat(),
        "evaluated_at": evaluated.isoformat(),
        "source_decision_validated": True,
        "decision_fingerprint_revalidated": True,
        "replay_check_completed": True,
        "decision_active": True,
        "decision_expired": False,
        "decision_revoked": False,
        "prior_consumption_preflight_detected": False,
        "continuation_eligible": True,
        "rework_eligible": False,
        "rejection_terminal": False,
        "blocked_reasons": [],
        "decision_consumption_started": False,
        "decision_consumed": False,
        "continuation_started": False,
        "rework_started": False,
        "approval_request_created": False,
        "legacy_approval_decision_created": False,
        "main_project_file_written": False,
        "sandbox_file_written": False,
        "manifest_file_written": False,
        "diff_file_written": False,
        "patch_applied": False,
        "git_write_performed": False,
        "worktree_created": False,
        "worker_started": False,
        "task_created": False,
        "run_created": False,
        "gate_allows_write": False,
        "ai_project_director_total_loop": "Partial",
    }
    session.add(
        ProjectDirectorMessageTable(
            id=preflight_msg_id,
            session_id=SESSION_ID,
            role="assistant",
            content="Extra preflight.",
            sequence_no=seq_no,
            intent="sandbox_candidate_diff_review_human_escalation_decision_consumption_preflight",
            source="system",
            source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False,
            risk_level="high",
            related_project_id=PROJECT_ID,
            related_task_id=TASK_ID,
        )
    )
    session.commit()
    return preflight_msg_id


# ══════════════════════════════════════════════════════════════════════
# 1. TestConstants
# ══════════════════════════════════════════════════════════════════════


class TestConstants:
    def test_source_detail(self) -> None:
        assert (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_SOURCE_DETAIL
            == "p21_d_sandbox_candidate_diff_review_human_escalation_decision_consumed"
        )

    def test_action_type(self) -> None:
        assert (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_ACTION_TYPE
            == "p21_d_sandbox_candidate_diff_review_human_escalation_decision_consumption_record"
        )

    def test_schema_version(self) -> None:
        assert HUMAN_ESCALATION_DECISION_CONSUMPTION_SCHEMA_VERSION == "p21-d-d4.v1"


# ══════════════════════════════════════════════════════════════════════
# 2. TestThreeTransitionMappings
# ══════════════════════════════════════════════════════════════════════


class TestThreeTransitionMappings:
    _EXPECTED_COMMON = {
        "decision_consumption_started": True,
        "decision_consumed": True,
        "continuation_started": False,
        "rework_started": False,
        "gate_allows_write": False,
    }

    _TRANSITION_EXPECTATIONS = {
        "APPROVE_CONTINUE": {
            "transition_kind": "CONTINUE_GUARDRAIL",
            "continuation_guardrail_eligible": True,
            "bounded_rework_guardrail_eligible": False,
            "terminal_rejection": False,
            "gate_allows_protected_transition_guardrail": True,
        },
        "REQUEST_REWORK": {
            "transition_kind": "BOUNDED_REWORK_GUARDRAIL",
            "continuation_guardrail_eligible": False,
            "bounded_rework_guardrail_eligible": True,
            "terminal_rejection": False,
            "gate_allows_protected_transition_guardrail": True,
        },
        "REJECT": {
            "transition_kind": "TERMINAL_REJECTION",
            "continuation_guardrail_eligible": False,
            "bounded_rework_guardrail_eligible": False,
            "terminal_rejection": True,
            "gate_allows_protected_transition_guardrail": False,
        },
    }

    @pytest.mark.parametrize(
        "decision_action",
        ["APPROVE_CONTINUE", "REQUEST_REWORK", "REJECT"],
    )
    def test_transition_mapping(self, db_engine, decision_action: str) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf_result, pf_msg_id, _d2_msg_id, _pkg_msg_id = _seed_full_chain(
            SessionLocal, decision_action=decision_action
        )

        svc, svc_session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pf_msg_id,
        )
        assert result.result.consumption_status == "consumed"
        assert result.message is not None

        expected = self._TRANSITION_EXPECTATIONS[decision_action]
        for field, value in expected.items():
            assert getattr(result.result, field) == value, f"{field} mismatch for {decision_action}"

        for field, value in self._EXPECTED_COMMON.items():
            assert getattr(result.result, field) == value, f"{field} mismatch for {decision_action}"

        assert result.result.decision_active_at_consumption is True
        assert result.result.decision_expired is False
        assert result.result.decision_revoked is False
        assert result.result.prior_consumption_detected is False
        assert result.result.blocked_reasons == []

        # Message role and source
        assert result.message.role == ProjectDirectorMessageRole.ASSISTANT
        assert result.message.source == ProjectDirectorMessageSource.SYSTEM
        assert result.message.requires_confirmation is False
        assert result.message.risk_level == ProjectDirectorMessageRiskLevel.HIGH

        svc_session.close()


# ══════════════════════════════════════════════════════════════════════
# 3. TestD3PreflightValidation
# ══════════════════════════════════════════════════════════════════════


class TestD3PreflightValidation:
    def _assert_blocked(
        self,
        SessionLocal,
        *,
        preflight_msg_id: UUID,
        reason: str,
    ) -> None:
        svc, session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=preflight_msg_id,
        )
        assert result.result.consumption_status == "blocked"
        assert reason in result.result.blocked_reasons
        assert result.message is None
        session.close()

    def test_preflight_missing(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        svc, session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=uuid4(),
        )
        assert result.result.consumption_status == "blocked"
        assert "source_consumption_preflight_message_missing" in result.result.blocked_reasons
        session.close()

    def test_session_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        foreign_session_id = uuid4()
        session = SessionLocal()
        session.add(
            ProjectDirectorSessionTable(
                id=foreign_session_id, project_id=PROJECT_ID,
                goal_text="Foreign", constraints="", status="confirmed",
            )
        )
        session.flush()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        row.session_id = foreign_session_id
        session.commit()
        session.close()

        self._assert_blocked(
            SessionLocal,
            preflight_msg_id=pf_msg_id,
            reason="source_preflight_session_mismatch",
        )

    def test_project_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        foreign_project_id = uuid4()
        session = SessionLocal()
        session.add(
            ProjectTable(
                id=foreign_project_id, name="Foreign", summary="Foreign project",
                status="active", stage="intake",
            )
        )
        session.flush()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        row.related_project_id = foreign_project_id
        session.commit()
        session.close()

        self._assert_blocked(
            SessionLocal,
            preflight_msg_id=pf_msg_id,
            reason="source_preflight_project_mismatch",
        )

    def test_task_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        foreign_task_id = uuid4()
        session = SessionLocal()
        session.add(
            TaskTable(
                id=foreign_task_id, project_id=PROJECT_ID,
                title="Foreign", status="pending", priority="normal",
                input_summary="FOREIGN", risk_level="normal",
                human_status="none", source_draft_id="p12-f",
                acceptance_criteria="[]",
            )
        )
        session.flush()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        row.related_task_id = foreign_task_id
        session.commit()
        session.close()

        self._assert_blocked(
            SessionLocal,
            preflight_msg_id=pf_msg_id,
            reason="source_preflight_task_mismatch",
        )

    def test_wrong_role(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        row.role = "user"
        session.commit()
        session.close()

        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="source_preflight_role_invalid",
        )

    def test_wrong_source(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        row.source = "ai"
        session.commit()
        session.close()

        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="source_preflight_source_invalid",
        )

    def test_wrong_intent(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        row.intent = "wrong_intent"
        session.commit()
        session.close()

        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="source_preflight_intent_invalid",
        )

    def test_wrong_source_detail(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        row.source_detail = "wrong_detail"
        session.commit()
        session.close()

        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="source_message_is_not_p21_d_d3_ready_preflight",
        )

    def test_wrong_confirmation(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        row.requires_confirmation = True
        session.commit()
        session.close()

        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="source_preflight_confirmation_contract_invalid",
        )

    def test_wrong_risk_level(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        row.risk_level = "low"
        session.commit()
        session.close()

        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="source_preflight_risk_level_invalid",
        )

    def test_empty_actions(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        row.suggested_actions_json = "[]"
        session.commit()
        session.close()

        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="source_consumption_preflight_record_missing",
        )

    def test_wrong_action_type(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["type"] = "wrong_type"
        row.suggested_actions_json = json.dumps([action])
        session.commit()
        session.close()

        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="source_consumption_preflight_record_invalid",
        )

    def test_wrong_schema_version(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["schema_version"] = "wrong"
        row.suggested_actions_json = json.dumps([action])
        session.commit()
        session.close()

        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="source_consumption_preflight_record_invalid",
        )

    def test_preflight_status_not_ready(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["preflight_status"] = "blocked"
        row.suggested_actions_json = json.dumps([action])
        session.commit()
        session.close()

        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="source_preflight_domain_reconstruction_invalid",
        )

    def test_source_decision_id_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["source_decision_message_id"] = str(uuid4())
        row.suggested_actions_json = json.dumps([action])
        session.commit()
        session.close()

        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="source_human_escalation_decision_message_missing",
        )

    def test_decision_id_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["decision_id"] = str(uuid4())
        row.suggested_actions_json = json.dumps([action])
        session.commit()
        session.close()

        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="consumption_preflight_decision_binding_mismatch",
        )

    def test_package_id_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["escalation_package_id"] = str(uuid4())
        row.suggested_actions_json = json.dumps([action])
        session.commit()
        session.close()

        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="consumption_preflight_decision_binding_mismatch",
        )

    def test_decision_action_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(
            SessionLocal, decision_action="APPROVE_CONTINUE"
        )

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        # Change to a different valid action and update eligibility
        action["decision_action"] = "REQUEST_REWORK"
        action["continuation_eligible"] = False
        action["rework_eligible"] = True
        action["rejection_terminal"] = False
        row.suggested_actions_json = json.dumps([action])
        session.commit()
        session.close()

        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="consumption_preflight_decision_binding_mismatch",
        )

    def test_created_timestamp_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["decision_created_at"] = (
            datetime.now(timezone.utc) - timedelta(hours=5)
        ).isoformat()
        row.suggested_actions_json = json.dumps([action])
        session.commit()
        session.close()

        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="consumption_preflight_decision_binding_mismatch",
        )

    def test_expires_timestamp_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["decision_expires_at"] = (
            datetime.now(timezone.utc) + timedelta(hours=99)
        ).isoformat()
        row.suggested_actions_json = json.dumps([action])
        session.commit()
        session.close()

        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="consumption_preflight_decision_binding_mismatch",
        )

    def test_eligibility_booleans_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(
            SessionLocal, decision_action="APPROVE_CONTINUE"
        )

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        # Flip continuation_eligible to False (should be True for APPROVE_CONTINUE)
        action["continuation_eligible"] = False
        row.suggested_actions_json = json.dumps([action])
        session.commit()
        session.close()

        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="source_preflight_domain_reconstruction_invalid",
        )

    def test_dual_decision_fingerprint_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["revalidated_decision_confirmation_fingerprint"] = "f" * 64
        row.suggested_actions_json = json.dumps([action])
        session.commit()
        session.close()

        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="source_preflight_domain_reconstruction_invalid",
        )


# ══════════════════════════════════════════════════════════════════════
# 4. TestD3D2Binding
# ══════════════════════════════════════════════════════════════════════


class TestD3D2Binding:
    """Tamper D3 preflight binding fields to trigger binding mismatch against D2."""

    def _assert_blocked(
        self,
        SessionLocal,
        *,
        preflight_msg_id: UUID,
        reason: str,
    ) -> None:
        svc, session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=preflight_msg_id,
        )
        assert result.result.consumption_status == "blocked"
        assert reason in result.result.blocked_reasons
        assert result.message is None
        session.close()

    def _seed_and_tamper(
        self, db_engine, *, field: str, value: Any
    ) -> tuple[Any, UUID]:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action[field] = value
        row.suggested_actions_json = json.dumps([action])
        session.commit()
        session.close()
        return SessionLocal, pf_msg_id

    def test_source_decision_message_id(self, db_engine) -> None:
        SessionLocal, pf_msg_id = self._seed_and_tamper(
            db_engine, field="source_decision_message_id", value=str(uuid4())
        )
        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="source_human_escalation_decision_message_missing",
        )

    def test_decision_id(self, db_engine) -> None:
        SessionLocal, pf_msg_id = self._seed_and_tamper(
            db_engine, field="decision_id", value=str(uuid4())
        )
        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="consumption_preflight_decision_binding_mismatch",
        )

    def test_source_package_message_id(self, db_engine) -> None:
        SessionLocal, pf_msg_id = self._seed_and_tamper(
            db_engine, field="source_package_message_id", value=str(uuid4())
        )
        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="consumption_preflight_decision_binding_mismatch",
        )

    def test_escalation_package_id(self, db_engine) -> None:
        SessionLocal, pf_msg_id = self._seed_and_tamper(
            db_engine, field="escalation_package_id", value=str(uuid4())
        )
        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="consumption_preflight_decision_binding_mismatch",
        )

    def test_decision_action(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(
            SessionLocal, decision_action="APPROVE_CONTINUE"
        )

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["decision_action"] = "REQUEST_REWORK"
        action["continuation_eligible"] = False
        action["rework_eligible"] = True
        action["rejection_terminal"] = False
        row.suggested_actions_json = json.dumps([action])
        session.commit()
        session.close()

        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="consumption_preflight_decision_binding_mismatch",
        )

    def test_decision_created_at(self, db_engine) -> None:
        SessionLocal, pf_msg_id = self._seed_and_tamper(
            db_engine,
            field="decision_created_at",
            value=(datetime.now(timezone.utc) - timedelta(hours=10)).isoformat(),
        )
        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="consumption_preflight_decision_binding_mismatch",
        )

    def test_decision_expires_at(self, db_engine) -> None:
        SessionLocal, pf_msg_id = self._seed_and_tamper(
            db_engine,
            field="decision_expires_at",
            value=(datetime.now(timezone.utc) + timedelta(hours=100)).isoformat(),
        )
        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="consumption_preflight_decision_binding_mismatch",
        )

    def test_decision_confirmation_fingerprint(self, db_engine) -> None:
        SessionLocal, pf_msg_id = self._seed_and_tamper(
            db_engine, field="decision_confirmation_fingerprint", value="e" * 64
        )
        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="source_preflight_domain_reconstruction_invalid",
        )

    def test_revalidated_decision_confirmation_fingerprint(self, db_engine) -> None:
        SessionLocal, pf_msg_id = self._seed_and_tamper(
            db_engine,
            field="revalidated_decision_confirmation_fingerprint",
            value="d" * 64,
        )
        self._assert_blocked(
            SessionLocal, preflight_msg_id=pf_msg_id,
            reason="source_preflight_domain_reconstruction_invalid",
        )


# ══════════════════════════════════════════════════════════════════════
# 5. TestLifecycleRecheck
# ══════════════════════════════════════════════════════════════════════


class TestLifecycleRecheck:
    def test_decision_expires_after_preflight(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        # Seed with a decision that expires quickly
        now = datetime.now(timezone.utc)
        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(
            SessionLocal,
            d2_expires_at=now + timedelta(seconds=2),
            d3_evaluated_at=now,
        )

        # Now consume with consumed_at past the expiry
        svc, svc_session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pf_msg_id,
            consumed_at=now + timedelta(hours=2),
        )
        assert result.result.consumption_status == "blocked"
        assert "human_escalation_decision_expired" in result.result.blocked_reasons
        assert result.message is None
        svc_session.close()

    def test_decision_revoked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, d2_msg_id, _pkg = _seed_full_chain(SessionLocal)

        # Get the decision_id from the D2 action
        session = SessionLocal()
        d2_row = session.get(ProjectDirectorMessageTable, d2_msg_id)
        d2_action = json.loads(d2_row.suggested_actions_json)[0]
        decision_id = UUID(d2_action["decision_id"])

        # Seed a revocation
        _seed_revocation_message(
            session, d2_msg_id=d2_msg_id, decision_id=decision_id
        )
        session.close()

        svc, svc_session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pf_msg_id,
        )
        assert result.result.consumption_status == "blocked"
        assert "human_escalation_decision_revoked" in result.result.blocked_reasons
        assert result.message is None
        svc_session.close()

    def test_decision_already_consumed(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, d2_msg_id, _pkg = _seed_full_chain(SessionLocal)

        # Get the decision_id from the D2 action
        session = SessionLocal()
        d2_row = session.get(ProjectDirectorMessageTable, d2_msg_id)
        d2_action = json.loads(d2_row.suggested_actions_json)[0]
        decision_id = UUID(d2_action["decision_id"])

        # Seed a prior consumption with matching decision_id
        _seed_prior_consumption_message(
            session, d2_msg_id=d2_msg_id, decision_id=decision_id
        )
        session.close()

        svc, svc_session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pf_msg_id,
        )
        assert result.result.consumption_status == "blocked"
        assert "prior_human_escalation_decision_consumption_record_invalid" in result.result.blocked_reasons
        assert result.message is None
        svc_session.close()

    def test_preflight_already_consumed(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        # Get the preflight_id from the D3 action
        session = SessionLocal()
        pf_row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        pf_action = json.loads(pf_row.suggested_actions_json)[0]
        preflight_id = UUID(pf_action["preflight_id"])

        # Seed a prior consumption with matching preflight_id
        _seed_prior_consumption_message(
            session, preflight_msg_id=pf_msg_id, preflight_id=preflight_id
        )
        session.close()

        svc, svc_session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pf_msg_id,
        )
        assert result.result.consumption_status == "blocked"
        assert "prior_human_escalation_decision_consumption_record_invalid" in result.result.blocked_reasons
        assert result.message is None
        svc_session.close()

    def test_multiple_ready_preflights(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, d2_msg_id, _pkg = _seed_full_chain(SessionLocal)

        # Get the decision_id from the D2 action
        session = SessionLocal()
        d2_row = session.get(ProjectDirectorMessageTable, d2_msg_id)
        d2_action = json.loads(d2_row.suggested_actions_json)[0]
        decision_id = UUID(d2_action["decision_id"])

        # Seed an extra preflight with matching decision
        _seed_prior_preflight_message(
            session, d2_msg_id=d2_msg_id, decision_id=decision_id
        )
        session.close()

        svc, svc_session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pf_msg_id,
        )
        assert result.result.consumption_status == "blocked"
        assert "human_escalation_decision_multiple_ready_preflights_detected" in result.result.blocked_reasons
        assert result.message is None
        svc_session.close()


# ══════════════════════════════════════════════════════════════════════
# 6. TestFingerprintIsolation
# ══════════════════════════════════════════════════════════════════════


class TestFingerprintIsolation:
    def test_consumed_result_fingerprint_fields(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        svc, svc_session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pf_msg_id,
        )
        assert result.result.consumption_status == "consumed"

        # Consumption fingerprint is non-empty SHA-256
        fp = result.result.consumption_evidence_fingerprint
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)

        # Decision confirmation fingerprint
        dcfp = result.result.decision_confirmation_fingerprint
        assert len(dcfp) == 64
        assert dcfp == result.result.revalidated_decision_confirmation_fingerprint

        # Aggregate evidence fingerprint
        afp = result.result.aggregate_evidence_fingerprint
        assert len(afp) == 64

        svc_session.close()

    def test_all_id_fields_populated(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        svc, svc_session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pf_msg_id,
        )
        assert result.result.consumption_status == "consumed"
        r = result.result
        assert r.consumption_id is not None
        assert r.preflight_id is not None
        assert r.source_decision_message_id is not None
        assert r.decision_id is not None
        assert r.source_package_message_id is not None
        assert r.escalation_package_id is not None
        svc_session.close()

    def test_all_timestamps_populated(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        svc, svc_session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pf_msg_id,
        )
        assert result.result.consumption_status == "consumed"
        r = result.result
        assert r.decision_created_at is not None
        assert r.decision_created_at.tzinfo is not None
        assert r.decision_expires_at is not None
        assert r.decision_expires_at.tzinfo is not None
        assert r.preflight_evaluated_at is not None
        assert r.preflight_evaluated_at.tzinfo is not None
        assert r.consumed_at is not None
        assert r.consumed_at.tzinfo is not None
        svc_session.close()

    def test_transition_and_eligibility_fields(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(
            SessionLocal, decision_action="APPROVE_CONTINUE"
        )

        svc, svc_session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pf_msg_id,
        )
        assert result.result.consumption_status == "consumed"
        r = result.result
        assert r.transition_kind == "CONTINUE_GUARDRAIL"
        assert r.continuation_guardrail_eligible is True
        assert r.bounded_rework_guardrail_eligible is False
        assert r.terminal_rejection is False
        assert r.gate_allows_protected_transition_guardrail is True
        svc_session.close()

    def test_stored_fingerprint_tampered_blocks_future_e(self, db_engine) -> None:
        """Tamper the D2 decision fingerprint and verify D4 blocks."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, d2_msg_id, _pkg = _seed_full_chain(SessionLocal)

        # Tamper D2 decision fingerprint
        session = SessionLocal()
        d2_row = session.get(ProjectDirectorMessageTable, d2_msg_id)
        d2_action = json.loads(d2_row.suggested_actions_json)[0]
        d2_action["decision_confirmation_fingerprint"] = "ff" * 32
        d2_row.suggested_actions_json = json.dumps([d2_action])
        session.commit()
        session.close()

        svc, svc_session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pf_msg_id,
        )
        assert result.result.consumption_status == "blocked"
        assert result.message is None
        svc_session.close()


# ══════════════════════════════════════════════════════════════════════
# 7. TestReplayAndPagination
# ══════════════════════════════════════════════════════════════════════


class TestReplayAndPagination:
    def test_filler_messages_between_chain_and_consume(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        # Get the highest seq_no
        session = SessionLocal()
        pf_row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        last_seq = pf_row.sequence_no

        # Insert 105 filler messages
        _seed_filler_messages(session, last_seq + 1, 105)
        session.close()

        svc, svc_session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pf_msg_id,
        )
        assert result.result.consumption_status == "consumed"
        assert result.message is not None
        svc_session.close()

    def test_cross_page_revocation_detected(self, db_engine) -> None:
        """Revocation message is beyond the first 100-message page."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, d2_msg_id, _pkg = _seed_full_chain(SessionLocal)

        # Get the preflight action to extract decision_id
        session = SessionLocal()
        pf_row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        pf_action = json.loads(pf_row.suggested_actions_json)[0]
        last_seq = pf_row.sequence_no
        d2_row = session.get(ProjectDirectorMessageTable, d2_msg_id)
        d2_action = json.loads(d2_row.suggested_actions_json)[0]
        decision_id = UUID(d2_action["decision_id"])

        # Insert fillers so revocation is on a later page
        _seed_filler_messages(session, last_seq + 1, 105)
        filler_last_seq = last_seq + 105

        # Seed revocation after fillers
        _seed_revocation_message(
            session,
            d2_msg_id=d2_msg_id,
            decision_id=decision_id,
            seq_no=filler_last_seq + 1,
        )
        session.close()

        svc, svc_session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pf_msg_id,
        )
        assert result.result.consumption_status == "blocked"
        assert "human_escalation_decision_revoked" in result.result.blocked_reasons
        svc_session.close()

    def test_cross_page_prior_consumption_detected(self, db_engine) -> None:
        """Prior consumption message is beyond the first 100-message page."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, d2_msg_id, _pkg = _seed_full_chain(SessionLocal)

        session = SessionLocal()
        pf_row = session.get(ProjectDirectorMessageTable, pf_msg_id)
        last_seq = pf_row.sequence_no
        d2_row = session.get(ProjectDirectorMessageTable, d2_msg_id)
        d2_action = json.loads(d2_row.suggested_actions_json)[0]
        decision_id = UUID(d2_action["decision_id"])

        # Insert fillers
        _seed_filler_messages(session, last_seq + 1, 105)
        filler_last_seq = last_seq + 105

        # Seed prior consumption after fillers
        _seed_prior_consumption_message(
            session,
            d2_msg_id=d2_msg_id,
            decision_id=decision_id,
            seq_no=filler_last_seq + 1,
        )
        session.close()

        svc, svc_session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pf_msg_id,
        )
        assert result.result.consumption_status == "blocked"
        assert "prior_human_escalation_decision_consumption_record_invalid" in result.result.blocked_reasons
        svc_session.close()


# ══════════════════════════════════════════════════════════════════════
# 8. TestConcurrency
# ══════════════════════════════════════════════════════════════════════


class HoldingImmediateTransactionRepository(ProjectDirectorMessageRepository):
    """Test-only repo: acquires BEGIN IMMEDIATE then holds until released."""

    def __init__(self, session, writer_lock_acquired, release_writer):
        super().__init__(session)
        self._writer_lock_acquired = writer_lock_acquired
        self._release_writer = release_writer

    @contextmanager
    def sqlite_immediate_transaction(self):
        with super().sqlite_immediate_transaction():
            self._writer_lock_acquired.set()
            if not self._release_writer.wait(timeout=10):
                raise TimeoutError("writer release timeout")
            yield


class AttemptSignalingRepository(ProjectDirectorMessageRepository):
    """Test-only repo: signals before and after entering BEGIN IMMEDIATE."""

    def __init__(self, session, second_writer_attempted, second_writer_entered):
        super().__init__(session)
        self._second_writer_attempted = second_writer_attempted
        self._second_writer_entered = second_writer_entered

    @contextmanager
    def sqlite_immediate_transaction(self):
        self._second_writer_attempted.set()
        with super().sqlite_immediate_transaction():
            self._second_writer_entered.set()
            yield


class TestConcurrency:
    def test_two_threads_one_consumed_one_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        writer_lock_acquired = threading.Event()
        release_writer = threading.Event()
        second_writer_attempted = threading.Event()
        second_writer_entered = threading.Event()

        results = []
        errors = []

        def worker_a():
            try:
                sess = SessionLocal()
                msg_repo = HoldingImmediateTransactionRepository(
                    sess, writer_lock_acquired, release_writer
                )
                sess_repo = ProjectDirectorSessionRepository(sess)
                task_repo = TaskRepository(sess)
                svc = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionService(
                    session_repository=sess_repo,
                    message_repository=msg_repo,
                    task_repository=task_repo,
                )
                result = svc.consume_human_escalation_decision(
                    session_id=SESSION_ID,
                    source_task_id=TASK_ID,
                    source_message_id=pf_msg_id,
                )
                results.append(result)
            except Exception as e:
                errors.append(f"thread-a:{type(e).__name__}:{e}")
            finally:
                sess.close()

        def worker_b():
            try:
                sess = SessionLocal()
                msg_repo = AttemptSignalingRepository(
                    sess, second_writer_attempted, second_writer_entered
                )
                sess_repo = ProjectDirectorSessionRepository(sess)
                task_repo = TaskRepository(sess)
                svc = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionService(
                    session_repository=sess_repo,
                    message_repository=msg_repo,
                    task_repository=task_repo,
                )
                result = svc.consume_human_escalation_decision(
                    session_id=SESSION_ID,
                    source_task_id=TASK_ID,
                    source_message_id=pf_msg_id,
                )
                results.append(result)
            except Exception as e:
                errors.append(f"thread-b:{type(e).__name__}:{e}")
            finally:
                sess.close()

        t_a = threading.Thread(target=worker_a)
        t_a.start()

        if not writer_lock_acquired.wait(timeout=30):
            raise TimeoutError("thread A did not acquire writer lock")

        t_b = threading.Thread(target=worker_b)
        t_b.start()

        if not second_writer_attempted.wait(timeout=30):
            raise TimeoutError("thread B did not attempt writer lock")

        assert not second_writer_entered.wait(timeout=0.25), (
            "thread B entered SQLite immediate transaction while A still holds lock"
        )

        release_writer.set()

        t_a.join(timeout=30)
        t_b.join(timeout=30)

        assert second_writer_entered.wait(timeout=0), (
            "thread B never entered SQLite immediate transaction after A released"
        )
        assert not t_a.is_alive(), "thread A did not finish"
        assert not t_b.is_alive(), "thread B did not finish"
        assert len(errors) == 0, f"Unexpected errors: {errors}"
        assert len(results) == 2

        statuses = [r.result.consumption_status for r in results]
        assert statuses.count("consumed") == 1
        assert statuses.count("blocked") == 1

        consumed_result = next(r for r in results if r.result.consumption_status == "consumed")
        blocked_result = next(r for r in results if r.result.consumption_status == "blocked")
        assert consumed_result.message is not None
        assert blocked_result.message is None
        assert "human_escalation_decision_already_consumed" in blocked_result.result.blocked_reasons or \
               "human_escalation_decision_preflight_already_consumed" in blocked_result.result.blocked_reasons

        verify = SessionLocal()
        count = verify.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd"
            ),
            {"sd": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_SOURCE_DETAIL},
        ).scalar()
        assert count == 1
        verify.close()


class TestBarrierContention:
    def test_barrier_two_threads_one_consumed_one_blocked(self, tmp_path) -> None:
        db_path = str(tmp_path / "barrier.db")
        engine = _make_test_engine(db_path)
        SessionLocal = _make_session_factory(engine)

        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        barrier = threading.Barrier(2, timeout=30)
        results = []
        errors = []

        def worker(worker_id: int):
            try:
                sess = SessionLocal()
                msg_repo = ProjectDirectorMessageRepository(sess)
                sess_repo = ProjectDirectorSessionRepository(sess)
                task_repo = TaskRepository(sess)
                svc = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionService(
                    session_repository=sess_repo,
                    message_repository=msg_repo,
                    task_repository=task_repo,
                )
                barrier.wait()
                result = svc.consume_human_escalation_decision(
                    session_id=SESSION_ID,
                    source_task_id=TASK_ID,
                    source_message_id=pf_msg_id,
                )
                results.append((worker_id, result))
                sess.close()
            except Exception as e:
                errors.append(f"worker-{worker_id}:{type(e).__name__}:{e}")

        t1 = threading.Thread(target=worker, args=(1,))
        t2 = threading.Thread(target=worker, args=(2,))
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        assert not t1.is_alive(), "thread 1 did not finish"
        assert not t2.is_alive(), "thread 2 did not finish"
        assert len(errors) == 0, f"Unexpected errors: {errors}"
        assert len(results) == 2

        statuses = [r.result.consumption_status for _, r in results]
        assert statuses.count("consumed") == 1
        assert statuses.count("blocked") == 1

        consumed = next(r for _, r in results if r.result.consumption_status == "consumed")
        blocked = next(r for _, r in results if r.result.consumption_status == "blocked")
        assert consumed.message is not None
        assert blocked.message is None

        verify = SessionLocal()
        count = verify.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd"
            ),
            {"sd": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_SOURCE_DETAIL},
        ).scalar()
        assert count == 1
        verify.close()
        engine.dispose()


# ══════════════════════════════════════════════════════════════════════
# 9. TestAppendOnly
# ══════════════════════════════════════════════════════════════════════


class TestAppendOnly:
    def test_no_new_tasks(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        pre = SessionLocal()
        task_count_before = pre.execute(text("SELECT COUNT(*) FROM tasks")).scalar()
        pre.close()

        svc, svc_session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pf_msg_id,
        )
        assert result.result.consumption_status == "consumed"
        svc_session.close()

        post = SessionLocal()
        task_count_after = post.execute(text("SELECT COUNT(*) FROM tasks")).scalar()
        assert task_count_after == task_count_before
        post.close()

    def test_no_new_runs(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        svc, svc_session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pf_msg_id,
        )
        assert result.result.consumption_status == "consumed"
        svc_session.close()

        post = SessionLocal()
        run_count = post.execute(text("SELECT COUNT(*) FROM runs")).scalar()
        assert run_count == 0
        post.close()

    def test_no_workers(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        svc, svc_session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pf_msg_id,
        )
        assert result.result.consumption_status == "consumed"
        svc_session.close()

        # workers table may not exist in test DB; verify via result flags
        assert result.result.worker_started is False
        assert result.result.worktree_created is False

    def test_source_messages_unchanged(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, d2_msg_id, _pkg = _seed_full_chain(SessionLocal)

        # Snapshot source messages
        session = SessionLocal()
        pf_snapshot = session.get(ProjectDirectorMessageTable, pf_msg_id).suggested_actions_json
        d2_snapshot = session.get(ProjectDirectorMessageTable, d2_msg_id).suggested_actions_json
        session.close()

        svc, svc_session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pf_msg_id,
        )
        assert result.result.consumption_status == "consumed"
        svc_session.close()

        # Verify source messages unchanged
        verify = SessionLocal()
        pf_after = verify.get(ProjectDirectorMessageTable, pf_msg_id).suggested_actions_json
        d2_after = verify.get(ProjectDirectorMessageTable, d2_msg_id).suggested_actions_json
        assert pf_after == pf_snapshot
        assert d2_after == d2_snapshot
        verify.close()

    def test_no_side_effect_flags_on_consumed_result(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        svc, svc_session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pf_msg_id,
        )
        r = result.result
        assert r.consumption_status == "consumed"
        assert r.continuation_started is False
        assert r.rework_started is False
        assert r.approval_request_created is False
        assert r.legacy_approval_decision_created is False
        assert r.main_project_file_written is False
        assert r.sandbox_file_written is False
        assert r.manifest_file_written is False
        assert r.diff_file_written is False
        assert r.patch_applied is False
        assert r.git_write_performed is False
        assert r.worktree_created is False
        assert r.worker_started is False
        assert r.task_created is False
        assert r.run_created is False
        assert r.gate_allows_write is False
        assert r.ai_project_director_total_loop == "Partial"
        svc_session.close()

    def test_consumption_message_action_fields(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        svc, svc_session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pf_msg_id,
        )
        assert result.result.consumption_status == "consumed"
        assert result.message is not None

        msg = result.message
        assert msg.session_id == SESSION_ID
        assert msg.role == ProjectDirectorMessageRole.ASSISTANT
        assert msg.source == ProjectDirectorMessageSource.SYSTEM
        assert msg.requires_confirmation is False
        assert msg.risk_level == ProjectDirectorMessageRiskLevel.HIGH
        assert msg.related_project_id == PROJECT_ID
        assert msg.related_task_id == TASK_ID
        assert msg.intent == "sandbox_candidate_diff_review_human_escalation_decision_consumption"
        assert msg.source_detail == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_SOURCE_DETAIL

        assert len(msg.suggested_actions) == 1
        action = msg.suggested_actions[0]
        assert action["type"] == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_ACTION_TYPE
        assert action["schema_version"] == HUMAN_ESCALATION_DECISION_CONSUMPTION_SCHEMA_VERSION
        assert action["session_id"] == str(SESSION_ID)
        assert action["source_task_id"] == str(TASK_ID)
        assert action["consumption_status"] == "consumed"

        svc_session.close()

    def test_db_persistence(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _pf, pf_msg_id, _d2, _pkg = _seed_full_chain(SessionLocal)

        svc, svc_session = _make_d4_service(SessionLocal)
        result = svc.consume_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pf_msg_id,
        )
        assert result.result.consumption_status == "consumed"
        assert result.message is not None
        msg_id = result.message.id
        svc_session.close()

        verify = SessionLocal()
        row = verify.get(ProjectDirectorMessageTable, msg_id)
        assert row is not None
        assert row.role == "assistant"
        assert row.source == "system"
        assert row.requires_confirmation is False
        assert row.risk_level == "high"
        assert row.source_detail == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_SOURCE_DETAIL
        assert row.intent == "sandbox_candidate_diff_review_human_escalation_decision_consumption"

        actions = json.loads(row.suggested_actions_json)
        assert len(actions) == 1
        act = actions[0]
        assert act["type"] == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_ACTION_TYPE
        assert act["schema_version"] == HUMAN_ESCALATION_DECISION_CONSUMPTION_SCHEMA_VERSION
        assert act["consumption_status"] == "consumed"

        count = verify.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd"
            ),
            {"sd": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_SOURCE_DETAIL},
        ).scalar()
        assert count == 1
        verify.close()
