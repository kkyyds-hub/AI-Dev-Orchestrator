"""Real P25-F durable Outcome checks through its public coordinator API."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess

from sqlalchemy import func, select

from app.core.db_tables import RunTable, TaskTable
from tests.p25_outcome_real_chain_test_support import (
    RaisingBoundedReworkExecutor,
    RecordingBoundedReworkExecutor,
    build_fresh_outcome_services,
    build_real_p25_attempt_zero_outcome_context,
)


def _counts(context, *, package_service=None):
    service = package_service or context.claim_context.package_context.package_service
    session = service._message_repository._session
    caller_had_transaction = session.in_transaction()
    try:
        history = service._load_history(
            context.session_id,
            require_claim_outcomes=False,
        )
        return (
            len(history.packages),
            len(history.reservations),
            len(history.claims),
            len(history.outcomes),
        )
    finally:
        if not caller_had_transaction and session.in_transaction():
            session.rollback()


def _task_run_counts(session):
    caller_had_transaction = session.in_transaction()
    try:
        return (
            session.scalar(select(func.count()).select_from(TaskTable)),
            session.scalar(select(func.count()).select_from(RunTable)),
        )
    finally:
        if not caller_had_transaction and session.in_transaction():
            session.rollback()


def _git_control_fingerprint(repository: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((repository / ".git").rglob("*")):
        if path.is_file():
            digest.update(str(path.relative_to(repository)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _execute(context, service=None):
    return (service or context.outcome_service).execute_bounded_rework_from_reservation(
        session_id=context.session_id,
        source_task_id=context.task_id,
        source_reservation_message_id=context.claim_context.reservation_result.message.id,
    )


def test_real_attempt_zero_executes_once_and_records_outcome(tmp_path):
    context = build_real_p25_attempt_zero_outcome_context(tmp_path)
    try:
        result = _execute(context)

        assert result.status == "outcome_recorded", result.blocked_reasons
        assert result.claim is not None
        assert result.claim_message is not None
        assert result.outcome is not None
        assert result.outcome_message is not None
        assert isinstance(context.executor, RecordingBoundedReworkExecutor)
        assert context.executor.call_count == 1
        assert context.executor.session_states_at_call == [False]
        claim, outcome = result.claim, result.outcome
        assert claim.package_id == context.claim_context.package_result.package.package_id
        assert claim.reservation_id == context.claim_context.reservation_result.reservation.reservation_id
        assert claim.exact_task_id == context.task_id
        assert claim.exact_run_id == context.claim_context.package_context.run_id
        assert claim.rework_attempt_index == 0
        assert claim.invocation_ordinal == 0
        assert outcome.outcome_status == "returned"
        assert outcome.executor_attempted is True
        assert outcome.executor_started is True
        assert outcome.executor_returned is True
        assert outcome.executor_raised is False
        assert outcome.executor_result_valid is True
        assert outcome.safe_error_code is None
        assert outcome.redacted_error_summary is None
        assert outcome.declared_changed_paths == ("src/example.py",)
        assert outcome.observed_changed_paths == ("src/example.py",)
        assert outcome.scope_validation_status == "valid"
        assert outcome.side_effect_state == "observed"
        assert outcome.git_activity_detected is False
        assert outcome.git_activity_kinds == ()
        assert outcome.candidate_files_changed is True
        assert outcome.candidate_manifest_id is not None
        assert outcome.candidate_manifest_fingerprint is not None
        assert outcome.recovery_required is False
        assert outcome.human_escalation_required is False
        assert all(
            getattr(outcome, field) is False
            for field in (
                "product_runtime_git_write_allowed",
                "main_project_write_allowed",
                "git_add_allowed",
                "git_commit_allowed",
                "git_push_allowed",
                "branch_operation_allowed",
                "pull_request_allowed",
                "merge_allowed",
                "ci_trigger_allowed",
            )
        )
        assert _counts(context) == (1, 1, 1, 1)
    finally:
        context.close()


def test_outcome_execution_changes_only_bounded_workspace_file(tmp_path):
    context = build_real_p25_attempt_zero_outcome_context(tmp_path)
    try:
        workspace = context.environment["workspace_path"]
        repository = context.environment["repository_root"]
        manifest = workspace / ".ai-project-director/workspace-manifest.json"
        before = (
            subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            subprocess.run(["git", "status", "--porcelain"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            _git_control_fingerprint(repository),
            sorted(str(path.relative_to(workspace)) for path in workspace.rglob("*")),
            manifest.read_bytes(),
            (workspace / "src/example.py").read_bytes(),
            _task_run_counts(context.session),
        )

        result = _execute(context)

        after = (
            subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            subprocess.run(["git", "status", "--porcelain"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            _git_control_fingerprint(repository),
            sorted(str(path.relative_to(workspace)) for path in workspace.rglob("*")),
            manifest.read_bytes(),
            (workspace / "src/example.py").read_bytes(),
            _task_run_counts(context.session),
        )
        assert result.status == "outcome_recorded", result.blocked_reasons
        assert before[:5] == after[:5]
        assert before[5] != after[5]
        assert before[6] == after[6]
    finally:
        context.close()


def test_same_session_outcome_replays_without_executor_recall(tmp_path):
    context = build_real_p25_attempt_zero_outcome_context(tmp_path)
    try:
        first = _execute(context)
        second = _execute(context)

        assert first.status == "outcome_recorded", first.blocked_reasons
        assert second.status == "outcome_replayed", second.blocked_reasons
        assert second.claim == first.claim
        assert second.outcome == first.outcome
        assert second.outcome_message == first.outcome_message
        assert context.executor.call_count == 1
        assert _counts(context) == (1, 1, 1, 1)
    finally:
        context.close()


def test_fresh_session_outcome_replays_without_executor_recall(tmp_path):
    context = build_real_p25_attempt_zero_outcome_context(tmp_path)
    fresh = None
    try:
        first = _execute(context)
        assert first.status == "outcome_recorded", first.blocked_reasons
        context.session.close()
        fresh = build_fresh_outcome_services(context)
        replay = _execute(context, service=fresh.outcome_service)

        assert replay.status == "outcome_replayed", replay.blocked_reasons
        assert replay.claim == first.claim
        assert replay.outcome == first.outcome
        assert context.executor.call_count == 1
        assert _counts(
            context,
            package_service=fresh.claim_services.reservation_services.package_service,
        ) == (1, 1, 1, 1)
        assert fresh.session.in_transaction() is False
    finally:
        if fresh is not None:
            fresh.close()
        context.close()


def test_outcome_coordinator_does_not_rollback_caller_owned_transaction(tmp_path):
    context = build_real_p25_attempt_zero_outcome_context(tmp_path)
    try:
        context.session.begin()
        task = context.session.get(TaskTable, context.task_id)
        assert task is not None
        task.input_summary = "caller-owned Outcome pending write"
        context.session.flush()

        result = _execute(context)

        assert result.status == "blocked"
        assert result.blocked_reasons == ("history_invalid",)
        assert context.session.in_transaction() is True
        persisted_value = context.session.execute(
            select(TaskTable.input_summary).where(TaskTable.id == context.task_id)
        ).scalar_one()
        assert persisted_value == "caller-owned Outcome pending write"
        assert context.executor.call_count == 0
        assert _counts(context) == (1, 1, 0, 0)
    finally:
        if context.session.in_transaction():
            context.session.rollback()
        context.close()


def test_raising_executor_records_durable_outcome_and_replays(tmp_path):
    executor = RaisingBoundedReworkExecutor(session=None)
    context = build_real_p25_attempt_zero_outcome_context(tmp_path, executor=executor)
    try:
        executor.session = context.session
        first = _execute(context)
        second = _execute(context)

        assert first.status == "outcome_recorded", first.blocked_reasons
        assert first.outcome is not None
        assert first.outcome.outcome_status == "raised"
        assert first.outcome.executor_attempted is True
        assert first.outcome.executor_started is True
        assert first.outcome.executor_returned is False
        assert first.outcome.executor_raised is True
        assert first.outcome.executor_result_valid is False
        assert first.outcome.safe_error_code == "executor_raised"
        assert first.outcome.recovery_required is True
        assert first.outcome.human_escalation_required is False
        assert "api_key=" not in (first.outcome.redacted_error_summary or "")
        assert second.status == "outcome_replayed", second.blocked_reasons
        assert executor.call_count == 1
        assert _counts(context) == (1, 1, 1, 1)
    finally:
        context.close()


def test_mismatched_declared_paths_records_durable_invalid_outcome(tmp_path):
    executor = RecordingBoundedReworkExecutor(session=None, declared_changed_paths=())
    context = build_real_p25_attempt_zero_outcome_context(tmp_path, executor=executor)
    try:
        executor.session = context.session
        first = _execute(context)
        second = _execute(context)

        assert first.status == "outcome_recorded", first.blocked_reasons
        assert first.outcome is not None
        assert first.outcome.outcome_status == "invalid_result"
        assert first.outcome.executor_result_valid is False
        assert first.outcome.safe_error_code == "execution_result_invalid"
        assert first.outcome.recovery_required is True
        assert first.outcome.human_escalation_required is False
        assert second.status == "outcome_replayed", second.blocked_reasons
        assert executor.call_count == 1
        assert _counts(context) == (1, 1, 1, 1)
    finally:
        context.close()
