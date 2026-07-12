"""Shared test support for P23 protected transition tests."""

from __future__ import annotations

import hashlib
import json
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

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


@dataclass
class FakeBudgetDecision:
    allowed: bool = True
    strategy_code: str = "normal"
    budget_policy_source: str = "test"

    @property
    def pressure_level(self):
        return _FakePressure()

    @property
    def suggested_action(self):
        return _FakeAction()

    @property
    def retry_status(self):
        return _FakeRetryStatus()


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
    def __init__(self, session=None, *, intent_id=None, p22_summary_id=None, review_id=None, freshness_id=None, project_id=None):
        self._message_repository = type("R", (), {"_session": session})()
        self._task_repository = type("R", (), {"session": session})()
        self._intent_id = intent_id or uuid4()
        self._p22_summary_id = p22_summary_id or uuid4()
        self._review_id = review_id or uuid4()
        self._freshness_id = freshness_id or uuid4()
        self._project_id = project_id

    def revalidate_persisted_protected_transition_dispatch_intent(self, **kwargs):
        pid = self._project_id or kwargs.get("project_id")
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
                "disposition_type": "AUTO_CONTINUE",
                "dispatch_kind": "auto_continue",
                "target_task_strategy": "source_task_continue",
                "review_result_fingerprint": _FINGERPRINT,
                "review_semantic_fingerprint": _FINGERPRINT,
                "freshness_evidence_fingerprint": _FINGERPRINT,
                "source_diff_sha256": DIFF_SHA256,
                "review_scope_paths": ["src/example.py"],
                "workspace_path": WORKSPACE_PATH,
                "workspace_path_within_root": True,
                "rework_attempt_index": 0,
                "rework_attempt_limit": 3,
                "transition_kind": "CONTINUE_GUARDRAIL",
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
    )

    # Create deterministic fakes
    intent_svc = FakeIntentService(
        session=session,
        intent_id=intent_id, p22_summary_id=p22_summary_id,
        review_id=review_id, freshness_id=freshness_id,
        project_id=project_id,
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
