"""Real P25-I next-attempt support composed from the P25-B through P25-H-C chain."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from app.services.project_director_bounded_rework_convergence_service import (
    ProjectDirectorBoundedReworkConvergenceService,
)
from app.services.project_director_bounded_rework_post_review_orchestration_service import (
    ProjectDirectorBoundedReworkPostReviewOrchestrationService,
)
from tests.p25_post_review_real_chain_test_support import _build_post_review_services
from tests.p25_review_execution_real_chain_test_support import (
    FreshP25ReviewExecutionServices,
    RealP25AttemptZeroReviewExecutionContext,
    build_fresh_review_execution_services,
    build_real_p25_attempt_zero_review_execution_context,
)


CHANGES_REQUIRED_REVIEW_OUTPUT = """{
  "review_status": "reviewed",
  "verdict": "changes_required",
  "risk_level": "medium",
  "summary": "The candidate improves the target but still lacks an idempotent retry guard.",
  "findings": [
    {
      "finding_id": "missing-idempotent-retry-guard",
      "severity": "medium",
      "title": "Missing idempotent retry guard",
      "summary": "The bounded retry can be scheduled more than once.",
      "evidence_paths": ["src/example.py"],
      "recommended_action": "Add an explicit guard that prevents the same bounded retry from being scheduled twice."
    }
  ],
  "recommended_next_step": "Apply the bounded correction and submit the next candidate for review."
}"""


@dataclass(slots=True)
class RealP25AttemptZeroNextAttemptConvergenceContext:
    review_execution_context: RealP25AttemptZeroReviewExecutionContext
    h_b_result: object
    h_c_result: object
    convergence_service: ProjectDirectorBoundedReworkConvergenceService

    @property
    def session(self):
        return self.review_execution_context.session

    @property
    def session_id(self):
        return self.review_execution_context.session_id

    @property
    def task_id(self):
        return self.review_execution_context.task_id

    @property
    def message_repository(self):
        return self.review_execution_context.message_repository

    @property
    def candidate_diff_message_id(self):
        return (
            self.review_execution_context.review_preflight_context.candidate_diff_result
            .diff_message.id
        )

    @property
    def transport(self):
        return self.review_execution_context.transport

    @property
    def executor(self):
        return (
            self.review_execution_context.review_preflight_context.candidate_context
            .outcome_context.executor
        )

    def close(self) -> None:
        self.review_execution_context.close()


@dataclass(slots=True)
class FreshP25NextAttemptConvergenceServices:
    review_execution_services: FreshP25ReviewExecutionServices
    orchestration_service: ProjectDirectorBoundedReworkPostReviewOrchestrationService
    convergence_service: ProjectDirectorBoundedReworkConvergenceService

    @property
    def session(self):
        return self.review_execution_services.session

    def close(self) -> None:
        self.review_execution_services.close()


def build_real_p25_attempt_zero_next_attempt_convergence_context(tmp_path):
    """Create P25-B through P25-H-C with one current medium review finding."""

    review_execution_context = build_real_p25_attempt_zero_review_execution_context(
        tmp_path
    )
    review_execution_context.transport.raw_output_text = CHANGES_REQUIRED_REVIEW_OUTPUT
    h_b_result = review_execution_context.review_execution_service.execute_claimed_readonly_review(
        session_id=review_execution_context.session_id,
        source_task_id=review_execution_context.task_id,
        source_review_claim_message_id=(
            review_execution_context.h_a_result.review_claim_message.id
        ),
    )
    assert h_b_result.status == "review_outcome_persisted", h_b_result.blocked_reasons
    assert h_b_result.review_outcome is not None
    assert h_b_result.review_outcome.outcome_status == "validated_output"
    assert h_b_result.review_outcome.adapter_result is not None
    assert h_b_result.review_outcome.adapter_result.verdict == "changes_required"
    assert h_b_result.review_outcome.adapter_result.risk_level == "medium"
    assert len(h_b_result.review_outcome.adapter_result.findings) == 1

    disposition_service, post_review_automation_service = _build_post_review_services(
        review_execution_context
    )
    orchestration_service = ProjectDirectorBoundedReworkPostReviewOrchestrationService(
        review_execution_service=review_execution_context.review_execution_service,
        disposition_service=disposition_service,
        post_review_automation_service=post_review_automation_service,
    )
    h_c_result = orchestration_service.orchestrate_fresh_post_review(
        session_id=review_execution_context.session_id,
        source_task_id=review_execution_context.task_id,
        source_review_outcome_message_id=h_b_result.review_outcome_message.id,
    )
    assert h_c_result.status == "post_review_orchestrated", h_c_result.blocked_reasons
    assert h_c_result.disposition is not None
    assert h_c_result.disposition.disposition_type == "AUTO_REWORK"
    assert h_c_result.disposition.disposition_reason == (
        "review_changes_required_within_automatic_rework_boundary"
    )
    assert h_c_result.p22_summary is not None
    assert h_c_result.p22_summary_message is not None
    assert h_c_result.p22_summary.orchestration_status == "ready_for_future_transition"
    assert h_c_result.p22_summary.route == "bounded_automatic_rework"
    assert h_c_result.p22_summary.transition_kind == "BOUNDED_REWORK_GUARDRAIL"
    assert h_c_result.p22_summary.transition_authority == "AUTOMATED_DISPOSITION"
    assert h_c_result.p22_summary.evidence_fresh is True

    candidate_context = review_execution_context.review_preflight_context.candidate_context
    return RealP25AttemptZeroNextAttemptConvergenceContext(
        review_execution_context=review_execution_context,
        h_b_result=h_b_result,
        h_c_result=h_c_result,
        convergence_service=ProjectDirectorBoundedReworkConvergenceService(
            message_repository=review_execution_context.message_repository,
            candidate_diff_service=candidate_context.candidate_diff_service,
            review_execution_service=review_execution_context.review_execution_service,
            post_review_automation_service=post_review_automation_service,
        ),
    )


def build_fresh_next_attempt_convergence_services(
    context: RealP25AttemptZeroNextAttemptConvergenceContext,
) -> FreshP25NextAttemptConvergenceServices:
    """Rebuild the complete P25-B through P25-H-C graph with a new Session."""

    review_execution_services = build_fresh_review_execution_services(
        context.review_execution_context
    )
    message_repository = (
        review_execution_services.review_preflight_services.candidate_services
        .outcome_services.claim_services.reservation_services.message_repository
    )
    disposition_service, post_review_automation_service = _build_post_review_services(
        SimpleNamespace(
            session=review_execution_services.session,
            message_repository=message_repository,
            review_execution_service=review_execution_services.review_execution_service,
        )
    )
    orchestration_service = ProjectDirectorBoundedReworkPostReviewOrchestrationService(
        review_execution_service=review_execution_services.review_execution_service,
        disposition_service=disposition_service,
        post_review_automation_service=post_review_automation_service,
    )
    return FreshP25NextAttemptConvergenceServices(
        review_execution_services=review_execution_services,
        orchestration_service=orchestration_service,
        convergence_service=ProjectDirectorBoundedReworkConvergenceService(
            message_repository=message_repository,
            candidate_diff_service=(
                review_execution_services.review_preflight_services.candidate_services
                .candidate_diff_service
            ),
            review_execution_service=review_execution_services.review_execution_service,
            post_review_automation_service=post_review_automation_service,
        ),
    )
