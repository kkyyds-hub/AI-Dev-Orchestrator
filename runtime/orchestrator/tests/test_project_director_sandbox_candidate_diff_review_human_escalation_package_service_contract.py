"""Contract tests for P21-D-D1 human escalation package gate."""

from __future__ import annotations

import copy
import hashlib
import json
import threading
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
from app.domain.project_director_sandbox_candidate_diff_review_human_escalation_package import (
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_sandbox_candidate_diff_readonly_review_execution_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
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
from app.services.project_director_sandbox_candidate_diff_review_human_escalation_package_service import (
    HUMAN_ESCALATION_PACKAGE_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_SOURCE_DETAIL,
    PreparedSandboxCandidateDiffReviewHumanEscalationPackage,
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService,
)

# ── Constants ───────────────────────────────────────────────────────

SESSION_ID = uuid4()
TASK_ID = uuid4()
PROJECT_ID = uuid4()
SOURCE_REVIEW_MSG_ID = uuid4()
PREFLIGHT_MSG_ID = uuid4()
DIFF_MSG_ID = uuid4()
DISPOSITION_MSG_ID = uuid4()
DISPOSITION_ID = uuid4()

_DIFF_SHA256 = hashlib.sha256(b"diff content").hexdigest()
_PROMPT_SHA256 = hashlib.sha256(b"prompt content").hexdigest()
_RAW_OUTPUT_SHA256 = hashlib.sha256(b"raw output").hexdigest()

_DISPOSITION_FALSE_FLAGS = [
    "continuation_started",
    "rework_started",
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

_ESCALATION_FALSE_FLAGS = [
    f for f in _DISPOSITION_FALSE_FLAGS if f != "human_escalation_package_created"
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
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


# ── Seed helpers ────────────────────────────────────────────────────


def _seed_base_records(session: Session) -> None:
    session.add(
        ProjectTable(
            id=PROJECT_ID,
            name="Test",
            summary="Test project",
            status="active",
            stage="intake",
        )
    )
    session.flush()
    acceptance = json.dumps(
        [
            "safe_dry_run_task=true",
            "worker_simulate_required=true",
            "product_runtime_git_write_allowed=false",
            "native_executor_started=false",
            "codex_started=false",
            "claude_code_started=false",
        ]
    )
    session.add(
        TaskTable(
            id=TASK_ID,
            project_id=PROJECT_ID,
            title="Test task",
            status="pending",
            priority="normal",
            input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
            risk_level="normal",
            human_status="none",
            source_draft_id="p12-test-draft",
            acceptance_criteria=acceptance,
        )
    )
    session.add(
        ProjectDirectorSessionTable(
            id=SESSION_ID,
            project_id=PROJECT_ID,
            goal_text="Test goal",
            constraints="",
            status="confirmed",
        )
    )
    session.commit()


def _valid_review_action(**overrides: Any) -> dict[str, Any]:
    action: dict[str, Any] = {
        "type": P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
        "session_id": str(SESSION_ID),
        "source_task_id": str(TASK_ID),
        "source_preflight_message_id": str(PREFLIGHT_MSG_ID),
        "source_diff_message_id": str(DIFF_MSG_ID),
        "requested_reviewer_executor": "codex",
        "source_diff_sha256": _DIFF_SHA256,
        "review_prompt_sha256": _PROMPT_SHA256,
        "review_scope_paths": ["src/example.py"],
        "review_output_schema_version": REVIEW_OUTPUT_SCHEMA_VERSION,
        "adapter_status": "validated_output",
        "output_validation_status": "validated",
        "raw_output_sha256": _RAW_OUTPUT_SHA256,
        "strict_json_valid": True,
        "schema_valid": True,
        "semantics_valid": True,
        "evidence_scope_valid": True,
        "review_status": "reviewed",
        "verdict": "no_blocking_findings",
        "risk_level": "high",
        "summary": "High risk review with critical security finding.",
        "findings": [
            {
                "finding_id": "F1",
                "severity": "high",
                "title": "Critical vulnerability found",
                "summary": "Critical security vulnerability in authentication module",
                "evidence_paths": ["src/auth.py"],
                "recommended_action": "Fix immediately",
            }
        ],
        "recommended_next_step": "Escalate to human.",
        "ai_project_director_total_loop": "Partial",
    }
    for flag in [
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
    ]:
        action[flag] = False
    action.update(overrides)
    return action


def _seed_review_message(
    session: Session,
    *,
    review_msg_id: UUID | None = None,
    action: dict[str, Any] | None = None,
    seq_no: int = 50,
) -> UUID:
    review_msg_id = review_msg_id or SOURCE_REVIEW_MSG_ID
    action = action or _valid_review_action()
    session.add(
        ProjectDirectorMessageTable(
            id=review_msg_id,
            session_id=SESSION_ID,
            role="assistant",
            content="Readonly review executed.",
            sequence_no=seq_no,
            intent="sandbox_candidate_diff_readonly_review_execution",
            source="system",
            source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False,
            risk_level="high",
            related_project_id=PROJECT_ID,
            related_task_id=TASK_ID,
        )
    )
    session.commit()
    return review_msg_id


def _compute_review_fingerprint_from_action(
    action: dict[str, Any],
    *,
    session_id: UUID = SESSION_ID,
    source_task_id: UUID = TASK_ID,
    source_review_message_id: UUID = SOURCE_REVIEW_MSG_ID,
) -> str:
    from app.services.project_director_sandbox_candidate_diff_review_disposition_service import (
        ProjectDirectorSandboxCandidateDiffReviewDispositionService,
    )

    class _FakeMsg:
        def __init__(self, a):
            self.session_id = session_id
            self.related_task_id = source_task_id
            self.source_detail = P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL
            self.role = ProjectDirectorMessageRole.ASSISTANT
            self.source = ProjectDirectorMessageSource.SYSTEM
            self.intent = "sandbox_candidate_diff_readonly_review_execution"
            self.requires_confirmation = False
            self.risk_level = ProjectDirectorMessageRiskLevel.HIGH
            self.suggested_actions = [a]

    fake = _FakeMsg(action)
    rv = ProjectDirectorSandboxCandidateDiffReviewDispositionService.revalidate_persisted_review_result_fingerprint(
        session_id=session_id,
        source_task_id=source_task_id,
        source_review_message_id=source_review_message_id,
        source_review_message=fake,
    )
    return rv.review_result_fingerprint


def _seed_disposition_message(
    session: Session,
    *,
    disposition_msg_id: UUID | None = None,
    review_msg_id: UUID = SOURCE_REVIEW_MSG_ID,
    fingerprint: str | None = None,
    action_overrides: dict[str, Any] | None = None,
    seq_no: int = 60,
) -> UUID:
    disposition_msg_id = disposition_msg_id or DISPOSITION_MSG_ID
    review_action = _valid_review_action()
    if fingerprint is None:
        fingerprint = _compute_review_fingerprint_from_action(
            review_action,
            source_review_message_id=review_msg_id,
        )
    action: dict[str, Any] = {
        "type": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_ACTION_TYPE,
        "schema_version": REVIEW_DISPOSITION_SCHEMA_VERSION,
        "disposition_status": "computed",
        "session_id": str(SESSION_ID),
        "source_task_id": str(TASK_ID),
        "source_review_message_id": str(review_msg_id),
        "source_preflight_message_id": str(PREFLIGHT_MSG_ID),
        "source_diff_message_id": str(DIFF_MSG_ID),
        "requested_reviewer_executor": "codex",
        "source_diff_sha256": _DIFF_SHA256,
        "review_prompt_sha256": _PROMPT_SHA256,
        "review_scope_paths": ["src/example.py"],
        "review_output_schema_version": REVIEW_OUTPUT_SCHEMA_VERSION,
        "review_result_fingerprint": fingerprint,
        "disposition_id": str(DISPOSITION_ID),
        "disposition_type": "ESCALATE_TO_HUMAN",
        "disposition_reason": "high_review_risk_requires_human_escalation",
        "source_review_verdict": "no_blocking_findings",
        "source_review_risk_level": "high",
        "escalation_triggers": ["high_review_risk"],
        "evaluated_trigger_kinds": EVALUATED_TRIGGER_KINDS,
        "deferred_trigger_kinds": DEFERRED_TRIGGER_KINDS,
        "actor": "system",
        "client_request_id": None,
        "disposition_created_at": datetime.now(timezone.utc).isoformat(),
        "ai_project_director_total_loop": "Partial",
    }
    for flag in _DISPOSITION_FALSE_FLAGS:
        action[flag] = False
    if action_overrides:
        action.update(action_overrides)
    session.add(
        ProjectDirectorMessageTable(
            id=disposition_msg_id,
            session_id=SESSION_ID,
            role="assistant",
            content="Disposition computed.",
            sequence_no=seq_no,
            intent="sandbox_candidate_diff_review_disposition",
            source="system",
            source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False,
            risk_level="high",
            related_project_id=PROJECT_ID,
            related_task_id=TASK_ID,
        )
    )
    session.commit()
    return disposition_msg_id


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


# ── Service helper ──────────────────────────────────────────────────


def _make_d1_service(session_local):
    session = session_local()
    msg_repo = ProjectDirectorMessageRepository(session)
    sess_repo = ProjectDirectorSessionRepository(session)
    task_repo = TaskRepository(session)
    svc = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
    )
    return svc, session


def _d1_prepare(
    SessionLocal,
    disposition_msg_id: UUID = DISPOSITION_MSG_ID,
) -> tuple[UUID, int]:
    svc, session = _make_d1_service(SessionLocal)
    result = svc.prepare_human_escalation_package(
        session_id=SESSION_ID,
        source_task_id=TASK_ID,
        source_message_id=disposition_msg_id,
    )
    assert result.result.package_status == "prepared"
    assert result.message is not None
    pkg_msg_id = result.message.id
    pkg_seq_no = result.message.sequence_no
    session.close()
    return pkg_msg_id, pkg_seq_no


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
    def test_source_detail(self) -> None:
        assert (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_SOURCE_DETAIL
            == "p21_d_sandbox_candidate_diff_review_human_escalation_package_prepared"
        )

    def test_action_type(self) -> None:
        assert (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_ACTION_TYPE
            == "p21_d_sandbox_candidate_diff_review_human_escalation_package_record"
        )

    def test_schema_version(self) -> None:
        assert HUMAN_ESCALATION_PACKAGE_SCHEMA_VERSION == "p21-d-d1.v1"

    def test_disposition_source_detail(self) -> None:
        assert (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL
            == "p21_d_sandbox_candidate_diff_review_disposition_computed"
        )


# ══════════════════════════════════════════════════════════════════════
# 2. TestDomainBlockedContract
# ══════════════════════════════════════════════════════════════════════


class TestDomainBlockedContract:
    def test_blocked_requires_reasons(self) -> None:
        with pytest.raises(ValueError, match="blocked escalation package requires a reason"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(
                package_status="blocked",
                source_disposition_message_id=uuid4(),
                blocked_reasons=[],
            )

    def test_blocked_no_package_id(self) -> None:
        with pytest.raises(ValueError, match="blocked escalation package may not be created"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(
                package_status="blocked",
                source_disposition_message_id=uuid4(),
                escalation_package_id=uuid4(),
                blocked_reasons=["some_reason"],
            )

    def test_blocked_no_created_at(self) -> None:
        with pytest.raises(ValueError, match="blocked escalation package may not be created"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(
                package_status="blocked",
                source_disposition_message_id=uuid4(),
                package_created_at=datetime.now(timezone.utc),
                blocked_reasons=["some_reason"],
            )

    def test_blocked_no_aggregate_fp(self) -> None:
        with pytest.raises(
            ValueError,
            match="blocked escalation package may not expose an aggregate fingerprint",
        ):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(
                package_status="blocked",
                source_disposition_message_id=uuid4(),
                aggregate_evidence_fingerprint="a" * 64,
                blocked_reasons=["some_reason"],
            )

    def test_blocked_no_human_escalation_package_created(self) -> None:
        with pytest.raises(
            ValueError,
            match="blocked escalation package may not report creation",
        ):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(
                package_status="blocked",
                source_disposition_message_id=uuid4(),
                human_escalation_package_created=True,
                blocked_reasons=["some_reason"],
            )

    def test_blocked_valid(self) -> None:
        result = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(
            package_status="blocked",
            source_disposition_message_id=uuid4(),
            blocked_reasons=["session_missing"],
        )
        assert result.package_status == "blocked"
        assert result.blocked_reasons == ["session_missing"]
        assert result.escalation_package_id is None
        assert result.package_created_at is None
        assert result.aggregate_evidence_fingerprint == ""
        assert result.human_escalation_package_created is False


# ══════════════════════════════════════════════════════════════════════
# 3. TestDomainPreparedContract
# ══════════════════════════════════════════════════════════════════════


def _valid_prepared_kwargs(**overrides: Any) -> dict[str, Any]:
    sha = hashlib.sha256(b"valid").hexdigest()
    now = datetime.now(timezone.utc)
    review_msg_id = uuid4()
    kwargs: dict[str, Any] = dict(
        package_status="prepared",
        escalation_package_id=uuid4(),
        source_disposition_message_id=uuid4(),
        source_review_message_id=review_msg_id,
        source_preflight_message_id=uuid4(),
        source_diff_message_id=uuid4(),
        disposition_id=uuid4(),
        disposition_type="ESCALATE_TO_HUMAN",
        disposition_reason="high_review_risk_requires_human_escalation",
        review_result_fingerprint=sha,
        revalidated_review_result_fingerprint=sha,
        aggregate_evidence_fingerprint=sha,
        escalation_triggers=["high_review_risk"],
        escalation_scope="single_source_review",
        related_task_ids=[uuid4()],
        related_review_message_ids=[review_msg_id],
        unresolved_blocking_findings=[],
        risk_summary="High risk review.",
        proposed_human_decision_scope="resolve_single_source_review_escalation",
        source_review_validated=True,
        replay_check_completed=True,
        prior_escalation_package_detected=False,
        package_created_at=now,
        human_escalation_package_created=True,
    )
    kwargs.update(overrides)
    return kwargs


class TestDomainPreparedContract:
    def test_valid_prepared(self) -> None:
        result = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(
            **_valid_prepared_kwargs()
        )
        assert result.package_status == "prepared"
        assert result.disposition_type == "ESCALATE_TO_HUMAN"
        assert result.escalation_triggers == ["high_review_risk"]
        assert result.escalation_scope == "single_source_review"
        assert result.human_escalation_package_created is True

    def test_prepared_requires_package_id(self) -> None:
        kwargs = _valid_prepared_kwargs(escalation_package_id=None)
        with pytest.raises(ValueError, match="prepared escalation package requires identity"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(**kwargs)

    def test_prepared_requires_created_at(self) -> None:
        kwargs = _valid_prepared_kwargs(package_created_at=None)
        with pytest.raises(ValueError, match="prepared escalation package requires identity"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(**kwargs)

    def test_prepared_requires_timezone_aware(self) -> None:
        kwargs = _valid_prepared_kwargs(package_created_at=datetime(2025, 1, 1))
        with pytest.raises(ValueError, match="timezone-aware"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(**kwargs)

    def test_prepared_requires_escalate_to_human(self) -> None:
        kwargs = _valid_prepared_kwargs(disposition_type="AUTO_CONTINUE")
        with pytest.raises(ValueError, match="human escalation disposition"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(**kwargs)

    def test_prepared_requires_source_bindings(self) -> None:
        for field in [
            "source_review_message_id",
            "source_preflight_message_id",
            "source_diff_message_id",
            "disposition_id",
        ]:
            kwargs = _valid_prepared_kwargs(**{field: None})
            with pytest.raises(ValueError, match="exact source bindings"):
                ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(**kwargs)

    def test_prepared_requires_fingerprints(self) -> None:
        kwargs = _valid_prepared_kwargs(review_result_fingerprint="invalid")
        with pytest.raises(ValueError, match="review fingerprint"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(**kwargs)

    def test_prepared_requires_matching_fingerprints(self) -> None:
        kwargs = _valid_prepared_kwargs(revalidated_review_result_fingerprint="b" * 64)
        with pytest.raises(ValueError, match="matching review fingerprints"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(**kwargs)

    def test_prepared_requires_aggregate_fp(self) -> None:
        kwargs = _valid_prepared_kwargs(aggregate_evidence_fingerprint="")
        with pytest.raises(ValueError, match="aggregate evidence"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(**kwargs)

    def test_prepared_requires_exact_triggers(self) -> None:
        kwargs = _valid_prepared_kwargs(escalation_triggers=["other"])
        with pytest.raises(ValueError, match="exact escalation trigger"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(**kwargs)

    def test_prepared_requires_single_source_scope(self) -> None:
        kwargs = _valid_prepared_kwargs(escalation_scope="multi_source")
        with pytest.raises((ValueError, Exception)):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(**kwargs)

    def test_prepared_requires_one_task_one_review(self) -> None:
        kwargs = _valid_prepared_kwargs(related_task_ids=[])
        with pytest.raises(ValueError, match="one task and one review"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(**kwargs)

    def test_prepared_review_binding_exact(self) -> None:
        review_msg_id = uuid4()
        kwargs = _valid_prepared_kwargs(
            source_review_message_id=review_msg_id,
            related_review_message_ids=[uuid4()],
        )
        with pytest.raises(ValueError, match="review binding must be exact"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(**kwargs)

    def test_prepared_requires_risk_summary(self) -> None:
        kwargs = _valid_prepared_kwargs(risk_summary="")
        with pytest.raises(ValueError, match="risk summary"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(**kwargs)

    def test_prepared_requires_decision_scope(self) -> None:
        kwargs = _valid_prepared_kwargs(proposed_human_decision_scope=None)
        with pytest.raises(ValueError, match="bounded decision scope"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(**kwargs)

    def test_prepared_requires_validated_review(self) -> None:
        kwargs = _valid_prepared_kwargs(source_review_validated=False)
        with pytest.raises(ValueError, match="validated review evidence"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(**kwargs)

    def test_prepared_requires_clean_replay(self) -> None:
        kwargs = _valid_prepared_kwargs(replay_check_completed=False)
        with pytest.raises(ValueError, match="clean replay check"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(**kwargs)

    def test_prepared_rejects_prior_detected(self) -> None:
        kwargs = _valid_prepared_kwargs(prior_escalation_package_detected=True)
        with pytest.raises(ValueError, match="clean replay check"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(**kwargs)

    def test_prepared_requires_creation_flag(self) -> None:
        kwargs = _valid_prepared_kwargs(human_escalation_package_created=False)
        with pytest.raises(ValueError, match="append-only creation"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(**kwargs)

    def test_prepared_rejects_blocked_reasons(self) -> None:
        kwargs = _valid_prepared_kwargs(blocked_reasons=["stale"])
        with pytest.raises(ValueError, match="prepared escalation package may not be blocked"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(**kwargs)


# ══════════════════════════════════════════════════════════════════════
# 4. TestFalseOnlyFlags
# ══════════════════════════════════════════════════════════════════════


class TestFalseOnlyFlags:
    @pytest.mark.parametrize("flag", _ESCALATION_FALSE_FLAGS)
    def test_forbidden_side_effect_flag_rejected(self, flag: str) -> None:
        kwargs = _valid_prepared_kwargs(**{flag: True})
        with pytest.raises(ValueError, match="human escalation package may not"):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(**kwargs)

    def test_total_loop_must_be_partial(self) -> None:
        kwargs = _valid_prepared_kwargs(ai_project_director_total_loop="Full")
        with pytest.raises(ValueError):
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(**kwargs)


# ══════════════════════════════════════════════════════════════════════
# 5. TestDependencies
# ══════════════════════════════════════════════════════════════════════


class TestDependencies:
    def test_missing_session_repo(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        session.close()
        session = SessionLocal()
        msg_repo = ProjectDirectorMessageRepository(session)
        task_repo = TaskRepository(session)
        svc = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService(
            session_repository=None,
            message_repository=msg_repo,
            task_repository=task_repo,
        )
        with pytest.raises(ValueError, match="human escalation package repositories"):
            svc.prepare_human_escalation_package(
                session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=uuid4()
            )
        session.close()

    def test_missing_message_repo(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        session.close()
        session = SessionLocal()
        sess_repo = ProjectDirectorSessionRepository(session)
        task_repo = TaskRepository(session)
        svc = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService(
            session_repository=sess_repo,
            message_repository=None,
            task_repository=task_repo,
        )
        with pytest.raises(ValueError, match="human escalation package repositories"):
            svc.prepare_human_escalation_package(
                session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=uuid4()
            )
        session.close()

    def test_missing_task_repo(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        session.close()
        session = SessionLocal()
        msg_repo = ProjectDirectorMessageRepository(session)
        sess_repo = ProjectDirectorSessionRepository(session)
        svc = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=None,
        )
        with pytest.raises(ValueError, match="human escalation package repositories"):
            svc.prepare_human_escalation_package(
                session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=uuid4()
            )
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 6. TestNormalPreparedPath
# ══════════════════════════════════════════════════════════════════════


class TestNormalPreparedPath:
    def test_full_success(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "prepared"
        assert result.result.disposition_type == "ESCALATE_TO_HUMAN"
        assert result.result.escalation_triggers == ["high_review_risk"]
        assert result.result.escalation_scope == "single_source_review"
        assert result.result.source_review_validated is True
        assert result.result.replay_check_completed is True
        assert result.result.prior_escalation_package_detected is False
        assert result.result.human_escalation_package_created is True
        assert result.result.blocked_reasons == []
        assert result.result.escalation_package_id is not None
        assert result.result.package_created_at is not None
        assert result.result.package_created_at.tzinfo is not None
        assert result.result.aggregate_evidence_fingerprint != ""
        assert len(result.result.aggregate_evidence_fingerprint) == 64
        assert result.result.unresolved_blocking_findings
        assert result.result.risk_summary != ""
        assert result.result.proposed_human_decision_scope == "resolve_single_source_review_escalation"
        session.close()

    def test_message_fields(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        msg = result.message
        assert msg is not None
        assert msg.session_id == SESSION_ID
        assert msg.role == ProjectDirectorMessageRole.ASSISTANT
        assert msg.source == ProjectDirectorMessageSource.SYSTEM
        assert msg.requires_confirmation is True
        assert msg.risk_level == ProjectDirectorMessageRiskLevel.HIGH
        assert msg.related_project_id == PROJECT_ID
        assert msg.related_task_id == TASK_ID
        assert msg.intent == "sandbox_candidate_diff_review_human_escalation_package"
        assert msg.source_detail == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_SOURCE_DETAIL
        assert len(msg.suggested_actions) == 1
        assert msg.created_at.tzinfo is not None
        assert msg.created_at.utcoffset() is not None

        content_lower = msg.content.lower()
        assert "prepared" in content_lower
        assert "human" in content_lower
        assert "total loop remains partial" in content_lower
        assert "continuation" not in content_lower or "no continuation" in content_lower
        assert "write authorized" not in content_lower

        forbidden = msg.forbidden_actions_detected
        for required in [
            "no_human_decision",
            "no_approval_request",
            "no_legacy_approval_decision",
            "no_continuation_start",
            "no_rework_start",
            "no_workspace_write",
            "no_main_project_file_write",
            "no_manifest_write",
            "no_diff_file_write",
            "no_patch_apply",
            "no_product_runtime_git_write",
            "no_worker_dispatch",
            "no_task_creation",
            "no_run_creation",
            "no_worktree_creation",
            "no_pr_creation",
            "no_merge",
            "no_ci_trigger",
        ]:
            assert required in forbidden
        session.close()

    def test_action_fields(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        action = result.message.suggested_actions[0]
        assert action["type"] == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_ACTION_TYPE
        assert action["schema_version"] == HUMAN_ESCALATION_PACKAGE_SCHEMA_VERSION
        assert action["package_status"] == "prepared"
        assert UUID(action["escalation_package_id"])
        assert action["session_id"] == str(SESSION_ID)
        assert action["source_task_id"] == str(TASK_ID)
        assert action["source_disposition_message_id"] == str(DISPOSITION_MSG_ID)
        assert action["source_review_message_id"] == str(SOURCE_REVIEW_MSG_ID)
        assert action["disposition_id"] == str(DISPOSITION_ID)
        assert action["disposition_type"] == "ESCALATE_TO_HUMAN"
        assert action["escalation_triggers"] == ["high_review_risk"]
        assert action["escalation_scope"] == "single_source_review"
        assert action["requested_reviewer_executor"] == "codex"
        assert action["source_diff_sha256"] == _DIFF_SHA256
        assert action["review_prompt_sha256"] == _PROMPT_SHA256
        assert action["review_scope_paths"] == ["src/example.py"]
        assert action["review_output_schema_version"] == REVIEW_OUTPUT_SCHEMA_VERSION
        assert action["source_review_verdict"] == "no_blocking_findings"
        assert action["source_review_risk_level"] == "high"
        assert action["actor"] == "system"
        assert action["client_request_id"] is None
        assert action["blocked_reasons"] == []
        assert action["source_review_validated"] is True
        assert action["replay_check_completed"] is True
        assert action["prior_escalation_package_detected"] is False

        for flag in _ESCALATION_FALSE_FLAGS:
            assert action.get(flag) is False, f"{flag} should be False"
        assert action["ai_project_director_total_loop"] == "Partial"

        assert action["aggregate_evidence_fingerprint"] == result.result.aggregate_evidence_fingerprint
        assert len(action["unresolved_blocking_findings"]) > 0
        session.close()

    def test_db_persistence(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.message is not None
        msg_id = result.message.id
        session.close()

        verify = SessionLocal()
        row = verify.get(ProjectDirectorMessageTable, msg_id)
        assert row is not None
        assert row.role == "assistant"
        assert row.source == "system"
        assert row.requires_confirmation is True
        assert row.risk_level == "high"
        assert row.source_detail == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_SOURCE_DETAIL
        assert row.intent == "sandbox_candidate_diff_review_human_escalation_package"

        actions = json.loads(row.suggested_actions_json)
        assert len(actions) == 1
        act = actions[0]
        assert act["type"] == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_ACTION_TYPE
        assert act["schema_version"] == HUMAN_ESCALATION_PACKAGE_SCHEMA_VERSION
        assert act["package_status"] == "prepared"
        assert act["disposition_type"] == "ESCALATE_TO_HUMAN"
        assert act["escalation_triggers"] == ["high_review_risk"]
        assert act["actor"] == "system"
        assert act["client_request_id"] is None

        count = verify.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd"
            ),
            {"sd": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_SOURCE_DETAIL},
        ).scalar()
        assert count == 1
        verify.close()


# ══════════════════════════════════════════════════════════════════════
# 7. TestTaskProjectBinding
# ══════════════════════════════════════════════════════════════════════


class TestTaskProjectBinding:
    def test_session_missing(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=uuid4(),
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "blocked"
        assert "session_missing" in result.result.blocked_reasons
        assert result.message is None
        session.close()

    def test_task_missing(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=uuid4(),
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "blocked"
        assert "source_task_missing" in result.result.blocked_reasons
        assert result.message is None
        session.close()

    def test_task_project_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)

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

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=other_task_id,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "blocked"
        assert "source_task_project_mismatch" in result.result.blocked_reasons
        assert result.message is None
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 8. TestDispositionMessageTampering
# ══════════════════════════════════════════════════════════════════════


class TestDispositionMessageTampering:
    def _assert_blocked(
        self,
        SessionLocal,
        *,
        reason: str,
        disposition_msg_id: UUID = DISPOSITION_MSG_ID,
    ) -> None:
        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=disposition_msg_id,
        )
        assert result.result.package_status == "blocked"
        assert reason in result.result.blocked_reasons
        assert result.message is None
        session.close()

    def test_disposition_missing(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        session.close()
        self._assert_blocked(SessionLocal, reason="source_disposition_message_missing")

    def test_session_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        disp_id = _seed_disposition_message(session)
        foreign_session_id = uuid4()
        session.add(
            ProjectDirectorSessionTable(
                id=foreign_session_id, project_id=PROJECT_ID,
                goal_text="Foreign", constraints="", status="confirmed",
            )
        )
        session.flush()
        row = session.get(ProjectDirectorMessageTable, disp_id)
        row.session_id = foreign_session_id
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, reason="source_disposition_message_session_mismatch")

    def test_task_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        disp_id = _seed_disposition_message(session)
        foreign_task_id = uuid4()
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
        row = session.get(ProjectDirectorMessageTable, disp_id)
        row.related_task_id = foreign_task_id
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, reason="source_disposition_message_task_mismatch")

    def test_wrong_role(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        disp_id = _seed_disposition_message(session)
        row = session.get(ProjectDirectorMessageTable, disp_id)
        row.role = "user"
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, reason="source_disposition_message_role_invalid")

    def test_wrong_source(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        disp_id = _seed_disposition_message(session)
        row = session.get(ProjectDirectorMessageTable, disp_id)
        row.source = "ai"
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, reason="source_disposition_message_source_invalid")

    def test_wrong_intent(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        disp_id = _seed_disposition_message(session)
        row = session.get(ProjectDirectorMessageTable, disp_id)
        row.intent = "wrong_intent"
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, reason="source_disposition_message_intent_invalid")

    def test_wrong_source_detail(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        disp_id = _seed_disposition_message(session)
        row = session.get(ProjectDirectorMessageTable, disp_id)
        row.source_detail = "wrong_detail"
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, reason="source_message_is_not_p21_d_review_disposition")

    def test_confirmation_not_false(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        disp_id = _seed_disposition_message(session)
        row = session.get(ProjectDirectorMessageTable, disp_id)
        row.requires_confirmation = True
        session.commit()
        session.close()
        self._assert_blocked(
            SessionLocal,
            reason="source_disposition_message_confirmation_contract_invalid",
        )

    def test_wrong_risk_level(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        disp_id = _seed_disposition_message(session)
        row = session.get(ProjectDirectorMessageTable, disp_id)
        row.risk_level = "low"
        session.commit()
        session.close()
        self._assert_blocked(
            SessionLocal,
            reason="source_disposition_message_risk_level_invalid",
        )

    def test_empty_actions(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        disp_id = _seed_disposition_message(session)
        row = session.get(ProjectDirectorMessageTable, disp_id)
        row.suggested_actions_json = "[]"
        session.commit()
        session.close()
        self._assert_blocked(
            SessionLocal, reason="p21_d_review_disposition_record_missing"
        )

    def test_two_actions(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        disp_id = _seed_disposition_message(session)
        row = session.get(ProjectDirectorMessageTable, disp_id)
        actions = json.loads(row.suggested_actions_json)
        row.suggested_actions_json = json.dumps([actions[0], actions[0]])
        session.commit()
        session.close()
        self._assert_blocked(
            SessionLocal, reason="p21_d_review_disposition_record_missing"
        )

    def test_wrong_action_type(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        disp_id = _seed_disposition_message(session)
        row = session.get(ProjectDirectorMessageTable, disp_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["type"] = "wrong_type"
        row.suggested_actions_json = json.dumps([action])
        session.commit()
        session.close()
        self._assert_blocked(
            SessionLocal, reason="p21_d_review_disposition_record_missing"
        )


# ══════════════════════════════════════════════════════════════════════
# 9. TestDispositionDomainReconstruction
# ══════════════════════════════════════════════════════════════════════


class TestDispositionDomainReconstruction:
    def _assert_blocked(self, SessionLocal, *, reason: str) -> None:
        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "blocked"
        assert reason in result.result.blocked_reasons
        session.close()

    def test_wrong_schema_version(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={"schema_version": "wrong"})
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_schema_version_mismatch")

    def test_session_action_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={"session_id": str(uuid4())})
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_action_session_mismatch")

    def test_task_action_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={"source_task_id": str(uuid4())})
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_action_task_mismatch")

    def test_auto_continue_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "disposition_type": "AUTO_CONTINUE",
            "disposition_reason": "review_has_no_blocking_findings",
            "escalation_triggers": [],
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_type_not_human_escalation")

    def test_auto_rework_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "disposition_type": "AUTO_REWORK",
            "disposition_reason": "review_changes_required",
            "escalation_triggers": [],
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_type_not_human_escalation")

    def test_fingerprint_tampered(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(
            session,
            action_overrides={"review_result_fingerprint": "a" * 64},
        )
        session.close()
        self._assert_blocked(SessionLocal, reason="review_result_fingerprint_mismatch")

    def test_wrong_triggers(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "escalation_triggers": ["other_trigger"],
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_trigger_contract_invalid")

    def test_wrong_actor(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={"actor": "user"})
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_actor_invalid")

    def test_client_request_id_not_none(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "client_request_id": str(uuid4()),
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_client_request_id_invalid")

    def test_bad_timestamp(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "disposition_created_at": "2025-01-01T00:00:00",
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_timestamp_invalid")

    @pytest.mark.parametrize("flag", _DISPOSITION_FALSE_FLAGS)
    def test_disposition_flag_set_true(self, db_engine, flag: str) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={flag: True})
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_write_boundary_violated")

    def test_total_loop_not_partial(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "ai_project_director_total_loop": "Pass",
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_write_boundary_violated")

    def test_invalid_review_id(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "source_review_message_id": "not-a-uuid",
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_binding_invalid")

    def test_invalid_preflight_id(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "source_preflight_message_id": "",
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_binding_invalid")

    def test_invalid_diff_id(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "source_diff_message_id": "bad",
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_binding_invalid")

    def test_invalid_disposition_id(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "disposition_id": "not-uuid",
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_binding_invalid")

    def test_invalid_executor(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "requested_reviewer_executor": "invalid",
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_binding_invalid")

    def test_invalid_diff_sha(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "source_diff_sha256": "not_sha",
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_binding_invalid")

    def test_invalid_prompt_sha(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "review_prompt_sha256": "bad",
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_binding_invalid")

    def test_invalid_scope_paths(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "review_scope_paths": [],
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_binding_invalid")

    def test_invalid_output_schema(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "review_output_schema_version": "wrong",
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_binding_invalid")

    def test_invalid_verdict(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "source_review_verdict": "invalid",
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_binding_invalid")

    def test_invalid_risk_level(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "source_review_risk_level": "critical",
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_binding_invalid")

    def test_wrong_evaluated_triggers(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "evaluated_trigger_kinds": ["other"],
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_trigger_contract_invalid")

    def test_wrong_deferred_triggers(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "deferred_trigger_kinds": ["other"],
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_trigger_contract_invalid")


# ══════════════════════════════════════════════════════════════════════
# 10. TestReviewMessageTampering
# ══════════════════════════════════════════════════════════════════════


class TestReviewMessageTampering:
    def _assert_blocked(self, SessionLocal, *, reason: str) -> None:
        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "blocked"
        assert reason in result.result.blocked_reasons
        session.close()

    def test_review_missing(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_disposition_message(session)
        session.close()
        self._assert_blocked(SessionLocal, reason="source_review_message_missing")

    def test_review_session_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        foreign_session_id = uuid4()
        session.add(
            ProjectDirectorSessionTable(
                id=foreign_session_id, project_id=PROJECT_ID,
                goal_text="Foreign", constraints="", status="confirmed",
            )
        )
        session.flush()
        row = session.get(ProjectDirectorMessageTable, SOURCE_REVIEW_MSG_ID)
        row.session_id = foreign_session_id
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, reason="source_review_message_session_mismatch")

    def test_review_task_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        foreign_task_id = uuid4()
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
        row = session.get(ProjectDirectorMessageTable, SOURCE_REVIEW_MSG_ID)
        row.related_task_id = foreign_task_id
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, reason="source_review_message_task_mismatch")

    def test_review_wrong_role(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        row = session.get(ProjectDirectorMessageTable, SOURCE_REVIEW_MSG_ID)
        row.role = "user"
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, reason="source_review_message_role_invalid")

    def test_review_wrong_source(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        row = session.get(ProjectDirectorMessageTable, SOURCE_REVIEW_MSG_ID)
        row.source = "ai"
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, reason="source_review_message_source_invalid")

    def test_review_wrong_intent(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        row = session.get(ProjectDirectorMessageTable, SOURCE_REVIEW_MSG_ID)
        row.intent = "wrong_intent"
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, reason="source_review_message_intent_invalid")

    def test_review_confirmation_not_false(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        row = session.get(ProjectDirectorMessageTable, SOURCE_REVIEW_MSG_ID)
        row.requires_confirmation = True
        session.commit()
        session.close()
        self._assert_blocked(
            SessionLocal,
            reason="source_review_message_confirmation_contract_invalid",
        )

    def test_review_wrong_risk_level(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        row = session.get(ProjectDirectorMessageTable, SOURCE_REVIEW_MSG_ID)
        row.risk_level = "low"
        session.commit()
        session.close()
        self._assert_blocked(SessionLocal, reason="source_review_message_risk_level_invalid")

    def test_review_wrong_source_detail(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        row = session.get(ProjectDirectorMessageTable, SOURCE_REVIEW_MSG_ID)
        row.source_detail = "wrong_detail"
        session.commit()
        session.close()
        self._assert_blocked(
            SessionLocal,
            reason="source_message_is_not_p21_c_readonly_review_execution",
        )

    def test_review_empty_actions(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        row = session.get(ProjectDirectorMessageTable, SOURCE_REVIEW_MSG_ID)
        row.suggested_actions_json = "[]"
        session.commit()
        session.close()
        self._assert_blocked(
            SessionLocal,
            reason="p21_c_readonly_review_execution_record_missing",
        )

    def test_review_two_actions(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        row = session.get(ProjectDirectorMessageTable, SOURCE_REVIEW_MSG_ID)
        actions = json.loads(row.suggested_actions_json)
        row.suggested_actions_json = json.dumps([actions[0], actions[0]])
        session.commit()
        session.close()
        self._assert_blocked(
            SessionLocal,
            reason="p21_c_readonly_review_execution_record_missing",
        )

    def test_review_wrong_action_type(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        row = session.get(ProjectDirectorMessageTable, SOURCE_REVIEW_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["type"] = "wrong_type"
        row.suggested_actions_json = json.dumps([action])
        session.commit()
        session.close()
        self._assert_blocked(
            SessionLocal,
            reason="p21_c_readonly_review_execution_record_missing",
        )


# ══════════════════════════════════════════════════════════════════════
# 11. TestFingerprintRevalidation
# ══════════════════════════════════════════════════════════════════════


class TestFingerprintRevalidation:
    def test_fingerprint_tampered_in_disposition(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(
            session,
            action_overrides={"review_result_fingerprint": "a" * 64},
        )
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "blocked"
        assert "review_result_fingerprint_mismatch" in result.result.blocked_reasons
        session.close()

    def test_review_content_tampered_blocks(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        row = session.get(ProjectDirectorMessageTable, SOURCE_REVIEW_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["source_diff_sha256"] = hashlib.sha256(b"tampered").hexdigest()
        row.suggested_actions_json = json.dumps([action])
        session.commit()
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "blocked"
        assert "review_result_fingerprint_mismatch" in result.result.blocked_reasons
        session.close()

    def test_review_verdict_tampered_blocks(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        row = session.get(ProjectDirectorMessageTable, SOURCE_REVIEW_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["verdict"] = "changes_required"
        row.suggested_actions_json = json.dumps([action])
        session.commit()
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "blocked"
        assert "review_result_fingerprint_mismatch" in result.result.blocked_reasons
        session.close()

    def test_review_scope_tampered_blocks(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        row = session.get(ProjectDirectorMessageTable, SOURCE_REVIEW_MSG_ID)
        action = json.loads(row.suggested_actions_json)[0]
        action["review_scope_paths"] = ["src/tampered.py"]
        row.suggested_actions_json = json.dumps([action])
        session.commit()
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "blocked"
        assert "review_result_fingerprint_mismatch" in result.result.blocked_reasons
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 12. TestSourceEvidenceBinding
# ══════════════════════════════════════════════════════════════════════


class TestSourceEvidenceBinding:
    def _assert_blocked(self, SessionLocal, *, reason: str) -> None:
        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "blocked"
        assert reason in result.result.blocked_reasons
        session.close()

    def test_preflight_id_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        review_action = _valid_review_action()
        _seed_review_message(session, action=review_action)
        _seed_disposition_message(session, action_overrides={
            "source_preflight_message_id": str(uuid4()),
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_source_binding_mismatch")

    def test_diff_id_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "source_diff_message_id": str(uuid4()),
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_source_binding_mismatch")

    def test_executor_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "requested_reviewer_executor": "claude-code",
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_source_binding_mismatch")

    def test_diff_sha_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "source_diff_sha256": hashlib.sha256(b"other").hexdigest(),
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_source_binding_mismatch")

    def test_prompt_sha_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "review_prompt_sha256": hashlib.sha256(b"other").hexdigest(),
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_source_binding_mismatch")

    def test_scope_paths_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "review_scope_paths": ["src/other.py"],
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_source_binding_mismatch")

    def test_schema_version_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "review_output_schema_version": "wrong",
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_binding_invalid")

    def test_verdict_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "source_review_verdict": "changes_required",
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_source_binding_mismatch")

    def test_risk_level_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session, action_overrides={
            "source_review_risk_level": "medium",
        })
        session.close()
        self._assert_blocked(SessionLocal, reason="disposition_source_binding_mismatch")


# ══════════════════════════════════════════════════════════════════════
# 13. TestStrictFindings
# ══════════════════════════════════════════════════════════════════════


class TestStrictFindings:
    def test_high_finding_extracted(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "prepared"
        assert len(result.result.unresolved_blocking_findings) > 0
        assert all(
            f.severity == "high"
            for f in result.result.unresolved_blocking_findings
        )
        session.close()

    def test_medium_low_findings_not_extracted(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        review_action = _valid_review_action(
            findings=[
                {
                    "finding_id": "F1",
                    "severity": "medium",
                    "title": "Medium finding",
                    "summary": "Medium severity",
                    "evidence_paths": ["src/a.py"],
                    "recommended_action": "Fix later",
                },
                {
                    "finding_id": "F2",
                    "severity": "low",
                    "title": "Low finding",
                    "summary": "Low severity",
                    "evidence_paths": ["src/b.py"],
                    "recommended_action": "Ignore",
                },
            ],
        )
        _seed_review_message(session, action=review_action)
        fingerprint = _compute_review_fingerprint_from_action(review_action)
        _seed_disposition_message(session, fingerprint=fingerprint)
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "prepared"
        assert len(result.result.unresolved_blocking_findings) == 0
        session.close()

    def test_invalid_finding_schema_blocks(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        review_action = _valid_review_action(
            findings=[{"severity": "high"}],
        )
        _seed_review_message(session, action=review_action)
        fingerprint = _compute_review_fingerprint_from_action(review_action)
        _seed_disposition_message(session, fingerprint=fingerprint)
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "blocked"
        assert "source_review_strict_output_invalid" in result.result.blocked_reasons
        session.close()

    def test_high_risk_no_high_findings(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        review_action = _valid_review_action(
            risk_level="high",
            findings=[
                {
                    "finding_id": "F1",
                    "severity": "medium",
                    "title": "Medium finding",
                    "summary": "Medium severity finding",
                    "evidence_paths": ["src/a.py"],
                    "recommended_action": "Fix later",
                },
            ],
        )
        _seed_review_message(session, action=review_action)
        fingerprint = _compute_review_fingerprint_from_action(review_action)
        _seed_disposition_message(session, fingerprint=fingerprint)
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "prepared"
        assert len(result.result.unresolved_blocking_findings) == 0
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 14. TestAggregateFingerprint
# ══════════════════════════════════════════════════════════════════════


class TestAggregateFingerprint:
    def test_deterministic(self, tmp_path) -> None:
        db1 = str(tmp_path / "test1.db")
        db2 = str(tmp_path / "test2.db")
        engine1 = _make_test_engine(db1)
        engine2 = _make_test_engine(db2)
        SL1 = _make_session_factory(engine1)
        SL2 = _make_session_factory(engine2)

        for SL in (SL1, SL2):
            s = SL()
            _seed_base_records(s)
            _seed_review_message(s, review_msg_id=SOURCE_REVIEW_MSG_ID)
            _seed_disposition_message(s, disposition_msg_id=DISPOSITION_MSG_ID)
            s.close()

        svc1, s1 = _make_d1_service(SL1)
        r1 = svc1.prepare_human_escalation_package(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert r1.result.package_status == "prepared"
        s1.close()

        svc2, s2 = _make_d1_service(SL2)
        r2 = svc2.prepare_human_escalation_package(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert r2.result.package_status == "prepared"
        s2.close()

        assert r1.result.aggregate_evidence_fingerprint
        assert r2.result.aggregate_evidence_fingerprint
        assert r1.result.aggregate_evidence_fingerprint == r2.result.aggregate_evidence_fingerprint
        engine1.dispose()
        engine2.dispose()

    def test_different_evidence_different_fp(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        svc1, s1 = _make_d1_service(SessionLocal)
        r1 = svc1.prepare_human_escalation_package(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        s1.close()

        SessionLocal2 = _make_session_factory(db_engine)
        session2 = SessionLocal2()
        alt_action = _valid_review_action(
            review_scope_paths=["src/different.py"],
        )
        _seed_review_message(session2, review_msg_id=uuid4(), action=alt_action, seq_no=500)
        fp = _compute_review_fingerprint_from_action(alt_action)
        _seed_disposition_message(
            session2,
            disposition_msg_id=uuid4(),
            review_msg_id=uuid4(),
            fingerprint=fp,
            seq_no=501,
        )
        session2.close()

        svc2, s2 = _make_d1_service(SessionLocal2)
        r2 = svc2.prepare_human_escalation_package(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=uuid4(),
        )
        if r2.result.package_status == "prepared":
            assert r1.result.aggregate_evidence_fingerprint != r2.result.aggregate_evidence_fingerprint
        s2.close()

    def test_fp_is_sha256(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        fp = result.result.aggregate_evidence_fingerprint
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 15. TestSequentialReplay
# ══════════════════════════════════════════════════════════════════════


class TestSequentialReplay:
    def test_first_prepared_second_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        svc1, s1 = _make_d1_service(SessionLocal)
        r1 = svc1.prepare_human_escalation_package(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert r1.result.package_status == "prepared"
        assert r1.message is not None
        s1.close()

        svc2, s2 = _make_d1_service(SessionLocal)
        r2 = svc2.prepare_human_escalation_package(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert r2.result.package_status == "blocked"
        assert "human_escalation_package_already_created" in r2.result.blocked_reasons
        assert r2.result.prior_escalation_package_detected is True
        assert r2.result.replay_check_completed is True
        assert r2.message is None
        s2.close()

    def test_db_count_one(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        svc1, s1 = _make_d1_service(SessionLocal)
        r1 = svc1.prepare_human_escalation_package(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert r1.result.package_status == "prepared"
        s1.close()

        svc2, s2 = _make_d1_service(SessionLocal)
        r2 = svc2.prepare_human_escalation_package(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert r2.result.package_status == "blocked"
        s2.close()

        verify = SessionLocal()
        count = verify.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd"
            ),
            {"sd": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_SOURCE_DETAIL},
        ).scalar()
        assert count == 1
        verify.close()


# ══════════════════════════════════════════════════════════════════════
# 16. TestCrossPageReplay
# ══════════════════════════════════════════════════════════════════════


class TestCrossPageReplay:
    def test_replay_detected_across_pages(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        pkg_msg_id, pkg_seq_no = _d1_prepare(SessionLocal)

        session = SessionLocal()
        _seed_filler_messages(session, pkg_seq_no + 1, 105)
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "blocked"
        assert result.result.prior_escalation_package_detected is True
        assert result.result.replay_check_completed is True
        assert "human_escalation_package_already_created" in result.result.blocked_reasons
        assert result.message is None

        d1_count = session.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd"
            ),
            {"sd": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_SOURCE_DETAIL},
        ).scalar()
        assert d1_count == 1
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 17. TestConcurrentDoubleCall
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


class TestConcurrentDoubleCall:
    def test_two_threads_one_prepared_one_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        writer_lock_acquired = threading.Event()
        release_writer = threading.Event()
        second_writer_attempted = threading.Event()
        second_writer_entered = threading.Event()

        results = []
        errors = []

        def worker_a():
            session = SessionLocal()
            msg_repo = HoldingImmediateTransactionRepository(
                session, writer_lock_acquired, release_writer
            )
            sess_repo = ProjectDirectorSessionRepository(session)
            task_repo = TaskRepository(session)
            svc = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService(
                session_repository=sess_repo,
                message_repository=msg_repo,
                task_repository=task_repo,
            )
            try:
                result = svc.prepare_human_escalation_package(
                    session_id=SESSION_ID,
                    source_task_id=TASK_ID,
                    source_message_id=DISPOSITION_MSG_ID,
                )
                results.append(result)
            except Exception as e:
                errors.append(f"thread-a:{type(e).__name__}:{e}")
            finally:
                session.close()

        def worker_b():
            session = SessionLocal()
            msg_repo = AttemptSignalingRepository(
                session, second_writer_attempted, second_writer_entered
            )
            sess_repo = ProjectDirectorSessionRepository(session)
            task_repo = TaskRepository(session)
            svc = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService(
                session_repository=sess_repo,
                message_repository=msg_repo,
                task_repository=task_repo,
            )
            try:
                result = svc.prepare_human_escalation_package(
                    session_id=SESSION_ID,
                    source_task_id=TASK_ID,
                    source_message_id=DISPOSITION_MSG_ID,
                )
                results.append(result)
            except Exception as e:
                errors.append(f"thread-b:{type(e).__name__}:{e}")
            finally:
                session.close()

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

        statuses = [r.result.package_status for r in results]
        assert statuses.count("prepared") == 1
        assert statuses.count("blocked") == 1

        prepared_result = next(r for r in results if r.result.package_status == "prepared")
        blocked_result = next(r for r in results if r.result.package_status == "blocked")
        assert prepared_result.message is not None
        assert blocked_result.message is None
        assert blocked_result.result.prior_escalation_package_detected is True
        assert blocked_result.result.replay_check_completed is True
        assert "human_escalation_package_already_created" in blocked_result.result.blocked_reasons

        verify_session = SessionLocal()
        count = verify_session.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd"
            ),
            {"sd": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_SOURCE_DETAIL},
        ).scalar()
        assert count == 1
        verify_session.execute(text("BEGIN IMMEDIATE"))
        verify_session.commit()
        verify_session.close()


# ══════════════════════════════════════════════════════════════════════
# 18. TestLockRelease
# ══════════════════════════════════════════════════════════════════════


class TestLockRelease:
    def test_prepared_releases_lock(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "prepared"
        session.close()

        verify = SessionLocal()
        verify.execute(text("BEGIN IMMEDIATE"))
        verify.commit()
        verify.close()

    def test_validation_blocked_releases_lock(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=uuid4(),
        )
        assert result.result.package_status == "blocked"
        session.close()

        verify = SessionLocal()
        verify.execute(text("BEGIN IMMEDIATE"))
        verify.commit()
        verify.close()

    def test_replay_blocked_releases_lock(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _d1_prepare(SessionLocal)

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "blocked"
        assert result.result.prior_escalation_package_detected is True
        session.close()

        verify = SessionLocal()
        verify.execute(text("BEGIN IMMEDIATE"))
        verify.commit()
        verify.close()

    def test_create_exception_rollback_releases_lock(self, db_engine, monkeypatch) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        call_count = 0
        original_create = ProjectDirectorMessageRepository.create

        def _failing_create(self, message):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("simulated DB write failure")
            return original_create(self, message)

        monkeypatch.setattr(ProjectDirectorMessageRepository, "create", _failing_create)

        svc, session = _make_d1_service(SessionLocal)
        with pytest.raises(RuntimeError, match="simulated DB write failure"):
            svc.prepare_human_escalation_package(
                session_id=SESSION_ID,
                source_task_id=TASK_ID,
                source_message_id=DISPOSITION_MSG_ID,
            )
        session.close()

        verify = SessionLocal()
        verify.execute(text("BEGIN IMMEDIATE"))
        verify.commit()
        verify.close()


# ══════════════════════════════════════════════════════════════════════
# 19. TestAppendOnlyAndNoSideEffects
# ══════════════════════════════════════════════════════════════════════


class TestAppendOnlyAndNoSideEffects:
    def test_disposition_message_unchanged(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)

        disp_row = session.get(ProjectDirectorMessageTable, DISPOSITION_MSG_ID)
        disp_snapshot = disp_row.suggested_actions_json
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "prepared"
        session.close()

        verify = SessionLocal()
        disp_after = verify.get(ProjectDirectorMessageTable, DISPOSITION_MSG_ID)
        assert disp_after.suggested_actions_json == disp_snapshot
        verify.close()

    def test_review_message_unchanged(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)

        review_row = session.get(ProjectDirectorMessageTable, SOURCE_REVIEW_MSG_ID)
        review_snapshot = review_row.suggested_actions_json
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "prepared"
        session.close()

        verify = SessionLocal()
        review_after = verify.get(ProjectDirectorMessageTable, SOURCE_REVIEW_MSG_ID)
        assert review_after.suggested_actions_json == review_snapshot
        verify.close()

    def test_task_unchanged(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)

        task_row = session.get(TaskTable, TASK_ID)
        task_snapshot = {
            "title": task_row.title,
            "status": task_row.status,
            "priority": task_row.priority,
        }
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "prepared"
        session.close()

        verify = SessionLocal()
        task_after = verify.get(TaskTable, TASK_ID)
        assert task_after.title == task_snapshot["title"]
        assert task_after.status == task_snapshot["status"]
        assert task_after.priority == task_snapshot["priority"]
        verify.close()

    def test_no_new_tasks(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        pre_sess = SessionLocal()
        task_count_before = pre_sess.execute(text("SELECT COUNT(*) FROM tasks")).scalar()
        pre_sess.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "prepared"
        session.close()

        post_sess = SessionLocal()
        task_count_after = post_sess.execute(text("SELECT COUNT(*) FROM tasks")).scalar()
        assert task_count_after == task_count_before
        post_sess.close()

    def test_no_new_runs(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "prepared"
        session.close()

        post_sess = SessionLocal()
        run_count = post_sess.execute(text("SELECT COUNT(*) FROM runs")).scalar()
        assert run_count == 0
        post_sess.close()

    def test_no_new_tasks_or_runs_after_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        _d1_prepare(SessionLocal)

        pre_sess = SessionLocal()
        task_count_before = pre_sess.execute(text("SELECT COUNT(*) FROM tasks")).scalar()
        run_count_before = pre_sess.execute(text("SELECT COUNT(*) FROM runs")).scalar()
        pre_sess.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        assert result.result.package_status == "blocked"
        session.close()

        post_sess = SessionLocal()
        assert post_sess.execute(text("SELECT COUNT(*) FROM tasks")).scalar() == task_count_before
        assert post_sess.execute(text("SELECT COUNT(*) FROM runs")).scalar() == run_count_before
        post_sess.close()

    def test_no_side_effect_flags_on_result(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_review_message(session)
        _seed_disposition_message(session)
        session.close()

        svc, session = _make_d1_service(SessionLocal)
        result = svc.prepare_human_escalation_package(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=DISPOSITION_MSG_ID,
        )
        r = result.result
        assert r.continuation_started is False
        assert r.rework_started is False
        assert r.human_decision_recorded is False
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
        session.close()
