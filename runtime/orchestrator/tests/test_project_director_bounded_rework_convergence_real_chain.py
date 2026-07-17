"""P25-I real attempt-zero convergence-decision regression coverage."""

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
    ProjectDirectorBoundedReworkConvergenceService,
)
from tests.p25_convergence_real_chain_test_support import (
    build_fresh_convergence_services,
    build_real_p25_attempt_zero_convergence_context,
)
from tests.p25_post_review_real_chain_test_support import _build_post_review_services
from tests.p25_review_execution_real_chain_test_support import (
    build_real_p25_attempt_zero_review_execution_context,
)


def _candidate_diff_message_id(context):
    return (
        context.post_review_context.review_execution_context.review_preflight_context
        .candidate_diff_result.diff_message.id
    )


def _decision_messages(context):
    session = context.session
    caller_had_transaction = session.in_transaction()
    try:
        messages, has_more = context.post_review_context.message_repository.list_by_session_id(
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


def _decide(context, *, service=None, task_id=None):
    return (service or context.convergence_service).decide_bounded_rework_convergence(
        session_id=context.session_id,
        source_task_id=task_id or context.task_id,
        source_candidate_diff_message_id=_candidate_diff_message_id(context),
    )


def _business_entries(context):
    workspace = (
        context.post_review_context.review_execution_context.review_preflight_context
        .environment["workspace_path"]
    )
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


def test_real_attempt_zero_persists_converged_decision(tmp_path):
    context = build_real_p25_attempt_zero_convergence_context(tmp_path)
    try:
        result = _decide(context)

        assert result.status == "decision_persisted", result.blocked_reasons
        assert result.decision is not None
        assert result.decision_message is not None
        assert result.decision.decision_type == "CONVERGED"
        assert result.decision.decision_reason == "review_converged"
        candidate_context = (
            context.post_review_context.review_execution_context.review_preflight_context
            .candidate_context
        )
        assert result.decision.source_package_id == (
            candidate_context.outcome_context.claim_context.package_result.package.package_id
        )
        assert result.decision.source_attempt_id == (
            candidate_context.outcome_context.claim_context.reservation_result.reservation.reservation_id
        )
        assert result.decision.source_executor_outcome_id == (
            context.post_review_context.review_execution_context.review_preflight_context
            .outcome_result.outcome.outcome_id
        )
        assert result.decision.source_candidate_diff_message_id == _candidate_diff_message_id(
            context
        )
        assert result.decision.source_review_outcome_message_id == (
            context.post_review_context.h_b_result.review_outcome_message.id
        )
        assert result.decision.source_p22_summary_message_id == (
            context.h_c_result.p22_summary_message.id
        )
        assert result.decision.current_rework_attempt_index == 0
        assert result.decision.rework_attempt_limit == 3
        assert result.decision.next_rework_attempt_index is None
        assert result.decision.candidate_diff_status == "generated"
        assert result.decision.diff_changed is True
        assert result.decision.converged is True
        assert result.decision.next_attempt_eligible is False
        assert result.decision.human_escalation_required is False
        assert result.decision.automatic_processing_terminal is True
    finally:
        context.close()


def test_convergence_uses_current_h_b_review_and_p25_g_diff(tmp_path):
    context = build_real_p25_attempt_zero_convergence_context(tmp_path)
    try:
        result = _decide(context)
        assert result.decision is not None
        decision = result.decision
        h_b_outcome = context.post_review_context.h_b_result.review_outcome
        h_b_message = context.post_review_context.h_b_result.review_outcome_message
        preflight = context.post_review_context.review_execution_context.h_a_result.preflight
        root_authority = (
            context.post_review_context.review_execution_context.review_preflight_context
            .candidate_context.outcome_context.claim_context.package_result.package.authority
        )

        assert decision.source_review_outcome_message_id == h_b_message.id
        assert decision.source_review_result_fingerprint == h_b_outcome.review_result_fingerprint
        assert decision.current_review_semantic_fingerprint == h_b_outcome.review_semantic_fingerprint
        assert decision.source_candidate_diff_message_id == _candidate_diff_message_id(context)
        assert decision.source_review_outcome_message_id != root_authority.source_review_message_id
        assert decision.source_review_result_fingerprint != root_authority.source_review_fingerprint
        assert decision.current_diff_sha256 != preflight.old_review_source_diff_sha256
        assert decision.previous_review_semantic_fingerprint == (
            root_authority.source_review_semantic_fingerprint
        )
    finally:
        context.close()


def test_convergence_decision_is_audit_only(tmp_path):
    context = build_real_p25_attempt_zero_convergence_context(tmp_path)
    try:
        environment = (
            context.post_review_context.review_execution_context.review_preflight_context
            .environment
        )
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


def test_same_session_convergence_replays_exactly(tmp_path):
    context = build_real_p25_attempt_zero_convergence_context(tmp_path)
    try:
        first = _decide(context)
        replay = _decide(context)

        assert first.status == "decision_persisted", first.blocked_reasons
        assert replay.status == "decision_replayed", replay.blocked_reasons
        assert replay.decision == first.decision
        assert replay.decision_message == first.decision_message
        assert len(_decision_messages(context)) == 1
        assert context.post_review_context.executor.call_count == 1
        assert context.post_review_context.transport.execute_calls == 1
    finally:
        context.close()


def test_fresh_session_convergence_replays_without_executor_or_reviewer_recall(tmp_path):
    context = build_real_p25_attempt_zero_convergence_context(tmp_path)
    fresh = None
    try:
        first = _decide(context)
        context.session.close()
        fresh = build_fresh_convergence_services(context)
        replay = _decide(context, service=fresh.convergence_service)

        assert first.status == "decision_persisted", first.blocked_reasons
        assert replay.status == "decision_replayed", replay.blocked_reasons
        assert replay.decision == first.decision
        assert replay.decision_message == first.decision_message
        assert context.post_review_context.executor.call_count == 1
        assert context.post_review_context.transport.execute_calls == 1
        assert fresh.session.in_transaction() is False
    finally:
        if fresh is not None:
            fresh.close()
        context.close()


def test_converged_decision_revalidates_as_terminal_for_p22_summary(tmp_path):
    context = build_real_p25_attempt_zero_convergence_context(tmp_path)
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
        assert revalidated.decision == first.decision
        assert revalidated.decision_message == first.decision_message
        assert revalidated.blocked_reasons == ("convergence_already_terminal",)
        assert revalidated.decision.next_rework_attempt_index is None
        assert revalidated.decision.next_attempt_eligible is False
        assert revalidated.decision.human_escalation_required is False
    finally:
        context.close()


def test_convergence_does_not_rollback_caller_owned_transaction(tmp_path):
    context = build_real_p25_attempt_zero_convergence_context(tmp_path)
    try:
        assert context.session.in_transaction() is False
        context.session.begin()
        task = context.session.get(TaskTable, context.task_id)
        assert task is not None
        task.input_summary = "caller-owned P25-I pending write"
        context.session.flush()

        result = _decide(context)

        assert result.status == "blocked"
        assert result.blocked_reasons == ("persistence_failed",)
        assert context.session.in_transaction() is True
        assert context.session.execute(
            select(TaskTable.input_summary).where(TaskTable.id == context.task_id)
        ).scalar_one() == "caller-owned P25-I pending write"
        assert _decision_messages(context) == ()
        assert context.post_review_context.executor.call_count == 1
        assert context.post_review_context.transport.execute_calls == 1
    finally:
        if context.session.in_transaction():
            context.session.rollback()
        context.close()


def test_convergence_blocks_before_h_c_summary_exists(tmp_path):
    context = build_real_p25_attempt_zero_review_execution_context(tmp_path)
    try:
        h_b_result = context.review_execution_service.execute_claimed_readonly_review(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_review_claim_message_id=context.h_a_result.review_claim_message.id,
        )
        candidate_context = context.review_preflight_context.candidate_context
        convergence_service = ProjectDirectorBoundedReworkConvergenceService(
            message_repository=context.message_repository,
            candidate_diff_service=candidate_context.candidate_diff_service,
            review_execution_service=context.review_execution_service,
            post_review_automation_service=(
                _build_post_review_services(context)[1]
            ),
        )
        result = convergence_service.decide_bounded_rework_convergence(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=(
                context.review_preflight_context.candidate_diff_result.diff_message.id
            ),
        )

        assert h_b_result.status == "review_outcome_persisted", h_b_result.blocked_reasons
        assert result.status == "blocked"
        assert result.decision is None
        assert result.decision_message is None
        assert result.blocked_reasons
    finally:
        context.close()


def test_convergence_persistence_failure_leaves_no_partial_decision(tmp_path, monkeypatch):
    context = build_real_p25_attempt_zero_convergence_context(tmp_path)
    try:
        original_create = context.post_review_context.message_repository.create

        def fail_convergence_decision(message):
            if message.intent == P25_BOUNDED_REWORK_CONVERGENCE_DECISION_INTENT:
                raise SQLAlchemyError("injected convergence persistence failure")
            return original_create(message)

        monkeypatch.setattr(
            context.post_review_context.message_repository,
            "create",
            fail_convergence_decision,
        )
        failed = _decide(context)
        monkeypatch.setattr(
            context.post_review_context.message_repository,
            "create",
            original_create,
        )
        recovered = _decide(context)

        assert failed.status == "recovery_required"
        assert failed.blocked_reasons == ("persistence_failed",)
        assert _decision_messages(context) == (recovered.decision_message,)
        assert recovered.status == "decision_persisted", recovered.blocked_reasons
        assert context.post_review_context.executor.call_count == 1
        assert context.post_review_context.transport.execute_calls == 1
    finally:
        context.close()


def test_workspace_drift_blocks_convergence_without_decision(tmp_path):
    context = build_real_p25_attempt_zero_convergence_context(tmp_path)
    try:
        workspace = (
            context.post_review_context.review_execution_context.review_preflight_context
            .environment["workspace_path"]
        )
        (workspace / "src/example.py").write_text("workspace drift\n", encoding="utf-8")

        result = _decide(context)

        assert result.status == "blocked"
        assert result.decision is None
        assert _decision_messages(context) == ()
    finally:
        context.close()


def test_second_legal_task_cannot_decide_first_task_candidate_diff(tmp_path):
    context = build_real_p25_attempt_zero_convergence_context(tmp_path)
    try:
        project_id = (
            context.post_review_context.review_execution_context.review_preflight_context
            .project_id
        )
        other_task = TaskRepository(context.session).create(
            Task(
                project_id=project_id,
                title="Independent task for P25-I authority isolation",
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


def test_tampered_convergence_decision_fails_closed_without_second_message(tmp_path):
    context = build_real_p25_attempt_zero_convergence_context(tmp_path)
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
