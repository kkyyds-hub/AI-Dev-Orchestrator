"""Contract tests for P22 Post-Review Automation Orchestrator."""

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
from app.domain.project_director_message import (
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_post_review_automation import (
    ProjectDirectorPostReviewAutomationResult,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_post_review_automation_service import (
    POST_REVIEW_AUTOMATION_SCHEMA_VERSION,
    P22_POST_REVIEW_AUTOMATION_ACTION_TYPE,
    P22_POST_REVIEW_AUTOMATION_SOURCE_DETAIL,
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
_WORKSPACE_PATH = "/tmp/test-workspace-p22"
CANDIDATE_WRITE_MSG_ID = uuid4()

_DIFF_SHA256 = hashlib.sha256(b"diff content").hexdigest()
_PROMPT_SHA256 = hashlib.sha256(b"prompt content").hexdigest()
_RAW_OUTPUT_SHA256 = hashlib.sha256(b"raw output").hexdigest()

_P22_FALSE_FLAGS = [
    "continuation_started",
    "rework_started",
    "human_decision_recorded",
    "task_created",
    "run_created",
    "worker_started",
    "worktree_created",
    "main_project_file_written",
    "sandbox_file_written",
    "manifest_file_written",
    "diff_file_written",
    "patch_applied",
    "git_write_performed",
    "gate_allows_write",
    "product_runtime_git_write_allowed",
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
            id=PROJECT_ID, name="Test", summary="Test project",
            status="active", stage="intake",
        )
    )
    session.flush()
    acceptance = json.dumps([
        "safe_dry_run_task=true",
        "worker_simulate_required=true",
        "product_runtime_git_write_allowed=false",
        "native_executor_started=false",
        "codex_started=false",
        "claude_code_started=false",
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


def _valid_review_action(
    *,
    verdict: str = "no_blocking_findings",
    risk_level: str = "low",
    session_id: UUID = SESSION_ID,
    task_id: UUID = TASK_ID,
    **overrides: Any,
) -> dict[str, Any]:
    action: dict[str, Any] = {
        "type": P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
        "session_id": str(session_id),
        "source_task_id": str(task_id),
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
        "verdict": verdict,
        "risk_level": risk_level,
        "summary": "Review completed.",
        "findings": [],
        "recommended_next_step": "Proceed.",
        "workspace_path": _WORKSPACE_PATH,
        "workspace_path_within_root": True,
        "diff_generation_status": "generated",
        "readonly_real_diff_generated": True,
        "real_diff_generated": True,
        "diff_bytes": 100,
        "diff_file_count": 1,
        "unified_diff_text": "diff content",
        "diff_entries": [{"relative_path": "src/example.py", "unified_diff": "diff content", "operation": "update"}],
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


def _seed_review_message(
    session: Session,
    *,
    msg_id: UUID = SOURCE_REVIEW_MSG_ID,
    action: dict[str, Any] | None = None,
    seq_no: int = 50,
    session_id: UUID = SESSION_ID,
    task_id: UUID = TASK_ID,
) -> None:
    action = action or _valid_review_action(session_id=session_id, task_id=task_id)
    session.add(
        ProjectDirectorMessageTable(
            id=msg_id, session_id=session_id, role="assistant",
            content="Readonly review executed.", sequence_no=seq_no,
            intent="sandbox_candidate_diff_readonly_review_execution",
            source="system",
            source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False, risk_level="high",
            related_project_id=PROJECT_ID, related_task_id=task_id,
        )
    )
    session.commit()


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
            id=msg_id, session_id=SESSION_ID, role="assistant",
            content="Candidate files written to sandbox workspace.",
            sequence_no=seq_no, intent="sandbox_candidate_files_write",
            source="system", source_detail="p21_c_sandbox_candidate_files_write_executed",
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False, risk_level="high",
            related_project_id=PROJECT_ID, related_task_id=TASK_ID,
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
            id=msg_id, session_id=SESSION_ID, role="assistant",
            content="Readonly unified diff generated.",
            sequence_no=seq_no, intent="sandbox_candidate_diff",
            source="system", source_detail="p21_c_sandbox_candidate_diff_generated",
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False, risk_level="high",
            related_project_id=PROJECT_ID, related_task_id=TASK_ID,
        )
    )
    session.commit()
    return msg_id


def _seed_filler_messages(
    session: Session, start_seq: int, count: int = 105,
    session_id: UUID = SESSION_ID, task_id: UUID = TASK_ID,
) -> None:
    for i in range(count):
        session.add(
            ProjectDirectorMessageTable(
                id=uuid4(), session_id=session_id, role="user",
                content=f"filler-{i}", sequence_no=start_seq + i,
                source="system", source_detail="filler",
                suggested_actions_json="[]", requires_confirmation=False,
                risk_level="low", related_project_id=PROJECT_ID,
                related_task_id=task_id,
            )
        )
    session.commit()


def _seed_diff_and_write_messages(
    session: Session,
    *,
    session_id: UUID = SESSION_ID,
    task_id: UUID = TASK_ID,
) -> None:
    candidate_write_action = {
        "type": "p21_c_sandbox_candidate_files_write_record",
        "source_message_id": str(uuid4()),
        "source_task_id": str(task_id),
        "workspace_path": "/tmp/ws",
        "candidate_write_status": "written",
        "ai_project_director_total_loop": "Partial",
    }
    for flag in [
        "main_project_file_written", "sandbox_file_written", "manifest_file_written",
        "diff_file_written", "patch_applied", "git_write_performed",
        "worktree_created", "worker_started", "task_created", "run_created",
    ]:
        candidate_write_action[flag] = False
    session.add(
        ProjectDirectorMessageTable(
            id=CANDIDATE_WRITE_MSG_ID, session_id=session_id, role="assistant",
            content="Candidate files written.", sequence_no=10,
            intent="sandbox_candidate_files_write",
            related_project_id=PROJECT_ID, related_task_id=task_id,
            source="system",
            source_detail="p21_c_sandbox_candidate_files_write_executed",
            suggested_actions_json=json.dumps([candidate_write_action]),
            requires_confirmation=False, risk_level="high",
        )
    )
    diff_action = {
        "type": "p21_c_sandbox_candidate_diff_record",
        "diff_generation_status": "generated",
        "source_task_id": str(task_id),
        "source_message_id": str(CANDIDATE_WRITE_MSG_ID),
        "workspace_path": "/tmp/ws",
        "workspace_path_within_root": True,
        "readonly_real_diff_generated": True,
        "real_diff_generated": True,
        "diff_file_count": 1,
        "diff_bytes": 4,
        "diff_entries": [
            {"relative_path": "src/example.py", "unified_diff": "diff content"}
        ],
        "unified_diff_text": "diff content",
        "ai_project_director_total_loop": "Partial",
    }
    for flag in [
        "main_project_file_written", "sandbox_file_written", "manifest_file_written",
        "diff_file_written", "patch_applied", "git_write_performed",
        "worktree_created", "worker_started", "task_created", "run_created",
    ]:
        diff_action[flag] = False
    session.add(
        ProjectDirectorMessageTable(
            id=DIFF_MSG_ID, session_id=session_id, role="assistant",
            content="Candidate diff generated.", sequence_no=11,
            intent="sandbox_candidate_diff",
            related_project_id=PROJECT_ID, related_task_id=task_id,
            source="system",
            source_detail="p21_c_sandbox_candidate_diff_generated",
            suggested_actions_json=json.dumps([diff_action]),
            requires_confirmation=False, risk_level="high",
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
def SessionLocal(db_engine):
    return _make_session_factory(db_engine)


@pytest.fixture()
def seeded_auto_continue(SessionLocal):
    session = SessionLocal()
    _seed_base_records(session)
    _seed_review_message(session, action=_valid_review_action(verdict="no_blocking_findings", risk_level="low"))
    _seed_diff_and_write_messages(session)
    session.close()
    return SessionLocal


@pytest.fixture()
def seeded_auto_rework(SessionLocal):
    session = SessionLocal()
    _seed_base_records(session)
    _seed_review_message(session, action=_valid_review_action(verdict="changes_required", risk_level="medium"))
    _seed_diff_and_write_messages(session)
    session.close()
    return SessionLocal


@pytest.fixture()
def seeded_auto_continue(SessionLocal):
    session = SessionLocal()
    _seed_base_records(session)
    _seed_candidate_write_message(session)
    _seed_diff_message(session)
    _seed_review_message(session, action=_valid_review_action(verdict="no_blocking_findings", risk_level="low"))
    session.close()
    return SessionLocal


@pytest.fixture()
def seeded_auto_rework(SessionLocal):
    session = SessionLocal()
    _seed_base_records(session)
    _seed_candidate_write_message(session)
    _seed_diff_message(session)
    _seed_review_message(session, action=_valid_review_action(verdict="changes_required", risk_level="medium"))
    session.close()
    return SessionLocal


@pytest.fixture()
def seeded_human_escalation(SessionLocal):
    session = SessionLocal()
    _seed_base_records(session)
    _seed_candidate_write_message(session)
    _seed_diff_message(session)
    _seed_review_message(session, action=_valid_review_action(verdict="no_blocking_findings", risk_level="high"))
    session.close()
    return SessionLocal


@pytest.fixture()
def seeded_base_only(SessionLocal):
    session = SessionLocal()
    _seed_base_records(session)
    session.close()
    return SessionLocal


# ══════════════════════════════════════════════════════════════════════
# 1. TestConstants
# ══════════════════════════════════════════════════════════════════════


class TestConstants:
    def test_source_detail(self) -> None:
        assert P22_POST_REVIEW_AUTOMATION_SOURCE_DETAIL == "p22_post_review_automation_orchestrated"

    def test_action_type(self) -> None:
        assert P22_POST_REVIEW_AUTOMATION_ACTION_TYPE == "p22_post_review_automation_record"

    def test_schema_version(self) -> None:
        assert POST_REVIEW_AUTOMATION_SCHEMA_VERSION == "p22-b.v1"


# ══════════════════════════════════════════════════════════════════════
# 2. TestDomainBlockedContract
# ══════════════════════════════════════════════════════════════════════


class TestDomainBlockedContract:
    def test_blocked_requires_reasons(self) -> None:
        with pytest.raises(ValueError, match="blocked.*原因"):
            ProjectDirectorPostReviewAutomationResult(
                orchestration_status="blocked",
                orchestration_id=uuid4(), route="none",
                current_step="blocked", source_review_message_id=uuid4(),
                blocked_reasons=[],
            )

    def test_blocked_no_evidence_fresh(self) -> None:
        with pytest.raises(ValueError, match="不得允许受保护转换"):
            ProjectDirectorPostReviewAutomationResult(
                orchestration_status="blocked",
                orchestration_id=uuid4(), route="none",
                current_step="blocked", source_review_message_id=uuid4(),
                blocked_reasons=["x"], evidence_fresh=True,
            )

    def test_blocked_no_gate_allows(self) -> None:
        with pytest.raises(ValueError, match="不得允许受保护转换"):
            ProjectDirectorPostReviewAutomationResult(
                orchestration_status="blocked",
                orchestration_id=uuid4(), route="none",
                current_step="blocked", source_review_message_id=uuid4(),
                blocked_reasons=["x"], gate_allows_protected_transition_guardrail=True,
            )

    def test_blocked_no_waiting_for_human(self) -> None:
        with pytest.raises(ValueError, match="不得报告等待人工"):
            ProjectDirectorPostReviewAutomationResult(
                orchestration_status="blocked",
                orchestration_id=uuid4(), route="none",
                current_step="blocked", source_review_message_id=uuid4(),
                blocked_reasons=["x"], waiting_for_human=True,
            )

    def test_blocked_no_human_escalation_package_created(self) -> None:
        with pytest.raises(ValueError, match="不得报告新建人工升级包"):
            ProjectDirectorPostReviewAutomationResult(
                orchestration_status="blocked",
                orchestration_id=uuid4(), route="none",
                current_step="blocked", source_review_message_id=uuid4(),
                blocked_reasons=["x"], human_escalation_package_created=True,
            )


# ══════════════════════════════════════════════════════════════════════
# 3. TestDomainAutomaticSuccess
# ══════════════════════════════════════════════════════════════════════


class TestDomainAutomaticSuccess:
    def _valid_auto_continue_kwargs(self) -> dict[str, Any]:
        return dict(
            orchestration_status="ready_for_future_transition",
            orchestration_id=uuid4(), route="automatic_continuation",
            current_step="freshness_ready", source_review_message_id=uuid4(),
            source_disposition_message_id=uuid4(),
            source_consumption_preflight_message_id=uuid4(),
            source_consumption_message_id=uuid4(),
            source_handoff_message_id=uuid4(),
            source_freshness_message_id=uuid4(),
            disposition_type="AUTO_CONTINUE",
            handoff_kind="automatic_continuation",
            transition_kind="CONTINUE_GUARDRAIL",
            transition_authority="AUTOMATED_DISPOSITION",
            evidence_fresh=True,
            gate_allows_protected_transition_guardrail=True,
        )

    def test_auto_continue_valid(self) -> None:
        result = ProjectDirectorPostReviewAutomationResult(**self._valid_auto_continue_kwargs())
        assert result.orchestration_status == "ready_for_future_transition"
        assert result.route == "automatic_continuation"

    def test_auto_rework_valid(self) -> None:
        kwargs = self._valid_auto_continue_kwargs()
        kwargs.update(route="bounded_automatic_rework", disposition_type="AUTO_REWORK",
                      handoff_kind="bounded_automatic_rework", transition_kind="BOUNDED_REWORK_GUARDRAIL")
        result = ProjectDirectorPostReviewAutomationResult(**kwargs)
        assert result.route == "bounded_automatic_rework"

    def test_auto_continue_requires_all_evidence_ids(self) -> None:
        kwargs = self._valid_auto_continue_kwargs()
        kwargs["source_handoff_message_id"] = None
        with pytest.raises(ValueError, match="完整 C1/C2/C3/E 证据绑定"):
            ProjectDirectorPostReviewAutomationResult(**kwargs)

    def test_auto_continue_no_human_package(self) -> None:
        kwargs = self._valid_auto_continue_kwargs()
        kwargs["source_human_escalation_package_message_id"] = uuid4()
        with pytest.raises(ValueError, match="不得绑定人工升级包"):
            ProjectDirectorPostReviewAutomationResult(**kwargs)

    def test_auto_continue_requires_automated_disposition_authority(self) -> None:
        kwargs = self._valid_auto_continue_kwargs()
        kwargs["transition_authority"] = "HUMAN_ESCALATION_DECISION"
        with pytest.raises(ValueError, match="自动 disposition 权限来源"):
            ProjectDirectorPostReviewAutomationResult(**kwargs)

    def test_auto_continue_requires_freshness(self) -> None:
        kwargs = self._valid_auto_continue_kwargs()
        kwargs["evidence_fresh"] = False
        with pytest.raises(ValueError, match="freshness guardrail"):
            ProjectDirectorPostReviewAutomationResult(**kwargs)

    def test_auto_continue_no_waiting_for_human(self) -> None:
        kwargs = self._valid_auto_continue_kwargs()
        kwargs["waiting_for_human"] = True
        with pytest.raises(ValueError, match="不得报告等待人工"):
            ProjectDirectorPostReviewAutomationResult(**kwargs)

    def test_auto_continue_no_blocked_reasons(self) -> None:
        kwargs = self._valid_auto_continue_kwargs()
        kwargs["blocked_reasons"] = ["x"]
        with pytest.raises(ValueError, match="不得包含 blocked 原因"):
            ProjectDirectorPostReviewAutomationResult(**kwargs)

    def test_disposition_route_transition_must_match(self) -> None:
        kwargs = self._valid_auto_continue_kwargs()
        kwargs["disposition_type"] = "AUTO_CONTINUE"
        kwargs["route"] = "bounded_automatic_rework"
        with pytest.raises(ValueError, match="disposition、route 与 transition 必须一致"):
            ProjectDirectorPostReviewAutomationResult(**kwargs)


# ══════════════════════════════════════════════════════════════════════
# 4. TestDomainHumanSuccess
# ══════════════════════════════════════════════════════════════════════


class TestDomainHumanSuccess:
    def _valid_human_kwargs(self) -> dict[str, Any]:
        return dict(
            orchestration_status="waiting_for_human",
            orchestration_id=uuid4(), route="human_escalation",
            current_step="human_escalation_package_prepared",
            source_review_message_id=uuid4(),
            source_disposition_message_id=uuid4(),
            source_human_escalation_package_message_id=uuid4(),
            disposition_type="ESCALATE_TO_HUMAN",
            waiting_for_human=True, human_escalation_package_created=True,
        )

    def test_human_valid(self) -> None:
        result = ProjectDirectorPostReviewAutomationResult(**self._valid_human_kwargs())
        assert result.orchestration_status == "waiting_for_human"
        assert result.route == "human_escalation"

    def test_human_requires_disposition_message(self) -> None:
        kwargs = self._valid_human_kwargs()
        kwargs["source_disposition_message_id"] = None
        with pytest.raises(ValueError, match="必须绑定 disposition message"):
            ProjectDirectorPostReviewAutomationResult(**kwargs)

    def test_human_requires_package_message(self) -> None:
        kwargs = self._valid_human_kwargs()
        kwargs["source_human_escalation_package_message_id"] = None
        with pytest.raises(ValueError, match="必须绑定 D1 package message"):
            ProjectDirectorPostReviewAutomationResult(**kwargs)

    def test_human_no_automatic_ids(self) -> None:
        kwargs = self._valid_human_kwargs()
        kwargs["source_consumption_preflight_message_id"] = uuid4()
        with pytest.raises(ValueError, match="不得绑定 C1/C2/C3/E"):
            ProjectDirectorPostReviewAutomationResult(**kwargs)

    def test_human_no_handoff_kind(self) -> None:
        kwargs = self._valid_human_kwargs()
        kwargs["handoff_kind"] = "automatic_continuation"
        with pytest.raises(ValueError, match="不得伪造自动转换信息"):
            ProjectDirectorPostReviewAutomationResult(**kwargs)

    def test_human_no_transition_kind(self) -> None:
        kwargs = self._valid_human_kwargs()
        kwargs["transition_kind"] = "CONTINUE_GUARDRAIL"
        with pytest.raises(ValueError, match="不得伪造自动转换信息"):
            ProjectDirectorPostReviewAutomationResult(**kwargs)

    def test_human_no_transition_authority(self) -> None:
        kwargs = self._valid_human_kwargs()
        kwargs["transition_authority"] = "AUTOMATED_DISPOSITION"
        with pytest.raises(ValueError, match="不得伪造自动转换信息"):
            ProjectDirectorPostReviewAutomationResult(**kwargs)

    def test_human_requires_waiting_for_human(self) -> None:
        kwargs = self._valid_human_kwargs()
        kwargs["waiting_for_human"] = False
        with pytest.raises(ValueError, match="必须报告等待人工"):
            ProjectDirectorPostReviewAutomationResult(**kwargs)

    def test_human_requires_package_created(self) -> None:
        kwargs = self._valid_human_kwargs()
        kwargs["human_escalation_package_created"] = False
        with pytest.raises(ValueError, match="D1 package 已创建"):
            ProjectDirectorPostReviewAutomationResult(**kwargs)

    def test_human_no_freshness(self) -> None:
        kwargs = self._valid_human_kwargs()
        kwargs["evidence_fresh"] = True
        with pytest.raises(ValueError, match="不得通过 freshness guardrail"):
            ProjectDirectorPostReviewAutomationResult(**kwargs)

    def test_human_no_blocked_reasons(self) -> None:
        kwargs = self._valid_human_kwargs()
        kwargs["blocked_reasons"] = ["x"]
        with pytest.raises(ValueError, match="不得包含 blocked 原因"):
            ProjectDirectorPostReviewAutomationResult(**kwargs)

    def test_human_requires_escalate_to_human_disposition(self) -> None:
        kwargs = self._valid_human_kwargs()
        kwargs["disposition_type"] = "AUTO_CONTINUE"
        with pytest.raises(ValueError, match="ESCALATE_TO_HUMAN disposition"):
            ProjectDirectorPostReviewAutomationResult(**kwargs)

    def test_human_requires_human_escalation_route(self) -> None:
        kwargs = self._valid_human_kwargs()
        kwargs["route"] = "automatic_continuation"
        with pytest.raises(ValueError, match="ESCALATE_TO_HUMAN disposition"):
            ProjectDirectorPostReviewAutomationResult(**kwargs)


# ══════════════════════════════════════════════════════════════════════
# 5. TestFalseOnlyFlags
# ══════════════════════════════════════════════════════════════════════


class TestFalseOnlyFlags:
    @pytest.mark.parametrize("flag", _P22_FALSE_FLAGS)
    def test_flag_rejected_when_true(self, flag: str) -> None:
        kwargs = dict(
            orchestration_status="blocked", orchestration_id=uuid4(),
            route="none", current_step="blocked", source_review_message_id=uuid4(),
            blocked_reasons=["x"],
        )
        kwargs[flag] = True
        with pytest.raises(ValueError, match="审查后编排不得执行转换或授权写入"):
            ProjectDirectorPostReviewAutomationResult(**kwargs)

    @pytest.mark.parametrize("flag", _P22_FALSE_FLAGS)
    def test_flag_accepted_when_false(self, flag: str) -> None:
        kwargs = dict(
            orchestration_status="blocked", orchestration_id=uuid4(),
            route="none", current_step="blocked", source_review_message_id=uuid4(),
            blocked_reasons=["x"],
        )
        kwargs[flag] = False
        result = ProjectDirectorPostReviewAutomationResult(**kwargs)
        assert getattr(result, flag) is False


# ══════════════════════════════════════════════════════════════════════
# 6-8. TestRouting
# ══════════════════════════════════════════════════════════════════════


class TestAutoContinueRouting:

    def test_full_chain_ready_for_future_transition(self, seeded_auto_continue) -> None:
        svc, session = _make_p22_service(seeded_auto_continue)
        result = svc.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        assert result.result.orchestration_status == "ready_for_future_transition", (
            f"blocked_reasons={result.result.blocked_reasons}"
        )
        assert result.result.route == "automatic_continuation"
        assert result.result.disposition_type == "AUTO_CONTINUE"
        session.close()




    def test_evidence_chain_bound(self, seeded_auto_continue) -> None:
        svc, session = _make_p22_service(seeded_auto_continue)
        result = svc.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        assert result.result.source_disposition_message_id is not None
        assert result.result.source_consumption_preflight_message_id is not None
        session.close()




    def test_summary_message_created(self, seeded_auto_continue) -> None:
        svc, session = _make_p22_service(seeded_auto_continue)
        result = svc.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        assert result.message is not None
        session.close()


class TestAutoReworkRouting:


    def test_full_chain_auto_rework(self, seeded_auto_rework) -> None:
        svc, session = _make_p22_service(seeded_auto_rework)
        result = svc.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        assert result.result.orchestration_status == "ready_for_future_transition"
        assert result.result.route == "bounded_automatic_rework"
        session.close()


class TestHumanEscalationRouting:

    def test_human_path_waiting_for_human(self, seeded_human_escalation) -> None:
        svc, session = _make_p22_service(seeded_human_escalation)
        result = svc.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        assert result.result.orchestration_status == "waiting_for_human"
        assert result.result.route == "human_escalation"
        session.close()


    def test_no_automatic_evidence_ids(self, seeded_human_escalation) -> None:
        svc, session = _make_p22_service(seeded_human_escalation)
        result = svc.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        assert result.result.source_consumption_preflight_message_id is None
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 9. TestStepBlocked
# ══════════════════════════════════════════════════════════════════════


class TestStepBlocked:
    def test_disposition_blocked_no_review_message(self, seeded_base_only) -> None:
        svc, session = _make_p22_service(seeded_base_only)
        result = svc.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        assert result.result.orchestration_status == "blocked"
        assert "post_review_disposition_blocked" in result.result.blocked_reasons
        session.close()

    def test_session_missing_raises(self, seeded_auto_continue) -> None:
        svc, session = _make_p22_service(seeded_auto_continue)
        with pytest.raises(ValueError, match="session not found"):
            svc.orchestrate_post_review(
                session_id=uuid4(), source_task_id=TASK_ID,
                source_review_message_id=SOURCE_REVIEW_MSG_ID,
            )
        session.close()

    def test_task_missing_raises(self, seeded_auto_continue) -> None:
        svc, session = _make_p22_service(seeded_auto_continue)
        with pytest.raises(ValueError, match="source task not found"):
            svc.orchestrate_post_review(
                session_id=SESSION_ID, source_task_id=uuid4(),
                source_review_message_id=SOURCE_REVIEW_MSG_ID,
            )
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 10. TestDispositionReplay
# ══════════════════════════════════════════════════════════════════════


class TestDispositionReplay:


    def test_sequential_replay_returns_same_result(self, seeded_auto_continue) -> None:
        svc, session = _make_p22_service(seeded_auto_continue)
        r1 = svc.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        assert r1.result.orchestration_status == "ready_for_future_transition"
        session.close()

        svc2, session2 = _make_p22_service(seeded_auto_continue)
        r2 = svc2.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        assert r2.result.resumed_from_existing_evidence is True
        session2.close()




    def test_different_review_message_id_fresh(self, seeded_auto_continue) -> None:
        svc, session = _make_p22_service(seeded_auto_continue)
        r1 = svc.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        assert r1.result.orchestration_status == "ready_for_future_transition"
        session.close()

        other_review_id = uuid4()
        session2 = seeded_auto_continue()
        _seed_review_message(session2, msg_id=other_review_id,
                            action=_valid_review_action(verdict="no_blocking_findings", risk_level="low"),
                            seq_no=51)
        session2.close()

        svc2, session3 = _make_p22_service(seeded_auto_continue)
        r2 = svc2.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=other_review_id,
        )
        assert r2.result.source_review_message_id == other_review_id
        session3.close()

    def test_blocked_replay_returns_blocked(self, seeded_base_only) -> None:
        svc, session = _make_p22_service(seeded_base_only)
        r1 = svc.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        assert r1.result.orchestration_status == "blocked"
        session.close()

        svc2, session2 = _make_p22_service(seeded_base_only)
        r2 = svc2.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        assert r2.result.orchestration_status == "blocked"
        assert r2.result.resumed_from_existing_evidence is True
        session2.close()


# ══════════════════════════════════════════════════════════════════════
# 11. TestSummaryReplay
# ══════════════════════════════════════════════════════════════════════


class TestSummaryReplay:

    def test_sequential_summary_replay(self, seeded_auto_continue) -> None:
        svc, session = _make_p22_service(seeded_auto_continue)
        r1 = svc.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        assert r1.message is not None
        session.close()

        svc2, session2 = _make_p22_service(seeded_auto_continue)
        r2 = svc2.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        assert r2.result.resumed_from_existing_evidence is True
        session2.close()

    def test_blocked_summary_replay(self, seeded_base_only) -> None:
        svc, session = _make_p22_service(seeded_base_only)
        r1 = svc.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        assert r1.result.orchestration_status == "blocked"
        session.close()

        svc2, session2 = _make_p22_service(seeded_base_only)
        r2 = svc2.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        assert r2.result.orchestration_status == "blocked"
        assert r2.result.resumed_from_existing_evidence is True
        session2.close()


# ══════════════════════════════════════════════════════════════════════
# 12-14. Cross-layer, chain binding, duplicate adoption
# ══════════════════════════════════════════════════════════════════════


class TestCrossLayerConsistency:

    def test_disposition_type_reflects_in_result(self, seeded_auto_continue) -> None:
        svc, session = _make_p22_service(seeded_auto_continue)
        result = svc.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        assert result.result.disposition_type == "AUTO_CONTINUE"
        session.close()


    def test_human_disposition_reflects_in_result(self, seeded_human_escalation) -> None:
        svc, session = _make_p22_service(seeded_human_escalation)
        result = svc.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        assert result.result.disposition_type == "ESCALATE_TO_HUMAN"
        session.close()


class TestExactChainBinding:


    def test_chain_message_ids_all_distinct(self, seeded_auto_continue) -> None:
        svc, session = _make_p22_service(seeded_auto_continue)
        result = svc.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        ids = [
            result.result.source_disposition_message_id,
            result.result.source_consumption_preflight_message_id,
            result.result.source_consumption_message_id,
            result.result.source_handoff_message_id,
            result.result.source_freshness_message_id,
        ]
        assert all(i is not None for i in ids)
        assert len(set(ids)) == 5
        session.close()


class TestDuplicateAdoption:


    def test_replay_after_first_call_adopts(self, seeded_auto_continue) -> None:
        svc, session = _make_p22_service(seeded_auto_continue)
        r1 = svc.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        assert r1.result.orchestration_status == "ready_for_future_transition"
        session.close()

        svc2, session2 = _make_p22_service(seeded_auto_continue)
        r2 = svc2.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        assert r2.result.resumed_from_existing_evidence is True
        session2.close()


# ══════════════════════════════════════════════════════════════════════
# 15. TestRuntimeException
# ══════════════════════════════════════════════════════════════════════


class TestRuntimeException:
    def test_session_missing_raises(self, seeded_auto_continue) -> None:
        svc, session = _make_p22_service(seeded_auto_continue)
        with pytest.raises(ValueError, match="session not found"):
            svc.orchestrate_post_review(
                session_id=uuid4(), source_task_id=TASK_ID,
                source_review_message_id=SOURCE_REVIEW_MSG_ID,
            )
        session.close()

    def test_task_missing_raises(self, seeded_auto_continue) -> None:
        svc, session = _make_p22_service(seeded_auto_continue)
        with pytest.raises(ValueError, match="source task not found"):
            svc.orchestrate_post_review(
                session_id=SESSION_ID, source_task_id=uuid4(),
                source_review_message_id=SOURCE_REVIEW_MSG_ID,
            )
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 16. TestSummaryMessageContract
# ══════════════════════════════════════════════════════════════════════


class TestSummaryMessageContract:

    def test_summary_message_metadata(self, seeded_auto_continue) -> None:
        svc, session = _make_p22_service(seeded_auto_continue)
        result = svc.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        assert result.message is not None
        msg = result.message
        assert msg.source_detail == P22_POST_REVIEW_AUTOMATION_SOURCE_DETAIL
        assert msg.source == ProjectDirectorMessageSource.SYSTEM
        assert msg.role == ProjectDirectorMessageRole.ASSISTANT
        assert msg.requires_confirmation is False
        assert msg.risk_level == ProjectDirectorMessageRiskLevel.HIGH
        assert msg.intent == "post_review_automation_orchestration"
        action = msg.suggested_actions[0]
        assert action["type"] == P22_POST_REVIEW_AUTOMATION_ACTION_TYPE
        assert action["schema_version"] == POST_REVIEW_AUTOMATION_SCHEMA_VERSION
        session.close()


    def test_summary_forbidden_actions_present(self, seeded_auto_continue) -> None:
        svc, session = _make_p22_service(seeded_auto_continue)
        result = svc.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        assert result.message is not None
        forbidden = result.message.forbidden_actions_detected
        assert "no_continuation_start" in forbidden
        assert "no_product_runtime_git_write" in forbidden
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 17. TestPermanentSafetyBoundary
# ══════════════════════════════════════════════════════════════════════


class TestPermanentSafetyBoundary:
    def test_all_false_flags_default_false(self) -> None:
        result = ProjectDirectorPostReviewAutomationResult(
            orchestration_status="blocked", orchestration_id=uuid4(),
            route="none", current_step="blocked",
            source_review_message_id=uuid4(), blocked_reasons=["x"],
        )
        for flag in _P22_FALSE_FLAGS:
            assert getattr(result, flag) is False

    def test_total_loop_always_partial(self) -> None:
        result = ProjectDirectorPostReviewAutomationResult(
            orchestration_status="blocked", orchestration_id=uuid4(),
            route="none", current_step="blocked",
            source_review_message_id=uuid4(), blocked_reasons=["x"],
        )
        assert result.ai_project_director_total_loop == "Partial"


    def test_auto_continue_result_all_false_flags(self, seeded_auto_continue) -> None:
        svc, session = _make_p22_service(seeded_auto_continue)
        result = svc.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        for flag in _P22_FALSE_FLAGS:
            assert getattr(result.result, flag) is False
        session.close()

    def test_blocked_result_all_false_flags(self, seeded_base_only) -> None:
        svc, session = _make_p22_service(seeded_base_only)
        result = svc.orchestrate_post_review(
            session_id=SESSION_ID, source_task_id=TASK_ID,
            source_review_message_id=SOURCE_REVIEW_MSG_ID,
        )
        for flag in _P22_FALSE_FLAGS:
            assert getattr(result.result, flag) is False
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 18. TestConcurrentOrchestration
# ══════════════════════════════════════════════════════════════════════


class TestConcurrentOrchestration:


    def test_two_threads_same_review(self, seeded_auto_continue) -> None:
        barrier = threading.Barrier(2, timeout=30)
        results: list[Any] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def _run() -> None:
            try:
                svc, session = _make_p22_service(seeded_auto_continue)
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
            assert r.result.orchestration_status == "ready_for_future_transition"

    def test_two_threads_blocked_no_error(self, seeded_base_only) -> None:
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
