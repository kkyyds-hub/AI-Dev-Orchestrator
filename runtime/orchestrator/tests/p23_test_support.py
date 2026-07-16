"""Shared test support for P23 protected transition tests."""

from __future__ import annotations

import hashlib
import json
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4, uuid5

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.db_tables import (
    ORMBase,
    ProjectDirectorMessageTable,
    ProjectDirectorSessionTable,
    ProjectTable,
    RunTable,
    TaskTable,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.run import (
    Run,
    RunBudgetPressureLevel,
    RunBudgetStrategyAction,
    RunRoutingScoreItem,
    RunStatus,
    RunStrategyDecision,
)
from app.domain.task import Task, TaskEventReason, TaskHumanStatus, TaskStatus
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.budget_guard_service import BudgetGuardDecision, BudgetGuardService
from app.services.project_director_protected_transition_dispatch_consumption_preflight_service import (
    ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService,
)
from app.services.project_director_protected_transition_dispatch_consumption_service import (
    ProjectDirectorProtectedTransitionDispatchConsumptionService,
)
from app.services.project_director_protected_transition_dispatch_intent_service import (
    P23_PROTECTED_TRANSITION_DISPATCH_INTENT_ACTION_TYPE,
    P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL,
    PROTECTED_TRANSITION_DISPATCH_INTENT_SCHEMA_VERSION,
    ProjectDirectorProtectedTransitionDispatchIntentService,
)
from app.services.project_director_protected_transition_evidence_freshness_service import (
    ProjectDirectorProtectedTransitionEvidenceFreshnessService,
    RevalidatedCurrentProtectedTransitionEvidenceFreshness,
)
from app.services.project_director_protected_transition_worker_start_reservation_service import (
    ProjectDirectorProtectedTransitionWorkerStartReservationService,
)
from app.services.task_readiness_service import TaskReadinessResult, TaskReadinessService
from app.services.task_router_service import TaskRouterService, TaskRoutingCandidate
from app.services.task_state_machine_service import (
    TaskStateMachineService,
    TaskStateTransition,
)
from app.workers.task_worker import (
    TaskWorker,
    WorkerReservedRunExecutionSnapshot,
    WorkerRunResult,
)


SHA256 = lambda data: hashlib.sha256(data).hexdigest()
DIFF_SHA256 = SHA256(b"diff content")
PROMPT_SHA256 = SHA256(b"prompt content")
RAW_OUTPUT_SHA256 = SHA256(b"raw output")
WORKSPACE_PATH = "/tmp/test-workspace-p23"
_FINGERPRINT = "a" * 64


def make_test_engine(tmp_path: str):
    engine = create_engine(
        f"sqlite:///{tmp_path}",
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


def make_session_factory(engine):
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


def seed_base_records(
    session: Session,
    *,
    project_id: UUID | None = None,
    session_id: UUID | None = None,
    task_id: UUID | None = None,
    task_status: str = "pending",
) -> dict[str, UUID]:
    pid = project_id or uuid4()
    sid = session_id or uuid4()
    tid = task_id or uuid4()
    session.add(
        ProjectTable(
            id=pid, name="Test", summary="Test project",
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
            id=tid, project_id=pid, title="Test task",
            status=task_status, priority="normal",
            input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
            risk_level="normal", human_status="none",
            source_draft_id="p12-test-draft", acceptance_criteria=acceptance,
        )
    )
    session.add(
        ProjectDirectorSessionTable(
            id=sid, project_id=pid,
            goal_text="Test goal", constraints="", status="confirmed",
        )
    )
    session.commit()
    return {"project_id": pid, "session_id": sid, "task_id": tid}


def make_repos(session_local):
    session = session_local()
    msg_repo = ProjectDirectorMessageRepository(session)
    sess_repo = ProjectDirectorSessionRepository(session)
    task_repo = TaskRepository(session)
    run_repo = RunRepository(session)
    agent_sess_repo = AgentSessionRepository(session)
    return session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo


def count_messages_by_source_detail(
    msg_repo: ProjectDirectorMessageRepository,
    session_id: UUID,
    source_detail: str,
) -> int:
    msgs, _ = msg_repo.list_by_session_id(session_id=session_id, limit=200)
    return sum(1 for m in msgs if m.source_detail == source_detail)


def get_messages_by_source_detail(
    msg_repo: ProjectDirectorMessageRepository,
    session_id: UUID,
    source_detail: str,
) -> list[ProjectDirectorMessage]:
    msgs, _ = msg_repo.list_by_session_id(session_id=session_id, limit=200)
    return [m for m in msgs if m.source_detail == source_detail]


# ── Deterministic Fakes ──────────────────────────────────────────────


@dataclass
class _FakePressure:
    value: str = "normal"


@dataclass
class _FakeAction:
    value: str = "allow"


@dataclass
class _FakeRetryStatus:
    retry_limit_reached: bool = False
    max_task_retries: int = 3
    execution_attempts: int = 0
    retries_used: int = 0
    retries_remaining: int = 3


@dataclass
class _FakeBudgetSnapshot:
    daily_budget_usd: float = 100.0
    daily_cost_used: float = 0.0
    daily_cost_remaining: float = 100.0
    daily_usage_ratio: float = 0.0
    daily_budget_exceeded: bool = False
    daily_window_started_at: Any = None
    session_budget_usd: float = 100.0
    session_cost_used: float = 0.0
    session_cost_remaining: float = 100.0
    session_usage_ratio: float = 0.0
    session_budget_exceeded: bool = False
    session_started_at: Any = None
    max_task_retries: int = 3
    strategy_code: str = "normal"
    strategy_label: str = "Normal"
    strategy_summary: str = "Normal execution"
    preferred_model_tier: str = "standard"
    budget_blocked_runs_daily: int = 0
    budget_blocked_runs_session: int = 0
    budget_policy_source: str = "test"
    per_run_budget_usd: float = 0.0
    estimated_run_cost_usd: float = 0.0

    @property
    def pressure_level(self):
        return _FakePressure()

    @property
    def suggested_action(self):
        return _FakeAction()


@dataclass
class FakeBudgetDecision:
    allowed: bool = True
    strategy_code: str = "normal"
    budget_policy_source: str = "test"
    summary: str | None = None
    failure_category: Any = None

    @property
    def pressure_level(self):
        return _FakePressure()

    @property
    def suggested_action(self):
        return _FakeAction()

    @property
    def retry_status(self):
        return _FakeRetryStatus()

    @property
    def budget(self):
        return _FakeBudgetSnapshot()


class FakeBudgetGuardService:
    def __init__(self, session=None, *, allowed=True):
        self._db_session = session
        self._allowed = allowed

    def evaluate_before_execution(self, *args, **kwargs):
        return FakeBudgetDecision(allowed=self._allowed)


class FakeTaskReadinessService:
    def __init__(self, *, ready=True):
        self._ready = ready

    def evaluate_task(self, *, task=None, **kwargs):
        return TaskReadinessResult(
            task_id=task.id if task else uuid4(),
            ready_for_execution=self._ready,
            blocking_signals=[],
            blocking_reasons=[],
            dependency_items=[],
        )


class FakeTaskStateMachineService:
    def build_claim_transition(self, *, task):
        return TaskStateTransition(
            status=TaskStatus.RUNNING,
            event_reason=TaskEventReason.CLAIMED,
            message="Task claimed",
            human_status=None,
            update_human_status=False,
            paused_reason=None,
            update_paused_reason=False,
        )

    def build_retry_transition(self, *, task):
        return TaskStateTransition(
            status=TaskStatus.PENDING,
            event_reason=TaskEventReason.RETRIED,
            message="Task retried",
            human_status=None,
            update_human_status=False,
            paused_reason=None,
            update_paused_reason=False,
        )


class FakeTaskRouterService:
    def evaluate_exact_task_for_dispatch(self, *, task):
        from app.domain.project_role import ProjectRoleCode
        return TaskRoutingCandidate(
            task=task,
            readiness=TaskReadinessResult(
                task_id=task.id,
                ready_for_execution=True,
                blocking_signals=[],
                blocking_reasons=[],
                dependency_items=[],
            ),
            ready=True,
            routing_score=1.0,
            route_reason="test",
            routing_score_breakdown=[RunRoutingScoreItem(code="test", label="Test", score=1.0, detail="test")],
            execution_attempts=0,
            recent_failure_count=0,
            budget_pressure_level=RunBudgetPressureLevel.NORMAL,
            budget_action=RunBudgetStrategyAction.FULL_SPEED,
            budget_strategy_code="normal",
            budget_score_adjustment=0.0,
            project_stage=None,
            owner_role_code=ProjectRoleCode.ARCHITECT,
            upstream_role_code=None,
            downstream_role_code=None,
            dispatch_status="dispatched",
            handoff_reason="test",
            matched_terms=(),
            model_name="test-model",
            model_tier=None,
            selected_skill_codes=(),
            selected_skill_names=(),
            strategy_code="normal",
            strategy_summary="Normal execution",
            strategy_reasons=[],
            strategy_decision=RunStrategyDecision(
                budget_pressure_level=RunBudgetPressureLevel.NORMAL,
                budget_action=RunBudgetStrategyAction.FULL_SPEED,
                strategy_code="normal",
                summary="Normal execution",
            ),
        )


class FakeFreshnessService:
    def __init__(self, session=None, *, blocked_reasons=None):
        self._blocked = blocked_reasons or []
        self._message_repository = type("R", (), {"_session": session})()
        self._task_repository = type("R", (), {"session": session})()

    def revalidate_current_automatic_transition_evidence_from_persisted_freshness(self, **kwargs):
        return RevalidatedCurrentProtectedTransitionEvidenceFreshness(
            freshness_status="ready" if not self._blocked else "blocked",
            source_freshness_message_id=kwargs.get("source_freshness_message_id", uuid4()),
            source_transition_message_id=None,
            source_review_message_id=None,
            source_diff_message_id=None,
            persisted_freshness_evidence_fingerprint=_FINGERPRINT,
            current_freshness_fingerprint=_FINGERPRINT,
            reviewed_diff_sha256=DIFF_SHA256,
            current_diff_sha256=DIFF_SHA256,
            reviewed_scope_paths=["src/example.py"],
            current_scope_paths=["src/example.py"],
            workspace_path=WORKSPACE_PATH,
            workspace_path_within_root=True,
            review_result_fingerprint=_FINGERPRINT,
            validated_at=datetime.now(timezone.utc),
            blocked_reasons=self._blocked,
        )

    def revalidate_persisted_protected_transition_evidence_freshness(self, **kwargs):
        return type("R", (), {
            "result": type("F", (), {
                "freshness_evidence_fingerprint": _FINGERPRINT,
                "source_diff_sha256": DIFF_SHA256,
                "review_scope_paths": ["src/example.py"],
                "workspace_path": WORKSPACE_PATH,
                "workspace_path_within_root": True,
                "validated_at": datetime.now(timezone.utc),
            })(),
            "blocked_reasons": [],
        })()


class FakeIntentService:
    """Deterministic fake that returns consistent IDs and fingerprints."""
    def __init__(self, session=None, *, intent_id=None, p22_summary_id=None, review_id=None, freshness_id=None, project_id=None, disposition_type="AUTO_CONTINUE", dispatch_kind="auto_continue"):
        self._message_repository = type("R", (), {"_session": session})()
        self._task_repository = type("R", (), {"session": session})()
        self._intent_id = intent_id or uuid4()
        self._p22_summary_id = p22_summary_id or uuid4()
        self._review_id = review_id or uuid4()
        self._freshness_id = freshness_id or uuid4()
        self._project_id = project_id
        self._disposition_type = disposition_type
        self._dispatch_kind = dispatch_kind

    def revalidate_persisted_protected_transition_dispatch_intent(self, **kwargs):
        pid = self._project_id or kwargs.get("project_id")
        transition_kind = "CONTINUE_GUARDRAIL" if self._disposition_type == "AUTO_CONTINUE" else "BOUNDED_REWORK_GUARDRAIL"
        target_strategy = "source_task_continue" if self._dispatch_kind == "auto_continue" else "source_task_rework"
        rework_index = 0
        return type("R", (), {
            "result": type("I", (), {
                "intent_status": "prepared",
                "intent_id": self._intent_id,
                "dispatch_intent_id": self._intent_id,
                "dispatch_intent_fingerprint": _FINGERPRINT,
                "project_id": pid,
                "target_task_id": kwargs.get("source_task_id"),
                "source_p22_summary_message_id": self._p22_summary_id,
                "source_review_message_id": self._review_id,
                "source_freshness_message_id": self._freshness_id,
                "disposition_type": self._disposition_type,
                "dispatch_kind": self._dispatch_kind,
                "target_task_strategy": target_strategy,
                "review_result_fingerprint": _FINGERPRINT,
                "review_semantic_fingerprint": _FINGERPRINT,
                "freshness_evidence_fingerprint": _FINGERPRINT,
                "source_diff_sha256": DIFF_SHA256,
                "review_scope_paths": ["src/example.py"],
                "workspace_path": WORKSPACE_PATH,
                "workspace_path_within_root": True,
                "rework_attempt_index": rework_index,
                "rework_attempt_limit": 3,
                "transition_kind": transition_kind,
                "transition_authority": "AUTOMATED_DISPOSITION",
                "source_freshness_validated_at": datetime.now(timezone.utc),
                "blocked_reasons": [],
            })(),
            "blocked_reasons": [],
        })()


def seed_intent_message(
    session: Session,
    *,
    session_id: UUID,
    task_id: UUID,
    project_id: UUID,
    intent_id: UUID | None = None,
    p22_summary_id: UUID | None = None,
    review_id: UUID | None = None,
    freshness_id: UUID | None = None,
    disposition_type: str = "AUTO_CONTINUE",
    dispatch_kind: str = "auto_continue",
    seq_no: int = 60,
) -> UUID:
    mid = intent_id or uuid4()
    action = {
        "type": P23_PROTECTED_TRANSITION_DISPATCH_INTENT_ACTION_TYPE,
        "schema_version": PROTECTED_TRANSITION_DISPATCH_INTENT_SCHEMA_VERSION,
        "session_id": str(session_id),
        "source_task_id": str(task_id),
        "intent_status": "prepared",
        "dispatch_intent_id": str(mid),
        "dispatch_intent_fingerprint": _FINGERPRINT,
        "project_id": str(project_id),
        "target_task_id": str(task_id),
        "source_p22_summary_message_id": str(p22_summary_id or uuid4()),
        "source_review_message_id": str(review_id or uuid4()),
        "source_disposition_message_id": str(uuid4()),
        "source_consumption_preflight_message_id": str(uuid4()),
        "source_consumption_message_id": str(uuid4()),
        "source_handoff_message_id": str(uuid4()),
        "source_freshness_message_id": str(freshness_id or uuid4()),
        "disposition_type": disposition_type,
        "transition_kind": "CONTINUE_GUARDRAIL" if disposition_type == "AUTO_CONTINUE" else "BOUNDED_REWORK_GUARDRAIL",
        "transition_authority": "AUTOMATED_DISPOSITION",
        "dispatch_kind": dispatch_kind,
        "target_task_strategy": "source_task_continue" if dispatch_kind == "auto_continue" else "source_task_rework",
        "review_result_fingerprint": _FINGERPRINT,
        "review_semantic_fingerprint": _FINGERPRINT,
        "freshness_evidence_fingerprint": _FINGERPRINT,
        "source_diff_sha256": DIFF_SHA256,
        "review_scope_paths": ["src/example.py"],
        "workspace_path": WORKSPACE_PATH,
        "workspace_path_within_root": True,
        "rework_attempt_index": 0,
        "rework_attempt_limit": 3,
        "replay_check_completed": True,
        "resumed_from_existing_intent": False,
        "blocked_reasons": [],
        "ai_project_director_total_loop": "Partial",
    }
    for flag in [
        "task_status_mutated", "task_created", "run_created", "worker_started",
        "runtime_started", "continuation_started", "rework_started", "worktree_created",
        "main_project_file_written", "sandbox_file_written", "manifest_file_written",
        "diff_file_written", "file_written", "patch_applied", "git_write_performed",
        "gate_allows_write", "product_runtime_git_write_allowed",
    ]:
        action[flag] = False
    session.add(
        ProjectDirectorMessageTable(
            id=mid, session_id=session_id, role="assistant",
            content="Dispatch intent prepared.", sequence_no=seq_no,
            intent="protected_transition_dispatch_intent",
            source="system",
            source_detail=P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False, risk_level="high",
            related_project_id=project_id, related_task_id=task_id,
        )
    )
    session.commit()
    return mid


def prepare_valid_preflight(
    session_local,
    *,
    session_id: UUID,
    task_id: UUID,
    project_id: UUID,
    intent_id: UUID | None = None,
    p22_summary_id: UUID | None = None,
    review_id: UUID | None = None,
    freshness_id: UUID | None = None,
    disposition_type: str = "AUTO_CONTINUE",
    dispatch_kind: str = "auto_continue",
) -> tuple[UUID, Any, Any, Any, Any, Any]:
    """Create a real persisted P23-C preflight using real service with deterministic fakes.

    Returns (preflight_message_id, session, msg_repo, task_repo, run_repo, preflight_svc).
    """
    intent_id = intent_id or uuid4()
    p22_summary_id = p22_summary_id or uuid4()
    review_id = review_id or uuid4()
    freshness_id = freshness_id or uuid4()

    session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)

    # Seed the intent message that the preflight service will revalidate
    seed_intent_message(
        session,
        session_id=session_id, task_id=task_id, project_id=project_id,
        intent_id=intent_id, p22_summary_id=p22_summary_id,
        review_id=review_id, freshness_id=freshness_id,
        disposition_type=disposition_type, dispatch_kind=dispatch_kind,
    )

    # Create deterministic fakes
    intent_svc = FakeIntentService(
        session=session,
        intent_id=intent_id, p22_summary_id=p22_summary_id,
        review_id=review_id, freshness_id=freshness_id,
        project_id=project_id,
        disposition_type=disposition_type, dispatch_kind=dispatch_kind,
    )
    intent_svc._message_repository = msg_repo
    intent_svc._task_repository = task_repo

    freshness_svc = FakeFreshnessService(session=session)
    freshness_svc._message_repository = msg_repo
    freshness_svc._task_repository = task_repo

    budget_svc = FakeBudgetGuardService(session=session)
    readiness_svc = FakeTaskReadinessService()
    state_machine_svc = FakeTaskStateMachineService()

    preflight_svc = ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        dispatch_intent_service=intent_svc,
        freshness_service=freshness_svc,
        task_readiness_service=readiness_svc,
        task_state_machine_service=state_machine_svc,
        budget_guard_service=budget_svc,
    )

    result = preflight_svc.prepare_protected_transition_dispatch_consumption_preflight(
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=intent_id,
    )
    assert result.message is not None, f"Preflight failed: {result.result.blocked_reasons}"
    return result.message.id, session, msg_repo, task_repo, run_repo, preflight_svc


def make_d1_service(
    session_local,
    *,
    preflight_svc=None,
    session_obj=None,
    msg_repo=None,
    task_repo=None,
    run_repo=None,
    budget_allowed=True,
    task_ready=True,
):
    """Create a real D1 service with real repos and deterministic fakes."""
    if msg_repo is None:
        session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
    else:
        session = msg_repo._session
        sess_repo = ProjectDirectorSessionRepository(session)
        agent_sess_repo = AgentSessionRepository(session)

    if preflight_svc is None:
        intent_svc = FakeIntentService(session=session)
        intent_svc._message_repository = msg_repo
        intent_svc._task_repository = task_repo
        freshness_svc = FakeFreshnessService(session=session)
        freshness_svc._message_repository = msg_repo
        freshness_svc._task_repository = task_repo
        preflight_svc = ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
            dispatch_intent_service=intent_svc,
            freshness_service=freshness_svc,
            task_readiness_service=FakeTaskReadinessService(ready=task_ready),
            task_state_machine_service=FakeTaskStateMachineService(),
            budget_guard_service=FakeBudgetGuardService(session=session, allowed=budget_allowed),
        )

    d1_svc = ProjectDirectorProtectedTransitionDispatchConsumptionService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        run_repository=run_repo,
        preflight_service=preflight_svc,
        task_readiness_service=FakeTaskReadinessService(ready=task_ready),
        task_state_machine_service=FakeTaskStateMachineService(),
        task_router_service=FakeTaskRouterService(),
        budget_guard_service=FakeBudgetGuardService(session=session, allowed=budget_allowed),
    )
    return d1_svc, session, msg_repo, task_repo, run_repo


def make_b1_service(
    session_local,
    *,
    msg_repo=None,
    task_repo=None,
    run_repo=None,
    agent_sess_repo=None,
    d1_service=None,
    budget_allowed=True,
    freshness_blocked=None,
):
    """Create a real B1 service with real repos and deterministic fakes."""
    if msg_repo is None:
        session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
    else:
        session = msg_repo._session
        sess_repo = ProjectDirectorSessionRepository(session)
        if agent_sess_repo is None:
            agent_sess_repo = AgentSessionRepository(session)

    freshness_svc = FakeFreshnessService(session=session, blocked_reasons=freshness_blocked)
    freshness_svc._message_repository = msg_repo
    freshness_svc._task_repository = task_repo

    # D1 service needs to share repos for the shared session check
    d1_msg_repo = msg_repo
    d1_task_repo = task_repo
    d1_run_repo = run_repo

    if d1_service is None:
        # Create a real D1 service for the B1 to use for revalidation
        intent_svc = FakeIntentService(session=session)
        intent_svc._message_repository = msg_repo
        intent_svc._task_repository = task_repo
        freshness_svc_inner = FakeFreshnessService(session=session)
        freshness_svc_inner._message_repository = msg_repo
        freshness_svc_inner._task_repository = task_repo
        preflight_svc_inner = ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
            dispatch_intent_service=intent_svc,
            freshness_service=freshness_svc_inner,
            task_readiness_service=FakeTaskReadinessService(),
            task_state_machine_service=FakeTaskStateMachineService(),
            budget_guard_service=FakeBudgetGuardService(session=session, allowed=budget_allowed),
        )
        d1_service = ProjectDirectorProtectedTransitionDispatchConsumptionService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
            run_repository=run_repo,
            preflight_service=preflight_svc_inner,
            task_readiness_service=FakeTaskReadinessService(),
            task_state_machine_service=FakeTaskStateMachineService(),
            task_router_service=FakeTaskRouterService(),
            budget_guard_service=FakeBudgetGuardService(session=session, allowed=budget_allowed),
        )

    b1_svc = ProjectDirectorProtectedTransitionWorkerStartReservationService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        run_repository=run_repo,
        agent_session_repository=agent_sess_repo,
        dispatch_consumption_service=d1_service,
        freshness_service=freshness_svc,
        budget_guard_service=FakeBudgetGuardService(session=session, allowed=budget_allowed),
    )
    return b1_svc, session, msg_repo, task_repo, run_repo, agent_sess_repo


# ── Event Spy ────────────────────────────────────────────────────────


class EventSpy:
    """Intercept event_stream_service.publish_task_updated and RunRepository.publish_created.

    Each callback opens a new SQLAlchemy Session against the same SQLite file
    to verify that committed state is visible at event time.
    """

    def __init__(self, session_factory):
        self._sf = session_factory
        self.task_events: list[dict[str, Any]] = []
        self.run_events: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._task_event_count = 0
        self._run_event_count = 0

    @property
    def task_event_count(self) -> int:
        with self._lock:
            return self._task_event_count

    @property
    def run_event_count(self) -> int:
        with self._lock:
            return self._run_event_count

    def on_task_updated(self, *, task, reason, previous_status=None):
        """Called in place of event_stream_service.publish_task_updated."""
        with self._lock:
            self._task_event_count += 1
            # Open a new session to verify committed state
            s = self._sf()
            from app.core.db_tables import TaskTable, RunTable, ProjectDirectorMessageTable
            from app.domain.task import TaskStatus
            from app.services.project_director_protected_transition_dispatch_consumption_service import (
                P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL,
            )
            observed_task = s.get(TaskTable, task.id)
            observed_task_status = observed_task.status if observed_task else None
            runs = s.query(RunTable).filter(RunTable.task_id == task.id).all()
            run_count = len(runs)
            d1_msgs = (
                s.query(ProjectDirectorMessageTable)
                .filter(
                    ProjectDirectorMessageTable.session_id == task.session_id
                    if hasattr(task, "session_id") else True,
                    ProjectDirectorMessageTable.source_detail == P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL,
                )
                .all()
            )
            d1_count = len(d1_msgs)
            s.close()
            self.task_events.append({
                "task_id": str(task.id),
                "observed_task_status": observed_task_status,
                "observed_run_count": run_count,
                "observed_d1_count": d1_count,
            })

    def on_run_created(self, *, run, reason):
        """Called in place of RunRepository.publish_created."""
        with self._lock:
            self._run_event_count += 1
            s = self._sf()
            from app.core.db_tables import RunTable, ProjectDirectorMessageTable
            from app.services.project_director_protected_transition_dispatch_consumption_service import (
                P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL,
            )
            observed_run = s.get(RunTable, run.id)
            run_exists = observed_run is not None
            d1_msgs = (
                s.query(ProjectDirectorMessageTable)
                .filter(
                    ProjectDirectorMessageTable.source_detail == P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL,
                )
                .all()
            )
            d1_count = len(d1_msgs)
            s.close()
            self.run_events.append({
                "run_id": str(run.id),
                "run_exists": run_exists,
                "observed_d1_count": d1_count,
            })

    def install(self, d1_service, run_repository):
        """Monkey-patch the D1 service and run repository to intercept events."""
        self._orig_publish = d1_service._publish_committed_reservation
        self._orig_publish_created = run_repository.publish_created

        def spy_publish(result):
            task = d1_service._task_repository.get_by_id(result.source_task_id)
            run = d1_service._run_repository.get_by_id(result.run_id)
            if task is None or run is None:
                return
            self.on_task_updated(task=task, reason="claimed", previous_status=result.task_status_before)
            self.on_run_created(run=run, reason="created")

        d1_service._publish_committed_reservation = spy_publish
        run_repository.publish_created = lambda run: None  # suppress double publish

    def restore(self, d1_service, run_repository):
        """Restore original methods."""
        if hasattr(self, "_orig_publish"):
            d1_service._publish_committed_reservation = self._orig_publish
        if hasattr(self, "_orig_publish_created"):
            run_repository.publish_created = self._orig_publish_created


# ── Exploding Spies for B1 Persisted Finder ──────────────────────────


class ExplodingFreshnessService:
    """Raises AssertionError if any current-check method is called."""

    def __init__(self, *, session=None, msg_repo=None, task_repo=None):
        self._session = session
        self._message_repository = msg_repo or type("R", (), {"_session": session})()
        self._task_repository = task_repo or type("R", (), {"session": session})()

    def revalidate_current_automatic_transition_evidence_from_persisted_freshness(self, **kwargs):
        raise AssertionError("persisted finder must not call current freshness check")

    def revalidate_persisted_protected_transition_evidence_freshness(self, **kwargs):
        raise AssertionError("persisted finder must not call persisted freshness revalidation")


class ExplodingBudgetGuardService:
    """Raises AssertionError if evaluate_before_execution is called."""

    def __init__(self, session=None):
        self._db_session = session

    def evaluate_before_execution(self, *args, **kwargs):
        raise AssertionError("persisted finder must not call budget check")


class ExplodingAgentSessionRepository:
    """Raises AssertionError if get_by_run_id is called."""

    def __init__(self, session=None):
        self.session = session
        self._called = False

    def get_by_run_id(self, run_id):
        self._called = True
        raise AssertionError("persisted finder must not call AgentSession absence lookup")

    def get_by_id(self, sid):
        return None


# ── TaskWorker Helpers ───────────────────────────────────────────────


class SpySharedExecutionHelper:
    """Intercepts _execute_running_task_run on a TaskWorker instance."""

    def __init__(self):
        self.call_count = 0
        self.calls: list[dict[str, Any]] = []
        self._orig = None

    def install(self, worker: Any) -> None:
        self._orig = worker._execute_running_task_run

        def spy(*, task, run, routing_decision, reserved_snapshot):
            self.call_count += 1
            self.calls.append({
                "task_id": task.id,
                "run_id": run.id,
                "reserved_snapshot": reserved_snapshot,
            })
            # Return a minimal valid result without entering real execution
            return WorkerRunResult(
                claimed=True,
                message="spy-executed",
                execution_mode="spy",
                route_reason=run.route_reason,
                routing_score=run.routing_score,
                model_name=run.model_name,
                strategy_code=run.strategy_decision.strategy_code if run.strategy_decision else None,
                dispatch_status=run.dispatch_status,
                reserved_run_execution_snapshot=reserved_snapshot,
            )

        worker._execute_running_task_run = spy

    def restore(self, worker: Any) -> None:
        if self._orig is not None:
            worker._execute_running_task_run = self._orig


class ExplodingTaskRouterService:
    """Raises AssertionError if route_next_task is called."""

    def route_next_task(self, **kwargs):
        raise AssertionError("reserved path must not call route_next_task")


class ExplodingRunCreationService:
    """Raises if Run creation methods are called."""

    def add_running_run_no_event(self, **kwargs):
        raise AssertionError("reserved path must not create Run")

    def create_running_run(self, **kwargs):
        raise AssertionError("reserved path must not create Run")


class SpyAgentConversationService:
    """Minimal fake for AgentConversationService used by TaskWorker."""

    def __init__(self, session=None, agent_session_repository=None):
        self.agent_session_repository = agent_session_repository or type("R", (), {
            "session": session,
            "get_by_run_id": lambda self, rid: None,
            "get_by_id": lambda self, sid: None,
        })()

    def start_session(self, **kwargs):
        raise AssertionError("spy should not reach start_session")

    def record_execution_started(self, **kwargs):
        raise AssertionError("spy should not reach record_execution_started")


def make_task_worker(
    session,
    *,
    task_repo,
    run_repo,
    agent_sess_repo=None,
    budget_guard_service=None,
    task_router_service=None,
):
    """Create a real TaskWorker with real repos and minimal fakes for external services."""
    from app.services.agent_conversation_service import AgentConversationService
    from app.services.cost_estimator_service import CostEstimatorService
    from app.services.context_builder_service import ContextBuilderService
    from app.services.executor_service import ExecutorService
    from app.services.failure_review_service import FailureReviewService
    from app.services.model_routing_service import ModelRoutingService
    from app.services.prompt_builder_service import PromptBuilderService
    from app.services.run_logging_service import RunLoggingService
    from app.services.token_accounting_service import TokenAccountingService
    from app.services.verifier_service import VerifierService

    if agent_sess_repo is None:
        agent_sess_repo = AgentSessionRepository(session)
    if budget_guard_service is None:
        budget_guard_service = FakeBudgetGuardService(session=session)
    if task_router_service is None:
        task_router_service = ExplodingTaskRouterService()

    agent_conv = SpyAgentConversationService(
        session=session, agent_session_repository=agent_sess_repo,
    )

    worker = TaskWorker(
        session=session,
        task_repository=task_repo,
        run_repository=run_repo,
        executor_service=type("F", (), {"execute": lambda s, **kw: None})(),
        verifier_service=type("F", (), {"verify": lambda s, **kw: None})(),
        budget_guard_service=budget_guard_service,
        run_logging_service=type("F", (), {
            "append_event": lambda s, **kw: None,
            "append_role_handoff_event": lambda s, **kw: None,
            "initialize_run_log": lambda s, **kw: f"/tmp/test-log-{kw.get('run_id', 'x')}.jsonl",
        })(),
        cost_estimator_service=CostEstimatorService(),
        context_builder_service=type("F", (), {
            "build_context_package": lambda s, **kw: type("P", (), {"context_items": []})(),
            "build_agent_thread_context_seed": lambda s, **kw: None,
        })(),
        task_router_service=task_router_service,
        model_routing_service=type("F", (), {"resolve": lambda s, **kw: None})(),
        prompt_registry_service=None,
        prompt_builder_service=type("F", (), {"build": lambda s, **kw: None})(),
        token_accounting_service=TokenAccountingService(),
        task_state_machine_service=TaskStateMachineService(),
        failure_review_service=type("F", (), {"ensure_review": lambda s, **kw: None})(),
        agent_conversation_service=agent_conv,
    )
    return worker


def prepare_valid_b1_reservation(
    session_local,
    *,
    session_id: UUID,
    task_id: UUID,
    project_id: UUID,
    disposition_type: str = "AUTO_CONTINUE",
    dispatch_kind: str = "auto_continue",
):
    """Create a full D1→B1 chain and return all references.

    Returns dict with: sf, session, msg_repo, task_repo, run_repo, agent_sess_repo,
    d1_svc, b1_svc, ids, preflight_msg_id, d1_result, b1_result.
    """
    ids = {"session_id": session_id, "task_id": task_id, "project_id": project_id}

    # Seed base records first (project, task, session)
    s = session_local()
    seed_base_records(
        s,
        project_id=project_id, session_id=session_id, task_id=task_id,
        task_status="pending",
    )
    s.close()

    preflight_msg_id, session, msg_repo, task_repo, run_repo, preflight_svc = (
        prepare_valid_preflight(
            session_local,
            session_id=session_id, task_id=task_id, project_id=project_id,
            disposition_type=disposition_type, dispatch_kind=dispatch_kind,
        )
    )
    agent_sess_repo = AgentSessionRepository(session)
    session.close()

    d1_svc, session, msg_repo, task_repo, run_repo = make_d1_service(
        session_local, preflight_svc=preflight_svc,
        msg_repo=msg_repo, task_repo=task_repo, run_repo=run_repo,
    )
    d1_result = d1_svc.consume_protected_transition_dispatch_preflight(
        session_id=session_id, source_task_id=task_id,
        source_message_id=preflight_msg_id,
    )
    assert d1_result.result.consumption_status == "reserved_for_worker_start"
    session.close()

    b1_svc, session, msg_repo, task_repo, run_repo, agent_sess_repo = make_b1_service(
        session_local,
        msg_repo=msg_repo, task_repo=task_repo, run_repo=run_repo,
        d1_service=d1_svc,
    )
    b1_result = b1_svc.prepare_protected_transition_worker_start_reservation(
        session_id=session_id, source_task_id=task_id,
        source_message_id=d1_result.message.id,
    )
    assert b1_result.result.reservation_status == "reserved"
    session.close()

    return {
        "sf": session_local,
        "session": session,
        "msg_repo": msg_repo,
        "task_repo": task_repo,
        "run_repo": run_repo,
        "agent_sess_repo": agent_sess_repo,
        "d1_svc": d1_svc,
        "b1_svc": b1_svc,
        "ids": ids,
        "preflight_msg_id": preflight_msg_id,
        "d1_result": d1_result,
        "b1_result": b1_result,
    }


# ── D3 Full-Stack Helpers ────────────────────────────────────────────

from app.services.project_director_sandbox_candidate_diff_review_disposition_service import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionService,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL,
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
from app.services.project_director_post_review_automation_service import (
    ProjectDirectorPostReviewAutomationService,
    P22_POST_REVIEW_AUTOMATION_SOURCE_DETAIL,
)
from app.services.project_director_protected_transition_worker_invocation_service import (
    ProjectDirectorProtectedTransitionWorkerInvocationService,
    P23_PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL,
    P23_PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_candidate_diff_readonly_review_execution_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_candidate_diff_review_execution_preflight_service import (
    REVIEW_OUTPUT_SCHEMA_VERSION,
)
from app.services.project_director_protected_transition_dispatch_intent_service import (
    P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL,
)
from app.services.project_director_protected_transition_dispatch_consumption_preflight_service import (
    P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL,
)
from app.services.project_director_protected_transition_dispatch_consumption_service import (
    P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL,
)
from app.services.project_director_protected_transition_worker_start_reservation_service import (
    P23_PROTECTED_TRANSITION_WORKER_START_RESERVATION_SOURCE_DETAIL,
)
from app.services.project_director_protected_transition_auto_advance_service import (
    ProjectDirectorProtectedTransitionAutoAdvanceService,
)


_SHA256 = lambda data: hashlib.sha256(data).hexdigest()
_DIFF_SHA256 = _SHA256(b"diff content")
_PROMPT_SHA256 = _SHA256(b"prompt content")
_RAW_OUTPUT_SHA256 = _SHA256(b"raw output")
_WORKSPACE_PATH = "/tmp/test-workspace-p23-d3"


def _valid_review_action_d3(
    *,
    verdict: str = "no_blocking_findings",
    risk_level: str = "low",
    session_id: UUID | None = None,
    task_id: UUID | None = None,
) -> dict[str, Any]:
    action: dict[str, Any] = {
        "type": P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
        "session_id": str(session_id or uuid4()),
        "source_task_id": str(task_id or uuid4()),
        "source_preflight_message_id": str(uuid4()),
        "source_diff_message_id": str(uuid4()),
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
    return action


def _seed_p21_c_review_chain(
    session: Session,
    *,
    session_id: UUID,
    task_id: UUID,
    project_id: UUID,
    review_msg_id: UUID | None = None,
    verdict: str = "no_blocking_findings",
    risk_level: str = "low",
    seq_no: int = 50,
) -> UUID:
    """Seed P21-C review message + candidate write + diff messages."""
    review_msg_id = review_msg_id or uuid4()
    write_msg_id = uuid4()
    diff_msg_id = uuid4()

    # Candidate write message
    write_action = {
        "type": "p21_c_sandbox_candidate_files_write_record",
        "session_id": str(session_id),
        "source_task_id": str(task_id),
        "workspace_path": _WORKSPACE_PATH,
    }
    session.add(
        ProjectDirectorMessageTable(
            id=write_msg_id, session_id=session_id, role="assistant",
            content="Candidate files written.", sequence_no=30,
            intent="sandbox_candidate_files_write",
            source="system", source_detail="p21_c_sandbox_candidate_files_write_executed",
            suggested_actions_json=json.dumps([write_action]),
            requires_confirmation=False, risk_level="high",
            related_project_id=project_id, related_task_id=task_id,
        )
    )

    # Diff message
    diff_action = {
        "type": "p21_c_sandbox_candidate_diff_record",
        "session_id": str(session_id),
        "source_task_id": str(task_id),
        "source_message_id": str(write_msg_id),
        "workspace_path": _WORKSPACE_PATH,
        "workspace_path_within_root": True,
        "diff_generation_status": "generated",
        "readonly_real_diff_generated": True,
        "real_diff_generated": True,
        "diff_file_count": 1,
        "diff_bytes": 100,
        "unified_diff_text": "diff content",
        "diff_entries": [{"relative_path": "src/example.py", "unified_diff": "diff content"}],
    }
    for flag in [
        "main_project_file_written", "sandbox_file_written", "manifest_file_written",
        "diff_file_written", "patch_applied", "git_write_performed",
        "worktree_created", "worker_started", "task_created", "run_created",
    ]:
        diff_action[flag] = False
    session.add(
        ProjectDirectorMessageTable(
            id=diff_msg_id, session_id=session_id, role="assistant",
            content="Candidate diff generated.", sequence_no=35,
            intent="sandbox_candidate_diff",
            source="system", source_detail="p21_c_sandbox_candidate_diff_generated",
            suggested_actions_json=json.dumps([diff_action]),
            requires_confirmation=False, risk_level="high",
            related_project_id=project_id, related_task_id=task_id,
        )
    )

    # Review message - use the actual diff message ID
    action = _valid_review_action_d3(
        verdict=verdict, risk_level=risk_level,
        session_id=session_id, task_id=task_id,
    )
    action["source_diff_message_id"] = str(diff_msg_id)
    action["source_preflight_message_id"] = str(write_msg_id)
    session.add(
        ProjectDirectorMessageTable(
            id=review_msg_id, session_id=session_id, role="assistant",
            content="Readonly review executed.", sequence_no=seq_no,
            intent="sandbox_candidate_diff_readonly_review_execution",
            source="system",
            source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False, risk_level="high",
            related_project_id=project_id, related_task_id=task_id,
        )
    )
    session.commit()
    return review_msg_id


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


def _make_p22_service(session, msg_repo, sess_repo, task_repo):
    """Create a real P22 service with all real sub-services."""
    return ProjectDirectorPostReviewAutomationService(
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


def make_real_d3_stack(
    session_local,
    *,
    session_id: UUID,
    task_id: UUID,
    project_id: UUID,
    verdict: str = "no_blocking_findings",
    risk_level: str = "low",
    disposition_type: str = "AUTO_CONTINUE",
    dispatch_kind: str = "auto_continue",
    fake_worker=None,
):
    """Build a full D3 stack with real services and shared repositories.

    Returns dict with all services, repos, IDs, and the fake worker.
    """
    # Seed base records
    s = session_local()
    seed_base_records(
        s,
        project_id=project_id, session_id=session_id, task_id=task_id,
        task_status="pending",
    )
    review_msg_id = _seed_p21_c_review_chain(
        s,
        session_id=session_id, task_id=task_id, project_id=project_id,
        verdict=verdict, risk_level=risk_level,
    )
    s.close()

    # Create shared repos
    session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)

    # P22 service
    p22_svc = _make_p22_service(session, msg_repo, sess_repo, task_repo)

    # P23-B intent service
    freshness_svc = ProjectDirectorProtectedTransitionEvidenceFreshnessService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        review_handoff_service=_StubHandoff(),
        candidate_diff_service=_StubDiff(),
    )
    intent_svc = ProjectDirectorProtectedTransitionDispatchIntentService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
    )

    # P23-C preflight service - use real intent service for D3 stack
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

    # D1 service
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

    # B1 service
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

    # B2 service
    if fake_worker is None:
        fake_worker = FakeTaskWorker(session=session)
    else:
        fake_worker.session = session
    b2_svc = ProjectDirectorProtectedTransitionWorkerInvocationService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        run_repository=run_repo,
        agent_session_repository=agent_sess_repo,
        worker_start_reservation_service=b1_svc,
        freshness_service=freshness_svc,
        task_worker=fake_worker,
    )

    # D3 service
    d3_svc = ProjectDirectorProtectedTransitionAutoAdvanceService(
        post_review_automation_service=p22_svc,
        dispatch_intent_service=intent_svc,
        dispatch_consumption_preflight_service=preflight_svc,
        dispatch_consumption_service=d1_svc,
        worker_start_reservation_service=b1_svc,
        worker_invocation_service=b2_svc,
    )

    return {
        "session": session,
        "msg_repo": msg_repo,
        "sess_repo": sess_repo,
        "task_repo": task_repo,
        "run_repo": run_repo,
        "agent_sess_repo": agent_sess_repo,
        "p22_svc": p22_svc,
        "intent_svc": intent_svc,
        "preflight_svc": preflight_svc,
        "d1_svc": d1_svc,
        "b1_svc": b1_svc,
        "b2_svc": b2_svc,
        "d3_svc": d3_svc,
        "fake_worker": fake_worker,
        "session_id": session_id,
        "task_id": task_id,
        "project_id": project_id,
        "review_msg_id": review_msg_id,
    }


class FakeTaskWorker:
    """Fake TaskWorker for B2/D3 tests. Records calls and returns controlled results."""

    def __init__(self, *, session=None, result=None, exception=None):
        self.session = session
        self._result = result
        self._exception = exception
        self.run_reserved_once_calls: list[dict] = []
        self.run_once_calls: list[dict] = []
        self._call_lock = threading.Lock()

    def run_reserved_once(self, *, task_id, run_id):
        with self._call_lock:
            self.run_reserved_once_calls.append({"task_id": task_id, "run_id": run_id})
        if self._exception:
            raise self._exception
        return self._result

    def run_once(self, *, project_id=None):
        with self._call_lock:
            self.run_once_calls.append({"project_id": project_id})
        return None


def make_d3_worker_result(
    *,
    task_id: UUID,
    run_id: UUID,
    disposition_type: str = "AUTO_CONTINUE",
    git_activity: bool = False,
    contract_valid: bool = True,
):
    """Build a valid WorkerRunResult with reserved snapshot for D3 tests."""
    snapshot = WorkerReservedRunExecutionSnapshot(
        source="p23_d2_exact_reserved_run" if contract_valid else "invalid_source",
        exact_task_id=task_id if contract_valid else uuid4(),
        exact_run_id=run_id if contract_valid else uuid4(),
        reserved_run_execution_requested=contract_valid,
        exact_binding_validated=contract_valid,
        task_routed=not contract_valid,
        task_claimed_in_this_cycle=not contract_valid,
        run_created_in_this_cycle=not contract_valid,
        budget_rechecked=contract_valid,
        existing_run_reused=contract_valid,
        shared_execution_seam_used=contract_valid,
        product_runtime_git_write_allowed=not contract_valid,
        blocked_reasons=[],
    )
    result = WorkerRunResult(
        claimed=True,
        message="fake worker executed",
        execution_mode="fake",
        result_summary="fake execution",
        reserved_run_execution_snapshot=snapshot,
    )
    if git_activity:
        from dataclasses import replace
        result = replace(result, git_diff_dry_run_runs_write_git=True)
    return result


def count_p23_evidence(msg_repo, session_id):
    """Count all P22/P23 evidence messages."""
    msgs, _ = msg_repo.list_by_session_id(session_id=session_id, limit=500)
    counts = {}
    for sd in [
        P22_POST_REVIEW_AUTOMATION_SOURCE_DETAIL,
        P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL,
        P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL,
        P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL,
        P23_PROTECTED_TRANSITION_WORKER_START_RESERVATION_SOURCE_DETAIL,
        P23_PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL,
        P23_PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL,
    ]:
        counts[sd] = sum(1 for m in msgs if m.source_detail == sd)
    return counts


# ══════════════════════════════════════════════════════════════════════
# P25 AUTO_REWORK D3 Stack (real P25 authority chain)
# ══════════════════════════════════════════════════════════════════════


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def make_p25_auto_rework_d3_stack(
    session_local,
    *,
    session_id: UUID | None = None,
    task_id: UUID | None = None,
    project_id: UUID | None = None,
    fake_worker=None,
    rework_attempt_index: int = 1,
):
    """Build a full P25 AUTO_REWORK D3 stack with real P25 authority chain.

    Creates: P25 candidate diff → P25 review outcome → P22 summary
    → P25 convergence NEXT_ATTEMPT_ELIGIBLE → P23 intent with P25 authority
    → D3 stack ready for advance_post_review_protected_transition.

    Returns dict with all services, repos, IDs, fake worker, and P25 evidence.
    """
    # Deferred imports to avoid circular import at module level
    from app.domain.project_director_bounded_rework_contract import (
        ProjectDirectorBoundedReworkAuthorityEnvelope,
    )
    from app.domain.project_director_bounded_rework_review_reentry import (
        P25_BOUNDED_REWORK_REVIEW_OUTCOME_NAMESPACE,
        P25_BOUNDED_REWORK_REVIEW_OUTPUT_SCHEMA_VERSION,
        ProjectDirectorBoundedReworkReviewInvocationOutcome,
    )
    from app.domain.project_director_sandbox_candidate_diff_readonly_reviewer_adapter import (
        ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult,
    )
    from app.domain.project_director_sandbox_candidate_diff_review_output import (
        ProjectDirectorSandboxCandidateDiffReviewFinding,
    )
    from app.services.project_director_bounded_rework_review_execution_service import (
        ProjectDirectorBoundedReworkReviewExecutionService,
    )
    from tests.p25_dynamic_test_support import (
        CANDIDATE_DIFF_FINGERPRINT,
        CLAIM_FINGERPRINT,
        MANIFEST_FINGERPRINT,
        NEW_DIFF_SHA256,
        OUTCOME_FINGERPRINT,
        PACKAGE_FINGERPRINT,
        PREVIOUS_DIFF_SHA256,
        PROMPT_SHA256,
        P25_BOUNDED_REWORK_CANDIDATE_DIFF_ACTION_TYPE,
        P25_BOUNDED_REWORK_CANDIDATE_DIFF_INTENT,
        P25_BOUNDED_REWORK_CANDIDATE_DIFF_SCHEMA_VERSION,
        P25_BOUNDED_REWORK_CANDIDATE_DIFF_SOURCE_DETAIL,
        P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_ACTION_TYPE,
        P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_INTENT,
        P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_SCHEMA_VERSION,
        P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_SOURCE_DETAIL,
        P25_BOUNDED_REWORK_REVIEW_OUTCOME_ACTION_TYPE,
        P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT,
        P25_BOUNDED_REWORK_REVIEW_OUTCOME_SCHEMA_VERSION,
        P25_BOUNDED_REWORK_REVIEW_OUTCOME_SOURCE_DETAIL,
        REVIEW_RESULT_FINGERPRINT,
        REVIEW_SEMANTIC_FINGERPRINT,
        SHA256,
        FakeCandidateDiffService,
        FakeReviewExecutionService,
        make_convergence_service,
    )

    session_id = session_id or uuid4()
    task_id = task_id or uuid4()
    project_id = project_id or uuid4()

    # Step 1: Seed base records
    s = session_local()
    seed_base_records(
        s,
        project_id=project_id, session_id=session_id, task_id=task_id,
        task_status="pending",
    )
    s.close()

    # Step 2: Create the initial P21-C/P22/P23 chain that authorizes P25 rework.
    session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
    p22_svc = _make_p22_service(session, msg_repo, sess_repo, task_repo)
    initial_review_id = _seed_p21_c_review_chain(
        session,
        session_id=session_id,
        task_id=task_id,
        project_id=project_id,
        verdict="changes_required",
        risk_level="medium",
    )
    initial_summary = p22_svc.orchestrate_post_review(
        session_id=session_id,
        source_task_id=task_id,
        source_review_message_id=initial_review_id,
    )
    assert initial_summary.result.orchestration_status == "ready_for_future_transition"
    prior_intent = ProjectDirectorProtectedTransitionDispatchIntentService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
    ).prepare_protected_transition_dispatch_intent(
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=initial_summary.message.id,
    )
    assert prior_intent.result.intent_status == "prepared"
    assert prior_intent.result.rework_attempt_index == 0

    # Step 3: Seed P25 candidate diff message
    candidate_diff_id = uuid4()
    candidate_write_id = uuid4()
    candidate_write = ProjectDirectorMessage(
        id=candidate_write_id,
        session_id=session_id, role="assistant",
        content="Candidate files written.",
        sequence_no=msg_repo.get_next_sequence_no(session_id=session_id),
        intent="sandbox_candidate_files_write",
        related_project_id=project_id, related_task_id=task_id,
        source="system",
        source_detail="p21_c_sandbox_candidate_files_write_executed",
        suggested_actions=[{
            "type": "p21_c_sandbox_candidate_files_write_record",
            "session_id": str(session_id),
            "source_task_id": str(task_id),
            "workspace_path": _WORKSPACE_PATH,
        }],
        requires_confirmation=False, risk_level="high",
    )
    msg_repo.create(candidate_write)
    candidate_diff_msg = ProjectDirectorMessage(
        id=candidate_diff_id,
        session_id=session_id, role="assistant",
        content="P25 bounded rework candidate diff.",
        sequence_no=msg_repo.get_next_sequence_no(session_id=session_id),
        intent=P25_BOUNDED_REWORK_CANDIDATE_DIFF_INTENT,
        related_project_id=project_id, related_task_id=task_id,
        source="system",
        source_detail=P25_BOUNDED_REWORK_CANDIDATE_DIFF_SOURCE_DETAIL,
        suggested_actions=[{
            "type": P25_BOUNDED_REWORK_CANDIDATE_DIFF_ACTION_TYPE,
            "source_message_id": str(candidate_write_id),
            "workspace_path": _WORKSPACE_PATH,
        }],
        requires_confirmation=False, risk_level="high",
    )
    msg_repo.create(candidate_diff_msg)
    msg_repo.commit()

    # Step 4: Seed P25 review outcome message
    attempt_replay_key = _sha(f"attempt-replay-{rework_attempt_index}-{candidate_diff_id}")
    now = datetime.now(timezone.utc)
    authority = ProjectDirectorBoundedReworkAuthorityEnvelope(
        session_id=session_id,
        project_id=project_id,
        source_task_id=task_id,
        target_task_id=task_id,
        source_run_id=uuid4(),
        source_review_message_id=initial_review_id,
        source_review_fingerprint=_sha("source-review"),
        source_review_semantic_fingerprint=_sha("previous-semantic"),
        source_disposition_message_id=initial_summary.result.source_disposition_message_id,
        source_p22_summary_message_id=initial_summary.message.id,
        source_p23_dispatch_intent_id=prior_intent.message.id,
        source_p23_dispatch_intent_fingerprint=_sha("source-intent"),
        source_p23_dispatch_consumption_id=uuid4(),
        source_p23_dispatch_consumption_fingerprint=_sha("source-consumption"),
    )
    finding = ProjectDirectorSandboxCandidateDiffReviewFinding(
        finding_id=f"finding-{rework_attempt_index}",
        severity="medium",
        title=f"Fresh guard {rework_attempt_index}",
        summary="A fresh blocking issue remains.",
        evidence_paths=["src/example.py"],
        recommended_action="Resolve the fresh blocking issue.",
    )
    adapter = ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult(
        adapter_status="validated_output",
        requested_reviewer_executor="codex",
        review_prompt_verified=True,
        review_prompt_sha256=SHA256(f"prompt-{rework_attempt_index}".encode()),
        review_prompt_bytes=100,
        review_scope_paths=["src/example.py"],
        review_output_schema_version=P25_BOUNDED_REWORK_REVIEW_OUTPUT_SCHEMA_VERSION,
        transport_invoked=True,
        transport_status="completed",
        output_validation_status="validated",
        raw_output_sha256=SHA256(f"raw-{rework_attempt_index}".encode()),
        raw_output_bytes=100,
        strict_json_valid=True,
        schema_valid=True,
        semantics_valid=True,
        evidence_scope_valid=True,
        review_status="reviewed",
        verdict="changes_required",
        risk_level="medium",
        summary=f"Fresh review {rework_attempt_index} completed.",
        findings=[finding],
        recommended_next_step="Prepare the next bounded rework attempt.",
    )
    outcome_values = {
        "review_outcome_id": uuid5(P25_BOUNDED_REWORK_REVIEW_OUTCOME_NAMESPACE, attempt_replay_key),
        "review_outcome_replay_key": ProjectDirectorBoundedReworkReviewInvocationOutcome.compute_outcome_replay_key(
            review_attempt_replay_key=attempt_replay_key,
            source_candidate_diff_sha256=DIFF_SHA256,
            review_prompt_sha256=adapter.review_prompt_sha256,
            invocation_ordinal=0,
        ),
        "created_at": now,
        "outcome_status": "validated_output",
        "review_attempt_id": uuid4(),
        "review_attempt_fingerprint": _sha(f"attempt-{rework_attempt_index}"),
        "review_attempt_replay_key": attempt_replay_key,
        "review_claim_id": uuid4(),
        "review_claim_fingerprint": _sha(f"claim-{rework_attempt_index}"),
        "preflight_id": uuid4(),
        "preflight_fingerprint": _sha(f"preflight-{rework_attempt_index}"),
        "source_candidate_diff_message_id": candidate_diff_id,
        "source_candidate_diff_id": candidate_diff_id,
        "source_candidate_diff_fingerprint": CANDIDATE_DIFF_FINGERPRINT,
        "source_candidate_diff_sha256": DIFF_SHA256,
        "source_candidate_manifest_id": uuid4(),
        "source_candidate_manifest_fingerprint": MANIFEST_FINGERPRINT,
        "source_executor_outcome_id": uuid4(),
        "source_package_id": uuid4(),
        "source_attempt_id": uuid4(),
        "authority": authority,
        "exact_task_id": task_id,
        "exact_run_id": authority.source_run_id,
        "rework_attempt_index": rework_attempt_index,
        "rework_attempt_limit": 3,
        "requested_reviewer_executor": "codex",
        "review_prompt_sha256": adapter.review_prompt_sha256,
        "review_prompt_bytes": adapter.review_prompt_bytes,
        "review_scope_paths": ("src/example.py",),
        "review_output_schema_version": P25_BOUNDED_REWORK_REVIEW_OUTPUT_SCHEMA_VERSION,
        "invocation_ordinal": 0,
        "adapter_result": adapter,
        "review_semantic_fingerprint": ProjectDirectorBoundedReworkReviewExecutionService._review_semantic_fingerprint(
            adapter_result=adapter,
            source_candidate_diff_sha256=DIFF_SHA256,
            review_scope_paths=("src/example.py",),
        ),
        "safe_error_code": None,
        "blocked_reasons": (),
        "recovery_required": False,
        "human_escalation_required": False,
    }
    draft = ProjectDirectorBoundedReworkReviewInvocationOutcome.model_construct(
        review_outcome_fingerprint="0" * 64,
        review_result_fingerprint="0" * 64,
        **outcome_values,
    )
    result_fingerprint = ProjectDirectorBoundedReworkReviewExecutionService.rebuild_persisted_review_result_fingerprint(draft)
    fingerprint_draft = ProjectDirectorBoundedReworkReviewInvocationOutcome.model_construct(
        review_outcome_fingerprint="0" * 64,
        review_result_fingerprint=result_fingerprint,
        **outcome_values,
    )
    outcome = ProjectDirectorBoundedReworkReviewInvocationOutcome(
        review_outcome_fingerprint=fingerprint_draft.compute_fingerprint(),
        review_result_fingerprint=result_fingerprint,
        **outcome_values,
    )
    review_outcome_msg = ProjectDirectorMessage(
        id=outcome.review_outcome_id,
        session_id=session_id, role="assistant",
        content=(
            f"P25 bounded rework review outcome persisted: "
            f"{outcome.review_outcome_id} attempt {outcome.review_attempt_id} "
            f"status validated_output verdict changes_required summary validated_review_output"
        ),
        sequence_no=msg_repo.get_next_sequence_no(session_id=session_id),
        intent=P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT,
        related_project_id=project_id, related_task_id=task_id,
        source="system",
        source_detail=P25_BOUNDED_REWORK_REVIEW_OUTCOME_SOURCE_DETAIL,
        suggested_actions=[{"type": P25_BOUNDED_REWORK_REVIEW_OUTCOME_ACTION_TYPE, **outcome.model_dump(mode="json")}],
        requires_confirmation=False, risk_level="high",
        forbidden_actions_detected=[
            "provider_called=false",
            "main_project_write_allowed=false",
            "product_runtime_git_write_allowed=false",
            "patch_apply_allowed=false",
            "git_write_allowed=false",
            "task_created=false",
            "run_created=false",
        ],
        created_at=now,
    )
    persisted_outcome = msg_repo.create(review_outcome_msg)
    msg_repo.commit()

    # Step 5: Create P22 summary via the real service
    p22_summary = p22_svc.orchestrate_post_review(
        session_id=session_id,
        source_task_id=task_id,
        source_review_message_id=outcome.review_outcome_id,
    )
    assert p22_summary.result.orchestration_status == "ready_for_future_transition", (
        p22_summary.result.blocked_reasons
    )
    assert p22_summary.result.disposition_type == "AUTO_REWORK"

    # Step 6: Create P25 convergence decision via real service
    previous_finding = ProjectDirectorSandboxCandidateDiffReviewFinding(
        finding_id=f"previous-{rework_attempt_index}",
        severity="high",
        title=f"Previous guard {rework_attempt_index}",
        summary="A previous blocking issue remained.",
        evidence_paths=["src/example.py"],
        recommended_action="Resolve the previous blocking issue.",
    )
    package = SimpleNamespace(
        package_id=uuid4(),
        package_fingerprint=SHA256(f"package-{rework_attempt_index}".encode()),
        authority=authority,
        rework_attempt_index=rework_attempt_index - 1,
        blocking_findings=(previous_finding,),
    )
    candidate_diff = SimpleNamespace(
        candidate_diff_id=candidate_diff_id,
        candidate_diff_fingerprint=CANDIDATE_DIFF_FINGERPRINT,
        candidate_diff_replay_key=SHA256(f"candidate-replay-{candidate_diff_id}".encode()),
        diff_status="generated",
        non_convergence_reason=None,
        authority=authority,
        source_attempt_id=outcome.source_attempt_id,
        rework_attempt_index=rework_attempt_index - 1,
        rework_attempt_limit=3,
        previous_diff_sha256=PREVIOUS_DIFF_SHA256,
        new_diff_sha256=DIFF_SHA256,
    )
    candidate_service = FakeCandidateDiffService(
        message_repository=msg_repo,
        candidate_diff=candidate_diff,
        candidate_diff_message=candidate_diff_msg,
        package=package,
        invocation_outcome=SimpleNamespace(outcome_id=outcome.source_executor_outcome_id),
    )
    review_service = FakeReviewExecutionService(
        message_repository=msg_repo,
        review_outcome=outcome,
        review_outcome_message=persisted_outcome,
    )
    convergence_service, _, _ = make_convergence_service(
        session_local,
        msg_repo=msg_repo,
        candidate_diff_svc=candidate_service,
        review_execution_svc=review_service,
        post_review_automation_svc=p22_svc,
    )
    convergence = convergence_service.decide_bounded_rework_convergence(
        session_id=session_id,
        source_task_id=task_id,
        source_candidate_diff_message_id=candidate_diff_id,
    )
    assert convergence.status == "decision_persisted", convergence.blocked_reasons
    assert convergence.decision.decision_type == "NEXT_ATTEMPT_ELIGIBLE"
    assert convergence.decision.next_rework_attempt_index == rework_attempt_index

    # Step 7: Create P23 intent via real service with convergence authority
    intent_svc = ProjectDirectorProtectedTransitionDispatchIntentService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        bounded_rework_convergence_service=convergence_service,
    )
    intent_result = intent_svc.prepare_protected_transition_dispatch_intent(
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=p22_summary.message.id,
    )
    assert intent_result.result.intent_status == "prepared", intent_result.result.blocked_reasons
    assert intent_result.result.rework_attempt_index == rework_attempt_index

    # Step 8: Build remaining D3 stack services
    freshness_svc = ProjectDirectorProtectedTransitionEvidenceFreshnessService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        review_handoff_service=_StubHandoff(),
        candidate_diff_service=_StubDiff(),
    )

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

    if fake_worker is None:
        fake_worker = FakeTaskWorker(session=session)
    else:
        fake_worker.session = session

    b2_svc = ProjectDirectorProtectedTransitionWorkerInvocationService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        run_repository=run_repo,
        agent_session_repository=agent_sess_repo,
        worker_start_reservation_service=b1_svc,
        freshness_service=freshness_svc,
        task_worker=fake_worker,
    )

    d3_svc = ProjectDirectorProtectedTransitionAutoAdvanceService(
        post_review_automation_service=p22_svc,
        dispatch_intent_service=intent_svc,
        dispatch_consumption_preflight_service=preflight_svc,
        dispatch_consumption_service=d1_svc,
        worker_start_reservation_service=b1_svc,
        worker_invocation_service=b2_svc,
    )

    return {
        "session": session,
        "msg_repo": msg_repo,
        "sess_repo": sess_repo,
        "task_repo": task_repo,
        "run_repo": run_repo,
        "agent_sess_repo": agent_sess_repo,
        "p22_svc": p22_svc,
        "intent_svc": intent_svc,
        "preflight_svc": preflight_svc,
        "d1_svc": d1_svc,
        "b1_svc": b1_svc,
        "b2_svc": b2_svc,
        "d3_svc": d3_svc,
        "fake_worker": fake_worker,
        "session_id": session_id,
        "task_id": task_id,
        "project_id": project_id,
        "review_msg_id": outcome.review_outcome_id,
        "convergence_service": convergence_service,
        "convergence": convergence,
        "intent_result": intent_result,
        "p22_summary": p22_summary,
        "candidate_diff_id": candidate_diff_id,
        "review_outcome_id": outcome.review_outcome_id,
    }
