"""P25-I-D closes the exact P23 task/run attempt before a retry."""

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from app.domain.run import RunFailureCategory, RunStatus
from app.domain.task import TaskStatus
from app.services.project_director_bounded_rework_attempt_lifecycle_closure_service import (
    ProjectDirectorBoundedReworkAttemptLifecycleClosureService,
)
from tests.p25_convergence_real_chain_test_support import (
    build_real_p25_attempt_zero_convergence_context,
)
from tests.p25_convergence_next_attempt_real_chain_test_support import (
    build_fresh_next_attempt_convergence_services,
    build_real_p25_attempt_zero_next_attempt_convergence_context,
)


def test_next_attempt_decision_closes_exact_running_task_and_run(tmp_path):
    context = build_real_p25_attempt_zero_next_attempt_convergence_context(tmp_path)
    try:
        decision = context.convergence_service.decide_bounded_rework_convergence(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=context.candidate_diff_message_id,
        )
        assert decision.decision is not None
        assert decision.decision_message is not None
        assert decision.decision.decision_type == "NEXT_ATTEMPT_ELIGIBLE"

        package_context = (
            context.review_execution_context.review_preflight_context.candidate_context
            .outcome_context.claim_context.package_context
        )
        closure = ProjectDirectorBoundedReworkAttemptLifecycleClosureService(
            message_repository=context.message_repository,
            task_repository=(
                package_context.package_service._dispatch_intent_service._task_repository
            ),
            run_repository=(
                package_context.package_service._dispatch_consumption_service._run_repository
            ),
            dispatch_consumption_service=(
                package_context.package_service._dispatch_consumption_service
            ),
            convergence_service=context.convergence_service,
        ).close_bounded_rework_attempt_lifecycle(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_convergence_decision_message_id=decision.decision_message.id,
        )

        assert closure.status == "closure_persisted", closure.blocked_reasons
        assert closure.closure is not None
        assert closure.closure.closure_kind == "retryable_verification_failure"
        assert closure.task is not None and closure.task.status == TaskStatus.FAILED
        assert closure.run is not None and closure.run.status == RunStatus.FAILED
        assert closure.run.failure_category == RunFailureCategory.VERIFICATION_FAILED
        assert closure.run.quality_gate_passed is False
    finally:
        context.close()


def test_next_attempt_lifecycle_closure_replays_after_task_and_run_are_closed(tmp_path):
    context = build_real_p25_attempt_zero_next_attempt_convergence_context(tmp_path)
    try:
        decision = context.convergence_service.decide_bounded_rework_convergence(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=context.candidate_diff_message_id,
        )
        assert decision.decision_message is not None

        package_context = (
            context.review_execution_context.review_preflight_context.candidate_context
            .outcome_context.claim_context.package_context
        )
        service = ProjectDirectorBoundedReworkAttemptLifecycleClosureService(
            message_repository=context.message_repository,
            task_repository=(
                package_context.package_service._dispatch_intent_service._task_repository
            ),
            run_repository=(
                package_context.package_service._dispatch_consumption_service._run_repository
            ),
            dispatch_consumption_service=(
                package_context.package_service._dispatch_consumption_service
            ),
            convergence_service=context.convergence_service,
        )

        first = service.close_bounded_rework_attempt_lifecycle(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_convergence_decision_message_id=decision.decision_message.id,
        )
        replay = service.close_bounded_rework_attempt_lifecycle(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_convergence_decision_message_id=decision.decision_message.id,
        )

        assert first.status == "closure_persisted", first.blocked_reasons
        assert replay.status == "closure_replayed", replay.blocked_reasons
        assert replay.closure == first.closure
        assert replay.message == first.message
        assert replay.task is not None and replay.task.status == TaskStatus.FAILED
        assert replay.run is not None and replay.run.status == RunStatus.FAILED
    finally:
        context.close()


def test_lifecycle_message_failure_leaves_task_and_run_running(tmp_path, monkeypatch):
    context = build_real_p25_attempt_zero_next_attempt_convergence_context(tmp_path)
    try:
        decision = context.convergence_service.decide_bounded_rework_convergence(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=context.candidate_diff_message_id,
        )
        assert decision.decision_message is not None

        package_context = (
            context.review_execution_context.review_preflight_context.candidate_context
            .outcome_context.claim_context.package_context
        )
        service = ProjectDirectorBoundedReworkAttemptLifecycleClosureService(
            message_repository=context.message_repository,
            task_repository=(
                package_context.package_service._dispatch_intent_service._task_repository
            ),
            run_repository=(
                package_context.package_service._dispatch_consumption_service._run_repository
            ),
            dispatch_consumption_service=(
                package_context.package_service._dispatch_consumption_service
            ),
            convergence_service=context.convergence_service,
        )
        original_create = context.message_repository.create

        def fail_closure_message(message):
            if message.intent == "bounded_rework_attempt_lifecycle_closure":
                raise SQLAlchemyError("injected P25 lifecycle message failure")
            return original_create(message)

        monkeypatch.setattr(context.message_repository, "create", fail_closure_message)
        failed = service.close_bounded_rework_attempt_lifecycle(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_convergence_decision_message_id=decision.decision_message.id,
        )

        assert failed.status == "recovery_required"
        assert failed.blocked_reasons == ("persistence_failed",)
        task = package_context.package_service._dispatch_intent_service._task_repository.get_by_id(
            context.task_id
        )
        run = package_context.package_service._dispatch_consumption_service._run_repository.get_by_id(
            decision.decision.authority.source_run_id
        )
        assert task is not None and task.status == TaskStatus.RUNNING
        assert run is not None and run.status == RunStatus.RUNNING
    finally:
        context.close()


def test_next_attempt_lifecycle_closure_replays_from_fresh_session(tmp_path):
    context = build_real_p25_attempt_zero_next_attempt_convergence_context(tmp_path)
    fresh = None
    try:
        decision = context.convergence_service.decide_bounded_rework_convergence(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=context.candidate_diff_message_id,
        )
        assert decision.decision_message is not None

        package_context = (
            context.review_execution_context.review_preflight_context.candidate_context
            .outcome_context.claim_context.package_context
        )
        first = ProjectDirectorBoundedReworkAttemptLifecycleClosureService(
            message_repository=context.message_repository,
            task_repository=(
                package_context.package_service._dispatch_intent_service._task_repository
            ),
            run_repository=(
                package_context.package_service._dispatch_consumption_service._run_repository
            ),
            dispatch_consumption_service=(
                package_context.package_service._dispatch_consumption_service
            ),
            convergence_service=context.convergence_service,
        ).close_bounded_rework_attempt_lifecycle(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_convergence_decision_message_id=decision.decision_message.id,
        )
        assert first.status == "closure_persisted", first.blocked_reasons

        context.session.close()
        fresh = build_fresh_next_attempt_convergence_services(context)
        reservation_services = (
            fresh.review_execution_services.review_preflight_services.candidate_services
            .outcome_services.claim_services.reservation_services
        )
        replay = ProjectDirectorBoundedReworkAttemptLifecycleClosureService(
            message_repository=reservation_services.message_repository,
            task_repository=reservation_services.task_repository,
            run_repository=reservation_services.run_repository,
            dispatch_consumption_service=(
                reservation_services.package_service._dispatch_consumption_service
            ),
            convergence_service=fresh.convergence_service,
        ).close_bounded_rework_attempt_lifecycle(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_convergence_decision_message_id=decision.decision_message.id,
        )

        assert replay.status == "closure_replayed", replay.blocked_reasons
        assert replay.closure == first.closure
        assert replay.message == first.message
        assert context.executor.call_count == 1
        assert context.transport.execute_calls == 1
    finally:
        if fresh is not None:
            fresh.close()
        context.close()


def test_converged_decision_completes_exact_running_task_and_run(tmp_path):
    context = build_real_p25_attempt_zero_convergence_context(tmp_path)
    try:
        preflight_context = (
            context.post_review_context.review_execution_context.review_preflight_context
        )
        candidate_context = preflight_context.candidate_context
        decision = context.convergence_service.decide_bounded_rework_convergence(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=(
                preflight_context.candidate_diff_result.diff_message.id
            ),
        )
        assert decision.decision_message is not None
        assert decision.decision is not None
        assert decision.decision.decision_type == "CONVERGED"

        package_context = candidate_context.outcome_context.claim_context.package_context
        closure = ProjectDirectorBoundedReworkAttemptLifecycleClosureService(
            message_repository=context.post_review_context.message_repository,
            task_repository=(
                package_context.package_service._dispatch_intent_service._task_repository
            ),
            run_repository=(
                package_context.package_service._dispatch_consumption_service._run_repository
            ),
            dispatch_consumption_service=(
                package_context.package_service._dispatch_consumption_service
            ),
            convergence_service=context.convergence_service,
        ).close_bounded_rework_attempt_lifecycle(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_convergence_decision_message_id=decision.decision_message.id,
        )

        assert closure.status == "closure_persisted", closure.blocked_reasons
        assert closure.closure is not None
        assert closure.closure.closure_kind == "converged_success"
        assert closure.task is not None and closure.task.status == TaskStatus.COMPLETED
        assert closure.run is not None and closure.run.status == RunStatus.SUCCEEDED
        assert closure.run.failure_category is None
        assert closure.run.quality_gate_passed is True
    finally:
        context.close()
