"""Contract tests for P21-D-D2 human escalation decision recorder."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
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
from app.domain.project_director_sandbox_candidate_diff_review_human_escalation_decision import (
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_sandbox_candidate_diff_review_human_escalation_decision_service import (
    HUMAN_ESCALATION_DECISION_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionService,
)
from app.services.project_director_sandbox_candidate_diff_review_human_escalation_package_service import (
    HUMAN_ESCALATION_PACKAGE_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_SOURCE_DETAIL,
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
    _seed_filler_messages,
)


# ── D2 false-only side-effect flags ────────────────────────────────

_D2_FALSE_ONLY_FLAGS = [
    "decision_consumption_started",
    "decision_consumed",
    "decision_revoked",
    "decision_expired",
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
]

_D2_PACKAGE_FALSE_FLAGS = [
    "continuation_started",
    "rework_started",
    "human_decision_recorded",
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
]


# ── Helpers ─────────────────────────────────────────────────────────


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


def _valid_recorded_kwargs(**overrides: Any) -> dict[str, Any]:
    sha = hashlib.sha256(b"valid").hexdigest()
    now = datetime.now(timezone.utc)
    kwargs: dict[str, Any] = dict(
        decision_status="recorded",
        decision_id=uuid4(),
        source_package_message_id=uuid4(),
        escalation_package_id=uuid4(),
        source_disposition_message_id=uuid4(),
        source_review_message_id=uuid4(),
        source_preflight_message_id=uuid4(),
        source_diff_message_id=uuid4(),
        disposition_id=uuid4(),
        aggregate_evidence_fingerprint=sha,
        decision_scope="resolve_single_source_review_escalation",
        decision_action="APPROVE_CONTINUE",
        actor_type="human",
        actor="human-reviewer",
        client_request_id="req-123",
        decision_created_at=now,
        decision_expires_at=now.replace(year=2099),
        decision_confirmation_fingerprint=sha,
        source_package_validated=True,
        aggregate_evidence_fingerprint_revalidated=True,
        replay_check_completed=True,
        prior_decision_detected=False,
        human_escalation_package_created=True,
        human_decision_recorded=True,
    )
    kwargs.update(overrides)
    return kwargs


def _seed_full_d1_d2(
    SessionLocal,
    *,
    decision_action="APPROVE_CONTINUE",
    actor="human-reviewer",
    client_request_id=None,
    decision_expires_at=None,
):
    """Seed base records, review, disposition, D1 package, then call D2."""
    session = SessionLocal()
    _seed_base_records(session)
    _seed_review_message(session)
    _seed_disposition_message(session)
    session.close()

    pkg_msg_id, pkg_seq_no = _d1_prepare(SessionLocal)

    if client_request_id is None:
        client_request_id = f"req-{uuid4()}"
    if decision_expires_at is None:
        decision_expires_at = datetime.now(timezone.utc).replace(year=2099)

    svc, sess = _make_d2_service(SessionLocal)
    result = svc.record_human_escalation_decision(
        session_id=SESSION_ID,
        source_task_id=TASK_ID,
        source_message_id=pkg_msg_id,
        decision_action=decision_action,
        actor=actor,
        client_request_id=client_request_id,
        decision_expires_at=decision_expires_at,
    )
    sess.close()
    return result, pkg_msg_id


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def db_engine(tmp_path):
    db_path = str(tmp_path / "test.db")
    engine = _make_test_engine(db_path)
    yield engine
    engine.dispose()


@pytest.fixture()
def seeded_session_local(db_engine):
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
    def test_source_detail(self) -> None:
        assert (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_SOURCE_DETAIL
            == "p21_d_sandbox_candidate_diff_review_human_escalation_decision_recorded"
        )

    def test_action_type(self) -> None:
        assert (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_ACTION_TYPE
            == "p21_d_sandbox_candidate_diff_review_human_escalation_decision_record"
        )

    def test_schema_version(self) -> None:
        assert HUMAN_ESCALATION_DECISION_SCHEMA_VERSION == "p21-d-d2.v1"

    def test_d1_source_detail_imported(self) -> None:
        assert (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_SOURCE_DETAIL
            == "p21_d_sandbox_candidate_diff_review_human_escalation_package_prepared"
        )

    def test_d1_action_type_imported(self) -> None:
        assert (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_ACTION_TYPE
            == "p21_d_sandbox_candidate_diff_review_human_escalation_package_record"
        )

    def test_d1_schema_version_imported(self) -> None:
        assert HUMAN_ESCALATION_PACKAGE_SCHEMA_VERSION == "p21-d-d1.v1"


# ══════════════════════════════════════════════════════════════════════
# 2. TestDomainBlockedContract
# ══════════════════════════════════════════════════════════════════════


class TestDomainBlockedContract:
    def test_blocked_requires_reasons(self) -> None:
        with pytest.raises(ValueError, match="blocked human escalation decision requires a reason"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(
                decision_status="blocked",
                source_package_message_id=uuid4(),
                blocked_reasons=[],
            )

    def test_blocked_no_decision_id(self) -> None:
        with pytest.raises(
            ValueError,
            match="blocked human escalation decision may not be created",
        ):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(
                decision_status="blocked",
                source_package_message_id=uuid4(),
                decision_id=uuid4(),
                blocked_reasons=["some_reason"],
            )

    def test_blocked_no_confirmation_fingerprint(self) -> None:
        with pytest.raises(
            ValueError,
            match="blocked decision may not expose a confirmation fingerprint",
        ):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(
                decision_status="blocked",
                source_package_message_id=uuid4(),
                decision_confirmation_fingerprint="a" * 64,
                blocked_reasons=["some_reason"],
            )

    def test_blocked_no_human_decision_recorded(self) -> None:
        with pytest.raises(
            ValueError,
            match="blocked decision may not report a human decision",
        ):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(
                decision_status="blocked",
                source_package_message_id=uuid4(),
                human_decision_recorded=True,
                blocked_reasons=["some_reason"],
            )

    def test_blocked_valid(self) -> None:
        result = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(
            decision_status="blocked",
            source_package_message_id=uuid4(),
            blocked_reasons=["session_missing"],
        )
        assert result.decision_status == "blocked"
        assert result.blocked_reasons == ["session_missing"]
        assert result.decision_id is None
        assert result.decision_confirmation_fingerprint == ""
        assert result.human_decision_recorded is False


# ══════════════════════════════════════════════════════════════════════
# 3. TestDomainPreparedContract
# ══════════════════════════════════════════════════════════════════════


class TestDomainPreparedContract:
    def test_valid_recorded(self) -> None:
        result = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(
            **_valid_recorded_kwargs()
        )
        assert result.decision_status == "recorded"
        assert result.decision_scope == "resolve_single_source_review_escalation"
        assert result.decision_action == "APPROVE_CONTINUE"
        assert result.actor_type == "human"
        assert result.human_decision_recorded is True
        assert result.human_escalation_package_created is True

    def test_requires_decision_id(self) -> None:
        kwargs = _valid_recorded_kwargs(decision_id=None)
        with pytest.raises(ValueError, match="recorded decision requires exact decision and package identity"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(**kwargs)

    def test_requires_escalation_package_id(self) -> None:
        kwargs = _valid_recorded_kwargs(escalation_package_id=None)
        with pytest.raises(ValueError, match="recorded decision requires exact decision and package identity"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(**kwargs)

    def test_requires_source_ids(self) -> None:
        for field in [
            "source_disposition_message_id",
            "source_review_message_id",
            "source_preflight_message_id",
            "source_diff_message_id",
            "disposition_id",
        ]:
            kwargs = _valid_recorded_kwargs(**{field: None})
            with pytest.raises(ValueError, match="recorded decision requires all exact source identifiers"):
                ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(**kwargs)

    def test_requires_aggregate_fingerprint(self) -> None:
        kwargs = _valid_recorded_kwargs(aggregate_evidence_fingerprint="invalid")
        with pytest.raises(ValueError, match="recorded decision requires aggregate evidence fingerprint"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(**kwargs)

    def test_requires_decision_scope(self) -> None:
        kwargs = _valid_recorded_kwargs(decision_scope=None)
        with pytest.raises(ValueError, match="recorded decision requires the bounded decision scope"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(**kwargs)

    def test_requires_decision_action(self) -> None:
        kwargs = _valid_recorded_kwargs(decision_action=None)
        with pytest.raises(ValueError, match="recorded decision action is invalid"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(**kwargs)

    def test_requires_actor_type_human(self) -> None:
        kwargs = _valid_recorded_kwargs(actor_type="system")
        with pytest.raises(Exception):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(**kwargs)

    def test_requires_actor_non_empty(self) -> None:
        kwargs = _valid_recorded_kwargs(actor="")
        with pytest.raises(ValueError, match="recorded decision requires normalized human identity"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(**kwargs)

    def test_requires_client_request_id_non_empty(self) -> None:
        kwargs = _valid_recorded_kwargs(client_request_id="")
        with pytest.raises(ValueError, match="recorded decision requires normalized human identity"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(**kwargs)

    def test_requires_timestamps(self) -> None:
        kwargs = _valid_recorded_kwargs(decision_created_at=None)
        with pytest.raises(ValueError, match="recorded decision requires created and expiry timestamps"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(**kwargs)

        kwargs = _valid_recorded_kwargs(decision_expires_at=None)
        with pytest.raises(ValueError, match="recorded decision requires created and expiry timestamps"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(**kwargs)

    def test_requires_expires_after_created(self) -> None:
        now = datetime.now(timezone.utc)
        kwargs = _valid_recorded_kwargs(
            decision_created_at=now,
            decision_expires_at=now,
        )
        with pytest.raises(ValueError, match="decision_expires_at must be later than decision_created_at"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(**kwargs)

    def test_requires_confirmation_fingerprint(self) -> None:
        kwargs = _valid_recorded_kwargs(decision_confirmation_fingerprint="invalid")
        with pytest.raises(ValueError, match="recorded decision requires confirmation fingerprint"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(**kwargs)

    def test_requires_source_package_validated(self) -> None:
        kwargs = _valid_recorded_kwargs(source_package_validated=False)
        with pytest.raises(ValueError, match="recorded decision requires a validated D1 package"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(**kwargs)

    def test_requires_replay_check_completed(self) -> None:
        kwargs = _valid_recorded_kwargs(replay_check_completed=False)
        with pytest.raises(ValueError, match="recorded decision requires a clean replay check"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(**kwargs)

    def test_rejects_prior_decision_detected(self) -> None:
        kwargs = _valid_recorded_kwargs(prior_decision_detected=True)
        with pytest.raises(ValueError, match="recorded decision requires a clean replay check"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(**kwargs)

    def test_requires_human_decision_recorded(self) -> None:
        kwargs = _valid_recorded_kwargs(human_decision_recorded=False)
        with pytest.raises(ValueError, match="recorded decision requires package and decision state"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(**kwargs)

    def test_requires_human_escalation_package_created(self) -> None:
        kwargs = _valid_recorded_kwargs(human_escalation_package_created=False)
        with pytest.raises(ValueError, match="recorded decision requires package and decision state"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(**kwargs)

    def test_rejects_blocked_reasons(self) -> None:
        kwargs = _valid_recorded_kwargs(blocked_reasons=["stale"])
        with pytest.raises(ValueError, match="recorded decision may not contain blocked reasons"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(**kwargs)


# ══════════════════════════════════════════════════════════════════════
# 4. TestFalseOnlyFlags
# ══════════════════════════════════════════════════════════════════════


class TestFalseOnlyFlags:
    @pytest.mark.parametrize("flag", _D2_FALSE_ONLY_FLAGS)
    def test_forbidden_side_effect_flag_rejected(self, flag: str) -> None:
        kwargs = _valid_recorded_kwargs(**{flag: True})
        with pytest.raises(ValueError, match="human escalation decision may not"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(**kwargs)

    def test_exactly_19_false_only_fields(self) -> None:
        assert len(_D2_FALSE_ONLY_FLAGS) == 19

    def test_total_loop_must_be_partial(self) -> None:
        kwargs = _valid_recorded_kwargs(ai_project_director_total_loop="Full")
        with pytest.raises(ValueError):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(**kwargs)


# ══════════════════════════════════════════════════════════════════════
# 5. TestSuccessPath
# ══════════════════════════════════════════════════════════════════════


class TestSuccessPath:
    def _verify_recorded_result(self, result, *, expected_action: str) -> None:
        r = result.result
        msg = result.message

        assert r.decision_status == "recorded"
        assert r.actor_type == "human"
        assert r.decision_action == expected_action
        assert r.decision_scope == "resolve_single_source_review_escalation"
        assert r.source_package_validated is True
        assert r.aggregate_evidence_fingerprint_revalidated is True
        assert r.replay_check_completed is True
        assert r.prior_decision_detected is False
        assert r.human_escalation_package_created is True
        assert r.human_decision_recorded is True
        assert r.blocked_reasons == []
        assert r.decision_id is not None
        assert r.escalation_package_id is not None
        assert r.decision_created_at is not None
        assert r.decision_created_at.tzinfo is not None
        assert r.decision_expires_at is not None
        assert r.decision_expires_at > r.decision_created_at
        assert len(r.aggregate_evidence_fingerprint) == 64
        assert len(r.decision_confirmation_fingerprint) == 64

        assert msg is not None
        assert msg.session_id == SESSION_ID
        assert msg.role == ProjectDirectorMessageRole.USER
        assert msg.source == ProjectDirectorMessageSource.SYSTEM
        assert msg.requires_confirmation is False
        assert msg.risk_level == ProjectDirectorMessageRiskLevel.HIGH
        assert msg.related_project_id == PROJECT_ID
        assert msg.related_task_id == TASK_ID
        assert msg.intent == "sandbox_candidate_diff_review_human_escalation_decision"
        assert msg.source_detail == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_SOURCE_DETAIL
        assert len(msg.suggested_actions) == 1
        assert msg.created_at.tzinfo is not None

        content_lower = msg.content.lower()
        assert "recorded" in content_lower
        assert "human" in content_lower
        assert "total loop remains partial" in content_lower
        assert "no raw" in content_lower or "raw" not in content_lower or "no_raw" in str(msg.forbidden_actions_detected)

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
            "no_raw_human_confirmation_text",
        ]:
            assert required in forbidden

        action = msg.suggested_actions[0]
        assert action["type"] == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_ACTION_TYPE
        assert action["schema_version"] == HUMAN_ESCALATION_DECISION_SCHEMA_VERSION
        assert action["decision_status"] == "recorded"
        assert action["decision_action"] == expected_action
        assert action["actor_type"] == "human"
        assert action["session_id"] == str(SESSION_ID)
        assert action["source_task_id"] == str(TASK_ID)

        for flag in _D2_FALSE_ONLY_FLAGS:
            assert action.get(flag) is False, f"{flag} should be False"
        assert action["ai_project_director_total_loop"] == "Partial"
        assert action["gate_allows_write"] is False

    def test_approve_continue_success(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        result, pkg_msg_id = _seed_full_d1_d2(
            SessionLocal,
            decision_action="APPROVE_CONTINUE",
        )
        self._verify_recorded_result(result, expected_action="APPROVE_CONTINUE")

    def test_request_rework_success(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        result, pkg_msg_id = _seed_full_d1_d2(
            SessionLocal,
            decision_action="REQUEST_REWORK",
        )
        self._verify_recorded_result(result, expected_action="REQUEST_REWORK")

    def test_reject_success(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        result, pkg_msg_id = _seed_full_d1_d2(
            SessionLocal,
            decision_action="REJECT",
        )
        self._verify_recorded_result(result, expected_action="REJECT")


# ══════════════════════════════════════════════════════════════════════
# 6. TestInputNormalization
# ══════════════════════════════════════════════════════════════════════


class TestInputNormalization:
    def test_actor_whitespace_stripped(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        result, _ = _seed_full_d1_d2(
            SessionLocal,
            actor="  human-reviewer  ",
        )
        assert result.result.decision_status == "recorded"
        assert result.result.actor == "human-reviewer"

    def test_client_request_id_whitespace_stripped(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        result, _ = _seed_full_d1_d2(
            SessionLocal,
            client_request_id="  req-abc  ",
        )
        assert result.result.decision_status == "recorded"
        assert result.result.client_request_id == "req-abc"

    def test_actor_empty_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        pkg_msg_id, _ = _d1_prepare(SessionLocal)
        svc, sess = _make_d2_service(SessionLocal)
        result = svc.record_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pkg_msg_id,
            decision_action="APPROVE_CONTINUE",
            actor="",
            client_request_id="req-1",
            decision_expires_at=datetime.now(timezone.utc).replace(year=2099),
        )
        assert result.result.decision_status == "blocked"
        assert "human_escalation_decision_actor_invalid" in result.result.blocked_reasons
        sess.close()

    def test_client_request_id_empty_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        pkg_msg_id, _ = _d1_prepare(SessionLocal)
        svc, sess = _make_d2_service(SessionLocal)
        result = svc.record_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pkg_msg_id,
            decision_action="APPROVE_CONTINUE",
            actor="reviewer",
            client_request_id="",
            decision_expires_at=datetime.now(timezone.utc).replace(year=2099),
        )
        assert result.result.decision_status == "blocked"
        assert "human_decision_client_request_id_invalid" in result.result.blocked_reasons
        sess.close()

    def test_actor_too_long_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        pkg_msg_id, _ = _d1_prepare(SessionLocal)
        svc, sess = _make_d2_service(SessionLocal)
        result = svc.record_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pkg_msg_id,
            decision_action="APPROVE_CONTINUE",
            actor="x" * 201,
            client_request_id="req-1",
            decision_expires_at=datetime.now(timezone.utc).replace(year=2099),
        )
        assert result.result.decision_status == "blocked"
        assert "human_escalation_decision_actor_invalid" in result.result.blocked_reasons
        sess.close()

    def test_client_request_id_too_long_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        pkg_msg_id, _ = _d1_prepare(SessionLocal)
        svc, sess = _make_d2_service(SessionLocal)
        result = svc.record_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pkg_msg_id,
            decision_action="APPROVE_CONTINUE",
            actor="reviewer",
            client_request_id="x" * 201,
            decision_expires_at=datetime.now(timezone.utc).replace(year=2099),
        )
        assert result.result.decision_status == "blocked"
        assert "human_decision_client_request_id_invalid" in result.result.blocked_reasons
        sess.close()

    def test_decision_expires_at_naive_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        pkg_msg_id, _ = _d1_prepare(SessionLocal)
        svc, sess = _make_d2_service(SessionLocal)
        result = svc.record_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pkg_msg_id,
            decision_action="APPROVE_CONTINUE",
            actor="reviewer",
            client_request_id="req-1",
            decision_expires_at=datetime(2099, 1, 1),
        )
        assert result.result.decision_status == "blocked"
        assert "human_escalation_decision_expiry_invalid" in result.result.blocked_reasons
        sess.close()

    def test_decision_expires_at_before_created_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        pkg_msg_id, _ = _d1_prepare(SessionLocal)
        svc, sess = _make_d2_service(SessionLocal)
        past = datetime(2020, 1, 1, tzinfo=timezone.utc)
        result = svc.record_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pkg_msg_id,
            decision_action="APPROVE_CONTINUE",
            actor="reviewer",
            client_request_id="req-1",
            decision_expires_at=past,
        )
        assert result.result.decision_status == "blocked"
        assert "human_escalation_decision_expiry_invalid" in result.result.blocked_reasons
        sess.close()


# ══════════════════════════════════════════════════════════════════════
# 7. TestD1SourceVerification
# ══════════════════════════════════════════════════════════════════════


class TestD1SourceVerification:
    def _prepare_and_get_pkg_id(self, SessionLocal) -> UUID:
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()
        pkg_msg_id, _ = _d1_prepare(SessionLocal)
        return pkg_msg_id

    def _assert_blocked(
        self,
        SessionLocal,
        pkg_msg_id: UUID,
        *,
        reason: str,
    ) -> None:
        svc, sess = _make_d2_service(SessionLocal)
        result = svc.record_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pkg_msg_id,
            decision_action="APPROVE_CONTINUE",
            actor="human-reviewer",
            client_request_id=f"req-{uuid4()}",
            decision_expires_at=datetime.now(timezone.utc).replace(year=2099),
        )
        assert result.result.decision_status == "blocked"
        assert reason in result.result.blocked_reasons
        assert result.message is None
        sess.close()

    def test_session_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        pkg_msg_id = self._prepare_and_get_pkg_id(SessionLocal)
        foreign_session = uuid4()
        session = SessionLocal()
        session.add(
            ProjectDirectorSessionTable(
                id=foreign_session, project_id=PROJECT_ID,
                goal_text="Foreign", constraints="", status="confirmed",
            )
        )
        session.flush()
        row = session.get(ProjectDirectorMessageTable, pkg_msg_id)
        row.session_id = foreign_session
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, pkg_msg_id, reason="source_package_message_session_mismatch")

    def test_task_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        pkg_msg_id = self._prepare_and_get_pkg_id(SessionLocal)
        foreign_task = uuid4()
        session = SessionLocal()
        session.add(
            TaskTable(
                id=foreign_task, project_id=PROJECT_ID, title="Foreign",
                status="pending", priority="normal", input_summary="F",
                risk_level="normal", human_status="none",
                source_draft_id="p12-f", acceptance_criteria="[]",
            )
        )
        session.flush()
        row = session.get(ProjectDirectorMessageTable, pkg_msg_id)
        row.related_task_id = foreign_task
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, pkg_msg_id, reason="source_package_message_task_mismatch")

    def test_project_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        pkg_msg_id = self._prepare_and_get_pkg_id(SessionLocal)
        foreign_project = uuid4()
        session = SessionLocal()
        session.add(
            ProjectTable(
                id=foreign_project, name="Other", summary="Other",
                status="active", stage="intake",
            )
        )
        session.flush()
        row = session.get(ProjectDirectorMessageTable, pkg_msg_id)
        row.related_project_id = foreign_project
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, pkg_msg_id, reason="source_package_message_project_mismatch")

    def test_role_changed(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        pkg_msg_id = self._prepare_and_get_pkg_id(SessionLocal)
        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pkg_msg_id)
        row.role = "user"
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, pkg_msg_id, reason="source_package_message_role_invalid")

    def test_source_changed(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        pkg_msg_id = self._prepare_and_get_pkg_id(SessionLocal)
        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pkg_msg_id)
        row.source = "ai"
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, pkg_msg_id, reason="source_package_message_source_invalid")

    def test_intent_changed(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        pkg_msg_id = self._prepare_and_get_pkg_id(SessionLocal)
        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pkg_msg_id)
        row.intent = "wrong_intent"
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, pkg_msg_id, reason="source_package_message_intent_invalid")

    def test_source_detail_changed(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        pkg_msg_id = self._prepare_and_get_pkg_id(SessionLocal)
        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pkg_msg_id)
        row.source_detail = "wrong_detail"
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, pkg_msg_id, reason="source_message_is_not_p21_d_d1_package")

    def test_requires_confirmation_changed(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        pkg_msg_id = self._prepare_and_get_pkg_id(SessionLocal)
        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pkg_msg_id)
        row.requires_confirmation = False
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, pkg_msg_id, reason="source_package_confirmation_contract_invalid")

    def test_risk_level_changed(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        pkg_msg_id = self._prepare_and_get_pkg_id(SessionLocal)
        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pkg_msg_id)
        row.risk_level = "low"
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, pkg_msg_id, reason="source_package_message_risk_level_invalid")

    def test_action_type_changed(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        pkg_msg_id = self._prepare_and_get_pkg_id(SessionLocal)
        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pkg_msg_id)
        actions = json.loads(row.suggested_actions_json)
        actions[0]["type"] = "wrong_type"
        row.suggested_actions_json = json.dumps(actions)
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, pkg_msg_id, reason="source_human_escalation_package_record_missing")

    def test_schema_version_changed(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        pkg_msg_id = self._prepare_and_get_pkg_id(SessionLocal)
        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pkg_msg_id)
        actions = json.loads(row.suggested_actions_json)
        actions[0]["schema_version"] = "wrong"
        row.suggested_actions_json = json.dumps(actions)
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, pkg_msg_id, reason="source_package_schema_version_mismatch")

    def test_package_status_changed(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        pkg_msg_id = self._prepare_and_get_pkg_id(SessionLocal)
        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pkg_msg_id)
        actions = json.loads(row.suggested_actions_json)
        actions[0]["package_status"] = "blocked"
        row.suggested_actions_json = json.dumps(actions)
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, pkg_msg_id, reason="source_package_status_invalid")

    def test_escalation_package_id_changed(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        pkg_msg_id = self._prepare_and_get_pkg_id(SessionLocal)
        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pkg_msg_id)
        actions = json.loads(row.suggested_actions_json)
        actions[0]["escalation_package_id"] = str(uuid4())
        actions[0]["aggregate_evidence_fingerprint"] = "f" * 64
        row.suggested_actions_json = json.dumps(actions)
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, pkg_msg_id, reason="aggregate_evidence_fingerprint_mismatch")

    def test_source_disposition_id_changed(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        pkg_msg_id = self._prepare_and_get_pkg_id(SessionLocal)
        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pkg_msg_id)
        actions = json.loads(row.suggested_actions_json)
        actions[0]["source_disposition_message_id"] = str(uuid4())
        row.suggested_actions_json = json.dumps(actions)
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, pkg_msg_id, reason="aggregate_evidence_fingerprint_mismatch")

    def test_source_review_id_changed(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        pkg_msg_id = self._prepare_and_get_pkg_id(SessionLocal)
        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pkg_msg_id)
        actions = json.loads(row.suggested_actions_json)
        new_review_id = str(uuid4())
        actions[0]["source_review_message_id"] = new_review_id
        actions[0]["related_review_message_ids"] = [new_review_id]
        actions[0]["aggregate_evidence_fingerprint"] = "f" * 64
        row.suggested_actions_json = json.dumps(actions)
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, pkg_msg_id, reason="aggregate_evidence_fingerprint_mismatch")

    def test_source_preflight_id_changed(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        pkg_msg_id = self._prepare_and_get_pkg_id(SessionLocal)
        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pkg_msg_id)
        actions = json.loads(row.suggested_actions_json)
        actions[0]["source_preflight_message_id"] = str(uuid4())
        row.suggested_actions_json = json.dumps(actions)
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, pkg_msg_id, reason="aggregate_evidence_fingerprint_mismatch")

    def test_source_diff_id_changed(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        pkg_msg_id = self._prepare_and_get_pkg_id(SessionLocal)
        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pkg_msg_id)
        actions = json.loads(row.suggested_actions_json)
        actions[0]["source_diff_message_id"] = str(uuid4())
        row.suggested_actions_json = json.dumps(actions)
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, pkg_msg_id, reason="aggregate_evidence_fingerprint_mismatch")

    def test_disposition_id_changed(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        pkg_msg_id = self._prepare_and_get_pkg_id(SessionLocal)
        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pkg_msg_id)
        actions = json.loads(row.suggested_actions_json)
        actions[0]["disposition_id"] = str(uuid4())
        row.suggested_actions_json = json.dumps(actions)
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, pkg_msg_id, reason="aggregate_evidence_fingerprint_mismatch")

    def test_aggregate_evidence_fingerprint_changed(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        pkg_msg_id = self._prepare_and_get_pkg_id(SessionLocal)
        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pkg_msg_id)
        actions = json.loads(row.suggested_actions_json)
        actions[0]["aggregate_evidence_fingerprint"] = "a" * 64
        row.suggested_actions_json = json.dumps(actions)
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, pkg_msg_id, reason="aggregate_evidence_fingerprint_mismatch")

    @pytest.mark.parametrize("flag", _D2_PACKAGE_FALSE_FLAGS)
    def test_false_only_flag_set_true(self, db_engine, flag: str) -> None:
        SessionLocal = _make_session_factory(db_engine)
        pkg_msg_id = self._prepare_and_get_pkg_id(SessionLocal)
        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pkg_msg_id)
        actions = json.loads(row.suggested_actions_json)
        actions[0][flag] = True
        row.suggested_actions_json = json.dumps(actions)
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, pkg_msg_id, reason="source_package_write_boundary_violated")

    def test_total_loop_not_partial(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        pkg_msg_id = self._prepare_and_get_pkg_id(SessionLocal)
        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pkg_msg_id)
        actions = json.loads(row.suggested_actions_json)
        actions[0]["ai_project_director_total_loop"] = "Full"
        row.suggested_actions_json = json.dumps(actions)
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, pkg_msg_id, reason="source_package_write_boundary_violated")


# ══════════════════════════════════════════════════════════════════════
# 8. TestFingerprintIsolation
# ══════════════════════════════════════════════════════════════════════


class TestFingerprintIsolation:
    def _record_and_get_action(self, SessionLocal) -> tuple[dict[str, Any], str, str]:
        """Record a D2 decision and return (stored_action, session_id_str, source_task_id_str)."""
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        pkg_msg_id, _ = _d1_prepare(SessionLocal)
        client_req = f"req-{uuid4()}"
        svc, sess = _make_d2_service(SessionLocal)
        result = svc.record_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pkg_msg_id,
            decision_action="APPROVE_CONTINUE",
            actor="human-reviewer",
            client_request_id=client_req,
            decision_expires_at=datetime.now(timezone.utc).replace(year=2099),
        )
        assert result.result.decision_status == "recorded"
        msg_id = result.message.id
        sess.close()

        verify = SessionLocal()
        row = verify.get(ProjectDirectorMessageTable, msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        verify.close()
        return action, str(SESSION_ID), str(TASK_ID)

    def _revalidate_fingerprint(
        self, action: dict[str, Any], session_id_str: str, task_id_str: str
    ) -> str:
        svc_cls = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionService
        rv = svc_cls.revalidate_persisted_human_escalation_decision_fingerprint(
            session_id=UUID(session_id_str),
            source_task_id=UUID(task_id_str),
            source_decision_message_id=uuid4(),
            source_decision_action=action,
        )
        return rv.decision_confirmation_fingerprint

    @pytest.mark.parametrize(
        "field,new_value",
        [
            ("session_id", str(uuid4())),
            ("source_task_id", str(uuid4())),
            ("source_package_message_id", str(uuid4())),
            ("escalation_package_id", str(uuid4())),
            ("source_disposition_message_id", str(uuid4())),
            ("source_review_message_id", str(uuid4())),
            ("source_preflight_message_id", str(uuid4())),
            ("source_diff_message_id", str(uuid4())),
            ("disposition_id", str(uuid4())),
            ("aggregate_evidence_fingerprint", "b" * 64),
            ("decision_scope", "other_scope"),
            ("decision_action", "REJECT"),
            ("actor", "other-actor"),
            ("client_request_id", "other-req"),
            ("decision_id", str(uuid4())),
            ("decision_created_at", datetime(2000, 1, 1, tzinfo=timezone.utc).isoformat()),
            ("decision_expires_at", datetime(2099, 12, 31, tzinfo=timezone.utc).isoformat()),
        ],
        ids=[
            "session_id",
            "source_task_id",
            "source_package_message_id",
            "escalation_package_id",
            "source_disposition_message_id",
            "source_review_message_id",
            "source_preflight_message_id",
            "source_diff_message_id",
            "disposition_id",
            "aggregate_evidence_fingerprint",
            "decision_scope",
            "decision_action",
            "actor",
            "client_request_id",
            "decision_id",
            "decision_created_at",
            "decision_expires_at",
        ],
    )
    def test_field_change_breaks_fingerprint(self, tmp_path, field, new_value) -> None:
        db_path = str(tmp_path / "fp_iso.db")
        engine = _make_test_engine(db_path)
        SessionLocal = _make_session_factory(engine)

        action, sid, tid = self._record_and_get_action(SessionLocal)
        original_fp = self._revalidate_fingerprint(action, sid, tid)
        assert original_fp != ""

        tampered = dict(action)
        tampered[field] = new_value
        tampered_fp = self._revalidate_fingerprint(tampered, sid, tid)
        assert tampered_fp != original_fp, f"Changing {field} should break fingerprint"

        engine.dispose()

    def test_stored_fingerprint_tampered_blocks_d3_revalidation(self, tmp_path) -> None:
        db_path = str(tmp_path / "fp_tamp.db")
        engine = _make_test_engine(db_path)
        SessionLocal = _make_session_factory(engine)

        action, sid, tid = self._record_and_get_action(SessionLocal)
        original_fp = self._revalidate_fingerprint(action, sid, tid)
        assert original_fp != ""
        assert original_fp == action["decision_confirmation_fingerprint"]

        tampered = dict(action)
        tampered["decision_confirmation_fingerprint"] = "f" * 64
        revalidated_fp = self._revalidate_fingerprint(tampered, sid, tid)
        assert revalidated_fp == original_fp
        assert revalidated_fp != tampered["decision_confirmation_fingerprint"]

        engine.dispose()


# ══════════════════════════════════════════════════════════════════════
# 9. TestReplay
# ══════════════════════════════════════════════════════════════════════


class TestReplay:
    def test_source_package_message_id_replay(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        pkg_msg_id, pkg_seq_no = _d1_prepare(SessionLocal)
        client_req_1 = f"req-{uuid4()}"

        svc1, s1 = _make_d2_service(SessionLocal)
        r1 = svc1.record_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pkg_msg_id,
            decision_action="APPROVE_CONTINUE",
            actor="human-reviewer",
            client_request_id=client_req_1,
            decision_expires_at=datetime.now(timezone.utc).replace(year=2099),
        )
        assert r1.result.decision_status == "recorded"
        d2_seq = r1.message.sequence_no
        s1.close()

        session = SessionLocal()
        _seed_filler_messages(session, d2_seq + 1, 105)
        session.close()

        svc2, s2 = _make_d2_service(SessionLocal)
        r2 = svc2.record_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pkg_msg_id,
            decision_action="REQUEST_REWORK",
            actor="other-reviewer",
            client_request_id=f"req-{uuid4()}",
            decision_expires_at=datetime.now(timezone.utc).replace(year=2099),
        )
        assert r2.result.decision_status == "blocked"
        assert "human_escalation_decision_already_recorded" in r2.result.blocked_reasons
        assert r2.result.prior_decision_detected is True
        assert r2.result.replay_check_completed is True
        assert r2.message is None
        s2.close()

    def test_escalation_package_id_replay(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        pkg_msg_id_1, _ = _d1_prepare(SessionLocal)

        svc1, s1 = _make_d2_service(SessionLocal)
        r1 = svc1.record_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pkg_msg_id_1,
            decision_action="APPROVE_CONTINUE",
            actor="human-reviewer",
            client_request_id=f"req-{uuid4()}",
            decision_expires_at=datetime.now(timezone.utc).replace(year=2099),
        )
        assert r1.result.decision_status == "recorded"
        d2_seq = r1.message.sequence_no
        escalation_pkg_id = r1.result.escalation_package_id
        s1.close()

        session = SessionLocal()
        _seed_filler_messages(session, d2_seq + 1, 105)
        session.close()

        review_msg_id_2 = uuid4()
        disp_msg_id_2 = uuid4()
        disp_id_2 = uuid4()
        session = SessionLocal()
        _seed_review_message(session, review_msg_id=review_msg_id_2, seq_no=300)
        review_action_2 = _valid_review_action()
        fp_2 = _compute_review_fingerprint_from_action(
            review_action_2, source_review_message_id=review_msg_id_2,
        )
        _seed_disposition_message(
            session,
            disposition_msg_id=disp_msg_id_2,
            review_msg_id=review_msg_id_2,
            fingerprint=fp_2,
            action_overrides={"disposition_id": str(disp_id_2)},
            seq_no=310,
        )
        session.close()

        pkg_msg_id_2, _ = _d1_prepare(SessionLocal, disposition_msg_id=disp_msg_id_2)

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, pkg_msg_id_2)
        actions = json.loads(row.suggested_actions_json)
        actions[0]["escalation_package_id"] = str(escalation_pkg_id)
        row.suggested_actions_json = json.dumps(actions)
        session.commit()
        session.close()

        svc2, s2 = _make_d2_service(SessionLocal)
        r2 = svc2.record_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pkg_msg_id_2,
            decision_action="REJECT",
            actor="other-reviewer",
            client_request_id=f"req-{uuid4()}",
            decision_expires_at=datetime.now(timezone.utc).replace(year=2099),
        )
        assert r2.result.decision_status == "blocked"
        assert "human_escalation_package_already_decided" in r2.result.blocked_reasons
        assert r2.result.prior_decision_detected is True
        assert r2.result.replay_check_completed is True
        assert r2.message is None
        s2.close()

    def test_client_request_id_replay(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        pkg_msg_id_1, _ = _d1_prepare(SessionLocal)
        shared_client_req = f"req-{uuid4()}"

        svc1, s1 = _make_d2_service(SessionLocal)
        r1 = svc1.record_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pkg_msg_id_1,
            decision_action="APPROVE_CONTINUE",
            actor="human-reviewer",
            client_request_id=shared_client_req,
            decision_expires_at=datetime.now(timezone.utc).replace(year=2099),
        )
        assert r1.result.decision_status == "recorded"
        d2_seq = r1.message.sequence_no
        s1.close()

        session = SessionLocal()
        _seed_filler_messages(session, d2_seq + 1, 105)
        session.close()

        review_msg_id_2 = uuid4()
        disp_msg_id_2 = uuid4()
        disp_id_2 = uuid4()
        session = SessionLocal()
        _seed_review_message(session, review_msg_id=review_msg_id_2, seq_no=300)
        review_action_2 = _valid_review_action()
        fp_2 = _compute_review_fingerprint_from_action(
            review_action_2, source_review_message_id=review_msg_id_2,
        )
        _seed_disposition_message(
            session,
            disposition_msg_id=disp_msg_id_2,
            review_msg_id=review_msg_id_2,
            fingerprint=fp_2,
            action_overrides={"disposition_id": str(disp_id_2)},
            seq_no=310,
        )
        session.close()

        pkg_msg_id_2, _ = _d1_prepare(SessionLocal, disposition_msg_id=disp_msg_id_2)

        svc2, s2 = _make_d2_service(SessionLocal)
        r2 = svc2.record_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pkg_msg_id_2,
            decision_action="REJECT",
            actor="other-reviewer",
            client_request_id=shared_client_req,
            decision_expires_at=datetime.now(timezone.utc).replace(year=2099),
        )
        assert r2.result.decision_status == "blocked"
        assert "human_decision_client_request_id_reused" in r2.result.blocked_reasons
        assert r2.result.prior_decision_detected is True
        assert r2.result.replay_check_completed is True
        assert r2.message is None
        s2.close()

    def test_d2_message_count_exactly_one(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        result, _ = _seed_full_d1_d2(SessionLocal)

        verify = SessionLocal()
        count = verify.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd"
            ),
            {"sd": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_SOURCE_DETAIL},
        ).scalar()
        assert count == 1
        verify.close()


# ══════════════════════════════════════════════════════════════════════
# 10. TestConcurrency
# ══════════════════════════════════════════════════════════════════════


class TestConcurrency:
    def test_barrier_two_threads_one_recorded_one_blocked(self, tmp_path) -> None:
        db_path = str(tmp_path / "concurrent.db")
        engine = _make_test_engine(db_path)
        SessionLocal = _make_session_factory(engine)

        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        pkg_msg_id, _ = _d1_prepare(SessionLocal)

        barrier = threading.Barrier(2, timeout=30)
        results: list = []
        errors: list = []

        def worker(worker_id: int):
            try:
                sess = SessionLocal()
                msg_repo = ProjectDirectorMessageRepository(sess)
                sess_repo = ProjectDirectorSessionRepository(sess)
                task_repo = TaskRepository(sess)
                svc = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionService(
                    session_repository=sess_repo,
                    message_repository=msg_repo,
                    task_repository=task_repo,
                )
                barrier.wait()
                result = svc.record_human_escalation_decision(
                    session_id=SESSION_ID,
                    source_task_id=TASK_ID,
                    source_message_id=pkg_msg_id,
                    decision_action="APPROVE_CONTINUE",
                    actor="human-reviewer",
                    client_request_id=f"req-worker-{worker_id}-{uuid4()}",
                    decision_expires_at=datetime.now(timezone.utc).replace(year=2099),
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

        statuses = [r.result.decision_status for _, r in results]
        assert statuses.count("recorded") == 1
        assert statuses.count("blocked") == 1

        recorded_result = next(r for _, r in results if r.result.decision_status == "recorded")
        blocked_result = next(r for _, r in results if r.result.decision_status == "blocked")
        assert recorded_result.message is not None
        assert blocked_result.message is None
        assert blocked_result.result.prior_decision_detected is True
        assert blocked_result.result.replay_check_completed is True

        verify = SessionLocal()
        count = verify.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd"
            ),
            {"sd": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_SOURCE_DETAIL},
        ).scalar()
        assert count == 1
        verify.execute(text("BEGIN IMMEDIATE"))
        verify.commit()
        verify.close()
        engine.dispose()


# ══════════════════════════════════════════════════════════════════════
# 11. TestAppendOnlyAndNoSideEffects
# ══════════════════════════════════════════════════════════════════════


class TestAppendOnlyAndNoSideEffects:
    def test_d1_package_message_unchanged(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        pkg_msg_id, _ = _d1_prepare(SessionLocal)

        session = SessionLocal()
        pkg_row = session.get(ProjectDirectorMessageTable, pkg_msg_id)
        pkg_snapshot = pkg_row.suggested_actions_json
        session.close()

        svc, sess = _make_d2_service(SessionLocal)
        result = svc.record_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pkg_msg_id,
            decision_action="APPROVE_CONTINUE",
            actor="human-reviewer",
            client_request_id=f"req-{uuid4()}",
            decision_expires_at=datetime.now(timezone.utc).replace(year=2099),
        )
        assert result.result.decision_status == "recorded"
        sess.close()

        verify = SessionLocal()
        pkg_after = verify.get(ProjectDirectorMessageTable, pkg_msg_id)
        assert pkg_after.suggested_actions_json == pkg_snapshot
        verify.close()

    def test_no_new_tasks(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        pre = SessionLocal()
        task_count_before = pre.execute(text("SELECT COUNT(*) FROM tasks")).scalar()
        pre.close()

        pkg_msg_id, _ = _d1_prepare(SessionLocal)

        svc, sess = _make_d2_service(SessionLocal)
        result = svc.record_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pkg_msg_id,
            decision_action="APPROVE_CONTINUE",
            actor="human-reviewer",
            client_request_id=f"req-{uuid4()}",
            decision_expires_at=datetime.now(timezone.utc).replace(year=2099),
        )
        assert result.result.decision_status == "recorded"
        sess.close()

        post = SessionLocal()
        task_count_after = post.execute(text("SELECT COUNT(*) FROM tasks")).scalar()
        assert task_count_after == task_count_before
        post.close()

    def test_no_new_runs(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        result, _ = _seed_full_d1_d2(SessionLocal)
        assert result.result.decision_status == "recorded"

        post = SessionLocal()
        run_count = post.execute(text("SELECT COUNT(*) FROM runs")).scalar()
        assert run_count == 0
        post.close()

    def test_no_side_effect_flags_on_result(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        result, _ = _seed_full_d1_d2(SessionLocal)
        r = result.result
        assert r.decision_consumption_started is False
        assert r.decision_consumed is False
        assert r.decision_revoked is False
        assert r.decision_expired is False
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

    def test_action_forbidden_actions_on_message(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        result, _ = _seed_full_d1_d2(SessionLocal)
        action = result.message.suggested_actions[0]
        for flag in _D2_FALSE_ONLY_FLAGS:
            assert action.get(flag) is False, f"{flag} should be False in action"
        assert action["ai_project_director_total_loop"] == "Partial"
        assert action["gate_allows_write"] is False

    def test_no_tasks_or_runs_after_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        pkg_msg_id, _ = _d1_prepare(SessionLocal)

        pre = SessionLocal()
        task_count_before = pre.execute(text("SELECT COUNT(*) FROM tasks")).scalar()
        run_count_before = pre.execute(text("SELECT COUNT(*) FROM runs")).scalar()
        pre.close()

        svc, sess = _make_d2_service(SessionLocal)
        result = svc.record_human_escalation_decision(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=pkg_msg_id,
            decision_action="APPROVE_CONTINUE",
            actor="",
            client_request_id="",
            decision_expires_at=datetime.now(timezone.utc).replace(year=2099),
        )
        assert result.result.decision_status == "blocked"
        sess.close()

        post = SessionLocal()
        assert post.execute(text("SELECT COUNT(*) FROM tasks")).scalar() == task_count_before
        assert post.execute(text("SELECT COUNT(*) FROM runs")).scalar() == run_count_before
        post.close()
