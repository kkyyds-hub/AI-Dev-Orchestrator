"""Contract tests for P21-D-E protected transition evidence freshness service."""

from __future__ import annotations

import hashlib
import json
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

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
from app.domain.project_director_protected_transition_evidence_freshness import (
    ProjectDirectorProtectedTransitionEvidenceFreshnessResult,
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
from app.services.project_director_sandbox_candidate_diff_review_human_escalation_decision_lifecycle_service import (
    HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION,
    HUMAN_ESCALATION_DECISION_REVOCATION_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionLifecycleService,
)
from app.services.project_director_sandbox_candidate_diff_review_human_escalation_decision_consumption_service import (
    HUMAN_ESCALATION_DECISION_CONSUMPTION_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionService,
)
from app.services.project_director_protected_transition_evidence_freshness_service import (
    PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SCHEMA_VERSION,
    P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_ACTION_TYPE,
    P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SOURCE_DETAIL,
    ProjectDirectorProtectedTransitionEvidenceFreshnessService,
    RevalidatedPersistedProtectedTransitionFreshnessFingerprint,
)


# ── Constants ───────────────────────────────────────────────────────

CANDIDATE_WRITE_MSG_ID = uuid4()
_WORKSPACE_PATH = "/tmp/test-workspace-freshness"

_DIFF_TEXT = "diff content"

_E_FALSE_FLAGS = [
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


# ── Stub services for handoff and candidate diff ────────────────────


@dataclass(frozen=True, slots=True)
class _StubHandoffResult:
    review_handoff_status: str = "created"
    source_diff_verified: bool = True
    source_diff_sha256: str = ""
    review_scope_paths: list[str] = dc_field(default_factory=list)
    diff_bytes: int = 100


@dataclass(frozen=True, slots=True)
class _StubDiffEntry:
    relative_path: str = ""
    operation: str = "modified"
    target_file_path: str = "/tmp/t"
    candidate_file_path: str = "/tmp/c"
    target_file_existed: bool = True
    candidate_file_existed: bool = True
    target_file_content_read: bool = True
    candidate_file_content_read: bool = True
    unified_diff: str = ""
    diff_bytes: int = 12


@dataclass(frozen=True, slots=True)
class _StubCandidateDiffResult:
    diff_generation_status: str = "generated"
    source_candidate_write_verified: bool = True
    readonly_real_diff_generated: bool = True
    real_diff_generated: bool = True
    workspace_path: str = ""
    workspace_path_within_root: bool = True
    unified_diff_text: str = ""
    diff_entries: list[Any] = dc_field(default_factory=list)
    diff_bytes: int = 12
    diff_file_count: int = 1


class _StubHandoffService:
    """Minimal stub that returns predictable handoff results."""

    def __init__(
        self,
        *,
        diff_sha256: str = _DIFF_SHA256,
        scope_paths: list[str] | None = None,
        diff_bytes: int = 100,
    ) -> None:
        self._diff_sha256 = diff_sha256
        self._scope_paths = scope_paths or ["src/example.py"]
        self._diff_bytes = diff_bytes

    def build_candidate_diff_review_handoff_from_sources(self, **kwargs: Any) -> _StubHandoffResult:
        return _StubHandoffResult(
            source_diff_sha256=self._diff_sha256,
            review_scope_paths=list(self._scope_paths),
            diff_bytes=self._diff_bytes,
        )


class _StubCandidateDiffService:
    """Minimal stub that returns predictable diff results."""

    def __init__(
        self,
        *,
        unified_diff_text: str = _DIFF_TEXT,
        workspace_path: str = _WORKSPACE_PATH,
        scope_paths: list[str] | None = None,
    ) -> None:
        self._unified_diff_text = unified_diff_text
        self._workspace_path = workspace_path
        self._scope_paths = scope_paths or ["src/example.py"]

    def build_candidate_diff_from_sources(self, **kwargs: Any) -> _StubCandidateDiffResult:
        entries = [
            _StubDiffEntry(relative_path=p, unified_diff=self._unified_diff_text)
            for p in self._scope_paths
        ]
        return _StubCandidateDiffResult(
            workspace_path=self._workspace_path,
            workspace_path_within_root=True,
            unified_diff_text=self._unified_diff_text,
            diff_entries=entries,
            diff_bytes=len(self._unified_diff_text.encode("utf-8")),
            diff_file_count=len(self._scope_paths),
        )


# ── Seed helpers for additional messages ─────────────────────────────


def _seed_candidate_write_message(
    session: Session,
    *,
    msg_id: UUID | None = None,
    seq_no: int = 30,
) -> UUID:
    msg_id = msg_id or CANDIDATE_WRITE_MSG_ID
    action: dict[str, Any] = {
        "type": "p21_c_sandbox_candidate_files_write_record",
        "session_id": str(SESSION_ID),
        "source_task_id": str(TASK_ID),
        "workspace_path": _WORKSPACE_PATH,
    }
    session.add(
        ProjectDirectorMessageTable(
            id=msg_id,
            session_id=SESSION_ID,
            role="assistant",
            content="Candidate files written to sandbox workspace.",
            sequence_no=seq_no,
            intent="sandbox_candidate_files_write",
            source="system",
            source_detail="p21_c_sandbox_candidate_files_write_executed",
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False,
            risk_level="high",
            related_project_id=PROJECT_ID,
            related_task_id=TASK_ID,
        )
    )
    session.commit()
    return msg_id


def _seed_diff_message(
    session: Session,
    *,
    msg_id: UUID | None = None,
    seq_no: int = 35,
) -> UUID:
    msg_id = msg_id or DIFF_MSG_ID
    action: dict[str, Any] = {
        "type": "p21_c_sandbox_candidate_diff_generate_record",
        "session_id": str(SESSION_ID),
        "source_task_id": str(TASK_ID),
        "source_message_id": str(CANDIDATE_WRITE_MSG_ID),
        "workspace_path": _WORKSPACE_PATH,
    }
    session.add(
        ProjectDirectorMessageTable(
            id=msg_id,
            session_id=SESSION_ID,
            role="assistant",
            content="Readonly unified diff generated.",
            sequence_no=seq_no,
            intent="sandbox_candidate_diff",
            source="system",
            source_detail="p21_c_sandbox_candidate_diff_generated",
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False,
            risk_level="high",
            related_project_id=PROJECT_ID,
            related_task_id=TASK_ID,
        )
    )
    session.commit()
    return msg_id


def _seed_filler_messages(
    session: Session, start_seq: int, count: int = 105
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


# ── Service helpers ─────────────────────────────────────────────────


def _make_d2_service(session_local: Any) -> tuple[Any, Any]:
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


def _make_d3_service(session_local: Any) -> tuple[Any, Any]:
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


def _make_d4_service(session_local: Any) -> tuple[Any, Any]:
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


def _make_e_service(
    session_local: Any,
    *,
    handoff_service: Any = None,
    candidate_diff_service: Any = None,
) -> tuple[Any, Any]:
    session = session_local()
    msg_repo = ProjectDirectorMessageRepository(session)
    sess_repo = ProjectDirectorSessionRepository(session)
    task_repo = TaskRepository(session)
    svc = ProjectDirectorProtectedTransitionEvidenceFreshnessService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        review_handoff_service=handoff_service or _StubHandoffService(),
        candidate_diff_service=candidate_diff_service or _StubCandidateDiffService(),
    )
    return svc, session


def _seed_full_human_chain(
    session_local: Any,
    *,
    decision_action: str = "APPROVE_CONTINUE",
) -> UUID:
    """Seed D1->D2->D3->D4 and return the D4 consumption message ID."""
    session = session_local()
    _seed_base_records(session)
    _seed_candidate_write_message(session, seq_no=30)
    _seed_diff_message(session, seq_no=35)
    _seed_review_message(session, seq_no=50)
    _seed_disposition_message(session, seq_no=60)
    session.close()

    # D1: package
    pkg_msg_id, _ = _d1_prepare(session_local)

    # D2: decision
    d2_svc, d2_sess = _make_d2_service(session_local)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    d2_result = d2_svc.record_human_escalation_decision(
        session_id=SESSION_ID,
        source_task_id=TASK_ID,
        source_message_id=pkg_msg_id,
        decision_action=decision_action,
        actor="human tester",
        client_request_id="test-request-001",
        decision_expires_at=expires_at,
    )
    assert d2_result.result.decision_status == "recorded", (
        f"D2 blocked: {d2_result.result.blocked_reasons}"
    )
    decision_msg_id = d2_result.message.id
    d2_sess.close()

    # D3: consumption preflight
    d3_svc, d3_sess = _make_d3_service(session_local)
    d3_result = d3_svc.prepare_human_escalation_decision_consumption_preflight(
        session_id=SESSION_ID,
        source_task_id=TASK_ID,
        source_message_id=decision_msg_id,
    )
    assert d3_result.result.preflight_status == "ready", (
        f"D3 blocked: {d3_result.result.blocked_reasons}"
    )
    preflight_d3_msg_id = d3_result.message.id
    d3_sess.close()

    # D4: consumption
    d4_svc, d4_sess = _make_d4_service(session_local)
    d4_result = d4_svc.consume_human_escalation_decision(
        session_id=SESSION_ID,
        source_task_id=TASK_ID,
        source_message_id=preflight_d3_msg_id,
    )
    assert d4_result.result.consumption_status == "consumed", (
        f"D4 blocked: {d4_result.result.blocked_reasons}"
    )
    consumption_msg_id = d4_result.message.id
    d4_sess.close()

    # E requires requires_confirmation=False on the D1 package message,
    # but D1 creates it with True. Update after D2 validated it.
    fix_sess = session_local()
    pkg_row = fix_sess.get(ProjectDirectorMessageTable, pkg_msg_id)
    if pkg_row is not None:
        pkg_row.requires_confirmation = False
        fix_sess.commit()
    fix_sess.close()

    return consumption_msg_id


# ── Domain model helpers ────────────────────────────────────────────


def _sha() -> str:
    return hashlib.sha256(b"valid_freshness_fp").hexdigest()


def _valid_blocked_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = dict(
        freshness_status="blocked",
        source_transition_message_id=uuid4(),
        source_task_id=uuid4(),
        blocked_reasons=["some_reason"],
    )
    kwargs.update(overrides)
    return kwargs


def _valid_ready_human_kwargs(
    *,
    kind: str = "CONTINUE_GUARDRAIL",
    **overrides: Any,
) -> dict[str, Any]:
    sha = _sha()
    now = datetime.now(timezone.utc)
    is_continue = kind == "CONTINUE_GUARDRAIL"
    kwargs: dict[str, Any] = dict(
        freshness_status="ready",
        freshness_validation_id=uuid4(),
        source_transition_message_id=uuid4(),
        source_transition_record_id=uuid4(),
        source_task_id=uuid4(),
        transition_authority="HUMAN_ESCALATION_DECISION",
        transition_kind=kind,
        validated_at=now,
        source_review_message_id=uuid4(),
        source_diff_message_id=uuid4(),
        review_result_fingerprint=sha,
        revalidated_review_result_fingerprint=sha,
        reviewed_diff_sha256=sha,
        persisted_source_diff_sha256=sha,
        current_diff_sha256=sha,
        reviewed_scope_paths=["src/example.py"],
        persisted_source_scope_paths=["src/example.py"],
        current_scope_paths=["src/example.py"],
        workspace_path="/tmp/test",
        workspace_path_within_root=True,
        aggregate_evidence_fingerprint=sha,
        revalidated_aggregate_evidence_fingerprint=sha,
        decision_confirmation_fingerprint=sha,
        revalidated_decision_confirmation_fingerprint=sha,
        decision_consumption_evidence_fingerprint=sha,
        revalidated_decision_consumption_evidence_fingerprint=sha,
        source_transition_validated=True,
        source_review_validated=True,
        review_result_fingerprint_revalidated=True,
        source_diff_revalidated=True,
        current_workspace_revalidated=True,
        current_diff_regenerated=True,
        ordered_scope_revalidated=True,
        aggregate_evidence_fingerprint_revalidated=True,
        decision_fingerprint_revalidated=True,
        decision_consumption_fingerprint_revalidated=True,
        decision_not_expired_at_freshness_check=True,
        decision_not_revoked_after_consumption=True,
        single_decision_consumption_validated=True,
        evidence_fresh=True,
        replay_check_completed=True,
        prior_freshness_validation_detected=False,
        continuation_guardrail_eligible=is_continue,
        bounded_rework_guardrail_eligible=not is_continue,
        gate_allows_protected_transition_guardrail=True,
        gate_allows_write=False,
        blocked_reasons=[],
        freshness_evidence_fingerprint=sha,
        source_human_consumption_message_id=uuid4(),
        human_consumption_id=uuid4(),
        source_decision_message_id=uuid4(),
        decision_id=uuid4(),
        source_package_message_id=uuid4(),
        escalation_package_id=uuid4(),
        decision_action="APPROVE_CONTINUE" if is_continue else "REQUEST_REWORK",
        decision_expires_at=now + timedelta(hours=1),
    )
    kwargs.update(overrides)
    return kwargs


def _valid_ready_auto_kwargs(
    *,
    kind: str = "CONTINUE_GUARDRAIL",
    **overrides: Any,
) -> dict[str, Any]:
    sha = _sha()
    now = datetime.now(timezone.utc)
    is_continue = kind == "CONTINUE_GUARDRAIL"
    kwargs: dict[str, Any] = dict(
        freshness_status="ready",
        freshness_validation_id=uuid4(),
        source_transition_message_id=uuid4(),
        source_transition_record_id=uuid4(),
        source_task_id=uuid4(),
        transition_authority="AUTOMATED_DISPOSITION",
        transition_kind=kind,
        validated_at=now,
        source_handoff_message_id=uuid4(),
        handoff_id=uuid4(),
        source_disposition_consumption_message_id=uuid4(),
        disposition_consumption_id=uuid4(),
        source_disposition_message_id=uuid4(),
        disposition_id=uuid4(),
        disposition_type="AUTO_CONTINUE" if is_continue else "AUTO_REWORK",
        source_review_message_id=uuid4(),
        source_diff_message_id=uuid4(),
        review_result_fingerprint=sha,
        revalidated_review_result_fingerprint=sha,
        reviewed_diff_sha256=sha,
        persisted_source_diff_sha256=sha,
        current_diff_sha256=sha,
        reviewed_scope_paths=["src/example.py"],
        persisted_source_scope_paths=["src/example.py"],
        current_scope_paths=["src/example.py"],
        workspace_path="/tmp/test",
        workspace_path_within_root=True,
        source_transition_validated=True,
        source_review_validated=True,
        review_result_fingerprint_revalidated=True,
        source_diff_revalidated=True,
        current_workspace_revalidated=True,
        current_diff_regenerated=True,
        ordered_scope_revalidated=True,
        evidence_fresh=True,
        replay_check_completed=True,
        prior_freshness_validation_detected=False,
        continuation_guardrail_eligible=is_continue,
        bounded_rework_guardrail_eligible=not is_continue,
        gate_allows_protected_transition_guardrail=True,
        gate_allows_write=False,
        blocked_reasons=[],
        freshness_evidence_fingerprint=sha,
    )
    kwargs.update(overrides)
    return kwargs


def _valid_freshness_action_human(
    *,
    kind: str = "CONTINUE_GUARDRAIL",
    **overrides: Any,
) -> dict[str, Any]:
    """Build a valid E action dict for the human path fingerprint revalidation."""
    sha = _sha()
    now = datetime.now(timezone.utc)
    is_continue = kind == "CONTINUE_GUARDRAIL"
    action: dict[str, Any] = {
        "type": P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_ACTION_TYPE,
        "schema_version": PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SCHEMA_VERSION,
        "session_id": str(SESSION_ID),
        "source_task_id": str(TASK_ID),
        "freshness_status": "ready",
        "freshness_validation_id": str(uuid4()),
        "source_transition_message_id": str(uuid4()),
        "source_transition_record_id": str(uuid4()),
        "transition_authority": "HUMAN_ESCALATION_DECISION",
        "transition_kind": kind,
        "validated_at": now.isoformat(),
        "source_handoff_message_id": None,
        "handoff_id": None,
        "source_disposition_consumption_message_id": None,
        "disposition_consumption_id": None,
        "source_disposition_message_id": None,
        "disposition_id": None,
        "disposition_type": None,
        "source_human_consumption_message_id": str(uuid4()),
        "human_consumption_id": str(uuid4()),
        "source_decision_message_id": str(uuid4()),
        "decision_id": str(uuid4()),
        "source_package_message_id": str(uuid4()),
        "escalation_package_id": str(uuid4()),
        "decision_action": "APPROVE_CONTINUE" if is_continue else "REQUEST_REWORK",
        "decision_expires_at": (now + timedelta(hours=1)).isoformat(),
        "source_review_message_id": str(uuid4()),
        "source_diff_message_id": str(uuid4()),
        "review_result_fingerprint": sha,
        "revalidated_review_result_fingerprint": sha,
        "reviewed_diff_sha256": sha,
        "persisted_source_diff_sha256": sha,
        "current_diff_sha256": sha,
        "reviewed_scope_paths": ["src/example.py"],
        "persisted_source_scope_paths": ["src/example.py"],
        "current_scope_paths": ["src/example.py"],
        "workspace_path": "/tmp/test",
        "workspace_path_within_root": True,
        "aggregate_evidence_fingerprint": sha,
        "revalidated_aggregate_evidence_fingerprint": sha,
        "decision_confirmation_fingerprint": sha,
        "revalidated_decision_confirmation_fingerprint": sha,
        "decision_consumption_evidence_fingerprint": sha,
        "revalidated_decision_consumption_evidence_fingerprint": sha,
        "source_transition_validated": True,
        "source_review_validated": True,
        "review_result_fingerprint_revalidated": True,
        "source_diff_revalidated": True,
        "current_workspace_revalidated": True,
        "current_diff_regenerated": True,
        "ordered_scope_revalidated": True,
        "aggregate_evidence_fingerprint_revalidated": True,
        "decision_fingerprint_revalidated": True,
        "decision_consumption_fingerprint_revalidated": True,
        "decision_not_expired_at_freshness_check": True,
        "decision_not_revoked_after_consumption": True,
        "single_decision_consumption_validated": True,
        "evidence_fresh": True,
        "replay_check_completed": True,
        "prior_freshness_validation_detected": False,
        "continuation_guardrail_eligible": is_continue,
        "bounded_rework_guardrail_eligible": not is_continue,
        "gate_allows_protected_transition_guardrail": True,
        "gate_allows_write": False,
        "blocked_reasons": [],
        "freshness_evidence_fingerprint": sha,
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
        "ai_project_director_total_loop": "Partial",
    }
    action.update(overrides)
    return action


def _valid_freshness_action_auto(
    *,
    kind: str = "CONTINUE_GUARDRAIL",
    **overrides: Any,
) -> dict[str, Any]:
    """Build a valid E action dict for the automatic path fingerprint revalidation."""
    sha = _sha()
    now = datetime.now(timezone.utc)
    is_continue = kind == "CONTINUE_GUARDRAIL"
    action: dict[str, Any] = {
        "type": P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_ACTION_TYPE,
        "schema_version": PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SCHEMA_VERSION,
        "session_id": str(SESSION_ID),
        "source_task_id": str(TASK_ID),
        "freshness_status": "ready",
        "freshness_validation_id": str(uuid4()),
        "source_transition_message_id": str(uuid4()),
        "source_transition_record_id": str(uuid4()),
        "transition_authority": "AUTOMATED_DISPOSITION",
        "transition_kind": kind,
        "validated_at": now.isoformat(),
        "source_handoff_message_id": str(uuid4()),
        "handoff_id": str(uuid4()),
        "source_disposition_consumption_message_id": str(uuid4()),
        "disposition_consumption_id": str(uuid4()),
        "source_disposition_message_id": str(uuid4()),
        "disposition_id": str(uuid4()),
        "disposition_type": "AUTO_CONTINUE" if is_continue else "AUTO_REWORK",
        "source_human_consumption_message_id": None,
        "human_consumption_id": None,
        "source_decision_message_id": None,
        "decision_id": None,
        "source_package_message_id": None,
        "escalation_package_id": None,
        "decision_action": None,
        "decision_expires_at": None,
        "source_review_message_id": str(uuid4()),
        "source_diff_message_id": str(uuid4()),
        "review_result_fingerprint": sha,
        "revalidated_review_result_fingerprint": sha,
        "reviewed_diff_sha256": sha,
        "persisted_source_diff_sha256": sha,
        "current_diff_sha256": sha,
        "reviewed_scope_paths": ["src/example.py"],
        "persisted_source_scope_paths": ["src/example.py"],
        "current_scope_paths": ["src/example.py"],
        "workspace_path": "/tmp/test",
        "workspace_path_within_root": True,
        "aggregate_evidence_fingerprint": "",
        "revalidated_aggregate_evidence_fingerprint": "",
        "decision_confirmation_fingerprint": "",
        "revalidated_decision_confirmation_fingerprint": "",
        "decision_consumption_evidence_fingerprint": "",
        "revalidated_decision_consumption_evidence_fingerprint": "",
        "source_transition_validated": True,
        "source_review_validated": True,
        "review_result_fingerprint_revalidated": True,
        "source_diff_revalidated": True,
        "current_workspace_revalidated": True,
        "current_diff_regenerated": True,
        "ordered_scope_revalidated": True,
        "aggregate_evidence_fingerprint_revalidated": False,
        "decision_fingerprint_revalidated": False,
        "decision_consumption_fingerprint_revalidated": False,
        "decision_not_expired_at_freshness_check": False,
        "decision_not_revoked_after_consumption": False,
        "single_decision_consumption_validated": False,
        "evidence_fresh": True,
        "replay_check_completed": True,
        "prior_freshness_validation_detected": False,
        "continuation_guardrail_eligible": is_continue,
        "bounded_rework_guardrail_eligible": not is_continue,
        "gate_allows_protected_transition_guardrail": True,
        "gate_allows_write": False,
        "blocked_reasons": [],
        "freshness_evidence_fingerprint": sha,
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
        "ai_project_director_total_loop": "Partial",
    }
    action.update(overrides)
    return action


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def db_engine(tmp_path: Any) -> Any:
    db_path = str(tmp_path / "test.db")
    engine = _make_test_engine(db_path)
    yield engine
    engine.dispose()


@pytest.fixture()
def seeded_session(db_engine: Any) -> Any:
    SessionLocal = _make_session_factory(db_engine)
    session = SessionLocal()
    _seed_base_records(session)
    _seed_candidate_write_message(session, seq_no=30)
    _seed_diff_message(session, seq_no=35)
    _seed_review_message(session, seq_no=50)
    _seed_disposition_message(session, seq_no=60)
    session.close()
    return SessionLocal


# ══════════════════════════════════════════════════════════════════════
# 1. TestConstants
# ══════════════════════════════════════════════════════════════════════


class TestConstants:
    def test_source_detail(self) -> None:
        assert (
            P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SOURCE_DETAIL
            == "p21_d_protected_transition_evidence_freshness_validated"
        )

    def test_action_type(self) -> None:
        assert (
            P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_ACTION_TYPE
            == "p21_d_protected_transition_evidence_freshness_record"
        )

    def test_schema_version(self) -> None:
        assert PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SCHEMA_VERSION == "p21-d-e.v1"


# ══════════════════════════════════════════════════════════════════════
# 2. TestDomainBlockedContract
# ══════════════════════════════════════════════════════════════════════


class TestDomainBlockedContract:
    def test_blocked_requires_reasons(self) -> None:
        with pytest.raises(ValueError, match="blocked freshness gate requires a reason"):
            ProjectDirectorProtectedTransitionEvidenceFreshnessResult(
                **_valid_blocked_kwargs(blocked_reasons=[])
            )

    def test_blocked_no_freshness_validation_id(self) -> None:
        with pytest.raises(
            ValueError, match="blocked freshness gate may not create a record"
        ):
            ProjectDirectorProtectedTransitionEvidenceFreshnessResult(
                **_valid_blocked_kwargs(freshness_validation_id=uuid4())
            )

    def test_blocked_no_gate_allows_protected_transition_guardrail(self) -> None:
        with pytest.raises(
            ValueError, match="blocked freshness gate may not allow transition"
        ):
            ProjectDirectorProtectedTransitionEvidenceFreshnessResult(
                **_valid_blocked_kwargs(gate_allows_protected_transition_guardrail=True)
            )


# ══════════════════════════════════════════════════════════════════════
# 3. TestDomainReadyContract
# ══════════════════════════════════════════════════════════════════════


class TestDomainReadyContract:
    def test_valid_ready_human_continue(self) -> None:
        result = ProjectDirectorProtectedTransitionEvidenceFreshnessResult(
            **_valid_ready_human_kwargs(kind="CONTINUE_GUARDRAIL")
        )
        assert result.freshness_status == "ready"
        assert result.transition_authority == "HUMAN_ESCALATION_DECISION"
        assert result.transition_kind == "CONTINUE_GUARDRAIL"
        assert result.continuation_guardrail_eligible is True
        assert result.bounded_rework_guardrail_eligible is False
        assert result.gate_allows_protected_transition_guardrail is True

    def test_valid_ready_human_rework(self) -> None:
        result = ProjectDirectorProtectedTransitionEvidenceFreshnessResult(
            **_valid_ready_human_kwargs(kind="BOUNDED_REWORK_GUARDRAIL")
        )
        assert result.transition_kind == "BOUNDED_REWORK_GUARDRAIL"
        assert result.continuation_guardrail_eligible is False
        assert result.bounded_rework_guardrail_eligible is True

    def test_valid_ready_auto_continue(self) -> None:
        result = ProjectDirectorProtectedTransitionEvidenceFreshnessResult(
            **_valid_ready_auto_kwargs(kind="CONTINUE_GUARDRAIL")
        )
        assert result.transition_authority == "AUTOMATED_DISPOSITION"
        assert result.transition_kind == "CONTINUE_GUARDRAIL"

    def test_valid_ready_auto_rework(self) -> None:
        result = ProjectDirectorProtectedTransitionEvidenceFreshnessResult(
            **_valid_ready_auto_kwargs(kind="BOUNDED_REWORK_GUARDRAIL")
        )
        assert result.transition_authority == "AUTOMATED_DISPOSITION"
        assert result.transition_kind == "BOUNDED_REWORK_GUARDRAIL"

    def test_ready_requires_identity_fields(self) -> None:
        for field in [
            "freshness_validation_id",
            "source_transition_record_id",
            "transition_authority",
            "transition_kind",
            "validated_at",
            "source_review_message_id",
            "source_diff_message_id",
        ]:
            kwargs = _valid_ready_human_kwargs(**{field: None})
            with pytest.raises(ValueError, match="ready freshness gate requires"):
                ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)

    def test_ready_requires_revalidation_booleans(self) -> None:
        for field in [
            "source_transition_validated",
            "source_review_validated",
            "review_result_fingerprint_revalidated",
            "source_diff_revalidated",
            "current_workspace_revalidated",
            "current_diff_regenerated",
            "ordered_scope_revalidated",
            "evidence_fresh",
            "replay_check_completed",
            "gate_allows_protected_transition_guardrail",
            "workspace_path_within_root",
        ]:
            kwargs = _valid_ready_human_kwargs(**{field: False})
            with pytest.raises(ValueError, match="complete revalidation"):
                ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)

    def test_ready_requires_review_fingerprint(self) -> None:
        kwargs = _valid_ready_human_kwargs(review_result_fingerprint="invalid")
        with pytest.raises(ValueError, match="review fingerprint"):
            ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)

    def test_ready_requires_matching_review_fingerprints(self) -> None:
        kwargs = _valid_ready_human_kwargs(
            revalidated_review_result_fingerprint="b" * 64
        )
        with pytest.raises(ValueError, match="matching review fingerprints"):
            ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)

    def test_ready_requires_diff_fingerprints(self) -> None:
        kwargs = _valid_ready_human_kwargs(reviewed_diff_sha256="not_sha")
        with pytest.raises(ValueError, match="diff fingerprints"):
            ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)

    def test_ready_requires_matching_diff_fingerprints(self) -> None:
        kwargs = _valid_ready_human_kwargs(current_diff_sha256="b" * 64)
        with pytest.raises(ValueError, match="matching diff fingerprints"):
            ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)

    def test_ready_requires_ordered_scopes(self) -> None:
        kwargs = _valid_ready_human_kwargs(reviewed_scope_paths=[])
        with pytest.raises(ValueError, match="ordered scopes"):
            ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)

    def test_ready_requires_workspace_path(self) -> None:
        kwargs = _valid_ready_human_kwargs(workspace_path="")
        with pytest.raises(ValueError, match="workspace path"):
            ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)

    def test_ready_requires_eligibility_match(self) -> None:
        kwargs = _valid_ready_human_kwargs(
            kind="CONTINUE_GUARDRAIL",
            continuation_guardrail_eligible=False,
        )
        with pytest.raises(ValueError, match="eligibility must match"):
            ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)

    def test_ready_requires_freshness_evidence_fingerprint(self) -> None:
        kwargs = _valid_ready_human_kwargs(freshness_evidence_fingerprint="invalid")
        with pytest.raises(ValueError, match="evidence fingerprint"):
            ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)

    def test_ready_rejects_prior_detected(self) -> None:
        kwargs = _valid_ready_human_kwargs(prior_freshness_validation_detected=True)
        with pytest.raises(ValueError, match="unreplayed source"):
            ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)

    def test_ready_rejects_blocked_reasons(self) -> None:
        kwargs = _valid_ready_human_kwargs(blocked_reasons=["something"])
        with pytest.raises(ValueError, match="unreplayed source"):
            ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)

    def test_human_requires_human_identity(self) -> None:
        for field in [
            "source_human_consumption_message_id",
            "human_consumption_id",
            "source_decision_message_id",
            "decision_id",
            "source_package_message_id",
            "escalation_package_id",
            "decision_action",
            "decision_expires_at",
        ]:
            kwargs = _valid_ready_human_kwargs(**{field: None})
            with pytest.raises(ValueError, match="human freshness gate requires"):
                ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)

    def test_human_rejects_automatic_identity(self) -> None:
        uuid_fields = [
            "source_handoff_message_id",
            "handoff_id",
            "source_disposition_consumption_message_id",
            "disposition_consumption_id",
            "source_disposition_message_id",
            "disposition_id",
        ]
        for field in uuid_fields:
            kwargs = _valid_ready_human_kwargs(**{field: uuid4()})
            with pytest.raises(
                ValueError, match="human freshness gate may not forge automatic"
            ):
                ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)
        # disposition_type is a Literal; set to a valid literal that doesn't belong
        kwargs = _valid_ready_human_kwargs(disposition_type="AUTO_CONTINUE")
        with pytest.raises(
            ValueError, match="human freshness gate may not forge automatic"
        ):
            ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)

    def test_human_requires_matching_fingerprints(self) -> None:
        for stored_field, reval_field in [
            ("aggregate_evidence_fingerprint", "revalidated_aggregate_evidence_fingerprint"),
            ("decision_confirmation_fingerprint", "revalidated_decision_confirmation_fingerprint"),
            ("decision_consumption_evidence_fingerprint", "revalidated_decision_consumption_evidence_fingerprint"),
        ]:
            kwargs = _valid_ready_human_kwargs(**{reval_field: "b" * 64})
            with pytest.raises(ValueError, match="matching fingerprints"):
                ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)

    def test_human_requires_human_revalidation_flags(self) -> None:
        for field in [
            "aggregate_evidence_fingerprint_revalidated",
            "decision_fingerprint_revalidated",
            "decision_consumption_fingerprint_revalidated",
            "decision_not_expired_at_freshness_check",
            "decision_not_revoked_after_consumption",
            "single_decision_consumption_validated",
        ]:
            kwargs = _valid_ready_human_kwargs(**{field: False})
            with pytest.raises(
                ValueError, match="current decision checks"
            ):
                ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)

    def test_auto_requires_auto_identity(self) -> None:
        for field in [
            "source_handoff_message_id",
            "handoff_id",
            "source_disposition_consumption_message_id",
            "disposition_consumption_id",
            "source_disposition_message_id",
            "disposition_id",
            "disposition_type",
        ]:
            kwargs = _valid_ready_auto_kwargs(**{field: None})
            with pytest.raises(
                ValueError, match="automatic freshness gate requires"
            ):
                ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)

    def test_auto_rejects_human_identity(self) -> None:
        now = datetime.now(timezone.utc)
        uuid_fields = [
            "source_human_consumption_message_id",
            "human_consumption_id",
            "source_decision_message_id",
            "decision_id",
            "source_package_message_id",
            "escalation_package_id",
        ]
        for field in uuid_fields:
            kwargs = _valid_ready_auto_kwargs(**{field: uuid4()})
            with pytest.raises(
                ValueError, match="automatic freshness gate may not forge human identity"
            ):
                ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)
        # decision_action is a Literal; use valid literal value
        kwargs = _valid_ready_auto_kwargs(decision_action="APPROVE_CONTINUE")
        with pytest.raises(
            ValueError, match="automatic freshness gate may not forge human identity"
        ):
            ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)
        # decision_expires_at is a datetime
        kwargs = _valid_ready_auto_kwargs(decision_expires_at=now + timedelta(hours=1))
        with pytest.raises(
            ValueError, match="automatic freshness gate may not forge human identity"
        ):
            ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)

    def test_auto_rejects_human_fingerprints(self) -> None:
        sha = "a" * 64
        for field in [
            "aggregate_evidence_fingerprint",
            "revalidated_aggregate_evidence_fingerprint",
            "decision_confirmation_fingerprint",
            "revalidated_decision_confirmation_fingerprint",
            "decision_consumption_evidence_fingerprint",
            "revalidated_decision_consumption_evidence_fingerprint",
        ]:
            kwargs = _valid_ready_auto_kwargs(**{field: sha})
            with pytest.raises(
                ValueError, match="automatic freshness gate may not forge human fingerprints"
            ):
                ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)

    def test_auto_rejects_human_checks(self) -> None:
        for field in [
            "aggregate_evidence_fingerprint_revalidated",
            "decision_fingerprint_revalidated",
            "decision_consumption_fingerprint_revalidated",
            "decision_not_expired_at_freshness_check",
            "decision_not_revoked_after_consumption",
            "single_decision_consumption_validated",
        ]:
            kwargs = _valid_ready_auto_kwargs(**{field: True})
            with pytest.raises(
                ValueError, match="automatic freshness gate may not report human checks"
            ):
                ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)


# ══════════════════════════════════════════════════════════════════════
# 4. TestFalseOnlyFlags
# ══════════════════════════════════════════════════════════════════════


class TestFalseOnlyFlags:
    @pytest.mark.parametrize("flag", _E_FALSE_FLAGS)
    def test_forbidden_side_effect_flag_rejected(self, flag: str) -> None:
        kwargs = _valid_ready_human_kwargs(**{flag: True})
        with pytest.raises(ValueError, match="freshness gate may not"):
            ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)

    def test_exactly_15_false_only_fields(self) -> None:
        assert len(_E_FALSE_FLAGS) == 15

    def test_total_loop_must_be_partial(self) -> None:
        kwargs = _valid_ready_human_kwargs(ai_project_director_total_loop="Full")
        with pytest.raises(ValueError):
            ProjectDirectorProtectedTransitionEvidenceFreshnessResult(**kwargs)


# ══════════════════════════════════════════════════════════════════════
# 5. TestHumanPathSuccess
# ══════════════════════════════════════════════════════════════════════


class TestHumanPathSuccess:
    def test_approve_continue_guardrail(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        consumption_msg_id = _seed_full_human_chain(
            SessionLocal, decision_action="APPROVE_CONTINUE"
        )

        svc, session = _make_e_service(SessionLocal)
        result = svc.prepare_protected_transition_evidence_freshness_gate(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=consumption_msg_id,
        )
        assert result.result.freshness_status == "ready"
        assert result.result.transition_authority == "HUMAN_ESCALATION_DECISION"
        assert result.result.transition_kind == "CONTINUE_GUARDRAIL"
        assert result.result.continuation_guardrail_eligible is True
        assert result.result.bounded_rework_guardrail_eligible is False
        assert result.result.source_transition_validated is True
        assert result.result.source_review_validated is True
        assert result.result.review_result_fingerprint_revalidated is True
        assert result.result.source_diff_revalidated is True
        assert result.result.current_workspace_revalidated is True
        assert result.result.current_diff_regenerated is True
        assert result.result.ordered_scope_revalidated is True
        assert result.result.aggregate_evidence_fingerprint_revalidated is True
        assert result.result.decision_fingerprint_revalidated is True
        assert result.result.decision_consumption_fingerprint_revalidated is True
        assert result.result.decision_not_expired_at_freshness_check is True
        assert result.result.decision_not_revoked_after_consumption is True
        assert result.result.single_decision_consumption_validated is True
        assert result.result.evidence_fresh is True
        assert result.result.gate_allows_protected_transition_guardrail is True
        assert result.result.gate_allows_write is False
        assert result.result.blocked_reasons == []
        assert result.message is not None
        session.close()

    def test_request_rework_guardrail(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        consumption_msg_id = _seed_full_human_chain(
            SessionLocal, decision_action="REQUEST_REWORK"
        )

        svc, session = _make_e_service(SessionLocal)
        result = svc.prepare_protected_transition_evidence_freshness_gate(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=consumption_msg_id,
        )
        assert result.result.freshness_status == "ready"
        assert result.result.transition_kind == "BOUNDED_REWORK_GUARDRAIL"
        assert result.result.continuation_guardrail_eligible is False
        assert result.result.bounded_rework_guardrail_eligible is True
        assert result.result.gate_allows_protected_transition_guardrail is True
        assert result.result.gate_allows_write is False
        assert result.result.blocked_reasons == []
        assert result.message is not None
        session.close()

    def test_message_fields(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        consumption_msg_id = _seed_full_human_chain(SessionLocal)

        svc, session = _make_e_service(SessionLocal)
        result = svc.prepare_protected_transition_evidence_freshness_gate(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=consumption_msg_id,
        )
        msg = result.message
        assert msg is not None
        assert msg.session_id == SESSION_ID
        assert msg.role == ProjectDirectorMessageRole.ASSISTANT
        assert msg.source == ProjectDirectorMessageSource.SYSTEM
        assert msg.requires_confirmation is False
        assert msg.risk_level == ProjectDirectorMessageRiskLevel.HIGH
        assert msg.related_project_id == PROJECT_ID
        assert msg.related_task_id == TASK_ID
        assert msg.intent == "protected_transition_evidence_freshness"
        assert (
            msg.source_detail
            == P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SOURCE_DETAIL
        )
        assert len(msg.suggested_actions) == 1
        assert msg.created_at.tzinfo is not None

        forbidden = msg.forbidden_actions_detected
        for required in [
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
        session.close()

    def test_action_fields(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        consumption_msg_id = _seed_full_human_chain(SessionLocal)

        svc, session = _make_e_service(SessionLocal)
        result = svc.prepare_protected_transition_evidence_freshness_gate(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=consumption_msg_id,
        )
        action = result.message.suggested_actions[0]
        assert (
            action["type"]
            == P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_ACTION_TYPE
        )
        assert (
            action["schema_version"]
            == PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SCHEMA_VERSION
        )
        assert action["freshness_status"] == "ready"
        assert UUID(action["freshness_validation_id"])
        assert action["session_id"] == str(SESSION_ID)
        assert action["source_task_id"] == str(TASK_ID)
        assert action["transition_authority"] == "HUMAN_ESCALATION_DECISION"
        assert action["transition_kind"] == "CONTINUE_GUARDRAIL"
        assert action["gate_allows_protected_transition_guardrail"] is True
        assert action["gate_allows_write"] is False
        assert action["blocked_reasons"] == []
        assert action["ai_project_director_total_loop"] == "Partial"

        for flag in _E_FALSE_FLAGS:
            assert action.get(flag) is False, f"{flag} should be False"
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 6. TestRejectBlocked
# ══════════════════════════════════════════════════════════════════════


class TestRejectBlocked:
    def test_reject_has_no_protected_transition(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        consumption_msg_id = _seed_full_human_chain(
            SessionLocal, decision_action="REJECT"
        )

        svc, session = _make_e_service(SessionLocal)
        result = svc.prepare_protected_transition_evidence_freshness_gate(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=consumption_msg_id,
        )
        assert result.result.freshness_status == "blocked"
        assert (
            "terminal_rejection_has_no_protected_transition"
            in result.result.blocked_reasons
        )
        assert result.message is None
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 7. TestDependencies
# ══════════════════════════════════════════════════════════════════════


class TestDependencies:
    def test_missing_session_repo(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        session.close()
        session = SessionLocal()
        msg_repo = ProjectDirectorMessageRepository(session)
        task_repo = TaskRepository(session)
        svc = ProjectDirectorProtectedTransitionEvidenceFreshnessService(
            session_repository=None,
            message_repository=msg_repo,
            task_repository=task_repo,
            review_handoff_service=_StubHandoffService(),
            candidate_diff_service=_StubCandidateDiffService(),
        )
        with pytest.raises(ValueError, match="protected transition freshness dependencies"):
            svc.prepare_protected_transition_evidence_freshness_gate(
                session_id=SESSION_ID,
                source_task_id=TASK_ID,
                source_message_id=uuid4(),
            )
        session.close()

    def test_missing_message_repo(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        session.close()
        session = SessionLocal()
        sess_repo = ProjectDirectorSessionRepository(session)
        task_repo = TaskRepository(session)
        svc = ProjectDirectorProtectedTransitionEvidenceFreshnessService(
            session_repository=sess_repo,
            message_repository=None,
            task_repository=task_repo,
            review_handoff_service=_StubHandoffService(),
            candidate_diff_service=_StubCandidateDiffService(),
        )
        with pytest.raises(ValueError, match="protected transition freshness dependencies"):
            svc.prepare_protected_transition_evidence_freshness_gate(
                session_id=SESSION_ID,
                source_task_id=TASK_ID,
                source_message_id=uuid4(),
            )
        session.close()

    def test_missing_task_repo(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        session.close()
        session = SessionLocal()
        msg_repo = ProjectDirectorMessageRepository(session)
        sess_repo = ProjectDirectorSessionRepository(session)
        svc = ProjectDirectorProtectedTransitionEvidenceFreshnessService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=None,
            review_handoff_service=_StubHandoffService(),
            candidate_diff_service=_StubCandidateDiffService(),
        )
        with pytest.raises(ValueError, match="protected transition freshness dependencies"):
            svc.prepare_protected_transition_evidence_freshness_gate(
                session_id=SESSION_ID,
                source_task_id=TASK_ID,
                source_message_id=uuid4(),
            )
        session.close()

    def test_missing_handoff_service(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        session.close()
        session = SessionLocal()
        msg_repo = ProjectDirectorMessageRepository(session)
        sess_repo = ProjectDirectorSessionRepository(session)
        task_repo = TaskRepository(session)
        svc = ProjectDirectorProtectedTransitionEvidenceFreshnessService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
            review_handoff_service=None,
            candidate_diff_service=_StubCandidateDiffService(),
        )
        with pytest.raises(ValueError, match="protected transition freshness dependencies"):
            svc.prepare_protected_transition_evidence_freshness_gate(
                session_id=SESSION_ID,
                source_task_id=TASK_ID,
                source_message_id=uuid4(),
            )
        session.close()

    def test_missing_candidate_diff_service(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        session.close()
        session = SessionLocal()
        msg_repo = ProjectDirectorMessageRepository(session)
        sess_repo = ProjectDirectorSessionRepository(session)
        task_repo = TaskRepository(session)
        svc = ProjectDirectorProtectedTransitionEvidenceFreshnessService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
            review_handoff_service=_StubHandoffService(),
            candidate_diff_service=None,
        )
        with pytest.raises(ValueError, match="protected transition freshness dependencies"):
            svc.prepare_protected_transition_evidence_freshness_gate(
                session_id=SESSION_ID,
                source_task_id=TASK_ID,
                source_message_id=uuid4(),
            )
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 8. TestTaskProjectBinding
# ══════════════════════════════════════════════════════════════════════


class TestTaskProjectBinding:
    def test_session_missing(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        session.close()

        svc, session = _make_e_service(SessionLocal)
        result = svc.prepare_protected_transition_evidence_freshness_gate(
            session_id=uuid4(),
            source_task_id=TASK_ID,
            source_message_id=uuid4(),
        )
        assert result.result.freshness_status == "blocked"
        assert "session_missing" in result.result.blocked_reasons
        assert result.message is None
        session.close()

    def test_task_missing(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        session.close()

        svc, session = _make_e_service(SessionLocal)
        result = svc.prepare_protected_transition_evidence_freshness_gate(
            session_id=SESSION_ID,
            source_task_id=uuid4(),
            source_message_id=uuid4(),
        )
        assert result.result.freshness_status == "blocked"
        assert "source_task_missing" in result.result.blocked_reasons
        assert result.message is None
        session.close()

    def test_task_project_mismatch(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        other_project_id = uuid4()
        session.add(
            ProjectTable(
                id=other_project_id,
                name="Other",
                summary="Other project",
                status="active",
                stage="intake",
            )
        )
        session.flush()
        other_task_id = uuid4()
        session.add(
            TaskTable(
                id=other_task_id,
                project_id=other_project_id,
                title="Other task",
                status="pending",
                priority="normal",
                input_summary="OTHER",
                risk_level="normal",
                human_status="none",
                source_draft_id="p12-other",
                acceptance_criteria="[]",
            )
        )
        session.commit()
        session.close()

        svc, session = _make_e_service(SessionLocal)
        result = svc.prepare_protected_transition_evidence_freshness_gate(
            session_id=SESSION_ID,
            source_task_id=other_task_id,
            source_message_id=uuid4(),
        )
        assert result.result.freshness_status == "blocked"
        assert "source_task_project_mismatch" in result.result.blocked_reasons
        assert result.message is None
        session.close()

    def test_source_message_missing(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        session.close()

        svc, session = _make_e_service(SessionLocal)
        result = svc.prepare_protected_transition_evidence_freshness_gate(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=uuid4(),
        )
        assert result.result.freshness_status == "blocked"
        assert "source_transition_message_missing" in result.result.blocked_reasons
        assert result.message is None
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 9. TestFingerprintIsolation
# ══════════════════════════════════════════════════════════════════════


class TestFingerprintIsolation:
    """Verify each fingerprint input field changes the canonical fingerprint."""

    def _revalidate(
        self, action: dict[str, Any], session_id: UUID = SESSION_ID, source_task_id: UUID = TASK_ID
    ) -> RevalidatedPersistedProtectedTransitionFreshnessFingerprint:
        return (
            ProjectDirectorProtectedTransitionEvidenceFreshnessService
            .revalidate_persisted_protected_transition_freshness_fingerprint(
                session_id=session_id,
                source_task_id=source_task_id,
                source_freshness_message_id=uuid4(),
                source_freshness_action=action,
            )
        )

    def test_session_id_isolation(self) -> None:
        other_sid = uuid4()
        a1 = _valid_freshness_action_human()
        a2 = _valid_freshness_action_human(session_id=str(other_sid))
        fp1 = self._revalidate(a1)
        fp2 = self._revalidate(a2, session_id=other_sid)
        assert not fp1.blocked_reasons, fp1.blocked_reasons
        assert not fp2.blocked_reasons, fp2.blocked_reasons
        assert fp1.freshness_evidence_fingerprint != fp2.freshness_evidence_fingerprint

    def test_source_task_id_isolation(self) -> None:
        other_tid = uuid4()
        a1 = _valid_freshness_action_human()
        a2 = _valid_freshness_action_human(source_task_id=str(other_tid))
        fp1 = self._revalidate(a1)
        fp2 = self._revalidate(a2, source_task_id=other_tid)
        assert not fp1.blocked_reasons, fp1.blocked_reasons
        assert not fp2.blocked_reasons, fp2.blocked_reasons
        assert fp1.freshness_evidence_fingerprint != fp2.freshness_evidence_fingerprint

    @pytest.mark.parametrize(
        "label,overrides",
        [
            ("freshness_validation_id", {"freshness_validation_id": str(uuid4())}),
            ("source_transition_message_id", {"source_transition_message_id": str(uuid4())}),
            ("source_transition_record_id", {"source_transition_record_id": str(uuid4())}),
            ("source_review_message_id", {"source_review_message_id": str(uuid4())}),
            ("source_diff_message_id", {"source_diff_message_id": str(uuid4())}),
            (
                "review_fingerprint",
                {
                    "review_result_fingerprint": hashlib.sha256(b"other_rfp").hexdigest(),
                    "revalidated_review_result_fingerprint": hashlib.sha256(b"other_rfp").hexdigest(),
                },
            ),
            (
                "three_diff_sha",
                {
                    "reviewed_diff_sha256": hashlib.sha256(b"other_diff").hexdigest(),
                    "persisted_source_diff_sha256": hashlib.sha256(b"other_diff").hexdigest(),
                    "current_diff_sha256": hashlib.sha256(b"other_diff").hexdigest(),
                },
            ),
            (
                "three_scope",
                {
                    "reviewed_scope_paths": ["src/other.py"],
                    "persisted_source_scope_paths": ["src/other.py"],
                    "current_scope_paths": ["src/other.py"],
                },
            ),
            ("workspace_path", {"workspace_path": "/tmp/other"}),
            (
                "validated_at",
                {"validated_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()},
            ),
            ("source_decision_message_id", {"source_decision_message_id": str(uuid4())}),
            ("decision_id", {"decision_id": str(uuid4())}),
            ("source_package_message_id", {"source_package_message_id": str(uuid4())}),
            ("escalation_package_id", {"escalation_package_id": str(uuid4())}),
            (
                "decision_expires_at",
                {"decision_expires_at": (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()},
            ),
            (
                "aggregate_fingerprint",
                {
                    "aggregate_evidence_fingerprint": hashlib.sha256(b"other_agg").hexdigest(),
                    "revalidated_aggregate_evidence_fingerprint": hashlib.sha256(b"other_agg").hexdigest(),
                },
            ),
            (
                "decision_confirmation_fingerprint",
                {
                    "decision_confirmation_fingerprint": hashlib.sha256(b"other_dcf").hexdigest(),
                    "revalidated_decision_confirmation_fingerprint": hashlib.sha256(b"other_dcf").hexdigest(),
                },
            ),
            (
                "consumption_fingerprint",
                {
                    "decision_consumption_evidence_fingerprint": hashlib.sha256(b"other_cef").hexdigest(),
                    "revalidated_decision_consumption_evidence_fingerprint": hashlib.sha256(b"other_cef").hexdigest(),
                },
            ),
        ],
        ids=[
            "freshness_validation_id",
            "source_transition_message_id",
            "source_transition_record_id",
            "source_review_message_id",
            "source_diff_message_id",
            "review_fingerprint",
            "three_diff_sha",
            "three_scope",
            "workspace_path",
            "validated_at",
            "source_decision_message_id",
            "decision_id",
            "source_package_message_id",
            "escalation_package_id",
            "decision_expires_at",
            "aggregate_fingerprint",
            "decision_confirmation_fingerprint",
            "consumption_fingerprint",
        ],
    )
    def test_human_path_field_isolation(
        self, label: str, overrides: dict[str, Any]
    ) -> None:
        base_action = _valid_freshness_action_human()
        base_fp = self._revalidate(base_action)
        assert not base_fp.blocked_reasons, f"base blocked: {base_fp.blocked_reasons}"

        changed_action = {**base_action, **overrides}
        changed_fp = self._revalidate(changed_action)
        assert not changed_fp.blocked_reasons, f"changed blocked: {changed_fp.blocked_reasons}"

        assert base_fp.freshness_evidence_fingerprint != (
            changed_fp.freshness_evidence_fingerprint
        ), f"fingerprint not isolated for {label}"

    def test_auto_path_freshness_validation_id_isolation(self) -> None:
        """Auto-path fingerprint is isolated by freshness_validation_id."""
        base_action = _valid_freshness_action_auto()
        base_fp = self._revalidate(base_action)
        assert not base_fp.blocked_reasons, f"base blocked: {base_fp.blocked_reasons}"

        changed_action = {**base_action, "freshness_validation_id": str(uuid4())}
        changed_fp = self._revalidate(changed_action)
        assert not changed_fp.blocked_reasons, f"changed blocked: {changed_fp.blocked_reasons}"
        assert base_fp.freshness_evidence_fingerprint != (
            changed_fp.freshness_evidence_fingerprint
        )

    def test_auto_path_source_transition_record_id_isolation(self) -> None:
        """Auto-path fingerprint is isolated by source_transition_record_id."""
        base_action = _valid_freshness_action_auto()
        base_fp = self._revalidate(base_action)
        assert not base_fp.blocked_reasons

        changed_action = {**base_action, "source_transition_record_id": str(uuid4())}
        changed_fp = self._revalidate(changed_action)
        assert not changed_fp.blocked_reasons
        assert base_fp.freshness_evidence_fingerprint != (
            changed_fp.freshness_evidence_fingerprint
        )

    def test_fp_is_sha256(self) -> None:
        action = _valid_freshness_action_human()
        fp = self._revalidate(action)
        assert not fp.blocked_reasons
        assert len(fp.freshness_evidence_fingerprint) == 64
        assert all(c in "0123456789abcdef" for c in fp.freshness_evidence_fingerprint)

    def test_deterministic(self) -> None:
        a1 = _valid_freshness_action_human()
        a2 = dict(a1)
        fp1 = self._revalidate(a1)
        fp2 = self._revalidate(a2)
        assert not fp1.blocked_reasons
        assert not fp2.blocked_reasons
        assert fp1.freshness_evidence_fingerprint == fp2.freshness_evidence_fingerprint


# ══════════════════════════════════════════════════════════════════════
# 10. TestReplayAndPagination
# ══════════════════════════════════════════════════════════════════════


class TestReplayAndPagination:
    def test_first_ready_second_blocked(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        consumption_msg_id = _seed_full_human_chain(SessionLocal)

        svc1, s1 = _make_e_service(SessionLocal)
        r1 = svc1.prepare_protected_transition_evidence_freshness_gate(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=consumption_msg_id,
        )
        assert r1.result.freshness_status == "ready"
        assert r1.message is not None
        s1.close()

        svc2, s2 = _make_e_service(SessionLocal)
        r2 = svc2.prepare_protected_transition_evidence_freshness_gate(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=consumption_msg_id,
        )
        assert r2.result.freshness_status == "blocked"
        assert (
            "protected_transition_freshness_already_validated"
            in r2.result.blocked_reasons
        )
        assert r2.result.prior_freshness_validation_detected is True
        assert r2.result.replay_check_completed is True
        assert r2.message is None
        s2.close()

    def test_replay_detected_across_pages(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        consumption_msg_id = _seed_full_human_chain(SessionLocal)

        svc1, s1 = _make_e_service(SessionLocal)
        r1 = svc1.prepare_protected_transition_evidence_freshness_gate(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=consumption_msg_id,
        )
        assert r1.result.freshness_status == "ready"
        e_seq = r1.message.sequence_no
        s1.close()

        session = SessionLocal()
        _seed_filler_messages(session, e_seq + 1, 105)
        session.close()

        svc2, s2 = _make_e_service(SessionLocal)
        r2 = svc2.prepare_protected_transition_evidence_freshness_gate(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=consumption_msg_id,
        )
        assert r2.result.freshness_status == "blocked"
        assert r2.result.prior_freshness_validation_detected is True
        assert r2.result.replay_check_completed is True
        assert (
            "protected_transition_freshness_already_validated"
            in r2.result.blocked_reasons
        )
        assert r2.message is None
        s2.close()

        verify = SessionLocal()
        count = verify.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd"
            ),
            {"sd": P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SOURCE_DETAIL},
        ).scalar()
        assert count == 1
        verify.close()

    def test_three_replay_keys(self, db_engine: Any) -> None:
        """Three independent replay keys: transition_message_id,
        transition_record_id, and review_message_id."""
        SessionLocal = _make_session_factory(db_engine)
        consumption_msg_id = _seed_full_human_chain(SessionLocal)

        svc1, s1 = _make_e_service(SessionLocal)
        r1 = svc1.prepare_protected_transition_evidence_freshness_gate(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=consumption_msg_id,
        )
        assert r1.result.freshness_status == "ready"
        s1.close()

        svc2, s2 = _make_e_service(SessionLocal)
        r2 = svc2.prepare_protected_transition_evidence_freshness_gate(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=consumption_msg_id,
        )
        assert r2.result.freshness_status == "blocked"
        assert r2.result.prior_freshness_validation_detected is True
        s2.close()


# ══════════════════════════════════════════════════════════════════════
# 11. TestConcurrency
# ══════════════════════════════════════════════════════════════════════


class HoldingImmediateTransactionRepository(ProjectDirectorMessageRepository):
    """Test-only repo: acquires BEGIN IMMEDIATE then holds until released."""

    def __init__(self, session: Any, writer_lock_acquired: Any, release_writer: Any):
        super().__init__(session)
        self._writer_lock_acquired = writer_lock_acquired
        self._release_writer = release_writer

    @contextmanager
    def sqlite_immediate_transaction(self) -> Any:
        with super().sqlite_immediate_transaction():
            self._writer_lock_acquired.set()
            if not self._release_writer.wait(timeout=10):
                raise TimeoutError("writer release timeout")
            yield


class AttemptSignalingRepository(ProjectDirectorMessageRepository):
    """Test-only repo: signals before and after entering BEGIN IMMEDIATE."""

    def __init__(self, session: Any, second_writer_attempted: Any, second_writer_entered: Any):
        super().__init__(session)
        self._second_writer_attempted = second_writer_attempted
        self._second_writer_entered = second_writer_entered

    @contextmanager
    def sqlite_immediate_transaction(self) -> Any:
        self._second_writer_attempted.set()
        with super().sqlite_immediate_transaction():
            self._second_writer_entered.set()
            yield


class TestConcurrency:
    def test_two_threads_one_ready_one_blocked(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        consumption_msg_id = _seed_full_human_chain(SessionLocal)

        handoff_svc = _StubHandoffService()
        diff_svc = _StubCandidateDiffService()

        writer_lock_acquired = threading.Event()
        release_writer = threading.Event()
        second_writer_attempted = threading.Event()
        second_writer_entered = threading.Event()

        results: list = []
        errors: list = []

        def worker_a() -> None:
            try:
                sess = SessionLocal()
                msg_repo = HoldingImmediateTransactionRepository(
                    sess, writer_lock_acquired, release_writer
                )
                sess_repo = ProjectDirectorSessionRepository(sess)
                task_repo = TaskRepository(sess)
                svc = ProjectDirectorProtectedTransitionEvidenceFreshnessService(
                    session_repository=sess_repo,
                    message_repository=msg_repo,
                    task_repository=task_repo,
                    review_handoff_service=handoff_svc,
                    candidate_diff_service=diff_svc,
                )
                result = svc.prepare_protected_transition_evidence_freshness_gate(
                    session_id=SESSION_ID,
                    source_task_id=TASK_ID,
                    source_message_id=consumption_msg_id,
                )
                results.append(result)
            except Exception as e:
                errors.append(f"thread-a:{type(e).__name__}:{e}")
            finally:
                sess.close()

        def worker_b() -> None:
            try:
                sess = SessionLocal()
                msg_repo = AttemptSignalingRepository(
                    sess, second_writer_attempted, second_writer_entered
                )
                sess_repo = ProjectDirectorSessionRepository(sess)
                task_repo = TaskRepository(sess)
                svc = ProjectDirectorProtectedTransitionEvidenceFreshnessService(
                    session_repository=sess_repo,
                    message_repository=msg_repo,
                    task_repository=task_repo,
                    review_handoff_service=handoff_svc,
                    candidate_diff_service=diff_svc,
                )
                result = svc.prepare_protected_transition_evidence_freshness_gate(
                    session_id=SESSION_ID,
                    source_task_id=TASK_ID,
                    source_message_id=consumption_msg_id,
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

        statuses = [r.result.freshness_status for r in results]
        assert statuses.count("ready") == 1
        assert statuses.count("blocked") == 1

        ready_result = next(r for r in results if r.result.freshness_status == "ready")
        blocked_result = next(
            r for r in results if r.result.freshness_status == "blocked"
        )
        assert ready_result.message is not None
        assert blocked_result.message is None
        assert blocked_result.result.prior_freshness_validation_detected is True
        assert blocked_result.result.replay_check_completed is True
        assert (
            "protected_transition_freshness_already_validated"
            in blocked_result.result.blocked_reasons
        )

        verify = SessionLocal()
        count = verify.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd"
            ),
            {"sd": P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SOURCE_DETAIL},
        ).scalar()
        assert count == 1
        verify.execute(text("BEGIN IMMEDIATE"))
        verify.commit()
        verify.close()


# ══════════════════════════════════════════════════════════════════════
# 12. TestAppendOnly
# ══════════════════════════════════════════════════════════════════════


class TestAppendOnly:
    def test_consumption_message_unchanged(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        consumption_msg_id = _seed_full_human_chain(SessionLocal)

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, consumption_msg_id)
        snapshot = row.suggested_actions_json
        session.close()

        svc, s = _make_e_service(SessionLocal)
        result = svc.prepare_protected_transition_evidence_freshness_gate(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=consumption_msg_id,
        )
        assert result.result.freshness_status == "ready"
        s.close()

        verify = SessionLocal()
        after = verify.get(ProjectDirectorMessageTable, consumption_msg_id)
        assert after.suggested_actions_json == snapshot
        verify.close()

    def test_review_message_unchanged(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        consumption_msg_id = _seed_full_human_chain(SessionLocal)

        session = SessionLocal()
        row = session.get(ProjectDirectorMessageTable, SOURCE_REVIEW_MSG_ID)
        snapshot = row.suggested_actions_json
        session.close()

        svc, s = _make_e_service(SessionLocal)
        result = svc.prepare_protected_transition_evidence_freshness_gate(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=consumption_msg_id,
        )
        assert result.result.freshness_status == "ready"
        s.close()

        verify = SessionLocal()
        after = verify.get(ProjectDirectorMessageTable, SOURCE_REVIEW_MSG_ID)
        assert after.suggested_actions_json == snapshot
        verify.close()

    def test_task_unchanged(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        consumption_msg_id = _seed_full_human_chain(SessionLocal)

        session = SessionLocal()
        task_row = session.get(TaskTable, TASK_ID)
        task_snapshot = {
            "title": task_row.title,
            "status": task_row.status,
            "priority": task_row.priority,
        }
        session.close()

        svc, s = _make_e_service(SessionLocal)
        result = svc.prepare_protected_transition_evidence_freshness_gate(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=consumption_msg_id,
        )
        assert result.result.freshness_status == "ready"
        s.close()

        verify = SessionLocal()
        task_after = verify.get(TaskTable, TASK_ID)
        assert task_after.title == task_snapshot["title"]
        assert task_after.status == task_snapshot["status"]
        assert task_after.priority == task_snapshot["priority"]
        verify.close()

    def test_no_new_tasks(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        consumption_msg_id = _seed_full_human_chain(SessionLocal)

        pre = SessionLocal()
        task_count_before = pre.execute(text("SELECT COUNT(*) FROM tasks")).scalar()
        pre.close()

        svc, s = _make_e_service(SessionLocal)
        result = svc.prepare_protected_transition_evidence_freshness_gate(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=consumption_msg_id,
        )
        assert result.result.freshness_status == "ready"
        s.close()

        post = SessionLocal()
        task_count_after = post.execute(text("SELECT COUNT(*) FROM tasks")).scalar()
        assert task_count_after == task_count_before
        post.close()

    def test_no_side_effect_flags_on_result(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        consumption_msg_id = _seed_full_human_chain(SessionLocal)

        svc, s = _make_e_service(SessionLocal)
        result = svc.prepare_protected_transition_evidence_freshness_gate(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=consumption_msg_id,
        )
        r = result.result
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
        s.close()

    def test_db_count_one_after_ready(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        consumption_msg_id = _seed_full_human_chain(SessionLocal)

        svc, s = _make_e_service(SessionLocal)
        result = svc.prepare_protected_transition_evidence_freshness_gate(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=consumption_msg_id,
        )
        assert result.result.freshness_status == "ready"
        s.close()

        verify = SessionLocal()
        count = verify.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd"
            ),
            {"sd": P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SOURCE_DETAIL},
        ).scalar()
        assert count == 1
        verify.close()

    def test_lock_release_after_ready(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        consumption_msg_id = _seed_full_human_chain(SessionLocal)

        svc, s = _make_e_service(SessionLocal)
        result = svc.prepare_protected_transition_evidence_freshness_gate(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=consumption_msg_id,
        )
        assert result.result.freshness_status == "ready"
        s.close()

        verify = SessionLocal()
        verify.execute(text("BEGIN IMMEDIATE"))
        verify.commit()
        verify.close()

    def test_lock_release_after_blocked(self, db_engine: Any) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        session.close()

        svc, s = _make_e_service(SessionLocal)
        result = svc.prepare_protected_transition_evidence_freshness_gate(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=uuid4(),
        )
        assert result.result.freshness_status == "blocked"
        s.close()

        verify = SessionLocal()
        verify.execute(text("BEGIN IMMEDIATE"))
        verify.commit()
        verify.close()
