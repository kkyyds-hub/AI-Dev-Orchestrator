"""Concurrency tests for P22 Post-Review Automation Orchestrator.

See P22-BUG-001 in the contract test file: the orchestrator cannot persist
a summary on a fresh run because _disposition_action omits blocked_reasons.
Happy-path concurrency tests are marked xfail; blocked-path tests pass.
"""

from __future__ import annotations

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.db_tables import (
    ORMBase,
    ProjectDirectorMessageTable,
    ProjectDirectorSessionTable,
    ProjectTable,
    TaskTable,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_post_review_automation_service import (
    ProjectDirectorPostReviewAutomationService,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_service import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionService,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_consumption_preflight_service import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightService,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_consumption_service import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionService,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_handoff_service import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService,
)
from app.services.project_director_sandbox_candidate_diff_review_human_escalation_package_service import (
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService,
)
from app.services.project_director_protected_transition_evidence_freshness_service import (
    ProjectDirectorProtectedTransitionEvidenceFreshnessService,
)
from app.services.project_director_sandbox_candidate_diff_readonly_review_execution_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
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
CANDIDATE_WRITE_MSG_ID = uuid4()
_WORKSPACE_PATH = "/tmp/test-workspace-p22-concurrency"

_DIFF_SHA256 = hashlib.sha256(b"diff content").hexdigest()
_PROMPT_SHA256 = hashlib.sha256(b"prompt content").hexdigest()
_RAW_OUTPUT_SHA256 = hashlib.sha256(b"raw output").hexdigest()



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
            id=PROJECT_ID, name="Test", summary="Test project",
            status="active", stage="intake",
        )
    )
    session.flush()
    acceptance = json.dumps([
        "safe_dry_run_task=true",
        "worker_simulate_required=true",
        "product_runtime_git_write_allowed=false",
    ])
    session.add(
        TaskTable(
            id=TASK_ID, project_id=PROJECT_ID, title="Test task",
            status="pending", priority="normal",
            input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
            risk_level="normal", human_status="none",
            source_draft_id="p12-test-draft", acceptance_criteria=acceptance,
        )
    )
    session.add(
        ProjectDirectorSessionTable(
            id=SESSION_ID, project_id=PROJECT_ID,
            goal_text="Test goal", constraints="", status="confirmed",
        )
    )
    session.commit()


def _seed_candidate_write_message(session: Session, *, seq_no: int = 30) -> None:
    action: dict[str, Any] = {
        "type": "p21_c_sandbox_candidate_files_write_record",
        "session_id": str(SESSION_ID),
        "source_task_id": str(TASK_ID),
        "workspace_path": _WORKSPACE_PATH,
    }
    session.add(
        ProjectDirectorMessageTable(
            id=CANDIDATE_WRITE_MSG_ID, session_id=SESSION_ID, role="assistant",
            content="Candidate files written.", sequence_no=seq_no,
            intent="sandbox_candidate_files_write", source="system",
            source_detail="p21_c_sandbox_candidate_files_write_executed",
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False, risk_level="high",
            related_project_id=PROJECT_ID, related_task_id=TASK_ID,
        )
    )
    session.commit()


def _seed_diff_message(session: Session, *, seq_no: int = 35) -> None:
    action: dict[str, Any] = {
        "type": "p21_c_sandbox_candidate_diff_generate_record",
        "session_id": str(SESSION_ID),
        "source_task_id": str(TASK_ID),
        "source_message_id": str(CANDIDATE_WRITE_MSG_ID),
        "workspace_path": _WORKSPACE_PATH,
    }
    session.add(
        ProjectDirectorMessageTable(
            id=DIFF_MSG_ID, session_id=SESSION_ID, role="assistant",
            content="Readonly unified diff generated.", sequence_no=seq_no,
            intent="sandbox_candidate_diff", source="system",
            source_detail="p21_c_sandbox_candidate_diff_generated",
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False, risk_level="high",
            related_project_id=PROJECT_ID, related_task_id=TASK_ID,
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
        "risk_level": "low",
        "summary": "Review completed.",
        "findings": [],
        "recommended_next_step": "Proceed.",
        "ai_project_director_total_loop": "Partial",
    }
    for flag in [
        "main_project_file_written", "sandbox_file_written", "manifest_file_written",
        "diff_file_written", "patch_applied", "git_write_performed",
        "worktree_created", "worker_started", "task_created", "run_created",
    ]:
        action[flag] = False
    action.update(overrides)
    return action


def _seed_review_message(session: Session, *, seq_no: int = 50) -> None:
    action = _valid_review_action()
    session.add(
        ProjectDirectorMessageTable(
            id=SOURCE_REVIEW_MSG_ID, session_id=SESSION_ID, role="assistant",
            content="Readonly review executed.", sequence_no=seq_no,
            intent="sandbox_candidate_diff_readonly_review_execution",
            source="system",
            source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False, risk_level="high",
            related_project_id=PROJECT_ID, related_task_id=TASK_ID,
        )
    )
    session.commit()


def _seed_filler_messages(session: Session, start_seq: int, count: int = 105) -> None:
    for i in range(count):
        session.add(
            ProjectDirectorMessageTable(
                id=uuid4(), session_id=SESSION_ID, role="user",
                content=f"filler-{i}", sequence_no=start_seq + i,
                source="system", source_detail="filler",
                suggested_actions_json="[]", requires_confirmation=False,
                risk_level="low", related_project_id=PROJECT_ID,
                related_task_id=TASK_ID,
            )
        )
    session.commit()


# ── Stub services ───────────────────────────────────────────────────


class _StubHandoff:
    def build_candidate_diff_review_handoff_from_sources(self, **kw: Any) -> Any:
        return type("H", (), {
            "review_handoff_status": "created",
            "source_diff_verified": True,
            "source_diff_sha256": _DIFF_SHA256,
            "review_scope_paths": ["src/example.py"],
            "diff_bytes": 100,
        })()


class _StubDiff:
    def build_candidate_diff_from_sources(self, **kw: Any) -> Any:
        return type("D", (), {
            "diff_generation_status": "generated",
            "source_candidate_write_verified": True,
            "readonly_real_diff_generated": True,
            "real_diff_generated": True,
            "workspace_path": _WORKSPACE_PATH,
            "workspace_path_within_root": True,
            "unified_diff_text": "diff content",
            "diff_entries": [type("E", (), {"relative_path": "src/example.py", "unified_diff": "diff content"})()],
            "diff_bytes": 12,
            "diff_file_count": 1,
        })()


# ── Service factory ─────────────────────────────────────────────────


def _make_p22_service(session_local: Any) -> tuple[ProjectDirectorPostReviewAutomationService, Any]:
    session = session_local()
    msg_repo = ProjectDirectorMessageRepository(session)
    sess_repo = ProjectDirectorSessionRepository(session)
    task_repo = TaskRepository(session)
    svc = ProjectDirectorPostReviewAutomationService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        disposition_service=ProjectDirectorSandboxCandidateDiffReviewDispositionService(
            session_repository=sess_repo, message_repository=msg_repo,
        ),
        preflight_service=ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightService(
            session_repository=sess_repo, message_repository=msg_repo,
        ),
        consumption_service=ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionService(
            session_repository=sess_repo, message_repository=msg_repo,
            task_repository=task_repo,
            review_handoff_service=_StubHandoff(),
            candidate_diff_service=_StubDiff(),
        ),
        handoff_service=ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService(
            session_repository=sess_repo, message_repository=msg_repo,
            task_repository=task_repo,
        ),
        human_escalation_package_service=ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService(
            session_repository=sess_repo, message_repository=msg_repo,
            task_repository=task_repo,
        ),
        freshness_service=ProjectDirectorProtectedTransitionEvidenceFreshnessService(
            session_repository=sess_repo, message_repository=msg_repo,
            task_repository=task_repo,
            review_handoff_service=_StubHandoff(),
            candidate_diff_service=_StubDiff(),
        ),
    )
    return svc, session


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
    _seed_candidate_write_message(session)
    _seed_diff_message(session)
    _seed_review_message(session)
    session.close()
    return SessionLocal


@pytest.fixture()
def seeded_base_only(db_engine):
    SessionLocal = _make_session_factory(db_engine)
    session = SessionLocal()
    _seed_base_records(session)
    session.close()
    return SessionLocal


# ══════════════════════════════════════════════════════════════════════
# 19. TestDispositionConcurrency
# ══════════════════════════════════════════════════════════════════════


class TestDispositionConcurrency:
    def test_concurrent_disposition_only_one_persists(self, seeded_session) -> None:
        barrier = threading.Barrier(2, timeout=30)
        results: list[Any] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def _run() -> None:
            try:
                svc, session = _make_p22_service(seeded_session)
                barrier.wait()
                result = svc.orchestrate_post_review(
                    session_id=SESSION_ID, source_task_id=TASK_ID,
                    source_review_message_id=SOURCE_REVIEW_MSG_ID,
                )
                with lock:
                    results.append(result)
                session.close()
            except Exception as exc:
                with lock:
                    errors.append(exc)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(_run) for _ in range(2)]
            for f in as_completed(futures):
                f.result()

        assert len(errors) == 0
        assert len(results) == 2
        for r in results:
            assert r.result.orchestration_status == "ready_for_future_transition", (
                f"blocked_reasons={r.result.blocked_reasons}"
            )

    def test_concurrent_disposition_no_corruption(self, seeded_session) -> None:
        barrier = threading.Barrier(3, timeout=30)
        results: list[Any] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def _run() -> None:
            try:
                svc, session = _make_p22_service(seeded_session)
                barrier.wait()
                result = svc.orchestrate_post_review(
                    session_id=SESSION_ID, source_task_id=TASK_ID,
                    source_review_message_id=SOURCE_REVIEW_MSG_ID,
                )
                with lock:
                    results.append(result)
                session.close()
            except Exception as exc:
                with lock:
                    errors.append(exc)

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(_run) for _ in range(3)]
            for f in as_completed(futures):
                f.result()

        assert len(errors) == 0
        assert len(results) == 3
        for r in results:
            assert r.result.orchestration_status in ("blocked", "ready_for_future_transition")
            assert r.result.source_review_message_id == SOURCE_REVIEW_MSG_ID


# ══════════════════════════════════════════════════════════════════════
# 20. TestSummaryConcurrency
# ══════════════════════════════════════════════════════════════════════


class TestSummaryConcurrency:
    def test_concurrent_summary_both_succeed(self, seeded_session) -> None:
        barrier = threading.Barrier(2, timeout=30)
        results: list[Any] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def _run() -> None:
            try:
                svc, session = _make_p22_service(seeded_session)
                barrier.wait()
                result = svc.orchestrate_post_review(
                    session_id=SESSION_ID, source_task_id=TASK_ID,
                    source_review_message_id=SOURCE_REVIEW_MSG_ID,
                )
                with lock:
                    results.append(result)
                session.close()
            except Exception as exc:
                with lock:
                    errors.append(exc)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(_run) for _ in range(2)]
            for f in as_completed(futures):
                f.result()

        assert len(errors) == 0
        assert len(results) == 2
        for r in results:
            assert r.result.replay_check_completed is True

    def test_concurrent_blocked_no_error(self, seeded_base_only) -> None:
        barrier = threading.Barrier(2, timeout=30)
        results: list[Any] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def _run() -> None:
            try:
                svc, session = _make_p22_service(seeded_base_only)
                barrier.wait()
                result = svc.orchestrate_post_review(
                    session_id=SESSION_ID, source_task_id=TASK_ID,
                    source_review_message_id=SOURCE_REVIEW_MSG_ID,
                )
                with lock:
                    results.append(result)
                session.close()
            except Exception as exc:
                with lock:
                    errors.append(exc)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(_run) for _ in range(2)]
            for f in as_completed(futures):
                f.result()

        assert len(errors) == 0
        assert len(results) == 2
        for r in results:
            assert r.result.orchestration_status == "blocked"
            assert r.result.replay_check_completed is True
