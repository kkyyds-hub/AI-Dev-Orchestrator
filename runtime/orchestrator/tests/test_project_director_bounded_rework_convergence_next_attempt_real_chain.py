"""P25-I real attempt-zero next-attempt eligibility regression coverage."""

from __future__ import annotations

import hashlib
import json
import subprocess

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.db_tables import ProjectDirectorMessageTable, RunTable, TaskTable
from app.domain.project_role import ProjectRoleCode
from app.domain.task import Task
from app.repositories.task_repository import TaskRepository
from app.services.project_director_bounded_rework_convergence_service import (
    P25_BOUNDED_REWORK_CONVERGENCE_DECISION_INTENT,
)
from app.services.project_director_bounded_rework_attempt_reservation_service import (
    P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_INTENT,
)
from app.services.project_director_bounded_rework_candidate_diff_service import (
    P25_BOUNDED_REWORK_CANDIDATE_DIFF_INTENT,
    P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_INTENT,
)
from app.services.project_director_bounded_rework_invocation_claim_service import (
    P25_BOUNDED_REWORK_INVOCATION_CLAIM_INTENT,
)
from app.services.project_director_bounded_rework_invocation_outcome_service import (
    P25_BOUNDED_REWORK_INVOCATION_OUTCOME_INTENT,
)
from app.services.project_director_bounded_rework_package_preparation_service import (
    P25_BOUNDED_REWORK_PACKAGE_INTENT,
)
from app.services.project_director_bounded_rework_review_execution_service import (
    P25_BOUNDED_REWORK_REVIEW_ATTEMPT_INTENT,
    P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT,
)
from app.services.project_director_bounded_rework_review_reentry_preflight_service import (
    P25_BOUNDED_REWORK_REVIEW_CLAIM_INTENT,
    P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_INTENT,
)
from tests.p25_convergence_next_attempt_real_chain_test_support import (
    build_fresh_next_attempt_convergence_services,
    build_real_p25_attempt_zero_next_attempt_convergence_context,
)


def _decision_messages(context):
    session = context.session
    caller_had_transaction = session.in_transaction()
    try:
        messages, has_more = context.message_repository.list_by_session_id(
            session_id=context.session_id,
            limit=200,
        )
        assert has_more is False
        return tuple(
            message
            for message in messages
            if message.intent == P25_BOUNDED_REWORK_CONVERGENCE_DECISION_INTENT
        )
    finally:
        if not caller_had_transaction and session.in_transaction():
            session.rollback()


def _all_messages(context):
    session = context.session
    caller_had_transaction = session.in_transaction()
    try:
        messages, has_more = context.message_repository.list_by_session_id(
            session_id=context.session_id,
            limit=200,
        )
        assert has_more is False
        return tuple(messages)
    finally:
        if not caller_had_transaction and session.in_transaction():
            session.rollback()


def _decide(context, *, service=None, task_id=None):
    return (service or context.convergence_service).decide_bounded_rework_convergence(
        session_id=context.session_id,
        source_task_id=task_id or context.task_id,
        source_candidate_diff_message_id=context.candidate_diff_message_id,
    )


def _business_entries(context):
    workspace = context.review_execution_context.environment["workspace_path"]
    return tuple(
        sorted(
            (
                path.relative_to(workspace).as_posix(),
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
            for path in workspace.rglob("*")
            if path.is_file() and ".ai-project-director" not in path.parts
        )
    )


def _git_control_fingerprint(repository):
    digest = hashlib.sha256()
    for path in sorted((repository / ".git").rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(repository).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _task_run_counts(context):
    session = context.session
    caller_had_transaction = session.in_transaction()
    try:
        return (
            session.scalar(select(func.count()).select_from(TaskTable)),
            session.scalar(select(func.count()).select_from(RunTable)),
        )
    finally:
        if not caller_had_transaction and session.in_transaction():
            session.rollback()


def test_real_attempt_zero_persists_next_attempt_eligible_decision(tmp_path):
    context = build_real_p25_attempt_zero_next_attempt_convergence_context(tmp_path)
    try:
        result = _decide(context)

        assert result.status == "decision_persisted", result.blocked_reasons
        assert result.decision is not None
        assert result.decision_message is not None
        assert result.decision.decision_type == "NEXT_ATTEMPT_ELIGIBLE"
        assert result.decision.decision_reason == "changed_blocking_findings"
        assert result.decision.current_rework_attempt_index == 0
        assert result.decision.rework_attempt_limit == 3
        assert result.decision.next_rework_attempt_index == 1
        assert result.decision.converged is False
        assert result.decision.next_attempt_eligible is True
        assert result.decision.human_escalation_required is False
        assert result.decision.automatic_processing_terminal is False
    finally:
        context.close()


def test_next_attempt_decision_binds_complete_real_evidence(tmp_path):
    context = build_real_p25_attempt_zero_next_attempt_convergence_context(tmp_path)
    try:
        result = _decide(context)
        assert result.decision is not None
        decision = result.decision
        preflight_context = context.review_execution_context.review_preflight_context
        candidate_context = preflight_context.candidate_context
        package = candidate_context.outcome_context.claim_context.package_result.package
        reservation = candidate_context.outcome_context.claim_context.reservation_result.reservation

        assert decision.source_package_id == package.package_id
        assert decision.source_attempt_id == reservation.reservation_id
        assert decision.source_executor_outcome_id == (
            preflight_context.outcome_result.outcome.outcome_id
        )
        assert decision.source_candidate_diff_message_id == context.candidate_diff_message_id
        assert decision.source_review_outcome_message_id == context.h_b_result.review_outcome_message.id
        assert decision.source_p22_summary_message_id == context.h_c_result.p22_summary_message.id
        assert decision.candidate_diff_status == "generated"
        assert decision.diff_changed is True
        assert decision.review_semantics_changed is True
        assert decision.blocking_findings_changed is True
    finally:
        context.close()


def test_current_review_diff_and_findings_are_distinct_from_root(tmp_path):
    context = build_real_p25_attempt_zero_next_attempt_convergence_context(tmp_path)
    try:
        result = _decide(context)
        assert result.decision is not None
        decision = result.decision
        preflight = context.review_execution_context.h_a_result.preflight
        package = (
            context.review_execution_context.review_preflight_context.candidate_context
            .outcome_context.claim_context.package_result.package
        )

        assert decision.source_review_outcome_message_id != package.authority.source_review_message_id
        assert decision.current_review_semantic_fingerprint != (
            package.authority.source_review_semantic_fingerprint
        )
        assert decision.source_candidate_diff_message_id != preflight.old_review_source_diff_message_id
        assert decision.current_diff_sha256 != decision.previous_diff_sha256
        assert decision.current_blocking_findings_fingerprint != (
            decision.previous_blocking_findings_fingerprint
        )
    finally:
        context.close()


def test_next_attempt_decision_is_audit_only(tmp_path):
    context = build_real_p25_attempt_zero_next_attempt_convergence_context(tmp_path)
    try:
        environment = context.review_execution_context.environment
        workspace = environment["workspace_path"]
        manifest = workspace / ".ai-project-director/workspace-manifest.json"
        repository = environment["repository_root"]
        before = (
            _business_entries(context),
            (manifest.read_bytes(), manifest.stat().st_ino, manifest.stat().st_mtime_ns),
            subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            subprocess.run(["git", "status", "--porcelain"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            _git_control_fingerprint(repository),
            subprocess.run(["git", "branch", "--show-current"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            subprocess.run(["git", "tag", "--points-at", "HEAD"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            _task_run_counts(context),
        )

        result = _decide(context)

        assert result.status == "decision_persisted", result.blocked_reasons
        assert result.decision_message is not None
        assert set(result.decision_message.forbidden_actions_detected) == {
            "next_p23_intent_created=false", "next_p23_consumption_created=false",
            "next_package_created=false", "next_reservation_created=false",
            "next_claim_created=false", "executor_called=false", "reviewer_called=false",
            "provider_called=false", "task_created=false", "run_created=false",
            "worker_started=false", "main_project_file_written=false",
            "sandbox_file_written=false", "patch_applied=false", "git_write_performed=false",
            "product_runtime_git_write_allowed=false",
        }
        assert before == (
            _business_entries(context),
            (manifest.read_bytes(), manifest.stat().st_ino, manifest.stat().st_mtime_ns),
            subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            subprocess.run(["git", "status", "--porcelain"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            _git_control_fingerprint(repository),
            subprocess.run(["git", "branch", "--show-current"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            subprocess.run(["git", "tag", "--points-at", "HEAD"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            _task_run_counts(context),
        )
    finally:
        context.close()


def test_same_session_next_attempt_decision_replays_exactly(tmp_path):
    context = build_real_p25_attempt_zero_next_attempt_convergence_context(tmp_path)
    try:
        first = _decide(context)
        replay = _decide(context)

        assert first.status == "decision_persisted", first.blocked_reasons
        assert replay.status == "decision_replayed", replay.blocked_reasons
        assert replay.decision == first.decision
        assert replay.decision_message == first.decision_message
        assert len(_decision_messages(context)) == 1
        assert context.executor.call_count == 1
        assert context.transport.execute_calls == 1
    finally:
        context.close()


def test_fresh_session_next_attempt_decision_replays_without_recall(tmp_path):
    context = build_real_p25_attempt_zero_next_attempt_convergence_context(tmp_path)
    fresh = None
    try:
        first = _decide(context)
        context.session.close()
        fresh = build_fresh_next_attempt_convergence_services(context)
        replay = _decide(context, service=fresh.convergence_service)

        assert first.status == "decision_persisted", first.blocked_reasons
        assert replay.status == "decision_replayed", replay.blocked_reasons
        assert replay.decision == first.decision
        assert replay.decision_message == first.decision_message
        assert context.executor.call_count == 1
        assert context.transport.execute_calls == 1
        assert fresh.session.in_transaction() is False
    finally:
        if fresh is not None:
            fresh.close()
        context.close()


def test_next_attempt_decision_revalidates_for_p22_summary(tmp_path):
    context = build_real_p25_attempt_zero_next_attempt_convergence_context(tmp_path)
    try:
        first = _decide(context)
        revalidated = (
            context.convergence_service.revalidate_next_attempt_decision_for_p22_summary(
                session_id=context.session_id,
                source_task_id=context.task_id,
                source_p22_summary_message_id=context.h_c_result.p22_summary_message.id,
            )
        )

        assert first.status == "decision_persisted", first.blocked_reasons
        assert revalidated.blocked_reasons == ()
        assert revalidated.decision == first.decision
        assert revalidated.decision_message == first.decision_message
        assert revalidated.decision.decision_type == "NEXT_ATTEMPT_ELIGIBLE"
        assert revalidated.decision.decision_reason == "changed_blocking_findings"
        assert revalidated.decision.next_rework_attempt_index == 1
        assert revalidated.decision.next_attempt_eligible is True
        assert revalidated.decision.automatic_processing_terminal is False
    finally:
        context.close()


def test_next_attempt_decision_preserves_caller_owned_transaction(tmp_path):
    context = build_real_p25_attempt_zero_next_attempt_convergence_context(tmp_path)
    try:
        assert context.session.in_transaction() is False
        context.session.begin()
        task = context.session.get(TaskTable, context.task_id)
        assert task is not None
        task.input_summary = "caller-owned P25-I next-attempt pending write"
        context.session.flush()

        result = _decide(context)

        assert result.status == "blocked"
        assert result.blocked_reasons == ("persistence_failed",)
        assert context.session.in_transaction() is True
        assert context.session.execute(
            select(TaskTable.input_summary).where(TaskTable.id == context.task_id)
        ).scalar_one() == "caller-owned P25-I next-attempt pending write"
        assert _decision_messages(context) == ()
        assert context.executor.call_count == 1
        assert context.transport.execute_calls == 1
    finally:
        if context.session.in_transaction():
            context.session.rollback()
        context.close()


def test_next_attempt_decision_persistence_failure_recovers_atomically(tmp_path, monkeypatch):
    context = build_real_p25_attempt_zero_next_attempt_convergence_context(tmp_path)
    try:
        original_create = context.message_repository.create

        def fail_convergence_decision(message):
            if message.intent == P25_BOUNDED_REWORK_CONVERGENCE_DECISION_INTENT:
                raise SQLAlchemyError("injected convergence persistence failure")
            return original_create(message)

        monkeypatch.setattr(context.message_repository, "create", fail_convergence_decision)
        failed = _decide(context)
        monkeypatch.setattr(context.message_repository, "create", original_create)
        recovered = _decide(context)

        assert failed.status == "recovery_required"
        assert failed.blocked_reasons == ("persistence_failed",)
        assert recovered.status == "decision_persisted", recovered.blocked_reasons
        assert _decision_messages(context) == (recovered.decision_message,)
        assert context.executor.call_count == 1
        assert context.transport.execute_calls == 1
    finally:
        context.close()


def test_workspace_drift_blocks_next_attempt_decision(tmp_path):
    context = build_real_p25_attempt_zero_next_attempt_convergence_context(tmp_path)
    try:
        workspace = context.review_execution_context.environment["workspace_path"]
        (workspace / "src/example.py").write_text("workspace drift\n", encoding="utf-8")

        result = _decide(context)

        assert result.status == "blocked"
        assert result.decision is None
        assert _decision_messages(context) == ()
    finally:
        context.close()


def test_second_legal_task_cannot_decide_first_task_candidate_diff(tmp_path):
    context = build_real_p25_attempt_zero_next_attempt_convergence_context(tmp_path)
    try:
        other_task = TaskRepository(context.session).create(
            Task(
                project_id=context.review_execution_context.review_preflight_context.project_id,
                title="Independent task for P25-I next-attempt isolation",
                input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
                acceptance_criteria=["safe_dry_run_task=true"],
                owner_role_code=ProjectRoleCode.ARCHITECT,
            )
        )
        if context.session.in_transaction():
            context.session.rollback()

        result = _decide(context, task_id=other_task.id)

        assert result.status == "blocked"
        assert result.decision is None
        assert _decision_messages(context) == ()
    finally:
        context.close()


def test_tampered_next_attempt_decision_fails_closed_without_second_message(tmp_path):
    context = build_real_p25_attempt_zero_next_attempt_convergence_context(tmp_path)
    try:
        first = _decide(context)
        assert first.decision_message is not None
        row = context.session.get(ProjectDirectorMessageTable, first.decision_message.id)
        assert row is not None
        actions = json.loads(row.suggested_actions_json)
        actions[0]["decision_fingerprint"] = "0" * 64
        row.suggested_actions_json = json.dumps(actions)
        context.session.commit()

        result = _decide(context)

        assert result.status == "blocked"
        assert result.blocked_reasons in {
            ("history_invalid",),
            ("convergence_decision_conflict",),
        }
        assert len(_decision_messages(context)) == 1
    finally:
        context.close()


def test_next_attempt_decision_stops_after_one_audit_message(tmp_path):
    context = build_real_p25_attempt_zero_next_attempt_convergence_context(tmp_path)
    try:
        before_messages = _all_messages(context)
        before_counts = _task_run_counts(context)

        result = _decide(context)

        assert result.status == "decision_persisted", result.blocked_reasons
        assert result.decision_message is not None
        after_messages = _all_messages(context)
        assert after_messages[:-1] == before_messages
        assert after_messages[-1] == result.decision_message
        assert _task_run_counts(context) == before_counts
        expected_attempt_zero_intents = {
            P25_BOUNDED_REWORK_PACKAGE_INTENT,
            P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_INTENT,
            P25_BOUNDED_REWORK_INVOCATION_CLAIM_INTENT,
            P25_BOUNDED_REWORK_INVOCATION_OUTCOME_INTENT,
            P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_INTENT,
            P25_BOUNDED_REWORK_CANDIDATE_DIFF_INTENT,
            P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_INTENT,
            P25_BOUNDED_REWORK_REVIEW_CLAIM_INTENT,
            P25_BOUNDED_REWORK_REVIEW_ATTEMPT_INTENT,
            P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT,
            P25_BOUNDED_REWORK_CONVERGENCE_DECISION_INTENT,
        }
        for intent in expected_attempt_zero_intents:
            assert sum(message.intent == intent for message in after_messages) == 1
        assert not any(
            message.intent == "bounded_rework_terminal_escalation"
            for message in after_messages
        )
    finally:
        context.close()
