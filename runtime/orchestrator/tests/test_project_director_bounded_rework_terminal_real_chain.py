"""Persisted terminal closeout coverage over an actual P25-B through P25-G chain."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.run import RunStatus
from app.domain.task import TaskHumanStatus, TaskStatus
from app.external_executors.project_director_bounded_rework_executor import (
    ProjectDirectorBoundedReworkExecutorRequest,
    ProjectDirectorBoundedReworkExecutorResult,
)
from app.services.project_director_bounded_rework_attempt_lifecycle_closure_service import (
    ProjectDirectorBoundedReworkAttemptLifecycleClosureService,
)
from app.services.project_director_bounded_rework_convergence_service import (
    ProjectDirectorBoundedReworkConvergenceService,
)
from app.services.project_director_bounded_rework_terminal_escalation_service import (
    ProjectDirectorBoundedReworkTerminalEscalationService,
)
from tests.p25_candidate_diff_real_chain_test_support import (
    build_real_p25_attempt_zero_candidate_diff_context,
)


@dataclass(slots=True)
class _NoChangeBoundedReworkExecutor:
    """A controlled P25 executor that performs no workspace write."""

    session: object | None = None
    call_count: int = 0

    def execute_bounded_rework(
        self,
        request: ProjectDirectorBoundedReworkExecutorRequest,
    ) -> ProjectDirectorBoundedReworkExecutorResult:
        assert self.session is not None
        assert self.session.in_transaction() is False
        self.call_count += 1
        return ProjectDirectorBoundedReworkExecutorResult(
            result_status="returned",
            declared_changed_paths=(),
            safe_summary="No bounded workspace changes were required.",
            git_add=False,
            git_commit=False,
            git_push=False,
            branch_create=False,
            branch_delete=False,
            checkout=False,
            switch=False,
            reset=False,
            stash=False,
            rebase=False,
            tag=False,
            pull_request=False,
            merge=False,
            ci_trigger=False,
            main_project_write=False,
            workspace_escape=False,
        )


class _UnusedReviewOrPostReviewService:
    """Non-convergence must decide before any P25-H/P22 service is entered."""

    def __init__(self, message_repository) -> None:
        self._message_repository = message_repository

    def __getattr__(self, name):
        raise AssertionError(f"terminal non-convergence called unexpected dependency: {name}")


def test_empty_diff_escalates_and_closes_the_exact_running_attempt(tmp_path):
    executor = _NoChangeBoundedReworkExecutor()
    context = build_real_p25_attempt_zero_candidate_diff_context(
        tmp_path,
        executor=executor,
    )
    try:
        executor.session = context.session
        outcome = (
            context.outcome_context.outcome_service
            .execute_bounded_rework_from_reservation(
                session_id=context.session_id,
                source_task_id=context.task_id,
                source_reservation_message_id=(
                    context.outcome_context.claim_context.reservation_result.message.id
                ),
            )
        )
        assert outcome.status == "outcome_recorded", outcome.blocked_reasons
        assert outcome.outcome_message is not None

        candidate = context.candidate_diff_service.regenerate_candidate_manifest_and_diff(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_outcome_message_id=outcome.outcome_message.id,
        )
        assert candidate.status == "candidate_diff_non_convergence", candidate.blocked_reasons
        assert candidate.candidate_diff is not None
        assert candidate.diff_message is not None
        assert candidate.candidate_diff.diff_status == "non_convergence"
        assert candidate.candidate_diff.non_convergence_reason == "empty_diff"

        package_context = context.outcome_context.claim_context.package_context
        message_repository = package_context.msg_repo
        unused = _UnusedReviewOrPostReviewService(message_repository)
        convergence = ProjectDirectorBoundedReworkConvergenceService(
            message_repository=message_repository,
            candidate_diff_service=context.candidate_diff_service,
            review_execution_service=unused,
            post_review_automation_service=unused,
        )
        decision = convergence.decide_bounded_rework_convergence(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=candidate.diff_message.id,
        )
        assert decision.status == "decision_persisted", decision.blocked_reasons
        assert decision.decision is not None
        assert decision.decision_message is not None
        assert decision.decision.decision_type == "ESCALATE_TO_HUMAN"
        assert decision.decision.decision_reason == "empty_diff"

        terminal = ProjectDirectorBoundedReworkTerminalEscalationService(
            message_repository=message_repository,
            convergence_service=convergence,
        ).prepare_bounded_rework_terminal_escalation(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_convergence_decision_message_id=decision.decision_message.id,
        )
        assert terminal.status == "package_prepared", terminal.blocked_reasons
        assert terminal.package is not None
        assert terminal.package.decision_reason == "empty_diff"

        closure = ProjectDirectorBoundedReworkAttemptLifecycleClosureService(
            message_repository=message_repository,
            task_repository=(
                package_context.package_service._dispatch_intent_service._task_repository
            ),
            run_repository=(
                package_context.package_service._dispatch_consumption_service._run_repository
            ),
            dispatch_consumption_service=(
                package_context.package_service._dispatch_consumption_service
            ),
            convergence_service=convergence,
        ).close_bounded_rework_attempt_lifecycle(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_convergence_decision_message_id=decision.decision_message.id,
        )
        assert closure.status == "closure_persisted", closure.blocked_reasons
        assert closure.closure is not None
        assert closure.closure.closure_kind == "terminal_human_escalation"
        assert closure.task is not None and closure.task.status == TaskStatus.WAITING_HUMAN
        assert closure.task.human_status == TaskHumanStatus.REQUESTED
        assert closure.run is not None and closure.run.status == RunStatus.FAILED
        assert executor.call_count == 1
    finally:
        context.close()
