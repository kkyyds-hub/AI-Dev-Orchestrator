"""Shared test support for P25 dynamic convergence and terminal escalation tests."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from dataclasses import dataclass
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
    TaskTable,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
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
# NOTE: Service imports are deferred to make_* functions to avoid circular imports.
# The convergence/terminal escalation service imports transitively pull in many
# service modules that form a cycle at import time.


# ── SHA256 Constants ──────────────────────────────────────────────────

SHA256 = lambda data: hashlib.sha256(data).hexdigest()

DIFF_SHA256 = SHA256(b"p25 diff content base")
NEW_DIFF_SHA256 = SHA256(b"p25 new diff content")
PREVIOUS_DIFF_SHA256 = SHA256(b"p25 previous diff content")
PROMPT_SHA256 = SHA256(b"p25 review prompt content")
RAW_OUTPUT_SHA256 = SHA256(b"p25 raw review output")
MANIFEST_FINGERPRINT = "a" * 64
CANDIDATE_DIFF_FINGERPRINT = "b" * 64
REVIEW_RESULT_FINGERPRINT = "c" * 64
REVIEW_SEMANTIC_FINGERPRINT = "d" * 64
OUTCOME_FINGERPRINT = "e" * 64
CLAIM_FINGERPRINT = "f" * 64
PACKAGE_FINGERPRINT = "1" * 64
RESERVATION_FINGERPRINT = "2" * 64
CONVERGENCE_FINGERPRINT = "3" * 64
TERMINAL_FINGERPRINT = "4" * 64
WORKSPACE_PATH = "/tmp/test-workspace-p25"


# ── Database Helpers ──────────────────────────────────────────────────


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
            id=pid, name="Test P25", summary="Test project for P25",
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
            id=tid, project_id=pid, title="Test P25 task",
            status=task_status, priority="normal",
            input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
            risk_level="normal", human_status="none",
            source_draft_id="p25-test-draft", acceptance_criteria=acceptance,
        )
    )
    session.add(
        ProjectDirectorSessionTable(
            id=sid, project_id=pid,
            goal_text="Test P25 goal", constraints="", status="confirmed",
        )
    )
    session.commit()
    return {"project_id": pid, "session_id": sid, "task_id": tid}


def make_repos(session_local):
    session = session_local()
    msg_repo = ProjectDirectorMessageRepository(session)
    sess_repo = ProjectDirectorSessionRepository(session)
    task_repo = TaskRepository(session)
    return session, msg_repo, sess_repo, task_repo


# ── Message Counting Utility ──────────────────────────────────────────


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


# ── P25-B Instruction Package Message Seeding ─────────────────────────


P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_SOURCE_DETAIL = (
    "p25_b_bounded_rework_instruction_package_prepared"
)
P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_ACTION_TYPE = (
    "p25_bounded_rework_instruction_package_record"
)
P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_SCHEMA_VERSION = "p25-b.v1"
P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_INTENT = (
    "bounded_rework_instruction_package"
)

P25_BOUNDED_REWORK_CANDIDATE_DIFF_SOURCE_DETAIL = "p25_g_candidate_diff_generated"
P25_BOUNDED_REWORK_CANDIDATE_DIFF_ACTION_TYPE = (
    "p25_bounded_rework_candidate_diff_record"
)
P25_BOUNDED_REWORK_CANDIDATE_DIFF_SCHEMA_VERSION = "p25-g-d.v1"
P25_BOUNDED_REWORK_CANDIDATE_DIFF_INTENT = "bounded_rework_candidate_diff"

P25_BOUNDED_REWORK_REVIEW_OUTCOME_SOURCE_DETAIL = (
    "p25_h_bounded_rework_review_invocation_outcome_persisted"
)
P25_BOUNDED_REWORK_REVIEW_OUTCOME_ACTION_TYPE = (
    "p25_h_bounded_rework_review_invocation_outcome_record"
)
P25_BOUNDED_REWORK_REVIEW_OUTCOME_SCHEMA_VERSION = "p25-h-o.v1"
P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT = (
    "bounded_rework_review_reentry_invocation_outcome"
)

P22_POST_REVIEW_AUTOMATION_SOURCE_DETAIL = "p22_post_review_automation_orchestrated"
P22_POST_REVIEW_AUTOMATION_ACTION_TYPE = "p22_post_review_automation_record"
P22_POST_REVIEW_AUTOMATION_SCHEMA_VERSION = "p22-b.v1"

P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SCHEMA_VERSION = (
    "p25-i-b-convergence-decision.v1"
)
P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SOURCE_DETAIL = (
    "p25_i_b_bounded_rework_convergence_decided"
)
P25_BOUNDED_REWORK_CONVERGENCE_DECISION_ACTION_TYPE = (
    "p25_bounded_rework_convergence_decision_record"
)

P25_BOUNDED_REWORK_TERMINAL_ESCALATION_SCHEMA_VERSION = (
    "p25-i-c2-terminal-escalation-package.v1"
)
P25_BOUNDED_REWORK_TERMINAL_ESCALATION_SOURCE_DETAIL = (
    "p25_i_c2_terminal_escalation_package_prepared"
)
P25_BOUNDED_REWORK_TERMINAL_ESCALATION_ACTION_TYPE = (
    "p25_bounded_rework_terminal_escalation_package_record"
)


def _seed_p25_package_message(
    session: Session,
    *,
    session_id: UUID,
    task_id: UUID,
    project_id: UUID,
    package_id: UUID | None = None,
    base_commit_sha: str | None = None,
    source_candidate_diff_message_id: UUID | None = None,
    source_candidate_diff_sha256: str | None = None,
    rework_attempt_index: int = 0,
    rework_attempt_limit: int = 3,
    seq_no: int = 10,
) -> UUID:
    """Seed a P25-B instruction package message (initial bounded rework package)."""
    package_id = package_id or uuid4()
    base_commit_sha = base_commit_sha or "a" * 40
    source_candidate_diff_message_id = (
        source_candidate_diff_message_id or uuid4()
    )
    source_candidate_diff_sha256 = source_candidate_diff_sha256 or DIFF_SHA256

    now = datetime.now(timezone.utc).isoformat()
    authority = {
        "session_id": str(session_id),
        "project_id": str(project_id),
    }
    action = {
        "type": P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_ACTION_TYPE,
        "schema_version": P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_SCHEMA_VERSION,
        "package_id": str(package_id),
        "package_fingerprint": PACKAGE_FINGERPRINT,
        "package_replay_key": SHA256(str(package_id).encode()),
        "created_at": now,
        "authority": authority,
        "exact_task_id": str(task_id),
        "exact_run_id": str(uuid4()),
        "rework_attempt_index": rework_attempt_index,
        "rework_attempt_limit": rework_attempt_limit,
        "base_commit_sha": base_commit_sha,
        "base_snapshot_fingerprint": "a" * 64,
        "source_candidate_diff_message_id": str(source_candidate_diff_message_id),
        "source_candidate_diff_sha256": source_candidate_diff_sha256,
        "allowed_scope_paths": ["src/"],
        "forbidden_scope_paths": [".git/"],
        "workspace_binding": {
            "workspace_path": WORKSPACE_PATH,
        },
        "repository_binding": {
            "repository_root": "/tmp/test-repo-p25",
        },
        "executor_instructions": "Execute bounded rework.",
        "reviewer_instructions": "Review the diff.",
    }
    session.add(
        ProjectDirectorMessageTable(
            id=package_id, session_id=session_id, role="assistant",
            content="P25 bounded rework instruction package prepared.",
            sequence_no=seq_no,
            intent=P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_INTENT,
            source="system",
            source_detail=P25_BOUNDED_REWORK_INSTRUCTION_PACKAGE_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False, risk_level="high",
            related_project_id=project_id, related_task_id=task_id,
        )
    )
    session.commit()
    return package_id


def _seed_candidate_diff_message(
    session: Session,
    *,
    session_id: UUID,
    task_id: UUID,
    project_id: UUID,
    candidate_diff_id: UUID | None = None,
    source_outcome_id: UUID | None = None,
    source_package_id: UUID | None = None,
    diff_status: str = "generated",
    new_diff_sha256: str | None = None,
    previous_diff_sha256: str | None = None,
    non_convergence_reason: str | None = None,
    unified_diff_text: str = "diff --git a/src/example.py b/src/example.py\n+new line",
    seq_no: int = 20,
) -> UUID:
    """Seed a P25-G candidate diff message.

    When diff_status is "generated" the diff is considered a real change.
    When diff_status is "non_convergence" the diff did not produce a change.
    """
    candidate_diff_id = candidate_diff_id or uuid4()
    source_outcome_id = source_outcome_id or uuid4()
    source_package_id = source_package_id or uuid4()
    previous_diff_sha256 = previous_diff_sha256 or PREVIOUS_DIFF_SHA256
    if new_diff_sha256 is None:
        new_diff_sha256 = hashlib.sha256(
            unified_diff_text.encode("utf-8")
        ).hexdigest()

    now = datetime.now(timezone.utc).isoformat()
    authority = {
        "session_id": str(session_id),
        "project_id": str(project_id),
    }
    action = {
        "type": P25_BOUNDED_REWORK_CANDIDATE_DIFF_ACTION_TYPE,
        "schema_version": P25_BOUNDED_REWORK_CANDIDATE_DIFF_SCHEMA_VERSION,
        "candidate_diff_id": str(candidate_diff_id),
        "candidate_diff_fingerprint": CANDIDATE_DIFF_FINGERPRINT,
        "candidate_diff_replay_key": SHA256(str(candidate_diff_id).encode()),
        "created_at": now,
        "diff_status": diff_status,
        "source_attempt_id": str(uuid4()),
        "source_outcome_id": str(source_outcome_id),
        "source_outcome_fingerprint": OUTCOME_FINGERPRINT,
        "source_claim_id": str(uuid4()),
        "source_reservation_id": str(uuid4()),
        "source_package_id": str(source_package_id),
        "candidate_manifest_id": str(uuid4()),
        "candidate_manifest_fingerprint": MANIFEST_FINGERPRINT,
        "authority": authority,
        "exact_task_id": str(task_id),
        "exact_run_id": str(uuid4()),
        "rework_attempt_index": 0,
        "rework_attempt_limit": 3,
        "previous_diff_message_id": str(uuid4()),
        "previous_diff_sha256": previous_diff_sha256,
        "base_commit_sha": "a" * 40,
        "base_snapshot_fingerprint": "a" * 64,
        "base_content_source": "exact_git_commit_object",
        "readonly_base_snapshot_verified": True,
        "workspace_after_manifest_fingerprint": "a" * 64,
        "workspace_after_content_fingerprint": "b" * 64,
        "scope_paths": ["src/example.py"],
        "diff_entries": [
            {
                "relative_path": "src/example.py",
                "operation": "update",
                "base_file_existed": True,
                "candidate_file_existed": True,
                "base_content_sha256": "c" * 64,
                "candidate_content_sha256": "d" * 64,
                "unified_diff": unified_diff_text[:100],
                "diff_bytes": len(unified_diff_text),
            }
        ],
        "unified_diff_text": unified_diff_text,
        "new_diff_sha256": new_diff_sha256,
        "diff_bytes": len(unified_diff_text),
        "diff_file_count": 1,
        "non_convergence_reason": non_convergence_reason,
    }
    session.add(
        ProjectDirectorMessageTable(
            id=candidate_diff_id, session_id=session_id, role="assistant",
            content=(
                f"P25 bounded rework candidate diff: "
                f"{candidate_diff_id} ({diff_status})"
            ),
            sequence_no=seq_no,
            intent=P25_BOUNDED_REWORK_CANDIDATE_DIFF_INTENT,
            source="system",
            source_detail=P25_BOUNDED_REWORK_CANDIDATE_DIFF_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False, risk_level="high",
            related_project_id=project_id, related_task_id=task_id,
        )
    )
    session.commit()
    return candidate_diff_id


def _seed_review_outcome_message(
    session: Session,
    *,
    session_id: UUID,
    task_id: UUID,
    project_id: UUID,
    review_outcome_id: UUID | None = None,
    source_candidate_diff_id: UUID | None = None,
    source_candidate_diff_sha256: str | None = None,
    verdict: str = "no_blocking_findings",
    risk_level: str = "low",
    outcome_status: str = "validated_output",
    seq_no: int = 30,
) -> UUID:
    """Seed a P25-H review outcome message with configurable verdict/risk."""
    review_outcome_id = review_outcome_id or uuid4()
    source_candidate_diff_id = source_candidate_diff_id or uuid4()
    source_candidate_diff_sha256 = source_candidate_diff_sha256 or NEW_DIFF_SHA256

    now = datetime.now(timezone.utc).isoformat()
    authority = {
        "session_id": str(session_id),
        "project_id": str(project_id),
    }

    adapter_result = None
    review_semantic_fingerprint = None
    if outcome_status == "validated_output":
        adapter_result = {
            "adapter_status": "validated_output",
            "verdict": verdict,
            "risk_level": risk_level,
            "summary": "Review completed.",
            "findings": [],
            "recommended_next_step": "Proceed.",
            "review_output_schema_version": "p25-h-output.v1",
            "review_prompt_sha256": PROMPT_SHA256,
            "review_prompt_bytes": 100,
            "review_scope_paths": ["src/example.py"],
            "requested_reviewer_executor": "codex",
            "source_candidate_diff_sha256": source_candidate_diff_sha256,
        }
        review_semantic_fingerprint = REVIEW_SEMANTIC_FINGERPRINT

    action = {
        "type": P25_BOUNDED_REWORK_REVIEW_OUTCOME_ACTION_TYPE,
        "schema_version": P25_BOUNDED_REWORK_REVIEW_OUTCOME_SCHEMA_VERSION,
        "review_outcome_replay_key": SHA256(str(review_outcome_id).encode()),
        "created_at": now,
        "outcome_status": outcome_status,
        "review_attempt_id": str(uuid4()),
        "review_attempt_fingerprint": "a" * 64,
        "review_attempt_replay_key": SHA256(b"attempt"),
        "review_claim_id": str(uuid4()),
        "review_claim_fingerprint": CLAIM_FINGERPRINT,
        "preflight_id": str(uuid4()),
        "preflight_fingerprint": "b" * 64,
        "source_candidate_diff_message_id": str(source_candidate_diff_id),
        "source_candidate_diff_id": str(source_candidate_diff_id),
        "source_candidate_diff_fingerprint": CANDIDATE_DIFF_FINGERPRINT,
        "source_candidate_diff_sha256": source_candidate_diff_sha256,
        "source_candidate_manifest_id": str(uuid4()),
        "source_candidate_manifest_fingerprint": MANIFEST_FINGERPRINT,
        "source_executor_outcome_id": str(uuid4()),
        "source_package_id": str(uuid4()),
        "source_attempt_id": str(uuid4()),
        "authority": authority,
        "exact_task_id": str(task_id),
        "exact_run_id": str(uuid4()),
        "rework_attempt_index": 0,
        "rework_attempt_limit": 3,
        "requested_reviewer_executor": "codex",
        "review_prompt_sha256": PROMPT_SHA256,
        "review_prompt_bytes": 100,
        "review_scope_paths": ["src/example.py"],
        "review_output_schema_version": "p25-h-output.v1",
        "invocation_ordinal": 0,
        "adapter_result": adapter_result,
        "review_result_fingerprint": REVIEW_RESULT_FINGERPRINT,
        "review_semantic_fingerprint": review_semantic_fingerprint,
        "safe_error_code": None,
        "blocked_reasons": [],
        "recovery_required": False,
        "human_escalation_required": False,
        "review_outcome_id": str(review_outcome_id),
        "review_outcome_fingerprint": OUTCOME_FINGERPRINT,
    }

    verdict_text = f" verdict {verdict}" if verdict else ""
    summary = "validated_review_output" if outcome_status == "validated_output" else "reviewer_execution_raised"
    session.add(
        ProjectDirectorMessageTable(
            id=review_outcome_id, session_id=session_id, role="assistant",
            content=(
                f"P25 bounded rework review outcome persisted: "
                f"{review_outcome_id} attempt {action['review_attempt_id']} "
                f"status {outcome_status}{verdict_text} summary {summary}"
            ),
            sequence_no=seq_no,
            intent=P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT,
            source="system",
            source_detail=P25_BOUNDED_REWORK_REVIEW_OUTCOME_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False, risk_level="high",
            related_project_id=project_id, related_task_id=task_id,
        )
    )
    session.commit()
    return review_outcome_id


def _seed_p22_summary_message(
    session: Session,
    *,
    session_id: UUID,
    task_id: UUID,
    project_id: UUID,
    source_review_message_id: UUID,
    disposition_type: str = "AUTO_CONTINUE",
    route: str = "automatic_continuation",
    orchestration_status: str = "ready_for_future_transition",
    current_step: str = "freshness_ready",
    source_human_escalation_package_message_id: UUID | None = None,
    seq_no: int = 40,
) -> UUID:
    """Seed a P22 post-review automation message with configurable disposition/route/status."""
    summary_id = uuid4()
    now = datetime.now(timezone.utc).isoformat()

    transition_kind = "CONTINUE_GUARDRAIL" if disposition_type == "AUTO_CONTINUE" else "BOUNDED_REWORK_GUARDRAIL"
    transition_authority = "AUTOMATED_DISPOSITION"
    is_ready = orchestration_status == "ready_for_future_transition"

    # Build kwargs based on orchestration_status to satisfy the validator
    base_kwargs = dict(
        orchestration_status=orchestration_status,
        orchestration_id=uuid4(),
        route=route,
        current_step=current_step,
        source_review_message_id=source_review_message_id,
        disposition_type=disposition_type,
        replay_check_completed=True,
        created_at=datetime.now(timezone.utc),
    )

    if is_ready:
        handoff_kind = "automatic_continuation" if disposition_type == "AUTO_CONTINUE" else "bounded_automatic_rework"
        base_kwargs.update(
            handoff_kind=handoff_kind,
            transition_kind=transition_kind,
            transition_authority=transition_authority,
            source_disposition_message_id=uuid4(),
            source_consumption_preflight_message_id=uuid4(),
            source_consumption_message_id=uuid4(),
            source_handoff_message_id=uuid4(),
            source_freshness_message_id=uuid4(),
            evidence_fresh=True,
            gate_allows_protected_transition_guardrail=True,
        )
    elif orchestration_status == "waiting_for_human":
        base_kwargs.update(
            route="human_escalation",
            disposition_type="ESCALATE_TO_HUMAN",
            source_disposition_message_id=uuid4(),
            source_human_escalation_package_message_id=source_human_escalation_package_message_id or uuid4(),
            evidence_fresh=False,
            gate_allows_protected_transition_guardrail=False,
            waiting_for_human=True,
            human_escalation_package_created=True,
        )
    else:
        # blocked - simplest
        base_kwargs.update(
            blocked_reasons=["test_blocked"],
            evidence_fresh=False,
            gate_allows_protected_transition_guardrail=False,
        )

    result = ProjectDirectorPostReviewAutomationResult(**base_kwargs)
    action = result.model_dump(mode="json")
    action.update({
        "type": P22_POST_REVIEW_AUTOMATION_ACTION_TYPE,
        "schema_version": P22_POST_REVIEW_AUTOMATION_SCHEMA_VERSION,
        "session_id": str(session_id),
        "source_task_id": str(task_id),
    })

    session.add(
        ProjectDirectorMessageTable(
            id=summary_id, session_id=session_id, role="assistant",
            content="Post review automation orchestrated.",
            sequence_no=seq_no,
            intent="post_review_automation_orchestration",
            source="system",
            source_detail=P22_POST_REVIEW_AUTOMATION_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False, risk_level="high",
            related_project_id=project_id, related_task_id=task_id,
        )
    )
    session.commit()
    return summary_id


def _seed_convergence_decision_message(
    session: Session,
    *,
    session_id: UUID,
    task_id: UUID,
    project_id: UUID,
    decision_id: UUID | None = None,
    decision_type: str = "CONVERGED",
    decision_reason: str = "review_converged",
    source_candidate_diff_message_id: UUID | None = None,
    source_review_outcome_message_id: UUID | None = None,
    source_p22_summary_message_id: UUID | None = None,
    seq_no: int = 50,
) -> UUID:
    """Seed a P25-I-B convergence decision message."""
    decision_id = decision_id or uuid4()
    source_candidate_diff_message_id = source_candidate_diff_message_id or uuid4()
    source_review_outcome_message_id = source_review_outcome_message_id or uuid4()
    source_p22_summary_message_id = source_p22_summary_message_id or uuid4()

    now = datetime.now(timezone.utc).isoformat()
    authority = {
        "session_id": str(session_id),
        "project_id": str(project_id),
    }
    action = {
        "type": P25_BOUNDED_REWORK_CONVERGENCE_DECISION_ACTION_TYPE,
        "schema_version": P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SCHEMA_VERSION,
        "decision_id": str(decision_id),
        "decision_fingerprint": CONVERGENCE_FINGERPRINT,
        "decision_replay_key": SHA256(str(decision_id).encode()),
        "created_at": now,
        "decision_type": decision_type,
        "decision_reason": decision_reason,
        "source_candidate_diff_message_id": str(source_candidate_diff_message_id),
        "source_candidate_diff_id": str(source_candidate_diff_message_id),
        "source_candidate_diff_fingerprint": CANDIDATE_DIFF_FINGERPRINT,
        "source_review_outcome_message_id": str(source_review_outcome_message_id),
        "source_review_outcome_id": str(source_review_outcome_message_id),
        "source_review_outcome_fingerprint": OUTCOME_FINGERPRINT,
        "source_p22_summary_message_id": str(source_p22_summary_message_id),
        "source_package_id": str(uuid4()),
        "authority": authority,
        "exact_task_id": str(task_id),
        "exact_run_id": str(uuid4()),
        "rework_attempt_index": 0,
        "rework_attempt_limit": 3,
        "review_result_fingerprint": REVIEW_RESULT_FINGERPRINT,
        "review_semantic_fingerprint": REVIEW_SEMANTIC_FINGERPRINT,
        "canonical_blocking_findings_fingerprint": None,
        "previous_diff_sha256": PREVIOUS_DIFF_SHA256,
        "new_diff_sha256": NEW_DIFF_SHA256,
        "review_verdict": "no_blocking_findings",
        "review_risk_level": "low",
    }
    session.add(
        ProjectDirectorMessageTable(
            id=decision_id, session_id=session_id, role="assistant",
            content=f"P25 convergence decision: {decision_type} ({decision_reason})",
            sequence_no=seq_no,
            intent="bounded_rework_convergence_decision",
            source="system",
            source_detail=P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False, risk_level="high",
            related_project_id=project_id, related_task_id=task_id,
        )
    )
    session.commit()
    return decision_id


def _seed_p25_terminal_escalation_message(
    session: Session,
    *,
    session_id: UUID,
    task_id: UUID,
    project_id: UUID,
    terminal_id: UUID | None = None,
    source_convergence_decision_id: UUID | None = None,
    escalation_reason: str = "attempt_limit_exhausted",
    seq_no: int = 60,
) -> UUID:
    """Seed a P25-I-C2 terminal escalation package message."""
    terminal_id = terminal_id or uuid4()
    source_convergence_decision_id = source_convergence_decision_id or uuid4()

    now = datetime.now(timezone.utc).isoformat()
    authority = {
        "session_id": str(session_id),
        "project_id": str(project_id),
    }
    action = {
        "type": P25_BOUNDED_REWORK_TERMINAL_ESCALATION_ACTION_TYPE,
        "schema_version": P25_BOUNDED_REWORK_TERMINAL_ESCALATION_SCHEMA_VERSION,
        "package_id": str(terminal_id),
        "package_fingerprint": TERMINAL_FINGERPRINT,
        "package_replay_key": SHA256(str(terminal_id).encode()),
        "created_at": now,
        "escalation_reason": escalation_reason,
        "source_convergence_decision_message_id": str(source_convergence_decision_id),
        "source_convergence_decision_id": str(source_convergence_decision_id),
        "source_convergence_decision_fingerprint": CONVERGENCE_FINGERPRINT,
        "source_package_id": str(uuid4()),
        "source_package_fingerprint": PACKAGE_FINGERPRINT,
        "authority": authority,
        "exact_task_id": str(task_id),
        "exact_run_id": str(uuid4()),
        "rework_attempt_index": 0,
        "rework_attempt_limit": 3,
        "review_result_fingerprint": REVIEW_RESULT_FINGERPRINT,
        "review_semantic_fingerprint": REVIEW_SEMANTIC_FINGERPRINT,
        "canonical_blocking_findings_fingerprint": None,
        "findings": [],
        "escalation_summary": f"Terminal escalation: {escalation_reason}",
        "automatic_processing_terminal": True,
        "ai_project_director_total_loop": "Partial",
    }
    session.add(
        ProjectDirectorMessageTable(
            id=terminal_id, session_id=session_id, role="assistant",
            content=f"P25 terminal escalation package: {escalation_reason}",
            sequence_no=seq_no,
            intent="bounded_rework_terminal_escalation_package",
            source="system",
            source_detail=P25_BOUNDED_REWORK_TERMINAL_ESCALATION_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False, risk_level="high",
            related_project_id=project_id, related_task_id=task_id,
        )
    )
    session.commit()
    return terminal_id


# ── Fakes ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _FakeCandidateDiffLineage:
    """Minimal data needed by the convergence service from candidate diff revalidation."""
    package: Any | None = None
    reservation: Any | None = None
    invocation_claim: Any | None = None
    invocation_outcome: Any | None = None
    outcome_message: ProjectDirectorMessage | None = None
    candidate_manifest: Any | None = None
    candidate_manifest_message: ProjectDirectorMessage | None = None
    candidate_diff: Any | None = None
    candidate_diff_message: ProjectDirectorMessage | None = None
    blocked_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FakeRevalidatedCandidateDiff:
    """Fake result for ProjectDirectorBoundedReworkCandidateDiffService revalidation."""
    package: Any | None = None
    reservation: Any | None = None
    invocation_claim: Any | None = None
    invocation_outcome: Any | None = None
    outcome_message: ProjectDirectorMessage | None = None
    candidate_manifest: Any | None = None
    candidate_manifest_message: ProjectDirectorMessage | None = None
    candidate_diff: Any | None = None
    candidate_diff_message: ProjectDirectorMessage | None = None
    blocked_reasons: tuple[str, ...] = ()


class FakeCandidateDiffService:
    """Fake ProjectDirectorBoundedReworkCandidateDiffService for convergence/terminal tests.

    Returns a configurable result from revalidation methods.
    """

    def __init__(
        self,
        *,
        message_repository: ProjectDirectorMessageRepository | None = None,
        blocked_reasons: tuple[str, ...] = (),
        candidate_diff: Any | None = None,
        candidate_diff_message: ProjectDirectorMessage | None = None,
        package: Any | None = None,
        invocation_outcome: Any | None = None,
    ):
        self._message_repository = message_repository or type(
            "FakeMsgRepo", (), {"_session": None, "sqlite_immediate_transaction": lambda self: _noop_context()}
        )()
        self._blocked_reasons = blocked_reasons
        self._candidate_diff = candidate_diff
        self._candidate_diff_message = candidate_diff_message
        self._package = package
        self._invocation_outcome = invocation_outcome

    def revalidate_persisted_candidate_diff_for_convergence(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_candidate_diff_message_id: UUID,
    ) -> FakeRevalidatedCandidateDiff:
        if self._blocked_reasons:
            return FakeRevalidatedCandidateDiff(blocked_reasons=self._blocked_reasons)
        return FakeRevalidatedCandidateDiff(
            package=self._package,
            candidate_diff=self._candidate_diff,
            candidate_diff_message=self._candidate_diff_message,
            invocation_outcome=self._invocation_outcome,
            blocked_reasons=(),
        )

    def revalidate_persisted_candidate_diff_for_convergence_persistence(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_candidate_diff_message_id: UUID,
    ) -> FakeRevalidatedCandidateDiff:
        return self.revalidate_persisted_candidate_diff_for_convergence(
            session_id=session_id,
            source_task_id=source_task_id,
            source_candidate_diff_message_id=source_candidate_diff_message_id,
        )


@dataclass(frozen=True, slots=True)
class FakeRevalidatedReviewOutcome:
    """Fake result for ProjectDirectorBoundedReworkReviewExecutionService revalidation."""
    status: str = "validated_output"
    review_attempt: Any | None = None
    review_attempt_message: ProjectDirectorMessage | None = None
    review_outcome: Any | None = None
    review_outcome_message: ProjectDirectorMessage | None = None
    preflight: Any | None = None
    review_claim: Any | None = None
    candidate_diff: Any | None = None
    candidate_manifest: Any | None = None
    package: Any | None = None
    blocked_reasons: tuple[str, ...] = ()


class FakeReviewExecutionService:
    """Fake ProjectDirectorBoundedReworkReviewExecutionService for convergence/terminal tests."""

    def __init__(
        self,
        *,
        message_repository: ProjectDirectorMessageRepository | None = None,
        blocked_reasons: tuple[str, ...] = (),
        review_outcome: Any | None = None,
        review_outcome_message: ProjectDirectorMessage | None = None,
    ):
        self._message_repository = message_repository or type(
            "FakeMsgRepo", (), {"_session": None, "sqlite_immediate_transaction": lambda self: _noop_context()}
        )()
        self._blocked_reasons = blocked_reasons
        self._review_outcome = review_outcome
        self._review_outcome_message = review_outcome_message

    def revalidate_review_outcome_for_candidate_diff(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_candidate_diff_message_id: UUID,
    ) -> FakeRevalidatedReviewOutcome:
        if self._blocked_reasons:
            return FakeRevalidatedReviewOutcome(
                status="blocked",
                blocked_reasons=self._blocked_reasons,
            )
        return FakeRevalidatedReviewOutcome(
            status="validated_output",
            review_outcome=self._review_outcome,
            review_outcome_message=self._review_outcome_message,
            blocked_reasons=(),
        )


@dataclass(frozen=True, slots=True)
class FakeRevalidatedPostReviewSummary:
    """Fake result for ProjectDirectorPostReviewAutomationService revalidation."""
    summary_exists: bool = False
    result: ProjectDirectorPostReviewAutomationResult | None = None
    message: ProjectDirectorMessage | None = None
    blocked_reasons: tuple[str, ...] = ()


class FakePostReviewAutomationService:
    """Fake ProjectDirectorPostReviewAutomationService for convergence/terminal tests."""

    def __init__(
        self,
        *,
        message_repository: ProjectDirectorMessageRepository | None = None,
        summary_exists: bool = True,
        result: ProjectDirectorPostReviewAutomationResult | None = None,
        message: ProjectDirectorMessage | None = None,
        blocked_reasons: tuple[str, ...] = (),
    ):
        self._message_repository = message_repository or type(
            "FakeMsgRepo", (), {"_session": None, "sqlite_immediate_transaction": lambda self: _noop_context()}
        )()
        self._summary_exists = summary_exists
        self._result = result
        self._message = message
        self._blocked_reasons = blocked_reasons

    def revalidate_existing_post_review_summary(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_review_message_id: UUID,
    ) -> FakeRevalidatedPostReviewSummary:
        if self._blocked_reasons:
            return FakeRevalidatedPostReviewSummary(
                summary_exists=False,
                blocked_reasons=self._blocked_reasons,
            )
        return FakeRevalidatedPostReviewSummary(
            summary_exists=self._summary_exists,
            result=self._result,
            message=self._message,
            blocked_reasons=(),
        )


# ── Canonical Findings Fingerprint (duplicated to avoid circular import) ──


def compute_canonical_blocking_findings_fingerprint(findings):
    """Hash the order-independent medium/high blocking-finding projection.

    This is a standalone copy of the production function to avoid circular imports
    in the test module. The production implementation is in
    app.services.project_director_bounded_rework_convergence_service.
    """
    finding_hashes = []
    for finding in findings:
        severity = finding.get("severity") if isinstance(finding, dict) else getattr(finding, "severity", None)
        if severity not in {"medium", "high"}:
            continue
        title = finding.get("title") if isinstance(finding, dict) else getattr(finding, "title", None)
        evidence_paths = finding.get("evidence_paths") if isinstance(finding, dict) else getattr(finding, "evidence_paths", None)
        recommended_action = finding.get("recommended_action") if isinstance(finding, dict) else getattr(finding, "recommended_action", None)
        if (
            not isinstance(title, str) or not title.strip()
            or not isinstance(recommended_action, str) or not recommended_action.strip()
            or not isinstance(evidence_paths, (list, tuple)) or not evidence_paths
            or any(not isinstance(p, str) or not p for p in evidence_paths)
        ):
            raise ValueError("blocking finding projection is invalid")
        projection = {
            "severity": severity,
            "title": title,
            "evidence_paths": sorted(evidence_paths),
            "recommended_action": recommended_action,
        }
        finding_hashes.append(SHA256(json.dumps(projection, sort_keys=True).encode()))
    return SHA256(json.dumps({"schema_version": "p25-i-b-canonical-blocking-findings.v1", "finding_hashes": sorted(set(finding_hashes))}, sort_keys=True).encode())


# ── Context Manager Helper ────────────────────────────────────────────


@contextmanager
def _noop_context():
    yield None


# ── Service Constructors ──────────────────────────────────────────────


def make_convergence_service(
    session_local,
    *,
    msg_repo: ProjectDirectorMessageRepository | None = None,
    candidate_diff_svc=None,
    review_execution_svc=None,
    post_review_automation_svc=None,
):
    """Create a real ProjectDirectorBoundedReworkConvergenceService with real repos.

    Fake sub-services are used by default for the candidate diff, review execution,
    and post review automation revalidation. Pass real services to override.

    Returns (service, session, msg_repo).
    """
    from app.services.project_director_bounded_rework_convergence_service import (
        ProjectDirectorBoundedReworkConvergenceService,
    )

    if msg_repo is None:
        session, msg_repo, sess_repo, task_repo = make_repos(session_local)
    else:
        session = msg_repo._session
        sess_repo = ProjectDirectorSessionRepository(session)
        task_repo = TaskRepository(session)

    if candidate_diff_svc is None:
        candidate_diff_svc = FakeCandidateDiffService(message_repository=msg_repo)
    if review_execution_svc is None:
        review_execution_svc = FakeReviewExecutionService(message_repository=msg_repo)
    if post_review_automation_svc is None:
        post_review_automation_svc = FakePostReviewAutomationService(
            message_repository=msg_repo,
        )

    svc = ProjectDirectorBoundedReworkConvergenceService(
        message_repository=msg_repo,
        candidate_diff_service=candidate_diff_svc,
        review_execution_service=review_execution_svc,
        post_review_automation_service=post_review_automation_svc,
    )
    return svc, session, msg_repo


def make_terminal_escalation_service(
    session_local,
    *,
    msg_repo: ProjectDirectorMessageRepository | None = None,
    convergence_svc=None,
):
    """Create a real ProjectDirectorBoundedReworkTerminalEscalationService.

    A real convergence service is constructed internally unless provided.
    Returns (service, session, msg_repo).
    """
    from app.services.project_director_bounded_rework_convergence_service import (
        ProjectDirectorBoundedReworkConvergenceService,
    )
    from app.services.project_director_bounded_rework_terminal_escalation_service import (
        ProjectDirectorBoundedReworkTerminalEscalationService,
    )

    if msg_repo is None:
        session, msg_repo, sess_repo, task_repo = make_repos(session_local)
    else:
        session = msg_repo._session

    if convergence_svc is None:
        candidate_diff_svc = FakeCandidateDiffService(message_repository=msg_repo)
        review_execution_svc = FakeReviewExecutionService(message_repository=msg_repo)
        post_review_automation_svc = FakePostReviewAutomationService(
            message_repository=msg_repo,
        )
        convergence_svc = ProjectDirectorBoundedReworkConvergenceService(
            message_repository=msg_repo,
            candidate_diff_service=candidate_diff_svc,
            review_execution_service=review_execution_svc,
            post_review_automation_service=post_review_automation_svc,
        )

    svc = ProjectDirectorBoundedReworkTerminalEscalationService(
        message_repository=msg_repo,
        convergence_service=convergence_svc,
    )
    return svc, session, msg_repo
