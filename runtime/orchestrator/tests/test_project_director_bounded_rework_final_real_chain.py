"""P25 final-loop coverage over the persisted attempt-zero real chain."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.external_executors.project_director_bounded_rework_executor import (
    ProjectDirectorBoundedReworkExecutorRequest,
    ProjectDirectorBoundedReworkExecutorResult,
)
from app.services.project_director_bounded_rework_attempt_reservation_service import (
    ProjectDirectorBoundedReworkAttemptReservationService,
)
from app.services.project_director_bounded_rework_candidate_diff_service import (
    ProjectDirectorBoundedReworkCandidateDiffService,
)
from app.services.project_director_bounded_rework_convergence_service import (
    ProjectDirectorBoundedReworkConvergenceService,
)
from app.services.project_director_bounded_rework_invocation_claim_service import (
    ProjectDirectorBoundedReworkInvocationClaimService,
)
from app.services.project_director_bounded_rework_invocation_outcome_service import (
    ProjectDirectorBoundedReworkInvocationOutcomeService,
)
from app.services.project_director_bounded_rework_package_preparation_service import (
    ProjectDirectorBoundedReworkPackagePreparationService,
)
from app.services.project_director_bounded_rework_post_review_orchestration_service import (
    ProjectDirectorBoundedReworkPostReviewOrchestrationService,
)
from app.services.project_director_bounded_rework_review_execution_service import (
    ProjectDirectorBoundedReworkReviewExecutionService,
)
from app.services.project_director_bounded_rework_review_reentry_preflight_service import (
    ProjectDirectorBoundedReworkReviewReentryPreflightService,
)
from app.services.project_director_bounded_rework_attempt_lifecycle_closure_service import (
    ProjectDirectorBoundedReworkAttemptLifecycleClosureService,
)
from app.services.project_director_bounded_rework_terminal_escalation_service import (
    ProjectDirectorBoundedReworkTerminalEscalationService,
)
from app.services.project_director_protected_transition_dispatch_consumption_preflight_service import (
    ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService,
)
from app.services.project_director_protected_transition_dispatch_consumption_service import (
    ProjectDirectorProtectedTransitionDispatchConsumptionService,
)
from app.services.project_director_protected_transition_dispatch_intent_service import (
    ProjectDirectorProtectedTransitionDispatchIntentService,
)
from app.services.project_director_protected_transition_evidence_freshness_service import (
    ProjectDirectorProtectedTransitionEvidenceFreshnessService,
)
from app.services.project_director_post_review_source_evidence_resolver import (
    ProjectDirectorPostReviewSourceEvidenceResolver,
)
from app.services.project_director_sandbox_candidate_diff_service import (
    ProjectDirectorSandboxCandidateDiffService,
)
from tests.p25_post_review_real_chain_test_support import _build_post_review_services
from tests.p25_convergence_next_attempt_real_chain_test_support import (
    CHANGES_REQUIRED_REVIEW_OUTPUT,
    build_real_p25_attempt_zero_next_attempt_convergence_context,
)


@dataclass(slots=True)
class _AttemptOneExecutor:
    session: object
    call_count: int = 0

    def execute_bounded_rework(
        self,
        request: ProjectDirectorBoundedReworkExecutorRequest,
    ) -> ProjectDirectorBoundedReworkExecutorResult:
        assert self.session.in_transaction() is False
        assert request.rework_attempt_index == 1
        self.call_count += 1
        (Path(request.workspace_path) / "src/example.py").write_text(
            "value = 'candidate'\n# bounded rework attempt 1\n",
            encoding="utf-8",
        )
        return ProjectDirectorBoundedReworkExecutorResult(
            result_status="returned",
            declared_changed_paths=("src/example.py",),
            safe_summary="Applied the second bounded correction.",
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


@dataclass(slots=True)
class _AttemptTwoExecutor:
    session: object
    call_count: int = 0

    def execute_bounded_rework(
        self,
        request: ProjectDirectorBoundedReworkExecutorRequest,
    ) -> ProjectDirectorBoundedReworkExecutorResult:
        assert self.session.in_transaction() is False
        assert request.rework_attempt_index == 2
        self.call_count += 1
        (Path(request.workspace_path) / "src/example.py").write_text(
            "value = 'candidate'\n# bounded rework attempt 2\n",
            encoding="utf-8",
        )
        return ProjectDirectorBoundedReworkExecutorResult(
            result_status="returned",
            declared_changed_paths=("src/example.py",),
            safe_summary="Applied the final bounded correction.",
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


@dataclass(slots=True)
class _AttemptOneNoChangeExecutor:
    session: object
    call_count: int = 0

    def execute_bounded_rework(
        self,
        request: ProjectDirectorBoundedReworkExecutorRequest,
    ) -> ProjectDirectorBoundedReworkExecutorResult:
        assert self.session.in_transaction() is False
        assert request.rework_attempt_index == 1
        self.call_count += 1
        return ProjectDirectorBoundedReworkExecutorResult(
            result_status="returned",
            declared_changed_paths=(),
            safe_summary="The prior candidate remains the bounded state.",
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


def _attempt_one_services(
    context,
    *,
    source_convergence_service=None,
    source_review_execution_service=None,
):
    package_context = (
        context.review_execution_context.review_preflight_context.candidate_context
        .outcome_context.claim_context.package_context
    )
    attempt_zero_package_service = package_context.package_service
    attempt_zero_intent_service = attempt_zero_package_service._dispatch_intent_service
    attempt_zero_consumption_service = (
        attempt_zero_package_service._dispatch_consumption_service
    )
    attempt_zero_preflight_service = attempt_zero_consumption_service._preflight_service
    source_convergence_service = (
        source_convergence_service or context.convergence_service
    )
    source_review_execution_service = (
        source_review_execution_service
        or context.review_execution_context.review_execution_service
    )

    intent_service = ProjectDirectorProtectedTransitionDispatchIntentService(
        session_repository=attempt_zero_intent_service._session_repository,
        message_repository=attempt_zero_intent_service._message_repository,
        task_repository=attempt_zero_intent_service._task_repository,
        bounded_rework_convergence_service=source_convergence_service,
    )
    freshness_service = ProjectDirectorProtectedTransitionEvidenceFreshnessService(
        session_repository=attempt_zero_preflight_service._session_repository,
        message_repository=attempt_zero_preflight_service._message_repository,
        task_repository=attempt_zero_preflight_service._task_repository,
        review_handoff_service=attempt_zero_preflight_service._freshness_service._review_handoff_service,
        candidate_diff_service=attempt_zero_preflight_service._freshness_service._candidate_diff_service,
        source_evidence_resolver=ProjectDirectorPostReviewSourceEvidenceResolver(
            review_execution_service=source_review_execution_service
        ),
    )
    preflight_service = ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService(
        session_repository=attempt_zero_preflight_service._session_repository,
        message_repository=attempt_zero_preflight_service._message_repository,
        task_repository=attempt_zero_preflight_service._task_repository,
        dispatch_intent_service=intent_service,
        freshness_service=freshness_service,
        task_readiness_service=attempt_zero_preflight_service._task_readiness_service,
        task_state_machine_service=attempt_zero_preflight_service._task_state_machine_service,
        budget_guard_service=attempt_zero_preflight_service._budget_guard_service,
    )
    consumption_service = ProjectDirectorProtectedTransitionDispatchConsumptionService(
        session_repository=attempt_zero_consumption_service._session_repository,
        message_repository=attempt_zero_consumption_service._message_repository,
        task_repository=attempt_zero_consumption_service._task_repository,
        run_repository=attempt_zero_consumption_service._run_repository,
        preflight_service=preflight_service,
        task_readiness_service=attempt_zero_consumption_service._task_readiness_service,
        task_state_machine_service=attempt_zero_consumption_service._task_state_machine_service,
        task_router_service=attempt_zero_consumption_service._task_router_service,
        budget_guard_service=attempt_zero_consumption_service._budget_guard_service,
    )
    package_service = ProjectDirectorBoundedReworkPackagePreparationService(
        message_repository=attempt_zero_package_service._message_repository,
        dispatch_consumption_service=consumption_service,
        dispatch_intent_service=intent_service,
        evidence_resolver=attempt_zero_package_service._evidence_resolver,
    )
    attempt_zero_package_service._evidence_resolver.configure_p25_h_review_execution_service(
        source_review_execution_service,
        freshness_service=freshness_service,
        dispatch_intent_service=intent_service,
    )
    return intent_service, preflight_service, consumption_service, package_service


def _close_attempt(context, decision):
    package_context = (
        context.review_execution_context.review_preflight_context.candidate_context
        .outcome_context.claim_context.package_context
    )
    return ProjectDirectorBoundedReworkAttemptLifecycleClosureService(
        message_repository=context.message_repository,
        task_repository=package_context.package_service._dispatch_intent_service._task_repository,
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


def test_real_attempt_one_package_uses_current_p25_review_evidence(tmp_path):
    context = build_real_p25_attempt_zero_next_attempt_convergence_context(tmp_path)
    try:
        decision = context.convergence_service.decide_bounded_rework_convergence(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=context.candidate_diff_message_id,
        )
        assert decision.status == "decision_persisted", decision.blocked_reasons
        assert decision.decision is not None
        assert decision.decision_message is not None
        assert decision.decision.next_rework_attempt_index == 1
        closure = _close_attempt(context, decision)
        assert closure.status == "closure_persisted", closure.blocked_reasons

        intent_service, preflight_service, consumption_service, package_service = (
            _attempt_one_services(context)
        )
        intent = intent_service.prepare_protected_transition_dispatch_intent(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_message_id=context.h_c_result.p22_summary_message.id,
        )
        assert intent.result.intent_status == "prepared", intent.result.blocked_reasons
        assert intent.result.rework_attempt_index == 1

        preflight = preflight_service.prepare_protected_transition_dispatch_consumption_preflight(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_message_id=intent.message.id,
        )
        assert preflight.result.preflight_status == "ready", preflight.result.blocked_reasons

        consumption = consumption_service.consume_protected_transition_dispatch_preflight(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_message_id=preflight.message.id,
        )
        assert consumption.result.consumption_status == "reserved_for_worker_start"
        assert consumption.result.rework_attempt_index == 1
        assert consumption.result.run_id != closure.run.id

        authority = package_service._revalidate_authority(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_consumption_message_id=consumption.message.id,
        )
        source_message = context.message_repository.get_by_id(
            authority.authority.source_review_message_id
        )
        assert package_service._evidence_resolver._review_source_kind(source_message) == "p25_h"
        evidence = package_service._evidence_resolver.resolve_bounded_rework_evidence_snapshot(
            session_id=context.session_id,
            project_id=authority.authority.project_id,
            source_task_id=context.task_id,
            source_run_id=authority.authority.source_run_id,
            source_review_message_id=authority.authority.source_review_message_id,
            source_review_fingerprint=authority.authority.source_review_fingerprint,
            source_review_semantic_fingerprint=(
                authority.authority.source_review_semantic_fingerprint
            ),
            source_freshness_message_id=authority.source_freshness_message_id,
            source_diff_message_id=authority.source_diff_message_id,
        )
        assert evidence.status == "resolved", evidence.blocked_reasons
        replayed_evidence = package_service._evidence_resolver.revalidate_bounded_rework_evidence_snapshot(
            evidence.snapshot
        )
        assert replayed_evidence.status == "resolved", replayed_evidence.blocked_reasons
        replayed_authority = package_service._revalidate_authority(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_consumption_message_id=consumption.message.id,
        )
        assert replayed_authority == authority

        history = package_service._load_history(context.session_id)
        assert [
            item.rework_attempt_index for _, item in history.packages
        ] == [0]
        lineage = package_service._attempt_lineage(
            history=history,
            authority_context=authority,
            evidence=evidence.snapshot,
        )
        assert lineage.rework_attempt_index == 1
        assert lineage.previous_rework_attempt_index == 0
        assert lineage.previous_candidate_diff_sha256 == (
            history.packages[0][1].source_candidate_diff_sha256
        )
        assert lineage.previous_review_semantic_fingerprint == (
            history.packages[0][1].authority.source_review_semantic_fingerprint
        )
        context.session.rollback()

        package = package_service.prepare_bounded_rework_instruction_package(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_p23_dispatch_consumption_message_id=consumption.message.id,
        )
        assert package.status == "package_prepared", package.blocked_reasons
        assert package.package.rework_attempt_index == 1
        assert package.package.authority.source_review_message_id == (
            context.h_b_result.review_outcome_message.id
        )
    finally:
        context.close()


def _run_attempt_one_and_close(
    tmp_path,
    *,
    review_output: str,
    expected_decision_type: str,
    expected_decision_reason: str | None = None,
    keep_context: bool = False,
    attempt_executor_type=_AttemptOneExecutor,
    expected_non_convergence_reason: str | None = None,
):
    context = build_real_p25_attempt_zero_next_attempt_convergence_context(tmp_path)
    try:
        decision_zero = context.convergence_service.decide_bounded_rework_convergence(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=context.candidate_diff_message_id,
        )
        assert decision_zero.decision_message is not None
        assert _close_attempt(context, decision_zero).status == "closure_persisted"

        intent_service, preflight_service, consumption_service, package_service = (
            _attempt_one_services(context)
        )
        intent = intent_service.prepare_protected_transition_dispatch_intent(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_message_id=context.h_c_result.p22_summary_message.id,
        )
        assert intent.message is not None
        preflight = preflight_service.prepare_protected_transition_dispatch_consumption_preflight(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_message_id=intent.message.id,
        )
        assert preflight.message is not None, preflight.result.blocked_reasons
        consumption = consumption_service.consume_protected_transition_dispatch_preflight(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_message_id=preflight.message.id,
        )
        assert consumption.message is not None
        assert consumption.result.run_id != decision_zero.decision.authority.source_run_id

        package = package_service.prepare_bounded_rework_instruction_package(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_p23_dispatch_consumption_message_id=consumption.message.id,
        )
        assert package.status == "package_prepared", package.blocked_reasons
        assert package.message is not None

        package_context = (
            context.review_execution_context.review_preflight_context.candidate_context
            .outcome_context.claim_context.package_context
        )
        attempt_zero_claim_service = (
            context.review_execution_context.review_preflight_context.candidate_context
            .outcome_context.claim_context.claim_service
        )
        attempt_zero_reservation_service = (
            attempt_zero_claim_service._attempt_reservation_service
        )
        reservation_service = ProjectDirectorBoundedReworkAttemptReservationService(
            message_repository=context.message_repository,
            task_repository=attempt_zero_reservation_service._task_repository,
            run_repository=attempt_zero_reservation_service._run_repository,
            package_preparation_service=package_service,
            worker_start_reservation_service=(
                attempt_zero_reservation_service._worker_start_reservation_service
            ),
            worker_invocation_service=(
                attempt_zero_reservation_service._worker_invocation_service
            ),
        )
        reservation = reservation_service.reserve_bounded_rework_attempt(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_package_message_id=package.message.id,
        )
        assert reservation.status == "reservation_reserved", reservation.blocked_reasons
        assert reservation.message is not None

        claim_service = ProjectDirectorBoundedReworkInvocationClaimService(
            message_repository=context.message_repository,
            attempt_reservation_service=reservation_service,
        )
        executor = attempt_executor_type(context.session)
        outcome_service = ProjectDirectorBoundedReworkInvocationOutcomeService(
            message_repository=context.message_repository,
            claim_service=claim_service,
            bounded_rework_executor=executor,
        )
        outcome = outcome_service.execute_bounded_rework_from_reservation(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_reservation_message_id=reservation.message.id,
        )
        assert outcome.status == "outcome_recorded", outcome.blocked_reasons
        assert outcome.outcome_message is not None

        candidate_service = ProjectDirectorBoundedReworkCandidateDiffService(
            message_repository=context.message_repository,
            claim_service=claim_service,
            candidate_diff_service=ProjectDirectorSandboxCandidateDiffService(),
        )
        candidate = candidate_service.regenerate_candidate_manifest_and_diff(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_outcome_message_id=outcome.outcome_message.id,
        )
        if expected_non_convergence_reason is not None:
            assert candidate.status == "candidate_diff_non_convergence", candidate.blocked_reasons
            assert candidate.candidate_diff is not None
            assert candidate.candidate_diff.non_convergence_reason == expected_non_convergence_reason
            assert candidate.diff_message is not None
            convergence_service = ProjectDirectorBoundedReworkConvergenceService(
                message_repository=context.message_repository,
                candidate_diff_service=candidate_service,
                review_execution_service=context.review_execution_context.review_execution_service,
                post_review_automation_service=context.convergence_service._post_review_automation_service,
            )
            decision_one = convergence_service.decide_bounded_rework_convergence(
                session_id=context.session_id,
                source_task_id=context.task_id,
                source_candidate_diff_message_id=candidate.diff_message.id,
            )
            assert decision_one.status == "decision_persisted", decision_one.blocked_reasons
            assert decision_one.decision is not None
            assert decision_one.decision.decision_type == expected_decision_type
            assert decision_one.decision.decision_reason == expected_decision_reason
            assert decision_one.decision_message is not None
            terminal = ProjectDirectorBoundedReworkTerminalEscalationService(
                message_repository=context.message_repository,
                convergence_service=convergence_service,
            ).prepare_bounded_rework_terminal_escalation(
                session_id=context.session_id,
                source_task_id=context.task_id,
                source_convergence_decision_message_id=decision_one.decision_message.id,
            )
            assert terminal.status == "package_prepared", terminal.blocked_reasons
            closure = ProjectDirectorBoundedReworkAttemptLifecycleClosureService(
                message_repository=context.message_repository,
                task_repository=attempt_zero_reservation_service._task_repository,
                run_repository=attempt_zero_reservation_service._run_repository,
                dispatch_consumption_service=consumption_service,
                convergence_service=convergence_service,
            ).close_bounded_rework_attempt_lifecycle(
                session_id=context.session_id,
                source_task_id=context.task_id,
                source_convergence_decision_message_id=decision_one.decision_message.id,
            )
            assert closure.status == "closure_persisted", closure.blocked_reasons
            assert closure.task is not None and closure.task.status.value == "waiting_human"
            assert closure.run is not None and closure.run.status.value == "failed"
            assert executor.call_count == 1
            return None
        assert candidate.status == "candidate_diff_generated", candidate.blocked_reasons
        assert candidate.diff_message is not None

        review_preflight_service = ProjectDirectorBoundedReworkReviewReentryPreflightService(
            message_repository=context.message_repository,
            candidate_diff_service=candidate_service,
        )
        review_preflight = review_preflight_service.prepare_review_reentry_preflight_and_claim(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=candidate.diff_message.id,
        )
        assert (
            review_preflight.status == "review_preflight_claimed"
        ), review_preflight.blocked_reasons
        assert review_preflight.review_claim_message is not None

        context.review_execution_context.transport.raw_output_text = review_output
        review_execution_service = ProjectDirectorBoundedReworkReviewExecutionService(
            message_repository=context.message_repository,
            preflight_service=review_preflight_service,
            transport_resolver_factory=context.review_execution_context.resolver_factory,
        )
        review_outcome = review_execution_service.execute_claimed_readonly_review(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_review_claim_message_id=review_preflight.review_claim_message.id,
        )
        assert review_outcome.status == "review_outcome_persisted", review_outcome.blocked_reasons
        assert review_outcome.review_outcome_message is not None

        disposition_service, post_review_automation_service = _build_post_review_services(
            type(
                "AttemptOnePostReviewContext",
                (),
                {
                    "session": context.session,
                    "message_repository": context.message_repository,
                    "review_execution_service": review_execution_service,
                },
            )()
        )
        orchestration_service = ProjectDirectorBoundedReworkPostReviewOrchestrationService(
            review_execution_service=review_execution_service,
            disposition_service=disposition_service,
            post_review_automation_service=post_review_automation_service,
        )
        post_review = orchestration_service.orchestrate_fresh_post_review(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_review_outcome_message_id=review_outcome.review_outcome_message.id,
        )
        assert post_review.status == "post_review_orchestrated", post_review.blocked_reasons
        assert post_review.p22_summary_message is not None

        convergence_service = ProjectDirectorBoundedReworkConvergenceService(
            message_repository=context.message_repository,
            candidate_diff_service=candidate_service,
            review_execution_service=review_execution_service,
            post_review_automation_service=post_review_automation_service,
        )
        decision_one = convergence_service.decide_bounded_rework_convergence(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=candidate.diff_message.id,
        )
        assert decision_one.status == "decision_persisted", decision_one.blocked_reasons
        assert decision_one.decision is not None
        assert decision_one.decision.decision_type == expected_decision_type
        assert decision_one.decision.decision_reason == expected_decision_reason
        assert decision_one.decision_message is not None

        revalidated_intent = (
            intent_service.revalidate_persisted_only_protected_transition_dispatch_intent(
                session_id=context.session_id,
                source_task_id=context.task_id,
                source_intent_message_id=intent.message.id,
            )
        )
        assert not revalidated_intent.blocked_reasons, (
            revalidated_intent.blocked_reasons
        )
        revalidated_consumption = (
            consumption_service.revalidate_persisted_protected_transition_dispatch_consumption(
                session_id=context.session_id,
                source_task_id=context.task_id,
                source_consumption_message_id=consumption.message.id,
            )
        )
        assert not revalidated_consumption.blocked_reasons, (
            revalidated_consumption.blocked_reasons
        )
        context.session.rollback()

        terminal = None
        if expected_decision_type == "ESCALATE_TO_HUMAN":
            terminal = ProjectDirectorBoundedReworkTerminalEscalationService(
                message_repository=context.message_repository,
                convergence_service=convergence_service,
            ).prepare_bounded_rework_terminal_escalation(
                session_id=context.session_id,
                source_task_id=context.task_id,
                source_convergence_decision_message_id=decision_one.decision_message.id,
            )
            assert terminal.status in {
                "package_prepared",
                "existing_human_package_reused",
            }, terminal.blocked_reasons
            if terminal.package is not None:
                assert terminal.package.decision_reason == expected_decision_reason

        closure = ProjectDirectorBoundedReworkAttemptLifecycleClosureService(
            message_repository=context.message_repository,
            task_repository=attempt_zero_reservation_service._task_repository,
            run_repository=attempt_zero_reservation_service._run_repository,
            dispatch_consumption_service=consumption_service,
            convergence_service=convergence_service,
        ).close_bounded_rework_attempt_lifecycle(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_convergence_decision_message_id=decision_one.decision_message.id,
        )
        assert closure.status == "closure_persisted", closure.blocked_reasons
        if expected_decision_type == "CONVERGED":
            assert closure.task is not None and closure.task.status.value == "completed"
            assert closure.run is not None and closure.run.status.value == "succeeded"
        elif expected_decision_type == "NEXT_ATTEMPT_ELIGIBLE":
            assert closure.task is not None and closure.task.status.value == "failed"
            assert closure.run is not None and closure.run.status.value == "failed"
        else:
            assert closure.task is not None and closure.task.status.value == "waiting_human"
            assert closure.run is not None and closure.run.status.value == "failed"
        assert executor.call_count == 1
        if keep_context:
            return (
                context,
                post_review,
                review_execution_service,
                convergence_service,
            )
    finally:
        if not keep_context:
            context.close()


def test_real_attempt_one_converges_and_closes_the_retry_run(tmp_path):
    _run_attempt_one_and_close(
        tmp_path,
        review_output="""{
          "review_status": "reviewed",
          "verdict": "no_blocking_findings",
          "risk_level": "low",
          "summary": "The second bounded correction converged.",
          "findings": [],
          "recommended_next_step": "Close the bounded attempt."
        }""",
        expected_decision_type="CONVERGED",
        expected_decision_reason="review_converged",
    )


def test_real_attempt_one_repeated_review_semantic_escalates_and_closes(tmp_path):
    _run_attempt_one_and_close(
        tmp_path,
        review_output=CHANGES_REQUIRED_REVIEW_OUTPUT,
        expected_decision_type="ESCALATE_TO_HUMAN",
        expected_decision_reason="repeated_review_semantic_fingerprint",
    )


def test_real_attempt_one_repeated_canonical_findings_escalates_and_closes(tmp_path):
    _run_attempt_one_and_close(
        tmp_path,
        review_output="""{
          "review_status": "reviewed",
          "verdict": "changes_required",
          "risk_level": "medium",
          "summary": "The candidate changed, but the same retry guard remains absent.",
          "findings": [
            {
              "finding_id": "same-finding-new-id",
              "severity": "medium",
              "title": "Missing idempotent retry guard",
              "summary": "The wording changed without resolving the guard.",
              "evidence_paths": ["src/example.py"],
              "recommended_action": "Add an explicit guard that prevents the same bounded retry from being scheduled twice."
            }
          ],
          "recommended_next_step": "Apply the bounded correction and submit the next candidate for review."
        }""",
        expected_decision_type="ESCALATE_TO_HUMAN",
        expected_decision_reason="repeated_canonical_blocking_findings",
    )


def test_real_attempt_one_high_review_risk_escalates_and_closes(tmp_path):
    _run_attempt_one_and_close(
        tmp_path,
        review_output="""{
          "review_status": "reviewed",
          "verdict": "changes_required",
          "risk_level": "high",
          "summary": "The candidate can bypass a required authorization boundary.",
          "findings": [
            {
              "finding_id": "authorization-boundary-bypass",
              "severity": "high",
              "title": "Authorization boundary bypass",
              "summary": "The candidate can bypass a required authorization boundary.",
              "evidence_paths": ["src/example.py"],
              "recommended_action": "Restore the authorization boundary before another automated attempt."
            }
          ],
          "recommended_next_step": "Escalate the authorization risk to a human reviewer."
        }""",
        expected_decision_type="ESCALATE_TO_HUMAN",
        expected_decision_reason="high_review_risk",
    )


def test_real_attempt_one_inherited_candidate_escalates_as_unchanged_diff(tmp_path):
    _run_attempt_one_and_close(
        tmp_path,
        review_output="",
        expected_decision_type="ESCALATE_TO_HUMAN",
        expected_decision_reason="unchanged_diff",
        attempt_executor_type=_AttemptOneNoChangeExecutor,
        expected_non_convergence_reason="unchanged_diff",
    )


def test_real_attempt_two_package_follows_attempt_one_authority(tmp_path):
    result = _run_attempt_one_and_close(
        tmp_path,
        review_output="""{
          "review_status": "reviewed",
          "verdict": "changes_required",
          "risk_level": "medium",
          "summary": "The first correction still needs a distinct recovery guard.",
          "findings": [
            {
              "finding_id": "missing-recovery-guard",
              "severity": "medium",
              "title": "Missing recovery guard",
              "summary": "The bounded correction needs a recovery guard.",
              "evidence_paths": ["src/example.py"],
              "recommended_action": "Add the recovery guard before retrying."
            }
          ],
          "recommended_next_step": "Apply the bounded correction and submit the next candidate for review."
        }""",
        expected_decision_type="NEXT_ATTEMPT_ELIGIBLE",
        expected_decision_reason="changed_blocking_findings",
        keep_context=True,
    )
    assert result is not None
    context, post_review_one, review_execution_one, convergence_one = result
    try:
        intent_service, preflight_service, consumption_service, package_service = (
            _attempt_one_services(
                context,
                source_convergence_service=convergence_one,
                source_review_execution_service=review_execution_one,
            )
        )
        intent = intent_service.prepare_protected_transition_dispatch_intent(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_message_id=post_review_one.p22_summary_message.id,
        )
        assert intent.message is not None
        assert intent.result.rework_attempt_index == 2
        preflight = preflight_service.prepare_protected_transition_dispatch_consumption_preflight(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_message_id=intent.message.id,
        )
        assert preflight.message is not None, preflight.result.blocked_reasons
        consumption = consumption_service.consume_protected_transition_dispatch_preflight(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_message_id=preflight.message.id,
        )
        assert consumption.message is not None
        assert consumption.result.rework_attempt_index == 2
        package = package_service.prepare_bounded_rework_instruction_package(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_p23_dispatch_consumption_message_id=consumption.message.id,
        )
        assert package.status == "package_prepared", package.blocked_reasons
        assert package.package is not None
        assert package.package.rework_attempt_index == 2

        package_context = (
            context.review_execution_context.review_preflight_context.candidate_context
            .outcome_context.claim_context.package_context
        )
        attempt_zero_claim_service = (
            context.review_execution_context.review_preflight_context.candidate_context
            .outcome_context.claim_context.claim_service
        )
        attempt_zero_reservation_service = (
            attempt_zero_claim_service._attempt_reservation_service
        )
        reservation_service = ProjectDirectorBoundedReworkAttemptReservationService(
            message_repository=context.message_repository,
            task_repository=attempt_zero_reservation_service._task_repository,
            run_repository=attempt_zero_reservation_service._run_repository,
            package_preparation_service=package_service,
            worker_start_reservation_service=(
                attempt_zero_reservation_service._worker_start_reservation_service
            ),
            worker_invocation_service=(
                attempt_zero_reservation_service._worker_invocation_service
            ),
        )
        reservation = reservation_service.reserve_bounded_rework_attempt(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_package_message_id=package.message.id,
        )
        assert reservation.status == "reservation_reserved", reservation.blocked_reasons
        assert reservation.message is not None
        claim_service = ProjectDirectorBoundedReworkInvocationClaimService(
            message_repository=context.message_repository,
            attempt_reservation_service=reservation_service,
        )
        executor = _AttemptTwoExecutor(context.session)
        outcome_service = ProjectDirectorBoundedReworkInvocationOutcomeService(
            message_repository=context.message_repository,
            claim_service=claim_service,
            bounded_rework_executor=executor,
        )
        outcome = outcome_service.execute_bounded_rework_from_reservation(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_reservation_message_id=reservation.message.id,
        )
        assert outcome.status == "outcome_recorded", outcome.blocked_reasons
        assert outcome.outcome_message is not None
        candidate_service = ProjectDirectorBoundedReworkCandidateDiffService(
            message_repository=context.message_repository,
            claim_service=claim_service,
            candidate_diff_service=ProjectDirectorSandboxCandidateDiffService(),
        )
        candidate = candidate_service.regenerate_candidate_manifest_and_diff(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_outcome_message_id=outcome.outcome_message.id,
        )
        assert candidate.status == "candidate_diff_generated", candidate.blocked_reasons
        assert candidate.diff_message is not None
        review_preflight_service = ProjectDirectorBoundedReworkReviewReentryPreflightService(
            message_repository=context.message_repository,
            candidate_diff_service=candidate_service,
        )
        review_preflight = review_preflight_service.prepare_review_reentry_preflight_and_claim(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=candidate.diff_message.id,
        )
        assert review_preflight.status == "review_preflight_claimed", review_preflight.blocked_reasons
        assert review_preflight.review_claim_message is not None
        context.review_execution_context.transport.raw_output_text = """{
          "review_status": "reviewed",
          "verdict": "changes_required",
          "risk_level": "medium",
          "summary": "The final correction still needs a distinct audit marker.",
          "findings": [
            {
              "finding_id": "missing-audit-marker",
              "severity": "medium",
              "title": "Missing audit marker",
              "summary": "The final bounded correction needs an audit marker.",
              "evidence_paths": ["src/example.py"],
              "recommended_action": "Add the audit marker before any further work."
            }
          ],
          "recommended_next_step": "Escalate after the bounded attempt limit is exhausted."
        }"""
        review_execution_service = ProjectDirectorBoundedReworkReviewExecutionService(
            message_repository=context.message_repository,
            preflight_service=review_preflight_service,
            transport_resolver_factory=context.review_execution_context.resolver_factory,
        )
        review_outcome = review_execution_service.execute_claimed_readonly_review(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_review_claim_message_id=review_preflight.review_claim_message.id,
        )
        assert review_outcome.status == "review_outcome_persisted", review_outcome.blocked_reasons
        assert review_outcome.review_outcome_message is not None
        disposition_service, post_review_automation_service = _build_post_review_services(
            type(
                "AttemptTwoPostReviewContext",
                (),
                {
                    "session": context.session,
                    "message_repository": context.message_repository,
                    "review_execution_service": review_execution_service,
                },
            )()
        )
        post_review = ProjectDirectorBoundedReworkPostReviewOrchestrationService(
            review_execution_service=review_execution_service,
            disposition_service=disposition_service,
            post_review_automation_service=post_review_automation_service,
        ).orchestrate_fresh_post_review(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_review_outcome_message_id=review_outcome.review_outcome_message.id,
        )
        assert post_review.status == "post_review_orchestrated", post_review.blocked_reasons
        convergence_service = ProjectDirectorBoundedReworkConvergenceService(
            message_repository=context.message_repository,
            candidate_diff_service=candidate_service,
            review_execution_service=review_execution_service,
            post_review_automation_service=post_review_automation_service,
        )
        decision = convergence_service.decide_bounded_rework_convergence(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_candidate_diff_message_id=candidate.diff_message.id,
        )
        assert decision.status == "decision_persisted", decision.blocked_reasons
        assert decision.decision is not None
        assert decision.decision.decision_type == "ESCALATE_TO_HUMAN"
        assert decision.decision.decision_reason == "attempt_limit_exhausted"
        assert decision.decision.next_rework_attempt_index is None
        terminal = ProjectDirectorBoundedReworkTerminalEscalationService(
            message_repository=context.message_repository,
            convergence_service=convergence_service,
        ).prepare_bounded_rework_terminal_escalation(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_convergence_decision_message_id=decision.decision_message.id,
        )
        assert terminal.status == "package_prepared", terminal.blocked_reasons
        closure = ProjectDirectorBoundedReworkAttemptLifecycleClosureService(
            message_repository=context.message_repository,
            task_repository=attempt_zero_reservation_service._task_repository,
            run_repository=attempt_zero_reservation_service._run_repository,
            dispatch_consumption_service=consumption_service,
            convergence_service=convergence_service,
        ).close_bounded_rework_attempt_lifecycle(
            session_id=context.session_id,
            source_task_id=context.task_id,
            source_convergence_decision_message_id=decision.decision_message.id,
        )
        assert closure.status == "closure_persisted", closure.blocked_reasons
        assert closure.task is not None and closure.task.status.value == "waiting_human"
        assert closure.run is not None and closure.run.status.value == "failed"
        assert executor.call_count == 1
        history = intent_service._scan_intent_history(
            session_id=context.session_id,
            source_task_id=context.task_id,
            project_id=package.package.authority.project_id,
        )
        assert sorted(
            item[0].rework_attempt_index
            for item in history.valid_intents
            if item[0].dispatch_kind == "auto_rework"
        ) == [0, 1, 2]
    finally:
        context.close()
