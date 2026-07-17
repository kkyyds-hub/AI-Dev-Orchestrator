"""Real P25-E durable Claim checks without executor or Outcome execution."""

from __future__ import annotations

import subprocess
from uuid import uuid4

from sqlalchemy import func, select

from app.core.db_tables import RunTable, TaskTable
from app.domain.project_role import ProjectRoleCode
from app.domain.task import Task
from app.services.project_director_bounded_rework_invocation_claim_service import (
    P25_BOUNDED_REWORK_EXECUTOR_ADAPTER_KIND,
)
from tests.p25_claim_real_chain_test_support import (
    RealP25AttemptZeroClaimContext,
    build_fresh_claim_services,
    build_real_p25_attempt_zero_claim_context,
)


def _counts(
    context: RealP25AttemptZeroClaimContext,
    *,
    package_service=None,
):
    current_package_service = package_service or context.package_context.package_service
    current_session = current_package_service._message_repository._session
    caller_had_transaction = current_session.in_transaction()
    try:
        history = current_package_service._load_history(
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
        if not caller_had_transaction and current_session.in_transaction():
            current_session.rollback()


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


def _claim(context, service=None, task_id=None, reservation_message_id=None):
    return (service or context.claim_service).claim_bounded_rework_invocation(
        session_id=context.session_id,
        source_task_id=task_id or context.task_id,
        source_reservation_message_id=(
            reservation_message_id or context.reservation_result.message.id
        ),
    )


def test_real_attempt_zero_claims_exact_invocation(tmp_path):
    context = build_real_p25_attempt_zero_claim_context(tmp_path)
    try:
        result = _claim(context)

        assert result.status == "claim_claimed", result.blocked_reasons
        assert result.blocked_reasons == ()
        assert result.claim is not None
        assert result.message is not None
        claim = result.claim
        reservation = context.reservation_result.reservation
        package = context.package_result.package
        assert claim.reservation_id == reservation.reservation_id
        assert claim.package_id == package.package_id
        assert claim.exact_task_id == context.task_id
        assert claim.exact_run_id == context.package_context.run_id
        assert claim.rework_attempt_index == 0
        assert claim.rework_attempt_limit == 3
        assert claim.authority == package.authority == reservation.authority
        assert claim.invocation_ordinal == 0
        assert claim.executor_adapter_kind == P25_BOUNDED_REWORK_EXECUTOR_ADAPTER_KIND
        assert claim.workspace_before_manifest_fingerprint
        assert claim.workspace_before_content_fingerprint
        assert all(
            getattr(claim, field) is False
            for field in (
                "executor_call_attempted",
                "executor_started",
                "executor_returned",
                "executor_raised",
                "executor_success_evidence_present",
                "sandbox_file_written_by_claim",
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
        assert _counts(context) == (1, 1, 1, 0)
        assert context.session.in_transaction() is False
    finally:
        context.close()


def test_claim_is_read_only_and_does_not_mutate_workspace(tmp_path):
    context = build_real_p25_attempt_zero_claim_context(tmp_path)
    try:
        workspace = context.environment["workspace_path"]
        repository = context.environment["repository_root"]
        manifest = workspace / ".ai-project-director/workspace-manifest.json"
        before = (
            sorted(str(path.relative_to(workspace)) for path in workspace.rglob("*")),
            (workspace / "src/example.py").read_bytes(),
            manifest.read_bytes(),
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repository,
                check=True,
                capture_output=True,
                text=True,
            ).stdout,
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repository,
                check=True,
                capture_output=True,
                text=True,
            ).stdout,
            _task_run_counts(context.session),
        )

        result = _claim(context)

        after = (
            sorted(str(path.relative_to(workspace)) for path in workspace.rglob("*")),
            (workspace / "src/example.py").read_bytes(),
            manifest.read_bytes(),
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repository,
                check=True,
                capture_output=True,
                text=True,
            ).stdout,
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repository,
                check=True,
                capture_output=True,
                text=True,
            ).stdout,
            _task_run_counts(context.session),
        )
        assert result.status == "claim_claimed", result.blocked_reasons
        assert before == after
        assert _counts(context) == (1, 1, 1, 0)
    finally:
        context.close()


def test_pending_claim_blocks_same_session_duplicate(tmp_path):
    context = build_real_p25_attempt_zero_claim_context(tmp_path)
    try:
        first = _claim(context)
        second = _claim(context)

        assert first.status == "claim_claimed", first.blocked_reasons
        assert first.claim is not None
        assert first.message is not None
        assert second.status == "blocked"
        assert second.blocked_reasons == ("claim_without_outcome",)
        assert second.claim == first.claim
        assert second.message == first.message
        assert _counts(context) == (1, 1, 1, 0)
    finally:
        context.close()


def test_pending_claim_survives_fresh_session_without_second_claim(tmp_path):
    context = build_real_p25_attempt_zero_claim_context(tmp_path)
    fresh = None
    try:
        first = _claim(context)
        assert first.status == "claim_claimed", first.blocked_reasons
        assert first.claim is not None
        assert first.message is not None

        context.session.close()
        fresh = build_fresh_claim_services(context)
        replay = _claim(context, service=fresh.claim_service)

        assert replay.status == "blocked"
        assert replay.blocked_reasons == ("claim_without_outcome",)
        assert replay.claim is not None
        assert replay.message is not None
        assert replay.claim.claim_id == first.claim.claim_id
        assert replay.message.id == first.message.id
        assert _counts(
            context,
            package_service=fresh.reservation_services.package_service,
        ) == (1, 1, 1, 0)
        assert fresh.session.in_transaction() is False
    finally:
        if fresh is not None:
            fresh.close()
        context.close()


def test_claim_does_not_rollback_caller_owned_transaction(tmp_path):
    context = build_real_p25_attempt_zero_claim_context(tmp_path)
    try:
        context.session.begin()
        task = context.session.get(TaskTable, context.task_id)
        assert task is not None
        task.input_summary = "caller-owned Claim pending write"
        context.session.flush()

        result = _claim(context)

        assert result.status == "blocked"
        assert result.blocked_reasons == ("history_invalid",)
        assert context.session.in_transaction() is True
        persisted_value = context.session.execute(
            select(TaskTable.input_summary).where(TaskTable.id == context.task_id)
        ).scalar_one()
        assert persisted_value == "caller-owned Claim pending write"
        assert _counts(context) == (1, 1, 0, 0)
    finally:
        if context.session.in_transaction():
            context.session.rollback()
        context.close()


def test_claim_releases_owned_read_transaction_when_reservation_preflight_blocks(tmp_path):
    context = build_real_p25_attempt_zero_claim_context(tmp_path)
    try:
        result = _claim(context, reservation_message_id=uuid4())

        assert result.status == "blocked"
        assert result.claim is None
        assert result.message is None
        assert _counts(context) == (1, 1, 0, 0)
        assert context.session.in_transaction() is False
    finally:
        context.close()


def test_claim_rejects_cross_task_reservation_without_persistence(tmp_path):
    context = build_real_p25_attempt_zero_claim_context(tmp_path)
    try:
        task_repository = context.claim_service._attempt_reservation_service._task_repository
        other_task = task_repository.create(
            Task(
                project_id=context.project_id,
                title="Independent task for cross-task P25-E rejection",
                input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
                acceptance_criteria=["safe_dry_run_task=true"],
                owner_role_code=ProjectRoleCode.ARCHITECT,
            )
        )
        if context.session.in_transaction():
            context.session.rollback()
        before_task_runs = _task_run_counts(context.session)

        result = _claim(context, task_id=other_task.id)

        assert result.status == "blocked"
        assert result.claim is None
        assert result.message is None
        assert _counts(context) == (1, 1, 0, 0)
        assert _task_run_counts(context.session) == before_task_runs
        assert context.session.in_transaction() is False
    finally:
        context.close()
