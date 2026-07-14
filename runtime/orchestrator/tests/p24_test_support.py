"""Shared test support for P24 cross-task exact worker invocation tests."""

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
from app.domain.project_director_cross_task_exact_worker_invocation_claim import (
    CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_ACTION_TYPE,
    CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_INTENT,
    CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_SCHEMA_VERSION,
    CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL,
    ProjectDirectorCrossTaskExactWorkerInvocationClaim,
    ProjectDirectorCrossTaskExactWorkerInvocationClaimResult,
)
from app.domain.project_director_cross_task_exact_worker_invocation_outcome import (
    CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_ACTION_TYPE,
    CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_INTENT,
    CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_SCHEMA_VERSION,
    CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL,
    ProjectDirectorCrossTaskExactWorkerInvocationOutcome,
    ProjectDirectorCrossTaskExactWorkerInvocationOutcomeResult,
)
from app.domain.project_director_cross_task_exact_run_reservation import (
    CROSS_TASK_EXACT_RUN_RESERVATION_ACTION_TYPE,
    CROSS_TASK_EXACT_RUN_RESERVATION_INTENT,
    CROSS_TASK_EXACT_RUN_RESERVATION_SCHEMA_VERSION,
    CROSS_TASK_EXACT_RUN_RESERVATION_SOURCE_DETAIL,
    ProjectDirectorCrossTaskExactRunReservation,
)
from app.domain.project_director_cross_task_exact_worker_start_reservation import (
    CROSS_TASK_EXACT_WORKER_START_RESERVATION_ACTION_TYPE,
    CROSS_TASK_EXACT_WORKER_START_RESERVATION_INTENT,
    CROSS_TASK_EXACT_WORKER_START_RESERVATION_SCHEMA_VERSION,
    CROSS_TASK_EXACT_WORKER_START_RESERVATION_SOURCE_DETAIL,
    ProjectDirectorCrossTaskExactWorkerStartReservation,
)
from app.domain.project_director_cross_task_continuation import (
    CROSS_TASK_CONTINUATION_SCHEMA_VERSION,
    CROSS_TASK_CONTINUATION_ACTION,
    ProjectDirectorCrossTaskContinuationRoot,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_next_task_instruction_package import (
    NEXT_TASK_INSTRUCTION_PACKAGE_SCHEMA_VERSION,
    ProjectDirectorNextTaskInstructionPackage,
    compute_p24_contract_sha256,
)
from app.domain.project_director_next_task_instruction_package_candidate import (
    NEXT_TASK_INSTRUCTION_PACKAGE_CANDIDATE_SCHEMA_VERSION,
    ProjectDirectorCandidateRepositoryBindingSnapshot,
    ProjectDirectorCandidateSelectedModel,
    ProjectDirectorCandidateSelectedSkill,
    ProjectDirectorCandidateSelectedStrategy,
    ProjectDirectorCandidateWorkspaceBindingSnapshot,
    ProjectDirectorConfirmedInstructionScopeSnapshot,
    ProjectDirectorCandidateVerificationRequirement,
    ProjectDirectorCandidateTestRequirement,
    ProjectDirectorCandidateEvidenceRequirement,
)
from app.domain.project_director_exact_next_task_routing_snapshot import (
    ProjectDirectorNextTaskSourceAuthorityLineageSnapshot,
    ProjectDirectorRoutingScoreItemSnapshot,
    ProjectDirectorStrategyDecisionSnapshot,
    ProjectDirectorStrategyReasonSnapshot,
)
from app.domain.project_director_source_execution_authority import (
    SourceExecutionAuthorityKind,
)

from app.domain.project_role import ProjectRoleCode
from app.domain.run import (
    Run,
    RunBudgetPressureLevel,
    RunBudgetStrategyAction,
    RunRoutingScoreItem,
    RunStatus,
    RunStrategyDecision,
    RunStrategyReasonItem,
)
from app.domain.task import Task, TaskHumanStatus, TaskStatus
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.workers.task_worker import (
    TaskWorker,
    WorkerReservedRunExecutionSnapshot,
    WorkerRunResult,
)


SHA256 = lambda data: hashlib.sha256(data).hexdigest()
_FINGERPRINT = "a" * 64
_HEX64 = "0123456789abcdef"


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
    plan_version_id: UUID | None = None,
    plan_version_no: int = 1,
    task_status: str = "running",
    human_status: str = "none",
) -> dict[str, UUID]:
    from app.core.db_tables import ProjectDirectorPlanVersionTable
    pid = project_id or uuid4()
    sid = session_id or uuid4()
    tid = task_id or uuid4()
    pvid = plan_version_id or uuid4()
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
            risk_level="normal", human_status=human_status,
            owner_role_code="architect",
            source_draft_id=f"pdv:{pvid}:{plan_version_no}", acceptance_criteria=acceptance,
        )
    )
    session.add(
        ProjectDirectorSessionTable(
            id=sid, project_id=pid,
            goal_text="Test goal", constraints="", status="confirmed",
        )
    )
    session.flush()
    session.add(
        ProjectDirectorPlanVersionTable(
            id=pvid, session_id=sid, project_id=pid,
            version_no=1, status="confirmed",
        )
    )
    session.commit()
    return {"project_id": pid, "session_id": sid, "task_id": tid, "plan_version_id": pvid}


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
    msgs, _ = msg_repo.list_by_session_id(session_id=session_id, limit=500)
    return sum(1 for m in msgs if m.source_detail == source_detail)


def get_messages_by_source_detail(
    msg_repo: ProjectDirectorMessageRepository,
    session_id: UUID,
    source_detail: str,
) -> list[ProjectDirectorMessage]:
    msgs, _ = msg_repo.list_by_session_id(session_id=session_id, limit=500)
    return [m for m in msgs if m.source_detail == source_detail]


# ── Deterministic Helpers ────────────────────────────────────────────


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _hex64(seed: str) -> str:
    return _sha256_hex(seed)


# ── Full P24 Chain Builder ──────────────────────────────────────────


@dataclass
class P24Chain:
    """Complete P24 chain from package through claim."""
    session_id: UUID
    project_id: UUID
    plan_version_id: UUID
    task_creation_record_id: UUID
    source_task_id: UUID
    source_run_id: UUID
    source_completion_evidence_id: UUID
    next_task_id: UUID
    exact_run_id: UUID
    continuation_id: UUID
    package_id: UUID
    root_record_id: UUID
    exact_run_reservation_id: UUID
    worker_start_reservation_id: UUID
    claim_id: UUID
    now: datetime
    package: ProjectDirectorNextTaskInstructionPackage
    root: ProjectDirectorCrossTaskContinuationRoot
    exact_run_reservation: ProjectDirectorCrossTaskExactRunReservation
    worker_start_reservation: ProjectDirectorCrossTaskExactWorkerStartReservation
    claim: ProjectDirectorCrossTaskExactWorkerInvocationClaim


def build_p24_chain(
    *,
    session_id: UUID | None = None,
    project_id: UUID | None = None,
    next_task_id: UUID | None = None,
    exact_run_id: UUID | None = None,
    model_name: str = "test-model",
    model_tier: str = "standard",
    skill_code: str = "test-skill",
    skill_name: str = "Test Skill",
    owner_role_code: ProjectRoleCode = ProjectRoleCode.ARCHITECT,
    task_human_status: str = "none",
) -> P24Chain:
    """Build a complete valid P24 chain for testing."""
    sid = session_id or uuid4()
    pid = project_id or uuid4()
    plan_version_id = uuid4()
    task_creation_record_id = uuid4()
    source_task_id = uuid4()
    source_run_id = uuid4()
    source_completion_evidence_id = uuid4()
    next_tid = next_task_id or uuid4()
    exact_rid = exact_run_id or uuid4()
    continuation_id = uuid4()
    package_id = uuid4()
    root_record_id = uuid4()
    exact_run_reservation_id = uuid4()
    worker_start_reservation_id = uuid4()
    claim_id = uuid4()
    now = _now_utc()

    # Build common fingerprints
    source_completion_fp = _hex64(f"source-completion:{source_completion_evidence_id}")
    source_exec_auth_fp = _hex64(f"source-exec-auth:{source_task_id}")
    source_outcome_fp = _hex64(f"source-outcome:{source_task_id}")
    completion_policy_fp = _hex64(f"completion-policy:{pid}")

    # Build selected skills
    selected_skill = ProjectDirectorCandidateSelectedSkill(
        skill_code=skill_code,
        skill_name=skill_name,
    )

    # Build strategy
    strategy_decision = ProjectDirectorStrategyDecisionSnapshot(
        version="1",
        project_stage=None,
        owner_role_code=owner_role_code,
        model_tier=model_tier,
        model_name=model_name,
        selected_skill_codes=[skill_code],
        selected_skill_names=[skill_name],
        budget_pressure_level=RunBudgetPressureLevel.NORMAL,
        budget_action=RunBudgetStrategyAction.FULL_SPEED,
        strategy_code="normal",
        summary="Normal execution",
        role_model_policy_source="test",
        role_model_policy_desired_tier=model_tier,
        role_model_policy_adjusted_tier=model_tier,
        role_model_policy_final_tier=model_tier,
        role_model_policy_stage_override_applied=False,
        rule_codes=["normal"],
        reasons=[
            ProjectDirectorStrategyReasonSnapshot(
                code="normal", label="Normal", detail="Normal", score=1.0,
            ),
        ],
    )
    routing_score_item = ProjectDirectorRoutingScoreItemSnapshot(
        code="test", label="Test", score=1.0, detail="test",
    )
    selected_strategy = ProjectDirectorCandidateSelectedStrategy(
        strategy_code="normal",
        strategy_summary="Normal execution",
        strategy_reasons=[
            ProjectDirectorStrategyReasonSnapshot(
                code="normal", label="Normal", detail="Normal", score=1.0,
            ),
        ],
        strategy_decision=strategy_decision,
        routing_score=1.0,
        routing_score_breakdown=[routing_score_item],
        route_reason="test",
        execution_attempts=0,
        recent_failure_count=0,
        budget_pressure_level=RunBudgetPressureLevel.NORMAL,
        budget_action=RunBudgetStrategyAction.FULL_SPEED,
        budget_strategy_code="normal",
        budget_score_adjustment=0.0,
        dispatch_status="dispatched",
        handoff_reason="test",
        matched_terms=(),
        project_stage=None,
        owner_role_code=owner_role_code,
        upstream_role_code=None,
        downstream_role_code=None,
    )

    # Build selected model
    selected_model = ProjectDirectorCandidateSelectedModel(
        model_name=model_name,
        model_tier=model_tier,
    )

    # Build binding snapshots
    repo_binding = ProjectDirectorCandidateRepositoryBindingSnapshot(
        binding_type="local",
        binding_mode="read-write",
        target="/tmp/test-repo",
        configured_branch="main",
        effective_branch="main",
        focus_paths=("src/",),
        usage="test",
        safety_note="test",
        review_status="approved",
    )
    workspace_binding = ProjectDirectorCandidateWorkspaceBindingSnapshot(
        workspace_id=uuid4(),
        project_id=pid,
        root_path="/tmp/test-workspace",
        allowed_workspace_root="/tmp/test-workspace",
        display_name="Test Workspace",
        access_mode="read_only",
        default_base_branch="main",
        ignore_rule_summary=(".gitignore",),
    )

    # Build scope
    confirmed_scope = ProjectDirectorConfirmedInstructionScopeSnapshot(
        project_in_scope=("src/",),
        project_out_of_scope=("tests/",),
        project_assumptions=("test env",),
        next_proposed_task_title="Test task",
        next_proposed_task_description="Test description",
        next_proposed_task_role_code=owner_role_code,
        next_proposed_task_priority_hint="normal",
        deliverable_boundaries=(),
    )

    # Build source authority lineage (construct then compute fingerprint)
    source_outcome_id = uuid4()
    lineage_evidence_id = uuid4()
    completion_review_evidence_id = uuid4()
    cp_id = uuid4()
    lineage_values = {
        "schema_version": "p24-d-source-authority-lineage.v1",
        "source_completion_evidence_id": source_completion_evidence_id,
        "source_completion_evidence_fingerprint": source_completion_fp,
        "source_execution_authority_kind": "p24_cross_task_continuation",
        "source_execution_authority_id": source_task_id,
        "source_execution_authority_fingerprint": source_exec_auth_fp,
        "source_reservation_id": worker_start_reservation_id,
        "source_claim_id": claim_id,
        "source_outcome_id": source_outcome_id,
        "source_outcome_schema_version": "p23-d2-worker-run-result.v1",
        "source_outcome_fingerprint": source_outcome_fp,
        "source_review_id": None,
        "source_review_outcome": None,
        "source_transition_evidence_ids": (lineage_evidence_id,),
        "completion_policy_id": cp_id,
        "completion_policy_version": 1,
        "completion_policy_fingerprint": completion_policy_fp,
        "completion_review_requirement": "not_required",
        "completion_review_satisfaction_status": "not_required_by_policy",
        "completion_review_evidence_kind": "none",
        "completion_review_evidence_ids": (completion_review_evidence_id,),
        "authority_lineage_fingerprint": _FINGERPRINT,
    }
    # Use model_construct to bypass validation, compute fingerprint, then validate
    lineage_provisional = ProjectDirectorNextTaskSourceAuthorityLineageSnapshot.model_construct(**lineage_values)
    lineage_fp = lineage_provisional.compute_fingerprint()
    lineage_values["authority_lineage_fingerprint"] = lineage_fp
    source_authority_lineage = ProjectDirectorNextTaskSourceAuthorityLineageSnapshot.model_validate(lineage_values)

    # Build package
    package_replay_key = compute_p24_contract_sha256({
        "schema_version": "p24-package-replay.v1",
        "action": "cross_task_auto_continue",
        "continuation_id": str(continuation_id),
        "source_completion_evidence_id": str(source_completion_evidence_id),
        "next_task_id": str(next_tid),
    })
    package_payload = {
        "schema_version": NEXT_TASK_INSTRUCTION_PACKAGE_SCHEMA_VERSION,
        "package_id": package_id,
        "package_fingerprint": _FINGERPRINT,
        "package_replay_key": package_replay_key,
        "created_at": now,
        "continuation_id": continuation_id,
        "supersedes_package_id": None,
        "instruction_candidate_schema_version": NEXT_TASK_INSTRUCTION_PACKAGE_CANDIDATE_SCHEMA_VERSION,
        "instruction_candidate_fingerprint": _hex64(f"candidate:{package_id}"),
        "session_id": sid,
        "project_id": pid,
        "plan_version_id": plan_version_id,
        "plan_version_no": 1,
        "task_creation_record_id": task_creation_record_id,
        "source_task_id": source_task_id,
        "source_run_id": source_run_id,
        "source_completion_evidence_id": source_completion_evidence_id,
        "source_completion_evidence_fingerprint": source_completion_fp,
        "source_execution_authority_kind": "p24_cross_task_continuation",
        "source_execution_authority_id": source_task_id,
        "source_execution_authority_fingerprint": source_exec_auth_fp,
        "source_worker_start_reservation_id": worker_start_reservation_id,
        "source_worker_invocation_claim_id": claim_id,
        "source_worker_invocation_outcome_id": source_outcome_id,
        "source_worker_outcome_schema_version": "p23-d2-worker-run-result.v1",
        "source_worker_outcome_fingerprint": source_outcome_fp,
        "source_review_id": None,
        "source_review_outcome": None,
        "source_transition_evidence_ids": (lineage_evidence_id,),
        "completion_policy_id": cp_id,
        "completion_policy_version": 1,
        "completion_policy_fingerprint": completion_policy_fp,
        "review_requirement": "not_required",
        "source_authority_lineage": source_authority_lineage,
        "next_task_id": next_tid,
        "next_task_index": 0,
        "task_count": 1,
        "task_title": "Test task",
        "task_input_summary": "SAFE DRY-RUN TASK DISPATCH ONLY",
        "owner_role_code": owner_role_code,
        "priority": "normal",
        "risk_level": "normal",
        "depends_on_task_ids": (),
        "confirmed_scope": confirmed_scope,
        "repository_binding": repo_binding,
        "workspace_binding": workspace_binding,
        "allowed_paths": ("src/",),
        "forbidden_scope_entries": (),
        "workspace_ignore_rule_summary": (".gitignore",),
        "forbidden_paths": ("secrets/",),
        "acceptance_criteria_source": "task",
        "acceptance_criteria": ("safe_dry_run_task=true",),
        "verification_requirements": (),
        "test_requirements": (),
        "evidence_requirements": (),
        "selected_strategy": selected_strategy,
        "selected_model": selected_model,
        "selected_skills": (selected_skill,),
        "human_confirmation_required": False,
        "human_confirmation_evidence_id": None,
        "product_runtime_git_write_allowed": False,
        "forbidden_actions": (
            "product_runtime_git_write", "git_add", "git_commit", "git_push",
            "pull_request_creation", "merge", "branch_destruction",
            "global_pending_task_scan", "next_task_skip", "plan_mutation",
            "duplicate_task_creation", "uncontrolled_workspace_write",
            "task_claim", "run_creation", "worker_invocation",
            "verification_command_execution",
        ),
    }
    package_payload["package_fingerprint"] = _FINGERPRINT
    package_provisional = ProjectDirectorNextTaskInstructionPackage.model_construct(**package_payload)
    package_fingerprint = package_provisional.compute_fingerprint()
    package_payload["package_fingerprint"] = package_fingerprint
    package = ProjectDirectorNextTaskInstructionPackage.model_validate(package_payload)

    # Build continuation root
    root_idempotency_key = compute_p24_contract_sha256({
        "schema_version": "p24-continuation-replay.v1",
        "action": "cross_task_auto_continue",
        "session_id": str(sid),
        "project_id": str(pid),
        "plan_version_id": str(plan_version_id),
        "task_creation_record_id": str(task_creation_record_id),
        "source_task_id": str(source_task_id),
        "source_run_id": str(source_run_id),
        "source_completion_evidence_id": str(source_completion_evidence_id),
    })
    root_payload = {
        "schema_version": CROSS_TASK_CONTINUATION_SCHEMA_VERSION,
        "record_id": root_record_id,
        "continuation_id": continuation_id,
        "continuation_fingerprint": _FINGERPRINT,
        "idempotency_key": root_idempotency_key,
        "created_at": now,
        "status": "prepared",
        "session_id": sid,
        "project_id": pid,
        "plan_version_id": plan_version_id,
        "task_creation_record_id": task_creation_record_id,
        "source_task_id": source_task_id,
        "source_run_id": source_run_id,
        "source_completion_evidence_id": source_completion_evidence_id,
        "source_completion_evidence_fingerprint": source_completion_fp,
        "instruction_package_id": package_id,
        "instruction_package_fingerprint": package_fingerprint,
        "instruction_candidate_fingerprint": package.instruction_candidate_fingerprint,
        "next_task_id": next_tid,
        "product_runtime_git_write_allowed": False,
        "forbidden_actions": (
            "product_runtime_git_write", "git_add", "git_commit", "git_push",
            "pull_request_creation", "merge", "branch_destruction",
            "global_pending_task_scan", "next_task_skip", "plan_mutation",
            "duplicate_task_creation", "uncontrolled_workspace_write",
            "task_claim", "run_creation", "worker_invocation",
            "verification_command_execution",
        ),
    }
    root_payload["continuation_fingerprint"] = _FINGERPRINT
    root_provisional = ProjectDirectorCrossTaskContinuationRoot.model_construct(**root_payload)
    root_fingerprint = root_provisional.compute_fingerprint()
    root_payload["continuation_fingerprint"] = root_fingerprint
    root = ProjectDirectorCrossTaskContinuationRoot.model_validate(root_payload)

    # Build exact run reservation
    e1b_reservation_replay_key = compute_p24_contract_sha256({
        "schema_version": "p24-exact-run-reservation-replay.v1",
        "action": "reserve_exact_next_task_run",
        "continuation_id": str(continuation_id),
        "continuation_root_record_id": str(root_record_id),
        "instruction_package_id": str(package_id),
        "next_task_id": str(next_tid),
    })
    strategy = package.selected_strategy
    e1b_payload = {
        "schema_version": "p24-e-exact-run-reservation.v1",
        "exact_run_reservation_id": exact_run_reservation_id,
        "reservation_fingerprint": _FINGERPRINT,
        "reservation_replay_key": e1b_reservation_replay_key,
        "created_at": now,
        "continuation_id": continuation_id,
        "continuation_root_record_id": root_record_id,
        "continuation_root_fingerprint": root_fingerprint,
        "continuation_idempotency_key": root_idempotency_key,
        "instruction_package_id": package_id,
        "instruction_package_fingerprint": package_fingerprint,
        "instruction_candidate_fingerprint": package.instruction_candidate_fingerprint,
        "continuation_sequence_no": 2,
        "previous_record_id": root_record_id,
        "replay_of_record_id": None,
        "action": "reserve_exact_next_task_run",
        "status": "next_task_run_created",
        "session_id": sid,
        "project_id": pid,
        "plan_version_id": plan_version_id,
        "task_creation_record_id": task_creation_record_id,
        "source_task_id": source_task_id,
        "source_run_id": source_run_id,
        "source_completion_evidence_id": source_completion_evidence_id,
        "source_completion_evidence_fingerprint": source_completion_fp,
        "next_task_id": next_tid,
        "next_task_index": 0,
        "task_count": 1,
        "task_title": "Test task",
        "task_input_summary": "SAFE DRY-RUN TASK DISPATCH ONLY",
        "owner_role_code": owner_role_code,
        "priority": "normal",
        "risk_level": "normal",
        "depends_on_task_ids": (),
        "task_human_status": task_human_status,
        "exact_run_id": exact_rid,
        "run_model_name": model_name,
        "run_route_reason": strategy.route_reason,
        "run_routing_score": strategy.routing_score,
        "run_routing_score_breakdown": strategy.routing_score_breakdown,
        "run_strategy_decision": strategy.strategy_decision,
        "run_owner_role_code": strategy.owner_role_code,
        "run_upstream_role_code": strategy.upstream_role_code,
        "run_downstream_role_code": strategy.downstream_role_code,
        "run_handoff_reason": strategy.handoff_reason,
        "run_dispatch_status": strategy.dispatch_status,
        "exact_run_started_at": now,
        "exact_run_created_at": now,
        "active_run_ids_before": (),
        "active_agent_session_ids_before": (),
        "product_runtime_git_write_allowed": False,
        "forbidden_actions": (
            "product_runtime_git_write", "git_add", "git_commit", "git_push",
            "pull_request_creation", "merge", "branch_destruction",
            "global_pending_task_scan", "next_task_skip", "plan_mutation",
            "duplicate_task_creation", "uncontrolled_workspace_write",
            "worker_invocation", "verification_command_execution",
            "duplicate_task_claim", "duplicate_run_creation",
            "worker_invocation_without_reservation",
        ),
    }
    e1b_payload["reservation_fingerprint"] = _FINGERPRINT
    e1b_provisional = ProjectDirectorCrossTaskExactRunReservation.model_construct(**e1b_payload)
    e1b_fingerprint = e1b_provisional.compute_fingerprint()
    e1b_payload["reservation_fingerprint"] = e1b_fingerprint
    exact_run_reservation = ProjectDirectorCrossTaskExactRunReservation.model_validate(e1b_payload)

    # Build worker start reservation
    e2a_replay_key = compute_p24_contract_sha256({
        "schema_version": "p24-exact-worker-start-reservation-replay.v1",
        "action": "reserve_exact_worker_start",
        "continuation_id": str(continuation_id),
        "exact_run_reservation_id": str(exact_run_reservation_id),
        "instruction_package_id": str(package_id),
        "next_task_id": str(next_tid),
        "exact_run_id": str(exact_rid),
    })
    e2a_payload = {
        "schema_version": "p24-e-exact-worker-start-reservation.v1",
        "exact_worker_start_reservation_id": worker_start_reservation_id,
        "worker_start_reservation_fingerprint": _FINGERPRINT,
        "worker_start_reservation_replay_key": e2a_replay_key,
        "created_at": now,
        "continuation_id": continuation_id,
        "continuation_root_record_id": root_record_id,
        "continuation_root_fingerprint": root_fingerprint,
        "continuation_idempotency_key": root_idempotency_key,
        "instruction_package_id": package_id,
        "instruction_package_fingerprint": package_fingerprint,
        "instruction_candidate_fingerprint": package.instruction_candidate_fingerprint,
        "exact_run_reservation_id": exact_run_reservation_id,
        "exact_run_reservation_fingerprint": e1b_fingerprint,
        "exact_run_reservation_replay_key": e1b_reservation_replay_key,
        "continuation_sequence_no": 3,
        "previous_record_id": exact_run_reservation_id,
        "replay_of_record_id": None,
        "action": "reserve_exact_worker_start",
        "status": "worker_start_reserved",
        "session_id": sid,
        "project_id": pid,
        "plan_version_id": plan_version_id,
        "task_creation_record_id": task_creation_record_id,
        "source_task_id": source_task_id,
        "source_run_id": source_run_id,
        "source_completion_evidence_id": source_completion_evidence_id,
        "source_completion_evidence_fingerprint": source_completion_fp,
        "next_task_id": next_tid,
        "next_task_index": 0,
        "task_count": 1,
        "task_human_status": task_human_status,
        "exact_run_id": exact_rid,
        "exact_run_started_at": now,
        "exact_run_created_at": now,
        "active_agent_session_ids_before": (),
        "worker_model_name": model_name,
        "worker_model_tier": model_tier,
        "worker_owner_role_code": owner_role_code,
        "worker_upstream_role_code": None,
        "worker_downstream_role_code": None,
        "worker_selected_skills": (selected_skill,),
        "worker_repository_binding": repo_binding,
        "worker_workspace_binding": workspace_binding,
        "worker_allowed_paths": ("src/",),
        "worker_forbidden_paths": ("secrets/",),
        "worker_start_reserved": True,
        "worker_called": False,
        "agent_session_created": False,
        "runtime_started": False,
        "invocation_claim_created": False,
        "worker_outcome_recorded": False,
        "product_runtime_git_write_allowed": False,
        "forbidden_actions": (
            "product_runtime_git_write", "git_add", "git_commit", "git_push",
            "pull_request_creation", "merge", "branch_destruction",
            "global_pending_task_scan", "next_task_skip", "plan_mutation",
            "duplicate_task_creation", "duplicate_task_claim",
            "duplicate_run_creation", "duplicate_worker_start_reservation",
            "worker_invocation", "worker_invocation_without_reservation",
            "worker_invocation_without_claim", "agent_session_creation",
            "verification_command_execution", "uncontrolled_workspace_write",
        ),
    }
    e2a_payload["worker_start_reservation_fingerprint"] = _FINGERPRINT
    e2a_provisional = ProjectDirectorCrossTaskExactWorkerStartReservation.model_construct(**e2a_payload)
    e2a_fingerprint = e2a_provisional.compute_fingerprint()
    e2a_payload["worker_start_reservation_fingerprint"] = e2a_fingerprint
    worker_start_reservation = ProjectDirectorCrossTaskExactWorkerStartReservation.model_validate(e2a_payload)

    # Build claim
    claim_replay_key = ProjectDirectorCrossTaskExactWorkerInvocationClaim.compute_worker_invocation_claim_replay_key(
        continuation_id=continuation_id,
        exact_worker_start_reservation_id=worker_start_reservation_id,
        exact_run_reservation_id=exact_run_reservation_id,
        instruction_package_id=package_id,
        next_task_id=next_tid,
        exact_run_id=exact_rid,
    )
    claim_token = ProjectDirectorCrossTaskExactWorkerInvocationClaim.compute_worker_invocation_claim_token(
        exact_worker_invocation_claim_id=claim_id,
        worker_invocation_claim_replay_key=claim_replay_key,
        exact_worker_start_reservation_id=worker_start_reservation_id,
        exact_worker_start_reservation_fingerprint=e2a_fingerprint,
        exact_run_id=exact_rid,
    )
    claim_payload = {
        "schema_version": CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_SCHEMA_VERSION,
        "exact_worker_invocation_claim_id": claim_id,
        "worker_invocation_claim_fingerprint": _FINGERPRINT,
        "worker_invocation_claim_replay_key": claim_replay_key,
        "worker_invocation_claim_token": claim_token,
        "created_at": now,
        "continuation_id": continuation_id,
        "continuation_root_record_id": root_record_id,
        "continuation_root_fingerprint": root_fingerprint,
        "continuation_idempotency_key": root_idempotency_key,
        "instruction_package_id": package_id,
        "instruction_package_fingerprint": package_fingerprint,
        "instruction_candidate_fingerprint": package.instruction_candidate_fingerprint,
        "exact_run_reservation_id": exact_run_reservation_id,
        "exact_run_reservation_fingerprint": e1b_fingerprint,
        "exact_run_reservation_replay_key": e1b_reservation_replay_key,
        "exact_worker_start_reservation_id": worker_start_reservation_id,
        "exact_worker_start_reservation_fingerprint": e2a_fingerprint,
        "exact_worker_start_reservation_replay_key": e2a_replay_key,
        "continuation_sequence_no": 4,
        "previous_record_id": worker_start_reservation_id,
        "replay_of_record_id": None,
        "action": "claim_exact_worker_invocation",
        "status": "worker_invocation_claimed",
        "session_id": sid,
        "project_id": pid,
        "plan_version_id": plan_version_id,
        "task_creation_record_id": task_creation_record_id,
        "source_task_id": source_task_id,
        "source_run_id": source_run_id,
        "source_completion_evidence_id": source_completion_evidence_id,
        "source_completion_evidence_fingerprint": source_completion_fp,
        "next_task_id": next_tid,
        "next_task_index": 0,
        "task_count": 1,
        "task_status_before": "running",
        "task_human_status_before": task_human_status,
        "task_paused_reason_absent": True,
        "exact_run_id": exact_rid,
        "run_status_before": "running",
        "exact_run_started_at": now,
        "exact_run_created_at": now,
        "exact_run_finished_at_before": None,
        "exact_run_failure_category_before": None,
        "exact_run_quality_gate_passed_before": None,
        "active_run_ids_before": (exact_rid,),
        "active_agent_session_ids_before": (),
        "worker_model_name": model_name,
        "worker_model_tier": model_tier,
        "worker_owner_role_code": owner_role_code,
        "worker_upstream_role_code": None,
        "worker_downstream_role_code": None,
        "worker_selected_skills": (selected_skill,),
        "worker_repository_binding": repo_binding,
        "worker_workspace_binding": workspace_binding,
        "worker_allowed_paths": ("src/",),
        "worker_forbidden_paths": ("secrets/",),
        "task_claimed": True,
        "run_created": True,
        "worker_start_reserved": True,
        "worker_invocation_claimed": True,
        "single_use_worker_call_authorized": True,
        "worker_called": False,
        "worker_call_attempted": False,
        "agent_session_created": False,
        "runtime_started": False,
        "worker_outcome_recorded": False,
        "task_status_mutated_by_claim": False,
        "run_status_mutated_by_claim": False,
        "product_runtime_git_write_allowed": False,
        "forbidden_actions": (
            "product_runtime_git_write", "git_add", "git_commit", "git_push",
            "pull_request_creation", "merge", "branch_destruction",
            "global_pending_task_scan", "next_task_skip", "plan_mutation",
            "duplicate_task_creation", "duplicate_task_claim",
            "duplicate_run_creation", "duplicate_worker_start_reservation",
            "duplicate_worker_invocation_claim",
            "worker_invocation_without_reservation",
            "worker_invocation_without_claim",
            "worker_reinvocation",
            "agent_session_creation_without_claim",
            "worker_outcome_without_claim",
            "verification_command_execution", "uncontrolled_workspace_write",
        ),
    }
    claim_provisional = ProjectDirectorCrossTaskExactWorkerInvocationClaim.model_construct(**claim_payload)
    claim_fingerprint = claim_provisional.compute_fingerprint()
    claim_payload["worker_invocation_claim_fingerprint"] = claim_fingerprint
    claim = ProjectDirectorCrossTaskExactWorkerInvocationClaim.model_validate(claim_payload)

    return P24Chain(
        session_id=sid,
        project_id=pid,
        plan_version_id=plan_version_id,
        task_creation_record_id=task_creation_record_id,
        source_task_id=source_task_id,
        source_run_id=source_run_id,
        source_completion_evidence_id=source_completion_evidence_id,
        next_task_id=next_tid,
        exact_run_id=exact_rid,
        continuation_id=continuation_id,
        package_id=package_id,
        root_record_id=root_record_id,
        exact_run_reservation_id=exact_run_reservation_id,
        worker_start_reservation_id=worker_start_reservation_id,
        claim_id=claim_id,
        now=now,
        package=package,
        root=root,
        exact_run_reservation=exact_run_reservation,
        worker_start_reservation=worker_start_reservation,
        claim=claim,
    )


def build_valid_outcome(
    chain: P24Chain,
    *,
    status: str = "returned",
    contract_valid: bool = True,
    budget_rechecked: bool = True,
    git_activity: bool = False,
    worker_result_message: str = "fake worker executed",
) -> ProjectDirectorCrossTaskExactWorkerInvocationOutcome:
    """Build a valid Outcome from a chain."""
    claim = chain.claim
    now = _now_utc()

    if status == "not_invoked":
        # Not-invoked outcome
        values = _base_outcome_values(chain, now, status="not_invoked")
        skill_codes = tuple(item.skill_code for item in claim.worker_selected_skills)
        skill_names = tuple(item.skill_name for item in claim.worker_selected_skills)
        values.update({
            "worker_called": False,
            "worker_call_attempted": False,
            "worker_returned": False,
            "worker_raised": False,
            "worker_started": False,
            "worker_result_contract_valid": False,
            "worker_authority_result_validated": False,
            "reserved_snapshot_present": False,
            "native_process_started": False,
            "claim_worker_model_name": claim.worker_model_name,
            "claim_worker_model_tier": claim.worker_model_tier,
            "claim_worker_selected_skill_codes": skill_codes,
            "claim_worker_selected_skill_names": skill_names,
            "claim_worker_owner_role_code": claim.worker_owner_role_code,
            "claim_worker_upstream_role_code": claim.worker_upstream_role_code,
            "claim_worker_downstream_role_code": claim.worker_downstream_role_code,
            "human_recovery_required": True,
            "blocked_reasons": ("exact_worker_invocation_outcome_pre_call_revalidation_failed",),
            "worker_reported_git_write_activity": False,
        })
    elif status == "returned":
        values = _base_outcome_values(chain, now, status="returned")
        snapshot = WorkerReservedRunExecutionSnapshot(
            source="p23_d2_exact_reserved_run",
            exact_task_id=claim.next_task_id,
            exact_run_id=claim.exact_run_id,
            reserved_run_execution_requested=True,
            exact_binding_validated=True,
            task_routed=False,
            task_claimed_in_this_cycle=False,
            run_created_in_this_cycle=False,
            budget_rechecked=budget_rechecked,
            existing_run_reused=True,
            shared_execution_seam_used=True,
            product_runtime_git_write_allowed=False,
            blocked_reasons=[],
        )
        skill_codes = tuple(item.skill_code for item in claim.worker_selected_skills)
        skill_names = tuple(item.skill_name for item in claim.worker_selected_skills)
        values.update({
            "worker_called": True,
            "worker_call_attempted": True,
            "worker_returned": True,
            "worker_raised": False,
            "worker_started": True,
            "worker_result_contract_valid": contract_valid,
            "worker_result_claimed": True if contract_valid else None,
            "worker_result_message": worker_result_message if contract_valid else None,
            "worker_execution_mode": "fake" if contract_valid else None,
            "worker_failure_category": None,
            "worker_quality_gate_passed": None if not contract_valid else True,
            "worker_result_summary": "fake execution" if contract_valid else None,
            "claim_worker_model_name": claim.worker_model_name,
            "claim_worker_model_tier": claim.worker_model_tier,
            "claim_worker_selected_skill_codes": skill_codes,
            "claim_worker_selected_skill_names": skill_names,
            "claim_worker_owner_role_code": claim.worker_owner_role_code,
            "claim_worker_upstream_role_code": claim.worker_upstream_role_code,
            "claim_worker_downstream_role_code": claim.worker_downstream_role_code,
            "worker_result_model_name": claim.worker_model_name if contract_valid else None,
            "worker_result_model_tier": claim.worker_model_tier if contract_valid else None,
            "worker_result_selected_skill_codes": skill_codes if contract_valid else (),
            "worker_result_selected_skill_names": skill_names if contract_valid else (),
            "worker_result_owner_role_code": claim.worker_owner_role_code if contract_valid else None,
            "worker_result_upstream_role_code": claim.worker_upstream_role_code if contract_valid else None,
            "worker_result_downstream_role_code": claim.worker_downstream_role_code if contract_valid else None,
            "worker_result_route_reason": "test" if contract_valid else None,
            "worker_result_strategy_code": "normal" if contract_valid else None,
            "worker_result_dispatch_status": "dispatched" if contract_valid else None,
            "worker_authority_result_validated": contract_valid,
            "reserved_snapshot_present": contract_valid,
            "reserved_snapshot_source": "p23_d2_exact_reserved_run" if contract_valid else None,
            "reserved_snapshot_exact_task_id": claim.next_task_id if contract_valid else None,
            "reserved_snapshot_exact_run_id": claim.exact_run_id if contract_valid else None,
            "reserved_snapshot_exact_binding_validated": contract_valid,
            "reserved_snapshot_task_routed": False,
            "reserved_snapshot_task_claimed_in_this_cycle": False,
            "reserved_snapshot_run_created_in_this_cycle": False,
            "reserved_snapshot_budget_rechecked": budget_rechecked if contract_valid else False,
            "reserved_snapshot_existing_run_reused": contract_valid,
            "reserved_snapshot_shared_execution_seam_used": contract_valid,
            "reserved_snapshot_blocked_reasons": (),
            "native_process_started": False,
            "human_recovery_required": not contract_valid,
            "blocked_reasons": ("exact_worker_invocation_outcome_worker_result_invalid",) if not contract_valid else (),
            "worker_reported_git_write_activity": git_activity,
        })
    elif status == "raised":
        values = _base_outcome_values(chain, now, status="raised")
        skill_codes = tuple(item.skill_code for item in claim.worker_selected_skills)
        skill_names = tuple(item.skill_name for item in claim.worker_selected_skills)
        values.update({
            "worker_called": True,
            "worker_call_attempted": True,
            "worker_returned": False,
            "worker_raised": True,
            "worker_started": True,
            "worker_result_contract_valid": False,
            "worker_authority_result_validated": False,
            "reserved_snapshot_present": False,
            "native_process_started": False,
            "exception_type": "RuntimeError",
            "exception_summary": "Worker raised an exception; details were redacted.",
            "claim_worker_model_name": claim.worker_model_name,
            "claim_worker_model_tier": claim.worker_model_tier,
            "claim_worker_selected_skill_codes": skill_codes,
            "claim_worker_selected_skill_names": skill_names,
            "claim_worker_owner_role_code": claim.worker_owner_role_code,
            "claim_worker_upstream_role_code": claim.worker_upstream_role_code,
            "claim_worker_downstream_role_code": claim.worker_downstream_role_code,
            "human_recovery_required": True,
            "blocked_reasons": ("exact_worker_invocation_outcome_worker_raised",),
            "worker_reported_git_write_activity": False,
        })
    else:
        raise ValueError(f"Unknown status: {status}")

    provisional = ProjectDirectorCrossTaskExactWorkerInvocationOutcome.model_construct(**values)
    payload = provisional.model_dump(
        mode="python",
        exclude={"worker_invocation_outcome_fingerprint"},
    )
    values["worker_invocation_outcome_fingerprint"] = compute_p24_contract_sha256(payload)
    return ProjectDirectorCrossTaskExactWorkerInvocationOutcome.model_validate(values)


def _base_outcome_values(chain: P24Chain, now: datetime, *, status: str) -> dict[str, Any]:
    claim = chain.claim
    outcome_replay_key = ProjectDirectorCrossTaskExactWorkerInvocationOutcome.compute_worker_invocation_outcome_replay_key(
        continuation_id=claim.continuation_id,
        exact_worker_invocation_claim_id=claim.exact_worker_invocation_claim_id,
        exact_worker_invocation_claim_token=claim.worker_invocation_claim_token,
        exact_worker_start_reservation_id=claim.exact_worker_start_reservation_id,
        next_task_id=claim.next_task_id,
        exact_run_id=claim.exact_run_id,
    )
    return {
        "exact_worker_invocation_outcome_id": uuid4(),
        "worker_invocation_outcome_fingerprint": _FINGERPRINT,
        "worker_invocation_outcome_replay_key": outcome_replay_key,
        "created_at": now,
        "continuation_id": claim.continuation_id,
        "continuation_root_record_id": claim.continuation_root_record_id,
        "continuation_root_fingerprint": claim.continuation_root_fingerprint,
        "continuation_idempotency_key": claim.continuation_idempotency_key,
        "instruction_package_id": claim.instruction_package_id,
        "instruction_package_fingerprint": claim.instruction_package_fingerprint,
        "instruction_candidate_fingerprint": claim.instruction_candidate_fingerprint,
        "exact_run_reservation_id": claim.exact_run_reservation_id,
        "exact_run_reservation_fingerprint": claim.exact_run_reservation_fingerprint,
        "exact_run_reservation_replay_key": claim.exact_run_reservation_replay_key,
        "exact_worker_start_reservation_id": claim.exact_worker_start_reservation_id,
        "exact_worker_start_reservation_fingerprint": claim.exact_worker_start_reservation_fingerprint,
        "exact_worker_start_reservation_replay_key": claim.exact_worker_start_reservation_replay_key,
        "exact_worker_invocation_claim_id": claim.exact_worker_invocation_claim_id,
        "exact_worker_invocation_claim_fingerprint": claim.worker_invocation_claim_fingerprint,
        "exact_worker_invocation_claim_replay_key": claim.worker_invocation_claim_replay_key,
        "exact_worker_invocation_claim_token": claim.worker_invocation_claim_token,
        "continuation_sequence_no": 5,
        "previous_record_id": claim.exact_worker_invocation_claim_id,
        "replay_of_record_id": None,
        "action": "record_exact_worker_invocation_outcome",
        "status": status,
        "session_id": claim.session_id,
        "project_id": claim.project_id,
        "plan_version_id": claim.plan_version_id,
        "task_creation_record_id": claim.task_creation_record_id,
        "source_task_id": claim.source_task_id,
        "source_run_id": claim.source_run_id,
        "source_completion_evidence_id": claim.source_completion_evidence_id,
        "source_completion_evidence_fingerprint": claim.source_completion_evidence_fingerprint,
        "next_task_id": claim.next_task_id,
        "next_task_index": claim.next_task_index,
        "task_count": claim.task_count,
        "exact_run_id": claim.exact_run_id,
        "task_status_after": "running",
        "task_human_status_after": "none",
        "task_paused_reason_after": None,
        "run_status_after": "running",
        "run_finished_at_after": None,
        "run_failure_category_after": None,
        "run_quality_gate_passed_after": None,
        "agent_session_id": None,
        "agent_session_status": None,
        "agent_session_phase": None,
        "runtime_handle_id": None,
        "worker_call_state_indeterminate": False,
        "product_runtime_git_write_allowed": False,
        "forbidden_actions": (
            "product_runtime_git_write", "git_add", "git_commit", "git_push",
            "pull_request_creation", "merge", "branch_destruction",
            "global_pending_task_scan", "next_task_skip", "plan_mutation",
            "duplicate_task_creation", "duplicate_task_claim",
            "duplicate_run_creation", "duplicate_worker_start_reservation",
            "duplicate_worker_invocation_claim",
            "duplicate_worker_invocation_outcome",
            "worker_invocation_without_reservation",
            "worker_invocation_without_claim",
            "worker_reinvocation",
            "agent_session_creation_without_claim",
            "worker_outcome_without_claim",
            "worker_outcome_overwrite",
            "verification_command_execution", "uncontrolled_workspace_write",
        ),
    }


# ── Seed Messages ───────────────────────────────────────────────────


def seed_package_message(
    session: Session,
    package: ProjectDirectorNextTaskInstructionPackage,
) -> None:
    """Seed a package message into the database."""
    action = {
        "type": "p24_next_task_instruction_package_record",
        **package.model_dump(mode="json"),
    }
    session.add(
        ProjectDirectorMessageTable(
            id=package.package_id,
            session_id=package.session_id,
            role="assistant",
            content=f"P24 next Task instruction package: {package.package_id}",
            sequence_no=10,
            intent="cross_task_next_task_instruction_package",
            source="system",
            source_detail="p24_next_task_instruction_package_prepared",
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False,
            risk_level="high",
            related_plan_version_id=package.plan_version_id,
            related_project_id=package.project_id,
            related_task_id=package.next_task_id,
            created_at=package.created_at,
            forbidden_actions_detected_json=json.dumps(list(package.forbidden_actions)),
        )
    )
    session.commit()


def seed_root_message(
    session: Session,
    root: ProjectDirectorCrossTaskContinuationRoot,
) -> None:
    """Seed a continuation root message into the database."""
    action = {
        "type": "p24_cross_task_continuation_record",
        **root.model_dump(mode="json"),
    }
    session.add(
        ProjectDirectorMessageTable(
            id=root.record_id,
            session_id=root.session_id,
            role="assistant",
            content=f"P24 cross-Task continuation root: {root.record_id}",
            sequence_no=11,
            intent="cross_task_auto_continue",
            source="system",
            source_detail="p24_cross_task_continuation_recorded",
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False,
            risk_level="high",
            related_plan_version_id=root.plan_version_id,
            related_project_id=root.project_id,
            related_task_id=root.next_task_id,
            created_at=root.created_at,
            forbidden_actions_detected_json=json.dumps(list(root.forbidden_actions)),
        )
    )
    session.commit()


def seed_e1b_message(
    session: Session,
    reservation: ProjectDirectorCrossTaskExactRunReservation,
) -> None:
    """Seed an exact run reservation message into the database."""
    action = {
        "type": "p24_cross_task_exact_run_reservation_record",
        **reservation.model_dump(mode="json"),
    }
    session.add(
        ProjectDirectorMessageTable(
            id=reservation.exact_run_reservation_id,
            session_id=reservation.session_id,
            role="assistant",
            content=f"P24 exact next Task Run reservation: {reservation.exact_run_reservation_id}",
            sequence_no=12,
            intent="cross_task_exact_run_reservation",
            source="system",
            source_detail="p24_cross_task_exact_run_reserved",
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False,
            risk_level="high",
            related_plan_version_id=reservation.plan_version_id,
            related_project_id=reservation.project_id,
            related_task_id=reservation.next_task_id,
            created_at=reservation.created_at,
            forbidden_actions_detected_json=json.dumps(list(reservation.forbidden_actions)),
        )
    )
    session.commit()


def seed_e2a_message(
    session: Session,
    reservation: ProjectDirectorCrossTaskExactWorkerStartReservation,
) -> None:
    """Seed a worker start reservation message into the database."""
    action = {
        "type": "p24_cross_task_exact_worker_start_reservation_record",
        **reservation.model_dump(mode="json"),
    }
    session.add(
        ProjectDirectorMessageTable(
            id=reservation.exact_worker_start_reservation_id,
            session_id=reservation.session_id,
            role="assistant",
            content=f"P24 exact Worker-start reservation: {reservation.exact_worker_start_reservation_id}",
            sequence_no=13,
            intent="cross_task_exact_worker_start_reservation",
            source="system",
            source_detail="p24_cross_task_exact_worker_start_reserved",
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False,
            risk_level="high",
            related_plan_version_id=reservation.plan_version_id,
            related_project_id=reservation.project_id,
            related_task_id=reservation.next_task_id,
            created_at=reservation.created_at,
            forbidden_actions_detected_json=json.dumps(list(reservation.forbidden_actions)),
        )
    )
    session.commit()


def seed_claim_message(
    session: Session,
    claim: ProjectDirectorCrossTaskExactWorkerInvocationClaim,
) -> None:
    """Seed a claim message into the database."""
    action = {
        "type": CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_ACTION_TYPE,
        **claim.model_dump(mode="json"),
    }
    session.add(
        ProjectDirectorMessageTable(
            id=claim.exact_worker_invocation_claim_id,
            session_id=claim.session_id,
            role="assistant",
            content=f"P24 exact Worker invocation claim: {claim.exact_worker_invocation_claim_id}",
            sequence_no=14,
            intent=CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_INTENT,
            source="system",
            source_detail=CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False,
            risk_level="high",
            related_plan_version_id=claim.plan_version_id,
            related_project_id=claim.project_id,
            related_task_id=claim.next_task_id,
            created_at=claim.created_at,
            forbidden_actions_detected_json=json.dumps(list(claim.forbidden_actions)),
        )
    )
    session.commit()


def seed_outcome_message(
    session: Session,
    outcome: ProjectDirectorCrossTaskExactWorkerInvocationOutcome,
) -> None:
    """Seed an outcome message into the database."""
    action = {
        "type": CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_ACTION_TYPE,
        **outcome.model_dump(mode="json"),
    }
    session.add(
        ProjectDirectorMessageTable(
            id=outcome.exact_worker_invocation_outcome_id,
            session_id=outcome.session_id,
            role="assistant",
            content=f"P24 exact Worker invocation outcome: {outcome.exact_worker_invocation_outcome_id}",
            sequence_no=15,
            intent=CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_INTENT,
            source="system",
            source_detail=CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False,
            risk_level="high",
            related_plan_version_id=outcome.plan_version_id,
            related_project_id=outcome.project_id,
            related_task_id=outcome.next_task_id,
            created_at=outcome.created_at,
            forbidden_actions_detected_json=json.dumps(list(outcome.forbidden_actions)),
        )
    )
    session.commit()


def seed_full_p24_chain(
    session: Session,
    chain: P24Chain,
) -> None:
    """Seed the complete P24 chain into the database."""
    seed_package_message(session, chain.package)
    seed_root_message(session, chain.root)
    seed_e1b_message(session, chain.exact_run_reservation)
    seed_e2a_message(session, chain.worker_start_reservation)
    seed_claim_message(session, chain.claim)


# ── Run Helpers ─────────────────────────────────────────────────────


def seed_run(
    session: Session,
    *,
    run_id: UUID,
    task_id: UUID,
    model_name: str = "test-model",
    started_at: datetime | None = None,
    created_at: datetime | None = None,
    strategy_decision: RunStrategyDecision | None = None,
) -> None:
    """Seed a running Run into the database."""
    now = started_at or _now_utc()
    sd = strategy_decision or RunStrategyDecision(
        version="1",
        project_stage=None,
        owner_role_code=ProjectRoleCode.ARCHITECT,
        model_tier="standard",
        model_name=model_name,
        selected_skill_codes=["test-skill"],
        selected_skill_names=["Test Skill"],
        budget_pressure_level=RunBudgetPressureLevel.NORMAL,
        budget_action=RunBudgetStrategyAction.FULL_SPEED,
        strategy_code="normal",
        summary="Normal execution",
        role_model_policy_source="test",
        role_model_policy_desired_tier="standard",
        role_model_policy_adjusted_tier="standard",
        role_model_policy_final_tier="standard",
        role_model_policy_stage_override_applied=False,
        rule_codes=["normal"],
        reasons=[
            RunStrategyReasonItem(
                code="normal", label="Normal", detail="Normal", score=1.0,
            ),
        ],
    )
    session.add(
        RunTable(
            id=run_id,
            task_id=task_id,
            status="running",
            model_name=model_name,
            route_reason="test",
            routing_score=1.0,
            routing_score_breakdown=json.dumps([{"code": "test", "label": "Test", "score": 1.0, "detail": "test"}]),
            strategy_decision_json=json.dumps(sd.model_dump(mode="json")),
            owner_role_code="architect",
            upstream_role_code=None,
            downstream_role_code=None,
            handoff_reason="test",
            dispatch_status="dispatched",
            started_at=now,
            created_at=created_at or now,
        )
    )
    session.commit()


# ── Fake TaskWorker ─────────────────────────────────────────────────


class FakeTaskWorker:
    """Fake TaskWorker for P24 tests. Records calls and returns controlled results."""

    def __init__(self, *, session=None, result=None, exception=None):
        self.session = session
        self._result = result
        self._exception = exception
        self.run_reserved_once_calls: list[dict] = []
        self.run_once_calls: list[dict] = []
        self._call_lock = threading.Lock()
        # Required by OutcomeService._require_shared_session
        # These must be set AFTER the real session is known
        self._task_repo = None
        self._run_repo = None
        self._agent_sess_repo = None

    def bind_session(self, session, task_repo, run_repo, agent_sess_repo):
        """Bind the worker to a shared session and repos."""
        self.session = session
        self._task_repo = task_repo
        self._run_repo = run_repo
        self._agent_sess_repo = agent_sess_repo

    @property
    def task_repository(self):
        return self._task_repo or type("R", (), {"session": self.session})()

    @property
    def run_repository(self):
        return self._run_repo or type("R", (), {"session": self.session})()

    @property
    def agent_conversation_service(self):
        repo = self._agent_sess_repo or type("R", (), {"session": self.session})()
        return type("R", (), {"agent_session_repository": repo})()

    @property
    def call_count(self) -> int:
        with self._call_lock:
            return len(self.run_reserved_once_calls)

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


# ── Service Builders ────────────────────────────────────────────────


def make_claim_service(
    session,
    *,
    msg_repo=None,
    task_repo=None,
    run_repo=None,
    agent_sess_repo=None,
):
    """Create a real ClaimService with real repos."""
    from app.services.project_director_cross_task_exact_worker_invocation_claim_service import (
        ProjectDirectorCrossTaskExactWorkerInvocationClaimService,
    )
    if msg_repo is None:
        msg_repo = ProjectDirectorMessageRepository(session)
    if task_repo is None:
        task_repo = TaskRepository(session)
    if run_repo is None:
        run_repo = RunRepository(session)
    if agent_sess_repo is None:
        agent_sess_repo = AgentSessionRepository(session)
    return ProjectDirectorCrossTaskExactWorkerInvocationClaimService(
        message_repository=msg_repo,
        task_repository=task_repo,
        run_repository=run_repo,
        agent_session_repository=agent_sess_repo,
    )


def make_outcome_service(
    session,
    *,
    msg_repo=None,
    task_repo=None,
    run_repo=None,
    agent_sess_repo=None,
    claim_service=None,
    task_worker=None,
):
    """Create a real OutcomeService with real repos."""
    from app.services.project_director_cross_task_exact_worker_invocation_outcome_service import (
        ProjectDirectorCrossTaskExactWorkerInvocationOutcomeService,
    )
    if msg_repo is None:
        msg_repo = ProjectDirectorMessageRepository(session)
    if task_repo is None:
        task_repo = TaskRepository(session)
    if run_repo is None:
        run_repo = RunRepository(session)
    if agent_sess_repo is None:
        agent_sess_repo = AgentSessionRepository(session)
    if claim_service is None:
        claim_service = make_claim_service(
            session,
            msg_repo=msg_repo,
            task_repo=task_repo,
            run_repo=run_repo,
            agent_sess_repo=agent_sess_repo,
        )
    if task_worker is None:
        task_worker = FakeTaskWorker(session=session)
    # Bind the worker to share the session
    if isinstance(task_worker, FakeTaskWorker):
        task_worker.bind_session(session, task_repo, run_repo, agent_sess_repo)
    return ProjectDirectorCrossTaskExactWorkerInvocationOutcomeService(
        message_repository=msg_repo,
        task_repository=task_repo,
        run_repository=run_repo,
        agent_session_repository=agent_sess_repo,
        claim_service=claim_service,
        task_worker=task_worker,
    )


# ── AgentSession Seed Helper ────────────────────────────────────────


def seed_agent_session(
    session: Session,
    *,
    agent_session_id: UUID | None = None,
    project_id: UUID,
    task_id: UUID,
    run_id: UUID,
    status: str = "running",
    current_phase: str = "context_ready",
) -> UUID:
    """Seed an AgentSession into the database."""
    from app.core.db_tables import AgentSessionTable
    aid = agent_session_id or uuid4()
    session.add(
        AgentSessionTable(
            id=aid,
            project_id=project_id,
            task_id=task_id,
            run_id=run_id,
            status=status,
            current_phase=current_phase,
        )
    )
    session.commit()
    return aid


# ── SharedGatedWorkerController for Concurrency ────────────────────


class SharedGatedWorkerController:
    """Thread-safe controller for concurrency tests.

    Thread A calls `run_reserved_once` which blocks until `release()` is called.
    Thread B's adapter raises AssertionError if called.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._call_count = 0
        self._calls: list[dict] = []
        self._entered = threading.Event()
        self._release = threading.Event()
        self._result = None
        self._exception = None

    @property
    def call_count(self) -> int:
        with self._lock:
            return self._call_count

    @property
    def calls(self) -> list[dict]:
        with self._lock:
            return list(self._calls)

    def set_result(self, result):
        self._result = result

    def set_exception(self, exc):
        self._exception = exc

    def run_reserved_once(self, *, task_id, run_id):
        with self._lock:
            self._call_count += 1
            self._calls.append({"task_id": task_id, "run_id": run_id})
        self._entered.set()
        released = self._release.wait(timeout=10)
        assert released, "Worker was not released before timeout"
        if self._exception:
            raise self._exception
        return self._result

    def wait_until_entered(self, timeout: float = 10) -> bool:
        reached = self._entered.wait(timeout=timeout)
        assert reached, "Worker did not enter run_reserved_once before timeout"
        return reached

    def release(self):
        self._release.set()


class ExplodingWorkerAdapter:
    """Raises AssertionError if run_reserved_once is called."""

    def __init__(self, session=None):
        self.session = session
        self._task_repo = None
        self._run_repo = None
        self._agent_sess_repo = None

    def bind_session(self, session, task_repo, run_repo, agent_sess_repo):
        self.session = session
        self._task_repo = task_repo
        self._run_repo = run_repo
        self._agent_sess_repo = agent_sess_repo

    @property
    def task_repository(self):
        return self._task_repo or type("R", (), {"session": self.session})()

    @property
    def run_repository(self):
        return self._run_repo or type("R", (), {"session": self.session})()

    @property
    def agent_conversation_service(self):
        repo = self._agent_sess_repo or type("R", (), {"session": self.session})()
        return type("R", (), {"agent_session_repository": repo})()

    def run_reserved_once(self, *, task_id, run_id):
        raise AssertionError("ExplodingWorkerAdapter must not be called")

    def run_once(self, *, project_id=None):
        raise AssertionError("ExplodingWorkerAdapter must not be called")


# ── Failing Message Repository Wrapper ──────────────────────────────


class FailingMessageRepositoryWrapper:
    """Wraps a real MessageRepository, intercepting create/post_write."""

    def __init__(self, real_repo):
        self._real = real_repo
        self._fail_create = False
        self._fail_post_write = False
        self._create_call_count = 0

    def __getattr__(self, name):
        return getattr(self._real, name)

    @property
    def _session(self):
        return self._real._session

    def create(self, message):
        self._create_call_count += 1
        if self._fail_create:
            raise ValueError("Simulated create failure")
        return self._real.create(message)

    def sqlite_immediate_transaction(self):
        return self._real.sqlite_immediate_transaction()

    def list_by_session_id(self, **kwargs):
        return self._real.list_by_session_id(**kwargs)

    def get_next_sequence_no(self, **kwargs):
        return self._real.get_next_sequence_no(**kwargs)


# ── Message Corruption Helper ───────────────────────────────────────


def corrupt_message_field(
    session: Session,
    message_id: UUID,
    *,
    field: str,
    value: Any,
) -> None:
    """Directly corrupt a field on a persisted message."""
    from app.core.db_tables import ProjectDirectorMessageTable
    msg = session.get(ProjectDirectorMessageTable, message_id)
    if msg is None:
        raise ValueError(f"Message {message_id} not found")
    setattr(msg, field, value)
    session.commit()


# ── Full E4B Invocation Helper ──────────────────────────────────────


def invoke_exact_worker_full(
    session_local,
    chain: P24Chain,
    *,
    task_worker=None,
    task_status: str = "running",
    strategy_decision=None,
    agent_sessions: list[dict] | None = None,
) -> tuple:
    """Seed full chain and invoke E4B. Returns (result, fake_worker, msg_repo)."""
    s = session_local()
    seed_base_records(
        s,
        session_id=chain.session_id,
        project_id=chain.project_id,
        task_id=chain.next_task_id,
        plan_version_id=chain.plan_version_id,
        task_status=task_status,
    )
    seed_package_message(s, chain.package)
    seed_root_message(s, chain.root)
    seed_e1b_message(s, chain.exact_run_reservation)
    seed_e2a_message(s, chain.worker_start_reservation)
    sd = strategy_decision or RunStrategyDecision(
        version="1",
        project_stage=None,
        owner_role_code=chain.claim.worker_owner_role_code,
        model_tier=chain.claim.worker_model_tier,
        model_name=chain.claim.worker_model_name,
        selected_skill_codes=[sk.skill_code for sk in chain.claim.worker_selected_skills],
        selected_skill_names=[sk.skill_name for sk in chain.claim.worker_selected_skills],
        budget_pressure_level=RunBudgetPressureLevel.NORMAL,
        budget_action=RunBudgetStrategyAction.FULL_SPEED,
        strategy_code="normal",
        summary="Normal execution",
        role_model_policy_source="test",
        role_model_policy_desired_tier=chain.claim.worker_model_tier,
        role_model_policy_adjusted_tier=chain.claim.worker_model_tier,
        role_model_policy_final_tier=chain.claim.worker_model_tier,
        role_model_policy_stage_override_applied=False,
        rule_codes=["normal"],
        reasons=[RunStrategyReasonItem(code="normal", label="Normal", detail="Normal", score=1.0)],
    )
    seed_run(
        s,
        run_id=chain.exact_run_id,
        task_id=chain.next_task_id,
        model_name=chain.claim.worker_model_name,
        started_at=chain.claim.exact_run_started_at,
        created_at=chain.claim.exact_run_created_at,
        strategy_decision=sd,
    )
    if agent_sessions:
        for as_info in agent_sessions:
            seed_agent_session(
                s,
                agent_session_id=as_info.get("id"),
                project_id=as_info.get("project_id", chain.project_id),
                task_id=as_info.get("task_id", chain.next_task_id),
                run_id=as_info.get("run_id", chain.exact_run_id),
                status=as_info.get("status", "running"),
                current_phase=as_info.get("current_phase", "executing"),
            )
    s.close()

    if task_worker is None:
        snapshot = WorkerReservedRunExecutionSnapshot(
            source="p23_d2_exact_reserved_run",
            exact_task_id=chain.next_task_id,
            exact_run_id=chain.exact_run_id,
            reserved_run_execution_requested=True,
            exact_binding_validated=True,
            task_routed=False,
            task_claimed_in_this_cycle=False,
            run_created_in_this_cycle=False,
            budget_rechecked=True,
            existing_run_reused=True,
            shared_execution_seam_used=True,
            product_runtime_git_write_allowed=False,
            blocked_reasons=[],
        )
        task_worker = FakeTaskWorker(
            session=None,
            result=WorkerRunResult(
                claimed=True,
                message="fake worker executed",
                execution_mode="fake",
                result_summary="fake execution",
                model_name=chain.claim.worker_model_name,
                model_tier=chain.claim.worker_model_tier,
                selected_skill_codes=[sk.skill_code for sk in chain.claim.worker_selected_skills],
                selected_skill_names=[sk.skill_name for sk in chain.claim.worker_selected_skills],
                owner_role_code=chain.claim.worker_owner_role_code,
                upstream_role_code=chain.claim.worker_upstream_role_code,
                downstream_role_code=chain.claim.worker_downstream_role_code,
                route_reason="test",
                strategy_code="normal",
                dispatch_status="dispatched",
                reserved_run_execution_snapshot=snapshot,
            ),
        )

    session, msg_repo, sess_repo, task_repo, run_repo, agent_sess_repo = make_repos(session_local)
    outcome_svc = make_outcome_service(
        session,
        msg_repo=msg_repo,
        task_repo=task_repo,
        run_repo=run_repo,
        agent_sess_repo=agent_sess_repo,
        task_worker=task_worker,
    )

    result = outcome_svc.invoke_exact_worker(
        session_id=chain.session_id,
        project_id=chain.project_id,
        continuation_root_record_id=chain.root_record_id,
        instruction_package_id=chain.package_id,
        exact_run_reservation_id=chain.exact_run_reservation_id,
        exact_worker_start_reservation_id=chain.worker_start_reservation_id,
    )

    return result, task_worker, msg_repo


def build_worker_result_for_chain(
    chain: P24Chain,
    *,
    model_name: str | None = None,
    model_tier: str | None = None,
    skill_codes: list[str] | None = None,
    skill_names: list[str] | None = None,
    owner_role_code=None,
    upstream_role_code=None,
    downstream_role_code=None,
    snapshot_source: str = "p23_d2_exact_reserved_run",
    snapshot_task_id: UUID | None = None,
    snapshot_run_id: UUID | None = None,
    exact_binding_validated: bool = True,
    task_routed: bool = False,
    task_claimed_in_this_cycle: bool = False,
    run_created_in_this_cycle: bool = False,
    existing_run_reused: bool = True,
    shared_execution_seam_used: bool = True,
    snapshot_blocked_reasons: list[str] | None = None,
    budget_rechecked: bool = True,
    git_commit_triggered: bool = False,
    git_operation_applied: bool = False,
    delivery_gate_allows_write: bool = False,
    delivery_push_triggered: bool = False,
    snapshot_product_git_write: bool = False,
    message: str = "fake worker executed",
) -> WorkerRunResult:
    """Build a WorkerRunResult with customizable fields for testing."""
    claim = chain.claim
    snapshot = WorkerReservedRunExecutionSnapshot(
        source=snapshot_source,
        exact_task_id=snapshot_task_id if snapshot_task_id is not None else claim.next_task_id,
        exact_run_id=snapshot_run_id if snapshot_run_id is not None else claim.exact_run_id,
        reserved_run_execution_requested=True,
        exact_binding_validated=exact_binding_validated,
        task_routed=task_routed,
        task_claimed_in_this_cycle=task_claimed_in_this_cycle,
        run_created_in_this_cycle=run_created_in_this_cycle,
        budget_rechecked=budget_rechecked,
        existing_run_reused=existing_run_reused,
        shared_execution_seam_used=shared_execution_seam_used,
        product_runtime_git_write_allowed=snapshot_product_git_write,
        blocked_reasons=snapshot_blocked_reasons or [],
    )
    return WorkerRunResult(
        claimed=True,
        message=message,
        execution_mode="fake",
        result_summary="fake execution",
        model_name=model_name if model_name is not None else claim.worker_model_name,
        model_tier=model_tier if model_tier is not None else claim.worker_model_tier,
        selected_skill_codes=skill_codes if skill_codes is not None else [sk.skill_code for sk in claim.worker_selected_skills],
        selected_skill_names=skill_names if skill_names is not None else [sk.skill_name for sk in claim.worker_selected_skills],
        owner_role_code=owner_role_code if owner_role_code is not None else claim.worker_owner_role_code,
        upstream_role_code=upstream_role_code if upstream_role_code is not None else claim.worker_upstream_role_code,
        downstream_role_code=downstream_role_code if downstream_role_code is not None else claim.worker_downstream_role_code,
        route_reason="test",
        strategy_code="normal",
        dispatch_status="dispatched",
        reserved_run_execution_snapshot=snapshot,
        git_diff_dry_run_git_commit_triggered=git_commit_triggered,
        git_operation_dry_run_operation_applied=git_operation_applied,
        delivery_gate_evidence_gate_allows_write=delivery_gate_allows_write,
        delivery_human_approval_git_push_triggered=delivery_push_triggered,
    )


# ── Phase 2 Injection Helpers ───────────────────────────────────────


class Phase2InjectingClaimServiceWrapper:
    """Wraps ClaimService: after creating claim, injects state changes via independent session."""

    def __init__(self, real_claim_service, session_local, *, inject_fn):
        self._real = real_claim_service
        self._session_local = session_local
        self._inject_fn = inject_fn
        self._last_claim_result = None

    def __getattr__(self, name):
        return getattr(self._real, name)

    @property
    def _message_repository(self):
        return self._real._message_repository

    @property
    def _task_repository(self):
        return self._real._task_repository

    @property
    def _run_repository(self):
        return self._real._run_repository

    @property
    def _agent_session_repository(self):
        return self._real._agent_session_repository

    def claim_exact_worker_invocation(self, **kwargs):
        result = self._real.claim_exact_worker_invocation(**kwargs)
        self._last_claim_result = result
        if result.status == "invocation_claim_created":
            # Inject state change via independent session
            s = self._session_local()
            try:
                self._inject_fn(s, kwargs)
                s.commit()
            finally:
                s.close()
        return result


class AgentSessionCreatingWorker:
    """Creates AgentSession(s) during run_reserved_once via independent session."""

    def __init__(self, session_local, *, result=None, agent_sessions_to_create=None):
        self._session_local = session_local
        self._result = result
        self._agent_sessions = agent_sessions_to_create or []
        self._call_count = 0
        self._calls = []
        self._lock = threading.Lock()
        self.session = None
        self._task_repo = None
        self._run_repo = None
        self._agent_sess_repo = None

    def bind_session(self, session, task_repo, run_repo, agent_sess_repo):
        self.session = session
        self._task_repo = task_repo
        self._run_repo = run_repo
        self._agent_sess_repo = agent_sess_repo

    @property
    def task_repository(self):
        return self._task_repo or type("R", (), {"session": self.session})()

    @property
    def run_repository(self):
        return self._run_repo or type("R", (), {"session": self.session})()

    @property
    def agent_conversation_service(self):
        repo = self._agent_sess_repo or type("R", (), {"session": self.session})()
        return type("R", (), {"agent_session_repository": repo})()

    @property
    def call_count(self) -> int:
        with self._lock:
            return self._call_count

    def run_reserved_once(self, *, task_id, run_id):
        with self._lock:
            self._call_count += 1
            self._calls.append({"task_id": task_id, "run_id": run_id})
        # Create AgentSessions via independent session
        for as_info in self._agent_sessions:
            s = self._session_local()
            try:
                seed_agent_session(
                    s,
                    project_id=as_info["project_id"],
                    task_id=as_info["task_id"],
                    run_id=as_info["run_id"],
                    status=as_info.get("status", "running"),
                    current_phase=as_info.get("current_phase", "executing"),
                )
            finally:
                s.close()
        if self._result is not None:
            return self._result
        raise AssertionError("AgentSessionCreatingWorker: no result configured")

    def run_once(self, *, project_id=None):
        return None


class OutcomeOnlyFailingMessageRepository:
    """Wraps a real MessageRepository: allows Claim messages, fails on Outcome messages."""

    def __init__(self, real_repo):
        self._real = real_repo
        self._create_call_count = 0
        self._fail_outcome = False

    def __getattr__(self, name):
        return getattr(self._real, name)

    @property
    def _session(self):
        return self._real._session

    def create(self, message):
        self._create_call_count += 1
        if self._fail_outcome and hasattr(message, 'intent') and \
           message.intent == "cross_task_exact_worker_invocation_outcome":
            raise ValueError("Simulated Outcome create failure")
        if self._fail_outcome and hasattr(message, 'source_detail') and \
           message.source_detail == "p24_cross_task_exact_worker_invocation_outcome_recorded":
            raise ValueError("Simulated Outcome create failure")
        return self._real.create(message)

    def sqlite_immediate_transaction(self):
        return self._real.sqlite_immediate_transaction()

    def list_by_session_id(self, **kwargs):
        return self._real.list_by_session_id(**kwargs)

    def get_next_sequence_no(self, **kwargs):
        return self._real.get_next_sequence_no(**kwargs)


class PostWriteFailingOutcomeRepository:
    """Wraps a real MessageRepository: allows create, fails on post_write_validate for Outcome."""

    def __init__(self, real_repo):
        self._real = real_repo
        self._fail_post_write = False
        self._create_call_count = 0

    def __getattr__(self, name):
        return getattr(self._real, name)

    @property
    def _session(self):
        return self._real._session

    def create(self, message):
        self._create_call_count += 1
        return self._real.create(message)

    def sqlite_immediate_transaction(self):
        return self._real.sqlite_immediate_transaction()

    def list_by_session_id(self, **kwargs):
        return self._real.list_by_session_id(**kwargs)

    def get_next_sequence_no(self, **kwargs):
        return self._real.get_next_sequence_no(**kwargs)
