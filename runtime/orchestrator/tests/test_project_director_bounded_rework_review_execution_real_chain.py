"""P25-H-B real readonly review execution transaction regression coverage."""

from __future__ import annotations

import json
import subprocess

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.db_tables import TaskTable
from app.domain.project_role import ProjectRoleCode
from app.domain.task import Task
from app.repositories.task_repository import TaskRepository
from app.services.project_director_bounded_rework_review_execution_service import (
    P25_BOUNDED_REWORK_REVIEW_ATTEMPT_INTENT,
    P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT,
)
from tests.p25_review_execution_real_chain_test_support import (
    VALID_REVIEW_OUTPUT,
    build_fresh_review_execution_services,
    build_real_p25_attempt_zero_review_execution_context,
)


def _review_execution_messages(context):
    session = context.message_repository._session
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
            if message.intent
            in {
                P25_BOUNDED_REWORK_REVIEW_ATTEMPT_INTENT,
                P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT,
            }
        )
    finally:
        if not caller_had_transaction and session.in_transaction():
            session.rollback()


def _execute(context, *, service=None, task_id=None):
    return (service or context.review_execution_service).execute_claimed_readonly_review(
        session_id=context.session_id,
        source_task_id=task_id or context.task_id,
        source_review_claim_message_id=context.h_a_result.review_claim_message.id,
    )


def test_review_execution_does_not_rollback_caller_owned_transaction(tmp_path):
    context = build_real_p25_attempt_zero_review_execution_context(tmp_path)
    try:
        assert context.session.in_transaction() is False
        context.session.begin()
        task = context.session.get(TaskTable, context.task_id)
        assert task is not None
        task.input_summary = "caller-owned P25-H-B pending write"
        context.session.flush()

        result = context.review_execution_service.execute_claimed_readonly_review(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_review_claim_message_id=context.h_a_result.review_claim_message.id,
        )

        assert result.status == "blocked"
        assert result.blocked_reasons == ("history_invalid",)
        assert context.session.in_transaction() is True
        assert context.session.execute(
            select(TaskTable.input_summary).where(TaskTable.id == context.task_id)
        ).scalar_one() == "caller-owned P25-H-B pending write"
        assert _review_execution_messages(context) == ()
        assert context.resolver_factory.factory_calls == 0
        assert context.resolver_factory.resolver_calls == 0
        assert context.transport.execute_calls == 0
    finally:
        if context.session.in_transaction():
            context.session.rollback()
        context.close()


def test_real_attempt_zero_executes_readonly_review_once_and_persists_outcome(tmp_path):
    context = build_real_p25_attempt_zero_review_execution_context(tmp_path)
    try:
        result = context.review_execution_service.execute_claimed_readonly_review(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_review_claim_message_id=context.h_a_result.review_claim_message.id,
        )

        assert result.status == "review_outcome_persisted", result.blocked_reasons
        assert result.blocked_reasons == ()
        assert result.review_attempt is not None
        assert result.review_attempt_message is not None
        assert result.review_outcome is not None
        assert result.review_outcome_message is not None
        assert result.review_outcome.outcome_status == "validated_output"
        assert context.resolver_factory.factory_calls == 1
        assert context.resolver_factory.resolver_calls == 1
        assert context.transport.execute_calls == 1
        assert context.transport.session_states_at_call == [False]
        assert len(_review_execution_messages(context)) == 2
    finally:
        context.close()


def test_review_execution_is_readonly_and_persists_no_raw_prompt_or_output(tmp_path):
    context = build_real_p25_attempt_zero_review_execution_context(tmp_path)
    try:
        workspace = context.environment["workspace_path"]
        repository = context.environment["repository_root"]
        business_path = workspace / "src/example.py"
        manifest_path = workspace / ".ai-project-director/workspace-manifest.json"
        before = (
            business_path.read_bytes(),
            manifest_path.read_bytes(),
            manifest_path.stat().st_ino,
            manifest_path.stat().st_mtime_ns,
            subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repository, check=True,
                capture_output=True, text=True,
            ).stdout,
            subprocess.run(
                ["git", "status", "--porcelain"], cwd=repository, check=True,
                capture_output=True, text=True,
            ).stdout,
        )

        result = _execute(context)

        assert result.status == "review_outcome_persisted", result.blocked_reasons
        assert before == (
            business_path.read_bytes(),
            manifest_path.read_bytes(),
            manifest_path.stat().st_ino,
            manifest_path.stat().st_mtime_ns,
            subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repository, check=True,
                capture_output=True, text=True,
            ).stdout,
            subprocess.run(
                ["git", "status", "--porcelain"], cwd=repository, check=True,
                capture_output=True, text=True,
            ).stdout,
        )
        persisted = "\n".join(
            f"{message.content}\n{json.dumps(message.suggested_actions)}"
            for message in _review_execution_messages(context)
        )
        request = context.transport.requests[0]
        assert context.h_a_result.review_claim.review_claim_token not in persisted
        assert request.review_prompt_text not in persisted
        assert VALID_REVIEW_OUTPUT not in persisted
        for message in _review_execution_messages(context):
            assert tuple(message.forbidden_actions_detected) == (
                "provider_called=false",
                "main_project_write_allowed=false",
                "product_runtime_git_write_allowed=false",
                "patch_apply_allowed=false",
                "git_write_allowed=false",
                "task_created=false",
                "run_created=false",
            )
    finally:
        context.close()


def test_reviewer_receives_exact_rebuilt_prompt_and_scope(tmp_path):
    context = build_real_p25_attempt_zero_review_execution_context(tmp_path)
    try:
        result = _execute(context)
        request = context.transport.requests[0]
        preflight = context.h_a_result.preflight

        assert result.status == "review_outcome_persisted", result.blocked_reasons
        assert context.resolver_factory.workspace_paths == [
            context.environment["workspace_path"].as_posix()
        ]
        assert context.resolver_factory.requested_reviewer_executors == [
            preflight.requested_reviewer_executor
        ]
        assert request.requested_reviewer_executor == preflight.requested_reviewer_executor
        assert request.review_prompt_sha256 == preflight.review_prompt_sha256
        assert request.review_prompt_bytes == preflight.review_prompt_bytes
        assert request.review_scope_paths == ["src/example.py"]
        assert request.review_output_schema_version == preflight.review_output_schema_version
        assert len(request.review_prompt_text.encode("utf-8")) == preflight.review_prompt_bytes
    finally:
        context.close()


def test_same_session_review_outcome_replays_without_reviewer_recall(tmp_path):
    context = build_real_p25_attempt_zero_review_execution_context(tmp_path)
    try:
        first = _execute(context)
        replay = _execute(context)

        assert first.status == "review_outcome_persisted", first.blocked_reasons
        assert replay.status == "review_outcome_replayed", replay.blocked_reasons
        assert replay.review_attempt == first.review_attempt
        assert replay.review_attempt_message == first.review_attempt_message
        assert replay.review_outcome == first.review_outcome
        assert replay.review_outcome_message == first.review_outcome_message
        assert context.resolver_factory.factory_calls == 1
        assert context.resolver_factory.resolver_calls == 1
        assert context.transport.execute_calls == 1
        assert len(_review_execution_messages(context)) == 2
    finally:
        context.close()


def test_fresh_session_review_outcome_replays_without_reviewer_recall(tmp_path):
    context = build_real_p25_attempt_zero_review_execution_context(tmp_path)
    fresh = None
    try:
        first = _execute(context)
        context.session.close()
        fresh = build_fresh_review_execution_services(context)
        replay = _execute(context, service=fresh.review_execution_service)

        assert first.status == "review_outcome_persisted", first.blocked_reasons
        assert replay.status == "review_outcome_replayed", replay.blocked_reasons
        assert replay.review_attempt == first.review_attempt
        assert replay.review_outcome == first.review_outcome
        assert context.transport.execute_calls == 1
        assert fresh.session.in_transaction() is False
    finally:
        if fresh is not None:
            fresh.close()
        context.close()


def test_persisted_review_outcome_revalidates_as_current_p25_h_output(tmp_path):
    context = build_real_p25_attempt_zero_review_execution_context(tmp_path)
    try:
        result = _execute(context)
        revalidated = context.review_execution_service.revalidate_persisted_review_invocation_outcome(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_review_outcome_message_id=result.review_outcome_message.id,
        )
        by_diff = context.review_execution_service.revalidate_review_outcome_for_candidate_diff(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=context.h_a_result.preflight.source_candidate_diff_message_id,
        )

        assert result.status == "review_outcome_persisted", result.blocked_reasons
        assert revalidated.status == "validated_output", revalidated.blocked_reasons
        assert revalidated.review_attempt == result.review_attempt
        assert revalidated.review_outcome == result.review_outcome
        assert by_diff.status == "validated_output", by_diff.blocked_reasons
        assert by_diff.review_outcome == result.review_outcome
        assert result.review_outcome.review_claim_id != context.h_a_result.preflight.old_review_message_id
    finally:
        context.close()


def test_invalid_reviewer_output_is_durable_blocked_outcome_without_recall(tmp_path):
    context = build_real_p25_attempt_zero_review_execution_context(tmp_path)
    try:
        context.transport.raw_output_text = "{}"
        first = _execute(context)
        replay = _execute(context)

        assert first.status == "review_outcome_persisted", first.blocked_reasons
        assert first.review_outcome.outcome_status == "blocked"
        assert first.review_outcome.adapter_result.adapter_status == "blocked"
        assert first.review_outcome.blocked_reasons
        assert first.review_outcome.review_semantic_fingerprint is None
        assert replay.status == "review_outcome_replayed", replay.blocked_reasons
        assert context.transport.execute_calls == 1
    finally:
        context.close()


def test_resolver_factory_exception_is_durable_raised_outcome_without_recall(tmp_path):
    context = build_real_p25_attempt_zero_review_execution_context(tmp_path)
    try:
        context.resolver_factory.factory_exception = RuntimeError("sensitive failure text")
        first = _execute(context)
        replay = _execute(context)

        assert first.status == "review_outcome_persisted", first.blocked_reasons
        assert first.review_outcome.outcome_status == "raised"
        assert first.review_outcome.safe_error_code == "reviewer_transport_resolver_factory_raised"
        assert first.review_outcome.adapter_result is None
        assert first.review_outcome.recovery_required is False
        assert first.review_outcome.human_escalation_required is False
        assert replay.status == "review_outcome_replayed", replay.blocked_reasons
        assert context.resolver_factory.factory_calls == 1
        assert context.transport.execute_calls == 0
        assert "sensitive failure text" not in "\n".join(
            message.content for message in _review_execution_messages(context)
        )
    finally:
        context.close()


def test_review_outcome_persistence_failure_never_recalls_reviewer(tmp_path):
    context = build_real_p25_attempt_zero_review_execution_context(tmp_path)
    fresh = None
    original_create = context.message_repository.create
    try:
        def create_with_outcome_failure(message):
            if message.intent == P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT:
                raise SQLAlchemyError("injected review outcome persistence failure")
            return original_create(message)

        context.message_repository.create = create_with_outcome_failure
        first = _execute(context)
        context.message_repository.create = original_create
        replay = _execute(context)
        context.session.close()
        fresh = build_fresh_review_execution_services(context)
        fresh_replay = _execute(context, service=fresh.review_execution_service)

        assert first.status == "recovery_required"
        assert first.blocked_reasons == ("claim_without_outcome",)
        assert len(_review_execution_messages(context)) == 1
        assert context.transport.execute_calls == 1
        assert replay.status == "recovery_required"
        assert fresh_replay.status == "recovery_required"
        assert context.transport.execute_calls == 1
    finally:
        context.message_repository.create = original_create
        if fresh is not None:
            fresh.close()
        context.close()


def test_workspace_drift_blocks_before_review_attempt_or_transport(tmp_path):
    context = build_real_p25_attempt_zero_review_execution_context(tmp_path)
    try:
        (context.environment["workspace_path"] / "src/example.py").write_text(
            "workspace drift\n", encoding="utf-8"
        )
        result = _execute(context)

        assert result.status == "blocked"
        assert result.blocked_reasons == ("workspace_invalid",)
        assert _review_execution_messages(context) == ()
        assert context.transport.execute_calls == 0
    finally:
        context.close()


def test_second_legal_task_cannot_execute_first_task_review_claim(tmp_path):
    context = build_real_p25_attempt_zero_review_execution_context(tmp_path)
    try:
        other_task = TaskRepository(context.session).create(
            Task(
                project_id=context.review_preflight_context.project_id,
                title="Independent task for P25-H-B authority isolation",
                input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
                acceptance_criteria=["safe_dry_run_task=true"],
                owner_role_code=ProjectRoleCode.ARCHITECT,
            )
        )
        if context.session.in_transaction():
            context.session.rollback()

        result = _execute(context, task_id=other_task.id)

        assert result.status == "blocked"
        assert _review_execution_messages(context) == ()
        assert context.transport.execute_calls == 0
        assert context.session.in_transaction() is False
    finally:
        context.close()
