"""Contract tests for P21-D-C1 disposition consumption preflight & atomic replay guard."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
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
from app.domain.project_director_sandbox_candidate_diff_review_disposition_consumption_preflight import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightResult,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.services.project_director_sandbox_candidate_diff_readonly_review_execution_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_consumption_preflight_service import (
    DISPOSITION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightService,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_service import (
    DEFERRED_TRIGGER_KINDS,
    EVALUATED_TRIGGER_KINDS,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL,
    REVIEW_DISPOSITION_SCHEMA_VERSION,
)
from app.services.project_director_sandbox_candidate_diff_review_execution_preflight_service import (
    REVIEW_OUTPUT_SCHEMA_VERSION,
)

# ── Constants ───────────────────────────────────────────────────────

SESSION_ID = uuid4()
TASK_ID = uuid4()
PROJECT_ID = uuid4()
SOURCE_REVIEW_MSG_ID = uuid4()
PREFLIGHT_MSG_ID = uuid4()
DIFF_MSG_ID = uuid4()

_TRUE_HEX_SHA256 = hashlib.sha256(b"diff content").hexdigest()
_PROMPT_SHA256 = hashlib.sha256(b"prompt content").hexdigest()
_RAW_OUTPUT_SHA256 = hashlib.sha256(b"raw output").hexdigest()

_DISPOSITION_FALSE_FLAGS = [
    "continuation_started",
    "rework_started",
    "disposition_consumed",
    "human_escalation_package_created",
    "human_decision_recorded",
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


# ── Test database helpers ───────────────────────────────────────────


def _make_test_engine(db_path: str):
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )

    @event.listens_for(engine, "connect")
    def _configure_sqlite(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.close()

    ORMBase.metadata.create_all(bind=engine)
    return engine


def _make_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


# ── Seed helpers ────────────────────────────────────────────────────


def _seed_base_records(session: Session) -> None:
    session.add(ProjectTable(
        id=PROJECT_ID, name="Test", summary="Test project",
        status="active", stage="intake",
    ))
    session.add(TaskTable(
        id=TASK_ID, project_id=PROJECT_ID, title="Test task",
        status="pending", priority="normal", input_summary="Test",
        risk_level="normal", human_status="none",
    ))
    session.commit()


def _seed_review_message(
    session: Session,
    *,
    msg_id=SOURCE_REVIEW_MSG_ID,
    verdict="no_blocking_findings",
    risk_level="low",
    findings=None,
    source_diff_sha256=None,
    review_prompt_sha256=None,
    review_scope_paths=None,
) -> None:
    findings = findings if findings is not None else []
    src_diff_sha = source_diff_sha256 or _TRUE_HEX_SHA256
    src_prompt_sha = review_prompt_sha256 or _PROMPT_SHA256
    src_scope = review_scope_paths or ["src/example.py"]
    action = {
        "type": P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
        "session_id": str(SESSION_ID),
        "source_task_id": str(TASK_ID),
        "source_preflight_message_id": str(PREFLIGHT_MSG_ID),
        "source_diff_message_id": str(DIFF_MSG_ID),
        "requested_reviewer_executor": "codex",
        "source_diff_sha256": src_diff_sha,
        "review_prompt_sha256": src_prompt_sha,
        "review_scope_paths": list(src_scope),
        "review_output_schema_version": REVIEW_OUTPUT_SCHEMA_VERSION,
        "adapter_status": "validated_output",
        "output_validation_status": "validated",
        "raw_output_sha256": _RAW_OUTPUT_SHA256,
        "strict_json_valid": True,
        "schema_valid": True,
        "semantics_valid": True,
        "evidence_scope_valid": True,
        "review_status": "reviewed",
        "verdict": verdict,
        "risk_level": risk_level,
        "summary": "Review completed.",
        "findings": list(findings),
        "recommended_next_step": "Proceed.",
        "ai_project_director_total_loop": "Partial",
    }
    for flag in [
        "main_project_file_written", "sandbox_file_written", "manifest_file_written",
        "diff_file_written", "patch_applied", "git_write_performed",
        "worktree_created", "worker_started", "task_created", "run_created",
    ]:
        action[flag] = False
    session.add(ProjectDirectorMessageTable(
        id=msg_id, session_id=SESSION_ID, role="assistant",
        content="Readonly review executed.", sequence_no=50,
        intent="sandbox_candidate_diff_readonly_review_execution",
        related_project_id=PROJECT_ID, related_task_id=TASK_ID,
        source="system",
        source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
        suggested_actions_json=json.dumps([action]),
        requires_confirmation=False, risk_level="high",
    ))
    session.commit()


def _seed_disposition_message(
    session: Session,
    *,
    disposition_msg_id: UUID | None = None,
    disposition_type="AUTO_CONTINUE",
    disposition_reason="review_has_no_blocking_findings",
    verdict="no_blocking_findings",
    risk_level="low",
    escalation_triggers=None,
    findings=None,
    source_diff_sha256=None,
    review_prompt_sha256=None,
    review_scope_paths=None,
    source_review_msg_id=None,
    source_preflight_msg_id=None,
    source_diff_msg_id=None,
    review_result_fingerprint_override=None,
    resync_review_message=True,
) -> UUID:
    disposition_msg_id = disposition_msg_id or uuid4()
    escalation_triggers = escalation_triggers if escalation_triggers is not None else []
    findings = findings if findings is not None else []
    src_diff_sha = source_diff_sha256 or _TRUE_HEX_SHA256
    src_prompt_sha = review_prompt_sha256 or _PROMPT_SHA256
    src_scope = review_scope_paths or ["src/example.py"]
    src_review_id = source_review_msg_id or SOURCE_REVIEW_MSG_ID
    src_preflight_id = source_preflight_msg_id or PREFLIGHT_MSG_ID
    src_diff_id = source_diff_msg_id or DIFF_MSG_ID

    if resync_review_message and (
        verdict != "no_blocking_findings"
        or risk_level != "low"
        or findings
        or source_diff_sha256
        or review_prompt_sha256
        or review_scope_paths
    ):
        existing = session.get(ProjectDirectorMessageTable, src_review_id)
        if existing is not None:
            action = json.loads(existing.suggested_actions_json)[0]
            action["verdict"] = verdict
            action["risk_level"] = risk_level
            action["findings"] = list(findings)
            if source_diff_sha256:
                action["source_diff_sha256"] = source_diff_sha256
            if review_prompt_sha256:
                action["review_prompt_sha256"] = review_prompt_sha256
            if review_scope_paths:
                action["review_scope_paths"] = list(review_scope_paths)
            existing.suggested_actions_json = json.dumps([action])
            session.commit()

    fp = review_result_fingerprint_override or _compute_review_fingerprint(
        verdict=verdict, risk_level=risk_level, findings=findings,
        source_diff_sha256=src_diff_sha, review_prompt_sha256=src_prompt_sha,
        review_scope_paths=src_scope,
    )

    action = {
        "type": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_ACTION_TYPE,
        "schema_version": REVIEW_DISPOSITION_SCHEMA_VERSION,
        "disposition_status": "computed",
        "session_id": str(SESSION_ID),
        "source_task_id": str(TASK_ID),
        "source_review_message_id": str(src_review_id),
        "source_preflight_message_id": str(src_preflight_id),
        "source_diff_message_id": str(src_diff_id),
        "requested_reviewer_executor": "codex",
        "source_diff_sha256": src_diff_sha,
        "review_prompt_sha256": src_prompt_sha,
        "review_scope_paths": list(src_scope),
        "review_output_schema_version": REVIEW_OUTPUT_SCHEMA_VERSION,
        "review_result_fingerprint": fp,
        "disposition_id": str(uuid4()),
        "disposition_type": disposition_type,
        "disposition_reason": disposition_reason,
        "source_review_verdict": verdict,
        "source_review_risk_level": risk_level,
        "escalation_triggers": list(escalation_triggers),
        "evaluated_trigger_kinds": list(EVALUATED_TRIGGER_KINDS),
        "deferred_trigger_kinds": list(DEFERRED_TRIGGER_KINDS),
        "actor": "system",
        "client_request_id": None,
        "disposition_created_at": datetime.now(timezone.utc).isoformat(),
    }
    for flag in _DISPOSITION_FALSE_FLAGS:
        action[flag] = False
    action["ai_project_director_total_loop"] = "Partial"

    session.add(ProjectDirectorMessageTable(
        id=disposition_msg_id, session_id=SESSION_ID, role="assistant",
        content="Disposition computed.", sequence_no=60,
        intent="sandbox_candidate_diff_review_disposition",
        related_project_id=PROJECT_ID, related_task_id=TASK_ID,
        source="system",
        source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL,
        suggested_actions_json=json.dumps([action]),
        requires_confirmation=False, risk_level="high",
    ))
    session.commit()
    return disposition_msg_id


def _compute_review_fingerprint(
    *,
    verdict="no_blocking_findings",
    risk_level="low",
    findings=None,
    source_diff_sha256=None,
    review_prompt_sha256=None,
    review_scope_paths=None,
) -> str:
    findings = findings if findings is not None else []
    src_diff_sha = source_diff_sha256 or _TRUE_HEX_SHA256
    src_prompt_sha = review_prompt_sha256 or _PROMPT_SHA256
    src_scope = review_scope_paths or ["src/example.py"]
    payload = {
        "session_id": str(SESSION_ID),
        "source_task_id": str(TASK_ID),
        "source_review_message_id": str(SOURCE_REVIEW_MSG_ID),
        "source_preflight_message_id": str(PREFLIGHT_MSG_ID),
        "source_diff_message_id": str(DIFF_MSG_ID),
        "requested_reviewer_executor": "codex",
        "source_diff_sha256": src_diff_sha,
        "review_prompt_sha256": src_prompt_sha,
        "review_scope_paths": list(src_scope),
        "review_output_schema_version": REVIEW_OUTPUT_SCHEMA_VERSION,
        "raw_output_sha256": _RAW_OUTPUT_SHA256,
        "output_validation_status": "validated",
        "strict_json_valid": True,
        "schema_valid": True,
        "semantics_valid": True,
        "evidence_scope_valid": True,
        "review_status": "reviewed",
        "verdict": verdict,
        "risk_level": risk_level,
        "summary": "Review completed.",
        "findings": findings,
        "recommended_next_step": "Proceed.",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _seed_pd_session(session: Session) -> None:
    session.add(ProjectDirectorSessionTable(
        id=SESSION_ID, project_id=PROJECT_ID,
        goal_text="Test goal", constraints="",
        status="confirmed",
    ))
    session.commit()


# ── Full fixture ────────────────────────────────────────────────────


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
    _seed_pd_session(session)
    _seed_review_message(session)
    session.close()
    return SessionLocal


def _make_service(session_local):
    session = session_local()
    msg_repo = ProjectDirectorMessageRepository(session)
    sess_repo = ProjectDirectorSessionRepository(session)
    svc = ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightService(
        session_repository=sess_repo,
        message_repository=msg_repo,
    )
    return svc, msg_repo, session


# ══════════════════════════════════════════════════════════════════════
# A. Repository transaction contract
# ══════════════════════════════════════════════════════════════════════


class TestRepositoryTransactionContract:
    def test_idle_session_can_enter_immediate(self, seeded_session) -> None:
        session = seeded_session()
        repo = ProjectDirectorMessageRepository(session)
        with repo.sqlite_immediate_transaction():
            session.execute(text("SELECT 1"))
        session.close()

    def test_active_transaction_rejected(self, seeded_session) -> None:
        session = seeded_session()
        repo = ProjectDirectorMessageRepository(session)
        session.execute(text("BEGIN"))
        with pytest.raises(ValueError, match="idle session"):
            with repo.sqlite_immediate_transaction():
                pass
        session.rollback()
        session.close()

    def test_active_transaction_no_auto_commit(self, seeded_session) -> None:
        session = seeded_session()
        repo = ProjectDirectorMessageRepository(session)
        session.add(ProjectDirectorMessageTable(
            id=uuid4(), session_id=SESSION_ID, role="user",
            content="pending", sequence_no=999,
            source="user", source_detail="",
        ))
        with pytest.raises(ValueError, match="idle session"):
            with repo.sqlite_immediate_transaction():
                pass
        other_session = seeded_session()
        count = other_session.execute(
            text("SELECT COUNT(*) FROM project_director_messages WHERE sequence_no = 999")
        ).scalar()
        assert count == 0
        session.rollback()
        session.close()
        other_session.close()

    def test_exception_rollback(self, seeded_session) -> None:
        session = seeded_session()
        repo = ProjectDirectorMessageRepository(session)
        with pytest.raises(RuntimeError, match="test error"):
            with repo.sqlite_immediate_transaction():
                session.add(ProjectDirectorMessageTable(
                    id=uuid4(), session_id=SESSION_ID, role="user",
                    content="should be rolled back", sequence_no=998,
                    source="user", source_detail="",
                ))
                raise RuntimeError("test error")
        other_session = seeded_session()
        count = other_session.execute(
            text("SELECT COUNT(*) FROM project_director_messages WHERE sequence_no = 998")
        ).scalar()
        assert count == 0
        other_session.execute(text("BEGIN IMMEDIATE"))
        other_session.commit()
        session.close()
        other_session.close()

    def test_blocked_return_releases_lock(self, seeded_session) -> None:
        session = seeded_session()
        _seed_disposition_message(session)
        session.close()

        session_a = seeded_session()
        msg_repo_a = ProjectDirectorMessageRepository(session_a)
        sess_repo_a = ProjectDirectorSessionRepository(session_a)
        svc_a = ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightService(
            session_repository=sess_repo_a,
            message_repository=msg_repo_a,
        )
        disposition_msg_id = uuid4()
        _seed_disposition_message(seeded_session(), disposition_msg_id=disposition_msg_id)
        result = svc_a.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert result.result.preflight_status in ("ready", "blocked")
        session_a.close()

        session_b = seeded_session()
        session_b.execute(text("BEGIN IMMEDIATE"))
        session_b.commit()
        session_b.close()


# ══════════════════════════════════════════════════════════════════════
# B. Domain safety contract
# ══════════════════════════════════════════════════════════════════════


class TestDomainSafetyContract:
    def test_ready_must_have_valid_fingerprints(self, seeded_session) -> None:
        disposition_msg_id = _seed_disposition_message(seeded_session())
        svc, _, session = _make_service(seeded_session)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert result.result.preflight_status == "ready"
        assert len(result.result.review_result_fingerprint) == 64
        assert len(result.result.revalidated_review_result_fingerprint) == 64
        assert result.result.review_result_fingerprint == result.result.revalidated_review_result_fingerprint
        session.close()

    def test_ready_must_have_disposition_id_and_review_msg(self, seeded_session) -> None:
        disposition_msg_id = _seed_disposition_message(seeded_session())
        svc, _, session = _make_service(seeded_session)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert result.result.disposition_id is not None
        assert result.result.source_review_message_id is not None
        session.close()

    def test_ready_must_have_replay_check_completed(self, seeded_session) -> None:
        disposition_msg_id = _seed_disposition_message(seeded_session())
        svc, _, session = _make_service(seeded_session)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert result.result.replay_check_completed is True
        assert result.result.prior_preflight_detected is False
        session.close()

    def test_ready_eligibility_matches_disposition(self, seeded_session) -> None:
        disposition_msg_id = _seed_disposition_message(
            seeded_session(), disposition_type="AUTO_CONTINUE"
        )
        svc, _, session = _make_service(seeded_session)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert result.result.continuation_eligible is True
        assert result.result.rework_eligible is False
        session.close()

    def test_blocked_no_eligibility(self, seeded_session) -> None:
        svc, _, session = _make_service(seeded_session)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=uuid4(),
        )
        assert result.result.preflight_status == "blocked"
        assert result.result.continuation_eligible is False
        assert result.result.rework_eligible is False
        assert len(result.result.blocked_reasons) > 0
        session.close()

    @pytest.mark.parametrize("flag", _DISPOSITION_FALSE_FLAGS)
    def test_forbidden_side_effect_flag_rejected(self, flag: str) -> None:
        with pytest.raises(ValueError, match="consumption preflight may not"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightResult(
                preflight_status="ready",
                source_disposition_message_id=uuid4(),
                source_review_message_id=uuid4(),
                disposition_id=uuid4(),
                disposition_type="AUTO_CONTINUE",
                review_result_fingerprint="a" * 64,
                revalidated_review_result_fingerprint="a" * 64,
                replay_check_completed=True,
                prior_preflight_detected=False,
                continuation_eligible=True,
                **{flag: True},
            )

    def test_total_loop_can_only_be_partial(self, seeded_session) -> None:
        disposition_msg_id = _seed_disposition_message(seeded_session())
        svc, _, session = _make_service(seeded_session)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert result.result.ai_project_director_total_loop == "Partial"
        session.close()


# ══════════════════════════════════════════════════════════════════════
# C. AUTO_CONTINUE ready
# ══════════════════════════════════════════════════════════════════════


class TestAutoContinueReady:
    def test_auto_continue_ready(self, seeded_session) -> None:
        disposition_msg_id = _seed_disposition_message(seeded_session())
        svc, _, session = _make_service(seeded_session)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert result.result.preflight_status == "ready"
        assert result.result.disposition_type == "AUTO_CONTINUE"
        assert result.result.continuation_eligible is True
        assert result.result.rework_eligible is False
        assert result.result.replay_check_completed is True
        assert result.result.prior_preflight_detected is False
        assert result.result.blocked_reasons == []
        assert result.message is not None
        assert result.message.requires_confirmation is False
        session.close()


# ══════════════════════════════════════════════════════════════════════
# D. AUTO_REWORK ready
# ══════════════════════════════════════════════════════════════════════


class TestAutoReworkReady:
    def test_auto_rework_ready(self, seeded_session) -> None:
        disposition_msg_id = _seed_disposition_message(
            seeded_session(),
            disposition_type="AUTO_REWORK",
            disposition_reason="review_changes_required_within_automatic_rework_boundary",
            verdict="changes_required",
            risk_level="medium",
        )
        svc, _, session = _make_service(seeded_session)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert result.result.preflight_status == "ready"
        assert result.result.disposition_type == "AUTO_REWORK"
        assert result.result.continuation_eligible is False
        assert result.result.rework_eligible is True
        assert result.result.blocked_reasons == []
        assert result.message is not None
        session.close()


# ══════════════════════════════════════════════════════════════════════
# E. ESCALATE_TO_HUMAN blocked
# ══════════════════════════════════════════════════════════════════════


class TestEscalateBlocked:
    def test_escalate_not_consumed(self, seeded_session) -> None:
        disposition_msg_id = _seed_disposition_message(
            seeded_session(),
            disposition_type="ESCALATE_TO_HUMAN",
            disposition_reason="high_review_risk_requires_human_escalation",
            verdict="no_blocking_findings",
            risk_level="high",
            escalation_triggers=["high_review_risk"],
        )
        svc, _, session = _make_service(seeded_session)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert result.result.preflight_status == "blocked"
        assert "disposition_type_escalation_unhandled" in result.result.blocked_reasons
        assert result.message is None
        session.close()


# ══════════════════════════════════════════════════════════════════════
# F. Fingerprint and direct binding
# ══════════════════════════════════════════════════════════════════════


class TestFingerprintAndBinding:
    def test_fingerprint_tampering(self, seeded_session) -> None:
        disposition_msg_id = _seed_disposition_message(
            seeded_session(),
            review_result_fingerprint_override="b" * 64,
        )
        svc, _, session = _make_service(seeded_session)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert result.result.preflight_status == "blocked"
        assert "review_result_fingerprint_mismatch" in result.result.blocked_reasons
        assert result.message is None
        session.close()

    def test_source_diff_sha256_tampering(self, seeded_session) -> None:
        disposition_msg_id = _seed_disposition_message(
            seeded_session(),
            source_diff_sha256=hashlib.sha256(b"tampered").hexdigest(),
            resync_review_message=False,
        )
        svc, _, session = _make_service(seeded_session)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert result.result.preflight_status == "blocked"
        reasons = result.result.blocked_reasons
        assert "disposition_source_binding_mismatch" in reasons
        session.close()

    def test_review_prompt_sha256_tampering(self, seeded_session) -> None:
        disposition_msg_id = _seed_disposition_message(
            seeded_session(),
            review_prompt_sha256=hashlib.sha256(b"tampered").hexdigest(),
            resync_review_message=False,
        )
        svc, _, session = _make_service(seeded_session)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert result.result.preflight_status == "blocked"
        assert "disposition_source_binding_mismatch" in result.result.blocked_reasons
        session.close()

    def test_review_scope_paths_tampering(self, seeded_session) -> None:
        disposition_msg_id = _seed_disposition_message(
            seeded_session(),
            review_scope_paths=["src/tampered.py"],
            resync_review_message=False,
        )
        svc, _, session = _make_service(seeded_session)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert result.result.preflight_status == "blocked"
        assert "disposition_source_binding_mismatch" in result.result.blocked_reasons
        session.close()

    def test_source_preflight_message_id_tampering(self, seeded_session) -> None:
        disposition_msg_id = _seed_disposition_message(
            seeded_session(),
            source_preflight_msg_id=uuid4(),
        )
        svc, _, session = _make_service(seeded_session)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert result.result.preflight_status == "blocked"
        assert "disposition_source_binding_mismatch" in result.result.blocked_reasons
        session.close()


# ══════════════════════════════════════════════════════════════════════
# G. P21-C source evidence tampering
# ══════════════════════════════════════════════════════════════════════


class TestSourceEvidenceTampering:
    def test_tampered_review_verdict(self, seeded_session) -> None:
        sess = seeded_session()
        row = sess.get(ProjectDirectorMessageTable, SOURCE_REVIEW_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["verdict"] = "changes_required"
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()

        disposition_msg_id = _seed_disposition_message(seeded_session())
        svc, _, session = _make_service(seeded_session)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert result.result.preflight_status == "blocked"
        assert result.message is None
        session.close()


# ══════════════════════════════════════════════════════════════════════
# H. Trigger contract
# ══════════════════════════════════════════════════════════════════════


class TestTriggerContract:
    def test_auto_continue_triggers_empty(self, seeded_session) -> None:
        disposition_msg_id = _seed_disposition_message(seeded_session())
        svc, _, session = _make_service(seeded_session)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert result.result.preflight_status == "ready"
        session.close()

    def test_escalate_triggers_present(self, seeded_session) -> None:
        disposition_msg_id = _seed_disposition_message(
            seeded_session(),
            disposition_type="ESCALATE_TO_HUMAN",
            disposition_reason="high_review_risk_requires_human_escalation",
            risk_level="high",
            escalation_triggers=["high_review_risk"],
        )
        svc, _, session = _make_service(seeded_session)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert result.result.preflight_status == "blocked"
        assert "disposition_type_escalation_unhandled" in result.result.blocked_reasons
        session.close()

    def test_trigger_contract_tampering(self, seeded_session) -> None:
        disposition_msg_id = uuid4()
        sess = seeded_session()
        action = {
            "type": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_ACTION_TYPE,
            "schema_version": REVIEW_DISPOSITION_SCHEMA_VERSION,
            "disposition_status": "computed",
            "session_id": str(SESSION_ID),
            "source_task_id": str(TASK_ID),
            "source_review_message_id": str(SOURCE_REVIEW_MSG_ID),
            "source_preflight_message_id": str(PREFLIGHT_MSG_ID),
            "source_diff_message_id": str(DIFF_MSG_ID),
            "requested_reviewer_executor": "codex",
            "source_diff_sha256": _TRUE_HEX_SHA256,
            "review_prompt_sha256": _PROMPT_SHA256,
            "review_scope_paths": ["src/example.py"],
            "review_output_schema_version": REVIEW_OUTPUT_SCHEMA_VERSION,
            "review_result_fingerprint": _compute_review_fingerprint(),
            "disposition_id": str(uuid4()),
            "disposition_type": "AUTO_CONTINUE",
            "disposition_reason": "review_has_no_blocking_findings",
            "source_review_verdict": "no_blocking_findings",
            "source_review_risk_level": "low",
            "escalation_triggers": [],
            "evaluated_trigger_kinds": ["wrong_trigger"],
            "deferred_trigger_kinds": list(DEFERRED_TRIGGER_KINDS),
            "actor": "system",
            "client_request_id": None,
            "disposition_created_at": datetime.now(timezone.utc).isoformat(),
        }
        for flag in _DISPOSITION_FALSE_FLAGS:
            action[flag] = False
        action["ai_project_director_total_loop"] = "Partial"
        sess.add(ProjectDirectorMessageTable(
            id=disposition_msg_id, session_id=SESSION_ID, role="assistant",
            content="tampered disposition", sequence_no=61,
            source="system",
            source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False, risk_level="high",
        ))
        sess.commit()
        sess.close()

        svc, _, session = _make_service(seeded_session)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert result.result.preflight_status == "blocked"
        assert "disposition_trigger_contract_invalid" in result.result.blocked_reasons
        assert result.message is None
        session.close()


# ══════════════════════════════════════════════════════════════════════
# I. Sequential replay
# ══════════════════════════════════════════════════════════════════════


class TestSequentialReplay:
    def test_second_call_blocked(self, seeded_session) -> None:
        disposition_msg_id = _seed_disposition_message(seeded_session())
        svc, _, session = _make_service(seeded_session)
        r1 = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert r1.result.preflight_status == "ready"
        session.close()

        svc2, _, session2 = _make_service(seeded_session)
        r2 = svc2.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert r2.result.preflight_status == "blocked"
        assert r2.result.prior_preflight_detected is True
        assert "disposition_already_preflighted" in r2.result.blocked_reasons
        assert r2.message is None
        session2.close()

    def test_only_one_ready_preflight_in_db(self, seeded_session) -> None:
        disposition_msg_id = _seed_disposition_message(seeded_session())
        svc, _, session = _make_service(seeded_session)
        svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        session.close()

        svc2, _, session2 = _make_service(seeded_session)
        svc2.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        count = session2.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd AND suggested_actions_json LIKE :pat"
            ),
            {
                "sd": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL,
                "pat": f'%"{disposition_msg_id}"%',
            },
        ).scalar()
        assert count == 1
        session2.close()


# ══════════════════════════════════════════════════════════════════════
# J. Full-session pagination
# ══════════════════════════════════════════════════════════════════════


class TestFullSessionPagination:
    def test_prior_preflight_found_beyond_first_page(self, seeded_session) -> None:
        disposition_msg_id = _seed_disposition_message(seeded_session())

        sess = seeded_session()
        for i in range(105):
            sess.add(ProjectDirectorMessageTable(
                id=uuid4(), session_id=SESSION_ID, role="assistant",
                content=f"filler {i}", sequence_no=1000 + i,
                source="system", source_detail="filler",
            ))
        sess.commit()
        sess.close()

        svc1, _, s1 = _make_service(seeded_session)
        r1 = svc1.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert r1.result.preflight_status == "ready"
        s1.close()

        svc2, _, s2 = _make_service(seeded_session)
        r2 = svc2.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert r2.result.preflight_status == "blocked"
        assert "disposition_already_preflighted" in r2.result.blocked_reasons
        s2.close()


# ══════════════════════════════════════════════════════════════════════
# K. Real concurrent competition
# ══════════════════════════════════════════════════════════════════════


class TestConcurrentCompetition:
    def test_two_threads_one_ready_one_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        seed_session = SessionLocal()
        _seed_base_records(seed_session)
        _seed_pd_session(seed_session)
        _seed_review_message(seed_session)
        disposition_msg_id = _seed_disposition_message(seed_session)
        seed_session.close()

        results: list[str] = []
        errors: list[str] = []
        lock = threading.Lock()

        def worker(thread_id: int):
            session = SessionLocal()
            msg_repo = ProjectDirectorMessageRepository(session)
            sess_repo = ProjectDirectorSessionRepository(session)
            svc = ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightService(
                session_repository=sess_repo,
                message_repository=msg_repo,
            )
            try:
                result = svc.prepare_candidate_diff_review_disposition_consumption(
                    session_id=SESSION_ID,
                    source_task_id=TASK_ID,
                    source_message_id=disposition_msg_id,
                )
                with lock:
                    results.append(result.result.preflight_status)
            except Exception as e:
                with lock:
                    errors.append(f"thread-{thread_id}:{type(e).__name__}:{e}")
            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(worker, i) for i in range(2)]
            for f in as_completed(futures, timeout=30):
                f.result()

        assert len(errors) == 0, f"Unexpected errors: {errors}"
        assert len(results) == 2
        assert "ready" in results
        assert "blocked" in results

        verify_session = SessionLocal()
        count = verify_session.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd AND suggested_actions_json LIKE :pat"
            ),
            {
                "sd": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL,
                "pat": f'%"{disposition_msg_id}"%',
            },
        ).scalar()
        assert count == 1

        verify_session.execute(text("BEGIN IMMEDIATE"))
        verify_session.commit()
        verify_session.close()

    def test_concurrent_different_dispositions_both_ready(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        seed_session = SessionLocal()
        _seed_base_records(seed_session)
        _seed_pd_session(seed_session)
        _seed_review_message(seed_session)
        disp_id_a = _seed_disposition_message(seed_session)
        disp_id_b = _seed_disposition_message(seed_session)
        seed_session.close()

        results: dict[str, str] = {}

        def worker(label: str, disp_id: UUID):
            session = SessionLocal()
            msg_repo = ProjectDirectorMessageRepository(session)
            sess_repo = ProjectDirectorSessionRepository(session)
            svc = ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightService(
                session_repository=sess_repo,
                message_repository=msg_repo,
            )
            result = svc.prepare_candidate_diff_review_disposition_consumption(
                session_id=SESSION_ID, source_task_id=TASK_ID,
                source_message_id=disp_id,
            )
            results[label] = result.result.preflight_status
            session.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(worker, "a", disp_id_a),
                executor.submit(worker, "b", disp_id_b),
            ]
            for f in as_completed(futures, timeout=20):
                f.result()

        assert results["a"] == "ready"
        assert results["b"] == "ready"


# ══════════════════════════════════════════════════════════════════════
# L. Append-only ready persistence
# ══════════════════════════════════════════════════════════════════════


class TestAppendOnlyPersistence:
    def test_ready_message_contract(self, seeded_session) -> None:
        disposition_msg_id = _seed_disposition_message(seeded_session())
        svc, _, session = _make_service(seeded_session)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert result.message is not None
        msg = result.message
        assert msg.source_detail == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL
        assert msg.requires_confirmation is False
        assert msg.source == ProjectDirectorMessageSource.SYSTEM
        assert msg.related_task_id == TASK_ID
        assert msg.session_id == SESSION_ID

        action = msg.suggested_actions[0]
        assert action["type"] == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_ACTION_TYPE
        assert action["schema_version"] == DISPOSITION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION
        assert action["session_id"] == str(SESSION_ID)
        assert action["source_task_id"] == str(TASK_ID)
        assert action["source_disposition_message_id"] == str(disposition_msg_id)
        assert action["source_review_message_id"] == str(SOURCE_REVIEW_MSG_ID)
        assert action["source_preflight_message_id"] == str(PREFLIGHT_MSG_ID)
        assert action["source_diff_message_id"] == str(DIFF_MSG_ID)
        assert action["disposition_type"] == "AUTO_CONTINUE"
        assert action["review_result_fingerprint"] != ""
        assert action["revalidated_review_result_fingerprint"] != ""
        assert action["review_result_fingerprint"] == action["revalidated_review_result_fingerprint"]
        assert action["continuation_eligible"] is True
        assert action["rework_eligible"] is False
        assert action["replay_check_completed"] is True
        assert action["prior_preflight_detected"] is False
        session.close()


# ══════════════════════════════════════════════════════════════════════
# M. No-side-effect evidence
# ══════════════════════════════════════════════════════════════════════


class TestNoSideEffectEvidence:
    def _assert_no_side_effects(self, action: dict) -> None:
        for flag in _DISPOSITION_FALSE_FLAGS:
            assert action.get(flag) is False, f"{flag} should be False"
        assert action["ai_project_director_total_loop"] == "Partial"

    def test_auto_continue_no_side_effects(self, seeded_session) -> None:
        disposition_msg_id = _seed_disposition_message(seeded_session())
        svc, _, session = _make_service(seeded_session)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        action = result.message.suggested_actions[0]
        self._assert_no_side_effects(action)
        assert action["continuation_eligible"] is True
        assert action["continuation_started"] is False
        session.close()

    def test_auto_rework_no_side_effects(self, seeded_session) -> None:
        disposition_msg_id = _seed_disposition_message(
            seeded_session(),
            disposition_type="AUTO_REWORK",
            disposition_reason="review_changes_required_within_automatic_rework_boundary",
            verdict="changes_required",
            risk_level="medium",
        )
        svc, _, session = _make_service(seeded_session)
        result = svc.prepare_candidate_diff_review_disposition_consumption(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        action = result.message.suggested_actions[0]
        self._assert_no_side_effects(action)
        assert action["rework_eligible"] is True
        assert action["rework_started"] is False
        session.close()


# ══════════════════════════════════════════════════════════════════════
# N. Repository dependency contract
# ══════════════════════════════════════════════════════════════════════


class TestRepositoryDependency:
    def test_missing_session_repo(self, seeded_session) -> None:
        session = seeded_session()
        msg_repo = ProjectDirectorMessageRepository(session)
        svc = ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightService(
            session_repository=None,
            message_repository=msg_repo,
        )
        with pytest.raises(ValueError, match="repositories are required"):
            svc.prepare_candidate_diff_review_disposition_consumption(
                session_id=SESSION_ID, source_task_id=TASK_ID,
                source_message_id=uuid4(),
            )
        session.close()

    def test_missing_message_repo(self, seeded_session) -> None:
        session = seeded_session()
        sess_repo = ProjectDirectorSessionRepository(session)
        svc = ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightService(
            session_repository=sess_repo,
            message_repository=None,
        )
        with pytest.raises(ValueError, match="repositories are required"):
            svc.prepare_candidate_diff_review_disposition_consumption(
                session_id=SESSION_ID, source_task_id=TASK_ID,
                source_message_id=uuid4(),
            )
        session.close()
